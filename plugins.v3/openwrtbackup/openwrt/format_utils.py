"""
通用格式化工具
纯函数，无第三方依赖，供状态层与 UI 层共用
"""
from typing import Any


def human_bytes(value: Any) -> str:
    """
    把字节数格式化为人类可读文本（自动切换 B/KB/MB/GB/TB）
    例：45685186560 -> "42.5 GB"，762534447 -> "727 MB"，94205 -> "92.0 KB"
    """
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return "0 B"

    negative = number < 0
    number = abs(number)

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    index = 0
    while number >= 1024 and index < len(units) - 1:
        number /= 1024.0
        index += 1

    if index == 0:
        text = f"{int(number)} B"
    elif number >= 100:
        text = f"{number:.0f} {units[index]}"
    elif number >= 10:
        text = f"{number:.1f} {units[index]}"
    else:
        text = f"{number:.2f} {units[index]}"

    return f"-{text}" if negative else text
