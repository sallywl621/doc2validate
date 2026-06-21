# SciData selected 50 gold benchmark v1

Generated at: 2026-06-12T18:01:59

This directory was built from `selected_run_50.xlsx`.

Rules used:

1. For each selected article, copy known JSON/PDF files into `<article_id>/json/` and `<article_id>/pdf/`.
2. Copy only existing `downloaded_artifacts/<article_id>/**/extracted/` directories into `<article_id>/artifact/github/`.
3. Extract manually downloaded replacement zip files from `/tmp/0612_download` into `<article_id>/artifact/<new_source>/`.
4. Write `benchmark_manifest.csv`, `manual_replacement_log.csv`, and per-case `case_build_manifest.json`.

Total selected cases: 50
