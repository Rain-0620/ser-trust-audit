"""Build the final demo video.

Sources
  MAIN  : the 2-hour OBS recording of the whole agent run (1280x720, 30 fps)
  TRACE : a ~24 s screen recording of the AGH Trace view of the same session,
          which is the only footage that contains the END (report approved and written)

Why the extra work compared with cut_demo_video.py
  * the browser tab strip / address bar / bookmarks bar carry the operator's personal
    browsing, so both recordings are cropped to y >= 80
  * the first cut stopped at the exploratory/confirmatory comparison and never showed
    the result; the results slides and the trace footage close that gap
  * subtitles are burned in so the video reads without narration

Every number on the result slides is taken from the run's own outputs:
  outputs/battery/report_Session5_pc0_seed20261008.md   and   trust_boundary_report.md
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import report_render  # noqa: E402  (local module, renders the Markdown report to a tall PNG)

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(r"D:\ser-audit")
FF = ROOT / "tools" / "bin" / "ffmpeg-9.0.2-essentials_build" / "bin" / "ffmpeg.exe"
MAIN = Path(r"D:\Program Files\obs-studio\2026-10-09 16-18-57.mp4")
TRACE = Path(r"D:\Program Files\obs-studio\2026-10-09 18-37-49.mp4")
OUT = ROOT / "outputs" / "video" / "final"
SUBDIR = OUT / "sub"
CARDDIR = OUT / "cards"

W, H = 1280, 720
CROP = "crop=1280:632:0:80"
PAD = "pad=1280:720:0:44:color=0x0b1020"
FONT_R = "C:/Windows/Fonts/msyh.ttc"
FONT_B = "C:/Windows/Fonts/msyhbd.ttc"

BG = (11, 16, 32)
BG2 = (22, 32, 58)
WHITE = (245, 248, 255)
GREY = (156, 168, 192)
ACCENT = (94, 208, 255)
WARM = (255, 168, 118)
GREEN = (126, 226, 168)


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size, index=0)


def wrap(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        if draw.textlength(cur + ch, font=f) <= max_w:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def gradient(w: int, h: int, top: tuple, bot: tuple) -> Image.Image:
    img = Image.new("RGB", (1, h))
    px = img.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        px[0, y] = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
    return img.resize((w, h), Image.BILINEAR)


# ---------------------------------------------------------------- subtitle strips

def subtitle_png(text: str, path: Path) -> None:
    """Transparent 1280x720 overlay: a dark bar with wrapped white text near the bottom."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font(FONT_R, 30)
    lines = wrap(d, text, f, 1130)
    lh = 44
    block_h = lh * len(lines) + 26
    top = H - 70 - block_h
    d.rounded_rectangle([50, top, W - 50, top + block_h], radius=14, fill=(8, 12, 24, 205))
    y = top + 13
    for ln in lines:
        tw = d.textlength(ln, font=f)
        d.text(((W - tw) / 2, y), ln, font=f, fill=(255, 255, 255, 255))
        y += lh
    img.save(path)


# ---------------------------------------------------------------- cards

def title_card(path: Path) -> None:
    img = gradient(W, H, BG, BG2).convert("RGBA")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 8], fill=ACCENT)
    d.text((80, 196), "用 Agent 审计一个语音情感识别模型", font=font(FONT_B, 52), fill=WHITE)
    d.line([80, 282, 300, 282], fill=ACCENT, width=4)
    d.text((80, 308), "SER 信任边界审计 · Agnes 3.0 Flash × AGH", font=font(FONT_R, 30), fill=ACCENT)
    d.text((80, 366), "被审计对象：superb/wav2vec2-base-superb-er（IEMOCAP Session5）",
           font=font(FONT_R, 24), fill=GREY)
    d.text((80, 404), "审计工具 audit.py 与 Agent 行为协议 SKILL.md 由本团队自研",
           font=font(FONT_R, 24), fill=GREY)
    d.text((80, 600), "目标：这个模型在什么条件下不可信，用可复现的证据说清楚",
           font=font(FONT_R, 26), fill=WARM)
    img.convert("RGB").save(path)


def findings_card(path: Path) -> None:
    img = gradient(W, H, BG, BG2).convert("RGBA")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 8], fill=ACCENT)
    d.text((60, 44), "发现：模型有两种不同的失效方式", font=font(FONT_B, 44), fill=WHITE)
    d.text((60, 112), "干净基线 balanced accuracy 0.776（随机水平 0.25，n=1241）",
           font=font(FONT_R, 26), fill=GREY)

    d.rounded_rectangle([60, 168, 610, 396], radius=16, fill=(28, 22, 26),
                        outline=(214, 122, 92), width=2)
    d.text((90, 190), "签名 A ｜ 加性噪声", font=font(FONT_B, 30), fill=WARM)
    d.text((90, 238), "模型只会答 happy", font=font(FONT_B, 34), fill=WHITE)
    d.text((90, 296), "gaussian_snr ≤ 2 dB", font=font(FONT_R, 24), fill=GREY)
    d.text((90, 328), "white_noise ≥ 0.02", font=font(FONT_R, 24), fill=GREY)
    d.text((90, 360), "触发规则：一个类占满输出（占比 ≥ 0.80）", font=font(FONT_R, 20), fill=GREY)

    d.rounded_rectangle([670, 168, 1220, 396], radius=16, fill=(20, 26, 34),
                        outline=(92, 168, 214), width=2)
    d.text((700, 190), "签名 B ｜ 带宽 / 编解码 / 变速", font=font(FONT_B, 30), fill=ACCENT)
    d.text((700, 238), "模型只会答 neutral", font=font(FONT_B, 34), fill=WHITE)
    d.text((700, 296), "lowpass ≤ 850 Hz　mp3 ≤ 8 kbps", font=font(FONT_R, 24), fill=GREY)
    d.text((700, 328), "timestretch ≥ 1.5×", font=font(FONT_R, 24), fill=GREY)
    d.text((700, 360), "触发规则：熵 ≤ 0.30（自信地答错）", font=font(FONT_R, 20), fill=GREY)

    d.rounded_rectangle([60, 424, 1220, 556], radius=14, fill=(16, 22, 38))
    d.text((88, 446), "两种机制落进两个不同的常数类，触发的判据也不同 ——", font=font(FONT_R, 26), fill=WHITE)
    d.text((88, 486), "低通族准确率还有 0.44–0.50（高于随机水平一倍），看起来只是「变差」，",
           font=font(FONT_R, 24), fill=GREY)
    d.text((88, 518), "实际已经不判断了。只监控准确率的系统抓不到这一种。", font=font(FONT_R, 24), fill=GREY)
    img.convert("RGB").save(path)


def boundary_card(path: Path) -> None:
    img = gradient(W, H, BG, BG2).convert("RGBA")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 8], fill=ACCENT)
    d.text((60, 40), "信任边界：以下条件下不应采信该模型", font=font(FONT_B, 42), fill=WHITE)
    d.text((60, 104), "阈值均为相邻采样点之间的推断，不是观测值", font=font(FONT_R, 24), fill=GREY)

    rows = [
        ("SNR < ~3.5 dB", "塌缩到 happy（占比 0.81）"),
        ("低通截止 < ~875 Hz", "塌缩到 neutral（熵 0.29）"),
        ("MP3 比特率 < ~12 kbps", "塌缩到 neutral（占比 0.84）"),
        ("白噪声幅度 > ~0.01", "塌缩到 happy（占比 0.80）"),
        ("时间拉伸 > ~1.4×", "塌缩到 neutral（占比 0.81）"),
    ]
    y = 152
    for cond, eff in rows:
        d.rounded_rectangle([60, y, 1220, y + 52], radius=10, fill=(24, 20, 24))
        d.text((84, y + 11), cond, font=font(FONT_B, 26), fill=(255, 190, 150))
        d.text((560, y + 13), eff, font=font(FONT_R, 24), fill=WHITE)
        y += 62

    d.rounded_rectangle([60, y + 8, 1220, y + 68], radius=10, fill=(18, 28, 26))
    d.text((84, y + 20), "能耐受：高通 ≤ 800 Hz · 削波 ≤ 30% · MP3 ≥ 32 kbps · 音高 ±2 半音",
           font=font(FONT_R, 24), fill=GREEN)

    d.text((60, 588), "阈值依赖评测集：lowpass:900 Hz 在全量 n=1241 判「健康」，在平衡子集 n=192 判「塌缩」",
           font=font(FONT_R, 22), fill=GREY)
    d.text((60, 620), "（P(deg)=0.58，自身如同掷硬币）；跨 5 个 session、5 次抽样复核均只有 2/5 复现。",
           font=font(FONT_R, 22), fill=GREY)
    img.convert("RGB").save(path)


def end_card(path: Path) -> None:
    img = gradient(W, H, BG, BG2).convert("RGBA")
    d = ImageDraw.Draw(img)
    d.rectangle([0, H - 8, W, H], fill=ACCENT)
    d.text((80, 250), "SER 信任边界审计", font=font(FONT_B, 50), fill=WHITE)
    d.line([80, 330, 320, 330], fill=ACCENT, width=4)
    d.text((80, 364), "路径：catalog → probe → sweep → curve → battery → 报告",
           font=font(FONT_R, 27), fill=GREY)
    d.text((80, 408), "53 个条件 · n=1241 · 全程经 AGH 执行并留痕", font=font(FONT_R, 27), fill=GREY)
    d.text((80, 452), "Agnes 3.0 Flash × AGH ｜ 审计工具与协议由本团队自研", font=font(FONT_R, 27), fill=ACCENT)
    img.convert("RGB").save(path)


# ---------------------------------------------------------------- ffmpeg helpers

def run(args: list[str], label: str) -> bool:
    p = subprocess.run([str(FF), "-y", "-v", "error", *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode != 0:
        print(f"  {label}: FAILED\n{p.stderr[-1800:]}")
        return False
    return True


def video_segment(src: Path, start: float, dur: float, speed: float,
                  sub: Path | None, dst: Path, label: str) -> bool:
    """crop -> pad -> (speed) -> 30fps -> burn subtitle."""
    chain = [CROP, PAD, "fps=30"]
    if speed != 1.0:
        chain.insert(2, f"setpts=PTS/{speed}")
    if sub is None:
        return run(["-ss", str(start), "-t", str(dur), "-i", str(src),
                    "-vf", ",".join(chain), "-an",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-r", "30", str(dst)], label)
    args: list[str] = ["-ss", str(start), "-t", str(dur), "-i", str(src), "-i", str(sub),
                       "-filter_complex",
                       f"[0:v]{','.join(chain)}[base];[base][1:v]overlay=0:0:format=auto[out]",
                       "-map", "[out]", "-an",
                       "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                       "-pix_fmt", "yuv420p", "-r", "30", str(dst)]
    return run(args, label)


def still_segment(png: Path, dur: float, dst: Path, label: str) -> bool:
    return run(["-loop", "1", "-t", str(dur), "-i", str(png),
                "-vf", "fps=30", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-r", "30", str(dst)], label)


def scroll_segment(png: Path, doc_h: int, dur: float, sub: Path | None,
                   dst: Path, label: str) -> bool:
    """Scroll a 1280x632 window from the top to the bottom of a tall PNG."""
    span = max(doc_h - 632, 1)
    expr = f"min((ih-632)*t/{dur}\\,{span})"
    chain = f"fps=30,crop=1280:632:0:'{expr}',pad=1280:720:0:44:color=0x0b1020"
    base = ["-loop", "1", "-t", str(dur), "-i", str(png)]
    tail = ["-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", "30", str(dst)]
    if sub is None:
        return run([*base, "-vf", chain, *tail], label)
    return run([*base, "-i", str(sub),
                "-filter_complex", f"[0:v]{chain}[base];[base][1:v]overlay=0:0:format=auto[out]",
                "-map", "[out]", *tail], label)


# ---------------------------------------------------------------- main

SEGMENTS = [
    # (label, source, start, duration, speed, subtitle)
    ("01_task",      MAIN,    8.0,   25.0, 1.0,
     "① 把任务交给 Agent —— 测什么、怎么测，提示词没有指定"),
    ("02_planning",  MAIN,   96.0,   26.0, 1.0,
     "② 读完工具清单，自己选定第一轮扰动：不同失效机制各选一个"),
    ("03_metrics",   MAIN,  336.0,   24.0, 1.0,
     "③ 读懂多指标：区分「不确定」与「已塌缩」—— 只看准确率分不出这两种"),
    ("04_curve",     MAIN,  398.0,   30.0, 1.0,
     "④ 用 curve 加密采样定位阈值；发现低通 8000 Hz 与干净音频逐位相同，"
     "判定「变换未生效」而不是「模型鲁棒」"),
    ("05_defect",    MAIN,  688.0,   30.0, 1.0,
     "⑤ 撞上工具缺陷：MP3 曲线族全部报错 → 主动上报「这是工具的缺陷，不是关于模型的结论」"),
    ("06_battery",   MAIN,  831.0, 5735.0, 380.0,
     "⑥ 全量确认：53 个条件 × 1241 条话语（单次调用有超时上限，分 30 次调用跑完）"),
    ("07_compare",   MAIN, 6798.0,   28.0, 1.0,
     "⑦ 自己对照探索(n=96)与确认(n=1241)：边缘判定翻转、欠功效变显著 → 只采信确认阶段"),
    ("08_trace",     TRACE,   0.0,   24.4, 1.0,
     "⑧ Trace 视图：每一步工具调用、审批与输出全程留痕；报告经人工批准后写入"),
]

CARDS = [
    ("00_title",   "title",    4.0),
    ("09_findings", "findings", 22.0),
    ("10_boundary", "boundary", 20.0),
    ("11_end",      "end",       4.0),
]

# the report itself, scrolled top to bottom, placed after the summary cards
REPORT_MD = ROOT / "trust_boundary_report.md"
REPORT_DUR = 34.0
REPORT_SUBTITLE = "⑨ 报告原文（Agent 输出）：trust_boundary_report.md —— 自上而下完整滚动"


def main() -> int:
    for p in (OUT, SUBDIR, CARDDIR):
        p.mkdir(parents=True, exist_ok=True)
    if not FF.exists():
        print(f"ffmpeg missing: {FF}")
        return 1
    for s in (MAIN, TRACE):
        if not s.exists():
            print(f"source missing: {s}")
            return 1

    print("== cards ==")
    card_paths: dict[str, Path] = {}
    for maker, key in ((title_card, "title"), (findings_card, "findings"),
                       (boundary_card, "boundary"), (end_card, "end")):
        p = CARDDIR / f"{key}.png"
        maker(p)
        card_paths[key] = p
        print(f"  {key}.png")

    # the report itself, rendered to one tall image and scrolled later
    report_png = CARDDIR / "report_full.png"
    doc_h = report_render.render(REPORT_MD, report_png)
    print(f"  report_full.png  (1280x{doc_h})")

    print("== subtitles ==")
    sub_paths: dict[str, Path] = {}
    for label, _src, _st, _du, _sp, text in SEGMENTS:
        if not text:
            continue
        p = SUBDIR / f"{label}.png"
        subtitle_png(text, p)
        sub_paths[label] = p
        print(f"  {label}.png")
    rep_sub = SUBDIR / "12_report.png"
    subtitle_png(REPORT_SUBTITLE, rep_sub)
    print("  12_report.png")

    made: list[Path] = []
    total = 0.0

    print("== build ==")
    # 1) title
    dst = OUT / "00_title.mp4"
    if still_segment(card_paths["title"], 4.0, dst, "00_title"):
        made.append(dst); total += 4.0
        print(f"  00_title  (card) 4.0s")

    # 2) recorded segments in order
    for label, src, st, du, sp, _t in SEGMENTS:
        folder = OUT
        dst = folder / f"{label}.mp4"
        sub = sub_paths.get(label)
        ok = video_segment(src, st, du, sp, sub, dst, label)
        if not ok:
            return 1
        out_dur = du / sp
        made.append(dst); total += out_dur
        print(f"  {label:13s} {st:7.0f}s +{du:6.0f}s @{sp:5.1f}x -> {out_dur:6.1f}s")

    # 3) result cards: findings + trust boundary
    for label, key, dur in (("09_findings", "findings", 22.0),
                            ("10_boundary", "boundary", 20.0)):
        dst = OUT / f"{label}.mp4"
        if still_segment(card_paths[key], dur, dst, label):
            made.append(dst); total += dur
            print(f"  {label:13s} (card) {dur:.1f}s")

    # 4) the report itself, scrolled
    dst = OUT / "12_report.mp4"
    if scroll_segment(report_png, doc_h, REPORT_DUR, rep_sub, dst, "12_report"):
        made.append(dst); total += REPORT_DUR
        print(f"  12_report     (scroll {doc_h}px) {REPORT_DUR:.1f}s")

    # 5) end card
    dst = OUT / "11_end.mp4"
    if still_segment(card_paths["end"], 4.0, dst, "11_end"):
        made.append(dst); total += 4.0
        print(f"  11_end        (card) 4.0s")

    # 4) concat
    listfile = OUT / "concat.txt"
    listfile.write_text("".join(f"file '{p.as_posix()}'\n" for p in made), encoding="utf-8")
    merged = OUT / "demo_merged.mp4"
    if not run(["-f", "concat", "-safe", "0", "-i", str(listfile), "-c", "copy",
                "-movflags", "+faststart", str(merged)], "concat"):
        return 1

    # 5) add a silent stereo track (some players/uploaders expect an audio stream)
    final = ROOT / "outputs" / "video" / "demo_final.mp4"
    if not run(["-i", str(merged), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                "-shortest", "-c:v", "copy", "-c:a", "aac", "-b:a", "96k",
                "-movflags", "+faststart", str(final)], "mux-audio"):
        return 1

    size = final.stat().st_size / 1e6
    print(f"\nfinal: {final}")
    print(f"  ~{total:.1f}s ({total/60:.2f} min), {size:.1f} MB, {len(made)} segments")
    return 0


if __name__ == "__main__":
    sys.exit(main())
