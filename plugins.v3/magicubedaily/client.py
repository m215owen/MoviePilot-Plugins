"""魔搭站点访问层：登录态（CookieCloud / 手填）、HTTP 请求、响应解析。

设计约束（V3 契约）：

* 只依赖 ``app.sdk.*`` 稳定入口 —— 不碰 ``app.adapters`` / ``app.foundation`` /
  ``app.runtime`` 的内部文件位置。CookieCloud 的解密逻辑按宿主的算法在本文件内
  自行实现（AES-CBC + ``Salted__``，密码 = ``md5("{key}-{password}")[:16]``），
  这样宿主的适配器搬家也不会把插件带崩。
* 本模块**只做纯函数与无状态请求**，不读写插件配置、不起任务，便于单测。
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.sdk.config import settings
from app.sdk.logging import logger
from app.sdk.network import AsyncRequestUtils
from app.sdk.utilities import CryptoJsUtils

from .constants import (
    BALANCE_PATH,
    BASE_URL,
    COOKIECLOUD_TIMEOUT,
    COOKIE_DOMAIN_SUFFIX,
    DEFAULT_TIMEOUT,
    SESSION_COOKIE_NAME,
    TRANSACTIONS_PAGE_SIZE,
    TRANSACTIONS_PATH,
    USER_AGENT,
    USER_INFO_PATH,
)

__all__ = [
    "MagicubeClient",
    "cookie_header",
    "load_cookie_from_cookiecloud",
    "parse_cookie_input",
    "pick_modelscope_cookies",
]


# ── 登录态 ────────────────────────────────────────────────────────


def parse_cookie_input(raw: str) -> Dict[str, str]:
    """把手填的 cookie 解析成 ``{name: value}``。

    兼容四种常见形态（用户从浏览器复制过来时往往并不规整）：

    1. ``a=1; b=2``（DevTools 的 ``Cookie:`` 请求头，可带前缀与换行）
    2. cURL / 抓包里的多行 ``name<TAB>value`` 不保证，按分行分号处理
    3. Cookie-Editor 导出的 JSON 数组 ``[{"name":..,"value":..}]``
    4. 简单 JSON 对象 ``{"a": "1"}``
    """
    text = (raw or "").strip()
    if not text:
        return {}

    lowered = text.lower()
    if lowered.startswith("cookie:"):
        text = text[len("cookie:"):].strip()

    # JSON 形态（数组或对象）
    if text[:1] in ("[", "{"):
        try:
            data = json.loads(text)
        except Exception:  # noqa: BLE001 - 不是 JSON 就退回文本解析
            data = None
        if isinstance(data, list):
            jar: Dict[str, str] = {}
            for item in data:
                if isinstance(item, dict) and item.get("name"):
                    jar[str(item["name"])] = "" if item.get("value") is None else str(item["value"])
            if jar:
                return jar
        elif isinstance(data, dict):
            # 只收标量值，避免把嵌套结构误当 cookie
            scalars = {
                str(k): str(v)
                for k, v in data.items()
                if isinstance(v, (str, int, float)) and not isinstance(v, bool)
            }
            if scalars:
                return scalars

    jar = {}
    for chunk in re.split(r"[;\n\r]+", text):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        name, _, value = chunk.partition("=")
        name = name.strip().strip('"')
        if not name:
            continue
        jar[name] = value.strip().strip('"')
    return jar


def cookie_header(jar: Dict[str, str]) -> str:
    """把 cookie 字典拼成请求头值（空值也要保留，部分站点靠空值判定）"""
    return ";".join(f"{name}={value}" for name, value in (jar or {}).items())


def pick_modelscope_cookies(contents: Any) -> Dict[str, str]:
    """从 CookieCloud 的 ``cookie_data`` 里挑出魔搭的 cookie 并合并。

    同一份数据会有多个域分组（``.modelscope.cn`` / ``www.modelscope.cn`` /
    ``passport.modelscope.cn`` …）。合并规则：**域名越具体越优先**（``www`` 的
    值覆盖 ``.modelscope.cn`` 的同名值），这与浏览器实际发送行为一致。
    """
    if not isinstance(contents, dict):
        return {}

    entries: List[Tuple[int, str, str, str]] = []
    for group_key, cookies in contents.items():
        if not isinstance(cookies, (list, tuple)):
            # 少数超老的 CC 版本直接给 "k=v; k2=v2" 字符串
            if isinstance(cookies, str) and _is_modelscope_domain(str(group_key)):
                for name, value in parse_cookie_input(cookies).items():
                    entries.append((len(str(group_key)), str(group_key), name, value))
            continue
        for item in cookies:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not name:
                continue
            domain = str(item.get("domain") or "") or str(group_key or "")
            if not _is_modelscope_domain(domain) and not _is_modelscope_domain(str(group_key)):
                continue
            value = "" if item.get("value") is None else str(item.get("value"))
            entries.append((len(domain), domain, str(name), value))

    # 域名短的（更宽泛）先写，长的（更具体）后写覆盖
    entries.sort(key=lambda entry: (entry[0], entry[1]))
    jar: Dict[str, str] = {}
    for _length, _domain, name, value in entries:
        jar[name] = value
    return jar


def _is_modelscope_domain(domain: str) -> bool:
    """判断域名是否属于魔搭（兼容带前导点 / 带端口 / 大小写混写）"""
    value = (domain or "").strip().lower().lstrip(".")
    if not value:
        return False
    value = value.split(":")[0]
    return value == COOKIE_DOMAIN_SUFFIX or value.endswith("." + COOKIE_DOMAIN_SUFFIX)


def _runtime_value(key: str) -> str:
    """读取宿主运行时配置（CookieCloud 三项），缺失时返回空串"""
    try:
        value = getattr(settings, key, "")
    except Exception:  # noqa: BLE001 - 配置对象版本差异兜底
        value = ""
    return str(value or "").strip()


async def load_cookie_from_cookiecloud() -> Tuple[str, str]:
    """从宿主的 CookieCloud 配置读取魔搭登录态。

    :return: ``(cookie 请求头, 错误说明)``；成功时错误说明为空串。
    """
    host = _runtime_value("COOKIECLOUD_HOST").rstrip("/")
    key = _runtime_value("COOKIECLOUD_KEY")
    password = _runtime_value("COOKIECLOUD_PASSWORD")
    if not (host and key and password):
        return "", "宿主未配置 CookieCloud（COOKIECLOUD_HOST / KEY / PASSWORD 有空值）"

    url = f"{host}/get/{key}"
    try:
        response = await AsyncRequestUtils().get_res(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=COOKIECLOUD_TIMEOUT,
        )
    except Exception as err:  # noqa: BLE001 - 网络层异常统一转成可用提示
        return "", f"拉取 CookieCloud 数据失败：{err}"

    if response is None:
        return "", "拉取 CookieCloud 数据失败（请求无响应，检查宿主网络与 CookieCloud 地址）"
    try:
        status = getattr(response, "status_code", None)
        if status and int(status) != 200:
            return "", f"CookieCloud 返回 HTTP {status}"
        body = _response_text(response)
    finally:
        await _close_async_response(response)

    try:
        payload = json.loads(body)
    except Exception:  # noqa: BLE001
        return "", "CookieCloud 响应不是合法 JSON"
    if not isinstance(payload, dict):
        return "", "CookieCloud 响应结构异常"

    encrypted = payload.get("encrypted")
    if not encrypted:
        return "", "CookieCloud 未返回密文（可能 KEY 不对）"

    # 与宿主 CookieCloudHelper 完全一致的密钥派生：md5("{key}-{password}")[:16]
    crypt_key = hashlib.md5(f"{key}-{password}".encode("utf-8")).hexdigest()[:16].encode("utf-8")
    try:
        plain = CryptoJsUtils.decrypt(str(encrypted), crypt_key).decode("utf-8")
        data = json.loads(plain)
    except Exception as err:  # noqa: BLE001
        return "", f"CookieCloud 数据解密失败：{err}"

    contents = data.get("cookie_data") if isinstance(data, dict) else None
    if not isinstance(contents, dict):
        contents = data if isinstance(data, dict) else {}

    jar = pick_modelscope_cookies(contents)
    if not jar:
        return "", "CookieCloud 里没有 modelscope.cn 的 cookie（请在浏览器登录魔搭后再同步）"
    if SESSION_COOKIE_NAME not in jar:
        return "", f"CookieCloud 的魔搭 cookie 缺少登录态 {SESSION_COOKIE_NAME}（CookieCloud 快照过期，请重新同步）"
    return cookie_header(jar), ""


def _response_text(response: Any) -> str:
    """安全取出 httpx2 响应正文（同步或异步实现都能吃）"""
    content = getattr(response, "content", None)
    if content is None:
        text = getattr(response, "text", "")
        return str(text or "")
    try:
        return str(content, "utf-8", "replace")
    except Exception:  # noqa: BLE001
        return ""


async def _close_async_response(response: Any) -> None:
    """关闭 httpx2 响应对象。

    ``AsyncRequestUtils.get_res`` 返回的是**异步**响应，``close()`` 会抛
    ``Attempted to call a sync close on an async stream``，必须走 ``aclose()``。
    """
    closer = getattr(response, "aclose", None)
    if closer is None:
        return
    try:
        result = closer()
        if hasattr(result, "__await__"):
            await result
    except Exception as err:  # noqa: BLE001 - 关连接失败不影响结果
        logger.debug(f"魔搭魔粒签到：关闭响应失败（忽略）：{err}")


# ── 站点客户端 ────────────────────────────────────────────────────


class MagicubeClient:
    """魔搭魔粒接口的薄封装（只读 + 触发访问，无写操作）。"""

    def __init__(self, cookie: str, timeout: int = DEFAULT_TIMEOUT, proxy: str = "") -> None:
        self._cookie = (cookie or "").strip()
        self._timeout = max(5, int(timeout or DEFAULT_TIMEOUT))
        proxy = (proxy or "").strip()
        self._proxies: Optional[Dict[str, str]] = (
            {"http://": proxy, "https://": proxy} if proxy else None
        )

    @property
    def cookie(self) -> str:
        return self._cookie

    @property
    def has_session(self) -> bool:
        """cookie 里是否有登录态字段（只做粗筛，真正的有效性由接口回答）"""
        return f"{SESSION_COOKIE_NAME}=" in self._cookie

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Cookie": self._cookie,
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        return headers

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Tuple[Optional[int], str]:
        """发起 GET，返回 ``(HTTP 状态码, 正文)``；网络失败返回 ``(None, "")``。"""
        url = path if path.startswith("http") else f"{BASE_URL}{path}"
        kwargs: Dict[str, Any] = {
            "headers": self._headers(),
            "timeout": self._timeout,
        }
        if self._proxies:
            kwargs["proxies"] = self._proxies
        response = None
        try:
            response = await AsyncRequestUtils().get_res(url, params=params, **kwargs)
        except Exception as err:  # noqa: BLE001
            logger.debug(f"魔搭魔粒签到：请求 {path} 异常：{err}")
            return None, ""
        if response is None:
            return None, ""
        try:
            status = getattr(response, "status_code", None)
            body = _response_text(response)
            return (int(status) if status is not None else None), body
        finally:
            await _close_async_response(response)

    async def get_json(
        self, path: str, params: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        """请求并解析 JSON 信包，把站点的业务错误翻译成中文提示。"""
        status, body = await self._get(path, params=params)
        if status is None:
            return None, "请求失败（无响应：网络不通、超时或被站点拦截）"
        if not body:
            return None, f"响应为空（HTTP {status}）"
        try:
            data = json.loads(body)
        except Exception:  # noqa: BLE001
            return None, f"响应不是 JSON（HTTP {status}，{len(body)} 字节）"
        if not isinstance(data, dict):
            return None, "响应结构异常"
        if data.get("success") is False:
            code = str(data.get("code") or "").strip()
            message = str(data.get("message") or "").strip()
            if code == "InvalidAuthentication" or "authentication" in message.lower():
                return None, f"登录态无效（{message or code}）：请重新在浏览器登录魔搭并同步 CookieCloud"
            return None, f"接口返回失败：{code or '未知错误'} {message}".strip()
        return data, ""

    async def balance(self) -> Tuple[Optional[Dict[str, Any]], str]:
        """``GET /openapi/v1/magicubes/balance`` → ``{total_balance, available_balance, frozen_amount}``"""
        data, err = await self.get_json(BALANCE_PATH)
        if err:
            return None, err
        payload = data.get("data") if isinstance(data.get("data"), dict) else {}
        return payload, ""

    async def transactions(self, page_size: int = TRANSACTIONS_PAGE_SIZE) -> Tuple[List[Dict[str, Any]], str]:
        """``GET /openapi/v1/magicubes/transactions`` → 由新到旧的流水记录"""
        data, err = await self.get_json(
            TRANSACTIONS_PATH,
            params={"page_number": 1, "page_size": int(page_size)},
        )
        if err:
            return [], err
        payload = data.get("data") if isinstance(data.get("data"), dict) else {}
        records = payload.get("records")
        if not isinstance(records, list):
            return [], "流水响应缺少 records 字段"
        return [record for record in records if isinstance(record, dict)], ""

    async def user_info(self) -> Tuple[Dict[str, str], str]:
        """``GET /openapi/v1/users/me`` → 当前登录用户。

        实测返回 ``data: {username, nickname, avatar_url, email, description}``。
        这一步只是「显示是谁在领」，失败不影响领取本身，所以调用方要允许它为空。
        """
        data, err = await self.get_json(USER_INFO_PATH)
        if err:
            return {}, err
        payload = data.get("data") if isinstance(data.get("data"), dict) else {}
        return {
            "username": str(payload.get("username") or ""),
            "nickname": str(payload.get("nickname") or ""),
            "avatar_url": str(payload.get("avatar_url") or ""),
        }, ""

    async def touch(self, paths: Iterable[str]) -> List[Dict[str, Any]]:
        """带登录态访问若干页面 —— 这就是「每日发放」的触发动作。

        站点把 +200/+50 记在**当天首次带登录态的访问**上（服务端去重），
        所以这里不需要也不存在「签到接口」。失败不抛，交给上层汇总。
        """
        results: List[Dict[str, Any]] = []
        for path in paths:
            status, body = await self._get(path)
            results.append(
                {
                    "path": path,
                    "ok": bool(status == 200 and body),
                    "status": status,
                    "size": len(body or ""),
                }
            )
        return results
