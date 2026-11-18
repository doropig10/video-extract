#!/usr/bin/env bash
# 安装依赖并自检
# 用法: ./install.sh          仅 CPU
#       ./install.sh --gpu    同时装 CUDA 运行库（约 1.2GB，NVIDIA 显卡）
set -euo pipefail
cd "$(dirname "$0")"

echo "== Python =="
python -c "import sys; assert sys.version_info>=(3,10), '需要 Python 3.10+'; print(sys.version.split()[0], 'ok')"

echo "== 安装依赖 =="
python -m pip install -r requirements.txt

if [ "${1:-}" = "--gpu" ]; then
  echo "== 安装 CUDA 运行库（1.2GB，慢）=="
  python -m pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
fi

echo "== 自检 =="
python - <<'PY'
import shutil, sys
try:
    import yt_dlp; print("yt-dlp        ok")
except ImportError: print("yt-dlp        缺失")
try:
    import imageio_ffmpeg as f
    print("ffmpeg        ok ->", f.get_ffmpeg_exe())
except ImportError: print("ffmpeg        缺失")
try:
    import numpy, PIL; print("numpy/pillow  ok")
except ImportError: print("numpy/pillow  缺失")
try:
    import faster_whisper; print("faster-whisper ok")
except ImportError: print("faster-whisper 缺失")

if sys.platform == "win32":
    print("提示：本项目的 01/02 是 bash 脚本，Windows 下需用 Git Bash 运行")
PY

echo
echo "装完了。试跑："
echo '  python extract.py "<链接>" -p 1 --probe-only'
