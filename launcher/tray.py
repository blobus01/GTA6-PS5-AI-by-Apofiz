"""System tray (Windows) / menu bar item (macOS) on top of pystray.

pystray drives NSStatusItem on macOS and Shell_NotifyIcon on Windows, so one
code path covers both. On macOS we additionally switch the process to an
"accessory" app (no Dock icon) even when started outside the .app bundle.
"""
from __future__ import annotations

import logging
import signal
import threading

import pystray
from PIL import Image

from . import ui
from .core import ASSETS, DISPLAY_NAME, IS_MAC, Controller, logs_dir

log = logging.getLogger("launcher.tray")


def _icon_image() -> Image.Image:
    for name in ("tray@2x.png", "tray.png", "icon.png"):
        p = ASSETS / name
        if p.exists():
            return Image.open(p).convert("RGBA")
    return Image.new("RGBA", (64, 64), (59, 130, 246, 255))


def _mac_accessory() -> None:
    try:
        from AppKit import NSApplication  # type: ignore
        NSApplication.sharedApplication().setActivationPolicy_(1)  # Accessory: menu bar only
    except Exception:  # noqa: BLE001
        log.debug("AppKit not available")


def _mac_fix_icon_size(icon: "pystray.Icon") -> None:
    """pystray rasterises the icon at 1x (22px). Swap in the 128px PNG drawn at 18pt
    so the mark is crisp on Retina menu bars."""
    try:
        from AppKit import NSImage, NSSize  # type: ignore
        src = ASSETS / "tray@2x.png"
        img = NSImage.alloc().initWithContentsOfFile_(str(src)) if src.exists() else None
        if img is not None:
            img.setSize_(NSSize(18, 18))
            icon._status_item.button().setImage_(img)  # noqa: SLF001 - pystray private, guarded
    except Exception:  # noqa: BLE001
        log.debug("could not resize menubar icon", exc_info=True)


def on_main_thread(fn) -> None:
    """AppKit objects must be touched on the main thread (macOS)."""
    if IS_MAC:
        try:
            from PyObjCTools import AppHelper  # type: ignore
            AppHelper.callAfter(fn)
            return
        except Exception:  # noqa: BLE001
            pass
    fn()


class Tray:
    def __init__(self, ctl: Controller):
        self.ctl = ctl
        self.status = "Starting…"
        self.icon = pystray.Icon("ApofizPlay", _icon_image(), DISPLAY_NAME, menu=self._menu())
        ctl.on_change = self.refresh

    # ------------------------------------------------------------ menu
    def _menu(self) -> pystray.Menu:
        c = self.ctl
        item = pystray.MenuItem
        return pystray.Menu(
            item(lambda _: f"{DISPLAY_NAME} {c.version} — {self.status}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            item("Open Remote", self._bg(lambda: ui.open_url(c.url("/"))), default=True),
            item("Setup Wizard", self._bg(lambda: ui.open_url(c.url("/setup")))),
            item("OBS Overlay", self._bg(self._overlay)),
            pystray.Menu.SEPARATOR,
            item(lambda _: "Stop bot" if c.bot_cached else "Start bot", self._bg(self._toggle_bot)),
            pystray.Menu.SEPARATOR,
            item("Check for updates…", self._bg(self._updates)),
            item("Logs folder", self._bg(lambda: ui.open_folder(logs_dir()))),
            pystray.Menu.SEPARATOR,
            item("Quit", self._quit),
        )

    def _bot_on(self) -> bool:
        try:
            return self.ctl.bot_running()
        except Exception:  # noqa: BLE001
            return False

    def refresh(self) -> None:
        def do():
            try:
                self.icon.update_menu()
            except Exception:  # noqa: BLE001
                log.debug("update_menu failed", exc_info=True)
        on_main_thread(do)

    def _bg(self, fn):
        """Run menu actions off the UI thread; never let them raise into pystray."""
        def handler(_icon=None, _item=None):
            def run():
                try:
                    fn()
                except Exception:  # noqa: BLE001
                    log.exception("menu action failed")
                finally:
                    self.refresh()
            threading.Thread(target=run, daemon=True).start()
        return handler

    # ------------------------------------------------------------ actions
    def _overlay(self) -> None:
        url = self.ctl.url("/overlay")
        ui.open_url(url)
        ui.notify(f"Add a Browser Source in OBS: {url}", icon=self.icon)

    def _toggle_bot(self) -> None:
        if self._bot_on():
            self.ctl.stop_bot()
            self.ctl.bot_cached = False
            ui.notify("Bot stopped", icon=self.icon)
        else:
            how = self.ctl.start_bot()
            self.ctl.bot_cached = not how.startswith("error")
            if how.startswith("error"):
                ui.alert(f"Could not start the bot:\n{how[6:].strip()}\n\nOpen the Setup Wizard to finish setup.")
            else:
                ui.notify("Bot started. Watch it in Open Remote or the OBS overlay.", icon=self.icon)

    def _updates(self) -> None:
        info, err = self.ctl.check_update()
        if err:
            ui.alert(f"Could not check for updates:\n{err}")
            return
        if not info:
            ui.alert(f"You are up to date ({self.ctl.version}).")
            return
        ver = info.get("version", "?") if isinstance(info, dict) else "?"
        notes = (info.get("notes") or "")[:600] if isinstance(info, dict) else ""
        if ui.confirm(f"Version {ver} is available (you have {self.ctl.version}).\n\n{notes}\n\nInstall now?",
                      ok="Install", cancel="Later"):
            self.status = f"downloading {ver}…"
            self.refresh()
            res, err = self.ctl.apply_update(info)
            self.status = f"running on :{self.ctl.port}"
            if err:
                ui.alert(f"Update failed:\n{err}")
            elif res.get("action") == "opened_dmg":
                if ui.confirm(f"Version {ver} is downloaded and opened.\nQuit Apofiz Play, then drag the new app "
                              "into Applications to replace this one.", ok="Quit now", cancel="Later"):
                    on_main_thread(self._quit)
            elif res.get("quit_required"):
                if ui.confirm(f"Version {ver} is ready. Quit now to finish installing?", ok="Quit now", cancel="Later"):
                    on_main_thread(self._quit)
            else:
                ui.alert(f"Version {ver} installed. Restart Apofiz Play to use it.")

    def _quit(self, _icon=None, _item=None) -> None:
        log.info("quit requested")
        self.status = "Quitting…"
        try:
            self.ctl.shutdown()
        finally:
            self.icon.stop()

    # ------------------------------------------------------------ run
    def run(self, on_ready) -> None:
        def setup(icon):
            icon.visible = True
            if IS_MAC:
                _mac_fix_icon_size(icon)
            on_ready(self)
        if IS_MAC:
            # NSApp.run() never returns to the interpreter, so plain signal handlers
            # would not fire; route SIGTERM/SIGINT through a Mach port instead.
            try:
                from PyObjCTools import MachSignals  # type: ignore
                for sig in (signal.SIGTERM, signal.SIGINT):
                    MachSignals.signal(sig, lambda *_: self._quit())
            except Exception:  # noqa: BLE001
                log.debug("MachSignals unavailable", exc_info=True)
            _mac_accessory()
        self.icon.run(setup=setup)
