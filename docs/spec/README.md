# BeFriend FundAsset - 功能增强 Spec 文档

## 文档结构

```
docs/spec/
├── README.md                    # 本文件 - 总览与进度追踪
├── decisions.md                 # 所有技术决策记录
├── phase-1-data-foundation/     # 阶段1: 数据基础
│   ├── 05-transaction-records.md
│   ├── 04-dividend-split.md
│   └── 14-data-backup.md
├── phase-2-analysis-core/       # 阶段2: 分析核心
│   ├── 01-return-attribution.md
│   ├── 03-fund-comparison.md
│   └── 09-correlation-analysis.md
├── phase-3-strategy/            # 阶段3: 策略增强
│   ├── 02-rebalancing.md
│   ├── 07-dca-enhancement.md
│   └── 08-valuation-metrics.md
├── phase-4-operations/          # 阶段4: 运营支持
│   ├── 06-data-health-monitor.md
│   ├── 10-investment-diary.md
│   └── 12-data-export.md
├── phase-5-ux/                  # 阶段5: 用户体验
│   └── 11-mobile-adaptation.md
└── test-reports/                # 测试报告
    └── {feature-id}-{name}.md
```

## 实施阶段与进度

| 阶段 | 功能 | 状态 | 测试 | 提交 |
|------|------|------|------|------|
| **Phase 1: 数据基础** | | | | |
| 1.1 | #14 数据备份 | ✅ 完成 | ✅ 11/11 | ✅ |
| 1.2 | #6 数据源健康监控 | ✅ 完成 | ✅ 9/9 | ✅ |
| **Phase 2: 分析核心** | | | | |
| 2.1 | #3 基金筛选/比较 | ✅ 完成 | ✅ 10/10 | ✅ |
| 2.2 | #9 相关性分析 | ✅ 完成 | ✅ 7/7 | ✅ |
| 2.3 | #1 收益归因分析 | ✅ 完成 | ✅ 5/5 | ✅ |
| **Phase 3: 策略增强** | | | | |
| 3.1 | #8 估值指标 | ✅ 完成 | ✅ 12/12 | ✅ |
| 3.2 | #2 再平衡建议 | ✅ 完成 | ✅ 3/3 | ✅ |
| 3.3 | #7 定投策略增强 | ✅ 完成 | ✅ 9/9 | ✅ |
| **Phase 4: 运营支持** | | | | |
| 4.1 | #10 投资日记 | ✅ 完成 | ✅ 6/6 | ✅ |
| 4.2 | #12 数据导出 & 报表 | ✅ 完成 | ✅ 5/5 | ✅ |
| **Phase 5: 用户体验** | | | | |
| 5.1 | #11 移动端适配 | ✅ 完成 | ✅ CSS/PWA | ✅ |

## 实施原则

1. **Spec 先行**: 每个功能先写 spec，再实现
2. **独立可测**: 每个功能前后端测试通过后才提交
3. **决策记录**: 所有技术决策写入 decisions.md
4. **测试报告**: 每个功能完成后生成测试报告
5. **增量提交**: 每个独立模块完成后 git commit
6. **不询问用户**: 所有决策自主完成并记录

## 调整说明

原始规划中的 #5 交易记录明细和 #4 分红/拆分处理 需要改变现有数据导入流程（微众/支付宝对账单只有周快照），
且用户当前数据源不支持逐笔交易。这两个功能推迟到有真实交易数据源后再实现。
详见 decisions.md D001。
