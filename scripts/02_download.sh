#!/usr/bin/env bash
# 02 取流：音频与视频分开下，不合并
# 用法: ./02_download.sh <链接> <分P号> <输出目录>
set -euo pipefail
URL="${1:?用法: 02_download.sh <链接> <分P号> <输出目录>}"
P="${2:?缺分P号}"
OUT="${3:?缺输出目录}"
mkdir -p "$OUT"

echo "=== 音频（最高码率，单文件，无需 ffmpeg 合并） ==="
python -m yt_dlp -I "$P" -f "ba" -o "$OUT/%(id)s.%(ext)s" "$URL"

echo "=== 视频（720P，读板书用；只取视频流） ==="
python -m yt_dlp -I "$P" -f "30064" -o "$OUT/src_%(id)s.%(ext)s" "$URL"

ls -lh "$OUT"
