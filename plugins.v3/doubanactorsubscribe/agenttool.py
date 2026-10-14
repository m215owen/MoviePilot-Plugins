"""
TMDB 演员订阅的智能体工具定义。

MoviePilot 的 AI 智能体通过这里注册的工具读取插件抓取到的演员作品数据。
工具类必须继承 ``MoviePilotTool``，并以 pydantic 字段声明
``name`` / ``description`` / ``args_schema``。

关于实例绑定：宿主的 ``get_agent_tools()`` 在插件实例上调用，因此这里用
``bind()`` 把当前运行实例注入工具类，避免在工具内部依赖进程级单例或硬编码
插件 ID，从而对插件虚拟分身保持友好。
"""
from __future__ import annotations

from typing import Any, ClassVar, Optional, Type

from pydantic import BaseModel, Field

from app.agent.tools.base import MoviePilotTool


class ActorWorksInput(BaseModel):
    """智能体工具入参模型。"""

    actor: Optional[str] = Field(
        default=None,
        description="演员名称，留空则返回全部已配置演员的作品",
    )
    limit: int = Field(default=8, description="每位演员返回的作品条数上限")


class DoubanActorWorksTool(MoviePilotTool):
    """查询「TMDB 演员订阅」已抓取到的演员最新作品的智能体工具。"""

    # 工具名称是智能体侧的稳定标识符，保持原值不变，避免已配置的智能体找不到工具；
    # 描述与展示文案随插件更名一起更新为 TMDB。
    name: str = "douban_actor_latest_works"
    description: str = (
        "Query the latest filmography of the actors tracked by the MoviePilot plugin "
        "named DoubanActorSubscribe (TMDB演员订阅). Returns each actor's most recent "
        "movies and TV shows with year, rating and TMDB id."
    )
    # 输入参数模型
    args_schema: Type[BaseModel] = ActorWorksInput

    # 当前运行的插件实例，由 get_agent_tools() 注入
    _plugin_ref: ClassVar[Any] = None

    @classmethod
    def bind(cls, plugin: Any) -> None:
        """绑定当前运行的插件实例。

        :param plugin: ``DoubanActorSubscribe`` 的运行时实例
        """
        cls._plugin_ref = plugin

    def get_tool_message(self, **kwargs: Any) -> Optional[str]:
        """返回给用户的执行提示语。"""
        return "正在查询 TMDB 演员的最新作品……"

    async def run(
        self, actor: Optional[str] = None, limit: int = 8, **kwargs: Any
    ) -> str:
        """工具核心逻辑（异步）。

        :param actor: 演员名称，留空返回全部
        :param limit: 每位演员返回的作品条数上限
        :param kwargs: 宿主附加参数（如 explanation）
        :return: 面向智能体的文本结果
        """
        plugin = type(self)._plugin_ref
        if plugin is None:
            return "TMDB 演员订阅插件当前未运行，无法查询作品。"

        try:
            size = max(1, min(int(limit), 50))
        except (TypeError, ValueError):
            size = 8

        payload = plugin.get_works_payload()
        actors = payload.get("actors") or []
        keyword = str(actor or "").strip()
        if keyword:
            matched = [
                item
                for item in actors
                if keyword in str(item.get("name") or "")
                or keyword == str(item.get("key") or "")
                or keyword == str(item.get("id") or "")
            ]
            if not matched:
                known = "、".join(str(item.get("name")) for item in actors) or "（暂无）"
                return f"未找到演员「{keyword}」。当前已配置的演员：{known}"
            actors = matched

        if not actors:
            return "TMDB 演员订阅插件尚未抓取到任何演员作品，请先配置演员并刷新一次。"

        blocks = []
        for item in actors:
            name = str(item.get("name") or item.get("key") or "未知演员")
            works = (item.get("works") or [])[:size]
            if not works:
                blocks.append(f"【{name}】暂无作品数据（{item.get('error') or '待刷新'}）。")
                continue
            lines = [
                f"  · {work.get('title')}（{work.get('year') or '年份未知'}）"
                f"{work.get('type') or ''} 评分 {work.get('vote') or '暂无'}"
                f"｜TMDB ID {work.get('media_id')}"
                for work in works
            ]
            blocks.append(f"【{name}】最近 {len(lines)} 部作品：\n" + "\n".join(lines))
        return "\n".join(blocks)
