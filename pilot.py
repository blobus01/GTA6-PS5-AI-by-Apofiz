"""Быстрый автопилот (без нейросети): 15 раз в секунду держит значок цели по центру компаса и бежит к нему.

Компас GTA 6 — полоса вверху экрана, значок цели бирюзовый. Камера поворачивается правым стиком,
персонаж бежит туда, куда смотрит камера (левый стик вперёд). Если значка не видно — крутим камеру.
"""
from __future__ import annotations

import collections
import os
import threading
import time

import numpy as np

import gta_tools
import hud as hudmod

HZ = 15
_yolo = None


def detect(rgb):
    """YOLO: машины и люди на кадре. -> list of (cls, cx, cy, w, h, conf) в долях кадра."""
    global _yolo
    if _yolo is None:
        from ultralytics import YOLO
        _yolo = YOLO("yolo11n.pt")
    r = _yolo.predict(rgb, device="mps", verbose=False, conf=0.35, imgsz=640)[0]
    out = []
    H, W = rgb.shape[:2]
    for (x1, y1, x2, y2), c, p in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(), r.boxes.conf.tolist()):
        name = _yolo.names[int(c)]
        if name in ("car", "truck", "bus", "motorcycle", "person"):
            out.append((name, (x1 + x2) / 2 / W, (y1 + y2) / 2 / H, (x2 - x1) / W, (y2 - y1) / H, p))
    return out


def is_player(d):  # наш персонаж — человек по центру внизу кадра
    return d[0] == "person" and 0.3 < d[1] < 0.7 and d[2] > 0.45 and d[4] > 0.3


def find_target_x(rgb: np.ndarray) -> float | None:
    """x значка цели на компасе, -1..1 от центра, или None."""
    h, w, _ = rgb.shape
    strip = rgb[int(h * 0.02):int(h * 0.09), int(w * 0.30):int(w * 0.70)].astype(np.int16)
    r, g, b = strip[..., 0], strip[..., 1], strip[..., 2]
    mask = (g > 150) & (g - r > 45) & (np.abs(g - b) < 60)
    ys, xs = np.nonzero(mask)
    if len(xs) < 4:
        return None
    x = np.median(xs) + int(w * 0.30)
    return float((x - w / 2) / (w * 0.20))  # край полосы компаса ≈ ±1


def _threat_person(dets):
    """Ближайший к центру чужой человек рядом (не наш персонаж) или None."""
    people = [d for d in dets if d[0] == "person"]
    cands = [d for d in people if is_player(d)]
    me = min(cands, key=lambda d: abs(d[1] - 0.5) + abs(d[2] - 0.6)) if cands else None  # наш — один, ближе всех к центру
    best = None
    for d in people:
        if d is me:
            continue
        close = d[4] > 0.22 or d[3] * d[4] > 0.025
        if close and abs(d[1] - 0.5) < 0.38:
            if best is None or d[4] > best[4]:
                best = d
    return best


class Pilot:
    def __init__(self, remote):
        self.remote = remote
        self.thread: threading.Thread | None = None
        self.stop_evt = threading.Event()
        self._status = {"mode": "idle"}
        self.hint = {}
        self.hint_t = 0.0
        # рефлексы без мозга (HUD по пикселям): вкл/выкл через hint {"reflexes": false} или env PILOT_REFLEXES=0
        self.reflexes = os.environ.get("PILOT_REFLEXES", "1") != "0"
        self.circle_when_stopped = False  # в погоне за рулём: держать ○ при остановке (hint {"circle_when_stopped": true})
        self.hud: dict = {}
        self.hud_t = 0.0
        self._hp_hist: collections.deque = collections.deque()  # (t, health)
        self._stars_t = 0.0  # когда последний раз видели звёзды
        self._stars_last = 0
        self._reflex = ""
        self._hud_lock = threading.Lock()

    # status: то, что отдаёт GET /api/pilot. Всегда содержит hud (даже когда пилот стоит —
    # тогда HUD читается по требованию с последнего кадра, не чаще раза в 0.25 с).
    @property
    def status(self) -> dict:
        st = dict(self._status)
        running = self.thread is not None and self.thread.is_alive()
        st["hud"] = self.hud if running and time.time() - self.hud_t < 1.0 else self.hud_now()
        st["reflexes"] = self.reflexes
        if self._reflex:
            st["reflex"] = self._reflex
        return st

    @status.setter
    def status(self, v: dict) -> None:
        self._status = v

    def hud_now(self) -> dict:
        if time.time() - self.hud_t < 0.25 and self.hud:
            return self.hud
        try:
            rgb = self._frame()
        except Exception:
            rgb = None
        if rgb is None:
            return self.hud or {}
        return self._update_hud(rgb)

    def _update_hud(self, rgb) -> dict:
        try:
            h = hudmod.read(rgb, rgb=True)
        except Exception as e:  # HUD не должен ронять пилота
            return {"error": str(e)}
        now = time.time()
        with self._hud_lock:
            hp = h.get("health")
            if hp is not None:
                self._hp_hist.append((now, hp))
            while self._hp_hist and now - self._hp_hist[0][0] > 2.0:
                self._hp_hist.popleft()
            if h.get("stars"):
                self._stars_t, self._stars_last = now, h["stars"]
            recent = [v for t, v in self._hp_hist if now - t < 1.5]
            h["health_drop"] = round(max(recent) - hp, 3) if (recent and hp is not None) else 0.0
            # звёзды мигают — держим последнее значение 3 с
            h["stars_recent"] = self._stars_last if now - self._stars_t < 3.0 else 0
            h["t"] = round(now, 2)
            self.hud, self.hud_t = h, now
        return h

    def set_hint(self, h: dict) -> None:
        h = dict(h or {})
        if "reflexes" in h:
            self.reflexes = bool(h.pop("reflexes"))
        if "circle_when_stopped" in h:
            self.circle_when_stopped = bool(h.pop("circle_when_stopped"))
        if not h:
            return  # чистое переключение флагов — подсказку мозга не трогаем
        self.hint, self.hint_t = h, time.time()

    def start(self, mode: str = "goto", seconds: float = 120, sprint: bool = True) -> dict:
        self.stop()
        self.stop_evt.clear()
        self.thread = threading.Thread(target=self._run, args=(mode, seconds, sprint), daemon=True, name="pilot")
        self.thread.start()
        gta_tools.log("pilot", mode=mode, seconds=seconds, sprint=sprint)
        return {"ok": True}

    def stop(self) -> dict:
        self.stop_evt.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        s = self.remote.native
        if s:
            s.set_state(set())
        self.status = {"mode": "idle"}
        self._reflex = ""
        return {"ok": True}

    def _frame(self):
        s = self.remote.native
        if not s:
            return None
        with s._frame_lock:
            f = s._frame
        return None if f is None else f.to_ndarray(format="rgb24")

    def _run(self, mode: str, seconds: float, sprint: bool) -> None:
        end = time.time() + seconds
        lost = 0
        prev = None
        still = 0
        unstick_until = 0.0
        ticks = 0
        dets_cache: list = []
        dets_t = 0.0
        fight_until = 0.0
        while not self.stop_evt.is_set() and time.time() < end:
            t0 = time.time()
            self.remote.touch()
            s = self.remote.native
            rgb = self._frame()
            if s is None or rgb is None:
                time.sleep(0.2)
                continue
            ticks += 1
            small = rgb[::16, ::16].mean(-1)
            if prev is not None:
                still = still + 1 if float(np.abs(small - prev).mean()) < 2.0 else 0
            prev = small
            x = find_target_x(rgb)
            held = {"L3"} if (sprint and ticks % 30 == 0) else set()  # бег = клик L3 (не ✕!)
            hint_fresh = time.time() - self.hint_t < 5
            h = self._update_hud(rgb)
            self._reflex = ""
            if self.reflexes:
                now = time.time()
                in_car = mode == "drive" or (hint_fresh and bool(self.hint.get("in_car")))
                # 1) смерть/чёрный экран/карта — руки прочь от джойстика
                if h.get("black") or h.get("wasted") or h.get("screen") in ("map", "bright"):
                    s.set_state(set())
                    self._reflex = "pause:" + str(h.get("screen"))
                    self.status = {"mode": mode, "state": "paused", "why": h.get("screen")}
                    still, prev, fight_until = 0, None, 0.0
                    time.sleep(max(0.0, 1 / HZ - (time.time() - t0)))
                    continue
                hp = h.get("health")
                stars = int(h.get("stars_recent") or 0)
                danger = bool(h.get("red_tint")) or (hp is not None and hp < 0.3) or float(h.get("health_drop") or 0) > 0.12
                if not in_car and (danger or stars or now < fight_until):
                    # YOLO дорогой (~20–40 мс) — только в опасности и не чаще ~5 раз/с
                    if now - dets_t > 0.2:
                        try:
                            dets_cache = detect(rgb)
                        except Exception:
                            dets_cache = []
                        dets_t = now
                    tp = _threat_person(dets_cache)
                    point_blank = tp is not None and tp[4] > 0.45
                    # 2) бьют/стреляют и враг рядом по центру — сразу отвечаем, не ждём мозг
                    if tp is not None and (danger or now < fight_until) and (stars == 0 or point_blank or danger):
                        fight_until = now + 2.0
                        et = max(-1.0, min(1.0, (tp[1] - 0.5) * 2.2))
                        armed = (self.hint.get("armed", True) if hint_fresh else True) and not point_blank
                        if armed:
                            fire = (ticks % 6) < 2  # короткие очереди, L2 — автозахват
                            s.set_state({"L2", "R2"} if fire else {"L2"}, left=(0, 0), right=(0.5 * et, 0))
                        else:
                            s.set_state({"SQUARE"} if ticks % 4 < 2 else set(), left=(0, -0.4), right=(0.6 * et, 0))  # □ рукопашка
                        self._reflex = "fight"
                        self.status = {"mode": mode, "state": "reflex:fight", "enemy_turn": round(et, 2),
                                       "melee": not armed, "health": hp}
                        time.sleep(max(0.0, 1 / HZ - (time.time() - t0)))
                        continue
                    # 3) розыск пешком — убегаем (в режиме car продолжаем искать машину — это и есть побег)
                    if stars and mode != "car" and not (hint_fresh and self.hint.get("mode") == "enter_car"):
                        threats = [d for d in dets_cache if not is_player(d) and (d[0] == "person" or d[0] == "car")]
                        if threats:
                            tx = max(threats, key=lambda d: d[3] * d[4])[1]
                            turn = 0.0 if abs(tx - 0.5) > 0.25 else (-0.8 if tx >= 0.5 else 0.8)  # отворачиваем от угрозы
                        else:
                            turn = 0.0 if x is None else max(-1.0, min(1.0, x * 2.0))
                        if time.time() < unstick_until:
                            s.set_state({"CROSS"} if ticks % 10 == 0 else set(), left=(0.8, -1.0))
                        else:
                            s.set_state({"L3"} if ticks % 15 == 0 else set(), left=(0, -1.0), right=(turn, 0))
                        if still > HZ * 1.5 and time.time() >= unstick_until:
                            unstick_until = time.time() + 1.2
                            still = 0
                        self._reflex = "flee"
                        self.status = {"mode": mode, "state": "reflex:flee", "stars": stars, "turn": round(turn, 2)}
                        time.sleep(max(0.0, 1 / HZ - (time.time() - t0)))
                        continue
            if hint_fresh and self.hint.get("threat") and self.hint.get("health") != "low" and not self.hint.get("in_car"):
                et = max(-1.0, min(1.0, float(self.hint.get("enemy_turn", 0) or 0)))
                fire = (ticks % 6) < 2  # короткие очереди
                s.set_state({"L2", "R2"} if fire else {"L2"}, left=(0, 0), right=(0.5 * et, 0))  # L2 — автозахват цели
                self.status = {"mode": mode, "state": "fight", "enemy_turn": et}
                time.sleep(max(0.0, 1 / HZ - (time.time() - t0)))
                continue
            if hint_fresh and self.hint.get("threat") and self.hint.get("health") == "low" and not self.hint.get("in_car"):
                ft = -float(self.hint.get("enemy_turn", 0) or 0)
                s.set_state({"L3"} if ticks % 30 == 0 else set(), left=(0, -1.0), right=(1.0 if ft >= 0 else -1.0, 0))  # мало здоровья — бежим (L3)
                self.status = {"mode": mode, "state": "flee"}
                time.sleep(max(0.0, 1 / HZ - (time.time() - t0)))
                continue
            if mode == "car":
                dets = [d for d in detect(rgb) if d[0] in ("car", "truck")]
                if dets:
                    tgt = max(dets, key=lambda d: d[3] * d[4])
                    ex = (tgt[1] - 0.5) * 2
                    turn = max(-1.0, min(1.0, ex * 2.0))
                    if 0.05 < abs(ex) and abs(turn) < 0.4:
                        turn = 0.4 if turn > 0 else -0.4
                    close = tgt[3] * tgt[4] > 0.10 or tgt[4] > 0.35
                    if close:
                        s.set_state({"TRIANGLE"}, left=(0, -0.5), right=(turn * 0.5, 0))
                        self.status = {"mode": mode, "state": "at_car", "area": round(tgt[3] * tgt[4], 3)}
                    else:
                        s.set_state(held if abs(ex) < 0.4 else set(), left=(0, -1.0 if abs(ex) < 0.4 else -0.3), right=(turn, 0))
                        self.status = {"mode": mode, "state": "to_car", "ex": round(ex, 2), "area": round(tgt[3] * tgt[4], 3)}
                    lost = 0
                else:
                    lost += 1
                    if time.time() - self.hint_t < 5 and self.hint.get("obstacle"):
                        ht = float(self.hint.get("turn", 0) or 0)
                        s.set_state(held, left=(0, -1.0), right=(0.6 * ht, 0))
                    else:
                        s.set_state(held if lost % 60 < 40 else set(), left=(0, -1.0) if lost % 60 < 40 else (0, 0), right=(0, 0) if lost % 60 < 40 else (0.8, 0))  # идём и иногда осматриваемся
                    self.status = {"mode": mode, "state": "search_car"}
                if still > HZ * 2 and time.time() >= unstick_until:
                    unstick_until = time.time() + 1.0
                    still = 0
                if time.time() < unstick_until:
                    s.set_state({"CROSS"} if ticks % 10 == 0 else set(), left=(0.8, -1.0))
                time.sleep(max(0.0, 1 / HZ - (time.time() - t0)))
                continue
            if mode == "drive":
                hint_ok = time.time() - self.hint_t < 5 and self.hint.get("obstacle")
                steer = float(self.hint.get("turn", 0) or 0) if hint_ok else (0.0 if x is None else max(-1.0, min(1.0, x * 2.5)))
                if x is None and not hint_ok:
                    steer = 0.6
                gas = {"R2"}  # R2 газ
                if still > HZ * 2 and time.time() >= unstick_until:
                    unstick_until = time.time() + 1.5
                    still = 0
                    gta_tools.log("say", text="Застрял, сдаю назад", tag="funny")
                wanted = self.reflexes and bool(self.hud.get("stars_recent"))
                if time.time() < unstick_until:
                    rev = {"L2"}
                    if wanted and self.circle_when_stopped:
                        rev = {"L2", "CIRCLE"}
                    s.set_state(rev, left=(-steer, 0))
                else:
                    s.set_state(gas, left=(steer, 0))  # в розыске просто едем дальше, не останавливаемся
                self.status = {"mode": mode, "state": "driving", "target_x": None if x is None else round(x, 2), "steer": round(steer, 2), "wanted": wanted}
                time.sleep(max(0.0, 1 / HZ - (time.time() - t0)))
                continue
            if time.time() < unstick_until:
                s.set_state({"CROSS"} if ticks % 10 == 0 else held, left=(0.8, -1.0))  # обход + прыжок/перелезть (✕)
            elif time.time() - self.hint_t < 5 and self.hint.get("mode") in ("walk", "enter_car", "flee"):
                ht = max(-1.0, min(1.0, float(self.hint.get("turn", 0) or 0)))
                since = time.time() - self.hint_t
                turn_time = abs(ht) * 1.0  # разовый поворот: turn=1 ≈ 90° (замер 25.11: 0.45 с ≈ 40°), потом прямо
                if since < turn_time:
                    s.set_state(set(), left=(0, 0), right=(1.0 if ht > 0 else -1.0, 0))
                elif self.hint.get("mode") == "enter_car" and since > 2.5:
                    s.set_state({"TRIANGLE"}, left=(0, -1.0))
                else:
                    s.set_state(held, left=(0, -1.0), right=(0, 0))
                self.status = {"mode": mode, "state": "brain:" + str(self.hint.get("mode")), "turn": ht}
            elif x is None:
                lost += 1
                s.set_state(set(), left=(0, 0), right=(0.7, 0))  # ищем значок, крутим камеру
                if lost > HZ * 8:
                    self.status = {"mode": mode, "state": "target not visible"}
            else:
                lost = 0
                turn = max(-1.0, min(1.0, x * 3.0))
                if 0.04 < abs(x) and abs(turn) < 0.4:
                    turn = 0.4 if turn > 0 else -0.4  # мёртвая зона стика в GTA
                fwd = -1.0 if abs(x) < 0.6 else -0.3
                s.set_state(held, left=(0, fwd), right=(turn, 0))
                self.status = {"mode": mode, "state": "moving", "target_x": round(x, 2)}
            if still > HZ * 1.5 and time.time() >= unstick_until:
                gta_tools.log("say", text="Застрял, обхожу препятствие", tag="funny")
                unstick_until = time.time() + 1.2
                still = 0
            time.sleep(max(0.0, 1 / HZ - (time.time() - t0)))
        if self.remote.native:
            self.remote.native.set_state(set())
        self.status = {"mode": "idle", "last": "finished"}
        gta_tools.log("pilot", mode="stop")
