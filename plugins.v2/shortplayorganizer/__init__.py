import datetime
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from threading import Lock
from typing import Any, List, Dict, Tuple, Optional, Set

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

from app.core.config import settings
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import NotificationType
from app.utils.system import SystemUtils

lock = Lock()


class FileMonitorHandler(FileSystemEventHandler):
    """目录监控响应类"""

    def __init__(self, watching_path: str, file_change: Any, **kwargs):
        super(FileMonitorHandler, self).__init__(**kwargs)
        self._watch_path = watching_path
        self.file_change = file_change

    def on_created(self, event):
        if not event.is_directory:
            self.file_change.event_handler(
                event=event,
                source_dir=self._watch_path,
                event_path=event.src_path
            )

    def on_moved(self, event):
        if not event.is_directory:
            self.file_change.event_handler(
                event=event,
                source_dir=self._watch_path,
                event_path=event.dest_path
            )


class ShortPlayOrganizer(_PluginBase):
    """短剧整理器插件"""

    # 插件元数据
    plugin_name = "短剧整理器"
    plugin_desc = "读取tvshow.nfo中的片名，按Emby标准格式整理短剧文件"
    plugin_icon = "Amule_B.png"
    plugin_version = "1.0.0"
    plugin_author = "AI"
    author_url = "https://github.com/thsrite"
    plugin_config_prefix = "shortplayorganizer_"
    plugin_order = 26
    auth_level = 1

    # 私有属性
    _enabled = False
    _onlyonce = False
    _monitor_confs = ""
    _transfer_type = "link"
    _exclude_keywords = ""
    _observer = []
    _notify = False
    _interval = 10
    _scan_interval = 60
    _scan_enabled = True
    _dirconf = {}           # 源目录 -> 目的目录
    _renameconf = {}        # 源目录 -> 是否重命名
    _medias = {}            # 通知队列
    _scanning = False

    # 统计和缓存
    _statistics = {
        "success_count": 0,
        "success_list": [],
        "skip_folder_list": []
    }
    _success_cache: Set[str] = set()       # 已成功处理的文件
    _skip_folder_cache: Set[str] = set()   # 跳过的文件夹（无nfo）

    # 定时器
    _scheduler: Optional[BackgroundScheduler] = None

    def init_plugin(self, config: dict = None):
        """初始化插件"""
        if config:
            self._enabled = config.get("enabled", False)
            self._onlyonce = config.get("onlyonce", False)
            self._monitor_confs = config.get("monitor_confs", "")
            self._transfer_type = config.get("transfer_type", "link")
            self._exclude_keywords = config.get("exclude_keywords", "")
            self._notify = config.get("notify", False)
            self._interval = config.get("interval", 10)
            self._scan_interval = config.get("scan_interval", 60)
            self._scan_enabled = config.get("scan_enabled", True)

        # 加载统计数据
        self._load_statistics()

        # 清空配置
        self._dirconf = {}
        self._renameconf = {}

        # 停止现有任务
        self.stop_service()

        if not (self._enabled or self._onlyonce):
            return

        # 解析监控目录配置
        self._parse_monitor_configs()

        # 启动定时服务
        self._scheduler = BackgroundScheduler(timezone=settings.TZ)

        # 入库消息定时发送
        if self._notify:
            self._scheduler.add_job(
                func=self.send_msg,
                trigger=IntervalTrigger(seconds=15),
                id="shortplayorganizer_notify"
            )

        # 定时扫描任务
        if self._enabled and self._scan_enabled and self._scan_interval > 0:
            self._scheduler.add_job(
                func=self.scan_all_dirs,
                trigger=IntervalTrigger(seconds=self._scan_interval),
                id="shortplayorganizer_scan"
            )
            logger.info(f"定时扫描已启动，间隔: {self._scan_interval} 秒")

        # 全量同步
        if self._onlyonce:
            logger.info("立即运行一次")
            self._scheduler.add_job(
                func=self.scan_all_dirs,
                trigger='date',
                run_date=datetime.datetime.now(pytz.timezone(settings.TZ)) + datetime.timedelta(seconds=3),
                id="shortplayorganizer_sync"
            )
            self._onlyonce = False
            self.__update_config()

        # 启动任务
        if self._scheduler.get_jobs():
            self._scheduler.start()

    def _parse_monitor_configs(self):
        """解析监控目录配置"""
        if not self._monitor_confs:
            logger.warning("未配置监控目录")
            return

        for line in self._monitor_confs.split("\n"):
            line = line.strip()
            if not line:
                continue

            parts = line.split("#")
            if len(parts) < 3:
                logger.error(f"配置格式错误: {line}，应为: 监控方式#源目录#目的目录#是否重命名")
                continue

            mode = parts[0].strip()
            source_dir = parts[1].strip()
            target_dir = parts[2].strip()
            rename = parts[3].strip() if len(parts) > 3 else "true"

            # 标准化路径
            source_dir = os.path.normpath(source_dir)
            target_dir = os.path.normpath(target_dir)

            self._dirconf[source_dir] = target_dir
            self._renameconf[source_dir] = rename

            # 启动目录监控
            if self._enabled:
                self._start_monitor(mode, source_dir)

    def _start_monitor(self, mode: str, source_dir: str):
        """启动目录监控"""
        if not os.path.exists(source_dir):
            logger.warning(f"监控目录不存在: {source_dir}")
            return

        try:
            if mode == "compatibility":
                observer = PollingObserver(timeout=10)
                logger.info(f"{source_dir} 使用兼容模式")
            else:
                observer = Observer(timeout=10)
                logger.info(f"{source_dir} 使用实时监控")

            self._observer.append(observer)
            observer.schedule(
                FileMonitorHandler(source_dir, self),
                path=source_dir,
                recursive=True
            )
            observer.daemon = True
            observer.start()
            logger.info(f"{source_dir} 监控已启动")
        except Exception as e:
            logger.error(f"{source_dir} 监控启动失败: {e}")

    def _load_statistics(self):
        """加载统计数据"""
        data = self.get_data("statistics")
        if data:
            self._statistics = data
            self._success_cache = set(data.get("success_list", []))
            self._skip_folder_cache = set(data.get("skip_folder_list", []))

    def _save_statistics(self):
        """保存统计数据"""
        self._statistics["success_count"] = len(self._success_cache)
        self._statistics["success_list"] = list(self._success_cache)[-200:]
        self._statistics["skip_folder_list"] = list(self._skip_folder_cache)[-200:]
        self.save_data("statistics", self._statistics)

    def _record_success(self, file_path: str, title: str, target_path: str):
        """记录成功"""
        self._success_cache.add(file_path)
        self._save_statistics()
        logger.info(f"整理成功: {file_path} -> {title}")

    def _is_skipped_folder(self, folder_path: str) -> bool:
        """检查文件夹是否被跳过（无nfo）"""
        return folder_path in self._skip_folder_cache

    def _mark_skip_folder(self, folder_path: str):
        """标记文件夹为跳过（无nfo）"""
        if folder_path not in self._skip_folder_cache:
            self._skip_folder_cache.add(folder_path)
            self._save_statistics()
            logger.info(f"跳过无NFO文件夹: {folder_path}")

    def _has_nfo_in_folder(self, folder_path: str) -> bool:
        """检查文件夹是否包含 tvshow.nfo（仅当前目录，不向上查找）"""
        return (Path(folder_path) / "tvshow.nfo").exists()

    def _get_title_from_nfo(self, folder_path: str) -> Optional[str]:
        """从当前目录的nfo文件获取片名"""
        nfo_path = Path(folder_path) / "tvshow.nfo"
        if not nfo_path.exists():
            return None
        try:
            tree = ET.parse(nfo_path)
            root = tree.getroot()
            title_elem = root.find("title")
            if title_elem is not None and title_elem.text:
                return title_elem.text.strip()
            original_elem = root.find("originaltitle")
            if original_elem is not None and original_elem.text:
                return original_elem.text.strip()
        except Exception as e:
            logger.error(f"解析NFO失败 {nfo_path}: {e}")
        return None

    def _sanitize_filename(self, filename: str) -> str:
        """清理非法字符"""
        return re.sub(r'[\\/*?:"<>|]', '', filename).strip('. ')

    def _extract_episode(self, filename: str) -> Optional[int]:
        """提取集数"""
        match = re.search(r'[sS]\d+[eE](\d+)', filename)
        if match:
            return int(match.group(1))
        match = re.search(r'[eE](\d+)', filename)
        if match:
            return int(match.group(1))
        match = re.search(r'第(\d+)集', filename)
        if match:
            return int(match.group(1))
        return None

    def _transfer_file(self, source: Path, target: Path) -> bool:
        """转移文件"""
        with lock:
            if self._transfer_type == "link":
                retcode, _ = SystemUtils.link(source, target)
            elif self._transfer_type == "softlink":
                retcode, _ = SystemUtils.softlink(source, target)
            elif self._transfer_type == "move":
                retcode, _ = SystemUtils.move(source, target)
            else:
                retcode, _ = SystemUtils.copy(source, target)
            return retcode == 0

    def _organize_video(self, source_path: Path, target_folder: Path, rename: str) -> Optional[Path]:
        """整理视频文件"""
        target_folder.mkdir(parents=True, exist_ok=True)

        episode = self._extract_episode(source_path.name)

        if rename == "true" and episode is not None:
            episode_str = f"E0{episode}" if episode < 10 else f"E{episode}"
            new_name = f"S01{episode_str}{source_path.suffix}"
            target_path = target_folder / new_name
        else:
            target_path = target_folder / source_path.name

        if target_path.exists():
            return target_path

        if self._transfer_file(source_path, target_path):
            logger.info(f"整理完成: {source_path} -> {target_path}")
            return target_path
        return None

    def _copy_metadata(self, source_folder: Path, target_folder: Path):
        """复制元数据"""
        target_folder.mkdir(parents=True, exist_ok=True)

        # 复制 nfo
        nfo_path = source_folder / "tvshow.nfo"
        if nfo_path.exists() and not (target_folder / "tvshow.nfo").exists():
            self._transfer_file(nfo_path, target_folder / "tvshow.nfo")

        # 复制海报
        for poster in ["poster.jpg", "folder.jpg", "cover.jpg"]:
            poster_path = source_folder / poster
            if poster_path.exists() and not (target_folder / "poster.jpg").exists():
                self._transfer_file(poster_path, target_folder / "poster.jpg")
                break

    def _is_valid_folder(self, folder_path: str, source_dir: str) -> bool:
        """检查是否为有效的剧集文件夹（监控目录的下一级）"""
        # 获取相对路径
        rel_path = os.path.relpath(folder_path, source_dir)
        # 如果相对路径是 "." 说明就是监控目录本身，跳过
        # 如果相对路径包含 "/"，说明是更深层目录，也跳过（只处理下一级）
        if rel_path == "." or "/" in rel_path or "\\" in rel_path:
            return False
        return True

    def _process_file(self, file_path: str, source_dir: str):
        """处理单个文件"""
        # 检查是否已成功
        if file_path in self._success_cache:
            logger.debug(f"已成功过，跳过: {file_path}")
            return

        source_path = Path(file_path)
        folder_path = str(source_path.parent)

        # 检查是否为有效的剧集文件夹（监控目录的下一级）
        if not self._is_valid_folder(folder_path, source_dir):
            logger.debug(f"不是有效剧集文件夹，跳过: {folder_path}")
            return

        # 检查文件夹是否被跳过
        if self._is_skipped_folder(folder_path):
            logger.debug(f"文件夹已跳过，跳过文件: {file_path}")
            return

        # 检查是否有 nfo（仅当前目录）
        if not self._has_nfo_in_folder(folder_path):
            self._mark_skip_folder(folder_path)
            return

        # 获取目的目录
        dest_dir = self._dirconf.get(source_dir)
        if not dest_dir:
            logger.error(f"未找到目的目录: {source_dir}")
            return

        # 获取片名
        title = self._get_title_from_nfo(folder_path)
        if not title:
            logger.warning(f"无法解析片名: {folder_path}")
            return

        title = self._sanitize_filename(title)
        target_folder = Path(dest_dir) / title
        rename = self._renameconf.get(source_dir, "true")

        # 整理视频
        target_path = self._organize_video(source_path, target_folder, rename)
        if target_path:
            self._record_success(file_path, title, str(target_path))
            # 复制元数据（仅第一次）
            self._copy_metadata(Path(folder_path), target_folder)

            # 通知队列
            if self._notify:
                self._add_to_notify(title, file_path)

    def _add_to_notify(self, title: str, file_path: str):
        """添加到通知队列"""
        data = self._medias.get(title, {})
        files = data.get("files", [])
        if file_path not in files:
            files.append(file_path)
        self._medias[title] = {"files": files, "time": datetime.datetime.now()}

    def get_state(self) -> bool:
        return self._enabled

    def get_api(self) -> List[Dict[str, Any]]:
        return []

    def get_command(self) -> List[Dict[str, Any]]:
        return [
            {"cmd": "/shortplay_stats", "event": None, "desc": "查看统计", "category": "管理", "data": {"action": "stats"}},
            {"cmd": "/shortplay_clear", "event": None, "desc": "清空统计", "category": "管理", "data": {"action": "clear"}}
        ]

    def scan_all_dirs(self):
        """扫描所有监控目录"""
        if self._scanning:
            return

        self._scanning = True
        try:
            logger.info("开始扫描...")
            for source_dir, dest_dir in self._dirconf.items():
                if not os.path.exists(source_dir):
                    continue

                # 只扫描监控目录的下一级文件夹
                for item in os.listdir(source_dir):
                    folder_path = os.path.join(source_dir, item)
                    if not os.path.isdir(folder_path):
                        continue

                    # 跳过已标记的文件夹
                    if self._is_skipped_folder(folder_path):
                        continue

                    # 检查是否有 nfo
                    if not self._has_nfo_in_folder(folder_path):
                        self._mark_skip_folder(folder_path)
                        continue

                    # 扫描文件夹内的视频文件
                    for file in os.listdir(folder_path):
                        file_path = os.path.join(folder_path, file)
                        if Path(file_path).suffix.lower() in settings.RMT_MEDIAEXT:
                            if file_path in self._success_cache:
                                continue
                            self._process_file(file_path, source_dir)

            logger.info("扫描完成")
        except Exception as e:
            logger.error(f"扫描失败: {e}")
        finally:
            self._scanning = False

    def event_handler(self, event, source_dir: str, event_path: str):
        """处理文件变化事件"""
        # 过滤
        if any(x in event_path for x in ["/@Recycle", "/#recycle", "/.", "/@eaDir"]):
            return
        if self._exclude_keywords:
            for kw in self._exclude_keywords.split("\n"):
                if kw and kw in event_path:
                    return
        if Path(event_path).suffix.lower() not in settings.RMT_MEDIAEXT:
            return

        logger.debug(f"检测到文件: {event_path}")
        self._process_file(event_path, source_dir)

    def send_msg(self):
        """发送通知"""
        if not self._notify or not self._medias:
            return

        for title, data in list(self._medias.items()):
            if (datetime.datetime.now() - data["time"]).total_seconds() > self._interval:
                self.post_message(
                    mtype=NotificationType.Organize,
                    title=f"{title} 已入库",
                    text=f"共 {len(data['files'])} 个文件\n转移方式: {self._transfer_type}"
                )
                del self._medias[title]

    def __update_config(self):
        self.update_config({
            "enabled": self._enabled,
            "onlyonce": False,
            "monitor_confs": self._monitor_confs,
            "transfer_type": self._transfer_type,
            "exclude_keywords": self._exclude_keywords,
            "notify": self._notify,
            "interval": self._interval,
            "scan_interval": self._scan_interval,
            "scan_enabled": self._scan_enabled
        })

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [{"component": "VSwitch", "props": {"model": "enabled", "label": "启用插件"}}]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [{"component": "VSwitch", "props": {"model": "onlyonce", "label": "立即运行一次"}}]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [{"component": "VSwitch", "props": {"model": "notify", "label": "发送通知"}}]
                            }
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VSelect", "props": {"model": "transfer_type", "label": "转移方式", "items": [
                                    {"title": "移动", "value": "move"}, {"title": "复制", "value": "copy"},
                                    {"title": "硬链接", "value": "link"}, {"title": "软链接", "value": "softlink"}
                                ]}}]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VTextField", "props": {"model": "interval", "label": "通知延迟（秒）", "placeholder": "10"}}]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [{"component": "VTextField", "props": {"model": "scan_interval", "label": "扫描间隔（秒）", "placeholder": "60"}}]
                            }
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [{"component": "VSwitch", "props": {"model": "scan_enabled", "label": "启用定时扫描"}}]
                            }
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [{"component": "VTextarea", "props": {"model": "monitor_confs", "label": "监控目录", "rows": 4, "placeholder": "auto#/源目录#/目的目录#true\n示例: auto#/vol00/.../download/短剧#/media/短剧#true"}}]
                            }
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [{"component": "VTextarea", "props": {"model": "exclude_keywords", "label": "排除关键词", "rows": 2, "placeholder": "每行一个关键词"}}]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": False, "onlyonce": False, "monitor_confs": "", "transfer_type": "link",
            "exclude_keywords": "", "notify": False, "interval": 10, "scan_interval": 60, "scan_enabled": True
        }

    def get_page(self) -> List[dict]:
        total = len(self._success_cache) + len(self._skip_folder_cache)
        success_rate = round(len(self._success_cache) / total * 100, 1) if total > 0 else 0

        success_rows = []
        for path in list(self._success_cache)[-20:]:
            success_rows.append({"component": "tr", "content": [
                {"component": "td", "text": Path(path).name[:50]},
                {"component": "td", "text": path[:60]},
                {"component": "td", "text": "成功"}
            ]})

        skip_rows = []
        for folder in list(self._skip_folder_cache)[-20:]:
            skip_rows.append({"component": "tr", "content": [
                {"component": "td", "text": folder[:60]},
                {"component": "td", "text": "无 tvshow.nfo"},
                {"component": "td", "text": "跳过"}
            ]})

        return [
            {
                "component": "VRow",
                "content": [
                    {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [{"component": "VCard", "props": {"variant": "tonal", "color": "success"}, "content": [{"component": "VCardText", "props": {"class": "text-center"}, "content": [{"component": "div", "props": {"class": "text-h4"}, "text": str(len(self._success_cache))}, {"component": "div", "text": "成功整理"}]}]}]},
                    {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [{"component": "VCard", "props": {"variant": "tonal", "color": "error"}, "content": [{"component": "VCardText", "props": {"class": "text-center"}, "content": [{"component": "div", "props": {"class": "text-h4"}, "text": str(len(self._skip_folder_cache))}, {"component": "div", "text": "跳过文件夹"}]}]}]},
                    {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [{"component": "VCard", "props": {"variant": "tonal", "color": "info"}, "content": [{"component": "VCardText", "props": {"class": "text-center"}, "content": [{"component": "div", "props": {"class": "text-h4"}, "text": f"{success_rate}%"}, {"component": "div", "text": "成功率"}]}]}]}
                ]
            },
            {
                "component": "VCard", "props": {"class": "mt-4"}, "content": [
                    {"component": "VCardTitle", "text": "📁 成功记录"},
                    {"component": "VCardText", "props": {"class": "pa-0"}, "content": [{"component": "VTable", "props": {"hover": True}, "content": [
                        {"component": "thead", "content": [{"component": "th", "text": "文件名"}, {"component": "th", "text": "路径"}, {"component": "th", "text": "状态"}]},
                        {"component": "tbody", "content": success_rows if success_rows else [{"component": "tr", "content": [{"component": "td", "props": {"colspan": 3, "class": "text-center"}, "text": "暂无"}]}]}
                    ]}]}
                ]
            },
            {
                "component": "VCard", "props": {"class": "mt-4"}, "content": [
                    {"component": "VCardTitle", "text": "⏭️ 跳过文件夹"},
                    {"component": "VCardText", "props": {"class": "pa-0"}, "content": [{"component": "VTable", "props": {"hover": True}, "content": [
                        {"component": "thead", "content": [{"component": "th", "text": "文件夹"}, {"component": "th", "text": "原因"}, {"component": "th", "text": "状态"}]},
                        {"component": "tbody", "content": skip_rows if skip_rows else [{"component": "tr", "content": [{"component": "td", "props": {"colspan": 3, "class": "text-center"}, "text": "暂无"}]}]}
                    ]}]}
                ]
            }
        ]

    def stop_service(self):
        """停止服务"""
        if self._scheduler:
            self._scheduler.remove_all_jobs()
            if self._scheduler.running:
                self._scheduler.shutdown()
            self._scheduler = None

        for observer in self._observer:
            try:
                observer.stop()
                observer.join()
            except Exception:
                pass
        self._observer = []
