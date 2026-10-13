"""订阅批量编辑器（MoviePilot V3 插件后端）。

功能：按规则筛选订阅，批量修改其订阅站点、下载器、保存路径、包含/排除规则、
洗版状态、订阅状态，以及订阅归属用户。

为什么需要它：MoviePilot 的订阅只能在详情页逐条修改；当订阅数量较多——尤其是
插件自动创建的一批订阅——逐条改写的成本极高。本插件把「筛选 + 批量改写」做成
一次可重复执行的动作，并支持在新增订阅时自动触发。

V3 契约要点
-----------
1. **依赖入口**：宿主依赖一律走 ``app.sdk.*`` 稳定入口（基类、日志、事件、
   配置、调度器）；订阅/站点/用户的数据访问走 ``app.sdk._legacy.subscribe`` /
   ``site`` / ``user``——这是宿主为兼容旧插件保留、但已收拢进 SDK 命名空间的
   官方入口。不直接引用 ``app.core`` / ``app.db`` / ``app.helper``。
2. **渲染模式**：使用宿主默认的 ``vuetify``（即 ``get_render_mode()`` 默认值），
   配置页与详情页都由后端下发 Vuetify 组件 JSON 渲染。因此本插件不需要自带
   前端构建产物，也不依赖模块联邦。
3. **一次性任务**：不再自建 ``BackgroundScheduler``（进程退出后无法回收、且与
   宿主调度器重复），改由 ``app.sdk.scheduler.add_plugin_once_job`` 托管，
   插件停用时用 ``remove_plugin_once_job`` 清理。
4. **「订阅来源」是本插件的核心差异点**：MoviePilot 中由插件发起的订阅会把
   ``username`` 直接写成**插件名**（本机实例实测出现 ``豆瓣演员订阅`` /
   ``embykit`` / ``订阅助手（增强版）``），这些取值不在系统用户表里，
   因此宿主的「订阅用户」筛选与常规插件都选不到它们。本插件在生成配置表单时
   **动态扫描订阅库**，把「系统用户 + 插件来源 + 无归属」合并成一个可多选的
   来源列表，使用户能够精确筛选并批量改写插件自动创建的订阅。
5. **写入安全**：批量写入前先读取每一条订阅的原值（用于通知与审计），且只提交
   用户显式设置的字段，避免把未配置的项误写成空值。
"""
from __future__ import annotations

import json
import threading
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.types import EventType, MediaType
from app.sdk.events import Event, eventmanager
from app.sdk.logging import logger
from app.sdk.plugin import _PluginBase

# 消息类型枚举在宿主版本间存在改名：V3.1+ 使用 MessageType，更早的实现使用
# NotificationType。做一次兼容性导入，避免因宿主版本差异导致插件整体加载失败。
try:  # pragma: no cover - 取决于宿主版本
    from app.schemas.types import MessageType as _MessageType
except ImportError:  # pragma: no cover
    from app.schemas.types import NotificationType as _MessageType  # type: ignore

# 插件展示名（同时作为模块常量，便于自检脚本静态比对）
PLUGIN_NAME = "订阅批量编辑器"

# 一次性任务 ID
_ONCE_JOB_ID = "batch_edit_once"

# 「无归属用户」哨兵值：订阅的 username 为空时用它表示。
# 用双下划线包裹是为了不与真实用户名 / 插件名冲突。
NO_OWNER = "__none__"

# 详情页最多列出的匹配条目数：只用于人类阅读，避免页面 JSON 过大
_PAGE_PREVIEW_LIMIT = 30

# 并发保护：事件触发与手动执行可能同时命中同一批订阅，串行化改写动作
_lock = threading.RLock()


# ─── 宿主数据入口（惰性获取，缺失时降级而不炸插件） ──────────────


def _subscribe_oper() -> Any:
    """获取订阅数据端口（V3 稳定入口）；宿主缺该入口时返回 None。"""
    try:
        from app.sdk._legacy.subscribe import SubscribeOper
    except Exception as err:  # pragma: no cover - 宿主版本差异兜底
        logger.debug(f"{PLUGIN_NAME} 未找到订阅数据入口：{err}")
        return None
    try:
        return SubscribeOper()
    except Exception as err:  # pragma: no cover - 宿主版本差异兜底
        logger.debug(f"{PLUGIN_NAME} 初始化订阅数据入口失败：{err}")
        return None


def _site_oper() -> Any:
    """获取站点数据端口；用于渲染「新站点」下拉。"""
    try:
        from app.sdk._legacy.site import SiteOper
    except Exception as err:  # pragma: no cover
        logger.debug(f"{PLUGIN_NAME} 未找到站点数据入口：{err}")
        return None
    try:
        return SiteOper()
    except Exception as err:  # pragma: no cover
        logger.debug(f"{PLUGIN_NAME} 初始化站点数据入口失败：{err}")
        return None


def _user_oper() -> Any:
    """获取用户数据端口；用于区分「系统用户」与「插件来源」。"""
    try:
        from app.sdk._legacy.user import UserOper
    except Exception as err:  # pragma: no cover
        logger.debug(f"{PLUGIN_NAME} 未找到用户数据入口：{err}")
        return None
    try:
        return UserOper()
    except Exception as err:  # pragma: no cover
        logger.debug(f"{PLUGIN_NAME} 初始化用户数据入口失败：{err}")
        return None


def _downloader_helper() -> Any:
    """获取下载器服务端口；用于渲染「新下载器」下拉。"""
    try:
        from app.sdk.services import DownloaderHelper
    except Exception as err:  # pragma: no cover
        logger.debug(f"{PLUGIN_NAME} 未找到下载器服务入口：{err}")
        return None
    try:
        return DownloaderHelper()
    except Exception as err:  # pragma: no cover
        logger.debug(f"{PLUGIN_NAME} 初始化下载器服务入口失败：{err}")
        return None


# ─── 配置值归一化工具 ────────────────────────────────────────────


def _as_list(value: Any) -> List[str]:
    """把多选值归一化成字符串列表。

    Vuetify 的 VSelect 多选时提交数组，但历史配置里也可能是 JSON 字符串
    （``["1","2"]``）或逗号分隔串，这里一并兼容，避免因配置格式差异丢项。
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
        except (ValueError, TypeError):
            parsed = None
        if isinstance(parsed, (list, tuple)):
            return [str(item).strip() for item in parsed if str(item).strip()]
    return [part.strip() for part in text.split(",") if part.strip()]


def _as_int(value: Any) -> Optional[int]:
    """把配置值转成整数；非法值返回 None（调用方按「未设置」处理）。"""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


class SubscribeBatchEditor(_PluginBase):
    """按规则筛选订阅并批量改写其可编辑项的插件。"""

    plugin_name = PLUGIN_NAME
    plugin_desc = (
        "按规则筛选订阅，批量修改订阅站点、下载器、保存路径、包含/排除规则、"
        "洗版状态、订阅状态与订阅归属用户；支持筛选由插件发起的订阅。"
    )
    plugin_icon = (
        "https://raw.githubusercontent.com/m215owen/MoviePilot-Plugins/"
        "main/icons/SubscribeBatchEditor.png"
    )
    plugin_version = "2.0.0"
    plugin_author = "m215owen"
    plugin_label = "订阅管理"
    plugin_config_prefix = "subscribebatcheditor_"
    plugin_order = 20
    auth_level = 1

    # ── 运行期状态 ──
    _enabled: bool = False
    _onlyonce: bool = False
    _notify: bool = False

    # ── 筛选规则 ──
    _filter_media_type: str = MediaType.TV.value
    _filter_episode_lt: str = ""
    _filter_episode_gt: str = ""
    _filter_usernames: List[str] = []
    _filter_best_version: str = ""

    # ── 修改策略 ──
    _modify_sites: List[str] = []
    _modify_downloader: str = ""
    _modify_save_path: str = ""
    _modify_include: str = ""
    _modify_exclude: str = ""
    _modify_best_version: str = ""
    _modify_state: str = ""
    _modify_username: str = ""

    # ─── 生命周期 ────────────────────────────────────────────────

    def init_plugin(self, config: dict | None = None) -> None:
        """读取配置并重建运行状态；宿主在启动与保存配置时都会调用，需可重复执行。"""
        # 先释放上一轮可能遗留的一次性任务，避免重复登记
        self.stop_service()

        cfg: Dict[str, Any] = dict(config or {})
        self._enabled = bool(cfg.get("enabled"))
        self._notify = bool(cfg.get("notify"))
        self._onlyonce = bool(cfg.get("onlyonce"))

        # 筛选规则
        self._filter_media_type = str(cfg.get("filter_media_type") or "").strip()
        self._filter_episode_lt = str(cfg.get("filter_episode_lt") or "").strip()
        self._filter_episode_gt = str(cfg.get("filter_episode_gt") or "").strip()
        self._filter_usernames = _as_list(cfg.get("filter_usernames"))
        self._filter_best_version = str(cfg.get("filter_best_version") or "").strip()

        # 修改策略
        self._modify_sites = _as_list(cfg.get("modify_sites"))
        self._modify_downloader = str(cfg.get("modify_downloader") or "").strip()
        self._modify_save_path = str(cfg.get("modify_save_path") or "").strip()
        self._modify_include = str(cfg.get("modify_include") or "").strip()
        self._modify_exclude = str(cfg.get("modify_exclude") or "").strip()
        self._modify_best_version = str(cfg.get("modify_best_version") or "").strip()
        self._modify_state = str(cfg.get("modify_state") or "").strip()
        self._modify_username = str(cfg.get("modify_username") or "").strip()

        # 勾选「立即运行一次」时交给宿主调度器延迟执行，而不是自建线程 / 调度器
        if self._enabled and self._onlyonce:
            if self._add_once_job(_ONCE_JOB_ID, 3):
                cfg["onlyonce"] = False
                self.update_config(cfg)
                logger.info(f"{PLUGIN_NAME} 已安排立即执行一次")

        logger.info(
            f"{PLUGIN_NAME} 初始化完成：enabled={self._enabled}，"
            f"媒体类型={self._filter_media_type or '不限'}，"
            f"来源筛选={len(self._filter_usernames)} 项"
        )

    def get_state(self) -> bool:
        """返回插件当前是否启用。"""
        return self._enabled

    def stop_service(self) -> None:
        """停用或卸载插件时释放后台资源；需保证可重复、安全地调用。"""
        try:
            from app.sdk import scheduler as scheduler_sdk  # 延迟导入，避免版本差异影响加载

            remove_job = getattr(scheduler_sdk, "remove_plugin_once_job", None)
            if remove_job:
                remove_job(self.__class__.__name__, _ONCE_JOB_ID)
        except Exception as err:  # pragma: no cover - 宿主版本差异兜底
            logger.debug(f"{PLUGIN_NAME} 清理一次性任务时跳过：{err}")

    def _add_once_job(self, job_id: str, delay_seconds: float = 3) -> bool:
        """向宿主调度器登记一次性任务，返回是否登记成功。

        注意 ``add_plugin_once_job`` 的关键字参数名是 ``func_kwargs``（不是
        ``kwargs``），传错会被它自己的 try/except 吞掉并只留下一条错误日志。
        """
        try:
            from app.sdk import scheduler as scheduler_sdk

            add_once = getattr(scheduler_sdk, "add_plugin_once_job", None)
            if not add_once:
                logger.warning(f"{PLUGIN_NAME} 当前宿主不支持一次性任务接口，改为同步执行")
                return False
            add_once(
                self.__class__.__name__,
                job_id,
                self.batch_edit,
                f"{PLUGIN_NAME}批量改写",
                delay_seconds=delay_seconds,
                func_kwargs={},
            )
            return True
        except Exception as err:  # pragma: no cover - 宿主版本差异兜底
            logger.warning(f"{PLUGIN_NAME} 登记一次性任务失败：{err}")
            return False

    # ─── 配置页（vuetify 模式） ──────────────────────────────────

    def _system_usernames(self) -> List[str]:
        """读取系统用户名单；用于把「真实用户」与「插件来源」区分开。"""
        oper = _user_oper()
        if oper is None:
            return []
        try:
            return [str(u.name).strip() for u in (oper.list() or []) if str(u.name).strip()]
        except Exception as err:
            logger.error(f"{PLUGIN_NAME} 读取用户列表失败：{err}")
            return []

    def _source_items(self) -> List[Dict[str, str]]:
        """构建「订阅来源 / 用户」下拉项。

        这是本插件的核心：把三类取值合并成一个列表
        —— 系统用户、从订阅库扫描出的**插件来源**（username 是插件名的那些）、
        以及「无归属」哨兵，使插件发起的订阅可以被筛选与批量改写。
        """
        users = self._system_usernames()
        user_keys = {name.lower() for name in users}
        counts: Dict[str, int] = {}
        has_no_owner = False

        for sub in self._list_subscribes():
            name = str(getattr(sub, "username", "") or "").strip()
            if not name:
                has_no_owner = True
                continue
            counts[name] = counts.get(name, 0) + 1

        items: List[Dict[str, str]] = []
        for name in sorted(users, key=str.lower):
            items.append({"title": name, "value": name})
        # 订阅库里出现、但不在系统用户表里的取值 = 插件发起的订阅
        for name in sorted(counts, key=str.lower):
            if name.lower() in user_keys:
                continue
            items.append({"title": f"{name}（插件 · {counts[name]} 条）", "value": name})
        if has_no_owner:
            items.append({"title": "（无归属用户）", "value": NO_OWNER})
        return items

    def _site_items(self) -> List[Dict[str, str]]:
        """构建站点下拉项（value 为站点 ID 字符串，与宿主保持一致）。"""
        oper = _site_oper()
        if oper is None:
            return []
        try:
            return [
                {"title": str(site.name), "value": str(site.id)}
                for site in (oper.list_order_by_pri() or [])
                if getattr(site, "id", None) is not None
            ]
        except Exception as err:
            logger.error(f"{PLUGIN_NAME} 读取站点列表失败：{err}")
            return []

    def _downloader_items(self) -> List[Dict[str, str]]:
        """构建下载器下拉项（value 为下载器名称，即订阅的 downloader 取值）。"""
        helper = _downloader_helper()
        if helper is None:
            return []
        try:
            configs = helper.get_configs() or {}
            return [
                {"title": str(cfg.name), "value": str(cfg.name)}
                for cfg in configs.values()
                if getattr(cfg, "name", None)
            ]
        except Exception as err:
            logger.error(f"{PLUGIN_NAME} 读取下载器列表失败：{err}")
            return []

    def get_form(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """组装配置表单与默认配置（vuetify 渲染模式）。"""
        # 多选下拉不放「不限」项：不选即代表不限，避免产生 [""] 这类脏值
        source_items = self._source_items()
        site_items = self._site_items()
        downloader_items = self._downloader_items()
        user_items = [{"title": "不修改", "value": ""}] + [
            {"title": name, "value": name} for name in self._system_usernames()
        ]

        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VAlert",
                                        "props": {
                                            "type": "info",
                                            "variant": "tonal",
                                            "text": (
                                                "筛选规则：设置条件筛选出需要修改的订阅，"
                                                "留空表示不限制。"
                                                "「订阅来源 / 用户」会把由插件发起的订阅"
                                                "（username 为插件名）一并列出，便于批量改写它们。"
                                            ),
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 6},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "filter_media_type",
                                            "label": "媒体类型",
                                            "items": [
                                                {"title": "不限", "value": ""},
                                                {"title": "电视剧", "value": MediaType.TV.value},
                                                {"title": "电影", "value": MediaType.MOVIE.value},
                                            ],
                                            "hint": "默认仅处理电视剧，可放开为电影或不限",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 6},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "filter_best_version",
                                            "label": "洗版状态",
                                            "items": [
                                                {"title": "不限", "value": ""},
                                                {"title": "关闭", "value": "0"},
                                                {"title": "开启", "value": "1"},
                                            ],
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "filter_usernames",
                                            "label": "订阅来源 / 用户",
                                            "items": source_items,
                                            "multiple": True,
                                            "chips": True,
                                            "clearable": True,
                                            "hint": (
                                                "可多选。带「（插件）」标注的是由插件发起的订阅；"
                                                "不选表示不限来源"
                                            ),
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "filter_episode_lt",
                                            "label": "集数小于",
                                            "placeholder": "例如: 3",
                                            "hint": "订阅总集数 < 此值，留空不限",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "filter_episode_gt",
                                            "label": "集数大于",
                                            "placeholder": "例如: 60",
                                            "hint": "订阅总集数 > 此值，留空不限",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VAlert",
                                        "props": {
                                            "type": "warning",
                                            "variant": "tonal",
                                            "text": (
                                                "修改策略：设置对匹配订阅的修改内容，"
                                                "留空表示不修改该项。"
                                                "一次性修改不可撤销，建议先用「立即运行一次」前的"
                                                "插件详情页确认匹配数量。"
                                            ),
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 6},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "modify_sites",
                                            "label": "新站点",
                                            "chips": True,
                                            "multiple": True,
                                            "clearable": True,
                                            "items": site_items,
                                            "hint": "替换订阅的搜索站点",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 6},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "modify_downloader",
                                            "label": "新下载器",
                                            "clearable": True,
                                            "items": downloader_items,
                                            "hint": "替换订阅的下载器",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "modify_save_path",
                                            "label": "新保存路径",
                                            "placeholder": "例如: /tv/shows",
                                            "hint": "替换订阅的保存路径",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 6},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "modify_best_version",
                                            "label": "新洗版状态",
                                            "items": [
                                                {"title": "不修改", "value": ""},
                                                {"title": "关闭", "value": "0"},
                                                {"title": "开启", "value": "1"},
                                            ],
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 6},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "modify_state",
                                            "label": "新订阅状态",
                                            "items": [
                                                {"title": "不修改", "value": ""},
                                                {"title": "订阅中 (R)", "value": "R"},
                                                {"title": "待定 (P)", "value": "P"},
                                                {"title": "暂停 (S)", "value": "S"},
                                            ],
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 6},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "modify_username",
                                            "label": "新订阅归属用户",
                                            "clearable": True,
                                            "items": user_items,
                                            "hint": (
                                                "把匹配到的订阅改归到该用户名下；"
                                                "不修改表示保留原归属"
                                            ),
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "modify_include",
                                            "label": "包含规则",
                                            "placeholder": "例如: HDR|DV|4K",
                                            "hint": "替换订阅的包含规则（正则），留空不修改",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "modify_exclude",
                                            "label": "排除规则",
                                            "placeholder": "例如: 抢播|国语",
                                            "hint": "替换订阅的排除规则（正则），留空不修改",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {"model": "enabled", "label": "启用插件"},
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {"model": "onlyonce", "label": "立即运行一次"},
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {"model": "notify", "label": "发送通知"},
                                    }
                                ],
                            },
                        ],
                    },
                ],
            }
        ], self._default_config()

    @staticmethod
    def _default_config() -> Dict[str, Any]:
        """返回配置默认值。"""
        return {
            "enabled": False,
            "onlyonce": False,
            "notify": False,
            "filter_media_type": MediaType.TV.value,
            "filter_episode_lt": "",
            "filter_episode_gt": "",
            "filter_usernames": [],
            "filter_best_version": "",
            "modify_sites": [],
            "modify_downloader": "",
            "modify_save_path": "",
            "modify_include": "",
            "modify_exclude": "",
            "modify_best_version": "",
            "modify_state": "",
            "modify_username": "",
        }

    def get_page(self) -> List[Dict[str, Any]]:
        """插件详情页：展示当前筛选条件命中的订阅，便于执行前确认。"""
        matched = self._filter_subscribes()
        lines = []
        for sub in matched[:_PAGE_PREVIEW_LIMIT]:
            owner = str(getattr(sub, "username", "") or "").strip() or "无归属"
            lines.append(
                f"#{sub.id} {sub.name}"
                + (f"（{sub.season}）" if getattr(sub, "season", None) else "")
                + f" · {owner} · {getattr(sub, 'state', '')}"
            )
        if len(matched) > _PAGE_PREVIEW_LIMIT:
            lines.append(f"…… 其余 {len(matched) - _PAGE_PREVIEW_LIMIT} 条已省略")

        summary = self._filter_summary()
        content: List[Dict[str, Any]] = [
            {
                "component": "VAlert",
                "props": {
                    "type": "info",
                    "variant": "tonal",
                    "text": f"当前筛选条件命中 {len(matched)} 个订阅。筛选条件：{summary}",
                },
            }
        ]
        if lines:
            content.append(
                {
                    "component": "VAlert",
                    "props": {
                        "type": "success",
                        "variant": "outlined",
                        "text": "\n".join(lines),
                        "style": "white-space: pre-line;",
                    },
                }
            )
        else:
            content.append(
                {
                    "component": "VAlert",
                    "props": {
                        "type": "warning",
                        "variant": "outlined",
                        "text": "没有订阅命中当前筛选条件。",
                    },
                }
            )
        return content

    def _filter_summary(self) -> str:
        """把当前筛选条件整理成一句人类可读的说明。"""
        parts: List[str] = []
        parts.append(f"媒体类型={'不限' if not self._filter_media_type else self._filter_media_type}")
        if self._filter_usernames:
            names = [
                "（无归属）" if item == NO_OWNER else item for item in self._filter_usernames
            ]
            parts.append(f"来源={'、'.join(names)}")
        else:
            parts.append("来源=不限")
        if self._filter_episode_lt:
            parts.append(f"集数<{self._filter_episode_lt}")
        if self._filter_episode_gt:
            parts.append(f"集数>{self._filter_episode_gt}")
        if self._filter_best_version:
            parts.append(f"洗版={'开启' if self._filter_best_version == '1' else '关闭'}")
        return "，".join(parts)

    # ─── 后台能力：远程命令 / HTTP 接口 ──────────────────────────

    def get_command(self) -> List[Dict[str, Any]]:
        """注册远程命令；实际动作通过 EventType.PluginAction 事件路由。"""
        return [
            {
                "cmd": "/batch_edit_subscribes",
                "event": EventType.PluginAction,
                "desc": "按当前规则批量改写订阅",
                "category": "订阅管理",
                "data": {"action": "subscribebatcheditor_apply"},
            }
        ]

    @eventmanager.register(EventType.PluginAction)
    def on_plugin_action(self, event: Event) -> None:
        """响应远程命令；仅处理属于本插件的 action。"""
        if not self._enabled:
            return
        event_data = event.event_data or {}
        if event_data.get("action") != "subscribebatcheditor_apply":
            return
        threading.Thread(target=self.batch_edit, daemon=True).start()

    @eventmanager.register(EventType.SubscribeAdded)
    def on_subscribe_added(self, event: Event) -> None:
        """新增订阅时按当前规则自动触发一次批量改写。

        注意：若修改策略为空，``batch_edit`` 会直接跳过，不会产生副作用。
        """
        if not self._enabled:
            return
        event_data = event.event_data or {}
        mediainfo = event_data.get("mediainfo")
        if not mediainfo:
            return
        media_type = mediainfo.get("type") if isinstance(mediainfo, dict) else None
        # 仅在媒体类型筛选未设限、或与新增订阅类型一致时触发，避免无谓扫描
        if self._filter_media_type and media_type and media_type != self._filter_media_type:
            return
        title = mediainfo.get("title") if isinstance(mediainfo, dict) else ""
        logger.info(f"{PLUGIN_NAME} 检测到新增订阅「{title}」，按规则执行批量改写")
        threading.Thread(target=self.batch_edit, daemon=True).start()

    def get_api(self) -> List[Dict[str, Any]]:
        """声明插件 HTTP 接口，挂载在 ``/api/v1/plugin/SubscribeBatchEditor/<path>``。"""
        return [
            {
                "path": "/preview",
                "endpoint": self.api_preview,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "预览命中筛选条件的订阅",
                "description": "返回当前筛选规则命中的订阅列表与总数，不会修改任何数据",
            },
            {
                "path": "/sources",
                "endpoint": self.api_sources,
                "methods": ["GET"],
                "auth": "apikey",
                "summary": "列出可用的订阅来源",
                "description": "返回系统用户、插件发起的订阅来源与无归属标记",
            },
            {
                "path": "/apply",
                "endpoint": self.api_apply,
                "methods": ["POST"],
                "auth": "apikey",
                "summary": "应用修改策略",
                "description": "对命中的订阅执行批量改写，返回成功 / 失败统计",
            },
        ]

    def api_preview(self) -> Dict[str, Any]:
        """API：预览命中筛选条件的订阅。"""
        try:
            matched = self._filter_subscribes()
            return {
                "success": True,
                "data": {
                    "total": len(matched),
                    "filter": self._filter_summary(),
                    "subscribes": [self._subscribe_view(sub) for sub in matched],
                },
            }
        except Exception as err:
            logger.error(f"{PLUGIN_NAME} 预览订阅失败：{err}")
            return {"success": False, "message": str(err)}

    def api_sources(self) -> Dict[str, Any]:
        """API：列出可用的订阅来源。"""
        try:
            users = self._system_usernames()
            user_keys = {name.lower() for name in users}
            sources: Dict[str, Dict[str, Any]] = {}
            for sub in self._list_subscribes():
                name = str(getattr(sub, "username", "") or "").strip()
                if not name:
                    continue
                entry = sources.setdefault(
                    name,
                    {"name": name, "count": 0, "kind": "user" if name.lower() in user_keys else "plugin"},
                )
                entry["count"] += 1
            return {
                "success": True,
                "data": {
                    "users": users,
                    "sources": sorted(sources.values(), key=lambda item: item["name"].lower()),
                    "no_owner": NO_OWNER,
                },
            }
        except Exception as err:
            logger.error(f"{PLUGIN_NAME} 读取订阅来源失败：{err}")
            return {"success": False, "message": str(err)}

    def api_apply(self) -> Dict[str, Any]:
        """API：应用修改策略。"""
        try:
            result = self.batch_edit()
            return {"success": True, "data": result}
        except Exception as err:
            logger.error(f"{PLUGIN_NAME} 执行批量改写失败：{err}")
            return {"success": False, "message": str(err)}

    # ─── 筛选逻辑 ────────────────────────────────────────────────

    def _list_subscribes(self) -> List[Any]:
        """读取全量订阅；失败时返回空列表，不影响配置页渲染。"""
        oper = _subscribe_oper()
        if oper is None:
            return []
        try:
            return list(oper.list() or [])
        except Exception as err:
            logger.error(f"{PLUGIN_NAME} 读取订阅列表失败：{err}")
            return []

    def _filter_subscribes(self) -> List[Any]:
        """按当前筛选规则过滤订阅。"""
        return [sub for sub in self._list_subscribes() if self._match_subscribe(sub)]

    def _match_source(self, raw_username: Any) -> bool:
        """判断订阅来源是否命中「订阅来源 / 用户」筛选。

        取值可能是真实用户名、插件名，或空（无归属）；用 ``NO_OWNER`` 哨兵匹配空值。
        未选择任何来源时视为不限。
        """
        if not self._filter_usernames:
            return True
        value = str(raw_username or "").strip()
        for item in self._filter_usernames:
            token = str(item).strip()
            if not token:
                continue
            if token == NO_OWNER:
                if not value:
                    return True
                continue
            if value and value.lower() == token.lower():
                return True
        return False

    def _match_subscribe(self, sub: Any) -> bool:
        """判断单个订阅是否命中全部筛选条件。"""
        # 媒体类型
        if self._filter_media_type and str(getattr(sub, "type", "") or "") != self._filter_media_type:
            return False

        # 订阅来源 / 用户（含插件发起的订阅与无归属）
        if not self._match_source(getattr(sub, "username", "")):
            return False

        # 集数：小于 / 大于，任一满足即可（与原行为一致）
        if self._filter_episode_lt or self._filter_episode_gt:
            total_episode = getattr(sub, "total_episode", 0) or 0
            hit = False
            lower = _as_int(self._filter_episode_lt)
            if lower is not None and total_episode < lower:
                hit = True
            upper = _as_int(self._filter_episode_gt)
            if not hit and upper is not None and total_episode > upper:
                hit = True
            if not hit:
                return False

        # 洗版状态
        if self._filter_best_version:
            target = _as_int(self._filter_best_version)
            if target is not None and (getattr(sub, "best_version", 0) or 0) != target:
                return False

        return True

    # ─── 修改策略 ────────────────────────────────────────────────

    def _build_update_payload(self) -> Dict[str, Any]:
        """按修改策略构建更新载荷；只包含用户显式设置的字段。"""
        payload: Dict[str, Any] = {}

        if self._modify_sites:
            site_ids: List[int] = []
            for item in self._modify_sites:
                value = _as_int(item)
                if value is not None:
                    site_ids.append(value)
            if site_ids:
                # sites 是 JSON 列，需要 Python 原生 list
                payload["sites"] = site_ids

        if self._modify_downloader:
            payload["downloader"] = self._modify_downloader
        if self._modify_save_path:
            payload["save_path"] = self._modify_save_path
        if self._modify_include:
            payload["include"] = self._modify_include
        if self._modify_exclude:
            payload["exclude"] = self._modify_exclude
        if self._modify_best_version:
            best_version = _as_int(self._modify_best_version)
            if best_version is not None:
                payload["best_version"] = best_version
        if self._modify_state:
            payload["state"] = self._modify_state
        if self._modify_username:
            payload["username"] = self._modify_username

        return payload

    @staticmethod
    def _subscribe_view(sub: Any) -> Dict[str, Any]:
        """把订阅对象压成前端易读的视图（不包含描述等大字段）。"""
        return {
            "id": getattr(sub, "id", None),
            "name": getattr(sub, "name", ""),
            "year": getattr(sub, "year", ""),
            "type": getattr(sub, "type", ""),
            "season": getattr(sub, "season", None),
            "state": getattr(sub, "state", ""),
            "username": getattr(sub, "username", "") or "",
            "sites": getattr(sub, "sites", None),
            "downloader": getattr(sub, "downloader", ""),
            "save_path": getattr(sub, "save_path", ""),
            "best_version": getattr(sub, "best_version", 0),
            "total_episode": getattr(sub, "total_episode", 0),
        }

    # ─── 执行 ────────────────────────────────────────────────────

    def batch_edit(self) -> Dict[str, Any]:
        """执行批量改写：筛选订阅并应用修改策略，返回执行统计。"""
        with _lock:
            matched = self._filter_subscribes()
            if not matched:
                logger.info(f"{PLUGIN_NAME} 没有订阅命中当前筛选条件")
                self._notify_result("没有订阅命中当前筛选条件", matched=[], payload={}, ok=0, fail=0)
                return {"total": 0, "success": 0, "failed": 0, "payload": {}}

            payload = self._build_update_payload()
            if not payload:
                logger.warning(f"{PLUGIN_NAME} 修改策略为空，未设置任何修改项，已跳过")
                self._notify_result("修改策略为空，未设置任何修改项", matched=[], payload={}, ok=0, fail=0)
                return {"total": len(matched), "success": 0, "failed": 0, "payload": {}}

            oper = _subscribe_oper()
            if oper is None:
                message = "未找到订阅数据入口，无法执行批量改写"
                logger.error(f"{PLUGIN_NAME} {message}")
                self._notify_result(message, matched=[], payload=payload, ok=0, fail=0)
                return {"total": len(matched), "success": 0, "failed": 0, "payload": payload}

            success, failed = 0, 0
            for sub in matched:
                try:
                    # 先记录原值，便于日志与通知里体现「改前 -> 改后」
                    before = {key: getattr(sub, key, None) for key in payload}
                    oper.update(getattr(sub, "id"), payload)
                    logger.info(
                        f"{PLUGIN_NAME} 已更新订阅 #{getattr(sub, 'id', '')}「{getattr(sub, 'name', '')}」："
                        f"{before} -> {payload}"
                    )
                    success += 1
                except Exception as err:
                    failed += 1
                    logger.error(
                        f"{PLUGIN_NAME} 更新订阅 #{getattr(sub, 'id', '')}"
                        f"「{getattr(sub, 'name', '')}」失败：{err}"
                    )

            logger.info(
                f"{PLUGIN_NAME} 批量改写完成：命中={len(matched)}，成功={success}，失败={failed}，"
                f"修改内容={payload}"
            )
            self._notify_result("批量改写完成", matched=matched, payload=payload, ok=success, fail=failed)
            return {
                "total": len(matched),
                "success": success,
                "failed": failed,
                "payload": payload,
            }

    def _notify_result(
        self,
        title: str,
        matched: List[Any],
        payload: Dict[str, Any],
        ok: int,
        fail: int,
    ) -> None:
        """按需发送执行结果通知；未配置通知渠道时静默降级。"""
        if not self._notify:
            return
        try:
            lines = [title]
            if payload:
                detail = "，".join(f"{key}={value}" for key, value in payload.items())
                lines.append(f"修改内容：{detail}")
            if matched:
                lines.append(f"命中订阅：{len(matched)} 个")
                lines.append(f"成功修改：{ok} 个，失败：{fail} 个")
                preview = [
                    f"· #{getattr(sub, 'id', '')} {getattr(sub, 'name', '')}"
                    for sub in matched[:10]
                ]
                lines.extend(preview)
                if len(matched) > 10:
                    lines.append(f"…… 其余 {len(matched) - 10} 个已省略")
            self.post_message(
                mtype=_MessageType.Plugin,
                title=f"【{self.plugin_name}】{title}",
                text="\n".join(lines),
            )
        except Exception as err:  # pragma: no cover - 未配置通知渠道时兜底
            logger.warning(f"{PLUGIN_NAME} 发送通知失败：{err}")
