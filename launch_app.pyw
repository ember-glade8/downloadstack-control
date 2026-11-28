# -*- coding: utf-8 -*-
"""DownloadStack Control v2.5 — 静默无黑框桌面应用启动器。
双击桌面快捷方式「DownloadStack Control」时运行：
1) 若 18550 本地服务未启动，则无窗口静默拉起 panel.py；
2) 以独立桌面应用窗口模式（无地址栏、独立 App Profile 与图标缓存均存放在软件所在盘符 cache/ 下，不占 C 盘）打开控制台并播放 3D 电影级启动动画。
"""
import ctypes
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
PORT = 18550
# 带上启动时间戳：每次打开都是全新 URL，强制 Chromium 重新拉取页面，
# 避免固定 profile 里缓存住旧版 panel_ui.html（改了界面看不到的问题）
URL = f"http://127.0.0.1:{PORT}/?boot=1&v={int(time.time())}"


def _set_app_id():
    if os.name == "nt":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DownloadStack.Control.v25")
        except Exception:
            pass


def _port_open(port: int = PORT) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.35):
            return True
    except Exception:
        return False


def _ensure_server():
    if _port_open(PORT):
        return True
    pyw = Path(sys.executable).with_name("pythonw.exe")
    exe = str(pyw if pyw.is_file() else Path(sys.executable))
    code = (
        f"import sys; sys.path.insert(0, {str(APP_DIR)!r}); "
        "import panel; panel.run_3d_server(open_browser=False)"
    )
    flags = 0x08000000 | 0x00000008 if os.name == "nt" else 0
    try:
        subprocess.Popen(
            [exe, "-B", "-u", "-c", code],
            cwd=str(APP_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=flags,
            close_fds=True,
        )
    except Exception:
        return False
    for _ in range(55):
        if _port_open(PORT):
            return True
        time.sleep(0.15)
    return _port_open(PORT)


def _find_chromium_app_host() -> str:
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    local = os.environ.get("LOCALAPPDATA") or ""
    if local:
        candidates.extend([
            str(Path(local) / r"Microsoft\Edge\Application\msedge.exe"),
            str(Path(local) / r"Google\Chrome\Application\chrome.exe"),
        ])
    for c in candidates:
        if Path(c).is_file():
            return c
    return ""


def _open_standalone_window():
    host = _find_chromium_app_host()
    if host:
        profile_dir = APP_DIR / "cache" / "app_profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            host,
            f"--app={URL}",
            f"--user-data-dir={profile_dir}",
            "--window-size=1520,940",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-features=TranslateUI",
        ]
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
            return
        except Exception:
            pass
    import webbrowser
    webbrowser.open(URL)


def main():
    _set_app_id()
    _ensure_server()
    _open_standalone_window()


if __name__ == "__main__":
    main()
