"""站点解析公用小工具（文本清洗 / 数值换算 / 简介拆解）。

历史来源：:mod:`shortdramanetsource.netsite` 里这几个函数与站点结构无关，
.org 解析器（:mod:`orgsite`）搬到本插件后仍要它们，于是原样收拢到这里 ——
**不掺任何 .net / .org 的页面结构假设**，两边都能引。

之所以不在插件里再造一份实现：`.net` 侧的语义已经由这些函数定死
（``995万`` → 9950000、「只写年份」的生日退化成 ``birth_year``…），
两站共用一份口径，展示层才不会出现同一字段两种解读。
"""

from __future__ import annotations

import re
from typing import Any, Dict, Tuple

#: ``2026-11-04`` / ``2026-11-04T00:00:00`` 里的日期部分
_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
#: 页面文案里的集数：``全 62 集`` / ``已更新至 10 集``
_EPISODES_RE = re.compile(r"(\d+)\s*集")
#: ``995万`` / ``320.51万`` / ``38.48 万字``（原著页的字数带「字」）都收
_WAN_RE = re.compile(r"^([\d.]+)\s*万(?:字)?$")
#: 卡片 title / alt 里的书名号
_TITLE_IN_BOOKS_RE = re.compile(r"《(?P<title>[^》]+)》")

#: 十二星座：人物介绍里会出现，用来补「生日只写到年份」时的档案项
_ZODIACS: Tuple[str, ...] = (
    "水瓶座",
    "双鱼座",
    "白羊座",
    "金牛座",
    "双子座",
    "巨蟹座",
    "狮子座",
    "处女座",
    "天秤座",
    "天蝎座",
    "射手座",
    "摩羯座",
)


def clean(value: Any) -> str:
    """折叠空白 + 去首尾空白；``None`` → 空串。"""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def to_int(value: Any, default: int = 0) -> int:
    """宽松转 int（``"3.0"`` 也能转）；失败返回默认值。"""
    try:
        return int(float(clean(value)))
    except (TypeError, ValueError):
        return default


def to_float(value: Any, default: float = 0.0) -> float:
    """宽松转 float；失败返回默认值。"""
    try:
        return float(clean(value))
    except (TypeError, ValueError):
        return default


def wan_to_number(value: Any, default: int = 0) -> int:
    """``995万`` → 9950000；纯数字照转；空/异常返回默认值。"""
    text = clean(value)
    if not text:
        return default
    match = _WAN_RE.match(text)
    if match:
        return int(round(to_float(match.group(1)) * 10000))
    return to_int(text, default)


def title_in_books(value: str) -> str:
    """取书名号里的内容（``短剧《X》`` → ``X``）；没有书名号返回空串。"""
    match = _TITLE_IN_BOOKS_RE.search(str(value or ""))
    return clean(match.group("title")) if match else ""


def profile_of(biography: str) -> Dict[str, Any]:
    """人物简介文本 → 档案字段（生日 / 籍贯 / 身高体重 / 星座 / 学历 / 爱好 / 国籍 / 代表作）。

    只做**文本里明确写了**的字段，绝不猜测：站点没写的项保持空值，
    展示层据此隐藏，比编一个「未知」更诚实。
    """
    text = clean(biography)
    profile: Dict[str, Any] = {
        "birth_date": "",
        "birth_year": "",
        "birth_place": "",
        "height_cm": 0,
        "weight_kg": 0,
        "constellation": "",
        "education": "",
        "hobbies": [],
        "nationality": "",
        "representative_text": "",
        "representative_works": [],
    }
    if not text:
        return profile

    # 生日：优先完整年月日，只有年份时退化成 birth_year
    found = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if found:
        profile["birth_date"] = "%s-%02d-%02d" % (
            found.group(1),
            int(found.group(2)),
            int(found.group(3)),
        )
        profile["birth_year"] = found.group(1)
    else:
        found = re.search(r"(\d{4})年(?=出生|生)", text)
        if found:
            profile["birth_year"] = found.group(1)

    # 籍贯：排除「出生于1999年…」那种日期，所以要求首字不是数字
    found = re.search(r"出生于([^\d，。；、,]{2,8})", text)
    if found:
        profile["birth_place"] = found.group(1).strip()

    found = re.search(r"身高\s*[:：]?\s*(\d{2,3})\s*(?:cm|CM|厘米)", text)
    if found:
        profile["height_cm"] = to_int(found.group(1))
    found = re.search(r"体重\s*[:：]?\s*(\d{2,3})\s*(?:kg|KG|公斤)", text)
    if found:
        profile["weight_kg"] = to_int(found.group(1))

    profile["constellation"] = next((item for item in _ZODIACS if item in text), "")

    found = re.search(r"毕业于([^，。；、,]{2,20})", text)
    if found:
        profile["education"] = found.group(1).strip()

    # 爱好：先把「代表作品…」那句掐掉再拆
    found = re.search(r"爱好\s*[:：]?\s*([^。；]*)", text)
    if found:
        tail = re.split(r"代表(?:作品|作)?", found.group(1))[0]
        profile["hobbies"] = [
            part.strip(" 、,，")
            for part in re.split(r"[、,，/和]", tail)
            if part.strip(" 、,，")
        ]

    # 国籍：只在文案自己写了「中国…演员 / 艺人」时记，避免「毕业于中国药科大学」误判
    if re.search(r"中国(?:内地|大陆|香港|澳门|台湾)?[^，。]{0,4}?(?:演员|艺人|明星)", text):
        profile["nationality"] = "中国"

    # 代表作：站点常把几个剧名连写，拼不出来就只留原文
    found = re.search(r"代表(?:作品|作)?(?:有|为|是)?\s*[:：]?\s*([^。]+)", text)
    if found:
        segment = re.sub(r"等$", "", found.group(1).strip(" ，、")).strip()
        profile["representative_text"] = segment
        parts = [
            part.strip(" ，、")
            for part in re.split(r"[、,，/]", segment)
            if part.strip(" ，、")
        ]
        if len(parts) > 1:
            profile["representative_works"] = parts
    return profile


__all__ = [
    "clean",
    "profile_of",
    "title_in_books",
    "to_float",
    "to_int",
    "wan_to_number",
]
