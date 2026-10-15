"""短剧百科数据源 · 宿主刮削出口（NFO 文本与图片清单）。

宿主的刮削链（``chain/scraping.py`` 的 ``_scrape_nfo_generic`` /
``_scrape_images_generic``）在写盘前各问一次模块：
``run_module("metadata_nfo" | "metadata_img", …)``。这两个契约都是
``public_to_plugins=True`` + ``plugin_short_circuit=True`` + ``FIRST_NON_EMPTY``
（``runtime/extensions/module/contracts.py``）⇒ 调度器**先跑插件**，插件返回非空就
直接短路，宿主模块根本不会被问（``runtime/extensions/module/dispatcher.py`` 的
``_dispatch``）。

反向看：五个内置 NFO 生成器（themoviedb / douban / bangumi / anilist / imdb）第一句
都是「``mediainfo.scrape_source or SCRAP_SOURCE`` 必须等于自己的来源」，而整理与手动
刮削会把 ``scrape_source`` 设成**媒体来源**（``chain/transfer/execution.py``、
``api/endpoints/media.py``）⇒ 在本来源下它们**全部返回 None**，插件不实现就只会在
日志里留下「NFO 文件生成失败」，磁盘上什么也没有。

这里直接复用宿主**公开**的 :class:`app.domain.scraper.MediaScraperHelper`
（anilist / bangumi / imdb 三个内置来源就是同一个姿势）：字段取统一 ``MediaInfo``，
``uniqueid`` 写成本来源标识，图片清单取 ``poster_path`` / ``backdrop_path``。
换来源意味着换一套字段口径，自己拼 XML 只会越走越偏。

两个刻意的取舍
--------------

1. **只服务自己的来源**。插件的 provider 排在宿主模块之前，若不做身份判断，
   TMDB / 豆瓣 等来源的刮削会被本插件劫持。:func:`is_own_media` 是唯一闸门。
2. **不造分季 / 分集素材**。站点只有**剧级**海报与剧照，没有分季海报，更没有分集剧照
   ⇒ ``season`` / ``episode`` 一律返回空，让媒体服务器走自己的兜底显示；写一份
   「看起来有、其实不是」的文件比留空更脏。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .constants import MEDIA_SOURCE_ALIASES, MEDIA_SOURCE_KEY, PLUGIN_NAME

try:  # 宿主公开的通用刮削器（anilist / bangumi / imdb 也用它）
    from app.domain.scraper import MediaScraperHelper as _ScraperHelper
except Exception:  # pragma: no cover - 宿主版本差异兜底
    _ScraperHelper = None  # type: ignore[assignment]

try:
    from app.sdk.logging import logger
except Exception:  # pragma: no cover - 宿主版本差异兜底
    import logging

    logger = logging.getLogger('shortdramabaikesource')  # type: ignore[assignment]


__all__ = ["build_images", "build_nfo", "is_own_media"]


def is_own_media(mediainfo: Any) -> bool:
    """``mediainfo`` 是否由本插件提供身份（刮削 provider 的**唯一**准入条件）。"""
    if mediainfo is None:
        return False
    value = getattr(mediainfo, "media_source", None)
    if value is None:
        return False
    # ``MediaSource`` 是 str 枚举；插件来源是动态成员，取值统一走 ``value``
    text = str(getattr(value, "value", value)).strip().lower()
    return text in MEDIA_SOURCE_ALIASES or text == MEDIA_SOURCE_KEY


def build_nfo(
    mediainfo: Any,
    season: Optional[int] = None,
    episode: Optional[int] = None,
) -> Optional[str]:
    """按宿主契约生成 NFO 文本（``tvshow`` / ``season`` / ``episodedetails`` / ``movie``）。

    四种形态由 ``season`` / ``episode`` 的有无决定，与宿主其它来源一致：

    ==================  ====================
    入参                 根节点
    ==================  ====================
    两者都无             ``tvshow``（剧集根目录 ``tvshow.nfo``）
    只有 ``season``      ``season``（季目录 ``season.nfo``）
    ``season``+``episode`` ``episodedetails``（集文件同名 ``.nfo``）
    ==================  ====================

    ⚠️ 站点没有分集信息（每集只有集号），所以 ``episodedetails`` 里的标题 / 简介 /
    演员都取**剧级**数据 —— 短剧本来就是「一部剧一个故事」，这与它在站点上的组织方式一致。

    :return: NFO XML 文本；不是本来源的媒体、宿主没有通用刮削器或生成失败时返回 ``None``
    """
    if _ScraperHelper is None or not is_own_media(mediainfo):
        return None
    try:
        text = _ScraperHelper.get_metadata_nfo(
            mediainfo, season=season, episode=episode
        )
    except Exception as err:  # pragma: no cover - 宿主字段差异兜底
        logger.debug(f"{PLUGIN_NAME} 生成 NFO 失败：{err}")
        return None
    if not text:
        return None
    # 宿主那个 helper 带 encoding 调 toprettyxml，拿到的是 bytes；契约声明的是 str
    if isinstance(text, bytes):
        try:
            return text.decode("utf-8")
        except UnicodeDecodeError:  # pragma: no cover - 理论不可达
            return None
    return str(text)


def build_images(
    mediainfo: Any,
    season: Optional[int] = None,
    episode: Optional[int] = None,
) -> Dict[str, str]:
    """返回「文件名 → 图片地址」清单（媒体库根目录的 ``poster`` / ``backdrop``）。

    * ``season`` / ``episode`` 有值时返回空字典：站点没有分季 / 分集素材（见模块 docstring）；
    * 返回的键就是最终文件名（宿主按 ``filename_hint`` 决定落盘名与扩展名）。

    ⚠️ 图片扩展名取自地址后缀，站点用 ``.jpg``；宿主对 ``backdrop`` 会自动再写一份
    ``fanart`` 别名（``IMAGE_ALIASES``），不必在这里重复。
    """
    if _ScraperHelper is None or not is_own_media(mediainfo):
        return {}
    if season is not None or episode is not None:
        return {}
    try:
        images = _ScraperHelper.get_metadata_img(mediainfo)
    except Exception as err:  # pragma: no cover - 宿主字段差异兜底
        logger.debug(f"{PLUGIN_NAME} 生成图片清单失败：{err}")
        return {}
    return {
        str(name): str(url)
        for name, url in (images or {}).items()
        if name and url
    }
