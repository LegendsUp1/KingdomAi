#!/usr/bin/env bash
# Run CQL offline RL training.
# Usage:
#   ./scripts/run_training.sh config/training.yaml data/train.npz data/val.npz

set -euo pipefail

CONFIG=$1
TRAIN_DATA=$2
VAL_DATA=${3:-}
RESUME=${4:-}

if [ -z "${VAL_DATA}" ]; then
  python -m training.train --config "${CONFIG}" --train-data "${TRAIN_DATA}" ${RESUME:+--resume "${RESUME}"}
else
  python -m training.train --config "${CONFIG}" --train-data "${TRAIN_DATA}" --val-data "${VAL_DATA}" ${RESUME:+--resume "${RESUME}"}
fi
