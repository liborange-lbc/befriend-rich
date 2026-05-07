# 需求确认清单

| 维度 | 确认内容 | 状态 |
|------|----------|------|
| 业务背景 | 散户因行为失控（追涨杀跌、频繁交易、重仓、恐慌割肉）导致亏损，需系统化纪律执行工具 | ✅ 已确认 |
| 核心功能 | 五大模块：投资计划制定、智能提醒、交易前AI对话评估、防冲动约束、复盘报告 | ✅ 已确认 |
| 影响范围 | 在现有 **BeFriend_FundAsset** 项目上扩展。已有 portfolio/strategy/guru/assistant 模块可复用 | ✅ 已确认 |
| 用户角色 | 单用户系统，无多用户/权限需求 | ✅ 已确认 |
| 数据流向 | 已有数据源(Tushare/Yahoo/AkShare/GuruFocus) → SQLite → 监控引擎/AI对话引擎 → 前端 UI | ✅ 已确认 |
| 非功能需求 | Docker Compose 部署，单用户，无高并发，已有 APScheduler 定时任务框架 | ✅ 已确认 |
| 约束条件 | 沿用 FastAPI+SQLAlchemy+Alembic+SQLite+React/TS/AntDesign，AI 使用已集成的 Anthropic SDK | ✅ 已确认 |
| 已有能力复用 | Portfolio模型/API、Strategy模型、Guru数据、Assistant(Claude)、Feishu通知、APScheduler | ✅ 已确认 |
| 验收标准 | 五大模块全部功能可用，P0+P1+P2 全覆盖 | ✅ 已确认 |
| 实践范围 | 全部 P0+P1+P2 | ✅ 已确认 |

确认人：用户
确认时间：2026-04-25
