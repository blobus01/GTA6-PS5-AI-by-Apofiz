"""Tiny native dialogs / notifications without a GUI toolkit."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import webbrowser
from pathlib import Path

from .core import DISPLAY_NAME, IS_MAC, IS_WIN

log = logging.getLogger("launcher.ui")


def _osa_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def notify(message: str, title: str = DISPLAY_NAME, icon=None) -> None:
    try:
        if IS_MAC:
            subprocess.Popen(["osascript", "-e", f"display notification {_osa_str(message)} with title {_osa_str(title)}"])
        elif icon is not None and getattr(icon, "HAS_NOTIFICATION", False):
            icon.notify(message, title)
    except Exception:  # noqa: BLE001
        log.exception("notify failed")


def alert(message: str, title: str = DISPLAY_NAME) -> None:
    confirm(message, title, ok="OK", cancel=None)


def confirm(message: str, title: str = DISPLAY_NAME, ok: str = "OK", cancel: str | None = "Cancel") -> bool:
    """Blocking yes/no dialog. Call from a worker thread, not the UI thread."""
    try:
        if IS_MAC:
            buttons = "{" + ", ".join(_osa_str(b) for b in ([cancel] if cancel else []) + [ok]) + "}"
            script = (f"display dialog {_osa_str(message)} with title {_osa_str(title)} buttons {buttons} "
                      f"default button {_osa_str(ok)}" + (f" cancel button {_osa_str(cancel)}" if cancel else ""))
            r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
            return r.returncode == 0 and ok in r.stdout
        if IS_WIN:
            import ctypes
            flags = (0x1 if cancel else 0x0) | 0x40 | 0x10000  # OKCANCEL|ICONINFO|SETFOREGROUND
            return ctypes.windll.user32.MessageBoxW(None, message, title, flags) == 1
    except Exception:  # noqa: BLE001
        log.exception("dialog failed")
    return False


def open_url(url: str) -> None:
    log.info("open %s", url)
    try:
        if IS_MAC:
            subprocess.Popen(["open", url])
        else:
            webbrowser.open(url)
    except Exception:  # noqa: BLE001
        log.exception("open url failed")


def open_folder(path: Path) -> None:
    try:
        if IS_MAC:
            subprocess.Popen(["open", str(path)])
        elif IS_WIN:
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:  # noqa: BLE001
        log.exception("open folder failed")
