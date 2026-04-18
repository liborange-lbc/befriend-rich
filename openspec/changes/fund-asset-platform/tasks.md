## 1. 项目初始化

- [x] 1.1 创建后端项目结构（FastAPI + SQLAlchemy + 目录骨架）
- [x] 1.2 创建前端项目结构（React + TypeScript + Ant Design + ECharts）
- [x] 1.3 配置 Docker Compose（frontend nginx + backend + sqlite volume）
- [x] 1.4 配置后端数据库（SQLAlchemy 引擎、会话管理、Alembic 迁移）
- [x] 1.5 配置后端统一响应格式和异常处理中间件

## 2. 基金管理（fund-management）

- [x] 2.1 创建 Fund ORM 模型（code, name, currency, data_source, fee_rate, is_active）
- [x] 2.2 创建 Fund Pydantic schemas（请求/响应模型）
- [x] 2.3 实现基金 CRUD API（创建、查询列表、查询详情、更新、停用）
- [x] 2.4 实现基金代码唯一性校验
- [x] 2.5 编写基金管理 API 单元测试
- [x] 2.6 实现前端基金管理页面（设置 > 基金管理，表格+表单）

## 3. 分类模型（classification-model）

- [x] 3.1 创建 ClassModel 和 ClassCategory ORM 模型（树形自引用结构）
- [x] 3.2 创建 FundClassMap ORM 模型（基金↔分类映射）
- [x] 3.3 实现分类模型 CRUD API（创建模型、编辑、删除）
- [x] 3.4 实现类别管理 API（创建/编辑/删除类别，树形查询）
- [x] 3.5 实现基金分类映射 API（映射、查询、替换）
- [x] 3.6 编写分类模型 API 单元测试
- [x] 3.7 实现前端分类模型管理页面（设置 > 分类模型，树形编辑器）
- [x] 3.8 实现前端基金分类映射页面（设置 > 基金映射）

## 4. 行情数据（market-data）

- [x] 4.1 定义 DataSourceAdapter 抽象接口
- [x] 4.2 实现 TushareAdapter（获取 A 股/国内基金每日收盘价）
- [x] 4.3 实现 YahooAdapter（获取美股/海外基金每日收盘价）
- [x] 4.4 创建 FundDailyPrice ORM 模型
- [x] 4.5 创建 ExchangeRate ORM 模型
- [x] 4.6 实现汇率获取服务（USD/CNY，通过 Yahoo Finance）
- [x] 4.7 实现行情抓取服务（遍历基金、调用适配器、同日覆盖）
- [x] 4.8 实现历史数据回填 API
- [x] 4.9 配置 APScheduler 每小时抓取任务
- [ ] 4.10 编写行情数据服务单元测试
- [ ] 4.11 实现前端数据源配置页面（设置 > 数据源，Tushare token 等）

## 5. 技术指标分析（technical-analysis）

- [x] 5.1 实现均线计算服务（MA30/60/90/120/180/360）
- [x] 5.2 实现均值偏差计算服务
- [x] 5.3 在行情抓取后自动触发指标计算
- [x] 5.4 实现技术指标查询 API（单基金+时间范围、多基金偏差汇总）
- [x] 5.5 编写技术指标计算单元测试

## 6. 大盘看板（dashboard）

- [x] 6.1 实现看板数据聚合 API（今日概览、基金行情列表、最新偏差数据）
- [x] 6.2 实现前端看板布局（概览卡片 + 基金列表 + 图表 + 热力图 + 提醒）
- [x] 6.3 实现前端 K 线图组件（ECharts，收盘价+均线，dataZoom 时间滑块）
- [x] 6.4 实现前端均值偏差热力图组件（ECharts heatmap）
- [x] 6.5 实现前端策略提醒列表组件
- [x] 6.6 编写看板 Playwright E2E 测试

## 7. 持仓录入与资产管理（portfolio-tracking + asset-report）

- [x] 7.1 创建 PortfolioRecord ORM 模型
- [x] 7.2 创建 PortfolioSnapshot ORM 模型
- [x] 7.3 实现持仓录入 API（单条/批量录入、同基金同日期去重）
- [x] 7.4 实现资产快照自动生成服务（汇率折算、模型分类汇总）
- [x] 7.5 实现持仓历史和快照趋势查询 API
- [x] 7.6 实现 TOP5 持仓查询 API
- [x] 7.7 编写持仓和快照 API 单元测试
- [x] 7.8 实现前端资产管理页面布局（总览 + 饼图 + 趋势图 + TOP5 + 录入入口）
- [x] 7.9 实现前端资产总览卡片组件
- [x] 7.10 实现前端多模型饼图组件（ECharts pie）
- [x] 7.11 实现前端分类趋势图组件（ECharts line，时间滑块）
- [x] 7.12 实现前端 TOP5 持仓榜单组件
- [x] 7.13 实现前端持仓录入弹窗（预填上次数据、批量编辑）
- [x] 7.14 编写资产管理页面 Playwright E2E 测试

## 8. 基金分析页面（technical-analysis 前端）

- [x] 8.1 实现前端基金分析页面（选择基金 → K线+MA+偏差图表）
- [x] 8.2 实现前端多基金对比功能
- [x] 8.3 实现前端时间范围滑块控件
- [ ] 8.4 编写基金分析页面 Playwright E2E 测试

## 9. 回测引擎（backtest-engine）

- [x] 9.1 创建 Strategy ORM 模型
- [x] 9.2 创建 BacktestResult ORM 模型
- [x] 9.3 实现回测引擎核心（基于 pandas，支持定投/条件买卖/止盈止损）
- [x] 9.4 实现回测指标计算（收益率、年化、夏普、最大回撤、波动率、胜率、盈亏比）
- [ ] 9.5 实现基准对比计算
- [x] 9.6 实现回测 API（创建策略、运行回测、查询结果）
- [x] 9.7 编写回测引擎单元测试
- [x] 9.8 实现前端回测页面（策略配置表单 + 运行按钮 + 结果展示）
- [x] 9.9 实现前端净值曲线图（策略 vs 基准）
- [x] 9.10 实现前端回测指标面板和交易明细表
- [ ] 9.11 编写回测页面 Playwright E2E 测试

## 10. 策略提醒（strategy-alert）

- [x] 10.1 实现策略管理 API（保存/编辑/启停/删除策略）
- [x] 10.2 实现提醒条件评估引擎（解析条件表达式、评估当前指标）
- [x] 10.3 实现飞书机器人通知服务（富文本卡片消息）
- [x] 10.4 配置 APScheduler 9/12/14 点策略检查任务
- [x] 10.5 编写策略提醒服务单元测试
- [x] 10.6 实现前端策略管理页面（列表 + 编辑 + 启停开关）
- [ ] 10.7 实现前端飞书机器人配置页面（设置 > 飞书通知）

## 11. 集成与部署

- [x] 11.1 前后端联调，确保所有 API 对接正确
- [x] 11.2 完善 Docker 镜像构建（前端 nginx 代理、后端 gunicorn）
- [x] 11.3 编写 docker-compose 启动/停止脚本
- [x] 11.4 编写全流程 Playwright E2E 测试（录入 → 看板 → 分析 → 回测 → 策略）
- [x] 11.5 运行全部测试并确保通过
