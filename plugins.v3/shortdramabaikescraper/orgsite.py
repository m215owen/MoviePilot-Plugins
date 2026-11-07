"""``duanjubaike.org``（新站）解析器 —— 与 :mod:`netsite`（.net 老站）同构的出口。

2026-11-02 接入（用户口径：插件支持在 .net / .org 之间二选一）。

两个站是**两套完全不同的架构**，这里不复用 .net 的解析逻辑：

==============  ===========================  ==========================
                .net（netsite.py）           .org（本模块）
==============  ===========================  ==========================
渲染方式        PHP 服务端渲染               Laravel SSR + Alpine
检索            ``/so.html?keyword=``        ``/zh-Hans/drama/search?q=``
详情页          ``/<分类>/info-<id>.html``   ``/zh-Hans/drama/<id>``
人物页          ``/yanyuan/info-<id>.html``  ``/zh-Hans/actor/<id>``
图片            按身份现拼（规律地址）       页面自带 CDN 绝对地址
身份前缀        分类开放集（duanju/manju…）  固定 ``drama`` / ``actor``
结构化数据      无                           **JSON-LD**（schema.org）
==============  ===========================  ==========================

解析策略：详情页与演员页**优先吃 ``<script type="application/ld+json">``**
（TVSeries / Person + PerformanceRole，站方自己输出的结构化数据，比 DOM 稳），
DOM 只补 JSON-LD 没有的部分（播放 / 收藏 / 热度统计、版权方、角标、
人物目录与列表卡）。列表 / 搜索页没有实体 JSON-LD，卡片全部走 DOM。

记录 shape 与 :mod:`netsite` **逐字段对齐**（``media_id`` / ``title`` /
``episodes`` / ``people`` …），下游（``record`` / ``payload`` / ``merge`` /
ID 库）不用知道数据来自哪个站。唯一的站间差异由 :mod:`identity` 吸收：
``.org`` 的海报是页面自带地址（随记录落盘），不是按身份现拼。
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from . import orgident as identity
from .constants import (
    ORG_AI_BADGE_TITLE,
    ORG_COMMENTS_SECTION,
    ORG_LANG,
    ORG_NOVEL_SECTION,
    ORG_SAME_NOVEL_SECTION,
    ORG_SAME_SCRIPT_SECTION,
    ORG_SERIES_SECTION,
)
from .dom import Node, parse_html
from .siteutil import (
    _DATE_RE,
    _EPISODES_RE,
    clean,
    profile_of as _profile_of,
    title_in_books,
    to_float,
    to_int,
    wan_to_number,
)
from .title_clean import season_of_text

__all__ = [
    "comments_of",
    "parse_actor",
    "parse_actor_cards",
    "parse_cards",
    "parse_people_list",
    "parse_search",
    "parse_work",
    "people_list_url",
    "search_url",
    "work_url",
]


# ─────────────────────────── 地址 ───────────────────────────


def _base(domain: str = "") -> str:
    if domain:
        return str(domain).rstrip("/")
    from .constants import SITE_DOMAINS, SITE_ORG

    return SITE_DOMAINS[SITE_ORG]


def _lang(lang: str = "") -> str:
    return (lang or ORG_LANG).strip("/") or ORG_LANG


def work_url(native_id: Any, domain: str = "", lang: str = "") -> str:
    native = identity.native_id_of(native_id)
    return f"{_base(domain)}/{_lang(lang)}/drama/{native}" if native else ""


def actor_url(native_id: Any, domain: str = "", lang: str = "") -> str:
    native = identity.native_id_of(native_id)
    return f"{_base(domain)}/{_lang(lang)}/actor/{native}" if native else ""


def search_url(keyword: str, domain: str = "", kind: str = "", lang: str = "") -> str:
    path = "actor/search" if kind == "actor" else "drama/search"
    return f"{_base(domain)}/{_lang(lang)}/{path}?q={quote(str(keyword or ''), safe='')}"


def people_list_url(
    page: int = 1, domain: str = "", lang: str = "", gender: str = ""
) -> str:
    """人物目录页（``/zh-Hans/actor``）。

    男女榜在站点上是**同一个页面的查询参数**：``?gender=男`` / ``?gender=女``
    （「全部」= 不带这个参数），可与分页叠加成 ``?gender=女&page=2``
    （2026-11-02 用户口径：发现页的演员要分男女榜）。
    """
    url = f"{_base(domain)}/{_lang(lang)}/actor"
    params: List[str] = []
    sex = str(gender or "").strip()
    if sex:
        params.append("gender=" + quote(sex, safe=""))
    if page and page > 1:
        params.append(f"page={max(1, int(page or 1))}")
    return f"{url}?{'&'.join(params)}" if params else url


# ─────────────────────────── 身份 ───────────────────────────


#: 页面地址 / ``@id`` 里的身份：``/zh-Hans/drama/74288``、``/actor/1191``。
#: 与 :mod:`identity` 的 .net 形态并列 —— 语言段可有可无（JSON-LD ``@id`` 带
#: ``#person`` 锚，同样要能认）。
_ORG_URL_RE = re.compile(r"/(?:zh-(?:Hans|Hant)/)?(?P<kind>drama|actor)/(?P<native>\d+)", re.IGNORECASE)

#: ``热度/播放/收藏`` 统计行：``8094万热度/467万播放``、``1,028``、``396万热度``
_STAT_RE = re.compile(r"([\d,.]+\s*万?)\s*(热度|播放|收藏)")

#: 统计块的标签（页面形态：``<span class="font-medium">17万</span> 播放``）
_STAT_LABELS = ("播放", "收藏", "热度")

#: 信息键值（详情页 / 演员页个人资料）：``<span class="text-gray-500">集数：</span>``
_KV_RE = re.compile(
    r">(?P<key>[\u4e00-\u9fa5（）]{2,10})[：:]\s*</[^>]+>\s*<[^>]*>\s*(?P<value>[^<]{1,80}?)\s*<",
    re.S,
)

#: 卡片角标里无意义的纯评分 / 集数以外的杂讯
_BADGE_NOISE = ("AI", "真人", "爆火", "完结", "新剧", "预约")

#: 封面上的**状态角标**（站点原样文本，一条可挂多枚）：
#: 与 ``badge``（内容类型：短剧 / 漫剧 / 平台名，单值）是两条轴 ——
#: 状态角标会随时间变（今天的「新剧」下周就没了），所以**多值 + 原样留存**，
#: 交给上层决定怎么展示（订阅插件的作品卡按它印「爆火」「新剧」，2026-11-02）。
_BADGE_STATES: Tuple[str, ...] = ("爆火", "新剧", "完结", "连载中", "已完结", "预约")

#: 封面左下角的**季标**（``第2季`` / ``第二季``）。它是「第几季」这一事实的唯一
#: 来源：.org 的剧名不带季号（``冒姓琅琊2`` 这种写法解析不出季，实测
#: ``title.season_of`` 全判成 1），不从这里取，``series`` 会被 ``lean_series``
#: 当成「就是第一季」整片丢掉。
_SEASON_BADGE_RE = re.compile(r"^第\s*([0-9一二三四五六七八九十]+)\s*季$")

_CN_DIGITS = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def _cn_int(text: str) -> int:
    """``2`` / ``二`` / ``十二`` → 整数（只服务季标这种个位到两位的场景）。"""
    value = str(text or "").strip()
    if value.isdigit():
        return int(value)
    if value == "十":
        return 10
    if "十" in value:
        head, _, tail = value.partition("十")
        tens = _CN_DIGITS.get(head, 1) if head else 1
        ones = _CN_DIGITS.get(tail, 0) if tail else 0
        return tens * 10 + ones
    return _CN_DIGITS.get(value, 0)


def _season_of_badge(text: str) -> int:
    match = _SEASON_BADGE_RE.match(text)
    return _cn_int(match.group(1)) if match else 0

#: 统计块数值的千分位
_COMMA_RE = re.compile(r",")


def _is_ai_badge(node: Node) -> bool:
    """是不是「AI 短剧」标（``<span title="AI短剧">AI</span>``）。"""
    return node.attr("title") == ORG_AI_BADGE_TITLE


def _card_is_ai(title_anchor: Optional[Node]) -> bool:
    """卡片标题锚里有没有 AI 标。

    真人卡的同一位置是 ``title="真人短剧"``，两者只会有一个。
    """
    if title_anchor is None:
        return False
    return any(_is_ai_badge(node) for node in title_anchor.find_all("span"))


def _heading_is_ai(heading: Optional[Node]) -> bool:
    """详情页标题行：``h1`` **之前**的兄弟节点挂类型标（AI / 真人）。

    ⚠️ 只能按位置认：详情页的「相关推荐」「演员作品区」里也有同款 AI 标，
    全文匹配会把真人剧整批判成 AI（实测真人剧页面能数出 3 个）。
    """
    if heading is None or heading.parent is None:
        return False
    for child in heading.parent.children:
        if child is heading:
            break
        if isinstance(child, Node) and _is_ai_badge(child):
            return True
    return False

_ISO_DURATION_RE = re.compile(
    r"^PT(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+)S)?$"
)


def _num(value: Any, default: int = 0) -> int:
    """``2,824`` / ``467万`` / ``3058万`` 都收（.org 数字带千分位）。"""
    text = clean(_COMMA_RE.sub("", str(value or "")))
    if not text:
        return default
    return wan_to_number(text, default)


def _duration_text(iso: Any) -> str:
    """``PT2H58M37S`` → ``2小时58分钟``（.net 口径的中文时长）。"""
    match = _ISO_DURATION_RE.match(clean(iso))
    if not match:
        return ""
    hours = to_int(match.group("h"))
    minutes = to_int(match.group("m"))
    seconds = to_int(match.group("s"))
    parts: List[str] = []
    if hours:
        parts.append(f"{hours}小时")
    if minutes or not parts:
        parts.append(f"{minutes}分钟")
    return "".join(parts)


def _graph(html: str) -> List[Dict[str, Any]]:
    """页面里唯一的 ``ld+json`` 的 ``@graph``（没有 / 解析失败 → 空表）。"""
    blocks = re.findall(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S
    )
    for block in blocks:
        try:
            data = json.loads(block)
        except (ValueError, TypeError):
            continue
        if isinstance(data, dict):
            graph = data.get("@graph")
            if isinstance(graph, list):
                return [item for item in graph if isinstance(item, dict)]
    return []


def _typed(graph: List[Dict[str, Any]], *types: str) -> List[Dict[str, Any]]:
    return [item for item in graph if str(item.get("@type") or "") in types]


def _meta(root: Node, name: str) -> str:
    for node in root.find_all("meta"):
        if node.attr("name") == name or node.attr("property") == name:
            return node.attr("content")
    return ""


def _id_of_url(value: Any, kind: str = "") -> str:
    match = _ORG_URL_RE.search(str(value or ""))
    if not match:
        return ""
    found = match.group("kind").lower()
    if kind and found != kind:
        return ""
    return match.group("native")


# ─────────────────────────── 卡片 ───────────────────────────


def _cover_anchor(root: Node, kind: str = "drama") -> List[Node]:
    """封面锚（``<a href=…/drama/74288 class="… aspect-[5/7] …">``）。"""
    rows: List[Node] = []
    for anchor in root.find_all("a"):
        href = (anchor.attr("href") or "").strip()
        native = _id_of_url(href, kind)
        if not native:
            continue
        if not any(cls.startswith("aspect-") for cls in anchor.classes):
            continue
        rows.append(anchor)
    return rows


def _cover_field(anchor: Node) -> Tuple[str, int, float, str, List[str], int]:
    """封面上叠的角标： ``(poster, episodes, rating, badge, states, season)``。

    * ``badge``：**内容类型**（短剧 / 漫剧 / 平台名），单值；
    * ``states``：**状态角标**（爆火 / 新剧 / 完结 / 预约…），多值、站点原样文本 ——
      以前按 ``_BADGE_NOISE`` 丢掉，卡片上就没法显示「爆火」「新剧」了
      （2026-11-02 用户要求作品卡带这两枚）；
    * ``season``：左下角季标换算出的季号（``0`` = 卡上没有季标）。它**不**落进
      ``badge`` —— 那个位子是内容类型，两码事。
    """
    image = anchor.find("img")
    poster = clean(image.attr("src") if image else "")
    episodes = 0
    rating = 0.0
    badge = ""
    states: List[str] = []
    season = 0
    for node in anchor.find_all("div"):
        text = clean(node.text)
        if not text:
            continue
        if _EPISODES_RE.search(text):
            # 集数角标外层还有一层装饰 div，同一段文本会到两次：
            # 第一次进 episodes，第二次直接跳过（不能落进 badge）
            if not episodes:
                episodes = to_int(_EPISODES_RE.search(text).group(1))
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?", text):
            # 评分恒带一位小数（8.3 / 8.0）且在 <span> 里；排行榜的名次是
            # 整数 div（可能也带 span）—— 用「必须有小数点」把名次排除掉
            if not rating and "." in text and node.find("span") is not None:
                value = to_float(text)
                if 0 < value <= 10:
                    rating = value
            continue
        if text in _BADGE_STATES:
            # 外层定位 div 与内层彩色 chip 的文本相同：去重即可，别印两枚
            if text not in states:
                states.append(text)
            continue
        season_badge = _season_of_badge(text)
        if season_badge:
            # 季标外层同样套了一层装饰 div（文本重复），保留第一次的值
            if not season:
                season = season_badge
            continue
        if not badge and text not in _BADGE_NOISE and len(text) <= 4:
            badge = text
    return poster, episodes, rating, badge, states, season


def _card_of(anchor: Node, domain: str = "") -> Dict[str, Any]:
    """一张作品卡（搜索 / 列表 / 榜单 / 演员页作品区同一套结构）。"""
    native = _id_of_url(anchor.attr("href"), "drama")
    if not native:
        return {}
    poster, episodes, rating, badge, states, season = _cover_field(anchor)

    # 信息块 = 卡容器里封面锚的**兄弟** <div>（``p-3`` / ``p-4`` 起手）
    info: Optional[Node] = None
    for sibling in anchor.siblings:
        if sibling.tag == "div" and any(
            cls in ("p-3", "p-4") for cls in sibling.classes
        ):
            info = sibling
            break
    title = ""
    stats_text = ""
    release = ""
    role = ""
    ai = False
    genres: List[str] = []
    if info is not None:
        image = anchor.find("img")
        title_anchor = None
        for node in info.find_all("a"):
            if _id_of_url(node.attr("href"), "drama"):
                title_anchor = node
                break
        if title_anchor is not None:
            ai = _card_is_ai(title_anchor)
            title = clean(title_anchor.text)
            # 标题锚里可能挂着 ``AI`` / ``真人`` 角标 span，剥掉
            for token in ("AI", "真人"):
                title = re.sub(rf"^{token}\s*", "", title)
        if not title and image is not None:
            title = clean(image.attr("alt"))
        for node in info.find_all("div"):
            text = clean(node.text)
            if not text:
                continue
            if not stats_text and _STAT_RE.search(text) and "：" not in text:
                stats_text = text
            found = re.search(r"首播[：:]\s*([\d-]+)", text)
            if found and not release:
                release = found.group(1)
            found = re.search(r"出演角色[：:]\s*(.+)", text)
            if found and not role:
                role = clean(found.group(1))
        for chip in info.find_all("span"):
            if "bg-blue-100" in chip.classes or "bg-blue-900" in chip.classes:
                text = clean(chip.text)
                if text and text not in _BADGE_NOISE and text not in genres:
                    genres.append(text)

    heat = play_count = favorites = 0
    for value, label in _STAT_RE.findall(stats_text):
        number = _num(value)
        if label == "热度":
            heat = number
        elif label == "播放":
            play_count = number
        elif label == "收藏":
            favorites = number

    return {
        "kind": "drama",
        "native_id": native,
        "media_id": identity.media_id("drama", native),
        "url": work_url(native, domain),
        "title": title,
        "badge": badge,
        # 季号：卡上没有季标就是 0（``season_of_card`` 会退到剧名解析，
        # 再不行才算第一季）
        "season": season,
        # 状态角标（爆火 / 新剧 / 完结 / 预约…，多值、站点原样）：内容类型
        # ``badge`` 之外的第二条轴，订阅插件的作品卡按它印标签
        "badges": states,
        # AI 生成标（.org 独有；.net 卡片没有这个位置，恒 False）
        "is_ai": ai,
        "poster": poster,
        "release_date": release,
        "episodes": episodes,
        "rating": rating,
        "heat": heat,
        "play_count": play_count,
        "favorites": favorites,
        "role": role,
        "actors_text": "",
        "genres_text": "、".join(genres),
        "genres": genres,
    }


def parse_cards(html: str, domain: str = "") -> List[Dict[str, Any]]:
    root = parse_html(html)
    cards: List[Dict[str, Any]] = []
    seen: set = set()
    for anchor in _cover_anchor(root, "drama"):
        card = _card_of(anchor, domain)
        if not card:
            continue
        key = card["media_id"]
        if key in seen:
            continue
        seen.add(key)
        cards.append(card)
    return cards


def parse_actor_cards(html: str, domain: str = "") -> List[Dict[str, Any]]:
    """人物卡（演员目录 / 演员搜索页）：整卡就是一个 ``<a …/actor/<id>``。"""
    root = parse_html(html)
    rows: List[Dict[str, Any]] = []
    seen: set = set()
    for anchor in root.find_all("a"):
        native = _id_of_url(anchor.attr("href"), "actor")
        if not native or native in seen:
            continue
        # 只有真正的「人物卡」才带头像方块（aspect-square 容器），
        # 详情页里的同款链接（演员阵容）没有，避免把人物条目抓花
        image = anchor.find("img")
        if image is None:
            continue
        name = clean(image.attr("alt"))
        heading = anchor.find("div", cls="text-lg")
        if not name and heading is not None:
            name = clean(heading.text)
        if not name:
            continue
        seen.add(native)
        subtitle = ""
        biography = ""
        for node in anchor.find_all("div"):
            text = clean(node.text)
            if not subtitle and re.match(r"^[男女]\s*·", text):
                subtitle = text
        for node in anchor.find_all("p"):
            if "line-clamp" in " ".join(node.classes) and not biography:
                biography = clean(node.text)
        works_count = 0
        found = re.search(r"短剧\s*(\d+)", subtitle)
        if found:
            works_count = to_int(found.group(1))
        rows.append(
            {
                "kind": "actor",
                "native_id": native,
                "media_id": identity.media_id("actor", native),
                "url": actor_url(native, domain),
                "title": name,
                "name": name,
                "poster": clean(image.attr("src")) if image else "",
                "gender": subtitle[:1] if subtitle[:1] in ("男", "女") else "",
                "job_title": "",
                "works_count": works_count,
                "biography": biography,
            }
        )
    return rows


#: 演员详情页侧栏的「XX合作的演员」区块标题片段（实测 '' 前面就是本人姓名）
_COOP_TITLE = "合作的演员"


def _coop_people(root: Node, domain: str = "") -> List[Dict[str, Any]]:
    """演员页侧栏的「合作演员」→ ``people`` 行（``name`` / ``poster`` / ``media_id``）。

    这些人带**站点身份**（``<a …/actor/<id>>`` + 头像 + 名字），形态与作品页
    演职员行一致，所以入库口 ``service.detail._catalog_record`` 会连他们一起写进
    ID 库 —— 点开一位演员，把他常合作的人也带进来（2026-11-02 用户口径：
    「演员的详情附带的演员 id」也要入库）。

    区块标题是 ``<h2>魏依珂合作的演员</h2>``，卡片是它的祖父节点；只吃
    ``/actor/<id>`` 链接，页面别处的人物链接（演职员、作品卡）不会混进来。
    """
    for node in root.find_all("h2"):
        if _COOP_TITLE not in clean(node.text):
            continue
        card = node.parent.parent if node.parent is not None else node
        rows: List[Dict[str, Any]] = []
        seen: set = set()
        for anchor in card.find_all("a"):
            native = _id_of_url(anchor.attr("href"), "actor")
            if not native or native in seen:
                continue
            image = anchor.find("img")
            name = clean(image.attr("alt")) if image is not None else ""
            if not name:
                heading = anchor.find("div", cls="font-medium")
                name = clean(heading.text) if heading is not None else ""
            if not name:
                continue
            seen.add(native)
            rows.append(
                {
                    "name": name,
                    "role": "",
                    # 头像在 cdn.duanjubaike.org（白名单已登记），可随记录落盘
                    "poster": clean(image.attr("src")) if image is not None else "",
                    "media_id": identity.media_id("actor", native),
                }
            )
        return rows
    return []


def parse_search(html: str, domain: str = "") -> Dict[str, Any]:
    """检索页 → ``{"works", "actors", "novels"}``。

    .org 作品与人物是**两个端点**（不像 .net 一页同回两块），
    本函数两套页面通吃：卡片按身份前缀归类，抓哪个端点就出哪一类。
    ``novels`` 恒空 —— .org 没有原著体系。
    """
    works: List[Dict[str, Any]] = []
    actors: List[Dict[str, Any]] = []
    for card in parse_cards(html, domain):
        works.append(card)
    for card in parse_actor_cards(html, domain):
        actors.append(
            {
                **card,
                "job_title": card.pop("job_title", "") or "actor",
            }
        )
    return {"works": works, "actors": actors, "novels": []}


# ─────────────────────────── 作品页 ───────────────────────────


def _kv_from_html(html: str) -> Dict[str, str]:
    table: Dict[str, str] = {}
    for match in _KV_RE.finditer(html):
        key = clean(match.group("key"))
        value = clean(match.group("value"))
        if key and value and key not in table:
            table[key] = value
    return table


def _stats_from_dom(root: Node) -> Dict[str, int]:
    """统计块：``<span class="font-medium">17万</span> 播放``。"""
    stats = {"play_count": 0, "favorites": 0, "heat": 0}
    for node in root.find_all("div"):
        text = clean(node.text)
        found = _STAT_RE.search(text)
        if not found:
            continue
        number = _num(found.group(1))
        label = found.group(2)
        if label == "播放":
            stats["play_count"] = stats["play_count"] or number
        elif label == "收藏":
            stats["favorites"] = stats["favorites"] or number
        elif label == "热度":
            stats["heat"] = stats["heat"] or number
    return stats


def _status_of(root: Node) -> str:
    """角标（``新剧`` / ``完结`` 一类，只认短词）。"""
    for node in root.find_all("span"):
        text = clean(node.text)
        if text in ("新剧", "完结", "连载中", "已完结"):
            return text
    return ""


def _section(root: Node, keyword: str) -> Optional[Node]:
    """按 ``<h2>`` 文本找区块容器（h2 的父级就是「标题 + 卡片列表」那块卡片）。"""
    text_key = str(keyword or "").strip()
    if not text_key:
        return None
    for node in root.find_all("h2"):
        if text_key in clean(node.text):
            return node.parent
    return None


def _section_works(root: Node, keyword: str, domain: str = "") -> List[Dict[str, Any]]:
    """区块里的作品卡（与搜索 / 列表页同构，直接走 :func:`_card_of`）。

    一个区块里每张卡会出现两个同 href 的锚（封面锚 + 标题锚），``_card_of`` 对
    两者产出同一张卡 —— 按 ``media_id`` 去重。
    """
    box = _section(root, keyword)
    if box is None:
        return []
    cards: List[Dict[str, Any]] = []
    seen: set = set()
    for anchor in box.find_all("a"):
        if not anchor.attr("href"):
            continue
        card = _card_of(anchor, domain)
        key = str(card.get("media_id") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        cards.append(card)
    return cards


def _novel_block(root: Node) -> Dict[str, Any]:
    """「《剧名》原著小说」区块：``{title, poster, genres}``（没有就是空 dict）。

    整块**没有链接**（2026-11-02 实测 0 个 ``<a>``）⇒ 拿不到 ``xiaoshuo:<id>``，
    所以不写 ``media_id``：写个空身份的行进 ID 库只会变成搜不到的脏数据。
    平台名（番茄小说…）站点只有一行灰色小字，没有对应字段，丢掉。
    """
    box = _section(root, ORG_NOVEL_SECTION)
    if box is None:
        return {}
    image = box.find("img")
    title = clean(image.attr("alt")) if image is not None else ""
    poster = clean(image.attr("src")) if image is not None else ""
    if not title:
        for node in box.find_all("div"):
            if "font-medium" in node.classes and clean(node.text):
                title = clean(node.text)
                break
    if not title:
        return {}
    genres = [
        clean(chip.text)
        for chip in box.find_all("span")
        if "bg-gray-100" in chip.classes and clean(chip.text)
    ]
    return {"title": title, "poster": poster, "genres": genres}


# ───────────────────── 热评（作品页 ``<section id="comments">``） ─────────────────────
#
# 2026-11-02 用户口径「作品详情支持网站的评论」。站点这块是 **Alpine 横滑卡片**：
# ``<article>`` × 最多 9 条，每条只有「头像 / 昵称 / 星级 / 正文 / 点赞数」，
# **没有**时间、没有评论 ID、没有分页，也没有「全部评论」入口（实测
# ``/zh-Hans/drama/71920`` 56KB 区块里 9 个 ``<article>``，区块尾部直接 ``</section>``）。
# 所以这里不加 ``time`` / ``id`` 字段、不编造 —— 前端按数组下标做 key。

#: 评论卡上的两条 ``aria-label``：``评分 10.0/10`` 与 ``点赞 6``（站点只印这两个数）。
_COMMENT_RATING_RE = re.compile(r"评分\s*([0-9]+(?:\.[0-9]+)?)")
_COMMENT_VOTES_RE = re.compile(r"点赞\s*([0-9]+)")


def _comments_region(html: str) -> str:
    """``<section id="comments">`` 那一段 HTML（没有评论区给空串）。

    评论卡用的全是工具类（``group flex w-72 shrink-0 snap-start``），样式一动就失效，
    而 **``id="comments"`` 是站点自己的锚点**（页面内跳转要它，稳定）。所以先按
    ``id`` 找到位置、往前回退到 ``<section``，再截到配对的 ``</section>``。
    """
    anchor = html.find('id="comments"')
    if anchor < 0:
        return ""
    start = html.rfind("<section", 0, anchor)
    if start < 0:
        return ""
    end = html.find("</section>", start)
    if end < 0:
        return ""
    return html[start:end]


def comments_of(html: str) -> List[Dict[str, Any]]:
    """作品页「热评」→ ``[{author, avatar, content, rating, votes}]``。

    ``rating`` 是站点的 10 分制原值（星星宽度那份百分比换算出来的），展示时
    由前端折成 5 星；``votes`` 是「点赞」数（站点把它当「有用」用）。取不到的
    项留空 / 0，**不猜**。
    """
    region = _comments_region(html)
    if not region:
        return []
    root = parse_html(region)
    rows: List[Dict[str, Any]] = []
    for article in root.find_all("article"):
        body = article.find("p")
        content = clean(body.text) if body is not None else ""
        if not content:
            # 没有正文的卡（站点偶尔留占位）不占一行
            continue
        author = avatar = ""
        rating = 0.0
        votes = 0
        for node in article.walk():
            if node.tag == "img" and not avatar:
                avatar = clean(node.attr("src"))
                continue
            label = clean(node.attr("aria-label"))
            if label:
                found = _COMMENT_RATING_RE.search(label)
                if found:
                    rating = to_float(found.group(1))
                    continue
                found = _COMMENT_VOTES_RE.search(label)
                if found:
                    votes = to_int(found.group(1))
                    continue
            if node.tag == "span" and not author and node.has_class("truncate"):
                author = clean(node.text)
        rows.append(
            {
                "author": author,
                "avatar": avatar,
                "content": content,
                "rating": rating,
                "votes": votes,
            }
        )
    return rows


def parse_work(html: str, url: str = "", domain: str = "") -> Dict[str, Any]:
    root = parse_html(html)
    graph = _graph(html)
    series_node = next(iter(_typed(graph, "TVSeries")), {})
    kind, native = identity.page_identity(url)
    kind = kind or "drama"
    if not native:
        native = _id_of_url(url, "drama")

    heading = root.find("h1")
    title = clean(series_node.get("name") or "") or clean(heading.text if heading else "")
    if not title:
        title = title_in_books(_meta(root, "og:title"))

    # 海报：og:image 是完整封面（卡片缩略图是 /thumb/cover/，详情页才是 /cover/）
    poster = clean(_meta(root, "og:image")) or clean(series_node.get("image") or "")

    table = _kv_from_html(html)
    release = clean(series_node.get("datePublished") or "") or table.get("首播时间", "")
    episodes = to_int(series_node.get("numberOfEpisodes")) or _num(
        table.get("集数", "").replace("集", "")
    )
    duration = _duration_text(series_node.get("duration") or "") or clean(
        table.get("时长", "")
    )
    genres = [
        clean(item)
        for item in (series_node.get("genre") or [])
        if clean(item)
    ]
    if not genres:
        genres = [
            clean(chip.text)
            for chip in root.find_all("span")
            if ("bg-blue-100" in chip.classes or "bg-blue-900" in chip.classes)
            and clean(chip.text)
        ]
    synopsis = clean(series_node.get("description") or "") or _meta(root, "description")
    stats = _stats_from_dom(root)

    # 演职员：JSON-LD PerformanceRole（characterName + Person），比 DOM 稳
    people: List[Dict[str, Any]] = []
    seen: set = set()
    for role in series_node.get("actor") or []:
        if not isinstance(role, dict):
            continue
        person = role.get("actor") or {}
        if not isinstance(person, dict):
            continue
        person_native = _id_of_url(person.get("@id") or person.get("url") or "", "actor")
        if not person_native or person_native in seen:
            continue
        seen.add(person_native)
        people.append(
            {
                "name": clean(person.get("name") or ""),
                "role": clean(role.get("characterName") or ""),
                "kind": "actor",
                "media_id": identity.media_id("actor", person_native),
                # 头像：JSON-LD 的 Person 自带 CDN 地址（.org 不能按身份现拼）
                "poster": clean(person.get("image") or ""),
            }
        )
    if not people:
        # JSON-LD 缺席时的 DOM 兜底：演员阵容区块 ``饰 <角色名>``
        people = _people_from_dom(root)

    rating_value = 0.0
    aggregate = series_node.get("aggregateRating")
    if isinstance(aggregate, dict):
        rating_value = to_float(aggregate.get("ratingValue"))

    # 关系区块（2026-11-02）：同一部作品的其他季 / 同一剧本的其他版本 /
    # 同一小说的其他版本 / 原著小说。四块都只在本页出现，卡片结构与搜索页同构。
    series_cards = _section_works(root, ORG_SERIES_SECTION, domain)
    same_script = _section_works(root, ORG_SAME_SCRIPT_SECTION, domain)
    adapted = _novel_block(root)
    if adapted:
        # 「同一小说还拍了以下版本」是**原著**的派生列表，跟 ``adapted_from.works``
        # 同一语义（.net 那侧也是这么存的）；原著块本身没有 id，works 才是可点的卡。
        adapted["works"] = _section_works(root, ORG_SAME_NOVEL_SECTION, domain)

    return {
        "media_id": identity.media_id(kind, native),
        # AI 生成标（标题行左侧那颗小标）：只用于「要不要进 ID 库」这一件事，
        # 不影响识别 / 播放 / 详情字段。
        "is_ai": _heading_is_ai(heading),
        # 站点页面上没有 TMDB 外链，先占位为 0；真实值由编排层匹配后回写（不猜）
        "tmdb_id": 0,
        "title": title,
        # 本页季号：剧名解析（``冒姓琅琊2`` 这种写法解析不出季，会算成第一季）。
        # 其他季各自的季号在 series 卡上，由封面季标换算（见 ``_cover_field``）。
        "season": season_of_text(title) or 1,
        "year": (release or "")[:4],
        "release_date": release,
        "episodes": episodes,
        "duration": duration,
        "status": _status_of(root),
        "rating": rating_value,
        "play_count": stats.get("play_count", 0),
        "heat": stats.get("heat", 0),
        "favorites": stats.get("favorites", 0),
        "genres": genres,
        "studio": clean(table.get("版权方", "")),
        "platform": "",
        "adapted_from": adapted,
        "series": series_cards,
        # 同一剧本的其他版本（含各季、AI 版、翻拍版）：站点原样，展示时按 id 去重
        "same_script": same_script,
        "people": [
            {
                "name": str(row.get("name") or ""),
                "role": str(row.get("role") or ""),
                "media_id": str(row.get("media_id") or ""),
                "poster": str(row.get("poster") or ""),
            }
            for row in people
        ],
        "synopsis": synopsis,
        "poster": poster,
        # 站点「热评」：与作品同页，解析零成本（.net 那侧恒为空列表）
        "comments": comments_of(html),
    }


def _people_from_dom(root: Node) -> List[Dict[str, Any]]:
    """演员阵容区块的 DOM 兜底（JSON-LD 缺席时）。"""
    rows: List[Dict[str, Any]] = []
    seen: set = set()
    section: Optional[Node] = None
    for node in root.find_all("h2"):
        if "演员阵容" in clean(node.text):
            section = node.parent
            break
    if section is None:
        return rows
    for anchor in section.find_all("a"):
        native = _id_of_url(anchor.attr("href"), "actor")
        if not native or native in seen:
            continue
        name = clean(anchor.text)
        if not name:
            continue
        seen.add(native)
        # 角色名：演员名所在 div 的下一个兄弟块里的 ``饰 X``
        role = ""
        holder = anchor.parent
        for node in (holder.walk() if holder is not None else []):
            text = clean(node.text)
            found = re.search(r"饰\s*(.+)", text)
            if found:
                role = clean(found.group(1))
                break
        poster = ""
        image = anchor.find("img")
        if image is not None:
            poster = clean(image.attr("src"))
        rows.append(
            {
                "name": name,
                "role": role,
                "kind": "actor",
                "media_id": identity.media_id("actor", native),
                "poster": poster,
            }
        )
    return rows


# ─────────────────────────── 人物页 ───────────────────────────


def parse_actor(html: str, url: str = "", domain: str = "") -> Dict[str, Any]:
    root = parse_html(html)
    graph = _graph(html)
    person_node = next(iter(_typed(graph, "Person")), {})
    kind, native = identity.page_identity(url)
    kind = kind or "actor"
    if not native:
        native = _id_of_url(url, "actor")

    heading = root.find("h1")
    name = clean(person_node.get("name") or "") or clean(heading.text if heading else "")
    if not name:
        name = title_in_books(_meta(root, "og:title"))
    poster = clean(person_node.get("image") or "") or clean(_meta(root, "og:image"))
    job_title = clean(person_node.get("jobTitle") or "")
    biography = clean(_meta(root, "description"))
    if not biography:
        # DOM 兜底：正文里以本人姓名开头的那段长介绍
        for node in root.find_all("p"):
            text = clean(node.text)
            if text.startswith(name) and len(text) >= 20:
                biography = text
                break

    table = _kv_from_html(html)
    profile = _profile_of(biography)
    # .org 的个人资料是**结构化键值**，比文案拆解可信 —— 有就覆盖
    if table.get("性别") in ("男", "女"):
        profile["gender"] = table["性别"]
    if table.get("出生日期"):
        birth = table["出生日期"]
        found = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", birth)
        if found:
            profile["birth_date"] = "%s-%02d-%02d" % (
                found.group(1),
                int(found.group(2)),
                int(found.group(3)),
            )
            profile["birth_year"] = found.group(1)
        elif _DATE_RE.search(birth):
            profile["birth_date"] = _DATE_RE.search(birth).group(0)
            profile["birth_year"] = profile["birth_date"][:4]
    if table.get("星座"):
        profile["constellation"] = table["星座"]
    if table.get("国籍"):
        profile["nationality"] = table["国籍"]
    if table.get("出生地") or table.get("籍贯"):
        profile["birth_place"] = clean(table.get("出生地") or table.get("籍贯"))
    if table.get("教育背景") or table.get("毕业院校"):
        profile["education"] = clean(table.get("教育背景") or table.get("毕业院校"))

    # 粉丝数 / 作品数：``64万 抖音粉丝``、``41 部短剧``
    # 数字必须**紧贴**量词 —— 外层容器把「41 部短剧」和「64万 抖音粉丝」
    # 揉在同一段文本里，泛搜会抓错
    followers = 0
    works_count = 0
    for node in root.find_all("div"):
        text = clean(node.text)
        if not followers:
            found = re.search(r"([\d,.]+\s*万?)\s*抖音粉丝", text)
            if found:
                followers = _num(found.group(1))
        if not works_count:
            found = re.search(r"(\d+)\s*部短剧", text)
            if found:
                works_count = to_int(found.group(1))
    # 档案里代表性的粉丝字段再兜底一次（与 .net 同名同义）
    if not followers:
        followers = _num(table.get("粉丝数量", ""))

    works = parse_cards(html, domain)
    if not works_count:
        works_count = len(works)

    return {
        "kind": kind,
        "native_id": native,
        "media_id": identity.media_id(kind, native),
        "url": actor_url(native, domain) or url,
        "name": name,
        "job_title": job_title,
        "gender": profile.get("gender", ""),
        "followers": followers,
        "likes": 0,
        "poster": poster,
        "biography": biography,
        "works": works,
        "works_count": works_count,
        # 侧栏「XX合作的演员」前 20 位：带站点身份，随详情一起进 ID 库
        "people": _coop_people(root, domain),
        **profile,
    }


def parse_people_list(html: str, kind: str = "", domain: str = "") -> Dict[str, Any]:
    """人物目录（``/zh-Hans/actor?page=N``）。``kind`` 参数兼容 .net 签名，忽略。"""
    rows = parse_actor_cards(html, domain)
    pages = [int(item) for item in re.findall(r"[?&]page=(\d+)", html)]
    return {"people": rows, "last_page": max(pages) if pages else 1}


