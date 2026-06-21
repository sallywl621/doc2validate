from __future__ import annotations

from pathlib import Path
from typing import Dict, List
import datetime as dt

import pandas as pd

HUMAN_ERROR_SOURCE_OPTIONS = [
    "",
    "documentation_artifact_mismatch",
    "llm_extraction_error",
    "grounding_algorithm_error",
    "insufficient_documentation",
    "acceptable_variant",
    "unsupported_or_non_file_claim",
    "artifact_access_or_unpacking_issue",
    "other_uncertain",
]

HUMAN_ACTION_OPTIONS = [
    "",
    "accept_system_assessment",
    "override_grounding",
    "manual_file_mapping",
    "mark_missing",
    "mark_ambiguous",
    "accept_variant_mapping",
    "exclude_from_file_validation",
    "request_supplementary_materials",
    "needs_second_review",
]


def _now() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat()


def _read_existing(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path, dtype=str).fillna("")
    return pd.DataFrame()


def _upsert(path: Path, row: Dict[str, str], key_cols: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    old = _read_existing(path)
    new = pd.DataFrame([row])
    if old.empty:
        new.to_csv(path, index=False)
        return
    for c in new.columns:
        if c not in old.columns:
            old[c] = ""
    for c in old.columns:
        if c not in new.columns:
            new[c] = ""
    mask = pd.Series([True] * len(old))
    for c in key_cols:
        mask &= old[c].astype(str) == str(row.get(c, ""))
    if mask.any():
        old.loc[mask, old.columns] = new[old.columns].iloc[0].values
        old.to_csv(path, index=False)
    else:
        pd.concat([old, new[old.columns]], ignore_index=True).to_csv(path, index=False)


def launch_annotation_ui(target_csv: str, output_csv: str, start_index: int = 0) -> None:
    """
    Jupyter UI for annotation target CSVs produced by
    export_presentation_grounding_manifests.py.

    Usage in notebook:
        from src.human_annotation.interactive_annotation_ui import launch_annotation_ui
        launch_annotation_ui(
            target_csv=".../presentation_grounding_annotation_targets.csv",
            output_csv=".../presentation_grounding_human_annotations.csv",
        )
    """
    import ipywidgets as widgets
    from IPython.display import display

    target_path = Path(target_csv)
    output_path = Path(output_csv)
    df = pd.read_csv(target_path, dtype=str).fillna("")
    if df.empty:
        print("No annotation targets found.")
        return

    state = {"idx": max(0, min(start_index, len(df) - 1))}

    title = widgets.HTML()
    evidence = widgets.HTML()
    error_source = widgets.Dropdown(options=HUMAN_ERROR_SOURCE_OPTIONS, description="Source:", layout=widgets.Layout(width="95%"))
    action = widgets.Dropdown(options=HUMAN_ACTION_OPTIONS, description="Action:", layout=widgets.Layout(width="95%"))
    annotator = widgets.Text(description="Annotator:", layout=widgets.Layout(width="60%"))
    notes = widgets.Textarea(description="Notes:", layout=widgets.Layout(width="95%", height="110px"))
    status = widgets.HTML()
    save_btn = widgets.Button(description="Save", button_style="success")
    prev_btn = widgets.Button(description="Previous")
    next_btn = widgets.Button(description="Next")
    skip_btn = widgets.Button(description="Skip")

    fields = [
        "article_id", "logical_file_id", "logical_name", "documented_path_or_pattern",
        "expected_format", "role", "matched_or_candidate_path", "grounding_status",
        "format_status", "role_status", "column_status", "column_coverage",
        "failed_dimensions", "uncertain_dimensions", "suggested_human_question",
    ]

    def html_escape(x: str) -> str:
        return str(x).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def render_row() -> None:
        row = df.iloc[state["idx"]]
        title.value = f"<h3>Annotation target {state['idx'] + 1} / {len(df)}</h3>"
        parts = []
        for f in fields:
            if f in row.index and str(row.get(f, "")):
                parts.append(f"<p><b>{f}</b>: {html_escape(row.get(f, ''))}</p>")
        evidence.value = "<div style='line-height:1.35'>" + "\n".join(parts) + "</div>"
        error_source.value = ""
        action.value = ""
        notes.value = ""
        status.value = ""

    def current_key(row: Dict[str, str]) -> List[str]:
        return ["article_id", "logical_file_id", "annotation_scope"]

    def save_current(_=None) -> None:
        row = df.iloc[state["idx"]].to_dict()
        row["human_error_source"] = error_source.value
        row["human_action"] = action.value
        row["human_notes"] = notes.value
        row["annotator"] = annotator.value
        row["annotation_timestamp"] = _now()
        _upsert(output_path, row, current_key(row))
        status.value = f"<span style='color:green'>Saved to {output_path}</span>"

    def go_prev(_=None) -> None:
        save_current()
        state["idx"] = max(0, state["idx"] - 1)
        render_row()

    def go_next(_=None) -> None:
        save_current()
        state["idx"] = min(len(df) - 1, state["idx"] + 1)
        render_row()

    def skip(_=None) -> None:
        state["idx"] = min(len(df) - 1, state["idx"] + 1)
        render_row()

    save_btn.on_click(save_current)
    prev_btn.on_click(go_prev)
    next_btn.on_click(go_next)
    skip_btn.on_click(skip)

    display(widgets.VBox([
        title,
        evidence,
        widgets.HTML("<hr>"),
        error_source,
        action,
        annotator,
        notes,
        widgets.HBox([prev_btn, save_btn, next_btn, skip_btn]),
        status,
    ]))
    render_row()
