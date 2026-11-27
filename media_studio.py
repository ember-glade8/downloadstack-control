# -*- coding: utf-8 -*-
"""DownloadStack 媒体与 AI 工坊模块：
1) 全网任意歌曲检索 + 6 大实时音乐榜单 + 本地/在线 LRC 同步歌词
2) 开源 AI 声音克隆（F5-TTS / 外部 API / Edge-TTS）
3) 本地 ComfyUI 生图/生视频（Z-Image Turbo / Wan 2.2 I2V / 终端用户自定义本地模型）
4) 中转 Codex「赛博小怪兽」内置智能体客户端

设计原则：
- 不打包任何第三方模型权重或二进制；F5-TTS 支持在独立 .venv-voice 中按需部署。
- 国内音源（网易云 / B站）默认直连免代理，海外音源（YouTube Music）自动透传系统代理。
- 绝不硬编码任何个人路径或 API 密钥，全部从本机 config.json 读取，严格满足安全扫描要求。
"""

import base64
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
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
# 1. 全网 6 大音源并发检索 + 6 大音乐榜单 + 多源 LRC 同步歌词 + 在线音频流解析
# ==================================================================
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
_BILI_SESSION = None
_BILI_SESSION_TS = 0.0


def _clean_html_text(s: str) -> str:
    import html as _html
    t = str(s or "")
    t = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), t)
    t = re.sub(r"<[^>]+>", "", t)
    t = _html.unescape(t).replace("\xa0", " ")
    return re.sub(r"\s+", " ", t).strip()


def _get_bili_session():
    global _BILI_SESSION, _BILI_SESSION_TS
    now = time.time()
    if _BILI_SESSION is None or (now - _BILI_SESSION_TS) > 1800.0:
        s = requests.Session()
        s.headers.update({"User-Agent": _UA, "Referer": "https://www.bilibili.com/"})
        try:
            s.get("https://www.bilibili.com/", proxies={"http": None, "https": None}, timeout=5)
        except Exception:
            pass
        _BILI_SESSION = s
        _BILI_SESSION_TS = now
    return _BILI_SESSION


def _search_qq(query: str, limit: int = 10) -> list:
    out = []
    try:
        body = {
            "comm": {"ct": "19", "cv": "1859", "uin": "0"},
            "req": {
                "method": "DoSearchForQQMusicDesktop",
                "module": "music.search.SearchCgiService",
                "param": {"grp": 1, "num_per_page": limit, "page_num": 1, "query": query, "search_type": 0},
            },
        }
        r = requests.post(
            "https://u.y.qq.com/cgi-bin/musicu.fcg",
            json=body,
            headers={"User-Agent": _UA, "Referer": "https://y.qq.com/"},
            proxies={"http": None, "https": None},
            timeout=6,
        )
        lst = (((r.json().get("req") or {}).get("data") or {}).get("body") or {}).get("song", {}).get("list") or []
        for s in lst:
            title = _clean_html_text(s.get("name") or s.get("title") or "")
            if not title:
                continue
            artists = ", ".join(str(a.get("name") or "") for a in (s.get("singer") or []) if a.get("name"))
            alb = s.get("album") or {}
            album = _clean_html_text(alb.get("name") or "")
            amid = str(alb.get("mid") or "").strip()
            cover = ("https://y.qq.com/music/photo_new/T002R300x300M000%s.jpg" % amid) if amid else ""
            mid = str(s.get("mid") or s.get("id") or "")
            dur = int(s.get("interval") or 0)
            out.append({
                "id": "qq_" + mid,
                "sid": "",
                "title": title,
                "artist": artists or "未知歌手",
                "album": album,
                "cover": cover,
                "duration": _fmt_dur(dur),
                "source": "QQ音乐",
                "url": "",
                "query": ("%s %s" % (title, artists)).strip(),
            })
    except Exception:
        pass
    return out


def _search_kugou(query: str, limit: int = 10) -> list:
    out = []
    try:
        r = requests.get(
            "http://mobilecdn.kugou.com/api/v3/search/song",
            params={"format": "json", "keyword": query, "page": 1, "pagesize": limit},
            headers={"User-Agent": _UA},
            proxies={"http": None, "https": None},
            timeout=6,
        )
        info = (r.json().get("data") or {}).get("info") or []
        for s in info:
            title = _clean_html_text(s.get("songname") or "")
            if not title:
                continue
            artist = _clean_html_text(s.get("singername") or "未知歌手")
            album = _clean_html_text(s.get("album_name") or "")
            dur = int(s.get("duration") or 0)
            h = str(s.get("hash") or "")
            out.append({
                "id": "kg_" + h[:16],
                "sid": "",
                "kg_hash": h,
                "dur_ms": dur * 1000,
                "title": title,
                "artist": artist,
                "album": album,
                "cover": "",
                "duration": _fmt_dur(dur),
                "source": "酷狗",
                "url": "",
                "query": ("%s %s" % (title, artist)).strip(),
            })
    except Exception:
        pass
    return out


def _search_kuwo(query: str, limit: int = 8) -> list:
    out = []
    try:
        r = requests.get(
            "http://search.kuwo.cn/r.s",
            params={
                "all": query, "ft": "music", "itemset": "web_2013",
                "client": "kt", "pn": 0, "rn": limit, "rformat": "json", "encoding": "utf8",
            },
            headers={"User-Agent": _UA},
            proxies={"http": None, "https": None},
            timeout=6,
        )
        j = json.loads(r.text.replace("'", '"'))
        for s in (j.get("abslist") or []):
            title = _clean_html_text(s.get("SONGNAME") or "")
            if not title:
                continue
            artist = _clean_html_text(s.get("ARTIST") or "未知歌手")
            album = _clean_html_text(s.get("ALBUM") or "")
            dur = int(s.get("DURATION") or 0)
            rid = str(s.get("MUSICRID") or "").replace("MUSIC_", "")
            pic = str(s.get("hts_MVPIC") or s.get("web_albumpic_short") or "")
            if pic and not pic.startswith("http"):
                pic = "https://img4.kuwo.cn/star/albumcover/" + pic.lstrip("/")
            out.append({
                "id": "kw_" + rid,
                "sid": "",
                "title": title,
                "artist": artist,
                "album": album,
                "cover": pic,
                "duration": _fmt_dur(dur),
                "source": "酷我",
                "url": "",
                "query": ("%s %s" % (title, artist)).strip(),
            })
    except Exception:
        pass
    return out


def _search_netease(query: str, limit: int = 10) -> list:
    out = []
    try:
        r = requests.post(
            "https://music.163.com/api/cloudsearch/pc",
            data={"s": query, "type": 1, "limit": limit, "offset": 0},
            headers={"User-Agent": _UA, "Referer": "https://music.163.com/"},
            proxies={"http": None, "https": None},
            timeout=6,
        )
        songs = ((r.json().get("result") or {}).get("songs")) or []
        if not songs:
            url = "https://music.163.com/api/search/get/web?s=%s&type=1&limit=%d" % (
                urllib.parse.quote(query), limit
            )
            r2 = requests.get(
                url,
                headers={"User-Agent": _UA, "Referer": "https://music.163.com/"},
                proxies={"http": None, "https": None},
                timeout=6,
            )
            songs = ((r2.json().get("result") or {}).get("songs")) or []
        for s in songs:
            title = str(s.get("name") or "").strip()
            if not title:
                continue
            ars = s.get("ar") or s.get("artists") or []
            artists = ", ".join(str(a.get("name") or "") for a in ars if a.get("name"))
            alb = s.get("al") or s.get("album") or {}
            album = str(alb.get("name") or "")
            cover = str(alb.get("picUrl") or "")
            dur_ms = int(s.get("dt") or s.get("duration") or 0)
            sid = str(s.get("id") or "")
            out.append({
                "id": "ne_" + sid,
                "sid": sid,
                "title": title,
                "artist": artists or "未知歌手",
                "album": album,
                "cover": cover,
                "duration": _fmt_dur(dur_ms / 1000.0),
                "source": "网易云",
                "url": "",
                "query": ("%s %s" % (title, artists)).strip(),
            })
    except Exception:
        pass
    return out


def _search_bilibili_music(query: str, limit: int = 8) -> list:
    out = []
    try:
        sess = _get_bili_session()
        r = sess.get(
            "https://api.bilibili.com/x/web-interface/search/type",
            params={"search_type": "video", "keyword": query, "page": 1, "page_size": limit},
            proxies={"http": None, "https": None},
            timeout=6,
        )
        j = r.json()
        items = ((j.get("data") or {}).get("result")) or []
        for it in items:
            title = _clean_html_text(it.get("title") or "")
            bvid = str(it.get("bvid") or "").strip()
            author = _clean_html_text(it.get("author") or "B站音乐")
            dur = str(it.get("duration") or "--:--")
            pic = str(it.get("pic") or "")
            if pic.startswith("//"):
                pic = "https:" + pic
            if not title or not bvid:
                continue
            out.append({
                "id": "bili_" + bvid,
                "sid": "",
                "bvid": bvid,
                "title": title,
                "artist": author,
                "album": "Bilibili 音频",
                "cover": pic,
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
                    "sid": "",
                    "title": title,
                    "artist": str(e.get("uploader") or e.get("channel") or "YouTube"),
                    "album": "YouTube Music",
                    "cover": str(e.get("thumbnail") or ""),
                    "duration": _fmt_dur(e.get("duration")),
                    "source": "YouTube",
                    "url": u,
                    "query": title,
                })
    except Exception:
        pass
    return out


def search_songs(query: str, source: str = "all", ytdlp: str = "", proxy: str = "") -> list:
    """6 大音源并发检索任意歌曲。source: all | qq | kugou | netease | kuwo | bilibili | youtube | ytmusic"""
    q = (query or "").strip()
    if not q:
        return []
    src = (source or "all").lower()
    if src == "qq":
        return _search_qq(q, limit=18)
    if src == "kugou":
        return _search_kugou(q, limit=18)
    if src == "kuwo":
        return _search_kuwo(q, limit=15)
    if src == "netease":
        return _search_netease(q, limit=18)
    if src == "bilibili":
        return _search_bilibili_music(q, limit=15)
    if src in ("youtube", "ytmusic"):
        return _search_ytmusic(ytdlp, q, limit=14, proxy=proxy)

    import concurrent.futures
    buckets = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futs = [
            ex.submit(_search_qq, q, 8),
            ex.submit(_search_kugou, q, 8),
            ex.submit(_search_netease, q, 8),
            ex.submit(_search_bilibili_music, q, 6),
            ex.submit(_search_kuwo, q, 5),
        ]
        if ytdlp and proxy:
            futs.append(ex.submit(_search_ytmusic, ytdlp, q, 5, proxy))
        for fut in futs:
            try:
                rows = fut.result(timeout=10) or []
                if rows:
                    buckets.append(rows)
            except Exception:
                pass

    # Interleave results across sources & deduplicate by (title, artist, source)
    results = []
    seen = set()
    max_len = max((len(b) for b in buckets), default=0)
    for i in range(max_len):
        for b in buckets:
            if i >= len(b):
                continue
            item = b[i]
            key = (item.get("title", "").lower(), item.get("artist", "").lower(), item.get("source", ""))
            if key in seen:
                continue
            seen.add(key)
            results.append(item)
    return results[:45]


# 各大热门音乐榜单（网易云 v6 + QQ 音乐官方榜单双源兜底，毫秒级响应）
MUSIC_CHARTS = [
    {"id": "hot", "pid": "3778678", "qq_top": 26, "name": "热歌榜", "icon": "🔥", "desc": "全网热度 TOP 榜"},
    {"id": "soar", "pid": "19723756", "qq_top": 62, "name": "飙升榜", "icon": "🚀", "desc": "24小时热度暴涨"},
    {"id": "new", "pid": "3779629", "qq_top": 27, "name": "新歌榜", "icon": "✨", "desc": "最新发行热单"},
    {"id": "douyin", "pid": "2250011882", "qq_top": 60, "name": "抖音热歌", "icon": "📱", "desc": "短视频爆款神曲"},
    {"id": "orig", "pid": "2884035", "qq_top": 52, "name": "原创榜", "icon": "🎸", "desc": "华语独立佳作"},
    {"id": "western", "pid": "2809513713", "qq_top": 3, "name": "欧美热歌", "icon": "🌍", "desc": "全球欧美流行榜"},
]

_CHART_CACHE = {}


def _fetch_qq_toplist(top_id: int, meta: dict, limit: int = 40) -> list:
    rows = []
    try:
        body = {
            "comm": {"ct": "24", "cv": "0"},
            "toplist": {
                "module": "musicToplist.ToplistInfoServer",
                "method": "GetDetail",
                "param": {"topId": int(top_id), "offset": 0, "num": min(60, limit), "period": ""},
            },
        }
        r = requests.post(
            "https://u.y.qq.com/cgi-bin/musicu.fcg",
            json=body,
            headers={"User-Agent": _UA, "Referer": "https://y.qq.com/"},
            proxies={"http": None, "https": None},
            timeout=7,
        )
        songs = (((r.json().get("toplist") or {}).get("data") or {}).get("songInfoList")) or []
        for idx, s in enumerate(songs[:limit], 1):
            title = _clean_html_text(s.get("name") or s.get("title") or "")
            if not title:
                continue
            artists = ", ".join(str(a.get("name") or "") for a in (s.get("singer") or []) if a.get("name"))
            alb = s.get("album") or {}
            album = _clean_html_text(alb.get("name") or "")
            amid = str(alb.get("mid") or "").strip()
            cover = ("https://y.qq.com/music/photo_new/T002R300x300M000%s.jpg" % amid) if amid else ""
            dur = int(s.get("interval") or 0)
            mid = str(s.get("mid") or s.get("id") or "")
            rows.append({
                "rank": idx,
                "id": "qq_" + mid,
                "sid": "",
                "title": title,
                "artist": artists or "未知歌手",
                "album": album,
                "cover": cover,
                "duration": _fmt_dur(dur),
                "source": "QQ音乐",
                "chart": meta["name"],
                "url": "",
                "query": ("%s %s" % (title, artists)).strip(),
            })
    except Exception:
        pass
    return rows


def fetch_music_chart(chart_id: str = "hot", limit: int = 40) -> dict:
    """拉取各大音乐榜单实时曲目列表（网易云 v6 + QQ 音乐双源兜底，10 分钟内存缓存）。"""
    cid = str(chart_id or "hot").strip().lower()
    meta = next((c for c in MUSIC_CHARTS if c["id"] == cid or c["pid"] == cid), MUSIC_CHARTS[0])
    now = time.time()
    cached = _CHART_CACHE.get(meta["id"])
    if cached and (now - cached[0]) < 600.0:
        rows = cached[1][:limit]
        return {"ok": bool(rows), "chart": meta, "results": rows,
                "msg": "已加载 %s（%d 首）" % (meta["name"], len(rows))}
    rows = []
    # 1) NetEase v6 playlist API
    try:
        url = "https://music.163.com/api/v6/playlist/detail?id=%s&n=%d" % (
            urllib.parse.quote(meta["pid"]), min(60, limit)
        )
        r = requests.get(
            url,
            headers={"User-Agent": _UA, "Referer": "https://music.163.com/"},
            proxies={"http": None, "https": None},
            timeout=7,
        )
        j = r.json()
        tracks = ((j.get("playlist") or {}).get("tracks")) or ((j.get("result") or {}).get("tracks")) or []
        for idx, s in enumerate(tracks[:60], 1):
            title = str(s.get("name") or "").strip()
            if not title:
                continue
            ars = s.get("ar") or s.get("artists") or []
            artists = ", ".join(str(a.get("name") or "") for a in ars if a.get("name"))
            alb = s.get("al") or s.get("album") or {}
            album = str(alb.get("name") or "")
            cover = str(alb.get("picUrl") or "")
            dur_ms = int(s.get("dt") or s.get("duration") or 0)
            sid = str(s.get("id") or "")
            rows.append({
                "rank": idx,
                "id": "ne_" + sid,
                "sid": sid,
                "title": title,
                "artist": artists or "未知歌手",
                "album": album,
                "cover": cover,
                "duration": _fmt_dur(dur_ms / 1000.0),
                "source": "网易云",
                "chart": meta["name"],
                "url": "",
                "query": ("%s %s" % (title, artists)).strip(),
            })
    except Exception:
        pass

    # 2) Fallback to QQ Music official toplist if NetEase returned empty
    if not rows and meta.get("qq_top"):
        rows = _fetch_qq_toplist(meta["qq_top"], meta, limit=limit)

    if rows:
        _CHART_CACHE[meta["id"]] = (now, rows)
    out = rows[:limit]
    return {
        "ok": bool(out),
        "chart": meta,
        "results": out,
        "msg": ("已加载 %s（%d 首）" % (meta["name"], len(out))) if out else "榜单加载失败，请稍后重试",
    }


def parse_lrc(lrc_text: str, trans_text: str = "") -> list:
    """解析标准 LRC 时间轴歌词（支持同步翻译），返回按时间排序的 [{t, text, trans}]。"""
    ts_re = re.compile(r"\[(\d{1,3}):(\d{2})(?:\.(\d{1,3}))?\]")

    def _extract(raw: str) -> list:
        rows = []
        for line in (raw or "").splitlines():
            line = line.strip()
            if not line:
                continue
            tags = list(ts_re.finditer(line))
            if not tags:
                continue
            txt = ts_re.sub("", line).strip()
            if not txt:
                continue
            for m in tags:
                mm = int(m.group(1))
                ss = int(m.group(2))
                ms_s = m.group(3) or "0"
                frac = int(ms_s) / (1000.0 if len(ms_s) == 3 else (100.0 if len(ms_s) == 2 else 10.0))
                rows.append((round(mm * 60 + ss + frac, 2), txt))
        rows.sort(key=lambda x: x[0])
        return rows

    main_rows = _extract(lrc_text)
    trans_rows = _extract(trans_text)
    out = []
    for t, txt in main_rows:
        tr = ""
        if trans_rows:
            best = min(trans_rows, key=lambda x: abs(x[0] - t))
            if abs(best[0] - t) <= 0.8:
                tr = best[1]
        out.append({"t": t, "text": txt, "trans": tr})
    if not out and (lrc_text or "").strip():
        for i, ln in enumerate((lrc_text or "").splitlines()):
            s = ln.strip()
            if s:
                out.append({"t": float(i * 3), "text": s, "trans": ""})
    return out


def _clean_song_query(title: str, artist: str = "") -> str:
    """把带有无损/频道修饰词的标题清洗为纯净的歌名 + 歌手，方便精准匹配歌词。"""
    s = re.sub(r"\.(mp3|flac|wav|m4a|ogg|aac)$", "", (title or ""), flags=re.I)
    m_book = re.search(r"《([^》]{1,40})》", s)
    core = m_book.group(1) if m_book else s
    core = re.sub(r"【[^】]*】|\[[^\]]*\]|\([^)]*\)|（[^）]*）", " ", core)
    core = re.sub(r"(?:Hi-?Res|无损音质|无损|原唱|完整版|高清|MV|Official|Audio|Lyrics|320K|FLAC)", " ", core, flags=re.I)
    core = re.sub(r"[｜|·\-_]+", " ", core).strip()
    art = (artist or "").strip()
    if art and art not in ("未知歌手", "B站音乐", "YouTube") and art.lower() not in core.lower():
        if len(art) <= 14 and "音乐" not in art and "电台" not in art:
            core = ("%s %s" % (core, art)).strip()
    return re.sub(r"\s+", " ", core).strip()[:48]


def _fetch_kugou_lyrics(title: str, artist: str = "", query: str = "") -> tuple:
    """从酷狗歌词库拉取精准 LRC（覆盖周杰伦等全华语版权，毫秒直连）。"""
    kw = _clean_song_query(title or query, artist) or (title or query or "").strip()
    if not kw:
        return [], ""
    try:
        r = requests.get(
            "http://krcs.kugou.com/search",
            params={"ver": 1, "man": "yes", "client": "mobi", "keyword": kw, "duration": ""},
            headers={"User-Agent": _UA},
            proxies={"http": None, "https": None},
            timeout=5,
        )
        cands = (r.json() or {}).get("candidates") or []
        if not cands and title:
            r = requests.get(
                "http://krcs.kugou.com/search",
                params={"ver": 1, "man": "yes", "client": "mobi", "keyword": _clean_song_query(title), "duration": ""},
                headers={"User-Agent": _UA},
                proxies={"http": None, "https": None},
                timeout=5,
            )
            cands = (r.json() or {}).get("candidates") or []
        for c in cands[:3]:
            cid, akey = c.get("id"), c.get("accesskey")
            if not cid or not akey:
                continue
            r2 = requests.get(
                "http://lyrics.kugou.com/download",
                params={"ver": 1, "client": "pc", "id": cid, "accesskey": akey, "fmt": "lrc", "charset": "utf8"},
                headers={"User-Agent": _UA},
                proxies={"http": None, "https": None},
                timeout=5,
            )
            b64 = (r2.json() or {}).get("content") or ""
            if not b64:
                continue
            raw = base64.b64decode(b64).decode("utf-8", errors="ignore")
            lines = parse_lrc(raw)
            if lines:
                return lines, raw
    except Exception:
        pass
    return [], ""


def fetch_song_lyrics(song_id: str = "", title: str = "", artist: str = "", query: str = "", audio_path: str = "") -> dict:
    """获取真实时间轴歌词（LRC）：优先本地 .lrc → 网易云（含翻译）→ 酷狗全版权歌词库。"""
    matched_title = (title or query or "").strip()
    matched_artist = (artist or "").strip()
    if audio_path:
        try:
            lrc_file = Path(audio_path).with_suffix(".lrc")
            if lrc_file.is_file() and lrc_file.stat().st_size > 12:
                raw_local = lrc_file.read_text(encoding="utf-8", errors="ignore")
                local_lines = parse_lrc(raw_local)
                if local_lines:
                    return {
                        "ok": True,
                        "sid": str(song_id or ""),
                        "title": matched_title or lrc_file.stem,
                        "artist": matched_artist,
                        "lines": local_lines,
                        "raw": raw_local,
                        "cover": "",
                        "msg": "已加载本地同步歌词（%d 行）" % len(local_lines),
                    }
        except Exception:
            pass

    sid = ""
    raw_id = str(song_id or "").strip()
    if raw_id.startswith("ne_"):
        sid = raw_id[3:]
    elif raw_id.isdigit():
        sid = raw_id

    cover = ""
    if not sid:
        q = _clean_song_query(title or query, artist)
        if not q and query:
            q = query.strip()
        hits = _search_netease(q, limit=5) if q else []
        if not hits and title:
            hits = _search_netease(_clean_song_query(title)[:24], limit=5)
        if hits:
            h = hits[0]
            sid = str(h.get("sid") or h.get("id", "").replace("ne_", ""))
            if not matched_title:
                matched_title = h.get("title") or ""
            if not matched_artist or matched_artist in ("未知歌手", "B站音乐", "YouTube"):
                matched_artist = h.get("artist") or ""
            cover = h.get("cover") or ""

    # 1) Try NetEase LRC if sid found
    if sid:
        try:
            url = "https://music.163.com/api/song/lyric?id=%s&lv=1&kv=1&tv=-1" % urllib.parse.quote(sid)
            r = requests.get(
                url,
                headers={"User-Agent": _UA, "Referer": "https://music.163.com/"},
                proxies={"http": None, "https": None},
                timeout=6,
            )
            j = r.json()
            raw_lrc = str(((j.get("lrc") or {}).get("lyric")) or "")
            raw_trans = str(((j.get("tlyric") or {}).get("lyric")) or "")
            lines = parse_lrc(raw_lrc, raw_trans)
            if lines:
                return {
                    "ok": True,
                    "sid": sid,
                    "title": matched_title or "歌曲",
                    "artist": matched_artist,
                    "lines": lines,
                    "raw": raw_lrc,
                    "cover": cover,
                    "msg": "已同步 %d 行时间轴歌词（网易云）" % len(lines),
                }
        except Exception:
            pass

    # 2) Fallback to Kugou LRC (covers Jay Chou & full Chinese catalog!)
    kg_lines, kg_raw = _fetch_kugou_lyrics(matched_title, matched_artist, query)
    if kg_lines:
        return {
            "ok": True,
            "sid": sid,
            "title": matched_title or "歌曲",
            "artist": matched_artist,
            "lines": kg_lines,
            "raw": kg_raw,
            "cover": cover,
            "msg": "已同步 %d 行时间轴歌词（酷狗曲库）" % len(kg_lines),
        }

    return {
        "ok": False, "title": matched_title or "未知歌曲", "artist": matched_artist,
        "lines": [], "raw": "", "cover": cover,
        "msg": "未在歌词库匹配到该歌曲，可在歌词页搜索框输入纯歌名重试",
    }


def _extract_bvid(text: str) -> str:
    m = re.search(r"(BV[0-9A-Za-z]{10})", str(text or ""))
    return m.group(1) if m else ""


def _resolve_bili_audio_stream(bvid: str) -> tuple:
    """毫秒级解析 B站高码率 DASH 音频直链（无需下载即可秒播）。"""
    if not bvid:
        return "", ""
    try:
        sess = _get_bili_session()
        r = sess.get(
            "https://api.bilibili.com/x/web-interface/view",
            params={"bvid": bvid},
            proxies={"http": None, "https": None},
            timeout=6,
        )
        data = (r.json() or {}).get("data") or {}
        cid = data.get("cid")
        if not cid:
            return "", ""
        r2 = sess.get(
            "https://api.bilibili.com/x/player/playurl",
            params={"bvid": bvid, "cid": cid, "fnval": 16, "fourk": 0},
            proxies={"http": None, "https": None},
            timeout=6,
        )
        d2 = (r2.json() or {}).get("data") or {}
        dash = d2.get("dash") or {}
        audios = dash.get("audio") or []
        if audios:
            # Prefer highest bandwidth m4a/aac stream for maximum browser compatibility
            audios_sorted = sorted(audios, key=lambda x: int(x.get("bandwidth") or 0), reverse=True)
            best = audios_sorted[0]
            u = best.get("baseUrl") or best.get("base_url") or (best.get("backupUrl") or [""])[0]
            mime = best.get("mimeType") or best.get("mime_type") or "audio/mp4"
            if u:
                return u, mime
        durl = d2.get("durl") or []
        if durl and durl[0].get("url"):
            return durl[0]["url"], "video/mp4"
    except Exception:
        pass
    return "", ""


def _find_local_music_match(music_dir: str, title: str, artist: str = "") -> str:
    """检查本地音乐目录是否已有同名音频文件，命中即零延迟本地播放。"""
    if not music_dir or not title:
        return ""
    try:
        p = Path(music_dir)
        if not p.is_dir():
            return ""
        clean_t = _clean_song_query(title).lower()
        clean_a = (artist or "").strip().lower()
        if len(clean_t) < 2:
            return ""
        best = ""
        for f in p.iterdir():
            if not f.is_file() or f.suffix.lower() not in (".mp3", ".flac", ".m4a", ".wav", ".ogg", ".aac"):
                continue
            stem = f.stem.lower()
            if clean_t in stem:
                if clean_a and clean_a in stem:
                    return str(f.resolve())
                if not best:
                    best = str(f.resolve())
        return best
    except Exception:
        return ""


def resolve_music_stream(title: str = "", artist: str = "", url: str = "", query: str = "",
                         bvid: str = "", ytdlp: str = "", proxy: str = "", music_dir: str = "") -> dict:
    """为任意音源歌曲解析秒播音频流：本地已下文件 → B站直链 DASH 音频 → 智能匹配 B站高码率音频 → yt-dlp bestaudio。"""
    # 1) Local downloaded file match
    local_fp = _find_local_music_match(music_dir, title or query, artist)
    if local_fp:
        return {"ok": True, "is_local": True, "local_path": local_fp, "source": "本地无损", "msg": "命中本地已下载音频 ✔"}

    # 2) Direct Bilibili bvid stream
    bv = bvid or _extract_bvid(url)
    if bv:
        su, mime = _resolve_bili_audio_stream(bv)
        if su:
            return {
                "ok": True, "is_local": False, "stream_url": su, "mime": mime,
                "headers": {"Referer": "https://www.bilibili.com/", "User-Agent": _UA},
                "use_proxy": False, "source": "B站高码率流", "msg": "B站高清音频流就绪 ✔",
            }

    # 3) Direct YouTube / video URL via yt-dlp -g
    u = (url or "").strip()
    if u and ytdlp and ("youtube.com" in u.lower() or "youtu.be" in u.lower()):
        try:
            env = os.environ.copy()
            if proxy:
                env["HTTP_PROXY"] = env["HTTPS_PROXY"] = env["http_proxy"] = env["https_proxy"] = proxy
                env.pop("ALL_PROXY", None)
                env.pop("all_proxy", None)
            r = subprocess.run(
                [ytdlp, "-f", "bestaudio[ext=m4a]/bestaudio", "-g", "--no-warnings", u],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                env=env, timeout=14, **_popen_kwargs()
            )
            su = (r.stdout or "").strip().splitlines()[0].strip() if r.stdout else ""
            if r.returncode == 0 and su.startswith("http"):
                return {
                    "ok": True, "is_local": False, "stream_url": su, "mime": "audio/mp4",
                    "headers": {"User-Agent": _UA},
                    "use_proxy": bool(proxy), "source": "YouTube 音频流", "msg": "YouTube 音频流就绪 ✔",
                }
        except Exception:
            pass

    # 4) Cross-source instant match on Bilibili (works for QQ / Kugou / NetEase / Kuwo including Jay Chou!)
    q_clean = _clean_song_query(title or query, artist) or (query or title or "").strip()
    if q_clean:
        for cand_q in (q_clean + " 无损 OR 完整版 OR 原唱", q_clean):
            hits = _search_bilibili_music(cand_q, limit=5)
            for h in hits:
                hbv = h.get("bvid") or _extract_bvid(h.get("url") or "")
                if not hbv:
                    continue
                su, mime = _resolve_bili_audio_stream(hbv)
                if su:
                    return {
                        "ok": True, "is_local": False, "stream_url": su, "mime": mime,
                        "headers": {"Referer": "https://www.bilibili.com/", "User-Agent": _UA},
                        "use_proxy": False, "source": "B站跨源秒播", "msg": "已自动匹配高清音源流 ✔",
                    }

    # 5) Final fallback: yt-dlp ytsearch1 audio
    if q_clean and ytdlp and proxy:
        try:
            env = os.environ.copy()
            env["HTTP_PROXY"] = env["HTTPS_PROXY"] = env["http_proxy"] = env["https_proxy"] = proxy
            env.pop("ALL_PROXY", None)
            env.pop("all_proxy", None)
            r = subprocess.run(
                [ytdlp, "-f", "bestaudio[ext=m4a]/bestaudio", "-g", "--no-warnings", "ytsearch1:" + q_clean + " audio"],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                env=env, timeout=15, **_popen_kwargs()
            )
            su = (r.stdout or "").strip().splitlines()[0].strip() if r.stdout else ""
            if r.returncode == 0 and su.startswith("http"):
                return {
                    "ok": True, "is_local": False, "stream_url": su, "mime": "audio/mp4",
                    "headers": {"User-Agent": _UA},
                    "use_proxy": True, "source": "YouTube 跨源流", "msg": "已通过 YouTube 匹配音频流 ✔",
                }
        except Exception:
            pass

    return {"ok": False, "msg": "暂未解析到可播放音频流，可点击下载按钮离线播放"}


def build_music_download_targets(url: str, query: str, has_proxy: bool) -> list:
    """为歌曲构造下载候选链路：有直链先用直链，网易云歌名优先 B站高码率音频，失败回退 YouTube。"""
    targets = []
    u = (url or "").strip()
    q = (query or "").strip()
    if u:
        is_cn = ("bilibili.com" in u.lower() or "b23.tv" in u.lower())
        targets.append((u, not is_cn, "直链音源"))
    if q:
        bili_hits = _search_bilibili_music(q + " 无损 OR 完整版 OR MV", limit=3)
        if not bili_hits:
            bili_hits = _search_bilibili_music(q, limit=3)
        for h in bili_hits[:2]:
            if h.get("url") and all(t[0] != h["url"] for t in targets):
                targets.append((h["url"], False, "B站高清音频"))
        targets.append(("ytsearch1:" + q + " audio", bool(has_proxy), "YouTube Music"))
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
    """使用 ffmpeg 把任意参考音频转成干净的 24kHz 单声道 WAV（截取前 15 秒）。"""
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
    """直连外部开源声音克隆 API（兼容 GPT-SoVITS / CosyVoice / Fish Speech）。"""
    base = (api_url or "").strip().rstrip("/")
    if not base.startswith("http"):
        return False, "请先填写有效的本地开源克隆 API 地址（如 http://127.0.0.1:9880）"
    try:
        data = {"tts_text": gen_text, "text": gen_text, "prompt_text": ref_text, "ref_text": ref_text,
                "ref_audio_path": str(ref_wav), "text_lang": "zh", "prompt_lang": "zh"}
        r = requests.post(base, data=data, files={"prompt_wav": (ref_wav.name, ref_wav.read_bytes(), "audio/wav")},
                          proxies={"http": None, "https": None}, timeout=120)
        if r.status_code == 200 and len(r.content) > 1000 and (
            "audio" in (r.headers.get("Content-Type") or "").lower()
            or r.content[:4] in (b"RIFF", b"ID3\x03", b"fLaC", b"OggS")
        ):
            out_file.write_bytes(r.content)
            return True, "外部开源克隆 API 合成完成 ✔"
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


# ==================================================================
# 3. 本地 ComfyUI 生图 / 生视频 + 终端用户自定义本地模型接入
# ==================================================================
def _list_ready_models(root_dir: Path, subdir: str) -> list:
    """列出 ComfyUI 模型目录中已完整落盘的模型文件（自动跳过含 .aria2 未完成文件）。"""
    out = []
    seen = set()
    for base in (root_dir / "models" / subdir, root_dir / "ComfyUI" / "models" / subdir):
        if not base.is_dir():
            continue
        for f in base.iterdir():
            if not f.is_file():
                continue
            if f.suffix.lower() not in (".safetensors", ".ckpt", ".pt", ".gguf", ".pth"):
                continue
            if (f.parent / (f.name + ".aria2")).exists():
                continue
            if f.name not in seen:
                seen.add(f.name)
                out.append(f.name)
    out.sort()
    return out


def detect_comfyui_models(comfy_root: str = "", start_bat: str = "") -> dict:
    """探测本地 ComfyUI 目录中已就绪的生图 / 生视频模型清单。"""
    root_s = (comfy_root or "").strip()
    root = Path(root_s) if root_s else None
    if not root or not root.is_dir():
        return {
            "root_exists": False,
            "has_start_bat": bool(start_bat and Path(start_bat).is_file()),
            "z_image_ready": False,
            "wan22_i2v_ready": False,
            "diffusion_models": [],
            "checkpoints": [],
            "loras": [],
            "vae": [],
            "text_encoders": [],
        }
    diff = _list_ready_models(root, "diffusion_models")
    ckpts = _list_ready_models(root, "checkpoints")
    loras = _list_ready_models(root, "loras")
    vaes = _list_ready_models(root, "vae")
    clips = _list_ready_models(root, "text_encoders")

    z_ready = (
        "z_image_turbo_bf16.safetensors" in diff
        and "qwen_3_4b.safetensors" in clips
        and "ae.safetensors" in vaes
    )
    wan_ready = (
        "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors" in diff
        and "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors" in diff
        and "umt5_xxl_fp8_e4m3fn_scaled.safetensors" in clips
        and "wan_2.1_vae.safetensors" in vaes
    )
    wan_lora_ready = (
        "wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors" in loras
        and "wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors" in loras
    )
    bat_ok = bool(start_bat and Path(start_bat).is_file())
    if not bat_ok:
        for cand in ("run_minimax_h3.bat", "run_nvidia_gpu.bat", "run.bat"):
            if (root / cand).is_file():
                bat_ok = True
                break
    return {
        "root_exists": True,
        "has_start_bat": bat_ok,
        "z_image_ready": z_ready,
        "wan22_i2v_ready": wan_ready,
        "wan22_lora_ready": wan_lora_ready,
        "diffusion_models": diff,
        "checkpoints": ckpts,
        "loras": loras,
        "vae": vaes,
        "text_encoders": clips,
    }


def probe_comfyui_server(base_url: str, timeout: float = 1.5) -> dict:
    """探测 ComfyUI HTTP 服务是否在线及队列状态。"""
    url = (base_url or "http://127.0.0.1:8188").strip().rstrip("/")
    try:
        r = requests.get(url + "/system_stats", timeout=timeout, proxies={"http": None, "https": None})
        if r.status_code == 200:
            stats = r.json() if r.content else {}
            devs = stats.get("devices") or []
            vram_free_gb = 0.0
            vram_tot_gb = 0.0
            dev_name = ""
            if devs:
                d0 = devs[0]
                dev_name = str(d0.get("name") or "")
                vram_free_gb = round(float(d0.get("vram_free") or 0) / (1024 ** 3), 2)
                vram_tot_gb = round(float(d0.get("vram_total") or 0) / (1024 ** 3), 2)
            q_run, q_pend = 0, 0
            try:
                qr = requests.get(url + "/queue", timeout=1.0, proxies={"http": None, "https": None}).json()
                q_run = len(qr.get("queue_running") or [])
                q_pend = len(qr.get("queue_pending") or [])
            except Exception:
                pass
            return {
                "online": True,
                "url": url,
                "device": dev_name,
                "vram_free_gb": vram_free_gb,
                "vram_total_gb": vram_tot_gb,
                "queue_running": q_run,
                "queue_pending": q_pend,
            }
    except Exception:
        pass
    return {
        "online": False,
        "url": url,
        "device": "",
        "vram_free_gb": 0.0,
        "vram_total_gb": 0.0,
        "queue_running": 0,
        "queue_pending": 0,
    }


def comfyui_free_vram(base_url: str, timeout: float = 6.0) -> tuple:
    """调用 ComfyUI /free 卸载缓存模型并释放显存（8G 显存跨模型切换防 OOM 关键步骤）。"""
    url = (base_url or "http://127.0.0.1:8188").strip().rstrip("/")
    try:
        r = requests.post(
            url + "/free",
            json={"unload_models": True, "free_memory": True},
            timeout=timeout,
            proxies={"http": None, "https": None},
        )
        if r.status_code == 200:
            return True, "已通知 ComfyUI 卸载缓存模型并释放显存 ✔"
        return False, "释放显存返回 HTTP %s" % r.status_code
    except Exception as ex:
        return False, "释放显存失败：%s" % ex


def build_zimage_t2i_workflow(prompt: str, neg_prompt: str = "", width: int = 1024, height: int = 576,
                              steps: int = 8, seed: int = -1, cfg: float = 1.0,
                              filename_prefix: str = "DS_ZImg") -> dict:
    """构造本地 Z-Image Turbo 文生图标准 ComfyUI API Prompt 工作流。"""
    sd = int(seed) if (seed is not None and int(seed) >= 0) else random.randint(1, 2 ** 31 - 1)
    w = max(256, min(1536, (int(width) // 16) * 16))
    h = max(256, min(1536, (int(height) // 16) * 16))
    st = max(4, min(30, int(steps or 8)))
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "z_image_turbo_bf16.safetensors",
                "weight_dtype": "default",
            },
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen_3_4b.safetensors",
                "type": "lumina2",
                "device": "default",
            },
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "ae.safetensors"},
        },
        "4": {
            "class_type": "ModelSamplingAuraFlow",
            "inputs": {"model": ["1", 0], "shift": 3.0},
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": str(prompt or ""), "clip": ["2", 0]},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": str(neg_prompt or ""), "clip": ["2", 0]},
        },
        "7": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {"width": w, "height": h, "batch_size": 1},
        },
        "8": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["4", 0],
                "positive": ["5", 0],
                "negative": ["6", 0],
                "latent_image": ["7", 0],
                "seed": sd,
                "steps": st,
                "cfg": float(cfg or 1.0),
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0,
            },
        },
        "9": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["8", 0], "vae": ["3", 0]},
        },
        "10": {
            "class_type": "SaveImage",
            "inputs": {"images": ["9", 0], "filename_prefix": filename_prefix},
        },
    }


def build_wan22_i2v_workflow(prompt: str, neg_prompt: str, image_name: str,
                             width: int = 832, height: int = 480, length: int = 33,
                             steps: int = 4, seed: int = -1, fps: float = 16.0,
                             use_4step_lora: bool = True) -> dict:
    """构造本地 Wan 2.2 I2V 14B FP8 (+ LightX2V 4-step LoRA) 图生视频工作流（8GB 显存友好）。"""
    sd = int(seed) if (seed is not None and int(seed) >= 0) else random.randint(1, 2 ** 31 - 1)
    w = max(256, min(1280, (int(width) // 16) * 16))
    h = max(256, min(1280, (int(height) // 16) * 16))
    n_frames = max(17, min(81, ((int(length or 33) - 1) // 4) * 4 + 1))
    st = max(4, min(20, int(steps or (4 if use_4step_lora else 12))))
    split_step = max(1, st // 2)
    neg = str(neg_prompt or "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的")

    wf = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors",
                "weight_dtype": "default",
            },
        },
        "2": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
                "weight_dtype": "default",
            },
        },
        "3": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                "type": "wan",
                "device": "default",
            },
        },
        "4": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "wan_2.1_vae.safetensors"},
        },
        "5": {
            "class_type": "LoadImage",
            "inputs": {"image": str(image_name)},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": str(prompt or ""), "clip": ["3", 0]},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": neg, "clip": ["3", 0]},
        },
        "8": {
            "class_type": "WanImageToVideo",
            "inputs": {
                "positive": ["6", 0],
                "negative": ["7", 0],
                "vae": ["4", 0],
                "width": w,
                "height": h,
                "length": n_frames,
                "batch_size": 1,
                "start_image": ["5", 0],
            },
        },
    }

    high_src = ["1", 0]
    low_src = ["2", 0]
    if use_4step_lora:
        wf["11"] = {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["1", 0],
                "lora_name": "wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors",
                "strength_model": 1.0,
            },
        }
        wf["12"] = {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["2", 0],
                "lora_name": "wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors",
                "strength_model": 1.0,
            },
        }
        high_src = ["11", 0]
        low_src = ["12", 0]

    wf["13"] = {"class_type": "ModelSamplingSD3", "inputs": {"model": high_src, "shift": 5.0}}
    wf["14"] = {"class_type": "ModelSamplingSD3", "inputs": {"model": low_src, "shift": 5.0}}
    wf["15"] = {
        "class_type": "KSamplerAdvanced",
        "inputs": {
            "model": ["13", 0],
            "add_noise": "enable",
            "noise_seed": sd,
            "steps": st,
            "cfg": 1.0 if use_4step_lora else 3.5,
            "sampler_name": "euler",
            "scheduler": "simple",
            "positive": ["8", 0],
            "negative": ["8", 1],
            "latent_image": ["8", 2],
            "start_at_step": 0,
            "end_at_step": split_step,
            "return_with_leftover_noise": "enable",
        },
    }
    wf["16"] = {
        "class_type": "KSamplerAdvanced",
        "inputs": {
            "model": ["14", 0],
            "add_noise": "disable",
            "noise_seed": 0,
            "steps": st,
            "cfg": 1.0 if use_4step_lora else 3.5,
            "sampler_name": "euler",
            "scheduler": "simple",
            "positive": ["8", 0],
            "negative": ["8", 1],
            "latent_image": ["15", 0],
            "start_at_step": split_step,
            "end_at_step": 10000,
            "return_with_leftover_noise": "disable",
        },
    }
    wf["17"] = {"class_type": "VAEDecode", "inputs": {"samples": ["16", 0], "vae": ["4", 0]}}
    wf["18"] = {"class_type": "CreateVideo", "inputs": {"images": ["17", 0], "fps": float(fps or 16.0)}}
    wf["19"] = {
        "class_type": "SaveVideo",
        "inputs": {
            "video": ["18", 0],
            "filename_prefix": "video/DS_Wan22",
            "format": "mp4",
        },
    }
    return wf


def build_sd_checkpoint_t2i_workflow(ckpt_name: str, prompt: str, neg_prompt: str = "",
                                     width: int = 1024, height: int = 576,
                                     steps: int = 20, seed: int = -1, cfg: float = 7.0) -> dict:
    """通用 Checkpoint 文生图工作流（供终端用户接入自己的 SD1.5 / SDXL 本地模型）。"""
    sd = int(seed) if (seed is not None and int(seed) >= 0) else random.randint(1, 2 ** 31 - 1)
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": str(ckpt_name)}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": str(prompt or ""), "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": str(neg_prompt or ""), "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": int(width), "height": int(height), "batch_size": 1}},
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0],
                "seed": sd, "steps": max(4, min(60, int(steps or 20))), "cfg": float(cfg or 7.0),
                "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
            },
        },
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "DS_Custom"}},
    }


def apply_custom_comfy_workflow(template_json: str, prompt: str, neg_prompt: str = "",
                                image_name: str = "", seed: int = -1) -> dict:
    """替换终端用户自定义 ComfyUI API Workflow JSON 中的占位符。"""
    sd = int(seed) if (seed is not None and int(seed) >= 0) else random.randint(1, 2 ** 31 - 1)
    obj = json.loads(template_json)

    def _walk(node):
        if isinstance(node, dict):
            return {k: _walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [_walk(v) for v in node]
        if isinstance(node, str):
            if node == "{{SEED}}":
                return sd
            return (node.replace("{{PROMPT}}", str(prompt or ""))
                        .replace("{{NEG_PROMPT}}", str(neg_prompt or ""))
                        .replace("{{IMAGE}}", str(image_name or ""))
                        .replace("{{SEED}}", str(sd)))
        return node

    return _walk(obj)


def comfyui_upload_image(base_url: str, image_path: Path) -> tuple:
    """上传首帧图片至 ComfyUI /upload/image，返回 (ok, remote_filename_or_err)。"""
    url = (base_url or "http://127.0.0.1:8188").strip().rstrip("/")
    try:
        raw = Path(image_path).read_bytes()
        name = _safe_filename(Path(image_path).stem, "frame") + (Path(image_path).suffix.lower() or ".png")
        r = requests.post(
            url + "/upload/image",
            files={"image": (name, raw, "image/png")},
            data={"overwrite": "true", "type": "input"},
            proxies={"http": None, "https": None},
            timeout=25,
        )
        if r.status_code == 200:
            j = r.json()
            fname = str(j.get("name") or name)
            sub = str(j.get("subfolder") or "").strip("/")
            return True, ("%s/%s" % (sub, fname)) if sub else fname
        return False, "上传首帧失败 HTTP %s" % r.status_code
    except Exception as ex:
        return False, "上传首帧异常：%s" % ex


def comfyui_queue_and_wait(base_url: str, workflow: dict, out_dir: Path,
                           progress_cb=None, cancel_check=None, timeout_sec: int = 900) -> tuple:
    """提交 ComfyUI API Prompt 并轮询等待成品，自动拉取成品图/视频落盘到 out_dir。"""
    url = (base_url or "http://127.0.0.1:8188").strip().rstrip("/")
    out_dir.mkdir(parents=True, exist_ok=True)
    client_id = "ds_panel_%d" % int(time.time() * 1000)
    try:
        r = requests.post(
            url + "/prompt",
            json={"prompt": workflow, "client_id": client_id},
            proxies={"http": None, "https": None},
            timeout=20,
        )
        if r.status_code != 200:
            return False, "ComfyUI 拒绝提交 (HTTP %s)：%s" % (r.status_code, (r.text or "")[:180]), []
        j = r.json()
        if j.get("error"):
            return False, "ComfyUI 工作流报错：%s" % str(j.get("error"))[:180], []
        pid = str(j.get("prompt_id") or "")
        if not pid:
            return False, "ComfyUI 未返回 prompt_id", []
    except Exception as ex:
        return False, "连接 ComfyUI 失败：%s" % ex, []

    t0 = time.time()
    step_pct = 12.0
    if progress_cb:
        progress_cb(step_pct, "已入队 ComfyUI（ID %s），推理中…" % pid[:8])

    while (time.time() - t0) < timeout_sec:
        if cancel_check and cancel_check():
            try:
                requests.post(url + "/interrupt", proxies={"http": None, "https": None}, timeout=3)
            except Exception:
                pass
            return False, "已取消生成任务", []

        time.sleep(1.2)
        try:
            hr = requests.get(url + "/history/" + urllib.parse.quote(pid),
                              proxies={"http": None, "https": None}, timeout=5)
            if hr.status_code == 200:
                hist = hr.json() or {}
                item = hist.get(pid)
                if item:
                    st = item.get("status") or {}
                    if st.get("status_str") == "error":
                        return False, "ComfyUI 执行出错，请检查显存或模型配置", []
                    outputs = item.get("outputs") or {}
                    saved = []
                    for _nid, node_out in outputs.items():
                        for key in ("images", "videos", "gifs"):
                            for fmeta in (node_out.get(key) or []):
                                fn = str(fmeta.get("filename") or "")
                                if not fn:
                                    continue
                                sub = str(fmeta.get("subfolder") or "")
                                ftype = str(fmeta.get("type") or "output")
                                qstr = urllib.parse.urlencode({"filename": fn, "subfolder": sub, "type": ftype})
                                vr = requests.get(url + "/view?" + qstr,
                                                  proxies={"http": None, "https": None}, timeout=60)
                                if vr.status_code == 200 and vr.content:
                                    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    ext = Path(fn).suffix.lower() or (".mp4" if key == "videos" else ".png")
                                    dst = out_dir / ("%s_%s%s" % (_safe_filename(Path(fn).stem, "gen"), stamp, ext))
                                    dst.write_bytes(vr.content)
                                    kind = "video" if ext in (".mp4", ".webm", ".mkv", ".mov") else "image"
                                    saved.append({"path": str(dst.resolve()), "name": dst.name, "kind": kind})
                    if saved:
                        if progress_cb:
                            progress_cb(100.0, "生成完成 ✔（共 %d 个成品）" % len(saved))
                        return True, "生成完成 ✔", saved
                    if st.get("completed"):
                        return False, "ComfyUI 已执行完但未产生可下载成品", []
        except Exception:
            pass

        elapsed = time.time() - t0
        step_pct = min(92.0, 15.0 + elapsed * 1.1)
        if progress_cb:
            progress_cb(step_pct, "ComfyUI GPU 推理中…（已耗时 %ds）" % int(elapsed))

    return False, "ComfyUI 生成超时（>%ds）" % timeout_sec, []


def run_custom_http_image_api(provider: str, api_url: str, api_key: str, model: str,
                              prompt: str, neg_prompt: str, width: int, height: int,
                              steps: int, out_dir: Path) -> tuple:
    """支持终端用户接入自己的本地 SD WebUI (A1111/Forge) 或 OpenAI 兼容生图接口。"""
    base = (api_url or "").strip().rstrip("/")
    if not base.startswith("http"):
        return False, "请先在「🔌 接入我的本地模型」填写有效接口地址", []
    out_dir.mkdir(parents=True, exist_ok=True)
    prov = (provider or "openai_image").strip().lower()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        if prov == "sdwebui":
            ep = base if base.endswith("/txt2img") else (base + "/sdapi/v1/txt2img")
            r = requests.post(
                ep,
                json={
                    "prompt": prompt,
                    "negative_prompt": neg_prompt,
                    "width": int(width or 1024),
                    "height": int(height or 576),
                    "steps": int(steps or 20),
                },
                proxies={"http": None, "https": None},
                timeout=300,
            )
            if r.status_code != 200:
                return False, "SD WebUI 返回 HTTP %s：%s" % (r.status_code, (r.text or "")[:140]), []
            imgs = (r.json() or {}).get("images") or []
            if not imgs:
                return False, "SD WebUI 未返回图片数据", []
            raw = base64.b64decode(imgs[0].split(",", 1)[-1])
            dst = out_dir / ("sdwebui_%s.png" % stamp)
            dst.write_bytes(raw)
            return True, "本地 SD WebUI 生图完成 ✔", [{"path": str(dst.resolve()), "name": dst.name, "kind": "image"}]

        # OpenAI-compatible /v1/images/generations
        ep = base if base.endswith("/generations") else (
            (base + "/images/generations") if base.endswith("/v1") else (base + "/v1/images/generations")
        )
        hdrs = {"Content-Type": "application/json"}
        if api_key:
            hdrs["Authorization"] = "Bearer " + api_key.strip()
        payload = {
            "model": model or "dall-e-3",
            "prompt": prompt,
            "size": "%dx%d" % (int(width or 1024), int(height or 1024)),
            "response_format": "b64_json",
        }
        r = requests.post(ep, headers=hdrs, json=payload, proxies={"http": None, "https": None}, timeout=180)
        if r.status_code != 200:
            return False, "生图接口返回 HTTP %s：%s" % (r.status_code, (r.text or "")[:160]), []
        data = (r.json() or {}).get("data") or []
        if not data:
            return False, "接口未返回图片 data", []
        item = data[0]
        if item.get("b64_json"):
            raw = base64.b64decode(item["b64_json"])
        elif item.get("url"):
            ir = requests.get(item["url"], timeout=60)
            ir.raise_for_status()
            raw = ir.content
        else:
            return False, "接口返回中不含图片内容", []
        dst = out_dir / ("custom_img_%s.png" % stamp)
        dst.write_bytes(raw)
        return True, "自定义模型生图完成 ✔", [{"path": str(dst.resolve()), "name": dst.name, "kind": "image"}]
    except Exception as ex:
        return False, "调用自定义生图模型失败：%s" % ex, []


# ==================================================================
# 4. 中转 Codex「赛博小怪兽」内置问答智能体客户端
# ==================================================================
def _norm_codex_base(base_url: str) -> str:
    b = (base_url or "").strip().rstrip("/")
    for suf in ("/v1/chat/completions", "/v1/responses", "/chat/completions", "/responses", "/v1"):
        if b.lower().endswith(suf):
            b = b[: -len(suf)]
            break
    return b.rstrip("/")


def codex_list_models(base_url: str, api_key: str, proxy: str = "", timeout: float = 10.0) -> tuple:
    """探测中转 Codex 站可用模型列表（代理/直连自动回退）。"""
    base = _norm_codex_base(base_url)
    if not base.startswith("http"):
        return False, "请先填写有效的中转域名（如 https://example.com）", []
    if not (api_key or "").strip():
        return False, "请先填写中转 API 密钥", []
    hdrs = {"Authorization": "Bearer " + api_key.strip()}
    proxy_plans = [{"http": None, "https": None}]
    if proxy:
        proxy_plans.append({"http": proxy, "https": proxy})
    last_err = ""
    for proxies in proxy_plans:
        try:
            r = requests.get(base + "/v1/models", headers=hdrs, proxies=proxies, timeout=timeout)
            if r.status_code == 200:
                j = r.json() or {}
                ids = [str(m.get("id")) for m in (j.get("data") or []) if isinstance(m, dict) and m.get("id")]
                return True, "中转站连通 ✔（发现 %d 个模型）" % len(ids), ids[:80]
            last_err = "HTTP %s：%s" % (r.status_code, (r.text or "")[:120])
        except Exception as ex:
            last_err = str(ex)
    return False, "连接中转站失败：%s" % last_err, []


def _extract_responses_text(j: dict) -> str:
    if isinstance(j.get("output_text"), str) and j["output_text"].strip():
        return j["output_text"].strip()
    parts = []
    for item in (j.get("output") or []):
        if not isinstance(item, dict):
            continue
        for c in (item.get("content") or []):
            if isinstance(c, dict) and c.get("text"):
                parts.append(str(c["text"]))
    return "\n".join(parts).strip()


def codex_chat_request(base_url: str, api_key: str, model: str, messages: list,
                       system_prompt: str = "", api_style: str = "auto",
                       proxy: str = "", timeout: float = 45.0) -> tuple:
    """调用中转 Codex / OpenAI 兼容问答接口（自动兼容 /v1/chat/completions 与 /v1/responses，且直连/代理自动回退）。"""
    base = _norm_codex_base(base_url)
    if not base.startswith("http"):
        return False, "尚未配置中转域名，请点右上角 ⚙ 填入中转域名与密钥。"
    if not (api_key or "").strip():
        return False, "尚未配置中转密钥，请点右上角 ⚙ 填入中转 API Key。"

    mdl = (model or "gpt-5.3-codex").strip()
    hdrs = {
        "Authorization": "Bearer " + api_key.strip(),
        "Content-Type": "application/json",
    }
    proxy_plans = [{"http": None, "https": None}]
    if proxy:
        proxy_plans.append({"http": proxy, "https": proxy})

    chat_msgs = []
    if system_prompt:
        chat_msgs.append({"role": "system", "content": system_prompt})
    for m in (messages or [])[-12:]:
        role = str(m.get("role") or "user")
        content = str(m.get("content") or "").strip()
        if content and role in ("user", "assistant", "system"):
            chat_msgs.append({"role": role, "content": content})

    order = ["responses", "chat"] if (api_style == "responses" or ("codex" in mdl.lower() and api_style == "auto")) else ["chat", "responses"]
    if api_style == "chat":
        order = ["chat", "responses"]

    last_err = ""
    for proxies in proxy_plans:
        for mode in order:
            try:
                if mode == "chat":
                    r = requests.post(
                        base + "/v1/chat/completions",
                        headers=hdrs,
                        json={"model": mdl, "messages": chat_msgs, "temperature": 0.6},
                        proxies=proxies,
                        timeout=timeout,
                    )
                    if r.status_code == 200:
                        j = r.json() or {}
                        ch = (j.get("choices") or [{}])[0]
                        msg = ch.get("message") or {}
                        txt = str(msg.get("content") or "").strip()
                        if txt:
                            return True, txt
                    last_err = "chat HTTP %s: %s" % (r.status_code, (r.text or "")[:160])
                else:
                    inp = [{"role": m["role"], "content": m["content"]} for m in chat_msgs if m["role"] != "system"]
                    body = {"model": mdl, "input": inp}
                    if system_prompt:
                        body["instructions"] = system_prompt
                    r = requests.post(
                        base + "/v1/responses",
                        headers=hdrs,
                        json=body,
                        proxies=proxies,
                        timeout=timeout,
                    )
                    if r.status_code == 200:
                        txt = _extract_responses_text(r.json() or {})
                        if txt:
                            return True, txt
                    last_err = "responses HTTP %s: %s" % (r.status_code, (r.text or "")[:160])
            except Exception as ex:
                last_err = str(ex)

    return False, "赛博小怪兽暂时连不上中转站（%s）。可在智能体页核对模型名或点「拉取可用模型」。" % last_err[:140]


# ==================================================================
# 5. 最近落盘成品扫描（视频 / 音频 / AI 图片 / 文件）
# ==================================================================
def scan_recent_downloads(dirs: list, limit: int = 10) -> list:
    """扫描多个下载与创作目录，返回最近落盘的媒体与成品文件列表。"""
    exts = {
        ".mp4", ".mkv", ".webm", ".mov",
        ".mp3", ".flac", ".wav", ".m4a", ".ogg",
        ".png", ".jpg", ".jpeg", ".webp",
        ".zip", ".7z", ".exe", ".iso", ".pdf",
    }
    audio_exts = {".mp3", ".flac", ".wav", ".m4a", ".ogg"}
    video_exts = {".mp4", ".mkv", ".webm", ".mov"}
    image_exts = {".png", ".jpg", ".jpeg", ".webp"}
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
                if ext in audio_exts:
                    kind = "audio"
                elif ext in video_exts:
                    kind = "video"
                elif ext in image_exts:
                    kind = "image"
                else:
                    kind = "file"
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
