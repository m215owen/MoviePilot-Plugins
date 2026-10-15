"""短剧百科数据源 · TMDB 真实身份补充。

**为什么需要它**：宿主详情页里，右侧信息面板（评分星条 / 状态 / 首播日期 / 出品方 / 原语言）、
演职员区、推荐 / 相似、分季分集，**全部挂在 ``tmdb_id`` 上**（前端 ``media-*.js`` 里是
``tmdb_id`` / ``douban_id`` / ``bangumi_id`` / ``anilist_id`` 四个布尔分支，插件来源一个都进不去）。
更关键的是：这些区块的内容**不是读 ``MediaInfo``**，而是宿主拿着 ``tmdb_id`` 自己去 TMDB 取
（``/api/v1/tmdb/credits/{id}/{type}``、``tmdb/recommend/{id}`` …）。所以**只要给出一个真实且正确的
``tmdb_id``，那几块立刻就全亮了**。

**严格匹配，宁可漏不可错**：实测短剧大多不在 TMDB 上（抽 14 部只命中 1 部），所以这里只做
「有就附、没有就算」：按片名 + 首播年在 TMDB 搜一次，要求归一化片名**完全相等**，
年份已知时要求一致（容差 1 年）、年份未知时只接受唯一候选。附错 ID 的代价是把页面连到另一部剧，
演员 / 推荐 / 分季全是别人的 —— 比不显示糟得多。

补充是**尽力而为**：有负结果缓存、失败只记 debug、不影响识别主流程。
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.parse
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.sdk.logging import logger

from .constants import PLUGIN_NAME
from .parser import _clean, _normalize_title

__all__ = ["TmdbIdentity", "build_season_info"]

# 身份几乎不会变，TTL 主要是防抖：同一部剧的多次识别（识别 + 检索 + 面板）只查一次
IDENTITY_TTL = 86400
# 一次检索取多少条候选（同名作品最多也就几条，取多了只是白花流量）
MAX_RESULTS = 8
# 年份容差：站点记的首播年与 TMDB 的首播年允许差 1 年（跨年首播 / 上线日期口径不同）
YEAR_TOLERANCE = 1
# TMDB 接口前缀（域名与 key 都来自宿主的运行时配置，插件不另存一份）
API_PREFIX = "/3"


def _tmdb_setting(name: str) -> str:
    """从宿主的运行时配置里取 TMDB 域名 / key。

    插件自己不该另存一份密钥 —— 宿主把 ``TMDB_API_DOMAIN`` / ``TMDB_API_KEY`` 放在运行时配置里
    （面板上改的也能生效），这里跟着它走；取不到就退回环境变量（容器里也是这么注入的）。
    """
    try:
        from app.runtime.settings import get_runtime_setting

        value = get_runtime_setting(name)
        if value:
            return _clean(str(value))
    except Exception:  # pragma: no cover - 宿主版本差异兜底
        pass
    return _clean(os.environ.get(name, ""))


def build_season_info(detail: Dict[str, Any]) -> List[Dict[str, Any]]:
    """把 TMDB ``/tv/{id}`` 的 ``seasons`` 转成宿主 ``MediaInfo.season_info`` 的形状。

    宿主详情页的分季区块按 ``season_info[].{season_number,name,episode_count}`` 渲染，而该区块的
    渲染条件只看 ``type=电视剧 && tmdb_id``（与 ``season_info`` 是否为空无关）—— 不填的话
    那一段会只剩一个光秃秃的「分季分集」标题。
    """
    rows: List[Dict[str, Any]] = []
    for season in (detail or {}).get("seasons") or []:
        if not isinstance(season, dict):
            continue
        number = season.get("season_number")
        if not isinstance(number, int):
            continue
        rows.append(
            {
                "id": season.get("id"),
                "name": _clean(season.get("name")) or f"第 {number} 季",
                "season_number": number,
                "episode_count": season.get("episode_count"),
                "air_date": _clean(season.get("air_date")) or None,
                "overview": None,
                "poster_path": season.get("poster_path"),
                "vote_average": None,
                "order": None,
                "locked": None,
                "episodes": [],
            }
        )
    return rows


class TmdbIdentity:
    """片名 + 首播年 → TMDB 真实身份（带 TTL 缓存，**负结果也缓存**）。

    用插件自己的同步 GET（:meth:`ShortDramaBaikeSource._get`）发请求 —— 代理、超时、UA
    与站点请求保持一致，不另起一套客户端。
    """

    def __init__(self, getter: Callable[[str], Tuple[str, Optional[int]]]) -> None:
        self._get = getter
        self._lock = threading.Lock()
        self._cache: Dict[str, Tuple[float, Optional[Dict[str, Any]]]] = {}
        # 「宿主没配 TMDB」只在**首次**报一次：环境级问题，每次调用都报会把日志刷满
        self._warned_unavailable = False

    # ── 缓存 ──────────────────────────────────────────────────────

    def _cache_get(self, key: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        now = time.time()
        with self._lock:
            entry = self._cache.get(key)
        if not entry:
            return False, None
        expires, value = entry
        if expires and now > expires:
            with self._lock:
                self._cache.pop(key, None)
            return False, None
        return True, value

    def _cache_set(self, key: str, value: Optional[Dict[str, Any]]) -> None:
        with self._lock:
            self._cache[key] = (time.time() + IDENTITY_TTL, value)
            if len(self._cache) > 512:
                oldest = sorted(self._cache.items(), key=lambda pair: pair[1][0])
                for stale_key, _ in oldest[:128]:
                    self._cache.pop(stale_key, None)

    def clear(self) -> int:
        """清缓存（停止插件 / 清空库时调用）。返回清掉的条数。"""
        with self._lock:
            removed = len(self._cache)
            self._cache.clear()
        return removed

    # ── 查询 ──────────────────────────────────────────────────────

    def enrich(self, title: str, year: Any = "", type_hint: str = "tv") -> Dict[str, Any]:
        """查到就返回 ``{"tmdb_id": …, "season_info": […], "number_of_seasons": …}``，否则空字典。

        没有可信的同名条目、网络失败、宿主没配 TMDB —— 一律返回空字典（负结果也进缓存，
        免得同一部剧每次识别都重打一次 TMDB）。
        """
        title = _clean(title)
        year = _clean(str(year or ""))
        if not title:
            return {}
        cache_key = f"tmdb|{_normalize_title(title)}|{year}"
        hit, value = self._cache_get(cache_key)
        if hit:
            return dict(value or {})

        domain = _tmdb_setting("TMDB_API_DOMAIN")
        api_key = _tmdb_setting("TMDB_API_KEY")
        if not domain or not api_key:
            if not self._warned_unavailable:
                self._warned_unavailable = True
                logger.warning(
                    f"{PLUGIN_NAME} 宿主未配置 TMDB_API_DOMAIN / TMDB_API_KEY，"
                    f"跳过 TMDB 身份补充（详情页的演职员 / 推荐区因此不会出现）"
                )
            return {}

        rows = self._search(domain, api_key, title, type_hint)
        matched = self._pick(rows, title, year)
        extra: Dict[str, Any] = {}
        if matched:
            extra["tmdb_id"] = matched
            detail = self._detail(domain, api_key, matched)
            seasons = build_season_info(detail)
            if seasons:
                extra["season_info"] = seasons
                total = detail.get("number_of_seasons")
                if isinstance(total, int):
                    extra["number_of_seasons"] = total
            logger.info(
                f"{PLUGIN_NAME} 《{title}》({year or '年份未知'}) 在 TMDB 有真实同名条目 "
                f"{type_hint}/{matched}（{len(seasons)} 季）"
                f" —— 详情页的演职员 / 推荐 / 分季区块将走 TMDB"
            )
        else:
            logger.debug(
                f"{PLUGIN_NAME} 《{title}》在 TMDB 没有可信的同名条目（候选 {len(rows)} 条），"
                f"保持插件来源身份"
            )
        self._cache_set(cache_key, extra or None)
        return extra

    def _search(self, domain: str, api_key: str, title: str, type_hint: str) -> List[Dict[str, Any]]:
        """调一次 TMDB 检索，返回原始结果行。"""
        kind = "movie" if type_hint == "movie" else "tv"
        query = urllib.parse.urlencode(
            {"api_key": api_key, "language": "zh-CN", "query": title, "include_adult": "false"}
        )
        payload = self._json(f"https://{domain}{API_PREFIX}/search/{kind}?{query}", title)
        rows = payload.get("results")
        return list(rows or [])[:MAX_RESULTS]

    def _detail(self, domain: str, api_key: str, media_id: int) -> Dict[str, Any]:
        """取 ``/tv/{id}``，用于补 ``season_info`` / ``number_of_seasons``。"""
        query = urllib.parse.urlencode({"api_key": api_key, "language": "zh-CN"})
        return self._json(f"https://{domain}{API_PREFIX}/tv/{media_id}?{query}", f"tv/{media_id}")

    def _json(self, url: str, label: str) -> Dict[str, Any]:
        """发请求并解析 JSON；任何失败都返回空字典，绝不把异常抛给识别主流程。"""
        try:
            text, status = self._get(url)
        except Exception as err:  # pragma: no cover - 网络异常按「查不到」处理
            logger.debug(f"{PLUGIN_NAME} TMDB 请求「{label}」异常：{type(err).__name__}: {err}")
            return {}
        if not text or (status and status >= 400):
            logger.debug(f"{PLUGIN_NAME} TMDB 请求「{label}」失败：status={status}")
            return {}
        try:
            payload = json.loads(text)
        except (ValueError, TypeError):
            logger.debug(f"{PLUGIN_NAME} TMDB 请求「{label}」返回的不是 JSON（{len(text)} 字节）")
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _pick(rows: List[Dict[str, Any]], title: str, year: str) -> Optional[int]:
        """从候选里挑出**可信的同一部作品**，挑不出就返回 None。

        规则（越靠后越保守）：
        1. 归一化片名必须与 TMDB 的 ``name`` 或 ``original_name`` **完全相等**；
        2. 年份两边都知道时：只接受相差 ≤ 1 年，且优先取完全一致的那条；
        3. 我们年份未知或 TMDB 没给日期时：**只有唯一候选**才认 —— 同名多条宁可不附。
        """
        target = _normalize_title(title)
        if not target:
            return None
        dated: List[Tuple[int, float, int]] = []   # (年份差, 流行度, id)
        undated: List[Tuple[int, float, int]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            names = {
                _normalize_title(row.get("name")),
                _normalize_title(row.get("original_name")),
            }
            if target not in names:
                continue
            media_id = row.get("id")
            if not isinstance(media_id, int):
                continue
            popularity = row.get("popularity")
            popularity = float(popularity) if isinstance(popularity, (int, float)) else 0.0
            row_year = _clean(row.get("first_air_date"))[:4]
            if year.isdigit() and row_year.isdigit():
                gap = abs(int(year) - int(row_year))
                if gap <= YEAR_TOLERANCE:
                    dated.append((gap, popularity, media_id))
            elif not year.isdigit() or not row_year:
                undated.append((0, popularity, media_id))
        if dated:
            dated.sort(key=lambda item: (item[0], -item[1]))
            return dated[0][2]
        if len(undated) == 1:
            return undated[0][2]
        return None

    def credentials(self) -> Tuple[str, str]:
        """返回 (TMDB 域名, key)；任一为空表示宿主没配 TMDB。"""
        return _tmdb_setting("TMDB_API_DOMAIN"), _tmdb_setting("TMDB_API_KEY")
