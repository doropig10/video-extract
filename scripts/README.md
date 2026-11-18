# scripts

四个脚本，按顺序用。都能单独跑，参数见各文件头部注释。

```
01_probe.sh <链接> [分P号]
    看清格式、字幕、时长。先跑这个，别急着下。

02_download.sh <链接> <分P号> <输出目录>
    音频 + 720P 视频分开下，不合并。

03_pick_frames.py <视频> <输出目录> [--crop 1120] [--per 3] [--every 4]
    抽帧 → 只比文字区去重 → 取最静止帧 → 拼页。

04_transcribe.py <16k单声道.wav> <输出.txt> [--model large-v3] [--probe 180]
    本地 whisper，自动优先 GPU，失败退 CPU。
```

## 依赖

```bash
pip install yt-dlp imageio-ffmpeg numpy pillow faster-whisper
# 想用 GPU 再加：
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

## 三个必须知道的坑

1. **命令走 `python -m yt_dlp`**，不要写裸 `yt-dlp`——很多机器上它不在 PATH。
2. **音频先转 16k 单声道 wav**，不要把 m4a 路径直接喂给 whisper（会踩 `av` 库的 `metadata_errors` 不兼容）。
3. **CUDA 库要手动加 DLL 目录**（`04_transcribe.py` 里已处理），否则报 `cublas64_12.dll is not found`；真正的路径是 `Lib\site-packages\nvidia\cublas\bin`。

## 测过的速度（RTX 4060 Laptop 8G + 32 核 CPU，43 分钟音频）

| 配置 | 耗时 | 倍数 |
|---|---|---|
| small / CPU int8 | 约 8 分钟 | 6x |
| small / GPU float16 | 约 2 分钟 | 21.9x |
| large-v3 / GPU float16 | 3 分 53 秒 | 11x |

结论：**能上 GPU 就上 large-v3**——比 small 在 CPU 上还快，质量高一档。
