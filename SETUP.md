# DownloadStack Control · 从零配置手册（SETUP）

> 面向**第一次安装这个软件的人**。照着从上到下做，30 分钟内可以跑起来。
> 本手册覆盖：安装 → 首次自检 → 逐项配置 → 可选组件 → 书城/音乐/短剧 → 自启/备份/卸载 → 故障排查 → **风险清单（必读）**。
> 其他文档：功能全貌看 [README.md](README.md)｜界面操作看 [TUTORIAL.md](TUTORIAL.md)｜免责条款看 [DISCLAIMER.md](DISCLAIMER.md)。

**一句话说明它是什么**：一个跑在**你自己电脑上**的本地网页面板（`http://127.0.0.1:18550/`），把 aria2 / qBittorrent / AriaNg / yt-dlp / 4K 影院 / 音乐 / 书城 / 本地 AI 画室聚合成一个窗口。它**不打包**第三方二进制与 AI 模型权重，也不提供任何账号体系——**默认只监听本机，谁打开这个地址谁就有全部权限**（见 §12）。

---

## 0. 五分钟速通（只想先跑起来）

**Windows**

1. 下载仓库 ZIP → 解压到**非系统盘**，例如 `D:\Tools\DownloadStack`（路径别带空格以外的特殊符号）
2. 双击 **`一键配置.bat`** → 选「一键配置(含环境)」。缺 Python 会自动装（winget 或官网安装包）
3. 双击 **`启动面板.bat`** → 自动打开桌面窗口 `http://127.0.0.1:18550/`
4. 顶栏看到 5 颗灯变绿 = 基本通了。红灯按 §11 排查

**Linux / macOS**

```bash
sh install.sh          # 装依赖 + 建目录 + 写配置
sh 启动面板.sh          # 或 python3 -B panel.py
```

**只想跑面板本体（已有 Python 和 aria2 的情况）**

```bash
python -m pip install -r requirements.txt
python -B panel.py
```

> 装完先别急着用。**§3「首次自检 6 项」建议 3 分钟内过一遍**，能挡掉 90% 的"打不开/灯不绿/下载不动"。

---

## 1. 系统要求

| 项目 | 最低 | 建议 | 说明 |
| --- | --- | --- | --- |
| 系统 | Windows 10 1809+ / macOS 12+ / 主流 Linux 桌面 | Windows 11 x64 | 无桌面环境的 Linux 只能用浏览器访问，无 App 窗口 |
| Python | 3.10 | **3.12** | 3.13+ 未做长期验证；面板本体只依赖 `requests` |
| 内存 | 8 GB | 16 GB+ | 4K 影院 / ComfyUI / 声音克隆同时开时吃内存 |
| 磁盘 | 程序 ~1.5 GB | 下载盘 **预留 50 GB+** | 程序 + aria2/ffmpeg/yt-dlp + 片库 + 书库缓存 |
| 显卡 | 核显可跑界面 | NVIDIA GTX 10 系+（NVENC） | 「RTX 4K 母带重建」需 NVIDIA；AMD FidelityFX CAS 实时修复走 WebGL2，核显也能开关但效果有限 |
| 网络 | 能开 GitHub / aria2 官方源 | 能科学上网最佳 | 书城（MangaDex / Gutenberg / Internet Archive）、音乐源、YouTube 在国内网络下**大概率需要代理**（§5.4） |
| 权限 | 普通用户即可 | — | 装到 `C:\Program Files` 或装系统级依赖才需要管理员 |

**不需要**：Node.js（除非你要用 LX Music 音源桥）、Docker、数据库、外网服务器、云账号。

---

## 2. 安装（三种方式，选一种，别混着来）

### 方式 A｜`一键配置.bat`（推荐给不熟命令行的人）

| 步骤 | 你会看到 | 你该做什么 |
| --- | --- | --- |
| 1 | 检测 Python（`[1/3] 检查 Python`） | 什么都没装过就等它自动装；出现 `[失败]` 时去 python.org 下 3.12 安装包，勾 **Add python.exe to PATH** |
| 2 | 弹出**图形向导**（有 tkinter 时） | 点「🔍 扫描」先看缺什么 → 点「⚡ 一键配置(含环境)」 |
| 3 | 无 tkinter 时自动转文本向导 | 按提示回车，输入 `y` 确认安装缺失组件 |

向导结束会打印"下一步：双击 启动面板.bat"。

**命令行无人值守**（脚本/远程部署用）：

```bat
一键配置.bat /scan
一键配置.bat /auto
```

Linux/macOS：`sh 一键配置.sh --scan` / `sh 一键配置.sh --auto`

### 方式 B｜`install.bat` 完整安装器（要 aria2 + AriaNg + qBittorrent + yt-dlp + ffmpeg 全家桶）

双击 `install.bat`，一共 9 步，**每一步都在问你之前先说清要干什么**：

| 步骤 | 动作 | 需要你回答 |
| --- | --- | --- |
| 0/9 | 环境体检（PowerShell / tar / curl / winget / Python / ffmpeg） | 无 |
| 1/9 | 发现本机已有安装 → **直接复用，不重复下载** | 回车复用，或输入 `N` 装到别处 |
| 2/9 | 列出可用盘符 | 选一个盘（如 `D`） |
| 3/9 | 确认 `程序目录` 与 `下载目录` | 回车默认 `X:\Tools\DownloadStack`；也可手输完整路径 |
| 4/9 | 建目录（aria2 / qBittorrent / ControlPanel / logs / cache / backups） | 无 |
| 5/9 | 下载 **aria2c 1.37.0** 并做 **SHA256 校验** | 无 |
| 6/9 | 下载 **AriaNg**（Web 管理前端） | 无 |
| 7/9 | 下载 **yt-dlp.exe**（失败则 `pip install yt-dlp` + 包装脚本兜底） | 无 |
| 7.5/9 | 可选 **qBittorrent**（winget） | `Y` / `N`（BT/PT 必须装） |
| 8/9 | 写 `config.json`、aria2.conf、启停脚本、**随机 RPC 密钥**、桌面快捷方式 | 无 |
| 9/9 | 自检 + 询问**是否开机自启** | `Y` / `N`（只写 HKCU 一个 Run 值） |

安装器**不会覆盖**已存在的 `config.json`（要强制重写用 `DS_FORCE=1`），也会跳过已有二进制。
跳过 qBittorrent：设 `DS_NO_QB=1`。只看不做：`install.bat --dry-run`。

**安装完成后的目录长这样**（`<ROOT>` = 你选的程序目录）：

```text
<ROOT>\                         ← 程序根（aria2 / qBittorrent / 启停脚本）
├─ ControlPanel\                ← 源码 + 你的 config.json（凭据在这）
│  ├─ panel.py / panel_ui.html  主服务与单文件前端
│  ├─ media_studio.py           音乐 / TTS / ComfyUI / 模型对接
│  ├─ magnet_tools.py           磁力搜索 / Tracker / DHT
│  ├─ reader_hub.py             书城后端（漫画 / 电子书）
│  ├─ drama_hub.py              短剧中心
│  ├─ lx_music_bridge.py        LX Music 音源桥（需 Node）
│  ├─ prompt_engine.py          提示词引擎
│  ├─ library\                  ★ 本地书库（自己往里放书）
│  ├─ config.json               ★ 你的配置（含密码 / Key，勿外传）
│  ├─ logs\ state\ cache\ backups\
├─ aria2\                       aria2c.exe + aria2.conf + rpc-secret.txt
├─ qBittorrent\                 qbittorrent.exe + profile\
├─ ariaNg\                      AriaNg 静态页
├─ tools\ffmpeg\bin\ffmpeg.exe
└─ <DOWNLOADS>\                 下载产物（默认同盘 X:\Downloads）
```

### 方式 C｜手动 / 绿色迁移（已有 Python 环境）

```bash
git clone <仓库地址> DownloadStack
cd DownloadStack
python -m pip install -r requirements.txt
python -B panel.py            # 或双击 启动面板.bat
```

- 目录可以整体拷到别的盘/别的机器：面板会按 `DOWNLOADSTACK_ROOT` → 向上找 `aria2\aria2c.exe` → 常见 `X:\Tools\DownloadStack` 的顺序自动定位，**不写死盘符**。
- 要把源码装进 `install.bat` 的目录结构里，请用方式 B；方式 C 直接跑在源码目录，`config.json` 就生成在源码目录旁（已被 `.gitignore` 排除）。
- **从仓库直接 clone 时注意**：`reader_hub.py`、`reader_catalog.py`、`drama_hub.py`、`lx_music_bridge.py`、`prompt_engine.py` 必须和 `panel.py` 在同一目录，缺哪个对应功能就会提示"模块未加载"。

---

## 3. 首次自检（6 项，3 分钟）

打开面板 → 右上 **“系统与运维中心”** → 点 **「一键自检」**，然后逐条确认：

| # | 检查 | 通过标准 | 不合格怎么办 |
| --- | --- | --- | --- |
| 1 | 面板端口 | 浏览器/窗口能打开 `http://127.0.0.1:18550/`，顶栏无红色告警 | 端口被占 → §5.2 |
| 2 | aria2 引擎 | 灯变绿，点「▶ 启动」后 `活跃任务` 有数字 | §11「aria2 不亮」 |
| 3 | qBittorrent | `/qbit/` 能进 WebUI 并已登录 | §3.1 |
| 4 | 下载目录 | 显示剩余空间，且 `下载` 动作后文件真的出现 | 目录不存在/无写权限 → 在配置里改 `paths.downloads` |
| 5 | yt-dlp / ffmpeg | 视频工坊能解析一条链接；`ffmpeg -version` 有输出 | §6 组件矩阵 |
| 6 | 本地书库 | 书城 → 本地书库 → 显示 `library\` 里的书名 | 放书后点「重新扫描」（§7） |

### 3.1 qBittorrent 首次登录（最容易卡住的一步）

- 面板里 `qbit.user` 默认 `admin`，`qbit.pass` **默认空**。
- qBittorrent 4.6+ 首次启动会生成**随机临时密码**，打印在启动日志里；装在 `<ROOT>\qBittorrent` 时到 `qBittorrent\profile\qBittorrent\data\logs\qbittorrent.log` 里搜 `temporary password`。
- 登录后建议：WebUI 里改一个自己的密码 → 回到面板 **系统与运维中心** 填入 `qbit.pass` → 保存并重启面板。
- 4.5 及更早版本可用 `admin/adminadmin`，登录后立刻改。
- WebUI 端口必须与 `qbit.port` 一致（默认 `8080`）；qB 的「Web 用户界面 → 启用」必须打开。

---

## 4. 逐项配置（`config.json` 全字段）

**两种改法，改完都要重启面板：**

1. 面板 UI：**系统与运维中心 / AI 画室 / 智能体** 页里的输入框（推荐，会做校验）
2. 直接编辑 `<ROOT>\ControlPanel\config.json`（改前先备份，格式是严格 JSON，**不能有注释、不能有尾逗号**）

> `config.example.json` 里的 `<ROOT>` / `<DOWNLOADS>` 是占位说明；`config.json` 首次生成时会替换成你机器上的真实路径。

### 4.1 `aria2`（下载引擎）

| 键 | 默认 | 说明 |
| --- | --- | --- |
| `host` / `port` | `127.0.0.1` / `6800` | 装机器时若被占用会自动换 6801–6805，**以 `config.json` 实际值为准** |
| `exe` | `<ROOT>\aria2\aria2c.exe` | 找不到启动会失败 |
| `conf` | `<ROOT>\aria2\aria2.conf` | BT/DHT 参数在这里；面板「DHT 修复」会无损改写它 |
| `secret` | `<ROOT>\aria2\rpc-secret.txt` | 安装时随机生成；**这是明文密码**，别外传 |
| `logdir` | `<ROOT>\logs` | aria2 日志目录 |

### 4.2 `qbit`（BT / PT）

| 键 | 默认 | 说明 |
| --- | --- | --- |
| `host` / `port` | `127.0.0.1` / `8080` | 与 qB WebUI 端口一致 |
| `user` / `pass` | `admin` / 空 | 建议改强密码后回填 |
| `config_dir` | `<ROOT>\qBittorrent\profile\qBittorrent\config` | 便携 profile，不污染系统 qB |
| `save_dir` | `<DOWNLOADS>\qBittorrent` | 种子内容落盘位置 |
| `exe_dir` | `<ROOT>\qBittorrent` | 「▶ 启动 qBittorrent」用 |

### 4.3 `yt`（视频下载）

| 键 | 默认 | 说明 |
| --- | --- | --- |
| `bat` / `bat2` | 安装器生成的 `ControlPanel\yt-download.cmd` | 外部下载壳；留空则用内建逻辑 |
| `ini` | 空 | `yt-dlp` 参数模板文件（可选） |
| `output` | `<DOWNLOADS>\yt-dlp` | 视频落盘目录 |
| `cookies` | `auto` | `auto` = 自动读本机浏览器登录态；`none` = 不读；也可指向 `cookies_file` |
| `cookies_file` | 空 | 手动导出的 `cookies.txt`（Netscape 格式） |

### 4.4 `ariang`

| 键 | 默认 | 说明 |
| --- | --- | --- |
| `port` | `16800` | 独立 AriaNg 端口（面板内 `/ariang/` 同源嵌入不依赖它） |
| `dir` / `script` | `<ROOT>\ariaNg` / `start_ariang.cmd` | 静态目录与启动脚本 |

### 4.5 `scripts`（启停脚本）

`start` / `stop` / `qbit` 三个键指向 `<ROOT>` 下的 `start_aria2.cmd`、`stop_aria2.cmd`、`start_qbit.cmd`。
面板**只操作自己记录在 `state\pids.json` 的 PID**，不会全局 `taskkill`。

### 4.6 `ui`（界面与自启）

| 键 | 默认 | 说明 |
| --- | --- | --- |
| `theme` | `dark` | 主题 |
| `autostart_panel` | `false` | 开机自启面板（只写 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`） |
| `autostart_aria2` | `false` | 面板起来时顺带拉起 aria2 |
| `upscale` | `false` | 视频下载默认开 2x 超分（要 Video2X） |

### 4.7 `paths`（产物目录）

| 键 | 默认 | 说明 |
| --- | --- | --- |
| `downloads` | 同盘 `X:\Downloads` | 下载总目录（磁盘卫士按它算剩余空间） |
| `music` | 空 → `downloads\music` | 音乐落盘 |
| `voice` | 空 → `downloads\voice-clone` | 声音克隆产物 |
| `aigc` | 空 → `downloads\ai-studio` | AI 画室产物 |
| `books` | 空 | **额外**本地书库目录（可与 `library\` 并存） |

### 4.8 `reader_roots`（书城额外书库）

```json
"reader_roots": ["D:\\Books", "E:\\Comic"]
```

- 只接受**已存在**的目录，且做了安全限制：**不会扫描 `C:\` 整盘**，也不会递归吞掉整个 D 盘（防止误扫系统目录）。
- 想加就加，想删就删，改完重启面板 → 书城点「重新扫描」。

### 4.9 `voice`（声音克隆 / 神经配音）

| 键 | 默认 | 说明 |
| --- | --- | --- |
| `api_url` | `http://127.0.0.1:9880` | 外部克隆 API（GPT-SoVITS / CosyVoice / FishSpeech）。内置 F5-TTS 走 `.venv-voice` 独立环境 |

### 4.10 `comfyui`（AI 画室）

| 键 | 默认 | 说明 |
| --- | --- | --- |
| `enabled` | `false` | 是否启用本地画室 |
| `owner_only` | `true` | 只允许本机 owner 使用（别关） |
| `url` | `http://127.0.0.1:8188` | 本机 ComfyUI 地址 |
| `root` / `start_bat` | 空 | ComfyUI 安装目录与启动脚本（面板内「▶ 启动」用） |
| `custom_mode` | `comfyui` | 也可选 `sdwebui` / `openai` 兼容接口 |
| `custom_url` / `custom_api_key` / `custom_model` | 空 | 自定义后端（**Key 明文存本地**） |
| `custom_workflow_json` | 空 | 自定义 Workflow，支持 `{{PROMPT}} {{NEG_PROMPT}} {{IMAGE}} {{SEED}}` 占位符 |

### 4.11 `codex`（赛博小怪兽）

| 键 | 默认 | 说明 |
| --- | --- | --- |
| `base_url` | 空 | OpenAI / Codex 兼容中转地址 |
| `api_key` | 空 | 明文存 `config.json` |
| `model` | 空 | 模型名（可点「🔎 拉取可用模型」） |
| `api_style` | `auto` | `auto` / `openai` / `responses` 等 |

### 4.12 环境变量（可选，覆盖配置文件）

| 变量 | 作用 |
| --- | --- |
| `DOWNLOADSTACK_ROOT` | 指定程序根目录（换盘 / 绿色迁移用） |
| `DOWNLOADSTACK_DOWNLOADS` | 指定下载目录 |
| `DOWNLOADSTACK_WEB_PORT` | 面板端口（默认 `18550`，被占用时改这个） |
| `DOWNLOADSTACK_YTBAT` / `DOWNLOADSTACK_YTSHELL_INI` | 覆盖 yt 下载壳与参数文件 |
| `VIDEO2X_PATH` | Video2X 可执行文件路径 |

---

## 5. 端口与网络

### 5.1 端口表

| 服务 | 默认端口 | 监听 | 谁能访问 |
| --- | --- | --- | --- |
| 面板本体 | `18550` | `127.0.0.1` | 仅本机 |
| aria2 RPC | `6800`（占用自动 6801–6805） | `127.0.0.1` | 仅本机 |
| AriaNg 独立站 | `16800`（占用自动 16801+） | `127.0.0.1` | 仅本机 |
| qBittorrent WebUI | `8080` | 视 qB 配置 | **默认也是本机**，别改到 0.0.0.0 |
| 声音克隆 API | `9880` | 由第三方服务决定 | 建议仅本机 |
| ComfyUI | `8188` | 由 ComfyUI 决定 | 建议仅本机 |

### 5.2 端口被占用

1. 查占用：`netstat -ano | findstr :18550` → `tasklist /FI "PID eq <PID>"`
2. 面板：设 `DOWNLOADSTACK_WEB_PORT=18560` 再启动（或改 `启动面板.bat` 里的端口）
3. aria2 / AriaNg：`install.bat` 安装时已自动避让；已装好的改 `config.json` 里 `aria2.port` / `ariang.port`，并同步改 `aria2.conf` 的 `rpc-listen-port`，最后重启两者

### 5.3 手机 / 平板 / 局域网访问

**默认不支持，这是有意的。** 面板没有任何登录鉴权（§12 R1），一旦绑到 `0.0.0.0`，同一 WiFi 下任何人都能删你的片、投任意下载、甚至触发关机。

真要多设备访问，按下面顺序做，别跳步：

1. 优先用 **Tailscale / ZeroTier 这类虚拟局域网**（只在你自己的设备间可达），再把面板绑到虚拟网卡 IP
2. 或者：Windows 防火墙只放行**指定来源 IP**，禁止 `0.0.0.0` 全网开放
3. 前面挂一层带 Basic Auth 的反向代理（Caddy/Nginx），**不要**直接暴露面板
4. 永远不要在路由器上给 18550 做端口映射

### 5.4 代理（国内网络必须理解这一点）

- `启动面板.bat` 启动时会**临时清空** `HTTP_PROXY/HTTPS_PROXY/ALL_PROXY`（避免 shell 里的代理污染子进程）；
- 面板后端自己读 **Windows 系统代理**（`ProxyEnable` / `ProxyServer`），并支持 `socks5://`；
- 书城（MangaDex / Gutenberg / Internet Archive / なろう）、音乐源、YouTube、GitHub 词库同步，在国内网络下**多数需要系统代理已开启**；
- 想让面板走代理：**开系统代理**（Clash/v2rayN 的"系统代理"开关），而不是设环境变量；
- 部分源在代理下仍超时 → 属源站问题，§11 有对应排查。

---

## 6. 可选组件矩阵（按需装，不装就少一块功能）

| 组件 | 被谁用 | 装法 | 不装的后果 |
| --- | --- | --- | --- |
| **ffmpeg** | 4K 影院转码、剪辑、截图、TTS 标准化、字幕 | 安装器自动下到 `<ROOT>\tools\ffmpeg\bin`，或 `winget install Gyan.FFmpeg` | MKV/TS/AC3 播放失败、剪辑不可用 |
| **yt-dlp** | 视频下载 | 安装器下载到 `<DOWNLOADS>\ytdlp` | 视频工坊不可用 |
| **qBittorrent** | BT/PT、磁力投递 | `install.bat` 7.5 步 / winget | BT 相关全灰 |
| **aria2 + AriaNg** | HTTP 直链多线程下载 | 安装器自动装 | 只剩 qB |
| **Video2X** | 2x AI 超分 | 自行下载后设 `VIDEO2X_PATH` | 超分开关无效，其它正常 |
| **ComfyUI**（含 Z-Image / Wan2.2 模型） | AI 画室 | 官方仓库 + 模型自行下载（**本仓库不含权重**） | 画室显示离线 |
| **F5-TTS**（`.venv-voice`） | 声音克隆 | 面板内一键部署（CUDA 环境） | 只剩 Edge-TTS 神经配音 |
| **edge-tts**（Python 包） | 神经配音、书城朗读 | `pip install edge-tts` | 朗读 / 配音不可用 |
| **Node.js 18+** | LX Music 音源桥（14 音源） | nodejs.org 或 `winget install OpenJS.NodeJS.LTS` | 音乐退回内置源，LX 音源灰色 |
| **LX Music 桌面版** | 提供 `user_api.json` 音源 | 自行安装（第三方开源软件） | 同上 |
| **系统代理** | 书城 / 音乐 / YouTube | 你的代理客户端开"系统代理" | 外部源大量超时 |

---

## 7. 书城（漫画 / 电子书 / 朗读）

**本地书库（离线、最稳）**

1. 把 `.epub / .txt / .pdf / .cbz / .zip`（或漫画图片文件夹）放进 `<ROOT>\ControlPanel\library\`
2. 面板 → **📚 书城** → 「本地书库」→ **重新扫描**
3. 想用别的目录：**书城 → 添加书库目录**（写入 `reader_roots`），或在 `config.json` 里加 `reader_roots`
4. TXT 默认按「第 X 章」切章；CBZ 按压缩包内图片顺序翻页

**在线源（需要网络）**

| 源 | 内容 | 备注 |
| --- | --- | --- |
| MangaDex | 公开漫画（官方 API） | 遵守其 DMCA 下架；部分章节有地区限制 |
| 维基文库 | 中文公有领域古籍 | 稳定 |
| Project Gutenberg | 7 万+ 公有领域名著 | 国内常需代理 |
| Internet Archive | 公有领域扫描本 / 黄金年代漫画 | 仅非借阅类；速度看网络 |
| Standard Ebooks | 精校英文名著 | 稳定 |
| 小説家になろう | 日轻 / 日文网文 | 国内需代理 |
| 风格馆 | 按题材直达 | 聚合上述源 |

**缓存与离线**：远程图片走同源代理 `/api/reader/img` 并落盘到 `cache\reader\img`；离线打包的漫画写到 `cache\reader\books\离线漫画\`。清缓存：书城 → 缓存 → 清理。

**朗读**：需要 `edge-tts`（在线）或 `voice.api_url` 指向的本地 TTS。语音列表来自系统 SAPI + Edge 音色。

---

## 8. 音乐（14 源 + LX 音源桥）

- 内置源：网易云 / QQ / 酷狗 / 酷我 / 咪咕 / B站 / YouTube 等，**并发检索**，单源失败不影响整体。
- **LX 音源桥**（14 源里的"LX 音源"）：面板以**只读**方式读取你本机 LX Music 的 `user_api.json`，用 `lx_userapi_host.js`（Node）在 `127.0.0.1` 起一个本地宿主来解析播放地址。
  - 需要 **Node.js 18+**；
  - **音源脚本是别人的 JavaScript，会在你本机 Node 里执行**（`vm` 沙箱但不等同于浏览器级隔离）——只装你信任来源的音源脚本（§12 R8）；
  - 桥不会写回 LX Music 的配置文件。
- 播放走 `/api/stream_audio`（支持 Range 拖动）；下载支持 MP3 / FLAC / M4A / WAV。
- 歌词：本地 `.lrc` → 网易云（含翻译）→ 酷狗 三层兜底。

---

## 9. 短剧中心

- 依赖 `drama_hub.py`。仓库里带了它；如果某次安装后点短剧提示 **「短剧模块未加载（drama_hub）」，页面顶部也会显示琥珀色提示条**，说明该文件没被复制到 `ControlPanel\`。
- 修法：把 `drama_hub.py` 放到与 `panel.py` 同目录 → 重启面板。
- 内容策略：只做**官方频道**的展厅与官方可嵌入播放器；受 DRM 保护的正片不解析、不缓存。

---

## 10. 自启 / 备份 / 迁移 / 卸载

**开机自启**：面板 → 系统与运维中心 → 勾选「开机自启」（只写一个 `HKCU\...\Run` 值，可随时关）。安装器 9/9 步也会问一次。

**备份**：
- 配置：系统与运维中心 → 「备份配置」→ 生成到 `<ROOT>\ControlPanel\backups\`
- 整体：直接拷 `<ROOT>` 目录（`config.json` 里含凭据，拷到别处注意安全）

**迁移到新盘 / 新机器**：
1. 关面板，停 aria2 / qB
2. 整个 `<ROOT>` 拷过去（含 `ControlPanel\config.json`）
3. 若盘符变了：设 `DOWNLOADSTACK_ROOT=<新路径>`，或重跑 `install.bat` 让它自动识别复用
4. 打开面板 → 系统与运维中心 → 一键自检

**卸载**：
1. 面板 → 「安全停止全部服务」
2. 关掉自启开关（或 `reg delete HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v DownloadStack` 视键名而定）
3. 删 `<ROOT>`；**下载目录 `X:\Downloads` 里是你自己的文件，按需手动清**
4. 若装过 `.venv-voice`，一并删除（在 `<ROOT>\ControlPanel` 下）

**日志位置**：`<ROOT>\ControlPanel\logs\`（`launcher.log` 看启动失败）、`<ROOT>\logs\`（aria2）。

---

## 11. 故障排查（症状 → 原因 → 处理）

| 症状 | 最可能原因 | 处理 |
| --- | --- | --- |
| 双击 `启动面板.bat` 闪退 | Python 缺失 / 依赖缺失 / 路径含特殊字符 | 看 `ControlPanel\logs\launcher.log`；`python -B panel.py` 前台跑一遍看报错 |
| 窗口开了但页面空白 | 前端缓存了旧版 / 端口错 | 地址后加 `?boot=1&v=<任意数字>` 强刷；删 `cache\chromium-*` profile |
| 打不开 `127.0.0.1:18550` | 端口被占 / 服务没起 | `netstat -ano \| findstr :18550`；改 `DOWNLOADSTACK_WEB_PORT` |
| aria2 灯一直红 | 未启动 / 端口不符 / 密钥不符 | 点「▶ 启动 aria2」；核对 `config.json` 的 port 与 `aria2.conf` 的 `rpc-listen-port`、`rpc-secret` 与 `rpc-secret.txt` |
| qB 页面 401 / 403 | 密码错 / CSRF / 端口错 | §3.1；qB 里勾「绕过本地认证」只在纯本机时可用 |
| 视频解析失败 | yt-dlp 太旧 / 需要登录 / 需要代理 | `yt-dlp -U`；配置 `cookies`；开系统代理 |
| 合并音视频失败 | ffmpeg 不在 PATH 也没在 `tools\ffmpeg\bin` | 装 ffmpeg 或设路径 |
| 磁力搜不到结果 | 源站挂了 / DHT 冷启动 / 网络受限 | 换关键词；磁力页「DHT 修复」；开代理 |
| 下载 0 速度（BT） | Tracker 失效 / 端口不通 | 磁力页「热更新 Tracker」；检查 qB 连接页是否只有 DHT |
| 磁力链接投递后一直"获取元数据" | 无人做种 / 防火墙拦 BT 端口 | 换源；放行 qB 监听端口 |
| 书城搜索超时 / 空白 | 外部源不可达（国内网络） | 开系统代理；先用「本地书库」；看 §7 源备注 |
| 书城图片不显示 | 图片域名不在白名单 / 代理失败 | 只用内置源；清 `cache\reader\img` 重试 |
| 书城提示"模块未加载" | `reader_hub.py` / `reader_catalog.py` 不在 `panel.py` 同目录 | 补齐文件重启 |
| 短剧提示"模块未加载" | `drama_hub.py` 缺失 | §9 |
| 音乐有结果但播不动 | 音源限流 / 需要登录 / LX 桥未起 | 换源试；装 Node 后重启面板；看 `logs` |
| AI 画室一直"离线" | ComfyUI 没起 / 地址错 / 显存不足 | 启动 ComfyUI（8188）；核对 `comfyui.url`；先跑一张小图 |
| 声音克隆部署失败 | 网络 / 无 CUDA / 磁盘不足 | 用 Edge-TTS 兜底；看向导输出 |
| 「RTX 4K 重建」失败 | 非 NVIDIA 或驱动太旧 | 改用 GPU 实时 CAS（快捷键 `E`） |
| `.bat` 中文乱码 | 控制台代码页不是 936 | `chcp 936`；或系统「区域设置 → 非 Unicode 程序语言」设为中文 |
| 界面卡 / 首屏慢 | 单文件前端 ~600 KB，属正常 | 关掉不用的工坊；别同时开 4K 影院 + ComfyUI |
| 端口自动变了找不到 | 安装器避让占用 | 以 `config.json` 实际值为准 |

---

## 12. 风险清单（**发布/交付前必须让使用者读这一段**）

### 12.1 默认安全姿态

- 面板、aria2 RPC、AriaNg、qB WebUI 默认**只监听 `127.0.0.1`**；
- 面板**没有账号/密码/Token**，本地即最高权限；
- 凭据（qB 密码、aria2 `rpc-secret`、AI Key）**明文**存在 `config.json` / `rpc-secret.txt`；
- 仓库 `.gitignore` 已排除 `config.json`、`logs/`、`cache/`、`state/`、`backups/`，提交前还会跑 `scripts/scan_secrets.py`。

### 12.2 风险条目

| 编号 | 风险 | 后果 | 缓解 |
| --- | --- | --- | --- |
| **R1** | **面板无鉴权 + 对外暴露** | 同网段/公网任何人可投递下载、删除片库、读取本机状态，甚至触发关机 | 永远只绑 `127.0.0.1`；远程用虚拟局域网 + 反代鉴权（§5.3）；不做路由器端口映射 |
| **R2** | 凭据明文落盘 | 截图、录屏、共享 `config.json`、把整个目录传网盘 = 泄露 qB 密码 / RPC 密钥 / AI Key | 传输前删 `config.json`；发截图前遮蔽；`.gitignore` 别破坏；定期换密钥 |
| **R3** | 自动读取浏览器 Cookies | `yt.cookies=auto` 时会读本机浏览器登录态用于下载，等于把这些站点的登录权限交给该进程 | 敏感账号用独立浏览器 profile；不需要时设 `cookies=none`；别在共享机器上开 `auto` |
| **R4** | 自动删除 / 自动关机 | 「看完即删」删的是**真实文件**（含同名种子、字幕、空目录）；「下完关机 / 睡眠」会中断其它程序 | 首次使用先在测试目录试；关机预约有 15 秒倒计时可取消；重要文件另存 |
| **R5** | 第三方内容源不稳定 / 有地区与合规差异 | 源站改版、限流、下架会导致搜索/播放失败；部分源本身存在版权争议 | 只用官方 API 与公有领域源；把「失败」当常态设计；关注 `CHANGELOG` |
| **R6** | 版权与平台条款 | 下载/分享受版权保护的内容可能违反著作权法与平台 ToS，风险由使用者承担 | 仅用于公有领域、CC 授权、自有内容、已获授权素材（见 `DISCLAIMER.md`） |
| **R7** | AI 声音克隆 / 深度合成 | 未经授权克隆他人声音、伪造他人形象，可能构成侵权甚至违法 | 只用本人或已获书面授权的声音；对外发布 AI 内容依法显著标识 |
| **R8** | LX 音源脚本在本机 Node 中执行 | 恶意音源脚本可读写你可访问的文件、发起网络请求 | 只装社区公认、可审查的音源；不确定就关掉 LX 桥 |
| **R9** | 代理与网络路径 | 面板会读系统代理；代理本身能看到你的请求元数据 | 用可信代理；不要把代理账号写进 `config.json` |
| **R10** | 第三方二进制供应链 | aria2 / qBittorrent / ffmpeg / yt-dlp 来自各自官方渠道，安装器对 aria2 做 SHA256 校验 | 保留校验；不要用来源不明的"绿色版"替换 `aria2c.exe` |
| **R11** | 本地模型吃显存 / 长时间高负载 | 4K 重建、ComfyUI 出片可能让 GPU 满载、温度升高 | 8 GB 显存先跑小图；注意散热；面板有「释放显存」 |
| **R12** | 日志与截图泄露隐私 | 日志含本机路径、URL、任务名 | 分享日志前替换用户名与路径；`scan_secrets.py` 只查代码不查日志 |
| **R13** | 目录权限与"书库白名单"限制 | 书城只允许显式目录，避免误扫整盘；但一旦你把 `D:\` 加进 `reader_roots`，就会扫全盘 | 只加具体书库目录，不要加盘符根 |
| **R14** | 卸载不干净 | 自启键、`.venv-voice`、下载目录里的文件会留下 | 按 §10 顺序卸载 |

### 12.3 出问题时的止损顺序

1. 面板 → **安全停止全部服务**
2. 关自启开关 → 断掉面板与 qB 的对外监听
3. 若怀疑凭据泄露：改 qB 密码 → 重新生成 `rpc-secret.txt` → 换 AI Key
4. 若怀疑被外部访问：查 `logs\` 与 qB 的连接日志，检查路由器映射与防火墙规则
5. 需要回滚：用 `backups\` 里的配置副本，或整目录还原

---

## 13. 交付检查清单（把软件发给别人之前逐条打勾）

- [ ] `python scripts/scan_secrets.py .` 输出 `[OK] 未发现敏感串`
- [ ] `python -m unittest discover -s tests` 全绿
- [ ] 仓库里**没有** `config.json`、`rpc-secret.txt`、`logs/`、`cache/`、`cos`、`*.log`
- [ ] `panel.py` 同目录下 `reader_hub.py`、`reader_catalog.py`、`drama_hub.py`、`lx_music_bridge.py`、`prompt_engine.py` 齐全
- [ ] 用**干净机器**（或删掉 `config.json` 后）跑一遍 §0 与 §3
- [ ] 短剧页在缺模块时显示琥珀提示条，而不是报错崩溃
- [ ] 端口表（§5.1）与你的实际 `config.json` 一致
- [ ] 使用者已读 §12，特别是 R1 / R2 / R4 / R6 / R7
- [ ] `SETUP.md`、`README.md`、`TUTORIAL.md`、`CHANGELOG.md` 版本号一致

---

## 14. 反馈与支持

- 问题排查先看 §11，再看 `logs\` 与浏览器 Console
- 提 issue 请附：系统版本、Python 版本、`config.json`（**先脱敏**）、`logs\launcher.log` 尾部、复现步骤
- 安全相关问题见 [SECURITY.md](SECURITY.md)
