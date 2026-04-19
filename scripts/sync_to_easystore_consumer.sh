#!/usr/bin/env bash
# CONSUMER-SAFE bundle → Easy Store (does NOT copy creator keys or owner data).
#
# Use this when you want a tree safe to hand to "consumer edition" users — NOT sync_to_easystore.sh
# for that purpose (that one is creator-oriented code backup; this one strips secrets).
#
#   bash scripts/sync_to_easystore_consumer.sh
#   DEST=/media/kingzilla456/easystore/kingdom_ai_consumer bash scripts/sync_to_easystore_consumer.sh
#
# Phase B hardening (2026-04): expanded excludes to cover every leak surface
# documented in the audit + call verify_consumer_bundle.sh afterwards; on any
# verifier hit the staged tree is removed and the script exits non-zero.
#
set -euo pipefail

SRC="${SRC:-/home/kingzilla456/kingdom_ai}"
DEST="${DEST:-/media/kingzilla456/easystore/kingdom_ai_consumer}"
STAGE="${STAGE:-${DEST}.stage}"

if [[ ! -d "$(dirname "$DEST")" ]] || [[ ! -w "$(dirname "$DEST")" ]]; then
  echo "ERROR: easystore not mounted or not writable: $(dirname "$DEST")"
  exit 1
fi

DRY=()
[[ "${1:-}" == "--dry-run" ]] && DRY=(--dry-run) && echo "DRY RUN"

mkdir -p "$STAGE"

# Accident paths that look like Windows drive letters (break exFAT on dest)
WINPATH_EXCLUDES=( --exclude='D*kingdom*' --exclude='D:*/' )

# Never ship creator-only or machine-private material to consumer bundles
# (Phase B expanded list. Re-runs are idempotent. See SECURITY.md never-ship list.)
SECRET_EXCLUDES=(
  # -- primary key stores --
  --exclude='config/api_keys.json'
  --exclude='config/api_keys.env'
  --exclude='config/.secrets.env'
  --exclude='config/.secrets.env.*'
  --exclude='.env'
  --exclude='.env.*'
  --exclude='.env.bak'
  --exclude='config/COMPLETE_SYSTEM_CONFIG.json'
  --exclude='config/redis_password.txt'
  # -- creator-only runtime files --
  --exclude='config/mobile_config_creator.json'
  --exclude='config/*_creator*.json'
  --exclude='config/account_link.json'
  --exclude='config/multi_coin_wallets.json'
  --exclude='config/wallet_external.json'
  --exclude='config/kaig/wallets.json'
  --exclude='config/kaig/'
  # -- creator data / owner data --
  --exclude='data/'
  --exclude='data/biometric_security/'
  --exclude='data/owner_enrollment/'
  --exclude='data/wallets/'
  --exclude='data/recovery/'
  --exclude='data/users/'
  --exclude='data/learning/'
  --exclude='data/scraped_content/'
  # -- owner docs / historical leak vectors --
  --exclude='AUTONOMOUS_*.md'
  --exclude='API_KEYS_*.md'
  --exclude='COMPLETE_API_KEY_*.md'
  --exclude='global_api_keys.py'
  --exclude='user_creator_*.json'
  --exclude='*.pem'
  --exclude='*.key'
  --exclude='*.jks'
  --exclude='release-keystore/'
  # -- logs & private backups --
  --exclude='logs/'
  --exclude='.private_backups/'
  --exclude='KingdomAI-Private/'
  # -- internal helpers that should never leave the creator machine --
  --exclude='scripts/_internal_*.py'
  --exclude='scripts/sync_to_easystore*.sh'
  --exclude='scripts/build_creator_*.sh'
  --exclude='core/creator_install_server.py'
  # -- transient build output --
  --exclude='mobile_build/build/'
  # -- third-party vendor installers / dev scripts that don't belong in a
  #    consumer bundle and can trip binary-scan false positives --
  --exclude='Unity Hub/'
  --exclude='exports/unity/'
  --exclude='robocopy_all_versions.ps1'
  --exclude='robocopy_*.ps1'
  --exclude='*.ps1'
)

rsync -a "${DRY[@]}" --info=progress2 \
  "${WINPATH_EXCLUDES[@]}" \
  "${SECRET_EXCLUDES[@]}" \
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
  --exclude='zen/' \
  --exclude='android-stubs/' \
  --exclude='.gradle/' \
  --exclude='build/' \
  --exclude='kingdom_ai/venv/' \
  "$SRC/" "$STAGE/"

# Phase C gate: any secret pattern in the staged tree aborts the sync.
VERIFIER="${SRC}/scripts/verify_consumer_bundle.sh"
if [[ -x "$VERIFIER" ]]; then
  echo ""
  echo "Running consumer bundle verifier..."
  if ! "$VERIFIER" "$STAGE"; then
    echo "ERROR: consumer bundle verification FAILED; staging tree retained at $STAGE for inspection."
    echo "Fix the leaks (extend excludes or redact tracked files) before re-running."
    exit 2
  fi
else
  echo "NOTE: $VERIFIER not found or not executable; skipping verifier gate."
fi

# Atomic promote: stage -> dest (keep previous as .prev for one cycle).
if [[ -d "$DEST" ]]; then
  rm -rf "${DEST}.prev"
  mv "$DEST" "${DEST}.prev"
fi
mv "$STAGE" "$DEST"

echo ""
echo "CONSUMER bundle done: $SRC → $DEST"
echo "Included: code + consumer-safe config EXCEPT secret files above; data/ excluded."
echo "Previous bundle retained at ${DEST}.prev (remove when satisfied)."
echo "Consumers use config/mobile_config.json and add their own keys on device."
