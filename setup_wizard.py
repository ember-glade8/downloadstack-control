# -*- coding: utf-8 -*-
"""DownloadStack 安装引导（图形向导，Windows / Linux / macOS 通用）

为什么用它：不往控制台刷一屏字，而是一个窗口：
    1. 先扫描你这台机器缺什么（逐条列出来，✔ / ✘）
    2. 你点「一键安装缺失项」才动手（不点不动）
    3. 装完再点「启动控制台」

用法：
    python3 setup_wizard.py          # 打开窗口
    python3 setup_wizard.py --scan   # 只扫描，打印结果（调试用）
"""
import os
import shutil
import subprocess
import sys
import threading
import queue
from pathlib import Path

APP = Path(__file__).resolve().parent
IS_WIN = os.name == "nt"
try:
    if IS_WIN:
        sys.stdout.reconfigure(encoding="mbcs", errors="replace")
        sys.stderr.reconfigure(encoding="mbcs", errors="replace")
except Exception:
    pass
IS_MAC = sys.platform == "darwin"
HOME = Path(os.environ.get("USERPROFILE") or Path.home())


# ---------------------------------------------------------------- 扫描逻辑
def _which(name):
    return shutil.which(name)


def _py_ok():
    return sys.version_info >= (3, 10)


def _has_module(mod):
    try:
        __import__(mod)
        return True
    except Exception:
        return False


def _detect_root():
    env = (os.environ.get("DOWNLOADSTACK_ROOT") or "").strip()
    if env and Path(env).is_dir():
        return Path(env)
    for cand in (APP, APP.parent, APP.parent.parent):
        if (cand / "aria2").is_dir() or (cand / "tools").is_dir():
            return cand
    for d in ("C", "D", "E", "F"):
        cand = Path(d + ":/Tools/DownloadStack")
        if (cand / "aria2").is_dir():
            return cand
    return APP


ROOT = _detect_root()
DL = Path(os.environ.get("DOWNLOADSTACK_DOWNLOADS") or (HOME / "Downloads"))


def _aria2():
    for p in (ROOT / "aria2" / "aria2c.exe", ROOT / "aria2" / "aria2c"):
        if p.is_file():
            return str(p)
    return _which("aria2c") or ""


def _ariang():
    for p in (ROOT / "ariaNg" / "index.html", ROOT / "ariang" / "index.html"):
        if p.is_file():
            return str(p)
    return ""


def _ytdlp():
    cands = [ROOT / "tools" / "yt-dlp.exe", ROOT / "tools" / "yt-dlp",
             DL / "ytdlp" / "yt-dlp.exe", DL / "ytdlp" / "yt-dlp"]
    for p in cands:
        if p.is_file():
            return str(p)
    return _which("yt-dlp") or ""


def _ffmpeg():
    cands = [ROOT / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe",
             ROOT / "tools" / "ffmpeg" / "bin" / "ffmpeg"]
    for p in cands:
        if p.is_file():
            return str(p)
    return _which("ffmpeg") or ""


def _qbit():
    cands = [ROOT / "qBittorrent" / "qbittorrent.exe", ROOT / "qBittorrent" / "qBittorrent.exe"]
    for p in cands:
        if p.is_file():
            return str(p)
    return _which("qbittorrent") or _which("qBittorrent") or ""


def _video2x():
    cands = [ROOT / "tools" / "video2x" / "video2x.exe",
             Path("D:/Video2X/video2x.exe")]
    for p in cands:
        if p.is_file():
            return str(p)
    return _which("video2x") or ""


def scan():
    """返回 [(名称, 是否就绪, 说明, 是否可自动安装)]"""
    items = []
    items.append(("操作系统", True, "%s %s" % (os.name, sys.platform), False))
    items.append(("Python 3.10+", _py_ok(), sys.version.split()[0], False))
    items.append(("pip", bool(_which("pip3") or _which("pip") or _has_module("pip")), "", True))
    items.append(("flet 依赖", _has_module("flet"), "面板界面库", True))
    items.append(("requests 依赖", _has_module("requests"), "HTTP 库", True))
    items.append(("aria2c", bool(_aria2()), _aria2() or "下载引擎", True))
    items.append(("AriaNg", bool(_ariang()), _ariang() or "Web 管理界面", True))
    items.append(("yt-dlp", bool(_ytdlp()), _ytdlp() or "视频下载器", True))
    items.append(("ffmpeg", bool(_ffmpeg()), _ffmpeg() or "合并音视频用", True))
    items.append(("qBittorrent", bool(_qbit()), _qbit() or "BT/PT（可选）", True))
    v2x = _video2x()
    items.append(("Video2X 超分", bool(v2x), v2x or "可选：想把视频 2x 超分才需要", False))
    items.append(("面板文件", (APP / "panel.py").is_file(), str(APP / "panel.py"), False))
    return items


def missing():
    return [x for x in scan() if not x[1]]


# ---------------------------------------------------------------- 安装动作
def installer_cmd():
    """复用已有安装脚本，保证逻辑单一来源。"""
    if IS_WIN:
        bat = APP / "install.bat"
        if bat.is_file():
            env = dict(os.environ)
            env["DS_AUTO"] = "1"
            env["DS_NOMSGBOX"] = "1"
            env["DS_NO_QB"] = "1"
            env["DS_BASE"] = str(ROOT)
            try:
                env["DS_DL"] = str(Path(ROOT.drive + "/Downloads")) if ROOT.drive else str(DL)
            except Exception:
                env["DS_DL"] = str(DL)
            return ["cmd", "/c", str(bat)], env
        return None, None
    sh = APP / "install.sh"
    if sh.is_file():
        env = dict(os.environ)
        env["DS_NO_QB"] = "1"
        return ["/bin/sh", str(sh), "--yes"], env
    return None, None


def apply_env(put=print):
    """把本套件用的环境变量写到用户级（Windows: HKCU\\Environment；POSIX: ~/.profile 片段）。"""
    root = str(ROOT)
    dl = str(DL)
    v2x = _video2x()
    ffdir = ROOT / "tools" / "ffmpeg" / "bin"
    if IS_WIN:
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE | winreg.KEY_READ)
            for name, val in (("DOWNLOADSTACK_ROOT", root),
                              ("DOWNLOADSTACK_DOWNLOADS", dl),
                              ("VIDEO2X_PATH", v2x) if v2x else ("DOWNLOADSTACK_YTBAT", "")):
                if val:
                    winreg.SetValueEx(k, name, 0, winreg.REG_SZ, val)
            # PATH 追加 ffmpeg
            if ffdir.is_dir():
                try:
                    cur, _ = winreg.QueryValueEx(k, "Path")
                except FileNotFoundError:
                    cur = ""
                parts = [p for p in cur.split(";") if p.strip()]
                if str(ffdir).lower() not in [p.lower() for p in parts]:
                    parts.append(str(ffdir))
                    winreg.SetValueEx(k, "Path", 0, winreg.REG_EXPAND_SZ, ";".join(parts))
                    put("  已把 ffmpeg 加入用户 PATH")
            winreg.CloseKey(k)
            put("  已写入环境变量: DOWNLOADSTACK_ROOT / DOWNLOADSTACK_DOWNLOADS%s" % (" / VIDEO2X_PATH" if v2x else ""))
            return True
        except Exception as ex:
            put("  环境变量写入失败: %s" % ex)
            return False
    # POSIX
    try:
        envf = Path.home() / ".config" / "downloadstack" / "env.sh"
        envf.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# DownloadStack env (auto-generated)",
            'export DOWNLOADSTACK_ROOT="%s"' % root,
            'export DOWNLOADSTACK_DOWNLOADS="%s"' % dl,
        ]
        if v2x:
            lines.append('export VIDEO2X_PATH="%s"' % v2x)
        if ffdir.is_dir():
            lines.append('export PATH="%s:$PATH"' % str(ffdir))
        envf.write_text("\n".join(lines) + "\n", encoding="utf-8")
        rc = Path.home() / ".bashrc"
        mark = "# downloadstack env"
        if rc.is_file():
            txt = rc.read_text(encoding="utf-8", errors="ignore")
            if mark not in txt:
                with rc.open("a", encoding="utf-8") as f:
                    f.write('\n%s\n. "%s"\n' % (mark, envf))
        put("  已写入 %s（并挂到 ~/.bashrc）" % envf)
        return True
    except Exception as ex:
        put("  环境变量写入失败: %s" % ex)
        return False


def run_stream(cmd, env, put):
    try:
        proc = subprocess.Popen(cmd, cwd=str(APP), env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                encoding=("mbcs" if IS_WIN else "utf-8"), errors="replace",
                                creationflags=(0x08000000 if IS_WIN else 0),
                                start_new_session=(not IS_WIN))
    except Exception as ex:
        put("启动安装失败: %s" % ex)
        return 1
    for line in proc.stdout:
        put(line.rstrip())
    return proc.wait()


TUTORIAL = r"""DownloadStack 使用教程
==================================================

【第一次使用】
1) 点「重新扫描」看这台机器缺什么（✔ 就绪 / ✘ 缺失）
2) 点「一键安装缺失项」→ 弹出确认 → 点「是」开始自动安装
   安装过程显示在右侧日志，不需要你干预
3) 装完按钮恢复，再点「启动控制台」打开面板

【面板里怎么用】
· 普通文件：点「启动 Aria2 + AriaNg」→ 浏览器会打开 AriaNg
            → 左上「新建」→ 粘贴直链 → 开始
            成品在 <下载根>\aria2
· 平台视频：点「启动 YT 下载壳」→ 打开视频下载器窗口
            → 粘链接 → 选清晰度 → 开始（可勾 2x 超分）
            成品在 <下载根>\yt-dlp
· BT / PT ：装好 qBittorrent 后点「启动 qBittorrent」
            → 「打开 WebUI」→ 拖 .torrent 进去
            成品在 <下载根>\qBittorrent

【灯的含义】
· 绿 ONLINE  = 服务正常
· 灰 OFFLINE = 没启动 / 没安装（点「启动」）
· 红 ERROR   = 装了但连不上（点「测试」看日志原因）

【出问题】
· 面板打不开：跑 diag.bat（Windows）/ sh diag.sh（Linux/macOS）
  生成 diag-report.txt
· 端口冲突：安装器会自动换端口；也能在设置页改
· qB 红灯：设置页填 WebUI 密码（面板有 30 秒失败退避）
"""




# ---------------------------------------------------------------- 逐项安装（带进度）
import urllib.request
import zipfile

URLS = {
    "aria2_win": "https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-win-64bit-build1.zip",
    "ariang": "https://github.com/mayswind/AriaNg/releases/download/1.3.15/AriaNg-1.3.15-AllInOne.zip",
    "ytdlp_win": "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe",
    "ytdlp_linux": "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_linux",
    "ytdlp_mac": "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos",
    "ffmpeg_win": "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
}


def _download(url, dest, put, progress, label):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "downloadstack-wizard/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            tmp = str(dest) + ".part"
            with open(tmp, "wb") as f:
                while True:
                    chunk = r.read(262144)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        progress(done / total)
                        put("      %s %d%% (%.1f/%.1f MB)" % (label, int(done * 100 / total),
                                                             done / 1048576, total / 1048576))
            Path(tmp).replace(dest)
        put("      %s 下载完成" % label)
        return True
    except Exception as ex:
        put("      %s 下载失败: %s" % (label, ex))
        return False


def _unzip(src, dest, put):
    try:
        with zipfile.ZipFile(src) as z:
            z.extractall(dest)
        put("      解压完成 -> %s" % dest)
        return True
    except Exception as ex:
        put("      解压失败: %s" % ex)
        return False


def _safe_cwd():
    """返回一个一定存在的目录，避免 cwd 被删导致 pip 崩（FileNotFoundError）。"""
    for c in (APP, HOME, Path(os.environ.get("TEMP") or ""), Path("/tmp") if not IS_WIN else Path("C:/")):
        try:
            if c and Path(c).is_dir():
                return str(c)
        except Exception:
            continue
    return None


def _run(cmd, put, cwd=None):
    try:
        if cwd is None:
            cwd = _safe_cwd()
        p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding=("mbcs" if IS_WIN else "utf-8"),
                             errors="replace", creationflags=(0x08000000 if IS_WIN else 0))
        for line in p.stdout:
            line = line.rstrip()
            if line:
                put("      " + line[:160])
        return p.wait()
    except Exception as ex:
        put("      执行失败: %s" % ex)
        return 1


SUDO_PW = {"pw": ""}


def _ask_sudo_password():
    """GUI 下弹框要一次密码；文本模式下由调用方提示。"""
    if SUDO_PW["pw"]:
        return SUDO_PW["pw"]
    try:
        import tkinter as tk
        from tkinter import simpledialog
        root = tk._default_root
        if root is None:
            return ""
        try:
            root.attributes("-topmost", True)
            root.update()
        except Exception:
            pass
        pw = simpledialog.askstring("需要管理员权限",
                                    "安装系统包需要 sudo 密码\n（输入内容不会显示，输完回车）",
                                    show="*", parent=root)
        try:
            root.attributes("-topmost", False)
            root.update()
        except Exception:
            pass
        if pw:
            SUDO_PW["pw"] = pw
        return pw or ""
    except Exception:
        return ""


def _sudo_run(cmd, put):
    """优先免密 sudo -n；不行就弹框要密码用 sudo -S 喂进去。"""
    try:
        r = subprocess.run(["sudo", "-n"] + cmd, capture_output=True, text=True,
                           cwd=_safe_cwd())
        if r.returncode == 0:
            put("      （免密 sudo 安装成功）")
            return 0
    except Exception:
        pass
    put("      >>> 安装系统包需要 sudo 密码，正在弹出密码框（它在最前面，请看屏幕）")
    put("      >>> 如果没看到弹框：关掉向导，改用终端执行  sh 一键配置.sh")
    pw = _ask_sudo_password()
    if not pw:
        put("      需要 sudo 密码但没有输入，改为手动安装：")
        put("      sudo " + " ".join(cmd))
        return 1
    try:
        r = subprocess.run(["sudo", "-S", "-p", ""] + cmd, input=pw + "\n",
                           capture_output=True, text=True, timeout=900,
                           cwd=_safe_cwd())
        for line in (r.stdout or "").splitlines()[-6:]:
            if line.strip():
                put("      " + line[:160])
        if r.returncode != 0:
            for line in (r.stderr or "").splitlines()[-4:]:
                if line.strip():
                    put("      ! " + line[:160])
            put("      sudo 执行失败（密码错误？）")
            SUDO_PW["pw"] = ""
        return r.returncode
    except Exception as ex:
        put("      sudo 执行异常: %s" % ex)
        return 1


def install_one(name, put, progress):
    """安装单项，progress(0..1) 汇报该项内部进度。返回 True/False。"""
    root = ROOT
    tmp = Path(os.environ.get("TEMP") or "/tmp") / "downloadstack"
    tmp.mkdir(parents=True, exist_ok=True)

    if name in ("flet 依赖", "requests 依赖", "pip"):
        pkgs = ["flet==1.1.3", "flet-desktop==1.1.3", "requests>=2.31"]
        progress(0.05)

        def try_pip(pyexe, extra):
            cmd = [pyexe, "-m", "pip", "install"] + extra + pkgs
            return _run(cmd, put)

        rc = 1
        venv_py = ROOT / ".venv" / ("Scripts/python.exe" if IS_WIN else "bin/python")
        if venv_py.is_file():
            put("      使用虚拟环境: %s" % venv_py)
            rc = try_pip(str(venv_py), [])
            if rc != 0:
                rc = try_pip(str(venv_py), ["-i", "https://pypi.tuna.tsinghua.edu.cn/simple"])
        if rc != 0 and not IS_WIN:
            vdir = ROOT / ".venv"
            put("      创建虚拟环境 %s ..." % vdir)
            _run([sys.executable, "-m", "venv", str(vdir)], put)
            if not (Path(str(venv_py))).is_file():
                put("      venv 创建失败，先安装 python3-venv ...")
                _sudo_run(["apt-get", "install", "-y", "python3-venv"], put)
                _run([sys.executable, "-m", "venv", str(vdir)], put)
            rc = try_pip(str(venv_py), [])
            if rc != 0:
                put("      venv 里没有 pip，安装 python3-venv 后重试 ...")
                _sudo_run(["apt-get", "install", "-y", "python3-venv"], put)
                _run([sys.executable, "-m", "venv", "--clear", str(vdir)], put)
                rc = try_pip(str(venv_py), [])
        if rc != 0:
            for extra in (["--user"], ["--user", "--break-system-packages"],
                          ["--break-system-packages"],
                          ["--user", "--break-system-packages", "-i",
                           "https://pypi.tuna.tsinghua.edu.cn/simple"]):
                put("      回退尝试: %s" % " ".join(extra))
                rc = try_pip(sys.executable, extra)
                if rc == 0:
                    break
        progress(1.0)
        return rc == 0

    if name == "aria2c":
        exe = root / "aria2" / ("aria2c.exe" if IS_WIN else "aria2c")
        if IS_WIN:
            zp = tmp / "aria2.zip"
            if not _download(URLS["aria2_win"], zp, put, progress, "aria2"):
                return False
            d = tmp / "aria2x"
            if not _unzip(zp, d, put):
                return False
            found = list(d.rglob("aria2c.exe"))
            if not found:
                put("      压缩包里没找到 aria2c.exe")
                return False
            exe.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(found[0], exe)
            put("      aria2c 已放到 %s" % exe)
            return True
        # Linux/macOS：交给包管理器
        if _which("apt-get"):
            return _sudo_run(["apt-get", "install", "-y", "aria2"], put) == 0
        if _which("brew"):
            return _run(["brew", "install", "aria2"], put) == 0
        put("      请手动安装 aria2（sudo apt install -y aria2）")
        return False

    if name == "AriaNg":
        zp = tmp / "ariang.zip"
        if not _download(URLS["ariang"], zp, put, progress, "AriaNg"):
            return False
        d = tmp / "ariangx"
        if not _unzip(zp, d, put):
            return False
        idx = list(d.rglob("index.html"))
        target = root / "ariaNg"
        target.mkdir(parents=True, exist_ok=True)
        if idx:
            src = idx[0].parent
            for f in src.iterdir():
                dest = target / f.name
                if f.is_dir():
                    shutil.copytree(f, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(f, dest)
        put("      AriaNg 已放到 %s" % target)
        return (target / "index.html").is_file()

    if name == "yt-dlp":
        dest = root / ("tools/yt-dlp.exe" if IS_WIN else "tools/yt-dlp")
        url = URLS["ytdlp_win"] if IS_WIN else (URLS["ytdlp_mac"] if IS_MAC else URLS["ytdlp_linux"])
        if not _download(url, dest, put, progress, "yt-dlp"):
            return False
        if not IS_WIN:
            os.chmod(dest, 0o755)
        put("      yt-dlp 已放到 %s" % dest)
        return True

    if name == "ffmpeg":
        if IS_WIN:
            zp = tmp / "ffmpeg.zip"
            if not _download(URLS["ffmpeg_win"], zp, put, progress, "ffmpeg"):
                return False
            d = tmp / "ffmpegx"
            if not _unzip(zp, d, put):
                return False
            exes = list(d.rglob("ffmpeg.exe"))
            target = root / "tools" / "ffmpeg" / "bin"
            target.mkdir(parents=True, exist_ok=True)
            for e in exes:
                shutil.copy2(e, target / e.name)
                for sib in e.parent.glob("ffprobe.exe"):
                    shutil.copy2(sib, target / sib.name)
            put("      ffmpeg 已放到 %s" % target)
            return (target / "ffmpeg.exe").is_file()
        if _which("apt-get"):
            return _sudo_run(["apt-get", "install", "-y", "ffmpeg"], put) == 0
        if _which("brew"):
            return _run(["brew", "install", "ffmpeg"], put) == 0
        put("      请手动安装 ffmpeg（sudo apt install -y ffmpeg）")
        return False

    if os.environ.get("DS_SKIP_QB") == "1":
        put("      已按参数跳过 qBittorrent")
        return True
    if name == "qBittorrent":
        if IS_WIN and _which("winget"):
            return _run(["winget", "install", "--id", "qBittorrent.qBittorrent", "-e", "--silent",
                         "--accept-package-agreements", "--accept-source-agreements"], put) == 0
        if _which("apt-get"):
            return _sudo_run(["apt-get", "install", "-y", "qbittorrent"], put) == 0
        if _which("brew"):
            return _run(["brew", "install", "--cask", "qbittorrent"], put) == 0
        put("      请手动安装 qBittorrent")
        return False

    put("      这一项需要手动处理")
    return False


def install_missing(items, put, set_step=None, set_progress=None):
    """按清单逐项安装；带 (i/n) 与单项进度。Video2X 跳过（需手动装）。"""
    items = [x for x in items if x[0] != "Video2X 超分"]
    names = [x[0] for x in items]
    total = len(names)
    ok_all = True
    for i, name in enumerate(names, 1):
        if set_step:
            set_step(i, total, name)
        put("=== [%d/%d] 正在安装: %s ===" % (i, total, name))

        def prog(f):
            if set_progress:
                set_progress((i - 1 + max(0.0, min(1.0, f))) / total)

        got = install_one(name, put, prog)
        if set_progress:
            set_progress(i / total)
        put("=== [%d/%d] %s: %s ===" % (i, total, name, "完成" if got else "未完成"))
        if not got and name == "qBittorrent":
            put("      qBittorrent 是可选组件（BT/PT 才需要），可稍后手动装： sudo apt install -y qbittorrent")
        ok_all = ok_all and got
    return ok_all


# ---------------------------------------------------------------- GUI
def gui():
    import tkinter as tk
    from tkinter import ttk, messagebox

    root = tk.Tk()
    root.title("DownloadStack 引导安装")
    root.geometry("880x620")
    root.configure(bg="#0B0E11")

    fg, dim, ok, bad, warn = "#E6EDF3", "#7A8A99", "#00E5A0", "#FF6B6B", "#FFB020"

    head = tk.Label(root, text="DownloadStack 安装引导", bg="#0B0E11", fg=ok,
                    font=("Consolas", 16, "bold"))
    head.pack(anchor="w", padx=16, pady=(12, 2))
    sub = tk.Label(root, text="① 先扫描  →  ② 你点「一键安装缺失项」  →  ③ 启动控制台",
                   bg="#0B0E11", fg=dim, font=("Microsoft YaHei UI", 10))
    sub.pack(anchor="w", padx=16)

    body = tk.Frame(root, bg="#0B0E11")
    body.pack(fill="both", expand=True, padx=16, pady=10)

    left = tk.Frame(body, bg="#0B0E11")
    left.pack(side="left", fill="both", expand=True)

    tree = ttk.Treeview(left, columns=("state", "name", "info"), show="headings", height=12)
    for c, t, w in (("state", "状态", 70), ("name", "项目", 150), ("info", "说明/路径", 420)):
        tree.heading(c, text=t)
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    right = tk.Frame(body, bg="#0B0E11")
    right.pack(side="right", fill="both", expand=True, padx=(10, 0))
    step_lbl = tk.Label(right, text="未开始", bg="#0B0E11", fg=warn,
                        font=("Microsoft YaHei UI", 10, "bold"), anchor="w")
    step_lbl.pack(fill="x", pady=(0, 4))
    bar = ttk.Progressbar(right, mode="determinate", maximum=100, value=0)
    bar.pack(fill="x", pady=(0, 6))
    log = tk.Text(right, bg="#04070E", fg=fg, insertbackground=fg,
                  font=("Consolas", 9), wrap="word")
    log.pack(fill="both", expand=True)

    btns = tk.Frame(root, bg="#0B0E11")
    btns.pack(fill="x", padx=16, pady=(0, 12))

    state = {"busy": False}
    q = queue.Queue()

    def fill():
        tree.delete(*tree.get_children())
        for name, good, info, _auto in scan():
            tree.insert("", "end", values=("✔ 就绪" if good else "✘ 缺失", name, info))

    def append(msg):
        log.insert("end", msg + "\n")
        log.see("end")

    def poll():
        try:
            while True:
                msg = q.get_nowait()
                if msg.startswith("__STEP__"):
                    step_lbl.config(text="正在安装 " + msg[8:])
                    continue
                if msg.startswith("__PROG__"):
                    bar["value"] = int(msg[8:])
                    continue
                if msg == "__DONE__":
                    step_lbl.config(text="安装结束")
                    bar["value"] = 100
                    continue
                append(msg)
        except queue.Empty:
            pass
        if state["busy"]:
            root.after(200, poll)

    def do_install():
        if state["busy"]:
            return
        miss = missing()
        if not miss:
            messagebox.showinfo("提示", "没有缺失项，直接点「启动控制台」即可")
            return
        names = "、".join(x[0] for x in miss)
        if not messagebox.askyesno("确认安装",
                                   "检测到缺少：\n%s\n\n现在自动安装吗？\n（会联网下载，可能要几分钟）" % names):
            return
        state["busy"] = True
        btn_install.config(state="disabled")
        btn_full.config(state="disabled")
        btn_launch.config(state="disabled")
        bar["value"] = 0
        append("=== 共 %d 项待安装 ===" % len(miss))

        def set_step(i, n, name):
            q.put("__STEP__%d/%d %s" % (i, n, name))

        def set_progress(f):
            q.put("__PROG__%d" % int(max(0.0, min(1.0, f)) * 100))

        def worker():
            try:
                install_missing(miss, q.put, set_step, set_progress)
            except Exception as ex:
                q.put("安装异常: %s" % ex)
            q.put("__DONE__")
            state["busy"] = False
            root.after(200, after_install)

        threading.Thread(target=worker, daemon=True).start()
        poll()

    def after_install():
        fill()
        btn_install.config(state="normal")
        still = missing()
        if still:
            append("仍有缺失：%s" % "、".join(x[0] for x in still))
        else:
            append("全部就绪，可以启动控制台")
        btn_launch.config(state="normal")
        root.after(600, lambda: None)

    def do_full():
        if state["busy"]:
            return
        if not messagebox.askyesno("一键配置",
                                   "将自动完成：\n  1) 安装缺失的依赖与组件\n  2) 写入环境变量\n\n现在开始吗？"):
            return
        state["busy"] = True
        btn_install.config(state="disabled")
        btn_full.config(state="disabled")
        btn_launch.config(state="disabled")
        bar["value"] = 0
        append("=== 一键配置开始（共 %d 项）===" % len(missing()))

        def worker():
            try:
                still = full_config(lambda s: q.put(s))
                q.put("=== 一键配置结束，剩余缺失: %s ===" % ("、".join(still) if still else "无"))
            except Exception as ex:
                q.put("一键配置异常: %s" % ex)
            state["busy"] = False
            root.after(200, after_install)

        threading.Thread(target=worker, daemon=True).start()
        poll()

    def launch():
        p = APP / "panel.py"
        if not p.is_file():
            messagebox.showerror("失败", "当前目录没有 panel.py")
            return
        env = dict(os.environ)
        env["DOWNLOADSTACK_ROOT"] = str(ROOT)
        args = [sys.executable, "-B", str(p)]
        try:
            if IS_WIN:
                subprocess.Popen(args, cwd=str(APP), env=env,
                                 creationflags=0x00000008 | 0x08000000)
            else:
                subprocess.Popen(args, cwd=str(APP), env=env, start_new_session=True)
            append("已启动控制台")
        except Exception as ex:
            messagebox.showerror("失败", str(ex))

    btn_scan = tk.Button(btns, text="重新扫描", width=12, command=fill,
                         bg="#123", fg=fg, activebackground="#234")
    btn_install = tk.Button(btns, text="一键安装缺失项", width=18, command=do_install,
                            bg="#00E5A0", fg="#04121A", font=("Microsoft YaHei UI", 10, "bold"))
    btn_full = tk.Button(btns, text="一键配置(含环境)", width=16, command=do_full,
                         bg="#00E5A0", fg="#04121A", font=("Microsoft YaHei UI", 10, "bold"))
    btn_launch = tk.Button(btns, text="启动控制台", width=14, command=launch,
                           bg="#00ccff", fg="#04121A", font=("Microsoft YaHei UI", 10, "bold"))
    def show_tutorial():
        win = tk.Toplevel(root)
        win.title("使用教程")
        win.geometry("640x520")
        win.configure(bg="#0B0E11")
        txt = tk.Text(win, bg="#04070E", fg=fg, font=("Microsoft YaHei UI", 10), wrap="word")
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        txt.insert("end", TUTORIAL)
        txt.config(state="disabled")

    btn_tut = tk.Button(btns, text="使用教程", width=10, command=show_tutorial,
                        bg="#123", fg=fg, activebackground="#234")
    btn_quit = tk.Button(btns, text="退出", width=8, command=root.destroy, bg="#123", fg=fg)
    for b in (btn_scan, btn_install, btn_full, btn_launch, btn_tut, btn_quit):
        b.pack(side="left", padx=6)

    fill()
    append("目录: %s" % APP)
    append("安装根: %s" % ROOT)
    append("点「重新扫描」可刷新；点「一键安装缺失项」才会开始装。")
    root.mainloop()


def text_mode():
    """没有图形界面时的逐步引导：扫描 -> 列清单 -> 问一句 -> 调安装脚本。"""
    items = scan()
    miss = missing()
    print("==== DownloadStack 引导安装 ====")
    print("目录:", APP)
    print("安装根:", ROOT)
    print()
    for name, good, info, _auto in items:
        print(("  [OK] " if good else "  [缺] ") + name + ("  (" + info + ")" if info else ""))
    print()
    if not miss:
        print("全部就绪，运行 启动面板.sh / 启动面板.bat 即可")
        return 0
    print("缺少：", "、".join(x[0] for x in miss))
    try:
        ans = input("现在自动安装缺失项吗？[Y/n]: ").strip().lower()
    except EOFError:
        ans = "n"
    if ans in ("n", "no"):
        print("已取消。可手动执行 install.sh / install.bat")
        return 1
    cmd, env = installer_cmd()
    if not cmd:
        print("找不到 install.sh / install.bat")
        return 1
    print("开始安装 ...")
    rc = run_stream(cmd, env, lambda s: print(s, flush=True))
    print("安装进程返回码:", rc)
    still = missing()
    print("剩余缺失:", [x[0] for x in still] or "无")
    return 0 if not still else 1


def full_config(put=print):
    """一键配置核心：逐项装缺的依赖/组件（带进度）+ 写环境变量。"""
    items = [x for x in scan() if not x[1]]
    if items:
        put("缺少 %d 项: %s" % (len(items), "、".join(x[0] for x in items)))
        install_missing(items, put,
                        lambda i, n, name: put(">>> [%d/%d] 正在安装 %s" % (i, n, name)),
                        lambda f: None)
    else:
        put("依赖齐全，跳过安装")
    put("写入环境变量 ...")
    apply_env(put)
    return [x[0] for x in scan() if not x[1]]


def auto_mode():
    """一键配置：扫描 -> 自动装缺的 -> 写环境变量 -> 复扫 -> 报告。"""
    print("==== DownloadStack 一键配置 ====")
    print("目录:", APP)
    items = scan()
    miss = [x[0] for x in items if not x[1]]
    print("扫描结果:")
    for name, good, info, _a in items:
        print(("  [OK] " if good else "  [缺] ") + name)
    still = full_config(lambda s: print(s, flush=True))
    print()
    print("==== 结果 ====")
    print("剩余缺失:", "、".join(still) if still else "无")
    if (APP / "panel.py").is_file():
        print("下一步: 双击 启动面板.bat（Windows）/ sh 启动面板.sh（Linux/macOS）")
    return 0 if not still else 0


def main():
    if "--auto" in sys.argv:
        return auto_mode()
    if "--text" in sys.argv:
        return text_mode()
    if "--scan" in sys.argv:
        for name, good, info, auto in scan():
            print(("OK  " if good else "MISS"), name, "|", info, "| 可自动装:", auto)
        print("missing:", [x[0] for x in missing()])
        return 0
    if (not IS_WIN) and (not IS_MAC) and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        print("检测到没有图形环境（SSH / 无桌面），改用文本引导：")
        print("（提示：想用图形窗口，请在虚拟机桌面里双击运行，不要在 SSH 里跑）")
        print()
        return text_mode()
    try:
        import tkinter  # noqa: F401
    except Exception:
        print("缺少 tkinter（图形界面库）。")
        print("  Ubuntu/Debian: sudo apt install python3-tk")
        print("  Fedora:        sudo dnf install python3-tkinter")
        print("  macOS:         brew install python-tk")
        print("或者直接用命令行安装：sh install.sh  /  install.bat")
        print("也可以走文本引导： python3 setup_wizard.py --text")
        return 2
    gui()
    return 0


if __name__ == "__main__":
    sys.exit(main())
