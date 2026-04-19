#!/usr/bin/env bash
# CREATOR / OWNER code backup: kingdom_ai → easystore/kingdom_ai
# (Not a consumer-safe bundle — for that use scripts/sync_to_easystore_consumer.sh.)
# Mount: /media/kingzilla456/easystore (label: easystore)
#
# Usage:
#   bash scripts/sync_to_easystore.sh              # sync (add/update files; does NOT delete extra files on easystore)
#   bash scripts/sync_to_easystore.sh --mirror     # strict mirror: DELETE on easystore anything not in source (dangerous)
#   bash scripts/sync_to_easystore.sh --dry-run    # preview
#
# Heavy / reproducible paths are excluded (reinstall venvs, re-download models).
# To also sync wallet/data or GPT-SoVITS, run separate rsyncs (see bottom comments).

set -euo pipefail

SRC="${SRC:-/home/kingzilla456/kingdom_ai}"
DEST="${DEST:-/media/kingzilla456/easystore/kingdom_ai}"

if [[ ! -d "$(dirname "$DEST")" ]] || [[ ! -w "$(dirname "$DEST")" ]]; then
  echo "ERROR: easystore not mounted or not writable: $(dirname "$DEST")"
  echo "Plug in Easy Store and open the drive once so it mounts at /media/$USER/easystore"
  exit 1
fi

DRY=()
DELETE=()
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY=(--dry-run)
  echo "DRY RUN — no files copied"
fi
if [[ "${1:-}" == "--mirror" ]] || [[ "${2:-}" == "--mirror" ]]; then
  DELETE=(--delete)
  echo "MIRROR mode: files removed from easystore if not in source (use with care)"
fi

mkdir -p "$DEST"

# Same spirit as robocopy_all_versions.ps1 excludes
# Accident paths that look like Windows drive letters (break exFAT / invalid names on dest)
WINPATH_EXCLUDES=(
  --exclude='D*kingdom*'
  --exclude='D:*/'
)

rsync -a "${DRY[@]}" --info=progress2 "${DELETE[@]}" \
  "${WINPATH_EXCLUDES[@]}" \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='node_modules/' \
  --exclude='.venv/' \
  --exclude='venv/' \
  --exclude='kingdom-venv/' \
  --exclude='voice_runtime_env/' \
  --exclude='kingdom_voice_env/' \
  --exclude='creation_env/' \
  --exclude='windows_creation_env/' \
  --exclude='poetry-env/' \
  --exclude='ml_packages_venv/' \
  --exclude='.flet/' \
  --exclude='firmware/' \
  --exclude='HunyuanVideo/' \
  --exclude='GPT-SoVITS/' \
  --exclude='data/' \
  --exclude='zen/' \
  --exclude='android-stubs/' \
  --exclude='.gradle/' \
  --exclude='build/' \
  --exclude='kingdom_ai/venv/' \
  "$SRC/" "$DEST/"

echo ""
echo "Done: $SRC → $DEST"
echo "Excluded (sync separately if needed): data/, GPT-SoVITS/, *venv*, zen/, node_modules/"
echo "Optional full data: rsync -a --info=progress2 $SRC/data/ $DEST/data/"
echo "Consumer-safe bundle (no owner secrets): bash scripts/sync_to_easystore_consumer.sh"

# ──────────────────────────────────────────────────────────────────────────
# Creator private artifacts (APK, iOS PWA bundle, encrypted bootstrap,
# FIRST_RUN_CREDENTIALS). These live OUTSIDE the repo (~/KingdomAI-Private/)
# so they never touch git, but they are essential for restoring the creator
# setup on a new computer. Mirror them separately into a sibling folder on
# Easy Store that is NEVER referenced by the consumer sanitizer.
# ──────────────────────────────────────────────────────────────────────────
PRIV_SRC="${PRIV_SRC:-$HOME/KingdomAI-Private}"
PRIV_DEST="${PRIV_DEST:-/media/kingzilla456/easystore/KingdomAI-Private}"
if [[ -d "$PRIV_SRC" ]]; then
  mkdir -p "$PRIV_DEST"
  rsync -a "${DRY[@]}" --info=progress2 "${DELETE[@]}" "$PRIV_SRC/" "$PRIV_DEST/"
  echo "Done: $PRIV_SRC → $PRIV_DEST  (creator APK + PWA bundle + credentials)"
else
  echo "Note: $PRIV_SRC not present; skipping private artifact backup."
fi
