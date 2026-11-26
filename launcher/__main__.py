"""Apofiz Play GTA6 desktop launcher.

    python -m launcher              tray/menu-bar app (default)
    python -m launcher --headless   no tray: start server, open browser, wait for Ctrl+C
    python -m launcher --no-browser don't open the browser on start

Env: APOFIZ_PORT (server port, default 8765), APOFIZ_NO_BROWSER=1,
APOFIZ_NO_UPDATE_CHECK=1, APOFIZ_BOT_GOAL / APOFIZ_BOT_MINUTES (fallback bot),
APOFIZ_LOG_DIR (override log folder).
"""
from __future__ import annotations

import argparse
import atexit
import logging
import os
import signal
import sys
import threading
import time

from . import ui
from .core import DISPLAY_NAME, Controller, SingleInstance, setup_logging

log = logging.getLogger("launcher")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="launcher", description=DISPLAY_NAME)
    ap.add_argument("--headless", action="store_true", help="no tray icon")
    ap.add_argument("--no-browser", action="store_true", help="do not open the browser")
    ap.add_argument("--port", type=int, help="server port (same as APOFIZ_PORT)")
    # macOS passes -psn_0_xxx when launched from Finder on old systems: ignore unknowns.
    args, _ = ap.parse_known_args(argv)
    if args.port:
        os.environ["APOFIZ_PORT"] = str(args.port)
    no_browser = args.no_browser or os.environ.get("APOFIZ_NO_BROWSER") == "1"

    log_path = setup_logging()
    lock = SingleInstance()
    if not lock.acquire():
        info = lock.read_info()
        port = info.get("port")
        log.info("already running (port %s); opening browser and exiting", port)
        if port and not no_browser:
            ui.open_url(f"http://127.0.0.1:{port}/")
        return 0

    ctl = Controller()
    log.info("%s %s starting (python %s, log %s)", DISPLAY_NAME, ctl.version, sys.version.split()[0], log_path)

    done = threading.Event()        # headless: "please exit"
    cleaned = threading.Lock()
    cleaned_flag = []

    def cleanup(*_):
        with cleaned:
            if cleaned_flag:
                return
            cleaned_flag.append(True)
        done.set()
        ctl.shutdown()
        lock.release()
    atexit.register(cleanup)

    def boot(tray=None):
        ok = ctl.start_server()
        lock.write_info(port=ctl.port, pid=os.getpid(), attached=ctl.attached)
        if tray:
            tray.status = f"running on :{ctl.port}" if ok else "server failed — see Logs"
            tray.refresh()
        if not ok:
            ui.alert("PS5 Remote server did not start.\nOpen the Logs folder from the menu for details.")
            return
        ctl.watch_bot()
        if not no_browser:
            ui.open_url(ctl.start_url())
        if os.environ.get("APOFIZ_NO_UPDATE_CHECK") != "1":
            t = threading.Timer(15, lambda: _silent_update_check(ctl, tray))
            t.daemon = True
            t.start()

    if args.headless:
        signal.signal(signal.SIGINT, lambda *_: done.set())
        signal.signal(signal.SIGTERM, lambda *_: done.set())
        boot()
        while not done.is_set():
            time.sleep(0.5)
        cleanup()
        return 0

    from .tray import Tray  # imported late: headless mode must not need pystray
    tray = Tray(ctl)

    def on_signal(*_):
        cleanup()
        tray.icon.stop()
    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    tray.run(on_ready=lambda t: threading.Thread(target=boot, args=(t,), daemon=True).start())
    cleanup()
    log.info("bye")
    return 0


def _silent_update_check(ctl: Controller, tray) -> None:
    info, _err = ctl.check_update()
    if info:
        ver = info.get("version", "") if isinstance(info, dict) else ""
        ui.notify(f"Update {ver} available — use “Check for updates…” in the menu.",
                  icon=tray.icon if tray else None)


if __name__ == "__main__":
    sys.exit(main())
