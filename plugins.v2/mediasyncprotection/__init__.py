import json
import threading
import time
import copy
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Tuple, Optional
from datetime import datetime

from app.plugins import _PluginBase
from app.log import logger
from app.schemas import NotificationType
from app.helper.downloader import DownloaderHelper


class MediaSyncProtection(_PluginBase):
    plugin_name = "媒体同步保护"
    plugin_desc = "监听Emby Webhook，收藏时添加/移除保种标签，删除时对种子执行操作"
    plugin_icon = "Amule_B.png"
    plugin_version = "1.0.0"
    plugin_author = "AI"
    plugin_config_prefix = "mediasyncprotection_"
    author_url = "https://github.com/m216owen/MoviePilot-Plugins"
    plugin_order = 24
    auth_level = 1

    def __init__(self):
        super().__init__()
        self._enabled = False
        self._webhook_path = "/mediasync"
        self._received_events = []
        self._event_lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=3)
        self._processed_events = {}
        self._processed_lock = threading.Lock()
        self._event_cache_ttl = 60
        self._last_notify_time = {}
        self._notify_throttle = 300
        self._downloader_cache = {}
        self._cache_ttl = 300
        self._last_cache_cleanup = time.time()
        self._cache_cleanup_interval = 60
        self._config = {}
        self._shutdown = False

    def _get_config_safe(self) -> dict:
        """安全获取配置"""
        return getattr(self, '_config', {}) or {}

    def get_config(self) -> dict:
        """获取插件配置"""
        return self._get_config_safe()

    def init_plugin(self, config: dict = None):
        if config:
            self._config = config
        cfg = self._get_config_safe()
        self._enabled = cfg.get("enabled", False)
        with self._event_lock:
            try:
                self._received_events = (self.get_data("received_events") or [])[:50]
            except Exception as e:
                logger.error(f"读取事件记录失败: {e}")
                self._received_events = []
        logger.info(f"媒体同步保护初始化完成，启用: {self._enabled}")

    def get_state(self) -> bool:
        return self._enabled

    def get_api(self) -> List[Dict[str, Any]]:
        if not self._enabled:
            return []
        return [{
            "path": self._webhook_path,
            "endpoint": self.handle_emby_webhook,
            "methods": ["POST", "GET"],
            "summary": "接收Emby Webhook"
        }]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        downloader_helper = DownloaderHelper()
        options = [{"title": c.name, "value": c.name} for c in downloader_helper.get_configs().values()]
        
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
                                    {"component": "VSwitch", "props": {"model": "enabled", "label": "启用插件"}}
                                ]
                            }
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSelect", 
                                        "props": {
                                            "model": "downloaders", 
                                            "label": "下载器（支持多选）", 
                                            "items": options,
                                            "multiple": True,
                                            "chips": True,
                                            "hint": "可选择多个下载器，将同时操作所有选中的下载器"
                                        }
                                    }
                                ]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {"component": "VTextField", "props": {"model": "seed_tag", "label": "保种标签/分类", "placeholder": "保种", "hint": "qBittorrent使用标签，Transmission使用分类"}}
                                ]
                            }
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "delete_action",
                                            "label": "删除时操作",
                                            "items": [
                                                {"title": "仅移除标签", "value": "remove_tag"},
                                                {"title": "暂停种子", "value": "pause"},
                                                {"title": "删除种子(保留文件)", "value": "delete"},
                                                {"title": "删除种子(删除文件)", "value": "delete_with_file"}
                                            ]
                                        }
                                    }
                                ]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {"component": "VSwitch", "props": {"model": "fuzzy_match", "label": "模糊匹配"}}
                                ]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {"component": "VSwitch", "props": {"model": "send_notify", "label": "发送通知"}}
                                ]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {"component": "VSwitch", "props": {"model": "async_delete", "label": "异步删除"}}
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
                                            "type": "info",
                                            "variant": "tonal",
                                            "text": "Webhook URL: /api/v1/plugin/MediaSyncProtection/mediasync\n\n注意：qBittorrent使用标签(Tag)，Transmission使用分类(Label)，功能类似。选择多个下载器时，将同时对所有选中的下载器执行相同操作。"
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
            "downloaders": [],  # 改为列表，支持多选
            "seed_tag": "保种",
            "delete_action": "remove_tag",
            "fuzzy_match": True,
            "send_notify": True,
            "async_delete": True
        }

    def get_page(self) -> List[dict]:
        with self._event_lock:
            events = self._received_events[:20]
            total = len(self._received_events)
            fav = len([e for e in self._received_events if e.get("event_type") == "收藏"])
            unfav = len([e for e in self._received_events if e.get("event_type") == "取消收藏"])
            dlt = len([e for e in self._received_events if e.get("event_type") == "删除"])
        
        return [
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 3},
                        "content": [self._stat_card("总事件数", total, "primary")]
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 3},
                        "content": [self._stat_card("收藏", fav, "success")]
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 3},
                        "content": [self._stat_card("取消收藏", unfav, "warning")]
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 3},
                        "content": [self._stat_card("删除", dlt, "error")]
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
                                "component": "VCard",
                                "props": {"variant": "outlined"},
                                "content": [
                                    {
                                        "component": "VCardTitle",
                                        "text": "事件记录"
                                    },
                                    {
                                        "component": "VCardText",
                                        "content": [
                                            {
                                                "component": "VTable",
                                                "props": {"density": "compact", "hover": True},
                                                "content": [
                                                    {
                                                        "component": "thead",
                                                        "content": [{
                                                            "component": "tr",
                                                            "content": [
                                                                {"component": "th", "text": "时间"},
                                                                {"component": "th", "text": "类型"},
                                                                {"component": "th", "text": "媒体"},
                                                                {"component": "th", "text": "操作者"},
                                                                {"component": "th", "text": "匹配数"},
                                                                {"component": "th", "text": "状态"}
                                                            ]
                                                        }]
                                                    },
                                                    {
                                                        "component": "tbody",
                                                        "content": [
                                                            {
                                                                "component": "tr",
                                                                "content": [
                                                                    {"component": "td", "text": e.get("time", "")},
                                                                    {"component": "td", "text": e.get("event_type", "")},
                                                                    {"component": "td", "text": e.get("item_name", "")},
                                                                    {"component": "td", "text": e.get("user_name", "")},
                                                                    {"component": "td", "text": str(e.get("matched_count", 0))},
                                                                    {"component": "td", "text": e.get("status", "")}
                                                                ]
                                                            } for e in events
                                                        ] if events else [{
                                                            "component": "tr",
                                                            "content": [{"component": "td", "props": {"colspan": 6, "class": "text-center"}, "text": "暂无数据"}]
                                                        }]
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]

    def _stat_card(self, title: str, value: int, color: str) -> dict:
        return {
            "component": "VCard",
            "props": {"variant": "tonal", "color": color},
            "content": [{
                "component": "VCardText",
                "props": {"class": "text-center"},
                "content": [
                    {"component": "div", "props": {"class": "text-h5"}, "text": str(value)},
                    {"component": "div", "props": {"class": "text-caption"}, "text": title}
                ]
            }]
        }

    def update_config(self, config: dict = None):
        """更新配置"""
        if not config:
            return
        
        # 确保 downloaders 是列表
        if config.get("downloaders") is None:
            config["downloaders"] = []
        elif isinstance(config.get("downloaders"), str):
            # 兼容旧配置：如果是字符串，转为列表
            config["downloaders"] = [config["downloaders"]] if config["downloaders"] else []
        
        # 验证必要配置
        if config.get("enabled") and not config.get("downloaders"):
            logger.warning("启用插件但未配置下载器")
            self._send_notification("配置错误", "启用插件但未配置下载器")
        
        # 保存配置的深拷贝
        config = copy.deepcopy(config)
        
        # 验证下载器是否存在
        if config.get("downloaders"):
            available_downloaders = []
            unavailable_downloaders = []
            for downloader_name in config["downloaders"]:
                downloader, dl_type = self._get_downloader(downloader_name)
                if downloader:
                    available_downloaders.append(downloader_name)
                else:
                    unavailable_downloaders.append(downloader_name)
            
            if unavailable_downloaders:
                logger.warning(f"以下下载器不可用: {', '.join(unavailable_downloaders)}")
                self._send_notification("配置警告", f"下载器不可用: {', '.join(unavailable_downloaders)}")
            
            # 只保存可用的下载器
            config["downloaders"] = available_downloaders
        
        # 清空下载器缓存
        self._downloader_cache.clear()
        
        # 保存配置
        self._config = config
        
        # 调用父类的 update_config
        try:
            super().update_config(config)
        except Exception as e:
            logger.error(f"调用父类 update_config 失败: {e}")
        
        # 重新初始化插件
        self.init_plugin(config)

    def _is_duplicate_event(self, event_id: str) -> bool:
        """检查是否为重复事件"""
        with self._processed_lock:
            now = time.time()
            # 清理过期缓存
            expired = [k for k, v in self._processed_events.items() if now - v > self._event_cache_ttl]
            for k in expired:
                del self._processed_events[k]
            
            # 检查重复
            if event_id in self._processed_events:
                if now - self._processed_events[event_id] < self._event_cache_ttl:
                    return True
            self._processed_events[event_id] = now
            return False

    def handle_emby_webhook(self, request_data: dict = None, request=None) -> dict:
        """处理 Emby Webhook"""
        if not self._enabled:
            logger.warning("插件未启用，忽略Webhook请求")
            return {"code": 403, "message": "Plugin disabled"}
        
        try:
            data = request_data or {}
            if request and hasattr(request, 'json'):
                data = request.json() if callable(request.json) else request.json
            
            event_type = data.get("Event") or data.get("event", "")
            logger.info(f"收到事件: {event_type}")
            
            # 生成事件ID用于去重
            item_id = data.get('Item', {}).get('Id', '')
            event_id = f"{event_type}_{item_id}_{datetime.now().timestamp()}"
            if self._is_duplicate_event(event_id):
                logger.info(f"忽略重复事件: {event_type}")
                return {"code": 200, "message": "忽略重复事件"}
            
            if event_type == "item.rate":
                return self._process_favourite(data)
            elif event_type == "library.deleted":
                return self._process_delete(data)
            return {"code": 200, "message": f"忽略: {event_type}"}
        except Exception as e:
            logger.error(f"处理失败: {e}")
            return {"code": 500, "message": str(e)}

    def _process_favourite(self, data: dict) -> dict:
        try:
            logger.info(f"收藏事件完整数据: {json.dumps(data, ensure_ascii=False)}")
            
            item = data.get("Item", {})
            user = data.get("User", {})
            
            item_name = item.get("SeriesName") or item.get("ParentName") or item.get("Name", "未知")
            user_name = user.get("Name", "未知")
            
            user_data = item.get("UserData", {})
            is_favorite = user_data.get("IsFavorite", False)
            
            rating = user_data.get("Rating")
            if rating is not None and not is_favorite:
                logger.info(f"评分事件（非收藏）: rating={rating}")
                return {"code": 200, "message": "非收藏操作，已忽略"}
            
            cfg = self._get_config_safe()
            downloader_names = cfg.get("downloaders", [])
            if not downloader_names:
                logger.warning("未配置下载器")
                return {"code": 400, "message": "未配置下载器"}
            
            fuzzy = cfg.get("fuzzy_match", True)
            seed_tag = cfg.get("seed_tag", "保种")
            send_notify = cfg.get("send_notify", True)
            
            logger.info(f"收藏事件: 剧名={item_name}, 用户={user_name}, 收藏={is_favorite}, 模糊匹配={fuzzy}, 下载器={downloader_names}")
            
            total_matched = 0
            all_matched_names = []
            downloader_results = []
            
            if is_favorite:
                action = "收藏"
                # 遍历所有下载器
                for downloader_name in downloader_names:
                    matched, names = self._manage_tag(downloader_name, item_name, seed_tag, "add", fuzzy)
                    total_matched += matched
                    all_matched_names.extend(names)
                    downloader_results.append(f"{downloader_name}: {matched}个")
                msg = f"已为 {total_matched} 个种子添加保种标签\n{', '.join(downloader_results)}"
            else:
                action = "取消收藏"
                for downloader_name in downloader_names:
                    matched, names = self._manage_tag(downloader_name, item_name, seed_tag, "remove", fuzzy)
                    total_matched += matched
                    all_matched_names.extend(names)
                    downloader_results.append(f"{downloader_name}: {matched}个")
                msg = f"已为 {total_matched} 个种子移除保种标签\n{', '.join(downloader_results)}"
            
            if send_notify and total_matched > 0:
                self._send_notification(f"{action}: {item_name}", msg, all_matched_names)
            
            self._record_event({
                "event_id": f"{datetime.now().timestamp()}_{action}",
                "event_type": action,
                "item_name": item_name,
                "user_name": user_name,
                "matched_count": total_matched,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": msg
            })
            return {"code": 200, "message": msg}
        except Exception as e:
            logger.error(f"处理收藏失败: {e}")
            return {"code": 500, "message": str(e)}

    def _process_delete(self, data: dict) -> dict:
        try:
            logger.info(f"删除事件完整数据: {json.dumps(data, ensure_ascii=False)}")
            
            item = data.get("Item", {})
            
            if item.get("Type") == "Episode":
                logger.info("跳过单集删除")
                return {"code": 200, "message": "跳过单集删除"}
            
            item_name = item.get("SeriesName") or item.get("ParentName") or item.get("Name", "未知")
            
            cfg = self._get_config_safe()
            downloader_names = cfg.get("downloaders", [])
            if not downloader_names:
                logger.warning("未配置下载器")
                return {"code": 400, "message": "未配置下载器"}
            
            fuzzy = cfg.get("fuzzy_match", True)
            delete_action = cfg.get("delete_action", "remove_tag")
            send_notify = cfg.get("send_notify", True)
            async_delete = cfg.get("async_delete", True)
            seed_tag = cfg.get("seed_tag", "保种")
            
            logger.info(f"删除事件: 剧名={item_name}, 操作={delete_action}, 模糊匹配={fuzzy}, 下载器={downloader_names}")
            
            event_id = f"{datetime.now().timestamp()}_delete"
            self._record_event({
                "event_id": event_id,
                "event_type": "删除",
                "item_name": item_name,
                "user_name": "系统",
                "matched_count": 0,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "处理中..."
            })
            
            if async_delete:
                # 检查线程池是否关闭
                if not self._shutdown:
                    self._executor.submit(self._execute_delete, event_id, downloader_names, item_name, 
                                         fuzzy, send_notify, delete_action, seed_tag)
                    return {"code": 200, "message": "删除任务已提交"}
                else:
                    logger.warning("线程池已关闭，同步执行删除")
                    # 降级为同步执行
                    total_matched, total_success, all_names = self._execute_delete_sync(
                        downloader_names, item_name, fuzzy, delete_action, seed_tag
                    )
                    self._update_event_status(event_id, total_matched, f"完成: 匹配{total_matched}个, 成功{total_success}个")
                    if send_notify and total_matched > 0:
                        self._send_notification(f"删除: {item_name}", f"已处理 {total_success}/{total_matched} 个种子", all_names)
                    return {"code": 200, "message": f"处理完成: {total_success}/{total_matched}"}
            else:
                total_matched, total_success, all_names = self._execute_delete_sync(
                    downloader_names, item_name, fuzzy, delete_action, seed_tag
                )
                self._update_event_status(event_id, total_matched, f"完成: 匹配{total_matched}个, 成功{total_success}个")
                if send_notify and total_matched > 0:
                    self._send_notification(f"删除: {item_name}", f"已处理 {total_success}/{total_matched} 个种子", all_names)
                return {"code": 200, "message": f"处理完成: {total_success}/{total_matched}"}
        except Exception as e:
            logger.error(f"处理删除失败: {e}")
            return {"code": 500, "message": str(e)}

    def _execute_delete(self, event_id: str, downloader_names: list, item_name: str, 
                        fuzzy: bool, send_notify: bool, action: str, tag: str):
        """异步执行删除操作（支持多下载器）"""
        if self._shutdown:
            logger.warning("插件正在关闭，跳过异步任务")
            return
        
        try:
            total_matched = 0
            total_success = 0
            all_names = []
            downloader_results = []
            
            for downloader_name in downloader_names:
                matched, names, hashes = self._find_torrents(downloader_name, item_name, fuzzy)
                if matched == 0:
                    downloader_results.append(f"{downloader_name}: 未找到匹配")
                    continue
                
                all_names.extend(names)
                total_matched += matched
                
                if action == "remove_tag":
                    success = self._batch_remove_tag(hashes, tag, downloader_name)
                    downloader_results.append(f"{downloader_name}: 移除标签 {success}/{matched}")
                elif action == "pause":
                    success = self._pause_torrents(hashes, downloader_name)
                    downloader_results.append(f"{downloader_name}: 暂停 {success}/{matched}")
                elif action == "delete":
                    success = self._delete_torrents(hashes, downloader_name, False)
                    downloader_results.append(f"{downloader_name}: 删除 {success}/{matched}")
                elif action == "delete_with_file":
                    success = self._delete_torrents(hashes, downloader_name, True)
                    downloader_results.append(f"{downloader_name}: 删除并删文件 {success}/{matched}")
                else:
                    success = 0
                    downloader_results.append(f"{downloader_name}: 未知操作")
                
                total_success += success
            
            msg = f"总计: {total_success}/{total_matched}\n" + "\n".join(downloader_results)
            self._update_event_status(event_id, total_matched, msg)
            
            if send_notify and total_matched > 0:
                display_names = all_names[:5] if all_names else []
                self._send_notification(f"删除: {item_name}", msg, display_names)
                
        except Exception as e:
            logger.error(f"后台删除失败: {e}")
            self._update_event_status(event_id, 0, f"失败: {str(e)}")

    def _execute_delete_sync(self, downloader_names: list, item_name: str, fuzzy: bool, action: str, tag: str) -> tuple:
        """同步执行删除操作（支持多下载器）"""
        total_matched = 0
        total_success = 0
        all_names = []
        
        for downloader_name in downloader_names:
            matched, names, hashes = self._find_torrents(downloader_name, item_name, fuzzy)
            if matched == 0:
                continue
            
            all_names.extend(names)
            total_matched += matched
            
            if action == "remove_tag":
                success = self._batch_remove_tag(hashes, tag, downloader_name)
            elif action == "pause":
                success = self._pause_torrents(hashes, downloader_name)
            elif action == "delete":
                success = self._delete_torrents(hashes, downloader_name, False)
            elif action == "delete_with_file":
                success = self._delete_torrents(hashes, downloader_name, True)
            else:
                success = 0
            
            total_success += success
        
        return total_matched, total_success, all_names

    def _manage_tag(self, downloader_name: str, media_name: str, tag: str, op: str, fuzzy: bool) -> tuple:
        """管理种子标签（单个下载器）"""
        matched, names, hashes = self._find_torrents(downloader_name, media_name, fuzzy)
        if matched == 0:
            return 0, []
        
        downloader, dl_type = self._get_downloader(downloader_name)
        if not downloader:
            logger.warning(f"下载器 {downloader_name} 不可用")
            return 0, []
        
        success = 0
        for h in hashes:
            if op == "add":
                ok = self._add_tag(h, tag, downloader, dl_type)
            else:
                ok = self._remove_tag(h, tag, downloader, dl_type)
            if ok:
                success += 1
        
        logger.info(f"下载器 {downloader_name} 标签操作完成: {op}, 成功 {success}/{matched}")
        return success, names

    def _find_torrents(self, downloader_name: str, media_name: str, fuzzy: bool) -> tuple:
        """用剧名作为关键字匹配种子"""
        logger.info(f"[匹配] 下载器={downloader_name}, 剧名={media_name}, 模糊匹配={fuzzy}")
        
        downloader, dl_type = self._get_downloader(downloader_name)
        if not downloader:
            logger.warning("[匹配] 下载器不可用")
            return 0, [], []
        
        torrents, error = downloader.get_torrents()
        if error:
            logger.error(f"[匹配] 获取种子列表失败: {error}")
            return 0, [], []
        
        logger.info(f"[匹配] 获取到 {len(torrents)} 个种子，开始匹配...")
        
        hashes, names = [], []
        for t in torrents:
            if hasattr(t, 'name'):
                name = t.name
                h = t.hashString if hasattr(t, 'hashString') else getattr(t, 'hash', '')
            else:
                name = t.get("name", "")
                h = t.get("hash", "") or t.get("hashString", "")
            
            if not name:
                continue
            
            if fuzzy:
                if len(media_name) >= 3:
                    match = media_name.lower() in name.lower()
                else:
                    match = media_name.lower() == name.lower()
            else:
                match = media_name.lower() == name.lower()
            
            if match:
                if fuzzy and media_name.lower() != name.lower() and len(media_name) >= 3:
                    ratio = len(media_name) / len(name)
                    if ratio < 0.3:
                        logger.warning(f"[匹配] 匹配度较低: {media_name} vs {name} (比例: {ratio:.2f})")
                
                if h:
                    hashes.append(h)
                    names.append(name)
                    logger.info(f"[匹配] ✓ 匹配成功: {name} (哈希: {h[:8]}...)")
                else:
                    logger.warning(f"[匹配] 匹配到种子但无哈希值: {name}")
        
        if hashes:
            logger.info(f"[匹配] 共匹配到 {len(hashes)} 个种子")
        else:
            logger.info(f"[匹配] ✗ 未匹配到种子，关键字: {media_name}")
            sample_names = []
            for t in torrents[:5]:
                if hasattr(t, 'name'):
                    sample_names.append(t.name)
                else:
                    sample_names.append(t.get("name", ""))
            logger.info(f"[匹配] 种子示例: {sample_names}")
        
        return len(hashes), names, hashes

    def _get_downloader(self, name: str) -> Tuple[Optional[Any], Optional[str]]:
        """获取下载器实例和类型（带缓存）"""
        now = time.time()
        
        # 定期清理缓存
        if now - self._last_cache_cleanup > self._cache_cleanup_interval:
            expired = [k for k, (_, _, t) in self._downloader_cache.items() if now - t > self._cache_ttl]
            for k in expired:
                del self._downloader_cache[k]
            self._last_cache_cleanup = now
        
        # 检查缓存
        if name in self._downloader_cache:
            instance, dl_type, cache_time = self._downloader_cache[name]
            if now - cache_time < self._cache_ttl:
                try:
                    if instance:
                        if hasattr(instance, 'is_inactive'):
                            if not instance.is_inactive():
                                return instance, dl_type
                        else:
                            return instance, dl_type
                except:
                    if instance:
                        return instance, dl_type
        
        try:
            service = DownloaderHelper().get_service(name=name)
            if not service or not service.instance:
                logger.warning(f"下载器服务 {name} 不存在")
                return None, None
            
            instance = service.instance
            
            try:
                if hasattr(instance, 'is_inactive') and instance.is_inactive():
                    logger.warning(f"下载器 {name} 未连接")
                    return None, None
            except:
                pass
            
            dl_type = None
            class_name = instance.__class__.__name__.lower()
            if 'qbittorrent' in class_name:
                dl_type = "qbittorrent"
            elif 'transmission' in class_name:
                dl_type = "transmission"
            elif hasattr(instance, 'qbc'):
                dl_type = "qbittorrent"
            elif hasattr(instance, 'trpc'):
                dl_type = "transmission"
            
            if not dl_type:
                logger.warning(f"不支持的下载器类型: {class_name}")
                return None, None
            
            self._downloader_cache[name] = (instance, dl_type, now)
            
            logger.info(f"获取下载器成功: {name}, 类型: {dl_type}")
            return instance, dl_type
        except Exception as e:
            logger.error(f"获取下载器失败: {e}")
            return None, None

    def _add_tag(self, h: str, tag: str, dl, dl_type: str) -> bool:
        """添加标签/分类到种子"""
        try:
            if dl_type == "qbittorrent":
                if hasattr(dl, 'add_torrent_tags'):
                    return dl.add_torrent_tags(h, tag)
                if hasattr(dl, 'qbc'):
                    dl.qbc.torrents_add_tags(tags=tag, torrent_hashes=h)
                    return True
            elif dl_type == "transmission":
                if hasattr(dl, 'add_torrent_label'):
                    return dl.add_torrent_label(h, tag)
                if hasattr(dl, 'set_torrent') and hasattr(dl, 'trpc'):
                    try:
                        dl.set_torrent(h, labels=[tag])
                        return True
                    except:
                        pass
            return False
        except Exception as e:
            logger.error(f"添加标签失败 [哈希={h}]: {e}")
            return False

    def _remove_tag(self, h: str, tag: str, dl, dl_type: str) -> bool:
        """从种子移除标签/分类"""
        try:
            if dl_type == "qbittorrent":
                if hasattr(dl, 'remove_torrent_tags'):
                    return dl.remove_torrent_tags(h, tag)
                if hasattr(dl, 'qbc'):
                    dl.qbc.torrents_remove_tags(tags=tag, torrent_hashes=h)
                    return True
            elif dl_type == "transmission":
                if hasattr(dl, 'remove_torrent_label'):
                    return dl.remove_torrent_label(h, tag)
                if hasattr(dl, 'get_torrent') and hasattr(dl, 'set_torrent'):
                    try:
                        torrent = dl.get_torrent(h)
                        if torrent:
                            current_labels = []
                            if hasattr(torrent, 'labels'):
                                current_labels = torrent.labels
                            elif isinstance(torrent, dict):
                                current_labels = torrent.get('labels', [])
                            
                            if tag in current_labels:
                                new_labels = [l for l in current_labels if l != tag]
                                if hasattr(dl, 'set_torrent'):
                                    dl.set_torrent(h, labels=new_labels)
                                    return True
                    except Exception as e:
                        logger.warning(f"通过API移除TR标签失败: {e}")
            return False
        except Exception as e:
            logger.error(f"移除标签失败 [哈希={h}]: {e}")
            return False

    def _batch_remove_tag(self, hashes: list, tag: str, dl_name: str) -> int:
        """批量移除标签"""
        BATCH_SIZE = 100
        
        # 分批处理
        if len(hashes) > BATCH_SIZE:
            logger.warning(f"批量操作数量过多 ({len(hashes)}), 将分批处理")
            total_success = 0
            for i in range(0, len(hashes), BATCH_SIZE):
                batch = hashes[i:i+BATCH_SIZE]
                total_success += self._batch_remove_tag(batch, tag, dl_name)
            return total_success
        
        dl, dt = self._get_downloader(dl_name)
        if not dl:
            logger.warning(f"下载器 {dl_name} 不可用")
            return 0
        
        if dt == "qbittorrent" and hasattr(dl, 'qbc'):
            try:
                dl.qbc.torrents_remove_tags(tags=tag, torrent_hashes='|'.join(hashes))
                logger.info(f"批量移除标签成功: {len(hashes)} 个种子")
                return len(hashes)
            except Exception as e:
                logger.warning(f"批量移除标签失败，回退到单个操作: {e}")
        
        success = 0
        for h in hashes:
            if self._remove_tag(h, tag, dl, dt):
                success += 1
        return success

    def _pause_torrents(self, hashes: list, dl_name: str) -> int:
        """暂停种子"""
        dl, dl_type = self._get_downloader(dl_name)
        if not dl:
            logger.warning(f"下载器 {dl_name} 不可用")
            return 0
        
        success = 0
        for h in hashes:
            try:
                if dl_type == "qbittorrent":
                    if hasattr(dl, 'pause_torrents'):
                        if dl.pause_torrents([h]):
                            success += 1
                    elif hasattr(dl, 'qbc'):
                        dl.qbc.torrents_pause([h])
                        success += 1
                elif dl_type == "transmission":
                    if hasattr(dl, 'stop_torrent'):
                        if dl.stop_torrent(h):
                            success += 1
                    elif hasattr(dl, 'trpc'):
                        dl.trpc.stop_torrent(h)
                        success += 1
                logger.debug(f"暂停种子成功: {h[:8]}...")
            except Exception as e:
                logger.error(f"暂停种子失败 {h[:8]}...: {e}")
        return success

    def _delete_torrents(self, hashes: list, dl_name: str, delete_file: bool) -> int:
        """删除种子"""
        dl, dl_type = self._get_downloader(dl_name)
        if not dl:
            logger.warning(f"下载器 {dl_name} 不可用")
            return 0
        
        success = 0
        for h in hashes:
            try:
                if dl_type == "qbittorrent":
                    if hasattr(dl, 'delete_torrents'):
                        if dl.delete_torrents(ids=[h], delete_file=delete_file):
                            success += 1
                    elif hasattr(dl, 'qbc'):
                        dl.qbc.torrents_delete(delete_files=delete_file, torrent_hashes=h)
                        success += 1
                elif dl_type == "transmission":
                    if hasattr(dl, 'remove_torrent'):
                        if dl.remove_torrent(h, delete_data=delete_file):
                            success += 1
                    elif hasattr(dl, 'trpc'):
                        dl.trpc.remove_torrent(h, delete_data=delete_file)
                        success += 1
                logger.debug(f"删除种子成功: {h[:8]}...")
            except Exception as e:
                logger.error(f"删除种子失败 {h[:8]}...: {e}")
        return success

    def _update_event_status(self, event_id: str, matched: int, status: str):
        """更新事件状态"""
        with self._event_lock:
            for e in self._received_events:
                if e.get("event_id") == event_id:
                    e["matched_count"] = matched
                    e["status"] = status
                    try:
                        self.save_data("received_events", self._received_events)
                    except Exception as ex:
                        logger.error(f"保存事件状态失败: {ex}")
                    break

    def _record_event(self, event: dict):
        """记录事件"""
        with self._event_lock:
            self._received_events.insert(0, event)
            if len(self._received_events) > 50:
                self._received_events = self._received_events[:50]
            try:
                self.save_data("received_events", self._received_events)
            except Exception as e:
                logger.error(f"保存事件记录失败: {e}")

    def _send_notification(self, title: str, msg: str, names: list = None):
        """发送通知（带节流）"""
        notify_key = title
        now = time.time()
        if notify_key in self._last_notify_time:
            if now - self._last_notify_time[notify_key] < self._notify_throttle:
                logger.debug(f"通知节流，跳过发送: {title}")
                return
        
        self._last_notify_time[notify_key] = now
        
        if names:
            msg += f"\n种子: {', '.join(names[:3])}"
            if len(names) > 3:
                msg += f" 等{len(names)}个"
        
        try:
            if hasattr(self, 'post_message'):
                self.post_message(title=f"【{self.plugin_name}】{title}", text=msg, mtype=NotificationType.SiteMessage)
            else:
                logger.info(f"模拟发送通知 - 标题: {title}, 内容: {msg}")
        except Exception as e:
            logger.error(f"发送通知失败: {e}")

    def stop_service(self):
        """停止服务"""
        self._enabled = False
        self._shutdown = True
        try:
            self._executor.shutdown(wait=True, timeout=30)
        except Exception as e:
            logger.error(f"关闭线程池失败: {e}")
        logger.info("媒体同步保护插件已停止")