import datetime
import os
import re
import time
import xml.etree.ElementTree as ET
from collections import OrderedDict
from pathlib import Path
from threading import RLock
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

# 使用可重入锁
lock = RLock()


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
    plugin_desc = "读取tvshow.nfo中的片名，按Emby标准格式整理短剧文件，自动提取演员添加到tag标签"
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

    # 定时器
    _scheduler: Optional[BackgroundScheduler] = None

    def __init__(self):
        super().__init__()
        # 只保留内存缓存，不写入数据库
        self._success_cache: OrderedDict = OrderedDict()
        
        # 预编译正则表达式以提高性能
        self._episode_patterns = [
            re.compile(r'[sS]\d+[eE](\d+)'),      # S01E01
            re.compile(r'[eE][pP]?(\d+)'),        # EP01, E01
            re.compile(r'第\s*(\d+)\s*集'),        # 第01集
            re.compile(r'[^a-zA-Z](\d{2,3})[^a-zA-Z]')  # 01, 001
        ]
        
        # 预编译排除关键词
        self._compiled_exclude_patterns = []
        
        # 系统文件夹集合
        self._system_folders = {'@Recycle', '#recycle', '@eaDir', 
                                'System Volume Information', '$RECYCLE.BIN'}
    def _extract_title_from_folder(self, folder_name: str) -> str:
        """从文件夹名提取剧名
        
        规则：
        1. 去除开头的数字和横杠（如 "22823-小楼昨夜又东风" -> "小楼昨夜又东风"）
        2. 取"（"前面的部分
        """
        original_name = folder_name.strip()
        title = original_name
        
        # 去除开头的数字和横杠（支持 -, －, —）
        title = re.sub(r'^\d+[-－—]\s*', '', title)
        
        # 取"（"前面的部分
        title = re.split(r'[（(]', title)[0]
        
        title = title.strip()
        
        logger.debug(f"剧名提取: '{original_name}' -> '{title}'")
        return title

    def _add_to_success_cache(self, key: str):
        """添加成功记录到缓存"""
        with lock:
            if key in self._success_cache:
                self._success_cache.move_to_end(key)
            else:
                self._success_cache[key] = True


    def _record_success(self, file_path: str, title: str, target_path: str):
        """记录成功 - 只记录到内存"""
        self._add_to_success_cache(file_path)
        logger.info(f"✅ 整理成功: {Path(file_path).name} -> {title}")


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
            
            # 预编译排除关键词
            self._compiled_exclude_patterns = []
            if self._exclude_keywords:
                for kw in self._exclude_keywords.split("\n"):
                    kw = kw.strip()
                    if kw:
                        try:
                            self._compiled_exclude_patterns.append(re.compile(kw))
                        except re.error:
                            self._compiled_exclude_patterns.append(kw)

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

            source_dir = os.path.normpath(source_dir)
            target_dir = os.path.normpath(target_dir)

            self._dirconf[source_dir] = target_dir
            self._renameconf[source_dir] = rename

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

    def _has_nfo_in_folder(self, folder_path: str) -> bool:
        """检查文件夹是否包含 tvshow.nfo"""
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

    def _get_actors_from_nfo(self, nfo_path: Path) -> List[str]:
        """从 NFO 文件中读取演员列表"""
        actors = []
        
        if not nfo_path.exists():
            return actors
        
        try:
            tree = ET.parse(nfo_path)
            root = tree.getroot()
            
            for actor_elem in root.findall("actor"):
                name_elem = actor_elem.find("name")
                if name_elem is not None and name_elem.text:
                    actor_name = name_elem.text.strip()
                    if actor_name:
                        actors.append(actor_name)
            
        except Exception as e:
            logger.error(f"读取 NFO 演员失败 {nfo_path}: {e}")
        
        return actors

    def _sync_actors_to_tags(self, nfo_path: Path):
        """将 NFO 中的演员信息同步到 tag 标签"""
        if not nfo_path.exists():
            return
        
        try:
            actors = self._get_actors_from_nfo(nfo_path)
            if not actors:
                return
            
            tree = ET.parse(nfo_path)
            root = tree.getroot()
            
            existing_tags = {tag.text.strip() for tag in root.findall("tag") if tag.text}
            actors_to_add = [actor for actor in actors if actor not in existing_tags]
            
            if not actors_to_add:
                return
            
            for actor in actors_to_add:
                new_tag = ET.SubElement(root, "tag")
                new_tag.text = actor
            
            try:
                ET.indent(tree, space="  ")
            except AttributeError:
                pass
            
            tree.write(nfo_path, encoding="utf-8", xml_declaration=True)
            logger.info(f"✅ 已将 {len(actors_to_add)} 个演员同步到 tag")
            
        except Exception as e:
            logger.error(f"❌ 同步演员到 tag 失败 {nfo_path}: {e}")

    def _extract_season_from_nfo(self, folder_path: str) -> str:
        """从 NFO 文件中提取季数"""
        nfo_path = Path(folder_path) / "tvshow.nfo"
        if not nfo_path.exists():
            return "S01"
        
        try:
            tree = ET.parse(nfo_path)
            root = tree.getroot()
            
            season_tags = ["season", "Season", "airedSeason"]
            
            for tag in season_tags:
                season_elem = root.find(tag)
                if season_elem is not None and season_elem.text:
                    try:
                        season_num = int(season_elem.text.strip())
                        if 0 <= season_num <= 99:
                            return f"S{season_num:02d}"
                    except (ValueError, TypeError):
                        continue
            
            namedseason = root.find("namedseason")
            if namedseason is not None and namedseason.text:
                try:
                    season_num = int(namedseason.text.strip())
                    if 0 <= season_num <= 99:
                        return f"S{season_num:02d}"
                except (ValueError, TypeError):
                    pass
            
            return "S01"
            
        except Exception as e:
            logger.error(f"读取季数失败 {nfo_path}: {e}")
            return "S01"

    def _extract_episode(self, filename: str) -> Optional[int]:
        """提取集数"""
        for pattern in self._episode_patterns:
            match = pattern.search(filename)
            if match:
                num = int(match.group(1))
                if 1 <= num <= 999:
                    return num
        return None

    def _transfer_file(self, source: Path, target: Path, is_metadata: bool = False) -> bool:
        """执行文件转移"""
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            
            if target.exists():
                logger.debug(f"目标文件已存在，跳过: {target}")
                return True
            
            if self._transfer_type == "move":
                result = SystemUtils.move(source, target)
            elif self._transfer_type == "copy":
                result = SystemUtils.copy(source, target)
            elif self._transfer_type == "link":
                result = SystemUtils.hardlink(source, target)
            elif self._transfer_type == "softlink":
                result = SystemUtils.softlink(source, target)
            else:
                result = SystemUtils.hardlink(source, target)
            
            if result:
                action = "复制" if is_metadata else "转移"
                logger.debug(f"{action}成功: {source.name} -> {target.name}")
            else:
                action = "复制" if is_metadata else "转移"
                logger.error(f"{action}失败: {source} -> {target}")
            
            return bool(result)
        except Exception as e:
            logger.error(f"文件转移异常: {e}")
            return False

    def _organize_video(self, source_path: Path, target_folder: Path, rename: str, has_nfo: bool = True) -> Optional[Path]:
        """整理视频文件
        
        Args:
            source_path: 源文件路径
            target_folder: 目标文件夹
            rename: 是否重命名
            has_nfo: 是否有 nfo 文件（用于决定季数提取方式）
        """
        target_folder.mkdir(parents=True, exist_ok=True)

        episode = self._extract_episode(source_path.name)

        if rename == "true" and episode is not None:
            if has_nfo:
                season = self._extract_season_from_nfo(str(source_path.parent))
            else:
                season = "S01"
            episode_str = f"E{episode:02d}"
            new_name = f"{season}{episode_str}{source_path.suffix}"
            target_path = target_folder / new_name
        else:
            target_path = target_folder / source_path.name

        if target_path.exists():
            logger.info(f"目标文件已存在，跳过: {target_path}")
            return target_path

        if self._transfer_file(source_path, target_path, is_metadata=False):
            logger.info(f"整理完成: {source_path.name} -> {target_path.name}")
            return target_path
        
        logger.error(f"文件转移失败: {source_path}")
        return None

    def _copy_metadata(self, source_folder: Path, target_folder: Path, has_nfo: bool = True):
        """复制元数据并同步演员
        
        Args:
            source_folder: 源文件夹
            target_folder: 目标文件夹
            has_nfo: 是否有 NFO 文件（决定是否复制 NFO 和同步演员）
        """
        target_folder.mkdir(parents=True, exist_ok=True)
        
        if has_nfo:
            # 复制 NFO
            nfo_path = source_folder / "tvshow.nfo"
            if nfo_path.exists() and not (target_folder / "tvshow.nfo").exists():
                result = SystemUtils.copy(nfo_path, target_folder / "tvshow.nfo")
                logger.debug(f"已复制 NFO: {nfo_path.name}")
            
            # 同步演员到 tag
            target_nfo_path = target_folder / "tvshow.nfo"
            if target_nfo_path.exists():
                self._sync_actors_to_tags(target_nfo_path)
        else:
            logger.info(f"没有 NFO 文件，跳过 NFO 复制和演员同步")
        
        # 复制海报（无论是否有 NFO 都尝试）
        if not (target_folder / "poster.jpg").exists():
            for poster_name in ["poster.jpg", "poster.png", "poster.jpeg", "0.jpg"]:
                poster_path = source_folder / poster_name
                if poster_path.exists():
                    result = SystemUtils.copy(poster_path, target_folder / "poster.jpg")
                    logger.info(f"已复制海报: {poster_name}")
                    break

    def _is_valid_folder(self, folder_path: str, source_dir: str) -> bool:
        """检查是否为有效的剧集文件夹"""
        try:
            source_path = Path(source_dir).resolve()
            folder_path_obj = Path(folder_path).resolve()
            
            try:
                relative = folder_path_obj.relative_to(source_path)
            except ValueError:
                logger.debug(f"文件夹不在监控目录下: {folder_path}")
                return False
            
            parts = relative.parts
            
            if len(parts) == 0:
                return False
            
            if len(parts) > 1:
                logger.debug(f"文件夹层级过深: {relative}")
                return False
            
            if parts[0].startswith('.'):
                logger.debug(f"跳过隐藏文件夹: {parts[0]}")
                return False
            
            if parts[0] in self._system_folders:
                logger.debug(f"跳过系统文件夹: {parts[0]}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"路径验证异常: {folder_path} - {e}")
            return False

    def _should_exclude(self, path: str) -> bool:
        """检查路径是否应该被排除"""
        if any(x in path for x in ["/@Recycle", "/#recycle", "/.", "/@eaDir"]):
            return True
        
        if self._compiled_exclude_patterns:
            for pattern in self._compiled_exclude_patterns:
                if isinstance(pattern, re.Pattern):
                    if pattern.search(path):
                        return True
                elif isinstance(pattern, str):
                    if pattern in path:
                        return True
        return False

    def _process_file(self, file_path: str, source_dir: str):
        """处理单个文件"""
        if self._should_exclude(file_path):
            return
        
        if Path(file_path).suffix.lower() not in settings.RMT_MEDIAEXT:
            return
        
        file_path_normalized = str(Path(file_path).resolve())
        
        with lock:
            if file_path_normalized in self._success_cache:
                logger.debug(f"已成功过，跳过: {Path(file_path).name}")
                return

        source_path = Path(file_path)
        folder_path = str(source_path.parent)

        if not self._is_valid_folder(folder_path, source_dir):
            logger.debug(f"不是有效剧集文件夹: {source_path.parent.name}")
            return

        # 检查是否有 nfo
        has_nfo = self._has_nfo_in_folder(folder_path)
        
        # 获取剧名
        if has_nfo:
            title = self._get_title_from_nfo(folder_path)
            if not title:
                title = self._extract_title_from_folder(source_path.parent.name)
                title = self._sanitize_filename(title)
                logger.warning(f"解析NFO失败，使用文件夹名: {title}")
        else:
            title = self._extract_title_from_folder(source_path.parent.name)
            title = self._sanitize_filename(title)
            logger.info(f"未找到 tvshow.nfo，使用文件夹名: {title}")

        if not title:
            logger.warning(f"无法获取片名: {source_path.parent.name}")
            return

        dest_dir = self._dirconf.get(source_dir)
        if not dest_dir:
            logger.error(f"未找到目的目录: {source_dir}")
            return

        target_folder = Path(dest_dir) / title
        rename = self._renameconf.get(source_dir, "true")

        # 整理视频文件
        target_path = self._organize_video(source_path, target_folder, rename, has_nfo)
        
        if not target_path:
            return
        
        # 记录成功
        self._record_success(file_path_normalized, title, str(target_path))
        
        # 复制元数据并同步演员（内部根据 has_nfo 判断）
        self._copy_metadata(Path(folder_path), target_folder, has_nfo=has_nfo)
        
        # 发送通知
        if self._notify:
            self._add_to_notify(title, file_path_normalized)

    def _add_to_notify(self, title: str, file_path: str):
        """添加到通知队列"""
        with lock:
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
            {"cmd": "/shortplay_stats", "event": None, "desc": "查看统计", "category": "管理"},
            {"cmd": "/shortplay_clear", "event": None, "desc": "清空缓存", "category": "管理"}
        ]

    def scan_all_dirs(self):
        """扫描所有监控目录"""
        if self._scanning:
            return

        self._scanning = True
        try:
            logger.info("开始扫描...")
            
            media_extensions = set(settings.RMT_MEDIAEXT)
            
            for source_dir in self._dirconf.keys():
                source_path = Path(source_dir)
                if not source_path.exists():
                    logger.warning(f"源目录不存在: {source_dir}")
                    continue

                for folder in source_path.iterdir():
                    if not folder.is_dir():
                        continue
                    

                    video_files = []
                    for ext in media_extensions:
                        video_files.extend(folder.glob(f"*{ext}"))
                    
                    if not video_files:
                        logger.debug(f"未找到视频文件: {folder.name}")
                        continue
                    
                    for video_file in video_files:
                        file_str = str(video_file)
                        
                        with lock:
                            if file_str in self._success_cache:
                                logger.debug(f"文件已处理: {video_file.name}")
                                continue
                        
                        logger.debug(f"发现新文件: {video_file.name}")
                        self._process_file(file_str, source_dir)

            logger.info("扫描完成")
        except Exception as e:
            logger.error(f"扫描失败: {e}", exc_info=True)
        finally:
            self._scanning = False

    def event_handler(self, event, source_dir: str, event_path: str):
        """处理文件变化事件"""
        if self._should_exclude(event_path):
            return
        
        if Path(event_path).suffix.lower() not in settings.RMT_MEDIAEXT:
            return

        logger.debug(f"检测到文件: {event_path}")
        self._process_file(event_path, source_dir)

    def send_msg(self):
        """发送通知"""
        if not self._notify:
            return
        
        with lock:
            if not self._medias:
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
                                "content": [{"component": "VTextarea", "props": {"model": "exclude_keywords", "label": "排除关键词", "rows": 2, "placeholder": "每行一个关键词（支持正则表达式）"}}]
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
        with lock:
            success_count = len(self._success_cache)

            success_rows = []
            for path in list(self._success_cache.keys())[-20:]:
                success_rows.append({"component": "tr", "content": [
                    {"component": "td", "text": Path(path).name[:50]},
                    {"component": "td", "text": path[:60]},
                    {"component": "td", "text": "成功"}
                ]})

            return [
                {
                    "component": "VRow",
                    "content": [
                        {"component": "VCol", "props": {"cols": 12}, "content": [{"component": "VCard", "props": {"variant": "tonal", "color": "success"}, "content": [{"component": "VCardText", "props": {"class": "text-center"}, "content": [{"component": "div", "props": {"class": "text-h4"}, "text": str(success_count)}, {"component": "div", "text": "成功整理"}]}]}]}
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