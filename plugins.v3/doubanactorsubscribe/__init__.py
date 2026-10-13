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
import re
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

# 订阅状态（宿主 subscribe.state）：N-新建 R-订阅中 P-待定 S-暂停。
# 「待定(P)」语义为「允许搜索、不允许完成」，正是未播出影视需要的「预订」。
_SUBSCRIBE_STATE_PENDING = "P"

# 订阅被拒时，命中这些关键词说明缺的是「影视信息」（未播出 / 条目刚建、TMDB 还没收录），
# 而不是作品本身有问题 —— 这类失败应当降级为「预订」，而不是直接判失败。
_RESERVE_FAILURE_HINTS = (
    "季集信息",
    "季的信息",
    "总集数",
    "集数信息",
    "未识别到媒体信息",
    "媒体信息识别失败",
)

# 预订占位集数：真实集数拿不到时先按 1 集占位。宿主刷新增量时会向上覆盖它
# （前提是 manual_total_episode 保持 0，所以绝不能顺手把它也置 1）。
_RESERVE_TOTAL_EPISODE = 1


def _subscribe_oper() -> Any:
    """惰性获取宿主的订阅写库端口；宿主缺这个入口时返回 None。

    走官方 SDK 兼容入口 ``app.sdk._legacy.subscribe.SubscribeOper``，
    避免直接依赖宿主内部模块路径。
    """
    try:
        from app.sdk._legacy.subscribe import SubscribeOper
    except Exception as err:  # pragma: no cover - 宿主版本差异兜底
        logger.debug(f"{PLUGIN_NAME} 未找到订阅写库入口，预订将只走订阅链：{err}")
        return None
    try:
        return SubscribeOper()
    except Exception as err:  # pragma: no cover - 宿主版本差异兜底
        logger.debug(f"{PLUGIN_NAME} 初始化订阅写库入口失败：{err}")
        return None


def _looks_like_missing_info(message: str) -> bool:
    """判断订阅失败是否属于「影视信息还没到」这一类（未播出 / 尚未收录）。

    已知文案：「媒体信息中没有季集信息」「未获取到第 N 季的总集数」「未识别到媒体信息」
    「媒体信息识别失败」。最后再用「季」「集」同现兜底，宿主换文案时不至于漏判。
    """
    text = str(message or "")
    if any(hint in text for hint in _RESERVE_FAILURE_HINTS):
        return True
    return "季" in text and "集" in text

# 豆瓣部分标题会夹带零宽/双向控制字符（实测「神探之痕迹\u200e」），
# 这类字符不可见却会污染订阅名与去重比对，统一剔除。
_INVISIBLE_CHARS = dict.fromkeys(
    [0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2060, 0xFEFF]
)


def _clean_text(value: Any) -> str:
    """去掉首尾空白与零宽/双向控制字符。"""
    return str(value or "").translate(_INVISIBLE_CHARS).strip()


# 豆瓣匿名搜索的限流非常严格：实测连续搜索约 5 次后，后续请求一律返回
# 403 ``{"msg": "need_login", "code": 103}``，且 90 秒内不恢复。
# 这种失败**不是**「没这个人」，必须与真正的空结果分开提示，否则会误导用户改配置。
_RATE_LIMIT_HINT = "豆瓣搜索被限流，稍后会自动重试；也可直接填人物 ID 跳过搜索"

# 豆瓣对匿名请求返回 403 need_login（code 103）作为限流信号；带上已登录的 Cookie 能显著抬高额度。
# 因此这条提示是可操作的：告诉用户去哪里解决，而不是让他反复重试。
_NEED_LOGIN_HINT = (
    "豆瓣要求登录（need_login）：请在插件配置里粘贴「豆瓣 Cookie」，"
    "或确认宿主的 CookieCloud 已同步豆瓣登录态；额度会明显提升。"
    "也可直接填人物 ID/主页链接跳过搜索"
)

# 已经带 Cookie 却仍返回 need_login，通常意味着登录态已过期，提示要能区分这两种情况
_COOKIE_EXPIRED_HINT = (
    "豆瓣仍要求登录（need_login）：Cookie 可能已失效，"
    "请在浏览器重新登录豆瓣并同步 CookieCloud，或在插件里更新豆瓣 Cookie"
)

# 每位演员「成功搜索一次」后，24 小时内不再按名称重复搜索。
# 豆瓣的搜索额度（匿名约 5 次、登录态也只多几倍）极其有限，而解析出人物 ID 后
# 本可长期复用；这里加一道 24 小时冷却，避免缓存丢失或异常路径下白花一次额度。
#
# 冷却是**成功才触发**的：限流 / need_login / 查无此人这些失败不记账，
# 下一轮刷新仍会重试（限流窗口很短，锁死一整天反而让演员长期解析不出来）。
#
# 注意：冷却只作用于「按名称搜索」这一步。已经解析出人物 ID 的演员本来就不搜索，
# 其作品与详情仍按 cron / 手动刷新照常抓取，不受此冷却影响。
_SEARCH_COOLDOWN_SECONDS = 24 * 3600

# 「新」的时间窗：演员自**加入订阅列表**起、作品自**在演员加入之后首次出现**起，
# N 天内标「新」。
#
# 这里刻意不用「相对上一轮快照新增」来判定 —— 那个口径只活到下一次刷新为止：
# 抓完新作品后随手点一次刷新、插件被重载、或定时任务跑一轮，标记就全被清零了，
# 于是计数长期是 0，看起来就像插件没抓到东西。按时间窗现算则天然稳定。
#
# 另一半同样关键：**作品只在「演员加入之后」出现才算新**。
# 否则刚把上百位演员一次性导进来时，他们过去几十年的作品会被整片标成「新」
# （实测 98 位演员 = 844 部全中），既糊成一片又毫无信息量。
# 判定方式是把作品的 first_seen 与演员的 added_at 比较：同一轮刷新里写入的基线
# first_seen 与 added_at 是**同一个 now 字符串**，因此基线作品天然不算「新」，
# 只有后来某轮刷新才冒出来的作品才会挂上「新」。演员本身则单独在 chip 上标「新」，
# 刚加进来的演员因此一眼可辨。
#
# 天数不宜太长，3 天足够跨过一个周末、又能让噪声自行消散；面板会把天数与口径写出来。
_NEW_WINDOW_DAYS = 3
_NEW_WINDOW_SECONDS = _NEW_WINDOW_DAYS * 24 * 3600

# 作品 first_seen 的落盘格式（与 strftime 保持一致）
_TS_FORMAT = "%Y-%m-%d %H:%M:%S"


def _parse_ts(value: Any) -> float:
    """把 ``first_seen`` 文本解析为 epoch 秒；格式非法或缺失时返回 0。"""
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        return datetime.strptime(text, _TS_FORMAT).timestamp()
    except ValueError:
        return 0.0


def _format_remaining(seconds: float) -> str:
    """把剩余冷却秒数写成「X 小时 Y 分钟」，便于用户判断什么时候会重试。"""
    total = max(0, int(seconds))
    hours, minutes = total // 3600, (total % 3600) // 60
    if hours and minutes:
        return f"{hours} 小时 {minutes} 分钟"
    if hours:
        return f"{hours} 小时"
    return f"{max(1, minutes)} 分钟"


def _search_cooldown_hint(remain_seconds: float) -> str:
    """搜索冷却期内的提示。要带上「还有多久」，否则用户会以为插件卡住了。"""
    return (
        f"24 小时内已搜索过（每位演员每 24 小时只搜 1 次），"
        f"约 {_format_remaining(remain_seconds)}后自动重试；"
        f"也可直接填人物 ID/主页链接跳过搜索"
    )

# 从豆瓣人物主页地址中提取人物 ID，方便用户直接粘贴链接
_PERSON_URL_PATTERN = re.compile(r"(?:personage|celebrity)/(\d+)")


class _CookieCloudClient:
    """从 CookieCloud 取指定域名的 Cookie。

    为什么不自己解密：CookieCloud 服务端支持 ``POST /get/{key}`` 带密码直接返回**已解密**的
    ``cookie_data``，这样插件不必实现 CookieCloud 的 AES 解密（那需要宿主内部模块或额外依赖），
    只依赖 ``app.sdk.network`` 即可。

    注意：本类只把 Cookie 留在内存里，不落盘、不写日志，避免把用户的登录态持久化。
    """

    TIMEOUT = 20

    def __init__(self, host: str = "", key: str = "", password: str = "") -> None:
        self._host = str(host or "").strip().rstrip("/")
        self._key = str(key or "").strip()
        self._password = str(password or "").strip()
        self.last_error = ""

    @property
    def configured(self) -> bool:
        """服务器地址、用户 KEY、加密密码三者齐全才算配置可用。"""
        return bool(self._host and self._key and self._password)

    def fetch(self, domain_keyword: str) -> str:
        """取包含 ``domain_keyword`` 的域名分组，拼成可直接使用的 Cookie 头。

        :param domain_keyword: 域名关键字，如 ``douban.com``
        :return: 形如 ``bid=xxx; dbcl2=yyy`` 的 Cookie 头；失败返回空串并写入 ``last_error``
        """
        self.last_error = ""
        if not self.configured:
            self.last_error = "CookieCloud 未配置（缺服务器地址 / KEY / 密码）"
            return ""

        response = None
        try:
            response = RequestUtils(
                content_type="application/json", timeout=self.TIMEOUT
            ).post_res(url=f"{self._host}/get/{self._key}", json={"password": self._password})
            if response is None:
                self.last_error = "CookieCloud 请求失败（网络不可达或地址有误）"
                return ""
            if response.status_code != 200:
                self.last_error = f"CookieCloud 返回 HTTP {response.status_code}"
                return ""
            payload = response.json()
        except Exception as err:  # noqa: BLE001 - 任何异常都降级为「取不到」
            self.last_error = f"CookieCloud 请求异常：{err}"
            return ""
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:  # pragma: no cover - 关闭失败可忽略
                    pass

        contents = payload.get("cookie_data") if isinstance(payload, dict) else None
        if not isinstance(contents, dict):
            # 服务端没解密时会只回 encrypted，此时必须给出明确原因，否则用户无从下手
            self.last_error = (
                "CookieCloud 只返回了密文（服务端未解密），请在插件配置里手工粘贴豆瓣 Cookie"
                if isinstance(payload, dict) and payload.get("encrypted")
                else "CookieCloud 返回内容为空"
            )
            return ""

        pairs: List[str] = []
        seen: set = set()
        for domain, cookies in contents.items():
            if domain_keyword not in str(domain).lower() or not isinstance(cookies, list):
                continue
            for item in cookies:
                if not isinstance(item, dict):
                    continue
                name, value = item.get("name"), item.get("value")
                # 同名 Cookie 只取第一个，避免后面的空值覆盖前面的有效值
                if not name or value is None or name in seen:
                    continue
                seen.add(name)
                pairs.append(f"{name}={value}")

        if not pairs:
            self.last_error = f"CookieCloud 里没有 {domain_keyword} 的 Cookie（请确认浏览器已登录豆瓣并同步）"
            return ""
        return "; ".join(pairs)


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
    # 豆瓣限流响应：搜索为 403 code 103(need_login)，详情为 403 code 400010(subject_ip_rate_limit)。
    # 详情接口的限流窗口很短（实测第 11 次失败、第 15 次已恢复），因此值得退避重试；
    # 搜索接口的限流窗口很长（90 秒内不恢复），重试几次后就该放弃并如实上报。
    RATE_LIMIT_STATUS = frozenset({403, 429, 503})
    RATE_LIMIT_RETRIES = 2
    RATE_LIMIT_BACKOFF = 1.5
    # 相邻请求之间的最小间隔，降低触发限流的概率
    POLITE_DELAY = 0.35
    USER_AGENTS = (
        "api-client/1 com.douban.frodo/7.22.0.beta9(231) Android/23 product/Mate 40 "
        "vendor/HUAWEI model/Mate 40 brand/HUAWEI  rom/android  network/wifi  platform/AndroidPad",
        "api-client/1 com.douban.frodo/7.18.0(230) Android/22 product/MI 9 vendor/Xiaomi "
        "model/MI 9 brand/Android  rom/miui6  network/wifi  platform/mobile nd/1",
    )

    def __init__(self, proxy: bool = False, cookie: str = "") -> None:
        self._proxy = proxy
        # 用户粘贴的豆瓣 Cookie（完整请求头原文）。豆瓣对匿名请求用 403 need_login
        # 做限流，带上已登录 Cookie 后额度会明显抬升，因此这是首选的可配置项。
        self._cookie = str(cookie or "").strip()
        self._last_request_at = 0.0
        # 最近一次请求的可观测状态，供上层区分「确实没有结果」与「请求被限流/失败」
        self.last_status = 0
        self.last_error = ""
        self.last_rate_limited = False
        # 是否命中过 need_login（豆瓣把「未登录」当限流信号用）
        self.last_need_login = False
        self.last_body = ""
        # 真实发起过的名称搜索次数。上层用它判断「这位演员今天到底搜没搜过」，
        # 只有真的打了搜索接口才记账，拿链接/ID 直接命中的不算。
        self.search_calls = 0

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

    def _wait_turn(self) -> None:
        """维持相邻请求之间的最小间隔。"""
        gap = time.monotonic() - self._last_request_at
        if gap < self.POLITE_DELAY:
            time.sleep(self.POLITE_DELAY - gap)
        self._last_request_at = time.monotonic()

    def _request_once(
        self, url_path: str, params: Dict[str, Any], proxies: Any
    ) -> Optional[Tuple[int, Optional[Dict[str, Any]]]]:
        """发起一次带签名的 GET，返回 ``(status, payload)``；网络层失败返回 None。"""
        self._wait_turn()
        response = None
        try:
            response = RequestUtils(
                ua=choice(self.USER_AGENTS),
                proxies=proxies,
                cookies=self._cookie or None,
                timeout=self.TIMEOUT,
            ).get_res(url=f"{self.BASE_URL}{url_path}", params=params)
            if response is None:
                self.last_error = "豆瓣请求无响应"
                logger.error(f"{PLUGIN_NAME} 豆瓣请求无响应：{url_path}")
                return None
            status = response.status_code
            self.last_status = status
            if status != 200:
                # 保留一段响应体：豆瓣用 403 need_login 表达「未登录/被限流」，
                # 只有读到 body 才能把提示写成「去配 Cookie」而不是笼统的「失败」。
                try:
                    self.last_body = (response.text or "")[:300]
                except Exception:  # pragma: no cover - 读取失败不影响判定
                    self.last_body = ""
                if "need_login" in self.last_body:
                    self.last_need_login = True
                return status, None
            payload = response.json()
            return status, (payload if isinstance(payload, dict) else None)
        except Exception as err:
            self.last_error = str(err)
            logger.error(f"{PLUGIN_NAME} 请求豆瓣接口失败（{url_path}）：{err}")
            return None
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:  # pragma: no cover - 关闭失败可忽略
                    pass

    def _get(self, url_path: str, **kwargs: Any) -> Optional[Dict[str, Any]]:
        """发起一次签名 GET 请求；限流时按指数退避重试。

        失败时不会抛异常，但会把原因写进 ``last_status`` / ``last_error`` /
        ``last_rate_limited``，让调用方能给出准确的提示而不是笼统的「无结果」。
        """
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

        self.last_status = 0
        self.last_error = ""
        self.last_rate_limited = False
        self.last_need_login = False
        self.last_body = ""

        for attempt in range(self.RATE_LIMIT_RETRIES + 1):
            outcome = self._request_once(url_path, params, proxies)
            if outcome is None:
                return None
            status, payload = outcome
            if status == 200:
                return payload
            if status in self.RATE_LIMIT_STATUS:
                self.last_rate_limited = True
                # need_login 说明豆瓣把匿名请求挡在了门外，退避重试基本无效，
                # 直接放弃并让上层提示「去配 Cookie」，比连打三次更省配额。
                if self.last_need_login and not self._cookie:
                    self.last_error = "豆瓣要求登录（need_login）"
                    logger.warning(f"{PLUGIN_NAME} 豆瓣返回 need_login，建议配置豆瓣 Cookie：{url_path}")
                    return None
                self.last_error = f"豆瓣限流（HTTP {status}）"
                if attempt < self.RATE_LIMIT_RETRIES:
                    delay = self.RATE_LIMIT_BACKOFF * (2**attempt)
                    logger.warning(f"{PLUGIN_NAME} 豆瓣限流，{delay:.1f}s 后重试：{url_path}")
                    time.sleep(delay)
                    continue
                logger.warning(f"{PLUGIN_NAME} 豆瓣接口持续限流（HTTP {status}）：{url_path}")
                return None
            self.last_error = f"豆瓣接口返回 HTTP {status}"
            logger.warning(f"{PLUGIN_NAME} 豆瓣接口返回 {status}：{url_path}")
            return None
        return None

    def failure_hint(self) -> str:
        """按最近一次失败的成因给出**可操作**的提示，供上层直接展示给用户。

        三种成因要分清：没配 Cookie（去配）、配了 Cookie 但已失效（去更新）、
        单纯被限流（等一会儿）。
        """
        if self.last_need_login:
            return _COOKIE_EXPIRED_HINT if self._cookie else _NEED_LOGIN_HINT
        return _RATE_LIMIT_HINT

    def search_person(self, name: str, count: int = 10) -> List[Dict[str, Any]]:
        """按名称搜索豆瓣人物，返回 ``[{id, name, avatar, url}]``。"""
        self.search_calls += 1
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
    plugin_version = "1.13.0"
    plugin_author = "m215owen"
    author_url = "https://github.com/m215owen"
    plugin_label = "订阅"
    # 配置项前缀：由宿主按运行实例保证唯一
    plugin_config_prefix = "doubanactorsubscribe_"
    plugin_order = 40
    auth_level = 1

    # ─── 运行时状态（统一由 init_plugin 重建，保证可重复初始化） ──────
    _enabled: bool = False
    # 是否在 MoviePilot 主界面侧栏展示插件入口（关闭后插件本身照常运行）
    _sidebar_nav: bool = True
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
    # 订阅偏好：面板与自动订阅提交时附带的下载目录、下载器与订阅站点
    _subscribe_save_path: str = ""
    _subscribe_downloader: str = ""
    _subscribe_sites: List[int] = []
    # 手填的豆瓣 Cookie（留空则自动从宿主已配置的 CookieCloud 拉取）
    _douban_cookie: str = ""
    # CookieCloud 取到的豆瓣 Cookie：只缓存于内存，不落盘
    _cookie_cache: str = ""
    _cookie_cached_at: float = 0.0
    # 当前 Cookie 来源，供面板展示：manual / cookiecloud / none
    _cookie_source: str = "none"
    # CookieCloud 取不到时的原因，供面板提示
    _cookie_hint: str = ""
    # Cookie 缓存有效期（秒）；豆瓣登录态通常能以天计，这里取半小时足够
    _COOKIE_TTL = 1800
    # 配置变更后等待后台补刷新的标记，供前端提示与轮询
    _pending_refresh: bool = False
    # 后台刷新进行中的标记；演员多时一次刷新可能持续数分钟，
    # 因此手动刷新改为后台执行，前端靠这个标记轮询进度
    _refreshing: bool = False
    # 本轮刷新开始时间，用于兜底清除异常中断残留的「刷新中」状态
    _refresh_started_at: float = 0.0
    # 超过该秒数仍未结束就认为标记已失效（避免线程异常导致标记永久卡住）
    _REFRESH_STALE_SECONDS = 1800

    # 插件数据表中的键名
    _DATA_ACTORS = "actors"
    _DATA_WORKS = "works"
    _DATA_SEEN = "auto_seen"
    _DATA_SUBS = "auto_subscribed"
    _DATA_STATE = "state"
    # 上一次生效的演员配置，用于识别「演员列表已变更」并安排自动刷新
    _DATA_CONFIGURED = "configured_actors"
    # 每位演员「最近一次成功发起名称搜索」的时间戳，用于 24 小时搜索冷却
    _DATA_SEARCH_LOG = "search_log"
    # 被用户手动忽略的作品（键为 media_source:media_id）：面板不展示，自动订阅也跳过
    _DATA_IGNORED = "ignored_works"

    # 一次性任务标识
    _ONCE_JOB_ID = "refresh_once"
    # 演员列表变更后触发的补刷新任务标识
    _STALE_JOB_ID = "refresh_stale"
    # 手动刷新改为后台任务后使用的任务标识
    _MANUAL_JOB_ID = "refresh_manual"

    # ─── 生命周期 ────────────────────────────────────────────────

    def init_plugin(self, config: dict | None = None) -> None:
        """读取配置并重建运行状态；宿主在启动与保存配置时都会调用，必须可重复执行。"""
        # 先释放上一轮运行可能遗留的资源
        self.stop_service()

        cfg: Dict[str, Any] = dict(config or {})
        self._enabled = bool(cfg.get("enabled"))
        # 默认开启：老配置里没有这个键时不应把侧栏入口弄丢
        self._sidebar_nav = bool(cfg.get("sidebar_nav", True))
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
        self._subscribe_save_path = str(cfg.get("subscribe_save_path") or "").strip()
        # 下载器名称（宿主 /download/clients 里的 name）；留空表示跟随宿主默认订阅配置
        self._subscribe_downloader = str(cfg.get("subscribe_downloader") or "").strip()
        self._subscribe_sites = self._parse_sites(cfg.get("subscribe_sites"))
        # Cookie 变更后旧缓存立即失效，避免继续用上一个账号的登录态
        new_cookie = str(cfg.get("douban_cookie") or "").strip()
        if new_cookie != self._douban_cookie:
            self._cookie_cache = ""
            self._cookie_cached_at = 0.0
        self._douban_cookie = new_cookie

        state = self.get_data(self._DATA_STATE)
        if isinstance(state, dict):
            self._run_count = self._clamp_int(state.get("run_count"), 0, 0, 10 ** 9)
            self._last_run_at = str(state.get("last_run_at") or "")

        # 演员列表变更 → 旧快照已失效：先去掉已移除演员的残留数据，再安排一次后台补刷新。
        # 之所以不在 init_plugin 里直接刷新，是因为本方法运行在宿主保存配置的 HTTP 请求线程里，
        # 同步抓豆瓣会让保存接口长时间无响应。
        actors_changed = self._detect_actors_changed()
        if actors_changed:
            self._drop_stale_snapshot()
        self.save_data(self._DATA_CONFIGURED, list(self._actor_entries))

        # 把当前运行实例注入智能体工具，避免工具依赖进程级单例查找
        DoubanActorWorksTool.bind(self)

        scheduled = False
        # 勾选「启用后立即执行一次」时交给宿主调度器延迟执行，而不是自建线程
        if self._enabled and cfg.get("onlyonce"):
            if self._add_once_job(self._ONCE_JOB_ID, 3, "once"):
                cfg["onlyonce"] = False
                self.update_config(cfg)

        # 演员列表变更，或尚无任何快照数据时，短延迟后自动补一次刷新，
        # 让面板不必等到下一个 cron 周期才更新。
        need_refresh = actors_changed or not self._load_works()
        if self._enabled and self._actor_entries and need_refresh:
            scheduled = self._add_once_job(self._STALE_JOB_ID, 2, "config_changed")
            if scheduled:
                logger.info(f"{self.plugin_name} 检测到演员配置变化，已安排后台刷新")

        self._pending_refresh = bool(scheduled)
        logger.info(
            f"{self.plugin_name} 初始化完成：enabled={self._enabled}，"
            f"演员 {len(self._actor_entries)} 位，cron={self._cron}"
            + ("，已安排补刷新" if scheduled else "")
        )

    def get_state(self) -> bool:
        """返回插件当前是否启用。"""
        return self._enabled

    def stop_service(self) -> None:
        """停用或卸载插件时释放后台资源；需保证可重复、安全地调用。"""
        self._enabled = False
        self._pending_refresh = False
        self._refreshing = False
        try:
            from app.sdk import scheduler as scheduler_sdk  # 延迟导入，避免版本差异影响加载

            remove_job = getattr(scheduler_sdk, "remove_plugin_once_job", None)
            if remove_job:
                for job_id in (self._ONCE_JOB_ID, self._STALE_JOB_ID, self._MANUAL_JOB_ID):
                    remove_job(self.__class__.__name__, job_id)
        except Exception as err:  # pragma: no cover - 宿主版本差异兜底
            logger.debug(f"{self.plugin_name} 清理一次性任务时跳过：{err}")

    def _detect_actors_changed(self) -> bool:
        """判断本次配置的演员列表与上一次生效的是否不同。

        首次初始化（尚无历史记录）视为「未变更」，避免每次重启都触发一次刷新。
        """
        previous = self.get_data(self._DATA_CONFIGURED)
        if not isinstance(previous, (list, tuple)):
            return False
        return self._parse_actors(previous) != self._actor_entries

    def _drop_stale_snapshot(self) -> None:
        """丢弃已不再属于配置的演员快照。

        只删除被移除演员的数据，保留仍然有效的演员快照，避免面板整体闪空。
        """
        snapshot = self._load_works()
        if not snapshot:
            return
        keep_ids = set()
        cache = self._load_actor_cache()
        for key in self._actor_entries:
            cached = cache.get(key) if isinstance(cache, dict) else None
            if isinstance(cached, dict) and cached.get("id"):
                keep_ids.add(str(cached["id"]))
        if not keep_ids:
            # 新配置的演员全部尚未解析出人物 ID，无法精确比对，整体清空更安全
            self.save_data(self._DATA_WORKS, {})
            return
        kept = {key: value for key, value in snapshot.items() if str(key) in keep_ids}
        if len(kept) != len(snapshot):
            self.save_data(self._DATA_WORKS, kept)

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
        total, new_count, new_actor_count = self._count_works()
        fresh_hint = (
            f"｜近 {_NEW_WINDOW_DAYS} 天新增 演员 {new_actor_count} / 作品 {new_count}"
            if (new_count or new_actor_count)
            else ""
        )
        return (
            {"cols": 12, "sm": 6, "md": 4},
            {
                "title": f"{self.plugin_name} · 最新作品",
                "subtitle": f"{len(self._actor_entries)} 位演员｜{total} 部作品" + fresh_hint,
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
        if not self.get_state() or not self._sidebar_nav:
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
        """注册定时刷新服务；启用后可在「设定 - 服务」查看状态与手动启动。

        ⚠️ 传给被调函数的参数必须写在 ``func_kwargs`` 里。宿主注册时会把
        ``service["kwargs"]`` **原样展开给 ``scheduler.add_job()``**（见
        宿主 ``scheduler/reconcile.py`` 的 ``update_plugin_job``），而 ``trigger``
        正是 ``add_job`` 自己的形参名 —— 写成 ``kwargs`` 会让 ``add_job()`` 收到
        两个 trigger（一个位置参数、一个关键字参数）并抛
        ``got multiple values for argument 'trigger'``，服务注册静默失败、
        每日定时刷新永远不会执行。宿主内置插件（如 popularsubscribe）用的也是
        ``func_kwargs``，此处与之一致。
        """
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
                "func_kwargs": {"trigger": "cron"},
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
                "path": "/reserve",
                "endpoint": self.api_reserve,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "把订阅失败的作品转为预订（待定）",
            },
            {
                "path": "/unsubscribe",
                "endpoint": self.api_unsubscribe,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "取消某部作品的订阅",
            },
            {
                "path": "/ignore",
                "endpoint": self.api_ignore,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "忽略某部作品（不再展示、自动订阅也跳过）",
            },
            {
                "path": "/unignore",
                "endpoint": self.api_unignore,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "恢复被忽略的作品",
            },
            {
                "path": "/actor/remove",
                "endpoint": self.api_remove_actor,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "从订阅演员中移除一位（同步删除配置里的条目）",
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

    # ─── 豆瓣 Cookie 解析 ────────────────────────────────────────

    def _resolve_douban_cookie(self) -> str:
        """解析要带给豆瓣的 Cookie，按优先级：插件手填 → 宿主 CookieCloud → 无。

        为什么需要 Cookie：豆瓣对匿名请求用 ``403 need_login`` 做限流，实测搜索额度只有
        约 5 次／窗口；带上已登录 Cookie 后实测连续可用次数翻倍以上，且不再受出口 IP
        被拉黑的影响（额度绑定到账号）。

        解析结果缓存在内存中（``_COOKIE_TTL`` 秒），不落盘，避免持久化用户的登录态。
        """
        # 1) 插件里手填的 Cookie 优先级最高，且视为长期有效
        if self._douban_cookie:
            self._cookie_source = "manual"
            self._cookie_hint = ""
            return self._douban_cookie

        # 2) 复用宿主已配置的 CookieCloud（用户不必再手工复制一次 Cookie）
        now = time.time()
        if self._cookie_cached_at and now - self._cookie_cached_at < self._COOKIE_TTL:
            return self._cookie_cache

        host, key, password = self._cookiecloud_config()
        client = _CookieCloudClient(host, key, password)
        cookie = client.fetch("douban.com")
        self._cookie_cache = cookie
        self._cookie_cached_at = now
        if cookie:
            self._cookie_source = "cookiecloud"
            self._cookie_hint = ""
            logger.info(f"{PLUGIN_NAME} 已从宿主 CookieCloud 取到豆瓣 Cookie（长度 {len(cookie)}）")
        else:
            self._cookie_source = "none"
            self._cookie_hint = client.last_error
            logger.info(f"{PLUGIN_NAME} 未取得豆瓣 Cookie：{client.last_error}")
        return cookie

    @staticmethod
    def _cookiecloud_config() -> Tuple[str, str, str]:
        """读取 CookieCloud 配置：一律沿用宿主系统设置里的值。

        这三个键是宿主 ``ConfigModel`` 的字段（CookieCloud 设置页），插件只需读取，
        不重复提供一套配置，避免用户在两个地方各配一遍。
        """
        def _read(name: str) -> str:
            return str(getattr(settings, name, "") or "").strip()

        return (
            _read("COOKIECLOUD_HOST"),
            _read("COOKIECLOUD_KEY"),
            _read("COOKIECLOUD_PASSWORD"),
        )

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

        self._refreshing = True
        self._refresh_started_at = time.time()
        started = time.time()
        # 带上豆瓣 Cookie（手填或宿主 CookieCloud）：匿名额度只有约 5 次/窗口，
        # 登录态能显著提高搜索可用次数，是解析大量演员名称的前提。
        client = _DoubanClient(proxy=self._proxy, cookie=self._resolve_douban_cookie())
        previous = self._load_works()
        snapshot: Dict[str, Any] = {}
        errors: List[str] = []
        new_count = 0
        # 演员解析缓存由本轮统一读写，最后一次性落盘
        cache = self._load_actor_cache()
        cache_dirty = False
        # 豆瓣匿名搜索限流极严（实测约 5 次后 403）：一旦触发，本轮剩下的「尚未解析过」
        # 演员直接跳过，避免对着 100+ 个名字空打一遍必然失败的请求。
        # 已经解析出人物 ID 的演员不受影响（走详情/作品集接口，配额宽松且会快速恢复）。
        search_blocked = False
        skipped = 0
        # 搜索冷却记账：某位演员**成功搜索一次**后，24 小时内不再重复搜这个名字。
        # 失败不记账（限流是暂时的，要允许下一轮重试）。只作用于「按名称搜索」这一步。
        now_ts = time.time()
        search_log = self._load_search_log()
        search_log_dirty = False
        cooling = 0

        for key in self._actor_entries:
            need_search = not str((cache.get(key) or {}).get("id") or "").strip()
            last_search = search_log.get(key) if need_search else None
            if last_search and now_ts - last_search < _SEARCH_COOLDOWN_SECONDS:
                # 24 小时内已经为这位演员打过一次搜索接口，不再重复消耗额度
                cooling += 1
                hint = _search_cooldown_hint(_SEARCH_COOLDOWN_SECONDS - (now_ts - last_search))
                errors.append(f"{key}：{hint}")
                snapshot[key] = {
                    "actor": {
                        "key": key,
                        "id": "",
                        "name": key,
                        "resolved_from": "search",
                        "error": hint,
                        "retryable": True,
                    },
                    "works": [],
                }
                continue
            if need_search and search_blocked:
                skipped += 1
                errors.append(f"{key}：{client.failure_hint()}")
                snapshot[key] = {
                    "actor": {
                        "key": key,
                        "id": "",
                        "name": key,
                        "resolved_from": "search",
                        "error": client.failure_hint(),
                        "retryable": True,
                    },
                    "works": [],
                }
                continue
            search_calls_before = client.search_calls
            try:
                actor, works, cached, discovered = self._refresh_actor(client, key, previous, cache)
            except Exception as err:  # pragma: no cover - 单演员失败不影响其他演员
                logger.error(f"{self.plugin_name} 刷新演员「{key}」失败：{err}")
                errors.append(f"{key}：{err}")
                continue
            if need_search and client.search_calls > search_calls_before:
                # 记账规则：只有**搜索成功**（真的解析出了人物 ID）才进入 24 小时冷却。
                # 失败（限流 / need_login / 查无此人）不冷却 —— 限流只是暂时的，
                # 锁死一整天会让这些演员长期解析不出来，下轮重试才合理。
                if str(actor.get("id") or "").strip():
                    search_log[key] = time.time()
                    search_log_dirty = True
            cache_dirty = cache_dirty or cached
            if actor.get("error"):
                errors.append(f"{key}：{actor['error']}")
            group_key = str(actor.get("id") or key)
            snapshot[group_key] = {"actor": actor, "works": works}
            new_count += discovered
            if need_search and client.last_rate_limited:
                search_blocked = True
                logger.warning(f"{self.plugin_name} 豆瓣搜索已限流，本轮跳过剩余未解析的演员")

        if cache_dirty:
            self.save_data(self._DATA_ACTORS, cache)
        if search_log_dirty:
            self.save_data(self._DATA_SEARCH_LOG, search_log)
        self.save_data(self._DATA_WORKS, snapshot)

        subscribed: List[Dict[str, Any]] = []
        if self._auto_subscribe:
            subscribed = self._auto_subscribe_works(snapshot, previous, errors)

        elapsed_ms = int((time.time() - started) * 1000)
        self._run_count += 1
        self._last_run_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # 本次已产出最新快照，「等待补刷新」标记随之失效
        self._pending_refresh = False
        self.save_data(
            self._DATA_STATE,
            {"run_count": self._run_count, "last_run_at": self._last_run_at},
        )

        work_total = sum(len(group["works"]) for group in snapshot.values())
        # 「新作品」与面板同一口径（演员加入之后才出现的才算），
        # 「新收录」则包含刚建立基线的演员作品 —— 两者分开说，否则用户看到
        # 通知里「本次新发现 98 部」而面板显示「新作品 0 部」会以为插件坏了。
        fresh_total = sum(
            1
            for group in snapshot.values()
            if isinstance(group, dict)
            for work in (group.get("works") or [])
            if isinstance(work, dict) and work.get("is_new")
        )
        detail = (
            f"刷新 {len(snapshot)} 位演员、{work_total} 部作品，"
            f"新作品 {fresh_total} 部，自动订阅 {len(subscribed)} 部（{elapsed_ms} ms）"
        )
        if new_count:
            detail += f"，本次新收录 {new_count} 部（首次建立基线的作品不计入新作品）"
        if errors:
            detail += f"，{len(errors)} 项异常"
        if skipped:
            detail += f"，{skipped} 位因豆瓣限流顺延到下次"
        if cooling:
            detail += f"，{cooling} 位搜索冷却中（24 小时内已搜过）"
        self._refreshing = False
        logger.info(f"{self.plugin_name} 任务完成（{trigger}）：{detail}")

        if self._notify:
            self._send_notify(detail, subscribed, errors)
        return True

    def _is_refreshing(self) -> bool:
        """后台刷新是否仍在进行（带超时兜底，避免标记永久卡住）。"""
        if not self._refreshing:
            return False
        if self._REFRESH_STALE_SECONDS and self._refresh_started_at:
            if time.time() - self._refresh_started_at > self._REFRESH_STALE_SECONDS:
                self._refreshing = False
                return False
        return True

    def get_works_payload(self) -> Dict[str, Any]:
        """组装面板所需的完整数据（演员 + 作品 + 统计）。"""
        snapshot = self._load_works()
        ignored = self._load_ignored()
        actors: List[Dict[str, Any]] = []
        new_count = 0
        new_actor_count = 0
        now = time.time()
        for group in snapshot.values():
            if not isinstance(group, dict):
                continue
            actor = dict(group.get("actor") or {})
            # 被忽略的作品不参与展示与统计；数据仍留在快照里，随时可以恢复
            visible = [
                work
                for work in (group.get("works") or [])
                if self._work_unique(work) not in ignored
            ]
            # 「新」全部现算：作品看「演员加入之后才出现 + 未过期」，演员看「加入未过期」。
            # 读旧快照也不会显示过期标记，口径与刷新落盘时完全一致。
            new_count += self._apply_new_flags(visible, _parse_ts(actor.get("baseline_at")))
            actor["is_new"] = self._is_fresh_actor(actor, now)
            new_actor_count += 1 if actor["is_new"] else 0
            # 同理：张冠李戴的判定也现算，旧缓存里的记录才会被标出来
            actor["fuzzy"] = self._is_fuzzy_actor(actor)
            actor["works"] = visible
            actors.append(actor)
        actors.sort(key=lambda item: str(item.get("name") or ""))
        total = sum(len(item["works"]) for item in actors)
        search_log = self._load_search_log()
        # 解析进度统计：只把「还没拿到人物 ID」的演员算作待解析。
        # 注意必须与搜索缓存取交集 —— 一旦某位演员解析出 ID，它这轮和下轮都不会再
        # 搜索，把它的历史搜索记录继续算成「冷却中」会让徽标显示一个只涨不降的假数字
        # （搜索记录要满 24 小时才过期，看起来就像永远不动）。
        cache = self._load_actor_cache()
        unresolved = [
            key
            for key in self._actor_entries
            if not str((cache.get(key) or {}).get("id") or "").strip()
        ]
        cooling = [key for key in unresolved if search_log.get(key)]
        return {
            "enabled": self._enabled,
            "updated_at": self._last_run_at,
            "run_count": self._run_count,
            "actor_count": len(self._actor_entries),
            "work_count": total,
            "new_count": new_count,
            # 近窗口内加入的演员数：作品不再逐张标新，新演员的规模改成这个数来体现，
            # 面板统计卡会把「近 N 天新增 演员 x / 作品 y」一起写出来。
            "new_actor_count": new_actor_count,
            # 「新」的口径：演员自加入、作品自在演员加入之后出现起，不超过这个天数。
            # 面板据此把口径写进统计卡，免得用户看到 0 或一个很大的数时无从判断是不是坏了。
            "new_window_days": _NEW_WINDOW_DAYS,
            "auto_subscribe": self._auto_subscribe,
            "auto_only_new": self._auto_only_new,
            "auto_min_vote": self._auto_min_vote,
            "auto_types": list(self._auto_types),
            "auto_subscribed": self._load_sub_history()[:50],
            "errors": self._load_errors(),
            "actors": actors,
            # 订阅偏好与「配置已变更待补刷新」「后台刷新中」标记，供面板回显与轮询
            "subscribe_save_path": self._subscribe_save_path,
            "subscribe_downloader": self._subscribe_downloader,
            "subscribe_sites": list(self._subscribe_sites),
            "pending_refresh": bool(self._pending_refresh),
            "refreshing": self._is_refreshing(),
            # 豆瓣 Cookie 来源，供面板显示「是不是靠登录态在提额度」
            "douban_cookie_source": self._cookie_source,
            "douban_cookie_hint": self._cookie_hint,
            # 尚未解析出人物 ID 的演员数（0 表示全部解析完毕，之后刷新不再消耗搜索额度）
            "unresolved_count": len(unresolved),
            # 其中仍处于 24 小时搜索冷却内、必须等冷却结束才会重试的数量
            "search_cooldown_count": len(cooling),
            # 被用户忽略的作品：面板据此显示「已忽略 N 部」并提供恢复入口
            "ignored_count": len(ignored),
            "ignored": self._ignored_list(ignored),
        }

    # ─── 业务逻辑：演员解析与作品抓取 ────────────────────────────

    @staticmethod
    def _is_fresh_work(work: Dict[str, Any], now: float, baseline_at: float = 0.0) -> bool:
        """作品是否属于「后来才出现的新作品」。

        两个条件缺一不可：

        1. 首次出现在**基线之后**（``first_seen`` > ``baseline_at``）——
           演员加入时就存在的作品属于基线，永远不算新，哪怕它是刚刚才从豆瓣抓回来的；
        2. 首次出现距今在 ``_NEW_WINDOW_SECONDS`` 之内 —— 时间窗负责让「新」自然过期。

        没有 first_seen（历史快照或字段缺失）时按「不新」处理，
        避免把来源不明的旧数据当成新作品推给自动订阅。

        :param baseline_at: 该演员建立基线的时刻（epoch 秒）；为 0 表示未知（升级前写入、
            尚未刷新过的旧快照），此时只按时间窗判定，宁可多标也不漏标。
        """
        first_seen = _parse_ts(work.get("first_seen"))
        if not first_seen:
            return False
        if baseline_at and first_seen <= baseline_at:
            return False
        return (now - first_seen) <= _NEW_WINDOW_SECONDS

    @staticmethod
    def _is_fresh_actor(actor: Dict[str, Any], now: float) -> bool:
        """演员是否属于「最近加入」——``joined_at`` 在 ``_NEW_WINDOW_SECONDS`` 之内。

        只用来在演员 chip 上标「新」：作品不再逐张标新（见 ``_is_fresh_work``），
        刚加进来的演员得靠这个标记才找得到。

        ``joined_at`` 只在**真正新加入**（本轮之前解析缓存里查无此人）时才写，
        因此升级前就在订阅列表里的老演员不会被误标 —— 他们的加入时间不可考，
        宁可什么都不标，也不要一次性把上百位演员都标成「新」。
        """
        joined_at = _parse_ts(actor.get("joined_at"))
        if not joined_at:
            return False
        return (now - joined_at) <= _NEW_WINDOW_SECONDS

    @staticmethod
    def _is_fuzzy_actor(actor: Dict[str, Any]) -> bool:
        """演员是否属于「按最接近的搜索结果」解析出来的（配置名 ≠ 豆瓣名）。

        以「来源是名称搜索 且 配置名与豆瓣名不一致」现算，而不是只看解析时记下的
        ``fuzzy``：字段出现之前写入的旧缓存同样存在张冠李戴，只有展示时现算才能
        把历史遗留的一并暴露出来（实测实例上有 8 位：宋星颐→宋星翰、任绵绵→林绵绵…）。

        直接填人物 ID 的配置名是「1025229」这类数字，与豆瓣名天然不同，
        因此必须用 ``resolved_from`` 先排除掉。
        """
        if str(actor.get("resolved_from") or "") != "search":
            return False
        key = str(actor.get("key") or "").strip()
        name = str(actor.get("name") or "").strip()
        return bool(key) and bool(name) and key != name

    def _apply_new_flags(self, works: List[Dict[str, Any]], baseline_at: float = 0.0) -> int:
        """按「基线时刻 + 时间窗」就地重算 ``is_new``，返回其中新作品的数量。

        所有对外输出作品的地方（刷新落盘、面板载荷、仪表板统计）都过这一手，
        保证「新」的口径只有一个，也不会因为读到旧快照而显示过期标记。

        :param baseline_at: 该批作品所属演员的基线时刻（epoch 秒），0 表示未知。
        """
        now = time.time()
        fresh = 0
        for work in works:
            if not isinstance(work, dict):
                continue
            flag = self._is_fresh_work(work, now, baseline_at)
            work["is_new"] = flag
            fresh += 1 if flag else 0
        return fresh

    def _refresh_actor(
        self,
        client: "_DoubanClient",
        key: str,
        previous: Dict[str, Any],
        cache: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]], bool, int]:
        """解析（必要时搜索）演员并抓取其最新作品。

        :param cache: 共享的演员解析缓存，由调用方统一读写，
            避免每位演员都落盘一次（112 位演员会变成 112 次写库）。
        :return: ``(演员信息, 作品列表, 缓存是否有更新, 本次首次收录的作品数)``
        """
        # 本轮统一的时间戳：同一轮里建立的基线与基线作品的 first_seen 都取它，
        # 于是基线作品的 first_seen == baseline_at，天然不会被判成「新作品」。
        now = datetime.now().strftime(_TS_FORMAT)
        cached = cache.get(key)
        actor: Dict[str, Any] = dict(cached) if isinstance(cached, dict) else {}
        # 是否「真正新加入」：本轮之前解析缓存里查无此人。只有这种演员才会拿到
        # joined_at（chip 标「新」）；升级前就在列表里的老演员查得到缓存，加入时间
        # 不可考，宁可什么都不标，也不要一次性把上百位演员都标成「新」。
        first_sight = not actor
        actor.pop("added_at", None)  # v1.12.0 中间版本的字段，语义已拆分为下面两个
        # 基线时刻：首次见到这位演员时写死，之后不再变 ——
        # 它是「加入前就有的老作品」与「加入之后才出现的作品」的分界线。
        baseline_at = str(actor.get("baseline_at") or "").strip() or now
        actor_id = str(actor.get("id") or "").strip()
        if not actor_id:
            actor = self._resolve_actor(client, key)
            actor_id = str(actor.get("id") or "").strip()
            actor.pop("added_at", None)
        if first_sight and not str(actor.get("joined_at") or "").strip():
            actor["joined_at"] = now
        actor["baseline_at"] = baseline_at

        cache_dirty = False
        # 每次刷新都取一次人物详情：既刷新头像/简介，也拿到最新的作品集 ID
        detail = client.person_detail(actor_id) if actor_id else None
        if detail:
            actor = {**actor, **self._actor_from_detail(actor_id, detail, key)}
            actor.pop("retryable", None)
        elif actor_id and client.last_rate_limited:
            # 详情接口的限流窗口很短，退避重试后仍失败就如实上报，
            # 不要把它伪装成「未找到该演员的豆瓣影视作品集」。
            actor["error"] = client.failure_hint()
            actor["retryable"] = True
            # 关键：ID 已经解析出来了，即使详情这次被限流也要把 ID 落缓存。
            # 否则下一轮会为一个**已经解析好**的演员再花一次宝贵的搜索额度。
            cache[key] = {k: v for k, v in actor.items() if k not in ("works", "retryable")}
            return actor, [], True, 0

        if actor_id and not actor.get("error"):
            cache[key] = {k: v for k, v in actor.items() if k not in ("works", "retryable")}
            cache_dirty = True

        collection_id = self._work_collection_id(detail) if detail else None
        if not collection_id:
            if not actor.get("error"):
                actor["error"] = "未找到该演员的豆瓣影视作品集"
            return actor, [], cache_dirty, 0

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

        # 继承首次出现时间（只在真正第一次见到时才写 now），
        # 「是否新作品」另由 first_seen 与基线时刻的比较决定，见 _apply_new_flags
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
        discovered = 0
        for work in works:
            first_seen = seen.get(work["media_id"])
            if first_seen:
                work["first_seen"] = first_seen
            else:
                work["first_seen"] = now
                discovered += 1
        self._apply_new_flags(works, _parse_ts(baseline_at))
        return actor, works, cache_dirty, discovered

    @staticmethod
    def _extract_person_id(value: str) -> str:
        """从配置项里提取豆瓣人物 ID，提取不到时返回空串。

        支持三种写法，方便用户直接从浏览器地址栏复制：
        ``37871253``、``https://www.douban.com/personage/37871253/``、
        ``https://movie.douban.com/celebrity/1025229/``。
        直接给 ID/链接可完全绕开豆瓣的匿名搜索限流。
        """
        text = str(value or "").strip()
        if not text:
            return ""
        if text.isdigit():
            return text
        matched = _PERSON_URL_PATTERN.search(text)
        return matched.group(1) if matched else ""

    def _resolve_actor(self, client: "_DoubanClient", key: str) -> Dict[str, Any]:
        """把配置项解析为豆瓣人物：人物 ID/主页链接直接采用，否则按名称搜索。"""
        person_id = self._extract_person_id(key)
        if person_id:
            return {"key": key, "id": person_id, "name": key, "resolved_from": "id", "error": None}

        candidates = client.search_person(key)
        if not candidates:
            # 关键：必须区分「被限流/请求失败」与「确实搜不到这个人」。
            # 早期版本把限流也报成「未搜索到该演员」，会误导用户去改配置，
            # 而真实原因是豆瓣匿名搜索配额用尽（实测约 5 次后 403 need_login）。
            if client.last_rate_limited:
                return {
                    "key": key,
                    "id": "",
                    "name": key,
                    "resolved_from": "search",
                    "error": client.failure_hint(),
                    "retryable": True,
                }
            if client.last_error:
                return {
                    "key": key,
                    "id": "",
                    "name": key,
                    "resolved_from": "search",
                    "error": f"豆瓣搜索失败：{client.last_error}",
                    "retryable": True,
                }
            return {
                "key": key,
                "id": "",
                "name": key,
                "resolved_from": "search",
                "error": "豆瓣未搜索到该演员，请改用人物 ID",
            }
        exact = next((item for item in candidates if item.get("name") == key), None)
        matched = exact or candidates[0]
        # 没有同名条目时退回最接近的搜索结果 —— 但必须把这个事实记下来。
        # 豆瓣的人物搜索是模糊匹配：配置「宋星颐」会返回「宋星翰 / 宋星成 / 宋星辰…」，
        # 静默取第一个会让面板上冒出一个用户从没填过的名字（作品也是别人的），
        # 用户只会觉得「我加的演员没生效」。记下 fuzzy 与候选名后，
        # 面板会显式提示「配置名 ↔ 实际解析到的名字」，由用户决定是否改用人物 ID。
        fuzzy = exact is None
        return {
            "key": key,
            "id": str(matched.get("id") or ""),
            "name": _clean_text(matched.get("name")) or key,
            "avatar": matched.get("avatar"),
            "resolved_from": "search",
            "fuzzy": fuzzy,
            "candidates": (
                [str(c.get("name")) for c in candidates[:5] if c.get("name")] if fuzzy else []
            ),
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
        # 被用户忽略的作品不自动订阅：忽略的语义就是「别再管它」
        ignored = self._load_ignored()
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
                if unique in seen or unique in ignored:
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
        """把单个作品提交给 MoviePilot 订阅链；返回 ``(是否成功, 说明)``。

        未播出 / 信息尚未收录的影视会被订阅链以「缺季集信息」拒掉。这类失败不是
        「这部作品有问题」而是「信息还没到」，因此会自动降级为「预订」
        （见 :meth:`_reserve_subscribe`），等影视播出、信息补全后照常参与搜索。
        """
        title = str(work.get("title") or "").strip()
        media_id = str(work.get("media_id") or "").strip()
        if not title or not media_id:
            return False, "标题或豆瓣 ID 为空"
        mtype = MediaType(work["type"]) if work.get("type") in _SUBSCRIBABLE_TYPES else None
        meta: Optional[MetaInfo] = None
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
                # 订阅偏好：留空时交给宿主按系统默认配置补全
                save_path=self._subscribe_save_path or None,
                downloader=self._subscribe_downloader or None,
                sites=list(self._subscribe_sites) or None,
            )
            if sid:
                return True, f"订阅成功（ID {sid}）"
            first_message = str(message or "订阅链未返回订阅 ID")
        except Exception as err:
            first_message = str(err)

        # 缺季集信息 / 未识别到媒体信息 → 降级为「预订」，而不是判失败
        if not _looks_like_missing_info(first_message):
            return False, first_message
        ok, reserve_message = self._reserve_subscribe(work, meta, mtype, first_message)
        if ok:
            return True, reserve_message
        if reserve_message:
            return False, f"{first_message}（转为预订也失败：{reserve_message}）"
        return False, first_message

    @staticmethod
    def _reserve_prefs(prefs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """解析预订用的订阅偏好；未提供的位置留空，由调用方回落到插件配置。"""
        data = prefs or {}
        raw_path = data.get("save_path")
        save_path = str(raw_path).strip() if isinstance(raw_path, str) else ""
        # 下载器名称：留空表示跟随宿主默认，非字符串输入直接忽略
        raw_downloader = data.get("downloader")
        downloader = raw_downloader.strip() if isinstance(raw_downloader, str) else ""
        sites: List[int] = []
        raw_sites = data.get("sites")
        if isinstance(raw_sites, (list, tuple)):
            for item in raw_sites:
                text = str(item).strip()
                if text.isdigit():
                    sites.append(int(text))
        return {"save_path": save_path, "downloader": downloader, "sites": sites}

    def _reserve_subscribe(
        self,
        work: Dict[str, Any],
        meta: Optional[MetaInfo],
        mtype: Optional[MediaType],
        reason: str,
        prefs: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str]:
        """把订阅失败的作品降级为「预订」：状态置为待定（P）。

        未播出 / 豆瓣条目才建时，订阅链拿不到季集信息会直接拒绝创建订阅，而这类作品
        恰恰最需要先占位，因此分两步兜底：

        1. 仍走官方订阅链，但补一个占位总集数跳过季集补齐，并把状态置为 ``P``；
        2. 连识别都过不去（TMDB 还没收录）时，直接按豆瓣身份落一条待定订阅。

        ``P``（待定）语义是「允许搜索、不允许完成」：不会在资源出现前被误判为已看完，
        也不会漏掉后续资源；宿主刷新到真实集数时会自动向上覆盖占位值。
        """
        if mtype is None and work.get("type") in _SUBSCRIBABLE_TYPES:
            mtype = MediaType(work["type"])
        if mtype is None:
            return False, ""
        title = str(work.get("title") or "").strip()
        media_id = str(work.get("media_id") or "").strip()
        if not title or not media_id:
            return False, "标题或豆瓣 ID 为空"
        source = str(work.get("media_source") or MediaSource.Douban.value)
        try:
            source_enum = MediaSource(source)
        except ValueError:  # pragma: no cover - 宿主枚举差异兜底
            source_enum = MediaSource.Douban
        effective = self._reserve_prefs(prefs)
        save_path = effective["save_path"] or self._subscribe_save_path or None
        downloader = effective["downloader"] or self._subscribe_downloader or None
        sites = effective["sites"] or list(self._subscribe_sites) or None

        is_tv = mtype == MediaType.TV
        season: Optional[int] = None
        if is_tv:
            begin = getattr(meta, "begin_season", None) if meta is not None else None
            season = int(begin) if isinstance(begin, int) and begin > 0 else 1

        # 一级兜底：正规订阅链路 + 占位季集 + 待定状态
        sid = 0
        message = ""
        try:
            sid, message = SubscribeChain().add(
                title=title,
                year=str(work.get("year") or ""),
                mtype=mtype,
                media_source=source_enum,
                media_id=media_id,
                exist_ok=True,
                username=PLUGIN_NAME,
                state=_SUBSCRIBE_STATE_PENDING,
                save_path=save_path,
                downloader=downloader,
                sites=sites,
                **(dict(season=season, total_episode=_RESERVE_TOTAL_EPISODE) if is_tv else {}),
            )
        except Exception as err:
            sid, message = 0, str(err)
        if sid:
            self._ensure_pending_state(int(sid))
            logger.info(f"{self.plugin_name} 「{title}」订阅失败已转为预订（ID {sid}）：{reason}")
            return True, f"已按「预订」提交（待定，ID {sid}）"
        # 二级兜底：识别链都过不去（尚未收录）→ 直接落一条待定订阅占位
        return self._reserve_subscribe_directly(
            work, mtype, season, reason, str(message or ""), save_path, downloader, sites
        )

    def _reserve_subscribe_directly(
        self,
        work: Dict[str, Any],
        mtype: MediaType,
        season: Optional[int],
        reason: str,
        chain_error: str,
        save_path: Optional[str],
        downloader: Optional[str],
        sites: Optional[List[int]],
    ) -> Tuple[bool, str]:
        """连识别都失败时，按豆瓣身份直接写一条待定订阅（预订占位）。

        订阅链必须先识别出媒体信息才会创建订阅，未播出、TMDB 尚未收录的作品过不了
        这一步 —— 而这正是最需要预订的情况。这里绕过识别直接写库：身份用豆瓣
        ``media_id``，状态 P，集数留占位值，等宿主刷新到真实信息后照常参与搜索。
        """
        oper = _subscribe_oper()
        if oper is None:
            return False, chain_error or "宿主未提供订阅写库接口"
        title = str(work.get("title") or "").strip()
        media_id = str(work.get("media_id") or "").strip()
        source = str(work.get("media_source") or MediaSource.Douban.value)
        is_tv = mtype == MediaType.TV
        identity = {
            "media_source": source,
            "media_id": media_id,
            "music_type": None,
            "season": season if is_tv else None,
            "episode_group": None,
        }
        payload: Dict[str, Any] = {
            "name": title,
            "year": str(work.get("year") or ""),
            "type": mtype.value,
            "media_source": source,
            "media_id": media_id,
            "season": season if is_tv else None,
            "state": _SUBSCRIBE_STATE_PENDING,
            "username": PLUGIN_NAME,
        }
        if is_tv:
            payload["total_episode"] = _RESERVE_TOTAL_EPISODE
            payload["lack_episode"] = _RESERVE_TOTAL_EPISODE
        poster = str(work.get("poster") or "").strip()
        if poster:
            payload["poster"] = poster
        subtitle = str(work.get("subtitle") or "").strip()
        if subtitle:
            payload["description"] = subtitle
        try:
            vote = float(work.get("vote") or 0)
        except (TypeError, ValueError):
            vote = 0.0
        if vote:
            payload["vote"] = vote
        if save_path:
            payload["save_path"] = save_path
        if downloader:
            payload["downloader"] = downloader
        if sites:
            payload["sites"] = list(sites)
        try:
            sid, message = oper.add(identity=identity, payload=payload, username=PLUGIN_NAME)
        except Exception as err:
            return False, str(err)
        if not sid:
            return False, str(message or chain_error or "预订写入失败")
        self._ensure_pending_state(int(sid))
        logger.info(f"{self.plugin_name} 「{title}」已直接落库为预订（ID {sid}）：{reason}")
        return True, f"已按「预订」提交（待定，ID {sid}）"

    @staticmethod
    def _ensure_pending_state(subscribe_id: int) -> None:
        """回读订阅并把状态校正为待定（P）。

        创建路径会带宿主自己的默认状态，个别版本可能忽略调用方传入的 ``state``；
        这里回读一次并补写，保证「预订」语义真的落地（待定：允许搜索、不允许完成）。
        """
        oper = _subscribe_oper()
        if oper is None:
            return
        try:
            row = oper.get(subscribe_id)
            if row is not None and str(getattr(row, "state", "") or "") == _SUBSCRIBE_STATE_PENDING:
                return
            oper.update(subscribe_id, {"state": _SUBSCRIBE_STATE_PENDING})
        except Exception as err:  # pragma: no cover - 宿主版本差异兜底
            logger.debug(f"{PLUGIN_NAME} 校正预订状态时跳过：{err}")

    # ─── 数据读写 ────────────────────────────────────────────────

    def _load_works(self) -> Dict[str, Any]:
        data = self.get_data(self._DATA_WORKS)
        return data if isinstance(data, dict) else {}

    def _load_actor_cache(self) -> Dict[str, Any]:
        data = self.get_data(self._DATA_ACTORS)
        return data if isinstance(data, dict) else {}

    def _load_search_log(self) -> Dict[str, float]:
        """读取「演员 → 最近一次真实搜索时间」的记账表。

        只保留仍在 24 小时冷却窗口内的记录：过期的没有意义，顺手清掉，
        避免这份数据随着时间无限增长。时间戳存成 float（epoch 秒）。
        """
        data = self.get_data(self._DATA_SEARCH_LOG)
        if not isinstance(data, dict):
            return {}
        threshold = time.time() - _SEARCH_COOLDOWN_SECONDS
        cleaned: Dict[str, float] = {}
        for key, value in data.items():
            try:
                ts = float(value)
            except (TypeError, ValueError):
                continue
            if ts > threshold:
                cleaned[str(key)] = ts
        return cleaned

    def _load_sub_history(self) -> List[Dict[str, Any]]:
        data = self.get_data(self._DATA_SUBS)
        return list(data) if isinstance(data, list) else []

    # ─── 被忽略作品 ──────────────────────────────────────────────

    @staticmethod
    def _work_unique(work: Dict[str, Any]) -> str:
        """作品的唯一键，必须与前端 ``workKey()`` 完全一致。"""
        return f"{work.get('media_source')}:{work.get('media_id')}"

    def _load_ignored(self) -> Dict[str, Any]:
        """读取「被忽略作品」记账表，键为 ``media_source:media_id``。"""
        data = self.get_data(self._DATA_IGNORED)
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _ignored_list(ignored: Dict[str, Any]) -> List[Dict[str, Any]]:
        """把忽略记账整理成列表（按忽略时间倒序），供面板展示与恢复。"""
        rows: List[Dict[str, Any]] = []
        for key, value in ignored.items():
            item = dict(value) if isinstance(value, dict) else {}
            item["key"] = key
            if ":" in str(key):
                source, _, media_id = str(key).partition(":")
                item.setdefault("media_source", source)
                item.setdefault("media_id", media_id)
            rows.append(item)
        rows.sort(key=lambda row: str(row.get("time") or ""), reverse=True)
        return rows[:200]

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

    def _count_works(self) -> Tuple[int, int, int]:
        """统计 ``(作品总数, 新作品数, 新演员数)``，口径与面板载荷完全一致。"""
        snapshot = self._load_works()
        now = time.time()
        total = 0
        new_count = 0
        new_actor_count = 0
        for group in snapshot.values():
            if not isinstance(group, dict):
                continue
            actor = group.get("actor") or {}
            if not isinstance(actor, dict):
                actor = {}
            works = [item for item in (group.get("works") or []) if isinstance(item, dict)]
            total += len(works)
            # 与面板同一套口径：现算，而不是读落盘时的旧标记
            new_count += self._apply_new_flags(works, _parse_ts(actor.get("baseline_at")))
            new_actor_count += 1 if self._is_fresh_actor(actor, now) else 0
        return total, new_count, new_actor_count

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

    def _add_once_job(
        self, job_id: str = _ONCE_JOB_ID, delay_seconds: float = 3, trigger: str = "once"
    ) -> bool:
        """向宿主调度器登记一次性任务，返回是否登记成功。

        注意 ``add_plugin_once_job`` 的关键字参数名是 ``func_kwargs``（不是 ``kwargs``），
        传错会被它自己的 try/except 吞掉并只留下一条错误日志。
        """
        try:
            from app.sdk import scheduler as scheduler_sdk

            add_once = getattr(scheduler_sdk, "add_plugin_once_job", None)
            if not add_once:
                logger.warning(f"{self.plugin_name} 当前宿主不支持一次性任务接口")
                return False
            add_once(
                self.__class__.__name__,
                job_id,
                self.execute_task,
                f"{self.plugin_name}延迟刷新",
                delay_seconds=delay_seconds,
                func_kwargs={"trigger": trigger},
            )
            return True
        except Exception as err:  # pragma: no cover - 宿主版本差异兜底
            logger.warning(f"{self.plugin_name} 登记一次性任务失败：{err}")
            return False

    # ─── 插件 API 实现 ───────────────────────────────────────────

    def _config_snapshot(self) -> Dict[str, Any]:
        """组装当前运行时配置（不含响应外壳）。

        单独抽出是为了让 ``api_get_config`` 的响应壳与持久化用的配置体解耦：
        宿主不会为插件动态路由套 ``Response[T]``，因此插件自己的接口必须
        自行返回 ``{success, data}``（与 ``api_get_works`` 等保持一致），
        但落盘/合并时只能用裸配置，不能把外壳写进配置。
        """
        return {
            "enabled": self._enabled,
            "sidebar_nav": self._sidebar_nav,
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
            "subscribe_save_path": self._subscribe_save_path,
            "subscribe_downloader": self._subscribe_downloader,
            "subscribe_sites": list(self._subscribe_sites),
            "douban_cookie": self._douban_cookie,
            "douban_cookie_source": self._cookie_source,
            "douban_cookie_hint": self._cookie_hint,
            "pending_refresh": bool(self._pending_refresh),
            "refreshing": self._is_refreshing(),
            "run_count": self._run_count,
        }

    def api_get_config(self) -> Dict[str, Any]:
        """返回当前运行时配置，供前端 Config 组件回显。"""
        return {"success": True, "data": self._config_snapshot()}

    def api_update_config(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """接收前端提交的配置，持久化后重新初始化插件。"""
        if not config or not isinstance(config, dict):
            return {"success": False, "message": "请求体不是合法对象"}

        merged = {**self._config_snapshot(), **config}
        merged["enabled"] = bool(merged.get("enabled"))
        merged["sidebar_nav"] = bool(merged.get("sidebar_nav", True))
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
        merged["subscribe_save_path"] = str(merged.get("subscribe_save_path") or "").strip()
        merged["subscribe_downloader"] = str(merged.get("subscribe_downloader") or "").strip()
        merged["subscribe_sites"] = self._parse_sites(merged.get("subscribe_sites"))
        merged["douban_cookie"] = str(merged.get("douban_cookie") or "").strip()
        # run_count / pending_refresh / refreshing / Cookie 来源属于运行时状态，不落盘
        merged.pop("run_count", None)
        merged.pop("pending_refresh", None)
        merged.pop("refreshing", None)
        merged.pop("douban_cookie_source", None)
        merged.pop("douban_cookie_hint", None)

        if not self.update_config(merged):
            return {"success": False, "message": "配置持久化失败"}

        self.init_plugin(merged)
        return {"success": True, "data": self._config_snapshot()}

    def api_get_works(self) -> Dict[str, Any]:
        """返回演员与作品快照，供前端面板渲染。"""
        return {"success": True, "data": self.get_works_payload()}

    def api_run(self) -> Dict[str, Any]:
        """手动刷新一次。

        演员多时（一次刷新可能上百个请求、持续数分钟）不能在 HTTP 请求里同步跑完，
        否则前端会先超时并报错。这里改为交给宿主调度器立即后台执行，
        前端依据 ``refreshing`` 标记轮询结果。
        """
        if not self.get_state() or not self._actor_entries:
            return {
                "success": False,
                "message": "刷新失败（插件未启用或未配置演员）",
                "data": self.get_works_payload(),
            }
        if self._refreshing:
            return {
                "success": True,
                "message": "刷新已在进行中",
                "data": self.get_works_payload(),
            }
        if not self._add_once_job(self._MANUAL_JOB_ID, 0, "manual"):
            # 宿主不支持一次性任务时退回同步执行
            ok = self.execute_task(trigger="api")
            return {
                "success": ok,
                "message": "刷新完成" if ok else "刷新失败（插件未启用或未配置演员）",
                "data": self.get_works_payload(),
            }
        self._refreshing = True
        self._refresh_started_at = time.time()
        logger.info(f"{self.plugin_name} 已安排后台刷新，共 {len(self._actor_entries)} 位演员")
        return {
            "success": True,
            "message": f"已在后台开始刷新 {len(self._actor_entries)} 位演员的作品",
            "data": self.get_works_payload(),
        }

    def api_search_actor(self, name: str = "") -> Dict[str, Any]:
        """按名称搜索豆瓣演员，供配置页辅助确定人物 ID。"""
        keyword = str(name or "").strip()
        if not keyword:
            return {"success": False, "message": "请提供演员名称"}
        # 直接粘贴人物 ID / 主页链接时无需搜索，避免占用本就紧张的搜索配额
        person_id = self._extract_person_id(keyword)
        if person_id:
            return {
                "success": True,
                "data": [{"id": person_id, "name": keyword, "avatar": None, "url": None}],
                "message": "已按人物 ID 解析",
            }
        client = _DoubanClient(proxy=self._proxy, cookie=self._resolve_douban_cookie())
        try:
            results = client.search_person(keyword)
        except Exception as err:
            return {"success": False, "message": f"搜索失败：{err}"}
        if not results:
            # 同样是空结果，原因不同：限流要提示稍后重试，而不是让用户误以为没有这个人
            if client.last_rate_limited:
                return {"success": False, "message": client.failure_hint(), "rate_limited": True}
            if client.last_error:
                return {"success": False, "message": f"搜索失败：{client.last_error}"}
        return {"success": True, "data": results}

    def api_reserve(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """把「订阅失败的作品」降级为预订（待定 P），供面板兜底。

        面板上的订阅按钮直接调宿主原生 ``POST subscribe/``（这样订阅归属当前登录用户），
        而宿主接口不接受创建时指定状态，也不允许绕过季集识别，所以未播出 / 尚未收录的
        作品在那里一定会失败。前端拿到这类失败后会回落到本接口，由插件按豆瓣身份
        建一条待定订阅占位。
        """
        data = payload if isinstance(payload, dict) else {}
        title = str(data.get("title") or "").strip()
        media_id = str(data.get("media_id") or "").strip()
        if not title or not media_id:
            return {"success": False, "message": "缺少作品标题或豆瓣 ID"}
        work: Dict[str, Any] = {
            "title": title,
            "year": str(data.get("year") or ""),
            "type": str(data.get("type") or ""),
            "media_source": str(data.get("media_source") or MediaSource.Douban.value),
            "media_id": media_id,
            "poster": str(data.get("poster") or ""),
            "subtitle": str(data.get("subtitle") or ""),
            "vote": data.get("vote") or 0,
        }
        mtype = MediaType(work["type"]) if work["type"] in _SUBSCRIBABLE_TYPES else None
        if mtype is None:
            return {"success": False, "message": "该作品类型不支持订阅"}
        meta = MetaInfo(title)
        if work["year"]:
            meta.year = work["year"]
        meta.type = mtype
        prefs = {
            "save_path": data.get("save_path"),
            "downloader": data.get("downloader"),
            "sites": data.get("sites"),
        }
        ok, message = self._reserve_subscribe(work, meta, mtype, "面板订阅未成功", prefs)
        if not ok:
            return {"success": False, "message": message or "转为预订失败"}
        return {"success": True, "message": message, "data": {"title": title}}

    def api_unsubscribe(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """取消一部作品的订阅：作品卡片上「已订阅」按钮的二次点击。

        粒度和「订阅」按钮保持一致 —— 用户点的是**这一部作品**，因此按豆瓣身份
        （``media_source`` + ``media_id``，可带 ``season``）把所有对得上的订阅记录删掉，
        而不是让前端拼一串 media_id/season 去逐个调宿主接口。

        找不到记录时返回失败而不是「已取消」：否则界面会把「查询出错」渲染成
        「取消成功」，下次刷新又冒出「已订阅」，比直接报错更让人困惑。
        """
        data = payload if isinstance(payload, dict) else {}
        media_id = str(data.get("media_id") or "").strip()
        if not media_id:
            return {"success": False, "message": "缺少豆瓣 ID"}
        source_text = str(data.get("media_source") or MediaSource.Douban.value).strip()
        try:
            source = MediaSource(source_text or MediaSource.Douban.value)
        except Exception:  # pragma: no cover - 宿主枚举实现差异，非法值一律挡回
            return {"success": False, "message": f"未知的媒体来源：{source_text}"}

        oper = _subscribe_oper()
        if oper is None:
            return {"success": False, "message": "宿主未提供订阅入口，无法取消订阅"}
        try:
            records = oper.list_by_media_identity(source, media_id) or []
        except Exception as err:  # pragma: no cover - 宿主版本差异兜底
            logger.warning(f"{self.plugin_name} 取消订阅时查询失败：{err}")
            return {"success": False, "message": f"查询订阅失败：{err}"}

        # 可选按季收窄：同一部剧存在整季订阅时，面板给得出季就只删那一季
        season = data.get("season")
        if isinstance(season, int):
            matched = [item for item in records if getattr(item, "season", None) == season]
            if matched:
                records = matched
        if not records:
            return {"success": False, "message": "未找到该作品的订阅（可能已被删除）"}

        removed = 0
        failures: List[str] = []
        for record in records:
            sid = getattr(record, "id", None)
            if sid is None:  # pragma: no cover - 宿主记录必带主键
                continue
            try:
                oper.delete(int(sid))
                removed += 1
            except Exception as err:  # pragma: no cover - 宿主版本差异兜底
                failures.append(str(err))
        if not removed:
            detail = failures[0] if failures else "未知原因"
            return {"success": False, "message": f"取消订阅失败：{detail}"}

        title = str(data.get("title") or "").strip() or media_id
        logger.info(f"{self.plugin_name} 已取消订阅：{title}（{removed} 条）")
        return {
            "success": True,
            "message": f"已取消订阅「{title}」",
            "data": {"removed": removed},
        }

    def api_ignore(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """忽略一部作品：面板不再展示，自动订阅也会跳过它。

        只记「作品身份」而不是从快照里删除数据 —— 这样随时可以恢复，
        下次刷新也不会因为作品重新出现而把忽略状态丢掉。
        """
        data = payload if isinstance(payload, dict) else {}
        media_id = str(data.get("media_id") or "").strip()
        if not media_id:
            return {"success": False, "message": "缺少 media_id"}
        source = str(data.get("media_source") or "douban").strip() or "douban"
        key = f"{source}:{media_id}"
        ignored = self._load_ignored()
        ignored[key] = {
            "title": str(data.get("title") or "").strip(),
            "year": str(data.get("year") or "").strip(),
            "type": str(data.get("type") or "").strip(),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.save_data(self._DATA_IGNORED, ignored)
        title = ignored[key]["title"] or media_id
        logger.info(f"{self.plugin_name} 已忽略作品：{title}")
        return {
            "success": True,
            "message": f"已忽略「{title}」，可在面板顶部恢复",
            "data": {"ignored_count": len(ignored)},
        }

    def api_unignore(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """恢复被忽略的作品；传 ``all=true`` 时清空整份忽略列表。"""
        data = payload if isinstance(payload, dict) else {}
        ignored = self._load_ignored()
        if data.get("all"):
            count = len(ignored)
            self.save_data(self._DATA_IGNORED, {})
            return {
                "success": True,
                "message": f"已恢复全部 {count} 部被忽略的作品",
                "data": {"ignored_count": 0},
            }
        key = str(data.get("key") or "").strip()
        if not key and data.get("media_id"):
            source = str(data.get("media_source") or "douban").strip() or "douban"
            key = f"{source}:{data['media_id']}"
        if not key or key not in ignored:
            return {"success": False, "message": "该作品不在忽略列表中"}
        removed = ignored.pop(key) or {}
        self.save_data(self._DATA_IGNORED, ignored)
        title = str(removed.get("title") or key)
        return {
            "success": True,
            "message": f"已恢复「{title}」",
            "data": {"ignored_count": len(ignored)},
        }

    def api_remove_actor(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """从订阅演员中移除一位，并同步删除配置面板里的同一条目。

        面板的作品墙按演员筛选，发现某位演员不再需要时不必再跑回配置页手工删一行。
        「配置里写的那个字符串」才是这层身份的真身（``actor.key``），所以默认按它精确匹配；
        若前端只能给出已解析的人物 ID，则用演员缓存里的 ID 兜底匹配。

        移除后走与保存配置完全相同的收尾：``init_plugin`` 会检测到演员列表变更，
        丢弃该演员的残留快照，并安排一次后台补刷新（不会在请求线程里同步抓豆瓣）。
        """
        data = payload if isinstance(payload, dict) else {}
        target = str(data.get("actor") or "").strip()
        if not target:
            return {"success": False, "message": "缺少要移除的演员"}

        entries = list(self._actor_entries)
        remaining = [item for item in entries if item.strip() != target]
        if len(remaining) == len(entries):
            # 兜底：允许只给出已解析的人物 ID（或作品组的 key 就是人物 ID 的情况）
            actor_id = str(data.get("actor_id") or "").strip()
            if actor_id:
                cache = self._load_actor_cache()
                remaining = [
                    item
                    for item in entries
                    if str((cache.get(item) or {}).get("id") or "").strip() != actor_id
                ]
        if len(remaining) == len(entries):
            return {"success": False, "message": f"配置里已没有演员「{target}」"}

        merged = {**self._config_snapshot(), "actors": "\n".join(remaining)}
        # 运行时状态不落盘（与 api_update_config 保持一致）
        for key in ("run_count", "pending_refresh", "refreshing", "douban_cookie_source", "douban_cookie_hint"):
            merged.pop(key, None)
        if not self.update_config(merged):
            return {"success": False, "message": "配置持久化失败"}
        self.init_plugin(merged)

        display = str(data.get("name") or "").strip() or target
        logger.info(f"{self.plugin_name} 已移除演员：{display}（剩余 {len(remaining)} 位）")
        return {
            "success": True,
            "message": f"已移除演员「{display}」，配置里的同名条目也已同步删除",
            "data": self.get_works_payload(),
        }

    def api_clear(self) -> Dict[str, Any]:
        """清空作品快照与自动订阅记录（配置不受影响）。

        同时清掉搜索冷却记账：这是用户显式要求重来的动作，
        相当于手动放行一次重搜（会重新消耗豆瓣搜索额度）。
        """
        self.save_data(self._DATA_WORKS, {})
        self.save_data(self._DATA_SUBS, [])
        self.save_data(self._DATA_SEEN, [])
        self.save_data(self._DATA_SEARCH_LOG, {})
        self._run_count = 0
        self._last_run_at = ""
        self.save_data(self._DATA_STATE, {"run_count": 0, "last_run_at": ""})
        return {"success": True, "message": "作品、自动订阅记录与搜索记账已清空"}

    # ─── 配置解析与默认值 ────────────────────────────────────────

    @staticmethod
    def _parse_actors(value: Any) -> List[str]:
        """解析演员配置。

        分隔符同时支持换行、英文/中文逗号与分号、中文顿号，方便直接粘贴
        「刘德华,吴京,张译」这类列表；连续分隔符与空白项会被忽略，重复项去重并保序。
        """
        if isinstance(value, (list, tuple)):
            raw_items = [str(item) for item in value]
        else:
            text = (
                str(value or "")
                .replace("，", ",")
                .replace("；", ";")
                .replace("、", ",")
            )
            for sep in ("\r\n", "\n", "\r", ";", ","):
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
    def _parse_sites(value: Any) -> List[int]:
        """解析订阅站点 ID 列表；非法项直接丢弃，保持原有顺序并去重。"""
        if value in (None, ""):
            return []
        if isinstance(value, (list, tuple, set)):
            raw_items = list(value)
        elif isinstance(value, str):
            raw_items = [item for item in value.replace("，", ",").split(",")]
        else:
            raw_items = [value]
        result: List[int] = []
        for item in raw_items:
            try:
                site_id = int(str(item).strip())
            except (TypeError, ValueError):
                continue
            if site_id > 0 and site_id not in result:
                result.append(site_id)
        return result

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
            "sidebar_nav": True,
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
            "subscribe_save_path": "",
            "subscribe_downloader": "",
            "subscribe_sites": [],
            "douban_cookie": "",
            "onlyonce": False,
        }
