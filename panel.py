# -*- coding: utf-8 -*-
"""
DOWNLOAD STACK // CONTROL —— 赛博朋克全息 3D 仪表盘（B 方案）

硬性约束（未改动）：
1) 只是前端：不内置 aria2 / yt-dlp / qBittorrent，不封装下载器。
2) 外部视频脚本（可选，bat/cmd）只调用，不改它的内部逻辑。
3) 配置 / 缓存 / 日志 / 备份全部跟着本文件所在目录，不散落到系统盘。
4) 启停只针对本面板记录的 PID；"一键全部停止"不会全局乱杀进程。
5) 所有外部调用都有 try/except + 超时；断连不闪退，指示灯变红并写日志。

本次仅改「UI 渲染层」：配色、玻璃拟态卡片、霓虹边框、按钮、指示灯脉冲、
日志终端风、导航、页面淡入淡出、背景网格与扫描线。
探测 / 业务 / 启停 / PID / 日志 / 备份 / 弹窗 / 配置读写逻辑保持原样。

说明：flet 1.1.3 没有 ft.StyleSheet 与 CSS style 属性，
所以"CSS 动画"用 Flet 自带的 animate_* + on_hover + 定时器做等效模拟
（不是真实 GPU 3D，也不引入任何第三方库）。
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path

import flet as ft
import requests

# ================= 平台差异层（Win / Linux / macOS） =================
IS_WIN = (os.name == "nt")
IS_MAC = (sys.platform == "darwin")
IS_LINUX = (not IS_WIN) and (not IS_MAC)
SCRIPT_EXT = ".cmd" if IS_WIN else ".sh"


def _spawn_flags(detached=True):
    """Windows 用 CREATE_NO_WINDOW / 新进程组；POSIX 用 start_new_session。"""
    if IS_WIN:
        return 0x08000000 if detached else 0
    return 0


def _popen_kwargs(detached=True):
    kw = {}
    if IS_WIN:
        kw["creationflags"] = _spawn_flags(detached)
    else:
        kw["start_new_session"] = True
    return kw



def kill_tree(pid):
    """结束进程树。Windows: taskkill /T；POSIX: 先 TERM 再 KILL 整个进程组。"""
    try:
        pid = int(pid)
    except Exception:
        return False
    try:
        if IS_WIN:
            kill_tree(pid)
        else:
            import signal
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            except Exception:
                os.kill(pid, signal.SIGTERM)
            time.sleep(0.6)
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except Exception:
                pass
        return True
    except Exception:
        return False


def script_cmd(script) -> list:
    """把脚本路径转成可执行的命令参数（Windows: cmd /c；POSIX: /bin/sh）。"""
    s = str(script)
    if IS_WIN:
        return ["cmd", "/c", s]
    return ["/bin/sh", s]


def shell_run(script, cwd=None):
    """执行外部脚本：Windows 走 cmd，POSIX 走 bash/sh。"""
    s = str(script)
    if IS_WIN:
        args = ["cmd", "/c", s]
    else:
        shell = "/bin/bash" if s.lower().endswith(".sh") else "/bin/sh"
        args = [shell, s]
    return subprocess.Popen(args, cwd=cwd or str(ROOT), **_popen_kwargs())


def open_path(path):
    p = str(path)
    try:
        if IS_WIN:
            os.startfile(p)
        elif IS_MAC:
            subprocess.Popen(["open", p])
        else:
            subprocess.Popen(["xdg-open", p])
    except Exception:
        pass

try:
    import hud_assets as HA
except Exception:  # 图片缺失也不影响功能
    HA = None

# ------------------------------------------------------------------ 路径（原样）
APP_DIR = Path(__file__).resolve().parent
HOME = Path(os.environ.get("USERPROFILE") or Path.home())


def _detect_root() -> Path:
    """定位安装根目录（aria2 / qBittorrent / 脚本所在）。

    优先级：环境变量 → 本目录/上级目录里能认出 aria2 或 qBittorrent → 本目录。
    这样换盘符、换路径、绿色解压都能跑，不依赖任何写死的盘符。
    """
    env = (os.environ.get("DOWNLOADSTACK_ROOT") or "").strip()
    if env:
        return Path(env)
    cands = [APP_DIR, APP_DIR.parent, APP_DIR.parent.parent]
    for drive in ("C:", "D:", "E:", "F:"):
        cands.append(Path(drive + "/Tools/DownloadStack"))
    for cand in cands:
        try:
            if (cand / "aria2" / "aria2c.exe").is_file():
                return cand
            if (cand / "aria2").is_dir() or (cand / "qBittorrent").is_dir():
                return cand
        except OSError:
            pass
    return APP_DIR


ROOT = _detect_root()
PANEL_DIR = APP_DIR                      # 配置/日志/缓存跟着程序走
def _first_existing(*cands: Path) -> Path:
    """返回第一个真实存在的候选路径；都不存在就返回第一个（便于报错提示）。"""
    for c in cands:
        try:
            if Path(c).is_file():
                return Path(c)
        except Exception:
            pass
    return Path(cands[0])


def _pick_downloads(root: Path) -> Path:
    env = (os.environ.get("DOWNLOADSTACK_DOWNLOADS") or "").strip()
    if env:
        return Path(env)
    try:
        same_drive = Path(root.drive + "\\Downloads")
        if same_drive.is_dir():
            return same_drive
    except Exception:
        pass
    return HOME / "Downloads"


DL_HOME = _pick_downloads(ROOT)
CONFIG = PANEL_DIR / "config.json"
STATE = PANEL_DIR / "state"
LOGS = PANEL_DIR / "logs"
CACHE = PANEL_DIR / "cache"
BACKUPS = PANEL_DIR / "backups"
for d in (PANEL_DIR, STATE, LOGS, CACHE, BACKUPS):
    d.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------ 赛博配色
BG = "#05070E"          # 基底
BG2 = "#070B16"
CARD = "#0A1020"
GLASS = "#0B1526"
LINE = "#00ccff55"
CYAN = "#00ccff"        # 赛博蓝
MINT = "#00E5A0"        # 青绿
WARN = "#FFB020"        # 琥珀
ERR = "#FF4D4F"         # 红
OFF = "#4A5666"         # 熄灭
TXT = "#D8F5FF"
SUB = "#6C8BA3"
DIM = "#233246"


# 每个按键的功能说明（UI 展示用，不影响业务）
BTN_DESC = {
    "启动 Aria2 + AriaNg": "启动 aria2 下载引擎并自动打开 AriaNg 面板；已在运行则只开面板",
    "停止": "停止本套 aria2 + AriaNg 服务（只停本面板/端口匹配的进程）",
    "重启": "先停再起 aria2 服务，用于改完 aria2.conf 后生效",
    "打开 aria2.conf": "用记事本打开 aria2 配置文件",
    "打开日志目录": "打开 aria2 日志所在文件夹",
    "打开 AriaNg 网页": "在浏览器打开 AriaNg 管理面板",
    "RPC 连通性测试": "调用 aria2.getVersion 验证 RPC 是否可用",
    "查看端口占用": "检查 aria2 / qB / AriaNg 三个端口是否被占用",
    "启动 qBittorrent": "启动 qBittorrent（独立配置目录），已在运行则跳过",
    "打开 WebUI": "打开 qBittorrent WebUI 网页（127.0.0.1:8080）",
    "打开配置文件夹": "打开 qBittorrent 的配置目录",
    "打开 BT 下载目录": "打开种子下载保存目录",
    "启动 YT 下载壳": "启动你在设置里指定的外部下载脚本（bat/cmd），只调用不改它",
    "关闭 YT 壳进程": "结束本面板启动的 YT 壳进程树",
    "打开视频输出目录": "打开视频输出目录（设置里配置）",
    "一键备份整套配置": "把 aria2.conf / qBittorrent.ini / config.json / ytshell-paths.ini 备份到 backups",
    "一键自检": "检查端口、文件、D 盘写权限、Aria2 RPC 与 qB WebUI 连通性",
    "打开总下载目录": "打开设置里的总下载目录",
    "清理 Aria2 日志": "删除 aria2 日志文件（会弹确认框）",
    "清理临时缓存": "删除面板 cache 目录内容（会弹确认框）",
    "■ 一键全部停止": "按 Aria2 → qBittorrent → YT 壳 顺序停止，只停本面板记录的进程",
    "清空": "清空日志列表（不删已写入的日志文件）",
    "导出": "把当前日志导出为 logs\\export-时间戳.log",
    "测试 Aria2": "用当前 RPC 配置测试 aria2 连通性",
    "测试 WebUI": "用当前 WebUI 账号密码测试 qBittorrent 连通性",
    "保存设置": "保存设置页的所有字段到 config.json 并立即生效",
    "恢复默认": "把配置恢复为出厂默认（重启面板后界面数值同步）",
    "切换深色/浅色": "在深色赛博主题与浅色主题之间切换",
    "▣ 仪表盘": "显示仪表盘（服务状态与全部控制按钮）",
    "⚙ 设置": "显示设置页（连接参数、路径、启动项、主题）",
}

DAFAULT = {
    "aria2": {
        "host": "127.0.0.1", "port": 6800,
        "exe": str(ROOT / "aria2" / "aria2c.exe"),
        "conf": str(ROOT / "aria2" / "aria2.conf"),
        "secret": str(ROOT / "aria2" / "rpc-secret.txt"),
        "logdir": str(ROOT / "logs"),
    },
    "qbit": {
        "host": "127.0.0.1", "port": 8080,
        "user": "admin", "pass": "",
        "config_dir": str(ROOT / "qBittorrent" / "profile" / "qBittorrent" / "config"),
        "save_dir": str(DL_HOME / "qBittorrent"),
        "exe_dir": str(ROOT / "qBittorrent"),
    },
    "yt": {
        # 外部下载脚本：默认用安装器生成的 yt-download（Windows .cmd / POSIX .sh）
        "bat": os.environ.get("DOWNLOADSTACK_YTBAT") or str(_first_existing(
            ROOT / "ControlPanel" / ("yt-download" + SCRIPT_EXT),
            ROOT / "ControlPanel" / "yt-download.sh",
            ROOT / "ControlPanel" / "yt-download.cmd")),
        "bat2": "",
        "ini": os.environ.get("DOWNLOADSTACK_YTSHELL_INI", ""),
    },
    "ariang": {
        "port": 16800,
        "dir": str(ROOT / "ariaNg"),
        "script": str(ROOT / ("start_ariang" + SCRIPT_EXT)),
    },
    "scripts": {
        # 兼容两种命名：新安装 start_aria2.cmd / 已有安装 Start-DownloadStack.cmd
        "start": str(_first_existing(ROOT / ("start_aria2" + SCRIPT_EXT),
                                     ROOT / "Start-DownloadStack.cmd",
                                     ROOT / ("start_aria2" + ".sh"))),
        "stop": str(_first_existing(ROOT / ("stop_aria2" + SCRIPT_EXT),
                                    ROOT / "Stop-DownloadStack.cmd",
                                    ROOT / ("stop_aria2" + ".sh"))),
        "qbit": str(_first_existing(ROOT / ("start_qbit" + SCRIPT_EXT),
                                    ROOT / "Start-qBittorrent.cmd",
                                    ROOT / ("start_qbit" + ".sh"))),
    },
    "ui": {"theme": "dark", "autostart_panel": False, "autostart_aria2": False,
           "upscale": False},
    "paths": {"downloads": str(DL_HOME)},
}


def A(color, alpha="CC"):
    """把 #RRGGBB + 透明度 转成 Flet 需要的 #AARRGGBB。"""
    try:
        c = color.lstrip("#")
        if len(c) == 8:      # 已经是 AARRGGBB
            return "#" + c
        return "#" + alpha.upper() + c[:6].upper()
    except Exception:
        return color


# ------------------------------------------------------------------ 配置（原样）
def load_cfg():
    cfg = json.loads(json.dumps(DAFAULT))
    if CONFIG.exists():
        try:
            user = json.loads(CONFIG.read_text(encoding="utf-8"))
            qb = user.get("qbit") if isinstance(user.get("qbit"), dict) else {}
            if "username" in qb and "user" not in qb:
                qb["user"] = qb.pop("username")
            if "password" in qb and "pass" not in qb:
                qb["pass"] = qb.pop("password")
            for k, v in user.items():
                if isinstance(v, dict) and k in cfg:
                    cfg[k].update(v)
                else:
                    cfg[k] = v
        except Exception:
            pass
    # 清洗示例配置里的占位符（<ROOT> / <DOWNLOADS>），避免读到假路径
    def _fix(v):
        if isinstance(v, str):
            return (v.replace("<ROOT>", str(ROOT))
                     .replace("<DOWNLOADS>", str(DL_HOME))
                     .replace("<安装根>", str(ROOT))
                     .replace("<下载根>", str(DL_HOME)))
        if isinstance(v, dict):
            return {k: _fix(x) for k, x in v.items()}
        return v
    cfg = _fix(cfg)
    save_cfg(cfg)
    return cfg


def save_cfg(cfg):
    try:
        CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def load_pids():
    try:
        return json.loads((STATE / "pids.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_pids(p):
    try:
        (STATE / "pids.json").write_text(json.dumps(p, indent=2), encoding="utf-8")
    except Exception:
        pass


def port_open(host, port):
    try:
        with socket.create_connection((host, int(port)), timeout=0.6):
            return True
    except Exception:
        return False


def pid_alive(pid):
    if not pid:
        return False
    try:
        out = subprocess.run(["tasklist", "/FI", "PID eq %d" % int(pid), "/NH"],
                             capture_output=True, text=True, timeout=5,
                             creationflags=0x08000000)
        return str(pid) in (out.stdout or "")
    except Exception:
        return False


def ini_get(path, key):
    try:
        for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return None


def read_secret(path):
    try:
        return Path(path).read_text(encoding="ascii", errors="replace").strip()
    except Exception:
        return ""


def hbytes(n):
    try:
        n = float(n)
    except Exception:
        return "-"
    for u in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(n) < 1024:
            return "%.1f %s" % (n, u)
        n /= 1024.0
    return "%.1f PiB" % n


def hspeed(n):
    return hbytes(n) + "/s"



# ------------------------------------------------------------------ 探测（原样）
class Probe:
    def __init__(self, cfg):
        self.cfg = cfg
        self.a = {"on": False, "ver": "", "dn": 0, "up": 0, "task": 0, "conn": 0, "err": ""}
        self.q = {"on": False, "dn": 0, "up": 0, "adl": 0, "aul": 0, "tor": 0, "seed": 0, "err": ""}
        self.y = {"on": False, "pid": None}

    def a_call(self, method, params=None, timeout=2.0):
        c = self.cfg["aria2"]
        sec = read_secret(c["secret"])
        body = {"jsonrpc": "2.0", "id": "panel", "method": method,
                "params": (["token:" + sec] if sec else []) + (params or [])}
        url = "http://%s:%d/jsonrpc" % (c["host"], int(c["port"]))
        r = requests.post(url, json=body, timeout=timeout,
                          proxies={"http": None, "https": None})
        r.raise_for_status()
        j = r.json()
        if "error" in j:
            raise RuntimeError(str(j["error"])[:100])
        return j.get("result")

    def poll_a(self):
        try:
            gs = self.a_call("aria2.getGlobalStat") or {}
            ver = ""
            try:
                ver = (self.a_call("aria2.getVersion") or {}).get("version", "")
            except Exception:
                pass
            conn = 0
            try:
                for t in (self.a_call("aria2.tellActive") or []):
                    conn += int(t.get("connections", 0) or 0)
            except Exception:
                pass
            self.a = {"on": True, "ver": ver,
                      "dn": int(gs.get("downloadSpeed", 0) or 0),
                      "up": int(gs.get("uploadSpeed", 0) or 0),
                      "task": int(gs.get("numActive", 0) or 0),
                      "conn": conn, "err": ""}
        except Exception as e:
            # 程序文件不存在 = 还没装，算离线；装了却连不上才算异常
            installed = False
            try:
                installed = Path(str((self.cfg.get("aria2") or {}).get("exe") or "")).is_file()
            except Exception:
                installed = False
            self.a = {"on": False, "ver": "", "dn": 0, "up": 0, "task": 0, "conn": 0,
                      "err": type(e).__name__ if installed else ""}

    def q_login(self, timeout=2.0):
        c = self.cfg["qbit"]
        s = requests.Session()
        s.proxies = {"http": None, "https": None}
        base = "http://%s:%d" % (c["host"], int(c["port"]))
        hdr = {"Referer": base + "/", "Origin": base}
        r = s.post(base + "/api/v2/auth/login", timeout=timeout, headers=hdr,
                   data={"username": c["user"], "password": c["pass"]})
        # qB 5.x 登录成功返回 204（空 body）或 200 + "Ok."
        if r.status_code == 204:
            return s, base
        if r.status_code != 200 or "Ok" not in (r.text or ""):
            raise RuntimeError("login_%s" % r.status_code)
        return s, base

    def poll_q(self):
        # 登录失败后退避，避免高频重试触发 qB 的失败封禁
        import time as _t
        until = getattr(self, "_q_hold_until", 0)
        if _t.time() < until:
            return
        try:
            s, base = self.q_login()
            d = s.get(base + "/api/v2/sync/maindata?rid=0", timeout=2.0,
                      headers={"Referer": base + "/"}).json()
            st = d.get("server_state", {}) or {}
            tq = d.get("torrents", {}) or {}
            self.q = {"on": True,
                      "dn": int(st.get("dl_info_speed", 0) or 0),
                      "up": int(st.get("up_info_speed", 0) or 0),
                      "adl": int(st.get("alltime_dl", 0) or 0),
                      "aul": int(st.get("alltime_ul", 0) or 0),
                      "tor": len(tq),
                      "seed": sum(1 for x in tq.values() if x.get("seeding")),
                      "err": ""}
        except Exception as e:
            self._q_hold_until = _t.time() + 30
            # 没装 / 没启动 → 算离线；装了但连不上 → 才算异常
            installed = False
            try:
                d = Path((self.cfg.get("qbit") or {}).get("exe_dir") or "")
                installed = any((d / n).exists() for n in ("qbittorrent.exe", "qBittorrent.exe"))
            except Exception:
                installed = False
            self.q = {"on": False, "dn": 0, "up": 0, "adl": 0, "aul": 0,
                      "tor": 0, "seed": 0,
                      "installed": installed,
                      "err": type(e).__name__ if installed else ""}

    def poll_y(self):
        pid = load_pids().get("yt")
        self.y = {"on": bool(pid and pid_alive(pid)), "pid": pid}


# ------------------------------------------------------------------ 面板
class Panel:
    def __init__(self, page: ft.Page):
        self.p = page
        self.cfg = load_cfg()
        self.pr = Probe(self.cfg)
        self.t0 = time.time()
        self.logs = []
        self.pids = load_pids()
        self.phase = 0                      # 呼吸/扫描动画相位
        self._wide = True                   # 窗口宽度降级标记

        self.p.title = "DOWNLOAD STACK // CONTROL"
        self.p.bgcolor = BG
        self.p.padding = 0
        self.p.theme_mode = ft.ThemeMode.DARK
        try:
            self.p.window.width = 1440
            self.p.window.height = 940
            self.p.window.min_width = 1000
            self.p.window.min_height = 700
            self.p.on_resize = self._on_resize
        except Exception:
            pass

        self._ui()
        self._ui_ready_at = time.time() + 3.0   # 屏蔽挂载瞬间的伪 on_change
        self.log("面板启动，配置 %s" % CONFIG)
        self.refresh()
        self.p.run_task(self._tick)
        self.p.run_task(self._fx)
        self.p.run_task(self._scroll_top)

    # ---------------------------------------------------------- 日志（保持逻辑，仅上色）
    def log(self, msg, level="INFO"):
        line = "%s [%-5s] %s" % (datetime.now().strftime("%H:%M:%S"), level, msg)
        self.logs.append(line)
        if len(self.logs) > 500:
            self.logs = self.logs[-500:]
        try:
            with open(LOGS / ("panel-%s.log" % datetime.now().strftime("%Y%m%d")),
                      "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass
        try:
            self.lv.controls = [self._log_line(x) for x in self.logs]
            self.p.update()
        except Exception:
            pass

    def _log_line(self, raw):
        """按级别上色：INFO 绿 / WARN 黄 / ERROR 红 / 其它青。"""
        color = MINT
        if "[WARN " in raw or "[WARN]" in raw:
            color = WARN
        elif "[ERROR]" in raw:
            color = ERR
        elif "[INFO " in raw:
            color = MINT
        return ft.Text(raw, size=12, font_family="Consolas", color=color,
                       no_wrap=False, selectable=True)

    # ---------------------------------------------------------- 样式构件（纯 UI）
    def glow(self, color, radius=18, blur=14):
        """一圈霓虹辉光（BoxShadow 叠加）。"""
        try:
            return [ft.BoxShadow(blur_radius=blur, color=A(color, "44"), offset=ft.Offset(0, 0)),
                    ft.BoxShadow(blur_radius=blur * 2, color=A(color, "22"), offset=ft.Offset(0, 0))]
        except Exception:
            return []

    def hover_lift(self, e, up=True, scale=1.012):
        """鼠标悬停：轻微放大 + 上浮（模拟 3D 抬升）。"""
        try:
            c = e.control
            c.scale = scale if up else 1.0
            c.offset = ft.Offset(0, -0.006 if up else 0)
            c.update()
        except Exception:
            pass

    def card(self, title, children, tone=CYAN, badge=None, zone=None):
        """玻璃拟态全息卡片 + 霓虹边框 + hover 抬升。"""
        head_badge = (ft.Image(src=(badge or (HA.HEXBADGE if HA else "")), width=18, height=18,
                               opacity=0.95) if HA else ft.Container(width=0))
        box = ft.Container(
            bgcolor="#E60A1220",
            border=ft.Border.all(1, A(tone, "55")),
            border_radius=10,
            padding=12,
            shadow=self.glow(tone, blur=10),
            animate_scale=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
            animate_offset=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
            content=ft.Column([
                ft.Row([
                    head_badge,
                    (ft.Container(content=ft.Text(zone, size=9, color=A(tone, "DD"),
                                                  font_family="Microsoft YaHei UI"),
                                  padding=ft.Padding.symmetric(horizontal=6, vertical=1),
                                  border=ft.Border.all(1, A(tone, "66")),
                                  border_radius=3, bgcolor="#66060B16")
                     if zone else ft.Container(width=0)),
                    ft.Container(width=6, height=6, bgcolor=tone, border_radius=3,
                                 shadow=self.glow(tone, blur=6)),
                    ft.Text(title, size=14, weight=ft.FontWeight.BOLD,
                            font_family="Consolas", color=tone),
                    ft.Container(expand=True),
                    ft.Text("◤ MODULE ◢", size=8, color=A(tone, "7A"),
                            font_family="Consolas"),
                ], spacing=8),
                ft.Container(height=1, bgcolor=A(tone, "33")),
                *children,
            ], spacing=8),
        )
        # 3D 立体：默认带一层极轻的透视旋转，hover 时抬起 + 轻微倾斜
        box.rotate = ft.Rotate(angle=0.0)
        box.animate_rotation = ft.Animation(180, ft.AnimationCurve.EASE_OUT)

        def on_hover(e):
            try:
                up = bool(e.data == "true" or e.data is True)
            except Exception:
                up = True
            if up:
                box.scale = 1.018
                box.offset = ft.Offset(0, -0.006)
                box.rotate = ft.Rotate(angle=0.004)
                box.shadow = self.glow(tone, blur=22)
            else:
                box.scale = 1.0
                box.offset = ft.Offset(0, 0)
                box.rotate = ft.Rotate(angle=0.0)
                box.shadow = self.glow(tone, blur=10)
            try:
                box.update()
            except Exception:
                pass

        box.on_hover = on_hover
        return box

    def btn(self, label, fn, color=CYAN):
        """赛博立体按键：霓虹边框 + hover 上浮发光 + 点击下沉反馈。"""
        accent = color
        txt = ft.Text(label, size=13, color=TXT, font_family="Microsoft YaHei UI")
        box = ft.Container(
            content=txt,
            padding=ft.Padding.symmetric(horizontal=12, vertical=7),
            border=ft.Border.all(1, accent + "66"),
            border_radius=4,
            bgcolor="#AA0C1830",
            tooltip=BTN_DESC.get(label, label),
            shadow=self.glow(accent, blur=6),
            animate_scale=ft.Animation(120, ft.AnimationCurve.EASE_OUT),
            animate_offset=ft.Animation(120, ft.AnimationCurve.EASE_OUT),
            on_click=fn,
        )

        def on_hover(e):
            try:
                up = bool(e.data == "true" or e.data is True)
            except Exception:
                up = True
            if up:
                box.scale = 1.05
                box.offset = ft.Offset(0, -0.01)
                box.shadow = self.glow(accent, blur=14)
                txt.color = accent
            else:
                box.scale = 1.0
                box.offset = ft.Offset(0, 0)
                box.shadow = self.glow(accent, blur=6)
                txt.color = TXT
            try:
                box.update()
            except Exception:
                pass

        def on_down(e):
            try:
                box.scale = 0.97
                box.offset = ft.Offset(0, 0.004)
                box.update()
            except Exception:
                pass

        box.on_hover = on_hover
        try:
            box.on_tap_down = on_down
        except Exception:
            pass
        return box

    def kv(self, label, tone=CYAN):
        """HUD 数字：等宽 + 发光 + 自动缩放。"""
        v = ft.Text("-", size=17, font_family="Consolas", color=tone, weight=ft.FontWeight.BOLD)
        unit = ft.Text("", size=10, font_family="Consolas", color=A(tone, "88"))
        col = ft.Column([
            ft.Text(label, size=10, color=SUB, font_family="Consolas"),
            ft.Row([v, unit], spacing=4, tight=True),
        ], spacing=0, width=132)
        return v, col

    def led(self, name, tone=MINT):
        """指示灯：容器圆点 + 文字；返回 (dot, text) 供 render 更新。"""
        dot = ft.Container(width=10, height=10, border_radius=5, bgcolor=OFF,
                           shadow=self.glow(OFF, blur=6),
                           animate_opacity=ft.Animation(600, ft.AnimationCurve.EASE_IN_OUT),
                           animate_scale=ft.Animation(600, ft.AnimationCurve.EASE_IN_OUT))
        txt = ft.Text(name, size=11, weight=ft.FontWeight.BOLD, color=OFF,
                      font_family="Consolas", data=name)
        return dot, txt

    # ---------------------------------------------------------- 窗口宽度降级
    def _on_resize(self, e=None):
        try:
            w = self.p.width or 1440
        except Exception:
            w = 1440
        wide = w >= 1180
        if wide == self._wide:
            return
        self._wide = wide
        # 窄窗口：关闭位移/缩放动效，防止按钮错位或裁切
        try:
            for box in self._cards:
                box.animate_scale = None if not wide else ft.Animation(180, ft.AnimationCurve.EASE_OUT)
                box.scale = 1.0
                box.offset = ft.Offset(0, 0)
            self.p.update()
        except Exception:
            pass

    # ---------------------------------------------------------- 界面
    def _ui(self):
        p = self.p
        self._cards = []
        cfg = self.cfg

        # ================= HUD =================
        self.t_clock = ft.Text("-", size=13, font_family="Consolas", color=MINT)
        self.t_up = ft.Text("00:00:00", size=13, font_family="Consolas", color=CYAN)
        self.led_a_dot, self.led_a = self.led("ARIA2")
        self.led_q_dot, self.led_q = self.led("QBITTORRENT")
        self.led_y_dot, self.led_y = self.led("YT-SHELL")

        self.ring_a = ft.ProgressRing(value=0, width=40, height=40, stroke_width=3,
                                      color=MINT, bgcolor="#10202E")
        self.ring_q = ft.ProgressRing(value=0, width=40, height=40, stroke_width=3,
                                      color=CYAN, bgcolor="#10202E")
        self.spark_a = [ft.Container(width=2, height=2, bgcolor=MINT, border_radius=1, opacity=0.5)
                        for _ in range(40)]
        self.spark_q = [ft.Container(width=2, height=2, bgcolor=CYAN, border_radius=1, opacity=0.5)
                        for _ in range(40)]
        spark_a_box = ft.Container(height=20, content=ft.Row(self.spark_a, spacing=1,
                                  vertical_alignment=ft.CrossAxisAlignment.END))
        spark_q_box = ft.Container(height=20, content=ft.Row(self.spark_q, spacing=1,
                                  vertical_alignment=ft.CrossAxisAlignment.END))

        self.v_adn, c1 = self.kv("ARIA2 ↓")
        self.v_aup, c2 = self.kv("ARIA2 ↑")
        self.v_atk, c3 = self.kv("TASKS")
        self.v_acn, c4 = self.kv("CONN")
        self.v_qdn, c5 = self.kv("QB ↓")
        self.v_qup, c6 = self.kv("QB ↑")
        self.v_qto, c7 = self.kv("TORRENTS")
        self.v_qse, c8 = self.kv("SEEDING")

        header = ft.Container(
            bgcolor="#DD08101F",
            border=ft.Border.all(1, A(MINT, "55")),
            border_radius=10,
            padding=ft.Padding.symmetric(horizontal=16, vertical=10),
            shadow=self.glow(MINT, blur=10),
            content=ft.Column([
                ft.Row([
                    ft.Image(src=(HA.EMBLEM2 if HA else ""), width=46, height=46,
                             opacity=0.95) if HA else ft.Container(width=0),
                    ft.Column([
                        ft.Row([ft.Text("DOWNLOAD STACK", size=22, weight=ft.FontWeight.BOLD,
                                        font_family="Consolas", color=MINT),
                                ft.Text("// CONTROL", size=22, weight=ft.FontWeight.BOLD,
                                        font_family="Consolas", color=CYAN),
                                ft.Text("HOLO-HUD v2.2", size=9, color=A(CYAN, "99"),
                                        font_family="Consolas"),
                                ft.Container(content=ft.Text("状态总览区", size=10, color=MINT,
                                                             font_family="Microsoft YaHei UI"),
                                             padding=ft.Padding.symmetric(horizontal=7, vertical=2),
                                             border=ft.Border.all(1, A(MINT, "66")),
                                             border_radius=3, bgcolor="#66060B16")], spacing=6),
                        ft.Row([self.led_a_dot, self.led_a, self.led_q_dot, self.led_q,
                                self.led_y_dot, self.led_y], spacing=12),
                    ], spacing=2),
                    ft.Container(expand=True),
                    ft.Row([ft.Container(content=self.ring_a, width=40, height=40), spark_a_box,
                            ft.Container(width=14),
                            ft.Container(content=self.ring_q, width=40, height=40), spark_q_box],
                           spacing=6),
                    ft.Column([
                        ft.Row([ft.Text("SYS", size=10, color=SUB, font_family="Consolas"),
                                self.t_clock], spacing=6),
                        ft.Row([ft.Text("UP", size=10, color=SUB, font_family="Consolas"),
                                self.t_up], spacing=6),
                    ], spacing=2),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=14),
                ft.Container(height=1, gradient=ft.LinearGradient(
                    begin=ft.Alignment(-1, 0), end=ft.Alignment(1, 0),
                    colors=[A(MINT, "00"), A(MINT, "77"), A(CYAN, "44"), A(MINT, "00")])),
                ft.Row([c1, c2, c3, c4, c5, c6, c7, c8], spacing=10, wrap=True, run_spacing=4),
            ], spacing=6),
        )

        self.yt_out = ft.Text(self.yt_output(), size=11, font_family="Consolas", color=CYAN)

        # ---------- 卡片内的信息行（只读，纯展示） ----------
        def info(label, value, tone=SUB):
            return ft.Row([
                ft.Text(label, size=11, color=SUB, font_family="Microsoft YaHei UI", width=70),
                ft.Text(value, size=11, color=tone, font_family="Consolas"),
            ], spacing=6, tight=True)

        def info_box(rows, tone):
            return ft.Container(
                bgcolor="#80040A14", border=ft.Border.all(1, A(tone, "33")),
                border_radius=6, padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                expand=True,
                content=ft.Column(rows, spacing=4))

        # ================= 四张卡 =================
        card_a = self.card("ARIA2", [
            ft.Row([self.btn("启动 Aria2 + AriaNg", self.on_start_a, MINT),
                    self.btn("停止", self.on_stop_a, ERR),
                    self.btn("重启", self.on_restart_a, CYAN)], wrap=True, spacing=8),
            ft.Row([self.btn("打开 aria2.conf", lambda e: self.open(cfg["aria2"]["conf"]), CYAN),
                    self.btn("打开日志目录", lambda e: self.open(cfg["aria2"]["logdir"]), CYAN),
                    self.btn("打开 AriaNg 网页", self.on_ariang, CYAN)], wrap=True, spacing=8),
            ft.Row([self.btn("RPC 连通性测试", self.on_test_a, CYAN),
                    self.btn("查看端口占用", self.on_ports, CYAN)], wrap=True, spacing=8),
            info_box([
                info("RPC", "http://%s:%d  (token 已启用)" % (cfg["aria2"]["host"], cfg["aria2"]["port"]), MINT),
                info("配置", cfg["aria2"]["conf"]),
                info("日志", cfg["aria2"]["logdir"]),
                info("成品", cfg["paths"]["downloads"] + r"\aria2"),
                info("面板", "http://127.0.0.1:16800  (AriaNg)", CYAN),
            ], MINT),
        ], MINT, badge=(HA.HEXBADGE if HA else None), zone="下载区 · aria2")

        card_q = self.card("QBITTORRENT", [
            ft.Row([self.btn("启动 qBittorrent", self.on_start_q, MINT),
                    self.btn("停止", self.on_stop_q, ERR),
                    self.btn("打开 WebUI", self.on_webui, CYAN)], wrap=True, spacing=8),
            ft.Row([self.btn("打开配置文件夹", lambda e: self.open(cfg["qbit"]["config_dir"]), CYAN),
                    self.btn("打开 BT 下载目录", lambda e: self.open(cfg["qbit"]["save_dir"]), CYAN)],
                   wrap=True, spacing=8),
            info_box([
                info("WebUI", "http://%s:%d  （仅本机）" % (cfg["qbit"]["host"], cfg["qbit"]["port"]), CYAN),
                info("账号", cfg["qbit"]["user"] + "  / 密码见 设置页", CYAN),
                info("保存", cfg["qbit"]["save_dir"]),
                info("配置", cfg["qbit"]["config_dir"]),
                info("PT", "WebUI 里“添加 Torrent 链接”，面板不代下", WARN),
            ], CYAN),
        ], CYAN, badge=(HA.HEXBADGE if HA else None), zone="下载区 · BT 种子")

        self.up_txt = ft.Text(self._up_label(), size=11, font_family="Microsoft YaHei UI",
                              color=(WARN if self.cfg["ui"].get("upscale") else SUB))
        self.up_switch = ft.Switch(value=bool(self.cfg["ui"].get("upscale")),
                                   on_change=self.on_upscale_toggle,
                                   active_color=WARN, label="超分 2x")
        updown_row = ft.Container(
            bgcolor="#80040A14", border=ft.Border.all(1, A(WARN, "55")), border_radius=6,
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            content=ft.Row([self.up_switch, self.up_txt], spacing=10,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER))

        card_y = self.card("YT-DLP 视频壳", [
            updown_row,
            ft.Row([self.btn("启动 YT 下载壳", self.on_start_y, MINT),
                    self.btn("关闭 YT 壳进程", self.on_stop_y, ERR)], wrap=True, spacing=8),
            ft.Row([self.btn("打开视频输出目录", lambda e: self.open(self.yt_output()), CYAN)],
                   wrap=True, spacing=8),
            info_box([
                info("输出", self.yt_output(), WARN),
                info("地址", cfg["yt"]["bat"] or "（未配置，设置页可填）", WARN),
                info("路径表", cfg["yt"]["ini"] or "（未配置，可选）", WARN),
                info("超分", "用上方开关：开=下载后 2x 超分 / 关=只下载", WARN),
                info("原则", "只调用外部 bat，不改 yt-dlp / venv / 脚本", SUB),
            ], WARN),
        ], WARN, badge=(HA.HEXBADGE_A if HA else None), zone="下载区 · 视频")

        card_t = self.card("高级工具", [
            ft.Row([self.btn("一键备份整套配置", self.on_backup, CYAN),
                    self.btn("一键自检", self.on_selfcheck, CYAN)], wrap=True, spacing=8),
            ft.Row([self.btn("打开总下载目录", lambda e: self.open(cfg["paths"]["downloads"]), CYAN),
                    self.btn("清理 Aria2 日志", self.on_clean_logs, WARN)], wrap=True, spacing=8),
            ft.Row([self.btn("清理临时缓存", self.on_clean_cache, WARN),
                    self.btn("■ 一键全部停止", self.on_stop_all, ERR)], wrap=True, spacing=8),
            info_box([
                info("备份", str(BACKUPS), ERR),
                info("日志", str(LOGS), ERR),
                info("停止序", "Aria2 → qBittorrent → YT 壳（只停本面板记录）", ERR),
                info("安全", "不全局 taskkill、不改订阅/TUN/防火墙", ERR),
                info("清理", "日志与缓存操作都会弹确认框", ERR),
            ], ERR),
        ], ERR, badge=(HA.HEXBADGE_R if HA else None), zone="工具与维护区")

        for c in (card_a, card_q, card_y, card_t):
            c.expand = True
        self._cards = [card_a, card_q, card_y, card_t]

        # ================= 右侧：状态提示 + 详细教程 =================
        magnet_banner = ft.Container(
            bgcolor="#CC1A0F14",
            border=ft.Border.all(1, A(ERR, "77")),
            border_radius=8,
            padding=12,
            shadow=self.glow(ERR, blur=8),
            content=ft.Column([
                ft.Row([ft.Container(width=9, height=9, border_radius=5, bgcolor=ERR,
                                     shadow=self.glow(ERR, blur=8)),
                        ft.Text("磁力 / DHT 不可用", size=14, weight=ft.FontWeight.BOLD,
                                color=ERR, font_family="Microsoft YaHei UI"),
                        ft.Container(expand=True),
                        ft.Container(content=ft.Text("状态提示区", size=10, color=A(ERR, "DD"),
                                                     font_family="Microsoft YaHei UI"),
                                     padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                     border=ft.Border.all(1, A(ERR, "55")), border_radius=3)],
                       spacing=8),
                ft.Text("现状（已实测）", size=11, color=WARN, weight=ft.FontWeight.BOLD),
                ft.Text("· tracker 接受汇报，但磁力自行取元数据未成功", size=10, color=TXT),
                ft.Text("· DHT 节点数长期为 0，UDP 对真实 IP 是通的", size=10, color=TXT),
                ft.Text("· 换节点/换出口都试过，不是单点问题", size=10, color=TXT),
                ft.Text("现在怎么下 BT", size=11, color=MINT, weight=ft.FontWeight.BOLD),
                ft.Text("· 有 .torrent：直接拖进 qBittorrent，正常下", size=10, color=TXT),
                ft.Text("· 只有磁力：先找同资源种子文件，或等修好", size=10, color=TXT),
                ft.Text("后续修复（要你点头再动）", size=11, color=CYAN, weight=ft.FontWeight.BOLD),
                ft.Text("· 换可用 DHT 引导节点 / 清理假 IP 路由", size=10, color=TXT),
                ft.Text("· 给 DHT 单独走直连出口，绕开代理假 IP 段", size=10, color=TXT),
            ], spacing=3),
        )

        def tt(txt, tone=TXT, size=11, bold=False, indent=0):
            return ft.Text(("　" * indent) + txt, size=size, color=tone,
                           font_family="Microsoft YaHei UI",
                           weight=ft.FontWeight.BOLD if bold else ft.FontWeight.NORMAL)

        def th(txt, tone=MINT):
            return ft.Row([
                ft.Container(width=3, height=14, bgcolor=tone, border_radius=2,
                             shadow=self.glow(tone, blur=6)),
                ft.Text(txt, size=12, color=tone, weight=ft.FontWeight.BOLD,
                        font_family="Microsoft YaHei UI"),
            ], spacing=6)

        tutorial = ft.Container(
            bgcolor="#CC0A1222",
            border=ft.Border.all(1, A(CYAN, "55")),
            border_radius=8,
            padding=12,
            expand=True,
            content=ft.Column([
                ft.Row([ft.Image(src=(HA.HEXBADGE if HA else ""), width=18, height=18) if HA else ft.Container(width=0),
                        ft.Text("使用教程（详细版）", size=14, weight=ft.FontWeight.BOLD,
                                color=CYAN, font_family="Microsoft YaHei UI"),
                        ft.Container(expand=True),
                        ft.Container(content=ft.Text("可下拉 ↓", size=10, color=A(CYAN, "DD"),
                                                     font_family="Microsoft YaHei UI"),
                                     padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                     border=ft.Border.all(1, A(CYAN, "55")), border_radius=3)],
                       spacing=8),

                th("0 · 开面板先看三盏灯", MINT),
                tt("绿 = 在线；灰 = 没开（点“启动”）；红 = 端口通但认证/接口失败"),
                tt("红灯先点对应“测试”按钮，日志区会写具体原因"),

                th("1 · 普通文件 / 直链（aria2）", MINT),
                tt("① 点“启动 Aria2 + AriaNg”，灯变绿"),
                tt("② 点“打开 AriaNg 网页”，会出现 AriaNg 管理界面"),
                tt("③ 左上“新建” → 粘贴直链 → 开始下载"),
                tt("④ 成品在 D:\\Downloads\\aria2，进度/速度看顶部数字或 AriaNg"),
                tt("⑤ 支持断点续传；暂停后点继续即可；取消会删 .aria2 控制文件", SUB),

                th("2 · 平台视频（YT 下载壳）", MINT),
                tt("① 点“启动 YT 下载壳”（会弹黑窗口，属于正常）"),
                tt("② 在黑窗口里粘贴视频链接 → 回车"),
                tt("③ 按提示选清晰度/是否只要音频；播放列表会问你范围"),
                tt("④ 下完点“打开视频输出目录”看成品：D:\\Downloads\\yt-dlp"),
                tt("⑤ 关掉壳：点“关闭 YT 壳进程”，只结束本面板启动的那个", SUB),

                th("3 · 需要 2 倍超分（可选）", MINT),
                tt("① 视频下好后，找到你自己的超分脚本（bat/cmd）"),
                tt("② 双击它，按提示选文件（本面板不内置超分）"),
                tt("③ 超分吃显卡，跑的时候别同时压测；默认不超分"),

                th("4 · 种子 / PT（qBittorrent）", MINT),
                tt("① 点“启动 qBittorrent”，灯变绿"),
                tt("② 点“打开 WebUI”，浏览器进 127.0.0.1:8080"),
                tt("③ 拖 .torrent 进窗口，或“添加 Torrent 链接”"),
                tt("④ 保存目录默认 D:\\Downloads\\qBittorrent"),
                tt("⑤ PT 站务必保持做种，别乱删任务，会被标记", SUB),

                th("5 · 磁力（当前不可用）", ERR),
                tt("现状：磁力自行取元数据失败，DHT 长期 0 节点（已记录）", ERR),
                tt("替代：找到同资源的 .torrent 文件，拖进 qBittorrent 即可"),
                tt("修复方向：换引导节点 / DHT 走直连出口（等你确认）", WARN),

                th("6 · 出错了怎么查（三步）", WARN),
                tt("① 看灯：灰=没开，红=认证或接口错"),
                tt("② 看日志区：ERROR 那行写了原因，紧跟“下一步”提示"),
                tt("③ 还不够：点“导出”，把 logs\\export-*.log 发我"),
                tt("更细的现场在 .diagnose\\errors-*.log"),

                th("7 · 文件都在哪", CYAN),
                tt("aria2 成品　D:\\Downloads\\aria2", SUB),
                tt("视频成品　　D:\\Downloads\\yt-dlp", SUB),
                tt("种子成品　　D:\\Downloads\\qBittorrent", SUB),
                tt("面板配置　　D:\\Tools\\DownloadStack\\ControlPanel\\config.json", SUB),
                tt("备份　　　　D:\\Tools\\DownloadStack\\ControlPanel\\backups", SUB),
                tt("日志　　　　D:\\Tools\\DownloadStack\\ControlPanel\\logs", SUB),

                th("8 · 常见问答", WARN),
                tt("Q 速度慢？　先看是不是单线程源；aria2 可加 -x16 多连"),
                tt("Q 点了没反应？　看日志区有没有 ERROR；重复点会被自动跳过"),
                tt("Q 端口被占？　点“查看端口占用”，再看是不是旧进程没退"),
                tt("Q 改端口？　设置页改完点“保存设置”，立即按新值重连"),
                tt("Q 想关全部？　用“一键全部停止”，只停本面板记录的进程"),
                tt("Q 会乱杀进程吗？　不会，不碰你没经过面板启动的东西", SUB),
            ], spacing=3, scroll=ft.ScrollMode.AUTO),
        )
        self.tut_col = tutorial.content

        quick = ft.Container(
            bgcolor="#CC0A1222",
            border=ft.Border.all(1, A(WARN, "55")),
            border_radius=8,
            padding=12,
            content=ft.Column([
                ft.Row([ft.Text("常见问题", size=13, weight=ft.FontWeight.BOLD, color=WARN,
                                font_family="Microsoft YaHei UI"),
                        ft.Container(expand=True),
                        ft.Container(content=ft.Text("速查区", size=10, color=A(WARN, "DD"),
                                                     font_family="Microsoft YaHei UI"),
                                     padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                     border=ft.Border.all(1, A(WARN, "55")), border_radius=3)],
                       spacing=8),
                ft.Text("· 灯是灰的 → 对应服务没开，点“启动”", size=10, color=TXT),
                ft.Text("· 灯是红的 → 端口通但认证/接口失败，点测试看原因", size=10, color=TXT),
                ft.Text("· 重复点启动 → 面板会检测端口，自动跳过", size=10, color=TXT),
                ft.Text("· 想改端口 → 设置页改完点保存，立即生效", size=10, color=TXT),
            ], spacing=3),
        )

        info_col = ft.Column([magnet_banner, tutorial, quick], spacing=10, width=470,
                             expand=True)

        grid = ft.Column([
            ft.Row([card_a, card_q], spacing=12, expand=True),
            ft.Row([card_y, card_t], spacing=12, expand=True),
        ], spacing=12, expand=True)

        main = ft.Row([grid, info_col], expand=True, spacing=12,
                      vertical_alignment=ft.CrossAxisAlignment.STRETCH)

        # ================= 日志 =================
        self.lv = ft.ListView(spacing=1, auto_scroll=True, expand=True)
        self.scan = ft.Container(height=2, bgcolor=A(MINT, "88"),
                                 animate_opacity=ft.Animation(900, ft.AnimationCurve.EASE_IN_OUT))
        log_card = ft.Container(
            bgcolor="#CC04070E",
            border=ft.Border.all(1, A(MINT, "55")),
            border_radius=10,
            padding=10,
            height=170,
            shadow=self.glow(MINT, blur=8),
            content=ft.Column([
                ft.Row([ft.Text("◤ 实时日志", size=12, weight=ft.FontWeight.BOLD,
                                color=MINT, font_family="Microsoft YaHei UI"),
                        ft.Container(content=ft.Text("日志区", size=10, color=A(MINT, "DD"),
                                                     font_family="Microsoft YaHei UI"),
                                     padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                     border=ft.Border.all(1, A(MINT, "55")), border_radius=3),
                        ft.Container(expand=True),
                        self.btn("清空", self.on_clear_log, CYAN),
                        self.btn("导出", self.on_export_log, CYAN)], spacing=8),
                ft.Container(content=self.lv, expand=True, padding=ft.Padding.only(left=2)),
                self.scan,
            ], spacing=6, expand=True),
        )

        # ================= 设置页 =================
        self.f = {}

        def field(label, key, value, w=470, pw=False):
            tf = ft.TextField(label=label, value=str(value), width=w, dense=True,
                              text_size=12, password=pw, can_reveal_password=pw,
                              bgcolor="#DD060B16", color=TXT,
                              label_style=ft.TextStyle(color=SUB))
            self.f[key] = tf
            return tf

        c = cfg
        desc_rows = []
        for label, desc in BTN_DESC.items():
            desc_rows.append(ft.Row([
                ft.Text("· " + label, size=10, color=CYAN, font_family="Microsoft YaHei UI",
                        width=180),
                ft.Text(desc, size=10, color=SUB),
            ], spacing=8))

        self.settings = ft.Column([
            ft.Text("◤ 服务连接", size=12, weight=ft.FontWeight.BOLD, color=MINT, font_family="Consolas"),
            ft.Row([field("Aria2 RPC 主机", "a_host", c["aria2"]["host"], 200),
                    field("端口", "a_port", c["aria2"]["port"], 110),
                    field("密钥文件", "a_secret", c["aria2"]["secret"], 300),
                    self.btn("测试 Aria2", self.on_test_a, CYAN)], wrap=True, spacing=8),
            ft.Container(height=1, bgcolor=A(CYAN, "33")),
            ft.Text("◤ qBittorrent WebUI", size=12, weight=ft.FontWeight.BOLD, color=CYAN, font_family="Consolas"),
            ft.Row([field("主机", "q_host", c["qbit"]["host"], 200),
                    field("端口", "q_port", c["qbit"]["port"], 110),
                    field("账号", "q_user", c["qbit"]["user"], 150),
                    field("密码", "q_pass", c["qbit"]["pass"], 180, True),
                    self.btn("测试 WebUI", self.on_test_q, CYAN)], wrap=True, spacing=8),
            ft.Container(height=1, bgcolor=A(CYAN, "33")),
            ft.Text("◤ 路径", size=12, weight=ft.FontWeight.BOLD, color=WARN, font_family="Consolas"),
            field("aria2c.exe", "p_aexe", c["aria2"]["exe"]),
            field("aria2.conf", "p_aconf", c["aria2"]["conf"]),
            field("qB 配置目录", "p_qcfg", c["qbit"]["config_dir"]),
            field("qB 保存目录", "p_qsave", c["qbit"]["save_dir"]),
            field("外部视频脚本 (bat)", "p_yt", c["yt"]["bat"]),
            field("外部脚本路径表 (ini，可选)", "p_ini", c["yt"]["ini"]),
            ft.Row([ft.Switch(label="开机自启本面板", value=bool(c["ui"].get("autostart_panel")),
                              on_change=self.on_auto_panel),
                    ft.Switch(label="开机后台拉起 Aria2", value=bool(c["ui"].get("autostart_aria2")),
                              on_change=self.on_auto_aria2),
                    self.btn("切换深色/浅色", self.on_theme, CYAN),
                    self.btn("保存设置", self.on_save, MINT),
                    self.btn("恢复默认", self.on_reset, WARN)], wrap=True, spacing=12),
            ft.Container(height=1, bgcolor=A(CYAN, "33")),
            ft.Text("◤ 按键说明 / 功能表", size=12, weight=ft.FontWeight.BOLD, color=CYAN,
                    font_family="Consolas"),
            *desc_rows,
        ], spacing=8, scroll=ft.ScrollMode.AUTO)

        self.dash_box = ft.Container(content=main, expand=True, padding=2,
                                     animate_opacity=ft.Animation(300, ft.AnimationCurve.EASE_IN))
        self.set_box = ft.Container(content=self.settings, expand=True, padding=8,
                                    visible=False, opacity=0,
                                    animate_opacity=ft.Animation(300, ft.AnimationCurve.EASE_IN))

        nav = ft.Container(width=140, bgcolor="#CC070D1A",
                           border=ft.Border.all(1, A(CYAN, "55")), border_radius=10,
                           padding=10, shadow=self.glow(CYAN, blur=8),
                           content=ft.Column([
                               ft.Row([ft.Image(src=(HA.EMBLEM if HA else ""), width=20, height=20) if HA else ft.Container(width=0),
                                       ft.Text("导航区", size=11, color=CYAN,
                                               font_family="Microsoft YaHei UI")], spacing=6),
                               self.btn("▣ 仪表盘", self.go_dash, MINT),
                               self.btn("⚙ 设置", self.go_set, CYAN),
                               ft.Container(expand=True),
                               ft.Text("HOLO-3D", size=8, color=DIM, font_family="Consolas"),
                               ft.Text("v2.2", size=8, color=DIM, font_family="Consolas"),
                           ], spacing=8, expand=True))

        grid_rows = [ft.Container(height=1, bgcolor="#0800ccff", expand=True) for _ in range(20)]
        grid_cols = [ft.Container(width=1, bgcolor="#0600E5A0", expand=True) for _ in range(30)]
        bg = ft.Stack([
            ft.Container(expand=True, gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1),
                colors=[BG, BG2, "#03050A"])),
            ft.Column(grid_rows, spacing=36, expand=True),
            ft.Row(grid_cols, spacing=56, expand=True),
        ], expand=True)

        self.scanline = ft.Container(height=90,
                                     gradient=ft.LinearGradient(
                                         begin=ft.Alignment(0, -1), end=ft.Alignment(0, 1),
                                         colors=[A(MINT, "00"), A(MINT, "10"), A(MINT, "00")]),
                                     offset=ft.Offset(0, -1.3),
                                     animate_offset=ft.Animation(3600, ft.AnimationCurve.LINEAR))

        body = ft.Container(
            expand=True, padding=10,
            content=ft.Column([
                header,
                ft.Row([nav, self.dash_box, self.set_box], expand=True, spacing=10),
                log_card,
            ], spacing=10, expand=True),
        )

        p.add(ft.Stack([bg, self.scanline, body], expand=True))

    # ---------------------------------------------------------- 导航（淡入淡出）
    def go_dash(self, e=None):
        self._fade_to(self.dash_box, self.set_box)

    def go_set(self, e=None):
        self._fade_to(self.set_box, self.dash_box)

    def _fade_to(self, show, hide):
        try:
            hide.opacity = 0
            show.visible = True
            show.opacity = 0
            self.p.update()
            show.opacity = 1
            self.p.update()
            hide.visible = False
            hide.opacity = 1
            self.p.update()
        except Exception:
            try:
                show.visible, hide.visible = True, False
                self.p.update()
            except Exception:
                pass

    # ---------------------------------------------------------- 刷新（原逻辑）
    async def _tick(self):
        import asyncio
        while True:
            try:
                self.pr.poll_a()
                self.pr.poll_q()
                self.pr.poll_y()
                self.render()
            except Exception as ex:
                self.log("轮询异常 %s" % type(ex).__name__, "ERROR")
            await asyncio.sleep(1.5)

    async def _scroll_top(self):
        """启动后把可滚动区域归位到顶部（教程/日志），避免默认停在底部。"""
        import asyncio
        await asyncio.sleep(1.2)
        for obj in (getattr(self, "tut_col", None),):
            try:
                if obj is not None:
                    await obj.scroll_to(offset=0)
                    self.p.update()
            except Exception:
                pass

    async def _fx(self):
        """UI 动画循环：指示灯呼吸 / 扫描线 / 日志扫光。"""
        import asyncio
        while True:
            try:
                self.phase = (self.phase + 1) % 4
                ph = self.phase
                # 指示灯脉冲
                for dot, state in ((self.led_a_dot, self.pr.a["on"]),
                                   (self.led_q_dot, self.pr.q["on"]),
                                   (self.led_y_dot, self.pr.y["on"])):
                    if state:
                        dot.opacity = 1.0 if ph % 2 == 0 else 0.55
                        dot.scale = 1.08 if ph % 2 == 0 else 0.94
                    else:
                        dot.opacity = 0.35 if ph % 2 == 0 else 0.18
                        dot.scale = 1.0
                # 扫描线（每 4 个相位跑一遍）
                if ph == 0:
                    self.scanline.offset = ft.Offset(0, -1.2)
                    self.p.update()
                elif ph == 1:
                    self.scanline.offset = ft.Offset(0, 1.2)
                    self.p.update()
                # 日志扫光
                try:
                    self.scan.opacity = 0.9 if ph % 2 == 0 else 0.25
                except Exception:
                    pass
                self.p.update()
            except Exception:
                pass
            await asyncio.sleep(1.1)

    def refresh(self):
        self.pr.poll_a()
        self.pr.poll_q()
        self.pr.poll_y()
        self.render()

    def _set_led(self, dot, txt, on, err):
        if on:
            color = MINT
            label = "ONLINE"
        elif err:
            color = ERR
            label = "ERROR"
        else:
            color = OFF
            label = "OFFLINE"
        dot.bgcolor = color
        try:
            dot.shadow = self.glow(color, blur=12 if on else 6)
        except Exception:
            pass
        txt.color = color
        base = txt.data or "SERVICE"
        txt.value = "%s  %s" % (base, label)
        return color

    def render(self):
        a, q, y = self.pr.a, self.pr.q, self.pr.y
        self.t_clock.value = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sec = int(time.time() - self.t0)
        self.t_up.value = "%02d:%02d:%02d" % (sec // 3600, sec % 3600 // 60, sec % 60)
        self._set_led(self.led_a_dot, self.led_a, a["on"], a["err"])
        self._set_led(self.led_q_dot, self.led_q, q["on"], q["err"])
        if q.get("err") and q.get("installed"):
            now = time.time()
            if now - getattr(self, "_q_warn_at", 0) > 60:
                self._q_warn_at = now
                self.log("qBittorrent 在运行但登录失败：到 设置页 填 WebUI 密码", "WARN")
        self._set_led(self.led_y_dot, self.led_y, y["on"], "")
        self.v_adn.value = hspeed(a["dn"])
        self.v_aup.value = hspeed(a["up"])
        self.v_atk.value = str(a["task"])
        self.v_acn.value = str(a["conn"])
        self.v_qdn.value = hspeed(q["dn"])
        self.v_qup.value = hspeed(q["up"])
        try:
            peak = 10 * 1024 * 1024
            self.bar_a.width = max(4, min(112, int(112 * min(1.0, a["dn"] / peak))))
            self.bar_q.width = max(4, min(112, int(112 * min(1.0, q["dn"] / peak))))
            self.ring_a.value = min(1.0, (a["dn"] or 0) / peak)
            self.ring_q.value = min(1.0, (q["dn"] or 0) / peak)
            for arr, val, col in ((self.spark_a, a["dn"], MINT), (self.spark_q, q["dn"], CYAN)):
                v = min(1.0, (val or 0) / peak)
                arr.pop(0)
                arr.append(ft.Container(width=3, height=max(2, int(16 * v)), bgcolor=col,
                                        border_radius=2, opacity=0.85,
                                        animate_size=ft.Animation(400, ft.AnimationCurve.EASE_OUT)))
        except Exception:
            pass
        self.v_qto.value = str(q["tor"])
        self.v_qse.value = str(q["seed"])
        self.yt_out.value = self.yt_output()
        self.p.update()

    def yt_output(self):
        ini = (self.cfg["yt"].get("ini") or "").strip()
        if ini:
            got = ini_get(ini, "OUTPUT")
            if got:
                return got
        base = self.cfg.get("paths", {}).get("downloads") or str(DL_HOME)
        return str(Path(base) / "yt-dlp")

    # ---------------------------------------------------------- 以下业务逻辑原样保留
    def run_cmd(self, args, title, key=None, cwd=None):
        try:
            proc = subprocess.Popen(args, cwd=cwd or str(ROOT), **_popen_kwargs())
            if key:
                self.pids[key] = proc.pid
                save_pids(self.pids)
            self.log("%s 发起 PID %s" % (title, proc.pid))
        except Exception as ex:
            self.log("%s 失败 %s" % (title, ex), "ERROR")

    def open(self, path):
        if not path or not Path(path).exists():
            self.log("路径不存在 %s" % path, "WARN")
            return
        open_any(path)
        self.log("打开 %s" % path)

    def on_start_a(self, e=None):
        script = str((self.cfg.get("scripts") or {}).get("start") or "")
        if script and not Path(script).exists():
            self.log("还没安装组件：先运行安装器 install.bat，或把 aria2 放到 %s"
                     % (self.cfg["aria2"]["exe"]), "ERROR")
            return
        if port_open(self.cfg["aria2"]["host"], self.cfg["aria2"]["port"]):
            self.log("Aria2 已在运行，跳过重复启动", "WARN")
            self.on_ariang()
            return
        self.run_cmd(script_cmd(self.cfg["scripts"]["start"]), "启动 Aria2", "stack")
        time.sleep(2)
        self.refresh()

    def on_stop_a(self, e=None):
        self.run_cmd(script_cmd(self.cfg["scripts"]["stop"]), "停止 Aria2")
        time.sleep(1.5)
        self.refresh()

    def on_restart_a(self, e=None):
        self.on_stop_a()
        time.sleep(2)
        self.on_start_a()

    def on_ariang(self, e=None):
        try:
            a = self.cfg.get("ariang", {}) or {}
            port = int(a.get("port") or 16800)
            if not port_open("127.0.0.1", port):
                script = str(a.get("script") or "")
                if script and Path(script).exists():
                    self.run_cmd(script_cmd(script), "启动 AriaNg 静态服务", "ariang")
                    for _ in range(20):
                        time.sleep(0.5)
                        if port_open("127.0.0.1", port):
                            break
                    if not port_open("127.0.0.1", port):
                        self.log("AriaNg 端口 %d 还没起来，10 秒后仍在等；"
                                 "请确认 %s 可执行" % (port, script), "WARN")
                else:
                    self.log("AriaNg 服务没起来，且没配置启动脚本（设置页可指定）", "WARN")
            token = ""
            try:
                tok_path = Path(str(self.cfg["aria2"]["secret"]))
                if tok_path.is_file():
                    token = tok_path.read_text(encoding="utf-8", errors="ignore").strip()
            except Exception:
                token = ""
            rpc_host = "127.0.0.1:%s" % (self.cfg["aria2"].get("port") or 6800)
            url = "http://127.0.0.1:%d/?rpc=%s" % (port, rpc_host)
            if token:
                url += "&secret=" + token
            webbrowser.open(url)
            self.log("打开 AriaNg：%s" % url)
        except Exception as ex:
            self.log("打开 AriaNg 失败 %s" % ex, "ERROR")

    def on_test_a(self, e=None):
        try:
            v = (self.pr.a_call("aria2.getVersion") or {}).get("version", "?")
            self.log("Aria2 RPC 通，version=%s" % v, "OK")
        except Exception as ex:
            self.log("Aria2 RPC 不通 %s" % ex, "ERROR")

    def on_ports(self, e=None):
        parts = []
        for name, port in (("aria2", self.cfg["aria2"]["port"]),
                           ("webui", self.cfg["qbit"]["port"]), ("ariang", int((self.cfg.get("ariang") or {}).get("port") or 16800))):
            parts.append("%s:%s=%s" % (name, port, "占用" if port_open("127.0.0.1", port) else "空闲"))
        self.log("端口 " + " ".join(parts))

    def on_start_q(self, e=None):
        if port_open(self.cfg["qbit"]["host"], self.cfg["qbit"]["port"]):
            self.log("qBittorrent 已在运行，跳过", "WARN")
            return
        self.run_cmd(script_cmd(self.cfg["scripts"]["qbit"]), "启动 qBittorrent", "qbit")
        time.sleep(3)
        self.refresh()

    def on_stop_q(self, e=None):
        pid = self.pids.get("qbit")
        if pid and pid_alive(pid):
            kill_tree(pid)
            self.pids.pop("qbit", None)
            save_pids(self.pids)
            self.log("已停止 qBittorrent PID %s" % pid)
        else:
            self.log("没有本面板记录的 qBittorrent 进程", "WARN")
        self.refresh()

    def on_webui(self, e=None):
        try:
            webbrowser.open("http://%s:%d/" % (self.cfg["qbit"]["host"], int(self.cfg["qbit"]["port"])))
            self.log("打开 WebUI")
        except Exception as ex:
            self.log("打开 WebUI 失败 %s" % ex, "ERROR")

    def on_test_q(self, e=None):
        try:
            s, base = self.pr.q_login()
            v = s.get(base + "/api/v2/app/version", timeout=2).text.strip()
            self.log("WebUI 通，version=%s" % v, "OK")
        except Exception as ex:
            self.log("WebUI 不通 %s" % ex, "ERROR")



    def _sys_proxy(self):
        """读系统代理。Windows 查注册表；macOS/Linux 读环境变量。"""
        if not IS_WIN:
            for k in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
                v = (os.environ.get(k) or "").strip()
                if v:
                    return v
            return ""
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
            try:
                enable, _ = winreg.QueryValueEx(k, "ProxyEnable")
            except Exception:
                enable = 0
            try:
                server, _ = winreg.QueryValueEx(k, "ProxyServer")
            except Exception:
                server = ""
            winreg.CloseKey(k)
            if not enable or not server:
                return ""
            s = str(server).strip()
            if "=" in s:                     # 形如 http=127.0.0.1:<port>;https=...
                for part in s.split(";"):
                    if part.lower().startswith("http="):
                        s = part.split("=", 1)[1]
                        break
            if not s:
                return ""
            if not s.lower().startswith(("http://", "socks5://", "socks4://", "https://")):
                s = "http://" + s
            return s
        except Exception:
            return ""

    def _up_label(self):
        if self.cfg["ui"].get("upscale"):
            return "已开启：之后启动的视频下载会做 2x 超分"
        return "已关闭：视频只下载不超分（默认）"

    def on_upscale_toggle(self, e=None):
        try:
            v = bool(e.control.value) if e is not None else not self.cfg["ui"].get("upscale")
        except Exception:
            v = not self.cfg["ui"].get("upscale")
        # 挂载瞬间 Flet 可能回放 on_change，不当作真人操作
        if time.time() < getattr(self, "_ui_ready_at", 0):
            try:
                self.up_txt.value = self._up_label()
                self.up_txt.color = WARN if self.cfg["ui"].get("upscale") else SUB
                self.p.update()
            except Exception:
                pass
            return
        if v == bool(self.cfg["ui"].get("upscale")):
            return
        self.cfg["ui"]["upscale"] = v
        save_cfg(self.cfg)
        try:
            self.up_txt.value = self._up_label()
            self.up_txt.color = WARN if v else SUB
            self.p.update()
        except Exception:
            pass
        self.log("超分开关 → %s（下次启动 YT 壳生效）" % ("开" if v else "关"))

    def on_start_y(self, e=None):
        bat = Path(self.cfg["yt"]["bat"])
        if not bat.exists():
            bat = Path(self.cfg["yt"]["bat2"])
        if not str(bat) or not bat.exists():
            # 回退：直接用 ControlPanel/ytdl_gui.py（安装器会生成，Windows/Linux 都有）
            gui = Path(str(self.cfg["scripts"].get("start") or "")).parent / "ControlPanel" / "ytdl_gui.py"
            alt = Path("ControlPanel") / "ytdl_gui.py"
            cand = [gui, ROOT / "ControlPanel" / "ytdl_gui.py", APP_DIR / "ytdl_gui.py"]
            hit = next((c for c in cand if c.is_file()), None)
            if hit is None:
                self.log("YT 下载器没找到：ControlPanel/ytdl_gui.py 不存在，请重跑 install.sh", "ERROR")
                return
            py = str(ROOT / ".venv" / ("Scripts/python.exe" if IS_WIN else "bin/python"))
            if not Path(py).is_file():
                py = sys.executable
            bat = hit
            self.log("YT 脚本路径为空，回退用内置下载器：%s" % hit)
            cmd_override = [py, "-B", str(hit)]
        else:
            cmd_override = script_cmd(bat)
        pid = self.pids.get("yt")
        if pid and pid_alive(pid):
            self.log("YT 壳已在运行，跳过", "WARN")
            return
        try:
            env = os.environ.copy()
            # 超分开关：开启则本次下载走 2x 超分（下游 python 读 UPSCALE）
            env["UPSCALE"] = "1" if self.cfg["ui"].get("upscale") else "0"
            # 代理：把系统代理透传给壳（面板自己不代理，本机服务不受影响）
            px = self._sys_proxy()
            if px:
                env["HTTP_PROXY"] = px
                env["HTTPS_PROXY"] = px
                env["http_proxy"] = px
                env["https_proxy"] = px
                env.pop("ALL_PROXY", None)
                env.pop("all_proxy", None)
                env["NO_PROXY"] = "localhost,127.0.0.1,::1,.local"
                env["no_proxy"] = env["NO_PROXY"]
            else:
                for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                          "http_proxy", "https_proxy", "all_proxy"):
                    env.pop(k, None)
            proc = shell_run(bat, cwd=str(bat.parent))
            self.pids["yt"] = proc.pid
            save_pids(self.pids)
            self.log("启动 YT 下载壳 PID %s（超分：%s｜代理：%s）"
                     % (proc.pid, "开" if env["UPSCALE"] == "1" else "关",
                        px if px else "直连"))
        except Exception as ex:
            self.log("启动 YT 壳失败 %s" % ex, "ERROR")
        time.sleep(2)
        self.refresh()

    def on_stop_y(self, e=None):
        pid = self.pids.get("yt")
        if pid and pid_alive(pid):
            kill_tree(pid)
            self.pids.pop("yt", None)
            save_pids(self.pids)
            self.log("已关闭 YT 壳 PID %s" % pid)
        else:
            if not (self.cfg["yt"].get("bat") or "").strip():
                self.log("未配置外部视频脚本，忽略", "INFO")
            else:
                self.log("没有本面板记录的 YT 壳进程", "WARN")
        self.refresh()

    def on_backup(self, e=None):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        dst = BACKUPS / ("backup-" + stamp)
        try:
            dst.mkdir(parents=True, exist_ok=True)
            n = 0
            for src, name in ((self.cfg["aria2"]["conf"], "aria2.conf"),
                              (str(Path(self.cfg["qbit"]["config_dir"]) / "qBittorrent.ini"), "qBittorrent.ini"),
                              (str(CONFIG), "config.json"),
                              (self.cfg["yt"]["ini"], "ytshell-paths.ini")):
                if src and Path(src).exists():
                    shutil.copy2(src, dst / name)
                    n += 1
            self.log("备份完成 %d 个文件 → %s" % (n, dst), "OK")
        except Exception as ex:
            self.log("备份失败 %s" % ex, "ERROR")

    def on_selfcheck(self, e=None):
        self.log("开始自检")
        for name, port in (("aria2", self.cfg["aria2"]["port"]),
                           ("webui", self.cfg["qbit"]["port"]), ("ariang", int((self.cfg.get("ariang") or {}).get("port") or 16800))):
            on = port_open("127.0.0.1", port)
            self.log("  端口 %s:%s %s" % (name, port, "在线" if on else "未监听"), "OK" if on else "WARN")
        for name, path in (("aria2c.exe", self.cfg["aria2"]["exe"]),
                           ("aria2.conf", self.cfg["aria2"]["conf"]),
                           ("qBittorrent.ini", str(Path(self.cfg["qbit"]["config_dir"]) / "qBittorrent.ini")),
                           ("外部视频脚本", self.cfg["yt"]["bat"]),
                           ("外部脚本路径表", self.cfg["yt"]["ini"])):
            ok = Path(path).exists()
            self.log("  %s %s" % (name, "存在" if ok else "缺失"), "OK" if ok else "ERROR")
        try:
            t = CACHE / "_w.tmp"
            t.write_text("x", encoding="utf-8")
            t.unlink(missing_ok=True)
            self.log("  D 盘可写", "OK")
        except Exception as ex:
            self.log("  D 盘不可写 %s" % ex, "ERROR")
        self.on_test_a()
        self.on_test_q()

    def on_clean_logs(self, e=None):
        dlg = ft.AlertDialog(
            title=ft.Text("清理 Aria2 日志？"),
            content=ft.Text("只删 %s 下的日志，不动配置和任务。" % self.cfg["aria2"]["logdir"]),
            actions=[ft.TextButton("取消", on_click=lambda ev: self.close_dlg(dlg)),
                     ft.TextButton("确认", on_click=lambda ev: self.do_clean_logs(dlg))])
        self.open_dlg(dlg)

    def do_clean_logs(self, dlg):
        self.close_dlg(dlg)
        n = 0
        try:
            for f in Path(self.cfg["aria2"]["logdir"]).glob("*"):
                if f.is_file():
                    f.unlink()
                    n += 1
        except Exception:
            pass
        self.log("清理 Aria2 日志 %d 个" % n, "OK")

    def on_clean_cache(self, e=None):
        dlg = ft.AlertDialog(
            title=ft.Text("清理面板临时缓存？"),
            content=ft.Text("只清 %s，不动下载成品与任务。" % CACHE),
            actions=[ft.TextButton("取消", on_click=lambda ev: self.close_dlg(dlg)),
                     ft.TextButton("确认", on_click=lambda ev: self.do_clean_cache(dlg))])
        self.open_dlg(dlg)

    def do_clean_cache(self, dlg):
        self.close_dlg(dlg)
        n = 0
        try:
            for f in CACHE.rglob("*"):
                if f.is_file():
                    f.unlink()
                    n += 1
        except Exception:
            pass
        self.log("清理缓存 %d 个" % n, "OK")

    def on_stop_all(self, e=None):
        dlg = ft.AlertDialog(
            title=ft.Text("确认停止全部服务？"),
            content=ft.Text("按 Aria2 → qBittorrent → YT 壳 顺序；只停本面板记录/端口匹配的进程。"),
            actions=[ft.TextButton("取消", on_click=lambda ev: self.close_dlg(dlg)),
                     ft.TextButton("确认停止", on_click=lambda ev: self.do_stop_all(dlg))])
        self.open_dlg(dlg)

    def do_stop_all(self, dlg):
        self.close_dlg(dlg)
        self.log("一键全部停止：Aria2 → qBittorrent → YT 壳")
        self.on_stop_a()
        self.on_stop_q()
        self.on_stop_y()

    def open_dlg(self, dlg):
        try:
            self.p.show_dialog(dlg)
        except Exception:
            try:
                self.p.overlay.append(dlg)
                dlg.open = True
                self.p.update()
            except Exception:
                pass

    def close_dlg(self, dlg):
        try:
            self.p.pop_dialog()
        except Exception:
            try:
                dlg.open = False
                self.p.update()
            except Exception:
                pass

    def on_clear_log(self, e=None):
        self.logs = []
        self.lv.controls = []
        self.p.update()

    def on_export_log(self, e=None):
        try:
            out = LOGS / ("export-%s.log" % datetime.now().strftime("%Y%m%d-%H%M%S"))
            out.write_text("\n".join(self.logs), encoding="utf-8")
            self.log("日志已导出 %s" % out, "OK")
        except Exception as ex:
            self.log("导出失败 %s" % ex, "ERROR")

    def on_save(self, e=None):
        f = self.f
        try:
            self.cfg["aria2"]["host"] = f["a_host"].value.strip()
            self.cfg["aria2"]["port"] = int(f["a_port"].value.strip() or 6800)
            self.cfg["aria2"]["secret"] = f["a_secret"].value.strip()
            self.cfg["aria2"]["exe"] = f["p_aexe"].value.strip()
            self.cfg["aria2"]["conf"] = f["p_aconf"].value.strip()
            self.cfg["qbit"]["host"] = f["q_host"].value.strip()
            self.cfg["qbit"]["port"] = int(f["q_port"].value.strip() or 8080)
            self.cfg["qbit"]["user"] = f["q_user"].value.strip()
            self.cfg["qbit"]["pass"] = f["q_pass"].value
            self.cfg["qbit"]["config_dir"] = f["p_qcfg"].value.strip()
            self.cfg["qbit"]["save_dir"] = f["p_qsave"].value.strip()
            self.cfg["yt"]["bat"] = f["p_yt"].value.strip()
            self.cfg["yt"]["ini"] = f["p_ini"].value.strip()
            save_cfg(self.cfg)
            self.pr.cfg = self.cfg
            self.log("设置已保存", "OK")
            self.refresh()
        except Exception as ex:
            self.log("保存失败 %s" % ex, "ERROR")

    def on_reset(self, e=None):
        self.cfg = json.loads(json.dumps(DAFAULT))
        save_cfg(self.cfg)
        self.pr.cfg = self.cfg
        self.log("已恢复默认（重启面板后界面同步）", "WARN")

    def on_theme(self, e=None):
        dark = self.p.theme_mode == ft.ThemeMode.DARK
        self.p.theme_mode = ft.ThemeMode.LIGHT if dark else ft.ThemeMode.DARK
        self.cfg["ui"]["theme"] = "light" if dark else "dark"
        save_cfg(self.cfg)
        self.p.update()
        self.log("主题切换 %s" % self.cfg["ui"]["theme"])

    def run_key(self, name, cmd, on):
        """开机自启：Windows 注册表 Run / macOS LaunchAgent / Linux ~/.config/autostart。"""
        try:
            if IS_WIN:
                import winreg
                k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                   r"Software\\Microsoft\\Windows\\CurrentVersion\\Run", 0,
                                   winreg.KEY_SET_VALUE)
                if on:
                    winreg.SetValueEx(k, name, 0, winreg.REG_SZ, cmd)
                else:
                    try:
                        winreg.DeleteValue(k, name)
                    except FileNotFoundError:
                        pass
                winreg.CloseKey(k)
                return True
            if IS_MAC:
                plist_dir = Path.home() / "Library" / "LaunchAgents"
                plist_dir.mkdir(parents=True, exist_ok=True)
                pf = plist_dir / ("com.downloadstack.%s.plist" % name.lower())
                if on:
                    pf.write_text(
                        '<?xml version="1.0" encoding="UTF-8"?>\n'
                        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                        '<plist version="1.0"><dict>\n'
                        '  <key>Label</key><string>com.downloadstack.%s</string>\n'
                        '  <key>ProgramArguments</key><array><string>/bin/sh</string>'
                        '<string>-c</string><string>%s</string></array>\n'
                        '  <key>RunAtLoad</key><true/>\n'
                        '</dict></plist>\n' % (name.lower(), cmd.replace("&", "&amp;")),
                        encoding="utf-8")
                else:
                    pf.unlink(missing_ok=True)
                return True
            # Linux
            adir = Path.home() / ".config" / "autostart"
            adir.mkdir(parents=True, exist_ok=True)
            df = adir / ("downloadstack-%s.desktop" % name.lower())
            if on:
                df.write_text(
                    "[Desktop Entry]\nType=Application\nName=%s\nExec=/bin/sh -c \"%s\"\n"
                    "X-GNOME-Autostart-enabled=true\n" % (name, cmd.replace('"', '\\"')),
                    encoding="utf-8")
            else:
                df.unlink(missing_ok=True)
            return True
        except Exception as ex:
            self.log("自启失败 %s" % ex, "ERROR")
            return False

    def on_auto_panel(self, e=None):
        v = bool(e.control.value)
        self.cfg["ui"]["autostart_panel"] = v
        save_cfg(self.cfg)
        import sys
        self.run_key("DownloadStackPanel", '"%s" "%s"' % (sys.executable, PANEL_DIR / "panel.py"), v)
        self.log("开机自启面板 %s" % ("开" if v else "关"))

    def on_auto_aria2(self, e=None):
        v = bool(e.control.value)
        self.cfg["ui"]["autostart_aria2"] = v
        save_cfg(self.cfg)
        self.run_key("DownloadStackAria2", 'cmd /c "%s"' % self.cfg["scripts"]["start"], v)
        self.log("开机拉起 Aria2 %s" % ("开" if v else "关"))


def main(page: ft.Page):
    Panel(page)


if __name__ == "__main__":
    # 无图形环境（SSH / 纯服务器）时自动改用 Web 模式，浏览器访问即可
    _no_display = (not IS_WIN) and (not IS_MAC) and not (
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    _force_web = os.environ.get("DOWNLOADSTACK_WEB") == "1"
    if _force_web or _no_display:
        if _no_display and not _force_web:
            print("[提示] 没有图形环境，改用 Web 模式")
        port = int(os.environ.get("DOWNLOADSTACK_WEB_PORT") or 8550)
        print("[提示] 浏览器打开 http://127.0.0.1:%d" % port)
        ft.run(main, view=ft.AppView.WEB_BROWSER, port=port)
    else:
        ft.run(main)
