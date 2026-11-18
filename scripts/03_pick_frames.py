#!/usr/bin/env python
"""03 抽帧：每 4 秒取样 → 只比文字区去重 → 取最静止帧 → 拼页

用法:
    python 03_pick_frames.py <视频文件> <输出目录> [--crop 1120] [--per 3] [--roi 20,52,336,190]

说明:
    --roi 是在 480x270 缩放图上的文字区 (x1,y1,x2,y2)。
    教师站在右侧时用默认值即可；换布局请先看一张图再调。
    手写动画场景下自动去重会退化，此时用 --per 3 拼页后人工合并重复。
"""
import argparse
import glob
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def sample_frames(src: str, outdir: str, every: int = 4) -> list[str]:
    os.makedirs(outdir, exist_ok=True)
    subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-i", src,
         "-vf", f"fps=1/{every},scale=480:-1", "-q:v", "6",
         os.path.join(outdir, "scan_%04d.jpg")],
        check=True,
    )
    return sorted(glob.glob(os.path.join(outdir, "scan_*.jpg")))


def pick(files: list[str], roi: tuple[int, int, int, int], win: int = 5,
         dedup: float = 5.0) -> list[int]:
    x1, y1, x2, y2 = roi
    feats, diffs, prev = [], [], None
    for f in files:
        a = np.asarray(Image.open(f).convert("L").resize((480, 270)),
                       dtype=np.float32)[y1:y2, x1:x2]
        feats.append(a)
        diffs.append(0.0 if prev is None else float(np.abs(a - prev).mean()))
        prev = a

    picks: list[int] = []
    for s in range(0, len(files), win):
        seg = diffs[s:s + win]
        if not seg:
            break
        idx = s + int(np.argmin(seg))
        if picks and np.abs(feats[idx] - feats[picks[-1]]).mean() < dedup:
            continue
        picks.append(idx)
    return picks


def build_strip(ts: list[int], wide_dir: str, out_path: str,
                top: int = 56, bottom: int = 150, cols: int = 4) -> None:
    """把每帧的标题行（单词+音标）横切出来拼成一张长图。

    用途：先一眼扫完整课词表，再回头细读需要的词条，
    避免逐页读整块板造成的重复劳动。
    """
    tiles = []
    for t in ts:
        p = os.path.join(wide_dir, f"w_{t}.jpg")
        if not os.path.exists(p):
            continue
        im = Image.open(p).crop((0, top, 1120, bottom))
        tiles.append((t, im))
    if not tiles:
        return
    w, h = tiles[0][1].size
    label = 70
    rows = (len(tiles) + cols - 1) // cols
    out = Image.new("RGB", (cols * w, rows * (h + label)), "white")
    d = ImageDraw.Draw(out)
    for i, (t, im) in enumerate(tiles):
        x, y = (i % cols) * w, (i // cols) * (h + label)
        d.text((6, y + 4), f"{t//60:02d}:{t%60:02d}", fill="black")
        out.paste(im, (x, y + 18))
    out.save(out_path, quality=90)


def export(src: str, files: list[str], picks: list[int], outdir: str,
           crop_w: int, per: int, every: int) -> int:
    wide = os.path.join(outdir, "wide")
    os.makedirs(wide, exist_ok=True)
    ts = []
    for i in picks:
        t = i * every if i else 1
        dst = os.path.join(wide, f"w_{t}.jpg")
        if not os.path.exists(dst):
            subprocess.run(
                [ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
                 "-ss", str(t), "-i", src, "-frames:v", "1",
                 "-vf", f"crop={crop_w}:720:0:0", "-q:v", "2", dst],
                check=False,
            )
        if os.path.exists(dst):
            ts.append(t)

    pages = 0
    for n in range(0, len(ts), per):
        chunk = ts[n:n + per]
        ims = [Image.open(os.path.join(wide, f"w_{t}.jpg")) for t in chunk]
        w, h = ims[0].size
        bar = 26
        out = Image.new("RGB", (w, sum(h + bar for _ in ims)), "white")
        d = ImageDraw.Draw(out)
        y = 0
        for t, im in zip(chunk, ims):
            d.rectangle([0, y, w, y + bar], fill="black")
            d.text((8, y + 7), f"{t // 60:02d}:{t % 60:02d}", fill="white")
            out.paste(im, (0, y + bar))
            y += h + bar
        pages += 1
        out.save(os.path.join(outdir, f"p_{pages:02d}.jpg"), quality=90)
    return pages, ts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("outdir")
    ap.add_argument("--every", type=int, default=4, help="每几秒取一帧")
    ap.add_argument("--crop", type=int, default=1120, help="裁切宽度（1280 宽源建议 1120）")
    ap.add_argument("--per", type=int, default=3, help="每页拼几张")
    ap.add_argument("--roi", default="20,52,336,190", help="480x270 上的文字区 x1,y1,x2,y2")
    ap.add_argument("--dedup", type=float, default=5.0)
    ap.add_argument("--strip", action="store_true",
                    help="额外生成标题条：每帧只切顶部词条行，一次看完全课词表")
    args = ap.parse_args()

    roi = tuple(int(v) for v in args.roi.split(","))
    files = sample_frames(args.src, args.outdir, args.every)
    picks = pick(files, roi, dedup=args.dedup)
    print(f"抽样 {len(files)} 帧 → 候选版面 {len(picks)}")
    pages, ts = export(args.src, files, picks, args.outdir, args.crop, args.per, args.every)
    if args.strip:
        strip_path = os.path.join(args.outdir, "strip.jpg")
        build_strip(ts, os.path.join(args.outdir, "wide"), strip_path)
        print(f"标题条：{strip_path}")
    print(f"导出 {pages} 页，在 {os.path.join(args.outdir)}")
    print("提示：手写动画场景下会有重复页，拼页后人工合并即可。")


if __name__ == "__main__":
    sys.exit(main())
