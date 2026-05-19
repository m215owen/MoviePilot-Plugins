import datetime
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from threading import Lock
from typing import Any, List, Dict, Tuple, Optional

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
    _dirconf = {}
    _renameconf = {}
    _medias = {}
    _scanning = False

    # 统计数据
    _statistics = {
        "success_count": 0,      # 成功整理数量
        "failed_count": 0,       # 失败整理数量
        "success_folders": [],   # 成功整理的目录
        "failed_records": []     # 失败记录
    }

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

        if self._enabled or self._onlyonce:
            # 定时服务
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
                logger.info(f"定时扫描服务已启动，扫描间隔: {self._scan_interval} 秒")

            # 读取目录配置
            if self._monitor_confs:
                monitor_confs = self._monitor_confs.split("\n")
                for monitor_conf in monitor_confs:
                    if not monitor_conf or not monitor_conf.strip():
                        continue

                    parts = monitor_conf.split("#")
                    if len(parts) < 3:
                        logger.error(f"{monitor_conf} 格式错误，应为：监控方式#监控目录#目的目录#是否重命名")
                        continue

                    mode = parts[0].strip()
                    source_dir = parts[1].strip()
                    target_dir = parts[2].strip()
                    rename_conf = parts[3].strip() if len(parts) > 3 else "true"

                    self._dirconf[source_dir] = target_dir
                    self._renameconf[source_dir] = rename_conf

                    if self._enabled:
                        self._start_monitor(mode, source_dir)

            # 全量同步
            if self._onlyonce:
                logger.info("短剧整理服务启动，立即运行一次")
                self._scheduler.add_job(
                    func=self.scan_all_dirs,
                    trigger='date',
                    run_date=datetime.datetime.now(
                        pytz.timezone(settings.TZ)
                    ) + datetime.timedelta(seconds=3),
                    id="shortplayorganizer_sync"
                )
                self._onlyonce = False
                self.__update_config()

            # 启动任务
            if self._scheduler.get_jobs():
                self._scheduler.start()

    def _load_statistics(self):
        """加载统计数据"""
        stats = self.get_data("statistics")
        if stats:
            self._statistics = stats
        else:
            self._statistics = {
                "success_count": 0,
                "failed_count": 0,
                "success_folders": [],
                "failed_records": []
            }

    def _save_statistics(self):
        """保存统计数据"""
        # 只保留最近100条记录
        if len(self._statistics["success_folders"]) > 100:
            self._statistics["success_folders"] = self._statistics["success_folders"][-100:]
        if len(self._statistics["failed_records"]) > 100:
            self._statistics["failed_records"] = self._statistics["failed_records"][-100:]
        
        self.save_data("statistics", self._statistics)

    def _record_success(self, title: str, source_path: str, target_path: str):
        """记录成功整理"""
        self._statistics["success_count"] += 1
        self._statistics["success_folders"].append({
            "title": title,
            "source": source_path,
            "target": str(target_path),
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        self._save_statistics()

    def _record_failure(self, source_path: str, reason: str):
        """记录失败整理"""
        self._statistics["failed_count"] += 1
        self._statistics["failed_records"].append({
            "source": source_path,
            "reason": reason,
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        self._save_statistics()

    def _start_monitor(self, mode: str, source_dir: str):
        """启动目录监控"""
        try:
            if not os.path.exists(source_dir):
                logger.warning(f"监控目录不存在: {source_dir}")
                return

            if mode == "compatibility":
                observer = PollingObserver(timeout=10)
                logger.info(f"{source_dir} 使用兼容模式（轮询）")
            else:
                observer = Observer(timeout=10)
                logger.info(f"{source_dir} 使用实时监控模式")

            self._observer.append(observer)
            observer.schedule(
                FileMonitorHandler(source_dir, self),
                path=source_dir,
                recursive=True
            )
            observer.daemon = True
            observer.start()
            logger.info(f"{source_dir} 的目录监控服务启动")
        except Exception as e:
            err_msg = str(e)
            if "inotify" in err_msg and "reached" in err_msg:
                logger.warning(
                    f"目录监控服务启动出现异常：{err_msg}，请在宿主机上执行："
                    "echo fs.inotify.max_user_watches=524288 | sudo tee -a /etc/sysctl.conf && sudo sysctl -p"
                )
            else:
                logger.error(f"{source_dir} 启动目录监控失败：{err_msg}")

    def get_state(self) -> bool:
        """返回插件状态"""
        return self._enabled

    def get_api(self) -> List[Dict[str, Any]]:
        """注册API - 本插件不需要对外提供API接口"""
        return []

    def get_command(self) -> List[Dict[str, Any]]:
        """注册远程命令 - 本插件不需要远程命令"""
        return [
            {
                "cmd": "/shortplay_stats",
                "event": None,
                "desc": "查看短剧整理统计",
                "category": "管理",
                "data": {"action": "stats"}
            },
            {
                "cmd": "/shortplay_clear",
                "event": None,
                "desc": "清空整理统计",
                "category": "管理",
                "data": {"action": "clear"}
            }
        ]

    def scan_all_dirs(self):
        """定时扫描所有监控目录"""
        if self._scanning:
            return

        self._scanning = True
        try:
            logger.info("开始定时扫描短剧整理目录...")
            for mon_path in self._dirconf.keys():
                if not os.path.exists(mon_path):
                    continue
                self._scan_directory(mon_path)
            logger.info("定时扫描短剧整理目录完成")
        except Exception as e:
            logger.error(f"定时扫描失败: {e}")
        finally:
            self._scanning = False

    def _scan_directory(self, source_dir: str):
        """扫描目录中的所有媒体文件"""
        try:
            for root, dirs, files in os.walk(source_dir):
                # 过滤排除关键词
                if self._exclude_keywords:
                    skip = False
                    for keyword in self._exclude_keywords.split("\n"):
                        if keyword and keyword in root:
                            skip = True
                            break
                    if skip:
                        continue

                for file in files:
                    file_path = os.path.join(root, file)
                    if Path(file_path).suffix.lower() in settings.RMT_MEDIAEXT:
                        self.event_handler(
                            event=None,
                            source_dir=source_dir,
                            event_path=file_path
                        )
        except Exception as e:
            logger.error(f"扫描目录失败 {source_dir}: {e}")

    def event_handler(self, event, source_dir: str, event_path: str):
        """处理文件变化"""
        # 回收站及隐藏的文件不处理
        if (event_path.find("/@Recycle") != -1
                or event_path.find("/#recycle") != -1
                or event_path.find("/.") != -1
                or event_path.find("/@eaDir") != -1):
            return

        # 命中过滤关键字不处理
        if self._exclude_keywords:
            for keyword in self._exclude_keywords.split("\n"):
                if keyword and keyword in event_path:
                    return

        # 只处理媒体文件
        if Path(event_path).suffix.lower() not in settings.RMT_MEDIAEXT:
            return

        self._handle_file(event_path=event_path, source_dir=source_dir)

    def _handle_file(self, event_path: str, source_dir: str):
        """整理单个文件"""
        try:
            source_path = Path(event_path)
            dest_dir = self._dirconf.get(source_dir)

            if not dest_dir:
                error_msg = f"未找到监控目录 {source_dir} 对应的目的目录"
                logger.error(error_msg)
                self._record_failure(event_path, error_msg)
                return

            # 向上查找包含 tvshow.nfo 的目录
            source_folder = self._find_nfo_parent(source_path.parent)

            if not source_folder:
                error_msg = f"未找到包含 tvshow.nfo 的目录"
                logger.debug(f"{event_path}: {error_msg}")
                self._record_failure(event_path, error_msg)
                return

            nfo_path = source_folder / "tvshow.nfo"
            if not nfo_path.exists():
                error_msg = f"目录 {source_folder} 没有 tvshow.nfo"
                logger.debug(error_msg)
                self._record_failure(event_path, error_msg)
                return

            # 解析片名
            title = self._parse_title_from_nfo(nfo_path)
            if not title:
                error_msg = f"无法从 {nfo_path} 解析片名"
                logger.warning(error_msg)
                self._record_failure(event_path, error_msg)
                return

            title = self._sanitize_filename(title)
            target_folder = Path(dest_dir) / title
            rename_conf = self._renameconf.get(source_dir, "true")

            # 处理视频文件
            if source_path.suffix.lower() in settings.RMT_MEDIAEXT:
                target_path = self._organize_video_file(
                    source_path=source_path,
                    target_folder=target_folder,
                    rename_conf=rename_conf
                )
                if target_path:
                    self._record_success(title, str(source_path), target_path)

            # 复制元数据文件
            self._copy_metadata_files(
                source_folder=source_folder,
                target_folder=target_folder
            )

            if self._notify:
                self._add_to_notify_queue(title, str(source_path))

        except Exception as e:
            error_msg = f"整理文件失败: {str(e)}"
            logger.error(f"{event_path}: {error_msg}")
            self._record_failure(event_path, error_msg)

    def _find_nfo_parent(self, start_path: Path, max_depth: int = 3) -> Optional[Path]:
        """向上查找包含 tvshow.nfo 的目录"""
        current = start_path
        for _ in range(max_depth):
            if (current / "tvshow.nfo").exists():
                return current
            if current.parent == current:
                break
            current = current.parent
        return None

    def _parse_title_from_nfo(self, nfo_path: Path) -> Optional[str]:
        """从 nfo 文件中解析片名"""
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
            logger.error(f"解析 NFO 文件失败 {nfo_path}: {str(e)}")

        return None

    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名中的非法字符"""
        illegal_chars = r'[\\/*?:"<>|]'
        cleaned = re.sub(illegal_chars, '', filename)
        return cleaned.strip('. ')

    def _organize_video_file(self, source_path: Path, target_folder: Path, rename_conf: str) -> Optional[Path]:
        """整理视频文件，返回目标路径"""
        try:
            target_folder.mkdir(parents=True, exist_ok=True)

            episode_num = self._extract_episode_number(source_path.name)

            if rename_conf == "true" and episode_num is not None:
                season_num = "01"
                episode_str = f"E0{episode_num}" if episode_num < 10 else f"E{episode_num}"
                new_name = f"S{season_num}{episode_str}{source_path.suffix}"
                target_path = target_folder / new_name
            else:
                target_path = target_folder / source_path.name

            if target_path.exists():
                logger.debug(f"目标文件已存在: {target_path}")
                return target_path

            retcode = self._transfer_file(source_path, target_path)

            if retcode == 0:
                logger.info(f"文件整理完成: {source_path} -> {target_path}")
                return target_path
            else:
                logger.error(f"文件整理失败: {source_path}")
                return None

        except Exception as e:
            logger.error(f"整理视频文件失败: {str(e)}")
            return None

    def _extract_episode_number(self, filename: str) -> Optional[int]:
        """从文件名中提取集数"""
        match = re.search(r'[sS](\d+)[eE](\d+)', filename)
        if match:
            return int(match.group(2))

        match = re.search(r'[eE](\d+)', filename)
        if match:
            return int(match.group(1))

        match = re.search(r'第(\d+)集', filename)
        if match:
            return int(match.group(1))

        return None

    def _copy_metadata_files(self, source_folder: Path, target_folder: Path):
        """复制 nfo 和海报文件"""
        target_folder.mkdir(parents=True, exist_ok=True)

        # 复制 tvshow.nfo
        source_nfo = source_folder / "tvshow.nfo"
        target_nfo = target_folder / "tvshow.nfo"
        if source_nfo.exists() and not target_nfo.exists():
            self._transfer_file(source_nfo, target_nfo)

        # 复制海报
        target_poster = target_folder / "poster.jpg"
        for poster_name in ["poster.jpg", "folder.jpg", "cover.jpg"]:
            source_img = source_folder / poster_name
            if source_img.exists() and not target_poster.exists():
                self._transfer_file(source_img, target_poster)
                break

    def _transfer_file(self, source: Path, target: Path) -> int:
        """转移文件"""
        with lock:
            if self._transfer_type == "link":
                retcode, retmsg = SystemUtils.link(source, target)
            elif self._transfer_type == "softlink":
                retcode, retmsg = SystemUtils.softlink(source, target)
            elif self._transfer_type == "move":
                retcode, retmsg = SystemUtils.move(source, target)
            else:
                retcode, retmsg = SystemUtils.copy(source, target)

            if retcode != 0:
                logger.error(retmsg)
            return retcode

    def _add_to_notify_queue(self, title: str, file_path: str):
        """添加到通知队列"""
        media_list = self._medias.get(title, {})
        if media_list:
            files = media_list.get("files", [])
            if file_path not in files:
                files.append(file_path)
            self._medias[title] = {
                "files": files,
                "time": datetime.datetime.now()
            }
        else:
            self._medias[title] = {
                "files": [file_path],
                "time": datetime.datetime.now()
            }

    def send_msg(self):
        """发送通知消息"""
        if not self._notify or not self._medias:
            return

        for title in list(self._medias.keys()):
            media_list = self._medias.get(title)
            if not media_list:
                continue

            files = media_list.get("files", [])
            last_time = media_list.get("time")

            if not files or not last_time:
                continue

            if (datetime.datetime.now() - last_time).total_seconds() > self._interval:
                self.post_message(
                    mtype=NotificationType.Organize,
                    title=f"{title} 已入库",
                    text=f"共 {len(files)} 个文件\n转移方式: {self._transfer_type}"
                )
                del self._medias[title]

    def __update_config(self):
        """更新配置"""
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
        """返回配置表单"""
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
                                "props": {"cols": 12, "md": 3},
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
                                "props": {"cols": 12, "md": 3},
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
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "transfer_type",
                                            "label": "转移方式",
                                            "items": [
                                                {"title": "移动", "value": "move"},
                                                {"title": "复制", "value": "copy"},
                                                {"title": "硬链接", "value": "link"},
                                                {"title": "软链接", "value": "softlink"}
                                            ]
                                        }
                                    }
                                ]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "interval",
                                            "label": "入库消息延迟（秒）",
                                            "placeholder": "10"
                                        }
                                    }
                                ]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "scan_interval",
                                            "label": "定时扫描间隔（秒）",
                                            "placeholder": "60"
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
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "scan_enabled",
                                            "label": "启用定时扫描",
                                            "hint": "关闭后仅依赖实时监控"
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
                                        "component": "VTextarea",
                                        "props": {
                                            "model": "monitor_confs",
                                            "label": "监控目录配置",
                                            "rows": 4,
                                            "placeholder": "监控方式#监控目录#目的目录#是否重命名（每行一条）\nauto#/downloads/短剧#/media/短剧#true\ncompatibility#/mnt/smb/share#/media/短剧#false"
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
                                        "component": "VTextarea",
                                        "props": {
                                            "model": "exclude_keywords",
                                            "label": "排除关键词",
                                            "rows": 2,
                                            "placeholder": "每行一个关键词"
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
                                            "type": "info",
                                            "variant": "tonal"
                                        },
                                        "content": [
                                            {
                                                "component": "div",
                                                "props": {"style": "font-weight: bold; margin-bottom: 8px;"},
                                                "text": "配置说明"
                                            },
                                            {
                                                "component": "div",
                                                "text": "1. 监控方式：auto（实时）或 compatibility（兼容/轮询）"
                                            },
                                            {
                                                "component": "div",
                                                "text": "2. 格式示例：auto#/downloads/短剧#/media/短剧#true"
                                            },
                                            {
                                                "component": "div",
                                                "text": "3. 定时扫描作为监控补充，可单独关闭"
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
            "onlyonce": False,
            "monitor_confs": "",
            "transfer_type": "link",
            "exclude_keywords": "",
            "notify": False,
            "interval": 10,
            "scan_interval": 60,
            "scan_enabled": True
        }

    def get_page(self) -> List[dict]:
        """返回详情页，包含统计图表和记录"""
        
        # 计算成功率
        total = self._statistics["success_count"] + self._statistics["failed_count"]
        success_rate = round(self._statistics["success_count"] / total * 100, 1) if total > 0 else 0
        
        # 构建成功目录表格行
        success_rows = []
        for item in self._statistics["success_folders"][-20:]:
            success_rows.append({
                "component": "tr",
                "content": [
                    {"component": "td", "text": item.get("title", "")[:30]},
                    {"component": "td", "text": item.get("source", "")[:50]},
                    {"component": "td", "text": item.get("time", "")}
                ]
            })
        
        # 构建失败记录表格行
        failed_rows = []
        for item in self._statistics["failed_records"][-20:]:
            failed_rows.append({
                "component": "tr",
                "content": [
                    {"component": "td", "text": item.get("source", "")[:50]},
                    {"component": "td", "text": item.get("reason", "")[:30]},
                    {"component": "td", "text": item.get("time", "")}
                ]
            })
        
        return [
            # 统计卡片
            {
                "component": "VRow",
                "content": [
                    # 成功数量卡片
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VCard",
                                "props": {"variant": "tonal", "color": "success"},
                                "content": [
                                    {
                                        "component": "VCardText",
                                        "props": {"class": "text-center"},
                                        "content": [
                                            {
                                                "component": "div",
                                                "props": {"class": "text-h4"},
                                                "text": str(self._statistics["success_count"])
                                            },
                                            {
                                                "component": "div",
                                                "text": "成功整理"
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    },
                    # 失败数量卡片
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VCard",
                                "props": {"variant": "tonal", "color": "error"},
                                "content": [
                                    {
                                        "component": "VCardText",
                                        "props": {"class": "text-center"},
                                        "content": [
                                            {
                                                "component": "div",
                                                "props": {"class": "text-h4"},
                                                "text": str(self._statistics["failed_count"])
                                            },
                                            {
                                                "component": "div",
                                                "text": "整理失败"
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    },
                    # 成功率卡片
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VCard",
                                "props": {"variant": "tonal", "color": "info"},
                                "content": [
                                    {
                                        "component": "VCardText",
                                        "props": {"class": "text-center"},
                                        "content": [
                                            {
                                                "component": "div",
                                                "props": {"class": "text-h4"},
                                                "text": f"{success_rate}%"
                                            },
                                            {
                                                "component": "div",
                                                "text": "成功率"
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
            # 成功整理记录表格
            {
                "component": "VCard",
                "props": {"class": "mt-4"},
                "content": [
                    {
                        "component": "VCardTitle",
                        "text": "📁 最近成功整理记录"
                    },
                    {
                        "component": "VDivider"
                    },
                    {
                        "component": "VCardText",
                        "props": {"class": "pa-0"},
                        "content": [
                            {
                                "component": "VTable",
                                "props": {"hover": True},
                                "content": [
                                    {
                                        "component": "thead",
                                        "content": [
                                            {
                                                "component": "th",
                                                "text": "片名"
                                            },
                                            {
                                                "component": "th",
                                                "text": "源文件"
                                            },
                                            {
                                                "component": "th",
                                                "text": "整理时间"
                                            }
                                        ]
                                    },
                                    {
                                        "component": "tbody",
                                        "content": success_rows if success_rows else [
                                            {
                                                "component": "tr",
                                                "content": [
                                                    {
                                                        "component": "td",
                                                        "props": {"colspan": 3, "class": "text-center"},
                                                        "text": "暂无成功记录"
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
            },
            # 失败记录表格
            {
                "component": "VCard",
                "props": {"class": "mt-4"},
                "content": [
                    {
                        "component": "VCardTitle",
                        "text": "❌ 最近失败记录"
                    },
                    {
                        "component": "VDivider"
                    },
                    {
                        "component": "VCardText",
                        "props": {"class": "pa-0"},
                        "content": [
                            {
                                "component": "VTable",
                                "props": {"hover": True},
                                "content": [
                                    {
                                        "component": "thead",
                                        "content": [
                                            {
                                                "component": "th",
                                                "text": "源文件"
                                            },
                                            {
                                                "component": "th",
                                                "text": "失败原因"
                                            },
                                            {
                                                "component": "th",
                                                "text": "时间"
                                            }
                                        ]
                                    },
                                    {
                                        "component": "tbody",
                                        "content": failed_rows if failed_rows else [
                                            {
                                                "component": "tr",
                                                "content": [
                                                    {
                                                        "component": "td",
                                                        "props": {"colspan": 3, "class": "text-center"},
                                                        "text": "暂无失败记录"
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

    def stop_service(self):
        """停止服务"""
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown()
                self._scheduler = None
        except Exception as e:
            logger.error(f"退出插件失败：{str(e)}")

        if self._observer:
            for observer in self._observer:
                try:
                    observer.stop()
                    observer.join()
                except Exception as e:
                    logger.debug(str(e))
            self._observer = []
