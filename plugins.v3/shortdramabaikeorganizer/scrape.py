"""自包含刮削：素材向 djbaike 数据源直取，落盘自己写。

**关键约束（用户 2026-10-23）：既然整理自包含，刮削也自包含 —— 不走宿主刮削链。**

原方案是发 ``MetadataScrape`` 广播事件，让宿主 ``chain/scraping.py`` 去问数据源
出口再落盘。实测（2026-10-23）这条路代价很大：

* 广播事件是**异步派发**，接口返回时产物还没落盘，只能靠轮询等（为此还加过
  20 × 0.3s 的等待上限）；
* ``file_list`` 语义强耦合：为空时宿主从根递归，**拿不到 tvshow.nfo 与海报**；
  非空又会按名单逐文件刮削，而 djbaike 的 ``metadata_nfo`` 对 ``episode`` 有值
  一律返回 ``None``（数据源只做剧级），宿主仍写出 262 字节空壳 NFO —— 42 集就是
  42 个垃圾文件 + 约 42 秒开销。为了拿到 2 个想要的文件，得先塞 1 个无关文件
  去骗宿主走对分支。

而数据源的 ``metadata_nfo`` / ``metadata_img`` **本来就把素材给全了**：nfo 是成品
文本、图片是最终 URL。落盘就两个文件，没理由绕一大圈。

本模块只依赖标准库，与 ``organize.py`` 同款立场：素材来自数据源（唯一身份来源仍是
djbaike，不自己抓站），落盘由自己完成（同步、可控、产物确定）。

**写剧目录**（``tvshow.nfo`` + ``poster.jpg``）+ **写季目录**（``Season N/season.nfo``
+ ``Season N/season{N}-poster.<ext>``，2026-10-23 用户「季的刮削要存到季的目录下 /
季的图片在剧集里要显示，符合 emby 的剧文件结构」），不逐文件 —— 短剧没有分集元数据，
逐文件只会产出空壳。季级素材取不到时静默跳过，不影响剧级产物。
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from .constants import SCRAPE_IMAGE_EXTENSIONS

logger = logging.getLogger(__name__)

# 剧级 nfo 固定文件名（Kodi/Emby 惯例）
NFO_FILENAME: str = "tvshow.nfo"
# 季级 nfo 固定文件名（放在 Season NN 目录里，Emby/Kodi 都认）
SEASON_NFO_FILENAME: str = "season.nfo"


def poster_url(mediainfo: Any) -> str:
    """整理历史 ``image`` 列要的海报地址（**口径与宿主一致**）。

    宿主写整理历史时取的是 ``mediainfo.get_poster_image()``
    （``application/transfer/history.py``），我们照抄同一个出口，历史记录里
    这条就与系统自己整理出来的长一样。它返回空串时退回 ``poster_path``。

    注意 ``get_poster_image`` 会把 TMDB 路径里的 ``original`` 换成 ``w500``；
    短剧百科的图床地址不含 ``original``，原样返回，不会被改尺寸。
    """
    if mediainfo is None:
        return ""
    getter = getattr(mediainfo, "get_poster_image", None)
    if callable(getter):
        try:
            value = getter()
        except Exception:  # noqa: BLE001 - 宿主版本差异不该影响整理
            value = None
        if isinstance(value, str) and value.strip():
            return value.strip()
    return str(getattr(mediainfo, "poster_path", "") or "").strip()


def image_extension(url: str) -> str:
    """按 URL 后缀判定图片扩展名，白名单外回落 ``.jpg``（与宿主口径一致）。"""
    try:
        suffix = Path(urlparse(url).path).suffix.lower()
    except ValueError:
        return ".jpg"
    return suffix if suffix in SCRAPE_IMAGE_EXTENSIONS else ".jpg"


def image_filename(name: str, url: str) -> str:
    """图片落盘名。

    数据源 ``metadata_img`` 给的是 ``{key: URL}``，实测 key 是**已带扩展名的完整
    文件名**（``poster.jpg``）——宿主 helper 的 ``get_metadata_img`` 就是按文件名给的。
    带扩展名时直接用，不带时按 URL 后缀补一个（兼容只给类型名的形态）。
    """
    clean = Path(str(name).replace("\\", "/")).name
    if Path(clean).suffix.lower() in SCRAPE_IMAGE_EXTENSIONS:
        return clean
    return f"{clean}{image_extension(url)}"


def fetch_material(
    nfo_func: Optional[Any],
    img_func: Optional[Any],
    mediainfo: Any,
    *,
    season: int = 0,
) -> tuple[str, dict[str, str]]:
    """向数据源取素材：``(nfo 文本, {图片类型: URL})``。

    :param season: 0 = 取**剧级**素材（数据源要求 season/episode 为 None）；
        N = 按**季**取一次（一季一条词条，图是这一季自己的；数据源没上季出口
        时返回空，调用方静默跳过）。
    """
    season_arg = int(season) if season else None
    nfo_text = ""
    if callable(nfo_func):
        try:
            value = nfo_func(mediainfo=mediainfo, season=season_arg, episode=None)
            if isinstance(value, bytes):  # 老版本 helper 可能给 bytes
                value = value.decode("utf-8", errors="ignore")
            if value:
                nfo_text = str(value)
        except Exception as err:  # noqa: BLE001 - 数据源差异不该让整理失败
            logger.warning(f"[刮削] 取 NFO 素材失败：{err}")

    images: dict[str, str] = {}
    if callable(img_func):
        try:
            raw = img_func(mediainfo=mediainfo, season=season_arg, episode=None) or {}
            for name, url in dict(raw).items():
                name = str(name or "").strip()
                url = str(url or "").strip()
                if name and url:
                    images[name] = url
        except Exception as err:  # noqa: BLE001
            logger.warning(f"[刮削] 取图片清单失败：{err}")

    return nfo_text, images


def _fetch_image_bytes(url: str) -> tuple[Optional[bytes], Optional[str]]:
    """取图片字节：借宿主 ``ImageHelper.fetch_image``（进程内直调，唯一取图路径）。

    宿主取图自带各图床的 Referer（``img*.doubanio.com`` → ``movie.douban.com``，
    见 ``application/image.py:_get_request_params``）+ 磁盘缓存 + 重试 + 代理，
    覆盖豆瓣 / 短剧图床等；比插件自己按域名猜 Referer 全。

    **取不到就如实返回错误，不再自包含回退**（2026-10-23 用户要求：只借宿主）。

    :return: ``(bytes, error)``，成功时 ``error`` 为 ``None``。
    """
    try:
        from app.application.image import ImageHelper

        data = ImageHelper().fetch_image(url)
    except Exception as err:  # noqa: BLE001 - 取图失败如实上报，不阻断刮削主流程
        return None, str(err)
    if not data:
        return None, "宿主取图返回空"
    return bytes(data), None


def _download(url: str, target: Path) -> Optional[str]:
    """下载一张图到 ``target``（先写临时文件再 replace，不留半截文件）。

    取图只走宿主 ``ImageHelper``（见 :func:`_fetch_image_bytes`），不再回退。

    :return: 成功返回 ``None``，失败返回错误描述。
    """
    data, error = _fetch_image_bytes(url)
    if not data:
        return error or "取图失败（空响应）"
    tmp_path = Path(f"{target}.part")
    try:
        with open(tmp_path, "wb") as handle:
            handle.write(data)
        os.replace(str(tmp_path), str(target))
        return None
    except OSError as err:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        return str(err)


def write_metadata(
    dest_dir: Path | str,
    *,
    nfo_text: str = "",
    images: Optional[dict[str, str]] = None,
    overwrite: bool = False,
) -> dict:
    """把素材落到剧目录：``tvshow.nfo`` + 各类型图片。

    **只写剧目录本身**，不递归季目录、不逐文件。已存在的产物默认跳过
    （``overwrite=False``），避免覆盖 Emby 或人工改过的版本。

    :return: ``{"nfo": bool, "images": [...], "skipped": [...], "errors": [...]}``
    """
    dest = Path(dest_dir)
    result: dict = {"nfo": False, "images": [], "skipped": [], "errors": []}
    if not dest.is_dir():
        result["errors"].append(f"目标目录不存在：{dest}")
        return result

    # 1) 剧级 nfo
    if nfo_text:
        nfo_path = dest / NFO_FILENAME
        if nfo_path.exists() and not overwrite:
            result["skipped"].append(NFO_FILENAME)
        else:
            tmp = dest / f"{NFO_FILENAME}.part"
            try:
                tmp.write_text(nfo_text, encoding="utf-8")
                os.replace(str(tmp), str(nfo_path))
                result["nfo"] = True
            except OSError as err:
                result["errors"].append(f"写入 {NFO_FILENAME} 失败：{err}")
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass

    # 2) 图片（数据源给的是 {文件名: URL}，如 {"poster.jpg": "https://.../x.jpg"}）
    for name, url in (images or {}).items():
        filename = image_filename(name, url)
        target = dest / filename
        if target.exists() and not overwrite:
            result["skipped"].append(filename)
            continue
        error = _download(url, target)
        if error:
            result["errors"].append(f"下载 {filename} 失败：{error}")
        else:
            result["images"].append(filename)

    return result


def season_dir_name(season: int) -> str:
    """季目录名：``Season {N}`` —— **不补零**，必须与 :func:`naming.build_target_path`
    的季目录口径完全一致，否则季刮削产物会和整理的集文件分家成两个并列目录
    （2026-10-23 实测踩坑：`Season 02` 与 `Season 2` 并存）。"""
    return f"Season {max(1, min(99, int(season or 1)))}"


def _season_image_filename(season: int, name: str, url: str) -> str:
    """季图落盘名（Emby 剧集结构）：海报固定 ``season{N}-poster.<ext>``。

    数据源给的 key 若是 ``poster.jpg`` 一类通用名，改写成季专属名，Emby 才会在
    剧集页把这季的图认出来；其它类型（fanart / banner 等）保持原样落季目录。
    季号同样**不补零**（``season2-poster.jpg``），与 Season 目录名同口径。
    """
    filename = image_filename(name, url)
    stem = Path(filename).stem.lower()
    if stem.startswith("poster"):
        return f"season{max(1, min(99, int(season or 1)))}-poster{image_extension(url)}"
    return filename


def write_season_metadata(
    dest_dir: Path | str,
    season: int,
    *,
    nfo_text: str = "",
    images: Optional[dict[str, str]] = None,
    overwrite: bool = False,
) -> dict:
    """把**季级**素材落到 ``Season N`` 目录：``season.nfo`` + 季海报。

    结构对齐 Emby 的剧集库约定（季目录名与 :func:`naming.build_target_path`
    完全同源，都是 ``Season {N}`` 不补零，整理的集文件与季刮削产物同目录）：

    .. code-block:: text

        剧名 (年)/
          tvshow.nfo / poster.jpg        ← 剧级（write_metadata 负责）
          Season 2/
            season.nfo                   ← 季级元数据
            season2-poster.webp          ← 季海报（剧集页按季显示的图）
            剧名 - S02E01.mp4

    已存在的产物默认跳过（``overwrite=False``），与剧级同口径。

    :return: ``{"nfo": bool, "images": [...], "skipped": [...], "errors": [...]}``
    """
    dest = Path(dest_dir) / season_dir_name(season)
    result: dict = {"nfo": False, "images": [], "skipped": [], "errors": []}
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as err:
        result["errors"].append(f"创建季目录失败：{err}")
        return result

    # 1) 季级 nfo
    if nfo_text:
        nfo_path = dest / SEASON_NFO_FILENAME
        if nfo_path.exists() and not overwrite:
            result["skipped"].append(SEASON_NFO_FILENAME)
        else:
            tmp = dest / f"{SEASON_NFO_FILENAME}.part"
            try:
                tmp.write_text(nfo_text, encoding="utf-8")
                os.replace(str(tmp), str(nfo_path))
                result["nfo"] = True
            except OSError as err:
                result["errors"].append(f"写入 {SEASON_NFO_FILENAME} 失败：{err}")
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass

    # 2) 季级图片（海报改写为 season{NN}-poster.<ext>，其余保持原名）
    for name, url in (images or {}).items():
        filename = _season_image_filename(season, name, url)
        target = dest / filename
        if target.exists() and not overwrite:
            result["skipped"].append(filename)
            continue
        error = _download(url, target)
        if error:
            result["errors"].append(f"下载 {filename} 失败：{error}")
        else:
            result["images"].append(filename)

    return result
