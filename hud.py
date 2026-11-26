"""Быстрое чтение HUD GTA 6 по пикселям (без нейросети), ~1–3 мс на кадр 1280x720.

read(img) -> dict:
  screen      "gameplay" | "black" | "wasted" | "map" | "bright" — что на экране
  hud         bool  — виден компас (синяя полоса вверху по центру) = игровой HUD показан
  health      float 0..1 | None — заполнение полоски здоровья слева вверху (None: полоска скрыта;
                                  в GTA 6 она появляется только после урона)
  health_bar  bool  — полоска здоровья видна
  stars       int   — белые звёзды розыска (0 если нет); то же, что wanted, но всегда int
  wanted      int | None — число белых (горящих) звёзд розыска справа вверху; None если звёзд нет вообще
  wanted_dim  int   — «тусклые» звёзды (серо-светлые: мигание/погоня теряет след)
  wanted_slots int  — сколько слотов звёзд видно (пустые контуры + заполненные)
  red_tint    bool  — красная виньетка урона по краям
  wasted      bool  — экран смерти/ареста (весь кадр красный/серый)
  black       bool  — чёрный экран (загрузка/затемнение)

Координаты откалиброваны на кадрах 1280x720 (другие размеры приводятся к 1280x720):
  полоска здоровья: x 42..132, y 21..25 (тёмно-красная подложка ~R130 G20 B25, заливка ярче R>160,
                    белый разделитель на x≈88)
  звёзды:           6 слотов, центры x = 1128,1152,1176,1200,1224,1248 (шаг 24), y = 29, размер ~14x14;
                    заполняются справа налево
  компас:           синяя линия y 20..24, x 460..820
"""
from __future__ import annotations

import time

import numpy as np  # без cv2: в процессе server.py уже есть PyAV, две копии libavdevice конфликтуют

W0, H0 = 1280, 720
HP_X0, HP_X1, HP_Y0, HP_Y1 = 42, 132, 21, 26
HP_DIV = (85, 92)  # белый разделитель
STAR_CX = [1128 + 24 * k for k in range(6)]
STAR_CY = 29


def _norm(img: np.ndarray, rgb: bool) -> np.ndarray:
    """-> BGR 1280x720 uint8."""
    if img.ndim != 3:
        raise ValueError("ожидается цветной кадр HxWx3")
    h, w = img.shape[:2]
    if (w, h) != (W0, H0):  # PIL nearest — ~1–2 мс для 1080p
        from PIL import Image
        img = np.asarray(Image.fromarray(np.ascontiguousarray(img)).resize((W0, H0), Image.NEAREST))
    if rgb:
        img = img[..., ::-1]
    return img


def _heart(a: np.ndarray) -> bool:
    """Значок-сердце слева от полоски: розовое/красное сердце (центр x≈28,y≈22) в тёмном круге."""
    h = a[18:27, 24:33].astype(np.int16)
    r, g = h[..., 2], h[..., 1]
    hv = (r > 140) & (r - g > 25)
    if hv.sum() < 4:
        return False
    ring = a[20:25, 14:19].astype(np.int16)[..., 2].mean()
    return float(r[hv].mean()) - float(ring) > 60


def _health(a: np.ndarray):
    """-> (present, fraction|None).

    Два вида полоски: обычный — розовая заливка (R~250,G~190,B~218) на сиреневой подложке
    (R~150,G~123,B~137); низкое здоровье — ярко-красная заливка (R>160) на тёмно-красной подложке (R~130,G~20).
    """
    if not _heart(a):
        return False, None
    band = a[HP_Y0:HP_Y1, HP_X0:HP_X1].astype(np.int16).mean(0)  # (90,3) BGR
    b, g, r = band[:, 0], band[:, 1], band[:, 2]
    idx = np.arange(HP_X0, HP_X1)
    keep = (idx < HP_DIV[0]) | (idx >= HP_DIV[1])
    pink = (r > 215) & (g > 150) & (g < 220) & (b > 170) & (r - g > 35) & (r - g < 85)
    mauve = (r > 120) & (r < 185) & (g > 95) & (g < 150) & (b > 110) & (b < 165) & (r - g > 12) & (r - g < 50)
    red_bg = (r > 85) & (r - g > 55) & (r - b > 45)
    red_mid = red_bg & ~pink
    ok = (pink | mauve | red_bg)[keep]
    if ok.mean() < 0.85:
        return False, None
    sel = (idx >= 95) & (idx < 128)
    if red_mid[sel].mean() > 0.7 and pink.mean() < 0.2:  # красный режим (мало здоровья)
        bg_r = float(np.median(r[sel]))
        fill = (r > bg_r + 25) & (r - g > 60) & (r > 150)
    else:
        fill = pink
    fill = fill | ~keep  # разделитель не рвёт заливку
    start = 0
    while start < 5 and not fill[start]:  # левая кромка темнее
        start += 1
    n = 0
    if start < 5:
        n = start
        for v in fill[start:]:
            if not v:
                break
            n += 1
        if n == start:
            n = 0
    frac = n / (HP_X1 - HP_X0 - 1)
    return True, round(min(1.0, frac), 3)


def _stars(a: np.ndarray):
    """-> (white, dim, slots)."""
    white = dim = slots = 0
    for cx in STAR_CX:
        core = a[STAR_CY - 3:STAR_CY + 4, cx - 3:cx + 4].astype(np.int16)
        patch = a[STAR_CY - 8:STAR_CY + 9, cx - 8:cx + 9].astype(np.int16)
        ring = np.concatenate([
            a[STAR_CY - 9:STAR_CY + 10, cx - 12:cx - 10].reshape(-1, 3),
            a[STAR_CY - 9:STAR_CY + 10, cx + 11:cx + 13].reshape(-1, 3),
            a[STAR_CY - 13:STAR_CY - 11, cx - 9:cx + 10].reshape(-1, 3),
        ]).astype(np.int16)
        cmin = core.min(-1)
        cspread = core.max(-1) - cmin
        bg = float(np.median(ring.mean(-1)))
        cv = float(core.mean())
        wfrac = float(((cmin > 185) & (cspread < 50)).mean())
        # белая звезда: ядро белое, а углы патча — нет (иначе это облако/небо)
        corners = np.concatenate([patch[:3, :3], patch[:3, -3:], patch[-3:, :3], patch[-3:, -3:]]).reshape(-1, 3)
        corner_white = float((corners.min(-1) > 185).mean())
        pw = (patch.min(-1) > 185)
        npw = int(pw.sum())
        sym = float((pw & pw[:, ::-1]).sum()) / max(1, npw)  # звезда симметрична слева-направо
        if wfrac > 0.6 and corner_white < 0.5 and bg < 170 and 40 <= npw <= 130 and sym > 0.75:
            white += 1
            slots += 1
        elif cv > bg + 45 and float((cspread < 40).mean()) > 0.7 and cv > 110:
            dim += 1
            slots += 1
        else:
            # пустой контур: ядро чуть темнее фона и однородное
            if -45 < cv - bg < -4 and float(core.std()) < 18:
                slots += 1
    if slots < 3 and not white:  # одиночный «контур» — шум текстуры
        slots = dim = 0
    return white, dim, slots


def _compass(a: np.ndarray) -> bool:
    s = a[19:26, 460:820].astype(np.int16)
    b, g, r = s[..., 0], s[..., 1], s[..., 2]
    blue = (b > 90) & (b - r > 50) & (b - g > 25)
    return float(blue.any(0).mean()) > 0.6


def read(img: np.ndarray, rgb: bool = False) -> dict:
    """Кадр BGR (как cv2.imread) или RGB с rgb=True, любой размер."""
    t0 = time.perf_counter()
    a = _norm(img, rgb)
    sm = a[::8, ::8]
    mx = sm.max(-1).astype(np.int16)
    mn = sm.min(-1).astype(np.int16)
    v = mx
    sat = float(np.where(mx > 0, (mx - mn) * 255 // np.maximum(mx, 1), 0).mean())  # S как в OpenCV HSV
    vmean = float(v.mean())
    smi = sm.astype(np.int16)
    redness = smi[..., 2] - (smi[..., 0] + smi[..., 1]) / 2
    h, w = redness.shape
    ew = max(2, w // 10)
    edge_red = float(np.concatenate([redness[:, :ew].ravel(), redness[:, -ew:].ravel()]).mean())
    center_red = float(redness[h // 4:3 * h // 4, w // 4:3 * w // 4].mean())
    black = vmean < 12 and float(np.percentile(v, 99)) < 45
    grey = (not black) and sat < 12 and vmean < 200
    # экран смерти: весь кадр насыщенно-красный (включая центр) + белая надпись по центру
    cband = a[270:380, 440:840]
    wtext = float((cband.min(-1) > 200).mean())
    wasted = (sat > 140 and center_red > 25 and float(redness.mean()) > 30) or (grey and wtext > 0.01)
    red_tint = (not wasted) and edge_red > 25 and edge_red - center_red > 10
    compass = _compass(a)
    hp_present, hp = (False, None)
    sw = sd = ss = 0
    if not black and not wasted:
        hp_present, hp = _health(a)
        sw, sd, ss = _stars(a)
    if black:
        screen = "black"
    elif wasted:
        screen = "wasted"
    elif compass or hp_present or ss:
        screen = "gameplay"
    elif vmean > 165 and float((sm.min(-1) > 150).mean()) > 0.4:
        screen = "map" if sat > 25 else "bright"
    else:
        screen = "gameplay"  # HUD скрыт (GTA прячет его в покое) — считаем игрой
    return {
        "screen": screen,
        "hud": compass,
        "health": hp if hp_present else None,
        "health_bar": hp_present,
        "stars": sw,  # белые звёзды розыска (0 если нет/не видно)
        "wanted": (sw if (ss or sw or sd) else None),
        "wanted_dim": sd,
        "wanted_slots": ss,
        "red_tint": red_tint,
        "wasted": wasted,
        "black": black,
        "ms": round((time.perf_counter() - t0) * 1000, 2),
    }


if __name__ == "__main__":
    import sys

    from PIL import Image
    for p in sys.argv[1:]:
        print(p, read(np.asarray(Image.open(p).convert("RGB")), rgb=True))
