"""把本站图片主机登记进宿主的「安全图片域名」白名单（`SECURITY_IMAGE_DOMAINS`）。

## 为什么必须做

宿主的图片代理（``/api/v1/system/img/0?imgurl=…``）、海报下载与前端 ``<img>`` 的安全策略
都按这份白名单放行；域名不在名单里，海报就是空白/裂图 —— 而短剧的来源图**全部**来自
这两个域，等于整个插件没封面。

## 登记哪些域

* ``img.duanjubaike.net`` —— 站点图床（``img.duanjubaike.net/{entity}/{id}.jpg``，
  ``media_id`` 就能反推地址）。写**具体主机**、不写父域 ``duanjubaike.net``：父域会顺带
  放行 ``www`` 这类网页地址，超出「让海报能显示」这个目的。
* ``doubanio.com`` —— 豆瓣图床**父域**：``douban:{sid}`` 条目的封面与 ``doubanp:`` 头像
  都在这里，而图床主机名随条目变（``img1/img2/img3/img9``、``qnmob3-sign`` …），
  穷举必漏；它本身只是图床域，不存在「顺带放出网页」的问题。

## 纪律

* **只在启用时登记、停用时撤回自己那两个域**，不碰用户或其它插件加的条目
  （``update_setting`` 是整份覆盖，所以必须「读 → 合并/剔除 → 写」）；
* 任何失败都只记 warning：白名单是「更好看」，不该让检索与识别一起失败；
* 用锁串行化读改写：``init_plugin`` 与 ``stop_service`` 可能交错。
"""

from __future__ import annotations

import threading
from typing import Any, Iterable, Optional

from app.sdk.logging import logger

__all__ = ["IMAGE_DOMAINS", "KEY", "active", "ensure", "revoke", "sync"]

try:  # 宿主正式门面；没有就整体降级为 no-op（老宿主不该因此拖垮插件）
    from app.sdk.config import settings as _host_settings
except Exception:  # noqa: BLE001
    _host_settings = None  # type: ignore[assignment]

#: 宿主配置里这项的名字
KEY = "SECURITY_IMAGE_DOMAINS"

#: 需要登记的图片主机（见模块 docstring 的取舍理由）
IMAGE_DOMAINS = (
    "img.duanjubaike.net",
    "doubanio.com",
)

#: 串行化读改写，避免 init 与 stop 交错时把对方的改动覆盖掉
_lock = threading.Lock()


def _current() -> Optional[list[str]]:
    """当前白名单；宿主没提供设置对象时返回 ``None``（调用方据此跳过）。"""
    if _host_settings is None:
        return None
    value = getattr(_host_settings, KEY, None)
    return [str(item) for item in value] if isinstance(value, list) else None


def _write(domains: list[str]) -> tuple[bool, str]:
    if _host_settings is None:
        return False, "宿主未提供设置对象"
    try:
        result, message = _host_settings.update_setting(KEY, domains)
    except Exception as err:  # noqa: BLE001 - 写配置失败不该影响插件主功能
        return False, str(err)
    return result is not False, str(message or "")


def ensure(domains: Iterable[str] = IMAGE_DOMAINS) -> list[str]:
    """补齐缺失的域名，返回本次**新增**的条目。"""
    wanted = [str(domain) for domain in domains if domain]
    with _lock:
        current = _current()
        if current is None:
            return []
        missing = [domain for domain in wanted if domain not in current]
        if not missing:
            return []
        ok, message = _write(current + missing)
        if not ok:
            logger.warning(f"{KEY} 登记失败：{message or '未知原因'}")
            return []
        return missing


def revoke(domains: Iterable[str] = IMAGE_DOMAINS) -> list[str]:
    """只撤回本插件登记的那几个域，返回实际移除的条目。"""
    wanted = {str(domain) for domain in domains if domain}
    with _lock:
        current = _current()
        if current is None:
            return []
        dropped = [domain for domain in current if domain in wanted]
        if not dropped:
            return []
        ok, message = _write([domain for domain in current if domain not in wanted])
        if not ok:
            logger.warning(f"{KEY} 撤回失败：{message or '未知原因'}")
            return []
        return dropped


def active(domains: Iterable[str] = IMAGE_DOMAINS) -> list[str]:
    """当前仍在本插件清单里、且宿主已放行的域名。"""
    current = _current()
    if current is None:
        return []
    return [domain for domain in domains if domain in current]


def sync(enabled: bool) -> dict[str, Any]:
    """按启用状态登记 / 撤回；任何异常都吞掉（只记 warning）。"""
    result: dict[str, Any] = {"added": [], "removed": []}
    try:
        if enabled:
            result["added"] = ensure()
        else:
            result["removed"] = revoke()
    except Exception as err:  # noqa: BLE001 - 白名单失败不该影响插件主功能
        logger.warning(f"{KEY} 同步失败（不影响检索与识别）：{err}")
        return result

    if result["added"]:
        logger.info(f"{KEY} 已登记：{', '.join(result['added'])}")
    if result["removed"]:
        logger.info(f"{KEY} 已撤回：{', '.join(result['removed'])}")
    result["active"] = active()
    return result
