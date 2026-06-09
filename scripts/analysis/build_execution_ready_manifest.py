import pandas as pd
from pathlib import Path

RUN_NAME = "scidata_4293"

manifest_path = Path(f"results/runs/{RUN_NAME}/manifests/artifact_download_manifest.csv")
structured_docs_root = Path("data/structured_docs")
output_dir = Path(f"results/runs/{RUN_NAME}/analysis")
output_dir.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(manifest_path)
success_df = df[df["status"] == "success"].copy()

rows = []
for _, row in success_df.iterrows():
    article_id = row["article_id"]
    schema_path = structured_docs_root / article_id / "dataset_structure.json"

    rows.append({
        "article_id": article_id,
        "download_status": row["status"],
        "artifact_path": row.get("artifact_path", None),
        "dataset_structure_exists": schema_path.exists(),
        "dataset_structure_path": str(schema_path) if schema_path.exists() else None,
    })

ready_df = pd.DataFrame(rows)

execution_ready_df = ready_df[ready_df["dataset_structure_exists"]].copy()

execution_ready_df.to_csv(output_dir / "execution_ready_manifest.csv", index=False)

with open(output_dir / "execution_ready_article_ids.txt", "w") as f:
    for aid in execution_ready_df["article_id"]:
        f.write(f"{aid}\n")

print(f"download success: {len(success_df)}")
print(f"execution-ready now: {len(execution_ready_df)}")
print(f"waiting for dataset_structure: {len(success_df) - len(execution_ready_df)}")
