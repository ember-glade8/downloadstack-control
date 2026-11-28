# -*- coding: utf-8 -*-
"""reader_hub —— DownloadStack 内置「书城」：漫画 + 电子书聚合搜索与阅读后端。

设计原则（与项目红线一致）：
  * 只接入**公开、合法、提供官方 API** 的内容源，不做盗版站爬虫：
      - MangaDex           公开漫画 API（官方发布 / 授权汉化组上传，遵守其 DMCA 下架）
      - 维基文库 zh         中文公有领域古籍 / 名著（CC / PD）
      - Project Gutenberg  7 万+ 公有领域世界名著（经 Gutendex 检索 + EPUB 下载）
      - Internet Archive   公有领域扫描书 / 黄金年代漫画（仅非借阅类，IIIF 翻页）
      - Standard Ebooks    精校公有领域英文名著（官方网页目录 / Atom 新书；EPUB 直链）
      - Open Library       仅收录带 Internet Archive 可公开阅读标识的条目，打开仍走 IA
      - 本地书库           你自己的 EPUB / TXT / PDF / CBZ / ZIP / 图片文件夹
  * 所有远程图片走同源 /api/reader/img 代理 + 本地磁盘缓存：站内闭环、翻页秒开。
  * 书架 / 进度 / 阅读偏好只写本地 cache/reader/shelf.json。
"""
from __future__ import annotations

import hashlib
import html as _html
import json
import re
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit

import requests

import reader_catalog as RC

UA = "DownloadStackReader/2.5 (desktop; +https://github.com/)"
IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".bmp"}
BOOK_EXTS = {".epub", ".txt", ".pdf", ".cbz", ".zip"}
MD_API = "https://api.mangadex.org"
WS_API = "https://zh.wikisource.org/w/api.php"
WS_INDEX = "https://zh.wikisource.org/w/index.php"
IMG_HOST_SUFFIXES = (
    "mangadex.org", "mangadex.network", "gutenberg.org", "wikimedia.org",
    "wikisource.org", "archive.org", "us.archive.org", "standardebooks.org",
    "openlibrary.org",
    "readdetectiveconan.com", "mangapill.com", "readcomiconline.li",
    "syosetu.com", "ncode.syosetu.com",
)

SOURCES = [
    {"id": "mangadex", "name": "MangaDex 漫画", "kind": "manga", "icon": "🍥"},
    {"id": "wikisource", "name": "维基文库 · 中文古籍", "kind": "book", "icon": "📜"},
    {"id": "gutenberg", "name": "Gutenberg 世界名著", "kind": "book", "icon": "🏛️"},
    {"id": "archive", "name": "Internet Archive 扫描本", "kind": "scan", "icon": "🗄️"},
    {"id": "stdbooks", "name": "Standard Ebooks 精校名著", "kind": "book", "icon": "📘"},
    {"id": "style", "name": "风格馆 · 按题材直达", "kind": "book", "icon": "🌈"},
    {"id": "syosetu", "name": "小説家になろう · 日轻", "kind": "book", "icon": "🇯🇵"},
    {"id": "local", "name": "本地书库", "kind": "local", "icon": "💾"},
]


# ============================================================ 小工具
def _natkey(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(s))]


def _decode_text(raw: bytes) -> str:
    if raw[:3] == b"\xef\xbb\xbf":
        return raw[3:].decode("utf-8", "replace")
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", "replace")
    for enc in ("utf-8", "gb18030", "big5"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", "replace")


def _sniff_img(data: bytes) -> str:
    if data[:4] == b"\x89PNG":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:4] == b"GIF8":
        return "image/gif"
    if data[4:12] in (b"ftypavif", b"ftypavis"):
        return "image/avif"
    if data[:2] == b"BM":
        return "image/bmp"
    return "image/jpeg"


def img_url(u: str) -> str:
    return "/api/reader/img?u=" + quote(u, safe="")


def local_url(path: str, entry: str = "") -> str:
    q = "/api/reader/local?p=" + quote(str(path), safe="")
    if entry:
        q += "&e=" + quote(entry, safe="")
    return q


def is_allowed_img_host(u: str) -> bool:
    try:
        sp = urlsplit(u)
    except Exception:
        return False
    if sp.scheme not in ("http", "https"):
        return False
    host = (sp.hostname or "").lower()
    return any(host == s or host.endswith("." + s) for s in IMG_HOST_SUFFIXES)


# ============================================================ HTML 清洗（只保留排版语义）
class _Sanitizer(HTMLParser):
    KEEP = {"p", "br", "h1", "h2", "h3", "h4", "h5", "h6", "em", "i", "b", "strong",
            "blockquote", "ul", "ol", "li", "hr", "sup", "sub", "img", "pre", "code",
            "table", "tr", "td", "th", "tbody", "thead", "ruby", "rt", "rp", "dl", "dt", "dd"}
    BLOCKS = {"div", "section", "article", "center", "header", "footer", "aside", "figure", "figcaption"}
    DROP = {"script", "style", "head", "title", "noscript", "iframe", "object", "svg", "math",
            "form", "button", "input", "select", "textarea", "nav", "link", "meta"}
    VOID = {"br", "hr", "img"}

    def __init__(self, img_cb=None, drop_classes=()):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0
        self.stack: list[str] = []
        self.img_cb = img_cb
        self.drop_classes = set(drop_classes)

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        a = dict(attrs)
        cls = set((a.get("class") or "").split())
        if self.skip:
            if tag not in self.VOID:
                self.skip += 1
            return
        if tag in self.DROP or (cls & self.drop_classes) or a.get("id") in ("headerContainer", "toc"):
            if tag not in self.VOID:
                self.skip = 1
            return
        if tag == "img":
            src = a.get("src") or a.get("data-src") or ""
            if self.img_cb and src:
                nu = self.img_cb(src)
                if nu:
                    self.out.append('<img loading="lazy" src="%s" alt=""/>' % _html.escape(nu, quote=True))
            return
        if tag in self.BLOCKS:
            tag = "p"
        if tag in self.KEEP:
            if tag in self.VOID:
                self.out.append("<%s/>" % tag)
            else:
                self.out.append("<%s>" % tag)
                self.stack.append(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self.skip:
            if tag not in self.VOID:
                self.skip -= 1
            return
        if tag in self.BLOCKS:
            tag = "p"
        if tag in self.KEEP and tag not in self.VOID and tag in self.stack:
            while self.stack:
                t = self.stack.pop()
                self.out.append("</%s>" % t)
                if t == tag:
                    break

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag.lower() not in self.VOID and not self.skip:
            self.handle_endtag(tag)

    def handle_data(self, data):
        if not self.skip and data:
            self.out.append(_html.escape(data, quote=False))

    def result(self) -> str:
        while self.stack:
            self.out.append("</%s>" % self.stack.pop())
        s = "".join(self.out)
        s = re.sub(r"<p>\s*</p>", "", s)
        s = re.sub(r"(<br/>\s*){3,}", "<br/><br/>", s)
        return s.strip()


def sanitize_html(raw: str, img_cb=None, drop_classes=()) -> str:
    p = _Sanitizer(img_cb=img_cb, drop_classes=drop_classes)
    try:
        p.feed(raw)
        p.close()
    except Exception:
        pass
    return p.result()


def text_to_html(txt: str) -> str:
    out = []
    for line in txt.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = line.strip().strip("\u3000")
        if line:
            out.append("<p>%s</p>" % _html.escape(line, quote=False))
    return "\n".join(out)


_TXT_CH_RE = re.compile(
    r"^\s{0,4}(?:(?:正文\s*)?第\s*[0-9零〇一二两三四五六七八九十百千万壹贰叁肆伍陆柒捌玖拾佰仟]+\s*[章回节節卷集部篇话話幕]"
    r"(?:[ \t\u3000:：、.\-—]*\S.{0,40})?|(?:序章|楔子|引子|尾声|尾聲|后记|後記|番外.{0,20}|前言|序言)\s*.{0,30}"
    r"|(?:Chapter|CHAPTER|Part|PART|Book|BOOK)\s+[0-9IVXLCivxlc]+\b.{0,60})\s*$",
    re.M,
)


def split_txt(txt: str):
    """把 TXT 切成章节：[(title, start, end)]。识别不到章节就按 ~6000 字分页。"""
    txt = txt.replace("\r\n", "\n").replace("\r", "\n")
    marks = [(m.start(), m.group(0).strip()) for m in _TXT_CH_RE.finditer(txt)]
    chs = []
    if len(marks) >= 2:
        if marks[0][0] > 200:
            chs.append(("开篇", 0, marks[0][0]))
        for i, (pos, title) in enumerate(marks):
            end = marks[i + 1][0] if i + 1 < len(marks) else len(txt)
            chs.append((title[:60], pos, end))
    else:
        step = 6000
        i, n = 0, 1
        while i < len(txt):
            j = min(len(txt), i + step)
            k = txt.find("\n", j)
            j = k if (k != -1 and k - j < 800) else j
            chs.append(("第 %d 页" % n, i, j))
            i, n = j, n + 1
    return chs or [("全文", 0, len(txt))]


# ============================================================ 主类
# inserted just above class ReaderHub

_TW2CN = str.maketrans({
    "紅": "红", "樓": "楼", "夢": "梦", "遊": "游", "國": "国", "傳": "传", "說": "说", "語": "语",
    "詩": "诗", "詞": "词", "經": "经", "學": "学", "戰": "战", "後": "后", "書": "书", "開": "开",
    "關": "关", "門": "门", "為": "为", "爲": "为", "與": "与", "這": "这", "還": "还", "來": "来",
    "對": "对", "時": "时", "長": "长", "東": "东", "車": "车", "農": "农", "風": "风", "萬": "万",
    "點": "点", "俠": "侠", "劍": "剑", "異": "异", "靈": "灵", "現": "现", "實": "实", "歷": "历",
    "記": "记", "義": "义", "華": "华", "漢": "汉", "愛": "爱", "戀": "恋", "歲": "岁", "從": "从",
    "無": "无", "電": "电", "術": "术", "業": "业", "發": "发", "會": "会", "內": "内", "個": "个",
    "們": "们", "條": "条", "爾": "尔", "將": "将", "於": "于", "並": "并", "卻": "却", "隻": "只",
    "葉": "叶", "馬": "马", "鳥": "鸟", "魚": "鱼", "龍": "龙", "鳳": "凤", "雲": "云", "論": "论",
    "莊": "庄", "亞": "亚", "歐": "欧", "齋": "斋", "誌": "志", "閱": "阅", "筆": "笔", "錄": "录",
    "戲": "戏", "劇": "剧", "兒": "儿", "殘": "残", "場": "场", "狀": "状", "觀": "观", "處": "处",
    "體": "体", "廣": "广", "園": "园", "圖": "图", "師": "师", "當": "当", "數": "数", "舊": "旧",
    "樂": "乐", "機": "机", "樹": "树", "氣": "气", "決": "决", "爭": "争", "獨": "独", "環": "环",
    "畫": "画", "盡": "尽", "種": "种", "竇": "窦", "簡": "简", "節": "节", "紅": "红", "純": "纯",
    "級": "级", "細": "细", "終": "终", "組": "组", "結": "结", "絕": "绝", "給": "给", "統": "统",
    "絲": "丝", "綠": "绿", "維": "维", "網": "网", "線": "线", "編": "编", "練": "练", "緣": "缘",
    "縱": "纵", "織": "织", "續": "续", "繼": "继", "齊": "齐", "麵": "面", "麼": "么", "係": "系",
    "孫": "孙", "蕭": "萧", "劉": "刘", "張": "张", "陳": "陈", "楊": "杨", "黃": "黄", "趙": "赵",
    "吳": "吴", "週": "周", "鄭": "郑", "馮": "冯", "蔣": "蒋", "韓": "韩", "曹": "曹", "薛": "薛",
    "賈": "贾", "釵": "钗", "黛": "黛", "玉": "玉", "寶": "宝", "蘭": "兰", "聖": "圣", "賢": "贤",
    "禮": "礼", "儀": "仪", "禪": "禅", "釋": "释", "僧": "僧", "佛": "佛", "陰": "阴", "陽": "阳",
    "兩": "两", "雙": "双", "貳": "贰", "冊": "册", "捲": "卷", "巻": "卷",
})

_EDITION_RE = re.compile(
    r"(简体横排|繁體豎排|繁體直排|繁体竖排|繁体|简体|通行本|脂评汇校本|脂评本|甲戌本|庚辰本|程甲本|"
    r"校注本|汇校本|校本|译注|注譯|白話|白话|全译|全譯|全本|绣像|繡像|点校本|點校本|"
    r"扫描版|掃描版|在线阅读|电子书|"
    r"上册|下册|中册|上卷|下卷|中卷|卷一|卷二|卷三|卷四|卷五|"
    r"第[0-9一二三四五六七八九十百千]+[部册卷集回篇]|"
    r"\s*[-–—_,，]\s*(pdf|epub|txt|doc|mobi|azw3|scan).*$)",
    re.I,
)

_FMT_RE = re.compile(r"(pdf|epub|txt|doc|mobi|azw3|html|扫描版|扫描本|文件)+", re.I)

_CANON_RAW = [
    "红楼梦", "西游记", "三国演义", "水浒传", "聊斋志异", "儒林外史", "封神演义",
    "金瓶梅", "古文观止", "史记", "资治通鉴", "诗经", "楚辞", "论语", "孟子",
    "道德经", "庄子", "左传", "战国策", "世说新语", "镜花缘", "三侠五义", "七侠五义",
    "西厢记", "牡丹亭", "桃花扇", "长生殿", "呐喊", "彷徨", "阿Q正传", "狂人日记",
    "孔乙己", "祝福", "搜神记", "阅微草堂笔记", "子不语", "老残游记", "海上花列传",
    "官场现形记", "儿女英雄传", "平妖传", "东游记", "Pride and Prejudice",
    "Jane Eyre", "Wuthering Heights", "Great Expectations", "Frankenstein",
    "Dracula", "Moby Dick", "War and Peace", "Crime and Punishment",
    "The Adventures of Sherlock Holmes", "Alice's Adventures in Wonderland",
]

_SRC_RANK = {
    "wikisource": 0, "stdbooks": 1, "gutenberg": 2, "mangadex": 3,
    "local": 4, "archive": 5,
}


def _compact_title(title: str) -> str:
    s = str(title or "").translate(_TW2CN).lower()
    s = re.sub(r"^(the|a|an)\s+", "", s)
    s = re.sub(r"[《》「」『』\[\]()（）【】〈〉<>]", "", s)
    s = _EDITION_RE.sub("", s)
    s = _FMT_RE.sub("", s)
    s = re.sub(r"(曹雪芹著|吳铭恩汇校|吴铭恩汇校|著$)", "", s)
    s = re.sub(r'[·・,，.。:：;；!！?？、"\'“”‘’`～/\s_\-—–]+', "", s)
    return s


_CANON_COMPACT = sorted({_compact_title(x) for x in _CANON_RAW if _compact_title(x)}, key=len, reverse=True)


def item_sid(it) -> str:
    return "%s::%s" % (it.get("src") or "", it.get("id") or "")


def work_fingerprint(it) -> str:
    key = _compact_title(it.get("title") or "")
    for c in _CANON_COMPACT:
        if not c:
            continue
        if key == c or key.startswith(c) or (len(c) >= 4 and c in key[: len(c) + 16]):
            return c + "|"
    author = re.sub(r"\s+", "", str(it.get("author") or "").translate(_TW2CN).lower())[:24]
    if len(key) < 4:
        return key + "|" + author + "|" + str(it.get("id") or "")
    return key[:48] + "|" + (author[:12] if author else "")


def _clean_score(it) -> float:
    t = str(it.get("title") or "")
    s = 0.0
    if it.get("cover"):
        s += 2
    low = t.lower()
    if any(x in low for x in ("pdf", "epub", "txt", "doc", "文件", "扫描")):
        s -= 3
    if any(x in t for x in ("通行本", "汇校", "脂评", "校注")):
        s -= 1
    s -= min(len(t), 120) / 120.0
    return s


def _better_edition(new, old) -> bool:
    nr = _SRC_RANK.get(new.get("src"), 9)
    or_ = _SRC_RANK.get(old.get("src"), 9)
    if nr < or_:
        return True
    if nr > or_:
        return False
    return _clean_score(new) > _clean_score(old) + 0.05


def dedupe_items(items):
    """Unique by src+id, then by normalized title/author. Prefer 维基文库 / Standard Ebooks over extra IA scans."""
    out = []
    sid_seen = set()
    fp_index = {}
    for it in items or []:
        if not it or not it.get("id"):
            continue
        sid = item_sid(it)
        if sid in sid_seen:
            continue
        sid_seen.add(sid)
        fp = work_fingerprint(it)
        if fp in fp_index:
            i = fp_index[fp]
            if _better_edition(it, out[i]):
                out[i] = it
            continue
        fp_index[fp] = len(out)
        out.append(it)
    return out



class ReaderHub:
    def __init__(self, cache_dir: Path, proxy_fn=None, roots_fn=None, log_fn=None):
        self.base = Path(cache_dir) / "reader"
        self.books_dir = self.base / "books"
        self.img_dir = self.base / "img"
        for d in (self.base, self.books_dir, self.img_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.shelf_file = self.base / "shelf.json"
        self.proxy_fn = proxy_fn or (lambda: "")
        self.roots_fn = roots_fn or (lambda: [])
        self.log = log_fn or (lambda *a, **k: None)
        self.lock = threading.RLock()
        self._mem: dict = {}           # 小型内存缓存：key -> (ts, value)
        self._scan_cache = (0.0, [])
        self._img_writes = 0
        self.jobs: dict = {}            # 离线下载任务
        self._src_fail_until: dict = {}  # 源站刚超时则短时跳过，避免拖死「全部来源」
        self.pool = ThreadPoolExecutor(max_workers=20)
        self._home_sids = set()
        self._home_fps = set()

    # ---------------------------------------------------------------- HTTP
    def _get(self, url, params=None, timeout=15, stream=False, headers=None):
        """直连优先，失败再走系统代理（或反之）；返回 requests.Response。"""
        px = ""
        try:
            px = self.proxy_fn() or ""
        except Exception:
            px = ""
        plans = ["", px] if px else [""]
        if px and any(h in url for h in ("mangadex", "gutendex", "gutenberg", "archive.org", "wikisource", "wikimedia", "standardebooks.org", "openlibrary.org")):
            plans = [px, ""]
        hdr = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7"}
        if headers:
            hdr.update(headers)
        last = None
        for p in plans:
            s = requests.Session()
            s.trust_env = False
            try:
                r = s.get(url, params=params, timeout=timeout, stream=stream, headers=hdr,
                          proxies=({"http": p, "https": p} if p else None))
                if r.status_code >= 500 and p != plans[-1]:
                    last = RuntimeError("HTTP %s" % r.status_code)
                    continue
                return r
            except Exception as ex:
                last = ex
        raise last or RuntimeError("网络请求失败")

    def _json(self, url, params=None, timeout=15):
        r = self._get(url, params=params, timeout=timeout)
        if r.status_code >= 400:
            raise RuntimeError("HTTP %s" % r.status_code)
        return r.json()

    def _memo(self, key, ttl, fn):
        now = time.time()
        with self.lock:
            hit = self._mem.get(key)
            if hit and now - hit[0] < ttl:
                return hit[1]
        val = fn()
        with self.lock:
            self._mem[key] = (now, val)
            if len(self._mem) > 300:
                for k in sorted(self._mem, key=lambda k: self._mem[k][0])[:100]:
                    self._mem.pop(k, None)
        return val

    # ---------------------------------------------------------------- 搜索
    # 各源单独限时：绝不为了一个挂掉的源（如 Gutenberg 维护）堵死整次搜索。
    SRC_TIMEOUT = {
        "local": 4, "mangadex": 12, "wikisource": 12, "archive": 12, "gutenberg": 8,
        "stdbooks": 12, "openlibrary": 12,
        "style": 16, "syosetu": 14,
    }
    SRC_FAIL_COOLDOWN = 90

    def search(self, q: str, source: str = "all", lang: str = "zh", page: int = 0):
        q = (q or "").strip()
        srcs = [s["id"] for s in SOURCES] if source in ("", "all") else [source]
        if source in ("", "all") and "openlibrary" not in srcs:
            srcs = list(srcs) + ["openlibrary"]
        elif source == "archive" and q:
            srcs = ["archive", "openlibrary"]
        fns = {
            "mangadex": lambda: self.md_search(q, lang, page),
            "wikisource": lambda: (self.ws_search(q, page) if q else self.ws_browse(
                ["紅樓夢", "西遊記", "三國演義", "水滸傳", "唐詩三百首", "論語"], page)),
            "gutenberg": lambda: self.gb_search(q, lang, page),
            "archive": lambda: self.ia_search(q, page),
            "local": lambda: self.local_search(q),
            "stdbooks": lambda: self.se_search(q, page),
            "openlibrary": lambda: (self.ol_search(q, page) if q else []),
            "style": lambda: self.style_search(q or "热门", page),
            "syosetu": lambda: self.sy_search(q, page),
        }
        results, errors = [], {}
        now0 = time.time()
        futs = {}
        for s in srcs:
            if s not in fns:
                continue
            until = float(self._src_fail_until.get(s) or 0)
            if until > now0:
                errors[s] = "源站最近超时，已暂时跳过"
                continue
            futs[self.pool.submit(fns[s])] = s
        pending = set(futs)
        while pending:
            now = time.time()
            expired, next_wait = [], 12.0
            for f in list(pending):
                s = futs[f]
                left = self.SRC_TIMEOUT.get(s, 12) - (now - now0)
                if left <= 0:
                    expired.append(f)
                else:
                    next_wait = min(next_wait, left)
            for f in expired:
                s = futs[f]
                pending.discard(f)
                errors[s] = "连接超时或源站无响应"
                self._src_fail_until[s] = time.time() + self.SRC_FAIL_COOLDOWN
            if not pending:
                break
            done, pending = wait(pending, timeout=max(0.05, next_wait), return_when=FIRST_COMPLETED)
            for f in done:
                s = futs[f]
                try:
                    results.extend(f.result() or [])
                    self._src_fail_until.pop(s, None)
                except Exception as ex:
                    errors[s] = (str(ex)[:160] or type(ex).__name__)
                    self._src_fail_until[s] = time.time() + self.SRC_FAIL_COOLDOWN
        return dedupe_items(results), errors

    # ---------------------------------------------------------------- MangaDex
    @staticmethod
    def _md_title(attr, lang):
        titles = attr.get("title") or {}
        alts = {}
        for d in attr.get("altTitles") or []:
            for k, v in d.items():
                alts.setdefault(k, v)
        order = (["zh", "zh-hk", "ja", "en", "ja-ro"] if lang.startswith("zh") else ["en", "ja-ro", "zh", "ja"])
        for k in order:
            if titles.get(k):
                return titles[k]
            if alts.get(k):
                return alts[k]
        return next(iter(titles.values()), "") or next(iter(alts.values()), "") or "未命名"

    def _md_item(self, m, lang):
        attr = m.get("attributes") or {}
        cover, author = "", ""
        for rel in m.get("relationships") or []:
            if rel.get("type") == "cover_art" and (rel.get("attributes") or {}).get("fileName"):
                cover = img_url("https://uploads.mangadex.org/covers/%s/%s.512.jpg" % (m["id"], rel["attributes"]["fileName"]))
            if rel.get("type") in ("author", "artist") and not author:
                author = (rel.get("attributes") or {}).get("name") or ""
        desc = attr.get("description") or {}
        d = desc.get("zh") or desc.get("zh-hk") or desc.get("en") or next(iter(desc.values()), "")
        tags = []
        for t in attr.get("tags") or []:
            nm = ((t.get("attributes") or {}).get("name") or {}).get("en")
            if nm:
                tags.append(nm)
        return {
            "src": "mangadex", "id": m["id"], "kind": "manga",
            "title": self._md_title(attr, lang), "author": author, "cover": cover,
            "desc": re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", d or "")[:1200],
            "tags": tags[:8], "status": attr.get("status") or "", "year": attr.get("year") or "",
            "langs": attr.get("availableTranslatedLanguages") or [],
        }

    def _md_langs(self, lang, wide=False):
        if wide or lang == "all":
            return ["zh", "zh-hk", "en", "ja"]
        if lang == "en":
            return ["en"]
        if lang == "ja":
            return ["ja", "en"]
        return ["zh", "zh-hk"]

    def md_search(self, q, lang="zh", page=0, tag=None, demographic=None, order=None, wide=False, status=None, limit=24):
        q = (q or "").strip()
        g = RC.match_manga_query(q) if q and not tag and not demographic else None
        q_title = q
        if g:
            tag = tag or g.get("tag")
            demographic = demographic or g.get("demo")
            q_title = ""
        limit = max(1, min(int(limit or 24), 100))
        params = {
            "limit": limit, "offset": max(0, int(page)) * limit,
            "includes[]": ["cover_art", "author"],
            "contentRating[]": ["safe", "suggestive"],
            "hasAvailableChapters": "true",
        }
        params["availableTranslatedLanguage[]"] = self._md_langs(lang, wide=wide)
        if tag:
            params["includedTags[]"] = tag
            params["includedTagsMode"] = "AND"
        if demographic:
            params["publicationDemographic[]"] = demographic
        if status:
            params["status[]"] = status
        if q_title:
            params["title"] = q_title
            params["order[relevance]"] = "desc"
        else:
            key = order or "followedCount"
            if key not in ("followedCount", "latestUploadedChapter", "relevance", "updatedAt", "createdAt"):
                key = "followedCount"
            params["order[%s]" % key] = "desc"
        memo_key = ("mds", q, lang, page, tag or "", demographic or "", order or "", bool(wide), status or "", limit)
        j = self._memo(memo_key, 600, lambda: self._json(MD_API + "/manga", params, timeout=18))
        return [self._md_item(m, lang) for m in j.get("data") or []]

    def md_detail(self, mid, lang="zh"):
        j = self._json(MD_API + "/manga/" + mid, {"includes[]": ["cover_art", "author"]})
        info = self._md_item(j["data"], lang)
        langs = self._md_langs(lang)

        def _md_feed(lang_list):
            got, off = [], 0
            while off < 3000:
                params = {
                    "limit": 500, "offset": off,
                    "order[volume]": "asc", "order[chapter]": "asc", "includeExternalUrl": 0,
                    "contentRating[]": ["safe", "suggestive", "erotica"],
                    "includes[]": ["scanlation_group"],
                }
                if lang_list:
                    params["translatedLanguage[]"] = lang_list
                f = self._json(MD_API + "/manga/%s/feed" % mid, params, timeout=20)
                for c in f.get("data") or []:
                    a = c.get("attributes") or {}
                    if a.get("externalUrl") or a.get("isUnavailable") or not a.get("pages"):
                        continue
                    grp = ""
                    for rel in c.get("relationships") or []:
                        if rel.get("type") == "scanlation_group":
                            grp = (rel.get("attributes") or {}).get("name") or ""
                    got.append({
                        "id": c["id"], "num": a.get("chapter") or "", "vol": a.get("volume") or "",
                        "lang": a.get("translatedLanguage") or "", "pages": a.get("pages") or 0,
                        "group": grp, "raw_title": a.get("title") or "",
                    })
                off += 500
                if off >= int(f.get("total") or 0):
                    break
            return got

        chapters = _md_feed(langs)
        if not chapters:
            wide = self._md_langs(lang, wide=True)
            if wide != list(langs):
                chapters = _md_feed(wide)
                langs = wide
        if not chapters:
            chapters = _md_feed(None)
        # 同一话多个译本：按语言偏好 + 页数取一个
        pref = {l: i for i, l in enumerate(langs)}
        best: dict = {}
        for c in chapters:
            k = (c["vol"], c["num"]) if c["num"] else ("_", c["id"])
            o = best.get(k)
            if o is None or (pref.get(c["lang"], 9), -c["pages"]) < (pref.get(o["lang"], 9), -o["pages"]):
                best[k] = c
        out = sorted(best.values(), key=lambda c: (_natkey(c["num"] or "0"), _natkey(c["vol"] or "0")))
        out.sort(key=lambda c: float(c["num"]) if re.fullmatch(r"\d+(\.\d+)?", c["num"] or "") else 1e9)
        for c in out:
            label = ("第 %s 话" % c["num"]) if c["num"] else "单话"
            if c["vol"]:
                label = "卷%s · %s" % (c["vol"], label)
            if c["raw_title"]:
                label += " " + c["raw_title"]
            c["title"] = label
            c["sub"] = "%s · %sP%s" % (c["lang"], c["pages"], (" · " + c["group"]) if c["group"] else "")
        info["chapters"] = [{"id": c["id"], "title": c["title"], "sub": c["sub"]} for c in out]
        info["read_type"] = "images"
        return info

    def md_pages(self, cid, quality="data"):
        j = self._json(MD_API + "/at-home/server/" + cid, timeout=15)
        if not j.get("baseUrl"):
            raise RuntimeError("该话暂不可读（可能已被版权方下架）")
        ch = j["chapter"]
        key = "dataSaver" if quality == "saver" else "data"
        files = ch.get(key) or ch.get("data") or []
        seg = "data-saver" if key == "dataSaver" else "data"
        return [img_url("%s/%s/%s/%s" % (j["baseUrl"], seg, ch["hash"], f)) for f in files]

    # ---------------------------------------------------------------- 维基文库
    def ws_search(self, q, page=0):
        j = self._memo(("wss", q, page), 900, lambda: self._json(WS_API, {
            "action": "query", "list": "search", "srsearch": q, "srnamespace": 0,
            "srlimit": 30, "sroffset": int(page) * 30, "format": "json", "srprop": "snippet|wordcount",
        }))
        seen, out = set(), []
        for x in (j.get("query") or {}).get("search") or []:
            title = x.get("title") or ""
            root = title.split("/")[0]
            if root in seen or "判决书" in root or "判決書" in root:
                continue
            seen.add(root)
            snip = re.sub(r"<[^>]+>", "", x.get("snippet") or "")
            out.append({"src": "wikisource", "id": root, "kind": "book", "title": root,
                        "author": "维基文库", "cover": "", "desc": _html.unescape(snip)[:300],
                        "tags": ["公有领域", "中文"]})
        return out[:20]

    def _ws_render(self, title):
        r = self._get(WS_INDEX, {"title": title, "action": "render", "variant": "zh-hans"}, timeout=20)
        if r.status_code >= 400:
            raise RuntimeError("维基文库页面不存在：%s" % title)
        r.encoding = "utf-8"
        return r.text

    def ws_detail(self, title):
        raw = self._memo(("wsr", title), 1800, lambda: self._ws_render(title))
        chapters, seen = [], set()
        for m in re.finditer(r'href="(?:https?:)?//zh\.wikisource\.org/wiki/([^"#?]+)"[^>]*>(.*?)</a>', raw, re.S):
            t = unquote(m.group(1)).replace("_", " ")
            if not t.startswith(title + "/") or t in seen:
                continue
            seen.add(t)
            label = re.sub(r"<[^>]+>", "", m.group(2)).strip() or t.split("/", 1)[1]
            chapters.append({"id": t, "title": label[:60], "sub": ""})
        author = ""
        ma = re.search(r'/wiki/Author:([^"#?]+)"', raw)
        if ma:
            author = unquote(ma.group(1)).replace("_", " ")
        if not chapters:
            chapters = [{"id": title, "title": title, "sub": "全文"}]
        return {"src": "wikisource", "id": title, "kind": "book", "title": title, "author": author,
                "cover": "", "desc": "维基文库公有领域文本 · 共 %d 章" % len(chapters),
                "chapters": chapters, "read_type": "html", "tags": ["公有领域"]}

    def ws_chapter(self, title):
        raw = self._memo(("wsr", title), 1800, lambda: self._ws_render(title))
        body = sanitize_html(
            raw,
            img_cb=lambda s: img_url(("https:" + s) if s.startswith("//") else s) if ("wikimedia" in s) else "",
            drop_classes=("mw-editsection", "reference", "references", "noprint", "navbox",
                          "mw-references-wrap", "ws-noexport", "licenseContainer", "licenseBanner",
                          "metadata", "printfooter", "catlinks"),
        )
        return {"type": "html", "title": title.split("/")[-1], "html": body}

    # ---------------------------------------------------------------- Gutenberg
    def gb_search(self, q, lang="zh", page=0):
        params = {"page": int(page) + 1}
        if q:
            params["search"] = q
        if lang in ("zh", "en"):
            params["languages"] = lang if q else "zh,en"
        j = self._memo(("gbs", q, lang, page), 1800, lambda: self._json("https://gutendex.com/books", params, timeout=25))
        out = []
        for b in j.get("results") or []:
            fm = b.get("formats") or {}
            if not any(k.startswith("application/epub") for k in fm):
                continue
            cov = fm.get("image/jpeg") or ""
            out.append({
                "src": "gutenberg", "id": str(b.get("id")), "kind": "book",
                "title": b.get("title") or "", "cover": img_url(cov) if cov else "",
                "author": ", ".join(a.get("name", "") for a in b.get("authors") or [])[:80],
                "desc": " / ".join((b.get("summaries") or [])[:1])[:900] or " · ".join((b.get("subjects") or [])[:4]),
                "tags": (b.get("languages") or []) + (b.get("bookshelves") or [])[:2],
            })
        return out

    def gb_fetch(self, gid):
        gid = re.sub(r"\D", "", str(gid))
        dst = self.books_dir / ("gutenberg_%s.epub" % gid)
        if dst.is_file() and dst.stat().st_size > 1024:
            return dst
        urls = ["https://www.gutenberg.org/ebooks/%s.epub3.images" % gid,
                "https://www.gutenberg.org/ebooks/%s.epub.images" % gid,
                "https://www.gutenberg.org/ebooks/%s.epub.noimages" % gid]
        last = None
        for u in urls:
            try:
                r = self._get(u, timeout=60)
                if r.status_code == 200 and r.content[:2] == b"PK":
                    tmp = dst.with_suffix(".part")
                    tmp.write_bytes(r.content)
                    tmp.replace(dst)
                    return dst
                last = RuntimeError("HTTP %s" % r.status_code)
            except Exception as ex:
                last = ex
        raise RuntimeError("Gutenberg EPUB 下载失败：%s" % last)

    def gb_detail(self, gid):
        p = self.gb_fetch(gid)
        info = self.local_detail(str(p))
        info.update({"src": "gutenberg", "id": str(gid)})
        return info

    # ---------------------------------------------------------------- Internet Archive
    def ia_search(self, q, page=0):
        q = (q or "").strip()
        if not q:
            qq = 'mediatype:texts AND (collection:gutenberg OR creator:"Standard Ebooks")' + RC.IA_SAFE
        else:
            safe = re.sub(r'[()\":]', " ", q)
            qq = "(title:(%s) OR creator:(%s)) AND mediatype:texts" % (safe, safe) + RC.IA_SAFE
        return self.ia_query(qq, page, kind_hint="scan")
    def ia_detail(self, ident):
        info = {"src": "archive", "id": ident, "kind": "scan", "title": ident, "author": "",
                "cover": img_url("https://archive.org/services/img/" + ident), "desc": "", "tags": []}
        try:
            md = self._json("https://archive.org/metadata/%s/metadata" % ident, timeout=15).get("result") or {}
            t = md.get("title")
            info["title"] = t if isinstance(t, str) else ident
            c = md.get("creator") or ""
            info["author"] = c if isinstance(c, str) else ", ".join(c[:2])
            d = md.get("description") or ""
            info["desc"] = re.sub(r"<[^>]+>", "", d if isinstance(d, str) else " ".join(d))[:900]
        except Exception:
            pass
        info["chapters"] = [{"id": ident, "title": "全本（扫描翻页）", "sub": "IIIF"}]
        info["read_type"] = "images"
        return info

    def ia_pages(self, ident, quality="data"):
        m = self._memo(("iam", ident), 3600, lambda: self._json(
            "https://iiif.archive.org/iiif/3/%s/manifest.json" % ident, timeout=30))
        width = 900 if quality == "saver" else 1600
        pages = []
        for canvas in m.get("items") or []:
            try:
                body = canvas["items"][0]["items"][0]["body"]
            except Exception:
                continue
            svc = body.get("service") or []
            sid = ""
            if isinstance(svc, list) and svc:
                sid = svc[0].get("id") or svc[0].get("@id") or ""
            if sid:
                pages.append(img_url("%s/full/%d,/0/default.jpg" % (sid.rstrip("/"), width)))
            elif body.get("id"):
                pages.append(img_url(body["id"]))
        if not pages:
            raise RuntimeError("该扫描本没有可用的页面（可能是借阅类图书）")
        return pages

    # ---------------------------------------------------------------- 本地书库
    def _roots(self):
        out = []
        for r in list(self.roots_fn() or []) + [self.books_dir]:
            try:
                p = Path(r).expanduser().resolve()
                if p.is_dir() and p not in out:
                    out.append(p)
            except Exception:
                pass
        return out

    def allowed_path(self, raw: str):
        if not raw:
            return None
        try:
            p = Path(raw).resolve()
        except Exception:
            return None
        if not p.exists():
            return None
        for rt in self._roots():
            try:
                p.relative_to(rt)
                return p
            except ValueError:
                continue
        return None

    def scan_local(self, force=False):
        ts, items = self._scan_cache
        if not force and time.time() - ts < 45 and items:
            return items
        found, seen = [], set()
        budget = [20000]

        def walk(d: Path, depth: int):
            if depth > 5 or budget[0] <= 0:
                return
            try:
                entries = list(d.iterdir())
            except Exception:
                return
            budget[0] -= len(entries)
            imgs = [e for e in entries if e.is_file() and e.suffix.lower() in IMG_EXTS]
            if len(imgs) >= 4 and depth > 0:
                key = str(d)
                if key not in seen:
                    seen.add(key)
                    found.append(self._local_item(d, "folder", len(imgs)))
            for e in entries:
                if e.name.startswith((".", "$")) or e.name in ("node_modules", "img", "__pycache__"):
                    continue
                if e.is_dir():
                    walk(e, depth + 1)
                elif e.suffix.lower() in BOOK_EXTS and str(e) not in seen:
                    if e.suffix.lower() == ".zip" and not self._zip_is_comic(e):
                        continue
                    seen.add(str(e))
                    found.append(self._local_item(e, e.suffix.lower().lstrip("."), 0))

        for rt in self._roots():
            walk(rt, 0)
        found.sort(key=lambda x: -x.get("mtime", 0))
        self._scan_cache = (time.time(), found)
        return found

    @staticmethod
    def _zip_is_comic(p: Path) -> bool:
        try:
            if p.stat().st_size > 2 * 1024 ** 3:
                return False
            with zipfile.ZipFile(p) as z:
                names = z.namelist()[:400]
            n = sum(1 for x in names if PurePosixPath(x).suffix.lower() in IMG_EXTS)
            return n >= 3 and n >= len(names) * 0.6
        except Exception:
            return False

    def _local_item(self, p: Path, fmt: str, nimg: int):
        try:
            st = p.stat()
            mtime, size = st.st_mtime, (st.st_size if p.is_file() else 0)
        except Exception:
            mtime, size = 0, 0
        kind = "manga" if fmt in ("cbz", "zip", "folder") else "book"
        cover = ""
        if fmt == "folder":
            try:
                first = sorted((e for e in p.iterdir() if e.suffix.lower() in IMG_EXTS), key=lambda e: _natkey(e.name))[0]
                cover = local_url(str(first))
            except Exception:
                cover = ""
        elif fmt in ("cbz", "zip", "epub"):
            cover = local_url(str(p), "@cover")
        title = p.stem if p.is_file() else p.name
        if fmt == "epub" and title.startswith("gutenberg_"):
            title = self._epub_meta_title(p) or title
        return {"src": "local", "id": str(p), "kind": kind, "title": title, "author": fmt.upper(),
                "cover": cover, "desc": str(p), "fmt": fmt, "size": size, "mtime": mtime,
                "tags": [fmt.upper()] + (["%d 张" % nimg] if nimg else [])}

    def local_search(self, q):
        items = self.scan_local()
        if not q:
            return items[:60]
        ql = q.lower()
        return [i for i in items if ql in i["title"].lower() or ql in i["id"].lower()][:60]

    # ----- EPUB
    def _epub_open(self, p: Path):
        key = ("epub", str(p), p.stat().st_mtime)
        return self._memo(key, 3600, lambda: self._epub_parse(p))

    def _epub_parse(self, p: Path):
        with zipfile.ZipFile(p) as z:
            names = set(z.namelist())
            opf_path = ""
            try:
                cx = z.read("META-INF/container.xml").decode("utf-8", "replace")
                m = re.search(r'full-path="([^"]+)"', cx)
                opf_path = m.group(1) if m else ""
            except Exception:
                pass
            if not opf_path:
                opf_path = next((n for n in names if n.lower().endswith(".opf")), "")
            opf = z.read(opf_path).decode("utf-8", "replace") if opf_path else ""
            base = str(PurePosixPath(opf_path).parent) if opf_path else ""

            def join(h):
                h = unquote(h.split("#")[0])
                full = str(PurePosixPath(base) / h) if base and base != "." else h
                parts = []
                for seg in full.split("/"):
                    if seg == "..":
                        if parts:
                            parts.pop()
                    elif seg and seg != ".":
                        parts.append(seg)
                return "/".join(parts)

            manifest, props = {}, {}
            for m in re.finditer(r"<(?:\w+:)?item\b([^>]*)/?>", opf):
                at = dict(re.findall(r'([\w:-]+)\s*=\s*"([^"]*)"', m.group(1)))
                if at.get("id") and at.get("href"):
                    manifest[at["id"]] = (join(at["href"]), at.get("media-type", ""))
                    props[at["id"]] = at.get("properties", "")
            spine = [m.group(1) for m in re.finditer(r'<(?:\w+:)?itemref\b[^>]*idref="([^"]+)"', opf)]
            title = ""
            mt = re.search(r"<dc:title[^>]*>(.*?)</dc:title>", opf, re.S)
            if mt:
                title = _html.unescape(re.sub(r"<[^>]+>", "", mt.group(1))).strip()
            author = ""
            ma = re.search(r"<dc:creator[^>]*>(.*?)</dc:creator>", opf, re.S)
            if ma:
                author = _html.unescape(re.sub(r"<[^>]+>", "", ma.group(1))).strip()
            cover = ""
            for iid, pr in props.items():
                if "cover-image" in pr:
                    cover = manifest[iid][0]
            if not cover:
                mc = re.search(r'<meta[^>]*name="cover"[^>]*content="([^"]+)"', opf) or \
                    re.search(r'<meta[^>]*content="([^"]+)"[^>]*name="cover"', opf)
                if mc and mc.group(1) in manifest:
                    cover = manifest[mc.group(1)][0]
            if not cover:
                cover = next((n for n in sorted(names) if "cover" in n.lower()
                              and PurePosixPath(n).suffix.lower() in IMG_EXTS), "")
            # 目录标题：nav.xhtml / toc.ncx
            toc = {}
            nav_id = next((i for i, pr in props.items() if "nav" in pr.split()), None)
            try:
                if nav_id:
                    nav_path = manifest[nav_id][0]
                    nav = z.read(nav_path).decode("utf-8", "replace")
                    nb = str(PurePosixPath(nav_path).parent)
                    for m in re.finditer(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', nav, re.S):
                        h = unquote(m.group(1).split("#")[0])
                        full = "/".join(x for x in (nb + "/" + h if nb not in ("", ".") else h).split("/") if x)
                        toc.setdefault(full, _html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip())
                else:
                    ncx_id = next((i for i, (h, mt_) in manifest.items() if "ncx" in mt_), None)
                    if ncx_id:
                        ncx = z.read(manifest[ncx_id][0]).decode("utf-8", "replace")
                        for m in re.finditer(r"<navPoint.*?<text>(.*?)</text>.*?<content[^>]*src=\"([^\"]+)\"", ncx, re.S):
                            toc.setdefault(join(m.group(2)), _html.unescape(m.group(1)).strip())
            except Exception:
                pass
        chapters = []
        for i, iid in enumerate(spine):
            if iid not in manifest:
                continue
            href, mt_ = manifest[iid]
            if "html" not in mt_ and not href.lower().endswith((".html", ".xhtml", ".htm")):
                continue
            chapters.append({"href": href, "title": toc.get(href) or ""})
        n = 0
        for c in chapters:
            n += 1
            if not c["title"]:
                c["title"] = "第 %d 节" % n
        return {"title": title, "author": author, "cover": cover, "chapters": chapters}

    def _epub_meta_title(self, p: Path):
        try:
            return self._epub_open(p).get("title") or ""
        except Exception:
            return ""

    # ----- TXT
    def _txt_open(self, p: Path):
        def load():
            txt = _decode_text(p.read_bytes())
            return txt, split_txt(txt)
        return self._memo(("txt", str(p), p.stat().st_mtime), 1800, load)

    # ----- CBZ / 文件夹
    def _zip_images(self, p: Path):
        def load():
            with zipfile.ZipFile(p) as z:
                return sorted((n for n in z.namelist() if PurePosixPath(n).suffix.lower() in IMG_EXTS
                               and not n.startswith("__MACOSX")), key=_natkey)
        return self._memo(("zipimg", str(p), p.stat().st_mtime), 3600, load)

    def _dir_images(self, p: Path):
        return sorted((e for e in p.iterdir() if e.is_file() and e.suffix.lower() in IMG_EXTS), key=lambda e: _natkey(e.name))

    def local_detail(self, raw):
        p = self.allowed_path(raw)
        if p is None:
            raise RuntimeError("文件不存在或不在书库目录内")
        fmt = "folder" if p.is_dir() else p.suffix.lower().lstrip(".")
        base = {"src": "local", "id": str(p), "title": p.stem if p.is_file() else p.name, "author": "",
                "desc": str(p), "cover": "", "tags": [fmt.upper()], "fmt": fmt}
        if fmt == "epub":
            e = self._epub_open(p)
            base.update({"kind": "book", "title": e["title"] or base["title"], "author": e["author"],
                         "cover": local_url(str(p), e["cover"]) if e["cover"] else "", "read_type": "html",
                         "chapters": [{"id": str(i), "title": c["title"], "sub": ""} for i, c in enumerate(e["chapters"])]})
        elif fmt == "txt":
            _, chs = self._txt_open(p)
            base.update({"kind": "book", "read_type": "html",
                         "chapters": [{"id": str(i), "title": t, "sub": "%d 字" % (b - a)} for i, (t, a, b) in enumerate(chs)]})
        elif fmt == "pdf":
            base.update({"kind": "book", "read_type": "pdf", "chapters": [{"id": "0", "title": "全文 PDF", "sub": ""}]})
        elif fmt in ("cbz", "zip"):
            imgs = self._zip_images(p)
            groups: dict = {}
            for n in imgs:
                parent = str(PurePosixPath(n).parent)
                groups.setdefault(parent, []).append(n)
            keys = sorted(groups, key=_natkey)
            base.update({"kind": "manga", "read_type": "images", "cover": local_url(str(p), imgs[0]) if imgs else "",
                         "chapters": ([{"id": k, "title": (k if k != "." else "全卷"), "sub": "%dP" % len(groups[k])} for k in keys]
                                      if len(keys) > 1 else [{"id": "*", "title": "全卷", "sub": "%dP" % len(imgs)}])})
        elif fmt == "folder":
            imgs = self._dir_images(p)
            subs = sorted((d for d in p.iterdir() if d.is_dir() and any(x.suffix.lower() in IMG_EXTS for x in d.iterdir())),
                          key=lambda d: _natkey(d.name)) if not imgs else []
            chs = [{"id": "*", "title": "全卷", "sub": "%dP" % len(imgs)}] if imgs else \
                [{"id": d.name, "title": d.name, "sub": ""} for d in subs]
            cov = imgs[0] if imgs else (self._dir_images(subs[0])[0] if subs else None)
            base.update({"kind": "manga", "read_type": "images", "chapters": chs,
                         "cover": local_url(str(cov)) if cov else ""})
        else:
            raise RuntimeError("不支持的格式：%s" % fmt)
        return base

    def local_chapter(self, raw, cid):
        p = self.allowed_path(raw)
        if p is None:
            raise RuntimeError("文件不存在或不在书库目录内")
        fmt = "folder" if p.is_dir() else p.suffix.lower().lstrip(".")
        if fmt == "epub":
            e = self._epub_open(p)
            idx = max(0, min(int(cid or 0), len(e["chapters"]) - 1))
            ch = e["chapters"][idx]
            with zipfile.ZipFile(p) as z:
                raw_html = _decode_text(z.read(ch["href"]))
            folder = str(PurePosixPath(ch["href"]).parent)

            def cb(src):
                if src.startswith(("http:", "https:", "data:")):
                    return ""
                full = "/".join(x for x in ((folder + "/" + unquote(src)) if folder not in ("", ".") else unquote(src)).split("/") if x)
                parts = []
                for seg in full.split("/"):
                    if seg == "..":
                        if parts:
                            parts.pop()
                    else:
                        parts.append(seg)
                return local_url(str(p), "/".join(parts))
            m = re.search(r"<body[^>]*>(.*)</body>", raw_html, re.S | re.I)
            return {"type": "html", "title": ch["title"], "html": sanitize_html(m.group(1) if m else raw_html, img_cb=cb)}
        if fmt == "txt":
            txt, chs = self._txt_open(p)
            idx = max(0, min(int(cid or 0), len(chs) - 1))
            t, a, b = chs[idx]
            body = txt[a:b]
            first = body.split("\n", 1)
            if first and first[0].strip() == t:
                body = first[1] if len(first) > 1 else ""
            return {"type": "html", "title": t, "html": text_to_html(body)}
        if fmt == "pdf":
            return {"type": "pdf", "title": p.stem, "url": "/api/reader/file?p=" + quote(str(p), safe="")}
        if fmt in ("cbz", "zip"):
            imgs = self._zip_images(p)
            if cid not in ("*", "", None):
                imgs = [n for n in imgs if str(PurePosixPath(n).parent) == cid]
            return {"type": "images", "pages": [local_url(str(p), n) for n in imgs]}
        if fmt == "folder":
            d = p if cid in ("*", "", None) else (p / cid)
            if self.allowed_path(str(d)) is None:
                raise RuntimeError("目录越界")
            return {"type": "images", "pages": [local_url(str(x)) for x in self._dir_images(d)]}
        raise RuntimeError("不支持的格式")

    def serve_local(self, raw, entry=""):
        """返回 (content_type, bytes) 或 None。"""
        p = self.allowed_path(raw)
        if p is None:
            return None
        if p.is_file() and p.suffix.lower() in IMG_EXTS and not entry:
            data = p.read_bytes()
            return _sniff_img(data), data
        if p.is_file() and p.suffix.lower() in (".epub", ".cbz", ".zip") and entry:
            with zipfile.ZipFile(p) as z:
                if entry == "@cover":
                    if p.suffix.lower() == ".epub":
                        entry = self._epub_open(p).get("cover") or ""
                    else:
                        ims = self._zip_images(p)
                        entry = ims[0] if ims else ""
                    if not entry:
                        return None
                if PurePosixPath(entry).suffix.lower() not in IMG_EXTS:
                    return None
                try:
                    data = z.read(entry)
                except KeyError:
                    return None
            return _sniff_img(data), data
        return None


    # ---------------------------------------------------------------- 分类 / 书廊 / 新源
    OL_STYLES = [
        ("romance", "恋爱言情", "💕"), ("fantasy", "奇幻魔法", "🐉"),
        ("science_fiction", "科幻", "🚀"), ("thriller", "惊悚悬疑", "🔪"),
        ("mystery", "推理探案", "🕵️"), ("horror", "恐怖", "👻"),
        ("adventure", "冒险", "🗺️"), ("historical_fiction", "历史小说", "🏛️"),
        ("poetry", "诗歌", "🪶"), ("philosophy", "哲学", "🧠"),
        ("biography", "传记", "👤"), ("humor", "幽默", "😄"),
        ("drama", "戏剧", "🎭"), ("short_stories", "短篇集", "📚"),
        ("comics_and_graphic_novels", "图像小说", "🗯️"), ("young_adult_fiction", "青春", "🌱"),
    ]

    def genres(self):
        d = RC.public_genres()
        try:
            subs = [{"id": sid, "name": name, "group": "风格馆 · 按题材直达", "en": sid, "icon": icon,
                     "blurb": "按题材跨源检索（维基文库 / Gutenberg / なろう / Archive），点开即站内阅读"}
                    for sid, name, icon, _kw in self.STYLES]
            d["subjects"] = subs
        except Exception:
            d["subjects"] = []
        return d

    def browse(self, kind: str, gid: str, lang: str = "zh", page: int = 0, want: int = 0, for_home: bool = False):
        kind = (kind or "").strip().lower()
        gid = (gid or "").strip()
        errors = {}
        meta = {"kind": kind, "id": gid, "title": gid, "group": "", "dedicated": True}
        items = []
        want = int(want or 0)
        try:
            rail_ids = {r["id"] for r in RC.HOME_RAILS} | {
                "md_popular", "md_latest", "md_completed", "se_popular", "se_new",
                "cn_classics", "pd_novels", "pd_comics",
            }
            if kind in ("style",):
                label = next((n for sid, n, _ic, _kw in self.STYLES if sid == gid), gid)
                items = self.style_search(gid, page)
                return items, {}, {"kind": "style", "id": gid, "title": label,
                                   "group": "风格馆", "dedicated": True, "page": int(page or 0)}
            if kind == "manga" or gid.startswith("md_") or (kind == "rail" and gid.startswith("md_")):
                items, meta, errors = self._browse_manga(gid, lang, page, want=want)
            elif RC.manga_by_id(gid) and kind not in ("novel", "book"):
                items, meta, errors = self._browse_manga(gid, lang, page, want=want)
            elif kind in ("novel", "book") or gid in rail_ids or RC.novel_by_id(gid):
                if gid.startswith("md_"):
                    items, meta, errors = self._browse_manga(gid, lang, page, want=want)
                else:
                    items, meta, errors = self._browse_novel_or_rail(gid, lang, page, want=want)
            else:
                raise RuntimeError("未知分类：%s/%s" % (kind, gid))
        except Exception as ex:
            errors["browse"] = str(ex)[:160]
        # Category first screen should not be the homepage rail recap.
        if (not for_home) and int(page or 0) == 0 and items and (self._home_sids or self._home_fps):
            fresh, seen = [], []
            for it in items:
                if item_sid(it) in self._home_sids or work_fingerprint(it) in self._home_fps:
                    seen.append(it)
                else:
                    fresh.append(it)
            items = list(fresh)
            meta["home_overlap_excluded"] = len(seen)
            if seen:
                meta["has_more"] = True
        meta["page"] = int(page or 0)
        meta["count"] = len(items)
        meta["dedicated"] = True
        return items, errors, meta

    def _browse_manga(self, gid, lang, page, want=0):
        limit = 48 if (want and want > 24) else 32
        if gid in ("md_popular", "popular", ""):
            # Pull a deep popular pool so cross-rail exclusivity can still fill 12 slots.
            pop_limit = 100 if (want and want >= 24) else limit
            items = self.md_search("", lang, 0, order="followedCount", wide=True, limit=pop_limit)
            if want and want >= 48:
                try:
                    items = (items or []) + (self.md_search("", lang, 1, order="followedCount", wide=True, limit=pop_limit) or [])
                except Exception:
                    pass
            items = dedupe_items(items)
            return items, {"kind": "manga", "id": "md_popular", "title": "热门漫画", "group": "书廊", "dedicated": True, "has_more": True}, {}
        if gid in ("md_latest", "latest"):
            items = self.md_search("", lang, page, order="latestUploadedChapter", wide=True, limit=max(limit, 50))
            items = dedupe_items(items)
            return items, {"kind": "manga", "id": "md_latest", "title": "新作漫画", "group": "书廊", "dedicated": True}, {}
        if gid in ("md_completed", "completed"):
            items = self.md_search("", lang, page, order="followedCount", wide=True, status="completed", limit=max(limit, 50))
            items = dedupe_items(items)
            return items, {"kind": "manga", "id": "md_completed", "title": "完结漫画", "group": "书廊", "dedicated": True}, {}
        rail_map = {
            "md_romance": "romance", "md_fantasy": "fantasy", "md_isekai": "isekai",
            "md_action": "action", "md_slice": "slice", "md_mystery": "mystery",
        }
        gid2 = rail_map.get(gid, gid)
        g = RC.manga_by_id(gid2)
        if not g:
            raise RuntimeError("未知漫画类型")
        # Category walls fetch several official tag pages so they are not the home rail's first 12.
        n_pages = 4 if int(page or 0) == 0 else 2
        src_page = 0 if int(page or 0) == 0 else (2 + (int(page) - 1) * 2)
        bags = []
        for p in range(src_page, src_page + n_pages):
            try:
                bags.append(self.md_search("", lang, p, tag=g.get("tag"), demographic=g.get("demo"),
                                           order="followedCount", wide=True, limit=limit) or [])
            except Exception:
                break
        items = dedupe_items([it for bag in bags for it in bag])
        meta = {
            "kind": "manga", "id": g["id"], "title": g["name"], "en": g.get("en") or "",
            "group": g.get("group") or "", "dedicated": True,
            "has_more": bool(bags and len(bags[-1]) >= max(8, limit // 3)),
        }
        return items, meta, {}

    def _browse_novel_or_rail(self, gid, lang, page, want=0):
        if gid in ("pd_comics",):
            items = dedupe_items(self._ia_pages(RC.IA_PD_COMICS, page, pages=2 if not want or want > 24 else 1, kind_hint="manga"))
            return items, {"kind": "novel", "id": "pd_comics", "title": "公有领域漫画", "group": "书廊", "dedicated": True}, {}
        if gid in ("pd_novels",):
            qq = 'mediatype:texts AND (collection:gutenberg OR creator:"Standard Ebooks")' + RC.IA_SAFE
            items = dedupe_items(self._ia_pages(qq, page, pages=2, kind_hint="book"))
            return items, {"kind": "novel", "id": "pd_novels", "title": "公有领域小说", "group": "书廊", "dedicated": True}, {}
        if gid in ("se_new",):
            items = dedupe_items(self.se_new_releases())
            return items, {"kind": "novel", "id": "se_new", "title": "精校新书", "group": "书廊", "dedicated": True}, {}
        if gid in ("se_popular", "stdbooks"):
            bags = []
            for p in range(int(page or 0), int(page or 0) + 3):
                try:
                    bags.append(self.se_catalog(page=p, sort="popular") or [])
                except Exception:
                    break
            items = dedupe_items([it for bag in bags for it in bag])
            return items, {"kind": "novel", "id": "stdbooks", "title": "精校英文名著", "group": "名著", "dedicated": True, "has_more": len(bags) >= 3}, {}
        g = RC.novel_by_id(gid)
        if gid == "cn_classics":
            g = RC.novel_by_id("chinese_classic")
        if not g:
            raise RuntimeError("未知小说类型")
        target = want if want else (36 if page else 80)
        items, errors, total = self.browse_novel(g, page, want=target)
        meta = {
            "kind": "novel", "id": g["id"], "title": g["name"], "group": g.get("group") or "",
            "blurb": g.get("blurb") or "", "sparse": bool(g.get("sparse")),
            "dedicated": True, "total": total,
            "has_more": (int(page or 0) * target + len(items)) < total,
        }
        return items, meta, errors

    def browse_novel(self, g, page=0, want=80):
        """Merge legal novel sources for one category; fail-soft per source. Dedupes editions of the same work."""
        errors, bags = {}, []
        want = max(12, min(int(want or 80), 120))
        # Home rails use want<=24 (one page per source, faster). Category pages go deeper.
        pages = 1 if want <= 24 else (2 if want < 60 else 3)
        jobs = []

        if g.get("se") == "popular":
            def _se():
                out = []
                for p in range(0, pages):
                    out.extend(self.se_catalog(page=p, sort="popular") or [])
                return out
            jobs.append(("stdbooks", _se))
        if g.get("se_query"):
            for p in range(0, min(pages, 3)):
                jobs.append(("stdbooks%s" % p, lambda p=p: self.se_search(g["se_query"], p)))
        if g.get("ia"):
            jobs.append(("archive", lambda: self._ia_pages(g["ia"], 0, pages=pages, kind_hint="book")))
        if g.get("ws_queries"):
            jobs.append(("wikisource", lambda: self.ws_direct(g["ws_queries"])))
        if g.get("gb_topic"):
            for p in range(0, min(pages, 3)):
                jobs.append(("gutenberg%s" % p, lambda p=p: self.gb_topic(g["gb_topic"], p)))
        if g.get("ol_subject"):
            for p in range(0, min(pages, 3)):
                jobs.append(("openlibrary%s" % p, lambda p=p: self.ol_subject(g["ol_subject"], p, limit=50)))

        # Use a *local* pool so we never nest submissions on self.pool (that deadlocks under home_rails).
        budget = 12 if want <= 24 else 20
        if not jobs:
            return [], errors, 0
        ex = ThreadPoolExecutor(max_workers=min(6, len(jobs)))
        try:
            futs = {ex.submit(fn): name for name, fn in jobs}
            done, _pend = wait(set(futs), timeout=budget)
            for f, name in futs.items():
                if f in done:
                    try:
                        bags.append(f.result() or [])
                    except Exception as err:
                        errors[name] = (str(err)[:160] or type(err).__name__)
                else:
                    errors[name] = "连接超时或源站无响应"
        finally:
            ex.shutdown(wait=False, cancel_futures=True)

        merged = []
        for bag in bags:
            merged.extend(bag or [])
        pool = dedupe_items(merged)
        if (g.get("id") == "chinese_classic") or ("古典" in (g.get("name") or "")):
            junk = re.compile(r"(strategy guide|walkthrough|攻略|超完全|同人|fanfic)", re.I)
            pool = [it for it in pool if not junk.search((it.get("title") or "") + " " + (it.get("desc") or ""))]
        offset = int(page or 0) * want
        return pool[offset:offset + want], errors, len(pool)

    def home_rails(self, lang: str = "zh"):
        futs = {}
        for spec in RC.HOME_RAILS:
            gid = spec.get("genre") or spec["id"]
            # Deep pool for popular/new/completed so exclusivity can still fill a row.
            if spec["id"] in ("md_popular", "md_latest", "md_completed"):
                want = 100
            elif spec.get("kind") == "novel" or spec["id"].startswith("n_") or spec["id"] in ("cn_classics", "se_popular", "se_new"):
                want = 24
            else:
                want = 32
            futs[self.pool.submit(self.browse, spec["kind"], gid, lang, 0, want, True)] = spec
        pending = set(futs)
        done, pending = wait(pending, timeout=28)
        if pending:
            done2, pending = wait(pending, timeout=16)
            done |= done2
        raw = []
        retry = []
        for f, spec in futs.items():
            entry = {"id": spec["id"], "title": spec["title"], "items": [], "errors": {}, "kind": spec.get("kind")}
            if f in done:
                try:
                    items, errors, meta = f.result(timeout=0)
                    entry["items"] = items or []
                    entry["errors"] = errors or {}
                    entry["title"] = spec["title"] or (meta or {}).get("title") or spec["title"]
                    entry["meta"] = meta or {}
                except Exception as ex:
                    entry["errors"] = {"rail": str(ex)[:160]}
            else:
                entry["errors"] = {"rail": "连接超时或源站无响应"}
            if not entry["items"]:
                retry.append((spec, entry))
            raw.append(entry)

        # Retry any blank rail once on a *local* pool — do not leave a whole novel section empty.
        if retry:
            def _retry(spec):
                gid = spec.get("genre") or spec["id"]
                return self.browse(spec["kind"], gid, lang, 0, 16, True)
            ex = ThreadPoolExecutor(max_workers=min(6, len(retry)))
            try:
                rf = {ex.submit(_retry, spec): entry for spec, entry in retry}
                d, _p = wait(set(rf), timeout=22)
                for f, entry in rf.items():
                    if f not in d:
                        continue
                    try:
                        items, errors, meta = f.result()
                        if items:
                            entry["items"] = items
                            entry["errors"] = errors or {}
                            entry["meta"] = meta or {}
                    except Exception as ex:
                        entry["errors"] = {"rail": str(ex)[:160]}
            finally:
                ex.shutdown(wait=False, cancel_futures=True)

        seen_sid, seen_fp = set(), set()
        rails = []
        for entry in raw:
            kept = []
            for it in dedupe_items(entry.get("items") or []):
                sid, fp = item_sid(it), work_fingerprint(it)
                if sid in seen_sid or fp in seen_fp:
                    continue
                seen_sid.add(sid)
                seen_fp.add(fp)
                kept.append(it)
                if len(kept) >= 12:
                    break
            raw_n = len(entry.get("items") or [])
            entry["items"] = kept
            entry["raw_before_exclusive"] = raw_n
            rails.append(entry)
        self._home_sids = set(seen_sid)
        self._home_fps = set(seen_fp)
        return {"rails": rails}


    def ws_direct(self, titles):
        """Build one Wikisource card per known public-domain title, no search (avoids 429 and edition floods)."""
        out = []
        seen = set()
        for t in titles or []:
            t = (t or "").strip()
            if not t:
                continue
            key = work_fingerprint({"title": t, "author": "", "id": t, "src": "wikisource"})
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "src": "wikisource", "id": t, "kind": "book",
                "title": t, "author": "",
                "cover": "",
                "desc": "维基文库 · 公有领域文本",
                "tags": ["维基文库"],
            })
        return out

    def ws_browse(self, queries, page=0):
        seen, out = set(), []
        for q in queries or []:
            try:
                for it in self.ws_search(q, page=0 if page == 0 else page):
                    if it["id"] in seen:
                        continue
                    seen.add(it["id"])
                    out.append(it)
            except Exception:
                continue
            if len(out) >= 80:
                break
        return dedupe_items(out)[:80]

    def gb_topic(self, topic, page=0):
        params = {"page": int(page) + 1, "topic": topic}
        j = self._memo(("gbt", topic, page), 1800, lambda: self._json("https://gutendex.com/books", params, timeout=12))
        return self._gb_items(j)

    def _gb_items(self, j):
        out = []
        for b in j.get("results") or []:
            fm = b.get("formats") or {}
            if not any(k.startswith("application/epub") for k in fm):
                continue
            cov = fm.get("image/jpeg") or ""
            out.append({
                "src": "gutenberg", "id": str(b.get("id")), "kind": "book",
                "title": b.get("title") or "", "cover": img_url(cov) if cov else "",
                "author": ", ".join(a.get("name", "") for a in (b.get("authors") or []))[:80],
                "desc": " / ".join((b.get("summaries") or [])[:1])[:900] or " · ".join((b.get("subjects") or [])[:4]),
                "tags": (b.get("languages") or []) + (b.get("bookshelves") or [])[:2],
            })
        return out

    # ---------------------------------------------------------------- Internet Archive (safe queries)
    _IA_BLOCK = re.compile(
        r"(z-library|zlibrary|\bzlib\b|anna-?archive|sci-?hub)", re.I)

    _IA_COMIC_BLOCK = re.compile(
        r"(spider[- ]?man|marvel comics|batman|superman|x-men|wonder woman|"
        r"dc comics|avengers|iron man|captain america|one piece|naruto|bleach|"
        r"dragon ball|harry potter|disney)",
        re.I,
    )

    def _ia_blocked(self, ident, title=""):
        ident = ident or ""
        blob = ident + " " + (title or "")
        if ident.lower().startswith("manga_"):
            return True
        if self._IA_BLOCK.search(blob) or self._IA_COMIC_BLOCK.search(blob):
            return True
        return False

    def _ia_item(self, d, kind_hint="scan"):
        ident = d.get("identifier")
        if not ident:
            return None
        title = d.get("title") if isinstance(d.get("title"), str) else ident
        if self._ia_blocked(ident, title):
            return None
        cr = d.get("creator") or ""
        if isinstance(cr, list):
            cr = ", ".join(cr[:2])
        ds = d.get("description") or ""
        if isinstance(ds, list):
            ds = " ".join(ds)
        kind = kind_hint if kind_hint in ("book", "manga", "scan") else "scan"
        return {
            "src": "archive", "id": ident, "kind": kind,
            "title": title, "author": (cr or "")[:80],
            "cover": img_url("https://archive.org/services/img/" + ident),
            "desc": re.sub(r"<[^>]+>", "", ds)[:600],
            "tags": [str(d.get("year") or "")] if d.get("year") else [],
        }

    def ia_query(self, qq: str, page=0, kind_hint="scan", rows=50):
        qq = (qq or "").strip() + ("" if "NOT collection:inlibrary" in (qq or "") else RC.IA_SAFE)
        rows = max(12, min(int(rows or 50), 100))
        j = self._memo(("iaq", qq, page, rows), 1800, lambda: self._json("https://archive.org/advancedsearch.php", {
            "q": qq, "fl[]": ["identifier", "title", "creator", "year", "description"],
            "rows": rows, "page": int(page) + 1, "output": "json", "sort[]": "downloads desc",
        }, timeout=18))
        out = []
        for d in (j.get("response") or {}).get("docs") or []:
            it = self._ia_item(d, kind_hint=kind_hint)
            if it:
                out.append(it)
        return out

    def _ia_pages(self, qq, page=0, pages=2, kind_hint="scan"):
        out = []
        start = max(0, int(page or 0))
        for p in range(start, start + max(1, int(pages or 1))):
            try:
                batch = self.ia_query(qq, p, kind_hint=kind_hint, rows=50) or []
            except Exception:
                break
            out.extend(batch)
            if not batch:
                break
        return out


    # ============================================================ Mangapill（热门漫画 · 站内直读）
    MP_BASE = "https://mangapill.com"

    def _mp_cards(self, html):
        out, seen = [], set()
        for m in re.finditer(
                r'href="(/manga/(\d+)/([^"]+))"[\s\S]{0,600}?(?:data-src|src)="([^"]+)"[^>]*alt="([^"]*)"', html):
            path, mid, slug, cover, alt = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
            if path in seen:
                continue
            seen.add(path)
            title = (alt or "").strip()
            if not title:
                title = slug.replace("-", " ").title()
            half = title[: len(title) // 2].strip()
            if half and title.startswith(half) and title.endswith(half):
                title = half
            if cover.startswith("//"):
                cover = "https:" + cover
            out.append({
                "src": "mangapill", "id": path[len("/manga/"):], "sid": "mp_" + mid,
                "title": title, "author": "Mangapill", "cover": cover, "desc": "",
                "lang": "en", "tags": ["漫画"], "status": "", "year": "",
                "kind": "manga", "badge": "热门漫画",
            })
        return out

    def mp_search(self, q, page=0):
        q = (q or "").strip()
        params = {"q": q, "type": "manga", "status": ""}
        if page:
            params["page"] = int(page) + 1
        r = self._get(self.MP_BASE + "/search", params=params, timeout=14,
                      headers={"Referer": self.MP_BASE + "/"})
        if r.status_code != 200:
            raise RuntimeError("Mangapill HTTP %s" % r.status_code)
        items = self._mp_cards(r.text)
        if q:
            low = q.lower()
            hit = [x for x in items if low in (x["title"] or "").lower()]
            items = hit or items
        return items

    def mp_detail(self, bid):
        bid = str(bid or "").lstrip("/")
        url = self.MP_BASE + "/manga/" + bid
        r = self._get(url, timeout=14, headers={"Referer": self.MP_BASE + "/"})
        if r.status_code != 200:
            raise RuntimeError("Mangapill HTTP %s" % r.status_code)
        html = r.text
        title = ""
        m = re.search(r"<h1[^>]*>([^<]+)</h1>", html)
        if m:
            title = m.group(1).strip()
        cover = ""
        m = re.search(r'<img[^>]+(?:data-src|src)="(https://[^"]+)"[^>]*class="[^"]*object-cover', html)
        if m:
            cover = m.group(1)
        desc = ""
        m = re.search(r'<p[^>]*class="[^"]*whitespace-pre-wrap[^"]*"[^>]*>([\s\S]{0,1200}?)</p>', html)
        if m:
            desc = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        chs, seen = [], set()
        for m in re.finditer(r'href="(/chapters/[^"]+)"', html):
            path = m.group(1)
            if path in seen:
                continue
            seen.add(path)
            slug = path.rsplit("/", 1)[-1]
            mm = re.search(r"chapter-([0-9.]+)", slug)
            label = ("第 %s 话" % mm.group(1)) if mm else slug.replace("-", " ")[-40:]
            chs.append({"id": path[len("/chapters/"):], "title": label})
        chs.reverse()
        return {
            "src": "mangapill", "id": bid, "title": title or bid, "author": "Mangapill",
            "cover": cover, "desc": desc or "Mangapill 在线漫画（图片经本地代理缓存，全站内直读）",
            "tags": ["漫画"], "status": "", "year": "", "lang": "en", "kind": "manga",
            "chapters": chs,
        }

    def mp_pages(self, cid):
        cid = str(cid or "").lstrip("/")
        url = self.MP_BASE + "/chapters/" + cid
        r = self._get(url, timeout=20, headers={"Referer": self.MP_BASE + "/"})
        if r.status_code != 200:
            raise RuntimeError("Mangapill 章节 HTTP %s" % r.status_code)
        pages, seen = [], set()
        for m in re.finditer(r'<img[^>]+(?:data-src|src)="(https://[^"]+?\.(?:jpg|jpeg|png|webp)[^"]*)"', r.text, re.I):
            u = m.group(1)
            if "readdetectiveconan" not in u and "mangapill" not in u:
                continue
            if u in seen:
                continue
            seen.add(u)
            pages.append(u)
        if not pages:
            raise RuntimeError("这一话没有解析到图片（可能已下架）")
        return pages

    # ============================================================ 小説家になろう（日轻 · 站内直读）
    SY_API = "https://api.syosetu.com/novelapi/api/"
    SY_BASE = "https://ncode.syosetu.com"
    SY_GENRE = {1: "恋爱", 2: "奇幻", 3: "科幻", 4: "恐怖", 99: "其他", 98: "其他",
                101: "异世界", 102: "恋爱", 201: "奇幻", 202: "科幻"}

    def sy_search(self, q, page=0):
        q = (q or "").strip()
        params = {"out": "json", "lim": 20, "order": "hyoka"}
        if q:
            params["word"] = q
        if page:
            params["st"] = int(page) * 20 + 1
        r = self._get(self.SY_API, params=params, timeout=14)
        j = r.json()
        out = []
        for it in (j[1:] if isinstance(j, list) else []):
            ncode = str(it.get("ncode") or "").upper()
            if not ncode:
                continue
            out.append({
                "src": "syosetu", "id": ncode, "sid": "sy_" + ncode,
                "title": str(it.get("title") or ncode),
                "author": str(it.get("writer") or "なろう作者"),
                "cover": "", "lang": "ja",
                "tags": [self.SY_GENRE.get(it.get("genre"), "轻小说")],
                "status": "连载" if it.get("end") == 0 else "完结",
                "year": "", "kind": "book", "badge": "日轻小说",
                "desc": re.sub(r"<[^>]+>", "", str(it.get("story") or ""))[:400],
            })
        return out

    def sy_detail(self, ncode):
        ncode = str(ncode or "").lower()
        r = self._get(self.SY_API, params={"out": "json", "ncode": ncode}, timeout=14)
        j = r.json()
        info = (j[1] if isinstance(j, list) and len(j) > 1 else {}) or {}
        total = int(info.get("general_all_no") or 1)
        chs = [{"id": str(i), "title": "第 %d 话" % i} for i in range(1, total + 1)]
        return {
            "src": "syosetu", "id": ncode, "title": str(info.get("title") or ncode),
            "author": str(info.get("writer") or ""), "cover": "",
            "desc": re.sub(r"<[^>]+>", "", str(info.get("story") or "")),
            "tags": [self.SY_GENRE.get(info.get("genre"), "轻小说")],
            "status": "", "year": "", "lang": "ja", "kind": "book",
            "chapters": chs or [{"id": "1", "title": "第 1 话"}],
        }

    def sy_read(self, ncode, no):
        url = "%s/%s/%s/" % (self.SY_BASE, str(ncode or "").lower(), int(no or 1))
        r = self._get(url, timeout=16)
        if r.status_code != 200:
            raise RuntimeError("なろう HTTP %s" % r.status_code)
        html = r.text
        i = html.find('js-novel-text')
        if i > 0:
            j = html.find('<div class="p-novel__', i + 10)
            k = html.find('<!--', i)
            ends = [x for x in (j, k) if x > i]
            body = html[html.rfind("<div", 0, i):(min(ends) if ends else i + 400000)]
        else:
            body = html
        body = re.sub(r"<ruby>[\s\S]*?</ruby>", lambda mm: re.sub(r"<[^>]+>", "", mm.group(0)), body)
        return {"type": "html", "title": "%s 第 %s 话" % (str(ncode).upper(), no),
                "html": sanitize_html(body)}



    # ============================================================ 风格馆（题材 → 多源组合检索）
    STYLES = [
        ("wuxia", "武侠江湖", "🗡️", ["武俠", "江湖", "劍俠"]),
        ("romance", "恋爱言情", "💕", ["愛情", "言情", "戀愛"]),
        ("fantasy", "奇幻魔法", "🐉", ["奇幻", "魔法", "神魔"]),
        ("mystery", "悬疑推理", "🕵️", ["推理", "偵探", "懸疑"]),
        ("horror", "恐怖惊悚", "👻", ["恐怖", "靈異", "鬼"]),
        ("history", "历史传奇", "🏛️", ["史記", "資治通鑑", "歷史"]),
        ("classic_novel", "章回小说", "📖", ["章回小說", "演義", "話本"]),
        ("poetry", "诗词歌赋", "🪶", ["唐詩", "宋詞", "詩經"]),
        ("philosophy", "诸子百家", "🧠", ["論語", "莊子", "諸子"]),
        ("scifi", "科幻", "🚀", ["科幻", "science fiction"]),
        ("humor", "轻松搞笑", "😄", ["幽默", "笑話", "喜劇"]),
        ("adult_fantasy", "异世界", "🌀", ["異世界", "転生", "穿越"]),
    ]

    def style_search(self, style, page=0, budget=5.0):
        """风格 ID 或中文关键词 → 多源并发组合检索（总预算 7s，慢源自动放弃，保证一定出结果）。"""
        kw = None
        for sid, _name, _icon, kws in self.STYLES:
            if sid == style:
                kw = kws
                break
        if kw is None:
            kw = [str(style or "").strip()] if str(style or "").strip() else ["热门"]
        jobs = []
        for word in kw[:3]:
            jobs.append(lambda w=word: self.ws_search(w, page))
            jobs.append(lambda w=word: self.gb_search(w, "all", page))
            jobs.append(lambda w=word: self.sy_search(w, page))
        futs = [self.pool.submit(fn) for fn in jobs]
        deadline = time.time() + float(budget or 7.0)
        bag, seen = [], set()
        for f in futs:
            left = deadline - time.time()
            if left <= 0.2:
                break
            try:
                rows = f.result(timeout=left) or []
            except Exception:
                continue
            for it in rows[:12]:
                _t = it.get("title") or ""
                if re.search(r"(法院|判決|判决|台上字|台上字第|司法院|年度.*字)", _t):
                    continue
                key = (it.get("src"), _t[:24])
                if key in seen:
                    continue
                seen.add(key)
                bag.append(it)
        return bag

    # ============================================================ OpenLibrary 主题馆（按风格找书 · 站内直读）
    def ol_subject(self, subject, page=0, want=40):
        subject = str(subject or "").strip()
        if not subject:
            return []
        limit = max(12, min(60, int(want or 40)))
        params = {
            "q": "subject:%s" % subject,
            "limit": limit,
            "offset": max(0, int(page or 0)) * limit,
            "has_fulltext": "true",
            "fields": "key,title,author_name,ia,public_scan_b,ebook_access,cover_i,first_publish_year,subject",
        }
        j = self._memo(("olsub", subject, page, limit), 900,
                       lambda: self._json("https://openlibrary.org/search.json", params, timeout=16))
        out = []
        for d in (j.get("docs") or []):
            ias = d.get("ia") or []
            if not ias:
                continue                     # 没有扫描件就不进书城，保证点开一定能读
            ident = str(ias[0])
            cover = ("https://covers.openlibrary.org/b/id/%s-L.jpg" % d["cover_i"]) if d.get("cover_i") else ""
            subj = [str(x) for x in (d.get("subject") or [])][:6]
            out.append({
                "src": "archive", "id": ident, "sid": "ia_" + ident,
                "title": str(d.get("title") or ident),
                "author": ", ".join(str(a) for a in (d.get("author_name") or [])[:2]) or "佚名",
                "cover": cover, "desc": " · ".join(subj[:4]),
                "lang": "all", "tags": subj[:4] or [subject],
                "status": "有扫描件" if d.get("public_scan_b") else "可借阅",
                "year": str(d.get("first_publish_year") or ""),
                "kind": "book", "badge": "风格馆",
            })
        return out

    # ---------------------------------------------------------------- Open Library → IA-readable public works
    def ol_search(self, q, page=0):
        q = (q or "").strip()
        if not q:
            return []
        params = {
            "q": q, "limit": 50, "offset": max(0, int(page)) * 50,
            "has_fulltext": "true",
            "fields": "key,title,author_name,ia,public_scan_b,ebook_access,cover_i,first_publish_year",
        }
        j = self._memo(("ols", q, page), 1800, lambda: self._json("https://openlibrary.org/search.json", params, timeout=14))
        return self._ol_items(j)

    def ol_subject(self, subject, page=0, limit=50):
        limit = max(12, min(int(limit or 50), 100))
        params = {
            "q": "subject:" + subject, "limit": limit, "offset": max(0, int(page)) * limit,
            "has_fulltext": "true",
            "fields": "key,title,author_name,ia,public_scan_b,ebook_access,cover_i,first_publish_year",
        }
        j = self._memo(("olsub", subject, page, limit), 1800, lambda: self._json("https://openlibrary.org/search.json", params, timeout=14))
        return self._ol_items(j, cap=limit)

    def _ol_items(self, j, cap=80):
        out, seen = [], set()
        for d in j.get("docs") or []:
            access = (d.get("ebook_access") or "")
            if access not in ("public", "borrowable", ""):
                # only keep public scans when possible; skip no-ebook
                if not d.get("public_scan_b") and access not in ("public",):
                    continue
            if access == "borrowable" and not d.get("public_scan_b"):
                continue
            ias = d.get("ia") or []
            if not ias:
                continue
            ident = None
            for cand in ias:
                if cand and not self._ia_blocked(cand, d.get("title") or ""):
                    ident = cand
                    break
            if not ident or ident in seen:
                continue
            # prefer public_scan
            if d.get("public_scan_b") is False and access != "public":
                continue
            seen.add(ident)
            authors = d.get("author_name") or []
            cover = img_url("https://archive.org/services/img/" + ident)
            out.append({
                "src": "archive", "id": ident, "kind": "scan",
                "title": d.get("title") or ident,
                "author": ", ".join(authors[:2])[:80],
                "cover": cover,
                "desc": "Open Library 公有领域 / 可在线阅读 · " + ident,
                "tags": ["Open Library"] + ([str(d.get("first_publish_year"))] if d.get("first_publish_year") else []),
            })
            if len(out) >= cap:
                break
        return out

    # ---------------------------------------------------------------- Standard Ebooks (official HTML catalog + Atom new-releases; OPDS is 401)
    SE_BASE = "https://standardebooks.org"

    def se_catalog(self, page=0, sort="popular", query=""):
        params = {"page": int(page) + 1, "sort": sort or "popular"}
        if query:
            params["query"] = query
        url = self.SE_BASE + "/ebooks"
        html = self._memo(("sehtml", sort, query, page), 1800, lambda: self._se_get(url, params))
        return self._se_parse_list(html)

    def se_search(self, q, page=0):
        q = (q or "").strip()
        if not q:
            return self.se_catalog(page=page, sort="popular")
        items = self.se_catalog(page=page, sort="popular", query=q)
        ql = q.lower()
        hit = [it for it in items if ql in (it.get("title") or "").lower() or ql in (it.get("author") or "").lower()]
        return hit

    def se_new_releases(self):
        raw = self._memo(("seatom",), 1800, lambda: self._se_get(self.SE_BASE + "/feeds/atom/new-releases", None, accept="application/atom+xml"))
        return self._se_parse_atom(raw)

    def _se_get(self, url, params=None, accept="text/html,application/xhtml+xml,application/atom+xml"):
        r = self._get(url, params=params, timeout=16, headers={"Accept": accept, "Referer": self.SE_BASE + "/"})
        if r.status_code >= 400:
            raise RuntimeError("Standard Ebooks HTTP %s" % r.status_code)
        r.encoding = "utf-8"
        return r.text or ""

    def _se_parse_list(self, html):
        out, seen = [], set()
        # Official catalog cards: <li typeof="schema:Book" about="/ebooks/...">
        for m in re.finditer(r'<li[^>]*about="(/ebooks/[^"]+)"[^>]*>([\s\S]*?)</li>', html or "", re.I):
            path = m.group(1).rstrip("/")
            block = m.group(2)
            bid = path[len("/ebooks/"):]
            if not bid or bid in seen:
                continue
            title = ""
            tm = re.search(r'property="schema:name"[^>]*>([^<]+)', block) or re.search(r'<a[^>]+href="/ebooks/[^"]+"[^>]*>([^<]+)</a>', block)
            if tm:
                title = _html.unescape(tm.group(1)).strip()
            author = ""
            am = re.search(r'property="schema:author"[^>]*>([\s\S]*?)</', block)
            if am:
                author = re.sub(r"<[^>]+>", "", am.group(1)).strip()
            cover = ""
            cm = re.search(r'srcset="([^"]+?cover\.jpg)[^\"]*"', block) or re.search(r'src="(/images/covers/[^"]+?cover\.jpg)"', block)
            if cm:
                src = cm.group(1).split(",")[0].strip().split(" ")[0]
                if src.startswith("/"):
                    src = self.SE_BASE + src
                cover = img_url(src)
            seen.add(bid)
            out.append({
                "src": "stdbooks", "id": bid, "kind": "book",
                "title": title or bid.replace("-", " ").replace("/", " · "),
                "author": author, "cover": cover,
                "desc": "Standard Ebooks 精校公有领域文本",
                "tags": ["Standard Ebooks"],
            })
        return out

    def _se_parse_atom(self, raw):
        out, seen = [], set()
        for m in re.finditer(r"<entry>([\s\S]*?)</entry>", raw or ""):
            ent = m.group(1)
            im = re.search(r"<id>(https://standardebooks.org/ebooks/[^<]+)</id>", ent)
            if not im:
                continue
            bid = im.group(1).split("/ebooks/", 1)[-1].rstrip("/")
            if not bid or bid in seen:
                continue
            tm = re.search(r"<title>([^<]+)</title>", ent)
            am = re.search(r"<author>[\s\S]*?<name>([^<]+)</name>", ent)
            sm = re.search(r"<summary[^>]*>([^<]+)</summary>", ent)
            cover = ""
            cm = re.search(r'rel="http://opds-spec.org/image"[^>]*href="([^"]+)"', ent) or re.search(r'<link[^>]+type="image/jpeg"[^>]+href="([^"]+)"', ent)
            if cm:
                href = cm.group(1)
                if href.startswith("/"):
                    href = self.SE_BASE + href
                cover = img_url(href)
            seen.add(bid)
            out.append({
                "src": "stdbooks", "id": bid, "kind": "book",
                "title": _html.unescape(tm.group(1) if tm else bid),
                "author": _html.unescape(am.group(1) if am else ""),
                "cover": cover,
                "desc": _html.unescape(sm.group(1) if sm else "Standard Ebooks 新书"),
                "tags": ["Standard Ebooks"],
            })
        return out

    def se_fetch(self, bid: str):
        bid = (bid or "").lstrip("/")
        if bid.startswith("ebooks/"):
            bid = bid[len("ebooks/"):]
        bid = bid.strip("/")
        if not bid or ".." in bid or not re.match(r"^[a-z0-9\-/]+$", bid):
            raise RuntimeError("无效的 Standard Ebooks 标识")
        slug = bid.replace("/", "_")
        dst = self.books_dir / ("se_%s.epub" % slug[:120])
        if dst.is_file() and dst.stat().st_size > 2048:
            return dst
        urls = [
            "%s/ebooks/%s/downloads/%s.epub" % (self.SE_BASE, bid, slug),
            "%s/ebooks/%s/download?download-type=epub" % (self.SE_BASE, bid),
            "%s/ebooks/%s/download?format=epub" % (self.SE_BASE, bid),
        ]
        # Try to discover a real .epub href on the official book page
        try:
            page = self._se_get(self.SE_BASE + "/ebooks/" + bid)
            for hm in re.finditer(r'href="([^"]+\.epub[^"]*)"', page, re.I):
                href = hm.group(1)
                if href.startswith("/"):
                    href = self.SE_BASE + href
                if href.startswith("http") and href not in urls:
                    urls.insert(0, href)
        except Exception:
            pass
        last = None
        for u in urls:
            try:
                r = self._get(u, timeout=60, headers={"Referer": self.SE_BASE + "/ebooks/" + bid, "Accept": "application/epub+zip,*/*"})
                if r.status_code == 200 and r.content[:2] == b"PK" and len(r.content) > 2048:
                    tmp = dst.with_suffix(".part")
                    tmp.write_bytes(r.content)
                    tmp.replace(dst)
                    return dst
                last = RuntimeError("HTTP %s" % r.status_code)
            except Exception as ex:
                last = ex
        raise RuntimeError("Standard Ebooks EPUB 下载失败：%s" % last)

    def se_detail(self, bid: str):
        p = self.se_fetch(bid)
        info = self.local_detail(str(p))
        info.update({"src": "stdbooks", "id": bid})
        return info
    # ---------------------------------------------------------------- 统一入口
    def detail(self, src, bid, lang="zh"):
        key = ("detail", src, bid, lang)
        if src == "mangadex":
            return self._memo(key, 600, lambda: self.md_detail(bid, lang))
        if src == "wikisource":
            return self.ws_detail(bid)
        if src == "gutenberg":
            return self.gb_detail(bid)
        if src == "archive":
            return self._memo(key, 3600, lambda: self.ia_detail(bid))
        if src == "local":
            return self.local_detail(bid)
        if src in ("stdbooks", "standardebooks"):
            return self.se_detail(bid)
        if src == "mangapill":
            return self._memo(key, 600, lambda: self.mp_detail(bid))
        if src == "syosetu":
            return self._memo(key, 600, lambda: self.sy_detail(bid))
        raise RuntimeError("未知来源：%s" % src)

    def chapter(self, src, bid, cid, quality="data"):
        if src == "mangadex":
            if not cid:
                raise RuntimeError("这一部暂时没有可阅读的章节（可换一个语言或稍后再试）")
            return {"type": "images", "pages": self._memo(("mdp", cid, quality), 600, lambda: self.md_pages(cid, quality))}
        if src == "wikisource":
            return self.ws_chapter(cid)
        if src == "gutenberg":
            return self.local_chapter(str(self.gb_fetch(bid)), cid)
        if src == "archive":
            return {"type": "images", "pages": self.ia_pages(bid, quality)}
        if src == "local":
            return self.local_chapter(bid, cid)
        if src in ("stdbooks", "standardebooks"):
            return self.local_chapter(str(self.se_fetch(bid)), cid)
        if src == "mangapill":
            if not cid:
                raise RuntimeError("这一部暂时没有可阅读的章节")
            return {"type": "images", "pages": self._memo(("mpp", cid), 600, lambda: self.mp_pages(cid))}
        if src == "syosetu":
            return self.sy_read(bid, cid or "1")
        raise RuntimeError("未知来源：%s" % src)

    # ---------------------------------------------------------------- 图片代理 + 磁盘缓存
    def fetch_image(self, u: str):
        if not is_allowed_img_host(u):
            return None
        h = hashlib.sha1(u.encode("utf-8")).hexdigest()
        fp = self.img_dir / h[:2] / h
        if fp.is_file():
            try:
                data = fp.read_bytes()
                return _sniff_img(data), data
            except Exception:
                pass
        ref = None
        if "readdetectiveconan.com" in u or "mangapill" in u:
            ref = "https://mangapill.com/"
        elif "mangadex" in u:
            ref = "https://mangadex.org/"
        elif "standardebooks.org" in u:
            ref = "https://standardebooks.org/"
        elif "archive.org" in u:
            ref = "https://archive.org/"
        r = self._get(u, timeout=30, headers={"Referer": ref} if ref else None)
        if r.status_code != 200 or not r.content or len(r.content) > 40 * 1024 * 1024:
            return None
        data = r.content
        ctype = r.headers.get("Content-Type", "")
        if not ctype.startswith("image/"):
            ctype = _sniff_img(data)
        try:
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_bytes(data)
            self._img_writes += 1
            if self._img_writes % 200 == 0:
                threading.Thread(target=self.prune_images, daemon=True).start()
        except Exception:
            pass
        return ctype, data

    def prune_images(self, max_bytes=1536 * 1024 * 1024):
        try:
            files = [(f.stat().st_atime, f.stat().st_size, f) for f in self.img_dir.rglob("*") if f.is_file()]
            total = sum(s for _, s, _ in files)
            for _, s, f in sorted(files):
                if total <= max_bytes:
                    break
                try:
                    f.unlink()
                    total -= s
                except Exception:
                    pass
        except Exception:
            pass

    def cache_stats(self):
        n, total = 0, 0
        for f in self.img_dir.rglob("*"):
            if f.is_file():
                n += 1
                total += f.stat().st_size
        return {"files": n, "bytes": total}

    def clear_cache(self):
        import shutil
        shutil.rmtree(self.img_dir, ignore_errors=True)
        self.img_dir.mkdir(parents=True, exist_ok=True)
        with self.lock:
            self._mem.clear()

    # ---------------------------------------------------------------- 离线下载（漫画章节 → CBZ）
    def offline(self, src, bid, cid, title, quality="data"):
        jid = hashlib.md5(("%s|%s|%s" % (src, bid, cid)).encode()).hexdigest()[:10]
        with self.lock:
            if self.jobs.get(jid, {}).get("state") == "running":
                return jid
            self.jobs[jid] = {"id": jid, "title": title, "state": "running", "done": 0, "total": 0, "file": ""}

        def run():
            job = self.jobs[jid]
            try:
                ch = self.chapter(src, bid, cid, quality)
                if ch.get("type") != "images":
                    raise RuntimeError("仅漫画章节支持离线打包")
                pages = ch["pages"]
                job["total"] = len(pages)
                safe = re.sub(r'[\\/:*?"<>|]+', "_", title)[:120] or jid
                out = self.books_dir / "离线漫画" / (safe + ".cbz")
                out.parent.mkdir(parents=True, exist_ok=True)
                tmp = out.with_suffix(".part")
                with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED) as z:
                    for i, pu in enumerate(pages):
                        u = unquote(pu.split("u=", 1)[1]) if pu.startswith("/api/reader/img") else ""
                        res = self.fetch_image(u) if u else None
                        if res:
                            ext = {"image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}.get(res[0], ".jpg")
                            z.writestr("%04d%s" % (i + 1, ext), res[1])
                        job["done"] = i + 1
                tmp.replace(out)
                job.update({"state": "done", "file": str(out)})
                self._scan_cache = (0.0, [])
            except Exception as ex:
                job.update({"state": "error", "error": str(ex)[:200]})
        threading.Thread(target=run, daemon=True).start()
        return jid

    # ---------------------------------------------------------------- 书架 / 进度 / 偏好
    def _shelf_load(self):
        try:
            d = json.loads(self.shelf_file.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                d.setdefault("items", {})
                d.setdefault("prefs", {})
                d.setdefault("stats", {})
                return d
        except Exception:
            pass
        return {"items": {}, "prefs": {}, "stats": {}}

    def _shelf_save(self, d):
        tmp = self.shelf_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.shelf_file)

    def shelf_get(self):
        with self.lock:
            return self._shelf_load()

    def shelf_put(self, item: dict):
        src, bid = str(item.get("src") or ""), str(item.get("id") or "")
        if not src or not bid:
            raise RuntimeError("缺少书目标识")
        key = src + "::" + bid
        allowed = ("src", "id", "title", "author", "cover", "kind", "chap_id", "chap_title",
                   "chap_idx", "chap_total", "pos", "page", "fav", "read_type")
        with self.lock:
            d = self._shelf_load()
            cur = d["items"].get(key, {})
            for k in allowed:
                if k in item:
                    cur[k] = item[k]
            cur["updated"] = time.time()
            d["items"][key] = cur
            self._shelf_save(d)
        return key

    def shelf_del(self, key: str):
        with self.lock:
            d = self._shelf_load()
            d["items"].pop(key, None)
            self._shelf_save(d)

    def prefs_save(self, prefs: dict):
        with self.lock:
            d = self._shelf_load()
            if isinstance(prefs, dict):
                d["prefs"].update({k: v for k, v in prefs.items() if isinstance(k, str) and len(k) < 40})
            self._shelf_save(d)
            return d["prefs"]

    def stats_add(self, seconds: int):
        day = time.strftime("%Y-%m-%d")
        with self.lock:
            d = self._shelf_load()
            st = d["stats"]
            st[day] = int(st.get(day, 0)) + max(0, min(int(seconds or 0), 3600))
            for k in sorted(st)[:-120]:
                st.pop(k, None)
            self._shelf_save(d)
            return st
