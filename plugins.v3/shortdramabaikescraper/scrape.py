"""短剧百科刮削源 · 宿主刮削出口（NFO 文本与图片清单）。

宿主的刮削链（``chain/scraping.py``）在写盘前各问一次模块：

* ``metadata_nfo``（``scraping.py:727``，裸 ``run_module``）；
* ``metadata_img``（``scraping.py:750``，插件来源先走插件分支，拿到 dict 就直接用）。

两个契约（``runtime/extensions/module/contracts.py:498-513``）都是
``FIRST_NON_EMPTY``，且 ``plugin_short_circuit`` 取基类默认 ``True``
（``contracts.py:125``）⇒ dispatcher（``runtime/extensions/module/dispatcher.py:_dispatch``）
**先跑插件**；而 ``is_valid_empty`` 只认 ``None``（``dispatcher.py:172-178``），
所以插件返回非空——**哪怕空 dict ``{}``**——都会短路，宿主内置模块根本不被问。

反向看：内置的 NFO / 图片生成器（themoviedb / douban / bangumi / anilist / imdb）
第一句都是「``mediainfo.scrape_source or SCRAP_SOURCE`` 必须等于自己的来源」，
而整理与手动刮削会把 ``scrape_source`` 设成**媒体来源**
（``chain/transfer/execution.py:581``、``api/endpoints/media.py:516/531``）⇒ 在本来源下
它们**全部返回 None**。插件不实现这两个契约，磁盘上就什么都不会有（日志里只剩
「NFO 文件生成失败！」与「未获取到图片信息，跳过图片刮削」）——这正是 2026-10-23
用户报「整理需要刮削，但没有 nfo 和封面下载」的根因。

实现上复用宿主**公开**的 :class:`app.domain.scraper.MediaScraperHelper`
（anilist / bangumi / imdb 三个内置来源同一个姿势）：字段取统一 ``MediaInfo``，
``uniqueid`` 写成本来源标识，图片清单取 ``poster_path`` / ``backdrop_path``。
自己拼 XML 只会与宿主口径越走越偏。

⚠️ ``app.domain.scraper`` 属官方文档点名的「内部文件位置」，所以导入做容缺：
拿不到时本模块两个出口整体降级（NFO 返 ``None`` / 图片返空），插件其余功能不受影响。

两个刻意的取舍（2026-10-23 用户定范围；季级政策同日二次修订）
------------------------------------

1. **季级素材按季词条产出**。站点把第 N 季拆成独立词条，**季号可从剧名识别**
   （``hostmedia.to_host_media`` 已把词条名里的季号派生进 ``season`` 字段，
   如 ``隐身侍卫第二季`` → ``season=2``），而季词条自己的海报就是该季海报：
   * ``season`` 有值 → NFO 走宿主 helper 的 ``season`` 根（``seasonnumber``）；
   * ``season`` + ``episode`` → helper 的 ``episodedetails`` 根（showtitle + 季集号）；
   * ``season`` 有值的图片 → ``season{NN}-poster{ext}``，取 ``poster_path``
     （仅当词条自身季号与请求季号一致——基名词条被问第 2 季时不拿第一季海报充数）；
   * **分集剧照**站点确实没有 ⇒ ``episode`` 有值的图片返回空 dict，这是真实无素材。
2. **只服务自己的来源**。插件的 provider 排在宿主模块之前且空 dict 也短路，若不做
   身份判断，TMDB / 豆瓣 等来源的刮削会被本插件劫持。:func:`is_own_media` 是唯一闸门，
   **非本来源必须返回 ``None``**（不是 ``{}``）——只有 ``None`` 会让 dispatcher 继续
   问内置模块。
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional
from xml.dom import minidom

from app.sdk.logging import logger

from . import constants

# 宿主公开的通用刮削器（anilist / bangumi / imdb 也用它）。内部路径导入，容缺降级。
try:
    from app.domain.scraper import MediaScraperHelper
except Exception:  # pragma: no cover - 宿主版本差异兜底
    MediaScraperHelper = None  # type: ignore[assignment]

__all__ = ["build_images", "build_nfo", "is_own_media"]


def is_own_media(mediainfo: Any) -> bool:
    """``mediainfo`` 是否由本插件提供身份（刮削 provider 的**唯一**准入条件）。

    刮削链上传进来的 ``MediaInfo`` 是 domain 版（``hostmedia.to_host_media`` 的产物），
    ``media_source`` 是单个 ``MediaSource`` 枚举成员而非识别链路的「多选元组」——
    所以这里不做元组展开，与 ``ShortDramaBaikeScraper._is_our_source`` 各管一段。
    """
    if mediainfo is None:
        return False
    value = getattr(mediainfo, "media_source", None)
    if value is None:
        return False
    # ``MediaSource`` 是 str 枚举，取值统一走 ``value``（拿不到就原样 str）
    return str(getattr(value, "value", value)).strip() == constants.MEDIA_SOURCE_ID


def _element_text(node: Any) -> str:
    """取一个元素节点的合并文本（没有就空串）。"""
    return "".join(
        child.nodeValue or ""
        for child in node.childNodes
        if child.nodeType == child.TEXT_NODE
    ).strip()


def _has_child(node: Any, tag: str) -> bool:
    return any(
        child.nodeType == child.ELEMENT_NODE and child.tagName == tag
        for child in node.childNodes
    )


def _strip_whitespace(node: Any) -> None:
    """递归删掉纯空白文本节点。

    ``minidom.parseString`` 会把 pretty XML 的换行/缩进也变成文本节点，直接
    ``toprettyxml`` 会每个元素前后各炸出一行空白（容器 Python 3.14 实测）。
    宿主自己生成文档时没有这些节点，删掉后再序列化即与原文一致。
    """
    for child in list(node.childNodes):
        if child.nodeType == child.TEXT_NODE and not (child.nodeValue or "").strip():
            node.removeChild(child)
        elif child.nodeType == child.ELEMENT_NODE:
            _strip_whitespace(child)


def _annotate_actors(text: str, mediainfo: Any) -> str:
    """给 NFO 的每个 ``<actor>`` 补 ``<order>``（番位）、``<type>Actor`` 与 ``<thumb>``。

    宿主通用刮削器只写 name / role / thumb 三件套，且 ``thumb`` 只认
    ``avatar`` / ``images`` 键——我们的演员 dict 里头像在 ``profile_path``
    （图床按人物 id 反推的完整 URL，``parser.detail_to_media_info`` 放的），
    不补就是个空节点。``order`` / ``type`` 是 NFO 规范字段（Emby/Jellyfin 按
    order 排演员表）。

    数量一致时按位置对齐；对不上退回按名字查，再不行就放弃该节点（宁缺勿脏）。
    解析失败一律原样返回——注入是锦上添花，不能弄脏一份本来合法的 NFO。
    """
    actors = [
        actor
        for actor in (getattr(mediainfo, "actors", None) or [])
        if isinstance(actor, dict) and str(actor.get("name") or "").strip()
    ]
    if not actors:
        return text
    try:
        doc = minidom.parseString(text.encode("utf-8"))
    except Exception as err:  # pragma: no cover - 宿主产物理论合法
        logger.debug(f"{constants.SOURCE_NAME} NFO 演员注入解析失败，保持原文：{err}")
        return text
    nodes = [
        node
        for node in doc.documentElement.childNodes
        if node.nodeType == node.ELEMENT_NODE and node.tagName == "actor"
    ]
    if not nodes:
        return text

    by_name: Dict[str, tuple] = {}
    for index, actor in enumerate(actors, start=1):
        name = str(actor.get("name") or "").strip()
        if name and name not in by_name:
            by_name[name] = (index, actor)

    positional = len(nodes) == len(actors)
    for position, node in enumerate(nodes, start=1):
        if positional:
            order, actor = position, actors[position - 1]
        else:
            order, actor = None, None
            for child in node.childNodes:
                if child.nodeType == child.ELEMENT_NODE and child.tagName == "name":
                    found = by_name.get(_element_text(child))
                    if found:
                        order, actor = found
                    break
        if actor is None or not order:
            continue
        if not _has_child(node, "order"):
            order_node = doc.createElement("order")
            order_node.appendChild(doc.createTextNode(str(order)))
            node.appendChild(order_node)
        if not _has_child(node, "type"):
            type_node = doc.createElement("type")
            type_node.appendChild(doc.createTextNode("Actor"))
            node.appendChild(type_node)
        thumb = str(actor.get("profile_path") or "").strip()
        if thumb:
            thumb_node = None
            for child in node.childNodes:
                if child.nodeType == child.ELEMENT_NODE and child.tagName == "thumb":
                    thumb_node = child
                    break
            if thumb_node is None:
                thumb_node = doc.createElement("thumb")
                node.appendChild(thumb_node)
            if not _element_text(thumb_node):
                thumb_node.appendChild(doc.createTextNode(thumb))

    _strip_whitespace(doc.documentElement)
    return doc.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")


def _has_uniqueid(node: Any, id_type: str) -> bool:
    """根节点下是否已有该 ``type`` 的 ``<uniqueid>``（避免重复写）。"""
    for child in node.childNodes:
        if child.nodeType != child.ELEMENT_NODE or child.tagName != "uniqueid":
            continue
        if (child.getAttribute("type") or "").strip().lower() == id_type.strip().lower():
            return True
    return False


def _annotate_external_ids(text: str, mediainfo: Any) -> str:
    """给 NFO 补上 TMDB / 豆瓣 id（宿主通用刮削器不写这两个）。

    宿主的 ``get_metadata_nfo`` 只写 ``_media_identity`` 拿到的那个 ``uniqueid``
    （本来源标识），外部 id 一概不写 —— 媒体服务器拿不到它们就拉不到更全的
    元数据，所以在这里补。

    **两套标签都写**，谁读都有：``<tmdbid>`` / ``<doubanid>`` 是 Kodi 的老写法，
    ``<uniqueid type="tmdb">`` 是 Emby / Jellyfin 用的新式。本来源那个
    ``uniqueid`` 已经占了 ``default="true"``，所以这两个新节点不带 default
    （一份 NFO 里只能有一个 default）。

    两个 id 都是 ``service`` 按片名+年份匹配回填的，常常为空 —— 空就不写，
    不写空节点（宁缺勿脏：空节点会被媒体服务器当成"有这个 id"）。
    """
    pairs = [
        ("tmdb", str(getattr(mediainfo, "tmdb_id", None) or "").strip()),
        ("douban", str(getattr(mediainfo, "douban_id", None) or "").strip()),
    ]
    pairs = [(tag, value) for tag, value in pairs if value]
    if not pairs:
        return text
    try:
        doc = minidom.parseString(text.encode("utf-8"))
    except Exception as err:  # pragma: no cover - 宿主产物理论合法
        logger.debug(f"{constants.SOURCE_NAME} NFO 外部 id 注入解析失败，保持原文：{err}")
        return text
    root = doc.documentElement
    for tag, value in pairs:
        if not _has_child(root, f"{tag}id"):
            legacy = doc.createElement(f"{tag}id")
            legacy.appendChild(doc.createTextNode(value))
            root.appendChild(legacy)
        if not _has_uniqueid(root, tag):
            unique = doc.createElement("uniqueid")
            unique.setAttribute("type", tag)
            unique.appendChild(doc.createTextNode(value))
            root.appendChild(unique)
    _strip_whitespace(doc.documentElement)
    return doc.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")


def _entry_season(mediainfo: Any) -> int:
    """词条自身的季号。

    ``to_host_media`` 从词条名派生（``隐身侍卫第二季`` → ``season=2``）；基名词条
    （站点把第 1 季存成不带后缀的原名）按第 1 季算。派生失败一律按 1。
    """
    try:
        return int(getattr(mediainfo, "season", None) or 1)
    except (TypeError, ValueError):
        return 1


_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def _image_ext(url: str) -> str:
    """海报地址的扩展名（白名单外回落 ``.jpg``，与宿主 ``_image_extension`` 同口径）。"""
    path = str(url).split("?", 1)[0].split("#", 1)[0]
    ext = os.path.splitext(path)[1].lower()
    return ext if ext in _IMAGE_EXTS else ".jpg"


def _season_image_name(season: int, url: str) -> str:
    """季海报文件名，TMDB 同款口径：``season02-poster.jpg``；第 0 季用 ``specials``。"""
    base = "season-specials-poster" if season <= 0 else f"season{season:02d}-poster"
    return f"{base}{_image_ext(url)}"


def build_nfo(
    mediainfo: Any,
    season: Optional[int] = None,
    episode: Optional[int] = None,
) -> Optional[str]:
    """按宿主契约生成 NFO 文本（剧级 / 季级 / 单集三种根节点）。

    :param mediainfo: 统一媒体信息（识别出口的 domain 版）
    :param season: 季号；有值走 helper 的 ``season`` 根（``seasonnumber``）
    :param episode: 集号；与 ``season`` 同有走 ``episodedetails`` 根（showtitle + 季集号）
    :return: NFO XML 文本；不是本来源、宿主没有通用刮削器或生成失败时返回 ``None``
    """
    if MediaScraperHelper is None or not is_own_media(mediainfo):
        return None
    try:
        text = MediaScraperHelper.get_metadata_nfo(mediainfo, season=season, episode=episode)
    except Exception as err:  # pragma: no cover - 宿主字段差异兜底
        logger.warning(f"{constants.SOURCE_NAME} 生成 NFO 失败：{err}")
        return None
    if not text:
        return None
    # 宿主 helper 带 encoding 调 toprettyxml；老版本可能给 bytes，契约要的是 str
    if isinstance(text, bytes):
        try:
            text = text.decode("utf-8")
        except UnicodeDecodeError:  # pragma: no cover - 理论不可达
            return None
    text = _annotate_actors(str(text), mediainfo)
    return _annotate_external_ids(text, mediainfo)


def build_images(
    mediainfo: Any,
    season: Optional[int] = None,
    episode: Optional[int] = None,
) -> Optional[Dict[str, str]]:
    """返回「文件名 → 图片地址」清单。

    * 非本来源返回 ``None``（让位给内置模块——只有 ``None`` 不会短路）；
    * ``episode`` 有值 → 空 dict：站点没有分集剧照，真实无素材；
    * ``season`` 有值 → ``season{NN}-poster{ext}``，取季词条自己的 ``poster_path``
      （词条季号与请求季号一致才出——基名词条被问第 2 季时不拿第一季海报充数）；
    * 剧级 → helper 的 ``poster``（+``backdrop`` 若有）。海报地址是图床完整 URL，
      零网络请求；宿主对 ``backdrop`` 会自动再写一份 ``fanart`` 别名。
    """
    if MediaScraperHelper is None or not is_own_media(mediainfo):
        return None
    if episode is not None:
        return {}
    if season is not None:
        if _entry_season(mediainfo) != season:
            return {}
        poster = str(getattr(mediainfo, "poster_path", None) or "").strip()
        if not poster:
            return {}
        return {_season_image_name(season, poster): poster}
    try:
        images = MediaScraperHelper.get_metadata_img(mediainfo)
    except Exception as err:  # pragma: no cover - 宿主字段差异兜底
        logger.warning(f"{constants.SOURCE_NAME} 生成图片清单失败：{err}")
        return {}
    return {
        str(name): str(url)
        for name, url in (images or {}).items()
        if name and url
    }
