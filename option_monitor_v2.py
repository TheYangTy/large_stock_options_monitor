#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
港股期权大单监控系统 V2.0 - 主入口文件
优化版本，使用新的架构设计
"""

import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.option_monitor_v2 import main

if __name__ == "__main__":
    main()