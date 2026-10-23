"""落盘前的 JSON 安全关卡。

整理历史统一走系统 ``TransferHistoryOper``，本模块主要用于把识别候选 /
``MediaInfo`` 等宿主对象投影成可 JSON 序列化的精简 dict，避免 ``MediaType`` 等
枚举让 ``save_data`` / 接口响应整体写入失败（真机踩过）。
"""

from __future__ import annotations

import datetime
from typing import Any, Optional


def jsonable(value: Any) -> Any:
    """递归把任意值转成 JSON 安全形态。

    * ``Enum`` → ``.value``
    * ``datetime`` / ``date`` → ISO 字符串
    * 带 ``model_dump`` 的 pydantic / domain 对象 → ``model_dump(mode="json")``
    * 其余 dict / list / tuple / 基础类型原样或递归处理
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    # Enum（MediaType / MediaSource 等）
    if isinstance(value, (str, int, float, bool)) is False and hasattr(value, "value"):
        try:
            return value.value
        except Exception:  # pragma: no cover - 兜底
            pass

    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()

    # pydantic / domain dataclass
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            return dump(mode="json")
        except Exception:  # pragma: no cover - 兜底
            pass

    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set, frozenset)):
        return [jsonable(v) for v in value]

    return str(value)


def safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """宽松整数解析：非法/空值返回 default。"""
    if value is None or value == "":
        return default
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def safe_str(value: Any, default: str = "") -> str:
    """安全字符串化，None/空 → default。"""
    if value is None:
        return default
    text = str(value).strip()
    return text or default
