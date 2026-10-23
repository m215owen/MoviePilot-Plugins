"""站内搜索 ``/so.html``：抓取、结果卡解析、空结果判定（计划 §5.1 第 ④ 层）。

实测（2026-10-21）：

* URL 形态 ``/so.html?keyword=<urlencoded>&page=<n>``，**每页 18 条**，``page`` 生效；
* 结果卡与目录页/搜索结果页卡片同构 —— ``<a href="/{entity}/info-{id}.html"
  title="短剧《X》" class="card">``，故直接复用 ``scan_ids`` 切 id、``name_near_link`` 取名；
* 搜人名会返回 ``yanyuan`` 卡（如「朱芝琳」→ 1 条人物），搜剧名返回作品卡；
* 无结果时页面有「没有找到 X 相关信息」，且**零个 info 链接**——以「零链接」为准判空。
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import quote

from app.sdk.logging import logger

from . import constants
from .fetcher import Fetcher
from .harvest import name_near_link
from .media_id import media_id_of, scan_ids

PAGE_SIZE = 18


def search_url(keyword: str, page: int = 1) -> str:
    """站内搜索页 URL；关键词为空返回空串。"""
    word = (keyword or "").strip()
    if not word:
        return ""
    return f"{constants.SITE_BASE}/so.html?keyword={quote(word)}&page={max(1, int(page or 1))}"


def parse_search_cards(html: str) -> list[tuple[str, str, str]]:
    """搜索结果页 → ``[(entity, native_id, name)]``，按页面顺序、按 id 去重。

    只保留百科八类实体：搜索页偶尔会带站内其它链接，先按前缀白名单挡掉。
    """
    if not html:
        return []
    cards: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for entity, native_id in scan_ids(html):
        if entity not in constants.ENTITY_ALL:
            continue
        media_id = media_id_of(entity, native_id)
        if not media_id or media_id in seen:
            continue
        seen.add(media_id)
        cards.append((entity, native_id, name_near_link(html, native_id)))
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
) -> Optional[str]:
    """抓搜索结果页；URL 非法 / 网络失败 / 软 404 返回 ``None``。"""
    url = search_url(keyword, page)
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
) -> list[tuple[str, str, str]]:
    """抓一页搜索结果并解析成卡片列表（失败返回 ``[]``）。"""
    html = await fetch_search_html(keyword, page, fetcher=fetcher)
    return parse_search_cards(html) if html else []
