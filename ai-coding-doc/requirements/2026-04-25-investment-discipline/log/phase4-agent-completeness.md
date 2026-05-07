# Phase 4 — 需求完整度审查

> Agent: Requirements Completeness Expert (需求完整度专家)
> 职责: 逐条核查 requirement-breakdown.md 中的 78 个 FR 子项，确认 design-doc.md 是否有完整的实现设计
> 审查时间: 2026-04-25

---

## 1. 逐项审查

### 模块 A: 投资计划制定器 (Plan)

| FR 编号 | 功能描述 | 覆盖状态 | 设计位置 | 问题 |
|---------|----------|---------|---------|------|
| FR-PLAN-001 | 用户输入基本信息（本金、年化目标、投资周期、风险承受、投资经验） | ✅ Covered | §3.1.1 investment_plan 表 + §3.2.1 PlanCreate schema | 字段完整对应 |
| FR-PLAN-002 | 基本信息字段校验（本金>0、目标合理范围、必填项检查） | ⚠️ Insufficient | §3.2.1 PlanCreate 有类型约束 | 缺少具体校验规则设计：principal>0 有注释但 annual_target 范围 0-1 是否足够？experience_level 枚举校验？缺少错误消息定义 |
| FR-PLAN-003 | 系统根据目标和风险承受力推荐资产配置方案 | ✅ Covered | §3.2.1 POST /plan/{id}/recommend | 有独立推荐接口 |
| FR-PLAN-004 | 用户可调整配置比例，系统实时计算预期收益 | ⚠️ Insufficient | §3.2.1 asset_allocation 字段 | 前端实时计算逻辑未设计（计算公式？是否纯前端？），缺少 expected_return 计算规则 |
| FR-PLAN-005 | 配置比例校验（总和=100%、单项不超限） | ⚠️ Insufficient | §3.2.1 asset_allocation 类型为 list[dict] | 缺少校验规则的具体设计：总和校验、单项上限值、校验时机（前端/后端） |
| FR-PLAN-006 | 用户设置选股买入条件（价值大师评分≥70、PE低于中位数等6项） | ✅ Covered | §3.1.1 buy_conditions JSON 字段 + §3.2.1 | 使用 `{field, operator, threshold, label}` 结构 |
| FR-PLAN-007 | 用户设置卖出条件（PE超90分位、评分<50等6项） | ✅ Covered | §3.1.1 sell_conditions JSON 字段 + §3.2.1 | 使用同样结构 |
| FR-PLAN-008 | 用户设置仓位管理规则（单票上限15%、分批买入等） | ✅ Covered | §3.1.1 position_rules JSON 字段 | 字段齐全：max_single_pct, buy_batches, buy_interval_days 等 |
| FR-PLAN-009 | 仓位规则校验（上限百分比≤100%、间隔天数>0、次数>0） | ⚠️ Insufficient | §3.2.1 position_rules: dict | 缺少具体校验规则设计，仅定义了 dict 类型 |
| FR-PLAN-010 | 计划生成后二次确认 | ✅ Covered | §3.2.1 POST /plan/{id}/lock + §2.3.1 时序图 | 有独立 lock 接口和时序 |
| FR-PLAN-011 | 确认后计划锁定，修改需48小时冷静期 | ✅ Covered | §3.1.1 status/locked_at/cooldown_until + §3.2.1 PUT + §5.3 cooling_period_plan_hours | 完整 |
| FR-PLAN-012 | 计划修改历史全部留痕 | ✅ Covered | §3.1.2 plan_revision_log 表 + §3.2.1 GET /plan/{id}/revisions | 完整 |
| FR-PLAN-013 | 计划数据持久化到 SQLite | ✅ Covered | §3.1.1 全表设计 + §5.2 数据迁移说明 | create_all() 自动建表 |
| FR-PLAN-014 | 展示本金、目标、已运行天数、当前净值、收益率、年化折算 | ✅ Covered | §3.2.1 PlanDashboard: portfolio_summary + days_running | 完整 |
| FR-PLAN-015 | 展示各仓位计划比例 vs 实际比例 vs 偏离度 vs 状态 | ✅ Covered | §3.2.1 PlanDashboard: allocation_status [{planned_pct, actual_pct, deviation, status}] | 完整 |
| FR-PLAN-016 | 展示本月操作次数/上限、下次再平衡日期 | ✅ Covered | §3.2.1 PlanDashboard: monthly_trades + next_rebalance_date | 完整 |
| FR-PLAN-017 | 计划锁定状态展示（修改按钮带锁标识） | ⚠️ Insufficient | §3.2.1 PlanDashboard 有 plan 对象 | 前端锁定 UI 状态展示规则未设计，仅数据模型包含 status/locked_at |
| FR-PLAN-018 | 无计划时引导创建计划 | ⚠️ Insufficient | §3.2.1 GET /plan/{id}/dashboard | 缺少空状态处理设计：dashboard 接口无计划时返回什么？前端引导流程？ |

### 模块 B: 智能提醒系统 (Alert)

| FR 编号 | 功能描述 | 覆盖状态 | 设计位置 | 问题 |
|---------|----------|---------|---------|------|
| FR-ALERT-001 | 监控目标股票价格跌至买入区间（低于GF Value 80%） | ✅ Covered | §3.4 Type A 触发逻辑 | AND 逻辑明确 |
| FR-ALERT-002 | 检查大师近期是否有新买入/加仓信号 | ✅ Covered | §3.4 Type A 数据源: GuruTrade | 作为 AND 条件之一 |
| FR-ALERT-003 | 检查当前仓位未达上限 + 现金仓位>5% | ✅ Covered | §3.4 Type A: 仓位未达上限+现金>5% | 完整 |
| FR-ALERT-004 | 全部条件满足时生成绿色买入提醒卡片 | ✅ Covered | §3.4 Feishu 通知: template="green" + §3.1.3 severity="green" | 完整 |
| FR-ALERT-005 | 买入提醒频率控制：每周最多2条 | ✅ Covered | §3.4 Type A: hourly, 每周≤2条 | 完整 |
| FR-ALERT-006 | 监控个股涨幅达+50%（止盈信号） | ✅ Covered | §3.4 Type B OR 逻辑: 涨幅+50% | 完整 |
| FR-ALERT-007 | 监控 PE 突破历史90分位 | ✅ Covered | §3.4 Type B: PE>90分位 | 完整 |
| FR-ALERT-008 | 监控3位以上大师同季减持 | ✅ Covered | §3.4 Type B: 3大师减持 | 完整 |
| FR-ALERT-009 | 监控 ROE 连续2季下降 | ✅ Covered | §3.4 Type B: ROE下降2季 | 完整 |
| FR-ALERT-010 | 监控单票权重超15%上限 | ✅ Covered | §3.4 Type B: 权重>15% | 完整 |
| FR-ALERT-011 | 任一条件满足时生成橙色减仓提醒卡片 | ✅ Covered | §3.4 Feishu 通知: template="orange" + §3.1.3 severity="orange" | 完整 |
| FR-ALERT-012 | 季度再平衡日期到达时触发 | ✅ Covered | §3.4 Type C: 季度日期到达 | 完整 |
| FR-ALERT-013 | 检测任一仓位偏离计划>5%时触发 | ✅ Covered | §3.4 Type C: 仓位偏离>5% | 完整 |
| FR-ALERT-014 | 生成蓝色再平衡提醒卡片（含具体调整建议金额） | ⚠️ Insufficient | §3.4 Type C + Feishu template="blue" | 提到了蓝色卡片，但"具体调整建议金额"的计算逻辑未设计 |
| FR-ALERT-015 | 支持"推迟1周"操作 | ❌ Not covered | - | Alert API 中没有"推迟"接口，仅有 read/dismiss 操作，缺少 postpone 端点和逻辑 |
| FR-ALERT-016 | 组合单日回撤>3% 触发红色预警 | ✅ Covered | §3.4 Type D: 单日回撤>3% | 完整 |
| FR-ALERT-017 | 组合月度回撤>8% 触发红色预警 | ✅ Covered | §3.4 Type D: 月度回撤>8% | 完整 |
| FR-ALERT-018 | 预警卡片含历史波动统计（"过去3年87%交易日波动在±3%以内"） | ⚠️ Insufficient | §3.4 Type D | 提到红色预警但历史波动统计数据的计算和展示未设计 |
| FR-ALERT-019 | 同一事件不重复推送 | ✅ Covered | §3.4 去重机制 + §3.1.3 dedupe_key UNIQUE 约束 | 完整 |
| FR-ALERT-020 | "我仍然想操作"按钮→进入交易对话 | ⚠️ Insufficient | - | Alert 详情中有操作按钮概念但缺少从预警跳转到 TradeEval 的交互设计和接口 |
| FR-ALERT-021 | 每周五收盘后推送周回顾 | ✅ Covered | §3.4 Type E 每周五16:00 + §3.5 job_weekly_discipline_report | 完整 |
| FR-ALERT-022 | 提醒列表页（按时间倒序，按类型筛选） | ✅ Covered | §3.2.2 GET /alert + Query Params: type, status, page, page_size | 完整 |
| FR-ALERT-023 | 提醒详情展示（触发原因、建议操作、操作按钮） | ✅ Covered | §3.2.2 GET /alert/{id} + §3.1.3 content JSON | 完整 |
| FR-ALERT-024 | 提醒已读/未读状态管理 | ✅ Covered | §3.2.2 PUT read/dismiss + GET unread-count + §3.1.3 status 字段 | 完整 |

### 模块 C: 交易前 AI 对话评估 (TradeEval)

| FR 编号 | 功能描述 | 覆盖状态 | 设计位置 | 问题 |
|---------|----------|---------|---------|------|
| FR-EVAL-001 | 用户发起交易意图（输入：标的、方向买/卖、金额） | ✅ Covered | §3.2.3 POST /trade/intent + TradeIntentCreate schema | 完整 |
| FR-EVAL-002 | 计划一致性检查（目标股票池、仓位空间、现金底线） | ✅ Covered | §3.3 get_plan_status + check_trade_constraints tools | 完整 |
| FR-EVAL-003 | 估值检查（PE vs 历史中位数、价值大师评分、GF Value 安全边际） | ✅ Covered | §3.3 get_fund_valuation tool | 完整 |
| FR-EVAL-004 | AI 通过多轮对话（3-5轮）评估买入/卖出动机 | ✅ Covered | §3.3 max_rounds=5 + System Prompt 明确 3-5 轮 | 完整 |
| FR-EVAL-005 | 对话中提供选择题（A/B/C/D选项）降低用户输入成本 | ✅ Covered | §3.3 System Prompt "提供选择题" + §3.2.3 TradeEvalResponse.options | 完整 |
| FR-EVAL-006 | 调用 Claude API 生成对话响应 | ✅ Covered | §3.3 全节 + 调用参数 + TRADE_EVAL_TOOLS | 完整 |
| FR-EVAL-007 | 按5维度加权评分（计划一致性30%、估值20%等） | ✅ Covered | §3.3 System Prompt 评分维度 + finalize_evaluation tool | 完整 |
| FR-EVAL-008 | 80-100分 → ✅通过 | ✅ Covered | §2.3.2 时序图 score >= 80 → 通过 | 完整 |
| FR-EVAL-009 | 60-79分 → ⚠提示风险 | ✅ Covered | §2.3.2 时序图 score 60-79 → 提示风险 | 完整 |
| FR-EVAL-010 | 40-59分 → 🟡建议调整 | ✅ Covered | §2.3.2 时序图 score 40-59 → 建议调整 | 完整 |
| FR-EVAL-011 | 0-39分 → 🔴拦截，进入冷静期 | ✅ Covered | §2.3.2 时序图 score < 40 → INSERT CoolingPeriod | 完整 |
| FR-EVAL-012 | 评分结果展示（各维度得分明细 + 总结建议） | ✅ Covered | §3.2.3 TradeEvalResponse: score_breakdown + §3.1.4 score_breakdown JSON | 完整 |
| FR-EVAL-013 | 聊天式对话界面（用户消息 + AI消息交替） | ✅ Covered | §3.1.5 trade_conversation messages + §3.2.3 evaluate 接口 | 完整 |
| FR-EVAL-014 | 选择题选项以按钮形式展示 | ⚠️ Insufficient | §3.2.3 TradeEvalResponse.options | 后端返回 options 数据但前端按钮展示规则未设计 |
| FR-EVAL-015 | 评分结果卡片展示（通过/拦截/冷静期状态） | ⚠️ Insufficient | §3.2.3 TradeEvalResponse.result | 后端返回 result 字段但前端卡片展示格式未设计 |
| FR-EVAL-016 | "确认执行"/"取消"/"进入冷静期"操作按钮 | ✅ Covered | §3.2.3 POST confirm / cancel 接口 | 完整 |
| FR-EVAL-017 | 对话历史保存，可回看 | ✅ Covered | §3.1.5 trade_conversation + §3.2.3 GET /trade/intent/{id} + GET /trade/intents | 完整 |

### 模块 D: 防冲动约束机制 (Constraint)

| FR 编号 | 功能描述 | 覆盖状态 | 设计位置 | 问题 |
|---------|----------|---------|---------|------|
| FR-CONST-001 | 修改投资计划 → 48小时冷静期 | ✅ Covered | §3.1.6 reason="plan_modify" + §5.3 cooling_period_plan_hours=48 | 完整 |
| FR-CONST-002 | 单笔超30万 → 24小时冷静期 | ✅ Covered | §3.1.6 reason="large_amount" + §5.3 cooling_period_trade_hours=24 | 完整 |
| FR-CONST-003 | AI评分<40 → 24小时冷静期 | ✅ Covered | §2.3.2 时序图 + §3.1.6 reason="low_score" | 完整 |
| FR-CONST-004 | 全仓操作(>50%仓位) → 48小时冷静期 | ✅ Covered | §3.1.6 reason="full_position" | 完整 |
| FR-CONST-005 | 当日第4笔交易 → 次日冷静期 | ✅ Covered | §3.1.6 reason="excess_trades" | 完整 |
| FR-CONST-006 | 冷静期倒计时展示 | ✅ Covered | §3.2.4 GET /constraint/cooling/{id} 含倒计时 | 完整 |
| FR-CONST-007 | 冷静期结束后推送确认通知（仍然执行/调整/放弃） | ✅ Covered | §2.3.3 时序图 Scheduler→Notif + §3.2.4 POST decide | 完整 |
| FR-CONST-008 | 冷静期内不删除意图，保留原始操作信息 | ✅ Covered | §3.1.6 original_action JSON 字段 | 完整 |
| FR-CONST-009 | 月交易次数统计（已用/上限/剩余） | ✅ Covered | §3.1.7 monthly_trade_stats 表 + §3.2.4 GET /constraint/monthly-stats | 完整 |
| FR-CONST-010 | 超出上限后不拦截但标记"超额交易" | ✅ Covered | §3.1.7 excess_count 字段 | 完整 |
| FR-CONST-011 | 检测操作金额突然放大（比近10次平均大3倍） | ✅ Covered | §3.2.4 POST /constraint/emotion-check | 完整 |
| FR-CONST-012 | 检测短时间连续操作（1小时内>3次） | ✅ Covered | §3.2.4 EmotionCheckResponse.signals | 完整 |
| FR-CONST-013 | 检测全仓/清仓请求（>50%仓位） | ✅ Covered | §3.2.4 emotion-check 接口 | 完整 |
| FR-CONST-014 | 检测市场暴跌日操作（大盘当日跌>3%） | ✅ Covered | §3.2.4 emotion-check 接口 | 完整 |
| FR-CONST-015 | 检测情绪化语言（NLP检测"崩了""完了""赶紧"） | ✅ Covered | §3.2.4 EmotionCheckRequest.intent_text | 完整 |
| FR-CONST-016 | ≥2个信号 → 自动触发冷静期+AI对话 | ✅ Covered | §3.2.4 EmotionCheckResponse: triggered (>=2 signals) + cooling_period_id | 完整 |
| FR-CONST-017 | 计划制定时引导用户写信给"恐慌时的自己" | ✅ Covered | §3.1.1 panic_letter 字段 + §3.2.1 POST /plan/{id}/panic-letter | 完整 |
| FR-CONST-018 | 恐慌操作被拦截时展示这封信 | ⚠️ Insufficient | §3.1.1 panic_letter 存储 | 有存储字段但缺少拦截时展示信件的具体触发逻辑和接口设计 |
| FR-CONST-019 | 信件可编辑更新 | ✅ Covered | §3.2.1 POST /plan/{id}/panic-letter（保存/更新） | 完整 |

### 模块 E: 复盘与报告 (Report)

| FR 编号 | 功能描述 | 覆盖状态 | 设计位置 | 问题 |
|---------|----------|---------|---------|------|
| FR-RPT-001 | 自动生成周报（本周涨跌、操作回顾） | ✅ Covered | §3.5 job_weekly_discipline_report + §3.1.8 type="weekly" | 完整 |
| FR-RPT-002 | 被拦截操作回顾 | ⚠️ Insufficient | §3.1.8 content JSON | 提到报告 content 按类型不同结构不同，但未定义周报的具体数据结构，被拦截操作如何聚合未设计 |
| FR-RPT-003 | "你没操作"的统计展示 | ⚠️ Insufficient | §3.1.8 content JSON | 同上，缺少具体字段设计 |
| FR-RPT-004 | 月度收益 vs 基准（沪深300/标普500各50%） | ⚠️ Insufficient | §3.5 job_monthly_discipline_report | 提到生成月报但缺少基准收益数据来源设计（沪深300/标普500数据从哪获取？） |
| FR-RPT-005 | 操作次数 vs 计划上限统计 | ✅ Covered | §3.1.7 monthly_trade_stats 已有数据支撑 | 完整 |
| FR-RPT-006 | 被拦截操作事后表现（"如果你冲动了，你会亏/赚X%"） | ⚠️ Insufficient | §3.2.5 POST /report/generate | 提到可手动生成但缺少"事后模拟"计算逻辑设计 |
| FR-RPT-007 | 计划执行得分 | ⚠️ Insufficient | §3.1.8 content JSON | 缺少执行得分的计算规则设计 |
| FR-RPT-008 | 大师最新动态摘要 | ⚠️ Insufficient | §5.1 读取 GuruHolding/Trade | 提到读取 guru 数据但缺少月报中大师动态摘要的具体聚合逻辑 |
| FR-RPT-009 | 季度收益、年化折算 | ⚠️ Insufficient | §3.1.8 type="quarterly" | 有季报类型但缺少年化折算计算公式 |
| FR-RPT-010 | 仓位偏离度分析 | ✅ Covered | §3.2.1 PlanDashboard.allocation_status 可复用 | 数据模型支持 |
| FR-RPT-011 | 再平衡执行情况 | ⚠️ Insufficient | - | 缺少再平衡执行记录的数据模型，无法追踪"建议 vs 实际执行" |
| FR-RPT-012 | 被拦截操作"如果执行了"模拟分析 | ⚠️ Insufficient | - | 同 FR-RPT-006，缺少模拟计算逻辑 |
| FR-RPT-013 | 下季度建议调整 | ⚠️ Insufficient | - | 缺少季度建议调整的生成逻辑设计 |
| FR-RPT-014 | 报告列表页（按周/月/季筛选） | ✅ Covered | §3.2.5 GET /report + §3.1.8 type 字段 | 完整 |
| FR-RPT-015 | 报告详情展示页（图表+数据） | ⚠️ Insufficient | §3.2.5 GET /report/{id} | 有接口但缺少报告详情的具体展示结构设计（图表类型、数据格式） |

### 模块 F: 数据同步 & 基础设施 (Infra)

| FR 编号 | 功能描述 | 覆盖状态 | 设计位置 | 问题 |
|---------|----------|---------|---------|------|
| FR-INFRA-001 | GuruFocus 数据自动定期同步 | ⚠️ Insufficient | §6 R2 提到"暂从 GuruFocus 数据间接获取" | 标为风险但缺少同步方案设计，P2 但应有占位设计 |
| FR-INFRA-002 | 交易日志模型（记录所有交易意图、评分、结果） | ✅ Covered | §3.1.4 trade_intent 表完整设计 | 完整 |
| FR-INFRA-003 | 提醒模型（类型、触发条件、状态、时间戳） | ✅ Covered | §3.1.3 discipline_alert 表完整设计 | 完整 |
| FR-INFRA-004 | 冷静期模型（操作意图、开始时间、结束时间、最终决定） | ✅ Covered | §3.1.6 cooling_period 表完整设计 | 完整 |
| FR-INFRA-005 | 券商API接入仓位实时同步 | ❌ Not covered | - | P2 项但完全没有设计，缺少接口抽象和占位 |
| FR-INFRA-006 | 移动端推送通知适配 | ❌ Not covered | - | P2 项但完全没有设计，仅有 Feishu 通知 |
| FR-INFRA-007 | Claude API 集成（封装调用、prompt管理、错误重试） | ✅ Covered | §3.3 完整设计 + §4.1 成本控制 + §5.3 SystemConfig | 完整 |

---

## 2. 统计汇总

| 指标 | 数量 | 占比 |
|------|------|------|
| 总 FR 子项 | 78 | 100% |
| ✅ Covered（完整覆盖） | 53 | 67.9% |
| ⚠️ Insufficient（覆盖不足） | 22 | 28.2% |
| ❌ Not covered（未覆盖） | 3 | 3.8% |

### 按模块统计

| 模块 | 总数 | ✅ | ⚠️ | ❌ |
|------|------|---|----|----|
| A: Plan | 18 | 12 | 6 | 0 |
| B: Alert | 24 | 20 | 3 | 1 |
| C: TradeEval | 17 | 15 | 2 | 0 |
| D: Constraint | 19 | 17 | 1 | 0 (注: 覆盖矩阵标注到19但实际只有19项) |
| E: Report | 15 | 4 | 11 | 0 |
| F: Infra | 7 | 4 | 1 | 2 |

### 按优先级统计

| 优先级 | 总数 | ✅ | ⚠️ | ❌ |
|--------|------|---|----|----|
| P0 | 34 | 29 | 5 | 0 |
| P1 | 30 | 20 | 10 | 0 |
| P2 | 14 | 4 | 7 | 3 |

---

## 3. 问题清单

```json
[
  {
    "severity": "CRITICAL",
    "category": "缺失设计",
    "location": "FR-ALERT-015",
    "issue": "再平衡提醒的'推迟1周'操作完全没有设计",
    "suggestion": "在 Alert API 中新增 POST /alert/{id}/postpone 接口，在 discipline_alert 表增加 postponed_until 字段"
  },
  {
    "severity": "CRITICAL",
    "category": "缺失设计",
    "location": "FR-INFRA-005",
    "issue": "券商API接入仓位实时同步完全没有设计",
    "suggestion": "P2项，建议至少定义抽象接口（BrokerAdapter）和数据流占位设计"
  },
  {
    "severity": "CRITICAL",
    "category": "缺失设计",
    "location": "FR-INFRA-006",
    "issue": "移动端推送通知适配完全没有设计",
    "suggestion": "P2项，建议在通知模块增加推送渠道抽象（PushChannel），当前 Feishu 作为默认实现"
  },
  {
    "severity": "HIGH",
    "category": "校验规则缺失",
    "location": "FR-PLAN-002",
    "issue": "基本信息字段校验缺少具体规则设计（范围、枚举值、错误消息）",
    "suggestion": "在 PlanCreate schema 中使用 Pydantic validators 定义：principal > 0, 0 < annual_target <= 0.5, experience_level in enum 等"
  },
  {
    "severity": "HIGH",
    "category": "计算逻辑缺失",
    "location": "FR-PLAN-004",
    "issue": "预期收益实时计算逻辑未设计",
    "suggestion": "明确计算公式：expected_return = Σ(ratio_i × expected_return_i)，说明是前端纯计算还是需要后端接口"
  },
  {
    "severity": "HIGH",
    "category": "校验规则缺失",
    "location": "FR-PLAN-005",
    "issue": "配置比例校验规则（总和=100%、单项上限）缺少具体设计",
    "suggestion": "在 PlanCreate validator 中增加 sum(allocation.ratio) == 1.0 校验，定义单项上限规则"
  },
  {
    "severity": "HIGH",
    "category": "校验规则缺失",
    "location": "FR-PLAN-009",
    "issue": "仓位规则校验缺少具体规则定义",
    "suggestion": "为 position_rules 定义 Pydantic sub-model，用 Field(gt=0) 等约束"
  },
  {
    "severity": "HIGH",
    "category": "前端设计缺失",
    "location": "FR-PLAN-017",
    "issue": "计划锁定状态的前端展示规则未设计",
    "suggestion": "前端根据 plan.status 和 cooldown_until 判断按钮状态，建议补充 UI 状态机"
  },
  {
    "severity": "HIGH",
    "category": "边界条件缺失",
    "location": "FR-PLAN-018",
    "issue": "无计划时的空状态处理和引导流程未设计",
    "suggestion": "dashboard 接口在无计划时返回 {plan: null, guide: true}，前端显示引导卡片"
  },
  {
    "severity": "HIGH",
    "category": "计算逻辑缺失",
    "location": "FR-ALERT-014",
    "issue": "再平衡提醒中'具体调整建议金额'的计算逻辑未设计",
    "suggestion": "补充计算规则：adjust_amount = total_value × (planned_pct - actual_pct)"
  },
  {
    "severity": "HIGH",
    "category": "展示逻辑缺失",
    "location": "FR-ALERT-018",
    "issue": "风险预警卡片中历史波动统计的计算和数据来源未设计",
    "suggestion": "定义波动统计查询：统计过去3年日收益率在±3%内的比例，数据来源 PortfolioSnapshot"
  },
  {
    "severity": "HIGH",
    "category": "交互设计缺失",
    "location": "FR-ALERT-020",
    "issue": "'我仍然想操作'按钮跳转到交易对话的交互流程未设计",
    "suggestion": "Alert 详情增加 action_url 字段，值为 /trade/intent?from_alert={alert_id}&fund_code=xxx"
  },
  {
    "severity": "HIGH",
    "category": "前端设计缺失",
    "location": "FR-EVAL-014",
    "issue": "选择题按钮展示规则缺少前端设计",
    "suggestion": "后端 options 结构已定义，前端渲染规则可在实现阶段明确，建议补充选项布局说明"
  },
  {
    "severity": "HIGH",
    "category": "前端设计缺失",
    "location": "FR-EVAL-015",
    "issue": "评分结果卡片的前端展示格式缺少设计",
    "suggestion": "定义卡片布局：总分 + 5维度雷达图/柱状图 + result 状态标签 + 操作按钮"
  },
  {
    "severity": "HIGH",
    "category": "展示逻辑缺失",
    "location": "FR-CONST-018",
    "issue": "恐慌操作被拦截时展示信件的触发逻辑缺少设计",
    "suggestion": "在冷静期创建响应中增加 panic_letter 字段，reason 为 low_score/full_position 时自动附带信件内容"
  },
  {
    "severity": "HIGH",
    "category": "数据结构缺失",
    "location": "FR-RPT-002",
    "issue": "周报中被拦截操作回顾的数据聚合逻辑未设计",
    "suggestion": "定义周报 content 结构：{portfolio_change, trades_summary, blocked_trades: [{intent_id, fund, score, reason}], no_trade_days}"
  },
  {
    "severity": "HIGH",
    "category": "数据结构缺失",
    "location": "FR-RPT-003",
    "issue": "周报中'你没操作'统计展示的具体设计缺失",
    "suggestion": "同上，在周报结构中定义 no_trade_days 和正向反馈文案"
  },
  {
    "severity": "HIGH",
    "category": "数据来源缺失",
    "location": "FR-RPT-004",
    "issue": "基准收益数据（沪深300/标普500）的获取来源未设计",
    "suggestion": "明确基准数据来源：是从 GuruFocus 获取还是外部 API？需要新增基准价格表？"
  },
  {
    "severity": "HIGH",
    "category": "计算逻辑缺失",
    "location": "FR-RPT-006",
    "issue": "被拦截操作事后模拟分析（'如果你冲动了'）的计算逻辑未设计",
    "suggestion": "定义模拟逻辑：取被拦截时的意图金额和标的，计算从拦截日到报告日的实际价格变化"
  },
  {
    "severity": "HIGH",
    "category": "计算逻辑缺失",
    "location": "FR-RPT-007",
    "issue": "计划执行得分的计算规则未设计",
    "suggestion": "定义得分维度：仓位偏离度(30%) + 交易频率合规(25%) + 冷静期遵守(25%) + 再平衡执行(20%)"
  },
  {
    "severity": "HIGH",
    "category": "数据聚合缺失",
    "location": "FR-RPT-008",
    "issue": "月报中大师动态摘要的具体聚合逻辑未设计",
    "suggestion": "查询本月 GuruTrade 记录，按基金分组，输出大师买卖汇总"
  },
  {
    "severity": "HIGH",
    "category": "计算逻辑缺失",
    "location": "FR-RPT-009",
    "issue": "季报年化折算的计算公式未设计",
    "suggestion": "明确公式：annualized_return = (1 + quarter_return)^4 - 1"
  },
  {
    "severity": "HIGH",
    "category": "数据模型缺失",
    "location": "FR-RPT-011",
    "issue": "再平衡执行情况缺少追踪数据模型",
    "suggestion": "需要记录再平衡建议 vs 实际执行的对比，可在 discipline_alert 增加 action_taken 字段"
  },
  {
    "severity": "HIGH",
    "category": "计算逻辑缺失",
    "location": "FR-RPT-012",
    "issue": "季报中被拦截操作模拟分析的设计缺失",
    "suggestion": "复用月报模拟逻辑，汇总季度数据"
  },
  {
    "severity": "HIGH",
    "category": "生成逻辑缺失",
    "location": "FR-RPT-013",
    "issue": "下季度建议调整的生成逻辑缺少设计",
    "suggestion": "基于仓位偏离趋势、市场估值变化、计划执行得分生成建议，可用 AI 或规则引擎"
  },
  {
    "severity": "HIGH",
    "category": "前端设计缺失",
    "location": "FR-RPT-015",
    "issue": "报告详情展示页的图表和数据格式缺少设计",
    "suggestion": "定义报告 content 的 JSON 结构和对应的前端图表组件映射"
  },
  {
    "severity": "HIGH",
    "category": "同步方案缺失",
    "location": "FR-INFRA-001",
    "issue": "GuruFocus 数据同步方案缺少具体设计",
    "suggestion": "P2项，建议至少定义同步频率、数据范围和增量更新策略"
  }
]
```

---

## 4. 结论

### 判定: FAIL

**理由:**

1. **3 个 CRITICAL 问题（未覆盖）**: FR-ALERT-015（推迟操作）虽然是 P1 但属于核心交互缺失；FR-INFRA-005/006 是 P2 但完全没有占位设计。
2. **22 个 HIGH 问题（覆盖不足）**: 其中 5 个影响 P0 功能（FR-PLAN-002/004/005/009/018 的校验和计算逻辑），需要在编码前明确。
3. **Report 模块覆盖率最低**: 15 个子项中仅 4 个完整覆盖（26.7%），大量计算逻辑和数据结构缺少具体设计。
4. **P0 覆盖率 85.3%（29/34）**: 5 个 P0 项覆盖不足，集中在校验规则和边界条件处理。

### 修复优先级建议

1. **立即修复（阻塞编码）**: FR-PLAN-002/005/009 的校验规则、FR-PLAN-018 空状态处理、FR-ALERT-015 推迟接口
2. **编码前补充**: Report 模块的数据结构定义（FR-RPT-002/003/004/007）
3. **可延后**: P2 项的占位设计（FR-INFRA-005/006）、前端展示细节（FR-EVAL-014/015、FR-PLAN-017）
