"""豆瓣通道：``tv_search`` / ``tv_detail`` 的薄包装（计划 §5.1 第 ⑤⑥ 层）。

为什么复用宿主 ``DoubanApi`` 而不是自己发请求：

* 宿主已内建 Frodo 通道、UA 池与限流，插件不该重复实现；
* ``app.modules.*`` 属官方「仍可稳定使用的既有公开入口」（插件开发指南 §6）。

两个硬约束（都来自实测）：

1. **``DoubanApi`` 是 ``WeakSingleton``**——``DoubanApi()`` 拿的就是宿主同一实例，
   所以**绝不调用它的 ``close()``**，否则会影响宿主自身的豆瓣功能。
2. 方法全是**同步阻塞**的，必须丢到线程里跑（``asyncio.to_thread``），否则会阻塞事件循环。

另外：短剧在豆瓣一律 ``type=tv``，``movie_detail`` 对短剧返回空壳，所以只走 tv 通道。
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any, Optional

from app.sdk.logging import logger

from . import constants
from .media_id import entity_of, native_id_of

# 豆瓣 target_type 里可视为「影视作品」的取值
_TV_TYPES = {"tv", "movie"}

# ── 全局限流熔断 ──────────────────────────────────────────────────────
# 实测（2026-10-21/22）：Frodo 搜索过频返回 ``{"code":103,"msg":"need_login"}``。
# 但宿主自身（``app/runtime/rate.py`` 的 ``ExponentialBackoffRateLimiter``）对豆瓣
# 限流**并不是「硬封 30 分钟」**，而是**指数退避**：``base_wait=60s``、
# ``max_wait=600s``、``backoff_factor=2``、且**成功一次即重置回 60s 基线**。
# 我们照搬这套，避免误判成永久封禁把人晾着：
#   - 一碰 103 → 先等 60s；冷却期内又碰 → 120s → 240s → 480s → 封顶 600s；
#   - 任意一次「未限流的成功搜索」立即把退避重置回基线。
# 这样正常浏览（偶尔几次搜索）几乎不触发；即使被限，也会随成功自动恢复。
THROTTLE_CODE = "103"
COOLDOWN_BASE_SECONDS = 60.0
COOLDOWN_MAX_SECONDS = 600.0
COOLDOWN_BACKOFF = 2.0

_search_blocked_until = 0.0  # time.monotonic() 时刻（进程内全局，reload 即清）
_current_wait = COOLDOWN_BASE_SECONDS
_last_skip_log = 0.0


def _mono() -> float:
    return time.monotonic()


def search_blocked() -> bool:
    """豆瓣搜索是否处于熔断冷却期（仅搜索类接口；详情/人物详情不受限）。"""
    return _mono() < _search_blocked_until


def search_cooldown_remaining() -> float:
    """熔断剩余秒数（未熔断为 0）。"""
    return max(0.0, _search_blocked_until - _mono())


def _fmt_cooldown(seconds: float) -> str:
    """把秒数渲染成人类可读（<60s 用秒，否则用分钟）。"""
    if seconds < 60:
        return f"{seconds:.0f} 秒"
    return f"{seconds / 60:.1f} 分钟"


def _note_throttle(result: Any) -> None:
    """错误包是 103 限流 → 指数退避推进冷却；其它错误码不熔断。"""
    global _search_blocked_until, _current_wait
    if isinstance(result, dict) and str(result.get("code") or "") == THROTTLE_CODE:
        now = _mono()
        wait = _current_wait
        _search_blocked_until = now + wait
        _current_wait = min(_current_wait * COOLDOWN_BACKOFF, COOLDOWN_MAX_SECONDS)
        logger.warning(
            f"{constants.SOURCE_NAME} 豆瓣搜索被限流（code=103 need_login），"
            f"自动退避降温：本轮冷却约 {_fmt_cooldown(wait)}（封顶 "
            f"{_fmt_cooldown(COOLDOWN_MAX_SECONDS)}）；期间搜索请求不再发往豆瓣，"
            f"成功一次即恢复"
        )


def _reset_throttle() -> None:
    """成功一次（未触发 103）即把退避重置回基线（对齐宿主 reset_on_success）。"""
    global _search_blocked_until, _current_wait
    if _search_blocked_until != 0.0 or _current_wait > COOLDOWN_BASE_SECONDS:
        _search_blocked_until = 0.0
        _current_wait = COOLDOWN_BASE_SECONDS


def _strip_html(text: str) -> str:
    """豆瓣 ``desc`` 是富文本 HTML，剥成纯文本给展示层。"""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", str(text))
    return (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .strip()
    )


def _is_error_envelope(result: Any) -> bool:
    """Frodo 错误包判别：``{"code":…, "msg":…}`` 且 code 非 0。"""
    return (
        isinstance(result, dict)
        and "code" in result
        and result.get("code") not in (0, None, "0")
    )


def _api():
    """取宿主豆瓣客户端（弱单例，不要 close）。"""
    from app.modules.douban import DoubanApi

    return DoubanApi()


def _normalize_search_item(item: dict) -> Optional[dict]:
    """``tv_search`` 的一条结果 → 归一化候选。"""
    target = item.get("target") or {}
    subject_id = str(target.get("id") or item.get("target_id") or "").strip()
    if not subject_id:
        return None
    target_type = str(item.get("target_type") or "").strip().lower()
    if target_type and target_type not in _TV_TYPES:
        return None
    rating = target.get("rating") or {}
    return {
        "media_id": f"{constants.DOUBAN_WORK}:{subject_id}",
        "name": (target.get("title") or "").strip(),
        "year": str(target.get("year") or "").strip(),
        "card_subtitle": str(target.get("card_subtitle") or "").strip(),
        "cover_url": str(target.get("cover_url") or "").strip(),
        "rating": float(rating.get("value") or 0.0),
        "type_name": str(item.get("type_name") or "").strip(),
    }


def _tv_search_sync(keyword: str, count: int) -> list[dict]:
    """同步搜索（须在线程里调用）。"""
    global _last_skip_log
    if search_blocked():
        # 冷却期零网络直返空；告警最多 5 分钟一条，别把日志刷爆
        if _mono() - _last_skip_log >= 300.0:
            _last_skip_log = _mono()
            logger.warning(
                f"{constants.SOURCE_NAME} 豆瓣搜索熔断中（剩 "
                f"{_fmt_cooldown(search_cooldown_remaining())}），跳过 {keyword}"
            )
        return []
    try:
        result = _api().tv_search(keyword, start=0, count=count)
    except Exception as err:  # pragma: no cover - 网络/通道异常一律降级
        logger.warning(f"{constants.SOURCE_NAME} 豆瓣搜索失败 {keyword}：{err}")
        return []
    if not isinstance(result, dict):
        return []
    # 错误包判别（实测 2026-10-21：搜索过频时返回 ``{"code":103,"msg":"need_login"}``，
    # 没有 ``items`` 键）——必须告警而不是当成"无结果"，否则调用方会把限流误判成
    # "豆瓣没收录"，把本可回填的 id 永久空置。
    if "code" in result and result.get("code") not in (0, None, "0"):
        _note_throttle(result)
        logger.warning(
            f"{constants.SOURCE_NAME} 豆瓣搜索被拒 {keyword}："
            f"code={result.get('code')} msg={result.get('msg')}"
        )
        return []
    # 走到这里说明没被限流（成功响应），对齐宿主 reset_on_success 立即退避归零
    _reset_throttle()
    items = result.get("items") or []
    out: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_search_item(item)
        if normalized:
            out.append(normalized)
    return out


async def tv_search(keyword: str, count: int = 20) -> list[dict]:
    """豆瓣剧集搜索；百科 0 结果时才调用（计划 §5.1 第 ⑤ 层）。"""
    word = (keyword or "").strip()
    if not word:
        return []
    return await asyncio.to_thread(_tv_search_sync, word, max(1, int(count or 20)))


def _year_int(value: Any) -> int:
    """年份转 int；取不到返回 0。"""
    try:
        return int(str(value).strip()[:4])
    except (TypeError, ValueError):
        return 0


def _names(items: Any) -> list[dict]:
    """豆瓣 ``[{name}]`` → 本插件 detail 的演职人员结构。"""
    out: list[dict] = []
    for item in items or []:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
        else:
            name = str(item or "").strip()
        if name:
            out.append({"media_id": "", "name": name, "role": ""})
    return out


def _detail_from_tv(media_id: str, data: dict) -> dict:
    """``tv_detail`` 的 69 字段 → 与百科解析器**同构**的 detail dict。"""
    subject_id = native_id_of(media_id)
    pic = data.get("pic") or {}
    rating = data.get("rating") or {}
    durations = data.get("durations") or []
    countries = data.get("countries") or []
    pubdate = data.get("pubdate") or []
    aka = data.get("aka") or []
    genres = data.get("genres") or []
    return {
        "media_id": media_id,
        "name": str(data.get("title") or "").strip(),
        # 豆瓣不区分短剧/漫剧，留空交给展示层按前缀回退，绝不硬编「短剧」
        "kind": "",
        "year": _year_int(data.get("year")),
        "episodes": int(data.get("episodes_count") or 0),
        "overview": str(data.get("intro") or "").strip(),
        "tags": [str(tag) for tag in genres if tag],
        "actors": _names(data.get("actors")),
        "directors": _names(data.get("directors")),
        "rating": float(rating.get("value") or 0.0),
        "duration": str(durations[0]) if durations else "",
        "release_date": str(pubdate[0]) if pubdate else "",
        "platform": "",
        "platform_heat": "",
        "play_count": "",
        "favorite_count": "",
        "novel": None,
        "author": "",
        "aka": "、".join(str(item) for item in aka if item),
        "words": "",
        # 豆瓣海报无法由 id 反推，只能取 pic；下不下载交给宿主
        "poster_path": str(pic.get("large") or pic.get("normal") or ""),
        "detail_url": f"{constants.DOUBAN_MOVIE_BASE}/subject/{subject_id}/",
        "desc": " / ".join(
            part
            for part in (
                str(data.get("card_subtitle") or "").strip(),
                str(countries[0]) if countries else "",
            )
            if part
        ),
        # 豆瓣侧额外字段（不参与 MediaInfo 映射，仅供排查）
        "douban_subject": subject_id,
    }


def _tv_detail_sync(subject_id: str) -> Optional[dict]:
    """同步取豆瓣剧集详情（须在线程里调用）。"""
    try:
        data = _api().tv_detail(str(subject_id))
    except Exception as err:  # pragma: no cover - 网络/通道异常一律降级
        logger.warning(f"{constants.SOURCE_NAME} 豆瓣详情失败 {subject_id}：{err}")
        return None
    if not isinstance(data, dict) or not data:
        return None
    if str(data.get("type") or "") not in ("tv", "movie"):
        # 书 / 影人 / 音乐等，不属于剧集通道
        return None
    return _detail_from_tv(f"{constants.DOUBAN_WORK}:{subject_id}", data)


async def tv_detail(subject_id: str) -> Optional[dict]:
    """豆瓣剧集详情 → detail dict（写缓存与组装 MediaInfo 都用它）。"""
    sid = str(subject_id or "").strip()
    if not sid:
        return None
    return await asyncio.to_thread(_tv_detail_sync, sid)


def is_douban_work(media_id: str) -> bool:
    """是否 ``douban:{sid}`` 形式。"""
    return entity_of(media_id) == constants.DOUBAN_WORK


# ── 豆瓣人物（人物档案融合用，2026-10-22 实装） ───────────────────────

def _person_search_sync(keyword: str) -> list[dict]:
    """同步人物搜索（须在线程里调用）。"""
    global _last_skip_log
    if search_blocked():
        if _mono() - _last_skip_log >= 300.0:
            _last_skip_log = _mono()
            logger.warning(
                f"{constants.SOURCE_NAME} 豆瓣搜索熔断中（剩 "
                f"{_fmt_cooldown(search_cooldown_remaining())}），跳过人物搜索 {keyword}"
            )
        return []
    try:
        result = _api().person_search(keyword, start=0, count=10)
    except Exception as err:  # pragma: no cover - 网络/通道异常一律降级
        logger.warning(f"{constants.SOURCE_NAME} 豆瓣人物搜索失败 {keyword}：{err}")
        return []
    if _is_error_envelope(result):
        _note_throttle(result)
        logger.warning(
            f"{constants.SOURCE_NAME} 豆瓣人物搜索被拒 {keyword}："
            f"code={result.get('code')} msg={result.get('msg')}"
        )
        return []
    # 走到这里说明没被限流（成功响应），对齐宿主 reset_on_success 立即退避归零
    _reset_throttle()
    out: list[dict] = []
    for item in (result or {}).get("items") or []:
        if not isinstance(item, dict) or item.get("layout") != "person":
            continue
        target = item.get("target") or {}
        pid = str(target.get("id") or "").strip()
        if not pid.isdigit():
            continue
        out.append(
            {
                "media_id": f"{constants.DOUBAN_PERSON}:{pid}",
                "name": str(target.get("title") or "").strip(),
                "url": str(target.get("url") or "").strip(),
            }
        )
    return out


async def person_search(keyword: str) -> list[dict]:
    """按名搜豆瓣人物，出 ``doubanp:{pid}`` 候选（subject 空间的影人 id）。"""
    word = (keyword or "").strip()
    if not word:
        return []
    return await asyncio.to_thread(_person_search_sync, word)


def _year_from_short(short: str) -> str:
    """``extra.short_info`` 开头的 ``YYYY / …`` → 年份。"""
    hit = re.match(r"\s*(\d{4})\s*/", short or "")
    return hit.group(1) if hit else ""


def _rating_of(subject: dict) -> float:
    try:
        rating = ((subject.get("extra") or {}).get("rating_group") or {}).get("rating") or {}
        return round(float(rating.get("value") or 0.0), 1)
    except (TypeError, ValueError):
        return 0.0


def _person_from_detail(pid: str, data: dict) -> Optional[dict]:
    """``person_detail`` 原始载荷 → 归一化人物档案（含作品清单）。

    作品在 ``modules[type=work_collections].payload.collections[].works``，
    每条 ``{roles, subject:{id, title, cover, extra:{short_info, rating_group}}}``。
    **载荷只带首页约 10 条**（total 是全量数，翻页接口 ``person_work`` 已废，
    实测 404）——合并豆瓣作品时只能补最近这几部，如实告诉展示层。
    """
    if not isinstance(data, dict) or not data:
        return None
    works: list[dict] = []
    total = 0
    for module in data.get("modules") or []:
        if not isinstance(module, dict) or module.get("type") != "work_collections":
            continue
        for col in (module.get("payload") or {}).get("collections") or []:
            if not isinstance(col, dict):
                continue
            try:
                total += int(col.get("total") or 0)
            except (TypeError, ValueError):
                pass
            for work in col.get("works") or []:
                if not isinstance(work, dict):
                    continue
                subject = work.get("subject") or {}
                sid = str(subject.get("id") or "").strip()
                if not sid.isdigit():
                    continue
                extra = subject.get("extra") or {}
                cover = (subject.get("cover") or {}).get("large") or {}
                works.append(
                    {
                        "media_id": f"{constants.DOUBAN_WORK}:{sid}",
                        "name": str(subject.get("title") or "").strip(),
                        "year": _year_from_short(str(extra.get("short_info") or "")),
                        "poster": str(cover.get("url") or "").strip(),
                        "rating": _rating_of(subject),
                        "roles": [str(r) for r in work.get("roles") or [] if r],
                    }
                )
    name = str(data.get("title") or "").strip()
    if not name and not works:
        return None
    info_pairs = ((data.get("extra") or {}).get("info") or [])
    info: dict[str, str] = {}
    for pair in info_pairs:
        if isinstance(pair, (list, tuple)) and len(pair) >= 2:
            info[str(pair[0])] = str(pair[1])
    return {
        "media_id": f"{constants.DOUBAN_PERSON}:{pid}",
        "name": name,
        "desc": _strip_html(str(data.get("desc") or "")),
        "avatar": (
            (data.get("cover") or {}).get("url")
            or (data.get("cover_img") or {}).get("url")
            or ""
        ),
        "info": info,
        "works": works,
        "total": total or len(works),
        "url": str(data.get("sharing_url") or data.get("url") or ""),
    }


def _person_detail_sync(pid: str) -> Optional[dict]:
    """同步人物详情（须在线程里调用）。"""
    try:
        return _api().person_detail(int(pid))
    except Exception as err:  # pragma: no cover - 网络/通道异常一律降级
        logger.warning(f"{constants.SOURCE_NAME} 豆瓣人物详情失败 {pid}：{err}")
        return None


async def person_detail(pid: str) -> Optional[dict]:
    """豆瓣人物档案 + 作品清单（``doubanp:{pid}`` 的纯数字 pid）。"""
    sid = str(pid or "").strip()
    if not sid:
        return None
    data = await asyncio.to_thread(_person_detail_sync, sid)
    if _is_error_envelope(data):
        logger.warning(
            f"{constants.SOURCE_NAME} 豆瓣人物详情被拒 {sid}："
            f"code={data.get('code')} msg={data.get('msg')}"
        )
        return None
    return _person_from_detail(sid, data)
