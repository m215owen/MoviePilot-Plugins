"""短剧百科数据源 · 宿主映射与对外载荷。

两件事，都在这一层收口：

1. **映射成宿主模型**：把 :mod: 解析出的扁平字典变成宿主认识的
   MediaInfo（识别 / 刮削 / 订阅走这条路），并登记图片域名。
2. **对外载荷**：给别的插件与外部脚本的纯 JSON 形态 —— 只保留标量 + 精简演员表，
   消费方不该被宿主 MediaInfo 的字段版本绑住，也不该在 JSON 里收到模型对象。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .constants import (
    CLASSIFICATION_FIELDS,
    CLASSIFICATION_FIELD_PREFIX,
    MEDIA_SOURCE_KEY,
    PLUGIN_NAME,
)
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


def build_media_info(item: Dict[str, Any], extra: Optional[Dict[str, Any]] = None) -> Any:
    """把解析结果映射成宿主 ``MediaInfo``。

    :param item: 解析结果（``parse_org_detail`` / 卡片记录）
    :param extra: 额外字段（目前只有 :mod:`tmdb` 补的 ``tmdb_id`` / ``season_info`` /
        ``number_of_seasons``）。**必须是真的、匹配过的 TMDB 身份** —— 宿主详情页的
        演职员 / 推荐 / 分季区块会拿这个 ID 去 TMDB 取数，附错等于把页面连到别的剧。

    宿主对插件返回值的唯一硬要求是「能当 ``MediaInfo`` 用」，因此这里先按
    ``app.sdk.media.MediaInfo``（与 TMDB / 豆瓣模块同一个领域模型）构造；
    该模型不可用时再退到 ``app.schemas.MediaInfo``。构造完成后**重新断言**
    ``media_source`` / ``media_id`` —— ``MediaInfo.__post_init__`` 会调用
    ``resolve_media_identity``，自定义来源有被归一化掉的风险，而已装插件
    ``iqiyidiscover`` 正是用「构造后再赋值」这一姿势绕开它的。
    """
    media_id = str(item.get("media_id") or "")
    title = _clean(item.get("title"))
    if not media_id or not title:
        return None
    extra = extra or {}

    rating = item.get("rating")
    try:
        vote_average = float(str(rating).strip()) if rating not in (None, "") else 0.0
    except (TypeError, ValueError):
        vote_average = 0.0

    tags = [tag for tag in (item.get("tags") or []) if tag]
    actors = _media_info_actors(item)
    studio = _clean(item.get("studio"))
    release_date = _clean(item.get("release_date")) or None
    episode_minutes = _episode_minutes(item)

    fields: Dict[str, Any] = {
        "media_source": media_source_value(),
        "media_id": media_id,
        "type": MediaType.TV,
        "title": title,
        "year": item.get("year") or None,
        "overview": _clean(item.get("overview")) or None,
        "poster_path": _normalize_image(item.get("poster")) or None,
        "backdrop_path": _normalize_image(item.get("backdrop")) or None,
        "vote_average": vote_average,
        "release_date": release_date,
        "first_air_date": release_date,
        "number_of_episodes": item.get("episode_count"),
        # ⚠️ 宿主详情页那行「N 分钟」在电视剧上读 ``runtime``（缺则 ``episode_run_time[0]``），
        # 语义是**单集时长** —— 实测 TMDB 剧集样本 ``runtime=null`` + ``episode_run_time=[45]``。
        # 站点给的是**全集总时长**，直接塞 runtime 会显示成「153 分钟」（80 集短剧），是错的；
        # 单集按集数折算（parser 已算），全集时长留在 record 的 ``duration_minutes`` 里。
        "runtime": episode_minutes,
        "genres": [{"name": tag} for tag in tags],
        "names": list(tags),
        "actors": actors,
        "production_companies": [{"name": studio}] if studio else [],
        "status": _clean(item.get("status")) or None,
        "homepage": _clean(item.get("url")) or None,
        # ``tagline`` 是详情页里**唯一无条件渲染的自由文本位**（简介标题正上方），
        # 其余能放链接的地方（chip / homepage 行）前端都写死了来源，插件的站点链接进不去
        # ⇒ 这里放**作品在站点上的原始地址**（宿主不把它渲染成可点链接，只是纯文本）。
        "tagline": _clean(item.get("url")) or None,
    }
    # TMDB 真实身份（:mod:`tmdb` 严格匹配过才给）：宿主详情页的评分面板 / 演职员 / 推荐 /
    # 分季全都挂在这个 ID 上。取不到就没有这个键，行为与从前完全一致。
    tmdb_id = extra.get("tmdb_id")
    if isinstance(tmdb_id, int) and tmdb_id > 0:
        fields["tmdb_id"] = tmdb_id

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
    # ``episode_run_time`` 是电视剧单集时长的规范位置（详情页在 runtime 缺失时读它）。
    # 构造后赋值而不是塞 kwargs：宿主旧版本若没这个字段，构造会整个失败、插件就废了。
    try:
        mediainfo.episode_run_time = [episode_minutes] if episode_minutes else []
    except Exception as err:  # pragma: no cover - 只读模型兜底
        logger.debug(f"{PLUGIN_NAME} 写入单集时长失败：{err}")
    # 分季信息同样构造后赋值（详情页的「分季分集」区块按 season_info 渲染，缺了会只剩标题）
    for name in ("season_info", "number_of_seasons"):
        if extra.get(name) is None:
            continue
        try:
            setattr(mediainfo, name, extra[name])
        except Exception as err:  # pragma: no cover - 只读模型兜底
            logger.debug(f"{PLUGIN_NAME} 写入 {name} 失败：{err}")
    # 分类事实：``MediaInfo.classification_facts`` 是宿主给插件来源留的口子
    # （``application/classification/analysis.py`` 的 ``_media_extension_facts``
    # 只读 ``extensions.<来源>.<字段>`` 前缀的键）。没有它，宿主的分类策略在我们的
    # 来源上一条规则都命中不了 ⇒ 落「未分类」⇒ 目录匹配拒绝 ⇒ **整理不了**。
    try:
        mediainfo.classification_facts = build_classification_facts(item)
    except Exception as err:  # pragma: no cover - 只读模型兜底
        logger.debug(f"{PLUGIN_NAME} 写入分类事实失败：{err}")
    return mediainfo


def build_classification_facts(item: Dict[str, Any]) -> Dict[str, Any]:
    """给宿主分类策略的扩展事实（键必须带 ``extensions.<来源>.`` 前缀）。

    * ``is_short_drama``：恒为 ``True``。本站只收录短剧，规则拿它做「是本源识别出来的
      就归短剧」的兜底条件 —— 宿主不允许用 ``identity.media_source`` 当条件（插件来源
      上该字段被判「不可用」），这是唯一能稳定表达「来源=短剧百科」的事实。
    * ``kind`` / ``tags``：站点真实字段（角标形态 / 题材标签），页面没给就不带，
      便于以后按真人 / AI 或题材再细分目录。**不伪造**：缺就是缺。
    """
    declared = {str(field.get("id")) for field in CLASSIFICATION_FIELDS}
    facts: Dict[str, Any] = {}
    for key, value in (
        ("is_short_drama", True),
        ("kind", _clean(item.get("kind"))),
        ("tags", [tag for tag in (item.get("tags") or []) if tag]),
    ):
        if not value:
            continue
        field_id = f"{CLASSIFICATION_FIELD_PREFIX}{key}"
        # 只发声明过的字段：没登记的事实会被宿主判为「忽略插件分类事实」并刷警告
        if field_id in declared:
            facts[field_id] = value
    return facts


def _media_info_actors(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    """阵容按宿主形体交给 ``MediaInfo``，顺带补一份 ``avatar``。

    宿主通用刮削器（``app.domain.scraper.MediaScraperHelper``）写 NFO 时读的是
    ``actor.get("avatar") or actor.get("images")``，而站点给的是 ``profile_path``
    （绝对地址）⇒ 不补这一手，NFO 里每个演员都会留一个空的 ``<thumb/>``。
    ``profile_path`` 原样保留，别处（跨插件载荷、演员接口）照旧。

    ⚠️ **必须拷贝**：``item`` 是解析缓存里的同一个字典，直接改会污染缓存与后续调用。
    """
    actors: List[Dict[str, Any]] = []
    for raw in item.get("actors") or []:
        if not raw.get("name"):
            continue
        actor = dict(raw)
        avatar = _clean(actor.get("profile_path"))
        if avatar and not actor.get("avatar"):
            actor["avatar"] = {"large": avatar}
        actors.append(actor)
    return actors


def _episode_minutes(item: Dict[str, Any]) -> Optional[int]:
    """单集时长（分钟）：优先取 parser 算好的，否则按「全集 ÷ 集数」现场折算。

    宿主详情页那行「N 分钟」对电视剧读的就是单集时长（见 ``build_media_info`` 里的注释）。
    """
    value = item.get("episode_minutes")
    if isinstance(value, int) and value > 0:
        return value
    episodes = item.get("episode_count")
    total = item.get("duration_minutes")
    if isinstance(episodes, int) and episodes > 0 and isinstance(total, int) and total > 0:
        return max(1, round(total / episodes))
    return None


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
    "episode_minutes",
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
    # TMDB 真实身份（严格匹配成功才有）：面板的「原始数据」与跨插件 JSON 都要看得见
    "tmdb_id",
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
