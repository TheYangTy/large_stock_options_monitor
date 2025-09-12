# 港股期权大单监控系统 V2.0

## 🚀 系统架构优化

### 核心改进

1. **专门的OpenD API后台线程**
   - 独立的API管理器负责所有富途API交互
   - 自动重连和心跳检测
   - 智能订阅管理
   - 实时数据缓存

2. **数据库存储系统**
   - SQLite数据库存储分时期权数据
   - 完整的期权交易历史记录
   - 支持复杂查询和数据分析
   - 自动数据清理和维护

3. **模块化架构**
   - 清晰的职责分离
   - 可扩展的组件设计
   - 更好的错误处理和日志记录
   - 回调机制支持

## 📁 目录结构

```
large_stock_options_monitor/
├── core/                          # 核心模块
│   ├── __init__.py
│   ├── api_manager.py            # API管理器
│   ├── database_manager.py       # 数据库管理器
│   ├── option_analyzer.py        # 期权分析器
│   └── option_monitor_v2.py      # 主监控器V2
├── utils/                         # 工具模块
│   ├── notifier.py               # 通知模块
│   ├── logger.py                 # 日志模块
│   └── ...
├── data/                          # 数据目录
│   ├── options_monitor.db        # SQLite数据库
│   ├── stock_prices.json         # 股价缓存
│   └── ...
├── templates/                     # Web模板
│   └── dashboard_v2.html         # V2仪表板
├── config.py                      # 配置文件
├── option_monitor.py             # 原版监控器
├── option_monitor_v2.py          # 新版监控器入口
├── web_dashboard_v2.py           # V2 Web仪表板
├── requirements_v2.txt           # 新版依赖
└── README_V2.md                  # V2文档
```

## ✨ 新版特性

### 1. API管理器 (APIManager)

- **后台线程运行**: 独立线程处理所有API交互
- **自动重连**: 检测连接断开并自动重连
- **智能订阅**: 动态管理股票和期权订阅
- **数据缓存**: 实时缓存股票报价和期权交易
- **回调机制**: 支持注册回调函数处理推送数据

```python
# 使用示例
from core import APIManager

api_manager = APIManager()
api_manager.start()

# 注册回调
api_manager.register_stock_quote_callback(on_stock_quote)
api_manager.register_option_trade_callback(on_option_trade)

# 获取数据
quote = api_manager.get_stock_quote('HK.00700')
trades = api_manager.get_option_trades('HK.00700C250929102500')
```

### 2. 数据库管理器 (DatabaseManager)

- **完整数据存储**: 存储期权交易的所有详细信息
- **历史数据查询**: 支持按时间、股票、期权等多维度查询
- **统计分析**: 内置统计功能，支持数据分析
- **数据导出**: 支持CSV、Excel、JSON格式导出

```python
# 使用示例
from core import DatabaseManager

db_manager = DatabaseManager()

# 保存期权记录
record_id = db_manager.save_option_record(option_record)

# 查询大单交易
big_trades = db_manager.get_big_trades(hours=24)

# 获取统计信息
stats = db_manager.get_statistics(hours=24)

# 导出数据
db_manager.export_data(start_date, end_date, 'output.csv')
```

### 3. 期权分析器 (OptionAnalyzer)

- **Greeks计算**: 自动计算Delta、Gamma、Theta、Vega
- **隐含波动率**: 使用Black-Scholes模型估算隐含波动率
- **价值分析**: 计算内在价值、时间价值、价值状态
- **风险评估**: 多维度风险等级评估
- **重要性评分**: 智能评估交易重要性

```python
# 使用示例
from core import OptionAnalyzer

analyzer = OptionAnalyzer()

# 分析期权交易
analysis = analyzer.analyze_option_trade(trade, stock_quote)

# 获取分析结果
print(f"期权类型: {analysis['option_type']}")
print(f"执行价格: {analysis['strike_price']}")
print(f"隐含波动率: {analysis['implied_volatility']:.2f}%")
print(f"重要性分数: {analysis['importance_score']}")
```

### 4. 优化版监控器 (OptionMonitorV2)

- **事件驱动**: 基于回调机制的实时处理
- **智能分析**: 自动分析和分类期权交易
- **多维通知**: 支持多种通知方式
- **状态监控**: 实时监控系统运行状态

## 🗄️ 数据库结构

### 期权记录表 (option_records)

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | INTEGER | 主键 |
| timestamp | DATETIME | 交易时间 |
| stock_code | TEXT | 股票代码 |
| stock_name | TEXT | 股票名称 |
| stock_price | REAL | 股票价格 |
| option_code | TEXT | 期权代码 |
| option_type | TEXT | 期权类型 (Call/Put) |
| strike_price | REAL | 执行价格 |
| expiry_date | TEXT | 到期日 |
| option_price | REAL | 期权价格 |
| volume | INTEGER | 成交量 |
| turnover | REAL | 成交额 |
| direction | TEXT | 买卖方向 |
| implied_volatility | REAL | 隐含波动率 |
| delta | REAL | Delta值 |
| gamma | REAL | Gamma值 |
| theta | REAL | Theta值 |
| vega | REAL | Vega值 |
| moneyness | TEXT | 价值状态 (ITM/ATM/OTM) |
| days_to_expiry | INTEGER | 到期天数 |
| is_big_trade | BOOLEAN | 是否大单 |
| risk_level | TEXT | 风险等级 |
| importance_score | INTEGER | 重要性分数 |

### 股票价格表 (stock_prices)

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | INTEGER | 主键 |
| timestamp | DATETIME | 时间戳 |
| stock_code | TEXT | 股票代码 |
| stock_name | TEXT | 股票名称 |
| price | REAL | 股票价格 |
| volume | INTEGER | 成交量 |
| turnover | REAL | 成交额 |
| change_rate | REAL | 涨跌幅 |

## 🚀 安装和使用

### 1. 安装依赖

```bash
pip install -r requirements_v2.txt
```

### 2. 配置系统

复制并编辑配置文件：

```bash
cp config.py.example config.py
# 编辑config.py，填入你的富途OpenD配置
```

### 3. 启动监控

```bash
# 启动V2版本
python option_monitor_v2.py

# 启动Web仪表板
python web_dashboard_v2.py

# 或者启动原版本
python option_monitor.py
```

### 4. 查看状态

系统启动后会自动：
- 连接富途OpenD
- 订阅监控股票
- 开始实时监控期权交易
- 发送大单通知

访问 http://localhost:8288 查看Web仪表板

## 🔧 API接口

### 获取监控状态

```python
from core import OptionMonitorV2

monitor = OptionMonitorV2()
status = monitor.get_monitoring_status()
print(status)
```

### 强制执行分析

```python
monitor.force_analysis()
```

### 导出数据

```python
from datetime import datetime, timedelta

start_date = datetime.now() - timedelta(days=7)
end_date = datetime.now()
monitor.export_data(start_date, end_date, 'export.csv')
```

## ⚡ 性能优化

1. **并发处理**: API交互和数据处理在不同线程中进行
2. **智能缓存**: 减少重复API调用
3. **批量操作**: 数据库批量插入和查询
4. **内存管理**: 自动清理过期数据
5. **连接池**: 数据库连接复用

## 📊 监控指标

- API连接状态
- 订阅股票数量
- 缓存数据量
- 处理交易数量
- 数据库记录数
- 系统响应时间

## 🔍 故障排除

### 常见问题

1. **API连接失败**
   - 检查富途OpenD是否启动
   - 确认配置文件中的host和port
   - 检查网络连接

2. **数据库错误**
   - 确保data目录有写权限
   - 检查磁盘空间
   - 查看错误日志

3. **通知发送失败**
   - 检查通知配置
   - 确认网络连接
   - 查看通知日志

### 日志文件

- 主日志: `logs/option_monitor.log`
- API日志: 包含在主日志中
- 数据库日志: 包含在主日志中

## 📈 版本对比

| 特性 | V1.0 | V2.0 |
|------|------|------|
| API管理 | 同步调用 | 异步后台线程 |
| 数据存储 | JSON/CSV | SQLite数据库 |
| 数据分析 | 基础分析 | 完整Greeks计算 |
| 错误处理 | 基础重试 | 智能重连 |
| 性能 | 中等 | 高性能 |
| 扩展性 | 有限 | 高度可扩展 |
| Web界面 | 基础 | 现代化响应式 |

## 🛠️ 开发指南

### 添加新的分析指标

```python
# 在 OptionAnalyzer 中添加新方法
def calculate_custom_metric(self, trade_data):
    # 自定义计算逻辑
    return result

# 在 analyze_option_trade 中调用
analysis['custom_metric'] = self.calculate_custom_metric(trade)
```

### 添加新的通知方式

```python
# 继承 Notifier 类
class CustomNotifier(Notifier):
    def send_notification(self, trade_info):
        # 自定义通知逻辑
        pass

# 在监控器中使用
monitor.notifier = CustomNotifier()
```

### 扩展数据库结构

```python
# 在 DatabaseManager 中添加新表
def create_custom_table(self):
    query = """
    CREATE TABLE IF NOT EXISTS custom_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        data TEXT
    )
    """
    self.execute_query(query)
```

## 🔮 未来规划

1. **机器学习集成**: 使用ML模型预测期权价格走势
2. **实时图表**: 集成TradingView图表组件
3. **移动端应用**: 开发iOS/Android应用
4. **云部署**: 支持Docker容器化部署
5. **多市场支持**: 扩展到美股、A股期权
6. **高频交易**: 支持毫秒级数据处理
7. **风控系统**: 集成风险管理模块

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 📞 支持

如有问题或建议，请：
1. 提交 [Issue](https://github.com/your-repo/issues)
2. 发送邮件到 support@example.com
3. 加入QQ群: 123456789

---

**注意**: 本系统仅供学习和研究使用，投资有风险，请谨慎决策。