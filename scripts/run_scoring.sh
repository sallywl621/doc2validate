#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}"

cd "${PROJECT_ROOT}"

RUN_NAME="${1:-}"

if [ -z "${RUN_NAME}" ]; then
  echo "Usage: bash scripts/run_scoring.sh <run_name>"
  echo "Example: bash scripts/run_scoring.sh scidata_182"
  exit 1
fi

RUN_DIR="results/runs/${RUN_NAME}"
LOG_DIR="${RUN_DIR}/logs"
MANIFEST_DIR="${RUN_DIR}/manifests"

mkdir -p "${LOG_DIR}"
mkdir -p "${MANIFEST_DIR}"

echo "Run name: ${RUN_NAME}"
echo "Project root: ${PROJECT_ROOT}"
echo "Scoring manifest: ${MANIFEST_DIR}/scoring_manifest.csv"
echo "Scoring log: ${LOG_DIR}/scoring.log"

python src/scoring/run_scoring.py \
  --run-name "${RUN_NAME}" \
  --overwrite \
  --manifest "${MANIFEST_DIR}/scoring_manifest.csv" \
  --log-path "${LOG_DIR}/scoring.log"

echo "Scoring finished."
