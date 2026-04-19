#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 SYMBOL REPO_URL [BRANCH]" >&2
  exit 1
fi

SYMBOL="$1"; shift
REPO_URL="$1"; shift
BRANCH="${1:-}"

COINS_DIR="${COINS_DIR:-$HOME/coins}"
LOG_DIR="${LOG_DIR:-$HOME/pow-build-logs}"

mkdir -p "$COINS_DIR" "$LOG_DIR"

cd "$COINS_DIR"

if [ ! -d "$SYMBOL" ]; then
  git clone --recursive "$REPO_URL" "$SYMBOL" 2>&1 | tee "$LOG_DIR/${SYMBOL}.clone.log"
else
  cd "$SYMBOL"
  git pull 2>&1 | tee "$LOG_DIR/${SYMBOL}.pull.log"
  cd "$COINS_DIR"
fi

cd "$COINS_DIR/$SYMBOL"

if [ -n "$BRANCH" ]; then
  git checkout "$BRANCH" 2>&1 | tee -a "$LOG_DIR/${SYMBOL}.clone.log"
fi

make -j"$(nproc)" 2>&1 | tee "$LOG_DIR/${SYMBOL}.build.log"

# Install all built binaries (daemons + wallets) into /usr/local/bin
if [ -d build/Linux/release/bin ]; then
  sudo install build/Linux/release/bin/* /usr/local/bin/ 2>&1 | tee "$LOG_DIR/${SYMBOL}.install.log"
else
  # Fallback: install any *d and *wallet* binaries from project root
  sudo install ./*d /usr/local/bin/ 2>&1 | tee "$LOG_DIR/${SYMBOL}.install.log" || true
  sudo install ./*wallet* /usr/local/bin/ 2>&1 | tee -a "$LOG_DIR/${SYMBOL}.install.log" || true
fi
