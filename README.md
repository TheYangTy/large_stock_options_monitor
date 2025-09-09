# 港股期权大单监控

简洁高效的港股期权大单监控与Web面板展示，支持自动订阅、缓存合并、企业微信通知与可视化筛选。

## 最近更新

- 基础信息独立存储
  - 新增 data/stock_base_info.json 专门保存股票名称等“基本不变字段”
  - 合并策略：仅用非空值更新，避免 API 失败导致名称等被清空
- 价格与缓存
  - get_stock_price 优先用内存缓存；行情失败时回退读取 data/stock_prices.json 的最近报价，统一返回 float
  - stock_prices.json 写入采用统一 dict 结构，包含 price/name/turnover/volume/update_time
- 订阅增强
  - 股票改为同时订阅 QUOTE + SNAPSHOT，确保能拿到成交额/量
  - 订阅后自动校验并对缺失股票进行一次“补订”
  - /api/status 返回 subscribed_stocks 与 missing_subscriptions 便于核查覆盖
- Web 面板
  - 移除“四个汇总格子”与“测试企微推送/强制推送大单”按钮
  - 列表排序：按固定股票顺序分组，组内按成交量(volume)降序、再按成交额(turnover)降序，并加入股票代码作为次级键，保证稳定
  - 成交额占比(%) 着色：占比>0.01% 且 Call 标绿，>0.01% 且 Put 标红，其余标黑
- 成交额缺失补齐
  - 接口端先从缓存补齐，若缺失则调用行情补齐；仍缺时 sleep 10s 后再次读取缓存回填（本次请求可能多等待约10秒）

## 快速开始

1) 安装依赖
- 需要本地 Futu OpenD 正常运行
- Python 依赖（示例）：futu-api、pandas、flask 等

2) 配置
- 复制 config.py.example 为 config.py，并按需填写：
  - FUTU_CONFIG.host/port
  - MONITOR_STOCKS（监控的股票列表）
  - WEB_CONFIG（端口等）
  - NOTIFICATION（按需开启企微机器人等）

3) 启动监控
- python option_monitor.py
- 程序会自动订阅 MONITOR_STOCKS 的 QUOTE+SNAPSHOT，并每分钟执行一次完整大单汇总

4) 启动Web面板
- python web_dashboard.py
- 浏览器访问 http://localhost:<WEB_CONFIG.port>
- /api/status 可查看当前订阅覆盖情况（missing_subscriptions 应为空）

## 接口概览

- GET /api/big_options_summary
  - 返回当前大单期权汇总（按后端顺序已排序）
  - 若存在成交额缺失，会尝试行情补齐并在必要时延迟10秒重试缓存回填
- GET /api/status
  - 返回运行状态、monitored_stocks、subscribed_stocks、missing_subscriptions 等
- GET /api/refresh_big_options
  - 强制从缓存文件刷新一次汇总并更新时间戳

## 数据文件

- data/current_big_option.json：大单汇总缓存
- data/stock_prices.json：正股价格/成交额/成交量等缓存
- data/stock_base_info.json：股票名称等基础信息（仅非空合并）
- data/option_chains.json：期权链缓存（带节流写盘）

## 常见问题

- 名称丢失
  - 基础信息采用“仅非空覆盖”策略，API 返回空不会覆盖名称
- 成交额/成交量为空
  - Web 接口端会尝试行情补齐；仍缺时延迟10秒再次读取缓存回填
- 排序看起来乱
  - 已加入固定股票顺序与稳定键（股票代码）；组内按 volume 再 turnover 降序

## 注意事项

- 不要手动清空 data/stock_base_info.json 与 data/stock_prices.json 的字段键名
- OpenD 需保持连接可用；若断开，程序会尝试重连或回退到缓存价格
- 启用企微推送需在 config.py 中正确配置 NOTIFICATION.wework_config