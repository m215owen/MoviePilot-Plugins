"""站点页面抓取与解析：人物目录 ``/<kind>/list.html``（``list_people`` 用）与
榜单页 ``/paihang/<key>.html``、推荐页 ``/tuijian.html``（``rank_medias`` 用）。

原「探索页榜单」的宿主注入（``DiscoverSource`` + ``/explore`` 端点）已于
2026-10-23 移除；同日榜单改为**跨插件模块方法**供给（``list_ranks`` /
``rank_medias``），本模块负责它的抓取与解析。榜单卡按**实际页面**解析
（2026-10-23 用户口径：不与 ``actor_works`` 卡形对齐），每个页面长什么样就
出什么字段 —— 排行榜卡带热度 / 评分，推荐卡带日期 / 演员行，互不硬凑。
"""

from __future__ import annotations

import re
from typing import Optional

from app.sdk.logging import logger
from app.sdk.network import AsyncRequestUtils

from . import constants
from .harvest import name_near_link
from .media_id import media_id_of, scan_ids


async def _get_html(url: str, label: str, *, timeout: int = 15) -> Optional[str]:
    """GET 一个站点页面并返回文本；任何失败返回 None（调用方降级）。"""
    if not url:
        return None
    try:
        response = await AsyncRequestUtils().get_res(url, timeout=timeout)
    except Exception as err:  # pragma: no cover - 网络异常统一降级
        logger.warning(f"{constants.SOURCE_NAME} {label}请求失败 {url}：{err}")
        return None
    if response is None:
        return None
    status = getattr(response, "status_code", 0)
    if status != 200:
        logger.warning(f"{constants.SOURCE_NAME} {label}状态异常 {url}：HTTP {status}")
        return None
    return getattr(response, "text", "") or ""


async def fetch_people_list_html(
    kind: str, page: int = 1, *, timeout: int = 15
) -> Optional[str]:
    """抓人物目录页 ``/<kind>/list.html?page=N``。失败返回 None。"""
    return await _get_html(
        constants.people_list_url(kind, page), f"人物目录({kind} p{page})",
        timeout=timeout,
    )


def parse_people_page(html: str, kind: str) -> tuple[list[tuple[str, str]], int]:
    """人物目录页 → ``([(media_id, name)], total_pages)``。

    卡片解析用 ``scan_ids`` + ``name_near_link``，只留本分类条目、按页面顺序去重；
    总页数取分页导航里本分类的最大页码，没有导航按 1 页算。
    """
    kind_key = str(kind or "").strip().lower()
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    for entity, native_id in scan_ids(html):
        if entity != kind_key:
            continue
        media_id = media_id_of(entity, native_id)
        if not media_id or media_id in seen:
            continue
        seen.add(media_id)
        rows.append((media_id, str(name_near_link(html, native_id) or "").strip()))
    total = 1
    for num in re.findall(rf"/{re.escape(kind_key)}/list\.html\?page=(\d+)", html):
        total = max(total, int(num))
    return rows, total


async def fetch_rank_html(
    key: str, page: int = 1, *, timeout: int = 15
) -> Optional[str]:
    """抓榜单页（``/paihang/<key>.html``，推荐页 ``/tuijian.html?page=N``）。

    失败返回 None（调用方降级为空榜）。不支持翻页的榜忽略 ``page``。
    """
    return await _get_html(
        constants.rank_url(key, page), f"榜单({key} p{page})", timeout=timeout
    )


def rank_total_pages(html: str) -> int:
    """榜单页的分页总数（推荐页有 ``page=N`` 导航）；没有导航按 1 页算。"""
    total = 1
    for num in re.findall(r"page=(\d+)", html):
        try:
            total = max(total, int(num))
        except ValueError:
            continue
    return total


def _card_chunks(html: str):
    """页面 HTML → 一段一段的 ``<a class="card">`` 卡片块（保页面顺序）。"""
    for chunk in html.split("<a ")[1:]:
        if 'class="card"' not in chunk or "info-" not in chunk:
            continue
        if 'data-cunzai="0"' in chunk:
            continue
        yield chunk


def _card_identity(chunk: str) -> tuple[str, str, str, str]:
    """卡片块 → ``(media_id, native_id, entity, href)``；无详情 id 返回空串。"""
    href_matched = re.search(r'href="([^"]*)"', chunk)
    href = href_matched.group(1).strip() if href_matched else ""
    if "/info-" not in href:
        return "", "", "", href
    entity = href.partition("/info-")[0].strip("/").split("/")[-1]
    native_id = href.partition("/info-")[2].split(".html")[0]
    return media_id_of(entity, native_id) or "", native_id, entity, href


def _card_title(chunk: str, native_id: str) -> str:
    """卡片标题：先取 ``title="…《剧名》"``，退回大字行，再退回 id。"""
    title_matched = re.search(r'title="[^"]*《([^》]+)》', chunk)
    if title_matched:
        return title_matched.group(1).strip()
    name_matched = re.search(r"text-lg font-semibold[^>]*>([^<]+)<", chunk)
    return name_matched.group(1).strip() if name_matched else native_id


def _card_badge(chunk: str, entity: str) -> str:
    """左上形态角标（「短剧」「AI剧」…）；没有按分类名兜底。"""
    badge_matched = re.search(r"top-2 left-2[^>]*>([^<]+)<", chunk)
    if badge_matched and badge_matched.group(1).strip():
        return badge_matched.group(1).strip()
    return constants.KIND_OF_ENTITY.get(entity, "短剧")


def _card_episodes(chunk: str) -> int:
    """右下角「全 N 集」→ N；没有给 0。"""
    ep_matched = re.search(r"全\s*(\d+)\s*集", chunk)
    return int(ep_matched.group(1)) if ep_matched else 0


def parse_paihang_cards(html: str) -> list[dict]:
    """排行榜页（``/paihang/<key>.html``）HTML → 卡行（按页面顺序、按 id 去重）。

    卡片形态（2026-10-23 对照站点实测逐字段核对）：``<a class="card" …>`` 内含
    形态角标（左上）、热度（左下）、总集数（右下）、标题、两行小字（评分行 /
    题材·演员行）。

    2026-10-23 用户口径：只留必要字段 —— ``media_id / title / badge /
    episodes / actors_text``；热度、评分、题材不要，海报与链接由 ``media_id``
    现推（不在缓存里存）。``date`` 恒空（排行榜卡没有日期）。

    小字「题材·演员·演员」行：拆开后丢掉首段题材，其余当演员。
    """
    rows: list[dict] = []
    seen: set[str] = set()
    for chunk in _card_chunks(html):
        media_id, native_id, entity, _href = _card_identity(chunk)
        if not media_id or media_id in seen:
            continue
        seen.add(media_id)
        small = [
            text.strip()
            for text in re.findall(r'text-sm[^"]*"[^>]*>([^<]+)</div>', chunk)
            if text.strip()
        ]
        mixed_text = next((text for text in small if "评分" not in text), "")
        # 小字行实测两种形态：「题材·演员·演员」（·分隔）与「题材 / 演员 / 演员」
        # （/ 分隔）—— 按出现的分隔符拆，首段是题材不进演员
        segments = [
            seg.strip() for seg in re.split(r"[·/，,]", mixed_text) if seg.strip()
        ]
        rows.append(
            {
                "media_id": media_id,
                "title": _card_title(chunk, native_id),
                "badge": _card_badge(chunk, entity),
                "episodes": _card_episodes(chunk),
                "date": "",
                "actors_text": " / ".join(segments[1:]),
            }
        )
    return rows


def parse_tuijian_cards(html: str) -> list[dict]:
    """推荐页（``/tuijian.html``）HTML → 卡行（按页面顺序、按 id 去重）。

    卡片形态（2026-10-23 对照站点实测逐字段核对）：``<a class="card" …>`` 内含
    形态角标（左上）、**上线日期**（左下，如「2026-10-14」）、总集数（右下）、
    标题、两行小字（演员行 / 题材行，都是「 / 」分隔，顺序固定）。

    2026-10-23 用户口径：只留必要字段 —— ``media_id / title / badge /
    episodes / date / actors_text``；题材不要，海报与链接由 ``media_id`` 现推。
    只有一行小字时那是题材行（站点省了演员行）⇒ ``actors_text`` 留空。
    """
    rows: list[dict] = []
    seen: set[str] = set()
    for chunk in _card_chunks(html):
        media_id, native_id, entity, _href = _card_identity(chunk)
        if not media_id or media_id in seen:
            continue
        seen.add(media_id)
        date_matched = re.search(
            r'bottom-2 left-2[^>]*>\s*(\d{4}-\d{2}-\d{2})\s*<', chunk
        )
        small = [
            text.strip()
            for text in re.findall(r'text-sm[^"]*"[^>]*>([^<]+)</div>', chunk)
            if text.strip()
        ]
        # 两行时顺序固定：先演员后题材；只有一行时站点省了演员行（那行是题材）
        actors_text = small[0] if len(small) >= 2 else ""
        rows.append(
            {
                "media_id": media_id,
                "title": _card_title(chunk, native_id),
                "badge": _card_badge(chunk, entity),
                "episodes": _card_episodes(chunk),
                "date": date_matched.group(1).strip() if date_matched else "",
                "actors_text": actors_text,
            }
        )
    return rows


#: 榜单 key → 解析器（每本榜按实际页面各写各的；推荐页结构与排行榜页不同）
RANK_PARSERS = {
    "tuijian": parse_tuijian_cards,
}
DEFAULT_RANK_PARSER = parse_paihang_cards
