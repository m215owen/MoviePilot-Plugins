"""
仪表盘构建器模块
负责构建插件仪表盘
"""
from typing import Any, List, Dict, Tuple, Optional
from app.log import logger

from ..openwrt.status import OpenWrtStatus
from ..openwrt.format_utils import human_bytes
from .traffic_pie import build_donut_html, short_device_name


class DashboardBuilder:
    """仪表盘构建器类"""
    
    def __init__(self, plugin_instance):
        self.plugin = plugin_instance
        self.plugin_name = plugin_instance.plugin_name
        self.openwrt_status = OpenWrtStatus(plugin_instance)
    
    def _get_openwrt_data(self) -> Dict[str, Any]:
        """获取OpenWrt路由器状态信息"""
        try:
            # 检查配置是否完整
            if not self.plugin._openwrt_host or not self.plugin._openwrt_host.strip():
                return {"status": "error", "message": "请先配置OpenWrt路由器基本信息（地址、用户名、密码）"}
            
            if not self.plugin._openwrt_username or not self.plugin._openwrt_username.strip():
                return {"status": "error", "message": "请先配置OpenWrt用户名"}
            
            if not self.plugin._openwrt_password:
                return {"status": "error", "message": "请先配置OpenWrt密码"}
            
            # 获取系统状态、流量统计和插件服务
            system_status = self.openwrt_status.get_system_status()
            traffic_stats = self.openwrt_status.get_traffic_stats()
            plugin_services = self.openwrt_status.get_plugin_services()
            
            if not system_status:
                return {"status": "error", "message": "无法获取系统信息"}
            
            return {
                "status": "success",
                "system": system_status,
                "traffic": traffic_stats or [],
                "plugins": plugin_services or []
            }
        except Exception as e:
            logger.error(f"{self.plugin_name} 获取OpenWrt状态失败: {e}")
            return {"status": "error", "message": str(e)}
    
    def build_dashboard(self, **kwargs) -> Tuple[Dict[str, Any], Dict[str, Any], List[dict]]:
        """构建仪表盘 - 返回 (cols, attrs, elements)"""
        # 仪表盘列配置
        cols = {
            "cols": 12, 
            "md": 12
        }
        
        # 仪表盘属性配置：刷新间隔30秒，显示边框
        attrs = {
            "refresh": 30, 
            "border": False
        }
        
        # 获取OpenWrt数据
        openwrt_data = self._get_openwrt_data()
        
        # 格式化函数
        def format_bytes(bytes_value):
            """格式化字节显示"""
            if bytes_value < 1024:
                return f"{bytes_value} B"
            elif bytes_value < 1024 * 1024:
                return f"{bytes_value / 1024:.2f} KB"
            elif bytes_value < 1024 * 1024 * 1024:
                return f"{bytes_value / (1024 * 1024):.2f} MB"
            else:
                return f"{bytes_value / (1024 * 1024 * 1024):.2f} GB"
        
        def format_uptime(uptime_str):
            """格式化运行时间"""
            if not uptime_str or uptime_str == "N/A":
                return "N/A"
            return uptime_str
        
        # 提取OpenWrt数据
        system_info = openwrt_data.get("system", {}) if openwrt_data.get("status") == "success" else {}
        traffic_info = openwrt_data.get("traffic", []) if openwrt_data.get("status") == "success" else []
        plugin_info = openwrt_data.get("plugins", []) if openwrt_data.get("status") == "success" else []
        
        cpu_usage = system_info.get("cpu_usage", 0)
        mem_usage = system_info.get("memory_usage", 0)
        mem_total = system_info.get("memory_total", 0)
        mem_used = system_info.get("memory_used", 0)
        uptime = system_info.get("uptime", "N/A")
        temperature = system_info.get("temperature", "N/A")
        load_5min = system_info.get("load_5min", "N/A")
        version = system_info.get("version", "N/A")
        
        # 确定颜色
        cpu_color = "success" if cpu_usage < 50 else "warning" if cpu_usage < 80 else "error"
        mem_color = "success" if mem_usage < 50 else "warning" if mem_usage < 80 else "error"
        
        # 构建仪表盘元素列表
        elements = []
        
        # 1. 系统概况卡片
        if openwrt_data.get("status") == "success":
            system_card = {
                'component': 'VCard',
                'props': {'variant': 'outlined', 'class': 'mb-3'},
                'content': [
                    {
                        'component': 'VCardTitle',
                        'props': {'class': 'text-h6'},
                        'text': '📊 系统概况'
                    },
                    {
                        'component': 'VDivider',
                        'props': {'class': 'my-2'}
                    },
                    {
                        'component': 'VCardText',
                        'content': [
                            {
                                'component': 'VRow',
                                'content': [
                                    {
                                        'component': 'VCol',
                                        'props': {'cols': '12', 'sm': '6', 'md': '3'},
                                        'content': [
                                            {
                                                'component': 'div',
                                                'props': {'class': 'pa-2'},
                                                'content': [
                                                    {
                                                        'component': 'div',
                                                        'props': {'class': 'd-flex align-center mb-2'},
                                                        'content': [
                                                            {'component': 'span', 'props': {'class': 'mr-2'}, 'text': '🖥️'},
                                                            {'component': 'span', 'props': {'class': 'text-body-2'}, 'text': 'CPU'},
                                                            {'component': 'VSpacer'},
                                                            {'component': 'span', 'props': {'class': 'text-body-1 font-weight-bold'}, 'text': f'{cpu_usage:.1f}%'}
                                                        ]
                                                    },
                                                    {
                                                        'component': 'VProgressLinear',
                                                        'props': {
                                                            'model-value': cpu_usage,
                                                            'color': cpu_color,
                                                            'height': '6',
                                                            'rounded': True
                                                        }
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        'component': 'VCol',
                                        'props': {'cols': '12', 'sm': '6', 'md': '3'},
                                        'content': [
                                            {
                                                'component': 'div',
                                                'props': {'class': 'pa-2'},
                                                'content': [
                                                    {
                                                        'component': 'div',
                                                        'props': {'class': 'd-flex align-center mb-2'},
                                                        'content': [
                                                            {'component': 'span', 'props': {'class': 'mr-2'}, 'text': '💾'},
                                                            {'component': 'span', 'props': {'class': 'text-body-2'}, 'text': '内存'},
                                                            {'component': 'VSpacer'},
                                                            {'component': 'span', 'props': {'class': 'text-body-1 font-weight-bold'}, 'text': f'{mem_usage:.1f}%'}
                                                        ]
                                                    },
                                                    {
                                                        'component': 'VProgressLinear',
                                                        'props': {
                                                            'model-value': mem_usage,
                                                            'color': mem_color,
                                                            'height': '6',
                                                            'rounded': True
                                                        }
                                                    },
                                                    {
                                                        'component': 'div',
                                                        'props': {'class': 'text-caption text-medium-emphasis mt-1'},
                                                        'text': f"已用 {format_bytes(mem_used * 1024 * 1024)} / 总计 {format_bytes(mem_total * 1024 * 1024)}"
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        'component': 'VCol',
                                        'props': {'cols': '12', 'sm': '6', 'md': '3'},
                                        'content': [
                                            {
                                                'component': 'div',
                                                'props': {'class': 'pa-2'},
                                                'content': [
                                                    {
                                                        'component': 'div',
                                                        'props': {'class': 'd-flex align-center mb-1'},
                                                        'content': [
                                                            {'component': 'span', 'props': {'class': 'mr-2'}, 'text': '🌡️'},
                                                            {'component': 'span', 'props': {'class': 'text-body-2'}, 'text': '温度'}
                                                        ]
                                                    },
                                                    {
                                                        'component': 'div',
                                                        'props': {'class': 'text-h6 font-weight-bold'}, 
                                                        'text': str(temperature)
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        'component': 'VCol',
                                        'props': {'cols': '12', 'sm': '6', 'md': '3'},
                                        'content': [
                                            {
                                                'component': 'div',
                                                'props': {'class': 'pa-2'},
                                                'content': [
                                                    {
                                                        'component': 'div',
                                                        'props': {'class': 'd-flex align-center mb-1'},
                                                        'content': [
                                                            {'component': 'span', 'props': {'class': 'mr-2'}, 'text': '⚡'},
                                                            {'component': 'span', 'props': {'class': 'text-body-2'}, 'text': '负载'}
                                                        ]
                                                    },
                                                    {
                                                        'component': 'div',
                                                        'props': {'class': 'text-h6 font-weight-bold'}, 
                                                        'text': str(load_5min)
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            },
                            {
                                'component': 'VDivider',
                                'props': {'class': 'my-2'}
                            },
                            {
                                'component': 'VRow',
                                'props': {'justify': 'space-between'},
                                'content': [
                                    {
                                        'component': 'VCol',
                                        'props': {'cols': 'auto'},
                                        'content': [
                                            {
                                                'component': 'div',
                                                'props': {'class': 'd-flex align-center pa-1'},
                                                'content': [
                                                    {'component': 'span', 'props': {'class': 'mr-2'}, 'text': '⏱️'},
                                                    {'component': 'div', 'content': [
                                                        {'component': 'div', 'props': {'class': 'text-caption font-weight-bold'}, 'text': format_uptime(uptime)},
                                                        {'component': 'div', 'props': {'class': 'text-caption'}, 'text': '运行时间'}
                                                    ]}
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        'component': 'VCol',
                                        'props': {'cols': 'auto'},
                                        'content': [
                                            {
                                                'component': 'div',
                                                'props': {'class': 'd-flex align-center pa-1'},
                                                'content': [
                                                    {'component': 'span', 'props': {'class': 'mr-2'}, 'text': '📦'},
                                                    {'component': 'div', 'content': [
                                                        {'component': 'div', 'props': {'class': 'text-caption font-weight-bold'}, 'text': str(version)},
                                                        {'component': 'div', 'props': {'class': 'text-caption'}, 'text': '固件版本'}
                                                    ]}
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
            elements.append(system_card)
        elif self.plugin._openwrt_host:
            # 如果配置了地址但连接失败，显示错误提示
            error_card = {
                'component': 'VAlert',
                'props': {
                    'type': 'warning',
                    'variant': 'tonal',
                    'text': f'⚠️ 无法获取OpenWrt路由器状态: {openwrt_data.get("message", "未知错误")}',
                    'class': 'mb-3'
                }
            }
            elements.append(error_card)
        
        # 2. 网络流量卡片（精简版，适合仪表盘）
        if traffic_info and len(traffic_info) > 0:
            source = traffic_info[0].get('source', '')
            window_hours = traffic_info[0].get('window_hours', 0)
            grand_total = sum(int(t.get('total_bytes') or 0) for t in traffic_info)
            total_human = human_bytes(grand_total)

            traffic_rows = []
            for traffic in traffic_info[:8]:
                device_name = short_device_name(
                    traffic.get('host') or traffic.get('interface') or 'N/A')
                ip = traffic.get('ip', '')

                name_cell = {
                    'component': 'div',
                    'props': {'class': 'text-body-2'},
                    'text': device_name
                }
                if ip and ip != device_name:
                    name_cell = {
                        'component': 'div',
                        'content': [
                            {'component': 'div', 'props': {'class': 'text-body-2'}, 'text': device_name},
                            {'component': 'div', 'props': {'class': 'text-caption text-medium-emphasis'}, 'text': ip}
                        ]
                    }

                traffic_rows.append({
                    'component': 'tr',
                    'content': [
                        {'component': 'td', 'content': [name_cell]},
                        {'component': 'td', 'text': str(traffic.get('rx_human') or '0 B')},
                        {'component': 'td', 'text': str(traffic.get('tx_human') or '0 B')},
                        {'component': 'td', 'text': f"{traffic.get('pct', 0)}%"}
                    ]
                })

            if traffic_rows:
                if source == 'bandix' and window_hours:
                    window_text = f"Bandix · 最近 {window_hours} 小时 · 共 {len(traffic_info)} 台 · 合计 {total_human}"
                elif source == 'rtbwmon':
                    window_text = f"rtbwmon · 自上次计数重置 · 共 {len(traffic_info)} 台 · 合计 {total_human}"
                else:
                    window_text = f"{source or '未知数据源'} · 共 {len(traffic_info)} 台 · 合计 {total_human}"

                pie_html = build_donut_html(traffic_info, top_n=8, size=176)
                traffic_content = [
                    {
                        'component': 'div',
                        'props': {'class': 'text-caption text-medium-emphasis mb-2'},
                        'text': window_text
                    }
                ]
                if pie_html:
                    traffic_content.append({
                        'component': 'div',
                        'props': {'class': 'mb-2'},
                        'html': pie_html
                    })
                traffic_content.append({
                    'component': 'div',
                    'props': {'style': {'max-height': '260px', 'overflow-y': 'auto'}},
                    'content': [{
                        'component': 'VTable',
                        'props': {'hover': True, 'density': 'compact'},
                        'content': [
                            {
                                'component': 'thead',
                                'content': [
                                    {
                                        'component': 'tr',
                                        'content': [
                                            {'component': 'th', 'props': {'class': 'text-caption'}, 'text': '设备'},
                                            {'component': 'th', 'props': {'class': 'text-caption'}, 'text': '下行'},
                                            {'component': 'th', 'props': {'class': 'text-caption'}, 'text': '上行'},
                                            {'component': 'th', 'props': {'class': 'text-caption'}, 'text': '占比'}
                                        ]
                                    }
                                ]
                            },
                            {
                                'component': 'tbody',
                                'content': traffic_rows
                            }
                        ]
                    }]
                })

                traffic_card = {
                    'component': 'VCard',
                    'props': {'variant': 'outlined'},
                    'content': [
                        {
                            'component': 'VCardTitle',
                            'props': {'class': 'text-h6'},
                            'text': '📈 网络流量'
                        },
                        {
                            'component': 'VCardText',
                            'props': {'class': 'pa-2'},
                            'content': traffic_content
                        }
                    ]
                }
                elements.append(traffic_card)
        
        return cols, attrs, elements

