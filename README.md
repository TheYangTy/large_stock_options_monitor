# 港股期权大单监控系统 📈

[![GitHub stars](https://img.shields.io/github/stars/altenli/large_stock_options_monitor?style=flat-square)](https://github.com/altenli/large_stock_options_monitor/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/altenli/large_stock_options_monitor?style=flat-square)](https://github.com/altenli/large_stock_options_monitor/network)
[![Python Version](https://img.shields.io/badge/python-3.11+-blue?style=flat-square)](https://www.python.org/)

基于 Futu OpenD 的港股期权大单实时监控系统，支持企微机器人推送、交易量变化检测和智能分析。

🎯 把压箱底的好东西分享出来，希望各位大佬赚钱后赏个鸡腿🍗，谢谢！

**联系方式**：WX: `altenli` | 支持付费咨询&部署

---

## 📋 目录

- [功能特点](#-功能特点)
- [技术架构](#-技术架构)
- [系统要求](#-系统要求)
- [快速开始](#-快速开始)
- [配置说明](#️-配置说明)
- [企微机器人设置](#-企微机器人设置)
- [使用方法](#-使用方法)
- [Web界面](#-web界面)
- [运行截图](#-运行截图)
- [数据存储](#-数据存储)
- [注意事项](#️-注意事项)
- [常见问题](#-常见问题)
- [贡献指南](#-贡献指南)
- [赞助支持](#-赞助支持)

---

## 🚀 功能特点

### 核心功能
- **🔍 实时监控**：自动监控指定港股的期权大单交易
- **🧠 智能分析**：自动识别期权类型(Call/Put)和交易方向(买入/卖出)
- **📊 变化检测**：只通知交易量发生变化的大单，避免重复通知
- **📈 股票信息**：显示股票名称和实时价格，更加直观

### 通知系统
- **🤖 企微机器人**：支持企业微信机器人推送
- **💻 系统通知**：Mac系统原生通知
- **🌐 Web界面**：实时数据展示和监控面板

### 数据管理
- **📋 汇总报告**：自动生成交易汇总报告
- **⏰ 定时刷新**：可配置的数据刷新间隔（默认5分钟）
- **💾 数据缓存**：股价缓存机制，优化API性能
- **📝 历史记录**：完整的交易历史数据存储

---

## 🏗️ 技术架构

- **编程语言**：Python 3.11+
- **数据接口**：Futu OpenD API
- **Web框架**：Flask
- **数据存储**：JSON + CSV
- **通知系统**：企业微信 Webhook API
- **前端技术**：HTML5 + CSS3 + JavaScript

---

## 📊 系统要求

### 软件要求
- **Python**: 3.11 或更高版本
- **Futu OpenD**: 最新版本
- **操作系统**: Windows / macOS / Linux

### 硬件要求
- **内存**: 最少 2GB RAM
- **存储**: 至少 100MB 可用空间
- **网络**: 稳定的互联网连接

### 账户要求
- 富途证券账户（用于 OpenD 连接）
- 企业微信账户（可选，用于通知推送）

---

## 🚀 快速开始

### 1. 克隆项目
```bash
git clone https://github.com/altenli/large_stock_options_monitor.git
cd large_stock_options_monitor
```

### 2. 创建虚拟环境
```bash
# 使用 conda（推荐）
conda create -n stock_options_env python=3.11
conda activate stock_options_env

# 或使用 venv
python -m venv stock_options_env
source stock_options_env/bin/activate  # Linux/macOS
# stock_options_env\Scripts\activate   # Windows
```

### 3. 安装依赖
```bash
pip install -r requirements.txt
```

### 4. 配置系统
```bash
# 复制配置文件模板
cp config.py.example config.py

# 编辑配置文件
nano config.py  # 或使用其他编辑器
```

### 5. 启动 Futu OpenD
确保 Futu OpenD 已正确安装并运行在 `127.0.0.1:11111`

### 6. 运行监控程序
```bash
# 持续监控模式
python option_monitor.py

# 单次运行模式（测试用）
python option_monitor.py --once
```

---

## ⚙️ 配置说明

所有配置都在 `config.py` 文件中，从 `config.py.example` 复制并修改：

### 核心配置

#### Futu OpenD 连接
```python
FUTU_CONFIG = {
    'host': '127.0.0.1',
    'port': 11111,
    'market': 'HK',  # 港股市场
}
```

#### 监控股票列表
```python
MONITOR_STOCKS = [
    'HK.00700',  # 腾讯控股
    'HK.09988',  # 阿里巴巴
    'HK.03690',  # 美团
    # 添加更多股票代码
]
```

#### 期权过滤条件
```python
OPTION_FILTER = {
    'min_volume': 100,        # 最小成交量（手）
    'min_turnover': 50000,    # 最小成交额（港币）
    'min_premium': 1000,      # 最小权利金
    'price_range': (0.01, 50), # 价格范围
    'show_all_big_options': False,  # 是否显示所有大单
}
```

#### 监控时间设置
```python
MONITOR_TIME = {
    'interval': 300,      # 监控间隔（秒）
    'lookback_days': 1,   # 回看天数
}
```

### 通知配置
```python
NOTIFICATION = {
    'enable_wework': True,    # 启用企微通知
    'enable_system': True,    # 启用系统通知
    'wework_config': {
        'webhook_url': 'YOUR_WEBHOOK_URL',
        'mentioned_list': [],
        'mentioned_mobile_list': [],
    }
}
```

---

## 🤖 企微机器人设置

### 1. 创建企微机器人
1. 在企业微信群中，点击右上角 `···` 
2. 选择 `添加群机器人`
3. 创建机器人并获取 Webhook URL

### 2. 配置机器人
在 `config.py` 中配置：
```python
'wework_config': {
    'webhook_url': 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxxxxxx',
    'mentioned_list': ['@all'],  # @所有人
    'mentioned_mobile_list': [],  # 或指定手机号
}
```

📖 **详细设置步骤**：请参考 [`WEWORK_SETUP.md`](WEWORK_SETUP.md)

---

## 📱 使用方法

### 基本使用

1. **启动监控程序**
   ```bash
   python option_monitor.py
   ```

2. **启动 Web 界面**（可选）
   ```bash
   python web_dashboard.py
   ```
   访问：http://localhost:5000

3. **测试模式**
   ```bash
   python option_monitor.py --once
   ```

### 命令行参数
- `--once`: 单次运行模式，用于测试配置
- `--config`: 指定配置文件路径
- `--debug`: 启用调试模式

---

## 🌐 Web界面

### 功能特性
- **📊 实时数据**：显示大单期权实时数据
- **🔄 自动刷新**：可配置刷新间隔
- **📈 详细信息**：期权类型、交易方向、股票信息
- **🔥 变化标记**：交易量变化可视化标识
- **🧪 测试功能**：企微机器人测试按钮

### 访问方式
- **本地访问**：http://localhost:5000
- **局域网访问**：配置 `WEB_CONFIG` 中的 host 和 port

---

## 📸 运行截图

### 控制台输出
![启动option_monitor](screenshots/console_output2.png)

![启动Web界面](screenshots/console_output.png)

### Web界面
![Web界面](screenshots/web_dashboard.png)

### 企微机器人通知
![企微机器人通知](screenshots/wework_notification.png)

---

## 💾 数据存储

### 文件结构
```
data/
├── current_big_option.json    # 当前大单期权汇总
├── option_trades.csv          # 历史交易记录
└── cache/                     # 缓存文件

logs/
└── option_monitor.log         # 系统日志

screenshots/                   # 截图文件
```

### 数据格式
- **JSON格式**：实时数据和配置
- **CSV格式**：历史交易记录，便于Excel分析
- **日志格式**：标准Python logging格式

---

## 🔄 交易量变化检测

### 检测机制
- **🔥 新增大单**：交易量有变化的大单
- **⚪ 存量大单**：符合条件但交易量无变化
- **📊 阈值控制**：可配置显示策略

### 配置选项
```python
OPTION_FILTER = {
    'show_all_big_options': False,  # True: 显示所有大单
                                   # False: 仅显示变化大单
}
```

---

## ⚠️ 注意事项

### 运行环境
- ✅ 确保 Futu OpenD 已正确配置并启动
- ✅ 建议在交易时段内运行以获取实时数据
- ✅ 网络连接稳定，避免API调用失败

### 配置建议
- 🔧 根据需要调整筛选条件，避免噪音
- 🔧 合理设置监控间隔，平衡实时性和性能
- 🔧 定期检查日志文件，监控系统状态

### 风险提示
- ⚠️ 本系统仅用于信息监控，不构成投资建议
- ⚠️ 期权交易存在风险，请谨慎决策
- ⚠️ 确保遵守相关法律法规和交易所规则

---

## ❓ 常见问题

### Q: Futu OpenD 连接失败怎么办？
**A**: 检查以下几点：
1. 确认 Futu OpenD 已启动且端口正确（默认11111）
2. 检查防火墙设置
3. 确认富途账户已登录

### Q: 企微机器人不推送消息？
**A**: 请检查：
1. Webhook URL 是否正确
2. 机器人是否被移除群聊
3. 消息频率是否过高被限制

### Q: Web界面无法访问？
**A**: 确认：
1. Flask 应用是否正常启动
2. 端口是否被占用
3. 防火墙设置

### Q: 如何添加新的监控股票？
**A**: 在 `config.py` 的 `MONITOR_STOCKS` 列表中添加股票代码，格式为 `'HK.XXXXX'`

---

## 🤝 贡献指南

欢迎贡献代码和建议！

### 贡献方式
1. **🐛 报告Bug**：提交Issue描述问题
2. **💡 功能建议**：在Discussion中讨论新功能
3. **🔧 代码贡献**：Fork项目并提交Pull Request

### 开发环境
```bash
# 克隆项目
git clone https://github.com/altenli/large_stock_options_monitor.git

# 安装开发依赖
pip install -r requirements-dev.txt

# 运行测试
python -m pytest tests/
```

### 代码规范
- 遵循 PEP 8 代码风格
- 添加适当的注释和文档
- 提交前运行测试确保代码质量

---

## 💖 赞助支持

如果这个项目对您有帮助，欢迎赞助支持！

<details>
<summary>💰 展开查看微信 / 支付宝打赏二维码</summary>

<p align="center">
  <img src="screenshots/wx.png" alt="微信赞赏码" width="300" />
  <img src="screenshots/zfb.png" alt="支付宝收款码" width="300" />
</p>

</details>

### 其他支持方式
- ⭐ 给项目点个Star
- 🔄 分享给更多朋友
- 🐛 报告问题和建议
- 💻 贡献代码

---

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=altenli/large_stock_options_monitor&type=Date)](https://star-history.com/#altenli/large_stock_options_monitor&Date)

---

## 📄 许可证

本项目采用 [MIT 许可证](LICENSE)

---

<div align="center">

**🎯 让期权监控更简单，让投资决策更明智！**

Made with ❤️ by [altenli](https://github.com/altenli)

</div>