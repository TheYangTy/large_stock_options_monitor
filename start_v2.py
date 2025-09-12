#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
港股期权大单监控系统 V2.0 - 启动脚本
提供多种启动方式
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

def check_dependencies():
    """检查依赖"""
    try:
        import futu as ft
        import pandas as pd
        import numpy as np
        import scipy
        print("✅ 基础依赖检查通过")
        return True
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("请运行: pip install -r requirements_v2.txt")
        return False

def check_config():
    """检查配置文件"""
    if not os.path.exists('config.py'):
        print("❌ 配置文件不存在")
        print("请复制 config.py.example 到 config.py 并填入配置")
        return False
    
    try:
        import config
        print("✅ 配置文件检查通过")
        return True
    except Exception as e:
        print(f"❌ 配置文件错误: {e}")
        return False

def start_monitor():
    """启动监控器"""
    print("🚀 启动期权监控器 V2.0...")
    try:
        subprocess.run([sys.executable, 'option_monitor_v2.py'])
    except KeyboardInterrupt:
        print("\n⏹️ 监控器已停止")

def start_web():
    """启动Web仪表板"""
    print("🌐 启动Web仪表板...")
    try:
        subprocess.run([sys.executable, 'web_dashboard_v2.py'])
    except KeyboardInterrupt:
        print("\n⏹️ Web仪表板已停止")

def start_both():
    """同时启动监控器和Web仪表板"""
    print("🚀 启动完整系统...")
    import threading
    import time
    
    # 启动监控器线程
    monitor_thread = threading.Thread(target=start_monitor, daemon=True)
    monitor_thread.start()
    
    # 等待一下再启动Web
    time.sleep(2)
    
    # 启动Web仪表板
    start_web()

def main():
    parser = argparse.ArgumentParser(description='港股期权大单监控系统 V2.0')
    parser.add_argument('mode', choices=['monitor', 'web', 'both'], 
                       help='启动模式: monitor(仅监控), web(仅Web), both(完整系统)')
    parser.add_argument('--check', action='store_true', help='仅检查环境')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🎯 港股期权大单监控系统 V2.0")
    print("=" * 60)
    
    # 检查环境
    if not check_dependencies():
        return 1
        
    if not check_config():
        return 1
        
    if args.check:
        print("✅ 环境检查完成，系统可以正常启动")
        return 0
    
    # 启动对应模式
    if args.mode == 'monitor':
        start_monitor()
    elif args.mode == 'web':
        start_web()
    elif args.mode == 'both':
        start_both()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())