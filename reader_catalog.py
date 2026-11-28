# -*- coding: utf-8 -*-
"""书城分类目录 —— 全部漫画类型均映射 MangaDex 官方 tag UUID 或官方 demographic；
小说类型均对应 Internet Archive / 维基文库 / Gutendex / Standard Ebooks / Open Library
的真实检索式。不编造不存在的标签，不接入盗版源。
"""
from __future__ import annotations

# MangaDex official tag UUIDs (from GET https://api.mangadex.org/manga/tag, 2026-11-28)
# group: genre / theme / format. Demographics use publicationDemographic, not tag ids.

MANGA_GENRES = [
    # ---- genre ----
    {"id": "action", "name": "热血", "en": "Action", "group": "类型",
     "tag": "391b0423-d847-456f-aff0-8b0cfc03066b", "aliases": ["动作", "热血", "action"]},
    {"id": "romance", "name": "恋爱", "en": "Romance", "group": "类型",
     "tag": "423e2eae-a7a2-4a8b-ac03-a8351462d71d", "aliases": ["恋爱", "愛情", "爱情", "romance"]},
    {"id": "fantasy", "name": "奇幻", "en": "Fantasy", "group": "类型",
     "tag": "cdc58593-87dd-415e-bbc0-2ec27bf404cc", "aliases": ["奇幻", "魔幻", "fantasy"]},
    {"id": "isekai", "name": "异世界", "en": "Isekai", "group": "类型",
     "tag": "ace04997-f6bd-436e-b261-779182193d3d", "aliases": ["异世界", "異世界", "isekai"]},
    {"id": "adventure", "name": "冒险", "en": "Adventure", "group": "类型",
     "tag": "87cc87cd-a395-47af-b27a-93258283bbc6", "aliases": ["冒险", "冒險", "adventure"]},
    {"id": "mystery", "name": "悬疑", "en": "Mystery", "group": "类型",
     "tag": "ee968100-4191-4968-93d3-f82d72be7e46", "aliases": ["悬疑", "懸疑", "推理", "mystery"]},
    {"id": "scifi", "name": "科幻", "en": "Sci-Fi", "group": "类型",
     "tag": "256c8bd9-4904-4360-bf4f-508a76d67183", "aliases": ["科幻", "sci-fi", "scifi", "science fiction"]},
    {"id": "historical", "name": "历史", "en": "Historical", "group": "类型",
     "tag": "33771934-028e-4cb3-8744-691e866a923e", "aliases": ["历史", "歷史", "historical"]},
    {"id": "wuxia", "name": "武侠", "en": "Wuxia", "group": "类型",
     "tag": "acc803a4-c95a-4c22-86fc-eb6b582d82a2", "aliases": ["武侠", "武俠", "江湖", "wuxia"]},
    {"id": "comedy", "name": "搞笑", "en": "Comedy", "group": "类型",
     "tag": "4d32cc48-9f00-4cca-9b5a-a839f0764984", "aliases": ["搞笑", "喜剧", "喜劇", "comedy"]},
    {"id": "horror", "name": "恐怖", "en": "Horror", "group": "类型",
     "tag": "cdad7e68-1419-41dd-bdce-27753074a640", "aliases": ["恐怖", "horror"]},
    {"id": "gl", "name": "百合", "en": "Girls' Love", "group": "类型",
     "tag": "a3c67850-4684-404e-9b7f-c69850ee5da6", "aliases": ["百合", "gl", "girls love", "girls' love"]},
    {"id": "bl", "name": "耽美", "en": "Boys' Love", "group": "类型",
     "tag": "5920b825-4181-4a17-beeb-9918b0ff7a30", "aliases": ["耽美", "bl", "boys love", "boys' love"]},
    {"id": "sports", "name": "运动", "en": "Sports", "group": "类型",
     "tag": "69964a64-2f90-4d33-beeb-f3ed2875eb4c", "aliases": ["运动", "運動", "sports"]},
    {"id": "drama", "name": "剧情", "en": "Drama", "group": "类型",
     "tag": "b9af3a63-f058-46de-a9a0-e0c13906197a", "aliases": ["剧情", "劇情", "drama"]},
    {"id": "thriller", "name": "惊悚", "en": "Thriller", "group": "类型",
     "tag": "07251805-a27e-4d59-b488-f0bfbec15168", "aliases": ["惊悚", "驚悚", "thriller"]},
    {"id": "slice", "name": "日常", "en": "Slice of Life", "group": "类型",
     "tag": "e5301a23-ebd9-49dd-a0cb-2add944c7fe9", "aliases": ["日常", "治愈系日常", "slice of life"]},
    {"id": "mecha", "name": "机甲", "en": "Mecha", "group": "类型",
     "tag": "50880a9d-5440-4732-9afb-8f457127e836", "aliases": ["机甲", "機甲", "mecha"]},
    {"id": "psychological", "name": "心理", "en": "Psychological", "group": "类型",
     "tag": "3b60b75c-a2d7-4860-ab56-05f391bb889c", "aliases": ["心理", "psychological"]},
    {"id": "crime", "name": "犯罪", "en": "Crime", "group": "类型",
     "tag": "5ca48985-9a9d-4bd8-be29-80dc0303db72", "aliases": ["犯罪", "crime"]},
    {"id": "superhero", "name": "超级英雄", "en": "Superhero", "group": "类型",
     "tag": "7064a261-a137-4d3a-8848-2d385de3a99c", "aliases": ["超级英雄", "超英", "superhero"]},
    {"id": "magical_girls", "name": "魔法少女", "en": "Magical Girls", "group": "类型",
     "tag": "81c836c9-914a-4eca-981a-560dad663e73", "aliases": ["魔法少女", "magical girls"]},
    {"id": "philosophical", "name": "哲思", "en": "Philosophical", "group": "类型",
     "tag": "b1e97889-25b4-4258-b28b-cd7f4d28ea9b", "aliases": ["哲思", "哲学", "philosophical"]},
    {"id": "medical", "name": "医学", "en": "Medical", "group": "类型",
     "tag": "c8cbe35b-1b2b-4a3f-9c37-db84c4514856", "aliases": ["医学", "醫學", "医疗", "medical"]},
    {"id": "tragedy", "name": "悲剧", "en": "Tragedy", "group": "类型",
     "tag": "f8f62932-27da-4fe4-8ee1-6779a8c5edba", "aliases": ["悲剧", "悲劇", "tragedy"]},
    # ---- theme ----
    {"id": "school", "name": "校园", "en": "School Life", "group": "题材",
     "tag": "caaa44eb-cd40-4177-b930-79d3ef2afe87", "aliases": ["校园", "校園", "学校", "school"]},
    {"id": "cooking", "name": "美食", "en": "Cooking", "group": "题材",
     "tag": "ea2bc92d-1c26-4930-9b7c-d5c0dc1b6869", "aliases": ["美食", "烹饪", "cooking"]},
    {"id": "music", "name": "音乐", "en": "Music", "group": "题材",
     "tag": "f42fbf9e-188a-447b-9fdc-f19dc1e4d685", "aliases": ["音乐", "音樂", "music"]},
    {"id": "office", "name": "职场", "en": "Office Workers", "group": "题材",
     "tag": "92d6d951-ca5e-429c-ac78-451071cbf064", "aliases": ["职场", "職場", "office"]},
    {"id": "timetravel", "name": "穿越", "en": "Time Travel", "group": "题材",
     "tag": "292e862b-2d17-4062-90a2-0356caa4ae27", "aliases": ["穿越", "时间旅行", "time travel"]},
    {"id": "reincarnation", "name": "重生", "en": "Reincarnation", "group": "题材",
     "tag": "0bc90acb-ccc1-44ca-a34a-b9f3a73259d0", "aliases": ["重生", "转生", "轉生", "reincarnation"]},
    {"id": "harem", "name": "后宫", "en": "Harem", "group": "题材",
     "tag": "aafb99c1-7f60-43fa-b75f-fc9502ce29c7", "aliases": ["后宫", "後宮", "harem"]},
    {"id": "reverse_harem", "name": "逆后宫", "en": "Reverse Harem", "group": "题材",
     "tag": "65761a2a-415e-47f3-bef2-a9dababba7a6", "aliases": ["逆后宫", "逆後宮", "reverse harem"]},
    {"id": "military", "name": "军事", "en": "Military", "group": "题材",
     "tag": "ac72833b-c4e9-4878-b9db-6c8a4a99444a", "aliases": ["军事", "軍事", "战争", "戰爭", "military", "战争军事"]},
    {"id": "magic", "name": "魔法", "en": "Magic", "group": "题材",
     "tag": "a1f53773-c69a-4ce5-8cab-fffcd90b1565", "aliases": ["魔法", "magic"]},
    {"id": "vampires", "name": "吸血鬼", "en": "Vampires", "group": "题材",
     "tag": "d7d1730f-6eb0-4ba6-9437-602cac38664c", "aliases": ["吸血鬼", "vampires", "vampire"]},
    {"id": "supernatural", "name": "灵异", "en": "Supernatural", "group": "题材",
     "tag": "eabc5b4c-6aff-42f3-b657-3e90cbd00b75", "aliases": ["灵异", "靈異", "超自然", "supernatural"]},
    {"id": "ghosts", "name": "鬼怪", "en": "Ghosts", "group": "题材",
     "tag": "3bb26d85-09d5-4d2e-880c-c34b974339e9", "aliases": ["鬼怪", "鬼魂", "ghosts"]},
    {"id": "demons", "name": "恶魔", "en": "Demons", "group": "题材",
     "tag": "39730448-9a5f-48a2-85b0-a70db87b1233", "aliases": ["恶魔", "惡魔", "demons"]},
    {"id": "monsters", "name": "怪物", "en": "Monsters", "group": "题材",
     "tag": "36fd93ea-e8b8-445e-b836-358f02b3d33d", "aliases": ["怪物", "monsters"]},
    {"id": "monster_girls", "name": "怪物娘", "en": "Monster Girls", "group": "题材",
     "tag": "dd1f77c5-dea9-4e2b-97ae-224af09caf99", "aliases": ["怪物娘", "monster girls"]},
    {"id": "martial_arts", "name": "武术", "en": "Martial Arts", "group": "题材",
     "tag": "799c202e-7daa-44eb-9cf7-8a3c0441531e", "aliases": ["武术", "武術", "格斗", "格鬥", "martial arts"]},
    {"id": "samurai", "name": "武士", "en": "Samurai", "group": "题材",
     "tag": "81183756-1453-4c81-aa9e-f6e1b63be016", "aliases": ["武士", "samurai"]},
    {"id": "ninja", "name": "忍者", "en": "Ninja", "group": "题材",
     "tag": "489dd859-9b61-4c37-af75-5b18e88daafc", "aliases": ["忍者", "ninja"]},
    {"id": "survival", "name": "生存", "en": "Survival", "group": "题材",
     "tag": "5fff9cde-849c-4d78-aab0-0d52b2ee1d25", "aliases": ["生存", "survival"]},
    {"id": "zombies", "name": "丧尸", "en": "Zombies", "group": "题材",
     "tag": "631ef465-9aba-4afb-b0fc-ea10efe274a8", "aliases": ["丧尸", "喪屍", "僵尸", "zombies"]},
    {"id": "mafia", "name": "黑道", "en": "Mafia", "group": "题材",
     "tag": "85daba54-a71c-4554-8a28-9901a8b0afad", "aliases": ["黑道", "黑手党", "mafia"]},
    {"id": "vr", "name": "虚拟现实", "en": "Virtual Reality", "group": "题材",
     "tag": "8c86611e-fab7-4986-9dec-d1a2f44acdd5", "aliases": ["虚拟现实", "虛擬現實", "vr", "virtual reality"]},
    {"id": "videogames", "name": "电子游戏", "en": "Video Games", "group": "题材",
     "tag": "9438db5a-7e2a-4ac0-b39e-e0d95a34b8a8", "aliases": ["电子游戏", "游戏", "video games"]},
    {"id": "apocalypse", "name": "末世", "en": "Post-Apocalyptic", "group": "题材",
     "tag": "9467335a-1b83-4497-9231-765337a00b96", "aliases": ["末世", "废土", "post-apocalyptic"]},
    {"id": "villainess", "name": "反派女主", "en": "Villainess", "group": "题材",
     "tag": "d14322ac-4d6f-4e9b-afd9-629d5f4d8a41", "aliases": ["反派女主", "恶役", "惡役", "villainess"]},
    {"id": "delinquents", "name": "不良", "en": "Delinquents", "group": "题材",
     "tag": "da2d50ca-3018-4cc0-ac7a-6b7d472a29ea", "aliases": ["不良", "delinquents"]},
    {"id": "police", "name": "警察", "en": "Police", "group": "题材",
     "tag": "df33b754-73a3-4c54-80e6-1a74a8058539", "aliases": ["警察", "police"]},
    {"id": "aliens", "name": "外星人", "en": "Aliens", "group": "题材",
     "tag": "e64f6742-c834-471d-8d72-dd51fc02b835", "aliases": ["外星人", "aliens"]},
    {"id": "animals", "name": "动物", "en": "Animals", "group": "题材",
     "tag": "3de8c75d-8ee3-48ff-98ee-e20a65c86451", "aliases": ["动物", "動物", "animals"]},
    {"id": "traditional_games", "name": "传统博弈", "en": "Traditional Games", "group": "题材",
     "tag": "31932a7e-5b8e-49a6-9f12-2afa39dc544c", "aliases": ["传统博弈", "棋牌", "麻将", "traditional games", "mahjong"]},
    {"id": "genderswap", "name": "性转", "en": "Genderswap", "group": "题材",
     "tag": "2bd2e8d0-f146-434a-9b51-fc9ff2c5fe6a", "aliases": ["性转", "性轉", "genderswap"]},
    {"id": "crossdressing", "name": "女装", "en": "Crossdressing", "group": "题材",
     "tag": "9ab53f92-3eed-4e9b-903a-917c86035ee3", "aliases": ["女装", "女裝", "crossdressing"]},
    {"id": "gyaru", "name": "辣妹", "en": "Gyaru", "group": "题材",
     "tag": "fad12b5e-68ba-460e-b933-9ae8318f5b65", "aliases": ["辣妹", "gyaru"]},
    # ---- format ----
    {"id": "oneshot", "name": "短篇", "en": "Oneshot", "group": "形制",
     "tag": "0234a31e-a729-4e28-9d6a-3f87c4966b9e", "aliases": ["短篇", "一发完", "oneshot"]},
    {"id": "longstrip", "name": "条漫", "en": "Long Strip", "group": "形制",
     "tag": "3e2b8dae-350e-4ab8-a8ce-016e844b9f0d", "aliases": ["条漫", "條漫", "长条", "long strip", "webtoon"]},
    {"id": "fourkoma", "name": "四格", "en": "4-Koma", "group": "形制",
     "tag": "b11fda93-8f1d-4bef-b2ed-8803d3733170", "aliases": ["四格", "4koma", "4-koma"]},
    {"id": "webcomic", "name": "网页漫画", "en": "Web Comic", "group": "形制",
     "tag": "e197df38-d0e7-43b5-9b09-2842d0c326dd", "aliases": ["网页漫画", "網頁漫畫", "web comic"]},
    {"id": "fullcolor", "name": "全彩", "en": "Full Color", "group": "形制",
     "tag": "f5ba408b-0e7a-484d-8d49-4e9125ac96de", "aliases": ["全彩", "full color"]},
    {"id": "official_colored", "name": "官方彩版", "en": "Official Colored", "group": "形制",
     "tag": "320831a8-4026-470b-94f6-8353740e6f04", "aliases": ["官方彩版", "official colored"]},
    {"id": "adaptation", "name": "改编", "en": "Adaptation", "group": "形制",
     "tag": "f4122d1c-3b44-44d0-9936-ff7502c39ad3", "aliases": ["改编", "改編", "adaptation"]},
    {"id": "award", "name": "获奖", "en": "Award Winning", "group": "形制",
     "tag": "0a39b5a1-b235-4886-a747-1d05d216532d", "aliases": ["获奖", "獲獎", "award"]},
    {"id": "anthology", "name": "选集", "en": "Anthology", "group": "形制",
     "tag": "51d83883-4103-437c-b4b1-731cb73d786c", "aliases": ["选集", "選集", "anthology"]},
    {"id": "doujinshi", "name": "同人", "en": "Doujinshi", "group": "形制",
     "tag": "b13b2a48-c720-44a9-9c77-39c9979373fb", "aliases": ["同人", "doujinshi"]},
    {"id": "selfpub", "name": "自制", "en": "Self-Published", "group": "形制",
     "tag": "891cf039-b895-47f0-9229-bef4c96eccd4", "aliases": ["自制", "自出版", "self-published"]},
    # ---- official demographic filters (not tags) ----
    {"id": "shounen", "name": "少年向", "en": "Shounen", "group": "读者",
     "demo": "shounen", "aliases": ["少年", "少年向", "shounen", "shonen"]},
    {"id": "shoujo", "name": "少女向", "en": "Shoujo", "group": "读者",
     "demo": "shoujo", "aliases": ["少女", "少女向", "shoujo", "shojo"]},
    {"id": "seinen", "name": "青年向", "en": "Seinen", "group": "读者",
     "demo": "seinen", "aliases": ["青年", "青年向", "seinen"]},
    {"id": "josei", "name": "女性向", "en": "Josei", "group": "读者",
     "demo": "josei", "aliases": ["女性", "女性向", "josei"]},
]

# 未收录的官方内容向标签（性暴力、血腥、以及不适合作为书城分类入口的条目）有意省略。
# 「治愈」在 MangaDex 无独立官方 tag，不编造；请用「日常」。
# 「长篇」无独立官方 tag（Long Strip 是条漫形制，不是长篇连载），不编造。

IA_SAFE = (
    " AND NOT collection:(inlibrary OR printdisabled OR lendinglibrary)"
    " AND NOT identifier:(z-library* OR zlib* OR zlibrary* OR anna-archive* OR annaarchive*"
    " OR sci-hub* OR scihub* OR manga_* )"
)

NOVEL_GENRES = [
    # 番茄式小说分类：每条绑定公开目录检索式，不抓取番茄/起点。
    {"id": "xuanhuan", "name": "玄幻", "icon": "🐉", "group": "男生",
     "blurb": "公有领域里的神魔与奇想（封神、西游、镜花缘等）。当代网络玄幻无法从公开源提供。",
     "sparse": True,
     "ws_queries": ["封神演義", "西遊記", "鏡花緣", "平妖傳", "東遊記"],
     "ia": "title:(封神演义 OR 西游记 OR 镜花缘 OR 平妖传 OR 东游记) AND mediatype:texts" + IA_SAFE,
     "ol_subject": "fantasy",
     "aliases": ["玄幻", "神魔"]},
    {"id": "qihuan", "name": "奇幻", "icon": "🧙", "group": "男生",
     "blurb": "公有领域奇幻与神话改编，来自 Archive、Open Library、Gutenberg 与 Standard Ebooks。",
     "gb_topic": "Fantasy", "ol_subject": "fantasy",
     "se_query": "fantasy",
     "ia": "subject:(fantasy OR mythological) AND mediatype:texts AND (collection:gutenberg OR creator:\"Standard Ebooks\")" + IA_SAFE,
     "aliases": ["奇幻文学", "奇幻", "fantasy"]},
    {"id": "wuxia", "name": "武侠", "icon": "⚔️", "group": "男生",
     "blurb": "公有领域侠义小说：三侠五义、儿女英雄传、水浒等。金庸、古龙等当代作品不在公开源中。",
     "sparse": True,
     "ws_queries": ["三俠五義", "七俠五義", "兒女英雄傳", "水滸傳", "小五義"],
     "ia": "title:(三侠五义 OR 七侠五义 OR 儿女英雄传 OR 水浒传 OR 小五义 OR 侠义) AND mediatype:texts" + IA_SAFE,
     "ol_subject": "wuxia",
     "aliases": ["武侠", "武俠", "江湖", "侠义"]},
    {"id": "xianxia", "name": "仙侠", "icon": "🧚", "group": "男生",
     "blurb": "公开源几乎没有当代仙侠网文。这里是封神、聊斋、镜花缘一类神魔志怪。",
     "sparse": True,
     "ws_queries": ["封神演義", "聊齋誌異", "鏡花緣", "搜神記"],
     "ia": "title:(封神演义 OR 聊斋志异 OR 镜花缘 OR 搜神记) AND mediatype:texts" + IA_SAFE,
     "aliases": ["仙侠", "仙俠"]},
    {"id": "dushi", "name": "都市", "icon": "🏙️", "group": "男生",
     "blurb": "当代都市爽文无法从公开源提供。这里是近代市井与都市生活题材的公有领域作品。",
     "sparse": True,
     "ws_queries": ["老殘遊記", "海上花列傳", "官場現形記", "二十年目睹之怪現狀"],
     "ia": "subject:(\"city and town life\" OR \"urban fiction\" OR \"social life and customs\") AND mediatype:texts AND (collection:gutenberg OR creator:\"Standard Ebooks\")" + IA_SAFE,
     "ol_subject": "city_and_town_life",
     "aliases": ["都市", "市井"]},
    {"id": "reality", "name": "现实", "icon": "🪟", "group": "女生",
     "blurb": "现实主义与社会题材：鲁迅等已进入公有领域的现代文学，以及西方写实名著。",
     "ws_queries": ["吶喊", "彷徨", "阿Q正傳", "狂人日記", "孔乙己", "祝福", "藥"],
     "ia": "(title:(呐喊 OR 彷徨 OR 阿Q正传) OR subject:realism) AND mediatype:texts" + IA_SAFE,
     "ol_subject": "realism", "gb_topic": "Realism",
     "aliases": ["现实", "現實", "写实"]},
    {"id": "romance_n", "name": "言情", "icon": "💕", "group": "女生",
     "blurb": "公有领域爱情小说：奥斯汀、勃朗特等言情名著，以及有公开文本的爱情题材。",
     "gb_topic": "Love stories", "ol_subject": "romance",
     "ia": "subject:(romance OR \"love stories\") AND mediatype:texts AND (collection:gutenberg OR creator:\"Standard Ebooks\")" + IA_SAFE,
     "aliases": ["言情", "爱情", "爱情文学", "romance"]},
    {"id": "ancient_romance", "name": "古代言情", "icon": "🌸", "group": "女生",
     "blurb": "古典爱情与戏曲：红楼梦、西厢记、牡丹亭等公有领域文本。",
     "ws_queries": ["紅樓夢", "西廂記", "牡丹亭", "長生殿", "霍小玉傳", "桃花扇"],
     "ia": "title:(红楼梦 OR 西厢记 OR 牡丹亭 OR 长生殿 OR 桃花扇) AND mediatype:texts" + IA_SAFE,
     "aliases": ["古代言情", "古典言情"]},
    {"id": "history", "name": "历史", "icon": "🏺", "group": "男生",
     "gb_topic": "History", "ol_subject": "history",
     "ws_queries": ["史記", "資治通鑒", "漢書", "三國志", "左傳"],
     "ia": "subject:history AND mediatype:texts AND (collection:gutenberg OR creator:\"Standard Ebooks\" OR language:(chi OR chinese))" + IA_SAFE,
     "aliases": ["历史", "歷史", "history"]},
    {"id": "military", "name": "军事", "icon": "🎖️", "group": "男生",
     "gb_topic": "War", "ol_subject": "war",
     "ia": "subject:(war OR military) AND mediatype:texts AND (collection:gutenberg OR creator:\"Standard Ebooks\")" + IA_SAFE,
     "aliases": ["军事", "軍事", "战争", "战争文学", "war"]},
    {"id": "scifi_book", "name": "科幻", "icon": "🚀", "group": "男生",
     "gb_topic": "Science fiction", "ol_subject": "science_fiction",
     "se_query": "science fiction",
     "ia": "subject:(\"science fiction\" OR scifi) AND mediatype:texts AND (collection:gutenberg OR creator:\"Standard Ebooks\")" + IA_SAFE,
     "aliases": ["科幻", "科幻小说", "science fiction"]},
    {"id": "game_n", "name": "游戏", "icon": "🎮", "group": "男生",
     "blurb": "公开源里几乎没有当代游戏网文，只收录与游戏、棋牌相关的公有领域文本。",
     "sparse": True,
     "ol_subject": "games",
     "ia": "subject:(games OR chess OR \"video games\") AND mediatype:texts AND (collection:gutenberg OR creator:\"Standard Ebooks\")" + IA_SAFE,
     "aliases": ["游戏", "遊戲"]},
    {"id": "sports_n", "name": "体育", "icon": "🏆", "group": "男生",
     "blurb": "公有领域体育与运动题材，数量有限。",
     "sparse": True,
     "ol_subject": "sports", "gb_topic": "Sports",
     "ia": "subject:sports AND mediatype:texts AND (collection:gutenberg OR creator:\"Standard Ebooks\")" + IA_SAFE,
     "aliases": ["体育", "體育"]},
    {"id": "suspense", "name": "悬疑", "icon": "🕵️", "group": "女生",
     "gb_topic": "Thriller", "ol_subject": "thriller",
     "ia": "subject:(thriller OR suspense) AND mediatype:texts AND (collection:gutenberg OR creator:\"Standard Ebooks\")" + IA_SAFE,
     "aliases": ["悬疑", "懸疑"]},
    {"id": "detective", "name": "推理", "icon": "🔎", "group": "女生",
     "gb_topic": "Detective", "ol_subject": "mystery",
     "se_query": "detective",
     "ia": "subject:(detective OR mystery OR crime) AND mediatype:texts AND (collection:gutenberg OR creator:\"Standard Ebooks\")" + IA_SAFE,
     "aliases": ["推理", "侦探", "偵探", "detective", "mystery"]},
    {"id": "spirit", "name": "灵异", "icon": "👻", "group": "男生",
     "blurb": "志怪与鬼怪故事：聊斋、搜神记，以及西方哥特与超自然公有领域作品。",
     "ws_queries": ["聊齋誌異", "搜神記", "閱微草堂筆記", "子不語"],
     "ia": "(title:(聊斋 OR 搜神记 OR 阅微草堂) OR subject:(\"ghost stories\" OR supernatural OR gothic)) AND mediatype:texts" + IA_SAFE,
     "ol_subject": "ghost_stories", "gb_topic": "Horror",
     "aliases": ["灵异", "靈異", "鬼怪", "志怪"]},
    {"id": "erciyuan", "name": "二次元", "icon": "🎀", "group": "女生",
     "blurb": "二次元长篇网文不在公开源中。请到漫画类型里浏览；此处仅列出极少相关的公开文本。",
     "sparse": True,
     "ol_subject": "comic_books_strips_etc",
     "ia": "subject:(\"graphic novels\" OR manga) AND mediatype:texts AND (rights:(public OR \"public domain\") OR collection:gutenberg)" + IA_SAFE,
     "aliases": ["二次元"]},
    {"id": "lightnovel", "name": "轻小说", "icon": "📗", "group": "女生",
     "blurb": "当代轻小说多为版权作品，公开源几乎没有可提供的目录，因此不会用无关名著来凑数。",
     "sparse": True,
     "ia": "subject:(\"light novel\" OR lightnovels) AND mediatype:texts" + IA_SAFE,
     "ol_subject": "light_novels",
     "aliases": ["轻小说", "輕小說"]},

    {"id": "classics", "name": "名著", "icon": "🏛️", "group": "名著",
     "blurb": "世界经典名著：Standard Ebooks、Gutenberg、Open Library 与维基文库中的公开文本。",
     "gb_topic": "Best Books Ever Listings",
     "ol_subject": "fiction",
     "ia": "mediatype:texts AND (collection:gutenberg OR creator:\"Standard Ebooks\")" + IA_SAFE,
     "ws_queries": ["紅樓夢", "西遊記"],
     "aliases": ["名著", "经典", "经典名著", "classics"]},
    {"id": "chinese_classic", "name": "中国古典", "icon": "📜", "group": "名著",
     "blurb": "中国古典经史与小说戏曲，来自维基文库与 Archive 公有领域扫描本。同一部书只保留一个最好的版本。",
     "ws_queries": ["紅樓夢", "西遊記", "三國演義", "水滸傳", "聊齋誌異", "儒林外史", "封神演義",
                    "金瓶梅", "古文觀止", "史記", "資治通鑒", "詩經", "楚辭", "論語", "孟子",
                    "道德經", "莊子", "左傳", "戰國策", "世說新語", "鏡花緣", "三俠五義",
                    "西廂記", "牡丹亭", "桃花扇", "吶喊", "阿Q正傳"],
     "ia": "title:(红楼梦 OR 西游记 OR 三国演义 OR 水浒传 OR 聊斋 OR 儒林外史 OR 史记 OR 诗经 OR 论语 OR 庄子 OR 镜花缘 OR 封神) AND mediatype:texts AND language:(chi OR chinese OR zho OR zh)" + IA_SAFE,
     "aliases": ["古典", "中国古典", "古籍"]},
    {"id": "poetry", "name": "诗歌", "icon": "💮", "group": "名著",
     "ws_queries": ["唐詩三百首", "宋詞三百首", "詩經", "楚辭", "花間集"],
     "gb_topic": "Poetry", "ol_subject": "poetry",
     "ia": "subject:poetry AND mediatype:texts AND (collection:gutenberg OR creator:\"Standard Ebooks\")" + IA_SAFE,
     "aliases": ["诗歌", "詩", "唐诗宋词", "poetry", "poems"]},
    {"id": "essay", "name": "散文", "icon": "✍️", "group": "名著",
     "ws_queries": ["古文觀止", "岳陽樓記", "醉翁亭記", "桃花源記", "出師表", "陳情表", "秋夜"],
     "ol_subject": "essays", "gb_topic": "Essays",
     "ia": "subject:essays AND mediatype:texts AND (collection:gutenberg OR creator:\"Standard Ebooks\")" + IA_SAFE,
     "aliases": ["散文", "随笔", "essays"]},
    {"id": "children", "name": "儿童", "icon": "🧸", "group": "名著",
     "gb_topic": "Children", "ol_subject": "juvenile_fiction",
     "se_query": "children",
     "ia": "subject:(children OR \"juvenile fiction\") AND mediatype:texts AND (collection:gutenberg OR creator:\"Standard Ebooks\")" + IA_SAFE,
     "aliases": ["儿童", "兒童", "少儿", "children"]},
    {"id": "popular_science", "name": "科普", "icon": "🔬", "group": "知识",
     "gb_topic": "Science", "ol_subject": "science",
     "ia": "subject:(science OR astronomy OR physics OR biology) AND mediatype:texts AND (collection:gutenberg OR creator:\"Standard Ebooks\")" + IA_SAFE,
     "aliases": ["科普", "科学", "科學", "science"]},
    {"id": "philosophy", "name": "哲学", "icon": "🧭", "group": "知识",
     "gb_topic": "Philosophy", "ol_subject": "philosophy",
     "ws_queries": ["論語", "孟子", "道德經", "莊子"],
     "ia": "subject:philosophy AND mediatype:texts AND (collection:gutenberg OR creator:\"Standard Ebooks\")" + IA_SAFE,
     "aliases": ["哲学", "哲學", "philosophy"]},
    {"id": "travel", "name": "游记", "icon": "🗺️", "group": "知识",
     "gb_topic": "Travel", "ol_subject": "travel",
     "ia": "subject:travel AND mediatype:texts AND (collection:gutenberg OR creator:\"Standard Ebooks\")" + IA_SAFE,
     "aliases": ["游记", "遊記", "travel"]},
    {"id": "biography", "name": "传记", "icon": "👤", "group": "知识",
     "gb_topic": "Biography", "ol_subject": "biography",
     "ia": "subject:biography AND mediatype:texts AND (collection:gutenberg OR creator:\"Standard Ebooks\")" + IA_SAFE,
     "aliases": ["传记", "傳記", "biography"]},
    {"id": "drama_book", "name": "戏剧", "icon": "🎭", "group": "名著",
     "gb_topic": "Drama", "ol_subject": "drama",
     "ws_queries": ["竇娥冤", "西廂記", "牡丹亭"],
     "ia": "subject:(drama OR plays) AND mediatype:texts AND (collection:gutenberg OR creator:\"Standard Ebooks\")" + IA_SAFE,
     "aliases": ["戏剧", "戲劇", "戏曲", "drama", "plays"]},
    {"id": "fairy", "name": "童话", "icon": "🧚", "group": "名著",
     "gb_topic": "Fairy tales", "ol_subject": "fairy_tales",
     "se_query": "fairy",
     "ia": "subject:(\"fairy tales\" OR folklore) AND mediatype:texts AND (collection:gutenberg OR creator:\"Standard Ebooks\")" + IA_SAFE,
     "aliases": ["童话", "童話", "fairy"]},
    {"id": "stdbooks", "name": "精校英文名著", "icon": "📘", "group": "名著",
     "se": "popular",
     "aliases": ["standard ebooks", "精校"]},
    {"id": "honglou", "name": "红楼梦", "icon": "🌸", "group": "专题",
     "ws_queries": ["紅樓夢"],
     "ia": "title:(红楼梦 OR 紅樓夢) AND mediatype:texts" + IA_SAFE,
     "aliases": ["红楼梦", "紅樓夢"]},
    {"id": "xiyou", "name": "西游记", "icon": "🐒", "group": "专题",
     "ws_queries": ["西遊記"],
     "ia": "title:(西游记 OR 西遊記) AND mediatype:texts" + IA_SAFE,
     "aliases": ["西游记", "西遊記"]},
    {"id": "sanguo", "name": "三国演义", "icon": "⚔️", "group": "专题",
     "ws_queries": ["三國演義"],
     "ia": "title:(三国演义 OR 三國演義) AND mediatype:texts" + IA_SAFE,
     "aliases": ["三国", "三国演义", "三國演義"]},
    {"id": "shuihu", "name": "水浒传", "icon": "🏹", "group": "专题",
     "ws_queries": ["水滸傳"],
     "ia": "title:(水浒传 OR 水滸傳) AND mediatype:texts" + IA_SAFE,
     "aliases": ["水浒", "水浒传", "水滸傳"]},
]

# Public-domain comics on Internet Archive only. Do NOT use raw collection:comics
# (it is full of modern unauthorized uploads). rights/public-domain filter was verified 2026-11-28.
IA_PD_COMICS = (
    'mediatype:texts AND (subject:comics OR subject:"comic books" OR subject:"comic strips")'
    ' AND (rights:(public OR "public domain" OR publicdomain) OR licenseurl:(*publicdomain* OR *public_domain* OR *cc0*))'
    + IA_SAFE
)

# 主页推荐频道。排序靠前的栏目优先保留封面，后面栏目不得重复同一部作品。
# 书架 / 继续阅读由前端单独渲染，允许重复用户正在读的书。
HOME_RAILS = [
    {"id": "md_romance", "title": "恋爱漫画", "kind": "manga", "genre": "romance"},
    {"id": "md_fantasy", "title": "奇幻漫画", "kind": "manga", "genre": "fantasy"},
    {"id": "md_isekai", "title": "异世界", "kind": "manga", "genre": "isekai"},
    {"id": "md_action", "title": "热血漫画", "kind": "manga", "genre": "action"},
    {"id": "md_slice", "title": "日常漫画", "kind": "manga", "genre": "slice"},
    {"id": "md_mystery", "title": "悬疑漫画", "kind": "manga", "genre": "mystery"},
    {"id": "md_completed", "title": "完结漫画", "kind": "rail", "via": "md_completed"},
    {"id": "md_latest", "title": "新作漫画", "kind": "rail", "via": "mangadex", "order": "latestUploadedChapter"},
    {"id": "md_popular", "title": "热门漫画", "kind": "rail", "via": "mangadex", "order": "followedCount"},
    {"id": "n_romance", "title": "言情名著", "kind": "novel", "genre": "romance_n"},
    {"id": "n_detect", "title": "侦探推理", "kind": "novel", "genre": "detective"},
    {"id": "n_scifi", "title": "科幻经典", "kind": "novel", "genre": "scifi_book"},
    {"id": "n_fantasy", "title": "奇幻经典", "kind": "novel", "genre": "qihuan"},
    {"id": "n_history", "title": "历史与传奇", "kind": "novel", "genre": "history"},
    {"id": "n_poetry", "title": "诗歌精选", "kind": "novel", "genre": "poetry"},
    {"id": "cn_classics", "title": "中国古典", "kind": "novel", "genre": "chinese_classic"},
    {"id": "se_new", "title": "精校新书", "kind": "rail", "via": "se_new"},
    {"id": "se_popular", "title": "精校英文名著", "kind": "novel", "genre": "stdbooks"},
    {"id": "pd_comics", "title": "公有领域漫画", "kind": "rail", "via": "ia_comics"},
]

NOVEL_GROUP_ORDER = ["女生", "男生", "名著", "知识", "专题"]


def manga_by_id(gid: str):
    gid = (gid or "").strip().lower()
    for g in MANGA_GENRES:
        if g["id"] == gid or g["name"] == gid or gid in [a.lower() for a in g.get("aliases") or []]:
            return g
    return None


def novel_by_id(gid: str):
    gid = (gid or "").strip().lower()
    for g in NOVEL_GENRES:
        if g["id"] == gid or g["name"] == gid or gid in [a.lower() for a in g.get("aliases") or []]:
            return g
    return None


def match_manga_query(q: str):
    """If the search box looks like a genre name, return that genre dict."""
    s = (q or "").strip().lower()
    if not s or len(s) > 16:
        return None
    for g in MANGA_GENRES:
        names = [g["id"], g["name"], g.get("en") or ""] + list(g.get("aliases") or [])
        if s in {n.lower() for n in names if n}:
            return g
    return None


def match_novel_query(q: str):
    s = (q or "").strip().lower()
    if not s or len(s) > 20:
        return None
    for g in NOVEL_GENRES:
        names = [g["id"], g["name"]] + list(g.get("aliases") or [])
        if s in {n.lower() for n in names if n}:
            return g
    return None


def public_genres():
    manga = [{k: g[k] for k in ("id", "name", "en", "group", "icon") if k in g} for g in MANGA_GENRES]
    novels = [{k: g[k] for k in ("id", "name", "icon", "group", "blurb", "sparse") if k in g} for g in NOVEL_GENRES]
    return {
        "manga": manga,
        "novels": novels,
        "manga_count": len(manga),
        "novel_count": len(novels),
        "novel_groups": list(NOVEL_GROUP_ORDER),
        "home_rails": [{"id": r["id"], "title": r["title"], "kind": r.get("kind")} for r in HOME_RAILS],
    }
