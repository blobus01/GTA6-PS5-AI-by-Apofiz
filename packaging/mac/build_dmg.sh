#!/usr/bin/env bash
# Build "Apofiz Play GTA6.app" and its .dmg (macOS, Apple Silicon).
#
#   packaging/mac/build_dmg.sh            # from the repo root (or anywhere)
#
# Outputs:
#   dist/Apofiz Play GTA6.app
#   dist/ApofizPlay-GTA6-<VERSION>-mac-arm64.dmg
#   dist/ApofizPlay-GTA6-mac-arm64.dmg            (version-less copy for "latest")
#
# Environment (all optional):
#   VERSION                 override; must match the VERSION file in CI
#   APOFIZ_BUILD_CACHE      download/pip cache (default ~/.cache/apofiz-build)
#   APOFIZ_WITH_ML=0        skip ultralytics/torch (≈ -600 MB; YOLO features off)
#   APOFIZ_SKIP_DMG=1       build the .app only
#   APOFIZ_DMG_FORMAT       hdiutil format, default ULFO (lzfse); UDZO for max compat
#   APOFIZ_DMG_LAYOUT=0     skip the Finder window layout step (headless boxes)
#   Signing (default: ad-hoc "-", fine for local testing only):
#   APOFIZ_CODESIGN=1 + APPLE_SIGN_IDENTITY="Developer ID Application: … (TEAMID)"
#                           sign every Mach-O + the app with --options runtime --timestamp
#   APPLE_TEAM_ID           informational / sanity check against the identity
#   APPLE_NOTARY_PROFILE    keychain profile for `xcrun notarytool` (store-credentials);
#                           when set (and signing is on) the dmg is notarized + stapled.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
cd "$REPO"

FILE_VERSION="$(tr -d ' \n\r' < VERSION)"
VERSION="${VERSION:-$FILE_VERSION}"
if [[ "$VERSION" != "$FILE_VERSION" ]]; then
  echo "!! VERSION env ($VERSION) != VERSION file ($FILE_VERSION)" >&2
  exit 1
fi
BUILD_NUM="${BUILD_NUMBER:-${GITHUB_RUN_NUMBER:-$(date +%Y%m%d%H%M)}}"

CACHE="${APOFIZ_BUILD_CACHE:-$HOME/.cache/apofiz-build}"
WITH_ML="${APOFIZ_WITH_ML:-1}"
DMG_FORMAT="${APOFIZ_DMG_FORMAT:-ULFO}"

# Pinned python-build-standalone (astral-sh) release.
PBS_TAG="20261110"
PBS_PY="3.12.16"
PBS_FILE="cpython-${PBS_PY}+${PBS_TAG}-aarch64-apple-darwin-install_only_stripped.tar.gz"
PBS_SHA256="2f11b8aa3726bdbd87dd9eb76568412faddf4f47e26913fa45d6a2e424972acd"
PBS_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_TAG}/${PBS_FILE/+/%2B}"

APP_NAME="Apofiz Play GTA6"
DIST="$REPO/dist"
APP="$DIST/$APP_NAME.app"
DMG="$DIST/ApofizPlay-GTA6-${VERSION}-mac-arm64.dmg"
DMG_LATEST="$DIST/ApofizPlay-GTA6-mac-arm64.dmg"
CONTENTS="$APP/Contents"
RES="$CONTENTS/Resources"
PY="$RES/python/bin/python3"

step() { printf '\n==> %s\n' "$*"; }

[[ "$(uname -s)" == "Darwin" ]] || { echo "macOS only" >&2; exit 1; }
[[ "$(uname -m)" == "arm64" ]] || echo "!! building on $(uname -m); output is still arm64 (python + wheels are arm64)"

# ---------------------------------------------------------------- python
step "python-build-standalone $PBS_PY ($PBS_TAG)"
mkdir -p "$CACHE"
if [[ ! -f "$CACHE/$PBS_FILE" ]]; then
  curl -fL --retry 3 -o "$CACHE/$PBS_FILE.part" "$PBS_URL"
  mv "$CACHE/$PBS_FILE.part" "$CACHE/$PBS_FILE"
fi
echo "$PBS_SHA256  $CACHE/$PBS_FILE" | shasum -a 256 -c -

step "app skeleton -> $APP"
rm -rf "$APP"
mkdir -p "$CONTENTS/MacOS" "$RES/app"
tar -xzf "$CACHE/$PBS_FILE" -C "$RES"          # -> Resources/python
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
unset PYTHONPATH PYTHONHOME

# ---------------------------------------------------------------- deps
step "dependencies (ML=$WITH_ML)"
REQS=(-r requirements.txt -r launcher/requirements.txt)
[[ "$WITH_ML" == "1" ]] && REQS+=(ultralytics)
if command -v uv >/dev/null 2>&1 && [[ "${APOFIZ_USE_UV:-1}" == "1" ]]; then
  UV_CACHE_DIR="$CACHE/uv" uv pip install --python "$PY" --link-mode=copy --no-compile "${REQS[@]}"
else
  "$PY" -m pip install --disable-pip-version-check --no-warn-script-location --no-compile \
    --cache-dir "$CACHE/pip" "${REQS[@]}"
fi
"$PY" - <<'EOF'
import aiohttp, av, PIL, pystray, requests, psnawp_api, mcp  # noqa: F401
import AppKit  # noqa: F401  (pystray darwin backend)
print("imports ok")
EOF

step "prune"
SP="$RES/python/lib/python3.12"
rm -rf "$SP/test" "$SP/idlelib" "$SP/tkinter" "$SP/turtledemo" "$SP/lib2to3" \
       "$RES/python/share" "$RES/python/bin/idle"* "$RES/python/bin/2to3"* "$RES/python/bin/pydoc"*
rm -rf "$RES/python/lib/tcl"* "$RES/python/lib/tk"* "$RES/python/lib/itcl"* "$RES/python/lib/thread"* 2>/dev/null || true
rm -f "$SP/lib-dynload/_tkinter"*.so
if [[ -d "$SP/site-packages/torch" ]]; then
  rm -rf "$SP/site-packages/torch/include" "$SP/site-packages/torch/share" "$SP/site-packages/torch/test"
fi
find "$RES/python" -name '__pycache__' -type d -prune -exec rm -rf {} +
find "$RES/python" -name '*.pyi' -delete

# ---------------------------------------------------------------- app files
step "project files"
rsync -a --delete \
  --exclude '/.git' --exclude '/.github' --exclude '/.venv' --exclude '/.buildenv' --exclude '/vendor' \
  --exclude '/logs' --exclude '/shots' --exclude '/dist' --exclude '/build' --exclude '/packaging' \
  --exclude '/site' --exclude '/docs' --exclude '/tests' --exclude '.pytest_cache' --exclude '/dsh-bundle' \
  --exclude '__pycache__' --exclude '*.pyc' --exclude '*.log' --exclude '.DS_Store' \
  --exclude '.env.local' --exclude '.env.*.local' --exclude '.mcp.json' --exclude '.claude' \
  --exclude 'native/build' --exclude '*.dll' --exclude '*.lib' --exclude '*.pdb' \
  --exclude '/launcher/assets/make_icons.py' --exclude '/start.cmd' --exclude '/start.sh' \
  ./ "$RES/app/"
[[ -f "$RES/app/native/libps5bridge.dylib" ]] || echo "!! native/libps5bridge.dylib missing — Remote Play will not work"
[[ -f "$RES/app/yolo11n.pt" ]] && echo "   yolo11n.pt included" || echo "   (no yolo11n.pt — ultralytics downloads it on first use)"
echo "$VERSION" > "$RES/app/VERSION"

step "bytecode (unchecked-hash: valid inside a read-only signed bundle)"
"$PY" -m compileall -q -j 0 --invalidation-mode unchecked-hash "$SP" "$RES/app" >/dev/null || true

step "launcher stub + Info.plist + icon"
clang -O2 -arch arm64 -mmacosx-version-min=12.0 \
  -I "$RES/python/include/python3.12" "$HERE/stub.c" \
  -L "$RES/python/lib" -lpython3.12 \
  -Wl,-rpath,@executable_path/../Resources/python/lib \
  -o "$CONTENTS/MacOS/ApofizPlay"
sed -e "s/@VERSION@/$VERSION/" -e "s/@BUILD@/$BUILD_NUM/" "$HERE/Info.plist.in" > "$CONTENTS/Info.plist"
plutil -lint "$CONTENTS/Info.plist" >/dev/null
printf 'APPL????' > "$CONTENTS/PkgInfo"
cp launcher/assets/icon.icns "$RES/AppIcon.icns"

# ---------------------------------------------------------------- signing
# NUL-separated list of Mach-O files except the main stub (signed last).
macho_files() {
  find "$CONTENTS" -type f \( -name '*.so' -o -name '*.dylib' -o -perm -u+x \) -print0 |
    while IFS= read -r -d '' f; do
      [[ "$f" == "$CONTENTS/MacOS/ApofizPlay" ]] && continue
      if file -b "$f" | grep -q 'Mach-O'; then printf '%s\0' "$f"; fi
    done
}
if [[ "${APOFIZ_CODESIGN:-0}" == "1" && -n "${APPLE_SIGN_IDENTITY:-}" ]]; then
  step "codesign with '$APPLE_SIGN_IDENTITY' (hardened runtime)"
  if [[ -n "${APPLE_TEAM_ID:-}" && "$APPLE_SIGN_IDENTITY" != *"$APPLE_TEAM_ID"* ]]; then
    echo "!! APPLE_SIGN_IDENTITY does not mention APPLE_TEAM_ID=$APPLE_TEAM_ID" >&2
  fi
  SIGN=(codesign --force --timestamp --options runtime --entitlements "$HERE/entitlements.plist" --sign "$APPLE_SIGN_IDENTITY")
  # inside-out: every library/executable, then the stub, then the bundle
  macho_files | xargs -0 -n 50 -P 4 "${SIGN[@]}"
  "${SIGN[@]}" "$CONTENTS/MacOS/ApofizPlay"
  "${SIGN[@]}" "$APP"
  codesign --verify --strict --deep --verbose=2 "$APP"
  SIGNED=1
else
  step "ad-hoc codesign (local testing; set APOFIZ_CODESIGN=1 + APPLE_SIGN_IDENTITY for release)"
  # wheels/python are already linker-signed; sign the stub + seal the bundle.
  codesign --force --sign - "$CONTENTS/MacOS/ApofizPlay"
  codesign --force --sign - "$APP"
  codesign --verify --deep "$APP"
  SIGNED=0
fi
du -sh "$APP"

[[ "${APOFIZ_SKIP_DMG:-0}" == "1" ]] && { echo "APOFIZ_SKIP_DMG=1, done"; exit 0; }

# ---------------------------------------------------------------- dmg
step "dmg ($DMG_FORMAT)"
STAGE="$(mktemp -d "${TMPDIR:-/tmp}/apofiz-dmg.XXXXXX")"
MNT=""
trap 'hdiutil detach "$MNT" -quiet -force >/dev/null 2>&1 || true; rm -rf "$STAGE"' EXIT
VOL="$APP_NAME"
mkdir -p "$STAGE/src/.background"
ditto "$APP" "$STAGE/src/$APP_NAME.app"
ln -s /Applications "$STAGE/src/Applications"
"$PY" "$HERE/make_background.py" "$STAGE/bg" >/dev/null
tiffutil -cathidpicheck "$STAGE/bg/background.png" "$STAGE/bg/background@2x.png" \
  -out "$STAGE/src/.background/background.tiff" >/dev/null 2>&1 \
  || cp "$STAGE/bg/background.png" "$STAGE/src/.background/background.tiff"
cp launcher/assets/icon.icns "$STAGE/src/.VolumeIcon.icns"

SIZE_MB=$(( $(du -sm "$STAGE/src" | cut -f1) + 200 ))
hdiutil create -quiet -srcfolder "$STAGE/src" -volname "$VOL" -fs HFS+ -format UDRW \
  -size "${SIZE_MB}m" "$STAGE/rw.dmg"
MNT="$(hdiutil attach -readwrite -noverify -noautoopen "$STAGE/rw.dmg" | awk -F'\t' '/\/Volumes\//{print $NF; exit}')"
echo "   mounted at $MNT"
SetFile -a C "$MNT" 2>/dev/null || true   # custom volume icon (needs Xcode CLT)

if [[ "${APOFIZ_DMG_LAYOUT:-1}" == "1" ]]; then
  # Finder layout is cosmetic: never fail the build on it (CI runners may block AppleEvents).
  /usr/bin/osascript <<EOF || echo "!! Finder layout skipped (no AppleEvents access)"
tell application "Finder"
  tell disk "$(basename "$MNT")"
    open
    set current view of container window to icon view
    set toolbar visible of container window to false
    set statusbar visible of container window to false
    set the bounds of container window to {200, 120, 860, 560}
    set opts to the icon view options of container window
    set arrangement of opts to not arranged
    set icon size of opts to 112
    set text size of opts to 13
    set background picture of opts to file ".background:background.tiff"
    set position of item "$APP_NAME.app" of container window to {170, 230}
    set position of item "Applications" of container window to {490, 230}
    update without registering applications
    delay 1
    close
  end tell
end tell
EOF
fi
chmod -Rf go-w "$MNT" 2>/dev/null || true
sync
hdiutil detach "$MNT" -quiet || { sleep 2; hdiutil detach "$MNT" -force -quiet; }
MNT=""

mkdir -p "$DIST"
rm -f "$DMG"
hdiutil convert -quiet "$STAGE/rw.dmg" -format "$DMG_FORMAT" -o "$DMG"

if [[ "$SIGNED" == "1" ]]; then
  codesign --force --timestamp --sign "$APPLE_SIGN_IDENTITY" "$DMG"
  if [[ -n "${APPLE_NOTARY_PROFILE:-}" ]]; then
    step "notarize ($APPLE_NOTARY_PROFILE)"
    xcrun notarytool submit "$DMG" --keychain-profile "$APPLE_NOTARY_PROFILE" --wait
    xcrun stapler staple "$DMG"
  fi
fi

cp -f "$DMG" "$DMG_LATEST"
step "done"
ls -lh "$DMG" "$DMG_LATEST"
shasum -a 256 "$DMG"
