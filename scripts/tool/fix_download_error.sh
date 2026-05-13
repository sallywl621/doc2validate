python - <<'PY'
from pathlib import Path
import json

root = Path("data/downloaded_artifacts")

remove_status = {
    "failed",
    "skipped",
}

for manifest in root.rglob("ARTIFACT_DOWNLOAD_MANIFEST.json"):
    data = json.loads(manifest.read_text())
    resources = data.get("resources", [])

    # 保留任何已经 downloaded 的目录
    if any(r.get("status") == "downloaded" for r in resources):
        continue

    # 只删除没有下载成功的 manifest，让它下次可重跑
    manifest.unlink()
    print("removed manifest:", manifest)
PY
