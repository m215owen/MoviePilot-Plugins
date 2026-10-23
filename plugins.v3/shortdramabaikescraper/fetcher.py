"""页面抓取：统一 UA、超时、轻量重试与站点软 404 判定。

站点的软 404 特征（2026-10-21 实测，错前缀与不存在的 id 表现一致）：

* HTTP 仍返回 **200**；
* 响应体约 **40172 字节**；
* 既没有 ``<title>`` 也没有 ``<h1>``。

所以「取没取到页面」不能只看状态码，必须同时判软 404，否则会反复打同一个坏 id。
但**字节数不能当判据**——无结果搜索页约 40.2 KB，与空壳页区间重叠（见 ``is_soft_404``）。
"""

from __future__ import annotations

import asyncio
from typing import Optional

from app.sdk.logging import logger
from app.sdk.network import AsyncRequestUtils

from . import constants

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# 软 404 的响应体长度（实测恒定，容差 ±64 字节防站点微调空白）
SOFT_404_SIZE = 40172
_SOFT_404_TOLERANCE = 64


def is_soft_404(html: str) -> bool:
    """判断是否命中了站点的「空壳页」。

    判据以**页面结构**为准：空壳页既没有 ``<title>`` 也没有 ``<h1>``。

    ⚠️ **不能按字节数判断**：无结果的搜索页实测约 40.2 KB，与空壳页的 40172 字节
    区间重叠，按大小判会把正常页面误杀（实测搜索「情靡」被误判成软 404，日志误导）。
    字节数只保留作常量参考，不再参与判定。

    ``<h1>`` 用全文匹配：搜索页的 ``<h1>`` 出现在 38 KB 处，只看头部会漏。
    """
    if not html:
        return True
    if "<h1" in html:
        return False
    # ``<title>`` 必在文档前部，只对头部做小写化，省掉整页拷贝
    return "<title" not in html[:12000].lower()


class Fetcher:
    """带重试的页面抓取器；每次请求新建客户端，用完即弃，避免长连接泄漏。"""

    def __init__(self, *, timeout: int = 20, attempts: int = 2) -> None:
        self._timeout = timeout
        self._attempts = max(1, attempts)

    async def get_html(self, url: str) -> Optional[str]:
        """取页面文本；软 404、网络失败、非 200 一律返回 ``None``。"""
        if not url:
            return None
        last_error = ""
        for attempt in range(self._attempts):
            try:
                client = AsyncRequestUtils(ua=UA, timeout=self._timeout)
                response = await client.get_res(url)
            except Exception as err:  # pragma: no cover - 网络异常统一降级
                last_error = str(err)
                response = None
            if response is not None:
                status = getattr(response, "status_code", 0)
                if status == 200:
                    html = getattr(response, "text", "") or ""
                    if is_soft_404(html):
                        logger.debug(f"{constants.SOURCE_NAME} 软 404：{url}")
                        return None
                    return html
                last_error = f"HTTP {status}"
                if status in (403, 404, 410):
                    # 不该重试的状态
                    logger.warning(f"{constants.SOURCE_NAME} 抓取被拒 {url}：HTTP {status}")
                    return None
            if attempt + 1 < self._attempts:
                await asyncio.sleep(0.6 * (attempt + 1))
        logger.warning(f"{constants.SOURCE_NAME} 抓取失败 {url}：{last_error or 'unknown'}")
        return None

    async def close(self) -> None:
        """预留的释放钩子（当前每次请求自建客户端，无需释放）。"""
        return None
