<div align="center">

# DownloadStack Control

**一个把 aria2 / AriaNg / qBittorrent / yt-dlp 串成一个控制台的 Windows / Linux / macOS 桌面面板**

赛博朋克 HUD 风格 · 只做监控与调度 · 不内置任何下载引擎

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flet](https://img.shields.io/badge/Flet-1.1.3-00ccff)](https://flet.dev/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-00E5A0)](#-支持平台)
[![License](https://img.shields.io/badge/License-MIT-FFB020)](LICENSE)
[![PRs](https://img.shields.io/badge/PRs-welcome-brightgreen)](CONTRIBUTING.md)

</div>

---

## 📖 这是什么

你机器上可能同时装了 **aria2**（下直链）、**AriaNg**（aria2 的网页界面）、**qBittorrent**（下 BT/PT）、
**yt-dlp**（下视频）。它们各自有界面、各自要启停、各自的配置在各自目录里。

**DownloadStack Control 不替代它们，只做一件事：把状态聚合到一个面板，把启停收进一个按钮。**

> 面板本身不下载任何东西，只调用你已安装的程序；不修改它们的配置，只读取状态。

---

## ✨ 功能

### 监控
- 🔴🟢 **三服务状态灯**：ONLINE（绿）/ ERROR（红）/ OFFLINE（灰），带呼吸脉冲动画
- 📊 实时速率、任务数、连接数、种子数、做种数
- 💫 环形负载表 + 迷你波形图（按 10 MiB/s 归一化）
- 🧾 实时日志区（INFO 绿 / WARN 黄 / ERROR 红），支持清空与导出

### 调度
- ▶️ 一键启动 Aria2 + AriaNg（自动拉静态服务、自动打开浏览器）
- ⏹️ 一键停止 / 重启（**只操作本面板记录的 PID**，不全局 `taskkill`）
- 🧲 一键全部停止：按 Aria2 → qBittorrent → YT 壳 顺序
- 🩺 一键自检：端口、文件、可写性、RPC、WebUI 全测一遍
- 💾 一键备份：`aria2.conf` / `qBittorrent.ini` / `config.json` / 路径表 → `backups/`

### 视频下载器（内置 GUI）
- 🎬 粘链接 → 选清晰度（最佳 / ≤1080P / ≤720P / 仅音频 mp3）→ 下载
- ⚡ **2x 超分开关**：检测到 Video2X 时下载完自动超分，没装会明确提示跳过
- ❌ 取消会结束整个进程树，不留后台任务
- 📂 一键打开保存目录

### 工程细节
- 🧩 **平台差异层**：`tasklist/taskkill` → `os.kill`/进程组；注册表 Run → LaunchAgents / `.desktop`
- 🔌 **端口自动避让**：6800/16800 被占用时自动顺延到 6801/16801，并写进配置
- 🧠 **安装根自动探测**：环境变量 → 上级目录 → `C~H:\Tools\DownloadStack`
- 🛡 **凭据不落仓库**：`config.json`、`rpc-secret.txt`、`logs/`、`backups/` 全在 `.gitignore` 里
- 🔍 **提交前体检**：`scripts/scan_secrets.py` 扫用户名、明文密码、绝对用户路径

---

## 🖼 界面预览

> 截图里含本机路径，仓库默认不附带；跑起来后欢迎提 PR 补图。

```
┌──────────────────────── 状态总览区（三灯 · 8 项速率 · 环形表 · 波形）────────────────────────┐
│导航区 │  下载区 · aria2        │  下载区 · BT 种子      │ 状态提示区（磁力/DHT 现状）│
│ 仪表盘│  下载区 · 视频          │  工具与维护区          │ 使用教程区（9 小节，可下拉）│
├──────────────────────────── 日志区（清空 / 导出）───────────────────────────────────────────┤
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 快速开始（只需一个入口）

| 平台 | 入口 | 怎么用 |
| --- | --- | --- |
| Windows | `一键配置.bat` | 双击 → 弹出图形向导 → 点「一键配置(含环境)」 |
| Linux / macOS | `一键配置.sh` | 终端里执行一行：`sh 一键配置.sh` |

```bash
# Linux / macOS
cd downloadstack-control
sh 一键配置.sh            # 交互式（会问你要不要装）
sh 一键配置.sh --scan     # 只体检，不安装
sh 一键配置.sh --auto     # 全自动
```

> Linux 里双击 `.sh` 只会用文本编辑器打开（从 Windows 拷过去的文件没有执行权限，
> 这是系统行为），所以 Linux 上请用上面那一行命令。

配置完成后启动面板：`启动面板.bat`（Windows）/ `sh 启动面板.sh`（Linux/macOS）。

### 安装时你会看到什么

1. **先列清单**：左侧逐项 `✔ 就绪 / ✘ 缺失`，右侧日志同时打印"缺少 N 项：…"
2. **逐项安装 + 进度条**：

   ```
   正在安装 2/5：ffmpeg
   === [2/5] 正在安装: ffmpeg ===
         ffmpeg  45% (13.2/29.4 MB)
   ```

   进度条按「已完成项 + 当前项内部进度」推进；下载类项目显示 MB 与百分比，每项结束打 `完成/未完成`
3. 全部结束后自动复扫，再点「启动控制台」

### 环境变量（一键配置自动写入）

| 变量 | 值 | 作用 |
| --- | --- | --- |
| `DOWNLOADSTACK_ROOT` | 安装根目录 | 面板/脚本定位 aria2、qB、tools |
| `DOWNLOADSTACK_DOWNLOADS` | 下载根目录 | 成品去处 |
| `VIDEO2X_PATH` | video2x 可执行文件（检测到才写） | 超分用 |
| `PATH` | 追加 `<ROOT>/tools/ffmpeg/bin` | 让 yt-dlp 能找到 ffmpeg |

Linux/macOS 写到 `~/.config/downloadstack/env.sh` 并自动挂进 `~/.bashrc`。

### 安装器会做的事

```
[0/9] 环境体检      Python / pip / flet / requests / ffmpeg / tar / curl / winget
[1/9] 复用检测      发现已有安装就直接复用，不重复下载
[2/9] 选盘符        列出可用盘，回车=默认，可自定目录（绝对路径校验）
[3/9] 确认位置      程序目录 / 下载目录
[4/9] 建目录        aria2 · ariaNg · qBittorrent · ControlPanel · logs · cache · backups · tools
[5/9] aria2c        官方 release + SHA256 校验
[6/9] AriaNg        官方 AllInOne + SHA256 校验
[7/9] yt-dlp        官方 latest（失败自动 pip 兜底）
[8/9] 写配置        aria2.conf（随机 64 位密钥）+ config.json + 4 个启停脚本 + GUI 启动器
[9/9] 自检          逐项打 [OK]/[缺失]，弹窗总结
```

---

## 🧭 使用教程

### 1. 普通文件 / 直链（aria2）

1. 面板点 **启动 Aria2 + AriaNg** → 灯变绿，浏览器自动打开 `http://127.0.0.1:16800`
2. AriaNg 左上「新建」→ 粘贴直链 → 开始
3. 成品在 `<下载根>/aria2`（默认 `D:\Downloads\aria2`）
4. 支持断点续传；暂停后继续即可；取消会删 `.aria2` 控制文件

### 2. 平台视频（内置 GUI）

1. 面板点 **启动 YT 下载壳**（默认就是 `ytdl_gui.py`），或双击 `ControlPanel/yt-download.cmd`
2. 粘贴链接 → 选清晰度 → 开始下载
3. 成品在 `<下载根>/yt-dlp`
4. 要超分就勾 **下载后 2x 超分**（检测到 Video2X 才可点）

### 3. BT / PT（qBittorrent）

1. 安装器会问要不要用 winget 装 qB；或自己装到 `<程序目录>/qBittorrent`
2. 面板点 **启动 qBittorrent** → **打开 WebUI**（`127.0.0.1:8080`）
3. 拖 `.torrent` 进窗口，或「添加 Torrent 链接」
4. 成品在 `<下载根>/qBittorrent`

### 4. 出差错怎么看

| 现象 | 看哪里 |
|---|---|
| 灯是灰的 | 服务没启动，点「启动」 |
| 灯是红的 | 装了但认证/接口失败 → 点「测试」按钮，日志区有具体原因 |
| 面板打不开 | 跑 `diag.bat` / `sh diag.sh`，生成 `diag-report.txt` |
| qB 红灯 | 在设置页填 WebUI 密码；面板已做 30 秒失败退避，避免自己把 IP 封了 |

---

## 🏗 它实现了什么（架构）

```
panel.py（Flet 单文件 UI）────────────────────────────────┐
  ├─ 平台差异层   IS_WIN / pid_alive / kill_tree / shell_run / open_path
  ├─ Probe         aria2 JSON-RPC 轮询 · qB WebUI 登录+maindata · yt pid 探测
  ├─ 动作层        start/stop/restart · 备份 · 自检 · 清理 · 原厂重置
  └─ 渲染层        状态灯 · 数字 · 波形 · 环形表 · 日志 · 卡片

setup_wizard.py（tkinter 引导）
  └─ scan() 逐项探测 → 缺失清单 → 一次确认 → 调 install.bat/.sh → 复扫 → 启动

install.bat / install.sh（真正的安装器）
  └─ 体检 · 复用 · 盘符/目录 · 下载+SHA256 · 生成配置与启停脚本 · 自检
```

**关键实现点**

| 点 | 做法 |
|---|---|
| 只读状态 | 全部走 aria2 JSON-RPC / qB WebUI，超时 2s，失败不崩溃只变灯 |
| 只管自己的进程 | PID 记在 `state/pids.json`，停止只杀这些；没有全局 kill |
| 凭据本机 | qB 密码、aria2 密钥存在本地 JSON/文本，`.gitignore` 排除 |
| 端口不冲突 | 安装时探测 6800..6805 / 16800..16803，取第一个空闲并写入配置 |
| 跨平台 | 差异全部收敛到文件顶部 ~90 行平台层，业务代码零 if-win |

---

## ⚙️ 配置说明（`config.json`）

| 键 | 说明 | 默认 |
|---|---|---|
| `aria2.host/port` | RPC 地址 | `127.0.0.1:6800` |
| `aria2.exe/conf/secret` | 程序、配置、密钥文件路径 | 安装目录下 |
| `qbit.host/port` | WebUI 地址 | `127.0.0.1:8080` |
| `qbit.user/pass` | WebUI 账号密码（本机明文存储） | `admin` / 空 |
| `qbit.save_dir` | 种子保存目录 | `<下载根>/qBittorrent` |
| `ariang.port/dir/script` | AriaNg 静态服务 | `16800` + 安装目录 |
| `yt.bat` | 外部视频脚本（留空=不启用） | 安装器填 GUI 启动器 |
| `scripts.start/stop/qbit` | 启停脚本路径 | 安装器生成 |
| `ui.upscale` | 超分开关 | `false` |

环境变量覆盖：`DOWNLOADSTACK_ROOT`、`DOWNLOADSTACK_DOWNLOADS`、`DOWNLOADSTACK_YTBAT`、
`DOWNLOADSTACK_YTSHELL_INI`、`PYTHON_EXE`、`VIDEO2X_PATH`。

---

## 📁 目录结构

```
downloadstack-control/
├─ panel.py              面板主程序（3D 控制台后端服务 + 探测 + 动作 + 平台差异层）
├─ panel_ui.html         曲面 3D 空间控制台前端（零外链离线运行 + 内置 AriaNg / 磁力工坊 / 任务队列）
├─ magnet_tools.py       磁力解析 / Tracker 热更新 / DHT 修复 / 种子预取校验模块
├─ ytdl_gui.py           视频下载器 GUI
├─ setup_wizard.py       图形/文本引导（--auto / --text / --scan）
├─ 一键配置.bat / .sh     一键配置（依赖 + 组件 + 环境变量）
├─ 启动面板.bat / .sh     启动器（先体检 → 缺就问你 → 启动）
├─ install.bat / .sh     安装向导（盘符自选、端口避让、SHA256 校验）
├─ diag.bat / diag.sh    诊断 → diag-report.txt
├─ config.example.json   配置模板
├─ requirements.txt      flet==1.1.3 / requests
├─ scripts/
│  ├─ scan_secrets.py    提交前敏感信息扫描
│  └─ build.ps1          PyInstaller 打包脚本（可选）
├─ LICENSE / NOTICE / SECURITY.md / CONTRIBUTING.md / README.md
```

## ❓ 已知问题

1. **磁力 / DHT**：部分网络下 magnet 取不到元数据、DHT 长期 0 节点；用 `.torrent` 文件即可绕过。属网络环境问题。
2. **AriaNg 连不上 aria2**：需要 aria2 开 `rpc-allow-origin-all=true`（安装器默认写入），否则浏览器跨源拦截。
3. **qB WebUI 登录失败会封 IP**：面板已做 30 秒退避，建议先配好密码再启动。
4. **qBittorrent 静默安装**：官方只给安装包，向导用 winget 代装，失败时给手动命令。
5. **macOS**：代码已做平台适配，未在真机验证。

---


## 🆘 用户常遇到的问题（照着做即可）

### 1. 抖音/小红书 403 Forbidden、提示 Fresh cookies are needed

这些站点要登录态。视频下载器里中间那行 **「登录状态 / Cookies」**：

| 你的情况 | 选择 |
| --- | --- |
| Linux/Windows 里用 Firefox 登录过该站 | `用 Firefox 登录态` |
| 用 Chrome 登录过 | `用 Chrome 登录态` |
| 有导出的 cookies.txt | 填进「cookies.txt 路径」 |

> 选择会**记住**（写在 `ControlPanel/ytdl_settings.json`），下次不用再选。

### 2. AriaNg 打开报「认证失败」

aria2 是带 `rpc-secret` 启动的，AriaNg 必须带密钥。新版面板打开时会自动拼：

```
http://127.0.0.1:16800/?rpc=127.0.0.1:6800&secret=<你的密钥>
```

如果还是认证失败：面板 → 设置 → 确认「密钥文件」指向 `aria2/rpc-secret.txt`，保存后重开。

### 3. AriaNg 页面「无法访问 / 拒绝连接」

AriaNg 是个静态页，需要一个本地 HTTP 服务（端口 16800）。检查：

```bash
ss -ltn | grep 16800        # 有输出=在跑
sh ~/DownloadStack/start_ariang.sh &   # 没跑就手动起
```

新版面板点「打开 AriaNg 网页」会自动拉起并**等待最多 10 秒**。

### 4. 面板窗口不弹出来（SSH / 无桌面）

```bash
DOWNLOADSTACK_WEB=1 sh ~/DownloadStack/ControlPanel/启动面板.sh
# 然后浏览器打开 http://127.0.0.1:8550
```

### 5. 点「启动 YT 下载壳」没反应

```bash
ls -l ~/DownloadStack/ControlPanel/yt-download.sh
```
不存在就补：

```bash
cat > ~/DownloadStack/ControlPanel/yt-download.sh <<'EOF'
#!/bin/sh
exec "$HOME/DownloadStack/.venv/bin/python" -B "$HOME/DownloadStack/ControlPanel/ytdl_gui.py"
EOF
chmod +x ~/DownloadStack/ControlPanel/yt-download.sh
```

### 6. 安装时报 `externally-managed-environment`

Ubuntu 24.04 的 PEP 668 限制。安装器已经自动建 `venv` 规避；如果仍报错：

```bash
sudo apt install -y python3-venv python3-pip
rm -rf ~/DownloadStack/.venv
sh install.sh
```

### 7. 导出诊断

```bash
sh diag.sh        # 生成 diag-report.txt
```
里面包含系统、Python、依赖、组件、端口、日志，排错时先看这个。

## 🛣 Roadmap

- [ ] 下载队列可视化（aria2 多任务进度条）
- [ ] 托盘图标 + 最小化到托盘
- [ ] 定时任务（夜间限速、定时备份）
- [ ] 主题商店（更多赛博配色）
- [ ] 打包为单文件 exe（Release 附件 + SHA256）

---

## 🤝 贡献

欢迎 PR。提交前请跑：

```bash
python scripts/scan_secrets.py .
```

**Commit 规范（Conventional Commits）**

```
feat(panel): 支持 qB 认证失败提示
fix(installer): 修正 AriaNg 哈希校验
docs(readme): 补三平台安装说明
refactor(platform): 抽出 kill_tree 到平台层
chore(deps): 锁定 flet==1.1.3
```

**分支**：`feat/xxx`、`fix/xxx`；**PR** 请描述「改了什么 / 怎么验证」。

---

## 📄 License

MIT © DownloadStack Control contributors
第三方组件（aria2 GPL-2.0 / AriaNg MIT / qBittorrent GPL-2.0 / yt-dlp Unlicense / flet Apache-2.0 / requests Apache-2.0）见 [NOTICE](NOTICE)。

> 本仓库只包含自有源码，**不打包任何第三方二进制**；安装器只从官方发布地址下载。
> 请仅下载你有权获取的内容，遵守所在地法律与各站点服务条款。
