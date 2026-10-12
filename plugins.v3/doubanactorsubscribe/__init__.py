"""
豆瓣演员订阅（MoviePilot V3 插件后端）。

功能：按配置的演员（豆瓣人物名或人物 ID）抓取其「影视作品集」，把最新作品
展示在插件详情页 / 仪表板 / 侧栏全页，面板上提供「一键订阅」把作品提交给
MoviePilot 的订阅系统；可选开启自动订阅，把新出现且满足筛选条件的作品入库。

实现要点（V3 契约）：
1. 豆瓣接口在插件内自持（Frodo API + HMAC-SHA1 签名），只依赖 ``app.sdk.network``
   的 HTTP 工具，不碰宿主内部目录，避免宿主结构变化导致插件加载失败。
2. 自动订阅走官方稳定入口 ``app.chain.subscribe.SubscribeChain``（官方 V3 插件
   doubanrank / bangumicoll 等均如此）；前端面板的「订阅」按钮则直接调用宿主
   ``POST /api/v1/subscribe/``，使订阅归属到当前登录用户。
3. 配置与数据一律走基类方法（``get_data`` / ``save_data`` / ``update_config``），
   并且全部以 ``self.__class__.__name__`` 推导 ID，兼容插件虚拟分身。
4. 不在模块导入期做网络 / 数据库 / 任务启动。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time
from datetime import datetime
from random import choice
from typing import Any, Dict, List, Optional, Tuple
from urllib import parse

from apscheduler.triggers.cron import CronTrigger

from app.chain.subscribe import SubscribeChain
from app.schemas.types import EventType, MediaSource, MediaType
from app.sdk.config import settings
from app.sdk.events import Event, eventmanager
from app.sdk.logging import logger
from app.sdk.media import MetaInfo
from app.sdk.network import RequestUtils
from app.sdk.plugin import _PluginBase

# 消息类型枚举在宿主版本间存在改名：V3.1+ 使用 MessageType，更早的实现使用 NotificationType。
# 这里做一次兼容性导入，避免因宿主版本差异导致插件整体加载失败。
try:  # pragma: no cover - 取决于宿主版本
    from app.schemas.types import MessageType as _MessageType
except ImportError:  # pragma: no cover
    from app.schemas.types import NotificationType as _MessageType  # type: ignore

from .agenttool import DoubanActorWorksTool

# 插件展示名，同时作为自动订阅的归属用户名
PLUGIN_NAME = "豆瓣演员订阅"

# 豆瓣作品类型 → MoviePilot 媒体类型
_TYPE_ALIASES: Dict[str, str] = {
    "movie": MediaType.MOVIE.value,
    "电影": MediaType.MOVIE.value,
    "tv": MediaType.TV.value,
    "series": MediaType.TV.value,
    "电视剧": MediaType.TV.value,
}

# 允许参与自动订阅的媒体类型
_SUBSCRIBABLE_TYPES = (MediaType.MOVIE.value, MediaType.TV.value)

# 豆瓣部分标题会夹带零宽/双向控制字符（实测「神探之痕迹\u200e」），
# 这类字符不可见却会污染订阅名与去重比对，统一剔除。
_INVISIBLE_CHARS = dict.fromkeys(
    [0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2060, 0xFEFF]
)


def _clean_text(value: Any) -> str:
    """去掉首尾空白与零宽/双向控制字符。"""
    return str(value or "").translate(_INVISIBLE_CHARS).strip()


class _DoubanClient:
    """豆瓣 Frodo API 的轻量客户端（插件内自持，不依赖宿主内部模块）。

    仅使用 ``app.sdk.network.RequestUtils`` 发请求，签名规则与豆瓣移动端一致：
    ``_sig = base64(hmac_sha1(secret, "GET&" + quote(path) + "&" + _ts))``。

    注意：``path`` 必须是**完整请求路径**，即包含 ``/api/v2`` 前缀。
    豆瓣服务端按全路径校验签名，漏掉前缀会直接返回 400 Bad Request
    （宿主 ``app.modules.douban.apiv2`` 也是用 ``urlparse(full_url).path`` 取全路径再签名）。
    """

    BASE_URL = "https://frodo.douban.com/api/v2"
    # 签名覆盖的路径前缀，必须与 BASE_URL 的路径部分一致
    SIGN_BASE_PATH = "/api/v2"
    API_KEY = "0dad551ec0f84ed02907ff5c42e8ec70"
    API_SECRET = "bf7dddc7c9cfe6f7"
    TIMEOUT = 15
    # 作品集接口单次返回条数上限。实测请求 20/50 同样只回 10 条，
    # 且任何 start > 0 都会得到 {"total": 0, "works": []}，即**不支持翻页**，
    # 因此每位演员实际只能取到最近 10 部作品（插件侧的 max_works 也就封顶为 10）。
    MAX_WORKS_PER_REQUEST = 10
    # 该接口仅 time / collection 有效；vote 会返回空列表，故做白名单兜底
    SORT_ORDERS = ("time", "collection")
    USER_AGENTS = (
        "api-client/1 com.douban.frodo/7.22.0.beta9(231) Android/23 product/Mate 40 "
        "vendor/HUAWEI model/Mate 40 brand/HUAWEI  rom/android  network/wifi  platform/AndroidPad",
        "api-client/1 com.douban.frodo/7.18.0(230) Android/22 product/MI 9 vendor/Xiaomi "
        "model/MI 9 brand/Android  rom/miui6  network/wifi  platform/mobile nd/1",
    )

    def __init__(self, proxy: bool = False) -> None:
        self._proxy = proxy

    @classmethod
    def _sign(cls, url_path: str, ts: str) -> str:
        """按豆瓣移动端规则生成 ``_sig``。

        :param url_path: 完整请求路径（含 ``/api/v2`` 前缀）
        :param ts: ``YYYYMMDD`` 形式的时间戳
        """
        path = url_path if url_path.startswith(cls.SIGN_BASE_PATH) else f"{cls.SIGN_BASE_PATH}{url_path}"
        raw = "&".join(["GET", parse.quote(path, safe=""), ts])
        digest = hmac.new(cls.API_SECRET.encode(), raw.encode(), hashlib.sha1).digest()
        return base64.b64encode(digest).decode()

    def _get(self, url_path: str, **kwargs: Any) -> Optional[Dict[str, Any]]:
        """发起一次签名 GET 请求；失败时记录日志并返回 None。"""
        ts = datetime.now().strftime("%Y%m%d")
        params: Dict[str, Any] = dict(kwargs)
        params.update(
            {
                "os_rom": "android",
                "apiKey": self.API_KEY,
                "_ts": ts,
                "_sig": self._sign(url_path, ts),
            }
        )
        proxies = getattr(settings, "PROXY", None) if self._proxy else None
        response = None
        try:
            response = RequestUtils(
                ua=choice(self.USER_AGENTS), proxies=proxies, timeout=self.TIMEOUT
            ).get_res(url=f"{self.BASE_URL}{url_path}", params=params)
            if response is None:
                logger.error(f"{PLUGIN_NAME} 豆瓣请求无响应：{url_path}")
                return None
            if response.status_code != 200:
                logger.warning(f"{PLUGIN_NAME} 豆瓣接口返回 {response.status_code}：{url_path}")
                return None
            payload = response.json()
            return payload if isinstance(payload, dict) else None
        except Exception as err:
            logger.error(f"{PLUGIN_NAME} 请求豆瓣接口失败（{url_path}）：{err}")
            return None
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:  # pragma: no cover - 关闭失败可忽略
                    pass

    def search_person(self, name: str, count: int = 10) -> List[Dict[str, Any]]:
        """按名称搜索豆瓣人物，返回 ``[{id, name, avatar, url}]``。"""
        payload = self._get("/search/subjects", type="person", q=name, start=0, count=count)
        results: List[Dict[str, Any]] = []
        seen = set()
        for item in (payload or {}).get("items") or []:
            if not isinstance(item, dict):
                continue
            target = item.get("target") if isinstance(item.get("target"), dict) else {}
            person_id = str(item.get("target_id") or target.get("id") or "").strip()
            title = _clean_text(target.get("title"))
            if not person_id.isdigit() or not title or person_id in seen:
                continue
            seen.add(person_id)
            cover = target.get("cover_img") if isinstance(target.get("cover_img"), dict) else {}
            results.append(
                {
                    "id": person_id,
                    "name": title,
                    "avatar": str(cover.get("url") or "").replace("/l/public/", "/s/public/") or None,
                    "url": target.get("url"),
                }
            )
        return results

    def person_detail(self, person_id: str) -> Optional[Dict[str, Any]]:
        """获取豆瓣人物详情（含作品集 modules）。"""
        if not person_id:
            return None
        return self._get(f"/elessar/subject/{person_id}")

    def person_works(
        self, collection_id: str, start: int = 0, count: int = 20, sort_by: str = "time"
    ) -> List[Dict[str, Any]]:
        """获取人物「影视」作品集。

        受豆瓣接口限制：单次最多 10 条，且 ``start > 0`` 一律返回空结果，
        因此这里只取首页（``start`` 参数保留是为了签名外的调用兼容，实际不生效）。
        ``sort_by`` 仅 time / collection 有效，其余取值回退为 time。
        """
        if not collection_id:
            return []
        order = sort_by if sort_by in self.SORT_ORDERS else "time"
        limit = min(max(1, int(count or self.MAX_WORKS_PER_REQUEST)), self.MAX_WORKS_PER_REQUEST)
        payload = self._get(
            f"/elessar/work_collections/{collection_id}/works",
            sortby=order,
            collection_title="影视",
            start=0,
            count=limit,
        )
        return [item for item in (payload or {}).get("works") or [] if isinstance(item, dict)]


class DoubanActorSubscribe(_PluginBase):
    """订阅豆瓣演员，抓取最新作品并一键提交到 MoviePilot 订阅系统。"""

    # ─── 插件元数据（需与 package.v3.json 保持一致） ──────────────────
    # 注意：这里必须是字符串字面量，不能用 PLUGIN_NAME 常量。
    # 部分离线安装工具（如 LocalPluginInstall）会用 AST 静态解析插件类，
    # 只认 ast.Constant 形式的字符串属性，引用变量会被判定为“缺少 plugin_name”。
    # 与 PLUGIN_NAME 的一致性由 scripts/verify_plugin.py 自动校验。
    plugin_name = "豆瓣演员订阅"
    plugin_desc = (
        "订阅豆瓣演员，自动抓取其最新影视作品并展示在面板中，"
        "支持一键提交到 MoviePilot 订阅系统，也可按评分/类型阈值自动订阅新作品。"
    )
    plugin_icon = (
        "https://raw.githubusercontent.com/m215owen/MoviePilot-Plugins/main/"
        "icons/DoubanActorSubscribe.png"
    )
    plugin_version = "1.0.0"
    plugin_author = "m215owen"
    author_url = "https://github.com/m215owen"
    plugin_label = "订阅"
    # 配置项前缀：由宿主按运行实例保证唯一
    plugin_config_prefix = "doubanactorsubscribe_"
    plugin_order = 40
    auth_level = 1

    # ─── 运行时状态（统一由 init_plugin 重建，保证可重复初始化） ──────
    _enabled: bool = False
    _cron: str = "0 8 * * *"
    _actor_entries: List[str] = []
    _max_works: int = 10
    _sort_by: str = "time"
    _proxy: bool = False
    _notify: bool = False
    _auto_subscribe: bool = False
    _auto_only_new: bool = True
    _auto_min_vote: float = 0.0
    _auto_types: List[str] = list(_SUBSCRIBABLE_TYPES)
    _auto_max_per_run: int = 5
    _run_count: int = 0
    _last_run_at: str = ""

    # 插件数据表中的键名
    _DATA_ACTORS = "actors"
    _DATA_WORKS = "works"
    _DATA_SEEN = "auto_seen"
    _DATA_SUBS = "auto_subscribed"
    _DATA_STATE = "state"

    # 一次性任务标识
    _ONCE_JOB_ID = "refresh_once"

    # ─── 生命周期 ────────────────────────────────────────────────

    def init_plugin(self, config: dict | None = None) -> None:
        """读取配置并重建运行状态；宿主在启动与保存配置时都会调用，必须可重复执行。"""
        # 先释放上一轮运行可能遗留的资源
        self.stop_service()

        cfg: Dict[str, Any] = dict(config or {})
        self._enabled = bool(cfg.get("enabled"))
        self._cron = str(cfg.get("cron") or "0 8 * * *").strip()
        self._actor_entries = self._parse_actors(cfg.get("actors"))
        # 上限 10：豆瓣作品集接口不支持翻页，取再多也拿不到
        self._max_works = self._clamp_int(cfg.get("max_works"), 10, 5, 10)
        self._sort_by = str(cfg.get("sort_by") or "time").strip() or "time"
        self._proxy = bool(cfg.get("proxy"))
        self._notify = bool(cfg.get("notify"))
        self._auto_subscribe = bool(cfg.get("auto_subscribe"))
        self._auto_only_new = bool(cfg.get("auto_only_new", True))
        self._auto_min_vote = self._to_float(cfg.get("auto_min_vote"), 0.0)
        self._auto_types = self._parse_types(cfg.get("auto_types"))
        self._auto_max_per_run = self._clamp_int(cfg.get("auto_max_per_run"), 5, 1, 100)

        state = self.get_data(self._DATA_STATE)
        if isinstance(state, dict):
            self._run_count = self._clamp_int(state.get("run_count"), 0, 0, 10 ** 9)
            self._last_run_at = str(state.get("last_run_at") or "")

        # 把当前运行实例注入智能体工具，避免工具依赖进程级单例查找
        DoubanActorWorksTool.bind(self)

        # 勾选“启用后立即执行一次”时交给宿主调度器延迟执行，而不是自建线程
        if self._enabled and cfg.get("onlyonce"):
            if self._add_once_job():
                cfg["onlyonce"] = False
                self.update_config(cfg)

        logger.info(
            f"{self.plugin_name} 初始化完成：enabled={self._enabled}，"
            f"演员 {len(self._actor_entries)} 位，cron={self._cron}"
        )

    def get_state(self) -> bool:
        """返回插件当前是否启用。"""
        return self._enabled

    def stop_service(self) -> None:
        """停用或卸载插件时释放后台资源；需保证可重复、安全地调用。"""
        self._enabled = False
        try:
            from app.sdk import scheduler as scheduler_sdk  # 延迟导入，避免版本差异影响加载

            remove_job = getattr(scheduler_sdk, "remove_plugin_once_job", None)
            if remove_job:
                remove_job(self.__class__.__name__, self._ONCE_JOB_ID)
        except Exception as err:  # pragma: no cover - 宿主版本差异兜底
            logger.debug(f"{self.plugin_name} 清理一次性任务时跳过：{err}")

    # ─── 页面与渲染模式 ──────────────────────────────────────────

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        """声明使用 Vue 联邦远程组件渲染，产物目录为 dist/assets。"""
        return "vue", "dist/assets"

    def get_form(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Vue 模式下配置页由远程 Config 组件渲染，后端只返回默认配置模型。"""
        return [], self._default_config()

    def get_page(self) -> List[Dict[str, Any]]:
        """Vue 模式下详情页由远程 Page 组件渲染，后端返回空列表。"""
        return []

    def get_dashboard_meta(self) -> Optional[List[Dict[str, str]]]:
        """声明仪表板窗口；插件未启用时不注册。"""
        if not self.get_state():
            return None
        return [{"key": "works", "name": f"{self.plugin_name} · 最新作品"}]

    def get_dashboard(
        self, key: str = "", **kwargs: Any
    ) -> Optional[Tuple[Dict[str, Any], Dict[str, Any], List[dict]]]:
        """声明仪表板内容，返回 ``(列配置, 全局配置, 页面 JSON)`` 三元组。

        Vue 联邦插件通过前端 Dashboard 组件呈现内容，因此页面 JSON 为空。
        """
        if not self.get_state():
            return None
        if key and key != "works":
            return None
        total, new_count = self._count_works()
        return (
            {"cols": 12, "sm": 6, "md": 4},
            {
                "title": f"{self.plugin_name} · 最新作品",
                "subtitle": f"{len(self._actor_entries)} 位演员｜{total} 部作品"
                + (f"｜{new_count} 部新作品" if new_count else ""),
                "refresh": 300,
                "border": True,
            },
            [],
        )

    def get_sidebar_nav(self) -> List[Dict[str, Any]]:
        """声明主界面侧栏全页入口；仅 Vue 渲染模式的插件会被聚合。

        ``section`` 仅接受 start / discovery / subscribe / organize / system；
        ``permission`` 仅接受 subscribe / discovery / search / manage / admin。
        """
        if not self.get_state():
            return []
        return [
            {
                "nav_key": "main",
                "title": self.plugin_name,
                "icon": "mdi-account-star-outline",
                "section": "subscribe",
                "permission": "subscribe",
                "order": 30,
            },
            {
                "nav_key": "settings",
                "title": f"{self.plugin_name} · 运行状态",
                "icon": "mdi-chart-timeline-variant",
                "section": "subscribe",
                "permission": "subscribe",
                "order": 31,
            },
        ]

    # ─── 后台能力：定时服务 / 远程命令 / HTTP 接口 ────────────────

    def get_service(self) -> List[Dict[str, Any]]:
        """注册定时刷新服务；启用后可在「设定 - 服务」查看状态与手动启动。"""
        if not self.get_state() or not self._actor_entries:
            return []
        cron = self._cron or "0 8 * * *"
        try:
            trigger = CronTrigger.from_crontab(cron)
        except Exception as err:
            logger.error(f"{self.plugin_name} cron 表达式不合法（{cron}）：{err}")
            return []
        return [
            {
                "id": f"{self.__class__.__name__}.Refresh",
                "name": f"{self.plugin_name}刷新服务",
                "trigger": trigger,
                "func": self.execute_task,
                "kwargs": {"trigger": "cron"},
            }
        ]

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """注册远程命令，实际动作通过 EventType.PluginAction 事件路由。"""
        return [
            {
                "cmd": "/doubanactor",
                "event": EventType.PluginAction,
                "desc": "刷新豆瓣演员最新作品",
                "category": "插件命令",
                "data": {"action": "doubanactorsubscribe_refresh"},
            }
        ]

    @eventmanager.register(EventType.PluginAction)
    def on_plugin_action(self, event: Event) -> None:
        """响应远程命令；仅处理属于本插件的 action。"""
        event_data = event.event_data or {}
        if event_data.get("action") != "doubanactorsubscribe_refresh":
            return
        self.execute_task(trigger="command")

    def get_api(self) -> List[Dict[str, Any]]:
        """声明插件 HTTP 接口，最终挂载在 ``/api/v1/plugin/<PluginID>/<path>``。

        面向前端联邦组件的接口使用 ``bear`` 鉴权。
        """
        return [
            {
                "path": "/config",
                "endpoint": self.api_get_config,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取插件配置",
            },
            {
                "path": "/config",
                "endpoint": self.api_update_config,
                "methods": ["PUT"],
                "auth": "bear",
                "summary": "更新插件配置",
            },
            {
                "path": "/works",
                "endpoint": self.api_get_works,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取演员与其最新作品",
            },
            {
                "path": "/run",
                "endpoint": self.api_run,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "立即刷新一次",
            },
            {
                "path": "/search_actor",
                "endpoint": self.api_search_actor,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "按名称搜索豆瓣演员",
            },
            {
                "path": "/clear",
                "endpoint": self.api_clear,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "清空作品与自动订阅记录",
            },
        ]

    # ─── 高级能力：工作流动作 / 智能体工具 ────────────────────────

    def get_actions(self) -> List[Dict[str, Any]]:
        """注册工作流动作；动作函数第一个参数固定为 ActionContent，返回 ``(成功, ActionContent)``。"""
        return [
            {
                "id": "doubanactorsubscribe_refresh",
                "name": f"{self.plugin_name} · 刷新作品",
                "func": self.action_refresh,
                "kwargs": {},
            }
        ]

    def action_refresh(self, action: Any = None, **kwargs: Any) -> Tuple[bool, Any]:
        """工作流动作实现：刷新一次并原样回传 ActionContent。"""
        ok = self.execute_task(trigger="workflow")
        return ok, action

    def get_agent_tools(self) -> List[type]:
        """注册智能体工具，供 MoviePilot 的 AI 智能体查询演员最新作品。"""
        DoubanActorWorksTool.bind(self)
        return [DoubanActorWorksTool]

    # ─── 业务逻辑：刷新作品 ──────────────────────────────────────

    def execute_task(self, trigger: str = "manual") -> bool:
        """刷新全部配置演员的作品快照，并按配置执行自动订阅。

        :param trigger: 触发来源，取值 manual / cron / command / workflow / api / once
        :return: 是否执行成功（未启用或未配置演员时返回 False）
        """
        if not self.get_state():
            logger.info(f"{self.plugin_name} 未启用，跳过执行")
            return False
        if not self._actor_entries:
            logger.warning(f"{self.plugin_name} 未配置演员，跳过执行")
            return False

        started = time.time()
        client = _DoubanClient(proxy=self._proxy)
        previous = self._load_works()
        snapshot: Dict[str, Any] = {}
        errors: List[str] = []
        new_count = 0

        for key in self._actor_entries:
            try:
                actor, works = self._refresh_actor(client, key, previous)
            except Exception as err:  # pragma: no cover - 单演员失败不影响其他演员
                logger.error(f"{self.plugin_name} 刷新演员「{key}」失败：{err}")
                errors.append(f"{key}：{err}")
                continue
            if actor.get("error"):
                errors.append(f"{key}：{actor['error']}")
            group_key = str(actor.get("id") or key)
            snapshot[group_key] = {"actor": actor, "works": works}
            new_count += sum(1 for item in works if item.get("is_new"))

        self.save_data(self._DATA_WORKS, snapshot)

        subscribed: List[Dict[str, Any]] = []
        if self._auto_subscribe:
            subscribed = self._auto_subscribe_works(snapshot, previous, errors)

        elapsed_ms = int((time.time() - started) * 1000)
        self._run_count += 1
        self._last_run_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save_data(
            self._DATA_STATE,
            {"run_count": self._run_count, "last_run_at": self._last_run_at},
        )

        work_total = sum(len(group["works"]) for group in snapshot.values())
        detail = (
            f"刷新 {len(snapshot)} 位演员、{work_total} 部作品，"
            f"新增 {new_count} 部，自动订阅 {len(subscribed)} 部（{elapsed_ms} ms）"
        )
        if errors:
            detail += f"，{len(errors)} 项异常"
        logger.info(f"{self.plugin_name} 任务完成（{trigger}）：{detail}")

        if self._notify:
            self._send_notify(detail, subscribed, errors)
        return True

    def get_works_payload(self) -> Dict[str, Any]:
        """组装面板所需的完整数据（演员 + 作品 + 统计）。"""
        snapshot = self._load_works()
        actors: List[Dict[str, Any]] = []
        for group in snapshot.values():
            if not isinstance(group, dict):
                continue
            actor = dict(group.get("actor") or {})
            actor["works"] = list(group.get("works") or [])
            actors.append(actor)
        actors.sort(key=lambda item: str(item.get("name") or ""))
        total = sum(len(item["works"]) for item in actors)
        new_count = sum(1 for item in actors for work in item["works"] if work.get("is_new"))
        return {
            "enabled": self._enabled,
            "updated_at": self._last_run_at,
            "run_count": self._run_count,
            "actor_count": len(self._actor_entries),
            "work_count": total,
            "new_count": new_count,
            "auto_subscribe": self._auto_subscribe,
            "auto_only_new": self._auto_only_new,
            "auto_min_vote": self._auto_min_vote,
            "auto_types": list(self._auto_types),
            "auto_subscribed": self._load_sub_history()[:50],
            "errors": self._load_errors(),
            "actors": actors,
        }

    # ─── 业务逻辑：演员解析与作品抓取 ────────────────────────────

    def _refresh_actor(
        self, client: "_DoubanClient", key: str, previous: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """解析（必要时搜索）演员并抓取其最新作品，返回 ``(演员信息, 作品列表)``。"""
        cache = self._load_actor_cache()
        actor: Dict[str, Any] = dict(cache.get(key) or {})
        actor_id = str(actor.get("id") or "").strip()
        if not actor_id:
            actor = self._resolve_actor(client, key)
            actor_id = str(actor.get("id") or "").strip()

        # 每次刷新都取一次人物详情：既刷新头像/简介，也拿到最新的作品集 ID
        detail = client.person_detail(actor_id) if actor_id else None
        if detail:
            actor = {**actor, **self._actor_from_detail(actor_id, detail, key)}
        if actor_id and not actor.get("error"):
            cache[key] = {k: v for k, v in actor.items() if k != "works"}
            self.save_data(self._DATA_ACTORS, cache)

        collection_id = self._work_collection_id(detail) if detail else None
        if not collection_id:
            if not actor.get("error"):
                actor["error"] = "未找到该演员的豆瓣影视作品集"
            return actor, []

        # 豆瓣作品集接口不支持翻页，每位演员最多取到 10 部
        fetch_count = min(self._max_works, _DoubanClient.MAX_WORKS_PER_REQUEST)
        raw_works = client.person_works(
            collection_id, start=0, count=fetch_count, sort_by=self._sort_by
        )
        works: List[Dict[str, Any]] = []
        for item in raw_works:
            work = self._normalize_work(item)
            if work:
                works.append(work)
        works = self._sort_works(works)[: self._max_works]

        # 继承首次发现时间，据此标记 is_new（供面板显示「新」徽标与自动订阅判定）
        previous_works: List[Any] = []
        if isinstance(previous, dict):
            group = previous.get(actor_id)
            if isinstance(group, dict):
                previous_works = group.get("works") or []
        seen = {
            str(item.get("media_id")): item.get("first_seen")
            for item in previous_works
            if isinstance(item, dict) and item.get("media_id")
        }
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for work in works:
            first_seen = seen.get(work["media_id"])
            if first_seen:
                work["first_seen"] = first_seen
                work["is_new"] = False
            else:
                work["first_seen"] = now
                work["is_new"] = True
        return actor, works

    def _resolve_actor(self, client: "_DoubanClient", key: str) -> Dict[str, Any]:
        """把配置项解析为豆瓣人物：纯数字按人物 ID 处理，否则按名称搜索。"""
        if key.isdigit():
            return {"key": key, "id": key, "name": key, "resolved_from": "id", "error": None}

        candidates = client.search_person(key)
        if not candidates:
            return {
                "key": key,
                "id": "",
                "name": key,
                "resolved_from": "search",
                "error": "豆瓣未搜索到该演员，请改用人物 ID",
            }
        exact = next((item for item in candidates if item.get("name") == key), None)
        matched = exact or candidates[0]
        return {
            "key": key,
            "id": str(matched.get("id") or ""),
            "name": _clean_text(matched.get("name")) or key,
            "avatar": matched.get("avatar"),
            "resolved_from": "search",
            "error": None,
        }

    @staticmethod
    def _actor_from_detail(actor_id: str, detail: Dict[str, Any], key: str) -> Dict[str, Any]:
        """从豆瓣人物详情响应提取展示信息。"""
        cover = detail.get("cover_img") if isinstance(detail.get("cover_img"), dict) else {}
        avatar = str(cover.get("url") or "").replace("/l/public/", "/s/public/")
        extra = detail.get("extra") if isinstance(detail.get("extra"), dict) else {}
        return {
            "key": key,
            "id": str(detail.get("id") or actor_id),
            "name": _clean_text(detail.get("title")) or key,
            "avatar": avatar or None,
            "biography": _clean_text(extra.get("short_info"))[:200],
            "error": None,
        }

    @staticmethod
    def _work_collection_id(detail: Optional[Dict[str, Any]]) -> Optional[str]:
        """从人物详情的 modules 中取「影视」作品集 ID。"""
        if not isinstance(detail, dict):
            return None
        collections: List[Dict[str, Any]] = []
        for module in detail.get("modules") or []:
            if not isinstance(module, dict) or module.get("type") != "work_collections":
                continue
            payload = module.get("payload")
            if isinstance(payload, dict) and payload.get("id"):
                collections.append(payload)
        if not collections:
            return None
        # 标题实测为「作品集」，旧版可能是「影视」，两种都优先匹配
        preferred = next(
            (
                item
                for item in collections
                if any(
                    keyword in str(item.get("title") or item.get("name") or "")
                    for keyword in ("影视", "作品集")
                )
            ),
            None,
        )
        return str((preferred or collections[0]).get("id"))

    @classmethod
    def _normalize_work(cls, raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """把豆瓣作品条目归一化为前端可直接渲染的结构。

        豆瓣作品集接口返回的条目形如 ``{"roles": [...], "subject": {...}}``，
        其中的字段位置容易踩坑：

        * ``subject.type`` 恒为 ``"subject"``（实体种类），真正的媒体类型在 ``subject.subtype``；
        * 年份在 ``subject.extra.year``，顶层没有 ``year``；
        * 评分在 ``subject.extra.rating_group.rating.value``（无评分时 rating 为 null）；
        * 简介在 ``subject.extra.short_info``。
        """
        if not isinstance(raw, dict):
            return None
        subject = raw.get("subject") if isinstance(raw.get("subject"), dict) else raw
        media_id = str(subject.get("id") or "").strip()
        title = _clean_text(subject.get("title"))
        if not media_id.isdigit() or not title:
            return None

        extra = subject.get("extra") if isinstance(subject.get("extra"), dict) else {}

        # subtype 才是媒体类型；type 只在没有 subtype 时兜底，且要排除 "subject" 这个占位值
        raw_type = _clean_text(
            subject.get("subtype") or subject.get("type_name") or subject.get("type")
        )
        if raw_type.lower() == "subject":
            raw_type = ""
        mtype = _TYPE_ALIASES.get(raw_type.lower(), "") or _TYPE_ALIASES.get(raw_type, "")

        pic = subject.get("pic") if isinstance(subject.get("pic"), dict) else {}
        cover = subject.get("cover") if isinstance(subject.get("cover"), dict) else {}
        poster = (
            pic.get("large")
            or pic.get("normal")
            or cover.get("large")
            or cover.get("normal")
            or subject.get("cover_url")
            or ""
        )
        if isinstance(poster, dict):
            poster = poster.get("url") or ""

        return {
            "media_source": MediaSource.Douban.value,
            "media_id": media_id,
            "title": title,
            "year": _clean_text(subject.get("year") or extra.get("year")),
            "type": mtype,
            "raw_type": raw_type,
            "subscribable": mtype in _SUBSCRIBABLE_TYPES,
            "vote": cls._extract_vote(subject, extra),
            "poster": str(poster),
            "subtitle": _clean_text(subject.get("card_subtitle") or extra.get("short_info")),
            "url": f"https://movie.douban.com/subject/{media_id}/",
            "roles": cls._extract_roles(raw.get("roles")),
        }

    @staticmethod
    def _extract_vote(subject: Dict[str, Any], extra: Dict[str, Any]) -> float:
        """从作品条目中取评分；兼容顶层 rating 与 extra.rating_group.rating 两种布局。"""
        value: Any = None
        rating = subject.get("rating") if isinstance(subject.get("rating"), dict) else {}
        value = rating.get("value")
        if value in (None, ""):
            group = extra.get("rating_group") if isinstance(extra.get("rating_group"), dict) else {}
            inner = group.get("rating") if isinstance(group.get("rating"), dict) else {}
            value = inner.get("value")
        try:
            return round(float(value), 1) if value not in (None, "") else 0.0
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _extract_roles(value: Any) -> List[str]:
        """从作品条目的 roles/actors 字段中尽力提取该演员的职务。"""
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if not isinstance(value, list):
            return []
        roles: List[str] = []
        for item in value:
            text = ""
            if isinstance(item, str):
                text = item.strip()
            elif isinstance(item, dict):
                text = str(item.get("name") or item.get("title") or "").strip()
            if text and text not in roles:
                roles.append(text)
        return roles

    @staticmethod
    def _sort_works(works: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """按年份倒序排列；Python 稳定排序保证同一年内保留豆瓣的按时间倒序。"""

        def year_of(item: Dict[str, Any]) -> int:
            text = str(item.get("year") or "").strip()[:4]
            return int(text) if text.isdigit() else 0

        return sorted(works, key=year_of, reverse=True)

    # ─── 业务逻辑：自动订阅 ──────────────────────────────────────

    def _auto_subscribe_works(
        self,
        snapshot: Dict[str, Any],
        previous: Dict[str, Any],
        errors: List[str],
    ) -> List[Dict[str, Any]]:
        """对新出现且满足筛选条件的作品调用订阅链落库。"""
        seen = set(self.get_data(self._DATA_SEEN) or [])
        history = self._load_sub_history()
        subscribed: List[Dict[str, Any]] = []
        budget = self._auto_max_per_run

        for group_key, group in snapshot.items():
            if budget <= 0:
                break
            actor = group.get("actor") or {}
            had_previous = bool((previous.get(group_key) or {}).get("works"))
            for work in group.get("works") or []:
                if budget <= 0:
                    break
                unique = f"{work.get('media_source')}:{work.get('media_id')}"
                if unique in seen:
                    continue
                if not work.get("is_new"):
                    continue
                # 首次抓取某演员时只建立基线，避免一次性订阅其全部历史作品
                if not had_previous and self._auto_only_new:
                    seen.add(unique)
                    continue
                if not work.get("subscribable"):
                    continue
                if self._auto_types and work.get("type") not in self._auto_types:
                    continue
                if self._auto_min_vote and float(work.get("vote") or 0) < self._auto_min_vote:
                    continue

                ok, message = self._add_subscribe(work)
                seen.add(unique)
                budget -= 1
                record = {
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "actor": str(actor.get("name") or ""),
                    "title": str(work.get("title") or ""),
                    "year": str(work.get("year") or ""),
                    "type": str(work.get("type") or ""),
                    "vote": work.get("vote"),
                    "media_id": str(work.get("media_id") or ""),
                    "success": ok,
                    "detail": message,
                }
                history.insert(0, record)
                if ok:
                    subscribed.append(record)
                    logger.info(f"{self.plugin_name} 自动订阅成功：{record['title']}（{message}）")
                else:
                    errors.append(f"自动订阅 {record['title']} 失败：{message}")
                    logger.warning(
                        f"{self.plugin_name} 自动订阅失败：{record['title']}（{message}）"
                    )

        self.save_data(self._DATA_SEEN, sorted(seen)[-2000:])
        self.save_data(self._DATA_SUBS, history[:200])
        return subscribed

    def _add_subscribe(self, work: Dict[str, Any]) -> Tuple[bool, str]:
        """把单个作品提交给 MoviePilot 订阅链；返回 ``(是否成功, 说明)``。"""
        title = str(work.get("title") or "").strip()
        media_id = str(work.get("media_id") or "").strip()
        if not title or not media_id:
            return False, "标题或豆瓣 ID 为空"
        mtype = MediaType(work["type"]) if work.get("type") in _SUBSCRIBABLE_TYPES else None
        try:
            meta = MetaInfo(title)
            if work.get("year"):
                meta.year = str(work["year"])
            if mtype:
                meta.type = mtype
            chain = SubscribeChain()
            # 命中已有订阅时直接视为成功，避免重复入库
            try:
                if chain.exists(meta=meta):
                    return True, "订阅已存在"
            except Exception as err:  # pragma: no cover - 宿主版本差异兜底
                logger.debug(f"{self.plugin_name} 订阅存在性检查跳过：{err}")
            sid, message = chain.add(
                title=title,
                year=str(work.get("year") or ""),
                mtype=mtype,
                media_source=MediaSource.Douban,
                media_id=media_id,
                season=meta.begin_season,
                exist_ok=True,
                username=PLUGIN_NAME,
            )
            if sid:
                return True, f"订阅成功（ID {sid}）"
            return False, str(message or "订阅链未返回订阅 ID")
        except Exception as err:
            return False, str(err)

    # ─── 数据读写 ────────────────────────────────────────────────

    def _load_works(self) -> Dict[str, Any]:
        data = self.get_data(self._DATA_WORKS)
        return data if isinstance(data, dict) else {}

    def _load_actor_cache(self) -> Dict[str, Any]:
        data = self.get_data(self._DATA_ACTORS)
        return data if isinstance(data, dict) else {}

    def _load_sub_history(self) -> List[Dict[str, Any]]:
        data = self.get_data(self._DATA_SUBS)
        return list(data) if isinstance(data, list) else []

    def _load_errors(self) -> List[str]:
        snapshot = self._load_works()
        errors: List[str] = []
        for key, group in snapshot.items():
            if not isinstance(group, dict):
                continue
            actor = group.get("actor")
            if isinstance(actor, dict) and actor.get("error"):
                errors.append(f"{actor.get('name') or key}：{actor['error']}")
        return errors

    def _count_works(self) -> Tuple[int, int]:
        snapshot = self._load_works()
        total = 0
        new_count = 0
        for group in snapshot.values():
            if not isinstance(group, dict):
                continue
            works = group.get("works") or []
            total += len(works)
            new_count += sum(1 for item in works if item.get("is_new"))
        return total, new_count

    def _send_notify(
        self, detail: str, subscribed: List[Dict[str, Any]], errors: List[str]
    ) -> None:
        """通过宿主通知渠道发送结果；通知失败不影响主流程。"""
        lines = [detail]
        if subscribed:
            lines.append("")
            lines.append("自动订阅：")
            lines.extend(
                f"· {item['title']}（{item['year']}）{item.get('type') or ''}"
                for item in subscribed[:10]
            )
        if errors:
            lines.append("")
            lines.append("异常：")
            lines.extend(f"· {item}" for item in errors[:5])
        try:
            self.post_message(
                mtype=_MessageType.Plugin,
                title=f"【{self.plugin_name}】刷新完成",
                text="\n".join(lines),
            )
        except Exception as err:  # pragma: no cover - 未配置通知渠道时兜底
            logger.warning(f"{self.plugin_name} 发送通知失败：{err}")

    def _add_once_job(self) -> bool:
        """向宿主调度器登记一次性任务，返回是否登记成功。"""
        try:
            from app.sdk import scheduler as scheduler_sdk

            add_once = getattr(scheduler_sdk, "add_plugin_once_job", None)
            if not add_once:
                logger.warning(f"{self.plugin_name} 当前宿主不支持一次性任务接口")
                return False
            add_once(
                self.__class__.__name__,
                self._ONCE_JOB_ID,
                self.execute_task,
                f"{self.plugin_name}立即刷新一次",
                delay_seconds=3,
                kwargs={"trigger": "once"},
            )
            return True
        except Exception as err:  # pragma: no cover - 宿主版本差异兜底
            logger.warning(f"{self.plugin_name} 登记一次性任务失败：{err}")
            return False

    # ─── 插件 API 实现 ───────────────────────────────────────────

    def api_get_config(self) -> Dict[str, Any]:
        """返回当前运行时配置，供前端 Config 组件回显。"""
        return {
            "enabled": self._enabled,
            "cron": self._cron,
            "actors": "\n".join(self._actor_entries),
            "max_works": self._max_works,
            "sort_by": self._sort_by,
            "proxy": self._proxy,
            "notify": self._notify,
            "auto_subscribe": self._auto_subscribe,
            "auto_only_new": self._auto_only_new,
            "auto_min_vote": self._auto_min_vote,
            "auto_types": ",".join(self._auto_types),
            "auto_max_per_run": self._auto_max_per_run,
            "run_count": self._run_count,
        }

    def api_update_config(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """接收前端提交的配置，持久化后重新初始化插件。"""
        if not config or not isinstance(config, dict):
            return {"success": False, "message": "请求体不是合法对象"}

        merged = {**self.api_get_config(), **config}
        merged["enabled"] = bool(merged.get("enabled"))
        merged["notify"] = bool(merged.get("notify"))
        merged["proxy"] = bool(merged.get("proxy"))
        merged["auto_subscribe"] = bool(merged.get("auto_subscribe"))
        merged["auto_only_new"] = bool(merged.get("auto_only_new", True))
        merged["cron"] = str(merged.get("cron") or "0 8 * * *").strip()
        merged["actors"] = str(merged.get("actors") or "").strip()
        merged["sort_by"] = str(merged.get("sort_by") or "time").strip() or "time"
        merged["auto_types"] = str(merged.get("auto_types") or "").strip()
        merged["auto_min_vote"] = self._to_float(merged.get("auto_min_vote"), 0.0)
        merged["max_works"] = self._clamp_int(merged.get("max_works"), 10, 5, 10)
        merged["auto_max_per_run"] = self._clamp_int(merged.get("auto_max_per_run"), 5, 1, 100)
        # run_count 属于运行时统计，不落盘
        merged.pop("run_count", None)

        if not self.update_config(merged):
            return {"success": False, "message": "配置持久化失败"}

        self.init_plugin(merged)
        return {"success": True, "data": self.api_get_config()}

    def api_get_works(self) -> Dict[str, Any]:
        """返回演员与作品快照，供前端面板渲染。"""
        return {"success": True, "data": self.get_works_payload()}

    def api_run(self) -> Dict[str, Any]:
        """手动刷新一次。"""
        ok = self.execute_task(trigger="api")
        return {
            "success": ok,
            "message": "刷新完成" if ok else "刷新失败（插件未启用或未配置演员）",
            "data": self.get_works_payload(),
        }

    def api_search_actor(self, name: str = "") -> Dict[str, Any]:
        """按名称搜索豆瓣演员，供配置页辅助确定人物 ID。"""
        keyword = str(name or "").strip()
        if not keyword:
            return {"success": False, "message": "请提供演员名称"}
        try:
            results = _DoubanClient(proxy=self._proxy).search_person(keyword)
        except Exception as err:
            return {"success": False, "message": f"搜索失败：{err}"}
        return {"success": True, "data": results}

    def api_clear(self) -> Dict[str, Any]:
        """清空作品快照与自动订阅记录（配置不受影响）。"""
        self.save_data(self._DATA_WORKS, {})
        self.save_data(self._DATA_SUBS, [])
        self.save_data(self._DATA_SEEN, [])
        self._run_count = 0
        self._last_run_at = ""
        self.save_data(self._DATA_STATE, {"run_count": 0, "last_run_at": ""})
        return {"success": True, "message": "作品与自动订阅记录已清空"}

    # ─── 配置解析与默认值 ────────────────────────────────────────

    @staticmethod
    def _parse_actors(value: Any) -> List[str]:
        """解析演员配置：支持换行、逗号、分号分隔，去重并保序。"""
        if isinstance(value, (list, tuple)):
            raw_items = [str(item) for item in value]
        else:
            text = str(value or "").replace("，", ",").replace("；", ";")
            for sep in ("\r\n", "\n", ";", ","):
                text = text.replace(sep, "\n")
            raw_items = text.split("\n")
        result: List[str] = []
        for item in raw_items:
            name = item.strip()
            if name and name not in result:
                result.append(name)
        return result

    @staticmethod
    def _parse_types(value: Any) -> List[str]:
        """解析自动订阅的媒体类型白名单；未识别时回退为电影 + 电视剧。"""
        if isinstance(value, (list, tuple)):
            raw_items = [str(item) for item in value]
        else:
            text = str(value or "").replace("，", ",").replace("；", ",").replace(";", ",")
            raw_items = text.split(",")
        result = [item.strip() for item in raw_items if item.strip() in _SUBSCRIBABLE_TYPES]
        deduped: List[str] = []
        for item in result:
            if item not in deduped:
                deduped.append(item)
        return deduped or list(_SUBSCRIBABLE_TYPES)

    @staticmethod
    def _clamp_int(value: Any, default: int, low: int, high: int) -> int:
        try:
            number = int(float(value))
        except (TypeError, ValueError):
            return default
        return max(low, min(high, number))

    @staticmethod
    def _to_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _default_config() -> Dict[str, Any]:
        """返回配置页默认值。"""
        return {
            "enabled": False,
            "cron": "0 8 * * *",
            "actors": "",
            "max_works": 10,
            "sort_by": "time",
            "proxy": False,
            "notify": False,
            "auto_subscribe": False,
            "auto_only_new": True,
            "auto_min_vote": 0,
            "auto_types": "电影,电视剧",
            "auto_max_per_run": 5,
            "onlyonce": False,
        }
