# Physical grounding

This module contains the current selected-50 physical grounding implementation used for the grounding v2 hardfilter 0618 results.

It maps documentation-derived logical file and column claims to observed physical repository artifacts, exports grounding manifests, and produces file-, loader/header-, and column-level review targets.

Current implementation:

- `grounder_v2_hardfilter.py`
- `run_grounding_v2_hardfilter.py`
- `export_grounding_v2_hardfilter_manifests.py`
- `interactive_annotation_ui_hardfilter.py`

The hardfilter rule is:

- file annotation targets = file rows where `grounding_status != resolved`
- column annotation targets = weak or unmatched columns from files where `grounding_status == resolved`

Full run outputs are written locally under:

`gold_benchmarks/scidata_selected_50_v1/grounding_v2_hardfilter_0618/`

Clean benchmark manifests are copied into:

`gold_benchmarks/scidata_selected_50_v1/manifests/grounding/`
