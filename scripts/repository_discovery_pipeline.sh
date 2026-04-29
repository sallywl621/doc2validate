#!/usr/bin/env bash
set -euo pipefail

RUN_NAME="${1:-}"

if [ -z "${RUN_NAME}" ]; then
  echo "Usage: bash scripts/repository_discovery_pipeline.sh <run_name>"
  echo "Example: bash scripts/repository_discovery_pipeline.sh scidata_test_10"
  exit 1
fi

RUN_DIR="results/runs/${RUN_NAME}"
LOG_DIR="${RUN_DIR}/logs"
MANIFEST_DIR="${RUN_DIR}/manifests"

mkdir -p "${LOG_DIR}"
mkdir -p "${MANIFEST_DIR}"

echo "Run name: ${RUN_NAME}"
echo "Run directory: ${RUN_DIR}"

python src/extraction/run_dataset_extraction.py \
  --run-name "${RUN_NAME}" \
  --manifest "${MANIFEST_DIR}/dataset_extraction_manifest.csv" \
  --log-path "${LOG_DIR}/dataset_extraction.log"

python src/extraction/run_code_repository_extraction.py \
  --run-name "${RUN_NAME}" \
  --manifest "${MANIFEST_DIR}/code_repository_extraction_manifest.csv" \
  --log-path "${LOG_DIR}/code_repository_extraction.log"

python src/validation/run_url_validation.py \
  --run-name "${RUN_NAME}" \
  --manifest "${MANIFEST_DIR}/url_validation_manifest.csv" \
  --log-path "${LOG_DIR}/url_validation.log"

python src/repository_crawling/run_repository_crawler.py \
  --run-name "${RUN_NAME}" \
  --manifest "${MANIFEST_DIR}/repository_crawl_manifest.csv" \
  --log-path "${LOG_DIR}/repository_crawler.log"

echo "Repository discovery pipeline finished."
echo "Outputs:"
echo "  ${MANIFEST_DIR}/dataset_extraction_manifest.csv"
echo "  ${MANIFEST_DIR}/code_repository_extraction_manifest.csv"
echo "  ${MANIFEST_DIR}/url_validation_manifest.csv"
echo "  ${MANIFEST_DIR}/repository_crawl_manifest.csv"
echo "  ${LOG_DIR}/"
