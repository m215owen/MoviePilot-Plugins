"""
插件开发模板的智能体工具定义。

MoviePilot 的 AI 智能体通过这里注册的工具来读取插件状态。工具类必须继承
``MoviePilotTool``，并以 pydantic 字段声明 ``name`` / ``description`` / ``args_schema``。

关于实例绑定：宿主的 ``get_agent_tools()`` 在插件实例上调用，因此这里用
``bind()`` 把当前运行实例注入工具类，避免在工具内部依赖进程级单例或硬编码插件 ID，
从而对插件虚拟分身保持友好。若插件源码被某个实例遮蔽而需要反向查表，可改用
``app.sdk`` 提供的插件管理器，但优先推荐本模板的注入方式。
"""
from __future__ import annotations

from typing import Any, ClassVar, Optional, Type

from pydantic import BaseModel, Field

from app.agent.tools.base import MoviePilotTool


class StatusQueryInput(BaseModel):
    """智能体工具入参模型。"""

    limit: int = Field(default=5, description="需要返回的最近执行记录条数")


class PluginTemplateStatusTool(MoviePilotTool):
    """查询「插件开发模板」最近执行记录的智能体工具。"""

    # 工具名称与描述：智能体据此决定何时调用
    name: str = "plugin_template_status"
    description: str = (
        "Query the latest execution records of the MoviePilot plugin named "
        "PluginTemplate (插件开发模板)."
    )
    # 输入参数模型
    args_schema: Type[BaseModel] = StatusQueryInput

    # 当前运行的插件实例，由 get_agent_tools() 注入
    _plugin_ref: ClassVar[Any] = None

    @classmethod
    def bind(cls, plugin: Any) -> None:
        """绑定当前运行的插件实例。

        :param plugin: ``PluginTemplate`` 的运行时实例
        """
        cls._plugin_ref = plugin

    def get_tool_message(self, **kwargs: Any) -> Optional[str]:
        """返回给用户的执行提示语。"""
        return "正在查询插件开发模板的执行记录……"

    async def run(self, limit: int = 5, **kwargs: Any) -> str:
        """工具核心逻辑（异步）。

        :param limit: 返回的记录条数
        :param kwargs: 宿主附加参数（如 explanation）
        :return: 面向智能体的文本结果
        """
        plugin = type(self)._plugin_ref
        if plugin is None:
            return "插件开发模板当前未运行，无法查询执行记录。"

        records = plugin.get_records(limit=limit)
        if not records:
            return "插件开发模板暂无执行记录。"

        lines = [
            f"- {item.get('time')}｜触发方式 {item.get('trigger')}｜"
            f"{'成功' if item.get('success') else '失败'}：{item.get('detail')}"
            for item in records
        ]
        return f"插件开发模板最近 {len(lines)} 条执行记录：\n" + "\n".join(lines)
