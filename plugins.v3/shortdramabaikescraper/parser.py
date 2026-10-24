"""详情页解析：把百科页面转成结构化 dict（作品 / 原著）。

模板按实体分化（2026-10-21 实测）：

* ``duanju``：演员/角色、导演/编剧、剧情介绍、改编自同名小说；
* ``hema`` / ``huolong``：只有剧情介绍（无演员区块）→ 演员/导演按空处理；
* ``xiaoshuo``：剧情介绍 + 改编拍摄的系列短剧；
* 人物页（``yanyuan`` 等）走 P3，这里只按作品模板兜底。

可靠字段来源优先级：``meta description``（年份/集数/类型/评分/时长/平台热度最全）→
``<h1>``（权威剧名）→ 各 ``<h3>`` 区块（简介、演员、导演、原著）。
"""

from __future__ import annotations

import html as html_lib
import re
from typing import Optional

from . import classify, constants
from .harvest import attr_value
from .media_id import (
    detail_url,
    entity_of,
    image_url,
    kind_from_tags,
    kind_of,
    media_id_of,
)


def _text(raw: str) -> str:
    """去标签 + 反转义 + 折叠空白。"""
    plain = re.sub(r"<[^>]+>", "", raw or "")
    return re.sub(r"\s+", " ", html_lib.unescape(plain)).strip()


def _region(html: str, start: str, ends: tuple[str, ...]) -> str:
    """截取 ``start`` 之后、最近一个 ``ends`` 之前的片段。"""
    begin = html.find(start)
    if begin < 0:
        return ""
    end = len(html)
    for marker in ends:
        idx = html.find(marker, begin + len(start))
        if 0 <= idx < end:
            end = idx
    return html[begin:end]


def _cards(region: str) -> list[dict]:
    """从卡片区块抽 ``[{media_id, name, role}]``。"""
    cards: list[dict] = []
    for chunk in region.split("<a ")[1:]:
        href = attr_value(chunk, "href")
        if "info-" not in href:
            continue
        entity = href.partition("/info-")[0].strip("/").split("/")[-1]
        native_id = href.partition("/info-")[2].split(".html")[0]
        raw_name = attr_value(chunk, "alt")
        role_hint = ""
        for prefix in ("演员：", "编剧：", "导演：", "演员:", "导演:", "编剧:"):
            if raw_name.startswith(prefix):
                role_hint = prefix.rstrip(":：")
                raw_name = raw_name[len(prefix) :]
                break
        if not raw_name:
            raw_name = _text(chunk.split("<div", 2)[1]) if "<div" in chunk else ""
        role = ""
        mark = chunk.find("饰 ")
        if mark >= 0:
            role = _text(chunk[mark + 2 :].split("<", 1)[0])
        cards.append(
            {
                "media_id": media_id_of(entity, native_id),
                "name": _text(raw_name),
                "role": role or role_hint,
            }
        )
    return cards


def _adapt_cards(region: str) -> list[dict]:
    """从「改编拍摄的系列短剧」区块抽 ``[{media_id, name, kind, date, episodes}]``。

    与 `_cards` 的差异：作品卡的名字在 ``title="短剧《…》"`` / ``alt="…海报"`` 里，
    且角标带上线日期（``2026-02-06``）与总集数（``全 75 集``）——这两样正是
    原著档案的改编清单要展示的。
    """
    cards: list[dict] = []
    seen: set[str] = set()
    for chunk in region.split("<a ")[1:]:
        href = attr_value(chunk, "href")
        if "info-" not in href:
            continue
        entity = href.partition("/info-")[0].strip("/").split("/")[-1]
        native_id = href.partition("/info-")[2].split(".html")[0]
        media_id = media_id_of(entity, native_id)
        if not media_id or media_id in seen:
            continue
        seen.add(media_id)
        raw_name = attr_value(chunk, "title") or attr_value(chunk, "alt")
        # 「短剧《雪落时逢你》」「短剧《X》海报」→ 剥壳取书名号内的名字
        match = re.search(r"《([^》]+)》", raw_name or "")
        name = match.group(1).strip() if match else _text(raw_name)
        date = _fact(r"(20\d{2}-\d{2}-\d{2})", chunk)
        episodes = _first_int(r"全\s*(\d+)\s*集", chunk)
        cards.append(
            {
                "media_id": media_id,
                "name": name,
                "kind": kind_of(media_id) or "短剧",
                "date": date,
                "episodes": episodes or 0,
            }
        )
    return cards


def _fact(pattern: str, desc: str, group: int = 1) -> str:
    match = re.search(pattern, desc)
    return match.group(group).strip() if match else ""


def _first_int(pattern: str, desc: str) -> Optional[int]:
    raw = _fact(pattern, desc)
    return int(raw) if raw.isdigit() else None


def parse_detail(media_id: str, html: str) -> Optional[dict]:
    """解析作品/原著详情页；拿不到 ``<h1>`` 视为无效页，返回 ``None``。"""
    if not media_id or not html:
        return None
    # 只解析百科八类实体页；豆瓣前缀（douban/doubanp）走豆瓣通道，不归本解析器
    if entity_of(media_id) not in constants.ENTITY_ALL:
        return None
    h1 = re.search(r"<h1[^>]*>(.{0,500}?)</h1>", html, re.S)
    name = _text(h1.group(1)) if h1 else ""
    if not name:
        return None

    title_tag = _text((re.search(r"<title>(.{0,500}?)</title>", html, re.S) or [None, ""])[1])
    desc = _text((re.search(r'<meta name="description" content="(.{0,1000}?)"', html, re.S) or [None, ""])[1])
    entity = entity_of(media_id)

    # 类型标签：``短剧类型为爱情、都市爱情、…``
    tags_raw = _fact(r"类型为([^，。]+)", desc)
    tags = [tag for tag in re.split(r"[、,，]", tags_raw) if tag]
    if entity in constants.ENTITY_NOVEL:
        kind = "原著"
    elif any("漫" in tag for tag in tags):
        kind = "漫剧"
    elif "漫剧" in title_tag:
        kind = "漫剧"
    elif tags or "短剧" in title_tag:
        kind = "短剧"
    else:
        kind = kind_from_tags(tags) if tags else (kind_of(media_id) or "短剧")

    # 简介
    intro = _region(html, "剧情介绍：", ("改编自同名小说", "改编拍摄的系列短剧", "<h3", "新剧排行榜"))
    overview = ""
    if intro:
        block = intro.split('class="pt-2"', 1)
        if len(block) == 2:
            overview = _text(block[1].split("</div>", 1)[0])
        if not overview:
            overview = _text(intro.split("</h3>", 1)[-1])[:800]
    overview = overview.lstrip(">").strip()

    # 演员 / 导演编剧（hema / huolong 没有这两块）
    actors = _cards(_region(html, "演员/角色", ("导演/编剧", "剧情介绍", "新剧排行榜")))
    staff = _cards(_region(html, "导演/编剧", ("剧情介绍", "新剧排行榜")))

    # 原著链接
    novel = None
    novel_pos = html.find('href="/xiaoshuo/info-')
    if novel_pos >= 0:
        chunk = html[novel_pos : novel_pos + 600]
        href = attr_value(chunk, "href")
        native_id = href.partition("/info-")[2].split(".html")[0]
        novel_name = attr_value(chunk, "alt")
        for prefix in ("小说：", "小说《", "原著："):
            if novel_name.startswith(prefix):
                novel_name = novel_name[len(prefix) :]
        novel = {
            "media_id": media_id_of("xiaoshuo", native_id),
            "name": _text(novel_name).rstrip("》"),
        }

    # 原著页专属：改编拍摄的系列短剧（作品页没有这个区块，得到空列表）
    adaptations = _adapt_cards(_region(html, "改编拍摄的系列短剧", ("新剧排行榜", "<h3")))

    episodes = _first_int(r"(\d+)集", desc) or _first_int(r"已更新至(\d+)集", desc)

    # 站内热度 / 播放 / 收藏：**一律保留站点原串**（``383.37万``、``989万``、``1.32万``），
    # 折算成数字反而会丢掉量级感、也无法区分「站内写的」与「我们算的」。
    # 正则都要吃「万 / 亿」两种后缀（``3.2亿播放量`` 曾因只写 ``万?`` 整条抓不到）。
    duration_raw = _fact(r"时长为([^，。]+)", desc)
    platform = _fact(r"在([^，。]{2,20}?)上目前已有", desc)
    heat_raw = _fact(r"目前已有([^，。]+?)热度", desc)
    play_raw = _fact(r"([\d.]+\s*[万亿]?)播放量", desc)
    favorite_raw = _fact(r"([\d.]+\s*[万亿]?)人收藏", desc)

    detail = {
        "media_id": media_id,
        "name": name,
        "kind": kind,
        "year": _first_int(r"(20\d{2})年", desc),
        "episodes": episodes,
        "overview": overview,
        "tags": tags,
        "actors": actors,
        "directors": [item for item in staff if item["name"]],
        "rating": float(_fact(r"评分为([\d.]+)分", desc) or 0) or None,
        "duration": duration_raw,
        "release_date": _fact(r"上线播出时间为([^，。]+)", desc),
        "platform": platform,
        "platform_heat": heat_raw,
        "play_count": play_raw,
        "favorite_count": favorite_raw,
        "novel": novel,
        # 原著页专属（作品页为空串/None，不影响其它逻辑）
        "adaptations": adaptations,
        "author": _fact(r"作者：([^，。]+)", desc),
        "aka": _fact(r"又名：《([^》]+)》", desc),
        "words": _fact(r"已更新([\d.]+ ?万字?)", desc),
        "poster_path": image_url(media_id),
        "detail_url": detail_url(media_id),
        "desc": desc,
    }
    return detail


def detail_to_media_info(detail: dict):
    """详情 dict → 宿主 ``MediaInfo``（识别出口）。

    宿主的 ``actors`` 要 ``MediaCredit``、``genres`` 要 ``MediaGenre``，直接塞
    字符串/dict 会触发 pydantic 校验错误（实测 7 条 validation errors）。
    """
    from app.schemas import MediaInfo
    from app.schemas.context import MediaCompany, MediaCredit, MediaGenre
    from app.schemas.types import MediaSource, MediaType

    source = MediaSource(constants.MEDIA_SOURCE_ID)
    actors = []
    for item in detail.get("actors", []):
        if not item.get("name"):
            continue
        actors.append(
            MediaCredit(
                name=item["name"],
                character=item.get("role") or None,
                url=detail_url(item.get("media_id", "")) or None,
                # 头像：站点演员卡给的是「百度 gimg 中转 + 自家图床源」，两种都不必
                # 抓页面 —— 图床模板对人物实体同样成立（``yanyuan/<id>.jpg``，实测
                # 200 / 22KB），按身份反推即得。不传的话宿主 ``MediaInfo.actors``
                # 里压根没有头像字段，下游详情页只能出人形占位。
                profile_path=image_url(item.get("media_id", "")) or None,
            )
        )
    directors = []
    for item in detail.get("directors", []):
        if not item.get("name"):
            continue
        directors.append(
            MediaCredit(
                name=item["name"],
                job=item.get("role") or "导演",
                url=detail_url(item.get("media_id", "")) or None,
                # 头像同演员：站点「导演/编剧」区块的卡片也是 ``<img src=…yanyuan|daoyan|bianju/<id>.jpg>``，
                # 图床模板按身份反推即得，零请求。
                profile_path=image_url(item.get("media_id", "")) or None,
            )
        )
    genres = [MediaGenre(id=0, name=tag) for tag in detail.get("tags", []) if tag]

    # 热度 / 播放 / 收藏**不进 MediaInfo**：宿主的 ``popularity`` 是数值字段，装不了
    # ``383.37万`` 这种原串，硬折算又会丢量级。它们由 ``classify.facts_for`` 以
    # ``extensions.djbaike.heat / play_count / favorite_count`` 原样提交（见该模块）。

    # 平台 → 宿主流媒体平台（``MediaCompany``）；站点只给名字，id 留空。
    platform = str(detail.get("platform") or "").strip()
    networks = [MediaCompany(name=platform)] if platform else None

    info = MediaInfo(
        type=MediaType.TV.value,
        title=detail.get("name", ""),
        original_title=detail.get("name", ""),
        media_source=source,
        media_id=detail.get("media_id", ""),
        year=str(detail["year"]) if detail.get("year") else None,
        number_of_episodes=detail.get("episodes") or 0,
        overview=detail.get("overview", ""),
        genres=genres or None,
        actors=actors or None,
        directors=directors or None,
        poster_path=detail.get("poster_path") or None,
        vote_average=detail.get("rating") or 0.0,
        # 上线时间 / 平台：宿主都有标准坑位，不能只留在 detail dict 里
        # （``hostmedia.to_host_media`` 只搬白名单字段，漏传等于识别结果里没有）
        release_date=str(detail.get("release_date") or "") or None,
        networks=networks,
        # 两个外部 id 都是 `service` 回填的（站点页面本身没有这两个字段）：
        # 豆瓣走站内搜索 + 豆瓣，`_fill_tmdb_id` 经宿主 TMDB 通道按片名+年份匹配。
        # 查不到时回填的是 "" 占位（让缓存命中路径不再重复搜），这里一律当没有。
        # 挂上去只有一个目的：让 NFO 能带上外部 id（注入见 scrape.py）。
        douban_id=str(detail["douban_id"]) if detail.get("douban_id") else None,
        tmdb_id=int(detail["tmdb_id"]) if str(detail.get("tmdb_id") or "").isdigit() else None,
        detail_link=detail.get("detail_url", ""),
    )
    # 来源专有分类事实（extensions.djbaike.kind = 短剧/漫剧）：让自动分类规则
    # 不依赖 identity.media_source（那个会被 TMDB 重识别覆盖）。
    # 播放量 / 收藏数宿主没有标准字段，也在这层挂成事实，不让解析结果白丢。
    return classify.attach(info, detail=detail)


# ── 人物页（P3 第一步：档案 + 作品清单；豆瓣融合仍留后续） ─────────────
#
# 三类页面（``/yanyuan/``、``/daoyan/``、``/bianju/``）同构，字段与区块位置一致
# （见 ``docs/sources/短剧百科-页面结构分析.md`` §5）。站点**没有**出生日期/地区/
# 身高这类结构化字段，所以这里只给：姓名、身份文案、头像、介绍正文、作品清单。

_PERSON_ROLE_HINT = {"yanyuan": "演员", "daoyan": "导演", "bianju": "编剧"}
# 左栏 H1 下面那一行身份文案：``导演`` / ``编剧`` / ``女演员`` / ``男演员``
_PERSON_ROLE_RE = re.compile(r"<p[^>]*>\s*(男演员|女演员|导演|编剧|演员)\s*</p>")
# 作品卡底部两行（第一行演员表、第二行分类标签），都不含角色名
_LINE_CLAMP_RE = re.compile(r'line-clamp-1[^"]*"[^>]*>(.{0,1000}?)</div>', re.S)
_WORK_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_WORK_EPS_RE = re.compile(r"全\s*(\d+)\s*集")


def _split_slash(text: str) -> list[str]:
    """``查祎琛 / 陈瑞丰`` → ``['查祎琛', '陈瑞丰']``。"""
    return [part.strip() for part in re.split(r"\s*/\s*", text or "") if part.strip()]


def parse_person_works(html: str) -> list[dict]:
    """人物页作品卡 → ``[{media_id, name, date, episodes, actors, tags}]``。

    只收 ``duanju/manju/hema/huolong`` 前缀、且卡里带 ``title="短剧《X》"`` 的链接：
    APP 推广块、侧栏推荐都没有这个特征。按 ``media_id`` 去重，保持页面原顺序
    （站点已按上线日期倒序）。

    一张卡比列表页多两行信息（完整演员表 + 分类标签），所以这里一并取出来 ——
    做「某演员参演的剧」补全时能直接用，不必再抓每部剧的详情页。
    """
    works: list[dict] = []
    seen: set[str] = set()
    for chunk in (html or "").split("<a ")[1:]:
        href = attr_value(chunk, "href")
        if "/info-" not in href:
            continue
        entity = href.partition("/info-")[0].strip("/").split("/")[-1]
        if entity not in constants.ENTITY_DRAMA:
            continue
        media_id = media_id_of(entity, href.partition("/info-")[2].split(".html")[0])
        if not media_id or media_id in seen:
            continue
        seen.add(media_id)

        name = ""
        title_attr = attr_value(chunk, "title")
        found = re.search(r"《(.{1,300}?)》", title_attr or "")
        if found:
            name = _text(found.group(1))
        if not name:
            heading = re.search(r'class="[^"]*text-lg[^"]*"[^>]*>(.{0,1000}?)</div>', chunk, re.S)
            name = _text(heading.group(1)) if heading else ""

        # 集数在演员页上是 ``全\n&nbsp;&nbsp;73 集``，正则里的 \s 已够用
        date_hit = _WORK_DATE_RE.search(chunk)
        eps_hit = _WORK_EPS_RE.search(chunk)
        lines = [_text(item) for item in _LINE_CLAMP_RE.findall(chunk)]
        works.append(
            {
                "media_id": media_id,
                "name": name,
                "kind": constants.KIND_OF_ENTITY.get(entity, ""),
                "poster": image_url(media_id) or "",
                "date": date_hit.group(0) if date_hit else "",
                "episodes": int(eps_hit.group(1)) if eps_hit else 0,
                "actors": _split_slash(lines[0]) if lines else [],
                "tags": _split_slash(lines[1]) if len(lines) > 1 else [],
            }
        )
    return works


def parse_person(media_id: str, html: str) -> Optional[dict]:
    """解析人物页；无 ``<h1>``（软 404 空壳）返回 ``None``。"""
    entity = entity_of(media_id)
    if entity not in constants.ENTITY_PERSON or not html:
        return None
    h1 = re.search(r"<h1[^>]*>(.{0,500}?)</h1>", html, re.S)
    name = _text(h1.group(1)) if h1 else ""
    if not name:
        return None

    role = ""
    if h1:
        # 身份文案就在 H1 后面几百字节内（左栏那一行），不必全文找
        window = html[h1.end() : h1.end() + 800]
        hit = _PERSON_ROLE_RE.search(window)
        if hit:
            role = hit.group(1)
    if not role:
        role = _PERSON_ROLE_HINT.get(entity, "人物")

    intro = ""
    for pattern in (
        r"<h3[^>]*>[^<]{0,80}介绍：</h3>\s*<div[^>]*>(.{0,5000}?)</div>",
        r"<h3[^>]*>[^<]{0,80}(?:介绍|简介)[^<]{0,20}</h3>\s*<div[^>]*>(.{0,5000}?)</div>",
    ):
        hit = re.search(pattern, html, re.S)
        if hit:
            intro = _text(hit.group(1))
            break

    works = parse_person_works(html)
    return {
        "media_id": media_id,
        "name": name,
        "role": role,
        "kind": role,
        "avatar": image_url(media_id) or "",
        "intro": intro,
        "works": works,
        "work_count": len(works),
        "detail_url": detail_url(media_id),
    }
