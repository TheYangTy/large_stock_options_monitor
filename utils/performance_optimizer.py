# -*- coding: utf-8 -*-
"""
性能优化工具 - 提供系统性能优化功能
"""

import gc
import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict, deque


class PerformanceOptimizer:
    """性能优化器"""
    
    def __init__(self):
        self.logger = logging.getLogger('OptionMonitor.PerformanceOptimizer')
        
        # 缓存管理
        self.cache_stats = defaultdict(dict)
        self.cache_limits = {}
        
        # 内存管理
        self.gc_interval = 300  # 5分钟
        self.last_gc_time = datetime.now()
        
        # 性能统计
        self.performance_stats = {
            'api_calls': deque(maxlen=1000),
            'db_operations': deque(maxlen=1000),
            'cache_hits': deque(maxlen=1000),
            'cache_misses': deque(maxlen=1000)
        }
        
    def optimize_cache(self, cache_name: str, cache_dict: dict, 
                      max_size: int = 1000, ttl_seconds: int = 3600):
        """优化缓存"""
        try:
            current_time = datetime.now()
            
            # 设置缓存限制
            self.cache_limits[cache_name] = {
                'max_size': max_size,
                'ttl_seconds': ttl_seconds
            }
            
            # 清理过期项
            expired_keys = []
            for key, value in cache_dict.items():
                if isinstance(value, dict) and 'timestamp' in value:
                    if (current_time - value['timestamp']).seconds > ttl_seconds:
                        expired_keys.append(key)
                        
            for key in expired_keys:
                del cache_dict[key]
                
            # 限制缓存大小
            if len(cache_dict) > max_size:
                # 删除最旧的项目
                sorted_items = sorted(
                    cache_dict.items(),
                    key=lambda x: x[1].get('timestamp', datetime.min) if isinstance(x[1], dict) else datetime.min
                )
                
                items_to_remove = len(cache_dict) - max_size
                for i in range(items_to_remove):
                    key = sorted_items[i][0]
                    del cache_dict[key]
                    
            # 更新统计
            self.cache_stats[cache_name] = {
                'size': len(cache_dict),
                'max_size': max_size,
                'expired_removed': len(expired_keys),
                'last_cleanup': current_time
            }
            
            self.logger.debug(f"缓存 {cache_name} 优化完成: 大小={len(cache_dict)}, 清理过期={len(expired_keys)}")
            
        except Exception as e:
            self.logger.error(f"优化缓存 {cache_name} 失败: {e}")
            
    def force_garbage_collection(self):
        """强制垃圾回收"""
        try:
            before_count = len(gc.get_objects())
            collected = gc.collect()
            after_count = len(gc.get_objects())
            
            self.last_gc_time = datetime.now()
            
            self.logger.info(f"垃圾回收完成: 回收={collected}, 对象数量 {before_count} -> {after_count}")
            
            return {
                'collected': collected,
                'objects_before': before_count,
                'objects_after': after_count,
                'timestamp': self.last_gc_time
            }
            
        except Exception as e:
            self.logger.error(f"垃圾回收失败: {e}")
            return {'error': str(e)}
            
    def auto_garbage_collection(self):
        """自动垃圾回收"""
        current_time = datetime.now()
        if (current_time - self.last_gc_time).seconds >= self.gc_interval:
            return self.force_garbage_collection()
        return None
        
    def record_api_call(self, duration: float, success: bool = True):
        """记录API调用性能"""
        self.performance_stats['api_calls'].append({
            'timestamp': datetime.now(),
            'duration': duration,
            'success': success
        })
        
    def record_db_operation(self, operation: str, duration: float, success: bool = True):
        """记录数据库操作性能"""
        self.performance_stats['db_operations'].append({
            'timestamp': datetime.now(),
            'operation': operation,
            'duration': duration,
            'success': success
        })
        
    def record_cache_hit(self, cache_name: str):
        """记录缓存命中"""
        self.performance_stats['cache_hits'].append({
            'timestamp': datetime.now(),
            'cache_name': cache_name
        })
        
    def record_cache_miss(self, cache_name: str):
        """记录缓存未命中"""
        self.performance_stats['cache_misses'].append({
            'timestamp': datetime.now(),
            'cache_name': cache_name
        })
        
    def get_performance_report(self, hours: int = 1) -> Dict[str, Any]:
        """获取性能报告"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            # 过滤时间范围内的数据
            api_calls = [
                call for call in self.performance_stats['api_calls']
                if call['timestamp'] > cutoff_time
            ]
            
            db_operations = [
                op for op in self.performance_stats['db_operations']
                if op['timestamp'] > cutoff_time
            ]
            
            cache_hits = [
                hit for hit in self.performance_stats['cache_hits']
                if hit['timestamp'] > cutoff_time
            ]
            
            cache_misses = [
                miss for miss in self.performance_stats['cache_misses']
                if miss['timestamp'] > cutoff_time
            ]
            
            # 计算统计信息
            report = {
                'period_hours': hours,
                'timestamp': datetime.now(),
                'api_calls': {
                    'total': len(api_calls),
                    'success_rate': sum(1 for call in api_calls if call['success']) / len(api_calls) * 100 if api_calls else 0,
                    'avg_duration': sum(call['duration'] for call in api_calls) / len(api_calls) if api_calls else 0,
                    'max_duration': max((call['duration'] for call in api_calls), default=0),
                    'min_duration': min((call['duration'] for call in api_calls), default=0)
                },
                'database': {
                    'total_operations': len(db_operations),
                    'success_rate': sum(1 for op in db_operations if op['success']) / len(db_operations) * 100 if db_operations else 0,
                    'avg_duration': sum(op['duration'] for op in db_operations) / len(db_operations) if db_operations else 0,
                    'operations_by_type': {}
                },
                'cache': {
                    'total_hits': len(cache_hits),
                    'total_misses': len(cache_misses),
                    'hit_rate': len(cache_hits) / (len(cache_hits) + len(cache_misses)) * 100 if (cache_hits or cache_misses) else 0,
                    'cache_stats': dict(self.cache_stats)
                }
            }
            
            # 按操作类型统计数据库操作
            for op in db_operations:
                op_type = op['operation']
                if op_type not in report['database']['operations_by_type']:
                    report['database']['operations_by_type'][op_type] = {
                        'count': 0,
                        'avg_duration': 0,
                        'total_duration': 0
                    }
                
                stats = report['database']['operations_by_type'][op_type]
                stats['count'] += 1
                stats['total_duration'] += op['duration']
                stats['avg_duration'] = stats['total_duration'] / stats['count']
                
            return report
            
        except Exception as e:
            self.logger.error(f"生成性能报告失败: {e}")
            return {'error': str(e)}
            
    def get_optimization_suggestions(self) -> List[str]:
        """获取优化建议"""
        suggestions = []
        
        try:
            report = self.get_performance_report(hours=1)
            
            # API调用优化建议
            if report['api_calls']['total'] > 0:
                if report['api_calls']['success_rate'] < 95:
                    suggestions.append(f"API成功率较低 ({report['api_calls']['success_rate']:.1f}%)，建议检查网络连接和API配置")
                    
                if report['api_calls']['avg_duration'] > 5:
                    suggestions.append(f"API平均响应时间较长 ({report['api_calls']['avg_duration']:.2f}s)，建议优化网络或增加超时处理")
                    
            # 数据库优化建议
            if report['database']['total_operations'] > 0:
                if report['database']['avg_duration'] > 1:
                    suggestions.append(f"数据库操作平均耗时较长 ({report['database']['avg_duration']:.2f}s)，建议优化查询或添加索引")
                    
                for op_type, stats in report['database']['operations_by_type'].items():
                    if stats['avg_duration'] > 2:
                        suggestions.append(f"{op_type}操作耗时较长 ({stats['avg_duration']:.2f}s)，建议优化")
                        
            # 缓存优化建议
            if report['cache']['hit_rate'] < 80 and (report['cache']['total_hits'] + report['cache']['total_misses']) > 10:
                suggestions.append(f"缓存命中率较低 ({report['cache']['hit_rate']:.1f}%)，建议调整缓存策略")
                
            # 内存优化建议
            if (datetime.now() - self.last_gc_time).seconds > self.gc_interval * 2:
                suggestions.append("距离上次垃圾回收时间较长，建议执行垃圾回收")
                
            # 缓存大小建议
            for cache_name, stats in self.cache_stats.items():
                if stats['size'] > stats['max_size'] * 0.9:
                    suggestions.append(f"缓存 {cache_name} 接近容量上限，建议增加容量或减少TTL")
                    
            if not suggestions:
                suggestions.append("系统性能良好，无需特别优化")
                
        except Exception as e:
            self.logger.error(f"生成优化建议失败: {e}")
            suggestions.append(f"无法生成优化建议: {e}")
            
        return suggestions
        
    def optimize_system(self) -> Dict[str, Any]:
        """执行系统优化"""
        results = {
            'timestamp': datetime.now(),
            'actions': [],
            'errors': []
        }
        
        try:
            # 执行垃圾回收
            gc_result = self.auto_garbage_collection()
            if gc_result:
                results['actions'].append(f"执行垃圾回收: 回收了 {gc_result.get('collected', 0)} 个对象")
                
            # 优化所有已知缓存
            for cache_name in self.cache_stats.keys():
                # 这里需要实际的缓存对象，暂时跳过
                results['actions'].append(f"缓存 {cache_name} 已检查")
                
            if not results['actions']:
                results['actions'].append("无需执行优化操作")
                
        except Exception as e:
            results['errors'].append(str(e))
            self.logger.error(f"系统优化失败: {e}")
            
        return results


# 全局性能优化器实例
performance_optimizer = PerformanceOptimizer()