#!/usr/bin/env bash
set -euo pipefail

RUN_NAME="${1:-}"

if [ -z "$RUN_NAME" ]; then
  echo "Usage: bash scripts/corpus_builder_pipeline.sh <run_name>"
  echo "Example: bash scripts/corpus_builder_pipeline.sh scidata_test_10"
  exit 1
fi

RUN_DIR="results/runs/${RUN_NAME}"
LOG_DIR="${RUN_DIR}/logs"
MANIFEST_DIR="${RUN_DIR}/manifests"

mkdir -p "${LOG_DIR}"
mkdir -p "${MANIFEST_DIR}"
mkdir -p "data/raw_pdfs"
mkdir -p "data/structured_docs"

echo "Run name: ${RUN_NAME}"
echo "Run directory: ${RUN_DIR}"


python src/preprocessing/preprocess.py \
  --manifest "${MANIFEST_DIR}/pdf_manifest.csv" \
  --structured-output-dir data/structured_docs \
  --status-csv "${MANIFEST_DIR}/preprocess_status.csv" \
  --log-path "${LOG_DIR}/preprocess.log"

echo "Corpus builder pipeline finished."
echo "Outputs:"
echo "  ${MANIFEST_DIR}/preprocess_status.csv"
echo "  ${LOG_DIR}/"
