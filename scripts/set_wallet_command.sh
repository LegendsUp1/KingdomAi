#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 SYMBOL CMD..." >&2
  exit 1
fi

SYMBOL="$1"; shift
WALLET_JSON="config/wallet_external.json"

tmp="$(mktemp)"
# Build JSON array of command args
cmd_json=$(printf '%s\n' "$@" | jq -R . | jq -s .)

jq --arg sym "$SYMBOL" --argjson cmd "$cmd_json" '
  .[$sym].command = $cmd
' "$WALLET_JSON" > "$tmp"

mv "$tmp" "$WALLET_JSON"
echo "Updated $WALLET_JSON for $SYMBOL"
