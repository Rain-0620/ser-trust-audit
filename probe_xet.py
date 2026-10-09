import importlib.metadata as md
import os
from pathlib import Path

print("=== packages that could hijack downloads ===")
for name in ("hf_xet", "hf-xet", "huggingface_hub", "httpx", "requests"):
    try:
        print(f"  {name:18s} {md.version(name)}")
    except Exception:
        print(f"  {name:18s} not installed")

print("\n=== download attempt with Xet disabled ===")
os.environ["HF_HUB_DISABLE_XET"] = "1"          # force plain HTTP file transfer
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")
# NOTE: keep whatever proxy the process already has; small-file tests showed it works.

from huggingface_hub import hf_hub_download

cache = Path("D:/ser-audit/.hfprobe")
cache.mkdir(parents=True, exist_ok=True)

for filename in ("preprocessor_config.json", "config.json"):
    try:
        path = hf_hub_download(
            repo_id="superb/wav2vec2-base-superb-er",
            filename=filename,
            cache_dir=str(cache / "noxet"),
        )
        size = os.path.getsize(path)
        print(f"  {filename:26s} OK   {size} bytes")
        if size == 0:
            print("      !! still empty")
    except Exception as e:
        print(f"  {filename:26s} FAIL {type(e).__name__}: {str(e)[:200]}")
