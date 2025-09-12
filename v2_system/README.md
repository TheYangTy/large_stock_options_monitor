# 🚀 V2 港股期权大单监控系统

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.8%2B-green.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen.svg)]()

> 🎯 **专业级港股期权大单实时监控系统** - 基于富途 API 的高性能期权交易监控解决方案

## ✨ 核心特性

### 🔥 **实时监控**
- 🚨 **毫秒级响应** - 实时捕获期权大单交易
- 📊 **智能筛选** - 可配置的成交量、成交额阈值
- 🎯 **精准识别** - 自动识别 Call/Put 期权类型
- ⚡ **高效处理** - 支持数百只期权同时监控

### 📈 **数据分析**
- 📋 **分类统计** - 按股票代码和期权类型（Put/Call）分别统计
- 🔍 **变化量追踪** - 精确计算与上一条记录的成交量差值
- 📊 **多维度排行** - 成交额、交易笔数、成交量等多重排序
- 📅 **历史数据** - 完整的交易历史记录和趋势分析

### 🔔 **智能通知**
- 📱 **多渠道推送** - 企业微信、Mac 系统通知、控制台输出
- 📊 **汇总报告** - 统一发送所有期权变化的综合报告
- ⏰ **防骚扰机制** - 智能通知间隔控制，避免频繁推送
- 🎨 **美观格式** - 结构化的通知内容，易于阅读

### 🌐 **Web 界面**
- 💻 **现代化 UI** - 基于 Bootstrap 5 的响应式设计
- 📊 **实时数据** - 股票统计、交易记录实时展示
- 🔍 **高级筛选** - 支持股票代码、期权代码、日期范围筛选
- 📄 **分页浏览** - 高效的大数据量分页显示

### 🗄️ **数据管理**
- 💾 **SQLite 数据库** - 轻量级、高性能的本地数据存储
- 🔄 **数据同步** - 股票信息与交易记录分离存储，避免冗余
- 🛠️ **数据修复** - 内置数据修正工具，确保数据准确性
- 📦 **自动备份** - 可配置的数据备份机制

## 🏗️ 系统架构

```
V2 港股期权监控系统
├── 🎯 核心监控模块 (option_monitor_v2.py)
│   ├── 富途 API 连接管理
│   ├── 期权数据实时获取
│   ├── 大单识别与处理
│   └── 智能重连机制
├── 📊 数据处理层 (utils/)
│   ├── 数据库管理 (database_manager.py)
│   ├── 大单处理器 (big_options_processor.py)
│   ├── 通知系统 (notifier.py)
│   └── 数据处理器 (data_handler.py)
├── 🌐 Web 服务 (web_viewer.py)
│   ├── Flask Web 应用
│   ├── RESTful API 接口
│   └── 响应式前端界面
└── 🛠️ 工具集
    ├── 数据修正工具 (fix_volume_diff.py)
    ├── 配置管理 (config.py)
    └── 日志系统 (logger.py)
```

## 🚀 快速开始

### 📋 环境要求

- **Python**: 3.8+
- **操作系统**: Windows / macOS / Linux
- **内存**: 建议 2GB+
- **存储**: 建议 1GB+ 可用空间

### 📦 安装依赖

```bash
# 克隆项目
git clone <repository-url>
cd large_stock_options_monitor/v2_system
# 初始化配置文件
cp config.py.sample config.py

# 安装 Python 依赖
pip install -r requirements.txt

# 或手动安装核心依赖
pip install futu-api pandas numpy flask requests
```

### ⚙️ 配置设置

1. **编辑配置文件** `config.py`:

```python
# 富途 API 配置
FUTU_CONFIG = {
    'host': '127.0.0.1',    # 富途牛牛客户端地址
    'port': 11111,          # API 端口
    'market': 'HK'          # 市场代码
}

# 大单监控阈值
BIG_TRADE_CONFIG = {
    'min_volume_threshold': 100,      # 最小成交量(张)
    'min_turnover_threshold': 500000, # 最小成交额(港币)
    'notification_cooldown': 300      # 通知冷却时间(秒)
}

# 通知配置
NOTIFICATION = {
    'enable_wework_bot': True,        # 企业微信通知
    'enable_mac_notification': True,  # Mac 系统通知
    'wework_webhook': 'YOUR_WEBHOOK_URL'
}
```

2. **启动富途牛牛客户端** 并开启 API 功能

### 🎯 运行系统

```bash
# 启动主监控程序
python option_monitor_v2.py

# 启动 Web 界面 (新终端)
python web_viewer.py
```

访问 Web 界面: http://localhost:5001

## 📊 功能详解

### 🔍 **实时监控**

系统会自动监控配置的港股期权，当检测到符合条件的大单交易时：

1. **数据采集**: 从富途 API 获取实时期权数据
2. **智能筛选**: 根据成交量、成交额阈值过滤
3. **变化计算**: 精确计算与上一条记录的差值
4. **数据存储**: 保存到 SQLite 数据库
5. **实时通知**: 发送到配置的通知渠道

### 📈 **统计分析**

- **按股票统计**: 每个股票的 Put/Call 期权分别统计
- **排行榜**: 成交额、交易笔数、成交量等多维度排序
- **历史趋势**: 完整的交易历史和变化趋势
- **实时更新**: 数据实时刷新，确保信息准确性

### 🔔 **通知系统**

**汇总报告格式**:
```
📊 期权监控汇总报告
⏰ 时间: 2025-09-12 16:00:00
📈 总交易: 50 笔 (新增: 15 笔，符合通知条件: 8 笔)
💰 总金额: 5,000,000 港币 (新增: 2,000,000 港币)

📋 新增大单统计:
• 腾讯控股 (HK.00700): 5笔, 1,500,000港币 (股价: 320.50)
  1. HK.TCH250930C330000: Call, 2.500×1000张, +500张, 125.0万
  2. HK.TCH250930P310000: Put, 1.800×800张, +300张, 72.0万
```

## 🛠️ 高级功能

### 📊 **数据修正工具**

```bash
# 修正历史数据的变化量计算和股票名称
python fix_volume_diff.py
```

功能包括:
- ✅ 重新计算所有记录的变化量（与上一条记录比较）
- ✅ 从 stock_info 表补充缺失的股票名称
- ✅ 批量处理，安全高效
- ✅ 自动验证修正结果

### 🔧 **配置优化**

**监控股票配置**:
```python
MONITORED_STOCKS = [
    'HK.00700',  # 腾讯控股
    'HK.09988',  # 阿里巴巴
    'HK.03690',  # 美团
    # ... 更多股票
]
```

**期权过滤配置**:
```python
OPTION_FILTERS = {
    'default': {
        'min_volume': 10,
        'min_turnover': 200000,
        'min_days_to_expiry': 1,
        'max_days_to_expiry': 365
    }
}
```

## 📁 项目结构

```
v2_system/
├── 📄 README.md                    # 项目文档
├── ⚙️ config.py                    # 配置文件
├── 🎯 option_monitor_v2.py         # 主监控程序
├── 🌐 web_viewer.py               # Web 界面
├── 🛠️ fix_volume_diff.py          # 数据修正工具
├── 📊 utils/                      # 工具模块
│   ├── 🗄️ database_manager.py     # 数据库管理
│   ├── 📈 big_options_processor.py # 大单处理器
│   ├── 🔔 notifier.py             # 通知系统
│   ├── 📱 mac_notifier.py         # Mac 通知
│   ├── 📋 data_handler.py         # 数据处理
│   └── 📝 logger.py               # 日志系统
├── 🎨 templates/                  # Web 模板
│   ├── 🏠 base.html               # 基础模板
│   ├── 📊 stocks.html             # 股票统计页面
│   └── 📋 trades.html             # 交易记录页面
├── 💾 data/                       # 数据目录
│   └── 🗄️ options_monitor_v2.db   # SQLite 数据库
└── 📝 logs/                       # 日志目录
```

## 🔧 故障排除

### 常见问题

**Q: 富途 API 连接失败**
```
A: 1. 确保富途牛牛客户端已启动
   2. 检查 API 功能是否开启
   3. 验证 config.py 中的 host 和 port 配置
```

**Q: 没有收到通知**
```
A: 1. 检查通知配置是否正确
   2. 验证企业微信 webhook 地址
   3. 确认大单阈值设置是否合理
```

**Q: Web 界面无法访问**
```
A: 1. 确认 web_viewer.py 已启动
   2. 检查端口 5001 是否被占用
   3. 查看控制台错误信息
```

## 🗓 TODO


- [ ] 支持美股期权

## 🤝 贡献指南

我们欢迎社区贡献！请遵循以下步骤：

1. **Fork** 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 **Pull Request**

## 📄 许可证

本项目基于 **Apache License 2.0** 开源协议发布。

```
Copyright 2025 V2 港股期权监控系统

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

详细许可证内容请查看 [LICENSE](LICENSE) 文件。

## 💖 赞助支持

如果这个项目对您有帮助，欢迎支持我们的开发工作！

### 🎯 **为什么需要您的支持？**

- 🔧 **持续开发**: 新功能开发和性能优化
- 🐛 **问题修复**: 及时响应和修复用户反馈的问题  
- 📚 **文档维护**: 保持文档的完整性和准确性
- 🚀 **服务器成本**: 维护演示环境和测试服务器

### 💰 **赞助方式**

#### 🇨🇳 **个人赞助**
<details>
<summary>点击展开二维码</summary>

**微信赞赏码**

![微信赞赏码](screenshots/wx.png)


**支付宝收款码**  

![支付宝收款码](screenshots/zfb.png)

</details>


#### 💎 **企业赞助**
如果您的企业希望成为项目赞助商，请联系我们讨论定制化支持和商业合作。

**联系方式**: liqian115@gmail.com

**联系wx**: altenli

### 🏆 **赞助者名单**

感谢以下赞助者对项目的支持：

| 赞助者 | 金额 | 时间 | 留言 |
|--------|------|------|------|
| 范 | ¥188 | 2025-9 | 期待您的支持！ |

> 💡 **注意**: 赞助完全自愿，项目将始终保持开源免费。您的支持将帮助我们提供更好的服务！

## 📞 联系我们

- **项目主页**: [GitHub 仓库链接](https://github.com/AltenLi/large_stock_options_monitor)
- **问题反馈**: [GitHub Issues 链接](https://github.com/AltenLi/large_stock_options_monitor/issues)
- **技术交流**: ![QQ群/微信群](screenshots/wxqun.jpg)
- **邮箱**: liqian115@gmail.com

## 🙏 致谢

- 感谢 [富途证券](https://www.futunn.com/) 提供的优秀 API 服务
- 感谢所有贡献者和用户的支持与反馈
- 感谢开源社区提供的优秀工具和库

---

<div align="center">

**⭐ 如果这个项目对您有帮助，请给我们一个 Star！⭐**

**🚀 让我们一起打造更好的港股期权监控工具！🚀**

</div>


---

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=altenli/large_stock_options_monitor&type=Date)](https://star-history.com/#altenli/large_stock_options_monitor&Date)
