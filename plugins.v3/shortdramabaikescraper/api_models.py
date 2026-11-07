"""插件 API 的响应模型（显式声明 ``response_model``，官方 §9.2 / FAQ 03 硬要求）。

普通 JSON 端点统一显式返回 ``schemas.Response[...]``：宿主不会替插件包 envelope，
而插件面板与外部调用方都按 ``{success, message, data}`` 读取。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app import schemas
from app.schemas import MediaInfo


class ConfigData(BaseModel):
    """``/config``：插件配置（键与 ``get_form()`` 的字段一一对应）。

    Vue 配置页（联邦 `./Config`）只认这几个字段；宿主原生表单走 ``get_form()``。
    两者必须同源，否则「面板里改了、宿主表单里没变」这种分裂迟早出现。
    """

    enabled: bool = Field(default=False, description="是否启用插件")
    site: str = Field(
        default="net",
        description="主站：net（www.duanjubaike.net）/ org（duanjubaike.org）；"
        "只影响检索 / 人物目录 / 榜单，详情按 media_id 前缀自动路由",
    )
    use_baidu_image_proxy: bool = Field(
        default=True,
        description="是否保留使用百度图床代理（gimg 中转）；false = 直连站点自家图床。"
        "只对老站（.net）生效：新站（.org）的海报是页面自带的 CDN 绝对地址，与本开关无关",
    )
    exclude_manju: bool = Field(
        default=True,
        description="排除开关（按主站口径）：老站排「漫剧」、新站排 AI 剧；"
        "识别候选 / 面板检索 / 榜单 / 演员作品都生效",
    )


class StatusData(BaseModel):
    """``/status``：插件状态与 ``baike`` 表概览。"""

    enabled: bool = Field(default=False, description="插件是否启用")
    version: str = Field(default="", description="插件版本")
    media_source: str = Field(default="", description="媒体来源标识")
    site: str = Field(default="net", description="当前主站（net / org）")
    exclude_manju: bool = Field(True, description="排除开关是否打开（老站排漫剧 / 新站排 AI 剧）")
    total: int = Field(default=0, description="ID 库总条数")
    searchable: int = Field(default=0, description="可检索条数（name 非空）")
    by_entity: dict[str, int] = Field(default_factory=dict, description="按实体前缀计数")
    ext_total: int = Field(default=0, description="外部 id 表（baike_ext）条数")
    ext_douban: int = Field(default=0, description="外部 id 表里有豆瓣 id 的条数")
    ext_tmdb: int = Field(default=0, description="外部 id 表里有 TMDB id 的条数")
    regions: list[str] = Field(default_factory=list, description="缓存 region 清单")
    by_region: dict[str, int] = Field(
        default_factory=dict, description="各缓存 region 的当前条数（饼图统计用）"
    )


class OpResult(BaseModel):
    """破坏性/管理类操作的统一返回。"""

    ok: bool = Field(default=False, description="是否成功")
    detail: str = Field(default="", description="补充说明")
    affected: int = Field(default=0, description="影响条数")


class CacheItem(BaseModel):
    """缓存枚举的一行原始数据。

    ``parent`` 非空 = 这行是从一个**数组值**里展开出来的子条目（缓存里真正的
    键是 ``parent``，删除时要删它）；普通条目 ``parent`` 为空。
    """

    key: str = Field(default="", description="缓存键")
    value: Any = Field(default=None, description="缓存原始值")
    parent: str = Field(default="", description="数组条目的宿主缓存键（空 = 自身就是键）")
    label: str = Field(default="", description="面板显示名（榜单数组给「推荐（30 部）」这种）")


class CacheItemsData(BaseModel):
    """``/cache/items`` 返回。"""

    region: str = Field(default="", description="缓存 region")
    total: int = Field(default=0, description="本次返回条数")
    items: list[CacheItem] = Field(default_factory=list, description="键值对")


class BaikePageData(BaseModel):
    """``/baike/list`` 返回。"""

    total: int = Field(default=0, description="符合条件的总条数")
    offset: int = Field(default=0, description="偏移")
    limit: int = Field(default=50, description="每页条数")
    items: list[dict[str, Any]] = Field(default_factory=list, description="站点行（media_id / name 两列）")


class BaikeExtData(BaseModel):
    """``/baike/ext`` 返回：外部 id 表的一行（**主键就是名字**）。"""

    name: str = Field(default="", description="作品 / 人物名（外部 id 的键）")
    douban: str = Field(default="", description="豆瓣复合 id：作品 douban:{sid} / 影人 doubanp:{pid}")
    tmdb: str = Field(default="", description="TMDB 复合 id：作品 tmdb:{id} / 影人 tmdbp:{pid}")


class BaikeExtPageData(BaseModel):
    """``/baike/extlist`` 返回：外部 id 表分页（一行 = 名字 + 豆瓣 + TMDB）。

    ``source`` 为 ``douban`` / ``tmdb`` 时，``items`` 里只有该列非空的行
    （面板把外部 id 拆成「豆瓣 id」「TMDB id」两个分类）。
    """

    total: int = Field(default=0, description="符合条件的总条数")
    offset: int = Field(default=0, description="偏移")
    limit: int = Field(default=50, description="每页条数")
    items: list[BaikeExtData] = Field(default_factory=list, description="名字 + 豆瓣 + TMDB")


class PersonWork(BaseModel):
    """人物页的一张作品卡（比列表页多出演员表与标签两行）。"""

    media_id: str = Field(default="", description="作品 media_id")
    name: str = Field(default="", description="剧名")
    kind: str = Field(default="", description="短剧 / 漫剧")
    poster: str = Field(default="", description="海报地址（按 media_id 反推）")
    date: str = Field(default="", description="上线日期 YYYY-MM-DD")
    episodes: int = Field(default=0, description="总集数")
    actors: list[str] = Field(default_factory=list, description="完整演员表（不含角色名）")
    tags: list[str] = Field(default_factory=list, description="分类标签")
    origin: str = Field(
        default="baike",
        description="来源：baike=短剧百科 / douban=豆瓣独有（合并进来的）",
    )
    year: str = Field(default="", description="年份（豆瓣来源才有）")
    rating: float = Field(default=0.0, description="豆瓣评分（豆瓣来源才有）")


class PersonPeer(BaseModel):
    """人物页侧栏「XX合作的演员」里的一行（带站点身份）。

    ``.org`` 才有这块；``.net`` 人物页没有合作区块，列表就是空的。
    """

    media_id: str = Field(default="", description="合作演员 media_id（actor:{id}）")
    name: str = Field(default="", description="姓名")
    role: str = Field(default="", description="身份文案（站点没给就是空）")
    avatar: str = Field(default="", description="头像地址（站点头像，CDN 绝对地址）")


class PersonData(BaseModel):
    """``/person`` 返回：人物档案 + 作品清单 + 合作演员。

    人物**不是** ``MediaInfo``（那个结构描述的是"一部片"），所以单独一个模型，
    只给面板与外部插件看，不参与识别链路。
    """

    media_id: str = Field(default="", description="人物 media_id")
    name: str = Field(default="", description="姓名")
    role: str = Field(default="", description="身份文案：女演员 / 男演员 / 导演 / 编剧")
    kind: str = Field(default="", description="与 role 同值（展示用）")
    avatar: str = Field(default="", description="头像地址（按 media_id 反推）")
    intro: str = Field(default="", description="介绍正文（站点原文）")
    works: list[PersonWork] = Field(default_factory=list, description="作品清单")
    work_count: int = Field(default=0, description="作品条数")
    people: list[PersonPeer] = Field(
        default_factory=list,
        description="常合作的演员（.org 侧栏区块，最多 20 位；同批 id 一并入 ID 库）",
    )
    detail_url: str = Field(default="", description="站点人物页地址")
    douban_id: str = Field(
        default="",
        description="豆瓣影人 id（doubanp:{pid}，绑定成功才有）",
    )
    tmdb_id: str = Field(
        default="",
        description="TMDB 影人 id（tmdbp:{pid}，按作品交集绑定成功才有）",
    )
    douban_info: list[str] = Field(
        default_factory=list,
        description="豆瓣补充信息（性别 / 生日 / 出生地等，绑定成功才有）",
    )


class NovelWork(BaseModel):
    """原著档案里的一张改编作品卡（站点「改编拍摄的系列短剧」区块）。"""

    media_id: str = Field(default="", description="改编作品 media_id")
    name: str = Field(default="", description="剧名")
    kind: str = Field(default="", description="短剧 / 漫剧")
    poster: str = Field(default="", description="海报地址（按 media_id 反推）")
    date: str = Field(default="", description="上线日期 YYYY-MM-DD")
    episodes: int = Field(default=0, description="总集数")


class NovelData(BaseModel):
    """``/novel`` 返回：原著档案 + 改编作品清单。

    原著与人物一样**不是** ``MediaInfo``（原著是"一本书"），单独建模只给面板看。
    """

    media_id: str = Field(default="", description="原著 media_id")
    name: str = Field(default="", description="书名")
    kind: str = Field(default="原著", description="固定「原著」")
    author: str = Field(default="", description="作者")
    aka: str = Field(default="", description="又名（改编版剧名，站点标注才有）")
    words: str = Field(default="", description="字数（如 32.5 万字）")
    overview: str = Field(default="", description="剧情介绍")
    poster: str = Field(default="", description="封面地址（按 media_id 反推）")
    detail_url: str = Field(default="", description="站点原著页地址")
    adaptations: list[NovelWork] = Field(default_factory=list, description="改编作品清单")
    adaptation_count: int = Field(default=0, description="改编作品条数")
    novel_id_of: str = Field(
        default="", description="请求时传的剧 media_id（直接传原著时为空）"
    )


class BackfillData(BaseModel):
    """``/baike/extids`` 一轮批量回填的结果（可反复调用直到 ``remaining`` 归零）。"""

    entity: str = Field(default="", description="本次补的实体前缀（空 = 全库）")
    scanned: int = Field(default=0, description="本轮扫过的行数")
    douban: int = Field(default=0, description="本轮补上豆瓣 id 的条数")
    tmdb: int = Field(default=0, description="本轮补上 TMDB id 的条数")
    remaining: int = Field(default=0, description="库里仍缺外部 id 的作品行剩余条数（人物不计）")
    cursor: str = Field(
        default="", description="本批最后一条 media_id（下一批用它当 after 游标）"
    )
    throttled: bool = Field(
        default=False, description="豆瓣搜索是否处于限流熔断（true = 这轮提前收工，过几分钟再来）"
    )


StatusResponse = schemas.Response[StatusData]
ConfigResponse = schemas.Response[ConfigData]
OpResponse = schemas.Response[OpResult]
# ``/lookup`` 形状随参数变：``media_id`` 给单条详情，``name`` 给候选列表
LookupResponse = schemas.Response[MediaInfo | list[MediaInfo] | None]
SearchResponse = schemas.Response[list[MediaInfo]]
CacheItemsResponse = schemas.Response[CacheItemsData]
BaikePageResponse = schemas.Response[BaikePageData]
BaikeExtResponse = schemas.Response[BaikeExtData]
BaikeExtPageResponse = schemas.Response[BaikeExtPageData]
BaikeExtIdsResponse = schemas.Response[BackfillData]
PersonResponse = schemas.Response[PersonData | None]
NovelResponse = schemas.Response[NovelData | None]
