"""Агент: медленный цикл с мозгом Haiku поверх быстрого автопилота pilot.py (15 Гц).

Мозг спрашиваем ПО СОБЫТИЯМ (сменился state пилота, сели/вышли из машины, изменился HUD:
упало здоровье, появились звёзды, WASTED) или по пульсу: пешком ~4 с, за рулём ~6 с,
на игровом автопилоте ~9 с.

Цель car: найти машину → (WAiNK-скан припаркованной) → угнать → завести → игровой автопилот
до метки (↓ Quick Navigation + Options = кинокамера, держать ○ = Auto-Drive). Если автопилот
не едет — повтор один раз, потом ручная езда pilot drive. Приехали — лог и стоп.
Запуск: .venv/bin/python agent.py car|goto|drive|fight [минуты]
Переменные: WAINK=0 — не сканировать машины перед угоном."""
import io, os, re, sys, time
import requests
from brain import Brain
import gta_tools as g
from semi import semi

API = "http://127.0.0.1:8765"
GOAL = sys.argv[1] if len(sys.argv) > 1 else "car"
MIN = float(sys.argv[2]) if len(sys.argv) > 2 else 4
WAINK = os.environ.get("WAINK", "1") != "0"
GOALS = {"car": "ЦЕЛЬ: лучше всего машину С ВОДИТЕЛЕМ (стоит на светофоре/едет медленно) — тогда мотор заведён. Найти ближайшую машину (припаркованную или стоящую на дороге), подойти вплотную и угнать. Иди к улицам и парковкам. turn — на машину. НЕ угоняй, если рядом полиция — найди другую. Новые дорогие спорткары часто keyless (подсказка Clone Key) — их не завести; лучше старые/дешёвые седаны, пикапы, фургоны или машина с водителем.",
         "goto": "ЦЕЛЬ: дойти до метки на компасе, обходя препятствия.",
         "fight": "ЦЕЛЬ: выжить в перестрелке. Отмечай threat, enemy_turn (где враг) и health. Если здоровья мало — найти укрытие/убежать.",
         "drive": "ЦЕЛЬ: мы за рулём (велосипед/машина). Едем к метке на компасе по дорогам. turn — руль: -1 влево, 1 вправо. obstacle=true если впереди препятствие и надо объехать."}
# пульс мозга (с) по фазам; событие спрашивает сразу, но не чаще MIN_GAP
HEARTBEAT = {"car": 4.0, "goto": 4.0, "fight": 3.0, "drive": 6.0, "auto": 9.0}
MIN_GAP = 1.5
TICK = 0.5
EXTRA = (' Добавь поля: "occupied":true/false (в ближайшей машине сидит водитель),'
         ' "dist":"расстояние до цели на компасе вверху по центру как написано, напр. 0.18 mi / 300 ft, или пусто",'
         ' "wasted":true/false (на экране WASTED/BUSTED/ПОТРАЧЕНО), "stars":0..6 (звёзды розыска справа сверху).')
b = Brain()


# ---------- API ----------
def play(steps):
    try:
        return requests.post(f"{API}/api/play", json={"steps": steps, "frame_every_ms": 0, "width": 320}, timeout=60).json()
    except Exception as e:
        print("play error:", e, flush=True)
        return {}


def shot(w=512):
    return requests.get(f"{API}/api/screen.jpg?width={w}", timeout=20).content


def status() -> dict:
    try:
        return requests.get(f"{API}/api/pilot", timeout=10).json() or {}
    except Exception:
        return {}


def pilot_start(mode):
    try:
        requests.post(f"{API}/api/pilot/start", json={"mode": mode, "seconds": max(10, end - time.time()), "sprint": True}, timeout=60)
    except Exception as e:
        print("pilot start error:", e, flush=True)


def pilot_stop():
    try:
        requests.post(f"{API}/api/pilot/stop", timeout=10)
    except Exception:
        pass


def hint(h):
    try:
        requests.post(f"{API}/api/pilot/hint", json=h, timeout=10)
    except Exception:
        pass


def ask(note, img=None) -> dict:
    try:
        h = b.ask(img or shot(), note)
    except Exception as e:  # таймаут/упал процесс claude
        print("brain error:", e, flush=True)
        try:
            b.restart()
        except Exception:
            pass
        return {}
    return h if isinstance(h, dict) else {}


def say(text, tag=""):
    g.log("say", text=text, tag=tag)
    print("SAY:", text, flush=True)


# ---------- HUD / кадры ----------
def hud_of(st, h=None) -> dict:
    """HUD из /api/pilot (поле hud от hud.py) с запасным вариантом из ответа мозга.
    Ожидаем hud = {health: 0..1 или 0..100, stars: int, wasted: bool, busted?: bool}; всё опционально."""
    raw = st.get("hud") if isinstance(st.get("hud"), dict) else {}
    out = {"health": None, "stars": None, "wasted": False}
    hp = raw.get("health")
    if isinstance(hp, (int, float)) and not isinstance(hp, bool):
        out["health"] = float(hp) / (100.0 if hp > 1 else 1.0)
    stars = raw.get("stars")
    if isinstance(stars, (int, float)) and not isinstance(stars, bool):
        out["stars"] = int(stars)
    out["wasted"] = bool(raw.get("wasted") or raw.get("busted") or raw.get("dead"))
    if h:
        if out["stars"] is None and isinstance(h.get("stars"), (int, float)) and not isinstance(h.get("stars"), bool):
            out["stars"] = int(h["stars"])
        seen = (h.get("see") or "").lower()
        if h.get("wasted") is True or any(w in seen for w in ("wasted", "busted", "потрачено", "арестован")):
            out["wasted"] = True
    return out


def gray(w=160):
    """Маленький серый кадр для детекции движения (без мозга)."""
    try:
        import numpy as np
        from PIL import Image
        return np.asarray(Image.open(io.BytesIO(shot(w))).convert("L"), dtype=np.int16)
    except Exception:
        return None


def motion(a, c) -> float | None:
    if a is None or c is None or a.shape != c.shape:
        return None
    return float(abs(a - c).mean())


def parse_dist(s) -> float | None:
    """'0.18 mi' / '300 ft' / '1.2 km' / '250 m' -> мили."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(mi|ft|km|m)\b", str(s or "").lower())
    if not m:
        return None
    v = float(m.group(1).replace(",", "."))
    return {"mi": v, "ft": v / 5280, "km": v / 1.609, "m": v / 1609}[m.group(2)]


def is_menu(h) -> bool:
    seen = (h.get("see") or "").lower()
    return any(w in seen for w in ("фоторежим", "меню", "пауз", "карта gta", "photo"))


def has_lr(pr) -> bool:  # мини-игра проводки: кольца L и R
    p = " " + pr
    return " l" in p and " r" in p and len(pr) < 15


# ---------- угон ----------
def skip_car(why, inside=False):
    say({"keyless": "Эта машина без ключа — нужна другая", "tracker": "На машине трекер — копы найдут, ищу другую",
         "scan": "Сканер против — ищу другую машину"}.get(why, "Ищу другую машину"), "fail")
    pilot_stop()
    steps = [{"hold": ["TRIANGLE"], "ms": 400}, {"ms": 2500}] if inside else []
    steps += [{"right": [1, 0], "ms": 1000}, {"left": [0, -1], "ms": 3000}, {"hold": ["L3"], "ms": 300}, {"left": [0, -1], "ms": 2000}]
    play(steps)
    pilot_start("car")


def waink_scan() -> dict:
    """Держать ↑ ~1 с — сканер WAiNK на машину перед нами, прочитать карточку, закрыть ○."""
    pilot_stop()
    play([{"hold": ["UP"], "ms": 1000}, {"ms": 900}])
    h = ask("Открыт сканер WAiNK в телефоне, наведён на машину. Прочитай карточку машины. Добавь поля: "
            '"scan_ok":true/false (карточка видна), "lock":"unlocked|locked|key cloner|registered|?", '
            '"alarm":"alarmed|deactivated|?", "tracker":"none|standard|advanced|?" (advanced = красная иконка), '
            '"tool":"slim jim|smash|key cloner|none|?" (что нужно для взлома), "occupied":true/false. JSON.')
    play([{"hold": ["CIRCLE"], "ms": 300}, {"ms": 600}])
    print("waink:", h, flush=True)
    return h


def scan_verdict(s) -> str | None:
    """None — брать; иначе причина пропуска."""
    if not s.get("scan_ok", True):
        return None  # не прочитали — не мешаем старой логике (Clone Key по подсказке)
    txt = " ".join(str(s.get(k) or "") for k in ("lock", "tool", "prompts", "see")).lower()
    if "clon" in txt or "keyless" in txt:
        return "keyless"
    if "advanced" in str(s.get("tracker") or "").lower():
        return "tracker"
    if "registered" in str(s.get("lock") or "").lower():
        return "scan"
    return None


def slim_jim():
    """△ Slim Jim + вращать правый стик по кругу, пока не щёлкнет замок."""
    import math
    circle = []
    for i in range(24):
        a = 2 * math.pi * i / 24
        circle.append({"right": [math.sin(a), -math.cos(a)], "ms": 60})
    play([{"hold": ["TRIANGLE"], "ms": 400}, {"ms": 500}] + circle * 4 + [{"ms": 800}])


def hotwire():
    say("Завожу без ключа: провода полукругом", "mission")
    pilot_stop()
    # L по правой дуге, R по левой, снизу вверх (см. controls_gta6.md)
    play(semi({"left": 1, "right": -1}, 2500, 30) + [{"left": [0, -1], "right": [0, -1], "ms": 600}, {"right": [0, 0.5], "ms": 300}])


def break_in(h) -> bool:
    """У машины: по подсказкам довести до 'сидим в машине и мотор заведён'. False — бросили машину."""
    pilot_stop()
    for i in range(7):
        pr = (h.get("prompts") or "").lower()
        inside = bool(h.get("in_car"))
        if "clone" in pr and "slim" not in pr and "smash" not in pr:
            skip_car("keyless", inside=inside)
            return False
        if inside:
            if has_lr(pr):
                hotwire()
            else:
                say("Я в машине", "win")
                return True
        elif "slim" in pr:
            say("Вскрываю Slim Jim", "mission")
            slim_jim()
        elif "smash" in pr or "разб" in pr:
            play([{"hold": ["SQUARE"], "ms": 400}, {"ms": 3500}])  # □ разбить стекло (проверено)
        else:  # с водителем / не заперта — △ сесть (выкинуть водителя)
            play([{"left": [0, -1], "ms": 500}, {"hold": ["TRIANGLE"], "ms": 400}, {"ms": 1800}])
        h = ask("Мы угоняем машину. Что за кнопочные подсказки на экране и сидим ли уже в машине (мотор заведён)? JSON.")
        print("break_in:", h, flush=True)
    return bool(h.get("in_car")) and not has_lr((h.get("prompts") or "").lower())


# ---------- игровой автопилот ----------
def autodrive_on(gas=False):
    """↓ держать (Quick Navigation) + Options не отпуская (кинокамера) → держать ○ (Auto-Drive)."""
    steps = [{"hold": ["DOWN"], "ms": 1200}, {"hold": ["DOWN", "OPTIONS"], "ms": 350}, {"ms": 700}]
    if gas:  # если подсказка Auto-Drive не появилась — чуть газануть
        steps += [{"hold": ["R2"], "ms": 500}]
    steps += [{"hold": ["CIRCLE"], "ms": 2500}, {"ms": 500}]
    play(steps)


def autodrive_off():
    play([{"hold": ["DOWN"], "ms": 1500}, {"ms": 500}])  # удержание ↓ возвращает обычный вид


# ---------- главный цикл ----------
end = time.time() + MIN * 60
phase = {"car": "car", "goto": "goto", "fight": "fight", "drive": "drive"}.get(GOAL, "car")
if phase == "car":
    pilot_start("car")
elif phase == "drive":
    pilot_start("drive")
else:
    pilot_start(phase)
print("phase:", phase, "minutes:", MIN, "waink:", WAINK, flush=True)

last = "нет"
last_ask = 0.0
force = True              # спросить мозг на следующем тике
prev = {"state": None, "in_car": None, "health": None, "stars": None}
scanned_at = 0.0          # кулдаун WAiNK (одна машина — один скан)
wasted_until = 0.0        # после респауна не реагировать на остаточный WASTED
pending = []              # события, накопленные до следующего вопроса мозгу
# состояние игрового автопилота
auto = {"retries": 0, "started": 0.0, "frame": None, "still": 0.0, "dists": [], "bad": 0, "wanted": False}


def enter_auto(retry=False):
    global phase
    pilot_stop()
    if retry:
        say("Автопилот встал — включаю ещё раз", "mission")
        autodrive_on(gas=True)
    else:
        say("Включаю автопилот до метки", "mission")
        autodrive_on()
    phase = "auto"
    auto.update(started=time.time(), frame=gray(), still=0.0, dists=[], bad=0)


def enter_manual(why):
    global phase
    say(f"Автопилот не едет ({why}) — рулю сам", "mission")
    autodrive_off()
    phase = "drive"
    pilot_start("drive")


def arrived(h) -> bool:
    d = parse_dist(h.get("dist"))
    obj = (h.get("objective") or "").strip()
    seen = (h.get("see") or "").lower()
    text = seen + " " + obj.lower()
    return (d is not None and d < 0.03) or h.get("arrived") is True \
        or any(w in text for w in ("mission start", "mission passed", "начало миссии", "задание началось"))


while time.time() < end:
    st = status()
    hud = hud_of(st)
    now = time.time()
    events = pending
    sa, sb = prev["state"], st.get("state")
    if sa != sb and phase != "auto" and ("at_car" in (sa, sb) or {sa, sb} & {"fight", "flee", None}):
        events.append(f"pilot:{sa}->{sb}")  # to_car<->search_car не дёргают мозг
    if hud["stars"] is not None and hud["stars"] != prev["stars"]:
        if (prev["stars"] or 0) == 0 and hud["stars"] > 0:
            say("Звёзды! Нас ищут копы", "police")
            auto["wanted"] = True
        events.append(f"stars:{prev['stars']}->{hud['stars']}")
    if hud["health"] is not None and prev["health"] is not None and hud["health"] < prev["health"] - 0.1:
        events.append(f"health:{prev['health']:.2f}->{hud['health']:.2f}")
    prev.update(state=st.get("state"), stars=hud["stars"] if hud["stars"] is not None else prev["stars"],
                health=hud["health"] if hud["health"] is not None else prev["health"])

    # ---- смерть по HUD (без мозга) ----
    if hud["wasted"] and now > wasted_until and "wasted" not in events:
        events.append("wasted")

    # ---- игровой автопилот: дешёвый контроль движения по кадрам ----
    if phase == "auto":
        f = gray()
        m = motion(auto["frame"], f)
        auto["frame"] = f if f is not None else auto["frame"]
        if m is not None:
            auto["still"] = auto["still"] + TICK + 0.3 if m < 1.5 else 0.0  # +время на кадр
        if auto["still"] >= 8 and now - auto["started"] > 6 and "auto:still" not in events:
            events.append("auto:still")

    hb = HEARTBEAT.get(phase, 4.0)
    if not (force or events or now - last_ask >= hb) or now - last_ask < MIN_GAP:
        time.sleep(TICK)
        continue
    force = False
    pending = []

    # ---- вопрос мозгу ----
    if phase == "auto":
        note = ("Мы в машине на игровом автопилоте (кинокамера, Auto-Drive). Добавь поля: \"autodrive\":true/false "
                "(включён кинорежим/автопилот), \"moving\":true/false (машина едет), \"arrived\":true/false "
                "(приехали: старт миссии/текст задания/цель рядом).")
    elif phase == "drive":
        note = GOALS["drive"] + ' Добавь поле "arrived":true/false.'
    else:
        note = GOALS.get(phase, GOALS["car"]) + f" target_x={st.get('target_x')}; state={st.get('state')};"
    t = time.time()
    h = ask(f"{note}{EXTRA} События: {', '.join(events) or 'пульс'}. Прошлое решение: {last}. JSON.")
    last_ask = time.time()
    hud = hud_of(st, h)
    last = f"{h.get('see')} / mode={h.get('mode')} turn={h.get('turn')}"
    print(f"{last_ask - t:.1f}s [{phase}] {events or 'hb'} | {h.get('see')} | mode {h.get('mode')} turn {h.get('turn')} "
          f"threat {h.get('threat')} hp {h.get('health')} car {h.get('in_car')} pr {h.get('prompts')} dist {h.get('dist')}", flush=True)
    if not h:
        continue
    if is_menu(h):
        play([{"hold": ["CIRCLE"], "ms": 300}, {"ms": 1200}])  # вышли из меню/фото
        last = "был в меню, нажал Back"
        force = True
        continue
    if h.get("say"):
        g.log("say", text=h["say"], tag=h.get("tag", ""))

    # ---- смерть / арест ----
    if hud["wasted"] and time.time() > wasted_until:
        pilot_stop()
        say("Потрачено. Жду респаун", "fail")
        time.sleep(12)
        play([{"hold": ["CROSS"], "ms": 300}, {"ms": 3000}])  # пропустить экран, если ждёт кнопку
        wasted_until = time.time() + 20
        auto.update(retries=0, wanted=False)
        if GOAL in ("car", "drive"):
            phase = "car"
            pilot_start("car")
        else:
            pilot_start(phase)
        force = True
        continue
    if h.get("in_car") is not None and h.get("in_car") != prev["in_car"]:
        if prev["in_car"] is not None:
            force = True  # сели/вышли — перепроверить на следующем тике
        prev["in_car"] = h.get("in_car")
    pr = (h.get("prompts") or "").lower()

    # ---- фаза: ищем машину ----
    if phase == "car":
        if h.get("in_car"):
            if "clone" in pr:
                skip_car("keyless", inside=True)
                last = "сел в keyless — вышел, ищу старую машину или с водителем"
                force = True
                continue
            if has_lr(pr):
                hotwire()
                force = True
                continue
            say("Я в машине", "win")
            auto["retries"] = 0
            enter_auto()
            continue
        if st.get("state") == "at_car":
            occupied = h.get("occupied") is True
            if not occupied and WAINK and now - scanned_at > 25:
                scanned_at = now
                s = waink_scan()
                if s.get("occupied") is True:
                    occupied = True
                why = None if occupied else scan_verdict(s)
                if why:
                    skip_car(why)
                    last = f"скан WAiNK: {why} — бросил, ищу другую"
                    force = True
                    continue
                h2 = ask("Мы у машины. Какие кнопочные подсказки на экране? Сидим ли в машине? JSON.")
                h = h2 or h
            elif occupied:
                say("Машина с водителем — выкидываю", "mission")
            if break_in(h):
                auto["retries"] = 0
                enter_auto()
            else:
                pilot_start("car")
            force = True
            continue
        hint(h)
        continue

    # ---- фаза: игровой автопилот ----
    if phase == "auto":
        if arrived(h):
            say("Приехали к метке!", "win")
            break
        if h.get("in_car") is False and not h.get("threat"):
            say("Мы не в машине — ищу новую", "fail")
            phase = "car"
            pilot_start("car")
            continue
        d = parse_dist(h.get("dist"))
        if d is not None:
            auto["dists"].append(d)
            auto["dists"] = auto["dists"][-4:]
        no_progress = len(auto["dists"]) >= 3 and auto["dists"][-1] >= auto["dists"][-3] - 0.005
        auto["bad"] = auto["bad"] + 1 if (h.get("moving") is False or h.get("autodrive") is False) else 0
        stuck = "auto:still" in events or no_progress or auto["bad"] >= 2
        if stuck and time.time() - auto["started"] > 6:
            why = "стоим" if "auto:still" in events else ("дистанция не падает" if no_progress else "мозг: не едем")
            if auto["wanted"] or (hud["stars"] or 0) > 0:
                enter_manual(why + ", звёзды")  # под розыском автопилот глохнет — сразу руками
            elif auto["retries"] < 1:
                auto["retries"] += 1
                enter_auto(retry=True)
            else:
                enter_manual(why)
            force = True
        continue

    # ---- фаза: ручная езда ----
    if phase == "drive":
        if arrived(h):
            say("Приехали к метке!", "win")
            break
        if h.get("in_car") is False and not h.get("threat"):
            phase = "car"  # выкинули из машины — снова ищем машину
            pilot_start("car")
            force = True
            continue
        hint(h)
        continue

    # ---- goto / fight: как раньше, подсказки пилоту ----
    hint(h)

pilot_stop()
print("agent finished, phase:", phase, flush=True)
