# VideoExtract

从视频里**可靠取料**的命令行工具：探测格式 → 取音视频流 → 转写成带时间戳文本 → 抽帧读板书。

不是"下载器"，也不是"笔记生成器"。它只负责一件事：**把视频里能取的信息完整、可核对地取出来**，交给下游（人或模型）去做笔记。

---

## 给 AI 用（最快路径）

把这个仓库丢给任何 AI，让它读 **`START_HERE.md`**。

- **能跑命令的 AI**（Claude Code、Cursor、Cline、WorkBuddy 等）：它会自己调用 `extract.py` 取料、读板面图、按模板出笔记。
- **只能对话的 AI**（网页版）：它会先声明"无法下载视频"，然后按同一套模板整理你给的字幕或截图。

一句话的启动方式：

```
读 START_HERE.md，按里面的流程处理这个视频：<链接>
```

`START_HERE.md` 里已经写好了五套笔记模板、四条铁律、交付自检和"用户要改样式时怎么办"。AI 不需要你额外解释。

---

## 30 秒上手

```bash
cd video-extract
python extract.py "<链接>" -p 23 --all
```

产出在 `outputs/BVxxxx_p23/`：

| 文件 | 是什么 | 用在哪 |
|---|---|---|
| `audio.m4a` | 最高码率音轨，单文件 | 转写输入 |
| `src_*.mp4` | 720P 视频流 | 读板书 |
| `a16k.wav` | 16k 单声道 | whisper 的标准输入 |
| `transcript.txt` | `[起-止] 文本` | 口述轨 |
| `frames/p_*.jpg` | 拼好的板面页 | 板面轨 |

跑到一半失败不用重来——每一步都能单独执行：

```bash
python extract.py "<链接>" -p 23 --probe-only          # 只看有什么，不下载
python extract.py "<链接>" -p 23 --audio --transcribe   # 只要音频和文本
python extract.py "<链接>" -p 23 --frames               # 补抽帧（需先有 src.mp4）
python extract.py "<链接>" -p 23 --transcribe large-v3  # 换模型重转
```

---

## 四个步骤

```
01 probe     → 格式清单 / 字幕轨 / 时长
02 download  → 音轨 + 720P 视频流（分开下，不合并）
03 frames    → 每 4 秒取样 → 只比文字区去重 → 拼页
04 transcribe → faster-whisper，GPU 优先，失败退 CPU
```

**为什么分开下而不合并**：B 站是 DASH，音视频分离。合并要 ffmpeg 且体积翻倍；做笔记时画面只用来读文字，720P 够用，音频单独取最高码率反而更准。

**为什么抽帧要比"文字区"而不是整幅**：教师站在右边，她的动作变化会被整幅比对当成"新版面"，导致同一块板子反复出现。

**为什么转写前先转 16k wav**：whisper 直接吃 m4a 路径会踩 `av` 库的 `metadata_errors` 不兼容（`TypeError`）。转成 wav 后传 numpy 数组，绕开整条路径。

---

## 依赖

```bash
./install.sh          # 或 ./install.sh --gpu 一起装 CUDA 运行库
```

手动装：

```bash
pip install yt-dlp imageio-ffmpeg numpy pillow faster-whisper
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12    # 想用 GPU 才需要
```

模型首次下载建议走镜像：`HF_ENDPOINT=https://hf-mirror.com`；有缓存后加 `HF_HUB_OFFLINE=1` 离线加载。

---

## 分享给别人

**不要整目录打包**：3.5GB 里 3.4GB 是模型、109MB 是素材，代码本体只有 128KB（压缩后 32KB）。

```bash
tar --exclude=models --exclude=outputs --exclude='*.mp4' \
    --exclude='*.wav' --exclude='*.m4a' -czf video-extract-src.tar.gz .
```

对方拿到后三步验收：

```bash
./install.sh                                    # 装依赖 + 自检
python extract.py "<链接>" -p 1 --probe-only     # 能出格式清单 = 通路正常
python extract.py "<链接>" -p 1 --transcribe small  # 能出文本 = 转写正常
```

**如果接手的是 AI，不是人：**

| 对方 AI | 给什么 |
|---|---|
| 能跑命令（Claude Code / Cursor / Cline） | 代码包本身。它会自动读 `AGENTS.md` 和 `START_HERE.md` |
| 只能对话（网页版） | `dist/单文件版.md` 全文，它不需要仓库，只要内容 |
| 支持 MCP | 自己包一层 server，把 `extract.py` 的四个步骤暴露成工具；返回里必须带绝对路径 |

关键一条：让 agent 加 `--json`，从返回的 `files` 字段判断成败，而不是看到"完成"就汇报。

> Windows 用户注意：`01/02` 是 bash 脚本，需要在 Git Bash 里跑；`extract.py` 本身跨平台。

---

## 实测速度（RTX 4060 Laptop 8G + 32 核 CPU，43 分钟音频）

| 配置 | 耗时 | 倍数 |
|---|---|---|
| small / CPU int8 | 约 8 分钟 | 6x |
| small / GPU float16 | 约 2 分钟 | 21.9x |
| **large-v3 / GPU float16** | **3 分 53 秒** | **11x** |

**能上 GPU 就上 large-v3**：它比 small 在 CPU 上跑还快，质量高一档。实测 small 会把"不唠嗑"听成"不落坑"——这是语义级错误，不是错别字。

---

## 目录

```
video-extract/
├── extract.py              入口：一条命令串起四步
├── START_HERE.md           给 AI 的作业单（取料 + 五套模板 + 四条铁律）
├── AGENTS.md               给 AI 的工具说明（agent 自动加载）
├── scripts/                四个可单独运行的脚本 + 说明
├── dist/
│   └── 单文件版.md            不依赖仓库，整段粘给网页版 AI
├── docs/
│   ├── A_怎么读视频.md        每步的判断依据、参数、边界
│   └── 视频转笔记_可复用流程.html  流程图
├── outputs/                产出（按视频 ID 分目录）
│   ├── P6_生态动物类/         笔记 7 版 + 源视频
│   └── U5L4_公司词群/         笔记 2 版 + 两份转写稿 + 19 张板面页
└── models/whisper/         small + large-v3，3.4GB，跨任务复用
```

`outputs/` 里那两个是**示例产物**，用来验证这条流水线真能跑通，不是工具的一部分。它们**不随仓库发布**（涉及第三方课程内容），clone 下来是空的，第一次运行会自动创建。

工具本身只有 `extract.py` + `scripts/` + `models/`。

---

## 设计取向（为什么不做得更大）

| 没做的事 | 原因 |
|---|---|
| 不做 GUI | 一条命令够用，做界面反而增加维护面积 |
| 不自动生成笔记 | 笔记要判断"这句是谁说的"，属于下游，硬塞进工具会把错误固化 |
| 不依赖平台转写服务 | 平台侧不可控（实测两次 900 秒超时），本地可重跑更重要 |
| 不追 1080P | 读文字 720P 足够；更高画质要登录态，收益不成比例 |

---

## 已知的坑（都踩过）

| 坑 | 症状 | 解法 |
|---|---|---|
| 裸 `yt-dlp` | command not found | 一律 `python -m yt_dlp` |
| 场景检测 | 纯色背景换文字不触发 | 按文字区做帧间差分 |
| 手写动画 | 去重失效，同版面反复出现 | 别跟算法较劲，拼页后人工合并 |
| `av` 版本 | `metadata_errors` TypeError | 先转 16k wav |
| CUDA DLL | `cublas64_12.dll is not found` | 手动加 `nvidia/cublas/bin` 等三目录（脚本已处理） |
| HF 直连 | 502 | `HF_ENDPOINT=https://hf-mirror.com` |
| 平台转写 | 900 秒超时，切片也超 | 超时一次就切本地 |

---

## 边界

付费课程、番剧、充电专属取不到——权限问题，不是技术问题。取下来的内容自用可以，原样分发是另一回事。
