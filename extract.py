#!/usr/bin/env python
"""VideoExtract · 一条命令从视频里取料

用法:
    python extract.py "<链接>" -p 23 --all
    python extract.py "<链接>" -p 23 --audio --transcribe large-v3
    python extract.py "<链接>" -p 23 --probe-only

产出（默认在 outputs/BVxxxx_p23/）:
    audio.m4a        最高码率音轨，单文件
    src.mp4          720P 视频流（读板书用）
    a16k.wav         16k 单声道，转写输入
    transcript.txt   带时间戳文本
    frames/          抽帧拼页（p_01.jpg ...）

设计取向：所有步骤都能单独跑，不必一次到底。失败只影响那一步。
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "scripts")
MODELS = os.path.join(HERE, "models", "whisper")

# 允许指定解释器：沙箱里的 AI 常常自带一个缺依赖的 Python，
# 用 VX_PYTHON 指到系统已装好的那一个，可跳过重复安装。
PY = os.environ.get("VX_PYTHON") or sys.executable


def sh(cmd: list[str], **kw) -> int:
    print("$", " ".join(cmd), flush=True)
    return subprocess.run(cmd, **kw).returncode


def ytdlp(*args: str) -> int:
    """直接用 yt-dlp 模块，不经过 bash 脚本（沙箱里常常没有 bash）。"""
    return sh([PY, "-m", "yt_dlp", "--no-warnings", *args])


def ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def video_id(url: str, p: str) -> str:
    import re
    m = re.search(r"(BV[0-9A-Za-z]+)", url)
    return f"{m.group(1)}_p{p}" if m else "video"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="从 B 站视频取音频、字幕、板书帧、转写文本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("url")
    ap.add_argument("-p", "--part", default=None, help="分P号；合集视频必填")
    ap.add_argument("-o", "--out", default=None, help="输出目录（默认 outputs/<id>）")
    ap.add_argument("--probe-only", action="store_true", help="只打印格式与字幕，不下载")
    ap.add_argument("--audio", action="store_true", help="下载音轨")
    ap.add_argument("--video", action="store_true", help="下载 720P 视频流")
    ap.add_argument("--frames", action="store_true", help="抽帧并拼页（需先有 src.mp4）")
    ap.add_argument("--transcribe", nargs="?", const="large-v3", default=None,
                    metavar="MODEL", help="转写，默认 large-v3")
    ap.add_argument("--all", action="store_true", help="= --audio --video --frames --transcribe")
    ap.add_argument("--per", type=int, default=3, help="拼页每页几张")
    ap.add_argument("--crop", type=int, default=1120, help="裁切宽度")
    ap.add_argument("--json", action="store_true", help="结束时输出 JSON（给 agent 解析）")
    args = ap.parse_args()

    if args.all:
        args.audio = args.video = args.frames = True
        args.transcribe = args.transcribe or "large-v3"
    if not any([args.probe_only, args.audio, args.video, args.frames, args.transcribe]):
        ap.error("至少选一个动作：--probe-only / --audio / --video / --frames / --transcribe / --all")

    vid = video_id(args.url, args.part or "1")
    out = os.path.abspath(args.out or os.path.join(HERE, "outputs", vid))
    os.makedirs(out, exist_ok=True)

    def emit(files: dict, ok: bool = True) -> None:
        if args.json:
            import json
            print(json.dumps({"ok": ok, "video_id": vid, "dir": out,
                              "files": files}, ensure_ascii=False))

    # 1 探测（纯 Python，不依赖 bash）
    ytdlp("-I", args.part or "1", "-F", args.url)
    print("\n=== 字幕轨（只显示 danmaku 就是没字幕）===", flush=True)
    ytdlp("--list-subs", args.url)
    print("\n=== 元信息 ===", flush=True)
    ytdlp("-I", args.part or "1", "--skip-download",
          "--print", "%(title)s | %(duration)s s | %(uploader)s", args.url)
    if args.probe_only:
        emit({})
        return 0

    # 2 取流（直接用 yt-dlp，不依赖 bash）
    if args.audio:
        sub = ["-I", args.part or "1", "-f", "ba",
               "-o", os.path.join(out, "%(id)s.%(ext)s"), args.url]
        if ytdlp(*sub) != 0:
            print("音频下载失败；若已有 *.m4a 可继续后续步骤", file=sys.stderr)
    if args.video:
        sub = ["-I", args.part or "1", "-f", "30064",
               "-o", os.path.join(out, "src_%(id)s.%(ext)s"), args.url]
        if ytdlp(*sub) != 0:
            print("视频下载失败；若已有 src_*.mp4 可继续后续步骤", file=sys.stderr)

    audio = next(iter(glob.glob(os.path.join(out, "*.m4a"))), None)
    video = next(iter(glob.glob(os.path.join(out, "src_*.mp4"))), None)

    # 3 转写（先转 16k wav，绕开 av 库不兼容）
    if args.transcribe:
        if not audio:
            print("找不到音轨，跳过转写（先加 --audio）", file=sys.stderr)
        else:
            wav = os.path.join(out, "a16k.wav")
            if not os.path.exists(wav):
                sh([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
                    "-i", audio, "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wav])
            sh([PY, os.path.join(SCRIPTS, "04_transcribe.py"),
                wav, os.path.join(out, "transcript.txt"),
                "--model", args.transcribe, "--models-dir", MODELS])

    # 4 抽帧
    if args.frames:
        if not video:
            print("找不到视频流，跳过抽帧（先加 --video）", file=sys.stderr)
        else:
            sh([PY, os.path.join(SCRIPTS, "03_pick_frames.py"),
                video, os.path.join(out, "frames"),
                "--crop", str(args.crop), "--per", str(args.per)])

    print(f"\n完成 → {out}")
    produced = {}
    for f in sorted(os.listdir(out)):
        p = os.path.join(out, f)
        size = sum(os.path.getsize(os.path.join(p, x)) for x in os.listdir(p)) if os.path.isdir(p) else os.path.getsize(p)
        print(f"  {size/1048576:8.1f} MB  {f}")
        produced[f] = p
    emit(produced)
    return 0


if __name__ == "__main__":
    sys.exit(main())
