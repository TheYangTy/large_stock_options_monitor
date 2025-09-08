#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速启动脚本 - 港股期权大单监控
"""

import os
import sys

def check_dependencies():
    """检查依赖包"""
    required_packages = ['futu', 'pandas', 'flask', 'requests']
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
        print("pip install futu-api pandas flask requests")
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
    print("\n📊 当前监控股票 (21只):")
    print("   - 科技股: 腾讯控股、阿里巴巴、美团、小米、京东、百度、快手")
    print("   - 金融股: 中国平安、汇丰控股、建设银行、友邦保险、香港交易所")
    print("   - 新能源汽车: 比亚迪、理想汽车、小鹏汽车、蔚来")
    print("   - 其他: 中芯国际、安踏体育、药明生物、吉利汽车")
    print("\n🔄 监控模式说明:")
    print("   - 实时监控: 每1分钟检查大单期权交易")
    print("   - 智能筛选: 根据股票特性设置不同阈值")
    print("   - 多重通知: 控制台 + Mac通知 + 企微机器人")
    print("\n🚀 使用说明:")
    print("1. 确保 Futu OpenD 客户端已启动 (端口11111)")
    print("2. 启用企微通知:")
    print("   export ENABLE_WEWORK_BOT=1")
    print("3. 运行监控程序:")
    print("   python option_monitor.py")
    print("4. 启动Web监控面板:")
    print("   python web_dashboard.py")
    print("   访问地址: http://localhost:8288")
    print("5. 修改监控股票: 编辑 config.py 中的 MONITOR_STOCKS")
    print("\n✨ 新功能特性:")
    print("   - 期权类型准确识别 (Call/Put)")
    print("   - 成交额占比分析")
    print("   - 股票筛选多选框")
    print("   - 按股票分组排序显示")

if __name__ == "__main__":
    main()