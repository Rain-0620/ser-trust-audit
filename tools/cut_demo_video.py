"""Cut the 2-hour OBS recording into a ~4.5 minute demo.

Facts this script is built on:
  * source: 1280x720, 30 fps, 1:59:09, single continuous screen recording of the AGH web UI
  * the browser tab strip (y 0-27), address bar (27-55) and bookmarks bar (55-77) carry the
    operator's personal browsing, so every segment is cropped to y>=80 and the Windows
    taskbar sliver at the bottom is cropped off too -> crop=1280:632:0:80
  * the run's timeline (session started 16:19:08, recording started 16:18:57):
        0:00-0:35   task prompt pasted, agent starts
        ~0:25       first approval (allowed-session)
        0:30-13:51  exploration: catalog, probe, sweeps, curves
        13:51-1:49  battery: 30 calls, 53 conditions  <- 95 minutes of near-identical frames
        1:49-1:59   analysis, report write attempts

Output: outputs/video/cut/*.mp4 then a concatenated outputs/video/demo_cut.mp4
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FF = ROOT / "tools" / "bin" / "ffmpeg-9.0.2-essentials_build" / "bin" / "ffmpeg.exe"
SRC = Path(r"D:\Program Files\obs-studio\2026-10-09 16-18-57.mp4")
OUT = ROOT / "outputs" / "video" / "cut"
CROP = "crop=1280:632:0:80"

# (label, source start seconds, duration seconds, extra speed factor)
SEGMENTS = [
    ("01_task_paste",     5.0,     30.0, 1.0),    # the prompt, agent wakes up
    ("02_catalog_sweep",  85.0,    45.0, 1.0),    # catalog output + first sweep
    ("03_result_tables",  365.0,   60.0, 1.0),    # sweep result tables
    ("04_curves",         695.0,   45.0, 1.0),    # curve refinement
    ("05_battery",        831.0, 5735.0, 285.0),  # 95 min -> ~20 s
    ("06_analysis",      6740.0,   60.0, 1.0),    # exploratory vs confirmatory, write approval
]


def run(args: list[str], label: str) -> bool:
    p = subprocess.run([str(FF), "-y", "-v", "error", *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode != 0:
        print(f"  {label}: FAILED\n{p.stderr[-1500:]}")
        return False
    print(f"  {label}: ok")
    return True


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    made = []
    total = 0.0

    print(f"source: {SRC.name}")
    for label, start, dur, speed in SEGMENTS:
        dst = OUT / f"{label}.mp4"
        vf = f"{CROP},fps=30" if speed == 1.0 else f"{CROP},setpts=PTS/{speed},fps=30"
        ok = run(["-ss", str(start), "-t", str(dur), "-i", str(SRC),
                  "-vf", vf, "-an",
                  "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                  "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                  str(dst)], label)
        if ok:
            made.append(dst)
            out_dur = dur / speed
            total += out_dur
            print(f"      {start:.0f}s +{dur:.0f}s @ {speed}x  ->  {out_dur:.1f}s")

    if not made:
        print("nothing produced")
        return 1

    listfile = OUT / "concat.txt"
    listfile.write_text("".join(f"file '{p.as_posix()}'\n" for p in made), encoding="utf-8")
    final = ROOT / "outputs" / "video" / "demo_cut.mp4"
    ok = run(["-f", "concat", "-safe", "0", "-i", str(listfile), "-c", "copy",
              "-movflags", "+faststart", str(final)], "concat")
    if not ok:
        return 1

    size = final.stat().st_size / 1e6
    print(f"\nfinal: {final}")
    print(f"  duration ~{total:.1f}s  ({total/60:.2f} min), size {size:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
