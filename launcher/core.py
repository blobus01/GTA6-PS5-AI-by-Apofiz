"""Launcher core: paths, logging, single-instance lock, child processes.

No GUI code here so the Windows installer (or tests) can reuse it headless.
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

IS_MAC = sys.platform == "darwin"
IS_WIN = os.name == "nt"

APP_NAME = "ApofizPlay"
DISPLAY_NAME = "Apofiz Play GTA6"
DEFAULT_PORT = 8765

# Project root = the folder that contains server.py (parent of launcher/).
ROOT = Path(os.environ.get("APOFIZ_APP_ROOT") or Path(__file__).resolve().parent.parent)
ASSETS = Path(__file__).resolve().parent / "assets"
BUNDLED = os.environ.get("APOFIZ_BUNDLED") == "1"

log = logging.getLogger("launcher")


# ---------------------------------------------------------------- paths
def version() -> str:
    try:
        return (ROOT / "VERSION").read_text(encoding="utf-8").strip() or "0.0.0"
    except OSError:
        return "0.0.0"


def logs_dir() -> Path:
    if os.environ.get("APOFIZ_LOG_DIR"):
        d = Path(os.environ["APOFIZ_LOG_DIR"])
    elif IS_MAC:
        d = Path.home() / "Library" / "Logs" / APP_NAME
    elif IS_WIN:
        d = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / APP_NAME / "logs"
    else:
        d = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / APP_NAME / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def data_dir() -> Path:
    """Writable working dir for children (the .app bundle itself is read-only)."""
    if IS_MAC:
        d = Path.home() / "Library" / "Application Support" / APP_NAME
    elif IS_WIN:
        d = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / APP_NAME
    else:
        d = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def remote_home() -> Path:
    """Same rule as store.py: PS5_REMOTE_HOME or ~/.ps5-remote."""
    return Path(os.environ.get("PS5_REMOTE_HOME", Path.home() / ".ps5-remote"))


def setup_done_file() -> bool:
    """Offline fallback; the server's /api/state `setup_done` is authoritative."""
    try:
        d = json.loads((remote_home() / "setup.json").read_text(encoding="utf-8"))
        return bool(d.get("done") or d.get("complete"))
    except (OSError, ValueError, AttributeError):
        return False


def child_python() -> str:
    """Interpreter for server.py/agent.py. In the macOS .app the launcher runs inside
    an embedding stub (sys.executable = the stub), so the stub passes the real one."""
    return os.environ.get("APOFIZ_PYTHON") or sys.executable


def setup_logging() -> Path:
    path = logs_dir() / "launcher.log"
    h = logging.handlers.RotatingFileHandler(path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(h)
    if sys.stderr and sys.stderr.isatty():
        root.addHandler(logging.StreamHandler())
    return path


def rotate(path: Path, keep: int = 3, max_bytes: int = 5_000_000) -> None:
    try:
        if not path.exists() or path.stat().st_size < max_bytes:
            return
        for i in range(keep - 1, 0, -1):
            src = path.with_suffix(path.suffix + f".{i}")
            if src.exists():
                src.replace(path.with_suffix(path.suffix + f".{i + 1}"))
        path.replace(path.with_suffix(path.suffix + ".1"))
    except OSError:
        pass


def child_env(port: int) -> dict:
    env = dict(os.environ)
    port_s = str(port)
    # server.py reads REMOTE_PORT; the others are for agents/tools that adopt them.
    env.update(REMOTE_PORT=port_s, PS5_REMOTE_PORT=port_s, APOFIZ_PORT=port_s,
               PS5_REMOTE_URL=f"http://127.0.0.1:{port_s}",
               PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
    if BUNDLED:
        env["PYTHONNOUSERSITE"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
    # Finder/Explorer start apps with a bare PATH; brain.py needs the `claude` CLI.
    extra = []
    home = Path.home()
    if IS_MAC or not IS_WIN:
        extra = [home / ".local/bin", home / ".claude/local", home / ".npm-global/bin",
                 Path("/opt/homebrew/bin"), Path("/usr/local/bin")]
    else:
        appdata = Path(os.environ.get("APPDATA", home / "AppData/Roaming"))
        extra = [appdata / "npm", home / ".local/bin", home / ".claude/local"]
    parts = env.get("PATH", "").split(os.pathsep)
    for p in extra:
        if p.is_dir() and str(p) not in parts:
            parts.append(str(p))
    env["PATH"] = os.pathsep.join(x for x in parts if x)
    return env


# ---------------------------------------------------------------- single instance
class SingleInstance:
    """OS file lock in the data dir. The lock file also stores the port."""

    def __init__(self, name: str = "launcher.lock"):
        self.path = data_dir() / name
        self._fh = None

    def acquire(self) -> bool:
        self._fh = open(self.path, "a+")
        try:
            if IS_WIN:
                import msvcrt
                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._fh.close()
            self._fh = None
            return False
        return True

    def write_info(self, **info) -> None:
        # Separate sidecar file: on Windows the locked byte can't be rewritten.
        self.path.with_suffix(".json").write_text(json.dumps(info), encoding="utf-8")

    def read_info(self) -> dict:
        try:
            return json.loads(self.path.with_suffix(".json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def release(self) -> None:
        if self._fh:
            try:
                self._fh.close()
            finally:
                self._fh = None
            try:
                self.path.with_suffix(".json").unlink()
            except OSError:
                pass


# ---------------------------------------------------------------- http helpers
def http(method: str, url: str, body: dict | None = None, timeout: float = 3.0):
    """Return (status, parsed_json_or_text). status 0 = connection failed."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            status = r.status
    except urllib.error.HTTPError as e:
        return e.code, None
    except (urllib.error.URLError, OSError, TimeoutError):
        return 0, None
    try:
        return status, json.loads(raw or b"null")
    except ValueError:
        return status, raw.decode("utf-8", "replace")


def port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def free_port(start: int, tries: int = 20) -> int:
    for p in range(start, start + tries):
        if not port_busy(p):
            return p
    raise RuntimeError(f"no free port in {start}..{start + tries - 1}")


# ---------------------------------------------------------------- child processes
class Child:
    """A python child (server.py / agent.py) with its own process group and log."""

    def __init__(self, name: str, args: list[str], port: int, log_name: str):
        self.name, self.args, self.port = name, args, port
        self.log_path = logs_dir() / log_name
        self.proc: subprocess.Popen | None = None
        self._log_fh = None

    def start(self) -> None:
        if self.running():
            return
        rotate(self.log_path)
        self._log_fh = open(self.log_path, "ab", buffering=0)
        self._log_fh.write(f"\n=== {time.strftime('%F %T')} start {self.name}: {self.args}\n".encode())
        kw: dict = {}
        if IS_WIN:
            kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        else:
            kw["start_new_session"] = True
        cwd = data_dir() if BUNDLED else ROOT
        self.proc = subprocess.Popen([child_python(), "-u", *self.args], cwd=str(cwd), env=child_env(self.port),
                                     stdin=subprocess.DEVNULL, stdout=self._log_fh, stderr=subprocess.STDOUT, **kw)
        log.info("%s started pid=%s", self.name, self.proc.pid)

    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def stop(self, timeout: float = 6.0) -> None:
        p = self.proc
        if p is None:
            return
        if p.poll() is None:
            log.info("stopping %s pid=%s", self.name, p.pid)
            try:
                if IS_WIN:
                    p.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    os.killpg(p.pid, signal.SIGTERM)
            except (OSError, ValueError):
                p.terminate()
            try:
                p.wait(timeout)
            except subprocess.TimeoutExpired:
                log.warning("%s did not exit, killing", self.name)
                if IS_WIN:
                    subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
                else:
                    try:
                        os.killpg(p.pid, signal.SIGKILL)
                    except OSError:
                        p.kill()
                p.wait(3)
        log.info("%s exited code=%s", self.name, p.returncode)
        self.proc = None
        if self._log_fh:
            self._log_fh.close()
            self._log_fh = None


class Controller:
    """Everything the tray menu does, UI-agnostic."""

    # Bot endpoints of setup_api.py. If they answer 404 (older server), the
    # launcher spawns agent.py itself.
    BOT_START = "/api/setup/agent/start"   # POST {mode, minutes}
    BOT_STOP = "/api/setup/agent/stop"
    BOT_STATUS = "/api/setup/agent"        # GET -> {running, ...}

    def __init__(self):
        self.version = version()
        want = os.environ.get("APOFIZ_PORT") or os.environ.get("PS5_REMOTE_PORT")
        self.port = int(want) if want else DEFAULT_PORT
        self.port_explicit = bool(want)
        self.attached = False          # True = reusing a server we did not start
        self.server: Child | None = None
        self.bot: Child | None = None
        self.bot_via_api = False
        self.bot_api_running = False
        self.on_change = lambda: None  # tray sets this to refresh the menu
        self._stop = threading.Event()

    # ------------------------------------------------------------ urls
    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def url(self, path: str = "/") -> str:
        return self.base + path

    def start_url(self) -> str:
        status, data = http("GET", self.url("/api/state"), timeout=3)
        done = data.get("setup_done") if status == 200 and isinstance(data, dict) else None
        if done is None:
            done = setup_done_file()
        return self.url("/" if done else "/setup")

    # ------------------------------------------------------------ server
    def healthy(self) -> bool:
        status, data = http("GET", self.url("/api/state"), timeout=2)
        return status == 200 and isinstance(data, dict)

    def start_server(self, wait: float = 180.0) -> bool:  # first launch: Gatekeeper scans the big bundle
        if port_busy(self.port):
            if self.healthy():
                log.info("port %s already serves PS5 Remote: attaching, not spawning", self.port)
                self.attached = True
                return True
            if self.port_explicit:
                log.error("port %s busy by something else", self.port)
                return False
            self.port = free_port(self.port + 1)
            log.warning("port busy, using %s", self.port)
        self.server = Child("server", [str(ROOT / "server.py")], self.port, "server.log")
        self.server.start()
        threading.Thread(target=self._watch_server, daemon=True).start()
        return self.wait_healthy(wait)

    def wait_healthy(self, wait: float) -> bool:
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            if self.server and not self.server.running():
                log.error("server exited early (code=%s), see %s", self.server.proc and self.server.proc.returncode,
                          self.server.log_path)
                return False
            if self.healthy():
                log.info("server healthy on %s", self.base)
                return True
            time.sleep(0.4)
        log.error("server not healthy after %ss", wait)
        return False

    def _watch_server(self) -> None:
        """Restart the server if it crashes (max 3 times in 5 minutes)."""
        crashes: list[float] = []
        while not self._stop.wait(2.0):
            s = self.server
            if s is None or s.running() or self._stop.is_set():
                continue
            now = time.monotonic()
            crashes = [t for t in crashes if now - t < 300] + [now]
            if len(crashes) > 3:
                log.error("server keeps crashing, giving up; see %s", s.log_path)
                self.on_change()
                return
            log.warning("server died (code=%s), restarting", s.proc and s.proc.returncode)
            s.stop()
            s.start()
            self.on_change()

    # ------------------------------------------------------------ bot
    bot_cached = False  # last known state, read by the menu without blocking

    def watch_bot(self, every: float = 3.0) -> None:
        """Background poll so the tray label follows bots started from the web UI too."""
        def loop():
            while not self._stop.wait(every):
                try:
                    on = self.bot_running(probe_api=True)
                except Exception:  # noqa: BLE001
                    continue
                if on != self.bot_cached:
                    self.bot_cached = on
                    self.on_change()
        threading.Thread(target=loop, daemon=True).start()

    def bot_running(self, probe_api: bool = False) -> bool:
        if probe_api and not self.bot_via_api and not (self.bot and self.bot.running()):
            status, data = http("GET", self.url(self.BOT_STATUS), timeout=1.5)
            if status == 200 and isinstance(data, dict) and data.get("running"):
                self.bot_via_api, self.bot_api_running = True, True
                return True
        if self.bot_via_api:
            status, data = http("GET", self.url(self.BOT_STATUS), timeout=1.5)
            if status == 200 and isinstance(data, dict):
                self.bot_api_running = bool(data.get("running"))
            return self.bot_api_running
        return bool(self.bot and self.bot.running())

    def start_bot(self) -> str:
        """Return a human status string ("started", "spawned" or "error: ...")."""
        goal = os.environ.get("APOFIZ_BOT_GOAL", "car")
        minutes = os.environ.get("APOFIZ_BOT_MINUTES", "10")
        status, data = http("POST", self.url(self.BOT_START), body={"mode": goal, "minutes": float(minutes)},
                            timeout=15)
        if status == 200 and isinstance(data, dict):
            log.info("bot via %s: ok=%s error=%s", self.BOT_START, data.get("ok"), data.get("error"))
            self.bot_via_api = True
            self.bot_api_running = bool(data.get("running", data.get("ok")))
            return "started" if data.get("ok") else f"error: {data.get('error', 'unknown')}"
        if status not in (404, 405):
            return f"error: server answered {status or 'nothing'}"
        self.bot_via_api = False
        self.bot = Child("bot", [str(ROOT / "agent.py"), goal, minutes], self.port, "bot.log")
        self.bot.start()
        return "spawned"

    def stop_bot(self) -> None:
        if self.bot_via_api:
            http("POST", self.url(self.BOT_STOP), body={}, timeout=10)
            self.bot_api_running = False
        if self.bot:
            self.bot.stop()
            self.bot = None
        # Also stop the autopilot loop the bot drives (safe no-op if idle).
        http("POST", self.url("/api/pilot/stop"), body={}, timeout=5)

    # ------------------------------------------------------------ updates
    def check_update(self):
        """Return (info|None, error|None). apofiz_update is optional."""
        try:
            if str(ROOT) not in sys.path:
                sys.path.insert(0, str(ROOT))
            import apofiz_update  # type: ignore
        except ImportError:
            return None, "updater not available in this build"
        try:
            return apofiz_update.check_for_update(self.version), None
        except Exception as e:  # noqa: BLE001 - never crash the tray on updater bugs
            log.exception("update check failed")
            return None, str(e)

    def apply_update(self, info, progress_cb=None):
        """Return (result_dict|None, error|None). result: {path, version, action, quit_required}."""
        try:
            import apofiz_update  # type: ignore
            kw = {"progress_cb": progress_cb} if progress_cb else {}
            return apofiz_update.apply_update(info, **kw) or {}, None
        except Exception as e:  # noqa: BLE001 - includes apofiz_update.UpdateError
            log.exception("apply_update failed")
            return None, str(e)

    # ------------------------------------------------------------ shutdown
    def shutdown(self) -> None:
        self._stop.set()
        try:
            if self.bot or self.bot_via_api:
                self.stop_bot()
        finally:
            if self.server:
                self.server.stop()
                self.server = None
