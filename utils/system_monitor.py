# -*- coding: utf-8 -*-
"""
系统监控工具 - 监控系统运行状态和性能
"""

import psutil
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
import threading


class SystemMonitor:
    """系统监控器"""
    
    def __init__(self):
        self.logger = logging.getLogger('OptionMonitor.SystemMonitor')
        self.is_monitoring = False
        self.monitor_thread = None
        self.stats_history = []
        self.max_history = 1000  # 最多保存1000条记录
        
    def start_monitoring(self, interval: int = 60):
        """开始监控"""
        if self.is_monitoring:
            return
            
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop, 
            args=(interval,), 
            daemon=True
        )
        self.monitor_thread.start()
        self.logger.info("系统监控已启动")
        
    def stop_monitoring(self):
        """停止监控"""
        self.is_monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        self.logger.info("系统监控已停止")
        
    def _monitor_loop(self, interval: int):
        """监控循环"""
        while self.is_monitoring:
            try:
                stats = self._collect_stats()
                self._save_stats(stats)
                time.sleep(interval)
            except Exception as e:
                self.logger.error(f"监控循环异常: {e}")
                time.sleep(10)
                
    def _collect_stats(self) -> Dict[str, Any]:
        """收集系统统计信息"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 内存使用情况
            memory = psutil.virtual_memory()
            
            # 磁盘使用情况
            disk = psutil.disk_usage('/')
            
            # 网络IO
            net_io = psutil.net_io_counters()
            
            # 进程信息
            process = psutil.Process()
            process_info = {
                'cpu_percent': process.cpu_percent(),
                'memory_mb': process.memory_info().rss / 1024 / 1024,
                'num_threads': process.num_threads(),
                'num_fds': process.num_fds() if hasattr(process, 'num_fds') else 0
            }
            
            return {
                'timestamp': datetime.now(),
                'cpu_percent': cpu_percent,
                'memory': {
                    'total_gb': memory.total / 1024 / 1024 / 1024,
                    'available_gb': memory.available / 1024 / 1024 / 1024,
                    'percent': memory.percent,
                    'used_gb': memory.used / 1024 / 1024 / 1024
                },
                'disk': {
                    'total_gb': disk.total / 1024 / 1024 / 1024,
                    'free_gb': disk.free / 1024 / 1024 / 1024,
                    'percent': (disk.used / disk.total) * 100
                },
                'network': {
                    'bytes_sent': net_io.bytes_sent,
                    'bytes_recv': net_io.bytes_recv,
                    'packets_sent': net_io.packets_sent,
                    'packets_recv': net_io.packets_recv
                },
                'process': process_info
            }
            
        except Exception as e:
            self.logger.error(f"收集系统统计信息失败: {e}")
            return {
                'timestamp': datetime.now(),
                'error': str(e)
            }
            
    def _save_stats(self, stats: Dict[str, Any]):
        """保存统计信息"""
        self.stats_history.append(stats)
        
        # 限制历史记录数量
        if len(self.stats_history) > self.max_history:
            self.stats_history = self.stats_history[-self.max_history:]
            
    def get_current_stats(self) -> Dict[str, Any]:
        """获取当前统计信息"""
        return self._collect_stats()
        
    def get_stats_history(self, hours: int = 1) -> List[Dict[str, Any]]:
        """获取历史统计信息"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        return [
            stats for stats in self.stats_history
            if stats.get('timestamp', datetime.min) > cutoff_time
        ]
        
    def get_performance_summary(self, hours: int = 1) -> Dict[str, Any]:
        """获取性能摘要"""
        history = self.get_stats_history(hours)
        
        if not history:
            return {}
            
        try:
            # 计算平均值和峰值
            cpu_values = [s.get('cpu_percent', 0) for s in history if 'cpu_percent' in s]
            memory_values = [s.get('memory', {}).get('percent', 0) for s in history if 'memory' in s]
            process_cpu = [s.get('process', {}).get('cpu_percent', 0) for s in history if 'process' in s]
            process_memory = [s.get('process', {}).get('memory_mb', 0) for s in history if 'process' in s]
            
            return {
                'period_hours': hours,
                'data_points': len(history),
                'system': {
                    'cpu_avg': sum(cpu_values) / len(cpu_values) if cpu_values else 0,
                    'cpu_max': max(cpu_values) if cpu_values else 0,
                    'memory_avg': sum(memory_values) / len(memory_values) if memory_values else 0,
                    'memory_max': max(memory_values) if memory_values else 0
                },
                'process': {
                    'cpu_avg': sum(process_cpu) / len(process_cpu) if process_cpu else 0,
                    'cpu_max': max(process_cpu) if process_cpu else 0,
                    'memory_avg_mb': sum(process_memory) / len(process_memory) if process_memory else 0,
                    'memory_max_mb': max(process_memory) if process_memory else 0
                },
                'latest_stats': history[-1] if history else {}
            }
            
        except Exception as e:
            self.logger.error(f"计算性能摘要失败: {e}")
            return {'error': str(e)}
            
    def check_system_health(self) -> Dict[str, Any]:
        """检查系统健康状态"""
        current_stats = self.get_current_stats()
        
        if 'error' in current_stats:
            return {
                'status': 'ERROR',
                'message': current_stats['error']
            }
            
        warnings = []
        
        # 检查CPU使用率
        cpu_percent = current_stats.get('cpu_percent', 0)
        if cpu_percent > 90:
            warnings.append(f"CPU使用率过高: {cpu_percent:.1f}%")
        elif cpu_percent > 70:
            warnings.append(f"CPU使用率较高: {cpu_percent:.1f}%")
            
        # 检查内存使用率
        memory_percent = current_stats.get('memory', {}).get('percent', 0)
        if memory_percent > 90:
            warnings.append(f"内存使用率过高: {memory_percent:.1f}%")
        elif memory_percent > 80:
            warnings.append(f"内存使用率较高: {memory_percent:.1f}%")
            
        # 检查磁盘使用率
        disk_percent = current_stats.get('disk', {}).get('percent', 0)
        if disk_percent > 95:
            warnings.append(f"磁盘使用率过高: {disk_percent:.1f}%")
        elif disk_percent > 85:
            warnings.append(f"磁盘使用率较高: {disk_percent:.1f}%")
            
        # 检查进程资源使用
        process_memory = current_stats.get('process', {}).get('memory_mb', 0)
        if process_memory > 1000:  # 1GB
            warnings.append(f"进程内存使用较高: {process_memory:.1f}MB")
            
        # 确定整体状态
        if not warnings:
            status = 'HEALTHY'
            message = '系统运行正常'
        elif len(warnings) <= 2:
            status = 'WARNING'
            message = f"发现 {len(warnings)} 个警告"
        else:
            status = 'CRITICAL'
            message = f"发现 {len(warnings)} 个严重问题"
            
        return {
            'status': status,
            'message': message,
            'warnings': warnings,
            'stats': current_stats,
            'timestamp': datetime.now()
        }


# 全局系统监控实例
system_monitor = SystemMonitor()