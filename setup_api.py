"""First-run setup wizard backend: http://127.0.0.1:8765/setup

Registered by server.py with `setup_api.register(app, lambda: remote)`.
Everything here degrades gracefully when the PS5 is offline: every endpoint
answers with JSON describing what it could and could not check.

Endpoints (all JSON unless noted):
  GET  /setup                      wizard page (web/setup/index.html)
  GET  /setup/assets/*             wizard static files
  GET  /api/setup/state            progress + remote snapshot + done flag
  POST /api/setup/progress         {step?, checks?, complete?} merge into setup.json
  POST /api/setup/reset            forget wizard progress (keys stay)
  GET  /api/setup/discover         LAN discovery via DDP
  POST /api/setup/host             {host} probe + save PS5_HOST to .env.local
  GET  /api/setup/network          ?host= Wi-Fi/Ethernet + ping/jitter to PS5
  GET  /api/setup/brain            claude CLI path/version/login
  POST /api/setup/brain/check      deep check: run a tiny `claude -p` prompt
  POST /api/setup/brain/install    run the official installer (only on click)
  GET  /api/setup/brain/install    installer progress + log
  POST /api/setup/brain/login      open a terminal running `claude` to sign in
  GET  /api/setup/agent            bot status + log tail
  POST /api/setup/agent/start      {mode, minutes} run agent.py as subprocess
  POST /api/setup/agent/stop       stop the bot

Progress lives in ~/.ps5-remote/setup.json (same folder as consoles.json).
Set PS5_SETUP_MOCK=1 to fake a found PS5, network and brain (UI preview).
"""
from __future__ import annotations

import asyncio
import glob
import ipaddress
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

from aiohttp import web

import ddp
import store

ROOT = Path(__file__).parent
WEB = ROOT / "web" / "setup"
ENV_LOCAL = ROOT / ".env.local"
SETUP_FILE = store.HOME / "setup.json"
AGENT_LOG = ROOT / "logs" / "setup-agent.log"
MOCK = os.environ.get("PS5_SETUP_MOCK") == "1"
IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"
STEPS = ["find", "permissions", "psn", "link", "brain", "test", "play"]
MODES = {"car": "car", "drive": "drive", "goto": "goto", "mission": "fight", "fight": "fight"}

_remote_getter = lambda: None  # noqa: E731


def _remote():
    try:
        return _remote_getter()
    except NameError:
        return None


# ---------------------------------------------------------------- progress
def load_progress() -> dict:
    try:
        data = json.loads(SETUP_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return {"step": "find", "checks": {}, "complete": False}


def save_progress(data: dict) -> None:
    store.HOME.mkdir(parents=True, exist_ok=True)
    tmp = SETUP_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(SETUP_FILE)


def _linked_already() -> bool:
    try:
        data = store.load()
    except (OSError, ValueError):
        return False
    return bool(data.get("account") and data.get("consoles"))


def done() -> bool:
    """True when the wizard was finished, or the machine was linked before it existed."""
    return bool(load_progress().get("complete")) or _linked_already()


def state_hint() -> dict:
    """Extra fields server.py merges into GET /api/state."""
    return {"setup_done": done(), "setup_url": "/setup"}


# ---------------------------------------------------------------- helpers
def _run(cmd: list[str] | str, timeout: float = 10, shell: bool = False) -> tuple[int, str]:
    try:
        kw = {"creationflags": subprocess.CREATE_NO_WINDOW} if IS_WIN else {}
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=shell,
                           encoding="utf-8", errors="replace", **kw)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as err:
        return -1, str(err)


def _valid_host(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{0,252}", host))


def _console_view(info: dict) -> dict:
    code = info.get("status_code")
    return {
        "ip": info.get("ip"),
        "name": info.get("host-name") or "PlayStation 5",
        "mac": info.get("host-id"),
        "firmware": info.get("system-version"),
        "power": "on" if code == 200 else ("standby" if code else "unknown"),
        "app": info.get("running-app-name") or "",
    }


MOCK_CONSOLE = {"ip": "192.168.1.42", "host-name": "PS5-Living-Room", "host-id": "5C96664EFA8A",
                "system-version": "10010001", "status_code": 200, "host-type": "PS5"}


def write_env(key: str, value: str) -> None:
    lines = []
    if ENV_LOCAL.exists():
        lines = [l for l in ENV_LOCAL.read_text(encoding="utf-8").splitlines() if not l.startswith(f"{key}=")]
    lines.insert(0, f"{key}={value}")
    ENV_LOCAL.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ[key] = value


# ---------------------------------------------------------------- network
def _iface_for(host: str | None) -> dict:
    """Which interface reaches the PS5 (or the default route) and is it Wi-Fi."""
    out: dict = {"iface": None, "kind": "unknown", "label": None}
    if IS_MAC:
        rc, text = _run(["route", "-n", "get", host or "default"], 5)
        m = re.search(r"interface:\s*(\S+)", text)
        if not m:
            return out
        out["iface"] = m.group(1)
        rc, ports = _run(["networksetup", "-listallhardwareports"], 5)
        for block in ports.split("\n\n"):
            pm = re.search(r"Hardware Port:\s*(.+)", block)
            dm = re.search(r"Device:\s*(\S+)", block)
            if pm and dm and dm.group(1) == out["iface"]:
                out["label"] = pm.group(1).strip()
                low = out["label"].lower()
                out["kind"] = "wifi" if ("wi-fi" in low or "airport" in low) else (
                    "ethernet" if ("ethernet" in low or "lan" in low or "thunderbolt" in low or "usb" in low) else "other")
        if out["kind"] == "unknown" and out["iface"].startswith("utun"):
            out["kind"] = "vpn"
    elif IS_WIN:
        target = host or "8.8.8.8"
        ps = ("$r=Find-NetRoute -RemoteIPAddress '%s' -ErrorAction SilentlyContinue | Where-Object InterfaceAlias | "
              "Select-Object -First 1; if($r){$a=Get-NetAdapter -InterfaceIndex $r.InterfaceIndex; "
              "ConvertTo-Json @{alias=$a.Name; media=[string]$a.PhysicalMediaType; desc=$a.InterfaceDescription}}" % target)
        rc, text = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], 12)
        try:
            j = json.loads(text[text.index("{"):])
            out["iface"], out["label"] = j.get("alias"), j.get("desc")
            media = (j.get("media") or "").lower() + " " + (j.get("desc") or "").lower()
            out["kind"] = "wifi" if ("802.11" in media or "wireless" in media or "wi-fi" in media) else (
                "ethernet" if ("802.3" in media or "ethernet" in media) else "other")
        except (ValueError, AttributeError):
            pass
    else:
        rc, text = _run(["ip", "route", "get", host or "8.8.8.8"], 5)
        m = re.search(r"dev\s+(\S+)", text)
        if m:
            out["iface"] = m.group(1)
            out["kind"] = "wifi" if Path(f"/sys/class/net/{m.group(1)}/wireless").exists() else "ethernet"
    return out


def _ping(host: str, count: int = 10) -> dict:
    if IS_WIN:
        cmd = ["ping", "-n", str(count), "-w", "1000", host]
    else:
        cmd = ["ping", "-c", str(count), "-i", "0.2", "-W", "1000" if IS_MAC else "1", host]
    rc, text = _run(cmd, count * 1.5 + 5)
    times = [float(t) for t in re.findall(r"(?:time|время)[=<]\s*([\d.]+)", text, re.I)]
    return _stats(times, count, "icmp")


def _ddp_rtt(host: str, count: int = 5) -> dict:
    times = []
    for _ in range(count):
        t = time.perf_counter()
        try:
            if ddp.status(host, 1.0):
                times.append((time.perf_counter() - t) * 1000)
        except OSError:  # "Host is down" / no route: the PS5 is offline
            break
    return _stats(times, count, "ddp")


def _stats(times: list[float], sent: int, method: str) -> dict:
    if not times:
        return {"method": method, "sent": sent, "received": 0, "loss": 100.0,
                "avg_ms": None, "min_ms": None, "max_ms": None, "jitter_ms": None}
    jitter = (sum(abs(a - b) for a, b in zip(times, times[1:])) / (len(times) - 1)) if len(times) > 1 else 0.0
    return {"method": method, "sent": sent, "received": len(times),
            "loss": round(100 * (1 - len(times) / sent), 1), "avg_ms": round(sum(times) / len(times), 1),
            "min_ms": round(min(times), 1), "max_ms": round(max(times), 1), "jitter_ms": round(jitter, 1)}


def network_report(host: str | None) -> dict:
    if MOCK:
        return {"host": host or MOCK_CONSOLE["ip"], "iface": "en0", "kind": "wifi", "label": "Wi-Fi",
                "ping": _stats([4.1, 6.3, 3.9, 12.8, 4.4, 5.0, 3.7, 9.9, 4.2, 4.0], 10, "icmp"),
                "verdict": "warn"}
    rep = {"host": host, **_iface_for(host), "ping": None}
    if host:
        ping = _ping(host)
        if not ping["received"]:
            ping = _ddp_rtt(host)  # some routers drop ICMP; DDP still answers when the PS5 is up
        rep["ping"] = ping
    p = rep["ping"] or {}
    bad = rep["kind"] == "wifi" or (p.get("avg_ms") or 0) > 15 or (p.get("jitter_ms") or 0) > 5 or (p.get("loss") or 0) > 0
    rep["verdict"] = "unknown" if not p.get("received") and host else ("warn" if bad else "good")
    return rep


# ---------------------------------------------------------------- brain (claude CLI)
def _claude_candidates() -> list[str]:
    home = Path.home()
    c: list[str] = []
    found = shutil.which("claude")
    if found:
        c.append(found)
    if IS_WIN:
        appdata, local = os.environ.get("APPDATA", ""), os.environ.get("LOCALAPPDATA", "")
        c += [str(home / ".local" / "bin" / "claude.exe"), os.path.join(appdata, "npm", "claude.cmd"),
              os.path.join(local, "Programs", "claude", "claude.exe"), os.path.join(local, "AnthropicClaude", "claude.exe")]
    else:
        c += [str(home / ".local/bin/claude"), str(home / ".claude/local/claude"), "/opt/homebrew/bin/claude",
              "/usr/local/bin/claude", str(home / ".npm-global/bin/claude"), str(home / ".bun/bin/claude")]
        c += sorted(glob.glob(str(home / ".nvm/versions/node/*/bin/claude")), reverse=True)
    seen, out = set(), []
    for p in c:
        if p and p not in seen and os.path.isfile(p):
            seen.add(p)
            out.append(p)
    return out


def install_commands() -> dict:
    if IS_WIN:
        return {"native": "irm https://claude.ai/install.ps1 | iex", "npm": "npm install -g @anthropic-ai/claude-code",
                "shell": "PowerShell"}
    return {"native": "curl -fsSL https://claude.ai/install.sh | bash", "npm": "npm install -g @anthropic-ai/claude-code",
            "shell": "Terminal"}


def brain_report() -> dict:
    cmds = install_commands()
    if MOCK:
        return {"installed": True, "path": "/Users/you/.local/bin/claude", "version": "2.1.0 (Claude Code)",
                "logged_in": True, "auth": {"method": "claude.ai", "plan": "max", "email": "you@example.com"},
                "commands": cmds, "on_path": True}
    paths = _claude_candidates()
    rep: dict = {"installed": bool(paths), "path": paths[0] if paths else None, "version": None,
                 "logged_in": None, "auth": None, "commands": cmds, "on_path": bool(shutil.which("claude")),
                 "npm": bool(shutil.which("npm"))}
    if not paths:
        return rep
    exe = paths[0]
    rc, text = _run([exe, "--version"], 15)
    if rc == 0:
        rep["version"] = text.strip().splitlines()[0] if text.strip() else None
    rc, text = _run([exe, "auth", "status"], 15)
    try:
        j = json.loads(text[text.index("{"):text.rindex("}") + 1])
        rep["logged_in"] = bool(j.get("loggedIn"))
        rep["auth"] = {"method": j.get("authMethod"), "plan": j.get("subscriptionType"), "email": j.get("email")}
    except ValueError:
        rep["logged_in"] = None  # older CLI without `auth status`; the deep check answers it
    return rep


def brain_deep_check() -> dict:
    paths = _claude_candidates()
    if MOCK:
        return {"ok": True, "ms": 2300, "reply": "ok"}
    if not paths:
        return {"ok": False, "error": "claude CLI not found"}
    t = time.perf_counter()
    rc, text = _run([paths[0], "-p", "Reply with just: ok", "--output-format", "json"], 60)
    ms = int((time.perf_counter() - t) * 1000)
    try:
        j = json.loads(text[text.index("{"):text.rindex("}") + 1])
        if j.get("is_error"):
            return {"ok": False, "ms": ms, "error": str(j.get("result") or "error")[:300]}
        return {"ok": True, "ms": ms, "reply": str(j.get("result", ""))[:80]}
    except ValueError:
        low = text.lower()
        hint = "not signed in" if ("login" in low or "log in" in low or "auth" in low) else text.strip()[-300:]
        return {"ok": False, "ms": ms, "error": hint or f"exit code {rc}"}


class Installer:
    def __init__(self):
        self.running = False
        self.rc: int | None = None
        self.log: deque[str] = deque(maxlen=200)
        self.method = None

    def start(self, method: str) -> dict:
        if self.running:
            return {"ok": True, "running": True}
        cmds = install_commands()
        if method == "npm" and not shutil.which("npm"):
            return {"ok": False, "error": "npm not found. Use the native installer."}
        if method == "npm":
            cmd = ["npm", "install", "-g", "@anthropic-ai/claude-code"]
            if IS_WIN:
                cmd = ["cmd", "/c"] + cmd
        elif IS_WIN:
            cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmds["native"]]
        else:
            cmd = ["bash", "-c", cmds["native"]]
        self.running, self.rc, self.method = True, None, method
        self.log.clear()
        self.log.append("$ " + (cmds["npm"] if method == "npm" else cmds["native"]))
        threading.Thread(target=self._run, args=(cmd,), daemon=True).start()
        return {"ok": True, "running": True}

    def _run(self, cmd: list[str]) -> None:
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                 encoding="utf-8", errors="replace")
            for line in p.stdout:
                self.log.append(line.rstrip())
            self.rc = p.wait()
        except OSError as err:
            self.log.append(str(err))
            self.rc = -1
        self.running = False

    def status(self) -> dict:
        return {"running": self.running, "rc": self.rc, "method": self.method, "log": list(self.log)[-60:]}


installer = Installer()


def open_login_terminal() -> dict:
    paths = _claude_candidates()
    exe = paths[0] if paths else "claude"
    try:
        if IS_MAC:
            script = f'tell application "Terminal" to do script "{exe}"\ntell application "Terminal" to activate'
            subprocess.Popen(["osascript", "-e", script])
        elif IS_WIN:
            subprocess.Popen(["cmd", "/c", "start", "Claude sign-in", "cmd", "/k", exe])
        else:
            term = shutil.which("x-terminal-emulator") or shutil.which("gnome-terminal")
            if not term:
                return {"ok": False, "error": "No terminal found", "command": exe}
            subprocess.Popen([term, "--", exe])
    except OSError as err:
        return {"ok": False, "error": str(err), "command": exe}
    return {"ok": True, "command": exe}


# ---------------------------------------------------------------- bot runner
class AgentRunner:
    def __init__(self):
        self.proc: subprocess.Popen | None = None
        self.mode = None
        self.minutes = None
        self.started = None
        self.tail: deque[str] = deque(maxlen=300)
        self._fh = None

    def running(self) -> bool:
        return bool(self.proc and self.proc.poll() is None)

    def start(self, mode: str, minutes: float) -> dict:
        if self.running():
            return {"ok": False, "error": "already running", **self.status()}
        goal = MODES.get(mode)
        if not goal:
            return {"ok": False, "error": f"unknown mode {mode!r}; use {sorted(MODES)}"}
        minutes = max(1.0, min(180.0, float(minutes)))
        AGENT_LOG.parent.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, "-u", str(ROOT / "agent.py"), goal, f"{minutes:g}"]
        kw: dict = {}
        if IS_WIN:
            kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        else:
            kw["start_new_session"] = True
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
        self.tail.clear()
        self._fh = open(AGENT_LOG, "a", encoding="utf-8")
        self._fh.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} {' '.join(cmd[2:])} =====\n")
        try:
            self.proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         text=True, encoding="utf-8", errors="replace", env=env, **kw)
        except OSError as err:
            return {"ok": False, "error": str(err)}
        self.mode, self.minutes, self.started = mode, minutes, time.time()
        threading.Thread(target=self._pump, args=(self.proc,), daemon=True).start()
        return {"ok": True, **self.status()}

    def _pump(self, proc: subprocess.Popen) -> None:
        for line in proc.stdout:
            line = line.rstrip()
            self.tail.append(line)
            if self._fh:
                self._fh.write(line + "\n")
                self._fh.flush()
        proc.wait()
        self.tail.append(f"[exit {proc.returncode}]")

    def stop(self) -> dict:
        p = self.proc
        if p and p.poll() is None:
            try:
                if IS_WIN:
                    p.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    os.killpg(p.pid, signal.SIGTERM)
                p.wait(5)
            except (OSError, subprocess.TimeoutExpired, ValueError):
                p.kill()
        return {"ok": True, **self.status()}

    def status(self) -> dict:
        p = self.proc
        return {"running": self.running(), "mode": self.mode, "minutes": self.minutes,
                "started": self.started, "elapsed_s": int(time.time() - self.started) if self.started and self.running() else None,
                "exit_code": p.poll() if p else None, "log": list(self.tail)[-80:]}


agent = AgentRunner()


# ---------------------------------------------------------------- HTTP
async def _body(req: web.Request) -> dict:
    try:
        b = await req.json()
        return b if isinstance(b, dict) else {}
    except (json.JSONDecodeError, ValueError):
        return {}


def _snapshot() -> dict:
    r = _remote()
    if MOCK:
        return {"reachable": True, "host": MOCK_CONSOLE["ip"], "name": MOCK_CONSOLE["host-name"],
                "firmware": MOCK_CONSOLE["system-version"], "power": "on", "signed_in": None,
                "linked": False, "connected": False, "message": "mock"}
    if r is None:
        return {}
    try:
        return r.snapshot()
    except Exception as err:  # noqa: BLE001
        return {"error": str(err)}


async def page(_req):
    return web.FileResponse(WEB / "index.html", headers={"Cache-Control": "no-cache"})


async def get_state(_req):
    prog = load_progress()
    return web.json_response({
        "progress": prog, "steps": STEPS, "done": done(), "linked_before": _linked_already(),
        "remote": _snapshot(), "env_host": os.environ.get("PS5_HOST", ""), "mock": MOCK,
        "platform": {"os": "windows" if IS_WIN else ("mac" if IS_MAC else "linux"), "release": platform.release()},
        "agent": {"running": agent.running(), "mode": agent.mode},
    })


async def post_progress(req):
    b = await _body(req)
    prog = load_progress()
    if b.get("step") in STEPS:
        prog["step"] = b["step"]
    if isinstance(b.get("checks"), dict):
        prog.setdefault("checks", {}).update({str(k)[:64]: bool(v) for k, v in b["checks"].items()})
    if "complete" in b:
        prog["complete"] = bool(b["complete"])
        if prog["complete"]:
            prog["completed_at"] = time.time()
    for k in ("mode", "minutes", "lang"):
        if k in b:
            prog[k] = b[k]
    prog["updated_at"] = time.time()
    save_progress(prog)
    return web.json_response({"ok": True, "progress": prog, "done": done()})


async def post_reset(_req):
    save_progress({"step": "find", "checks": {}, "complete": False})
    return web.json_response({"ok": True})


async def get_discover(_req):
    if MOCK:
        return web.json_response({"ok": True, "consoles": [_console_view(MOCK_CONSOLE)]})
    try:
        found = await asyncio.to_thread(ddp.search, None, 2.5)
    except OSError as err:
        return web.json_response({"ok": False, "consoles": [], "error": str(err)})
    return web.json_response({"ok": True, "consoles": [_console_view(c) for c in found]})


async def post_host(req):
    host = str((await _body(req)).get("host", "")).strip()
    if not host or not _valid_host(host):
        return web.json_response({"ok": False, "error": "invalid host"}, status=400)
    info = MOCK_CONSOLE if MOCK else None
    if not MOCK:
        try:
            info = await asyncio.to_thread(ddp.status, host, 2.0)
        except OSError:
            info = None
    if MOCK:
        os.environ["PS5_HOST"] = host  # preview only: never touch the real .env.local
    else:
        write_env("PS5_HOST", host)
    r = _remote()
    if r is not None and not MOCK:
        r.host = host
        r.status = info or {}
    return web.json_response({"ok": True, "saved": True, "reachable": bool(info),
                              "console": _console_view({**(info or {}), "ip": host}) if info else None})


async def get_network(req):
    host = req.query.get("host") or os.environ.get("PS5_HOST") or (_snapshot().get("host") or None)
    if host and not _valid_host(host):
        return web.json_response({"ok": False, "error": "invalid host"}, status=400)
    return web.json_response({"ok": True, **(await asyncio.to_thread(network_report, host))})


async def get_brain(_req):
    return web.json_response({"ok": True, **(await asyncio.to_thread(brain_report))})


async def post_brain_check(_req):
    return web.json_response(await asyncio.to_thread(brain_deep_check))


async def post_brain_install(req):
    method = str((await _body(req)).get("method", "native"))
    if MOCK:
        return web.json_response({"ok": False, "error": "mock mode: install disabled"})
    return web.json_response(installer.start("npm" if method == "npm" else "native"))


async def get_brain_install(_req):
    return web.json_response(installer.status())


async def post_brain_login(_req):
    return web.json_response(await asyncio.to_thread(open_login_terminal))


async def get_agent(_req):
    return web.json_response(agent.status())


async def post_agent_start(req):
    b = await _body(req)
    try:
        minutes = float(b.get("minutes", 10))
    except (TypeError, ValueError):
        minutes = 10.0
    res = agent.start(str(b.get("mode", "car")), minutes)
    if res.get("ok"):
        prog = load_progress()
        prog.update({"mode": b.get("mode"), "minutes": minutes})
        save_progress(prog)
    return web.json_response(res)


async def post_agent_stop(req):
    res = agent.stop()
    pilot = req.app.get("pilot")
    if pilot is not None:
        try:
            pilot.stop()  # release the controller the bot was driving
        except Exception:  # noqa: BLE001
            pass
    return web.json_response(res)


async def _cleanup(_app):
    agent.stop()


def register(app: web.Application, remote_getter=None) -> None:
    global _remote_getter
    if remote_getter is not None:
        _remote_getter = remote_getter
    app.add_routes([
        web.get("/setup", page),
        web.get("/setup/", page),
        web.get("/api/setup/state", get_state),
        web.post("/api/setup/progress", post_progress),
        web.post("/api/setup/reset", post_reset),
        web.get("/api/setup/discover", get_discover),
        web.post("/api/setup/host", post_host),
        web.get("/api/setup/network", get_network),
        web.get("/api/setup/brain", get_brain),
        web.post("/api/setup/brain/check", post_brain_check),
        web.post("/api/setup/brain/install", post_brain_install),
        web.get("/api/setup/brain/install", get_brain_install),
        web.post("/api/setup/brain/login", post_brain_login),
        web.get("/api/setup/agent", get_agent),
        web.post("/api/setup/agent/start", post_agent_start),
        web.post("/api/setup/agent/stop", post_agent_stop),
    ])
    app.router.add_static("/setup/assets", WEB, show_index=False)
    app.on_cleanup.append(_cleanup)
