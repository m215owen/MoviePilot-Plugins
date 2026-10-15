"""短剧百科数据源 · 插件缓存层（与宿主**同一套缓存机制**，但**不进**宿主的缓存管理）。

为什么要有这一层
----------------
插件原来自带一个 512 条上限的进程内字典（``_cache``），它与宿主有三处口径不一致：

1. **后端**：宿主用 ``app.sdk.cache``（``CACHE_BACKEND_TYPE=redis`` 时是 Redis，否则
   进程内有界内存），插件却只认内存 ⇒ 重启即空、多进程不共享。
2. **有效期**：宿主按系统设置 ``META_CACHE_EXPIRE``（小时，0 = 自动）控制单条元数据
   识别缓存的有效期；插件的 TTL 是自己一个配置项，两套口径。
3. **站点开关**：宿主支持 ``NO_CACHE_SITE_KEY``（域名含关键字就不缓存该站点的资源），
   插件没有对应行为。

本模块把这三件事对齐到宿主，同时**不接入**宿主的缓存管理：

* **不注册** ``tmdb_cache_items`` / ``tmdb_cache_delete`` / ``tmdb_cache_clear`` 这类
  legacy 模块方法（那会把插件条目混进宿主的「识别缓存」列表，还会劫持宿主的删除），
  宿主的缓存管理页里**看不到也动不了**本插件的缓存。
* region 固定 :data:`CACHE_REGION` ⇒ 在宿主那台 Redis 上自成键空间
  （``region:shortdramabaike:key:*``），清空只影响本插件，不会碰宿主与其它插件。
* 条目自己带元数据（写入时间 / 类型 / 展示名），所以插件面板能给出一个**和宿主缓存
  管理页同构**的界面：统计、按类型筛选、删除单条、清空。

跟随哪些系统开关
----------------
===============================================  ===========================================
系统设置（面板「设置 → 缓存 / 站点」）              对插件缓存的作用
===============================================  ===========================================
``CACHE_BACKEND_TYPE`` / ``CACHE_BACKEND_URL``  决定插件缓存落在 Redis 还是进程内内存
``META_CACHE_EXPIRE``（小时，0 = 自动）           决定插件每条缓存的有效期（0 时按宿主口径
                                                取 24 小时，大内存模式 72 小时）
``NO_CACHE_SITE_KEY``（逗号分隔的域名关键字）      命中本站域名时插件**不写也不读**缓存
``GLOBAL_IMAGE_CACHE`` / ``..._DAYS``           插件的海报走宿主图片代理，该开关决定代理
                                                是否使用磁盘缓存（由面板下发到前端）
===============================================  ===========================================

图片不在这层：海报 / 剧照一律经宿主图片代理（``system/img``、``system/cache/image``），
由宿主统一落 ``CACHE_PATH/images`` 并按 ``GLOBAL_IMAGE_CACHE_DAYS`` 回收，插件不另存一份。

文档依据
--------
* 上游 ``docs/faq/15-use-system-cache.md``（「如何在插件中使用系统级统一缓存」）：
  插件用 ``TTLCache(region=…, maxsize=…, ttl=…)`` / ``@cached(region=…)`` 即可，
  **后端由系统自动选择**（``CACHE_BACKEND_TYPE``），插件代码不必区分；
  最佳实践要求①每插件独立 region ②合理 TTL ③**卸载时清理缓存避免内存泄漏**。
  ⚠️ 该 FAQ 写于 v2.7.4 时代，给的是 ``from app.core.cache import …`` —— v3 里
  ``app.core.*`` 只是兼容别名，规范路径见 ADR-0008（``app/sdk/plugin`` 的同一决策）：
  **新插件从 ``app.sdk.*`` 取**，所以这里导入 ``app.sdk.cache``。
* 上游 ``docs/faq/03-expose-plugin-api.md``：插件接口在 ``get_api()`` 里声明，
  缓存管理那三条（``GET/DELETE /cache``）就按它注册。
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Tuple

from app.sdk.logging import logger

from .constants import PLUGIN_NAME

try:  # 规范入口（v3）：ADR-0008 定「新插件从 app.sdk.* 取」
    from app.sdk.cache import TTLCache as _SdkTTLCache
except Exception:  # pragma: no cover - 宿主版本差异兜底
    _SdkTTLCache = None

try:  # FAQ 15 里的老路径（v2.7.4+，v3 由 runtime/compat 提供别名）
    from app.core.cache import TTLCache as _LegacyTTLCache
except Exception:  # pragma: no cover - v3 且 SDK 可用时用不到
    _LegacyTTLCache = None

if _SdkTTLCache is None and _LegacyTTLCache is not None:  # pragma: no cover
    _SdkTTLCache = _LegacyTTLCache

try:  # 运行时设置（读系统缓存开关；与读 RECOGNIZE_SOURCE 同一个入口）
    from app.runtime.settings import get_runtime_setting as _get_runtime_setting
except Exception:  # pragma: no cover - 宿主版本差异兜底
    _get_runtime_setting = None

__all__ = [
    "CACHE_REGION",
    "CACHE_KINDS",
    "KIND_LABELS",
    "CacheEntry",
    "PluginCache",
    "SystemCacheSettings",
    "system_cache_settings",
]

# 缓存区名：独立于宿主与其它插件的键空间（Redis 键前缀 ``region:shortdramabaike:key:``）。
CACHE_REGION = "shortdramabaike"
# 条目类型（面板上的「类型」筛选按它分类，与宿主识别缓存的「识别来源」同位置）
CACHE_KINDS: Tuple[str, ...] = ("detail", "actor", "tmdb")
KIND_LABELS: Dict[str, str] = {
    "detail": "作品详情",
    "actor": "演员档案",
    "tmdb": "TMDB 身份",
}
# 内存后端（未启用 Redis）时的条目上限 —— 与宿主 ``settings.CONF`` 的同类量级一致
MEMORY_MAXSIZE = 512
# 系统 ``META_CACHE_EXPIRE`` 为 0（自动）时宿主的取值口径，见 ``runtime/config.py::CONF``
AUTO_TTL_NORMAL = 24 * 3600
AUTO_TTL_BIG_MEMORY = 72 * 3600
# 条目包装标记：让「是不是本插件写的」一眼可辨（宿主的键空间里同时躺着别人的数据）
ENTRY_MARK = "sdbs"

# 占位：真实值由 system_cache_settings() 每次现读（宿主改设置不必重启插件）
_DEFAULT_AUTO_TTL = AUTO_TTL_NORMAL


def _runtime_setting(name: str, default: Any = None) -> Any:
    """读一项宿主运行时设置；取不到（老宿主 / 单测环境）返回默认值。"""
    if _get_runtime_setting is None:
        return default
    try:
        value = _get_runtime_setting(name, default)
    except Exception:  # pragma: no cover - 宿主版本差异兜底
        return default
    return default if value is None else value


@dataclass(frozen=True)
class SystemCacheSettings:
    """宿主「缓存」相关开关的快照（面板上原样展示，便于解释插件缓存的现状）。"""

    backend: str = ""
    meta_expire_hours: int = 0
    auto_ttl: int = _DEFAULT_AUTO_TTL
    image_cache: bool = False
    image_cache_days: int = 7
    no_cache_site_key: str = ""

    @property
    def is_redis(self) -> bool:
        """宿主是否把缓存放在了 Redis（决定插件缓存能不能跨重启存活）。"""
        return self.backend.strip().lower() == "redis"

    def blocks_domain(self, domain: str) -> bool:
        """站点域名是否命中 ``NO_CACHE_SITE_KEY``。

        判据与宿主 ``TorrentsChain._is_no_cache_site`` 完全一致：关键字**子串命中**
        即视为不缓存（宿主那边比的是站点域名，这里比的是插件站点域名）。
        """
        host = (domain or "").strip().lower()
        if not host:
            return False
        keys = (key.strip().lower() for key in self.no_cache_site_key.split(","))
        return any(key and key in host for key in keys)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "backend": self.backend,
            "meta_expire_hours": self.meta_expire_hours,
            "auto_ttl": self.auto_ttl,
            "image_cache": self.image_cache,
            "image_cache_days": self.image_cache_days,
            "no_cache_site_key": self.no_cache_site_key,
        }


def system_cache_settings() -> SystemCacheSettings:
    """现读宿主的缓存相关开关（任何一项读不到都退回宿主默认值）。"""

    def _int(name: str, default: int) -> int:
        try:
            return int(_runtime_setting(name, default) or default)
        except (TypeError, ValueError):
            return default

    hours = max(_int("META_CACHE_EXPIRE", 0), 0)
    auto_ttl = AUTO_TTL_BIG_MEMORY if bool(_runtime_setting("BIG_MEMORY_MODE", False)) else AUTO_TTL_NORMAL
    return SystemCacheSettings(
        backend=str(_runtime_setting("CACHE_BACKEND_TYPE", "") or ""),
        meta_expire_hours=hours,
        auto_ttl=auto_ttl,
        image_cache=bool(_runtime_setting("GLOBAL_IMAGE_CACHE", False)),
        image_cache_days=max(_int("GLOBAL_IMAGE_CACHE_DAYS", 7), 1),
        no_cache_site_key=str(_runtime_setting("NO_CACHE_SITE_KEY", "") or ""),
    )


@dataclass(frozen=True)
class CacheEntry:
    """一条缓存记录的**元数据视图**（不含 payload，供列表展示）。"""

    key: str
    kind: str
    label: str
    ref: str
    cached_at: float

    @property
    def kind_label(self) -> str:
        return KIND_LABELS.get(self.kind, self.kind or "其它")

    def as_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "kind": self.kind,
            "kind_label": self.kind_label,
            "label": self.label,
            "ref": self.ref,
            "cached_at": self.cached_at,
        }


def kind_of(key: str) -> str:
    """按键前缀判类型（键形如 ``detail:60017`` / ``actor:371`` / ``tmdb|片名|年份``）。"""
    head = str(key or "").split(":", 1)[0].split("|", 1)[0]
    return head if head in CACHE_KINDS else "other"


class PluginCache:
    """插件缓存门面。

    * 后端与有效期**跟着宿主走**（见模块 docstring 的对照表）；
    * 宿主未提供 ``app.sdk.cache``（老版本 / 本地单测）时**降级**成进程内实现，
      行为与插件旧版一致（512 条上限 + 惰性过期），功能不缺失；
    * 只暴露「本插件用得上」的几个动作：读、写、删、清空、列举 —— 管理界面就架在
      后两个之上。
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sdk = _SdkTTLCache is not None
        self._backend: Any = None
        self._local: Dict[str, Tuple[float, Any]] = {}
        self._signature: Optional[Tuple[Any, ...]] = None
        self._override_ttl = 0
        self._domain = ""
        self._ttl = _DEFAULT_AUTO_TTL
        self._ttl_source = "system"
        self._system = system_cache_settings()
        self._degraded_warned = False
        self.refresh()

    # ── 配置与系统开关 ────────────────────────────────────────────

    def configure(self, override_ttl: int = 0, domain: str = "") -> None:
        """按插件配置重建。

        ``override_ttl`` 三种取值：

        * ``0``（默认）= **跟随系统**（系统设置「单条元数据识别缓存有效期」）；
        * ``> 0`` = 显式覆盖，单位秒；
        * ``< 0`` = **关闭插件缓存**（排障 / 站点改版期用；系统本身没有「关掉识别缓存」
          的开关，所以这一档留在插件侧，面板上写清楚）。
        """
        with self._lock:
            self._override_ttl = int(override_ttl or 0)
            self._domain = domain or ""
        self.refresh()

    def refresh(self) -> None:
        """重读系统开关。宿主改了 ``META_CACHE_EXPIRE`` / 换了后端都靠这里跟上。"""
        system = system_cache_settings()
        with self._lock:
            self._system = system
            self._ttl, self._ttl_source = self._resolve_ttl(system)
            self._reload_backend()

    def _resolve_ttl(self, system: SystemCacheSettings) -> Tuple[int, str]:
        """有效期：插件显式覆盖 / 关闭 > 系统显式值 > 系统自动口径。"""
        if self._override_ttl > 0:
            return self._override_ttl, "plugin"
        if self._override_ttl < 0:
            return 0, "off"
        if system.meta_expire_hours > 0:
            return system.meta_expire_hours * 3600, "system"
        return system.auto_ttl, "system-auto"

    def _reload_backend(self) -> None:
        """TTL 或后端类型变化时重建后端实例（TTL 是构造参数）。"""
        signature = ("sdk" if self._sdk else "local", self._ttl)
        if self._backend is not None and self._signature == signature:
            return
        if self._sdk:
            try:
                self._backend = _SdkTTLCache(
                    region=CACHE_REGION, maxsize=MEMORY_MAXSIZE, ttl=self._ttl
                )
                self._signature = signature
                self._local.clear()
                return
            except Exception as err:  # pragma: no cover - Redis 未就绪等
                if not self._degraded_warned:
                    self._degraded_warned = True
                    logger.warning(
                        f"{PLUGIN_NAME} 宿主缓存后端暂不可用（{type(err).__name__}: {err}），"
                        f"本次退回进程内缓存；下一轮自动重试"
                    )
        self._backend = None
        self._signature = None

    # ── 现状 ──────────────────────────────────────────────────────

    @property
    def ttl(self) -> int:
        return self._ttl

    @property
    def ttl_source(self) -> str:
        return self._ttl_source

    @property
    def system(self) -> SystemCacheSettings:
        return self._system

    @property
    def backend_name(self) -> str:
        """实际落点：``redis`` / ``cachetools``（宿主内存后端）/ ``local``（降级）。"""
        if not self._sdk or self._backend is None:
            return "local"
        return "redis" if self._system.is_redis else "cachetools"

    @property
    def enabled(self) -> bool:
        """缓存是否生效。

        关闭的两条路径：插件配置 ``cache_ttl < 0``（``_ttl`` 被解析成 0），
        以及站点命中系统的 ``NO_CACHE_SITE_KEY``（与宿主 ``_is_no_cache_site`` 同判据）。
        """
        return self._ttl > 0 and not self._system.blocks_domain(self._domain)

    def describe(self) -> Dict[str, Any]:
        """面板展示用：有效期从哪来、后端是什么、系统开关各是什么。"""
        return {
            "region": CACHE_REGION,
            "enabled": self.enabled,
            "ttl": self._ttl,
            "ttl_source": self._ttl_source,
            "override_ttl": self._override_ttl,
            "disabled": self._override_ttl < 0,
            "backend": self.backend_name,
            "sdk": self._sdk,
            "domain": self._domain,
            "system": self._system.as_dict(),
            "blocked": self._system.blocks_domain(self._domain),
        }

    # ── 读写 ──────────────────────────────────────────────────────

    def lookup(self, key: str) -> Optional[Tuple[CacheEntry, Any]]:
        """取一条缓存：``(元数据, payload)``；没命中返回 ``None``。

        ⚠️ 与 :meth:`get` 的区别在「命中但值是空」：TMDB 身份补充会把「查过、没有」
        也缓存下来（负结果），那种情况 :meth:`get` 返回 ``None`` 分不清「没缓存」，
        所以需要区分时要看本方法的返回值是否为 ``None``。
        """
        entry = self._read(key)
        if entry is None:
            return None
        meta = CacheEntry(
            key=str(key),
            kind=str(entry.get("kind") or kind_of(key)),
            label=str(entry.get("label") or ""),
            ref=str(entry.get("ref") or ""),
            cached_at=float(entry.get("at") or 0.0),
        )
        return meta, entry.get("data")

    def get(self, key: str) -> Any:
        """取一条缓存的 payload；没有就返回 ``None``。"""
        found = self.lookup(key)
        return None if found is None else found[1]

    def set(
        self,
        key: str,
        data: Any,
        *,
        kind: str = "",
        label: str = "",
        ref: str = "",
    ) -> None:
        """写一条缓存（含面板要用的元数据）。缓存关闭时**什么都不做**。"""
        if not self.enabled:
            return
        key = str(key or "")
        if not key:
            return
        wrapped = {
            "mark": ENTRY_MARK,
            "at": time.time(),
            "kind": kind or kind_of(key),
            "label": str(label or ""),
            "ref": str(ref or ""),
            "data": data,
        }
        self._write(key, wrapped)

    def delete(self, key: str) -> bool:
        """删一条。返回是否真的删掉了（管理界面据此回「不存在」）。"""
        key = str(key or "")
        if not key:
            return False
        existed = self._read(key) is not None
        try:
            if self._backend is not None:
                self._backend.delete(key)
            with self._lock:
                self._local.pop(key, None)
        except Exception as err:  # pragma: no cover - 后端异常不该打断面板
            logger.warning(f"{PLUGIN_NAME} 删除缓存「{key}」失败：{type(err).__name__}: {err}")
            return False
        return existed

    def clear(self, kind: str = "") -> int:
        """清空（可按类型）。返回删掉的条数 —— 条目自己的 ``kind`` 说了算。"""
        removed = 0
        for entry in self.entries():
            if kind and entry.kind != kind:
                continue
            if self.delete(entry.key):
                removed += 1
        if not kind:
            # 整区清空再兜一次底：漏进来的「不是本插件写的」条目一并收走
            try:
                if self._backend is not None:
                    self._backend.clear()
            except Exception as err:  # pragma: no cover
                logger.warning(f"{PLUGIN_NAME} 清空缓存区失败：{type(err).__name__}: {err}")
            with self._lock:
                self._local.clear()
        return removed

    # ── 列举与统计 ────────────────────────────────────────────────

    def entries(self, kind: str = "", keyword: str = "") -> List[CacheEntry]:
        """列出缓存条目（按写入时间倒序），供面板的缓存管理界面使用。"""
        keyword = (keyword or "").strip().lower()
        rows: List[CacheEntry] = []
        for key, value in self._iter_raw():
            if not isinstance(value, dict) or value.get("mark") != ENTRY_MARK:
                continue
            item_kind = str(value.get("kind") or kind_of(key))
            if kind and item_kind != kind:
                continue
            label = str(value.get("label") or "")
            ref = str(value.get("ref") or "")
            if keyword and keyword not in f"{label} {ref} {key}".lower():
                continue
            rows.append(
                CacheEntry(
                    key=key,
                    kind=item_kind,
                    label=label,
                    ref=ref,
                    cached_at=float(value.get("at") or 0.0),
                )
            )
        rows.sort(key=lambda item: item.cached_at, reverse=True)
        return rows

    def stats(self) -> Dict[str, Any]:
        """各类型条数（面板顶部的统计条）。"""
        by_kind: Dict[str, int] = {name: 0 for name in CACHE_KINDS}
        total = 0
        for entry in self.entries():
            total += 1
            by_kind[entry.kind] = by_kind.get(entry.kind, 0) + 1
        return {"count": total, "kinds": by_kind}

    def release(self) -> bool:
        """卸载插件时释放缓存。返回「是否清空了」——**落 Redis 时不清**。

        FAQ 15 的最佳实践是「在插件卸载时清理相关缓存，避免内存泄漏」：那条针对的是
        进程内后端。落在宿主 Redis 上时缓存是跨重启的持久数据（与宿主的识别缓存同性质），
        卸载时清掉只会让下次重新抓一遍页面（站点有风控）—— 所以只释放内存，不清 Redis；
        真要清由面板的「清空缓存」显式触发。

        ⚠️ 清完**不拆后端实例**：拆掉会让后续读写落到降级的内存实现上，直到下一次
        :meth:`refresh` 才恢复 —— 卸载后插件仍可能被识别链调用，不该有这段空窗。
        """
        if self.backend_name == "redis":
            return False
        with self._lock:
            self._local.clear()
        if self._backend is not None:
            try:
                self._backend.clear()
            except Exception as err:  # pragma: no cover - 后端差异
                logger.debug(f"{PLUGIN_NAME} 释放进程内缓存失败：{type(err).__name__}: {err}")
        return True

    # ── 内部：与后端打交道 ────────────────────────────────────────

    def _read(self, key: str) -> Optional[Dict[str, Any]]:
        value: Any = None
        try:
            if self._backend is not None:
                value = self._backend.get(key)
            else:
                value = self._read_local(key)
        except Exception as err:  # pragma: no cover - 后端异常按「没缓存」处理
            logger.debug(f"{PLUGIN_NAME} 读缓存「{key}」失败：{type(err).__name__}: {err}")
            return None
        return value if isinstance(value, dict) and value.get("mark") == ENTRY_MARK else None

    def _write(self, key: str, value: Dict[str, Any]) -> None:
        try:
            if self._backend is not None:
                self._backend.set(key, value)
                return
        except Exception as err:  # pragma: no cover - 后端异常不该打断识别
            logger.debug(f"{PLUGIN_NAME} 写缓存「{key}」失败：{type(err).__name__}: {err}")
            return
        self._write_local(key, value)

    def _iter_raw(self) -> Iterator[Tuple[str, Any]]:
        """遍历本 region 的全部原始条目（宿主 Redis 只扫自己的键前缀）。"""
        if self._backend is not None:
            try:
                for key, value in list(self._backend.items()):
                    yield str(key), value
                return
            except Exception as err:  # pragma: no cover
                logger.warning(f"{PLUGIN_NAME} 列举缓存失败：{type(err).__name__}: {err}")
                return
        now = time.time()
        with self._lock:
            snapshot = list(self._local.items())
        for key, (expires, value) in snapshot:
            if expires and now > expires:
                with self._lock:
                    self._local.pop(key, None)
                continue
            yield key, value

    # 降级实现（宿主没有 app.sdk.cache 时）：与插件旧版内存缓存行为一致
    def _read_local(self, key: str) -> Any:
        now = time.time()
        with self._lock:
            entry = self._local.get(key)
            if not entry:
                return None
            expires, value = entry
            if expires and now > expires:
                self._local.pop(key, None)
                return None
        return value

    def _write_local(self, key: str, value: Dict[str, Any]) -> None:
        with self._lock:
            self._local[key] = (time.time() + self._ttl, value)
            if len(self._local) > MEMORY_MAXSIZE:
                oldest = sorted(self._local.items(), key=lambda pair: pair[1][0])
                for stale_key, _ in oldest[: MEMORY_MAXSIZE // 4]:
                    self._local.pop(stale_key, None)
