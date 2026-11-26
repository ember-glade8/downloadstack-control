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
    import magnet_tools as MT
except Exception:
    MT = None

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
                                 capture_output=True, text=True, timeout=5,
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
        r = requests.post(url, json=body, timeout=timeout,
                          proxies={"http": None, "https": None})
        r.raise_for_status()
        j = r.json()
        if "error" in j:
            raise RuntimeError(str(j["error"])[:100])
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
                    tasks.append({
                        "gid": str(t.get("gid", "")),
                        "name": self._a_task_name(t),
                        "status": str(t.get("status", "")),
                        "total": tot,
                        "done": done,
                        "pct": pct,
                        "speed": int(t.get("downloadSpeed", 0) or 0),
                        "conn": int(t.get("connections", 0) or 0),
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
        s.proxies = {"http": None, "https": None}
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
                    "size": int(x.get("size", 0) or 0),
                    "pct": round(float(x.get("progress", 0) or 0) * 100, 1),
                    "speed": int(x.get("dlspeed", 0) or 0),
                    "up": int(x.get("upspeed", 0) or 0),
                    "ratio": round(float(x.get("ratio", 0) or 0), 2),
                })
            q_tasks.sort(key=lambda it: (it["speed"], it["up"], it["pct"]), reverse=True)
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
            "cookies": str((self.cfg.get("yt") or {}).get("cookies") or "none"),
            "cookies_file": str((self.cfg.get("yt") or {}).get("cookies_file") or ""),
            "pct": 0.0, "speed": "", "eta": "", "status": "就绪",
            "logs": [], "file": "",
        }
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
        except Exception as ex:
            self.log("轮询异常 %s" % type(ex).__name__, "ERROR")

    def _poll_loop(self):
        while True:
            time.sleep(1.5)
            self.poll_once()

    def yt_output(self):
        ini = (self.cfg["yt"].get("ini") or "").strip()
        if ini:
            got = ini_get(ini, "OUTPUT")
            if got:
                return got
        base = self.cfg.get("paths", {}).get("downloads") or str(DL_HOME)
        return str(Path(base) / "yt-dlp")

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

    def _open_local(self, path):
        if not path or not Path(path).exists():
            self.log("路径不存在 %s" % path, "WARN")
            return False, "路径不存在"
        open_path(path)
        self.log("打开 %s" % path)
        return True, "已打开本地路径"

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
        m = re.search(r"https?://[^\s\"'<>]+", s)
        return m.group(0).rstrip(".,;!?）)】》」") if m else s

    def _yt_append_log(self, line: str):
        ts = datetime.now().strftime("%H:%M:%S")
        with self.lock:
            self.yt_job["logs"].append("%s %s" % (ts, line))
            if len(self.yt_job["logs"]) > 200:
                self.yt_job["logs"] = self.yt_job["logs"][-200:]

    def _run_yt_worker(self, url: str, quality: str, cookies: str, cookies_file: str, upscale: bool):
        import re
        ytdlp = self._find_ytdlp()
        if not ytdlp:
            with self.lock:
                self.yt_job["running"] = False
                self.yt_job["status"] = "未检测到 yt-dlp"
            self._yt_append_log("[ERROR] 未找到 yt-dlp，请先运行一键配置或安装 yt-dlp")
            return
        out_dir = Path(self.yt_output())
        out_dir.mkdir(parents=True, exist_ok=True)
        cmd = [ytdlp, "--newline", "--progress", "--no-color", "-P", str(out_dir)]
        ff_dir = self._find_ffmpeg()
        if ff_dir:
            cmd += ["--ffmpeg-location", ff_dir]
        if quality == "1080":
            cmd += ["-f", "bv*[height<=1080]+ba/b[height<=1080]/best", "--merge-output-format", "mp4"]
        elif quality == "720":
            cmd += ["-f", "bv*[height<=720]+ba/b[height<=720]/best", "--merge-output-format", "mp4"]
        elif quality == "audio":
            cmd += ["-x", "--audio-format", "mp3", "--audio-quality", "0"]
        else:
            cmd += ["-f", "bv*+ba/best", "--merge-output-format", "mp4"]

        if cookies in ("firefox", "chrome", "edge"):
            cmd += ["--cookies-from-browser", cookies]
        elif cookies == "file" and cookies_file and Path(cookies_file).is_file():
            cmd += ["--cookies", cookies_file]

        cmd.append(url)
        env = os.environ.copy()
        px = self._sys_proxy()
        if px:
            env["HTTP_PROXY"] = env["HTTPS_PROXY"] = env["http_proxy"] = env["https_proxy"] = px
            env.pop("ALL_PROXY", None)
            env.pop("all_proxy", None)
            env["NO_PROXY"] = env["no_proxy"] = "localhost,127.0.0.1,::1,.local"

        pct_re = re.compile(r"(\d+(?:\.\d+)?)%")
        spd_re = re.compile(r"at\s+([^\s]+/s)")
        eta_re = re.compile(r"ETA\s+([0-9:]+)")
        dest_re = re.compile(r"(?:Destination:|Merging formats into\s+\"?)(.+?)\"?$")

        last_file = ""
        try:
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
            self._yt_append_log("[INFO] 启动 yt-dlp PID=%s（画质=%s | 代理=%s）" % (proc.pid, quality, px or "直连"))
            self.log("YT 工坊开始下载：%s" % url[:80], "OK")

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
                if m_dst:
                    cand = m_dst.group(1).strip().strip('"')
                    if cand:
                        last_file = cand
                        with self.lock:
                            self.yt_job["file"] = cand
                self._yt_append_log(line)

            rc = proc.wait()
            if rc == 0:
                with self.lock:
                    self.yt_job["pct"] = 100.0
                    self.yt_job["status"] = "下载完成 ✔"
                self._yt_append_log("[OK] 下载完成 → %s" % (last_file or out_dir))
                self.log("YT 工坊下载完成 → %s" % (last_file or out_dir), "OK")
                if upscale and quality != "audio":
                    v2x = self._find_video2x()
                    if v2x and last_file and Path(last_file).is_file():
                        with self.lock:
                            self.yt_job["status"] = "2x AI 超分中…"
                        self._yt_append_log("[INFO] 检测到 Video2X，开始 2x 超分：%s" % Path(last_file).name)
                        out_up = str(Path(last_file).with_stem(Path(last_file).stem + "_2x"))
                        up_proc = subprocess.Popen([v2x, "-i", last_file, "-o", out_up, "-s", "2"],
                                                   cwd=str(out_dir), **_popen_kwargs())
                        with self.lock:
                            self.yt_job["pid"] = up_proc.pid
                        up_rc = up_proc.wait()
                        with self.lock:
                            self.yt_job["status"] = "2x 超分完成 ✔" if up_rc == 0 else "下载完成（超分异常）"
                        self._yt_append_log("[OK] 2x 超分完成 → %s" % out_up if up_rc == 0 else "[WARN] 超分退出码 %s" % up_rc)
                    else:
                        self._yt_append_log("[WARN] 未检测到 Video2X 可执行文件，已跳过 2x 超分（视频已正常保存）")
            else:
                with self.lock:
                    if self.yt_job["status"] != "已取消":
                        self.yt_job["status"] = "下载失败 (码 %s)" % rc
                self._yt_append_log("[ERROR] yt-dlp 退出码 %s（若报 403 请在上方勾选浏览器 Cookies）" % rc)
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
        yt_state = dict(self.pr.y)
        yt_state["upscale"] = bool(self.cfg.get("ui", {}).get("upscale"))
        yt_state["on"] = bool(yt_state.get("on") or yt_job.get("running"))
        yt_job["has_ytdlp"] = bool(self._find_ytdlp())
        yt_job["has_ffmpeg"] = bool(self._find_ffmpeg())
        yt_job["has_video2x"] = bool(self._find_video2x())
        yt_job["out_dir"] = self.yt_output()
        yt_job["proxy"] = self._sys_proxy() or "直连"
        return {
            "aria2": dict(self.pr.a),
            "qbit": dict(self.pr.q),
            "yt": yt_state,
            "yt_studio": yt_job,
            "magnet": self._magnet_diag(),
            "tasks": {
                "aria2": list(self.pr.a_tasks),
                "qbit": list(self.pr.q_tasks),
            },
            "urls": {
                "ariang": self._ariang_url(),
                "ariang_embedded": self._ariang_dir() is not None,
                "qbit": self._qbit_url(),
            },
            "cfg": self.cfg,
            "wave": wave,
            "logs": logs,
            "uptime": up,
        }

    def handle_action(self, body):
        act = (body.get("action") or "").strip()
        if act == "start_a":
            if port_open(self.cfg["aria2"]["host"], self.cfg["aria2"]["port"]):
                self.log("Aria2 已在线，可直接打开 AriaNg", "OK")
                return True, "Aria2 已在线", {"open_url": self._ariang_url()}
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
            self.log("跳转 AriaNg：%s（同源免端口冲突，已自动注入 RPC Token）" % url, "OK")
            return True, "正在打开 AriaNg", {"open_url": url}

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
                self.log("qBittorrent 已在线", "OK")
                return True, "qBittorrent 已在线", {"open_url": self._qbit_url()}
            script = str((self.cfg.get("scripts") or {}).get("qbit") or "")
            if script and Path(script).exists():
                ok, msg = self.run_cmd(script_cmd(script), "启动 qBittorrent", "qbit")
            else:
                exe_dir = Path(str((self.cfg.get("qbit") or {}).get("exe_dir") or ""))
                hit = next((exe_dir / n for n in ("qbittorrent.exe", "qBittorrent.exe") if (exe_dir / n).is_file()), None)
                if hit:
                    ok, msg = self.run_cmd([str(hit)], "启动 qBittorrent", "qbit", cwd=str(exe_dir))
                else:
                    return False, "未找到 qBittorrent 程序或脚本", {}
            for _ in range(10):
                time.sleep(0.3)
                if port_open(self.cfg["qbit"]["host"], self.cfg["qbit"]["port"]):
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
            url = self._qbit_url()
            self.log("跳转 qBittorrent WebUI：%s" % url, "OK")
            return True, "正在打开 qB WebUI", {"open_url": url}

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

        if act == "add_download":
            raw_url = str(body.get("url") or "").strip()
            engine = str(body.get("engine") or "auto").strip().lower()
            if not raw_url:
                return False, "请先粘贴下载链接或磁力链接", {}
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
            video_hosts = ("youtube.com", "youtu.be", "bilibili.com", "b23.tv", "douyin.com",
                           "xiaohongshu.com", "xhslink.com", "tiktok.com", "vimeo.com", "x.com", "twitter.com", "twitch.tv")
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

                # 优先尝试秒级预取 .torrent 元数据（带 SHA1 校验），跳过 [METADATA] 卡顿
                tor_bytes, tor_src = b"", ""
                if MT is not None and ih:
                    try:
                        tor_bytes, tor_src = MT.resolve_magnet_torrent(ih, proxy=self._sys_proxy(), timeout=4.0)
                    except Exception:
                        tor_bytes, tor_src = b"", ""

                if target_eng == "qbit":
                    try:
                        s, base = self.pr.q_login()
                        hdr = {"Referer": base + "/", "Origin": base}
                        if tor_bytes:
                            r = s.post(base + "/api/v2/torrents/add", timeout=5.0, headers=hdr,
                                       files={"torrents": (ih + ".torrent", tor_bytes, "application/x-bittorrent")})
                        else:
                            r = s.post(base + "/api/v2/torrents/add", timeout=4.0, headers=hdr,
                                       data={"urls": enhanced})
                        if r.status_code == 200:
                            note = "（已秒级预取种子 %s）" % tor_src if tor_bytes else "（已自动补全公共 Tracker）"
                            self.log("qBittorrent 磁力投递成功 %s" % note, "OK")
                            self.poll_once()
                            return True, "磁力已投递至 qBittorrent" + note, {"engine": "qbit"}
                        raise RuntimeError("http_%s" % r.status_code)
                    except Exception as ex:
                        self.log("qB 磁力投递失败，尝试回退 Aria2：%s" % ex, "WARN")
                        target_eng = "aria2"

                if target_eng == "aria2":
                    try:
                        import base64
                        if not port_open(self.cfg["aria2"]["host"], self.cfg["aria2"]["port"]):
                            self.handle_action({"action": "start_a"})
                        if tor_bytes:
                            gid = self.pr.a_call("aria2.addTorrent", [base64.b64encode(tor_bytes).decode("ascii")])
                            note = "（已秒级预取种子 %s）" % tor_src
                        else:
                            gid = self.pr.a_call("aria2.addUri", [[enhanced]])
                            note = "（已自动补全公共 Tracker）"
                        self.log("Aria2 磁力投递成功 GID=%s %s" % (gid, note), "OK")
                        self.poll_once()
                        return True, "磁力已投递至 Aria2" + note, {"engine": "aria2", "gid": gid}
                    except Exception as ex:
                        self.log("Aria2 磁力投递失败 %s" % ex, "ERROR")
                        return False, "磁力投递失败，请先启动 Aria2 或 qBittorrent", {}

            if engine == "aria2":
                try:
                    if not port_open(self.cfg["aria2"]["host"], self.cfg["aria2"]["port"]):
                        self.handle_action({"action": "start_a"})
                    gid = self.pr.a_call("aria2.addUri", [[raw_url]])
                    self.log("Aria2 已投递直链任务 GID=%s" % gid, "OK")
                    self.poll_once()
                    return True, "已投递至 Aria2 高速下载", {"engine": "aria2", "gid": gid}
                except Exception as ex:
                    self.log("Aria2 投递失败 %s" % ex, "ERROR")
                    return False, "Aria2 投递失败，请先启动 Aria2", {}

            if engine == "qbit":
                try:
                    s, base = self.pr.q_login()
                    r = s.post(base + "/api/v2/torrents/add", timeout=4.0,
                               headers={"Referer": base + "/", "Origin": base},
                               data={"urls": raw_url})
                    if r.status_code == 200:
                        self.log("qBittorrent 已添加种子任务", "OK")
                        self.poll_once()
                        return True, "已投递至 qBittorrent 下载", {"engine": "qbit"}
                    raise RuntimeError("http_%s" % r.status_code)
                except Exception as ex:
                    self.log("qBittorrent 投递失败 %s" % ex, "ERROR")
                    return False, "qBittorrent 投递失败，请确认 qB 已启动", {}

            if engine == "yt":
                ytdlp = self._find_ytdlp()
                out_dir = Path(self.yt_output())
                out_dir.mkdir(parents=True, exist_ok=True)
                if ytdlp:
                    env = os.environ.copy()
                    px = self._sys_proxy()
                    if px:
                        env["HTTP_PROXY"] = env["HTTPS_PROXY"] = env["http_proxy"] = env["https_proxy"] = px
                    cmd = [ytdlp, "-P", str(out_dir), raw_url]
                    proc = subprocess.Popen(cmd, cwd=str(out_dir), env=env, **_popen_kwargs())
                    self.pids["yt"] = proc.pid
                    save_pids(self.pids)
                    self.log("YT-DLP 后台开始下载 PID %s → %s" % (proc.pid, out_dir), "OK")
                    self.poll_once()
                    return True, "已调用 yt-dlp 开始下载视频", {"engine": "yt"}
                return self.handle_action({"action": "start_y"})

        if act == "magnet_parse":
            if MT is None:
                return False, "magnet_tools 模块不可用", {}
            info = MT.parse_magnet(str(body.get("raw") or ""))
            return bool(info.get("valid")), info.get("error") or "磁力解析成功", {"info": info}

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
                cookies = str(body.get("cookies") or "none")
                cookies_file = str(body.get("cookies_file") or "").strip()
                upscale = bool(body.get("upscale", self.cfg["ui"].get("upscale")))
                self.cfg["yt"]["cookies"] = cookies
                self.cfg["yt"]["cookies_file"] = cookies_file
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
            try:
                for f in CACHE.rglob("*"):
                    if f.is_file():
                        f.unlink()
                        n += 1
            except Exception:
                pass
            self.log("清理缓存 %d 个" % n, "OK")
            return True, "已清理 %d 个缓存文件" % n, {}

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
                "downloads": str(dl_base),
            }
            target = mapping.get(key, "")
            if key in ("aria2_dl", "qbit_dl", "yt_out", "downloads") and target:
                try:
                    Path(target).mkdir(parents=True, exist_ok=True)
                except Exception:
                    pass
            ok, msg = self._open_local(target)
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

        def do_GET(self):
            req_path = self.path.split("?", 1)[0]
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
            self.send_error(404)

        def do_POST(self):
            req_path = self.path.split("?", 1)[0]
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
