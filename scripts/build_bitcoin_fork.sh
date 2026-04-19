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
  git clone "$REPO_URL" "$SYMBOL" 2>&1 | tee "$LOG_DIR/${SYMBOL}.clone.log"
else
  cd "$SYMBOL"
  git pull 2>&1 | tee "$LOG_DIR/${SYMBOL}.pull.log"
  cd "$COINS_DIR"
fi

cd "$COINS_DIR/$SYMBOL"

if [ -n "$BRANCH" ]; then
  git checkout "$BRANCH" 2>&1 | tee -a "$LOG_DIR/${SYMBOL}.clone.log"
fi

./autogen.sh 2>&1 | tee "$LOG_DIR/${SYMBOL}.autogen.log"
./configure --disable-tests --without-gui --prefix=/usr/local 2>&1 | tee "$LOG_DIR/${SYMBOL}.configure.log"
make -j"$(nproc)" 2>&1 | tee "$LOG_DIR/${SYMBOL}.build.log"

sudo make install 2>&1 | tee "$LOG_DIR/${SYMBOL}.install.log"
