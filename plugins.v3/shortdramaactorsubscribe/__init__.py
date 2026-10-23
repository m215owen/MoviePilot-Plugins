"""短剧演员订阅（MoviePilot V3 插件后端）。

一句话：把喜欢的**短剧演员**填进来，插件从**短剧百科**抓回他们的全部作品，摆成一面
和宿主「探索」页同形的海报墙；想追哪部点「订阅」，走的就是**宿主自己的订阅系统**。

这个插件**不做什么**
--------------------
2026-10-15 整体重写，删掉了一整条自建链路（站点搜索 / 择优下载 / 账本去重 / 自建订阅表
/ 自建整理入库 / 自写 NFO）。原因只有一条：这些宿主都已经有了 ——

* **订阅**：宿主订阅系统吃显式媒体身份（``media_source`` + ``media_id``），而短剧百科
  已经作为一等媒体数据源接入了宿主框架（能出卡片、能开媒体详情页），所以订阅直接交还给
  系统：插件面板上的「订阅」按钮调宿主注入的 ``nativeSubscribe``，弹出来的就是系统自己的
  订阅对话框，建出来的就是系统订阅，搜索 / 下载 / 整理全由宿主负责。
* **识别与刮削**：同理交给百科数据源与宿主刮削链，插件不再自己写 NFO。

插件现在只负责**发现**：演员 → 百科作品 → 作品墙 → 交给系统。

发现源 = 只有 ShortDramaBaikeScraper（duanjubaike.net）
--------------------------------------------------
作品 100% 来自 ``ShortDramaBaikeScraper``。走**跨插件模块方法**
（``search_actors`` / ``actor_works`` / ``actor_profile``，见 ``get_module()`` 白名单；
没登记的名字是**静默拿空**，不会报错）。

⚠️ **不走 ``self.chain.run_module``**（2026-10-17 改）：宿主分发器对**返回列表**的模块
方法做**跨插件合并**（``dispatcher._execute_plugin_provider_sequence`` 逐个体插入结果，
只有非列表结果才「首个非空即胜」）。宿主里同时装着别的短剧数据源时，``search_actors`` /
``actor_works`` 会把两边的候选混在一起 —— 各家站点各排各的号，混起来就是**认错人**。
所以这里按插件 id 精确取那一份方法表（:meth:`_source`），只认 scraper。

⚠️ V3 SDK 的 ``_PluginBase`` **不继承** ChainBase，``self.run_module`` 不存在；
``self.chain`` 只用于宿主链路，跨插件取数一律走 :meth:`_source`。

数据源契约（ShortDramaBaikeScraper / duanjubaike.net）
--------------------------------------------------
* **演员 ID 是复合形态** ``yanyuan:<数字>``；作品同理 ``duanju:<数字>``，
  前缀 = 站点分类（``duanju`` / ``manju`` / ``hema`` / ``huolong`` … 开放集）。作品身份
  **原样保留**复合 ID —— 剥成裸数字后分类就丢了，``manju`` / ``hema`` 的详情页会拼错地址。
* **宿主媒体来源标识**是 ``djbaike``（数据源 ``get_media_source`` 声明）——
  订阅 / 在库探针 / 详情投影里的 ``media_source`` 都用它；它与**站点分类前缀**是两码事，
  不能拿 ``djbaike`` 当 ``media_id`` 的前缀。
* **模块方法**：``search_actors`` / ``actor_works`` / ``actor_profile`` / ``list_people``
  （见 :meth:`get_module` 白名单）；没登记的名字静默拿空。
* 作品卡字段名：``badge``（短剧 / 漫剧…）才是「角标」位，``kind`` 是站点分类；
  ``episodes`` = 集数，``genres_text`` = 题材（``爱情 / 都市爱情 / …``）。

**只有一个数据源**（2026-10-18 用户定；2026-10-22 起为 ShortDramaBaikeScraper，
老 ShortDramaNetSource 已丢弃）：本插件只认当前数据源，不兼容任何
其它短剧数据源的历史身份 —— 别家站点的号段与这里完全无关，拿过来查只会是另一部剧。

演员解析纪律：站外索引的候选**含模糊结果**（搜「王石」会带出「王碩」），因此只收**归一化
名字精确相等**的候选；解析出的百科 ID 缓存进快照，后续轮次零引擎请求。

「新作品」口径
-------------
``release_date``（站点印的首播 / 上映日期）距今在 :data:`_NEW_WINDOW_DAYS` 天窗口内
⇒ 标「新」（2026-10-19 用户口径）。看片的人要的是「这周上新的剧」，所以判据必须是
**作品的日期**，而不是「我什么时候第一次看到它」：``first_seen`` 会因换源 / 刚关注 /
一次导入十几位演员而整片同时「首次出现」，拿它当新就会一次刷出上千部。
``first_seen`` 保留，只作「首次发现」展示。缺日期 / 未来日期一律不算新（宁少不错）。

V3 契约要点
-----------
1. **依赖入口**：宿主依赖一律走 ``app.sdk.*``。
2. **渲染模式**：``vue``（Vue 模块联邦）。配置页 / 详情页 / 仪表板 / 侧栏全页由
   ``dist`` 下的联邦产物目录（见 :func:`_frontend_dist`）里的联邦组件渲染，后端只提供 ``get_api()`` 接口。
3. **不在模块导入期**做网络、数据库或任务启动。
4. **插件类的运行时容器必须在 ``init_plugin`` 里重新赋值**（宿主 reconcile 会反复重建
   实例，类属性字典会跨实例串味）。
"""
from __future__ import annotations

import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

from apscheduler.triggers.interval import IntervalTrigger

# 宿主统一响应模型（``schemas.Response[T]``）：插件 API 走三段式 envelope，业务数据放 ``data``。
# 见官方 ``docs/V3_API_Response_Adaptation.md`` §1/§3.2；模型见 :mod:`api_models`。
from app import schemas
from app.sdk.events import Event, eventmanager
from app.sdk.logging import logger
from app.sdk.media import MetaInfo
from app.sdk.plugin import _PluginBase
from app.schemas.types import EventType
from fastapi import HTTPException

# 接口的响应模型（``response_model`` 声明 + 业务数据模型）
from . import api_models

# 消息类型枚举在宿主版本间存在改名：V3.1+ 使用 MessageType，更早的实现使用 NotificationType。
try:  # pragma: no cover - 取决于宿主版本
    from app.schemas.types import MessageType as _MessageType
except ImportError:  # pragma: no cover
    from app.schemas.types import NotificationType as _MessageType  # type: ignore

# 插件展示名，同时作为通知标题
PLUGIN_NAME = "短剧演员订阅"

# ─────────────────────────── 常量 ───────────────────────────

# 演员作品快照（插件数据，不是配置）
_DATA_ACTORS = "actors_state"

# 自动订阅台账（插件数据）：``media_id`` → 一条处理记录。
#
# 为什么要台账：宿主订阅 ``exist_ok=True`` 能把重复订阅挡掉，但每轮都去问一遍
# 就是几百次无谓调用；更重要的是「跳过在库 / 订阅失败」也要记住，否则每次刷新
# 都会重新撞同一堵墙。只记尝试过的（成功 / 跳过 / 失败），上限 :data:`_AUTO_SUB_LIMIT`。
_DATA_AUTO_SUB = "auto_subscribed"
_AUTO_SUB_LIMIT = 500

#: 台账里「没订，因为库里已经有了」的那句说明 —— 统计「订阅成功」时要摘掉它
_AUTO_SKIP_DETAIL = "已在媒体库，跳过"

# 自建订阅搜索台账（插件数据）：``media_id`` → 一条处理记录。
#
# 为什么有了宿主订阅还要自建（2026-10-22）：宿主订阅搜索按媒体类型拼**站点分类参数**
# （电视剧 → cat402/403/404/405），而 PTS 等站会把短剧挂在电影分类 —— 这类剧在宿主
# 订阅视角下「在站上不存在」，永远搜不到。自建器自己发**全分类标题搜索**（不传
# ``mtype`` ⇒ 站点把电影 + 电视剧 + 短剧 + 动漫一起搜），命中后按演员名 / 集数 /
# 年份旁证消歧，再交宿主下载链提交（整理 / 通知仍归宿主）。
_DATA_SUB_SEARCH = "subscribe_search"
_SUB_SEARCH_LIMIT = 800

# 自建订阅清单（插件数据）：``media_id`` → 订阅记录。
#
# 2026-10-22 用户口径：引擎 = 自建时，「订阅」**不再提交宿主订阅系统** —— 插件
# 自己就是订阅系统，订阅记在这里，由订阅搜索任务（:meth:`subscribe_search_task`）
# 搜到即下、下完即终。引擎 = 宿主时照旧走宿主订阅链；历史宿主 ``djbaike`` 订阅
# 也纳入自建搜索的候选（见 :meth:`_subscribed_works`），切换引擎不丢订阅。
_DATA_SUBS = "subscriptions"

# 订阅站 RSS 增量（插件数据）：RSS 条目标题 → 处理记录。
#
# 2026-10-23 用户口径：订阅的补搜接入宿主 RSS 系统 —— 定时拉**站点 RSS**
# （NexusPHP 站的 rss.php，地址含用户密钥，一行一条填在配置里），新种子与当前
# 订阅做匹配、命中直接交宿主下载链。拉 RSS 是普通页面请求，比搜索接口轻得多，
# 是从源头避开站点流控的正解；主动搜索降级为兜底（RSS 没有的再靠搜索补）。
# 处理过的条目按标题记历史（与宿主内置 rsssubscribe 插件同口径），只判一次。
_DATA_RSS_HISTORY = "subscribe_rss_history"
#: RSS 检查任务固定间隔（分钟）与历史条数上限。
#: RSS 源**不单独配置**（2026-10-23 用户口径）：直接取订阅站点的**站点配置** ——
#: 站点自带 ``rss`` 地址就用它；没有则用站点 cookie 现场生成
#: （``RssHelper.get_rss_link``，与宿主 CookieCloud 同步生成 RSS 同一套逻辑）。
_RSS_CHECK_INTERVAL_MINUTES = 30
_RSS_HISTORY_LIMIT = 2000

#: 随机订阅已挑过的作品（插件数据）：``media_id`` → 挑选记录。
#: 2026-10-23 用户口径：随机订阅**永不重复** —— 之前随机订过的（哪怕后来取消了
#: 订阅）不再进入候选，每次随机都给没见过的。
_DATA_RANDOM_PICKED = "random_picked"
_RANDOM_PICKED_LIMIT = 1000

# 自建订阅搜索的默认与上限（配置页可调，越界收口）
_SUB_SEARCH_DEFAULT_MAX = 5
_SUB_SEARCH_MAX_LIMIT = 30
_SUB_SEARCH_DEFAULT_HOURS = 6
_SUB_SEARCH_DEFAULT_PAGES = 3
_SUB_SEARCH_MAX_PAGES = 10
#: 失败重试冷却（小时）：链路异常 / 提交失败
_SUB_SEARCH_RETRY_HOURS = 24
#: 无结果重试冷却（小时）：站上暂时没有，过几天再看（新种可能发布）
_SUB_SEARCH_NORESULT_RETRY_HOURS = 72
#: 翻页间隔（秒）：参考宿主订阅搜索的站点节流口径，页与页之间歇一口气
_SUB_SEARCH_PAGE_SLEEP = 3
#: 全量订阅搜索**部与部之间**的随机间隔（秒， inclusive 区间）—— 与宿主
#: ``SubscribeChain._wait_before_scheduled_search`` 同参数（60~300），
#: 目的一样：「为了避免连续访问站点」触发站点流控。手动单部补搜不等。
_SUB_SEARCH_WORK_INTERVAL = (60, 300)

# 自动订阅单轮上限（部）。默认给个小数字：一轮刷新可能涌进上百部「新作品」，
# 一次全提交会把订阅列表和下载队列一起打爆；没轮到的不要紧 —— 不记台账，下一轮继续。
_AUTO_SUB_DEFAULT_MAX = 5
_AUTO_SUB_MAX_LIMIT = 50

# 「订阅全部作品」单次上限（部）。手动动作不按自动订阅的小预算走（用户点了就是要全订），
# 但也不能让一次 HTTP 请求无限跑 —— 超过这条线的作品留给下一次点击（已在库 / 已订阅的
# 会被跳过，重复点不会重复提交）。
_SUBSCRIBE_ALL_LIMIT = 200

# 解析失败重试间隔（分钟）。「上一轮失败」是可自愈的，等满一轮发现间隔恢复体验太差，
# 所以单独按短间隔重试（演员快照的保鲜期 = 发现间隔，见 snapshot_ttl_seconds）。
_DEFAULT_RETRY_MINUTES = 20

# 快照时间戳格式
_STAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

# 首播 / 上映日期：站点卡片上是纯日期（``2026-10-14``），后面可能跟时间，只取日期头
_RELEASE_DATE_RE = re.compile(r"\s*(\d{4})-(\d{1,2})-(\d{1,2})")

# 面板日志只显示消息本体（2026-10-23 用户口径：时间、[-] 括号、插件 id 都不要）。
# 宿主日志行形态：``【INFO】2026-10-23 21:43:13,418 [-] - shortdramaactorsubscribe - 消息``
_LOG_HEAD_RE = re.compile(
    r"^(?:【[^】]*】\s*)?"
    r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}[,.]\d{3}\s*"
    r"\[[^\]]*\]\s*-\s*"
)
#: 紧跟在头部后面的 logger 名（插件 id 小写）＋分隔符，也剥掉
_LOG_LOGGER_RE = re.compile(r"^[a-z][a-z0-9_.]*\s*-\s*")


def _clean_log_line(line: str) -> str:
    """一行宿主日志 → 只留消息本体。

    依次去掉：日志级别（``【INFO】``）、时间戳、线程方括号（``[-]``）、
    插件 id（logger 名）前缀，以及消息里自带的插件名开头
    （2026-10-23 用户口径：页面上不需要显示这些）。
    """
    text = _LOG_LOGGER_RE.sub("", _LOG_HEAD_RE.sub("", line)).strip()
    text = text or line.strip()
    for prefix in (PLUGIN_NAME, "ShortDramaActorSubscribe", "shortdramaactorsubscribe"):
        if prefix and text.startswith(prefix):
            text = text[len(prefix):].lstrip(" -—:：\t")
            break
    return text

# 「新作品」的时间窗（天）：**上映（首播）日期**在最近 N 天内的作品标「新」
# （2026-10-19 用户口径：从「首次发现晚于基线 3 天」改成「最近 7 天内上映」——
#  看片的人关心的是「这周上新的剧」，而不是「我什么时候第一次看到它」）。
_NEW_WINDOW_DAYS = 7
_NEW_WINDOW_SECONDS = _NEW_WINDOW_DAYS * 24 * 3600

# 唯一发现源标识（短剧百科作为宿主媒体数据源的标识）。
#
# ⚠️ 必须用**规范标识** ``djbaike``（与 ShortDramaBaikeScraper 的 ``MEDIA_SOURCE_ID``
# 一致）：官方插件开发文档要求「通用媒体身份必须同时包含 media_source + media_id，不要在
# 通用链路中只保存裸 ID」，而宿主侧的来源目录（``GET /api/v1/media/source``）认的都是
# 这个规范值 —— 用别的标识订阅出去的条目会被当成另一个来源，分类规则里的来源过滤就落空了。
# 2026-10-22 起：老数据源 ShortDramaNetSource（``duanju``）已丢弃，全部换 scraper。
_BAIKE_SOURCE = "djbaike"

# 裸数字 media_id 的**兜底分类**（站点实体前缀）。注意它与上面的来源标识是两码事：
# ``djbaike`` 只是宿主侧的来源声明，``djbaike:39980`` 不是合法身份 —— 前缀必须是
# 站点分类（``duanju`` / ``manju`` / …）。
_DEFAULT_ENTITY = "duanju"

# 唯一的发现源插件（**按插件 id 精确绑定**，不走 chain 聚合 —— 见模块头）。
# 插件 id = 类名（宿主 ``_running_plugins`` 的键），不是插件目录名。
_SOURCE_PLUGIN_ID = "ShortDramaBaikeScraper"

# 错误提示 / 日志里给用户看的名字，与插件面板上的显示名对齐
_SOURCE_LABEL = "短剧数据源（ShortDramaBaikeScraper）"

# 百科作品的类型：短剧一律按电视剧走（宿主没有「短剧」媒体类型）
_BAIKE_TYPE = "电视剧"

# 豆瓣融合作品（``douban:<subject id>``）走**宿主豆瓣源**（2026-10-22 用户拍板）：
# 订阅链 / 媒体库探针原生支持豆瓣身份 —— 识别走宿主豆瓣模块（media_source=douban
# + 裸 subject id → tv_detail），不再收敛成 ``djbaike``（豆瓣 subject 号与站点
# 各分类编号是两套独立空间，硬套 djbaike 会让订阅/探针认错剧）。
_DOUBAN_SOURCE = "douban"

# 作品墙分页：单页上限与默认页大小。
#
# 作品墙是**服务端筛选 + 排序 + 分页**（真机实测 95 位演员 = 2256 部），前端按页拉、
# 滚到底再拉下一页，所以默认页就是首屏规模（三两行卡片），不必一次拿全。
_MAX_PAGE_SIZE = 200
_DEFAULT_PAGE_SIZE = 60

# 排序模式 → (作品记录字段, 比较方式)。2026-10-23 用户口径：**只留首播日期** ——
# 热度 / 播放 / 评分在作品墙快照里恒为 0（人物页作品卡不印统计，评分也不是每部都有），
# 按它们排等于整片并列、顺序随机，撤掉。
#   ``date`` → 日期降序（``YYYY-MM-DD`` 字典序即时间序），缺数据的排最后。
_SORT_FIELDS = {
    "date": ("release_date", "date"),
}
_DEFAULT_SORT = "date"

# 「搜索演员」时最多给前几位候选补档案（头像 / 作品数 / 简介）—— 每位一次页面请求，
# 不设上限会让一次搜索拖很久；超出的候选仍以「只有名字」的卡片给出。
_ACTOR_LOOKUP_LIMIT = 12

# 人物目录的三个分类（站点 `/yanyuan|daoyan|bianju/list.html`）—— **有序**，
# 决定 `GET /people` 的默认分类。成员判定仍用 :data:`_PERSON_KINDS`（同一个集合，
# 定义在人物身份那一节），这里只管顺序与面板文案。
_PEOPLE_KINDS = ("yanyuan", "daoyan", "bianju")
_PERSON_KIND_LABELS = {"yanyuan": "演员", "daoyan": "导演", "bianju": "编剧"}

# 演员档案（头像 / 简介 / 身份）的字段口径。
#
# **只放进程内缓存，不落盘**（数据源为主：档案属内容字段，不在本地存第二份）。
# 发现流程每轮顺带补一次 → 卡片墙读内存即秒回；插件重载后缓存冷掉，卡片先出占位，
# ``/actors/cards?enrich=1`` 或下一轮发现再补。
_PROFILE_FIELDS = (
    # 身份两项：导演 / 编剧这类**不在关注名单**里的人物没有快照行兜底，
    # 名字与复合 ID 只能从 ``actor_profile`` 拿（2026-10-19 数据源已提供）。
    "name",
    "media_id",
    "profile",
    "bio",
    "gender",
    "nationality",
    "job_title",
    "url",
    "works_count",
    # 2026-10-18：站点人物页给「粉丝 / 获赞」，卡片上要显示（数据源 actor_profile 的
    # 契约字段名就叫 followers / likes）
    "followers",
    "likes",
    # 2026-10-18 补全：演员详情页「数据显示不全」——数据源 actor_profile 的跨插件契约
    # 里还有生日 / 籍贯 / 身高体重 / 星座 / 院校 / 爱好 / 代表作，之前白名单没列，
    # 取到也丢掉了，详情页因此只剩「职业｜国籍 + 简介」。
    "birth_date",
    "birth_year",
    "birth_place",
    "height_cm",
    "weight_kg",
    "constellation",
    "education",
    "hobbies",
    "rep_text",
)

#: 进程内**作品**缓存的保鲜期（秒）。v5 起作品随快照落盘，这一层只服务两种场景：
#: 快照里还没有 ``works`` 的老记录、以及刚抓完还没写回快照的同一轮 —— 挡住
#: 「同一批请求连着打」的重复取数，不是作品的主存储。
_WORKS_CACHE_TTL = 300.0

#: 进程内**档案**缓存的保鲜期（秒）。档案变化极慢，长一点没坏处。
_PROFILE_CACHE_TTL = 3600.0

# 快照记录的字段版本：低于当前值的记录会在下一轮刷新时重抓一次。
# 2026-10-15 = 2：作品开始带类型 / 年份 / 热度 / 播放 / 版权方等筛选排序字段，
# 旧快照里没有这些字段，靠这个版本号自动触发一次重抓（不必用户手动刷新）。
# 2026-10-17 = 3：数据源换成 ShortDramaNetSource，演员 / 作品 ID 换成**复合形态**
# （``yanyuan:<id>`` / ``duanju:<id>``）。更早的快照是另一套站点的裸号段，与 .net 完全
# 无关 —— 靠这个版本号整体重抓，陈旧身份不复用。
# 2026-10-18 = 4：**快照不再存作品内容**（数据源为主）—— ``works[]`` → ``first_seen``
# 映射 + ``works_count``；作品内容运行时向数据源取（见 ``_actor_works_cached``）。
# 旧记录在读入时由 :func:`migrate_record` 就地迁移，不需要为升级额外重抓一轮。
# 2026-10-19 = 5：**作品重新进快照**（用户口径）—— 每部只存身份 + 墙上要用的字段
# （:data:`_SNAPSHOT_WORK_KEYS`），作品墙不再每次逐演员打数据源；v4 记录缺 ``works``，
# 由版本门触发一次重抓补齐（补之前墙照样能读，走数据源兜底）。
_SNAPSHOT_SCHEMA = 5

#: 快照里每部作品保留的字段：**身份 + 作品墙要用的字段**（筛选 / 排序 / 卡片 / 详情兜底）。
#: 键名是 :func:`baike_work_to_candidate` 产出后的**本插件口径**（``episode_count`` /
#: ``genres``），不是数据源原始卡片的写法（``episodes`` / ``genres_text``）——
#: 存错键等于没存（v5 首版就踩过这个坑）。
#: ``type`` / ``source`` 不存：:func:`work_row` 每次都会按规范值重新补上。
_SNAPSHOT_WORK_KEYS = (
    "media_id",
    "title",
    "year",
    "poster",
    "url",
    "vote",
    "episode_count",
    "genres",
    "heat",
    "play_count",
    "studio",
    "platform",
    "kind",
    "release_date",
)

# 作品字段在数据源版本间会改名，一律按候选名依次取，取到第一个有值的为准。
# ``genres`` 是 .net 详情/补全后的形态，``genres_text`` 是演员页卡片上的原样字符串
# （``爱情 / 都市爱情 / …``，``tags_of`` 会按分隔符拆开）。
_TAGS_FIELDS = ("genres", "genres_names", "genres_text")
_HEAT_FIELDS = ("heat", "heat_count", "popularity")
_PLAY_FIELDS = ("play_count", "plays", "play")
_STUDIO_FIELDS = (
    "studio",
    "production_companies",
    "production",
    "producer",
    "company",
    "copyright",
    "copyright_holder",
)

# 播放平台（「在哪播」）：红果短剧 / 河马剧场 / 番茄 …，是站点**独立于站点分类**的
# 一维事实 —— 与 ``kind``（站点分类 duanju/manju）、``studio``（出品方）三条轴互不重叠。
#
# 数据源两种形体都可能出现：作品卡上直接给 ``platform``（``netsite`` 从 meta 文案
# ``在<平台>平台上`` 抠出来的字符串），进宿主模型后落成 TMDB 形体的
# ``networks=[{"name": "红果短剧"}]``（``payload.py``）。两种都认。
_PLATFORM_FIELDS = ("platform", "network", "networks", "channel")

# 一次性任务 ID
_ONCE_JOB_ID = "refresh_once"
# 自建订阅搜索的一次性任务 ID（与发现任务分开登记，避免互相顶掉）
_ONCE_SUB_JOB_ID = "subscribe_once"

# 全角 ASCII → 半角（剧名归一化用；0x3000 是全角空格）
_FULLWIDTH_MAP = {code: code - 0xFEE0 for code in range(0xFF01, 0xFF5F)}
_FULLWIDTH_MAP[0x3000] = 0x20

# 季/部标记：归一化剧名时剔除。注意「云渺3」这类**片名序号不属于季标记**，必须保留 ——
# 「云渺3：镇魔世家」和「云渺4：绝嗣佛子」是两部独立的剧，序号是唯一的区分键。
_SEASON_TOKEN_PATTERNS = (
    re.compile(r"(?:full\s*)?season\s*0*\d+", re.IGNORECASE),
    re.compile(r"[sS]0*\d{1,2}(?!\d)(?!\s*[eE]\d)"),
    re.compile(r"第\s*0*\d+\s*[季部]"),
    re.compile(r"第\s*[一二三四五六七八九十]+\s*[季部]"),
)

# 集数标记：只作信息字段，同时要从剧名里剔除以免影响归一化
_EPISODE_PATTERNS = (
    re.compile(r"共\s*\d+\s*集"),
    re.compile(r"全\s*\d+\s*集"),
    re.compile(r"\d+\s*集"),
    re.compile(r"[sS]\d{1,2}[eE]\d{1,4}"),
    re.compile(r"[eE][pP]?\d{1,4}\b"),
)

# 文件名/剧名中的非法字符
_ILLEGAL_NAME_CHARS = re.compile(r'[\\/*?:"<>|]')
# 归一化时要去除的标点与空白（保留字母、数字、汉字）
_NAME_NOISE = re.compile(
    r"[\s\-_.·•:：、,，;；!！?？~～^《》<>「」『』\[\]［］\(\)（）\"'“”‘’]+"
)


# ─────────────────────────── 纯函数（可单测） ───────────────────────────


def _clean_text(value: Any) -> str:
    """把任意值收敛成去空白的字符串（None / 数字 / 空白串 → 空串）。"""
    if value is None:
        return ""
    return str(value).strip()


def _clean_save_path(value: Any) -> str:
    """下载目录：只保留真实路径串，对象残值一律当空。

    前端踩过 ``v-combobox`` 的坑：Vuetify 3 里 ``return-object`` 默认为 true，
    选中候选时 v-model 拿到的是整条 item 对象，``str(obj)`` 落库成
    ``"[object Object]"`` —— 界面输入框显示目录名（「短剧」），存的却是这串
    废值，宿主按 save_path 精确匹配必然失败、退回默认目录。这类残值在入口就清掉。
    """
    text = _clean_text(value)
    if not text or (text.startswith("[object ") and text.endswith("]")):
        return ""
    return text


def _to_bool(value: Any, default: bool = False) -> bool:
    """宽松布尔转换：前端可能传真布尔，也可能传 "true"/"on"/"1" 之类的字符串。"""
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes", "on")


def _to_int(value: Any, default: int = 0) -> int:
    """宽松整数转换；拿不到数字返回默认值（百科的集数/热度字段经常是字符串或空）。"""
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    """宽松浮点转换；拿不到数字返回默认值（评分缺省按 0 处理，前端会统一格式化）。"""
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _pick_text(item: Dict[str, Any], names: Any) -> str:
    """按候选字段名依次取值，返回第一个非空文本（数据源版本间字段会改名）。

    ``[{"name": "红果…"}]``（宿主模型形态）、``{"name": "红果…"}``、``"红果…"``
    三种形态都收敛成同一个字符串。
    """
    for name in names:
        value = item.get(name)
        if isinstance(value, (list, tuple)):
            value = value[0] if value else ""
        if isinstance(value, dict):
            value = value.get("name")
        text = _clean_text(value)
        if text:
            return text
    return ""


def _pick_number(item: Dict[str, Any], names: Any) -> float:
    """按候选字段名依次取数值；一个都没有就返回 0（排序时自然排到最后）。"""
    for name in names:
        value = item.get(name)
        if value in (None, ""):
            continue
        number = _to_float(value, -1.0)
        if number >= 0:
            return number
    return 0.0


def platform_of(raw: Any) -> str:
    """播放平台名（可单测）：宿主 ``networks=[{"name": …}]`` 与数据源 ``platform="…"`` 同收。

    站点把播放平台写在 meta 文案末尾（``该短剧在红果短剧平台上目前已有…``），数据源
    ``netsite._platform_of`` 抠出来后：作品卡上叫 ``platform``（字符串），进宿主
    ``MediaInfo`` 后落成 ``networks=[{"name": …}]``。这里把两种形体收敛成一个字符串。

    多个平台时**只取第一个**（站点文案里本质上只印一个播放平台），拿不到返回空串 ——
    「没有平台」不该被显示成「未知」或占位符。
    """
    if isinstance(raw, (list, tuple)):
        for entry in raw:
            if isinstance(entry, dict):
                text = _clean_text(entry.get("name"))
            else:
                text = _clean_text(entry)
            if text:
                return text
        return ""
    if isinstance(raw, dict):
        return _clean_text(raw.get("name"))
    return _clean_text(raw)


def tags_of(item: Dict[str, Any]) -> List[str]:
    """作品的题材/类型标签（去重保序，可单测）。

    兼容三种形态：``["逆袭", "都市日常"]``、``"逆袭,都市日常"``、
    ``[{"name": "逆袭"}]`` —— 数据源在卡片 / 详情 / 宿主模型里给的并不一致。
    """
    raw: Any = None
    for name in _TAGS_FIELDS:
        value = item.get(name)
        if value:
            raw = value
            break
    if isinstance(raw, str):
        raw = re.split(r"[,，/、|;；]+", raw)
    if not isinstance(raw, (list, tuple)):
        return []
    result: List[str] = []
    seen: set = set()
    for entry in raw:
        if isinstance(entry, dict):
            entry = entry.get("name")
        text = _clean_text(entry)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def work_year(item: Dict[str, Any]) -> str:
    """作品的年份：优先 ``year``，否则从 ``release_date``（首播日期）里取前四位。"""
    year = _clean_text(item.get("year"))
    if year:
        return year
    release = _clean_text(item.get("release_date") or item.get("first_air_date"))
    match = re.match(r"(\d{4})", release)
    return match.group(1) if match else ""


def classify_error(message: str) -> str:
    """把数据源侧的错误文案归成稳定的原因码。

    * ``baike_empty`` —— **稳定**结果：数据源没收录这位演员（或数据源插件没装/停用）；
    * ``baike`` —— **临时**故障：网络抖动 / 数据源处于升级中间态，重试大概率自愈；
    * ``other`` —— 其余。
    """
    text = _clean_text(message)
    if "未收录" in text or "没有作品" in text:
        return "baike_empty"
    if text.startswith("短剧百科") or text.startswith("短剧数据源"):
        return "baike"
    return "other"


def record_state(record: Dict[str, Any]) -> str:
    """演员记录当前的展示状态（可单测）。

    * ``''`` 正常（已有作品）；
    * ``'waiting'`` 临时性失败 —— 面板只给一句「等待自动重试」；
    * ``'empty'`` 百科未收录 —— 中性说明，不是故障。

    临时性优先：同一条记录里既有临时故障又有「未收录」时按可重试处理；
    ``stale``（本轮数据源空手而归、沿用内存里的上次结果）同样按可重试处理 ——
    否则要等满整个快照 TTL 才会再去拉一次。
    """
    if not isinstance(record, dict):
        return "waiting"
    if _to_int(record.get("works_count")):
        return "waiting" if record.get("stale") else ""
    kinds = {classify_error(str(item)) for item in record.get("errors") or []}
    if "baike" in kinds or "other" in kinds:
        return "waiting"
    if "baike_empty" in kinds:
        return "empty"
    return "waiting"


def parse_stamp(value: Any) -> Optional[datetime]:
    """解析快照里的时间戳（``YYYY-MM-DD HH:MM:SS``）；不可解析返回 None。"""
    text = _clean_text(value)
    if not text:
        return None
    try:
        return datetime.strptime(text, _STAMP_FORMAT)
    except ValueError:
        return None


def snapshot_age_seconds(record: Dict[str, Any], now: Optional[datetime] = None) -> Optional[float]:
    """一条演员快照距今多少秒；缺时间戳 / 格式不对返回 None（视为「该刷新」）。"""
    parsed = parse_stamp((record or {}).get("time"))
    if parsed is None:
        return None
    return max(0.0, ((now or datetime.now()) - parsed).total_seconds())


def record_needs_refresh(
    record: Dict[str, Any],
    ttl_seconds: float,
    retry_seconds: float,
    now: Optional[datetime] = None,
    schema: int = 0,
) -> bool:
    """一条演员快照是否到了该重新解析的时间点（可单测）。

    - 没有记录 / 时间戳不可解析 → 要（新加的演员立刻解析）
    - 记录字段版本低于 ``schema``（数据源补齐了新字段）→ 要，立刻重抓一次
    - ``waiting``（临时性失败）→ 按**失败重试间隔**判定
    - 其余 → 按**快照刷新间隔**判定
    """
    if not isinstance(record, dict):
        return True
    if schema and _to_int(record.get("schema")) < schema:
        return True
    age = snapshot_age_seconds(record, now)
    if age is None:
        return True
    state = _clean_text(record.get("state"))
    if state == "waiting":
        return age >= retry_seconds
    if not state and not _to_int(record.get("works_count")):
        # 老快照（还没有 state 字段）里没作品的记录：分不清失败还是确无作品，按可重试处理
        return age >= retry_seconds
    return age >= ttl_seconds


def is_retry_candidate(record: Dict[str, Any]) -> bool:
    """该记录是否属于「解析失败、值得按短间隔重试」的一类（可单测）。"""
    if not isinstance(record, dict):
        return True
    if _clean_text(record.get("state")) == "waiting":
        return True
    return not record.get("state") and not _to_int(record.get("works_count"))


def release_epoch(value: Any) -> float:
    """首播 / 上映日期（``YYYY-MM-DD``，也可能带时间）→ epoch 秒；取不到返回 0。

    站点卡片印的是 ``2026-10-14`` 这种纯日期，用 :func:`parse_stamp` 会解析失败，
    所以单列一个只认日期头的解析器；非法日期（``2026-02-31``）按「没有」处理。
    """
    matched = _RELEASE_DATE_RE.match(_clean_text(value))
    if not matched:
        return 0.0
    try:
        moment = datetime(
            int(matched.group(1)), int(matched.group(2)), int(matched.group(3))
        )
    except ValueError:
        return 0.0
    return moment.timestamp()


def is_fresh_work(work: Dict[str, Any], now: float) -> bool:
    """作品是否属于「**最近 N 天内上映**」的新作品（可单测）。

    判据只有一个：``release_date``（站点印的首播 / 上映日期）距今在
    :data:`_NEW_WINDOW_SECONDS` 之内。

    * 缺日期 → 不算新（没日期就没法说它什么时候上的，宁少不错）；
    * 未来日期（预约剧 / 站点写错）→ 不算新（还没上映）；
    * 与「演员什么时候加入关注」**无关** —— 刚关注的演员，他这周上的剧照样算新。
    """
    released = release_epoch(work.get("release_date"))
    if not released:
        return False
    delta = now - released
    return 0 <= delta <= _NEW_WINDOW_SECONDS


def normalize_title(title: str) -> str:
    """把剧名归一化成可比较的键（全角转半角 → 去非法字符 → 剔季/集标记 → 去标点 → 小写）。

    **片名中的序号必须保留**：见 ``_SEASON_TOKEN_PATTERNS`` 处的说明。
    """
    text = _clean_text(title)
    if not text:
        return ""
    text = text.translate(_FULLWIDTH_MAP)
    text = _ILLEGAL_NAME_CHARS.sub("", text)
    for pattern in _SEASON_TOKEN_PATTERNS:
        text = pattern.sub(" ", text)
    for pattern in _EPISODE_PATTERNS:
        text = pattern.sub(" ", text)
    text = _NAME_NOISE.sub("", text)
    return text.lower()


def work_key(title: str, year: str = "") -> str:
    """作品的去重键：归一化剧名 + 年份。"""
    return f"{normalize_title(title)}|{_clean_text(year)}"


#: 种子标题 / 副标题里的集数提示（``全80集`` / ``80集`` / ``共80集``）。
_EPISODE_HINT_RE = re.compile(r"[全共]?\s*(\d{1,4})\s*集")


def torrent_haystack(context: Any) -> str:
    """把一条搜索结果里所有可用于片名比对的文本拼成一个「草堆」。

    种子标题（``为所欲为（80集）何田田&王轩等 - SKIT``）+ 副标题（``全80集 | 2026年 …``）
    + 识别出的原始字符串 —— 三处都可能藏着演员名 / 集数 / 年份旁证。
    """
    parts: List[str] = []
    torrent = getattr(context, "torrent_info", None)
    if torrent is not None:
        for attr in ("title", "description"):
            parts.append(_clean_text(getattr(torrent, attr, None)))
    meta = getattr(context, "meta_info", None)
    if meta is not None:
        for attr in ("org_string", "title", "subtitle"):
            parts.append(_clean_text(getattr(meta, attr, None)))
    return " ".join(part for part in parts if part)


def episode_hint(text: str) -> Optional[int]:
    """从文本里抠「集数」提示（``全80集`` → 80）；抠不到返回 ``None``。"""
    for match in _EPISODE_HINT_RE.finditer(_clean_text(text)):
        try:
            return int(match.group(1))
        except (TypeError, ValueError):  # pragma: no cover - 正则保证是数字
            continue
    return None


def match_work_context(
    context: Any, row: Dict[str, Any], title_key: str
) -> Tuple[bool, str]:
    """判断一条搜索结果是不是目标作品的资源；返回 ``(是否命中, 理由)``。

    两级判定（命中任意一级即收）：

    1. **身份命中**：搜索链已把种子识别出媒体身份（``torrent_info`` 或
       ``media_info`` 上带 ``media_source`` + ``media_id``），与目标一致 —— 最硬的证据。
    2. **剧名一致**：归一化剧名与种子文本里的剧名相同即收（2026-10-22 用户口径：
       **不再要求演员 / 集数 / 年份旁证**）。短剧种子标题恒带「（N集）演员A&演员B等 - SKIT」
       后缀，整串不可能相等，所以判据是「归一化剧名出现在归一化种子文本里」——
       归一化已剔掉季集标记与标点，等价于「剧名完全相同」。旁证只用来写命中理由
       （便于台账追溯是哪条证据），不再是门槛。
    """
    haystack = torrent_haystack(context)
    if not haystack:
        return False, "无种子文本"

    # ── 一级：媒体身份 ──
    target_source = _clean_text(row.get("media_source"))
    target_id = _clean_text(row.get("media_id"))
    candidates: List[Tuple[Any, Any]] = []
    torrent = getattr(context, "torrent_info", None)
    if torrent is not None:
        candidates.append((getattr(torrent, "media_source", None), getattr(torrent, "media_id", None)))
    media = getattr(context, "media_info", None)
    if media is not None:
        candidates.append((getattr(media, "source", None), getattr(media, "media_id", None)))
        candidates.append((getattr(media, "media_source", None), getattr(media, "media_id", None)))
    for source, media_id in candidates:
        source_text = str(getattr(source, "value", source) or "").strip()
        if source_text and source_text == target_source and same_media_id(media_id, target_id):
            return True, "媒体身份一致"

    # ── 二级：剧名一致即收 ──
    if title_key and title_key not in normalize_title(haystack):
        return False, "剧名不匹配"
    # 旁证只写进理由，不参与判定。演员旁证：订阅记录里的 ``actor`` 常是
    # 「卡戎 / 梁雯晶」这种联合串，而站点标题是「梁雯晶&卡戎等」—— 整串比对永远不中，
    # 拆成单人再逐个找（2026-10-22 真机）。
    corroborators: List[str] = []
    actor = _clean_text(row.get("actor"))
    for name in re.split(r"[,，/、|;；&\s]+", actor):
        name = name.strip()
        if len(name) >= 2 and name != "等" and name in haystack:
            corroborators.append(f"演员「{name}」")
            break
    episodes = _to_int(row.get("episode_count"))
    hint = episode_hint(haystack)
    if episodes > 0 and hint == episodes:
        corroborators.append(f"集数 {episodes}")
    year = _clean_text(row.get("year"))
    if year and year in haystack:
        corroborators.append(f"年份 {year}")
    if corroborators:
        return True, "剧名一致 + " + "、".join(corroborators[:2])
    return True, "剧名一致"


#: 复合 ID：``<站点分类>:<纯数字>``。分类是**开放集**（duanju / manju / hema …），
#: 只约束词法，不写死取值 —— 站点随时会加新分类。数据源给的 ID 唯一且就是这个形态，
#: 所以**不需要**再用前缀黑名单去猜「这是不是老源的号」：形态不符的就是别处的号。
_COMPOSITE_ID_RE = re.compile(r"^(?P<kind>[a-z][a-z0-9]*):(?P<native>\d+)$", re.IGNORECASE)

#: 站点上**不是剧集**的分类。用**黑名单**而不是白名单：分类是开放集，
#: 站点加一个新剧集频道（河马 / 火龙 …）时必须自动放行，写死白名单会把它误杀。
#: ``xiaoshuo`` 是小说频道 —— 站内搜索会把小说条目和剧集混在一个结果列表里。
_NON_DRAMA_KINDS = frozenset({"xiaoshuo", "novel", "book"})

#: 人物分类：搜索里万一带出人物卡，作品墙 / 作品详情都不该收（人物走演员那一路）。
_PERSON_KINDS = frozenset({"yanyuan", "daoyan", "bianju"})


def split_media_id(value: Any) -> Tuple[str, str]:
    """作品 / 人物 ID → ``(站点分类, 纯数字)``；认不出返回 ``("", "")``（可单测）。

    裸数字**不给分类**（``("", "39980")``）—— 分类缺了就只能由调用方决定默认值，
    这里绝不替它编一个前缀（编错了会去抓别的分类下的同名号）。
    """
    text = _clean_text(value)
    if not text:
        return "", ""
    parsed = _COMPOSITE_ID_RE.match(text)
    if parsed:
        return parsed.group("kind").lower(), parsed.group("native")
    if text.isdigit():
        return "", text
    return "", ""


def canonical_media_id(value: Any, default_kind: str = _DEFAULT_ENTITY) -> str:
    """把作品 ID 收敛成**规范复合形态** ``<分类>:<数字>``（可单测）。

    - ``duanju:39980`` → 原样（分类已给）；
    - ``39980`` → ``duanju:39980``（裸数字按 ``default_kind`` 补前缀）；
    - 认不出（空 / 非数字 / URL）→ 空串，交给调用方重解析。数据源给的 ID 一律是
      「分类 + 纯数字」，形态不符就不是本数据源的号，没有第三种情况。

    规范形态是**订阅 / 在库探针 / ``recognize_media`` 三方共用的唯一凭据**：
    身份里必须带分类，否则 ``manju`` / ``hema`` 的作品会被当成 ``duanju`` 的号去查。
    """
    text = _clean_text(value)
    if not text:
        return ""
    kind, native = split_media_id(text)
    if not native:
        return ""
    return f"{kind or default_kind}:{native}"


def same_media_id(left: Any, right: Any) -> bool:
    """两个作品 ID 是否指同一部剧（复合与裸数字视为同一，分类缺失的那侧不算冲突）。"""
    kind_left, native_left = split_media_id(left)
    kind_right, native_right = split_media_id(right)
    if not native_left or not native_right:
        return False
    if native_left != native_right:
        return False
    if kind_left and kind_right and kind_left != kind_right:
        return False
    return True


def is_drama_media_id(value: Any) -> bool:
    """这个 ID 是不是**一部剧**（可单测）。

    站内搜索会把小说频道（``xiaoshuo:…``）的条目和剧集混在同一个结果列表里，
    作品墙 / 作品详情只该收剧集。判定用**黑名单**：

    * 认不出分类（裸数字 / 空 / URL）→ **放行**（交给下游按默认分类兜底，
      不能因为「我没认出」就把用户搜到的剧扔掉）；
    * 分类在 :data:`_NON_DRAMA_KINDS` / :data:`_PERSON_KINDS` 里 → 不是剧；
    * 其余一律是剧（开放集，站点加新频道自动放行）。
    """
    kind, native = split_media_id(value)
    if not native:
        return bool(_clean_text(value))
    return kind not in _NON_DRAMA_KINDS and kind not in _PERSON_KINDS


def baike_media_id(work: Dict[str, Any]) -> str:
    """作品行的 ``media_id`` → 规范复合 ID（可单测）。

    快照里同一部剧可能存在两种写法（``39980`` / ``duanju:39980``），只看字符串会把
    一部剧拆成两行；这里统一成 ``<分类>:<数字>``。解析不出来（含老数据源身份）返回空串，
    由调用方重解析。
    """
    return canonical_media_id(work.get("media_id"))


def wall_row_key(work: Dict[str, Any]) -> str:
    """作品墙行的去重键：**优先按规范 ID**，ID 归一不了再退回 剧名|年份。

    为什么不直接用 ``work_key(title, year)``：不同演员的快照抓取时间不同，
    同一部剧可能一份带年份、一份是早年「年份恒空」的旧卡 —— 按剧名|年份
    会把同一部剧数成两部（这正是真机上 2185 行里混着 78 对重复的根因）。
    站点 ID 是作品的一等身份，用它最稳。
    """
    kind, native = split_media_id(work.get("media_id"))
    if native:
        # 去重键带来源前缀：站点身份仍是 djbaike|duanju:xxx（老快照键不变），
        # 豆瓣融合身份是独立键 douban|douban:xxx —— 融合层已保证一部剧只出一张卡
        source = _DOUBAN_SOURCE if kind == "douban" else _BAIKE_SOURCE
        return f"{source}|{kind or _DEFAULT_ENTITY}:{native}"
    return work_key(work.get("title") or "", work.get("year") or "")


def work_identity(work: Dict[str, Any]) -> str:
    """作品在 ``first_seen`` 映射里的键：规范复合 ID 优先，认不出退回 ``剧名|年份``。

    与 :func:`wall_row_key` 的区别：这里不带来源前缀（映射只服务「新作品」判定，
    不参与去重），所以同一部剧在 `duanju:` / `manju:` 下都按 ID 各自成键。
    """
    media_id = baike_media_id(work)
    if split_media_id(media_id)[1]:
        return media_id
    return work_key(work.get("title") or "", work.get("year") or "")


def merge_first_seen(
    old_map: Optional[Dict[str, Any]],
    works: List[Dict[str, Any]],
    stamp: str,
) -> Dict[str, str]:
    """把本轮作品并进 ``first_seen`` 映射（可单测）。

    旧映射里已有的作品**继承原来的首次出现时间**，只有真正新冒出来的才记本轮
    ``stamp``；**旧映射里已不存在的键剪掉**（作品下线 / 换源，留着只会无限膨胀）。

    映射键 = :func:`work_identity`（规范复合 ID，认不出才退回 ``剧名|年份``）。
    老记录（v3 及以前）里 ``剧名|年份`` 形态的键按剧名兜一层匹配 ——
    同一部剧「这次有 ID、上次没有」时不会被误判成新作品。
    """
    previous: Dict[str, str] = {}
    if isinstance(old_map, dict):
        for key, value in old_map.items():
            key, value = _clean_text(key), _clean_text(value)
            if key and value:
                previous[key] = value
    # 只有「剧名|年份」形态的旧键才参与剧名兜底（ID 键直接精确匹配）
    titles: Dict[str, str] = {}
    for key, value in previous.items():
        if split_media_id(key)[1]:
            continue
        titles.setdefault(normalize_title(key.split("|")[0]), value)

    result: Dict[str, str] = {}
    for work in works:
        if not isinstance(work, dict):
            continue
        key = work_identity(work)
        if not key:
            continue
        seen = previous.get(key) or titles.get(normalize_title(work.get("title") or ""))
        result[key] = seen or stamp
    return result


def migrate_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """把 v3 及以前的快照记录（作品全量落盘）迁移成当前结构（可单测）。

    * v5 记录（本版本写的）**原样返回** —— 作品本来就该在快照里；
    * 更早的记录：``works[]`` → ``first_seen`` 映射（每部作品的 ``first_seen`` 原样继承），
      ``works`` 丢掉（v4 的瘦身形态）。迁移后**保留原 ``schema``** —— 版本门
      （:func:`record_needs_refresh`）据此在下一轮重抓一次，把 ``works`` 补回快照；
      这里若顺手把 schema 抬到 5，版本门就再也不触发，作品墙只能一直走数据源兜底；
    * 档案字段（``profile`` / ``bio`` / ``gender`` / ``nationality`` / ``job_title``）
      **丢弃** —— 档案只进进程内缓存，不在本地存第二份；``url`` 保留（页面链接，不是内容）；
    * ``works_count`` 记下作品数：演员列表 / 状态接口要它。
    """
    if not isinstance(record, dict):
        return record
    if _to_int(record.get("schema")) >= _SNAPSHOT_SCHEMA and isinstance(
        record.get("works"), list
    ):
        return record
    if "works" not in record:
        return record
    works = [item for item in record.get("works") or [] if isinstance(item, dict)]
    mapping: Dict[str, str] = {}
    for work in works:
        key = work_identity(work)
        seen = _clean_text(work.get("first_seen"))
        if key and seen:
            mapping.setdefault(key, seen)
    slim = {
        key: value
        for key, value in record.items()
        if key
        not in ("works", "profile", "bio", "gender", "nationality", "job_title")
    }
    legacy = slim.get("first_seen")
    if isinstance(legacy, dict):
        for key, value in legacy.items():
            key, value = _clean_text(key), _clean_text(value)
            if key and value:
                mapping.setdefault(key, value)
    slim["first_seen"] = mapping
    slim["works_count"] = _to_int(slim.get("works_count")) or len(works)
    return slim


def lean_works(works: Any) -> List[Dict[str, Any]]:
    """作品列表 → **快照落盘形态**（可单测）。

    只留 :data:`_SNAPSHOT_WORK_KEYS` 里非空的字段 —— 落盘的是**身份 + 事实**，
    档案 / 详情这类内容字段一律运行时向数据源取，不在本地存第二份。
    没有合法 ``media_id`` 的条目直接丢掉（没身份既不能订阅也打不开详情）。
    """
    rows: List[Dict[str, Any]] = []
    seen: set = set()
    for item in works or []:
        if not isinstance(item, dict):
            continue
        media_id = canonical_media_id(item.get("media_id"))
        if not split_media_id(media_id)[1] or media_id in seen:
            continue
        seen.add(media_id)
        row: Dict[str, Any] = {"media_id": media_id}
        for key in _SNAPSHOT_WORK_KEYS:
            if key == "media_id":
                continue
            value = item.get(key)
            if value in (None, "", 0, [], {}):
                continue
            row[key] = value
        rows.append(row)
    return rows


def snapshot_works(record: Any) -> List[Dict[str, Any]]:
    """快照记录里的作品列表；没有这一项（v4 及更早的记录）返回空列表。"""
    if not isinstance(record, dict):
        return []
    works = record.get("works")
    if not isinstance(works, list):
        return []
    return [item for item in works if isinstance(item, dict)]


def _actor_name_key(name: Any) -> str:
    """演员名的宽松比较键：去空白后比对（百科候选可能带多余空格）。"""
    return re.sub(r"\s+", "", _clean_text(name))


def _actor_id_of(value: Any) -> str:
    """演员的**规范复合 ID**（``yanyuan:<n>`` 等）；认不出人物号就返回空串。

    2026-10-20 起演员身份统一收敛到 ID（用户口径：ID 是唯一的）—— 配置里的
    关注名单、快照主键、增删与「已关注」判定都以它为准；名字只作展示，
    以及「还没解析到 ID」的过渡态（见 :meth:`_rekey_actors` 的归位说明）。
    """
    actor_id = canonical_media_id(value, default_kind="yanyuan")
    kind, native = split_media_id(actor_id)
    if not native or kind not in _PERSON_KINDS:
        return ""
    return actor_id


class _SourceUnavailable(RuntimeError):
    """数据源插件没安装 / 已停用 / 没登记某个模块方法。

    单独一个异常类型，是为了让「数据源不可用」（该报 503 给人看）与
    「数据源拿不到这位演员」（正常空结果）在调用方分得开。
    """


#: 档案字段的**来源别名**：键是本插件缓存口径，值是该字段在数据源里的写法
#: （演员页给 ``poster`` / ``biography``，档案方法给 ``profile_path`` / ``bio``）。
_PROFILE_ALIASES: Dict[str, Tuple[str, ...]] = {
    # 身份两项：数据源 ``actor_profile`` 会带 ``name`` / ``media_id``（人物复合 ID）。
    # 非关注名单里的导演 / 编剧没有快照行可兜底，名字只能从档案里取 —— 所以留在这里。
    "name": ("name",),
    "media_id": ("media_id",),
    "profile": ("profile", "poster", "poster_path", "profile_path", "avatar"),
    "bio": ("bio", "biography", "introduction"),
    "job_title": ("job_title", "job", "role"),
    "gender": ("gender",),
    "nationality": ("nationality", "country"),
    "url": ("url", "page_url", "source_url"),
    "works_count": ("works_count", "worksCount"),
    "followers": ("followers", "fans", "fans_count"),
    "likes": ("likes", "like_count", "praise"),
    "birth_date": ("birth_date", "birthday", "birth"),
    "birth_year": ("birth_year", "year"),
    "birth_place": ("birth_place", "birthplace", "native_place", "hometown"),
    "height_cm": ("height_cm", "height"),
    "weight_kg": ("weight_kg", "weight"),
    "constellation": ("constellation", "star_sign", "zodiac"),
    "education": ("education", "school", "college", "university"),
    "hobbies": ("hobbies", "hobby", "interests"),
    "rep_text": ("rep_text", "representative_text", "works_text"),
}

#: 需要转成整数的档案字段（其余一律按文本收敛）
_PROFILE_INT_FIELDS = frozenset(
    {"works_count", "followers", "likes", "height_cm", "weight_kg"}
)

#: 值是**列表**的档案字段（按字符串列表收敛，不能走 `_clean_text`）
_PROFILE_LIST_FIELDS = frozenset({"hobbies"})

#: **卡片行**用得上的档案字段（详情页那几项 —— 生日 / 籍贯 / 身高 / 爱好 / 代表作 ——
#: 不进卡片：96 张卡每张都带一份纯属浪费，卡片上也不展示）
_CARD_PROFILE_FIELDS = (
    "profile",
    "bio",
    "gender",
    "nationality",
    "job_title",
    "url",
    "followers",
    "likes",
)


def person_job(kind: Any, gender: Any = "", job_title: Any = "") -> str:
    """人物的**职业文案**：优先数据源原文，缺了按「分类 + 性别」补（可单测）。

    为什么需要补：数据源的演员记录**不再落盘 ``job_title``**（2026-10-19 v18 口径，
    演员档案不展示职能），``actor_profile`` 的 ``job`` 因此在缓存命中时是空的。
    而站点的人物卡副行一直按「女演员 / 男演员 / 导演 / 编剧」写，这里按同一口径还原：

    * ``yanyuan`` + 性别（男 / 女）→ ``女演员`` / ``男演员``；
    * 性别不明或其余分类 → 用分类名（``演员`` / ``导演`` / ``编剧``）。
    """
    text = _clean_text(job_title)
    if text:
        return text
    kind_text = _clean_text(kind).lower() or "yanyuan"
    sex = _clean_text(gender)
    if kind_text == "yanyuan" and sex in ("男", "女"):
        return f"{sex}演员"
    return _PERSON_KIND_LABELS.get(kind_text, "演员")


def _text_list(value: Any) -> List[str]:
    """把「爱好」这类字段收敛成去重保序的字符串列表（可单测）。

    数据源给的是 JSON 数组（``["旅游", "健身"]``），但跨插件调用偶尔会退化成
    ``"旅游、健身"`` 这种一整串 —— 两种都认；空白项丢掉，不做其它加工。
    """
    if isinstance(value, (list, tuple, set)):
        raw = list(value)
    else:
        raw = re.split(r"[,，/、|;；\n\r]+", _clean_text(value))
    result: List[str] = []
    for item in raw:
        text = _clean_text(item)
        if text and text not in result:
            result.append(text)
    return result


def rep_work_rows(rep_text: Any, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """把站点那句「代表作」原文，对回这位演员的作品行（可单测）。

    站点给的是**一整串没有分隔符**的剧名（``武极天尊武极天尊2之神界篇行道者之剑…``），
    不能按标点切。这里拿演员的全部作品标题做**贪心最长匹配**：从当前位置找能匹配上的
    最长标题，命中就记一行并跳过它，没命中就前进一个字继续找。

    这样「武极天尊2之神界篇」不会被切成「武极天尊」+「2之神界篇」；
    原文里对不上任何作品的片段（站点写错 / 作品已下线）直接跳过 ——
    宁少不错，不拿相似标题硬凑。

    :return: 按**原文出现顺序**命中的作品行（去重）
    """
    text = re.sub(r"\s+", "", _clean_text(rep_text))
    if not text or not rows:
        return []
    candidates: List[Tuple[str, Dict[str, Any]]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        flat = re.sub(r"\s+", "", _clean_text(row.get("title") or row.get("key")))
        if len(flat) < 2:
            continue
        candidates.append((flat, row))
    # 长标题优先：保证「武极天尊2之神界篇」先于「武极天尊」被匹配
    candidates.sort(key=lambda item: len(item[0]), reverse=True)

    matched: List[Dict[str, Any]] = []
    seen: set = set()
    index = 0
    while index < len(text):
        hit: Optional[Tuple[str, Dict[str, Any]]] = None
        for flat, row in candidates:
            if text.startswith(flat, index):
                hit = (flat, row)
                break
        if hit is None:
            index += 1
            continue
        flat, row = hit
        marker = _clean_text(row.get("key")) or flat
        if marker not in seen:
            seen.add(marker)
            matched.append(row)
        index += len(flat)
    return matched


def profile_fields_of(raw: Any) -> Dict[str, Any]:
    """数据源档案 → 本插件缓存口径（``_PROFILE_FIELDS``，可单测）。

    同一个字段在数据源不同出口的键名不同（``poster`` / ``biography`` vs
    ``profile_path`` / ``bio``），语义却是同一件事；在这里一次对齐，快照 / 前端就只认
    一套键。值为空的字段**不写入** —— 「没有」不该被写成 ``0`` / ``""`` 混进缓存。
    """
    if not isinstance(raw, dict):
        return {}
    profile: Dict[str, Any] = {}
    for field, names in _PROFILE_ALIASES.items():
        value: Any = None
        for name in names:
            candidate = raw.get(name)
            if candidate not in (None, "", 0, [], {}):
                value = candidate
                break
        if value in (None, "", [], {}):
            continue
        if field in _PROFILE_LIST_FIELDS:
            profile[field] = _text_list(value)
        elif field in _PROFILE_INT_FIELDS:
            profile[field] = _to_int(value)
        else:
            profile[field] = _clean_text(value)
    return profile


def source_card(card: Any) -> Dict[str, Any]:
    """数据源作品卡 → 本插件内部卡（字段口径归一，可单测）。

    为什么要有这一层：数据源给卡片的键名与本插件的候选结构不同，而下游的
    :func:`baike_work_to_candidate` / :func:`work_row` 不该认识来源。

    * 集数：数据源卡片叫 ``episodes``，本插件统一叫 ``episode_count``；
    * 题材：``genres_text`` 是演员页卡片上的原样字符串（``爱情 / 都市爱情 / …``），
      交给 :func:`tags_of` 拆（``/`` 在分隔符表里）；
    * **角标**：本插件的 ``kind`` 是「真人 / AI」那个角标位。数据源的 ``kind`` 是
      **站点分类**（``duanju`` / ``manju``），绝不能流进这个键 —— 只认 ``badge``
      （``短剧`` / ``漫剧`` / ``河马短剧`` …）。
    """
    if not isinstance(card, dict):
        return {}
    merged = dict(card)
    merged["episode_count"] = merged.get("episodes")
    badge = _clean_text(merged.get("badge"))
    kind = _clean_text(merged.get("kind"))
    if badge:
        merged["kind"] = badge
    elif re.fullmatch(r"[a-z0-9_]+", kind):
        # 站点分类（全小写英文）不是角标 —— 宁可留空，也别把 ``duanju`` 印在卡上
        merged["kind"] = ""
    merged["media_id"] = canonical_media_id(merged.get("media_id"))
    return merged


def baike_work_to_candidate(card: Any) -> Optional[Dict[str, Any]]:
    """把数据源作品卡转成作品墙用的统一候选结构。

    ``media_id`` 是**规范复合身份** ``<站点分类>:<数字>``（``duanju:34146``），与
    ``media_source`` 一起构成宿主订阅系统认的**媒体身份** —— 作品墙上的「订阅」就是
    拿这两个字段交给系统订阅。分类必须留着：站点各分类各排各的号，剥成裸数字后
    ``manju`` / ``hema`` 的作品会被当成 ``duanju`` 的同一个号去查。

    筛选 / 排序用的字段（``genres`` 类型、``year`` 年份、``heat`` 热度、
    ``play_count`` 播放、``studio`` 版权方）**数据源给多少就存多少**，缺的一律
    留空或 0 —— 前端据此隐藏没有数据的筛选项，绝不拿假值填充（假值会让「按版权方
    筛选」出现一堆空标签，比没有这项更糟）。
    """
    if not isinstance(card, dict):
        return None
    title = _clean_text(card.get("title"))
    if not title:
        return None
    canonical_id = baike_media_id(card)
    kind, _native = split_media_id(canonical_id)
    return {
        "title": title,
        "year": work_year(card),
        "type": _BAIKE_TYPE,
        # 豆瓣融合身份（douban:）走宿主豆瓣源，站点身份仍是 djbaike（见常量注释）
        "source": _DOUBAN_SOURCE if kind == "douban" else _BAIKE_SOURCE,
        "media_id": canonical_id,
        # 图片出口口径（2026-10-17 用户）：**图床数据源给什么就用什么** ——
        # 这里原样透传，不改写主机、不换代理、不做「豆瓣 > TMDB > 站点」的择优
        # （那是数据源自己的事，本插件不参与）。空白地址也不猜，交给前端显示占位。
        "poster": _clean_text(card.get("poster")),
        "vote": _to_float(card.get("rating")),
        "episode_count": _to_int(card.get("episode_count") or card.get("episodes")),
        "url": _clean_text(card.get("url")),
        "genres": tags_of(card),
        "heat": _pick_number(card, _HEAT_FIELDS),
        "play_count": _pick_number(card, _PLAY_FIELDS),
        "studio": _pick_text(card, _STUDIO_FIELDS),
        # 播放平台（「在哪播」）：作品卡上叫 ``platform``，进宿主模型后是
        # ``networks=[{"name": …}]`` —— ``_pick_text`` 两种形体都收；站点没印就留空，
        # 前端据此隐藏该筛选项（绝不拿「未知」之类的假值填充）
        "platform": _pick_text(card, _PLATFORM_FIELDS),
        "kind": _clean_text(card.get("kind")),
        "release_date": _clean_text(card.get("release_date")),
    }


def work_row(work: Dict[str, Any], actor: str, actor_key: str) -> Dict[str, Any]:
    """把候选作品补成作品墙的一行（带上演员归属与前端需要的字段）。"""
    row = dict(work)
    row["key"] = wall_row_key(work)
    row["actor"] = actor
    row["actor_key"] = actor_key
    # 源标识按身份前缀分流（2026-10-22）：站点身份收敛到规范值 ``djbaike``，
    # 豆瓣融合身份（douban:）走宿主豆瓣源 ``douban`` —— 订阅 / 在库探针都按它匹配
    kind, _native = split_media_id(row.get("media_id"))
    row["media_source"] = _DOUBAN_SOURCE if kind == "douban" else _BAIKE_SOURCE
    # 类型同理：快照里的作品不存 ``type`` / ``source``（冗余），出墙时补回规范值 ——
    # 在库探针的回退匹配要按类型过滤
    if not _clean_text(row.get("type")):
        row["type"] = _BAIKE_TYPE
    if not _clean_text(row.get("source")):
        row["source"] = _BAIKE_SOURCE
    # 作品 ID 统一收敛成复合形态：站点身份是 ``duanju`` + 裸数字；豆瓣身份保持
    # ``douban:<subject id>``（订阅链按 ``douban`` 源 + 裸号识别，见 _add_subscribe）
    row["media_id"] = baike_media_id(work)
    return row


# ── 作品详情（面板自绘「媒体详情页」的数据面） ──────────────────────────
#
# 数据面 = 短剧百科的 ``recognize_media``（宿主模块合同，返回标准 ``MediaInfo``）
#          ＋ 本地快照里那一行的**墙上字段**（热度 / 播放 / 真人·AI / 首次发现 / 是否新 / 在库）。
#
# 为什么另起一个详情页：宿主自带的媒体详情页（宿主编译产物 ``MediaDetailView.vue``）里
# 右侧信息面板 / 演职员 / 推荐 / 分季**全部以 ``tmdb_id`` 为前提**，而短剧大多不在 TMDB 上
# ⇒ 那些区块整块不渲染；播放量 / 热度 / 真人·AI 更是宿主模型里压根没有的字段。
# 本插件把百科详情 + 卡上字段合起来自己渲染，风格照宿主那一页。

#: 演员页路径（站点口径：``/{分类}/info-{id}.html``，演员分类一般是 ``yanyuan``）
_ACTOR_PATH = "/{kind}/info-{id}.html"

#: 本站域名。只在**数据源没给地址**时用来兜底拼链接（见 :func:`site_info_url`）：
#: 本插件绑死这一个站点，域名是站点事实而非猜测。
_SITE_DOMAIN = "https://www.duanjubaike.net"
#: 站点图床（人物头像与作品海报同一台）
_SITE_IMAGE_HOST = "https://img.duanjubaike.net"


def actor_poster_url(media_id: Any) -> str:
    """按人物身份**现拼**头像地址（零请求，可单测）。

    站点人物头像固定是 ``<图床>/<分类>/<页面ID>.jpg`` —— 与数据源
    ``identity.poster_url`` 同一口径。档案缓存冷的时候（插件刚重载、发现任务
    还没轮到这位）靠它兜底，否则整面墙都是人形占位图。

    只认「分类 + 数字」的复合 ID；裸数字按 ``yanyuan`` 补（关注列表里绝大多数
    是演员）；认不出返回空串，让前端显示占位图（不编地址）。
    """
    kind, native = split_media_id(media_id)
    if not native:
        return ""
    return f"{_SITE_IMAGE_HOST}/{kind or 'yanyuan'}/{native}.jpg"


def site_info_url(media_id: Any, domain: str = _SITE_DOMAIN) -> str:
    """按站点规则由复合 ID 拼出**详情页地址**（可单测）。

    为什么需要：.net 数据源的 ``build_media_info`` **不写 ``homepage``**（``url`` 因此
    恒空），而详情页的「百科地址」与演员跳转都要它。ID 里已经带分类，路径就是
    ``/{分类}/info-{id}.html`` —— 与站点真实路径一致，不是瞎猜。

    认不出 ID（空 / 非数字）或没有域名 → 返回 ``""``（宁可不给链接）。
    """
    kind, native = split_media_id(media_id)
    if not native:
        return ""
    base = _clean_text(domain).rstrip("/")
    if not base:
        return ""
    return f"{base}{_ACTOR_PATH.format(kind=kind or _DEFAULT_ENTITY, id=native)}"


def _media_attr(info: Any, *names: str, default: Any = None) -> Any:
    """按名取宿主 ``MediaInfo`` 的属性：**取第一个有值的**（可单测）。

    字段名在宿主版本间动过（``runtime`` / ``episode_run_time``、
    ``number_of_episodes`` / ``episode_count``）；详情页少一行信息是小事，
    因为一个取不到的字段把整个端点打成 500 才是大事，所以一律宽松读取。
    刻意跳过数值 0：站点「没有评分」就是 0，那种值当作「没取到」交给下一个候选 /
    兜底更安全。
    """
    for name in names:
        value = getattr(info, name, None)
        if value not in (None, "", 0, [], {}):
            return value
    return default


def _year_of(value: Any) -> str:
    """从日期 / 年份串里取四位年份（``2026-09-23`` → ``2026``）。"""
    matched = re.match(r"\s*(\d{4})", str(value or ""))
    return matched.group(1) if matched else ""


def _actor_avatar(raw: Dict[str, Any]) -> str:
    """演员头像：从宿主 / 数据源给的几种形体里取第一个非空地址。

    顺序：``profile_path``（宿主通用形体）→ ``profile`` / ``poster`` / ``img``
    / ``image``（数据源自有写法）→ ``avatar`` / ``images``（字符串或
    ``{large, medium, small, url, src}`` 字典）。

    ⚠️ 现役数据源的 ``people`` 行会给 ``profile_path``（站点图床按身份现拼，零请求）；
    个别条目不给我就留空（前端出人形占位），不再按身份回查档案补图。
    """
    for key in ("profile_path", "profile", "poster", "img", "image"):
        value = _clean_text(raw.get(key))
        if value:
            return value
    for key in ("avatar", "images"):
        value = raw.get(key)
        if isinstance(value, str):
            text = _clean_text(value)
            if text:
                return text
        if isinstance(value, dict):
            picked = _clean_text(
                value.get("large")
                or value.get("medium")
                or value.get("small")
                or value.get("url")
                or value.get("src")
            )
            if picked:
                return picked
    return ""


#: TMDB 条目地址（宿主 ``MediaDetailView.vue::getTheMovieDbLink()`` 同款拼法）
_TMDB_PAGE = "https://www.themoviedb.org/{type}/{id}"


def tmdb_page_url(tmdb_id: Any, type_name: Any = "") -> str:
    """拼 TMDB 条目地址（可单测）。
    类型映射与宿主逐字一致（``type === '电影' ? 'movie' : 'tv'``）—— 宿主详情页来源区
    那个 TheMovieDb chip 指向的就是这个地址；短剧都是电视剧，所以实际恒为 ``tv``，
    但仍然照宿主实现留着电影分支，免得将来加电影时地址拼错。

    没有合法 ID 就返回空串：宁可不出这个 chip，也不要把用户送去 ``/tv/0``。
    """
    native = _to_int(tmdb_id)
    if native <= 0:
        return ""
    kind = "movie" if _clean_text(type_name) == "电影" else "tv"
    return _TMDB_PAGE.format(type=kind, id=native)


def douban_page_url(douban_id: Any) -> str:
    """豆瓣条目地址（有 id 才拼；详情页来源区的「豆瓣」chip 用它）。

    短剧在豆瓣的覆盖率比 TMDB 高（实测同一部剧豆瓣有、TMDB 空），所以这个 chip
    比 TheMovieDb 那个更常出现。没有合法 ID 就返回空串。
    """
    text = _clean_text(douban_id)
    if not text:
        return ""
    return f"https://movie.douban.com/subject/{text}/"




#: 数据源演员页地址里的身份：``…/yanyuan/info-<数字>.html``
_ACTOR_URL_RE = re.compile(r"/([a-z]+)/info-(\d+)(?:\.html)?", re.IGNORECASE)


def actor_id_from_url(url: Any) -> str:
    """从数据源给的演员页地址反解站点身份（可单测）。

    宿主的 ``MediaCredit`` 有 ``url`` 却**没有** ``media_id``（``model_config`` 是空的，
    不接收多余键），所以数据源（短剧百科）填进 ``url`` 的演员页地址就是唯一可用的
    身份线索：``https://www.duanjubaike.net/yanyuan/info-7497….html`` → ``yanyuan:7497…``。

    反解出身份后，演员卡才能精确跳转（而不是退化成按名字匹配）与精确判重
    （同名演员是两个人）。地址形态不认识就返回空串，交给调用方按名字兜底。
    """
    text = _clean_text(url)
    if not text:
        return ""
    matched = _ACTOR_URL_RE.search(text)
    if not matched:
        return ""
    return canonical_media_id(f"{matched.group(1)}:{matched.group(2)}")


def actor_page_url(work_url: Any, actor_id: Any) -> str:
    """由作品页地址推出演员页地址（可单测）。

    只有拿到**本站域名**才拼地址：没有作品页地址时宁可不给链接 ——
    硬猜一个域名等于把用户送去不存在的页面。演员 ID 是复合形态
    ``yanyuan:<id>``，分类直接进路径；只有裸数字时按 ``yanyuan`` 兜底（本插件
    关注的是演员，导演 / 编剧不会走到这里）。
    """
    kind, native = split_media_id(actor_id)
    if not native:
        return ""
    try:
        parts = urlsplit(_clean_text(work_url))
    except ValueError:  # pragma: no cover - 非法地址
        return ""
    if not parts.scheme or not parts.netloc:
        return ""
    path = _ACTOR_PATH.format(kind=kind or "yanyuan", id=native)
    return f"{parts.scheme}://{parts.netloc}{path}"


def detail_actor_rows(
    info: Any,
    work_url: Any = "",
    followed: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """把宿主 ``MediaInfo.actors`` 投影成详情页的演员行（可单测）。

    站点给的是宿主通用形体（``id`` / ``name`` / ``character`` / ``profile_path`` /
    ``kind``），这里挑详情页要用的，并补两样宿主不提供的东西：

    * ``url`` —— 数据源演员页地址（详情页点演员能跳过去）；
    * ``subscribed`` —— 这位演员是否已在本插件的关注列表里（决定「已关注 / 关注」）。

    头像走 ``_actor_avatar`` 的多形体别名（``profile_path`` 为主）。数据源现在
    在 ``people`` 行里就给 ``profile_path``（站点图床按身份现拼，零请求），所以
    **不再需要**本插件按身份回查档案去补头像 —— 那一层已随 2026-10-19 的数据源
    更新删掉；真的拿不到就留空，前端出人形占位。

    ⚠️ 演员身份只认 ``media_id``（复合 ``yanyuan:<id>``）。宿主 ``MediaCredit.id``
    在 .net 里写的是**TMDB 人物 id**（见 NetSource ``payload`` 的 ``person_id``），
    拿它拼站点地址会 404；识别不出站点身份时留空，前端改用**名字**打开演员页
    （``/actors/detail?name=…``，数据源按名字精确匹配）。

    ``followed`` 是关注名单（名字 / ID 混合，2026-10-20 起正在向 ID 收敛）：
    ``subscribed`` **ID 优先精确匹配** —— 行带站点身份时只认 ID（同名演员是两个人，
    按名字比会把同名的另一位误标成已关注）；行没有身份（数据源没给）才退回名字。
    """
    names = followed if isinstance(followed, (set, frozenset, list, tuple)) else ()
    followed_ids = {item for item in names if _actor_id_of(item)}
    followed_names = {
        _actor_name_key(item)
        for item in names
        if _clean_text(item) and not _actor_id_of(item)
    }
    rows: List[Dict[str, Any]] = []
    seen: set = set()
    for raw in _media_attr(info, "actors", default=[]) or []:
        if not isinstance(raw, dict):
            continue
        name = _clean_text(raw.get("name"))
        if not name:
            continue
        actor_id = canonical_media_id(raw.get("media_id"))
        if not split_media_id(actor_id)[1]:
            # 宿主 ``MediaCredit`` 没有 ``media_id`` 字段，但数据源会把演员页地址
            # 填进 ``url`` —— 从那里把站点身份反解回来（2026-10-22）。
            actor_id = actor_id_from_url(raw.get("url"))
        key = actor_id or _actor_name_key(name)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "actor_id": actor_id,
                "name": name,
                "character": _clean_text(raw.get("character") or raw.get("role")),
                "profile": _clean_text(_actor_avatar(raw)),
                "kind": _clean_text(raw.get("kind")),
                "url": actor_page_url(work_url, actor_id),
                "subscribed": (actor_id in followed_ids)
                if actor_id
                else (_actor_name_key(name) in followed_names),
            }
        )
    return rows


def project_media_detail(
    info: Any,
    media_id: Any,
    followed: Optional[Any] = None,
) -> Dict[str, Any]:
    """把宿主 ``MediaInfo`` 投影成详情页的业务数据（可单测）。

    * ``url`` 取 ``homepage``（``tagline`` 兜底）；数据源两者都不写 ⇒ 退回
      :func:`site_info_url` 按「分类 + 数字」拼站点详情页地址（不拼的话详情页的
      「百科地址」与演员跳转链接都是空）；
    * ``duration_minutes`` 是**折算值**（单集 × 集数）：站点只印全集总时长，而 ``MediaInfo``
      只保留单集时长（``runtime`` / ``episode_run_time[0]``），相乘还原详情页那个「时长」；
    * ``year`` 缺了就从首播日期退一个年份 —— 详情页标题行靠它；
    * ``tmdb_id`` / ``tmdb_url`` 是**百科给的真实 TMDB 身份**（百科插件按片名 + 首播年
      严格匹配过才写；大多数短剧没有）。宿主详情页里「ID」那一行、来源区的 TheMovieDb
      chip 以及演职员 / 推荐 / 相似 / 分季四块**全部以它为前提**，所以这里原样透出，
      让自绘详情页在有身份时和系统一样能给出 TMDB 入口。
    """
    native_id = canonical_media_id(media_id) or canonical_media_id(
        _media_attr(info, "media_id")
    )
    url = _clean_text(_media_attr(info, "homepage", "tagline")) or site_info_url(native_id)
    release_date = _clean_text(_media_attr(info, "release_date", "first_air_date"))
    tmdb_id = _to_int(_media_attr(info, "tmdb_id"))
    episode_minutes = _to_int(_media_attr(info, "runtime"))
    if not episode_minutes:
        run_times = _media_attr(info, "episode_run_time", default=[]) or []
        if isinstance(run_times, (list, tuple)) and run_times:
            episode_minutes = _to_int(run_times[0])
    episode_count = _to_int(_media_attr(info, "number_of_episodes", "episode_count"))
    genres: List[str] = []
    for tag in _media_attr(info, "genres", default=[]) or []:
        name = _clean_text(tag.get("name")) if isinstance(tag, dict) else _clean_text(tag)
        if name and name not in genres:
            genres.append(name)
    studio = ""
    for company in _media_attr(info, "production_companies", default=[]) or []:
        studio = (
            _clean_text(company.get("name"))
            if isinstance(company, dict)
            else _clean_text(company)
        )
        if studio:
            break
    # 播放平台：宿主 ``MediaInfo`` 里落成 TMDB 形体 ``networks=[{"name": …}]``，
    # 数据源自己的键叫 ``platform`` —— 两种都收（见 :func:`platform_of`）
    platform = platform_of(_media_attr(info, "networks", "platform"))
    return {
        "found": True,
        "media_source": _BAIKE_SOURCE,
        "media_id": native_id,
        "title": _clean_text(_media_attr(info, "title", "name")),
        "year": _clean_text(_media_attr(info, "year")) or _year_of(release_date),
        "type": _BAIKE_TYPE,
        "overview": _clean_text(_media_attr(info, "overview")),
        "poster": _clean_text(_media_attr(info, "poster_path")),
        "backdrop": _clean_text(_media_attr(info, "backdrop_path")),
        "vote": _to_float(_media_attr(info, "vote_average")),
        # 站内统计（热度 / 播放 / 收藏）**不在这里给**：数据源作为分类事实提交的是
        # 站点原文（「380.14万」），宿主 MediaInfo 装不下 —— 前端从 ``/lookup``
        # 那一份原样显示（2026-10-23 用户口径：只要原文，不要折算数值）。
        "release_date": release_date,
        "episode_count": episode_count,
        "episode_minutes": episode_minutes,
        "duration_minutes": episode_minutes * episode_count,
        "genres": genres,
        "studio": studio,
        "platform": platform,
        "status": _clean_text(_media_attr(info, "status")),
        "language": _clean_text(_media_attr(info, "original_language", "in_language")),
        "url": url,
        "tmdb_id": tmdb_id,
        "tmdb_url": tmdb_page_url(tmdb_id, _BAIKE_TYPE),
        # 豆瓣身份（数据源匹配到的；短剧在豆瓣的覆盖率比 TMDB 高）。
        # 有它前端才能去宿主的 /api/v1/douban/* 取短评与影评 —— 系统详情页那两块
        # 也是靠 douban_id 才有内容。
        "douban_id": _clean_text(_media_attr(info, "douban_id")),
        "douban_url": douban_page_url(_clean_text(_media_attr(info, "douban_id"))),
        "actors": detail_actor_rows(info, url, followed),
    }


def merge_detail_row(
    data: Dict[str, Any],
    row: Optional[Dict[str, Any]],
    in_library: Optional[bool] = None,
) -> Dict[str, Any]:
    """把「墙上那一行」并进详情（就地改 ``data`` 并返回，可单测）。

    两件事，方向刻意分开：

    * **补空**：详情投影缺字段时才拿卡上的值兜底（标题 / 年份 / 海报 / 百科地址 /
      出品方 / 播放平台 / 首播 / 题材 / 评分 / 集数）—— 站点详情页没解析出来的，
      卡上印的就是唯一来源；
    * **补宿主没有的**：热度 / 播放量 / 真人·AI / 首次发现 / 是否新 / 在库状态 ——
      这些字段 ``MediaInfo`` 里根本没有，只能从快照那一行取。
    """
    if not isinstance(row, dict):
        return data
    for field in ("title", "year", "poster", "url", "studio", "platform", "release_date"):
        value = _clean_text(row.get(field))
        if value and not _clean_text(data.get(field)):
            data[field] = value
    # 标题特例（2026-10-23 用户反馈）：站点详情页常丢季标 —— 季2 详情页叫
    # 「隐身侍卫」，列表行却叫「隐身侍卫第二季」，点进详情标题"缩水"回季1 的名字。
    # 行标题比详情标题**更具体**（详情标题是行标题的前缀）时以行为准：卡片上
    # 印的什么，详情页就叫什么；反向（详情更具体）不动。
    detail_title = _clean_text(data.get("title"))
    row_title = _clean_text(row.get("title"))
    if row_title and detail_title and detail_title != row_title:
        if row_title.startswith(detail_title):
            data["title"] = row_title
    if not data.get("genres"):
        data["genres"] = [tag for tag in (row.get("genres") or []) if _clean_text(tag)]
    if not _to_float(data.get("vote")):
        data["vote"] = _to_float(row.get("vote"))
    if not _to_int(data.get("episode_count")):
        data["episode_count"] = _to_int(row.get("episode_count"))
    # 热度 / 播放量 / 收藏**不进详情**：快照那两列恒为 0（人物页卡片不印），
    # 真值是站点原文（「380.14万」），由前端从 ``/lookup`` 原样显示。
    data["kind"] = _clean_text(row.get("kind"))
    data["first_seen"] = _clean_text(row.get("first_seen"))
    data["is_new"] = bool(row.get("is_new"))
    data["in_library"] = in_library
    return data


def filter_works(
    rows: List[Dict[str, Any]],
    *,
    actor: str = "",
    genre: str = "",
    year: str = "",
    studio: str = "",
    platform: str = "",
    only_not_in_library: bool = False,
    only_not_subscribed: bool = False,
    subscribed: Optional[Iterable[str]] = None,
    keyword: str = "",
) -> List[Dict[str, Any]]:
    """按查询条件过滤作品行（纯函数，可单测）。

    所有条件都是「空 = 不参与筛选」；演员命中口径与前端的演员 chip 一致 ——
    同一部剧多位演员参演时行里的 ``actor`` 是「A / B」，命中任一即可。

    ``only_not_in_library`` 只排除**明确已在库**的行（``in_library`` 为 ``True``）；
    「未知」（字段缺失 / 查库失败）的行**保留** —— 任何一处把「没查成」塌缩成
    「都不在库」，都会让异常被显示成结论。

    ``only_not_subscribed`` 排除**已订阅**的行（``subscribed`` 给的是订阅清单的
    media_id 集合；不给这个集合时该条件不生效，不静默当「都没订阅」）。
    """
    word = normalize_title(keyword)
    subscribed_ids = {str(item).strip() for item in (subscribed or []) if str(item).strip()}
    result: List[Dict[str, Any]] = []
    for row in rows:
        if only_not_subscribed and subscribed_ids:
            if _clean_text(row.get("media_id")) in subscribed_ids:
                continue
        if actor:
            owners = [item.strip() for item in str(row.get("actor") or "").split(" / ")]
            if actor not in owners and actor != row.get("actor_key"):
                continue
        if genre and genre not in (row.get("genres") or []):
            continue
        if year and _clean_text(row.get("year")) != year:
            continue
        if studio and _clean_text(row.get("studio")) != studio:
            continue
        if platform and _clean_text(row.get("platform")) != platform:
            continue
        if only_not_in_library and row.get("in_library") is True:
            continue
        if word and word not in normalize_title(row.get("title") or ""):
            continue
        result.append(row)
    return result


def sort_works(rows: List[Dict[str, Any]], mode: str = _DEFAULT_SORT) -> List[Dict[str, Any]]:
    """按首播日期排序（纯函数，可单测）。

    2026-10-23 用户口径：**只保留发布日期**（新剧在前）—— 热度 / 播放 / 评分三种
    排序撤掉：那些数值在作品墙快照里恒为 0（人物页卡片不印统计 / 评分也不是每部都有），
    排出来全是并列，等于假排序。

    缺日期的排最后；同值时按剧名排序，保证顺序稳定可预期（Python 的 ``sort`` 是
    稳定排序），不必为「日期降序但空值垫底」写特殊的可比较键。
    """
    field, _kind = _SORT_FIELDS.get(_clean_text(mode)) or _SORT_FIELDS[_DEFAULT_SORT]
    ordered = sorted(rows, key=lambda row: normalize_title(row.get("title") or ""))
    # ``YYYY-MM-DD`` 的字典序就是时间序；空串最小，降序后自然落到末尾
    ordered.sort(key=lambda row: _clean_text(row.get(field)) or "", reverse=True)
    return ordered


def build_facets(rows: List[Dict[str, Any]], limit: int = 60) -> Dict[str, Any]:
    """算筛选项（纯函数，可单测）：类型 / 年份 / 版权方 / 播放平台，各项带作品数。

    基于**筛选前**的全集计算 —— 选项不随用户勾选跳动。某项一条数据都没有时天然
    不在列表里：版权方 / 播放平台在数据源补齐之前就是空数组，前端据此隐藏该筛选项
    （同理，这两项也不该拿「未知」占位凑数）。
    """
    genres: Dict[str, int] = {}
    years: Dict[str, int] = {}
    studios: Dict[str, int] = {}
    platforms: Dict[str, int] = {}
    for row in rows:
        for tag in row.get("genres") or []:
            genres[tag] = genres.get(tag, 0) + 1
        year = _clean_text(row.get("year"))
        if year:
            years[year] = years.get(year, 0) + 1
        studio = _clean_text(row.get("studio"))
        if studio:
            studios[studio] = studios.get(studio, 0) + 1
        platform = _clean_text(row.get("platform"))
        if platform:
            platforms[platform] = platforms.get(platform, 0) + 1

    def top(counter: Dict[str, int], key: Any) -> List[Dict[str, Any]]:
        return [
            {"value": name, "count": count}
            for name, count in sorted(counter.items(), key=key)[:limit]
        ]

    return {
        "genres": top(genres, lambda kv: (-kv[1], kv[0])),
        # 年份：新的在前
        "years": top(
            years, lambda kv: (-_to_int(kv[0]), kv[0])
        ),
        "studios": top(studios, lambda kv: (-kv[1], kv[0])),
        "platforms": top(platforms, lambda kv: (-kv[1], kv[0])),
    }


# ─────────────────────────── 媒体库在库探针 ───────────────────────────


def _media_server_oper() -> Any:
    """惰性拿宿主的媒体服务器库操作对象（见 :class:`_LibraryProbe` 的取舍说明）。"""
    from app.db.oper.mediaserver import MediaServerOper

    return MediaServerOper()


#: 季标片段：``第X季`` / ``第X部`` / ``Season X`` / ``S X``（X = 汉字数字或阿拉伯数字）。
#: 演员作品列表里续作标题带季标（实例：百科季2 行叫「隐身侍卫第二季」），而媒体库
#: 常把多季挂在同一个基础名条目下（Emby「隐身侍卫」seasoninfo={1,…,2,…}）⇒ 精确
#: 标题匹配会漏掉续作。探针在精确未中后剥掉季标、按「基础名 + 季号」再查一次，
#: 存在性由宿主 ``exists(season=…)`` 用库条目的 seasoninfo 校验（季不存在 = 不在库）。
_SEASON_MARK_RE = re.compile(
    r"第\s*([0-9一二三四五六七八九十]{1,3})\s*[季部]"
    r"|season\s*(\d{1,2})"
    r"|\bs\s*(\d{1,2})\b",
    re.IGNORECASE,
)

#: 汉字数字 → int（季号只需覆盖 一~九十九）
_CN_DIGITS = {
    "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}

#: 裸数字季标：**汉字后面紧跟的 1~2 位结尾数字**（实例：「隐身侍卫2」→ 隐身侍卫 S2）。
#: 前一个字符必须是汉字——「重生1982」这类年份尾巴（数字后面还是数字）不会命中：
#: 结尾的「82」前面是「9」不是汉字，整个标题没有「汉字+短数字+结尾」的形态。
_TRAILING_NUM_RE = re.compile(r"([\u4e00-\u9fff])\s*(\d{1,2})$")


def _season_number(text: str) -> Optional[int]:
    """季标里的数字：``2`` / ``二`` → 2，``十二`` → 12；认不出返回 ``None``。"""
    text = text.strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if text == "十":
        return 10
    if "十" in text:
        left, _, right = text.partition("十")
        if left and left not in _CN_DIGITS:
            return None
        if right and right not in _CN_DIGITS:
            return None
        # 「十二」以十开头：left 空 ⇒ 十位是 1（十二=12，不是 102）；「二十」left=二 ⇒ 20
        return (1 if not left else _CN_DIGITS[left]) * 10 + (
            0 if not right else _CN_DIGITS[right]
        )
    return _CN_DIGITS.get(text)


def _split_season_title(title: str) -> Tuple[str, Optional[int]]:
    """从标题剥出季号：返回 ``(基础标题, 季号)``；没有季标则 ``(原标题, None)``。

    两级：先认**后缀**位置的显式季标（``第X季`` / ``第X部`` / ``Season X``），
    认不出再看**裸数字后缀**——汉字后面紧跟的 1~2 位结尾数字（「隐身侍卫2」）。
    季标必须是标题结尾：戳在中间的不算（实例：「Season 3 之谜」不该剥成「之谜」）。
    """
    title = title.strip()
    marks = [
        mark
        for mark in _SEASON_MARK_RE.finditer(title)
        if mark.end() == len(title)  # 季标是后缀（strip 过的标题结尾）
    ]
    if marks:
        mark = marks[-1]
        raw = mark.group(1) or mark.group(2) or mark.group(3)
        season = _season_number(raw or "")
        if season:
            base = title[: mark.start()].strip()
            # 剥完剩下的还得像个体面标题（非空），否则宁可不剥
            if base and _clean_text(base):
                return base, season
        return title, None
    # 裸数字后缀（「隐身侍卫2」）：汉字 + 1~2 位数字收尾。年份尾巴（「重生1982」）
    # 结构对不上（结尾数字前还是数字），天然不误剥。
    tail = _TRAILING_NUM_RE.search(title)
    if tail:
        season = int(tail.group(2))
        if season >= 1:
            base = title[: tail.start(1) + 1].strip()
            if base and _clean_text(base):
                return base, season
    return title, None


class _LibraryProbe:
    """「这部作品是否已在媒体库」的探针 —— **只按剧名判定**（2026-10-23 用户拍板）。

    走宿主 ``MediaServerOper().get_item_id(title=…, mtype=…)``，落在
    ``exists_by_title`` 分支：标题精确相等（+ 可选类型过滤），**年份与媒体身份
    都不参与** —— 短剧场景下这两条路是断的：

    * 年份：百科列表行不带年份（只在详情页，逐条现查代价太大），媒体库条目的
      year 也常是空 ⇒ 宿主跨来源回退的「标题+年份双全」永远凑不齐；
    * 身份：库表条目以别的来源（tmdb/douban/手动）入库，``djbaike:duanju`` 号
      永远对不上 ``exist_by_media_identity``。

    类型过滤保留（作品行恒为 电视剧）：挡住同名电影的误判。

    **续作兜底**：标题精确未中且标题带季标（``第X季`` 等）时，剥掉季标按
    「基础名 + 季号」再查 —— 存在性由宿主 ``exists(season=…)`` 用库条目的
    seasoninfo 校验（实例：百科「隐身侍卫第二季」→ 库条目「隐身侍卫」S2 在）。
    库里只有季1 时季2 依旧正确判「不在」。

    这里刻意复用宿主自己的 ``MediaServerOper``，而不是自己写 SQL 或走
    ``app.sdk`` 的 ``media_exists``（那是远程问 Emby/Plex，慢且语义不同）：判定
    走的还是宿主自己的本地库表匹配代码，口径随宿主版本演进的细节都由宿主保证。
    调用失败（宿主版本差异、事务执行器未就绪等）一律返回 ``None``（未知），
    绝不当成「不在库」——否则一次异常就会让整面墙看起来都没入库。

    结果带 **TTL 缓存**：作品墙每次打开都要现算（``in_library`` 和 ``is_new`` 一样
    不落盘），同一位演员的作品集变化不快，600 秒内重复打开墙面零查询。
    """

    #: 缓存有效期（秒）；过期后重新查库 —— 「不在库」的结论必须能被后续入库推翻
    CACHE_TTL = 600.0

    #: 缓存条目上限。key 含片名与年份，作品改名 / 年份补齐都会生成新 key 而旧 key 不释放；
    #: 真机作品墙已 2 300+ 部且随演员增加而涨，所以必须有闸门：越过就整体清一次
    #: （每条都只值一次 `get_item_id` 的省下，清空代价可忽略，但绝不能让它无限涨）。
    CACHE_MAX_ENTRIES = 20000

    def __init__(self) -> None:
        self._oper: Any = None
        self._disabled = False
        # key -> (True/False, 缓存时刻)；None 表示「查不了」，也缓存（免得反复撞同一个错误）
        self._cache: Dict[Tuple[str, str, str, str, str], Tuple[Optional[bool], float]] = {}
        self.last_error = ""

    def _ensure_oper(self) -> Any:
        """惰性导入宿主的库操作对象；不可用时只记录一次并停用后续尝试。"""
        if self._oper is not None or self._disabled:
            return self._oper
        try:
            self._oper = _media_server_oper()
        except Exception as err:  # pragma: no cover - 宿主版本差异兜底
            self._disabled = True
            self.last_error = str(err)
            logger.warning(f"{PLUGIN_NAME} 媒体库存在性检查不可用，本轮不标注入库状态：{err}")
        return self._oper

    @staticmethod
    def _cache_key(work: Dict[str, Any]) -> Tuple[str, str, str, str, str]:
        return (
            str(work.get("media_source") or ""),
            str(work.get("media_id") or ""),
            str(work.get("type") or ""),
            str(work.get("title") or ""),
            str(work.get("year") or ""),
        )

    def clear(self) -> None:
        """清空 TTL 缓存（插件禁用 / 重载时调用，别把旧结论带进下一次运行）。"""
        self._cache.clear()

    @property
    def available(self) -> bool:
        """判定通道是否可用（宿主 Oper 没有被之前的异常熔断掉）。

        「只看未入库」开关的展示依据 —— 通道不可用时开了也只会把全部作品当
        「未知」保留，筛不出任何东西。
        """
        return not self._disabled and self._ensure_oper() is not None

    def peek_cached(
        self, work: Dict[str, Any], now: Optional[float] = None
    ) -> Optional[bool]:
        """只读 TTL 缓存，**不触发查询**：有新鲜结论给 True/False，否则 None。

        供统计口径用 —— 作品墙改为「展示谁判谁」后，全集的统计只能报缓存里
        已有的结论，绝不能为了凑数字把全量查询又跑一遍。
        """
        key = self._cache_key(work)
        stamp = time.time() if now is None else now
        cached = self._cache.get(key)
        if cached is not None and stamp - cached[1] < self.CACHE_TTL:
            return cached[0]
        return None

    def lookup(self, work: Dict[str, Any], now: Optional[float] = None) -> Optional[bool]:
        """查询单个作品：``True`` 在库 / ``False`` 不在库 / ``None`` 未知（查不了）。

        ``now`` 仅供单测注入时钟。
        """
        key = self._cache_key(work)
        stamp = time.time() if now is None else now
        cached = self._cache.get(key)
        if cached is not None and stamp - cached[1] < self.CACHE_TTL:
            return cached[0]
        flag = self._lookup_uncached(work)
        if len(self._cache) >= self.CACHE_MAX_ENTRIES:
            self._cache.clear()
        self._cache[key] = (flag, stamp)
        return flag

    def _lookup_uncached(self, work: Dict[str, Any]) -> Optional[bool]:
        if self._disabled:
            # 之前失败过：本轮所有作品都是「未知」，不再反复触库刷警告
            return None
        title = str(work.get("title") or "").strip()
        if not title:
            return None
        oper = self._ensure_oper()
        if oper is None:
            return None
        # ── 只按剧名判定（2026-10-23 用户拍板：剧名是**唯一**判据）──
        # 走宿主 ``exists_by_title`` 分支（标题精确相等）。年份不参与 —— 短剧两头
        # 都断：百科列表行不带年份（年份只在详情页，逐条现查代价太大），媒体库
        # 条目的 year 也常是空（实例：《跟我玩茶香四溢，真千金她拳拳暴击》《重生
        # 1982，岳父一家上门逼婚》两侧年份皆空）。媒体身份（djbaike:duanju 号）也
        # 不参与 —— 库表条目以别的来源入库，身份永远对不上。仍带**类型过滤**
        # （作品行恒为 电视剧，库条目同为 电视剧）：挡住同名电影的误判；若发现
        # 有剧在库里被存成别的类型再放宽。
        try:
            item_id = oper.get_item_id(
                title=title,
                mtype=str(work.get("type") or "").strip() or None,
            )
        except Exception as err:  # pragma: no cover - 宿主机内差异兜底
            self._disabled = True
            self.last_error = str(err)
            logger.warning(f"{PLUGIN_NAME} 媒体库存在性检查失败，后续作品不再查询：{err}")
            return None
        # ── 续作兜底：剥掉季标，按「基础名 + 季号」再查一次 ──
        # 续作行标题带季标（实例：百科季2 行叫「隐身侍卫第二季」），而媒体库常把
        # 多季挂在同一个基础名条目下（Emby「隐身侍卫」seasoninfo={1,…,2,…}）⇒
        # 精确标题匹配漏掉续作。剥标后交给宿主 ``exists(season=…)``：命中条目且
        # 其 seasoninfo 含该季才算在库 —— 库里只有季1 时，季2 依然正确判「不在」。
        if not item_id and title:
            base_title, season = _split_season_title(title)
            if season and base_title and base_title != title:
                try:
                    item_id = oper.get_item_id(
                        title=base_title,
                        mtype=str(work.get("type") or "").strip() or None,
                        season=season,
                    )
                except Exception as err:  # pragma: no cover - 宿主机内差异兜底
                    # 主查询已成功过，兜底失败不熔断 —— 按未命中处理
                    logger.warning(
                        f"{PLUGIN_NAME} 季标兜底查询失败（{title} → {base_title} S{season}）：{err}"
                    )
        # 宿主返回的是媒体服务器的 item_id 字符串；空值即「本地没有这条」
        return bool(str(item_id or "").strip())



# ─────────────────────────── 插件 ───────────────────────────

# 在库探针**后台预热**闸门：作品墙页模式只判展示页，头部「已入库 N 部」在冷缓存时
# 只能报缓存里已有的结论（表现为「已入库 0 部」）。预热线程在后台把全集判一遍
# （真机 4600+ 部 ≈ 5 秒，结果进探针 TTL 缓存），统计随即变准 —— 用户不感知。
_PROBE_WARMING = threading.Event()


def _start_probe_warm(plugin: "ShortDramaActorSubscribe") -> None:
    """启动一次在库全集预热（已在跑 / 通道不可用时直接返回）。"""
    if _PROBE_WARMING.is_set() or not plugin.library_probe.available:
        return
    _PROBE_WARMING.set()

    def _warm() -> None:
        try:
            plugin._work_rows({"only_not_in_library": "1"}, with_probe=True)
            logger.info(f"{PLUGIN_NAME} 在库探针预热完成")
        except Exception as err:  # noqa: BLE001 - 预热失败不影响主流程
            logger.warning(f"{PLUGIN_NAME} 在库探针预热失败：{err}")
        finally:
            _PROBE_WARMING.clear()

    threading.Thread(target=_warm, daemon=True, name="sdas-probe-warm").start()


# ── 前端联邦产物目录（破缓存） ─────────────────────────────────────────
# 宿主给联邦入口拼的 URL 是 /plugin/file/<id>/<dist 目录>/remoteEntry.js?v=<plugin_version>；
# 测试阶段版本号冻结（?v= 不变），浏览器强缓存 / Service Worker 会一直复用旧 remoteEntry.js。
# 于是把产物目录名当缓存键：前端有实质改动就递增 vite.config.ts 里的 ASSETS_DIR（a1 → a2…），
# URL 随之变化 → 缓存天然失效，版本号仍可冻结。这里动态扫 dist/ 下序号最大且含
# remoteEntry.js 的 a<N> 目录；找不到（老产物 / 首次构建前）退回平铺的 dist/assets。
_FRONTEND_DIST_FALLBACK = "dist/assets"
_BUILD_DIR_RE = re.compile(r"a(\d+)")


def _frontend_dist() -> str:
    """返回 Vue 联邦产物目录（相对插件根），取 ``dist/`` 下序号最大的 ``a<N>`` 目录。"""
    try:
        base = Path(__file__).resolve().parent / "dist"
        best: Optional[Tuple[int, str]] = None
        for child in base.iterdir():
            if not child.is_dir():
                continue
            matched = _BUILD_DIR_RE.fullmatch(child.name)
            if not matched:
                continue
            # 只认里面有 remoteEntry.js 的目录，避免半成品目录把路径带偏
            if not (child / "remoteEntry.js").exists():
                continue
            order = int(matched.group(1))
            if best is None or order > best[0]:
                best = (order, child.name)
        return f"dist/{best[1]}" if best else _FRONTEND_DIST_FALLBACK
    except Exception:  # noqa: BLE001 - 目录扫描失败不该影响插件主功能
        return _FRONTEND_DIST_FALLBACK


class ShortDramaActorSubscribe(_PluginBase):
    """按演员发现短剧作品，订阅交回宿主订阅系统。"""
    # ── 插件元数据（需与 package.v3.json 保持一致） ──
    # 注意：plugin_name / plugin_icon 必须是**字符串字面量**，不能引用模块常量 ——
    # 宿主的部分离线安装工具用 AST 静态解析插件类，只认 ast.Constant。
    plugin_name = "短剧演员订阅"
    plugin_desc = (
        "跟着喜欢的演员追短剧：填演员名，插件从短剧百科（duanjubaike.net）取回他们的全部作品，"
        "摆成和「探索」页同形的海报墙；看中哪部点「订阅」，走的就是 MoviePilot 自己的订阅系统"
        "（搜索、下载、整理全部由系统负责）。作品墙按演员筛选，新作品自动标「新」。"
    )
    plugin_icon = (
        "https://raw.githubusercontent.com/m215owen/MoviePilot-Plugins/main/"
        "icons/ShortDramaActorSubscribe.png"
    )
    plugin_version = "1.0.0"
    plugin_author = "m215owen"
    author_url = "https://github.com/m215owen"
    plugin_config_prefix = "shortdramaactorsubscribe_"
    plugin_order = 55
    auth_level = 1

    # ── 运行时状态（⚠️ 全部在 init_plugin 里重新赋值，避免跨实例串味） ──
    _enabled = False
    _onlyonce = False
    _actors: List[str] = []
    _interval_hours = 12
    _retry_minutes = _DEFAULT_RETRY_MINUTES
    _notify = True
    _sidebar_nav = True
    # 资源搜索站点：逗号分隔的站点 ID（空 = 不限定，走宿主默认）
    _search_sites = ""
    # 订阅下载器：宿主下载客户端的名字（空 = 跟随系统默认）。
    # 作品墙提交订阅时由前端取用；**自动订阅**也用它（见 ``_add_subscribe``）。
    _subscribe_downloader = ""
    # 订阅站点：逗号分隔的站点 ID（空 = 跟随宿主订阅默认）。只作用于「提交订阅」，
    # 与上面 ``_search_sites``（作品墙点「搜索」跳资源页）是两件事，互不影响。
    _subscribe_sites = ""
    # 订阅下载目录：宿主 `/download/paths` 给出的 save_path（空 = 跟随宿主订阅默认）。
    # 自动订阅、批量订阅都带上它（见 ``_add_subscribe``）。
    _subscribe_save_path = ""
    # 订阅类型（宿主 ``Subscribe.best_version`` 口径）：
    #   * ``follow``（默认）—— 不传 kwargs，跟随宿主「订阅设置」里电视剧的洗版开关；
    #   * ``normal`` —— 显式 ``best_version=0``，一律按**普通订阅**发起；
    #   * ``best`` —— 显式 ``best_version=1``，一律按**洗版订阅**发起。
    # 手动订阅（前端直连 `/subscribe/`）、自动订阅、订阅全部作品三处共用（见 ``_add_subscribe``）。
    _subscribe_mode = "follow"
    # 自动订阅：把关注演员的作品直接交给宿主订阅链。
    #   * ``_auto_subscribe`` 开关（默认关 —— 订阅会触发下载，必须用户自己打开）；
    #   * ``_auto_subscribe_scope``：``new`` 只订「演员加入之后新出现的」（默认）/
    #     ``all`` 连历史作品一起（首次打开就会把整面墙都订上，慎用）；
    #   * ``_auto_subscribe_max_per_run``：单轮上限（见 ``_AUTO_SUB_DEFAULT_MAX``）；
    #   * ``_auto_subscribe_skip_library``：已在媒体库的跳过（默认开）。
    _auto_subscribe = False
    _auto_subscribe_scope = "new"
    _auto_subscribe_max_per_run = _AUTO_SUB_DEFAULT_MAX
    _auto_subscribe_skip_library = True
    # ⚠️ 下面两个锁在这里只是**占位**，真正的实例在 ``init_plugin`` 里重建：
    # 留在类属性上会被同一份源码的多个运行实例（虚拟分身 / 重载后的旧新实例）共用，
    # 表现为互相误判成「已有刷新在跑」而静默跳过整轮 —— 文档要求运行时容器按运行实例隔离。
    #   * ``_lock``：整轮刷新 / 失败重试 / 远程命令 / 手动刷新的**互斥**（别让两轮同时打百科）；
    #   * ``_snapshot_lock``：演员快照「读 → 改 → 写」的**原子性**（添加/移除演员与刷新任务
    #     会并发改同一份快照，整体覆盖写会把对方刚写的 key 抹掉）。
    _lock: Optional[Any] = None
    _snapshot_lock: Optional[Any] = None
    # 进程内缓存（作品在 v5 起随快照落盘，这里只是本轮/短时复用；档案始终不落盘）：
    #   * ``_works_cache``：actor_key → (works[], 写入时刻)，TTL = ``_WORKS_CACHE_TTL``；
    #   * ``_profile_cache``：actor_key → (profile{}, 写入时刻)，TTL = ``_PROFILE_CACHE_TTL``。
    # 与锁同理，必须在 ``init_plugin`` 里重建 —— 类属性字典会跨运行实例串味。
    _works_cache: Optional[Dict[str, Any]] = None
    _profile_cache: Optional[Dict[str, Any]] = None

    def __init__(self) -> None:
        super().__init__()
        self._actors = []
        self._lock = threading.Lock()
        self._snapshot_lock = threading.Lock()
        self._works_cache = {}
        self._profile_cache = {}
        #: 运行标志：``stop_service()`` 置 False，正在跑的整轮发现在下一位演员之前退出
        self._running = False
        #: 上一轮自动订阅结果 ``(成功, 库里已有跳过, 失败)``，任务日志用
        self._last_auto_subscribe: Tuple[int, int, int] = (0, 0, 0)
        #: 自建订阅搜索的独立锁（与发现任务互不阻塞，但同一时刻只跑一轮搜索）
        self._sub_lock = threading.Lock()

    # ── 生命周期 ──

    def init_plugin(self, config: Optional[Dict[str, Any]] = None) -> None:
        """读取配置并建立运行时状态；必须允许重复调用。"""
        config = config or {}
        # 锁与进程内缓存都按实例重建（见类属性处的说明）；重载后旧实例的
        # 锁/缓存不会拖住新实例（作品在快照里、档案冷掉重新取即可）
        self._lock = threading.Lock()
        self._snapshot_lock = threading.Lock()
        self._sub_lock = threading.Lock()
        self._works_cache = {}
        self._profile_cache = {}
        self._running = True
        self._last_auto_subscribe = (0, 0, 0)
        self._enabled = bool(config.get("enabled"))
        self._onlyonce = bool(config.get("onlyonce"))
        self._actors = self._parse_actors(config.get("actors"))
        # 老数据迁移：关注名单 / 快照主键正从「名字」向「演员 ID」收敛（2026-10-20，
        # ID 是唯一身份）。这里把快照里已带 ID 的记录换键、配置里的名字同步换成 ID；
        # 还没解析到 ID 的演员保持名字键，下一轮发现解析到后由同一函数归位。
        self._rekey_actors()
        self._interval_hours = max(1, _to_int(config.get("interval_hours")) or 12)
        self._retry_minutes = max(
            1, _to_int(config.get("retry_minutes")) or _DEFAULT_RETRY_MINUTES
        )
        self._notify = _to_bool(config.get("notify"), True)
        self._sidebar_nav = _to_bool(config.get("sidebar_nav"), True)
        self._search_sites = self._parse_site_ids(config.get("search_sites"))
        self._subscribe_downloader = _clean_text(config.get("subscribe_downloader"))
        self._subscribe_sites = self._parse_site_ids(config.get("subscribe_sites"))
        self._subscribe_save_path = _clean_save_path(config.get("subscribe_save_path"))
        mode = _clean_text(config.get("subscribe_mode")).lower()
        self._subscribe_mode = mode if mode in ("follow", "normal", "best") else "follow"
        # 优选条件（2026-10-23 用户口径）：同一部剧搜到多条时选哪条 ——
        # 按做种数（默认，越多越稳）或按大小（大 / 小均可配；
        # 旧值 "size" 归一为 size_desc = 体积最大）
        prefer = _clean_text(config.get("subscribe_prefer")).lower()
        if prefer == "size":
            prefer = "size_desc"
        self._subscribe_prefer = (
            prefer if prefer in ("seeders", "size_desc", "size_asc") else "seeders"
        )
        self._auto_subscribe = _to_bool(config.get("auto_subscribe"), False)
        scope = _clean_text(config.get("auto_subscribe_scope")).lower()
        self._auto_subscribe_scope = scope if scope in ("new", "all") else "new"
        self._auto_subscribe_max_per_run = max(
            1,
            min(
                _AUTO_SUB_MAX_LIMIT,
                _to_int(config.get("auto_subscribe_max_per_run"))
                or _AUTO_SUB_DEFAULT_MAX,
            ),
        )
        self._auto_subscribe_skip_library = _to_bool(
            config.get("auto_subscribe_skip_library"), True
        )
        # 自建订阅搜索（2026-10-22）：engine=host 走宿主订阅链（旧行为）；
        # engine=self 由插件自己全分类搜索 + 择优下载（绕开站点分类错位）。
        # 2026-10-23 用户口径：宿主订阅链路整套去除 —— 订阅引擎恒为**自建**
        # （配置里的 ``subscribe_engine`` 只为兼容旧配置保留，不再参与分流）
        self._subscribe_engine = "self"
        self._self_interval_hours = max(
            1, _to_int(config.get("self_interval_hours")) or _SUB_SEARCH_DEFAULT_HOURS
        )
        self._self_max_per_run = max(
            1,
            min(
                _SUB_SEARCH_MAX_LIMIT,
                _to_int(config.get("self_max_per_run")) or _SUB_SEARCH_DEFAULT_MAX,
            ),
        )
        self._self_max_pages = max(
            1,
            min(
                _SUB_SEARCH_MAX_PAGES,
                _to_int(config.get("self_max_pages")) or _SUB_SEARCH_DEFAULT_PAGES,
            ),
        )

        if self._onlyonce:
            self._add_once_job(delay_seconds=3, trigger="once")
            # 立即执行是「一次性」语义，落库时清掉开关，避免每次重载都触发
            self._onlyonce = False
            self.update_config(self._live_config())
            logger.info(f"{PLUGIN_NAME} 已登记立即运行一次任务")
            # 自建订阅引擎打开时，紧跟着也跑一轮订阅搜索（配置保存后马上能见效）
            if self._subscribe_engine == "self":
                self._add_once_job(
                    delay_seconds=15,
                    trigger="once",
                    func=self.subscribe_search_task,
                    job_id=_ONCE_SUB_JOB_ID,
                )

    def get_state(self) -> bool:
        """返回插件当前是否启用。"""
        return self._enabled

    def stop_service(self) -> None:
        """释放插件创建的后台资源。

        * ``_running = False`` —— 正在跑的整轮发现会在当前演员解析完成后退出循环
          （``_refresh_actors`` 里有检查点），不必等几十位演员全部抓完；
        * 清掉媒体库探针与它的 TTL 缓存 —— 插件禁用/重载后实例若被复用，
          不该拿上一轮的「在库/不在库」结论作答；
        * 清掉进程内作品 / 档案缓存 —— 同理，别把上一轮的内容带进下一次运行。
        """
        self._running = False
        for cache in (self._works_cache, self._profile_cache):
            if isinstance(cache, dict):
                cache.clear()
        probe = getattr(self, "_probe", None)
        clear = getattr(probe, "clear", None)
        if callable(clear):
            clear()
        self._probe = None

    # ── 数据源（跨插件取数） ──

    def source_modules(self) -> Dict[str, Any]:
        """绑定数据源插件（``ShortDramaBaikeScraper``）暴露的模块方法表。

        为什么不用 ``self.chain.run_module``：宿主分发器对**返回列表**的模块方法做
        **跨插件合并**（每个插件的返回都拼进同一个列表，见
        ``dispatcher._execute_plugin_provider_sequence``），宿主里装着别的短剧数据源时
        ``search_actors`` / ``actor_works`` 会把别家的候选混在一起 ——
        同名演员可能被配成另一个站的号。这里按**插件 id** 精确取那一份方法表。

        取数走宿主公开投影 ``PluginManager.get_plugin_modules(pid)``
        （``{(plugin_id, plugin_name): {method: callable}}``，只含**已启用**插件）；
        未安装 / 已停用 / 没登记该方法 ⇒ 表里没有，由 :meth:`_source` 抛
        ``_SourceUnavailable``（端点回 503，面板给一句人话）。
        """
        try:
            from app.sdk.plugin import PluginManager
        except Exception as err:  # noqa: BLE001 - 宿主版本差异
            logger.warning(f"{PLUGIN_NAME} 宿主未提供插件管理器：{err}")
            return {}
        try:
            manager = PluginManager()
            try:
                catalog = manager.get_plugin_modules(_SOURCE_PLUGIN_ID) or {}
            except TypeError:  # 老版本不收 pid：取全量再自己筛
                catalog = manager.get_plugin_modules() or {}
        except Exception as err:  # noqa: BLE001 - 管理器内部异常不该把端点打成 500
            logger.warning(f"{PLUGIN_NAME} 取数据源模块表失败：{err}")
            return {}
        for (plugin_id, _name), table in catalog.items():
            if plugin_id == _SOURCE_PLUGIN_ID and isinstance(table, dict):
                return table
        return {}

    def _source(self, method: str, **kwargs: Any) -> Any:
        """调用数据源的模块方法（不可用时抛 :class:`_SourceUnavailable`）。"""
        func = self.source_modules().get(method)
        if not callable(func):
            raise _SourceUnavailable(
                f"{_SOURCE_LABEL} 未启用，或没有提供 {method} 模块方法"
            )
        return func(**kwargs)

    def _source_people(self, kind: str, page: int) -> Dict[str, Any]:
        """向数据源要**一页人物目录**（模块方法 ``list_people``）。

        契约（数据源按这个形状给即可，多给的键原样透传）::

            list_people(kind="yanyuan", page=1) -> {
                "kind": "yanyuan", "page": 1, "has_more": True,
                "people": [{"name": "李柯以", "media_id": "yanyuan:742922…",
                            "url": "...", "poster": "...", "gender": "女",
                            "job_title": "演员", "works_count": 0}],
            }

        站点侧对应 ``/<kind>/list.html?page=N``（24 条/页，演员约 1396 页）；
        ``kind`` 只取 :data:`_PERSON_KINDS` 里的三个。**性别 / 职业这类站点卡上
        现成的字段一并带回来**（人物目录卡上就印着「女演员」）；导演 / 编剧目录的卡
        只有名字，``gender`` / ``job_title`` 由数据源留空、这里按分类补「导演 / 编剧」。

        ⚠️ 方法缺席（数据源停用 / 旧版本）时**不报错、不抛**：回空列表 + 一句说明，
        面板把说明原样显示，等对面恢复后同一个端点自动就有数据 —— 本插件不用跟着改。
        """
        try:
            raw = self._source("list_people", kind=kind, page=page)
        except _SourceUnavailable:
            return {
                "people": [],
                "has_more": False,
                "message": f"{_SOURCE_LABEL} 还没有提供人物目录（list_people 模块方法）",
            }
        except Exception as err:  # noqa: BLE001 - 目录取不到不该让面板打不开
            logger.warning(f"{PLUGIN_NAME} 取人物目录失败（{kind} 第 {page} 页）：{err}")
            return {"people": [], "has_more": False, "message": f"人物目录获取失败：{err}"}

        if isinstance(raw, dict):
            items = raw.get("people") or raw.get("items") or []
            has_more = bool(raw.get("has_more"))
        else:
            items = raw if isinstance(raw, list) else []
            # 数据源只回了裸列表：这一页满了就当还有下一页（下一页空自然收敛）
            has_more = bool(items)

        rows: List[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = _clean_text(item.get("name"))
            if not name:
                continue
            actor_id = canonical_media_id(
                item.get("media_id") or item.get("actor_id"), default_kind=kind
            )
            rows.append(
                {
                    "name": name,
                    "kind": kind,
                    "actor_id": actor_id,
                    "media_id": actor_id,
                    "url": _clean_text(item.get("url")),
                    "profile": _clean_text(item.get("profile") or item.get("poster")),
                    "gender": _clean_text(item.get("gender")),
                    "job_title": _clean_text(item.get("job_title"))
                    or _PERSON_KIND_LABELS.get(kind, ""),
                    "works_count": _to_int(item.get("works_count")),
                }
            )
        return {"people": rows, "has_more": has_more, "message": ""}

    def _source_profile(self, actor_id: str = "", name: str = "") -> Dict[str, Any]:
        """取一位演员的档案（口径 = ``_PROFILE_FIELDS``；纯 best-effort，不抛错）。

        两条路，按可用性依次试：

        1. 数据源的 ``actor_profile``（现役数据源已提供，跨插件契约见它的 README）——
           简介 / 性别 / 国籍 / 生日 / 身高体重 / 星座 / 院校 / 爱好 / 粉丝获赞 / 代表作
           一次拿全，命中详情缓存时零站点请求；
        2. 退回 ``search_actors``：候选行自带 ``poster``（头像）与演员页地址，
           库里命中时零请求。只有头像 / 名字 / 主页，简介那一档拿不到 ——
           **拿不到就不写**，不拿别的字段硬凑。

        ``enrich=False``：作品由 ``actor_works`` 单独取，别让档案那一路白补一遍。
        """
        try:
            raw = self._source(
                "actor_profile", actor_id=actor_id, name=name, enrich=False
            )
        except _SourceUnavailable:
            if not self.source_modules():
                return {}  # 数据源整个不可用：档案不值得再打一次日志
            raw = None
        except Exception as err:  # noqa: BLE001 - 档案是锦上添花
            logger.debug(f"{PLUGIN_NAME} 取演员档案失败（{actor_id or name}）：{err}")
            raw = None
        profile = profile_fields_of(raw)
        kind = split_media_id(actor_id)[0] or "yanyuan"

        def finish(fields: Dict[str, Any]) -> Dict[str, Any]:
            # 数据源不再落 job_title（v18）：按分类 + 性别把「女演员 / 导演 / 编剧」补回来
            fields["job_title"] = person_job(
                kind, fields.get("gender"), fields.get("job_title")
            )
            return fields

        if _clean_text(profile.get("profile")):
            return finish(profile)

        # ── 退路：从演员候选里拿头像 / 主页 ──
        if not name:
            return finish(profile)
        try:
            rows = self._source("search_actors", name=name) or []
        except Exception as err:  # noqa: BLE001 - 退路失败只跳过
            logger.debug(f"{PLUGIN_NAME} 演员候选查询失败（{name}）：{err}")
            return finish(profile)
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_id = row.get("actor_id") or row.get("media_id")
            if actor_id and not same_media_id(row_id, actor_id):
                continue
            fallback = profile_fields_of(row)
            fallback.pop("works_count", None)  # 候选里的作品数是站点口径，别覆盖真实值
            for field, value in fallback.items():
                profile.setdefault(field, value)
            profile.setdefault("name", _clean_text(row.get("name")))
            break
        return finish(profile)

    # ── 配置解析 ──

    @staticmethod
    def _parse_actors(value: Any) -> List[str]:
        """解析演员配置：支持列表或逗号/换行/分号分隔的字符串，去重且保序。"""
        if isinstance(value, (list, tuple)):
            items = [str(item) for item in value]
        else:
            items = re.split(r"[,，;；\n\r]+", str(value or ""))
        result: List[str] = []
        seen: set = set()
        for item in items:
            item = _clean_text(item)
            if not item or item in seen:
                continue
            seen.add(item)
            result.append(item)
        return result

    @staticmethod
    def _parse_site_ids(value: Any) -> str:
        """解析搜索站点配置：容忍列表或逗号/换行分隔，归一成逗号分隔的数字串。"""
        items = value if isinstance(value, (list, tuple)) else re.split(r"[,，;；\n\r]+", str(value or ""))
        ids: List[str] = []
        for item in items:
            text = _clean_text(str(item))
            if text.isdigit() and text not in ids:
                ids.append(text)
        return ",".join(ids)

    def _site_ids(self, value: Any) -> List[int]:
        """站点配置 → ``int`` 列表（容忍 ``"18,16"`` / 列表 / 空串）。"""
        return [
            int(item)
            for item in str(self._parse_site_ids(value) or "").split(",")
            if item.strip().isdigit()
        ]

    def _sub_targets(
        self, sub: Dict[str, Any]
    ) -> Tuple[List[int], Optional[str], Optional[str]]:
        """一条订阅的搜索 / 下载落点：``(站点, 下载器, 保存目录)``。

        2026-10-22 用户口径：订阅设置里可以单独配站点 / 下载器 / 目录，
        **留空就回落配置页的默认值** —— 所以这里逐项 ``or``，空串不等于「不设」，
        而是「用默认」。
        """
        sites = self._site_ids(sub.get("sites")) or self._site_ids(self._subscribe_sites)
        downloader = _clean_text(sub.get("downloader")) or (self._subscribe_downloader or None)
        save_path = _clean_save_path(sub.get("save_path")) or (self._subscribe_save_path or None)
        return sites, downloader, save_path

    def _live_config(self) -> Dict[str, Any]:
        """组装当前运行时配置用于回写（键与 ``_default_config`` 一致）。

        必须读**实例属性**：插件虚拟分身会在同一份源码上创建多个运行实例，只有实例属性
        才是本实例的真实配置。
        """
        return {
            "enabled": self._enabled,
            "onlyonce": self._onlyonce,
            "actors": ",".join(self._actors),
            "interval_hours": self._interval_hours,
            "retry_minutes": self._retry_minutes,
            "notify": self._notify,
            "sidebar_nav": self._sidebar_nav,
            "search_sites": self._search_sites,
            "subscribe_downloader": self._subscribe_downloader,
            "subscribe_sites": self._subscribe_sites,
            "subscribe_save_path": self._subscribe_save_path,
            "subscribe_mode": self._subscribe_mode,
            "subscribe_prefer": self._subscribe_prefer,
            "auto_subscribe": self._auto_subscribe,
            "auto_subscribe_scope": self._auto_subscribe_scope,
            "auto_subscribe_max_per_run": self._auto_subscribe_max_per_run,
            "auto_subscribe_skip_library": self._auto_subscribe_skip_library,
            "subscribe_engine": self._subscribe_engine,
            "self_interval_hours": self._self_interval_hours,
            "self_max_per_run": self._self_max_per_run,
            "self_max_pages": self._self_max_pages,
        }

    @staticmethod
    def _default_config() -> Dict[str, Any]:
        """返回配置页默认值。"""
        return {
            "enabled": False,
            "onlyonce": False,
            "actors": "",
            "interval_hours": 12,
            "retry_minutes": _DEFAULT_RETRY_MINUTES,
            "notify": True,
            "sidebar_nav": True,
            "search_sites": "",
            "subscribe_downloader": "",
            "subscribe_sites": "",
            "subscribe_save_path": "",
            "subscribe_mode": "follow",
            "subscribe_prefer": "seeders",
            "auto_subscribe": False,
            "auto_subscribe_scope": "new",
            "auto_subscribe_max_per_run": _AUTO_SUB_DEFAULT_MAX,
            "auto_subscribe_skip_library": True,
            "subscribe_engine": "host",
            "self_interval_hours": _SUB_SEARCH_DEFAULT_HOURS,
            "self_max_per_run": _SUB_SEARCH_DEFAULT_MAX,
            "self_max_pages": _SUB_SEARCH_DEFAULT_PAGES,
        }

    # ── 页面与渲染模式 ──

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        """声明使用 Vue 联邦远程组件渲染。

        产物目录动态取 ``dist/`` 下序号最大的 ``a<N>`` 目录（目录名变 = URL 变 =
        浏览器缓存自动失效；测试阶段版本号冻结，靠它代替 ``?v=`` 的破缓存作用）。
        """
        return "vue", _frontend_dist()

    def get_form(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Vue 模式下配置页由远程 Config 组件渲染，后端只返回默认配置模型。"""
        return [], self._default_config()

    def get_page(self) -> List[Dict[str, Any]]:
        """Vue 模式下详情页由远程 Page 组件渲染，后端返回空列表。"""
        return []

    def get_sidebar_nav(self) -> List[Dict[str, Any]]:
        """侧栏入口「短剧演员」，落在宿主的「订阅」分组里。

        宿主侧栏合并逻辑把插件项**追加到分组末尾**（``order`` 只在插件项之间排序），
        ``section`` 仅接受 start / discovery / subscribe / organize / system。
        """
        if not self.get_state() or not self._sidebar_nav:
            return []
        return [
            {
                "nav_key": "main",
                "title": "短剧演员",
                "icon": "mdi-movie-open-star-outline",
                "section": "subscribe",
                "permission": "subscribe",
                "order": 32,
            },
        ]

    def get_dashboard_meta(self) -> Optional[List[Dict[str, str]]]:
        """声明仪表板窗口；插件未启用时不注册。"""
        if not self.get_state():
            return None
        return [{"key": "overview", "name": f"{self.plugin_name} · 追剧概览"}]

    def get_dashboard(
        self, key: str = "", **kwargs: Any
    ) -> Optional[Tuple[Dict[str, Any], Dict[str, Any], List[dict]]]:
        """仪表板内容：``(列配置, 全局配置, 页面 JSON)``。

        Vue 联邦插件由前端 Dashboard 组件呈现内容，因此页面 JSON 为空。
        """
        if not self.get_state():
            return None
        if key and key != "overview":
            return None
        # 只出统计口径：仪表板 300 秒刷一次，不该顺带对全部作品查一遍媒体库
        _, summary = self._work_rows(with_probe=False)
        return (
            {"cols": 12, "sm": 6, "md": 4},
            {
                "title": f"{self.plugin_name} · 追剧概览",
                "subtitle": (
                    f"{len(self._actors)} 位演员｜{summary.get('total', 0)} 部作品"
                    f"｜新作品 {summary.get('new', 0)} 部"
                ),
                "refresh": 300,
                "border": True,
            },
            [],
        )

    # ── 服务 ──

    def get_service(self) -> List[Dict[str, Any]]:
        """注册定时服务：作品发现（按间隔）+ 解析失败重试（短间隔）。"""
        if not self.get_state() or not self._actors:
            return []
        # ⚠️ 传给被调函数的参数必须写在 ``func_kwargs`` 里。宿主注册时会把
        # ``service["kwargs"]`` **原样展开给** ``scheduler.add_job()``，而 ``trigger``
        # 正是 ``add_job`` 自己的形参名 —— 写成 ``kwargs`` 会抛
        # ``got multiple values for argument 'trigger'`` 并**拒绝注册**（真机实证）。
        services: List[Dict[str, Any]] = [
            {
                "id": f"{self.__class__.__name__}.Refresh",
                "name": "短剧演员 · 作品发现",
                "trigger": IntervalTrigger(hours=max(1, self._interval_hours)),
                "func": self.refresh_works_task,
                "func_kwargs": {"trigger": "interval"},
            },
        ]
        # 失败重试与整体刷新是两条节奏：失败是临时故障，等满一天才恢复体验太差
        services.append(
            {
                "id": f"{self.__class__.__name__}.Retry",
                "name": "短剧演员 · 解析失败重试",
                "trigger": IntervalTrigger(minutes=max(1, self._retry_minutes)),
                "func": self.retry_failed_actors,
                "func_kwargs": {"trigger": "interval"},
            }
        )
        # 自建订阅搜索（subscribe_engine=self）：全分类补搜 + 择优下载，
        # 绕开宿主订阅按媒体类型拼站点分类参数、短剧被站点挂在电影分类搜不到的问题
        if self._subscribe_engine == "self":
            services.append(
                {
                    "id": f"{self.__class__.__name__}.SubSearch",
                    "name": "短剧演员 · 自建订阅搜索",
                    "trigger": IntervalTrigger(hours=max(1, self._self_interval_hours)),
                    "func": self.subscribe_search_task,
                    "func_kwargs": {"trigger": "interval"},
                }
            )
            # 订阅站 RSS 增量检查：源取订阅站点的站点配置（不单独配置），固定节奏
            services.append(
                {
                    "id": f"{self.__class__.__name__}.RssCheck",
                    "name": "短剧演员 · 订阅站 RSS 增量",
                    "trigger": IntervalTrigger(minutes=_RSS_CHECK_INTERVAL_MINUTES),
                    "func": self.rss_check_task,
                    "func_kwargs": {"trigger": "interval"},
                }
            )
        return services

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """注册远程命令，实际动作通过 ``EventType.PluginAction`` 事件路由。"""
        return [
            {
                "cmd": "/shortdrama",
                "event": EventType.PluginAction,
                "desc": "刷新短剧演员作品",
                "category": "插件命令",
                "data": {"action": "shortdramaactorsubscribe_refresh"},
            }
        ]

    @eventmanager.register(EventType.PluginAction)
    def on_plugin_action(self, event: Event) -> None:
        """响应远程命令；仅处理属于本插件的 action。"""
        event_data = getattr(event, "event_data", None) or {}
        if _clean_text((event_data or {}).get("action")) != "shortdramaactorsubscribe_refresh":
            return
        if not self._lock.acquire(blocking=False):
            logger.info(f"{PLUGIN_NAME} 已有刷新任务在运行，忽略本次命令")
            return
        try:
            before = self._load_actors()
            self._refresh_actors(force=True)
            fresh = self._collect_fresh(before)
            self._notify_fresh(fresh)
        finally:
            self._lock.release()

    # ── 接口 ──

    def get_api(self) -> List[Dict[str, Any]]:
        """插件 HTTP 端点（``/api/v1/plugin/ShortDramaActorSubscribe/…``）。

        三条合同（见官方 ``docs/V3_API_Response_Adaptation.md``）：

        1. **信封**：全部返回宿主统一 envelope :class:`app.schemas.Response` —— 顶层只有
           ``success`` / ``message`` / ``data`` 三个键，业务对象一律进 ``data``；
        2. **模型**：每个端点声明与真实输出一致的 ``response_model``（模型见 :mod:`api_models`），
           响应结构在宿主 ``/docs`` 的 OpenAPI 里可查；
        3. **错误**：参数 / 资源 / 状态类错误抛 ``HTTPException``（400 / 404 / 409 / 503），
           由宿主生成统一错误 envelope；``200 + success=False`` 只留给「调用完成但业务被拒」。

        认证统一 ``auth: "bear"``：宿主 ``verify_token`` 同时接受 JWT 与 API Token，
        这样面板（登录态）与外部脚本能共用同一批接口。
        """
        return [
            {
                "path": "/status",
                "endpoint": self.api_status,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "插件状态",
                "response_model": api_models.StatusResponse,
            },
            {
                "path": "/works",
                "endpoint": self.api_works,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "作品墙",
                "response_model": api_models.WorksResponse,
            },
            {
                "path": "/actors",
                "endpoint": self.api_actors,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "演员列表",
                "response_model": api_models.ActorsResponse,
            },
            {
                "path": "/actors/cards",
                "endpoint": self.api_actor_cards,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "已关注演员的卡片数据（与搜索候选同构）",
                "response_model": api_models.ActorCardsResponse,
            },
            {
                "path": "/people",
                "endpoint": self.api_people,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "人物目录（演员 / 导演 / 编剧，数据源人物列表页）",
                "response_model": api_models.PeopleListResponse,
            },
            {
                "path": "/ranks",
                "endpoint": self.api_ranks,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "站点榜单目录（发现页榜单 chips）",
                "response_model": api_models.RanksResponse,
            },
            {
                "path": "/ranks/works",
                "endpoint": self.api_rank_works,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "一个榜单的作品卡（发现页榜单网格）",
                "response_model": api_models.RankWorksResponse,
            },
            {
                "path": "/logs",
                "endpoint": self.api_logs,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "插件最近日志（面板右上日志面板）",
                "response_model": api_models.LogsResponse,
            },
            {
                "path": "/actors/search",
                "endpoint": self.api_search_actor,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "在短剧百科里查演员",
                "response_model": api_models.ActorSearchResponse,
            },
            {
                "path": "/works/search",
                "endpoint": self.api_search_work,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "在短剧百科里按片名查作品",
                "response_model": api_models.WorkSearchResponse,
            },
            {
                "path": "/works/detail",
                "endpoint": self.api_work_detail,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "作品详情（面板自绘详情页，不用宿主详情页）",
                "response_model": api_models.WorkDetailResponse,
            },
            {
                "path": "/actors/detail",
                "endpoint": self.api_actor_detail,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "演员详情（面板自绘演员作品页，版式照宿主演员详情页）",
                "response_model": api_models.ActorDetailResponse,
            },
            {
                "path": "/actors/add",
                "endpoint": self.api_add_actor,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "添加演员",
                "response_model": api_models.ActorMutationResponse,
            },
            {
                "path": "/actors/remove",
                "endpoint": self.api_remove_actor,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "移除演员",
                "response_model": api_models.ActorMutationResponse,
            },
            {
                "path": "/actors/works",
                "endpoint": self.api_actor_works,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "某位演员的全部作品（百科实时，关注与否均可）",
                "response_model": api_models.ActorWorksResponse,
            },
            {
                "path": "/actors/subscribe_all",
                "endpoint": self.api_subscribe_all,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "订阅某位演员的全部作品（跳过已订阅与已在库）",
                "response_model": api_models.ActorSubscribeAllResponse,
            },
            {
                "path": "/subscriptions",
                "endpoint": self.api_subscriptions,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "当前订阅清单（作品墙左侧「订阅作品」面板）",
                "response_model": api_models.SubscriptionsResponse,
            },
            {
                "path": "/subscribe",
                "endpoint": self.api_subscribe,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "订阅一部作品（引擎=self 记插件清单，host 走宿主订阅链）",
                "response_model": api_models.SubscribeResponse,
            },
            {
                "path": "/unsubscribe",
                "endpoint": self.api_unsubscribe,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "取消一部作品的订阅（插件清单 + 宿主 djbaike 订阅都清）",
                "response_model": api_models.SubscribeResponse,
            },
            {
                "path": "/subscribe/update",
                "endpoint": self.api_subscribe_update,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "编辑一条订阅的配置（暂停 / 站点 / 下载器 / 保存目录）",
                "response_model": api_models.SubscribeResponse,
            },
            {
                "path": "/subscribe/search_now",
                "endpoint": self.api_subscribe_search_now,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "对一部订阅立即搜索一次（清冷却 + 后台跑一轮）",
                "response_model": api_models.SubscribeResponse,
            },
            {
                "path": "/subscribe/random",
                "endpoint": self.api_subscribe_random,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "随机订阅：从作品墙全集随机挑 N 部未订阅且未入库的作品",
                "response_model": api_models.RandomSubscribeResponse,
            },
            {
                "path": "/subscribe/search_all",
                "endpoint": self.api_subscribe_search_all,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "立即对全部订阅作品执行一轮订阅搜索（清冷却）",
                "response_model": api_models.SubscribeResponse,
            },
            {
                "path": "/refresh",
                "endpoint": self.api_refresh,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "立即刷新作品",
                "response_model": api_models.RefreshResponse,
            },
            {
                "path": "/config",
                "endpoint": self.api_get_config,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "读取配置",
                "response_model": api_models.ConfigResponse,
            },
            {
                "path": "/config",
                "endpoint": self.api_update_config,
                "methods": ["PUT"],
                "auth": "bear",
                "summary": "保存配置",
                "response_model": api_models.ConfigResponse,
            },
        ]

    def api_get_config(self) -> "schemas.Response[api_models.ConfigData]":
        """读取当前配置（前端配置弹窗用）。"""
        return schemas.Response(
            success=True, data=api_models.ConfigData(**self._live_config())
        )

    def api_update_config(
        self, payload: Optional[Dict[str, Any]] = None
    ) -> "schemas.Response[api_models.ConfigData]":
        """保存配置：只认 ``_default_config()`` 里的键，其余一律丢弃。

        整体替换而不是合并，这样删掉的概念（比如曾经的配置项）会在用户保存一次后
        自动从库里消失，不会残留成幽灵配置。
        """
        incoming = payload if isinstance(payload, dict) else {}
        base = self._default_config()
        merged = {key: incoming.get(key, base[key]) for key in base}
        self.update_config(merged)
        self.init_plugin(merged)
        return schemas.Response(
            success=True, data=api_models.ConfigData(**self._live_config())
        )

    def api_status(self) -> "schemas.Response[api_models.StatusData]":
        """插件状态总览：演员、作品、新作品、最近刷新时间。

        ⚠️ 这条接口只出**统计口径**，刻意不做媒体库在库判定（``with_probe=False``）：
        仪表板和状态查询会周期调用它，真机 2 300+ 部作品逐条查库纯属白跑。
        """
        _, summary = self._work_rows(with_probe=False)
        snapshot = self._load_actors()
        last = ""
        for record in snapshot.values():
            if isinstance(record, dict):
                stamp = _clean_text(record.get("time"))
                if stamp > last:
                    last = stamp
        ledger = self._auto_subscribe_ledger()
        # 「已在媒体库，跳过」记在台账里但不是「订阅成功」，统计时要摘出去
        subscribed = [
            row
            for row in ledger.values()
            if row.get("ok") and _clean_text(row.get("detail")) != _AUTO_SKIP_DETAIL
        ]
        recent = sorted(
            ledger.values(), key=lambda row: _clean_text(row.get("time")), reverse=True
        )[:5]
        # 自建订阅搜索汇总（引擎 = self 才有数字）。2026-10-22 起候选收敛为
        # 「已订阅」的作品（见 _subscribed_works），各计数也只按订阅算 ——
        # 台账里订阅之外的历史条目（早期全库试跑留下的）不再进统计。
        if self._subscribe_engine == "self":
            sub_ledger = self._sub_ledger()
            # 订阅没有「暂停」态（2026-10-23 用户口径）：清单里的都算在跑，
            # 暂停与否由台账的终态 / 冷却决定，不额外判断。
            active_wanted = list(self._subscribed_works())

            def _sub_count(*states: str) -> int:
                return sum(
                    1
                    for mid in active_wanted
                    if _clean_text((sub_ledger.get(mid) or {}).get("state")) in states
                )

            sub_downloaded = _sub_count("downloaded")
            sub_noresult = _sub_count("noresult")
            sub_failed = _sub_count("failed")
            sub_skipped = _sub_count("in_library", "history")
            sub_pending = max(
                0,
                len(active_wanted) - sub_downloaded - sub_noresult - sub_failed - sub_skipped,
            )
        else:
            sub_downloaded = sub_noresult = sub_failed = sub_skipped = sub_pending = 0
        return schemas.Response(
            success=True,
            data=api_models.StatusData(
                enabled=bool(self.get_state()),
                configured=bool(self._actors),
                actors=len(self._actors),
                works=int(summary.get("total", 0)),
                new_works=int(summary.get("new", 0)),
                last_refresh=last,
                new_window_days=_NEW_WINDOW_DAYS,
                states=[
                    api_models.ActorRow(**self._actor_row(key, record))
                    for key, record in snapshot.items()
                    if isinstance(record, dict)
                ],
                auto_subscribe=bool(self._auto_subscribe),
                auto_subscribed=len(subscribed),
                auto_subscribe_recent=[
                    api_models.AutoSubscribeRow(
                        time=_clean_text(row.get("time")),
                        title=_clean_text(row.get("title")),
                        year=_clean_text(row.get("year")),
                        media_id=_clean_text(row.get("media_id")),
                        actor=_clean_text(row.get("actor")),
                        ok=bool(row.get("ok")),
                        detail=_clean_text(row.get("detail")),
                    )
                    for row in recent
                ],
                sub_engine=self._subscribe_engine,
                sub_downloaded=sub_downloaded,
                sub_noresult=sub_noresult,
                sub_failed=sub_failed,
                sub_skipped=sub_skipped,
                sub_pending=sub_pending,
            ),
        )

    def api_works(
        self,
        actor: str = "",
        genre: str = "",
        year: str = "",
        studio: str = "",
        platform: str = "",
        sort: str = "",
        only_not_in_library: str = "",
        only_not_subscribed: str = "",
        keyword: str = "",
        page: str = "",
        page_size: str = "",
    ) -> Dict[str, Any]:
        """作品墙数据（服务端筛选 / 排序 / 分页）。

        ⚠️ 参数一律声明成**函数形参**：宿主把插件端点直接交给 FastAPI 注册
        （``adapters/web/plugin/routes.py`` → ``add_api_route``），查询参数靠 FastAPI
        按形参名注入 —— 用 flask 的 ``request.args`` 读在 v3 上永远是空（真机实证：
        ``?page_size=2`` 被忽略、照样返回整页）。

        参数：

        * ``actor`` —— 演员（名字或 key，空=全部）
        * ``genre`` —— 类型（作品的题材标签，任一命中）
        * ``year`` —— 年份（作品的首播年）
        * ``studio`` —— 版权方（数据源给出才有，空选项时前端不显示这一栏）
        * ``platform`` —— 播放平台（「在哪播」，如红果短剧；数据源从站点 meta 文案里
          抠出来，同样「给出才有」，空选项时前端不显示这一栏）
        * ``sort`` —— 只支持 ``date``（首播日期，新剧在前，也是默认）。热度 / 播放 /
          评分三种排序已撤（2026-10-23 用户口径）：那些值在墙的快照里恒为 0
        * ``only_not_in_library`` —— ``1`` 只看未入库（只排除**明确已在库**的；
          查库失败/没有数据的「未知」作品保留，绝不把「没查成」显示成「都不在库」。
          判定与宿主媒体详情页同一套：身份精确匹配 → 片名+类型+年份回退）
        * ``keyword`` —— 剧名关键字
        * ``page`` / ``page_size`` —— 分页（前端滚到底再拉下一页）

        全部用字符串接、内部再宽松转换：非法值（比如 ``page=abc``）只该被当成默认值，
        不该让 FastAPI 直接甩 422 把整面墙打死。

        响应里的 ``facets`` 是筛选项（类型 / 年份 / 版权方 / 播放平台，各带作品数）、
        ``has_more`` 供前端判断还要不要继续加载。
        """
        rows, summary = self._work_rows(
            {
                "actor": actor,
                "genre": genre,
                "year": year,
                "studio": studio,
                "platform": platform,
                "sort": sort,
                "only_not_in_library": only_not_in_library,
                "only_not_subscribed": only_not_subscribed,
                "keyword": keyword,
            }
        )
        page_no = max(1, _to_int(page, 1))
        size = min(_MAX_PAGE_SIZE, max(1, _to_int(page_size, _DEFAULT_PAGE_SIZE)))
        total = len(rows)
        start = (page_no - 1) * size
        chunk = rows[start : start + size]
        # 页模式补判：宿主媒体详情页同款「展示谁判谁」——只对**本页要展示**的
        # 几十行做在库判定（单行毫秒级），全集判定只留给「只看未入库」筛选
        # （那种情况下 ``_work_rows`` 已在筛选前全量判过，这里跳过）
        if not summary.get("probe_full") and self.library_probe.available:
            probe = self.library_probe
            for row in chunk:
                row["in_library"] = probe.lookup(row)
        # 自建订阅搜索状态（引擎 = self 时每行带出台账结论，作品卡直接显示）
        self._attach_sub_state(chunk)
        facets = summary.get("facets") or {
            "genres": [],
            "years": [],
            "studios": [],
            "platforms": [],
        }
        # 回显**归一后**的排序键：非法值实际按默认排序跑，回显原值会让前端的排序按钮
        # 一个都不高亮（见 _SORT_FIELDS 的取值域）
        sort_key = _clean_text(sort)
        if sort_key not in _SORT_FIELDS:
            sort_key = _DEFAULT_SORT
        return schemas.Response(
            success=True,
            data=api_models.WorksData(
                total=total,
                page=page_no,
                page_size=size,
                has_more=start + len(chunk) < total,
                sort=sort_key,
                new_window_days=_NEW_WINDOW_DAYS,
                works=[api_models.WorkRow(**row) for row in chunk],
                actor_filters=[
                    api_models.ActorFilterRow(**item)
                    for item in summary.get("actors") or []
                ],
                facets=api_models.FacetsData(**facets),
                summary=api_models.WorksSummaryData(
                    total=int(summary.get("total", 0)),
                    new=int(summary.get("new", 0)),
                    library_known=int(summary.get("library_known", 0)),
                    in_library=int(summary.get("in_library", 0)),
                    probe_available=bool(summary.get("probe_available")),
                    probe_full=bool(summary.get("probe_full")),
                ),
            ),
        )

    def api_actors(self) -> "schemas.Response[api_models.ActorsData]":
        """演员列表（含解析状态、百科 ID、作品数）。"""
        snapshot = self._load_actors()
        return schemas.Response(
            success=True,
            data=api_models.ActorsData(
                actors=[
                    api_models.ActorRow(**self._actor_row(key, snapshot.get(key)))
                    for key in self._actors
                ]
            ),
        )

    def _query_actor_candidates(self, name: str) -> List[Dict[str, Any]]:
        """查数据源的演员候选（候选行已归一成前端要的形状）。

        上游不可用时抛 ``HTTPException(503)`` —— 这是「请求没能完成」，不是「查到了但是空」
        （文档 §3.3/§3.4）；数据源没收录属于后者，返回空列表由调用方展示中性空态。

        ⚠️ 演员身份是**复合形态** ``yanyuan:<id>``，数据源给的键叫 ``media_id``
        （它没有 ``actor_id`` 这个键）。这里统一收敛到本插件的 ``actor_id`` ——
        前端与快照只认这一个字段，往下所有调用（``actor_works`` / 详情页）都靠它。
        """
        try:
            candidates = self._source("search_actors", name=name) or []
        except _SourceUnavailable as err:
            raise HTTPException(status_code=503, detail=str(err)) from err
        except Exception as err:  # noqa: BLE001 - 数据源不可用是上游故障
            logger.warning(f"{PLUGIN_NAME} 数据源查找演员失败（{name}）：{err}")
            raise HTTPException(
                status_code=503, detail=f"短剧数据源查找失败：{err}"
            ) from err
        rows: List[Dict[str, Any]] = []
        for row in candidates:
            if not isinstance(row, dict):
                continue
            # 演员 ID 的默认分类是 ``yanyuan``（与 api_add_actor / _baike_works /
            # _source_profile 等所有演员 ID 调用点一致）：数据源回退成裸数字时
            # 不能补成作品那个 ``duanju:`` 前缀，否则会拿演员号去查作品分类
            actor_id = canonical_media_id(
                row.get("actor_id") or row.get("media_id"), default_kind="yanyuan"
            )
            if not split_media_id(actor_id)[1]:
                continue
            label = _clean_text(row.get("name"))
            rows.append(
                {
                    "name": label,
                    "actor_id": actor_id,
                    "media_id": _clean_text(row.get("media_id")) or actor_id,
                    "url": _clean_text(row.get("url")),
                    # 候选行自带头像（.net 的 ``poster``）：搜索卡片立刻能用，
                    # 不必等 actor_profile 那一趟。地址**原样透传** ——
                    # 图床数据源给什么就用什么，这里不改写、不择优。
                    "profile": _clean_text(
                        row.get("profile") or row.get("poster")
                    ),
                    "job_title": _clean_text(row.get("job_title")),
                    "works_count": _to_int(row.get("works_count")),
                    "exact": _actor_name_key(label) == _actor_name_key(name),
                    # 已关注判定按 ID（ID 是唯一身份，2026-10-20）：同名的另一位
                    # 是不同的人，不能因为名字相同就标成已关注
                    "subscribed": self._followed_actor(label, actor_id),
                }
            )
        return rows

    def api_search_actor(
        self, payload: Optional[Dict[str, Any]] = None
    ) -> "schemas.Response[api_models.ActorSearchData]":
        """在短剧百科里查演员：返回候选（供添加演员时挑选 / 演员搜索卡片）。

        百科的站外索引召回**含模糊结果**，所以这里把候选原样返回给前端挑；
        后端只在「归一化名字精确相等」时才认为可以直接采纳。

        ``enrich`` 为真时再给**前 N 位**候选补上演员档案（头像 ``profile`` / 作品数
        ``works_count`` / 简介 ``bio`` / 性别 / 国籍）—— 每位候选要多抓一次演员页，
        所以只补前几位，且失败一律降级成「只有名字」的卡片，不让整次搜索失败。
        面板的「搜索演员」用得上头像，添加演员的候选列表不需要，按需开启。

        ``subscribed`` 表示这位演员是否已在关注列表里（前端据此把卡片标成已添加）。
        """
        body = payload if isinstance(payload, dict) else {}
        name = _clean_text(body.get("name"))
        if not name:
            raise HTTPException(status_code=400, detail="请填写演员名")
        enrich = _to_bool(body.get("enrich"), False)
        rows = self._query_actor_candidates(name)
        if enrich and rows:
            self._enrich_actor_cards(rows[:_ACTOR_LOOKUP_LIMIT])
        return schemas.Response(
            success=True,
            data=api_models.ActorSearchData(
                name=name,
                candidates=[api_models.ActorCandidateRow(**row) for row in rows],
            ),
        )

    def api_search_work(
        self, payload: Optional[Dict[str, Any]] = None
    ) -> "schemas.Response[api_models.WorkSearchData]":
        """在短剧百科里按片名查作品：返回候选（搜索结果页的作品卡片用）。

        经 ``search_medias(meta=…, media_source="djbaike")`` 向**绑定的数据源**要候选 ——
        与宿主搜索框同一条检索链路（库 → 站内搜索），返回宿主 ``MediaInfo``，
        这里只挑展示用的字段转成纯 dict。
        """
        body = payload if isinstance(payload, dict) else {}
        name = _clean_text(body.get("name"))
        if not name:
            raise HTTPException(status_code=400, detail="请填写作品名")
        meta = MetaInfo(name)
        try:
            infos = self._source(
                "search_medias", meta=meta, media_source=_BAIKE_SOURCE
            ) or []
        except _SourceUnavailable as err:
            raise HTTPException(status_code=503, detail=str(err)) from err
        except Exception as err:  # noqa: BLE001 - 数据源不可用是上游故障
            logger.warning(f"{PLUGIN_NAME} 数据源查找作品失败（{name}）：{err}")
            raise HTTPException(
                status_code=503, detail=f"短剧数据源查找失败：{err}"
            ) from err
        works: List[Dict[str, Any]] = []
        for info in infos:
            media_id = canonical_media_id(getattr(info, "media_id", "") or "")
            title = _clean_text(getattr(info, "title", "") or "")
            if not media_id or not title:
                continue
            # 站内搜索会把小说频道（``xiaoshuo:…``）的条目混进来 —— 这里只收剧集，
            # 否则用户搜到的第一条会是订阅不了的小说（见 is_drama_media_id）
            if not is_drama_media_id(media_id):
                logger.debug(f"{PLUGIN_NAME} 搜索命中非剧集条目，已跳过：{media_id}")
                continue
            works.append(
                {
                    "media_source": _clean_text(getattr(info, "media_source", "") or "")
                    or _BAIKE_SOURCE,
                    "media_id": media_id,
                    "title": title,
                    "year": _clean_text(str(getattr(info, "year", "") or "")),
                    "poster": _clean_text(getattr(info, "poster_path", "") or ""),
                    "overview": _clean_text(getattr(info, "overview", "") or ""),
                    "vote": float(getattr(info, "vote_average", 0) or 0),
                }
            )
        return schemas.Response(
            success=True,
            data=api_models.WorkSearchData(
                name=name,
                works=[api_models.WorkSearchRow(**row) for row in works],
            ),
        )

    def _enrich_actor_cards(self, rows: List[Dict[str, Any]]) -> None:
        """给演员候选补头像 / 作品数 / 简介（就地改 ``rows``，best-effort）。

        走 :meth:`_source_profile`：数据源有 ``actor_profile`` 时用它（不补作品详情），
        没有就退回候选自带的 ``poster``。任何异常都只跳过这一位候选。
        """
        for row in rows:
            actor_id = _clean_text(row.get("actor_id"))
            if not actor_id:
                continue
            profile = self._source_profile(actor_id, _clean_text(row.get("name")))
            if not profile:
                continue
            row["name"] = _clean_text(profile.get("name")) or row.get("name", "")
            row["profile"] = _clean_text(profile.get("profile")) or _clean_text(
                row.get("profile")
            )
            row["works_count"] = _to_int(profile.get("works_count")) or _to_int(
                row.get("works_count")
            )
            row["bio"] = _clean_text(profile.get("bio"))
            row["gender"] = _clean_text(profile.get("gender"))
            row["nationality"] = _clean_text(profile.get("nationality"))
            row["job_title"] = _clean_text(profile.get("job_title")) or _clean_text(
                row.get("job_title")
            )
            row["url"] = _clean_text(profile.get("url")) or row.get("url", "")
            row["followers"] = _to_int(profile.get("followers"))
            row["likes"] = _to_int(profile.get("likes"))

    def api_add_actor(
        self, payload: Optional[Dict[str, Any]] = None
    ) -> "schemas.Response[api_models.ActorMutationData]":
        """添加演员到关注列表。

        2026-10-20 起身份收敛到 ID（ID 是唯一身份）：

        - 给了 ``actor_id``（用户在候选里挑过）→ 直接以 ID 入列表 / 快照；
        - 只给名字 → 先查百科，**只有归一化名字精确相等**才采纳（宁可让用户挑一次，
          也不错配成另一个演员）；没有精确命中时返回 ``need_pick=True`` + 候选列表
          （这不是接口失败，见文档 §3.3）；
        - 重复判定**按 ID**：同名的另一位是不同的人，允许共存 —— 名字只在「列表里
          还是名字键的过渡态」时兜一层（同一位、快照还没归位）。
        """
        body = payload if isinstance(payload, dict) else {}
        name = _clean_text(body.get("name"))
        # 前端回传的可能是候选卡上的复合 ID；裸数字按 ``yanyuan`` 补前缀（历史形态）
        actor_id = _actor_id_of(body.get("actor_id"))
        if not name and not actor_id:
            raise HTTPException(status_code=400, detail="请填写演员名")
        if actor_id and any(same_media_id(item, actor_id) for item in self._actors):
            raise HTTPException(status_code=409, detail="这位演员已经在关注列表里")

        if not actor_id:
            rows = self._query_actor_candidates(name)
            matched = [row for row in rows if row.get("exact")]
            if not matched:
                return schemas.Response(
                    success=True,
                    message=f"短剧数据源里没有与「{name}」完全同名的演员，请从候选里挑一位",
                    data=api_models.ActorMutationData(
                        actors=list(self._actors),
                        need_pick=True,
                        candidates=[
                            api_models.ActorCandidateRow(**row) for row in rows
                        ],
                    ),
                )
            actor_id = _actor_id_of(matched[0].get("actor_id"))
            if not actor_id:
                raise HTTPException(status_code=502, detail="百科候选没有有效的演员 ID")
            name = _clean_text(matched[0].get("name")) or name
            # 列表里还是名字键的过渡态：同一位（快照已记下同一 ID）不重复添加
            legacy = next(
                (
                    item
                    for item in self._actors
                    if not _actor_id_of(item)
                    and _actor_name_key(item) == _actor_name_key(name)
                ),
                "",
            )
            legacy_record = self._load_actors().get(legacy)
            if isinstance(legacy_record, dict) and same_media_id(
                legacy_record.get("baike_id"), actor_id
            ):
                raise HTTPException(status_code=409, detail=f"「{name}」已经在关注列表里")

        # 先把演员写进配置，再立即抓一轮（让用户马上看到作品，而不是等下个轮询周期）。
        # 快照 / 名单都以 ID 为键；名字只作展示字段。
        self._actors = self._actors + [actor_id]
        config = self._live_config()
        self.update_config(config)
        self.init_plugin(config)
        # 记下数据源演员 ID：后续轮次直接按 ID 取作品页，不再走站外检索
        self._merge_snapshot(
            {
                actor_id: {
                    "key": actor_id,
                    "name": name,
                    "baike_id": actor_id,
                    "source": _SOURCE_PLUGIN_ID,
                    "works": [],
                    "errors": [],
                }
            }
        )
        count = self._refresh_one(actor_id)
        return schemas.Response(
            success=True,
            message=f"已添加「{name}」" + (f"，拿到 {count} 部作品" if count else "，正在获取作品"),
            data=api_models.ActorMutationData(actors=list(self._actors)),
        )

    def api_remove_actor(
        self, payload: Optional[Dict[str, Any]] = None
    ) -> "schemas.Response[api_models.ActorMutationData]":
        """把演员移出关注列表（连同他的快照一起删掉）。

        ``actor_id``（ID 是唯一身份）与 ``name`` 都认：名单正在向 ID 收敛，
        名字键的过渡态也要能删。同名演员按 ID 精确移除，不会误伤另一位。
        """
        body = payload if isinstance(payload, dict) else {}
        name = _clean_text(body.get("name"))
        actor_id = _actor_id_of(body.get("actor_id"))
        key = ""
        if actor_id:
            key = next(
                (item for item in self._actors if same_media_id(item, actor_id)), ""
            )
        if not key and name:
            key = next((item for item in self._actors if item == name), "")
        if not key and name:
            # 名单里已是 ID 键、前端还拿着旧名字：按快照里记录的名字回查
            snapshot = self._load_actors()
            key = next(
                (
                    item
                    for item in self._actors
                    if _actor_name_key((snapshot.get(item) or {}).get("name"))
                    == _actor_name_key(name)
                    and _actor_id_of(item)
                ),
                "",
            )
        if not key:
            raise HTTPException(status_code=404, detail="演员不在关注列表里")
        removed_name = _clean_text((self._load_actors().get(key) or {}).get("name")) or name or key
        self._actors = [item for item in self._actors if item != key]
        config = self._live_config()
        self.update_config(config)
        self.init_plugin(config)
        self._merge_snapshot(drop=[key])
        # 进程内缓存一并清掉（作品 / 档案都不该留着已移除演员的内容）
        self._works_cache.pop(key, None)
        self._profile_cache.pop(key, None)
        return schemas.Response(
            success=True,
            message=f"已移除「{removed_name}」",
            data=api_models.ActorMutationData(actors=list(self._actors)),
        )

    def api_actor_works(
        self, actor_id: str = "", name: str = ""
    ) -> "schemas.Response[api_models.ActorWorksData]":
        """某位演员的**全部**作品（点演员卡片展开作品墙用，关注与否均可）。

        作品**现查**数据源（``actor_works``，演员页自带全部作品卡），不落盘、
        不进快照 —— 关注列表的作品墙数据照旧走 ``/works``。
        参数是函数形参（FastAPI 按名注入，见 ``api_works`` 的说明）。
        """
        actor_id = canonical_media_id(actor_id, default_kind="yanyuan")
        name = _clean_text(name)
        if not split_media_id(actor_id)[1] and not name:
            raise HTTPException(
                status_code=400, detail="缺少演员标识（actor_id 或 name）"
            )
        try:
            works = self._source_works(actor_id, name)
        except _SourceUnavailable as err:
            raise HTTPException(status_code=503, detail=str(err)) from err
        except Exception as err:  # noqa: BLE001 - 数据源不可用是上游故障
            logger.warning(
                f"{PLUGIN_NAME} 数据源取演员作品失败（{actor_id or name}）：{err}"
            )
            raise HTTPException(
                status_code=503, detail=f"短剧数据源取作品失败：{err}"
            ) from err
        rows: List[Dict[str, Any]] = []
        seen: set = set()
        for candidate in works:
            row = work_row(candidate, name, actor_id)
            if row["key"] in seen:
                continue
            seen.add(row["key"])
            # 在库判定与作品墙同一套探针（三态；查不了就是「未知」，不硬给结论）
            row["in_library"] = self.library_probe.lookup(row)
            rows.append(row)
        # ⚠️ ``sort_works`` 返回**新列表**（不就地改）：早年写成不赋值的形式，
        # 演员作品页实际一直以数据源原始顺序返回，「新剧在前」没生效
        rows = sort_works(rows, _DEFAULT_SORT)
        self._attach_sub_state(rows)
        return schemas.Response(
            success=True,
            data=api_models.ActorWorksData(
                name=name,
                total=len(rows),
                works=[api_models.WorkRow(**row) for row in rows],
            ),
        )

    def api_subscribe_all(
        self, payload: Optional[Dict[str, Any]] = None
    ) -> "schemas.Response[api_models.ActorSubscribeAllData]":
        """把一位演员的**全部作品**提交给宿主订阅链（演员卡 / 演员详情页的按钮）。

        与自动订阅的区别：这是**用户手动动作** —— 不受单轮预算与「只订新作品」范围
        限制（点了就是全部），但仍按配置跳过已在媒体库的作品；前端已知已订阅的
        ``exclude_ids`` 也直接跳过，不必再问宿主一遍。

        幂等：宿主订阅本身 ``exist_ok=True``，重复点击不会产生重复订阅；
        已在库 / 已订阅都会计数，前端照实提示「提交 N 部 / 跳过 M 部」。

        逐部通知关掉（``message=False``）：一次点出几十条系统通知没有意义，
        汇总结果由前端 toast 一次说清。
        """
        body = payload if isinstance(payload, dict) else {}
        actor_id = canonical_media_id(body.get("actor_id"), default_kind="yanyuan")
        name = _clean_text(body.get("name"))
        if not split_media_id(actor_id)[1] and not name:
            raise HTTPException(
                status_code=400, detail="缺少演员标识（actor_id 或 name）"
            )
        try:
            works = self._source_works(actor_id, name)
        except _SourceUnavailable as err:
            raise HTTPException(status_code=503, detail=str(err)) from err
        except Exception as err:  # noqa: BLE001 - 数据源不可用是上游故障
            logger.warning(
                f"{PLUGIN_NAME} 订阅全部作品时取作品失败（{actor_id or name}）：{err}"
            )
            raise HTTPException(
                status_code=503, detail=f"短剧数据源取作品失败：{err}"
            ) from err

        rows: List[Dict[str, Any]] = []
        seen: set = set()
        for candidate in works:
            row = work_row(candidate, name, actor_id)
            if row["key"] in seen:
                continue
            seen.add(row["key"])
            rows.append(row)

        raw_excluded = body.get("exclude_ids")
        excluded: set = set()
        if isinstance(raw_excluded, (list, tuple, set)):
            excluded = {
                _clean_text(item) for item in raw_excluded if _clean_text(item)
            }

        # 已在媒体库 → 跳过（订阅只为拿到没有的片子；与自动订阅同一个配置开关）
        probe = self.library_probe if self._auto_subscribe_skip_library else None
        submitted = skipped_library = skipped_subscribed = failed = 0
        media_ids: List[str] = []
        details: List[api_models.AutoSubscribeRow] = []
        stamped = datetime.now().strftime(_STAMP_FORMAT)
        for row in rows[:_SUBSCRIBE_ALL_LIMIT]:
            media_id = _clean_text(row.get("media_id"))
            if not media_id:
                continue
            if media_id in excluded:
                skipped_subscribed += 1
                continue
            # 引擎 = self 时插件清单里的订阅也算「已订阅」（exclude_ids 兜不到
            # 的场景：别的入口订的 / 前端集合还没刷出来）
            if self._subscribe_engine == "self" and media_id in self._plugin_subs():
                skipped_subscribed += 1
                continue
            if probe is not None and probe.lookup(row) is True:
                skipped_library += 1
                continue
            ok, detail = self._add_subscribe(row, message=False)
            if ok:
                submitted += 1
                media_ids.append(media_id)
            else:
                failed += 1
            details.append(
                api_models.AutoSubscribeRow(
                    time=stamped,
                    title=_clean_text(row.get("title")),
                    year=_clean_text(row.get("year")),
                    media_id=media_id,
                    actor=name or actor_id,
                    ok=ok,
                    detail=_clean_text(detail),
                )
            )

        total = len(rows)
        capped = total > _SUBSCRIBE_ALL_LIMIT
        parts = [f"提交 {submitted} 部"]
        if skipped_library:
            parts.append(f"已在库跳过 {skipped_library} 部")
        if skipped_subscribed:
            parts.append(f"已订阅跳过 {skipped_subscribed} 部")
        if failed:
            parts.append(f"失败 {failed} 部")
        if capped:
            parts.append(f"超出单次上限 {_SUBSCRIBE_ALL_LIMIT} 部，可再点一次继续")
        return schemas.Response(
            success=True,
            message=f"《{name or actor_id}》{'，'.join(parts)}",
            data=api_models.ActorSubscribeAllData(
                name=name or actor_id,
                total=total,
                submitted=submitted,
                skipped_library=skipped_library,
                skipped_subscribed=skipped_subscribed,
                failed=failed,
                capped=capped,
                media_ids=media_ids,
                details=details,
            ),
        )

    def _source_works(self, actor_id: str = "", name: str = "") -> List[Dict[str, Any]]:
        """取一位演员的全部作品，**已归一到本插件的候选结构**（去重前的原始顺序）。

        数据源卡片的键名（``badge`` / ``episodes`` / ``genres_text``）由
        :func:`source_card` 对齐后再投影 —— 下游（``work_row`` / 作品墙 / 详情页兜底）
        因此不必认识来源。
        """
        cards = self._source("actor_works", actor_id=actor_id, name=name) or []
        works: List[Dict[str, Any]] = []
        for card in cards:
            if not isinstance(card, dict):
                continue
            candidate = baike_work_to_candidate(source_card(card))
            if candidate:
                works.append(candidate)
        return works

    def _actor_works_cached(
        self, key: str, record: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """取一位**关注中的**演员的作品。

        顺序（v5 起）：

        1. **快照里的 ``works``** —— 作品已经落盘，读它是纯内存操作、零请求；
           发现任务每轮会把最新一版写回去（见 :meth:`_discover_actor`）；
        2. 记录里没有 ``works``（v4 及更早，或刚添加还没抓过）→ 进程内缓存
           （``_WORKS_CACHE_TTL``）→ 数据源 ``actor_works``（它自己的详情缓存兜底）。

        ``record`` 由调用方传进来省一次 ``_load_actors``（作品墙要遍历 96 位演员，
        逐个读 plugindata 是白费）。数据源不可用时返回空列表 —— 下一轮发现补回来。
        """
        if not isinstance(record, dict):
            record = self._load_actors().get(key) or {}
        if isinstance(record.get("works"), list):
            return snapshot_works(record)
        cached = self._works_cache.get(key)
        now = time.time()
        if isinstance(cached, tuple) and now - cached[1] < _WORKS_CACHE_TTL:
            return cached[0]
        actor_id = canonical_media_id(record.get("baike_id"), default_kind="yanyuan")
        if not split_media_id(actor_id)[1]:
            return list(cached[0]) if isinstance(cached, tuple) else []
        try:
            works = self._source_works(actor_id, _clean_text(record.get("name")) or key)
        except Exception as err:  # noqa: BLE001 - 数据源不可用走上次结果
            logger.debug(f"{PLUGIN_NAME} 取演员作品失败（{key}）：{err}")
            return list(cached[0]) if isinstance(cached, tuple) else []
        self._works_cache[key] = (works, now)
        return works

    def _followed_actor(self, name: str, actor_id: str) -> bool:
        """这位演员在不在本插件的关注列表里。

        2026-10-20 起按 ID 精确匹配（ID 是唯一身份）：行带站点身份时**只认 ID**
        —— 名单键直接对、快照记录里的 ``baike_id`` 也对一层（覆盖名单还是名字键
        的过渡态）；没有 ID 才退回名字。同名演员是两个人，按名字比会把同名的
        另一位误标成已关注（2026-10-20 用户确认要按 ID 统一）。
        """
        actor_id = _actor_id_of(actor_id)
        if actor_id:
            snapshot = self._load_actors()
            for key in self._actors:
                if same_media_id(key, actor_id):
                    return True
                record = snapshot.get(key)
                if isinstance(record, dict) and same_media_id(
                    record.get("baike_id"), actor_id
                ):
                    return True
            return False
        return bool(name) and name in self._actors

    def _cached_profile(self, name: str, actor_id: str) -> Dict[str, Any]:
        """从**进程内档案缓存**里取这位演员的档案（字段口径 = :data:`_PROFILE_FIELDS`）。

        ``/actors/detail`` 的档案**优先**用数据源现查的结果；现查拿不到时用这里兜底
        —— 发现流程每轮会顺带补一次（:meth:`_fill_profile_cache`），缓存热着就有。
        档案不落盘：缓存冷掉时这几项就是空，不硬凑。
        """
        snapshot = self._load_actors()
        keys: List[str] = [name] if name else []
        if split_media_id(actor_id)[1]:
            for key, item in snapshot.items():
                if isinstance(item, dict) and same_media_id(
                    item.get("baike_id"), actor_id
                ):
                    keys.append(key)
                    break
        profile: Dict[str, Any] = {}
        for key in keys:
            cached = self._profile_cache.get(key)
            if isinstance(cached, tuple) and cached[0]:
                profile = dict(cached[0])
                break
        record = next(
            (
                item
                for key, item in snapshot.items()
                if isinstance(item, dict)
                # 快照键已收敛成 ID（2026-10-20）：按名字找不到时按记录里的 ID 对一层
                and (key == name or (actor_id and same_media_id(item.get("baike_id"), actor_id)))
            ),
            None,
        ) or {}
        profile.setdefault("name", _clean_text(record.get("name")) or name)
        profile.setdefault("actor_id", _clean_text(record.get("baike_id")) or actor_id)
        profile.setdefault("media_id", _clean_text(record.get("media_id")))
        return profile

    # ── 订阅（自建订阅系统的入口；引擎 = host 时退化为宿主订阅的代提交）──

    def api_subscriptions(self) -> "schemas.Response[api_models.SubscriptionsData]":
        """当前订阅清单（作品墙左侧「订阅作品」面板的数据源）。

        与 :meth:`_subscribed_works` 同口径：插件订阅清单 ∪ 宿主 ``djbaike`` 未暂停
        订阅；每条附订阅搜索状态（引擎 = ``self`` 才有搜索行为）。
        """
        wanted = self._subscribed_works()
        ledger = self._sub_ledger() if self._subscribe_engine == "self" else {}
        probe = self.library_probe
        items: List[api_models.SubscriptionRow] = []
        for media_id, info in wanted.items():
            entry = ledger.get(media_id) or {}
            # 在库三态（探针现查，剧名唯一判据）：已订阅页的「已入库 / 未入库」
            # 筛选与卡片「已在媒体库」角标都吃它；查不了（探针不可用）就是 None
            in_library: Optional[bool] = None
            if probe.available:
                in_library = probe.lookup(
                    {
                        "media_source": _BAIKE_SOURCE,
                        "media_id": media_id,
                        "type": "电视剧",
                        "title": _clean_text(info.get("name")),
                        "year": _clean_text(info.get("year")),
                    }
                )
            items.append(
                api_models.SubscriptionRow(
                    media_id=media_id,
                    title=_clean_text(info.get("name")),
                    year=_clean_text(info.get("year")),
                    actor=_clean_text(info.get("actor")),
                    poster=_clean_text(info.get("poster")),
                    in_library=in_library,
                    sub_state=_clean_text(entry.get("state")),
                    sub_detail=_clean_text(entry.get("detail")),
                    sub_time=_clean_text(entry.get("time")),
                    torrent_url=_clean_text(entry.get("torrent_url")),
                    torrent_title=_clean_text(entry.get("torrent_title")),
                    # 订阅级覆写（空 = 用配置页默认）
                    sites=_clean_text(info.get("sites")),
                    downloader=_clean_text(info.get("downloader")),
                    save_path=_clean_text(info.get("save_path")),
                )
            )
        items.sort(key=lambda row: row.sub_time or "", reverse=True)
        return schemas.Response(
            success=True,
            data=api_models.SubscriptionsData(
                engine=self._subscribe_engine,
                items=items,
                # 配置页默认值：前端在订阅设置里当 placeholder / 「用默认」提示
                default_sites=str(self._subscribe_sites or ""),
                default_downloader=self._subscribe_downloader or "",
                default_save_path=self._subscribe_save_path or "",
            ),
        )

    def api_subscribe(
        self, payload: Optional[Dict[str, Any]] = None
    ) -> "schemas.Response[None]":
        """订阅一部作品。

        引擎 = ``self``：记进**插件订阅清单**（不进宿主订阅系统），等订阅搜索
        自动下载；引擎 = ``host``：走宿主订阅链（与旧行为一致）。两路都幂等。
        """
        body = payload if isinstance(payload, dict) else {}
        title = _clean_text(body.get("title"))
        media_id = _clean_text(body.get("media_id"))
        if not title or not media_id:
            raise HTTPException(status_code=400, detail="缺少标题或媒体身份")
        row = {
            "title": title,
            "year": _clean_text(body.get("year")),
            "media_id": media_id,
            "media_source": _clean_text(body.get("media_source")) or _BAIKE_SOURCE,
            "actor": _clean_text(body.get("actor")),
            "poster": _clean_text(body.get("poster")),
        }
        ok, message = self._add_subscribe(row)
        return schemas.Response(success=ok, message=message)

    def api_unsubscribe(
        self, payload: Optional[Dict[str, Any]] = None
    ) -> "schemas.Response[None]":
        """取消订阅：只清**插件订阅清单**（宿主订阅链路整套去除）。"""
        body = payload if isinstance(payload, dict) else {}
        media_id = _clean_text(body.get("media_id"))
        if not media_id:
            raise HTTPException(status_code=400, detail="缺少媒体身份")
        ok, message = self._plugin_unsubscribe(media_id)
        # 不能恒 True：前端据此判断「真的取消了没」，恒 True 会让失败也提示成功
        return schemas.Response(success=ok, message=message)

    def api_subscribe_update(
        self, payload: Optional[Dict[str, Any]] = None
    ) -> "schemas.Response[None]":
        """编辑一条订阅的配置（作品详情页「订阅设置」：「站点 / 下载器 / 目录」）。

        订阅**没有暂停态**（2026-10-23 用户口径）：要么在清单里、要么取消订阅，
        所以这里只改落点三项。只对**插件订阅清单**里的订阅生效 —— 引擎 = ``self``
        的订阅归插件自己管；宿主订阅（引擎 = ``host`` 期间建的）请到宿主订阅页操作。
        """
        body = payload if isinstance(payload, dict) else {}
        media_id = _clean_text(body.get("media_id"))
        if not media_id:
            raise HTTPException(status_code=400, detail="缺少媒体身份")

        def provided(key: str) -> Optional[str]:
            """只把**请求里带了**的键当改动；没带 = None（本次不动这一项）。"""
            return None if key not in body else _clean_text(body.get(key))

        ok, message = self._plugin_subscribe_update(
            media_id,
            sites=provided("sites"),
            downloader=provided("downloader"),
            save_path=provided("save_path"),
        )
        return schemas.Response(success=ok, message=message)

    def api_subscribe_search_now(
        self, payload: Optional[Dict[str, Any]] = None
    ) -> "schemas.Response[None]":
        """对一部订阅**立即搜索一次**（不等下一轮定时）。

        清掉这台的冷却 / 终态记录后开后台线程跑一轮 ``_self_search_one``（与
        订阅搜索任务同一把锁、同一套台账 —— 结果同样写进「订阅设置」的状态里）。
        """
        body = payload if isinstance(payload, dict) else {}
        media_id = _clean_text(body.get("media_id"))
        if not media_id:
            raise HTTPException(status_code=400, detail="缺少媒体身份")
        sub = self._subscribed_works().get(media_id)
        if not sub:
            raise HTTPException(status_code=404, detail="不在订阅清单里")
        # 清冷却：立即搜索本身就是「别管冷却再试一次」的意思
        ledger = self._sub_ledger()
        if media_id in ledger:
            del ledger[media_id]
            self._save_sub_ledger(ledger)
        title = _clean_text(sub.get("name"))
        threading.Thread(
            target=self._search_now_worker,
            args=(media_id, dict(sub)),
            daemon=True,
            name=f"{PLUGIN_NAME}-search-now",
        ).start()
        return schemas.Response(success=True, message=f"已开始搜索《{title}》，结果稍后回填")

    def api_subscribe_random(
        self, payload: Optional[Dict[str, Any]] = None
    ) -> "schemas.Response[api_models.RandomSubscribeData]":
        """随机订阅（2026-10-23 用户口径）：从**作品墙全集**里随机挑 N 部订阅。

        ``count`` 可指定数量（默认 1，上限 10）。候选 = 快照里的全部作品，排除：
        已订阅、**之前随机订过的**（哪怕后来取消了订阅，也不再重复挑 —— 记录在
        :data:`_DATA_RANDOM_PICKED`）、已在媒体库（剧名判据，不重复收已收的）。
        候选不足就订剩下的全部，一个都没有时 ``success=false``。
        """
        body = payload if isinstance(payload, dict) else {}
        try:
            count = max(1, min(10, int(body.get("count") or 1)))
        except (TypeError, ValueError):
            count = 1
        subscribed = self._subscribed_works()
        picked_before = self._random_picked()
        probe = self.library_probe
        # 候选只做**廉价的身份过滤**（已订阅 / 随机订过剔除），在库判定留给下面
        # 的随机游走 —— 全集 4 500+ 部逐条查库要几分钟（真机实测），随机抽样边走
        # 边查期望只查几次。
        candidates: List[Tuple[Dict[str, Any], str]] = []
        seen: set = set()
        snapshot = self._load_actors()
        for key, record in snapshot.items():
            if not isinstance(record, dict):
                continue
            actor = _clean_text(record.get("name")) or key
            for work in self._actor_works_cached(key, record):
                if not isinstance(work, dict):
                    continue
                row = work_row(work, actor, key)
                mid = _clean_text(row.get("media_id"))
                if not mid or mid in seen or mid in subscribed or mid in picked_before:
                    continue
                seen.add(mid)
                candidates.append((row, actor))
        if not candidates:
            return schemas.Response(
                success=False,
                message="没有可随机订阅的作品（都订阅过了或都随机订过）",
                data=api_models.RandomSubscribeData(requested=count, items=[]),
            )
        random.shuffle(candidates)
        items: List[api_models.RandomSubscribeWork] = []
        for row, actor in candidates:
            if len(items) >= count:
                break
            # 已入库的跳过（剧名判据）：不重复收已收的。探针有 TTL 缓存，同样的
            # 剧在订阅搜索 / 作品墙里查过的这里零查询。
            if probe.available and probe.lookup(row) is True:
                continue
            ok, _ = self._add_subscribe(row)
            if not ok:
                continue
            mid = _clean_text(row.get("media_id"))
            # 记进「随机订过」：哪怕之后取消订阅，随机也不再挑它（永不重复）
            picked_before[mid] = {
                "time": datetime.now().strftime(_STAMP_FORMAT),
                "title": _clean_text(row.get("title")),
                "actor": actor,
            }
            items.append(
                api_models.RandomSubscribeWork(
                    media_id=_clean_text(row.get("media_id")),
                    title=_clean_text(row.get("title")),
                    year=_clean_text(row.get("year")),
                    actor=actor,
                    poster=_clean_text(row.get("poster")),
                )
            )
        if not items:
            return schemas.Response(
                success=False,
                message="没有可随机订阅的作品（候选都已在库）",
                data=api_models.RandomSubscribeData(requested=count, items=[]),
            )
        self._save_random_picked(picked_before)
        titles = "、".join(f"《{item.title}》" for item in items)
        return schemas.Response(
            success=True,
            message=f"已随机订阅 {len(items)} 部：{titles}",
            data=api_models.RandomSubscribeData(requested=count, items=items),
        )

    def api_subscribe_search_all(
        self, payload: Optional[Dict[str, Any]] = None
    ) -> "schemas.Response[None]":
        """立即对**全部订阅作品**跑一轮订阅搜索（主界面按钮；不等下一轮定时）。

        手动全量时把「暂无资源 / 搜索失败」的冷却记录清掉 —— 用户点了就是想让
        它们现在重搜；终态（已下载 / 在库 / 下载历史已有）保持跳过，那些不需要再下。
        与定时任务同一把锁：上一轮还在跑时本轮直接结束（那轮会顺带把清过冷却的
        订阅搜掉，不重复排队）。
        """
        if self._subscribe_engine != "self":
            raise HTTPException(status_code=400, detail="订阅引擎不是自建模式，无订阅搜索可执行")
        if not self.get_state():
            raise HTTPException(status_code=400, detail="插件未启用")
        ledger = self._sub_ledger()
        cleared = 0
        for mid, entry in list(ledger.items()):
            if isinstance(entry, dict) and _clean_text(entry.get("state")) in (
                "noresult",
                "failed",
            ):
                del ledger[mid]
                cleared += 1
        if cleared:
            self._save_sub_ledger(ledger)
        threading.Thread(
            target=self.subscribe_search_task,
            args=("manual",),
            daemon=True,
            name=f"{PLUGIN_NAME}-search-all",
        ).start()
        suffix = f"，已清 {cleared} 条冷却记录" if cleared else ""
        return schemas.Response(success=True, message=f"已开始订阅搜索（全部订阅）{suffix}，结果稍后回填")

    def api_actor_detail(
        self,
        actor_id: str = "",
        name: str = "",
        works_page: str = "1",
        works_page_size: str = "24",
    ) -> "schemas.Response[api_models.ActorDetailData]":
        """一位演员的**详情** + 一页作品（面板自绘的演员作品页用）。

        数据面两拨：

        * 数据源档案（:meth:`_source_profile`，``enrich=False`` —— 作品由下一路单独取，
          别让它白补一遍）→ 姓名 / 头像 / 简介 / 职业 / 国籍 / 性别 / 生日 / 出生地 /
          身高体重 / 星座 / 院校 / 爱好 / 代表作 / 粉丝 / 获赞 / 演员页地址；
        * 数据源 ``actor_works`` → 全部作品，投影与 ``/actors/works`` **同一段代码**
          （见 :meth:`_source_works`），按 ``works_page`` / ``works_page_size`` 切片返回。

        **作品分页**（2026-10-18）：详情页改成滚动加载 —— 一页一页取，首屏不必等
        一次投影 / 探针几十部。投影结果（含在库判定）在进程内缓存 ``_WORKS_CACHE_TTL``
        秒（键 ``detail:<身份>``，与作品墙的演员键不同命名空间），翻页因此是纯内存切片，
        不会每页都去站点抓一遍。判定结果最多陈旧 5 分钟，作品墙同一口径。

        「关注状态」读本地关注列表；在库计数用作品墙那套探针现算 —— 探针是三态的
        （``None`` = 查不了），所以给前端的是「明确在库 N 部 / 查成了 M 部」两个数字，
        由前端决定要不要展示（``library_known == 0`` 就是判定不可用，整行隐藏）。

        ⚠️ 两路都空 = 「没这位演员」⇒ ``success=true`` + ``found=false``，
        **不算接口失败**（官方 API 专题 §3.3）；只有上游抛错才是 503。

        参数是函数形参（FastAPI 按名注入查询参数，见 ``api_works`` 的说明）。
        """
        actor_id = canonical_media_id(actor_id, default_kind="yanyuan")
        name = _clean_text(name)
        if not split_media_id(actor_id)[1] and not name:
            raise HTTPException(
                status_code=400, detail="缺少演员标识（actor_id 或 name）"
            )

        page = max(1, _to_int(works_page, 1))
        size = max(1, min(60, _to_int(works_page_size, 24) or 24))

        # ── 档案：现查（best-effort，拿不到不影响作品那一路） ──
        profile = self._source_profile(actor_id, name)

        # ── 作品：全部投影结果进进程内缓存，翻页只是切片 ──
        cache_key = f"detail:{actor_id or name}"
        cached = self._works_cache.get(cache_key)
        now = time.time()
        if isinstance(cached, tuple) and now - cached[1] < _WORKS_CACHE_TTL:
            all_rows = list(cached[0])
        else:
            try:
                works = self._source_works(actor_id, name)
            except _SourceUnavailable as err:
                raise HTTPException(status_code=503, detail=str(err)) from err
            except Exception as err:  # noqa: BLE001 - 数据源不可用是上游故障
                logger.warning(
                    f"{PLUGIN_NAME} 数据源取演员作品失败（{actor_id or name}）：{err}"
                )
                raise HTTPException(
                    status_code=503, detail=f"短剧数据源取作品失败：{err}"
                ) from err

            all_rows = []
            seen: set = set()
            for candidate in works:
                row = work_row(candidate, name, actor_id)
                if row["key"] in seen:
                    continue
                seen.add(row["key"])
                row["in_library"] = self.library_probe.lookup(row)
                all_rows.append(row)
            all_rows = sort_works(all_rows, _DEFAULT_SORT)
            self._works_cache[cache_key] = (all_rows, now)

        works_total = len(all_rows)
        offset = (page - 1) * size
        rows = all_rows[offset : offset + size]

        # 现查不到的字段从进程内档案缓存兜底（同一口径，前端不必自己再拼一次）
        fallback = self._cached_profile(name, actor_id)

        def pick(field: str) -> str:
            return _clean_text(profile.get(field)) or _clean_text(fallback.get(field))

        def pick_list(field: str) -> List[str]:
            for source in (profile, fallback):
                value = source.get(field)
                if isinstance(value, (list, tuple)) and value:
                    return [str(item) for item in value if str(item).strip()]
                text = _clean_text(value)
                if text:
                    return _text_list(text)
            return []

        label = pick("name") or name
        data = api_models.ActorDetailData(
            found=bool(profile) or bool(fallback) or bool(all_rows),
            actor_id=pick("actor_id") or actor_id,
            media_id=pick("media_id"),
            name=label,
            profile=pick("profile"),
            bio=pick("bio"),
            job_title=pick("job_title"),
            gender=pick("gender"),
            nationality=pick("nationality"),
            url=pick("url"),
            # ── 2026-10-18 补全：这些字段数据源一直有，之前白名单没列 ⇒ 详情页缺一半 ──
            birth_date=pick("birth_date"),
            birth_year=pick("birth_year"),
            birth_place=pick("birth_place"),
            height_cm=_to_int(profile.get("height_cm")) or _to_int(fallback.get("height_cm")),
            weight_kg=_to_int(profile.get("weight_kg")) or _to_int(fallback.get("weight_kg")),
            constellation=pick("constellation"),
            education=pick("education"),
            hobbies=pick_list("hobbies"),
            rep_text=pick("rep_text"),
            # 代表作原文对回作品行 ⇒ 前端做成可点条目（站点给的是一整串无分隔剧名）
            rep_works=[
                api_models.WorkRow(**row)
                for row in rep_work_rows(pick("rep_text"), all_rows)
            ],
            followers=_to_int(profile.get("followers")) or _to_int(fallback.get("followers")),
            likes=_to_int(profile.get("likes")) or _to_int(fallback.get("likes")),
            works_count=(
                _to_int(profile.get("works_count"))
                or _to_int(fallback.get("works_count"))
                or works_total
            ),
            total=len(rows),
            works_total=works_total,
            works_page=page,
            works_page_size=size,
            has_more=offset + len(rows) < works_total,
            in_library_count=sum(1 for row in all_rows if row.get("in_library") is True),
            library_known=sum(1 for row in all_rows if row.get("in_library") is not None),
            subscribed=self._followed_actor(label, pick("actor_id")),
            works=[api_models.WorkRow(**row) for row in rows],
        )
        return schemas.Response(
            success=True,
            message="" if data.found else "短剧数据源里没有这位演员的档案",
            data=data,
        )

    def api_work_detail(
        self, media_id: str = "", title: str = "", year: str = ""
    ) -> "schemas.Response[api_models.WorkDetailData]":
        """一部作品的**详情**（面板自绘的详情页用；不接受宿主自带详情页那一套）。

        数据面两拨（见 :func:`project_media_detail` / :func:`merge_detail_row`）：

        1. 数据源 ``recognize_media(media_source="djbaike", media_id=…)`` 拿详情页的标准
           ``MediaInfo``（简介 / 题材 / 单集时长 / 集数 / 首播 / 出品方 / 评分 /
           语言 / 海报 / 剧照首图 / 演员表含角色）；
        2. 按 ``media_id`` 从本地快照那一行补上**宿主模型里没有**的字段 ——
           热度 / 播放量 / 角标 / 首次发现 / 是否新 / 在库状态（数据源不吃集数时集数也从这里补）。

        ``media_id`` 必填（面板三个入口的作品行都带它；``duanju:`` 这类**分类前缀
        要保留** —— 站点各分类各排各的号；形态不符（URL / 乱码）的 ID 不收），
        ``title`` / ``year`` 只是兜底文案用。**未命中不算接口失败**（API 专题 §3.3）：
        数据源里没有这部剧时给 ``success=true`` + ``found=false`` + 空壳（前端给空态）；
        只有参数缺失（400）与数据源不可用 / 投影失败（503）走 ``HTTPException``。

        ``recognize_media`` 直接问**绑定的数据源**：``media_id`` 是复合形态，前缀即
        站点分类，数据源据此一次定位到正确的分类下那一条（这正是不能剥前缀的原因）。
        """
        native = canonical_media_id(media_id)
        title = _clean_text(title)
        if not native:
            if _clean_text(media_id):
                # 给了 ID 但形态不是「分类 + 纯数字」：数据源不会产出这种号，直接拒
                raise HTTPException(
                    status_code=400,
                    detail=f"作品标识无法识别（应为 <分类>:<数字>）：{_clean_text(media_id)}",
                )
            raise HTTPException(status_code=400, detail="缺少作品标识 media_id")
        try:
            info = self._source(
                "recognize_media", media_source=_BAIKE_SOURCE, media_id=native
            )
        except _SourceUnavailable as err:
            raise HTTPException(status_code=503, detail=str(err)) from err
        except Exception as err:  # noqa: BLE001 - 数据源不可用是上游故障
            logger.warning(f"{PLUGIN_NAME} 数据源取作品详情失败（{native}）：{err}")
            raise HTTPException(
                status_code=503, detail=f"短剧数据源取详情失败：{err}"
            ) from err
        # 未命中回 None；万一某个实现回的是列表，这里取第一条（返回形态不该把端点打成 500）
        if isinstance(info, (list, tuple)):
            info = info[0] if info else None
        if info:
            try:
                data = project_media_detail(info, native, self._actors)
            except Exception as err:  # noqa: BLE001 - 宿主模型版本差异
                logger.warning(f"{PLUGIN_NAME} 作品详情投影失败（{native}）：{err}")
                raise HTTPException(
                    status_code=503, detail=f"短剧详情解析失败：{err}"
                ) from err
            message = ""
        else:
            data = {
                "found": False,
                "media_source": _BAIKE_SOURCE,
                "media_id": native,
                "title": title,
                "year": _clean_text(year),
                "type": _BAIKE_TYPE,
            }
            message = "短剧数据源里没有这部剧的详情"
        row = self._snapshot_work_row(native)
        if row is not None:
            merge_detail_row(data, row, self.library_probe.lookup(row))
        return schemas.Response(
            success=True, message=message, data=api_models.WorkDetailData(**data)
        )

    def _snapshot_work_row(self, media_id: str) -> Optional[Dict[str, Any]]:
        """按百科 ID 从**快照里的作品**捞这部作品的墙上行（找不到返回 ``None``）。

        v5 起作品随快照落盘（:data:`_SNAPSHOT_WORK_KEYS`），所以这里读快照即可，
        零请求、插件重载后也不怕缓存冷掉；只有快照里还没作品（v4 老记录 / 刚添加
        还没抓过）时才退回进程内缓存。两处都没有就返回 ``None``（详情页只显示数据源
        给的内容，不硬编）—— 详情页不开网络补抓：那是作品墙的活。
        ``is_new`` 现算（与作品墙同一口径：过了窗口的「新」自动消失）。
        """
        target = canonical_media_id(media_id)
        if not target:
            return None
        snapshot = self._load_actors()
        for key in self._actors:
            record = snapshot.get(key)
            record = record if isinstance(record, dict) else {}
            works = snapshot_works(record)
            if not works:
                cached = self._works_cache.get(key)
                works = cached[0] if isinstance(cached, tuple) else []
            actor = _clean_text(record.get("name")) or key
            mapping = record.get("first_seen")
            mapping = mapping if isinstance(mapping, dict) else {}
            for work in works:
                if not isinstance(work, dict) or not same_media_id(
                    work.get("media_id"), target
                ):
                    continue
                row = work_row(work, actor, key)
                row["first_seen"] = _clean_text(mapping.get(work_identity(work)))
                row["is_new"] = is_fresh_work(row, time.time())
                return row
        return None

    def api_refresh(self) -> "schemas.Response[api_models.RefreshData]":
        """立即刷新全部演员的作品（忽略缓存）。"""
        if not self._actors:
            raise HTTPException(status_code=400, detail="还没有添加演员")
        if not self._lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="已有刷新任务在运行")
        try:
            before = self._load_actors()
            self._refresh_actors(force=True)
            fresh = self._collect_fresh(before)
            self._notify_fresh(fresh)
            _, summary = self._work_rows(with_probe=False)
            return schemas.Response(
                success=True,
                message=f"刷新完成：{summary.get('total', 0)} 部作品"
                + (f"，新增 {len(fresh)} 部" if fresh else ""),
                data=api_models.RefreshData(
                    total=int(summary.get("total", 0)),
                    new=int(summary.get("new", 0)),
                ),
            )
        finally:
            self._lock.release()

    # ── 发现层：只认短剧百科 ──

    def _discover_actor(self, key: str) -> Dict[str, Any]:
        """发现单个演员的作品列表（只认短剧百科）。

        这里负责「取一次作品 → 更新关注元数据」。**作品随快照落盘**（v5，
        :data:`_SNAPSHOT_WORK_KEYS`：身份 + 墙上要用的字段），另放一份进进程内缓存；
        作品墙 / 详情页读取时走 :meth:`_actor_works_cached`（快照优先）。

        返回 ``{"key","name","baike_id","url","media_id","works","first_seen",
        "works_count","errors","state"}``。
        """
        record: Dict[str, Any] = {
            "key": key,
            # 2026-10-20 起键可能是演员 ID（身份已收敛到 ID）：名字不再拿键凑数，
            # 解析后仍拿不到就从档案里补（见下面 _baike_works 之后的兜底）
            "name": "" if _actor_id_of(key) else key,
            "baike_id": _actor_id_of(key),
            "source": _SOURCE_PLUGIN_ID,
            "errors": [],
        }
        works: List[Dict[str, Any]] = []

        existing = self._load_actors().get(key)
        # 换了数据源插件：**旧 ID 与旧映射一律作废**。别家站点各排各的号，
        # 拿别家的 12 去查 .net 的 12 是另一个人；旧映射留着还会把别的剧算成「已见过」。
        same_source = (
            isinstance(existing, dict)
            and _clean_text(existing.get("source")) == _SOURCE_PLUGIN_ID
        )
        if same_source:
            # 数据源演员 ID 缓存在快照里：解析一次后，后续轮次直接按 ID 取作品页，
            # 不再走站外检索（站点检索一次要几秒，几十位演员逐个查一轮不可接受）
            record["baike_id"] = (
                canonical_media_id(existing.get("baike_id")) or _actor_id_of(key)
            )
            record["name"] = _clean_text(existing.get("name")) or record["name"]
            record["url"] = _clean_text(existing.get("url"))
            record["media_id"] = _clean_text(existing.get("media_id"))

        # 本轮时间戳：记首次发现 / 刷新时间（「新作品」不看它，看作品自己的首播日期）
        stamp = datetime.now().strftime(_STAMP_FORMAT)

        self._baike_works(record, works)
        # ⚠️ 数据源这一轮空手而归时**沿用内存里的上次结果**（不再落盘旧作品）：
        # 数据源处于升级 / 中间态时演员页会返回 0 部，整面墙不能因此清空。
        # 内存缓存也没有（刚重载）就只能空着，按临时故障的短间隔重试。
        if not works and record.get("errors"):
            cached = self._works_cache.get(key)
            if isinstance(cached, tuple) and cached[0]:
                works = cached[0]
                record["stale"] = True
        # first_seen 映射：老键原样继承、新作品记本轮时间、下线的键剪掉
        record["first_seen"] = merge_first_seen(
            (existing or {}).get("first_seen") if isinstance(existing, dict) else None,
            works,
            stamp,
        )
        # 键是 ID（身份已收敛）时名字不随键来：从档案兜一层，拿不到才落回键
        if not _clean_text(record.get("name")):
            profile = self._source_profile(_clean_text(record.get("baike_id")), "")
            record["name"] = _clean_text(profile.get("name")) or key
        record["works_count"] = len(works)
        # 作品进快照（v5）：只留身份 + 墙上要用的字段，作品墙读快照不再逐个打数据源
        record["works"] = lean_works(works)
        if works:
            # 作品内容只进进程内缓存（数据源自己的详情缓存兜底）
            self._works_cache[key] = (works, time.time())
        # 顺带补一次演员档案（只进进程内缓存，best-effort；拿不到就空着，不硬凑）
        if key not in self._profile_cache:
            self._fill_profile_cache(
                key,
                _clean_text(record.get("name")),
                _clean_text(record.get("baike_id")),
            )
        # state 依赖 stale 判定，算完再把它摘掉 —— stale 只影响本轮状态，不落盘
        state = record_state(record)
        record.pop("stale", None)
        record["state"] = state
        record["schema"] = _SNAPSHOT_SCHEMA
        return record

    def _baike_works(self, record: Dict[str, Any], works: List[Dict[str, Any]]) -> None:
        """从数据源取一位演员的全部作品（就地追加进 ``works``）。

        链路（全部经 :meth:`_source` 精确打到 ShortDramaBaikeScraper）：

        1. 快照里已缓存 ``baike_id``（复合 ``yanyuan:<id>``）→ 直接
           ``actor_works(actor_id)``，零检索请求；
        2. 没缓存 → ``search_actors(name)``，只收**归一化名字精确相等**的候选。

        缓存 ID 只在**形态对得上**时才用：数据源的人物号只会落在人物分类
        （``yanyuan`` / ``daoyan`` / ``bianju``）下，别的分类前缀（作品号、别家站点的
        号段）不是这位演员的号 —— 判废、清掉缓存、按名字重解析，不拿它去猜。

        任何异常都只记进 ``errors``，不会拖垮发现任务。
        """
        key = _clean_text(record.get("key"))
        if not key:
            return
        try:
            baike_id = canonical_media_id(record.get("baike_id"), default_kind="yanyuan")
            kind, native = split_media_id(baike_id)
            if not native or kind not in _PERSON_KINDS:
                if baike_id:
                    logger.debug(f"{PLUGIN_NAME} 快照里的演员 ID 不是人物号，已清空重解析：{baike_id}")
                record["baike_id"] = ""
                baike_id = ""
            if baike_id:
                cards = self._source("actor_works", actor_id=baike_id) or []
            else:
                candidates = self._source("search_actors", name=key) or []
                matched = [
                    row
                    for row in candidates
                    if isinstance(row, dict)
                    and _actor_name_key(row.get("name")) == _actor_name_key(key)
                    and split_media_id(row.get("actor_id") or row.get("media_id"))[1]
                ]
                if not matched:
                    # 稳定结果：站上没收录这位演员（或数据源插件未安装/已停用）
                    record["errors"].append(
                        "短剧数据源：未收录该演员（若数据源插件未安装或已停用也会出现此提示）"
                    )
                    return
                baike_id = canonical_media_id(
                    matched[0].get("actor_id") or matched[0].get("media_id"),
                    default_kind="yanyuan",
                )
                record["baike_id"] = baike_id
                cards = self._source("actor_works", actor_id=baike_id) or []
            for card in cards or []:
                candidate = baike_work_to_candidate(source_card(card))
                if candidate:
                    works.append(candidate)
            if baike_id and not cards:
                record["errors"].append("短剧数据源：演员页没有作品")
        except _SourceUnavailable as err:
            record["errors"].append(f"短剧数据源：{err}")
        except Exception as err:  # noqa: BLE001 - 数据源不可用只记错误
            record["errors"].append(f"短剧数据源：查找失败（{err}）")

    # ── 发现层节奏 ──

    def snapshot_ttl_seconds(self) -> float:
        """演员快照的保鲜期（秒）= 发现间隔。

        「发现间隔」既是定时任务的轮询节奏，也是快照的 TTL：
        每轮任务把「距上次抓取已超过一个间隔」的演员重抓一遍，
        两个口径天然一致，不再分开配置。
        """
        return max(1, _to_int(self._interval_hours) or 12) * 3600.0

    def retry_seconds(self) -> float:
        """解析失败后的重试间隔（秒）。"""
        return max(1, _to_int(self._retry_minutes) or _DEFAULT_RETRY_MINUTES) * 60.0

    def _due_actor_keys(self, cached: Dict[str, Any]) -> List[str]:
        """当前到期待解析的演员（新加的 / 快照过期 / 字段版本落后 / 失败已到重试点）。"""
        ttl = self.snapshot_ttl_seconds()
        retry = self.retry_seconds()
        return [
            key
            for key in self._actors
            if record_needs_refresh(cached.get(key), ttl, retry, schema=_SNAPSHOT_SCHEMA)
        ]

    def _merge_snapshot(
        self, records: Optional[Dict[str, Any]] = None, drop: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """快照的**唯一写入通道**：锁内「读 → 合并/删除若干 key → 写回」。

        为什么不让调用方自己「读出来改完再整份写回」：刷新任务与「添加/移除演员」会在
        不同线程并发改同一份快照（真机首轮解析能跑几十分钟），整份覆盖写会把另一方刚写的
        key 抹掉 —— 表现就是「刚添加的演员作品墙空了一轮」。全部收口到这里，读-改-写在
        临界区内完成，代价是几毫秒。
        """
        records = records or {}
        with self._snapshot_lock:
            # 复制一层再改：``get_data`` 的实现可能把同一个对象交回（本机单测的内存替身就是），
            # 就地改会让调用方手里那份「刷新前的快照」跟着变 —— 「新增作品」的对比就废了。
            snapshot = dict(self._load_actors())
            for key, record in records.items():
                snapshot[key] = record
            for key in drop or []:
                snapshot.pop(key, None)
            self.save_data(_DATA_ACTORS, snapshot)
            return snapshot

    def _refresh_one(self, key: str) -> int:
        """只重解析一位演员并落盘，返回作品数（添加演员时用）。

        解析要真抓网络，**不持锁**；只有落盘那一瞬间进临界区，避免长时间占着快照锁
        （否则用户添加演员会等一次几十秒的解析）。
        """
        record = self._discover_actor(key)
        record["time"] = datetime.now().strftime(_STAMP_FORMAT)
        self._merge_snapshot({key: record})
        return _to_int(record.get("works_count"))

    def _refresh_actors(
        self, force: bool = False, only: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """刷新演员作品快照；只重解析「到期」的演员，其余沿用缓存。

        - ``force=True``（手动刷新）无视缓存全部重解析；
        - ``only=[…]`` 只重解析指定演员（失败重试任务用）。

        全部命中缓存时**不写盘也不打日志** —— 定时轮询每轮都会走这里，静默是常态。
        """
        cached = {
            key: value for key, value in self._load_actors().items() if key in self._actors
        }
        if force:
            due = list(self._actors)
        elif only is not None:
            wanted = set(only)
            due = [key for key in self._actors if key in wanted]
        else:
            due = self._due_actor_keys(cached)
        if not due:
            return []

        for key in due:
            # 插件被停用（stop_service）时不再往下抓：剩下的演员留给下一轮
            if not self._running:
                logger.info(f"{PLUGIN_NAME} 插件已停止，本轮发现中断（剩余 {len(due)} 位）")
                break
            failed = False
            try:
                record = self._discover_actor(key)
            except Exception as err:  # noqa: BLE001 - 单个演员失败不影响其它演员
                logger.error(f"{PLUGIN_NAME} 解析演员「{key}」失败：{err}")
                # ⚠️ 上一轮的记录**整份继承**（尤其 ``works`` / ``first_seen``）：
                # 作品 v5 起就在快照里，一次解析失败不该把墙上已有的作品清空。
                # state 强制 waiting，好让失败重试任务按短间隔再来一次。
                previous = self._load_actors().get(key)
                record = dict(previous) if isinstance(previous, dict) else {}
                record.update({"key": key, "errors": [str(err)]})
                record.setdefault("name", key)
                failed = True
            record["state"] = "waiting" if failed else record_state(record)
            record["time"] = datetime.now().strftime(_STAMP_FORMAT)
            # ⚠️ 逐演员**增量落盘**：首轮解析可能拉长到几十分钟，宿主 reconcile 随时会
            # 重载插件打断整轮 —— 整轮结束才写盘会把已解析的演员全部丢回去重来。
            # 走 _merge_snapshot（锁内读-改-写）而不是拿本轮开头的 cached 整份覆盖：
            # 期间用户添加/移除演员的改动不能被抹掉。
            self._merge_snapshot({key: record})
        # 只保留配置里现有的演员（用户删掉的演员其作品不该再出现在作品墙）
        snapshot = self._merge_snapshot(
            drop=[
                key
                for key in self._load_actors()
                if key not in self._actors
            ]
        )
        self._log_actor_states(snapshot)
        # 自动订阅：只针对本轮真刷新过的演员（见 _auto_subscribe_round 的闸门）
        self._last_auto_subscribe = self._auto_subscribe_round(snapshot, due)
        # 本轮解析出 ID 的「名字键」演员在这里归位成 ID 键（放在最后 —— 上面的
        # 自动订阅 / 状态日志都还拿着旧键的快照与名单）
        self._rekey_actors()
        return []

    def _work_rows(
        self,
        query: Optional[Dict[str, Any]] = None,
        *,
        with_probe: bool = True,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """作品墙数据（可单测）：先算筛选前的全集，再按查询参数过滤 + 排序。

        :param query: 查询条件（``actor`` / ``genre`` / ``year`` / ``studio`` /
            ``platform`` / ``sort`` / ``keyword``）。不传 = 不过滤、按默认排序
            （``api_status`` 只取统计口径，走这条路）。
        :param with_probe: 是否做**媒体库在库判定**。``/works`` 需要（默认 ``True``）；
            只出统计口径的调用方（``/status``、仪表板）传 ``False`` —— 真机 3 500+ 部作品
            逐条查库纯属白跑，而它们并不展示在库标记（``in_library`` 一律 ``None`` = 未知，
            前端本来就按「未知不参与统计」处理）。判定时机学宿主媒体详情页的
            「展示谁判谁」：默认由 ``api_works`` 对**返回页**逐行判；「只看未入库」
            筛选开启时才在本方法里全量判（筛选语义需要全集）。

        ``is_new`` **不落盘**，每次查询现算（``release_date`` 是否在最近
        :data:`_NEW_WINDOW_DAYS` 天内）—— 过了窗口的「新」自动消失。

        **作品随快照落盘**（v5）：作品内容直接读快照（:meth:`_actor_works_cached`
        快照优先，老记录 / 刚添加还没抓过才退回数据源）。
        """
        snapshot = {
            key: value for key, value in self._load_actors().items() if key in self._actors
        }
        rows: Dict[str, Dict[str, Any]] = {}
        actor_counts: Dict[str, int] = {}
        now = time.time()
        for key, record in snapshot.items():
            if not isinstance(record, dict):
                continue
            actor = _clean_text(record.get("name")) or key
            mapping = record.get("first_seen")
            mapping = mapping if isinstance(mapping, dict) else {}
            works = self._actor_works_cached(key, record)
            actor_counts[actor] = len(works)
            for work in works:
                if not isinstance(work, dict):
                    continue
                row = work_row(work, actor, key)
                row["first_seen"] = _clean_text(mapping.get(work_identity(work)))
                row["is_new"] = is_fresh_work(row, now)
                seen = rows.get(row["key"])
                if seen:
                    # 同一部剧多位演员参演时合并演员名（「A / B」），命中任一演员的筛选都算
                    owners = {
                        item.strip()
                        for item in str(seen.get("actor") or "").split(" / ")
                        if item.strip()
                    }
                    owners.add(actor)
                    merged = " / ".join(sorted(owners))
                    # 新旧快照并存的同一部剧：早年作品卡「年份恒空」、字段残缺，
                    # 不能拿残缺的做底（空年份 + 失真的「新」标记都会上墙）——
                    # 字段更全的行顶上，演员归属无论谁做底都要合并
                    if not _clean_text(seen.get("year")) and _clean_text(row.get("year")):
                        row["actor"] = merged
                        rows[row["key"]] = row
                    else:
                        seen["actor"] = merged
                    continue
                rows[row["key"]] = row

        all_rows = list(rows.values())

        # ── 查询参数先行：「只看未入库」决定在库判定的范围 ──
        params = query if isinstance(query, dict) else {}
        only_not_in = _to_bool(params.get("only_not_in_library"))

        # ── 在库判定（与宿主媒体详情页同一套口径、同一套用法）──
        # 宿主的用法是「展示谁判谁」：详情页一次只判一部（毫秒级）。作品墙学它：
        # 默认**不在这里判**，由调用方（``api_works``）对**返回页**逐行判；
        # 唯一例外是「只看未入库」筛选 —— 它要拿全集的在库状态参与筛选，
        # 这时才全量判（探针 TTL 内复开零查询）。
        # ``in_library`` 三态：True 在库 / False 不在库 / None 未知（查不了或未查）
        # —— 未知不参与统计、也不被「只看未入库」排除，免得把「没查成」说成
        # 「都不在库」。``with_probe=False``（统计口径调用方）一律 None。
        probe_full = False
        if with_probe and only_not_in:
            probe = self.library_probe
            for row in all_rows:
                row["in_library"] = probe.lookup(row)
            probe_full = True

        known: List[Dict[str, Any]] = []
        if probe_full:
            known = [row for row in all_rows if row.get("in_library") is not None]
        elif with_probe:
            # 页模式：全集统计只汇报探针缓存里**已有**的新鲜结论 ——
            # 为了凑数字把全量查询又跑一遍，正是这次要改掉的慢路
            probe = self.library_probe
            known = [
                row for row in all_rows if probe.peek_cached(row) is not None
            ]

        summary = {
            "total": len(all_rows),
            "new": sum(1 for row in all_rows if row.get("is_new")),
            # 「已在库」统计只在**至少查成一条**时才给：整个库表都查不了时
            # library_known=0，前端据此隐藏统计（「只看未入库」开关的展示
            # 改由 probe_available 决定，不再依赖这个数）
            "library_known": len(known),
            "in_library": sum(1 for row in known if row.get("in_library") is True),
            # 判定通道可用性：页模式下开关的展示依据（与本次是否判过无关）
            "probe_available": bool(with_probe and self.library_probe.available),
            # 本次是否做过全量判定（前端可据此决定统计口径的可信展示）
            "probe_full": probe_full,
            "actors": [
                {
                    "key": _clean_text(record.get("name")) or key,
                    "name": _clean_text(record.get("name")) or key,
                    "works": actor_counts.get(
                        _clean_text(record.get("name")) or key,
                        _to_int(record.get("works_count")),
                    ),
                    "state": _clean_text(record.get("state")),
                }
                for key, record in snapshot.items()
                if isinstance(record, dict)
            ],
            # 筛选项基于**全集**算：选项不随勾选跳动
            "facets": build_facets(all_rows),
        }

        # ── 在库统计后台预热：页模式下 summary 只有缓存里的局部结论（冷缓存时
        # 「已入库 0 部」），后台把全集判一遍，统计随下一次请求变准 ──
        if with_probe and not probe_full and self.library_probe.available:
            _start_probe_warm(self)

        # ── 筛选 → 排序 ──
        filtered = filter_works(
            all_rows,
            actor=_clean_text(params.get("actor")),
            genre=_clean_text(params.get("genre")),
            year=_clean_text(params.get("year")),
        studio=_clean_text(params.get("studio")),
        platform=_clean_text(params.get("platform")),
        only_not_in_library=_to_bool(params.get("only_not_in_library")),
        only_not_subscribed=_to_bool(params.get("only_not_subscribed")),
        # 订阅身份来自订阅清单（插件清单 ∪ 宿主 djbaike 订阅），与卡片红心同一份真相
        subscribed=(
            set(self._subscribed_works())
            if _to_bool(params.get("only_not_subscribed"))
            else None
        ),
            keyword=_clean_text(params.get("keyword")),
        )
        return sort_works(filtered, _clean_text(params.get("sort"))), summary

    @property
    def library_probe(self) -> _LibraryProbe:
        """作品在库探针（实例级复用：TTL 缓存跨请求生效，进程里只建一个 Oper）。"""
        probe = getattr(self, "_probe", None)
        if probe is None:
            probe = _LibraryProbe()
            self._probe = probe
        return probe

    def _actor_row(self, key: str, record: Any) -> Dict[str, Any]:
        """演员列表的一行（状态 / 作品数 / 错误原因）。

        作品数取快照里的**真实条数**（v5 起作品随快照落盘）；记录里还没作品
        （v4 老记录 / 刚添加还没抓过）时退回上一轮发现记下的 ``works_count``。
        """
        record = record if isinstance(record, dict) else {}
        return {
            "key": key,
            "name": _clean_text(record.get("name")) or key,
            "baike_id": _clean_text(record.get("baike_id")),
            "works": len(snapshot_works(record)) or _to_int(record.get("works_count")),
            "state": _clean_text(record.get("state")),
            "time": _clean_text(record.get("time")),
            "errors": [str(item) for item in record.get("errors") or []],
        }

    def _actor_card_row(self, key: str, record: Any) -> Dict[str, Any]:
        """把一位演员摊成**卡片行**（与搜索结果候选同构）。

        字段与 ``/actors/search`` 的候选一致，前端两处用同一个卡片组件渲染；
        档案来自**进程内缓存**（档案不落盘）—— 缓存冷着就先给空值，
        ``enrich=1`` 或下一轮发现再补。``works_count`` 用快照里作品的真实条数，
        没有作品时退回上一轮记下的数字，保证与作品墙对得上。
        """
        record = record if isinstance(record, dict) else {}
        cached = self._profile_cache.get(key)
        profile = cached[0] if isinstance(cached, tuple) else {}
        # 档案是**进程内缓存**（插件一重载就空）⇒ 没档案时按身份现拼头像，
        # 否则整面墙都是人形占位图（2026-10-18 真实反馈）。
        avatar = _clean_text(profile.get("profile")) or actor_poster_url(
            record.get("baike_id") or record.get("media_id")
        )
        return {
            "name": _clean_text(record.get("name")) or key,
            "actor_id": _clean_text(record.get("baike_id")),
            "media_id": _clean_text(record.get("media_id"))
            or _clean_text(record.get("baike_id")),
            "url": _clean_text(profile.get("url")) or _clean_text(record.get("url")),
            "exact": True,
            "subscribed": True,  # 能出现在这个列表里 = 已关注
            "profile": avatar,
            "works_count": len(snapshot_works(record))
            or _to_int(record.get("works_count")),
            "followers": _to_int(profile.get("followers")),
            "likes": _to_int(profile.get("likes")),
            "bio": _clean_text(profile.get("bio")),
            "gender": _clean_text(profile.get("gender")),
            "nationality": _clean_text(profile.get("nationality")),
            "job_title": _clean_text(profile.get("job_title")),
            "state": _clean_text(record.get("state")),
        }

    def _fill_profile_cache(
        self, key: str, name: str = "", actor_id: str = ""
    ) -> Dict[str, Any]:
        """给一位演员**补一次档案并写进进程内缓存**（best-effort，**不落盘**）。

        档案属内容字段（数据源为主），只在内存里保鲜 ``_PROFILE_CACHE_TTL`` 秒；
        拿不到就返回空字典，不拿别的字段硬凑。

        ⚠️ 数据源没有 ``actor_profile`` 时头像只能从演员候选的 ``poster`` 来
        （见 :meth:`_source_profile`），简介 / 性别 / 国籍就是空。
        """
        actor_id = canonical_media_id(actor_id, default_kind="yanyuan")
        if not split_media_id(actor_id)[1]:
            record = self._load_actors().get(key)
            record = record if isinstance(record, dict) else {}
            actor_id = canonical_media_id(record.get("baike_id"), default_kind="yanyuan")
        if not split_media_id(actor_id)[1]:
            return {}
        profile = self._source_profile(actor_id, name)
        if not profile:
            return {}
        normalized: Dict[str, Any] = {
            field: profile.get(field) for field in _PROFILE_FIELDS if profile.get(field)
        }
        if name:
            normalized.setdefault("name", name)
        self._profile_cache[key] = (normalized, time.time())
        return normalized

    def _fill_actor_profiles(
        self, rows: List[Dict[str, Any]], limit: int = _ACTOR_LOOKUP_LIMIT
    ) -> int:
        """给卡片行里**档案还不全**的演员现取一次档案（写进程内缓存，不落盘）。

        “不全” = 没头像**或**没简介（数据源还没提供 ``actor_profile`` 时，
        头像来自搜索结果候选，简介等一直是空）。

        ``limit`` 默认 ``_ACTOR_LOOKUP_LIMIT``（搜索结果那种「补前几位就够」的场景）；
        已关注演员的卡片墙传**全部** —— 那一页本来就几十上百位，用户点一次「刷新」
        要能把整面墙的头像 / 粉丝 / 获赞都补上。

        **并发 6 路**：每位一次站点页面抓取（数据源详情缓存命中则零请求），串行补
        96 位要一分半，并发后二十秒上下；前端这个端点的超时是 120 秒。

        :return: 这次真正补到档案的位数（0 = 没得补了，调用方据此判断是否继续）
        """
        pending = [
            row
            for row in rows
            if _clean_text(row.get("actor_id"))
            and (
                not _clean_text(row.get("profile"))
                or not _clean_text(row.get("bio"))
            )
        ][:limit]
        if not pending:
            return 0

        def fill_one(row: Dict[str, Any]) -> bool:
            key = _clean_text(row.get("name"))
            if not key:
                return False
            profile = self._fill_profile_cache(
                key, key, _clean_text(row.get("actor_id"))
            )
            if not profile:
                return False  # 还是抓不到（百科没给 / 暂不可用），留给下一轮发现任务
            for field in _CARD_PROFILE_FIELDS:
                value = profile.get(field)
                if value not in (None, "", 0):
                    row[field] = value
            return True

        filled = 0
        with ThreadPoolExecutor(max_workers=6) as pool:
            for ok in pool.map(fill_one, pending):
                filled += 1 if ok else 0
        return filled

    def api_people(
        self, kind: str = "yanyuan", page: str = "1"
    ) -> "schemas.Response[api_models.PeopleListData]":
        """人物目录的一页（面板「发现演员」用，``GET /people``）。

        数据来自数据源的 ``list_people``（站点 ``/<kind>/list.html?page=N``，
        24 条/页）。分类就是三个：演员 / 导演 / 编剧 —— 三者**同属人物**，
        身份是复合 ID（``kind:<id>``），所以这里只做转发 + 标「已关注」，
        不把任何人写进本地库（翻几十页就是几万人，入库会把库撑成浏览记录）。

        ``kind`` / ``page`` 都按 ``str`` 收：面板与脚本都可能传空串 / ``"None"``，
        声明成 ``int`` 会被 FastAPI 直接挡成 422（数据源侧踩过这个坑）。
        """
        key = str(kind or "").strip().lower()
        if key in ("", "none", "null", "undefined"):
            key = _PEOPLE_KINDS[0]
        if key not in _PERSON_KINDS:
            key = _PEOPLE_KINDS[0]
        page_no = _to_int(page, 1) or 1
        page_no = max(1, page_no)

        payload = self._source_people(key, page_no)
        followed_names = {_actor_name_key(name) for name in self._actors}
        followed_ids = {
            _clean_text(record.get("baike_id"))
            for record in self._load_actors().values()
            if isinstance(record, dict)
        }
        rows: List[api_models.PeopleRow] = []
        for row in payload.get("people") or []:
            actor_id = _clean_text(row.get("actor_id"))
            rows.append(
                api_models.PeopleRow(
                    **{
                        **row,
                        "subscribed": bool(
                            _actor_name_key(row.get("name")) in followed_names
                            or (actor_id and actor_id in followed_ids)
                        ),
                    }
                )
            )
        return schemas.Response(
            success=True,
            data=api_models.PeopleListData(
                kind=key,
                page=page_no,
                has_more=bool(payload.get("has_more")),
                message=_clean_text(payload.get("message")),
                people=rows,
            ),
        )

    def api_ranks(self) -> "schemas.Response[api_models.RanksData]":
        """榜单目录（发现页「榜单」chips 用，``GET /ranks``）。

        2026-10-23 用户口径：榜单解析归**数据源**统一供给 —— 走跨插件模块方法
        ``list_ranks``（与 ``list_people`` 同一条 ``_source`` 通道），本插件不再
        自抓页面。目录是纯静态的，零网络。
        """
        try:
            raw = self._source("list_ranks")
        except _SourceUnavailable:
            raw = None
            message = f"{_SOURCE_LABEL} 还没有提供榜单目录（list_ranks 模块方法）"
        except Exception as err:  # noqa: BLE001 - 目录取不到不该把面板打不开
            logger.warning(f"{PLUGIN_NAME} 取榜单目录失败：{err}")
            raw = None
            message = f"榜单目录获取失败：{err}"
        else:
            message = str(raw.get("message") or "") if isinstance(raw, dict) else ""
        items = (raw or {}).get("ranks") if isinstance(raw, dict) else None
        return schemas.Response(
            success=True,
            data=api_models.RanksData(
                ranks=[
                    api_models.RankRow(
                        key=str(item.get("key") or ""),
                        name=str(item.get("name") or ""),
                        has_detail=item.get("has_detail") is not False,
                    )
                    for item in (items or [])
                    if isinstance(item, dict)
                ],
                message=message,
            ),
        )

    def api_rank_works(
        self, rank: str = "", page: str = "1"
    ) -> "schemas.Response[api_models.RankWorksData]":
        """一个榜单的作品卡（发现页网格用，``GET /ranks/works?rank=rebo&page=1``）。

        2026-10-23 用户口径：数据源按**实际页面**解析（不与 ``actor_works``
        对齐），这里原样透传 ``medias``——不归一、不套在库判定与订阅台账；
        卡片样式由前端映射到与作品页同一张卡。

        2026-10-24：「推荐」页支持翻页（``/tuijian.html?page=N``），按 ``page``
        透传给数据源并回传 ``has_more``；``/paihang/*`` 排行榜页不分页
        （传了也忽略，``has_more`` 恒假）。抓不到时 ``medias`` 空 + ``message``，
        不算接口失败。
        """
        page_no = max(1, _to_int(page, 1))
        key = str(rank or "").strip().lower()
        try:
            raw = self._source("rank_medias", rank=key, page=page_no)
        except _SourceUnavailable:
            return schemas.Response(
                success=True,
                data=api_models.RankWorksData(
                    rank=key,
                    page=page_no,
                    message=f"{_SOURCE_LABEL} 还没有提供榜单取数（rank_medias 模块方法）",
                ),
            )
        except Exception as err:  # noqa: BLE001 - 榜单取不到不该把面板打不开
            logger.warning(f"{PLUGIN_NAME} 取榜单失败（{key} p{page_no}）：{err}")
            return schemas.Response(
                success=True,
                data=api_models.RankWorksData(
                    rank=key, page=page_no, message=f"榜单获取失败：{err}"
                ),
            )
        raw = raw if isinstance(raw, dict) else {}
        rows = [card for card in raw.get("medias") or [] if isinstance(card, dict)]
        # 卡片上的「入库」图标：用作品页同一个在库探针（缓存共享，只按剧名判）
        probe = self.library_probe
        if probe.available:
            for row in rows:
                row["in_library"] = probe.lookup(row)
        return schemas.Response(
            success=True,
            data=api_models.RankWorksData(
                rank=key,
                name=str(raw.get("name") or ""),
                page=_to_int(raw.get("page"), page_no),
                has_more=bool(raw.get("has_more")),
                medias=[api_models.RankMediaRow(**row) for row in rows],
                message=str(raw.get("message") or ""),
            ),
        )

    def api_logs(self, limit: str = "80") -> "schemas.Response[api_models.LogsData]":
        """插件最近日志（面板右上「日志」面板用，``GET /logs?limit=80``）。

        宿主按插件把日志分文件（``<LOG_PATH>/plugins/<插件类名小写>.log``，
        2026-10-23 实测：文件名取的是**类名**不是 ``plugin_name`` —— 中文插件名
        拼出来的路径永远不存在），
        这里直接取文件尾部，不用再挂 logging handler（免得热重载时重复挂 /
        漏摘）。旧行在前、新行在后，前端自动滚到底就是「实时滚动」。
        """
        n = min(400, max(20, _to_int(limit, 80)))
        items: List[str] = []
        try:
            from app.core.config import settings

            path = (
                Path(settings.LOG_PATH)
                / "plugins"
                / f"{self.__class__.__name__.lower()}.log"
            )
        except Exception as err:  # noqa: BLE001 - 宿主版本差异兜底
            logger.warning(f"{PLUGIN_NAME} 日志路径取不到：{err}")
            path = None
        if path is not None and path.exists():
            try:
                with path.open("rb") as fh:
                    fh.seek(0, 2)
                    size = fh.tell()
                    fh.seek(max(0, size - 512 * 1024))
                    text = fh.read().decode("utf-8", "ignore")
                # 首行可能是半截（512KB 窗口从中间切开），丢掉
                lines = text.splitlines()
                if size > 512 * 1024 and lines:
                    lines = lines[1:]
                # 面板只显示消息本体（2026-10-23 用户口径）：去掉
                # 「【INFO】2026-10-23 22:25:50,960 [-] - 插件id - 」这段前缀，
                # 以及消息里自带的插件名开头（「短剧演员订阅 …」）
                items = [
                    _clean_log_line(line) for line in lines if line.strip()
                ][-n:]
            except Exception as err:  # noqa: BLE001 - 读日志失败不影响面板
                logger.warning(f"{PLUGIN_NAME} 读取插件日志失败：{err}")
        return schemas.Response(success=True, data=api_models.LogsData(items=items))

    def api_actor_cards(
        self, enrich: str = ""
    ) -> "schemas.Response[api_models.ActorCardsData]":
        """已关注演员的**卡片数据**（面板「已关注的演员」区块用）。

        字段与 ``/actors/search`` 的候选行同构 —— 前端两处用**同一个卡片组件**渲染，
        视觉与交互因此完全一致。

        档案（头像 / 简介 / 身份）读**进程内缓存**（数据源为主，档案不落盘）：发现流程
        每轮会顺带补一次（见 ``_fill_profile_cache``），缓存热着就是纯内存操作、秒回。
        ``enrich=1`` 时对档案还不全的演员现取一次（最多 ``_ACTOR_LOOKUP_LIMIT`` 位）——
        首次安装、或想立刻看到头像时用（会慢几秒）。

        参数是函数形参：FastAPI 按名注入查询参数（见 ``api_works`` 的说明）。
        """
        snapshot = self._load_actors()
        rows = [self._actor_card_row(key, snapshot.get(key)) for key in self._actors]
        if _to_bool(enrich):
            # 已关注列表动辄上百位：一次请求就尽力补全（并发 6 路，120 秒超时够用）
            self._fill_actor_profiles(rows, limit=len(rows))
        return schemas.Response(
            success=True,
            data=api_models.ActorCardsData(
                actors=[api_models.ActorCardRow(**row) for row in rows]
            ),
        )

    def _collect_fresh(self, before: Dict[str, Any]) -> List[Dict[str, Any]]:
        """找出这一轮**新出现、且最近 :data:`_NEW_WINDOW_DAYS` 天内上映**的作品。

        两个条件都得满足，缺一不可：

        * 「新出现」= 刷新前还没有 ``first_seen`` 键 —— 首次建立基线的演员整批都不算
          （否则一次导入十几位演员会整片刷屏）；
        * 「最近上映」= ``release_date`` 在窗口内 —— 与作品墙「新作品」**同一口径**
          （:func:`is_fresh_work`）。只按「新出现」报会跟墙上的标记对不上。

        作品从刚写回快照的 ``works`` 里查（取不到的只跳过，不硬编标题）。
        """
        after = self._load_actors()
        now = time.time()
        # 主键正在从名字归位成 ID（:meth:`_rekey_actors` 在每轮刷新后跑）：基线
        # ``before`` 还拿着旧键。按「键或记录里的 baike_id」建一次索引，新旧键都能对上
        baseline: Dict[str, Dict[str, Any]] = {}
        for old_key, old_record in before.items():
            if not isinstance(old_record, dict):
                continue
            old_id = _actor_id_of(old_record.get("baike_id"))
            baseline[old_id or old_key] = old_record
        fresh: List[Dict[str, Any]] = []
        for key, record in after.items():
            if not isinstance(record, dict):
                continue
            old = baseline.get(key)
            old_map = (old or {}).get("first_seen") if isinstance(old, dict) else None
            if not isinstance(old_map, dict) or not old_map:
                continue
            current = record.get("first_seen")
            current = current if isinstance(current, dict) else {}
            new_keys = [item for item in current if item not in old_map]
            if not new_keys:
                continue
            actor = _clean_text(record.get("name")) or key
            works = snapshot_works(record)
            if not works:
                cached = self._works_cache.get(key)
                works = cached[0] if isinstance(cached, tuple) else []
            lookup = {
                work_identity(work): work for work in works if isinstance(work, dict)
            }
            for item in new_keys:
                work = lookup.get(item)
                if not work or not is_fresh_work(work, now):
                    continue
                fresh.append({"actor": actor, **work})
        return fresh

    def _notify_fresh(self, fresh: List[Dict[str, Any]]) -> None:
        """新作品汇总通知（一条，不逐条刷屏）。"""
        if not fresh or not self._notify:
            return
        lines = [f"发现 {len(fresh)} 部新作品："]
        for item in fresh[:10]:
            title = _clean_text(item.get("title"))
            actor = _clean_text(item.get("actor"))
            lines.append(f"· {actor}：{title}")
        if len(fresh) > 10:
            lines.append(f"· ……另有 {len(fresh) - 10} 部")
        try:
            self.post_message(
                mtype=_MessageType.Plugin,
                title=f"【{self.plugin_name}】新作品",
                text="\n".join(lines),
            )
        except Exception as err:  # noqa: BLE001 - 通知失败不该影响发现结果
            logger.warning(f"{PLUGIN_NAME} 发送新作品通知失败：{err}")

    @staticmethod
    def _log_actor_states(snapshot: Dict[str, Any]) -> None:
        """把整轮演员状态汇总成最多两条日志（等待重试 / 百科未收录）。"""
        waiting: List[str] = []
        empty: List[str] = []
        for key, record in snapshot.items():
            name = _clean_text(record.get("name")) or key
            state = _clean_text(record.get("state"))
            if state == "waiting":
                waiting.append(name)
            elif state == "empty":
                empty.append(name)
        if waiting:
            logger.info(
                f"{PLUGIN_NAME} 暂未取到作品的演员（会自动重试）：{'、'.join(waiting)}"
            )
        if empty:
            logger.info(f"{PLUGIN_NAME} 短剧百科未收录的演员：{'、'.join(empty)}")

    # ── 自动订阅 ──

    def _auto_subscribe_ledger(self) -> Dict[str, Any]:
        """读自动订阅台账（``media_id`` → 处理记录）。"""
        data = self.get_data(_DATA_AUTO_SUB)
        if not isinstance(data, dict):
            return {}
        return {
            str(key): value
            for key, value in data.items()
            if isinstance(value, dict) and str(key).strip()
        }

    def _save_auto_subscribe_ledger(self, ledger: Dict[str, Any]) -> None:
        """把台账写回（只留最近 ``_AUTO_SUB_LIMIT`` 条，按处理时间倒序截断）。"""
        rows = sorted(
            ledger.items(),
            key=lambda kv: str(kv[1].get("time") or ""),
            reverse=True,
        )[:_AUTO_SUB_LIMIT]
        self.save_data(_DATA_AUTO_SUB, dict(rows))

    # ── 自建订阅搜索 ──

    def _sub_ledger(self) -> Dict[str, Any]:
        """读自建订阅搜索台账（``media_id`` → 处理记录）。"""
        data = self.get_data(_DATA_SUB_SEARCH)
        if not isinstance(data, dict):
            return {}
        return {
            str(key): value
            for key, value in data.items()
            if isinstance(value, dict) and str(key).strip()
        }

    def _save_sub_ledger(self, ledger: Dict[str, Any]) -> None:
        """把自建订阅搜索台账写回（按处理时间倒序截断）。"""
        rows = sorted(
            ledger.items(),
            key=lambda kv: str(kv[1].get("time") or ""),
            reverse=True,
        )[:_SUB_SEARCH_LIMIT]
        self.save_data(_DATA_SUB_SEARCH, dict(rows))

    # ── 自建订阅清单（引擎 = self 时订阅归插件自己管）──

    def _plugin_subs(self) -> Dict[str, Any]:
        """读插件订阅清单（``media_id`` → 订阅记录）。"""
        data = self.get_data(_DATA_SUBS)
        if not isinstance(data, dict):
            return {}
        return {
            str(key): value
            for key, value in data.items()
            if isinstance(value, dict) and str(key).strip()
        }

    def _plugin_subscribe(self, row: Dict[str, Any], actor: str = "") -> Tuple[bool, str]:
        """把一部作品记进插件订阅清单（幂等；返回 ``(是否新增, 提示)``）。"""
        media_id = _clean_text(row.get("media_id"))
        title = _clean_text(row.get("title"))
        if not media_id or not title:
            return False, "缺少媒体身份，无法订阅"
        subs = self._plugin_subs()
        if media_id in subs:
            return False, "已在订阅清单里"
        subs[media_id] = {
            "time": datetime.now().strftime(_STAMP_FORMAT),
            "title": title,
            "year": _clean_text(row.get("year")),
            "media_id": media_id,
            "media_source": _clean_text(row.get("media_source")) or _BAIKE_SOURCE,
            "actor": _clean_text(actor),
            "poster": _clean_text(row.get("poster")),
        }
        self.save_data(_DATA_SUBS, subs)
        # 订阅了就把搜索台账里的旧处理记录清掉（冷却 / 终态都不该挡住新订阅）
        ledger = self._sub_ledger()
        if media_id in ledger:
            del ledger[media_id]
            self._save_sub_ledger(ledger)
        return True, f"已订阅《{title}》，等订阅搜索自动下载"

    def _plugin_unsubscribe(self, media_id: str) -> Tuple[bool, str]:
        """把一部作品移出插件订阅清单（幂等）。"""
        media_id = _clean_text(media_id)
        subs = self._plugin_subs()
        if media_id not in subs:
            return False, "不在订阅清单里"
        title = _clean_text(subs[media_id].get("title"))
        del subs[media_id]
        self.save_data(_DATA_SUBS, subs)
        return True, f"已取消订阅《{title}》"

    def _plugin_subscribe_update(
        self,
        media_id: str,
        sites: Optional[str] = None,
        downloader: Optional[str] = None,
        save_path: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """编辑一条插件订阅的落点：站点 / 下载器 / 保存目录。

        三项落点（2026-10-22 用户口径）都是「订阅自己配优先，留空 = 用配置页默认」，
        所以传空串等于**清除覆盖**；``None`` 表示这次不动这一项。

        订阅没有暂停态（2026-10-23 用户口径）：想停就取消订阅 —— 取消时台账记录
        一并清掉（见 :meth:`_plugin_unsubscribe`）。
        """
        media_id = _clean_text(media_id)
        subs = self._plugin_subs()
        if media_id not in subs:
            return False, "不在插件订阅清单里（宿主订阅请到订阅页管理）"
        entry = subs[media_id]
        title = _clean_text(entry.get("title"))
        changed: List[str] = []
        if sites is not None:
            entry["sites"] = self._parse_site_ids(sites)
            changed.append("站点")
        if downloader is not None:
            entry["downloader"] = _clean_text(downloader)
            changed.append("下载器")
        if save_path is not None:
            entry["save_path"] = _clean_save_path(save_path)
            changed.append("保存目录")
        if not changed:
            return True, "未改动"
        self.save_data(_DATA_SUBS, subs)
        return True, f"已更新《{title}》的{'、'.join(changed)}"

    def _random_picked(self) -> Dict[str, Any]:
        """读随机订阅已挑记录（``media_id`` → 挑选记录）。"""
        data = self.get_data(_DATA_RANDOM_PICKED)
        if not isinstance(data, dict):
            return {}
        return {
            str(key): value
            for key, value in data.items()
            if isinstance(value, dict) and str(key).strip()
        }

    def _save_random_picked(self, picked: Dict[str, Any]) -> None:
        """把随机订阅已挑记录写回（按挑选时间倒序截断）。"""
        rows = sorted(
            picked.items(),
            key=lambda kv: str(kv[1].get("time") or ""),
            reverse=True,
        )[:_RANDOM_PICKED_LIMIT]
        self.save_data(_DATA_RANDOM_PICKED, dict(rows))

    def _subscribed_site_rss_urls(
        self, wanted: Dict[str, Any], RssHelper: Any, SiteOper: Any
    ) -> Tuple[List[str], List[str]]:
        """从**订阅站点**的站点配置解析 RSS 源（不单独配置，2026-10-23 用户口径）。

        站点集合 = 配置页「订阅站点」默认 ∪ 各订阅自己的站点（都为空 = 不限定，
        用全部启用站点）。每个站点：站点配置自带 ``rss`` 地址**直接用**；没有则
        用站点 cookie 现场生成（``RssHelper.get_rss_link``，与宿主 CookieCloud
        同步生成 RSS 同一套逻辑）—— 生成要去站点打一炮，进程内缓存 24 小时，
        别每半小时都去生成一遍。

        返回 ``(rss 地址列表, 站点名列表)``，两表按下标对齐。
        """
        site_ids: set = set(self._site_ids(self._subscribe_sites))
        for sub in wanted.values():
            site_ids.update(self._site_ids(sub.get("sites")))
        try:
            sites = [
                site
                for site in (SiteOper().list_active() or [])
                if getattr(site, "id", None) is not None
            ]
        except Exception as err:  # noqa: BLE001 - 读站点配置失败本轮就算了
            logger.warning(f"{PLUGIN_NAME} 读站点配置失败，RSS 检查跳过：{err}")
            return [], []
        if site_ids:
            sites = [site for site in sites if site.id in site_ids]
        urls: List[str] = []
        names: List[str] = []
        cache = getattr(self, "_rss_link_cache", None)
        if not isinstance(cache, dict):
            cache = self._rss_link_cache = {}
        now = time.time()
        for site in sites:
            name = _clean_text(getattr(site, "name", None)) or f"站点#{site.id}"
            # 站点配置里存了 RSS 地址：直接用（零额外请求）
            rss_url = _clean_text(getattr(site, "rss", None))
            if rss_url:
                urls.append(rss_url)
                names.append(name)
                continue
            url = _clean_text(getattr(site, "url", None))
            cookie = _clean_text(getattr(site, "cookie", None))
            if getattr(site, "public", 0) or not url or not cookie:
                logger.debug(
                    f"{PLUGIN_NAME} 站点 {name} 没有配置 RSS 且无法生成（公开站 / 缺地址或 Cookie），跳过"
                )
                continue
            # 缓存命中的生成结果（24 小时）：生成链接本身要去站点走一趟
            cached = cache.get(site.id)
            if cached and cached[0] and now - cached[1] < 86400:
                urls.append(cached[0])
                names.append(name)
                continue
            try:
                rss_url, errmsg = RssHelper().get_rss_link(
                    url=url,
                    cookie=cookie,
                    ua=_clean_text(getattr(site, "ua", None)) or "Mozilla/5.0",
                    proxy=bool(getattr(site, "proxy", 0)),
                    timeout=_to_int(getattr(site, "timeout", None)) or 15,
                )
            except Exception as err:  # noqa: BLE001 - 单站失败不影响其它站点
                logger.warning(f"{PLUGIN_NAME} 站点 {name} 生成 RSS 链接失败：{err}")
                continue
            if rss_url:
                cache[site.id] = (rss_url, now)
                urls.append(rss_url)
                names.append(name)
            else:
                logger.warning(
                    f"{PLUGIN_NAME} 站点 {name} 生成 RSS 链接失败："
                    f"{_clean_text(errmsg) or '原因未知'}"
                )
        return urls, names

    def _rss_history(self) -> Dict[str, Any]:
        """读 RSS 处理历史（条目标题 → 处理记录）。"""
        data = self.get_data(_DATA_RSS_HISTORY)
        if not isinstance(data, dict):
            return {}
        return {
            str(key): value
            for key, value in data.items()
            if isinstance(value, dict) and str(key).strip()
        }

    def _save_rss_history(self, history: Dict[str, Any]) -> None:
        """把 RSS 处理历史写回（按处理时间倒序截断，上限 :data:`_RSS_HISTORY_LIMIT`）。"""
        rows = sorted(
            history.items(),
            key=lambda kv: str(kv[1].get("time") or ""),
            reverse=True,
        )[:_RSS_HISTORY_LIMIT]
        self.save_data(_DATA_RSS_HISTORY, dict(rows))

    def rss_check_task(self, trigger: str = "interval") -> bool:
        """订阅站 RSS 增量检查：拉站点 RSS，与当前订阅匹配，命中直接下载。

        「接入宿主 RSS 系统」的落地形态（2026-10-23 用户拍板路径 1）：复用宿主
        ``app.sdk.network.RssHelper`` 拉取解析（与内置 rsssubscribe 插件同一套），
        每条新种子与**当前订阅**做 :func:`match_work_context` 消歧，命中且该订阅
        还需要资源（无终态 / 不在库 / 下载历史没有）时交宿主下载链。RSS 是普通
        页面请求，不打搜索接口 —— 避开站点流控；主动搜索降级为兜底。

        RSS 源**不单独配置**：直接取订阅站点的站点配置（见
        :meth:`_subscribed_site_rss_urls`）。与搜索任务共用 ``_sub_lock``：上一轮
        搜索/检查还在跑时本轮直接跳过（RSS 半小时后又来，不争这一时）。处理历史
        按条目标题去重，与宿主 rsssubscribe 插件同口径 —— 站点种子只判一次。
        """
        if not self.get_state() or not self._actors:
            return False
        if not self._sub_lock.acquire(blocking=False):
            logger.info(f"{PLUGIN_NAME} RSS 检查（{trigger}）：订阅搜索 / 上一轮检查进行中，本次跳过")
            return False
        try:
            try:
                from app.chain.download import DownloadChain
                from app.chain.media import MediaChain
                from app.db.oper.site import SiteOper
                from app.sdk.media import Context, TorrentInfo
                from app.sdk.network import RssHelper
                from app.schemas.types import MediaSource as _MediaSourceEnum
            except Exception as err:  # noqa: BLE001 - 宿主版本差异
                logger.warning(f"{PLUGIN_NAME} RSS 检查依赖不可用：{err}")
                return False
            wanted = self._subscribed_works()
            if not wanted:
                logger.info(f"{PLUGIN_NAME} RSS 检查（{trigger}）：没有进行中的短剧订阅，本轮跳过")
                return True
            urls, site_names = self._subscribed_site_rss_urls(wanted, RssHelper, SiteOper)
            if not urls:
                logger.info(
                    f"{PLUGIN_NAME} RSS 检查（{trigger}）：订阅站点没有可用的 RSS 源，本轮跳过"
                )
                return True
            logger.info(f"{PLUGIN_NAME} RSS 检查（{trigger}）：源 = {'、'.join(site_names)}")
            # 行索引（拿演员署名与消歧旁证，与订阅搜索任务同一段逻辑）
            snapshot = self._load_actors()
            rows_index: Dict[str, Tuple[Dict[str, Any], str]] = {}
            for key, record in snapshot.items():
                if not isinstance(record, dict):
                    continue
                actor = _clean_text(record.get("name")) or key
                for work in self._actor_works_cached(key, record):
                    if not isinstance(work, dict):
                        continue
                    row = work_row(work, actor, key)
                    mid = _clean_text(row.get("media_id"))
                    if mid in wanted and mid not in rows_index:
                        rows_index[mid] = (row, actor)
            history = self._rss_history()
            ledger = self._sub_ledger()
            ledger_dirty = False
            probe = self.library_probe
            sites = [
                int(item)
                for item in str(self._subscribe_sites or "").split(",")
                if item.strip().isdigit()
            ]
            downloader = self._subscribe_downloader or None
            save_path = self._subscribe_save_path or None
            checked = matched = downloaded = failed = skipped = 0
            for url in urls:
                try:
                    items = RssHelper().parse(url) or []
                except Exception as err:  # noqa: BLE001 - 单个地址失败不影响其它
                    logger.warning(f"{PLUGIN_NAME} RSS 拉取失败：{err}（{url}）")
                    continue
                if not items:
                    logger.warning(f"{PLUGIN_NAME} 未获取到 RSS 数据：{url}")
                    continue
                for item in items:
                    title = _clean_text(item.get("title"))
                    if not title or title in history:
                        continue
                    checked += 1
                    # 先记历史再处理：这条种子本轮就下结论，下一轮不再看它
                    pubdate = item.get("pubdate")
                    history[title] = {
                        "time": datetime.now().strftime(_STAMP_FORMAT),
                        "url": _clean_text(item.get("link")),
                        "enclosure": _clean_text(item.get("enclosure")),
                    }
                    description = _clean_text(item.get("description"))
                    try:
                        torrent = TorrentInfo(
                            title=title,
                            description=description,
                            enclosure=_clean_text(item.get("enclosure")),
                            page_url=_clean_text(item.get("link")),
                            size=item.get("size"),
                            pubdate=(
                                pubdate.strftime("%Y-%m-%d %H:%M:%S")
                                if hasattr(pubdate, "strftime")
                                else _clean_text(pubdate)
                            ),
                        )
                        context = Context(
                            meta_info=MetaInfo(title=title, subtitle=description),
                            media_info=None,
                            torrent_info=torrent,
                        )
                    except Exception as err:  # noqa: BLE001 - 单条坏数据不影响其它
                        logger.warning(f"{PLUGIN_NAME} RSS 条目构造种子失败：{title}（{err}）")
                        continue
                    # ── 与当前订阅逐个消歧 ──
                    for media_id, sub in wanted.items():
                        found = rows_index.get(media_id)
                        if found is not None:
                            row, actor = found
                        else:
                            actor = _clean_text(sub.get("actor")) or "（订阅）"
                            row = {
                                "title": _clean_text(sub.get("name")),
                                "year": _clean_text(sub.get("year")),
                                "media_id": media_id,
                                "media_source": _BAIKE_SOURCE,
                                "type": "电视剧",
                            }
                        row_title = _clean_text(row.get("title"))
                        if not row_title:
                            continue
                        hit, why = match_work_context(
                            context, row, normalize_title(row_title)
                        )
                        if not hit:
                            continue
                        matched += 1
                        # 终态跳过：这部已下载 / 已在库 / 下载历史已有，不用再下
                        entry = ledger.get(media_id)
                        if isinstance(entry, dict) and _clean_text(entry.get("state")) in (
                            "downloaded",
                            "in_library",
                            "history",
                        ):
                            skipped += 1
                            continue
                        # 在库跳过（与订阅搜索任务同口径，无条件）
                        if probe.available and probe.lookup(row) is True:
                            ledger[media_id] = {
                                "time": datetime.now().strftime(_STAMP_FORMAT),
                                "state": "in_library",
                                "detail": "已在媒体库，跳过",
                                "title": row_title,
                                "year": _clean_text(row.get("year")),
                                "media_id": media_id,
                                "actor": actor,
                            }
                            ledger_dirty = True
                            skipped += 1
                            continue
                        done, why_done = self._downloaded_before(row)
                        if done:
                            ledger[media_id] = {
                                "time": datetime.now().strftime(_STAMP_FORMAT),
                                "state": "history",
                                "detail": why_done,
                                "title": row_title,
                                "year": _clean_text(row.get("year")),
                                "media_id": media_id,
                                "actor": actor,
                            }
                            ledger_dirty = True
                            skipped += 1
                            continue
                        # ── 命中：补 djbaike 媒体识别（download_single 的硬门槛），
                        # 交宿主下载链，落点沿用订阅自己的设置 ──
                        try:
                            media = MediaChain().recognize_media(
                                meta=MetaInfo(title=row_title, subtitle=description),
                                media_source=_MediaSourceEnum(_BAIKE_SOURCE),
                            )
                        except Exception as err:  # noqa: BLE001 - 识别失败只影响这一条
                            media = None
                            logger.warning(
                                f"{PLUGIN_NAME} RSS 命中《{row_title}》识别媒体异常：{err}"
                            )
                        torrent_title = _clean_text(getattr(torrent, "title", None)) or title
                        page_url = _clean_text(getattr(torrent, "page_url", None))
                        if media is None:
                            ledger[media_id] = {
                                "time": datetime.now().strftime(_STAMP_FORMAT),
                                "state": "failed",
                                "detail": f"RSS 命中（{why}）但按作品名识别媒体失败",
                                "title": row_title,
                                "year": _clean_text(row.get("year")),
                                "media_id": media_id,
                                "actor": actor,
                                "torrent_url": page_url,
                                "torrent_title": torrent_title,
                            }
                            ledger_dirty = True
                            failed += 1
                            logger.warning(
                                f"{PLUGIN_NAME} RSS 命中《{row_title}》：识别媒体失败，"
                                f"交给后续订阅搜索兜底"
                            )
                            break
                        sub_targets = self._sub_targets(sub)
                        download_hash: Any = None
                        err_text = ""
                        try:
                            download_outcome = DownloadChain().download_single(
                                Context(meta_info=meta, media_info=media, torrent_info=torrent),
                                downloader=sub_targets[1] or downloader or None,
                                save_path=sub_targets[2] or save_path or None,
                                username=PLUGIN_NAME,
                                return_detail=True,
                            )
                        except Exception as err:  # noqa: BLE001 - 提交失败只影响这一条
                            err_text = str(err)
                        else:
                            if isinstance(download_outcome, tuple):
                                download_hash, err_text = (
                                    download_outcome[0],
                                    _clean_text(download_outcome[1]),
                                )
                            else:
                                download_hash = download_outcome
                        if download_hash:
                            ledger[media_id] = {
                                "time": datetime.now().strftime(_STAMP_FORMAT),
                                "state": "downloaded",
                                "detail": f"RSS 命中（{why}）",
                                "title": row_title,
                                "year": _clean_text(row.get("year")),
                                "media_id": media_id,
                                "actor": actor,
                                "hash": str(download_hash),
                                "torrent_url": page_url,
                                "torrent_title": torrent_title,
                            }
                            ledger_dirty = True
                            downloaded += 1
                            logger.info(
                                f"{PLUGIN_NAME} RSS 命中《{row_title}》：{torrent_title}"
                                f"（{why}），已提交下载"
                            )
                        else:
                            ledger[media_id] = {
                                "time": datetime.now().strftime(_STAMP_FORMAT),
                                "state": "failed",
                                "detail": f"RSS 命中（{why}）但下载链未受理："
                                f"{_clean_text(err_text) or '原因未知'}",
                                "title": row_title,
                                "year": _clean_text(row.get("year")),
                                "media_id": media_id,
                                "actor": actor,
                                "torrent_url": page_url,
                                "torrent_title": torrent_title,
                            }
                            ledger_dirty = True
                            failed += 1
                            logger.warning(
                                f"{PLUGIN_NAME} RSS 命中《{row_title}》下载未受理：{err_text}"
                            )
                        # 一条种子喂饱一个订阅就够了（同一部不会要两份）
                        break
            self._save_rss_history(history)
            if ledger_dirty:
                self._save_sub_ledger(ledger)
            logger.info(
                f"{PLUGIN_NAME} RSS 检查完成（{trigger}）：新条目 {checked}"
                + (f"，命中订阅 {matched} 次" if matched else "")
                + (f"，提交下载 {downloaded}" if downloaded else "")
                + (f"，失败 {failed}" if failed else "")
                + (f"，已下载 / 在库跳过 {skipped}" if skipped else "")
            )
            return True
        finally:
            try:
                self._sub_lock.release()
            except Exception:  # noqa: BLE001 - 锁已在他处释放
                pass

    def _search_now_worker(self, media_id: str, sub: Dict[str, Any]) -> None:
        """「立即搜索」的后台worker：与订阅搜索任务同一把锁、同一套台账格式。"""
        title = _clean_text(sub.get("name"))
        try:
            if not self._sub_lock.acquire(blocking=False):
                # 上一轮任务还在跑：台账已清，那轮结束后下一轮会先搜它，不重复排队
                logger.info(f"{PLUGIN_NAME} 立即搜索《{title}》：订阅搜索任务进行中，交给下一轮")
                return
        except Exception:  # noqa: BLE001 - 锁异常按失败记
            return
        try:
            # 落点（站点 / 下载器 / 目录）：订阅自己的设置优先，空则回落配置页默认
            sites, downloader, save_path = self._sub_targets(sub)
            row = {
                "title": title,
                "year": _clean_text(sub.get("year")),
                "media_id": media_id,
                "media_source": _BAIKE_SOURCE,
                "type": "电视剧",
                # 集数 / 演员是消歧旁证（短剧站标题是「剧名（66集）演员A&演员B - SKIT」）：
                # 订阅记录本身不存集数，靠 _subscribed_works() 从作品快照补进来 ——
                # 这里漏带的话，按「立即搜索」永远只能靠剧名孤证，必判「缺旁证」。
                "episode_count": _to_int(sub.get("episode_count")),
                "actor": _clean_text(sub.get("actor")),
            }
            actor = _clean_text(sub.get("actor")) or "（订阅）"
            # 已入库不再执行下载（2026-10-23 用户拍板，与订阅搜索任务同口径）：
            # 立即搜索对在库作品没有意义，记一条 in_library 台账让前端显示原因
            probe = self.library_probe
            if probe.available and probe.lookup(row) is True:
                ledger = self._sub_ledger()
                ledger[media_id] = {
                    "time": datetime.now().strftime(_STAMP_FORMAT),
                    "state": "in_library",
                    "detail": "已在媒体库，跳过",
                    "title": title,
                    "year": _clean_text(row.get("year")),
                    "media_id": media_id,
                    "actor": actor,
                }
                self._save_sub_ledger(ledger)
                logger.info(f"{PLUGIN_NAME} 立即搜索《{title}》：已在媒体库，跳过")
                return
            outcome = self._self_search_one(row, sites, downloader, save_path)
            state, detail = outcome["state"], outcome["detail"]
            ledger = self._sub_ledger()
            ledger[media_id] = {
                "time": datetime.now().strftime(_STAMP_FORMAT),
                "state": state,
                "detail": detail,
                "title": title,
                "year": _clean_text(row.get("year")),
                "media_id": media_id,
                "actor": actor,
                "hash": outcome["hash"],
                # 台账只留「种子页面 + 种子标题」：详情页给一枚按钮直接跳种子页
                "torrent_url": outcome["url"],
                "torrent_title": outcome["title"],
            }
            self._save_sub_ledger(ledger)
            if state == "downloaded":
                logger.info(f"{PLUGIN_NAME} 立即搜索下载《{title}》（{detail}）")
            else:
                logger.info(f"{PLUGIN_NAME} 立即搜索《{title}》：{detail}")
        except Exception as err:  # noqa: BLE001 - 单部失败不影响其它订阅
            logger.warning(f"{PLUGIN_NAME} 立即搜索《{title}》异常：{err}")
        finally:
            try:
                self._sub_lock.release()
            except Exception:  # noqa: BLE001 - 锁已在他处释放
                pass

    def _works_by_id(self) -> Dict[str, Dict[str, Any]]:
        """作品快照按 ``media_id`` 建索引（只读快照，不打数据源）。

        订阅清单里只存了标题 / 年份 / 演员 / 海报，**没有集数与身份** —— 而自建
        搜索的消歧要「集数」或「身份」当旁证，缺了就只能靠标题孤零零比对，短剧
        站那种「剧名（66集）演员A&演员B - SKIT」的标题极易被判「缺旁证」。
        这里按 id 从作品快照补回来（2026-10-22 真机：《梧栖春山》因此漏掉 PTS 的种）。
        """
        index: Dict[str, Dict[str, Any]] = {}
        for key, record in self._load_actors().items():
            if not isinstance(record, dict):
                continue
            for work in self._actor_works_cached(key, record) or []:
                if not isinstance(work, dict):
                    continue
                media_id = _clean_text(work.get("media_id"))
                if media_id and media_id not in index:
                    index[media_id] = work
        return index

    def _subscribed_works(self) -> Dict[str, Dict[str, Any]]:
        """自建搜索的候选 = 当前**有效的订阅**（``media_id`` → 记录）。

        两个来源取并集：
        1. 插件订阅清单（引擎 = self 时「订阅」落这里，见 :meth:`_plugin_subscribe`）；
        2. 宿主订阅表里 ``media_source=djbaike`` 的订阅（引擎切回宿主期间或更早
           建下的订阅，切换引擎不丢）。

        订阅没有暂停态（2026-10-23 用户口径）：清单里的都在跑，要停就取消订阅。
        宿主订阅表里 ``state=S`` 的条目也一视同仁地纳入（它是「在清单里」的一种）。

        每条记录都会用 :meth:`_works_by_id` 补上 ``episode_count`` / ``media_id`` /
        ``media_source``（订阅清单本身不存这三项）：消歧的「集数 / 身份」旁证全靠它们。
        """
        works_index = self._works_by_id()

        def enrich(
            media_id: str,
            *,
            name: str,
            year: str,
            actor: str,
            poster: str,
            sites: str = "",
            downloader: str = "",
            save_path: str = "",
        ) -> Dict[str, Any]:
            work = works_index.get(media_id) or {}
            return {
                "name": name or _clean_text(work.get("title")),
                "year": year or _clean_text(work.get("year")),
                "actor": actor or _clean_text(work.get("actor")),
                "poster": poster or _clean_text(work.get("poster")),
                "episode_count": _to_int(work.get("episode_count")),
                "media_id": media_id,
                "media_source": _BAIKE_SOURCE,
                # 订阅级落点（空 = 用配置页默认，见 _sub_targets）
                "sites": _clean_text(sites),
                "downloader": _clean_text(downloader),
                "save_path": _clean_save_path(save_path),
            }

        wanted: Dict[str, Dict[str, Any]] = {}
        for media_id, entry in self._plugin_subs().items():
            wanted[media_id] = enrich(
                media_id,
                name=_clean_text(entry.get("title")),
                year=_clean_text(entry.get("year")),
                actor=_clean_text(entry.get("actor")),
                poster=_clean_text(entry.get("poster")),
                sites=_clean_text(entry.get("sites")),
                downloader=_clean_text(entry.get("downloader")),
                save_path=_clean_text(entry.get("save_path")),
            )
        return wanted
    def _attach_sub_state(self, rows: List[Dict[str, Any]]) -> None:
        """给作品行补自建订阅搜索状态（行就地改；引擎非 ``self`` 时不加字段）。

        作品墙 / 演员作品页都调它 —— 「哪部会被下载、为什么没下」直接写在卡上，
        不用去翻日志。字段：``sub_state``（downloaded / history / in_library /
        noresult / failed）、``sub_detail``（人话说明）、``sub_time``（处理时间）；
        没进台账的行不加字段（= 还没轮到）。
        """
        if self._subscribe_engine != "self" or not rows:
            return
        ledger = self._sub_ledger()
        if not ledger:
            return
        for row in rows:
            entry = ledger.get(_clean_text(row.get("media_id")))
            if isinstance(entry, dict):
                row["sub_state"] = _clean_text(entry.get("state"))
                row["sub_detail"] = _clean_text(entry.get("detail"))
                row["sub_time"] = _clean_text(entry.get("time"))
                # 台账只留「种子页面 + 种子标题」：详情页渲染成按钮 + 一行标题
                row["sub_url"] = _clean_text(entry.get("torrent_url"))
                row["sub_torrent"] = _clean_text(entry.get("torrent_title"))

    @staticmethod
    def _sub_entry_due(entry: Dict[str, Any]) -> bool:
        """台账条目是否到期需要再处理（断点续跑的核心判断）。

        终态（已下载 / 已在库 / 下载历史已有）永不再跑；``noresult`` 按
        ``_SUB_SEARCH_NORESULT_RETRY_HOURS`` 冷却（站上可能上新种），其余失败按
        ``_SUB_SEARCH_RETRY_HOURS`` 冷却。参考宿主订阅搜索的冷却口径。
        """
        state = _clean_text(entry.get("state"))
        if state in ("downloaded", "in_library", "history"):
            return False
        stamp = parse_stamp(entry.get("time"))
        if stamp is None:
            return True
        age_hours = (datetime.now() - stamp).total_seconds() / 3600.0
        if state == "noresult":
            return age_hours >= _SUB_SEARCH_NORESULT_RETRY_HOURS
        return age_hours >= _SUB_SEARCH_RETRY_HOURS

    def _downloaded_before(self, row: Dict[str, Any]) -> Tuple[bool, str]:
        """查宿主下载历史：这部剧是不是已经下载过（与系统去重同口径）。

        两级：先按**媒体身份**精确查（下载历史带 ``media_source``/``media_id`` 时最可靠，
        身份字段在历史里可能是复合 ``duanju:…`` 也可能是裸号，两种都试）；再按**标题
        包含**兜底（识别不出身份的资源落库后只剩标题 / 路径可比）。查不了（SDK 缺失 /
        查询异常）时放行 —— 宁可多查一轮搜索，不因查询故障把整条订阅停摆。
        """
        try:
            from app.sdk.queries import (
                DownloadHistoryFilter,
                QueryPageRequest,
                list_download_history,
            )
        except Exception:  # noqa: BLE001 - 宿主版本差异
            return False, ""
        title = _clean_text(row.get("title"))
        source = _clean_text(row.get("media_source"))
        mid = _clean_text(row.get("media_id"))

        def query(filters: Dict[str, Any]) -> List[Any]:
            page = list_download_history(
                filters=DownloadHistoryFilter(**filters),
                page=QueryPageRequest(page=1, count=10),
            )
            items = getattr(page, "items", None)
            return list(items) if items else []

        try:
            if source and mid:
                ids = [mid]
                kind, native = split_media_id(mid)
                if kind and native:
                    ids.append(native)
                for candidate in ids:
                    items = query({"media_source": source, "media_id": candidate})
                    if items:
                        return True, "下载历史已有本剧（按媒体身份）"
            if title:
                key = normalize_title(title)
                if key:
                    for item in query({"text": title}):
                        hay = normalize_title(
                            f"{_clean_text(getattr(item, 'title', None))} "
                            f"{_clean_text(getattr(item, 'path', None))}"
                        )
                        if key in hay:
                            return True, "下载历史已有同名记录"
        except Exception as err:  # noqa: BLE001 - 查询失败不阻断订阅
            logger.warning(f"{PLUGIN_NAME} 查询下载历史失败（按未下载处理）：{err}")
        return False, ""

    def _self_search_one(
        self,
        row: Dict[str, Any],
        sites: List[int],
        downloader: Optional[str],
        save_path: Optional[str],
    ) -> Dict[str, Any]:
        """对一部作品做一轮「全分类搜索 → 消歧 → 提交下载」。

        返回字典 ``{"state", "detail", "hash", "url", "title"}``：``state`` ∈
        ``downloaded`` / ``noresult`` / ``failed``；``url`` / ``title`` 是**命中种子**
        的详情页与标题 —— 台账只记这两样（2026-10-22 用户口径），面板据此给一枚
        「种子页面」按钮 + 种子标题，够用且不占地方。翻页与节流参考宿主订阅搜索：
        逐页搜，页空即停，页与页之间歇 :data:`_SUB_SEARCH_PAGE_SLEEP` 秒。
        """

        def result(
            state: str,
            detail: str,
            digest: str = "",
            url: str = "",
            torrent_title: str = "",
        ) -> Dict[str, Any]:
            return {
                "state": state,
                "detail": detail,
                "hash": digest,
                "url": url,
                "title": torrent_title,
            }

        title = _clean_text(row.get("title"))
        title_key = normalize_title(title)
        try:
            from app.chain.download import DownloadChain
            from app.chain.search import SearchChain
        except Exception as err:  # noqa: BLE001 - 宿主版本差异
            return result("failed", f"宿主搜索 / 下载链不可用：{err}")

        contexts_all: List[Any] = []
        seen: set = set()
        try:
            for page in range(self._self_max_pages):
                contexts = (
                    SearchChain().search_by_title(
                        title=title,
                        page=page,
                        sites=sites or None,
                        # 关键：不传 mtype ⇒ 站点全分类一起搜（电影 + 电视剧 + 短剧 + 动漫），
                        # 分类被站点挂错的短剧（PTS 把短剧归电影）也能搜到。
                        mtype=None,
                    )
                    or []
                )
                fresh = 0
                for context in contexts:
                    torrent = getattr(context, "torrent_info", None)
                    marker = (
                        _clean_text(getattr(torrent, "page_url", None))
                        or _clean_text(getattr(torrent, "enclosure", None))
                        or _clean_text(getattr(torrent, "title", None))
                    )
                    if not marker or marker in seen:
                        continue
                    seen.add(marker)
                    contexts_all.append(context)
                    fresh += 1
                if not contexts or not fresh:
                    break
                if page + 1 < self._self_max_pages:
                    time.sleep(_SUB_SEARCH_PAGE_SLEEP)
        except Exception as err:  # noqa: BLE001 - 搜索失败只影响这一部
            return result("failed", f"搜索失败：{err}")

        matched: List[Tuple[Any, str]] = []
        for context in contexts_all:
            hit, why = match_work_context(context, row, title_key)
            if hit:
                matched.append((context, why))
        if not matched:
            return result(
                "noresult",
                f"全分类 {self._self_max_pages} 页无命中（共 {len(contexts_all)} 条）",
            )
        # 择优（2026-10-23 用户口径，配置页「优选条件」）：按做种数（默认）或按大小，
        # 大小方向（最大 / 最小）可配。不洗版 —— 短剧一条种子通常整季全带，选一条最好的就够。
        if self._subscribe_prefer.startswith("size"):
            sort_key = lambda pair: _to_float(  # noqa: E731 - 单行小谓词
                getattr(pair[0].torrent_info, "size", 0) or 0
            )
        else:
            sort_key = lambda pair: _to_int(  # noqa: E731 - 单行小谓词
                getattr(pair[0].torrent_info, "seeders", 0)
            )
        matched.sort(key=sort_key, reverse=self._subscribe_prefer != "size_asc")
        best, why = matched[0]
        torrent = getattr(best, "torrent_info", None)
        site_name = _clean_text(getattr(torrent, "site_name", None)) or "站点"
        seeders = _to_int(getattr(torrent, "seeders", 0))
        # ── 补全媒体三件套（真机实测的坑）：短剧大多不在 TMDB，搜索结果的
        # ``media_info`` 是 None ⇒ ``download_single`` 直接拒收「下载上下文缺少
        # 媒体、元数据或种子信息」。按**作品名**走 djbaike 源补一次识别（名字与
        # 百科 ID 一一对应），识别不出再放弃这一部。
        if getattr(best, "media_info", None) is None or getattr(best, "meta_info", None) is None:
            try:
                from app.chain.media import MediaChain
                from app.schemas.types import MediaSource as _MediaSourceEnum

                meta = getattr(best, "meta_info", None) or MetaInfo(
                    title=title,
                    subtitle=_clean_text(getattr(torrent, "description", None)),
                )
                media = MediaChain().recognize_media(
                    meta=meta,
                    media_source=_MediaSourceEnum(_BAIKE_SOURCE),
                )
                if media is not None:
                    best.media_info = media
                if getattr(best, "meta_info", None) is None:
                    best.meta_info = meta
                if getattr(best, "media_info", None) is None:
                    return result("failed", f"按作品名识别媒体失败（{title}）")
            except Exception as err:  # noqa: BLE001 - 识别失败只影响这一部
                return result("failed", f"补全媒体识别异常：{err}")
        try:
            # return_detail=True：失败时把下载链给的真实原因带回来记进台账，
            # 否则只留一句「未受理」，没法排查（真机实证：首轮 5 部全败在这）
            # ⚠️ 变量名**绝不能叫 result** —— 外面那个 result 是本函数的返回值
            # 构造闭包，这里一赋值就把它遮成 download_single 的返回 tuple，
            # 后续所有 ``return result(...)`` 都会炸「'tuple' object is not
            # callable」（2026-10-23 真机实证：《三生：渡厄》立即搜索即此因）。
            download_outcome = DownloadChain().download_single(
                best,
                downloader=downloader or None,
                save_path=save_path or None,
                username=PLUGIN_NAME,
                return_detail=True,
            )
        except Exception as err:  # noqa: BLE001 - 提交失败只影响这一部
            return result("failed", f"提交下载失败：{err}")
        if isinstance(download_outcome, tuple):
            download_hash, error_msg = download_outcome[0], download_outcome[1]
        else:
            download_hash, error_msg = download_outcome, ""
        if not download_hash:
            return result("failed", f"下载链未受理：{_clean_text(error_msg) or '原因未知'}")
        page_url = _clean_text(getattr(torrent, "page_url", None)) or _clean_text(
            getattr(torrent, "enclosure", None)
        )
        torrent_title = _clean_text(getattr(torrent, "title", None))
        # 「上次处理」只给人看三样：站点 / 种子名 / 做种数（2026-10-22 用户口径）；
        # 匹配理由只写日志，不占台账文案的位置。
        logger.info(
            f"{PLUGIN_NAME} 《{title}》命中 {site_name}：{torrent_title}（{why}，做种 {seeders}）"
        )
        return result(
            "downloaded",
            " · ".join(
                part
                for part in (
                    site_name,
                    torrent_title or title,
                    f"做种 {seeders}",
                )
                if part
            ),
            str(download_hash),
            page_url,
            torrent_title,
        )

    @staticmethod
    def _pacing_sleep(seconds: int, check_running: Optional[Any] = None) -> bool:
        """分片睡眠（1 秒一片），``check_running()`` 返回 False 时提前打断。

        返回 True = 睡满了 / 正常结束；False = 中途被叫停（插件停用），调用方
        应尽快收尾。全量搜索部与部之间的流控间隔靠它 —— 否则停用插件时要白等
        几百秒。
        """
        slept = 0.0
        while slept < seconds:
            if check_running is not None and not check_running():
                return False
            time.sleep(1)
            slept += 1
        return True

    def subscribe_search_task(self, trigger: str = "interval") -> bool:
        """自建订阅搜索任务：给**已订阅**的短剧作品补搜下载。

        自建器是独立的订阅系统（2026-10-22 用户口径）：订阅清单归插件自己管
        （:data:`_DATA_SUBS`，另兼容历史宿主 ``djbaike`` 订阅），不提交宿主订阅
        链；``subscribe_engine=self`` 时接管搜索这一步（全分类，绕开站点分类
        错位），下载 / 整理 / 通知仍走宿主链。断点在台账（:data:`_DATA_SUB_SEARCH`）
        里：终态跳过、失败 / 无结果按冷却重试，单轮预算用完即停，没轮到的下一轮继续。
        """
        if not self.get_state() or not self._actors:
            return False
        if self._subscribe_engine != "self":
            return False
        if not self._sub_lock.acquire(blocking=False):
            logger.info(f"{PLUGIN_NAME} 上一轮订阅搜索还在进行，本次跳过（{trigger}）")
            return False
        try:
            sites = [
                int(item)
                for item in str(self._subscribe_sites or "").split(",")
                if item.strip().isdigit()
            ]
            # 在库跳过**无条件**（2026-10-23 用户拍板：已入库的作品不会再执行下载
            # —— 不再挂在 auto_subscribe_skip_library 开关下，那是自动订阅的口径）
            probe = self.library_probe
            budget = self._self_max_per_run
            ledger = self._sub_ledger()
            ledger_dirty = False
            downloader = self._subscribe_downloader or None
            save_path = self._subscribe_save_path or None
            searched = downloaded = noresult = failed = skipped = 0
            # ── 候选范围：只搜「已订阅」的作品（2026-10-22 用户口径）──
            # 自建器是**订阅系统**，不是全库下载器：关注演员只决定作品墙，真正
            # 要搜要下的是墙里点过订阅的那部（宿主订阅表里 ``media_source=djbaike``
            # 的订阅 —— 卡片订阅 / 订阅全部 / 自动订阅三处都落到这）。已暂停（S）
            # 的订阅跳过：用户按了暂停就不该再自动下。
            wanted = self._subscribed_works()
            if not wanted:
                logger.info(f"{PLUGIN_NAME} 订阅搜索（{trigger}）：没有进行中的短剧订阅，本轮跳过")
                return True
            # 作品墙快照 → 订阅身份的行索引（拿演员署名与消歧旁证；没进快照的
            # 订阅（如取消关注后遗留）用订阅记录本身兜底拼行）
            snapshot = self._load_actors()
            rows_index: Dict[str, Tuple[Dict[str, Any], str]] = {}
            for key, record in snapshot.items():
                if not isinstance(record, dict):
                    continue
                actor = _clean_text(record.get("name")) or key
                for work in self._actor_works_cached(key, record):
                    if not isinstance(work, dict):
                        continue
                    row = work_row(work, actor, key)
                    mid = _clean_text(row.get("media_id"))
                    if mid in wanted and mid not in rows_index:
                        rows_index[mid] = (row, actor)
            for media_id, sub in wanted.items():
                if budget <= 0 or not self._running:
                    break
                found = rows_index.get(media_id)
                if found is not None:
                    row, actor = found
                else:
                    actor = _clean_text(sub.get("actor")) or "（订阅）"
                    row = {
                        "title": _clean_text(sub.get("name")),
                        "year": _clean_text(sub.get("year")),
                        "media_id": media_id,
                        "media_source": _BAIKE_SOURCE,
                        "type": "电视剧",
                    }
                title = _clean_text(row.get("title"))
                if not title:
                    continue
                entry = ledger.get(media_id)
                if isinstance(entry, dict) and not self._sub_entry_due(entry):
                    continue
                # 在库跳过（**无条件**，2026-10-23 用户拍板：已入库的作品不会再执行
                # 下载；探针查不了时按不在库处理，交给下载历史去重兜底）
                if probe.available and probe.lookup(row) is True:
                    ledger[media_id] = {
                        "time": datetime.now().strftime(_STAMP_FORMAT),
                        "state": "in_library",
                        "detail": "已在媒体库，跳过",
                        "title": title,
                        "year": _clean_text(row.get("year")),
                        "media_id": media_id,
                        "actor": actor,
                    }
                    ledger_dirty = True
                    skipped += 1
                    continue
                # 去重：下载历史里已有本剧（含手动搜到的 / 之前轮次提交的）
                done, why = self._downloaded_before(row)
                if done:
                    ledger[media_id] = {
                        "time": datetime.now().strftime(_STAMP_FORMAT),
                        "state": "history",
                        "detail": why,
                        "title": title,
                        "year": _clean_text(row.get("year")),
                        "media_id": media_id,
                        "actor": actor,
                    }
                    ledger_dirty = True
                    skipped += 1
                    continue
                # ── 搜索这一部（预算按真实搜索扣）──
                # 部与部之间的流控间隔：本轮已经真实搜过至少一部时，先随机歇
                # 60~300 秒再动站点（与宿主订阅搜索同口径，见 _SUB_SEARCH_WORK_INTERVAL；
                # 手动单部补搜不经过这里，不受影响）。插件停用时提前打断。
                if searched:
                    wait_s = random.randint(*_SUB_SEARCH_WORK_INTERVAL)
                    logger.info(
                        f"{PLUGIN_NAME} 订阅搜索（{trigger}）：为了避免连续访问站点，"
                        f"约 {wait_s} 秒后继续搜索《{title}》"
                    )
                    if not self._pacing_sleep(wait_s, lambda: self._running):
                        logger.info(f"{PLUGIN_NAME} 订阅搜索（{trigger}）已停用，本轮到此为止")
                        break
                budget -= 1
                searched += 1
                # 落点逐部解析：订阅自己配了站点 / 下载器 / 目录就用它，否则配置页默认
                sub_targets = self._sub_targets(sub)
                outcome = self._self_search_one(
                    row, sub_targets[0] or sites, sub_targets[1] or downloader, sub_targets[2] or save_path
                )
                state, detail = outcome["state"], outcome["detail"]
                ledger[media_id] = {
                    "time": datetime.now().strftime(_STAMP_FORMAT),
                    "state": state,
                    "detail": detail,
                    "title": title,
                    "year": _clean_text(row.get("year")),
                    "media_id": media_id,
                    "actor": actor,
                    "hash": outcome["hash"],
                    # 台账只留「种子页面 + 种子标题」
                    "torrent_url": outcome["url"],
                    "torrent_title": outcome["title"],
                }
                ledger_dirty = True
                if state == "downloaded":
                    downloaded += 1
                    logger.info(f"{PLUGIN_NAME} 订阅搜索下载《{title}》（{detail}）")
                elif state == "noresult":
                    noresult += 1
                    logger.info(f"{PLUGIN_NAME} 订阅搜索无结果：《{title}》（{detail}）")
                else:
                    failed += 1
                    logger.warning(f"{PLUGIN_NAME} 订阅搜索失败：《{title}》（{detail}）")
            if ledger_dirty:
                self._save_sub_ledger(ledger)
            logger.info(
                f"{PLUGIN_NAME} 订阅搜索完成（{trigger}）：搜索 {searched} 部"
                + (f"，提交下载 {downloaded} 部" if downloaded else "")
                + (f"，无结果 {noresult} 部（冷却重试）" if noresult else "")
                + (f"，失败 {failed} 部（冷却重试）" if failed else "")
                + (f"，在库 / 已下载跳过 {skipped} 部" if skipped else "")
                + (f"，预算内未跑完，下轮继续" if budget <= 0 else "")
            )
            if self._notify and (downloaded or failed):
                lines = [f"本轮搜索 {searched} 部：提交下载 {downloaded}、无结果 {noresult}、失败 {failed}。"]
                shown = 0
                for item in ledger.values():
                    if shown >= 8:
                        lines.append("· ……")
                        break
                    if _clean_text(item.get("state")) == "downloaded":
                        lines.append(
                            f"· {_clean_text(item.get('actor'))}：{_clean_text(item.get('title'))}"
                            f"（{_clean_text(item.get('detail'))}）"
                        )
                        shown += 1
                try:
                    self.post_message(
                        mtype=_MessageType.Plugin,
                        title=f"【{PLUGIN_NAME}】订阅搜索",
                        text="\n".join(lines),
                    )
                except Exception as err:  # noqa: BLE001 - 通知失败不影响结果
                    logger.warning(f"{PLUGIN_NAME} 发送订阅搜索通知失败：{err}")
            return True
        except Exception as err:  # noqa: BLE001 - 兜底，避免定时任务挂掉
            logger.error(f"{PLUGIN_NAME} 订阅搜索异常：{err}")
            return False
        finally:
            self._sub_lock.release()

    def _add_subscribe(
        self, row: Dict[str, Any], message: bool = True
    ) -> Tuple[bool, str]:
        """订阅一部作品：记进**插件订阅清单**；返回 ``(是否成功, 说明)``。

        2026-10-23 用户口径：宿主订阅链路（``SubscribeChain`` 提交 / 宿主订阅表读取）
        整套去除 —— 订阅只落插件清单，由自建订阅搜索全分类补搜、命中即下。
        """
        title = _clean_text(row.get("title"))
        media_id = _clean_text(row.get("media_id"))
        kind, native = split_media_id(media_id)
        if not title or not native:
            return False, "标题或媒体身份为空"
        return self._plugin_subscribe(row, actor=_clean_text(row.get("actor")))

    def _auto_subscribe_round(
        self, snapshot: Dict[str, Any], keys: List[str]
    ) -> Tuple[int, int, int]:
        """把**本轮刷新过**的演员作品交给订阅链；返回 ``(成功, 库里已有跳过, 失败)``。

        只处理 ``keys``（本轮真刷新过的演员）：没刷新的演员作品没变，再跑一遍纯属重复。

        闸门（任一不满足就跳过）：

        1. ``auto_subscribe`` 开关关着 → 整轮不跑；
        2. 台账里已处理过（成功 / 跳过 / 失败都算）→ 不再重复提交；
        3. 范围：``new`` 只订**最近 :data:`_NEW_WINDOW_DAYS` 天内上映**的作品
           （与作品墙「新作品」同一口径 :func:`is_fresh_work`），``all`` 连历史作品一起；
        4. 已在媒体库 → 跳过并记台账（订阅只为拿到没有的片子）；
        5.         单轮上限：预算耗尽就停，**没轮到的直接留到下一轮**（不记台账）。

        2026-10-22 引擎分流：``host`` 走宿主订阅链；``self`` 记进**插件订阅清单**
        （不进宿主订阅系统），由订阅搜索任务接手 —— 同一部剧只有一条路，不重复下载。
        """
        if not self._auto_subscribe or not keys:
            return 0, 0, 0
        ledger = self._auto_subscribe_ledger()
        budget = self._auto_subscribe_max_per_run
        probe = self.library_probe if self._auto_subscribe_skip_library else None
        now = time.time()
        subscribed = skipped = failed = 0
        for key in keys:
            if budget <= 0 or not self._running:
                break
            record = snapshot.get(key)
            if not isinstance(record, dict):
                continue
            works = self._actor_works_cached(key, record)
            if not works:
                continue
            actor = _clean_text(record.get("name")) or key
            mapping = record.get("first_seen")
            mapping = mapping if isinstance(mapping, dict) else {}
            for work in works:
                if budget <= 0 or not self._running:
                    break
                if not isinstance(work, dict):
                    continue
                row = work_row(work, actor, key)
                media_id = _clean_text(row.get("media_id"))
                if not media_id or media_id in ledger:
                    continue
                row["first_seen"] = _clean_text(mapping.get(work_identity(work)))
                if self._auto_subscribe_scope == "new" and not is_fresh_work(row, now):
                    continue
                if probe is not None and probe.lookup(row) is True:
                    skipped += 1
                    ledger[media_id] = {
                        "time": datetime.now().strftime(_STAMP_FORMAT),
                        "title": _clean_text(row.get("title")),
                        "year": _clean_text(row.get("year")),
                        "media_id": media_id,
                        "actor": actor,
                        "ok": True,
                        "detail": _AUTO_SKIP_DETAIL,
                    }
                    continue
                ok, detail = self._add_subscribe(row)
                budget -= 1
                ledger[media_id] = {
                    "time": datetime.now().strftime(_STAMP_FORMAT),
                    "title": _clean_text(row.get("title")),
                    "year": _clean_text(row.get("year")),
                    "media_id": media_id,
                    "actor": actor,
                    "ok": ok,
                    "detail": detail,
                }
                title = _clean_text(row.get("title"))
                if ok:
                    subscribed += 1
                    logger.info(f"{PLUGIN_NAME} 自动订阅成功：《{title}》（{detail}）")
                else:
                    failed += 1
                    logger.warning(f"{PLUGIN_NAME} 自动订阅失败：《{title}》（{detail}）")
        if subscribed or skipped or failed:
            self._save_auto_subscribe_ledger(ledger)
        return subscribed, skipped, failed

    # ── 任务 ──

    def refresh_works_task(self, trigger: str = "interval") -> bool:
        """定时发现任务：刷新演员作品快照，新作品发一条汇总通知。

        本插件自身**不下载、不整理**；订阅只做一件事：配置里打开「自动订阅」时，
        把本轮刷新到的作品按闸门交给宿主订阅链（:meth:`_auto_subscribe_round`），
        后续搜索 / 下载 / 整理照旧全部由宿主订阅系统接管。
        """
        if not self.get_state() or not self._actors:
            return False
        if not self._lock.acquire(blocking=False):
            logger.info(f"{PLUGIN_NAME} 上一轮刷新还在进行，本次跳过（{trigger}）")
            return False
        try:
            before = self._load_actors()
            self._refresh_actors()
            fresh = self._collect_fresh(before)
            self._notify_fresh(fresh)
            _, summary = self._work_rows(with_probe=False)
            auto_ok, auto_skipped, auto_failed = self._last_auto_subscribe
            logger.info(
                f"{PLUGIN_NAME} 作品发现完成（{trigger}）：{len(self._actors)} 位演员、"
                f"{summary.get('total', 0)} 部作品"
                + (f"，新增 {len(fresh)} 部" if fresh else "")
                + (f"，自动订阅 {auto_ok} 部" if auto_ok else "")
                + (f"，库里已有跳过 {auto_skipped} 部" if auto_skipped else "")
                + (f"，自动订阅失败 {auto_failed} 部" if auto_failed else "")
            )
            return True
        except Exception as err:  # noqa: BLE001 - 兜底，避免定时任务挂掉
            logger.error(f"{PLUGIN_NAME} 作品发现异常：{err}")
            return False
        finally:
            self._lock.release()

    def retry_failed_actors(self, trigger: str = "interval") -> bool:
        """失败重试任务：只重解析「到期的失败演员」。

        与完整刷新分开，是因为两者时间尺度不同：快照一天刷一次，而失败的演员
        20 分钟后就该再试一次（百科插件一恢复就能自己好，不必等满一天）。
        """
        if not self.get_state() or not self._actors:
            return False
        cached = self._load_actors()
        due = [
            key for key in self._due_actor_keys(cached) if is_retry_candidate(cached.get(key))
        ]
        if not due:
            return False
        if not self._lock.acquire(blocking=False):
            return False
        try:
            before = {
                key: _clean_text((cached.get(key) or {}).get("state"))
                for key in self._actors
                if isinstance(cached.get(key), dict)
            }
            before_snapshot = dict(cached)
            self._refresh_actors(only=due)
            after = self._load_actors()
            recovered = [
                key
                for key, state in before.items()
                if state == "waiting"
                and _clean_text((after.get(key) or {}).get("state")) != "waiting"
            ]
            fresh = self._collect_fresh(before_snapshot)
            self._notify_fresh(fresh)
            logger.info(
                f"{PLUGIN_NAME} 解析失败重试完成（{trigger}）：重试 {len(due)} 位"
                + (f"，已恢复 {len(recovered)} 位：{'、'.join(recovered)}" if recovered else "")
            )
            return True
        except Exception as err:  # noqa: BLE001 - 兜底
            logger.error(f"{PLUGIN_NAME} 失败重试异常：{err}")
            return False
        finally:
            self._lock.release()

    # ── 工具 ──

    def _load_actors(self) -> Dict[str, Any]:
        """加载演员快照；没有数据时返回空字典（首次运行）。

        读入时就地做结构迁移（:func:`migrate_record`）：v4 及更早的记录补上
        ``first_seen`` 映射、保留原 ``schema``，于是下一轮由版本门（``schema < 5``）
        重抓一次，把作品补进快照；v5 起记录原样返回 —— 作品随快照落盘
        （:data:`_SNAPSHOT_WORK_KEYS`），作品墙读它、不再逐演员打数据源。
        """
        data = self.get_data(_DATA_ACTORS)
        if not isinstance(data, dict):
            return {}
        return {
            key: migrate_record(record) if isinstance(record, dict) else record
            for key, record in data.items()
        }

    def _rekey_actors(self) -> bool:
        """把关注名单 / 快照主键从「名字」归位成「演员 ID」（返回是否有变化）。

        2026-10-20 起演员身份统一收敛到 ID（用户口径：ID 是唯一的，名字不参与匹配）。
        老数据里配置存的是名字、快照键也是名字 —— 记录里已经解析到 ``baike_id``
        的直接换键，配置里的名字同步替换；还没解析到 ID 的（数据源未装 / 未收录 /
        刚手输名字加进来的）保持名字键，等发现任务拿到 ID 后再归位。

        快照换键整段进临界区（与发现任务的增量落盘互斥）；配置变化也在这里一起
        回写 —— ``update_config`` 只保存不重入，实例属性就地更新即可。
        """
        snapshot = self._load_actors()
        renamed: Dict[str, str] = {}  # 旧键（名字）→ 新键（ID）
        taken: set = set()  # 已占用的新键（配置里已有的 ID / 本轮已归位的）
        next_actors: List[str] = []
        changed = False
        for key in self._actors:
            actor_id = _actor_id_of(key)
            if actor_id:
                taken.add(actor_id)
                next_actors.append(actor_id)
                continue
            record = snapshot.get(key)
            new_key = _actor_id_of(record.get("baike_id")) if isinstance(record, dict) else ""
            if new_key and new_key not in taken:
                renamed[key] = new_key
                taken.add(new_key)
                next_actors.append(new_key)
                changed = True
            else:
                next_actors.append(key)
        if not renamed:
            return False
        with self._snapshot_lock:
            snapshot = dict(self._load_actors())
            for old, new in renamed.items():
                record = snapshot.pop(old, None)
                if isinstance(record, dict):
                    record["key"] = new
                    snapshot[new] = record
            self.save_data(_DATA_ACTORS, snapshot)
        self._actors = next_actors
        self.update_config(self._live_config())
        for old, new in renamed.items():
            logger.info(f"{PLUGIN_NAME} 关注身份已归位为 ID：{old} → {new}")
        return True

    def _add_once_job(
        self,
        delay_seconds: float = 3,
        trigger: str = "once",
        func: Optional[Any] = None,
        job_id: str = _ONCE_JOB_ID,
    ) -> bool:
        """向宿主调度器登记一次性任务（立即刷新一次）。

        ⚠️ 关键字是 ``func_kwargs``（不是 ``kwargs``），传错会被内部 try/except 吞掉，
        只留一条错误日志，表现为「手动运行没反应」。
        """
        try:
            from app.sdk import scheduler as scheduler_sdk

            add_once = getattr(scheduler_sdk, "add_plugin_once_job", None)
            if not add_once:
                logger.warning(f"{PLUGIN_NAME} 当前宿主不支持一次性任务接口")
                return False
            add_once(
                self.__class__.__name__,
                job_id,
                func or self.refresh_works_task,
                f"{PLUGIN_NAME}执行",
                delay_seconds=delay_seconds,
                func_kwargs={"trigger": trigger},
            )
            return True
        except Exception as err:  # pragma: no cover - 宿主版本差异兜底
            logger.warning(f"{PLUGIN_NAME} 登记一次性任务失败：{err}")
            return False
