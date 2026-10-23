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
