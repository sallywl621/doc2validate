#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}"

cd "${PROJECT_ROOT}"

RUN_NAME="${1:-}"
TOP_K="${2:-2}"

if [ -z "${RUN_NAME}" ]; then
  echo "Usage: bash scripts/run_code_generation.sh <run_name> [top_k]"
  echo "Example: bash scripts/run_code_generation.sh scidata_182 2"
  exit 1
fi

RUN_DIR="results/runs/${RUN_NAME}"
LOG_DIR="${RUN_DIR}/logs"
MANIFEST_DIR="${RUN_DIR}/manifests"
GENERATED_CODE_DIR="${RUN_DIR}/generated_code"

mkdir -p "${LOG_DIR}"
mkdir -p "${MANIFEST_DIR}"
mkdir -p "${GENERATED_CODE_DIR}"

echo "Run name: ${RUN_NAME}"
echo "Project root: ${PROJECT_ROOT}"
echo "Top-k selected files: ${TOP_K}"
echo "Generated code dir: ${GENERATED_CODE_DIR}"
echo "Code generation manifest: ${MANIFEST_DIR}/code_generation_manifest.csv"
echo "Code generation log: ${LOG_DIR}/code_generation.log"

python src/code_generation/run_code_generation.py \
  --run-name "${RUN_NAME}" \
  --top-k "${TOP_K}" \
  --overwrite \
  --manifest "${MANIFEST_DIR}/code_generation_manifest.csv" \
  --log-path "${LOG_DIR}/code_generation.log"

echo "Code generation finished."
