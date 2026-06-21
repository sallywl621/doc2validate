import argparse
import json
from pathlib import Path
from runtime.validation_runtime import run_validation


SPEC = {
  "article_id": "s41597-024-03190-7",
  "logical_file_id": "lf_003",
  "logical_name": "structure_type_classification_output",
  "observed_suffix": ".xlsx",
  "artifact_relative_path": "s41597-024-03190-7/artifact/github/github_github.com__TomerFishman_MaterialIntensityEstimator/MaterialIntensityEstimator-main/data_input_and_ml_processing/buildings_v2-structure_type_ML.xlsx",
  "target_columns": [
    "concrete",
    "steel"
  ]
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-root", required=True)
    parser.add_argument("--out-json", default=None)
    args = parser.parse_args()

    result = run_validation(SPEC, args.benchmark_root)

    if args.out_json:
        out_path = Path(args.out_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    else:
        print(json.dumps(result, indent=2))

    if not result.get("load_success"):
        raise SystemExit(2)

    columns = result.get("columns", [])
    if not columns:
        raise SystemExit(3)

    if not all(c.get("profile_success") for c in columns):
        raise SystemExit(4)


if __name__ == "__main__":
    main()
