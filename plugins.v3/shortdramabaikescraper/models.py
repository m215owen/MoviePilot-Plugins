"""插件自有表：``baike`` —— 一张 4 列注册表，覆盖全部查询（计划 §3）。

只存「id ↔ 名字 / 外部 id」，不存简介、演员、评分等正文；正文全在缓存里。
表名带插件前缀，避免与宿主或其它插件的同名表冲突（官方 §7.3 硬要求）。
"""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.sdk.database import plugin_declarative_base

# 每个进程只构造一次声明基类；热重载重新执行本模块时由 ``extend_existing`` 复用元数据。
PluginBase = plugin_declarative_base()


class Baike(PluginBase):
    """短剧百科的 id 注册表：作品与人物共用一表，靠 ``media_id`` 前缀区分。"""

    __tablename__ = "shortdramabaikescraper_baike"
    __table_args__ = {"extend_existing": True}

    # ``{entity}:{id}``，如 duanju:7696405989787978814 / yanyuan:7501352905799128344
    media_id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # 原文，不做归一化：作品=剧名，人物=人名。``WHERE name = ?`` 原样匹配。
    name: Mapped[str] = mapped_column(String(255), index=True, default="")

    # 复合 id：douban:{sid} / doubanp:{pid}。初始为空，取到详情时回填。
    douban: Mapped[str] = mapped_column(String(32), index=True, default="")

    # 作品交叉 id：识别时同步从 TMDB 仅取 id 回填；不建索引（只部分填充、系列级共享）。
    tmdb: Mapped[str] = mapped_column(String(32), default="")

    def as_dict(self) -> dict:
        """物化成普通字典（会话释放后不能懒加载）。"""
        return {
            "media_id": self.media_id,
            "name": self.name,
            "douban": self.douban,
            "tmdb": self.tmdb,
        }


def ensure_table() -> None:
    """只创建本插件的表，不触发宿主全部元数据建表。"""
    from app.db import Engine

    Baike.__table__.create(bind=Engine, checkfirst=True)
