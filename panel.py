# -*- coding: utf-8 -*-
"""
DOWNLOAD STACK // CONTROL —— Spatial 3D 曲面空间控制台后端服务。

硬性约束：
1) 只做监控、调度与增强路由：不内置下载引擎二进制。
2) 配置 / 缓存 / 日志 / 备份全部跟随面板目录，凭据永不落仓库。
3) 启停仅操作本面板记录的 PID 或官方 RPC/API 优雅关闭，绝不全局 taskkill。
4) 同源直出 AriaNg、支持免密 qBittorrent、融合 magnet_tools 磁力/DHT 修复与任务队列。
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

import requests

try:
    import prompt_engine as PE
except Exception:
    PE = None

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
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           capture_output=True, timeout=5,
                           creationflags=0x08000000)
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


def shell_run(script, cwd=None, env=None):
    """执行外部脚本：Windows 走 cmd，POSIX 走 bash/sh。"""
    s = str(script)
    if IS_WIN:
        args = ["cmd", "/c", s]
    else:
        shell = "/bin/bash" if s.lower().endswith(".sh") else "/bin/sh"
        args = [shell, s]
    return subprocess.Popen(args, cwd=cwd or str(ROOT), env=env, **_popen_kwargs())


def open_path(path, select_file: bool = False):
    """跨平台可靠打开本地目录或定位文件（Windows 使用 explorer.exe 置顶前台，绝不静默失效）。"""
    p = os.path.normpath(str(path or "").strip())
    if not p:
        return False, "路径为空"
    try:
        if IS_WIN:
            if select_file and Path(p).is_file():
                subprocess.Popen(["explorer.exe", "/select," + p])
                return True, "已定位并打开成品文件"
            if Path(p).is_dir():
                subprocess.Popen(["explorer.exe", p])
                return True, "已打开本地目录"
            os.startfile(p)
            return True, "已打开本地路径"
        elif IS_MAC:
            subprocess.Popen(["open", "-R", p] if (select_file and Path(p).is_file()) else ["open", p])
            return True, "已打开本地路径"
        else:
            target = str(Path(p).parent) if (select_file and Path(p).is_file()) else p
            subprocess.Popen(["xdg-open", target])
            return True, "已打开本地路径"
    except Exception as ex:
        try:
            if IS_WIN:
                os.startfile(p)
                return True, "已打开本地路径"
        except Exception:
            pass
        return False, "打开目录失败：%s" % ex

try:
    import magnet_tools as MT
except Exception:
    MT = None

try:
    import media_studio as MS
except Exception:
    MS = None

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

DEFAULT_CFG = {
    "aria2": {
        "host": "127.0.0.1", "port": 6800,
        "exe": str(ROOT / "aria2" / ("aria2c.exe" if IS_WIN else "aria2c")),
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
    "paths": {"downloads": str(DL_HOME), "music": "", "voice": "", "aigc": ""},
    "voice": {"api_url": "http://127.0.0.1:9880"},
    "comfyui": {
        "enabled": False,
        "owner_only": True,
        "url": "http://127.0.0.1:8188",
        "root": "",
        "start_bat": "",
        "custom_mode": "comfyui",
        "custom_url": "",
        "custom_api_key": "",
        "custom_model": "",
        "custom_workflow_json": "",
    },
    "codex": {
        "base_url": "",
        "api_key": "",
        "model": "gpt-5.3-codex",
        "api_style": "auto",
    },
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
    cfg = json.loads(json.dumps(DEFAULT_CFG))
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
        pid = int(pid)
        if IS_WIN:
            out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid, "/NH"],
                                 capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5,
                                 creationflags=0x08000000)
            return str(pid) in (out.stdout or "")
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
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



# ------------------------------------------------------------------ 探测（支持免密 qB + 实时任务队列）
class Probe:
    def __init__(self, cfg):
        self.cfg = cfg
        self.a = {"on": False, "ver": "", "dn": 0, "up": 0, "task": 0, "conn": 0, "err": ""}
        self.q = {"on": False, "dn": 0, "up": 0, "adl": 0, "aul": 0, "tor": 0, "seed": 0, "err": ""}
        self.y = {"on": False, "pid": None}
        self.a_tasks = []
        self.q_tasks = []

    def a_call(self, method, params=None, timeout=2.0):
        c = self.cfg["aria2"]
        sec = read_secret(c["secret"])
        body = {"jsonrpc": "2.0", "id": "panel", "method": method,
                "params": (["token:" + sec] if sec else []) + (params or [])}
        url = "http://%s:%d/jsonrpc" % (c["host"], int(c["port"]))
        s = requests.Session()
        s.trust_env = False
        r = s.post(url, json=body, timeout=timeout)
        r.raise_for_status()
        j = r.json()
        if "error" in j:
            raise RuntimeError(str(j["error"])[:120])
        return j.get("result")

    @staticmethod
    def _a_task_name(t):
        try:
            bt = (t.get("bittorrent") or {}).get("info") or {}
            if bt.get("name"):
                return str(bt["name"])
            files = t.get("files") or []
            if files:
                p = files[0].get("path") or ""
                if p:
                    return Path(p).name or p
                uris = files[0].get("uris") or []
                if uris:
                    u = uris[0].get("uri") or ""
                    return u.split("?")[0].rstrip("/").split("/")[-1] or u[:60]
        except Exception:
            pass
        return "Task " + str(t.get("gid", ""))[:8]

    def poll_a(self):
        c = self.cfg["aria2"]
        if not port_open(c["host"], c["port"]):
            self.a = {"on": False, "ver": "", "dn": 0, "up": 0, "task": 0, "conn": 0, "err": ""}
            self.a_tasks = []
            return
        try:
            gs = self.a_call("aria2.getGlobalStat") or {}
            ver = ""
            try:
                ver = (self.a_call("aria2.getVersion") or {}).get("version", "")
            except Exception:
                pass
            conn = 0
            tasks = []
            try:
                active = self.a_call("aria2.tellActive") or []
                waiting = self.a_call("aria2.tellWaiting", [0, 12]) or []
                stopped = self.a_call("aria2.tellStopped", [0, 8]) or []
                for t in active:
                    conn += int(t.get("connections", 0) or 0)
                for t in (active + waiting + stopped)[:20]:
                    tot = int(t.get("totalLength", 0) or 0)
                    done = int(t.get("completedLength", 0) or 0)
                    pct = round((done / tot) * 100, 1) if tot > 0 else 0.0
                    tname = self._a_task_name(t)
                    stt = str(t.get("status", ""))
                    tasks.append({
                        "gid": str(t.get("gid", "")),
                        "name": tname,
                        "status": stt,
                        "total": tot,
                        "done": done,
                        "pct": pct,
                        "speed": int(t.get("downloadSpeed", 0) or 0),
                        "conn": int(t.get("connections", 0) or 0),
                        "seeders": int(t.get("numSeeders", 0) or 0),
                        "err": str(t.get("errorMessage") or ""),
                        "is_meta": ("[METADATA]" in tname or (tot == 0 and stt in ("active", "waiting"))),
                    })
            except Exception:
                pass
            self.a = {"on": True, "ver": ver,
                      "dn": int(gs.get("downloadSpeed", 0) or 0),
                      "up": int(gs.get("uploadSpeed", 0) or 0),
                      "task": int(gs.get("numActive", 0) or 0),
                      "conn": conn, "err": ""}
            self.a_tasks = tasks
        except Exception as e:
            self.a = {"on": False, "ver": "", "dn": 0, "up": 0, "task": 0, "conn": 0,
                      "err": type(e).__name__}
            self.a_tasks = []

    def q_login(self, timeout=2.0):
        c = self.cfg["qbit"]
        s = requests.Session()
        s.trust_env = False
        s.proxies = {}
        base = "http://%s:%d" % (c["host"], int(c["port"]))
        hdr = {"Referer": base + "/", "Origin": base}
        # 优先兼容 LocalHostAuth=false / 本机白名单免密访问
        try:
            probe = s.get(base + "/api/v2/app/version", timeout=timeout, headers=hdr)
            if probe.status_code == 200 and (probe.text or "").strip():
                return s, base
        except Exception:
            pass
        r = s.post(base + "/api/v2/auth/login", timeout=timeout, headers=hdr,
                   data={"username": c["user"], "password": c["pass"]})
        # qB 5.x 登录成功返回 204（空 body）或 200 + "Ok."
        if r.status_code == 204:
            return s, base
        if r.status_code != 200 or "Ok" not in (r.text or ""):
            raise RuntimeError("login_%s" % r.status_code)
        return s, base

    def poll_q(self):
        c = self.cfg["qbit"]
        if not port_open(c["host"], c["port"]):
            self._q_hold_until = 0
            self.q = {"on": False, "dn": 0, "up": 0, "adl": 0, "aul": 0,
                      "tor": 0, "seed": 0, "installed": False, "err": ""}
            self.q_tasks = []
            return
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
            seed_states = {"uploading", "stalledUP", "forcedUP", "queuedUP", "checkingUP"}
            q_tasks = []
            seed_cnt = 0
            for h, x in tq.items():
                stt = str(x.get("state", ""))
                if x.get("seeding") or stt in seed_states:
                    seed_cnt += 1
                q_tasks.append({
                    "hash": str(h),
                    "name": str(x.get("name", h[:10])),
                    "state": stt,
                    "size": int(x.get("size", 0) or x.get("total_size", 0) or 0),
                    "done": int(x.get("completed", 0) or x.get("downloaded", 0) or 0),
                    "pct": round(float(x.get("progress", 0) or 0) * 100, 1),
                    "speed": int(x.get("dlspeed", 0) or 0),
                    "up": int(x.get("upspeed", 0) or 0),
                    "seeds": int(x.get("num_seeds", 0) or 0),
                    "peers": int(x.get("num_leechs", 0) or 0),
                    "eta": int(x.get("eta", 0) or 0),
                    "added_on": int(x.get("added_on", 0) or 0),
                    "ratio": round(float(x.get("ratio", 0) or 0), 2),
                })
            dl_states = {"downloading", "forcedDL", "metaDL", "stalledDL", "checkingDL", "allocating", "queuedDL"}
            q_tasks.sort(
                key=lambda it: (1 if it["state"] in dl_states else 0, it["speed"], it["added_on"], it["pct"]),
                reverse=True,
            )
            self.q = {"on": True,
                      "dn": int(st.get("dl_info_speed", 0) or 0),
                      "up": int(st.get("up_info_speed", 0) or 0),
                      "adl": int(st.get("alltime_dl", 0) or 0),
                      "aul": int(st.get("alltime_ul", 0) or 0),
                      "tor": len(tq),
                      "seed": seed_cnt,
                      "dht": int(st.get("dht_nodes", 0) or 0),
                      "conn_status": str(st.get("connection_status", "") or ""),
                      "err": ""}
            self.q_tasks = q_tasks[:25]
        except Exception as e:
            self._q_hold_until = _t.time() + 30
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
            self.q_tasks = []

    def poll_y(self):
        pid = load_pids().get("yt")
        self.y = {"on": bool(pid and pid_alive(pid)), "pid": pid}


# ================= Spatial 3D Web HUD 后端服务 =================
class ControlBackend:
    """真 3D Web HUD 后端控制器：复用全部探测、PID 隔离、配置与维护逻辑。"""

    def __init__(self):
        import threading
        self.lock = threading.Lock()
        self.cfg = load_cfg()
        self.pr = Probe(self.cfg)
        self.pids = load_pids()
        self.t0 = time.time()
        self.logs = []
        self.wave = [0] * 40
        self._q_warn_at = 0.0
        self.yt_job = {
            "running": False, "pid": None, "url": "",
            "quality": "best",
            "cookies": str((self.cfg.get("yt") or {}).get("cookies") or "auto"),
            "cookies_file": str((self.cfg.get("yt") or {}).get("cookies_file") or ""),
            "pct": 0.0, "speed": "", "eta": "", "status": "就绪",
            "logs": [], "file": "",
        }
        self.music_job = {
            "running": False, "pid": None, "query": "", "source": "all",
            "fmt": "mp3", "title": "", "artist": "",
            "pct": 0.0, "speed": "", "eta": "", "status": "就绪",
            "results": [], "lyrics": {}, "logs": [], "file": "",
        }
        self.stream_tokens = {}
        self.repair4k_job = {
            "running": False, "pid": None, "pct": 0.0, "stage": "就绪",
            "src_path": "", "src_name": "", "out_path": "", "out_name": "",
            "encoder": "", "err": "", "cancel": False,
        }
        self.after_dl = {
            "mode": "off", "seen_active": False, "countdown": 0,
            "deadline": 0.0, "status": "未启用", "active_cnt": 0,
        }
        self._disk_cache = (0.0, {})
        cached_ref = CACHE / "ref_voice.wav"
        self.voice_job = {
            "running": False, "pid": None, "installing": False,
            "engine": "edge", "status": "就绪", "pct": 0.0,
            "ref_wav": str(cached_ref) if cached_ref.is_file() else "",
            "ref_name": "已加载上次参考音色 (ref_voice.wav)" if cached_ref.is_file() else "",
            "ref_text": "",
            "out_file": "",
            "api_url": str((self.cfg.get("voice") or {}).get("api_url") or "http://127.0.0.1:9880"),
            "logs": [],
        }
        self.aigc_job = {
            "running": False, "cancel": False,
            "mode": "t2i", "engine": "owner_comfy",
            "prompt": "", "neg_prompt": "",
            "width": 1024, "height": 576, "steps": 8, "length": 33, "seed": -1,
            "first_frame": "", "first_frame_name": "",
            "pct": 0.0, "status": "就绪",
            "gallery": [], "logs": [],
        }
        self._aigc_env_cache = None
        self._aigc_env_ts = 0.0
        self._voice_env_cache = None
        self._voice_env_ts = 0.0
        self._recent_cache = []
        self._recent_ts = 0.0
        self.log("Spatial 3D 控制台启动，配置 %s" % CONFIG)
        self.poll_once()
        t = threading.Thread(target=self._poll_loop, daemon=True)
        t.start()

    def log(self, msg, level="INFO"):
        line = "%s [%-5s] %s" % (datetime.now().strftime("%H:%M:%S"), level, msg)
        with self.lock:
            self.logs.append(line)
            if len(self.logs) > 300:
                self.logs = self.logs[-300:]
        try:
            with open(LOGS / ("panel-%s.log" % datetime.now().strftime("%Y%m%d")),
                      "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def poll_once(self):
        try:
            self.pr.poll_a()
            self.pr.poll_q()
            self.pr.poll_y()
            q = self.pr.q
            if q.get("err") and q.get("installed"):
                now = time.time()
                if now - self._q_warn_at > 60:
                    self._q_warn_at = now
                    self.log("qBittorrent 在运行但登录失败：请到设置抽屉填写 WebUI 密码", "WARN")
            total_dn = int((self.pr.a.get("dn") or 0) + (self.pr.q.get("dn") or 0))
            with self.lock:
                self.wave.append(total_dn)
                if len(self.wave) > 40:
                    self.wave = self.wave[-40:]
            self._check_after_dl()
        except Exception as ex:
            self.log("轮询异常 %s" % type(ex).__name__, "ERROR")

    def _disk_stats(self) -> dict:
        now = time.time()
        ts, cached = getattr(self, "_disk_cache", (0.0, {}))
        if cached and now - ts < 5.0:
            return dict(cached)
        dl_base = Path(str(self.cfg.get("paths", {}).get("downloads") or str(DL_HOME)))
        probe_p = dl_base if dl_base.exists() else Path(dl_base.anchor or ".")
        try:
            du = shutil.disk_usage(str(probe_p))
            free_gb = round(du.free / (1024 ** 3), 1)
            total_gb = round(du.total / (1024 ** 3), 1)
            used_pct = round((du.used / du.total) * 100.0, 1) if du.total > 0 else 0.0
            lvl = "crit" if free_gb < 10.0 else ("warn" if free_gb < 30.0 else "ok")
            drive = (probe_p.drive or str(probe_p)[:2] or "/").rstrip("\\")
            res = {
                "drive": drive, "free": int(du.free), "total": int(du.total),
                "free_gb": free_gb, "total_gb": total_gb, "used_pct": used_pct, "level": lvl,
            }
        except Exception:
            res = {"drive": "-", "free": 0, "total": 0, "free_gb": 0.0, "total_gb": 0.0, "used_pct": 0.0, "level": "ok"}
        self._disk_cache = (now, res)
        return dict(res)

    def _count_active_jobs(self) -> int:
        cnt = 0
        try:
            cnt += sum(1 for t in (self.pr.a_tasks or []) if t.get("status") in ("active", "waiting"))
        except Exception:
            pass
        try:
            dl_st = {"downloading", "forcedDL", "metaDL", "forcedMetaDL", "stalledDL", "checkingDL", "allocating", "queuedDL"}
            cnt += sum(1 for t in (self.pr.q_tasks or []) if t.get("state") in dl_st)
        except Exception:
            pass
        with self.lock:
            if self.yt_job.get("running"):
                cnt += 1
            if self.repair4k_job.get("running"):
                cnt += 1
        return cnt

    def _check_after_dl(self):
        with self.lock:
            mode = self.after_dl.get("mode", "off")
        if mode == "off":
            return
        active = self._count_active_jobs()
        now = time.time()
        fire_mode = None
        with self.lock:
            self.after_dl["active_cnt"] = active
            if active > 0:
                self.after_dl["seen_active"] = True
                self.after_dl["deadline"] = 0.0
                self.after_dl["countdown"] = 0
                self.after_dl["status"] = "护航中（%d 个任务运行中）" % active
            elif self.after_dl.get("seen_active"):
                dl = float(self.after_dl.get("deadline") or 0.0)
                if dl <= 0.0:
                    self.after_dl["deadline"] = now + 15.0
                    self.after_dl["countdown"] = 15
                    self.after_dl["status"] = "全部完成！15 秒后执行（可随时取消）"
                else:
                    rem = int(max(0, round(dl - now)))
                    self.after_dl["countdown"] = rem
                    if rem > 0:
                        self.after_dl["status"] = "全部完成！%d 秒后执行（可随时取消）" % rem
                    else:
                        fire_mode = mode
                        self.after_dl.update({
                            "mode": "off", "seen_active": False, "countdown": 0,
                            "deadline": 0.0, "status": "已触发：%s" % mode,
                        })
            else:
                self.after_dl["status"] = "待机中（等待新任务启动后开始监听）"

        if not fire_mode:
            return
        if fire_mode == "stop_seed":
            try:
                if port_open(self.cfg["qbit"]["host"], self.cfg["qbit"]["port"]):
                    s, base = self.pr.q_login(timeout=3.0)
                    hdr = {"Referer": base + "/", "Origin": base}
                    for ep in ("/api/v2/torrents/stop", "/api/v2/torrents/pause"):
                        r = s.post(base + ep, timeout=4.0, headers=hdr, data={"hashes": "all"})
                        if r.status_code == 200:
                            break
                self.log("🌙 挂机护航：全部下载已完成，已自动停止做种省电 ✔", "OK")
            except Exception as ex:
                self.log("挂机停种失败：%s" % ex, "WARN")
        elif fire_mode == "sleep":
            self.log("🌙 挂机护航：全部下载已完成，正在进入系统睡眠…", "WARN")
            try:
                if IS_WIN:
                    subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
                elif IS_MAC:
                    subprocess.Popen(["pmset", "sleepnow"])
                else:
                    subprocess.Popen(["systemctl", "suspend"])
            except Exception as ex:
                self.log("系统睡眠触发失败：%s" % ex, "ERROR")
        elif fire_mode == "shutdown":
            self.log("⏻ 挂机护航：全部下载已完成，将在 60 秒后关机（可点取消中止）", "WARN")
            try:
                if IS_WIN:
                    subprocess.Popen(["shutdown", "/s", "/t", "60", "/c", "DownloadStack 全部下载任务已完成，60秒后自动关机"])
                else:
                    subprocess.Popen(["shutdown", "-h", "+1"])
            except Exception as ex:
                self.log("系统关机触发失败：%s" % ex, "ERROR")

    def captures_output(self) -> Path:
        base = Path(str(self.cfg.get("paths", {}).get("downloads") or str(DL_HOME)))
        p = base / "captures"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _poll_loop(self):
        while True:
            time.sleep(1.5)
            self.poll_once()

    def yt_output(self):
        custom = (self.cfg.get("yt", {}).get("output") or "").strip()
        if custom:
            return custom
        ini = (self.cfg["yt"].get("ini") or "").strip()
        if ini:
            got = ini_get(ini, "OUTPUT")
            if got:
                return got
        base = self.cfg.get("paths", {}).get("downloads") or str(DL_HOME)
        return str(Path(base) / "yt-dlp")

    def music_output(self):
        custom = (self.cfg.get("paths", {}).get("music") or "").strip()
        if custom:
            return custom
        base = self.cfg.get("paths", {}).get("downloads") or str(DL_HOME)
        return str(Path(base) / "music")

    def voice_output(self):
        custom = (self.cfg.get("paths", {}).get("voice") or "").strip()
        if custom:
            return custom
        base = self.cfg.get("paths", {}).get("downloads") or str(DL_HOME)
        return str(Path(base) / "voice-clone")

    def aigc_output(self):
        custom = (self.cfg.get("paths", {}).get("aigc") or "").strip()
        if custom:
            return custom
        base = self.cfg.get("paths", {}).get("downloads") or str(DL_HOME)
        return str(Path(base) / "ai-studio")

    def _allowed_media_roots(self):
        base = Path(self.cfg.get("paths", {}).get("downloads") or str(DL_HOME))
        cands = [
            base,
            base / "aria2",
            Path(self.cfg.get("qbit", {}).get("save_dir") or str(base / "qBittorrent")),
            Path(self.yt_output()),
            Path(self.music_output()),
            Path(self.voice_output()),
            Path(self.aigc_output()),
            CACHE,
        ]
        cands.extend(getattr(self, "_cine_roots", set()) or set())
        comfy_root = (self.cfg.get("comfyui") or {}).get("root") or ""
        if comfy_root:
            cands.append(Path(comfy_root) / "output")
            cands.append(Path(comfy_root) / "input")
        with self.lock:
            for fp in (self.yt_job.get("file"), self.music_job.get("file"),
                       self.voice_job.get("out_file"), self.voice_job.get("ref_wav"),
                       self.aigc_job.get("first_frame")):
                if fp:
                    try:
                        cands.append(Path(fp).resolve().parent)
                    except Exception:
                        pass
            for g in (self.aigc_job.get("gallery") or []):
                fp = g.get("path") if isinstance(g, dict) else ""
                if fp:
                    try:
                        cands.append(Path(fp).resolve().parent)
                    except Exception:
                        pass
        roots = []
        for c in cands:
            try:
                roots.append(c.resolve())
            except Exception:
                pass
        return roots

    def _is_allowed_media(self, raw_path: str):
        if not raw_path:
            return None
        try:
            target = Path(raw_path).resolve()
        except Exception:
            return None
        if not target.is_file():
            return None
        allowed_exts = {
            ".mp3", ".flac", ".wav", ".m4a", ".ogg", ".aac", ".opus",
            ".webm", ".mp4", ".mkv", ".mov", ".m4v", ".avi", ".ts", ".wmv", ".flv",
            ".png", ".jpg", ".jpeg", ".webp", ".gif",
        }
        if target.suffix.lower() not in allowed_exts:
            return None
        for rt in self._allowed_media_roots():
            try:
                target.relative_to(rt)
                return target
            except ValueError:
                continue
        return None

    # ===================== CINEMA: in-app video library =====================
    _VIDEO_EXTS = {".mkv", ".mp4", ".webm", ".mov", ".m4v", ".avi", ".ts", ".m2ts", ".wmv", ".flv", ".rmvb"}
    _WEB_VIDEO_EXTS = {".mkv", ".mp4", ".webm", ".mov", ".m4v"}
    _SUB_EXTS = {".srt", ".vtt", ".ass", ".ssa"}
    _COPY_VCODECS = {"h264", "hevc", "h265", "vp9", "vp8", "av1"}
    _COPY_ACODECS = {"aac", "mp3", "opus"}
    _TEXT_SUB_CODECS = {"subrip", "srt", "ass", "ssa", "webvtt", "mov_text", "text"}

    def _is_allowed_sub(self, raw_path: str):
        if not raw_path:
            return None
        try:
            target = Path(raw_path).resolve()
        except Exception:
            return None
        if not target.is_file() or target.suffix.lower() not in self._SUB_EXTS:
            return None
        try:
            if target.stat().st_size > 8 * 1024 * 1024:
                return None
        except Exception:
            return None
        for rt in self._allowed_media_roots():
            try:
                target.relative_to(rt)
                return target
            except ValueError:
                continue
        return None

    def _walk_videos(self, root: Path, max_depth=4, min_size=1 << 20, cap=400):
        out = []
        try:
            root = Path(root).resolve()
        except Exception:
            return out
        if root.is_file():
            if root.suffix.lower() in self._VIDEO_EXTS:
                try:
                    if root.stat().st_size >= min_size:
                        out.append(root)
                except Exception:
                    pass
            return out
        if not root.is_dir():
            return out
        base_depth = len(root.parts)
        for dp, dns, fns in os.walk(root):
            if len(Path(dp).parts) - base_depth >= max_depth:
                dns[:] = []
            dns[:] = [d for d in dns if not d.startswith(".") and d.lower() not in ("$recycle.bin", "node_modules", "__pycache__")]
            for fn in fns:
                low_fn = fn.lower()
                if os.path.splitext(fn)[1].lower() not in self._VIDEO_EXTS:
                    continue
                if any(tok in low_fn for tok in (".tmp.", ".part.", ".upscaling.", ".!qb")):
                    continue  # skip unfinished / staging files
                if os.path.exists(os.path.join(dp, fn + ".aria2")):
                    continue  # aria2 still downloading
                fp = Path(dp) / fn
                try:
                    if fp.stat().st_size < min_size:
                        continue
                except Exception:
                    continue
                out.append(fp)
                if len(out) >= cap:
                    return out
        return out

    def _video_subs(self, p: Path, single_video: bool):
        from urllib.parse import quote
        subs = []
        stem = p.stem.lower()
        dirs = [p.parent] + [p.parent / d for d in ("Subs", "subs", "Subtitles", "subtitles")]
        for d in dirs:
            if not d.is_dir():
                continue
            try:
                entries = sorted(d.iterdir())
            except Exception:
                continue
            for sib in entries:
                if not sib.is_file() or sib.suffix.lower() not in self._SUB_EXTS:
                    continue
                nm = sib.name.lower()
                if not (nm.startswith(stem) or single_video or d != p.parent):
                    continue
                label = sib.stem[len(p.stem):].strip(" ._-") if nm.startswith(stem) else sib.stem
                subs.append({"label": label or "字幕", "url": "/api/subtitle?path=" + quote(str(sib), safe="")})
                if len(subs) >= 12:
                    return subs
        return subs

    def _video_item(self, p: Path, source: str, extra=None, single_video=False):
        from urllib.parse import quote
        try:
            st = p.stat()
        except Exception:
            return None
        ext = p.suffix.lower()
        it = {
            "name": p.name, "path": str(p), "size": int(st.st_size), "mtime": int(st.st_mtime),
            "ext": ext, "source": source, "hash": "", "torrent": "", "ready": True, "pct": 100.0,
            "web": ext in self._WEB_VIDEO_EXTS,
            "play_url": "/api/media?path=" + quote(str(p), safe=""),
            "subs": [],
        }
        try:
            it["subs"] = self._video_subs(p, single_video)
        except Exception:
            pass
        if extra:
            it.update(extra)
        return it

    def video_library(self):
        items, seen = [], set()
        new_roots = set()
        try:
            s, base = self.pr.q_login()
            ts = s.get(base + "/api/v2/torrents/info", timeout=4.0, headers={"Referer": base + "/"}).json() or []
        except Exception:
            ts = []
        for t in ts:
            cp = str(t.get("content_path") or "").strip()
            if not cp:
                continue
            pct = round(float(t.get("progress") or 0) * 100, 1)
            vids = self._walk_videos(Path(cp), max_depth=3, min_size=20 << 20, cap=200)
            sized = []
            for v in vids:
                try:
                    sized.append((v.stat().st_size, v))
                except Exception:
                    pass
            sized.sort(key=lambda x: -x[0])
            for _, v in sized:
                key = str(v).lower()
                if key in seen:
                    continue
                seen.add(key)
                new_roots.add(v.parent)
                it = self._video_item(v, "qB", {
                    "hash": str(t.get("hash") or ""), "torrent": str(t.get("name") or ""),
                    "ready": pct >= 100, "pct": pct,
                }, single_video=len(sized) == 1)
                if it:
                    items.append(it)
        self._cine_roots = new_roots
        base = Path(self.cfg.get("paths", {}).get("downloads") or str(DL_HOME))
        aria_dir = base / "aria2"
        yt_dir = Path(self.yt_output())
        roots = [(Path(self.cfg.get("qbit", {}).get("save_dir") or str(base / "qBittorrent")), "qB"),
                 (aria_dir, "aria2"), (yt_dir, "YT"), (base, "本地")]
        for r, label in roots:
            for v in self._walk_videos(r):
                key = str(v).lower()
                if key in seen:
                    continue
                seen.add(key)
                it = self._video_item(v, label)
                if it:
                    items.append(it)
                if len(items) >= 600:
                    break
        items.sort(key=lambda i: (0 if i["ready"] else 1, -i["mtime"]))
        return items

    def probe_video(self, raw_path: str) -> dict:
        """使用 ffprobe 实时探测视频真实画质参数与内嵌字幕轨（带文件 mtime 缓存）。"""
        from urllib.parse import quote
        target = self._is_allowed_media(raw_path)
        if target is None:
            return {"ok": False, "msg": "文件不存在或不在允许目录内"}
        try:
            st = target.stat()
            cache_key = (str(target), int(st.st_mtime), int(st.st_size))
        except Exception:
            return {"ok": False, "msg": "无法读取文件信息"}
        cache = getattr(self, "_probe_cache", None)
        if cache is None:
            cache = {}
            self._probe_cache = cache
        if cache_key in cache:
            return dict(cache[cache_key])

        ff_dir = self._find_ffmpeg()
        ffprobe = ""
        if ff_dir:
            cand = Path(ff_dir) / ("ffprobe.exe" if IS_WIN else "ffprobe")
            if cand.is_file():
                ffprobe = str(cand)
        if not ffprobe:
            ffprobe = shutil.which("ffprobe") or ""

        ext = target.suffix.lower()
        info = {
            "ok": True,
            "path": str(target),
            "size": int(st.st_size),
            "ext": ext,
            "width": 0, "height": 0, "res_label": "",
            "vcodec": "", "pix_fmt": "", "bit_depth": "", "fps": 0.0,
            "bitrate_mbps": 0.0, "duration": 0.0,
            "acodec": "", "achannels": 0,
            "color_transfer": "", "color_primaries": "", "is_hdr": False,
            "issues": [],
            "can_copy_video": True,
            "needs_remux": ext not in self._WEB_VIDEO_EXTS,
            "has_ffmpeg": bool(ff_dir or shutil.which("ffmpeg")),
            "embedded_subs": [],
        }
        if not ffprobe:
            return info

        try:
            r = subprocess.run(
                [ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(target)],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=8,
                creationflags=(0x08000000 if IS_WIN else 0),
            )
            if r.returncode == 0 and (r.stdout or "").strip():
                meta = json.loads(r.stdout)
                fmt = meta.get("format") or {}
                try:
                    info["duration"] = round(float(fmt.get("duration") or 0), 2)
                except Exception:
                    pass
                try:
                    br = float(fmt.get("bit_rate") or 0)
                    if br > 0:
                        info["bitrate_mbps"] = round(br / 1_000_000.0, 2)
                except Exception:
                    pass
                streams = meta.get("streams") or []
                v_st = next((x for x in streams if x.get("codec_type") == "video"
                             and (x.get("disposition") or {}).get("attached_pic", 0) == 0), None)
                a_st = next((x for x in streams if x.get("codec_type") == "audio"), None)
                if v_st:
                    w = int(v_st.get("width") or 0)
                    h = int(v_st.get("height") or 0)
                    vc = str(v_st.get("codec_name") or "").lower()
                    pf = str(v_st.get("pix_fmt") or "").lower()
                    info["width"] = w
                    info["height"] = h
                    info["vcodec"] = vc
                    info["pix_fmt"] = pf
                    info["bit_depth"] = "10bit" if ("10" in pf or "p010" in pf) else ("12bit" if "12" in pf else "8bit")
                    if max(w, h) >= 3800 or h >= 2100:
                        info["res_label"] = "4K UHD"
                    elif max(w, h) >= 2500 or h >= 1400:
                        info["res_label"] = "2K QHD"
                    elif max(w, h) >= 1900 or h >= 1000:
                        info["res_label"] = "1080P FHD"
                    elif max(w, h) >= 1200 or h >= 700:
                        info["res_label"] = "720P HD"
                    elif w and h:
                        info["res_label"] = "%dx%d" % (w, h)
                    fr = str(v_st.get("avg_frame_rate") or v_st.get("r_frame_rate") or "")
                    if "/" in fr:
                        try:
                            a_n, b_n = fr.split("/", 1)
                            if float(b_n) > 0:
                                info["fps"] = round(float(a_n) / float(b_n), 2)
                        except Exception:
                            pass
                    # 浏览器对 10bit H.264 / yuv444p / gbrp / rgb24 无法直接硬解，必须标记为需兼容性转码
                    bad_h264_pf = (vc == "h264" and pf and pf not in ("yuv420p", "yuvj420p", "nv12"))
                    bad_any_pf = (pf in ("yuv444p", "yuv444p10le", "gbrp", "rgb24", "bgr24"))
                    info["can_copy_video"] = (vc in self._COPY_VCODECS) and (not bad_h264_pf) and (not bad_any_pf)
                    if bad_h264_pf or bad_any_pf:
                        info["needs_remux"] = True
                    ct = str(v_st.get("color_transfer") or "").lower()
                    cp = str(v_st.get("color_primaries") or "").lower()
                    info["color_transfer"] = ct
                    info["color_primaries"] = cp
                    info["is_hdr"] = (ct in ("smpte2084", "arib-std-b67")) or ("2020" in cp)
                    # 自动画质体检诊断
                    issues = []
                    if w and h and max(w, h) < 3800 and h < 2100:
                        issues.append("源片仅 %dx%d（非原生 4K），建议开启 GPU 4K 锐化或用显卡重建纯 4K 母带" % (w, h))
                    br_m = float(info.get("bitrate_mbps") or 0)
                    if br_m > 0:
                        if h >= 2100 and br_m < 10.0:
                            issues.append("4K 码率偏低（%.1f Mbps，压缩痕迹较重）" % br_m)
                        elif 1000 <= h < 2100 and br_m < 4.5:
                            issues.append("1080P 码率偏低（%.1f Mbps，存在有损压缩模糊）" % br_m)
                        elif h < 1000 and br_m < 2.2:
                            issues.append("低清低码率片源（%.1f Mbps）" % br_m)
                    if info["is_hdr"]:
                        issues.append("检测到 HDR (%s/%s)，网页直接渲染易发灰，已支持一键色彩还原" % (ct or "HDR", cp or "BT2020"))
                    info["issues"] = issues
                if a_st:
                    ac = str(a_st.get("codec_name") or "").lower()
                    info["acodec"] = ac
                    info["achannels"] = int(a_st.get("channels") or 0)
                    # AC3/EAC3/DTS/TrueHD/PCM/WMA 在浏览器原生直出常无声，自动走无损视频直封 (-c:v copy)
                    if ac and ac not in self._COPY_ACODECS and ac not in ("vorbis", "flac"):
                        info["needs_remux"] = True
                # 提取内嵌文本字幕轨
                emb_subs = []
                for idx_s, s_st in enumerate(streams):
                    if s_st.get("codec_type") != "subtitle":
                        continue
                    sc = str(s_st.get("codec_name") or "").lower()
                    if sc not in self._TEXT_SUB_CODECS:
                        continue
                    s_idx = int(s_st.get("index", idx_s))
                    tags = s_st.get("tags") or {}
                    title = str(tags.get("title") or tags.get("TITLE") or "").strip()
                    lang = str(tags.get("language") or tags.get("LANGUAGE") or "").strip()
                    lbl = " · ".join(x for x in (title, lang) if x) or ("内嵌字幕 #%d" % (len(emb_subs) + 1))
                    emb_subs.append({
                        "stream": s_idx,
                        "label": "内嵌·" + lbl,
                        "lang": lang.lower(),
                        "url": "/api/subtitle?path=%s&stream=%d" % (quote(str(target), safe=""), s_idx),
                    })
                    if len(emb_subs) >= 12:
                        break
                info["embedded_subs"] = emb_subs
        except Exception:
            pass

        if len(cache) > 80:
            cache.clear()
        cache[cache_key] = dict(info)
        return info

    def _run_repair_4k_worker(self, src: Path, preset: str = "ultra4k", fix_hdr: bool = True):
        """后台使用 RTX NVENC + Lanczos 4K + Deblock/HQDN3D + FidelityFX CAS 重建纯 4K 高码率母带。"""
        ff_dir = self._find_ffmpeg()
        ffmpeg_exe = (str(Path(ff_dir) / ("ffmpeg.exe" if IS_WIN else "ffmpeg")) if ff_dir else (shutil.which("ffmpeg") or ""))
        if not ffmpeg_exe:
            with self.lock:
                self.repair4k_job.update({"running": False, "stage": "缺少 ffmpeg", "err": "未找到 ffmpeg 可执行文件"})
            return

        pinfo = self.probe_video(str(src))
        w = int(pinfo.get("width") or 0)
        h = int(pinfo.get("height") or 0)
        dur = float(pinfo.get("duration") or 0.0)
        acodec = str(pinfo.get("acodec") or "").lower()
        is_hdr = bool(pinfo.get("is_hdr"))

        out_path = src.with_name(src.stem + "_4K纯享修复.mp4")
        idx_n = 2
        while out_path.exists():
            out_path = src.with_name("%s_4K纯享修复_%d.mp4" % (src.stem, idx_n))
            idx_n += 1

        # 探测可用编码器（优先 RTX hevc_nvenc -> h264_nvenc -> libx264）
        enc_name = "libx264"
        try:
            enc_txt = subprocess.run(
                [ffmpeg_exe, "-hide_banner", "-encoders"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=6,
                creationflags=(0x08000000 if IS_WIN else 0),
            ).stdout or ""
            if "hevc_nvenc" in enc_txt:
                enc_name = "hevc_nvenc"
            elif "h264_nvenc" in enc_txt:
                enc_name = "h264_nvenc"
        except Exception:
            pass

        # 构建专业 4K 修复滤镜链：去压缩块/降噪 -> 纯 4K Lanczos 超分 -> AMD FidelityFX CAS 锐化 -> 微纹理 & HDR防发灰
        vf = []
        if preset in ("deblock", "ultra4k"):
            vf.append("deblock=filter=weak:block=4")
            vf.append("hqdn3d=1.0:1.0:3.0:3.0")
        # 若非纯 4K (3840 宽 / 2160 高)，拉升至纯 4K UHD（保持原比例且宽高为偶数）
        if max(w, h) < 3800 and h < 2100:
            if w > 0 and h > 0 and h > w:
                vf.append("scale=-2:3840:flags=lanczos+accurate_rnd+full_chroma_int")
            else:
                vf.append("scale=3840:-2:flags=lanczos+accurate_rnd+full_chroma_int")
        cas_val = "0.52" if preset == "ultra4k" else "0.42"
        vf.append("cas=strength=%s" % cas_val)
        vf.append("unsharp=3:3:0.30:3:3:0.0")
        if is_hdr and fix_hdr:
            vf.append("eq=contrast=1.08:saturation=1.15:gamma=1.02")
        vf.append("format=yuv420p")

        def _build_cmd(enc):
            c = [
                ffmpeg_exe, "-y", "-hide_banner", "-v", "error", "-nostdin",
                "-i", str(src),
                "-map", "0:v:0", "-map", "0:a:0?",
                "-vf", ",".join(vf),
            ]
            if enc == "hevc_nvenc":
                c += [
                    "-c:v", "hevc_nvenc", "-preset", "p5", "-tune", "hq",
                    "-rc", "vbr", "-cq", "16", "-b:v", "35M", "-maxrate", "65M", "-bufsize", "80M",
                    "-spatial_aq", "1", "-temporal_aq", "1", "-tag:v", "hvc1",
                ]
            elif enc == "h264_nvenc":
                c += [
                    "-c:v", "h264_nvenc", "-preset", "p5", "-tune", "hq",
                    "-rc", "vbr", "-cq", "16", "-b:v", "35M", "-maxrate", "65M", "-bufsize", "80M",
                    "-spatial_aq", "1",
                ]
            else:
                c += ["-c:v", "libx264", "-preset", "fast", "-crf", "16"]
            if acodec in self._COPY_ACODECS:
                c += ["-c:a", "copy"]
            else:
                c += ["-c:a", "aac", "-b:a", "320k", "-ac", "2"]
            c += ["-movflags", "+faststart", "-progress", "pipe:1", str(out_path)]
            return c

        with self.lock:
            self.repair4k_job.update({
                "running": True, "pct": 1.0,
                "stage": "正在调用 %s 重建纯 4K (3840×2160) 高码率母带…" % enc_name,
                "src_path": str(src), "src_name": src.name,
                "out_path": str(out_path), "out_name": out_path.name,
                "encoder": enc_name, "err": "", "cancel": False,
            })

        try_encs = [enc_name] + ([e for e in ("h264_nvenc", "libx264") if e != enc_name])
        success = False
        last_err = ""
        for enc in try_encs:
            with self.lock:
                if self.repair4k_job.get("cancel"):
                    break
                self.repair4k_job["encoder"] = enc
                self.repair4k_job["stage"] = "正在用 %s 重建纯 4K 母带…" % enc
            cmd = _build_cmd(enc)
            proc = None
            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, encoding="utf-8", errors="replace",
                    creationflags=(0x08000000 if IS_WIN else 0),
                )
                with self.lock:
                    self.repair4k_job["pid"] = proc.pid
                while True:
                    with self.lock:
                        if self.repair4k_job.get("cancel"):
                            proc.terminate()
                            break
                    line = proc.stdout.readline()
                    if not line:
                        if proc.poll() is not None:
                            break
                        continue
                    s = line.strip()
                    if s.startswith("out_time_us=") and dur > 0:
                        try:
                            us = float(s.split("=", 1)[1])
                            pct = min(99.0, max(1.0, (us / 1_000_000.0) / dur * 100.0))
                            with self.lock:
                                self.repair4k_job["pct"] = round(pct, 1)
                        except Exception:
                            pass
                    elif s.startswith("speed="):
                        spd = s.split("=", 1)[1].strip()
                        if spd and spd != "N/A":
                            with self.lock:
                                self.repair4k_job["stage"] = "纯 4K 母带重建中（%s · 速度 %s）" % (enc, spd)
                rc = proc.wait()
                err_txt = (proc.stderr.read() or "").strip() if proc.stderr else ""
                with self.lock:
                    canceled = bool(self.repair4k_job.get("cancel"))
                if canceled:
                    try:
                        if out_path.exists():
                            out_path.unlink()
                    except Exception:
                        pass
                    with self.lock:
                        self.repair4k_job.update({"running": False, "pid": None, "pct": 0.0, "stage": "已取消重建"})
                    return
                if rc == 0 and out_path.is_file() and out_path.stat().st_size > 100_000:
                    success = True
                    break
                last_err = err_txt[-160:] if err_txt else ("exit=%d" % rc)
                try:
                    if out_path.exists():
                        out_path.unlink()
                except Exception:
                    pass
            except Exception as ex:
                last_err = str(ex)
                if proc is not None:
                    try:
                        proc.kill()
                    except Exception:
                        pass

        if success:
            with self.lock:
                self.repair4k_job.update({
                    "running": False, "pid": None, "pct": 100.0,
                    "stage": "纯 4K 高码率母带重建完成 ✔",
                    "out_path": str(out_path), "out_name": out_path.name, "err": "",
                })
            self.log("纯 4K 母带重建完成 → %s" % out_path.name, "OK")
        else:
            with self.lock:
                self.repair4k_job.update({
                    "running": False, "pid": None, "pct": 0.0,
                    "stage": "4K 重建失败", "err": last_err or "编码失败",
                })
            self.log("纯 4K 母带重建失败：%s" % last_err, "ERROR")

    @staticmethod
    def _pick_folder_dialog(initial: str = "") -> str:
        """弹出跨平台系统原生文件夹选择框（置顶显示，防止被主窗遮挡）。"""
        code = (
            "import sys, tkinter as tk\n"
            "from tkinter import filedialog\n"
            "r = tk.Tk(); r.withdraw(); r.attributes('-topmost', True)\n"
            "init = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else ''\n"
            "p = filedialog.askdirectory(initialdir=init or None, title='选择下载保存目录')\n"
            "r.destroy()\n"
            "print(p or '', end='')\n"
        )
        try:
            init_arg = initial if (initial and Path(initial).is_dir()) else ""
            py_exe = sys.executable
            if IS_WIN:
                pyw = Path(sys.executable).with_name("pythonw.exe")
                if pyw.is_file():
                    py_exe = str(pyw)
            res = subprocess.run(
                [py_exe, "-B", "-c", code, init_arg],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
                **_popen_kwargs()
            )
            return (res.stdout or "").strip()
        except Exception:
            return ""

    def _sys_proxy(self):
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
            if "=" in s:
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

    def run_cmd(self, args, title, key=None, cwd=None):
        try:
            proc = subprocess.Popen(args, cwd=cwd or str(ROOT), **_popen_kwargs())
            if key:
                self.pids[key] = proc.pid
                save_pids(self.pids)
            self.log("%s 发起 PID %s" % (title, proc.pid))
            return True, "%s 已发起" % title
        except Exception as ex:
            self.log("%s 失败 %s" % (title, ex), "ERROR")
            return False, "%s 失败" % title

    def _open_local(self, path, select_file: bool = False):
        if not path or not Path(path).exists():
            self.log("路径不存在 %s" % path, "WARN")
            return False, "路径不存在：%s" % path
        ok, msg = open_path(path, select_file=select_file)
        self.log(("打开 %s" % path) if ok else ("打开失败 %s: %s" % (path, msg)), "INFO" if ok else "ERROR")
        return ok, msg

    def _run_key(self, name, cmd, on):
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
            self.log("自启设置失败 %s" % ex, "ERROR")
            return False

    def _ariang_dir(self):
        cands = [
            Path(str((self.cfg.get("ariang") or {}).get("dir") or "")),
            ROOT / "ariaNg",
            ROOT / "ariang",
            APP_DIR / "ariaNg",
            APP_DIR / "ariang",
        ]
        for d in cands:
            try:
                if (d / "index.html").is_file():
                    return d
            except Exception:
                pass
        return None

    def _ariang_url(self):
        import base64
        token = read_secret(self.cfg["aria2"]["secret"])
        rpc_host = self.cfg["aria2"].get("host") or "127.0.0.1"
        rpc_port = int(self.cfg["aria2"].get("port") or 6800)
        if self._ariang_dir() is not None:
            base_url = "/ariang/index.html"
        else:
            port = int((self.cfg.get("ariang") or {}).get("port") or 16800)
            base_url = "http://127.0.0.1:%d/" % port
        if token:
            b64 = base64.b64encode(token.encode("utf-8")).decode("ascii")
            return "%s#!/settings/rpc/set/http/%s/%d/jsonrpc/%s" % (base_url, rpc_host, rpc_port, b64)
        return base_url

    def _qbit_url(self):
        return "http://%s:%d/" % (self.cfg["qbit"]["host"], int(self.cfg["qbit"]["port"]))

    def _find_ytdlp(self):
        cands = [
            APP_DIR / "tools" / ("yt-dlp.exe" if IS_WIN else "yt-dlp"),
            ROOT / "tools" / ("yt-dlp.exe" if IS_WIN else "yt-dlp"),
            DL_HOME / "ytdlp" / ("yt-dlp.exe" if IS_WIN else "yt-dlp"),
        ]
        for c in cands:
            try:
                if c.is_file():
                    return str(c)
            except Exception:
                pass
        found = shutil.which("yt-dlp")
        return found or ""

    def _find_ffmpeg(self):
        cands = [
            APP_DIR / "tools" / "ffmpeg" / "bin" / ("ffmpeg.exe" if IS_WIN else "ffmpeg"),
            ROOT / "tools" / "ffmpeg" / "bin" / ("ffmpeg.exe" if IS_WIN else "ffmpeg"),
        ]
        for c in cands:
            try:
                if c.is_file():
                    return str(c.parent)
            except Exception:
                pass
        found = shutil.which("ffmpeg")
        return str(Path(found).parent) if found else ""

    def _find_video2x(self):
        env = (os.environ.get("VIDEO2X_PATH") or "").strip()
        if env and Path(env).is_file():
            return env
        cands = [
            ROOT / "tools" / "video2x" / ("video2x.exe" if IS_WIN else "video2x"),
            APP_DIR / "tools" / "video2x" / ("video2x.exe" if IS_WIN else "video2x"),
        ]
        for c in cands:
            try:
                if c.is_file():
                    return str(c)
            except Exception:
                pass
        return shutil.which("video2x") or ""

    @staticmethod
    def _clean_video_url(raw: str) -> str:
        import re
        s = (raw or "").strip()
        m = re.search(r"https?://[^\s\"'<>，。；！）)】》」]+", s)
        return m.group(0).rstrip(".,;!?）)】》」") if m else s

    @staticmethod
    def _is_cn_video_host(url: str) -> bool:
        from urllib.parse import urlsplit
        h = (urlsplit(url).hostname or "").lower().rstrip(".")
        cn = ("douyin.com", "iesdouyin.com", "bilibili.com", "b23.tv",
              "xiaohongshu.com", "xhslink.com", "kuaishou.com", "ixigua.com",
              "weibo.com", "weibo.cn", "youku.com", "iqiyi.com", "qq.com", "acfun.cn")
        return any(h == d or h.endswith("." + d) for d in cn)

    @staticmethod
    def _is_douyin_url(url: str) -> bool:
        from urllib.parse import urlsplit
        h = (urlsplit(url).hostname or "").lower().rstrip(".")
        return h in ("douyin.com", "iesdouyin.com", "v.douyin.com") or h.endswith(".douyin.com") or h.endswith(".iesdouyin.com")

    @staticmethod
    def _is_xhs_url(url: str) -> bool:
        from urllib.parse import urlsplit
        h = (urlsplit(url).hostname or "").lower().rstrip(".")
        return h in ("xiaohongshu.com", "xhslink.com") or h.endswith(".xiaohongshu.com") or h.endswith(".xhslink.com")

    def _find_local_cookies_txt(self, explicit: str = "") -> str:
        cands = []
        if explicit:
            cands.append(Path(explicit))
        cands.append(PANEL_DIR / "cookies.txt")
        ini = (self.cfg.get("yt") or {}).get("ini") or ""
        if ini:
            cands.append(Path(ini).parent / "cookies.txt")
        for c in cands:
            try:
                if c.is_file() and c.stat().st_size > 20:
                    return str(c)
            except Exception:
                pass
        return ""

    def _find_external_douyin_kernel(self):
        ini = (self.cfg.get("yt") or {}).get("ini") or ""
        cands = []
        if ini:
            cands.append(Path(ini).parent / "douyin_download.py")
        bat = (self.cfg.get("yt") or {}).get("bat") or ""
        if bat:
            cands.append(Path(bat).parent / "douyin_download.py")
        cands.append(PANEL_DIR / "douyin_download.py")
        for c in cands:
            try:
                if c.is_file():
                    return c
            except Exception:
                pass
        return None

    def _yt_append_log(self, line: str):
        ts = datetime.now().strftime("%H:%M:%S")
        with self.lock:
            self.yt_job["logs"].append("%s %s" % (ts, line))
            if len(self.yt_job["logs"]) > 200:
                self.yt_job["logs"] = self.yt_job["logs"][-200:]

    def _stream_direct_file(self, media_url: str, out_file: Path, referer: str = "", use_proxy: bool = False) -> bool:
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        }
        if referer:
            headers["Referer"] = referer
        proxies = None
        if use_proxy:
            px = self._sys_proxy()
            if px:
                proxies = {"http": px, "https": px}
        else:
            proxies = {"http": None, "https": None}
        r = requests.get(media_url, headers=headers, proxies=proxies, stream=True, timeout=25)
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        t0 = time.time()
        with open(out_file, "wb") as f:
            for chunk in r.iter_content(chunk_size=131072):
                if not chunk:
                    continue
                with self.lock:
                    if not self.yt_job.get("running"):
                        return False
                f.write(chunk)
                done += len(chunk)
                dt = max(0.05, time.time() - t0)
                spd = done / dt
                pct = (done / total * 100.0) if total > 0 else min(95.0, done / (1024 * 1024) * 5.0)
                with self.lock:
                    self.yt_job["pct"] = round(min(99.5, pct), 1)
                    self.yt_job["speed"] = hspeed(spd)
                    self.yt_job["eta"] = ("%02d:%02d" % (int((total - done) / spd) // 60, int((total - done) / spd) % 60)) if (total > done and spd > 1) else "-"
        return out_file.is_file() and out_file.stat().st_size > 10240

    def _download_douyin_smart(self, url: str, out_dir: Path, upscale: bool):
        """抖音专用双保险引擎：优先本地 douyin_download.py（无头高清封装），回退内置移动端直链解析。"""
        import re
        kernel = self._find_external_douyin_kernel()
        if kernel is not None:
            self._yt_append_log("[INFO] 检测到本地抖音高清内核：%s，正在解析最高画质流…" % kernel.name)
            with self.lock:
                self.yt_job["status"] = "解析抖音高清流…"
            runner = (
                "import os, sys, subprocess\n"
                "sys.path.insert(0, os.environ['DS_DY_DIR'])\n"
                "from douyin_download import resolve_video_url, download_command\n"
                "u = resolve_video_url(os.environ['DS_DY_URL'])\n"
                "print('[INFO] 已解析目标地址', flush=True)\n"
                "cmd = download_command(u)\n"
                "print('[INFO] 启动封装下载…', flush=True)\n"
                "rc = subprocess.call(cmd, cwd=os.environ['DS_DY_DIR'])\n"
                "sys.exit(rc)\n"
            )
            env = os.environ.copy()
            env["DS_DY_DIR"] = str(kernel.parent)
            env["DS_DY_URL"] = url
            env["YTSHELL_OUTPUT"] = str(out_dir)
            env["UPSCALE"] = "1" if upscale else "0"
            env["PYTHONUTF8"] = "1"
            for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
                env.pop(k, None)
            proc = subprocess.Popen(
                [sys.executable, "-u", "-B", "-c", runner],
                cwd=str(kernel.parent), env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                **_popen_kwargs()
            )
            with self.lock:
                self.yt_job["pid"] = proc.pid
                self.yt_job["status"] = "抖音高清解析与下载中…"
            self.pids["yt_job"] = proc.pid
            save_pids(self.pids)
            pct_re = re.compile(r"(\d+(?:\.\d+)?)%")
            assert proc.stdout is not None
            for raw in proc.stdout:
                line = raw.strip()
                if not line:
                    continue
                m = pct_re.search(line)
                if m:
                    with self.lock:
                        self.yt_job["pct"] = float(m.group(1))
                self._yt_append_log(line)
            rc = proc.wait()
            if rc == 0:
                return True, str(out_dir)
            self._yt_append_log("[WARN] 本地抖音内核退出码 %s，自动切换内置移动端直链回退…" % rc)

        # 内置通用抖音移动端分享页解析（不依赖任何外部脚本、无需登录、不锁 Edge Cookie）
        self._yt_append_log("[INFO] 启用内置抖音直链解析（免代理直连）…")
        with self.lock:
            self.yt_job["status"] = "内置解析抖音直链…"
        s = requests.Session()
        s.proxies = {"http": None, "https": None}
        ua_mob = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        r0 = s.get(url, headers={"User-Agent": ua_mob}, allow_redirects=True, timeout=15)
        m_id = re.search(r"/(?:share/)?video/(\d{6,})", r0.url or url)
        if not m_id:
            m_id = re.search(r'"aweme_id"\s*:\s*"(\d{6,})"', r0.text or "")
        if not m_id:
            self._yt_append_log("[ERROR] 未能从链接提取抖音视频 ID")
            return False, ""
        aweme_id = m_id.group(1)
        share_url = "https://www.iesdouyin.com/share/video/%s/" % aweme_id
        r1 = s.get(share_url, headers={"User-Agent": ua_mob, "Referer": "https://www.iesdouyin.com/"}, timeout=15)
        html = r1.text or ""
        play_url = ""
        title = "douyin_" + aweme_id
        m_rd = re.search(r"window\._ROUTER_DATA\s*=\s*(\{.*?\})\s*</script>", html, re.S)
        if m_rd:
            try:
                jd = json.loads(m_rd.group(1))
                txt = json.dumps(jd, ensure_ascii=False)
                m_desc = re.search(r'"desc"\s*:\s*"([^"]{1,80})"', txt)
                if m_desc:
                    safe = re.sub(r'[\\/:*?"<>|\r\n]+', "_", m_desc.group(1)).strip(" ._")
                    if safe:
                        title = safe[:60] + "_" + aweme_id[-6:]
                m_u = re.search(r'"play_addr"\s*:\s*\{[^}]*"url_list"\s*:\s*\[\s*"([^"]+)"', txt)
                if m_u:
                    play_url = m_u.group(1).replace("playwm", "play")
            except Exception:
                pass
        if not play_url:
            m_u2 = re.search(r'https://[^"\'\\]+playwm[^"\'\\]+', html)
            if m_u2:
                play_url = m_u2.group(0).replace("\\u002F", "/").replace("playwm", "play")
        if not play_url:
            self._yt_append_log("[ERROR] 抖音页面未返回公开直链（该作品可能受限）")
            return False, ""
        out_file = out_dir / (title + ".mp4")
        with self.lock:
            self.yt_job["status"] = "下载抖音无水印视频…"
            self.yt_job["file"] = str(out_file)
        self._yt_append_log("[INFO] 命中抖音直链 → %s" % out_file.name)
        ok = self._stream_direct_file(play_url, out_file, referer="https://www.douyin.com/", use_proxy=False)
        return ok, str(out_file)

    def _download_xhs_fallback(self, url: str, out_dir: Path):
        """小红书公开视频直链回退解析（免代理直连）。"""
        import re
        self._yt_append_log("[INFO] 启用内置小红书视频直链回退解析…")
        s = requests.Session()
        s.proxies = {"http": None, "https": None}
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        r = s.get(url, headers={"User-Agent": ua}, allow_redirects=True, timeout=15)
        html = r.text or ""
        m_v = re.search(r'"masterUrl"\s*:\s*"(https?://[^"]+)"', html)
        if not m_v:
            m_v = re.search(r'https?://sns-video[^"\'\\\s]+\.mp4[^"\'\\\s]*', html)
        if not m_v:
            return False, ""
        vurl = m_v.group(1 if m_v.lastindex else 0).replace("\\u002F", "/").replace("\\/", "/")
        out_file = out_dir / ("xhs_%s.mp4" % datetime.now().strftime("%Y%m%d_%H%M%S"))
        with self.lock:
            self.yt_job["status"] = "下载小红书视频…"
            self.yt_job["file"] = str(out_file)
        ok = self._stream_direct_file(vurl, out_file, referer="https://www.xiaohongshu.com/", use_proxy=False)
        return ok, str(out_file)

    def _exec_ytdlp_once(self, ytdlp: str, url: str, quality: str, out_dir: Path,
                         cookie_args: list, extra_args: list, use_proxy: bool):
        import re
        cmd = [ytdlp, "--newline", "--progress", "--no-color", "-P", str(out_dir)]
        ff_dir = self._find_ffmpeg()
        if ff_dir:
            cmd += ["--ffmpeg-location", ff_dir]
        q_norm = str(quality or "best").strip().lower()
        if q_norm in ("1080", "1080p"):
            cmd += ["-f", "bv*[height<=1080]+ba/b[height<=1080]/best", "-S", "res:1080,fps,vbr", "--merge-output-format", "mp4"]
        elif q_norm in ("720", "720p"):
            cmd += ["-f", "bv*[height<=720]+ba/b[height<=720]/best", "-S", "res:720,fps,vbr", "--merge-output-format", "mp4"]
        elif q_norm in ("audio", "mp3"):
            cmd += ["-x", "--audio-format", "mp3", "--audio-quality", "0"]
        else:
            # 优先拉取源站真实最高分辨率（2160p/4K AV1/VP9/HEVC），避免因强限 H.264 悄悄降级到 1080p
            cmd += [
                "-f", "bv*+ba/best",
                "-S", "res:2160,hdr:12,fps,vbr,abr",
                "--merge-output-format", "mp4",
            ]
        if "bilibili.com" in url.lower() or "b23.tv" in url.lower():
            cmd += ["--add-header", "Referer:https://www.bilibili.com/"]
        cmd += cookie_args + extra_args + [url]

        env = os.environ.copy()
        px = self._sys_proxy() if use_proxy else ""
        if px:
            env["HTTP_PROXY"] = env["HTTPS_PROXY"] = env["http_proxy"] = env["https_proxy"] = px
            env.pop("ALL_PROXY", None)
            env.pop("all_proxy", None)
            env["NO_PROXY"] = env["no_proxy"] = "localhost,127.0.0.1,::1,.local"
        else:
            for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
                env.pop(k, None)

        pct_re = re.compile(r"(\d+(?:\.\d+)?)%")
        spd_re = re.compile(r"at\s+([^\s]+/s)")
        eta_re = re.compile(r"ETA\s+([0-9:]+)")
        dest_re = re.compile(r"(?:Destination:|Merging formats into\s+\"?|\[download\]\s+)(.+?)(?:\"\s*$|\s+has already been downloaded\s*$|$)")

        proc = subprocess.Popen(
            cmd, cwd=str(out_dir), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            **_popen_kwargs()
        )
        with self.lock:
            self.yt_job["pid"] = proc.pid
            self.yt_job["status"] = "下载中…"
        self.pids["yt_job"] = proc.pid
        save_pids(self.pids)
        self._yt_append_log("[INFO] yt-dlp PID=%s（画质=%s | 线路=%s）" % (proc.pid, quality, ("代理 " + px) if px else "直连"))

        last_file = ""
        err_text = []
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.strip()
            if not line:
                continue
            m_pct = pct_re.search(line)
            if m_pct and "[download]" in line:
                m_spd = spd_re.search(line)
                m_eta = eta_re.search(line)
                with self.lock:
                    self.yt_job["pct"] = float(m_pct.group(1))
                    if m_spd:
                        self.yt_job["speed"] = m_spd.group(1)
                    if m_eta:
                        self.yt_job["eta"] = m_eta.group(1)
                continue
            m_dst = dest_re.search(line)
            if m_dst and ("Destination:" in line or "Merging formats into" in line or "has already been downloaded" in line):
                cand = m_dst.group(1).strip().strip('"')
                if cand:
                    last_file = cand
                    with self.lock:
                        self.yt_job["file"] = cand
            if "ERROR:" in line or "WARNING:" in line:
                err_text.append(line)
            self._yt_append_log(line)
        rc = proc.wait()
        return rc, last_file, "\n".join(err_text)

    def _run_yt_worker(self, url: str, quality: str, cookies: str, cookies_file: str, upscale: bool):
        out_dir = Path(self.yt_output())
        out_dir.mkdir(parents=True, exist_ok=True)
        last_file = ""
        ok_dl = False
        try:
            self.log("YT 工坊开始下载：%s" % url[:80], "OK")
            # 1) 抖音链接：直接走双保险抖音引擎（免 403、免 Edge 锁库）
            if self._is_douyin_url(url) and quality != "audio":
                ok_dl, last_file = self._download_douyin_smart(url, out_dir, upscale)
                if ok_dl:
                    with self.lock:
                        self.yt_job["pct"] = 100.0
                        self.yt_job["status"] = "下载完成 ✔"
                    self._recent_ts = 0.0
                    self._yt_append_log("[OK] 抖音视频下载完成 → %s" % (last_file or out_dir))
                    self.log("YT 工坊抖音下载完成 → %s" % (last_file or out_dir), "OK")
                    return

            # 2) 全平台 yt-dlp 智能多轮策略（国内站默认直连，海外站默认走代理）
            ytdlp = self._find_ytdlp()
            if not ytdlp:
                with self.lock:
                    self.yt_job["status"] = "未检测到 yt-dlp"
                self._yt_append_log("[ERROR] 未找到 yt-dlp，请先运行一键配置安装")
                return

            is_cn = self._is_cn_video_host(url)
            use_proxy = not is_cn
            local_ck = self._find_local_cookies_txt(cookies_file)
            cookie_args = []
            if cookies in ("firefox", "chrome", "edge"):
                cookie_args = ["--cookies-from-browser", cookies]
            elif cookies == "file" and local_ck:
                cookie_args = ["--cookies", local_ck]
            elif cookies == "auto" and local_ck:
                cookie_args = ["--cookies", local_ck]
                self._yt_append_log("[INFO] 自动加载本地 cookies.txt")

            rc, last_file, err_txt = self._exec_ytdlp_once(ytdlp, url, quality, out_dir, cookie_args, [], use_proxy)

            # Edge / Chrome 锁库自动救援
            if rc != 0 and "Could not copy Chrome cookie database" in err_txt:
                self._yt_append_log("[WARN] 检测到 Edge/Chrome 运行时独占锁定 Cookie 库，自动切换免锁库智能回退…")
                fallback_ck = ["--cookies", local_ck] if local_ck else []
                rc, last_file, err_txt = self._exec_ytdlp_once(ytdlp, url, quality, out_dir, fallback_ck, [], use_proxy)

            # YouTube 风控自动切 android/web 客户端重试
            if rc != 0 and ("youtube.com" in url.lower() or "youtu.be" in url.lower()):
                self._yt_append_log("[WARN] YouTube 常规解析受限，自动切换 android/web 客户端重试…")
                rc, last_file, err_txt = self._exec_ytdlp_once(
                    ytdlp, url, quality, out_dir, cookie_args if "Could not copy" not in err_txt else [],
                    ["--extractor-args", "youtube:player_client=android,web"], use_proxy
                )

            # 代理/直连智能反向重试一次（例如网络环境差异）
            if rc != 0 and self._sys_proxy():
                with self.lock:
                    canceled = (self.yt_job["status"] == "已取消")
                if not canceled and any(k in err_txt for k in ("Unable to download", "timed out", "Connection", "Proxy", "403")):
                    alt_proxy = not use_proxy
                    self._yt_append_log("[WARN] 自动切换%s线路重试…" % ("代理" if alt_proxy else "直连"))
                    rc, last_file, err_txt = self._exec_ytdlp_once(
                        ytdlp, url, quality, out_dir,
                        (["--cookies", local_ck] if local_ck else []), [], alt_proxy
                    )

            # 小红书内置直链回退
            if rc != 0 and self._is_xhs_url(url):
                ok_xhs, xhs_file = self._download_xhs_fallback(url, out_dir)
                if ok_xhs:
                    rc, last_file = 0, xhs_file

            if rc == 0:
                res_note = ""
                if last_file and Path(last_file).is_file() and quality not in ("audio", "mp3"):
                    try:
                        ff_dir = self._find_ffmpeg()
                        ffprobe = str(Path(ff_dir) / ("ffprobe.exe" if IS_WIN else "ffprobe")) if ff_dir else (shutil.which("ffprobe") or "")
                        if ffprobe and Path(ffprobe).is_file():
                            pr = subprocess.run(
                                [ffprobe, "-v", "error", "-select_streams", "v:0",
                                 "-show_entries", "stream=width,height,codec_name",
                                 "-of", "csv=p=0", last_file],
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=6, **_popen_kwargs()
                            )
                            parts = [x.strip() for x in (pr.stdout or "").strip().split(",") if x.strip()]
                            if len(parts) >= 2:
                                vw, vh = int(parts[0]), int(parts[1])
                                vc = parts[2] if len(parts) >= 3 else ""
                                tag = "真4K" if max(vw, vh) >= 3600 else ("2K" if max(vw, vh) >= 2400 else ("1080P" if max(vw, vh) >= 1800 else f"{vh}P"))
                                res_note = "（实测 %dx%d %s · %s）" % (vw, vh, vc, tag)
                                self._yt_append_log("[OK] 实测成品画质：%dx%d (%s) → %s" % (vw, vh, vc, tag))
                                if max(vw, vh) < 1800 and ("bilibili.com" in url.lower() or "youtube.com" in url.lower()):
                                    self._yt_append_log("[WARN] 当前实测低于 1080P：可能是源视频本身最高如此，或 B站/YouTube 需要选择浏览器 Cookies 登录态才能解锁 1080P+/真4K")
                    except Exception:
                        pass
                with self.lock:
                    self.yt_job["pct"] = 100.0
                    self.yt_job["status"] = "下载完成 ✔" + res_note
                self._recent_ts = 0.0
                self._yt_append_log("[OK] 下载完成 → %s" % (last_file or out_dir))
                self.log("YT 工坊下载完成%s → %s" % (res_note, last_file or out_dir), "OK")
                if upscale and quality != "audio":
                    v2x = self._find_video2x()
                    if last_file and Path(last_file).is_file():
                        with self.lock:
                            self.yt_job["status"] = "2x AI 超分中（GPU 加速）…"
                        src_p = Path(last_file)
                        out_up = str(src_p.with_stem(src_p.stem + "_2x"))
                        tmp_up = str(src_p.with_name(src_p.stem + "_2x.tmp.mp4"))
                        ff_dir = self._find_ffmpeg()
                        ffmpeg_exe = str(Path(ff_dir) / ("ffmpeg.exe" if IS_WIN else "ffmpeg")) if ff_dir else (shutil.which("ffmpeg") or "")
                        ffprobe_exe = str(Path(ff_dir) / ("ffprobe.exe" if IS_WIN else "ffprobe")) if ff_dir else (shutil.which("ffprobe") or "")

                        def _probe_wh(fp: str):
                            if not ffprobe_exe or not Path(fp).is_file() or Path(fp).stat().st_size < 4096:
                                return 0, 0
                            try:
                                r_p = subprocess.run(
                                    [ffprobe_exe, "-v", "error", "-select_streams", "v:0",
                                     "-show_entries", "stream=width,height", "-of", "csv=p=0", fp],
                                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                                    timeout=6, **_popen_kwargs()
                                )
                                pts = [x.strip() for x in (r_p.stdout or "").strip().split(",") if x.strip()]
                                if len(pts) >= 2:
                                    return int(pts[0]), int(pts[1])
                            except Exception:
                                pass
                            return 0, 0

                        sw, sh = _probe_wh(last_file)
                        tw = min(3840, (sw * 2) if sw > 0 else 1920)
                        th = min(2160, (sh * 2) if sh > 0 else 1080)
                        tw -= tw % 2
                        th -= th % 2

                        def _run_upscale_cmd(cmd_args, label: str) -> bool:
                            self._yt_append_log("[INFO] %s → 目标 %dx%d：%s" % (label, tw, th, src_p.name))
                            try:
                                if Path(tmp_up).is_file():
                                    Path(tmp_up).unlink(missing_ok=True)
                            except Exception:
                                pass
                            up_proc = subprocess.Popen(
                                cmd_args, cwd=str(out_dir),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace",
                                **_popen_kwargs()
                            )
                            with self.lock:
                                self.yt_job["pid"] = up_proc.pid
                            if up_proc.stdout is not None:
                                for uln in up_proc.stdout:
                                    tln = uln.strip()
                                    if tln and any(k in tln.lower() for k in ("error", "warn", "fps", "frame=", "completed", "vulkan", "nvenc")):
                                        self._yt_append_log("[V2X] %s" % tln[:180])
                            rc_u = up_proc.wait()
                            ow, oh = _probe_wh(tmp_up)
                            if ow >= max(640, sw) and oh >= max(360, sh):
                                os.replace(tmp_up, out_up)
                                return True
                            try:
                                if Path(tmp_up).is_file():
                                    Path(tmp_up).unlink(missing_ok=True)
                            except Exception:
                                pass
                            self._yt_append_log("[WARN] %s 未产出有效文件（退出码 %s），尝试备用 GPU 管线…" % (label, rc_u))
                            return False

                        up_ok = False
                        if v2x:
                            # Tier 1: Video2X v6 Vulkan libplacebo (Anime4K v4) + RTX h264_nvenc（强制 yuv420p 确保站内影院 100% 兼容）
                            up_ok = _run_upscale_cmd([
                                v2x, "-i", last_file, "-o", tmp_up,
                                "-w", str(tw), "-h", str(th),
                                "-p", "libplacebo", "--libplacebo-shader", "anime4k-v4-a+a",
                                "-d", "0", "-c", "h264_nvenc", "--pix-fmt", "yuv420p",
                                "-e", "cq=18", "-e", "preset=p5", "--no-progress",
                            ], "Video2X Vulkan AI (NVENC)")
                            # Tier 2: 非 N 卡环境回退 libx264 编码
                            if not up_ok:
                                up_ok = _run_upscale_cmd([
                                    v2x, "-i", last_file, "-o", tmp_up,
                                    "-w", str(tw), "-h", str(th),
                                    "-p", "libplacebo", "--libplacebo-shader", "anime4k-v4-a+a",
                                    "-c", "libx264", "--pix-fmt", "yuv420p",
                                    "-e", "crf=18", "-e", "preset=fast", "--no-progress",
                                ], "Video2X Vulkan AI (x264)")
                        # Tier 3: FFmpeg 硬件 Lanczos 2x + CAS 锐化兜底（100% 稳定兜底）
                        if not up_ok and ffmpeg_exe:
                            vf = "scale=%d:%d:flags=lanczos,cas=0.45" % (tw, th)
                            for enc_name, enc_args in (
                                ("FFmpeg NVENC 2x+CAS", ["-c:v", "h264_nvenc", "-cq", "18", "-preset", "p5", "-pix_fmt", "yuv420p"]),
                                ("FFmpeg x264 2x+CAS",  ["-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p"]),
                            ):
                                up_ok = _run_upscale_cmd(
                                    [ffmpeg_exe, "-y", "-i", last_file, "-vf", vf]
                                    + enc_args + ["-c:a", "copy", "-movflags", "+faststart", tmp_up],
                                    enc_name,
                                )
                                if up_ok:
                                    break
                        if up_ok:
                            ow, oh = _probe_wh(out_up)
                            with self.lock:
                                self.yt_job["file"] = out_up
                                self.yt_job["status"] = "2x AI 超分完成 ✔（%dx%d）" % (ow or tw, oh or th)
                            self._recent_ts = 0.0
                            self._yt_append_log("[OK] 2x AI 超分完成（实测 %dx%d）→ %s" % (ow or tw, oh or th, out_up))
                        else:
                            with self.lock:
                                self.yt_job["status"] = "下载完成（超分已跳过）"
                            self._yt_append_log("[WARN] 超分管线全部未通过，已完整保留原始高清视频：%s" % last_file)
                    else:
                        self._yt_append_log("[WARN] 未检测到目标视频文件，已跳过 2x 超分")
            else:
                with self.lock:
                    if self.yt_job["status"] != "已取消":
                        self.yt_job["status"] = "下载失败 (码 %s)" % rc
                self._yt_append_log("[ERROR] 下载失败（若为需登录站点，建议导出 cookies.txt 或使用 Firefox 登录态，避免 Edge/Chrome 锁库）")
        except Exception as ex:
            with self.lock:
                self.yt_job["status"] = "执行异常"
            self._yt_append_log("[ERROR] %s" % ex)
        finally:
            self.pids.pop("yt_job", None)
            save_pids(self.pids)
            with self.lock:
                self.yt_job["running"] = False
                self.yt_job["pid"] = None

    def _music_append_log(self, line: str):
        ts = datetime.now().strftime("%H:%M:%S")
        with self.lock:
            self.music_job["logs"].append("%s %s" % (ts, line))
            if len(self.music_job["logs"]) > 180:
                self.music_job["logs"] = self.music_job["logs"][-180:]

    def _voice_append_log(self, line: str):
        ts = datetime.now().strftime("%H:%M:%S")
        with self.lock:
            self.voice_job["logs"].append("%s %s" % (ts, line))
            if len(self.voice_job["logs"]) > 220:
                self.voice_job["logs"] = self.voice_job["logs"][-220:]

    def _run_music_worker(self, url: str, query: str, title: str, artist: str, fmt: str, out_dir_str: str):
        import re
        out_dir = Path(out_dir_str or self.music_output())
        out_dir.mkdir(parents=True, exist_ok=True)
        fmt = fmt if fmt in ("mp3", "flac", "wav", "m4a") else "mp3"
        t_start = time.time()
        try:
            ytdlp = self._find_ytdlp()
            if not ytdlp:
                with self.lock:
                    self.music_job["status"] = "未检测到 yt-dlp"
                self._music_append_log("[ERROR] 未检测到 yt-dlp，请先运行一键配置安装")
                return
            ff_dir = self._find_ffmpeg()
            px = self._sys_proxy()
            targets = MS.build_music_download_targets(url, query, bool(px)) if MS else ([(url, bool(px), "直链音源")] if url else [])
            if not targets:
                with self.lock:
                    self.music_job["status"] = "未找到可用音源"
                self._music_append_log("[ERROR] 未能匹配到可下载的音源，请换个关键词重试")
                return

            safe_stem = ""
            if title and MS:
                raw_name = ("%s - %s" % (artist, title)) if (artist and artist not in ("未知歌手", "B站音乐", "YouTube")) else title
                safe_stem = MS._safe_filename(raw_name, "song")

            pct_re = re.compile(r"(\d+(?:\.\d+)?)%")
            spd_re = re.compile(r"at\s+([^\s]+/s)")
            eta_re = re.compile(r"ETA\s+([0-9:]+)")
            dst_re = re.compile(r"(?:\[ExtractAudio\]\s*Destination:|Destination:)\s*(.+)$")

            final_file = ""
            ok = False
            for idx, (target_url, use_proxy, label) in enumerate(targets):
                with self.lock:
                    if not self.music_job.get("running"):
                        return
                    self.music_job["status"] = "尝试 %s (%d/%d)…" % (label, idx + 1, len(targets))
                    self.music_job["pct"] = 0.0
                self._music_append_log("[INFO] 音源[%s]：%s" % (label, target_url))

                cmd = [ytdlp, "--newline", "--progress", "--no-color", "--no-playlist",
                       "-P", str(out_dir), "-x", "--audio-format", fmt, "--audio-quality", "0", "--add-metadata"]
                if ff_dir:
                    cmd += ["--ffmpeg-location", ff_dir]
                    if fmt in ("mp3", "m4a", "flac"):
                        cmd += ["--embed-thumbnail"]
                if safe_stem:
                    cmd += ["-o", safe_stem + ".%(ext)s"]
                else:
                    cmd += ["-o", "%(title).70s.%(ext)s"]
                if "bilibili.com" in target_url.lower() or "b23.tv" in target_url.lower():
                    cmd += ["--add-header", "Referer:https://www.bilibili.com/"]
                elif "youtube" in target_url.lower() or target_url.startswith("ytsearch"):
                    cmd += ["--extractor-args", "youtube:player_client=android,web"]
                cmd.append(target_url)

                env = os.environ.copy()
                if use_proxy and px:
                    env["HTTP_PROXY"] = env["HTTPS_PROXY"] = env["http_proxy"] = env["https_proxy"] = px
                    env.pop("ALL_PROXY", None)
                    env.pop("all_proxy", None)
                    env["NO_PROXY"] = env["no_proxy"] = "localhost,127.0.0.1,::1,.local"
                else:
                    for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
                        env.pop(k, None)

                proc = subprocess.Popen(
                    cmd, cwd=str(out_dir), env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    **_popen_kwargs()
                )
                with self.lock:
                    self.music_job["pid"] = proc.pid
                self.pids["music_job"] = proc.pid
                save_pids(self.pids)

                last_dst = ""
                assert proc.stdout is not None
                for raw in proc.stdout:
                    line = raw.strip()
                    if not line:
                        continue
                    m_p = pct_re.search(line)
                    if m_p and "[download]" in line:
                        m_s = spd_re.search(line)
                        m_e = eta_re.search(line)
                        with self.lock:
                            self.music_job["pct"] = float(m_p.group(1))
                            if m_s:
                                self.music_job["speed"] = m_s.group(1)
                            if m_e:
                                self.music_job["eta"] = m_e.group(1)
                        continue
                    m_d = dst_re.search(line)
                    if m_d:
                        cand = m_d.group(1).strip().strip('"')
                        if cand:
                            last_dst = cand
                    if "[ExtractAudio]" in line or "ERROR:" in line or "WARNING:" in line:
                        self._music_append_log(line)
                rc = proc.wait()
                if rc == 0:
                    ok = True
                    if safe_stem and (out_dir / ("%s.%s" % (safe_stem, fmt))).is_file():
                        final_file = str(out_dir / ("%s.%s" % (safe_stem, fmt)))
                    elif last_dst and Path(last_dst).is_file():
                        final_file = str(Path(last_dst).resolve())
                    else:
                        cands = sorted(
                            [f for f in out_dir.iterdir() if f.is_file() and f.suffix.lower() in (".mp3", ".flac", ".wav", ".m4a", ".ogg", ".opus") and f.stat().st_mtime >= t_start - 3],
                            key=lambda x: x.stat().st_mtime, reverse=True
                        )
                        if cands:
                            final_file = str(cands[0].resolve())
                    break
                self._music_append_log("[WARN] 音源[%s]退出码 %s，自动切换下一候选音源…" % (label, rc))

            if ok:
                lyr = None
                if MS is not None:
                    try:
                        lyr = MS.fetch_song_lyrics(title=title or query, artist=artist, query=query)
                        if lyr and lyr.get("raw") and final_file:
                            try:
                                Path(final_file).with_suffix(".lrc").write_text(lyr["raw"], encoding="utf-8")
                            except Exception:
                                pass
                    except Exception:
                        lyr = None
                with self.lock:
                    self.music_job["pct"] = 100.0
                    self.music_job["status"] = "下载完成 ✔"
                    self.music_job["file"] = final_file
                    if lyr and lyr.get("lines"):
                        self.music_job["lyrics"] = lyr
                self._recent_ts = 0.0
                self._music_append_log("[OK] 歌曲已保存 → %s" % (final_file or out_dir))
                self.log("音乐工坊下载完成 → %s" % (Path(final_file).name if final_file else out_dir), "OK")
            else:
                with self.lock:
                    if self.music_job["status"] != "已取消":
                        self.music_job["status"] = "下载失败"
                self._music_append_log("[ERROR] 全部候选音源均失败，请换一个关键词或检查代理设置")
        except Exception as ex:
            with self.lock:
                self.music_job["status"] = "执行异常"
            self._music_append_log("[ERROR] %s" % ex)
        finally:
            self.pids.pop("music_job", None)
            save_pids(self.pids)
            with self.lock:
                self.music_job["running"] = False
                self.music_job["pid"] = None

    def _run_voice_install_f5_worker(self):
        try:
            if MS is None:
                self._voice_append_log("[ERROR] media_studio 模块缺失")
                return
            py312 = MS.find_compatible_py312()
            if not py312:
                with self.lock:
                    self.voice_job["status"] = "缺少 Python 3.10~3.12"
                self._voice_append_log("[ERROR] 未找到 Python 3.10~3.12（PyTorch CUDA 暂不支持 3.15），请安装 Python 3.12 后重试")
                return
            venv_dir = PANEL_DIR / ".venv-voice"
            vpy = MS.voice_venv_python(PANEL_DIR)
            gpu = MS.detect_gpu_name()
            has_nv = "NVIDIA" in gpu.upper()
            self._voice_append_log("[INFO] 检测到显卡：%s | 解释器：%s" % (gpu, py312))

            def _run_step(cmd, label):
                self._voice_append_log("[INFO] %s…" % label)
                with self.lock:
                    self.voice_job["status"] = label + "…"
                env = os.environ.copy()
                env["PYTHONUTF8"] = "1"
                px = self._sys_proxy()
                if px:
                    env["HTTP_PROXY"] = env["HTTPS_PROXY"] = env["http_proxy"] = env["https_proxy"] = px
                    env.pop("ALL_PROXY", None)
                    env.pop("all_proxy", None)
                proc = subprocess.Popen(
                    cmd, cwd=str(PANEL_DIR), env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    **_popen_kwargs()
                )
                with self.lock:
                    self.voice_job["pid"] = proc.pid
                self.pids["voice_job"] = proc.pid
                save_pids(self.pids)
                assert proc.stdout is not None
                for raw in proc.stdout:
                    line = raw.strip()
                    if line:
                        self._voice_append_log(line)
                return proc.wait()

            if not vpy.is_file():
                rc = _run_step([py312, "-m", "venv", str(venv_dir)], "创建独立隔离环境 .venv-voice")
                if rc != 0:
                    raise RuntimeError("创建 .venv-voice 失败 (码 %s)" % rc)

            with self.lock:
                self.voice_job["pct"] = 20.0
            _run_step([str(vpy), "-m", "pip", "install", "-U", "pip"], "升级 pip")

            with self.lock:
                self.voice_job["pct"] = 45.0
            if has_nv:
                rc = _run_step(
                    [str(vpy), "-m", "pip", "install", "torch", "torchaudio",
                     "--index-url", "https://download.pytorch.org/whl/cu124"],
                    "安装 PyTorch CUDA 12.4（RTX GPU 加速）"
                )
                if rc != 0:
                    rc = _run_step(
                        [str(vpy), "-m", "pip", "install", "torch", "torchaudio"],
                        "回退标准 PyPI 安装 PyTorch"
                    )
            else:
                rc = _run_step([str(vpy), "-m", "pip", "install", "torch", "torchaudio"], "安装 PyTorch (CPU)")
            if rc != 0:
                raise RuntimeError("PyTorch 安装失败 (码 %s)" % rc)

            with self.lock:
                self.voice_job["pct"] = 78.0
            rc = _run_step([str(vpy), "-m", "pip", "install", "f5-tts"], "安装开源顶尖 F5-TTS 引擎")
            if rc != 0:
                rc = _run_step(
                    [str(vpy), "-m", "pip", "install", "-i", "https://pypi.tuna.tsinghua.edu.cn/simple", "f5-tts"],
                    "切换清华镜像安装 F5-TTS"
                )
            if rc != 0:
                raise RuntimeError("f5-tts 安装失败 (码 %s)" % rc)

            self._voice_env_ts = 0.0
            with self.lock:
                self.voice_job["pct"] = 100.0
                self.voice_job["status"] = "F5-TTS 安装就绪 ✔"
            self._voice_append_log("[OK] F5-TTS 开源声音克隆引擎安装完成！现在上传 3~10 秒人声即可零样本克隆")
            self.log("F5-TTS 开源声音克隆引擎安装完成", "OK")
        except Exception as ex:
            with self.lock:
                self.voice_job["status"] = "安装失败"
            self._voice_append_log("[ERROR] %s" % ex)
        finally:
            self.pids.pop("voice_job", None)
            save_pids(self.pids)
            with self.lock:
                self.voice_job["installing"] = False
                self.voice_job["running"] = False
                self.voice_job["pid"] = None

    def _run_voice_synth_worker(self, engine: str, text: str, ref_text: str, voice_id: str,
                                rate: str, pitch: str, api_url: str, out_dir_str: str):
        out_dir = Path(out_dir_str or self.voice_output())
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snip = MS._safe_filename(text[:16], "voice") if MS else "voice"
        try:
            if MS is None:
                raise RuntimeError("media_studio 模块缺失")
            if engine == "edge":
                out_file = out_dir / ("tts_%s_%s.mp3" % (snip, stamp))
                with self.lock:
                    self.voice_job["status"] = "神经配音合成中…"
                    self.voice_job["pct"] = 35.0
                self._voice_append_log("[INFO] 使用神经音色 %s（语速 %s / 音调 %s）合成…" % (voice_id, rate, pitch))
                ok, msg = MS.run_edge_tts(text, voice_id, rate, pitch, out_file, proxy=self._sys_proxy())
                if not ok:
                    raise RuntimeError(msg)
                with self.lock:
                    self.voice_job["out_file"] = str(out_file.resolve())
                    self.voice_job["pct"] = 100.0
                    self.voice_job["status"] = "合成完成 ✔"
                self._recent_ts = 0.0
                self._voice_append_log("[OK] %s → %s" % (msg, out_file.name))
                self.log("声音工坊神经配音完成 → %s" % out_file.name, "OK")
                return

            with self.lock:
                ref_wav = self.voice_job.get("ref_wav") or ""
            if not ref_wav or not Path(ref_wav).is_file():
                raise RuntimeError("请先上传参考音频（3~15 秒清晰人声）或点击「🎙️ 麦克风录制」")

            if engine == "api":
                out_file = out_dir / ("clone_api_%s_%s.wav" % (snip, stamp))
                with self.lock:
                    self.voice_job["status"] = "调用外部开源克隆 API…"
                    self.voice_job["pct"] = 40.0
                self._voice_append_log("[INFO] 正在请求外部开源声音克隆 API：%s" % api_url)
                ok, msg = MS.run_external_clone_api(api_url, Path(ref_wav), ref_text, text, out_file)
                if not ok:
                    raise RuntimeError(msg)
                with self.lock:
                    self.voice_job["out_file"] = str(out_file.resolve())
                    self.voice_job["pct"] = 100.0
                    self.voice_job["status"] = "外部克隆完成 ✔"
                self._recent_ts = 0.0
                self._voice_append_log("[OK] %s → %s" % (msg, out_file.name))
                self.log("声音克隆完成（外部 API）→ %s" % out_file.name, "OK")
                return

            # engine == "f5"
            f5_cli = MS.voice_venv_f5cli(PANEL_DIR)
            cli_path = str(f5_cli) if f5_cli.is_file() else (shutil.which("f5-tts_infer-cli") or "")
            if not cli_path:
                raise RuntimeError("本机尚未安装 F5-TTS，请先点击「⚡ 一键部署 F5-TTS (CUDA)」或切换「⚡ 神经配音即用」")
            out_name = "clone_f5_%s_%s.wav" % (snip, stamp)
            out_file = out_dir / out_name
            cmd = [
                cli_path, "--model", "F5TTS_v1_Base",
                "--ref_audio", ref_wav,
                "--ref_text", ref_text,
                "--gen_text", text,
                "--output_dir", str(out_dir),
                "--output_file", out_name,
            ]
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            ff_dir = self._find_ffmpeg()
            if ff_dir:
                env["PATH"] = ff_dir + os.pathsep + env.get("PATH", "")
            px = self._sys_proxy()
            if px:
                env["HTTP_PROXY"] = env["HTTPS_PROXY"] = env["http_proxy"] = env["https_proxy"] = px
                env.pop("ALL_PROXY", None)
                env.pop("all_proxy", None)
            else:
                env.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

            self._voice_append_log("[INFO] 启动 F5-TTS 零样本声音克隆（首次运行将自动拉取 F5TTS_v1_Base 开源权重）…")
            with self.lock:
                self.voice_job["status"] = "F5-TTS 推理克隆中…"
                self.voice_job["pct"] = 25.0
            proc = subprocess.Popen(
                cmd, cwd=str(out_dir), env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                **_popen_kwargs()
            )
            with self.lock:
                self.voice_job["pid"] = proc.pid
            self.pids["voice_job"] = proc.pid
            save_pids(self.pids)
            assert proc.stdout is not None
            step_n = 0
            for raw in proc.stdout:
                line = raw.strip()
                if not line:
                    continue
                step_n += 1
                with self.lock:
                    self.voice_job["pct"] = min(94.0, 25.0 + step_n * 2.5)
                self._voice_append_log(line)
            rc = proc.wait()
            if rc == 0 and out_file.is_file() and out_file.stat().st_size > 1000:
                with self.lock:
                    self.voice_job["out_file"] = str(out_file.resolve())
                    self.voice_job["pct"] = 100.0
                    self.voice_job["status"] = "F5-TTS 克隆完成 ✔"
                self._recent_ts = 0.0
                self._voice_append_log("[OK] F5-TTS 声音克隆完成 → %s" % out_file.name)
                self.log("F5-TTS 声音克隆完成 → %s" % out_file.name, "OK")
            else:
                raise RuntimeError("F5-TTS 退出码 %s，请查看上方日志" % rc)
        except Exception as ex:
            with self.lock:
                if self.voice_job["status"] != "已取消":
                    self.voice_job["status"] = "合成失败"
            self._voice_append_log("[ERROR] %s" % ex)
        finally:
            self.pids.pop("voice_job", None)
            save_pids(self.pids)
            with self.lock:
                self.voice_job["running"] = False
                self.voice_job["pid"] = None

    def _aigc_append_log(self, line: str):
        ts = datetime.now().strftime("%H:%M:%S")
        with self.lock:
            self.aigc_job["logs"].append("%s %s" % (ts, line))
            if len(self.aigc_job["logs"]) > 180:
                self.aigc_job["logs"] = self.aigc_job["logs"][-180:]

    def _get_aigc_env_cached(self, force: bool = False):
        now = time.time()
        if force or self._aigc_env_cache is None or (now - self._aigc_env_ts) > 5.0:
            cc = self.cfg.get("comfyui") or {}
            owner_enabled = bool(cc.get("enabled"))
            url = str(cc.get("url") or "http://127.0.0.1:8188")
            root = str(cc.get("root") or "")
            bat = str(cc.get("start_bat") or "")
            srv = MS.probe_comfyui_server(url, timeout=1.2) if (MS and owner_enabled) else {"online": False, "url": url}
            models = MS.detect_comfyui_models(root, bat) if (MS and owner_enabled) else {"root_exists": False}
            custom_url = str(cc.get("custom_url") or "")
            custom_mode = str(cc.get("custom_mode") or "comfyui")
            custom_srv = (MS.probe_comfyui_server(custom_url, timeout=1.0)
                          if (MS and custom_mode == "comfyui" and custom_url)
                          else {"online": bool(custom_url)})
            self._aigc_env_cache = {
                "owner_enabled": owner_enabled,
                "server": srv,
                "models": models,
                "custom": {
                    "configured": bool(custom_url),
                    "mode": custom_mode,
                    "url": custom_url,
                    "model": str(cc.get("custom_model") or ""),
                    "has_key": bool((cc.get("custom_api_key") or "").strip()),
                    "has_workflow": bool((cc.get("custom_workflow_json") or "").strip()),
                    "online": bool(custom_srv.get("online")),
                },
            }
            self._aigc_env_ts = now
        return dict(self._aigc_env_cache)

    def _run_aigc_worker(self, engine: str, mode: str, prompt: str, neg_prompt: str,
                         width: int, height: int, steps: int, length: int, seed: int,
                         first_frame: str, out_dir_str: str):
        out_dir = Path(out_dir_str or self.aigc_output())
        out_dir.mkdir(parents=True, exist_ok=True)
        cc = self.cfg.get("comfyui") or {}
        try:
            if MS is None:
                raise RuntimeError("media_studio 模块缺失")

            def _prog(pct, st):
                with self.lock:
                    self.aigc_job["pct"] = round(float(pct), 1)
                    self.aigc_job["status"] = st

            def _canceled():
                with self.lock:
                    return bool(self.aigc_job.get("cancel"))

            if engine == "custom":
                cmode = str(cc.get("custom_mode") or "comfyui").strip().lower()
                curl = str(cc.get("custom_url") or "").strip()
                ckey = str(cc.get("custom_api_key") or "").strip()
                cmdl = str(cc.get("custom_model") or "").strip()
                cwf = str(cc.get("custom_workflow_json") or "").strip()
                if not curl:
                    raise RuntimeError("尚未配置自定义本地模型，请先点「🔌 接入我的本地模型」填入地址")
                if cmode in ("sdwebui", "openai_image"):
                    _prog(25.0, "正在调用自定义本地生图模型…")
                    self._aigc_append_log("[INFO] 调用自定义接口 [%s] → %s" % (cmode, curl))
                    ok, msg, saved = MS.run_custom_http_image_api(
                        cmode, curl, ckey, cmdl, prompt, neg_prompt, width, height, steps, out_dir
                    )
                else:
                    srv = MS.probe_comfyui_server(curl, timeout=2.0)
                    if not srv.get("online"):
                        raise RuntimeError("无法连接到自定义 ComfyUI：%s（请确认服务已启动）" % curl)
                    img_name = ""
                    if first_frame and Path(first_frame).is_file():
                        uok, ures = MS.comfyui_upload_image(curl, Path(first_frame))
                        if not uok:
                            raise RuntimeError(ures)
                        img_name = ures
                    if cwf:
                        wf = MS.apply_custom_comfy_workflow(cwf, prompt, neg_prompt, img_name, seed)
                    elif cmdl:
                        wf = MS.build_sd_checkpoint_t2i_workflow(cmdl, prompt, neg_prompt, width, height, steps, seed)
                    else:
                        raise RuntimeError("自定义 ComfyUI 模式请提供 API Workflow JSON 或 Checkpoint 模型名")
                    self._aigc_append_log("[INFO] 已提交自定义 ComfyUI 任务 → %s" % curl)
                    ok, msg, saved = MS.comfyui_queue_and_wait(curl, wf, out_dir, _prog, _canceled)
            else:
                if not cc.get("enabled"):
                    raise RuntimeError("本机未启用个人 ComfyUI，请点击「🔌 接入我的本地模型」接入你自己的模型")
                url = str(cc.get("url") or "http://127.0.0.1:8188")
                srv = MS.probe_comfyui_server(url, timeout=2.0)
                if not srv.get("online"):
                    self._aigc_append_log("[WARN] ComfyUI (%s) 未启动，尝试自动拉起本地 ComfyUI…" % url)
                    _prog(5.0, "正在拉起本地 ComfyUI 服务…")
                    ok_s, msg_s, _ = self.handle_action({"action": "aigc_start_comfy"})
                    if not ok_s:
                        raise RuntimeError("ComfyUI 未运行且自动拉起失败：%s" % msg_s)
                    for _i in range(45):
                        if _canceled():
                            raise RuntimeError("已取消任务")
                        time.sleep(2.0)
                        srv = MS.probe_comfyui_server(url, timeout=1.5)
                        if srv.get("online"):
                            break
                        _prog(min(18.0, 5.0 + _i * 0.3), "等待 ComfyUI 端口就绪 (%ds)…" % ((_i + 1) * 2))
                    if not srv.get("online"):
                        raise RuntimeError("等待 ComfyUI 启动超时，请查看 ComfyUI 窗口或稍后重试")

                models = MS.detect_comfyui_models(str(cc.get("root") or ""), str(cc.get("start_bat") or ""))
                vram_tot = float(srv.get("vram_total_gb") or 8.0)
                vram_free = float(srv.get("vram_free_gb") or 0.0)
                is_low_vram = (vram_tot <= 9.5)

                # 8G 显存自动防爆护栏：绝不允许模板或误填参数导致 CUDA OOM
                if is_low_vram:
                    if mode == "t2i":
                        if width * height > 600000:
                            old_wh = (width, height)
                            if width > height:
                                width, height = 896, 512
                            elif height > width:
                                width, height = 512, 896
                            else:
                                width, height = 768, 768
                            self._aigc_append_log("[WARN] 8G显存护栏：生图画幅 %dx%d → %dx%d 防爆显存" % (old_wh[0], old_wh[1], width, height))
                        if steps > 12:
                            steps = 8
                    else:
                        if width * height > 335000:
                            old_wh = (width, height)
                            width, height = (640, 384) if width >= height else (384, 640)
                            self._aigc_append_log("[WARN] 8G显存护栏：视频画幅 %dx%d → %dx%d 防爆显存" % (old_wh[0], old_wh[1], width, height))
                        if length > 25:
                            self._aigc_append_log("[WARN] 8G显存护栏：视频帧数 %d → 21 帧防爆显存" % length)
                            length = 21
                        if vram_free > 0 and vram_free < 2.5:
                            self._aigc_append_log("[INFO] 当前剩余显存 %.2fG 偏低，先释放 ComfyUI 缓存…" % vram_free)
                            MS.comfyui_free_vram(url)
                            time.sleep(1.0)

                if mode == "t2i":
                    if models.get("z_image_ready"):
                        self._aigc_append_log("[INFO] 使用本地 Z-Image Turbo 文生图 (%dx%d, %d 步)" % (width, height, steps))
                        wf = MS.build_zimage_t2i_workflow(prompt, neg_prompt, width, height, steps, seed)
                    elif models.get("checkpoints"):
                        ckpt = models["checkpoints"][0]
                        self._aigc_append_log("[INFO] 使用本地 Checkpoint %s 文生图" % ckpt)
                        wf = MS.build_sd_checkpoint_t2i_workflow(ckpt, prompt, neg_prompt, width, height, steps, seed)
                    else:
                        raise RuntimeError("未在本地 ComfyUI 检测到完整文生图模型")
                    ok, msg, saved = MS.comfyui_queue_and_wait(url, wf, out_dir, _prog, _canceled)
                elif mode in ("i2v", "t2v"):
                    if not models.get("wan22_i2v_ready"):
                        raise RuntimeError("未检测到完整 Wan 2.2 I2V 视频模型文件")
                    frame_path = Path(first_frame) if (first_frame and Path(first_frame).is_file()) else None
                    if mode == "t2v" or frame_path is None:
                        if not models.get("z_image_ready"):
                            raise RuntimeError("图生视频请先上传或从画廊选择首帧图片")
                        self._aigc_append_log("[INFO] 文生视频第 1 步：用 Z-Image Turbo 自动生成首帧 (%dx%d)…" % (width, height))
                        _prog(10.0, "第 1/2 步：Z-Image Turbo 生成首帧…")
                        wf1 = MS.build_zimage_t2i_workflow(prompt, neg_prompt, width or 640, height or 384, 8, seed, filename_prefix="DS_KeyFrame")
                        ok1, msg1, saved1 = MS.comfyui_queue_and_wait(url, wf1, out_dir, lambda p, s: _prog(p * 0.42, "首帧生成：" + s), _canceled)
                        if not ok1 or not saved1:
                            raise RuntimeError("首帧生成失败：" + msg1)
                        frame_path = Path(saved1[0]["path"])
                        self._aigc_append_log("[OK] 首帧已生成 → %s" % frame_path.name)
                        # 关键防爆步骤：在加载 Wan2.2 14B 前彻底卸载 Z-Image 模型释放 8G 显存！
                        self._aigc_append_log("[INFO] 卸载 Z-Image 释放显存，为 Wan 2.2 14B 腾出空间…")
                        MS.comfyui_free_vram(url)
                        time.sleep(1.5)

                    _prog(45.0, "第 2/2 步：上传首帧至 Wan 2.2 I2V…")
                    uok, ures = MS.comfyui_upload_image(url, frame_path)
                    if not uok:
                        raise RuntimeError(ures)
                    use_lora = bool(models.get("wan22_lora_ready"))
                    v_steps = 4 if use_lora else max(8, steps)
                    self._aigc_append_log("[INFO] 启动 Wan 2.2 I2V 14B (%dx%d, %d 帧, %d 步%s)…" % (
                        width, height, length, v_steps, " LightX2V 4-Step LoRA" if use_lora else ""
                    ))
                    wf2 = MS.build_wan22_i2v_workflow(
                        prompt, neg_prompt, ures, width=width, height=height,
                        length=length, steps=v_steps, seed=seed, use_4step_lora=use_lora
                    )
                    ok, msg, saved = MS.comfyui_queue_and_wait(
                        url, wf2, out_dir,
                        lambda p, s: _prog(45.0 + p * 0.55, "视频生成：" + s),
                        _canceled, timeout_sec=1200
                    )
                else:
                    raise RuntimeError("未知生成模式：" + mode)

            if ok and saved:
                now_str = datetime.now().strftime("%H:%M:%S")
                with self.lock:
                    for it in saved:
                        self.aigc_job["gallery"].insert(0, {
                            "path": it["path"],
                            "name": it["name"],
                            "kind": it["kind"],
                            "prompt": prompt[:120],
                            "mode": mode,
                            "time": now_str,
                        })
                    self.aigc_job["gallery"] = self.aigc_job["gallery"][:24]
                    self.aigc_job["pct"] = 100.0
                    self.aigc_job["status"] = msg
                self._recent_ts = 0.0
                self._aigc_append_log("[OK] %s → %s" % (msg, saved[0]["name"]))
                self.log("AI 创作工坊完成 → %s" % saved[0]["name"], "OK")
            else:
                with self.lock:
                    self.aigc_job["status"] = msg
                self._aigc_append_log("[ERROR] " + msg)
        except Exception as ex:
            with self.lock:
                self.aigc_job["status"] = "生成失败"
            self._aigc_append_log("[ERROR] %s" % ex)
        finally:
            with self.lock:
                self.aigc_job["running"] = False
                self.aigc_job["cancel"] = False

    @staticmethod
    def _mask_key(k: str) -> str:
        s = (k or "").strip()
        if not s:
            return ""
        if len(s) <= 8:
            return "*" * len(s)
        return s[:4] + "****" + s[-4:]

    def _safe_cfg_for_ui(self):
        c = json.loads(json.dumps(self.cfg))
        if isinstance(c.get("codex"), dict):
            raw_k = str(c["codex"].get("api_key") or "")
            c["codex"]["has_key"] = bool(raw_k.strip())
            c["codex"]["key_masked"] = self._mask_key(raw_k)
            c["codex"]["api_key"] = ""
        if isinstance(c.get("comfyui"), dict):
            raw_ck = str(c["comfyui"].get("custom_api_key") or "")
            c["comfyui"]["custom_has_key"] = bool(raw_ck.strip())
            c["comfyui"]["custom_api_key"] = ""
        return c

    def _get_voice_env_cached(self):
        now = time.time()
        if self._voice_env_cache is None or (now - self._voice_env_ts) > 15.0:
            self._voice_env_cache = MS.detect_voice_env(PANEL_DIR) if MS else {"gpu": "-", "py312": "", "f5_ready": False, "edge_ready": False, "voices": []}
            self._voice_env_ts = now
        return dict(self._voice_env_cache)

    def _get_recent_files_cached(self):
        now = time.time()
        if (now - self._recent_ts) > 3.5:
            dl_base = Path(self.cfg.get("paths", {}).get("downloads") or str(DL_HOME))
            dirs = [
                ("AI创作", self.aigc_output()),
                ("视频", self.yt_output()),
                ("音乐", self.music_output()),
                ("克隆", self.voice_output()),
                ("直链", str(dl_base / "aria2")),
                ("BT", self.cfg.get("qbit", {}).get("save_dir") or str(dl_base / "qBittorrent")),
            ]
            self._recent_cache = MS.scan_recent_downloads(dirs, limit=10) if MS else []
            self._recent_ts = now
        return list(self._recent_cache)

    def _magnet_diag(self):
        if MT is None:
            return {"ok": False, "tracker_count": 0, "missing": ["magnet_tools"], "dht_dat_size": 0}
        try:
            d = MT.diagnose_aria2_conf(self.cfg["aria2"]["conf"])
            tr_cache = MT.load_cached_trackers(CACHE / "trackers.txt")
            d["cached_trackers"] = len(tr_cache)
            return d
        except Exception:
            return {"ok": False, "tracker_count": 0, "missing": [], "dht_dat_size": 0, "cached_trackers": 0}

    def get_state(self):
        sec = int(time.time() - self.t0)
        up = "%02d:%02d:%02d" % (sec // 3600, sec % 3600 // 60, sec % 60)
        with self.lock:
            logs = list(self.logs[-120:])
            wave = list(self.wave)
            yt_job = dict(self.yt_job)
            yt_job["logs"] = list(self.yt_job["logs"][-120:])
            music_job = dict(self.music_job)
            music_job["logs"] = list(self.music_job["logs"][-80:])
            music_job["results"] = list(self.music_job["results"][:30])
            voice_job = dict(self.voice_job)
            voice_job["logs"] = list(self.voice_job["logs"][-100:])
            aigc_job = dict(self.aigc_job)
            aigc_job["logs"] = list(self.aigc_job["logs"][-100:])
            aigc_job["gallery"] = list(self.aigc_job["gallery"][:24])
        yt_state = dict(self.pr.y)
        yt_state["upscale"] = bool(self.cfg.get("ui", {}).get("upscale"))
        yt_state["on"] = bool(yt_state.get("on") or yt_job.get("running"))
        yt_job["has_ytdlp"] = bool(self._find_ytdlp())
        yt_job["has_ffmpeg"] = bool(self._find_ffmpeg())
        yt_job["has_video2x"] = bool(self._find_video2x())
        yt_job["out_dir"] = self.yt_output()
        yt_job["proxy"] = self._sys_proxy() or "直连"
        music_job["out_dir"] = self.music_output()
        music_job["has_ytdlp"] = yt_job["has_ytdlp"]
        music_job["has_ffmpeg"] = yt_job["has_ffmpeg"]
        music_job["charts"] = list(MS.MUSIC_CHARTS) if MS else []
        voice_job["out_dir"] = self.voice_output()
        voice_job["env"] = self._get_voice_env_cached()
        aigc_job["out_dir"] = self.aigc_output()
        aigc_job["env"] = self._get_aigc_env_cached()
        codex_cfg = self.cfg.get("codex") or {}
        codex_info = {
            "configured": bool((codex_cfg.get("base_url") or "").strip() and (codex_cfg.get("api_key") or "").strip()),
            "base_url": str(codex_cfg.get("base_url") or ""),
            "model": str(codex_cfg.get("model") or "gpt-5.3-codex"),
            "api_style": str(codex_cfg.get("api_style") or "auto"),
            "key_masked": self._mask_key(str(codex_cfg.get("api_key") or "")),
        }
        return {
            "aria2": dict(self.pr.a),
            "qbit": dict(self.pr.q),
            "yt": yt_state,
            "yt_studio": yt_job,
            "music_studio": music_job,
            "voice_studio": voice_job,
            "aigc_studio": aigc_job,
            "repair4k": dict(self.repair4k_job),
            "disk": self._disk_stats(),
            "after_dl": dict(self.after_dl),
            "codex": codex_info,
            "recent_files": self._get_recent_files_cached(),
            "magnet": self._magnet_diag(),
            "tasks": {
                "aria2": list(self.pr.a_tasks),
                "qbit": list(self.pr.q_tasks),
            },
            "urls": {
                "ariang": self._ariang_url(),
                "ariang_embedded": self._ariang_dir() is not None,
                "qbit": "/qbit/",
                "qbit_direct": self._qbit_url(),
            },
            "cfg": self._safe_cfg_for_ui(),
            "wave": wave,
            "logs": logs,
            "uptime": up,
        }

    def handle_action(self, body):
        act = (body.get("action") or "").strip()
        if act == "video_library":
            try:
                items = self.video_library()
            except Exception as ex:
                return False, "片库扫描失败：%s" % ex, {"items": []}
            ready = sum(1 for i in items if i.get("ready"))
            return True, "片库共 %d 部影片（可播放 %d）" % (len(items), ready), {"items": items}
        if act == "video_probe":
            info = self.probe_video(str(body.get("path") or ""))
            return bool(info.get("ok")), info.get("msg") or "探测完成", {"info": info}
        if act == "video_repair_4k":
            import threading
            with self.lock:
                if self.repair4k_job.get("running"):
                    return False, "已有 4K 画质重建任务正在运行，请等待完成或先取消", {"job": dict(self.repair4k_job)}
            target = self._is_allowed_media(str(body.get("path") or ""))
            if target is None or target.suffix.lower() not in self._VIDEO_EXTS:
                return False, "视频文件不存在或不在允许目录内", {}
            preset = str(body.get("preset") or "ultra4k").strip().lower()
            fix_hdr = bool(body.get("fix_hdr", True))
            threading.Thread(
                target=self._run_repair_4k_worker, args=(target, preset, fix_hdr), daemon=True
            ).start()
            return True, "已启动 RTX 显卡纯 4K (3840×2160) 高码率母带重建任务", {}
        if act == "video_repair_4k_cancel":
            with self.lock:
                self.repair4k_job["cancel"] = True
                pid = self.repair4k_job.get("pid")
            if pid and pid_alive(pid):
                kill_tree(pid)
            return True, "已取消 4K 母带重建任务", {}
        if act == "set_after_dl":
            mode = str(body.get("mode") or "off").strip().lower()
            if mode not in ("off", "stop_seed", "sleep", "shutdown"):
                return False, "无效的自动动作模式", {}
            if mode == "off" and IS_WIN:
                try:
                    subprocess.run(["shutdown", "/a"], capture_output=True, timeout=3, creationflags=0x08000000)
                except Exception:
                    pass
            active = self._count_active_jobs()
            labels = {"off": "未启用", "stop_seed": "下完自动停种", "sleep": "下完自动睡眠", "shutdown": "下完60秒后关机"}
            with self.lock:
                self.after_dl.update({
                    "mode": mode,
                    "seen_active": (active > 0) if mode != "off" else False,
                    "countdown": 0,
                    "deadline": 0.0,
                    "active_cnt": active,
                    "status": ("未启用" if mode == "off" else
                               ("护航中（%d 个任务运行中）" % active if active > 0 else "已预约：%s（等待任务开始）" % labels[mode])),
                })
            self.log("🌙 下完自动动作 → %s" % labels[mode], "OK")
            return True, "已设置：%s" % labels[mode], {"after_dl": dict(self.after_dl)}
        if act == "video_snap_frame":
            from urllib.parse import quote
            raw_p = str(body.get("path") or "").strip()
            target = self._is_allowed_media(raw_p)
            if target is None or target.suffix.lower() not in self._VIDEO_EXTS:
                return False, "视频文件不存在或不在允许目录内", {}
            try:
                sec = max(0.0, float(body.get("time_sec") or 0.0))
            except Exception:
                sec = 0.0
            send_aigc = bool(body.get("send_to_aigc"))
            ff_dir = self._find_ffmpeg()
            ffmpeg_exe = (str(Path(ff_dir) / ("ffmpeg.exe" if IS_WIN else "ffmpeg")) if ff_dir else (shutil.which("ffmpeg") or ""))
            if not ffmpeg_exe:
                return False, "未找到 ffmpeg，无法导出原画截图", {}
            cap_dir = self.captures_output()
            ts_tag = "%02d%02d%02d" % (int(sec // 3600), int((sec % 3600) // 60), int(sec % 60))
            out_png = cap_dir / ("%s_4K_%s_%s.png" % (target.stem[:42], ts_tag, datetime.now().strftime("%H%M%S")))
            try:
                r = subprocess.run(
                    [ffmpeg_exe, "-y", "-v", "error", "-ss", "%.3f" % sec, "-i", str(target),
                     "-frames:v", "1", "-compression_level", "3", str(out_png)],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
                    creationflags=(0x08000000 if IS_WIN else 0),
                )
                if r.returncode != 0 or not out_png.is_file():
                    return False, "截图失败：%s" % (r.stderr or "ffmpeg error")[:80], {}
            except Exception as ex:
                return False, "截图异常：%s" % ex, {}
            aigc_loaded = False
            if send_aigc:
                try:
                    dst = CACHE / "aigc_first_frame.png"
                    shutil.copy2(out_png, dst)
                    with self.lock:
                        self.aigc_job["first_frame"] = str(dst.resolve())
                        self.aigc_job["first_frame_name"] = out_png.name
                    aigc_loaded = True
                except Exception:
                    pass
            self._recent_ts = 0.0
            msg = ("已抓取 4K 原画截图并载入 AI 画室首帧 ✔" if aigc_loaded else "已保存 4K 无损原画截图 → %s" % out_png.name)
            self.log(msg, "OK")
            return True, msg, {
                "path": str(out_png), "name": out_png.name,
                "play_url": "/api/media?path=" + quote(str(out_png), safe=""),
                "aigc_loaded": aigc_loaded,
            }
        if act == "video_clip_extract":
            from urllib.parse import quote
            raw_p = str(body.get("path") or "").strip()
            target = self._is_allowed_media(raw_p)
            if target is None or target.suffix.lower() not in self._VIDEO_EXTS:
                return False, "视频文件不存在或不在允许目录内", {}
            try:
                t_start = max(0.0, float(body.get("start_sec") or 0.0))
                t_end = max(t_start + 1.0, float(body.get("end_sec") or (t_start + 15.0)))
            except Exception:
                return False, "剪辑时间范围无效", {}
            dur = min(600.0, t_end - t_start)
            mode = str(body.get("mode") or "clip").strip().lower()
            ff_dir = self._find_ffmpeg()
            ffmpeg_exe = (str(Path(ff_dir) / ("ffmpeg.exe" if IS_WIN else "ffmpeg")) if ff_dir else (shutil.which("ffmpeg") or ""))
            if not ffmpeg_exe:
                return False, "未找到 ffmpeg，无法剪辑导出", {}
            cap_dir = self.captures_output()
            ts_tag = "%02d%02d-%02d%02d" % (int(t_start // 60), int(t_start % 60), int((t_start + dur) // 60), int((t_start + dur) % 60))
            if mode == "voice_ref":
                dur = min(15.0, max(3.0, dur))
                out_wav = CACHE / "ref_voice.wav"
                r = subprocess.run(
                    [ffmpeg_exe, "-y", "-v", "error", "-ss", "%.3f" % t_start, "-t", "%.3f" % dur,
                     "-i", str(target), "-vn", "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(out_wav)],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
                    creationflags=(0x08000000 if IS_WIN else 0),
                )
                if r.returncode != 0 or not out_wav.is_file():
                    return False, "人声提取失败：%s" % (r.stderr or "")[:80], {}
                ref_name = "%s_%s.wav" % (target.stem[:24], ts_tag)
                with self.lock:
                    self.voice_job["ref_wav"] = str(out_wav.resolve())
                    self.voice_job["ref_name"] = ref_name
                self.log("🎙️ 已从影片截取 %.1fs 台词送入 AI 声音克隆参考音" % dur, "OK")
                return True, "已截取 %.1f 秒人声参考音并自动载入声音克隆工坊 ✔" % dur, {
                    "path": str(out_wav), "name": ref_name, "mode": "voice_ref",
                }
            if mode == "audio":
                out_mp3 = cap_dir / ("%s_audio_%s_%s.mp3" % (target.stem[:36], ts_tag, datetime.now().strftime("%H%M%S")))
                r = subprocess.run(
                    [ffmpeg_exe, "-y", "-v", "error", "-ss", "%.3f" % t_start, "-t", "%.3f" % dur,
                     "-i", str(target), "-vn", "-c:a", "libmp3lame", "-b:a", "320k", str(out_mp3)],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45,
                    creationflags=(0x08000000 if IS_WIN else 0),
                )
                if r.returncode != 0 or not out_mp3.is_file():
                    return False, "音轨提取失败：%s" % (r.stderr or "")[:80], {}
                self._recent_ts = 0.0
                self.log("🎵 已无损提取影片音轨 → %s" % out_mp3.name, "OK")
                return True, "已导出 320K 音轨 → %s" % out_mp3.name, {
                    "path": str(out_mp3), "name": out_mp3.name,
                    "play_url": "/api/media?path=" + quote(str(out_mp3), safe=""), "mode": "audio",
                }
            # 默认 mode == "clip": 极速零重编码无损高光剪辑 (-c:v copy)
            out_clip = cap_dir / ("%s_clip_%s_%s.mp4" % (target.stem[:36], ts_tag, datetime.now().strftime("%H%M%S")))
            pinfo = self.probe_video(str(target))
            acodec = str(pinfo.get("acodec") or "").lower()
            vcodec = str(pinfo.get("vcodec") or "").lower()
            cmd = [
                ffmpeg_exe, "-y", "-v", "error", "-ss", "%.3f" % t_start, "-t", "%.3f" % dur,
                "-i", str(target), "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "copy",
            ]
            if vcodec in ("hevc", "h265"):
                cmd += ["-tag:v", "hvc1"]
            if acodec in self._COPY_ACODECS:
                cmd += ["-c:a", "copy"]
            else:
                cmd += ["-c:a", "aac", "-b:a", "320k", "-ac", "2"]
            cmd += ["-movflags", "+faststart", str(out_clip)]
            r = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
                creationflags=(0x08000000 if IS_WIN else 0),
            )
            if r.returncode != 0 or not out_clip.is_file():
                return False, "高光剪辑失败：%s" % (r.stderr or "")[:80], {}
            self._recent_ts = 0.0
            self.log("✂️ 极速无损剪辑完成 → %s" % out_clip.name, "OK")
            return True, "已零压缩无损导出 %.0f 秒高光片段 → %s" % (dur, out_clip.name), {
                "path": str(out_clip), "name": out_clip.name,
                "play_url": "/api/media?path=" + quote(str(out_clip), safe=""), "mode": "clip",
            }
        if act in ("video_open_external", "video_open_folder"):
            target = self._is_allowed_media(str(body.get("path") or ""))
            if target is None or target.suffix.lower() not in self._VIDEO_EXTS:
                return False, "文件不在允许的下载目录内或不存在", {}
            if act == "video_open_external":
                open_path(target)
                self.log("系统播放器打开 %s" % target.name, "OK")
                return True, "已用系统默认播放器打开", {}
            if IS_WIN:
                try:
                    subprocess.Popen(["explorer", "/select,", str(target)])
                except Exception:
                    open_path(target.parent)
            else:
                open_path(target.parent)
            return True, "已打开所在文件夹", {}
        if act == "video_delete_and_clean":
            raw_p = str(body.get("path") or "").strip()
            tor_hash = str(body.get("hash") or "").strip()
            do_cache = bool(body.get("clean_cache", True))
            target = self._is_allowed_media(raw_p)
            if target is None or target.suffix.lower() not in self._VIDEO_EXTS:
                return False, "文件不存在或不在允许的下载目录内", {}
            name = target.name
            stem = target.stem
            parent = target.parent
            freed = 0
            try:
                freed = int(target.stat().st_size)
            except Exception:
                freed = 0
            qb_removed = False
            # 1) 若关联 qBittorrent 种子，先通知 qB 删除种子与文件（自动释放句柄并避免 Missing Files）
            if tor_hash and port_open(self.cfg["qbit"]["host"], self.cfg["qbit"]["port"]):
                try:
                    s, base = self.pr.q_login(timeout=3.0)
                    hdr = {"Referer": base + "/", "Origin": base}
                    r = s.post(base + "/api/v2/torrents/delete", timeout=6.0, headers=hdr,
                               data={"hashes": tor_hash, "deleteFiles": "true"})
                    if r.status_code == 200:
                        qb_removed = True
                        time.sleep(0.35)
                except Exception:
                    pass
            # 2) 确保视频文件本身已删除（Windows 句柄释放最多重试 5 次）
            file_deleted = not target.exists()
            last_err = ""
            if not file_deleted:
                for _ in range(5):
                    try:
                        target.unlink()
                        file_deleted = True
                        break
                    except FileNotFoundError:
                        file_deleted = True
                        break
                    except Exception as ex:
                        last_err = str(ex)
                        time.sleep(0.25)
            if not file_deleted:
                return False, "文件可能仍被其他程序占用，删除失败：%s" % last_err[:80], {}
            # 清理同名前缀的外挂字幕与残余控制文件
            extra_del = 0
            try:
                for sib in list(parent.iterdir()):
                    if not sib.is_file():
                        continue
                    sn = sib.name
                    if sn.startswith(name + ".") and sib.suffix.lower() in (".aria2", ".!qb", ".parts"):
                        try:
                            freed += int(sib.stat().st_size)
                            sib.unlink()
                            extra_del += 1
                        except Exception:
                            pass
                    elif sib.stem == stem and sib.suffix.lower() in self._SUB_EXTS:
                        try:
                            freed += int(sib.stat().st_size)
                            sib.unlink()
                            extra_del += 1
                        except Exception:
                            pass
            except Exception:
                pass
            # 若所在目录为该影片专属子目录且已空，自动移除空目录（绝不删下载根目录）
            try:
                dl_base = Path(self.cfg.get("paths", {}).get("downloads") or str(DL_HOME)).resolve()
                protected = {
                    dl_base,
                    (dl_base / "aria2").resolve(),
                    Path(self.cfg.get("qbit", {}).get("save_dir") or str(dl_base / "qBittorrent")).resolve(),
                    Path(self.yt_output()).resolve(),
                }
                if parent.resolve() not in protected and parent.is_dir() and not any(parent.iterdir()):
                    parent.rmdir()
            except Exception:
                pass
            # 3) 顺带清理面板缓存 + 探测缓存 + Aria2 已停记录
            cache_n = 0
            if do_cache:
                try:
                    pc = getattr(self, "_probe_cache", None)
                    if isinstance(pc, dict):
                        pc.clear()
                except Exception:
                    pass
                try:
                    for f in CACHE.rglob("*"):
                        if f.is_file() and f.name.lower() != "trackers.txt":
                            try:
                                freed += int(f.stat().st_size)
                                f.unlink()
                                cache_n += 1
                            except Exception:
                                pass
                except Exception:
                    pass
                try:
                    if port_open(self.cfg["aria2"]["host"], self.cfg["aria2"]["port"]):
                        self.pr.a_call("aria2.purgeDownloadResult")
                except Exception:
                    pass
            # 格式化释放空间
            v = float(freed)
            for unit in ("B", "KB", "MB", "GB", "TB"):
                if v < 1024.0 or unit == "TB":
                    freed_s = ("%d %s" % (int(v), unit)) if unit == "B" else ("%.2f %s" % (v, unit))
                    break
                v /= 1024.0
            self.poll_once()
            parts = ["已删除《%s》" % name]
            if qb_removed:
                parts.append("同步移除 qB 种子")
            if cache_n > 0:
                parts.append("清理 %d 个缓存" % cache_n)
            parts.append("释放 %s" % freed_s)
            msg = " · ".join(parts) + " ✔"
            self.log(msg, "OK")
            return True, msg, {"freed_bytes": freed, "freed_str": freed_s, "cache_cleaned": cache_n, "qbit_removed": qb_removed}
        if act == "start_a":
            if port_open(self.cfg["aria2"]["host"], self.cfg["aria2"]["port"]):
                self.log("Aria2 已在线，已切换内置 AriaNg 管理舱", "OK")
                return True, "Aria2 已在线", {"embedded_view": "ariang"}
            exe = Path(str(self.cfg["aria2"].get("exe") or ""))
            conf = Path(str(self.cfg["aria2"].get("conf") or ""))
            script = str((self.cfg.get("scripts") or {}).get("start") or "")
            started = False
            if exe.is_file() and conf.is_file():
                ok, _ = self.run_cmd([str(exe), "--conf-path=" + str(conf)], "启动 Aria2 引擎", "aria2", cwd=str(exe.parent))
                started = ok
            elif script and Path(script).exists():
                ok, _ = self.run_cmd(script_cmd(script), "启动 Aria2", "stack")
                started = ok
            else:
                self.log("未检测到 aria2c 或启动脚本，请先运行安装器", "ERROR")
                return False, "未找到 Aria2 程序或脚本", {}
            for _ in range(8):
                time.sleep(0.25)
                if port_open(self.cfg["aria2"]["host"], self.cfg["aria2"]["port"]):
                    break
            self.poll_once()
            return started, "Aria2 已启动" if started else "Aria2 启动失败", {}

        if act == "stop_a":
            pid = self.pids.get("aria2")
            if pid and pid_alive(pid):
                kill_tree(pid)
                self.pids.pop("aria2", None)
                save_pids(self.pids)
                self.log("已停止 Aria2 PID %s" % pid, "WARN")
            else:
                script = str((self.cfg.get("scripts") or {}).get("stop") or "")
                if script and Path(script).exists():
                    self.run_cmd(script_cmd(script), "停止 Aria2")
                else:
                    try:
                        self.pr.a_call("aria2.shutdown")
                        self.log("已通过 RPC 发送 Aria2 关停指令", "WARN")
                    except Exception:
                        pass
            time.sleep(0.6)
            self.poll_once()
            return True, "Aria2 已停止", {}

        if act == "restart_a":
            self.handle_action({"action": "stop_a"})
            time.sleep(0.8)
            return self.handle_action({"action": "start_a"})

        if act == "ariang":
            url = self._ariang_url()
            self.log("已切换至站内同源 AriaNg 管理舱（自动注入 RPC Token）", "OK")
            return True, "已打开内置 AriaNg", {"embedded_view": "ariang", "url": url}

        if act == "test_a":
            try:
                v = (self.pr.a_call("aria2.getVersion") or {}).get("version", "?")
                self.log("Aria2 RPC 通，version=%s" % v, "OK")
                return True, "Aria2 RPC 连通 (v%s)" % v, {}
            except Exception as ex:
                self.log("Aria2 RPC 不通 %s" % ex, "ERROR")
                return False, "Aria2 RPC 不通，请先启动 Aria2", {}

        if act == "ports":
            parts = []
            for name, port in (("aria2", self.cfg["aria2"]["port"]),
                               ("webui", self.cfg["qbit"]["port"])):
                parts.append("%s:%s=%s" % (name, port, "在线" if port_open("127.0.0.1", port) else "空闲"))
            parts.append("ariang=内置同源直出")
            msg = "端口 " + " ".join(parts)
            self.log(msg)
            return True, msg, {}

        if act == "start_q":
            if port_open(self.cfg["qbit"]["host"], self.cfg["qbit"]["port"]):
                self.pr._q_hold_until = 0
                self.log("qBittorrent 已在线", "OK")
                return True, "qBittorrent 已在线", {"embedded_view": "qbit"}
            script = str((self.cfg.get("scripts") or {}).get("qbit") or "")
            if script and Path(script).exists():
                ok, msg = self.run_cmd(script_cmd(script), "启动 qBittorrent", "qbit")
            else:
                exe_dir = Path(str((self.cfg.get("qbit") or {}).get("exe_dir") or ""))
                hit = next((exe_dir / n for n in ("qbittorrent.exe", "qBittorrent.exe") if (exe_dir / n).is_file()), None)
                if hit:
                    cmd = [str(hit)]
                    prof = str((self.cfg.get("qbit") or {}).get("profile") or "").strip()
                    if prof:
                        cmd.append("--profile=%s" % prof)
                    cmd.append("--no-splash")
                    ok, msg = self.run_cmd(cmd, "启动 qBittorrent", "qbit", cwd=str(exe_dir))
                else:
                    return False, "未找到 qBittorrent 程序或脚本", {}
            for _ in range(24):
                time.sleep(0.35)
                if port_open(self.cfg["qbit"]["host"], self.cfg["qbit"]["port"]):
                    self.pr._q_hold_until = 0
                    break
            self.poll_once()
            return ok, msg, {}

        if act == "stop_q":
            pid = self.pids.get("qbit")
            if pid and pid_alive(pid):
                kill_tree(pid)
                self.pids.pop("qbit", None)
                save_pids(self.pids)
                self.log("已停止 qBittorrent PID %s" % pid, "WARN")
                self.poll_once()
                return True, "已停止 qBittorrent", {}
            try:
                s, base = self.pr.q_login()
                s.post(base + "/api/v2/app/shutdown", timeout=2.0, headers={"Referer": base + "/"})
                self.log("已通过 WebUI API 优雅关闭 qBittorrent", "WARN")
                time.sleep(0.8)
                self.poll_once()
                return True, "已优雅关闭 qBittorrent", {}
            except Exception:
                self.log("没有本面板记录的 qBittorrent 进程", "WARN")
                return False, "未找到本面板记录的 qB 进程", {}

        if act == "webui":
            self.log("已切换至站内同源 qBittorrent WebUI", "OK")
            return True, "已打开内置 qB WebUI", {"embedded_view": "qbit"}

        if act == "test_q":
            try:
                s, base = self.pr.q_login()
                v = s.get(base + "/api/v2/app/version", timeout=2).text.strip()
                self.pr._q_hold_until = 0
                self.poll_once()
                self.log("WebUI 通，version=%s" % v, "OK")
                return True, "qB WebUI 连通 (%s)" % v, {}
            except Exception as ex:
                self.log("WebUI 不通 %s" % ex, "ERROR")
                return False, "qB WebUI 连接失败", {}

        if act == "pick_folder":
            target = str(body.get("target") or "").strip()
            init = str(body.get("initial") or "").strip()
            if not init:
                if target == "yt":
                    init = self.yt_output()
                elif target == "music":
                    init = self.music_output()
                elif target == "voice":
                    init = self.voice_output()
                elif target == "aigc":
                    init = self.aigc_output()
                elif target in ("qbit", "magnet"):
                    init = self.cfg["qbit"].get("save_dir") or str(DL_HOME)
                else:
                    init = self.cfg.get("paths", {}).get("downloads") or str(DL_HOME)
            chosen = self._pick_folder_dialog(init)
            if not chosen:
                return False, "已取消选择目录", {"path": ""}
            if target == "yt":
                self.cfg["yt"]["output"] = chosen
                save_cfg(self.cfg)
                self.log("YT 视频保存目录已设为：%s" % chosen, "OK")
            elif target == "music":
                self.cfg.setdefault("paths", {})["music"] = chosen
                save_cfg(self.cfg)
                self.log("音乐保存目录已设为：%s" % chosen, "OK")
            elif target == "voice":
                self.cfg.setdefault("paths", {})["voice"] = chosen
                save_cfg(self.cfg)
                self.log("声音克隆保存目录已设为：%s" % chosen, "OK")
            elif target == "aigc":
                self.cfg.setdefault("paths", {})["aigc"] = chosen
                save_cfg(self.cfg)
                self.log("AI 创作保存目录已设为：%s" % chosen, "OK")
            elif target == "qbit":
                self.cfg["qbit"]["save_dir"] = chosen
                save_cfg(self.cfg)
                self.log("qBittorrent 保存目录已设为：%s" % chosen, "OK")
            elif target == "downloads":
                self.cfg["paths"]["downloads"] = chosen
                save_cfg(self.cfg)
                self.log("总下载目录已设为：%s" % chosen, "OK")
            return True, "已选择目录：%s" % chosen, {"path": chosen}

        if act == "add_download":
            raw_url = str(body.get("url") or "").strip()
            engine = str(body.get("engine") or "auto").strip().lower()
            save_dir = str(body.get("save_dir") or "").strip()
            if not raw_url:
                return False, "请先粘贴下载链接或磁力链接", {}
            if save_dir:
                try:
                    Path(save_dir).mkdir(parents=True, exist_ok=True)
                except Exception:
                    pass
            low = raw_url.lower()
            is_magnet = False
            magnet_info = None
            if MT is not None:
                mi = MT.parse_magnet(raw_url)
                if mi.get("valid"):
                    is_magnet = True
                    magnet_info = mi
            elif low.startswith("magnet:"):
                is_magnet = True
            video_hosts = ("youtube.com", "youtu.be", "bilibili.com", "b23.tv", "douyin.com", "iesdouyin.com",
                           "xiaohongshu.com", "xhslink.com", "tiktok.com", "vimeo.com", "x.com", "twitter.com",
                           "twitch.tv", "kuaishou.com", "weibo.com")
            if engine == "auto":
                if is_magnet or low.endswith(".torrent"):
                    engine = "magnet"
                elif any(h in low for h in video_hosts):
                    engine = "yt"
                else:
                    engine = "aria2"

            if engine == "magnet" or (is_magnet and engine in ("aria2", "qbit")):
                target_eng = engine if engine in ("aria2", "qbit") else ("qbit" if self.pr.q.get("on") else "aria2")
                enhanced = raw_url
                ih = ""
                if MT is not None and magnet_info:
                    ih = magnet_info.get("infohash", "")
                    tr_pool = MT.load_cached_trackers(CACHE / "trackers.txt")
                    try:
                        enhanced = MT.enhance_magnet(raw_url, tr_pool)
                    except Exception:
                        enhanced = magnet_info.get("uri") or raw_url

                tor_bytes, tor_src = b"", ""
                if MT is not None and ih:
                    try:
                        tor_bytes, tor_src = MT.resolve_magnet_torrent(ih, proxy=self._sys_proxy(), timeout=4.0)
                    except Exception:
                        tor_bytes, tor_src = b"", ""

                if target_eng == "qbit":
                    try:
                        q_host = self.cfg["qbit"]["host"]
                        q_port = self.cfg["qbit"]["port"]
                        if not port_open(q_host, q_port):
                            self.log("qBittorrent 离线，正在自动拉起并等待 WebUI 就绪…", "INFO")
                            self.handle_action({"action": "start_q"})
                        if not port_open(q_host, q_port):
                            raise RuntimeError("qBittorrent 启动超时，端口 %s 未就绪" % q_port)
                        self.pr._q_hold_until = 0
                        s, base = self.pr.q_login(timeout=3.5)
                        hdr = {"Referer": base + "/", "Origin": base}
                        extra_data = {"savepath": save_dir} if save_dir else {}
                        added_ok = False
                        used_tor = False
                        if tor_bytes:
                            r = s.post(base + "/api/v2/torrents/add", timeout=6.0, headers=hdr,
                                       data=extra_data,
                                       files={"torrents": (ih + ".torrent", tor_bytes, "application/x-bittorrent")})
                            if r.status_code == 200 and "fails" not in (r.text or "").lower():
                                added_ok = True
                                used_tor = True
                        if not added_ok:
                            extra_data2 = dict(extra_data)
                            extra_data2["urls"] = enhanced
                            r = s.post(base + "/api/v2/torrents/add", timeout=5.0, headers=hdr,
                                       data=extra_data2)
                            if r.status_code == 200 and "fails" not in (r.text or "").lower():
                                added_ok = True
                        if added_ok:
                            # 投递后立即对新任务注入全量 IP+UDP Tracker 并强制 Reannounce，大幅缩短冷启动时间！
                            if MT is not None and ih:
                                try:
                                    if not getattr(self, "_qbit_turbo_applied", False):
                                        turbo = MT.build_qbit_turbo_prefs(tr_pool)
                                        s.post(base + "/api/v2/app/setPreferences", timeout=3.0, headers=hdr,
                                               data={"json": json.dumps(turbo)})
                                        self._qbit_turbo_applied = True
                                    tr_lines = "\n".join(tr_pool[:100])
                                    s.post(base + "/api/v2/torrents/addTrackers", timeout=2.5, headers=hdr,
                                           data={"hash": ih.lower(), "urls": tr_lines})
                                    s.post(base + "/api/v2/torrents/reannounce", timeout=2.5, headers=hdr,
                                           data={"hashes": ih.lower()})
                                except Exception:
                                    pass
                            note = "（已秒级预取种子 %s + 注入百源 Tracker）" % tor_src if used_tor else "（已注入 100+ IP/UDP Tracker 并强制唤醒节点）"
                            self.log("qBittorrent 磁力投递成功 %s" % note, "OK")
                            time.sleep(0.25)
                            self.poll_once()
                            return True, "磁力已投递至 qBittorrent" + note, {"engine": "qbit", "infohash": ih}
                        raise RuntimeError("http_%s_%s" % (r.status_code, (r.text or "")[:40]))
                    except Exception as ex:
                        self.log("qB 磁力投递失败，尝试回退 Aria2：%s" % ex, "WARN")
                        target_eng = "aria2"
                        qbit_fallback_reason = str(ex)[:80]
                else:
                    qbit_fallback_reason = ""

                if target_eng == "aria2":
                    try:
                        import base64
                        if not port_open(self.cfg["aria2"]["host"], self.cfg["aria2"]["port"]):
                            self.handle_action({"action": "start_a"})
                        opts = {"dir": save_dir} if save_dir else {}
                        if tor_bytes:
                            gid = self.pr.a_call("aria2.addTorrent",
                                                 [base64.b64encode(tor_bytes).decode("ascii"), [], opts])
                            note = "（已秒级预取种子 %s）" % tor_src
                        else:
                            gid = self.pr.a_call("aria2.addUri", [[enhanced], opts])
                            note = "（已自动补全公共 Tracker）"
                        fb = "（qB 未就绪已改由 Aria2 接管）" if qbit_fallback_reason else ""
                        self.log("Aria2 磁力投递成功 GID=%s %s" % (gid, note), "OK")
                        time.sleep(0.2)
                        self.poll_once()
                        return True, "磁力已投递至 Aria2" + fb + note, {"engine": "aria2", "gid": gid, "fallback": bool(qbit_fallback_reason)}
                    except Exception as ex:
                        ex_s = str(ex)
                        if "already registered" in ex_s.lower():
                            self.poll_once()
                            return True, "该磁力任务已在 Aria2 队列中，无需重复投递", {"engine": "aria2", "duplicate": True}
                        self.log("Aria2 磁力投递失败 %s" % ex, "ERROR")
                        return False, "磁力投递失败，请先启动 Aria2 或 qBittorrent", {}

            if engine == "aria2":
                try:
                    if not port_open(self.cfg["aria2"]["host"], self.cfg["aria2"]["port"]):
                        self.handle_action({"action": "start_a"})
                    opts = {"dir": save_dir} if save_dir else {}
                    gid = self.pr.a_call("aria2.addUri", [[raw_url], opts] if opts else [[raw_url]])
                    self.log("Aria2 已投递直链任务 GID=%s" % gid, "OK")
                    self.poll_once()
                    return True, "已投递至 Aria2 高速下载", {"engine": "aria2", "gid": gid}
                except Exception as ex:
                    self.log("Aria2 投递失败 %s" % ex, "ERROR")
                    return False, "Aria2 投递失败，请先启动 Aria2", {}

            if engine == "qbit":
                try:
                    if not port_open(self.cfg["qbit"]["host"], self.cfg["qbit"]["port"]):
                        self.handle_action({"action": "start_q"})
                    self.pr._q_hold_until = 0
                    s, base = self.pr.q_login(timeout=3.5)
                    data = {"urls": raw_url}
                    if save_dir:
                        data["savepath"] = save_dir
                    r = s.post(base + "/api/v2/torrents/add", timeout=5.0,
                               headers={"Referer": base + "/", "Origin": base},
                               data=data)
                    if r.status_code == 200 and "fails" not in (r.text or "").lower():
                        self.log("qBittorrent 已添加种子任务", "OK")
                        time.sleep(0.25)
                        self.poll_once()
                        return True, "已投递至 qBittorrent 下载", {"engine": "qbit"}
                    raise RuntimeError("http_%s_%s" % (r.status_code, (r.text or "")[:40]))
                except Exception as ex:
                    self.log("qBittorrent 投递失败 %s" % ex, "ERROR")
                    return False, "qBittorrent 投递失败，请确认 qB 已启动", {}

            if engine == "yt":
                return self.handle_action({
                    "action": "yt_download",
                    "url": raw_url,
                    "quality": "best",
                    "cookies": str((self.cfg.get("yt") or {}).get("cookies") or "auto"),
                    "cookies_file": str((self.cfg.get("yt") or {}).get("cookies_file") or ""),
                    "upscale": bool(self.cfg["ui"].get("upscale")),
                    "save_dir": save_dir,
                })

        if act == "magnet_parse":
            if MT is None:
                return False, "magnet_tools 模块不可用", {}
            info = MT.parse_magnet(str(body.get("raw") or ""))
            return bool(info.get("valid")), info.get("error") or "磁力解析成功", {"info": info}

        if act == "magnet_preview":
            # 投递到临时目录 → 下几 MB → 截一帧 → 让用户"先看画面再决定下不下"
            if MT is None:
                return False, "magnet_tools 模块不可用", {}
            mi = MT.parse_magnet(str(body.get("raw") or body.get("magnet") or ""))
            if not (mi or {}).get("valid"):
                return False, "磁力链接无效", {}
            ih = mi.get("infohash", "")
            uri = mi.get("uri") or str(body.get("raw") or "")
            pdir = CACHE / "preview"
            try:
                pdir.mkdir(parents=True, exist_ok=True)
                for f in list(pdir.rglob("*")):
                    if f.is_file():
                        f.unlink()
            except Exception:
                pass
            try:
                s, base = self.pr.q_login()
            except Exception as ex:
                return False, "qBittorrent 未就绪：%s" % str(ex)[:60], {}
            hdr = {"Referer": base + "/", "Origin": base}
            # 同 infohash 只允许一个任务：已在下载就不要再建预览任务，否则清理时会互相误删
            try:
                _infos = s.get(base + "/api/v2/torrents/info", timeout=8, headers=hdr,
                               proxies={"http": None, "https": None}).json() or []
                for _t in _infos:
                    if str(_t.get("hash", "")).lower() == str(ih).lower():
                        return False, "该种子已在下载队列中（%s%%），直接看下载进度即可，无需预览" % round(float(_t.get("progress") or 0) * 100, 1), {}
            except Exception:
                pass

            def _cleanup_preview():
                try:
                    s.post(base + "/api/v2/torrents/delete", timeout=8, headers=hdr,
                           data={"hashes": ih, "deleteFiles": "true"})
                except Exception:
                    pass

            try:
                s.post(base + "/api/v2/torrents/add", timeout=10, headers=hdr,
                       data={"urls": uri, "savepath": str(pdir), "paused": "false"})
            except Exception as ex:
                return False, "投递预览任务失败：%s" % str(ex)[:60], {}
            exts = (".mp4", ".mkv", ".avi", ".mov", ".ts", ".webm", ".flv", ".wmv", ".m4v")
            vfile = None
            deadline = time.time() + 45
            while time.time() < deadline:
                time.sleep(1.2)
                try:
                    for f in pdir.rglob("*"):
                        if f.is_file() and f.suffix.lower() in exts and f.stat().st_size >= 256 * 1024:
                            vfile = f
                            break
                except Exception:
                    pass
                if vfile:
                    break
            if not vfile:
                _cleanup_preview()
                return False, "22 秒内没下到可解析的视频数据（种子可能冷门，或还没连上做种者）", {}
            ff = self._find_ffmpeg()
            if not ff:
                _cleanup_preview()
                return False, "未找到 ffmpeg", {}
            shot = pdir / "_shot.jpg"
            ok_shot = False
            for ss in ("3", "1", "0"):
                try:
                    if shot.exists():
                        shot.unlink()
                except Exception:
                    pass
                try:
                    subprocess.run([str(ff), "-y", "-ss", ss, "-i", str(vfile),
                                    "-frames:v", "1", "-q:v", "3", str(shot)],
                                   capture_output=True, timeout=25)
                    if shot.exists() and shot.stat().st_size > 2048:
                        ok_shot = True
                        break
                except Exception:
                    pass
            if not ok_shot:
                _cleanup_preview()
                return False, "已下到数据但截帧失败（文件头没到齐），稍后重试", {}
            try:
                import base64
                b64 = base64.b64encode(shot.read_bytes()).decode("ascii")
            except Exception as ex:
                _cleanup_preview()
                return False, "读取预览图失败：%s" % str(ex)[:60], {}
            vname = vfile.name
            _cleanup_preview()
            try:
                for f in list(pdir.rglob("*")):
                    if f.is_file() and f.name != "_shot.jpg":
                        f.unlink()
            except Exception:
                pass
            self.log("磁力预览已生成：%s" % vname[:40], "OK")
            return True, "预览已生成：%s" % vname, {
                "image": "data:image/jpeg;base64," + b64,
                "file": vname,
            }

        if act == "magnet_search":
            if MT is None:
                return False, "magnet_tools 模块不可用", {}
            q = str(body.get("query") or "").strip()
            if not q:
                return False, "请输入搜索关键词（影视 / 动漫 / 软件 / 游戏等）", {"results": [], "sources": []}
            src = str(body.get("source") or "all").strip().lower()
            cat = str(body.get("category") or "all").strip().lower()
            sort_by = str(body.get("sort") or "seeders").strip().lower()
            try:
                lim = max(10, min(50, int(body.get("limit") or 25)))
            except Exception:
                lim = 25
            res = MT.search_magnets(q, source=src, sort=sort_by, proxy=self._sys_proxy(), limit=lim, category=cat)
            if res.get("ok") and res.get("results"):
                self.log("磁力搜索「%s」命中 %d 条（%s）" % (q, len(res.get("results") or []), res.get("msg", "")), "OK")
            return bool(res.get("ok")), str(res.get("msg") or ""), {
                "results": res.get("results") or [],
                "sources": res.get("sources") or [],
            }

        if act == "magnet_update_trackers":
            if MT is None:
                return False, "magnet_tools 模块不可用", {}
            tr, src = MT.fetch_trackers(CACHE / "trackers.txt", proxy=self._sys_proxy())
            MT.repair_aria2_conf(self.cfg["aria2"]["conf"], trackers=tr)
            live_updated = []
            try:
                if port_open(self.cfg["aria2"]["host"], self.cfg["aria2"]["port"]):
                    self.pr.a_call("aria2.changeGlobalOption", [{"bt-tracker": ",".join(tr)}])
                    live_updated.append("Aria2")
            except Exception:
                pass
            try:
                if port_open(self.cfg["qbit"]["host"], self.cfg["qbit"]["port"]):
                    s, base = self.pr.q_login()
                    prefs = json.dumps({"add_trackers_enabled": True, "add_trackers": "\n".join(tr)})
                    s.post(base + "/api/v2/app/setPreferences", timeout=3.0,
                           headers={"Referer": base + "/", "Origin": base}, data={"json": prefs})
                    live_updated.append("qBittorrent")
            except Exception:
                pass
            hot = (" · 热更新 " + "+".join(live_updated)) if live_updated else ""
            msg = "已更新 %d 个公共 Tracker（来源：%s%s）" % (len(tr), src, hot)
            self.log(msg, "OK")
            return True, msg, {"count": len(tr), "source": src}

        if act == "magnet_boost":
            if MT is None:
                return False, "magnet_tools 模块不可用", {}
            tr, src = MT.fetch_trackers(CACHE / "trackers.txt", proxy=self._sys_proxy())
            dht_ep = ""
            try:
                dht_ep = MT.discover_dht_entry_point(timeout=2.0)
            except Exception:
                dht_ep = ""
            MT.repair_aria2_conf(self.cfg["aria2"]["conf"], trackers=tr, dht_entry=dht_ep)
            boosted = []
            reannounced = 0
            try:
                if port_open(self.cfg["qbit"]["host"], self.cfg["qbit"]["port"]):
                    s, base = self.pr.q_login(timeout=3.5)
                    hdr = {"Referer": base + "/", "Origin": base}
                    turbo = MT.build_qbit_turbo_prefs(tr)
                    s.post(base + "/api/v2/app/setPreferences", timeout=3.5, headers=hdr,
                           data={"json": json.dumps(turbo)})
                    self._qbit_turbo_applied = True
                    tors = s.get(base + "/api/v2/torrents/info", timeout=3.5).json()
                    if isinstance(tors, list) and tors:
                        tr_blob = "\n".join(tr[:120])
                        hashes = []
                        for t in tors:
                            h = str(t.get("hash") or "").strip().lower()
                            if not h:
                                continue
                            hashes.append(h)
                            try:
                                s.post(base + "/api/v2/torrents/addTrackers", timeout=2.5, headers=hdr,
                                       data={"hash": h, "urls": tr_blob})
                            except Exception:
                                pass
                        if hashes:
                            s.post(base + "/api/v2/torrents/reannounce", timeout=3.0, headers=hdr,
                                   data={"hashes": "|".join(hashes)})
                            reannounced = len(hashes)
                    boosted.append("qBittorrent 极速调优(1000连接/200握手)")
            except Exception as ex:
                self.log("qB 加速调优部分跳过：%s" % ex, "WARN")
            try:
                if port_open(self.cfg["aria2"]["host"], self.cfg["aria2"]["port"]):
                    self.pr.a_call("aria2.changeGlobalOption", [{
                        "bt-tracker": ",".join(tr[:120]),
                        "bt-max-peers": "256",
                        "max-connection-per-server": "16",
                    }])
                    boosted.append("Aria2 热更新")
            except Exception:
                pass
            extra_r = (" · 已强制唤醒 %d 个种子" % reannounced) if reannounced else ""
            msg = "🚀 磁力极速破卡完成：注入 %d 个 IP+域名 Tracker（%s）· %s%s" % (
                len(tr), src, " + ".join(boosted) if boosted else "配置已写入", extra_r
            )
            self.log(msg, "OK")
            return True, msg, {"tracker_count": len(tr), "reannounced": reannounced, "dht_entry": dht_ep}

        if act == "magnet_repair":
            if MT is None:
                return False, "magnet_tools 模块不可用", {}
            tr, src = MT.fetch_trackers(CACHE / "trackers.txt", proxy=self._sys_proxy())
            dht_ep = ""
            try:
                dht_ep = MT.discover_dht_entry_point(timeout=2.0)
            except Exception:
                dht_ep = ""
            res = MT.repair_aria2_conf(self.cfg["aria2"]["conf"], trackers=tr, dht_entry=dht_ep)
            ep_txt = (" · DHT 节点 " + dht_ep) if dht_ep else ""
            msg = "磁力/DHT 配置已修复（%d 个 Tracker%s）" % (res.get("tracker_count", len(tr)), ep_txt)
            self.log(msg, "OK")
            return True, msg, {"repair": res, "dht_entry": dht_ep}

        if act == "magnet_probe_dht":
            if MT is None:
                return False, "magnet_tools 模块不可用", {}
            ok, detail = MT.probe_dht_bootstrap()
            ep = ""
            try:
                ep = MT.discover_dht_entry_point(timeout=2.0)
            except Exception:
                pass
            msg = "DHT 探测：%s%s" % (detail, (" · 可用节点 " + ep) if ep else "")
            self.log(msg, "OK" if ok else "WARN")
            return ok, msg, {"detail": detail, "dht_entry": ep}

        if act == "aria2_purge":
            try:
                self.pr.a_call("aria2.purgeDownloadResult")
                self.poll_once()
                return True, "已清空 Aria2 已完成/异常历史记录", {}
            except Exception as ex:
                self.log("清空 Aria2 记录失败 %s" % ex, "WARN")
                return False, "Aria2 未在线或清理失败", {}

        if act in ("aria2_pause", "aria2_resume", "aria2_remove"):
            gid = str(body.get("gid") or "").strip()
            if not gid:
                return False, "缺少任务 GID", {}
            method = {"aria2_pause": "aria2.pause", "aria2_resume": "aria2.unpause",
                      "aria2_remove": "aria2.forceRemove"}[act]
            try:
                try:
                    self.pr.a_call(method, [gid])
                except Exception:
                    if act == "aria2_remove":
                        self.pr.a_call("aria2.removeDownloadResult", [gid])
                    else:
                        raise
                self.poll_once()
                return True, "Aria2 任务操作已执行", {}
            except Exception as ex:
                self.log("Aria2 任务操作失败 %s" % ex, "ERROR")
                return False, "操作失败", {}

        if act in ("qbit_pause", "qbit_resume", "qbit_delete"):
            h = str(body.get("hash") or "").strip()
            if not h:
                return False, "缺少种子 Hash", {}
            try:
                s, base = self.pr.q_login()
                hdr = {"Referer": base + "/", "Origin": base}
                if act == "qbit_pause":
                    for ep in ("/api/v2/torrents/stop", "/api/v2/torrents/pause"):
                        r = s.post(base + ep, timeout=3.0, headers=hdr, data={"hashes": h})
                        if r.status_code == 200:
                            break
                elif act == "qbit_resume":
                    for ep in ("/api/v2/torrents/start", "/api/v2/torrents/resume"):
                        r = s.post(base + ep, timeout=3.0, headers=hdr, data={"hashes": h})
                        if r.status_code == 200:
                            break
                else:
                    s.post(base + "/api/v2/torrents/delete", timeout=3.0, headers=hdr,
                           data={"hashes": h, "deleteFiles": "false"})
                self.poll_once()
                return True, "qB 种子操作已执行", {}
            except Exception as ex:
                self.log("qB 种子操作失败 %s" % ex, "ERROR")
                return False, "操作失败", {}

        if act == "toggle_upscale":
            v = not bool(self.cfg["ui"].get("upscale"))
            self.cfg["ui"]["upscale"] = v
            save_cfg(self.cfg)
            self.log("超分开关 → %s（下次启动 YT 壳/内置下载生效）" % ("开" if v else "关"))
            return True, "2x 超分已%s" % ("开启" if v else "关闭"), {}

        if act == "yt_download":
            import threading
            raw_url = self._clean_video_url(str(body.get("url") or ""))
            if not raw_url:
                return False, "请先粘贴视频链接或分享口令", {}
            with self.lock:
                if self.yt_job.get("running"):
                    return False, "当前已有 YT 视频正在下载，请等待完成或先取消", {}
                quality = str(body.get("quality") or "best")
                cookies = str(body.get("cookies") or "auto")
                cookies_file = str(body.get("cookies_file") or "").strip()
                save_dir = str(body.get("save_dir") or "").strip()
                upscale = bool(body.get("upscale", self.cfg["ui"].get("upscale")))
                self.cfg["yt"]["cookies"] = cookies
                self.cfg["yt"]["cookies_file"] = cookies_file
                if save_dir:
                    self.cfg["yt"]["output"] = save_dir
                self.cfg["ui"]["upscale"] = upscale
                save_cfg(self.cfg)
                self.yt_job.update({
                    "running": True, "pid": None, "url": raw_url,
                    "quality": quality, "cookies": cookies, "cookies_file": cookies_file,
                    "pct": 0.0, "speed": "", "eta": "", "status": "初始化中…", "file": "",
                })
            t = threading.Thread(
                target=self._run_yt_worker,
                args=(raw_url, quality, cookies, cookies_file, upscale),
                daemon=True,
            )
            t.start()
            return True, "已启动内置 YT 视频下载", {}

        if act == "yt_cancel":
            with self.lock:
                pid = self.yt_job.get("pid")
            if pid and pid_alive(pid):
                kill_tree(pid)
                with self.lock:
                    self.yt_job["status"] = "已取消"
                    self.yt_job["running"] = False
                    self.yt_job["pid"] = None
                self._yt_append_log("[WARN] 已取消下载并结束进程树 PID=%s" % pid)
                self.log("已取消 YT 工坊下载 PID %s" % pid, "WARN")
                return True, "已取消下载并清理进程树", {}
            return False, "当前没有运行中的内置 YT 下载", {}

        if act == "yt_clear_log":
            with self.lock:
                self.yt_job["logs"] = []
            return True, "YT 日志已清空", {}

        if act == "music_search":
            if MS is None:
                return False, "media_studio 模块不可用", {}
            q = str(body.get("query") or "").strip()
            src = str(body.get("source") or "all").strip().lower()
            if not q:
                return False, "请输入歌名、歌手或歌词片段", {}
            res = MS.search_songs(q, source=src, ytdlp=self._find_ytdlp(), proxy=self._sys_proxy())
            with self.lock:
                self.music_job["query"] = q
                self.music_job["source"] = src
                self.music_job["results"] = res
            self.log("音乐检索 [%s]「%s」命中 %d 首" % (src, q, len(res)), "OK" if res else "WARN")
            return bool(res), ("找到 %d 首歌曲" % len(res)) if res else "未找到匹配歌曲，请更换关键词或切换音源", {"results": res}

        if act == "music_chart":
            if MS is None:
                return False, "media_studio 模块不可用", {}
            cid = str(body.get("chart_id") or body.get("chart") or "hot").strip().lower()
            try:
                limit = max(5, min(60, int(body.get("limit") or 40)))
            except Exception:
                limit = 40
            data = MS.fetch_music_chart(cid, limit=limit)
            rows = data.get("results") or []
            if rows and not body.get("silent"):
                with self.lock:
                    self.music_job["results"] = rows
            cname = (data.get("chart") or {}).get("name") or cid
            if not body.get("silent"):
                self.log("载入音乐榜单 [%s] 共 %d 首" % (cname, len(rows)), "OK" if rows else "WARN")
            return bool(rows), data.get("msg") or "榜单加载完成", {
                "chart": data.get("chart"),
                "results": rows,
                "charts": list(MS.MUSIC_CHARTS),
            }

        if act == "music_lyrics":
            if MS is None:
                return False, "media_studio 模块不可用", {}
            sid = str(body.get("song_id") or "").strip()
            title = str(body.get("title") or "").strip()
            artist = str(body.get("artist") or "").strip()
            query = str(body.get("query") or "").strip()
            audio_path = str(body.get("audio_path") or "").strip()
            lyr = MS.fetch_song_lyrics(song_id=sid, title=title, artist=artist, query=query, audio_path=audio_path)
            if lyr.get("lines"):
                with self.lock:
                    self.music_job["lyrics"] = lyr
            return bool(lyr.get("ok")), lyr.get("msg") or "歌词查询完成", {"lyrics": lyr}

        if act == "music_play":
            if MS is None:
                return False, "media_studio 模块不可用", {}
            import uuid
            from urllib.parse import quote
            title = str(body.get("title") or "").strip()
            artist = str(body.get("artist") or "").strip()
            url = str(body.get("url") or "").strip()
            query = str(body.get("query") or "").strip()
            bvid = str(body.get("bvid") or "").strip()
            info = MS.resolve_music_stream(
                title=title, artist=artist, url=url, query=query, bvid=bvid,
                ytdlp=self._find_ytdlp(), proxy=self._sys_proxy(), music_dir=self.music_output(),
            )
            if not info.get("ok"):
                return False, info.get("msg") or "未解析到可播放音频流", {}
            if info.get("is_local") and info.get("local_path"):
                lp = info["local_path"]
                return True, info.get("msg") or "本地音频就绪", {
                    "play_url": "/api/media?path=" + quote(lp, safe="") + "&t=" + str(int(time.time())),
                    "local_path": lp,
                    "is_local": True,
                    "source": info.get("source") or "本地",
                }
            tok = uuid.uuid4().hex[:16]
            with self.lock:
                self.stream_tokens[tok] = {
                    "url": info["stream_url"],
                    "headers": dict(info.get("headers") or {}),
                    "mime": info.get("mime") or "audio/mp4",
                    "use_proxy": bool(info.get("use_proxy")),
                    "ts": time.time(),
                }
                if len(self.stream_tokens) > 30:
                    oldest = sorted(self.stream_tokens.items(), key=lambda kv: kv[1]["ts"])[:10]
                    for k, _ in oldest:
                        self.stream_tokens.pop(k, None)
            self.log("在线播歌 [%s] %s" % (info.get("source") or "流媒体", title or query), "OK")
            return True, info.get("msg") or "音频流已就绪", {
                "play_url": "/api/stream_audio?id=" + tok,
                "local_path": "",
                "is_local": False,
                "source": info.get("source") or "在线流",
            }

        if act == "music_download":
            import threading
            url = str(body.get("url") or "").strip()
            q = str(body.get("query") or "").strip()
            title = str(body.get("title") or "").strip()
            artist = str(body.get("artist") or "").strip()
            fmt = str(body.get("fmt") or "mp3").strip().lower()
            save_dir = str(body.get("save_dir") or "").strip()
            if not url and not q and not title:
                return False, "请先选择歌曲或输入歌名/音频链接", {}
            with self.lock:
                if self.music_job.get("running"):
                    return False, "当前已有歌曲正在下载，请稍候或先取消", {}
                if save_dir:
                    self.cfg.setdefault("paths", {})["music"] = save_dir
                    save_cfg(self.cfg)
                self.music_job.update({
                    "running": True, "pid": None, "fmt": fmt,
                    "title": title or q, "artist": artist,
                    "pct": 0.0, "speed": "", "eta": "", "status": "初始化下载…", "file": "",
                })
            t = threading.Thread(
                target=self._run_music_worker,
                args=(url, q or title, title, artist, fmt, save_dir or self.music_output()),
                daemon=True,
            )
            t.start()
            return True, "开始下载「%s」(%s)" % (title or q or "音频", fmt.upper()), {}

        if act == "music_cancel":
            with self.lock:
                pid = self.music_job.get("pid")
                self.music_job["running"] = False
                self.music_job["status"] = "已取消"
            if pid and pid_alive(pid):
                kill_tree(pid)
                self._music_append_log("[WARN] 已取消下载 PID=%s" % pid)
                return True, "已取消音乐下载", {}
            return True, "已重置音乐下载状态", {}

        if act == "music_clear_log":
            with self.lock:
                self.music_job["logs"] = []
            return True, "音乐日志已清空", {}

        if act == "voice_install_f5":
            import threading
            with self.lock:
                if self.voice_job.get("installing") or self.voice_job.get("running"):
                    return False, "声音工坊当前有任务在运行，请等待完成", {}
                self.voice_job.update({
                    "installing": True, "running": True, "pid": None,
                    "pct": 5.0, "status": "正在初始化 F5-TTS (CUDA) 独立环境…",
                })
            t = threading.Thread(target=self._run_voice_install_f5_worker, daemon=True)
            t.start()
            return True, "已启动 F5-TTS 独立环境一键部署（不污染主环境，详见右侧日志）", {}

        if act == "voice_synthesize":
            import threading
            engine = str(body.get("engine") or "edge").strip().lower()
            text = str(body.get("text") or "").strip()
            ref_text = str(body.get("ref_text") or "").strip()
            voice_id = str(body.get("voice_id") or "zh-CN-XiaoxiaoNeural").strip()
            rate = str(body.get("rate") or "+0%").strip()
            pitch = str(body.get("pitch") or "+0Hz").strip()
            api_url = str(body.get("api_url") or self.voice_job.get("api_url") or "").strip()
            save_dir = str(body.get("save_dir") or "").strip()
            if not text:
                return False, "请先输入要合成或克隆朗读的文案", {}
            with self.lock:
                if self.voice_job.get("running"):
                    return False, "当前已有语音合成任务在进行中，请稍候", {}
                if save_dir:
                    self.cfg.setdefault("paths", {})["voice"] = save_dir
                if api_url:
                    self.cfg.setdefault("voice", {})["api_url"] = api_url
                save_cfg(self.cfg)
                self.voice_job.update({
                    "running": True, "pid": None, "engine": engine,
                    "ref_text": ref_text, "api_url": api_url,
                    "pct": 10.0, "status": "正在启动语音引擎…", "out_file": "",
                })
            t = threading.Thread(
                target=self._run_voice_synth_worker,
                args=(engine, text, ref_text, voice_id, rate, pitch, api_url, save_dir or self.voice_output()),
                daemon=True,
            )
            t.start()
            return True, "已开始语音合成/克隆", {}

        if act == "voice_cancel":
            with self.lock:
                pid = self.voice_job.get("pid")
                self.voice_job["running"] = False
                self.voice_job["installing"] = False
                self.voice_job["status"] = "已取消"
            if pid and pid_alive(pid):
                kill_tree(pid)
                self._voice_append_log("[WARN] 已取消任务 PID=%s" % pid)
                return True, "已终止声音任务进程树", {}
            return True, "已重置声音任务状态", {}

        if act == "voice_clear_log":
            with self.lock:
                self.voice_job["logs"] = []
            return True, "声音工坊日志已清空", {}

        if act == "aigc_start_comfy":
            cc = self.cfg.get("comfyui") or {}
            if not cc.get("enabled"):
                return False, "个人 ComfyUI 未在本机配置启用", {}
            url = str(cc.get("url") or "http://127.0.0.1:8188")
            if MS and MS.probe_comfyui_server(url, timeout=1.2).get("online"):
                self._aigc_env_ts = 0.0
                return True, "本地 ComfyUI 已在线 ✔", {}
            bat = Path(str(cc.get("start_bat") or ""))
            if not bat.is_file():
                root = Path(str(cc.get("root") or ""))
                for cand in ("run_minimax_h3.bat", "run_nvidia_gpu.bat", "run.bat"):
                    if (root / cand).is_file():
                        bat = root / cand
                        break
            if not bat.is_file():
                return False, "未找到本地 ComfyUI 启动脚本", {}
            try:
                kw = {"start_new_session": True} if not IS_WIN else {}
                proc = subprocess.Popen(script_cmd(bat), cwd=str(bat.parent), **kw)
                self.pids["comfyui"] = proc.pid
                save_pids(self.pids)
                self._aigc_env_ts = 0.0
                self._aigc_append_log("[INFO] 已拉起本地 ComfyUI PID=%s (%s)" % (proc.pid, bat.name))
                self.log("拉起本地 ComfyUI PID %s" % proc.pid, "OK")
                return True, "正在后台启动本地 ComfyUI，端口就绪后自动可用", {}
            except Exception as ex:
                self.log("启动 ComfyUI 失败 %s" % ex, "ERROR")
                return False, "启动本地 ComfyUI 失败：%s" % ex, {}

        if act == "aigc_stop_comfy":
            pid = self.pids.get("comfyui")
            if pid and pid_alive(pid):
                kill_tree(pid)
                self.pids.pop("comfyui", None)
                save_pids(self.pids)
                self._aigc_env_ts = 0.0
                self._aigc_append_log("[WARN] 已关闭本地 ComfyUI PID=%s" % pid)
                return True, "已安全关闭本地 ComfyUI", {}
            return False, "未找到本面板记录的 ComfyUI 进程", {}

        if act == "aigc_free_vram":
            if MS is None:
                return False, "media_studio 模块不可用", {}
            cc = self.cfg.get("comfyui") or {}
            url = str(cc.get("url") or cc.get("base_url") or "http://127.0.0.1:8188")
            ok, msg = MS.comfyui_free_vram(url)
            self._aigc_env_ts = 0.0
            self._aigc_append_log(("[OK] " if ok else "[WARN] ") + msg)
            return ok, msg, {}

        if act == "aigc_generate":
            import threading
            prompt = str(body.get("prompt") or "").strip()
            if not prompt:
                return False, "请先输入生图或生视频提示词", {}
            engine = str(body.get("engine") or "owner_comfy").strip().lower()
            mode = str(body.get("mode") or "t2i").strip().lower()
            neg_prompt = str(body.get("neg_prompt") or "").strip()
            width = int(body.get("width") or (832 if mode in ("i2v", "t2v") else 1024))
            height = int(body.get("height") or (480 if mode in ("i2v", "t2v") else 576))
            steps = int(body.get("steps") or (4 if mode in ("i2v", "t2v") else 8))
            length = int(body.get("length") or 33)
            seed = int(body.get("seed") if body.get("seed") not in ("", None) else -1)
            save_dir = str(body.get("save_dir") or "").strip()
            with self.lock:
                if self.aigc_job.get("running"):
                    return False, "当前已有 AI 生成任务在运行，请等待完成或先取消", {}
                if save_dir:
                    self.cfg.setdefault("paths", {})["aigc"] = save_dir
                    save_cfg(self.cfg)
                ff = str(body.get("first_frame") or self.aigc_job.get("first_frame") or "").strip()
                self.aigc_job.update({
                    "running": True, "cancel": False,
                    "engine": engine, "mode": mode, "prompt": prompt, "neg_prompt": neg_prompt,
                    "width": width, "height": height, "steps": steps, "length": length, "seed": seed,
                    "pct": 5.0, "status": "已提交生成任务…",
                })
            t = threading.Thread(
                target=self._run_aigc_worker,
                args=(engine, mode, prompt, neg_prompt, width, height, steps, length, seed, ff, save_dir or self.aigc_output()),
                daemon=True,
            )
            t.start()
            lbl = {"t2i": "AI 文生图", "i2v": "AI 图生视频", "t2v": "AI 文生视频"}.get(mode, "AI 生成")
            return True, "已启动 %s 任务，完成后自动在右侧画廊直出" % lbl, {}

        if act == "aigc_cancel":
            with self.lock:
                self.aigc_job["cancel"] = True
                self.aigc_job["status"] = "正在取消…"
            return True, "已发送取消信号", {}

        if act == "aigc_clear_log":
            with self.lock:
                self.aigc_job["logs"] = []
            return True, "AI 创作日志已清空", {}

        if act == "aigc_use_gallery_frame":
            fp = str(body.get("path") or "").strip()
            target = self._is_allowed_media(fp)
            if target is None:
                return False, "图片文件不可访问", {}
            with self.lock:
                self.aigc_job["first_frame"] = str(target)
                self.aigc_job["first_frame_name"] = target.name
            return True, "已将「%s」设为图生视频首帧 ✔" % target.name, {"first_frame": str(target), "first_frame_name": target.name}

        if act == "aigc_save_custom":
            cc = self.cfg.setdefault("comfyui", {})
            cc["custom_mode"] = str(body.get("custom_mode") or "comfyui").strip().lower()
            cc["custom_url"] = str(body.get("custom_url") or "").strip()
            new_key = str(body.get("custom_api_key") or "").strip()
            if new_key:
                cc["custom_api_key"] = new_key
            elif body.get("clear_key"):
                cc["custom_api_key"] = ""
            cc["custom_model"] = str(body.get("custom_model") or "").strip()
            cc["custom_workflow_json"] = str(body.get("custom_workflow_json") or "").strip()
            save_cfg(self.cfg)
            self._aigc_env_ts = 0.0
            self.log("已保存自定义本地模型接入配置 (%s)" % cc["custom_mode"], "OK")
            return True, "自定义本地模型配置已保存并生效 ✔", {}

        if act == "aigc_prompt_search":
            if PE is None:
                return False, "prompt_engine 模块不可用", {}
            q = str(body.get("query") or "").strip()
            cat = str(body.get("category") or "all").strip().lower()
            mode = str(body.get("mode") or "t2i").strip().lower()
            source = str(body.get("source") or "all").strip().lower()
            limit = int(body.get("limit") or 24)
            page = int(body.get("page") or 1)
            only_img = bool(body.get("only_with_image"))
            shuffle_seed = int(body.get("shuffle_seed") or 0)
            res = PE.search_prompts(
                query=q, category=cat, mode=mode, limit=limit,
                page=page, source=source, only_with_image=only_img, shuffle_seed=shuffle_seed,
            )
            return bool(res.get("ok")), res.get("msg") or "提示词检索完成", {
                "results": res.get("results") or [],
                "categories": res.get("categories") or [],
                "total": res.get("total") or 0,
                "page": res.get("page") or 1,
                "has_more": bool(res.get("has_more")),
                "elapsed_ms": res.get("elapsed_ms") or 0,
                "skill_status": res.get("skill_status") or {},
                "attribution": res.get("attribution") or "",
            }

        if act == "aigc_prompt_sync":
            if PE is None:
                return False, "prompt_engine 模块不可用", {}
            self.log("开始同步云端 20,000+ 社区提示词 Skill 词库...", "INFO")
            res = PE.sync_skill_prompt_library(proxy=self._sys_proxy())
            self.log(res.get("msg") or "提示词 Skill 同步完成", "OK" if res.get("ok") else "WARN")
            return bool(res.get("ok")), res.get("msg") or "同步完成", {
                "skill_status": res.get("skill_status") or {},
            }

        if act == "aigc_prompt_remix":
            if PE is None:
                return False, "prompt_engine 模块不可用", {}
            tpl_prompt = str(body.get("template_prompt") or "").strip()
            tpl_title = str(body.get("template_title") or "").strip()
            user_idea = str(body.get("user_idea") or "").strip()
            mode = str(body.get("mode") or "t2i").strip().lower()
            cx = self.cfg.get("codex") or {}
            chat_fn = MS.codex_chat_request if MS is not None else None
            res = PE.remix_prompt_with_skill(
                template_prompt=tpl_prompt,
                user_idea=user_idea,
                template_title=tpl_title,
                mode=mode,
                codex_cfg=cx,
                chat_fn=chat_fn,
                proxy=self._sys_proxy(),
            )
            if res.get("ok"):
                self.log("Skill Remix 模板精改完成（%d 套方案）" % len(res.get("variants") or []), "OK")
            return bool(res.get("ok")), res.get("msg") or "精改完成", {
                "variants": res.get("variants") or [],
            }

        if act == "aigc_prompt_optimize":
            if PE is None:
                return False, "prompt_engine 模块不可用", {}
            raw_inp = str(body.get("prompt") or body.get("query") or "").strip()
            mode = str(body.get("mode") or "t2i").strip().lower()
            style_hint = str(body.get("style") or "").strip()
            count = int(body.get("count") or 3)
            cx = self.cfg.get("codex") or {}
            chat_fn = MS.codex_chat_request if MS is not None else None
            res = PE.optimize_prompt_with_ai(
                raw_input=raw_inp,
                mode=mode,
                style_hint=style_hint,
                codex_cfg=cx,
                chat_fn=chat_fn,
                proxy=self._sys_proxy(),
                count=count,
            )
            if res.get("ok"):
                self.log("Skill-RAG AI 提示词优化完成（%d 套方案）" % len(res.get("variants") or []), "OK")
            return bool(res.get("ok")), res.get("msg") or "优化完成", {
                "variants": res.get("variants") or [],
                "rag_count": res.get("rag_count") or 0,
            }

        if act == "codex_save_cfg":
            cx = self.cfg.setdefault("codex", {})
            cx["base_url"] = str(body.get("base_url") or "").strip()
            new_k = str(body.get("api_key") or "").strip()
            if new_k:
                cx["api_key"] = new_k
            cx["model"] = str(body.get("model") or "gpt-5.3-codex").strip()
            cx["api_style"] = str(body.get("api_style") or "auto").strip().lower()
            save_cfg(self.cfg)
            self.log("已保存赛博小怪兽 Codex 中转配置（模型：%s）" % cx["model"], "OK")
            return True, "赛博小怪兽中转配置已保存到本地 config.json ✔", {}

        if act == "codex_test":
            if MS is None:
                return False, "media_studio 模块不可用", {}
            cx = self.cfg.get("codex") or {}
            base = str(body.get("base_url") or cx.get("base_url") or "").strip()
            key = str(body.get("api_key") or "").strip() or str(cx.get("api_key") or "").strip()
            ok, msg, models = MS.codex_list_models(base, key, proxy=self._sys_proxy())
            return ok, msg, {"models": models}

        if act == "codex_chat":
            if MS is None:
                return False, "media_studio 模块不可用", {}
            cx = self.cfg.get("codex") or {}
            msgs = body.get("messages") or []
            if not isinstance(msgs, list) or not msgs:
                q = str(body.get("prompt") or "").strip()
                if not q:
                    return False, "请输入想问赛博小怪兽的问题", {}
                msgs = [{"role": "user", "content": q}]
            active_view = str(body.get("view") or "cockpit")
            aigc_env = self._get_aigc_env_cached()

            # Auto-invoke built-in 20,000+ Prompt Skill inside the console whenever user asks about prompts/drawing/video!
            skill_prompts = []
            skill_ctx = ""
            if PE is not None:
                last_user = ""
                for m in reversed(msgs):
                    if isinstance(m, dict) and m.get("role") == "user":
                        last_user = str(m.get("content") or "").strip()
                        break
                prompt_triggers = (
                    "提示词", "prompt", "生图", "画画", "画一个", "画张", "画幅", "出图",
                    "模板", "skill", "生视频", "运镜", "封面", "海报", "头像", "写真",
                    "wan2", "z-image", "comfy", "赛博", "古风", "二次元",
                )
                low_u = last_user.lower()
                if last_user and (active_view == "aigc" or any(k in low_u for k in prompt_triggers)):
                    import re as _re
                    q_clean = _re.sub(
                        r"(帮我|请|找几个|找一些|推荐|给我|写一个|写个|生成|关于|的|提示词|模板|prompt|skill|画室|调用|用)",
                        " ", last_user, flags=_re.I
                    ).strip()
                    p_mode = "t2v" if any(k in low_u for k in ("视频", "运镜", "wan2", "动态")) else "t2i"
                    sr = PE.search_prompts(query=q_clean or last_user, category="all", mode=p_mode, limit=4, page=1, source="all")
                    skill_prompts = (sr.get("results") or [])[:3]
                    if skill_prompts:
                        lines = [
                            f"{idx}. [{it.get('source','')}] {it.get('title','')}: {str(it.get('prompt',''))[:260]}"
                            for idx, it in enumerate(skill_prompts, 1)
                        ]
                        skill_ctx = (
                            "\n【已自动调用控制台内置 20,000+ 提示词 Skill 检索到以下实战范本，下方聊天卡片已附带一键送入画室/生成按钮，"
                            "你可以直接点评、精选或帮用户改写成更精准的 Z-Image Turbo / Wan 2.2 提示词】：\n"
                            + "\n".join(lines)
                        )

            sys_prompt = (
                "你是「赛博小怪兽」，内嵌在 DownloadStack 3D Spatial Command OS 桌面控制台里的全能智能体助手。"
                "说话风格灵动专业、简洁直击重点，优先用中文回答。\n"
                "本软件内置全部 10 大本地工坊（严禁让用户跳外部网页或打开外部程序）：控制台、任务队列、内置 AriaNg、内置 qBittorrent、5源磁力搜索与DHT修复、"
                "站内原画4K影院(WebGL2 4K画质修复+看完即删)、全平台视频下载(yt-dlp)、音乐6大榜单+3D歌词舞台、开源AI声音克隆(F5-TTS/神经配音)、"
                "AI画室(本地ComfyUI Z-Image Turbo生图 + Wan 2.2 I2V生视频 + 内置 20,000+ 提示词 Skill 引擎与 Skill Remix)。\n"
                "当前本机实时状态（脱敏）：Aria2=%s, qBittorrent=%s, YT运行中=%s, 本地ComfyUI在线=%s, 当前页面=%s。%s"
                % (
                    "在线" if self.pr.a.get("on") else "离线",
                    "在线" if self.pr.q.get("on") else "离线",
                    "是" if self.yt_job.get("running") else "否",
                    "在线" if (aigc_env.get("server") or {}).get("online") else "离线",
                    active_view,
                    skill_ctx,
                )
            )
            ok, reply = MS.codex_chat_request(
                base_url=str(cx.get("base_url") or ""),
                api_key=str(cx.get("api_key") or ""),
                model=str(cx.get("model") or "gpt-5.3-codex"),
                messages=msgs,
                system_prompt=sys_prompt,
                api_style=str(cx.get("api_style") or "auto"),
                proxy=self._sys_proxy(),
            )
            return ok, ("已回复" if ok else reply), {"reply": reply, "skill_prompts": skill_prompts}

        if act == "start_y":
            bat = Path(self.cfg["yt"]["bat"])
            if not bat.exists():
                bat = Path(self.cfg["yt"]["bat2"])
            if not str(bat) or not bat.exists():
                cand = [
                    Path(str(self.cfg["scripts"].get("start") or "")).parent / "ControlPanel" / "ytdl_gui.py",
                    ROOT / "ControlPanel" / "ytdl_gui.py",
                    APP_DIR / "ytdl_gui.py",
                ]
                hit = next((c for c in cand if c.is_file()), None)
                if hit is None:
                    self.log("未找到 YT 下载器 ytdl_gui.py", "ERROR")
                    return False, "未找到 YT 下载器", {}
                py = str(ROOT / ".venv" / ("Scripts/python.exe" if IS_WIN else "bin/python"))
                if not Path(py).is_file():
                    py = sys.executable
                bat = hit
                cmd_override = [py, "-B", str(hit)]
            else:
                cmd_override = script_cmd(bat)
            pid = self.pids.get("yt")
            if pid and pid_alive(pid):
                self.log("YT 壳已在运行，跳过", "WARN")
                return True, "YT 下载壳已在运行", {}
            try:
                env = os.environ.copy()
                env["UPSCALE"] = "1" if self.cfg["ui"].get("upscale") else "0"
                px = self._sys_proxy()
                if px:
                    env["HTTP_PROXY"] = env["HTTPS_PROXY"] = env["http_proxy"] = env["https_proxy"] = px
                    env.pop("ALL_PROXY", None)
                    env.pop("all_proxy", None)
                    env["NO_PROXY"] = env["no_proxy"] = "localhost,127.0.0.1,::1,.local"
                else:
                    for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
                        env.pop(k, None)
                # 交互式视频下载壳允许展示窗口
                kw = {"start_new_session": True} if not IS_WIN else {}
                proc = subprocess.Popen(cmd_override, cwd=str(bat.parent), env=env, **kw)
                self.pids["yt"] = proc.pid
                save_pids(self.pids)
                self.log("启动 YT 下载壳 PID %s（超分：%s｜代理：%s）"
                         % (proc.pid, "开" if env["UPSCALE"] == "1" else "关", px if px else "直连"), "OK")
                self.poll_once()
                return True, "YT 下载壳已启动", {}
            except Exception as ex:
                self.log("启动 YT 壳失败 %s" % ex, "ERROR")
                return False, "启动 YT 壳失败", {}

        if act == "stop_y":
            pid = self.pids.get("yt")
            if pid and pid_alive(pid):
                kill_tree(pid)
                self.pids.pop("yt", None)
                save_pids(self.pids)
                self.log("已关闭 YT 壳 PID %s" % pid, "WARN")
                self.poll_once()
                return True, "已关闭 YT 下载壳", {}
            self.log("没有本面板记录的 YT 壳进程", "WARN")
            return False, "未找到运行中的 YT 壳进程", {}

        if act == "backup":
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
                return True, "已备份 %d 个配置文件" % n, {}
            except Exception as ex:
                self.log("备份失败 %s" % ex, "ERROR")
                return False, "备份失败", {}

        if act == "selfcheck":
            self.log("开始一键自检")
            for name, port in (("aria2", self.cfg["aria2"]["port"]),
                               ("webui", self.cfg["qbit"]["port"])):
                on = port_open("127.0.0.1", port)
                self.log("  端口 %s:%s %s" % (name, port, "在线" if on else "未监听"), "OK" if on else "WARN")
            self.log("  AriaNg 内置挂载 %s" % ("就绪" if self._ariang_dir() else "缺失"),
                     "OK" if self._ariang_dir() else "WARN")
            for name, path in (("aria2c", self.cfg["aria2"]["exe"]),
                               ("aria2.conf", self.cfg["aria2"]["conf"]),
                               ("qBittorrent.ini", str(Path(self.cfg["qbit"]["config_dir"]) / "qBittorrent.ini"))):
                ok = Path(path).exists()
                self.log("  %s %s" % (name, "存在" if ok else "缺失"), "OK" if ok else "ERROR")
            try:
                t = CACHE / "_w.tmp"
                t.write_text("x", encoding="utf-8")
                t.unlink(missing_ok=True)
                self.log("  缓存目录可写 (%s)" % CACHE, "OK")
            except Exception as ex:
                self.log("  缓存目录不可写 %s" % ex, "ERROR")
            self.handle_action({"action": "test_a"})
            self.handle_action({"action": "test_q"})
            return True, "一键自检完成，详见日志", {}

        if act == "clean_logs":
            n = 0
            try:
                for f in Path(self.cfg["aria2"]["logdir"]).glob("*"):
                    if f.is_file():
                        f.unlink()
                        n += 1
            except Exception:
                pass
            self.log("清理 Aria2 日志 %d 个" % n, "OK")
            return True, "已清理 %d 个日志文件" % n, {}

        if act == "clean_cache":
            n = 0
            freed = 0
            try:
                pc = getattr(self, "_probe_cache", None)
                if isinstance(pc, dict):
                    pc.clear()
            except Exception:
                pass
            try:
                for f in CACHE.rglob("*"):
                    if f.is_file() and f.name.lower() != "trackers.txt":
                        try:
                            freed += int(f.stat().st_size)
                            f.unlink()
                            n += 1
                        except Exception:
                            pass
            except Exception:
                pass
            try:
                if port_open(self.cfg["aria2"]["host"], self.cfg["aria2"]["port"]):
                    self.pr.a_call("aria2.purgeDownloadResult")
            except Exception:
                pass
            v = float(freed)
            for unit in ("B", "KB", "MB", "GB"):
                if v < 1024.0 or unit == "GB":
                    fs = ("%d %s" % (int(v), unit)) if unit == "B" else ("%.2f %s" % (v, unit))
                    break
                v /= 1024.0
            msg = "已清理 %d 个缓存文件（释放 %s）" % (n, fs)
            self.log(msg, "OK")
            return True, msg, {"count": n, "freed_bytes": freed}

        if act == "purge_all":
            rm_files = bool(body.get("remove_files"))
            cleared = {"aria2": 0, "qbit": 0, "cache": 0, "ctrl": 0}
            errs = []
            try:
                tasks = (self.pr.a_call("aria2.tellActive") or [])
                try:
                    tasks += (self.pr.a_call("aria2.tellWaiting", [0, 1000]) or [])
                except Exception:
                    pass
                for t in tasks:
                    gid = (t or {}).get("gid")
                    if not gid:
                        continue
                    try:
                        self.pr.a_call("aria2.forceRemove", [gid])
                        cleared["aria2"] += 1
                    except Exception:
                        pass
                try:
                    self.pr.a_call("aria2.purgeDownloadResult")
                except Exception:
                    pass
            except Exception as ex:
                errs.append("Aria2: %s" % str(ex)[:60])
            try:
                if port_open(self.cfg["qbit"]["host"], self.cfg["qbit"]["port"]):
                    s, base = self.pr.q_login()
                    hdr = {"Referer": base + "/", "Origin": base}
                    r = s.post(base + "/api/v2/torrents/delete", timeout=8.0, headers=hdr,
                               data={"hashes": "all", "deleteFiles": "true" if rm_files else "false"})
                    if r.status_code == 200:
                        cleared["qbit"] = 1
                    else:
                        errs.append("qB: HTTP %d" % r.status_code)
            except Exception as ex:
                errs.append("qB: %s" % str(ex)[:60])
            try:
                for f in CACHE.rglob("*"):
                    if f.is_file():
                        f.unlink()
                        cleared["cache"] += 1
            except Exception:
                pass
            if rm_files:
                try:
                    droot = Path(str((self.cfg.get("misc") or {}).get("downloads_root")
                                     or (self.cfg.get("paths") or {}).get("downloads") or ""))
                    if droot and droot.is_dir():
                        for f in droot.rglob("*"):
                            try:
                                if f.is_file() and f.suffix.lower() in (".aria2", ".torrent", ".!qb", ".parts"):
                                    f.unlink()
                                    cleared["ctrl"] += 1
                            except Exception:
                                pass
                except Exception:
                    pass
            self.poll_once()
            msg = "已清空 Aria2 %d 个任务、qB 全部任务（%s）、缓存 %d 个、控制文件残骸 %d 个" % (
                cleared["aria2"], "含文件" if rm_files else "保留文件", cleared["cache"], cleared["ctrl"])
            if errs:
                msg += "；" + "；".join(errs)
            self.log(msg, "WARN" if errs else "OK")
            return True, msg, {"cleared": cleared}

        if act == "stop_all":
            self.log("一键全部停止：Aria2 → qBittorrent → YT 壳", "WARN")
            self.handle_action({"action": "stop_a"})
            self.handle_action({"action": "stop_q"})
            self.handle_action({"action": "stop_y"})
            return True, "已按安全顺序停止全部服务", {}

        if act == "open_path":
            key = body.get("key") or ""
            dl_base = Path(self.cfg.get("paths", {}).get("downloads") or str(DL_HOME))
            mapping = {
                "aria2_conf": self.cfg["aria2"]["conf"],
                "aria2_logdir": self.cfg["aria2"]["logdir"],
                "aria2_dl": str(dl_base / "aria2"),
                "qbit_cfg": self.cfg["qbit"]["config_dir"],
                "qbit_dl": self.cfg["qbit"]["save_dir"],
                "yt_out": self.yt_output(),
                "music_dl": self.music_output(),
                "voice_dl": self.voice_output(),
                "aigc_dl": self.aigc_output(),
                "downloads": str(dl_base),
            }
            select_file = False
            if key == "custom":
                raw_p = str(body.get("path") or "").strip()
                p_obj = Path(raw_p) if raw_p else None
                if p_obj and body.get("reveal"):
                    select_file = p_obj.is_file()
                    target = str(p_obj) if select_file else str(p_obj)
                else:
                    target = raw_p
            else:
                custom_override = str(body.get("path") or "").strip()
                target = custom_override if (key == "yt_out" and custom_override) else mapping.get(key, "")
                if key == "yt_out":
                    last_f = str(self.yt_job.get("file") or "").strip()
                    if last_f and Path(last_f).is_file():
                        target = last_f
                        select_file = True
            if key in ("aria2_dl", "qbit_dl", "yt_out", "music_dl", "voice_dl", "aigc_dl", "downloads") and target and not select_file:
                try:
                    Path(target).mkdir(parents=True, exist_ok=True)
                except Exception:
                    pass
            ok, msg = self._open_local(target, select_file=select_file)
            return ok, msg, {}

        if act == "clear_log":
            with self.lock:
                self.logs = []
            return True, "日志已清空", {}

        if act == "export_log":
            try:
                out = LOGS / ("export-%s.log" % datetime.now().strftime("%Y%m%d-%H%M%S"))
                with self.lock:
                    content = "\n".join(self.logs)
                out.write_text(content, encoding="utf-8")
                self.log("日志已导出 %s" % out, "OK")
                return True, "日志已导出", {}
            except Exception as ex:
                self.log("导出失败 %s" % ex, "ERROR")
                return False, "导出失败", {}

        if act == "save_cfg":
            try:
                self.cfg["aria2"]["host"] = str(body.get("a_host") or "127.0.0.1").strip()
                self.cfg["aria2"]["port"] = int(str(body.get("a_port") or 6800).strip())
                self.cfg["aria2"]["secret"] = str(body.get("a_secret") or "").strip()
                self.cfg["qbit"]["host"] = str(body.get("q_host") or "127.0.0.1").strip()
                self.cfg["qbit"]["port"] = int(str(body.get("q_port") or 8080).strip())
                self.cfg["qbit"]["user"] = str(body.get("q_user") or "admin").strip()
                self.cfg["qbit"]["pass"] = str(body.get("q_pass") or "")
                self.cfg["qbit"]["save_dir"] = str(body.get("q_save") or "").strip()
                self.cfg["yt"]["bat"] = str(body.get("yt_bat") or "").strip()
                if "downloads" in body and str(body.get("downloads") or "").strip():
                    self.cfg["paths"]["downloads"] = str(body.get("downloads")).strip()
                if "music_dir" in body:
                    self.cfg.setdefault("paths", {})["music"] = str(body.get("music_dir") or "").strip()
                if "voice_dir" in body:
                    self.cfg.setdefault("paths", {})["voice"] = str(body.get("voice_dir") or "").strip()
                if "aigc_dir" in body:
                    self.cfg.setdefault("paths", {})["aigc"] = str(body.get("aigc_dir") or "").strip()
                if "yt_out" in body:
                    self.cfg["yt"]["output"] = str(body.get("yt_out") or "").strip()
                save_cfg(self.cfg)
                self.pr.cfg = self.cfg
                self.pr._q_hold_until = 0
                self.log("设置已保存并生效", "OK")
                self.poll_once()
                return True, "设置已保存", {}
            except Exception as ex:
                self.log("保存失败 %s" % ex, "ERROR")
                return False, "保存失败", {}

        if act == "reset_cfg":
            self.cfg = json.loads(json.dumps(DEFAULT_CFG))
            save_cfg(self.cfg)
            self.pr.cfg = self.cfg
            self.log("已恢复默认配置", "WARN")
            self.poll_once()
            return True, "已恢复默认配置", {}

        if act == "toggle_autostart_panel":
            v = not bool(self.cfg["ui"].get("autostart_panel"))
            self.cfg["ui"]["autostart_panel"] = v
            save_cfg(self.cfg)
            self._run_key("DownloadStackPanel", '"%s" "%s"' % (sys.executable, PANEL_DIR / "panel.py"), v)
            self.log("开机自启面板 %s" % ("开" if v else "关"))
            return True, "开机自启面板已%s" % ("开启" if v else "关闭"), {}

        if act == "toggle_autostart_aria2":
            v = not bool(self.cfg["ui"].get("autostart_aria2"))
            self.cfg["ui"]["autostart_aria2"] = v
            save_cfg(self.cfg)
            start_script = self.cfg["scripts"]["start"]
            cmd = ('cmd /c "%s"' % start_script) if IS_WIN else ('/bin/sh "%s"' % start_script)
            self._run_key("DownloadStackAria2", cmd, v)
            self.log("开机拉起 Aria2 %s" % ("开" if v else "关"))
            return True, "开机拉起 Aria2 已%s" % ("开启" if v else "关闭"), {}

        return False, "未知操作", {}


def _open_app_window(url: str):
    """优先用 Edge/Chrome 无边框 App 模式打开，回退到默认浏览器。"""
    if IS_WIN:
        cands = [
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
            Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
            Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
        ]
        for exe in cands:
            if exe.is_file():
                try:
                    subprocess.Popen([str(exe), "--app=" + url, "--window-size=1480,920"],
                                     **_popen_kwargs())
                    return
                except Exception:
                    pass
    webbrowser.open(url)


def run_3d_server(open_browser=True):
    """启动 Spatial 3D HUD 本地服务（同时同源直出 AriaNg）。"""
    import mimetypes
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import unquote

    ui_file = APP_DIR / "panel_ui.html"
    backend = ControlBackend()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            return

        def _send_json(self, obj, code=200):
            raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _proxy_qbit(self, method="GET"):
            c = backend.cfg.get("qbit") or {}
            host = c.get("host") or "127.0.0.1"
            port = int(c.get("port") or 8080)
            if not port_open(host, port):
                msg = (
                    "<html><body style='margin:0;height:100vh;display:flex;flex-direction:column;align-items:center;"
                    "justify-content:center;background:#040814;color:#93c5fd;font-family:sans-serif;gap:12px;'>"
                    "<div style='font-size:18px;font-weight:800;'>qBittorrent 尚未启动</div>"
                    "<div style='font-size:13px;color:#64748b;'>请点击上方「▶ 启动 qBittorrent」后刷新，即可在软件内直接使用 WebUI</div>"
                    "</body></html>"
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(msg)))
                self.end_headers()
                self.wfile.write(msg)
                return
            sub = self.path[len("/qbit"):] if self.path.startswith("/qbit") else "/"
            if not sub.startswith("/"):
                sub = "/" + sub
            target_url = "http://%s:%d%s" % (host, port, sub)
            hdrs = {
                "Referer": "http://%s:%d/" % (host, port),
                "Origin": "http://%s:%d" % (host, port),
            }
            if self.headers.get("Cookie"):
                hdrs["Cookie"] = self.headers.get("Cookie")
            if self.headers.get("Content-Type"):
                hdrs["Content-Type"] = self.headers.get("Content-Type")
            body_bytes = None
            if method == "POST":
                length = int(self.headers.get("Content-Length") or 0)
                body_bytes = self.rfile.read(length) if length > 0 else b""
            try:
                _ps = requests.Session()
                _ps.trust_env = False
                r = _ps.request(
                    method, target_url, headers=hdrs, data=body_bytes,
                    timeout=12, allow_redirects=False
                )
                # qB 重启会让浏览器里的旧 cookie 失效（403）；代理层自动登录后重试一次
                if r.status_code == 403:
                    try:
                        _s = requests.Session()
                        _s.trust_env = False
                        _qc = backend.cfg.get("qbit") or {}
                        _s.post(
                            "http://%s:%d/api/v2/auth/login" % (host, port),
                            data={"username": _qc.get("user") or "admin",
                                  "password": _qc.get("pass") or ""},
                            timeout=6,
                        )
                        _h = {k: v for k, v in hdrs.items() if k.lower() != "cookie"}
                        r = _s.request(
                            method, target_url, headers=_h, data=body_bytes,
                            timeout=12, allow_redirects=False
                        )
                    except Exception:
                        pass
                content = r.content
                ctype = r.headers.get("Content-Type") or "application/octet-stream"
                # 把 qB 根相对路径重写到 /qbit/ 下，确保站内 iframe 资源 100% 正常加载
                if "text/html" in ctype.lower():
                    try:
                        txt = content.decode("utf-8", errors="replace")
                        if "<base " not in txt.lower():
                            txt = txt.replace("<head>", "<head><base href='/qbit/'>", 1)
                        content = txt.encode("utf-8")
                    except Exception:
                        pass
                self.send_response(r.status_code)
                self.send_header("Content-Type", ctype)
                self.send_header("Cache-Control", "no-store")
                if r.headers.get("Set-Cookie"):
                    self.send_header("Set-Cookie", r.headers.get("Set-Cookie").replace("Path=/", "Path=/"))
                if r.headers.get("Location"):
                    loc = r.headers.get("Location")
                    if loc.startswith("/") and not loc.startswith("/qbit/"):
                        loc = "/qbit" + loc
                    self.send_header("Location", loc)
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                return
            except Exception as ex:
                try:
                    err = ("qBittorrent 内置代理连接失败：%s" % ex).encode("utf-8")
                    self.send_response(502)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(err)))
                    self.end_headers()
                    self.wfile.write(err)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    return

        def _proxy_tv(self, method="GET"):
            # KatelyaTV 同源反代：把 3030 的页面/资源搬到 /tv/ 下，绕开 iframe 第三方 cookie 拦截
            host, port = "127.0.0.1", 3030
            if not port_open(host, port):
                msg = (
                    "<html><body style='margin:0;height:100vh;display:flex;flex-direction:column;"
                    "align-items:center;justify-content:center;background:#040814;color:#93c5fd;"
                    "font-family:sans-serif;gap:12px;'>"
                    "<div style='font-size:18px;font-weight:800;'>影视站未启动</div>"
                    "<div style='font-size:13px;color:#64748b;'>请确认 Docker Desktop 已运行，容器 katelyatv 会自动就绪</div>"
                    "</body></html>"
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(msg)))
                self.end_headers()
                self.wfile.write(msg)
                return
            sub = self.path[len("/tv"):] if self.path.startswith("/tv") else "/"
            if not sub.startswith("/"):
                sub = "/" + sub
            target_url = "http://%s:%d%s" % (host, port, sub)
            hdrs = {"Host": "%s:%d" % (host, port)}
            for h in ("Cookie", "Content-Type", "Accept", "Accept-Language", "User-Agent"):
                v = self.headers.get(h)
                if v:
                    hdrs[h] = v
            body_bytes = None
            if method in ("POST", "PUT", "PATCH", "DELETE"):
                length = int(self.headers.get("Content-Length") or 0)
                body_bytes = self.rfile.read(length) if length > 0 else b""
            try:
                _ps = requests.Session()
                _ps.trust_env = False
                r = _ps.request(method, target_url, headers=hdrs, data=body_bytes,
                                timeout=25, allow_redirects=False)
                try:
                    if r.status_code >= 400:
                        backend.log("TV代理 %s %s -> %s" % (method, sub[:90], r.status_code), "WARN")
                except Exception:
                    pass
                content = r.content
                ctype = r.headers.get("Content-Type") or "application/octet-stream"
                low = ctype.lower()
                # Next.js 用绝对路径 /_next/ 与 /api/，必须改写到 /tv 前缀下才不会被面板根路径吞掉
                if ("text/html" in low) or ("javascript" in low) or ("text/css" in low):
                    try:
                        txt = content.decode("utf-8", errors="replace")
                        txt = txt.replace("/_next/", "/tv/_next/")
                        txt = txt.replace('"/api/', '"/tv/api/')
                        txt = txt.replace("'/api/", "'/tv/api/")
                        txt = txt.replace("( /api/", "( /tv/api/")
                        txt = txt.replace("(/api/", "(/tv/api/")
                        # 根路径下的静态文件也要搬到 /tv 下，否则会打到面板根吃 404
                        for _root in ("/manifest.json", "/sw.js", "/favicon.ico", "/icon-192.png",
                                      "/icon-512.png", "/apple-touch-icon.png", "/robots.txt",
                                      "/logo.png", "/logo.svg", "/banner.png"):
                            txt = txt.replace('"' + _root + '"', '"/tv' + _root + '"')
                            txt = txt.replace("'" + _root + "'", "'/tv" + _root + "'")
                        # Next.js 登录成功后 router.replace(redirect)，redirect 默认是 "/"，
                        # 在反代下必须补上 /tv 前缀；已带 /tv 的不能再拼，否则会变成 /tv/tv/
                        txt = txt.replace(
                            't.get("redirect")||"/";e.replace(r)',
                            't.get("redirect")||"/";e.replace(!r?"/tv/":(r.indexOf("/tv/")===0||r==="/tv"?r:(r==="/"?"/tv/":(r.charAt(0)==="/"?"/tv"+r:r))))'
                        )
                        txt = txt.replace(
                            "t.get('redirect')||'/';e.replace(r)",
                            "t.get('redirect')||'/';e.replace(!r?'/tv/':(r.indexOf('/tv/')===0||r==='/tv'?r:(r==='/'?'/tv/':(r.charAt(0)==='/'?'/tv'+r:r))))"
                        )
                        content = txt.encode("utf-8")
                    except Exception:
                        pass
                self.send_response(r.status_code)
                self.send_header("Content-Type", ctype)
                self.send_header("Cache-Control", "no-store")
                sc = r.headers.get("Set-Cookie")
                if sc:
                    self.send_header("Set-Cookie", sc)
                loc = r.headers.get("Location")
                if loc:
                    if loc.startswith("/") and not loc.startswith("/tv"):
                        loc = "/tv" + loc
                    self.send_header("Location", loc)
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                return
            except Exception as ex:
                try:
                    err = ("影视站反代失败：%s" % ex).encode("utf-8")
                    self.send_response(502)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(err)))
                    self.end_headers()
                    self.wfile.write(err)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    return

        def _proxy_tv_raw(self):
            # 兜底转发：KatelyaTV 的业务路由（/douban /play /search …）都是根绝对路径，
            # 面板未占用的路径一律交给它，否则 iframe 里点一下就 404
            if not port_open("127.0.0.1", 3030):
                return False
            try:
                _hdr = {"Host": "127.0.0.1:3030",
                        "Accept": self.headers.get("Accept") or "*/*"}
                _ck = self.headers.get("Cookie")
                if _ck:
                    _hdr["Cookie"] = _ck
                r = requests.get("http://127.0.0.1:3030" + str(self.path), timeout=12,
                                 allow_redirects=False, proxies={"http": None, "https": None},
                                 headers=_hdr)
                if r.status_code >= 400:
                    return False
                content = r.content
                ctype = r.headers.get("Content-Type") or "application/octet-stream"
                low = ctype.lower()
                if ("text/html" in low) or ("javascript" in low) or ("text/css" in low):
                    try:
                        txt = content.decode("utf-8", errors="replace")
                        txt = txt.replace("/_next/", "/tv/_next/")
                        txt = txt.replace('"/api/', '"/tv/api/')
                        txt = txt.replace("'/api/", "'/tv/api/")
                        txt = txt.replace("(/api/", "(/tv/api/")
                        content = txt.encode("utf-8")
                    except Exception:
                        pass
                self.send_response(r.status_code)
                self.send_header("Content-Type", ctype)
                self.send_header("Cache-Control", "no-store")
                sc = r.headers.get("Set-Cookie")
                if sc:
                    self.send_header("Set-Cookie", sc)
                loc = r.headers.get("Location")
                if loc:
                    if loc.startswith("/") and not loc.startswith("/tv"):
                        loc = "/tv" + loc
                    self.send_header("Location", loc)
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return True
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                return True
            except Exception:
                return False

        def do_GET(self):
            req_path = self.path.split("?", 1)[0]
            if req_path == "/qbit" or req_path.startswith("/qbit/"):
                if req_path == "/qbit":
                    self.send_response(302)
                    self.send_header("Location", "/qbit/")
                    self.end_headers()
                    return
                self._proxy_qbit("GET")
                return
            if req_path == "/tv" or req_path.startswith("/tv/"):
                if req_path == "/tv":
                    self.send_response(302)
                    self.send_header("Location", "/tv/")
                    self.end_headers()
                    return
                self._proxy_tv("GET")
                return
            if req_path in ("/favicon.ico", "/api/app_icon.png"):
                is_ico = (req_path == "/favicon.ico")
                fn = "DownloadStackControl.ico" if is_ico else "DownloadStackControl.png"
                cands = [
                    APP_DIR / "cache" / "icons" / fn,
                    APP_DIR / "assets" / fn,
                ]
                hit = next((p for p in cands if p.is_file()), None)
                if hit is None:
                    self.send_error(404, "Icon not found")
                    return
                data = hit.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/x-icon" if is_ico else "image/png")
                self.send_header("Cache-Control", "public, max-age=3600")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            if req_path in ("/", "/index.html"):
                html = ui_file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)
                return
            if req_path == "/api/state":
                self._send_json(backend.get_state())
                return
            if req_path == "/api/stream_audio":
                from urllib.parse import parse_qs, urlsplit
                qs = parse_qs(urlsplit(self.path).query)
                tok = (qs.get("id") or [""])[0]
                with backend.lock:
                    info = dict(backend.stream_tokens.get(tok) or {})
                if not info.get("url"):
                    self.send_error(404, "Stream expired")
                    return
                hdrs = dict(info.get("headers") or {})
                rng = self.headers.get("Range")
                if rng:
                    hdrs["Range"] = rng
                px_sys = backend._sys_proxy()
                want_px = bool(info.get("use_proxy")) and bool(px_sys)
                route_plan = [px_sys, ""] if want_px else (["", px_sys] if px_sys else [""])
                last_ex = None
                sent = False
                for route_px in route_plan:
                    sess = requests.Session()
                    if not route_px:
                        sess.trust_env = False
                    proxies = {"http": route_px, "https": route_px} if route_px else None
                    try:
                        with sess.get(info["url"], headers=hdrs, proxies=proxies, stream=True, timeout=16) as r:
                            if r.status_code in (403, 502, 503) and route_px != route_plan[-1]:
                                continue
                            self.send_response(r.status_code)
                            self.send_header("Content-Type", r.headers.get("Content-Type") or info.get("mime") or "audio/mp4")
                            self.send_header("Accept-Ranges", r.headers.get("Accept-Ranges") or "bytes")
                            self.send_header("Cache-Control", "no-store")
                            if r.headers.get("Content-Range"):
                                self.send_header("Content-Range", r.headers["Content-Range"])
                            if r.headers.get("Content-Length"):
                                self.send_header("Content-Length", r.headers["Content-Length"])
                            self.end_headers()
                            sent = True
                            for chunk in r.iter_content(chunk_size=65536):
                                if not chunk:
                                    continue
                                try:
                                    self.wfile.write(chunk)
                                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                                    break
                            break
                    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                        sent = True
                        break
                    except Exception as ex:
                        last_ex = ex
                if not sent and last_ex is not None:
                    try:
                        self.send_error(502, "Audio stream error: %s" % last_ex)
                    except Exception:
                        pass
                return
            if req_path == "/api/subtitle":
                from urllib.parse import parse_qs, urlsplit
                import re as _re
                qs = parse_qs(urlsplit(self.path).query)
                raw_p = (qs.get("path") or [""])[0]
                stream_param = (qs.get("stream") or [""])[0].strip()
                ff_dir = backend._find_ffmpeg()
                ffmpeg_exe = (str(Path(ff_dir) / ("ffmpeg.exe" if IS_WIN else "ffmpeg")) if ff_dir else (shutil.which("ffmpeg") or ""))

                # 模式 A：从视频文件内嵌字幕轨提取 WebVTT
                if stream_param != "":
                    v_target = backend._is_allowed_media(raw_p)
                    if v_target is None or not ffmpeg_exe or not stream_param.isdigit():
                        self.send_error(403, "Embedded subtitle not accessible")
                        return
                    try:
                        r = subprocess.run(
                            [ffmpeg_exe, "-v", "error", "-i", str(v_target),
                             "-map", "0:" + stream_param, "-f", "webvtt", "pipe:1"],
                            capture_output=True, timeout=20,
                            creationflags=(0x08000000 if IS_WIN else 0),
                        )
                        data = r.stdout or b"WEBVTT\n\n"
                    except Exception:
                        data = b"WEBVTT\n\n"
                    self.send_response(200)
                    self.send_header("Content-Type", "text/vtt; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return

                # 模式 B：外挂 .srt / .vtt / .ass / .ssa 字幕
                target = backend._is_allowed_sub(raw_p)
                if target is None:
                    self.send_error(403, "Subtitle not accessible")
                    return
                if target.suffix.lower() in (".ass", ".ssa") and ffmpeg_exe:
                    try:
                        r = subprocess.run(
                            [ffmpeg_exe, "-v", "error", "-i", str(target), "-f", "webvtt", "pipe:1"],
                            capture_output=True, timeout=12,
                            creationflags=(0x08000000 if IS_WIN else 0),
                        )
                        data = r.stdout if (r.returncode == 0 and r.stdout) else b"WEBVTT\n\n"
                    except Exception:
                        data = b"WEBVTT\n\n"
                else:
                    raw = target.read_bytes()
                    txt = None
                    for enc in ("utf-8-sig", "utf-16", "gb18030", "big5"):
                        try:
                            txt = raw.decode(enc)
                            if enc == "utf-16" and not raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
                                txt = None
                                continue
                            break
                        except Exception:
                            txt = None
                    if txt is None:
                        txt = raw.decode("utf-8", "replace")
                    txt = txt.replace("\r\n", "\n").replace("\r", "\n")
                    if target.suffix.lower() == ".srt":
                        txt = _re.sub(r"(\d{1,2}:\d{2}:\d{2}),(\d{1,3})", r"\1.\2", txt)
                        txt = "WEBVTT\n\n" + txt.lstrip("\ufeff")
                    data = txt.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/vtt; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return

            if req_path == "/api/stream_video":
                from urllib.parse import parse_qs, urlsplit
                qs = parse_qs(urlsplit(self.path).query)
                raw_p = (qs.get("path") or [""])[0]
                target = backend._is_allowed_media(raw_p)
                if target is None:
                    self.send_error(403, "Media not accessible")
                    return
                ff_dir = backend._find_ffmpeg()
                ffmpeg_exe = (str(Path(ff_dir) / ("ffmpeg.exe" if IS_WIN else "ffmpeg")) if ff_dir else (shutil.which("ffmpeg") or ""))
                if not ffmpeg_exe:
                    self.send_error(503, "ffmpeg not available")
                    return
                try:
                    start_sec = max(0.0, float((qs.get("start") or ["0"])[0] or 0))
                except Exception:
                    start_sec = 0.0
                pinfo = backend.probe_video(str(target))
                vcodec = str(pinfo.get("vcodec") or "").lower()
                acodec = str(pinfo.get("acodec") or "").lower()
                # 原画质零压缩：现代浏览器兼容编码与像素格式一律 -c:v copy 比特级直出；10bit H.264/yuv444p 自动高码率兼容转 yuv420p
                can_copy_v = bool(pinfo.get("can_copy_video", True)) and ((not vcodec) or (vcodec in backend._COPY_VCODECS))
                can_copy_a = acodec in backend._COPY_ACODECS
                cmd = [ffmpeg_exe, "-v", "error", "-nostdin"]
                if start_sec > 0.2:
                    cmd += ["-ss", "%.3f" % start_sec]
                cmd += ["-i", str(target), "-map", "0:v:0", "-map", "0:a:0?"]
                if can_copy_v:
                    cmd += ["-c:v", "copy"]
                    if vcodec in ("hevc", "h265"):
                        cmd += ["-tag:v", "hvc1"]
                else:
                    # 仅对浏览器物理无法硬件解码的老旧编码 (如 RMVB/WMV) 高码率兜底
                    cmd += ["-c:v", "libx264", "-crf", "14", "-preset", "veryfast", "-pix_fmt", "yuv420p"]
                if can_copy_a:
                    cmd += ["-c:a", "copy"]
                else:
                    cmd += ["-c:a", "aac", "-b:a", "320k", "-ac", "2"]
                cmd += ["-movflags", "frag_keyframe+empty_moov+default_base_moof", "-f", "mp4", "pipe:1"]

                proc = None
                try:
                    proc = subprocess.Popen(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                        bufsize=262144, creationflags=(0x08000000 if IS_WIN else 0),
                    )
                    self.send_response(200)
                    self.send_header("Content-Type", "video/mp4")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Cinema-Mode", "lossless-copy" if can_copy_v else "compat-hq")
                    self.end_headers()
                    while True:
                        chunk = proc.stdout.read(131072)
                        if not chunk:
                            break
                        try:
                            self.wfile.write(chunk)
                        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                            break
                except Exception:
                    pass
                finally:
                    if proc is not None:
                        try:
                            proc.terminate()
                            proc.wait(timeout=2)
                        except Exception:
                            try:
                                proc.kill()
                            except Exception:
                                pass
                return

            if req_path == "/api/prompt_preview":
                import threading
                from collections import OrderedDict
                from urllib.parse import parse_qs, urlsplit
                qs = parse_qs(urlsplit(self.path).query)
                raw_u = (qs.get("url") or [""])[0].strip()
                if PE is None or not PE.is_allowed_preview_url(raw_u):
                    self.send_error(403, "Preview URL not allowed")
                    return
                if not hasattr(backend, "_prompt_preview_cache"):
                    backend._prompt_preview_cache = OrderedDict()
                    backend._prompt_preview_lock = threading.Lock()
                hit = None
                with backend._prompt_preview_lock:
                    if raw_u in backend._prompt_preview_cache:
                        backend._prompt_preview_cache.move_to_end(raw_u)
                        hit = backend._prompt_preview_cache[raw_u]
                if hit is None:
                    ok_img, img_bytes, _ = PE._http_get_bytes(raw_u, proxy=backend._sys_proxy(), timeout=14.0)
                    if not ok_img or not img_bytes or len(img_bytes) > 12 * 1024 * 1024:
                        self.send_error(502, "Preview image unavailable")
                        return
                    if img_bytes[:4] == b"\x89PNG":
                        ctype = "image/png"
                    elif img_bytes[:4] == b"RIFF" and img_bytes[8:12] == b"WEBP":
                        ctype = "image/webp"
                    elif img_bytes[:4] == b"GIF8":
                        ctype = "image/gif"
                    else:
                        ctype = "image/jpeg"
                    hit = (ctype, img_bytes)
                    with backend._prompt_preview_lock:
                        backend._prompt_preview_cache[raw_u] = hit
                        while len(backend._prompt_preview_cache) > 160:
                            backend._prompt_preview_cache.popitem(last=False)
                ctype, img_bytes = hit
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Cache-Control", "public, max-age=86400")
                self.send_header("Content-Length", str(len(img_bytes)))
                self.end_headers()
                try:
                    self.wfile.write(img_bytes)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass
                return

            if req_path == "/api/media":
                from urllib.parse import parse_qs, urlsplit
                qs = parse_qs(urlsplit(self.path).query)
                raw_p = (qs.get("path") or [""])[0]
                target = backend._is_allowed_media(raw_p)
                if target is None:
                    self.send_error(403, "Media not accessible")
                    return
                size = target.stat().st_size
                ctype = {".mkv": "video/webm", ".m4v": "video/mp4", ".ts": "video/mp2t"}.get(
                    target.suffix.lower()) or mimetypes.guess_type(str(target))[0] or "application/octet-stream"
                rng = self.headers.get("Range")
                start, end = 0, size - 1
                code = 200
                if rng and rng.startswith("bytes="):
                    try:
                        part = rng[6:].split(",")[0].strip()
                        a, b = part.split("-", 1)
                        start = int(a) if a else 0
                        end = int(b) if b else (size - 1)
                        start = max(0, min(start, size - 1))
                        end = max(start, min(end, size - 1))
                        code = 206
                    except Exception:
                        start, end, code = 0, size - 1, 200
                length = end - start + 1
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Cache-Control", "no-store")
                if code == 206:
                    self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
                self.send_header("Content-Length", str(length))
                self.end_headers()
                with open(target, "rb") as f:
                    f.seek(start)
                    rem = length
                    while rem > 0:
                        chunk = f.read(min(131072, rem))
                        if not chunk:
                            break
                        try:
                            self.wfile.write(chunk)
                        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                            break
                        rem -= len(chunk)
                return
            if req_path == "/ariang" or req_path.startswith("/ariang/"):
                base_dir = backend._ariang_dir()
                if base_dir is None:
                    self.send_error(404, "AriaNg directory not found")
                    return
                rel = unquote(req_path[len("/ariang"):].lstrip("/")) or "index.html"
                target = (base_dir / rel).resolve()
                try:
                    target.relative_to(base_dir.resolve())
                except ValueError:
                    self.send_error(403)
                    return
                if target.is_dir():
                    target = target / "index.html"
                if not target.is_file():
                    self.send_error(404)
                    return
                data = target.read_bytes()
                ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
                if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
                    ctype += "; charset=utf-8"
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            try:
                backend.log("面板 404: %s" % str(self.path)[:120], "WARN")
            except Exception:
                pass
            # 兜底：面板没占用的路径交给 KatelyaTV（它有 /douban /play 这类根路由）
            _p = str(self.path).split("?", 1)[0]
            if not _p.startswith(("/api/", "/tv/", "/qbit/", "/ariang")):
                if self._proxy_tv_raw():
                    return
            self.send_error(404)

        def do_POST(self):
            req_path = self.path.split("?", 1)[0]
            if req_path == "/qbit" or req_path.startswith("/qbit/"):
                self._proxy_qbit("POST")
                return
            if req_path == "/tv" or req_path.startswith("/tv/"):
                self._proxy_tv("POST")
                return
            if req_path == "/api/action":
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length > 0 else b"{}"
                try:
                    body = json.loads(raw.decode("utf-8") or "{}")
                except Exception:
                    body = {}
                res = backend.handle_action(body)
                if len(res) == 3:
                    ok, msg, extra = res
                else:
                    ok, msg, extra = res[0], res[1], {}
                payload = {"ok": ok, "msg": msg}
                if isinstance(extra, dict):
                    payload.update(extra)
                self._send_json(payload)
                return
            if req_path == "/api/upload_ref":
                from urllib.parse import parse_qs, urlsplit
                qs = parse_qs(urlsplit(self.path).query)
                orig_name = (qs.get("name") or ["mic_sample.webm"])[0]
                length = int(self.headers.get("Content-Length") or 0)
                if length <= 0 or length > 26 * 1024 * 1024:
                    self._send_json({"ok": False, "msg": "音频文件为空或超过 25MB 限制"}, code=400)
                    return
                raw = self.rfile.read(length)
                ext = Path(orig_name).suffix.lower()
                if ext not in (".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm", ".aac", ".opus"):
                    ext = ".webm"
                raw_path = CACHE / ("ref_raw" + ext)
                raw_path.write_bytes(raw)
                dst_wav = CACHE / "ref_voice.wav"
                if MS is not None:
                    MS.normalize_ref_audio(raw_path, dst_wav, backend._find_ffmpeg())
                else:
                    shutil.copy2(raw_path, dst_wav)
                with backend.lock:
                    backend.voice_job["ref_wav"] = str(dst_wav.resolve())
                    backend.voice_job["ref_name"] = Path(orig_name).name
                backend._voice_append_log("[OK] 已载入并标准化参考音色：%s → 24kHz 单声道 WAV" % Path(orig_name).name)
                self._send_json({
                    "ok": True,
                    "msg": "参考音频已载入并标准化 ✔",
                    "ref_name": Path(orig_name).name,
                    "ref_wav": str(dst_wav.resolve()),
                })
                return
            if req_path == "/api/upload_aigc_image":
                from urllib.parse import parse_qs, urlsplit
                qs = parse_qs(urlsplit(self.path).query)
                orig_name = (qs.get("name") or ["first_frame.png"])[0]
                length = int(self.headers.get("Content-Length") or 0)
                if length <= 0 or length > 26 * 1024 * 1024:
                    self._send_json({"ok": False, "msg": "图片为空或超过 25MB 限制"}, code=400)
                    return
                raw = self.rfile.read(length)
                ext = Path(orig_name).suffix.lower()
                if ext not in (".png", ".jpg", ".jpeg", ".webp"):
                    ext = ".png"
                dst = CACHE / ("aigc_first_frame" + ext)
                dst.write_bytes(raw)
                with backend.lock:
                    backend.aigc_job["first_frame"] = str(dst.resolve())
                    backend.aigc_job["first_frame_name"] = Path(orig_name).name
                backend._aigc_append_log("[OK] 已载入图生视频首帧：%s" % Path(orig_name).name)
                self._send_json({
                    "ok": True,
                    "msg": "已载入首帧图片 ✔",
                    "first_frame": str(dst.resolve()),
                    "first_frame_name": Path(orig_name).name,
                })
                return
            self.send_error(404)

    base_port = int(os.environ.get("DOWNLOADSTACK_WEB_PORT") or 18550)
    srv = None
    port = base_port
    for p in range(base_port, base_port + 20):
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", p), Handler)
            port = p
            break
        except OSError:
            continue
    if srv is None:
        raise RuntimeError("无法绑定本地面板端口 %d..%d" % (base_port, base_port + 19))

    url = "http://127.0.0.1:%d/" % port
    print("[DownloadStack 3D] 控制台运行中：%s" % url, flush=True)
    if open_browser:
        _open_app_window(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    _no_display = (not IS_WIN) and (not IS_MAC) and not (
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    run_3d_server(open_browser=(not _no_display))
