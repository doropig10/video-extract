#!/usr/bin/env python
"""05 OCR：把板面页整页转文字（不用视觉模型逐页读）

用法:
    python 05_ocr.py <frames目录> <输出.txt>

说明:
    - 依赖 rapidocr-onnxruntime（onnxruntime 版，无需 paddle）
    - 中文准确率高，**音标（IPA）基本认不出**，需回原图补
    - 重复版面（同一块板子停留数分钟）会重复输出，脚本按行去重
    - 输出按时间戳分段，便于和转写稿对齐
"""
import argparse
import glob
import os
import re
import sys
import time
import multiprocessing


def ts_of(name: str) -> str:
    m = re.search(r"(\d{2,4})", os.path.basename(name))
    if not m:
        return ""
    v = int(m.group(1))
    return f"{v // 60:02d}:{v % 60:02d}" if v > 59 else ""


def _ocr_one(path: str):
    """单页 OCR，在子进程里跑；引擎在进程内首次调用时初始化。"""
    from rapidocr_onnxruntime import RapidOCR
    global _ENGINE
    try:
        eng = _ENGINE
    except NameError:
        eng = _ENGINE = RapidOCR()
    res, _ = eng(path)
    items = []
    for item in (res or []):
        txt = str(item[1]).strip()
        score = float(item[2]) if len(item) > 2 else 1.0
        items.append((txt, score))
    return os.path.basename(path), items


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("frames_dir")
    ap.add_argument("out")
    ap.add_argument("--min-score", type=float, default=0.55, help="低于此置信度丢弃")
    ap.add_argument("--workers", type=int, default=1,
                    help="进程数，默认 1。实测 4 进程比 1 进程更慢"
                         "（onnxruntime 内部已多线程，再叠进程只是抢 CPU）")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.frames_dir, "p_*.jpg")))
    if not files:
        raise SystemExit("没找到 p_*.jpg，先跑 03_pick_frames.py")

    workers = max(1, args.workers)
    t0 = time.time()
    if workers > 1:
        try:
            with multiprocessing.Pool(workers) as pool:
                results = pool.map(_ocr_one, files)
        except Exception as exc:  # 受限环境（沙箱）常禁止 multiprocessing 开管道
            print(f"多进程不可用（{type(exc).__name__}），退回单进程", file=sys.stderr)
            workers = 1
            results = [_ocr_one(f) for f in files]
    else:
        results = [_ocr_one(f) for f in files]
    print(f"OCR {len(files)} 页 / {workers} 进程 → {time.time()-t0:.0f}s")

    seen = set()
    total = 0
    with open(args.out, "w", encoding="utf-8") as f:
        for name, items in results:
            if not items:
                continue
            f.write(f"\n===== {name} =====\n")
            for txt, score in items:
                if score < args.min_score:
                    continue
                if re.fullmatch(r"[\d:A-Za-z]{0,6}", txt) or "晓艳英语" in txt or "学丞" in txt:
                    continue
                if txt in seen:
                    continue
                seen.add(txt)
                f.write(txt + "\n")
                total += 1
            f.flush()
    print(f"完成：{len(files)} 页 → {total} 行去重文本 → {args.out}")


if __name__ == "__main__":
    sys.exit(main())
