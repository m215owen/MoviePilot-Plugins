"""短剧百科数据源 · URL 发现（搜索引擎的站点限定检索）。

站点的站内检索是 Cloudflare 托管挑战，服务端恒 403；搜索页那条路已经彻底放弃。
所以「片名 / 演员名 → 页面 URL」这一跳交给搜索引擎：``site:<域名> <关键词>``。

引擎返回的每一条都是**带完整 URL 的结构化行**（``title`` / ``href`` / ``body``，
实测 ddgs 9.14.4），所以这里只做两件事：发检索、按 URL 形态分成「作品」与「演员」
两类（``/drama/<id>`` / ``/actor/<id>``）。真正的解析在 :mod:`parser`，
URL 的沉淀在 :mod:`store`。
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, Iterable, List, Tuple

from .constants import (
    DEFAULT_WEB_INDEX_BACKEND,
    WEB_INDEX_MAX_RESULTS,
    WEB_INDEX_MIN_INTERVAL,
    WEB_INDEX_TIMEOUT,
)
from .parser import (
    _clean,
    _strip_org_suffix,
    canonical_page_url,
    href_points_to_simplified,
    web_index_actor_id,
    web_index_native_id,
)

try:  # 宿主依赖里的多引擎搜索（DDGS）；缺失时该通道自动停用
    from ddgs import DDGS as _DDGS
except Exception:  # pragma: no cover - 宿主版本差异兜底
    _DDGS = None  # type: ignore[assignment]

__all__ = ["WebIndex", "extract_urls"]


def _engine_available() -> bool:
    return _DDGS is not None


class WebIndex:
    """站外检索的入口，带最小间隔节流。

    引擎不接受高频调用：相邻两次检索挨得太近，第二次直接放弃（返回空列表），
    由调用方决定兜底行为。节流状态是**实例级**的，跟着插件实例走。
    """

    def __init__(self, min_interval: float = WEB_INDEX_MIN_INTERVAL) -> None:
        self._lock = threading.Lock()
        self._last_at = 0.0
        self._min_interval = min_interval

    @property
    def available(self) -> bool:
        """引擎依赖是否可用（宿主没装 ddgs 时为 False）。"""
        return _engine_available()

    def reset_throttle(self) -> None:
        """清掉节流时间戳（测试与手动刷新用）。"""
        with self._lock:
            self._last_at = 0.0

    def search(
        self,
        keyword: str,
        host: str,
        backend: str = DEFAULT_WEB_INDEX_BACKEND,
        max_results: int = WEB_INDEX_MAX_RESULTS,
    ) -> List[Dict[str, Any]]:
        """检索一次，返回原始结果行 ``[{"title", "href"}]``。

        失败、过频或引擎不可用一律返回空列表 —— 调用方据此走「库里已有的 URL」或
        报告没找到，绝不会因为引擎抽风而抛异常。

        :param keyword: 片名 / 演员名
        :param host: 站点主机名（``duanjubaike.org``）
        :param backend: 引擎后端（``auto`` / ``yandex`` / ...）
        :param max_results: 最多取多少条
        """
        keyword = _clean(keyword)
        host = _clean(host).lower()
        if not keyword or not host or not _engine_available():
            return []

        now = time.time()
        with self._lock:
            if now - self._last_at < self._min_interval:
                return []
            self._last_at = now

        try:
            with _DDGS(timeout=WEB_INDEX_TIMEOUT) as client:
                raw = list(
                    client.text(
                        f"site:{host} {keyword}",
                        backend=backend or DEFAULT_WEB_INDEX_BACKEND,
                        max_results=max_results,
                    )
                )
        except Exception:
            return []

        return [
            {
                "title": _strip_org_suffix(_clean(row.get("title") or "")),
                "href": _clean(row.get("href") or row.get("url") or ""),
            }
            for row in raw
        ]


def extract_urls(
    rows: Iterable[Dict[str, Any]], host: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """把原始结果行按 URL 形态分成「作品」与「演员」两类。

    结果里混着图集页（``/drama/37508/photos``）、榜单页与外域地址，只认路径恰好是
    ``/drama/<数字>`` 或 ``/actor/<数字>`` 的行 —— 它们的末尾数字就是站点 ID。

    取出的 ``url`` 会先过 :func:`parser.canonical_page_url` 归一化语言前缀：实测引擎
    会给出 ``/actor/371``（无前缀）与 ``/zh-Hant/actor/24243`` 这类地址，两者都会被
    301 到繁体页，繁体页里作品链接与统计标签的写法让解析**静默出 0 部作品 / 热度为 null**。

    同时给每行打一个 ``simplified`` 标记（**按引擎给的原地址判断**，不是归一化之后的）：
    只有 ``/zh-Hans/…`` 那行的标题才是简体，繁体 / 无前缀那行的标题是繁体 —— 同一部剧
    在引擎里常常一行简体一行繁体，繁体那行按简体关键词打分恒为 0，会被当成无关候选丢掉。
    调用方（:meth:`ShortDramaBaikeSource._discover`）据此决定要不要补抓一次简体页换标题。

    :param rows: :meth:`WebIndex.search` 的返回值
    :param host: 站点主机名（用于剔除外域结果）
    :return: ``(works, actors)``，每项含 ``native_id`` / ``label`` / ``url`` / ``simplified``
    """
    works: List[Dict[str, Any]] = []
    actors: List[Dict[str, Any]] = []
    seen: set = set()
    for row in rows:
        href = _clean(row.get("href") or "")
        title = _clean(row.get("title") or "")
        if not href:
            continue
        simplified = href_points_to_simplified(href)
        native_id = web_index_native_id(href, host)
        if native_id:
            key = ("work", native_id)
            if key not in seen:
                seen.add(key)
                works.append({"native_id": native_id, "label": title,
                              "url": canonical_page_url(href), "simplified": simplified})
            continue
        actor_id = web_index_actor_id(href, host)
        if actor_id:
            key = ("actor", actor_id)
            if key not in seen:
                seen.add(key)
                actors.append({"native_id": actor_id, "label": title,
                               "url": canonical_page_url(href), "simplified": simplified})
    return works, actors
