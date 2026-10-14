"""短剧百科数据源 · 宿主映射与对外载荷。

两件事，都在这一层收口：

1. **映射成宿主模型**：把 :mod: 解析出的扁平字典变成宿主认识的
   MediaInfo（识别 / 刮削 / 订阅走这条路），并登记图片域名。
2. **对外载荷**：给别的插件与外部脚本的纯 JSON 形态 —— 只保留标量 + 精简演员表，
   消费方不该被宿主 MediaInfo 的字段版本绑住，也不该在 JSON 里收到模型对象。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .constants import MEDIA_SOURCE_KEY, PLUGIN_NAME
from .parser import _clean, _has_value, _normalize_image

try:  # 宿主媒体信息领域模型（与 TMDB / 豆瓣模块返回的是同一个类）
    from app.sdk.media import MediaInfo as _HostMediaInfo
except Exception:  # pragma: no cover - 宿主版本差异兜底
    _HostMediaInfo = None

try:  # 宿主媒体来源与类型枚举
    from app.schemas.types import MediaType
except Exception:  # pragma: no cover - 宿主版本差异兜底
    MediaType = None  # type: ignore[assignment]

try:
    from app.sdk.logging import logger
except Exception:  # pragma: no cover - 宿主版本差异兜底
    import logging

    logger = logging.getLogger('shortdramabaikesource')  # type: ignore[assignment]

try:  # 宿主媒体来源枚举
    from app.schemas import MediaSource
except Exception:  # pragma: no cover - 宿主版本差异兜底
    MediaSource = None  # type: ignore[assignment]


# ── 媒体信息映射 ──────────────────────────────────────────────────


def media_source_value() -> Any:
    """返回宿主的媒体来源标识；``MediaSource`` 不可用时退回纯字符串。"""
    if MediaSource is None:  # pragma: no cover - 极端兜底
        return MEDIA_SOURCE_KEY
    try:
        return MediaSource(MEDIA_SOURCE_KEY)
    except Exception:  # pragma: no cover - 宿主枚举不接受自定义值时
        return MEDIA_SOURCE_KEY


def build_detail_facts(item: Dict[str, Any]) -> str:
    """把「评分 / 集数 / 主演」拼成一行摘要，供详情页的 ``tagline`` 位使用。

    这是**有意的补偿**，不是照抄站点字段：宿主的媒体详情页里，「评分」区与
    「演职员」区是前端按 **TMDB / 豆瓣 / Bangumi 三个来源硬编码**渲染的 —— 判定
    条件就是媒体有没有 ``tmdb_id`` / ``douban_id`` / ``bangumi_id``，自定义来源
    （本插件）无论如何都拿不到这两个位置。整页里唯一能承载这类信息的**自由文本
    位**是 ``tagline``（它渲染在「简介」标题的正上方），所以把评分与主演收进
    这一行，是让它们在详情页可见的唯一办法。``detail_facts`` 开关可以关掉它。
    """
    parts: List[str] = []
    rating = _clean(item.get("rating"))
    if rating:
        parts.append(f"评分 {rating}")
    episodes = item.get("episode_count")
    if isinstance(episodes, int) and episodes > 0:
        parts.append(f"全 {episodes} 集")
    names = [
        _clean(actor.get("name"))
        for actor in (item.get("actors") or [])
        if isinstance(actor, dict) and _clean(actor.get("name"))
    ]
    if names:
        parts.append("主演 " + "、".join(names[:3]) + (" 等" if len(names) > 3 else ""))
    return " · ".join(parts)


def build_media_info(item: Dict[str, Any], facts: bool = True) -> Any:
    """把解析结果映射成宿主 ``MediaInfo``。

    宿主对插件返回值的唯一硬要求是「能当 ``MediaInfo`` 用」，因此这里先按
    ``app.sdk.media.MediaInfo``（与 TMDB / 豆瓣模块同一个领域模型）构造；
    该模型不可用时再退到 ``app.schemas.MediaInfo``。构造完成后**重新断言**
    ``media_source`` / ``media_id`` —— ``MediaInfo.__post_init__`` 会调用
    ``resolve_media_identity``，自定义来源有被归一化掉的风险，而已装插件
    ``iqiyidiscover`` 正是用「构造后再赋值」这一姿势绕开它的。

    ``facts`` 控制是否写入那行事实摘要（见 :func:`build_detail_facts`）——
    ``tagline`` 只有媒体详情页会渲染，所以由调用方按配置决定。
    """
    media_id = str(item.get("media_id") or "")
    title = _clean(item.get("title"))
    if not media_id or not title:
        return None

    rating = item.get("rating")
    try:
        vote_average = float(str(rating).strip()) if rating not in (None, "") else 0.0
    except (TypeError, ValueError):
        vote_average = 0.0

    tags = [tag for tag in (item.get("tags") or []) if tag]
    actors = [actor for actor in (item.get("actors") or []) if actor.get("name")]
    studio = _clean(item.get("studio"))
    release_date = _clean(item.get("release_date")) or None

    fields: Dict[str, Any] = {
        "media_source": media_source_value(),
        "media_id": media_id,
        "type": MediaType.TV,
        "title": title,
        "year": item.get("year") or None,
        "overview": _clean(item.get("overview")) or None,
        "tagline": (build_detail_facts(item) or None) if facts else None,
        "poster_path": _normalize_image(item.get("poster")) or None,
        "backdrop_path": _normalize_image(item.get("backdrop")) or None,
        "vote_average": vote_average,
        "release_date": release_date,
        "first_air_date": release_date,
        "number_of_episodes": item.get("episode_count"),
        "runtime": item.get("duration_minutes"),
        "genres": [{"name": tag} for tag in tags],
        "names": list(tags),
        "actors": actors,
        "production_companies": [{"name": studio}] if studio else [],
        "status": _clean(item.get("status")) or None,
        "homepage": _clean(item.get("url")) or None,
    }

    mediainfo = None
    for model in (_HostMediaInfo, _schema_media_info()):
        if model is None:
            continue
        try:
            mediainfo = model(**fields)  # type: ignore[misc]
            break
        except Exception as err:  # pragma: no cover - 字段集差异兜底
            logger.debug(f"{PLUGIN_NAME} 构造媒体信息失败（{model}）：{err}")

    if mediainfo is None:
        return None

    # __post_init__ 里的 resolve_media_identity 可能改写自定义来源，这里显式复位
    try:
        mediainfo.media_source = media_source_value()
        mediainfo.media_id = media_id
    except Exception as err:  # pragma: no cover - 只读模型兜底
        logger.debug(f"{PLUGIN_NAME} 复位媒体身份失败：{err}")
    return mediainfo


def _schema_media_info() -> Any:
    """惰性取 ``app.schemas.MediaInfo``（部分宿主版本只在这里暴露该类）。"""
    try:
        from app import schemas

        return getattr(schemas, "MediaInfo", None)
    except Exception:  # pragma: no cover - 宿主版本差异兜底
        return None


# ── 跨插件 / 外部消费的稳定载荷 ───────────────────────────────────
# 只保留标量 + 精简演员表：消费方（其它插件、脚本、外部程序）不该被宿主
# ``MediaInfo`` 的字段版本绑住，也不该在 JSON 里收到模型对象。
PUBLIC_RECORD_FIELDS = (
    "media_id",
    "native_id",
    "title",
    "year",
    "overview",
    "poster",
    "backdrop",
    "episode_count",
    "duration_minutes",
    "release_date",
    "rating",
    "heat",
    "play_count",
    "favorite_count",
    "kind",
    "badge",
    "series",
    "season",
    "tags",
    "studio",
    "url",
    "in_language",
)
# 作品记录里「演员」条目的字段（与演员档案的 PUBLIC_ACTOR_FIELDS 是两回事）。
# ⚠️ 字段名必须与 ``_org_cast_from_json_ld`` / ``_org_cast_from_html`` 的产出逐字一致
# —— 那两处写的是 ``character`` / ``profile_path``，不是 ``role`` / ``poster``。
PUBLIC_CAST_FIELDS = ("id", "name", "character", "profile_path", "kind")
# 「推荐位」最多带几部（站点一页通常 6~10 部，截到 10 免得载荷失控）
MAX_RELATED = 10


def build_public_record(item: Optional[Dict[str, Any]], origin: str = "detail") -> Dict[str, Any]:
    """把一条作品记录压成**纯 JSON** 载荷（其它插件调用的统一形状）。

    :param item: ``parse_org_detail`` / ``parse_org_cards`` 产出的记录
    :param origin: ``detail``（详情页，字段全）或 ``search``（详情页没抓到，退回检索结果——
        只有 ID 与片名，其余字段为空）
    """
    record: Dict[str, Any] = {
        "media_source": MEDIA_SOURCE_KEY,
        "origin": origin,
        "url": "",
        "title": "",
    }
    if not item:
        return record
    for name in PUBLIC_RECORD_FIELDS:
        value = item.get(name)
        if value in (None, "", []):
            continue
        record[name] = value
    actors = [
        {key: actor.get(key) for key in PUBLIC_CAST_FIELDS if actor.get(key)}
        for actor in (item.get("actors") or [])
        if actor.get("name")
    ]
    if actors:
        record["actors"] = actors
    # 同页「推荐短剧」：站点自己给的关联作品，字段口径与本记录一致（卡片解析产出）
    related = [
        {key: row.get(key) for key in PUBLIC_RECORD_FIELDS if _has_value(row.get(key))}
        for row in (item.get("related") or [])[:MAX_RELATED]
        if row.get("title")
    ]
    if related:
        record["related"] = related
    return record


# 演员档案对外 JSON 里带的字段（顺序即展示顺序）
PUBLIC_ACTOR_FIELDS: Tuple[str, ...] = (
    "actor_id",
    "media_id",
    "name",
    "job_title",
    "gender",
    "nationality",
    "profile",
    "bio",
    "url",
)


def build_public_actor(item: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """把一条演员档案整理成纯 JSON（跨插件 / 外部脚本用）。

    作品条目复用 ``parse_org_cards`` 的输出（``media_id`` / ``title`` / ``poster`` /
    ``episode_count`` / ``rating`` / ``tags`` …），这里只补一个 ``works_count``，
    免得消费方还要自己数。

    :param item: ``parse_org_actor`` 的结果
    :return: 无空值的纯 JSON 字典；``item`` 为空时返回空字典
    """
    if not item:
        return {}
    record: Dict[str, Any] = {
        name: item[name]
        for name in PUBLIC_ACTOR_FIELDS
        if _has_value(item.get(name))
    }
    works = [dict(work) for work in (item.get("works") or []) if work.get("title")]
    record["works"] = works
    record["works_count"] = len(works)
    # 合作演员来自 ``parse_org_cast``，用的是**阵容记录**的字段名（id / character /
    # profile_path），不是演员档案的字段名 —— 套错会把内容整条清空，只剩 name。
    coactors = [
        {key: actor.get(key) for key in PUBLIC_CAST_FIELDS if _has_value(actor.get(key))}
        for actor in (item.get("coactors") or [])
        if actor.get("name")
    ]
    if coactors:
        record["coactors"] = coactors
    return record
