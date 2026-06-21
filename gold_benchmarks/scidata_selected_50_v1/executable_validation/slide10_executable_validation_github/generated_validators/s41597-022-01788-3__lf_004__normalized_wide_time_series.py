import argparse
import json
from pathlib import Path
from runtime.validation_runtime import run_validation


SPEC = {
  "article_id": "s41597-022-01788-3",
  "logical_file_id": "lf_004",
  "logical_name": "normalized_wide_time_series",
  "observed_suffix": ".csv",
  "artifact_relative_path": "s41597-022-01788-3/artifact/github/github_github.com__BioRDM_COVID-Wastewater-Scotland/COVID-Wastewater-Scotland-main/data/norm_prevalence_timeseries.csv",
  "target_columns": [
    "2020-05-28",
    "Health_Board",
    "Site"
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
