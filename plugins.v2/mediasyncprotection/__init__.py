import json
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Tuple
from datetime import datetime

from app.plugins import _PluginBase
from app.log import logger
from app.core.event import eventmanager, Event
from app.schemas.types import EventType
from app.schemas import NotificationType
from app.helper.downloader import DownloaderHelper


class MediaSyncProtection(_PluginBase):
    plugin_name = "媒体同步保护"
    plugin_desc = "监听Emby Webhook，收藏时添加/移除保种标签，删除时对种子执行操作"
    plugin_icon = "Amule_B.png"
    plugin_version = "1.0.0"
    plugin_author = "AI"
    plugin_config_prefix = "mediasyncprotection_"
    plugin_order = 24
    auth_level = 1

    _enabled = False
    _webhook_path = "/mediasync"
    _received_events = []
    _event_lock = threading.Lock()
    _executor = ThreadPoolExecutor(max_workers=3)

    def init_plugin(self, config: dict = None):
        config = config or {}
        self._enabled = config.get("enabled", False)
        with self._event_lock:
            self._received_events = (self.get_data("received_events") or [])[:50]
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
            "auth": "apikey",
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
                                    {"component": "VSelect", "props": {"model": "downloader", "label": "下载器", "items": options}}
                                ]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {"component": "VTextField", "props": {"model": "seed_tag", "label": "保种标签", "placeholder": "保种"}}
                                ]
                            }
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
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
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {"component": "VSwitch", "props": {"model": "fuzzy_match", "label": "模糊匹配"}}
                                ]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {"component": "VSwitch", "props": {"model": "send_notify", "label": "发送通知"}}
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
                                            "text": "Webhook URL: /api/v1/plugin/MediaSyncProtection/mediasync?apikey=系统API_KEY"
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
            "downloader": None,
            "seed_tag": "保种",
            "delete_action": "remove_tag",
            "fuzzy_match": True,
            "send_notify": True
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

    def handle_emby_webhook(self, request_data: dict = None, request=None) -> dict:
        try:
            data = request_data or {}
            if request and hasattr(request, 'json'):
                data = request.json() if callable(request.json) else request.json
            
            event_type = data.get("Event") or data.get("event", "")
            logger.info(f"收到事件: {event_type}")
            
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
            is_favorite = item.get("UserData", {}).get("IsFavorite", False)
            
            cfg = self.get_config() or {}
            if not cfg.get("downloader"):
                logger.warning("未配置下载器")
                return {"code": 400, "message": "未配置下载器"}
            
            fuzzy = cfg.get("fuzzy_match", True)
            logger.info(f"收藏事件: 剧名={item_name}, 用户={user_name}, 收藏={is_favorite}, 模糊匹配={fuzzy}")
            
            if is_favorite:
                action = "收藏"
                matched, names = self._manage_tag(cfg["downloader"], item_name, cfg.get("seed_tag", "保种"), "add", fuzzy)
                msg = f"已为 {matched} 个种子添加保种标签"
            else:
                action = "取消收藏"
                matched, names = self._manage_tag(cfg["downloader"], item_name, cfg.get("seed_tag", "保种"), "remove", fuzzy)
                msg = f"已为 {matched} 个种子移除保种标签"
            
            if cfg.get("send_notify") and matched > 0:
                self._send_notification(f"{action}: {item_name}", msg, names)
            
            self._record_event({
                "event_id": f"{datetime.now().timestamp()}_{action}",
                "event_type": action,
                "item_name": item_name,
                "user_name": user_name,
                "matched_count": matched,
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
            
            cfg = self.get_config() or {}
            if not cfg.get("downloader"):
                return {"code": 400, "message": "未配置下载器"}
            
            fuzzy = cfg.get("fuzzy_match", True)
            delete_action = cfg.get("delete_action", "remove_tag")
            
            logger.info(f"删除事件: 剧名={item_name}, 操作={delete_action}, 模糊匹配={fuzzy}")
            
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
            
            if cfg.get("async_delete", True):
                self._executor.submit(self._execute_delete, event_id, cfg["downloader"], item_name, 
                                     fuzzy, cfg.get("send_notify", True), delete_action,
                                     cfg.get("seed_tag", "保种"))
                return {"code": 200, "message": "删除任务已提交"}
            else:
                matched, names, success = self._execute_delete_sync(cfg["downloader"], item_name, fuzzy,
                                                                     delete_action, cfg.get("seed_tag", "保种"))
                self._update_event_status(event_id, matched, f"完成: 匹配{matched}个, 成功{success}个")
                if cfg.get("send_notify") and matched > 0:
                    self._send_notification(f"删除: {item_name}", f"已处理 {success}/{matched} 个种子", names)
                return {"code": 200, "message": f"处理完成: {success}/{matched}"}
        except Exception as e:
            logger.error(f"处理删除失败: {e}")
            return {"code": 500, "message": str(e)}

    def _execute_delete(self, event_id: str, downloader_name: str, item_name: str, 
                        fuzzy: bool, send_notify: bool, action: str, tag: str):
        try:
            matched, names, hashes = self._find_torrents(downloader_name, item_name, fuzzy)
            if matched == 0:
                self._update_event_status(event_id, 0, "未找到匹配的种子")
                return
            
            if action == "remove_tag":
                success = self._batch_remove_tag(hashes, tag, downloader_name)
                msg = f"已移除 {success}/{matched} 个种子的保种标签"
            elif action == "pause":
                success = self._pause_torrents(hashes, downloader_name)
                msg = f"已暂停 {success}/{matched} 个种子"
            elif action == "delete":
                success = self._delete_torrents(hashes, downloader_name, False)
                msg = f"已删除 {success}/{matched} 个种子（保留文件）"
            elif action == "delete_with_file":
                success = self._delete_torrents(hashes, downloader_name, True)
                msg = f"已删除 {success}/{matched} 个种子（删除文件）"
            else:
                msg = f"未知操作: {action}"
                success = 0
            
            self._update_event_status(event_id, matched, msg)
            if send_notify and matched > 0:
                self._send_notification(f"删除: {item_name}", msg, names[:5])
        except Exception as e:
            logger.error(f"后台删除失败: {e}")
            self._update_event_status(event_id, 0, f"失败: {e}")

    def _execute_delete_sync(self, downloader_name: str, item_name: str, fuzzy: bool, action: str, tag: str) -> tuple:
        matched, names, hashes = self._find_torrents(downloader_name, item_name, fuzzy)
        if matched == 0:
            return 0, [], 0
        
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
        return matched, names, success

    def _manage_tag(self, downloader_name: str, media_name: str, tag: str, op: str, fuzzy: bool) -> tuple:
        matched, names, hashes = self._find_torrents(downloader_name, media_name, fuzzy)
        if matched == 0:
            return 0, []
        
        downloader, dl_type = self._get_downloader(downloader_name)
        if not downloader:
            return 0, []
        
        success = 0
        for h in hashes:
            if op == "add":
                ok = self._add_tag(h, tag, downloader, dl_type)
            else:
                ok = self._remove_tag(h, tag, downloader, dl_type)
            if ok:
                success += 1
        return success, names

    def _find_torrents(self, downloader_name: str, media_name: str, fuzzy: bool) -> tuple:
        """用剧名作为关键字匹配种子"""
        logger.info(f"[匹配] 下载器={downloader_name}, 剧名={media_name}, 模糊匹配={fuzzy}")
        
        downloader, _ = self._get_downloader(downloader_name)
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
            name = t.name if hasattr(t, 'name') else t.get("name", "")
            if not name:
                continue
            
            if fuzzy:
                match = media_name in name
            else:
                match = media_name == name
            
            if match:
                h = t.hashString if hasattr(t, 'hashString') else t.get("hash", "")
                if h:
                    hashes.append(h)
                    names.append(name)
                    logger.info(f"[匹配] ✓ 匹配成功: {name}")
        
        if hashes:
            logger.info(f"[匹配] 共匹配到 {len(hashes)} 个种子")
        else:
            logger.info(f"[匹配] ✗ 未匹配到种子，关键字: {media_name}")
            sample_names = [t.name if hasattr(t, 'name') else t.get("name", "") for t in torrents[:5]]
            logger.info(f"[匹配] 种子示例: {sample_names}")
        
        return len(hashes), names, hashes

    def _get_downloader(self, name: str):
        try:
            service = DownloaderHelper().get_service(name=name)
            if service and service.instance and not service.instance.is_inactive():
                dl_type = "qbittorrent" if ('qbittorrent' in str(type(service.instance)).lower() or hasattr(service.instance, 'qbc')) else "transmission"
                return service.instance, dl_type
            return None, None
        except Exception as e:
            logger.error(f"获取下载器失败: {e}")
            return None, None

    def _add_tag(self, h: str, tag: str, dl, dl_type: str) -> bool:
        try:
            if dl_type == "qbittorrent":
                if hasattr(dl, 'add_torrent_tags'):
                    return dl.add_torrent_tags(h, tag)
                if hasattr(dl, 'qbc'):
                    dl.qbc.torrents_add_tags(tags=tag, torrent_hashes=h)
                    return True
            else:
                if hasattr(dl, 'add_torrent_label'):
                    return dl.add_torrent_label(h, tag)
            return False
        except Exception as e:
            logger.error(f"添加标签失败: {e}")
            return False

    def _remove_tag(self, h: str, tag: str, dl, dl_type: str) -> bool:
        try:
            if dl_type == "qbittorrent":
                if hasattr(dl, 'remove_torrent_tags'):
                    return dl.remove_torrent_tags(h, tag)
                if hasattr(dl, 'qbc'):
                    dl.qbc.torrents_remove_tags(tags=tag, torrent_hashes=h)
                    return True
            else:
                if hasattr(dl, 'remove_torrent_label'):
                    return dl.remove_torrent_label(h, tag)
            return False
        except Exception as e:
            logger.error(f"移除标签失败: {e}")
            return False

    def _batch_remove_tag(self, hashes: list, tag: str, dl_name: str) -> int:
        success = 0
        dl, dt = self._get_downloader(dl_name)
        if not dl:
            return 0
        for h in hashes:
            if self._remove_tag(h, tag, dl, dt):
                success += 1
        return success

    def _pause_torrents(self, hashes: list, dl_name: str) -> int:
        dl, _ = self._get_downloader(dl_name)
        if not dl:
            return 0
        success = 0
        for h in hashes:
            try:
                if hasattr(dl, 'pause_torrents') and dl.pause_torrents([h]):
                    success += 1
                elif hasattr(dl, 'stop_torrent') and dl.stop_torrent(h):
                    success += 1
            except:
                pass
        return success

    def _delete_torrents(self, hashes: list, dl_name: str, delete_file: bool) -> int:
        dl, _ = self._get_downloader(dl_name)
        if not dl:
            return 0
        success = 0
        for h in hashes:
            try:
                if dl.delete_torrents(ids=[h], delete_file=delete_file):
                    success += 1
            except:
                pass
        return success

    def _update_event_status(self, event_id: str, matched: int, status: str):
        with self._event_lock:
            for e in self._received_events:
                if e.get("event_id") == event_id:
                    e["matched_count"] = matched
                    e["status"] = status
                    self.save_data("received_events", self._received_events)
                    break

    def _record_event(self, event: dict):
        with self._event_lock:
            self._received_events.insert(0, event)
            if len(self._received_events) > 50:
                self._received_events = self._received_events[:50]
            self.save_data("received_events", self._received_events)

    def _send_notification(self, title: str, msg: str, names: list = None):
        if names:
            msg += f"\n种子: {', '.join(names[:3])}"
            if len(names) > 3:
                msg += f" 等{len(names)}个"
        self.post_message(title=f"【{self.plugin_name}】{title}", text=msg, mtype=NotificationType.SiteMessage)

    def stop_service(self):
        self._enabled = False
        self._executor.shutdown(wait=False)
        logger.info("媒体同步保护插件已停止")
