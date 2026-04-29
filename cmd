#python src/preprocessing/journal_manifest_builder.py \
#  --issn 2052-4463 \
#  --output-manifest data/manifests/test_articles.csv \
#  --max-articles 10 \
#  --filter-mode openalex
#
#
#
#python src/preprocessing/journal_manifest_builder.py \
#  --issn 2052-4463 \
#  --output-manifest data/manifests/test.csv \
#  --max-articles 10 \
#  --max-fetched 50 \
#  --filter-mode nature
python src/preprocessing/pdf_downloader.py \
  --input-manifest data/manifests/test.csv \
  --output-manifest data/manifests/test_pdf_manifest.csv \
  --pdf-dir data/raw_pdfs

