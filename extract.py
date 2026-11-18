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
import time
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "scripts")
# 模型目录可用 VX_MODELS 指向别处，复用其他项目已下好的模型
MODELS = os.environ.get("VX_MODELS") or os.path.join(HERE, "models", "whisper")

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


# ---------------------------------------------------------------- 环境体检

PKGS = ["yt_dlp", "imageio_ffmpeg", "numpy", "PIL", "faster_whisper"]


def candidate_pythons() -> list[str]:
    """找出这台机器上可能装好依赖的所有解释器。"""
    import shutil as _sh

    cands = {sys.executable}
    for name in ("python", "python3", "py"):
        p = _sh.which(name)
        if p:
            cands.add(p)
    home = os.path.expanduser("~")
    patterns = [
        os.path.join(home, ".workbuddy", "binaries", "python", "versions", "*", "python.exe"),
        os.path.join(home, "anaconda3", "python.exe"),
        os.path.join(home, "miniconda3", "python.exe"),
        os.path.join(home, "AppData", "Local", "Programs", "Python", "Python*", "python.exe"),
        os.path.join(home, ".dsh", "dsh-runtimes", "*", "dependencies", "python", "python.exe"),
        r"C:\Python3*\python.exe",
        "/usr/bin/python3",
        "/usr/local/bin/python3",
    ]
    for pat in patterns:
        cands.update(glob.glob(pat))

    seen, out = set(), []
    for p in cands:
        try:
            rp = os.path.realpath(p)
        except OSError:
            continue
        if rp in seen or not os.path.isfile(rp):
            continue
        seen.add(rp)
        out.append(rp)
    return out


def inspect_python(p: str) -> dict:
    """探测一个解释器：版本 + 五个依赖是否可用。"""
    import json
    code = (
        "import json,sys,importlib.util as u;"
        "print(json.dumps({"
        "'v':'.'.join(map(str,sys.version_info[:2])),"
        "'pkg':{m:(u.find_spec(m) is not None) for m in json.loads(sys.argv[1])}"
        "}))"
    )
    try:
        r = subprocess.run([p, "-c", code, json.dumps(PKGS)],
                           capture_output=True, text=True, timeout=20)
        if r.returncode != 0:
            err = (r.stderr or "").strip().splitlines()
            return {"path": p, "ok": False, "err": err[-1:] or ["unknown"]}
        d = json.loads(r.stdout.strip().splitlines()[-1])
        d.update({"path": p, "ok": True})
        return d
    except Exception as e:
        return {"path": p, "ok": False, "err": [type(e).__name__]}


def doctor(as_json: bool = False) -> int:
    import json

    rows = [inspect_python(p) for p in candidate_pythons()]
    rows.sort(key=lambda r: (not r.get("ok"), -sum(r.get("pkg", {}).values())))

    ready = [r for r in rows if r.get("ok") and all(r["pkg"].values())]
    partial = [r for r in rows if r.get("ok") and not all(r["pkg"].values())]

    models = []
    if os.path.isdir(MODELS):
        for d in sorted(glob.glob(os.path.join(MODELS, "*"))):
            if not os.path.isdir(d):
                continue
            size = sum(os.path.getsize(os.path.join(dp, f))
                       for dp, _, fs in os.walk(d) for f in fs)
            has_bin = any(f == "model.bin" for _, _, fs in os.walk(d) for f in fs)
            if not has_bin:
                continue
            name = os.path.basename(d)
            if name.startswith("models--"):
                name = name.split("--")[-1]
            models.append({"name": name, "size_mb": round(size / 1048576)})

    bash = None
    for n in ("bash", "bash.exe"):
        import shutil as _sh
        bash = bash or _sh.which(n)

    result = {
        "pythons": rows,
        "recommend": ready[0]["path"] if ready else (partial[0]["path"] if partial else None),
        "missing_in_recommend": [k for k, v in (ready[0] if ready else partial[0] if partial else {"pkg": {}})["pkg"].items() if not v] if (ready or partial) else PKGS,
        "models": models,
        "bash": bash,
    }

    if as_json:
        print(json.dumps(result, ensure_ascii=False))
        return 0

    print("== 解释器 ==")
    for r in rows:
        if not r.get("ok"):
            print(f"  ✗ {r['path']}\n      无法运行：{r.get('err')}")
            continue
        mark = "★" if ready and r["path"] == ready[0]["path"] else " "
        got = "".join("✓" if v else "✗" for v in r["pkg"].values())
        names = " ".join(k for k, v in r["pkg"].items() if not v)
        print(f" {mark} Python {r['v']}  {got}  {r['path']}")
        if names:
            print(f"      缺：{names}")

    print("\n== 模型 ==")
    if models:
        for m in models:
            print(f"  ✓ {m['name']}  {m['size_mb']} MB")
    else:
        print("  ✗ 无。首次转写会自动下载（small 464MB / large-v3 3GB）")

    print("\n== bash ==")
    print(f"  {'✓ ' + bash if bash else '✗ 无 —— 不影响，extract.py 已不依赖 bash'}")

    print("\n== 结论 ==")
    if ready:
        print(f"  直接可用：{ready[0]['path']}")
        if os.path.realpath(ready[0]["path"]) != os.path.realpath(sys.executable):
            print(f"  用它跑：设置 VX_PYTHON={ready[0]['path']}")
        print("  不需要安装任何东西。")
    elif partial:
        print(f"  最接近可用：{partial[0]['path']}")
        print(f"  只缺：{', '.join(result['missing_in_recommend'])}")
        print(f"  装这些即可：{partial[0]['path']} -m pip install {' '.join(result['missing_in_recommend'])}")
        if "PIL" in result["missing_in_recommend"]:
            print("  （PIL 对应包名是 pillow）")
    else:
        print("  没有可用的 Python。先装 Python 3.10+，再 pip install -r requirements.txt")
    print("\n  下一步：python extract.py <链接> -p 1 --probe-only")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="从 B 站视频取音频、字幕、板书帧、转写文本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("url", nargs="?", help="视频链接；用 --doctor 时可省略")
    ap.add_argument("-p", "--part", default=None, help="分P号；合集视频必填")
    ap.add_argument("-o", "--out", default=None, help="输出目录（默认 outputs/<id>）")
    ap.add_argument("-n", "--name", default=None,
                    help="输出目录名，建议用课程单元名，如 U6L2-1_官人与计算")
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
    ap.add_argument("--ocr", action="store_true",
                    help="抽帧后对整页做 OCR，输出 board_ocr.txt（不读图也能拿到文字）")
    ap.add_argument("--doctor", action="store_true",
                    help="环境体检：找本机已有的 Python/依赖/模型，不下载任何东西")
    args = ap.parse_args()

    if args.doctor:
        return doctor(args.json)

    if not args.url:
        ap.error("缺视频链接；只想体检请用 --doctor")

    if args.all:
        args.audio = args.video = args.frames = args.ocr = True
        args.transcribe = args.transcribe or "large-v3"
    if not any([args.probe_only, args.audio, args.video, args.frames, args.transcribe]):
        ap.error("至少选一个动作：--probe-only / --audio / --video / --frames / --transcribe / --all")

    vid = video_id(args.url, args.part or "1")
    dirname = args.name or vid
    out = os.path.abspath(args.out or os.path.join(HERE, "outputs", dirname))
    os.makedirs(out, exist_ok=True)

    def emit(files: dict, ok: bool = True) -> None:
        if args.json:
            import json
            print(json.dumps({"ok": ok, "video_id": vid, "name": dirname,
                              "dir": out, "files": files}, ensure_ascii=False))

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

    # 3/4/5 转写 与 抽帧+OCR 互不依赖，并行跑
    def do_transcribe() -> None:
        if not args.transcribe:
            return
        if not audio:
            print("找不到音轨，跳过转写（先加 --audio）", file=sys.stderr)
            return
        wav = os.path.join(out, "a16k.wav")
        if not os.path.exists(wav):
            sh([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
                "-i", audio, "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wav])
        sh([PY, os.path.join(SCRIPTS, "04_transcribe.py"),
            wav, os.path.join(out, "transcript.txt"),
            "--model", args.transcribe, "--models-dir", MODELS])

    def do_frames_ocr() -> None:
        if args.frames:
            if not video:
                print("找不到视频流，跳过抽帧（先加 --video）", file=sys.stderr)
            else:
                sh([PY, os.path.join(SCRIPTS, "03_pick_frames.py"),
                    video, os.path.join(out, "frames"),
                    "--crop", str(args.crop), "--per", str(args.per),
                    "--strip"])
        if args.ocr:
            fdir = os.path.join(out, "frames")
            if not os.path.isdir(fdir):
                print("没有 frames/，跳过 OCR（先加 --frames）", file=sys.stderr)
            else:
                sh([PY, os.path.join(SCRIPTS, "05_ocr.py"),
                    fdir, os.path.join(out, "board_ocr.txt")])

    if args.transcribe or args.frames or args.ocr:
        from concurrent.futures import ThreadPoolExecutor
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=2) as ex:
            futs = [ex.submit(do_transcribe), ex.submit(do_frames_ocr)]
            for f in futs:
                f.result()
        print(f"\n转写与抽帧并行完成，耗时 {time.time()-t0:.0f}s")

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
