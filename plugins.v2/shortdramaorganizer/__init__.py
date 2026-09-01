"""
短剧整理器 (ShortDramaOrganizerPlugin)
MoviePilot插件：自动获取短剧种子、筛选下载、独立监控、识别整理、同步删除
"""

import os
import re
import json
import shutil
import time
import threading
import datetime
import fnmatch
from pathlib import Path
from typing import Any, List, Dict, Tuple, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, Future, as_completed

import chardet
from lxml import etree
from lxml.etree import Element, SubElement, tostring, parse
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import text
from app.core.config import settings
from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType, NotificationType, MediaType
from app.utils.http import RequestUtils
from app.utils.system import SystemUtils
from collections import OrderedDict
from app.core.metainfo import MetaInfo
from app.api.endpoints.plugin import register_plugin_api, PLUGIN_PREFIX
from fastapi import Request

# 尝试导入可选依赖
try:
    from app.core.cache import TTLCache
    HAS_TTLCACHE = True
except ImportError:
    HAS_TTLCACHE = False
    logger.warning("[短剧整理器] TTLCache不可用，将使用内置简单缓存")

try:
    from app.monitor import Monitor
    HAS_MONITOR = True
except ImportError:
    HAS_MONITOR = False
    logger.warning("[短剧整理器] 系统Monitor不可用，将使用内置监控")

try:
    from app.db.site_oper import SiteOper
    from app.helper.sites import SitesHelper
    from app.helper.downloader import DownloaderHelper
    from app.modules.indexer.spider import SiteSpider
    from app.chain.torrents import TorrentsChain
    from app.chain.media import MediaChain
    HAS_FRAMEWORK = True
except ImportError as e:
    HAS_FRAMEWORK = False
    logger.warning(f"[短剧整理器] 部分框架模块不可用: {e}")


# ==================== 常量 ====================

SYSTEM_FOLDERS = {
    '@Recycle', '#recycle', '@eaDir', 'System Volume Information',
    '$RECYCLE.BIN', '.DS_Store', 'Thumbs.db'
}

EPISODE_PATTERNS = [
    re.compile(r'[sS](\d+)[eE](\d+)'),
    re.compile(r'[eE][pP]?(\d+)'),
    re.compile(r'第\s*(\d+)\s*集'),
    ]

DEFAULT_PT_SITES = [
    {
        "domain": "agsvpt.com",
        "name": "AGSV",
        "search_url": "https://www.agsvpt.com/torrents.php?search_mode=0&search_area=0&page=0&notnewword=1&cat={cat}&search={title}",
        "params": {"cat": "419"},
    },
    {
        "domain": "ilolicon.com",
        "name": "萝莉站",
        "search_url": "https://share.ilolicon.com/torrents.php?search_mode=0&search_area=0&page=0&notnewword=1&cat={cat}&search={title}",
        "params": {"cat": "402"},
    },
    {
        "domain": "ptskit.org",
        "name": "PTSKit",
        "search_url": "https://www.ptskit.org/torrents.php?search_mode=0&search_area=0&page=0&notnewword=1&tag_id={tag_id}&search={title}",
        "params": {"tag_id": "238"},
    }
]


# ==================== 简单缓存（TTLCache 替代） ====================

class SimpleTTLCache:
    """简单的TTL缓存，使用定期清理"""
    
    def __init__(self, maxsize: int = 1000, ttl: int = 60):
        self.maxsize = maxsize
        self.ttl = ttl
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.RLock()
        self._last_cleanup = time.time()
        self._cleanup_interval = 30  # 每30秒清理一次
    
    def __contains__(self, key: str) -> bool:
        with self._lock:
            self._try_cleanup()
            if key in self._cache:
                value, timestamp = self._cache[key]
                if time.time() - timestamp < self.ttl:
                    return True
                del self._cache[key]
            return False
    
    def __setitem__(self, key: str, value: Any):
        with self._lock:
            self._try_cleanup()
            if len(self._cache) >= self.maxsize:
                # 删除最旧的（可能会删除过期项）
                self._cache.popitem(last=False)
            self._cache[key] = (value, time.time())
    
    def __getitem__(self, key: str) -> Any:
        with self._lock:
            self._try_cleanup()
            if key in self._cache:
                value, timestamp = self._cache[key]
                if time.time() - timestamp < self.ttl:
                    return value
                del self._cache[key]
            raise KeyError(key)
    
    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default
    
    def clear(self):
        """清空所有缓存"""
        with self._lock:
            self._cache.clear()
            self._last_cleanup = time.time()
            logger.debug(f"[SimpleTTLCache] 缓存已清空")
    
    def _try_cleanup(self):
        """定期执行完整清理"""
        now = time.time()
        if now - self._last_cleanup >= self._cleanup_interval:
            self._evict_expired()
            self._last_cleanup = now
    
    def _evict_expired(self):
        """删除所有过期项"""
        now = time.time()
        # 使用列表推导收集过期key
        expired = [k for k, (_, ts) in self._cache.items() if now - ts >= self.ttl]
        for k in expired:
            del self._cache[k]
        
        # 如果清理后仍然超出最大大小，删除最旧的
        while len(self._cache) > self.maxsize:
            self._cache.popitem(last=False)


# ==================== 配置类 ====================

class ShortDramaConfig:
    """短剧整理器配置"""
    
    def __init__(self, config: dict = None):
        config = config or {}
        
        self.enabled: bool = config.get("enabled", False)
        self.onlyonce: bool = config.get("onlyonce", False)
        self.organize_once: bool = config.get("organize_once", False)
        self.refresh_interval: int = config.get("refresh_interval", 30)
        self.notify_enabled: bool = config.get("notify_enabled", True)
        
        self.sites: List[str] = config.get("sites", [])
        
        self.whitelist_keywords: List[str] = self._parse_keywords(config.get("whitelist_keywords", ["短剧", "微短剧", "竖屏剧"]))
        self.blacklist_keywords: List[str] = self._parse_keywords(config.get("blacklist_keywords", ["欧美", "日剧", "韩剧", "电影", "动漫"]))
        self.min_size: int = int(config.get("min_size", 200) or 200)
        self.max_size: int = int(config.get("max_size", 2048) or 2048)
        self.min_seeders: int = int(config.get("min_seeders", 1) or 1)
        self.freeleech: str = config.get("freeleech", "free")
        self.exclude_hr: bool = config.get("exclude_hr", True)
        
        self.download_path: str = config.get("download_path", "")
        self.download_tags: List[str] = config.get("download_tags", ["短剧整理器"])
        self.downloader: str = config.get("downloader", "")
        
        raw_paths = config.get("monitor_path", "")
        if isinstance(raw_paths, str):
            self.monitor_paths: List[str] = [p.strip() for p in raw_paths.split("\n") if p.strip()]
        else:
            self.monitor_paths: List[str] = list(raw_paths) if raw_paths else []
        self.monitor_mode: str = config.get("monitor_mode", "normal")
        self.exclude_patterns: List[str] = config.get("exclude_patterns", ["*.sample", "*.nfo", "临时/"])
        self.recursive: bool = config.get("recursive", True)
        self.incremental_scan: bool = config.get("incremental_scan", True)
        
        self.transfer_type: str = config.get("transfer_type", "link")
        self.media_library: str = config.get("media_library", "")
        self.subdir: str = config.get("subdir", "短剧")
        self.media_type: str = config.get("media_type", "电视剧")
        self.category: str = config.get("category", "短剧")
        
        self.pt_sites: List[Dict] = config.get("pt_sites", DEFAULT_PT_SITES)
        self.pt_enabled: bool = config.get("pt_enabled", True)
        
        self.delete_enabled: bool = config.get("delete_enabled", False)
        self.clear_stats: bool = config.get("clear_stats", False)
        self.clear_history: bool = config.get("clear_history", False)
        self.clear_cache: bool = config.get("clear_cache", False)
        
        self.polling_interval: int = config.get("polling_interval", 5)
        self.retry_count: int = config.get("retry_count", 3)
        self.retry_interval: int = config.get("retry_interval", 5)
        self.use_proxy: bool = config.get("use_proxy", False)
        self.debounce_time: int = config.get("debounce_time", 3)
    
    @staticmethod
    def _parse_keywords(value) -> List[str]:
        """解析关键词配置，支持列表和逗号/换行分隔的字符串"""
        if isinstance(value, str):
            return [k.strip() for k in value.replace("\n", ",").split(",") if k.strip()]
        if isinstance(value, list):
            return [k.strip() for k in value if k.strip()]
        return []
    
    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "onlyonce": self.onlyonce,
            "organize_once": self.organize_once,
            "refresh_interval": self.refresh_interval,
            "notify_enabled": self.notify_enabled,
            "sites": self.sites,
            "whitelist_keywords": ",".join(self.whitelist_keywords),
            "blacklist_keywords": ",".join(self.blacklist_keywords),
            "min_size": self.min_size,
            "max_size": self.max_size,
            "min_seeders": self.min_seeders,
            "freeleech": self.freeleech,
            "exclude_hr": self.exclude_hr,
            "download_path": self.download_path,
            "download_tags": self.download_tags,
            "downloader": self.downloader,
            "monitor_path": "\n".join(self.monitor_paths),
            "monitor_mode": self.monitor_mode,
            "exclude_patterns": self.exclude_patterns,
            "recursive": self.recursive,
            "incremental_scan": self.incremental_scan,
            "transfer_type": self.transfer_type,
            "media_library": self.media_library,
            "subdir": self.subdir,
            "media_type": self.media_type,
            "category": self.category,
            "pt_sites": self.pt_sites,
            "pt_enabled": self.pt_enabled,
            "delete_enabled": self.delete_enabled,
            "clear_history": self.clear_history,
            "polling_interval": self.polling_interval,
            "retry_count": self.retry_count,
            "retry_interval": self.retry_interval,
            "use_proxy": self.use_proxy,
            "debounce_time": self.debounce_time,
        }


# ==================== 短剧识别器 ====================

class ShortDramaRecognizer:
    """短剧识别器 - 从文件夹名提取剧名，从文件名提取集数"""
    
    @staticmethod
    def extract_title(folder_name: str) -> str:
        """从文件夹名提取剧名"""
        if not folder_name:
            return ""
        
        title = folder_name.strip()
        
        # 移除开头的数字+横杠
        title = re.sub(r'^\d+[-－—]\s*', '', title)
        
        # 移除括号内容
        title = re.split(r'[（(]', title)[0]
        
        # 移除点号及后面的英文/数字后缀（如 .Tui.Hun.Zha.Nan.2024.S01.1080p...）
        title = re.sub(r'\..*', '', title)
        
        # 移除特殊字符
        title = re.sub(r'[\\/*?:"<>|]', '', title)
        
        return title.strip('. ')
    
    @staticmethod
    def extract_episode(filename: str) -> int:
        """从文件名提取集数"""
        if not filename:
            return 1
        
        name = Path(filename).stem
        
        for pattern in EPISODE_PATTERNS:
            match = pattern.search(name)
            if match:
                if match.group(0).startswith(('S', 's')) and len(match.groups()) >= 2:
                    return int(match.group(2))
                return int(match.group(1))
        
        digits = re.findall(r'\d+', name)
        if digits:
            episode = int(digits[-1])
            if 1 <= episode <= 200:
                return episode
        
        return 1
    
    @staticmethod
    def extract_season(filename: str) -> int:
        """提取季数（短剧默认1）"""
        match = re.search(r'[sS](\d+)[eE]', filename)
        if match:
            season = int(match.group(1))
            if 1 <= season <= 99:
                return season
        return 1
    
    def recognize(self, file_path: str) -> Optional[Dict]:
        """识别短剧信息"""
        path = Path(file_path)
        
        folder_title = self.extract_title(path.parent.name)
        if not folder_title:
            logger.warning(f"[短剧识别] 无法从文件夹名提取剧名: {path.parent.name}")
            return None
        
        return {
            "title": folder_title,
            "season": self.extract_season(path.name),
            "episode": self.extract_episode(path.name),
            "folder_name": path.parent.name,
            "file_name": path.name,
            "source_path": str(path)
        }


# ==================== PT站点信息补全 ====================

class PTInfoFetcher:
    """PT站点信息补全"""
    
    def __init__(self, config: ShortDramaConfig):
        self.config = config
        self._site_cache: Dict[str, Any] = {}
    
    def _get_page_source(self, url: str, site) -> Optional[str]:
        """获取页面源码"""
        try:
            ret = RequestUtils(
                cookies=site.cookie,
                timeout=30,
                proxies=settings.PROXY if self.config.use_proxy else None
            ).get_res(url, allow_redirects=True)
            
            if ret is None:
                return None
            
            raw_data = ret.content
            if raw_data:
                try:
                    result = chardet.detect(raw_data)
                    encoding = result['encoding'] if result else 'utf-8'
                    return raw_data.decode(encoding, errors='replace')
                except Exception:
                    if re.search(r"charset=\"?utf-8\"?", ret.text, re.IGNORECASE):
                        ret.encoding = "utf-8"
                    else:
                        ret.encoding = ret.apparent_encoding
                    return ret.text or ""
            
            return ret.text or ""
        
        except Exception as e:
            logger.error(f"[PT信息] 获取页面失败: {e}")
            return None
    
    def _get_site(self, domain: str) -> Optional[Any]:
        """获取站点"""
        if not HAS_FRAMEWORK:
            return None
        
        if domain not in self._site_cache:
            try:
                self._site_cache[domain] = SiteOper().get_by_domain(domain)
            except Exception as e:
                logger.error(f"[PT信息] 获取站点失败 {domain}: {e}")
                self._site_cache[domain] = None
        return self._site_cache[domain]
    def _extract_from_detail(self, html: etree._Element, config: dict) -> dict:
        """从详情页提取信息"""
        result = {}
        
        # 提取海报（硬编码方式）
        elements = html.xpath("//*[@id='kdescr']/img[1]/@src")
        if elements:
            result["poster_url"] = str(elements[0])
        
        # 2. 提取 kdescr 内容
        desc_elem = html.xpath("//*[@id='kdescr']")
        if desc_elem:
            full_text = desc_elem[0].xpath("string()").strip()
            if full_text:
                logger.debug(f"[PT信息] kdescr 内容: {full_text}")
            else:
                logger.debug("[PT信息] kdescr 内容为空")
                return result
        else:
            logger.debug("[PT信息] 未找到 kdescr 元素")
            return result
        
        # 直接用原有正则，两个站点都能匹配
        regex_map = {
            "title": r'片\s*名\s*[:：]?\s*([^\n]+)',
            "year": r'年\s*代\s*[:：]?\s*([^\n]+)',
            "country": r'产\s*地\s*[:：]?\s*([^\n]+)',
            "genres": r'类\s*别\s*[:：]?\s*([^\n]+)',
            "actors": r'主\s*演\s*[:：]?\s*([^\n]+)',
            "episodes": r'集\s*数\s*[:：]?\s*(\d+)',
            "overview": r'简\s*介\s*[:：]?\s*\n?\s*([^\n]+(?:\n[^\n]+)*?)(?=\n\s*\n|\s*◎|\s*引用|\s*General|$)',
        }
        
        for field, pattern in regex_map.items():
            match = re.search(pattern, full_text, re.IGNORECASE | re.DOTALL)
            if match:
                value = match.group(1).strip()
                if field == "genres":
                    result["genres"] = [g.strip() for g in re.split(r'[/、,，\s]+', value) if g.strip()]
                elif field == "actors":
                    result["actors"] = [a.strip() for a in re.split(r'[/、,，\s]+', value) if a.strip()]
                elif field == "episodes":
                    try:
                        result["episodes"] = int(value)
                    except ValueError:
                        pass
                elif field == "overview":
                    result["overview"] = re.sub(r'\s+', ' ', value).strip()
                else:
                    result[field] = value
        
        
        logger.info(f"[PT信息] 提取结果: {json.dumps({k: str(v)[:80] for k, v in result.items()}, ensure_ascii=False)}")
        return result
    
    def fetch(self, title: str, year: Optional[str] = None) -> Optional[Dict]:
        """从PT站点获取信息（并行搜索多个站点）"""
        if not self.config.pt_enabled or not HAS_FRAMEWORK:
            return None
        
        pt_sites = self.config.pt_sites or DEFAULT_PT_SITES
        merged: Dict[str, Any] = {}
        sources = []
        
        def _search_site(site_config: dict) -> Optional[Dict]:
            """单个站点搜索"""
            domain = site_config.get("domain")
            if not domain:
                return None
            
            site = self._get_site(domain)
            if not site:
                logger.debug(f"[PT信息] 站点未配置: {domain}")
                return None
            
            search_url = site_config.get("search_url", "")
            params = site_config.get("params", {}).copy()
            
            search_title = title
            if year and "agsvpt.com" in domain:
                search_title = f"{title} {year}"
            
            try:
                url = search_url.format(title=search_title, **params)
            except KeyError as e:
                logger.warning(f"[PT信息] {site_config.get('name')} URL格式化失败: {e}")
                return None
            
            logger.info(f"[PT信息] 搜索: {site_config.get('name')} - {title}")
            
            page_source = self._get_page_source(url, site)
            if not page_source:
                return None
            
            try:
                indexer = SitesHelper().get_indexer(domain)
                if not indexer:
                    logger.debug(f"[PT信息] 站点索引器不存在: {domain}")
                    return None
                spider = SiteSpider(indexer=indexer, page=1)
                torrents = spider.parse(page_source)
            except Exception as e:
                logger.debug(f"[PT信息] {site_config.get('name')} 解析失败: {e}")
                return None
            
            if not torrents:
                return None
            
            # 匹配最佳结果
            best_match = None
            best_score = 0
            for torrent in torrents:
                torrent_title = torrent.get("title", "")
                if not torrent_title:
                    continue
                if title.lower() in torrent_title.lower():
                    score = len(title) / len(torrent_title)
                    if score > best_score:
                        best_score = score
                        best_match = torrent
            
            if not best_match:
                best_match = torrents[0]
            
            detail_url = best_match.get("page_url")
            if not detail_url:
                return None
            
            detail_source = self._get_page_source(detail_url, site)
            if not detail_source:
                return None
            
            html = etree.HTML(detail_source)
            if html is None:
                return None
            
            info = self._extract_from_detail(html, site_config)
            if info:
                info["_source_name"] = site_config.get("name", domain)
            
            return info
        
        # 并行搜索所有站点
        with ThreadPoolExecutor(max_workers=min(len(pt_sites), 5)) as executor:
            futures = {executor.submit(_search_site, sc): sc for sc in pt_sites}
            for future in as_completed(futures):
                try:
                    info = future.result()
                    if info:
                        source_name = info.pop("_source_name", "未知")
                        sources.append(source_name)
                        logger.info(f"[PT信息] {source_name} 获取到: {json.dumps({k: str(v)[:80] for k, v in info.items()}, ensure_ascii=False)}")
                        
                        for key, value in info.items():
                            if value and not merged.get(key):
                                merged[key] = value
                            elif value and isinstance(value, list) and key in merged:
                                existing = set(merged[key])
                                for item in value:
                                    if item not in existing:
                                        merged[key].append(item)
                                        existing.add(item)
                except Exception as e:
                    logger.error(f"[PT信息] 站点搜索异常: {e}")
        
        if not merged:
            logger.warning(f"[PT信息] 所有站点搜索失败: {title}")
            return None
        
        merged["source"] = ", ".join(sources)
        logger.info(f"[PT信息] 合并结果 (来源: {merged['source']})")
        return merged


# ==================== 种子服务 ====================

class TorrentService:
    """种子服务 - 获取、筛选、下载"""
    
    def __init__(self, config: ShortDramaConfig):
        self.config = config
    
    def fetch(self) -> List:
        """浏览站点最新种子（使用系统 TorrentsChain）"""
        if not HAS_FRAMEWORK:
            logger.warning("[种子服务] 框架模块不可用")
            return []
        
        result = []
        for site_id in self.config.sites:
            try:
                site = SiteOper().get(int(site_id))
                if not site:
                    continue
                
                # 使用系统 TorrentsChain 获取种子
                torrents = TorrentsChain().browse(domain=site.domain)
                if not torrents:
                    continue
                
                # ⭐ 调试日志：打印前50个种子的原始属性
                logger.debug(f"[种子服务] ========== 原始种子调试 ==========")
                for idx, t in enumerate(torrents[:50]):
                    logger.debug(f"[种子服务] 种子 #{idx+1}:")
                    logger.debug(f"  title: {getattr(t, 'title', 'N/A')}")
                    logger.debug(f"  downloadvolumefactor: {getattr(t, 'downloadvolumefactor', 'N/A')}")
                    logger.debug(f"  uploadvolumefactor: {getattr(t, 'uploadvolumefactor', 'N/A')}")
                    logger.debug(f"  hit_and_run: {getattr(t, 'hit_and_run', 'N/A')}")
                    logger.debug(f"  seeders: {getattr(t, 'seeders', 'N/A')}")
                    logger.debug(f"  size: {getattr(t, 'size', 'N/A')}")
                    # 如果有 enclosure，也打印前50个字符
                    enc = getattr(t, 'enclosure', '')
                    logger.debug(f"  enclosure: {enc[:80] if enc else 'N/A'}")
                    logger.debug(f"  所有属性: {[attr for attr in dir(t) if not attr.startswith('_')]}")
                
                # 转换为 dict，保留所有筛选需要的字段
                for t in torrents:
                    result.append({
                        "title": getattr(t, 'title', ''),
                        "description": getattr(t, 'description', ''),
                        "labels": getattr(t, 'labels', ''),
                        "size": getattr(t, 'size', 0),
                        "seeders": getattr(t, 'seeders', 0),
                        "enclosure": getattr(t, 'enclosure', ''),
                        "page_url": getattr(t, 'page_url', ''),
                        "downloadvolumefactor": getattr(t, 'downloadvolumefactor', 1),
                        "uploadvolumefactor": getattr(t, 'uploadvolumefactor', 1),
                        "hit_and_run": getattr(t, 'hit_and_run', False),
                        "pubdate": getattr(t, 'pubdate', ''),
                    })
                
                logger.info(f"[种子服务] {site.name}: {len(torrents)} 个种子")
                if result:
                    logger.info(f"[种子服务] 第一个种子的 downloadvolumefactor: {result[0].get('downloadvolumefactor')}")
            except Exception as e:
                logger.error(f"[种子服务] 站点 {site_id} 获取失败: {e}")
        
        return result
    
    def filter(self, torrents: List) -> List:
        """筛选种子"""
        if not torrents:
            return []
        
        result = []
        for torrent in torrents:
            if self._check(torrent):
                result.append(torrent)
        
        logger.info(f"[种子服务] {len(torrents)} → {len(result)} 个通过筛选")
        return result
    
    def _check(self, torrent) -> bool:
        """检查单个种子"""
        # 统一从 dict 获取
        logger.debug(f"[筛选调试] torrent字典内容: {torrent}")
        if not isinstance(torrent, dict):
            logger.warning(f"[筛选] 非字典类型: {type(torrent)}")
            return False
        title = torrent.get('title', '') or ''
        description = torrent.get('description', '') or ''
        labels = torrent.get('labels', '') or ''
        size = float(torrent.get('size', 0) or 0)
        seeders = int(torrent.get('seeders', 0) or 0)
        download_factor = float(torrent.get('downloadvolumefactor', 1))
        upload_factor = float(torrent.get('uploadvolumefactor', 1))
        hit_and_run = bool(torrent.get('hit_and_run', False))
        logger.debug(f"[筛选调试] title={title[:30]}, download_factor={download_factor}, upload_factor={upload_factor}")

        
        combined = f"{title} {description} {labels}"
        
        # 白名单
        if self.config.whitelist_keywords:
            matched = False
            for keyword in self.config.whitelist_keywords:
                if keyword and keyword in combined:
                    matched = True
                    break
            if not matched:
                logger.debug(f"[筛选] 白名单未命中: {title[:50]}")
                return False
        
        # 黑名单
        if self.config.blacklist_keywords:
            for keyword in self.config.blacklist_keywords:
                if keyword and keyword in combined:
                    logger.debug(f"[筛选] 黑名单命中: {title[:50]} - {keyword}")
                    return False
        
        # 大小
        min_size = int(self.config.min_size or 0)
        max_size = int(self.config.max_size or 0)
        if min_size and size < min_size * 1024 * 1024:
            logger.debug(f"[筛选] 大小太小: {title[:50]} - {size/1024/1024:.1f}MB < {min_size}MB")
            return False
        if max_size and size > max_size * 1024 * 1024:
            logger.debug(f"[筛选] 太大: {title[:50]} - {size/1024/1024:.1f}MB > {max_size}MB")
            return False
        
        # 做种数
        min_seeders = int(self.config.min_seeders or 0)
        if min_seeders and seeders < min_seeders:
            logger.debug(f"[筛选] 做种数不足: {title[:50]} - {seeders} < {min_seeders}")
            return False
        
        # 促销（关键修复）
        if self.config.freeleech:
            if self.config.freeleech == "free" and download_factor != 0:
                logger.debug(f"[筛选] 非免费: {title[:50]} - download_factor={download_factor}")
                return False
            if self.config.freeleech == "2xfree":
                if download_factor != 0 or upload_factor != 2:
                    logger.debug(f"[筛选] 非2X免费: {title[:50]} - download_factor={download_factor}, upload_factor={upload_factor}")
                    return False
        
        # H&R
        if self.config.exclude_hr and hit_and_run:
            logger.debug(f"[筛选] H&R排除: {title[:50]}")
            return False
        
        return True
    
    def download(self, torrent) -> Optional[str]:
        """使用下载器下载种子，成功返回下载哈希，失败返回 None"""
        if isinstance(torrent, dict):
            enclosure = torrent.get('enclosure', '')
            title = torrent.get('title', '')
        else:
            enclosure = getattr(torrent, 'enclosure', '')
            title = getattr(torrent, 'title', '')
        
        if not enclosure:
            logger.error("[种子服务] 种子无下载链接")
            return None
        
        save_path = self.config.download_path
        if not save_path:
            logger.error("[种子服务] 未配置下载目录")
            return None
        
        downloader_name = self.config.downloader
        if not downloader_name:
            logger.error("[种子服务] 未选择下载器")
            return None
        
        tags = self.config.download_tags or ["短剧整理器"]
        
        # 1. 获取站点Cookie
        try:
            from urllib.parse import urlparse
            parsed = urlparse(enclosure)
            domain = parsed.netloc
            
            site = SiteOper().get_by_domain(domain)
            if not site:
                domain_parts = domain.split('.')
                if len(domain_parts) >= 2:
                    main_domain = '.'.join(domain_parts[-2:])
                    site = SiteOper().get_by_domain(main_domain)
            
            if not site or not site.cookie:
                logger.warning(f"[种子服务] 未找到站点 {domain} 的Cookie，可能无法下载种子")
                cookie = ""
            else:
                cookie = site.cookie
        except Exception as e:
            logger.warning(f"[种子服务] 获取站点Cookie失败: {e}")
            cookie = ""
        
        # 2. 下载种子文件
        try:
            response = RequestUtils(
                cookies=cookie,
                timeout=30,
                proxies=settings.PROXY if self.config.use_proxy else None
            ).get_res(enclosure)
            
            if not response or not response.content:
                logger.error("[种子服务] 下载种子文件失败")
                return None
            
            torrent_content = response.content
            
            content_sample = torrent_content[:20] if len(torrent_content) >= 20 else torrent_content
            if not (content_sample.startswith(b'd8:announce') or b'd8:announce' in content_sample):
                logger.error(f"[种子服务] 下载的内容不是有效的种子文件")
                return None
        except Exception as e:
            logger.error(f"[种子服务] 下载种子文件异常: {e}")
            return None
        
        # 3. 获取下载器实例并添加种子
        try:
            service = DownloaderHelper().get_service(name=downloader_name)
            if not service or not service.instance:
                logger.error(f"[种子服务] 下载器 {downloader_name} 不存在或未连接")
                return None
            
            dl = service.instance
            download_hash = None
            
            if DownloaderHelper().is_downloader("qbittorrent", service=service):
                success, hashes = dl.add_torrent(
                    content=torrent_content,
                    download_dir=save_path,
                    tag=",".join(tags)
                )
                if success:
                    download_hash = hashes[0] if hashes else None
                    logger.info(f"[种子服务] 下载成功: {title}, hash={download_hash}")
                else:
                    logger.error(f"[种子服务] qBittorrent 添加种子失败")
                    return None
            else:
                # Transmission
                result = dl.add_torrent(
                    content=torrent_content,
                    download_dir=save_path,
                    labels=tags
                )
                if result:
                    download_hash = getattr(result, 'hashString', None)
                    logger.info(f"[种子服务] 下载成功: {title}, hash={download_hash}")
                else:
                    logger.error(f"[种子服务] Transmission 添加种子失败")
                    return None
            
            return download_hash
        except Exception as e:
            logger.error(f"[种子服务] 下载异常: {e}")
            return None


# ==================== 整理器 ====================

class ShortDramaOrganizer:
    """短剧整理器 - 转移文件、生成NFO"""
    
    def __init__(self, config: ShortDramaConfig):
        self.config = config
    
    def organize(self, file_path: str, drama_info: dict) -> dict:
        """整理短剧"""
        try:
            source = Path(file_path)
            if not source.exists():
                return {"success": False, "error": f"源文件不存在: {file_path}"}
            
            target_path = self._build_target_path(drama_info)
            if not target_path:
                return {"success": False, "error": "无法构建目标路径"}
            
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 如果目标文件已存在且相同，跳过
            if target_path.exists():
                try:
                    if target_path.samefile(source):
                        logger.debug(f"[整理] 文件已存在且相同: {target_path}")
                        return {"success": True, "target_path": str(target_path)}
                except Exception:
                    pass
                
                # 目标文件已存在，跳过
                logger.debug(f"[整理] 目标文件已存在，跳过: {target_path}")
                return {"success": True, "target_path": str(target_path)}
            
            if not self._transfer_file(source, target_path):
                return {"success": False, "error": "文件转移失败"}
            
            # NFO 和海报存放在季目录的上级（剧名目录），与 Season 目录同级
            series_dir = target_path.parent.parent
            self._generate_nfo(series_dir, drama_info)
            
            # 海报已存在则跳过
            poster_path = series_dir / "poster.jpg"
            if not poster_path.exists():
                # 优先从源目录复制图片作为海报
                poster_saved = False
                source_dir = source.parent
                
                # 先找文件名包含 poster 关键字的图片
                for img_ext in ['.jpg', '.jpeg', '.png', '.webp']:
                    for img_file in source_dir.glob(f"*{img_ext}"):
                        if img_file.is_file() and 'poster' in img_file.stem.lower():
                            try:
                                shutil.copy2(str(img_file), str(poster_path))
                                logger.info(f"[海报] 从源目录复制（poster优先）: {img_file.name}")
                                poster_saved = True
                                break
                            except Exception as e:
                                logger.warning(f"[海报] 复制失败: {e}")
                    if poster_saved:
                        break
                
                # 没有 poster 关键字图片，则取第一张
                if not poster_saved:
                    for img_ext in ['.jpg', '.jpeg', '.png', '.webp']:
                        for img_file in source_dir.glob(f"*{img_ext}"):
                            if img_file.is_file():
                                try:
                                    shutil.copy2(str(img_file), str(poster_path))
                                    logger.info(f"[海报] 从源目录复制: {img_file.name}")
                                    poster_saved = True
                                    break
                                except Exception as e:
                                    logger.warning(f"[海报] 复制失败: {e}")
                        if poster_saved:
                            break
                
                # 没有本地图片则从 URL 下载
                if not poster_saved and drama_info.get("poster_url"):
                    self._download_poster(drama_info["poster_url"], poster_path)
            
            return {"success": True, "target_path": str(target_path)}
        
        except Exception as e:
            logger.error(f"[整理] 失败: {e}")
            return {"success": False, "error": str(e)}
    
    def _build_target_path(self, drama_info: dict) -> Optional[Path]:
        """构建目标路径"""
        title = drama_info.get("title", "未知短剧")
        season = drama_info.get("season", 1)
        episode = drama_info.get("episode", 1)
        
        media_library = self.config.media_library
        if not media_library:
            media_library = getattr(settings, 'MEDIA_LIBRARY_PATH', '')
        
        if not media_library:
            logger.error("[整理] 未配置媒体库路径")
            return None
        
        subdir = self.config.subdir or "短剧"
        safe_title = re.sub(r'[\\/*?:"<>|]', '', title).strip()
        
        target_dir = Path(media_library) / subdir / safe_title / f"Season {season:02d}"
        source_suffix = Path(drama_info.get('source_path', '')).suffix
        filename = f"S{season:02d}E{episode:02d}{source_suffix}"
        
        target = target_dir / filename
        logger.info(f"[整理] 目标路径: {target}")
        logger.info(f"[整理]   title={title} safe_title={safe_title} season={season} episode={episode} suffix={source_suffix}")
        return target
    
    def _transfer_file(self, source: Path, target: Path) -> bool:
        """转移文件
        
        Args:
            source: 源文件路径
            target: 目标文件路径
            
        Returns:
            bool: True 表示转移成功，False 表示转移失败
        """
        transfer_type = self.config.transfer_type or "link"
        
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            
            if target.exists():
                target.unlink()
            
            # 记录源文件大小（移动前）
            source_size = source.stat().st_size if source.exists() else 0
            
            # 执行转移操作
            if transfer_type == "move":
                SystemUtils.move(source, target)
            elif transfer_type == "copy":
                SystemUtils.copy(source, target)
            elif transfer_type == "softlink":
                SystemUtils.softlink(source, target)
            else:  # hard link
                SystemUtils.link(source, target)
            
            # 验证操作成功：目标文件必须存在
            if not target.exists():
                logger.error(f"[整理] 转移后目标文件不存在: {target}")
                return False
            
            # 对于复制操作，验证文件大小是否一致
            if transfer_type == "copy" and source_size > 0:
                try:
                    if target.stat().st_size != source_size:
                        logger.error(f"[整理] 文件大小不匹配: 源={source_size}, 目标={target.stat().st_size}")
                        return False
                except OSError as e:
                    logger.warning(f"[整理] 无法比较文件大小: {e}")
                    # 不因无法比较大小而失败
            
            # 对于移动操作，如果源文件还存在，验证其是否被删除或变小（移动后源文件不应存在）
            if transfer_type == "move":
                if source.exists():
                    try:
                        # 如果源文件还存在但大小变为0，可能是移动失败
                        if source.stat().st_size == 0:
                            logger.warning(f"[整理] 移动后源文件大小为0，可能移动失败: {source}")
                            return False
                    except OSError:
                        pass  # 无法访问源文件，可能已被移动
            
            logger.debug(f"[整理] 转移成功: {source} -> {target}")
            return True
            
        except Exception as e:
            logger.error(f"[整理] 转移失败: {source} -> {target}, 错误: {e}")
            return False
    
    def _generate_nfo(self, dir_path: Path, drama_info: dict):
        """生成NFO文件（仅首次写入，后续跳过）"""
        try:
            nfo_path = dir_path / "tvshow.nfo"
            
            # NFO 已存在则直接跳过，不再读取和比较
            if nfo_path.exists():
                logger.debug(f"[NFO] 已存在，跳过: {nfo_path}")
                return
            
            logger.info(f"[NFO] 目标路径: {nfo_path}")
            self._write_nfo(nfo_path, drama_info)
            logger.info(f"[NFO] 已生成: title={drama_info.get('title')}")
        
        except Exception as e:
            logger.error(f"[NFO] 生成失败: {e}")
    
    def _write_nfo(self, nfo_path: Path, info: dict):
        """写入NFO文件（使用 lxml.etree）"""
        try:
            root = Element("tvshow")
            
            # 标题
            title = info.get("title", "未知短剧")
            SubElement(root, "title").text = title
            SubElement(root, "originaltitle").text = title
            
            # 年份
            if info.get("year"):
                SubElement(root, "year").text = str(info["year"])
            
            # 简介
            if info.get("overview"):
                SubElement(root, "plot").text = info["overview"]
            
            # 类型
            genres = info.get("genres", [])
            if isinstance(genres, str):
                genres = [genres]
            for genre in genres:
                if genre:
                    SubElement(root, "genre").text = genre
            
            # 国家
            if info.get("country"):
                SubElement(root, "country").text = info["country"]
            
            # 演员
            actors = info.get("actors", [])
            if isinstance(actors, str):
                actors = [actors]
            for actor in actors:
                if actor:
                    actor_elem = SubElement(root, "actor")
                    SubElement(actor_elem, "name").text = actor
            
            # 演员标签（用于筛选）
            if actors:
                for actor in actors:
                    if actor:
                        SubElement(root, "tag").text = actor
            
            # 来源
            if info.get("source"):
                SubElement(root, "source").text = info["source"]
            
            # TMDB ID
            if info.get("tmdbid"):
                uniqueid = SubElement(root, "uniqueid")
                uniqueid.set("type", "tmdb")
                uniqueid.set("default", "true")
                uniqueid.text = str(info["tmdbid"])
            
            # 评分
            if info.get("rating"):
                SubElement(root, "rating").text = str(info["rating"])
            
            # 生成 XML
            xml_str = tostring(
                root,
                encoding='utf-8',
                pretty_print=True,
                xml_declaration=True
            )
            
            nfo_path.write_bytes(xml_str)
            logger.debug(f"[NFO] 写入成功: {nfo_path}")
            
        except Exception as e:
            logger.error(f"[NFO] 写入失败: {e}")
    
    @staticmethod
    def _get_text(root: Element, tag: str, default: str = "") -> str:
        """安全获取元素文本"""
        elem = root.find(tag)
        if elem is not None and elem.text:
            return elem.text.strip()
        return default
    
    def _download_poster(self, url: str, poster_path: Path):
        """下载海报"""
        try:
            if not url or poster_path.exists():
                return
            
            response = RequestUtils(timeout=30).get_res(url)
            if response and response.status_code == 200:
                poster_path.write_bytes(response.content)
                logger.debug(f"[海报] 下载成功: {poster_path}")
        except Exception as e:
            logger.error(f"[海报] 下载失败: {e}")


# ==================== 同步删除 (Webhook) ====================

class WebhookHandler:
    """同步删除处理器 - 根据 Emby 删除事件中的剧名匹配并删除下载器种子"""
    
    def __init__(self, config: ShortDramaConfig, plugin):
        self.config = config
        self.plugin = plugin
        
        # 使用TTLCache或简单缓存（防重）
        if HAS_TTLCACHE:
            self._processed = TTLCache(maxsize=1000, ttl=60)
        else:
            self._processed = SimpleTTLCache(maxsize=1000, ttl=60)
        
        # 缓存下载器实例
        self._downloader_cache = {}
        self._cache_ttl = 300
    
    def handle(self, data: dict) -> dict:
        """处理 Webhook 请求，用剧名匹配并删除种子"""
        try:
            # 解析 Emby 删除事件
            item = data.get("Item", {})
            item_type = item.get("Type", "")
            
            # 只处理 Series 和 Movie 类型
            if item_type not in ["Series", "Movie"]:
                logger.info(f"[Webhook] 跳过 {item_type} 类型删除事件")
                return {"code": 200, "message": f"跳过 {item_type} 类型"}
            
            # 提取剧名
            item_name = item.get("SeriesName") or item.get("Name", "")
            if not item_name:
                logger.warning("[Webhook] 无法提取剧名")
                return {"code": 400, "message": "无法提取剧名"}
            
            # 防重
            cache_key = f"delete_{item_name}"
            if cache_key in self._processed:
                logger.debug(f"[Webhook] 重复事件已忽略: {item_name}")
                return {"code": 200, "message": "重复事件已忽略"}
            self._processed[cache_key] = True
            
            logger.info(f"[Webhook] 收到删除事件: {item_name}")
            
            # 异步执行种子删除
            threading.Thread(
                target=self._delete_torrent,
                args=(item_name,),
                daemon=True
            ).start()
            
            return {"code": 200, "message": f"种子删除任务已启动: {item_name}"}
            
        except Exception as e:
            logger.error(f"[Webhook] 处理失败: {e}")
            return {"code": 500, "message": f"处理失败: {str(e)}"}
    
    def _get_downloader(self, name: str = None):
        """获取下载器实例，带缓存"""
        dl_name = name or self.config.downloader
        if not dl_name:
            logger.warning("[删除] 未配置下载器")
            return None
        
        now = time.time()
        if dl_name in self._downloader_cache:
            instance, cache_time = self._downloader_cache[dl_name]
            if now - cache_time < self._cache_ttl:
                try:
                    if not instance.is_inactive():
                        return instance
                except:
                    return instance
        
        try:
            service = DownloaderHelper().get_service(name=dl_name)
            if not service or not service.instance:
                logger.warning(f"[删除] 下载器 {dl_name} 不存在")
                return None
            
            instance = service.instance
            try:
                if instance.is_inactive():
                    logger.warning(f"[删除] 下载器 {dl_name} 未连接")
                    return None
            except:
                pass
            
            self._downloader_cache[dl_name] = (instance, now)
            return instance
            
        except Exception as e:
            logger.error(f"[删除] 获取下载器失败: {e}")
            return None
    
    def _delete_torrent(self, item_name: str):
        """根据剧名匹配并删除种子"""
        try:
            downloader = self._get_downloader()
            if not downloader:
                logger.warning("[删除] 下载器不可用，跳过删除种子")
                return
            
            logger.info(f"[删除] 开始搜索种子: {item_name}")
            torrents, error = downloader.get_torrents()
            if error:
                logger.error(f"[删除] 获取种子列表失败: {error}")
                return
            if not torrents:
                logger.debug("[删除] 下载器中没有种子任务")
                return
            
            matched_hashes = []
            matched_names = []
            for torrent in torrents:
                name = torrent.name if hasattr(torrent, 'name') else torrent.get("name", "")
                if not name:
                    continue
                
                # 模糊匹配：剧名在种子名称中
                if item_name.lower() in name.lower():
                    hash_str = torrent.hashString if hasattr(torrent, 'hashString') else torrent.get("hash", "")
                    if hash_str:
                        matched_hashes.append(hash_str)
                        matched_names.append(name)
            
            if not matched_hashes:
                logger.info(f"[删除] 未找到匹配的种子: {item_name}")
                return
            
            logger.info(f"[删除] 匹配到 {len(matched_hashes)} 个种子: {matched_names}")
            
            # 删除种子（含文件）
            for h in matched_hashes:
                try:
                    downloader.delete_torrents(ids=[h], delete_file=True)
                    logger.info(f"[删除] 已删除种子: {h[:8]}...")
                    # 立即更新种子数据
                    self.plugin._update_torrent_deleted(h)
                    # 删除对应的整理历史记录
                    self.plugin._delete_transfer_by_hash(h)
                except Exception as e:
                    logger.error(f"[删除] 删除种子失败 {h[:8]}...: {e}")
            
            logger.info(f"[删除] 删除完成: {item_name}, 共 {len(matched_hashes)} 个种子")
                
        except Exception as e:
            logger.error(f"[删除] 删除种子失败: {e}")


# ==================== 内置监控（备用） ====================

class BuiltinMonitor:
    """内置目录监控"""
    
    def __init__(self, config: ShortDramaConfig, callback: Callable, monitor_path: str):
        self.config = config
        self.callback = callback
        self._monitor_path = monitor_path
        self._observer = None
        self._processing = set()
        self._lock = threading.RLock()
    
    def start(self):
        if not self._monitor_path:
            return
        
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
            from watchdog.observers.polling import PollingObserver
        except ImportError:
            logger.error("[内置监控] watchdog 未安装")
            return
        
        class Handler(FileSystemEventHandler):
            def __init__(self, parent):
                self.parent = parent
            
            def on_created(self, event):
                if not event.is_directory:
                    self.parent._handle(event.src_path)
            
            def on_moved(self, event):
                if not event.is_directory:
                    self.parent._handle(event.dest_path)
        
        try:
            if self.config.monitor_mode == "compatibility":
                self._observer = PollingObserver(timeout=self.config.polling_interval)
            else:
                self._observer = Observer(timeout=10)
            
            self._observer.schedule(
                Handler(self),
                path=self._monitor_path,
                recursive=self.config.recursive
            )
            self._observer.daemon = True
            self._observer.start()
            logger.info(f"[内置监控] 已启动: {self._monitor_path}")
        
        except Exception as e:
            logger.error(f"[内置监控] 启动失败: {e}")
    
    def stop(self):
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
            logger.info("[内置监控] 已停止")
    
    def _handle(self, file_path: str):
        with self._lock:
            if file_path in self._processing:
                return
            self._processing.add(file_path)
        
        # 防抖
        time.sleep(self.config.debounce_time)
        
        try:
            if Path(file_path).suffix.lower() in settings.RMT_MEDIAEXT:
                self.callback("created", file_path)
        finally:
            with self._lock:
                self._processing.discard(file_path)


# ==================== 插件主类 ====================

class shortdramaorganizer(_PluginBase):
    """短剧整理器主类"""
    
    plugin_name = "短剧整理器"
    plugin_desc = "自动获取短剧种子、筛选下载、独立监控、识别整理、同步删除"
    plugin_icon = "📱"
    plugin_version = "1.0.2"
    plugin_author = "ShortDramaOrganizer"
    plugin_config_prefix = "shortdramaorganizer_"
    plugin_order = 26
    auth_level = 1
    
    # 私有属性
    _enabled: bool = False
    _stopping: bool = False
    _config: Optional[ShortDramaConfig] = None
    _executor: Optional[ThreadPoolExecutor] = None
    _processing_files: set = set()
    _lock: threading.RLock = threading.RLock()
    _task_cache: dict = {}
    _drama_cache: Optional[TTLCache] = None
    # 持久化映射：原始文件夹名 -> 最终标题，重启不丢失
    _title_mapping: Dict[str, str] = {}
    
    # 核心模块
    _torrent_service: Optional[TorrentService] = None
    _recognizer: Optional[ShortDramaRecognizer] = None
    _pt_fetcher: Optional[PTInfoFetcher] = None
    _organizer: Optional[ShortDramaOrganizer] = None
    _webhook: Optional[WebhookHandler] = None
    _builtin_monitors: List[BuiltinMonitor] = []
    
    def __init__(self):
        super().__init__()
        # 初始化缓存（使用系统 TTLCache，Redis 后端，重启不丢失）
        self._drama_cache = TTLCache(maxsize=500, ttl=86400)  # 最多500条，24小时过期
        logger.debug("[短剧整理器] 实例创建")

    
    # ==================== 生命周期 ====================
    
    def init_plugin(self, config: dict = None):
        if not config:
            logger.warning("[短剧整理器] 配置为空，跳过初始化")
            return
        
        logger.info("[短剧整理器] ========== 开始初始化 ==========")
        
        self._config = ShortDramaConfig(config)
        self._enabled = self._config.enabled
        
        logger.info(f"[短剧整理器] 配置加载完成: enabled={self._enabled}")
        
        # 先加载持久化数据，再停止旧服务（避免空数据覆盖）
        self._load_cache()
        self.stop_service()
        
        # stop_service 将 _enabled 置为 False，恢复为配置值
        self._enabled = self._config.enabled
        self._stopping = False
        
        if not self._enabled:
            logger.info("[短剧整理器] 插件未启用")
            return
        
        if not self._config.monitor_paths:
            logger.error("[短剧整理器] 未配置监控路径")
            return
        
        self._load_cache()
        
        # 初始化核心模块
        self._torrent_service = TorrentService(self._config)
        self._recognizer = ShortDramaRecognizer()
        self._pt_fetcher = PTInfoFetcher(self._config)
        self._organizer = ShortDramaOrganizer(self._config)
        self._executor = ThreadPoolExecutor(max_workers=3)
        
        if self._config.delete_enabled:
            self._webhook = WebhookHandler(self._config, self)
        
        # 清空数据面板（一次性操作，保存后自动复位）
        if self._config.clear_stats:
            logger.info("[短剧整理器] 清空数据面板")
            self._task_cache = {}
            self.save_data("tasks", self._task_cache)
            self.save_data("torrents", {})
            self.save_data("statistic", {})
            config["clear_stats"] = False
            self.update_config(config)
        
        # 清空整理历史记录（一次性操作，按设置的类别匹配）
        if self._config.clear_history:
            logger.info("[短剧整理器] 清空整理历史记录")
            try:
                from app.db import ScopedSession
                db = ScopedSession()
                try:
                    category = self._config.category or "短剧"
                    result = db.execute(
                        text("DELETE FROM transferhistory WHERE category = :category"),
                        {"category": category}
                    )
                    db.commit()
                    logger.info(f"[短剧整理器] 已清空类别 [{category}] 的整理历史，共 {result.rowcount} 条")
                except Exception:
                    db.rollback()
                    raise
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"[短剧整理器] 清空整理历史失败: {e}")
            config["clear_history"] = False
            self.update_config(config)
        
        # 清空缓存数据（一次性操作，保存后自动复位）
        if self._config.clear_cache:
            logger.info("[短剧整理器] 清空缓存数据")
            self._title_mapping = {}
            self._processing_files.clear()
            self._drama_cache.clear()
            self.save_data("title_mapping", self._title_mapping)
            config["clear_cache"] = False
            self.update_config(config)
        
        # 启动监控
        self._start_monitor()
        
        # 立即运行一次（刷流：获取种子+下载）
        if config.get("onlyonce"):
            logger.info("[短剧整理器] 立即运行一次（刷流）")
            threading.Timer(3, self._fetch_and_download).start()
            config["onlyonce"] = False
            self.update_config(config)
        
        # 立即执行一次全量整理
        if config.get("organize_once"):
            logger.info("[短剧整理器] 立即执行一次全量整理")
            threading.Timer(5, self._scan_and_process).start()
            config["organize_once"] = False
            self.update_config(config)
        
        # API 路由由 get_api() 返回，框架统一注册
        
        logger.info("[短剧整理器] ========== 初始化完成 ==========")
    
    def stop_service(self):
        logger.info("[短剧整理器] 停止服务")
        self._stopping = True
        self._enabled = False
        
        if self._builtin_monitors:
            for m in self._builtin_monitors:
                m.stop()
            self._builtin_monitors = []
        
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None
        
        self._save_cache()
        logger.info("[短剧整理器] 服务已停止")
    
    def get_state(self) -> bool:
        return self._enabled
    
    # ==================== 服务注册 ====================
    
    def get_service(self) -> List[Dict[str, Any]]:
        if not self._enabled or not self._config:
            return []
        
        services = []
        if self._config.refresh_interval > 0:
            services.append({
                "id": "shortdrama_fetch",
                "name": "短剧整理器-种子获取",
                "trigger": IntervalTrigger(minutes=self._config.refresh_interval),
                "func": self._fetch_and_download,
                "kwargs": {}
            })
        # 种子状态检查（每5分钟）
        services.append({
            "id": "shortdrama_check",
            "name": "短剧整理器-种子状态检查",
            "trigger": IntervalTrigger(minutes=5),
            "func": self._check_torrents_status,
            "kwargs": {}
        })
        return services
    
    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return [
            {"cmd": "/short_stats", "event": EventType.PluginAction, "desc": "查看统计", "category": "短剧", "data": {"action": "stats"}},
            {"cmd": "/short_clear", "event": EventType.PluginAction, "desc": "清空缓存", "category": "短剧", "data": {"action": "clear"}},
            {"cmd": "/short_scan", "event": EventType.PluginAction, "desc": "立即扫描", "category": "短剧", "data": {"action": "scan"}}
        ]
    
    def get_api(self) -> List[Dict[str, Any]]:
        if not self._enabled or not self._config or not self._config.delete_enabled:
            return []
        return [{
            "path": "/webhook/emby_delete",
            "endpoint": self._handle_webhook,
            "methods": ["POST"],
            "summary": "接收Emby删除事件"
        }]
    
    # ==================== 配置与面板 ====================
    
    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        defaults = {
            "enabled": False, "onlyonce": False, "organize_once": False, "refresh_interval": 30, "notify_enabled": True,
            "sites": [],
            "whitelist_keywords": ["短剧", "微短剧", "竖屏剧"],
            "blacklist_keywords": ["欧美", "日剧", "韩剧", "电影", "动漫"],
            "min_size": 200, "max_size": 2048, "min_seeders": 1,
            "freeleech": "free", "exclude_hr": True,
            "download_path": "", "download_tags": ["短剧整理器"], "downloader": "",
            "monitor_path": "", "monitor_mode": "normal",
            "exclude_patterns": ["*.sample", "*.nfo", "临时/"], "recursive": True, "incremental_scan": True,
            "transfer_type": "link", "media_library": "", "subdir": "短剧",
            "media_type": "电视剧", "category": "短剧",
            "pt_enabled": True, "delete_enabled": False, "clear_stats": False, "clear_history": False, "clear_cache": False,
            "debounce_time": 3,
            "use_proxy": False, "polling_interval": 5,
            "retry_count": 3, "retry_interval": 5,
            "pt_sites": DEFAULT_PT_SITES
        }
        
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [
                                {"component": "VSwitch", "props": {"model": "enabled", "label": "启用插件"}}
                            ]},
                            {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [
                                {"component": "VSwitch", "props": {"model": "onlyonce", "label": "立即刷流一次"}}
                            ]},
                            {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [
                                {"component": "VSwitch", "props": {"model": "organize_once", "label": "立即全量整理"}}
                            ]},
                            {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [
                                {"component": "VSwitch", "props": {"model": "notify_enabled", "label": "发送通知"}}
                            ]},
                            {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [
                                {"component": "VTextField", "props": {"model": "refresh_interval", "label": "刷新间隔(分钟)", "type": "number"}}
                            ]}
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {"component": "VCol", "props": {"cols": 12}, "content": [
                                {"component": "VSelect", "props": {
                                    "model": "sites",
                                    "label": "选择站点",
                                    "items": self._get_site_options(),
                                    "multiple": True,
                                    "chips": True
                                }}
                            ]}
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [
                                {"component": "VTextarea", "props": {
                                    "model": "whitelist_keywords",
                                    "label": "白名单关键词",
                                    "rows": 3,
                                    "placeholder": "用逗号或换行分隔，如：短剧,微短剧,竖屏剧"
                                }}
                            ]},
                            {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [
                                {"component": "VTextarea", "props": {
                                    "model": "blacklist_keywords",
                                    "label": "黑名单关键词",
                                    "rows": 3,
                                    "placeholder": "用逗号或换行分隔，如：欧美,日剧,韩剧,电影"
                                }}
                            ]}
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [
                                {"component": "VTextField", "props": {"model": "min_size", "label": "最小大小(MB)", "type": "number"}}
                            ]},
                            {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [
                                {"component": "VTextField", "props": {"model": "max_size", "label": "最大大小(MB)", "type": "number"}}
                            ]},
                            {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [
                                {"component": "VTextField", "props": {"model": "min_seeders", "label": "最小做种数", "type": "number"}}
                            ]},
                            {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [
                                {"component": "VSelect", "props": {
                                    "model": "freeleech",
                                    "label": "促销类型",
                                    "items": [
                                        {"title": "全部", "value": ""},
                                        {"title": "免费", "value": "free"},
                                        {"title": "2X免费", "value": "2xfree"}
                                    ]
                                }}
                            ]}
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {"component": "VCol", "props": {"cols": 12}, "content": [
                                {"component": "VSwitch", "props": {"model": "exclude_hr", "label": "排除H&R"}}
                            ]}
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [
                                {"component": "VTextField", "props": {"model": "download_path", "label": "下载目录", "placeholder": "留空使用系统默认"}}
                            ]},
                            {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [
                                {"component": "VCombobox", "props": {
                                    "model": "download_tags",
                                    "label": "自动标签",
                                    "multiple": True,
                                    "chips": True
                                }}
                            ]}
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [
                                {"component": "VSelect", "props": {
                                    "model": "downloader",
                                    "label": "选择下载器",
                                    "items": self._get_downloader_options()
                                }}
                            ]}
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [
                                {"component": "VTextarea", "props": {"model": "monitor_path", "label": "监控路径", "rows": 3, "placeholder": "每行一个路径"}}
                            ]},
                            {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [
                                {"component": "VSelect", "props": {
                                    "model": "monitor_mode",
                                    "label": "监控方式",
                                    "items": [
                                        {"title": "普通模式", "value": "normal"},
                                        {"title": "兼容模式", "value": "compatibility"}
                                    ]
                                }}
                            ]}
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {"component": "VCol", "props": {"cols": 12}, "content": [
                                {"component": "VTextarea", "props": {
                                    "model": "exclude_patterns",
                                    "label": "排除规则",
                                    "rows": 2,
                                    "placeholder": "每行一个通配符或正则"
                                }}
                            ]}
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [
                                {"component": "VSwitch", "props": {"model": "recursive", "label": "递归监控"}}
                            ]},
                            {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [
                                {"component": "VSwitch", "props": {"model": "incremental_scan", "label": "增量扫描"}}
                            ]},
                            {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [
                                {"component": "VTextField", "props": {"model": "debounce_time", "label": "防抖时间(秒)", "type": "number"}}
                            ]}
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [
                                {"component": "VSelect", "props": {
                                    "model": "transfer_type",
                                    "label": "转移方式",
                                    "items": [
                                        {"title": "硬链接", "value": "link"},
                                        {"title": "移动", "value": "move"},
                                        {"title": "复制", "value": "copy"},
                                        {"title": "软链接", "value": "softlink"}
                                    ]
                                }}
                            ]},
                            {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [
                                {"component": "VTextField", "props": {"model": "media_library", "label": "媒体库路径", "placeholder": "留空使用系统配置"}}
                            ]},
                            {"component": "VCol", "props": {"cols": 12, "md": 4}, "content": [
                                {"component": "VTextField", "props": {"model": "subdir", "label": "短剧子目录"}}
                            ]}
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [
                                {"component": "VSelect", "props": {
                                    "model": "media_type",
                                    "label": "媒体类型",
                                    "items": [
                                        {"title": "电视剧", "value": "电视剧"},
                                        {"title": "电影", "value": "电影"}
                                    ]
                                }}
                            ]},
                            {"component": "VCol", "props": {"cols": 12, "md": 6}, "content": [
                                {"component": "VTextField", "props": {"model": "category", "label": "分类", "placeholder": "如：短剧"}}
                            ]}
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {"component": "VCol", "props": {"cols": 12}, "content": [
                                {"component": "VSwitch", "props": {"model": "pt_enabled", "label": "启用PT站点信息补全"}}
                            ]}
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [
                                {"component": "VSwitch", "props": {"model": "delete_enabled", "label": "启用同步删除"}}
                            ]},
                            {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [
                                {"component": "VSwitch", "props": {"model": "clear_stats", "label": "清空数据面板", "color": "warning"}}
                            ]},
                            {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [
                                {"component": "VSwitch", "props": {"model": "clear_history", "label": "清空整理历史", "color": "warning"}}
                            ]},
                            {"component": "VCol", "props": {"cols": 12, "md": 3}, "content": [
                                {"component": "VSwitch", "props": {"model": "clear_cache", "label": "清空缓存数据", "color": "error"}}
                            ]}
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {"component": "VCol", "props": {"cols": 12}, "content": [
                                {"component": "VAlert", "props": {
                                    "type": "info",
                                    "variant": "tonal",
                                    "text": "监控路径中的文件会被自动识别为短剧并整理到媒体库。PT站点信息补全功能可以从AGSV、萝莉站等短剧专用站点获取剧名、年份、简介、海报等元数据。"
                                }}
                            ]}
                        ]
                    }
                ]
            }
        ], defaults
    
    def _get_site_options(self) -> List[Dict]:
        if not HAS_FRAMEWORK:
            return []
        
        try:
            sites = SitesHelper().get_indexers()
            return [{"title": s.get("name", s.get("id")), "value": s.get("id")} for s in sites]
        except Exception as e:
            logger.error(f"[短剧整理器] 获取站点列表失败: {e}")
            return []
    
    @staticmethod
    def _get_downloader_options() -> List[Dict]:
        """获取系统已配置的下载器列表"""
        try:
            from app.helper.downloader import DownloaderHelper
            services = DownloaderHelper().get_configs()
            return [{"title": name, "value": name} for name in services]
        except Exception as e:
            logger.error(f"[短剧整理器] 获取下载器列表失败: {e}")
            return []
    
    def get_page(self) -> List[dict]:
        # 种子明细
        torrents = self.get_data("torrents") or {}
        
        data_list = list(torrents.values())
        data_list.sort(key=lambda x: x.get("time") or 0, reverse=True)
        
        from app.utils.string import StringUtils
        
        if data_list:
            torrent_trs = [
                {
                    'component': 'tr',
                    'props': {'class': 'text-sm'},
                    'content': [
                        {
                            'component': 'td',
                            'props': {'class': 'whitespace-nowrap break-keep text-high-emphasis'},
                            'text': data.get("site_name") or "-"
                        },
                        {
                            'component': 'td',
                            'html': f'<span style="font-size: .85rem;">{data.get("title", "")}</span>' +
                                    (f'<br><span style="font-size: 0.75rem;">{data.get("description", "")}</span>' if data.get("description") else "")
                        },
                        {
                            'component': 'td',
                            'text': StringUtils.str_filesize(data.get("size") or 0)
                        },
                        {
                            'component': 'td',
                            'text': StringUtils.str_filesize(data.get("uploaded") or 0)
                        },
                        {
                            'component': 'td',
                            'text': StringUtils.str_filesize(data.get("downloaded") or 0)
                        },
                        {
                            'component': 'td',
                            'text': str(round(data.get('ratio') or 0, 2))
                        },
                        {
                            'component': 'td',
                            'text': "是" if data.get("hit_and_run") else "否"
                        },
                        {
                            'component': 'td',
                            'text': f"{data.get('seeding_time', 0) / 3600:.1f}h" if data.get('seeding_time') else "N/A"
                        },
                        {
                            'component': 'td',
                            'props': {'class': 'text-no-wrap'},
                            'text': data.get("downloader") or "-"
                        },
                        {
                            'component': 'td',
                            'props': {'class': 'text-no-wrap'},
                            'text': "已删除" if data.get("deleted") else "正常"
                        }
                    ]
                } for data in data_list
            ]
        else:
            torrent_trs = [{
                'component': 'tr',
                'content': [{'component': 'td', 'props': {'colspan': 10, 'class': 'text-center'}, 'text': '暂无数据'}]
            }]
        
        return [
            {
                'component': 'VRow',
                'content': self._get_total_elements() + [
                    {
                        'component': 'VCol',
                        'props': {'cols': 12},
                        'content': [{
                            'component': 'VTable',
                            'props': {'hover': True},
                            'content': [
                                {
                                    'component': 'thead',
                                    'props': {'class': 'text-no-wrap'},
                                    'content': [{
                                        'component': 'tr',
                                        'content': [
                                            {'component': 'th', 'props': {'class': 'text-start ps-4'}, 'text': '站点'},
                                            {'component': 'th', 'props': {'class': 'text-start ps-4'}, 'text': '标题'},
                                            {'component': 'th', 'props': {'class': 'text-start ps-4'}, 'text': '大小'},
                                            {'component': 'th', 'props': {'class': 'text-start ps-4'}, 'text': '上传量'},
                                            {'component': 'th', 'props': {'class': 'text-start ps-4'}, 'text': '下载量'},
                                            {'component': 'th', 'props': {'class': 'text-start ps-4'}, 'text': '分享率'},
                                            {'component': 'th', 'props': {'class': 'text-start ps-4'}, 'text': 'HR'},
                                            {'component': 'th', 'props': {'class': 'text-start ps-4'}, 'text': '做种时间'},
                                            {'component': 'th', 'props': {'class': 'text-start ps-4'}, 'text': '下载器'},
                                            {'component': 'th', 'props': {'class': 'text-start ps-4'}, 'text': '状态'}
                                        ]
                                    }]
                                },
                                {
                                    'component': 'tbody',
                                    'content': torrent_trs
                                }
                            ]
                        }]
                    }
                ]
            }
        ]
    
    def get_dashboard(self, key: str, **kwargs) -> Optional[Tuple[Dict[str, Any], Dict[str, Any], List[dict]]]:
        if not self.get_state():
            return None
        return (
            {"cols": 12},
            {},
            [{"component": "VRow", "content": self._get_total_elements()}]
        )
    
    def _get_total_elements(self) -> List[dict]:
        """组装统计卡片（与刷流低频版风格一致）"""
        statistic = self.get_data("statistic") or {
            "count": 0, "deleted": 0, "uploaded": 0, "downloaded": 0,
            "unarchived": 0, "active": 0, "active_uploaded": 0, "active_downloaded": 0
        }
        from app.utils.string import StringUtils
        
        total_uploaded = StringUtils.str_filesize(statistic.get("uploaded") or 0)
        total_downloaded = StringUtils.str_filesize(statistic.get("downloaded") or 0)
        total_count = statistic.get("count") or 0
        total_deleted = statistic.get("deleted") or 0
        total_active = statistic.get("active") or 0
        total_active_uploaded = StringUtils.str_filesize(statistic.get("active_uploaded") or 0)
        total_active_downloaded = StringUtils.str_filesize(statistic.get("active_downloaded") or 0)
        
        # 下次刷流运行时间
        next_run = ""
        try:
            from app.scheduler import Scheduler
            scheduler = Scheduler()
            if scheduler._scheduler and scheduler._scheduler.running:
                for job in scheduler._scheduler.get_jobs():
                    if job.id == "shortdramaorganizer_shortdrama_fetch":
                        from app.utils.timer import TimerUtils
                        next_run = TimerUtils.time_difference(job.next_run_time)
                        break
        except Exception:
            next_run = ""
        
        return [
            {
                "component": "VCol",
                "props": {"cols": 12, "md": 3, "sm": 6},
                "content": [{
                    "component": "VCard",
                    "props": {"variant": "tonal"},
                    "content": [{
                        "component": "VCardText",
                        "props": {"class": "d-flex align-center"},
                        "content": [
                            {"component": "VAvatar", "props": {"rounded": True, "variant": "text", "class": "me-3"},
                             "content": [{"component": "VImg", "props": {"src": "/plugin_icon/upload.png"}}]},
                            {"component": "div", "content": [
                                {"component": "span", "props": {"class": "text-caption"}, "text": "总上传量 / 活跃"},
                                {"component": "div", "props": {"class": "d-flex align-center flex-wrap"}, "content": [
                                    {"component": "span", "props": {"class": "text-h6"}, "text": f"{total_uploaded} / {total_active_uploaded}"}
                                ]}
                            ]}
                        ]
                    }]
                }]
            },
            {
                "component": "VCol",
                "props": {"cols": 12, "md": 3, "sm": 6},
                "content": [{
                    "component": "VCard",
                    "props": {"variant": "tonal"},
                    "content": [{
                        "component": "VCardText",
                        "props": {"class": "d-flex align-center"},
                        "content": [
                            {"component": "VAvatar", "props": {"rounded": True, "variant": "text", "class": "me-3"},
                             "content": [{"component": "VImg", "props": {"src": "/plugin_icon/download.png"}}]},
                            {"component": "div", "content": [
                                {"component": "span", "props": {"class": "text-caption"}, "text": "总下载量 / 活跃"},
                                {"component": "div", "props": {"class": "d-flex align-center flex-wrap"}, "content": [
                                    {"component": "span", "props": {"class": "text-h6"}, "text": f"{total_downloaded} / {total_active_downloaded}"}
                                ]}
                            ]}
                        ]
                    }]
                }]
            },
            {
                "component": "VCol",
                "props": {"cols": 12, "md": 3, "sm": 6},
                "content": [{
                    "component": "VCard",
                    "props": {"variant": "tonal"},
                    "content": [{
                        "component": "VCardText",
                        "props": {"class": "d-flex align-center"},
                        "content": [
                            {"component": "VAvatar", "props": {"rounded": True, "variant": "text", "class": "me-3"},
                             "content": [{"component": "VImg", "props": {"src": "/plugin_icon/seed.png"}}]},
                            {"component": "div", "content": [
                                {"component": "span", "props": {"class": "text-caption"}, "text": "下载种子数 / 活跃"},
                                {"component": "div", "props": {"class": "d-flex align-center flex-wrap"}, "content": [
                                    {"component": "span", "props": {"class": "text-h6"}, "text": f"{total_count} / {total_active}"}
                                ]}
                            ]}
                        ]
                    }]
                }]
            },
            {
                "component": "VCol",
                "props": {"cols": 12, "md": 3, "sm": 6},
                "content": [{
                    "component": "VCard",
                    "props": {"variant": "tonal"},
                    "content": [{
                        "component": "VCardText",
                        "props": {"class": "d-flex align-center"},
                        "content": [
                            {"component": "VAvatar", "props": {"rounded": True, "variant": "text", "class": "me-3"},
                             "content": [{"component": "VImg", "props": {"src": "/plugin_icon/delete.png"}}]},
                            {"component": "div", "content": [
                                {"component": "span", "props": {"class": "text-caption"}, "text": "删除种子数 / 下次刷流"},
                                {"component": "div", "props": {"class": "d-flex align-center flex-wrap"}, "content": [
                                    {"component": "span", "props": {"class": "text-h6"}, "text": f"{total_deleted} / {next_run or '未调度'}"}
                                ]}
                            ]}
                        ]
                    }]
                }]
            },
        ]
    
    # ==================== 核心功能 ====================
    
    def _start_monitor(self):
        """启动目录监控（支持多路径）"""
        if not self._config or not self._config.monitor_paths:
            return
        
        self._builtin_monitors = []
        for mp in self._config.monitor_paths:
            if not Path(mp).exists():
                logger.warning(f"[短剧整理器] 监控路径不存在，跳过: {mp}")
                continue
            monitor = BuiltinMonitor(self._config, self._on_file_event, mp)
            monitor.start()
            self._builtin_monitors.append(monitor)
            logger.info(f"[短剧整理器] 监控已启动: {mp}")
    
    def _update_torrent_deleted(self, download_hash: str):
        """删除种子后立即更新种子数据"""
        try:
            torrent_tasks: Dict[str, dict] = self.get_data("torrents") or {}
            if download_hash in torrent_tasks:
                torrent_tasks[download_hash]["deleted"] = True
                torrent_tasks[download_hash]["delete_time"] = time.time()
                self.save_data("torrents", torrent_tasks)
                # 更新统计
                deleted_count = sum(1 for t in torrent_tasks.values() if t.get("deleted"))
                statistic = self.get_data("statistic") or {}
                statistic["deleted"] = deleted_count
                self.save_data("statistic", statistic)
                logger.debug(f"[短剧整理器] 种子已标记删除: {download_hash[:8]}...")
        except Exception as e:
            logger.error(f"[短剧整理器] 更新种子删除状态失败: {e}")
    
    def _fetch_and_download(self):
        """获取种子并下载（使用标题去重）"""
        if not self._enabled or not self._torrent_service:
            return
        
        logger.info("[短剧整理器] 开始获取种子")
        try:
            torrents = self._torrent_service.fetch()
            if not torrents:
                logger.info("[短剧整理器] 未获取到种子")
                return
            
            logger.info(f"[短剧整理器] 获取到 {len(torrents)} 个种子")
            filtered = self._torrent_service.filter(torrents)
            if not filtered:
                logger.info("[短剧整理器] 没有符合条件的种子")
                return
            
            logger.info(f"[短剧整理器] 筛选出 {len(filtered)} 个种子")
            
            # 加载已存在的种子记录（包括已删除的），用于去重
            torrent_tasks: Dict[str, dict] = self.get_data("torrents") or {}
            
            # 构建已下载种子的标题集合（作为唯一标识）
            existing_titles = set()
            for h, info in torrent_tasks.items():
                title = info.get("title", "")
                if title:
                    existing_titles.add(title)
            
            logger.debug(f"[种子服务] 已存在 {len(existing_titles)} 个种子记录（按标题）")
            
            downloaded = 0
            skipped = 0
            for torrent in filtered:
                if not self._enabled or self._stopping:
                    break
                
                torrent_title = torrent.get("title", "")
                if not torrent_title:
                    logger.warning("[种子服务] 种子无标题，跳过")
                    continue
                
                torrent_size = torrent.get("size", 0)
                
                # 检查标题是否已下载过（包括已删除的）
                if torrent_title in existing_titles:
        
                    skipped += 1
                    continue
                
                # 获取站点名称
                site_name = ""
                try:
                    site_id = self._config.sites[0] if self._config.sites else None
                    if site_id:
                        site = SiteOper().get(int(site_id))
                        if site:
                            site_name = site.name
                except Exception:
                    pass
                
                # 下载种子
                download_hash = self._torrent_service.download(torrent)
                if download_hash:
                    downloaded += 1
                    existing_titles.add(torrent_title)  # 加入去重集合
                    
                    # 记录种子信息（明确标记未删除）
                    torrent_tasks[download_hash] = {
                        "title": torrent_title,
                        "description": torrent.get("description", ""),
                        "size": torrent_size,
                        "site_name": site_name,
                        "downloader": self._config.downloader or "",
                        "time": time.time(),
                        "hash": download_hash,
                        "deleted": False,  # 新下载的种子未删除
                    }
                    logger.info(f"[种子服务] 下载成功: {torrent_title[:40]}... hash={download_hash[:8]}")
                else:
                    logger.warning(f"[种子服务] 下载失败: {torrent_title[:40]}...")
            
            # 保存更新后的种子记录
            self.save_data("torrents", torrent_tasks)
            logger.info(f"[短剧整理器] 成功下载 {downloaded} 个种子，跳过已存在 {skipped} 个")
            
        except Exception as e:
            logger.error(f"[短剧整理器] 获取种子失败: {e}")
    
    def _check_torrents_status(self):
        """从下载器查询种子状态，更新统计数据"""
        if not self._enabled:
            return
        
        torrent_tasks: Dict[str, dict] = self.get_data("torrents") or {}
        if not torrent_tasks:
            return
        
        downloader_name = self._config.downloader if self._config else ""
        if not downloader_name:
            return
        
        try:
            service = DownloaderHelper().get_service(name=downloader_name)
            if not service or not service.instance:
                return
            
            dl = service.instance
            all_torrents, error = dl.get_torrents()
            if error or not all_torrents:
                return
            
            # 建立哈希索引
            torrent_map = {}
            for t in all_torrents:
                h = t.hashString if hasattr(t, 'hashString') else t.get("hash", "")
                if h:
                    torrent_map[h] = t
            
            active_count = 0
            total_uploaded = 0
            total_downloaded = 0
            active_uploaded = 0
            active_downloaded = 0
            deleted_hashes = []
            
            for h, info in torrent_tasks.items():
                t = torrent_map.get(h)
                if t:
                    # 种子还在下载器中
                    uploaded = t.uploaded if hasattr(t, 'uploaded') else t.get("uploaded", 0)
                    downloaded = t.downloaded if hasattr(t, 'downloaded') else t.get("downloaded", 0)
                    progress = t.progress if hasattr(t, 'progress') else t.get("progress", 0)
                    ratio = t.ratio if hasattr(t, 'ratio') else t.get("ratio", 0)
                    seeding_time = t.seeding_time if hasattr(t, 'seeding_time') else t.get("seeding_time", 0)
                    hit_and_run = t.hit_and_run if hasattr(t, 'hit_and_run') else t.get("hit_and_run", False)
                    
                    info["uploaded"] = uploaded
                    info["downloaded"] = downloaded
                    info["ratio"] = ratio
                    info["progress"] = progress
                    info["seeding_time"] = seeding_time
                    info["hit_and_run"] = hit_and_run
                    info["active"] = True
                    
                    total_uploaded += uploaded
                    total_downloaded += downloaded
                    
                    if progress < 100:
                        active_count += 1
                        active_uploaded += uploaded
                        active_downloaded += downloaded
                else:
                    # 种子已从下载器移除
                    if not info.get("deleted"):
                        info["deleted"] = True
                        info["delete_time"] = time.time()
            
            # 统计
            statistic = {
                "count": len(torrent_tasks),
                "deleted": sum(1 for t in torrent_tasks.values() if t.get("deleted")),
                "uploaded": total_uploaded,
                "downloaded": total_downloaded,
                "active": active_count,
                "active_uploaded": active_uploaded,
                "active_downloaded": active_downloaded,
                "unarchived": sum(1 for t in torrent_tasks.values() if t.get("progress", 0) >= 100 and not t.get("deleted")),
            }
            
            self.save_data("torrents", torrent_tasks)
            self.save_data("statistic", statistic)
            
        except Exception as e:
            logger.error(f"[短剧整理器] 查询种子状态失败: {e}")
    
    def _scan_and_process(self, force_full: bool = False):
        """扫描并处理目录
        
        Args:
            force_full: 是否强制全量扫描（忽略 incremental_scan 开关）
        """
        if not self._enabled or not self._config:
            return
        
        logger.info("[短剧整理器] 开始扫描目录")
        try:
            processed = 0
            
            for monitor_path_str in self._config.monitor_paths:
                if self._stopping:
                    logger.info("[短剧整理器] 停止信号，中断扫描")
                    return
                
                monitor_path = Path(monitor_path_str)
                if not monitor_path.exists():
                    logger.warning(f"[短剧整理器] 监控路径不存在: {monitor_path}")
                    continue
                
                logger.info(f"[短剧整理器] 扫描: {monitor_path}")
                
                if self._config.recursive:
                    for ext in settings.RMT_MEDIAEXT:
                        if self._stopping:
                            logger.info("[短剧整理器] 停止信号，中断扫描")
                            return
                        for video_file in monitor_path.rglob(f"*{ext}"):
                            if self._stopping:
                                logger.info("[短剧整理器] 停止信号，中断扫描")
                                return
                            if video_file.is_symlink():
                                continue
                            if not self._enabled:
                                return
                            if self._process_file(str(video_file)):
                                processed += 1
                else:
                    for folder in monitor_path.iterdir():
                        if self._stopping:
                            logger.info("[短剧整理器] 停止信号，中断扫描")
                            return
                        if not folder.is_dir():
                            continue
                        if self._is_excluded(str(folder)):
                            continue
                        if not self._enabled:
                            return
                        for ext in settings.RMT_MEDIAEXT:
                            if self._stopping:
                                logger.info("[短剧整理器] 停止信号，中断扫描")
                                return
                            for video_file in folder.glob(f"*{ext}"):
                                if self._process_file(str(video_file)):
                                    processed += 1
            
            if processed > 0:
                logger.info(f"[短剧整理器] 扫描完成，处理了 {processed} 个文件")
            else:
                logger.info("[短剧整理器] 扫描完成，无新文件")
        except Exception as e:
            logger.error(f"[短剧整理器] 扫描失败: {e}")
    
    def _is_excluded(self, path: str) -> bool:
        """检查路径是否被排除（使用标准通配符匹配）"""
        if not self._config:
            return False
        
        for pattern in self._config.exclude_patterns:
            if fnmatch.fnmatch(path, pattern):
                return True
            # 也检查路径中的任意部分
            if any(fnmatch.fnmatch(part, pattern) for part in Path(path).parts):
                return True
        return False
    
    def _on_file_event(self, event_type: str, file_path: str):
        """文件事件回调"""
        if not self._enabled:
            return
        
        if Path(file_path).suffix.lower() not in settings.RMT_MEDIAEXT:
            return
        
        logger.info(f"[短剧整理器] 文件事件: {event_type} - {file_path}")
        if self._executor:
            future = self._executor.submit(self._process_file, file_path)
            future.add_done_callback(self._handle_future_result)
        else:
            threading.Thread(target=self._process_file, args=(file_path,), daemon=True).start()
    
    def _handle_future_result(self, future: Future):
        """处理线程池任务结果"""
        try:
            result = future.result()
            if not result:
                logger.debug("[短剧整理器] 处理任务返回失败")
        except Exception as e:
            logger.error(f"[短剧整理器] 处理任务异常: {e}")
    
    def _process_file(self, file_path: str) -> bool:
        """处理单个文件"""
        if not self._enabled or self._stopping:
            return False
        
        file_path = str(Path(file_path).resolve())
        source_dir = str(Path(file_path).parent)
        
        with self._lock:
            if file_path in self._processing_files:
                logger.debug(f"[短剧整理器] 文件正在处理: {file_path}")
                return False
            self._processing_files.add(file_path)
        
        try:
            logger.info(f"[短剧整理器] ========== 开始处理文件 ==========")
            logger.info(f"[短剧整理器] 文件路径: {file_path}")
            logger.info(f"[短剧整理器] 源文件夹: {source_dir}")
            
            # 检查 transferhistory 是否已有相同 src 的记录，避免后续不必要的识别
            existing_record = self._check_transfer_history(file_path)
            if existing_record:
                if self._config.incremental_scan:
                    # 增量扫描开：跳过
                    logger.info(f"[短剧整理器] 源文件已有整理记录，跳过: {file_path}")
                    return True
                else:
                    # 增量扫描关：删除旧记录，重新整理
                    logger.info(f"[短剧整理器] 源文件已有整理记录，覆盖: {file_path}")
                    self._delete_transfer_history(file_path)
            
            # 检查持久化映射：原始文件夹名 -> 最终标题
            folder_name = Path(source_dir).name
            mapped_title = self._title_mapping.get(folder_name)
            if mapped_title:
                logger.info(f"[短剧整理器] 映射命中: {folder_name} -> {mapped_title}")
            
            # 检查文件夹级缓存
            cached = self._drama_cache.get(source_dir)
            if cached:
                logger.info(f"[短剧整理器] 缓存命中，缓存字段: {list(cached.keys())}")
                drama_info = cached.copy()
                drama_info["source_path"] = file_path
                drama_info["file_name"] = Path(file_path).name
                drama_info["episode"] = self._recognizer.extract_episode(Path(file_path).name) if self._recognizer else 1
                # 确保 title 使用 extract_title 的干净结果，不被缓存中的脏数据污染
                clean_title = self._recognizer.extract_title(folder_name) if self._recognizer else folder_name
                if clean_title:
                    drama_info["title"] = clean_title
                logger.info(f"[短剧整理器] 使用缓存 -> title={drama_info.get('title')} season={drama_info.get('season')} episode={drama_info.get('episode')}")
            else:
                logger.info(f"[短剧整理器] 缓存未命中，开始首次识别")
                # 首次识别：文件夹名提取标题，系统识别提取季/集+TMDB元数据
                logger.info(f"[短剧整理器] 文件夹名(原始): {folder_name}")
                title = mapped_title or (self._recognizer.extract_title(folder_name) if self._recognizer else folder_name)
                logger.info(f"[短剧整理器] extract_title结果: '{title}'")
                
                if not title:
                    logger.warning(f"[短剧整理器] extract_title返回空，放弃处理")
                    return False
                
                season = 1
                episode = 1
                tmdb_info = None
                # 搜索关键字使用 extract_title 的干净结果，不用 mapped_title（可能被污染）
                search_title = self._recognizer.extract_title(folder_name) if self._recognizer else folder_name
                if not search_title:
                    search_title = title
                
                if HAS_FRAMEWORK:
                    # 系统识别：路径解析季/集，优先使用识别得到的剧名作为搜索关键字
                    try:
                        ctx = MediaChain().recognize_by_path(file_path)
                        if ctx and ctx.meta_info:
                            m = ctx.meta_info
                            season = m.begin_season or 1
                            episode = m.begin_episode or 1
                            # 使用系统识别得到的剧名（比 extract_title 更准确）
                            if ctx.media_info and ctx.media_info.title:
                                search_title = ctx.media_info.title
                                logger.info(f"[短剧整理器] 路径识别 -> title={search_title} season={season} episode={episode}")
                            else:
                                logger.info(f"[短剧整理器] 路径识别 -> season={season} episode={episode} season_episode={m.season_episode}")
                    except Exception as e:
                        logger.warning(f"[短剧整理器] 路径识别异常: {e}")
                    
                    # TMDB搜索（使用识别得到的剧名）
                    try:
                        tmdb_info = self._search_tmdb(search_title)
                        if tmdb_info:
                            logger.info(f"[短剧整理器] TMDB补全: {json.dumps(tmdb_info, ensure_ascii=False, default=str)}")
                    except Exception as e:
                        logger.warning(f"[短剧整理器] TMDB搜索异常: {e}")
                # 检查同目录下是否有 nfo 文件
                nfo_path = Path(file_path).parent / "tvshow.nfo"
                nfo_info = None
                if nfo_path.exists():
                    try:
                        tree = parse(str(nfo_path))
                        root = tree.getroot()
                        nfo_info = {}
                        if root.findtext("title"):
                            nfo_info["title"] = root.findtext("title")
                        if root.findtext("year"):
                            nfo_info["year"] = root.findtext("year")
                        if root.findtext("plot"):
                            nfo_info["overview"] = root.findtext("plot")
                        if root.findtext("country"):
                            nfo_info["country"] = root.findtext("country")
                        genres = [g.text for g in root.findall("genre") if g.text]
                        if genres:
                            nfo_info["genres"] = genres
                        actors = [a.findtext("name") for a in root.findall("actor") if a.findtext("name")]
                        if actors:
                            nfo_info["actors"] = actors
                        uniqueid = root.find("uniqueid[@type='tmdb']")
                        if uniqueid is not None and uniqueid.text:
                            nfo_info["tmdbid"] = uniqueid.text
                        if root.findtext("rating"):
                            nfo_info["rating"] = root.findtext("rating")
                        logger.info(f"[短剧整理器] 读取到NFO信息: {list(nfo_info.keys())}")
                    except Exception as e:
                        logger.warning(f"[短剧整理器] 读取NFO失败: {e}")

                drama_info = {
                    "title": title,
                    "season": season,
                    "episode": episode,
                    "folder_name": folder_name,
                    "file_name": Path(file_path).name,
                    "source_path": file_path,
                }

                # 合并 TMDB 信息
                if tmdb_info:
                    for k, v in tmdb_info.items():
                        if v and not drama_info.get(k):
                            drama_info[k] = v
                    logger.info(f"[短剧整理器] 应用TMDB信息: {list(tmdb_info.keys())}")

                # PT站点信息补全（使用识别得到的剧名搜索）
                if self._pt_fetcher and self._config.pt_enabled:
                    try:
                        pt_info = self._pt_fetcher.fetch(search_title, drama_info.get("year"))
                        if pt_info:
                            for k, v in pt_info.items():
                                if v and not drama_info.get(k):
                                    drama_info[k] = v
                            # PT 的 title 是详情页的干净片名，优先使用
                            if pt_info.get("title"):
                                drama_info["title"] = pt_info["title"]
                                search_title = pt_info["title"]
                            logger.info(f"[短剧整理器] 应用PT信息: {list(pt_info.keys())}")
                    except Exception as e:
                        logger.warning(f"[短剧整理器] PT信息补全异常: {e}")

                # 合并 nfo 信息（优先使用 nfo 的数据）
                if nfo_info:
                    # 先合并 nfo，后续 TMDB/PT 只补充不覆盖
                    for k, v in nfo_info.items():
                        if v and not drama_info.get(k):
                            drama_info[k] = v
                    # 如果 nfo 有 title，优先使用
                    if nfo_info.get("title"):
                        drama_info["title"] = nfo_info["title"]
                        search_title = nfo_info["title"]
                    logger.info(f"[短剧整理器] 应用NFO信息: {list(nfo_info.keys())}")
                
                # 确保 title 使用识别得到的干净剧名
                if search_title:
                    drama_info["title"] = search_title
                
                # 写入缓存（排除每集变化的字段）
                cache_data = {
                    k: v for k, v in drama_info.items()
                    if k not in ("source_path", "file_name", "episode")
                }
                self._drama_cache[source_dir] = cache_data
                logger.info(f"[短剧整理器] 写入缓存 -> key={source_dir} fields={list(cache_data.keys())}")
                
                # 保存持久化映射：原始文件夹名 -> extract_title 的原始结果（不被 PT 等后续合并污染）
                clean_title = self._recognizer.extract_title(folder_name) if self._recognizer else folder_name
                if folder_name != clean_title:
                    self._title_mapping[folder_name] = clean_title
                    logger.info(f"[短剧整理器] 保存映射: {folder_name} -> {clean_title}")
            
            title = drama_info.get("title", "未知短剧")
            season = drama_info.get("season", 1)
            episode = drama_info.get("episode", 1)
            logger.info(f"[短剧整理器] 最终识别 -> title={title} season={season} episode={episode}")
            logger.debug(f"[短剧整理器] drama_info完整字段: {json.dumps({k: str(v)[:100] for k, v in drama_info.items()}, ensure_ascii=False)}")
            
            if self._organizer:
                logger.info(f"[短剧整理器] 开始整理文件")
                result = self._organizer.organize(file_path, drama_info)
                if result and result.get("success"):
                    logger.info(f"[短剧整理器] 整理成功 -> 目标: {result.get('target_path')}")
                    
                    self._save_mapping(file_path, result, drama_info)
                    
                    if self._config and self._config.notify_enabled:
                        self._send_notification(f"✅ {title} S{season:02d}E{episode:02d} 已入库")
                    
                    return True
                else:
                    logger.error(f"[短剧整理器] 整理失败: {result.get('error') if result else '未知错误'}")
                    return False
            
            return False
        
        except Exception as e:
            logger.error(f"[短剧整理器] 处理失败: {e}")
            return False
        
        finally:
            with self._lock:
                self._processing_files.discard(file_path)
    
    def _handle_webhook(self, request_data: dict = None, request=None) -> dict:
        """处理 Emby Webhook"""
        if not self._enabled:
            logger.warning("[Webhook] 插件未启用，忽略Webhook请求")
            return {"code": 403, "message": "Plugin disabled"}
        if not self._webhook:
            return {"code": 403, "message": "Webhook未启用"}
        
        try:
            data = request_data or {}
            if request and hasattr(request, 'json'):
                data = request.json() if callable(request.json) else request.json
            return self._webhook.handle(data)
        except Exception as e:
            logger.error(f"[Webhook] 处理异常: {e}")
            return {"code": 500, "message": str(e)}
    
    # ==================== TMDB搜索 ====================
    
    @staticmethod
    def _search_tmdb(title: str) -> Optional[Dict]:
        """搜索TMDB获取媒体信息"""
        try:
            
            meta = MetaInfo(title)
            if not meta.cn_name:
                meta.cn_name = title
            
            mediainfo = MediaChain().recognize_media(meta=meta, mtype=MediaType.TV)
            if not mediainfo:
                logger.debug(f"[TMDB] 未找到: {title}")
                return None
            
            result = {}
            if mediainfo.tmdb_id:
                result["tmdbid"] = mediainfo.tmdb_id
            if mediainfo.douban_id:
                result["doubanid"] = mediainfo.douban_id
            if mediainfo.overview:
                result["overview"] = mediainfo.overview
            if mediainfo.vote_average:
                result["rating"] = mediainfo.vote_average
            if mediainfo.year:
                result["year"] = str(mediainfo.year)
            if mediainfo.genres:
                genre_names = [g.get("name") for g in mediainfo.genres if g.get("name")]
                if genre_names:
                    result["genres"] = genre_names
            
            # 提取演员
            if mediainfo.actors:
                actors = [a.get('name') for a in mediainfo.actors if a.get('name')]
                if actors:
                    result["actors"] = actors[:10]
                    logger.debug(f"[TMDB] 提取演员: {actors[:10]}")
            
            logger.info(f"[TMDB] 找到: {title} -> tmdbid={result.get('tmdbid')}")
            return result
        except Exception as e:
            logger.debug(f"[TMDB] 搜索异常: {e}")
            return None
    
    # ==================== 缓存与持久化 ====================
    
    def _load_cache(self):
        try:
            self._task_cache = self.get_data("tasks") or {}
            self._title_mapping = self.get_data("title_mapping") or {}
            logger.debug(f"[短剧整理器] 加载缓存: 映射={len(self._title_mapping)}条")
        except Exception as e:
            logger.error(f"[短剧整理器] 加载缓存失败: {e}")
    
    def _save_cache(self):
        try:
            self.save_data("tasks", self._task_cache)
            self.save_data("title_mapping", self._title_mapping)
            logger.debug(f"[短剧整理器] 缓存已保存 (映射{len(self._title_mapping)}条)")
        except Exception as e:
            logger.error(f"[短剧整理器] 保存缓存失败: {e}")
    
    def _save_mapping(self, source_path: str, result: dict, drama_info: dict):
        """写入系统 transferhistory 表，同时更新 _task_cache（仅保留最近200条用于面板）"""
        try:
            key = str(Path(source_path).parent.name)
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 写入系统 transferhistory 表
            try:
                from app.db import ScopedSession
                
                tmdbid = drama_info.get("tmdbid")
                seasons = f"S{int(drama_info.get('season', 1)):02d}"
                episodes = f"E{int(drama_info.get('episode', 1)):02d}"
                
                # 构造文件信息 JSON（与系统格式一致）
                src_path = Path(source_path)
                dest_path = Path(result.get("target_path", ""))
                
                def make_fileitem(path: Path) -> dict:
                    stat = path.stat() if path.exists() else None
                    return {
                        "path": str(path),
                        "storage": "local",
                        "type": "file",
                        "name": path.name,
                        "basename": path.stem,
                        "extension": path.suffix.lstrip("."),
                        "size": stat.st_size if stat else 0,
                        "modify_time": stat.st_mtime if stat else 0,
                        "children": [],
                        "fileid": None,
                        "parent_fileid": None,
                        "thumbnail": None,
                        "pickcode": None,
                        "drive_id": None,
                        "url": None,
                    }
                
                src_fileitem = make_fileitem(src_path)
                dest_fileitem = make_fileitem(dest_path)
                
                db = ScopedSession()
                try:
                    db.execute(
                        text("INSERT INTO transferhistory "
                             "(src, src_storage, src_fileitem, dest, dest_storage, dest_fileitem, "
                             "mode, type, category, title, year, tmdbid, seasons, episodes, status, date) "
                             "VALUES (:src, 'local', :src_fileitem, :dest, 'local', :dest_fileitem, "
                             ":mode, :type, :category, :title, :year, :tmdbid, :seasons, :episodes, true, :date)"),
                        {
                            "src": source_path,
                            "src_fileitem": json.dumps(src_fileitem),
                            "dest": result.get("target_path", ""),
                            "dest_fileitem": json.dumps(dest_fileitem),
                            "mode": self._config.transfer_type or "link",
                            "type": self._config.media_type or "电视剧",
                            "category": self._config.category or "短剧",
                            "title": drama_info.get("title", "未知短剧"),
                            "year": drama_info.get("year", ""),
                            "tmdbid": tmdbid if tmdbid else None,
                            "seasons": seasons,
                            "episodes": episodes,
                            "date": now,
                        }
                    )
                    db.commit()
                    logger.debug(f"[短剧整理器] 已写入 transferhistory: {drama_info.get('title')} {seasons}{episodes}")
                except Exception:
                    db.rollback()
                    raise
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"[短剧整理器] 写入 transferhistory 失败: {e}")
            
            # 更新 _task_cache（仅保留最近200条）
            self._task_cache[key] = {
                "source": source_path,
                "target": result.get("target_path", ""),
                "title": drama_info.get("title", "未知短剧"),
                "timestamp": time.time()
            }
            # 超过200条时清理最旧的
            if len(self._task_cache) > 200:
                sorted_keys = sorted(self._task_cache.keys(),
                                     key=lambda k: self._task_cache[k].get("timestamp", 0))
                for old_key in sorted_keys[:-200]:
                    del self._task_cache[old_key]
            self.save_data("tasks", self._task_cache)
        except Exception as e:
            logger.error(f"[短剧整理器] 保存映射失败: {e}")
    
    def _check_transfer_history(self, src_path: str) -> bool:
        """检查 transferhistory 是否已有相同 src 的记录"""
        try:
            from app.db import ScopedSession
            db = ScopedSession()
            try:
                result = db.execute(
                    text("SELECT id FROM transferhistory WHERE src = :src LIMIT 1"),
                    {"src": src_path}
                )
                return result.fetchone() is not None
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[短剧整理器] 查询 transferhistory 失败: {e}")
            return False
    
    def _delete_transfer_history(self, src_path: str):
        """删除 transferhistory 中指定 src 的记录"""
        try:
            from app.db import ScopedSession
            db = ScopedSession()
            try:
                db.execute(
                    text("DELETE FROM transferhistory WHERE src = :src"),
                    {"src": src_path}
                )
                db.commit()
                logger.debug(f"[短剧整理器] 已删除旧整理记录: {src_path}")
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[短剧整理器] 删除 transferhistory 失败: {e}")
    
    def _delete_transfer_by_hash(self, download_hash: str):
        """根据下载哈希对应的种子信息，通过目标路径匹配删除 transferhistory 记录"""
        try:
            from app.db import ScopedSession
            db = ScopedSession()
            try:
                # 从 torrents 数据中找到该哈希对应的种子信息
                torrent_tasks = self.get_data("torrents") or {}
                info = torrent_tasks.get(download_hash)
                if info:
                    # 通过种子标题模糊匹配 dest 路径
                    title = info.get("title", "")
                    if title:
                        result = db.execute(
                            text("DELETE FROM transferhistory WHERE src LIKE :pattern"),
                            {"pattern": f"%{title}%"}
                        )
                        db.commit()
                        if result.rowcount > 0:
                            logger.debug(f"[短剧整理器] 已删除整理历史: {title}, {result.rowcount}条")
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[短剧整理器] 删除整理历史失败: {e}")
    
    # ==================== 通知 ====================
    
    def _send_notification(self, text: str):
        try:
            self.post_message(
                mtype=NotificationType.Organize,
                title="【短剧整理器】",
                text=text
            )
        except Exception as e:
            logger.error(f"[短剧整理器] 发送通知失败: {e}")
    
    # ==================== 命令处理 ====================
    
    @eventmanager.register(EventType.PluginAction)
    def handle_command(self, event: Event):
        action = (event.event_data or {}).get("action")
        
        if action == "stats":
            result = self._show_stats()
        elif action == "clear":
            result = self._clear_cache()
        elif action == "scan":
            result = self._force_scan()
        else:
            return
        
        self.post_message(mtype=NotificationType.Organize, title="【短剧整理器】", text=result)
    
    def _show_stats(self) -> str:
        statistic = self.get_data("statistic") or {}
        torrents = self.get_data("torrents") or {}
        return (
            f"📊 短剧整理器统计\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"下载种子数: {statistic.get('count', 0)}\n"
            f"活跃种子: {statistic.get('active', 0)}\n"
            f"已删除: {statistic.get('deleted', 0)}\n"
            f"总上传: {StringUtils.str_filesize(statistic.get('uploaded') or 0)}\n"
            f"总下载: {StringUtils.str_filesize(statistic.get('downloaded') or 0)}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"监控路径: {', '.join(self._config.monitor_paths) if self._config and self._config.monitor_paths else '未配置'}"
        )
    
    def _clear_cache(self) -> str:
        with self._lock:
            self._task_cache = {}
            self._title_mapping = {}
            self._processing_files.clear()
            # 清空系统缓存（Redis 后端）
            self._drama_cache.clear()
        self._save_cache()
        return "✅ 缓存已清空"
    
    def _force_scan(self) -> str:
        threading.Thread(target=self._scan_and_process, daemon=True).start()
        return "✅ 扫描任务已启动"
