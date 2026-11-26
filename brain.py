"""Мозг агента: постоянный сеанс Claude Code (подписка), кадр с PS5 → JSON-решение.
Один процесс claude в режиме stream-json, кадры отправляются картинкой (base64) без перезапуска.

Ускорение 26.11 (замеры на сохранённых кадрах: медиана ~4.1 с → ~2.6 с):
  * модель задаётся ЯВНО (BRAIN_MODEL, по умолчанию claude-opus-5-5): алиас "haiku" зависит от окружения —
    внутри Claude Code он подменяется на opus-5-5 (ANTHROPIC_DEFAULT_HAIKU_MODEL из ~/.claude/settings.json),
    а из голого терминала это настоящий Haiku 4.5 — на этих кадрах он медленнее (думал ~1400 ток., 14 с) и врёт;
  * --effort low + подсказка «без размышлений» (NUDGE) — thinking обычно 0 вместо 100–180 ток.
    (MAX_THINKING_TOKENS=0 / CLAUDE_CODE_DISABLE_THINKING на opus-5-5 не действуют, оставлено на всякий случай);
  * модель отвечает короткими ключами и пропускает значения по умолчанию; expand() разворачивает
    в прежний полный формат (see/say/mode/turn/... + occupied/dist/wasted/stars) — для вызывающих ничего не меняется;
  * перезапуск сеанса (каждые RESTART_EVERY-1 вопросов) — на заранее прогретый запасной процесс.
Пол — ~1.5–2 с до первого токена у API, ниже через CLI не опустить. Кадр 448 px быстрее не стал, но хуже читал HUD,
поэтому ширина 512 (как отдаёт сервер)."""
import base64, io, json, os, subprocess, threading, queue, time
import requests

API = "http://127.0.0.1:8765"
HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.environ.get("BRAIN_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("BRAIN_EFFORT", "low")          # "" — не передавать --effort
WIDTH = int(os.environ.get("BRAIN_WIDTH", "512"))       # 0 — не ужимать; кадр шире — ужимается
QUALITY = int(os.environ.get("BRAIN_QUALITY", "85"))     # <85 — пережимать и кадр нужной ширины
NUDGE = os.environ.get("BRAIN_NUDGE", " Без размышлений — сразу JSON.")  # подталкивает модель не «думать» перед ответом
RESTART_EVERY = int(os.environ.get("BRAIN_RESTART_EVERY", "6"))

# Модель отвечает КОРОТКИМИ ключами (вдвое меньше выходных токенов = быстрее), ask() разворачивает их
# в прежний полный формат — вызывающий код видит те же поля, что и раньше.
KEYS = {"s": "see", "y": "say", "m": "mode", "t": "turn", "o": "obstacle", "cs": "car_side", "cc": "car_close",
        "p": "prompts", "ic": "in_car", "th": "threat", "et": "enemy_turn", "h": "health", "ob": "objective", "tg": "tag",
        "oc": "occupied", "d": "dist", "w": "wasted", "st": "stars"}
# что подставить, если модель пропустила ключ (она пропускает значения по умолчанию — экономия токенов)
DEFAULTS = {"see": "", "say": "", "obstacle": False, "car_side": "none", "car_close": False, "prompts": "",
            "in_car": False, "threat": False, "enemy_turn": 0, "health": "ok", "objective": "", "tag": ""}
EXTRA_DEFAULTS = {"wasted": False, "stars": 0}
BOOLS = {"obstacle", "car_close", "in_car", "threat", "occupied", "wasted"}
SIDES = {"l": "left", "r": "right", "c": "center", "n": "none"}
SYSTEM = (open(os.path.join(HERE, "controls_gta6.md"), encoding="utf-8").read() + "\n\n" +
          "Ты пилот-навигатор бота в GTA 6 (вид от третьего лица, PS5). На каждый кадр СРАЗУ отвечай ОДНОЙ строкой JSON "
          "без пояснений и без ```, ключи короткие, true/false пиши 1/0:\n"
          '{"s":"что видишь, до 5 слов","y":"фраза для эфира от лица ИИ, по-русски, до 8 слов; пусто, если с прошлого кадра ничего нового",'
          '"m":"walk|drive|enter_car|fight|flee|wait","t":-1..1 (куда повернуть камеру/руль, минус влево),'
          '"o":1/0 препятствие впереди,"cs":"l|r|c|n" где ближайшая машина,"cc":1/0 машина в 1-3 метрах,'
          '"p":"кнопочные подсказки на экране, напр. △ Slim Jim / □ Smash window, или пусто",'
          '"ic":1/0 мы в машине (камера сзади машины, слева внизу плашка с названием машины, подсказки Clone Key/Hotwire),'
          '"th":1/0 угроза (стреляют, рядом враги, полиция, звёзды розыска),"et":-1..1 где ближайший враг (0 центр),'
          '"h":"ok|low" (low — полоска здоровья слева сверху красная/почти пустая, экран краснеет),'
          '"ob":"текст задания на экране или пусто","tg":"|crash|police|fail|win|funny|mission"}\n'
          'Ключи o,cs,cc,p,th,et,h,ob,tg ПРОПУСКАЙ, если значение по умолчанию (0, "n", пусто, "ok"); s,y,m,t,ic пиши всегда. '
          'Если в вопросе просят доп. поля — добавь их в тот же JSON короче: occupied→"oc":1/0, dist→"d", wasted→"w":1/0 (пропускай если 0), stars→"st" (пропускай если 0); прочие — с теми именами, как просили. '
          'ТЫ ведёшь бота: t — куда повернуть камеру (персонаж бежит туда, куда смотрит камера). В подсказке дано, где метка цели на компасе (target_x: -1 слева, 0 прямо, 1 справа) и сколько раз уже упирались. '
          'Не ломись в забор/стену повторно: выбери обход по улице или тротуару и держи его несколько ходов. Если рядом машина или самокат — m=enter_car и t на неё. Если цель видна и путь свободен — t по target_x.')


def expand(d: dict, full: bool = True) -> dict:
    """Короткие ключи → полные (see/say/mode/...), 1/0 → bool. Полные ключи пропускаются как есть."""
    if not isinstance(d, dict):
        return d
    out = {KEYS.get(k, k): v for k, v in d.items()}
    if full:
        for k, v in DEFAULTS.items():
            out.setdefault(k, v)
    for k in BOOLS:
        if k in out and isinstance(out[k], (int, float, str)) and not isinstance(out[k], bool):
            out[k] = str(out[k]).strip().lower() in ("1", "true", "yes", "1.0")
    if out.get("car_side") in SIDES:
        out["car_side"] = SIDES[out["car_side"]]
    return out


def prep(jpeg: bytes, width: int = None, quality: int = None) -> bytes:
    """Ужать кадр до width px (JPEG quality). Без PIL или при ошибке — кадр как есть."""
    width = WIDTH if width is None else width
    quality = QUALITY if quality is None else quality
    if not width:
        return jpeg
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(jpeg))
        if im.width > width:
            im = im.convert("RGB").resize((width, round(im.height * width / im.width)), Image.BILINEAR)
        elif quality >= 85:
            return jpeg
        out = io.BytesIO()
        im.convert("RGB").save(out, "JPEG", quality=quality)
        return out.getvalue() if out.tell() < len(jpeg) else jpeg
    except Exception:
        return jpeg


def shot(w: int = 512) -> bytes:
    return requests.get(f"{API}/api/screen.jpg?width={w}", timeout=20).content


class _Proc:
    """Один процесс claude -p (stream-json) со своей очередью ответов."""

    def __init__(self, model, system, effort):
        env = dict(os.environ, MAX_THINKING_TOKENS="0")
        import shutil, tempfile
        claude = shutil.which("claude") or "claude"   # npm on Windows installs claude.cmd
        # system prompt via file: cmd.exe limits a .cmd call to 8191 chars
        spf = os.path.join(tempfile.gettempdir(), "apofiz_brain_system.txt")
        with open(spf, "w", encoding="utf-8") as f:
            f.write(system)
        cmd = [claude, "-p", "--model", model, "--input-format", "stream-json", "--output-format", "stream-json",
               "--verbose", "--system-prompt-file", spf, "--tools", "", "--strict-mcp-config",
               "--setting-sources", "", "--disable-slash-commands", "--no-session-persistence"]
        if effort:
            cmd += ["--effort", effort]
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  text=True, encoding="utf-8", errors="replace", bufsize=1, env=env, cwd=HERE)
        self.q = queue.Queue()
        self.n = 0
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.p.stdout:
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if ev.get("type") == "result":
                self.q.put(ev)

    def alive(self):
        return self.p.poll() is None

    def kill(self):
        try:
            self.p.kill()
        except Exception:
            pass


class Brain:
    def __init__(self, model=None, system=None, effort=None, restart_every=None, width=None, quality=None):
        self.model = model if model and model != "haiku" else MODEL  # "haiku" — старое имя, см. docstring
        self.system = system or SYSTEM
        self.effort = EFFORT if effort is None else effort
        self.restart_every = RESTART_EVERY if restart_every is None else restart_every
        self.width, self.quality = width, quality
        self.cur = _Proc(self.model, self.system, self.effort)
        self.spare = None
        self._lock = threading.Lock()
        self._spawn_spare()

    def _spawn_spare(self):
        def go():
            new, old = _Proc(self.model, self.system, self.effort), self.spare
            self.spare = new
            if old is not None and old is not self.cur:
                old.kill()  # гонка двух запасных — лишний не оставляем висеть
        threading.Thread(target=go, daemon=True).start()

    def restart(self):
        """Новый чистый контекст: берём прогретый запасной процесс, старый убиваем."""
        old = self.cur
        sp = self.spare
        self.cur = sp if sp is not None and sp.alive() else _Proc(self.model, self.system, self.effort)
        self.spare = None
        old.kill()
        self._spawn_spare()

    def close(self):
        for pr in (self.cur, self.spare):
            if pr:
                pr.kill()

    def ask(self, jpeg: bytes, note: str = "") -> dict:
        with self._lock:
            if not self.cur.alive() or (self.restart_every and self.cur.n >= self.restart_every - 1):
                self.restart()  # не копим старые кадры в контексте
            pr = self.cur
            pr.n += 1
            while not pr.q.empty():  # опоздавший ответ прошлого (таймаутнувшего) вопроса
                pr.q.get_nowait()
            img = prep(jpeg, self.width, self.quality)
            msg = {"type": "user", "message": {"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(img).decode()}},
                {"type": "text", "text": (note or "Кадр.") + NUDGE}]}}
            t = time.time()
            pr.p.stdin.write(json.dumps(msg) + "\n"); pr.p.stdin.flush()
            ev = pr.q.get(timeout=60)
            self._log(ev, time.time() - t, len(img))
            txt = ev.get("result", "") or ""
        s, e = txt.find("{"), txt.rfind("}")
        try:
            r = expand(json.loads(txt[s:e + 1]), self.system is SYSTEM)
            for k, v in EXTRA_DEFAULTS.items():  # доп. поля, которые просили в вопросе, но модель пропустила как 0
                if k in r or f'"{k}"' not in (note or ""):
                    continue
                r[k] = v
            return r
        except Exception:
            return {"raw": txt}

    def _log(self, ev, dt, nbytes):
        try:
            u = ev.get("usage") or {}
            from paths import LOG_DIR
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            with open(LOG_DIR / "tokens.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"t": time.time(), "model": self.model,
                                    "latency": round(dt, 2), "img_bytes": nbytes,
                                    "thinking": (u.get("output_tokens_details") or {}).get("thinking_tokens"),
                                    "usage": u, "cost": ev.get("total_cost_usd")}) + "\n")
        except Exception:
            pass


if __name__ == "__main__":
    b = Brain()
    for i in range(3):
        jpg = shot()
        t = time.time(); r = b.ask(jpg); print(f"{time.time()-t:.1f}s", r, flush=True)
