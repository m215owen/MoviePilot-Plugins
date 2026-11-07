"""``.org`` 解析器要的身份工具（从 :mod:`media_id` 转发 + 页面 URL 支持）。

:mod:`orgsite` 是自 ``shortdramanetsource`` 整体搬来的，内部一律通过
``identity.media_id / native_id_of / page_identity`` 取身份。本插件的身份
实现是 :mod:`media_id`（多一层 ``duanju:`` 之类的前缀语义），函数名不同，
所以这里做一层薄薄的转接，**不复制任何解析逻辑**：

* ``media_id(kind, native)`` → :func:`media_id.media_id_of`
* ``native_id_of(value)`` → 既吃 ``drama:13502`` 也吃详情页 URL
* ``page_identity(value)`` → ``(kind, native)``，URL 形态按 ``.org`` 的
  ``/<lang>/drama/<id>``、``/<lang>/actor/<id>`` 认

页面 URL 识别是这里**唯一的**新增逻辑：``.org`` 的详情地址不带 ``info-``，
不能复用 :func:`media_id.scan_ids` 那套 ``.net`` 规则。
"""

from __future__ import annotations

import re
from typing import Tuple

from .media_id import media_id_of, native_id_of as _native_of_media_id, parse_media_id

#: ``.org`` 详情 / 人物页：``/zh-Hans/drama/13502``、``/zh-Hans/actor/8812``
#: （语言段可有可无，站点目前只有 ``zh-Hans`` 一个）
_ORG_PAGE_RE = re.compile(
    r"/(?:[A-Za-z-]+/)?(?P<kind>drama|actor)/(?P<native>\d{1,20})"
)


def media_id(kind: str, native_id: object) -> str:
    """``("drama", "13502")`` → ``drama:13502``（空入参返回空串）。"""
    return media_id_of(kind, native_id)


def native_id_of(value: object) -> str:
    """从 media_id / 详情页 URL / 裸 id 里取站点原生 id。"""
    text = str(value or "").strip()
    if not text:
        return ""
    # URL 必须先认：``https://`` 里的冒号会被 ``{kind}:{native}`` 的切法误当分隔符
    if "://" in text:
        match = _ORG_PAGE_RE.search(text)
        return match.group("native") if match else ""
    if ":" in text:
        return _native_of_media_id(text)
    return text if _looks_like_native(text) else ""


def page_identity(value: object) -> Tuple[str, str]:
    """``media_id`` / 详情页 URL → ``(kind, native)``；认不出时 kind 为空串。"""
    text = str(value or "").strip()
    if not text:
        return "", ""
    if "://" in text:
        match = _ORG_PAGE_RE.search(text)
        if match:
            return match.group("kind").lower(), match.group("native")
        return "", ""
    parsed = parse_media_id(text)
    if parsed[0]:
        return parsed[0].lower(), parsed[1]
    return "", native_id_of(text)


def _looks_like_native(text: str) -> bool:
    """裸串能否当站点 id：``.org`` 侧恒为十进制数字（``13502``）。"""
    return bool(text) and text.isdigit() and len(text) <= 20


__all__ = ["media_id", "native_id_of", "page_identity"]
