#!/usr/bin/env python
"""06 转写摘要：把口语转写压成"有信息量"的片段，减少 AI 阅读量

规则（可解释、可审计，不做语义压缩）：
  1. 去掉纯口头禅（好 / 再来 / 同学 / 对吗 / 是不是 / 快点 …）
  2. 连续重复只留一条（她讲一个词会反复念十几遍）
  3. 保留所有含英文或数字的行（词、音标、例句、时间戳都在这）
  4. 每 10 秒并成一段，标时间范围，便于回原片定位

用法:
    python 06_digest.py transcript.txt > transcript_digest.txt
"""
import argparse
import io
import re
import sys

FILLER = {
    "好", "好嘞", "好啊", "再来", "同学", "同学们", "好不好", "对吗", "是不是",
    "是吗", "嗯", "哦", "哎", "呀", "吧", "啊", "快点", "继续", "来", "走",
    "听", "听吗", "听见吗", "别走", "别急", "没问题", "ok", "对", "是的",
    "好继续", "我们看一下", "看一下", "想一想", "记住了", "对不对",
}


def is_english(s: str) -> bool:
    return bool(re.search(r"[A-Za-z]", s))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--window", type=int, default=10, help="合并窗口（秒），默认 10")
    args = ap.parse_args()

    raw = io.open(args.src, encoding="utf-8").read().splitlines()
    kept = []
    prev = ""
    for line in raw:
        m = re.match(r"\[([\d.]+)-([\d.]+)\]\s*(.*)", line.strip())
        if not m:
            continue
        t0, t1, text = float(m.group(1)), float(m.group(2)), m.group(3).strip()
        text = re.sub(r"\s+", " ", text)
        low = text.lower().strip("。！？， ")
        if low in FILLER:
            continue
        # 短行可能正是词义（"和谐"、"目标"），含英文的一律留
        if not is_english(text) and len(low) <= 2:
            continue
        if text == prev:            # 连续重复
            continue
        prev = text
        kept.append((t0, t1, text))

    # 按时间窗合并，窗口内保留全部文本
    out, buf, wt, last_t1 = [], [], None, 0.0
    for t0, t1, text in kept:
        if wt is None:
            wt = t0
        if t0 - wt >= args.window and buf:
            out.append((wt, last_t1, " ".join(buf)))
            buf, wt = [], t0
        buf.append(text)
        last_t1 = t1
    if buf:
        out.append((wt, last_t1, " ".join(buf)))

    for t0, t1, text in out:
        print(f"[{int(t0)//60:02d}:{int(t0)%60:02d}-{int(t1)//60:02d}:{int(t1)%60:02d}] {text}")

    print(f"\n# 原始 {len(raw)} 段 → 摘要 {len(out)} 段", file=sys.stderr)


if __name__ == "__main__":
    main()
