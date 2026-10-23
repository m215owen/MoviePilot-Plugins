"""顺带登记：从任意页面抽出全部 ``(media_id, name)`` 并批量入库（计划 §3.4）。

站点每个页面都是「ID 分发器」——详情页有演员/编剧/原著链接，人物页有作品链接，
搜索页/目录页有整页卡片。抓任何一页都顺手把里面的链接登记进 ``baike``，索引因此自己长大。

纪律：**只登记认识的八类实体前缀**；名字取不到就留空串（仍保留 id，名字空即不可检索）。
"""

from __future__ import annotations

import html as html_lib
import re
from typing import Iterable

from . import constants
from .media_id import media_id_of, name_from_card, scan_ids


def _plain(raw: str) -> str:
    """去标签 + 反转义 + 折叠空白。"""
    plain = re.sub(r"<[^>]+>", "", raw or "")
    return re.sub(r"\s+", " ", html_lib.unescape(plain)).strip()

# 卡片/头像的属性里常带「演员：」「编剧：」这类前缀，取名字时要剥掉
NAME_PREFIXES = (
    "短剧演员：",
    "短剧导演：",
    "短剧编剧：",
    "演员：",
    "导演：",
    "编剧：",
    "小说：",
    "短剧：",
    "漫剧：",
)


def attr_value(text: str, attr: str) -> str:
    """取标签内某属性的值（单双引号都认），取不到返回空串。"""
    for quote in ('"', "'"):
        needle = f"{attr}={quote}"
        start = text.find(needle)
        if start < 0:
            continue
        end = text.find(quote, start + len(needle))
        if end > start:
            return text[start + len(needle) : end]
    return ""


def name_near_link(html: str, native_id: str) -> str:
    """取 ``info-{id}.html`` **所在卡片**的名字。

    必须先把范围锁到当前 ``<a>...</a>`` 块再取属性：固定窗口 + ``rfind`` 会抓到手
    上一张卡的 ``alt``（实测把「张晋宜」错认成「卡戎」）。两种卡片形态都覆盖：

    * 作品卡：``<a href="..." title="短剧《X》">``
    * 人物卡：``<a href="..."><img alt="演员：X">``（名字也可能在后文的 ``<div>`` 里）
    * 人物目录卡（``/<kind>/list.html``）：``alt="image"`` 占位，真名在卡内
      ``<p class="font-bold ...">``（导演/编剧列表页实测）
    """
    idx = html.find(f"info-{native_id}.html")
    if idx < 0:
        return ""
    a_start = html.rfind("<a", 0, idx)
    a_end = html.find("</a>", idx)
    left = a_start if a_start >= 0 else max(0, idx - 400)
    right = a_end + 4 if a_end > 0 else idx + 400
    block = html[left:right]
    raw = attr_value(block, "title") or attr_value(block, "alt")
    if not raw or raw.strip().lower() in ("image", "img", "图片"):
        # 兜底一：目录页人物卡的 alt 可能是占位图文本（``alt="image"``，导演/编剧
        # 列表页实测如此），真名在卡内加粗标题段 ``<p class="font-bold ...">名字</p>``
        match = re.search(r'font-bold[^>]*>(.*?)</p>', block, re.S)
        if match:
            raw = _plain(match.group(1)) or raw or ""
    if not raw:
        # 兜底二：卡片里的标题 div（``<div class="text-base font-semibold">名字</div>``）
        match = re.search(r'text-base font-semibold[^>]*>(.*?)</div>', block, re.S)
        if match:
            raw = _plain(match.group(1))
    if not raw:
        return ""
    for prefix in NAME_PREFIXES:
        if raw.startswith(prefix):
            raw = raw[len(prefix) :]
            break
    return name_from_card(raw)


def extract_entries(html: str) -> list[tuple[str, str]]:
    """页面 → ``[(media_id, name)]``，只保留八类百科实体、按 id 去重。"""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for entity, native_id in scan_ids(html):
        if entity not in constants.ENTITY_ALL:
            continue
        media_id = media_id_of(entity, native_id)
        if not media_id or media_id in seen:
            continue
        seen.add(media_id)
        out.append((media_id, name_near_link(html, native_id)))
    return out


def harvest_page(html: str, store) -> int:
    """抓到的页面顺带登记，返回新增条数。任何异常都不影响主流程。"""
    if not html:
        return 0
    try:
        rows: Iterable[tuple[str, str]] = extract_entries(html)
        return store.upsert_many(rows=list(rows))
    except Exception:  # pragma: no cover - 登记失败不能影响刮削
        return 0
