"""GTA 6 macros on top of ps5_play + the public action log ("receipt").

Ported from Santy1422/gta6-mcp (MIT): drive / walk / enter_vehicle / combo / action log,
but sent through ps5-agent-remote's /api/play (libchiaki), not pyremoteplay.
Every action and every agent thought is appended to logs/agent.jsonl:
- the OBS overlay (/overlay) shows it live next to the game;
- the shorts cutter uses `tag` markers (crash, police, fail, win, funny) as clip points.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

LOG = Path(__file__).resolve().parent / "logs" / "agent.jsonl"
MAX_S = 5.0


def _clamp(v: float) -> float:
    return max(-1.0, min(1.0, float(v)))


def log(kind: str, **data) -> dict:
    LOG.parent.mkdir(exist_ok=True)
    rec = {"at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "t": time.time(), "kind": kind, **data}
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def tail(limit: int = 20) -> list[dict]:
    if not LOG.exists():
        return []
    lines = LOG.read_text(encoding="utf-8").splitlines()[-max(1, limit):]
    return [json.loads(x) for x in lines if x.strip()]


def drive_steps(throttle: float, steer: float, seconds: float) -> list[dict]:
    throttle, steer = _clamp(throttle), _clamp(steer)
    ms = int(max(0.2, min(seconds, MAX_S)) * 1000)
    hold = []
    if abs(throttle) > 0.05:
        hold = ["R2" if throttle >= 0 else "L2"]
    return [{"hold": hold, "left": [steer, 0.0], "ms": ms}]


def walk_steps(x: float, y: float, seconds: float, sprint: bool) -> list[dict]:
    ms = int(max(0.2, min(seconds, MAX_S)) * 1000)
    return [{"hold": ["CROSS"] if sprint else [], "left": [_clamp(x), _clamp(y)], "ms": ms}]


def combo_steps(buttons: list[str], interval_ms: int = 80) -> list[dict]:
    half = max(15, interval_ms // 2)
    out: list[dict] = []
    for b in buttons:
        out += [{"hold": [b], "ms": half}, {"ms": half}]
    return out
