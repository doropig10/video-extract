#!/usr/bin/env python
"""04 转写：本地 whisper（faster-whisper），优先 GPU

用法:
    # 先用一小段探性能，确认能跑再上全量
    python 04_transcribe.py audio.wav out.txt --model small --probe 180
    python 04_transcribe.py audio.wav out.txt --model large-v3 --device auto

要点:
    1) GPU 需要 CUDA 运行库（pip install nvidia-cublas-cu12 nvidia-cudnn-cu12），
       并把三个目录加进 DLL 搜索路径——见 setup_dll_dirs()。
    2) 不要传文件路径给 transcribe()，会踩 av 库的 metadata_errors 不兼容；
       先用 ffmpeg 转 16k 单声道 wav，再传 numpy 数组。
    3) 模型首次下载走镜像：HF_ENDPOINT=https://hf-mirror.com
       有缓存后加 HF_HUB_OFFLINE=1 离线加载。
"""
import argparse
import os
import site
import sys
import time
import wave

import numpy as np


def setup_dll_dirs() -> None:
    """把 pip 装的 CUDA 库目录加进 DLL 搜索路径（Windows 必需）。"""
    if sys.platform != "win32":
        return
    sp = os.path.join(os.path.dirname(sys.executable), "Lib", "site-packages")
    for sub in ("nvidia/cublas/bin", "nvidia/cudnn/bin", "ctranslate2"):
        d = os.path.join(sp, *sub.split("/"))
        if os.path.isdir(d):
            try:
                os.add_dll_directory(d)
            except OSError:
                pass
            os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]


def read_wav(path: str) -> np.ndarray:
    w = wave.open(path)
    if w.getnchannels() != 1 or w.getframerate() != 16000:
        raise SystemExit("需要 16k 单声道 wav：ffmpeg -i in.m4a -ac 1 -ar 16000 -c:a pcm_s16le out.wav")
    return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("out")
    ap.add_argument("--model", default="large-v3")
    ap.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    ap.add_argument("--models-dir", default=None)
    ap.add_argument("--language", default="zh")
    ap.add_argument("--probe", type=int, default=0, help="只跑前 N 秒，测速用")
    args = ap.parse_args()

    setup_dll_dirs()
    from faster_whisper import WhisperModel

    audio = read_wav(args.wav)
    if args.probe:
        audio = audio[: args.probe * 16000]
    dur = len(audio) / 16000
    print(f"音频 {dur/60:.1f} min", flush=True)

    models_dir = args.models_dir or os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "models", "whisper")

    attempts = []
    if args.device in ("auto", "cuda"):
        attempts.append(("cuda", "float16"))
    attempts.append(("cpu", "int8"))

    model = None
    for dev, ct in attempts:
        try:
            t0 = time.time()
            model = WhisperModel(args.model, device=dev, compute_type=ct,
                                 download_root=models_dir)
            print(f"{dev}/{ct} 就绪 {time.time()-t0:.0f}s", flush=True)
            break
        except Exception as e:
            print(f"{dev} 失败: {type(e).__name__}: {str(e)[:160]}", flush=True)

    if model is None:
        raise SystemExit("GPU 与 CPU 都失败，看上面的报错")

    t1 = time.time()
    segs, _ = model.transcribe(audio, language=args.language, beam_size=5,
                               vad_filter=True, condition_on_previous_text=False)
    with open(args.out, "w", encoding="utf-8") as f:
        n = 0
        for s in segs:
            f.write(f"[{s.start:.1f}-{s.end:.1f}] {s.text.strip()}\n")
            f.flush()
            n += 1
            if n % 100 == 0:
                print(f"已写 {n} 段 / {s.end/60:.1f} min", flush=True)
    el = time.time() - t1
    print(f"完成 段数={n} 耗时={el:.0f}s 速度={dur/el:.1f}x 实时", flush=True)


if __name__ == "__main__":
    sys.exit(main())
