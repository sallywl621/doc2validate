import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-root", required=True)
    parser.add_argument("--out-dir", default="rerun_outputs")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    validators = sorted((root / "generated_validators").glob("*.py"))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ok = 0
    failed = 0

    for v in validators:
        out_json = out_dir / (v.stem + ".json")
        cmd = [
            sys.executable,
            str(v),
            "--benchmark-root",
            args.benchmark_root,
            "--out-json",
            str(out_json),
        ]
        r = subprocess.run(cmd)
        if r.returncode == 0:
            ok += 1
        else:
            failed += 1

    summary = {
        "validators": len(validators),
        "success": ok,
        "failed": failed,
        "out_dir": str(out_dir),
    }

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
