import datetime
import json
import os
import re
import threading
import time
import xml.etree.ElementTree as ET
from collections import OrderedDict
from difflib import SequenceMatcher
from functools import wraps
from pathlib import Path
from threading import RLock
from typing import Any, List, Dict, Tuple, Optional
from xml.dom import minidom

import chardet
from apscheduler.triggers.interval import IntervalTrigger
from lxml import etree
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

from app.core.config import settings
from app.core.metainfo import MetaInfoPath
from app.core.event import eventmanager, Event
from app.db.site_oper import SiteOper
from app.helper.sites import SitesHelper
from app.log import logger
from app.modules.indexer.spider import SiteSpider
from app.plugins import _PluginBase
from app.schemas import MediaInfo
from app.schemas.types import EventType, NotificationType
from app.utils.dom import DomUtils
from app.utils.http import RequestUtils
from app.utils.system import SystemUtils

# ========== 常量 ==========
MAX_CACHE_SIZE = 1000
MAX_RETRIES = 3
RETRY_DELAY = 1
CACHE_TTL_SECONDS = 3600
FAILED_CACHE_TTL = 3600
FETCH_TIMEOUT = 30

SYSTEM_FOLDERS = {
    '@Recycle', '#recycle', '@eaDir', 'System Volume Information',
    '$RECYCLE.BIN', '.DS_Store', 'Thumbs.db'
}

TITLE_CLEAN_PATTERNS = [
    (re.compile(r'^\d+[-－—]\s*'), ''),
    (re.compile(r'\..*'), ''),
    (re.compile(r'[（(].*$'), ''),
    (re.compile(r'\[[^\]]+\]'), ''),
    (re.compile(r'[-–—_\s]+$'), ''),
]

EPISODE_PATTERNS = [
    re.compile(r'[eE][pP]?(\d{1,3})'),
    re.compile(r'第(\d+)集'),
]

FILENAME_CLEAN = re.compile(r'[\\/*?:"<>|]')

DEFAULT_SITES = [
    {
        "domain": "agsvpt.com",
        "name": "AGSV",
        "search_url": "https://www.agsvpt.com/torrents.php?search_mode=0&search_area=0&page=0&notnewword=1&cat=419&search={title}",
        "fields": {
            "title_index": 1,      # 片名所在索引
            "year_index": 2,       # 年代所在索引
            "country_index": 3,    # 产地所在索引
            "genre_index": 4,      # 类别所在索引
            "overview_index": 6    # 简介所在索引
        }
    },
    {
        "domain": "ilolicon.com",
        "name": "萝莉站",
        "search_url": "https://share.ilolicon.com/torrents.php?search_mode=0&search_area=0&page=0&notnewword=1&cat=402&search={title}",
        "fields": {
            "title_index": 0,
            "year_index": 1,
            "country_index": 2,
            "genre_index": 3,
            "actors_index": 4,
            "overview_index": 6
        }
    },
    {
        "domain": "ptskit.org",
        "name": "PTSKit",
        "search_url": "https://www.ptskit.org/torrents.php?search_mode=0&search_area=0&page=0&notnewword=1&tag_id=238&search={title}",
        "fields": {
            "title_index": 1,
            "genre_index": 2,
            "actors_index": 4,
            "overview_index": 6
        }
    }
]


def log_method(log_args: bool = True, log_result: bool = False):
    """方法日志装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            method_name = func.__name__
            logger.debug(f"[日志] >>> 进入方法: {method_name}")
            
            if log_args and args:
                # 截断过长的参数
                safe_args = []
                for arg in args:
                    if isinstance(arg, str) and len(arg) > 100:
                        safe_args.append(arg[:100] + "...")
                    else:
                        safe_args.append(arg)
                logger.debug(f"[日志] 参数: {safe_args}")
            
            if log_args and kwargs:
                safe_kwargs = {}
                for k, v in kwargs.items():
                    if isinstance(v, str) and len(v) > 100:
                        safe_kwargs[k] = v[:100] + "..."
                    else:
                        safe_kwargs[k] = v
                logger.debug(f"[日志] 关键字参数: {safe_kwargs}")
            
            start_time = time.time()
            try:
                result = func(self, *args, **kwargs)
                elapsed = (time.time() - start_time) * 1000
                
                if log_result:
                    logger.debug(f"[日志] <<< 方法完成: {method_name} (耗时: {elapsed:.2f}ms)")
                else:
                    logger.debug(f"[日志] <<< 方法完成: {method_name} (耗时: {elapsed:.2f}ms)")
                return result
            except Exception as e:
                elapsed = (time.time() - start_time) * 1000
                logger.error(f"[日志] ❌ 方法异常: {method_name} (耗时: {elapsed:.2f}ms) - {e}", exc_info=True)
                raise
        return wrapper
    return decorator


def log_step(step_name: str):
    """步骤日志装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            logger.info(f"[步骤] 🔸 {step_name} - 开始")
            start_time = time.time()
            try:
                result = func(self, *args, **kwargs)
                elapsed = (time.time() - start_time) * 1000
                logger.info(f"[步骤] ✅ {step_name} - 完成 (耗时: {elapsed:.2f}ms)")
                return result
            except Exception as e:
                elapsed = (time.time() - start_time) * 1000
                logger.error(f"[步骤] ❌ {step_name} - 失败 (耗时: {elapsed:.2f}ms): {e}", exc_info=True)
                raise
        return wrapper
    return decorator


class FileMonitorHandler(FileSystemEventHandler):
    """文件监控处理器"""
    def __init__(self, plugin, source_dir, max_wait=10.0):
        super().__init__()
        self.plugin = plugin
        self.source_dir = source_dir
        self.max_wait = max_wait
        self._pending = set()
        self._title_mapping: Dict[str, str] = {}  # 原始文件夹名 -> 最终标题的映射
        logger.debug(f"[监控] 初始化监控处理器: {source_dir}, 防抖等待: {max_wait}s")

    def on_created(self, event):
        if not event.is_directory and self._is_video(event.src_path):
            logger.info(f"[监控] 检测到文件创建: {event.src_path}")
            self._handle(event.src_path)

    def on_moved(self, event):
        if not event.is_directory and self._is_video(event.dest_path):
            logger.info(f"[监控] 检测到文件移动: {event.src_path} -> {event.dest_path}")
            self._handle(event.dest_path)

    def _is_video(self, path: str) -> bool:
        suffix = Path(path).suffix.lower()
        is_video = suffix in settings.RMT_MEDIAEXT
        if is_video:
            logger.debug(f"[监控] 识别为视频文件: {path}")
        return is_video

    def _handle(self, path: str):
        if path in self._pending:
            logger.debug(f"[监控] 文件已在处理队列中，跳过: {path}")
            return
        self._pending.add(path)
        logger.debug(f"[监控] 加入处理队列: {path}, 当前队列: {len(self._pending)}")
        threading.Thread(target=self._delayed_process, args=(path,), daemon=True).start()

    def _delayed_process(self, path: str):
        try:
            logger.debug(f"[监控] 开始延迟处理: {path}")
            self._wait_stable(path)
            self._pending.discard(path)
            logger.info(f"[监控] 开始处理文件: {path}")
            self.plugin.process_file(path, self.source_dir)
        except Exception as e:
            logger.error(f"[监控] 处理异常 {path}: {e}", exc_info=True)
            self._pending.discard(path)

    def _wait_stable(self, path: str):
        """等待文件写入完成"""
        logger.debug(f"[监控] 等待文件稳定: {path}")
        last_size = -1
        stable_count = 0
        start = time.time()
        while time.time() - start < self.max_wait:
            try:
                size = os.path.getsize(path)
                if size == 0:
                    logger.debug(f"[监控] 文件大小为0，等待写入: {path}")
                    time.sleep(0.3)
                    continue
                if size == last_size:
                    stable_count += 1
                    if stable_count >= 2:
                        logger.debug(f"[监控] 文件已稳定，大小: {size} bytes")
                        return
                else:
                    stable_count = 0
                    last_size = size
                    logger.debug(f"[监控] 文件大小变化: {last_size} -> {size}")
            except (FileNotFoundError, OSError) as e:
                logger.debug(f"[监控] 文件访问异常: {e}")
                pass
            time.sleep(0.3)
        logger.debug(f"[监控] 等待超时，强制处理: {path}")


class ShortPlayProcessor(_PluginBase):
    """短剧处理器"""
    plugin_name = "短剧处理器"
    plugin_desc = "监控短剧目录，自动刮削元数据并整理到媒体库"
    plugin_icon = "Amule_B.png"
    plugin_version = "3.0.0"
    plugin_author = "thsrite,AI"
    author_url = "https://github.com/m216owen/MoviePilot-Plugins"
    plugin_config_prefix = "shortplayprocessor_"
    plugin_order = 26
    auth_level = 1

    def __init__(self):
        super().__init__()
        logger.debug("[初始化] 创建 ShortPlayProcessor 实例")
        self._enabled = False
        self._onlyonce = False
        self._supplement = False
        self._monitor_confs = ""
        self._transfer_type = "link"
        self._exclude_keywords = ""
        self._notify = False
        self._interval = 10
        self._scan_interval = 60
        self._scan_enabled = True

        self._enable_local_nfo = True
        self._enable_mp_recognition = True
        self._enable_pt_search = True
        self._pt_priority = ""

        self._polling_interval = 5
        self._debounce_max_wait = 10.0
        self._enable_incremental_scan = True
        self._media_root = ""

        self._dirconf: Dict[str, str] = {}
        self._renameconf: Dict[str, str] = {}

        # 缓存
        self._success_cache: OrderedDict = OrderedDict()
        self._series_cache: OrderedDict = OrderedDict()
        self._failed_records: List[dict] = []

        # 运行时状态
        self._lock = RLock()
        self._processing_files: set = set()
        self._medias: Dict[str, dict] = {}
        self._scanning = False
        self._last_scan_time: Dict[str, float] = {}
        self._compiled_exclude_patterns: List[re.Pattern] = []

        # 统计
        self._stats = {
            'total_processed': 0, 'success_count': 0, 'failed_count': 0,
            'last_process_time': None, 'start_time': datetime.datetime.now(),
            'mp_calls': 0, 'mp_hits': 0, 'pt_calls': 0, 'pt_hits': 0, 'nfo_calls': 0, 'nfo_hits': 0,
        }

        self._observer = []
        self._site_cache: Dict[str, Any] = {}
        self._indexer_cache: Dict[str, Any] = {}

        self._pending_tasks: Dict[str, threading.Timer] = {}
        self._last_source = '-'
        self._sites_config = [s.copy() for s in DEFAULT_SITES]
        
        logger.debug("[初始化] 实例创建完成")

    # ========== 搜索方法 ==========

    @log_method(log_args=True, log_result=False)
    def search_pt(self, title: str) -> Optional[dict]:
        """PT站搜索 - 汇总多个站点结果"""
        if not self._enable_pt_search:
            logger.debug(f"[PT搜索] PT搜索已禁用，跳过 {title}")
            return None
        
        with self._lock:
            self._stats['pt_calls'] = self._stats.get('pt_calls', 0) + 1
        
        logger.info(f"[PT搜索] 🔍 开始搜索: {title}")
        
        # 汇总结果
        merged_result = None
        
        for idx, site_config in enumerate(DEFAULT_SITES):
            domain = site_config["domain"]
            logger.debug(f"[PT搜索] 尝试站点 #{idx+1}: {site_config['name']} ({domain})")

            site = SiteOper().get_by_domain(domain)
            if not site:
                logger.debug(f"[PT搜索] 站点未配置: {domain}")
                continue

            indexer = SitesHelper().get_indexer(domain)
            if not indexer:
                logger.debug(f"[PT搜索] 站点索引器不存在: {domain}")
                continue

            logger.info(f"[PT搜索] 请求站点: {site_config['name']} - {title}")

            try:
                search_url = site_config["search_url"].format(title=title)
                logger.debug(f"[PT搜索] 搜索URL: {search_url}")
                
                ret = RequestUtils(cookies=site.cookie, timeout=30).get_res(search_url, allow_redirects=True)
                if not ret:
                    logger.warning(f"[PT搜索] 请求失败: {site_config['name']}")
                    continue

                logger.debug(f"[PT搜索] 响应状态码: {ret.status_code}")
                page_source = ret.text
                logger.debug(f"[PT搜索] 响应内容长度: {len(page_source)} bytes")

                spider = SiteSpider(indexer=indexer, page=1)
                torrents = spider.parse(page_source)
                if not torrents:
                    logger.debug(f"[PT搜索] 未解析到种子: {site_config['name']}")
                    continue
                
                logger.debug(f"[PT搜索] 解析到 {len(torrents)} 个种子")

                detail_url = torrents[0].get("page_url")
                if not detail_url:
                    logger.debug(f"[PT搜索] 未获取到详情页URL")
                    continue

                logger.debug(f"[PT搜索] 详情页URL: {detail_url}")
                ret = RequestUtils(cookies=site.cookie, timeout=30).get_res(detail_url, allow_redirects=True)
                if not ret:
                    logger.warning(f"[PT搜索] 详情页请求失败")
                    continue

                detail_source = ret.text
                html = etree.HTML(detail_source)
                if html is None:
                    logger.debug(f"[PT搜索] HTML解析失败")
                    continue

                desc_elem = html.xpath("//*[@id='kdescr']")
                if not desc_elem:
                    logger.debug(f"[PT搜索] 未找到描述元素")
                    continue

                full_text = desc_elem[0].xpath("string()").strip()
                logger.debug(f"[PT识别] 描述文本长度: {len(full_text)}")

                poster_url = ""
                img_elements = html.xpath("//*[@id='kdescr']/img[1]/@src")
                if img_elements:
                    poster_url = str(img_elements[0])
                    logger.debug(f"[PT识别] 海报URL: {poster_url}")

                # 正则提取字段
                patterns = [
                    (r'片\s*名\s*[:：]?\s*([^\n]+)', 'title'),
                    (r'年\s*代\s*[:：]?\s*(\d{4})', 'year'),
                    (r'产\s*地\s*[:：]?\s*([^\n]+)', 'country'),
                    (r'类\s*别\s*[:：]?\s*([^\n]+)', 'genre'),
                    (r'主\s*演\s*[:：]?\s*([^\n]+)', 'actors'),
                    (r'简\s*介\s*[:：]?\s*\n?\s*([^\n]+)', 'overview'),
                ]
                
                result = {
                    "title": title,
                    "original_title": title,
                    "year": "",
                    "overview": "",
                    "genres": [],
                    "production_countries": [],
                    "actors": [],
                    "poster_path": poster_url,
                    "source": site_config['name']
                }
                
                # 执行正则匹配
                for pattern, field in patterns:
                    match = re.search(pattern, full_text, re.IGNORECASE)
                    if match:
                        value = match.group(1).strip()
                        if field == 'title':
                            result["title"] = value
                            result["original_title"] = value
                            logger.debug(f"[PT识别] 片名: {value}")
                        elif field == 'year':
                            result["year"] = value
                            logger.debug(f"[PT识别] 年代: {value}")
                        elif field == 'country':
                            result["production_countries"] = [value]
                            logger.debug(f"[PT识别] 产地: {value}")
                        elif field == 'genre':
                            genres = re.split(r'[/,、\s]+', value)
                            result["genres"] = [g.strip() for g in genres if g.strip()]
                            logger.debug(f"[PT识别] 类别: {value}")
                        elif field == 'actors':
                            actors = re.split(r'[/,、\s]+', value)
                            result["actors"] = [a.strip() for a in actors if a.strip()]
                            logger.debug(f"[PT识别] 主演: {value}")
                        elif field == 'overview':
                            result["overview"] = value
                            logger.debug(f"[PT识别] 简介: {value[:100]}...")

                if result.get("title"):
                    with self._lock:
                        self._stats['pt_hits'] = self._stats.get('pt_hits', 0) + 1
                    
                    # 合并结果
                    if merged_result is None:
                        merged_result = result
                        logger.info(f"[PT搜索] 初始化结果: {result['title']} (来源: {site_config['name']})")
                    else:
                        # 补充缺失的字段
                        if not merged_result.get("year") and result.get("year"):
                            merged_result["year"] = result["year"]
                            logger.debug(f"[PT搜索] 补充年份: {result['year']} (来自 {site_config['name']})")
                        
                        if not merged_result.get("overview") and result.get("overview"):
                            merged_result["overview"] = result["overview"]
                            logger.debug(f"[PT搜索] 补充简介 (来自 {site_config['name']})")
                        
                        if not merged_result.get("genres") and result.get("genres"):
                            merged_result["genres"] = result["genres"]
                            logger.debug(f"[PT搜索] 补充类型: {result['genres']} (来自 {site_config['name']})")
                        
                        if not merged_result.get("actors") and result.get("actors"):
                            merged_result["actors"] = result["actors"]
                            logger.debug(f"[PT搜索] 补充演员: {result['actors']} (来自 {site_config['name']})")
                        
                        if not merged_result.get("production_countries") and result.get("production_countries"):
                            merged_result["production_countries"] = result["production_countries"]
                            logger.debug(f"[PT搜索] 补充产地: {result['production_countries']} (来自 {site_config['name']})")
                        
                        # 来源信息累积
                        merged_result["source"] = f"{merged_result['source']} + {site_config['name']}"
                        
                        logger.info(f"[PT搜索] 合并结果，当前来源: {merged_result['source']}")
                    
                    # 如果有海报URL且当前没有，使用
                    if poster_url and not merged_result.get("poster_path"):
                        merged_result["poster_path"] = poster_url
                    
                    # 继续搜索其他站点，不返回
                else:
                    logger.debug(f"[PT搜索] 站点 {site_config['name']} 未解析到标题信息")

            except Exception as e:
                logger.error(f"[PT搜索] 异常: {e}", exc_info=True)
                continue

        if merged_result:
            logger.info(f"[PT搜索] ✅ 搜索完成，汇总来源: {merged_result['source']}")
            logger.debug(f"[PT识别] 完整数据: title={result['title']}, year={result['year']}, actors={result['actors']}")
            return merged_result
        else:
            logger.warning(f"[PT搜索] ❌ 所有站点搜索失败: {title}")
            return None

    @log_method(log_args=True, log_result=False)
    def search_mp(self, file_path: Path) -> Optional[dict]:
        """
        MP识别（豆瓣/TMDB）- 使用真实文件路径
        
        Args:
            file_path: 视频文件的真实路径
        
        Returns:
            返回 MediaInfo 字典，失败返回 None
        """
        if not self._enable_mp_recognition:
            logger.debug(f"[MP识别] MP识别已禁用，跳过 {file_path}")
            return None
        
        with self._lock:
            self._stats['mp_calls'] = self._stats.get('mp_calls', 0) + 1
        
        logger.info(f"[MP识别] 🔍 开始识别: {file_path}")
        
        if not file_path or not file_path.exists():
            logger.warning(f"[MP识别] 文件不存在: {file_path}")
            return None
        
        try:
            logger.debug(f"[MP识别] 创建 MetaInfoPath 对象")
            file_meta = MetaInfoPath(file_path)
            logger.info(f"[MP识别] 文件解析: name={file_meta.name}, season={file_meta.season}, episode={file_meta.episode}")
            
            logger.debug(f"[MP识别] 调用识别接口 chain.recognize_media")
            mediainfo = self.chain.recognize_media(meta=file_meta)
            
            if mediainfo and getattr(mediainfo, 'source', None) in ['douban', 'themoviedb']:
                result = {
                    "title": mediainfo.title,
                    "original_title": getattr(mediainfo, 'original_title', '') or getattr(mediainfo, 'original_name', '') or mediainfo.title,
                    "year": mediainfo.year or '',
                    "overview": getattr(mediainfo, 'overview', ''),
                    "genres": getattr(mediainfo, 'genres', []),
                    "production_countries": getattr(mediainfo, 'production_countries', []),
                    "actors": getattr(mediainfo, 'actors', []),
                    "poster_path": getattr(mediainfo, 'poster_path', ''),
                    "tmdb_id": getattr(mediainfo, 'tmdb_id', ''),
                    "douban_id": getattr(mediainfo, 'douban_id', ''),
                    "source": mediainfo.source
                }
                with self._lock:
                    self._stats['mp_hits'] = self._stats.get('mp_hits', 0) + 1
                logger.info(f"[MP识别] ✅ 识别成功: {result['title']} (来源: {result['source']}, 类型: {result.get('year', '未知年份')})")
                logger.debug(f"[MP识别] 完整数据: {result}")
                return result
            else:
                logger.warning(f"[MP识别] ❌ 未识别到有效结果 (mediainfo存在: {mediainfo is not None})")
                
        except Exception as e:
            logger.error(f"[MP识别] 异常: {e}", exc_info=True)
        
        return None

    @log_method(log_args=True, log_result=False)
    def search_local_nfo(self, title: str, source_dir: str) -> Optional[dict]:
        """本地NFO搜索"""
        if not self._enable_local_nfo:
            logger.debug(f"[本地NFO] 本地NFO已禁用，跳过 {title}")
            return None
        
        with self._lock:
            self._stats['nfo_calls'] = self._stats.get('nfo_calls', 0) + 1
        
        logger.info(f"[本地NFO] 🔍 开始搜索: {title}")

        try:
            source_folder = Path(source_dir) / title
            if not source_folder.exists():
                logger.debug(f"[本地NFO] 目录不存在: {source_folder}")
                return None

            nfo_file = source_folder / "tvshow.nfo"
            if not nfo_file.exists():
                logger.debug(f"[本地NFO] NFO文件不存在: {nfo_file}")
                return None

            logger.debug(f"[本地NFO] 读取NFO文件: {nfo_file}")
            mediainfo = self._read_local_nfo(source_folder)
            if not mediainfo or not mediainfo.title:
                logger.debug(f"[本地NFO] NFO解析失败或无标题")
                return None

            result = {
                "title": mediainfo.title,
                "original_title": getattr(mediainfo, 'original_title', '') or mediainfo.title,
                "year": mediainfo.year or '',
                "overview": getattr(mediainfo, 'overview', ''),
                "genres": getattr(mediainfo, 'genres', []),
                "production_countries": getattr(mediainfo, 'production_countries', []),
                "actors": getattr(mediainfo, 'actors', []),
                "poster_path": getattr(mediainfo, 'poster_path', ''),
                "tmdb_id": getattr(mediainfo, 'tmdb_id', ''),
                "douban_id": getattr(mediainfo, 'douban_id', ''),
                "source": "local_nfo"
            }
            with self._lock:
                self._stats['nfo_hits'] = self._stats.get('nfo_hits', 0) + 1
            logger.info(f"[本地NFO] ✅ 搜索成功: {result['title']} (年份: {result['year']})")
            logger.debug(f"[本地NFO] 完整数据: {result}")
            return result

        except Exception as e:
            logger.error(f"[本地NFO] 异常: {e}", exc_info=True)

        return None

    @log_method(log_args=True, log_result=False)
    def merge_search_results(self, title: str, source_dir: str = None, video_path: Path = None) -> dict:
        """合并搜索结果（PT > MP > 本地NFO，列表合并去重）"""
        cache_key = f"{title}_{source_dir}_{video_path}" if video_path else f"{title}_{source_dir}"
        
        logger.info(f"[合并] 🔄 开始合并搜索: {title}")
        logger.debug(f"[合并] 缓存键: {cache_key}")
        
        with self._lock:
            cached = self._series_cache.get(cache_key)
            if cached and time.time() - cached.get('ts', 0) < CACHE_TTL_SECONDS:
                logger.info(f"[缓存] ✅ 命中缓存: {title} (缓存时间: {datetime.datetime.fromtimestamp(cached.get('ts', 0)).strftime('%H:%M:%S')})")
                return cached.get('result', {}).copy()
        
        logger.debug(f"[合并] 缓存未命中，执行搜索")
        
        result = {
            "title": title,
            "originaltitle": title,
            "year": "",
            "plot": "",
            "country": "",
            "genre": "",
            "genres": [],
            "actors": [],
            "tag": [],
            "poster_url": "",
            "source": "文件夹名",
            "tmdb_id": "",
            "douban_id": ""
        }

        # 记录搜索来源
        search_sources = []

        # 1. PT搜索
        if self._enable_pt_search:
            logger.info(f"[合并] 步骤1: PT站搜索")
            pt_result = self.search_pt(title)
            if pt_result:
                search_sources.append("PT")
                logger.info(f"[合并] PT搜索返回: {pt_result.get('title')}")
                if pt_result.get("title"):
                    result["title"] = pt_result["title"]
                    result["originaltitle"] = pt_result.get("original_title", pt_result["title"])
                if pt_result.get("year"):
                    result["year"] = pt_result["year"]
                if pt_result.get("overview"):
                    result["plot"] = pt_result["overview"]
                if pt_result.get("production_countries"):
                    result["country"] = pt_result["production_countries"][0] if pt_result["production_countries"] else ""
                if pt_result.get("genres"):
                    for g in pt_result["genres"]:
                        if g and g not in result["genres"]:
                            result["genres"].append(g)
                    result["genre"] = result["genres"][0] if result["genres"] else ""
                if pt_result.get("actors"):
                    for a in pt_result["actors"]:
                        if a and a not in result["actors"]:
                            result["actors"].append(a)
                    result["tag"] = result["actors"].copy()
                if pt_result.get("poster_path"):
                    result["poster_url"] = pt_result["poster_path"]
                result["source"] = f"PT({pt_result.get('source', '')})"

        # 2. MP识别
        if self._enable_mp_recognition and video_path and video_path.exists():
            logger.info(f"[合并] 步骤2: MP识别 (文件: {video_path})")
            mp_result = self.search_mp(video_path)
            if mp_result:
                search_sources.append("MP")
                logger.info(f"[合并] MP识别返回: {mp_result.get('title')}")
                if not result["title"] or result["title"] == title:
                    if mp_result.get("title"):
                        result["title"] = mp_result["title"]
                        result["originaltitle"] = mp_result.get("original_title", mp_result["title"])
                if not result["year"] and mp_result.get("year"):
                    result["year"] = mp_result["year"]
                if not result["plot"] and mp_result.get("overview"):
                    result["plot"] = mp_result["overview"]
                if not result["country"] and mp_result.get("production_countries"):
                    result["country"] = mp_result["production_countries"][0] if mp_result["production_countries"] else ""
                if mp_result.get("genres"):
                    for g in mp_result["genres"]:
                        if g and g not in result["genres"]:
                            result["genres"].append(g)
                    if not result["genre"] and result["genres"]:
                        result["genre"] = result["genres"][0]
                if mp_result.get("actors"):
                    for a in mp_result["actors"]:
                        if a and a not in result["actors"]:
                            result["actors"].append(a)
                    result["tag"] = result["actors"].copy()
                if not result["poster_url"] and mp_result.get("poster_path"):
                    result["poster_url"] = mp_result["poster_path"]
                if mp_result.get("tmdb_id"):
                    result["tmdb_id"] = mp_result["tmdb_id"]
                if mp_result.get("douban_id"):
                    result["douban_id"] = mp_result["douban_id"]
                if result["source"] == "文件夹名":
                    result["source"] = f"MP({mp_result.get('source', '')})"

        # 3. 本地NFO
        if self._enable_local_nfo and source_dir:
            logger.info(f"[合并] 步骤3: 本地NFO搜索")
            local_result = self.search_local_nfo(title, source_dir)
            if local_result:
                search_sources.append("NFO")
                logger.info(f"[合并] 本地NFO返回: {local_result.get('title')}")
                if not result["title"] or result["title"] == title:
                    if local_result.get("title"):
                        result["title"] = local_result["title"]
                        result["originaltitle"] = local_result.get("original_title", local_result["title"])
                if not result["year"] and local_result.get("year"):
                    result["year"] = local_result["year"]
                if not result["plot"] and local_result.get("overview"):
                    result["plot"] = local_result["overview"]
                if not result["country"] and local_result.get("production_countries"):
                    result["country"] = local_result["production_countries"][0] if local_result["production_countries"] else ""
                if local_result.get("genres"):
                    for g in local_result["genres"]:
                        if g and g not in result["genres"]:
                            result["genres"].append(g)
                    if not result["genre"] and result["genres"]:
                        result["genre"] = result["genres"][0]
                if local_result.get("actors"):
                    for a in local_result["actors"]:
                        if a and a not in result["actors"]:
                            result["actors"].append(a)
                    result["tag"] = result["actors"].copy()
                if not result["poster_url"] and local_result.get("poster_path"):
                    result["poster_url"] = local_result["poster_path"]
                if local_result.get("tmdb_id"):
                    result["tmdb_id"] = local_result["tmdb_id"]
                if local_result.get("douban_id"):
                    result["douban_id"] = local_result["douban_id"]
                if result["source"] == "文件夹名":
                    result["source"] = "本地NFO"

        with self._lock:
            self._series_cache[cache_key] = {
                'result': result.copy(),
                'ts': time.time()
            }
            while len(self._series_cache) > MAX_CACHE_SIZE:
                removed_key = next(iter(self._series_cache))
                del self._series_cache[removed_key]
                logger.debug(f"[缓存] 清理旧缓存: {removed_key}")
        
        logger.info(f"[合并] ✅ 合并完成 - 最终标题: {result['title']}, 年份: {result['year'] or '未知'}, 来源: {result['source']}, 搜索来源: {', '.join(search_sources) if search_sources else '无'}")
        logger.debug(f"[合并] 完整结果: {result}")
        return result

    # ========== 生命周期 ==========

    def _cancel_pending_tasks(self):
        for name, task in list(self._pending_tasks.items()):
            if task.is_alive():
                logger.debug(f"[任务] 取消任务: {name}")
                task.cancel()
        self._pending_tasks.clear()
        logger.debug("[任务] 所有待处理任务已取消")

    @log_method(log_args=True)
    def init_plugin(self, config: dict = None):
        if not config:
            logger.warning("[初始化] 配置为空，跳过初始化")
            return

        logger.info("[初始化] ========== 开始初始化短剧处理器 ==========")
        logger.debug(f"[初始化] 配置内容: {config}")

        old_enabled = self._enabled
        old_monitor_confs = self._monitor_confs

        need_once = config.get("onlyonce", False)
        need_supplement = config.get("supplement", False)
        
        logger.info(f"[初始化] 加载配置 - 启用: {config.get('enabled')}, 一次性扫描: {need_once}, 补充元数据: {need_supplement}")
        
        self._load_config(config)

        if not self._enabled:
            logger.info("[初始化] 插件未启用")
            if old_enabled:
                logger.info("[初始化] 插件状态从启用变为禁用，停止监控并保存缓存")
                self._stop_monitors()
                self._save_cache()
            return

        logger.info("[初始化] 插件已启用，加载缓存和站点配置")
        
        if not old_enabled or not self._success_cache:
            logger.debug("[初始化] 加载缓存")
            self._load_cache()

        self._init_sites()
        self._apply_pt_priority()

        if old_monitor_confs != self._monitor_confs or not self._observer:
            logger.info("[初始化] 监控配置变更，重新启动监控")
            self._stop_monitors()
            self._parse_monitor_configs()

        if need_once:
            logger.info("[初始化] 执行一次性扫描任务 (3秒后)")
            t = threading.Timer(3, self.scan_all_dirs)
            self._pending_tasks['onlyonce'] = t
            t.start()

        if need_supplement:
            logger.info("[初始化] 执行一次性补充元数据任务 (3秒后)")
            t = threading.Timer(3, self._supplement_all_metadata)
            self._pending_tasks['supplement'] = t
            t.start()

        if need_once or need_supplement:
            logger.debug("[初始化] 清除配置中的一次性标志")
            config["onlyonce"] = False
            config["supplement"] = False
            self.update_config(config)
        
        logger.info("[初始化] ========== 短剧处理器初始化完成 ==========")

    def stop_service(self):
        logger.info("[服务] 停止短剧处理器服务")
        self._enabled = False
        self._cancel_pending_tasks()
        self._stop_monitors()
        self._save_cache()
        logger.info("[服务] 服务已停止")

    def get_service(self) -> List[Dict[str, Any]]:
        if not self._enabled:
            logger.debug("[服务] 插件未启用，无服务注册")
            return []
        
        services = []
        if self._scan_enabled and self._scan_interval > 0:
            logger.info(f"[服务] 注册定时扫描服务，间隔: {self._scan_interval}秒")
            services.append({
                "id": "ShortPlayProcessor.Scan",
                "name": "短剧处理器定时扫描",
                "trigger": IntervalTrigger(seconds=self._scan_interval),
                "func": self.scan_all_dirs,
            })
        if self._notify:
            logger.info(f"[服务] 注册通知聚合服务，间隔: {self._interval}秒")
            services.append({
                "id": "ShortPlayProcessor.Notify",
                "name": "短剧处理器通知聚合",
                "trigger": IntervalTrigger(seconds=self._interval),
                "func": self._send_notifications,
            })
        
        logger.info("[服务] 注册缓存清理服务，间隔: 1小时")
        services.append({
            "id": "ShortPlayProcessor.CleanCache",
            "name": "短剧处理器缓存清理",
            "trigger": IntervalTrigger(hours=1),
            "func": self._clean_expired_cache,
        })
        
        logger.debug(f"[服务] 共注册 {len(services)} 个服务")
        return services

    def get_state(self) -> bool:
        return self._enabled

    # ========== 配置 ==========

    def _load_config(self, config: dict):
        logger.debug("[配置] 加载配置参数")
        
        self._enabled = config.get("enabled", False)
        self._onlyonce = config.get("onlyonce", False)
        self._supplement = config.get("supplement", False)
        self._monitor_confs = config.get("monitor_confs", "")
        self._transfer_type = config.get("transfer_type", "link")
        self._exclude_keywords = config.get("exclude_keywords", "")
        self._notify = config.get("notify", False)
        self._interval = max(1, config.get("interval", 10))
        self._scan_interval = max(10, config.get("scan_interval", 60))
        self._scan_enabled = config.get("scan_enabled", True)
        self._enable_local_nfo = config.get("enable_local_nfo", True)
        self._enable_mp_recognition = config.get("enable_mp_recognition", True)
        self._enable_pt_search = config.get("enable_pt_search", True)
        self._pt_priority = config.get("pt_priority", "")
        self._media_root = config.get("media_root", "")
        self._polling_interval = max(1, config.get("polling_interval", 5))
        self._debounce_max_wait = max(1.0, config.get("debounce_max_wait", 10.0))
        self._enable_incremental_scan = config.get("enable_incremental_scan", True)

        logger.info(f"[配置] 主配置 - 启用: {self._enabled}, 转移方式: {self._transfer_type}, 通知: {self._notify}")
        logger.info(f"[配置] 扫描配置 - 定时扫描: {self._scan_enabled}, 间隔: {self._scan_interval}s, 增量: {self._enable_incremental_scan}")
        logger.info(f"[配置] 搜索配置 - PT: {self._enable_pt_search}, MP: {self._enable_mp_recognition}, NFO: {self._enable_local_nfo}")
        
        if self._pt_priority:
            logger.info(f"[配置] PT优先级: {self._pt_priority}")
        
        if self._media_root:
            logger.info(f"[配置] 媒体库根目录: {self._media_root}")

        self._compiled_exclude_patterns = []
        if self._exclude_keywords:
            kw_count = 0
            for kw in self._exclude_keywords.split("\n"):
                kw = kw.strip()
                if kw:
                    try:
                        self._compiled_exclude_patterns.append(re.compile(kw))
                        kw_count += 1
                    except re.error as e:
                        logger.warning(f"[配置] 无效的正则表达式: {kw}, 错误: {e}")
            logger.info(f"[配置] 加载排除关键词: {kw_count} 个")

    def _update_config(self):
        logger.debug("[配置] 更新配置")
        self.update_config({
            "enabled": self._enabled, "onlyonce": False, "supplement": False,
            "monitor_confs": self._monitor_confs, "transfer_type": self._transfer_type,
            "exclude_keywords": self._exclude_keywords, "notify": self._notify,
            "interval": self._interval, "scan_interval": self._scan_interval,
            "scan_enabled": self._scan_enabled,
            "enable_local_nfo": self._enable_local_nfo,
            "enable_mp_recognition": self._enable_mp_recognition,
            "enable_pt_search": self._enable_pt_search,
            "pt_priority": self._pt_priority,
            "polling_interval": self._polling_interval,
            "debounce_max_wait": self._debounce_max_wait,
            "enable_incremental_scan": self._enable_incremental_scan,
            "media_root": self._media_root,
        })

    # ========== 缓存 ==========

    def _save_cache(self):
        with self._lock:
            series_save = dict(list(self._series_cache.items())[-MAX_CACHE_SIZE:])
            success_save = dict(list(self._success_cache.items())[-MAX_CACHE_SIZE:])
            failed_save = self._failed_records[-500:]
            mapping_save = dict(list(self._title_mapping.items())[-MAX_CACHE_SIZE:])  # 新增
            
            logger.debug(f"[缓存] 保存缓存 - 成功: {len(success_save)}条, 系列: {len(series_save)}条, 失败: {len(failed_save)}条, 映射: {len(mapping_save)}条")
            
            self.save_data("series_cache", series_save)
            self.save_data("success_cache", success_save)
            self.save_data("failed_records", failed_save)
            self.save_data("title_mapping", mapping_save)  # 新增

    def _load_cache(self):
        logger.debug("[缓存] 加载缓存")
        series_data = self.get_data("series_cache") or {}
        success_data = self.get_data("success_cache") or {}
        failed_data = self.get_data("failed_records") or []
        mapping_data = self.get_data("title_mapping") or {}  # 新增

        loaded_series = 0
        for k, v in series_data.items():
            if isinstance(v, dict) and time.time() - v.get('ts', 0) < CACHE_TTL_SECONDS:
                self._series_cache[k] = v
                loaded_series += 1

        loaded_success = 0
        for k, v in success_data.items():
            if isinstance(v, dict):
                self._success_cache[k] = v
                loaded_success += 1

        self._failed_records = [r for r in failed_data if isinstance(r, dict)]
        self._title_mapping = {k: v for k, v in mapping_data.items() if isinstance(v, str)}  # 新增
        
        logger.info(f"[缓存] 加载完成 - 成功记录: {loaded_success}条, 系列缓存: {loaded_series}条, 失败记录: {len(self._failed_records)}条, 映射: {len(self._title_mapping)}条")

    def _clean_expired_cache(self):
        with self._lock:
            now = time.time()
            expired_series = [k for k, v in self._series_cache.items() if now - v.get('ts', 0) > CACHE_TTL_SECONDS]
            for k in expired_series:
                del self._series_cache[k]
            if expired_series:
                logger.info(f"[缓存] 清理过期缓存: {len(expired_series)}条")

    # ========== 站点初始化 ==========

    def _init_sites(self):
        logger.debug("[站点] 初始化站点配置")
        for site_conf in DEFAULT_SITES:
            domain = site_conf["domain"]
            try:
                site = SiteOper().get_by_domain(domain)
                self._site_cache[domain] = site
                self._indexer_cache[domain] = SitesHelper().get_indexer(domain) if site else None
                status = "已配置" if site else "未配置"
                logger.debug(f"[站点] {site_conf['name']}({domain}): {status}")
            except Exception as e:
                self._site_cache[domain] = None
                self._indexer_cache[domain] = None
                logger.error(f"[站点] 初始化失败 {domain}: {e}")

    def _apply_pt_priority(self):
        if not self._pt_priority:
            logger.debug("[PT优先级] 未设置优先级，使用默认顺序")
            return
        
        priority_list = [p.strip().lower() for p in self._pt_priority.split(",") if p.strip()]
        if not priority_list:
            return

        logger.info(f"[PT优先级] 应用优先级顺序: {priority_list}")

        def get_order(domain):
            for idx, p in enumerate(priority_list):
                if p in domain or domain.startswith(p):
                    return idx
            return 999

        old_order = [s["name"] for s in self._sites_config]
        self._sites_config.sort(key=lambda s: get_order(s["domain"]))
        new_order = [s["name"] for s in self._sites_config]
        logger.debug(f"[PT优先级] 站点顺序变更: {old_order} -> {new_order}")

    # ========== 监控 ==========

    def _parse_monitor_configs(self):
        if not self._monitor_confs:
            logger.warning("[监控] 监控配置为空")
            return

        logger.info("[监控] 解析监控配置")
        
        for line in self._monitor_confs.split("\n"):
            line = line.strip()
            if not line:
                continue

            parts = line.rsplit("#", 3)
            if len(parts) < 3:
                logger.error(f"[监控] 配置格式错误: {line}")
                continue

            mode = parts[0].strip()
            source_dir = os.path.normpath(parts[1].strip())
            target_dir = os.path.normpath(parts[2].strip())
            rename = parts[3].strip() if len(parts) > 3 else "smart"

            logger.info(f"[监控] 解析配置 - 模式: {mode}, 源目录: {source_dir}, 目标目录: {target_dir}, 重命名: {rename}")

            if self._media_root:
                try:
                    Path(target_dir).resolve().relative_to(Path(self._media_root).resolve())
                    logger.debug(f"[监控] 目标目录在媒体库根目录下: {target_dir}")
                except ValueError:
                    logger.error(f"[监控] 目标目录不在媒体库根目录下: {target_dir}")
                    continue

            if not os.path.exists(source_dir):
                logger.warning(f"[监控] 源目录不存在: {source_dir}")
                continue

            self._dirconf[source_dir] = target_dir
            self._renameconf[source_dir] = rename

            try:
                if mode == "compatibility":
                    logger.info(f"[监控] 使用兼容模式(PollingObserver), 轮询间隔: {self._polling_interval}s")
                    observer = PollingObserver(timeout=self._polling_interval)
                else:
                    logger.info(f"[监控] 使用普通模式(Observer)")
                    observer = Observer(timeout=10)
                
                handler = FileMonitorHandler(self, source_dir, max_wait=self._debounce_max_wait)
                observer.schedule(handler, path=source_dir, recursive=True)
                observer.daemon = True
                observer.start()
                self._observer.append(observer)
                logger.info(f"[监控] ✅ 监控已启动: {source_dir}")
            except Exception as e:
                logger.error(f"[监控] ❌ 启动监控失败 {source_dir}: {e}", exc_info=True)

        logger.info(f"[监控] 监控配置完成 - 共 {len(self._observer)} 个监控任务")

    def _stop_monitors(self):
        if not self._observer:
            logger.debug("[监控] 无运行中的监控任务")
            return
        
        logger.info(f"[监控] 停止 {len(self._observer)} 个监控任务")
        for idx, obs in enumerate(self._observer):
            try:
                obs.stop()
                obs.join(timeout=5)
                logger.debug(f"[监控] 监控任务 #{idx+1} 已停止")
            except Exception as e:
                logger.error(f"[监控] 停止监控任务失败: {e}")
        self._observer.clear()
        logger.info("[监控] 所有监控任务已停止")

    # ========== 扫描 ==========

    def scan_all_dirs(self):
        logger.info(f"[扫描] scan_all_dirs 被调用，当前 _scanning={self._scanning}")
        if self._scanning:
            logger.warning("[扫描] 已有扫描任务正在执行，跳过")
            return
        
        logger.info("[扫描] ========== 开始扫描所有监控目录 ==========")
        self._scanning = True
        
        try:
            logger.info(f"[扫描] 监控目录配置: {list(self._dirconf.keys())}")
            for source_dir in self._dirconf:
                logger.info(f"[扫描] 处理监控目录: {source_dir}")
                if not self._enabled:
                    logger.warning("[扫描] 插件已禁用，停止扫描")
                    break
                
                if self._enable_incremental_scan:
                    logger.info(f"[扫描] 使用增量扫描模式: {source_dir}")
                    self._incremental_scan(source_dir)
                else:
                    logger.info(f"[扫描] 使用全量扫描模式: {source_dir}")
                    self._full_scan(source_dir)

        except Exception as e:
            logger.error(f"[扫描] 扫描过程异常: {e}", exc_info=True)
        finally:
            self._scanning = False
            logger.info("[扫描] ========== 扫描结束 ==========")

    @log_method(log_args=True)
    def _full_scan(self, source_dir: str):
        source_path = Path(source_dir)
        if not source_path.exists():
            logger.warning(f"[全量扫描] 源目录不存在: {source_dir}")
            return

        logger.info(f"[全量扫描] 扫描目录: {source_dir}")
        # 全量扫描时清空缓存
        self.clear_cache()
        logger.info("[全量扫描] 已清空缓存，开始全新扫描")
        
        all_items = list(source_path.iterdir())
        logger.info(f"[全量扫描] 目录下共有 {len(all_items)} 个项目")
        
        for item in all_items:
            logger.debug(f"[全量扫描] 项目: {item.name}, is_dir={item.is_dir()}")
        
        folder_count = 0
        for folder in source_path.iterdir():
            if not self._enabled:
                logger.warning("[全量扫描] 插件已禁用，停止扫描")
                return  # 直接退出，不再处理后续文件夹
            if not folder.is_dir():
                logger.debug(f"[全量扫描] 跳过非目录: {folder.name}")
                continue
                
            logger.info(f"[全量扫描] 检查目录: {folder.name}")
            
            if not self._is_valid_folder(str(folder), source_dir):
                logger.warning(f"[全量扫描] 目录无效: {folder.name}")
                continue
                
            folder_count += 1
            logger.info(f"[全量扫描] 有效目录 #{folder_count}: {folder.name}")
            
            all_files = list(folder.iterdir())
            logger.info(f"[全量扫描] 目录 {folder.name} 中有 {len(all_files)} 个文件")
            
            for ext in settings.RMT_MEDIAEXT:
                video_files = list(folder.glob(f"*{ext}")) + list(folder.glob(f"*{ext.upper()}"))
                if video_files:
                    logger.info(f"[全量扫描] 找到 {len(video_files)} 个 {ext} 文件: {[f.name for f in video_files]}")
                
                for vf in video_files:
                    logger.info(f"[全量扫描] 处理视频文件: {vf}")
                    if not self._is_processed(str(vf)):
                        logger.info(f"[全量扫描] 文件未处理，开始处理: {vf}")
                        self._process_with_retry(str(vf), source_dir)
                    else:
                        logger.debug(f"[全量扫描] 文件已处理，跳过: {vf}")
        
        if folder_count == 0:
            logger.warning(f"[全量扫描] 没有找到有效的剧集目录！请检查目录结构。")
            logger.warning(f"[全量扫描] 要求: {source_dir}/剧名文件夹/视频文件")
        else:
            logger.info(f"[全量扫描] 扫描完成，共处理 {folder_count} 个目录")

    @log_method(log_args=True)
    def _incremental_scan(self, source_dir: str):
        last_scan = self._last_scan_time.get(source_dir, 0)
        now = time.time()
        
        if last_scan == 0:
            logger.info(f"[增量扫描] 首次扫描 {source_dir}")
        else:
            logger.info(f"[增量扫描] 上次扫描时间: {datetime.datetime.fromtimestamp(last_scan).strftime('%Y-%m-%d %H:%M:%S')}")
        
        source_path = Path(source_dir)
        if not source_path.exists():
            logger.warning(f"[增量扫描] 源目录不存在: {source_dir}")
            return

        processed_count = 0
        for folder in source_path.iterdir():
            if not folder.is_dir():
                continue
            
            if not self._is_valid_folder(str(folder), source_dir):
                continue
            
            for ext in settings.RMT_MEDIAEXT:
                for vf in list(folder.glob(f"*{ext}")) + list(folder.glob(f"*{ext.upper()}")):
                    if vf.is_file():
                        mtime = max(vf.stat().st_mtime, vf.stat().st_ctime)
                        if mtime > last_scan:
                            logger.debug(f"[增量扫描] 检测到新文件: {vf.name}, 修改时间: {datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')}")
                            if not self._is_processed(str(vf)):
                                logger.info(f"[增量扫描] 处理新文件: {vf}")
                                self._process_with_retry(str(vf), source_dir)
                                processed_count += 1
                            else:
                                logger.debug(f"[增量扫描] 文件已处理，跳过: {vf}")
                        else:
                            logger.debug(f"[增量扫描] 文件未变更，跳过: {vf}")

        self._last_scan_time[source_dir] = now
        logger.info(f"[增量扫描] 扫描完成 {source_dir}，处理新文件: {processed_count} 个")

    # ========== 文件处理 ==========

    def process_file(self, file_path: str, source_dir: str):
        logger.info(f"[文件处理] 收到文件: {file_path}, 源目录: {source_dir}")
        if not self._should_exclude(file_path) and Path(file_path).suffix.lower() in settings.RMT_MEDIAEXT:
            logger.debug(f"[文件处理] 文件通过检查，开始处理")
            self._process_with_retry(file_path, source_dir)
        else:
            if self._should_exclude(file_path):
                logger.debug(f"[文件处理] 文件被排除规则过滤: {file_path}")
            else:
                logger.debug(f"[文件处理] 非视频文件，跳过: {file_path}")

    @log_method(log_args=True, log_result=False)
    def _process_with_retry(self, file_path: str, source_dir: str):
        if not self._enabled:
            logger.debug("[处理] 插件已禁用，跳过处理")
            return  # 直接返回，不记录成功或失败
        normalized = self._normalize_path(file_path)
        logger.info(f"[处理] 开始处理文件: {normalized}")
        
        for attempt in range(MAX_RETRIES):
            logger.debug(f"[处理] 第 {attempt + 1}/{MAX_RETRIES} 次尝试")
            try:
                if self._do_process(file_path, source_dir):
                    logger.info(f"[处理] ✅ 处理成功")
                    return
                else:
                    logger.warning(f"[处理] 处理返回失败")
                    return
            except Exception as e:
                logger.error(f"[处理] 第 {attempt + 1} 次尝试异常: {e}", exc_info=True)
                if attempt == MAX_RETRIES - 1:
                    self._record_failure(normalized, str(e))
                    return
                wait_time = RETRY_DELAY * (attempt + 1)
                logger.debug(f"[处理] 等待 {wait_time}s 后重试")
                time.sleep(wait_time)

    @log_method(log_args=True, log_result=False)
    def _do_process(self, file_path: str, source_dir: str) -> bool:
        if not self._enabled:
            logger.debug("[处理] 插件已禁用，跳过处理")
            return True

        normalized = self._normalize_path(file_path)
        file_name = Path(file_path).name
        logger.info(f"[处理] ========== 处理文件: {file_name} ==========")

        with self._lock:
            if normalized in self._processing_files:
                logger.warning(f"[处理] 文件正在处理中，跳过: {file_name}")
                return True
            self._processing_files.add(normalized)
            logger.debug(f"[处理] 已加入处理队列，当前队列: {len(self._processing_files)}")

        try:
            source_path = Path(file_path)
            folder_path = source_path.parent
            logger.debug(f"[处理] 源目录: {source_dir}, 父目录: {folder_path}")

            if not self._is_valid_folder(str(folder_path), source_dir):
                logger.warning(f"[处理] 目录结构无效: {folder_path}")
                return True

            dest_dir = self._dirconf.get(source_dir)
            if not dest_dir:
                logger.error(f"[处理] 未找到目标目录: {source_dir}")
                return True

            rename_conf = self._renameconf.get(source_dir, "smart")
            logger.info(f"[处理] 目标目录: {dest_dir}, 重命名策略: {rename_conf}")
            
            clean_title = self._extract_title(folder_path.name)
            logger.info(f"[处理] 提取剧名: '{folder_path.name}' -> '{clean_title}'")

            # 检查是否有映射关系
            with self._lock:
                mapped_title = self._title_mapping.get(clean_title)
            
            if mapped_title:
                logger.info(f"[处理] 使用映射标题: {clean_title} -> {mapped_title}")
                target_folder = Path(dest_dir) / self._safe_name(mapped_title)
            else:
                target_folder = Path(dest_dir) / self._safe_name(clean_title)
            
            # 检查目标文件夹是否已存在且有NFO文件
            nfo_path = target_folder / "tvshow.nfo"
            merged_data = None
            
            if nfo_path.exists():
                logger.info(f"[处理] 目标文件夹已存在且包含NFO文件: {target_folder}")
                # 从现有NFO读取信息
                existing_mediainfo = self._read_local_nfo(target_folder)
                if existing_mediainfo and existing_mediainfo.title:
                    merged_data = {
                        "title": existing_mediainfo.title,
                        "originaltitle": getattr(existing_mediainfo, 'original_title', '') or existing_mediainfo.title,
                        "year": existing_mediainfo.year or '',
                        "plot": getattr(existing_mediainfo, 'overview', ''),
                        "country": existing_mediainfo.production_countries[0] if existing_mediainfo.production_countries else '',
                        "genre": existing_mediainfo.genres[0] if existing_mediainfo.genres else '',
                        "genres": existing_mediainfo.genres or [],
                        "actors": existing_mediainfo.actors or [],
                        "poster_url": getattr(existing_mediainfo, 'poster_path', ''),
                        "source": existing_mediainfo.source,
                        "tmdb_id": getattr(existing_mediainfo, 'tmdb_id', ''),
                        "douban_id": getattr(existing_mediainfo, 'douban_id', '')
                    }
                    logger.info(f"[处理] ✅ 使用已有剧集信息: {merged_data['title']} (来源: {merged_data['source']})")
                else:
                    logger.warning(f"[处理] NFO文件存在但解析失败，将重新识别")
            
            # 如果没有现有信息，则进行搜索
            if not merged_data:
                logger.debug(f"[处理] 未找到现有剧集信息，开始搜索...")
                merged_data = self.merge_search_results(
                    title=clean_title,
                    source_dir=source_dir,
                    video_path=source_path
                )
                title = merged_data.get("title", clean_title)
                self._last_source = merged_data.get("source", "文件夹名")
                logger.info(f"[处理] 最终标题: {title}, 来源: {self._last_source}")
                
                # 创建目标文件夹
                target_folder = Path(dest_dir) / self._safe_name(title)
                target_folder.mkdir(parents=True, exist_ok=True)
                logger.info(f"[处理] 目标文件夹: {target_folder}")
                
                # 保存映射关系
                with self._lock:
                    self._title_mapping[clean_title] = title
                    logger.debug(f"[处理] 保存映射: {clean_title} -> {title}")
                
                # 写入NFO文件
                logger.info(f"[处理] 创建 NFO 文件: {nfo_path}")
                self._write_nfo(nfo_path, merged_data)
                poster_url = merged_data.get("poster_url", "")
                if poster_url:
                    logger.debug(f"[处理] 下载海报: {poster_url}")
                    self._download_image(poster_url, target_folder / "poster.jpg")
                else:
                    logger.debug(f"[处理] 无海报URL")
            else:
                # 使用现有信息，确保目标文件夹存在
                target_folder.mkdir(parents=True, exist_ok=True)
                
                # 可选：补充NFO中可能缺少的字段
                self._merge_nfo(nfo_path, merged_data)
            
            # 组织视频文件
            target_path = self._organize_video(source_path, target_folder, rename_conf, folder_path)
            if not target_path:
                logger.error(f"[处理] 文件转移失败")
                return True

            self._record_success(
                normalized, 
                merged_data.get("title", clean_title), 
                str(target_path),
                merged_data.get("source", "文件夹名")
            )

            with self._lock:
                self._stats['total_processed'] += 1
                self._stats['success_count'] += 1
                self._stats['last_process_time'] = datetime.datetime.now()

            if self._notify:
                logger.debug(f"[处理] 添加通知: {merged_data.get('title', clean_title)}")
                self._add_notify(merged_data.get('title', clean_title), normalized)

            logger.info(f"[处理] ✅ 处理完成: {file_name} -> {merged_data.get('title', clean_title)} ({target_path.name})")
            return True

        except Exception as e:
            logger.error(f"[处理] ❌ 处理异常: {file_name}, {e}", exc_info=True)
            raise
        finally:
            with self._lock:
                self._processing_files.discard(normalized)
                logger.debug(f"[处理] 移出处理队列，当前队列: {len(self._processing_files)}")

    # ========== 辅助方法 ==========

    @log_method(log_args=True)
    def _read_local_nfo(self, folder_path: Path) -> Optional[MediaInfo]:
        nfo_path = folder_path / "tvshow.nfo"
        if not nfo_path.is_file():
            logger.debug(f"[本地NFO] NFO文件不存在: {nfo_path}")
            return None

        logger.debug(f"[本地NFO] 读取NFO: {nfo_path}")
        content = self._read_file(nfo_path)
        if not content:
            logger.warning(f"[本地NFO] 文件内容为空: {nfo_path}")
            return None

        try:
            root = ET.fromstring(content)
            mediainfo = MediaInfo()
            mediainfo.title = root.findtext("title", "").strip()
            mediainfo.year = root.findtext("year")
            mediainfo.overview = root.findtext("plot") or root.findtext("outline")
            mediainfo.genres = [g.text.strip() for g in root.findall("genre") if g.text]
            mediainfo.production_countries = [c.text.strip() for c in root.findall("country") if c.text]

            rating = root.findtext("rating")
            if rating:
                try:
                    mediainfo.vote_average = float(rating)
                except (ValueError, TypeError):
                    pass

            for uid in root.findall("uniqueid"):
                if uid.get("type") == "douban" and uid.text:
                    mediainfo.douban_id = uid.text.strip()
                elif uid.get("type") == "tmdb" and uid.text:
                    mediainfo.tmdb_id = uid.text.strip()

            mediainfo.source = "local"
            logger.debug(f"[本地NFO] 解析成功: title={mediainfo.title}, year={mediainfo.year}")
            return mediainfo
        except Exception as e:
            logger.error(f"[本地NFO] 解析失败: {e}", exc_info=True)
            return None

    @log_method(log_args=True, log_result=False)
    def _organize_video(self, source_path: Path, target_folder: Path, rename_conf: str, source_folder: Path) -> Optional[Path]:
        episode = self._extract_episode(source_path.name)
        season_num = self._extract_season(source_folder, source_path.name)
        
        logger.debug(f"[整理] 文件名: {source_path.name}, 集数: {episode}, 季数: {season_num}")

        if rename_conf == "smart" and episode is not None and season_num is not None:
            new_name = f"S{season_num:02d}E{max(episode, 1):02d}{source_path.suffix}"
            logger.info(f"[整理] 智能重命名: {source_path.name} -> {new_name}")
        else:
            new_name = source_path.name
            if rename_conf == "off":
                logger.debug(f"[整理] 重命名已禁用，保留原文件名: {new_name}")
            else:
                logger.debug(f"[整理] 使用原文件名: {new_name}")

        target_path = target_folder / new_name

        # 检查目标文件是否已存在
        if target_path.exists():
            # 如果是同一个文件，跳过
            try:
                if target_path.samefile(source_path):
                    logger.debug(f"[整理] 目标文件与源文件相同，跳过转移")
                    return target_path
                # 如果文件大小相同，可能是重复处理，跳过
                if target_path.stat().st_size == source_path.stat().st_size:
                    logger.debug(f"[整理] 目标文件已存在且大小相同，跳过转移")
                    return target_path
            except OSError as e:
                logger.debug(f"[整理] 文件比较异常: {e}")
            
        # 如果目标文件已存在，直接覆盖
        if target_path.exists():
            try:
                # 如果是同一个文件，跳过转移
                if target_path.samefile(source_path):
                    logger.debug(f"[整理] 目标文件与源文件相同，跳过转移")
                    return target_path
                # 否则删除已存在的文件
                logger.warning(f"[整理] 目标文件已存在，将覆盖: {target_path}")
                target_path.unlink()
            except OSError as e:
                logger.debug(f"[整理] 文件检查异常: {e}")

        return self._transfer_file(source_path, target_path)

    @log_method(log_args=True, log_result=False)
    def _transfer_file(self, source: Path, target: Path) -> Optional[Path]:
        logger.info(f"[转移] {self._transfer_type}: {source} -> {target}")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            logger.debug(f"[转移] 目标目录已创建: {target.parent}")

            if self._transfer_type == "move":
                ok = SystemUtils.move(source, target)
            elif self._transfer_type == "copy":
                ok = SystemUtils.copy(source, target)
            elif self._transfer_type == "softlink":
                ok = SystemUtils.softlink(source, target)
            else:
                ok = SystemUtils.link(source, target)

            if ok:
                logger.info(f"[转移] ✅ {self._transfer_type} 成功: {target.name}")
                return target
            else:
                logger.error(f"[转移] ❌ {self._transfer_type} 失败")
                return None
        except Exception as e:
            logger.error(f"[转移] 异常: {e}", exc_info=True)
            return None

    @log_method(log_args=True)
    def _write_nfo(self, nfo_path: Path, data: dict):
        """写入新NFO文件"""
        logger.info(f"[NFO] 写入NFO文件: {nfo_path}")
        try:
            nfo_path.parent.mkdir(parents=True, exist_ok=True)
            
            doc = minidom.Document()
            root = doc.createElement("tvshow")
            doc.appendChild(root)
            
            self._add_text_node(doc, root, "title", data.get("title", ""))
            self._add_text_node(doc, root, "originaltitle", data.get("originaltitle", data.get("title", "")))
            
            if data.get("year"):
                self._add_text_node(doc, root, "year", str(data["year"]))
                logger.debug(f"[NFO] 添加年份: {data['year']}")
            if data.get("plot"):
                self._add_text_node(doc, root, "plot", data["plot"])
                logger.debug(f"[NFO] 添加简介 (长度: {len(data['plot'])})")
            
            country = data.get("country", "")
            if isinstance(country, dict):
                country = country.get("name", "")
            if country and not isinstance(country, dict):
                self._add_text_node(doc, root, "country", country)
                logger.debug(f"[NFO] 添加国家: {country}")
            
            genres = data.get("genres", [])
            if genres:
                for genre in genres:
                    if genre and not isinstance(genre, dict):
                        self._add_text_node(doc, root, "genre", genre)
                        logger.debug(f"[NFO] 添加类型: {genre}")
            
            
            # 添加演员
            actor_names = []
            actor_count = 0
            for actor in data.get("actors", []):
                name = actor if isinstance(actor, str) else actor.get("name", "")
                if name:
                    actor_names.append(name)
                    existing = None
                    for existing_actor in root.getElementsByTagName("actor"):
                        name_nodes = existing_actor.getElementsByTagName("name")
                        if name_nodes:
                            name_node = name_nodes[0]
                            if name_node.firstChild and name_node.firstChild.nodeValue == name:
                                existing = existing_actor
                                break
                    if not existing:
                        actor_elem = doc.createElement("actor")
                        self._add_text_node(doc, actor_elem, "name", name)
                        root.appendChild(actor_elem)
                        actor_count += 1

            for actor_name in actor_names:
                self._add_text_node(doc, root, "tag", actor_name)
                logger.debug(f"[NFO] 添加 tag 标签: {actor_name}")
            
            if actor_count > 0:
                logger.debug(f"[NFO] 添加演员: {actor_count}人")
            
            # 添加唯一ID
            if data.get("tmdb_id"):
                node = doc.createElement("uniqueid")
                node.setAttribute("type", "tmdb")
                node.appendChild(doc.createTextNode(str(data["tmdb_id"])))
                root.appendChild(node)
                logger.debug(f"[NFO] 添加TMDB ID: {data['tmdb_id']}")
            if data.get("douban_id"):
                node = doc.createElement("uniqueid")
                node.setAttribute("type", "douban")
                node.appendChild(doc.createTextNode(str(data["douban_id"])))
                root.appendChild(node)
                logger.debug(f"[NFO] 添加豆瓣ID: {data['douban_id']}")
            if data.get("source"):
                self._add_text_node(doc, root, "source", data["source"])
                logger.debug(f"[NFO] 添加来源: {data['source']}")
            
            xml_str = doc.toprettyxml(indent="  ", encoding="utf-8")
            nfo_path.write_bytes(xml_str)
            logger.info(f"[NFO] ✅ NFO文件写入成功: {nfo_path.name}")
            
        except Exception as e:
            logger.error(f"[NFO] ❌ 写入失败: {e}", exc_info=True)

    def _add_text_node(self, doc: minidom.Document, parent: minidom.Element, tag: str, value: str):
        """添加文本节点"""
        if value:
            node = doc.createElement(tag)
            node.appendChild(doc.createTextNode(str(value)))
            parent.appendChild(node)

    @log_method(log_args=True)
    def _merge_nfo(self, nfo_path: Path, new_data: dict) -> bool:
        """合并NFO文件（只补充不存在的字段）"""
        logger.info(f"[NFO合并] 合并NFO: {nfo_path}")
        try:
            tree = ET.parse(nfo_path)
            root = tree.getroot()
            
            if root.findtext("user_protected") == "true":
                logger.debug(f"[NFO合并] NFO受用户保护，跳过合并")
                return False
            
            updated = False
            
            field_map = [
                ('title', 'title'), ('originaltitle', 'originaltitle'),
                ('year', 'year'), ('plot', 'plot'),
                ('country', 'country'), ('genre', 'genre'),
                ('source', 'source')
            ]
            
            for tag, key in field_map:
                if root.find(tag) is None and new_data.get(key):
                    elem = ET.SubElement(root, tag)
                    elem.text = str(new_data[key])
                    updated = True
                    logger.debug(f"[NFO合并] 补充字段: {tag}={new_data[key]}")
            
            # 处理演员和tag
            if new_data.get('actors'):
                existing_actors = set()
                existing_tags = set()  # 新增：收集现有tag
                
                # 收集现有演员
                for actor_elem in root.findall('actor'):
                    name_elem = actor_elem.find('name')
                    if name_elem is not None and name_elem.text:
                        existing_actors.add(name_elem.text.strip())
                
                # 新增：收集现有tag
                for tag_elem in root.findall('tag'):
                    if tag_elem.text:
                        existing_tags.add(tag_elem.text.strip())
                
                added_actors = 0
                added_tags = 0  # 新增：记录添加的tag数量
                
                for actor in new_data['actors']:
                    name = actor if isinstance(actor, str) else actor.get("name", "")
                    if not name:
                        continue
                    
                    # 补充演员节点
                    if name not in existing_actors:
                        actor_elem = ET.SubElement(root, 'actor')
                        name_elem = ET.SubElement(actor_elem, 'name')
                        name_elem.text = name
                        added_actors += 1
                        updated = True
                    
                    # 新增：补充tag节点（为每个演员单独创建tag）
                    if name not in existing_tags:
                        tag_elem = ET.SubElement(root, 'tag')
                        tag_elem.text = name
                        added_tags += 1
                        updated = True
                
                if added_actors > 0:
                    logger.debug(f"[NFO合并] 补充演员: {added_actors}人")
                if added_tags > 0:  # 新增：记录tag补充日志
                    logger.debug(f"[NFO合并] 补充 tag 标签: {added_tags}个")

            if new_data.get('tmdb_id') and not root.find(".//uniqueid[@type='tmdb']"):
                uid = ET.SubElement(root, 'uniqueid')
                uid.set('type', 'tmdb')
                uid.text = str(new_data['tmdb_id'])
                updated = True
                logger.debug(f"[NFO合并] 补充TMDB ID: {new_data['tmdb_id']}")
            
            if new_data.get('douban_id') and not root.find(".//uniqueid[@type='douban']"):
                uid = ET.SubElement(root, 'uniqueid')
                uid.set('type', 'douban')
                uid.text = new_data['douban_id']
                updated = True
                logger.debug(f"[NFO合并] 补充豆瓣ID: {new_data['douban_id']}")
            
            if updated:
                tree.write(nfo_path, encoding='utf-8', xml_declaration=True)
                logger.info(f"[NFO合并] ✅ 合并完成: {nfo_path.name}")
            else:
                logger.debug(f"[NFO合并] 无需更新: {nfo_path.name}")
            
            return updated
            
        except Exception as e:
            logger.error(f"[NFO合并] ❌ 合并失败: {e}", exc_info=True)
            return False

    @log_method(log_args=True)
    def _download_image(self, url: str, file_path: Path) -> bool:
        """下载图片，豆瓣使用专用方法"""
        if not url:
            logger.debug(f"[下载] URL为空，跳过下载")
            return False
        
        logger.debug(f"[下载] 下载图片: {url} -> {file_path}")
        
        # 豆瓣图片使用专用方法
        if 'doubanio.com' in url or 'douban.com' in url:
            logger.debug(f"[下载] 检测到豆瓣图片，使用专用下载器")
            return self._download_douban_image(url, file_path)
        
        # 其他图片直接下载
        try:
            r = RequestUtils(timeout=30).get_res(url=url, raise_exception=True)
            if r and r.status_code == 200:
                file_path.write_bytes(r.content)
                logger.info(f"[下载] ✅ 图片下载成功: {file_path.name} ({len(r.content)} bytes)")
                return True
            else:
                logger.warning(f"[下载] 下载失败: HTTP {r.status_code if r else 'None'}")
                return False
        except Exception as e:
            logger.error(f"[下载] 下载异常: {e}")
            return False


    def _download_douban_image(self, url: str, file_path: Path) -> bool:
        """下载豆瓣图片，支持不同尺寸"""
        try:
            # 提取图片ID，支持多种格式
            match = re.search(r'/public/(p\d+\.(?:webp|jpg|png))', url)
            if not match:
                logger.warning(f"[豆瓣下载] 无法提取图片ID: {url}")
                return False
            
            photo_id = match.group(1)
            logger.debug(f"[豆瓣下载] 提取图片ID: {photo_id}")
            
            # 尝试不同尺寸，优先大图
            for size, size_name in [('l', '大图'), ('m', '中图'), ('s', '小图')]:
                try_url = f"https://img1.doubanio.com/view/photo/{size}/public/{photo_id}"
                logger.debug(f"[豆瓣下载] 尝试 {size_name}: {try_url}")
                
                try:
                    r = RequestUtils(timeout=30).get_res(url=try_url, raise_exception=True)
                    if r and r.status_code == 200:
                        content = r.content
                        if len(content) > 100:  # 确保不是错误页面
                            file_path.write_bytes(content)
                            logger.info(f"[豆瓣下载] ✅ 下载成功 ({size_name}): {file_path.name} ({len(content)} bytes)")
                            return True
                        else:
                            logger.debug(f"[豆瓣下载] {size_name} 返回内容过小，可能是404")
                except Exception as e:
                    logger.debug(f"[豆瓣下载] {size_name} 异常: {e}")
                    continue
            
            logger.warning(f"[豆瓣下载] ❌ 所有尺寸都下载失败: {url}")
            return False
            
        except Exception as e:
            logger.error(f"[豆瓣下载] 下载异常: {e}", exc_info=True)
            return False

    @log_method(log_args=True)
    def _extract_episode(self, filename: str) -> Optional[int]:
        for pattern in EPISODE_PATTERNS:
            match = pattern.search(filename)
            if match:
                episode = int(match.group(1))
                logger.debug(f"[提取] 从文件名提取集数: {filename} -> {episode}")
                return episode
        for part in filename.split('.'):
            if part.isdigit() and 1 <= int(part) <= 999:
                episode = int(part)
                logger.debug(f"[提取] 从文件名数字提取集数: {filename} -> {episode}")
                return episode
        logger.debug(f"[提取] 未提取到集数: {filename}")
        return None

    @log_method(log_args=True)
    def _extract_season(self, source_folder: Path, filename: str) -> int:
        nfo_path = source_folder / "tvshow.nfo"
        if nfo_path.exists():
            try:
                tree = ET.parse(nfo_path)
                season = tree.findtext("season")
                if season:
                    season_num = int(season.strip())
                    logger.debug(f"[提取] 从NFO提取季数: {season_num}")
                    return season_num
            except Exception as e:
                logger.debug(f"[提取] NFO解析失败: {e}")

        match = re.search(r'[sS](\d+)', filename)
        if match:
            season_num = int(match.group(1))
            logger.debug(f"[提取] 从文件名提取季数: {filename} -> {season_num}")
            return season_num
        
        logger.debug(f"[提取] 使用默认季数: 1")
        return 1

    @log_method(log_args=True)
    def _extract_title(self, folder_name: str) -> str:
        original = folder_name.strip()
        title = original
        for pattern, repl in TITLE_CLEAN_PATTERNS:
            title = pattern.sub(repl, title)
        result = title.strip() or original
        if result != original:
            logger.debug(f"[提取] 清理标题: '{original}' -> '{result}'")
        return result

    def _safe_name(self, name: str) -> str:
        safe = FILENAME_CLEAN.sub('', name).strip('. ')
        if safe != name:
            logger.debug(f"[安全名称] '{name}' -> '{safe}'")
        return safe

    def _is_valid_folder(self, folder_path: str, source_dir: str) -> bool:
        try:
            parts = Path(folder_path).resolve().relative_to(Path(source_dir).resolve()).parts
            if len(parts) != 1:
                logger.debug(f"[验证] 目录结构无效: {folder_path} (深度: {len(parts)})")
                return False
            if parts[0].startswith('.') or parts[0] in SYSTEM_FOLDERS:
                logger.debug(f"[验证] 目录被排除: {parts[0]}")
                return False
            logger.debug(f"[验证] 目录有效: {folder_path}")
            return True
        except (ValueError, OSError) as e:
            logger.debug(f"[验证] 目录验证异常: {folder_path}, {e}")
            return False

    def _should_exclude(self, path: str) -> bool:
        for folder in SYSTEM_FOLDERS:
            if f"/{folder}/" in path or f"\\{folder}\\" in path:
                logger.debug(f"[排除] 系统文件夹匹配: {folder}")
                return True
        for p in self._compiled_exclude_patterns:
            if p.search(path):
                logger.debug(f"[排除] 关键词匹配: {p.pattern}")
                return True
        return False

    def _normalize_path(self, path: str) -> str:
        try:
            return str(Path(path).resolve())
        except Exception:
            return path

    def _is_processed(self, file_path: str) -> bool:
        return self._normalize_path(file_path) in self._success_cache

    # ========== 补充元数据 ==========

    def _supplement_all_metadata(self):
        """补充元数据"""
        logger.info("[补充元数据] ========== 开始补充元数据 ==========")
        if not self._dirconf:
            logger.warning("[补充元数据] 无监控配置，跳过")
            return

        try:
            total_processed = 0
            for source_dir, target_dir in self._dirconf.items():
                if not self._enabled:
                    logger.warning("[补充元数据] 插件已禁用，停止")
                    break

                target_path = Path(target_dir)
                if not target_path.exists():
                    logger.warning(f"[补充元数据] 目标目录不存在: {target_dir}")
                    continue

                logger.info(f"[补充元数据] 处理目标目录: {target_dir}")
                
                for tv_folder in target_path.iterdir():
                    if not tv_folder.is_dir():
                        continue

                    has_video = any(f.suffix.lower() in settings.RMT_MEDIAEXT for f in tv_folder.iterdir() if f.is_file())
                    if not has_video:
                        logger.debug(f"[补充元数据] 跳过无视频目录: {tv_folder.name}")
                        continue

                    title = tv_folder.name
                    logger.info(f"[补充元数据] 处理剧集: {title}")
                    
                    video_path = None
                    for ext in settings.RMT_MEDIAEXT:
                        video_files = list(tv_folder.glob(f"*{ext}")) + list(tv_folder.glob(f"*{ext.upper()}"))
                        if video_files:
                            video_path = video_files[0]
                            break
                    
                    merged_data = self.merge_search_results(title, source_dir, video_path)
                    nfo_path = tv_folder / "tvshow.nfo"
                    self._write_nfo(nfo_path, merged_data)

                    poster_url = merged_data.get("poster_url", "")
                    if poster_url:
                        self._download_image(poster_url, tv_folder / "poster.jpg")
                    
                    total_processed += 1

            logger.info(f"[补充元数据] ✅ 完成，处理 {total_processed} 个剧集")
        except Exception as e:
            logger.error(f"[补充元数据] ❌ 异常: {e}", exc_info=True)

    # ========== 通知 ==========

    def _add_notify(self, title: str, file_path: str):
        with self._lock:
            if title not in self._medias:
                self._medias[title] = {"files": [], "time": datetime.datetime.now()}
                logger.debug(f"[通知] 创建通知组: {title}")
            if file_path not in self._medias[title]["files"]:
                self._medias[title]["files"].append(file_path)
                logger.debug(f"[通知] 添加文件到通知组: {title}, 当前 {len(self._medias[title]['files'])} 个文件")

    def _send_notifications(self):
        with self._lock:
            if not self._medias:
                return

            logger.debug(f"[通知] 检查待发送通知，共 {len(self._medias)} 个组")
            now = datetime.datetime.now()
            for title, data in list(self._medias.items()):
                if (now - data["time"]).total_seconds() > self._interval:
                    logger.info(f"[通知] 发送通知: {title}, 文件数: {len(data['files'])}")
                    self.post_message(
                        mtype=NotificationType.Organize,
                        title=f"{title} 已入库",
                        text=f"共 {len(data['files'])} 个文件\n转移方式: {self._transfer_type}"
                    )
                    del self._medias[title]

    # ========== 记录管理 ==========

    def _record_success(self, file_path: str, title: str, target_path: str, source: str = None):
        with self._lock:
            actual_source = source if source is not None else self._last_source
            self._success_cache[file_path] = {
                'file_path': file_path, 
                'title': title, 
                'target_path': target_path,
                'timestamp': datetime.datetime.now().isoformat(), 
                'source': actual_source
            }
            while len(self._success_cache) > MAX_CACHE_SIZE:
                removed_key = next(iter(self._success_cache))
                del self._success_cache[removed_key]
                logger.debug(f"[记录] 清理旧成功记录: {removed_key}")
            logger.debug(f"[记录] 记录成功处理: {file_path} -> {title} (来源: {actual_source})")

    def _record_failure(self, file_path: str, error_msg: str):
        with self._lock:
            self._failed_records.append({
                'file_path': file_path, 'error_msg': error_msg,
                'timestamp': datetime.datetime.now().isoformat()
            })
            if len(self._failed_records) > MAX_CACHE_SIZE:
                removed = self._failed_records.pop(0)
                logger.debug(f"[记录] 清理旧失败记录: {removed['file_path']}")
            self._stats['total_processed'] += 1
            self._stats['failed_count'] += 1
            logger.warning(f"[记录] 记录失败处理: {file_path} - {error_msg[:100]}")

    @staticmethod
    def _title_match(a: str, b: str) -> bool:
        if not a or not b:
            return False

        def norm(s):
            return re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', s).lower()

        result = norm(a) == norm(b) or SequenceMatcher(None, norm(a), norm(b)).ratio() >= 0.85
        return result

    @staticmethod
    def _read_file(file_path: Path) -> Optional[str]:
        try:
            raw_data = file_path.read_bytes()
            if not raw_data:
                return None
            detected = chardet.detect(raw_data)
            encoding = detected.get('encoding', 'utf-8') if detected else 'utf-8'
            return raw_data.decode(encoding, errors='replace')
        except Exception as e:
            logger.debug(f"[文件读取] 读取失败 {file_path}: {e}")
            return None

    # ========== 远程命令 ==========

    def get_command(self) -> List[Dict[str, Any]]:
        return [
            {"cmd": "/shortplay_stats", "event": EventType.PluginAction, "desc": "查看统计",
             "category": "短剧处理", "data": {"action": "shortplay_stats"}},
            {"cmd": "/shortplay_clear", "event": EventType.PluginAction, "desc": "清空缓存",
             "category": "短剧处理", "data": {"action": "shortplay_clear"}},
            {"cmd": "/shortplay_scan", "event": EventType.PluginAction, "desc": "立即扫描",
             "category": "短剧处理", "data": {"action": "shortplay_scan"}},
            {"cmd": "/shortplay_supplement", "event": EventType.PluginAction, "desc": "补充元数据",
             "category": "短剧处理", "data": {"action": "shortplay_supplement"}},
        ]

    def get_api(self) -> List[Dict[str, Any]]:
        return []

    @eventmanager.register(EventType.PluginAction)
    def handle_command(self, event: Event):
        action = (event.event_data or {}).get("action")
        logger.info(f"[命令] 收到命令: {action}")
        
        if action == "shortplay_stats":
            result = self.show_stats()
        elif action == "shortplay_clear":
            result = self.clear_cache()
        elif action == "shortplay_scan":
            result = self.force_scan()
        elif action == "shortplay_supplement":
            result = self.force_supplement()
        else:
            logger.warning(f"[命令] 未知命令: {action}")
            return
        
        logger.info(f"[命令] 命令执行结果: {result[:50]}...")
        self.post_message(title="短剧处理器", text=result, mtype=NotificationType.Organize)

    def show_stats(self) -> str:
        with self._lock:
            s = self._stats
        
        result = (
            f"📊 短剧处理器统计\n"
            f"总处理: {s['total_processed']} | 成功: {s['success_count']} | 失败: {s['failed_count']}\n"
            f"缓存: 成功{len(self._success_cache)} | 系列{len(self._series_cache)} | 失败{len(self._failed_records)}\n"
            f"处理中: {len(self._processing_files)}\n"
            f"API: MP识别{s.get('mp_calls',0)}/{s.get('mp_hits',0)} | PT搜索{s.get('pt_calls',0)}/{s.get('pt_hits',0)} | NFO{s.get('nfo_calls',0)}/{s.get('nfo_hits',0)}"
        )
        logger.debug(f"[统计] {result}")
        return result

    def clear_cache(self) -> str:
        logger.info("[清理] 清空所有缓存")
        with self._lock:
            cache_sizes = {
                'success': len(self._success_cache),
                'series': len(self._series_cache),
                'failed': len(self._failed_records),
                'processing': len(self._processing_files),
                'medias': len(self._medias),
                'mapping': len(self._title_mapping)
            }
            logger.debug(f"[清理] 清空前缓存大小: {cache_sizes}")
            
            self._success_cache.clear()
            self._series_cache.clear()
            self._failed_records.clear()
            self._processing_files.clear()
            self._medias.clear()
            self._title_mapping.clear()  # 清空映射
        
        self._save_cache()
        logger.info("[清理] 缓存已清空")
        return "✅ 缓存已清空"

    def force_scan(self) -> str:
        logger.info("[命令] 手动触发扫描任务")
        threading.Thread(target=self.scan_all_dirs, daemon=True).start()
        return "✅ 扫描任务已启动"

    def force_supplement(self) -> str:
        logger.info("[命令] 手动触发补充元数据任务")
        threading.Thread(target=self._supplement_all_metadata, daemon=True).start()
        return "✅ 补充元数据任务已启动"

    # ========== 配置页面 ==========

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [
            {
                "component": "VForm",
                "content": [{
                    "component": "VRow",
                    "content": [
                        {"component": "VCol", "props": {"cols": 12}, "content": [
                            {"component": "VSwitch", "props": {"model": "enabled", "label": "启用插件"}},
                            {"component": "VSwitch", "props": {"model": "onlyonce", "label": "立即运行一次"}},
                            {"component": "VSwitch", "props": {"model": "supplement", "label": "补充元数据"}},
                        ]},
                        {"component": "VCol", "props": {"cols": 12}, "content": [
                            {"component": "VTextarea", "props": {"model": "monitor_confs", "label": "监控配置",
                                "rows": 5, "placeholder": "模式#源目录#目标目录#重命名\n模式: normal/compatibility\n重命名: smart/off"}},
                        ]},
                        {"component": "VCol", "props": {"cols": 6}, "content": [
                            {"component": "VSelect", "props": {"model": "transfer_type", "label": "转移方式",
                                "items": [{"title": "移动", "value": "move"}, {"title": "复制", "value": "copy"},
                                          {"title": "硬链接", "value": "link"}, {"title": "软链接", "value": "softlink"}]}},
                        ]},
                        {"component": "VCol", "props": {"cols": 6}, "content": [
                            {"component": "VSwitch", "props": {"model": "notify", "label": "发送通知"}},
                            {"component": "VTextField", "props": {"model": "interval", "label": "通知间隔(秒)", "type": "number"}},
                        ]},
                        {"component": "VCol", "props": {"cols": 12}, "content": [
                            {"component": "VTextarea", "props": {"model": "exclude_keywords", "label": "排除关键词",
                                "rows": 2, "placeholder": "每行一个正则"}},
                        ]},
                        {"component": "VCol", "props": {"cols": 6}, "content": [
                            {"component": "VSwitch", "props": {"model": "scan_enabled", "label": "定时扫描"}},
                            {"component": "VTextField", "props": {"model": "scan_interval", "label": "扫描间隔(秒)", "type": "number"}},
                        ]},
                        {"component": "VCol", "props": {"cols": 6}, "content": [
                            {"component": "VSwitch", "props": {"model": "enable_incremental_scan", "label": "增量扫描"}},
                        ]},
                        {"component": "VCol", "props": {"cols": 12}, "content": [
                            {"component": "VDivider"},
                            {"component": "VSwitch", "props": {"model": "enable_local_nfo", "label": "本地NFO"}},
                            {"component": "VSwitch", "props": {"model": "enable_mp_recognition", "label": "MP识别"}},
                            {"component": "VSwitch", "props": {"model": "enable_pt_search", "label": "PT站搜索"}},
                            {"component": "VTextField", "props": {"model": "pt_priority", "label": "PT优先级", "placeholder": "agsv,ilolicon"}},
                            {"component": "VTextField", "props": {"model": "media_root", "label": "媒体库根目录", "placeholder": "/path/to/media"}},
                        ]},
                        {"component": "VCol", "props": {"cols": 6}, "content": [
                            {"component": "VTextField", "props": {"model": "polling_interval", "label": "轮询间隔(秒)", "type": "number"}},
                        ]},
                        {"component": "VCol", "props": {"cols": 6}, "content": [
                            {"component": "VTextField", "props": {"model": "debounce_max_wait", "label": "防抖等待(秒)", "type": "number"}},
                        ]},
                    ]
                }]
            }
        ], {
            "enabled": False, "onlyonce": False, "supplement": False,
            "monitor_confs": "", "transfer_type": "link",
            "exclude_keywords": "", "notify": False, "interval": 10,
            "scan_interval": 60, "scan_enabled": True,
            "enable_local_nfo": True, "enable_mp_recognition": True,
            "enable_pt_search": True, "pt_priority": "",
            "polling_interval": 5, "debounce_max_wait": 10.0,
            "enable_incremental_scan": True, "media_root": ""
        }

    def get_page(self) -> List[dict]:
        """数据面板"""
        with self._lock:
            s = dict(self._stats)
            cache_size = len(self._success_cache)
            series_size = len(self._series_cache)
            failed_size = len(self._failed_records)
            processing = len(self._processing_files)
            recent_success = [v for v in list(self._success_cache.values())[-8:] if isinstance(v, dict)]
            recent_failed = [v for v in self._failed_records[-8:] if isinstance(v, dict)]

        logger.debug(f"[面板] 渲染数据面板 - 成功: {cache_size}, 系列: {series_size}, 失败: {failed_size}")

        def fmt_time(ts):
            try:
                dt = datetime.datetime.fromisoformat(ts) if isinstance(ts, str) else ts
                return dt.strftime("%m-%d %H:%M") if dt else "-"
            except Exception:
                return "-"

        mp_rate = round(s.get('mp_hits', 0) / max(1, s.get('mp_calls', 1)) * 100)
        pt_rate = round(s.get('pt_hits', 0) / max(1, s.get('pt_calls', 1)) * 100)
        nfo_rate = round(s.get('nfo_hits', 0) / max(1, s.get('nfo_calls', 1)) * 100)

        return [
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 6, "md": 3},
                        "content": [{"component": "VCard", "props": {"variant": "tonal", "color": "primary"}, "content": [
                            {"component": "VCardText", "props": {"class": "text-center"}, "content": [
                                {"component": "div", "props": {"class": "text-h4"}, "text": str(s['total_processed'])},
                                {"component": "div", "props": {"class": "text-caption"}, "text": "总处理"},
                            ]}
                        ]}]
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 6, "md": 3},
                        "content": [{"component": "VCard", "props": {"variant": "tonal", "color": "success"}, "content": [
                            {"component": "VCardText", "props": {"class": "text-center"}, "content": [
                                {"component": "div", "props": {"class": "text-h4"}, "text": str(s['success_count'])},
                                {"component": "div", "props": {"class": "text-caption"}, "text": "成功"},
                            ]}
                        ]}]
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 6, "md": 3},
                        "content": [{"component": "VCard", "props": {"variant": "tonal", "color": "error"}, "content": [
                            {"component": "VCardText", "props": {"class": "text-center"}, "content": [
                                {"component": "div", "props": {"class": "text-h4"}, "text": str(s['failed_count'])},
                                {"component": "div", "props": {"class": "text-caption"}, "text": "失败"},
                            ]}
                        ]}]
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 6, "md": 3},
                        "content": [{"component": "VCard", "props": {"variant": "tonal", "color": "warning"}, "content": [
                            {"component": "VCardText", "props": {"class": "text-center"}, "content": [
                                {"component": "div", "props": {"class": "text-h4"}, "text": str(processing)},
                                {"component": "div", "props": {"class": "text-caption"}, "text": "处理中"},
                            ]}
                        ]}]
                    },
                ]
            },
            {
                "component": "VRow",
                "props": {"class": "mt-2"},
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12},
                        "content": [{"component": "VCard", "props": {"variant": "tonal", "color": "info"}, "content": [
                            {"component": "VCardTitle", "text": "💾 缓存状态"},
                            {"component": "VCardText", "content": [
                                {"component": "VRow", "content": [
                                    {"component": "VCol", "props": {"cols": 4}, "content": [
                                        {"component": "div", "props": {"class": "text-center"}, "content": [
                                            {"component": "div", "props": {"class": "text-h5 text-success"}, "text": str(cache_size)},
                                            {"component": "div", "props": {"class": "text-caption"}, "text": "成功记录"},
                                        ]}
                                    ]},
                                    {"component": "VCol", "props": {"cols": 4}, "content": [
                                        {"component": "div", "props": {"class": "text-center"}, "content": [
                                            {"component": "div", "props": {"class": "text-h5 text-primary"}, "text": str(series_size)},
                                            {"component": "div", "props": {"class": "text-caption"}, "text": "系列信息"},
                                        ]}
                                    ]},
                                    {"component": "VCol", "props": {"cols": 4}, "content": [
                                        {"component": "div", "props": {"class": "text-center"}, "content": [
                                            {"component": "div", "props": {"class": "text-h5 text-error"}, "text": str(failed_size)},
                                            {"component": "div", "props": {"class": "text-caption"}, "text": "失败记录"},
                                        ]}
                                    ]},
                                ]},
                                {"component": "div", "props": {"class": "text-caption text-center mt-2"}, "text": f"启动: {fmt_time(s.get('start_time'))} | 上次处理: {fmt_time(s.get('last_process_time'))} | 模式: {'增量' if self._enable_incremental_scan else '全量'}"},
                            ]}
                        ]}]
                    },
                ]
            },
            {
                "component": "VRow",
                "props": {"class": "mt-2"},
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12},
                        "content": [{"component": "VCard", "props": {"variant": "tonal", "color": "success"}, "content": [
                            {"component": "VCardTitle", "text": "🎯 数据源命中率"},
                            {"component": "VCardText", "content": [
                                {"component": "div", "props": {"class": "mb-2"}, "content": [
                                    {"component": "div", "props": {"class": "text-caption mb-1"}, "text": f"MP识别: {s.get('mp_hits',0)}/{s.get('mp_calls',0)} ({mp_rate}%)"},
                                    {"component": "VProgressLinear", "props": {"modelValue": mp_rate, "color": "primary", "height": 8, "rounded": True}},
                                ]},
                                {"component": "div", "props": {"class": "mb-2"}, "content": [
                                    {"component": "div", "props": {"class": "text-caption mb-1"}, "text": f"PT搜索: {s.get('pt_hits',0)}/{s.get('pt_calls',0)} ({pt_rate}%)"},
                                    {"component": "VProgressLinear", "props": {"modelValue": pt_rate, "color": "success", "height": 8, "rounded": True}},
                                ]},
                                {"component": "div", "content": [
                                    {"component": "div", "props": {"class": "text-caption mb-1"}, "text": f"本地NFO: {s.get('nfo_hits',0)}/{s.get('nfo_calls',0)} ({nfo_rate}%)"},
                                    {"component": "VProgressLinear", "props": {"modelValue": nfo_rate, "color": "warning", "height": 8, "rounded": True}},
                                ]},
                            ]}
                        ]}]
                    },
                ]
            },
            {
                "component": "VRow",
                "props": {"class": "mt-2"},
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12},
                        "content": [{"component": "VCard", "props": {"variant": "tonal", "color": "success"}, "content": [
                            {"component": "VCardTitle", "text": "✅ 最近成功"},
                            {"component": "VCardText", "props": {"class": "pa-0"}, "content": [
                                {"component": "VTable", "props": {"hover": True, "dense": True}, "content": [
                                    {"component": "thead", "content": [
                                        {"component": "tr", "content": [
                                            {"component": "th", "text": "时间"},
                                            {"component": "th", "text": "剧名"},
                                            {"component": "th", "text": "剧集名"},
                                            {"component": "th", "text": "原始路径"},
                                            {"component": "th", "text": "识别来源"},
                                        ]}
                                    ]},
                                    {"component": "tbody", "content": [
                                        {"component": "tr", "content": [
                                            {"component": "td", "text": fmt_time(r.get('timestamp'))},
                                            {"component": "td", "text": r.get('title', '-')},
                                            {"component": "td", "text": Path(r.get('target_path', '-')).name},
                                            {"component": "td", "props": {"style": "max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"}, "text": f"{Path(r.get('file_path', '-')).parent.name}/{Path(r.get('file_path', '-')).name}"},
                                            {"component": "td", "text": r.get('source', '-')},
                                        ]} for r in reversed(recent_success)
                                    ] if recent_success else [
                                        {"component": "tr", "content": [
                                            {"component": "td", "props": {"colspan": 5, "class": "text-center text-caption"}, "text": "暂无记录"}
                                        ]}
                                    ]}
                                ]}
                            ]}
                        ]}]
                    },
                ]
            },
            {
                "component": "VRow",
                "props": {"class": "mt-2"},
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12},
                        "content": [{"component": "VCard", "props": {"variant": "tonal", "color": "error"}, "content": [
                            {"component": "VCardTitle", "text": "❌ 最近失败"},
                            {"component": "VCardText", "props": {"class": "pa-0"}, "content": [
                                {"component": "VTable", "props": {"hover": True, "dense": True}, "content": [
                                    {"component": "thead", "content": [
                                        {"component": "tr", "content": [
                                            {"component": "th", "text": "时间"},
                                            {"component": "th", "text": "文件"},
                                            {"component": "th", "text": "错误"},
                                        ]}
                                    ]},
                                    {"component": "tbody", "content": [
                                        {"component": "tr", "content": [
                                            {"component": "td", "text": fmt_time(r.get('timestamp'))},
                                            {"component": "td", "props": {"style": "max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"}, "text": Path(r.get('file_path', '-')).name},
                                            {"component": "td", "props": {"style": "max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"}, "text": r.get('error_msg', '-')},
                                        ]} for r in reversed(recent_failed)
                                    ] if recent_failed else [
                                        {"component": "tr", "content": [
                                            {"component": "td", "props": {"colspan": 3, "class": "text-center text-caption"}, "text": "暂无记录"}
                                        ]}
                                    ]}
                                ]}
                            ]}
                        ]}]
                    },
                ]
            },
        ]