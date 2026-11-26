# Releasing ApofizPlay GTA6

A release is a git tag `vX.Y.Z`. CI builds the installers, and the app's
auto-updater finds them on GitHub Releases.

## Steps

1. **Bump the version.** Edit `VERSION` at the repo root (one line, e.g. `0.2.0`;
   a pre-release is `0.2.0-beta.1`). The launcher, the installers and the
   updater all read this file.
2. **Write the notes.** In `CHANGELOG.md` move the `[Unreleased]` items into a new
   section `## [0.2.0] - YYYY-MM-DD`. CI copies that section into the release.
3. **Commit and push** to `main`:
   ```bash
   git commit -am "Release 0.2.0" && git push origin main
   ```
4. **Tag and push the tag:**
   ```bash
   git tag v0.2.0 && git push origin v0.2.0
   ```
   The tag must equal `v` + the content of `VERSION`, otherwise CI stops.
5. **CI** (`.github/workflows/release.yml`) runs:
   - `mac` on `macos-15` (arm64): `packaging/mac/build_dmg.sh` →
     `dist/ApofizPlay-GTA6-<VERSION>-mac-arm64.dmg`, optional codesign +
     notarization, then a `.sha256` file;
   - `windows` on `windows-latest`: `packaging/windows/build.ps1` →
     `dist/ApofizPlay-GTA6-<VERSION>-win-x64-Setup.exe`, optional Authenticode
     signing, then a `.sha256` file;
   - `release`: checks the hashes and publishes GitHub Release `vX.Y.Z` with all
     four files and the CHANGELOG section as notes. A version with a `-suffix`
     is marked as a pre-release.
6. **Check** the release page: two installers + two `.sha256` files.

A dry run without publishing: *Actions → release → Run workflow* on a branch.
The installers are kept as workflow artifacts. To publish from the UI, run it on
a `v*` tag with **publish** ticked.

## Signing (optional)

Signing steps run only when their repository secrets exist; without them the
build is unsigned (macOS Gatekeeper and Windows SmartScreen will warn).

| Platform | Secrets |
|---|---|
| macOS sign | `APPLE_CERT_P12_BASE64`, `APPLE_CERT_PASSWORD`, `APPLE_SIGN_IDENTITY` ("Developer ID Application: …") |
| macOS notarize | `APPLE_ID`, `APPLE_TEAM_ID`, `APPLE_APP_PASSWORD` (app-specific password) |
| Windows | `WIN_SIGN_PFX_BASE64`, `WIN_SIGN_PASSWORD` |

When the macOS certificate is imported, CI sets `APOFIZ_CODESIGN=1` and
`APPLE_SIGN_IDENTITY` for `build_dmg.sh`, so the script can sign the `.app`
inside the image (with `--options runtime` for notarization). CI then signs and
notarizes the `.dmg` itself. On Windows CI sets `WIN_SIGN_PFX` (path to the
certificate) and `WIN_SIGN_PASSWORD` for `build.ps1` to sign inner `.exe`
files; CI signs the final Setup.exe.

## How auto-update finds a release

`apofiz_update.py` (called by the launcher):

1. Asks `https://api.github.com/repos/blobus01/GTA6-PS5-AI-by-Apofiz/releases/latest`
   (channel `stable`, skips pre-releases) or `/releases` (channel `beta`).
   Timeout 5 s; the answer is cached for 6 hours in `~/.ps5-remote/update.json`.
   Offline, rate limited or private repo → no update, the app keeps working.
2. Compares the tag with the running `VERSION` by semver.
3. Picks the asset for the machine: `*-mac-arm64.dmg` on Apple Silicon,
   `*-win-x64-Setup.exe` on Windows (x64 and ARM64). Intel Macs and Linux get no
   update.
4. Reads the matching `<asset>.sha256` file. An update without a checksum is
   refused.
5. On install it downloads to a temp folder and verifies SHA-256. On macOS it
   opens the `.dmg` and the user drags the app to Applications. On Windows it
   starts `Setup.exe /SILENT` after the app quits.

So a release is picked up only if the tag is a valid semver, the release is
not a draft, and the asset names match the pattern above exactly.

While the repo is private, the API returns 404 to anonymous clients and the
updater sees no update. Set `APOFIZ_UPDATE_TOKEN` (a read-only token) for
testing, or make the repo public. `APOFIZ_UPDATE_REPO=owner/name` points the
updater at another repo.

Check by hand: `python apofiz_update.py --current 0.0.1 --force`.

## Note on build-native.yml

`build-native.yml` also runs on `v*` tags and creates a release with
`ps5bridge.dll`. `release.yml` adds its files to that release if it already
exists. If `release.yml` finishes first, the `gh release create` step in
`build-native.yml` fails because the release already exists. Change that step
to `gh release upload --clobber` or drop the tag trigger there.
