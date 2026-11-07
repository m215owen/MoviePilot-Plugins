"""``.org`` 解析结果 → 本插件的 detail / person 结构。

:mod:`orgsite` 是从 ``shortdramanetsource`` 整体搬过来的，输出的记录 shape 是
那边定的（``title`` / ``synopsis`` / ``people`` / ``genres`` …）。本插件下游
（``parser.detail_to_media_info`` / ``hostmedia`` / ``scrape`` / ``api``）认的是
``parser.parse_detail`` 那套键（``name`` / ``overview`` / ``actors`` / ``tags`` …）。

这里只做**字段搬运与少量归一**，不做任何再解析：

* 站点已给的字段原样搬（不重算、不猜）；
* 缺失的字段给空值（``""`` / ``None`` / ``[]``），让下游的「有就展示」逻辑自然跳过；
* ``.org`` 独有的字段（``series`` / ``same_script`` / ``comments`` / ``is_ai`` …）
  **原样带出去**，API 层可选展示，不影响识别链路。

两站 shape 的差异只在这一层吸收，``service`` / ``api`` / 前端都不用知道数据来自哪站。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import constants
from .media_id import detail_url as page_url
from .siteutil import clean, to_int


def _year_of(value: Any) -> Optional[int]:
    """``2026`` / ``2026-11-04`` → 2026；认不出给 ``None``。"""
    text = clean(value)
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    number = to_int(text, 0)
    return number or None


def _card(row: Dict[str, Any]) -> Dict[str, Any]:
    """``.org`` 卡行 → 本插件的人物作品卡（``parse_person_works`` 同形）。"""
    media_id = str(row.get("media_id") or "")
    genres = [clean(item) for item in (row.get("genres") or []) if clean(item)]
    return {
        "media_id": media_id,
        "name": clean(row.get("title") or row.get("name") or ""),
        "kind": constants.KIND_OF_ENTITY.get(media_id.partition(":")[0], ""),
        "poster": clean(row.get("poster") or ""),
        "date": clean(row.get("release_date") or ""),
        "episodes": to_int(row.get("episodes"), 0),
        "actors": [
            part.strip()
            for part in str(row.get("actors_text") or "").replace("·", "/").split("/")
            if part.strip()
        ],
        "tags": genres,
        "badge": clean(row.get("badge") or ""),
        # 状态角标（爆火 / 新剧 / 完结 / 预约…，parse_cards 已解析的多值原样文本）：
        # 消费方（短剧演员订阅）按它判「新剧」、在作品卡上印「爆火」——
        # 2026-11-04 修复：这层归一原来把它丢了，人物作品流里整列消失。
        "badges": [clean(item) for item in (row.get("badges") or []) if clean(item)],
        "season": to_int(row.get("season"), 0),
        # AI 标随卡带走：配置的「排除」开关在新站按它生效（service.is_excluded_item），
        # 少了这一格，人物作品 / 改编清单里的 AI 剧就漏过开关。
        "is_ai": bool(row.get("is_ai")),
    }


def _cards(rows: Any) -> List[Dict[str, Any]]:
    return [_card(row) for row in (rows or []) if isinstance(row, dict) and row.get("media_id")]


def work_detail(media_id: str, record: Dict[str, Any]) -> Dict[str, Any]:
    """``orgsite.parse_work`` 的记录 → ``parser.parse_detail`` 同形的 detail dict。"""
    adapted = record.get("adapted_from") or {}
    novel: Optional[Dict[str, Any]] = None
    if isinstance(adapted, dict) and (adapted.get("title") or adapted.get("poster")):
        novel = {
            # .org 的原著区块没有链接（整块 0 个 <a>）→ 拿不到 xiaoshuo:<id>，
            # 身份留空，只记书名 / 封面 / 题材（与 .net 的原著卡语义不同）
            "media_id": "",
            "name": clean(adapted.get("title") or ""),
            "poster": clean(adapted.get("poster") or ""),
            "genres": [clean(item) for item in (adapted.get("genres") or []) if clean(item)],
        }

    actors = [
        {
            "media_id": str(person.get("media_id") or ""),
            "name": clean(person.get("name") or ""),
            "role": clean(person.get("role") or ""),
            "poster": clean(person.get("poster") or ""),
        }
        for person in (record.get("people") or [])
        if isinstance(person, dict) and person.get("name")
    ]

    heat = record.get("heat")
    play = record.get("play_count")
    favorites = record.get("favorites")

    genres = [clean(item) for item in (record.get("genres") or []) if clean(item)]

    return {
        "media_id": record.get("media_id") or media_id,
        "name": clean(record.get("title") or ""),
        # .org 卡片没有 .net 的内容角标，类型看题材：站内把漫剧的题材里固定写了「漫剧」
        "kind": "漫剧" if "漫剧" in genres else "短剧",
        "year": _year_of(record.get("year") or record.get("release_date")),
        "episodes": to_int(record.get("episodes"), 0) or None,
        "overview": clean(record.get("synopsis") or ""),
        "tags": genres,
        "actors": actors,
        # .org 的 JSON-LD 只给演员（PerformanceRole），没有导演 / 编剧出口
        "directors": [],
        "rating": float(record.get("rating") or 0) or None,
        "duration": clean(record.get("duration") or ""),
        "release_date": clean(record.get("release_date") or ""),
        "platform": clean(record.get("platform") or record.get("studio") or ""),
        "platform_heat": heat or "",
        "play_count": play or "",
        "favorite_count": favorites or "",
        "novel": novel,
        # 「同一小说还拍了以下版本」→ 与 .net 原著页的 adaptations 同语义
        "adaptations": _cards((adapted or {}).get("works")),
        "author": "",
        "aka": "",
        "words": "",
        "poster_path": clean(record.get("poster") or ""),
        # 记录里不带 url（orgsite 的作品记录没有这个键）→ 按身份模板反推同一地址
        "detail_url": clean(record.get("url") or "") or page_url(str(record.get("media_id") or media_id)),
        "desc": "",
        # ── .org 独有（不影响识别，API / 前端可选展示） ──
        "season": to_int(record.get("season"), 0),
        "status": clean(record.get("status") or ""),
        "is_ai": bool(record.get("is_ai")),
        "series": _cards(record.get("series")),
        "same_script": _cards(record.get("same_script")),
        "comments": list(record.get("comments") or []),
    }


def person_detail(media_id: str, record: Dict[str, Any]) -> Dict[str, Any]:
    """``orgsite.parse_actor`` 的记录 → ``parser.parse_person`` 同形的 dict。"""
    works = _cards(record.get("works"))
    job_title = clean(record.get("job_title") or "") or "演员"
    return {
        "media_id": record.get("media_id") or media_id,
        "name": clean(record.get("name") or ""),
        "role": job_title,
        "kind": job_title,
        # .org 的头像是 CDN 绝对地址（随页面给），不能按身份反拼
        "avatar": clean(record.get("poster") or ""),
        "intro": clean(record.get("biography") or ""),
        "works": works,
        "work_count": to_int(record.get("works_count"), len(works)) or len(works),
        "detail_url": clean(record.get("url") or ""),
        # ── .org 独有档案字段 ──
        "gender": clean(record.get("gender") or ""),
        "birth_date": clean(record.get("birth_date") or ""),
        "birth_year": clean(record.get("birth_year") or ""),
        "birth_place": clean(record.get("birth_place") or ""),
        "constellation": clean(record.get("constellation") or ""),
        "education": clean(record.get("education") or ""),
        "nationality": clean(record.get("nationality") or ""),
        "height_cm": to_int(record.get("height_cm"), 0),
        "followers": to_int(record.get("followers"), 0),
        "people": list(record.get("people") or []),
    }


__all__ = ["person_detail", "work_detail"]
