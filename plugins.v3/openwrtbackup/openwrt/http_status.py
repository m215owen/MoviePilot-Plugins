"""
OpenWrt HTTP状态获取模块
负责通过HTTP API获取系统状态、流量统计和服务状态
"""
import re
import time
from typing import Optional, Dict, List
from app.log import logger

from .http_client import OpenWrtHTTPClient
from .format_utils import human_bytes


class OpenWrtHTTPStatus:
    """OpenWrt HTTP状态获取类"""
    
    def __init__(self, plugin_instance):
        """
        初始化OpenWrt HTTP状态获取器
        :param plugin_instance: OpenWrtBackup插件实例
        """
        self.plugin = plugin_instance
        self.plugin_name = plugin_instance.plugin_name
        self.http_client = OpenWrtHTTPClient(plugin_instance)
    
    def _ensure_connected(self) -> bool:
        """确保已连接"""
        # 如果session或auth_token不存在，直接登录
        if not self.http_client.session or not self.http_client.auth_token:
            success, error = self.http_client.login()
            if not success:
                logger.error(f"{self.plugin_name} HTTP连接失败: {error}")
                return False
            return True
        
        # 如果已存在session，先尝试一个简单的RPC调用来验证是否有效
        # 如果RPC调用失败（可能是session过期），则重新登录
        try:
            test_result = self.http_client._call_rpc('system', 'board', {})
            if test_result is None:
                # RPC调用失败，可能是session过期，重新登录
                logger.debug(f"{self.plugin_name} 检测到session可能过期，重新登录...")
                self.http_client.session = None
                self.http_client.auth_token = None
                success, error = self.http_client.login()
                if not success:
                    logger.error(f"{self.plugin_name} HTTP重新连接失败: {error}")
                    return False
        except Exception as e:
            # 如果测试调用异常，也重新登录
            logger.debug(f"{self.plugin_name} 连接测试异常，重新登录: {e}")
            self.http_client.session = None
            self.http_client.auth_token = None
            success, error = self.http_client.login()
            if not success:
                logger.error(f"{self.plugin_name} HTTP重新连接失败: {error}")
                return False
        
        return True
    
    def _read_proc_stat(self) -> Optional[tuple]:
        """
        通过 ubus file.read 读取路由器 /proc/stat 的 cpu 汇总行
        :return: (total_jiffies, idle_jiffies)，失败返回 None
        """
        result = self.http_client._call_rpc('file', 'read', {'path': '/proc/stat'})
        if not result or not isinstance(result, dict):
            return None
        data = result.get('data')
        if not isinstance(data, str):
            return None
        for line in data.split('\n'):
            if line.startswith('cpu '):
                fields = line.split()[1:]
                try:
                    values = [int(float(v)) for v in fields]
                except (TypeError, ValueError):
                    return None
                if len(values) < 4:
                    return None
                # 第4列 idle + 第5列 iowait 视为空闲
                idle = values[3] + (values[4] if len(values) > 4 else 0)
                return sum(values), idle
        return None

    def _get_cpu_usage_from_proc(self, interval: float = 0.4) -> Optional[float]:
        """两次采样 /proc/stat 计算 CPU 使用率（iStoreOS 的 luci.getCPUUsage 通常不可用）"""
        first = self._read_proc_stat()
        if not first:
            return None
        time.sleep(interval)
        second = self._read_proc_stat()
        if not second:
            return None
        total_delta = second[0] - first[0]
        idle_delta = second[1] - first[1]
        if total_delta <= 0:
            return None
        usage = (1 - idle_delta / total_delta) * 100
        return round(max(0.0, min(usage, 100.0)), 1)

    def _get_temperature(self) -> str:
        """
        读取温度：优先 /sys/class/thermal/thermal_zone*/temp，其次 luci.getTempInfo
        x86 软路由多数没有温度传感器，此时返回友好文案而非 N/A
        """
        for zone in (0, 1, 2):
            result = self.http_client._call_rpc(
                'file', 'read', {'path': f'/sys/class/thermal/thermal_zone{zone}/temp'})
            if result and isinstance(result, dict):
                raw = str(result.get('data', '')).strip()
                if not raw:
                    continue
                try:
                    value = float(raw)
                except ValueError:
                    continue
                if abs(value) > 200:  # 毫摄氏度
                    value = value / 1000.0
                return f"{value:.1f}°C"
        temp_result = self.http_client._call_rpc('luci', 'getTempInfo', {})
        if temp_result and isinstance(temp_result, dict):
            tempinfo_str = temp_result.get('tempinfo')
            if tempinfo_str:
                return str(tempinfo_str)
        return '无温度传感器'

    def get_system_status(self) -> Optional[Dict]:
        """获取系统状态信息"""
        if not self._ensure_connected():
            return None
        
        try:
            status = {}
            
            # 获取系统信息
            result = self.http_client._call_rpc('system', 'info', {})
            if result:
                # 解析系统信息
                if 'uptime' in result:
                    uptime_seconds = result['uptime']
                    days = int(uptime_seconds // 86400)
                    hours = int((uptime_seconds % 86400) // 3600)
                    minutes = int((uptime_seconds % 3600) // 60)
                    if days > 0:
                        status['uptime'] = f"{days}天{hours}小时{minutes}分钟"
                    else:
                        status['uptime'] = f"{hours}小时{minutes}分钟"
                    status['uptime_seconds'] = int(uptime_seconds)
                
                if 'load' in result:
                    load = result['load']
                    if isinstance(load, list) and len(load) >= 3:
                        # ubus返回的load值是固定点格式，需要除以65536
                        load_1min = load[0] / 65536.0 if isinstance(load[0], (int, float)) else float(load[0])
                        load_5min = load[1] / 65536.0 if isinstance(load[1], (int, float)) else float(load[1])
                        load_15min = load[2] / 65536.0 if isinstance(load[2], (int, float)) else float(load[2])
                        
                        status['load_1min'] = f"{load_1min:.2f}".rstrip('0').rstrip('.')
                        status['load_5min'] = f"{load_5min:.2f}".rstrip('0').rstrip('.')
                        status['load_15min'] = f"{load_15min:.2f}".rstrip('0').rstrip('.')
                
                if 'memory' in result:
                    memory = result['memory']
                    if isinstance(memory, dict):
                        total = memory.get('total', 0)
                        free = memory.get('free', 0)
                        cached = memory.get('cached', 0)
                        buffered = memory.get('buffered', 0)
                        used = total - free - cached - buffered
                        
                        status['memory_total'] = total // (1024 * 1024)  # 转换为MB
                        status['memory_used'] = used // (1024 * 1024)
                        status['memory_free'] = free // (1024 * 1024)
                        status['memory_usage'] = round((used / total * 100), 1) if total > 0 else 0
                
                if 'swap' in result:
                    swap = result['swap']
                    if isinstance(swap, dict):
                        swap_total = swap.get('total', 0)
                        swap_free = swap.get('free', 0)
                        swap_used = swap_total - swap_free
                        status['swap_total'] = swap_total // (1024 * 1024)
                        status['swap_used'] = swap_used // (1024 * 1024)
                        status['swap_usage'] = round((swap_used / swap_total * 100), 1) if swap_total > 0 else 0
            
            # 获取CPU使用率：/proc/stat 两次采样（iStoreOS 上 luci.getCPUUsage 会 Access denied）
            cpu_usage = self._get_cpu_usage_from_proc()
            if cpu_usage is None:
                cpu_usage_result = self.http_client._call_rpc('luci', 'getCPUUsage', {})
                if cpu_usage_result and isinstance(cpu_usage_result, dict):
                    cpuusage_str = cpu_usage_result.get('cpuusage', '')
                    if cpuusage_str:
                        cpu_match = re.search(r'(\d+\.?\d*)%', cpuusage_str)
                        if cpu_match:
                            cpu_usage = round(float(cpu_match.group(1)), 1)
            if cpu_usage is not None:
                status['cpu_usage'] = cpu_usage

            # 板卡信息：内核 / 固件版本 / 架构一次拿全（不依赖 luci 命名空间）
            board_result = self.http_client._call_rpc('system', 'board', {})
            if board_result and isinstance(board_result, dict):
                if board_result.get('kernel'):
                    status['kernel'] = board_result['kernel']

                release = board_result.get('release') or {}
                # 固件版本优先用 release.description（如 "iStoreOS 24.10.8 2026073111"）
                firmware = release.get('description') or release.get('version') or ''
                if firmware:
                    status['version'] = firmware

                # 架构：x86 上 board_name/model 是 "default-string-default-string" 这类无意义串，
                # 优先 CPU 型号(system) + 发行版 target
                cpu_model = str(board_result.get('system') or '').strip()
                target = str(release.get('target') or '').strip()
                arch_parts = []
                if cpu_model and 'default string' not in cpu_model.lower():
                    arch_parts.append(cpu_model)
                if target:
                    arch_parts.append(target)
                if arch_parts:
                    status['architecture'] = ' / '.join(arch_parts)

            # 固件版本兜底：LuCI 版本（仅当 board 未取到时）
            if not status.get('version'):
                luci_version = self.http_client._call_rpc('luci', 'getVersion', {})
                if luci_version and isinstance(luci_version, dict):
                    revision = luci_version.get('revision', '')
                    branch = luci_version.get('branch', '')
                    if revision and branch:
                        status['version'] = f"{branch} ({revision})"
                    elif revision:
                        status['version'] = revision
                    elif branch:
                        status['version'] = branch

            # 温度：thermal_zone 优先，无传感器时给出友好文案
            status['temperature'] = self._get_temperature()

            return status
        except Exception as e:
            logger.error(f"{self.plugin_name} 获取系统状态失败: {e}")
            return None
    
    def get_traffic_stats(self) -> Optional[List[Dict]]:
        """获取网络流量（按设备显示），数据源由插件配置 traffic_source 决定"""
        if not self._ensure_connected():
            return None

        try:
            # 数据源：auto（bandix 优先，依次回退 rtbwmon / wrtbwmon）/ bandix / wrtbwmon / rtbwmon
            source = str(getattr(self.plugin, '_traffic_source', 'auto') or 'auto').strip().lower()
            try:
                hours = int(getattr(self.plugin, '_traffic_window_hours', 24) or 24)
            except (TypeError, ValueError):
                hours = 24
            if hours <= 0:
                hours = 24

            if source == 'off':
                return []

            if source == 'bandix':
                traffic_stats = self._get_traffic_from_bandix(hours=hours)
            elif source == 'wrtbwmon':
                traffic_stats = self._get_traffic_from_wrtbwmon()
            elif source == 'rtbwmon':
                traffic_stats = self._get_traffic_from_rtbwmon()
            else:
                traffic_stats = (self._get_traffic_from_bandix(hours=hours)
                                 or self._get_traffic_from_rtbwmon()
                                 or self._get_traffic_from_wrtbwmon())

            # 补充人类可读字段，UI 层直接用
            for item in traffic_stats:
                total = int(item.get('rx_bytes') or 0) + int(item.get('tx_bytes') or 0)
                item['total_bytes'] = total
                item['total_human'] = human_bytes(total)
                item['rx_human'] = human_bytes(item.get('rx_bytes'))
                item['tx_human'] = human_bytes(item.get('tx_bytes'))

            # 按流量总量排序（降序）
            traffic_stats.sort(key=lambda x: x['rx_bytes'] + x['tx_bytes'], reverse=True)
            return traffic_stats
        except Exception as e:
            logger.error(f"{self.plugin_name} 获取流量统计失败: {e}")
            return None

    def _get_traffic_from_bandix(self, hours: int = 24) -> List[Dict]:
        """
        通过 luci.bandix.getTrafficUsageRanking 获取各设备流量（统计窗口：最近 N 小时）
        :return: 设备流量列表，接口不可用时返回空列表
        """
        traffic_stats = []
        now_ms = int(time.time() * 1000)
        start_ms = now_ms - hours * 3600 * 1000
        result = self.http_client._call_rpc(
            'luci.bandix', 'getTrafficUsageRanking',
            {'start_ms': start_ms, 'end_ms': now_ms, 'network_type': 'all'})
        if not result or not isinstance(result, dict):
            return traffic_stats

        rows = result.get('r') or []
        if not isinstance(rows, list):
            return traffic_stats

        # 占比分母：接口给的 t_b 优先，否则用各设备求和
        try:
            total_bytes = float(result.get('t_b') or 0)
        except (TypeError, ValueError):
            total_bytes = 0
        if total_bytes <= 0:
            total_bytes = sum(
                float(item.get('rx_b') or 0) + float(item.get('tx_b') or 0)
                for item in rows if isinstance(item, dict)) or 1

        for item in rows:
            if not isinstance(item, dict):
                continue
            try:
                rx_bytes = int(item.get('rx_b') or 0)
                tx_bytes = int(item.get('tx_b') or 0)
            except (TypeError, ValueError):
                continue
            if rx_bytes <= 0 and tx_bytes <= 0:
                continue

            ip = str(item.get('ip4') or '')
            host = str(item.get('host') or '').strip()
            mac = str(item.get('mac') or '')
            # 主机名优先（bandix 会带反查域名），没有则用 IP/MAC
            device_name = host or ip or mac

            pct = item.get('pct')
            try:
                pct = round(float(pct), 1)
            except (TypeError, ValueError):
                pct = round((rx_bytes + tx_bytes) / total_bytes * 100, 1)

            traffic_stats.append({
                'interface': device_name,
                'host': host,
                'mac': mac,
                'ip': ip,
                'iface': '',
                'rx_bytes': rx_bytes,
                'rx_mb': round(rx_bytes / (1024 * 1024), 2),
                'tx_bytes': tx_bytes,
                'tx_mb': round(tx_bytes / (1024 * 1024), 2),
                'pct': pct,
                'source': 'bandix',
                'window_hours': hours,
            })
        return traffic_stats

    def _get_traffic_from_wrtbwmon(self) -> List[Dict]:
        """旧数据源：luci.wrtbwmon.get_db_raw（wrtbwmon 已卸载的固件上不可用）"""
        traffic_stats = []
        result = self.http_client._call_rpc('luci.wrtbwmon', 'get_db_raw', {'protocol': 'ipv4'})
        if not result or not isinstance(result, dict):
            return traffic_stats

        data_content = result.get('data', '')
        if not isinstance(data_content, str):
            return traffic_stats

        # 格式: #mac,ip,iface,speed_in,speed_out,in,out,total,first_date,last_date
        for line in data_content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split(',')
            if len(parts) < 9:
                continue
            try:
                mac = parts[0]
                ip = parts[1] if parts[1] != 'NA' else ''
                iface = parts[2]
                in_bytes = int(parts[5]) if parts[5] else 0
                out_bytes = int(parts[6]) if parts[6] else 0
            except (ValueError, IndexError):
                continue
            traffic_stats.append({
                'interface': ip if ip else mac,
                'host': '',
                'mac': mac,
                'ip': ip,
                'iface': iface,
                'rx_bytes': in_bytes,
                'rx_mb': round(in_bytes / (1024 * 1024), 2),
                'tx_bytes': out_bytes,
                'tx_mb': round(out_bytes / (1024 * 1024), 2),
                'pct': 0,
                'source': 'wrtbwmon',
                'window_hours': 0,
            })

        total = sum(x['rx_bytes'] + x['tx_bytes'] for x in traffic_stats)
        if total > 0:
            for x in traffic_stats:
                x['pct'] = round((x['rx_bytes'] + x['tx_bytes']) / total * 100, 1)
        return traffic_stats

    def _get_traffic_from_rtbwmon(self) -> List[Dict]:
        """rtbwmon 数据源：经 ubus file.read 读取 /var/run/rtbwmon.csv

        CSV 每行: ip,mac,iface,上行包数,上行字节,下行包数,下行字节[,主机名]
        （上行在前；计数器约每 30 分钟空闲后重置，数值为"自上次重置"的累计量）
        """
        traffic_stats = []
        result = self.http_client._call_rpc('file', 'read', {'path': '/var/run/rtbwmon.csv'})
        if not result or not isinstance(result, dict):
            return traffic_stats

        data_content = result.get('data')
        if not isinstance(data_content, str):
            return traffic_stats

        for line in data_content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split(',')
            if len(parts) < 7:
                continue
            try:
                ip = parts[0] if parts[0] and parts[0] != 'NA' else ''
                mac = parts[1]
                iface = parts[2]
                # 字段顺序：上行在前，下行在后
                tx_bytes = int(parts[4]) if parts[4] else 0
                rx_bytes = int(parts[6]) if parts[6] else 0
            except (ValueError, IndexError):
                continue
            hostname = parts[7].strip() if len(parts) > 7 else ''
            traffic_stats.append({
                'interface': hostname or ip or mac,
                'host': hostname,
                'mac': mac,
                'ip': ip,
                'iface': iface,
                'rx_bytes': rx_bytes,
                'rx_mb': round(rx_bytes / (1024 * 1024), 2),
                'tx_bytes': tx_bytes,
                'tx_mb': round(tx_bytes / (1024 * 1024), 2),
                'pct': 0,
                'source': 'rtbwmon',
                'window_hours': 0,
            })

        total = sum(x['rx_bytes'] + x['tx_bytes'] for x in traffic_stats)
        if total > 0:
            for x in traffic_stats:
                x['pct'] = round((x['rx_bytes'] + x['tx_bytes']) / total * 100, 1)
        return traffic_stats

    def get_plugin_services(self) -> Optional[List[Dict]]:
        """获取LuCI插件服务状态"""
        if not self._ensure_connected():
            return None
        
        try:
            plugin_services = []
            
            # 已知的LuCI插件服务名称关键词
            plugin_keywords = [
                'lucky', 'nikki', 'nps', 'snmpd', 'turboacc', 'eqos',
                'wrtbwmon', 'design', 'adguard', 'passwall', 'openclash',
                'vssr', 'ssr-plus', 'shadowsocks', 'v2ray', 'xray'
            ]
            
            # 使用ubus rc.list获取服务列表
            rc_result = self.http_client._call_rpc('rc', 'list', {})
            if rc_result and isinstance(rc_result, dict):
                # rc.list返回格式: {'service_name': {'start': 80, 'enabled': True, 'running': True}, ...}
                for service_name, service_info in rc_result.items():
                    if isinstance(service_info, dict):
                        # 检查服务名是否包含插件关键词
                        service_name_lower = service_name.lower()
                        is_plugin = any(keyword in service_name_lower for keyword in plugin_keywords)
                        
                        if is_plugin:
                            is_enabled = service_info.get('enabled', False)
                            is_running = service_info.get('running', False)
                            
                            # 只显示已启用或正在运行的插件服务
                            if is_enabled or is_running:
                                plugin_services.append({
                                    'name': service_name,
                                    'enabled': is_enabled,
                                    'running': is_running,
                                    'status': '运行中' if is_running else '已停止'
                                })
                
                # 按服务名排序
                plugin_services.sort(key=lambda x: x['name'])
            
            return plugin_services
        except Exception as e:
            logger.error(f"{self.plugin_name} 获取插件服务状态失败: {e}")
            return None

