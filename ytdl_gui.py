# -*- coding: utf-8 -*-
"""YT 视频下载器（GUI）—— DownloadStack 附带组件

用法：
    python ytdl_gui.py            # 打开窗口
    python ytdl_gui.py --check    # 自检（不联网）

行为：
1. 粘链接 -> 选清晰度 -> 开始，走 yt-dlp 下载到「保存目录」
2. 打开「2x 超分」时，若检测到 video2x，下载完成后自动超分（否则提示跳过）
3. 取消会结束整个进程树（不会留后台下载）
"""
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import flet as ft

APP_DIR = Path(__file__).resolve().parent
IS_WIN = os.name == "nt"
HOME = Path(os.environ.get("USERPROFILE") or Path.home())


def _detect_root() -> Path:
    env = (os.environ.get("DOWNLOADSTACK_ROOT") or "").strip()
    if env:
        return Path(env)
    for cand in (APP_DIR, APP_DIR.parent, APP_DIR.parent.parent):
        if (cand / "aria2").is_dir() or (cand / "tools").is_dir():
            return cand
    return APP_DIR


ROOT = _detect_root()
DL = Path(os.environ.get("DOWNLOADSTACK_DOWNLOADS") or (HOME / "Downloads"))

SETTINGS = APP_DIR / "ytdl_settings.json"


def load_settings() -> dict:
    try:
        import json
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(d: dict):
    try:
        import json
        SETTINGS.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


BG, CARD, LINE = "#05070E", "#0B1526", "#00ccff55"
MINT, CYAN, ERR, TXT, SUB = "#00E5A0", "#00ccff", "#FF4D4F", "#D8F5FF", "#6C8BA3"


URL_RE = re.compile(r"""https?://[^\s，。、；："'<>()（）\[\]【】]+""")


def clean_url(text: str) -> str:
    """从抖音/小红书那种"复制打开…"的整段文案里提取出真正的链接。"""
    s = (text or "").strip()
    m = URL_RE.search(s)
    return m.group(0) if m else s


def find_ytdlp() -> str:
    """返回可直接执行的 yt-dlp 命令（字符串）。"""
    env = (os.environ.get("YTDLP_PATH") or "").strip()
    if env and Path(env).is_file():
        return env
    for cand in (ROOT / "tools" / "yt-dlp.exe", ROOT / "tools" / "yt-dlp",
                 DL / "ytdlp" / "yt-dlp.exe", DL / "ytdlp" / "yt-dlp"):
        if cand.is_file():
            return str(cand)
    which = shutil.which("yt-dlp")
    if which:
        return which
    return ""


def find_video2x() -> str:
    env = (os.environ.get("VIDEO2X_PATH") or "").strip()
    if env and Path(env).is_file():
        return env
    for cand in (ROOT / "tools" / "video2x" / "video2x.exe",
                 Path("D:/Video2X/video2x.exe")):
        if cand.is_file():
            return str(cand)
    which = shutil.which("video2x")
    return which or ""


def run_cmd(cmd, cwd=None, env=None):
    if IS_WIN:
        return subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace",
                                creationflags=0x08000000)
    return subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace",
                            start_new_session=True)


def kill_tree(pid):
    try:
        if IS_WIN:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           capture_output=True, creationflags=0x08000000)
        else:
            import signal
            os.killpg(os.getpgid(pid), signal.SIGTERM)
    except Exception:
        pass


class App:
    def __init__(self, page: ft.Page):
        self.p = page
        self.proc = None
        self.worker = None
        self.page = page
        self.p.title = "DownloadStack · 视频下载器"
        self.p.bgcolor = BG
        self.p.padding = 16
        self.p.theme_mode = ft.ThemeMode.DARK
        try:
            self.p.window.width = 900
            self.p.window.height = 640
        except Exception:
            pass
        self.ytdlp = find_ytdlp()
        self.v2x = find_video2x()
        self._build()

    # ---------------- UI ----------------
    def _build(self):
        _st = load_settings()
        self.url = ft.TextField(label="视频链接",
                                hint_text="粘贴 YouTube / B站 / 抖音等链接",
                                bgcolor="#0A1222", color=TXT, dense=True,
                                border=ft.InputBorder.OUTLINE, text_size=13,
                                expand=True)
        self.out = ft.TextField(label="保存目录", value=_st.get("out") or str(DL / "yt-dlp"),
                                bgcolor="#0A1222", color=TXT, dense=True,
                                border=ft.InputBorder.OUTLINE, text_size=12,
                                expand=True)
        self.quality = ft.Dropdown(
            label="清晰度", value=_st.get("quality", "best"), width=200,
            options=[ft.dropdown.Option("best", "最佳"),
                     ft.dropdown.Option("1080", "≤1080P"),
                     ft.dropdown.Option("720", "≤720P"),
                     ft.dropdown.Option("audio", "仅音频(mp3)")],
            bgcolor="#0A1222", color=TXT, text_size=12,
            border=ft.InputBorder.OUTLINE)
        self.auth = ft.Dropdown(
            label="登录状态 / Cookies", value=_st.get("auth", "none"), width=210,
            options=[ft.dropdown.Option("none", "不需要"),
                     ft.dropdown.Option("firefox", "用 Firefox 登录态"),
                     ft.dropdown.Option("chrome", "用 Chrome 登录态"),
                     ft.dropdown.Option("chromium", "用 Chromium 登录态"),
                     ft.dropdown.Option("edge", "用 Edge 登录态")],
            bgcolor="#0A1222", color=TXT, text_size=12, border=ft.InputBorder.OUTLINE)
        self.cookies = ft.TextField(label="cookies.txt 路径（可选，优先于上面的登录态）",
                                    value=_st.get("cookies", ""),
                                    bgcolor="#0A1222", color=TXT, dense=True,
                                    border=ft.InputBorder.OUTLINE, text_size=12, expand=True)
        self.upscale = ft.Switch(label="下载后 2x 超分", value=bool(_st.get("upscale", False)),
                                 active_color=MINT,
                                 disabled=(not self.v2x))
        self.btn_start = ft.FilledButton(content=ft.Text("开始下载", color="#04121A"),
                                         bgcolor=MINT, on_click=self.on_start)
        self.btn_stop = ft.FilledButton(content=ft.Text("取消", color="#fff"),
                                        bgcolor=ERR, on_click=self.on_stop,
                                        disabled=True)
        self.btn_open = ft.OutlinedButton(content=ft.Text("打开保存目录"),
                                          on_click=lambda e: self.open_dir())
        self.status = ft.Text("", size=12, color=SUB)
        self.log = ft.ListView(expand=True, spacing=1, auto_scroll=True)
        self.env_txt = ft.Text(
            "yt-dlp: %s%s" % (self.ytdlp or "未找到",
                              "" if not self.v2x else "  |  超分: 已检测到 video2x"),
            size=10, color=(MINT if self.ytdlp else ERR))

        head = ft.Row([
            ft.Text("DOWNLOAD STACK // VIDEO", size=16, weight=ft.FontWeight.BOLD,
                    color=MINT, font_family="Consolas"),
            ft.Container(expand=True),
            self.env_txt,
        ])
        card = ft.Container(
            bgcolor="#CC0A1222", border=ft.Border.all(1, LINE), border_radius=10,
            padding=12,
            content=ft.Column([
                self.url,
                ft.Row([self.out, self.quality], spacing=8),
                ft.Row([self.auth, self.cookies], spacing=8),
                ft.Row([self.upscale, self.btn_start, self.btn_stop, self.btn_open],
                       spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                self.status,
            ], spacing=10))
        log_box = ft.Container(
            bgcolor="#CC04070E", border=ft.Border.all(1, MINT + "55"), border_radius=10,
            padding=8, expand=True,
            content=ft.Column([
                ft.Text("输出日志", size=11, color=MINT, font_family="Consolas"),
                ft.Container(content=self.log, expand=True),
            ], spacing=4, expand=True))
        self.p.add(ft.Column([head, card, log_box], spacing=12, expand=True))

    # ---------------- 动作 ----------------
    def say(self, s, color=TXT):
        try:
            self.log.controls.append(ft.Text(s, size=11, color=color, font_family="Consolas"))
            self.p.update()
        except Exception:
            pass

    def open_dir(self):
        d = Path(self.out.value or "")
        try:
            d.mkdir(parents=True, exist_ok=True)
            if IS_WIN:
                os.startfile(str(d))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(d)])
            else:
                subprocess.Popen(["xdg-open", str(d)])
        except Exception as ex:
            self.say("打开目录失败: %s" % ex, ERR)

    def on_start(self, e=None):
        url = (self.url.value or "").strip()
        if not url:
            self.say("先粘链接", ERR)
            return
        if not self.ytdlp:
            self.say("没找到 yt-dlp.exe：先运行安装向导，或把 yt-dlp 放进 tools/", ERR)
            return
        outdir = Path(self.out.value or (DL / "yt-dlp"))
        outdir.mkdir(parents=True, exist_ok=True)
        fmt = {"best": "bv*+ba/b", "1080": "bv*[height<=1080]+ba/b[height<=1080]",
               "720": "bv*[height<=720]+ba/b[height<=720]", "audio": "ba/b"}[self.quality.value]
        url = clean_url(url)
        self.url.value = url
        save_settings({
            "out": str(self.out.value or ""),
            "quality": self.quality.value,
            "auth": self.auth.value,
            "cookies": (self.cookies.value or ""),
            "upscale": bool(self.upscale.value),
        })
        cmd = [self.ytdlp, "-P", str(outdir), "-f", fmt, "--newline", "--no-mtime"]
        cookies_file = (self.cookies.value or "").strip()
        if cookies_file and Path(cookies_file).is_file():
            cmd += ["--cookies", cookies_file]
            self.say("使用 cookies.txt: " + cookies_file)
        elif self.auth.value and self.auth.value != "none":
            cmd += ["--cookies-from-browser", self.auth.value]
            self.say("使用浏览器登录态: " + self.auth.value)
        if self.quality.value == "audio":
            cmd += ["-x", "--audio-format", "mp3"]
        cmd.append(url)

        self.btn_start.disabled = True
        self.btn_stop.disabled = False
        self.status.value = "下载中..."
        self.p.update()
        self.say("执行: " + " ".join(cmd[:6]) + " ...")

        env = dict(os.environ)
        self.worker = threading.Thread(target=self._run, args=(cmd, outdir, env), daemon=True)
        self.worker.start()

    def _run(self, cmd, outdir, env):
        try:
            self.proc = run_cmd(cmd, cwd=str(outdir), env=env)
        except Exception as ex:
            self.say("启动失败: %s" % ex, ERR)
            self._done(False)
            return
        last = ""
        for line in self.proc.stdout:
            line = line.rstrip("\n")
            if not line:
                continue
            if line.startswith("[download]") or "Destination" in line or "Merger" in line:
                m = re.search(r"(\d+\.\d+)%", line)
                if m:
                    last = m.group(1)
                    self.status.value = "下载中 %s%%" % last
                    try:
                        self.p.update()
                    except Exception:
                        pass
                continue
            if line.startswith("ERROR") or "error" in line.lower()[:30]:
                self.say(line[:200], ERR)
                self._tips(line)
            else:
                self.say(line[:200], SUB)
        rc = self.proc.wait()
        if rc == 0 and self.upscale.value and self.v2x:
            self.say("下载完成，开始 2x 超分 ...", CYAN)
            self._upscale(outdir)
        self._done(rc == 0)

    def _upscale(self, outdir):
        files = sorted([f for f in outdir.iterdir()
                        if f.suffix.lower() in (".mp4", ".mkv", ".webm", ".mov")],
                       key=lambda f: f.stat().st_mtime, reverse=True)
        if not files:
            self.say("没找到刚下载的视频，跳过超分", ERR)
            return
        src = files[0]
        dst = outdir / (src.stem + "_2x.mp4")
        cmd = [self.v2x, "-i", str(src), "-o", str(dst),
               "-p", "libplacebo", "--libplacebo-shader", "anime4k-v4-c+a",
               "-d", "0", "-c", "libx264", "--pix-fmt", "yuv420p"]
        self.say("超分: " + src.name)
        try:
            p = run_cmd(cmd, cwd=str(Path(self.v2x).parent))
            for line in p.stdout:
                pass
            p.wait()
        except Exception as ex:
            self.say("超分失败: %s" % ex, ERR)

    def _tips(self, text):
        low = (text or "").lower()
        if "403" in low or "forbidden" in low or "cookies" in low:
            self.say("提示：该站点需要登录态 → 在上面选「用 Firefox/Chrome 登录态」，"
                     "或导出 cookies.txt 填进 cookies 路径", CYAN)
        if "not a valid url" in low:
            self.say("提示：请只粘贴视频链接（本工具会自动从分享文案里提取）", CYAN)

    def _done(self, ok):
        self.btn_start.disabled = False
        self.btn_stop.disabled = True
        self.status.value = "完成" if ok else "结束（见日志）"
        try:
            self.p.update()
        except Exception:
            pass

    def on_stop(self, e=None):
        if self.proc:
            kill_tree(self.proc.pid)
            self.say("已取消", ERR)
        self.btn_start.disabled = False
        self.btn_stop.disabled = True
        self.p.update()


def check():
    print("ROOT :", ROOT)
    print("yt-dlp:", find_ytdlp() or "未找到")
    print("video2x:", find_video2x() or "未找到（超分会跳过）")
    return 0 if find_ytdlp() else 1


def main(page: ft.Page):
    App(page)


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(check())
    ft.run(main)
