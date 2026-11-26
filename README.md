<div align="center">

# DownloadStack Control

**把 aria2 / AriaNg / qBittorrent / Magnet 磁力增强 / yt-dlp 统一收拢进一个曲面 3D 空间控制台的跨平台桌面面板**

Windows / Linux / macOS · 零前端构建 · 离线可用 · 同源直出 AriaNg · 不内置任何下载引擎二进制

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![UI](https://img.shields.io/badge/UI-Spatial%203D%20Console-00E5A0)](#核心功能)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-00ccff)](#快速部署)
[![License](https://img.shields.io/badge/License-MIT-FFB020)](LICENSE)
[![PRs](https://img.shields.io/badge/PRs-welcome-brightgreen)](CONTRIBUTING.md)

</div>

---

## 📖 这是什么

机器上同时装了 **aria2**（直链加速）、**AriaNg**（aria2 网页管理）、**qBittorrent**（BT / PT）、**yt-dlp**（平台视频）时，各自独立启停、配置分散、磁力冷启动易卡元数据、AriaNg 经常遇端口或 Token 认证报错。

**DownloadStack Control 不替代它们，只做一件事：用一个 3D 空间控制台统一监控、调度、投递任务与修复磁力/DHT。**

> 面板本身不打包第三方下载引擎二进制；只通过官方 JSON-RPC / WebUI API 与本机已安装组件协作。

---

## 📋 环境与部署要求（开始前必看）

| 类别 | 组件 / 依赖 | 是否必装 | 说明 |
| --- | --- | --- | --- |
| **运行环境** | **Python 3.10+** | **必装** | Windows 官网安装时请勾选 `Add Python to PATH` |
| **Python 依赖** | **`requests>=2.31`** | **必装** | 3D 主控制台 `panel.py` 唯一外部依赖（其余全用标准库） |
| **展示窗口** | **Edge / Chrome / 任意现代浏览器** | **必装** | Windows 自动以 Edge/Chrome 无边框 App 窗口启动；Linux/macOS 自动开默认浏览器；无桌面 SSH 自动跑在 `http://127.0.0.1:18550/` |
| **下载引擎** | **aria2 + AriaNg + yt-dlp + ffmpeg** | **一键自动安装** | 运行 `一键配置.bat` / `sh 一键配置.sh` 会从官方 Release 下载并做 SHA256 校验 |
| **BT / PT 引擎** | **qBittorrent** | 可选 | 需要下种子/PT 时安装（支持 `WebUI` 密码登录与本机免密 `LocalHostAuth=false`） |
| **视频下载 GUI** | **`flet==1.1.3`** | 可选 | 仅独立视频图形窗口 `ytdl_gui.py` 需要；不装也能正常使用 3D 主控制台与命令行直投 |
| **AI 超分** | **Video2X** | 可选 | 检测到本地 Video2X 后可开启「2x 超分」开关，未安装自动跳过 |

---

## 🚀 快速部署（任选一种）

### 方式 A：全自动一键配置（推荐新手）

| 平台 | 第一步：配置环境与组件 | 第二步：启动 3D 控制台 |
| --- | --- | --- |
| **Windows** | 双击 `一键配置.bat` → 点「一键配置(含环境)」 | 双击 `启动面板.bat` |
| **Linux / macOS** | 终端执行 `sh 一键配置.sh`（支持 `--scan` / `--auto`） | 终端执行 `sh 启动面板.sh` |

> Linux 里双击 `.sh` 默认会用文本编辑器打开，请在终端运行 `sh 一键配置.sh`。

### 方式 B：极简手动部署（已有 aria2 / qBittorrent）

如果你本机已经装好了 aria2 或 qBittorrent，只需 3 条命令即可跑起 3D 控制台：

```bash
git clone https://github.com/ember-glade8/downloadstack-control.git
cd downloadstack-control
python -m pip install requests          # 若还要用独立 ytdl_gui.py，改为 pip install -r requirements.txt
python panel.py                         # 自动启动 http://127.0.0.1:18550/ 并打开 3D 控制台窗口
```

> 首次启动会在同目录自动生成 `config.json`、`state/`、`logs/`、`cache/`、`backups/`，全部位于 `.gitignore` 内，不会污染仓库。点击右上角 **「⚙ 设置」** 即可填入或微调本机路径与端口。

### 方式 C：无桌面 / SSH / NAS 服务器模式

```bash
DOWNLOADSTACK_WEB_PORT=18550 python panel.py
# 本机或 SSH 端口转发后浏览器访问 http://127.0.0.1:18550/
```

---

## ✨ 核心功能

### 1. 曲面 3D 空间控制台（`panel_ui.html`）
- **零外链离线运行**：纯原生 HTML5 / CSS3 3D / Canvas 渲染，无需 Node.js、无需构建、无 CDN 依赖。
- **曲面环抱驾驶舱**：左翼双通道液态吞吐波形、中枢 3D 极光能量地形台与万能直投舱、右翼实时任务雷达，下方四大带独立 3D 动态画布的实体操控台（Aria2 超光速隧道 / qBittorrent 3D P2P 球网 / Magnet 3D 磁感力场 / YT-DLP 声光频谱）。

### 2. 万能极速直投舱 & 实时任务队列
- **粘贴即下**：在中枢输入框粘贴 HTTP/HTTPS 直链、`magnet:?`、纯 40 位 Hex / 32 位 Base32 InfoHash、或视频平台链接，自动识别并分流投递。
- **全栈任务管理**：顶部切换 **「⚡ 任务队列」** 即可实时查看并暂停 / 继续 / 移除 Aria2 与 qBittorrent 全部任务。

### 3. 内置同源 AriaNg（免端口冲突）
- `panel.py` 直接在 `/ariang/` 挂载本地 `ariaNg/index.html` 并自动 Base64 注入 `rpc-secret`，不再依赖额外的 16800/16801 静态 HTTP 进程。
- 支持顶部 **「🌐 内置 AriaNg」** 全屏嵌入使用，或点击 **「↗ 跳转 AriaNg」** 前台弹出独立窗口。

### 4. 磁力 / DHT 增强工坊（`magnet_tools.py`）
- **秒解元数据**：投递磁力时自动尝试预取公共 `.torrent` 并做 **SHA1 InfoHash 严格校验**，跳过 `[METADATA]` 卡顿。
- **Tracker 热更新**：多镜像拉取公共高速 Tracker（支持自动代理回退与内置保底），一键热写入运行中的 Aria2 与 qBittorrent。
- **DHT 一键修复**：自动发现携带合法 `token` 的真实 KRPC DHT 节点并写入 `aria2.conf`，实时展示 qBittorrent DHT 节点数。

### 5. 安全调度与维护
- **PID 隔离**：停止 / 重启 / 一键全停（按 Aria2 → qBittorrent → YT 壳顺序）仅操作本面板记录的 PID 或官方 API 优雅关闭，**绝不全局 `taskkill`**。
- **一键自检 & 备份**：检查端口、核心文件、目录可写性与 RPC/WebUI 连通性；一键备份全套配置至 `backups/`。
- **敏感信息防泄漏**：提交前可运行 `python scripts/scan_secrets.py .` 扫描凭据与绝对用户路径。

---

## 🔌 默认端口与环境变量

| 端口 / 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DOWNLOADSTACK_WEB_PORT` | `18550`（被占自动顺延至 `18569`） | 3D 控制台本地服务端口（同时直出 `/ariang/`） |
| `aria2.port` | `6800` | aria2 JSON-RPC 端口（带 `rpc-secret` 认证） |
| `qbit.port` | `8080` | qBittorrent WebUI 端口（支持密码登录与本机免密） |
| `DOWNLOADSTACK_ROOT` | 自动探测 | 安装根目录（定位 aria2、ariaNg、qBittorrent、tools） |
| `DOWNLOADSTACK_DOWNLOADS` | `<同盘>\Downloads` 或 `~/Downloads` | 总下载成品根目录 |
| `VIDEO2X_PATH` | 自动探测（可选） | Video2X 可执行文件路径（2x 超分用） |

---

## 🏗 架构与目录结构

```text
panel.py（3D 控制台后端服务 + 平台差异层 + 实时轮询 + 同源 AriaNg 挂载）
  ├─ 平台差异层   IS_WIN / pid_alive / kill_tree / shell_run / open_path
  ├─ Probe         aria2 JSON-RPC + 任务队列 · qB WebUI 免密/登录 + DHT 节点 · yt PID
  ├─ ControlBackend 启停 · 万能投递 · 磁力增强 · 任务控制 · 自检 · 备份 · 清理 · 开机自启
  └─ HTTP Server   127.0.0.1:18550  (/ · /api/state · /api/action · /ariang/)

panel_ui.html      零外链离线曲面 3D 空间控制台前端
magnet_tools.py    磁力解析 · Tracker 拉取热更 · DHT token 节点发现 · SHA1 种子预取校验
ytdl_gui.py        独立视频下载器 GUI（支持画质/Cookies/2x 超分）
setup_wizard.py    图形/文本配置引导（--auto / --text / --scan）
install.bat / .sh  三平台组件安装器（目录初始化 + 官方包 SHA256 校验 + 启停脚本生成）
```

```text
downloadstack-control/
├─ panel.py              面板主程序（3D 控制台后端服务 + 探测 + 动作 + 平台差异层）
├─ panel_ui.html         曲面 3D 空间控制台前端（零外链离线运行 + 内置 AriaNg / 磁力工坊 / 任务队列）
├─ magnet_tools.py       磁力解析 / Tracker 热更新 / DHT 修复 / 种子预取校验模块
├─ ytdl_gui.py           独立视频下载器 GUI
├─ setup_wizard.py       图形/文本引导（--auto / --text / --scan）
├─ 一键配置.bat / .sh     一键配置（依赖 + 组件 + 环境变量）
├─ 启动面板.bat / .sh     启动器（先体检 → 缺就问你 → 启动 3D 控制台）
├─ install.bat / .sh     安装向导（盘符自选、端口避让、SHA256 校验）
├─ diag.bat / diag.sh    环境与端口诊断 → diag-report.txt
├─ config.example.json   配置模板
├─ requirements.txt      requests（必装） / flet（ytdl_gui.py 可选）
├─ scripts/
│  ├─ scan_secrets.py    提交前敏感信息扫描
│  └─ build.ps1          PyInstaller 单文件打包脚本（可选）
├─ tests/test_core.py    核心与磁力模块单元测试
└─ LICENSE / NOTICE / SECURITY.md / CONTRIBUTING.md / README.md
```

---

## 🆘 常见问题排错

### 1. qBittorrent 状态灯为红 / 登录失败
- 点击右上角 **「⚙ 设置」** 填写 qBittorrent WebUI 账号密码并保存；如果你在 qBittorrent 中勾选了「对本地主机上的客户端跳过身份验证（`LocalHostAuth=false`）」，面板会自动免密直连，密码留空即可。
- 面板内置 30 秒失败退避保护，避免密码填错触发 qB 封禁本机 IP。

### 2. 磁力链接卡在「获取元数据」或 DHT 为 0 节点
- 进入顶部 **「🧲 磁力工坊」** → 点 **「🔧 一键修复 DHT/磁力」** 与 **「🌐 更新并热载 Tracker」**。
- 直接在「磁力工坊」或中枢「万能直投舱」粘贴 `magnet:?` 或 40 位 InfoHash，系统会自动补全高速 Tracker 并优先预取 `.torrent`（带 SHA1 校验）。

### 3. 抖音 / 小红书视频提示 403 或需要 Cookies
- 打开视频下载器 GUI（`ytdl_gui.py`），在 **「登录状态 / Cookies」** 选择已登录该站点的 Firefox / Chrome 或指定导出的 `cookies.txt`（选择会自动保存）。

### 4. Linux / Ubuntu 24.04 报 `externally-managed-environment`
- 一键安装器默认创建独立 `.venv` 避开 PEP 668；若手动安装请先执行：
  ```bash
  sudo apt install -y python3-venv python3-pip
  python3 -m venv .venv && .venv/bin/pip install requests
  .venv/bin/python panel.py
  ```

### 5. 导出诊断报告
- Windows 双击 `diag.bat`，Linux/macOS 执行 `sh diag.sh`，会生成 `diag-report.txt`（包含系统、Python、核心文件、18550/6800/8080 端口与日志）。

---

## 🛣 Roadmap

- [x] 下载队列可视化（Aria2 + qBittorrent 多任务进度条与暂停/继续/移除）
- [x] 磁力 / DHT 增强工坊（Tracker 热更新、DHT 节点修复、SHA1 预取 `.torrent`）
- [x] 同源内置 AriaNg 挂载（零端口冲突 + 自动注入 RPC Token）
- [ ] 系统托盘图标 + 最小化到托盘
- [ ] 定时任务（夜间限速、定时备份）
- [ ] 打包为单文件 exe（Release 附件 + SHA256）

---

## 🤝 贡献与验证

提交 PR 前请运行本地自检（与 GitHub Actions CI 一致）：

```bash
python scripts/scan_secrets.py .
python -m py_compile panel.py magnet_tools.py ytdl_gui.py setup_wizard.py scripts/scan_secrets.py
python -m unittest discover -s tests -v
```

---

## 📄 License

MIT © DownloadStack Control contributors  
第三方组件许可见 [NOTICE](NOTICE)。本仓库只包含自有源码，不打包任何第三方二进制；请仅下载你有权获取的内容。
