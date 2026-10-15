"""短剧百科数据源 · 页面解析层。

纯函数：吃 HTML（或引擎结果行），吐字典；**不碰宿主、不碰网络、不碰数据库**，
所以可以拿真实页面夹具直接单测。

字段口径：页面里凡是能稳定拿到的都解析出来 —— JSON-LD 优先（语言无关、跨版本稳），
HTML 兜底与补缺（阵容、剧照、评分、播放/收藏/热度、角标、推荐位这些 JSON-LD 里
根本没有的只能从 HTML 取）。
"""
from __future__ import annotations

import html as _html
import json
import re
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

from .constants import (
    ACTOR_ID_PREFIX,
    ACTOR_PATH,
    EPISODE_CN_RE,
    FILENAME_EDGE_SEPARATOR_RE,
    LANG_PATH,
    ORG_DEFAULT_DOMAIN,
    SEASON_EPISODE_RE,
    SEASON_ONLY_RE,
    VIDEO_EXT_RE,
    WEB_INDEX_ACTOR_RE,
    WEB_INDEX_DETAIL_RE,
    WEB_INDEX_GALLERY_RE,
    WEB_INDEX_HOST_SUFFIX_RE,
    WEB_INDEX_TITLE_SUFFIX_RE,
)

__all__ = [
    "_clean",
    "_strip_tags",
    "_has_value",
    "_normalize_image",
    "_parse_int",
    "_parse_year",
    "_parse_wannum",
    "_parse_duration_minutes",
    "_normalize_title",
    "_match_title",
    "_strip_org_suffix",
    "video_name_of",
    "web_index_native_id",
    "web_index_actor_id",
    "canonical_page_url",
    "href_points_to_simplified",
    "parse_org_cards",
    "parse_org_detail",
    "parse_org_actor",
    "parse_org_cast",
    "parse_org_gallery",
    "is_cloudflare_challenge",
]


# ── 通用小工具 ────────────────────────────────────────────────────


def _clean(text: Any) -> str:
    """折叠空白并做 HTML 反转义；非字符串一律转成空串。"""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    return _html.unescape(re.sub(r"\s+", " ", text)).strip()


def _strip_tags(text: Any) -> str:
    if not isinstance(text, str):
        return _clean(text)
    return _clean(re.sub(r"<[^>]+>", " ", text))


def _has_value(value: Any) -> bool:
    """合并详情时用：空串 / 空集合 / None 都算「没值」，不该覆盖已有字段。"""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)
    return True


def _normalize_image(src: str) -> str:
    src = _clean(src)
    if not src:
        return ""
    if src.startswith("//"):
        return f"https:{src}"
    return src


def _parse_int(value: Any) -> Optional[int]:
    match = re.search(r"\d+", str(value or ""))
    return int(match.group(0)) if match else None


def _parse_year(value: Any) -> Optional[str]:
    match = re.search(r"(19|20)\d{2}", str(value or ""))
    return match.group(0) if match else None


def _parse_wannum(value: Any) -> Optional[float]:
    """把「965 万」这类带单位的计数还原成绝对值。

    站点在播放量一类的大数上会用**千分位**（``1,029``），所以先把逗号去掉再取数 ——
    否则正则只会匹配到第一个数字段，``1,029`` 会静默变成 ``1``。
    """
    text = _clean(value).replace(",", "")
    if not text:
        return None
    number = re.search(r"\d+(?:\.\d+)?", text)
    if not number:
        return None
    amount = float(number.group(0))
    if "亿" in text:
        amount *= 100000000
    elif "万" in text:
        amount *= 10000
    return amount


def _parse_duration_minutes(value: Any) -> Optional[int]:
    text = _clean(value)
    if not text:
        return None
    iso = re.fullmatch(
        r"P(?:(?P<days>\d+)D)?T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?",
        text,
    )
    if iso:
        days = int(iso.group("days") or 0)
        hours = int(iso.group("hours") or 0)
        minutes = int(iso.group("minutes") or 0)
        seconds = int(iso.group("seconds") or 0)
        total = days * 1440 + hours * 60 + minutes + (1 if seconds >= 30 else 0)
        return total or None
    hours = re.search(r"(\d+)\s*小时", text)
    minutes = re.search(r"(\d+)\s*分", text)
    if hours or minutes:
        return int(hours.group(1) if hours else 0) * 60 + int(minutes.group(1) if minutes else 0)
    return None


def _normalize_title(title: str) -> str:
    text = _clean(title)
    text = text.replace("《", "").replace("》", "")
    text = re.sub(r"\s+", "", text)
    text = "".join(
        chr(ord(char) - 0xFEE0) if "\uFF01" <= char <= "\uFF5E" else char for char in text
    )
    return text.casefold()


def video_name_of(text: Any) -> str:
    """把带「文件名味」的字符串还原成能拿去检索的片名。

    宿主把**整个文件名**原样塞进 ``MetaInfo.title``（容器内实测
    ``MetaInfo('雾锁情迷 - S01E71.mp4')`` → ``title = '雾锁情迷 - S01E71.mp4'``、
    ``name = '雾锁情迷'``）。这种脏串无论拿去问搜索引擎、去 URL 库 `match`、
    还是当检索节流的键，都必然落空 —— 库里存着的「雾锁情迷」永远查不回来。

    逐个**剥到不变为止**：扩展名 → ``S01E71`` → ``S01`` → ``第71集``，最后修掉
    残留的首尾分隔符。只认明确的文件级噪音，不去动正常片名里的字。
    """
    value = _clean(text)
    if not value:
        return ""
    while True:
        stripped = SEASON_EPISODE_RE.sub("", VIDEO_EXT_RE.sub("", value))
        stripped = EPISODE_CN_RE.sub("", SEASON_ONLY_RE.sub("", stripped))
        stripped = _clean(FILENAME_EDGE_SEPARATOR_RE.sub("", stripped))
        if stripped == value:
            return value
        if not stripped:
            # 全是噪音（``S01E71.mp4``）：宁可把原文交回去，上层还能按原文再试一次
            return value
        value = stripped


def _match_title(candidate: str, target: str) -> int:
    """给候选片名与目标片名的接近程度打分（越大越像），0 表示不相关。

    短剧站常见的召回缺口是「站点加了前后缀」（我的闪婚老公是豪门 vs 闪婚老公是豪门），
    所以包含关系也给分，但精确相等得分最高。
    """
    left, right = _normalize_title(candidate), _normalize_title(target)
    if not left or not right:
        return 0
    if left == right:
        return 100
    if left in right or right in left:
        return 60
    # 去掉季/部/集数等尾缀后再比一次
    trimmed = re.sub(r"(第[一二三四五六七八九十\d]+[季部]|全\d+集)$", "", right)
    if trimmed and trimmed != right and (left in trimmed or trimmed in left):
        return 40
    return 0


def _strip_org_suffix(title: str) -> str:
    """剥掉搜索引擎结果标题里的站点后缀与裸域名。

    实测四种形态（作品页 / 演员页 / 图集页 / 目录页各一种，详见
    ``constants.WEB_INDEX_TITLE_SUFFIX_RE``）::

        万妖图录传第七季 - 短剧 - 短剧百科        → 万妖图录传第七季
        魏依珂 - 短劇演員 - 短劇百科              → 魏依珂
        相亲对象是迟来的心动 - 剧照 - 短剧百科     → 相亲对象是迟来的心动
        魏珂 - 短劇演員 - 短劇百科 - duanjubaike.org → 魏珂

    两类后缀**交替剥到不变为止**：它们的出现顺序不固定（域名可能在前也可能在后）。
    """
    text = _clean(title)
    while True:
        stripped = WEB_INDEX_HOST_SUFFIX_RE.sub("", WEB_INDEX_TITLE_SUFFIX_RE.sub("", text)).strip()
        if stripped == text:
            return text
        text = stripped


def web_index_native_id(url: str, host: str) -> str:
    """从搜索引擎结果里的 URL 取作品 ID；不是本域的详情页 / 图集页一律返回空串。

    结果里混着演员页（``/actor/371``）与榜单页，它们都拿不到作品 ID —— 用「路径恰好是
    ``/drama/<数字>``」这一条把它们筛掉。

    ⚠️ **图集页（``/drama/<数字>/photos``）必须接住**：它是详情页的子路径、ID 完全一致，
    而引擎常常**只索引到图集页**。实测（2026-10-15）搜「难驯」返回 7 条，全是别的剧
    （重生难驯 / 野性难驯 / 他难驯）加上一条 ``/zh-Hans/drama/17139/photos``
    （标题「难驯 - 剧照 - 短剧百科」）—— 以前把这条当「图集页」剔掉，17139 就永远搜不到。
    """
    return (
        _web_index_id(url, host, WEB_INDEX_DETAIL_RE)
        or _web_index_id(url, host, WEB_INDEX_GALLERY_RE)
    )


def web_index_actor_id(url: str, host: str) -> str:
    return _web_index_id(url, host, WEB_INDEX_ACTOR_RE)


def _web_index_id(url: str, host: str, pattern: Any) -> str:
    """本域 + 路径形态都对上时取出末尾的数字 ID，否则空串。

    :param url: 搜索引擎结果里的地址
    :param host: 本域主机名（空表示不校验域名）
    :param pattern: 路径正则（``/drama/<id>`` 或 ``/actor/<id>``）
    """
    try:
        parsed = urllib.parse.urlparse(_clean(url))
    except Exception:  # pragma: no cover - 地址异常按非目标页处理
        return ""
    netloc = (parsed.netloc or "").lower()
    host = _clean(host).lower()
    if host and not (netloc == host or netloc.endswith("." + host)):
        return ""
    match = pattern.match(parsed.path or "")
    return match.group("id") if match else ""


# 页面路径形态：``/drama/<数字>`` / ``/actor/<数字>``，**语言前缀可有可无、可以是任何语言**
# （``/actor/371``、``/zh-Hant/actor/371`` 都得接住 —— 实测引擎两种都会给）。
# 末尾的 ``/photos``（图集页）一并吃下：它是详情页的子路径，归一化掉才是能抓的地址。
_PAGE_ANY_LANG_RE = re.compile(
    r"^/(?:[A-Za-z][A-Za-z-]{0,11}/)?(?P<kind>drama|actor)/(?P<id>\d+)(?:/photos)?/?$"
)


def canonical_page_url(url: str, domain: str = ORG_DEFAULT_DOMAIN) -> str:
    """把站点页面地址的**语言前缀归一化成** ``/zh-Hans``；其余部分原样保留。

    ⚠️ 这**不是**「按 ID 反拼地址」—— 路径形态（``/drama/`` 还是 ``/actor/``）与 ID
    仍然完全来自页面 / 引擎给的那条 URL，这里只把一个必须成立的前提写死：**站点只抓简体**。

    唯一的例外是**图集页**：``…/drama/17139/photos`` 会被归一化成 ``…/drama/17139``。
    它是详情页的子路径（同一个作品的 ID），却**不是**能抓的详情页地址；引擎在「详情页没被
    索引、只索引了图集页」时给的就是它（见 :func:`web_index_native_id`），照抄原址入库
    会拿图集页当详情页解析。

    实测（2026-10-15）：``/actor/371``、``/drama/22049``、``/zh-Hant/actor/24243`` 三种写法
    都会被 301 到 **繁体** 页面，而繁体页里

    1. 作品链接写成 ``/zh-Hant/drama/…`` ⇒ 卡片正则（只认 ``/zh-Hans``）静默解析出 **0 部作品**；
    2. 统计标签是「熱度 / 評分」⇒ 简体正则匹配不到，``heat`` 恒为 ``null``。

    两种症状都**不报错**，极难发现 —— 所以抓取与入库一律先过这一步。
    不是站点页面地址（榜单页、外域、图片 CDN 等）时**原样返回**，由调用方另行筛掉。
    """
    text = _clean(url)
    if not text:
        return ""
    try:
        parsed = urllib.parse.urlparse(text)
    except Exception:  # pragma: no cover - 地址异常按原样返回
        return text
    match = _PAGE_ANY_LANG_RE.match(parsed.path or "")
    if not match:
        return text
    base = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else _clean(domain).rstrip("/")
    return f"{base or ORG_DEFAULT_DOMAIN}{LANG_PATH}/{match.group('kind')}/{match.group('id')}"


def href_points_to_simplified(url: str) -> bool:
    """这个地址是不是**直接**指向简体页（``/zh-Hans/...``）。

    ⚠️ 这不是「地址能不能用」—— 用不了也得归一化成简体（见 :func:`canonical_page_url`）。
    它回答的是另一个问题：**引擎给的那条标题可不可信。**

    实测引擎会用三种写法回同一个作品：``/zh-Hans/drama/40354``、``/zh-Hant/drama/40445``、
    ``/drama/22049``（后两种都会被站点 301 到**繁体**页）。前者的标题是简体
    （``相亲对象是迟来的心动``），后两者是繁体（``相親對象是遲來的心動``）——
    拿繁体标题跟用户输入的简体关键词比对必然对不上，会被当成无关候选丢掉。
    所以发现阶段据此判断「需要抓一次简体页把标题换掉」。
    """
    try:
        path = urllib.parse.urlparse(_clean(url)).path or ""
    except Exception:  # pragma: no cover - 地址异常按不可信处理
        return False
    return path.startswith(LANG_PATH + "/")


# ── ``.org`` 卡片解析（目录页 / 精选页 / 榜单页通用） ────────────────

# 作品卡链接。三种版式的 href 形态一致，但标题与封面位置不同：
#   目录页/精选页  <a href="…/zh-Hans/drama/61824" class="relative block …">
#                      <img … alt="片名" src="封面">…</a>
#   榜单页        <a href="…/zh-Hans/drama/37512" class="hover:text-orange-600">片名</a>
#                  —— 标题是**锚文本**，封面 <img> 在**兄弟节点**（锚之前）
# 所以 id 一律从 href 取，标题与封面按「锚内优先、锚外兜底」两级取。
_ORG_CARD_RE = re.compile(
    r'<a\b[^>]*href="(?:https?://[^"]*?)?/zh-Hans/drama/(?P<id>\d+)"[^>]*>(?P<body>.*?)</a>',
    re.S,
)
_ORG_CARD_ALT_RE = re.compile(r'alt="(?P<alt>[^"]*)"')
_ORG_CARD_SRC_RE = re.compile(r'src="(?P<src>[^"]+)"')
_ORG_IMG_RE = re.compile(r'<img\b[^>]*src="(?P<src>[^"]+)"', re.S)

# ⚠️ 目录页 / 精选页的**每一部作品有两个锚**（海报锚 + 标题锚），而字段分散在两处：
#   海报锚内   封面 <img alt/src>、评分、系列季、集数
#   标题锚前后 真人/AI 角标、热度/播放、标签
# 所以必须按「卡片外壳」整块切，**不能**按「下一个锚」切 —— 那样会在标题锚处截断，
# 真人/AI、热度、标签三组字段会整段丢掉（实测过的静默失效）。
_ORG_CARD_BLOCK_MARK = (
    '<div class="bg-gray-50 dark:bg-gray-700 rounded-xl overflow-hidden '
    'border border-gray-200 dark:border-gray-600">'
)
_ORG_CARD_SPAN = 5000

# ── 卡片内的可选字段（站点在不同版式下渲染的字段并不一致，取不到就整条不带） ──
# 真人 / AI 角标：标题前那个带 title 的小胶囊
_ORG_KIND_RE = re.compile(r'<span class="inline-flex[^"]*"\s+title="(?P<kind>[^"]+)"')
# 状态角标（爆火 / 新剧 …）：海报左上角的胶囊。底色随语义变（目录页红＝爆火、
# 精选页绿＝新剧），所以颜色位用通配，靠 `text-white text-xs px-2 py-1 rounded-full`
# 这串固定的排版类锁定它。
_ORG_BADGE_RE = re.compile(
    r'<div class="bg-[a-z]+-500 text-white text-xs px-2 py-1 rounded-full[^"]*"[^>]*>(?P<body>.*?)</div>',
    re.S,
)
_ORG_EPISODES_RE = re.compile(r"(?P<count>\d+)\s*集")
_ORG_RATING_RE = re.compile(r"icon-star[^>]*>.*?<span>\s*(?P<rating>\d+(?:\.\d+)?)\s*</span>", re.S)
_ORG_SERIES_RE = re.compile(r'class="absolute bottom-2 left-2[^"]*"[^>]*title="(?P<series>[^"]*)"')
_ORG_SEASON_RE = re.compile(r"第\s*(?P<season>\d+)\s*季")
_ORG_TAG_RE = re.compile(r'<span class="inline-block rounded bg-blue-100[^"]*">\s*(?P<tag>[^<]+?)\s*</span>')
# 「11721万热度/648万播放」——两个数各自独立，播放数可能缺省
_ORG_HEAT_RE = re.compile(r"(?P<value>[\d.]+\s*[万亿]?)\s*热度")
_ORG_PLAYS_RE = re.compile(r"(?P<value>[\d.]+\s*[万亿]?)\s*播放")
# 卡片上的首播日期：演员页 / 榜单页的卡片都印这一行（「首播： 2026-09-19」），
# 而作品条目此前只有集数与评分 —— 首播时间是短剧区分同名版本的重要判据之一。
_ORG_CARD_RELEASE_RE = re.compile(r"首播\s*[：:]\s*(?P<date>\d{4}-\d{2}-\d{2})")
# 站点的 ``genre`` 里混着集数说明（实测「家庭」「女性成长」后面跟着「全72集」），
# 它不是类型标签，直接丢掉 —— 否则详情页的类型行会显示成「… | 全72集」。
_ORG_COUNT_TAG_RE = re.compile(r"^(?:全|共|更新至|已更新至)?\s*\d+\s*集$")


def _clean_tags(values: Any) -> List[str]:
    """清洗类型标签：去空白、去重、丢掉站点误塞进来的集数说明。"""
    tags: List[str] = []
    for value in values if isinstance(values, (list, tuple)) else [values]:
        tag = _clean(value)
        if not tag or _ORG_COUNT_TAG_RE.match(tag):
            continue
        if tag not in tags:
            tags.append(tag)
    return tags


def _org_card_regions(source: str) -> List[str]:
    """把页面切成「一张卡」的区间（逐字，不丢字段）。

    有卡片外壳标记（目录页 / 精选页）时按外壳切：一整张卡 = 海报锚 + 标题锚 +
    热度 + 标签，三处字段都在同一块里；没有外壳标记时退回「锚 + 锚前兄弟 ``<img>``」
    的切法（榜单页）。
    """
    if not source:
        return []

    marks = [match.start() for match in re.finditer(re.escape(_ORG_CARD_BLOCK_MARK), source)]
    if marks:
        regions = []
        for index, start in enumerate(marks):
            # 精确止于下一张卡的开头，避免把相邻作品的字段混进来
            end = (
                marks[index + 1]
                if index + 1 < len(marks)
                else min(len(source), start + _ORG_CARD_SPAN)
            )
            regions.append(source[start:end])
        return regions

    regions: List[str] = []
    anchors = list(_ORG_CARD_RE.finditer(source))
    seen: set = set()
    previous_end = 0
    for index, match in enumerate(anchors):
        native_id = match.group("id")
        if native_id in seen:
            continue
        seen.add(native_id)
        # 封面在**锚之前**的兄弟节点里（榜单页版式）。取「上一张卡的锚之后 → 本锚
        # 之前」这段窗口里的**最后一张** <img：既不回捞到上卡的封面，也不会错拿到
        # 页头 logo（窗口下界就是上卡锚的结尾）。
        window = source[previous_end: match.start()]
        images = list(_ORG_IMG_RE.finditer(window))
        start = previous_end + images[-1].start() if images else match.start()
        next_start = None
        for later in anchors[index + 1:]:
            if later.group("id") not in seen:
                next_start = later.start()
                break
        end = min(next_start or (match.end() + _ORG_CARD_SPAN), start + _ORG_CARD_SPAN)
        regions.append(source[start:end])
        previous_end = match.end()
    return regions


def parse_org_cards(html: str, domain: str = ORG_DEFAULT_DOMAIN) -> List[Dict[str, Any]]:
    """解析 ``.org`` 目录页 / 精选页 / 榜单页的作品卡，返回 ``id + 片名 + 海报``。

    三种页面共用同一套 ``href`` 形态，所以一个函数通吃；补充字段（真人/AI、状态角标、
    评分、集数、系列季、热度、播放、标签）能取到就带上，取不到留空 —— 榜单页没有这些
    字段，它们是**可选**的，任何调用方都不能依赖它们一定存在。
    """
    results: List[Dict[str, Any]] = []
    seen: set = set()
    for region in _org_card_regions(html or ""):
        anchor = _ORG_CARD_RE.search(region)
        if anchor is None:
            continue
        native_id = anchor.group("id")
        if native_id in seen:
            continue
        body = anchor.group("body") or ""

        # 标题：优先锚内 <img alt>（目录页 / 精选页），否则取锚文本（榜单页）
        alt = _ORG_CARD_ALT_RE.search(body)
        title = _clean(alt.group("alt")) if alt else ""
        if not title:
            title = _clean(_strip_tags(body))
        if not title:
            continue
        seen.add(native_id)

        # 封面：锚内 <img src> 优先，否则取锚之前的最近一张图（榜单页版式）
        src = _ORG_CARD_SRC_RE.search(body)
        if src is None:
            head = list(_ORG_IMG_RE.finditer(region[: anchor.start()]))
            if head:
                src = head[-1]

        record: Dict[str, Any] = {
            # 媒体 ID 是**裸数字**（与来源标识 ``duanju`` 配成一对，同 TMDB 的 ``603``）
            "media_id": str(native_id),
            "native_id": native_id,
            "title": title,
            "poster": _normalize_image(src.group("src")) if src else "",
            "url": f"{domain.rstrip('/')}/zh-Hans/drama/{native_id}",
        }
        record.update(_parse_org_card_extras(region))
        results.append(record)
    return results


def _parse_org_card_extras(region: str) -> Dict[str, Any]:
    """从**整张卡**的 HTML 里取「真人/AI、状态、评分、集数、首播、系列季、热度、播放、标签」。

    这些字段是**锦上添花**：站点在不同版式下渲染的字段并不一致（榜单页就没有），
    所以每个字段都独立判空，取不到就整条不带，绝不让缺失变成异常。

    ⚠️ 卡片印的题材标签是**摘要**（只印 1~3 个，实测《失控交易》卡片上只有「爱情」，
    而它详情页有 5 个），卡片上也没有**版权方** —— 这两样只有详情页才有。
    """
    extras: Dict[str, Any] = {}
    if not region:
        return extras

    kind = _ORG_KIND_RE.search(region)
    if kind and _clean(kind.group("kind")):
        extras["kind"] = _clean(kind.group("kind"))

    badge = _ORG_BADGE_RE.search(region)
    if badge:
        text = _clean(_strip_tags(badge.group("body")))
        if text:
            extras["badge"] = text

    rating = _ORG_RATING_RE.search(region)
    if rating:
        extras["rating"] = _clean(rating.group("rating"))

    episodes = _ORG_EPISODES_RE.search(region)
    if episodes:
        extras["episode_count"] = int(episodes.group("count"))

    release = _ORG_CARD_RELEASE_RE.search(region)
    if release:
        extras["release_date"] = _clean(release.group("date"))
        year = _parse_year(extras["release_date"])
        if year:
            extras["year"] = year

    series = _ORG_SERIES_RE.search(region)
    if series and _clean(series.group("series")):
        extras["series"] = _clean(series.group("series"))
        season = _ORG_SEASON_RE.search(region)
        if season:
            extras["season"] = int(season.group("season"))

    tags = _clean_tags([match.group("tag") for match in _ORG_TAG_RE.finditer(region)])
    if tags:
        extras["tags"] = tags

    heat = _ORG_HEAT_RE.search(region)
    if heat:
        amount = _parse_wannum(heat.group("value"))
        if amount is not None:
            extras["heat"] = amount

    plays = _ORG_PLAYS_RE.search(region)
    if plays:
        amount = _parse_wannum(plays.group("value"))
        if amount is not None:
            extras["play_count"] = amount

    return extras


# ── ``.org`` 详情页解析 ───────────────────────────────────────────

_ORG_LD_RE = re.compile(
    r'<script[^>]*application/ld\+json[^>]*>(?P<body>.*?)</script>', re.S
)
_ORG_H1_RE = re.compile(r"<h1[^>]*>(?P<title>.*?)</h1>", re.S)
_ORG_SUMMARY_RE = re.compile(r"剧情简介</h2>\s*<p[^>]*>(?P<overview>.*?)</p>", re.S)
# 形如 <span class="text-gray-500">集数：</span><span class="text-gray-900 …">106集</span>
_ORG_FIELD_RE = re.compile(
    r'<span class="text-gray-500">\s*(?P<label>[^<：:]+?)\s*[：:]\s*</span>\s*'
    r'<span class="text-gray-900[^"]*">\s*(?P<value>.*?)\s*</span>',
    re.S,
)
_ORG_STAT_RE = re.compile(
    r'<span class="font-medium">\s*(?P<value>[^<]+?)\s*</span>\s*(?P<label>播放|收藏|评分|热度)',
    re.S,
)
# 演员页「基本信息」区：<dt …>性别：</dt><dd …>女</dd>
_ORG_DT_DD_RE = re.compile(
    r"<dt[^>]*>\s*(?P<label>.*?)\s*</dt>\s*<dd[^>]*>\s*(?P<value>.*?)\s*</dd>", re.S
)
# 页面底部「推荐短剧」区块，卡片版式与其它位置完全一致，直接复用卡片解析
_ORG_RELATED_MARK = "推荐短剧"
_ORG_RELATED_WINDOW = 30000
# 演员阵容：<a href="…/zh-Hans/actor/{id}"> 头像锚 + 姓名锚，同一 id 出现两次
_ORG_ACTOR_LINK_RE = re.compile(
    r'<a\b[^>]*href="(?:https?://[^"]*?)?/zh-Hans/actor/(?P<id>\d+)"', re.S
)
_ORG_ACTOR_NAME_RE = re.compile(
    r'<a\b[^>]*href="[^"]*/zh-Hans/actor/\d+"[^>]*class="[^"]*text-blue-600[^"]*"[^>]*>'
    r"\s*(?P<name>[^<]+?)\s*</a>",
    re.S,
)
_ORG_ACTOR_ROLE_RE = re.compile(
    r"<span[^>]*>\s*饰\s*</span>\s*<span[^>]*>\s*(?P<role>[^<]*?)\s*</span>", re.S
)
_ORG_ACTOR_KIND_RE = re.compile(r">\s*(?P<kind>主演|配角|客串|特别出演)\s*<")
_ORG_ACTOR_ALT_RE = re.compile(r'alt="(?P<alt>[^"]*)"')
_ORG_ACTOR_WINDOW = 1500
# 「饰 XXX」到「主演 / 配角」之间隔着一条 HTML 注释和一整段 span 属性（实测约 450
# 字符），窗口给小了会取不到主次 —— 但也不能无限大，否则会把下一个演员的标签算进来
# （实测相邻演员相距约 1900 字符，900 是安全值）。
_ORG_ACTOR_KIND_SPAN = 900
# 剧照：<div id="drama-photo-gallery" …> 内每张图的 <a href> 就是原图
_ORG_GALLERY_MARK = 'id="drama-photo-gallery"'
_ORG_GALLERY_SRC_RE = re.compile(r'href="(?P<src>https?://[^"]+\.(?:jpg|jpeg|png|webp))"', re.S)
_ORG_GALLERY_WINDOW = 6000


def _org_html_body(html: str) -> str:
    """去掉 JSON-LD 脚本块后的正文。

    JSON-LD 里也有 ``/zh-Hans/actor/{id}`` 形式的 URL，不去掉会让按锚点定位的
    HTML 解析把 JSON-LD 误当成演员卡（窗口落在 JSON 里，取不到「饰 XXX」）。
    """
    return _ORG_LD_RE.sub(" ", html or "")


def _org_json_ld(html: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    series: Dict[str, Any] = {}
    page: Dict[str, Any] = {}
    for match in _ORG_LD_RE.finditer(html or ""):
        try:
            payload = json.loads(match.group("body"))
        except (ValueError, TypeError):
            continue
        graph = payload.get("@graph") if isinstance(payload, dict) else None
        nodes = graph if isinstance(graph, list) else [payload]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if node.get("@type") == "TVSeries":
                series = node
            elif node.get("@type") == "WebPage":
                page = node
    return series, page


def _org_cast_from_json_ld(series: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """从 ``TVSeries.actor``（``PerformanceRole`` 数组）取演员阵容。

    这是本站**最稳**的演员来源：字段规整，且 ``characterName`` 直接给出饰演角色。
    """
    roles = (series or {}).get("actor")
    if not isinstance(roles, list):
        return []
    actors: List[Dict[str, Any]] = []
    for role in roles:
        if not isinstance(role, dict):
            continue
        person = role.get("actor") if isinstance(role.get("actor"), dict) else role
        name = _clean(person.get("name"))
        if not name:
            continue
        actor_id = ""
        found = re.search(r"/zh-Hans/actor/(\d+)", _clean(person.get("url") or person.get("@id")))
        if found:
            actor_id = found.group(1)
        actors.append(
            {
                "id": actor_id,
                "name": name,
                "character": _clean(role.get("characterName")),
                "profile_path": _normalize_image(person.get("image")),
            }
        )
    return actors


def _org_actor_kinds(html: str) -> Dict[str, str]:
    """从 HTML 演员卡里取「主演 / 配角」标签，键为演员 ID。

    JSON-LD 没有主次之分，这个信息只在正文里。
    """
    body = _org_html_body(html)
    kinds: Dict[str, str] = {}
    for match in _ORG_ACTOR_LINK_RE.finditer(body):
        actor_id = match.group("id")
        if actor_id in kinds:
            continue
        window = body[match.start(): match.start() + _ORG_ACTOR_WINDOW]
        role_match = _ORG_ACTOR_ROLE_RE.search(window)
        if not role_match:
            continue
        # 只在「饰 XXX」之后的一小段里找，避免把下一个演员的标签算进来
        tail = window[role_match.end(): role_match.end() + _ORG_ACTOR_KIND_SPAN]
        kind_match = _ORG_ACTOR_KIND_RE.search(tail)
        if kind_match:
            kinds[actor_id] = _clean(kind_match.group("kind"))
    return kinds


def _org_cast_from_html(html: str) -> List[Dict[str, Any]]:
    """从 HTML「演员阵容」区块取演员阵容（JSON-LD 缺失时的兜底）。

    每个演员在标记里有两个同 ID 的 ``<a href="…/zh-Hans/actor/{id}">``：一个是头像、
    一个是姓名，按 id 去重即可。该区块在「这部作品没有录入角色」时整块不渲染 ——
    那是**作品级**差异，不是站点能力缺失（早期只读 JSON-LD 的 name/description
    就下过「本站没有演员表」的结论，实测证明是错的）。
    """
    body = _org_html_body(html)
    actors: List[Dict[str, Any]] = []
    seen: set = set()
    for match in _ORG_ACTOR_LINK_RE.finditer(body):
        actor_id = match.group("id")
        if actor_id in seen:
            continue
        window = body[match.start(): match.start() + _ORG_ACTOR_WINDOW]

        name = ""
        name_match = _ORG_ACTOR_NAME_RE.search(window)
        if name_match:
            name = _clean(name_match.group("name"))
        if not name:
            alt = _ORG_ACTOR_ALT_RE.search(window)
            if alt:
                name = _clean(alt.group("alt"))
        if not name:
            continue
        seen.add(actor_id)

        role = ""
        role_match = _ORG_ACTOR_ROLE_RE.search(window)
        if role_match:
            role = _clean(role_match.group("role"))

        avatar = ""
        src = _ORG_CARD_SRC_RE.search(window)
        if src:
            avatar = _normalize_image(src.group("src"))

        actors.append(
            {
                "id": actor_id,
                "name": name,
                "character": role,
                "profile_path": avatar,
            }
        )
    return actors


def parse_org_cast(
    html: str,
    series: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """解析演员阵容：JSON-LD 优先，HTML 兜底，再用 HTML 补「主演 / 配角」。"""
    source = html or ""
    actors = _org_cast_from_json_ld(series) or _org_cast_from_html(source)
    if not actors:
        return []
    kinds = _org_actor_kinds(source)
    for actor in actors:
        actor["kind"] = kinds.get(actor.get("id", ""), actor.get("kind", ""))
    return actors


def parse_org_gallery(html: str) -> List[str]:
    """解析剧照区块，返回原图直链（该站 PC / 移动端都只渲染 4 张）。"""
    source = html or ""
    mark = source.find(_ORG_GALLERY_MARK)
    if mark < 0:
        return []
    window = source[mark: mark + _ORG_GALLERY_WINDOW]
    stills: List[str] = []
    for match in _ORG_GALLERY_SRC_RE.finditer(window):
        src = _normalize_image(match.group("src"))
        if src and src not in stills:
            stills.append(src)
    return stills


def parse_org_detail(html: str, native_id: str, domain: str = ORG_DEFAULT_DOMAIN) -> Dict[str, Any]:
    """解析 ``.org`` 作品详情页。

    优先级：JSON-LD（字段规整、跨版本稳） → 页面正文（演员阵容 / 剧照 / 播放收藏
    这些 JSON-LD 里根本没有的内容只能从 HTML 取；其余字段作兜底）。
    """
    source = html or ""
    data: Dict[str, Any] = {
        # 媒体 ID 是**裸数字**（与来源标识 ``duanju`` 配成一对，同 TMDB 的 ``603``）
        "media_id": str(native_id),
        "native_id": native_id,
        # 兜底地址：只在页面自己没声明 url 时使用（见下方 JSON-LD 覆写）
        "url": f"{domain.rstrip('/')}/zh-Hans/drama/{native_id}",
    }

    series, page = _org_json_ld(source)

    # JSON-LD 里就有这条页面的规范地址（实测 TVSeries 的 ``url``，带 zh-Hans / zh-Hant
    # 语言前缀）—— 有就用它，别拿 ID 拼一个出来。
    data["url"] = _clean(series.get("url") or page.get("url")) or data["url"]

    data["title"] = _clean(series.get("name") or page.get("name"))
    if not data["title"]:
        h1 = _ORG_H1_RE.search(source)
        if h1:
            data["title"] = _strip_tags(h1.group("title"))

    data["overview"] = _clean(series.get("description") or page.get("description"))
    if not data["overview"]:
        summary = _ORG_SUMMARY_RE.search(source)
        if summary:
            data["overview"] = _strip_tags(summary.group("overview"))

    cover = ""
    primary = page.get("primaryImageOfPage")
    if isinstance(primary, dict):
        cover = _normalize_image(primary.get("url"))
    if not cover:
        image = series.get("image")
        cover = _normalize_image(image if isinstance(image, str) else "")
    data["poster"] = cover

    data["episode_count"] = _parse_int(series.get("numberOfEpisodes"))
    # ⚠️ 站点给的 ``duration`` 是**全集总时长**，不是单集时长（实测《失控交易》
    # ``"PT2H10M10S"`` = 130 分钟 / 77 集，页面上写的「时长 2小时10分」也是全集）。
    # 单集时长由下面按集数折算，两个字段都给，消费方按自己要什么取。
    data["duration_minutes"] = _parse_duration_minutes(series.get("duration"))

    published = _clean(series.get("datePublished"))
    if published:
        data["release_date"] = published
        data["year"] = _parse_year(published)

    genre = series.get("genre")
    if _has_value(genre):
        data["tags"] = _clean_tags(genre)

    holder = series.get("copyrightHolder")
    if isinstance(holder, dict):
        data["studio"] = _clean(holder.get("name"))

    # 评分：结构化数据里的 aggregateRating 优先（站上多数作品没有这一项）
    aggregate = series.get("aggregateRating")
    if isinstance(aggregate, dict):
        score = _clean(aggregate.get("ratingValue"))
    elif isinstance(aggregate, (str, int, float)):
        score = _clean(aggregate)
    else:
        score = ""
    if score:
        data["rating"] = score

    # 正文「标签：值」区块：补齐 JSON-LD 缺的字段
    for match in _ORG_FIELD_RE.finditer(source):
        label = _clean(match.group("label"))
        value = _strip_tags(match.group("value"))
        if not value:
            continue
        if label == "集数" and not data.get("episode_count"):
            data["episode_count"] = _parse_int(value)
        elif label == "时长" and not data.get("duration_minutes"):
            data["duration_minutes"] = _parse_duration_minutes(value)
        elif label == "首播时间" and not data.get("release_date"):
            data["release_date"] = value
            data["year"] = _parse_year(value)
        elif label == "出品方" and not data.get("studio"):
            data["studio"] = value
        elif label in ("类型", "标签") and not data.get("tags"):
            data["tags"] = _clean_tags(re.split(r"[，,、/\s]+", value))

    # 单集时长 = 全集总时长 ÷ 集数（站点只给全集，短剧每集 1~3 分钟，折算值够用）
    episodes = data.get("episode_count")
    total = data.get("duration_minutes")
    if isinstance(episodes, int) and episodes > 0 and isinstance(total, int) and total > 0:
        data["episode_minutes"] = max(1, round(total / episodes))

    # 播放 / 收藏 / 评分（JSON-LD 里没有）
    for match in _ORG_STAT_RE.finditer(source):
        label = _clean(match.group("label"))
        text = match.group("value").replace(",", "")
        if label == "播放":
            data["play_count"] = _parse_wannum(text)
        elif label == "收藏":
            data["favorite_count"] = _parse_wannum(text)
        elif label == "热度":
            # 「354万 热度」—— 站点自己的热度指标，短剧场景里比播放量更能反映当下的热度
            data["heat"] = _parse_wannum(text)
        elif label == "评分" and not _has_value(data.get("rating")):
            # 详情页的「评分」与卡片上的星星是同一个分值。站点无值时整个统计项不渲染，
            # 所以这里取不到就留空，绝不塞 0 —— 0 分会被宿主当成「有评分」显示出来。
            score = _clean(text)
            if score:
                data["rating"] = score

    # 剧照 → 背景图
    stills = parse_org_gallery(source)
    if stills:
        data["stills"] = stills
        data["backdrop"] = stills[0]

    # 真人 / AI 角标（h1 左侧那枚；与卡片解析共用同一条正则）
    kind = _ORG_KIND_RE.search(source)
    if kind and _clean(kind.group("kind")):
        data["kind"] = _clean(kind.group("kind"))

    language = _clean(series.get("inLanguage") or page.get("inLanguage"))
    if language:
        data["in_language"] = language

    data["actors"] = parse_org_cast(source, series)
    # 推荐位：同页底部的「推荐短剧」，字段口径与卡片解析完全一致
    data["related"] = parse_org_related(source, domain)
    data.setdefault("tags", [])
    return data


def parse_org_related(html: str, domain: str = ORG_DEFAULT_DOMAIN) -> List[Dict[str, Any]]:
    """解析页面底部「推荐短剧」区块（站点给的关联作品）。

    卡片版式与其它位置一致，所以直接截出该区块再交给 :func:`parse_org_cards` ——
    不用第二套解析规则，字段口径天然一致。
    """
    source = html or ""
    mark = source.find(_ORG_RELATED_MARK)
    if mark < 0:
        return []
    return parse_org_cards(source[mark: mark + _ORG_RELATED_WINDOW], domain)


# ── ``.org`` 演员页解析 ───────────────────────────────────────────
# ⚠️ 必须抓 **zh-Hans** 路径：不带语言前缀访问会被 301 到 zh-Hant，页面里的作品链接
# 随之变成 ``/zh-Hant/drama/<id>``，而卡片正则只认 ``/zh-Hans/drama/`` ⇒ 静默解析出
# 0 部作品（资料字段照常正确，所以极难发现）。

_ORG_PERSON_TITLE_RE = re.compile(r"<title>(?P<title>.*?)</title>", re.S)


def _org_person_json_ld(html: str) -> Dict[str, Any]:
    """从页面里抽出 ``Person`` JSON-LD 节点（演员页有，作品详情页没有）。"""
    for match in _ORG_LD_RE.finditer(html or ""):
        try:
            payload = json.loads(match.group("body"))
        except (ValueError, TypeError):
            continue
        graph = payload.get("@graph") if isinstance(payload, dict) else None
        nodes = graph if isinstance(graph, list) else [payload]
        for node in nodes:
            if isinstance(node, dict) and node.get("@type") == "Person":
                return node
    return {}


def parse_org_actor(
    html: str,
    actor_id: str,
    domain: str = ORG_DEFAULT_DOMAIN,
) -> Dict[str, Any]:
    """解析 ``.org`` 演员页，返回演员档案 + 全部作品 + 合作演员。

    :param html: 演员页正文（必须是 ``/zh-Hans/actor/<id>`` 的响应，见上方警告）
    :param actor_id: 站点演员 ID（裸数字）
    :param domain: 站点域名
    :return: ``{"actor_id", "media_id", "name", "bio", "profile", "job_title",
        "gender", "nationality", "url", "works": [...], "coactors": [...]}``
    """
    source = html or ""
    person = _org_person_json_ld(source)
    data: Dict[str, Any] = {
        "actor_id": actor_id,
        "media_id": f"{ACTOR_ID_PREFIX}:{actor_id}",
        "url": f"{domain.rstrip('/')}{ACTOR_PATH.format(id=actor_id)}",
        "name": _clean(person.get("name")),
        "bio": _clean(person.get("description")),
        "profile": _normalize_image(person.get("image")),
        "job_title": _clean(person.get("jobTitle")),
        "gender": _clean(person.get("gender")),
    }

    nationality = person.get("nationality")
    if isinstance(nationality, dict):
        data["nationality"] = _clean(nationality.get("name"))
    elif _has_value(nationality):
        data["nationality"] = _clean(nationality)

    # 姓名兜底：JSON-LD 缺失时从 <title> 里剥站点后缀（「魏依珂 - 短剧演员 - 短剧百科」）
    if not data["name"]:
        title = _ORG_PERSON_TITLE_RE.search(source)
        if title:
            data["name"] = _strip_org_suffix(_strip_tags(title.group("title")))

    # 「基本信息」区块（dt/dd）兜底：JSON-LD 缺 gender / nationality 时从页面取
    for match in _ORG_DT_DD_RE.finditer(source):
        label = _clean(match.group("label")).rstrip("：:")
        value = _strip_tags(match.group("value"))
        if not value:
            continue
        if label == "性别" and not data.get("gender"):
            data["gender"] = value
        elif label == "国籍" and not data.get("nationality"):
            data["nationality"] = value

    works = parse_org_cards(source, domain)
    data["works"] = works
    data["works_count"] = len(works)
    data["coactors"] = parse_org_cast(source, None)
    data["coactors_count"] = len(data["coactors"] or [])
    return data


def is_cloudflare_challenge(html: str, status_code: Optional[int] = None) -> bool:
    """判断响应是否为 Cloudflare 人机校验页（而非真实内容）。

    被挡住时把它当「没拿到内容」处理即可 —— 调用方据此放弃**这一次**解析。
    """
    if status_code == 403:
        return True
    text = (html or "")[:4000]
    return "Just a moment" in text or "cf-chl" in text or "Attention Required" in text

