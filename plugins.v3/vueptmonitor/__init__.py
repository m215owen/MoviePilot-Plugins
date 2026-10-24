import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from apscheduler.triggers.cron import CronTrigger
from bs4 import BeautifulSoup
from app.core.config import settings
from app.db.site_oper import SiteOper
from app.helper.browser import PlaywrightHelper
from app.helper.sites import SitesHelper
from app.log import logger
from app.plugins import _PluginBase
from app.scheduler import Scheduler
from app.schemas import NotificationType
from app.utils.http import RequestUtils


class VuePTMonitor(_PluginBase):
    # 插件名称
    plugin_name = "Vue-PT 监护台"
    # 插件描述
    plugin_desc = "展示 PT 站点运行状态、病危通知与站庆预告；探测各站点是否开放注册，支持把可添加站点写入 MP 站点管理并按状态联动启停。"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/m215owen/MoviePilot-Plugins/main/icons/VuePTMonitor.png"
    # 插件版本
    plugin_version = "1.3.0"
    # 插件作者
    plugin_author = "KoWming / m215owen"
    # 作者主页
    author_url = "https://github.com/KoWming"
    # 插件配置项ID前缀
    plugin_config_prefix = "vuept_"
    # 加载顺序
    plugin_order = 36
    # 可使用的用户级别
    auth_level = 2

    # 单页最大体积保护：超过该体积直接拒绝解析，防止异常页面把进程拖死
    _MAX_HTML_CHARS: int = 2 * 1024 * 1024
    # 解析耗时告警阈值（秒）
    _SLOW_PARSE_SECONDS: float = 3.0

    # 配置与缓存
    _enabled: bool = True
    _source_url: str = "https://savept.icu/"
    _request_timeout: int = 15
    _default_internal_only: bool = False
    _notify: bool = True
    _cron: str = "0 8 * * *"
    _use_proxy: bool = False
    _use_browser_emulation: bool = False
    # 新增：刷新时自动把「MP 可添加」站点写入站点管理
    _auto_add_available: bool = False
    # 新增：站点死亡时自动禁用 MP 中对应站点
    _sync_mp_active: bool = False
    # 新增：站点恢复健康时自动重新启用 MP 中对应站点
    _sync_mp_restore: bool = False
    # 新增：开放注册探测
    _signup_check: bool = True
    _signup_auto: bool = True
    _signup_cron: str = ""
    _signup_concurrency: int = 6
    # 自动探测的最小间隔（小时），避免频繁重复扫描站点
    _SIGNUP_AUTO_INTERVAL_HOURS: int = 6

    # ------------------------------------------------------------------
    # 开放注册探测常量
    # ------------------------------------------------------------------
    # 依次尝试的注册页路径（NexusPHP / Unit3D 等常见约定）
    _SIGNUP_PATHS: Tuple[str, ...] = ("/signup.php", "/register.php", "/register", "/signup")
    # 注册页请求头
    _SIGNUP_HEADERS: Dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    # 站点盾 / 无法确认（Cloudflare、备案阻断等）
    _SIGNUP_SHIELD_KW: Tuple[str, ...] = (
        "just a moment",
        "challenge-platform",
        "cf_chl_opt",
        "cf-browser-verification",
        "attention required",
        "enable javascript and cookies",
        "备案阻断",
        "access is prohibited",
        "access is forbidden",
    )
    # 明确不开放注册
    _SIGNUP_CLOSED_KW: Tuple[str, ...] = (
        "自由注册当前关闭",
        "自由註冊當前關閉",
        "关闭了自由注册",
        "关闭自由注册",
        "关闭注册",
        "關閉註冊",
        "注册已关闭",
        "註冊已關閉",
        "注册关闭",
        "停止注册",
        "暂停注册",
        "暫停註冊",
        "暂停售票",
        "不开放注册",
        "暂不支持公开注册",
        "封闭运行",
        "不对外开放",
        "站点关闭维护",
        "registration closed",
        "registration is closed",
        "signups are closed",
        "not open for registration",
        "closed for signup",
        "free registration not engaged",
        "current open registration limit",
    )
    # 需要邀请才能注册
    _SIGNUP_INVITE_KW: Tuple[str, ...] = (
        "只允许邀请注册",
        "只允許邀請註冊",
        "仅限邀请",
        "僅限邀請",
        "只接受邀请",
        "邀请注册",
        "邀請註冊",
        "邀请码",
        "邀請碼",
        "需要邀请",
        "邀请加入",
        "邀请机制",
        "通过邀请",
        "自助邀请",
        "邀请方式",
        "invite only",
        "invitation only",
        "by invitation",
        "invite code",
        "signup with invite",
    )
    # 探测状态展示文案
    _SIGNUP_STATUS_TEXT: Dict[str, str] = {
        "open": "开放注册",
        "invite": "仅限邀请",
        "closed": "未开放",
        "blocked": "访问受限",
        "unknown": "无法确认",
        "error": "探测失败",
    }

    # 当次探测的并发状态（进程内共享）；用可重入锁，避免同线程重入时自锁
    _signup_lock = threading.RLock()
    _signup_state: Dict[str, Any] = {
        "running": False,
        "done": 0,
        "total": 0,
        "started_at": "",
        "finished_at": "",
        "message": "",
    }
    # 探测结果缓存：domain -> 结果
    _signup_cache: Optional[Dict[str, Any]] = None

    # 缓存上一次抓取结果
    _last_snapshot: Dict[str, Any] = {}
    # 浏览器仿真实例缓存
    _playwright: Optional[PlaywrightHelper] = None

    # 从旧插件继承的配置键
    _LEGACY_CONFIG_KEYS: Tuple[str, ...] = (
        "enabled",
        "source_url",
        "request_timeout",
        "default_internal_only",
        "notify",
        "cron",
        "use_proxy",
        "use_browser_emulation",
    )
    # 旧插件标识（换 ID 前的类名）
    _LEGACY_PLUGIN_ID: str = "Savept"

    # MP 标准接口未暴露但实际支持的站点
    _HIDDEN_SITES: Dict[str, Dict[str, Any]] = {
        "exoticaz.to": {
            "id": "exoticaz",
            "name": "ExoticaZ",
            "url": "https://exoticaz.to/",
            "public": False,
        },
    }

    def __init__(self):
        super().__init__()
        self.siteoper = SiteOper()
        self.sites = SitesHelper()

    def init_plugin(self, config: dict = None) -> None:
        """初始化插件配置并设置默认值。"""
        config = config or {}
        if not config:
            config = self._inherit_legacy_config()
        self._apply_config(config)
        if self._use_browser_emulation:
            if not self._playwright:
                self._playwright = PlaywrightHelper()
        else:
            self._playwright = None

    def _inherit_legacy_config(self) -> Dict[str, Any]:
        """首次加载时，从旧插件（Savept）一次性继承配置与缓存快照。"""
        try:
            if self.get_data("legacy_inherited"):
                return {}
        except Exception:
            return {}
        inherited: Dict[str, Any] = {}
        try:
            legacy_config = self.get_config(plugin_id=self._LEGACY_PLUGIN_ID) or {}
            if isinstance(legacy_config, dict):
                for key in self._LEGACY_CONFIG_KEYS:
                    if key in legacy_config and legacy_config[key] not in (None, ""):
                        inherited[key] = legacy_config[key]
                if inherited:
                    logger.info(f"[{self.plugin_name}] 已从 {self._LEGACY_PLUGIN_ID} 继承配置: {sorted(inherited)}")
        except Exception as err:
            logger.warning(f"[{self.plugin_name}] 继承旧插件配置失败: {err}")
        try:
            if not self.get_data("last_snapshot"):
                legacy_snapshot = self.get_data("last_snapshot", plugin_id=self._LEGACY_PLUGIN_ID)
                if legacy_snapshot:
                    self.save_data("last_snapshot", legacy_snapshot)
                    self._last_snapshot = legacy_snapshot
                    logger.info(f"[{self.plugin_name}] 已继承 {self._LEGACY_PLUGIN_ID} 的站点快照缓存")
        except Exception as err:
            logger.warning(f"[{self.plugin_name}] 继承旧插件缓存失败: {err}")
        try:
            self.save_data("legacy_inherited", True)
        except Exception:
            pass
        return inherited

    def _apply_config(self, config: dict) -> None:
        """把配置字典应用到实例属性。"""
        self._enabled = self._to_bool(config.get("enabled", True))
        self._source_url = (config.get("source_url") or "https://savept.icu/").strip()
        self._request_timeout = max(int(config.get("request_timeout") or 15), 5)
        self._default_internal_only = bool(config.get("default_internal_only", False))
        self._notify = self._to_bool(config.get("notify", True))
        self._cron = (config.get("cron") or "0 8 * * *").strip()
        self._use_proxy = self._to_bool(config.get("use_proxy", False))
        self._use_browser_emulation = self._to_bool(config.get("use_browser_emulation", False))
        self._auto_add_available = self._to_bool(config.get("auto_add_available", False))
        self._sync_mp_active = self._to_bool(config.get("sync_mp_active", False))
        self._sync_mp_restore = self._to_bool(config.get("sync_mp_restore", False))
        self._signup_check = self._to_bool(config.get("signup_check", True))
        self._signup_auto = self._to_bool(config.get("signup_auto", True))
        self._signup_cron = (config.get("signup_cron") or "").strip()
        self._signup_concurrency = min(max(int(config.get("signup_concurrency") or 6), 1), 10)

    @staticmethod
    def _to_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def get_state(self) -> bool:
        """获取插件启用状态。"""
        return bool(self._enabled)

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """返回插件命令列表。"""
        return []

    def get_render_mode(self) -> Tuple[str, Optional[str]]:
        """返回渲染模式和前端资源目录。"""
        # 目录名同时充当缓存键：前端有实质改动就换新目录，避免浏览器复用旧的 remoteEntry
        return "vue", "dist/a1"

    def get_sidebar_nav(self) -> List[Dict[str, Any]]:
        """返回侧边栏导航配置。"""
        return [
            {
                "nav_key": "main",
                "title": "PT监护台",
                "icon": "mdi-heart-pulse",
                "section": "discovery",
                "order": 18,
            },
        ]

    def get_api(self) -> List[Dict[str, Any]]:
        """返回插件 API 路由定义。"""
        return [
            {
                "path": "/config",
                "endpoint": self._get_config,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取插件配置",
            },
            {
                "path": "/config",
                "endpoint": self._save_config,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "保存插件配置",
            },
            {
                "path": "/summary",
                "endpoint": self._get_summary,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取概览统计",
            },
            {
                "path": "/sites",
                "endpoint": self._get_sites,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取站点列表",
            },
            {
                "path": "/refresh",
                "endpoint": self._refresh_snapshot,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "刷新站点快照",
            },
            {
                "path": "/sites/add",
                "endpoint": self._add_available_sites,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "把 MP 可添加的站点写入站点管理",
            },
            {
                "path": "/sites/toggle",
                "endpoint": self._toggle_mp_site,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "启用或禁用 MP 站点",
            },
            {
                "path": "/signup/scan",
                "endpoint": self._start_signup_scan,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "探测站点是否开放注册",
            },
            {
                "path": "/signup/status",
                "endpoint": self._get_signup_status,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取注册探测进度与结果",
            },
        ]

    def get_form(self) -> Tuple[Optional[List[dict]], Dict[str, Any]]:
        """Vue 插件需要返回页面配置数据。"""
        return None, self._get_config()

    def get_page(self) -> List[dict]:
        """Vue 模式下返回页面路由列表。"""
        return []

    def get_service(self) -> List[Dict[str, Any]]:
        """注册定时公告推送服务。"""
        services: List[Dict[str, Any]] = []
        if self._enabled and self._notify and self._cron:
            try:
                services.append(
                    {
                        "id": self.__class__.__name__.lower(),
                        "name": f"{self.plugin_name} - 公告定时推送",
                        "trigger": CronTrigger.from_crontab(self._cron),
                        "func": self._cron_push_notice,
                        "kwargs": {},
                    }
                )
            except Exception:
                pass
        if self._enabled and self._signup_check and self._signup_cron:
            try:
                services.append(
                    {
                        "id": f"{self.__class__.__name__.lower()}_signup",
                        "name": f"{self.plugin_name} - 注册状态定时探测",
                        "trigger": CronTrigger.from_crontab(self._signup_cron),
                        "func": self._cron_scan_signup,
                        "kwargs": {},
                    }
                )
            except Exception:
                pass
        return services

    def stop_service(self) -> None:
        """插件卸载时的清理逻辑。"""
        try:
            Scheduler().remove_plugin_job(self.__class__.__name__.lower())
        except Exception:
            pass

    def _persist_config(self) -> None:
        """持久化当前配置到插件存储。"""
        self.update_config(self._get_config())

    def _get_config(self) -> Dict[str, Any]:
        """获取当前插件配置。"""
        return {
            "enabled": self._enabled,
            "source_url": self._source_url,
            "request_timeout": self._request_timeout,
            "default_internal_only": self._default_internal_only,
            "notify": self._notify,
            "cron": self._cron or "0 8 * * *",
            "use_proxy": self._use_proxy,
            "use_browser_emulation": self._use_browser_emulation,
            "auto_add_available": self._auto_add_available,
            "sync_mp_active": self._sync_mp_active,
            "sync_mp_restore": self._sync_mp_restore,
            "signup_check": self._signup_check,
            "signup_auto": self._signup_auto,
            "signup_cron": self._signup_cron,
            "signup_concurrency": self._signup_concurrency,
        }

    def _save_config(self, config_payload: dict) -> Dict[str, Any]:
        """保存配置并刷新当前插件状态。"""
        config_payload = config_payload or {}
        config_to_save = {
            "enabled": self._to_bool(config_payload.get("enabled", self._enabled)),
            "source_url": (config_payload.get("source_url") or self._source_url or "https://savept.icu/").strip(),
            "request_timeout": max(int(config_payload.get("request_timeout") or self._request_timeout or 15), 5),
            "default_internal_only": self._to_bool(config_payload.get("default_internal_only", self._default_internal_only)),
            "notify": self._to_bool(config_payload.get("notify", self._notify)),
            "cron": (config_payload.get("cron") or self._cron or "0 8 * * *").strip(),
            "use_proxy": self._to_bool(config_payload.get("use_proxy", self._use_proxy)),
            "use_browser_emulation": self._to_bool(config_payload.get("use_browser_emulation", self._use_browser_emulation)),
            "auto_add_available": self._to_bool(config_payload.get("auto_add_available", self._auto_add_available)),
            "sync_mp_active": self._to_bool(config_payload.get("sync_mp_active", self._sync_mp_active)),
            "sync_mp_restore": self._to_bool(config_payload.get("sync_mp_restore", self._sync_mp_restore)),
            "signup_check": self._to_bool(config_payload.get("signup_check", self._signup_check)),
            "signup_auto": self._to_bool(config_payload.get("signup_auto", self._signup_auto)),
            "signup_cron": (config_payload.get("signup_cron") or self._signup_cron or "").strip(),
            "signup_concurrency": min(
                max(int(config_payload.get("signup_concurrency") or self._signup_concurrency or 6), 1), 10
            ),
        }
        self.stop_service()
        self.init_plugin(config_to_save)
        self.update_config(config_to_save)
        return {"success": True, "message": "配置已保存", "data": self._get_config()}

    def _get_summary(self) -> Dict[str, Any]:
        """获取当前统计汇总数据。"""
        snapshot = self._with_signup(self._load_snapshot(force_refresh=False))
        return {"success": True, "data": snapshot.get("summary", {})}

    def _get_sites(self) -> Dict[str, Any]:
        """获取完整站点快照和公告数据。"""
        snapshot = self._with_signup(self._load_snapshot(force_refresh=False))
        return {"success": True, "data": snapshot}

    def _refresh_snapshot(self, payload: dict = None) -> Dict[str, Any]:
        """强制刷新一次实时快照。"""
        snapshot = self._load_snapshot(force_refresh=True)
        snapshot = self._with_signup(snapshot)
        return {"success": True, "message": "刷新成功", "data": snapshot}

    # ------------------------------------------------------------------
    # 与 MP 站点管理联动
    # ------------------------------------------------------------------
    def _add_available_sites(self, payload: dict = None) -> Dict[str, Any]:
        """把快照中「MP 可添加」的站点批量写入 MP 站点管理。"""
        payload = payload or {}
        wanted = {str(d).strip().lower() for d in (payload.get("domains") or []) if str(d).strip()}
        snapshot = self._load_snapshot(force_refresh=False)
        added: List[str] = []
        skipped: List[str] = []
        failed: List[str] = []
        for site in snapshot.get("sites") or []:
            if site.get("mp_status") != "available":
                continue
            domain = str(site.get("mp_site_domain") or site.get("domain") or "").strip().lower()
            if not domain:
                continue
            if wanted and domain not in wanted:
                continue
            name = site.get("mp_site_name") or site.get("name")
            url = site.get("mp_site_url") or site.get("url")
            if not name or not url:
                skipped.append(f"{domain}(缺少名称或地址)")
                continue
            try:
                if self.siteoper.exists(domain):
                    skipped.append(f"{domain}(已存在)")
                    continue
                ok, msg = self.siteoper.add(
                    name=name,
                    domain=domain,
                    url=url,
                    is_active=True,
                    public=bool(site.get("mp_public")) if site.get("mp_public") is not None else False,
                    pri=1,
                    timeout=self._request_timeout,
                )
                if ok:
                    added.append(domain)
                else:
                    skipped.append(f"{domain}({msg})")
            except Exception as err:
                failed.append(f"{domain}: {err}")
        if added:
            logger.info(f"[{self.plugin_name}] 已写入 MP 站点: {added}")
        return {
            "success": True,
            "message": f"新增 {len(added)} 个站点，跳过 {len(skipped)} 个，失败 {len(failed)} 个",
            "data": {"added": added, "skipped": skipped, "failed": failed},
        }

    def _toggle_mp_site(self, payload: dict = None) -> Dict[str, Any]:
        """启用或禁用 MP 站点（按域名）。"""
        payload = payload or {}
        domain = str(payload.get("domain") or "").strip().lower()
        active = self._to_bool(payload.get("active", True))
        if not domain:
            return {"success": False, "message": "缺少 domain 参数"}
        try:
            site = self.siteoper.get_by_domain(domain)
            if not site:
                return {"success": False, "message": f"MP 中未找到站点: {domain}"}
            self.siteoper.update(site.id, {"is_active": active})
            return {"success": True, "message": f"{domain} 已{'启用' if active else '禁用'}"}
        except Exception as err:
            return {"success": False, "message": f"操作失败: {err}"}

    def _apply_mp_sync(self, snapshot: Dict[str, Any]) -> None:
        """按配置执行站点写入与状态联动，异常一律隔离。"""
        if self._auto_add_available:
            try:
                result = self._add_available_sites({"domains": []})
                data = result.get("data") or {}
                if data.get("added"):
                    logger.info(f"[{self.plugin_name}] 自动添加站点完成: {data.get('added')}")
            except Exception as err:
                logger.error(f"[{self.plugin_name}] 自动添加站点失败: {err}")
        if self._sync_mp_active or self._sync_mp_restore:
            try:
                self._sync_mp_site_active(snapshot)
            except Exception as err:
                logger.error(f"[{self.plugin_name}] 站点状态联动失败: {err}")

    def _sync_mp_site_active(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """按监护状态联动 MP 站点启用状态（保守策略）。"""
        disabled: List[str] = []
        enabled: List[str] = []
        errors: List[str] = []
        try:
            records = {str(getattr(s, "domain", "") or "").lower(): s for s in (self.siteoper.list() or [])}
        except Exception as err:
            return {"disabled": [], "enabled": [], "errors": [f"读取站点列表失败: {err}"]}
        for site in snapshot.get("sites") or []:
            if site.get("mp_status") != "owned":
                continue
            domain = str(site.get("mp_site_domain") or site.get("domain") or "").strip().lower()
            record = records.get(domain)
            if not record:
                continue
            status = site.get("status")
            try:
                if self._sync_mp_active and status == "closed" and getattr(record, "is_active", True):
                    self.siteoper.update(record.id, {"is_active": False})
                    disabled.append(domain)
                elif self._sync_mp_restore and status == "healthy" and not getattr(record, "is_active", True):
                    self.siteoper.update(record.id, {"is_active": True})
                    enabled.append(domain)
            except Exception as err:
                errors.append(f"{domain}: {err}")
        if disabled or enabled:
            logger.info(f"[{self.plugin_name}] 站点联动 - 禁用: {disabled}, 启用: {enabled}")
        return {"disabled": disabled, "enabled": enabled, "errors": errors}

    # ------------------------------------------------------------------
    # 开放注册探测
    # ------------------------------------------------------------------
    def _signup_results(self) -> Dict[str, Any]:
        """读取注册探测结果缓存（内存优先，回落到插件存储）。"""
        if self._signup_cache is None:
            try:
                cached = self.get_data("signup_results") or {}
                self._signup_cache = cached if isinstance(cached, dict) else {}
            except Exception:
                self._signup_cache = {}
        return self._signup_cache

    def _signup_targets(self, snapshot: Dict[str, Any]) -> List[Dict[str, str]]:
        """从快照中挑出需要探测的站点（已关站的不再发起请求）。"""
        targets: List[Dict[str, str]] = []
        seen = set()
        for site in snapshot.get("sites") or []:
            domain = str(site.get("domain") or "").strip().lower()
            if not domain or domain in seen:
                continue
            seen.add(domain)
            if site.get("status") == "closed":
                continue
            targets.append({"domain": domain, "url": str(site.get("url") or "").strip()})
        return targets

    def _signup_proxies(self) -> Optional[Dict[str, str]]:
        """构造 requests 可用的代理设置。"""
        if not self._use_proxy:
            return None
        try:
            proxy = getattr(settings, "PROXY", None)
        except Exception:
            return None
        if not proxy:
            return None
        if isinstance(proxy, str):
            return {"http": proxy, "https": proxy}
        if isinstance(proxy, dict) and proxy:
            return proxy
        return None

    def _signup_get(self, url: str) -> Tuple[int, str, str]:
        """请求注册页，返回 (状态码, 最终地址, 页面源码)。"""
        try:
            requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]
        except Exception:
            pass
        response = requests.get(
            url,
            headers=self._SIGNUP_HEADERS,
            timeout=(5, self._request_timeout),
            allow_redirects=True,
            verify=False,
            proxies=self._signup_proxies(),
        )
        if not response.encoding or response.encoding.lower() in {"iso-8859-1", "ascii"}:
            response.encoding = response.apparent_encoding or "utf-8"
        html = response.text or ""
        if len(html) > self._MAX_HTML_CHARS:
            html = html[: self._MAX_HTML_CHARS]
        return response.status_code, response.url or url, html

    @staticmethod
    def _has_signup_form(low: str) -> bool:
        """判断页面是否为可填写的注册表单（需同时有密码框与注册提交地址）。"""
        if not any(token in low for token in ('type="password"', "type='password'", "type=password")):
            return False
        for match in re.finditer(r"<form[^>]{0,240}", low):
            segment = match.group(0)
            if "signup" in segment or "takesignup" in segment or "register" in segment:
                return True
        # NexusPHP 注册表单的字段名
        return "wantusername" in low or "wantpassword" in low

    def _classify_signup(self, html: str, code: int) -> Dict[str, Any]:
        """根据注册页内容判定注册状态。"""
        low = html.lower()
        text = html

        for keyword in self._SIGNUP_SHIELD_KW:
            if keyword in low:
                return {"status": "blocked", "reason": f"盾/访问限制（{keyword}）"}

        # 邀请类提示优先于「注册关闭」：「自由注册当前关闭，只允许邀请注册」对用户更有用的是「仅限邀请」
        for keyword in self._SIGNUP_INVITE_KW:
            if keyword in text or keyword in low:
                return {"status": "invite", "reason": f"页面提示「{keyword}」"}

        for keyword in self._SIGNUP_CLOSED_KW:
            if keyword in text or keyword in low:
                return {"status": "closed", "reason": f"页面提示「{keyword}」"}

        if self._has_signup_form(low):
            return {"status": "open", "reason": "存在可填写的注册表单"}

        if any(token in low for token in ('type="password"', "type='password'", "type=password")):
            return {"status": "unknown", "reason": "呈现登录页，无法确认注册状态"}

        if code in (401, 403):
            return {"status": "blocked", "reason": f"HTTP {code}"}
        if code >= 500:
            return {"status": "unknown", "reason": f"HTTP {code}"}
        return {"status": "unknown", "reason": "页面无可判定特征"}

    def _probe_signup(self, target: Dict[str, str]) -> Dict[str, Any]:
        """探测单个站点的开放注册状态。"""
        domain = target.get("domain") or ""
        checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        base = target.get("url") or ""
        if not base.startswith(("http://", "https://")):
            base = f"https://{domain}"
        base = base.rstrip("/")
        last_error = ""
        for path in self._SIGNUP_PATHS:
            url = f"{base}{path}"
            try:
                code, final_url, html = self._signup_get(url)
            except Exception as err:
                last_error = type(err).__name__
                continue
            if code == 404:
                last_error = "404"
                continue
            if len(html.strip()) < 40:
                last_error = "空页面"
                continue
            result = self._classify_signup(html, code)
            result.update(
                {
                    "domain": domain,
                    "url": url,
                    "final_url": final_url,
                    "checked_at": checked_at,
                }
            )
            return result
        if last_error == "404":
            return {
                "domain": domain,
                "status": "unknown",
                "reason": "未找到注册页（HTTP 404）",
                "url": f"{base}{self._SIGNUP_PATHS[0]}",
                "final_url": "",
                "checked_at": checked_at,
            }
        return {
            "domain": domain,
            "status": "error" if last_error else "unknown",
            "reason": f"请求失败（{last_error}）" if last_error else "未找到注册页",
            "url": f"{base}{self._SIGNUP_PATHS[0]}",
            "final_url": "",
            "checked_at": checked_at,
        }

    def _start_signup_scan(self, payload: dict = None) -> Dict[str, Any]:
        """启动一次后台注册探测（立即返回，不阻塞请求）。"""
        if not self._signup_check:
            return {"success": False, "message": "注册探测已在配置中关闭"}
        payload = payload or {}
        with self._signup_lock:
            if self._signup_state.get("running"):
                return {"success": True, "message": "探测已在进行中", "data": dict(self._signup_state)}
        # 注意：快照加载必须在锁外完成，否则会与「刷新后自动探测」的回调形成同线程重入死锁
        snapshot = self._load_snapshot(force_refresh=False)
        targets = self._signup_targets(snapshot)
        wanted = {str(item).strip().lower() for item in (payload.get("domains") or []) if str(item).strip()}
        if wanted:
            targets = [item for item in targets if item["domain"] in wanted]
        if not targets:
            return {"success": False, "message": "站点快照为空，请先刷新站点数据"}
        with self._signup_lock:
            if self._signup_state.get("running"):
                return {"success": True, "message": "探测已在进行中", "data": dict(self._signup_state)}
            self._signup_state.update(
                {
                    "running": True,
                    "done": 0,
                    "total": len(targets),
                    "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "finished_at": "",
                    "message": "探测中",
                }
            )
            thread = threading.Thread(
                target=self._run_signup_scan,
                args=(targets,),
                name="VuePTSignupScan",
                daemon=True,
            )
            thread.start()
        logger.info(f"[{self.plugin_name}] 开始探测 {len(targets)} 个站点的注册状态")
        return {"success": True, "message": f"已开始探测 {len(targets)} 个站点", "data": dict(self._signup_state)}

    def _run_signup_scan(self, targets: List[Dict[str, str]]) -> None:
        """后台探测主流程（线程池并发，分批落盘）。"""
        results: Dict[str, Any] = {}
        done = 0
        concurrency = min(max(self._signup_concurrency, 1), 10)
        try:
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = {executor.submit(self._probe_signup, target): target for target in targets}
                for future in as_completed(futures):
                    target = futures[future]
                    domain = target.get("domain") or ""
                    try:
                        results[domain] = future.result()
                    except Exception as err:
                        results[domain] = {
                            "domain": domain,
                            "status": "error",
                            "reason": f"{type(err).__name__}: {err}",
                            "url": "",
                            "final_url": "",
                            "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    done += 1
                    with self._signup_lock:
                        self._signup_state["done"] = done
                    if done % 20 == 0:
                        partial = {**self._signup_results(), **results}
                        self._signup_cache = partial
                        self._persist_signup(partial)
        except Exception as err:
            logger.error(f"[{self.plugin_name}] 注册探测异常: {err}")
        finally:
            merged = {**self._signup_results(), **results}
            self._signup_cache = merged
            self._persist_signup(merged)
            self._mark_signup_scanned()
            with self._signup_lock:
                opened = [domain for domain, item in results.items() if item.get("status") == "open"]
                self._signup_state.update(
                    {
                        "running": False,
                        "done": len(results),
                        "total": len(targets),
                        "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "message": f"完成，开放注册 {len(opened)} 个",
                    }
                )
            logger.info(f"[{self.plugin_name}] 注册探测完成：{len(results)} 个站点，开放注册 {len(opened)} 个")

    def _persist_signup(self, results: Dict[str, Any]) -> None:
        """把探测结果写入插件存储（失败不影响主流程）。"""
        try:
            self.save_data("signup_results", results)
        except Exception as err:
            logger.warning(f"[{self.plugin_name}] 注册探测结果保存失败: {err}")

    def _signup_scan_stale(self) -> bool:
        """判断上次探测是否已超过自动探测间隔。"""
        try:
            last = self.get_data("signup_scan_at") or ""
        except Exception:
            return True
        if not last:
            return True
        try:
            last_dt = datetime.strptime(str(last), "%Y-%m-%d %H:%M:%S")
        except Exception:
            return True
        return (datetime.now() - last_dt).total_seconds() >= self._SIGNUP_AUTO_INTERVAL_HOURS * 3600

    def _mark_signup_scanned(self) -> None:
        """记录本次探测完成时间。"""
        try:
            self.save_data("signup_scan_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        except Exception:
            pass

    def _get_signup_status(self) -> Dict[str, Any]:
        """返回探测进度与统计。"""
        results = self._signup_results()
        with self._signup_lock:
            state = dict(self._signup_state)
        stats = self._signup_stats(results)
        return {
            "success": True,
            "data": {
                "state": state,
                "stats": stats,
                "results": results,
                "status_text": self._SIGNUP_STATUS_TEXT,
            },
        }

    @staticmethod
    def _signup_stats(results: Dict[str, Any]) -> Dict[str, int]:
        """按状态汇总探测结果。"""
        stats = {key: 0 for key in ("open", "invite", "closed", "blocked", "unknown", "error")}
        for item in results.values():
            status = (item or {}).get("status")
            if status in stats:
                stats[status] += 1
        stats["total"] = len(results)
        return stats

    def _with_signup(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """把注册探测结果合并进快照（不污染已缓存的原始快照）。"""
        results = self._signup_results()
        merged_sites: List[Dict[str, Any]] = []
        open_count = 0
        for site in snapshot.get("sites") or []:
            item = dict(site)
            domain = str(item.get("domain") or "").strip().lower()
            signup = results.get(domain)
            if not signup and item.get("status") == "closed":
                signup = {
                    "status": "closed",
                    "reason": "站点已关站",
                    "checked_at": "",
                }
            if signup:
                signup_info = dict(signup)
                signup_info["text"] = self._SIGNUP_STATUS_TEXT.get(signup_info.get("status"), "未知")
                item["signup"] = signup_info
                if signup_info.get("status") == "open":
                    open_count += 1
            else:
                item["signup"] = None
            merged_sites.append(item)

        data = dict(snapshot)
        data["sites"] = merged_sites
        stats = self._signup_stats(results)
        summary = dict(snapshot.get("summary") or {})
        summary["signup_open"] = open_count
        summary["signup_scanned"] = stats["total"]
        data["summary"] = summary
        with self._signup_lock:
            data["signup_scan"] = dict(self._signup_state)
        data["signup_stats"] = stats
        return data

    def _cron_scan_signup(self) -> None:
        """定时触发注册探测。"""
        try:
            self._start_signup_scan({})
        except Exception as err:
            logger.error(f"[{self.plugin_name}] 定时注册探测失败: {err}")

    # ------------------------------------------------------------------
    # 通知
    # ------------------------------------------------------------------
    def _cron_push_notice(self) -> None:
        """按 Cron 定时抓取并推送公告。"""
        try:
            snapshot = self._load_snapshot(force_refresh=True)
            self._send_notice(snapshot)
        except Exception:
            pass

    def _send_notice(self, snapshot: Dict[str, Any]) -> None:
        """发送公告通知。"""
        if not self._notify:
            return

        title = "【🩺PT监护台】公告推送"
        text = self._build_notice_message(snapshot)
        try:
            self.post_message(
                mtype=NotificationType.Plugin,
                title=title,
                text=text,
            )
        except Exception:
            pass

    def _build_notice_message(self, snapshot: Dict[str, Any]) -> str:
        """格式化公告通知文本。"""
        alerts = snapshot.get("alerts") or []
        fetched_at = snapshot.get("fetched_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        grouped = {"critical": [], "success": [], "info": [], "error": []}
        for alert in alerts:
            level = alert.get("level")
            text = self._clean_text(alert.get("text"))
            if level in grouped and text:
                grouped[level].extend(self._split_notice_items(level, text))

        sections = [
            ("critical", "⚠️ 病危通知："),
            ("success", "✅ 恢复公告："),
            ("info", "🎉 站庆预告："),
            ("error", "🕯️ 死亡讣告："),
        ]

        lines: List[str] = []
        has_notice = False
        for key, title in sections:
            items = grouped.get(key) or []
            if not items:
                continue
            has_notice = True
            lines.append("━━━━━━━━━━━━━━")
            lines.append(title)
            for item in items:
                lines.append(f"• {item}")

        if not has_notice:
            lines.extend([
                "━━━━━━━━━━━━━━",
                "ℹ️ 暂无公告",
            ])

        lines.append("━━━━━━━━━━━━━━")
        lines.append(f"🕐 推送时间：{fetched_at}")
        return "\n".join(lines)

    def _split_notice_items(self, level: str, text: str) -> List[str]:
        """将公告正文拆分为逐条通知。"""
        text = self._clean_text(text).lstrip("• ").strip()
        if level == "critical":
            text = re.sub(r"^监测到站点异常，正在全力抢救中[：:]\s*", "", text)

        parts = re.split(r"\s*\|\s*", text)
        items: List[str] = []
        for part in parts:
            normalized = self._normalize_notice_item(level, part)
            if normalized:
                items.append(normalized)
        return items

    def _normalize_notice_item(self, level: str, text: Optional[str]) -> str:
        """规范单条公告的显示格式。"""
        item = self._clean_text(text).lstrip("• ").strip()
        if not item:
            return ""

        if level == "critical":
            item = re.sub(r"[，,]\s*濒临死亡$", "(濒临死亡)", item)
            item = re.sub(r"\s*\(\s*濒临死亡\s*\)$", "(濒临死亡)", item)
        elif level == "success":
            item = re.sub(r"[，,]\s*(于[^()]+恢复)$", r"(\1)", item)
            item = re.sub(r"\s*\(\s*(于[^()]+恢复)\s*\)$", r"(\1)", item)

        return item

    # ------------------------------------------------------------------
    # 快照加载与抓取
    # ------------------------------------------------------------------
    def _load_snapshot(self, force_refresh: bool = False) -> Dict[str, Any]:
        """加载缓存快照，必要时刷新或回退到兜底数据。"""
        if self._last_snapshot and not force_refresh:
            return self._last_snapshot
        try:
            snapshot = self._fetch_live_snapshot()
            if snapshot.get("sites"):
                self._last_snapshot = snapshot
                self.save_data("last_snapshot", snapshot)
                if self._auto_add_available or self._sync_mp_active or self._sync_mp_restore:
                    self._apply_mp_sync(snapshot)
                if self._signup_check and self._signup_auto and not self._signup_state.get("running"):
                    if self._signup_scan_stale():
                        try:
                            self._start_signup_scan({})
                        except Exception as err:
                            logger.warning(f"[{self.plugin_name}] 自动注册探测启动失败: {err}")
                return snapshot
        except Exception as err:
            cached = self.get_data("last_snapshot") or {}
            if cached:
                cached["warning"] = f"实时抓取失败，已回退缓存：{err}"
                self._last_snapshot = cached
                return cached
            empty_snapshot = {
                "source_url": self._source_url,
                "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "summary": {
                    "total": 0,
                    "healthy": 0,
                    "critical": 0,
                    "closed": 0,
                    "internal": 0,
                    "external": 0,
                    "today_anniv": 0,
                    "years": 0,
                },
                "alerts": [],
                "year_groups": [],
                "sites": [],
                "default_internal_only": self._default_internal_only,
                "warning": f"实时抓取失败，暂无缓存可用：{err}",
            }
            self._last_snapshot = empty_snapshot
            return empty_snapshot

    def _get_page_source(self, url: str) -> Optional[str]:
        """获取页面 HTML 源码，支持代理和浏览器仿真。"""
        proxies = self.__get_proxies()
        proxy_server = settings.PROXY_SERVER if self._use_proxy else None

        if self._use_browser_emulation:
            logger.info(f"[{self.plugin_name}] 使用 {settings.BROWSER_EMULATION} 浏览器仿真请求: {url}")
            if not self._playwright:
                self._playwright = PlaywrightHelper()
            return self._playwright.get_page_source(
                url=url,
                cookies=None,
                proxies=proxy_server,
                timeout=max(self._request_timeout, 60),
            )

        response = RequestUtils(proxies=proxies).get_res(url=url)
        if response and response.status_code == 200:
            return response.text

        status_code = response.status_code if response else "无响应"
        logger.error(f"[{self.plugin_name}] 普通请求失败: {url}, 状态码: {status_code}")
        return None

    def __get_proxies(self):
        """获取代理设置。"""
        if not self._use_proxy:
            logger.debug(f"[{self.plugin_name}] 未启用代理")
            return None

        try:
            if hasattr(settings, "PROXY") and settings.PROXY:
                logger.debug(f"[{self.plugin_name}] 使用系统代理: {settings.PROXY}")
                return settings.PROXY
            logger.debug(f"[{self.plugin_name}] 系统代理未配置")
            return None
        except Exception as err:
            logger.error(f"[{self.plugin_name}] 获取代理设置出错: {err}")
            return None

    def _fetch_live_snapshot(self) -> Dict[str, Any]:
        """从源站实时抓取页面并解析站点快照。"""
        html = self._get_page_source(self._source_url)
        if not html:
            raise requests.RequestException("获取页面源码失败")
        # 体积护栏：异常膨胀的页面直接拒绝解析，避免任何解析器在超大输入上失控
        if len(html) > self._MAX_HTML_CHARS:
            raise ValueError(
                f"页面体积异常（{len(html)} 字符 > {self._MAX_HTML_CHARS}），已拒绝解析以防卡死"
            )

        started = datetime.now()
        alert_texts = self._extract_notice_texts(html)
        year_groups = self._extract_year_groups(html)
        sites = self._annotate_sites_with_mp_status(self._extract_site_cards(html))
        summary = self._build_summary(sites, year_groups)
        cost = (datetime.now() - started).total_seconds()
        if cost > self._SLOW_PARSE_SECONDS:
            logger.warning(f"[{self.plugin_name}] 页面解析耗时 {cost:.2f}s（{len(html)} 字符，{len(sites)} 个站点）")

        return {
            "source_url": self._source_url,
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "summary": summary,
            "alerts": alert_texts,
            "year_groups": year_groups,
            "sites": sites,
            "default_internal_only": self._default_internal_only,
        }

    # ------------------------------------------------------------------
    # 解析（全部基于 BeautifulSoup，线性时间，杜绝正则回溯）
    # ------------------------------------------------------------------
    def _extract_notice_texts(self, html: str) -> List[Dict[str, str]]:
        """从页面中提取公告文本并返回标准化结果。"""
        soup = BeautifulSoup(html, "html.parser")
        notice_map = {
            "病危通知：": "critical",
            "恢复公告：": "success",
            "站庆预告：": "info",
            "死亡讣告：": "error",
        }
        results: List[Dict[str, str]] = []

        for strong in soup.find_all("strong"):
            title = self._clean_text(strong.get_text())
            level = notice_map.get(title)
            if not level:
                continue

            container = strong.parent
            if not container:
                continue

            text = self._clean_text(container.get_text(" ", strip=True))
            if text.startswith(title):
                text = self._clean_text(text[len(title):])

            if text:
                results.append({"level": level, "text": text})

        return results

    def _extract_year_groups(self, html: str) -> List[Dict[str, Any]]:
        """解析页面中的年份分组统计数据（BS4 优先，正则兜底且不回溯）。"""
        year_re = re.compile(r"^(\d{4}|未知)\s*年$")
        count_re = re.compile(r"\(?\s*(\d+)\s*个站点\s*\)?")
        groups: List[Dict[str, Any]] = []
        seen = set()

        def _add(year: str, count: int) -> None:
            key = (year, count)
            if key in seen:
                return
            seen.add(key)
            groups.append({"year": year, "count": count})

        try:
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup.find_all(["span", "div", "h3", "h4", "strong", "p", "b", "label"]):
                text = self._clean_text(tag.get_text(" ", strip=True))
                if not text or len(text) > 20:
                    continue
                year_match = year_re.match(text)
                if not year_match:
                    continue
                parent = tag.parent
                if not parent:
                    continue
                parent_text = self._clean_text(parent.get_text(" ", strip=True))
                count_match = count_re.search(parent_text)
                if count_match:
                    _add(year_match.group(1), int(count_match.group(1)))
        except Exception as err:
            logger.warning(f"[{self.plugin_name}] 年份分组解析异常: {err}")

        if not groups:
            # 兜底：用有界字符类替代 .*?，长度上限 200 字符，杜绝灾难性回溯
            for year, count in re.findall(r">\s*(\d{4}|未知)\s*年\s*<[^<]{0,200}?\(\s*(\d+)\s*个站点\)", html):
                try:
                    _add(year, int(count))
                except ValueError:
                    continue

        return groups

    def _extract_site_cards(self, html: str) -> List[Dict[str, Any]]:
        """解析站点卡片并返回结构化站点列表。

        历史问题：旧版使用一条 20 余段串联的超长正则解析整页 HTML，
        页面结构稍有变化即触发灾难性回溯，在 C 层长占 GIL 导致整个进程假死。
        此处改用 BeautifulSoup 做结构化提取，时间与页面大小近似线性。
        """
        cards: List[Dict[str, Any]] = []
        soup = BeautifulSoup(html, "html.parser")
        for anchor in soup.find_all("a", class_="card-link"):
            card = anchor.find("div", class_="card")
            status_strip = anchor.find("div", class_="status-strip")
            anniversary_badge = anchor.find("div", class_="anniversary-badge")
            duration_badge = anchor.find("div", class_="duration-badge")
            icon_img = anchor.find("img", class_="site-icon")
            title_div = anchor.find("div", class_="card-title")

            cards.append(
                {
                    "name": self._clean_text(title_div.get_text(" ", strip=True)) if title_div else "",
                    "url": anchor.get("href") or "",
                    "domain": self._extract_domain(anchor.get("href")),
                    "icon": (icon_img.get("src") if icon_img else "") or "",
                    "year": anchor.get("data-year") or "",
                    "status": self._normalize_status(
                        anchor.get("data-status"),
                        status_strip.get("title") if status_strip else "",
                    ),
                    "status_text": self._clean_text(status_strip.get("title")) if status_strip else "",
                    "site_type": "内站" if (anchor.get("data-type") or "") == "internal" else "外站",
                    "site_type_key": anchor.get("data-type") or "",
                    "anniversary_flag": anchor.get("data-anniversary") or "",
                    "anniversary_text": self._clean_text(anniversary_badge.get_text(" ", strip=True)) if anniversary_badge else "",
                    "duration_text": self._clean_text(duration_badge.get_text(" ", strip=True)) if duration_badge else "",
                    "open_time": (card.get("data-opentime") if card else "") or "",
                    "close_time": (card.get("data-closetime") if card else "") or "",
                    "search": self._clean_text(anchor.get("data-search")),
                }
            )
        return cards

    @staticmethod
    def _normalize_text(value: Any) -> str:
        if value is None:
            return ""
        return "".join(str(value).strip().lower().split())

    @classmethod
    def _normalize_site_name_candidates(cls, value: Any) -> List[str]:
        raw = cls._clean_text(value)
        if not raw:
            return []

        candidates: List[str] = []
        seen = set()

        def _add_candidate(text: str) -> None:
            normalized = cls._normalize_text(text)
            if normalized and normalized not in seen:
                seen.add(normalized)
                candidates.append(normalized)

        _add_candidate(raw)

        for separator in [" - ", " – ", " — ", " | ", " ｜ ", "/", "／"]:
            if separator in raw:
                parts = [part.strip() for part in raw.split(separator) if part.strip()]
                for part in parts:
                    _add_candidate(part)
                if parts:
                    _add_candidate(parts[0])

        # 有界字符类替代 .*?：括号内内容长度有限，避免任何回溯风险
        for stripped in re.split(r"[（(\[【][^）)\]】]*[）)\]】]", raw):
            _add_candidate(stripped)

        return candidates

    @staticmethod
    def _normalize_url(url: Any) -> str:
        if not url:
            return ""
        raw = str(url).strip()
        if not raw:
            return ""
        if not raw.startswith(("http://", "https://")):
            raw = f"https://{raw}"
        parsed = urlparse(raw)
        host = (parsed.netloc or parsed.path).lower().split(":")[0]
        path = parsed.path if parsed.netloc else ""
        path = path.rstrip("/")
        return f"{host}{path}".rstrip("/")

    @staticmethod
    def _strip_www(host: str) -> str:
        return host[4:] if host.startswith("www.") else host

    @classmethod
    def _extract_domain(cls, url: Any) -> str:
        if not url:
            return ""
        raw = str(url).strip()
        if not raw:
            return ""
        if not raw.startswith(("http://", "https://")):
            raw = f"https://{raw}"
        parsed = urlparse(raw)
        return (parsed.netloc or parsed.path).lower().split(":")[0]

    def _build_standard_indexes(self) -> Dict[str, Any]:
        raw_sites = {**self._HIDDEN_SITES, **(self.sites.get_indexsites() or {})}
        url_index: Dict[str, Dict[str, Any]] = {}
        name_index: Dict[str, List[Dict[str, Any]]] = {}
        domain_index: Dict[str, List[Dict[str, Any]]] = {}
        site_groups: Dict[str, Dict[str, Any]] = {}

        for domain, site in raw_sites.items():
            site_domain = str(domain or "").lower()
            site_name = site.get("name") or domain
            site_url = site.get("url") or f"https://{domain}"
            site_id = site.get("id")
            group_key = str(site_id or self._normalize_text(site_name) or site_domain)

            standard_site = site_groups.get(group_key)
            if not standard_site:
                standard_site = {
                    "domain": site_domain,
                    "id": site_id,
                    "name": site_name,
                    "url": site_url,
                    "public": site.get("public"),
                    "alias_domains": set(),
                    "alias_urls": set(),
                    "alias_names": set(),
                }
                site_groups[group_key] = standard_site

            standard_site["alias_domains"].add(site_domain)
            extracted_domain = self._extract_domain(site_url)
            if extracted_domain:
                standard_site["alias_domains"].add(extracted_domain)

            normalized_url = self._normalize_url(site_url)
            if normalized_url:
                standard_site["alias_urls"].add(normalized_url)

            for normalized_name in self._normalize_site_name_candidates(site_name):
                standard_site["alias_names"].add(normalized_name)

        for standard_site in site_groups.values():
            for normalized_url in standard_site["alias_urls"]:
                url_index[normalized_url] = standard_site
            for normalized_name in standard_site["alias_names"]:
                name_index.setdefault(normalized_name, []).append(standard_site)
            for alias_domain in standard_site["alias_domains"]:
                domain_index.setdefault(alias_domain, []).append(standard_site)

        return {
            "url_index": url_index,
            "name_index": name_index,
            "domain_index": domain_index,
        }

    def _build_existing_domain_set(self) -> set:
        domains = set()
        try:
            for site in self.siteoper.list() or []:
                domain = getattr(site, "domain", None)
                if domain:
                    domains.add(str(domain).lower())
                    domains.add(self._strip_www(str(domain).lower()))
        except Exception as err:
            logger.error(f"[{self.plugin_name}] 获取 MP 已有站点失败: {err}")
        return domains

    @staticmethod
    def _pick_unique_standard_site(candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not candidates:
            return None
        unique_sites: Dict[str, Dict[str, Any]] = {}
        for candidate in candidates:
            key = str(
                candidate.get("id")
                or candidate.get("domain")
                or candidate.get("url")
                or candidate.get("name")
                or ""
            )
            if key and key not in unique_sites:
                unique_sites[key] = candidate
        return next(iter(unique_sites.values())) if len(unique_sites) == 1 else None

    def _match_mp_site(self, site: Dict[str, Any], standard_indexes: Dict[str, Any], existing_domains: set) -> Dict[str, Any]:
        normalized_url = self._normalize_url(site.get("url"))
        normalized_names = self._normalize_site_name_candidates(site.get("name"))
        domain = (site.get("domain") or "").lower()
        normalized_url_nowww = self._strip_www(normalized_url) if normalized_url else ""
        domain_nowww = self._strip_www(domain) if domain else ""

        matched_standard = None
        match_type = "unmatched"

        if normalized_url and standard_indexes["url_index"].get(normalized_url):
            matched_standard = standard_indexes["url_index"][normalized_url]
            match_type = "url"
        elif normalized_url_nowww and normalized_url_nowww != normalized_url and standard_indexes["url_index"].get(normalized_url_nowww):
            matched_standard = standard_indexes["url_index"][normalized_url_nowww]
            match_type = "url"
        elif domain and standard_indexes["domain_index"].get(domain):
            candidates = standard_indexes["domain_index"][domain]
            unique_candidate = self._pick_unique_standard_site(candidates)
            if unique_candidate:
                matched_standard = unique_candidate
                match_type = "domain"
        elif domain_nowww and domain_nowww != domain and standard_indexes["domain_index"].get(domain_nowww):
            candidates = standard_indexes["domain_index"][domain_nowww]
            unique_candidate = self._pick_unique_standard_site(candidates)
            if unique_candidate:
                matched_standard = unique_candidate
                match_type = "domain"
        else:
            for normalized_name in normalized_names:
                if not normalized_name or not standard_indexes["name_index"].get(normalized_name):
                    continue
                candidates = standard_indexes["name_index"][normalized_name]
                unique_candidate = self._pick_unique_standard_site(candidates)
                if unique_candidate:
                    matched_standard = unique_candidate
                    match_type = "name"
                    break

            if not matched_standard and normalized_names:
                fuzzy_candidates: List[Dict[str, Any]] = []
                for standard_site in standard_indexes["url_index"].values():
                    alias_names = standard_site.get("alias_names") or set()
                    for normalized_name in normalized_names:
                        if not normalized_name:
                            continue
                        if any(
                            normalized_name == alias_name
                            or normalized_name in alias_name
                            or alias_name in normalized_name
                            for alias_name in alias_names
                        ):
                            fuzzy_candidates.append(standard_site)
                            break
                unique_candidate = self._pick_unique_standard_site(fuzzy_candidates)
                if unique_candidate:
                    matched_standard = unique_candidate
                    match_type = "name_fuzzy"

        if not matched_standard:
            return {
                **site,
                "mp_supported": False,
                "mp_exists": False,
                "mp_status": "unsupported",
                "mp_status_text": "MP未收录",
                "mp_match_type": match_type,
                "mp_site_id": "",
                "mp_site_name": "",
                "mp_site_domain": "",
                "mp_site_url": "",
                "mp_public": None,
            }

        target_domain = (matched_standard.get("domain") or self._extract_domain(matched_standard.get("url"))).lower()
        alias_domains = matched_standard.get("alias_domains") or set()
        already_exists = False
        for alias_domain in alias_domains:
            alias_domain = str(alias_domain or "").lower()
            alias_domain_nowww = self._strip_www(alias_domain) if alias_domain else ""
            if (alias_domain and alias_domain in existing_domains) or (alias_domain_nowww and alias_domain_nowww in existing_domains):
                already_exists = True
                break

        return {
            **site,
            "mp_supported": True,
            "mp_exists": already_exists,
            "mp_status": "owned" if already_exists else "available",
            "mp_status_text": "MP已拥有" if already_exists else "MP可添加",
            "mp_match_type": match_type,
            "mp_site_id": matched_standard.get("id") or "",
            "mp_site_name": matched_standard.get("name") or "",
            "mp_site_domain": target_domain,
            "mp_site_url": matched_standard.get("url") or "",
            "mp_public": matched_standard.get("public"),
        }

    def _annotate_sites_with_mp_status(self, sites: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        standard_indexes = self._build_standard_indexes()
        existing_domains = self._build_existing_domain_set()
        return [self._match_mp_site(site, standard_indexes, existing_domains) for site in sites]

    def _build_summary(self, sites: List[Dict[str, Any]], year_groups: List[Dict[str, Any]]) -> Dict[str, Any]:
        """构建站点统计汇总数据。"""
        total = len(sites)
        healthy = len([item for item in sites if item.get("status") == "healthy"])
        critical = len([item for item in sites if item.get("status") == "critical"])
        closed = len([item for item in sites if item.get("status") == "closed"])
        internal = len([item for item in sites if item.get("site_type_key") == "internal"])
        external = len([item for item in sites if item.get("site_type_key") != "internal"])
        today_anniv = len([
            item for item in sites
            if item.get("status") != "closed" and self._is_today_anniversary(item.get("anniversary_text"))
        ])
        mp_owned = len([item for item in sites if item.get("mp_status") == "owned"])
        mp_available = len([item for item in sites if item.get("mp_status") == "available"])
        mp_unsupported = len([item for item in sites if item.get("mp_status") == "unsupported"])
        return {
            "total": total,
            "healthy": healthy,
            "critical": critical,
            "closed": closed,
            "internal": internal,
            "external": external,
            "today_anniv": today_anniv,
            "years": len(year_groups),
            "mp_owned": mp_owned,
            "mp_available": mp_available,
            "mp_unsupported": mp_unsupported,
        }

    @staticmethod
    def _is_today_anniversary(value: Optional[str]) -> bool:
        text = VuePTMonitor._clean_text(value)
        return "0天" in text or "今天" in text

    @staticmethod
    def _clean_text(value: Optional[str]) -> str:
        if not value:
            return ""
        return re.sub(r"\s+", " ", str(value)).strip()

    @staticmethod
    def _normalize_status(status_key: Optional[str], status_text: Optional[str]) -> str:
        """标准化页面状态为内部状态码。"""
        status_key = (status_key or "").lower()
        status_text = (status_text or "").strip()
        if status_key == "online" or "运行" in status_text or "健康" in status_text:
            return "healthy"
        if status_key in {"down", "critical"} or "病危" in status_text or "抢救" in status_text:
            return "critical"
        if status_key in {"closed", "offline"} or "已关站" in status_text or "死亡" in status_text:
            return "closed"
        return "unknown"
