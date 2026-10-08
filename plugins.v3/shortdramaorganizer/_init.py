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
import asyncio
from pathlib import Path
from typing import Any, List, Dict, Tuple, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, Future, as_completed

import chardet
from lxml import etree
from lxml.etree import Element, SubElement, tostring, parse
from apscheduler.triggers.interval import IntervalTrigger

# 稳定 SDK 入口（MoviePilot V3）。
# 旧路径 app.core.* / app.utils.* / app.log / app.helper.* 在 V3 只由宿主兼容层
# 精确承接，命中时会输出"请迁移"的兼容警告，因此这里统一改用 app.sdk.*。
from app.sdk.cache import TTLCache
from app.sdk.config import settings
from app.sdk.events import Event, eventmanager
from app.sdk.logging import logger
from app.sdk.network import RequestUtils
from app.sdk.utilities import SystemUtils
# app.plugins 属于宿主仍在维护的公开入口（基类符号由兼容层精确承接）
from app.plugins import _PluginBase
from app.schemas.types import EventType, NotificationType, MediaType

# 尝试导入可选依赖
try:
    from app.sdk.network import SitesHelper
    from app.sdk.services import DownloaderHelper
    from app.sdk.media import MetaInfo
    from app.modules.indexer.spider import SiteSpider
    from app.chain.torrents import TorrentsChain
    from app.chain.media import MediaChain
    HAS_FRAMEWORK = True
except ImportError as e:
    HAS_FRAMEWORK = False
    logger.warning(f"[短剧整理器] 部分框架模块不可用: {e}")


# ==================== 常量 ====================

EPISODE_PATTERNS = [
    re.compile(r'[sS](\d+)[eE](\d+)'),
    re.compile(r'[eE][pP]?(\d+)'),
    re.compile(r'第\s*(\d+)\s*集'),
    ]

# 剧名中的季信息标记：Season 2 / full season 1 / S01 / 第二季 / 第3部
SEASON_TOKEN_PATTERNS = [
    re.compile(r'(?:full\s*)?season\s*0*\d+', re.IGNORECASE),
    # 排除 S01E02 这类"季+集"连写，避免把集数标记也吃掉
    re.compile(r'[sS]0*\d{1,2}(?!\d)(?!\s*[eE]\d)'),
    re.compile(r'第\s*0*\d+\s*[季部]'),
    re.compile(r'第\s*[一二三四五六七八九十]+\s*[季部]'),
]

# 文件名/目录名中的非法字符
_ILLEGAL_NAME_CHARS = re.compile(r'[\\/*?:"<>|]')
# 清理季信息后可能残留的分隔符
_NAME_SEPARATORS = r'\s\-_.·：:、,，;；'


def clean_season_title(title: str) -> str:
    """清理剧名中的季信息，让同一部剧的不同季归到同一个剧名

    "闪婚老公是豪门 S01" / "闪婚老公是豪门 第二季" -> "闪婚老公是豪门"
    "坏蛋是怎样炼成的：S12" -> "坏蛋是怎样炼成的"（顺带清掉孤立的冒号）
    "某剧 Season 2" / "某剧 full season 1" -> "某剧"

    若清理后为空（剧名本身就是季信息，如"第一季"），则退回原始剧名，避免出现空剧名。
    """
    raw = _ILLEGAL_NAME_CHARS.sub('', (title or '').strip())
    if not raw:
        return ''

    cleaned = raw
    for pattern in SEASON_TOKEN_PATTERNS:
        cleaned = pattern.sub(' ', cleaned)

    # 收紧剔除季信息后残留的分隔符与空白
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)
    cleaned = re.sub(r'[%s]{2,}' % _NAME_SEPARATORS, ' ', cleaned)
    cleaned = re.sub(r'^[%s]+' % _NAME_SEPARATORS, '', cleaned)
    cleaned = re.sub(r'[%s]+$' % _NAME_SEPARATORS, '', cleaned)
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)
    # 剔除季信息后可能留下空括号，如 "某某（第二季）" -> "某某（）"
    cleaned = re.sub(r'[（(]\s*[）)]', '', cleaned)
    cleaned = re.sub(r'[\[［]\s*[\]］]', '', cleaned)

    return cleaned or raw

DEFAULT_PT_SITES = [
    {
        "domain": "agsvpt.com",
        "name": "AGSV",
        "search_url": "https://www.agsvpt.com/torrents.php?search_mode=0&search_area=0&page=0&notnewword=1&cat=419&search={title}",
    },
    {
        "domain": "hdkyl.in",
        "name": "麒麟",
        "search_url": "https://www.hdkyl.in/torrents.php?search_mode=0&search_area=0&page=0&notnewword=1&cat=421&search={title}",
    },
    {
        "domain": "zmpt.cc",
        "name": "织梦",
        "search_url": "https://zmpt.cc/torrents.php?search_mode=0&search_area=0&page=0&notnewword=1&tagid=13&search={title}",
    },
    {
        "domain": "ptskit.org",
        "name": "PTSKit",
        "search_url": "https://www.ptskit.org/torrents.php?search_mode=0&search_area=0&page=0&notnewword=1&tag_id=238&search={title}",
    },
]


# ==================== 站点信息读取 ====================

class SiteInfo:
    """站点信息的最小视图（V3）

    屏蔽不同宿主版本下站点数据的形态差异（dict 快照 / ORM 对象），
    只暴露本插件真正需要的四个字段。
    """

    __slots__ = ("site_id", "name", "domain", "cookie")

    def __init__(self, site_id=None, name: str = "", domain: str = "", cookie: str = ""):
        self.site_id = site_id
        self.name = name or ""
        self.domain = domain or ""
        self.cookie = cookie or ""


def _site_field(obj, key: str) -> str:
    """从 dict 或对象上读取站点字段，兼容两种数据形态"""
    if obj is None:
        return ""
    if isinstance(obj, dict):
        value = obj.get(key)
    else:
        value = getattr(obj, key, None)
    return "" if value is None else str(value)


def get_site_info(domain: Optional[str] = None, site_id: Optional[int] = None) -> Optional[SiteInfo]:
    """读取站点信息（name / domain / cookie）

    V3 的稳定入口是 SitesHelper 的站点索引配置。该入口只提供索引元数据、
    拿不到 Cookie 时，退回 V3 兼容层已登记的 app.db.site_oper（等价于宿主
    自身的站点仓储）。两条路都不可用时返回 None，调用方需自行降级。
    """
    if not HAS_FRAMEWORK:
        return None

    # 1) 稳定入口：SitesHelper 的站点索引配置
    try:
        helper = SitesHelper()
        indexer = None
        if domain:
            indexer = helper.get_indexer(domain)
        elif site_id is not None:
            for item in helper.get_indexers() or []:
                if _site_field(item, "id") == str(site_id):
                    indexer = item
                    break
        if indexer:
            info = SiteInfo(
                site_id=_site_field(indexer, "id") or None,
                name=_site_field(indexer, "name"),
                domain=_site_field(indexer, "domain") or (domain or ""),
                cookie=_site_field(indexer, "cookie"),
            )
            if info.cookie:
                return info
    except Exception as e:
        logger.debug(f"[短剧整理器] SitesHelper 读取站点失败: {e}")

    # 2) 宿主站点数据：canonical Oper（app.db.oper.* 属宿主仍维护的稳定入口）
    oper = None
    try:
        from app.db.oper.site import SiteOper
        oper = SiteOper()
    except Exception:
        try:
            # 宿主版本差异兜底：V3 兼容层登记的旧路径
            from app.db.site_oper import SiteOper
            oper = SiteOper()
        except Exception as e:
            logger.debug(f"[短剧整理器] 站点 Oper 不可用: {e}")

    if oper is not None:
        try:
            record = oper.get_by_domain(domain) if domain else oper.get(int(site_id))
            if record:
                return SiteInfo(
                    site_id=_site_field(record, "id") or None,
                    name=_site_field(record, "name"),
                    domain=_site_field(record, "domain") or (domain or ""),
                    cookie=_site_field(record, "cookie"),
                )
        except Exception as e:
            logger.debug(f"[短剧整理器] 站点 Oper 读取失败: {e}")

    return None


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

        #  先移除开头的点号和空格
        title = title.lstrip('. ')

        # 移除括号及其内容（中文括号、英文括号）
        title = re.sub(r'[（(].*', '', title)
        
        # 先移除括号字符本身（方括号、中文括号、英文括号），保留括号内的内容
        # 必须在点号截断之前执行，否则 [中文名].英文名 会被点号提前截断
        title = re.sub(r'[\[\]（）()]', '', title)
        
        # 移除空格及后面的杂质内容
        title = re.sub(r'\s+\S+.*', '', title)

        # 移除点号及后面的所有内容（只保留剧名）
        title = re.sub(r'\..*', '', title)
        
        # 移除集数标记及后面内容
        title = re.sub(r'\d+集.*', '', title)
        
        # 移除 & 及后面的演员名
        title = re.sub(r'&.*', '', title)

        #  新增：移除 $ 和 ＄ 符号本身（保留文字）
        title = re.sub(r'[$＄]', '', title)
        
        # 移除 - 横杠及后面的发布组标记
        title = re.sub(r'\s*[-－—]\s*.*', '', title)
        
        
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
        folder_name = path.parent.name
        
        title = self.extract_title(folder_name)
        if not title:
            logger.warning(f"[短剧识别] 无法从文件夹名提取剧名: {folder_name}")
            return None
        
        return {
            "title": title,
            "season": self.extract_season(path.name),
            "episode": self.extract_episode(path.name),
            "folder_name": folder_name,
            "file_name": path.name,
            "source_path": str(path),
        }


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
        self.exclude_patterns: List[str] = self._parse_keywords(
            config.get("exclude_patterns", ["*.sample", "*.nfo", "临时/", "*.!qB", "*.part", "*.parts", "*.tmp", ".unwanted/", "*__??????"])
        )
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


# ==================== PT站点信息补全 ====================

class PTInfoFetcher:
    """PT站点信息补全"""
    
    def __init__(self, config: ShortDramaConfig):
        self.config = config
        self._site_cache: Dict[str, Any] = {}
    
    def _get_page_source(self, url: str, site) -> Optional[str]:
        """获取页面源码"""
        import requests as req_lib
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
                except (UnicodeDecodeError, LookupError):
                    if re.search(r"charset=\"?utf-8\"?", ret.text, re.IGNORECASE):
                        ret.encoding = "utf-8"
                    else:
                        ret.encoding = ret.apparent_encoding
                    return ret.text or ""
            
            return ret.text or ""
        
        except req_lib.Timeout:
            logger.error(f"[PT信息] 请求超时: {url[:60]}")
            return None
        except req_lib.ConnectionError:
            logger.error(f"[PT信息] 连接失败: {url[:60]}")
            return None
        except Exception as e:
            logger.error(f"[PT信息] 获取页面失败: {url[:60]}, {e}")
            return None
    
    def _get_site(self, domain: str) -> Optional[Any]:
        """获取站点"""
        if not HAS_FRAMEWORK:
            return None
        
        if domain not in self._site_cache:
            try:
                # V3：优先 SitesHelper，兼容层兜底；返回带 cookie/name/domain 的视图
                self._site_cache[domain] = get_site_info(domain=domain)
            except Exception as e:
                logger.error(f"[PT信息] 获取站点失败 {domain}: {e}")
                self._site_cache[domain] = None
        return self._site_cache[domain]
    def _extract_from_detail(self, html: etree._Element, config: dict) -> dict:
        """从详情页提取信息"""
        site_name = config.get("name", "未知站点")
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
                logger.debug(f"[PT信息] [{site_name}] kdescr 内容: {full_text[:200]}")
            else:
                logger.debug(f"[PT信息] [{site_name}] kdescr 内容为空")
                return result
        else:
            logger.debug(f"[PT信息] [{site_name}] 未找到 kdescr 元素")
            return result
        
        # 直接用原有正则，两个站点都能匹配
        regex_map = {
            "title": r'(?:片\s*名|译\s*名)\s*[:：]?\s*([^\n]+)',
            "year": r'年\s*代\s*[:：]?\s*([^\n]+)',
            "country": r'产\s*地\s*[:：]?\s*([^\n]+)',
            "genres": r'类\s*别\s*[:：]?\s*([^\n]+)',
            "actors": r'主\s*演\s*[:：]?\s*([\s\S]+?)(?=\n◎|\n\s*\n|简\s*介|$)',
            "episodes": r'集\s*数\s*[:：]?\s*(\d+)',
            "doubanid": r'豆瓣\s*链接.*?subject/(\d+)',
            "overview": r'简\s*介\s*[:：]?\s*\n?\s*([\s\S]+?)(?=\n\s*\n|\s*引用|\s*General|$)',
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
            
            search_title = title
            if year and "agsvpt.com" in domain:
                search_title = f"{title} {year}"
            
            try:
                url = search_url.format(title=search_title)
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
                            elif key == "poster_url" and value:
                                # 收集所有站点的海报 URL，按站点顺序存入列表
                                if "poster_urls" not in merged:
                                    merged["poster_urls"] = []
                                if value not in merged["poster_urls"]:
                                    merged["poster_urls"].append(value)
                except Exception as e:
                    logger.error(f"[PT信息] 站点搜索异常: {e}")
        
        if not merged:
            logger.warning(f"[PT信息] 所有站点搜索失败: {title}")
            return None
        
        merged["source"] = ", ".join(sources)
        logger.info(f"[PT信息] 合并结果 (来源: {merged['source']})")
        logger.info(f"[PT信息] 合并内容: {json.dumps(merged, ensure_ascii=False, default=str)[:500]}")
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
                site = get_site_info(site_id=int(site_id))
                if not site:
                    continue
                
                # 使用系统 TorrentsChain 获取种子
                torrents = TorrentsChain().browse(domain=site.domain)
                if not torrents:
                    continue
                
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
                        # 记录种子归属站点，避免后续一律记成第一个站点
                        "site_name": getattr(site, 'name', '') or '',
                    })
                
                logger.info(f"[种子服务] {site.name}: {len(torrents)} 个种子")
            except ValueError:
                logger.error(f"[种子服务] 站点ID格式无效: {site_id}")
            except ConnectionError:
                logger.error(f"[种子服务] 站点 {site_id} 连接失败")
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
    
    def check_exists(self, torrent_title: str, downloader_name: str) -> bool:
        """检查种子标题是否已在下载器中存在（去重）"""
        if not downloader_name or not torrent_title:
            return False
        try:
            service = DownloaderHelper().get_service(name=downloader_name)
            if not service or not service.instance:
                return False
            dl = service.instance
            all_t, err = dl.get_torrents()
            if err or not all_t:
                return False
            search_lower = torrent_title.lower().strip()
            for t in all_t:
                name = (t.name if hasattr(t, 'name') else t.get("name", "")).lower().strip()
                if name and (name == search_lower or name.startswith(search_lower) or search_lower.startswith(name)):
                    return True
            return False
        except Exception:
            return False
    
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
        from urllib.parse import urlparse
        try:
            parsed = urlparse(enclosure)
            domain = parsed.netloc
            
            site = get_site_info(domain=domain)
            if not site or not site.cookie:
                domain_parts = domain.split('.')
                if len(domain_parts) >= 2:
                    main_domain = '.'.join(domain_parts[-2:])
                    site = get_site_info(domain=main_domain)
            
            if not site or not site.cookie:
                logger.warning(f"[种子服务] 未找到站点 {domain} 的Cookie，可能无法下载种子")
                cookie = ""
            else:
                cookie = site.cookie
        except (ValueError, AttributeError) as e:
            logger.warning(f"[种子服务] 解析站点Cookie失败: {e}")
            cookie = ""
        
        # 2. 下载种子文件
        import requests as req_lib
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
        except req_lib.Timeout:
            logger.error(f"[种子服务] 下载种子文件超时: {title[:30]}")
            return None
        except req_lib.ConnectionError:
            logger.error(f"[种子服务] 下载种子文件连接失败: {title[:30]}")
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
        except (ConnectionError, OSError) as e:
            logger.error(f"[种子服务] 下载器连接异常: {e}")
            return None
        except Exception as e:
            logger.error(f"[种子服务] 下载异常: {e}")
            return None


# ==================== 整理器 ====================

class ShortDramaOrganizer:
    """短剧整理器 - 转移文件、生成NFO"""
    
    def __init__(self, config: ShortDramaConfig):
        self.config = config
    
    def organize(self, file_path: str, drama_info: dict, process_nfo: bool = True) -> dict:
        try:
            source = Path(file_path)
            if not source.exists():
                return {"success": False, "error": f"源文件不存在: {file_path}"}
            
            target_path = self._build_target_path(drama_info)
            if not target_path:
                return {"success": False, "error": "无法构建目标路径"}
            
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            series_dir = target_path.parent.parent
            
            # ✅ 总是处理海报，但 NFO 只在首次生成
            if process_nfo:
                self._generate_nfo(series_dir, drama_info)
                
                poster_path = series_dir / "poster.jpg"
                if not poster_path.exists():
                    poster_saved = False
                    source_dir = source.parent
                    
                    # 先找 poster 关键字或最后字符为0的图片（如 0.jpg, 10.jpg, 20.jpg）
                    for img_ext in ['.jpg', '.jpeg', '.png', '.webp']:
                        for img_file in source_dir.glob(f"*{img_ext}"):
                            if img_file.is_file() and ('poster' in img_file.stem.lower() or img_file.stem.endswith('0')):
                                try:
                                    shutil.copy2(str(img_file), str(poster_path))
                                    logger.info(f"[海报] 从源目录复制: {img_file.name}")
                                    poster_saved = True
                                    break
                                except Exception as e:
                                    logger.warning(f"[海报] 复制失败: {e}")
                        if poster_saved:
                            break
                    
                    # 没有本地图片，从URL下载（优先 TMDB，再依次尝试各 PT 站点）
                    downloaded_url = ""
                    if not poster_saved:
                        poster_urls = drama_info.get("poster_urls") or []
                        
                        # ---------- 增强日志 ----------
                        logger.info(f"[海报] 准备从 URL 下载海报，目标路径: {poster_path}")
                        logger.info(f"[海报] 候选 URL 数量: {len(poster_urls)}")
                        if poster_urls:
                            # 打印前3个URL以便快速查看
                            preview = poster_urls[:3]
                            logger.debug(f"[海报] URL 列表预览: {preview}")
                        else:
                            logger.warning("[海报] ⚠️ drama_info 中没有任何海报 URL（poster_urls 为空）")
                            logger.debug(f"[海报] drama_info 中与海报相关的字段: poster_url={drama_info.get('poster_url')}, "
                                        f"poster_urls={drama_info.get('poster_urls')}, "
                                        f"tmdb_info poster_url={drama_info.get('tmdb_poster_url')}")  # 假设可能有其他字段
                        # --------------------------------
                        
                        if poster_urls:
                            downloaded_url = self._download_poster(poster_urls, poster_path)
                            if downloaded_url:
                                logger.info(f"[海报] ✅ URL 下载成功，来源: {downloaded_url[:80]}")
                            else:
                                logger.warning("[海报] ❌ 所有 URL 尝试下载均失败")
                        else:
                            logger.info("[海报] 跳过 URL 下载（无可用 URL）")
                    else:
                        logger.info(f"[海报] 已通过本地复制获取海报，跳过 URL 下载")

                    # 记录实际成功的海报 URL（本地复制用 TMDB，下载用成功的 URL）
                    if poster_saved:
                        drama_info["_downloaded_poster"] = drama_info.get("poster_url") or ""
                        logger.debug(f"[海报] 本地复制成功，记录 poster_url: {drama_info.get('poster_url')}")
                    elif downloaded_url:
                        drama_info["_downloaded_poster"] = downloaded_url
                        logger.debug(f"[海报] URL 下载成功，记录 URL: {downloaded_url[:80]}")
                    else:
                        logger.warning("[海报] ⚠️ 未能获取任何海报，_downloaded_poster 将保持空值")
            
            # 实际转移文件
            if not self._transfer_file(source, target_path):
                return {"success": False, "error": "文件转移失败"}
            
            return {
                "success": True,
                "source_path": str(source),
                "target_path": str(target_path)
            }
            
        except Exception as e:
            logger.error(f"[整理] 整理失败: {e}")
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
        # 剧名目录不带季信息（S01 / 第二季 / Season 2 等），并剔除非法字符
        safe_title = clean_season_title(title) or "未知短剧"
        
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
            
            # 豆瓣 ID
            if info.get("doubanid"):
                uniqueid = SubElement(root, "uniqueid")
                uniqueid.set("type", "douban")
                uniqueid.text = str(info["doubanid"])
            
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
    
    def _download_poster(self, url, poster_path: Path) -> str:
        """下载海报，支持单个 URL 或 URL 列表，依次尝试。返回成功下载的 URL，失败返回空字符串"""
        try:
            # 1. 参数校验
            if not url:
                logger.debug("[海报] 未提供任何海报 URL，跳过下载")
                return ""
            if poster_path.exists():
                logger.debug(f"[海报] 海报文件已存在，跳过下载: {poster_path}")
                return ""

            # 2. 准备 URL 列表
            urls = url if isinstance(url, list) else [url]
            # 过滤空 URL
            urls = [u for u in urls if u]
            if not urls:
                logger.debug("[海报] URL 列表为空，跳过下载")
                return ""

            logger.info(f"[海报] 开始下载海报，共 {len(urls)} 个候选 URL，目标: {poster_path}")

            # 3. 依次尝试每个 URL
            for idx, u in enumerate(urls, 1):
                # 若中途海报已存在（可能被其他线程创建），则停止
                if poster_path.exists():
                    logger.debug(f"[海报] 下载过程中海报文件已存在，停止尝试")
                    return ""

                logger.debug(f"[海报] 尝试 URL #{idx}/{len(urls)}: {u[:80]}...")

                try:
                    response = RequestUtils(timeout=30).get_res(u)
                    if not response:
                        logger.warning(f"[海报] URL #{idx} 请求无响应: {u[:60]}")
                        continue

                    if response.status_code != 200:
                        logger.warning(f"[海报] URL #{idx} 返回非 200 状态码: {response.status_code}, {u[:60]}")
                        continue

                    # 写入文件
                    poster_path.write_bytes(response.content)
                    logger.info(f"[海报] ✅ 下载成功 (URL #{idx}): {poster_path}，来源: {u[:80]}")
                    return u

                except Exception as e:
                    logger.warning(f"[海报] URL #{idx} 下载异常: {u[:60]}, 错误: {e}")
                    continue

            # 4. 所有 URL 均失败
            logger.warning(f"[海报] ❌ 所有 {len(urls)} 个 URL 均尝试失败，未能下载海报")
            return ""

        except Exception as e:
            logger.error(f"[海报] 下载过程发生未预期异常: {e}")
            return ""


# ==================== 同步删除 (Webhook) ====================

class WebhookHandler:
    """同步删除处理器 - 根据 Emby 删除事件中的剧名匹配并删除下载器种子"""
    
    def __init__(self, config: ShortDramaConfig, plugin):
        self.config = config
        self.plugin = plugin
        
        # 使用TTLCache防重
        self._processed = TTLCache(maxsize=1000, ttl=60)
        
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

            # 独立删除整理记录（不依赖种子删除结果，按媒体标题匹配输出路径 dest）
            try:
                self.plugin._delete_transfer_by_title(item_name)
            except Exception as e:
                logger.error(f"[Webhook] 删除整理记录失败: {item_name}: {e}")

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
        """根据剧名匹配并删除种子（遍历所有系统配置的下载器）"""
        try:
            # 获取所有系统配置的下载器名称
            try:
                downloader_names = list(DownloaderHelper().get_configs().keys())
            except Exception as e:
                logger.error(f"[删除] 获取下载器列表失败: {e}")
                return
            
            if not downloader_names:
                logger.warning("[删除] 系统未配置下载器，跳过删除种子")
                return
            
            total_deleted = 0
            for downloader_name in downloader_names:
                downloader = self._get_downloader(downloader_name)
                if not downloader:
                    logger.warning(f"[删除] 下载器 {downloader_name} 不可用，跳过")
                    continue
                
                logger.info(f"[删除] 开始搜索种子: {item_name} @ {downloader_name}")
                torrents, error = downloader.get_torrents()
                if error:
                    logger.error(f"[删除] 获取种子列表失败: {downloader_name}: {error}")
                    continue
                if not torrents:
                    logger.debug(f"[删除] 下载器 {downloader_name} 中没有种子任务")
                    continue
                
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
                    logger.info(f"[删除] 下载器 {downloader_name} 未找到匹配的种子: {item_name}")
                    continue
                
                logger.info(f"[删除] 下载器 {downloader_name} 匹配到 {len(matched_hashes)} 个种子: {matched_names}")
                
                # 删除种子（含文件）
                for h in matched_hashes:
                    try:
                        # 从下载器获取种子详细信息
                        t = None
                        for torrent in torrents:
                            th = torrent.hashString if hasattr(torrent, 'hashString') else torrent.get("hash", "")
                            if th == h:
                                t = torrent
                                break
                        # 记录种子信息到数据面板
                        self.plugin._record_deleted_torrent(h, item_name, downloader_name, t)
                        # 删除种子
                        downloader.delete_torrents(ids=[h], delete_file=True)
                        logger.info(f"[删除] 已删除种子: {h[:8]}... @ {downloader_name}")
                        self.plugin._update_torrent_deleted(h)
                        total_deleted += 1
                    except Exception as e:
                        logger.error(f"[删除] 删除种子失败 {h[:8]}...: {e}")
            
            logger.info(f"[删除] 删除完成: {item_name}, 共 {total_deleted} 个种子")
                
        except Exception as e:
            logger.error(f"[删除] 删除种子失败: {e}")


# ==================== 内置监控（基于 watchfiles） ====================

class BuiltinMonitor:
    """内置目录监控（基于 watchfiles，支持立即停止）"""
    
    def __init__(self, config: ShortDramaConfig, callback: Callable, monitor_path: str):
        self.config = config
        self.callback = callback
        self._monitor_path = monitor_path
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._processing = set()
        self._lock = threading.RLock()
    
    def start(self):
        if not self._monitor_path or not Path(self._monitor_path).exists():
            logger.warning(f"[内置监控] 路径不存在，跳过: {self._monitor_path}")
            return
        
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name=f"ShortDramaMonitor-{Path(self._monitor_path).name}",
            daemon=True
        )
        self._thread.start()
        logger.info(f"[内置监控] 已启动: {self._monitor_path}")
    
    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None
        logger.info("[内置监控] 已停止")
    
    def _run(self):
        """运行 watchfiles 监控循环"""
        try:
            from watchfiles import watch, Change, DefaultFilter
            
            watch_filter = DefaultFilter()
            all_exts = settings.RMT_MEDIAEXT
            
            for changes in watch(
                str(self._monitor_path),
                watch_filter=watch_filter,
                stop_event=self._stop_event,
                rust_timeout=1000,
                yield_on_timeout=True,
                recursive=self.config.recursive,
                ignore_permission_denied=True,
            ):
                if self._stop_event.is_set():
                    break
                if not changes:
                    continue
                
                for change_type, path_str in changes:
                    if change_type not in (Change.added, Change.modified):
                        continue
                    if self._stop_event.is_set():
                        return
                    
                    event_path = Path(path_str)
                    # 只做最基本的扩展名过滤，其他检查由 _on_file_event 统一处理
                    if event_path.suffix.lower() not in all_exts:
                        continue
                    
                    self._handle(str(event_path))
        except Exception as e:
            if not self._stop_event.is_set():
                logger.error(f"[内置监控] 运行失败: {e}")
    
    def _handle(self, file_path: str):
        if self._stop_event.is_set():
            return
        with self._lock:
            if file_path in self._processing:
                return
            self._processing.add(file_path)
        
        # 防抖
        time.sleep(self.config.debounce_time)
        
        try:
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
    # V3 合同迁移基线：不再使用裸数据库会话（ScopedSession），宿主表统一走 Oper
    plugin_version = "2.0.0"
    plugin_author = "AI"
    plugin_config_prefix = "shortdramaorganizer_"
    plugin_order = 26
    auth_level = 1

    # 服务 / 任务 ID 带插件名前缀，避免多插件或虚拟分身抢占同一个稳定 ID
    _SVC_FETCH_ID = "shortdramaorganizer_fetch"
    _SVC_CHECK_ID = "shortdramaorganizer_check"
    
    # 私有属性
    _enabled: bool = False
    _stopping: bool = False
    _config: Optional[ShortDramaConfig] = None
    _executor: Optional[ThreadPoolExecutor] = None
    _processing_files: Dict[str, float] = {}
    _lock: threading.RLock = threading.RLock()
    _task_cache: dict = {}
    _drama_cache: Optional[TTLCache] = None
    # 持久化映射：文件夹名 -> 最终剧名
    # 首次识别后固定，缓存过期/重启后继续沿用，防止同剧分集落进不同剧名目录
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
                category = self._config.category or "短剧"
                deleted = self._clear_transfer_history(category)
                logger.info(f"[短剧整理器] 已清空类别 [{category}] 的整理历史，共 {deleted} 条")
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
            self._run_once("fetch", self._fetch_and_download, delay_seconds=3)
            config["onlyonce"] = False
            self.update_config(config)
        
        # 立即执行一次全量整理
        if config.get("organize_once"):
            logger.info("[短剧整理器] 立即执行一次全量整理")
            self._run_once(
                "organize",
                lambda: self._scan_and_process(force_full=True),
                delay_seconds=5,
            )
            config["organize_once"] = False
            self.update_config(config)
        
        # API 路由由 get_api() 返回，框架统一注册
        
        logger.info("[短剧整理器] ========== 初始化完成 ==========")
    
    def stop_service(self):
        logger.info("[短剧整理器] 停止服务")
        self._stopping = True
        self._enabled = False
        
        # 取消尚未执行的一次性任务（V3 由宿主调度器托管，必须显式撤销）
        for job_name in ("fetch", "organize", "scan"):
            try:
                from app.sdk.scheduler import remove_plugin_once_job
                remove_plugin_once_job(self.__class__.__name__, self._once_job_id(job_name))
            except Exception:
                pass
        
        if self._builtin_monitors:
            for m in self._builtin_monitors:
                m.stop()
            self._builtin_monitors = []
        
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None
        
        self._save_cache()
        logger.info("[短剧整理器] 服务已停止")

    @classmethod
    def _once_job_id(cls, job_name: str) -> str:
        """一次性任务的稳定 ID"""
        return f"{cls.__name__}_{job_name}_once"

    def _run_once(self, job_name: str, func: Callable, delay_seconds: float = 0) -> bool:
        """延后执行一次插件任务

        V3 由宿主调度器统一托管（替代插件自建线程 / BackgroundScheduler），任务
        可被跟踪，stop_service 时也能取消。宿主调度器不可用时降级为守护线程，
        保证配置页按钮仍然立刻生效。
        """
        try:
            from app.sdk.scheduler import add_plugin_once_job
            if add_plugin_once_job(
                plugin_id=self.__class__.__name__,
                job_id=self._once_job_id(job_name),
                func=func,
                name=f"{self.plugin_name}-{job_name}",
                delay_seconds=delay_seconds,
            ):
                return True
        except Exception as e:
            logger.warning(f"[短剧整理器] 宿主调度器不可用，改用线程执行一次: {e}")
        threading.Timer(delay_seconds, func).start()
        return False

    def get_state(self) -> bool:
        return self._enabled
    
    # ==================== 服务注册 ====================
    
    def get_service(self) -> List[Dict[str, Any]]:
        if not self._enabled or not self._config:
            return []
        
        services = []
        if self._config.refresh_interval > 0:
            services.append({
                "id": self._SVC_FETCH_ID,
                "name": "短剧整理器-种子获取",
                "trigger": IntervalTrigger(minutes=self._config.refresh_interval),
                "func": self._fetch_and_download,
                "kwargs": {}
            })
        # 种子状态检查（每5分钟）
        services.append({
            "id": self._SVC_CHECK_ID,
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
            "summary": "接收Emby删除事件",
            # Emby 属于外部系统调用：显式声明 apikey 鉴权，不开放匿名访问。
            # 配置 Webhook 地址时需带 ?apikey=<MoviePilot API Token>。
            "auth": "apikey",
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
            "monitor_path": "",
            "exclude_patterns": ["*.sample", "*.nfo", "临时/", "*.!qB", "*.part", "*.parts", "*.tmp", ".unwanted/", "*__??????"], "recursive": True, "incremental_scan": True,
            "transfer_type": "link", "media_library": "", "subdir": "短剧",
            "media_type": "电视剧", "category": "短剧",
            "pt_enabled": True, "delete_enabled": False, "clear_stats": False, "clear_history": False, "clear_cache": False,
            "debounce_time": 3,
            "use_proxy": False,
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
                            {"component": "VCol", "props": {"cols": 12}, "content": [
                                {"component": "VTextarea", "props": {"model": "monitor_path", "label": "监控路径", "rows": 3, "placeholder": "每行一个路径"}}
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
                                    "text": "监控路径中的文件会被自动识别为短剧并整理到媒体库。PT站点信息补全功能可以从AGSV、麒麟、织梦、PTSKit等短剧专用站点获取剧名、年份、简介、海报等元数据。"
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
            from app.sdk.services import DownloaderHelper
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
        
        from app.sdk.utilities import StringUtils
        
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
        """组装统计卡片"""
        statistic = self.get_data("statistic") or {
            "count": 0, "deleted": 0, "uploaded": 0, "downloaded": 0,
            "unarchived": 0, "active": 0, "active_uploaded": 0, "active_downloaded": 0
        }
        from app.sdk.utilities import StringUtils
        
        total_uploaded = StringUtils.str_filesize(statistic.get("uploaded") or 0)
        total_downloaded = StringUtils.str_filesize(statistic.get("downloaded") or 0)
        total_count = statistic.get("count") or 0
        total_deleted = statistic.get("deleted") or 0
        total_active = statistic.get("active") or 0
        total_active_uploaded = StringUtils.str_filesize(statistic.get("active_uploaded") or 0)
        total_active_downloaded = StringUtils.str_filesize(statistic.get("active_downloaded") or 0)
        
        # 下次刷流运行时间（V3 走稳定调度门面，不触碰 Scheduler 私有属性）
        next_run = ""
        try:
            from app.sdk.scheduler import list_scheduler_jobs
            target_job_id = f"{self.__class__.__name__}_{self._SVC_FETCH_ID}"
            for job in list_scheduler_jobs() or []:
                if str(getattr(job, "id", "") or "") != target_job_id:
                    continue
                value = getattr(job, "next_run", None) or getattr(job, "next_run_time", None)
                if value:
                    try:
                        from app.sdk.utilities import TimerUtils
                        next_run = TimerUtils.time_difference(value)
                    except Exception:
                        next_run = str(value)
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
    
    def _record_deleted_torrent(self, download_hash: str, title: str, downloader_name: str, torrent_obj=None):
        """同步删除时记录种子信息到数据面板"""
        try:
            torrent_tasks: Dict[str, dict] = self.get_data("torrents") or {}
            if download_hash not in torrent_tasks:
                info = {
                    "title": title,
                    "description": "",
                    "size": 0,
                    "site_name": "",
                    "downloader": downloader_name,
                    "uploaded": 0,
                    "downloaded": 0,
                    "ratio": 0,
                    "progress": 0,
                    "seeding_time": 0,
                    "hit_and_run": False,
                    "hash": download_hash,
                    "time": time.time(),
                    "deleted": True,
                    "delete_time": time.time(),
                    "active": False,
                }
                # 从种子对象中提取详细信息
                if torrent_obj:
                    # 兼容 Transmission 和 qBittorrent 的属性名差异
                    info["size"] = (getattr(torrent_obj, 'total_size', None) 
                                    or torrent_obj.get("total_size") 
                                    or getattr(torrent_obj, 'size', None) 
                                    or torrent_obj.get("size", 0))
                    info["uploaded"] = (getattr(torrent_obj, 'uploadedEver', None) 
                                        or torrent_obj.get("uploadedEver") 
                                        or getattr(torrent_obj, 'uploaded', None) 
                                        or torrent_obj.get("uploaded", 0))
                    info["downloaded"] = (getattr(torrent_obj, 'downloadedEver', None) 
                                          or torrent_obj.get("downloadedEver") 
                                          or getattr(torrent_obj, 'downloaded', None) 
                                          or torrent_obj.get("downloaded", 0))
                    info["ratio"] = getattr(torrent_obj, 'ratio', None) or torrent_obj.get("ratio", 0)
                    # 与状态刷新保持一致：统一换算成 0-100
                    info["progress"] = self._extract_progress(torrent_obj)
                    # 做种时间
                    seeding_time = (getattr(torrent_obj, 'seeding_time', None) 
                                    or torrent_obj.get("seeding_time"))
                    if seeding_time is None:
                        from datetime import datetime, timezone
                        date_added = getattr(torrent_obj, 'date_added', None) or torrent_obj.get("date_added")
                        if date_added:
                            if isinstance(date_added, datetime):
                                seeding_time = (datetime.now(timezone.utc) - date_added).total_seconds()
                            else:
                                seeding_time = 0
                        else:
                            seeding_time = 0
                    info["seeding_time"] = seeding_time
                    info["hit_and_run"] = (getattr(torrent_obj, 'hit_and_run', None) 
                                           or torrent_obj.get("hit_and_run", False))
                    # 从 tracker 中提取站点名称
                    site_name = ""
                    trackers = getattr(torrent_obj, 'trackers', None) or torrent_obj.get("trackers")
                    if trackers:
                        import re
                        for tracker in trackers:
                            if hasattr(tracker, 'announce'):
                                url = tracker.announce
                            else:
                                url = tracker.get("announce", "") if isinstance(tracker, dict) else str(tracker)
                            if url:
                                match = re.search(r'https?://([^/]+)', url)
                                if match:
                                    domain = match.group(1)
                                    # 尝试通过站点配置获取名称
                                    try:
                                        site = get_site_info(domain=domain)
                                        if site and site.name:
                                            site_name = site.name
                                            break
                                    except Exception:
                                        site_name = domain
                                        break
                    info["site_name"] = site_name
                    # 尝试从种子名称中提取描述
                    desc = torrent_obj.description if hasattr(torrent_obj, 'description') else torrent_obj.get("description", "")
                    if desc:
                        info["description"] = desc
                torrent_tasks[download_hash] = info
                self.save_data("torrents", torrent_tasks)
                logger.debug(f"[短剧整理器] 已记录删除的种子: {title}")
        except Exception as e:
            logger.error(f"[短剧整理器] 记录删除种子失败: {e}")
    
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
        """获取种子并下载（含去重和并发下载）"""
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
            
            # 去重：排除已在下载器中的种子
            downloader_name = self._config.downloader or ""
            # 已下载过的种子标题（含已删除），避免删除后重复下载
            torrent_tasks: Dict[str, dict] = self.get_data("torrents") or {}
            downloaded_titles = [
                t.get("title", "").lower().strip()
                for t in torrent_tasks.values()
                if t.get("title")
            ]
            to_download = []
            skipped = 0
            for torrent in filtered:
                title = torrent.get("title", "")
                if not title:
                    continue
                title_lower = title.lower().strip()
                # 已在下载器中
                if self._torrent_service.check_exists(title, downloader_name):
                    skipped += 1
                    logger.debug(f"[短剧整理器] 种子已在下载器中，跳过: {title[:40]}")
                    continue
                # 已下载过（含已删除），避免删除后重复下载
                if any(
                    dt and (dt == title_lower or dt.startswith(title_lower) or title_lower.startswith(dt))
                    for dt in downloaded_titles
                ):
                    skipped += 1
                    logger.debug(f"[短剧整理器] 种子已下载过，跳过: {title[:40]}")
                    continue
                to_download.append(torrent)
            
            if skipped:
                logger.info(f"[短剧整理器] 去重跳过 {skipped} 个种子")
            if not to_download:
                logger.info("[短剧整理器] 没有需要下载的新种子")
                return
            
            logger.info(f"[短剧整理器] 去重后剩余 {len(to_download)} 个种子，开始下载")
            
            downloaded = 0
            download_lock = threading.Lock()
            
            def _download_one(t):
                nonlocal downloaded
                if self._stopping:
                    return
                h = self._torrent_service.download(t)
                if h:
                    with download_lock:
                        downloaded += 1
                        torrent_tasks[h] = {
                            "title": t.get("title", ""),
                            "description": t.get("description", ""),
                            "size": t.get("size", 0),
                            # 站点名随种子一起带下来（fetch 阶段已标注归属站点）
                            "site_name": t.get("site_name", "") or "",
                            "downloader": downloader_name,
                            "time": time.time(),
                            "hash": h,
                        }
            
            # 并发下载，最多3个线程
            threads = []
            for t in to_download:
                if self._stopping:
                    break
                th = threading.Thread(target=_download_one, args=(t,), daemon=True)
                th.start()
                threads.append(th)
                if len(threads) >= 3:
                    for th in threads:
                        th.join(timeout=60)
                    threads = []
            for th in threads:
                th.join(timeout=60)
            
            self.save_data("torrents", torrent_tasks)
            # 立即更新统计（下载数/删除数），上传下载量由状态检查刷新
            statistic = self.get_data("statistic") or {}
            statistic["count"] = len(torrent_tasks)
            statistic["deleted"] = sum(1 for t in torrent_tasks.values() if t.get("deleted"))
            self.save_data("statistic", statistic)
            logger.info(f"[短剧整理器] 成功下载 {downloaded}/{len(to_download)} 个种子")
        except Exception as e:
            logger.error(f"[短剧整理器] 获取种子失败: {e}")
    
    @staticmethod
    def _extract_progress(torrent) -> float:
        """提取下载进度并统一为 0-100。

        两个下载器的字段语义不同，不能靠数值范围猜测：
          - qBittorrent: progress 是 0-1 小数（1.0 表示 100%）
          - Transmission: progress 是 0-100，另有 percentDone(0-1)
        旧实现用 "progress <= 1 就乘 100"，会把 Transmission 的 1% 当成 100%。
        这里改为按字段来源判断：优先识别 Transmission 的 percentDone。
        """
        def _get(key):
            value = getattr(torrent, key, None)
            if value is None and isinstance(torrent, dict):
                value = torrent.get(key)
            return value

        percent_done = _get("percentDone")
        if percent_done is not None:
            try:
                return float(percent_done) * 100  # Transmission: 0-1 -> 0-100
            except (TypeError, ValueError):
                return 0.0

        progress = _get("progress")
        if progress is None:
            return 0.0
        try:
            progress = float(progress)
        except (TypeError, ValueError):
            return 0.0
        # qBittorrent 的 progress 是 0-1 小数；若某些实现直接给 0-100 则原样使用
        return progress * 100 if progress <= 1 else progress

    def _check_torrents_status(self):
        """从下载器查询种子状态，更新统计数据（遍历所有系统配置的下载器）"""
        if not self._enabled:
            return
        
        torrent_tasks: Dict[str, dict] = self.get_data("torrents") or {}
        if not torrent_tasks:
            return
        
        try:
            # 获取所有系统配置的下载器
            try:
                downloader_names = list(DownloaderHelper().get_configs().keys())
            except Exception as e:
                logger.error(f"[短剧整理器] 获取下载器列表失败: {e}")
                return
            
            if not downloader_names:
                logger.warning("[短剧整理器] 系统未配置下载器，跳过状态检查")
                return
            
            # 只查询插件关心的哈希列表，避免全量遍历
            tracked_hashes = [h for h in torrent_tasks.keys() if h]
            if not tracked_hashes:
                return
            
            # 遍历所有下载器，收集种子状态及其归属下载器
            torrent_map = {}
            torrent_owner = {}
            for downloader_name in downloader_names:
                try:
                    service = DownloaderHelper().get_service(name=downloader_name)
                    if not service or not service.instance:
                        continue
                    dl = service.instance
                    
                    # 分批查询，每批最多50个哈希
                    batch_size = 50
                    for i in range(0, len(tracked_hashes), batch_size):
                        batch = tracked_hashes[i:i + batch_size]
                        try:
                            batch_torrents, err = dl.get_torrents(ids=batch)
                            if err:
                                logger.warning(f"[短剧整理器] 批量查询种子状态失败: {downloader_name}: {err}")
                                continue
                            if batch_torrents:
                                for t in batch_torrents:
                                    h = t.hashString if hasattr(t, 'hashString') else t.get("hash", "")
                                    if h:
                                        torrent_map[h] = t
                                        torrent_owner[h] = downloader_name
                        except Exception as e:
                            logger.warning(f"[短剧整理器] 批量查询异常: {downloader_name}: {e}")
                except Exception as e:
                    logger.warning(f"[短剧整理器] 下载器 {downloader_name} 查询异常: {e}")
            
            active_count = 0
            total_uploaded = 0
            total_downloaded = 0
            active_uploaded = 0
            active_downloaded = 0
            
            for h, info in torrent_tasks.items():
                t = torrent_map.get(h)
                if t:
                    # 兼容 qBittorrent (uploaded/downloaded/progress) 与 Transmission (uploadedEver/downloadedEver/percentDone)
                    uploaded = (getattr(t, 'uploaded', None)
                                or t.get("uploaded", 0)
                                or getattr(t, 'uploadedEver', None)
                                or t.get("uploadedEver", 0))
                    downloaded = (getattr(t, 'downloaded', None)
                                  or t.get("downloaded", 0)
                                  or getattr(t, 'downloadedEver', None)
                                  or t.get("downloadedEver", 0))
                    # 进度统一为 0-100（qB 与 Transmission 字段语义不同，按字段来源判断）
                    progress = self._extract_progress(t)
                    ratio = (getattr(t, 'ratio', None)
                             or t.get("ratio", 0)
                             or getattr(t, 'uploadRatio', None)
                             or t.get("uploadRatio", 0))
                    seeding_time = (getattr(t, 'seeding_time', None)
                                    or t.get("seeding_time", 0))
                    hit_and_run = (getattr(t, 'hit_and_run', None)
                                   or t.get("hit_and_run", False))
                    
                    info["uploaded"] = uploaded
                    info["downloaded"] = downloaded
                    info["ratio"] = ratio
                    info["progress"] = progress
                    info["seeding_time"] = seeding_time
                    info["hit_and_run"] = hit_and_run
                    info["active"] = True
                    # 刷新归属下载器，并在重新发现时“复活”记录（跨下载器迁移时保持面板连续）
                    info["downloader"] = torrent_owner.get(h) or info.get("downloader")
                    info["deleted"] = False
                    info.pop("delete_time", None)
                    
                    total_uploaded += uploaded
                    total_downloaded += downloaded
                    
                    if progress < 100:
                        active_count += 1
                        active_uploaded += uploaded
                        active_downloaded += downloaded
                else:
                    if not info.get("deleted"):
                        info["deleted"] = True
                        info["delete_time"] = time.time()
            
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
            skipped = 0
            
            for monitor_path_str in self._config.monitor_paths:
                if self._stopping:
                    logger.info("[短剧整理器] 停止信号，中断扫描")
                    return
                
                monitor_path = Path(monitor_path_str)
                if not monitor_path.exists():
                    logger.warning(f"[短剧整理器] 监控路径不存在: {monitor_path}")
                    continue
                
                logger.info(f"[短剧整理器] 扫描: {monitor_path}")
                
                # 增量模式下，先收集所有已有整理记录的 src 路径，避免重复处理
                processed_srcs = set()
                if self._config.incremental_scan and not force_full:
                    try:
                        target_category = self._config.category or "短剧"
                        processed_srcs = {
                            getattr(record, "src", None)
                            for record in self._iter_transfer_history()
                            if (getattr(record, "category", "") or "") == target_category
                            and getattr(record, "src", None)
                        }
                    except Exception as e:
                        logger.warning(f"[短剧整理器] 查询已有整理记录失败: {e}")
                
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
                            fp_str = str(video_file)
                            # 排除规则：跳过下载器残留临时目录/文件
                            if self._is_excluded(fp_str):
                                skipped += 1
                                continue
                            # 增量模式跳过已处理文件
                            if fp_str in processed_srcs:
                                skipped += 1
                                continue
                            if self._process_file(fp_str):
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
                                fp_str = str(video_file)
                                if self._is_excluded(fp_str):
                                    skipped += 1
                                    continue
                                if fp_str in processed_srcs:
                                    skipped += 1
                                    continue
                                if self._process_file(fp_str):
                                    processed += 1
            
            if processed > 0 or skipped > 0:
                logger.info(f"[短剧整理器] 扫描完成: 处理 {processed} 个, 跳过 {skipped} 个")
            else:
                logger.info("[短剧整理器] 扫描完成，无新文件")
        except Exception as e:
            logger.error(f"[短剧整理器] 扫描失败: {e}")
    
    def _is_excluded(self, path: str) -> bool:
        """检查路径是否被排除（支持目录/文件名通配符匹配）

        匹配范围包括：完整路径、文件名、以及路径中的每一段目录名。
        目录规则（如 “长篇/”、“临时/”、“.unwanted/”）会先去掉末尾斜杠再匹配。
        """
        if not self._config:
            return False
        
        path = str(path).replace("\\", "/").rstrip("/")
        if not path:
            return False
        
        path_obj = Path(path)
        # 候选匹配项：完整路径、文件名、路径中的每一段目录名
        candidates = [path, path_obj.name, *path_obj.parts]
        
        for raw_pattern in self._config.exclude_patterns:
            if not raw_pattern:
                continue
            # 兼容形如 “长篇/”、“临时/”、“.unwanted/” 的目录规则
            pattern = str(raw_pattern).replace("\\", "/").strip().rstrip("/")
            if not pattern:
                continue
            if any(fnmatch.fnmatch(candidate, pattern) for candidate in candidates):
                return True
        return False
    
    def _on_file_event(self, event_type: str, file_path: str):
        """文件事件回调"""
        if not self._enabled:
            return
        
        # 排除规则：跳过命中排除规则的路径（如下载器残留临时目录/文件）
        if self._is_excluded(file_path):
            logger.debug(f"[短剧整理器] 命中排除规则，忽略事件: {file_path}")
            return
        
        # 检查文件扩展名
        if Path(file_path).suffix.lower() not in settings.RMT_MEDIAEXT:
            return
        
        # 检查文件是否存在（系统 _build_event 逻辑：文件已消失则忽略）
        if not Path(file_path).exists():
            logger.debug(f"[短剧整理器] 文件已不存在，忽略事件: {file_path}")
            return
        
        # 检查文件大小是否有效（系统 _get_file_size 逻辑：大小为0或无法读取则忽略）
        try:
            file_size = Path(file_path).stat().st_size
            if file_size == 0:
                logger.debug(f"[短剧整理器] 文件大小为0，忽略事件: {file_path}")
                return
        except OSError:
            logger.debug(f"[短剧整理器] 无法读取文件大小，忽略事件: {file_path}")
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

    def _get_title_source(self, nfo_info: dict, tmdb_info: dict, pt_info: dict) -> str:
        """判断剧名最终来源"""
        if nfo_info and nfo_info.get("title"):
            return "📄 NFO文件"
        if tmdb_info and tmdb_info.get("_source"): 
            return "🎬 系统识别(TMDB)"
        if pt_info and pt_info.get("title"):
            return "🔗 PT站点"
        return "📁 基础提取"

    def _process_file(self, file_path: str) -> bool:
        if not self._enabled or self._stopping:
            return False
        
        file_path = str(Path(file_path).resolve())
        source_dir = str(Path(file_path).parent)
        
        with self._lock:
            if file_path in self._processing_files:
                logger.debug(f"[短剧整理器] 文件正在处理: {file_path}")
                return False
            self._processing_files[file_path] = time.time()
        
        try:
            logger.info(f"[短剧整理器] ========== 开始处理文件 ==========")
            logger.info(f"[短剧整理器] 文件路径: {file_path}")
            logger.info(f"[短剧整理器] 源文件夹: {source_dir}")
            
            # 检查 transferhistory 是否已有相同 src 的记录
            existing_record = self._check_transfer_history(file_path)
            if existing_record:
                if self._config.incremental_scan:
                    logger.info(f"[短剧整理器] 源文件已有整理记录，跳过: {file_path}")
                    return True
                else:
                    logger.info(f"[短剧整理器] 源文件已有整理记录，覆盖: {file_path}")
                    self._delete_transfer_history(file_path)
            
            # 检查持久化映射
            folder_name = ""
            if self._config and self._config.monitor_paths:
                fp = Path(file_path)
                for mp_str in self._config.monitor_paths:
                    mp = Path(mp_str)
                    if mp in fp.parents:
                        try:
                            rel = fp.relative_to(mp)
                            folder_name = rel.parts[0]
                        except ValueError:
                            continue
                        break
            if not folder_name:
                folder_name = Path(source_dir).name
            
            # 检查文件夹级缓存
            cached = self._drama_cache.get(source_dir)
            if cached:
                logger.info(f"[短剧整理器] 缓存命中，缓存字段: {list(cached.keys())}")
                drama_info = cached.copy()
                drama_info["source_path"] = file_path
                drama_info["file_name"] = Path(file_path).name
                drama_info["episode"] = self._recognizer.extract_episode(Path(file_path).name) if self._recognizer else 1
                # 旧缓存里可能存着带季信息的剧名，统一清理一次，保证目录名与 NFO 一致
                drama_info["title"] = (
                    clean_season_title(drama_info.get("title", "")) or drama_info.get("title", "")
                )
                logger.info(f"[短剧整理器] 使用缓存 -> title={drama_info.get('title')} season={drama_info.get('season')} episode={drama_info.get('episode')}")
                # 缓存命中：不处理NFO
                process_nfo = False
            else:
                logger.info(f"[短剧整理器] 缓存未命中，开始首次识别")
                logger.info(f"[短剧整理器] 文件夹名(原始): {folder_name}")
                
                base_title = self._recognizer.extract_title(folder_name) if self._recognizer else folder_name
                if not base_title:
                    logger.warning(f"[短剧整理器] extract_title返回空，放弃处理")
                    return False

                # 2️⃣ 初始化 drama_info
                drama_info = {
                    "title": base_title,
                    "season": 1,
                    "episode": 1,
                    "folder_name": folder_name,
                    "file_name": Path(file_path).name,
                    "source_path": file_path,
                }

                drama_info["episode"] = self._recognizer.extract_episode(Path(file_path).name) if self._recognizer else 1
                drama_info["season"] = self._recognizer.extract_season(Path(file_path).name) if self._recognizer else 1

                final_title = base_title

                # ✅ 3️⃣ 系统搜索识别
                tmdb_info = {}
                nfo_info = {}
                pt_info = {}

                if HAS_FRAMEWORK:
                    try:
                        # 用清洗后的中文名搜索 TMDB
                        search_title = base_title
                        logger.info(f"[短剧整理器] 系统搜索: {search_title}")
                        
                        meta = MetaInfo(search_title)
                        medias = asyncio.run(MediaChain().async_search_medias(meta=meta))
                        
                        # 检查 TMDB 返回的剧名是否合理：返回的剧名不能比搜索词长
                        # 例如搜索"走火"返回"走火炮"（3>2）说明是错误匹配
                        if medias and (
                            getattr(medias[0], "media_id", None)
                            or getattr(medias[0], "tmdb_id", None)
                        ):
                            result_title = medias[0].title or ''
                            if len(result_title) > len(base_title):
                                logger.warning(f"[短剧整理器] 返回剧名过长，拒绝: {result_title} ({len(result_title)} > {len(base_title)})")
                                medias = None
                        
                        if medias:
                            media_info = medias[0]
                            logger.info(f"[短剧整理器] ✅ 系统识别完整信息: {media_info}")
                            final_title = media_info.title
                            logger.info(f"[短剧整理器] ✅ 系统匹配: {final_title} ({media_info.year or '未知年份'})")
                            
                            tmdb_info["_source"] = media_info.media_source
                            # V3：媒体主身份统一为 media_source + media_id 成对，
                            # 无完整身份时宁可不写，避免半套主键污染下游缓存/数据库
                            identity_id = getattr(media_info, "media_id", None) or media_info.tmdb_id
                            if identity_id:
                                tmdb_info["media_source"] = media_info.media_source or "themoviedb"
                                tmdb_info["media_id"] = str(identity_id)
                            if media_info.tmdb_id:
                                # tmdbid 仅作为 NFO uniqueid 的辅助输出保留
                                tmdb_info["tmdbid"] = media_info.tmdb_id
                            if media_info.douban_id:
                                tmdb_info["doubanid"] = media_info.douban_id
                            if media_info.overview:
                                tmdb_info["overview"] = media_info.overview
                            if media_info.vote_average:
                                tmdb_info["rating"] = media_info.vote_average
                            if media_info.year:
                                tmdb_info["year"] = str(media_info.year)
                                if not drama_info.get("year"):
                                    drama_info["year"] = str(media_info.year)
                            if media_info.genres:
                                genre_names = [g.get("name") for g in media_info.genres if g.get("name")]
                                if genre_names:
                                    tmdb_info["genres"] = genre_names
                            if media_info.actors:
                                actors = [a.get('name') for a in media_info.actors if a.get('name')]
                                if actors:
                                    tmdb_info["actors"] = actors[:10]
                            poster_url = media_info.get_poster_image()
                            if poster_url:
                                tmdb_info["poster_url"] = poster_url
                            
                        else:
                            logger.warning(f"[短剧整理器] 系统搜索无结果: {search_title}")
                            
                    except Exception as e:
                        logger.warning(f"[短剧整理器] 系统搜索异常: {e}")
                        try:
                            ctx = MediaChain().recognize_by_path(file_path)
                            if ctx and ctx.media_info and ctx.media_info.title:
                                final_title = ctx.media_info.title
                                logger.info(f"[短剧整理器] ✅ 降级识别: {final_title}")
                                identity_id = getattr(ctx.media_info, "media_id", None) or ctx.media_info.tmdb_id
                                if identity_id:
                                    tmdb_info["media_source"] = ctx.media_info.media_source or "themoviedb"
                                    tmdb_info["media_id"] = str(identity_id)
                                if ctx.media_info.tmdb_id:
                                    tmdb_info["tmdbid"] = ctx.media_info.tmdb_id
                                poster_url = ctx.media_info.get_poster_image()
                                if poster_url:
                                    tmdb_info["poster_url"] = poster_url
                        except Exception as e2:
                            logger.warning(f"[短剧整理器] 降级识别也失败: {e2}")
                
                # 4️⃣ 本地 NFO 文件（次高优先级，覆盖系统识别）
                nfo_path = Path(file_path).parent / "tvshow.nfo"
                if nfo_path.exists():
                    try:
                        tree = parse(str(nfo_path))
                        root = tree.getroot()
                        nfo_title = root.findtext("title")
                        if nfo_title:
                            nfo_info["title"] = nfo_title
                            final_title = nfo_title
                            logger.info(f"[短剧整理器] ✅ NFO识别 -> title={final_title}")
                        
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
                            # NFO 的 uniqueid 属外部协议；顺带补齐 V3 主身份对
                            nfo_info["media_source"] = "themoviedb"
                            nfo_info["media_id"] = uniqueid.text
                        if root.findtext("rating"):
                            nfo_info["rating"] = root.findtext("rating")
                        logger.info(f"[短剧整理器] NFO信息: {list(nfo_info.keys())}")
                    except Exception as e:
                        logger.warning(f"[短剧整理器] 读取NFO失败: {e}")
                
                # 5️⃣ PT站点信息补全（补充元数据，但不覆盖已有剧名）
                if self._pt_fetcher and self._config.pt_enabled:
                    try:
                        pt_info = self._pt_fetcher.fetch(final_title, drama_info.get("year"))
                        if pt_info:
                            # 如果 PT 返回了更准确的剧名，且没有更高优先级的来源（NFO/TMDB）则使用
                            if pt_info.get("title") and not nfo_info and not tmdb_info:
                                final_title = pt_info["title"]
                                logger.info(f"[短剧整理器] ✅ PT识别 -> title={final_title}")
                            
                            # 合并非海报元数据（不覆盖已有字段）
                            for k, v in pt_info.items():
                                if v and k not in ("title", "poster_url", "poster_urls") and not drama_info.get(k):
                                    drama_info[k] = v
                            
                            # ---------- 海报 URL 收集与去重 ----------
                            poster_urls = []
                            
                            # 1. TMDB 海报（如果有）—— 放在最前，优先级最高
                            if tmdb_info.get("poster_url"):
                                poster_urls.append(tmdb_info["poster_url"])
                                drama_info["poster_url"] = tmdb_info["poster_url"]
                            
                            # 2. PT 单个海报
                            if pt_info.get("poster_url"):
                                poster_urls.append(pt_info["poster_url"])
                            
                            # 3. PT 海报列表（可能包含多个）
                            if pt_info.get("poster_urls"):
                                poster_urls.extend(pt_info["poster_urls"])
                            
                            # 去重（完全匹配）并保持添加顺序
                            if poster_urls:
                                drama_info["poster_urls"] = list(dict.fromkeys(poster_urls))
                                logger.debug(f"[短剧整理器] 海报URL已收集并去重，共{len(drama_info['poster_urls'])}个")
                            # -----------------------------------------
                            
                            logger.info(f"[短剧整理器] PT信息合并: {list(pt_info.keys())}")
                    except Exception as e:
                        logger.warning(f"[短剧整理器] PT信息补全异常: {e}")
                
                # 6️⃣ 合并 TMDB 和 NFO 元数据
                for info_dict in [tmdb_info, nfo_info]:
                    for k, v in info_dict.items():
                        if v and not drama_info.get(k):
                            drama_info[k] = v
                
                # ✅ 7️⃣ 最终剧名：清理季信息 + 持久化映射优先
                # 同一文件夹首次识别出的剧名会被固定下来，缓存过期或重启后继续沿用，
                # 避免同一部剧的分集因识别抖动（TMDB 匹配差异等）落进不同目录。
                mapped_title = self._title_mapping.get(folder_name)
                if mapped_title:
                    logger.info(f"[短剧整理器] 映射命中: {folder_name} -> {mapped_title}（沿用首次识别结果）")
                    final_title = mapped_title
                else:
                    logger.info(f"[短剧整理器] 🎯 最终剧名: {final_title} (来源: {self._get_title_source(nfo_info, tmdb_info, pt_info)})")
                
                # 剧名去掉季信息：目录名、tvshow.nfo、transferhistory 三处都用这个值
                cleaned_title = clean_season_title(final_title)
                if cleaned_title and cleaned_title != final_title:
                    logger.info(f"[短剧整理器] 剧名清理季信息: {final_title} -> {cleaned_title}")
                    final_title = cleaned_title
                drama_info["title"] = final_title
                
                # 8️⃣ 写入缓存
                cache_data = {
                    k: v for k, v in drama_info.items()
                    if k not in ("source_path", "file_name", "episode")
                }
                self._drama_cache[source_dir] = cache_data
                logger.info(f"[短剧整理器] 写入缓存 -> key={source_dir}")
                
                # 9️⃣ 记录持久化映射：文件夹名 -> 最终剧名（重启/缓存过期后仍生效）
                if folder_name and self._title_mapping.get(folder_name) != final_title:
                    self._title_mapping[folder_name] = final_title
                    logger.info(f"[短剧整理器] 保存映射: {folder_name} -> {final_title}")
                    self.save_data("title_mapping", self._title_mapping)
                
                # 首次识别需要生成NFO
                process_nfo = True
            if not self._organizer:
                return False

            result = self._organizer.organize(
                file_path,
                drama_info,
                process_nfo=process_nfo
            )

            if not result or not result.get("success"):
                logger.error(
                    f"[短剧整理器] 整理失败: {result.get('error') if result else '未知错误'}"
                )
                return False

            logger.info(f"[短剧整理器] 整理成功 -> 目标: {result.get('target_path')}")

            self._save_mapping(file_path, result, drama_info)

            self._notify_success(drama_info)

            return True
        
        except Exception as e:
            logger.error(f"[短剧整理器] 处理失败: {e}")
            return False
        
        finally:
            with self._lock:
                self._processing_files.pop(file_path, None)
    
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
    
    @staticmethod
    def _make_fileitem(path: Path) -> dict:
        """构造文件信息 JSON（与系统 transferhistory 格式一致）"""
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
    
    @staticmethod
    def _resolve_media_identity(drama_info: dict) -> Tuple[str, str]:
        """解析媒体主身份

        V3 把通用媒体主身份收敛为 media_source + media_id 这一对字段，两者必须
        同时有效（空串、"0"、半套身份都视为无身份），否则不写入。
        """
        source = drama_info.get("media_source")
        if hasattr(source, "value"):
            source = source.value
        source = str(source or "").strip()
        media_id = str(drama_info.get("media_id") or "").strip()
        if not source or not media_id or media_id == "0":
            return "", ""
        return source, media_id

    @staticmethod
    def _iter_transfer_history(**filters) -> List[Any]:
        """按 V3 只读查询合同分页读取整理历史

        宿主单页上限 200，这里翻完全部页，避免只处理到首屏。每页各自拥有
        独立事务（宿主 Oper 面向插件的兼容入口语义）。
        """
        from app.db.oper.transferhistory import TransferHistoryOper
        from app.schemas.query import QueryPageRequest, TransferHistoryFilter

        oper = TransferHistoryOper()
        condition = TransferHistoryFilter(**filters)
        page, count = 1, 200
        records: List[Any] = []
        while True:
            batch, total = oper.query(condition, QueryPageRequest(page=page, count=count))
            if not batch:
                break
            records.extend(batch)
            if page * count >= total:
                break
            page += 1
        return records

    def _clear_transfer_history(self, category: str) -> int:
        """按类别清空整理历史

        V3 的整理历史筛选合同没有 category 字段，因此分页取回后在本地按类别
        筛选，再逐条按 id 删除；删除只作用于无任务回执的历史记录。
        """
        from app.db.oper.transferhistory import TransferHistoryOper

        oper = TransferHistoryOper()
        targets = [
            record.id
            for record in self._iter_transfer_history()
            if (getattr(record, "category", "") or "") == category
        ]
        for record_id in targets:
            oper.delete(record_id)
        return len(targets)

    def _save_mapping(self, source_path: str, result: dict, drama_info: dict):
        """写入系统整理历史（V3 经宿主 TransferHistoryOper），同时更新 _task_cache"""
        try:
            key = str(Path(source_path).parent.name)
            
            try:
                seasons = f"S{int(drama_info.get('season', 1)):02d}"
                episodes = f"E{int(drama_info.get('episode', 1)):02d}"
                
                src_path = Path(source_path)
                dest_path = Path(result.get("target_path", ""))
                
                src_fileitem = self._make_fileitem(src_path)
                dest_fileitem = self._make_fileitem(dest_path)
                
                poster_path = Path(result.get("target_path", "")).parent.parent / "poster.jpg"
                poster_url = ""
                if poster_path.exists():
                    # 首次整理记录真实下载/复制的海报 URL；后续集数命中缓存时
                    # 复用首次解析好的海报 URL（TMDB 优先，其次 PT 站点）
                    poster_urls = drama_info.get("poster_urls") or []
                    poster_url = (
                        drama_info.get("_downloaded_poster")
                        or drama_info.get("poster_url")
                        or (poster_urls[0] if poster_urls else "")
                    )
                
                # V3：媒体主身份成对写入；拿不到完整身份时不写这两列
                media_source, media_id = self._resolve_media_identity(drama_info)

                payload = {
                    "src": source_path,
                    "src_storage": "local",
                    # JSON 列交给宿主 ORM 序列化，不要预先 json.dumps
                    "src_fileitem": src_fileitem,
                    "dest": result.get("target_path", ""),
                    "dest_storage": "local",
                    "dest_fileitem": dest_fileitem,
                    "mode": self._config.transfer_type or "link",
                    "type": self._config.media_type or "电视剧",
                    "category": self._config.category or "短剧",
                    "title": drama_info.get("title", "未知短剧"),
                    "year": drama_info.get("year") or "",
                    "seasons": seasons,
                    "episodes": episodes,
                    "image": poster_url,
                    "status": True,
                }
                if media_source and media_id:
                    payload["media_source"] = media_source
                    payload["media_id"] = media_id

                from app.db.oper.transferhistory import TransferHistoryOper
                TransferHistoryOper().add(**payload)
                logger.debug(
                    f"[短剧整理器] 已写入整理历史: {drama_info.get('title')} {seasons}{episodes}"
                    + (f" ({media_source}:{media_id})" if media_source else "")
                )
            except Exception as e:
                logger.error(f"[短剧整理器] 写入整理历史失败: {e}")
            
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
        """检查整理历史中是否已有相同 src 的记录"""
        try:
            from app.db.oper.transferhistory import TransferHistoryOper
            return TransferHistoryOper().get_by_src(src_path) is not None
        except Exception as e:
            logger.error(f"[短剧整理器] 查询整理历史失败: {e}")
            return False
    
    def _delete_transfer_history(self, src_path: str):
        """删除整理历史中指定 src 的记录

        宿主表的唯一约束是 (src, src_storage)，因此按 src 至多命中一条。
        """
        try:
            from app.db.oper.transferhistory import TransferHistoryOper
            oper = TransferHistoryOper()
            record = oper.get_by_src(src_path)
            if record is not None:
                oper.delete(record.id)
                logger.debug(f"[短剧整理器] 已删除旧整理记录: {src_path}")
        except Exception as e:
            logger.error(f"[短剧整理器] 删除整理历史失败: {e}")
    
    def _delete_transfer_by_title(self, title: str):
        """按“媒体库路径/子目录/标题/”目录边界匹配 dest 删除整理历史，独立于种子删除流程

        V3 的筛选合同只支持 dest 精确匹配，所以先用 text 字面包含缩小候选集，再在
        本地按目录边界比对，避免标题子串误伤（如“走火”匹配到“走火炮”）。
        """
        if not title:
            return
        try:
            from app.db.oper.transferhistory import TransferHistoryOper
            media_library = self._config.media_library
            if not media_library:
                media_library = getattr(settings, 'MEDIA_LIBRARY_PATH', '')
            subdir = self._config.subdir or "短剧"
            series_dir = title.strip()

            if media_library:
                boundary = os.path.join(str(media_library).rstrip('/\\'), subdir, series_dir)
            else:
                boundary = os.path.join(os.sep, subdir, series_dir)
            # 以目录整体作为边界（末尾带分隔符），避免标题子串误匹配
            boundary = os.path.normcase(os.path.normpath(boundary)) + os.sep

            oper = TransferHistoryOper()
            deleted = 0
            for record in self._iter_transfer_history(text=series_dir):
                dest = getattr(record, "dest", "") or ""
                if not dest:
                    continue
                if os.path.normcase(os.path.normpath(dest)).startswith(boundary):
                    oper.delete(record.id)
                    deleted += 1
            if deleted > 0:
                logger.info(f"[删除] 已按标题删除整理记录: {title}, {deleted}条")
            else:
                logger.debug(f"[删除] 未找到匹配的整理记录: {title}")
        except Exception as e:
            logger.error(f"[删除] 按标题删除整理记录失败: {title}: {e}")
    
    # ==================== 通知 ====================
    
    def _notify_success(self, drama_info: dict):
        """整理成功通知"""
        if not self._config or not self._config.notify_enabled:
            return
        title = drama_info.get("title", "未知短剧")
        season = drama_info.get("season", 1)
        episode = drama_info.get("episode", 1)
        self._send_notification(f"✅ {title} S{season:02d}E{episode:02d} 已入库")
    
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
        from app.sdk.utilities import StringUtils
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
            self._drama_cache.clear()
        self._save_cache()
        return "✅ 缓存已清空"
    
    def _force_scan(self) -> str:
        """立即执行一次全量扫描（忽略已有的整理记录）"""
        self._run_once("scan", lambda: self._scan_and_process(force_full=True))
        return "✅ 已启动全量扫描"
