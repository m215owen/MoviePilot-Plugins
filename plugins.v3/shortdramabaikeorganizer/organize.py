"""自包含整理引擎：扫描、规划、搬运、刮削检测。

**关键约束（用户 2026-10-22）：整理完全不走系统的方式。**

本模块**不**调用宿主 ``TransferChain`` / ``manual_transfer``，也不进宿主整理队列；
文件搬运由 ``transfer_file`` 直接用标准库完成。命名规则照搬宿主「短剧处理器」的
TV 惯例（``{剧名} ({年})/Season {季}/{剧名} - S{季:02d}E{NN}.ext``，季号取数据源
MediaInfo 的 ``season``、缺省 1）。整理历史由调用方
（``history.py`` / ``__init__.py``）写入系统 ``TransferHistoryOper``。

刮削（写 nfo / 海报）**同样自包含**（2026-10-23 起）：``scrape.py`` 直调 djbaike
数据源的 ``metadata_nfo`` / ``metadata_img`` 取素材，自己落盘到剧目录，不发
``MetadataScrape`` 事件、不进宿主刮削链。本模块只负责**检测**目标是否已刮削
（:func:`is_scraped`）。
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional

from .constants import (
    SCRAPE_IMAGE_NAMES,
    SCRAPE_NFO_NAMES,
    VIDEO_EXTENSIONS,
)
from .naming import build_target_path, extract_episode, natural_key


def iter_drama_dirs(source_dirs: list[str], scan_depth: int, excludes: list[str]) -> list[Path]:
    """扫描源目录，返回「每部剧一个目录」的列表。

    :param scan_depth: 1 = 只把源目录下的一级子目录当作一部剧；
        N = 继续向下 N-1 层（每层取子目录）
    :param excludes: 排除的路径片段（子串匹配，大小写不敏感）
    """
    depth = max(1, int(scan_depth or 1))
    exclude_l = [str(x).strip().lower() for x in excludes if x and str(x).strip()]

    def _walk(current: Path, level: int) -> list[Path]:
        out: list[Path] = []
        if level > depth:
            return out
        try:
            entries = [p for p in current.iterdir() if p.is_dir()]
        except OSError:
            return out
        for sub in sorted(entries, key=lambda p: natural_key(p.name)):
            if any(token in sub.name.lower() for token in exclude_l):
                continue
            if level == depth:
                out.append(sub)
            else:
                out.extend(_walk(sub, level + 1))
        return out

    results: list[Path] = []
    for root in source_dirs:
        root_path = Path(root.strip())
        if not root_path or not root_path.is_dir():
            continue
        if depth <= 1:
            for sub in sorted(root_path.iterdir(), key=lambda p: natural_key(p.name)):
                if sub.is_dir() and not any(tok in sub.name.lower() for tok in exclude_l):
                    results.append(sub)
        else:
            results.extend(_walk(root_path, 2))
    return results


def list_video_files(drama_dir: Path) -> list[Path]:
    """列出剧目录下的视频文件，按自然序排序。"""
    if not drama_dir or not Path(drama_dir).is_dir():
        return []
    allowed = {str(ext).lower() for ext in VIDEO_EXTENSIONS}
    files = [p for p in Path(drama_dir).iterdir() if p.is_file() and p.suffix.lower() in allowed]
    files.sort(key=lambda p: natural_key(p.name))
    return files


def plan_files(
    drama_dir: Path,
    *,
    title: str,
    year: Optional[int],
    library_dir: str,
    episode_width: int,
    auto_rename: bool,
    season: int = 1,
) -> list[tuple[Path, Path, int]]:
    """为一部剧计算「源 → 目标 → 集号」计划（只计算，不搬运）。

    集号：优先从源文件名提取；提取不到且 ``auto_rename`` 为真时按自然序补齐
    （自包含模式绕过宿主集号解析，必须自己补，否则所有文件会撞同一个 E001）。

    季号：**从源数据（数据源 MediaInfo）取**，由调用方传入（2026-10-23 用户
    「季号从源数据取」）。数据源不给时回落 1，行为与改造前一致。同一部剧的
    多个源目录（S01 / S02 各一个目录）靠它归到同一剧目录下的不同 Season，
    不再互相覆盖 —— 之前写死 season=1 时第二季会把第一季的目标路径全撞上。
    """
    videos = list_video_files(drama_dir)
    plans: list[tuple[Path, Path, int]] = []
    used: set[int] = set()
    season_no = max(1, min(99, int(season or 1)))
    for position, src in enumerate(videos, start=1):
        episode = extract_episode(src.stem)
        if episode is None:
            if not auto_rename:
                # 不补齐则跳过该文件（无法给目标集号）
                continue
            candidate = position
            while candidate in used:
                candidate += 1
            episode = candidate
        elif episode in used:
            # 同集号重复（多版本）：保留按首个，避免互相覆盖
            continue
        used.add(episode)
        target = build_target_path(
            library_dir,
            title,
            year,
            season=season_no,
            episode=episode,
            extension=src.suffix,
            width=episode_width,
        )
        plans.append((src, target, episode))
    return plans


def is_scraped(drama_dir: Path | str) -> bool:
    """目标剧目录是否已被刮削过（有 nfo / 海报等元数据产物）。

    判定范围：剧目录本身 + 它的一级子目录（短剧只有 ``Season 1`` 一层）。
    只看元数据文件，不看视频 —— 判断的是「刮削过没有」，不是「有没有文件」。
    """
    try:
        root = Path(drama_dir)
        if not root.is_dir():
            return False
        nfo_names = {name.lower() for name in SCRAPE_NFO_NAMES}
        image_names = {name.lower() for name in SCRAPE_IMAGE_NAMES}

        def _has_meta(directory: Path) -> bool:
            try:
                entries = list(os.scandir(directory))
            except OSError:
                return False
            for entry in entries:
                name = entry.name.lower()
                if entry.is_file() and (name in nfo_names or name in image_names):
                    return True
                if entry.is_file() and name.endswith(".nfo"):
                    return True
            return False

        if _has_meta(root):
            return True
        for sub in root.iterdir():
            if sub.is_dir() and _has_meta(sub):
                return True
        return False
    except OSError:
        return False


def transfer_file(source: Path, target: Path, transfer_type: str) -> bool:
    """把源文件搬运到目标（自包含，不依赖宿主整理链）。

    :param transfer_type: move / copy / link / softlink
    :return: 是否成功
    """
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() or target.is_symlink():
            target.unlink()

        src_size = source.stat().st_size if source.exists() else 0

        mode = (transfer_type or "move").lower()
        if mode == "move":
            shutil.move(str(source), str(target))
        elif mode == "copy":
            shutil.copy2(str(source), str(target))
        elif mode == "softlink":
            os.symlink(str(source.resolve()), str(target))
        else:  # hard link
            os.link(str(source), str(target))

        if not target.exists():
            return False

        # 复制后校验大小一致（move/link 不适用）
        if mode == "copy" and src_size > 0:
            try:
                if target.stat().st_size != src_size:
                    return False
            except OSError:
                pass
        return True
    except Exception as err:  # pragma: no cover
        import logging

        logging.getLogger("ShortDramaBaikeOrganizer").error(
            f"[整理] 转移失败 {source} -> {target}: {err}"
        )
        return False
