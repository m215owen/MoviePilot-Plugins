import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from aiohttp import web

from app.plugins import _PluginBase
from app.core.event import eventmanager, Event
from app.schemas.types import EventType
from app.log import logger


class MediaSyncProtection(_PluginBase):
    """媒体同步保护：收藏时从刷流移除，删除时标记种子待删除"""
    
    # 插件元数据
    plugin_name = "媒体同步保护"
    plugin_desc = "Emby收藏时从刷流插件移除种子，Emby删除媒体时标记种子待删除（由刷流插件执行）"
    plugin_icon = "sync_file.png"
    plugin_version = "1.0.0"
    plugin_author = "AI"
    plugin_config_prefix = "mediasyncprotection_"
    plugin_order = 24
    auth_level = 2
    
    # 目标刷流插件
    TARGET_PLUGINS = ["BrushFlowLowFreq", "BrushFlow", "站点刷流（低频版）"]
    
    # 私有属性
    _config = {}
    _enabled = False
    
    def init_plugin(self, config: dict = None):
        """初始化插件"""
        if config:
            self._config = config
            self._enabled = config.get("enabled", False)
        logger.info(f"媒体同步保护插件已启动，启用状态: {self._enabled}")
    
    def get_state(self) -> bool:
        """返回插件状态"""
        return self._enabled
    
    def get_api(self) -> List[Dict[str, Any]]:
        """注册API，接收Emby Webhook"""
        return [
            {
                "path": "/emby_webhook",
                "endpoint": self.receive_emby_webhook,
                "methods": ["POST"],
                "summary": "接收Emby Webhook",
                "description": "处理Emby的收藏和删除事件",
                "auth": "none"
            }
        ]
    
    async def receive_emby_webhook(self, request: web.Request) -> web.Response:
        """
        处理Emby Webhook
        支持的事件类型：
        - item.markedfavorite: 收藏 → 从刷流移除
        - item.removed: 删除媒体 → 标记种子待删除
        """
        # 插件未启用时直接返回
        if not self._enabled:
            return web.Response(status=200, text="Plugin disabled")
        
        try:
            form_data = await request.post()
            
            event_type = form_data.get("Event", "")
            item_name = form_data.get("ItemName", "")
            
            logger.info(f"收到Emby Webhook: 事件={event_type}, 媒体={item_name}")
            
            # 1. 收藏事件：从刷流插件移除（不删除文件）
            if event_type == "item.markedfavorite" and item_name:
                self.remove_from_brush_plugins(item_name)
                if self._config.get("notify", True):
                    self.post_message(
                        title="📌 收藏保护",
                        text=f"「{item_name}」已收藏\n已从刷流任务中移除，该种子将不会被自动删除"
                    )
            
            # 2. 删除媒体事件：标记种子待删除（由刷流插件执行）
            elif event_type in ["item.removed", "item.deleted"] and item_name:
                self.mark_torrents_for_deletion(item_name)
            
            return web.Response(status=200, text="OK")
            
        except Exception as e:
            logger.error(f"处理Emby Webhook失败: {e}")
            return web.Response(status=500, text=str(e))
    
    def remove_from_brush_plugins(self, keyword: str):
        """
        从刷流插件中移除匹配的种子（收藏时调用）
        直接从数据中删除记录，种子文件保留
        """
        if not keyword or not self._enabled:
            return
        
        removed_count = 0
        removed_details = []
        keyword_lower = keyword.lower()
        
        for plugin_id in self.TARGET_PLUGINS:
            torrents_data = self.get_data("torrents", plugin_id)
            
            if not torrents_data or not isinstance(torrents_data, dict):
                continue
            
            modified = False
            to_remove = []
            
            for torrent_hash, torrent_info in torrents_data.items():
                title = torrent_info.get("title", "")
                if keyword_lower in title.lower():
                    to_remove.append(torrent_hash)
                    removed_details.append({
                        "hash": torrent_hash,
                        "title": title,
                        "site": torrent_info.get("site_name"),
                        "plugin": plugin_id
                    })
                    logger.debug(f"匹配成功: {keyword} -> {title}")
            
            for torrent_hash in to_remove:
                del torrents_data[torrent_hash]
                modified = True
                removed_count += 1
            
            if modified:
                self.save_data("torrents", torrents_data, plugin_id)
                logger.info(f"从插件 {plugin_id} 移除了 {len(to_remove)} 个种子")
        
        # 记录历史
        if removed_details:
            self._save_removed_history(removed_details, keyword)
    
    def mark_torrents_for_deletion(self, media_name: str):
        """
        标记种子待删除（删除媒体时调用）
        在刷流插件数据中标记 pending_delete，让刷流插件的 check 方法执行实际删除
        """
        if not media_name or not self._enabled:
            return
        
        keyword_lower = media_name.lower()
        marked_count = 0
        marked_details = []
        
        for plugin_id in self.TARGET_PLUGINS:
            torrents_data = self.get_data("torrents", plugin_id)
            
            if not torrents_data or not isinstance(torrents_data, dict):
                continue
            
            modified = False
            
            for torrent_hash, torrent_info in torrents_data.items():
                title = torrent_info.get("title", "")
                
                # 跳过已删除或已标记的
                if torrent_info.get("deleted") or torrent_info.get("pending_delete"):
                    continue
                
                if keyword_lower in title.lower():
                    # 标记为待删除
                    torrent_info["pending_delete"] = True
                    torrent_info["pending_delete_time"] = time.time()
                    torrent_info["pending_delete_reason"] = f"媒体库删除: {media_name}"
                    modified = True
                    marked_count += 1
                    marked_details.append({
                        "hash": torrent_hash,
                        "title": title,
                        "site": torrent_info.get("site_name"),
                        "plugin": plugin_id
                    })
                    logger.info(f"标记种子待删除: {title[:50]}...")
            
            if modified:
                self.save_data("torrents", torrents_data, plugin_id)
                logger.info(f"在插件 {plugin_id} 中标记了 {marked_count} 个种子待删除")
        
        # 触发刷流插件的检查，让其立即处理待删除的种子
        if marked_count > 0:
            self._trigger_brush_check()
            
            # 发送通知
            if self._config.get("notify", True):
                self.post_message(
                    title="🗑️ 媒体删除同步",
                    text=f"「{media_name}」已从媒体库删除\n已标记 {marked_count} 个种子待删除，将由刷流插件执行"
                )
        else:
            logger.info(f"未找到匹配的种子: {media_name}")
        
        # 记录历史
        if marked_details:
            self._save_deleted_history(marked_details, media_name)
    
    def _trigger_brush_check(self):
        """触发刷流插件的检查任务，让其立即处理待删除的种子"""
        for plugin_id in self.TARGET_PLUGINS:
            try:
                plugin = self._get_plugin_instance(plugin_id)
                if plugin and hasattr(plugin, 'check'):
                    logger.info(f"触发刷流插件检查: {plugin_id}")
                    plugin.check()
                    break
            except Exception as e:
                logger.debug(f"触发刷流插件检查失败 ({plugin_id}): {e}")
    
    def _get_plugin_instance(self, plugin_id: str):
        """获取插件实例"""
        try:
            from app.core.plugin import PluginManager
            plugin_manager = PluginManager()
            return plugin_manager.get_plugin(plugin_id)
        except ImportError:
            try:
                from app.plugins import PluginManager
                plugin_manager = PluginManager()
                return plugin_manager.get_plugin(plugin_id)
            except Exception as e:
                logger.debug(f"获取插件实例失败: {e}")
                return None
        except Exception as e:
            logger.debug(f"获取插件实例失败: {e}")
            return None
    
    def _save_removed_history(self, removed_details: List[Dict], keyword: str):
        """保存收藏移除历史"""
        history = self.get_data("removed_history") or []
        
        history.append({
            "keyword": keyword,
            "action": "favorite_remove",
            "time": time.time(),
            "time_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "removed_count": len(removed_details),
            "details": removed_details[:10]
        })
        
        # 保留最近200条
        if len(history) > 200:
            history = history[-200:]
        
        self.save_data("removed_history", history)
    
    def _save_deleted_history(self, marked_details: List[Dict], media_name: str):
        """保存删除标记历史"""
        history = self.get_data("deleted_history") or []
        
        history.append({
            "media_name": media_name,
            "action": "mark_for_deletion",
            "marked_count": len(marked_details),
            "details": marked_details[:10],
            "time": time.time(),
            "time_str": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        if len(history) > 200:
            history = history[-200:]
        
        self.save_data("deleted_history", history)
    
    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """注册远程命令"""
        return [
            {
                "cmd": "/media_sync_remove",
                "event": EventType.PluginAction,
                "desc": "手动从刷流移除种子",
                "category": "管理",
                "data": {"action": "remove"}
            },
            {
                "cmd": "/media_sync_mark",
                "event": EventType.PluginAction,
                "desc": "手动标记种子待删除",
                "category": "管理",
                "data": {"action": "mark"}
            },
            {
                "cmd": "/media_sync_history",
                "event": EventType.PluginAction,
                "desc": "查看操作历史",
                "category": "查询",
                "data": {"action": "history"}
            },
            {
                "cmd": "/media_sync_trigger",
                "event": EventType.PluginAction,
                "desc": "手动触发刷流检查",
                "category": "管理",
                "data": {"action": "trigger"}
            }
        ]
    
    @eventmanager.register(EventType.PluginAction)
    def handle_command(self, event: Event):
        """处理远程命令"""
        if not self._enabled:
            return
        
        action = event.event_data.get("action")
        keyword = event.event_data.get("keyword") or event.event_data.get("name")
        
        if action == "remove" and keyword:
            self.remove_from_brush_plugins(keyword)
            self.post_message("手动操作", f"已从刷流移除: {keyword}")
        
        elif action == "mark" and keyword:
            self.mark_torrents_for_deletion(keyword)
        
        elif action == "trigger":
            self._trigger_brush_check()
            self.post_message("手动操作", "已触发刷流插件检查")
        
        elif action == "history":
            self._send_history_report()
    
    def _send_history_report(self):
        """发送历史报告"""
        removed_history = self.get_data("removed_history") or []
        deleted_history = self.get_data("deleted_history") or []
        
        total_removed = sum(h.get("removed_count", 0) for h in removed_history)
        total_marked = sum(h.get("marked_count", 0) for h in deleted_history)
        
        lines = [
            f"📊 统计报告",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"📌 收藏移除: {len(removed_history)} 次，共 {total_removed} 个种子",
            f"🗑️ 删除标记: {len(deleted_history)} 次，共 {total_marked} 个种子",
            "",
            "📌 最近收藏移除："
        ]
        
        for item in removed_history[-5:]:
            lines.append(f"  · {item.get('time_str')} - 「{item.get('keyword')}」({item.get('removed_count')}个)")
        
        lines.append("")
        lines.append("🗑️ 最近删除标记：")
        
        for item in deleted_history[-5:]:
            lines.append(f"  · {item.get('time_str')} - 「{item.get('media_name')}」({item.get('marked_count')}个)")
        
        self.post_message("操作历史", "\n".join(lines))
    
    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """配置表单"""
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
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
                                "props": {"cols": 12, "md": 6},
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
                                            "type": "success",
                                            "variant": "tonal"
                                        },
                                        "content": [
                                            {
                                                "component": "div",
                                                "props": {"style": "font-weight: bold; margin-bottom: 8px;"},
                                                "text": "功能说明"
                                            },
                                            {
                                                "component": "div",
                                                "text": "1. 📌 收藏媒体 → 从刷流插件移除种子记录（种子文件保留）"
                                            },
                                            {
                                                "component": "div",
                                                "text": "2. 🗑️ 删除媒体 → 在刷流插件中标记种子待删除，由刷流插件执行实际删除"
                                            },
                                            {
                                                "component": "div",
                                                "props": {"style": "margin-top: 8px; color: #888;"},
                                                "text": "提示：删除操作会调用刷流插件的 check 方法，复用其所有删除规则（标签保护、动态删种等）"
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": False,
            "notify": True
        }
    
    def get_page(self) -> List[dict]:
        """详情页显示历史"""
        removed_history = self.get_data("removed_history") or []
        deleted_history = self.get_data("deleted_history") or []
        
        # 合并并排序
        all_records = []
        
        for item in removed_history:
            all_records.append({
                "time_str": item.get("time_str", ""),
                "type": "📌 收藏移除",
                "name": item.get("keyword", ""),
                "count": item.get("removed_count", 0)
            })
        
        for item in deleted_history:
            all_records.append({
                "time_str": item.get("time_str", ""),
                "type": "🗑️ 删除标记",
                "name": item.get("media_name", ""),
                "count": item.get("marked_count", 0)
            })
        
        all_records.sort(key=lambda x: x.get("time_str", ""), reverse=True)
        all_records = all_records[:30]
        
        if not all_records:
            return [{"component": "div", "text": "暂无操作记录", "props": {"class": "text-center"}}]
        
        rows = []
        for record in all_records:
            rows.append({
                "component": "tr",
                "content": [
                    {"component": "td", "text": record.get("time_str", "")},
                    {"component": "td", "text": record.get("type", "")},
                    {"component": "td", "text": record.get("name", "")[:50]},
                    {"component": "td", "text": str(record.get("count", 0))}
                ]
            })
        
        return [
            {
                "component": "VCard",
                "content": [
                    {
                        "component": "VCardTitle",
                        "text": "操作记录"
                    },
                    {
                        "component": "VTable",
                        "props": {"hover": True},
                        "content": [
                            {
                                "component": "thead",
                                "content": [
                                    {"component": "th", "text": "时间"},
                                    {"component": "th", "text": "操作类型"},
                                    {"component": "th", "text": "媒体/关键词"},
                                    {"component": "th", "text": "数量"}
                                ]
                            },
                            {"component": "tbody", "content": rows}
                        ]
                    }
                ]
            }
        ]
    
    def stop_service(self):
        """停止服务"""
        self._enabled = False
        logger.info("媒体同步保护插件已停止")
