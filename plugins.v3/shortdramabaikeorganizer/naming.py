"""源文件名集号规整与短剧处理器命名渲染。

短剧常见 80-120 集，源文件名花样极多：``第18集.mp4`` / ``EP18.mp4`` /
``18.mp4`` / ``剧名-018.mp4``。本模块负责两件事：

1. 从文件名提取集号（提不到时由调用方决定是否按自然序补齐）；
2. 按宿主「短剧处理器」TV 命名规则渲染目标路径
   （``{剧名} ({年})/Season {季}/{剧名} - S{季:02d}E{NN}.ext``，季号由调用方
   从数据源 MediaInfo 传入，缺省 1）。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .constants import EPISODE_PATTERNS

_COMPILED_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern) for pattern in EPISODE_PATTERNS
)

_EPISODE_MIN = 1
_EPISODE_MAX = 9999

# 剧名里不能进路径的字符（Windows / Linux 通用）
_ILLEGAL_PATH = re.compile(r'[\\/:*?"<>|]')


def safe_title(title: str) -> str:
    """剔除剧名里不能进目录名的非法字符，并压缩空白。"""
    if not title:
        return "未知短剧"
    cleaned = _ILLEGAL_PATH.sub(" ", str(title)).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or "未知短剧"


def extract_episode(text: str) -> Optional[int]:
    """从文件名/路径片段中提取集号，提不到返回 None。

    按 ``EPISODE_PATTERNS`` 顺序尝试，命中即返回；结果做范围校验。
    """
    if not text:
        return None
    name = str(text)
    stem = Path(name).stem
    if stem:
        name = stem
    for pattern in _COMPILED_PATTERNS:
        match = pattern.search(name)
        if not match:
            continue
        try:
            value = int(match.group(1))
        except (TypeError, ValueError, IndexError):
            continue
        if _EPISODE_MIN <= value <= _EPISODE_MAX:
            return value
    return None


def natural_key(name: str) -> tuple:
    """自然排序键：``第2集`` 排在 ``第10集`` 之前。"""
    parts = re.split(r"(\d+)", str(name))
    return tuple(
        (1, int(part)) if part.isdigit() else (0, part.lower())
        for part in parts
        if part != ""
    )


def format_episode(episode: int, width: int) -> str:
    """按位数补零：width=3 时 18 -> ``018``（默认 2 位，与短剧处理器一致）。"""
    safe_width = max(1, min(4, int(width or 2)))
    return str(int(episode)).zfill(safe_width)


def build_episode_name(
    title: str,
    season: int,
    episode: int,
    *,
    width: int,
    extension: str,
) -> str:
    """渲染短剧处理器文件名：``剧名 - S01E018.ext``。"""
    episode_part = format_episode(episode, width)
    season_part = str(max(1, int(season or 1))).zfill(2)
    return f"{title} - S{season_part}E{episode_part}{extension}"


# ── 剧名里的季号/括号年份后缀（2026-10-23 用户「目标应该是隐身侍卫 分季在剧文件夹下」）──
#
# 短剧百科站点把第 N 季拆成**独立词条**（``隐身侍卫`` / ``隐身侍卫第二季``），
# recognize 原样带回标题。宿主短剧处理器的口径是同剧多季同目录：
# ``隐身侍卫 (2026)/Season 2/隐身侍卫 - S02E86.mp4`` —— 季号交给 Season
# 目录，所以这里把季号后缀与括号年份从剧名里剥掉。
_CN_NUMBERS: dict[str, int] = {
    "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9,
}
_FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")

# 尾部括号年份：``隐身侍卫第二季（2026）`` → 2026
_YEAR_SUFFIX_RE = re.compile(r"[（(]\s*(?P<year>19\d{2}|20\d{2})\s*[）)]\s*$")

# 尾部季号后缀（三种写法都认）：第2季 / 第二季 / S02 / Season 2
_SEASON_SUFFIX_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"[（(]?\s*第\s*(?P<num>[0-9０-９一二两三四五六七八九十]+)\s*季\s*[）)]?\s*$"),
    re.compile(r"[（(]?\s*(?<![A-Za-z0-9])[sS]\s*(?P<num>\d{1,2})\s*[）)]?\s*$"),
    re.compile(r"[（(]?\s*(?<![A-Za-z])[sS]eason\s*(?P<num>\d{1,2})\s*[）)]?\s*$", re.IGNORECASE),
)
# 剥完后缀残留的分隔符（空格 / 横线 / 标点）
_TRAILING_JUNK = " \t-–—·:：/、,，"


def _cn_number(token: str) -> Optional[int]:
    """季号数字串 → int：阿拉伯 / 全角阿拉伯 / 中文数字（到 99）。

    ``2``→2、``０２``→2、``二``→2、``十二``→12、``二十``→20。
    """
    text = str(token or "").strip().translate(_FULLWIDTH_DIGITS)
    if not text:
        return None
    if text.isdigit():
        return int(text)
    total = 0
    for char in text:
        if char == "十":
            total = (total or 1) * 10
        elif char in _CN_NUMBERS:
            total += _CN_NUMBERS[char]
        else:
            return None
    return total or None


def parse_title_identity(title: str) -> tuple[str, Optional[int], Optional[int]]:
    """拆数据源识别的剧名 → ``(剧名, 季号, 年份)``（季号/年份可为 None）。

    站点一季一条独立词条，recognize 带回的可能是 ``隐身侍卫第二季`` 或
    ``隐身侍卫第二季（2026）``。**季号只检测不剥除**（2026-10-23 用户改回
    「第二季就按第二季剧名整理」：一季一个独立剧目录，``隐身侍卫第二季`` 就是
    剧名本身），括号年份仍剥掉交给 ``(年)`` 目录后缀；检测出的季号供调用方
    回落到 ``Season N`` 子目录。

    对没有季号后缀的干净剧名（``一见钟情``）是恒等变换。
    """
    text = str(title or "").strip()
    year: Optional[int] = None
    match = _YEAR_SUFFIX_RE.search(text)
    if match:
        year = int(match.group("year"))
        text = text[: match.start()].rstrip(_TRAILING_JUNK)
    season: Optional[int] = None
    probe = text
    for pattern in _SEASON_SUFFIX_PATTERNS:
        match = pattern.search(probe)
        if not match:
            continue
        parsed = _cn_number(match.group("num"))
        if parsed and 1 <= parsed <= 99:
            season = parsed
            break
    return (text or "未知短剧"), season, year


def build_drama_dir(library_dir: str, title: str, year: Optional[int]) -> Path:
    """渲染剧目录：``{library_dir}/{剧名} ({年})``（无年份则不带括号）。"""
    name = safe_title(title)
    if year:
        return Path(library_dir) / f"{name} ({int(year)})"
    return Path(library_dir) / name


def build_target_path(
    library_dir: str,
    title: str,
    year: Optional[int],
    season: int,
    episode: int,
    extension: str,
    *,
    width: int,
) -> Path:
    """渲染单集目标路径（短剧处理器 TV 惯例）。

    ``{library_dir}/{剧名} ({年})/Season 1/{剧名} - S01E{NN}.ext``
    """
    # 季目录**不补零**：宿主短剧处理器与 Emby 侧的习惯都是 `Season 1`，
    # 补零成 `Season 01` 会和已有库目录并列出两套（2026-10-23 实测发现）。
    season_dir = build_drama_dir(library_dir, title, year) / f"Season {max(1, int(season or 1))}"
    filename = build_episode_name(title, season, episode, width=width, extension=extension)
    return season_dir / filename
