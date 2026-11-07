"""TMDB 通道：宿主 ``TmdbApi`` 的薄包装（回填 ``baike.tmdb`` 列用）。

为什么复用宿主 ``TmdbApi`` 而不是自己发请求：

* 宿主已内建 API key、缓存与语言策略，插件不该重复实现；
* 与 ``douban.py`` 同一纪律：只包薄薄一层，网络异常一律降级成空列表。

实测（2026-10-21）：TMDB 上**有**中文短剧收录——「以爱为家」→ 317820、
「移巢」→ 333508；但「春江许我愁」搜不到（TMDB 收录不全），所以回填判据
必须严格（名字完全相等 + 年份一致），查不到就空着，绝不猜。

与 ``douban.py`` 的差异：``async_search_tvs`` 要求带年份（无年份时同名混淆
风险大，调用方在 detail 没有年份时应直接跳过）。
"""

from __future__ import annotations

from typing import Any

from app.sdk.logging import logger

from . import constants


def _api():
    """取宿主 TMDB 客户端。"""
    from app.modules.themoviedb.tmdbapi import TmdbApi

    return TmdbApi()


def _normalize(item: Any) -> dict | None:
    """TMDB ``search/tv`` 的一条结果 → 归一化候选。"""
    if not isinstance(item, dict):
        return None
    tmdb_id = str(item.get("id") or "").strip()
    if not tmdb_id.isdigit():
        return None
    return {
        "id": tmdb_id,
        "name": str(item.get("name") or item.get("original_name") or item.get("title") or "").strip(),
        "year": str(item.get("first_air_date") or "").strip()[:4],
    }


async def tv_search(title: str, year: str) -> list[dict]:
    """按名 + 年份搜 TMDB 剧集；任何异常降级为空列表。"""
    word = (title or "").strip()
    if not word:
        return []
    try:
        api = _api()
        try:
            items = await api.async_search_tvs(word, str(year or ""))
        except AttributeError:
            # 宿主方法签名变化兜底：退回同步版
            items = api.search_tvs(word, str(year or ""))
    except Exception as err:  # pragma: no cover - 网络/通道异常一律降级
        logger.warning(f"{constants.SOURCE_NAME} TMDB 搜索失败 {word}：{err}")
        return []
    out: list[dict] = []
    for item in items or []:
        normalized = _normalize(item)
        if normalized:
            out.append(normalized)
    return out


# ── 影人（人物）通道：给 ``baike.tmdb`` 列绑 ``tmdbp:{pid}`` ─────────────────
#
# 宿主 ``TmdbApi`` 早就有 ``async_search_persons`` / ``async_get_person_credits``
# （2026-11-03 用户提醒「系统有人物搜索的接口」），所以人物不该只有豆瓣一条腿。
# 绑定判据与豆瓣侧同口径：**作品名交集**，零交集不绑（短剧演员重名极多）。


def _normalize_person(item: Any) -> dict | None:
    """TMDB ``search/person`` 的一条结果 → 归一化候选。"""
    if not isinstance(item, dict):
        return None
    pid = str(item.get("id") or "").strip()
    if not pid.isdigit():
        return None
    works = []
    for work in item.get("known_for") or []:
        if not isinstance(work, dict):
            continue
        title = str(work.get("name") or work.get("title") or "").strip()
        if title:
            works.append(title)
    path = str(item.get("profile_path") or "").strip()
    return {
        "media_id": f"{constants.TMDB_PERSON}:{pid}",
        "id": pid,
        "name": str(item.get("name") or "").strip(),
        "avatar": f"https://image.tmdb.org/t/p/w185{path}" if path else "",
        # ``known_for`` 是 TMDB 给的代表作（5 部上下），先拿它算交集，
        # 交集为零再去拉完整 credits —— 大多数情况省掉那次请求。
        "works": works,
    }


async def person_search(name: str) -> list[dict]:
    """按名搜 TMDB 影人；任何异常降级为空列表（与 ``tv_search`` 同纪律）。"""
    word = (name or "").strip()
    if not word:
        return []
    try:
        api = _api()
        try:
            items = await api.async_search_persons(word)
        except AttributeError:
            items = api.search_persons(word)
    except Exception as err:  # pragma: no cover - 网络/通道异常一律降级
        logger.warning(f"{constants.SOURCE_NAME} TMDB 影人搜索失败 {word}：{err}")
        return []
    out: list[dict] = []
    for item in items or []:
        normalized = _normalize_person(item)
        if normalized:
            out.append(normalized)
    return out


async def person_credits(person_id: str) -> list[str]:
    """影人作品**名字**清单（第 1 页，最多 24 条）；异常降级为空列表。"""
    pid = str(person_id or "").strip()
    if not pid.isdigit():
        return []
    try:
        api = _api()
        try:
            items = await api.async_get_person_credits(int(pid))
        except AttributeError:
            items = api.get_person_credits(int(pid))
    except Exception as err:  # pragma: no cover
        logger.warning(f"{constants.SOURCE_NAME} TMDB 影人作品失败 {pid}：{err}")
        return []
    out: list[str] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("name") or item.get("title") or "").strip()
        if title:
            out.append(title)
    return out
