from pathlib import Path

p = Path("slide10_execute_validation.py")
text = p.read_text(encoding="utf-8")

start = text.index("def load_dataframe(path: Path, suffix: str):")
end = text.index("\ndef normalize_col_name", start)

new_func = '''def read_csv_safely(path: Path, **kwargs):
    if kwargs.get("engine") == "python":
        return pd.read_csv(path, **kwargs)
    return pd.read_csv(path, low_memory=False, **kwargs)


def load_dataframe(path: Path, suffix: str):
    suffix = suffix.lower().strip()

    if suffix == ".csv":
        attempts = [
            {"sep": ",", "encoding": "utf-8"},
            {"sep": None, "engine": "python", "encoding": "utf-8"},
            {"sep": ",", "encoding": "latin1"},
            {"sep": None, "engine": "python", "encoding": "latin1"},
        ]
        last_err = None
        for kwargs in attempts:
            try:
                return read_csv_safely(path, **kwargs)
            except Exception as e:
                last_err = e
        raise last_err

    if suffix == ".tsv":
        attempts = [
            {"sep": "\\t", "encoding": "utf-8"},
            {"sep": "\\t", "encoding": "latin1"},
        ]
        last_err = None
        for kwargs in attempts:
            try:
                return read_csv_safely(path, **kwargs)
            except Exception as e:
                last_err = e
        raise last_err

    if suffix == ".xlsx":
        return pd.read_excel(path)

    raise ValueError("Unsupported suffix for this experiment: " + suffix)
'''

text = text[:start] + new_func + text[end:]
p.write_text(text, encoding="utf-8")

print("patched")
