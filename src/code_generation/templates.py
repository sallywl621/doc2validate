from __future__ import annotations

from pathlib import Path


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_requirements(out_dir: Path) -> None:
    write_text(
        out_dir / "requirements.txt",
        "pandas>=2.0.0\n"
        "pyyaml>=6.0.0\n"
        "openpyxl>=3.1.0\n"
        "pyarrow>=14.0.0\n",
    )


def write_readme(out_dir: Path, article_id: str) -> None:
    write_text(
        out_dir / "README.md",
        f"# Generated validation scaffold\n\n"
        f"Article: `{article_id}`\n\n"
        "## Purpose\n"
        "This scaffold loads selected dataset artifacts inferred from `dataset_structure.json` "
        "and performs lightweight validation checks.\n\n"
        "## Inputs\n"
        "- `generated_manifest.json`\n"
        "- local artifact roots listed in the manifest\n\n"
        "## Run\n"
        "```bash\n"
        "pip install -r requirements.txt\n"
        "python run.py\n"
        "```\n\n"
        "## Output\n"
        "- `run_output.json`\n",
    )


def write_src_init(out_dir: Path) -> None:
    write_text(out_dir / "src" / "__init__.py", "")


def write_loaders(out_dir: Path) -> None:
    write_text(
        out_dir / "src" / "loaders.py",
        r'''from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd


@dataclass
class LoadResult:
    ok: bool
    path: Optional[str]
    strategy: str
    error: Optional[str] = None


def _split_patterns(value: str | None) -> List[str]:
    if not value:
        return []
    return [p.strip() for p in value.split(",") if p.strip()]


def _candidate_names(rel_path: str | None, file_pattern: str | None) -> List[str]:
    names: List[str] = []

    for raw in [rel_path, file_pattern]:
        for item in _split_patterns(raw):
            p = Path(item)
            names.append(str(p))
            names.append(p.name)

    # Deduplicate while preserving order.
    seen = set()
    out = []
    for name in names:
        if not name or name.lower() == "unknown":
            continue
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def _find_file(data_roots: List[str], rel_path: str | None, file_pattern: str | None, fmt: str) -> Tuple[Optional[Path], str]:
    names = _candidate_names(rel_path, file_pattern)

    for root_str in data_roots:
        root = Path(root_str)
        if not root.exists():
            continue

        for name in names:
            direct = root / name
            if direct.exists() and direct.is_file():
                return direct, "direct"

        for name in names:
            basename = Path(name).name
            matches = list(root.rglob(basename))
            if matches:
                return matches[0], "basename_search"

        if fmt:
            matches = list(root.rglob(f"*.{fmt}"))
            if matches:
                return matches[0], "extension_fallback"

    return None, "not_found"


def load_tabular_from_roots(
    data_roots: List[str],
    rel_path: str | None,
    fmt: str,
    file_pattern: str | None = None,
):
    path, strategy = _find_file(data_roots, rel_path, file_pattern, fmt)

    if path is None:
        return None, LoadResult(ok=False, path=None, strategy=strategy, error="file_not_found")

    try:
        fmt = (fmt or "").lower()
        if fmt == "csv":
            df = pd.read_csv(path)
        elif fmt == "tsv":
            df = pd.read_csv(path, sep="\t")
        elif fmt in {"xlsx", "xls"}:
            df = pd.read_excel(path)
        elif fmt == "json":
            df = pd.read_json(path)
        elif fmt == "jsonl":
            df = pd.read_json(path, lines=True)
        elif fmt == "parquet":
            df = pd.read_parquet(path)
        else:
            return None, LoadResult(ok=False, path=str(path), strategy=strategy, error=f"unsupported_format:{fmt}")

        return df, LoadResult(ok=True, path=str(path), strategy=strategy)

    except Exception as exc:
        return None, LoadResult(ok=False, path=str(path), strategy=strategy, error=f"{type(exc).__name__}: {exc}")
''',
    )


def write_validate(out_dir: Path) -> None:
    write_text(
        out_dir / "src" / "validate.py",
        r'''from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

import pandas as pd


@dataclass
class ValidationItem:
    name: str
    ok: bool
    detail: str


def validate_dataframe(
    df: pd.DataFrame,
    expected_columns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    items: List[ValidationItem] = []

    if df is None:
        items.append(ValidationItem("df_exists", False, "df is None"))
        return {"ok": False, "items": [asdict(x) for x in items]}

    items.append(ValidationItem("non_empty_rows", df.shape[0] > 0, f"{df.shape[0]} rows"))
    items.append(ValidationItem("non_empty_cols", df.shape[1] > 0, f"{df.shape[1]} cols"))

    if expected_columns:
        missing = [c for c in expected_columns if c not in df.columns]
        items.append(
            ValidationItem(
                "expected_columns",
                len(missing) == 0,
                "all expected columns present" if not missing else f"missing: {missing[:20]}",
            )
        )

    try:
        miss_rate = float(df.isna().mean().mean()) if df.size > 0 else 0.0
        items.append(ValidationItem("missingness_rate", True, f"{miss_rate:.4f}"))
    except Exception as exc:
        items.append(ValidationItem("missingness_rate", False, f"{type(exc).__name__}: {exc}"))

    ok = all(item.ok for item in items if item.name in {"non_empty_rows", "non_empty_cols"})
    return {"ok": ok, "items": [asdict(x) for x in items]}
''',
    )


def write_analysis(out_dir: Path) -> None:
    write_text(
        out_dir / "src" / "analysis.py",
        r'''from __future__ import annotations

from typing import Any, Dict

import pandas as pd


def basic_profile(df: pd.DataFrame) -> Dict[str, Any]:
    if df is None:
        return {"ok": False, "error": "df is None"}

    out: Dict[str, Any] = {
        "ok": True,
        "n_rows": int(df.shape[0]),
        "n_cols": int(df.shape[1]),
        "columns": [str(c) for c in df.columns],
        "dtypes": {str(k): str(v) for k, v in df.dtypes.to_dict().items()},
    }

    try:
        out["describe_numeric"] = df.describe(include=["number"]).to_dict()
    except Exception:
        out["describe_numeric"] = {}

    return out
''',
    )


def write_run_py(out_dir: Path) -> None:
    write_text(
        out_dir / "run.py",
        r'''from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.analysis import basic_profile
from src.loaders import load_tabular_from_roots
from src.validate import validate_dataframe

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "generated_manifest.json"


def main() -> None:
    if not MANIFEST.exists():
        raise SystemExit("generated_manifest.json not found")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    selected = manifest.get("selected_primary_files", [])
    data_roots = manifest.get("data_roots", [])

    output = {
        "article_id": manifest.get("article_id"),
        "generated_version": manifest.get("generated_version"),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "data_roots": data_roots,
        "runs": [],
    }

    for file_info in selected:
        df, load_result = load_tabular_from_roots(
            data_roots=data_roots,
            rel_path=file_info.get("path"),
            fmt=file_info.get("format") or "",
            file_pattern=file_info.get("file_pattern"),
        )

        validation = validate_dataframe(
            df,
            expected_columns=file_info.get("expected_columns"),
        )

        profile = basic_profile(df)

        output["runs"].append(
            {
                "file": file_info,
                "load_result": load_result.__dict__,
                "validation": validation,
                "profile": profile,
            }
        )

    (HERE / "run_output.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("Wrote run_output.json")


if __name__ == "__main__":
    main()
''',
    )


def write_all_templates(out_dir: Path, article_id: str) -> None:
    write_requirements(out_dir)
    write_readme(out_dir, article_id)
    write_src_init(out_dir)
    write_loaders(out_dir)
    write_validate(out_dir)
    write_analysis(out_dir)
    write_run_py(out_dir)
