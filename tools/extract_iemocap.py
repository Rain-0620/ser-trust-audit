#!/usr/bin/env python
"""Extract the IEMOCAP session archives, skipping video (avi) and MoCap payload.

Source : F:\\BaiduNetdiskDownload\\Session{1..5}.zip + Documentation.zip
Target : D:\\ser-audit\\data\\IEMOCAP\\  (top level stays Session1 .. Session5)

Kept   : EmoEvaluation labels, transcriptions, dialogue & sentence wav,
         forced alignment, documentation.
Skipped: anything under a directory named 'avi' or starting with 'MOCAP'
         (video + motion-capture data, useless for the audio SER audit,
          several GB per session).

Usage:  python extract_iemocap.py
Re-running is safe: existing files are overwritten.
"""
from __future__ import annotations

import sys
import time
import zipfile
from pathlib import Path

SRC = Path(r"F:\BaiduNetdiskDownload")
DST = Path(r"D:\ser-audit\data\IEMOCAP")

SKIP_COMPONENTS = {"avi"}
SKIP_PREFIXES = ("mocap",)


def should_skip(name: str) -> bool:
    for part in name.split("/"):
        low = part.lower()
        if low in SKIP_COMPONENTS or any(low.startswith(p) for p in SKIP_PREFIXES):
            return True
    return False


def extract_one(zip_path: Path, dst: Path) -> tuple[int, int, float]:
    kept = 0
    t0 = time.time()
    with zipfile.ZipFile(zip_path) as zf:
        infos = zf.infolist()
        keep = [i for i in infos if not should_skip(i.filename)]
        for info in keep:
            zf.extract(info, dst)
            kept += 1
        skipped = len(infos) - kept
    return kept, skipped, time.time() - t0


def main() -> int:
    dst = DST
    dst.mkdir(parents=True, exist_ok=True)
    jobs = [SRC / f"Session{i}.zip" for i in range(1, 6)] + [SRC / "Documentation.zip"]
    grand_kept = 0
    t_start = time.time()
    for z in jobs:
        if not z.exists():
            print(f"MISSING  {z}")
            return 1
        kept, skipped, dt = extract_one(z, dst)
        grand_kept += kept
        print(f"{z.name:20s} kept={kept:6d}  skipped={skipped:6d}  {dt:6.1f}s", flush=True)
    print(f"TOTAL kept={grand_kept} files in {time.time() - t_start:.1f}s -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
