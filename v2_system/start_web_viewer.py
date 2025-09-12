#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V2系统数据库浏览器启动脚本
"""

import os
import sys
import subprocess
import webbrowser
import time
from threading import Timer

def check_dependencies():
    """检查依赖包"""
    try:
        import flask
        print("✓ Flask已安装")
        return True
    except ImportError:
        print("✗ Flask未安装，正在安装...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'flask', 'pandas'])
            print("✓ 依赖包安装完成")
            return True
        except subprocess.CalledProcessError:
            print("✗ 依赖包安装失败，请手动安装: pip install flask pandas")
            return False

def open_browser():
    """延迟打开浏览器"""
    time.sleep(2)  # 等待服务器启动
    webbrowser.open('http://localhost:5001')

def main():
    """主函数"""
    print("=" * 50)
    print("V2期权监控系统 - 数据库浏览器")
    print("=" * 50)
    
    # 检查依赖
    if not check_dependencies():
        return
    
    # 检查数据库文件
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, 'data', 'v2_options.db')
    
    if not os.path.exists(db_path):
        print(f"⚠️  数据库文件不存在: {db_path}")
        print("请先运行V2监控系统生成数据")
    else:
        print(f"✓ 数据库文件: {db_path}")
    
    # 启动Web服务器
    print("\n启动Web服务器...")
    print("访问地址: http://localhost:5001")
    print("按 Ctrl+C 停止服务器")
    print("-" * 50)
    
    # 延迟打开浏览器
    Timer(2.0, open_browser).start()
    
    # 启动Flask应用
    try:
        from .web_viewer import app
        app.run(debug=False, host='0.0.0.0', port=5001)
    except KeyboardInterrupt:
        print("\n服务器已停止")
    except ImportError:
        # 如果相对导入失败，尝试直接导入
        try:
            import web_viewer
            web_viewer.app.run(debug=False, host='0.0.0.0', port=5001)
        except Exception as e:
            print(f"启动失败: {e}")
    except Exception as e:
        print(f"启动失败: {e}")

if __name__ == '__main__':
    main()