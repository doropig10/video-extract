# 让别人的 AI 用这个项目

三种情况，三条路。先看对方 AI **能不能执行命令**，这决定了九成的做法。

| 对方 AI | 能做什么 | 给它什么 |
|---|---|---|
| 有命令行（WorkBuddy、Claude Code、Cursor、Cline 等） | 能跑 `extract.py`、能读文件 | **整个代码包 + AGENTS.md** |
| 纯对话（网页版 ChatGPT、Kimi 等） | 只能读你贴的文字/图片 | `docs/发给AI_一份就够.md` 全文 |
| 支持 MCP 的客户端 | 能直接调用工具 | MCP server（需自己包一层，见第三节） |

---

## 一、有命令行的 AI（推荐）

### 给它什么

只给**代码包**，不要给整个目录（模型 3.4GB，白传）：

```bash
tar --exclude=models --exclude=outputs --exclude='*.mp4' \
    --exclude='*.wav' --exclude='*.m4a' -czf video-extract-src.tar.gz .
```

### 关键：`AGENTS.md` 就是给它的说明书

项目根目录已经放了 `AGENTS.md`。主流编程 agent 会自动读这个文件（Claude Code 读 `CLAUDE.md`，Cursor 读 `.cursorrules`，可复制一份改名）。

它里面写了三件对方 AI 一定会搞错的事：

1. **入口只有 `extract.py`**，不要自己去拼 `yt-dlp` 命令；
2. **英文词以板面为准**，转写只取中文讲解——否则它会照着"Camponet"写笔记；
3. **必须加 `--json`**，从 `files` 字段判断成败，而不是看到"完成"就汇报。

### 对方 AI 的标准调用

```bash
python extract.py "<链接>" -p 23 --probe-only --json     # 先探，确认有没有字幕
python extract.py "<链接>" -p 23 --all --json            # 再全量取料
```

跑完它会拿到：

```json
{"ok": true, "dir": ".../outputs/BV1kmpk6SEPV_p1",
 "files": {"transcript.txt": "...", "frames": "...", "src_xxx.mp4": "..."}}
```

然后让它**读 `frames/` 里的图**（图像识别），不要只读 `transcript.txt`。

### 顺手提一句环境

对方机器上要装依赖，告诉他：

```bash
./install.sh          # 或 ./install.sh --gpu
```

Windows 下 `01/02` 是 bash 脚本，要用 Git Bash；`extract.py` 本身跨平台。

---

## 二、纯对话 AI

它没有文件系统，跑不了命令。这时候**不要给项目**，给方法：

把 `docs/发给AI_一份就够.md` 整段贴进去（21KB，自包含），它就知道怎么处理你提供的字幕、截图或文字稿。

前提是**你得先给它料**：要么自己用本项目取好 `transcript.txt` 和 `frames/` 再上传，要么让它明确说"我没取到原片，仅基于你给的材料整理"。

---

## 三、MCP 化（想让工具直接变成 AI 的能力）

标准做法是包一层 MCP server，暴露四个工具：`probe`、`download`、`transcribe`、`frames`。

骨架长这样（未在本机验证，需自己装 `mcp` 包）：

```python
# mcp_server.py
from mcp.server.fastmcp import FastMCP
import subprocess, sys, os, json

ROOT = os.path.dirname(os.path.abspath(__file__))
mcp = FastMCP("video-extract")

@mcp.tool()
def extract(url: str, part: str = "1", steps: str = "all") -> str:
    """从视频取料。steps: probe/audio/video/frames/transcribe/all"""
    flag = "--all" if steps == "all" else "--" + steps
    r = subprocess.run([sys.executable, os.path.join(ROOT, "extract.py"),
                        url, "-p", part, flag, "--json"],
                       capture_output=True, text=True)
    return r.stdout[-2000:]

if __name__ == "__main__":
    mcp.run()
```

然后在对方客户端的 MCP 配置里加上这个脚本即可。

**MCP 的代价**：调用方只看得到你 return 的字符串，看不到文件；所以 `--json` 里必须带绝对路径，否则它没法继续读图。

---

## 不管走哪条路，三句话要交代到

1. **英文拼写以板面为准**，转写不可信；
2. **先 `--probe-only`**，确认有字幕再决定要不要转写；
3. **有遮挡就标 `[ ]`**，缺就说缺，别补。

这三条不交代，对方 AI 一定会照转写稿写出"Camponet 是一种公司"这种东西，还会很自信。
