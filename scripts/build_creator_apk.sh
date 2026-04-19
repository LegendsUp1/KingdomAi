#!/usr/bin/env bash
# Build the CREATOR-mode Android APK.
#
# Output: ~/KingdomAI-Private/KingdomAI-Creator.apk (never in the repo,
# never in the public Netlify downloads, never in the consumer Easy Store
# backup).
#
# Prerequisites:
#   - flet CLI installed (pip install flet)
#   - Android SDK + Java 17 available
#   - release.keystore + key.properties in mobile_build/build/flutter/android/app/
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="${OUT_DIR:-$HOME/KingdomAI-Private}"
mkdir -p "$OUT_DIR"

export KINGDOM_APP_MODE=creator
# Mobile platform — light dependency tier for the APK.
export KINGDOM_APP_PLATFORM=mobile

# Creator APK uses the existing creator launcher (kingdom_mobile_creator.py)
# which sets KINGDOM_APP_MODE=creator before importing the shared engine
# (kingdom_mobile.py). We pass it to flet via --module-name so the APK boots
# straight into creator mode without touching the consumer launcher.
if [[ ! -f "$ROOT/mobile_build/kingdom_mobile_creator.py" ]]; then
  echo ""
  echo "ERROR: mobile_build/kingdom_mobile_creator.py not found."
  echo "This launcher sets KINGDOM_APP_MODE=creator before loading the shared"
  echo "engine. Without it, the APK would boot in whatever mode the device"
  echo "happens to have set (usually none)."
  echo ""
  exit 2
fi

pushd "$ROOT/mobile_build" >/dev/null
echo "Building Kingdom AI creator APK (mode=creator)..."
BUILD_VERSION="$(python3 -c 'import json; print(json.load(open("'"$ROOT"'/config/version.json"))["flutter_build"].split("+")[0])')"

# Isolate the creator build's output tree so it cannot clobber the public
# consumer build in mobile_build/build/apk/.
CREATOR_OUTDIR="$ROOT/mobile_build/build/apk-creator"
rm -rf "$CREATOR_OUTDIR"

# --module-name forces flet to use the creator launcher as the Python entry
# point for this build. The consumer launcher is not touched.
# --project / --product / --artifact differentiate the bundle id, app name,
# and on-disk APK filename so both variants can coexist on one device.
flet build apk --yes \
  --build-version "$BUILD_VERSION" \
  --module-name kingdom_mobile_creator \
  --project "kingdom-ai-creator" \
  --product "Kingdom AI (Creator)" \
  --artifact "kingdom-ai-creator" \
  --output "$CREATOR_OUTDIR" || {
  echo "flet build failed"; popd; exit 1;
}
popd >/dev/null

SRC_APK="$(ls -t "$CREATOR_OUTDIR"/*.apk 2>/dev/null | head -1 || true)"
if [[ -z "$SRC_APK" ]]; then
  echo "no APK found after flet build"; exit 1
fi

TARGET="$OUT_DIR/KingdomAI-Creator.apk"
cp -f "$SRC_APK" "$TARGET"
sha256sum "$TARGET" | awk '{print $1}' > "$TARGET.sha256"
chmod 600 "$TARGET" "$TARGET.sha256"

echo ""
echo "Creator APK written: $TARGET"
echo "SHA-256 written:     $TARGET.sha256"
echo "Remember: this file must NEVER be uploaded to Netlify or committed."
