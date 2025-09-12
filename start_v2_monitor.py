#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V2系统启动脚本 - 支持从项目根目录启动
"""

import os
import sys
import subprocess

def main():
    """启动V2系统"""
    # 获取当前脚本所在目录（项目根目录）
    root_dir = os.path.dirname(os.path.abspath(__file__))
    v2_system_dir = os.path.join(root_dir, 'v2_system')
    
    # 检查v2_system目录是否存在
    if not os.path.exists(v2_system_dir):
        print(f"错误: V2系统目录不存在: {v2_system_dir}")
        sys.exit(1)
    
    # 检查option_monitor_v2.py是否存在
    v2_script = os.path.join(v2_system_dir, 'option_monitor_v2.py')
    if not os.path.exists(v2_script):
        print(f"错误: V2系统主脚本不存在: {v2_script}")
        sys.exit(1)
    
    print(f"从根目录启动V2系统...")
    print(f"项目根目录: {root_dir}")
    print(f"V2系统目录: {v2_system_dir}")
    
    # 传递所有命令行参数给V2系统
    args = sys.argv[1:]  # 去掉脚本名称
    
    try:
        # 切换到v2_system目录并执行
        os.chdir(v2_system_dir)
        cmd = [sys.executable, 'option_monitor_v2.py'] + args
        print(f"执行命令: {' '.join(cmd)}")
        print(f"工作目录: {os.getcwd()}")
        print("-" * 50)
        
        # 执行V2系统
        result = subprocess.run(cmd, cwd=v2_system_dir)
        sys.exit(result.returncode)
        
    except KeyboardInterrupt:
        print("\n用户中断，退出V2系统")
        sys.exit(0)
    except Exception as e:
        print(f"启动V2系统时发生错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()