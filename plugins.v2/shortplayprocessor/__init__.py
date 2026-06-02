import datetime
import os
import re
import threading
import time
import xml.etree.ElementTree as ET
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from threading import Lock, RLock
from typing import Any, List, Dict, Tuple, Optional, Set, Callable
from xml.dom import minidom

import chardet
import pytz
from PIL import Image
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from lxml import etree
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

from app.core.config import settings
from app.core.meta.words import WordsMatcher
from app.core.metainfo import MetaInfoPath
from app.db.site_oper import SiteOper
from app.helper.sites import SitesHelper
from app.log import logger
from app.modules.indexer.spider import SiteSpider
from app.plugins import _PluginBase
from app.schemas import MediaInfo
from app.schemas.types import NotificationType
from app.utils.dom import DomUtils
from app.utils.http import RequestUtils
from app.utils.system import SystemUtils

# ========== 常量定义 ==========
MAX_CACHE_SIZE = 1000
MAX_RETRIES = 3
RETRY_DELAY = 1
LOCK_TIMEOUT = 30
MAX_DISPLAY_CACHE = 50  # 面板最多显示50条缓存

# 系统文件夹黑名单
SYSTEM_FOLDERS = {'@Recycle', '#recycle', '@eaDir', 'System Volume Information', '$RECYCLE.BIN', '.DS_Store', 'Thumbs.db'}


class TransferType(str, Enum):
    """转移类型"""
    MOVE = "move"
    COPY = "copy"
    LINK = "link"
    SOFTLINK = "softlink"


class ProcessStatus(str, Enum):
    """处理状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ProcessRecord:
    """处理记录"""
    file_path: str
    title: str
    target_path: str
    status: ProcessStatus
    timestamp: datetime.datetime
    error_msg: str = ""
    retry_count: int = 0


@dataclass
class CacheEntry:
    """缓存条目"""
    mediainfo: Optional[MediaInfo]
    pt_tv_info: Optional[Dict]
    title: str
    timestamp: float = field(default_factory=time.time)
    
    def is_expired(self, ttl: int = 3600) -> bool:
        """检查是否过期（默认1小时）"""
        return time.time() - self.timestamp > ttl
    
    def update_timestamp(self):
        """更新时间戳"""
        self.timestamp = time.time()


class FileMonitorHandler(FileSystemEventHandler):
    """目录监控响应类 - 优化版"""
    
    def __init__(self, watching_path: str, file_change: Any, delay: float = 0.5, **kwargs):
        super().__init__(**kwargs)
        self._watch_path = watching_path
        self.file_change = file_change
        self.delay = delay
        self._pending_events: Dict[str, float] = {}
        self._lock = Lock()
    
    def on_created(self, event):
        if not event.is_directory:
            self._handle_event(event.src_path)
    
    def on_moved(self, event):
        if not event.is_directory:
            self._handle_event(event.dest_path)
    
    def _handle_event(self, path: str):
        """处理事件（去抖）"""
        with self._lock:
            self._pending_events[path] = time.time()
        
        def delayed_process():
            time.sleep(self.delay)
            with self._lock:
                if self._pending_events.get(path) and time.time() - self._pending_events[path] >= self.delay:
                    self._pending_events.pop(path, None)
                    self.file_change.event_handler(
                        event=None,
                        source_dir=self._watch_path,
                        event_path=path
                    )
        
        threading.Thread(target=delayed_process, daemon=True).start()


class ShortPlayProcessor(_PluginBase):
    """短剧处理器 - 整合刮削和整理功能"""

    # 插件元数据
    plugin_name = "短剧处理器"
    plugin_desc = "监控短剧目录，自动刮削元数据并整理到媒体库（优先本地NFO，支持豆瓣/PT站）"
    plugin_icon = "Amule_B.png"
    plugin_version = "1.0.0"
    plugin_author = "thsrite,AI"
    author_url = "https://github.com/m216owen/MoviePilot-Plugins"
    plugin_config_prefix = "shortplayprocessor_"
    plugin_order = 26
    auth_level = 1

    def __init__(self):
        super().__init__()
        
        # 预编译正则表达式
        self._init_regex_patterns()
        
        # 配置属性
        self._enabled = False
        self._onlyonce = False
        self._monitor_confs = ""
        self._transfer_type = TransferType.LINK
        self._exclude_keywords = ""
        self._notify = False
        self._interval = 10
        self._scan_interval = 60
        self._scan_enabled = True
        self._image = False
        self._timeline = "00:00:10"
        
        # ========== 三个数据源开关 ==========
        self._enable_local_nfo = True      # 本地NFO识别开关
        self._enable_mp_recognition = True  # MP识别开关（豆瓣/TMDB）
        self._enable_pt_search = True       # PT站点搜索开关
        
        # 配置字典
        self._dirconf: Dict[str, str] = {}
        self._renameconf: Dict[str, str] = {}
        self._coverconf: Dict[str, str] = {}
        
        # 缓存和状态
        self._success_cache: OrderedDict[str, ProcessRecord] = OrderedDict()
        self._series_cache: Dict[str, CacheEntry] = {}
        self._processing_files: Set[str] = set()
        self._failed_records: List[ProcessRecord] = []
        self._medias: Dict[str, Dict] = {}
        self._scanning = False
        self._compiled_exclude_patterns: List[Any] = []
        
        # 统计信息
        self._stats = {
            'total_processed': 0,
            'success_count': 0,
            'failed_count': 0,
            'skipped_count': 0,
            'last_process_time': None,
            'start_time': datetime.datetime.now()
        }
        
        # 线程安全
        self._lock = RLock()
        self._cache_lock = Lock()
        
        # 监控器
        self._observer: List[Any] = []
        
        # 定时器
        self._scheduler: Optional[BackgroundScheduler] = None
    
    def _init_regex_patterns(self):
        """初始化正则表达式模式"""
        
        # 剧名清理模式（按顺序执行）
        self._title_clean_patterns = [
            (r'^\d+[-－—]\s*', ''),           # 去除开头序号
            (r'\..*', ''),                    # 去除点号及之后所有内容（删除拼音后缀）
            (r'[（(].*$', ''),                 # 去除括号及之后内容
            (r'\[[^\]]+\]', ''),              # 去除方括号内容
            (r'[-–—_\s]+$', ''),              # 去除末尾分隔符
        ]
        
        # 站点配置
        self._sites_config = [
            {
                "domain": "agsvpt.com",
                "name": "AGSV",
                "search_url": "https://www.agsvpt.com/torrents.php?search_mode=0&search_area=0&page=0&notnewword=1&cat=419&search={title}",
                "img_xpath": "//*[@id='kdescr']/img[1]/@src"
            },
            {
                "domain": "ilolicon.com",
                "name": "萝莉站",
                "search_url": "https://share.ilolicon.com/torrents.php?search_mode=0&search_area=0&page=0&notnewword=1&cat=402&search={title}",
                "img_xpath": "//*[@id='kdescr']/img[1]/@src"
            },
            {
                "domain": "ptskit.org",
                "name": "PTSKit",
                "search_url": "https://www.ptskit.org/torrents.php?search_mode=0&search_area=0&page=0&notnewword=1&tag_id=238&search={title}",
                "img_xpath": "//*[@id='kdescr']/img[1]/@src"
            }
        ]

    def init_plugin(self, config: dict = None):
        """初始化插件"""
        if not config:
            return
        
        # 加载配置
        self._load_config(config)
        
        # 清空旧配置
        self._dirconf.clear()
        self._renameconf.clear()
        self._coverconf.clear()
        
        # 停止现有服务
        self.stop_service()
        
        if not (self._enabled or self._onlyonce):
            return
        
        # 解析监控目录配置
        if not self._parse_monitor_configs():
            logger.warning("监控目录配置解析失败")
            return
        
        # 启动定时服务
        self._start_scheduler()
        
        # 全量同步 - 使用线程直接执行，避免调度器问题
        if self._onlyonce:
            self._schedule_once_scan()
            self._onlyonce = False
            self._update_config()
        
        # 封面裁剪
        if self._image:
            self._image = False
            self._update_config()
            self._schedule_image_crop()
        
    
    def _load_config(self, config: dict):
        """加载配置"""
        self._enabled = config.get("enabled", False)
        self._onlyonce = config.get("onlyonce", False)
        self._monitor_confs = config.get("monitor_confs", "")
        
        transfer_type = config.get("transfer_type", "link")
        self._transfer_type = TransferType(transfer_type) if transfer_type in [t.value for t in TransferType] else TransferType.LINK
        
        self._exclude_keywords = config.get("exclude_keywords", "")
        self._notify = config.get("notify", False)
        self._interval = int(config.get("interval", 10))
        self._scan_interval = int(config.get("scan_interval", 60))
        self._scan_enabled = config.get("scan_enabled", True)
        self._image = config.get("image", False)
        
        # ========== 加载三个数据源开关配置 ==========
        self._enable_local_nfo = config.get("enable_local_nfo", True)
        self._enable_mp_recognition = config.get("enable_mp_recognition", True)
        self._enable_pt_search = config.get("enable_pt_search", True)
        
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
    
    def _parse_monitor_configs(self) -> bool:
        """解析监控目录配置"""
        if not self._monitor_confs:
            logger.warning("未配置监控目录")
            return False
        
        success = False
        for line in self._monitor_confs.split("\n"):
            line = line.strip()
            if not line:
                continue
            
            parts = line.split("#")
            if len(parts) < 3:
                logger.error(f"配置格式错误: {line}，应为: 监控方式#源目录#目的目录#是否重命名#封面比例")
                continue
            
            mode = parts[0].strip()
            source_dir = os.path.normpath(parts[1].strip())
            target_dir = os.path.normpath(parts[2].strip())
            rename = parts[3].strip() if len(parts) > 3 else "smart"
            cover = parts[4].strip() if len(parts) > 4 else "16:9"
            
            # 验证目录
            if not os.path.exists(source_dir):
                logger.warning(f"源目录不存在，跳过: {source_dir}")
                continue
            
            self._dirconf[source_dir] = target_dir
            self._renameconf[source_dir] = rename
            self._coverconf[source_dir] = cover
            
            if self._enabled:
                self._start_monitor(mode, source_dir)
            
            success = True
        
        return success
    
    def _start_monitor(self, mode: str, source_dir: str):
        """启动目录监控"""
        try:
            if mode == "compatibility":
                observer = PollingObserver(timeout=10)
                logger.info(f"{source_dir} 使用兼容模式")
            else:
                observer = Observer(timeout=10)
                logger.info(f"{source_dir} 使用实时监控")
            
            self._observer.append(observer)
            observer.schedule(
                FileMonitorHandler(source_dir, self, delay=0.5),
                path=source_dir,
                recursive=True
            )
            observer.daemon = True
            observer.start()
            logger.info(f"{source_dir} 监控已启动")
        except Exception as e:
            logger.error(f"{source_dir} 监控启动失败: {e}")
    
    def _start_scheduler(self):
        """启动定时器"""
        try:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            logger.debug("调度器已创建")
            
            # 入库消息定时发送
            if self._notify:
                self._scheduler.add_job(
                    func=self._send_notifications,
                    trigger=IntervalTrigger(seconds=15),
                    id="shortplayprocessor_notify",
                    coalesce=True,
                    max_instances=1
                )
                logger.debug("已添加通知任务")
            
            # 定时扫描任务
            if self._enabled and self._scan_enabled and self._scan_interval > 0:
                self._scheduler.add_job(
                    func=self.scan_all_dirs,
                    trigger=IntervalTrigger(seconds=self._scan_interval),
                    id="shortplayprocessor_scan",
                    coalesce=True,
                    max_instances=1
                )
                logger.info(f"定时扫描已启动，间隔: {self._scan_interval} 秒")
            
            # 启动任务
            if self._scheduler.get_jobs():
                self._scheduler.start()
                logger.debug("调度器已启动")
        except Exception as e:
            logger.error(f"启动调度器失败: {e}")
            self._scheduler = None
    
    def _schedule_once_scan(self):
        """安排一次性扫描 - 使用线程直接执行，避免调度器问题"""
        def delayed_scan():
            logger.info("等待3秒后开始扫描...")
            time.sleep(3)
            logger.info("开始执行一次性扫描")
            self.scan_all_dirs()
            logger.info("一次性扫描执行完成")
        
        thread = threading.Thread(target=delayed_scan, daemon=True)
        thread.start()
    
    def _schedule_image_crop(self):
        """安排封面裁剪 - 使用线程直接执行"""
        def delayed_crop():
            logger.info("等待5秒后开始裁剪封面...")
            time.sleep(5)
            self._crop_all_posters()
        
        thread = threading.Thread(target=delayed_crop, daemon=True)
        thread.start()
    
    # ========== 文件处理核心方法 ==========
    
    def scan_all_dirs(self):
        """扫描所有监控目录"""
        if self._scanning:
            logger.info("扫描任务正在进行中，跳过本次扫描")
            return
        
        self._scanning = True
        start_time = time.time()
        
        try:
            logger.info("=" * 50)
            logger.info("开始扫描监控目录...")
            
            for source_dir in self._dirconf.keys():
                source_path = Path(source_dir)
                if not source_path.exists():
                    continue
                
                for folder in source_path.iterdir():
                    if not folder.is_dir():
                        continue
                    
                    if not self._is_valid_folder(str(folder), source_dir):
                        continue
                    
                    # 获取视频文件
                    video_files = self._find_video_files(folder)
                    if not video_files:
                        continue
                    
                    for video_file in video_files:
                        # 检查是否已处理
                        if self._is_already_processed(str(video_file)):
                            continue
                        
                        # 处理文件
                        self._process_file_with_retry(str(video_file), source_dir)
            
            elapsed = time.time() - start_time
            logger.info(f"扫描完成，耗时: {elapsed:.2f}秒")
            logger.info("=" * 50)
            
        except Exception as e:
            logger.error(f"扫描失败: {e}", exc_info=True)
        finally:
            self._scanning = False
    
    def _find_video_files(self, folder: Path) -> List[Path]:
        """查找视频文件"""
        video_files = []
        for ext in settings.RMT_MEDIAEXT:
            video_files.extend(folder.glob(f"*{ext}"))
            video_files.extend(folder.glob(f"*{ext.upper()}"))
        return video_files
    
    def _is_already_processed(self, file_path: str) -> bool:
        """检查文件是否已处理"""
        with self._lock:
            if file_path in self._success_cache:
                return True
            if file_path in self._processing_files:
                return True
        return False
    
    def _process_file_with_retry(self, file_path: str, source_dir: str) -> bool:
        """带重试的文件处理"""
        for attempt in range(MAX_RETRIES):
            try:
                result = self._process_file(file_path, source_dir)
                if result:
                    return True
            except Exception as e:
                logger.error(f"处理失败 (尝试 {attempt + 1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    self._record_failure(file_path, str(e))
        return False
    
    def _process_file(self, file_path: str, source_dir: str) -> bool:
        """处理单个文件"""
        # 排除检查
        if self._should_exclude(file_path):
            return False
        
        # 扩展名检查
        if Path(file_path).suffix.lower() not in settings.RMT_MEDIAEXT:
            return False
        
        # 标记处理中
        file_path_normalized = str(Path(file_path).resolve())
        with self._lock:
            if file_path_normalized in self._processing_files:
                logger.debug(f"文件正在处理中，跳过: {Path(file_path).name}")
                return False
            self._processing_files.add(file_path_normalized)
        
        try:
            source_path = Path(file_path)
            folder_path = source_path.parent
            folder_path_str = str(folder_path.resolve())
            
            # 验证文件夹
            if not self._is_valid_folder(folder_path_str, source_dir):
                return False
            
            # 获取配置
            dest_dir = self._dirconf.get(source_dir)
            if not dest_dir:
                logger.error(f"未找到目标目录: {source_dir}")
                return False
            
            rename_conf = self._renameconf.get(source_dir, "smart")
            cover_conf = self._coverconf.get(source_dir, "16:9")
            
            # 获取剧集信息（带缓存）
            clean_title = self._extract_title_from_folder(folder_path.name)
            cache_key = folder_path_str
            
            with self._cache_lock:
                if cache_key in self._series_cache:
                    cached = self._series_cache[cache_key]
                    if not cached.is_expired():
                        mediainfo = cached.mediainfo
                        pt_tv_info = cached.pt_tv_info
                        title = cached.title
                        logger.debug(f"💾 使用缓存: {title}")
                        cached.update_timestamp()
                    else:
                        logger.debug(f"⏰ 缓存过期，重新识别: {cache_key}")
                        del self._series_cache[cache_key]
                        mediainfo, pt_tv_info, title = self._fetch_series_info(
                            folder_path, clean_title
                        )
                else:
                    logger.debug(f"🆕 首次识别: {clean_title}")
                    mediainfo, pt_tv_info, title = self._fetch_series_info(
                        folder_path, clean_title
                    )
                    self._series_cache[cache_key] = CacheEntry(
                        mediainfo=mediainfo,
                        pt_tv_info=pt_tv_info,
                        title=title
                    )
            
            if not title:
                logger.warning(f"无法获取片名: {folder_path.name}")
                return False
            
            # 创建目标目录
            target_folder = Path(dest_dir) / self._sanitize_filename(title)
            target_folder.mkdir(parents=True, exist_ok=True)
            
            # 整理视频文件
            target_path = self._organize_video(source_path, target_folder, rename_conf, folder_path)
            if not target_path:
                return False
            
            # 处理元数据（仅首次）
            nfo_path = target_folder / "tvshow.nfo"
            if not nfo_path.exists():
                self._process_metadata(folder_path, target_folder, mediainfo, title, cover_conf, pt_tv_info)
            
            # 记录成功
            self._record_success(file_path_normalized, title, str(target_path))
            
            # 添加到通知队列
            if self._notify:
                self._add_to_notify(title, file_path_normalized)
            
            # 更新统计
            with self._lock:
                self._stats['total_processed'] += 1
                self._stats['success_count'] += 1
                self._stats['last_process_time'] = datetime.datetime.now()
            
            return True
            
        except Exception as e:
            logger.error(f"处理文件异常: {e}", exc_info=True)
            self._record_failure(file_path_normalized, str(e))
            return False
        finally:
            with self._lock:
                self._processing_files.discard(file_path_normalized)

    def _is_title_match(self, recognized_title: str, search_title: str) -> bool:
        """检查识别的标题是否与搜索标题匹配"""
        if not recognized_title or not search_title:
            return False
        
        if recognized_title in search_title or search_title in recognized_title:
            logger.debug(f"标题匹配: '{recognized_title}' ↔ '{search_title}'")
            return True

        return False
    
    def _fetch_series_info(self, folder_path: Path, clean_title: str) -> Tuple[Optional[MediaInfo], Optional[Dict], str]:
        """获取剧集信息（根据开关控制数据源）"""
        
        # ========== 1. 本地 NFO（根据开关） ==========
        if self._enable_local_nfo:
            local_nfo_info = self._get_info_from_local_nfo(folder_path)
            if local_nfo_info:
                logger.info(f"✅ 使用本地 NFO: {local_nfo_info['title']}")
                mediainfo = self._create_mediainfo_from_local(local_nfo_info, clean_title)
                return mediainfo, None, local_nfo_info['title']
            else:
                logger.debug("📁 未找到本地 NFO")
        
        # ========== 2. MP 识别（豆瓣/TMDB，根据开关） ==========
        if self._enable_mp_recognition:
            try:
                file_meta = MetaInfoPath(Path(f"{clean_title}"))
                mediainfo = self.chain.recognize_media(meta=file_meta)
                
                if mediainfo and getattr(mediainfo, 'source', None) in ['douban', 'themoviedb']:
                    recognized_title = mediainfo.title
                    if self._is_title_match(recognized_title, clean_title):
                        logger.info(f"✅ MP识别成功: {recognized_title} ({mediainfo.source})")
                        title = recognized_title
                        
                        if hasattr(mediainfo, 'poster_path') and mediainfo.poster_path:
                            if 'm_ratio_poster' in mediainfo.poster_path:
                                mediainfo.poster_path = mediainfo.poster_path.replace('m_ratio_poster', 'm')
                        
                        if hasattr(mediainfo, 'actors') and mediainfo.actors:
                            logger.debug(f"🎭 获取到 {len(mediainfo.actors)} 个演员")
                        elif hasattr(mediainfo, 'douban_info') and mediainfo.douban_info:
                            self._extract_actors_from_douban(mediainfo)
                        
                        return mediainfo, None, title
                    else:
                        logger.debug(f"⚠️ 标题不匹配: '{recognized_title}' ≠ '{clean_title}'")
                else:
                    logger.debug(f"🔍 MP识别无结果: {clean_title}")
            except Exception as e:
                logger.debug(f"❌ MP识别异常: {e}")
        
        # ========== 3. PT 站搜索（根据开关） ==========
        if self._enable_pt_search:
            logger.debug(f"🔍 开始 PT 站搜索: {clean_title}")
            pt_tv_info = self._search_pt_site(clean_title)
            if pt_tv_info and pt_tv_info.get("title"):
                logger.info(f"✅ PT站搜索成功: {pt_tv_info['title']} ({pt_tv_info.get('source', 'PT站')})")
                return None, pt_tv_info, pt_tv_info['title']
            else:
                logger.debug(f"🔍 PT站搜索无结果: {clean_title}")
        
        # ========== 4. 使用文件夹名 ==========
        logger.info(f"📁 使用文件夹名: {clean_title}")
        return None, None, clean_title
    
    def _fix_douban_poster_url(self, url: str) -> str:
        """修复豆瓣海报URL"""
        if 'm_ratio_poster' in url:
            return url.replace('m_ratio_poster', 'm')
        return url
    
    def _extract_actors_from_douban(self, mediainfo: MediaInfo):
        """从豆瓣信息提取演员"""
        if hasattr(mediainfo, 'douban_info') and mediainfo.douban_info:
            douban_info = mediainfo.douban_info
            if isinstance(douban_info, dict) and 'actors' in douban_info:
                actors = []
                for actor in douban_info['actors']:
                    if isinstance(actor, dict) and 'name' in actor:
                        actors.append(actor['name'])
                    elif isinstance(actor, str):
                        actors.append(actor)
                if actors:
                    mediainfo.actors = actors
    
    def _organize_video(self, source_path: Path, target_folder: Path, rename_conf: str, source_folder: Path) -> Optional[Path]:
        """整理视频文件"""
        episode = self._extract_episode(source_path.name)
        
        season_num = self._extract_season_from_nfo(source_folder)
        if season_num is None:
            season_num = self._extract_season(source_path.name)
        
        if rename_conf == "smart":
            if episode is None and season_num is not None:
                episode = 1
                logger.debug(f"📺 无集数信息，使用默认第1集")
        
        if rename_conf == "smart" and episode is not None and season_num is not None:
            season_str = f"S{season_num:02d}"
            episode_str = f"E{episode:02d}"
            new_name = f"{season_str}{episode_str}{source_path.suffix}"
            target_path = target_folder / new_name
            logger.debug(f"✏️ 重命名: {source_path.name} -> {new_name}")
        else:
            target_path = target_folder / source_path.name
            if episode is None:
                logger.debug(f"📄 保持原名: {source_path.name}")
        
        target_path = self._resolve_conflict(target_path, source_path)
        if not target_path:
            return None
        
        if self._transfer_file(source_path, target_path):
            logger.info(f"✅ {source_path.name} -> {target_path.name}")
            return target_path
        
        logger.error(f"❌ 转移失败: {source_path.name}")
        return None
    
    def _resolve_conflict(self, target_path: Path, source_path: Path) -> Optional[Path]:
        """解决文件冲突"""
        if not target_path.exists():
            return target_path
        
        try:
            if target_path.samefile(source_path):
                logger.debug(f"⏭️ 文件已处理过，跳过: {target_path.name}")
                return target_path
            
            if target_path.stat().st_size == source_path.stat().st_size:
                logger.warning(f"⚠️ 同名同大小文件已存在，跳过: {target_path.name}")
                return None
            
            tmp_path = target_path.with_suffix(target_path.suffix + '.tmp')
            if self._transfer_file(source_path, tmp_path):
                target_path.unlink(missing_ok=True)
                tmp_path.rename(target_path)
                logger.debug(f"🔄 文件冲突，替换: {source_path.name} -> {target_path.name}")
                return target_path
            return None
            
        except Exception as e:
            logger.error(f"❌ 检查文件冲突失败: {e}")
            return None
    
    def _transfer_file(self, source: Path, target: Path, is_metadata: bool = False) -> bool:
        """执行文件转移"""
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            
            if target.exists():
                return True
            
            if is_metadata or target.suffix in ['.nfo', '.jpg', '.png']:
                result = SystemUtils.copy(source, target)
            else:
                if self._transfer_type == TransferType.MOVE:
                    result = SystemUtils.move(source, target)
                elif self._transfer_type == TransferType.COPY:
                    result = SystemUtils.copy(source, target)
                elif self._transfer_type == TransferType.SOFTLINK:
                    result = SystemUtils.softlink(source, target)
                else:
                    result = SystemUtils.link(source, target)
            
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
    
    def _process_metadata(self, source_folder: Path, target_folder: Path, 
                          mediainfo: Optional[MediaInfo], title: str, 
                          cover_conf: str, pt_tv_info: Optional[Dict] = None):
        """处理元数据"""
        nfo_path = target_folder / "tvshow.nfo"
        
        if not nfo_path.exists():
            source_nfo = source_folder / "tvshow.nfo"
            if source_nfo.exists():
                self._transfer_file(source_nfo, nfo_path, is_metadata=True)
                logger.debug(f"📄 复制本地NFO: {nfo_path.name}")
            else:
                self._generate_nfo(target_folder, mediainfo, title, pt_tv_info)
        
        if nfo_path.exists():
            self._sync_actors_to_tags(nfo_path)
        
        self._process_poster(source_folder, target_folder, mediainfo, cover_conf, pt_tv_info)
    
    def _generate_nfo(self, target_folder: Path, mediainfo: Optional[MediaInfo], 
                    title: str, pt_tv_info: Optional[Dict]):
        """生成 NFO 文件"""
        if mediainfo and getattr(mediainfo, 'source', None) in ['douban', 'themoviedb']:
            self._gen_tv_nfo_with_douban(target_folder, mediainfo)
        elif pt_tv_info and pt_tv_info.get("title"):
            self._gen_tv_nfo_with_pt(target_folder, pt_tv_info)
            if pt_tv_info.get("actors"):
                self._add_actors_to_nfo(target_folder / "tvshow.nfo", pt_tv_info["actors"])
        else:
            self._gen_tv_nfo_file(target_folder, title)
    
    def _process_poster(self, source_folder: Path, target_folder: Path, 
                        mediainfo: Optional[MediaInfo], cover_conf: str, 
                        pt_tv_info: Optional[Dict]):
        """处理海报 - 根据 _image 开关决定是否裁剪"""
        poster_path = target_folder / "poster.jpg"
        
        if poster_path.exists():
            logger.debug(f"📷 海报已存在，跳过: {poster_path.name}")
            if self._image and cover_conf and cover_conf != "None":
                self._crop_poster(poster_path, cover_conf)
            return
        
        source_poster = source_folder / "poster.jpg"
        if source_poster.exists():
            self._transfer_file(source_poster, poster_path, is_metadata=True)
            logger.info(f"📷 复制本地海报: {poster_path.name}")
            if self._image and cover_conf and cover_conf != "None":
                self._crop_poster(poster_path, cover_conf)
            return
        
        poster_url = None
        if mediainfo and getattr(mediainfo, 'source', None) in ['douban', 'themoviedb']:
            poster_url = getattr(mediainfo, 'poster_path', None)
            logger.debug(f"📷 从 {mediainfo.source} 获取海报" + (f": {poster_url[:80]}..." if poster_url else " - 无URL"))
        elif pt_tv_info and pt_tv_info.get("poster_url"):
            poster_url = pt_tv_info.get("poster_url")
            logger.debug(f"📷 从 PT站 获取海报: {poster_url[:80]}...")
        
        if poster_url:
            if self._download_image(poster_url, poster_path):
                logger.info(f"📷 海报下载成功: {poster_path.name}")
                if self._image and cover_conf and cover_conf != "None":
                    self._crop_poster(poster_path, cover_conf)
    
    # ========== 辅助方法 ==========
    
    def _extract_title_from_folder(self, folder_name: str) -> str:
        """从文件夹名提取剧名"""
        if not folder_name:
            return ""
        
        original_name = folder_name.strip()
        
        title = original_name
        for pattern, repl in self._title_clean_patterns:
            title = re.sub(pattern, repl, title)
        
        title = title.strip()
        return title if title else original_name
    
    def _extract_episode(self, filename: str) -> Optional[int]:
        """提取集数 - 优先匹配明确格式"""
        match = re.search(r'[eE][pP]?(\d{1,3})', filename)
        if match:
            episode = int(match.group(1))
            logger.debug(f"匹配到 E01 格式，集数: {episode}")
            return episode
        
        match = re.search(r'第(\d+)集', filename)
        if match:
            episode = int(match.group(1))
            logger.debug(f"匹配到 第X集 格式，集数: {episode}")
            return episode
        
        for part in filename.split('.'):
            if part.isdigit():
                num = int(part)
                if 1 <= num <= 999:
                    logger.debug(f"按点分隔提取纯数字: {num}")
                    return num
        
        logger.debug(f"未提取到集数")
        return None
    
    def _extract_season(self, filename: str) -> int:
        """提取季数，默认返回1"""
        match = re.search(r'[sS](\d+)[eE](\d+)', filename)
        if match:
            return int(match.group(1))
        
        for part in filename.split('.'):
            match = re.match(r'^[sS](\d+)$', part)
            if match:
                return int(match.group(1))
        
        return 1
    
    def _extract_season_from_nfo(self, folder_path: Path) -> Optional[int]:
        """从NFO文件提取季数"""
        nfo_path = folder_path / "tvshow.nfo"
        if not nfo_path.exists():
            return None
        
        try:
            tree = ET.parse(nfo_path)
            root = tree.getroot()
            season_elem = root.find("season")
            if season_elem is not None and season_elem.text:
                season = int(season_elem.text.strip())
                if season > 0:
                    return season
        except Exception:
            pass
        return None
    
    def _get_info_from_local_nfo(self, folder_path: Path) -> Optional[Dict]:
        """从本地 tvshow.nfo 读取剧集信息"""
        nfo_path = folder_path / "tvshow.nfo"
        if not nfo_path.exists():
            return None        
        try:
            tree = ET.parse(nfo_path)
            root = tree.getroot()
            
            info = {
                "title": None,
                "original_title": None,
                "year": None,
                "overview": None,
                "country": None,
                "genre": None,
                "rating": None,
                "douban_id": None,
                "poster_path": None,
                "season": None
            }
            
            title_elem = root.find("title")
            if title_elem is not None and title_elem.text:
                info["title"] = title_elem.text.strip()
            
            original_elem = root.find("originaltitle")
            if original_elem is not None and original_elem.text:
                info["original_title"] = original_elem.text.strip()
            
            year_elem = root.find("year")
            if year_elem is not None and year_elem.text:
                info["year"] = year_elem.text.strip()
            
            plot_elem = root.find("plot")
            if plot_elem is not None and plot_elem.text:
                info["overview"] = plot_elem.text.strip()
            
            country_elem = root.find("country")
            if country_elem is not None and country_elem.text:
                info["country"] = country_elem.text.strip()
            
            genre_elems = root.findall("genre")
            if genre_elems:
                info["genre"] = ", ".join([g.text.strip() for g in genre_elems if g.text])
            
            rating_elem = root.find("rating")
            if rating_elem is not None and rating_elem.text:
                try:
                    info["rating"] = float(rating_elem.text.strip())
                except ValueError:
                    pass
            
            for uid in root.findall("uniqueid"):
                if uid.get("type") == "douban" and uid.text:
                    info["douban_id"] = uid.text.strip()
                    break
            
            season_elem = root.find("season")
            if season_elem is not None and season_elem.text:
                info["season"] = season_elem.text.strip()
            
            poster_path = folder_path / "poster.jpg"
            if poster_path.exists():
                info["poster_path"] = str(poster_path)
            
            if info["title"]:
                logger.info(f"从本地 NFO 读取到剧集信息: {info['title']}")
                return info
            
        except Exception as e:
            logger.error(f"解析本地 NFO 失败: {e}")
        
        return None
    
    def _create_mediainfo_from_local(self, info: Dict, title: str) -> MediaInfo:
        """从本地 NFO 信息创建 MediaInfo 对象"""
        mediainfo = MediaInfo()
        mediainfo.title = info.get("title") or title
        mediainfo.original_title = info.get("original_title") or info.get("title") or title
        mediainfo.year = info.get("year")
        mediainfo.overview = info.get("overview")
        mediainfo.production_countries = [info.get("country")] if info.get("country") else []
        mediainfo.genres = [info.get("genre")] if info.get("genre") else []
        mediainfo.vote_average = info.get("rating")
        mediainfo.douban_id = info.get("douban_id")
        mediainfo.poster_path = info.get("poster_path")
        mediainfo.source = "local"
        return mediainfo
    
    def _search_pt_site(self, title: str) -> Optional[Dict]:
        """搜索PT站点获取剧集信息"""
        for site_config in self._sites_config:
            try:
                site = SiteOper().get_by_domain(site_config["domain"])
                if not site:
                    logger.debug(f"⚠️ 站点 {site_config['domain']} 未配置，跳过")
                    continue
                
                req_url = site_config["search_url"].format(title=title)
                logger.debug(f"🔍 搜索 {site_config['name']}: {title}")
                
                page_source = self._get_page_source(req_url, site)
                if not page_source:
                    logger.debug(f"⚠️ 请求失败: {site_config['name']}")
                    continue
                
                indexer = SitesHelper().get_indexer(site_config["domain"])
                if not indexer:
                    continue
                
                spider = SiteSpider(indexer=indexer, page=1)
                torrents = spider.parse(page_source)
                if not torrents:
                    logger.debug(f"🔍 未找到种子: {site_config['name']}")
                    continue
                
                detail_url = torrents[0].get("page_url")
                if not detail_url:
                    continue
                    
                detail_source = self._get_page_source(detail_url, site)
                if not detail_source:
                    continue
                
                html = etree.HTML(detail_source)
                if html is None:
                    continue
                
                image_elem = html.xpath(site_config["img_xpath"])
                poster_url = str(image_elem[0]) if image_elem else None
                if poster_url:
                    logger.debug(f"📷 获取到封面: {poster_url[:80]}...")
                
                tv_info = self._parse_pt_nfo(html, title, site_config["name"])
                if poster_url:
                    tv_info["poster_url"] = poster_url
                
                if tv_info.get("title"):
                    logger.debug(f"✅ 解析成功: {tv_info['title']}")
                    return tv_info
                    
            except Exception as e:
                logger.debug(f"❌ 搜索站点 {site_config.get('name', 'unknown')} 异常: {e}")
                continue
        
        return None
    
    def _parse_pt_nfo(self, html, title: str, source: str) -> Dict:
        """解析 PT 站 NFO 信息"""
        tv_info = {
            "source": source,
            "title": title,
            "year": "",
            "country": "",
            "genre": "",
            "overview": "",
            "actors": []
        }
        
        desc_elem = html.xpath("//*[@id='kdescr']")
        if not desc_elem:
            return tv_info
        
        text = desc_elem[0].xpath("string()").strip()
        if not text:
            return tv_info
        
        patterns = [
            (r'[◎]?片\s*名\s*[:：]?\s*([^\n]+)', 'title'),
            (r'[◎]?年\s*代\s*[:：]?\s*(\d{4})', 'year'),
            (r'[◎]?产\s*地\s*[:：]?\s*([^\n]+)', 'country'),
            (r'[◎]?类\s*别\s*[:：]?\s*([^\n]+)', 'genre'),
            (r'[◎]?简\s*介\s*[:：]?\s*([^\n]+)', 'overview'),
        ]
        
        for pattern, field in patterns:
            match = re.search(pattern, text)
            if match:
                tv_info[field] = match.group(1).strip()
        
        actors_match = re.search(r'[◎]?主\s*演\s*[:：]?\s*([^\n]+)', text)
        if actors_match:
            actors_str = actors_match.group(1).strip()
            tv_info["actors"] = [a.strip() for a in re.split(r'[,，、/;；]', actors_str) if a.strip()]
        
        if not tv_info.get("title"):
            tv_info["title"] = title
        
        return tv_info
    
    def _get_page_source(self, url: str, site) -> Optional[str]:
        """获取页面源码"""
        try:
            ret = RequestUtils(
                cookies=site.cookie,
                timeout=30,
            ).get_res(url, allow_redirects=True)
            
            if ret is None:
                return None
            
            raw_data = ret.content
            if not raw_data:
                return ret.text
            
            result = chardet.detect(raw_data)
            encoding = result['encoding'] or 'utf-8'
            return raw_data.decode(encoding, errors='ignore')
            
        except Exception as e:
            logger.error(f"获取页面失败 {url}: {e}")
            return None
    
    def _crop_poster(self, poster_path: Path, cover_conf: str):
        """裁剪海报"""
        if not poster_path.exists():
            return
        
        try:
            image = Image.open(poster_path)
            
            if cover_conf and cover_conf != "None":
                try:
                    parts = cover_conf.split(":")
                    if len(parts) == 2:
                        target_ratio = int(parts[0]) / int(parts[1])
                    else:
                        target_ratio = 2 / 3
                except (ValueError, ZeroDivisionError):
                    target_ratio = 2 / 3
            else:
                target_ratio = 2 / 3
            
            original_ratio = image.width / image.height
            
            if original_ratio > target_ratio:
                new_width = int(image.height * target_ratio)
                left = (image.width - new_width) // 2
                right = left + new_width
                cropped = image.crop((left, 0, right, image.height))
            else:
                new_height = int(image.width / target_ratio)
                top = (image.height - new_height) // 2
                bottom = top + new_height
                cropped = image.crop((0, top, image.width, bottom))
            
            cropped.save(poster_path)
            logger.info(f"📷 海报已裁剪: {poster_path.name}")
            
        except Exception as e:
            logger.error(f"裁剪海报失败: {e}")
    
    def _download_image(self, url: str, file_path: Path) -> bool:
        """下载图片"""
        try:
            if 'doubanio.com' in url:
                return self._download_douban_image(url, file_path)
            
            r = RequestUtils().get_res(url=url, raise_exception=True)
            if r and r.status_code == 200:
                file_path.write_bytes(r.content)
                return True
            else:
                logger.warning(f"图片下载失败: {getattr(r, 'status_code', 'N/A')}")
                return False
                
        except Exception as e:
            logger.error(f"图片下载异常: {e}")
            return False
    
    def _download_douban_image(self, url: str, file_path: Path) -> bool:
        """下载豆瓣图片"""
        match = re.search(r'/public/(p\d+\.webp)', url)
        if not match:
            return False
        photo_id = match.group(1)
        
        for size in ['l', 'm', 's']:
            try_url = f"https://img1.doubanio.com/view/photo/{size}/public/{photo_id}"
            try:
                r = RequestUtils().get_res(url=try_url, raise_exception=True)
                if r and r.status_code == 200:
                    file_path.write_bytes(r.content)
                    return True
            except Exception:
                continue
        
        logger.warning(f"豆瓣图片所有尺寸均下载失败: {url}")
        return False
    
    def _gen_tv_nfo_file(self, dir_path: Path, title: str):
        """生成基础NFO"""
        doc = minidom.Document()
        root = DomUtils.add_node(doc, doc, "tvshow")
        DomUtils.add_node(doc, root, "title", title)
        DomUtils.add_node(doc, root, "originaltitle", title)
        DomUtils.add_node(doc, root, "season", "-1")
        DomUtils.add_node(doc, root, "episode", "-1")
        self._save_nfo(doc, dir_path / "tvshow.nfo")
    
    def _gen_tv_nfo_with_douban(self, dir_path: Path, mediainfo: MediaInfo):
        """使用豆瓣/TMDB信息生成NFO"""
        logger.info(f"正在使用 {mediainfo.source} 信息生成NFO：{dir_path.name}")
        doc = minidom.Document()
        root = DomUtils.add_node(doc, doc, "tvshow")
        
        DomUtils.add_node(doc, root, "title", mediainfo.title or "")
        DomUtils.add_node(doc, root, "originaltitle", mediainfo.original_title or mediainfo.title or "")
        
        if mediainfo.year:
            DomUtils.add_node(doc, root, "year", str(mediainfo.year))
        if mediainfo.overview:
            DomUtils.add_node(doc, root, "plot", mediainfo.overview)
        
        if mediainfo.production_countries:
            for country in mediainfo.production_countries:
                if isinstance(country, dict):
                    DomUtils.add_node(doc, root, "country", country.get("name", ""))
                else:
                    DomUtils.add_node(doc, root, "country", str(country))
        
        if mediainfo.genres:
            for genre in mediainfo.genres:
                if isinstance(genre, dict):
                    DomUtils.add_node(doc, root, "genre", genre.get("name", ""))
                else:
                    DomUtils.add_node(doc, root, "genre", str(genre))
        
        if mediainfo.vote_average:
            DomUtils.add_node(doc, root, "rating", str(mediainfo.vote_average))
        
        has_default = False
        
        if hasattr(mediainfo, 'tmdb_id') and mediainfo.tmdb_id:
            node = DomUtils.add_node(doc, root, "uniqueid", str(mediainfo.tmdb_id))
            node.setAttribute("type", "tmdb")
            if not has_default:
                node.setAttribute("default", "true")
                has_default = True
        
        if hasattr(mediainfo, 'douban_id') and mediainfo.douban_id:
            node = DomUtils.add_node(doc, root, "uniqueid", mediainfo.douban_id)
            node.setAttribute("type", "douban")
            if not has_default:
                node.setAttribute("default", "true")
                has_default = True
        
        if hasattr(mediainfo, 'actors') and mediainfo.actors:
            for actor in mediainfo.actors:
                if isinstance(actor, dict):
                    actor_name = actor.get("name", "")
                else:
                    actor_name = str(actor)
                if actor_name:
                    DomUtils.add_node(doc, root, "actor", actor_name)
        
        DomUtils.add_node(doc, root, "season", "1")
        DomUtils.add_node(doc, root, "episode", "-1")
        
        self._save_nfo(doc, dir_path / "tvshow.nfo")
    
    def _gen_tv_nfo_with_pt(self, dir_path: Path, tv_info: Dict):
        """使用PT站信息生成NFO"""
        doc = minidom.Document()
        root = DomUtils.add_node(doc, doc, "tvshow")
        
        title = tv_info.get("title", dir_path.name)
        DomUtils.add_node(doc, root, "title", title)
        DomUtils.add_node(doc, root, "originaltitle", title)
        
        if tv_info.get("year"):
            DomUtils.add_node(doc, root, "year", tv_info["year"])
        if tv_info.get("overview"):
            DomUtils.add_node(doc, root, "plot", tv_info["overview"])
        if tv_info.get("country"):
            DomUtils.add_node(doc, root, "country", tv_info["country"])
        if tv_info.get("genre"):
            DomUtils.add_node(doc, root, "genre", tv_info["genre"])
        if tv_info.get("source"):
            DomUtils.add_node(doc, root, "source", tv_info["source"])
        
        DomUtils.add_node(doc, root, "season", "1")
        DomUtils.add_node(doc, root, "episode", "-1")
        
        self._save_nfo(doc, dir_path / "tvshow.nfo")
    
    def _save_nfo(self, doc, file_path: Path):
        """保存NFO"""
        xml_str = doc.toprettyxml(indent="  ", encoding="utf-8")
        file_path.write_bytes(xml_str)
        logger.info(f"NFO文件已保存: {file_path.name}")
    
    def _add_actors_to_nfo(self, nfo_path: Path, actors: List[str]):
        """添加演员到NFO"""
        if not nfo_path.exists() or not actors:
            return
        
        try:
            tree = ET.parse(nfo_path)
            root = tree.getroot()
            
            existing_actors = set()
            for actor_elem in root.findall("actor"):
                name_elem = actor_elem.find("name")
                if name_elem is not None and name_elem.text:
                    existing_actors.add(name_elem.text.strip())
            
            added = 0
            for actor in actors:
                if actor and actor not in existing_actors:
                    actor_elem = ET.SubElement(root, "actor")
                    name_elem = ET.SubElement(actor_elem, "name")
                    name_elem.text = actor
                    added += 1
            
            if added:
                tree.write(nfo_path, encoding="utf-8", xml_declaration=True)
                logger.debug(f"已将 {added} 个演员添加到 NFO")
                
        except Exception as e:
            logger.error(f"添加演员失败: {e}")
    
    def _sync_actors_to_tags(self, nfo_path: Path):
        """同步演员到tag"""
        if not nfo_path.exists():
            return
        
        try:
            tree = ET.parse(nfo_path)
            root = tree.getroot()
            
            actors = []
            for actor_elem in root.findall("actor"):
                name_elem = actor_elem.find("name")
                if name_elem is not None and name_elem.text:
                    actors.append(name_elem.text.strip())
            
            if not actors:
                return
            
            existing_tags = set()
            for tag in root.findall("tag"):
                if tag.text:
                    existing_tags.add(tag.text.strip())
            
            added = 0
            for actor in actors:
                if actor not in existing_tags:
                    tag = ET.SubElement(root, "tag")
                    tag.text = actor
                    added += 1
            
            if added:
                tree.write(nfo_path, encoding="utf-8", xml_declaration=True)
                logger.debug(f"已将 {added} 个演员同步到 tag")
                
        except Exception as e:
            logger.error(f"同步演员到 tag 失败: {e}")
    
    def _crop_all_posters(self):
        """批量裁剪所有海报 - 只有开启裁剪开关时才执行"""
        if not self._image:
            return
        
        if not self._dirconf:
            return
        
        logger.info("开始批量裁剪封面...")
        for source_dir, cover_conf in self._coverconf.items():
            target_dir = self._dirconf.get(source_dir)
            if not target_dir:
                continue
            
            target_path = Path(target_dir)
            if not target_path.exists():
                continue
            
            for poster_path in target_path.rglob("poster.jpg"):
                try:
                    image = Image.open(poster_path)
                    current_ratio = image.width / image.height
                    
                    if cover_conf and cover_conf != "None":
                        parts = cover_conf.split(":")
                        if len(parts) == 2:
                            target_ratio = int(parts[0]) / int(parts[1])
                        else:
                            continue
                    else:
                        continue
                    
                    if abs(current_ratio - target_ratio) > 0.01:
                        self._crop_poster(poster_path, cover_conf)
                        
                except Exception as e:
                    logger.debug(f"裁剪失败 {poster_path}: {e}")
        
        logger.info("批量裁剪封面完成！")
    
    def _is_valid_folder(self, folder_path: str, source_dir: str) -> bool:
        """检查是否为有效的剧集文件夹"""
        try:
            source_path = Path(source_dir).resolve()
            folder_path_obj = Path(folder_path).resolve()
            
            try:
                relative = folder_path_obj.relative_to(source_path)
            except ValueError:
                return False
            
            parts = relative.parts
            if len(parts) != 1:
                return False
            
            folder_name = parts[0]
            if folder_name.startswith('.'):
                return False
            if folder_name in SYSTEM_FOLDERS:
                return False
            
            return True
        except Exception:
            return False
    
    def _should_exclude(self, path: str) -> bool:
        """检查路径是否应该被排除"""
        for folder in SYSTEM_FOLDERS:
            if f"/{folder}/" in path or f"\\{folder}\\" in path:
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
    
    def _sanitize_filename(self, filename: str) -> str:
        """清理非法字符"""
        return re.sub(r'[\\/*?:"<>|]', '', filename).strip('. ')
    
    # ========== 记录和统计 ==========
    
    def _record_success(self, file_path: str, title: str, target_path: str):
        """记录成功"""
        with self._lock:
            record = ProcessRecord(
                file_path=file_path,
                title=title,
                target_path=target_path,
                status=ProcessStatus.SUCCESS,
                timestamp=datetime.datetime.now()
            )
            self._success_cache[file_path] = record
            
            while len(self._success_cache) > MAX_CACHE_SIZE:
                self._success_cache.popitem(last=False)
    
    def _record_failure(self, file_path: str, error_msg: str):
        """记录失败"""
        with self._lock:
            record = ProcessRecord(
                file_path=file_path,
                title="",
                target_path="",
                status=ProcessStatus.FAILED,
                timestamp=datetime.datetime.now(),
                error_msg=error_msg
            )
            self._failed_records.append(record)
            
            if len(self._failed_records) > MAX_CACHE_SIZE:
                self._failed_records.pop(0)
            
            self._stats['total_processed'] += 1
            self._stats['failed_count'] += 1
    
    def _add_to_notify(self, title: str, file_path: str):
        """添加到通知队列"""
        with self._lock:
            data = self._medias.get(title, {})
            files = data.get("files", [])
            if file_path not in files:
                files.append(file_path)
            self._medias[title] = {"files": files, "time": datetime.datetime.now()}
    
    def _send_notifications(self):
        """发送通知"""
        if not self._notify:
            return
        
        with self._lock:
            if not self._medias:
                return
            
            for title, data in list(self._medias.items()):
                if (datetime.datetime.now() - data["time"]).total_seconds() > self._interval:
                    self.post_message(
                        mtype=NotificationType.Organize,
                        title=f"{title} 已入库",
                        text=f"共 {len(data['files'])} 个文件\n转移方式: {self._transfer_type.value}"
                    )
                    del self._medias[title]
    
    def _update_config(self):
        """更新配置"""
        self.update_config({
            "enabled": self._enabled,
            "onlyonce": False,
            "monitor_confs": self._monitor_confs,
            "transfer_type": self._transfer_type.value,
            "exclude_keywords": self._exclude_keywords,
            "notify": self._notify,
            "interval": self._interval,
            "scan_interval": self._scan_interval,
            "scan_enabled": self._scan_enabled,
            "image": self._image,
            "enable_local_nfo": self._enable_local_nfo,
            "enable_mp_recognition": self._enable_mp_recognition,
            "enable_pt_search": self._enable_pt_search
        })
    
    def _clear_cache(self):
        """清空缓存"""
        with self._lock:
            self._success_cache.clear()
            self._series_cache.clear()
            self._processing_files.clear()
            self._failed_records.clear()
            logger.info("缓存已清空")
    
    def _get_stats(self) -> Dict:
        """获取统计信息"""
        with self._lock:
            stats = self._stats.copy()
            stats['cache_size'] = len(self._success_cache)
            stats['series_cache_size'] = len(self._series_cache)
            stats['processing_count'] = len(self._processing_files)
            stats['failed_count'] = len(self._failed_records)
            return stats
    
    # ========== 命令处理 ==========
    
    def show_stats(self, args: List[str] = None) -> str:
        """显示统计信息"""
        stats = self._get_stats()
        return f"""
📊 短剧处理器统计
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
总处理: {stats['total_processed']}
成功: {stats['success_count']}
失败: {stats['failed_count']}
缓存大小: {stats['cache_size']}
系列缓存: {stats['series_cache_size']}
处理中: {stats['processing_count']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        """
    
    def clear_cache(self, args: List[str] = None) -> str:
        """清空缓存"""
        self._clear_cache()
        return "✅ 缓存已清空"
    
    def force_scan(self, args: List[str] = None) -> str:
        """强制扫描"""
        self.scan_all_dirs()
        return "✅ 扫描已启动"
    
    # ========== 事件处理 ==========
    
    def event_handler(self, event, source_dir: str, event_path: str):
        """处理文件变化事件"""
        if self._should_exclude(event_path):
            return
        
        if Path(event_path).suffix.lower() not in settings.RMT_MEDIAEXT:
            return
        
        logger.info(f"📹 检测到文件: {Path(event_path).name}")
        self._process_file_with_retry(event_path, source_dir)
    
    # ========== 插件接口 ==========
    
    def get_state(self) -> bool:
        return self._enabled
    
    def get_command(self) -> List[Dict[str, Any]]:
        return [
            {
                "cmd": "/shortplay_stats",
                "func": self.show_stats,
                "desc": "查看统计信息"
            },
            {
                "cmd": "/shortplay_clear",
                "func": self.clear_cache,
                "desc": "清空缓存"
            },
            {
                "cmd": "/shortplay_scan",
                "func": self.force_scan,
                "desc": "立即扫描"
            }
        ]
    
    def get_api(self) -> List[Dict[str, Any]]:
        return []
    
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
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [{"component": "VSwitch", "props": {"model": "image", "label": "封面裁剪"}}]
                            }
                        ]
                    },
                    # ========== 数据源配置行 ==========
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {"component": "VCard", "props": {"variant": "tonal", "color": "primary", "class": "mt-2"}, "content": [
                                        {"component": "VCardTitle", "text": "🔍 数据源配置"},
                                        {"component": "VCardText", "content": [
                                            {"component": "VRow", "content": [
                                                {
                                                    "component": "VCol",
                                                    "props": {"cols": 12, "md": 4},
                                                    "content": [{"component": "VSwitch", "props": {"model": "enable_local_nfo", "label": "📁 本地NFO识别", "hint": "优先读取源目录中的 tvshow.nfo"}}]
                                                },
                                                {
                                                    "component": "VCol",
                                                    "props": {"cols": 12, "md": 4},
                                                    "content": [{"component": "VSwitch", "props": {"model": "enable_mp_recognition", "label": "🎬 MP识别（豆瓣/TMDB）", "hint": "使用MoviePilot识别接口"}}]
                                                },
                                                {
                                                    "component": "VCol",
                                                    "props": {"cols": 12, "md": 4},
                                                    "content": [{"component": "VSwitch", "props": {"model": "enable_pt_search", "label": "🌐 PT站点搜索", "hint": "从AGSV/萝莉站/PTSKit搜索"}}]
                                                }
                                            ]}
                                        ]}
                                    ]}
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
                                "content": [{"component": "VSelect", "props": {"model": "transfer_type", "label": "转移方式", "items": [
                                    {"title": "移动", "value": "move"}, {"title": "复制", "value": "copy"},
                                    {"title": "硬链接", "value": "link"}, {"title": "软链接", "value": "softlink"}
                                ]}}]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [{"component": "VTextField", "props": {"model": "interval", "label": "通知延迟（秒）", "placeholder": "10"}}]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [{"component": "VTextField", "props": {"model": "scan_interval", "label": "扫描间隔（秒）", "placeholder": "60"}}]
                            },
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
                                "content": [{"component": "VTextarea", "props": {"model": "monitor_confs", "label": "监控目录", "rows": 4, 
                                    "placeholder": "auto#/源目录#/目的目录#smart#16:9\n格式: 监控方式#源目录#目的目录#重命名#封面比例\n重命名: false/smart"}}]
                            }
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [{"component": "VTextarea", "props": {"model": "exclude_keywords", "label": "排除关键词", "rows": 2, 
                                    "placeholder": "每行一个关键词（支持正则表达式）"}}]
                            }
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [{"component": "VAlert", "props": {"type": "info", "variant": "tonal", 
                                    "text": "数据优先级：本地NFO > MP识别 > PT站搜索 > 基础信息。可关闭任意数据源。"}}]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": False, "onlyonce": False, "monitor_confs": "", "transfer_type": "link",
            "exclude_keywords": "", "notify": False, "interval": 10, "scan_interval": 60,
            "scan_enabled": True, "image": False,
            "enable_local_nfo": True,
            "enable_mp_recognition": True,
            "enable_pt_search": True
        }
    
    def get_page(self) -> List[dict]:
        """获取页面数据"""
        stats = self._get_stats()
        
        with self._lock:
            # 按时间排序（最新在前），只取最近 MAX_DISPLAY_CACHE 条
            sorted_cache = sorted(
                self._series_cache.items(),
                key=lambda x: x[1].timestamp,
                reverse=True
            )[:MAX_DISPLAY_CACHE]
            
            # 按来源分类系列缓存
            cache_by_type = {
                "system": [],   # 系统识别（豆瓣/TMDB）
                "pt": [],       # PT识别
                "local": []     # 本地识别（本地NFO/文件夹名）
            }
            
            for cache_key, cache_entry in sorted_cache:
                # 处理后的剧集名（目标文件夹名）
                recognized_name = cache_entry.title if cache_entry.title else "未知"
                # 原始文件夹名
                original_folder = Path(cache_key).name if cache_key else "未知"
                
                # 获取处理文件列表（目标文件名）
                processed_files = []
                for record in self._success_cache.values():
                    if record.title == recognized_name or original_folder in record.file_path:
                        target_name = Path(record.target_path).name if record.target_path else ""
                        if target_name:
                            processed_files.append(target_name)
                
                file_count = len(processed_files)
                
                # 显示处理文件：超过5个显示 "S01E01等66个文件"
                if file_count == 0:
                    file_display = "待处理"
                elif file_count <= 5:
                    file_display = "\n".join(processed_files)
                else:
                    first_file = processed_files[0] if processed_files else ""
                    file_display = f"{first_file}等{file_count}个文件"
                
                # 判断来源类型
                if cache_entry.mediainfo:
                    source = getattr(cache_entry.mediainfo, 'source', '')
                    if source == 'douban':
                        cache_by_type["system"].append({
                            "name": recognized_name[:30],
                            "folder": original_folder[:30],
                            "source": "豆瓣",
                            "files": file_display,
                            "count": file_count
                        })
                    elif source == 'themoviedb':
                        cache_by_type["system"].append({
                            "name": recognized_name[:30],
                            "folder": original_folder[:30],
                            "source": "TMDB",
                            "files": file_display,
                            "count": file_count
                        })
                    elif source == 'local':
                        cache_by_type["local"].append({
                            "name": recognized_name[:30],
                            "folder": original_folder[:30],
                            "source": "本地NFO",
                            "files": file_display,
                            "count": file_count
                        })
                    else:
                        cache_by_type["local"].append({
                            "name": recognized_name[:30],
                            "folder": original_folder[:30],
                            "source": "其他",
                            "files": file_display,
                            "count": file_count
                        })
                elif cache_entry.pt_tv_info:
                    pt_source = cache_entry.pt_tv_info.get('source', 'PT站')
                    cache_by_type["pt"].append({
                        "name": recognized_name[:30],
                        "folder": original_folder[:30],
                        "source": pt_source,
                        "files": file_display,
                        "count": file_count
                    })
                else:
                    cache_by_type["local"].append({
                        "name": recognized_name[:30],
                        "folder": original_folder[:30],
                        "source": "文件夹名",
                        "files": file_display,
                        "count": file_count
                    })
            
            # 按文件数量排序（处理文件多的排在前面）
            for key in cache_by_type:
                cache_by_type[key].sort(key=lambda x: x.get("count", 0), reverse=True)
            
            # 构建三大类缓存表格
            cache_cards = []
            
            # 系统识别卡片
            if cache_by_type["system"]:
                rows = []
                for item in cache_by_type["system"][:20]:
                    rows.append({"component": "tr", "content": [
                        {"component": "td", "text": item["name"]},
                        {"component": "td", "text": item["folder"]},
                        {"component": "td", "text": item["source"]},
                        {"component": "td", "props": {"style": "white-space: pre-line;"}, "text": item["files"]}
                    ]})
                cache_cards.append({
                    "component": "VCard",
                    "props": {"class": "mt-4", "variant": "tonal", "color": "info"},
                    "content": [
                        {"component": "VCardTitle", "text": f"🤖 系统识别（豆瓣/TMDB） - {len(cache_by_type['system'])} 个"},
                        {"component": "VCardText", "props": {"class": "pa-0"}, "content": [
                            {"component": "VTable", "props": {"hover": True, "dense": True}, "content": [
                                {"component": "thead", "content": [
                                    {"component": "tr", "content": [
                                        {"component": "th", "text": "剧集名"},
                                        {"component": "th", "text": "原始文件夹"},
                                        {"component": "th", "text": "来源"},
                                        {"component": "th", "text": "处理文件"}
                                    ]}
                                ]},
                                {"component": "tbody", "content": rows}
                            ]}
                        ]}
                    ]
                })
            
            # PT识别卡片
            if cache_by_type["pt"]:
                rows = []
                for item in cache_by_type["pt"][:20]:
                    rows.append({"component": "tr", "content": [
                        {"component": "td", "text": item["name"]},
                        {"component": "td", "text": item["folder"]},
                        {"component": "td", "text": item["source"]},
                        {"component": "td", "props": {"style": "white-space: pre-line;"}, "text": item["files"]}
                    ]})
                cache_cards.append({
                    "component": "VCard",
                    "props": {"class": "mt-4", "variant": "tonal", "color": "warning"},
                    "content": [
                        {"component": "VCardTitle", "text": f"🌐 PT识别（AGSV/萝莉站/PTSKit） - {len(cache_by_type['pt'])} 个"},
                        {"component": "VCardText", "props": {"class": "pa-0"}, "content": [
                            {"component": "VTable", "props": {"hover": True, "dense": True}, "content": [
                                {"component": "thead", "content": [
                                    {"component": "tr", "content": [
                                        {"component": "th", "text": "剧集名"},
                                        {"component": "th", "text": "原始文件夹"},
                                        {"component": "th", "text": "来源"},
                                        {"component": "th", "text": "处理文件"}
                                    ]}
                                ]},
                                {"component": "tbody", "content": rows}
                            ]}
                        ]}
                    ]
                })
            
            # 本地识别卡片
            if cache_by_type["local"]:
                rows = []
                for item in cache_by_type["local"][:20]:
                    rows.append({"component": "tr", "content": [
                        {"component": "td", "text": item["name"]},
                        {"component": "td", "text": item["folder"]},
                        {"component": "td", "text": item["source"]},
                        {"component": "td", "props": {"style": "white-space: pre-line;"}, "text": item["files"]}
                    ]})
                cache_cards.append({
                    "component": "VCard",
                    "props": {"class": "mt-4", "variant": "tonal", "color": "success"},
                    "content": [
                        {"component": "VCardTitle", "text": f"💾 本地识别（本地NFO/文件夹名） - {len(cache_by_type['local'])} 个"},
                        {"component": "VCardText", "props": {"class": "pa-0"}, "content": [
                            {"component": "VTable", "props": {"hover": True, "dense": True}, "content": [
                                {"component": "thead", "content": [
                                    {"component": "tr", "content": [
                                        {"component": "th", "text": "剧集名"},
                                        {"component": "th", "text": "原始文件夹"},
                                        {"component": "th", "text": "来源"},
                                        {"component": "th", "text": "处理文件"}
                                    ]}
                                ]},
                                {"component": "tbody", "content": rows}
                            ]}
                        ]}
                    ]
                })
            
            # 失败记录
            failed_rows = []
            
            # 处理失败记录
            for record in self._failed_records[-20:]:
                name = Path(record.file_path).name if record.file_path else "未知"
                error_msg = record.error_msg[:50] if record.error_msg else "未知错误"
                failed_rows.append({"component": "tr", "content": [
                    {"component": "td", "text": name[:50]},
                    {"component": "td", "text": error_msg},
                    {"component": "td", "text": record.timestamp.strftime("%Y-%m-%d %H:%M:%S")}
                ]})
            
            # 识别失败记录
            for cache_key, cache_entry in self._series_cache.items():
                if not cache_entry.mediainfo and not cache_entry.pt_tv_info:
                    folder_name = Path(cache_key).name if cache_key else "未知"
                    cache_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(cache_entry.timestamp))
                    failed_rows.append({"component": "tr", "content": [
                        {"component": "td", "text": folder_name[:50]},
                        {"component": "td", "text": "未匹配到任何来源"},
                        {"component": "td", "text": cache_time}
                    ]})
            
            # 去重
            seen = set()
            unique_failed_rows = []
            for row in failed_rows:
                key = f"{row['content'][0]['text']}_{row['content'][2]['text']}"
                if key not in seen:
                    seen.add(key)
                    unique_failed_rows.append(row)
            
            failed_card = {
                "component": "VCard",
                "props": {"class": "mt-4", "variant": "tonal", "color": "error"},
                "content": [
                    {"component": "VCardTitle", "text": f"❌ 失败记录 - 共 {len(unique_failed_rows)} 条"},
                    {"component": "VCardText", "props": {"class": "pa-0"}, "content": [
                        {"component": "VTable", "props": {"hover": True, "dense": True}, "content": [
                            {"component": "thead", "content": [
                                {"component": "tr", "content": [
                                    {"component": "th", "text": "文件/文件夹名"},
                                    {"component": "th", "text": "错误信息"},
                                    {"component": "th", "text": "时间"}
                                ]}
                            ]},
                            {"component": "tbody", "content": unique_failed_rows[:20] if unique_failed_rows else [
                                {"component": "tr", "content": [
                                    {"component": "td", "props": {"colspan": 3, "class": "text-center"}, "text": "暂无失败记录"}
                                ]}
                            ]}
                        ]}
                    ]}
                ]
            }
        
        return [
            # 统计卡片（5个）
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 2, "sm": 4},
                        "content": [
                            {"component": "VCard", "props": {"variant": "tonal", "color": "primary"}, "content": [
                                {"component": "VCardText", "props": {"class": "text-center"}, "content": [
                                    {"component": "div", "props": {"class": "text-h4"}, "text": str(stats['total_processed'])},
                                    {"component": "div", "text": "总处理"}
                                ]}
                            ]}
                        ]
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 2, "sm": 4},
                        "content": [
                            {"component": "VCard", "props": {"variant": "tonal", "color": "success"}, "content": [
                                {"component": "VCardText", "props": {"class": "text-center"}, "content": [
                                    {"component": "div", "props": {"class": "text-h4"}, "text": str(stats['success_count'])},
                                    {"component": "div", "text": "成功"}
                                ]}
                            ]}
                        ]
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 2, "sm": 4},
                        "content": [
                            {"component": "VCard", "props": {"variant": "tonal", "color": "error"}, "content": [
                                {"component": "VCardText", "props": {"class": "text-center"}, "content": [
                                    {"component": "div", "props": {"class": "text-h4"}, "text": str(stats['failed_count'])},
                                    {"component": "div", "text": "失败"}
                                ]}
                            ]}
                        ]
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 3, "sm": 6},
                        "content": [
                            {"component": "VCard", "props": {"variant": "tonal", "color": "info"}, "content": [
                                {"component": "VCardText", "props": {"class": "text-center"}, "content": [
                                    {"component": "div", "props": {"class": "text-h4"}, "text": str(stats['series_cache_size'])},
                                    {"component": "div", "text": "系列缓存"}
                                ]}
                            ]}
                        ]
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 3, "sm": 6},
                        "content": [
                            {"component": "VCard", "props": {"variant": "tonal", "color": "warning"}, "content": [
                                {"component": "VCardText", "props": {"class": "text-center"}, "content": [
                                    {"component": "div", "props": {"class": "text-h4"}, "text": str(len(self._failed_records))},
                                    {"component": "div", "text": "失败记录"}
                                ]}
                            ]}
                        ]
                    }
                ]
            },
            # 三大类缓存卡片
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12},
                        "content": cache_cards if cache_cards else [
                            {"component": "VCard", "props": {"class": "mt-4"}, "content": [
                                {"component": "VCardText", "props": {"class": "text-center"}, "content": [
                                    {"component": "div", "text": "暂无系列缓存"}
                                ]}
                            ]}
                        ]
                    }
                ]
            },
            # 失败记录卡片
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12},
                        "content": [failed_card]
                    }
                ]
            }
        ]
    
    def stop_service(self):
        """停止服务"""
        if self._scheduler:
            try:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown(wait=False)
            except Exception as e:
                logger.debug(f"停止调度器失败: {e}")
            self._scheduler = None
        
        with self._lock:
            self._series_cache.clear()
            self._success_cache.clear()
            self._processing_files.clear()
            self._medias.clear()
            self._failed_records.clear()
        
        for observer in self._observer:
            try:
                observer.stop()
                observer.join(timeout=5)
            except Exception as e:
                logger.debug(f"停止监控器失败: {e}")
        self._observer = []
        
        logger.info("短剧处理器已停止")