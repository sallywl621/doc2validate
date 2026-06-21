from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import json


def md_cell(text: str) -> Dict[str, Any]:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": text.strip() + "\n",
    }


def code_cell(code: str) -> Dict[str, Any]:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": code.strip() + "\n",
    }


def make_notebook(cells: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "pygments_lexer": "ipython3",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def write_notebook(
    notebook: Dict[str, Any],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            notebook,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def python_literal(obj: Any) -> str:
    """
    Convert a Python object into Python source code.

    Do not use json.dumps() for notebook code-cell objects, because JSON
    null/true/false are not valid Python literals. repr() preserves
    None/True/False.
    """
    return repr(obj)


def status_emoji(status: str) -> str:
    return {
        "resolved": "✅",
        "ambiguous": "⚠️",
        "weak_match": "⚠️",
        "missing": "❌",
        "ungroundable": "🚫",
        "unsupported_non_file_claim": "🚫",
    }.get(status, "⚠️")


def warning_summary_text(warnings: List[Dict[str, Any]]) -> str:
    if not warnings:
        return "No warnings."

    parts = []

    for w in warnings:
        parts.append(
            f"- **{w.get('warning_type', 'unknown')}** "
            f"({w.get('severity', 'unknown')}): "
            f"{w.get('message', '')}"
        )

    return "\n".join(parts)


def collect_preview_targets(
    file_grounding: Dict[str, Any],
    max_candidates: int = 3,
) -> List[Dict[str, Any]]:
    """
    Decide which physical files the notebook should preview.

    We preview:
      - resolved matched files
      - weak_match matched files
      - ambiguous matched files

    We do not automatically preview missing format-only candidates, because
    loading same-format files may falsely imply that they are accepted mappings.
    """
    status = file_grounding.get("grounding_status")

    if status not in {"resolved", "weak_match", "ambiguous"}:
        return []

    matched = file_grounding.get("matched_physical_files") or []

    return matched[:max_candidates]


def make_setup_cell(
    article_id: str,
    logical_schema_path: Path,
    grounding_path: Path,
    human_annotations_path: Path,
    notebook_execution_path: Path,
) -> Dict[str, Any]:
    return code_cell(
        f"""
from pathlib import Path
import json
import pandas as pd
from datetime import datetime
from IPython.display import display

ARTICLE_ID = {python_literal(article_id)}
LOGICAL_SCHEMA_PATH = Path({python_literal(str(logical_schema_path))})
GROUNDING_PATH = Path({python_literal(str(grounding_path))})
HUMAN_ANNOTATIONS_PATH = Path({python_literal(str(human_annotations_path))})
NOTEBOOK_EXECUTION_PATH = Path({python_literal(str(notebook_execution_path))})

def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

logical_schema_raw = read_json(LOGICAL_SCHEMA_PATH)
grounding = read_json(GROUNDING_PATH)

preview_results = []
human_annotations = []

print("ARTICLE_ID:", ARTICLE_ID)
print("LOGICAL_SCHEMA_PATH:", LOGICAL_SCHEMA_PATH)
print("GROUNDING_PATH:", GROUNDING_PATH)
"""
    )


def make_helper_cell() -> Dict[str, Any]:
    return code_cell(
        """
def read_tabular_preview(path, max_rows=20):
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(path, nrows=max_rows)

    if suffix == ".tsv":
        return pd.read_csv(path, sep="\\t", nrows=max_rows)

    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, nrows=max_rows)

    if suffix == ".parquet":
        return pd.read_parquet(path).head(max_rows)

    raise ValueError(f"Unsupported preview suffix: {suffix}")


def preview_one_file(target, max_rows=20):
    path = Path(target["absolute_path"])
    result = {
        "article_id": ARTICLE_ID,
        "logical_file_id": target.get("logical_file_id"),
        "logical_name": target.get("logical_name"),
        "grounding_status": target.get("grounding_status"),
        "relative_path": target.get("relative_path"),
        "absolute_path": str(path),
        "match_score": target.get("match_score"),
        "match_type": target.get("match_type"),
        "preview_success": False,
        "error": "",
        "num_preview_rows": None,
        "num_preview_columns": None,
        "columns": [],
    }

    try:
        df = read_tabular_preview(path, max_rows=max_rows)
        result["preview_success"] = True
        result["num_preview_rows"] = int(df.shape[0])
        result["num_preview_columns"] = int(df.shape[1])
        result["columns"] = list(map(str, df.columns))
        display(df.head(max_rows))
    except Exception as exc:
        result["error"] = str(exc)
        print("Preview failed:", exc)

    preview_results.append(result)
    return result
"""
    )


def make_overview_markdown(
    article_id: str,
    grounding: Dict[str, Any],
) -> Dict[str, Any]:
    summary = grounding.get("summary", {})
    physical_summary = grounding.get("physical_summary", {})

    text = f"""
# Curatability Review Notebook

**Article ID:** `{article_id}`

This notebook is a curator-facing review artifact. It is generated from:

- documentation-derived logical schema: `dataset_structure.json`
- physical grounding result: `refined_artifact_grounding.json`

The notebook does not replace human stewardship. It packages machine-generated evidence, warnings, executable previews, and structured human annotation cells.

## Grounding summary

| Metric | Value |
|---|---:|
| Logical files | {summary.get("num_logical_files")} |
| File-grounding applicable claims | {summary.get("num_file_grounding_applicable")} |
| Resolved | {summary.get("num_resolved")} |
| Ambiguous | {summary.get("num_ambiguous")} |
| Weak match | {summary.get("num_weak_match")} |
| Missing | {summary.get("num_missing")} |
| Ungroundable | {summary.get("num_ungroundable")} |
| Unsupported non-file claims | {summary.get("num_unsupported_non_file_claim")} |
| Human review needed | {summary.get("num_human_review_needed")} |
| Grounding score | {summary.get("grounding_score")} |

## Physical inventory summary

| Metric | Value |
|---|---:|
| Effective artifact root exists | {physical_summary.get("effective_artifact_root_exists")} |
| Physical files | {physical_summary.get("num_physical_files")} |
| Tabular candidates | {physical_summary.get("num_tabular_candidates")} |
"""

    return md_cell(text)


def make_summary_tables_cell() -> Dict[str, Any]:
    return code_cell(
        """
file_groundings = grounding.get("file_groundings", [])
global_warnings = grounding.get("global_warnings", [])

file_rows = []
for g in file_groundings:
    file_rows.append({
        "logical_file_id": g.get("logical_file_id"),
        "logical_name": g.get("logical_name"),
        "documented_path_or_pattern": g.get("documented_path_or_pattern"),
        "expected_format": g.get("expected_format"),
        "role": g.get("role"),
        "num_documented_columns": g.get("num_documented_columns"),
        "grounding_status": g.get("grounding_status"),
        "human_review_needed": g.get("human_review_needed"),
        "matched_physical_files": " | ".join(
            m.get("relative_path", "")
            for m in g.get("matched_physical_files", [])
        ),
        "warning_types": ";".join(
            w.get("warning_type", "unknown")
            for w in g.get("warnings", [])
        ),
    })

file_grounding_df = pd.DataFrame(file_rows)
display(file_grounding_df)

warning_rows = []

for g in file_groundings:
    for w in g.get("warnings", []):
        warning_rows.append({
            "scope": "logical_file",
            "logical_file_id": g.get("logical_file_id"),
            "logical_name": g.get("logical_name"),
            "grounding_status": g.get("grounding_status"),
            "warning_type": w.get("warning_type"),
            "severity": w.get("severity"),
            "message": w.get("message"),
        })

for w in global_warnings:
    warning_rows.append({
        "scope": "global",
        "logical_file_id": "",
        "logical_name": "",
        "grounding_status": "",
        "warning_type": w.get("warning_type"),
        "severity": w.get("severity"),
        "message": w.get("message"),
    })

warning_df = pd.DataFrame(warning_rows)
display(warning_df)
"""
    )


def make_global_warnings_markdown(
    grounding: Dict[str, Any],
) -> Dict[str, Any]:
    warnings = grounding.get("global_warnings") or []

    if not warnings:
        return md_cell(
            """
## Global warnings

No global warnings.
"""
        )

    text = "## Global warnings\n\n"

    for w in warnings:
        text += (
            f"- **{w.get('warning_type', 'unknown')}** "
            f"({w.get('severity', 'unknown')}): "
            f"{w.get('message', '')}\n"
        )

        if w.get("sources"):
            text += f"  - Sources: `{', '.join(w.get('sources'))}`\n"

    return md_cell(text)


def make_file_grounding_markdown(
    file_grounding: Dict[str, Any],
) -> Dict[str, Any]:
    status = file_grounding.get("grounding_status", "unknown")
    emoji = status_emoji(status)

    matched = file_grounding.get("matched_physical_files") or []
    candidates = file_grounding.get("candidate_physical_files") or []

    matched_text = (
        "\n".join(
            f"- `{m.get('relative_path')}` "
            f"(score={m.get('match_score')}, type={m.get('match_type')})"
            for m in matched
        )
        if matched
        else "No accepted physical match."
    )

    candidate_text = (
        "\n".join(
            f"- `{c.get('relative_path')}` "
            f"(score={c.get('match_score')}, type={c.get('match_type')})"
            for c in candidates[:10]
        )
        if candidates
        else "No candidates."
    )

    warnings = file_grounding.get("warnings") or []

    text = f"""
## {emoji} Logical file `{file_grounding.get('logical_file_id')}` — `{file_grounding.get('logical_name')}`

| Field | Value |
|---|---|
| Documented path or pattern | `{file_grounding.get('documented_path_or_pattern')}` |
| Expected format | `{file_grounding.get('expected_format')}` |
| Role | `{file_grounding.get('role')}` |
| Grounding status | **{status}** |
| Human review needed | `{file_grounding.get('human_review_needed')}` |
| Documented columns | `{file_grounding.get('num_documented_columns')}` |

### Matched physical files

{matched_text}

### Candidate physical files

{candidate_text}

### Warnings

{warning_summary_text(warnings)}
"""

    return md_cell(text)


def make_preview_cell(
    file_grounding: Dict[str, Any],
) -> Dict[str, Any]:
    targets = []

    for t in collect_preview_targets(file_grounding):
        targets.append(
            {
                "logical_file_id": file_grounding.get("logical_file_id"),
                "logical_name": file_grounding.get("logical_name"),
                "grounding_status": file_grounding.get("grounding_status"),
                "relative_path": t.get("relative_path"),
                "absolute_path": t.get("absolute_path"),
                "match_score": t.get("match_score"),
                "match_type": t.get("match_type"),
            }
        )

    if not targets:
        return code_cell(
            f"""
# No automatic preview for {file_grounding.get("logical_file_id")}
# Status: {file_grounding.get("grounding_status")}
# Reason: unresolved, missing, unsupported, or not safely previewable.
"""
        )

    return code_cell(
        f"""
preview_targets = {python_literal(targets)}

for target in preview_targets:
    print("\\n" + "=" * 80)
    print("Logical file:", target["logical_file_id"], target["logical_name"])
    print("Grounding status:", target["grounding_status"])
    print("Physical file:", target["relative_path"])
    print("Match:", target["match_score"], target["match_type"])
    preview_one_file(target, max_rows=10)
"""
    )


def make_annotation_cell(
    review_target: Dict[str, Any],
    file_grounding_lookup: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    logical_file_id = review_target.get("logical_file_id")
    g = file_grounding_lookup.get(logical_file_id, {})

    candidates = [
        c.get("relative_path")
        for c in g.get("candidate_physical_files", [])[:10]
    ]

    matched = [
        m.get("relative_path")
        for m in g.get("matched_physical_files", [])
    ]

    annotation_template = {
        "annotation_id": f"ann_{logical_file_id}_grounding",
        "annotation_scope": "grounding",
        "target_id": logical_file_id,
        "target_type": "logical_file",
        "logical_name": review_target.get("logical_name"),
        "system_status": review_target.get("grounding_status"),
        "system_question": review_target.get("question"),
        "default_action": review_target.get("default_action"),
        "candidate_physical_files": candidates,
        "system_matched_physical_files": matched,

        # Curator-editable fields:
        "annotation_type": "",
        "human_decision": "",
        "selected_physical_file": "",
        "comment": "",
        "curator_confidence": "",
        "timestamp": "",
    }

    allowed_types = [
        "accept_system_assessment",
        "override_grounding",
        "manual_file_mapping",
        "mark_missing",
        "mark_ambiguous",
        "exclude_from_file_validation",
        "request_supplementary_materials",
        "needs_second_review",
    ]

    return code_cell(
        f"""
# Human annotation target: {logical_file_id}
# Allowed annotation_type values:
# {", ".join(allowed_types)}
#
# Edit the curator-editable fields below before saving annotations.

annotation = {python_literal(annotation_template)}

# Example edits:
# annotation["annotation_type"] = "manual_file_mapping"
# annotation["human_decision"] = "map_to_physical_file"
# annotation["selected_physical_file"] = "example.csv"
# annotation["comment"] = "Curator explanation here."
# annotation["curator_confidence"] = "high"

annotation["timestamp"] = datetime.now().isoformat()
human_annotations.append(annotation)
annotation
"""
    )


def make_final_decision_cell() -> Dict[str, Any]:
    template = {
        "annotation_id": "ann_final_decision",
        "annotation_scope": "final_decision",
        "target_id": "article",
        "target_type": "dataset",
        "system_grounding_score": None,
        "system_recommendation": "",
        "annotation_type": "",
        "human_final_decision": "",
        "comment": "",
        "curator_confidence": "",
        "timestamp": "",
    }

    return code_cell(
        f"""
# Final curator decision
#
# Suggested annotation_type values:
# final_accept_for_ingest
# final_reject_dataset
# request_supplementary_materials
# needs_second_review

final_decision = {python_literal(template)}

final_decision["system_grounding_score"] = grounding.get("summary", {{}}).get("grounding_score")

# Edit these fields:
# final_decision["annotation_type"] = "needs_second_review"
# final_decision["human_final_decision"] = "request_supplementary_materials"
# final_decision["comment"] = "Reason for final decision."
# final_decision["curator_confidence"] = "high"

final_decision["timestamp"] = datetime.now().isoformat()
human_annotations.append(final_decision)
final_decision
"""
    )


def make_save_outputs_cell() -> Dict[str, Any]:
    return code_cell(
        """
HUMAN_ANNOTATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
HUMAN_ANNOTATIONS_PATH.write_text(
    json.dumps(
        {
            "article_id": ARTICLE_ID,
            "created_at": datetime.now().isoformat(),
            "annotations": human_annotations,
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)

runtime_report = {
    "article_id": ARTICLE_ID,
    "created_at": datetime.now().isoformat(),
    "grounding_summary": grounding.get("summary", {}),
    "num_preview_results": len(preview_results),
    "num_preview_success": sum(1 for r in preview_results if r.get("preview_success")),
    "num_preview_failed": sum(1 for r in preview_results if not r.get("preview_success")),
    "preview_results": preview_results,
}

NOTEBOOK_EXECUTION_PATH.parent.mkdir(parents=True, exist_ok=True)
NOTEBOOK_EXECUTION_PATH.write_text(
    json.dumps(runtime_report, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print("Saved human annotations:", HUMAN_ANNOTATIONS_PATH)
print("Saved notebook runtime report:", NOTEBOOK_EXECUTION_PATH)
"""
    )


class CuratabilityNotebookBuilder:
    """
    Build a curator-facing notebook from logical schema + physical grounding.

    This notebook is a review artifact:
      - it displays logical claims
      - shows physical grounding evidence
      - previews matched/candidate files
      - creates structured human annotation templates
      - saves human_annotations.json and notebook_execution.json when run
    """

    def build(
        self,
        article_id: str,
        logical_schema_path: Path,
        grounding_path: Path,
        human_annotations_path: Path,
        notebook_execution_path: Path,
        grounding: Dict[str, Any],
    ) -> Dict[str, Any]:
        cells: List[Dict[str, Any]] = []

        cells.append(
            make_overview_markdown(
                article_id=article_id,
                grounding=grounding,
            )
        )

        cells.append(
            make_setup_cell(
                article_id=article_id,
                logical_schema_path=logical_schema_path,
                grounding_path=grounding_path,
                human_annotations_path=human_annotations_path,
                notebook_execution_path=notebook_execution_path,
            )
        )

        cells.append(make_helper_cell())

        cells.append(
            md_cell(
                """
# Summary tables

The following tables summarize logical file grounding, warnings, and review needs.
"""
            )
        )

        cells.append(make_summary_tables_cell())

        cells.append(make_global_warnings_markdown(grounding))

        file_groundings = grounding.get("file_groundings") or []

        cells.append(
            md_cell(
                """
# File-level grounding review

Each section below corresponds to one documentation-derived logical file claim.
"""
            )
        )

        for g in file_groundings:
            cells.append(make_file_grounding_markdown(g))
            cells.append(make_preview_cell(g))

        human_review_targets = grounding.get("human_review_targets") or []
        file_grounding_lookup = {
            g.get("logical_file_id"): g
            for g in file_groundings
        }

        cells.append(
            md_cell(
                """
# Human annotation targets

Edit the annotation cells below to record curator judgment. These annotations are saved to `human_annotations.json`.
"""
            )
        )

        for target in human_review_targets:
            cells.append(
                make_annotation_cell(
                    review_target=target,
                    file_grounding_lookup=file_grounding_lookup,
                )
            )

        cells.append(
            md_cell(
                """
# Final curator decision

Record the final curator decision for this dataset package.
"""
            )
        )

        cells.append(make_final_decision_cell())

        cells.append(
            md_cell(
                """
# Save review outputs

Run the following cell after editing human annotations.
"""
            )
        )

        cells.append(make_save_outputs_cell())

        return make_notebook(cells)
