# -*- coding: utf-8 -*-
"""DownloadStack Control · 内置短剧剧场（软件内自有页面）。

只使用正规官方平台的公开元数据，以及可在同一页面合法嵌入的官方播放器
（YouTube / Bilibili 官方 embed）。
严禁拉出官方站点的新操作系统窗口，不调用系统浏览器，
不接入未授权聚合源，不缓存、不破解、不绕过受 DRM / VIP 保护的正片流。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urlparse
from urllib.request import Request, urlopen

APP_DIR = Path(__file__).resolve().parent
STATE_DIR = APP_DIR / "state"
STATE_FILE = STATE_DIR / "drama_hub.json"
PROFILE_DIR = APP_DIR / "cache" / "drama_profile"
LOG_FILE = APP_DIR / "logs" / "drama-hub.log"
MAX_HISTORY = 80
MAX_FAVORITES = 80

# 仅这几个平台提供同一页面内的官方 embed。其余平台只进自有展厅。
EMBED_IDS = {"bilibili", "youtube"}

# 封面只允许这些官方 CDN，避免把任意 URL 塞进页面。
COVER_HOSTS = (
    "hdslb.com", "hdslb.net", "ytimg.com", "youtube.com",
    "ggpht.com", "googleusercontent.com",
)

PLATFORMS = [
    {
        "id": "hongguo",
        "name": "红果短剧",
        "vendor": "抖音集团",
        "official": True,
        "featured": True,
        "color": "#ff3d71",
        "tag": "主源 · 官方免费短剧",
        "home": "https://hongguoduanju.com/",
        "search": "https://hongguoduanju.com/search?keyword={q}",
        "hosts": ("hongguoduanju.com",),
        "blurb": "抖音集团官方短剧平台。进站后即可用官方搜索、分类和推荐，支持登录后在软件内观看。",
        "channels": [
            {"name": "官方首页", "url": "https://hongguoduanju.com/", "note": "官方推荐与热门"},
            {"name": "热播榜", "url": "https://hongguoduanju.com/rank/hot-drama", "note": "官方热度排行"},
            {"name": "短剧分类", "url": "https://hongguoduanju.com/category", "note": "按题材浏览"},
        ],
    },
    {
        "id": "douyin",
        "name": "抖音",
        "vendor": "抖音集团",
        "official": True,
        "featured": True,
        "color": "#00e5ff",
        "tag": "官方短视频 / 短剧",
        "home": "https://www.douyin.com/",
        "search": "https://www.douyin.com/search/{q}",
        "hosts": ("douyin.com", "iesdouyin.com"),
        "blurb": "进入抖音官方网页，用站内搜索和推荐找短剧。",
        "channels": [
            {"name": "官方首页", "url": "https://www.douyin.com/", "note": "官方推荐"},
        ],
    },
    {
        "id": "kuaishou",
        "name": "快手",
        "vendor": "快手",
        "official": True,
        "featured": True,
        "color": "#ff4d2e",
        "tag": "官方短视频 / 短剧",
        "home": "https://www.kuaishou.com/",
        "search": "https://www.kuaishou.com/search/video?searchKey={q}",
        "hosts": ("kuaishou.com",),
        "blurb": "进入快手官方网页，搜索热门短剧与系列内容。",
        "channels": [
            {"name": "官方首页", "url": "https://www.kuaishou.com/", "note": "官方推荐"},
        ],
    },
    {
        "id": "tencent",
        "name": "腾讯视频",
        "vendor": "腾讯",
        "official": True,
        "featured": True,
        "color": "#ff8a00",
        "tag": "微短剧 / 正片",
        "home": "https://v.qq.com/",
        "search": "https://v.qq.com/x/search/?q={q}",
        "hosts": ("v.qq.com", "film.qq.com", "video.qq.com"),
        "blurb": "进入腾讯视频官方站，用站内搜索和频道看微短剧与正片。",
        "channels": [
            {"name": "官方首页", "url": "https://v.qq.com/", "note": "官方推荐"},
        ],
    },
    {
        "id": "iqiyi",
        "name": "爱奇艺",
        "vendor": "爱奇艺",
        "official": True,
        "featured": True,
        "color": "#00f5b8",
        "tag": "微剧 / 热播",
        "home": "https://www.iqiyi.com/",
        "search": "https://so.iqiyi.com/so/q_{q}",
        "hosts": ("iqiyi.com", "iqiyi.cn"),
        "blurb": "进入爱奇艺官方站，可浏览微剧频道或搜索热播剧集。",
        "channels": [
            {"name": "官方首页", "url": "https://www.iqiyi.com/", "note": "官方推荐"},
            {"name": "微剧频道", "url": "https://www.iqiyi.com/microdrama/", "note": "官方微剧"},
        ],
    },
    {
        "id": "mgtv",
        "name": "芒果TV",
        "vendor": "芒果超媒",
        "official": True,
        "featured": False,
        "color": "#ffd000",
        "tag": "官方影视 / 短剧",
        "home": "https://www.mgtv.com/",
        "search": "https://so.mgtv.com/so?k={q}",
        "hosts": ("mgtv.com",),
        "blurb": "进入芒果TV 官方网页，使用站内搜索与分类。",
        "channels": [
            {"name": "官方首页", "url": "https://www.mgtv.com/", "note": "官方推荐"},
        ],
    },
    {
        "id": "youku",
        "name": "优酷",
        "vendor": "阿里巴巴",
        "official": True,
        "featured": False,
        "color": "#38bdf8",
        "tag": "官方影视 / 短剧",
        "home": "https://www.youku.com/",
        "search": "https://so.youku.com/search_video/q_{q}",
        "hosts": ("youku.com", "youku.com.cn"),
        "blurb": "进入优酷官方网页，使用站内搜索与分类。",
        "channels": [
            {"name": "官方首页", "url": "https://www.youku.com/", "note": "官方推荐"},
        ],
    },
    {
        "id": "ixigua",
        "name": "西瓜视频",
        "vendor": "抖音集团",
        "official": True,
        "featured": False,
        "color": "#7bdc00",
        "tag": "官方视频",
        "home": "https://www.ixigua.com/",
        "search": "https://www.ixigua.com/search/{q}",
        "hosts": ("ixigua.com",),
        "blurb": "进入西瓜视频官方网页检索。",
        "channels": [
            {"name": "官方首页", "url": "https://www.ixigua.com/", "note": "官方推荐"},
        ],
    },
    {
        "id": "bilibili",
        "name": "哔哩哔哩",
        "vendor": "哔哩哔哩",
        "official": True,
        "featured": False,
        "color": "#fb7299",
        "tag": "官方内容",
        "home": "https://www.bilibili.com/",
        "search": "https://search.bilibili.com/all?keyword={q}",
        "hosts": ("bilibili.com", "b23.tv"),
        "blurb": "进入 B 站官方搜索短剧、影视与相关投稿。",
        "channels": [
            {"name": "官方首页", "url": "https://www.bilibili.com/", "note": "官方推荐"},
            {"name": "放映厅", "url": "https://www.bilibili.com/movie/", "note": "官方影视"},
        ],
    },
    {
        "id": "migu",
        "name": "咪咕视频",
        "vendor": "中国移动",
        "official": True,
        "featured": False,
        "color": "#a78bfa",
        "tag": "官方影视",
        "home": "https://www.miguvideo.com/",
        "search": "https://www.miguvideo.com/mgs/website/prd/search.html?keywords={q}",
        "hosts": ("miguvideo.com", "migu.cn"),
        "blurb": "进入咪咕视频官方网页检索。",
        "channels": [
            {"name": "官方首页", "url": "https://www.miguvideo.com/", "note": "官方推荐"},
        ],
    },

    {
        "id": "sohu",
        "name": "搜狐视频",
        "vendor": "搜狐",
        "official": True,
        "featured": True,
        "color": "#ff6a00",
        "tag": "官方影视 / 短剧",
        "home": "https://tv.sohu.com/",
        "search": "https://so.tv.sohu.com/s?wd={q}",
        "hosts": ("sohu.com",),
        "blurb": "进入搜狐视频官方站，使用站内搜索和分类。",
        "channels": [
            {"name": "官方首页", "url": "https://tv.sohu.com/", "note": "官方推荐"},
        ],
    },
    {
        "id": "m1905",
        "name": "1905电影网",
        "vendor": "电影频道",
        "official": True,
        "featured": True,
        "color": "#e11d2e",
        "tag": "官方电影",
        "home": "https://www.1905.com/",
        "search": "https://www.1905.com/search/?q={q}",
        "hosts": ("1905.com",),
        "blurb": "电影频道官方网站，浏览与检索官方影视内容。",
        "channels": [
            {"name": "官方首页", "url": "https://www.1905.com/", "note": "官方推荐"},
        ],
    },
    {
        "id": "yangshipin",
        "name": "央视频",
        "vendor": "中央广播电视总台",
        "official": True,
        "featured": True,
        "color": "#c81e1e",
        "tag": "总台官方",
        "home": "https://www.yangshipin.cn/",
        "search": "https://www.yangshipin.cn/",
        "hosts": ("yangshipin.cn",),
        "blurb": "中央广播电视总台官方视频平台。",
        "channels": [
            {"name": "官方首页", "url": "https://www.yangshipin.cn/", "note": "官方推荐"},
        ],
    },
    {
        "id": "cctv",
        "name": "央视网",
        "vendor": "中央广播电视总台",
        "official": True,
        "featured": False,
        "color": "#d32f2f",
        "tag": "官方视听",
        "home": "https://tv.cctv.com/",
        "search": "https://search.cctv.com/search.php?qtext={q}",
        "hosts": ("cctv.com", "cntv.cn"),
        "blurb": "进入央视网官方视听首页。",
        "channels": [
            {"name": "官方首页", "url": "https://tv.cctv.com/", "note": "官方推荐"},
        ],
    },
    {
        "id": "haokan",
        "name": "好看视频",
        "vendor": "百度",
        "official": True,
        "featured": True,
        "color": "#3b82f6",
        "tag": "官方短视频",
        "home": "https://haokan.baidu.com/",
        "search": "https://haokan.baidu.com/web/search/page?query={q}",
        "hosts": ("haokan.baidu.com",),
        "blurb": "百度官方视频平台，可用站内搜索浏览短视频与剧集相关内容。",
        "channels": [
            {"name": "官方首页", "url": "https://haokan.baidu.com/", "note": "官方推荐"},
        ],
    },
    {
        "id": "acfun",
        "name": "AcFun",
        "vendor": "快手",
        "official": True,
        "featured": False,
        "color": "#fd4c5c",
        "tag": "官方弹幕视频",
        "home": "https://www.acfun.cn/",
        "search": "https://www.acfun.cn/search?keyword={q}",
        "hosts": ("acfun.cn",),
        "blurb": "进入 AcFun 官方站检索与观看。",
        "channels": [
            {"name": "官方首页", "url": "https://www.acfun.cn/", "note": "官方推荐"},
        ],
    },
    {
        "id": "toutiao",
        "name": "今日头条",
        "vendor": "抖音集团",
        "official": True,
        "featured": False,
        "color": "#f43f5e",
        "tag": "官方资讯 / 视频",
        "home": "https://www.toutiao.com/",
        "search": "https://www.toutiao.com/search/?keyword={q}",
        "hosts": ("toutiao.com",),
        "blurb": "进入今日头条官方网页检索视频与资讯。",
        "channels": [
            {"name": "官方首页", "url": "https://www.toutiao.com/", "note": "官方推荐"},
        ],
    },
    {
        "id": "xiaohongshu",
        "name": "小红书",
        "vendor": "行吟信息",
        "official": True,
        "featured": True,
        "color": "#ff2442",
        "tag": "官方社区 / 视频",
        "home": "https://www.xiaohongshu.com/explore",
        "search": "https://www.xiaohongshu.com/search_result?keyword={q}",
        "hosts": ("xiaohongshu.com",),
        "blurb": "进入小红书官方网页，浏览与搜索视频内容。",
        "channels": [
            {"name": "发现", "url": "https://www.xiaohongshu.com/explore", "note": "官方推荐"},
        ],
    },
    {
        "id": "weibo",
        "name": "微博视频",
        "vendor": "微博",
        "official": True,
        "featured": False,
        "color": "#ff8200",
        "tag": "官方视频",
        "home": "https://weibo.com/tv",
        "search": "https://s.weibo.com/weibo?q={q}",
        "hosts": ("weibo.com", "weibo.cn", "sina.com.cn"),
        "blurb": "进入微博官方视频页，使用站内搜索。",
        "channels": [
            {"name": "微博视频", "url": "https://weibo.com/tv", "note": "官方视频"},
            {"name": "微博首页", "url": "https://weibo.com/", "note": "官方首页"},
        ],
    },
    {
        "id": "weishi",
        "name": "腾讯微视",
        "vendor": "腾讯",
        "official": True,
        "featured": False,
        "color": "#ff6b00",
        "tag": "官方短视频",
        "home": "https://weishi.qq.com/",
        "search": "https://weishi.qq.com/",
        "hosts": ("weishi.qq.com",),
        "blurb": "进入腾讯微视官方网页。",
        "channels": [
            {"name": "官方首页", "url": "https://weishi.qq.com/", "note": "官方推荐"},
        ],
    },
    {
        "id": "ifeng",
        "name": "凤凰视频",
        "vendor": "凤凰网",
        "official": True,
        "featured": False,
        "color": "#f5c518",
        "tag": "官方视听",
        "home": "https://v.ifeng.com/",
        "search": "https://so.ifeng.com/video?q={q}",
        "hosts": ("ifeng.com",),
        "blurb": "进入凤凰网官方视频频道。",
        "channels": [
            {"name": "官方首页", "url": "https://v.ifeng.com/", "note": "官方推荐"},
        ],
    },
    {
        "id": "sina",
        "name": "新浪视频",
        "vendor": "新浪",
        "official": True,
        "featured": False,
        "color": "#e6162d",
        "tag": "官方视频",
        "home": "https://video.sina.com.cn/",
        "search": "https://search.sina.com.cn/?q={q}&c=video",
        "hosts": ("sina.com.cn",),
        "blurb": "进入新浪官方视频频道。",
        "channels": [
            {"name": "官方首页", "url": "https://video.sina.com.cn/", "note": "官方推荐"},
        ],
    },
    {
        "id": "funshion",
        "name": "风行网",
        "vendor": "风行在线",
        "official": True,
        "featured": False,
        "color": "#00b3ff",
        "tag": "官方影视",
        "home": "https://www.fun.tv/",
        "search": "https://www.fun.tv/search/?q={q}",
        "hosts": ("fun.tv",),
        "blurb": "进入风行网官方影视首页。",
        "channels": [
            {"name": "官方首页", "url": "https://www.fun.tv/", "note": "官方推荐"},
        ],
    },
    {
        "id": "letv",
        "name": "乐视视频",
        "vendor": "乐视",
        "official": True,
        "featured": False,
        "color": "#e31c23",
        "tag": "官方影视",
        "home": "https://www.le.com/",
        "search": "https://so.le.com/s?wd={q}",
        "hosts": ("le.com",),
        "blurb": "进入乐视官方视频网站。",
        "channels": [
            {"name": "官方首页", "url": "https://www.le.com/", "note": "官方推荐"},
        ],
    },
    {
        "id": "zhihu",
        "name": "知乎",
        "vendor": "知乎",
        "official": True,
        "featured": False,
        "color": "#0066ff",
        "tag": "官方视频 / 讨论",
        "home": "https://www.zhihu.com/zvideo",
        "search": "https://www.zhihu.com/search?type=video&q={q}",
        "hosts": ("zhihu.com",),
        "blurb": "进入知乎官方视频区检索。",
        "channels": [
            {"name": "知乎视频", "url": "https://www.zhihu.com/zvideo", "note": "官方视频"},
        ],
    },
    {
        "id": "youtube",
        "name": "YouTube",
        "vendor": "Google",
        "official": True,
        "featured": False,
        "color": "#ff0000",
        "tag": "官方国际视频",
        "home": "https://www.youtube.com/",
        "search": "https://www.youtube.com/results?search_query={q}",
        "hosts": ("youtube.com", "youtu.be", "youtube-nocookie.com"),
        "blurb": "进入 YouTube 官方网站检索与观看。",
        "channels": [
            {"name": "官方首页", "url": "https://www.youtube.com/", "note": "官方推荐"},
        ],
    },
    {
        "id": "wasu",
        "name": "华数TV",
        "vendor": "华数传媒",
        "official": True,
        "featured": False,
        "color": "#00a0e9",
        "tag": "官方广电",
        "home": "https://www.wasu.cn/",
        "search": "https://www.wasu.cn/Search/show/k/{q}",
        "hosts": ("wasu.cn",),
        "blurb": "进入华数TV官方网站。",
        "channels": [
            {"name": "官方首页", "url": "https://www.wasu.cn/", "note": "官方推荐"},
        ],
    },
    {
        "id": "neteasetv",
        "name": "网易视频",
        "vendor": "网易",
        "official": True,
        "featured": False,
        "color": "#c00",
        "tag": "官方视频",
        "home": "https://v.163.com/",
        "search": "https://www.163.com/search?keyword={q}",
        "hosts": ("v.163.com",),
        "blurb": "进入网易官方视频频道。",
        "channels": [
            {"name": "官方首页", "url": "https://v.163.com/", "note": "官方推荐"},
        ],
    },
    {
        "id": "huanxi",
        "name": "欢喜首映",
        "vendor": "欢喜传媒",
        "official": True,
        "featured": False,
        "color": "#8b5cf6",
        "tag": "官方影视",
        "home": "https://www.huanxi.com/",
        "search": "https://www.huanxi.com/",
        "hosts": ("huanxi.com",),
        "blurb": "进入欢喜首映官方网站。",
        "channels": [
            {"name": "官方首页", "url": "https://www.huanxi.com/", "note": "官方推荐"},
        ],
    },
    {
        "id": "pptv",
        "name": "PPTV",
        "vendor": "苏宁",
        "official": True,
        "featured": False,
        "color": "#1aa260",
        "tag": "官方影视",
        "home": "https://www.pptv.com/",
        "search": "https://www.pptv.com/",
        "hosts": ("pptv.com",),
        "blurb": "进入 PPTV 官方网站。",
        "channels": [
            {"name": "官方首页", "url": "https://www.pptv.com/", "note": "官方推荐"},
        ],
    },
    {
        "id": "iq",
        "name": "iQIYI 国际站",
        "vendor": "爱奇艺",
        "official": True,
        "featured": False,
        "color": "#1ce783",
        "tag": "官方国际站",
        "home": "https://www.iq.com/",
        "search": "https://www.iq.com/search?query={q}",
        "hosts": ("iq.com",),
        "blurb": "进入爱奇艺国际站官方网页。",
        "channels": [
            {"name": "官方首页", "url": "https://www.iq.com/", "note": "官方推荐"},
        ],
    },

]


GENRES = [
    "热播短剧", "甜宠", "逆袭", "战神", "重生", "穿越",
    "都市", "古装", "玄幻", "职场", "萌宝", "搞笑",
    "家庭", "年代", "悬疑", "系统流",
]

# 题材展厅（软件内编辑的分类入口，不是伪造的平台剧目列表）
THEMES = [
    {"id": "hot", "name": "热播短剧", "query": "短剧", "summary": "热门短剧题材，适合先从这里逛起。"},
    {"id": "romance", "name": "甜宠", "query": "甜宠 短剧", "summary": "甜宠、恋爱线题材。"},
    {"id": "rise", "name": "逆袭", "query": "逆袭 短剧", "summary": "逆袭、翻盘题材。"},
    {"id": "war", "name": "战神", "query": "战神 短剧", "summary": "战神、强者回归题材。"},
    {"id": "rebirth", "name": "重生", "query": "重生 短剧", "summary": "重生、重来一次题材。"},
    {"id": "travel", "name": "穿越", "query": "穿越 短剧", "summary": "穿越、时空题材。"},
    {"id": "urban", "name": "都市", "query": "都市 短剧", "summary": "都市情感与现实线。"},
    {"id": "ancient", "name": "古装", "query": "古装 短剧", "summary": "古装、权谋与侠义题材。"},
    {"id": "fantasy", "name": "玄幻", "query": "玄幻 短剧", "summary": "玄幻、修仙题材。"},
    {"id": "work", "name": "职场", "query": "职场 短剧", "summary": "职场与商战题材。"},
    {"id": "baby", "name": "萌宝", "query": "萌宝 短剧", "summary": "萌宝、家庭线题材。"},
    {"id": "funny", "name": "搞笑", "query": "搞笑 短剧", "summary": "轻松搞笑短剧。"},
    {"id": "family", "name": "家庭", "query": "家庭 短剧", "summary": "家庭伦理与亲情线。"},
    {"id": "period", "name": "年代", "query": "年代 短剧", "summary": "年代、民国与怀旧题材。"},
    {"id": "mystery", "name": "悬疑", "query": "悬疑 短剧", "summary": "悬疑、反转题材。"},
    {"id": "system", "name": "系统流", "query": "系统 短剧", "summary": "系统流、金手指题材。"},
]

SPOTLIGHT = [
    {"title": "红果主源展厅", "subtitle": "官方频道 · 软件内浏览", "platform": "hongguo", "channel": "热播榜", "color": "#ff3d71"},
    {"title": "甜宠题材", "subtitle": "题材分支 · 软件内展厅", "platform": "hongguo", "channel": "甜宠", "color": "#fb7185"},
    {"title": "战神 / 逆袭", "subtitle": "热门题材 · 软件内展厅", "platform": "hongguo", "channel": "战神", "color": "#f43f5e"},
    {"title": "爱奇艺微剧厅", "subtitle": "官方频道展厅 · 不外开网页", "platform": "iqiyi", "channel": "微剧频道", "color": "#00f5b8"},
    {"title": "腾讯视频厅", "subtitle": "官方频道展厅 · 不外开网页", "platform": "tencent", "channel": "", "color": "#ff8a00"},
    {"title": "B站可看", "subtitle": "官方检索 + 页内嵌入播放", "platform": "bilibili", "channel": "短剧", "color": "#fb7299"},
    {"title": "YouTube 嵌入", "subtitle": "粘贴官方链接即可页内播放", "platform": "youtube", "channel": "", "color": "#ff0000"},
    {"title": "快手展厅", "subtitle": "官方频道 · 软件内浏览", "platform": "kuaishou", "channel": "", "color": "#ff4d2e"},
    {"title": "抖音展厅", "subtitle": "官方频道 · 软件内浏览", "platform": "douyin", "channel": "", "color": "#00e5ff"},
    {"title": "芒果TV 展厅", "subtitle": "官方频道 · 软件内浏览", "platform": "mgtv", "channel": "", "color": "#ffd000"},
    {"title": "央视频展厅", "subtitle": "总台官方频道 · 软件内浏览", "platform": "yangshipin", "channel": "", "color": "#c81e1e"},
    {"title": "搜狐视频厅", "subtitle": "官方频道 · 软件内浏览", "platform": "sohu", "channel": "", "color": "#ff6a00"},
]


def _log(msg):
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + str(msg) + "\n")
    except Exception:
        pass


def _empty_state():
    return {"history": [], "favorites": [], "last_platform": "hongguo", "updated": 0}


def _load_state():
    try:
        if STATE_FILE.is_file():
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("history", [])
                data.setdefault("favorites", [])
                data.setdefault("last_platform", "hongguo")
                return data
    except Exception:
        pass
    return _empty_state()


def _save_state(data):
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _platform_by_id(pid):
    for p in PLATFORMS:
        if p["id"] == pid:
            return p
    return None


def _allowed_hosts():
    hosts = set()
    for p in PLATFORMS:
        for h in p["hosts"]:
            hosts.add(h.lower())
    return hosts


def _host_allowed(host, extra=()):
    host = (host or "").lower().strip().strip(".")
    if not host:
        return False
    allowed = set(_allowed_hosts())
    allowed.update(h.lower() for h in extra)
    for h in allowed:
        if host == h or host.endswith("." + h):
            return True
    return False


def sanitize_url(raw):
    """只允许 https 官方域名，拒绝 javascript / file / 任意跳转。"""
    url = str(raw or "").strip()
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    if not re.match(r"^https://", url, re.I):
        return ""
    try:
        u = urlparse(url)
    except Exception:
        return ""
    if (u.scheme or "").lower() != "https":
        return ""
    if not _host_allowed(u.hostname or ""):
        return ""
    if u.username or u.password:
        return ""
    if len(url) > 2000:
        return ""
    if (u.path or "").lower().endswith("error.html"):
        return ""
    return url


def sanitize_cover(raw):
    url = str(raw or "").strip()
    if url.startswith("//"):
        url = "https:" + url
    if not re.match(r"^https://", url, re.I):
        return ""
    try:
        u = urlparse(url)
    except Exception:
        return ""
    if (u.scheme or "").lower() != "https":
        return ""
    if not _host_allowed(u.hostname or "", extra=COVER_HOSTS):
        return ""
    if u.username or u.password or len(url) > 2000:
        return ""
    return url


def sanitize_embed(raw, platform_id=""):
    """只放行官方 embed 地址，禁止任意第三方播放器。"""
    url = sanitize_url(raw)
    if not url:
        return ""
    u = urlparse(url)
    host = (u.hostname or "").lower()
    path = u.path or ""
    if platform_id == "youtube" or host.endswith("youtube.com") or host.endswith("youtube-nocookie.com"):
        m = re.search(r"/embed/([A-Za-z0-9_-]{11})\b", path)
        if not m:
            return ""
        vid = m.group(1)
        return "https://www.youtube-nocookie.com/embed/%s?rel=0&modestbranding=1&playsinline=1" % vid
    if platform_id == "bilibili" or host.endswith("bilibili.com") or host.endswith("b23.tv"):
        if host == "player.bilibili.com" or host.endswith(".bilibili.com") or host == "www.bilibili.com":
            qs = parse_qs(u.query or "")
            bvid = (qs.get("bvid") or [""])[0]
            aid = (qs.get("aid") or [""])[0]
            if not bvid:
                m = re.search(r"(BV[0-9A-Za-z]+)", path + "&" + (u.query or ""))
                if m:
                    bvid = m.group(1)
            if bvid and re.match(r"^BV[0-9A-Za-z]+$", bvid):
                return "https://player.bilibili.com/player.html?bvid=%s&high_quality=1&danmaku=0&autoplay=0" % quote(bvid, safe="")
            if aid and str(aid).isdigit():
                return "https://player.bilibili.com/player.html?aid=%s&high_quality=1&danmaku=0&autoplay=0" % aid
        return ""
    return ""


def _playback_of(pid):
    return "embed" if pid in EMBED_IDS else "hall"


def _public_blurb(p):
    if p["id"] in EMBED_IDS:
        return "在本软件自有剧场里检索，并用官方嵌入播放器观看，不会另开系统窗口。"
    return "进入软件内官方频道展厅，浏览公开元数据与题材。该平台正片受官方 DRM 保护，软件内不解码、不外开网页。"


def platforms_public():
    out = []
    keys = ("id", "name", "vendor", "official", "featured", "color", "tag", "home", "channels")
    for p in PLATFORMS:
        item = {k: p[k] for k in keys if k in p}
        item["blurb"] = _public_blurb(p)
        item["playback"] = _playback_of(p["id"])
        item["home"] = p.get("home") or ""
        returnable_channels = []
        for ch in p.get("channels") or []:
            returnable_channels.append({
                "name": ch.get("name") or "频道",
                "note": ch.get("note") or "",
            })
        item["channels"] = returnable_channels
        out.append(item)
    return out


def _theme_by_name(name):
    name = (name or "").strip()
    if not name:
        return None
    for t in THEMES:
        if t["name"] == name or t["id"] == name:
            return t
    for t in THEMES:
        if t["name"] in name or name in t["name"]:
            return t
    return None


def _item_key(entry):
    return str(entry.get("item_id") or entry.get("url") or "").strip()


def _touch_list(items, entry, limit):
    key = _item_key(entry)
    items = [x for x in items if _item_key(x) != key]
    items.insert(0, entry)
    return items[:limit]


def record_history(entry):
    st = _load_state()
    item_id = str(entry.get("item_id") or "").strip()
    url = sanitize_url(entry.get("url") or "")
    if not item_id and not url:
        return st
    platform_id = str(entry.get("platform") or "").strip()
    rec = {
        "item_id": item_id or url,
        "url": url,
        "title": str(entry.get("title") or "")[:120],
        "platform": platform_id,
        "query": str(entry.get("query") or "")[:80],
        "kind": str(entry.get("kind") or "hall")[:20],
        "cover": sanitize_cover(entry.get("cover") or ""),
        "ts": int(time.time()),
    }
    st["history"] = _touch_list(st["history"], rec, MAX_HISTORY)
    if platform_id:
        st["last_platform"] = platform_id
    st["updated"] = int(time.time())
    _save_state(st)
    return st


def toggle_favorite(entry):
    st = _load_state()
    item_id = str(entry.get("item_id") or "").strip()
    url = sanitize_url(entry.get("url") or "")
    key = item_id or url
    if not key:
        return st, False
    existed = any(_item_key(x) == key for x in st["favorites"])
    if existed:
        st["favorites"] = [x for x in st["favorites"] if _item_key(x) != key]
        on = False
    else:
        rec = {
            "item_id": key,
            "url": url,
            "title": str(entry.get("title") or "")[:120],
            "platform": str(entry.get("platform") or ""),
            "kind": str(entry.get("kind") or "hall")[:20],
            "cover": sanitize_cover(entry.get("cover") or ""),
            "ts": int(time.time()),
        }
        st["favorites"] = _touch_list(st["favorites"], rec, MAX_FAVORITES)
        on = True
    st["updated"] = int(time.time())
    _save_state(st)
    return st, on


# ---------- official metadata: Bilibili / YouTube URL ----------

_WBI_CACHE = {"mixin": "", "ts": 0}
_WBI_MIXIN_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 21, 56, 34, 51, 25, 52, 22, 62, 44, 63, 4, 6, 0, 1, 30, 57, 59,
    36, 64, 20, 60, 11,
]


def _http_json(url, timeout=7, referer="https://www.bilibili.com/", headers=None):
    req = Request(url, headers={
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Referer": referer,
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        **((headers or {})),
    })
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8", "replace"))


def _http_text(url, timeout=16, referer=None, encoding=None):
    """抓 HTML 文本（红果 SEO 页用）；失败返回空串，不抛异常。"""
    try:
        req = Request(url, headers={
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/131.0.0.0 Safari/537.36"),
            "Referer": referer or url,
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        return raw.decode(encoding or "utf-8", "replace")
    except Exception as ex:
        _log("http_text failed %s: %s" % (str(url)[:90], ex))
        return ""


def _wbi_mixin():
    now = time.time()
    if _WBI_CACHE["mixin"] and now - _WBI_CACHE["ts"] < 3600:
        return _WBI_CACHE["mixin"]
    try:
        data = _http_json("https://api.bilibili.com/x/web-interface/nav")
        wbi = ((data.get("data") or {}).get("wbi_img") or {})
        img = Path(urlparse(wbi.get("img_url") or "").path).stem
        sub = Path(urlparse(wbi.get("sub_url") or "").path).stem
        orig = img + sub
        mixed = "".join(orig[i] for i in _WBI_MIXIN_TAB if i < len(orig))[:32]
        if mixed:
            _WBI_CACHE["mixin"] = mixed
            _WBI_CACHE["ts"] = now
            return mixed
    except Exception as ex:
        _log("wbi mixin failed: %s" % ex)
    return _WBI_CACHE.get("mixin") or ""


def _wbi_sign(params):
    params = dict(params or {})
    params["wts"] = int(time.time())
    mixin = _wbi_mixin()
    clean = {}
    for k, v in params.items():
        clean[k] = re.sub(r"[!'()*]", "", str(v))
    query = urlencode(sorted(clean.items()))
    if mixin:
        clean["w_rid"] = hashlib.md5((query + mixin).encode("utf-8")).hexdigest()
    return clean


def _bili_item(raw, kind="video"):
    if not isinstance(raw, dict):
        return None
    title = re.sub(r"<[^>]+>", "", str(raw.get("title") or raw.get("org_title") or "")).strip()
    bvid = str(raw.get("bvid") or "").strip()
    aid = raw.get("aid") or raw.get("id") or ""
    if not bvid:
        m = re.search(r"(BV[0-9A-Za-z]+)", str(raw.get("arcurl") or raw.get("uri") or ""))
        if m:
            bvid = m.group(1)
    embed = ""
    if bvid and re.match(r"^BV[0-9A-Za-z]+$", bvid):
        embed = sanitize_embed("https://player.bilibili.com/player.html?bvid=%s" % bvid, "bilibili")
        item_id = "bili:" + bvid
        url = "https://www.bilibili.com/video/%s" % bvid
    elif str(aid).isdigit():
        embed = sanitize_embed("https://player.bilibili.com/player.html?aid=%s" % aid, "bilibili")
        item_id = "bili:av%s" % aid
        url = "https://www.bilibili.com/video/av%s" % aid
    else:
        return None
    if not embed:
        return None
    author = ""
    if isinstance(raw.get("author"), str):
        author = raw["author"]
    elif isinstance(raw.get("owner"), dict):
        author = str(raw["owner"].get("name") or "")
    cover = sanitize_cover(raw.get("pic") or raw.get("cover") or "")
    desc = re.sub(r"<[^>]+>", "", str(raw.get("description") or raw.get("desc") or "")).strip()
    return {
        "item_id": item_id,
        "title": (title or "B站内容")[:120],
        "platform": "bilibili",
        "kind": "embed",
        "playback": "embed",
        "subtitle": (author or "哔哩哔哩官方嵌入")[:80],
        "summary": desc[:180],
        "cover": cover,
        "embed": embed,
        "url": url,
        "aspect": "16:9",
        "source": "bilibili",
    }



# ============================================================ 短剧总库（B站正版可看 · 题材聚合 · 站内播放）
LIB_GENRES = [
    {"id": "tianchong", "name": "甜宠", "kws": ["短剧 甜宠 合集", "甜宠短剧 全集"]},
    {"id": "nixi", "name": "逆袭", "kws": ["短剧 逆袭 合集", "逆袭短剧 全集"]},
    {"id": "zhanshen", "name": "战神", "kws": ["短剧 战神 合集", "战神短剧 全集"]},
    {"id": "fuchou", "name": "复仇", "kws": ["短剧 复仇 合集", "复仇短剧 全集"]},
    {"id": "chuanyue", "name": "穿越", "kws": ["短剧 穿越 合集", "穿越短剧 全集"]},
    {"id": "guzhuang", "name": "古装", "kws": ["古装短剧 合集", "短剧 古装 全集"]},
    {"id": "xuanyi", "name": "悬疑", "kws": ["短剧 悬疑 合集", "悬疑短剧 全集"]},
    {"id": "zhichang", "name": "职场", "kws": ["短剧 职场 合集", "职场短剧 全集"]},
    {"id": "jiating", "name": "家庭", "kws": ["短剧 家庭 合集", "家庭短剧 全集"]},
    {"id": "xiaoyuan", "name": "校园", "kws": ["短剧 校园 合集", "校园短剧 全集"]},
    {"id": "mengbao", "name": "萌宝", "kws": ["短剧 萌宝 合集", "萌宝短剧 全集"]},
    {"id": "shenyi", "name": "神医", "kws": ["短剧 神医 合集", "神医短剧 全集"]},
    {"id": "dushi", "name": "都市", "kws": ["都市短剧 合集", "短剧 都市 全集"]},
    {"id": "yulequan", "name": "娱乐圈", "kws": ["短剧 娱乐圈 合集"]},
]

_LIB_CACHE = {}
_LIB_TTL = 900
_LIB_BAD_WORDS = ("解说", "花絮", "预告", "混剪", "盘点", "排行", "榜单", "吐槽", "剪辑",
                  "reaction", "剪辑版", "预告片", "片花")


def _lib_duration_sec(txt):
    """'1:23:45' / '45:12' → 秒"""
    try:
        parts = [int(x) for x in str(txt or "").split(":") if str(x).strip().isdigit()]
    except Exception:
        return 0
    if not parts:
        return 0
    sec = 0
    for p in parts:
        sec = sec * 60 + p
    return sec


def _lib_clean(it, genre_name):
    """过滤掉解说/预告/碎片，只留像正片合集的条目"""
    title = str(it.get("title") or "")
    if not title:
        return False
    low = title.lower()
    if any(w in title or w.lower() in low for w in _LIB_BAD_WORDS):
        return False
    sec = _lib_duration_sec(it.get("duration"))
    looks_full = any(k in title for k in ("全集", "合集", "全剧", "完整版", "一口气", "正片", "第1集", "第一集", "全"))
    if sec and sec < 300 and not looks_full:
        return False
    if not sec and not looks_full:
        return False
    it["genre"] = genre_name
    return True



# ============================================================ 红果官方剧库（SEO 页直抓，零签名）
HG_BASE = "https://hongguoduanju.com"
HG_CATS = [
    ("real-drama", "真人短剧"), ("comic-drama", "漫剧"), ("ai-drama", "AI 短剧"), ("comic", "漫画"),
]
HG_RANKS = [
    ("hot-drama", "全站热播"), ("hot-real-drama", "真人热播"), ("hot-comic-drama", "漫剧热播"),
    ("hot-ai-drama", "AI 热播"), ("new-drama", "新剧榜"),
    ("must-watch-drama", "必看榜"), ("followed-drama", "追剧榜"),
]
_HG_CACHE = {}
_HG_TTL = 600


def _hg_get(path, timeout=16):
    r = _http_text(HG_BASE + path, timeout=timeout, referer=HG_BASE + "/")
    return r or ""


def _hg_cards(html, limit=60):
    """解析 SEO 页里的剧目卡（红果用 <a class="pc-card" href="/detail?series_id=..."> 结构）：
    series_id / 标题 / 集数 / 标签 / 封面。"""
    out, seen = [], set()
    html = html or ""
    marks = [(m.start(), m.group(1)) for m in re.finditer(r'href="/detail\?series_id=(\d+)"', html)]
    for idx, (pos, sid) in enumerate(marks):
        if sid in seen:
            continue
        seen.add(sid)
        endp = marks[idx + 1][0] if idx + 1 < len(marks) else min(len(html), pos + 3000)
        block = html[pos:endp]
        # 标题：img alt 优先，其次 aria-label / title
        title = ""
        for pat in (r'<img[^>]+alt="([^"]{2,60})"', r'aria-label="([^"]{2,60})"', r'title="([^"]{2,60})"'):
            mt = re.search(pat, block)
            if mt:
                title = mt.group(1).strip()
                break
        if not title:
            txt = re.sub(r"<[^>]+>", "", block)
            txt = re.sub(r"\s+", " ", txt).strip()
            mt = re.search(r"全\s*\d+\s*集\s*([^ ]{2,40})", txt)
            title = (mt.group(1) if mt else txt[:24]) or ("红果 " + sid)
        # 集数
        eps = ""
        me = re.search(r"全\s*(\d+)\s*集", re.sub(r"<[^>]+>", " ", block))
        if me:
            eps = "全%s集" % me.group(1)
        # 标签
        tags = [re.sub(r'\s+', '', t) for t in re.findall(r'pc-tag-text[^>]*>([^<]{2,8})<', block)][:3]
        # 封面：srcSet / src
        cover = ""
        mc = re.search(r'srcSet="(https://[^"]+)"', block) or re.search(r'src="(https://[^"]+)"', block)
        if mc:
            cover = mc.group(1).split(" ")[0]
        out.append({"series_id": sid, "title": title, "eps": eps, "tags": tags,
                    "cover": cover, "platform": "hongguo", "item_id": "hg:%s" % sid})
        if len(out) >= limit:
            break
    return out



# ============================================================ 红果整库索引（本地 JSON，秒开）
HG_INDEX_FILE = None


def _hg_index_path():
    return STATE_DIR.parent / "cache" / "drama_hg_index.json"


def _hg_index_load():
    p = _hg_index_path()
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def hongguo_build_index(max_pages=40, cats=None):
    """整库爬取：3 类 × 最多 max_pages 页，去重后写入本地索引。返回统计。"""
    cats = cats or [k for k, _n in HG_CATS if k != "comic"]
    all_items, seen, stat = [], set(), {}
    for key in cats:
        got = 0
        for page in range(0, int(max_pages)):
            try:
                items, more = hongguo_lib("category", key, page, limit=60)
            except Exception:
                break
            if not items:
                break
            new = 0
            for it in items:
                sid = it.get("series_id")
                if not sid or sid in seen:
                    continue
                seen.add(sid)
                it["cat"] = it.get("cat") or dict(HG_CATS).get(key, key)
                all_items.append(it)
                new += 1
                got += 1
            if new == 0:
                break
        stat[key] = got
    payload = {"ts": time.time(), "total": len(all_items),
               "cats": [{"id": k, "name": n} for k, n in HG_CATS],
               "items": all_items}
    try:
        p = _hg_index_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)
    except Exception as ex:
        _log("hg index write failed: %s" % ex)
    return {"total": len(all_items), "per_cat": stat, "file": str(_hg_index_path())}


def hongguo_index_items():
    d = _hg_index_load()
    return d.get("items") or []


def hongguo_index_search(q, limit=60):
    q = (q or "").strip().lower()
    if not q:
        return []
    out = []
    for it in hongguo_index_items():
        t = (it.get("title") or "").lower()
        if q in t or all(ch in t for ch in q.split()):
            out.append({**it, "source": "红果", "item_id": "hg:%s" % it.get("series_id")})
            if len(out) >= limit:
                break
    return out


def hongguo_lib(kind="category", key="real-drama", page=0, limit=60):
    """kind=category|rank；page 从 0 开始（红果分页参数 ?page=N，1 基）"""
    key = key or ("real-drama" if kind == "category" else "hot-drama")
    page = max(0, int(page or 0))
    ck = ("hg", kind, key, page)
    now = time.time()
    hit = _HG_CACHE.get(ck)
    if hit and now - hit[0] < _HG_TTL:
        return hit[1], hit[2]
    if kind == "rank":
        path = "/rank/%s" % key
        if page:
            path += "?page=%d" % (page + 1)
    else:
        path = "/category/%s" % key
        if page:
            path += "?page=%d" % (page + 1)
    html = _hg_get(path)
    items = _hg_cards(html, limit=limit)
    total = 0
    mt = re.search(r'"total"\s*:\s*(\d+)', html or "")
    if mt:
        total = int(mt.group(1))
    label = dict(HG_CATS).get(key) or dict(HG_RANKS).get(key) or key
    for it in items:
        it["cat"] = label
    has_more = bool(items) and (total == 0 or (page + 1) * max(24, len(items)) < max(total, len(items)))
    _HG_CACHE[ck] = (now, items, has_more)
    return items, has_more


def hongguo_series(series_id):
    """详情页：剧名 / 集数 / 标签 / 每集 player 链接"""
    sid = str(series_id or "").strip()
    html = _hg_get("/detail?series_id=%s" % sid)
    if not html:
        return {}
    title = ""
    mt = re.search(r"<title>([^<|]+)[<|]", html)
    if mt:
        title = mt.group(1).strip()
    total = 0
    me = re.search(r"全\s*(\d+)\s*集", html)
    if me:
        total = int(me.group(1))
    eps, seen = [], set()
    for m in re.finditer(r'href="(/player/%s/[^"]+)"' % re.escape(sid), html):
        path = m.group(1)
        if path in seen:
            continue
        seen.add(path)
        vid = path.rsplit("/", 1)[-1]
        if vid == sid:
            continue
        eps.append({"vid": vid, "no": len(eps) + 1})
    cover = ""
    mc = re.search(r'(?:poster|data-poster|src)="(https://p[0-9]+-sign\.douyinpic\.com[^"]+)"', html)
    if mc:
        cover = mc.group(1)
    return {"series_id": sid, "title": title or ("红果 %s" % sid), "total": total,
            "episodes": eps, "cover": cover, "platform": "hongguo",
            "item_id": "hg:%s" % sid}


def hongguo_play(series_id, vid):
    """player 页里直接有同源 mp4 → 返回 {url, quality}，可交给面板代理站内播放"""
    sid = str(series_id or "").strip()
    v = str(vid or "").strip()
    if not sid or not v:
        raise RuntimeError("缺少 series_id / vid")
    html = _hg_get("/player/%s/%s" % (sid, v))
    if not html:
        raise RuntimeError("播放页抓取失败")
    best = ""
    for m in re.finditer(r'"?(/video/public/[^"\']+?/(\d+)p\.mp4)"?', html):
        u, q = m.group(1), int(m.group(2))
        if not best or q > int(re.search(r"/(\d+)p\.mp4", best).group(1) or 0):
            best = u
    if not best:
        m = re.search(r'<video[^>]+src="([^"]+)"', html)
        if m:
            best = m.group(1)
    if not best:
        raise RuntimeError("这一集没解析到视频地址")
    if best.startswith("/"):
        best = HG_BASE + best
    return {"url": best, "series_id": sid, "vid": v,
            "quality": (re.search(r"/(\d+)p\.mp4", best).group(1) + "p") if re.search(r"/(\d+)p\.mp4", best) else ""}


def lib_search(genre_id, page=0, page_size=30):
    """按题材聚合 B 站短剧正片，返回 (items, has_more)。每个题材 2 组关键词 × 多页。"""
    gid = str(genre_id or "").strip()
    g = next((x for x in LIB_GENRES if x["id"] == gid or x["name"] == gid), LIB_GENRES[0])
    page = max(0, int(page or 0))
    key = ("lib", g["id"], page)
    now = time.time()
    hit = _LIB_CACHE.get(key)
    if hit and now - hit[0] < _LIB_TTL:
        return hit[1], hit[2]
    items, seen = [], set()
    bili_page = page + 1
    for kw in g["kws"][:2]:
        params = {"search_type": "video", "keyword": kw, "page": bili_page, "pagesize": 30}
        try:
            signed = _wbi_sign(params)
            data = _http_json("https://api.bilibili.com/x/web-interface/wbi/search/type?" + urlencode(signed))
            if (data or {}).get("code") not in (0, "0", None):
                data = _http_json("https://api.bilibili.com/x/web-interface/wbi/search/type?" + urlencode(params))
        except Exception as ex:
            _log("lib_search %s failed: %s" % (kw, ex))
            data = None
        rows = ((data or {}).get("data") or {}).get("result") or []
        for row in rows[:page_size]:
            it = _bili_item(row)
            if not it or it.get("item_id") in seen:
                continue
            if not _lib_clean(it, g["name"]):
                continue
            seen.add(it.get("item_id"))
            items.append(it)
    has_more = len(items) >= 8
    _LIB_CACHE[key] = (now, items, has_more)
    if len(_LIB_CACHE) > 200:
        for k in sorted(_LIB_CACHE, key=lambda k: _LIB_CACHE[k][0])[:80]:
            _LIB_CACHE.pop(k, None)
    return items, has_more



# ============================================================ B站高画质解析（短剧播放用）
_BILI_QN_ORDER = [120, 116, 112, 80, 74, 64, 32, 16]   # 4K/1080P60/1080P/720P60/720P/480P/360P




# ============================================================ B站登录（扫码/验证码）→ 1080P
BILI_LOGIN_PROFILE = APP_DIR / "cache" / "bili_login_profile"
BILI_COOKIE_FILE = APP_DIR / "cache" / "bilibili_cookie.txt"


def _bili_edge_path():
    import os as _os
    cands = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
             r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
             r"C:\Program Files\Google\Chrome\Application\chrome.exe",
             r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"]
    for c in cands:
        if Path(c).is_file():
            return c
    return ""



BILI_DEBUG_PORT = 19443


def _cdp_get_cookies(port=BILI_DEBUG_PORT, timeout=12):
    """连 CDP 读所有 cookie（含 httpOnly）。返回 {name: value}"""
    import asyncio
    import urllib.request as _ur
    try:
        with _ur.urlopen("http://127.0.0.1:%d/json/list" % port, timeout=5) as r:
            targets = json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return {}
    page = None
    for t in targets or []:
        if t.get("type") == "page" and "passport.bilibili.com" in (t.get("url") or ""):
            page = t
            break
    if page is None:
        for t in targets or []:
            if t.get("type") == "page":
                page = t
                break
    if not page or not page.get("webSocketDebuggerUrl"):
        return {}

    async def _run():
        import websockets
        out = {}
        async with websockets.connect(page["webSocketDebuggerUrl"], max_size=8 * 1024 * 1024) as ws:
            await ws.send(json.dumps({"id": 1, "method": "Network.getAllCookies", "params": {}}))
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
                if msg.get("id") == 1:
                    for c in (msg.get("result") or {}).get("cookies") or []:
                        if "bilibili.com" in (c.get("domain") or ""):
                            out[c.get("name")] = c.get("value")
                    break
        return out

    try:
        return asyncio.run(_run()) or {}
    except Exception as ex:
        _log("cdp cookies failed: %s" % ex)
        return {}


def bili_login_check_cdp(write=True):
    pairs = _cdp_get_cookies()
    if not pairs.get("SESSDATA"):
        return {"logged_in": False, "msg": "没拿到 SESSDATA：请保持登录窗口开着，再点一次"}
    order = ("SESSDATA", "bili_jct", "buvid3", "DedeUserID", "DedeUserID__ckMd5", "sid")
    cookie = "; ".join("%s=%s" % (k, pairs[k]) for k in order if pairs.get(k))
    if write:
        try:
            BILI_COOKIE_FILE.write_text(cookie, encoding="utf-8")
        except Exception:
            pass
    info = {}
    try:
        info = bili_play("BV1Rgxe69E2i", want_qn=120)
    except Exception:
        info = {}
    h = int(info.get("height") or 0)
    return {"logged_in": True, "cookie_head": cookie[:22] + "...",
            "max_height": h, "quality": ("%dP" % h) if h else "未知",
            "msg": ("已登录（CDP 读取成功）当前最高 %dP" % h) if h else "已登录（CDP 读取成功），但分辨率探测失败"}


def bili_login_open(tel=""):
    """打开 B站登录窗口（独立 profile，不碰你的日常浏览器）。"""
    exe = _bili_edge_path()
    if not exe:
        raise RuntimeError("找不到 Edge/Chrome")
    BILI_LOGIN_PROFILE.mkdir(parents=True, exist_ok=True)
    url = "https://passport.bilibili.com/login"
    cmd = [exe, "--app=" + url, "--user-data-dir=" + str(BILI_LOGIN_PROFILE),
           "--remote-debugging-port=%d" % BILI_DEBUG_PORT,
           "--window-size=980,760", "--no-first-run", "--no-default-browser-check",
           "--disable-features=TranslateUI"]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=(0x08000000 if os.name == "nt" else 0))
    return {"opened": True, "tel": str(tel or ""), "profile": str(BILI_LOGIN_PROFILE)}


def _dpapi_unprotect(blob):
    try:
        import win32crypt
        return win32crypt.CryptUnprotectData(blob, None, None, None, 0)[1]
    except Exception:
        return b""


def _edge_master_key(profile_dir):
    """从 Local State 取 os_crypt.encrypted_key → DPAPI → AES 主密钥"""
    import base64
    ls = Path(profile_dir) / "Local State"
    if not ls.is_file():
        return b""
    try:
        d = json.loads(ls.read_text(encoding="utf-8", errors="replace"))
        enc = base64.b64decode((d.get("os_crypt") or {}).get("encrypted_key") or "")
        if enc[:5] == b"DPAPI":
            enc = enc[5:]
        return _dpapi_unprotect(enc)
    except Exception:
        return b""


def _decrypt_cookie_value(key, enc_value):
    """Chromium: v10/v11 + 12B nonce + ciphertext + 16B tag（AES-256-GCM）"""
    try:
        if not enc_value:
            return ""
        if enc_value[:3] not in (b"v10", b"v11"):
            out = _dpapi_unprotect(enc_value)
            return out.decode("utf-8", "replace") if out else ""
        if not key:
            return ""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        nonce = enc_value[3:15]
        payload = enc_value[15:]
        data = AESGCM(key).decrypt(nonce, payload, None)
        return data.decode("utf-8", "replace")
    except Exception:
        return ""



def _close_login_windows():
    """只关掉 bili_login_profile 那几个 Edge 进程（不碰主面板窗口）"""
    try:
        ps = ("Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | "
              "Where-Object { $_.CommandLine -like '*bili_login_profile*' } | "
              "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
        subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, timeout=25,
                       creationflags=(0x08000000 if os.name == "nt" else 0))
        time.sleep(1.5)
        return True
    except Exception:
        return False



def _cookie_looks_valid(pairs):
    """SESSDATA 形如 847b1bc4%2C1755...（含 %2C，长度 ≥ 40），否则认为是解密失败"""
    v = str((pairs or {}).get("SESSDATA") or "")
    if len(v) < 40:
        return False
    return ("%2C" in v) or (v.count(",") >= 1 and len(v) > 60)


def bili_read_cookies(auto_close=True):
    """从登录 profile 里读出 .bilibili.com 的 Cookie（含 httpOnly 的 SESSDATA）。
    Edge 在跑时会锁 DB → 默认先关掉登录窗口再读（只关 bili_login_profile 的进程）。"""
    import shutil as _sh
    import sqlite3
    prof = BILI_LOGIN_PROFILE
    if auto_close:
        _close_login_windows()
    for sub in ("Default", "Profile 1"):
        db = Path(prof) / sub / "Network" / "Cookies"
        if not db.is_file():
            db = Path(prof) / sub / "Cookies"
        if not db.is_file():
            continue
        tmp = Path(prof) / ("ck_%s.db" % sub.replace(" ", "_"))
        try:
            _sh.copy2(db, tmp)
        except Exception:
            if auto_close:
                _close_login_windows()
                try:
                    _sh.copy2(db, tmp)
                except Exception:
                    continue
            else:
                continue
        key = _edge_master_key(prof)
        pairs = {}
        try:
            con = sqlite3.connect(str(tmp))
            cur = con.cursor()
            cur.execute("select host_key, name, encrypted_value, value from cookies "
                        "where host_key like '%bilibili.com'")
            for host, name, enc, plain in cur.fetchall():
                val = plain or _decrypt_cookie_value(key, enc or b"")
                if val:
                    pairs[name] = val
            con.close()
        except Exception:
            pass
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
        if pairs.get("SESSDATA"):
            return pairs
    return {}


def bili_login_check(write=True):
    """读取凭据 → 写入 cache/bilibili_cookie.txt → 验证 1080P 是否可用"""
    pairs = bili_read_cookies(auto_close=False)
    if not pairs.get("SESSDATA") or not _cookie_looks_valid(pairs):
        return {"logged_in": False, "msg": "还没检测到登录态：请保持登录窗口打开再点一次（本地解密兜底已禁用）"}
    order = ("SESSDATA", "bili_jct", "buvid3", "DedeUserID", "DedeUserID__ckMd5", "sid")
    cookie = "; ".join("%s=%s" % (k, pairs[k]) for k in order if pairs.get(k))
    if write:
        try:
            BILI_COOKIE_FILE.write_text(cookie, encoding="utf-8")
        except Exception:
            pass
    maxh = 0
    try:
        info = bili_play("BV1Rgxe69E2i", want_qn=120)
        maxh = int(info.get("height") or 0)
    except Exception:
        maxh = 0
    return {"logged_in": True, "cookie_head": cookie[:24] + "...",
            "max_height": maxh, "quality": ("%dP" % maxh) if maxh else "未知",
            "msg": ("已登录，当前可用最高 %dP" % maxh) if maxh else "已登录但分辨率探测失败"}


def _bili_cookie():
    """B站登录态：config.json 的 bilibili_cookie / cache/bilibili_cookie.txt / cache/bilibili_cookies.txt"""
    try:
        cfg = Path(STATE_DIR.parent / "config.json")
        if cfg.is_file():
            import json as _j
            d = _j.loads(cfg.read_text(encoding="utf-8"))
            v = str((d.get("bilibili_cookie") or (d.get("bilibili") or {}).get("cookie") or "")).strip()
            if v:
                return v
    except Exception:
        pass
    for p in (STATE_DIR.parent / "cache" / "bilibili_cookie.txt",
              STATE_DIR.parent / "cache" / "bilibili_cookies.txt"):
        try:
            if p.is_file():
                t = p.read_text(encoding="utf-8", errors="replace").strip()
                if t:
                    return t.splitlines()[0].strip()
        except Exception:
            pass
    return ""


def bili_play(bvid_or_url, want_qn=120):
    """解析 B站视频的最高可用 DASH 视频流 + 最佳音频流；返回 {vurl, aurl, quality, height, duration}。
    无登录 cookie 时多数视频上限 480P；配置了 cookies 后可到 1080P。"""
    bv = ""
    m = re.search(r"(BV[0-9A-Za-z]{10})", str(bvid_or_url or ""))
    if m:
        bv = m.group(1)
    if not bv:
        raise RuntimeError("不是合法的 B 站 bvid")
    v = _http_json("https://api.bilibili.com/x/web-interface/view?bvid=" + bv)
    if (v or {}).get("code") not in (0, "0", None):
        raise RuntimeError("B站 view 接口失败：%s" % (v or {}).get("message"))
    d = v.get("data") or {}
    cid = d.get("cid") or (((d.get("pages") or [{}])[0]).get("cid"))
    dur = d.get("duration") or 0
    if not cid:
        raise RuntimeError("拿不到 cid")
    _ck = _bili_cookie()
    _url = ("https://api.bilibili.com/x/player/playurl?bvid=%s&cid=%s&qn=%d&fnval=4048&fnver=0&fourk=1"
            % (bv, cid, int(want_qn)))
    pj = _http_json(_url, headers=({"Cookie": _ck} if _ck else None))
    if (pj or {}).get("code") not in (0, "0", None):
        raise RuntimeError("B站 playurl 失败：%s" % (pj or {}).get("message"))
    data = pj.get("data") or {}
    dash = data.get("dash") or {}
    vids = dash.get("video") or []
    auds = dash.get("audio") or []
    if not vids:
        raise RuntimeError("这条视频没有 DASH 流（可能是番剧/付费内容）")
    # 优先 avc1（浏览器硬解兼容），同高度取码率最高
    def _score(x):
        codecs = str(x.get("codecs") or "")
        return (int(x.get("height") or 0), 1 if codecs.startswith("avc1") else 0, int(x.get("bandwidth") or 0))
    best = sorted(vids, key=_score, reverse=True)[0]
    abest = sorted(auds, key=lambda a: int(a.get("bandwidth") or 0), reverse=True)[0] if auds else None
    qtxt = {120: "4K", 116: "1080P60", 112: "1080P+", 80: "1080P", 74: "720P60",
            64: "720P", 32: "480P", 16: "360P"}.get(int(best.get("id") or 0),
                                                   "%sP" % (best.get("height") or "?"))
    return {
        "bvid": bv, "cid": cid, "duration": dur,
        "vurl": best.get("baseUrl") or best.get("base_url"),
        "aurl": (abest.get("baseUrl") or abest.get("base_url")) if abest else "",
        "quality": qtxt, "height": int(best.get("height") or 0),
        "codecs": str(best.get("codecs") or ""),
        "accept": data.get("accept_description") or [],
    }



# ============================================================ 高画质集号缓存（DASH → 本地 mp4）

_HQ_JOBS = {}
_HQ_LOCK = threading.Lock()


def _hq_job_start(bvid, backend_obj):
    import uuid
    jid = uuid.uuid4().hex[:12]
    with _HQ_LOCK:
        _HQ_JOBS[jid] = {"state": "running", "bvid": bvid, "ts": time.time()}
        if len(_HQ_JOBS) > 40:
            for k in sorted(_HQ_JOBS, key=lambda k: _HQ_JOBS[k]["ts"])[:16]:
                _HQ_JOBS.pop(k, None)

    def _run():
        try:
            try:
                set_ffmpeg_hint(getattr(backend_obj, "_find_ffmpeg", lambda: "")())
            except Exception:
                pass
            path, quality, dur = bili_cache_episode(bvid, want_qn=120)
            import urllib.parse as _up
            with _HQ_LOCK:
                _HQ_JOBS[jid].update({"state": "done", "quality": quality, "duration": dur,
                                      "local_path": path,
                                      "play_url": "/api/drama_media?path=" + _up.quote(path, safe="")})
        except Exception as ex:
            with _HQ_LOCK:
                _HQ_JOBS[jid].update({"state": "error", "msg": str(ex)[:200]})

    threading.Thread(target=_run, daemon=True).start()
    return jid


def bili_cache_episode(bvid, want_qn=120, out_dir=None):
    """把一集的 DASH 视频+音频无损合成到本地 mp4（-c copy），返回 (本地路径, 画质, 秒数)。"""
    info = bili_play(bvid, want_qn=want_qn)
    base = Path(out_dir) if out_dir else (STATE_DIR.parent / "cache" / "drama_hq")
    base.mkdir(parents=True, exist_ok=True)
    tag = "%s_%s" % (info["bvid"], (info.get("quality") or "q"))
    out = base / (tag + ".mp4")
    if out.is_file() and out.stat().st_size > 200 * 1024:
        return str(out), info.get("quality"), info.get("duration")
    ff = ""
    if _FFMPEG_HINT.get("path"):
        ff = _FFMPEG_HINT["path"]
    if not ff:
        for c in (STATE_DIR.parent / "bin" / "ffmpeg.exe", STATE_DIR.parent / "tools" / "ffmpeg.exe"):
            if Path(c).is_file():
                ff = str(c)
                break
    if not ff:
        import shutil as _sh
        ff = _sh.which("ffmpeg") or ""
    if not ff:
        raise RuntimeError("找不到 ffmpeg，无法合成高清片源")
    hdr = ("Referer: https://www.bilibili.com/\r\n"
           "Origin: https://www.bilibili.com\r\n"
           "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36\r\n")
    _ck2 = _bili_cookie()
    if _ck2:
        hdr += "Cookie: " + _ck2 + "\r\n"
    tmp = base / (tag + ".part.mp4")
    cmd = [ff, "-y", "-v", "error", "-nostdin", "-headers", hdr, "-i", info["vurl"]]
    if info.get("aurl"):
        cmd += ["-headers", hdr, "-i", info["aurl"], "-map", "0:v:0", "-map", "1:a:0"]
    else:
        cmd += ["-map", "0:v:0"]
    cmd += ["-c:v", "copy"]
    if info.get("aurl"):
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    cmd += ["-movflags", "+faststart", str(tmp)]
    r = subprocess.run(cmd, capture_output=True, timeout=600, creationflags=(0x08000000 if os.name == "nt" else 0))
    if r.returncode != 0 or not tmp.is_file() or tmp.stat().st_size < 200 * 1024:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        raise RuntimeError("片源合成失败：%s" % (r.stderr or b"")[:160].decode("utf-8", "replace"))
    tmp.replace(out)
    return str(out), info.get("quality"), info.get("duration")


_FFMPEG_HINT = {}


def set_ffmpeg_hint(path):
    _FFMPEG_HINT["path"] = str(path or "")



def search_all(q, limit=36):
    """站内直搜：B站 + 红果 一起搜，返回可直接就地播放的条目（含封面/时长/来源）。"""
    q = (q or "").strip()
    if not q:
        return []
    out, seen = [], set()
    try:
        for it in (bili_search(q, limit=limit) or []):
            tid = it.get("item_id")
            if not tid or tid in seen:
                continue
            seen.add(tid)
            out.append({**it, "source": "B站"})
    except Exception as ex:
        _log("search_all bili failed: %s" % ex)
    try:
        for it in (hongguo_lib("search", q, 0, limit=24)[0] or []):
            tid = it.get("item_id")
            if not tid or tid in seen:
                continue
            seen.add(tid)
            out.append({**it, "source": "红果"})
    except Exception as ex:
        _log("search_all hongguo failed: %s" % ex)
    return out

def bili_search(query, limit=18):
    q = (query or "").strip() or "短剧"
    items = []
    seen = set()

    def _push(row):
        it = _bili_item(row)
        if not it or it["item_id"] in seen:
            return
        seen.add(it["item_id"])
        items.append(it)

    def _call(endpoint, params):
        try:
            signed = _wbi_sign(params)
            url = endpoint + "?" + urlencode(signed)
            data = _http_json(url)
            if data.get("code") not in (0, "0", None):
                # 再试一次未签名，兼容部分环境
                url2 = endpoint + "?" + urlencode(params)
                data = _http_json(url2)
            return data
        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as ex:
            _log("bili search failed %s: %s" % (endpoint, ex))
            return None

    if q:
        data = _call(
            "https://api.bilibili.com/x/web-interface/wbi/search/type",
            {"search_type": "video", "keyword": q, "page": 1, "pagesize": 20},
        )
        result = ((data or {}).get("data") or {}).get("result") or []
        if isinstance(result, list):
            for row in result:
                _push(row)
                if len(items) >= limit:
                    return items
    return items


def bili_popular(limit=18, keyword=""):
    items = []
    try:
        data = _http_json("https://api.bilibili.com/x/web-interface/popular?ps=20")
        lst = ((data or {}).get("data") or {}).get("list") or []
        key = (keyword or "").strip().lower()
        for row in lst:
            it = _bili_item(row if not row.get("owner") else {
                "title": row.get("title"),
                "bvid": row.get("bvid"),
                "aid": row.get("aid"),
                "pic": row.get("pic"),
                "description": row.get("desc"),
                "owner": row.get("owner"),
                "author": (row.get("owner") or {}).get("name"),
            })
            if not it:
                continue
            if key:
                blob = (it["title"] + it.get("summary", "") + it.get("subtitle", "")).lower()
                if key not in blob and keyword not in it["title"]:
                    continue
            items.append(it)
            if len(items) >= limit:
                break
    except Exception as ex:
        _log("bili popular failed: %s" % ex)
    if len(items) < 6:
        extra = bili_search(keyword or "短剧", limit=limit)
        seen = {x["item_id"] for x in items}
        for it in extra:
            if it["item_id"] not in seen:
                items.append(it)
                seen.add(it["item_id"])
            if len(items) >= limit:
                break
    return items[:limit]


_YT_ID_RE = re.compile(
    r"(?:youtube(?:-nocookie)?\.com/(?:watch\?.*?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)


def parse_youtube_id(raw):
    text = str(raw or "").strip()
    m = _YT_ID_RE.search(text)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", text) and "http" not in text and " " not in text:
        # 仅在明确像链接残留时使用；11 位中文搜索词不应误判，故这里要求全部 ASCII 且来自 URL
        return ""
    return ""


def youtube_item_from_url(raw):
    text = str(raw or "").strip()
    m = _YT_ID_RE.search(text)
    if not m:
        return None
    vid = m.group(1)
    embed = sanitize_embed("https://www.youtube.com/embed/%s" % vid, "youtube")
    if not embed:
        return None
    cover = sanitize_cover("https://i.ytimg.com/vi/%s/hqdefault.jpg" % vid)
    title = "YouTube 官方视频"
    try:
        data = _http_json(
            "https://www.youtube.com/oembed?format=json&url=" + quote("https://www.youtube.com/watch?v=" + vid, safe=""),
            referer="https://www.youtube.com/",
        )
        title = str((data or {}).get("title") or title)[:120]
        author = str((data or {}).get("author_name") or "")[:80]
    except Exception:
        author = ""
    return {
        "item_id": "yt:" + vid,
        "title": title,
        "platform": "youtube",
        "kind": "embed",
        "playback": "embed",
        "subtitle": author or "YouTube 官方嵌入",
        "summary": "使用 YouTube 官方嵌入播放器在软件内观看。",
        "cover": cover,
        "embed": embed,
        "url": "https://www.youtube.com/watch?v=" + vid,
        "aspect": "16:9",
        "source": "youtube",
    }


def parse_bilibili_url(raw):
    text = str(raw or "").strip()
    m = re.search(r"(BV[0-9A-Za-z]+)", text)
    if m:
        return _bili_item({"title": "B站视频", "bvid": m.group(1)})
    m = re.search(r"(?:[?&]aid=|/video/av)(\d+)", text, re.I)
    if m:
        return _bili_item({"title": "B站视频", "aid": m.group(1)})
    return None


def theme_cards(platform_id="", query=""):
    q = (query or "").strip()
    plat = _platform_by_id(platform_id) if platform_id else None
    out = []
    for t in THEMES:
        if q and (q not in t["name"] and q not in t["query"] and t["name"] not in q):
            continue
        item_id = "theme:%s:%s" % (platform_id or "hub", t["id"])
        out.append({
            "item_id": item_id,
            "title": t["name"],
            "platform": platform_id or "hongguo",
            "kind": "theme",
            "playback": "hall",
            "subtitle": (plat["name"] if plat else "短剧中心") + " · 题材展厅",
            "summary": t["summary"],
            "cover": "",
            "embed": "",
            "channel": t["name"],
            "query": t["query"],
            "url": "",
            "aspect": "9:16",
            "source": "theme",
        })
    return out


def hall_notice(plat):
    if not plat:
        return "未找到该官方频道。"
    if plat["id"] in EMBED_IDS:
        if plat["id"] == "youtube":
            return "YouTube 可在本页使用官方嵌入播放器观看。请粘贴官方视频链接；本软件不抓取、不破解 YouTube 流。"
        return "哔哩哔哩支持官方检索，并在本页使用官方嵌入播放器观看。不另开新窗口，不缓存正片文件。"
    return (
        "已进入「%s」软件内展厅。该平台正片通常带有官方 DRM / 会员校验，"
        "本软件不会解码、不会缓存，也绝不会再弹出爱奇艺等官方新窗口。"
        "可在此浏览频道与题材；若要在软件内直接观看，请改用 B站 或 YouTube 的官方嵌入内容。"
    ) % plat["name"]


def hall_payload(platform_id, query="", channel=""):
    plat = _platform_by_id(platform_id)
    if not plat:
        plat = _platform_by_id("hongguo")
        platform_id = "hongguo"
    q = (query or "").strip()
    ch = (channel or "").strip()
    # 频道名若像题材，转成题材查询
    theme = _theme_by_name(ch)
    if theme and not q:
        q = theme["query"] if plat["id"] in EMBED_IDS else theme["name"]
        ch = theme["name"]
    elif ch and ch not in ("官方首页", "发现", "微博视频", "微博首页", "知乎视频") and not q:
        if plat["id"] in EMBED_IDS:
            q = ch if ch not in ("热播榜", "短剧分类", "微剧频道", "放映厅") else "短剧"
    items = []
    recs = []
    playback = _playback_of(plat["id"])
    if plat["id"] == "bilibili":
        items = bili_search(q or "短剧", limit=18) if q else bili_popular(limit=18)
        recs = bili_popular(limit=8) if q else items[:8]
    elif plat["id"] == "youtube":
        yt = youtube_item_from_url(q)
        if yt:
            items = [yt]
        elif q:
            # 无官方无钥搜索接口，不抓取 YouTube 网页
            items = []
        recs = []
    else:
        items = theme_cards(plat["id"], query=ch if (ch and not q) else q)
        # 仅在有明确题材/检索词时附加 B 站可嵌入结果，避免刚打开展厅就被官网接口拖住
        if q or theme:
            recs = bili_search(q or (theme["query"] if theme else ch) or "短剧", limit=10)
        else:
            recs = []
    title = plat["name"]
    if ch:
        title = "%s · %s" % (plat["name"], ch)
    if q and plat["id"] in EMBED_IDS:
        title = "在%s搜索「%s」" % (plat["name"], q)
    elif q and not ch:
        title = "%s · 检索「%s」" % (plat["name"], q)
    return {
        "view": "hall",
        "platform": plat["id"],
        "platform_name": plat["name"],
        "vendor": plat.get("vendor") or "",
        "color": plat.get("color") or "#ff3d71",
        "tag": plat.get("tag") or "官方频道",
        "blurb": _public_blurb(plat),
        "notice": hall_notice(plat),
        "playback": playback,
        "channels": [{"name": c.get("name") or "频道", "note": c.get("note") or ""} for c in (plat.get("channels") or [])],
        "channel": ch,
        "query": q,
        "title": title,
        "items": items,
        "recommendations": recs,
        "url": "",
    }


def resolve_item(item_id, fallback=None):
    item_id = str(item_id or "").strip()
    fallback = fallback or {}
    if item_id.startswith("bili:"):
        token = item_id.split(":", 1)[1]
        raw = {"title": fallback.get("title") or "B站视频"}
        if token.startswith("av") and token[2:].isdigit():
            raw["aid"] = token[2:]
        else:
            raw["bvid"] = token
        it = _bili_item(raw)
        if it:
            if fallback.get("title"):
                it["title"] = str(fallback["title"])[:120]
            if fallback.get("cover"):
                it["cover"] = sanitize_cover(fallback["cover"]) or it["cover"]
        return it
    if item_id.startswith("yt:"):
        vid = item_id.split(":", 1)[1]
        return youtube_item_from_url("https://www.youtube.com/watch?v=" + vid)
    if item_id.startswith("theme:"):
        parts = item_id.split(":")
        # theme:{platform}:{themeId}
        pid = parts[1] if len(parts) > 1 else "hongguo"
        tid = parts[2] if len(parts) > 2 else ""
        theme = None
        for t in THEMES:
            if t["id"] == tid or t["name"] == tid:
                theme = t
                break
        if not theme:
            return None
        return {
            "item_id": item_id,
            "title": theme["name"],
            "platform": pid if _platform_by_id(pid) else "hongguo",
            "kind": "theme",
            "playback": "hall",
            "subtitle": "题材展厅",
            "summary": theme["summary"],
            "channel": theme["name"],
            "query": theme["query"],
            "cover": "",
            "embed": "",
            "url": "",
            "aspect": "9:16",
            "source": "theme",
        }
    if item_id.startswith("hall:"):
        pid = item_id.split(":", 1)[1]
        plat = _platform_by_id(pid)
        if not plat:
            return None
        return {
            "item_id": item_id,
            "title": plat["name"],
            "platform": pid,
            "kind": "hall",
            "playback": "hall",
            "subtitle": plat.get("vendor") or "",
            "summary": _public_blurb(plat),
            "cover": "",
            "embed": "",
            "url": "",
            "aspect": "9:16",
            "source": "hall",
        }
    # 兼容旧记录：一条官方主页 URL
    url = sanitize_url(item_id) or sanitize_url(fallback.get("url") or "")
    if url:
        host = (urlparse(url).hostname or "").lower()
        for p in PLATFORMS:
            if _host_allowed(host) and any(host == h or host.endswith("." + h) for h in p["hosts"]):
                return {
                    "item_id": "hall:" + p["id"],
                    "title": p["name"],
                    "platform": p["id"],
                    "kind": "hall",
                    "playback": "hall",
                    "subtitle": p.get("vendor") or "",
                    "summary": _public_blurb(p),
                    "cover": "",
                    "embed": "",
                    "url": "",
                    "aspect": "9:16",
                    "source": "hall",
                }
    yt = youtube_item_from_url(item_id) or youtube_item_from_url(fallback.get("url") or "")
    if yt:
        return yt
    bili = parse_bilibili_url(item_id) or parse_bilibili_url(fallback.get("url") or "")
    if bili:
        return bili
    return None


def search_payload(query, preferred="hongguo"):
    q = (query or "").strip()
    pref = preferred or "hongguo"
    items = []
    # 粘贴的官方可嵌入链接优先
    yt = youtube_item_from_url(q)
    if yt:
        items.append(yt)
    bili = parse_bilibili_url(q)
    if bili:
        items.append(bili)
    themes = theme_cards(pref if _platform_by_id(pref) and pref not in EMBED_IDS else "", q)
    pasted = bool(yt or (bili and re.search(r"(BV[0-9A-Za-z]+)|bilibili\.com|/video/av", q, re.I)))
    if q and not pasted:
        items.extend(bili_search(q, limit=16))
    halls = []
    for p in PLATFORMS:
        hit = (not q) or (q in p["name"] or q in p.get("vendor", "") or q in p.get("tag", "") or q in p["id"])
        if hit:
            halls.append({
                "item_id": "hall:" + p["id"],
                "title": p["name"],
                "platform": p["id"],
                "kind": "hall",
                "playback": _playback_of(p["id"]),
                "subtitle": (p.get("vendor") or "") + " · " + (p.get("tag") or "官方频道"),
                "summary": _public_blurb(p),
                "cover": "",
                "embed": "",
                "url": "",
                "color": p.get("color") or "#ff3d71",
                "aspect": "9:16",
                "source": "hall",
            })
    halls.sort(key=lambda r: (0 if r["platform"] == pref else 1, 0 if r["playback"] == "embed" else 1, r["title"]))
    return {
        "query": q,
        "preferred": pref,
        "items": items,
        "themes": themes,
        "halls": halls,
        "results": halls,  # 兼容旧字段：站点切换条
    }


def close_leftover_profile():
    """关闭残留的 drama_profile 浏览器进程，绝不杀 DownloadStack Control。"""
    if os.name != "nt":
        return 0
    killed = 0
    try:
        out = subprocess.run(
            [
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                "Get-CimInstance Win32_Process | "
                "Where-Object { $_.CommandLine -and ($_.CommandLine -like '*drama_profile*') } | "
                "Select-Object -ExpandProperty ProcessId",
            ],
            capture_output=True, text=True, timeout=8,
            creationflags=0x08000000 if os.name == "nt" else 0,
        )
        pids = []
        for line in (out.stdout or "").splitlines():
            line = line.strip()
            if line.isdigit():
                pids.append(int(line))
        for pid in pids:
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True, timeout=4,
                    creationflags=0x08000000,
                )
                killed += 1
            except Exception:
                pass
    except Exception as ex:
        _log("close leftover failed: %s" % ex)
    if killed:
        _log("closed leftover drama_profile count=%s" % killed)
    return killed


# 明确废弃：任何调用都不得再启动 Edge/Chrome --app 窗口。
def _launch_app_window(*_args, **_kwargs):
    _log("v5: _launch_app_window disabled")
    return 0, "已禁用官方站点外弹窗口"


def open_in_app(*_args, **_kwargs):
    return False, "已改为软件内自有剧场，不再打开官方站点窗口", {"disabled": True, "docked": False}


def dock_update(*_args, **_kwargs):
    return True, "", {"docked": False, "disabled": True}


def close_theater():
    n = close_leftover_profile()
    return True, "", {"hidden": True, "cleared": n}


_LEFTOVER_ONCE = {"done": False}


def _maybe_clear_leftover():
    if _LEFTOVER_ONCE["done"]:
        return
    _LEFTOVER_ONCE["done"] = True
    try:
        close_leftover_profile()
    except Exception:
        pass


def handle_action(_backend, act, body):
    body = body or {}
    if act == "drama_catalog":
        _maybe_clear_leftover()
        st = _load_state()
        return True, "", {
            "platforms": platforms_public(),
            "genres": GENRES,
            "spotlight": SPOTLIGHT,
            "history": st.get("history") or [],
            "favorites": st.get("favorites") or [],
            "last_platform": st.get("last_platform") or "hongguo",
        }

    if act == "drama_bili_login_open":
        return True, "登录窗口已弹出", bili_login_open(str(body.get("tel") or ""))

    if act == "drama_bili_login_check":
        st = bili_login_check_cdp()
        if not st.get("logged_in"):
            st2 = bili_login_check()
            if st2.get("logged_in"):
                st = st2
        return bool(st.get("logged_in")), st.get("msg") or "", st

    if act == "drama_bili_login_close":
        _close_login_windows()
        return True, "登录窗口已关闭", {}

    if act == "drama_hot_list":
        n = int(body.get("n") or 18)
        idx = hongguo_index_items()
        hot = idx[:n] if idx else (hongguo_lib("category", "real-drama", 0, limit=n)[0] or [])
        out = []
        for it in hot:
            sid = it.get("series_id")
            out.append({**it,
                        "url": "https://hongguoduanju.com/detail?series_id=%s" % sid,
                        "item_id": "hg:%s" % sid})
        return True, "", {"items": out, "total": len(idx)}

    if act == "drama_hg_catalog":
        kind = str(body.get("kind") or "category")
        key = str(body.get("key") or "")
        page = int(body.get("page") or 0)
        size = int(body.get("limit") or 36)
        idx = hongguo_index_items()
        if kind == "index" and idx:
            start = page * size
            items = idx[start:start + size]
            return True, "", {"items": items, "has_more": start + size < len(idx), "page": page,
                              "total": len(idx),
                              "cats": [{"id": k, "name": n} for k, n in HG_CATS if k != "comic"]}
        if idx:
            pool = [x for x in idx if (not key or x.get("cat") == dict(HG_CATS).get(key, key))]
            start = page * size
            items = pool[start:start + size]
            if items:
                return True, "", {"items": items, "has_more": start + size < len(pool), "page": page,
                                  "total": len(pool),
                                  "cats": [{"id": k, "name": n} for k, n in HG_CATS if k != "comic"]}
        key = key or "real-drama"
        items, more = hongguo_lib(kind, key, page, limit=size)
        return True, "", {"items": items, "has_more": more, "page": page,
                          "cats": [{"id": k, "name": n} for k, n in HG_CATS],
                          "ranks": [{"id": k, "name": n} for k, n in HG_RANKS]}

    if act == "drama_hg_build_index":
        st = hongguo_build_index(max_pages=int(body.get("max_pages") or 40))
        return True, "索引完成：%d 部" % st.get("total", 0), st

    if act == "drama_hg_play":
        sid = str(body.get("series_id") or body.get("item_id") or "").replace("hg:", "").strip()
        ser = hongguo_series(sid)
        eps = ser.get("episodes") or []
        title = str(body.get("title") or ser.get("title") or "").strip()
        info = None
        if eps:
            try:
                info = hongguo_play(sid, eps[0]["vid"])
            except Exception:
                info = None
        if info and info.get("url"):
            return True, "红果直出（%s）" % (info.get("quality") or "360P"), {
                "play_url": "/api/hg_media?u=" + quote(info["url"], safe=""),
                "quality": info.get("quality") or "360P",
                "episodes": len(eps), "title": title, "series_id": sid, "source": "红果",
            }
        # 红果这集是 JS 播放页 → 自动回落 B站同剧（高清链路，异步合成）
        cand = ""
        try:
            for it in (bili_search(title or sid, limit=6) or []):
                tid = str(it.get("item_id") or "")
                if tid.startswith("bili:"):
                    cand = tid.split(":", 1)[1]
                    break
        except Exception:
            cand = ""
        if not cand:
            return False, "红果该集无直链，B站也没找到同名剧；换个名字试试", {}
        jid = _hq_job_start(cand, _backend)
        return True, "红果无直链，已自动切 B站高清（首次合成 20~90s）", {
            "job": jid, "pending": True, "bvid": cand, "title": title, "source": "B站",
        }

    if act == "drama_search_all":
        q = str(body.get("query") or body.get("q") or "").strip()
        items = hongguo_index_search(q, limit=24)
        if len(items) < 12:
            items += search_all(q, limit=int(body.get("limit") or 36))
        return True, "搜到 %d 部" % len(items), {"query": q, "items": items}

    if act == "drama_play_hq":
        import urllib.parse as _up
        item_id = str(body.get("item_id") or body.get("bvid") or "").strip()
        bvid = item_id.split(":", 1)[1] if item_id.startswith("bili:") else item_id
        # 已有缓存直接返回（秒开）
        try:
            base = STATE_DIR.parent / "cache" / "drama_hq"
            hit = sorted(base.glob("%s_*.mp4" % bvid), key=lambda p: p.stat().st_size, reverse=True)
            if hit and hit[0].stat().st_size > 200 * 1024:
                p = hit[0]
                q = p.stem.split("_", 1)[1] if "_" in p.stem else ""
                return True, "命中缓存（%s）" % q, {
                    "play_url": "/api/drama_media?path=" + _up.quote(str(p), safe=""),
                    "quality": q, "local_path": str(p), "ready": True,
                }
        except Exception:
            pass
        jid = _hq_job_start(bvid, _backend)
        return True, "正在后台合成最高可用画质（首次 20~90s）", {"job": jid, "pending": True}

    if act == "drama_play_hq_status":
        jid = str(body.get("job") or "").strip()
        with _HQ_LOCK:
            j = dict(_HQ_JOBS.get(jid) or {})
        if not j:
            return False, "任务不存在或已过期", {}
        if j.get("state") == "error":
            return False, j.get("msg") or "合成失败", {}
        return True, ("就绪：%s" % j.get("quality")) if j.get("state") == "done" else "合成中…", j
    if act == "drama_lib":
        gid = str(body.get("genre") or "").strip() or LIB_GENRES[0]["id"]
        page = int(body.get("page") or 0)
        items, more = lib_search(gid, page)
        return True, "", {
            "genres": [{"id": g["id"], "name": g["name"]} for g in LIB_GENRES],
            "genre": gid,
            "items": items,
            "page": page,
            "has_more": more,
        }
    if act == "drama_search":
        q = str(body.get("query") or body.get("q") or "").strip()
        pref = str(body.get("platform") or body.get("preferred") or "hongguo").strip() or "hongguo"
        bundle = search_payload(q, preferred=pref)
        return True, "", bundle
    if act == "drama_open":
        plat = str(body.get("platform") or "").strip()
        q = str(body.get("query") or "").strip()
        ch = str(body.get("channel") or "").strip()
        item_id = str(body.get("item_id") or "").strip()
        # 若带的是可嵌入链接或旧版官方 URL，先解析成条目
        if item_id or body.get("url"):
            resolved = resolve_item(item_id or body.get("url"), fallback=body)
            if resolved and resolved.get("kind") == "embed":
                st = record_history(resolved)
                recs = bili_popular(limit=8) if resolved.get("platform") == "bilibili" else []
                return True, "", {
                    "view": "player",
                    "item": resolved,
                    "recommendations": recs,
                    "history": st.get("history") or [],
                    "favorites": st.get("favorites") or [],
                    "url": "",
                    "docked": False,
                }
            if resolved and resolved.get("kind") in ("theme", "hall"):
                plat = resolved.get("platform") or plat
                if resolved.get("kind") == "theme":
                    ch = resolved.get("channel") or ch
                    q = q or resolved.get("query") or ""
        if not plat:
            url = sanitize_url(body.get("url") or "")
            if url:
                host = (urlparse(url).hostname or "").lower()
                for p in PLATFORMS:
                    if any(host == h or host.endswith("." + h) for h in p["hosts"]):
                        plat = p["id"]
                        break
        if not plat:
            plat = "hongguo"
        # 标题若只是平台名，不要当成频道
        plat_obj = _platform_by_id(plat)
        if plat_obj and ch in (plat_obj["name"], plat_obj["name"] + "官方页面", "官方页面", "内置剧场"):
            ch = ""
        if q and not ch and plat in EMBED_IDS:
            pass
        extra = hall_payload(plat, query=q, channel=ch)
        embed_items = [x for x in (extra.get("items") or []) if x.get("kind") == "embed"]
        if q and len(embed_items) == 1 and (youtube_item_from_url(q) or parse_bilibili_url(q)):
            resolved = embed_items[0]
            st = record_history(resolved)
            return True, "", {
                "view": "player",
                "item": resolved,
                "recommendations": extra.get("recommendations") or [],
                "history": st.get("history") or [],
                "favorites": st.get("favorites") or [],
                "url": "",
                "docked": False,
            }
        st = record_history({
            "item_id": "hall:" + plat + ((":" + ch) if ch else ""),
            "title": extra.get("title") or (plat_obj["name"] if plat_obj else plat),
            "platform": plat,
            "query": q,
            "kind": "hall",
            "url": "",
        })
        extra["history"] = st.get("history") or []
        extra["favorites"] = st.get("favorites") or []
        extra["docked"] = False
        extra["url"] = ""
        return True, "", extra
    if act == "drama_play":
        item_id = str(body.get("item_id") or "").strip()
        resolved = resolve_item(item_id or body.get("url") or "", fallback=body)
        if not resolved:
            return False, "没有可在软件内打开的条目", {}
        if resolved.get("kind") != "embed":
            # 主题 / 展厅回到 hall，绝不外开窗口
            plat = resolved.get("platform") or "hongguo"
            extra = hall_payload(plat, query=resolved.get("query") or "", channel=resolved.get("channel") or "")
            st = record_history(resolved)
            extra["history"] = st.get("history") or []
            extra["favorites"] = st.get("favorites") or []
            extra["docked"] = False
            extra["url"] = ""
            return True, "", extra
        st = record_history(resolved)
        recs = []
        if resolved.get("platform") == "bilibili":
            recs = bili_popular(limit=8)
        elif resolved.get("platform") == "youtube":
            recs = []
        return True, "", {
            "view": "player",
            "item": resolved,
            "recommendations": recs,
            "history": st.get("history") or [],
            "favorites": st.get("favorites") or [],
            "url": "",
            "docked": False,
        }
    if act == "drama_dock":
        return dock_update()
    if act == "drama_hide":
        return close_theater()
    if act == "drama_fav":
        st, on = toggle_favorite({
            "item_id": str(body.get("item_id") or "").strip(),
            "url": body.get("url") or "",
            "title": str(body.get("title") or ""),
            "platform": str(body.get("platform") or ""),
            "kind": str(body.get("kind") or ""),
            "cover": body.get("cover") or "",
        })
        return True, ("已加入片单" if on else "已移出片单"), {
            "favorited": on,
            "favorites": st.get("favorites") or [],
        }
    if act == "drama_clear_history":
        st = _load_state()
        st["history"] = []
        st["updated"] = int(time.time())
        _save_state(st)
        return True, "已清空观看记录", {"history": []}
    return False, "未知的短剧操作", {}
