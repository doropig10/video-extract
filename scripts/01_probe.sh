#!/usr/bin/env bash
# 01 探测：看清有什么，再决定下什么
# 用法: ./01_probe.sh <链接> [分P号]
set -euo pipefail
URL="${1:?用法: 01_probe.sh <链接> [分P号]}"
P="${2:-}"

ARGS=()
[ -n "$P" ] && ARGS=(-I "$P")

echo "=== 格式清单 ==="
python -m yt_dlp --no-warnings "${ARGS[@]}" -F "$URL"

echo
echo "=== 字幕轨（只显示 danmaku 就是没字幕） ==="
python -m yt_dlp --no-warnings --list-subs "$URL" | tail -6

echo
echo "=== 元信息 ==="
python -m yt_dlp --no-warnings "${ARGS[@]}" --skip-download \
  --print "%(title)s | %(duration)s s | %(uploader)s" "$URL"
