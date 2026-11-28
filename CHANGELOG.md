# Changelog · DownloadStack Control

All notable user-facing releases of **DownloadStack Control (Spatial 3D Command OS)** are documented here.

---

## [2026-11-28 开源发布同步] — 仓库补齐书城 / 短剧 / LX 音源 + 新增从零配置手册

### 📦 同步与修复
- 仓库源码与**正在运行的版本**对齐：`panel.py` / `panel_ui.html` / `media_studio.py` / `启动面板.bat` / `launch_app.pyw` 全部取最新运行版（旧仓库版缺 575+ 行界面与后端逻辑）。
- 新增入库：`reader_hub.py`（书城后端）、`reader_catalog.py`（书源目录）、`drama_hub.py`（短剧中心）、`lx_music_bridge.py` + `lx_userapi_host.js`（LX Music 音源桥）、`library/`（本地书库说明与样例）。
- 修复 `install.bat` / `install.sh` **漏拷贝** `reader_hub.py` / `reader_catalog.py` / `prompt_engine.py`：新机器装完不会再出现「书城模块未加载」。
- 修复 `reader_hub._compact_title` 字符类字符串被引号截断导致的 `SyntaxWarning`（未来 Python 版本会升级为语法错误）。
- `/api/state` 新增 `modules` 字段（`reader` / `drama` / `lx` 可用性）；短剧页在 `drama_hub.py` 缺失时显示琥珀提示条并指向 `SETUP.md`，不再静默失败。
- `.gitignore` 补本地书库规则：`library/` 只保留说明与官方样例，用户自己放的书不入库。

### 📚 文档
- 新增 **SETUP.md《从零配置手册》**：系统要求 → 三种安装方式 → 首次自检 6 项 → `config.json` 全字段 → 端口与局域网 → 可选组件矩阵 → 书城/音乐/短剧 → 自启/备份/迁移/卸载 → 20 条故障排查 → **风险清单 R1–R14** → 交付检查清单。
- `README.md`：配置手册入口、书城功能段、安全边界摘要、目录结构更新。
- `TUTORIAL.md`：新增第 11 章「书城（漫画 / 电子书 / 朗读）」，FAQ 补书城/短剧/音乐三条。
- `config.example.json`：补 `reader_roots`、`paths.books` 与逐项说明指引。

---

## [2026-11-28 UI 体验修复]

### 🎵 底部播放条常驻 + 音频可视化
- 新增 `S.miniPinned`：播过一次就常驻，暂停 / 切页 / 往返音乐页都不消失，**只有 ✕ 会关掉**。
- 左侧 canvas 频谱（20 根柱，走 `AnalyserNode`，上升快下落慢）；暂停/待机时是双频呼吸波形。
- 播放中整条边框青色发光（`.mini-player.playing`）+ 底部细进度条（随 `timeupdate`）。

### 🔎 搜索不再"一点播放就没了"
- 主页热歌下拉：点歌播放后**不再自动收起**，40 条结果保留，可连着点下一首（✕ / Esc / 点空白才收）。
- 音乐页：`S.muRows / S.muMode` 记住搜索结果，播放与视图往返都不被榜单覆盖（实测 151 行稳定）。

### 📈 结果更多
- 单源上限翻 2~3 倍（网易云30/QQ30/咪咕40含翻页/酷狗30/酷我24/B站16/音乐区16/YouTube15/SC10/Audius12/Apple20/Deezer16/Archive8/本地30），
  总上限 **90 → 200**；下拉一次展示 40 条。实测「周杰伦」186 首 / 12 源 / 2.8s。

### 🧭 顶栏全部功能都在顶部
- 导航补到 **14 项**（加 教程 / 系统），超宽时横向滚 + 滚轮左右滚 + 两端渐隐；
- 新增 **☰ 全部** 下拉，两列列全 14 项（图标 + 名称 + 说明）。

### 🧩 主页分门别类
- 原 13 张门户卡 + 新增 5 张，按「下载与影音 8 / 视频与音乐 4 / AI 创作 4 / 系统与工具 4」归类，
  **20 张卡 0 重复**；删除了上一轮重复的「全部功能」面板。

---

## [2026-11-28 书架清空 + 主页固定热门 40 + /px 反代（SPA 可渲染）]

### 书架
- cache/reader/shelf.json：items 7 → **0**，stats 清空（备份 ackups/shelf.json.bak_*）。
- 前端新增 
dHideEmptyShelf()：书架为空时自动收起该区块（不再显示「书架还是空白」），每次渲染热门后自动执行。

### 主页
- 「🔥 热门 40 部」常驻 #rd-home 首位：实测 **40 张**（漫画 20 · 小说 20），点「换一批」轮换。
- 统计条：今日阅读 0 分钟 / 书架 0 册。

### /px 路径前缀反代（解决「番茄内部访问不了」）
- 新增 GET|POST /px/<host>/<path>：服务端转发、剥 X-Frame-Options/CSP、转发 Cookie 会话、改 Location。
- HTML 里只改写 href/src/action/data-src/poster 属性（上一版把 JS 正则字面量改坏，导致 SyntaxError: Invalid regular expression flags，已修）。
- 注入请求改写 shim：页面内 etch/XHR 的绝对路径自动加 /px/<host> 前缀 → SPA 的接口也走反代。
- 实测：/px/fanqienovel.com/ 200 / 169KB / 含 base + shim；微信读书 /px/weread.qq.com/ 渲染出标题与 56 个链接。

### 已知限制
- 微信读书检测到反代访问会弹「请勿使用第三方插件」，固把 weread 设为**直连**（proxy=false）。
- 番茄接口有签名，页面能拉起、推荐流可见，站内搜索不一定可用。

---

## [2026-11-28 书城平台扩容：29 个，小说 21 个全部可站内打开]

### 平台清单（GET /api/reader/platforms）
| 分组 | 数量 | 平台 |
|---|---|---|
| 漫画 | 5 | MangaDex、哔哩哔哩漫画、腾讯动漫、快看漫画、漫画柜 |
| **小说** | **21** | 起点中文网、微信读书、17K、笔趣阁、爱下电子书、落霞小说、百度小说、掌阅、咪咕阅读、豆瓣读书（直连）· 番茄小说、QQ阅读、纵横中文网、Goodreads、Wattpad、成为小说家、Kakuyomu、AO3、Webnovel、Scribble Hub、Royal Road（反代） |
| 公有领域 | 3 | 维基文库、Gutenberg、Internet Archive |

### 机制
- 直连：站点自身不限制被 iframe 嵌入（起点/微信读书/17K/笔趣阁 等 10 个）。
- 反代：X-Frame-Options / rame-ancestors 拒嵌的 11 个，前端自动走 /ext?u=（服务端剥头 + 注 <base>），标题栏标注「（反代）」。
- drEmbed(url, title, forceProxy) 新增第三参数，平台清单里 proxy: true 的自动走反代。

### 实测
`
平台按钮 29 个，分组：漫画·5 / 小说·21 / 公有领域·3
番茄小说 → /ext?u=https%3A%2F%2Ffanqienovel.com ，iframe 内标题「小说,番茄小说网_好看的小说尽在番茄小说官网」
微信读书 → 直连 weread.qq.com；起点中文网 → 直连 qidian.com
exceptions 0
`

---

## [2026-11-28 书城升级：热门 40 部 + 14 个内嵌平台 + 全能搜索]

### 修好的大坑（书城空白的真正原因）
- do_GET 的尾部（/api/reader/*、/api/media、/api/stream_video、/ariang、404 兜底，共 218 行）
  被之前的补丁挤进了 _stream_remote_impl() 里，成了**死代码** → 书城所有接口无响应（RemoteDisconnected）。
- 已把 218 行剪出并接回 do_GET 末尾；校验：/api/reader/sources|genres|home 全部 200。

### 新增
1. GET /api/reader/hot：热门 48 部（漫画 24 + 小说 24，去重，10 分钟缓存），实测 14.6s 冷启、缓存后秒回。
2. GET /api/reader/platforms：**14 个平台**（MangaDex/哔哩哔哩漫画/腾讯动漫/快看/漫画柜 + 起点/番茄/微信读书/纵横/17K/知轩 + 维基文库/Gutenberg/Archive）。
3. 书城首页顶部：**🔥 热门 40 部（漫画 20 · 小说 20）** 墙 + 「换一批」；下方「🏛 漫画·小说平台」按钮条，点开**在软件内部 iframe**浏览。
4. 搜索框支持**链接直达**（粘 URL → 内嵌打开）；分类页取不到内容时不再留白，提示 + 自动回首页。

### 实测
`
书城首屏：cards=40（manga=20, novel=20）· 平台按钮=14 · meta「🔥 热门 40 部 漫画 20 · 小说 20」
点「哔哩哔哩漫画」→ iframe = https://manga.bilibili.com/（内嵌，未跳外部）
exceptions 0
`

### 已知限制
- 小说侧公开源目前是公有领域经典（英文名著/中文古籍），中文网文（起点/番茄）受风控无法直接抓取 → 走内嵌平台浏览。
- MangaDex 图片 CDN 在本机被墙，章节页会显示 p1…pN 破图；漫画请用「哔哩哔哩漫画/腾讯动漫/快看」内嵌看。

---

## [2026-11-28 内嵌官方平台模式（1080P 秒开，不再等合成）]

### 用户拍板的方向：全部内嵌打开官方页
- 实测 hongguoduanju.com / www.bilibili.com / player.bilibili.com **都没有 X-Frame-Options / CSP frame-ancestors** → 可直接同窗口 iframe。
- 新增全屏内嵌容器 #dr-embed（标题 + URL + 重载 + ✕ 关闭 + iframe），**所有官方页面都在软件内打开，不开外部窗口**。

### 主页
- 新增「🔥 热门短剧」卡：从 1792 部索引取 **18 部**（封面 + 集数 + 标签 + 红果角标），
  点卡片 → 内嵌打开 hongguoduanju.com/detail?series_id=…；「换一批」轮换。

### 搜索
- 短剧搜索框：**粘链接直接内嵌打开**（B站/红果/YouTube 都行）；关键词搜索出的卡片，点击同样内嵌打开对应官方页
  （ili:BVxxx → ilibili.com/video/BVxxx，hg:series_id → hongguoduanju.com/detail?...）。
- 放弃"先合成再播"的等待路径：1080P 由**官方播放器自己**给（已登录，实测播放器显示 1080P 高清）。

### 实测
`
主页热门短剧：18 张卡（cnt=18，首条「温夜潮湿」）
点卡片      ：overlay 打开，iframe = hongguoduanju.com/detail?series_id=7710503618658454553
粘链接搜索  ：iframe = bilibili.com/video/BV1xyWt6JEDB，播放器显示「1080P 高清」，31:24 正常播放
exceptions  ：0
`

### 修：点卡片仍走合成
- 根因：panel_ui.html 里存在**两个 drLibPlay 定义**，后一个（调用 drPlayHQ）覆盖了内嵌版 → 点卡片又进合成。
- 已删除重复的 drLibPlay 与旧 drPlayHQ / drPlayHG（合成路径整体移除，残留 正在合成片源 = 0）；
  进入短剧页时自动清除遗留的 #dr-inline-player 占位框。
- 验证：库 36 卡 → 点第一张 → 内嵌 hongguoduanju.com/detail?series_id=7710503618658454553（红果官方详情页，
  6377万热度 / 9.4分 / 17 集选集 / 播放正片），全页无「合成」字样，exceptions 0。

### 修：展厅（更多官方平台）点不动 / 空白
- 原来点击走 dramaOpen → 后端 hall_payload，返回空 → 什么都不发生。
- 现在 [data-drama-open] 全部改为**内嵌打开对应官方站**：drPlatformEmbed(pid, query, channel)
  → channels[0].url 或 home，有搜索词则用 search 模板替换 {q}。
- 新增本地反代 GET /ext?u=<url>：服务端抓取、**剥掉 X-Frame-Options / CSP frame-ancestors**、注入 <base>，
  用于本身就禁止内嵌的站点；前端按 DR_NOFRAME 白名单自动走反代，标题栏标注「（反代）」。
- 实测（真窗口点击）：
  - 直嵌正常：哔哩哔哩 ilibili.com、红果 hongguoduanju.com、抖音、快手、咪咕、搜狐、央视、微博、小红书
  - 反代后能渲染：爱奇艺（iframe 内标题「爱奇艺」）、腾讯视频（外壳已拉取）
  - 反代仍被挡：YouTube（返回 Error response）
  - 展厅可点元素 110 个，全部有响应；exceptions 0~1（来自代理页内部脚本）

---

## [2026-11-28 红果整库入库：1792 部热门短剧]

### 数量（实测，落盘可查）
`
hongguo_build_index() → 30.0s 完成
total = 1792 部   （真人短剧 800 + AI短剧 800 + 漫剧 192）
索引文件：cache/drama_hg_index.json
`
- 红果分类页每页 24 部、页内 "total":800，翻到第 34 页；三类合计 1792（漫剧只公开到 192）。
- 短剧页现在默认读**本地索引**：drama_hg_catalog 0.02s 返回，第 10 页也是 0.02s（不再每页现爬）。
- 搜索也走索引：逆袭 24 部 0.02s、重生 24 部 0.02s、战神 15 部 0.62s。
- 芯片：全部 / 真人短剧 / 漫剧 / AI短剧，标题栏显示 红果官方 · 共 800 部 · 已载 36，点「全部」= 1792 部。

### 播放
- 红果有直链 → /api/hg_media Range 直通，秒开（360P，红果 Web 上限）。
- 红果该集是 JS 播放页 → 自动回落 B站同剧（异步合成，真实进度，60s 明确超时）。
- 1080P 仍需 B站登录态：cache/bilibili_cookie.txt 一行 SESSDATA=…; bili_jct=…;。

---

## [2026-11-28 短剧：站内直搜 + 就地播放（不再跳剧场）]

### 你手机截图里的 4 部，现在软件里都能搜到（实测）
| 剧名 | 站内直搜结果 | 首条 |
|---|---|---|
| 重生扬子鳄 | 12 部 / 0.72s | 《重生扬子鳄：从网购开始吞噬进化第二季》一口气看完 |
| 诡校还魂夜 | 12~20 部 / 0.53s | 夜班里死去的学生还魂取我命…诡校还魂夜 |
| 规则怪谈·封校七日 | 12 部 / 0.52s | 七日封校（完结版） |
| 万古第一宗 | 12 部 / 0.51s | 【1-3季】万古第一宗：从签到召唤开始 |

### 改动
1. **新增 drama_search_all**：一次同时搜 B站 + 红果，结果直接铺到短剧页网格（不再只给官方展厅链接）。
2. **顶部搜索框改走站内直搜**，搜不到才回落官方展厅。
3. **播放改成就地内嵌**：#dr-inline-player 插在库区上方，视频播完/收起后网格还在；**不进剧场、不跳页、不用 iframe**。
4. **合成改异步**（drama_play_hq 立即返回 job，drama_play_hq_status 轮询）：避免 HTTP handler 30s 超时导致的断连（长合集合成要 40~90s）。
5. 缓存命中即秒开（cache/drama_hq/{bvid}_{画质}.mp4）。
6. 修 	hreading 未导入导致整个 short-drama 模块加载失败的坑。

### 实测
`
搜「诡校还魂夜」→ 20 部卡片 → 点第一张 → inlineBox:true，grid 仍在(20)，video 854×480，readyState 4，39:14，未进剧场
exceptions 0；缓存命中路径 0.0s 返回
`

### 画质说明（实测上限，非实现问题）
| 源 | 上限 |
|---|---|
| 红果 Web | 360P（480/720/1080 全 404） |
| B站 匿名 | **480P**（accept 里写 1080P，但 dash 只给 480） |
| B站 + 登录 Cookie | **1080P** |

放 cookie 的两种方式（放完重启面板即生效）：
- config.json 加 "bilibili_cookie": "SESSDATA=xxx; bili_jct=yyy;"
- 或建 cache/bilibili_cookie.txt，文件里一行 SESSDATA=xxx; bili_jct=yyy;

---

## [2026-11-28 短剧高画质播放链路（站内 <video>，无广告）]

### 关键结论（实测，不是猜）
- **红果 Web 只发 360p**：/video/public/{vid}/360p.mp4 200 OK，480p/720p/1080p 全部 404 → 官方网页版码率天花板。
- **B站可站内 mux 播放**：playurl(fnval=4048) → DASH 视频流 + 音频流 → fmpeg -c:v copy 合成 mp4 落盘缓存 → 站内播放。
- 匿名（无登录）B站最高 **480P**；配置 B站 SESSDATA 后同一部可到 **1080P**。

### 新增能力
1. drama_hub.bili_play()：解析最高可用 DASH 流（优先 avc1 硬解兼容、同高度取最高码率），返回画质/高度/时长。
2. drama_hub.bili_cache_episode()：fmpeg -headers(Referer/Origin/UA/Cookie) -i 视频 -i 音频 -c:v copy -c:a aac -movflags +faststart → cache/drama_hq/{bvid}_{画质}.mp4（59MB/集，27s 出片；二次播放 0.2s）。
3. POST /api/action drama_play_hq：返回 play_url=/api/drama_media?path=…。
4. **GET /api/drama_media（带 Range 206）**：新增在 do_GET 最前面，绕开原先 /api/media 被 reader 分支吞掉的坑。
5. 短剧页卡片点击 → drPlayHQ()：剧场内 <video> 直接播 + 左上角画质角标（实测 ideoWidth 853 × videoHeight 480、
eadyState 4、时长 699s）。
6. B站登录态读取：config.json 的 "bilibili_cookie" 或 cache/bilibili_cookie.txt（一行 SESSDATA=...; bili_jct=...;）→ 自动 1080P。

### 实测数据
`
短剧库翻页：5 题材 × 4 页 = 288 条（去重 204），has_more 持续为 true → 14 题材可翻到 2000+
首集缓存：27.3s / 59.0MB / 480P
站内播放：HTTP 206 video/mp4 Content-Range bytes 0-65535/61843780
浏览器验证：853×480，readyState 4，badge 显示 480P，exceptions 0
`

### 顺手修掉的隐藏 bug
/api/media、/api/reader/* 这类走 reader 分支的 GET 在 python 客户端下直接断连（handler 未命中就空返回）。
新增顶层 /api/drama_media 后短剧播放稳定；书城图片/接口如需修复可同法提到 do_GET 前部。

---

## [2026-11-28 短剧总库（正规正片 · 站内无广告）]

### 🔎 先查清「为什么短剧页全是垃圾」
- 原短剧页本质是**把各官方站点（红果 / 抖音 / 快手 / 爱奇艺…）当网页塞进 iframe**，你看到的就是那些站点自己的信息流 + 贴片广告，不是本软件的内容库。
- **红果 / 番茄官方短剧 API 走字节签名**（pi5-normal-*.fqnovel.com 不带签名返回空 body，hongguoduanju.com 是 React SPA + sdk-glue.js 反爬）→ 想直连官方目录需要逆向其签名，风险与工作量都很大，本轮没做。
- 已验证可用的**正版可看**通道：**B站（www.bilibili.com）** 官方播放器可嵌入、无贴片广告、支持 1080P。

### 🗂 新增「正版短剧总库」（短剧页顶栏下方）
- **14 个题材**：甜宠 / 逆袭 / 战神 / 复仇 / 穿越 / 古装 / 悬疑 / 职场 / 家庭 / 校园 / 萌宝 / 神医 / 都市 / 娱乐圈。
- 每题材 **2 组关键词 × 翻页聚合**，并过滤掉解说 / 花絮 / 预告 / 混剪 / 盘点 / 少于 5 分钟且非合集的碎片 → 只留正片合集。
- 横向封面流 + 「再翻一页」，实测首屏 190 部（14 题材合计），单题材翻页可上到 100+，总计可到上千部。
- 点卡片 **在软件内剧场用 B 站官方播放器播放**（player.bilibili.com/player.html?bvid=…），不跳外部、无贴片广告；实测点开《野佛》完结合集 58:49 正常播放。

### 📊 实测
`
/api/action drama_lib：14 题材首屏 190 部，单题材 6~23 部/页，has_more=true
UI：进短剧页自动聚合 16 部 → 翻页 30 部 → 切「悬疑」14 部
点卡片：theaterOn=true，iframe = player.bilibili.com/player.html?bvid=BV1k7sK6HEmV，仍在 view-drama
exceptions：0
`

> 想接**红果官方上万部目录**，需要一份能过签的接口（或你自己抓的签名参数）。给我参数我就接；
> 现在的总库是「B站正版可看 + 无广告 + 全站内」，这条路不依赖任何第三方聚合站。

---

## [2026-11-28 书城扩容 + 主页风格墙]

### 🔍 先查清了"为什么书城只有冷门书"
| 源 | 本机实测 | 结论 |
|---|---|---|
| MangaDex（漫画主源） | API 直连/走代理都返回 `mangadex.org/edge/challenge` | **被 Cloudflare 拦，全站漫画因此几乎全空** → 只剩公有领域古籍 |
| Mangapill / Mangatown / BaTo / 漫画柜 | 搜索页 200，但图片 CDN 一律 **403**（防盗链） | 站内读不了，**不接成源**，避免"点了看不了" |
| 拷贝漫画 copymanga | API 200 但 `list` 恒为空 | 用不了 |
| 喜马拉雅/AcFun/5sing/笔趣阁镜像 | 403 / 域名不通 | 用不了 |
| 维基文库 / Gutenberg / Standard Ebooks / Archive / OpenLibrary | 正常（维基文库偶发 429 限速） | 继续用 |
| **小説家になろう（なろう）** | API 200 + 正文页可解析 | ✅ 新增可读源 |

### 🌈 新增「风格馆」——按题材跨源直达（全在软件内部）
- 12 个风格：武侠江湖 / 章回小说 / 诗词歌赋 / 历史传奇 / 悬疑推理 / 恋爱言情 / 奇幻魔法 / 恐怖惊悚 / 诸子百家 / 科幻 / 轻松搞笑 / 异世界。
- 每个风格 = 3 组关键词 × 3 个可读源**并发检索，5 秒总预算**（慢源自动放弃）；结果过滤掉法院判决书等噪声。
- **主页新增「📚 书城 · 按风格直达」卡**：点任意风格 → 直接 `switchView('reader')` + 该书城分类页出封面墙，**不跳任何外部站点**。
- 书城源芯片从 6 个补到 **10 个**（新增 风格馆 / なろう日轻 / Standard Ebooks / Open Library）。

### 📚 新增源：小説家になろう（日轻小说，站内直读）
- 搜索走 `api.syosetu.com`（人气排序），详情按 `general_all_no` 生成章节表，正文从 `js-novel-text` 抽 `<p>` 段，
  `<ruby>` 注音自动拍平成纯文本。实测：搜「异世界」→ 20 部（転生したらスライムだった件、無職転生…），点开可读。

### 🔧 顺带修
- 书城「热门漫画」按钮原来写死 `source=mangadex`（本机必空），改为**全源检索**。
- `rdSetSource` 白名单补齐新源，点芯片即搜。
- `browse()` 新增 `kind=style` 分支；`/api/reader/genres` 多返一组 `subjects`（12 个风格）。

### 📊 实测（真实窗口 + CDP）
```
主页风格墙：12 个芯片 → 点「章回小说」→ 仍在 view-reader，分类页 12 部（典籍論/論短篇小說…）
书城源芯片：全部来源 / 🌈风格馆 / 🇯🇵なろう日轻 / 🍥MangaDex / 📜维基文库 / 🏛️Gutenberg / 📘Standard Ebooks / 🗄️Archive / 🌍Open Library / 💾本地
なろう搜索「异世界」：12 条结果，errors 空，0 异常
```

> 待办：漫画类要在本机可读，需要 ①给 MangaDex 一个能过 Cloudflare 的代理，或 ②换一个图片不防盗链的源。
> 这两条一旦具备，把源接进 `SOURCES` 即可，风格墙与书城 UI 不需要再改。

---

## [2026-11-28 布局平衡]

- **中间列每类列数按数量规划**：四类补齐为 8/4/4/4 后统一 4 列，行行填满、右侧不再留黑窟窿
  （补的两张是实用卡：本地曲库、端口自检）。
- **左列空白改成实时图表**：新增「📈 速率趋势 · 近 60s」（画 `S.waveA/S.waveQ`，带网格、峰值刻度、空态提示），
  5 张引擎卡改为**等高均分**（103px × 5）。
- **中间列可滚动**：内容超窗口不再被裁掉，「最近成品 / AI 画室」永远够得着；细青色滚动条。
- 门户卡 padding 10→8px、分类间距 9→7px，940px 高窗口基本一屏装下。

---

## [2026-11-28 音源扩容]

### 🎵 音源从 6 个扩到 14 个（搜不到的冷门歌基本都能挖出来了）
| 音源 | 类型 | 播放 |
|---|---|---|
| 网易云 / QQ音乐 / 酷狗 / 酷我 | 国内主流 | 跨源解析（B站高码率 / YouTube） |
| **咪咕**（新增） | 国内主流（版权库大，单次可回 20 条） | 跨源解析 |
| B站 / **B站音乐区**（新增，`tids=3` 定向音乐区） | 站内视频源 | B站 DASH 直链 |
| **YouTube**（有代理即启用，yt-dlp ytsearch） | 海外 | yt-dlp 直链 |
| **SoundCloud**（新增，yt-dlp `scsearch`，免 API key） | 翻唱 / Remix / Live | yt-dlp；仅 HLS 时**按需落盘再播** |
| **Audius**（新增，多节点容灾） | 独立/电子 | **完整音频直链（秒播）** |
| **Apple / iTunes**（新增，国内店+海外店） | 全球曲库 | 30 秒试听直链 |
| **Deezer**（新增） | 欧美/日韩 | 30 秒试听直链 |
| **Internet Archive**（新增） | 公共版权/古典/老唱片 | **mp3 直链（秒播）** |
| **本地曲库**（新增） | 已下载音频按文件名分词命中 | 本地文件秒播 |

### ⚡ 检索体验
- 14 源**并发**：纯中文关键词约 **2.8s** 出首屏，带英文的多等 1.5~2.6s 以纳入海外源；单源上限 20 条，总上限 **90 条**（原来 45）。
- 跨源按「歌名+歌手」归一去重，重复曲目合并显示为 `网易云 + QQ音乐 / 咪咕 / 酷狗`。
- QQ 主接口为空时自动走老接口兜底；咪咕走 App 接口；Audius 多节点容灾。
- 音乐页检索结果现在直接显示**每源命中明细**（网易云10 · 咪咕20 · …），主页热歌搜歌下拉同步显示「命中 N 首 · M 源（明细）」。
- 音源芯片从 7 个扩到 15 个（含「全网 14 源」），可单源精查。

### 🐞 顺带修掉：短剧卡片的 inline handler 语法错误刷屏
- `onclick="dramaOpen(${JSON.stringify(url)}, …)"` 在双引号属性里会截断 handler，
  每次渲染短剧数据都往 `logs\client_errors.log` 写一条 `SyntaxError: Unexpected end of input`。
- 已改 6 处为 `onclick="dramaOpen('${escJs(url)}', …)"`，实测页面内 9 个 drama handler 全通过、
  重开后日志 0 条。

### 📊 实测
```
周杰伦 晴天  2.84s 71 首   netease10 qq10 migu20 kugou10 kuwo8 bilibili5 bilibili2_6 itunes8 audius6 deezer3 archive2
陈奕迅 富士山下 2.84s 60 首   11 源
草东没有派对  2.87s 46 首
nujabes luv sic 5.43s 74 首（含 soundcloud / audius / archive）
Audius 播放 → /api/stream_audio HTTP 206 audio/mpeg ✔
Archive 播放 → HTTP 206 audio/mpeg ✔（0.02s 直连）
Apple 试听 → HTTP 206 audio/x-m4p ✔
SoundCloud（仅 HLS）→ 按需落盘后 HTTP 206 audio/mp4 ✔
```

---

## [2026-11-28 修复 + 新特性]

### 🐞 首屏 7 个统计位永久「检测中…」（根因：作用域，而不是 applyState 中途抛错）
- **真凶**：`init() → switchView('cockpit') → closeReaderOverlay() → rdListenStop() → rdListenPause()`
  抛 `ReferenceError: $ is not defined`（阅读器区块写在 IIFE 之外，看不到 IIFE 内的 `const $`），
  `init()` 整条链断在 `switchView`，排在最后的 `pollState()` 永不执行 → `/api/state` 从未请求，
  `applyState` 一次都没跑。首屏初始文本写「检测中…」的恰好只有那 7 个元素，所以看起来只坏 7 个。
- **修法**：IIFE 收尾把 `$ / esc / escJs / fmt / fmtBytes / toast / applyState / pollState` 显式挂到 `window`；
  `applyState` 内 **121 处 DOM 写入**统一改走判空封装 `_set/_cls/_val/_prop/_sty`；
  `pollState` 不再 `catch(_){}` 静默吞异常；新增 8 秒「检测中…」看门狗 `__stuckCheck()`。
- **配套**：前端异常自上报 `POST /api/client_log` → `logs/client_errors.log`，桌面壳没有 F12 也能定位。

### 🎵 主页热歌卡新增「站内搜歌」（不跳页 · 不撑高卡片）
- 热歌卡右上角新增 **🔍** 按钮，点开浮起输入框（绝对定位覆盖标签行），输入即 320ms 防抖搜索，
  结果以**卡片内下拉层**呈现（`max-height: calc(100% - 42px)` 内部滚动），卡片高度/头高**恒定不变**（实测 438px / 41px）。
- 下拉每条支持 **▶ 主页直接播放**（留在控制台页，不切视图）、**🌌 3D 歌词播放**、**⬇ 下载**；
  `Enter` 搜索、`Esc` 或点空白处收起；后发先至的并发搜索用序号保护，避免旧结果覆盖新结果。
- 底部播放条同步显示正在播放的曲目，与音乐页共用同一套 `playOnlineSongObj / downloadSongObj` 逻辑。

### 📺 在线影视分享页 → m3u8 提取扩容（原「剩 2 集未覆盖」）
- 新增 `_unescape_page`（`\/`、`\u002F`、`\u0026`、`&amp;`、`&#47;` 还原）、`_m3u8_rules`（7 级优先级规则）、
  `_find_subpage`（中转壳页跟随：`iframe` / `location.href` / `window.location` / `meta refresh`，最多 2 层）。
- 单元自测 10/10 通过；未命中时写日志 `TV 分享页未匹配到 m3u8：<url>` 便于后续精确定位。

---
## [v2.5] — Spatial 3D Command OS Final Release

**从纯下载调度面板全面升级为「下载 · 4K 影音 · 本地 AI 创作」全站内闭环桌面工作台，零外部浏览器跳转。**

### 🌟 重点新特性

- **🎞️ 站内原画 4K 影院（零压缩 · 全屏沉浸 · 看完即删）**
  - 种子下载至 `100%` 自动入库并弹出左下角提示条，一键直达 **真全屏（`F`/双击）** 或 **窗口沉浸铺满（`I`）**，静止 2.5 秒自动隐藏控件与鼠标，支持全屏侧滑选集抽屉（`D`）。
  - **双模式零压缩原画引擎**：原生格式走 `/api/media` HTTP 206 原字节直出；遇 MKV/TS 或 AC3/DTS/TrueHD 音轨自动切换 `/api/stream_video`（`ffmpeg -c:v copy` 视频比特级零压缩 + 320K 实时音轨解码），支持精准拖动跳转。
  - **自动加载字幕**：同时支持外挂 `.srt / .vtt / .ass / .ssa` 与 MKV/MP4 内嵌中文字幕轨提取。
  - **🗑️ 看完即删 & 清缓存**：播完自动弹出「看完即删 & 清缓存」遮罩（顶栏及片库列表亦有一键删除），先释放播放句柄再同步移除影片、关联 qBittorrent 种子、同名字幕、空子目录与临时缓存（自动保留 `trackers.txt`）。

- **✨ 双重「4K 画质修复」引擎**
  - **0 延迟 GPU 实时修复（快捷键 `E`）**：基于 WebGL2 的 **AMD FidelityFX CAS（对比度自适应锐化）** + 原生物理像素 (`devicePixelRatio`) 渲染 + **HDR10/HLG 防发灰色彩还原**，支持实时微调滑块与 **⚖️ 左右分屏对比原画**。
  - **显卡深度重建纯 4K 母带**：针对低清或高压缩源片，一键后台调用硬件编码器（`hevc_nvenc` / `h264_nvenc` / `libx264` 自动回退），通过 `Deblock + HQDN3D + Lanczos 3840×2160 + CAS` 重建高码率纯 4K MP4 母带（不覆盖原片）。

- **📸 4K 无损原画截图 & ✂️ 极速无损高光剪辑（创意三工坊联动）**
  - 按 **`S`** 或点 **「📸 4K截图」** 提取原始分辨率无损 PNG，可一键送入 **🎨 AI 画室** 作为图生视频首帧。
  - A-B 区间 0.3 秒零重编码导出高光片段 (`-c:v copy`)、320K 音轨 (MP3)，或一键截取 3~15 秒电影/动漫台词转为 24kHz 单声道 WAV 送入 **🎙️ AI 声音克隆** 参考音。

- **🧲 5 源并发站内磁力搜索引擎 & 实时进度监视**
  - 并发检索 **Knaben 聚合 / APIBay / SolidTorrents / 蜜柑计划 / Nyaa** 五大公开源，自动去重、按做种数/体积/最新排序，内置中文检索相关性过滤，拦截无关英文热榜脏数据。
  - 投递磁力时自动拉起未启动的 qBittorrent / Aria2、自动补全公共 Tracker 并秒级预取 `.torrent` 元数据；磁力页内置实时下载进度监视器。

- **💿 磁盘空间实时卫士 + 🌙 挂机下完自动动作**
  - 顶栏常驻实时下载盘剩余空间显示，低于 `30 GB` 琥珀预警、低于 `10 GB` 红色预警，点击直达影院删片释放空间。
  - 下载队列栏支持一键预约 **下完停种 / 下完睡眠 / 下完 60 秒后关机**（带 15 秒安全倒计时随时取消）。

- **🎨 本地 AI 创作画室 & 提示词搜索引擎（8GB 显存深度适配）**
  - 支持本机 ComfyUI（Z-Image Turbo 文生图 / Wan 2.2 一键文生视频与图生视频）及任意自定义本地生图接口接入，**已深度适配 8GB 显存，生图与生视频均可在 1 分钟内流畅直出**。
  - 内置 13 分类 54 套大师提示词库、中英语义检索、6 风格即时定制与 AI 大师一键 3 方案优化。
  - 内置自动显存调度与一键 `🧹 释放显存`（文生视频两阶段自动 `/free` 释放缓存）。

- **🌌 映画级 WebGL GLSL 全屏 3D 歌词舞台 & 6 音源音乐榜单**
  - 6 音源并发搜歌（QQ/酷狗/网易云/酷我/B站/YouTube）+ 6 大榜单 + 三层 LRC 歌词匹配 + 6 大随歌切换的实景 GLSL 着色器 + 真 100% 全屏无遮挡沉浸态。

- **🎬 全平台 4K 视频工坊 + 🎙️ 开源 AI 声音克隆 + 👾 赛博小怪兽 + 📖 11 章内置交互式教程**
  - YT/B站/抖音等平台优先真 4K/HDR 下载并用 `ffprobe` 实测验真真实分辨率。
  - 独立虚拟环境 `.venv-voice` 一键部署 F5-TTS CUDA 声音克隆 + 零显卡 Edge-TTS 神经配音。
  - 全站右下角常驻 **赛博小怪兽**（支持接入任意 OpenAI / Codex 兼容接口，凭据仅存本地 `config.json`）。
  - 首页升级为 **2×6 十二项全能传送门矩阵**，顶部导航内置 **📖 教程**（11 章交互式图文步骤 + 关键词搜索 + 一键跳转）。

### 🛡️ 隐私与安全边界
- 所有密钥、密码、中转地址与个人路径仅存于本地未入库的 `config.json`。
- 启停服务严格遵循 PID 隔离，绝不全局误杀其他进程；删除影片严格校验下载目录白名单。
- 本地引擎访问全面绕过系统代理 (`trust_env = False`)，qBittorrent 反代支持 403 自动重登与断连静默处理。
