"""短剧百科数据源的智能体工具定义。

MoviePilot 的 AI 智能体通过这里注册的工具，用**片名或媒体 ID** 识别短剧，
拿到片名 / 年份 / 海报 / 集数 / 标签 / 演员等结构化结果。

工具类必须继承 ``MoviePilotTool``，并用 pydantic 字段声明
``name`` / ``description`` / ``args_schema``。

关于实例绑定：宿主的 ``get_agent_tools()`` 在**插件实例**上调用，因此这里用
``bind()`` 把当前运行实例注入工具类，避免在工具内部依赖进程级单例或硬编码
插件 ID，从而对插件虚拟分身保持友好。
"""
from __future__ import annotations

from typing import Any, ClassVar, Optional, Type

from pydantic import BaseModel, Field

from app.agent.tools.base import MoviePilotTool


class ShortDramaIdentifyInput(BaseModel):
    """智能体工具入参模型。"""

    keyword: Optional[str] = Field(
        default=None,
        description="短剧片名（可只写关键词，例如「万妖图录传」）",
    )
    media_id: Optional[str] = Field(
        default=None,
        description="本数据源的媒体 ID，形如 org:40105；已知 ID 时优先用它，最省额度",
    )
    year: Optional[str] = Field(
        default=None,
        description="年份，用于同名剧消歧",
    )


class ShortDramaIdentifyTool(MoviePilotTool):
    """用片名 / 媒体 ID 识别短剧的智能体工具。"""

    # 工具名称与描述：智能体据此决定何时调用
    name: str = "short_drama_identify"
    description: str = (
        "Identify a Chinese short drama (短剧) through the MoviePilot plugin named "
        "ShortDramaBaikeSource, which uses duanjubaike.org as its data source. Useful for "
        "short dramas that TMDB and Douban do not have. Give either a title keyword or a "
        "media id like org:40105. Returns title, year, poster, episode count, tags and cast."
    )
    args_schema: Type[BaseModel] = ShortDramaIdentifyInput

    # 当前运行的插件实例，由 get_agent_tools() 注入
    _plugin_ref: ClassVar[Any] = None

    @classmethod
    def bind(cls, plugin: Any) -> None:
        """绑定当前运行的插件实例。

        :param plugin: ``ShortDramaBaikeSource`` 的运行时实例
        """
        cls._plugin_ref = plugin

    def get_tool_message(self, **kwargs: Any) -> Optional[str]:
        """返回给用户的执行提示语。"""
        return "正在短剧百科里识别这部短剧……"

    async def run(
        self,
        keyword: Optional[str] = None,
        media_id: Optional[str] = None,
        year: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """工具核心逻辑（异步）。

        :param keyword: 片名关键词
        :param media_id: 形如 ``org:40105`` 的媒体 ID
        :param year: 年份（消歧）
        :param kwargs: 宿主附加参数（如 explanation）
        :return: 面向智能体的文本结果
        """
        plugin = type(self)._plugin_ref
        if plugin is None:
            return "短剧百科数据源插件当前未运行，无法识别。"

        report = plugin.api_recognize(
            media_id=str(media_id or ""),
            keyword=str(keyword or ""),
            year=str(year or ""),
        )
        if not report.get("success"):
            return str(report.get("message") or "未识别到这部短剧。")

        record = report.get("record") or {}
        lines = [
            f"片名：{record.get('title')}",
            f"媒体 ID：{record.get('media_id')}（来源 media_source={record.get('media_source')}）",
            f"年份：{record.get('year') or '未知'}",
            f"集数：{record.get('episode_count') or '未知'}"
            f"｜单集时长：{record.get('duration_minutes') or '未知'} 分钟",
            f"类型：{'、'.join(record.get('tags') or []) or '未知'}"
            f"｜真人/AI：{record.get('kind') or '未知'}",
            f"海报：{record.get('poster') or '无'}",
            f"详情页：{record.get('url') or '无'}",
        ]
        if record.get("overview"):
            lines.append(f"简介：{record['overview']}")
        actors = record.get("actors") or []
        if actors:
            cast = "、".join(
                f"{actor.get('name')}"
                + (f"（饰 {actor['role']}）" if actor.get("role") else "")
                for actor in actors[:12]
            )
            lines.append(f"主要演员：{cast}")
        return "\n".join(lines)
