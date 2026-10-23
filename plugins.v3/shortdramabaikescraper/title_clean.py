"""输入剧名清洗：把带集数 / 演员 / Tag / 季号的乱命名洗成干净剧名（计划 §5.1.1）。

典型输入（MP 给电视剧取的是**父目录名**）::

    一品猎罪师（70集）潘子剑&上淇等 - SKIT
    一品猎罪师（70集）潘子剑&上淇等 - SKIT/一品猎罪师 - S01E07.mp4
    以爱为家第二季

输出是一组**有序候选**（最干净在前），交给识别管线依次做 exact 匹配、再退到站内搜索。

纪律：
* **只作用于输入查询**，绝不动 ``baike.name``（存储侧仍存原文、仍 ``WHERE name = ?``）；
* 不丢原串——原串永远在候选末尾兜底，清洗失败最坏退化为原样匹配；
* 「括号」只在能安全切分时才用（标题本身带括号的合法剧名靠原串候选保命）。
"""

from __future__ import annotations

import re
from typing import Optional

# 季集号：S01E07 / EP07 / E07 / 第70集
_EPISODE_RE = re.compile(
    r"(?:[Ss]\d{1,3}\s*[Ee]\d{1,4}|[Ee][Pp]?\s?\d{1,4}|第\s*\d{1,4}\s*[集话期])"
)
# 纯季号（无集号）：第二季 / S2 → 剥掉才能命中站点存的基名
_SEASON_RE = re.compile(
    r"(?:第\s*[一二三四五六七八九十百零〇0-9]{1,3}\s*季"
    r"|(?<![A-Za-z])[Ss]\d{1,3}(?![0-9Ee]))"
)
# 括号（含内容）：全角/半角/方头/方括号
_BRACKET_RE = re.compile(r"[（(【\[][^）)】\]]*[）)】\]]")
_OPEN_BRACKET_RE = re.compile(r"[（(【\[]")
# Tag 词（大小写不敏感）。SKIT 不加 \b：中文字符也属 \w，边界判断在中文旁边不可靠
_TAG_RE = re.compile(
    r"(?i)(?:SKIT|竖屏|横屏|完整版|未删减|无删减|高清版|超清|高清|全集|"
    r"(?:1080|720|2160|480)\s?[Pp]|4[Kk]|WEB[- ]?DL|HDR|HDTV)"
)
# 尾部人名串：``潘子剑&上淇等`` / ``张三、李四``；允许后面残留分隔符/空白
# （剥掉 Tag ``SKIT`` 之后尾部常留下 `` - ``，不允许就会漏剥）
_ACTOR_TAIL_RE = re.compile(
    r"[\u4e00-\u9fa5·]{2,6}(?:[&、][\u4e00-\u9fa5·]{2,6})+等?\s*[-_—–\s]*$"
)
# 书名号脱壳：``短剧《越界贪欢》`` / ``《越界贪欢》``
_BOOK_TITLE_RE = re.compile(r"^[^《]{0,8}《([^》]{1,80})》$")
# 方括号（短剧发布组把中文名塞这里）：``[... 念念归秦 | 全70集 | 2026年 | 类型：悬疑 ...]``
_SQUARE_BRACKET_RE = re.compile(r"[\[【]([^\[\]【】]{1,200})[\]】]")
# **开头**的方括号标签：``[2X免费]实习生掌权…`` / ``【独家】某某``
# 与「后缀方括号装中文名」是两种相反形态，必须分开处理（见 ``_drop_leading_bracket``）
_LEADING_BRACKET_RE = re.compile(r"^\s*[\[【(（]([^\[\]【】()（）]{1,30})[\]】)）]\s*")
# 方括号首段若是「纯描述」就不当剧名：全70集 / 2026年 / 类型：xxx
_DESCRIPTIVE_RE = re.compile(r"^(?:全?\s*\d+\s*[集话期]|\d{4}\s*年?|类型\s*[:：]|主演\s*[:：]|导演\s*[:：])")
# 括号内容「像噪音」的判据：集数 / 演员串 / Tag / 纯数字
_BRACKET_NOISE_RE = re.compile(
    r"(?:\d+\s*[集话期]|全\s*\d+\s*集|[&、]|SKIT|竖屏|横屏|完整版|未删减|"
    r"(?:1080|720|2160|480)\s?[Pp]|4[Kk]|^\s*\d+\s*$)",
    re.I,
)
# 分隔符（取首个之前）
_SEP_RE = re.compile(r"\s*[-_—–]\s+|\s+[-_—–]\s*|_")
# 首尾要剥掉的杂字符
_TRIM_CHARS = " \t\r\n-—_.,，。:：|/\\"


def _drop_episodes(text: str) -> str:
    """去季集号。"""
    return _EPISODE_RE.sub(" ", text)


def _drop_season(text: str) -> str:
    """去纯季号后缀（``以爱为家第二季`` → ``以爱为家``）。"""
    return _SEASON_RE.sub(" ", text)


# ── 季号提取（识别侧「第 N 季」独立词条匹配用） ────────────────────────
# 与 ``_SEASON_RE``（清洗用，只判「有没有」）不同，这里要把**数字**拿出来。
# ASCII 形态连 ``S02E01`` 里的季号也要吃 —— 整理插件按目录名识别时季号只在
# 名字里（``隐身侍卫 S02（90集）…``），宿主给文件 meta 时也可能没有
# ``begin_season``，所以不能沿用 ``(?![0-9Ee])`` 的尾判。
_SEASON_NUM_ASCII_RE = re.compile(r"(?<![A-Za-z0-9])[Ss]\s*0*(\d{1,2})(?![0-9])")
_SEASON_NUM_ARABIC_RE = re.compile(r"第\s*(\d{1,2})\s*季")
_SEASON_NUM_CN_RE = re.compile(r"第\s*([一二两三四五六七八九十]{1,3})\s*季")

_CN_DIGIT = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}


def _cn_int(text: str) -> Optional[int]:
    """中文数字（``二`` / ``十`` / ``十二`` / ``二十`` / ``二十五``）→ int。"""
    if not text:
        return None
    if text == "十":
        return 10
    if "十" in text:
        left, _, right = text.partition("十")
        if left and left not in _CN_DIGIT:
            return None
        if right and right not in _CN_DIGIT:
            return None
        tens = _CN_DIGIT.get(left, 1)
        ones = _CN_DIGIT.get(right, 0)
        return tens * 10 + ones
    return _CN_DIGIT.get(text)


def season_of_text(text: str) -> Optional[int]:
    """从**识别入参**（目录名 / 文件名 / meta 标题）里挖季号。

    ``S02`` / ``S2`` / ``S02E01`` / ``第2季`` / ``第二季`` 都认；挖不到返回
    ``None``。站点把第 N 季拆成独立词条（``隐身侍卫`` / ``隐身侍卫第二季``），
    不认季号就把第 2 季起的发布全部错认到第一季词条。
    """
    if not text:
        return None
    for pattern in (_SEASON_NUM_ARABIC_RE, _SEASON_NUM_CN_RE):
        hit = pattern.search(text)
        if hit:
            value = _cn_int(hit.group(1)) if pattern is _SEASON_NUM_CN_RE else int(hit.group(1))
            if value:
                return value
    hit = _SEASON_NUM_ASCII_RE.search(text)
    if hit:
        value = int(hit.group(1))
        if value:
            return value
    return None


_CN_NUMERAL = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八", 9: "九"}


def cn_season_numeral(season: int) -> str:
    """1-99 → 中文数字（站点独立季词条存的是「第二季」这种写法）。"""
    if season < 1 or season > 99:
        return ""
    if season < 10:
        return _CN_NUMERAL[season]
    tens, ones = divmod(season, 10)
    head = "十" if tens == 1 else _CN_NUMERAL[tens] + "十"
    return head + (_CN_NUMERAL[ones] if ones else "")


def season_suffixes(season: Optional[int]) -> list[str]:
    """站点独立季词条的名字后缀（中文数字优先——站点那么存）。"""
    if not season or season < 2:
        return []
    out: list[str] = []
    cn = cn_season_numeral(season)
    if cn:
        out.append(f"第{cn}季")
    out.append(f"第{season}季")
    return out


def has_season_suffix(name: str, season: Optional[int]) -> bool:
    """候选名是否带指定季号的后缀（``隐身侍卫第二季`` + 2 → True）。"""
    if not name or not season or season < 2:
        return False
    return any(suffix in name for suffix in season_suffixes(season))


def _drop_brackets(text: str) -> str:
    """去括号及其内容（集数 / 演员 / TAG 常塞在括号里）。

    **只在括号内容像噪音时生效**：``XX（番外篇）`` 这类合法剧名必须原样保留，
    否则首个候选会变成 ``XX``，拿它去站内搜索会捞回一堆不相关结果。
    """
    if "（" not in text and "(" not in text and "【" not in text and "[" not in text:
        return text
    if not _bracket_looks_like_noise(text):
        return text
    return _BRACKET_RE.sub(" ", text)


def _drop_tags(text: str) -> str:
    """去 Tag 词（SKIT / 竖屏 / 分辨率 …）。"""
    return _TAG_RE.sub(" ", text)


def _drop_actor_tail(text: str) -> str:
    """剥尾部「人名&人名等」串。"""
    return _ACTOR_TAIL_RE.sub(" ", text)


def _cut_at_separator(text: str) -> str:
    """首个分隔符之前截断（标题永远在最前）。"""
    match = _SEP_RE.search(text)
    if match and match.start() > 0:
        return text[: match.start()]
    return text


def _unwrap_book_title(text: str) -> str:
    """书名号脱壳：``短剧《越界贪欢》`` → ``越界贪欢``。"""
    match = _BOOK_TITLE_RE.match(text or "")
    return match.group(1).strip() if match else text


def _cut_before_bracket(text: str) -> str:
    """首个左括号之前截断——短剧标题在最前，第一个左括号后必是集数/演员/TAG。"""
    match = _OPEN_BRACKET_RE.search(text)
    if match and match.start() > 0:
        return text[: match.start()]
    return ""


def _drop_leading_bracket(text: str) -> str:
    """剥掉**开头**的方括号标签（``[2X免费]`` / ``【独家】``），后面还有正文才剥。

    实测种子::

        [2X免费]实习生掌权，三月干垮整家公司（57集） - SKIT

    这里方括号里是**营销标签**而不是剧名 —— 与 ``[念念归秦 | 全70集]``（方括号在后、
    装的是名字）恰好相反。不剥的话：
    ① 候选首位会是 ``2X免费``，拿它去站内搜索必然 0 结果；
    ② ``（57集）`` 永远轮不到被剥（``_drop_brackets`` 只看**首个**括号）。

    保守判据（宁可少剥，不可误杀）：方括号内容 ≤ 8 字、不含集/话/期、且剥完剩余
    仍有 ≥ 4 字正文。``【重生】之恋`` 这种「括号即名字一部分」的形态不会被剥。
    """
    match = _LEADING_BRACKET_RE.match(text or "")
    if not match:
        return text
    content = match.group(1).strip()
    rest = text[match.end() :].strip()
    if len(content) > 8 or re.search(r"[集话期]", content):
        return text
    if len(rest) < 4 or not re.search(r"[\u4e00-\u9fa5]", rest):
        return text
    return rest


def _bracket_looks_like_noise(text: str) -> bool:
    """首个括号里的内容是否像「集数 / 演员 / TAG」。

    像噪音才把「括号前截断」当首选；否则（如 ``XX（番外篇）``）只是多留一个候选、
    排在后面——绝不因为截断而丢掉合法剧名。
    """
    match = _OPEN_BRACKET_RE.search(text or "")
    if not match:
        return False
    rest = text[match.start() :]
    close = _BRACKET_RE.search(rest)
    if not close:
        return False
    return bool(_BRACKET_NOISE_RE.search(close.group(0)))


def _cut_at_dot_release(text: str) -> str:
    """``中文名.拼音.年份.S01E66.1080p.WEB-DL…`` → ``中文名``。

    短剧发布组（GodDramas / SKIT 等）最常见的一种命名：中文名后面用 ``.`` 接**拼音**、
    年份和规格串。站点只认中文（见 :func:`_has_cjk`），拼音段拿去搜必然 0 结果。

    判据是「**第一个后面跟着纯 ASCII 段的点**」而不是「第一个点」：

    * ``顾机长，太太说自己已守寡三年.Gu.Ji.Zhang…`` → 第 1 段后是 ``Gu`` ⇒ 截到第 1 段；
    * ``重生.我一心求死.2025.S01E01`` → 第 2 段仍含中文 ⇒ 跳过，截到 ``重生.我一心求死``
      （合法带点的中文剧名不会被截断）；
    * ``1.5米的她.1080p`` → 截断点之前没有中文 ⇒ 原样返回。

    截断后的串仍要过后续阶梯（去季集、去 Tag、去演员串），这里只负责砍掉后缀噪音。
    """
    raw = text or ""
    if "." not in raw:
        return raw
    parts = raw.split(".")
    for index in range(len(parts) - 1):
        nxt = parts[index + 1].strip()
        if not nxt or _has_cjk(nxt):
            continue
        if not re.fullmatch(r"[A-Za-z0-9 _\-]+", nxt):
            continue
        head = ".".join(parts[: index + 1]).strip()
        return head if _has_cjk(head) else raw
    return raw


def _has_cjk(text: str) -> bool:
    """是否含中文字符（本数据源只收中文名，纯 ASCII 候选没有检索价值）。"""
    return bool(re.search(r"[\u4e00-\u9fa5]", text or ""))


# 渐进剥离的变换序列，顺序有依赖：先砍掉「.拼音.规格」后缀，再剥季集号/季号，
# 再剥括号，才露得出 Tag 与演员串
_STEPS = (
    _cut_at_dot_release,
    _unwrap_book_title,
    # 前缀标签必须在剥括号之前：``[2X免费]X（57集）`` 剥掉前缀后，
    # ``（57集）`` 才会成为「首个括号」而被 ``_drop_brackets`` 处理
    _drop_leading_bracket,
    _drop_episodes,
    _drop_season,
    _drop_brackets,
    _drop_tags,
    _drop_actor_tail,
    _cut_at_separator,
)


def _tidy(text: str) -> str:
    """折叠空白并剥掉首尾杂字符。"""
    return re.sub(r"\s+", " ", text or "").strip().strip(_TRIM_CHARS).strip()


def _bracket_titles(raw: str) -> list[str]:
    """方括号里的中文名（短剧发布组的标准命名形态，可信度最高）。

    实测种子::

        Nian Nian Gui Qin 2026 S01 720p WEB-DL H.265 AAC-GodDramas
            [念念归秦 | 全70集 | 2026年 | 网络收费短剧 | 类型：悬疑 学霸 家庭]

    ``meta.title`` 取到的是**整串**（拼音 + 分辨率 + 方括号），拼音打站内搜索必然 0 结果；
    真正的中文名在方括号首段。所以这类候选必须排在**最前**，比任何剥离结果都可信。

    但**开头的方括号不算**：``[2X免费]实习生掌权…`` / ``【重生】之恋`` 里，方括号是
    营销标签 / 名字的一部分，只有「位置不在串首、或后面已无正文」的方括号才是名字容器
    （``_drop_leading_bracket`` 负责剥前缀，两者判据互补）。
    """
    out: list[str] = []
    raw = raw or ""
    for match in _SQUARE_BRACKET_RE.finditer(raw):
        # 前缀方括号 + 后面还有正文 ⇒ 这是标签，不是名字
        if match.start() == 0 and raw[match.end() :].strip():
            continue
        content = match.group(1)
        first = re.split(r"[|｜]", content)[0].strip()
        if not first or not re.search(r"[\u4e00-\u9fa5]", first):
            continue
        if _DESCRIPTIVE_RE.match(first):
            continue
        out.append(first)
    return out


def _strip_extension(name: str) -> str:
    """去扩展名（只认 2~5 位字母数字，避免把 ``S01.E07`` 当扩展名）。"""
    match = re.search(r"\.([A-Za-z0-9]{2,5})$", name or "")
    if match:
        return name[: match.start()]
    return name or ""


def _sources(text: str) -> list[str]:
    """一个输入 → 取名来源。

    * 含路径分隔符：只取**父目录名**与**文件名（去扩展名）**——整串带路径的形态
      洗出来全是噪音候选（实测会产出 ``… - SKIT/一品猎罪师 - .mp4`` 这类垃圾）；
    * 纯文件名：去扩展名后的名字 + 原串（原串兜底）。
    """
    raw = (text or "").strip()
    if not raw:
        return []
    parts = [part for part in re.split(r"[\\/]+", raw) if part]
    if len(parts) >= 2:
        return [parts[-2], _strip_extension(parts[-1])]
    # 纯文件名：只留去扩展名后的形态——带 ``.mp4`` 的原串剥完集号会剩
    # ``一品猎罪师 - .mp4`` 这种垃圾候选，没有任何匹配价值
    return [_strip_extension(raw)]


def _rungs(text: str) -> list[str]:
    """逐级剥离的阶梯（第 0 级是原串，末级最干净）。"""
    rungs = [text]
    current = text
    for step in _STEPS:
        nxt = step(current)
        if nxt != current:
            current = nxt
            rungs.append(current)
    return rungs


def clean_candidates(*sources: str) -> list[str]:
    """生成有序候选（最干净在前、去重、原串兜底）。

    ``sources`` 可传宿主 ``MetaInfo.title``、文件名、完整路径，或任意组合。
    """
    out: list[str] = []
    seen: set[str] = set()
    for source in sources:
        for raw in _sources(source):
            ordered: list[str] = []
            # 0) 方括号内的中文名最可信（短剧种子的标准命名，见 ``_bracket_titles``）
            ordered.extend(_bracket_titles(raw))
            # 「首个左括号前截断」只在括号内像集数/演员/TAG 时排第一；
            # 否则放到最高优先级之外（如 ``XX（番外篇）``→``XX`` 不许盖过原名）
            cut = _cut_before_bracket(raw)
            if cut and _bracket_looks_like_noise(raw):
                ordered.append(cut)
            # 阶梯逆序 = 最干净 → 最原始
            ordered.extend(reversed(_rungs(raw)))
            if cut and not _bracket_looks_like_noise(raw):
                ordered.append(cut)
            for candidate in ordered:
                cleaned = _tidy(candidate)
                if not cleaned:
                    continue
                # 中间态常留下「已剥 Tag 但没剥演员串」的形态（``X 潘子剑&上淇等``），
                # 再剥一次尾部人名，避免产出无意义的候选
                cleaned = _tidy(_drop_actor_tail(cleaned)) or cleaned
                if cleaned in seen:
                    continue
                seen.add(cleaned)
                out.append(cleaned)
    return out


def primary_name(*sources: str) -> str:
    """最干净的单个剧名（候选首位）；全空时返回空串。"""
    candidates = clean_candidates(*sources)
    return candidates[0] if candidates else ""
