"""识别结果的落点类型：``app.sdk.media.MediaInfo``（即 ``app.domain.context.MediaInfo``）。

## 为什么不能把 ``app.schemas.MediaInfo`` 直接交给宿主

官方 FAQ 19 / 多数示例写的是 ``from app.schemas import MediaInfo``。在宿主 v3.1.8 上
这条路**会让整条识别链路 500**，实测栈：

```
File "app/application/classification/execution.py", line 420, in _apply_evaluation
    finalized.set_library_category(...)
AttributeError: 'MediaInfo' object has no attribute 'set_library_category'
```

* 识别收敛（``chain/_recognition.py`` → ``application/classification/execution.py``）拿到
  插件返回的对象后，会调 ``set_library_category()`` 回写兼容目录分类；
* 这个方法是 **domain dataclass** 上的方法，``app/schemas/context.py`` 里那个 pydantic
  模型**没有**（它的对应物只是一个 ``library_category`` 字符串字段）；
* 于是插件按名识别明明已经成功（service 层能返回完整 MediaInfo），宿主在 finalize 阶段
  抛异常 → ``/api/v1/media/recognize2`` 返回 500 → 界面上就是「识别不到」。

官方 ``Plugin_Development.md``（§「V3 已为插件整理稳定 SDK」）已明确：新插件优先从
``app.sdk`` 导入，媒体上下文就在 ``app.sdk.media`` —— 那里导出的正是 domain 版。

## 两套模型的字段形态差异（v3.1.8 实测，必须显式转换）

| 字段 | domain（宿主内部） | schemas（HTTP 传输层） |
| --- | --- | --- |
| ``type`` | ``MediaType`` 枚举 | ``str``（"电视剧"） |
| ``genres`` / ``actors`` / ``directors`` | ``List[dict]`` | pydantic 对象（``MediaGenre``/``MediaCredit``） |
| ``detail_link`` | **没有这个字段** | 有（详情页地址） |
| ``classification_facts`` | 有（**宿主分类器从这里读**） | 有（我们 ``classify.attach`` 挂的） |

所以转换是「有损」的：详情页地址在 domain 版上无处安放，直接丢弃（宿主自己也不认这个键）。

## ``classification_facts`` 必须显式搬（2026-10-22 实测，别删）

宿主自动分类读的是**返回对象自己身上的** ``classification_facts``：

```
application/classification/execution.py:  _registered_extensions(media)
  → startup/initializers/modules.py:160  _plugin_classification_facts(media)
    → runtime/extensions/plugin/classification.py:148  facts(media)
        raw_facts = getattr(media, "classification_facts", None)   # ← 就是这里
```

``facts()`` 还会逐条校验：命名空间必须是 ``extensions.<media_source>.``、
字段必须**先声明**（``get_media_source`` 的 ``classification_fields``）、
值必须符合 ``value_type``、``media.type`` 必须在声明的 ``media_types`` 里。
任何一条不满足就**静默丢弃该字段**（只留一条 warning），表现为「规则明明写了却不命中」。

历史坑：本模块原先逐字段构造 domain 对象时漏了这一个键 → 识别/搜索返回给宿主的那条
``MediaInfo`` 事实恒为 ``{}`` → ``extensions.djbaike.kind`` 规则在真实整理里永远取不到值
（只有按 ``identity.media_source`` 写的旧分类规则在生效）。**所以这个键不能省。**

## 站内指标：只有热度/平台/上线时间有宿主坑位

平台进 ``networks``（``MediaCompany`` 列表）、上线时间进 ``release_date``。

**热度 / 播放量 / 收藏数三个模型上都没有对应列**（``popularity`` 是 float，装不了
``383.37万`` 这种原串） —— 它们由 ``classify.facts_for`` 以
``extensions.djbaike.heat / play_count / favorite_count`` 提交**站点原串**（事实通道）。
所以这里**不该**搬 ``popularity``：搬了就是把「站点原串」硬折算成数字，量级感与来源都丢。

## 边界与分工

* **``get_module()`` 的返回值**（``recognize_media`` / ``async_recognize_media`` /
  ``search_medias``）→ 必须走本模块转换；
* **HTTP 端点**（``/lookup``、``/search``）→ 继续用 ``app.schemas.MediaInfo``
  作 ``response_model``；把 domain 版塞进 ``schemas.Response[...]`` 会校验失败
  （pydantic 不会从 dataclass 取属性，实测 ``Input should be a valid dictionary``）。
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional

#: 宿主只认这个命名空间下的事实（``extensions.<media_source>.<field>``）
_FACT_PREFIX = "extensions."


def _has_host_marker(value: Any) -> bool:
    """已经是宿主 domain 对象（带 classification 回写方法）就不用再转。"""
    return hasattr(value, "set_library_category")


def _facts_dict(value: Any) -> dict[str, Any]:
    """把来源专有分类事实归一成 ``{字段id: 标量}``。

    * 只要 ``extensions.`` 开头的键——宿主 ``facts()`` 对别的命名空间直接丢弃并告警；
    * 只要标量（``str`` / ``int`` / ``float`` / ``bool``）：``MediaInfo.classification_facts``
      的声明是 ``dict[str, ClassificationFactValue]``，塞列表/字典进去会在
      ``classification_fact_matches_definition`` 那里被判类型不符；
    * 其余一律丢掉——**少一个字段不该让整次识别失败**。
    """
    if not isinstance(value, Mapping):
        return {}
    cleaned: dict[str, Any] = {}
    for raw_key, item in value.items():
        key = str(raw_key or "").strip()
        if not key.startswith(_FACT_PREFIX) or len(key) <= len(_FACT_PREFIX):
            continue
        if isinstance(item, bool) or isinstance(item, (str, int, float)):
            cleaned[key] = item
    return cleaned


def _credit_dicts(items: Optional[Iterable[Any]]) -> list[dict]:
    """把 schemas 的 ``MediaGenre`` / ``MediaCredit`` 摊成 domain 要的 list[dict]。

    已经是 dict 的原样收下（将来上游换实现时不至于炸），认不出的条目丢掉 ——
    少一条演员不该让整次识别失败。
    """
    rows: list[dict] = []
    for item in items or []:
        if isinstance(item, dict):
            if item:
                rows.append(dict(item))
            continue
        dump = getattr(item, "model_dump", None)
        if callable(dump):
            data = dump(exclude_none=True)
            if data:
                rows.append(data)
    return rows


def _host_media_type(value: Any) -> Any:
    """``type`` 归一到 ``MediaType`` 枚举；认不出的字符串退回电视剧（本来源只声明 TV）。"""
    from app.schemas.types import MediaType

    if isinstance(value, MediaType):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return MediaType(value.strip())
        except ValueError:
            return MediaType.TV
    return MediaType.TV


def _host_seasons(info: Any) -> dict[int, list[int]]:
    """补出宿主要的「季 → 集号列表」。

    domain 的 ``MediaInfo.seasons`` 是 ``Dict[int, List[int]]``，宿主的下载/订阅链路
    （``chain/download/existence.py`` 的缺集判定、``chain/interaction.py`` 的补全）
    都拿它当**有季集信息**的凭据：空 dict 会直接报
    ``ERROR 媒体信息中没有季集信息：<title> (year)`` 并放弃后续补集判断。

    短剧是"单季多集"，站点详情页只给总集数（``number_of_episodes``），所以按
    「第 1 季 = 1..N」补齐。集数未知（0）时保持空 —— 编不出集号就不要编，
    让宿主走它自己的兜底。

    ⚠️ 不从词条名推断季号（2026-10-23 用户明确去除）：站点虽是一季一条独立词条
    （``隐身侍卫第二季``），但那是标题文本、不是结构化数据，出口侧猜出来的季号
    一律不产出 —— 季号恒按第 1 季合成，标题保留词条原样。
    """
    raw = getattr(info, "seasons", None)
    if isinstance(raw, dict) and raw:
        picked: dict[int, list[int]] = {}
        for season_no, episodes in raw.items():
            try:
                picked[int(season_no)] = [int(item) for item in (episodes or [])]
            except (TypeError, ValueError):
                continue  # 形态不认识就别硬转，交给下面的「按总集数补」
        if picked:
            return picked

    total = int(getattr(info, "number_of_episodes", None) or 0)
    if total <= 0:
        return {}
    try:
        season_no = int(getattr(info, "season", None) or 1)
    except (TypeError, ValueError):
        season_no = 1
    return {season_no: list(range(1, total + 1))}


def to_host_media(info: Any) -> Any:
    """``schemas.MediaInfo`` → ``app.sdk.media.MediaInfo``（``None`` 直接透传）。

    幂等：传进来的已经是 domain 版（或有 domain 的方法）就原样返回。
    """
    if info is None:
        return None
    if _has_host_marker(info):
        return info

    from app.sdk.media import MediaInfo as HostMediaInfo

    # ⚠️ 不做季号推断、不做标题归一（2026-10-23 用户明确去除）：词条名里的
    # 「第N季」是站点文本、不是结构化数据，出口侧一律原样透传 —— 标题保留
    # 词条原样（如「隐身侍卫第二季」），season 恒为 None（下游按第 1 季兜底），
    # seasons 按「第 1 季 = 1..N」合成。识别层（``local_match_seasonal`` /
    # ``_meta_season``）仍按季号认对词条，但出口不再携带季号。
    seasons = _host_seasons(info)

    return HostMediaInfo(
        media_source=getattr(info, "media_source", None),
        media_id=getattr(info, "media_id", None),
        type=_host_media_type(getattr(info, "type", None)),
        title=getattr(info, "title", None),
        original_title=getattr(info, "original_title", None),
        year=getattr(info, "year", None),
        season=getattr(info, "season", None),
        seasons=seasons,
        number_of_seasons=len(seasons) or None,
        number_of_episodes=getattr(info, "number_of_episodes", None),
        overview=getattr(info, "overview", None),
        poster_path=getattr(info, "poster_path", None),
        backdrop_path=getattr(info, "backdrop_path", None),
        vote_average=getattr(info, "vote_average", None),
        vote_count=getattr(info, "vote_count", None),
        # 外部 id：NFO 要往外写这两个（媒体服务器靠它们拉更全的元数据）。
        # 白名单式搬运漏了就等于出口侧恒为空 —— 与 release_date 同款漏法。
        douban_id=getattr(info, "douban_id", None),
        tmdb_id=getattr(info, "tmdb_id", None),
        # 上线时间 / 平台：这两个是「识别结果里最容易白解析」的字段 ——
        # parser 已经从 desc 抠出来了，但这里是白名单式搬运，漏一行就等于没解析。
        # 「平台」进 ``networks``（``MediaCompany`` 名字即可，站点不给 id）。
        release_date=getattr(info, "release_date", None),
        status=getattr(info, "status", None),
        networks=_credit_dicts(getattr(info, "networks", None)),
        production_companies=_credit_dicts(getattr(info, "production_companies", None)),
        genres=_credit_dicts(getattr(info, "genres", None)),
        actors=_credit_dicts(getattr(info, "actors", None)),
        directors=_credit_dicts(getattr(info, "directors", None)),
        # 自动分类要的事实（``extensions.djbaike.kind`` 等）：宿主分类器只认返回对象
        # 身上的这个键，漏了就等于本来源没声明过任何事实 —— 详见模块 docstring。
        classification_facts=_facts_dict(getattr(info, "classification_facts", None)),
    )


def to_host_media_list(items: Optional[Iterable[Any]]) -> list[Any]:
    """列表版（``search_medias`` 用）。"""
    return [converted for converted in (to_host_media(item) for item in items or []) if converted]
