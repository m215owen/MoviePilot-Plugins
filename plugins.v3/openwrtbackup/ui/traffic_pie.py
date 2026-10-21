"""
流量占比环图（纯 SVG 内联 HTML，无第三方图表库）
MP 的 VPage 组件树支持节点的 html 字段（前端用 innerHTML 渲染），因此可直接注入 SVG。
"""
from typing import Any, Dict, List

from ..openwrt.format_utils import human_bytes

# 固定调色板：按排名顺序取色，深色/浅色主题下均可辨识
PALETTE = [
    "#5E7CE2", "#4FC3A1", "#F5A623", "#E5657A", "#8E7CC3",
    "#3DA5D9", "#F2C14E", "#7EC8E3", "#B5838D", "#90BE6D",
]
OTHER_COLOR = "#9E9E9E"


def _escape(text: Any) -> str:
    """HTML 转义，避免主机名里的特殊字符破坏结构"""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;"))


def short_device_name(name: Any, limit: int = 22) -> str:
    """设备显示名：去掉 .lan 后缀（太短则保留），过长截断"""
    text = str(name or "").strip()
    if text.endswith(".lan") and len(text) > 6:
        text = text[:-4]
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text


def _short_name(item: Dict[str, Any], limit: int = 22) -> str:
    """图例里显示的设备名：主机名优先，过长截断"""
    name = item.get("host") or item.get("interface") or item.get("ip") or item.get("mac") or "未知设备"
    return short_device_name(name, limit)


def _slice_total(item: Dict[str, Any]) -> int:
    try:
        return max(0, int(item.get("rx_bytes") or 0) + int(item.get("tx_bytes") or 0))
    except (TypeError, ValueError):
        return 0


def build_donut_html(stats: List[Dict[str, Any]], top_n: int = 8,
                     size: int = 200, stroke: int = 28) -> str:
    """
    构建流量占比环图 + 图例的 HTML 片段
    :param stats: 流量列表（需含 rx_bytes / tx_bytes / host / interface / ip）
    :param top_n: 图例最多显示几项，其余合并为「其他」
    :param size: 环图外框边长(px)
    :param stroke: 环宽(px)
    :return: HTML 字符串；无数据返回空串
    """
    items = [s for s in (stats or []) if _slice_total(s) > 0]
    if not items:
        return ""

    items.sort(key=_slice_total, reverse=True)
    grand_total = sum(_slice_total(s) for s in items)
    if grand_total <= 0:
        return ""

    head = items[:top_n]
    rest = items[top_n:]

    segments: List[Dict[str, Any]] = []
    for idx, item in enumerate(head):
        total = _slice_total(item)
        segments.append({
            "name": _short_name(item),
            "color": PALETTE[idx % len(PALETTE)],
            "bytes": total,
            "pct": total / grand_total * 100,
        })
    if rest:
        rest_bytes = sum(_slice_total(s) for s in rest)
        segments.append({
            "name": f"其他 {len(rest)} 台",
            "color": OTHER_COLOR,
            "bytes": rest_bytes,
            "pct": rest_bytes / grand_total * 100,
        })

    # 环形几何
    center = size / 2.0
    radius = center - stroke / 2.0 - 4
    circumference = 2 * 3.141592653589793 * radius

    circles = []
    offset = 0.0
    for seg in segments:
        length = circumference * seg["pct"] / 100.0
        # 极细的分段在最前面补 0.4px，避免完全看不见
        draw_len = max(length, 0.4)
        circles.append(
            f'<circle cx="{center:.1f}" cy="{center:.1f}" r="{radius:.1f}" fill="none" '
            f'stroke="{seg["color"]}" stroke-width="{stroke}" '
            f'stroke-dasharray="{draw_len:.2f} {circumference - draw_len:.2f}" '
            f'stroke-dashoffset="{-offset:.2f}"></circle>'
        )
        offset += length

    svg = (
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" '
        f'style="flex:none" xmlns="http://www.w3.org/2000/svg">'
        f'<g transform="rotate(-90 {center:.1f} {center:.1f})">'
        + "".join(circles) +
        '</g>'
        f'<text x="{center:.1f}" y="{center - 6:.1f}" text-anchor="middle" '
        f'style="font-size:12px;fill:currentColor;opacity:.6">总流量</text>'
        f'<text x="{center:.1f}" y="{center + 16:.1f}" text-anchor="middle" '
        f'style="font-size:17px;font-weight:700;fill:currentColor">{human_bytes(grand_total)}</text>'
        '</svg>'
    )

    legend_rows = []
    for seg in segments:
        legend_rows.append(
            '<div style="display:flex;align-items:center;gap:8px;font-size:12px;line-height:1.4">'
            f'<span style="width:10px;height:10px;border-radius:3px;background:{seg["color"]};flex:none"></span>'
            f'<span style="flex:1 1 auto;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;opacity:.85">'
            f'{_escape(seg["name"])}</span>'
            f'<span style="flex:none;opacity:.6;font-variant-numeric:tabular-nums">{human_bytes(seg["bytes"])}</span>'
            f'<span style="flex:none;min-width:46px;text-align:right;font-weight:600;'
            f'font-variant-numeric:tabular-nums">{seg["pct"]:.1f}%</span>'
            '</div>'
        )

    legend = (
        '<div style="display:flex;flex-direction:column;gap:6px;flex:1 1 220px;min-width:200px">'
        + "".join(legend_rows) +
        '</div>'
    )

    return (
        '<div style="display:flex;gap:20px;flex-wrap:wrap;align-items:center;justify-content:center;'
        'color:inherit;padding:4px 0 8px">'
        + svg + legend +
        '</div>'
    )
