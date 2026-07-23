import ast
import json
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pytz
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.core.event import eventmanager, Event
from app.db.site_oper import SiteOper
from app.db.subscribe_oper import SubscribeOper
from app.db.user_oper import UserOper
from app.helper.downloader import DownloaderHelper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType, MediaType, NotificationType

lock = threading.RLock()


class SubscribeBatchEditor(_PluginBase):
    """
    订阅批量编辑器。
    根据规则筛选电视剧订阅，批量修改订阅的站点、下载器、保存路径、洗版功能等。
    """

    plugin_name = "订阅批量编辑器"
    plugin_desc = "根据规则筛选电视剧订阅，批量修改订阅站点、下载器、保存路径、洗版功能。"
    plugin_icon = "https://raw.githubusercontent.com/InfinityPacer/MoviePilot-Plugins/main/icons/subscribeassistant.png"
    plugin_version = "1.3.0"
    plugin_author = "AI"
    plugin_label = "订阅管理"
    plugin_config_prefix = "subscribebatcheditor_"
    plugin_order = 20
    auth_level = 1

    # 私有属性
    subscribe_oper = None
    downloader_helper = None
    _enabled = False
    _onlyonce = False
    _notify = False
    _scheduler = None
    _event = threading.Event()

    # 筛选规则
    _filter_episode_lt = ""        # 集数小于
    _filter_episode_gt = ""        # 集数大于
    _filter_username = ""           # 订阅用户
    _filter_best_version = ""       # 洗版状态：空-不限, 0-关闭, 1-开启

    # 修改策略
    _modify_sites = ""              # 新站点 ID 列表
    _modify_downloader = ""         # 新下载器名称
    _modify_save_path = ""          # 新保存路径
    _modify_include = ""            # 包含规则
    _modify_exclude = ""            # 排除规则
    _modify_best_version = ""       # 新洗版状态：空-不修改, 0-关闭, 1-开启
    _modify_state = ""              # 新订阅状态：空-不修改, R-订阅中, P-待定, S-暂停

    def init_plugin(self, config: dict = None):
        """根据插件配置初始化运行状态。"""
        self.subscribe_oper = SubscribeOper()
        self.downloader_helper = DownloaderHelper()

        if not config:
            return

        self._enabled = config.get("enabled", False)
        self._onlyonce = config.get("onlyonce", False)
        self._notify = config.get("notify", False)

        # 读取筛选规则
        self._filter_episode_lt = config.get("filter_episode_lt", "")
        self._filter_episode_gt = config.get("filter_episode_gt", "")
        self._filter_username = config.get("filter_username", "")
        self._filter_best_version = config.get("filter_best_version", "")

        # 读取修改策略
        self._modify_sites = config.get("modify_sites", "")
        self._modify_downloader = config.get("modify_downloader", "")
        self._modify_save_path = config.get("modify_save_path", "")
        self._modify_include = config.get("modify_include", "")
        self._modify_exclude = config.get("modify_exclude", "")
        self._modify_best_version = config.get("modify_best_version", "")
        self._modify_state = config.get("modify_state", "")

        # 停止现有任务
        self.stop_service()

        if self._enabled:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            self._scheduler.start()

            if self._onlyonce:
                logger.info("订阅批量编辑器，立即运行一次")
                self._scheduler.add_job(
                    func=self.batch_edit,
                    trigger="date",
                    run_date=datetime.now(tz=pytz.timezone(settings.TZ)) + timedelta(seconds=3),
                    name="订阅批量编辑",
                )
                self._onlyonce = False
                self.update_config({
                    "onlyonce": False,
                    "enabled": self._enabled,
                    "notify": self._notify,
                    "filter_episode_lt": self._filter_episode_lt,
                    "filter_episode_gt": self._filter_episode_gt,
                    "filter_username": self._filter_username,
                    "filter_best_version": self._filter_best_version,
                    "modify_sites": self._modify_sites,
                    "modify_downloader": self._modify_downloader,
                    "modify_save_path": self._modify_save_path,
                    "modify_include": self._modify_include,
                    "modify_exclude": self._modify_exclude,
                    "modify_best_version": self._modify_best_version,
                    "modify_state": self._modify_state,
                })

            logger.info("订阅批量编辑器启动完成")

    def get_state(self) -> bool:
        """获取插件启用状态。"""
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """返回插件远程命令列表。"""
        return [
            {
                "cmd": "/batch_edit_subscribes",
                "event": EventType.PluginAction,
                "desc": "订阅批量编辑",
                "category": "订阅管理",
                "data": {
                    "action": "batch_edit"
                }
            }
        ]

    def get_api(self) -> List[Dict[str, Any]]:
        """返回插件 API 列表。"""
        return [
            {
                "path": "/preview",
                "endpoint": self.api_preview,
                "methods": ["GET"],
                "summary": "预览匹配的订阅列表",
                "description": "根据当前筛选规则返回匹配的订阅列表",
            },
            {
                "path": "/apply",
                "endpoint": self.api_apply,
                "methods": ["POST"],
                "summary": "应用修改策略",
                "description": "对匹配的订阅应用修改策略",
            },
        ]

    def get_form(self) -> Tuple[Optional[List[dict]], Dict[str, Any]]:
        """返回插件配置表单与默认配置。"""
        # 从系统读取用户列表
        user_items = [{"title": "不限", "value": ""}]
        try:
            for u in UserOper().list():
                user_items.append({"title": u.name, "value": u.name})
        except Exception as e:
            logger.error(f"读取用户列表失败: {e}")

        # 从系统读取站点列表
        site_items = []
        try:
            for s in SiteOper().list_order_by_pri():
                site_items.append({"title": s.name, "value": str(s.id)})
        except Exception as e:
            logger.error(f"读取站点列表失败: {e}")

        # 从系统读取下载器列表
        downloader_items = []
        try:
            for dc in DownloaderHelper().get_configs().values():
                downloader_items.append({"title": dc.name, "value": dc.name})
        except Exception as e:
            logger.error(f"读取下载器列表失败: {e}")

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
                                            "text": "筛选规则：设置条件筛选出需要修改的电视剧订阅。留空表示不限制。"
                                        }
                                    }
                                ]
                            }
                        ]
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
                                            "hint": "订阅总集数 < 此值，留空不限"
                                        }
                                    }
                                ]
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
                                            "hint": "订阅总集数 > 此值，留空不限"
                                        }
                                    }
                                ]
                            }
                        ]
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
                                            "model": "filter_username",
                                            "label": "订阅用户",
                                            "items": user_items,
                                            "hint": "匹配订阅创建用户"
                                        }
                                    }
                                ]
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
                                                {"title": "开启", "value": "1"}
                                            ]
                                        }
                                    }
                                ]
                            }
                        ]
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
                                            "text": "修改策略：设置对匹配订阅的修改内容。留空表示不修改该项。"
                                        }
                                    }
                                ]
                            }
                        ]
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
                                            "hint": "替换订阅的搜索站点"
                                        }
                                    }
                                ]
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
                                            "chips": True,
                                            "clearable": True,
                                            "items": downloader_items,
                                            "hint": "替换订阅的下载器"
                                        }
                                    }
                                ]
                            }
                        ]
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
                                            "hint": "替换订阅的保存路径"
                                        }
                                    }
                                ]
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
                                                {"title": "开启", "value": "1"}
                                            ]
                                        }
                                    }
                                ]
                            }
                        ]
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
                                                {"title": "暂停 (S)", "value": "S"}
                                            ]
                                        }
                                    }
                                ]
                            }
                        ]
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
                                            "hint": "替换订阅的包含规则（正则），留空不修改"
                                        }
                                    }
                                ]
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
                                            "hint": "替换订阅的排除规则（正则），留空不修改"
                                        }
                                    }
                                ]
                            }
                        ]
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
                                        "props": {
                                            "model": "enabled",
                                            "label": "启用插件"
                                        }
                                    }
                                ]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "onlyonce",
                                            "label": "立即运行一次"
                                        }
                                    }
                                ]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "notify",
                                            "label": "发送通知"
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": False,
            "onlyonce": False,
            "notify": False,
            "filter_episode_lt": "",
            "filter_episode_gt": "",
            "filter_username": "",
            "filter_best_version": "",
            "modify_sites": "",
            "modify_downloader": "",
            "modify_save_path": "",
            "modify_include": "",
            "modify_exclude": "",
            "modify_best_version": "",
            "modify_state": "",
        }

    def get_page(self) -> Optional[List[dict]]:
        """返回插件详情页面。"""
        if not self._enabled:
            return None

        try:
            matched = self._filter_subscribes()
            total = len(matched)
        except Exception as e:
            logger.error(f"获取匹配订阅数量失败: {e}")
            total = 0

        return [
            {
                "component": "VAlert",
                "props": {
                    "type": "info",
                    "text": f"当前筛选规则匹配 {total} 个电视剧订阅。"
                           f"如需执行批量修改，请在配置中设置修改策略并点击「立即运行一次」。"
                }
            }
        ]

    def stop_service(self) -> None:
        """停止插件后台服务并释放资源。"""
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._event.set()
                    self._scheduler.shutdown(wait=False)
                self._scheduler = None
        except Exception as e:
            logger.error(f"停止订阅批量编辑器服务失败: {e}")

    def _filter_subscribes(self) -> list:
        """根据筛选规则过滤电视剧订阅。"""
        if not self.subscribe_oper:
            self.subscribe_oper = SubscribeOper()

        all_subscribes = self.subscribe_oper.list() or []
        tv_subscribes = [s for s in all_subscribes if s.type == MediaType.TV.value]

        matched = []
        for sub in tv_subscribes:
            if not self._match_subscribe(sub):
                continue
            matched.append(sub)

        return matched

    def _match_subscribe(self, sub) -> bool:
        """判断单个订阅是否匹配所有筛选规则。"""

        # 集数筛选：小于 或 大于，任一满足即可
        episode_matched = True
        if self._filter_episode_lt or self._filter_episode_gt:
            episode_matched = False
            total_ep = sub.total_episode or 0
            if self._filter_episode_lt:
                try:
                    if total_ep < int(self._filter_episode_lt):
                        episode_matched = True
                except ValueError:
                    logger.warning(f"集数小于值无效: {self._filter_episode_lt}")
            if not episode_matched and self._filter_episode_gt:
                try:
                    if total_ep > int(self._filter_episode_gt):
                        episode_matched = True
                except ValueError:
                    logger.warning(f"集数大于值无效: {self._filter_episode_gt}")
        if not episode_matched:
            return False

        # 订阅用户匹配
        if self._filter_username:
            sub_user = (sub.username or "").strip()
            if self._filter_username.lower() != sub_user.lower():
                return False

        # 洗版状态匹配
        if self._filter_best_version:
            target = int(self._filter_best_version)
            current = sub.best_version or 0
            if current != target:
                return False

        return True

    def _build_update_payload(self) -> dict:
        """根据修改策略构建更新 payload。"""
        payload = {}

        # 站点：modify_sites 是多选 VSelect，配置中可能是 list 对象或字符串
        if self._modify_sites:
            try:
                if isinstance(self._modify_sites, list):
                    site_ids = self._modify_sites
                elif isinstance(self._modify_sites, str):
                    site_ids = json.loads(self._modify_sites)
                else:
                    site_ids = []
                if isinstance(site_ids, list) and len(site_ids) > 0:
                    # sites 字段是 SQLAlchemy JSON 列，需要 Python list
                    payload["sites"] = [int(s) for s in site_ids]
            except (ValueError, TypeError, json.JSONDecodeError) as e:
                logger.warning(f"站点数据格式无效: {self._modify_sites}, 错误: {e}")

        if self._modify_downloader:
            payload["downloader"] = self._modify_downloader

        if self._modify_save_path:
            payload["save_path"] = self._modify_save_path

        if self._modify_include:
            payload["include"] = self._modify_include

        if self._modify_exclude:
            payload["exclude"] = self._modify_exclude

        if self._modify_best_version:
            payload["best_version"] = int(self._modify_best_version)

        if self._modify_state:
            payload["state"] = self._modify_state

        return payload

    def batch_edit(self):
        """执行批量编辑：筛选订阅并应用修改策略。"""
        with lock:
            logger.info("开始执行订阅批量编辑...")

            if not self.subscribe_oper:
                self.subscribe_oper = SubscribeOper()

            matched = self._filter_subscribes()
            if not matched:
                logger.info("没有匹配的订阅需要修改")
                if self._notify:
                    self.post_message(
                        channel=None,
                        mtype=NotificationType.SiteMessage,
                        title="订阅批量编辑",
                        text="没有匹配的订阅需要修改",
                    )
                return

            payload = self._build_update_payload()
            if not payload:
                logger.warning("修改策略为空，未设置任何修改项")
                if self._notify:
                    self.post_message(
                        channel=None,
                        mtype=NotificationType.SiteMessage,
                        title="订阅批量编辑",
                        text="修改策略为空，未设置任何修改项",
                    )
                return

            success_count = 0
            fail_count = 0
            for sub in matched:
                try:
                    self.subscribe_oper.update(sid=sub.id, payload=payload)
                    logger.info(f"已更新订阅: {sub.name} (ID={sub.id}), payload={payload}")
                    success_count += 1
                except Exception as e:
                    logger.error(f"更新订阅失败: {sub.name} (ID={sub.id}), 错误: {e}")
                    fail_count += 1

            if self._notify:
                changed_fields = ", ".join([
                    f"{k}={v}" for k, v in payload.items()
                ])
                self.post_message(
                    channel=None,
                    mtype=NotificationType.SiteMessage,
                    title="订阅批量编辑完成",
                    text=f"匹配订阅: {len(matched)} 个\n"
                         f"成功修改: {success_count} 个\n"
                         f"修改失败: {fail_count} 个\n"
                         f"修改内容: {changed_fields}",
                )

            logger.info(f"订阅批量编辑完成: 匹配={len(matched)}, 成功={success_count}, 失败={fail_count}")

    def api_preview(self) -> dict:
        """API: 预览匹配的订阅列表。"""
        if not self._enabled:
            return {"code": 1, "message": "插件未启用"}

        try:
            matched = self._filter_subscribes()
            result = []
            for sub in matched:
                result.append({
                    "id": sub.id,
                    "name": sub.name,
                    "year": sub.year,
                    "season": sub.season,
                    "state": sub.state,
                    "downloader": sub.downloader,
                    "save_path": sub.save_path,
                    "best_version": sub.best_version,
                    "sites": sub.sites,
                    "total_episode": sub.total_episode,
                    "username": sub.username,
                })
            return {
                "code": 0,
                "data": {
                    "total": len(result),
                    "subscribes": result
                }
            }
        except Exception as e:
            logger.error(f"预览订阅失败: {e}")
            return {"code": 1, "message": str(e)}

    def api_apply(self) -> dict:
        """API: 应用修改策略。"""
        if not self._enabled:
            return {"code": 1, "message": "插件未启用"}

        try:
            self.batch_edit()
            return {"code": 0, "message": "批量编辑已执行"}
        except Exception as e:
            logger.error(f"应用修改失败: {e}")
            return {"code": 1, "message": str(e)}

    @eventmanager.register(EventType.PluginAction)
    def handle_command(self, event: Event) -> None:
        """处理插件命令事件。"""
        if not self._enabled:
            return

        event_data = event.event_data or {}
        if event_data.get("action") != "batch_edit":
            return

        threading.Thread(target=self.batch_edit, daemon=True).start()

    @eventmanager.register(EventType.SubscribeAdded)
    def handle_subscribe_added(self, event: Event) -> None:
        """新增订阅时自动触发批量编辑。"""
        if not self._enabled:
            return

        event_data = event.event_data or {}
        mediainfo_dict = event_data.get("mediainfo")
        if not mediainfo_dict:
            return

        # mediainfo 是 dict，检查 type 是否为电视剧
        media_type = mediainfo_dict.get("type")
        if media_type != MediaType.TV.value:
            return

        logger.info(f"检测到新增电视剧订阅: {mediainfo_dict.get('title')}, 自动执行批量编辑")
        threading.Thread(target=self.batch_edit, daemon=True).start()
