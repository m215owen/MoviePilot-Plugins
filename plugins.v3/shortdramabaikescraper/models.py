"""插件自有表（计划 §3）：站点注册表 ``baike`` + 外部 id 表 ``baike_ext``。

分工（2026-11-04 用户口径「外部 id 单独记录，不在站点单独记录」）：

* ``baike``：**站点身份**一行一个 ``media_id``（同一部剧新老站各一行，身份不能合并），
  只存站点自己的东西 —— id、名字、是否 AI 剧。
* ``baike_ext``：**作品级属性**（豆瓣 / TMDB）。它们跟“在哪个站”无关、一部片子只有
  一套，所以**按名字存一份**（主键就是名字），站点行读的时候按名现取。

两张表都不存简介、演员、评分等正文；正文全在缓存里。表名带插件前缀，避免与宿主
或其它插件的同名表冲突（官方 §7.3 硬要求）。
"""

from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.sdk.database import plugin_declarative_base

# 每个进程只构造一次声明基类；热重载重新执行本模块时由 ``extend_existing`` 复用元数据。
PluginBase = plugin_declarative_base()


class Baike(PluginBase):
    """站点注册表：作品与人物共用一表，靠 ``media_id`` 前缀区分。"""

    __tablename__ = "shortdramabaikescraper_baike"
    __table_args__ = {"extend_existing": True}

    # ``{entity}:{id}``，如 duanju:7696405989787978814 / yanyuan:7501352905799128344
    media_id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # 原文，不做归一化：作品=剧名，人物=人名。``WHERE name = ?`` 原样匹配。
    name: Mapped[str] = mapped_column(String(255), index=True, default="")

    # 是否 AI 剧（2026-11-04）：**就是「漫剧」**，同一根「排除」开关的判据。
    # 老站按 media_id 前缀（manju/hema/huolong）就能判，新站没有前缀差异，
    # 只能靠卡片标题行的「AI短剧」标 —— 不带这一列，排除开关对新站的库内行就失效。
    # 只在**见到过标注**时置 True（默认 False 表示「没标 / 未见过」，不是「一定是真人剧」）。
    is_ai: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    def as_dict(self) -> dict:
        """物化成普通字典（会话释放后不能懒加载）。

        ``douban`` / ``tmdb`` 不在这里 —— 它们来自 :class:`BaikeExt`，由仓储层
        读取时按名字挂上（:meth:`store.BaikeStore._attach_ext`），字典形状对上层
        保持不变。
        """
        return {
            "media_id": self.media_id,
            "name": self.name,
            "is_ai": bool(self.is_ai),
        }


class BaikeExt(PluginBase):
    """外部 id 表：**主键就是名字** —— 一个名字只记一条。

    2026-11-04 用户口径：站点库记「名字 + id」，外部 id 记「名字 + tmdb + 豆瓣」，
    读的时候**按名字取**。所以这里没有 scope，也没有站点维度。

    * ``douban``：复合 id，``douban:{sid}``（作品）/ ``doubanp:{pid}``（影人）。
    * ``tmdb``：复合 id，``tmdb:{id}``（作品）/ ``tmdbp:{pid}``（影人）—— 与豆瓣对称
      （2026-11-04 用户口径「豆瓣和 tmdb 的 id 也可以作为复合 id」）。
    * ``owner``：首次写下这条记录的 ``media_id``，纯溯源（不参与任何查询语义）。

    值的种类由 ``store._value_fits`` 在读写两端复核：``doubanp:`` / ``tmdbp:``
    只挂人物行，作品 id 只挂作品行 —— 同名跨种类（剧名撞人名）时不会串台。
    """

    __tablename__ = "shortdramabaikescraper_baike_ext"
    __table_args__ = {"extend_existing": True}

    name: Mapped[str] = mapped_column(String(255), primary_key=True, default="")
    douban: Mapped[str] = mapped_column(String(32), default="")
    tmdb: Mapped[str] = mapped_column(String(32), default="")
    owner: Mapped[str] = mapped_column(String(64), default="")

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "douban": self.douban,
            "tmdb": self.tmdb,
        }


def ensure_table() -> None:
    """只创建本插件的表，不触发宿主全部元数据建表；老库补缺失列。

    老库的 ``douban`` / ``tmdb`` 两列不在这里删：数据要先搬进 ``baike_ext``，
    搬家在 :func:`store.BaikeStore.ensure_table` 里做（它才知道前缀怎么分 scope）。
    """
    from sqlalchemy import inspect, text

    from app.db import Engine

    Baike.__table__.create(bind=Engine, checkfirst=True)
    BaikeExt.__table__.create(bind=Engine, checkfirst=True)
    # ``create(checkfirst=True)`` 只建表不加列：后加的列要就地补（PG 语法；
    # 其它后端理论同 ANSI，失败只降级不挡启动，下次 init 再试）
    missing = {
        "is_ai": "BOOLEAN NOT NULL DEFAULT FALSE",
    }
    # 已废弃的列（2026-11-04 晚删除）：``alt_id`` 曾把同名对站行互指，但写入
    # 来源就是同名匹配、读取端一处都没有 —— 等于把「按名查一次」物化成一个会
    # 陈旧、只填空永不修正的字段。删掉；跨站关系不再需要——外部 id 已经按作品
    # 单存进 ``baike_ext``（与站在哪边无关），没有「另一站那行」要互指了。
    legacy = {"alt_id"}
    try:
        insp = inspect(Engine)
        cols = {col["name"] for col in insp.get_columns(Baike.__tablename__)}
        for name, ddl in missing.items():
            if name in cols:
                continue
            with Engine.begin() as conn:
                conn.execute(
                    text(
                        f"ALTER TABLE {Baike.__tablename__} ADD COLUMN {name} {ddl}"
                    )
                )
        for name in legacy & cols:
            with Engine.begin() as conn:
                conn.execute(
                    text(f"ALTER TABLE {Baike.__tablename__} DROP COLUMN {name}")
                )
    except Exception:  # noqa: BLE001 - 补列失败下次 init 再试，不挡插件启动
        pass
