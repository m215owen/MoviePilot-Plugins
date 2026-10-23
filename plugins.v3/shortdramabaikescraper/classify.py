"""来源专有分类事实：把「是不是本站短剧 / 是短剧还是漫剧」交给宿主自动分类。

为什么不用宿主标准字段 ``身份·媒体来源``：

* 插件来源在 ``identity.media_source`` 这个字段上被宿主判为「不可用」
  （UI 直接显示红字，规则存下来也不会命中）；
* 而且主身份一旦被 TMDB 重新识别，``media_source`` 就变成 ``themoviedb``。

所以按官方 FAQ 19 §4 / FAQ 20 §2 声明**自己命名空间**下的字段，随识别结果提交事实：

* ``extensions.djbaike.is_short_drama``（boolean）：本站识别出来的作品恒为真，
  规则用 ``is_true`` —— **不需要条件值**，也不受主身份变化影响；
* ``extensions.djbaike.kind``（string，候选值 短剧/漫剧）：站点真实分类，供细分目录。

两条硬约束（源码实测，别踩）：

1. **``value_type`` 不要用 ``enum``**。``enum`` + ``allow_custom_values=False`` 时，
   目录外的值会被宿主当成「值不符合声明」整条丢弃，规则静默漏命中；参考实现
   ``ShortDramaBaikeSource`` 也是刻意用 ``string`` + ``options`` 仅作候选提示。
2. 事实必须**先声明后提交**：没登记的字段会被宿主记
   ``classification_extension_source_unregistered`` 并忽略。
"""

from __future__ import annotations

from typing import Any, Optional

from app.sdk.logging import logger

from . import constants
from .media_id import is_drama, kind_of, parse_media_id

#: 字段前缀（宿主校验：必须 ``extensions.<media_source>.``）
FIELD_PREFIX = f"extensions.{constants.MEDIA_SOURCE_ID}."

#: 是否本站收录（boolean，恒真）——规则用 ``is_true``，无需条件值
FACT_IS_SHORT = f"{FIELD_PREFIX}is_short_drama"
#: 站点分类（string：短剧 / 漫剧）
FACT_KIND = f"{FIELD_PREFIX}kind"
#: 站内热度 / 播放量 / 收藏数（string，站点原串）——宿主 ``MediaInfo`` 没有对应字段，
#: 不挂成事实就只能烂在 detail dict 里（详情缓存有、识别结果没有）
FACT_HEAT = f"{FIELD_PREFIX}heat"
FACT_PLAY = f"{FIELD_PREFIX}play_count"
FACT_FAVORITE = f"{FIELD_PREFIX}favorite_count"

#: 兼容旧名（此前只声明了 kind 一个字段）
KIND_OPTIONS = ("短剧", "漫剧")

_MEDIA_TYPES = ["电视剧"]


def protocol_version() -> int:
    """宿主支持的分类来源协议版本；旧宿主按 0 处理。"""
    try:
        from app.sdk.classification import MEDIA_SOURCE_CLASSIFICATION_PROTOCOL_VERSION
    except (ImportError, AttributeError):
        return 0
    try:
        return int(MEDIA_SOURCE_CLASSIFICATION_PROTOCOL_VERSION)
    except (TypeError, ValueError):  # pragma: no cover
        return 0


def classification_fields() -> list[Any]:
    """构造本来源的分类字段声明；宿主不支持时返回空列表（来源声明照常）。"""
    if protocol_version() < 1:
        return []
    try:
        from app.sdk.classification import ClassificationFieldDefinition

        return [
            ClassificationFieldDefinition(
                id=FACT_IS_SHORT,
                label="短剧百科收录",
                group="短剧百科",
                description="由短剧百科识别成功的作品；规则可用「为真」直接归入短剧",
                value_type="boolean",
                operators=["is_true", "is_false", "exists", "not_exists"],
                media_types=_MEDIA_TYPES,
            ),
            ClassificationFieldDefinition(
                id=FACT_KIND,
                label="短剧形态",
                group="短剧百科",
                description="站点上的分类：短剧 / 漫剧（开放字符串，新增形态不会被丢弃）",
                value_type="string",
                operators=[
                    "equals",
                    "not_equals",
                    "in",
                    "not_in",
                    "exists",
                    "not_exists",
                ],
                media_types=_MEDIA_TYPES,
                # options 只作前端候选提示；allow_custom_values 保持默认 True
                options=[
                    {"value": "短剧", "label": "短剧"},
                    {"value": "漫剧", "label": "漫剧"},
                ],
            ),
            # 站内指标：宿主 MediaInfo 没有「热度 / 播放 / 收藏」列，只能作为来源事实提交。
            # 一律用 ``string`` 存**站点原串**（``383.37万``、``989万``）：折算成数字既丢
            # 量级感，又分不清「站点给的」与「我们算的」。规则侧因此写不了 gt/lt，
            # 只能 equals / contains / exists —— 这三个指标本来也不该当排序键。
            ClassificationFieldDefinition(
                id=FACT_HEAT,
                label="站内热度",
                group="短剧百科",
                description="短剧百科详情页标注的平台热度（站点原串，如 383.37万）",
                value_type="string",
                operators=["equals", "not_equals", "in", "not_in", "contains", "exists", "not_exists"],
                media_types=_MEDIA_TYPES,
            ),
            ClassificationFieldDefinition(
                id=FACT_PLAY,
                label="站内播放量",
                group="短剧百科",
                description="短剧百科详情页标注的累计播放量（站点原串，如 989万）",
                value_type="string",
                operators=["equals", "not_equals", "in", "not_in", "contains", "exists", "not_exists"],
                media_types=_MEDIA_TYPES,
            ),
            ClassificationFieldDefinition(
                id=FACT_FAVORITE,
                label="站内收藏数",
                group="短剧百科",
                description="短剧百科详情页标注的收藏人数（站点原串，如 1.32万）",
                value_type="string",
                operators=["equals", "not_equals", "in", "not_in", "contains", "exists", "not_exists"],
                media_types=_MEDIA_TYPES,
            ),
        ]
    except Exception:  # pragma: no cover - 声明失败只降级，不影响来源注册
        return []


def facts_for(media_id: str, detail: Optional[dict] = None) -> dict[str, Any]:
    """作品 ``media_id`` → 分类事实；人物与原著不产出事实。

    * 百科作品前缀（duanju/manju/hema/huolong）→ ``is_short_drama=True`` + ``kind``；
    * ``douban:`` 条目不知道是否短剧 → 不产出（**不伪造**）；
    * 传了 ``detail`` 时再附上站内热度 / 播放 / 收藏（宿主 ``MediaInfo`` 没有这三列，
      只有事实通道能带出去；值就是站点原串，不折算）。

    指标只在**非空**时才提交：站点没写这一项就不提交该键，这样规则里的
    ``exists`` / ``not_exists`` 才是「有 / 没有」而不是「有值 / 空串」。
    """
    entity, native_id = parse_media_id(media_id)
    if not entity or not native_id or not is_drama(media_id):
        return {}
    # 豆瓣条目只是「条目存在」，站点没给分类，不能冒充本站短剧
    if entity.startswith("douban"):
        return {}
    kind = kind_of(media_id)
    facts: dict[str, Any] = {FACT_IS_SHORT: True}
    if kind in KIND_OPTIONS:
        facts[FACT_KIND] = kind
    if isinstance(detail, dict):
        # 热度 / 播放 / 收藏：原串直出（``989万`` 之类），**不做任何数值折算**
        for fact_id, key in (
            (FACT_HEAT, "platform_heat"),
            (FACT_PLAY, "play_count"),
            (FACT_FAVORITE, "favorite_count"),
        ):
            value = str(detail.get(key) or "").strip()
            if value:
                facts[fact_id] = value
    return facts


def attach(
    media_info: Any,
    media_id: Optional[str] = None,
    detail: Optional[dict] = None,
) -> Any:
    """把分类事实挂到 ``MediaInfo`` 上（构造后追加，避免各调用点重复写）。

    两条落点都要覆盖，否则宿主分类器读不到值：

    * ``app.schemas.MediaInfo``（HTTP 端点直接序列化）；
    * ``app.sdk.media.MediaInfo``（``hostmedia.to_host_media`` 的产物，见该模块 docstring）。
    """
    if media_info is None:
        return media_info
    try:
        facts = facts_for(media_id or getattr(media_info, "media_id", "") or "", detail)
        if facts:
            media_info.classification_facts = {
                **(getattr(media_info, "classification_facts", None) or {}),
                **facts,
            }
    except Exception as err:  # pragma: no cover - 可选增强
        # 以前这里是静默 pass：事实没挂上只会表现为「规则莫名不命中」，极难排查。
        logger.warning(f"{constants.SOURCE_NAME} 分类事实挂载失败：{err}")
    return media_info
