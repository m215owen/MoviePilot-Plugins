"""把余额序列画成**波浪风格**的 SVG（面积 + 平滑曲线）。

为什么用 SVG 内联成 data URI：插件详情页是宿主用 Vuetify 组件 JSON 渲染的，
既不能塞脚本也不能塞外链图片请求（图片请求不带登录态）。所以曲线在这里算好、
渲染成 SVG 字符串，再由调用方 base64 成 ``data:image/svg+xml;base64,...``
喂给 ``VImg`` —— 一个请求都不多发，也不暴露 apikey。

本模块是纯函数：输入 ``[(标签, 余额), ...]``，输出 SVG 文本，不碰网络与配置。

两种横轴：

* ``time_axis=False``（默认）—— 标签是 ``YYYY-MM-DD``，点按**索引等距**，用于按天视图；
* ``time_axis=True`` —— 标签带时分（``YYYY-MM-DD HH:MM:SS``），点按**真实时间比例**排布。
  这样「每 30 分钟刷新一次」的采样密度会如实反映在图上：间隔变了，点的疏密也跟着变。
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, List, Optional, Sequence, Tuple

__all__ = ["render_wave_svg"]

#: 曲线主色（与插件图标同一支紫色）
_LINE = "#6D5BF6"
_AREA_OPACITY = "0.13"
_TEXT = "#5B5B66"
_TEXT_STRONG = "#2F2F3A"
_GRID = "rgba(120,120,140,0.16)"

#: 单张图最多画多少个点（点再多也看不出差别，只会让 SVG 变大）
_MAX_POINTS = 140

_TIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d")


def _parse_ts(label: str) -> Optional[float]:
    """把标签解析成时间戳；解析不了返回 None。"""
    text = str(label).strip()
    for fmt in _TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt).timestamp()
        except ValueError:
            continue
    return None


def _thin(series: Sequence[Tuple[str, int]], limit: int = _MAX_POINTS) -> List[Tuple[str, int]]:
    """等间隔抽稀，始终保留首尾两点。"""
    if limit <= 2 or len(series) <= limit:
        return list(series)
    step = (len(series) - 1) / (limit - 1)
    picked = [series[round(index * step)] for index in range(limit)]
    picked[-1] = series[-1]
    return picked


def _axis_positions(labels: Sequence[str], time_axis: bool, left: float, width: float) -> List[float]:
    """算每个点的 x 坐标。

    ``time_axis`` 时按时间戳线性映射 —— 这才是「刷新周期」真正体现在图上的地方：
    23:00 与 08:10 之间隔了 9 小时 10 分，它在横轴上就该占那么宽。
    """
    if len(labels) <= 1:
        return [left + width / 2.0]
    if time_axis:
        stamps = [_parse_ts(label) for label in labels]
        if all(stamp is not None for stamp in stamps):
            valid = [stamp for stamp in stamps if stamp is not None]
            low, high = min(valid), max(valid)
            if high > low:
                return [left + width * (stamp - low) / (high - low) for stamp in valid]
    return [left + width * index / (len(labels) - 1) for index in range(len(labels))]


def _axis_label(label: str, time_axis: bool, cross_day: bool) -> str:
    """横轴标签：按天视图给 ``MM-DD``，时间轴给 ``HH:MM``（跨天时补上日期）"""
    text = str(label)
    if not time_axis:
        return text[5:10] if len(text) >= 10 else text
    if len(text) < 16:
        return text[5:10] if len(text) >= 10 else text
    return text[5:16] if cross_day else text[11:16]


def _smooth_path(coords: Sequence[Tuple[float, float]]) -> str:
    """Catmull-Rom 转三次贝塞尔 —— 点之间保持平滑，看起来像波浪而不是折线。

    **控制点做了区间钳制**：纯 Catmull-Rom 在「190 → 250」这种台阶处会过冲出
    一个比两端都低的假低谷（实测 y 冲到 197，而两端是 177/58）。把每个控制点的
    y 限制在相邻两点之间即可消除过冲，曲线仍然平滑 —— 这就是「单调三次插值」的
    简化做法，用在余额这种阶梯数据上正合适。
    """
    if not coords:
        return ""
    if len(coords) == 1:
        x, y = coords[0]
        return f"M {x:.1f} {y:.1f}"
    path = [f"M {coords[0][0]:.1f} {coords[0][1]:.1f}"]
    for index in range(len(coords) - 1):
        p0 = coords[index - 1] if index > 0 else coords[index]
        p1 = coords[index]
        p2 = coords[index + 1]
        p3 = coords[index + 2] if index + 2 < len(coords) else p2
        c1x = p1[0] + (p2[0] - p0[0]) / 6.0
        c1y = p1[1] + (p2[1] - p0[1]) / 6.0
        c2x = p2[0] - (p3[0] - p1[0]) / 6.0
        c2y = p2[1] - (p3[1] - p1[1]) / 6.0
        # 钳到 p1..p2 的包围盒内，杜绝过冲
        c1x = min(max(c1x, p1[0]), p2[0])
        c2x = min(max(c2x, p1[0]), p2[0])
        low_y, high_y = (p1[1], p2[1]) if p1[1] <= p2[1] else (p2[1], p1[1])
        c1y = min(max(c1y, low_y), high_y)
        c2y = min(max(c2y, low_y), high_y)
        path.append(f"C {c1x:.1f} {c1y:.1f} {c2x:.1f} {c2y:.1f} {p2[0]:.1f} {p2[1]:.1f}")
    return " ".join(path)


def render_wave_svg(
    points: Iterable[Tuple[str, int]],
    width: int = 640,
    height: int = 210,
    title: str = "魔粒余额走势",
    subtitle: str = "",
    time_axis: bool = False,
) -> str:
    """把 ``[(标签, 余额)]`` 画成带面积填充的平滑曲线。

    :param points: 按时间升序；空序列也能出图（显示「暂无余额数据」）。
    :param subtitle: 标题下方的小字说明（如「每 30 分钟自动采样」）。
    :param time_axis: True 时横轴按真实时间比例排布（标签需带时分）。
    """
    raw: List[Tuple[str, int]] = [
        (str(label), int(value)) for label, value in (points or []) if str(label)
    ]
    series = _thin(raw)

    pad_left, pad_right = 14, 14
    pad_top = 44 if not subtitle else 56
    pad_bottom = 28
    inner_w = max(1, width - pad_left - pad_right)
    inner_h = max(1, height - pad_top - pad_bottom)

    parts: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{title}">',
        f"<title>{title}</title>",
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="transparent"/>',
        f'<text x="{pad_left}" y="20" font-family="system-ui, -apple-system, sans-serif" '
        f'font-size="12" fill="{_TEXT}">{title}</text>',
    ]
    if subtitle:
        parts.append(
            f'<text x="{pad_left}" y="36" font-family="system-ui, -apple-system, sans-serif" '
            f'font-size="11" fill="{_TEXT}" fill-opacity="0.75">{subtitle}</text>'
        )

    if not series:
        parts.append(
            f'<text x="{width / 2:.0f}" y="{height / 2:.0f}" text-anchor="middle" '
            f'font-family="system-ui, sans-serif" font-size="13" fill="{_TEXT}">'
            f"暂无余额数据</text>"
        )
        parts.append("</svg>")
        return "".join(parts)

    values = [value for _label, value in series]
    low, high = min(values), max(values)
    span = high - low
    if span == 0:
        low, high = low - 10, high + 10
        span = high - low
    # 上下各留 12% 呼吸空间，避免曲线贴边
    low -= span * 0.12
    high += span * 0.12
    span = high - low

    xs = _axis_positions([label for label, _value in series], time_axis, pad_left, inner_w)
    coords = [
        (x, pad_top + inner_h * (1 - (value - low) / span))
        for x, value in zip(xs, values)
    ]

    # 三条淡网格线（上 / 中 / 下）
    for ratio in (0.0, 0.5, 1.0):
        y = pad_top + inner_h * ratio
        parts.append(
            f'<line x1="{pad_left}" y1="{y:.1f}" x2="{width - pad_right}" y2="{y:.1f}" '
            f'stroke="{_GRID}" stroke-width="1" stroke-dasharray="3 4"/>'
        )

    curve = _smooth_path(coords)
    if len(coords) > 1:
        base_y = pad_top + inner_h
        area = f"{curve} L {coords[-1][0]:.1f} {base_y:.1f} L {coords[0][0]:.1f} {base_y:.1f} Z"
        parts.append(
            f'<path d="{area}" fill="{_LINE}" fill-opacity="{_AREA_OPACITY}" stroke="none"/>'
        )

    parts.append(
        f'<path d="{curve}" fill="none" stroke="{_LINE}" stroke-width="2.6" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
    )

    # 数据点：中间小、末尾大（末尾 = 当前余额）。点多时只画小点，避免糊成一片
    for index, (x, y) in enumerate(coords):
        last = index == len(coords) - 1
        radius = 4.2 if last else (1.8 if len(coords) > 60 else 2.2)
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="#fff" '
            f'stroke="{_LINE}" stroke-width="{2.0 if last else 1.4}"/>'
        )

    # 当前值大字（右上），末尾与首个点对比
    current = values[-1]
    anchor_x = width - pad_right
    parts.append(
        f'<text x="{anchor_x}" y="20" text-anchor="end" '
        f'font-family="system-ui, -apple-system, sans-serif" font-size="17" '
        f'font-weight="600" fill="{_TEXT_STRONG}">{current}</text>'
    )
    if len(values) > 1:
        delta = current - values[0]
        sign = "+" if delta > 0 else ""
        color = "#E5484D" if delta > 0 else ("#18A058" if delta < 0 else _TEXT)
        cross_day = series[0][0][:10] != series[-1][0][:10]
        first_label = _axis_label(series[0][0], time_axis, cross_day)
        last_label = _axis_label(series[-1][0], time_axis, cross_day)
        parts.append(
            f'<text x="{anchor_x}" y="36" text-anchor="end" '
            f'font-family="system-ui, sans-serif" font-size="11" fill="{color}">'
            f"{sign}{delta}（{first_label} → {last_label}）</text>"
        )

    # 横轴：首 / 中 / 尾，避免标签挤在一起
    cross_day = series[0][0][:10] != series[-1][0][:10]
    label_indexes = sorted({0, len(series) // 2, len(series) - 1})
    for index in label_indexes:
        x = xs[index]
        label = _axis_label(series[index][0], time_axis, cross_day)
        anchor = "start" if index == 0 else ("end" if index == len(series) - 1 else "middle")
        parts.append(
            f'<text x="{x:.1f}" y="{height - 8}" text-anchor="{anchor}" '
            f'font-family="system-ui, sans-serif" font-size="10" fill="{_TEXT}">{label}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)
