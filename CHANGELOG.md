# Changelog

All notable changes to ApofizPlay GTA6 (GTA6 PS5 AI by Apofiz) are listed here.
Versions follow [Semantic Versioning](https://semver.org). The release workflow
copies the section for a version into its GitHub Release notes, so keep the
heading format `## [X.Y.Z] - YYYY-MM-DD`.

## [Unreleased]

## [0.2.0] - 2026-11-26

First public build.

### Added
- **Remote Play bridge.** Connects to a real PS5 over Sony Remote Play (chiaki-ng):
  video in, gamepad out, web remote and REST API on `127.0.0.1:8765`. Native
  bridge for Windows (`ps5bridge.dll`) and macOS Apple Silicon (`libps5bridge.dylib`).
- **Bot (`agent.py`).** Goal-driven scenarios: steal a car (WAiNK scanner, skips
  keyless and tracked cars, carjacking, Slim Jim, window smash, hotwire
  mini-game), recover after WASTED, drive to the waypoint.
- **Brain (`brain.py`).** Persistent Claude process via the Claude Code CLI and
  the user's own subscription; short JSON decisions every few seconds, token log.
- **HUD reflexes (`hud.py`, `pilot.py`).** Pixel reader for health, wanted stars,
  WASTED and damage tint in about 1 ms; 15 Hz YOLO11 pilot (MPS on Apple Silicon)
  for cars and people; fights back or flees without waiting for the LLM.
- **Autopilot.** Sets a waypoint on the map (story mission icons) and uses the
  in-game Quick Navigation autopilot, with its own driving as fallback.
- **Knowledge base.** Controls cheat-sheet (`controls_gta6.md`) plus a full GTA VI
  knowledge base in `knowledge/` (on foot, combat, vehicles, police, phone,
  missions, short-form clipping rules).
- **MCP server.** Tools so any agent (Claude Code etc.) can drive the PS5.
- **Streamer overlay.** OBS overlay with the bot's live thoughts at `/overlay`.
- **Landing page** for the project (`site/`).
- **Desktop app.** Tray launcher, setup wizard, installers for macOS (.dmg) and
  Windows (Setup.exe), and auto-update from GitHub Releases with SHA-256 checks.
