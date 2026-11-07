"""站内搜索 ``/so.html``：抓取、结果卡解析、空结果判定（计划 §5.1 第 ④ 层）。

实测（2026-10-21）：

* URL 形态 ``/so.html?keyword=<urlencoded>&page=<n>``，**每页 18 条**，``page`` 生效；
* 结果卡与目录页/搜索结果页卡片同构 —— ``<a href="/{entity}/info-{id}.html"
  title="短剧《X》" class="card">``，故直接复用 ``scan_ids`` 切 id、``name_near_link`` 取名；
* 搜人名会返回 ``yanyuan`` 卡（如「朱芝琳」→ 1 条人物），搜剧名返回作品卡；
* 无结果时页面有「没有找到 X 相关信息」，且**零个 info 链接**——以「零链接」为准判空。
"""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import quote

from app.sdk.logging import logger

from . import constants
from .fetcher import Fetcher
from .harvest import name_near_link
from .media_id import kind_from_card, media_id_of, scan_ids

PAGE_SIZE = 18

#: 结果卡的整块结构：``<a href="/{entity}/info-{id}.html" ...> … </a>``（卡内不嵌 a，可安全切块）
#: ``id`` **不假设任何字符集**：数字（``duanju``）、15 位字母数字混排（``huolong``）、
#: 将来换别的形态都照收，只要求「不含斜杠 / 引号 / 空白、以 ``.html`` 结尾」。
_CARD_BLOCK_RE = re.compile(
    r"""<a[^>]+href="/(?P<entity>\w+)/(?:info|book)-(?P<nid>[^/"'\s]+)\.html"[^>]*>(?P<body>.*?)</a>""",
    re.S,
)

#: **卡片右下角的分类角标** —— 站点明确标出「这个条目是什么」的那一处：
#: ``<div class="absolute bottom-2 right-2 bg-black/70 …">漫剧</div>``。
#: 2026-10-27 用户口径：判断短剧/漫剧看的就是这个字段（不是 ``title`` 属性）。
_BADGE_RE = re.compile(r"absolute bottom-2 right-2[^>]*>\s*(短剧|漫剧|小说|原著)\s*<")


def _card_kinds(html: str) -> dict[str, str]:
    """整页扫一遍 → ``{media_id: 短剧|漫剧|原著}``，**只认卡片右下角的角标**。

    2026-10-27 用户口径：「是否是漫剧从卡片右下角是唯一的」—— 这是站点唯一
    权威的分类标注，``title`` 属性、URL 前缀都不算数。

    按卡片块解析而不是整页正则：角标是**卡片内部**的元素，整页搜会把相邻卡片的
    标注错配到别人头上。

    ⚠️ 有的分区（实测 ``huolong``）卡片**没有角标**，这类条目的 ``kind`` 就是空串，
    上游不会把它当漫剧 —— 这正是「唯一依据」的预期结果，不要再用前缀去补。
    """
    kinds: dict[str, str] = {}
    for matched in _CARD_BLOCK_RE.finditer(html or ""):
        media_id = media_id_of(matched.group("entity"), matched.group("nid"))
        if not media_id or media_id in kinds:
            continue
        badge = _BADGE_RE.search(matched.group("body"))
        if not badge:
            continue
        kind = kind_from_card(badge.group(1))
        if kind:
            kinds[media_id] = kind
    return kinds


def search_url(keyword: str, page: int = 1, kind: str = "") -> str:
    """站内搜索页 URL；关键词为空返回空串。

    ``.org`` 主站时走新站检索端点：作品 ``/{lang}/drama/search``、人物
    ``/{lang}/actor/search``（两个端点，``kind="actor"`` 时才走人物那个）。
    新站检索页**不分页**（实测只有 ``q`` 参数），``page`` 被忽略。
    """
    word = (keyword or "").strip()
    if not word:
        return ""
    if constants.is_org_site():
        base = constants.SITE_DOMAINS[constants.SITE_ORG]
        path = "actor/search" if str(kind or "").strip().lower() == "actor" else "drama/search"
        return f"{base}/{constants.ORG_LANG}/{path}?q={quote(word)}"
    return f"{constants.SITE_BASE}/so.html?keyword={quote(word)}&page={max(1, int(page or 1))}"


def _parse_org_search_cards(html: str) -> list[tuple[str, str, str, str, bool, str]]:
    """``.org`` 检索页 → 与 ``.net`` 同形的 6 元组（AI 标 + 海报）。

    新站的卡片**同时**存在于作品与人物两个解析结果里（同一页面可能两类卡都有），
    这里按 ``media_id`` 合并去重、保持页面顺序：先作品后人物。

    末位 ``is_ai`` 取自卡片标题行的 ``AI短剧`` 标 —— 新站**没有**老站那种
    「短剧 / 漫剧」内容角标，AI 与否就是这个标；配置的「排除」开关在新站
    按它生效（见 ``service.is_excluded_item``）。

    第 6 位 ``poster`` 是页面自带的 CDN 绝对地址（含 UUID）。**必须随卡带出**：
    新站海报不能按 media_id 反推（:func:`service.image_url` 对 ``drama:`` 恒空），
    丢在这里搜索结果就永远无图（2026-11-03 用户反馈）。
    """
    from . import orgsite

    cards: list[tuple[str, str, str, str, bool, str]] = []
    seen: set[str] = set()
    rows = list(orgsite.parse_cards(html)) + list(orgsite.parse_actor_cards(html))
    for row in rows:
        media_id = str(row.get("media_id") or "").strip()
        if not media_id or media_id in seen:
            continue
        entity, _, native_id = media_id.partition(":")
        name = str(row.get("title") or row.get("name") or "").strip()
        # 新站卡片没有 .net 那种「短剧 / 漫剧」内容角标，类型只能看题材标签：
        # 站内把漫剧的题材里固定写了「漫剧」，角标有值时才优先用角标
        genres = [str(item) for item in (row.get("genres") or [])]
        kind = kind_from_card(str(row.get("badge") or "")) or (
            "漫剧" if "漫剧" in genres else ""
        )
        seen.add(media_id)
        cards.append(
            (
                entity,
                native_id,
                name,
                kind,
                bool(row.get("is_ai")),
                str(row.get("poster") or ""),
            )
        )
    return cards


def parse_search_cards(html: str) -> list[tuple[str, str, str, str, bool, str]]:
    """搜索结果页 → ``[(entity, native_id, name, kind, is_ai, poster)]``，按页面顺序、按 id 去重。

    只保留百科八类实体：搜索页偶尔会带站内其它链接，先按前缀白名单挡掉。

    ``kind`` 取自卡片右下角的**分类角标**（站点原样标注：短剧 / 漫剧 / 小说），
    值域「短剧 / 漫剧 / 原著」；卡片没有角标时给空串，由调用方决定要不要退回前缀推。
    2026-10-27 用户口径：判断是不是漫剧**就看这个字段**，别拿 URL 前缀硬猜。

    ``is_ai`` 只有 ``.org`` 卡片才有（标题行 ``AI短剧`` 标），老站恒 ``False``。

    ``poster`` 只有 ``.org`` 卡片带值（CDN 绝对地址，不能按 id 反推）；老站海报
    能按 media_id 反推（``image_url``），恒空串、由 ``_pack`` 兜底。

    ``.org`` 主站时换 :func:`_parse_org_search_cards`（新站卡片是 Alpine 模板，
    没有 ``info-`` 形态的链接，``scan_ids`` 那套规则不适用）。
    """
    if not html:
        return []
    if constants.is_org_site():
        return _parse_org_search_cards(html)
    kinds = _card_kinds(html)
    cards: list[tuple[str, str, str, str, bool, str]] = []
    seen: set[str] = set()
    for entity, native_id in scan_ids(html):
        if entity not in constants.ENTITY_ALL:
            continue
        media_id = media_id_of(entity, native_id)
        if not media_id or media_id in seen:
            continue
        seen.add(media_id)
        name = name_near_link(html, native_id)
        cards.append((entity, native_id, name, kinds.get(media_id, ""), False, ""))
    return cards


def is_empty_result(html: str, cards: Optional[list] = None) -> bool:
    """是否无结果：**零条卡片**即判空（页面无结果文案作二次确认，仅用于日志）。"""
    if not html:
        return True
    items = parse_search_cards(html) if cards is None else cards
    return not items


def has_no_result_text(html: str) -> bool:
    """页面是否含「没有找到 … 相关信息」文案（调试用，不参与判空决策）。"""
    return "没有找到" in (html or "")


async def fetch_search_html(
    keyword: str,
    page: int = 1,
    *,
    fetcher: Optional[Fetcher] = None,
    kind: str = "",
) -> Optional[str]:
    """抓搜索结果页；URL 非法 / 网络失败 / 软 404 返回 ``None``。"""
    url = search_url(keyword, page, kind=kind)
    if not url:
        return None
    client = fetcher or Fetcher()
    html = await client.get_html(url)
    if not html:
        logger.debug(f"{constants.SOURCE_NAME} 搜索页无内容：{keyword} p{page}")
    return html


async def search_cards(
    keyword: str,
    page: int = 1,
    *,
    fetcher: Optional[Fetcher] = None,
    kind: str = "",
) -> list[tuple[str, str, str, str, bool, str]]:
    """抓一页搜索结果并解析成卡片列表（失败返回 ``[]``）。

    元素形如 ``(entity, native_id, name, kind, is_ai, poster)``，``kind`` 来自卡片
    原始标注，``is_ai`` 只有 ``.org`` 卡片带值（标题行 ``AI短剧`` 标）；
    ``poster`` 只有 ``.org`` 卡片带值（CDN 绝对地址）。
    ``kind="actor"`` 只对 ``.org`` 有意义（作品 / 人物是两个检索端点）。
    """
    html = await fetch_search_html(keyword, page, fetcher=fetcher, kind=kind)
    return parse_search_cards(html) if html else []
