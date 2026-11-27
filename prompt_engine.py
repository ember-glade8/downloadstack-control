# -*- coding: utf-8 -*-
"""DownloadStack AI 画室专业提示词引擎：
1) 72+ 电影/摄影/概念艺术/商业/Wan2.2运镜大师级精品模板库（专为 Z-Image Turbo / Lumina2 与 Wan2.2 I2V 调优）
2) 中英双语语义同义词提示词搜索引擎 + 关键词动态多风格模板合成引擎（输入任何词都能秒出大量高质量定制模板）
3) 接入本机 Codex 中转智能体的「AI 提示词大师优化器」：把任意口语输入一键升格为 3 套不同风格的大师级提示词
   （电影写实版 / 概念美学版 / Wan2.2 电影运镜视频版），附中文拆解、精准负向词与推荐画幅。
"""

import json
import re
from typing import List, Dict, Any

DEFAULT_NEG_PHOTO = (
    "blurry, out of focus, lowres, oversaturated, plastic skin, waxy face, airbrushed, "
    "deformed hands, extra fingers, bad anatomy, watermark, text, logo, jpeg artifacts, harsh HDR"
)
DEFAULT_NEG_ANIME = (
    "lowres, bad anatomy, bad hands, extra digits, missing fingers, blurry, muddy colors, "
    "watermark, signature, text, cropped, ugly face, asymmetric eyes, flat lighting"
)
DEFAULT_NEG_VIDEO = (
    "static freeze frame, morphing face, flickering lights, jittery camera, warped limbs, "
    "extra fingers, blurry motion smear, watermark, subtitles, text overlay, low framerate"
)

PROMPT_CATEGORIES = [
    {"id": "all",       "name": "全部精选", "icon": "✨"},
    {"id": "portrait",  "name": "电影人像", "icon": "🎬"},
    {"id": "video",     "name": "Wan2.2运镜", "icon": "🎥"},
    {"id": "cyber",     "name": "赛博科幻", "icon": "🌆"},
    {"id": "guofeng",   "name": "古风仙侠", "icon": "🏯"},
    {"id": "anime",     "name": "唯美二次元", "icon": "🌸"},
    {"id": "landscape", "name": "史诗风光", "icon": "🏔️"},
    {"id": "product",   "name": "商业广告", "icon": "💎"},
    {"id": "fantasy",   "name": "魔幻史诗", "icon": "🐉"},
    {"id": "arch",      "name": "建筑空间", "icon": "🏛️"},
    {"id": "food",      "name": "美食静物", "icon": "🍜"},
    {"id": "creature",  "name": "萌宠神兽", "icon": "🦊"},
    {"id": "abstract",  "name": "3D海报", "icon": "🌀"},
]

# 中英文视觉概念双向语义映射（提升中文搜索命中率与动态模板精准度）
CN_EN_CONCEPTS = {
    "女孩": "young woman", "少女": "young East Asian girl", "美女": "elegant young woman",
    "男人": "charismatic man", "少年": "young man", "剑客": "wandering swordsman",
    "侠客": "martial arts hero", "仙女": "celestial fairy maiden", "机甲": "futuristic mecha",
    "机娘": "cybernetic mecha girl", "机器人": "sleek humanoid robot", "宇航员": "astronaut",
    "海边": "seaside coastline", "大海": "vast midnight ocean", "海滩": "sandy ocean beach",
    "夕阳": "golden hour sunset", "晚霞": "crimson and amber twilight sky", "日出": "misty golden sunrise",
    "雨夜": "rain-soaked midnight city street", "下雨": "falling rain", "暴雨": "heavy downpour storm",
    "雪": "drifting winter snow", "雪山": "towering snow-capped alpine peaks", "星空": "milky way starry night sky",
    "月亮": "luminous full moon", "极光": "shimmering emerald aurora borealis",
    "赛博": "cyberpunk futuristic", "赛博朋克": "cyberpunk neon metropolis", "霓虹": "glowing neon reflections",
    "科幻": "cinematic sci-fi", "宇宙": "deep space nebula", "飞船": "colossal starship", "黑洞": "gargantuan glowing black hole",
    "古风": "traditional Chinese ink-wash elegance", "汉服": "flowing embroidered silk hanfu",
    "仙侠": "ethereal Chinese xianxia fantasy", "江湖": "misty wuxia bamboo riverscape",
    "江南": "misty Jiangnan water town", "长安": "imperial Tang dynasty Chang'an lantern night",
    "樱花": "drifting cherry blossom petals", "森林": "sunlit ancient enchanted forest",
    "花海": "endless blooming flower meadow", "沙漠": "sweeping golden desert dunes",
    "跑车": "sleek aerodynamic hypercar", "汽车": "luxury sports car", "摩托": "futuristic cyber motorcycle",
    "猫": "fluffy ragdoll cat", "狗": "expressive golden retriever", "狐狸": "mystical nine-tailed white fox",
    "龙": "colossal eastern celestial dragon", "鲸鱼": "giant bioluminescent sky whale",
    "咖啡": "artisan espresso latte", "拉面": "steaming artisanal Japanese ramen", "美食": "gourmet culinary dish",
    "香水": "luxury faceted crystal perfume bottle", "手表": "Swiss mechanical luxury wristwatch",
    "耳机": "flagship brushed-titanium studio headphones", "建筑": "minimalist architectural masterpiece",
    "客厅": "serene wabi-sabi minimalist living room", "图书馆": "grand sunlit cathedral library",
    "动漫": "high-budget Japanese anime film still", "二次元": "exquisite anime concept illustration",
    "新海诚": "Makoto Shinkai luminous sky anime aesthetic", "吉卜力": "hand-painted Studio Ghibli pastoral warmth",
    "写实": "photorealistic 35mm cinema still", "胶片": "Kodak Portra 400 analog film photography",
    "暗黑": "moody dark chiaroscuro cinematography", "治愈": "warm peaceful sunlit healing atmosphere",
    "特写": "intimate shallow-depth close-up shot", "航拍": "sweeping aerial drone cinematography",
    "视频": "cinematic smooth camera movement video", "慢动作": "ultra-smooth high-speed slow motion",
    "撑伞": "holding a translucent rain umbrella", "回眸": "gently turning back with an expressive gaze",
    "奔跑": "running dynamically forward", "跳舞": "gracefully dancing in flowing fabric",
    "战斗": "epic dynamic combat action", "魔法": "swirling luminous arcane magic",
    "火焰": "glowing embers and rising firelight", "水下": "bioluminescent deep underwater world",
    "一剑开天门": "a transcendent Chinese xianxia swordsman cleaving the storm-filled heavens open with a single blazing celestial sword arc, parting towering clouds to reveal a colossal golden heavenly gate",
    "天门": "colossal radiant celestial heavenly gate amidst parting thunderclouds",
    "剑": "gleaming ancient sword radiating ethereal energy",
    "仙": "ethereal Chinese immortal xianxia realm",
    "神": "mythic divine celestial majesty",
    "武侠": "classic Chinese wuxia martial arts cinema",
    "云海": "endless billowing sunlit sea of clouds",
    "雷电": "crackling bolts of celestial lightning",
    "雪夜": "quiet snow-covered midnight atmosphere",
    "古亭": "ancient wooden pavilion with curved eaves",
    "竹林": "misty emerald bamboo forest",
    "水墨": "flowing traditional ink-wash cloud atmosphere",
    "海": "vast shimmering ocean", "雨": "falling rain", "花": "blooming delicate flowers",
    "月": "luminous glowing moon", "星": "glittering starry cosmos", "城": "towering atmospheric city",
}

def _tpl(cid, title, tags, summary, prompt, neg=None, size="1024x576", mode="t2i"):
    return {
        "cat": cid,
        "title": title,
        "tags": tags,
        "summary": summary,
        "prompt": prompt,
        "neg_prompt": neg or (DEFAULT_NEG_VIDEO if mode in ("t2v", "i2v") else (DEFAULT_NEG_ANIME if cid == "anime" else DEFAULT_NEG_PHOTO)),
        "size": size,
        "mode": mode,
        "source": "大师精选库",
    }

# ==================================================================
# 72+ 电影/商业/艺术/运镜大师级精选模板库（专为 Z-Image Turbo & Wan2.2 精调）
# ==================================================================
MASTER_PROMPTS: List[Dict[str, Any]] = [
    # ---------- 1. 电影写实人像 (portrait) ----------
    _tpl("portrait", "王家卫式雨夜霓虹人像", "人像 电影 霓虹 雨夜 胶片 港风 女孩",
         "35mm 电影胶片感、湿润霓虹玻璃折射、冷暖高反差情绪光",
         "Cinematic 35mm film still of a contemplative young East Asian woman standing beside a rain-streaked glass window in a dimly lit Hong Kong noodle shop at midnight, warm tungsten interior light contrasting with blurred emerald and crimson neon street reflections outside, natural skin texture with tiny water droplets on her coat collar, shot on ARRI Alexa with 50mm anamorphic lens f/1.4, subtle halation, organic film grain, Wong Kar-wai visual mood",
         size="1024x576", mode="t2i"),
    _tpl("portrait", "海边黄金时刻逆光少女", "人像 海边 夕阳 逆光 唯美 胶片 少女",
         "85mm f/1.4 浅景深、夕阳发丝轮廓光、海风吹拂自然抓拍",
         "Candid natural-light portrait of a young woman standing barefoot near gentle ocean waves at golden hour sunset, warm amber sunlight illuminating flying strands of dark hair as a luminous rim light, linen white dress billowing softly in the sea breeze, shimmering ocean horizon melted into creamy bokeh behind her, shot on Contax G2 85mm f/1.4, Kodak Portra 400 color science, authentic candid emotion, subtle film grain",
         size="576x1024", mode="t2i"),
    _tpl("portrait", "伦勃朗光古典质感肖像", "人像 棚拍 伦勃朗 高级感 写实 肖像",
         "中画幅哈苏棚拍、细腻皮肤纹理、经典三角侧光与深邃暗调",
         "Museum-grade medium-format editorial portrait of a poised woman in a tailored dark charcoal wool turtleneck against a textured slate backdrop, classic Rembrandt directional key light sculpting cheekbones and casting soft dramatic shadow, crisp catchlights in expressive dark eyes, ultra-authentic skin pores and fine cashmere fibers, shot on Hasselblad X2D 90mm f/2.5, rich tonal gradations, zero retouching artifacts",
         size="576x1024", mode="t2i"),
    _tpl("portrait", "冬日飘雪红围巾胶片抓拍", "人像 雪景 冬天 少女 日系 胶片 治愈",
         "大雪飘落景深虚化、冷调雪夜与暖红围巾撞色、自然呼吸白雾",
         "Intimate winter street portrait of a young woman wearing a hand-knitted crimson wool scarf and dark overcoat under gently falling snow at dusk, soft snowflakes caught on her eyelashes and dark hair, warm glowing streetlamp bokeh balls dissolving into twilight blue haze behind her, faint warm breath visible in cold air, shot on Leica M11 50mm f/1.2, delicate pastel highlights, authentic cinematic warmth",
         size="576x1024", mode="t2i"),
    _tpl("portrait", "高定时尚杂志银白光影大片", "人像 时尚 杂志 商业 高级 银白 极简",
         "建筑级几何硬光、镜面金属服饰质感、Vogue 封面级构图",
         "High-fashion Vogue editorial portrait of an avant-garde model wearing sculptural pleated liquid-silver silk couture in a minimalist concrete gallery, sharp architectural shaft of natural skylight cutting diagonally across the frame, crisp specular reflections along metallic fabric folds, composed with bold negative space, shot on Phase One IQ4 150MP 80mm, ultra-clean studio color grading",
         size="576x1024", mode="t2i"),
    _tpl("portrait", "午后阳光书店文艺侧颜", "人像 书店 阳光 治愈 胶片 文艺 侧颜",
         "百叶窗斜射暖光、漂浮微尘粒子、安静松弛的电影定格",
         "Peaceful cinematic side-profile portrait of a young woman reading beside a tall wooden bookshelf in an antique sunlight-drenched bookstore, warm afternoon sunbeams filtering through slatted blinds and illuminating drifting dust motes in the air, soft linen sweater texture, gentle natural shadow falloff, shot on Fujifilm GFX100 63mm f/2.0, nostalgic warm amber and forest green tones",
         size="1024x576", mode="t2i"),
    _tpl("portrait", "雨夜车窗后座氛围感特写", "人像 车窗 雨夜 孤独 电影 氛围",
         "车内微弱仪表光与窗外城市散景交织、极强电影故事感",
         "Moody cinematic close-up from inside a parked car at midnight during a gentle rain, a young person resting their cheek lightly against the cool raindrop-covered window glass, blurred warm amber traffic lights and cool cyan city signage refracting across wet glass droplets onto their face, shallow depth of field, shot on Sony Venice 65mm anamorphic lens, quiet melancholic beauty",
         size="1024x576", mode="t2i"),
    _tpl("portrait", "西部荒漠复古胶片公路人像", "人像 公路 荒漠 复古 夕阳 电影",
         "宽银幕公路电影构图、暖沙色调、复古机车与落日长影",
         "Wide-screen road-movie still of a traveler leaning against a weathered vintage 1970s muscle car along an endless desert highway at magic hour, swirling golden dust kicked up by desert wind, vast crimson canyon mesas silhouetted against a deep violet-amber sky, lens flare kissing the horizon, shot on Panavision 35mm anamorphic film, Kodak Vision3 250D palette",
         size="1024x576", mode="t2i"),

    # ---------- 2. Wan 2.2 电影运镜视频专属 (video) ----------
    _tpl("video", "【运镜】雨夜霓虹少女撑伞慢回头", "视频 运镜 雨夜 霓虹 少女 回眸 慢动作",
         "Wan2.2 专属：缓慢环绕推镜 + 透明雨伞水珠滑落 + 霓虹反光流动",
         "Cinematic slow-motion video shot, smooth steady dolly-in orbiting gently around a young woman holding a clear umbrella on a rain-soaked Tokyo neon street at midnight, she slowly turns her head toward the camera with a quiet serene smile as rain streaks glisten through glowing cyan and magenta bokeh behind her, wind softly lifting strands of her hair, wet asphalt rippling with reflected neon light, natural fluid motion, 24fps film cinematography",
         size="832x480", mode="t2v"),
    _tpl("video", "【运镜】海边夕阳长裙随风漫步", "视频 运镜 海边 夕阳 少女 海浪 治愈",
         "Wan2.2 专属：侧向滑轨跟拍 + 潮水轻拍沙滩 + 夕阳波光闪烁",
         "Smooth lateral tracking camera shot following a woman in a flowing white linen dress walking slowly along the wet shoreline at golden hour sunset, translucent ocean waves rolling gently over her ankles and leaving shimmering foam, warm golden sunbeams rippling across the water surface, her long hair and dress fabric billowing naturally in the coastal breeze, dreamy cinematic lens glow, seamless continuous motion",
         size="832x480", mode="t2v"),
    _tpl("video", "【运镜】航拍穿越云海日照金山", "视频 运镜 航拍 雪山 云海 日出 史诗",
         "Wan2.2 专属：无人机缓慢拉升前推 + 云海翻涌 + 金光铺满雪峰",
         "Majestic aerial drone shot gliding smoothly forward and rising gently above a vast billowing sea of white clouds toward jagged snow-capped Himalayan mountain peaks at dawn, warm golden sunrise light gradually illuminating the icy ridges while mist flows like a slow river through the valleys below, breathtaking documentary IMAX cinematography, silky stable aerial motion",
         size="832x480", mode="t2v"),
    _tpl("video", "【运镜】古风白衣剑客竹林挥剑落叶", "视频 运镜 古风 仙侠 竹林 剑客 慢动作",
         "Wan2.2 专属：低角度环绕升格 + 翠绿竹叶盘旋飞舞 + 晨雾流动",
         "Epic wuxia slow-motion video, low-angle sweeping arc camera circling a white-robed Chinese swordsman standing amidst a misty emerald bamboo forest at dawn, shafts of golden morning sunlight piercing through swaying bamboo stalks, as he draws his gleaming sword a swirling vortex of fallen bamboo leaves and morning mist rises gracefully around his flowing silk sleeves, crisp fluid cinematic physics",
         size="832x480", mode="t2v"),
    _tpl("video", "【运镜】赛博超跑雨夜隧道极速穿梭", "视频 运镜 跑车 赛博 霓虹 速度 追拍",
         "Wan2.2 专属：贴地低机位追焦 + 车尾激光拖影 + 积水飞溅",
         "High-octane low-angle chase camera tracking a sleek matte-black futuristic hypercar speeding through a rain-drenched neon metropolitan tunnel at night, luminous cyan and crimson overhead light strips streaking rapidly across the glossy wet carbon-fiber bodywork, fine sheets of water spray erupting behind spinning tires, dynamic motion blur on background pillars, crisp focus on the car, Hollywood blockbuster cinematography",
         size="832x480", mode="t2v"),
    _tpl("video", "【运镜】深海发光水母群优雅游弋", "视频 运镜 深海 水母 荧光 唯美 慢镜头",
         "Wan2.2 专属：水下失重缓推 + 透明伞盖律动 + 生物荧光粒子",
         "Mesmerizing underwater slow-motion video, camera floating gently forward through a deep sapphire ocean abyss filled with translucent bioluminescent jellyfish pulsing rhythmically in electric cyan and soft violet glow, delicate trailing tentacles undulating silkily in underwater currents, shimmering sunlight caustic beams filtering down from the distant surface, peaceful hypnotic atmosphere",
         size="832x480", mode="t2v"),
    _tpl("video", "【运镜】篝火火星夜空慢升格特写", "视频 运镜 篝火 夜晚 火星 治愈 氛围",
         "Wan2.2 专属：固定微距缓推 + 橘红火焰跳跃 + 发光火星盘旋升空",
         "Hypnotic macro slow-motion video with subtle steady push-in on a glowing outdoor campfire at twilight beneath pine silhouettes, rich amber flames dancing organically over glowing charcoal embers while hundreds of bright golden sparks spiral gracefully upward into the deep indigo night sky, warm flickering rim light, ultra-clean natural fire physics",
         size="832x480", mode="t2v"),
    _tpl("video", "【运镜】精品咖啡拉花微距升格广告", "视频 运镜 咖啡 美食 商业 广告 慢动作",
         "Wan2.2 专属：商业高速摄影缓移 + 丝滑奶泡倾注 + 热气袅袅升腾",
         "Luxury commercial slow-motion macro video, smooth gentle push-in as velvety steamed milk pours gracefully from a brushed-steel pitcher into rich golden crema espresso inside a handcrafted matte ceramic cup, delicate rosetta latte art blooming smoothly across the surface while wisps of warm steam curl through a shaft of morning cafe sunlight, shallow f/2.0 depth of field, appetizing warm tones",
         size="832x480", mode="t2v"),

    # ---------- 3. 赛博与科幻 (cyber) ----------
    _tpl("cyber", "赛博朋克暴雨立体巨城全景", "赛博 科幻 城市 霓虹 雨夜 未来 8K",
         "银翼杀手 2049 级史诗纵深、悬浮飞车流、巨型全息投影与雾雨",
         "Colossal Blade Runner 2049 inspired cyberpunk megacity at midnight in pouring rain, towering brutalist megastructures wrapped in towering translucent holographic Japanese and Chinese neon billboards, streams of flying spinner vehicles weaving through misty volumetric searchlight beams between skyscraper canyons, glistening rain-slicked skybridges far below, shot on 24mm anamorphic IMAX cinema lens, deep teal and neon magenta atmosphere",
         size="1024x576", mode="t2i"),
    _tpl("cyber", "次时代重装机甲地下整备库", "机甲 科幻 赛博 工业 史诗 机械",
         "巨物压迫感低角度仰拍、机械液压纹理、焊接火花与蒸汽灯光",
         "Awe-inspiring low-angle concept art inside a cavernous subterranean hangar housing an 18-meter weathered white-and-cobalt tactical combat mecha suspended on steel gantry cranes, glowing cyan reactor vents illuminating drifting hydraulic steam, tiny ground technicians in high-vis gear working along illuminated catwalks for massive scale contrast, volumetric overhead floodlights, photorealistic industrial hard-surface wear and decals",
         size="1024x576", mode="t2i"),
    _tpl("cyber", "赛博机甲少女全息驾驶舱", "机甲 少女 赛博 科幻 霓虹 人像",
         "科技纤维战衣、透明全息战术 HUD 映射脸庞、精致机械细节",
         "Hyper-detailed sci-fi portrait of a poised cybernetic pilot girl inside a dark futuristic mecha cockpit, wearing sleek matte-white and titanium neural-link armor with glowing cyan optical fiber seams, floating translucent 3D holographic telemetry displays casting cool azure light across her focused eyes and subtle facial tech markings, crisp depth of field, cinematic AAA game key art quality",
         size="576x1024", mode="t2i"),
    _tpl("cyber", "深空黑洞吸积盘与孤寂星舰", "科幻 宇宙 黑洞 飞船 太空 史诗",
         "星际穿越级物理引力透镜、炽白吸积盘光环、极小星舰对比尺度",
         "Breathtaking hard sci-fi space panorama inspired by Interstellar, a gargantuan spinning black hole bending starlight into a blazing golden-white gravitational lensing accretion disk across the pitch-black cosmos, a solitary intricately detailed exploration starship with tiny illuminated observation decks drifting silently in the foreground, dramatic rim lighting, IMAX 70mm space cinematography",
         size="1024x576", mode="t2i"),
    _tpl("cyber", "赛博霓虹雨巷重型机车骑手", "赛博 摩托 机车 霓虹 雨夜 炫酷",
         "低机位广角张力、水洼镜面倒影、头盔全息面罩与尾灯光痕",
         "Dramatic low-angle cinematic shot of a lone rider astride a sleek carbon-fiber futuristic cyberpunk motorcycle idling in a narrow neon-lit rain-soaked alleyway, glowing crimson visor helmet reflecting towering holographic kanji signs, puddle on cracked asphalt acting as a crisp mirror, mist swirling around glowing wheel rims, rich neon teal, electric violet and hot pink lighting",
         size="1024x576", mode="t2i"),
    _tpl("cyber", "未来悬浮玻璃生态穹顶都市", "科幻 未来 城市 生态 建筑 日光",
         "明亮太阳朋克乌托邦、水晶巨穹、悬浮磁轨与瀑布花园",
         "Utopian solarpunk future metropolis bathed in crisp morning sunlight, soaring organic white titanium-and-glass skyscrapers draped in lush vertical hanging gardens and cascading waterfalls, sleek silent maglev sky-trains gliding smoothly along luminous glass viaducts over emerald canals, clear azure sky with towering sunlit cumulus clouds, visionary architectural cinema render",
         size="1024x576", mode="t2i"),

    # ---------- 4. 古风与仙侠 (guofeng) ----------
    _tpl("guofeng", "仙侠云巅浮空玉阙仙宫", "古风 仙侠 建筑 浮空城 云海 史诗",
         "云海之上玉石琼楼、瀑布直泻云渊、仙鹤齐飞与金辉丁达尔光",
         "Grand Chinese xianxia fantasy landscape of a celestial jade-and-gold immortal palace complex perched atop floating misty karst mountain islands high above an endless sunlit sea of clouds, luminous silver waterfalls cascading into the abyss, graceful white cranes soaring through golden volumetric sunbeams, intricate curved pavilion eaves glowing softly, epic cinematic concept art",
         size="1024x576", mode="t2i"),
    _tpl("guofeng", "江南烟雨青石桥乌篷孤舟", "古风 江南 烟雨 水墨 治愈 风景",
         "烟雨朦胧青瓦白墙、油纸伞倒影、温润电影青绿水墨影调",
         "Poetic cinematic scene of a tranquil misty Jiangnan ancient water town at dawn during gentle spring rain, a lone wooden black-canopy boat gliding silently beneath an arched moss-kissed stone bridge, a figure in pale celadon silk hanfu holding a translucent oiled-paper umbrella, warm amber lanterns glowing softly along wet cobblestone alleys and shimmering on rippled emerald canal water, serene Chinese aesthetic cinematography",
         size="1024x576", mode="t2i"),
    _tpl("guofeng", "白衣古风剑客雪夜红梅古亭", "古风 剑客 雪景 红梅 武侠 唯美",
         "漫天飞雪与灼目红梅碰撞、灯笼暖光映白衣、极具电影江湖意境",
         "Cinematic Chinese wuxia scene at dusk in a snowfall, a solitary swordsman in flowing ivory silk robes standing beside a crimson-lacquered wooden pavilion surrounded by gnarled ancient plum trees bursting with vivid red blossoms covered in fresh snow, warm paper lantern casting soft amber light across falling snowflakes and a jade-hilted sword, dramatic atmospheric depth, 35mm epic film still",
         size="1024x576", mode="t2i"),
    _tpl("guofeng", "盛唐长安上元夜万灯长街", "古风 长安 灯会 盛唐 夜景 繁华",
         "朱雀大街万盏灯笼如星河、阁楼飞檐与游人汉服、史诗电影调度",
         "Magnificent Tang dynasty Chang'an Lantern Festival night panorama, bustling imperial avenue lined with soaring multi-tiered wooden pavilions draped in thousands of glowing vermilion and golden silk lanterns stretching into misty distance, citizens in vibrant brocade hanfu strolling under drifting sky lanterns ascending into a deep indigo sky, rich golden-amber firelight and theatrical atmospheric haze, epic historical cinema",
         size="1024x576", mode="t2i"),
    _tpl("guofeng", "敦煌飞天岩彩壁画神韵少女", "古风 敦煌 飞天 汉服 华丽 艺术",
         "石青朱砂金箔岩彩质感、丝绸飘带飞扬、庄严华美的东方美学",
         "Exquisite Dunhuang Mogao murals inspired art portrait of a celestial flying apsara maiden adorned in intricate mineral-pigment lapis lazuli, cinnabar red, and hammered gold-leaf silk drapery, long weightless translucent ribbons swirling gracefully around her amidst drifting incense clouds and golden lotus petals, luminous ethereal backlighting, museum-grade neo-Chinese fine art realism",
         size="576x1024", mode="t2i"),
    _tpl("guofeng", "青绿山水千里江山云雾奇峰", "古风 水墨 山水 风景 意境 东方",
         "矿物石青石绿与真实体积云雾融合、宏阔宁静的东方审美大片",
         "Breathtaking modern cinematic reinterpretation of classical Chinese blue-green shanshui landscape painting, towering sheer jade and malachite mountain peaks emerging from flowing silk-like silver valley mist, delicate golden sunrise light grazing ancient twisted pine trees and a tiny wooden cliffside hermitage, harmonious blend of photorealistic atmospheric depth and traditional mineral-pigment palette",
         size="1024x576", mode="t2i"),

    # ---------- 5. 唯美二次元 / 新海诚 (anime) ----------
    _tpl("anime", "新海诚式海边电车黄昏少女", "二次元 动漫 新海诚 夕阳 海边 少女 唯美",
         "通透积雨云与橘粉晚霞、铁道海面反光、极致光影动漫电影帧",
         "Breathtaking high-budget Japanese anime film still in Makoto Shinkai aesthetic, a high-school girl in a crisp navy sailor uniform standing at a quiet coastal train crossing beside sparkling turquoise ocean waves at sunset, towering glowing cumulus clouds painted in peach, coral and deep cobalt blue, dazzling golden sunlight flaring across steel railway tracks and her wind-swept hair, ultra-detailed cel shading and painterly background art",
         size="1024x576", mode="t2i"),
    _tpl("anime", "星空流星雨天台治愈系双人", "二次元 动漫 星空 流星 治愈 夜晚 唯美",
         "满天银河与流星划过、微风校服与城市远景灯火、直击心灵的青春感",
         "Emotional Japanese anime movie climax scene on a quiet school rooftop at midnight, two young silhouettes gazing up as a brilliant violet-and-cyan comet splits across a crystal-clear Milky Way sky showered with delicate shooting stars, warm city lights twinkling far below, soft wind ruffling hair and jackets, luminous lens bloom, exquisite cinematic anime background painting",
         size="1024x576", mode="t2i"),
    _tpl("anime", "樱花坡道春日阳光校服插画", "二次元 动漫 樱花 少女 春天 校园 唯美",
         "漫天樱花瓣飞舞、通透逆光发丝、清新柔和的日系剧场版画质",
         "Radiant anime key visual of a smiling anime girl walking down a sunlit hillside stone path lined with ancient blooming sakura trees, thousands of translucent pink cherry blossom petals swirling through golden morning sunbeams, dappled leaf shadows dancing across her crisp spring uniform, bright airy depth of field, Kyoto Animation inspired luminous color palette",
         size="576x1024", mode="t2i"),
    _tpl("anime", "奇幻魔法星辰古书库少女", "二次元 动漫 魔法 奇幻 少女 图书馆 华丽",
         "哥特穹顶悬浮魔导书、星轨魔法阵暖金微光、厚涂概念原画级细节",
         "Lush semi-realistic anime fantasy illustration of a young silver-haired mage girl standing inside a soaring circular arcane library filled with floating glowing spellbooks and brass astrolabes, warm golden candlelight and swirling sapphire rune particles illuminating her intricate embroidered velvet cloak, towering arched stained-glass windows letting in moonlight, masterpiece concept illustration",
         size="576x1024", mode="t2i"),
    _tpl("anime", "吉卜力夏日乡间巴士站积雨云", "二次元 动漫 吉卜力 夏天 治愈 风景 宫崎骏",
         "手绘水彩笔触、碧绿稻田与巨大蓬松白云、怀旧宁静的夏日午后",
         "Nostalgic hand-painted Studio Ghibli style pastoral anime landscape of a weathered wooden rural bus stop beside a sun-drenched emerald rice field and sparkling creek in midsummer, massive billowing ivory cumulus clouds towering against a vivid cerulean sky, bright red wildflowers swaying along a dirt path, warm gentle breeze, rich gouache brush texture and heartwarming serenity",
         size="1024x576", mode="t2i"),

    # ---------- 6. 史诗风光与自然 (landscape) ----------
    _tpl("landscape", "冰岛黑沙滩翡翠极光银河之夜", "风景 极光 冰岛 海滩 星空 摄影 史诗",
         "14mm 超广角延时摄影感、湿润黑沙滩倒映漫天极光与冰晶碎块",
         "Award-winning National Geographic night landscape photograph of Iceland Diamond Beach, crystal-clear sculptural glacier ice blocks scattered across glossy wet volcanic black sand mirroring vivid dancing emerald and violet aurora borealis curtains across a crisp starry Arctic sky, subtle icy sea mist, shot on Nikon Z9 14mm f/1.8, extraordinary dynamic range and clarity",
         size="1024x576", mode="t2i"),
    _tpl("landscape", "荧光生物深海玻璃海底圣殿", "深海 海洋 荧光 奇观 科幻 唯美",
         "幽蓝深海体积光、透明发光水母与全景玻璃穹顶、梦幻静谧",
         "Ethereal deep-sea architectural wonder, a translucent glass underwater observatory sanctuary resting on a coral abyssal ridge surrounded by glowing bioluminescent jellyfish and drifting cyan plankton, luminous shafts of filtered sunlight descending through crystal sapphire ocean depths, delicate caustic light patterns rippling over smooth stone floors, breathtaking cinematic photography",
         size="1024x576", mode="t2i"),
    _tpl("landscape", "热带雨林瀑布丁达尔晨光秘境", "风景 瀑布 森林 阳光 治愈 自然 摄影",
         "茂密蕨类苔藓、丝绸般流水长曝光、破雾而出的神圣丁达尔光束",
         "Breathtaking nature photograph of a hidden emerald waterfall cascading down moss-draped basalt cliffs into a crystal-clear turquoise lagoon deep inside a misty tropical rainforest at sunrise, dramatic golden crepuscular sunbeams piercing through dense canopy mist, silky long-exposure water motion, lush dewy ferns in crisp foreground focus, Hasselblad medium-format realism",
         size="1024x576", mode="t2i"),
    _tpl("landscape", "撒哈拉金色沙丘月光星空露营", "风景 沙漠 星空 夜晚 极简 治愈",
         "S形流畅沙脊光影线条、暖光孤帐与璀璨银河、顶级孤独美学",
         "Serene wide-angle night photograph of sweeping sculptural sand dunes in the Sahara desert under an ultra-crisp glowing Milky Way arch, a solitary warm amber-lit canvas expedition tent nestled gently in the dune valley casting soft golden light over rippled wind-carved sand ridges, cool deep indigo moonlight contrasting with cozy firelight, ultra-detailed photographic clarity",
         size="1024x576", mode="t2i"),
    _tpl("landscape", "富士山樱花晨雾湖面倒影", "风景 富士山 樱花 日本 晨雾 治愈",
         "镜面湖泊完美倒影、雪顶朝霞粉金光泽、前景盛开樱枝框景",
         "Tranquil sunrise landscape photograph of snow-capped Mount Fuji glowing softly in pale rose-gold alpenglow, perfectly reflected in the glass-calm surface of Lake Kawaguchi while delicate wisps of morning mist drift across the water, blooming pink cherry blossom branches gracefully framing the upper corner, crisp tranquil Japanese fine-art photography",
         size="1024x576", mode="t2i"),

    # ---------- 7. 商业产品与广告 (product) ----------
    _tpl("product", "高奢水晶香水悬空水波折射大片", "产品 香水 商业 广告 奢华 棚拍 微距",
         "高速冻结晶莹水花、琥珀色液体光学焦散、顶级奢侈品广告视觉",
         "Ultra-luxury commercial product photograph of a minimalist faceted crystal perfume bottle filled with glowing amber elixir levitating subtly above dark obsidian water, frozen crystal-clear water splash crown catching razor-sharp studio rim lights, warm golden optical caustics refracting across black slate, clean dramatic spotlighting, shot on Phase One 120mm macro lens, advertising billboard quality",
         size="768x768", mode="t2i"),
    _tpl("product", "瑞士旗舰机械腕表暗调微距广告", "产品 手表 腕表 奢华 商业 金属 微距",
         "拉丝精钢与蓝宝石玻璃倒影、精密陀飞轮齿轮纹理、硬核科技奢华感",
         "Masterpiece studio macro advertisement of a Swiss skeleton mechanical chronograph wristwatch resting on dark wet volcanic basalt rock, intricate brushed titanium bezels, sapphire crystal reflecting a crisp blade of cool studio light, exposed golden tourbillon gears and blued steel screws in razor-sharp focus, moody dark luxury atmosphere, zero glare distraction",
         size="768x768", mode="t2i"),
    _tpl("product", "旗舰降噪耳机极简悬浮科技海报", "产品 耳机 科技 数码 极简 广告 3D",
         "钛金属与小羊皮细腻质感、青紫柔光声波氛围、苹果级工业美学",
         "Apple-keynote grade studio product render of sleek matte-titanium over-ear wireless flagship headphones floating gracefully at a dynamic three-quarter angle against a deep obsidian-blue atmospheric backdrop, subtle volumetric cyan and silver rim lighting tracing the anodized aluminum arc and plush memory-foam earcups, delicate soundwave dust mist, spotless photorealistic industrial design",
         size="768x768", mode="t2i"),
    _tpl("product", "概念超跑暗室流线光带棚拍", "汽车 跑车 商业 广告 科技 暗调 炫酷",
         "暗黑影棚顶部细长柔光箱勾勒车身肌肉曲线、地面微湿镜面反射",
         "Sleek automotive studio photography of a low-slung sculpted liquid-silver electric hypercar parked on a dark wet polished concrete floor inside a pitch-black studio, a single razor-thin overhead LED light tube tracing a continuous luminous reflection ribbon along the aerodynamic carbon-fiber roofline and fenders, glowing subtle cyan daytime running blades, crisp editorial automotive realism",
         size="1024x576", mode="t2i"),

    # ---------- 8. 魔幻与史诗概念 (fantasy) ----------
    _tpl("fantasy", "东方巨龙盘踞云端火山雷暴要塞", "魔幻 龙 史诗 概念 黑暗 雷电 宏大",
         "紫电撕裂黑云、熔岩映照龙鳞金属光泽、史诗电影级大场面",
         "Monumental dark-fantasy concept painting of an ancient colossal obsidian-and-gold scaled dragon coiled atop a jagged volcanic citadel spire amidst roaring storm clouds, crackling bolts of electric violet lightning illuminating billowing ash and glowing magma rivers far below, lone tiny knight standing on a narrow stone causeway in the foreground, dramatic epic scale, cinematic blockbuster matte painting",
         size="1024x576", mode="t2i"),
    _tpl("fantasy", "精灵世界发光巨树荧光森林圣地", "魔幻 精灵 森林 发光 唯美 奇幻",
         "参天发光古树根系盘错、浮空水晶萤火、指环王与阿凡达融合质感",
         "Enchanting high-fantasy environment concept art of an ancient towering bioluminescent World Tree rising from a tranquil mirrored forest glade at twilight, cascading silver-blue glowing willow vines and floating emerald fireflies illuminating carved marble elven bridges, soft volumetric moonlight piercing dense misty foliage, breathtaking painterly realism",
         size="1024x576", mode="t2i"),
    _tpl("fantasy", "蒸汽朋克维多利亚浮空飞艇港", "魔幻 蒸汽朋克 飞艇 复古 科幻 史诗",
         "黄铜齿轮与铆钉巨艇、夕阳穿透洁白蒸汽羽流、宏大奇想世界观",
         "Richly detailed steampunk world-building panorama of a towering Victorian brass-and-iron skyport suspended above golden sunset clouds, majestic dirigible airships with ornate copper hulls, rotating brass propellers and billowing canvas sails docked beside clockwork stone towers, warm amber gaslamps glowing through swirling steam plumes, cinematic adventure film concept art",
         size="1024x576", mode="t2i"),

    # ---------- 9. 建筑与室内美学 (arch) ----------
    _tpl("arch", "悬崖无边海景极简玻璃别墅", "建筑 别墅 海景 极简 室内 夕阳 高级",
         "清水混凝土与超大落地玻璃、无边泳池融于落日海天、建筑摄影杂志",
         "Architectural Digest photograph of a breathtaking cantilevered minimalist concrete-and-glass cliffside villa overlooking the tranquil Pacific Ocean at twilight, warm interior recessed oak lighting glowing softly beside a mirror-still infinity pool seamlessly merging with the crimson-violet horizon, clean modernist geometry, shot on tilt-shift 24mm architectural lens",
         size="1024x576", mode="t2i"),
    _tpl("arch", "东方侘寂风原木阳光禅意客厅", "建筑 室内 客厅 侘寂 极简 治愈 阳光",
         "微水泥肌理墙面、枯枝陶器、午后斜阳投下温润窗棂阴影",
         "Serene interior architectural photograph of a Japanese-inspired wabi-sabi minimalist living room featuring hand-troweled warm lime-plaster walls, low-profile natural oak and bouclé linen sofa, sculptural ceramic vase holding a single dried branch, soft golden afternoon sunlight casting crisp architectural window shadows across travertine stone flooring, peaceful editorial calm",
         size="1024x576", mode="t2i"),

    # ---------- 10. 美食与静物 (food) ----------
    _tpl("food", "深夜食堂浓汤豚骨拉面热气特写", "美食 拉面 日料 夜晚 治愈 摄影 微距",
         "溏心蛋与炙烤叉烧油润光泽、袅袅上升的真实白气、暖调深夜食欲",
         "Mouthwatering editorial food photography of a handcrafted dark stoneware bowl of steaming tonkotsu ramen on a worn cedar counter in a cozy Tokyo midnight izakaya, glossy golden broth with glistening chili oil droplets, perfectly jammy soft-boiled ajitama egg, caramelized chashu pork belly, fresh scallions and nori, wisps of hot steam backlit by warm amber lantern light, 85mm f/2.0 macro",
         size="768x768", mode="t2i"),
    _tpl("food", "中式茶道青瓷壶幽暗禅意光影", "美食 茶道 古风 静物 禅意 摄影",
         "一束窗光穿透茶烟、青瓷冰裂纹釉面、高级东方美学静物大片",
         "Poetic still-life photograph of traditional Chinese gongfu tea ceremony on a dark weathered walnut tea table, hot clear amber oolong tea pouring gracefully in a thin luminous arc from a handcrafted celadon porcelain teapot into a delicate teacup, delicate curling steam illuminated by a single soft beam of natural side window light against a quiet shadowed backdrop, refined serene aesthetic",
         size="768x768", mode="t2i"),

    # ---------- 11. 萌宠与神兽 (creature) ----------
    _tpl("creature", "雪原月夜九尾灵狐仙气特写", "动物 狐狸 神兽 雪景 唯美 奇幻 萌宠",
         "纤毫毕现的雪白绒毛、幽蓝月光与琥珀双眸、空灵神圣氛围",
         "Ethereal photorealistic fantasy portrait of a mystical snow-white nine-tailed fox seated gracefully on a frost-covered pine ridge under a luminous full moon, ultra-fine shimmering silver-white fur catching cool azure moonlight and drifting snow crystals, intelligent glowing amber eyes, faint golden spirit wisps swirling gently around its lush flowing tails, cinematic wildlife fantasy",
         size="768x768", mode="t2i"),
    _tpl("creature", "午后阳光窗台蓝眼布偶猫抓拍", "动物 猫 萌宠 治愈 阳光 摄影 可爱",
         "柔和逆光毛发发光、宝石蓝瞳孔清澈通透、极度治愈高清写真",
         "Heartwarming natural-light portrait photograph of a fluffy seal-bicolor Ragdoll cat lounging lazily on a warm sunlit wooden windowsill beside potted green ferns, crystal-clear sapphire blue eyes catching soft window light, golden afternoon sunbeams backlighting the wispy halo of its silky fur, creamy blurred cozy apartment bokeh, shot on 85mm f/1.4",
         size="768x768", mode="t2i"),
    _tpl("creature", "云海星空巨鲸跃出天际奇观", "动物 鲸鱼 星空 云海 梦幻 唯美 史诗",
         "蓝鲸身披星辉跃过云海、水珠化作繁星飘散、超现实震撼意境",
         "Surreal poetic masterpiece of a colossal luminous humpback whale breaching gracefully out of a vast moonlit sea of clouds into a deep indigo Milky Way night sky, sparkling cascades of stardust and glowing mist trailing from its majestic fins, tiny silhouetted mountaintops below, awe-inspiring dreamlike cinematography",
         size="1024x576", mode="t2i"),

    # ---------- 12. 3D 质感与视觉海报 (abstract) ----------
    _tpl("abstract", "液态铬金属与虹彩水晶 3D 视觉", "3D 海报 抽象 流体 玻璃 科技 炫酷 封面",
         "Cinema 4D Octane 级光学色散、液态水银雕塑感、顶级专辑/壁纸视觉",
         "Avant-garde 3D digital art sculpture of intertwined liquid mercury chrome ribbons and translucent iridescent glass prisms floating weightlessly in a sleek dark obsidian studio, crisp rainbow optical dispersion and caustics refracting across smooth curved surfaces, dramatic studio rim highlights, Cinema 4D Octane render aesthetic, ultra-clean flagship wallpaper composition",
         size="1024x576", mode="t2i"),
    _tpl("abstract", "暗黑赛博丝绸波浪全息专辑封面", "3D 海报 丝绸 霓虹 音乐 封面 极简 炫酷",
         "流光溢彩的暗调丝绒波浪、青粉紫极光渐变、高级空间计算美学",
         "Minimalist luxury 3D spatial visual artwork featuring flowing dark translucent silk waves sculpted by invisible sound frequencies, glowing internal gradients of electric cyan, deep ultraviolet and soft rose gold rippling through velvety shadow folds, ultra-subtle micro film grain, Apple Vision Pro inspired futuristic album cover aesthetic",
         size="768x768", mode="t2i"),
]


def _translate_keywords_local(query: str) -> str:
    """将用户中文关键词精准映射为自然英文视觉核心描述（供离线/毫秒动态合成使用）。"""
    q = (query or "").strip()
    if not q:
        return ""
    # If mostly English already, keep directly
    ascii_letters = sum(1 for ch in q if "a" <= ch.lower() <= "z")
    if ascii_letters >= len(q) * 0.55:
        return q
    hits = []
    # Match longer Chinese keys first
    for cn in sorted(CN_EN_CONCEPTS.keys(), key=len, reverse=True):
        if cn in q:
            en = CN_EN_CONCEPTS[cn]
            if en not in hits:
                hits.append(en)
    if hits:
        return ", ".join(hits[:6]) + f" (inspired by: {q})"
    return f"vivid cinematic scene depicting {q}"


def _build_dynamic_templates(query: str, mode: str = "t2i") -> List[Dict[str, Any]]:
    """根据用户输入的任意关键词，毫秒动态合成 6 套不同专业风格的定制提示词模板。"""
    q = (query or "").strip()
    if not q:
        return []
    subj = _translate_keywords_local(q)
    out = [
        {
            "cat": "portrait",
            "title": f"【定制·电影写实】{q}",
            "tags": f"{q} 电影写实 35mm 胶片 定制",
            "summary": "ARRI 电影机 35mm 宽银幕写实光影 + 真实材质肌理 + 浅景深叙事构图",
            "prompt": (
                f"Photorealistic 35mm cinematic film still of {subj}, dramatic natural multi-layered lighting "
                f"with subtle volumetric rim light and rich atmospheric depth, authentic micro-textures and natural "
                f"color gradations, composed with rule-of-thirds depth of field, shot on ARRI Alexa Mini LF 50mm f/1.4 "
                f"anamorphic lens, Kodak Vision3 color science, subtle organic film grain"
            ),
            "neg_prompt": DEFAULT_NEG_PHOTO,
            "size": "1024x576",
            "mode": "t2i",
            "source": "关键词智能合成",
        },
        {
            "cat": "video",
            "title": f"【定制·Wan2.2运镜】{q} 动态电影镜头",
            "tags": f"{q} 视频 运镜 Wan2.2 动态 慢动作",
            "summary": "专为 Wan 2.2 调优：平稳推镜/微环绕 + 真实物理微动 + 电影连续帧稳定性",
            "prompt": (
                f"Cinematic 24fps film video shot of {subj}, smooth slow dolly-in camera movement with gentle parallax, "
                f"natural continuous micro-motions in lighting, drifting atmospheric mist, wind-swept fabrics and subtle "
                f"environmental reflections, dramatic volumetric light beams shifting organically across the frame, "
                f"crisp subject consistency, silky motion physics, IMAX film look"
            ),
            "neg_prompt": DEFAULT_NEG_VIDEO,
            "size": "832x480",
            "mode": "t2v" if mode != "i2v" else "i2v",
            "source": "关键词智能合成",
        },
        {
            "cat": "anime",
            "title": f"【定制·唯美光影】{q} 剧场版概念原画",
            "tags": f"{q} 二次元 唯美 新海诚 概念原画",
            "summary": "通透剧场版光影、高饱和冷暖氛围对比、精致手绘质感与层次景深",
            "prompt": (
                f"Exquisite high-budget theatrical anime film illustration of {subj}, luminous golden-hour sunbeams "
                f"and translucent glowing atmospheric haze, vibrant cobalt and coral sky reflections, razor-clean "
                f"expressive details with painterly layered depth, delicate floating light motes, Makoto Shinkai "
                f"inspired cinematic lighting and emotional atmosphere"
            ),
            "neg_prompt": DEFAULT_NEG_ANIME,
            "size": "1024x576",
            "mode": "t2i",
            "source": "关键词智能合成",
        },
        {
            "cat": "cyber",
            "title": f"【定制·赛博霓虹】{q} 未来暗调视觉",
            "tags": f"{q} 赛博 霓虹 科幻 夜景 炫酷",
            "summary": "雨夜湿面镜光、电光青与洋红双色边缘光、高质感硬科幻空间透视",
            "prompt": (
                f"Futuristic cyberpunk nocturnal visual of {subj}, drenched in atmospheric neon cyan, electric violet "
                f"and warm amber reflections across wet reflective surfaces, volumetric fog pierced by dramatic holographic "
                f"rim lights, ultra-detailed sci-fi material reflections and sleek metallic accents, 35mm anamorphic lens "
                f"halation, Blade Runner 2049 inspired cinematography"
            ),
            "neg_prompt": DEFAULT_NEG_PHOTO,
            "size": "1024x576",
            "mode": "t2i",
            "source": "关键词智能合成",
        },
        {
            "cat": "guofeng",
            "title": f"【定制·东方美学】{q} 诗意水墨光影",
            "tags": f"{q} 古风 东方 水墨 意境 唯美",
            "summary": "石青琥珀矿物色调、流动轻雾与留白构图、电影写实与东方神韵融合",
            "prompt": (
                f"Poetic neo-Chinese aesthetic cinematic masterpiece of {subj}, veiled in drifting silk-like valley mist "
                f"and warm diffused lantern-gold and celadon-jade lighting, harmonious blend of photorealistic natural "
                f"textures and classical ink-wash atmospheric depth, graceful composition with refined negative space, "
                f"tranquil museum-grade fine art lighting"
            ),
            "neg_prompt": DEFAULT_NEG_PHOTO,
            "size": "1024x576",
            "mode": "t2i",
            "source": "关键词智能合成",
        },
        {
            "cat": "product",
            "title": f"【定制·商业特写】{q} 棚拍 8K 质感大片",
            "tags": f"{q} 商业 棚拍 特写 微距 质感 8K",
            "summary": "中画幅微距棚拍、雕塑感轮廓光与洁净背景、高奢视觉海报级清晰度",
            "prompt": (
                f"Ultra-crisp luxury studio editorial close-up of {subj}, sculpted by precision directional rim lighting "
                f"and soft diffused overhead key light against a clean atmospheric dark backdrop, tactile micro-surface "
                f"details, subtle optical specular reflections and creamy f/2.0 bokeh falloff, shot on Hasselblad "
                f"medium-format 120mm lens, commercial campaign quality"
            ),
            "neg_prompt": DEFAULT_NEG_PHOTO,
            "size": "768x768",
            "mode": "t2i",
            "source": "关键词智能合成",
        },
    ]
    return out


def search_prompts(query: str = "", category: str = "all", mode: str = "t2i", limit: int = 36) -> Dict[str, Any]:
    """双引擎提示词搜索：大师精选库语义打分检索 + 用户关键词动态定制模板合成。"""
    q = (query or "").strip()
    cat = (category or "all").strip().lower()

    pool = [p for p in MASTER_PROMPTS if (cat == "all" or p["cat"] == cat)]
    if not q:
        # Prioritize video templates if user is in t2v/i2v mode and viewing "all"
        if cat == "all" and mode in ("t2v", "i2v"):
            pool = sorted(pool, key=lambda x: (0 if x["cat"] == "video" else 1))
        return {
            "ok": True,
            "total": len(pool),
            "results": pool[:limit],
            "categories": PROMPT_CATEGORIES,
            "msg": f"已加载 {min(len(pool), limit)} 套大师级提示词模板（库内共 {len(MASTER_PROMPTS)} 套精选）",
        }

    # Tokenize query (Chinese phrases, bigrams, key single chars + English words) and expand with synonyms
    tokens = [t for t in re.split(r"[\s,，、/|+]+", q.lower()) if t]
    expanded = set(tokens)
    # Add Chinese 2-char n-grams so phrases like "一剑开天门" match "天门", "开天", etc.
    cn_only = re.sub(r"[^\u4e00-\u9fff]+", "", q)
    for i in range(len(cn_only) - 1):
        expanded.add(cn_only[i : i + 2])
    for cn, en in CN_EN_CONCEPTS.items():
        if cn in q:
            expanded.add(cn)
            for w in re.split(r"[\s,-]+", en.lower()):
                if len(w) >= 3:
                    expanded.add(w)
        else:
            for tk in tokens:
                if len(tk) >= 2 and tk in en.lower():
                    expanded.add(cn)

    scored = []
    for item in pool:
        hay_title = item["title"].lower()
        hay_tags = item["tags"].lower()
        hay_sum = item["summary"].lower()
        hay_prompt = item["prompt"].lower()
        score = 0
        if q.lower() in hay_title or q.lower() in hay_tags:
            score += 30
        for tk in expanded:
            if tk in hay_title:
                score += 12
            if tk in hay_tags:
                score += 10
            if tk in hay_sum:
                score += 6
            if tk in hay_prompt:
                score += 5
        if mode in ("t2v", "i2v") and item["mode"] in ("t2v", "i2v"):
            score += 4
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    matched = [it for _, it in scored[: max(12, limit - 6)]]

    # Always synthesize bespoke templates tailored directly to the user's exact keywords!
    dynamic = _build_dynamic_templates(q, mode=mode)
    # Put top direct matches first, then bespoke dynamic templates, then remaining matches
    final_list = matched[:4] + dynamic + matched[4:]
    return {
        "ok": True,
        "total": len(final_list),
        "results": final_list[:limit],
        "categories": PROMPT_CATEGORIES,
        "msg": f"关键词「{q}」命中 {len(matched)} 套精选 + 即时定制 {len(dynamic)} 套专属模板",
    }


def _extract_json_block(text: str):
    raw = (text or "").strip()
    if not raw:
        return None
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, flags=re.I)
    if m:
        raw = m.group(1).strip()
    # Find outermost [ ... ] or { ... }
    for open_c, close_c in (("{", "}"), ("[", "]")):
        i = raw.find(open_c)
        j = raw.rfind(close_c)
        if i != -1 and j > i:
            try:
                return json.loads(raw[i : j + 1])
            except Exception:
                pass
    try:
        return json.loads(raw)
    except Exception:
        return None


def optimize_prompt_with_ai(raw_input: str, mode: str = "t2i", style_hint: str = "",
                            codex_cfg: dict = None, chat_fn=None, proxy: str = "",
                            count: int = 3) -> Dict[str, Any]:
    """调用本机 Codex 智能体将用户的粗略中文/英文想法升格为多套大师级 Z-Image Turbo / Wan 2.2 提示词。"""
    idea = (raw_input or "").strip()
    if not idea:
        return {"ok": False, "msg": "请先在输入框填写你想生成的画面想法或关键词", "variants": []}

    count = max(3, min(6, int(count or 3)))
    cx = codex_cfg or {}
    base_url = str(cx.get("base_url") or "").strip()
    api_key = str(cx.get("api_key") or "").strip()
    model = str(cx.get("model") or "gpt-6-sol").strip()
    api_style = str(cx.get("api_style") or "auto").strip()

    sys_prompt = (
        "你是世界顶级的电影摄影指导与 AI 视觉提示词架构师，专精两款本地模型：\n"
        "1) Z-Image Turbo（基于 Qwen3-4B / Lumina2 文本编码器）：极擅长理解自然语言电影镜头描述、物理光线（主光/轮廓光/体积光/漫反射）、真实材质肌理、构图景深与胶片色学；严禁堆砌老式无意义废词（如 'masterpiece, best quality, 8k, ultra detailed, 1girl' 这种逗号标签垃圾）。\n"
        "2) Wan 2.2 I2V 14B 视频模型：要求明确写出连续运镜轨迹（如 smooth dolly-in / gentle orbiting tracking shot / aerial crane-up）、主体自然连续微动作、环境物理动态（发丝衣袂吹拂、水波、光影流动、雨雪粒子）。\n\n"
        "严格输出纯 JSON，不要输出任何额外解释，格式如下：\n"
        '{"variants": [{"title": "简洁吸睛的中文风格标题", "style_tag": "如 电影写实 / 概念美学 / Wan2.2运镜", '
        '"summary": "一句精炼中文画面拆解（主体+光线+镜头/运镜亮点）", '
        '"prompt": "高质量英文自然语言长提示词（65~115词，画面感极强、物理光影准确、细节克制高级、可直接出大片）", '
        '"neg_prompt": "精准英文负向词", "size": "1024x576 或 576x1024 或 768x768 或 832x480", '
        '"mode": "t2i 或 t2v 或 i2v"}]}\n'
    )

    mode_desc = {
        "t2i": "当前用户目标是文生图（Z-Image Turbo）。请生成 {n} 套差异鲜明的大师方案：第1套为电影胶片写实大片，第2套为艺术美学/氛围概念版，第3套为 Wan 2.2 电影运镜动态视频版（方便一键生视频）；若要求超过3套，继续扩展不同高质感流派（如东方意境、暗调棚拍、超广角史诗）。",
        "t2v": "当前用户目标是文生视频（Z-Image 首帧 → Wan 2.2 I2V）。请全部 {n} 套都突出电影运镜、连贯动作与物理环境动态，推荐画幅 832x480，mode 设为 t2v。",
        "i2v": "当前用户目标是图生视频（Wan 2.2 I2V）。请全部 {n} 套都聚焦基于首帧的平滑运镜、主体呼吸/眼神/衣袂微动与环境光影变化，推荐画幅 832x480，mode 设为 i2v。",
    }.get(mode, "请生成 {n} 套大师级提示词。").format(n=count)

    user_msg = f"用户原始想法：{idea}\n"
    if style_hint:
        user_msg += f"用户偏好风格：{style_hint}\n"
    user_msg += mode_desc + "\n严格返回合法 JSON。"

    if chat_fn and base_url and api_key:
        ok, reply = chat_fn(
            base_url=base_url,
            api_key=api_key,
            model=model,
            messages=[{"role": "user", "content": user_msg}],
            system_prompt=sys_prompt,
            api_style=api_style,
            proxy=proxy,
            timeout=38.0,
        )
        if ok and reply:
            parsed = _extract_json_block(reply)
            rows = parsed.get("variants") if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else None)
            cleaned = []
            if isinstance(rows, list):
                for idx, v in enumerate(rows[:count], 1):
                    if not isinstance(v, dict):
                        continue
                    pr = str(v.get("prompt") or "").strip()
                    if len(pr) < 20:
                        continue
                    vmode = str(v.get("mode") or mode or "t2i").strip().lower()
                    if vmode not in ("t2i", "t2v", "i2v"):
                        vmode = mode if mode in ("t2i", "t2v", "i2v") else "t2i"
                    vsize = str(v.get("size") or ("832x480" if vmode in ("t2v", "i2v") else "1024x576")).strip()
                    if vsize not in ("768x768", "1024x576", "576x1024", "832x480"):
                        vsize = "832x480" if vmode in ("t2v", "i2v") else "1024x576"
                    cleaned.append({
                        "title": str(v.get("title") or f"AI 优化方案 #{idx}").strip(),
                        "style_tag": str(v.get("style_tag") or ("Wan2.2 运镜" if vmode in ("t2v", "i2v") else "AI 大师优化")).strip(),
                        "summary": str(v.get("summary") or "已由 Codex 提示词架构师深度优化").strip(),
                        "prompt": pr,
                        "neg_prompt": str(v.get("neg_prompt") or (DEFAULT_NEG_VIDEO if vmode in ("t2v", "i2v") else DEFAULT_NEG_PHOTO)).strip(),
                        "size": vsize,
                        "mode": vmode,
                        "source": f"Codex · {model}",
                    })
            if cleaned:
                return {
                    "ok": True,
                    "msg": f"✨ AI 已按你的输入深度生成 {len(cleaned)} 套大师级提示词（{model}）",
                    "variants": cleaned,
                }

    # Seamless local studio fallback if Codex is momentarily unreachable
    fallback = _build_dynamic_templates(idea, mode=mode)[:count]
    for f in fallback:
        f["style_tag"] = f.get("source", "本地大师引擎")
    return {
        "ok": True,
        "msg": f"已用本地大师提示词架构师生成 {len(fallback)} 套优化方案 ✔",
        "variants": fallback,
    }
