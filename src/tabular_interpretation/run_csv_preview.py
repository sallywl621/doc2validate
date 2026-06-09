from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from src.tabular_interpretation.csv_preview_builder import save_csv_previews
from src.utils.config import DATA_DIR, ensure_run_dirs
from src.utils.io import write_manifest


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument("--run-name", required=True)
    parser.add_argument("--article-id", required=True)
    parser.add_argument("--n-rows", type=int, default=5)
    parser.add_argument("--manifest", type=Path)

    args = parser.parse_args()

    dirs = ensure_run_dirs(args.run_name)

    article_id = args.article_id

    artifact_root = DATA_DIR / "downloaded_artifacts" / article_id

    output_dir = (
        dirs["run_dir"]
        / "tabular_interpretation"
        / article_id
    )

    output_path = output_dir / "csv_previews.json"

    started = datetime.now().isoformat()
    status = "unknown"
    error = ""
    csv_file_count = 0

    try:
        payload = save_csv_previews(
            article_id=article_id,
            artifact_root=artifact_root,
            output_path=output_path,
            n_rows=args.n_rows,
        )

        csv_file_count = payload.get(
            "csv_file_count",
            0,
        )

        status = "success"

    except Exception as exc:
        status = "error"
        error = str(exc)

    rows = [
        {
            "article_id": article_id,
            "status": status,
            "csv_file_count": csv_file_count,
            "output_path": str(output_path),
            "error": error,
            "started_at": started,
            "finished_at": datetime.now().isoformat(),
        }
    ]

    out_manifest = (
        args.manifest
        or dirs["manifests_dir"] / "csv_preview_manifest.csv"
    )

    write_manifest(
        rows,
        out_manifest,
    )

    print(f"{article_id}: {status}, csv_file_count={csv_file_count}")
    print(output_path)


if __name__ == "__main__":
    main()
