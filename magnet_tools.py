# -*- coding: utf-8 -*-
"""磁力链接（Magnet）/ DHT / BT Tracker 修复与辅助模块。

职责：
1. 校验、解析、补全磁力链接（支持 magnet:?xt=... 与纯 40 位 hex / 32 位 Base32 InfoHash）。
2. 拉取并缓存公共 BT Tracker（多镜像 + 代理回退 + 内置保底列表）。
3. 一键修复 aria2.conf 的 BT / DHT / 磁力元数据 / Tracker 配置（保留原有端口与密钥）。
4. 热更新正在运行的 aria2 与 qBittorrent 的 Tracker / DHT 配置。
5. 诊断磁力 / DHT 现状（配置文件、dht.dat、RPC/WebUI 状态、DHT 引导节点连通性）。
"""

import hashlib
import os
import re
import socket
import struct
import urllib.parse
import urllib.request
from pathlib import Path

# 公共 Tracker 源（按国内直连友好度排序，自动回退）
TRACKER_SOURCES = [
    "https://cf.trackerslist.com/best.txt",
    "https://cdn.jsdelivr.net/gh/XIU2/TrackersListCollection@master/best.txt",
    "https://fastly.jsdelivr.net/gh/ngosang/trackerslist@master/trackers_best.txt",
    "https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_best.txt",
]

# 内置高可用公共 Tracker 保底（完全离线或源站不可达时也能立即生效）
BUILTIN_TRACKERS = [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.stealth.si:80/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://tracker.bittor.pw:1337/announce",
    "udp://public.popcorn-tracker.org:6969/announce",
    "udp://tracker.dler.org:6969/announce",
    "udp://exodus.desync.com:6969/announce",
    "udp://open.demonii.com:1337/announce",
    "udp://tracker.openbittorrent.com:6969/announce",
    "udp://tracker.moeking.me:6969/announce",
    "udp://explodie.org:6969/announce",
    "udp://tracker1.bt.moack.co.kr:80/announce",
    "udp://tracker.theoks.net:6969/announce",
    "udp://tracker-udp.gbitt.info:80/announce",
    "udp://retracker01-msk-virt.corbina.net:80/announce",
    "http://tracker.opentrackr.org:1337/announce",
    "http://tracker.bt4g.com:2095/announce",
    "http://tracker.gbitt.info:80/announce",
    "https://tracker.tamersunion.org:443/announce",
    "https://tracker.gbitt.info:443/announce",
    "https://tr.burnabyhighstar.com:443/announce",
    "wss://tracker.openwebtorrent.com",
    "wss://tracker.btorrent.xyz",
]

# aria2 磁力 / DHT 正常工作所需的推荐配置项
ARIA2_BT_DEFAULTS = {
    "enable-dht": "true",
    "enable-dht6": "true",
    "dht-entry-point": "dht.transmissionbt.com:6881",
    "dht-entry-point6": "dht.transmissionbt.com:6881",
    "listen-port": "6881-6999",
    "dht-listen-port": "6881-6999",
    "enable-peer-exchange": "true",
    "bt-enable-lpd": "true",
    "follow-torrent": "true",
    "bt-save-metadata": "true",
    "bt-load-saved-metadata": "true",
    "bt-max-peers": "128",
    "bt-request-peer-speed-limit": "10M",
    "bt-detach-seed-only": "true",
    "bt-remove-unselected-file": "true",
    "peer-id-prefix": "-qB4520-",
    "peer-agent": "qBittorrent/4.5.2",
}

_HEX40_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_B32_RE = re.compile(r"^[A-Z2-7]{32}$", re.IGNORECASE)
_BTIH_RE = re.compile(r"urn:btih:([0-9a-fA-F]{40}|[A-Za-z2-7]{32})", re.IGNORECASE)
_BTMH_RE = re.compile(r"urn:btmh:1220([0-9a-fA-F]{64})", re.IGNORECASE)
_TRACKER_SCHEME_RE = re.compile(r"^(udp|http|https|ws|wss)://[^\s,]+$", re.IGNORECASE)


def parse_tracker_text(text: str) -> list:
    """从纯文本中提取合法、去重后的 Tracker URL 列表。"""
    seen = set()
    out = []
    for raw in (text or "").replace(",", "\n").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not _TRACKER_SCHEME_RE.match(line):
            continue
        if line not in seen:
            seen.add(line)
            out.append(line)
    return out


def parse_magnet(raw: str) -> dict:
    """解析并校验磁力链接或纯 InfoHash。

    返回 dict:
      valid: bool
      uri: 规范化后的 magnet:?xt=...
      infohash: 提取到的 btih / btmh
      name: 显示名称 (dn)
      trackers: 原链接自带的 tr 列表
      error: 失败原因（valid=False 时非空）
    """
    s = (raw or "").strip()
    if not s:
        return {"valid": False, "uri": "", "infohash": "", "name": "", "trackers": [], "error": "输入为空"}

    # 支持直接粘贴 40 位 hex 或 32 位 Base32 InfoHash
    if _HEX40_RE.match(s):
        ih = s.lower()
        return {"valid": True, "uri": "magnet:?xt=urn:btih:" + ih, "infohash": ih,
                "name": "", "trackers": [], "error": ""}
    if _B32_RE.match(s):
        ih = s.upper()
        return {"valid": True, "uri": "magnet:?xt=urn:btih:" + ih, "infohash": ih,
                "name": "", "trackers": [], "error": ""}

    # 从分享文本中提取 magnet:? 片段
    idx = s.lower().find("magnet:?")
    if idx >= 0:
        s = s[idx:].split()[0].strip()

    if not s.lower().startswith("magnet:?"):
        return {"valid": False, "uri": "", "infohash": "", "name": "", "trackers": [],
                "error": "不是有效的磁力链接（需以 magnet:? 开头或为 40 位 InfoHash）"}

    qs = urllib.parse.parse_qs(s[8:], keep_blank_values=False)
    xts = qs.get("xt") or []
    ih = ""
    for xt in xts:
        m = _BTIH_RE.search(xt)
        if m:
            ih = m.group(1)
            break
        m2 = _BTMH_RE.search(xt)
        if m2:
            ih = m2.group(1)
            break
    if not ih:
        return {"valid": False, "uri": "", "infohash": "", "name": "", "trackers": [],
                "error": "磁力链接缺少有效的 xt=urn:btih / urn:btmh"}

    name = (qs.get("dn") or [""])[0]
    trackers = []
    seen = set()
    for tr in qs.get("tr") or []:
        t = tr.strip()
        if t and _TRACKER_SCHEME_RE.match(t) and t not in seen:
            seen.add(t)
            trackers.append(t)

    return {"valid": True, "uri": s, "infohash": ih, "name": name, "trackers": trackers, "error": ""}


def enhance_magnet(raw: str, extra_trackers=None, max_trackers: int = 30) -> str:
    """校验磁力链接并自动补全去重后的公共 Tracker，提升冷启动成功率。"""
    info = parse_magnet(raw)
    if not info["valid"]:
        raise ValueError(info["error"])
    uri = info["uri"]
    existing = set(info["trackers"])
    pool = list(extra_trackers) if extra_trackers else list(BUILTIN_TRACKERS)
    added = []
    for tr in pool:
        t = tr.strip()
        if not t or t in existing or not _TRACKER_SCHEME_RE.match(t):
            continue
        existing.add(t)
        added.append(t)
        if len(existing) >= max_trackers:
            break
    if not added:
        return uri
    sep = "&" if "?" in uri and not uri.endswith("?") else ""
    tail = "&".join("tr=" + urllib.parse.quote(t, safe="") for t in added)
    return uri + sep + tail


def fetch_trackers(cache_file=None, proxy: str = "", timeout: float = 6.0) -> tuple:
    """从公共源拉取最新 Tracker 列表，失败自动回退到缓存或内置列表。

    返回 (trackers: list[str], source_label: str)
    """
    headers = {"User-Agent": "DownloadStack-Control/1.0"}

    def _get(url: str, use_proxy: bool):
        handlers = []
        if use_proxy and proxy:
            handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        else:
            handlers.append(urllib.request.ProxyHandler({}))
        opener = urllib.request.build_opener(*handlers)
        req = urllib.request.Request(url, headers=headers)
        with opener.open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")

    # 先直连拉取，若全失败且存在系统代理则走代理重试
    attempts = [(False, "直连")]
    if proxy:
        attempts.append((True, "代理"))

    for use_proxy, mode in attempts:
        for url in TRACKER_SOURCES:
            try:
                txt = _get(url, use_proxy)
                tr = parse_tracker_text(txt)
                if len(tr) >= 5:
                    if cache_file:
                        try:
                            p = Path(cache_file)
                            p.parent.mkdir(parents=True, exist_ok=True)
                            p.write_text("\n".join(tr) + "\n", encoding="utf-8")
                        except Exception:
                            pass
                    host = urllib.parse.urlparse(url).netloc
                    return tr, "%s（%s）" % (host, mode)
            except Exception:
                continue

    # 回退：本地缓存
    if cache_file:
        try:
            p = Path(cache_file)
            if p.is_file():
                cached = parse_tracker_text(p.read_text(encoding="utf-8", errors="ignore"))
                if len(cached) >= 5:
                    return cached, "本地缓存"
        except Exception:
            pass

    # 最终保底：内置列表
    return list(BUILTIN_TRACKERS), "内置保底"


def load_cached_trackers(cache_file=None) -> list:
    """快速读取本地缓存的 Tracker 列表，无缓存则返回内置列表（不发网络请求）。"""
    if cache_file:
        try:
            p = Path(cache_file)
            if p.is_file():
                tr = parse_tracker_text(p.read_text(encoding="utf-8", errors="ignore"))
                if tr:
                    return tr
        except Exception:
            pass
    return list(BUILTIN_TRACKERS)


def read_aria2_conf_map(conf_path) -> dict:
    """把 aria2.conf 读成 key -> value 字典（忽略注释与空行）。"""
    out = {}
    p = Path(conf_path)
    if not p.is_file():
        return out
    for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def repair_aria2_conf(conf_path, trackers=None, dht_dir=None, dht_entry: str = "") -> dict:
    """无损修复 aria2.conf 的 BT / DHT / Tracker 配置，保留用户原有端口、密钥和路径。"""
    p = Path(conf_path)
    if not p.parent.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines() if p.is_file() else []

    tr_list = parse_tracker_text("\n".join(trackers)) if trackers else list(BUILTIN_TRACKERS)
    desired = dict(ARIA2_BT_DEFAULTS)
    if dht_entry:
        desired["dht-entry-point"] = dht_entry
    desired["bt-tracker"] = ",".join(tr_list)

    base_dir = Path(dht_dir) if dht_dir else p.parent
    existing_map = read_aria2_conf_map(p) if p.is_file() else {}
    if "dht-file-path" not in existing_map:
        desired["dht-file-path"] = str(base_dir / "dht.dat")
    if "dht-file-path6" not in existing_map:
        desired["dht-file-path6"] = str(base_dir / "dht6.dat")

    updated = []
    seen = set()
    new_lines = []
    for raw in lines:
        s = raw.strip()
        if s and not s.startswith("#") and "=" in s:
            k, old_v = s.split("=", 1)
            k = k.strip()
            old_v = old_v.strip()
            if k in desired:
                if k in seen:
                    continue
                seen.add(k)
                new_v = desired[k]
                if old_v != new_v:
                    updated.append(k)
                new_lines.append("%s=%s" % (k, new_v))
                continue
        new_lines.append(raw)

    missing_keys = [k for k in desired if k not in seen]
    if missing_keys:
        if new_lines and new_lines[-1].strip() != "":
            new_lines.append("")
        new_lines.append("# --- Magnet / DHT / BT Trackers (auto-configured) ---")
        for k in missing_keys:
            new_lines.append("%s=%s" % (k, desired[k]))
            updated.append(k)

    p.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return {
        "path": str(p),
        "updated_keys": updated,
        "tracker_count": len(tr_list),
        "changed": bool(updated),
    }


def discover_dht_entry_point(timeout: float = 2.0) -> str:
    """通过 KRPC find_node 发现一个在 get_peers 中携带合法 token 的真实 DHT 节点。

    背景：aria2 1.37.0 的 DHTMessageFactoryImpl 对缺少 token 字段的 get_peers 回复会抛
    `errorCode=1 Malformed DHT message. Missing token` 并丢弃整个 nodes 列表，导致冷启动时
    dht.transmissionbt.com 返回的节点无法入表、DHT 长期 0 节点。
    先由 Python 发送 find_node 拿到真实客户端节点并验证含 `5:token`，再写入 dht-entry-point 即可彻底规避。
    """
    my_id = os.urandom(20)
    target = os.urandom(20)
    q_fn = b"d1:ad2:id20:" + my_id + b"6:target20:" + target + b"e1:q9:find_node1:t2:fn1:y1:qe"
    q_gp = b"d1:ad2:id20:" + my_id + b"9:info_hash20:" + target + b"e1:q9:get_peers1:t2:gp1:y1:qe"

    cands = []
    seen = set()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        for host, port in (("dht.transmissionbt.com", 6881),
                           ("router.bittorrent.com", 6881),
                           ("router.utorrent.com", 6881)):
            try:
                ip = socket.gethostbyname(host)
                sock.sendto(q_fn, (ip, port))
                data, _ = sock.recvfrom(2048)
                nidx = data.find(b"5:nodes")
                if nidx > 0:
                    colon = data.find(b":", nidx + 7)
                    if colon > 0:
                        nlen = int(data[nidx + 7:colon])
                        raw = data[colon + 1:colon + 1 + nlen]
                        for i in range(0, len(raw) - 25, 26):
                            nip = socket.inet_ntoa(raw[i + 20:i + 24])
                            nport = struct.unpack("!H", raw[i + 24:i + 26])[0]
                            if 1024 <= nport <= 65535 and (nip, nport) not in seen:
                                seen.add((nip, nport))
                                cands.append((nip, nport))
                if cands:
                    break
            except Exception:
                continue

        sock.settimeout(1.2)
        for nip, nport in cands[:8]:
            try:
                sock.sendto(q_gp, (nip, nport))
                r, _ = sock.recvfrom(2048)
                if b"5:token" in r:
                    return "%s:%d" % (nip, nport)
            except Exception:
                continue
    finally:
        sock.close()
    return ""


def _bencode_skip(buf: bytes, idx: int) -> int:
    """推进一个 bencode 元素并返回结束下标（用于校验 .torrent 的 info 字典 SHA1）。"""
    c = buf[idx:idx + 1]
    if c == b"i":
        return buf.index(b"e", idx + 1) + 1
    if c in (b"l", b"d"):
        idx += 1
        while buf[idx:idx + 1] != b"e":
            idx = _bencode_skip(buf, idx)
        return idx + 1
    colon = buf.index(b":", idx)
    ln = int(buf[idx:colon])
    return colon + 1 + ln


def verify_torrent_infohash(torrent_bytes: bytes, expected_hex: str) -> bool:
    """校验下载到的 .torrent 二进制与磁力链接的 SHA1 InfoHash 严格一致，防伪造与污染。"""
    if not torrent_bytes or torrent_bytes[:1] != b"d" or not _HEX40_RE.match(expected_hex or ""):
        return False
    try:
        idx = torrent_bytes.find(b"4:info")
        if idx < 0:
            return False
        start = idx + 6
        end = _bencode_skip(torrent_bytes, start)
        got = hashlib.sha1(torrent_bytes[start:end]).hexdigest().lower()
        return got == expected_hex.lower()
    except Exception:
        return False


def resolve_magnet_torrent(infohash: str, proxy: str = "", timeout: float = 5.0) -> tuple:
    """尝试从公共种子缓存秒级预取 .torrent 元数据并做 SHA1 完整性校验。

    成功返回 (torrent_bytes, source_host)，失败返回 (b"", "")。
    这样即使在 UDP/DHT 受限或冷启动环境下，也能跳过 [METADATA] 卡顿阶段直接开始下载。
    """
    ih = (infohash or "").strip()
    if _B32_RE.match(ih):
        import base64
        try:
            ih = base64.b32decode(ih.upper()).hex()
        except Exception:
            return b"", ""
    if not _HEX40_RE.match(ih):
        return b"", ""

    ih_up = ih.upper()
    urls = [
        "https://itorrents.org/torrent/%s.torrent" % ih_up,
        "https://btcache.me/torrent/%s" % ih_up,
    ]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DownloadStack/1.0"}
    attempts = [False] + ([True] if proxy else [])

    for use_proxy in attempts:
        handlers = [urllib.request.ProxyHandler({"http": proxy, "https": proxy} if use_proxy else {})]
        opener = urllib.request.build_opener(*handlers)
        for u in urls:
            try:
                req = urllib.request.Request(u, headers=headers)
                with opener.open(req, timeout=timeout) as resp:
                    data = resp.read(8 * 1024 * 1024)
                if verify_torrent_infohash(data, ih):
                    return data, urllib.parse.urlparse(u).netloc
            except Exception:
                continue
    return b"", ""


def probe_dht_bootstrap(host: str = "dht.transmissionbt.com", port: int = 6881, timeout: float = 2.0) -> tuple:
    """探测 DHT 引导节点 DNS 解析与 UDP 套接字发送是否正常。"""
    try:
        infos = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_DGRAM)
        if not infos:
            return False, "DNS 无 IPv4 记录"
        ip = infos[0][4][0]
        # 发一个标准 KRPC ping（bencode: d1:ad2:id20:01234567890123456789e1:q4:ping1:t2:aa1:y1:qe）
        ping = b"d1:ad2:id20:01234567890123456789e1:q4:ping1:t2:aa1:y1:qe"
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        try:
            sock.sendto(ping, (ip, port))
            data, _ = sock.recvfrom(512)
            if data and b"y1:r" in data:
                return True, "%s:%d UDP 响应正常" % (ip, port)
            return True, "%s:%d 已收到 UDP 回包" % (ip, port)
        except socket.timeout:
            return False, "%s:%d UDP 无响应（可能被防火墙/NAT/代理拦截）" % (ip, port)
        finally:
            sock.close()
    except Exception as ex:
        return False, "探测失败: %s" % ex


def diagnose_aria2_conf(conf_path) -> dict:
    """检查 aria2.conf 的磁力/DHT 配置健康度。"""
    p = Path(conf_path)
    if not p.is_file():
        return {"exists": False, "missing": list(ARIA2_BT_DEFAULTS.keys()) + ["bt-tracker"],
                "tracker_count": 0, "dht_dat_size": -1, "ok": False}
    kv = read_aria2_conf_map(p)
    missing = [k for k in ("enable-dht", "dht-entry-point", "enable-peer-exchange",
                           "follow-torrent", "bt-save-metadata", "bt-tracker")
               if not kv.get(k)]
    tr_count = len(parse_tracker_text(kv.get("bt-tracker", "")))
    if tr_count == 0 and "bt-tracker" not in missing:
        missing.append("bt-tracker")
    dht_path = Path(kv.get("dht-file-path") or (p.parent / "dht.dat"))
    dht_size = dht_path.stat().st_size if dht_path.is_file() else 0
    return {
        "exists": True,
        "missing": missing,
        "tracker_count": tr_count,
        "dht_dat_size": dht_size,
        "ok": (not missing and tr_count > 0),
    }
