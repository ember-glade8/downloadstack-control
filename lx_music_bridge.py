# -*- coding: utf-8 -*-
"""LXSRC: bridge to the user's installed LX Music userApi 音源.

Reads LX Music config/user_api.json in read-only mode, hosts those scripts
via lx_userapi_host.js (Node, 127.0.0.1), and resolves playable URLs for
DownloadStack Control's in-app music player.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
STATE_DIR = APP_DIR / "state"
LOG_DIR = APP_DIR / "logs"
HOST_JS = APP_DIR / "lx_userapi_host.js"
STATE_PATH = STATE_DIR / "lx_userapi_host.json"
SNAPSHOT_PATH = STATE_DIR / "lx_sources_snapshot.json"
DEFAULT_PORT = 18562
DEFAULT_API = "user_api_101_1770000001000"
NODE_CANDIDATES = [
    r"C:\Program Files\nodejs\node.exe",
    r"C:\Program Files (x86)\nodejs\node.exe",
]
USER_API_CANDIDATES = [
    Path(os.path.expandvars(r"%APPDATA%\lx-music-desktop\LxDatas\user_api.json")),
    Path(os.path.expanduser("~/AppData/Roaming/lx-music-desktop/LxDatas/user_api.json")),
    Path(os.environ.get("DOWNLOADSTACK_LX_USERAPI") or (APP_DIR / "lx_sources" / "user_api.snapshot.json")),
]
CONFIG_CANDIDATES = [
    Path(os.path.expandvars(r"%APPDATA%\lx-music-desktop\LxDatas\config_v2.json")),
    Path(os.path.expanduser("~/AppData/Roaming/lx-music-desktop/LxDatas/config_v2.json")),
    Path(os.environ.get("DOWNLOADSTACK_LX_CONFIG") or (APP_DIR / "lx_sources" / "config_v2.snapshot.json")),
]

_lock = threading.Lock()
_cached_list = None
_cached_at = 0.0

SOURCE_NAME_MAP = {
    "qq": "tx", "qq音乐": "tx", "tx": "tx", "qmusic": "tx",
    "netease": "wy", "网易云": "wy", "网易": "wy", "wy": "wy", "ne": "wy",
    "kugou": "kg", "酷狗": "kg", "kg": "kg",
    "kuwo": "kw", "酷我": "kw", "kw": "kw",
    "migu": "mg", "咪咕": "mg", "mg": "mg",
    "bilibili": "bili", "b站": "bili", "bili": "bili", "b站音乐区": "bili",
    "youtube": "ytb", "yt": "ytb", "ytb": "ytb",
    "汽水": "qs", "qs": "qs", "qsvip": "qsvip",
    "虾米": "xm", "xm": "xm",
}

PLAYABLE_PLATFORMS = {"tx", "wy", "kg", "kw", "mg", "qs", "qsvip", "bili", "ytb"}

QUALITY_HEADERS = {
    "tx": {"Referer": "https://y.qq.com/", "Origin": "https://y.qq.com"},
    "wy": {"Referer": "https://music.163.com/", "Origin": "https://music.163.com"},
    "kg": {"Referer": "https://www.kugou.com/", "Origin": "https://www.kugou.com"},
    "kw": {"Referer": "https://www.kuwo.cn/", "Origin": "https://www.kuwo.cn"},
    "mg": {"Referer": "https://music.migu.cn/", "Origin": "https://music.migu.cn"},
}

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def _node_exe() -> str:
    for p in NODE_CANDIDATES:
        if p and os.path.isfile(p):
            return p
    return "node"


def find_user_api_json() -> Path | None:
    for p in USER_API_CANDIDATES:
        try:
            if p and p.is_file():
                return p
        except Exception:
            continue
    return None


def find_lx_config() -> Path | None:
    for p in CONFIG_CANDIDATES:
        try:
            if p and p.is_file():
                return p
        except Exception:
            continue
    return None


def read_default_api() -> str:
    cfg = find_lx_config()
    if not cfg:
        return DEFAULT_API
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
        src = ((data.get("setting") or {}).get("common.apiSource") or "").strip()
        return src or DEFAULT_API
    except Exception:
        return DEFAULT_API


def map_platform(source: str, song_id: str = "", lx_source: str = "") -> str:
    if lx_source:
        key = str(lx_source).strip().lower()
        if key in SOURCE_NAME_MAP.values() or key in SOURCE_NAME_MAP:
            return SOURCE_NAME_MAP.get(key, key)
    sid = str(song_id or "")
    for prefix, plat in (("qq_", "tx"), ("qq2_", "tx"), ("ne_", "wy"), ("kg_", "kg"),
                         ("kw_", "kw"), ("mg_", "mg"), ("bili_", "bili"), ("bg_", "bili"),
                         ("yt_", "ytb")):
        if sid.startswith(prefix):
            return plat
    key = str(source or "").strip().lower()
    return SOURCE_NAME_MAP.get(key, "")


def attach_lx_fields(item: dict, platform: str, **ids) -> dict:
    """Attach musicInfo fields expected by LX userApi scripts. In-place."""
    if not item:
        return item
    plat = map_platform(platform, item.get("id") or "", item.get("lx_source") or platform)
    if not plat:
        return item
    info = {
        "name": item.get("title") or "",
        "singer": item.get("artist") or "",
        "albumName": item.get("album") or "",
        "interval": item.get("duration") or "",
        "source": plat,
        "type": "music",
    }
    for k, v in ids.items():
        if v is None or v == "":
            continue
        info[k] = v
    if info.get("songmid") and not info.get("id"):
        info["id"] = info["songmid"]
    if info.get("id") and not info.get("songmid"):
        info["songmid"] = info["id"]
    item["lx_source"] = plat
    item["lx_info"] = info
    return item


def metadata_from_user_api() -> list:
    path = find_user_api_json()
    if not path:
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        apis = data.get("userApis") or []
    except Exception:
        return []
    default = read_default_api()
    out = []
    for api in apis:
        out.append({
            "id": api.get("id") or "",
            "name": api.get("name") or "",
            "version": api.get("version") or "",
            "author": api.get("author") or "",
            "description": api.get("description") or "",
            "ready": None,
            "sources": {},
            "default": (api.get("id") or "") == default,
        })
    return out


def _load_state() -> dict:
    try:
        if STATE_PATH.is_file():
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_state(data: dict) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _port_open(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=0.4):
            return True
    except Exception:
        return False


def _http_json(url: str, payload: dict | None = None, timeout: float = 20.0) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as ex:
        raw = ""
        try:
            raw = ex.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {"ok": False, "error": "http %s" % ex.code}
        except Exception:
            return {"ok": False, "error": "http %s" % ex.code}


def health(port: int | None = None) -> dict:
    st = _load_state()
    port = int(port or st.get("port") or DEFAULT_PORT)
    if not _port_open(port):
        return {}
    try:
        return _http_json("http://127.0.0.1:%d/health" % port, timeout=2.0) or {}
    except Exception:
        return {}


def ensure_host(timeout: float = 25.0) -> dict:
    """Start the Node userApi host if needed. Cheap no-op when already healthy."""
    h = health()
    if h.get("ok") and h.get("service") == "lx-userapi-host":
        return h
    with _lock:
        h = health()
        if h.get("ok") and h.get("service") == "lx-userapi-host":
            return h
        if not HOST_JS.is_file():
            return {"ok": False, "error": "lx_userapi_host.js missing"}
        node = _node_exe()
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOG_DIR / "lx_userapi_host.log"
        user_api = find_user_api_json()
        port = DEFAULT_PORT
        # If the default port is occupied by something else, step forward a little.
        if _port_open(port) and not (h.get("service") == "lx-userapi-host"):
            for cand in range(DEFAULT_PORT + 1, DEFAULT_PORT + 8):
                if not _port_open(cand):
                    port = cand
                    break
        env = os.environ.copy()
        env["LX_USERAPI_PORT"] = str(port)
        env["LX_USERAPI_BIND"] = "127.0.0.1"
        env["LX_DEFAULT_API"] = read_default_api()
        if user_api:
            env["LX_USER_API_JSON"] = str(user_api)
        flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
        logf = open(log_path, "a", encoding="utf-8", errors="replace")
        try:
            proc = subprocess.Popen(
                [node, str(HOST_JS), "--port", str(port)],
                cwd=str(APP_DIR),
                env=env,
                stdout=logf,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=flags,
            )
        except Exception as ex:
            try:
                logf.close()
            except Exception:
                pass
            return {"ok": False, "error": "failed to start node host: %s" % ex}
        _save_state({
            "pid": proc.pid,
            "port": port,
            "started": time.time(),
            "user_api": str(user_api or ""),
        })
        deadline = time.time() + timeout
        last = {}
        while time.time() < deadline:
            last = health(port)
            if last.get("ok") and last.get("service") == "lx-userapi-host":
                try:
                    SNAPSHOT_PATH.write_text(
                        json.dumps({"ts": time.time(), "apis": last.get("apis") or []}, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                except Exception:
                    pass
                return last
            time.sleep(0.35)
        return last or {"ok": False, "error": "lx userApi host did not become ready", "pid": proc.pid, "port": port}


def list_sources(start_host: bool = False) -> dict:
    """Cheap listing for UI/state. Does not start Node on the polling path."""
    global _cached_list, _cached_at
    h = health()
    if h.get("ok"):
        info = {
            "ok": True,
            "ready": True,
            "port": h.get("port") or _load_state().get("port") or DEFAULT_PORT,
            "defaultApi": read_default_api(),
            "apis": h.get("apis") or [],
        }
        _cached_list, _cached_at = info, time.time()
        return info
    if start_host:
        h = ensure_host()
        if h.get("ok"):
            return list_sources(start_host=False)
    if _cached_list and (time.time() - _cached_at) < 30:
        return dict(_cached_list, ready=False)
    apis = []
    try:
        if SNAPSHOT_PATH.is_file():
            snap = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
            apis = snap.get("apis") or []
    except Exception:
        apis = []
    if not apis:
        apis = metadata_from_user_api()
    info = {
        "ok": bool(apis),
        "ready": False,
        "port": _load_state().get("port") or DEFAULT_PORT,
        "defaultApi": read_default_api(),
        "apis": apis,
    }
    _cached_list, _cached_at = info, time.time()
    return info


def build_music_info(title: str = "", artist: str = "", album: str = "",
                     source: str = "", song: dict | None = None, **extra) -> tuple[str, dict]:
    song = dict(song or {})
    plat = map_platform(
        extra.get("lx_source") or song.get("lx_source") or source or song.get("source") or "",
        extra.get("id") or song.get("id") or "",
        extra.get("lx_source") or song.get("lx_source") or "",
    )
    info = dict(song.get("lx_info") or extra.get("lx_info") or {})
    info.setdefault("name", title or song.get("title") or "")
    info.setdefault("singer", artist or song.get("artist") or "")
    info.setdefault("albumName", album or song.get("album") or "")
    info.setdefault("interval", song.get("duration") or "")
    info["type"] = "music"
    if plat:
        info["source"] = plat

    def _put(key, *vals):
        for v in vals:
            if v not in (None, ""):
                info[key] = v
                return

    sid = extra.get("sid") or song.get("sid") or ""
    _put("songmid", extra.get("songmid"), song.get("songmid"), info.get("songmid"), sid,
         (song.get("id") or "")[3:] if str(song.get("id") or "").startswith(("ne_", "kw_", "qq_")) else "")
    _put("id", extra.get("nid"), sid, info.get("id"), info.get("songmid"))
    _put("hash", extra.get("kg_hash") or extra.get("hash"), song.get("kg_hash"), song.get("hash"), info.get("hash"))
    _put("albumId", extra.get("albumId") or extra.get("album_id"), song.get("albumId"), song.get("album_id"), info.get("albumId"))
    _put("album_id", info.get("albumId"), song.get("album_id"))
    _put("albumMid", extra.get("albumMid") or extra.get("album_mid"), song.get("albumMid"), info.get("albumMid"))
    _put("strMediaMid", extra.get("strMediaMid") or extra.get("media_mid"), song.get("strMediaMid"), song.get("media_mid"), info.get("strMediaMid"))
    _put("media_mid", info.get("strMediaMid"))
    _put("copyrightId", extra.get("copyrightId") or extra.get("migu_id"), song.get("migu_id"), song.get("copyrightId"), info.get("copyrightId"))
    _put("contentId", extra.get("contentId"), song.get("contentId"), info.get("contentId"), info.get("copyrightId"))
    _put("bvid", extra.get("bvid"), song.get("bvid"))
    if plat:
        info["source"] = plat
    return plat, info


def stream_headers(platform: str) -> dict:
    hdrs = {"User-Agent": _UA, "Accept": "*/*"}
    hdrs.update(QUALITY_HEADERS.get(platform) or {})
    return hdrs


def resolve_play_url(title: str = "", artist: str = "", source: str = "",
                     quality: str = "flac", api_id: str = "auto",
                     song: dict | None = None, **extra) -> dict:
    """Resolve a playable HTTP audio URL via the user's LX 音源. Starts host if needed."""
    plat, info = build_music_info(title, artist, extra.get("album") or "", source, song, **extra)
    if not plat:
        return {"ok": False, "msg": "当前条目没有可对接的 LX 平台 ID（仅网易/QQ/酷狗/酷我/咪咕等可走 LX 音源）"}
    if plat not in PLAYABLE_PLATFORMS:
        return {"ok": False, "msg": "平台 %s 暂不走 LX 音源" % plat}
    if plat in ("tx", "wy", "kg", "kw", "mg"):
        if plat == "kg" and not info.get("hash"):
            return {"ok": False, "msg": "酷狗条目缺少 hash，无法向 LX 音源取链"}
        if plat != "kg" and not (info.get("songmid") or info.get("id") or info.get("copyrightId")):
            return {"ok": False, "msg": "条目缺少平台歌曲 ID，无法向 LX 音源取链"}
    host = ensure_host()
    if not host.get("ok"):
        return {"ok": False, "msg": host.get("error") or "LX 音源宿主未能启动"}
    port = int(host.get("port") or _load_state().get("port") or DEFAULT_PORT)
    payload = {
        "apiId": api_id or "auto",
        "source": plat,
        "quality": quality or "flac",
        "musicInfo": info,
        "probe": True,
    }
    try:
        out = _http_json("http://127.0.0.1:%d/musicUrl" % port, payload, timeout=36.0)
    except Exception as ex:
        return {"ok": False, "msg": "音源宿主请求失败：%s" % ex}
    if not out.get("ok") or not out.get("url"):
        tried = out.get("tried") or []
        detail = "；".join(
            "%s %s" % (t.get("apiName") or t.get("apiId") or "", t.get("reason") or "失败")
            for t in tried[:4]
        )
        return {
            "ok": False,
            "msg": out.get("error") or ("LX 音源未能解析播放地址" + ("（%s）" % detail if detail else "")),
            "tried": tried,
            "lx_source": plat,
        }
    api_name = out.get("apiName") or out.get("apiId") or "LX 音源"
    q = out.get("quality") or quality
    return {
        "ok": True,
        "is_local": False,
        "stream_url": out["url"],
        "headers": stream_headers(plat),
        "mime": out.get("contentType") or "audio/mpeg",
        "use_proxy": False,
        "source": "%s · %s · %s" % (api_name, _plat_label(plat), q),
        "lx_api": out.get("apiId") or "",
        "lx_api_name": api_name,
        "lx_quality": q,
        "lx_source": plat,
        "msg": "已用 LX 音源「%s」解析 %s / %s ✔" % (api_name, _plat_label(plat), q),
        "tried": out.get("tried") or [],
    }


def _plat_label(plat: str) -> str:
    return {
        "tx": "QQ音乐", "wy": "网易云", "kg": "酷狗", "kw": "酷我", "mg": "咪咕",
        "qs": "汽水音乐", "qsvip": "汽水VIP", "bili": "B站", "ytb": "YouTube", "xm": "虾米",
    }.get(plat, plat)


def ui_source_payload() -> dict:
    info = list_sources(start_host=False)
    apis = []
    for a in info.get("apis") or []:
        srcs = a.get("sources") or {}
        platforms = []
        for k, meta in srcs.items():
            platforms.append({
                "id": k,
                "name": (meta or {}).get("name") or _plat_label(k),
                "qualitys": (meta or {}).get("qualitys") or [],
                "actions": (meta or {}).get("actions") or [],
            })
        apis.append({
            "id": a.get("id") or "",
            "name": a.get("name") or "",
            "version": a.get("version") or "",
            "ready": a.get("ready"),
            "default": bool(a.get("default")),
            "error": a.get("error") or "",
            "platforms": platforms,
        })
    return {
        "ready": bool(info.get("ready")),
        "defaultApi": info.get("defaultApi") or DEFAULT_API,
        "count": len(apis),
        "apis": apis,
    }


def warmup_async() -> None:
    def _run():
        try:
            ensure_host()
        except Exception:
            pass
    t = threading.Thread(target=_run, daemon=True, name="lx-userapi-warmup")
    t.start()
