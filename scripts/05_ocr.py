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


def ts_of(name: str) -> str:
    m = re.search(r"(\d{2,4})", os.path.basename(name))
    if not m:
        return ""
    v = int(m.group(1))
    return f"{v // 60:02d}:{v % 60:02d}" if v > 59 else ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("frames_dir")
    ap.add_argument("out")
    ap.add_argument("--min-score", type=float, default=0.55, help="低于此置信度丢弃")
    args = ap.parse_args()

    from rapidocr_onnxruntime import RapidOCR

    eng = RapidOCR()
    files = sorted(glob.glob(os.path.join(args.frames_dir, "p_*.jpg")))
    if not files:
        raise SystemExit("没找到 p_*.jpg，先跑 03_pick_frames.py")

    seen = set()
    total = 0
    with open(args.out, "w", encoding="utf-8") as f:
        for path in files:
            res, _ = eng(path)
            if not res:
                continue
            f.write(f"\n===== {os.path.basename(path)} =====\n")
            for item in res:
                txt = str(item[1]).strip()
                score = float(item[2]) if len(item) > 2 else 1.0
                if not txt or score < args.min_score:
                    continue
                # 去水印与页码噪声
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
