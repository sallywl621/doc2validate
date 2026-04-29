from src.extraction.run_extraction import run_extractor
import argparse
from pathlib import Path

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--run-name", required=True)
    p.add_argument("--manifest", type=Path)
    p.add_argument("--log-path", type=Path)
    p.add_argument("--max-articles", type=int)
    p.add_argument("--overwrite", action="store_true")
    a = p.parse_args()
    run_extractor("code_repository", a.run_name, a.manifest, a.log_path, a.max_articles, a.overwrite)
