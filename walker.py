"""Простой автопилот пешком: идёт вперёд, при застревании поворачивает, на заставках ждёт.
Запуск: .venv/bin/python walker.py [минуты]. Стоп: Ctrl+C или kill."""
import base64, io, random, sys, time
import numpy as np, requests
from PIL import Image
import gta_tools as g

API = "http://127.0.0.1:8765"
MINUTES = float(sys.argv[1]) if len(sys.argv) > 1 else 5


def img(b64): return np.asarray(Image.open(io.BytesIO(base64.b64decode(b64))).convert("L").resize((160, 90)), dtype=np.float32)


def play(steps, frames=2):
    total = sum(s.get("ms", 0) for s in steps)
    r = requests.post(f"{API}/api/play", json={"steps": steps, "frame_every_ms": max(1, total // max(1, frames - 1)), "width": 640}, timeout=60).json()
    if not r.get("ok"):
        raise RuntimeError(r.get("error"))
    return [img(f["jpeg_b64"]) for f in r["frames"]]


def letterbox(a):  # заставка: чёрные полосы сверху и снизу
    return a[:5].mean() < 8 and a[-5:].mean() < 8


g.log("say", text="Иду гулять по городу", tag="")
end = time.time() + MINUTES * 60
stuck = 0
while time.time() < end:
    try:
        fr = play([{"left": [0, -1], "hold": ["CROSS"] if random.random() < .3 else [], "ms": 2500}], frames=3)
    except Exception as e:
        print("err", e); time.sleep(2); continue
    if letterbox(fr[-1]):
        print("cutscene, wait"); time.sleep(3); continue
    diff = float(np.abs(fr[0] - fr[-1]).mean())
    print(f"walk diff={diff:.1f}", flush=True)
    if diff < 6:
        stuck += 1
        side = random.choice([-1, 1])
        g.log("say", text="Упёрся, разворачиваюсь", tag="funny" if stuck > 2 else "")
        play([{"right": [side, 0], "ms": 700}, {"left": [side, 0], "ms": 800}], frames=1)
    else:
        stuck = 0
        if random.random() < .25:  # иногда осматривается
            play([{"left": [0, -1], "right": [random.choice([-.6, .6]), 0], "ms": 600}], frames=1)
g.log("say", text="Прогулка окончена", tag="")
