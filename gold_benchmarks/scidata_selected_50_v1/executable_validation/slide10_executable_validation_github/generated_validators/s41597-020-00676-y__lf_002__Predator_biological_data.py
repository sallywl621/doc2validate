import argparse
import json
from pathlib import Path
from runtime.validation_runtime import run_validation


SPEC = {
  "article_id": "s41597-020-00676-y",
  "logical_file_id": "lf_002",
  "logical_name": "Predator biological data",
  "observed_suffix": ".csv",
  "artifact_relative_path": "s41597-020-00676-y/artifact/github/github_github.com__mcarolinegraham_North_Pacific_Marine_Salmon_Diet_Database/North_Pacific_Marine_Salmon_Diet_Database-master/data/predator_biological_data.csv",
  "target_columns": [
    "predator_life_stage",
    "predator_subsample_id"
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
