from pathlib import Path
import json
import pandas as pd


ROOT = Path(
    "results/runs/scidata_4293/artifact_grounding"
)

rows = []


def classify_failure(reason: str) -> str:
    r = (reason or "").lower()

    # 1. inventory empty
    if "no physical candidate files provided" in r:
        return "inventory_absent"

    # 2. unsupported modality
    unsupported_terms = [
        "jpeg",
        "image",
        "nifti",
        "dicom",
        "binary",
        "neo4j",
        ".dump",
        "zip archive",
        "rdf",
    ]
    if any(x in r for x in unsupported_terms):
        return "unsupported_modality"

    # 3. repository missing artifact
    missing_terms = [
        "not found",
        "no file named",
        "no file matching",
        "not present",
        "no csv files present",
        "expected",
    ]
    if any(x in r for x in missing_terms):
        return "repository_missing"

    # 4. directory-level / family abstraction
    abstraction_terms = [
        "directory",
        "collection",
        "multiple files",
        "homogeneous",
        "family",
    ]
    if any(x in r for x in abstraction_terms):
        return "directory_family_abstraction"

    # 5. ambiguity
    ambiguity_terms = [
        "ambiguous",
        "multiple",
        "overlapping purpose",
        "require inference",
    ]
    if any(x in r for x in ambiguity_terms):
        return "semantic_ambiguity"

    return "other"


for p in ROOT.glob("*/grounding_manifest.json"):

    data = json.loads(p.read_text())

    aid = data["article_id"]

    resolutions = (
        data
        .get("result", {})
        .get("resolutions", [])
    )

    for r in resolutions:

        status = r.get(
            "grounding_status"
        )

        if status == "resolved":
            continue

        reason = r.get("reason")

        rows.append({
            "article_id": aid,
            "logical_name":
                r.get("logical_name"),

            "status": status,

            "confidence":
                r.get(
                    "confidence",
                    0,
                ),

            "reason": reason,

            "failure_category":
                classify_failure(
                    reason
                ),
        })

df = pd.DataFrame(rows)

print("\n=== FAILURE TAXONOMY ===")
print(
    df.failure_category
    .value_counts()
)

print("\n=== BY STATUS ===")
print(
    pd.crosstab(
        df.failure_category,
        df.status,
    )
)

print("\n=== SAMPLE ===")
print(
    df[
        [
            "article_id",
            "logical_name",
            "status",
            "failure_category",
            "reason",
        ]
    ]
    .head(50)
    .to_string(index=False)
)

out = Path(
    "results/runs/scidata_4293/analysis"
)

out.mkdir(
    parents=True,
    exist_ok=True,
)

csv_path = (
    out
    / "grounding_failure_taxonomy.csv"
)

df.to_csv(
    csv_path,
    index=False,
)

print(
    "\nSaved:",
    csv_path
)
