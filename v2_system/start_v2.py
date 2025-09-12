#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V2系统启动脚本
"""

import os
import sys
import subprocess
import argparse

def main():
    parser = argparse.ArgumentParser(description='V2系统启动脚本')
    parser.add_argument('--mode', choices=['monitor', 'scan', 'status', 'test', 'web'], 
                       default='monitor', help='运行模式')
    parser.add_argument('--daemon', action='store_true', help='后台运行')
    
    args = parser.parse_args()
    
    # 切换到V2系统目录
    v2_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(v2_dir)
    
    if args.mode == 'web':
        # 启动Web界面
        cmd = [sys.executable, 'web_dashboard_v2.py']
    else:
        # 启动监控程序
        cmd = [sys.executable, 'option_monitor_v2.py', '--mode', args.mode]
    
    if args.daemon:
        # 后台运行
        with open('v2_monitor.log', 'a') as log_file:
            process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=v2_dir
            )
        print(f"V2系统已在后台启动，PID: {process.pid}")
        
        # 保存PID
        with open('v2_monitor.pid', 'w') as pid_file:
            pid_file.write(str(process.pid))
    else:
        # 前台运行
        subprocess.run(cmd, cwd=v2_dir)

if __name__ == '__main__':
    main()