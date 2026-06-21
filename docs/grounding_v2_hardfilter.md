# Doc2Validate grounding v2 hardfilter 0618

This is a fresh standalone package with a different directory name, script names, module names, and default output directory to avoid cache/name confusion.

## Package directory

```text
grounding_v2_hardfilter_0618/
  VERSION_HARDFILTER_0618.txt
  grounder_v2_hardfilter.py
  run_grounding_v2_hardfilter.py
  export_grounding_v2_hardfilter_manifests.py
  interactive_annotation_ui_hardfilter.py
```

## Default output directory

```text
/mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1/grounding_v2_hardfilter_0618
```

This intentionally differs from the previous `grounding_v2` directory.

## Hard rule

```text
file annotation targets = rows where grounding_status != resolved
column annotation targets = weak/unmatched columns from rows where grounding_status == resolved
```

Resolved rows are never exported to file-level annotation merely because role evidence is weak or column evidence is partial.

## Run one case

```bash
cd /path/to/grounding_v2_hardfilter_0618
cat VERSION_HARDFILTER_0618.txt

python run_grounding_v2_hardfilter.py \
  --project-root /mydata/doc2validate \
  --benchmark-root /mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1 \
  --article-id s41597-020-00688-8 \
  --overwrite

python export_grounding_v2_hardfilter_manifests.py \
  --project-root /mydata/doc2validate \
  --benchmark-root /mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1 \
  --article-id s41597-020-00688-8
```

Expected for `s41597-020-00688-8`:

```text
file rows: 6
column rows: 23
file annotation target rows: 1
column annotation target rows: 2
```

## Run all selected-50

```bash
python run_grounding_v2_hardfilter.py \
  --project-root /mydata/doc2validate \
  --benchmark-root /mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1 \
  --overwrite

python export_grounding_v2_hardfilter_manifests.py \
  --project-root /mydata/doc2validate \
  --benchmark-root /mydata/doc2validate/gold_benchmarks/scidata_selected_50_v1
```
