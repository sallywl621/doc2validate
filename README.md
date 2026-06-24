# Doc2Validate

**Doc2Validate** is a documentation-driven dataset grounding and executable validation framework for machine-assisted repository stewardship.

The project studies whether heterogeneous dataset documentation can be transformed into machine-actionable evidence for repository operations. It normalizes documentation into logical dataset schemas, checks whether those logical objects are supported by physical artifacts, estimates dataset curatability as downstream workload and validation risk, and generates baseline validation workflows for datasets that are ready for automation.

## Why this matters

Digital repositories increasingly receive datasets with heterogeneous documentation: data papers, README files, repository pages, codebooks, metadata files, and mixed code/data deposits. Repository stewards need to understand whether a dataset is not only described and accessible, but also operationally curatable:

- Can its logical structure be reconstructed?
- Can documented files be matched to physical artifacts?
- Are columns, roles, and validation targets described clearly enough?
- Can baseline loading and validation code be generated?
- Which cases require human review, manual completion, or specialized runtime support?

Doc2Validate treats **dataset curatability** as an operational concept: the degree to which a dataset package can be moved toward reliable, executable, and human-reviewable stewardship with limited manual intervention.

## Conceptual workflow

```text
Documentation
→ Structured Context
→ LLM + Schema-based Extraction
→ Logical Dataset Structure
→ Physical Correspondence / Grounding
→ Validation Code Generation
→ Execution
→ Score / Failure Evidence
```

The schema is not just an extraction format. It is the interface that makes documentation comparable, verifiable, quantifiable, and actionable for downstream stewardship.

## Current implementation modules

The current codebase is organized around a full repository-stewardship pipeline rather than a schema-only extraction workflow.

```text
src/
├── artifact_downloading/
├── artifact_grounding/
├── code_generation/
├── context/
├── execution/
├── extraction/
├── feature_computation/
├── preprocessing/
├── repository_crawling/
├── schema_extraction/
├── scoring/
├── tabular_interpretation/
├── utils/
└── validation/
```

Important modules include:

- `artifact_downloading/`: downloads supported dataset artifacts from GitHub, Zenodo, and direct artifact URLs.
- `artifact_grounding/`: builds a physical inventory and maps logical dataset files to physical files.
- `tabular_interpretation/`: builds lightweight previews of tabular files.
- `schema_extraction/`: reconstructs logical dataset structure from documentation.
- `code_generation/`: generates validation code using logical schema and, when available, artifact grounding.
- `execution/`: runs generated validation workflows.
- `scoring/`: computes curatability-related signals.
- `repository_crawling/`: gathers repository documentation/context.

## Scripts

The repository includes shell entry points and analysis utilities.

```text
scripts/
├── corpus_builder_pipeline.sh
├── repository_discovery_pipeline.sh
├── run_artifact_downloader.sh
├── run_code_generation.sh
├── run_scoring.sh
├── analysis/
│   ├── analyze_download_candidates.py
│   ├── analyze_grounding_failures.py
│   ├── analyze_landing_page_vs_download.py
│   ├── build_execution_ready_manifest.py
│   └── build_grounding_review_workbook.py
└── tool/
    ├── build_pdf_manifest_from_existing_pdfs.sh
    ├── fix_download_error.sh
    └── preprocess_existing_pdfs.sh
```

## Main data flow

The current corpus-scale pipeline can be summarized as:

```text
article corpus
→ PDF preprocessing
→ dataset/code URL extraction
→ URL validation
→ repository crawling
→ artifact downloading
→ dataset structure extraction
→ artifact grounding
→ CSV preview / tabular interpretation
→ code generation
→ execution
→ scoring and failure analysis
```

The research-level explanation is:

```text
documentation + repository/package context
→ logical dataset structure
→ physical artifact correspondence
→ semantic validation targets
→ generated validation workflow
→ execution-grounded curatability evidence
```

## Dataset structure output

A typical `dataset_structure.json` has a top-level wrapper and a `result` object:

```text
top-level
└── result
    ├── dataset_identity
    ├── organization
    ├── files
    ├── sample_or_record_unit
    ├── spatial_temporal_coverage
    ├── validation_targets
    ├── execution_relevant_notes
    ├── structure_confidence
    └── context_summary
```

Within `result.files`, the current schema may include fields such as:

```text
logical_name
file_pattern
format
schema_type
role
source
path
structure.columns
```

Column semantics are often stored under:

```text
file["structure"]["columns"]
```

where `columns` is a dictionary keyed by column name.

## Artifact downloading behavior

The artifact downloader intentionally focuses on validation-relevant dataset artifacts rather than full software reproduction.

It currently supports:

- GitHub repositories: downloaded as archive zip, then extracted.
- Zenodo records: downloaded through the Zenodo records API.
- Direct artifact URLs: downloaded if the URL ends in a supported data/archive extension.

Unsupported landing pages, including many Figshare/OSF/Dataverse landing pages, may require manual completion.

For GitHub URLs, the downloader creates:

```text
downloaded_artifacts/<article_id>/github/<repo_key>/
├── archive/
└── extracted/
```

The `archive/` directory is expected for GitHub downloads and should not be interpreted as a problem by itself.

## Gold benchmark: `scidata_selected_50_v1`

A manually curated selected-50 benchmark has been built for near-term experiments.

Path:

```text
/mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1
```

Construction summary:

```text
187 artifact directories
→ 113 with real downloaded artifacts
→ 103 with extracted content
→ 72 with extracted strict tabular files
→ 70 high-priority benchmark candidates
→ 50 manually confirmed gold benchmark cases
```

Benchmark build status:

```text
50 selected cases built successfully
10 cases planned for external replacement
9 external replacements completed
1 pending external replacement
```

Effective artifact source distribution:

```text
github      41
figshare     8
osf          1
```

The one external replacement still pending is:

```text
s41597-024-03120-7 / figshare / 24259573.zip
```

That case uses GitHub as fallback.

Core benchmark files:

```text
scidata_selected_50_v1/
├── selected_run_50.xlsx
├── benchmark_manifest.csv
├── manual_replacement_log.csv
├── effective_artifact_manifest.csv
├── effective_artifact_roots.txt
├── selected_50_article_ids.txt
└── <article_id>/
    ├── json/
    ├── pdf/
    └── artifact/
        ├── github/
        ├── figshare/
        └── osf/
```

The main input for future gold-benchmark runs is:

```text
effective_artifact_manifest.csv
```

It records, for each article, the artifact source and root directory that should be used by downstream grounding and execution.

Effective artifact selection rule:

```text
if artifact/figshare has files:
    use figshare
elif artifact/osf has files:
    use osf
else:
    use github
```

## How the high-priority 70 and selected-50 benchmark were produced

The current gold benchmark was not sampled directly from the full 4,293-article discovery corpus. It was constructed through a staged audit and curation process.

### Step 1. Audit the downloaded artifact pool

The first stage audited the locally downloaded artifact pool:

```text
/mydata/doc2validate/data/downloaded_artifacts
```

This pool contained:

```text
187 artifact directories
```

The audit separated manifest-only folders from folders with real downloaded content, extracted content, and strict tabular candidates.

Downloaded artifact status:

```text
187 artifact directories
├── 113 contain real downloaded artifacts
├── 103 contain extracted content
└── 72 contain extracted strict tabular files
```

Here, “strict tabular files” means files that are suitable for the current lightweight validation workflow, such as:

```text
.csv
.tsv
.xlsx
.xls
.parquet
```

### Step 2. Combine artifact evidence with logical schema evidence

The second stage joined the artifact audit with documentation-derived `dataset_structure.json` outputs.

The schema parser was corrected to read the real schema layout:

```text
dataset_structure.json
└── result
    └── files[*]
        └── structure.columns
```

After this correction, the audit found:

```text
187 have dataset_structure.json
180 include column semantics
185 include path or file-pattern information
98 include primary tabular logical files
```

The high-priority candidate filter required:

```text
has extracted strict tabular file
+ has dataset_structure.json
+ has column semantics
+ has path or file-pattern information
```

This produced:

```text
70 high-priority candidates
```

These 70 cases are high-priority because they combine three signals needed by the current experiment:

```text
1. local usable artifacts
2. strict tabular physical files
3. documentation-derived logical schema with column semantics and path/pattern evidence
```

The 70 candidates were further divided into:

```text
Rerun-ready v1: 41
Manual-check pool v1: 29
```

This showed that the usable experiment pool was larger than the earlier execution-ready subset. The 41 rerun-ready cases could be sent directly to a general tabular workflow, while the 29 manual-check cases required human inspection to determine whether the tabular files were primary enough and whether software/runtime components were blocking.

### Step 3. Manual curation from high-priority 70 to selected 50

The selected-50 benchmark was then manually curated from the 70 high-priority candidates.

The review workbook was:

```text
selected_run_50.xlsx
```

Selection criteria included:

```text
1. the case is a real dataset, not a code-only repository
2. the dataset size is manageable for current experiments
3. the artifact can be stored locally and accessed by downstream workflow steps
4. documentation or repository-packaged non-code text provides enough structure or semantic evidence
5. the case remains suitable for the current tabular or tabular-like validation benchmark
```

During manual review, some GitHub repositories were found to be code-heavy, to contain only sample data, or to duplicate data that was more properly deposited in an external repository such as Figshare or OSF. For these cases, the source-of-record rule was:

```text
if an official external deposited artifact was available and successfully downloaded:
    use the external artifact as the preferred benchmark source
else:
    retain the GitHub extracted artifact as fallback
```

The resulting benchmark is:

```text
/mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1
```

Build outcome:

```text
50 selected cases built successfully
10 cases planned for external replacement
9 external replacements completed
1 external replacement pending
```

Effective artifact source distribution:

```text
github      41
figshare     8
osf          1
```

Therefore, the selected-50 benchmark currently contains:

```text
41 GitHub-based cases
8 Figshare-based cases
1 OSF-based case
```

The only planned external replacement still pending is:

```text
s41597-024-03120-7
planned source: figshare / 24259573.zip
effective source: github fallback
github_file_count: 428
```

A special corrected case is:

```text
sdata2018310
external source: figshare
actual local archive: PEPCONF.tar.xz
extracted file count: 8310
size: ~29.9 MB
```

The benchmark’s effective artifact roots are recorded in:

```text
effective_artifact_manifest.csv
effective_artifact_roots.txt
```

The effective artifact root selection rule is:

```text
if artifact/figshare has files:
    use figshare
elif artifact/osf has files:
    use osf
else:
    use github
```

Downstream workflow steps should use:

```text
/mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1/effective_artifact_manifest.csv
```

rather than returning to the original downloaded artifact pool.

### Summary

In short:

> The high-priority 70 were produced by auditing the downloaded artifact pool and selecting cases that combined real extracted tabular artifacts with documentation-derived logical schema, column semantics, and path/pattern evidence. The selected 50 were then produced through manual review of these 70 candidates, removing code-only or sample-data repositories, verifying dataset validity and size suitability, and replacing GitHub artifacts with official Figshare or OSF deposits when available.

## Current research focus

The current experiments should focus on the selected-50 gold benchmark rather than expanding again to the full 4,293-article discovery corpus.

Near-term tasks:

1. Use `effective_artifact_manifest.csv` as the artifact root manifest.
2. Rerun artifact inventory and grounding on the selected-50 benchmark.
3. Rebuild tabular previews using the effective artifact roots.
4. Generate validation code using gold benchmark artifacts.
5. Run execution validation and classify failures.
6. Compare curatability score against human-review burden and validation risk.
7. Separate acquisition-layer failures from stewardship-layer failures.

## Failure analysis principles

Doc2Validate distinguishes acquisition-layer failures from stewardship-layer failures.

Acquisition-layer failures include:

```text
external artifact not automatically downloaded
unsupported landing page
missing downloader support
archive handling problem
network/access limitation
```

These are engineering/corpus-preparation issues and should not be treated as direct evidence of poor dataset curatability.

Stewardship-layer failures include:

```text
version mismatch
documentation–repository filename mismatch
schema granularity mismatch
column semantic mismatch
role ambiguity
software/runtime environment support
unsupported modality
format/parser requirement missing
```

These are more directly relevant to repository stewardship.

## Tabular benchmark rationale

The current benchmark emphasizes tabular or tabular-like datasets because tabular files expose machine-readable structural signals such as headers and column names. These signals make it possible to compare documented logical schemas with physical files and to generate baseline validation code.

Important caveat:

> Tabular does not mean easy or always loadable.

Tabular datasets may still fail because of encoding issues, delimiter mismatches, compressed file handling, large files, Excel sheet complexity, JSON shape, Git LFS pointers, version mismatch, or missing runtime/software dependencies.

## Citation / reporting language

Suggested project description:

> Doc2Validate proposes a pathway from heterogeneous dataset documentation to repository operations. It normalizes documentation into logical dataset schemas, checks physical artifact correspondence, estimates curatability as downstream workload and validation risk, and generates executable validation workflows for datasets that are ready for automation.

Suggested benchmark description:

> From 70 high-priority candidates, we manually selected 50 datasets that were confirmed to be genuine dataset artifacts, had manageable size, and contained sufficient documentation or repository-packaged non-code text. When both GitHub and an official external repository artifact such as Figshare or OSF were available, the external deposited artifact was used as the preferred source when successfully downloaded. The resulting gold benchmark contains 41 GitHub-based cases, 8 Figshare-based cases, and 1 OSF-based case.

## Current work plan

The immediate plan is to review and update the workflow code from the logical-structure stage onward so that the next experiment run is aligned with the selected-50 gold benchmark.

Today’s planned work:

```text
1. Review the workflow code starting from logical dataset structure.
2. Identify code changes needed for the selected-50 benchmark.
3. Ensure downstream stages read effective_artifact_manifest.csv.
4. Update artifact grounding so it uses effective_artifact_root.
5. Review tabular preview, scoring, code generation, and execution inputs.
6. Write modification notes for experiments that still need to be completed.
7. Rerun the workflow on scidata_selected_50_v1.
8. Fill in all missing experiment outputs and manifests.
```

The core principle for the rerun is:

```text
selected-50 gold benchmark
+ effective artifact roots
+ logical dataset structures
→ grounding
→ tabular previews
→ code generation
→ execution
→ scoring
→ failure evidence
```

The rerun should produce a complete experiment dataset for reporting:

```text
schema completeness signals
artifact grounding outcomes
tabular preview availability
code generation outcomes
execution outcomes
runtime failure categories
curatability score components
human-review / failure-analysis evidence
```

## Status

This README reflects the current research and implementation state after construction of the selected-50 gold benchmark. Some pipeline scripts may still need adaptation to read `effective_artifact_manifest.csv` rather than the original downloaded artifact pool.
---

## 2026-06-16 Update — Selected-50 Logical Claims and Physical Grounding

This update documents the decision and implementation completed in the current conversation so a future conversation can resume without losing context.

### Major design decision

We decided **not** to build or run a new `refine_schema_extraction` module for the selected-50 benchmark.

Reason:

- The existing copied `dataset_structure.json` files already provide complete documentation-derived logical schemas for all 50 selected cases.
- The goal of the next stage is not to re-extract or modify the logical schema.
- The selected-50 workflow should preserve a clean distinction between:

```text
logical schema layer:
  dataset_structure.json
  = documentation-derived logical file/column claims

physical grounding layer:
  refined_artifact_grounding.json
  = comparison between logical claims and observed artifact files

notebook / scoring / human review layer:
  curatability_review.ipynb
  notebook_execution.json
  human_annotations.json
  curatability_report.json
```

Important principle:

> Logical schema completeness does not imply physical curatability. Dataset stewardship requires a separate grounding step that compares documentation-derived logical claims against actual deposited artifacts.

### Updated selected-50 loader

`src/selected50/benchmark_loader.py` was rewritten to expose separate logical and physical loading functions.

Key functions:

```python
load_logical_claims(case)
```

Reads only `json/dataset_structure.json` and normalizes the old schema into logical claims:

```text
logical_file_id
logical_name
documented_path_or_pattern
expected_format
schema_type
role
columns
source
```

This function acts as the schema adapter, so a separate `schema_adapter.py` is not currently needed.

```python
load_physical_inventory(case)
```

Scans only `effective_artifact_root` and returns observed physical files.

```python
load_grounding_inputs(case)
```

Returns both evidence layers:

```text
logical_claims
physical_inventory
artifact_sources_overview
```

This is the direct input for physical grounding.

Optional diagnostic/provenance helper:

```python
load_case_json_bundle(case)
```

This loads all JSON files for debugging/provenance, but physical grounding should not let these override `dataset_structure.json` logical claims.

### Workspace check result

Command:

```bash
python -m src.selected50.check_workspace \
  --benchmark-root /mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1
```

Result:

```text
n cases: 50
artifact root exists: 50
dataset_structure exists: 50
total files: 13141
total tabular candidates: 2456
Potential problem cases: none
```

### Logical schema audit result

A new audit script was added:

```text
src/selected50/audit_logical_claims.py
```

This audits the exact logical claims representation returned by `load_logical_claims(case)`.

Command:

```bash
python -m src.selected50.audit_logical_claims \
  --benchmark-root /mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1
```

Result:

```text
n cases: 50
success: 50
logical files > 0: 50
path/pattern > 0: 50
format > 0: 50
tabular claims > 0: 50
columns > 0: 50
score >= 0.75: 50

Score distribution:
count    50.0
mean      1.0
std       0.0
min       1.0
25%       1.0
50%       1.0
75%       1.0
max       1.0
```

Conclusion:

> All 50 selected benchmark cases have complete documentation-derived logical schemas. The existing `dataset_structure.json` files are sufficient as the logical schema layer; no selected-50 schema refinement is needed.

### Physical grounding module added

New module:

```text
src/refine_artifact_grounding/
├── __init__.py
├── refined_grounder.py
├── run_refined_artifact_grounding.py
└── export_grounding_manifests.py
```

Purpose:

- Compare `load_logical_claims(case)` against `load_physical_inventory(case)`.
- Produce fact-based grounding evidence.
- Do not modify `dataset_structure.json`.
- Output one JSON per article:

```text
<article_id>/json/refined_artifact_grounding.json
```

Grounding statuses:

```text
resolved
ambiguous
weak_match
missing
ungroundable
unsupported_non_file_claim
```

Warning types include:

```text
ambiguous_physical_match
weak_physical_match
missing_physical_match
missing_name_match_with_same_format_candidates
multiple_artifact_sources_available
unsupported_non_file_claim
```

Important interpretation:

- `resolved`: strong filename/path match.
- `ambiguous`: multiple physical files match a logical claim with similar evidence.
- `weak_match`: there is some weak match evidence, but curator review is required.
- `missing`: no physical file matches the documented logical claim strongly enough.
- `missing_name_match_with_same_format_candidates`: files with the expected format exist, but their names/path do not match the documented claim.
- `unsupported_non_file_claim`: the claim appears to describe an API, endpoint, or data stream rather than a deposited physical file.

### Single-case grounding sanity test

Test article:

```text
s41597-019-0035-4
```

Command:

```bash
python -m src.refine_artifact_grounding.run_refined_artifact_grounding \
  --benchmark-root /mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1 \
  --article-id s41597-019-0035-4 \
  --overwrite
```

Final result after adding `unsupported_non_file_claim` handling:

```text
n cases: 1
success: 1
file_grounding_applicable: 5
resolved: 0
ambiguous: 1
weak_match: 1
missing: 3
ungroundable: 0
unsupported_non_file_claim: 1
human_review_needed: 6
avg grounding_score: 0.15
```

File-level interpretation:

```text
lf_001 anatomical_iqms => missing
  warning: missing_name_match_with_same_format_candidates

lf_002 functional_iqms => missing
  warning: missing_name_match_with_same_format_candidates

lf_003 expert_ratings => weak_match
  matched candidate: rating.csv
  warning: weak_physical_match

lf_004 iqm_metadata => missing
  warning: missing_physical_match

lf_005 curated_anatomical_iqms => ambiguous
  candidates: T2w_curated.csv, T1w_curated.csv, bold_curated.csv
  warning: ambiguous_physical_match

lf_006 api_data_stream => unsupported_non_file_claim
  warning: unsupported_non_file_claim
```

This case is useful because it shows the gap between documentation-derived logical claims and actual deposited artifact names.

### Full selected-50 physical grounding results

Command:

```bash
python -m src.refine_artifact_grounding.run_refined_artifact_grounding \
  --benchmark-root /mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1 \
  --overwrite
```

Result:

```text
n cases: 50
success: 50
file_grounding_applicable: 324
resolved: 119
ambiguous: 84
weak_match: 43
missing: 78
ungroundable: 0
unsupported_non_file_claim: 1
human_review_needed: 206
avg grounding_score: 0.5156
```

Exported manifests:

```bash
python -m src.refine_artifact_grounding.export_grounding_manifests \
  --benchmark-root /mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1
```

Output files:

```text
refined_artifact_grounding_article_manifest.csv
refined_artifact_grounding_file_manifest.csv
refined_artifact_grounding_warning_manifest.csv
```

Manifest summary:

```text
articles: 50
successful articles: 50
logical file rows: 325
warning rows: 215
```

Article-level statistics:

```text
n articles: 50
success: 50
mean grounding_score: 0.515624
median grounding_score: 0.5
articles with any missing: 26
articles with any ambiguous: 32
articles with any weak_match: 23
articles with unsupported non-file claims: 1
```

Total grounding counts:

```text
num_file_grounding_applicable: 324
num_resolved: 119
num_ambiguous: 84
num_weak_match: 43
num_missing: 78
num_ungroundable: 0
num_unsupported_non_file_claim: 1
num_human_review_needed: 206
```

File-level grounding status distribution:

```text
resolved                      119
ambiguous                      84
missing                        78
weak_match                     43
unsupported_non_file_claim      1
```

Warning-type distribution:

```text
ambiguous_physical_match                          84
weak_physical_match                               43
missing_physical_match                            40
missing_name_match_with_same_format_candidates    38
multiple_artifact_sources_available                9
unsupported_non_file_claim                         1
```

Severity distribution:

```text
medium    128
high       78
low         9
```

### Key empirical claim now supported

The selected-50 benchmark now shows a clear gap between logical schema completeness and physical grounding success.

Logical schema audit:

```text
50/50 cases have complete logical schemas
mean logical_schema_score = 1.0
```

Physical grounding:

```text
119 / 324 file-applicable logical claims resolved = 36.7%
206 / 325 logical claims need human review = 63.4%
mean grounding_score = 0.516
```

Slide-ready sentence:

> Although all 50 selected benchmark cases had complete documentation-derived logical schemas, only 36.7% of file-applicable logical claims could be automatically resolved to physical artifacts. The remaining claims were ambiguous, weakly matched, or missing, requiring curator review in 63.4% of logical file claims.

Core interpretation:

> Logical schema completeness does not guarantee physical curatability. Curatability depends on whether documentation-derived claims can be grounded in actual deposited artifacts and reviewed by curators.

### Manifest files for slides/statistics

Use these CSVs directly for slides:

```text
/mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1/logical_claims_audit.csv
/mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1/refined_artifact_grounding_article_manifest.csv
/mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1/refined_artifact_grounding_file_manifest.csv
/mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1/refined_artifact_grounding_warning_manifest.csv
```

Recommended slide stats:

```text
logical schema completeness:
  50/50 complete, mean score 1.0

grounding distribution:
  resolved / ambiguous / weak_match / missing / unsupported

human review burden:
  206/325 logical claims require review

risk taxonomy:
  ambiguous_physical_match
  weak_physical_match
  missing_physical_match
  missing_name_match_with_same_format_candidates
  multiple_artifact_sources_available
  unsupported_non_file_claim
```

### Next step

Start the `curatability_notebook` module.

Inputs:

```text
dataset_structure.json
refined_artifact_grounding.json
```

Expected notebook output:

```text
<article_id>/notebooks/curatability_review.ipynb
```

Notebook should include:

```text
1. Dataset overview
2. Logical schema summary
3. Physical grounding summary
4. Grounding warning sections
5. Human annotation targets
6. Preview/load cells for resolved, weak, and ambiguous candidate files
7. Final curator decision cell
```

Notebook-local scores can be displayed, but final scoring should be generated later by `curatability_scoring` from JSON evidence.

Human annotation types should be recorded in structured form, including:

```text
accept_system_assessment
override_grounding
manual_file_mapping
mark_missing
mark_ambiguous
exclude_from_file_validation
request_supplementary_materials
modify_validation_code
accept_validation_result
reject_validation_result
final_accept_for_ingest
final_reject_dataset
needs_second_review
```

Important notebook/scoring boundary:

```text
refined_artifact_grounding.json
  source of truth for grounding evidence

curatability_review.ipynb
  curator-facing review artifact and executable draft

human_annotations.json
  curator decisions and corrections

curatability_report.json
  final aggregated score and recommendation
```


## Selected-50 current state after 2026-06-16 update

The selected-50 implementation currently treats the existing `dataset_structure.json` files as the logical schema layer and focuses on physical grounding and curator-facing review.

Completed selected-50 modules:

```text
src/selected50/
  benchmark_loader.py
  check_workspace.py
  audit_logical_claims.py

src/refine_artifact_grounding/
  refined_grounder.py
  run_refined_artifact_grounding.py
  export_grounding_manifests.py
```

Current selected-50 benchmark path:

```text
/mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1
```

The physical grounding outputs are now available under each article directory:

```text
<article_id>/json/refined_artifact_grounding.json
```

And benchmark-level CSV manifests are available at:

```text
refined_artifact_grounding_article_manifest.csv
refined_artifact_grounding_file_manifest.csv
refined_artifact_grounding_warning_manifest.csv
```

## Selected-50 full pipeline completion after 2026-06-16 update

The selected-50 benchmark now has an end-to-end implementation from logical schema loading through physical grounding, curator-facing notebook generation, notebook execution, preview classification, human annotation scaffolding, component-based scoring, and aggregate reporting.

### Completed modules

```text
src/selected50/
  benchmark_loader.py
  check_workspace.py
  audit_logical_claims.py

src/refine_artifact_grounding/
  refined_grounder.py
  run_refined_artifact_grounding.py
  export_grounding_manifests.py

src/curatability_notebook/
  notebook_builder.py
  run_curatability_notebook_generation.py

src/notebook_execution/
  run_curatability_notebook_execution.py
  export_notebook_review_manifests.py

src/curatability_scoring/
  score_selected50_curatability.py
  summarize_selected50_curatability.py
```

### Benchmark root

```text
/mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1
```

### Main generated outputs

Per article:

```text
<article_id>/json/refined_artifact_grounding.json
<article_id>/notebooks/curatability_review.ipynb
<article_id>/json/notebook_execution.json
<article_id>/json/human_annotations.json
<article_id>/json/curatability_report.json
```

Benchmark-level manifests:

```text
refined_artifact_grounding_article_manifest.csv
refined_artifact_grounding_file_manifest.csv
refined_artifact_grounding_warning_manifest.csv

curatability_notebook_generation_manifest.csv
curatability_notebook_execution_manifest.csv
curatability_notebook_execution_article_manifest.csv
curatability_notebook_preview_manifest.csv
curatability_notebook_preview_manifest_classified.csv
curatability_human_annotation_manifest.csv

selected50_curatability_summary.csv
selected50_curatability_component_scores.csv
selected50_curatability_issue_manifest.csv
selected50_curatability_aggregate_report.json
selected50_curatability_slide_stats.md
```

### Commands used for full selected-50 run

Generate notebooks:

```bash
python -m src.curatability_notebook.run_curatability_notebook_generation \
  --benchmark-root /mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1 \
  --overwrite
```

Execute notebooks with `nbclient`:

```bash
conda activate vllm_env
cd /mydata/doc2validate

python -m src.notebook_execution.run_curatability_notebook_execution \
  --benchmark-root /mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1 \
  --overwrite \
  --timeout 300
```

Export notebook review manifests:

```bash
python -m src.notebook_execution.export_notebook_review_manifests \
  --benchmark-root /mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1
```

Score curatability:

```bash
python -m src.curatability_scoring.score_selected50_curatability \
  --benchmark-root /mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1
```

Summarize aggregate results:

```bash
python -m src.curatability_scoring.summarize_selected50_curatability \
  --benchmark-root /mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1
```

### Final selected-50 results

Notebook generation:

```text
n cases: 50
success: 50
human_review_needed: 206
avg grounding_score: 0.5156
```

Notebook execution:

```text
n cases: 50
success: 50
errors: 0
preview_success: 210
preview_failed: 184
annotations: 256
```

Notebook review manifests:

```text
article rows: 50
preview rows: 394
annotation rows: 256
preview success: 210
preview failed: 184
annotation rows:
  grounding: 206
  final_decision: 50
```

Preview outcome classification:

```text
tabular_preview_success                    210
code_or_notebook_artifact_not_tabular       52
document_or_text_artifact_not_tabular       29
csv_encoding_error                          22
archive_artifact_requires_unpacking         22
structured_metadata_not_tabular             21
specialized_data_format_requires_loader     19
unsupported_format                          12
image_artifact_not_tabular                   6
missing_optional_dependency_xlrd             1
```

Curatability scoring:

```text
articles: 50
avg overall_score: 0.5910
avg physical_grounding_score: 0.5156
avg executable_preview_score: 0.6215
```

Recommendation counts:

```text
request_supplementary_materials_or_manual_mapping: 23
accept_for_ingest_with_light_review: 14
accept_with_curator_review: 9
high_risk_manual_review: 4
```

Component means:

```text
logical_schema_score        0.9349
executable_preview_score    0.6215
overall_score               0.5910
intervention_need_score     0.5613
physical_grounding_score    0.5156
review_burden_score         0.3446
```

Top issue counts:

```text
physical_grounding  num_ambiguous                              84
physical_grounding  num_missing                                78
executable_preview  code_or_notebook_artifact_not_tabular      52
physical_grounding  num_weak_match                             43
executable_preview  document_or_text_artifact_not_tabular      29
executable_preview  csv_encoding_error                         22
executable_preview  archive_artifact_requires_unpacking        22
executable_preview  structured_metadata_not_tabular            21
executable_preview  specialized_data_format_requires_loader    19
executable_preview  unsupported_format                         12
executable_preview  image_artifact_not_tabular                  6
physical_grounding  num_unsupported_non_file_claim              1
executable_preview  missing_optional_dependency_xlrd            1
```

### Main empirical claim

```text
Documentation-derived schema completeness does not imply dataset curatability.
```

Evidence:

```text
Mean logical schema score:       0.9349
Mean physical grounding score:   0.5156
Mean review burden score:        0.3446
Resolved grounding claims:       119 / 324 (36.7%)
Human review targets:            206
Tabular preview success:         210 / 394 (53.3%)
```

Paper-ready wording:

```text
Across 50 selected benchmark cases, documentation-derived logical schema completeness was high on average (0.935), but physical grounding was substantially lower (0.516), and review-burden scores were lower still (0.345). Only 119 of 324 file-grounding-applicable logical claims were automatically resolved to physical artifacts. Although all generated curator-facing notebooks executed successfully, only 210 of 394 preview targets could be loaded by the generic tabular preview helper. These results show that curatability cannot be inferred from documentation completeness alone; it must be measured through grounded artifact evidence, executable inspection, and curator-facing review burden.
```

### Environment notes

`jupyter nbconvert` failed in the local environment because `jupyter_contrib_nbextensions` expected the older `notebook.services` API. The notebook execution module therefore uses `nbclient` directly. Execute it inside `vllm_env`.

### Current interpretation

The implementation does not replace curator judgment. It makes curator workload visible and measurable by converting documentation claims, artifact grounding, executable preview results, and human annotation targets into structured evidence. The strongest selected-50 result is that logical documentation completeness is much higher than physical grounding and review-burden scores, showing why curatability must be measured beyond documentation extraction.

---

## 2026-06-20 Update — Final PV Slide Framework and Executable Validation Evidence

This update records the latest presentation framework and experimental results after the Slide 10–12 work.

### Final presentation structure

The updated PV 2026 deck uses 14 content slides:

```text
Slide 1  — Problem Definition
Slide 2  — Motivation
Slide 3  — Workflow Design and Long-term Vision
Slide 4  — Structured Extraction and Schema Design
Slide 5  — Physical Grounding
Slide 6  — From Grounding to Review Targets and Executable Evidence
Slide 7  — Scoring as a Curator-facing Triage Layer
Slide 8  — Corpus Building
Slide 9  — Experimental Design
Slide 10 — Solved Results: Resolved Files and Columns Become Executable Validation
Slide 11 — Unresolved Grounding Results Become Meaningful Review Targets
Slide 12 — Score Alignment with Execution and Review Outcomes
Slide 13 — Contributions and Findings
Slide 14 — Next Steps
```

Core story:

```text
Slide 10: resolved mappings become executable validation artifacts.
Slide 11: unresolved mappings become targeted human review tasks.
Slide 12: evidence-derived score broadly aligns with automation readiness and review burden.
```

### Slide 10 executable validation evidence

A stricter executable validation subset was defined from the selected-50 grounding outputs:

```text
119 resolved file mappings
→ 81 header-loadable resolved files
→ 69 validation-ready files with automatically matched columns
→ 68 files successfully loaded
→ 66 files fully executed
```

Execution summary:

```text
validation_candidate_files:       69
validation_jobs_generated:        69 / 69 = 100%
file_load_success:                68 / 69 = 98.6%
file_execution_success:           66 / 69 = 95.7%
column_targets:                   200
column_access_success:            198 / 200 = 99.0%
column_profile_success:           198 / 200 = 99.0%
numeric columns profiled:         61
string/object columns profiled:   137
```

Failure interpretation:

```text
1 file parser / delimiter irregularity
2 execution-discovered possible grounding false positives
```

A GitHub-ready generated validation package was created with generated validators, specs, runtime, results, and README, but without raw artifacts:

```text
slide10_executable_validation_github/
  README.md
  requirements.txt
  runtime/
  specs/
  generated_validators/
  results/
  run_all_validators.py
  generated_validator_manifest.csv
```

### Slide 11 annotation pilot evidence

Full review-target pool:

```text
file mapping review targets:       206
loader/header review targets:       15 files / 62 documented columns
column semantic review targets:    144
```

Manual pilot annotation over 45 sampled review targets:

```text
human-confirmed stewardship issues:       30
over-conservative / false alarms:         10
incomplete evidence / needs second review: 5
```

Among adjudicated targets:

```text
30 / 40 = 75%
```

Preferred terminology:

```text
Human-confirmed stewardship issue
  The system flagged a review target, and human review confirmed a real documentation-artifact problem or curator-relevant ambiguity.

Over-conservative / false alarm
  The system flagged a target, but the file or column was acceptable after human inspection.

Incomplete evidence / needs second review
  The available corpus evidence was insufficient to adjudicate the target.
```

### Slide 12 score alignment evidence

The score is treated as a curator-facing triage signal, not an independent predictive model.

Definition:

```text
Review burden here = average number of file-level items marked human_review_needed in the article manifest.
It is not the total number of rows across all annotation CSVs.
```

Score-bin alignment:

```text
High score group:
  n=12
  avg score=0.733
  avg file-level human review targets=2.5
  avg matched columns=11.9
  validation-ready files=46
  file execution success=44/46=95.7%
  column profile success=138/139=99.3%

Medium score group:
  n=20
  avg score=0.546
  avg file-level human review targets=3.5
  avg matched columns=2.9
  validation-ready files=19
  file execution success=19/19=100%
  column profile success=54/54=100%

Low score group:
  n=18
  avg score=0.327
  avg file-level human review targets=5.9
  avg matched columns=0.4
  validation-ready files=4
  file execution success=3/4=75.0%
  column profile success=6/7=85.7%
```

Interpretation:

```text
The score broadly separates automation-ready cases from high-review-burden cases.
The strongest alignment is not execution success rate alone, but the amount of automation-ready evidence produced.
```

Caveat:

```text
One high-score outlier had all ambiguous file mappings and no executable targets, suggesting that future score refinement should penalize unresolved ambiguity more strongly.
```

### Updated empirical interpretation

Doc2Validate now has three connected forms of evidence:

```text
1. Resolved evidence:
   automatically grounded file and column mappings that can become executable validators.

2. Unresolved evidence:
   review targets that often reveal human-confirmed stewardship issues.

3. Score evidence:
   a curator-facing triage signal that broadly aligns with automation readiness and review burden.
```

This supports the central claim:

```text
Machine-assisted stewardship should be measured not only by automatic resolution,
but also by whether unresolved cases are converted into structured, auditable curator tasks.
```

