"""短剧演员订阅 · 插件 HTTP 接口的**响应模型**（V3 API 专题合同）。

为什么单独一层
--------------
官方 ``docs/V3_API_Response_Adaptation.md`` 的两条硬要求：

1. §3.1「不要只写 ``dict``、``list[dict]`` 或 ``Any`` 作为长期输出模型。每个端点的完整
   响应结构都应在 ``/docs`` 的 OpenAPI 中可查」⇒ 每个 endpoint 都要声明与真实输出一致
   的 ``response_model``；
2. §1「选择 envelope 的插件不要增加额外顶层字段，业务对象应放在 ``data`` 中」⇒ 本插件统一
   走宿主标准 envelope :class:`app.schemas.Response`，**业务对象一律在 ``data`` 里**。

于是本模块做两件事：

* 为 13 个端点各定义**业务数据模型**（``*Data``），字段与 ``_work_rows`` / ``_actor_row`` /
  ``baike_work_to_candidate`` / 详情投影的真实产出逐字对齐；
* 用 ``schemas.Response[Data]`` 造出路由要声明的 ``response_model``（``*Response``）。

两条刻意的设计取舍
------------------
* **投影类模型 ``extra="allow"``**（:class:`WorkRow` / :class:`ActorCandidateRow`）：作品卡
  由百科页面解析器决定字段，数据源版本升级随时会多出新键。宿主按 ``response_model`` 序列化时
  会**丢掉未声明的字段** —— 那等于悄悄吃掉数据，所以这两类显式放行未知键；结构类模型
  （envelope、统计、配置）保持严格。
* **数值叶子用宽联合**（``str | int | float``）：站点字段类型不稳定（评分给字符串、播放量给
  浮点），声明单一类型会在个别作品上抛校验错误把接口打成 500。``Any`` 不用（文档明确不推荐）。
"""
from __future__ import annotations

from typing import List, Optional, Union

from pydantic import BaseModel, ConfigDict

from app import schemas

__all__ = [
    "ActorCandidateRow",
    "ActorCardRow",
    "ActorCardsData",
    "ActorCardsResponse",
    "ActorDetailData",
    "ActorDetailResponse",
    "ActorFilterRow",
    "ActorMutationData",
    "ActorMutationResponse",
    "ActorRow",
    "ActorSearchData",
    "ActorSearchResponse",
    "ActorWorksData",
    "ActorWorksResponse",
    "ActorSubscribeAllData",
    "ActorSubscribeAllResponse",
    "ActorsData",
    "ActorsResponse",
    "AutoSubscribeRow",
    "ConfigData",
    "ConfigResponse",
    "FacetRow",
    "FacetsData",
    "RefreshData",
    "RefreshResponse",
    "RandomSubscribeData",
    "RandomSubscribeResponse",
    "LogsData",
    "LogsResponse",
    "RankMediaRow",
    "RankRow",
    "RanksData",
    "RanksResponse",
    "RankWorksData",
    "RankWorksResponse",
    "StatusData",
    "StatusResponse",
    "WorkDetailActorRow",
    "WorkDetailData",
    "WorkDetailResponse",
    "WorkRow",
    "WorkSearchData",
    "WorkSearchResponse",
    "WorkSearchRow",
    "WorksData",
    "WorksResponse",
    "WorksSummaryData",
]

#: 数值叶子：站点给字符串 / 整数 / 浮点都算合法（见模块头「设计取舍」）
Num = Union[str, int, float]


class ConfigData(BaseModel):
    """插件配置（``GET/PUT /config`` 的 ``data``），键与 ``_default_config()`` 一一对应。"""

    enabled: bool = False
    onlyonce: bool = False
    actors: str = ""
    interval_hours: int = 12
    retry_minutes: int = 20
    notify: bool = True
    sidebar_nav: bool = True
    search_sites: str = ""
    subscribe_mode: str = "follow"
    subscribe_prefer: str = "seeders"
    subscribe_downloader: str = ""
    #: 订阅站点（逗号分隔的站点 ID；空 = 跟随宿主订阅默认）
    subscribe_sites: str = ""
    #: 订阅下载目录（宿主 `/download/paths` 的 save_path；空 = 跟随宿主订阅默认）
    subscribe_save_path: str = ""
    #: 自动订阅：关注演员的作品直接交给宿主订阅链
    auto_subscribe: bool = False
    #: ``new`` = 只订演员加入之后新出现的作品（默认）/ ``all`` = 连历史作品一起
    auto_subscribe_scope: str = "new"
    #: 单轮最多提交几部（1..50）
    auto_subscribe_max_per_run: int = 5
    #: 已在媒体库的作品是否跳过
    auto_subscribe_skip_library: bool = True
    #: 订阅引擎：`host` = 宿主订阅链（默认）/ `self` = 插件自建订阅搜索（全分类补搜）
    subscribe_engine: str = "host"
    #: 自建订阅搜索的运行间隔（小时）
    self_interval_hours: int = 6
    #: 自建订阅搜索单轮最多搜索几部（1..30）
    self_max_per_run: int = 5
    #: 自建订阅搜索每部最多翻几页（1..10）
    self_max_pages: int = 3


class ActorFilterRow(BaseModel):
    """演员筛选行（``/works`` 的 ``actor_filters``）：只带筛选项需要的四项。"""

    key: str = ""
    name: str = ""
    works: int = 0
    state: str = ""


class ActorRow(BaseModel):
    """演员行（``/actors`` 与 ``/status`` 的 ``states``）：含百科 ID 与解析状态。"""

    key: str = ""
    name: str = ""
    baike_id: str = ""
    works: int = 0
    state: str = ""
    time: str = ""
    errors: List[str] = []


class AutoSubscribeRow(BaseModel):
    """一条自动订阅记录（``/status`` 的 ``auto_subscribe_recent``）。

    台账里存的是「尝试过什么」，所以 ``ok=False`` 的记录也在（失败原因在 ``detail``）；
    ``detail`` 为「已在媒体库，跳过」的那条不算订阅成功。
    """

    time: str = ""
    title: str = ""
    year: str = ""
    media_id: str = ""
    actor: str = ""
    ok: bool = False
    detail: str = ""


class SubscriptionRow(BaseModel):
    """一条订阅（作品墙左侧「订阅作品」面板的行，``GET /subscriptions``）。

    ``sub_state/sub_detail/sub_time`` 是订阅搜索的处理状态（引擎 = ``self`` 才有
    搜索行为；空 = 还没轮到 / 引擎是宿主）。
    """

    media_id: str = ""
    title: str = ""
    year: str = ""
    actor: str = ""
    #: 海报（订阅面板用作品墙同款海报卡展示）
    poster: str = ""
    #: 在库三态（探针现查）：True 已入库 / False 未入库 / None 未知（探针不可用）
    in_library: Optional[bool] = None
    sub_state: str = ""
    sub_detail: str = ""
    sub_time: str = ""
    #: 台账里记下的**种子页面**与**种子标题**（下载成功才有；详情页给按钮 + 标题）
    torrent_url: str = ""
    torrent_title: str = ""
    #: 订阅级落点覆写（空串 = 用配置页默认）：站点 id 逗号串 / 下载器名 / 保存目录
    sites: str = ""
    downloader: str = ""
    save_path: str = ""


class SubscriptionsData(BaseModel):
    """订阅清单（``GET /subscriptions``）。"""

    #: 当前订阅引擎（self = 自建订阅搜索；host = 宿主订阅链）
    engine: str = "self"
    items: List[SubscriptionRow] = []
    #: 配置页里的默认落点（订阅设置里「留空即用默认」提示这几项）
    default_sites: str = ""
    default_downloader: str = ""
    default_save_path: str = ""


class RandomSubscribeWork(BaseModel):
    """随机订阅命中的那一部（``POST /subscribe/random``）。"""

    media_id: str = ""
    title: str = ""
    year: str = ""
    actor: str = ""
    poster: str = ""


class RandomSubscribeData(BaseModel):
    """随机订阅结果：``requested`` 要几部 / ``items`` 实际订上的（候选不足就少订）。"""

    requested: int = 0
    items: List[RandomSubscribeWork] = []


RandomSubscribeResponse = schemas.Response[RandomSubscribeData]


class StatusData(BaseModel):
    """插件状态总览（``GET /status``）。"""

    enabled: bool = False
    configured: bool = False
    actors: int = 0
    works: int = 0
    new_works: int = 0
    last_refresh: str = ""
    new_window_days: int = 7
    states: List[ActorRow] = []
    #: 自动订阅是否打开（关着时下面三个字段仍返回，方便面板说明「有多少条历史」）
    auto_subscribe: bool = False
    #: 累计自动订阅成功的部数（不含「已在媒体库」那类跳过）
    auto_subscribed: int = 0
    #: 最近几条自动订阅记录（新的在前，最多 5 条）
    auto_subscribe_recent: List[AutoSubscribeRow] = []
    #: 自建订阅搜索引擎（host / self；host 时下面五个计数恒为 0）
    sub_engine: str = "host"
    #: 已提交下载
    sub_downloaded: int = 0
    #: 无结果（冷却中，会自动重试）
    sub_noresult: int = 0
    #: 失败（冷却中，会自动重试）
    sub_failed: int = 0
    #: 在库 / 下载历史已有而跳过
    sub_skipped: int = 0
    #: 还没轮到（全部作品 - 已进台账）
    sub_pending: int = 0


class WorkRow(BaseModel):
    """作品墙上的一行（``/works``、``/actors/works`` 的 ``works[]``）。

    ``extra="allow"``：数据源版本升级会往作品卡里加字段，投影时不能把它们吃掉。
    """

    model_config = ConfigDict(extra="allow")

    key: str = ""
    title: str = ""
    year: str = ""
    type: str = ""
    source: str = ""
    media_source: str = ""
    media_id: str = ""
    poster: str = ""
    vote: Num = 0
    episode_count: Num = 0
    url: str = ""
    genres: List[str] = []
    heat: Num = 0
    play_count: Num = 0
    studio: str = ""
    #: 播放平台（「在哪播」，如 红果短剧 / 河马剧场）。数据源从站点 meta 文案
    #: ``在<平台>平台上`` 抠出来；站点没印就是空串（不显示该筛选项）
    platform: str = ""
    kind: str = ""
    release_date: str = ""
    actor: str = ""
    actor_key: str = ""
    first_seen: str = ""
    is_new: bool = False
    #: 三态：True 在库 / False 不在库 / None 未知（查库失败或未查）
    in_library: Optional[bool] = None
    overview: str = ""
    #: 自建订阅搜索台账：处理状态 / 说明 / 时间 / 种子页面 / 种子标题
    sub_state: str = ""
    sub_detail: str = ""
    sub_time: str = ""
    sub_url: str = ""
    sub_torrent: str = ""


class WorkDetailActorRow(BaseModel):
    """作品详情里的演员行（``GET /works/detail`` 的 ``actors[]``）。

    数据来自短剧百科作品页的「演员阵容」区块：``character`` 是角色名，``kind`` 是站点标的
    「主演 / 配角」。``extra="allow"``：站点的演员区块随时会多出新键（国籍 / 身高…）。
    """

    model_config = ConfigDict(extra="allow")

    actor_id: str = ""
    name: str = ""
    #: 饰演角色（站点没录入时为空）
    character: str = ""
    #: 头像（站点 CDN 绝对地址，前端统一走宿主 system/img 代理）
    profile: str = ""
    #: 主演 / 配角（站点角标）
    kind: str = ""
    #: 百科演员页地址（由作品页域名推出，推不出来时为空）
    url: str = ""
    #: 是否已在本插件的关注列表里（详情页据此显示「已关注 / 关注」）
    subscribed: bool = False


class WorkDetailData(BaseModel):
    """一部作品的详情（``GET /works/detail``）—— 面板**自绘详情页**的数据源。

    为什么有这个端点：宿主自带的媒体详情页里，右侧信息面板 / 演职员 / 推荐 / 分季
    **全部以 ``tmdb_id`` 为前提**（``MoviePilot-Frontend`` 的 ``MediaDetailView.vue``），
    而短剧大多不在 TMDB 上 ⇒ 那些区块整块不渲染；播放量 / 收藏 / 热度 / 真人·AI 角标
    这些站点字段宿主模型里也压根没有。本端点把这些一起给全。

    TMDB 身份（``tmdb_id`` / ``tmdb_url``）**照实透出**：百科插件严格匹配到 TMDB 条目时
    才非空（实测「夏星望野」= 百科 30409 / TMDB 326627），详情页据此补「TMDB ID」行与
    来源区的 TheMovieDb chip —— 与系统那一页同款，只是不把 TMDB 的演职员 / 推荐 / 分季
    搬过来（那些是 TMDB 自己的条目，点开也回不到本插件的数据面）。

    字段分两拨：
    * **百科详情页侧**（``overview`` / ``genres`` / ``studio`` / 单集·全集时长 / 演员表…）——
      由 ``run_module("recognize_media")`` 返回的宿主 ``MediaInfo`` 投影而来；
    * **墙上快照侧**（``heat`` / ``play_count`` / ``kind`` / ``first_seen`` / ``is_new`` /
      ``in_library``）—— 作品卡解析才有、``MediaInfo`` 里没有的字段，按 ``media_id``
      从本地快照那一行补齐（三个入口点开同一部剧，详情页信息因此一致）。
    """

    model_config = ConfigDict(extra="allow")

    #: 百科里是否有这部剧（未命中 = ``success=true`` + ``found=false``，不是接口失败）
    found: bool = False
    media_source: str = ""
    media_id: str = ""
    title: str = ""
    year: str = ""
    type: str = ""
    overview: str = ""
    poster: str = ""
    #: 剧照首图，详情页顶栏大图用（没有则退回海报）
    backdrop: str = ""
    vote: Num = 0
    release_date: str = ""
    episode_count: Num = 0
    #: 单集时长（分钟；站点只印全集总时长，这里按集数折算）
    episode_minutes: Num = 0
    #: 全集时长（分钟；= 单集 × 集数，折算值）
    duration_minutes: Num = 0
    genres: List[str] = []
    #: 出品方 / 版权方
    studio: str = ""
    #: 播放平台（「在哪播」）。宿主 ``MediaInfo`` 里是 ``networks=[{"name": …}]``，
    #: 详情投影收敛成一个字符串；站点没印就是空串
    platform: str = ""
    status: str = ""
    #: 原语言（``zh`` / ``zh-Hans`` 等，站点 JSON-LD 的 ``inLanguage``）
    language: str = ""
    #: 百科作品页地址（详情页的「百科页」按钮）
    url: str = ""
    #: 百科严格匹配到的 TMDB 条目 ID（0 = 没有 TMDB 身份；详情页据此显示「TMDB ID」行）
    tmdb_id: int = 0
    #: TMDB 条目地址（有 ``tmdb_id`` 才有；详情页来源区的 TheMovieDb chip 用它）
    tmdb_url: str = ""
    #: 豆瓣条目 ID / 地址（数据源匹配到的）。有它前端才去宿主的 ``/api/v1/douban/*``
    #: 取豆瓣详情、短评与影评 —— 系统详情页那几块也是靠 douban_id 才有内容
    douban_id: str = ""
    douban_url: str = ""
    actors: List[WorkDetailActorRow] = []
    # ── 墙上快照侧的字段（MediaInfo 里没有） ──
    # 热度 / 播放量 / 收藏**不在这里**：数据源给的是站点原文（「380.14万」），
    # 由前端从 ``/lookup`` 原样显示（2026-10-23 用户口径：不要折算数值）
    #: 真人短剧 / AI 短剧（站点角标）
    kind: str = ""
    #: 这部作品在本插件里首次被发现的时间
    first_seen: str = ""
    is_new: bool = False
    #: 三态：True 在库 / False 不在库 / None 未知（查库失败），判定与作品墙同一套探针
    in_library: Optional[bool] = None


class FacetRow(BaseModel):
    """一个筛选项（类型 / 年份 / 版权方 / 播放平台）及其作品数。"""

    value: str = ""
    count: int = 0


class FacetsData(BaseModel):
    """筛选项集合（基于筛选前的全集计算，不随勾选跳动）。

    ``platforms``（播放平台）与 ``studios``（出品方）同源同理：**数据源给了才有**，
    一项数据都没有时是空数组，前端据此整栏隐藏 —— 不显示一堆空选项。
    """

    genres: List[FacetRow] = []
    years: List[FacetRow] = []
    studios: List[FacetRow] = []
    platforms: List[FacetRow] = []


class WorksSummaryData(BaseModel):
    """作品墙的统计口径（全集，不受当前筛选影响）。"""

    total: int = 0
    new: int = 0
    #: 在库状态**查成了**的作品数；0 表示本次请求没有全集判定结论
    #: （页模式只判展示页，全集统计只报探针缓存里已有的）——
    #: 前端据此隐藏「已入库 X 部」统计行
    library_known: int = 0
    in_library: int = 0
    #: 判定通道可用（宿主库表查得动）——「只看未入库」开关的展示依据，
    #: 页模式下不再依赖 library_known（那需要全量判定才有数）
    probe_available: bool = False
    #: 本次请求是否做过全量判定（「只看未入库」开启时为 True）
    probe_full: bool = False


class WorksData(BaseModel):
    """作品墙一页（``GET /works``）。"""

    total: int = 0
    page: int = 1
    page_size: int = 0
    has_more: bool = False
    sort: str = "heat"
    new_window_days: int = 7
    works: List[WorkRow] = []
    actor_filters: List[ActorFilterRow] = []
    facets: FacetsData = FacetsData()
    summary: WorksSummaryData = WorksSummaryData()


class ActorsData(BaseModel):
    """演员列表（``GET /actors``）。"""

    actors: List[ActorRow] = []


class ActorCandidateRow(BaseModel):
    """百科演员候选（``POST /actors/search`` 的 ``candidates[]``）。

    ``extra="allow"``：``enrich=True`` 时会补上头像 / 作品数 / 简介 / 性别 / 国籍等字段，
    补档案的字段集合随百科解析器演进，不能在这里被吃掉。
    """

    model_config = ConfigDict(extra="allow")

    name: str = ""
    actor_id: str = ""
    media_id: str = ""
    url: str = ""
    #: 与输入名字归一化后完全相等（前端据此决定「可直接采纳」还是「让用户挑」）
    exact: bool = False
    subscribed: bool = False
    profile: str = ""
    works_count: int = 0
    bio: str = ""
    gender: str = ""
    nationality: str = ""
    job_title: str = ""
    #: 站点人物页的粉丝 / 获赞（卡片上展示；数据源没给就是 0）
    followers: int = 0
    likes: int = 0


class ActorSearchData(BaseModel):
    """百科查演员的结果（``POST /actors/search``）。"""

    name: str = ""
    candidates: List[ActorCandidateRow] = []


class ActorCardRow(BaseModel):
    """**已关注演员**的卡片行（``GET /actors/cards``）—— 面板「已关注的演员」区块用。

    字段与 :class:`ActorCandidateRow` 刻意保持同构：前端两处（搜索结果 / 已关注列表）
    用**同一个卡片组件**渲染，视觉与交互因此完全一致。多出来的 ``state`` 是本地解析
    状态（'' 正常 / 'waiting' 临时失败 / 'empty' 百科未收录），只在卡片上做提示用。
    """

    model_config = ConfigDict(extra="allow")

    name: str = ""
    actor_id: str = ""
    media_id: str = ""
    url: str = ""
    exact: bool = True
    subscribed: bool = True
    profile: str = ""
    works_count: int = 0
    bio: str = ""
    gender: str = ""
    nationality: str = ""
    job_title: str = ""
    #: 站点人物页的粉丝 / 获赞（卡片上展示；数据源没给就是 0）
    followers: int = 0
    likes: int = 0
    #: '' 正常 / 'waiting' 临时失败（会自动重试）/ 'empty' 百科未收录
    state: str = ""


class ActorCardsData(BaseModel):
    """已关注演员列表（``GET /actors/cards``）。"""

    actors: List[ActorCardRow] = []


class PeopleRow(BaseModel):
    """人物目录的一行（``GET /people`` 的 ``people[]``）。

    与 ``ActorCardRow`` 同构（前端用同一个卡片组件渲染），多一个 ``kind``
    区分这一行是演员 / 导演 / 编剧（数据源目录页是分开的三个列表）。
    """

    model_config = ConfigDict(extra="allow")

    name: str = ""
    #: 复合人物 ID（``yanyuan:<id>`` / ``daoyan:<id>`` / ``bianju:<id>``）
    actor_id: str = ""
    media_id: str = ""
    kind: str = ""
    url: str = ""
    profile: str = ""
    gender: str = ""
    job_title: str = ""
    works_count: int = 0
    subscribed: bool = False


class PeopleListData(BaseModel):
    """人物目录的一页（``GET /people``）。

    ``message`` 只在一个情况下非空：数据源还没提供 ``list_people`` 模块方法
    （或这次取数失败）—— 此时 ``people`` 为空、``has_more=false``，前端把
    ``message`` 显示出来，不把它当成错误。
    """

    kind: str = ""
    page: int = 1
    has_more: bool = False
    message: str = ""
    people: List[PeopleRow] = []


class WorkSearchRow(BaseModel):
    """百科按片名查作品的候选行（``POST /works/search`` 的 ``works[]``）。"""

    model_config = ConfigDict(extra="allow")

    media_source: str = ""
    media_id: str = ""
    title: str = ""
    year: str = ""
    poster: str = ""
    overview: str = ""
    vote: Num = 0


class WorkSearchData(BaseModel):
    """百科按片名查作品的结果（``POST /works/search``）。"""

    name: str = ""
    works: List[WorkSearchRow] = []


class ActorMutationData(BaseModel):
    """演员增删（``POST /actors/add``、``POST /actors/remove``）的结果。

    ``/actors/add`` 只给名字、而百科里没有**同名精确命中**时不算接口失败：返回
    ``need_pick=True`` + 候选列表，由前端让用户挑一位（文档 §3.3「未命中不等于接口失败，
    由 data 表达空结果」）。形状固定在这里，避免同一端点两种 data 结构。
    """

    actors: List[str] = []
    need_pick: bool = False
    candidates: List[ActorCandidateRow] = []


class ActorWorksData(BaseModel):
    """某位演员的全部作品（``GET /actors/works``，百科实时取，不落盘）。"""

    name: str = ""
    total: int = 0
    works: List[WorkRow] = []


class ActorSubscribeAllData(BaseModel):
    """一位演员「订阅全部作品」的结果（``POST /actors/subscribe_all``）。

    计数口径：

    * ``total``：这位演员的作品总数（去重后）；
    * ``submitted``：本次真正提交成功、进宿主订阅列表的部数；
    * ``skipped_library``：已在媒体库、按配置跳过（订阅只为拿到没有的片子）；
    * ``skipped_subscribed``：前端已知已订阅（``exclude_ids``）、本次直接跳过；
    * ``failed``：提交被宿主拒绝（原因在 ``details[].detail``）；
    * ``capped``：作品数超过单次上限 :data:`_SUBSCRIBE_ALL_LIMIT`，剩下的再点一次。
    """

    name: str = ""
    total: int = 0
    submitted: int = 0
    skipped_library: int = 0
    skipped_subscribed: int = 0
    failed: int = 0
    capped: bool = False
    #: 本次提交成功的作品 ``media_id``（前端据此把爱心点亮，不必等回查）
    media_ids: List[str] = []
    #: 逐部结果（成功 / 跳过 / 失败都记，顺序与作品顺序一致）
    details: List[AutoSubscribeRow] = []


class ActorDetailData(BaseModel):
    """一位演员的**详情**（``GET /actors/detail``）—— 面板自绘的演员作品页用。

    版式照宿主的演员详情页（``PersonDetailView.vue``）：头部一行是**圆形大头像 + 姓名 +
    一行副信息**，下面是简介，再下面是「参演作品」标题与作品卡网格。

    ⚠️ 字段分两拨，和宿主的模型对不上是正常的 —— 宿主演员详情页的「生日 | 出生地 /
    别名」它自己那几个源（TMDB / 豆瓣 / Bangumi / AniList）有，短剧百科**没有**；
    百科有而宿主模型没有的是 ``job_title`` / ``nationality`` / ``gender`` / 作品数。
    所以副信息行用「职业 | 国籍」，坐的是宿主「生日 | 出生地」那个位置。
    """

    model_config = ConfigDict(extra="allow")

    #: 百科里有没有这位演员（false 时前端出空态，**不算接口失败**）
    found: bool = False
    actor_id: str = ""
    media_id: str = ""
    name: str = ""
    profile: str = ""
    bio: str = ""
    job_title: str = ""
    gender: str = ""
    nationality: str = ""
    url: str = ""
    # ── 2026-10-18 补全：数据源 actor_profile 契约里一直有、本模型之前没投影的档案字段 ──
    #: 出生日期（``1996-05-20``；站点只给到年份时为空、看 ``birth_year``）
    birth_date: str = ""
    birth_year: str = ""
    #: 出生地 / 籍贯
    birth_place: str = ""
    #: 身高（cm）/ 体重（kg）；0 = 站点没给
    height_cm: int = 0
    weight_kg: int = 0
    #: 星座 / 毕业院校
    constellation: str = ""
    education: str = ""
    #: 爱好（列表；空列表 = 站点没给）
    hobbies: List[str] = []
    #: 站点原文里的「代表作」那一句
    rep_text: str = ""
    #: 「代表作」原文对回作品行的结果（按原文顺序，前端做成可点条目；
    #: 站点给的是**一整串无分隔剧名**，切分在后端按「最长标题匹配」做）
    rep_works: List["WorkRow"] = []
    #: 粉丝数 / 获赞数（站点人物页给的纯数字，0 = 没有）
    followers: int = 0
    likes: int = 0
    #: 百科侧的作品总数（``works_count``）
    works_count: int = 0
    #: **本页**实际返回的作品条数（= ``len(works)``）
    total: int = 0
    #: 这位演员的作品总数（分页前，前端据此算「已加载 N / 共 M」）
    works_total: int = 0
    #: 本次是哪一页 / 每页多少条
    works_page: int = 1
    works_page_size: int = 24
    #: 还有下一页（前端滚到底据此续拉）
    has_more: bool = False
    #: 其中明确已在媒体库的条数 / 查成了在库状态的条数（0 = 判定不可用，前端隐藏该行）
    in_library_count: int = 0
    library_known: int = 0
    #: 这位演员在不在本插件的关注列表里
    subscribed: bool = False
    works: List[WorkRow] = []


class RankRow(BaseModel):
    """榜单目录的一行（``GET /ranks`` 的 ``ranks[]``）。"""

    key: str = ""
    name: str = ""
    #: 该榜当前抓不抓得到带 media_id 的卡（False = 站点整页未收录详情，前端隐藏）
    has_detail: bool = True


class RanksData(BaseModel):
    """榜单目录（``GET /ranks``）。``message`` 非空 = 目录取不到时的说明。"""

    ranks: List[RankRow] = []
    message: str = ""


class RankMediaRow(BaseModel):
    """榜单卡行（``GET /ranks/works`` 的 ``medias[]``）。

    2026-10-23 用户口径：**不与 ``actor_works`` 卡形对齐**，按数据源实际页面
    取必要字段 —— ``media_id / title / badge / episodes / date /
    actors_text``；热度 / 评分 / 题材不要。``poster`` / ``url`` 由数据源按
    ``media_id`` 现推后附带。``extra="allow"``：字段随站点页面演进。
    """

    model_config = ConfigDict(extra="allow")

    media_id: str = ""
    title: str = ""
    badge: str = ""
    episodes: int = 0
    date: str = ""
    actors_text: str = ""
    poster: str = ""
    url: str = ""
    #: 在库判定（True 在库 / False 不在库 / None 未知）—— 卡片「入库」图标用
    in_library: Optional[bool] = None


class RankWorksData(BaseModel):
    """一个榜单的作品卡列表（``GET /ranks/works``）。

    ``medias`` 为数据源 ``rank_medias`` 的**原样卡行**（本插件不做归一、不套
    在库判定与订阅台账）；卡片样式由前端映射到与作品页同一张卡。
    """

    rank: str = ""
    name: str = ""
    #: 当前页码（从 1 起；只有「推荐」这类可翻页榜单会 > 1）
    page: int = 1
    #: 是否还有下一页（排行榜页恒 False —— 站点不分页）
    has_more: bool = False
    medias: List[RankMediaRow] = []
    #: 抓取失败 / 榜单空时的说明（空串 = 正常）
    message: str = ""


class LogsData(BaseModel):
    """插件最近日志（``GET /logs`` 的 ``items[]``：原始日志行，旧的在前）。"""

    items: List[str] = []


class RefreshData(BaseModel):
    """立即刷新的结果（``POST /refresh``）。"""

    total: int = 0
    new: int = 0


# ── 路由要声明的 response_model（参数化的宿主 envelope） ──
StatusResponse = schemas.Response[StatusData]
WorksResponse = schemas.Response[WorksData]
WorkDetailResponse = schemas.Response[WorkDetailData]
ActorsResponse = schemas.Response[ActorsData]
ActorSearchResponse = schemas.Response[ActorSearchData]
ActorCardsResponse = schemas.Response[ActorCardsData]
PeopleListResponse = schemas.Response[PeopleListData]
WorkSearchResponse = schemas.Response[WorkSearchData]
ActorMutationResponse = schemas.Response[ActorMutationData]
ActorWorksResponse = schemas.Response[ActorWorksData]
ActorSubscribeAllResponse = schemas.Response[ActorSubscribeAllData]
ActorDetailResponse = schemas.Response[ActorDetailData]
RefreshResponse = schemas.Response[RefreshData]
RanksResponse = schemas.Response[RanksData]
RankWorksResponse = schemas.Response[RankWorksData]
LogsResponse = schemas.Response[LogsData]
ConfigResponse = schemas.Response[ConfigData]
SubscriptionsResponse = schemas.Response[SubscriptionsData]
SubscribeResponse = schemas.Response[None]
