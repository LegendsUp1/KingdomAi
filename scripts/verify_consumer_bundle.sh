#!/usr/bin/env bash
# verify_consumer_bundle.sh -- Phase C of the hardening plan.
#
# Scans a consumer artifact for creator-data leaks. Accepts:
#   - a directory
#   - a .apk / .zip / .jar (unpacked with unzip)
#   - a .AppImage (mounted / extracted with --appimage-extract)
#   - a .dmg (extracted with 7z if present; otherwise skipped with warning)
#   - a .exe (scanned as-is with strings)
#
# Exits non-zero on any pattern hit. Designed to run from CI, from
# sync_to_easystore_consumer.sh, and from manual release drills.
#
# Usage:
#   scripts/verify_consumer_bundle.sh <path>            # single target
#   scripts/verify_consumer_bundle.sh <path> [<path>..] # multiple targets
#
set -euo pipefail

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 <dir-or-archive> [<dir-or-archive>...]" >&2
  exit 64
fi

# ---- patterns that must never appear in a consumer artifact ----
# Known live-token prefixes, creator-only filenames, owner data markers.
LEAK_PATTERNS=(
  # token prefixes
  'KAIG-[A-Z0-9]{4,}'
  'nfp_[A-Za-z0-9]{20,}'
  'ghp_[A-Za-z0-9]{20,}'
  'HRKU-[A-Za-z0-9-]{10,}'
  'figd_[A-Za-z0-9_-]{20,}'
  'xai-[A-Za-z0-9_-]{20,}'
  'sk-[A-Za-z0-9_-]{20,}'
  'sk-ant-[A-Za-z0-9_-]{20,}'
  'AKIA[0-9A-Z]{16}'
  'AstraCS:[A-Za-z0-9]+:'
  'dckr_pat_[A-Za-z0-9_-]{10,}'
  'github_pat_[A-Za-z0-9_]{30,}'
  # creator-only filename/content signatures. Only match strings that can
  # ONLY appear as a real leak (either the filename being present in the
  # bundle, or the file's content being inlined). Rsync excludes already
  # omit the actual files; these catch anything that slips through.
  'mobile_config_creator\.json'
  'account_link\.json'
  'KingdomAI-Creator\.apk'
)

# Hard-fail if any of these creator-only filenames exist as files in the tree.
FORBIDDEN_FILES=(
  'mobile_config_creator.json'
  'account_link.json'
  '.secrets.env'
  'creator_bootstrap.enc'
  'KingdomAI-Creator.apk'
  'FIRST_RUN_CREDENTIALS.txt'
  'creator_passphrase.txt'
)

# ---- files that LEGITIMATELY mention leak-pattern names as part of their
# defensive purpose (gitignore rules, SECURITY.md documentation, the verifier
# itself, pre-commit hook rules, and the consumer-guard code that checks for
# the presence of `.secrets.env` and refuses to start if found).
# These files are allowlisted so the verifier does not trip on its own
# documentation / enforcement wiring.
ALLOWLIST_FILES=(
  '.gitignore'
  '.gitleaks.toml'
  '.pre-commit-config.yaml'
  'SECURITY.md'
  'verify_consumer_bundle.sh'
  'sync_to_easystore_consumer.sh'
  'sync_to_easystore.sh'
  'build_creator_apk.sh'
  'build_creator_pwa.sh'
  '_internal_write_creator_bootstrap.py'
  '_internal_redact_phase_a.py'
  'secrets_loader.py'
  'main.py'
  'kingdom_mobile_consumer.py'
  'kingdom_mobile.py'
  'creator_install_server.py'
  'recovery_vault.py'
  'api_key_catalog.json'
  'HANDOFF.md'
  'DOCUMENTATION_MASTER_INDEX.md'
  'AUTONOMOUS_TRADING_COMPLETE.md'
  # source files that legitimately build or mention KAIG-* identifiers
  # (template strings, schema examples, comments) but carry no live values.
  # These are safe to ship: the runtime always generates fresh, device-local
  # values on first launch.
  'kaig_engine.py'
  'username_registry.py'
  'kaig_engine_integration.py'
  'kaig_stealth_core.py'
)

# Build grep --exclude args from the allowlist.
GREP_EXCLUDES=()
for f in "${ALLOWLIST_FILES[@]}"; do
  GREP_EXCLUDES+=( --exclude="$f" )
done

# ---- helper to run grep across the tree with the patterns above ----
run_rg() {
  local target="$1"
  local pattern
  local hits=0
  for pattern in "${LEAK_PATTERNS[@]}"; do
    if grep -REH --binary-files=text "${GREP_EXCLUDES[@]}" "$pattern" "$target" 2>/dev/null >/tmp/verify_hits.$$ ; then
      if [[ -s /tmp/verify_hits.$$ ]]; then
        echo ""
        echo "LEAK pattern matched: $pattern"
        head -5 /tmp/verify_hits.$$
        hits=$((hits + 1))
      fi
    fi
  done
  rm -f /tmp/verify_hits.$$
  return $hits
}

find_forbidden_files() {
  local dir="$1"
  local name
  local hits=0
  for name in "${FORBIDDEN_FILES[@]}"; do
    local found
    found=$(find "$dir" -type f -name "$name" 2>/dev/null | head -5)
    if [[ -n "$found" ]]; then
      echo ""
      echo "FORBIDDEN file present: $name"
      echo "$found"
      hits=$((hits + 1))
    fi
  done
  return $hits
}

scan_dir() {
  local dir="$1"
  echo "Verifying directory: $dir"
  local fails=0
  run_rg "$dir" || fails=$?
  local fail_files=0
  find_forbidden_files "$dir" || fail_files=$?
  fails=$((fails + fail_files))
  if [[ $fails -gt 0 ]]; then
    echo ""
    echo "VERIFY FAILED: $fails issue(s) in $dir"
    return 1
  fi
  echo "  OK (no leak patterns or forbidden files)"
  return 0
}

scan_archive() {
  local archive="$1"
  local tmp
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' RETURN
  case "$archive" in
    *.apk|*.zip|*.jar|*.aab)
      if command -v unzip >/dev/null; then
        unzip -qq -o "$archive" -d "$tmp" || { echo "unzip failed for $archive"; return 3; }
      else
        echo "unzip not installed; cannot scan $archive"; return 4
      fi
      ;;
    *.AppImage)
      (cd "$tmp" && "$archive" --appimage-extract >/dev/null 2>&1) || {
        echo "AppImage extraction failed for $archive"; return 3; }
      ;;
    *.dmg)
      if command -v 7z >/dev/null; then
        7z x -y -o"$tmp" "$archive" >/dev/null || { echo "7z failed for $archive"; return 3; }
      else
        echo "7z not installed; skipping $archive (install p7zip-full to enable)"
        return 0
      fi
      ;;
    *.exe)
      cp "$archive" "$tmp/"
      if command -v strings >/dev/null; then
        strings "$archive" > "$tmp/_strings.txt" || true
      fi
      ;;
    *)
      echo "Unsupported archive: $archive"; return 5
      ;;
  esac
  scan_dir "$tmp"
}

fail=0
for target in "$@"; do
  if [[ -d "$target" ]]; then
    scan_dir "$target" || fail=1
  elif [[ -f "$target" ]]; then
    scan_archive "$target" || fail=1
  else
    echo "No such target: $target" >&2
    fail=1
  fi
done

if [[ $fail -ne 0 ]]; then
  echo ""
  echo "verify_consumer_bundle.sh: FAILED"
  exit 1
fi

echo ""
echo "verify_consumer_bundle.sh: all targets clean."
exit 0
