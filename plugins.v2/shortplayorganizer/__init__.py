import datetime
import os
import re
import shutil
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
    _dirconf = {}
    _renameconf = {}
    _medias = {}
    _scanning = False

    # 定时器
    _scheduler: Optional[BackgroundScheduler] = None

    def init_plugin(self, config: dict = None):
        """初始化插件"""
        logger.info(f"短剧整理器初始化开始")
        
        if config:
            self._enabled = config.get("enabled", False)
            self._onlyonce = config.get("onlyonce", False)
            self._monitor_confs = config.get("monitor_confs", "")
            self._transfer_type = config.get("transfer_type", "link")
            self._exclude_keywords = config.get("exclude_keywords", "")
            self._notify = config.get("notify", False)
            
            # 类型转换：防止配置存储为字符串
            interval = config.get("interval")
            if interval is not None:
                try:
                    self._interval = int(interval)
                except (ValueError, TypeError):
                    self._interval = 10
            else:
                self._interval = 10
                
            scan_interval = config.get("scan_interval")
            if scan_interval is not None:
                try:
                    self._scan_interval = int(scan_interval)
                except (ValueError, TypeError):
                    self._scan_interval = 60
            else:
                self._scan_interval = 60
        else:
            # 默认值
            self._enabled = False
            self._onlyonce = False
            self._monitor_confs = ""
            self._transfer_type = "link"
            self._exclude_keywords = ""
            self._notify = False
            self._interval = 10
            self._scan_interval = 60
        
        logger.info(f"短剧整理器配置: enabled={self._enabled}, scan_interval={self._scan_interval}")

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
            if self._enabled and self._scan_interval > 0:
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

                    # 检查媒体库目录是不是下载目录的子目录
                    if self._enabled:
                        try:
                            if target_dir and Path(target_dir).is_relative_to(Path(source_dir)):
                                logger.warning(f"{target_dir} 是下载目录 {source_dir} 的子目录，无法监控")
                                self.systemmessage.put(f"{target_dir} 是下载目录 {source_dir} 的子目录，无法监控")
                                continue
                        except Exception as e:
                            logger.debug(str(e))

                        try:
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
                            self.systemmessage.put(f"{source_dir} 启动目录监控失败：{err_msg}")

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
                self._scheduler.print_jobs()
                self._scheduler.start()
        else:
            logger.info("短剧整理器插件未启用")

    def get_state(self) -> bool:
        """返回插件状态"""
        return self._enabled

    def scan_all_dirs(self):
        """定时扫描所有监控目录"""
        if self._scanning:
            logger.debug("上一轮扫描尚未完成，跳过本次扫描")
            return

        self._scanning = True
        try:
            logger.info("开始定时扫描短剧整理目录...")
            for mon_path in self._dirconf.keys():
                if not os.path.exists(mon_path):
                    logger.warning(f"监控目录不存在: {mon_path}")
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
            logger.debug(f"{event_path} 是回收站或隐藏的文件，跳过处理")
            return

        # 命中过滤关键字不处理
        if self._exclude_keywords:
            for keyword in self._exclude_keywords.split("\n"):
                if keyword and keyword in event_path:
                    logger.debug(f"{event_path} 命中排除关键词 {keyword}，跳过处理")
                    return

        # 只处理媒体文件
        if Path(event_path).suffix.lower() not in settings.RMT_MEDIAEXT:
            return

        if event:
            logger.debug(f"变动类型 {event.event_type} 变动路径 {event_path}")
        else:
            logger.debug(f"扫描到文件: {event_path}")
        
        self._handle_file(event_path=event_path, source_dir=source_dir)

    def _handle_file(self, event_path: str, source_dir: str):
        """整理单个文件"""
        try:
            source_path = Path(event_path)
            dest_dir = self._dirconf.get(source_dir)

            if not dest_dir:
                logger.error(f"未找到监控目录 {source_dir} 对应的目的目录")
                return

            # 获取所在目录（向上查找包含 tvshow.nfo 的目录）
            source_folder = self._find_nfo_parent(source_path.parent)

            if not source_folder:
                logger.debug(f"未找到包含 tvshow.nfo 的目录: {event_path}")
                return

            # 查找 tvshow.nfo 文件
            nfo_path = source_folder / "tvshow.nfo"
            if not nfo_path.exists():
                logger.debug(f"{source_folder} 没有 tvshow.nfo，跳过")
                return

            # 解析 nfo 获取片名
            title = self._parse_title_from_nfo(nfo_path)
            if not title:
                logger.warning(f"无法从 {nfo_path} 解析片名")
                return

            # 清理片名中的非法字符
            title = self._sanitize_filename(title)

            # 构建目标文件夹路径
            target_folder = Path(dest_dir) / title

            # 是否重命名
            rename_conf = self._renameconf.get(source_dir, "true")

            # 处理视频文件
            if source_path.suffix.lower() in settings.RMT_MEDIAEXT:
                self._organize_video_file(
                    source_path=source_path,
                    target_folder=target_folder,
                    rename_conf=rename_conf
                )

            # 复制 nfo 和海报文件
            self._copy_metadata_files(
                source_folder=source_folder,
                target_folder=target_folder
            )

            # 发送通知
            if self._notify:
                self._add_to_notify_queue(title, str(source_path))

        except Exception as e:
            logger.error(f"整理文件失败 {event_path}: {str(e)}")

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

        except ET.ParseError as e:
            logger.error(f"解析 NFO 文件失败 {nfo_path}: {str(e)}")
        except Exception as e:
            logger.error(f"读取 NFO 文件失败 {nfo_path}: {str(e)}")

        return None

    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名中的非法字符"""
        illegal_chars = r'[\\/*?:"<>|]'
        cleaned = re.sub(illegal_chars, '', filename)
        cleaned = cleaned.strip('. ')
        return cleaned

    def _organize_video_file(self, source_path: Path, target_folder: Path, rename_conf: str):
        """整理视频文件"""
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
                return

            retcode = self._transfer_file(source_path, target_path)

            if retcode == 0:
                logger.info(f"文件整理完成: {source_path} -> {target_path}")
            else:
                logger.error(f"文件整理失败: {source_path}")

        except Exception as e:
            logger.error(f"整理视频文件失败: {str(e)}")

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

        match = re.search(r'(\d{2})(?:[^0-9]|$)', filename)
        if match and int(match.group(1)) <= 99:
            return int(match.group(1))

        return None

    def _copy_metadata_files(self, source_folder: Path, target_folder: Path):
        """复制 nfo 和海报文件"""
        target_folder.mkdir(parents=True, exist_ok=True)

        source_nfo = source_folder / "tvshow.nfo"
        target_nfo = target_folder / "tvshow.nfo"
        if source_nfo.exists() and not target_nfo.exists():
            self._transfer_file(source_nfo, target_nfo)
            logger.debug(f"复制 NFO: {target_nfo}")

        target_poster = target_folder / "poster.jpg"
        for poster_name in ["poster.jpg", "folder.jpg", "cover.jpg", "thumb.jpg"]:
            source_img = source_folder / poster_name
            if source_img.exists() and not target_poster.exists():
                self._transfer_file(source_img, target_poster)
                logger.debug(f"复制海报: {source_img} -> {target_poster}")
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

            last_time = media_list.get("time")
            files = media_list.get("files", [])

            if not last_time or not files:
                continue

            if (datetime.datetime.now() - last_time).total_seconds() > int(self._interval):
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
            "onlyonce": self._onlyonce,
            "monitor_confs": self._monitor_confs,
            "transfer_type": self._transfer_type,
            "exclude_keywords": self._exclude_keywords,
            "notify": self._notify,
            "interval": self._interval,
            "scan_interval": self._scan_interval
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
                                            "variant": "tonal",
                                            "text": "配置说明：监控方式 auto（实时）或 compatibility（兼容/轮询）。格式示例：auto#/downloads/短剧#/media/短剧#true"
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
            "monitor_confs": "",
            "transfer_type": "link",
            "exclude_keywords": "",
            "notify": False,
            "interval": 10,
            "scan_interval": 60
        }

    def get_page(self) -> List[dict]:
        """返回详情页"""
        return [
            {
                "component": "VCard",
                "content": [
                    {
                        "component": "VCardText",
                        "props": {"class": "pa-4"},
                        "content": [
                            {
                                "component": "div",
                                "content": [
                                    f"监控目录: {self._monitor_confs or '未配置'}",
                                    f"转移方式: {self._transfer_type}",
                                    f"发送通知: {'是' if self._notify else '否'}",
                                    f"定时扫描间隔: {self._scan_interval} 秒"
                                ]
                            }
                        ]
                    }
                ]
            }
        ]

    def get_command(self) -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return []

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
