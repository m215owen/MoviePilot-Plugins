"""media_id 的解析与反推：``{entity}:{id}`` 一个字符串承载全部身份信息。

设计要点（计划 §2）：

* 站点 URL 形态固定 —— ``/{entity}/info-{id}.html`` 与 ``img.../{entity}/{id}.jpg``，
  所以 **不需要正则、也不需要判断 id 字符集**，直接按路径段切。
* ``media_id`` 全程字符串：``huolong`` 的 id 是 15 位字母数字混排，``int()`` 会抛异常；
  19 位纯数字转 int 还会掉精度。
* 「短剧 / 漫剧 / 原著」由前缀推断（``kind_of``），不落列；``hema`` 的少量误差只在
  展示层用详情缓存的精确 ``kind`` 纠正。
"""

from __future__ import annotations

from . import constants

# 列表卡片 title / alt 的形态：``短剧《X》`` / ``漫剧《X》`` / ``小说《X》``
_CARD_KIND_PREFIX = {"短剧": "短剧", "漫剧": "漫剧", "小说": "原著"}

_QUOTE_PAIRS = (("《", "》"), ("「", "」"), ("\"", "\""))


def parse_media_id(media_id: str) -> tuple[str, str]:
    """把 ``{entity}:{id}`` 切成 (entity, native_id)。

    没有冒号时返回 ``("", 原串)``——裸的 ``duanju`` 是个实体名而不是 id，
    entity 必须留空，否则 ``is_known("duanju")`` 会误判成「认识的 id」。
    多余冒号只切第一个（id 里不会出现冒号）。
    """
    text = media_id or ""
    if ":" not in text:
        return "", text
    entity, _, native_id = text.partition(":")
    return entity, native_id


def entity_of(media_id: str) -> str:
    """取 media_id 的实体前缀。"""
    return parse_media_id(media_id)[0]


def native_id_of(media_id: str) -> str:
    """取 media_id 的站点原生 id。"""
    return parse_media_id(media_id)[1]


def is_drama(media_id: str) -> bool:
    """是否影视作品（可刮削）：短剧 / 漫剧四分区，或纯豆瓣作品条目。"""
    entity = entity_of(media_id)
    return entity in constants.ENTITY_DRAMA or entity == constants.DOUBAN_WORK


def is_novel(media_id: str) -> bool:
    """是否原著（小说）：不入作品候选，只供 media_id 直取详情。"""
    return entity_of(media_id) in constants.ENTITY_NOVEL


def is_person(media_id: str) -> bool:
    """是否人物：演员 / 导演 / 编剧，或纯豆瓣影人条目。"""
    entity = entity_of(media_id)
    return entity in constants.ENTITY_PERSON or entity == constants.DOUBAN_PERSON


def is_known(media_id: str) -> bool:
    """是否本插件认识的 media_id 形态（八类百科实体 + 两个豆瓣前缀）。"""
    entity = entity_of(media_id)
    return entity in constants.ENTITY_ALL or entity in (
        constants.DOUBAN_WORK,
        constants.DOUBAN_PERSON,
    )


def kind_of(media_id: str) -> str:
    """按前缀推断展示类型：「短剧」/「漫剧」/「原著」；人物与豆瓣条目返回空串。

    ``hema`` 有约 7% 实为短剧，属已知且接受的误差，展示时优先用详情缓存的精确
    ``kind``（见 ``parser.kind_from_tags``）。
    """
    return constants.KIND_OF_ENTITY.get(entity_of(media_id), "")


def detail_url(media_id: str) -> str:
    """详情页 URL。百科八类按固定模板反推；豆瓣两个前缀走各自详情页。

    未知前缀**不编造** URL（返回空串），避免把 ``themoviedb:550`` 拼成本站页面。
    """
    entity, native_id = parse_media_id(media_id)
    if entity == constants.DOUBAN_WORK:
        return f"{constants.DOUBAN_MOVIE_BASE}/subject/{native_id}/"
    if entity == constants.DOUBAN_PERSON:
        return f"{constants.DOUBAN_MOVIE_BASE}/personage/{native_id}/"
    if entity not in constants.ENTITY_ALL or not native_id:
        return ""
    return f"{constants.SITE_BASE}/{entity}/info-{native_id}.html"


def image_url(media_id: str) -> str:
    """海报 / 头像 URL。

    百科八类可由固定模板反推（实测 200）；豆瓣两个前缀无法反推图片，
    只能从详情缓存里取（因此返回空串，由调用方回退到缓存）。
    """
    entity, native_id = parse_media_id(media_id)
    if entity in (constants.DOUBAN_WORK, constants.DOUBAN_PERSON):
        return ""
    if entity not in constants.ENTITY_ALL or not native_id:
        return ""
    return f"{constants.IMAGE_BASE}/{entity}/{native_id}.jpg"


def scan_ids(html: str) -> list[tuple[str, str]]:
    """从任意页面抽出全部 ``(entity, id)``。

    URL 恒为 ``/{entity}/info-{id}.html`` ⇒ ``info-`` 之后到 ``.html`` 之前就是 id，
    再往左一个 ``/`` 之前就是 entity。不限定 id 字符集。

    两处必要防护：
    1. ``info-`` 前必须是 ``/``，挡掉 ``class="info-badge"`` 这类噪音；
    2. entity 边界用 ``rfind("/", 0, i - 1)`` —— ``info-`` 前紧邻的 ``/`` 属于
       entity 段本身，拿它当边界会切出空串（索引差一的经典坑）。
    """
    out: list[tuple[str, str]] = []
    pos = 0
    while True:
        i = html.find("info-", pos)
        if i < 0:
            break
        if i == 0 or html[i - 1] != "/":
            pos = i + 5
            continue
        j = html.find(".html", i + 5)
        if j < 0:
            break
        k = html.rfind("/", 0, i - 1)
        if k < 0:
            pos = j + 5
            continue
        entity = html[k + 1 : i - 1]
        native_id = html[i + 5 : j]
        if (
            entity
            and native_id
            and "/" not in native_id
            and "?" not in native_id
            and "#" not in native_id
            and len(native_id) <= 64
            and not any(ch.isspace() for ch in native_id)
        ):
            out.append((entity, native_id))
        pos = j + 5
    return out


def media_id_of(entity: str, native_id: str) -> str:
    """拼复合 media_id；任一侧为空则返回空串。"""
    if not entity or not native_id:
        return ""
    return f"{entity}:{native_id}"


def name_from_card(text: str) -> str:
    """从卡片 ``title`` / ``alt``（形如 ``短剧《进个城，就和大佬闪婚了》``）取原文名。

    取不到书名号时退回整串（去掉首尾空白），绝不返回编造值。
    """
    raw = (text or "").strip()
    if not raw:
        return ""
    for left, right in _QUOTE_PAIRS:
        start = raw.find(left)
        if start < 0:
            continue
        end = raw.find(right, start + len(left))
        if end > start + len(left):
            return raw[start + len(left) : end].strip()
    return raw


def kind_from_card(label: str) -> str:
    """列表卡片标注 → 展示类型（``短剧``/``漫剧``/``小说`` → 短剧/漫剧/原著）。"""
    return _CARD_KIND_PREFIX.get((label or "").strip(), "")


def kind_from_tags(tags: list[str]) -> str:
    """详情页分类标签 → 精确类型：带「漫」的标签（漫剧/3D漫/仿真人动态漫）即漫剧。

    这是纠正 ``hema`` 前缀误差的唯一来源；结果只写详情缓存 ``djbaike.detail.kind``。
    短剧侧标签是「女性成长」「都市」「逆袭」这类，不含「漫」，故判定可靠。
    """
    return "漫剧" if any("漫" in str(tag) for tag in tags or []) else "短剧"
