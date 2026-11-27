<div align="center">

# DownloadStack Control v2.5 · Spatial 3D Command OS

**开箱即用、全站内闭环的桌面下载 / 4K 影音 / 本地 AI 一体化 3D 空间控制中心**

支持 Windows / Linux / macOS · 全程站内同源嵌入零外跳 · 不打包第三方二进制与模型权重 · 凭据仅存本地永不入库

[![Version](https://img.shields.io/badge/Release-v2.5-00E5FF?style=flat-square)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![WebGL](https://img.shields.io/badge/UI-Spatial%203D%20HUD%20%2B%20WebGL2%20CAS-a78bfa)](#-核心功能全景)
[![Tutorial](https://img.shields.io/badge/Docs-全功能使用教程-FFB347)](TUTORIAL.md)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-00F5B8)](#-快速开始)
[![License](https://img.shields.io/badge/License-MIT-FFB020)](LICENSE)

> 🎉 **v2.5 正式定版**：全新集成 **5 源并发站内搜磁力**、**站内原画 4K 影院（零压缩直出 + GPU WebGL2 FidelityFX CAS 4K画质修复 + RTX 重建纯 4K + 看完即删）**、**4K 原画截图/无损剪辑联动 AI 画室与声音克隆**、**磁盘空间实时卫士 + 通宵挂机自动睡眠/关机**、以及 **11 章交互式教程中心**。  
> 📖 完整指南见 **[《DownloadStack Control v2.5 使用教程手册》](TUTORIAL.md)** ｜ 更新详情见 **[CHANGELOG.md](CHANGELOG.md)**。

</div>

---

## 🎯 需求面向（为谁而生）

如果你本机同时使用或想要一站式管理以下工具，又受够了在十几个窗口、网页、命令行之间反复切换：

- **高速下载用户**：需要把 **Aria2**（多线程直链）、**AriaNg**（Web 管理）、**qBittorrent**（BT/PT 做种）、**磁力/DHT 修复** 聚合在同一个桌面窗口内管理，不再弹出一堆外部浏览器标签页。
- **全平台音视频收藏者**：希望直接粘贴 YouTube / B站 / 抖音 / 小红书 / X / TikTok 链接一键下最高 4K 视频（可选 2x 超分），同时支持 **6 大音乐榜单、6 音源聚合搜歌、秒播试听、下载与电影级全屏 3D 歌词舞台**。
- **本地 AI 创作者**：希望在软件内直接接入自己的本地 **ComfyUI / SD WebUI / OpenAI 兼容生图生视频模型**（含提示词搜索引擎与 AI 提示词优化器）以及 **开源 AI 声音克隆（F5-TTS / 神经配音）**，并配有一只常驻桌面随时问答的 **赛博小怪兽智能体**。

---

## 🏷️ 项目标签（GitHub Topics / Tags）

`download-manager` · `aria2` · `ariang` · `qbittorrent` · `yt-dlp` · `magnet-dht` · `music-player` · `webgl-shaders` · `3d-lyrics` · `comfyui` · `ai-prompt-optimizer` · `wan22` · `f5-tts` · `voice-cloning` · `ai-agent` · `desktop-dashboard` · `cyberpunk-ui` · `python`

---

## 🚨 项目红线（设计与开源铁律）

1. **一切功能站内闭环，禁止外跳外部浏览器**：AriaNg、qBittorrent WebUI、3D 歌词全屏舞台、AI 画室画廊与高清灯箱、赛博小怪兽问答框全部同源内嵌在桌面面板内部。
2. **禁止空壳、禁止留空白框**：每个视觉元素背后必须承载真实可用的后端能力，主屏左/中/右三栏与 10 大功能卡片全部直连实机状态。
3. **3D 空间控制台，绝不是“旋转立方体”**：采用全屏 3D 透视网格、轨道雷达 HUD、卡片 3D 悬停跟手微倾，以及基于 GPU WebGL GLSL 的电影级实景着色器。
4. **凭据与隐私零落库**：所有 API Key、中转域名、qBittorrent 密码、RPC 密钥与本机路径仅存于本地 `config.json`（已加入 `.gitignore`），代码、注释、日志、文档严禁硬编码；提交前强制跑 `scripts/scan_secrets.py`。
5. **只做调度与聚合，不打包第三方二进制/模型权重**：不内嵌 aria2 / qBittorrent / ffmpeg / ComfyUI 模型权重，全部复用用户本机已装环境或从官方地址按需配置；启停服务只操作面板自身记录的 PID，绝不全局 `taskkill`。

---

## ✨ 核心功能全景（11 大站内工坊 + 12 项首页传送门 + 常驻智能体）

### 1. ✦ 3D 空间控制台总览大屏（Cockpit）
- **3D 全息轨道指挥核**：实时 3D 轨道雷达 + 6 颗引擎运行卫星 + 5 层实时吞吐量能量波面 + 5 项核心指标（总下行/峰值速率、活跃任务/连接、BT 种子/DHT 节点、本地 GPU 显存占用、AI 与智能体状态）。
- **全能智能投递舱（Omni Dispatch）**：单一输入框自动识别 HTTP 直链、磁力/InfoHash、YouTube/B站/抖音视频链接、歌曲名、AI 生图提示词或向小怪兽提问，一键分流直达。
- **全站 10 大核心工坊 3D 霓虹矩阵**：10 张带 3D 悬停微倾的实时状态卡，点击 100% 站内跳转，消灭一切死卡片。
- **双核直出展台 & 左右动力翼**：左翼 5 大引擎实时启停/显存仪表；中下双栏同时展示「最近成品直出舱」与「AI 画室直出墙」；右翼集成实时任务雷达、热歌/飙升/抖音即点即播台与实时遥测终端。

### 2. 🎬 YT / 全平台视频下载工坊
- 支持 YouTube、Bilibili、抖音、小红书、TikTok、X 等主流平台链接与分享口令自动提取。
- 一键选择画质（最佳 4K/HDR、1080P、720P、仅提取 MP3）、浏览器 Cookies 自动识别或手动 `cookies.txt`、**Video2X 2x AI 超分开关**、实时进度条、取消并清理整棵进程树与内核日志。

### 3. 🎵 全网 6 音源音乐榜单与秒播中心
- **6 大官方实时榜单**：热歌榜、飙升榜、新歌榜、抖音热歌、原创榜、欧美热歌（网易云 v6 + QQ 音乐双源兜底）。
- **6 大音源并发聚合检索**：同时并发搜索 **QQ 音乐、酷狗、网易云、酷我、B站音乐、YouTube**，去重聚合，周杰伦等热门原唱优先命中。
- **免下载一键站内秒播**：优先命中本地已下载音频，否则自动通过同源音频流代理（`/api/stream_audio`，完整支持 `Range` 拖动进度条）实时播放高清音频。
- **三层 LRC 同步歌词**：本地同名 `.lrc` → 网易云（含双语翻译）→ 酷狗全版权歌词库自动兜底。
- **多格式下载**：支持 MP3 / FLAC / M4A / WAV 下载并自动扫描入最近成品舱。

### 4. 🌌 电影级 GPU WebGL GLSL 全屏沉浸 3D 歌词舞台
- **真·零遮挡全屏沉浸**（点击 `⛶ 全屏沉浸` / 双击画面 / 按 `F`）：隐藏顶栏、侧栏、浮标与边框，100vw × 100vh 铺满屏幕；鼠标静止 **2.4 秒** 后自动隐去全部浮动控件与光标，轻动鼠标柔和唤醒；支持「影院封面+歌词」与「纯净居中歌词」双版式切换。
- **6 大电影级 GPU 着色器实景（随歌曲意境自动切换，也可按 `M` 手动切换）**：
  - `🌊 深海月光`：真实 3D 透视海平面、波纹法线碎银月光反射、微云与细星。
  - `🌧️ 雨夜车窗`：物理折射雨滴滑落玻璃 + 11 盏 35mm 大光圈城市虚化散景光斑。
  - `🌅 日落微光`：暮色体积霞光云海 + 暖色逆光散射与柔光浮尘。
  - `🏔️ 水墨月雾`：多层流动水墨云海 + 朦胧孤月与远山薄雾剪影。
  - `🎬 暗室舞台`：3 束体积聚光灯穿透烟雾扫射 + 变形宽银幕光晕与湿润舞台倒影。
  - `✨ 流光色韵`：域扭曲液态丝绸流体，柔和呼吸律动。
- **真实音频 FFT 驱动 + ACES 电影色调**：接入同源 WebAudio `AnalyserNode` 实时响应低/中/高频鼓点与人声，辅以 ACES 电影高光滚落与 35mm 微胶片颗粒。

### 5. 🎨 AI 创作画室（本地 ComfyUI + 自定义模型 + 提示词引擎）
- **提示词直出，全程站内**：
  - **文生图（T2I）**：对接本地 ComfyUI（如 Z-Image Turbo / SD Checkpoint），结果直接渲染在站内画廊，点击弹出全屏灯箱预览。
  - **一键文生视频（T2V） & 图生视频（I2V）**：支持「提示词 → 自动生成首帧 → Wan 2.2 I2V 出片」单次输入全自动链路，也支持上传本地首帧或将画廊图片一键设为视频首帧。
- **🔌 接入自己的本地模型**：任何终端用户均可点击画室顶部的「接入自己的本地模型」，填入自己的 **自定义 ComfyUI 地址与 API Workflow JSON**（支持 `{{PROMPT}}` / `{{NEG_PROMPT}}` / `{{IMAGE}}` / `{{SEED}}` 占位符）、**Stable Diffusion WebUI / Forge** 或 **OpenAI Images 兼容接口**，配置安全存于本地 `config.json`。
- **✨ 专业提示词搜索引擎 & AI 大师优化架构师**（`prompt_engine.py`）：
  - **13 大分类 54 套大师级模板库**：专为 Lumina2 / Qwen 编码器与 Wan 2.2 调优的自然语言电影提示词（拒绝老式无意义堆砌词）。
  - **中英语义检索 + 关键词即时合成 6 风格模板**：输入任意中文或英文关键词，毫秒返回精选匹配 + 6 套专属定制风格模板。
  - **✨ AI 大师一键优化**：调用本机配置的 Codex 智能体，把任意一句口语想法升格为 **3 套差异化大师方案**（电影写实版 / 概念美学版 / Wan2.2 运镜视频版），附中文拆解、精准负向词与最佳画幅，一键填入或立即生成。
  - **专业词缀积木栏**：一键追加光影、电影镜头焦段与 Wan 2.2 运镜修饰语。

### 6. 🎙️ 开源 AI 声音克隆 & 神经配音工坊
- **零污染独立虚拟环境（`.venv-voice`）**：一键部署 **F5-TTS (CUDA)**，不污染主 Python 环境。
- 支持上传 3~15 秒参考音频或浏览器**麦克风直录**（自动用 ffmpeg 标准化为 24kHz 单声道 WAV），同时内置零显卡秒出的多情感 **Edge-TTS 神经配音** 以及 **外部克隆 API（GPT-SoVITS / CosyVoice / FishSpeech）** 接口。

### 7. ⚡ 下载核心（全站内同源嵌入）
- **实时任务队列**：统一管理 Aria2 与 qBittorrent 活跃任务（暂停 / 继续 / 移除 / 自动分流投递）。
- **内置同源 AriaNg**：`/ariang/` 同源直嵌，自动注入 RPC 密钥。
- **内置同源 qBittorrent**：`/qbit/` 后端反向代理重写 `<base>` 路径，直接在软件窗口内操作完整 WebUI。
- **5 源并发站内磁力搜索引擎 + DHT 修复实验室**：
  - 全程站内并发检索 **Knaben 聚合 / APIBay / SolidTorrents / 蜜柑计划 (Mikan) / Nyaa** 五大公开源（自动去重、按做种数/体积/时间排序、中文查询自动过滤无关英文热榜脏数据），支持从顶部全能输入栏、队列栏或磁力舱直接输关键词搜磁力，并一键 **投递 qBittorrent / 投递 Aria2 / 复制磁力 / 填入解析器**。
  - 支持 `magnet:?` 与 40 位 InfoHash 解析、秒级预取 `.torrent` 元数据、一键热更新公共 Tracker 至运行中的 Aria2 / qBittorrent、无损修复 `aria2.conf` BT/DHT 参数与 DHT 引导探测。

### 8. 🎞️ 站内原画 4K 影院（零压缩直出 · 4K画质修复 · 看完即删）
- **原画质零压缩播放**：下载完成的种子/视频自动入库并弹窗一键全屏观影；原生容器走 `/api/media` HTTP 206 原字节直出，遇到 MKV/TS 或 AC3/DTS/TrueHD 音轨自动切换 `/api/stream_video`（`ffmpeg -c:v copy` 视频比特级零压缩 + 320k AAC 实时音轨解码），并自动挂载外挂 `.srt/.vtt/.ass` 与 MKV 内嵌字幕。
- **✨ 双重 4K 画质修复引擎**：
  - **0 延迟 GPU 实时修复（快捷键 `E`）**：基于 WebGL2 的 **AMD FidelityFX CAS（对比度自适应锐化）** + 物理像素渲染 + HDR10/HLG 防发灰自动还原，支持实时滑块微调与分屏对比原画。
  - **RTX 显卡深度重建纯 4K 母带**：针对低清/高压缩源片，一键后台调用 `hevc_nvenc`（`Deblock + HQDN3D + Lanczos 3840×2160 + CAS`）重建 40Mbps 级高码率纯 4K 母带（不覆盖原片）。
- **🗑️ 看完即删 & 清缓存**：播完自动弹出「看完即删 & 清缓存」面板，先安全卸载播放锁再同步删除影片、关联 qB 种子、同名字幕、空子目录与临时缓存（保留 `trackers.txt`）。
- **📸 4K 无损原画截图 & ✂️ 极速无损高光剪辑（创意联动闭环）**：快捷键 `S` 直接抓取原始 4K PNG 截图并可一键送入 **AI 画室作为 Wan 2.2 视频首帧**；A-B 区间 0.3 秒零压缩无损导出高光片段 (`-c:v copy`)、320K 音轨，或一键截取电影台词作为 **AI 声音克隆参考音**。
- **💿 磁盘空间实时卫士 & 🌙 挂机下完自动动作**：顶栏常驻实时下载盘剩余空间预警（`<30GB` 琥珀预警 / `<10GB` 红色警告）；下载队列栏支持预约「下完停种 / 下完睡眠 / 下完 60 秒关机」（带 15 秒安全倒计时随时取消）。

### 9. 👾 赛博小怪兽 · Codex 内置智能体
- 全站右下角常驻悬浮 **赛博小怪兽**（SVG 霓虹精灵 + 实时跟随鼠标转动的电子眼），在任意页面点击即弹出站内多轮问答框，自动感知当前页面与本机引擎状态（严格脱敏）。
- 支持在 **👾 智能体** 页面配置任意 OpenAI / Codex 兼容中转地址、模型名与 API Key（支持一键拉取可用模型列表，代理/直连自动回退，密钥仅写本地 `config.json`）。

### 10. 🛠️ 系统与运维中心 & 📖 内置交互式教程模块
- **系统与运维中心**：全局端口/路径配置、开机自启开关、一键自检、端口扫描、一键备份配置、日志清空/导出、清理缓存与安全停止全部服务。
- **📖 站内全功能教程模板**：顶部导航直达，内置 10 大功能完整步骤教程、避坑技巧、FAQ 与关键词实时筛选，每章提供「🚀 立即前往」按钮一键跳转对应工坊；离线文档同步维护于 [TUTORIAL.md](TUTORIAL.md)。

---

## 🚀 快速开始

### 1. 首次一键配置

| 平台 | 入口 | 用法 |
| --- | --- | --- |
| **Windows** | `一键配置.bat` | 双击打开向导 → 点「一键配置(含环境)」 |
| **Linux / macOS** | `一键配置.sh` | 终端执行：`sh 一键配置.sh`（支持 `--scan` / `--auto`） |

### 2. 启动 3D 控制台

- **Windows**：双击 `启动面板.bat`（或命令行运行 `python -B panel.py`），自动以无边框桌面 App 窗口打开 `http://127.0.0.1:18550/`。
- **Linux / macOS**：`sh 启动面板.sh`（无桌面环境可访问 `http://127.0.0.1:18550/`）。

### 3. 接入 AI 能力（可选，按需开启）
- **AI 画室本地模型**：进入 **🎨 AI画室** → 点右上角 **「🔌 接入自己的本地模型」** → 填写你的 ComfyUI / SD WebUI / OpenAI Image 接口地址即可生效。
- **赛博小怪兽 & AI 提示词优化**：进入 **👾 智能体** → 填写你的中转域名与 API Key → 点 **「🔎 拉取可用模型」** 选好模型并保存（仅写入本地 `config.json`）。

---

## 📁 仓库目录结构

```text
downloadstack-control/
├─ panel.py              核心本地服务（HTTP /api/state、/api/action、/api/media、/api/stream_audio、/ariang/、/qbit/ 代理）
├─ panel_ui.html         无构建链单文件 Spatial 3D Command OS 前端（含 WebGL GLSL 沉浸舞台）
├─ media_studio.py       6 音源搜歌、6 大榜单、LRC 歌词、音频流解析、声音克隆、ComfyUI 与 Codex 客户端
├─ prompt_engine.py      AI 画室提示词引擎（54+ 大师模板库、中英语义检索、动态合成、Codex 优化架构师）
├─ magnet_tools.py       5 源并发磁力搜索引擎、磁力 / InfoHash 解析、公共 Tracker 热更新、DHT 诊断与 aria2.conf 无损修复
├─ ytdl_gui.py           独立视频下载 GUI 工具
├─ setup_wizard.py       图形 / 命令行跨平台引导向导
├─ install.bat / .sh     一键环境与组件安装器（盘符自选、端口避让、SHA256 校验）
├─ 一键配置.bat / .sh     首次配置统一入口
├─ 启动面板.bat / .sh     面板启动器
├─ diag.bat / .sh        一键环境诊断脚本
├─ config.example.json   脱敏配置模板（运行时自动生成本地 config.json）
├─ scripts/
│  ├─ scan_secrets.py    提交前敏感信息与个人路径扫描器
│  └─ build.ps1          打包辅助脚本
├─ tests/test_core.py    核心单元测试
├─ TUTORIAL.md           全功能 11 章图文步骤使用教程手册
├─ CHANGELOG.md          版本发布说明（v2.5）
└─ LICENSE / NOTICE / SECURITY.md / CONTRIBUTING.md
```

---

## 🛡 提交前安全与单测自检

```bash
python scripts/scan_secrets.py .
python -m unittest discover -s tests -v
```

---

## 📄 License & 合规声明

MIT © DownloadStack Control contributors  
第三方组件许可信息见 [NOTICE](NOTICE)。

> 本仓库仅包含自有源码与文档，**不包含任何第三方二进制文件、模型权重、API 密钥或个人配置**。  
> 请仅下载与处理您拥有合法权限的内容，严格遵守所在地法律法规及各平台服务条款。
