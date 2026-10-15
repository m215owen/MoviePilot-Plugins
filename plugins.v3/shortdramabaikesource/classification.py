"""短剧百科数据源 · 宿主「媒体分类扩展协议」适配层。

为什么要有这一层：宿主的媒体库目录匹配是**按分类**挑目录的
（``application/directory.py`` 的 ``media_match_rank``：目录固定了分类时，媒体的分类
ID 不一致就直接判不匹配）⇒ 分类没命中 = 「未找到有效的媒体库目录」= 整理失败。
而宿主的分类规则**不能用来源身份当条件** —— 标准字段（``identity.media_source`` /
``media.*``）的能力表只登记了内置来源，插件来源一律 ``unavailable``，实测发布规则
会被拒：

    ``字段 identity.media_source 在所选来源中均不可用：duanju``

宿主留给插件的唯一口子就是 ``extensions.<来源>.<字段>`` 命名空间，所以插件必须自己
声明字段、自己给出事实。本模块把这件事收在一处，对齐官方文档
``docs/faq/19-register-media-source.md`` 第 4 节（声明来源分类字段）与
``docs/faq/20-media-classification.md`` 第 2 节，其中两条是硬要求：

1. **协议探测 + 降级**：先看 ``app.sdk.classification`` 的
   ``MEDIA_SOURCE_CLASSIFICATION_PROTOCOL_VERSION`` 够不够；模块导不进来、版本不够、
   声明构造失败，**一律降级成不带扩展字段的普通来源声明**，绝不把异常抛给宿主 ——
   声明失败不能连带把「来源注册」本身一起丢掉（旧宿主上识别、搜索还得照跑）。
2. **命名空间与类型匹配**：字段 ID 必须落在 ``extensions.<来源>.`` 里；值类型、
   操作符、媒体类型三者必须互相匹配（宿主按
   ``domain/classification/fields.VALUE_TYPE_OPERATORS`` 校验），否则**整份**声明被拒。

官方可选能力中**刻意未实现**的两项（都不影响来源注册与分类）：
* ``get_media_auxiliary_info``（给已有电影 / 电视剧补别名）—— 本插件是被动识别的
  短剧源，别名没有权威来源，宁缺勿造；且宿主会把返回的别名并进搜索关键词，泛词会
  捞回无关资源。
* ``get_media_classification_facts``（协议 v2 的「补充缺失标准事实」）—— 要先按精确
  外部 ID 证明是同一媒体，而本站作品在 TMDB 上的命中率极低（抽 14 部只 1 部有），
  为它单开一条出网路径不划算；主身份是 (``duanju``, 站点数字 ID)，借不出外部 ID。
"""
from __future__ import annotations

import importlib
from typing import Any, Dict, List, Optional

from app.schemas.types import MediaType
from app.sdk.logging import logger

from .constants import (
    CLASSIFICATION_FIELDS,
    CLASSIFICATION_FIELD_PREFIX,
    MEDIA_SOURCE_KEY,
    MEDIA_SOURCE_LABEL,
    PLUGIN_NAME,
)
from .parser import _clean

# 本插件按宿主协议**第 1 版**声明来源扩展分类字段（来源声明 + classification_facts）。
# v2 的 ``get_media_classification_facts`` 补充分支未实现，理由见模块头。
CLASSIFICATION_PROTOCOL_VERSION = 1

_SDK_MODULE = "app.sdk.classification"
_REQUIRED_SDK_ATTRS = ("ClassificationFieldDefinition", "MediaSourceInfo")


# ── 协议探测 ──────────────────────────────────────────────────────


def _load_sdk_module() -> Optional[Any]:
    """导入宿主公开的分类协议入口；旧宿主没有这个模块时返回 ``None``。"""
    try:
        return importlib.import_module(_SDK_MODULE)
    except ImportError:  # pragma: no cover - 只有旧宿主会走到
        return None


def classification_protocol_version() -> int:
    """返回宿主公开的分类扩展协议版本；旧宿主 / 脏值一律按 ``0``（不支持）处理。

    单独暴露出来是给启动日志用的 —— 真机排障时「宿主到底支不支持扩展字段」比
    「声明长什么样」更值得先看一眼。
    """
    sdk = _load_sdk_module()
    try:
        return int(
            getattr(sdk, "MEDIA_SOURCE_CLASSIFICATION_PROTOCOL_VERSION", 0) or 0
        )
    except (AttributeError, TypeError, ValueError):
        return 0


def _classification_sdk() -> Optional[Any]:
    """按官方文档探测协议可用性：版本达标，且两个声明类型都在。"""
    if classification_protocol_version() < CLASSIFICATION_PROTOCOL_VERSION:
        return None
    sdk = _load_sdk_module()
    if sdk is None:  # pragma: no cover - 版本读到了却导不进来
        return None
    if not all(hasattr(sdk, name) for name in _REQUIRED_SDK_ATTRS):
        return None
    return sdk


# ── 来源声明 ──────────────────────────────────────────────────────


def _base_declaration() -> Dict[str, Any]:
    """不依赖 SDK 的最小来源声明（旧宿主 / 降级通道）。

    不带 ``classification_fields``：旧宿主的 ``MediaSourceInfo`` 认识这个键（有默认值），
    但把它删掉更干净 —— 降级的意义就是「只说对方听得懂的」。
    """
    return {
        "name": MEDIA_SOURCE_LABEL,
        "media_source": MEDIA_SOURCE_KEY,
        "media_types": [MediaType.TV],
    }


def media_source_declaration() -> List[Dict[str, Any]]:
    """返回交给宿主的来源声明（短剧在 MoviePilot 里统一按电视剧处理）。

    优先用 SDK 类型构造：字段拼错、值类型与操作符不匹配这类错误会在**构造期**当场
    暴露，而不是等宿主校验时整份拒绝；构造失败只降级、不抛出（见模块头第 1 条）。
    """
    sdk = _classification_sdk()
    if sdk is not None:
        try:
            return [
                sdk.MediaSourceInfo(
                    name=MEDIA_SOURCE_LABEL,
                    media_source=MEDIA_SOURCE_KEY,
                    media_types=[MediaType.TV],
                    classification_fields=[
                        sdk.ClassificationFieldDefinition(**dict(spec))
                        for spec in CLASSIFICATION_FIELDS
                    ],
                ).model_dump(mode="json")
            ]
        except Exception as err:  # noqa: BLE001 - 可选能力绝不允许阻断插件加载
            logger.warning(
                f"{PLUGIN_NAME} 分类字段声明构造失败（宿主协议 "
                f"v{classification_protocol_version()}），本次降级为不含扩展字段的来源声明：{err}"
            )
    return [_base_declaration()]


# ── 分类事实 ──────────────────────────────────────────────────────


def build_classification_facts(item: Dict[str, Any]) -> Dict[str, Any]:
    """给宿主分类策略的扩展事实（键必须带 ``extensions.<来源>.`` 前缀）。

    宿主只接受**声明过**的字段：没登记的事实会被记为「忽略插件分类事实」并刷警告，
    所以这里拿 :data:`constants.CLASSIFICATION_FIELDS` 当白名单。

    * ``is_short_drama``：恒为 ``True``。本站只收录短剧，规则拿它做「是本源识别出来的
      就归短剧」的兜底条件 —— 宿主不允许用 ``identity.media_source`` 当条件（插件来源
      上该字段被判「不可用」），这是唯一能稳定表达「来源=短剧百科」的事实。
    * ``kind`` / ``tags``：站点真实字段（角标形态 / 题材标签），页面没给就不带，
      便于以后按真人 / AI 或题材再细分目录。**不伪造**：缺就是缺。

    事实提取**不新增网络请求**（文档硬要求）：只投影本次解析已经拿到的字段。
    """
    declared = {str(field.get("id")) for field in CLASSIFICATION_FIELDS}
    # 站点标签理论上都是字符串，但**类型不符的事实会被宿主整条丢弃**（只留一条警告），
    # 所以这里顺手归一成去空白的字符串列表，别把脏值送出网。空值（``None`` / ``""``）
    # 直接丢，别让它变成 ``"None"`` 这种假值。
    tags: List[str] = []
    for tag in item.get("tags") or []:
        if not tag:
            continue
        text = str(tag).strip()
        if text:
            tags.append(text)
    facts: Dict[str, Any] = {}
    for key, value in (
        ("is_short_drama", True),
        ("kind", _clean(item.get("kind"))),
        ("tags", tags),
    ):
        if not value:
            continue
        field_id = f"{CLASSIFICATION_FIELD_PREFIX}{key}"
        if field_id in declared:
            facts[field_id] = value
    return facts
