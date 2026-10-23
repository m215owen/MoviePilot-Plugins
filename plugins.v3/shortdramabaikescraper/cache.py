"""缓存门面：按 region 管理详情、人物、豆瓣、检索、目录页与榜单卡。

宿主 ``TTLCache`` 自动选 Redis 或内存（本实例已配 Redis），签名实测
``(region, maxsize, ttl)``；可用方法含 ``get`` / ``set`` / ``delete`` / ``items`` /
``keys`` / ``clear``，管理面板的枚举与单条删除直接建立在它们之上。

有效期（2026-10-23 用户口径）：**全插件统一一份**，跟随宿主系统设置
``META_CACHE_EXPIRE``（小时，0 = 自动：普通 24h / 大内存 72h）——见
:func:`unified_ttl`。插件 init / 保存配置时经 :meth:`CacheFacade.refresh`
重读，宿主改设置即生效（TTL 变了就重建后端实例）。

纪律：缓存里只放**已物化的 dict / list**，不放 ORM 对象；缓存未命中不代表条目不存在。
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from app.sdk.cache import TTLCache

from . import constants


def _runtime_setting(name: str, default: Any) -> Any:
    """读宿主运行时设置；读不到 / 宿主结构变化时退回默认值。"""
    try:
        from app.runtime.config import settings

        return getattr(settings, name, default)
    except Exception:  # pragma: no cover - 宿主导入环境差异
        return default


def unified_ttl() -> int:
    """全插件统一的缓存有效期（秒）。

    系统设置 ``META_CACHE_EXPIRE`` > 0 时按它的小时数计；0 / 未配置走宿主
    自动口径 —— 普通模式 24 小时、大内存模式 72 小时。
    """
    try:
        hours = max(int(_runtime_setting("META_CACHE_EXPIRE", 0) or 0), 0)
    except (TypeError, ValueError):
        hours = 0
    if hours > 0:
        return hours * 3600
    big_memory = bool(_runtime_setting("BIG_MEMORY_MODE", False))
    return constants.AUTO_TTL_BIG_MEMORY if big_memory else constants.AUTO_TTL_NORMAL


class CacheFacade:
    """各 region 的统一入口（同一份统一 TTL）。"""

    def __init__(self) -> None:
        self._ttl = unified_ttl()
        self._build()

    def _build(self) -> None:
        """按当前 ``self._ttl`` 建全部 region（refresh 换 TTL 时先 close 再重建）。"""
        self.detail = TTLCache(
            region=constants.REGION_DETAIL,
            maxsize=constants.MAXSIZE_DETAIL,
            ttl=self._ttl,
        )
        self.person = TTLCache(
            region=constants.REGION_PERSON,
            maxsize=constants.MAXSIZE_PERSON,
            ttl=self._ttl,
        )
        self.douban = TTLCache(
            region=constants.REGION_DOUBAN,
            maxsize=constants.MAXSIZE_DOUBAN,
            ttl=self._ttl,
        )
        self.search = TTLCache(
            region=constants.REGION_SEARCH,
            maxsize=constants.MAXSIZE_SEARCH,
            ttl=self._ttl,
        )
        self.rank = TTLCache(
            region=constants.REGION_RANK,
            maxsize=constants.MAXSIZE_RANK,
            ttl=self._ttl,
        )
        # 负缓存（djbaike.neg）已移除：失败的 id 不再被记住（用户 2026-10-21 要求），
        # 下次访问就是重新探测一次 —— 站点偶尔抽风导致的"永久打不开"比多一次请求糟得多。

    def refresh(self) -> None:
        """重读系统缓存设置；TTL 变了就重建后端实例（TTL 是构造参数）。

        ⚠️ 重建前先 ``close()`` 旧的：Redis 后端持有连接，直接覆盖只会等 GC。
        """
        ttl = unified_ttl()
        if ttl == self._ttl:
            return
        self.close()
        self._ttl = ttl
        self._build()

    # ── 便捷方法 ─────────────────────────────────────────────────────
    def get_detail(self, media_id: str) -> Optional[dict]:
        """取详情缓存（键就是 media_id 本身）。"""
        value = self.detail.get(media_id) if media_id else None
        return value if isinstance(value, dict) else None

    def set_detail(self, media_id: str, detail: dict) -> None:
        """写详情缓存。"""
        if media_id and detail:
            self.detail.set(media_id, detail)

    def get_person(self, media_id: str) -> Optional[dict]:
        """取人物融合缓存。"""
        value = self.person.get(media_id) if media_id else None
        return value if isinstance(value, dict) else None

    def set_person(self, media_id: str, payload: dict) -> None:
        """写人物融合缓存。"""
        if media_id and payload:
            self.person.set(media_id, payload)

    def is_negative(self, key: str) -> bool:
        """恒 ``False`` —— 负缓存已移除（不保存失败结果）。

        保留签名只为不打断调用点（``service`` 里有几处"命中负缓存就提前返回"的写法）；
        现在这些分支永远不会命中，等于"每次都重新探测一次"。
        """
        return False

    def mark_negative(self, key: str) -> None:
        """空实现 —— 负缓存已移除，失败不再落任何标记。"""
        return None

    # ── 管理用 ───────────────────────────────────────────────────────
    def region(self, name: str) -> Optional[TTLCache]:
        """按 region 名取缓存实例；未知 region 返回 None。"""
        return {
            constants.REGION_DETAIL: self.detail,
            constants.REGION_PERSON: self.person,
            constants.REGION_DOUBAN: self.douban,
            constants.REGION_SEARCH: self.search,
            constants.REGION_RANK: self.rank,
        }.get(name)

    def items(self, name: str, limit: int = 100) -> list[dict]:
        """枚举某 region 的原始键值（管理面板「看原始数据」用）。"""
        cache = self.region(name)
        if cache is None:
            return []
        out: list[dict] = []
        try:
            iterator: Iterable[Any] = cache.items()
        except Exception:  # pragma: no cover - 后端差异
            return []
        for key, value in iterator:
            out.append({"key": key, "value": value})
            if len(out) >= limit:
                break
        return out

    def counts(self) -> dict[str, int]:
        """各 region 的**当前条数**（管理面板「缓存分布」饼图用）。

        走的是契约方法 ``keys()`` —— Redis 后端是 SCAN + 逐条取值，所以是 O(n)。
        只在面板打开 / 点刷新时调一次；本插件 5 个 region 合计在百~千级，可接受。
        读失败的 region 记 0（不让统计问题挡住整个状态接口）。
        """
        out: dict[str, int] = {}
        for name in constants.ALL_REGIONS:
            cache = self.region(name)
            if cache is None:
                out[name] = 0
                continue
            try:
                out[name] = sum(1 for _ in cache.keys())
            except Exception:  # pragma: no cover - 后端差异
                out[name] = 0
        return out

    def delete(self, name: str, key: str) -> bool:
        """删单条缓存。"""
        cache = self.region(name)
        if cache is None or not key:
            return False
        try:
            cache.delete(key)
            return True
        except Exception:  # pragma: no cover - 后端差异
            return False

    def clear_all(self) -> list[str]:
        """清空全部 region，返回成功清理的 region 名。"""
        cleared: list[str] = []
        for name in constants.ALL_REGIONS:
            cache = self.region(name)
            if cache is None:
                continue
            try:
                cache.clear()
                cleared.append(name)
            except Exception:  # pragma: no cover - 后端差异
                continue
        return cleared

    def close(self) -> None:
        """释放缓存客户端（插件停止时调用，可重复）。"""
        for name in constants.ALL_REGIONS:
            cache = self.region(name)
            if cache is None:
                continue
            try:
                cache.close()
            except Exception:  # pragma: no cover - 后端差异
                pass
