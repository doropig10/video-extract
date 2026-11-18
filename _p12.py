import io

# 1) OCR 默认单进程，把实测结论写进帮助文本
p = "scripts/05_ocr.py"
s = io.open(p, encoding="utf-8").read()
s = s.replace(
    '    ap.add_argument("--workers", type=int, default=0, help="并行进程数，0=自动")',
    '    ap.add_argument("--workers", type=int, default=1,\n'
    '                    help="进程数，默认 1。实测 4 进程比 1 进程更慢"\n'
    '                         "（onnxruntime 内部已多线程，再叠进程只是抢 CPU）")',
)
s = s.replace(
    "    workers = args.workers or min(4, (os.cpu_count() or 2))",
    "    workers = max(1, args.workers)",
)
io.open(p, "w", encoding="utf-8").write(s)
print("ok 05_ocr.py")

# 2) extract.py：转写与（抽帧+OCR）并行
p = "extract.py"
s = io.open(p, encoding="utf-8").read()

old = '''    # 3 转写（先转 16k wav，绕开 av 库不兼容）
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
                "--crop", str(args.crop), "--per", str(args.per),
                "--strip"])

    # 5 OCR：整页转文字，省去逐页看图
    if args.ocr:
        fdir = os.path.join(out, "frames")
        if not os.path.isdir(fdir):
            print("没有 frames/，跳过 OCR（先加 --frames）", file=sys.stderr)
        else:
            sh([PY, os.path.join(SCRIPTS, "05_ocr.py"),
                fdir, os.path.join(out, "board_ocr.txt")])'''

new = '''    # 3/4/5 转写 与 抽帧+OCR 互不依赖，并行跑
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

    from concurrent.futures import ThreadPoolExecutor
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(do_transcribe), ex.submit(do_frames_ocr)]
        for f in futs:
            f.result()
    print(f"\\n转写与抽帧并行完成，耗时 {time.time()-t0:.0f}s")'''

assert old in s, "extract.py 主体未匹配"
s = s.replace(old, new)
s = s.replace("import subprocess\n", "import subprocess\nimport time\n", 1)
io.open(p, "w", encoding="utf-8").write(s)
print("ok extract.py")
