# Windows installer (Apofiz Play GTA6)

Builds `dist\ApofizPlay-GTA6-<VERSION>-win-x64-Setup.exe` (plus a version-less copy
`dist\ApofizPlay-GTA6-win-x64-Setup.exe` for the website). The installer ships its own
Python 3.12, so the user needs nothing preinstalled.

## Prerequisites (build machine)

| Tool | Why | Install |
|---|---|---|
| Windows 10/11 x64, PowerShell 5.1+ | runs `build.ps1` | built in |
| Inno Setup 6.3+ or 7 | compiles `installer.iss` | `winget install JRSoftware.InnoSetup` or https://jrsoftware.org/isdl.php |
| Internet | python-build-standalone, PyPI, PyTorch index, Mbed TLS | |
| Git | only if `native\ps5bridge.dll` and `vendor\chiaki-ng-src` are both missing | `winget install Git.Git` |
| Windows SDK (signtool) | only when signing | Visual Studio Installer → Windows SDK |

No system Python, MSVC or clang is needed: `build.ps1` downloads a pinned
python-build-standalone (CPython 3.12.16, SHA-256 checked) and, if the DLL is missing,
builds it with `zig cc` from the `ziglang` pip package (see `docs/07-building.md`).

## One-command build

From the repo root:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1
```

Options:

- `-Cuda [-CudaIndex cu128]` — torch with CUDA for NVIDIA GPUs. Output gets a `-cuda`
  suffix; about 2.5 GB bigger. Default is CPU-only torch.
- `-Version 0.2.0` — otherwise `$env:VERSION`, then the `VERSION` file, then `0.1.0`.
- `-Clean` — rebuild the bundled Python from scratch (otherwise reused while
  `requirements*.txt` are unchanged).
- `-SkipInstaller` — stop after staging (`packaging\windows\.work\stage`).
- `-Iscc C:\path\ISCC.exe` — non-standard Inno Setup location.

Downloads are cached in `$env:APOFIZ_BUILD_CACHE` (default `packaging\windows\.cache`).

### Code signing (optional)

Set `WIN_SIGN_PFX` (path to a `.pfx`; `WIN_SIGN_CERT` also works) and `WIN_SIGN_PASSWORD`,
optionally `WIN_SIGN_TIMESTAMP`. Then `ps5bridge.dll`, `python.exe`, `pythonw.exe`, the
uninstaller and Setup.exe are signed with signtool. Without them nothing is signed.

## What goes into the installer

`{app}` = `C:\Program Files\Apofiz Play GTA6`

- `runtime\` — CPython 3.12 + requirements.txt + launcher deps (pystray, Pillow) + torch/torchvision + ultralytics, precompiled to `.pyc`.
- project `.py` files, `web\`, `assets\`, `knowledge\`, `launcher\`, `docs\`, `native\ps5bridge.dll`, `yolo11n.pt`.
- excluded: `.venv`, `vendor`, `logs`, `tests`, `.env.local`, `*.log`, `.mcp.json`, `site`, `packaging`.
- `ApofizPlay.pyw` — shortcut entry point: sets `APOFIZ_BUNDLED=1` and runs `python -m launcher`.

## What the user sees

1. **SmartScreen** (unsigned builds): "Windows protected your PC" → *More info* → *Run anyway*.
   A signed build with an EV cert (or a reputation-built OV cert) avoids it.
2. UAC prompt (the installer needs admin for Program Files and the firewall).
3. Wizard (English/Russian): folder, tasks:
   - Desktop shortcut (on)
   - Start when I sign in to Windows (off) — starts in the tray without opening the browser
   - Allow PS5 Remote Play through Windows Firewall (on) — adds inbound rules named
     "Apofiz Play GTA6": UDP 9295-9304 and 987, TCP 9295, and UDP for the bundled
     python.exe/pythonw.exe, all limited to `remoteip=localsubnet`.
4. After install the app starts: tray icon + browser opens `http://127.0.0.1:8765/setup`.
5. Start Menu: *Apofiz Play GTA6*, *Logs*, *Uninstall*.

Uninstall (Settings → Apps, or Start Menu) stops the app, removes the firewall rules and
the install folder, then asks whether to delete user data
(`%USERPROFILE%\.ps5-remote` — console keys; `%LOCALAPPDATA%\ApofizPlay` — logs). Default
is **keep**; the PSN sign-in is then backed up to `%USERPROFILE%\.ps5-remote\env.local.backup`
and restored by the next install.

Silent:

```powershell
Setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART [/NOLAUNCH] [/TASKS="desktopicon,firewall"]
"C:\Program Files\Apofiz Play GTA6\unins000.exe" /VERYSILENT [/REMOVEUSERDATA]
```

The auto-updater runs `Setup.exe /SILENT /SUPPRESSMSGBOXES /NORESTART`; the installer
closes the running app first and starts it again afterwards (no `skipifsilent`).

## Troubleshooting

- **"No PS5 found"** — the PC and PS5 must be on the same network/subnet. Guest Wi-Fi,
  "AP isolation" and VPNs (TurboVPN etc.) block discovery. Set `PS5_HOST=<ip>` in
  `C:\Program Files\Apofiz Play GTA6\.env.local` to skip discovery.
- **Firewall** — if you skipped the firewall task, Windows may silently drop the PS5's
  UDP stream (black screen / connect timeout). Re-run the installer with the task
  ticked, or check *Windows Defender Firewall → Advanced → Inbound rules → "Apofiz Play GTA6"*.
  Third-party antivirus firewalls need the same ports allowed.
- **Wi-Fi vs Ethernet** — Remote Play is ~10-15 Mbit/s of UDP at 720p60. Ethernet on
  the PS5 (and ideally the PC) removes most stutter and FEC errors; on Wi-Fi use 5 GHz,
  or lower `PS5_RESOLUTION=540p` / `PS5_FPS=30` in `.env.local`.
- **NVIDIA vs CPU** — the default build runs YOLO on the CPU (~60-150 ms per frame on a
  modern 6-core; the pilot only calls it a few times a second in danger). With an NVIDIA
  GPU build with `-Cuda` (~5-10 ms). AMD/Intel GPUs use the CPU build.
- **AI brain** — the bot uses the `claude` CLI; install Claude Code and sign in. The launcher
  adds `%APPDATA%\npm` and `%USERPROFILE%\.local\bin` to PATH for it.
- **Logs** — `%LOCALAPPDATA%\ApofizPlay\logs\launcher.log` and `server.log`
  (Start Menu → Apofiz Play GTA6 → Logs).
- **Port 8765 busy** — the launcher picks the next free port automatically.

## Known issues (code outside packaging/)

See the build report; the installer works around them by giving Users modify rights on
the install folder.
