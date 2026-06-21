# Selected-50 Curatability Aggregate Report

Created at: `2026-06-16T16:21:23.393811`

## Key numbers

| Metric | Value |
| --- | --- |
| Articles | 50 |
| Mean overall score | 0.5910 |
| Mean logical schema score | 0.9349 |
| Mean physical grounding score | 0.5156 |
| Mean executable preview score | 0.6215 |
| Mean review burden score | 0.3446 |
| Mean intervention need score | 0.5613 |
| Resolved grounding claims | 119 / 324 (36.7%) |
| Human review targets | 206 |
| Tabular preview success | 210 / 394 (53.3%) |

## Overall score distribution

| Statistic | Value |
| --- | --- |
| count | 50 |
| mean | 0.5910 |
| std | 0.2088 |
| min | 0.2000 |
| p25 | 0.4655 |
| median | 0.5398 |
| p75 | 0.7586 |
| max | 0.9793 |

## Recommendation counts

| Recommendation | Count | Percent |
| --- | --- | --- |
| request_supplementary_materials_or_manual_mapping | 23 | 46.0% |
| accept_for_ingest_with_light_review | 14 | 28.0% |
| accept_with_curator_review | 9 | 18.0% |
| high_risk_manual_review | 4 | 8.0% |

## Component means

| Component | Mean |
| --- | --- |
| logical_schema_score | 0.9349 |
| executable_preview_score | 0.6215 |
| overall_score | 0.5910 |
| intervention_need_score | 0.5613 |
| physical_grounding_score | 0.5156 |
| review_burden_score | 0.3446 |

## Top issues

| Scope | Issue type | Count |
| --- | --- | --- |
| physical_grounding | num_ambiguous | 84 |
| physical_grounding | num_missing | 78 |
| executable_preview | code_or_notebook_artifact_not_tabular | 52 |
| physical_grounding | num_weak_match | 43 |
| executable_preview | document_or_text_artifact_not_tabular | 29 |
| executable_preview | csv_encoding_error | 22 |
| executable_preview | archive_artifact_requires_unpacking | 22 |
| executable_preview | structured_metadata_not_tabular | 21 |
| executable_preview | specialized_data_format_requires_loader | 19 |
| executable_preview | unsupported_format | 12 |
| executable_preview | image_artifact_not_tabular | 6 |
| physical_grounding | num_unsupported_non_file_claim | 1 |
| executable_preview | missing_optional_dependency_xlrd | 1 |

## Preview outcome counts

| Preview outcome | Count | Percent |
| --- | --- | --- |
| tabular_preview_success | 210 | 53.3% |
| code_or_notebook_artifact_not_tabular | 52 | 13.2% |
| document_or_text_artifact_not_tabular | 29 | 7.4% |
| csv_encoding_error | 22 | 5.6% |
| archive_artifact_requires_unpacking | 22 | 5.6% |
| structured_metadata_not_tabular | 21 | 5.3% |
| specialized_data_format_requires_loader | 19 | 4.8% |
| unsupported_format | 12 | 3.0% |
| image_artifact_not_tabular | 6 | 1.5% |
| missing_optional_dependency_xlrd | 1 | 0.3% |

## Lowest overall-score cases

| Article ID | Overall | Recommendation | Grounding | Preview | Review burden | Missing | Ambiguous | Review targets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sdata2018310 | 0.20000000000000004 | high_risk_manual_review | 0.0 | 0.0 | 0.0 | 3 | 0 | 3 |
| s41597-023-02749-0 | 0.20000000000000004 | high_risk_manual_review | 0.0 | 0.0 | 0.0 | 6 | 0 | 6 |
| s41597-022-01141-8 | 0.23825000000000007 | high_risk_manual_review | 0.0625 | 0.2 | 0.0 | 7 | 1 | 8 |
| s41597-021-00929-4 | 0.26039000000000007 | high_risk_manual_review | 0.0938 | 0.2 | 0.0 | 6 | 1 | 8 |
| s41597-023-02160-9 | 0.3585961538461539 | request_supplementary_materials_or_manual_mapping | 0.3125 | 0.23846153846153847 | 0.0 | 3 | 5 | 8 |
| s41597-023-02576-3 | 0.36300000000000004 | request_supplementary_materials_or_manual_mapping | 0.25 | 0.19999999999999998 | 0.0 | 0 | 0 | 8 |
| s41597-020-00702-z | 0.37306128205128214 | request_supplementary_materials_or_manual_mapping | 0.4167 | 0.15384615384615385 | 0.0 | 0 | 4 | 6 |
| s41597-023-02724-9 | 0.3995000000000001 | request_supplementary_materials_or_manual_mapping | 0.3125 | 0.4000000000000001 | 0.125 | 3 | 2 | 7 |
| s41597-023-02070-w | 0.42940000000000006 | request_supplementary_materials_or_manual_mapping | 0.05 | 1.0 | 0.0 | 4 | 0 | 5 |
| s41597-022-01850-0 | 0.4396900000000001 | request_supplementary_materials_or_manual_mapping | 0.3438 | 0.36 | 0.25 | 4 | 1 | 6 |

## Highest overall-score cases

| Article ID | Overall | Recommendation | Grounding | Preview | Review burden | Missing | Ambiguous | Review targets |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| s41597-022-01473-5 | 0.9793 | accept_for_ingest_with_light_review | 1.0 | 0.9099999999999999 | 1.0 | 0 | 0 | 0 |
| s41597-022-01146-3 | 0.9510000000000002 | accept_for_ingest_with_light_review | 0.9375 | 1.0 | 0.875 | 0 | 1 | 1 |
| s41597-020-00712-x | 0.9440085714285715 | accept_for_ingest_with_light_review | 0.9286 | 1.0 | 0.8571428571428572 | 0 | 1 | 1 |
| s41597-024-04232-w | 0.9280000000000002 | accept_for_ingest_with_light_review | 0.9375 | 0.9 | 0.875 | 0 | 1 | 1 |
| s41597-020-00688-8 | 0.9245000000000003 | accept_for_ingest_with_light_review | 0.875 | 1.0 | 0.8333333333333334 | 0 | 0 | 1 |
| s41597-022-01255-z | 0.9186666666666667 | accept_for_ingest_with_light_review | 1.0 | 0.7333333333333334 | 1.0 | 0 | 0 | 0 |
| s41597-020-00676-y | 0.9186100000000003 | accept_for_ingest_with_light_review | 0.9062 | 0.925 | 0.875 | 0 | 0 | 1 |
| s41597-024-03368-z | 0.8739000000000002 | accept_for_ingest_with_light_review | 0.9375 | 0.73 | 0.875 | 0 | 1 | 1 |
| s41597-022-01788-3 | 0.8721100000000002 | accept_for_ingest_with_light_review | 0.7812 | 1.0 | 0.75 | 1 | 0 | 2 |
| s41597-022-01704-9 | 0.8259375000000002 | accept_for_ingest_with_light_review | 1.0 | 0.4062500000000001 | 1.0 | 0 | 0 | 0 |

## Slide-ready findings

- Across 50 selected benchmark cases, the mean overall curatability score was 0.591.
- Logical schema completeness was high on average (0.935), but physical grounding was substantially lower (0.516), indicating that documentation-derived schema completeness does not imply physical curatability.
- The system resolved 119 of 324 file-grounding-applicable logical claims (36.7%).
- Human review was requested for 206 logical file claims, reflecting curator workload that remains after automated grounding and preview.
- All generated notebooks that were executed completed successfully (50 / 50), while artifact preview exposed heterogeneous artifact-level inspection needs.
- The generic preview helper successfully loaded 210 of 394 preview targets (53.3%). The remaining 184 targets required non-generic handling such as archive unpacking, specialized loaders, text/code inspection, or encoding repair.
- Recommendation distribution: 14 light-review ingest, 9 curator-review ingest, 23 request supplementary materials/manual mapping, and 4 high-risk manual review.

## Suggested paper wording

Documentation-derived schema completeness did not imply curatability. Although selected benchmark cases had high logical-schema scores, physical grounding, executable preview, and review-burden signals revealed substantial downstream curator workload. These results support treating curatability as a measurable, evidence-grounded property of dataset deposits rather than as a property of documentation alone.
