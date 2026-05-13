#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}"

cd "${PROJECT_ROOT}"

RUN_NAME="${1:-}"

if [ -z "${RUN_NAME}" ]; then
  echo "Usage: bash scripts/run_artifact_downloader.sh <run_name>"
  echo "Example: bash scripts/run_artifact_downloader.sh scidata_182"
  exit 1
fi

RUN_DIR="results/runs/${RUN_NAME}"
LOG_DIR="${RUN_DIR}/logs"
MANIFEST_DIR="${RUN_DIR}/manifests"

mkdir -p "${LOG_DIR}"
mkdir -p "${MANIFEST_DIR}"
mkdir -p "data/downloaded_artifacts"

echo "Run name: ${RUN_NAME}"
echo "Project root: ${PROJECT_ROOT}"
echo "Downloaded artifacts root: ${PROJECT_ROOT}/data/downloaded_artifacts"
echo "Manifest dir: ${MANIFEST_DIR}"
echo "Log dir: ${LOG_DIR}"

python src/artifact_downloading/run_artifact_downloader.py \
  --run-name "${RUN_NAME}" \
  --manifest "${MANIFEST_DIR}/artifact_download_manifest.csv" \
  --log-path "${LOG_DIR}/artifact_downloader.log"

echo "Artifact downloading finished."
echo "Manifest:"
echo "  ${MANIFEST_DIR}/artifact_download_manifest.csv"
echo "Log:"
echo "  ${LOG_DIR}/artifact_downloader.log"
echo "Downloaded artifacts:"
echo "  data/downloaded_artifacts/"
