# -*- coding: utf-8 -*-
"""在桌面创建名为「DownloadStack Control」的静默无黑框快捷方式（图标缓存位于软件所在盘符 cache/icons/）。"""
import ctypes
import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent


def ensure_d_icon_cache() -> Path:
    cache_dir = APP_DIR / "cache" / "icons"
    cache_dir.mkdir(parents=True, exist_ok=True)
    ico_dst = cache_dir / "DownloadStackControl.ico"
    png_dst = cache_dir / "DownloadStackControl.png"
    assets_dir = APP_DIR / "assets"
    if (assets_dir / "DownloadStackControl.ico").is_file() and not ico_dst.is_file():
        shutil.copy2(assets_dir / "DownloadStackControl.ico", ico_dst)
    if (assets_dir / "DownloadStackControl.png").is_file() and not png_dst.is_file():
        shutil.copy2(assets_dir / "DownloadStackControl.png", png_dst)
    return ico_dst


def create_windows_desktop_shortcut() -> Path:
    if os.name != "nt":
        raise RuntimeError("桌面 .lnk 快捷方式仅适用于 Windows")
    ico_path = ensure_d_icon_cache()
    pyw = Path(sys.executable).with_name("pythonw.exe")
    target_exe = str(pyw if pyw.is_file() else Path(sys.executable))
    launcher = str(APP_DIR / "launch_app.pyw")

    ps = (
        "$desk = [Environment]::GetFolderPath('Desktop'); "
        "$lnkPath = Join-Path $desk 'DownloadStack Control.lnk'; "
        "$ws = New-Object -ComObject WScript.Shell; "
        "$sc = $ws.CreateShortcut($lnkPath); "
        f"$sc.TargetPath = '{target_exe}'; "
        f"$sc.Arguments = '\"{launcher}\"'; "
        f"$sc.WorkingDirectory = '{APP_DIR}'; "
        f"$sc.IconLocation = '{ico_path},0'; "
        "$sc.Description = 'DownloadStack Control v2.5 · Spatial 3D Command OS'; "
        "$sc.WindowStyle = 7; "
        "$sc.Save(); "
        "Write-Output $lnkPath"
    )
    res = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
    )
    lnk = Path(res.stdout.strip().splitlines()[-1].strip())
    # Notify Windows Shell to refresh Desktop icon immediately
    try:
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    except Exception:
        pass
    return lnk


if __name__ == "__main__":
    p = create_windows_desktop_shortcut()
    print(f"[OK] Desktop shortcut created: {p}")
