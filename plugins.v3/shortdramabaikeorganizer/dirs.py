"""目录候选：系统配置里的目录 + 目录浏览接口。

配置页要「选择目录」，候选有两个来源（用户 2026-10-22 要求）：

1. **读取系统配置的目录**：宿主「设置 → 目录」里的整理目录条目
   （``SystemConfigKey.Directories``，元素结构见宿主 ``TransferDirectoryConf``）。
   下载目录与媒体库目录天然成对，还带 ``media_category`` /
   ``library_category_folder`` 这类子目录开关，比让用户手打绝对路径可靠。
2. **浏览目录**：下拉只列上面的根目录；要往下走就点「浏览目录」按钮，
   由前端弹窗调 :func:`browse` 一层层进（**不在下拉里摊平子目录** ——
   用户 2026-10-22 明确要求，摊平会把一两百个剧目录灌进下拉）。

排序是**短剧优先**（实测：15 个目录配置里只有一条是短剧，不排前面会被动漫番剧挤掉）：

* 名称/分类含「短剧」的条目 → 根目录（+ 分类子目录，若开关打开或目录真实存在）；
* 其它条目 → 只列根目录；
* 最后是常见挂载兜底（``/downloads``、``/media``，存在才列）。

本模块只做纯逻辑 + ``os.scandir``，**不 import 宿主**：系统配置由调用方
（``__init__._directory_confs()``）读好传进来，单测可以直接喂 dict 列表。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .constants import (
    CATEGORY_SHORT_DRAMA,
    DIR_OPTION_PER_ROOT,
    DIR_OPTION_TOTAL,
    DOWNLOAD_ROOTS,
    LIBRARY_ROOTS,
)
from .serialize import safe_str


# ---------------------------------------------------------------- 值归一

def as_path(value: Any) -> str:
    """把单个目录值归一成字符串。

    ``VCombobox`` 可能把值存成 ``{"title": ..., "value": ...}`` 对象
    （certmanager 踩过），也可能存成单元素列表，这里一并容错。
    """
    if isinstance(value, dict):
        value = value.get("value") or value.get("title")
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return _norm_path(safe_str(value))


def as_path_list(value: Any) -> list[str]:
    """把配置值归一成去重的路径列表（兼容换行字符串 / 列表 / 对象列表）。"""
    if isinstance(value, str):
        raw: list[Any] = [line.strip() for line in value.splitlines()]
    elif isinstance(value, (list, tuple, set)):
        raw = [as_path(item) for item in value]
    elif isinstance(value, dict):
        raw = [as_path(value)]
    else:
        raw = []

    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        path = as_path(item)
        if path and path not in seen:
            seen.add(path)
            out.append(path)
    return out


def normalize_directory_confs(raw: Any) -> list[dict]:
    """只保留结构合法的目录配置条目（容错历史残留的脏数据）。"""
    if not isinstance(raw, (list, tuple)):
        return []
    return [dict(item) for item in raw if isinstance(item, dict)]


def _norm_path(text: str) -> str:
    """去掉结尾斜杠（保留根 ``/`` 与 Windows 盘符根），便于去重与比较。"""
    value = safe_str(text)
    if len(value) > 1:
        trimmed = value.rstrip("/\\")
        if trimmed:
            return trimmed
    return value


# ---------------------------------------------------------------- 文件系统

def _subdir_paths(base: str | Path, limit: int = DIR_OPTION_PER_ROOT) -> list[Path]:
    """列出目录下的一级子目录（自然序，最多 ``limit`` 个；异常降级为空）。"""
    try:
        root = Path(base)
        if not root.is_dir():
            return []
        entries: list[Path] = []
        with os.scandir(root) as scan:
            for entry in scan:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        entries.append(Path(entry.path))
                except OSError:
                    continue
        entries.sort(key=lambda item: item.name.lower())
        return entries[:limit]
    except OSError:
        return []


def _join(base: str, name: str) -> str:
    return _norm_path(os.path.join(str(base).rstrip("/\\"), str(name)))


def _abs_or_join(base: str, path_like: str) -> str:
    """分类字段可能是名称，也可能是宿主存下的路径快照。"""
    text = safe_str(path_like)
    if not text:
        return ""
    if text.startswith("/") or (len(text) > 2 and text[1] == ":"):
        return _norm_path(text)
    return _join(base, text)


def _is_short_drama(conf: dict) -> bool:
    """目录配置是否就是短剧库/短剧下载目录。"""
    text = " ".join(
        safe_str(conf.get(key))
        for key in ("name", "media_category", "media_category_id", "download_path", "library_path")
    )
    return CATEGORY_SHORT_DRAMA in text


# ---------------------------------------------------------------- 候选构建

def _append(options: list[dict], seen: set[str], title: str, value: str) -> None:
    """去重追加一条候选（同 value 只留第一次出现的标题）。"""
    path = _norm_path(value)
    if not path or path in seen:
        return
    seen.add(path)
    options.append({"title": title, "value": path})


def _conf_path(conf: dict, key: str) -> str:
    return as_path(conf.get(key))


def _collect(
    confs: list[dict],
    *,
    path_key: str,
    storage_key: str,
    root_label: str,
    category_key: str = "",
    roots: tuple[str, ...],
) -> list[dict]:
    """统一的候选装配：短剧条目（根+子目录）→ 其它条目（只根）→ 挂载兜底。"""
    options: list[dict] = []
    seen: set[str] = set()

    local: list[dict] = []
    for conf in confs:
        storage = safe_str(conf.get(storage_key)) or "local"
        base = _conf_path(conf, path_key)
        if storage != "local" or not base:
            continue
        local.append(conf)

    prioritized = [conf for conf in local if _is_short_drama(conf)]
    prioritized_ids = {id(conf) for conf in prioritized}
    others = [conf for conf in local if id(conf) not in prioritized_ids]

    # 1) 短剧条目：根 + 分类子目录（**不再摊平子目录** —— 用户 2026-10-22 明确：
    #    下拉只列系统配置的目录，要进子目录走「浏览目录」按钮）
    for conf in prioritized:
        base = _conf_path(conf, path_key)
        name = safe_str(conf.get("name")) or base
        _append(options, seen, f"{root_label} · {name}", base)

        if category_key:
            category = safe_str(conf.get("media_category")) or safe_str(conf.get("media_category_id"))
            category_path = _abs_or_join(base, category) if category else ""
            # 开关打开时一定列；没开但目录真实存在也列（常见手工建好的分类库）
            if category_path and (conf.get(category_key) or Path(category_path).is_dir()):
                _append(options, seen, f"{root_label} · {name} / {category}", category_path)

    # 2) 其它条目：只列根
    for conf in others:
        base = _conf_path(conf, path_key)
        name = safe_str(conf.get("name")) or base
        _append(options, seen, f"{root_label} · {name}", base)

    # 3) 挂载兜底：容器里没配对应目录配置时也能选
    for root in roots:
        if not Path(root).is_dir():
            continue
        _append(options, seen, f"挂载目录 · {root}", root)

    return options[:DIR_OPTION_TOTAL]


def download_options(raw_dirs: Any) -> list[dict]:
    """下载侧候选（扫描根）：短剧目录优先，其余配置目录只给根。"""
    return _collect(
        normalize_directory_confs(raw_dirs),
        path_key="download_path",
        storage_key="storage",
        root_label="下载目录",
        category_key="download_category_folder",
        roots=DOWNLOAD_ROOTS,
    )


def library_options(raw_dirs: Any) -> list[dict]:
    """媒体库侧候选（目标库根）：短剧库优先，其余配置库只给根。"""
    return _collect(
        normalize_directory_confs(raw_dirs),
        path_key="library_path",
        storage_key="library_storage",
        root_label="媒体库",
        category_key="library_category_folder",
        roots=LIBRARY_ROOTS,
    )


# ---------------------------------------------------------------- 浏览接口

def browse(base: str = "") -> dict:
    """浏览一层目录，返回当前路径 / 上级 / 子目录（供 ``/dirs/browse`` 使用）。"""
    root = Path(base) if safe_str(base) else Path("/")
    if not root.is_dir():
        root = Path("/")

    children = _subdir_paths(root, DIR_OPTION_PER_ROOT * 2)
    root_text = str(root)
    parent = root_text if root_text == root.anchor else str(root.parent)

    return {
        "path": root_text,
        "parent": parent,
        # 兼容旧调用方：纯名字列表
        "dirs": [item.name for item in children],
        "entries": [{"title": item.name, "value": str(item)} for item in children],
    }
