#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速启动脚本 - 港股期权大单监控
"""

import os
import sys

def check_dependencies():
    """检查依赖包"""
    required_packages = ['futu', 'pandas', 'flask']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ 缺少以下依赖包:")
        for pkg in missing_packages:
            print(f"   - {pkg}")
        print("\n请运行以下命令安装:")
        print("pip install futu-api pandas flask")
        return False
    
    return True

def create_directories():
    """创建必要的目录"""
    directories = ['logs', 'data', 'templates']
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

def main():
    """主函数"""
    print("🚀 港股期权大单监控系统")
    print("=" * 40)
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 创建目录
    create_directories()
    
    print("✅ 系统检查完成")
    print("\n监控模式说明:")
    print("🔄 双层监控策略:")
    print("   - 快速检查: 每30秒检查活跃期权")
    print("   - 完整汇总: 每小时生成详细报告")
    print("\n使用说明:")
    print("1. 确保 Futu OpenD 客户端已启动")
    print("2. 修改 config.py 中的监控股票列表")
    print("3. 运行监控程序:")
    print("   python option_monitor.py")
    print("4. 或启动Web面板:")
    print("   python web_dashboard.py")
    print("   访问地址: http://localhost:8080")
    print("5. 如需修改间隔，编辑 config.py 中的 MONITOR_TIME")
    print("\n首次使用建议先运行:")
    print("   python test_connection.py")

if __name__ == "__main__":
    main()