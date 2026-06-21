from __future__ import annotations

from typing import Any, Dict

import numpy as np

from src.scoring.scoring_constants import SCS_VERSION


def org_score(org_type: str) -> float:
    org_type = (org_type or "unknown").lower()

    if org_type == "flat":
        return 20.0
    if org_type == "hierarchical":
        return 18.0
    if org_type in {"mixed", "sharded"}:
        return 12.0
    if org_type == "api_based":
        return 6.0

    return 0.0


def compute_scs_from_features(features: Dict[str, Any]) -> Dict[str, Any]:
    n_tabular = int(features.get("n_tabular_files") or 0)
    n_supported_tabular = int(features.get("n_supported_tabular_files") or 0)
    tabular_with_columns = int(features.get("tabular_with_columns") or 0)

    has_any_columns = bool(features.get("has_any_columns"))
    n_known_paths = int(features.get("n_known_paths") or 0)
    n_pattern_paths = int(features.get("n_pattern_paths") or 0)

    has_repository_docs = bool(features.get("has_repository_docs"))
    structure_confidence = float(features.get("structure_confidence") or 0.0)

    generation_success = bool(features.get("generation_success"))
    selected_file_count = int(features.get("selected_file_count") or 0)
    has_expected_columns = bool(features.get("has_expected_columns_in_codegen"))
    has_access_restriction_warning = bool(
        features.get("has_access_restriction_warning")
    )

    org = org_score(features.get("organization_type", "unknown"))

    tabular = 25.0 * min(1.0, n_supported_tabular / 2.0)

    column = 20.0 if has_any_columns else 0.0

    ratio = tabular_with_columns / max(n_tabular, 1)
    schema = 15.0 * ratio

    if n_known_paths > 0:
        path = 10.0
    elif n_pattern_paths > 0:
        path = 6.0
    else:
        path = 0.0

    repo = 10.0 if has_repository_docs else 0.0

    conf = 10.0 * float(np.clip(structure_confidence, 0.0, 1.0))

    generation = 0.0

    if generation_success:
        generation += 6.0

    if selected_file_count > 0:
        generation += 2.0

    if has_expected_columns:
        generation += 2.0

    if has_access_restriction_warning:
        generation -= 3.0

    generation = max(0.0, min(10.0, generation))

    subscores = {
        "organization": org,
        "tabular": tabular,
        "columns": column,
        "schema": schema,
        "path": path,
        "repository": repo,
        "confidence": conf,
        "generation": generation,
    }

    raw_score = sum(subscores.values())

    scs = float(np.clip(raw_score, 0.0, 110.0))

    normalized_scs = scs / 110.0

    return {
        "scs_version": SCS_VERSION,
        "scs": scs,
        "scs_normalized": normalized_scs,
        "subscores": subscores,
    }
