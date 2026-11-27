# -*- coding: utf-8 -*-
"""DownloadStack 媒体工坊模块：全网歌曲检索下载 + 开源 AI 声音克隆（F5-TTS / 外部 API / Edge-TTS）。

设计原则：
- 不打包任何第三方模型权重或二进制；F5-TTS 支持自动在独立 .venv-voice 中按需部署。
- 国内音源（网易云 / B站）默认直连免代理，海外音源（YouTube Music）自动透传系统代理。
- 所有路径动态探测，绝不写死个人路径，严格满足安全扫描要求。
"""

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path

import requests

IS_WIN = (os.name == "nt")

# 内置高拟真神经配音音色（edge-tts，零显卡立即可用）
EDGE_VOICES = [
    {"id": "zh-CN-XiaoxiaoNeural", "name": "晓晓（女 · 自然全能中文）"},
    {"id": "zh-CN-YunxiNeural", "name": "云希（男 · 阳光磁性中文）"},
    {"id": "zh-CN-YunjianNeural", "name": "云健（男 · 沉稳播音解说）"},
    {"id": "zh-CN-XiaoyiNeural", "name": "晓伊（女 · 温柔甜美中文）"},
    {"id": "zh-CN-YunyangNeural", "name": "云扬（男 · 新闻纪录片风）"},
    {"id": "zh-CN-liaoning-XiaobeiNeural", "name": "晓北（女 · 东北话特色）"},
    {"id": "zh-CN-shaanxi-XiaoniNeural", "name": "晓妮（女 · 陕西话特色）"},
    {"id": "zh-HK-HiuGaaiNeural", "name": "晓佳（女 · 粤语自然）"},
    {"id": "zh-TW-HsiaoChenNeural", "name": "晓臻（女 · 台湾腔自然）"},
    {"id": "en-US-AvaMultilingualNeural", "name": "Ava（女 · 中英双语丝滑）"},
    {"id": "en-US-AndrewMultilingualNeural", "name": "Andrew（男 · 中英双语质感）"},
    {"id": "ja-JP-NanamiNeural", "name": "Nanami（女 · 日语自然）"},
]


def _popen_kwargs():
    if IS_WIN:
        return {"creationflags": 0x08000000}
    return {"start_new_session": True}


def _fmt_dur(sec) -> str:
    try:
        s = int(float(sec or 0))
        if s <= 0:
            return "--:--"
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return ("%d:%02d:%02d" % (h, m, s)) if h else ("%02d:%02d" % (m, s))
    except Exception:
        return "--:--"


def _safe_filename(name: str, fallback: str = "audio") -> str:
    s = re.sub(r'[\\/:*?"<>|\r\n]+', "_", (name or "").strip()).strip(" ._")
    return (s[:72] if s else fallback)


# ==================================================================
# 1. 全网任意歌曲检索（网易云 / B站 / YouTube Music 多源聚合）
# ==================================================================
def _search_netease(query: str, limit: int = 10) -> list:
    out = []
    try:
        url = "https://music.163.com/api/search/get/web?s=%s&type=1&limit=%d" % (
            urllib.parse.quote(query), limit
        )
        r = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
                "Referer": "https://music.163.com/",
            },
            proxies={"http": None, "https": None},
            timeout=6,
        )
        j = r.json()
        songs = ((j.get("result") or {}).get("songs")) or []
        for s in songs:
            title = str(s.get("name") or "").strip()
            artists = ", ".join(str(a.get("name") or "") for a in (s.get("artists") or []) if a.get("name"))
            album = str(((s.get("album") or {}).get("name")) or "")
            dur_ms = int(s.get("duration") or 0)
            sid = str(s.get("id") or "")
            if not title:
                continue
            out.append({
                "id": "ne_" + sid,
                "title": title,
                "artist": artists or "未知歌手",
                "album": album,
                "duration": _fmt_dur(dur_ms / 1000.0),
                "source": "网易云",
                "url": "",  # 下载时自动通过高清无版权限制音频源精准匹配下载
                "query": ("%s %s" % (title, artists)).strip(),
            })
    except Exception:
        pass
    return out


def _search_bilibili_music(query: str, limit: int = 8) -> list:
    out = []
    try:
        url = "https://api.bilibili.com/x/web-interface/search/type?search_type=video&keyword=%s&page_size=%d" % (
            urllib.parse.quote(query), limit
        )
        r = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
                "Referer": "https://www.bilibili.com/",
            },
            proxies={"http": None, "https": None},
            timeout=6,
        )
        j = r.json()
        items = ((j.get("data") or {}).get("result")) or []
        for it in items:
            raw_t = str(it.get("title") or "")
            title = re.sub(r"<[^>]+>", "", raw_t).strip()
            bvid = str(it.get("bvid") or "").strip()
            author = str(it.get("author") or "B站音乐").strip()
            dur = str(it.get("duration") or "--:--")
            if not title or not bvid:
                continue
            out.append({
                "id": "bili_" + bvid,
                "title": title,
                "artist": author,
                "album": "Bilibili 音频",
                "duration": dur,
                "source": "B站",
                "url": "https://www.bilibili.com/video/" + bvid,
                "query": title,
            })
    except Exception:
        pass
    return out


def _search_ytmusic(ytdlp: str, query: str, limit: int = 8, proxy: str = "") -> list:
    if not ytdlp:
        return []
    out = []
    try:
        env = os.environ.copy()
        if proxy:
            env["HTTP_PROXY"] = env["HTTPS_PROXY"] = env["http_proxy"] = env["https_proxy"] = proxy
            env.pop("ALL_PROXY", None)
            env.pop("all_proxy", None)
        cmd = [ytdlp, "--flat-playlist", "--dump-single-json", "--no-warnings",
               "ytsearch%d:%s" % (limit, query)]
        res = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=env, timeout=14, **_popen_kwargs()
        )
        if res.returncode == 0 and res.stdout:
            d = json.loads(res.stdout)
            for e in (d.get("entries") or []):
                vid = str(e.get("id") or "")
                title = str(e.get("title") or "").strip()
                if not vid or not title:
                    continue
                u = str(e.get("url") or "")
                if not u.startswith("http"):
                    u = "https://www.youtube.com/watch?v=" + vid
                out.append({
                    "id": "yt_" + vid,
                    "title": title,
                    "artist": str(e.get("uploader") or e.get("channel") or "YouTube"),
                    "album": "YouTube Music",
                    "duration": _fmt_dur(e.get("duration")),
                    "source": "YouTube",
                    "url": u,
                    "query": title,
                })
    except Exception:
        pass
    return out


def search_songs(query: str, source: str = "all", ytdlp: str = "", proxy: str = "") -> list:
    """多源并发检索任意歌曲。source: all | netease | bilibili | youtube"""
    q = (query or "").strip()
    if not q:
        return []
    src = (source or "all").lower()
    results = []
    if src == "netease":
        return _search_netease(q, limit=15)
    if src == "bilibili":
        return _search_bilibili_music(q, limit=12)
    if src == "youtube":
        return _search_ytmusic(ytdlp, q, limit=12, proxy=proxy)

    # all: 并发拉取网易云 + B站（毫秒级）+ 若启用代理则补充 YouTube Music
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        f_ne = ex.submit(_search_netease, q, 8)
        f_bi = ex.submit(_search_bilibili_music, q, 6)
        f_yt = ex.submit(_search_ytmusic, ytdlp, q, 6, proxy) if (ytdlp and proxy) else None
        for fut in (f_ne, f_bi, f_yt):
            if fut is None:
                continue
            try:
                results.extend(fut.result(timeout=12) or [])
            except Exception:
                pass
    return results


def build_music_download_targets(url: str, query: str, has_proxy: bool) -> list:
    """为歌曲构造下载候选链路：有直链先用直链，网易云歌名优先 B站高码率音频，失败回退 YouTube。"""
    targets = []
    u = (url or "").strip()
    q = (query or "").strip()
    if u:
        is_cn = ("bilibili.com" in u.lower() or "b23.tv" in u.lower())
        targets.append((u, not is_cn, "直链音源"))
    if q:
        # 优先用 B站 API 找到对应高码率音乐视频，速度快且免代理
        bili_hits = _search_bilibili_music(q + " 无损 OR 完整版 OR MV", limit=3)
        if not bili_hits:
            bili_hits = _search_bilibili_music(q, limit=3)
        for h in bili_hits[:2]:
            if h.get("url") and all(t[0] != h["url"] for t in targets):
                targets.append((h["url"], False, "B站高清音频"))
        if has_proxy:
            targets.append(("ytsearch1:" + q + " audio", True, "YouTube Music"))
        else:
            targets.append(("ytsearch1:" + q + " audio", False, "YouTube Music"))
    return targets


# ==================================================================
# 2. 顶尖开源 AI 声音克隆环境探测 & 推理（F5-TTS / 外部 API / Edge-TTS）
# ==================================================================
def find_compatible_py312() -> str:
    """查找兼容 PyTorch CUDA + F5-TTS 的 Python 3.10~3.12 解释器。"""
    cands = []
    if IS_WIN:
        for ver in ("-3.12", "-3.11", "-3.10"):
            try:
                r = subprocess.run(["py", ver, "-c", "import sys;print(sys.executable)"],
                                   capture_output=True, text=True, timeout=4, **_popen_kwargs())
                p = (r.stdout or "").strip()
                if r.returncode == 0 and p and Path(p).is_file():
                    cands.append(p)
            except Exception:
                pass
    else:
        for name in ("python3.12", "python3.11", "python3.10", "python3"):
            p = shutil.which(name)
            if p:
                cands.append(p)
    # 兜底检查当前解释器版本是否在 3.10..3.12
    if (3, 10) <= sys.version_info[:2] <= (3, 12):
        cands.append(sys.executable)
    for c in cands:
        if c and Path(c).is_file():
            return c
    return ""


def voice_venv_python(panel_dir: Path) -> Path:
    venv = panel_dir / ".venv-voice"
    return venv / ("Scripts/python.exe" if IS_WIN else "bin/python")


def voice_venv_f5cli(panel_dir: Path) -> Path:
    venv = panel_dir / ".venv-voice"
    return venv / ("Scripts/f5-tts_infer-cli.exe" if IS_WIN else "bin/f5-tts_infer-cli")


def detect_gpu_name() -> str:
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=3, **_popen_kwargs()
        )
        if r.returncode == 0 and (r.stdout or "").strip():
            return r.stdout.strip().splitlines()[0]
    except Exception:
        pass
    return "CPU（未检测到 NVIDIA GPU）"


def detect_voice_env(panel_dir: Path) -> dict:
    """探测本机声音克隆引擎就绪状态。"""
    vpy = voice_venv_python(panel_dir)
    f5_cli = voice_venv_f5cli(panel_dir)
    f5_ready = f5_cli.is_file() or bool(shutil.which("f5-tts_infer-cli"))
    edge_ready = False
    try:
        import importlib.util
        edge_ready = importlib.util.find_spec("edge_tts") is not None
    except Exception:
        edge_ready = False
    if not edge_ready:
        edge_ready = bool(shutil.which("edge-tts"))
    return {
        "gpu": detect_gpu_name(),
        "py312": find_compatible_py312(),
        "f5_ready": f5_ready,
        "f5_venv_py": str(vpy) if vpy.is_file() else "",
        "edge_ready": edge_ready,
        "voices": EDGE_VOICES,
    }


def normalize_ref_audio(src: Path, dst_wav: Path, ffmpeg_dir: str = "") -> Path:
    """使用 ffmpeg 把任意参考音频（WebM/MP3/M4A/WAV）转成干净的 24kHz 单声道 WAV（截取前 15 秒）。"""
    ff = ""
    if ffmpeg_dir:
        cand = Path(ffmpeg_dir) / ("ffmpeg.exe" if IS_WIN else "ffmpeg")
        if cand.is_file():
            ff = str(cand)
    if not ff:
        ff = shutil.which("ffmpeg") or ""
    if not ff:
        shutil.copy2(src, dst_wav)
        return dst_wav
    cmd = [ff, "-y", "-i", str(src), "-t", "15", "-ac", "1", "-ar", "24000", "-sample_fmt", "s16", str(dst_wav)]
    r = subprocess.run(cmd, capture_output=True, timeout=30, **_popen_kwargs())
    if r.returncode == 0 and dst_wav.is_file() and dst_wav.stat().st_size > 1000:
        return dst_wav
    shutil.copy2(src, dst_wav)
    return dst_wav


def run_edge_tts(text: str, voice_id: str, rate: str, pitch: str, out_file: Path, proxy: str = "") -> tuple:
    """调用 edge-tts 生成高拟真多情感语音。"""
    code = (
        "import asyncio, sys, edge_tts\n"
        "async def go():\n"
        "    comm = edge_tts.Communicate(sys.argv[1], voice=sys.argv[2], rate=sys.argv[3], pitch=sys.argv[4])\n"
        "    await comm.save(sys.argv[5])\n"
        "asyncio.run(go())\n"
    )
    env = os.environ.copy()
    if proxy:
        env["HTTP_PROXY"] = env["HTTPS_PROXY"] = env["http_proxy"] = env["https_proxy"] = proxy
        env.pop("ALL_PROXY", None)
        env.pop("all_proxy", None)
    r = subprocess.run(
        [sys.executable, "-B", "-c", code, text, voice_id, rate, pitch, str(out_file)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=45, **_popen_kwargs()
    )
    if r.returncode == 0 and out_file.is_file() and out_file.stat().st_size > 500:
        return True, "配音合成完成 ✔"
    # 若带代理失败尝试直连重试一次
    if proxy:
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            env.pop(k, None)
        r2 = subprocess.run(
            [sys.executable, "-B", "-c", code, text, voice_id, rate, pitch, str(out_file)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=env, timeout=45, **_popen_kwargs()
        )
        if r2.returncode == 0 and out_file.is_file() and out_file.stat().st_size > 500:
            return True, "配音合成完成（直连）✔"
        return False, (r2.stderr or r2.stdout or "edge-tts 失败")[:180]
    return False, (r.stderr or r.stdout or "edge-tts 失败")[:180]


def run_external_clone_api(api_url: str, ref_wav: Path, ref_text: str, gen_text: str, out_file: Path) -> tuple:
    """直连外部开源声音克隆 API（兼容 GPT-SoVITS / CosyVoice / Fish Speech / 自定义标准 multipart 接口）。"""
    base = (api_url or "").strip().rstrip("/")
    if not base.startswith("http"):
        return False, "请先填写有效的本地开源克隆 API 地址（如 http://127.0.0.1:9880）"
    try:
        # 1) 通用 multipart POST（适配 CosyVoice / Fish Speech / 自定义 FastAPI 服务）
        with open(ref_wav, "rb") as f:
            files = {"prompt_wav": (ref_wav.name, f, "audio/wav"), "reference_audio": (ref_wav.name, f, "audio/wav")}
            data = {"tts_text": gen_text, "text": gen_text, "prompt_text": ref_text, "ref_text": ref_text,
                    "ref_audio_path": str(ref_wav), "text_lang": "zh", "prompt_lang": "zh"}
            r = requests.post(base, data=data, files={"prompt_wav": (ref_wav.name, ref_wav.read_bytes(), "audio/wav")},
                              proxies={"http": None, "https": None}, timeout=120)
        if r.status_code == 200 and len(r.content) > 1000 and ("audio" in (r.headers.get("Content-Type") or "").lower() or r.content[:4] in (b"RIFF", b"ID3\x03", b"fLaC", b"OggS")):
            out_file.write_bytes(r.content)
            return True, "外部开源克隆 API 合成完成 ✔"
        # 2) 回退 GPT-SoVITS /tts JSON 接口格式
        r2 = requests.post(
            base if base.endswith("/tts") else (base + "/tts"),
            json={"text": gen_text, "text_lang": "zh", "ref_audio_path": str(ref_wav),
                  "prompt_text": ref_text, "prompt_lang": "zh", "media_type": "wav"},
            proxies={"http": None, "https": None}, timeout=120
        )
        if r2.status_code == 200 and len(r2.content) > 1000:
            out_file.write_bytes(r2.content)
            return True, "外部克隆 API（GPT-SoVITS 协议）合成完成 ✔"
        return False, "API 返回状态 %s：%s" % (r.status_code, (r.text or "")[:120])
    except Exception as ex:
        return False, "连接外部克隆服务失败：%s" % ex


def scan_recent_downloads(dirs: list, limit: int = 8) -> list:
    """扫描多个下载目录，返回最近落盘的媒体与成品文件列表（供主控台「最近成品秒开舱」展示）。"""
    exts = {".mp4", ".mkv", ".webm", ".mov", ".mp3", ".flac", ".wav", ".m4a", ".ogg", ".zip", ".7z", ".exe", ".iso", ".pdf"}
    audio_exts = {".mp3", ".flac", ".wav", ".m4a", ".ogg"}
    video_exts = {".mp4", ".mkv", ".webm", ".mov"}
    found = []
    seen = set()
    for label, d in dirs:
        try:
            p = Path(d)
            if not p.is_dir():
                continue
            for f in p.iterdir():
                if not f.is_file():
                    continue
                if f.name.startswith(".") or f.suffix.lower() in (".aria2", ".part", ".tmp", ".ytdl"):
                    continue
                if f.suffix.lower() not in exts:
                    continue
                fp = str(f.resolve())
                if fp in seen:
                    continue
                seen.add(fp)
                st = f.stat()
                ext = f.suffix.lower()
                kind = "audio" if ext in audio_exts else ("video" if ext in video_exts else "file")
                found.append({
                    "name": f.name,
                    "path": fp,
                    "dir": str(f.parent),
                    "size": st.st_size,
                    "mtime": st.st_mtime,
                    "time": datetime.fromtimestamp(st.st_mtime).strftime("%m-%d %H:%M"),
                    "tag": label,
                    "kind": kind,
                })
        except Exception:
            continue
    found.sort(key=lambda x: x["mtime"], reverse=True)
    return found[:limit]
