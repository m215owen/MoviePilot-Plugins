"""识别结果的数据结构（2026-10-23 精简版）。

识别本身不在这里做：``__init__.recognize_drama()`` 把**目录名原样**交给短剧百科
插件的 ``recognize_media``，拿回唯一身份。本模块只声明两件事：

* :class:`Candidate` —— 从 MediaInfo 里摘出来的身份（``media_id`` 即身份主键）；
* :class:`MatchDecision` —— 识别结论（采纳 / 未识别待人工）。

刻意不做任何本地归一、评分、剥除、年份集数校验 —— 这些死代码已按用户要求删除，
识别口径只有一个：**百科识别返回什么就是什么**。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# 选取动作
ACTION_ADOPT = "adopt"  # 采纳（可直接进入整理）
ACTION_HOLD = "hold"    # 未识别，待人工处理


@dataclass
class Candidate:
    """一条待整理剧目的身份视图（由调用方从 MediaInfo 转换而来）。"""

    media_id: str
    title: str = ""
    year: Optional[int] = None
    episode_count: Optional[int] = None
    kind: str = ""


@dataclass
class MatchDecision:
    """识别结论：采纳哪条身份，或为什么没采纳。"""

    action: str
    candidate: Optional[Candidate] = None
    reason: str = ""

    @property
    def adopted(self) -> bool:
        """是否可以直接进入整理流程。"""
        return self.action == ACTION_ADOPT
