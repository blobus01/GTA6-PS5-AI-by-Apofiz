"""Setup wizard API with a mocked PS5 (no console, no network needed).

Run:  .venv/bin/python tests/test_setup_api.py     (or with pytest)
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="ps5setup-"))
os.environ["PS5_REMOTE_HOME"] = str(TMP / "home")
os.environ.pop("PS5_SETUP_MOCK", None)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aiohttp import web  # noqa: E402
from aiohttp.test_utils import TestClient, TestServer  # noqa: E402

import ddp  # noqa: E402
import setup_api  # noqa: E402

FAKE = {"ip": "10.0.0.9", "host-name": "PS5-Test", "host-id": "AABBCCDDEEFF", "system-version": "10010001",
        "status_code": 620, "host-type": "PS5"}


class FakeRemote:
    def __init__(self):
        self.host, self.status = "", {}

    def snapshot(self):
        return {"reachable": bool(self.status), "host": self.host, "power": "standby" if self.status else "unknown",
                "signed_in": None, "linked": False, "connected": False}


def _setup_env():
    setup_api.ENV_LOCAL = TMP / ".env.local"
    setup_api.ENV_LOCAL.write_text("PS5_FPS=60\nPS5_HOST=1.2.3.4\n", encoding="utf-8")
    setup_api.SETUP_FILE = TMP / "home" / "setup.json"
    fake_root = TMP / "root"
    fake_root.mkdir(exist_ok=True)
    (fake_root / "agent.py").write_text(
        "import sys, time\nprint('agent', *sys.argv[1:], flush=True)\ntime.sleep(30)\n", encoding="utf-8")
    setup_api.ROOT = fake_root
    setup_api.AGENT_LOG = fake_root / "logs" / "setup-agent.log"
    ddp.search = lambda host=None, timeout=2.0: [dict(FAKE)] if host in (None, FAKE["ip"]) else []
    ddp.status = lambda host, timeout=1.5: dict(FAKE) if host == FAKE["ip"] else None
    setup_api._ping = lambda host, count=10: setup_api._stats([3.0, 4.0, 3.5, 6.0], 4, "icmp")


async def _run():
    _setup_env()
    remote = FakeRemote()
    app = web.Application()
    setup_api.register(app, lambda: remote)
    async with TestClient(TestServer(app)) as c:
        r = await c.get("/setup")
        assert r.status == 200 and "GTA6 PS5 AI" in await r.text()
        for asset in ("app.js", "setup.css", "apofiz-mark.png"):
            assert (await c.get(f"/setup/assets/{asset}")).status == 200, asset

        st = await (await c.get("/api/setup/state")).json()
        assert st["done"] is False and st["progress"]["step"] == "find"

        d = await (await c.get("/api/setup/discover")).json()
        assert d["consoles"][0]["name"] == "PS5-Test" and d["consoles"][0]["power"] == "standby"

        bad = await c.post("/api/setup/host", json={"host": "rm -rf /"})
        assert bad.status == 400

        h = await (await c.post("/api/setup/host", json={"host": FAKE["ip"]})).json()
        assert h["ok"] and h["reachable"] and remote.host == FAKE["ip"]
        env = setup_api.ENV_LOCAL.read_text(encoding="utf-8")
        assert "PS5_HOST=10.0.0.9" in env and "PS5_HOST=1.2.3.4" not in env and "PS5_FPS=60" in env

        off = await (await c.post("/api/setup/host", json={"host": "10.0.0.77"})).json()
        assert off["ok"] and off["saved"] and not off["reachable"]  # offline PS5 still saves

        n = await (await c.get("/api/setup/network", params={"host": FAKE["ip"]})).json()
        assert n["ok"] and n["ping"]["avg_ms"] == 4.1 and n["kind"] in ("wifi", "ethernet", "other", "vpn", "unknown")

        p = await (await c.post("/api/setup/progress", json={"step": "permissions", "checks": {"perm_rp": 1}})).json()
        assert p["progress"]["step"] == "permissions" and p["progress"]["checks"]["perm_rp"] is True

        b = await (await c.get("/api/setup/brain")).json()
        assert "installed" in b and "commands" in b

        a = await (await c.post("/api/setup/agent/start", json={"mode": "nope"})).json()
        assert not a["ok"]
        a = await (await c.post("/api/setup/agent/start", json={"mode": "mission", "minutes": 2})).json()
        assert a["ok"] and a["running"]
        for _ in range(30):
            s = await (await c.get("/api/setup/agent")).json()
            if s["log"]:
                break
            await asyncio.sleep(0.1)
        assert s["log"][0] == "agent fight 2", s["log"]
        s = await (await c.post("/api/setup/agent/stop", json={})).json()
        assert not s["running"]

        p = await (await c.post("/api/setup/progress", json={"complete": True})).json()
        assert p["done"] is True and setup_api.state_hint()["setup_done"] is True


def test_setup_api():
    asyncio.run(_run())


def test_stats():
    s = setup_api._stats([1.0, 3.0, 2.0], 4, "icmp")
    assert s["loss"] == 25.0 and s["jitter_ms"] == 1.5 and s["avg_ms"] == 2.0
    assert setup_api._stats([], 5, "ddp")["loss"] == 100.0


if __name__ == "__main__":
    t = time.time()
    test_stats()
    test_setup_api()
    print(f"OK setup_api tests passed in {time.time() - t:.1f}s")
