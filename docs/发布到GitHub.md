# 发布到 GitHub / Gitee

本机没有 `gh`，也没有远端凭据，所以推送这一步需要你自己执行（或给我一个已授权的环境）。

下面三套步骤，选一套。

---

## 一、GitHub（网页建仓 + 命令行推）

```bash
# 1 在 github.com 新建仓库，名字 video-extract，不要勾选 README/.gitignore/LICENSE
# 2 回到本地，把地址换成你的
cd video-extract
git remote add origin https://github.com/<你的用户名>/video-extract.git
git branch -M main
git push -u origin main
```

如果提示要密码，用 Personal Access Token 而不是账号密码（GitHub 2021 年起就不收密码了）。

## 二、装 gh 一键建仓（推荐，少点网页操作）

```powershell
winget install GitHub.cli
gh auth login          # 走浏览器授权
cd video-extract
gh repo create video-extract --public --source=. --remote=origin --push
```

`gh` 会自动建仓、设 remote、推 main，并读走 `.gitignore`。

## 三、Gitee（国内速度好）

```bash
# 1 gitee.com 新建仓库，同样不要初始化
cd video-extract
git remote add origin https://gitee.com/<你的用户名>/video-extract.git
git branch -M main
git push -u origin main
```

Gitee 推之前要在「设置 → 私人令牌」生成 token，用 token 当密码。

---

## 推之前自检三件事

| 检查 | 命令 | 期望 |
|---|---|---|
| 模型没被带进去 | `git ls-files \| grep models` | 无输出 |
| 笔记没被带进去 | `git ls-files \| grep outputs` | 无输出 |
| 没有个人路径 | `git grep -n "Users\\\\"` | 无输出 |

这三条任何一条有输出，先别推——3.4GB 的模型推上去会被 GitHub 拒（单文件 100MB 上限），笔记推上去是版权问题。

---

## 推完之后

1. **仓库描述**填一句：「从视频里可靠取料的命令行工具：音轨、字幕、板书帧、带时间戳转写」
2. **Topics** 加：`bilibili` `whisper` `video-to-text` `notes` `faster-whisper` `ffmpeg`
3. **Releases** 打一个 `v0.1.0`，附上 `video-extract-src.tar.gz`（32KB），方便别人直接下
4. README 顶部可以加两行 badge（可选）：

```markdown
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
```

---

## 需要我做什么

- **给我一台有 `gh auth login` 的环境**，我可以直接建仓、推代码、打 tag。
- 或者你给我一个 **PAT**（`repo` 权限），我在本机装 `gh` 后推上去——但令牌会经过这次会话，用完建议立即吊销。

两条都可以，看你觉得哪个更省事。
