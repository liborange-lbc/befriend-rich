# Execution Logging Guide

开发全流程的日志记录规范。目标：将全过程完全可视化、可追溯。

## 核心原则

1. **每个步骤必须留痕** — 不记录 = 不存在
2. **决策点必须说明理由** — 不是记流水账，而是记决策链
3. **引用必须可追溯** — 每条结论都要标注数据来源
4. **Subagent 独立记录** — 每个 subagent 写自己的日志文件，避免竞争

## 日志文件命名

```
log/
├── phase0-knowledge-bootstrap.md      # Phase 0: 系统知识检查/生成
├── phase1-requirement-interview.md    # Phase 1: 需求面试 + 功能拆解
├── phase2a-code-reading.md            # Phase 2a: 代码阅读（subagent）
├── phase2b-knowledge-lookup.md        # Phase 2b: 知识库查阅
├── phase3-design.md                   # Phase 3: 细分设计
├── phase4-agent-completeness.md       # Phase 4: 需求完整度专家（subagent）
├── phase4-agent-architecture.md       # Phase 4: 架构安全专家（subagent）
├── phase5-iteration-1.md              # Phase 5: 第 1 轮设计迭代
├── phase5-iteration-2.md              # Phase 5: 第 2 轮（如有）
├── phase5-iteration-3.md              # Phase 5: 第 3 轮（如有）
├── phase6-coding.md                   # Phase 6: 编码实现
├── phase7-testing.md                  # Phase 7: 测试用例编写
├── phase8-agent-standards.md          # Phase 8: 代码规范专家（subagent）
├── phase8-agent-logic.md              # Phase 8: 逻辑正确性专家（subagent）
├── phase8-agent-testing.md            # Phase 8: 测试质量专家（subagent）
├── phase8-iteration-1.md              # Phase 8: 第 1 轮代码迭代（如有）
├── phase8-iteration-2.md              # Phase 8: 第 2 轮（如有）
├── phase8-iteration-3.md              # Phase 8: 第 3 轮（如有）
├── phase9-delivery.md                 # Phase 9: 开发报告 + 验收报告
├── execution-summary.md               # 执行路径汇总
└── execution-flowchart.md             # 全局流程图（Mermaid）
```

## 单步日志格式

每个步骤按以下结构记录：

```markdown
## Step {N.M}: {步骤名称}

> 时间: {timestamp}

**决策点**: {为什么要执行这一步？基于什么判断？}

**执行动作**:
- {具体操作 1}
- {具体操作 2}

**引用材料**:
- 文档: `system-knowledge/domain-model.md` §实体关系 — 确认了 Order 和 Payment 的关联方式
- 代码: `src/main/java/com/xxx/OrderService.java:45-78` — 阅读了现有下单流程
- 链接: {飞书/Confluence URL} — 获取了支付回调的业务规则

**结论**:
- {关键发现 1}
- {关键发现 2}
- {产出文件路径}（如有）
```

## Subagent 日志格式

Subagent 日志文件需额外包含：

```markdown
# Phase {N}: {Agent 角色名}

> Agent 类型: {completeness | architecture | standards | logic | testing | code-reader}
> 任务摘要: {一句话描述 subagent 要做什么}
> 输入: {读取了哪些文件}
> 开始时间: {timestamp}

## 执行过程

### Checklist Item 1: {检查项名称}

**检查内容**: {这个检查项要验证什么}
**执行点**: {读了设计文档的哪个章节 / 代码的哪个文件}
**引用**: `design-doc.md` §3.1 接口设计 + `OrderController.java:23`
**结果**: PASS / FAIL({severity})
**发现**: {如果 FAIL，描述问题和建议}

### Checklist Item 2: ...

---

## 汇总

- 检查项总数: N
- PASS: N
- FAIL: N (CRITICAL: N, HIGH: N, MEDIUM: N, LOW: N)

> 结束时间: {timestamp}
```

## 执行路径汇总（execution-summary.md）

在所有 Phase 完成后生成，作为全局索引：

```markdown
# 开发全流程执行路径汇总

> 需求: {feature-name}
> 执行时间: {start} → {end}
> 设计迭代轮数: {N}
> 代码评审迭代轮数: {M}
> 最终结果: PASS / FAIL（残留 N 项）

## 执行时间线

| # | 阶段 | 状态 | 关键产出 | 详细日志 |
|---|------|------|----------|----------|
| 0 | 系统知识检查 | {状态} | {产出摘要} | [→](phase0-knowledge-bootstrap.md) |
| 1 | 需求面试+功能拆解 | {状态} | {产出摘要} | [→](phase1-requirement-interview.md) |
| 2a | 代码阅读 | {状态} | {产出摘要} | [→](phase2a-code-reading.md) |
| 2b | 知识查阅 | {状态} | {产出摘要} | [→](phase2b-knowledge-lookup.md) |
| 3 | 细分设计 | {状态} | {产出摘要} | [→](phase3-design.md) |
| 4-R1 | 设计评审 | {PASS/FAIL} | {NC/NH/NM} | [完整度](phase4-agent-completeness.md) [架构](phase4-agent-architecture.md) |
| 5-R1 | 设计修正 | {状态} | {修了什么} | [→](phase5-iteration-1.md) |
| 6 | 编码实现 | {状态} | {N个文件} | [→](phase6-coding.md) |
| 7 | 测试编写 | {状态} | {N个用例} | [→](phase7-testing.md) |
| 8-R1 | 代码评审 | {PASS/FAIL} | {NC/NH/NM} | [规范](phase8-agent-standards.md) [逻辑](phase8-agent-logic.md) [测试](phase8-agent-testing.md) |
| 9 | 交付报告 | {状态} | 开发+验收报告 | [→](phase9-delivery.md) |
| 10 | 日志汇总 | 完成 | 本文件 | — |

## 关键决策链

按时间顺序列出所有重要决策点：

1. **[Phase 0]** {决策} — 理由: {why}
2. **[Phase 1]** {需求澄清/功能拆解} — 用户选择: {what}
3. **[Phase 3]** {架构选型} — 依据: {引用来源}
4. **[Phase 5]** {回退深度} — 判定: {标准}
5. **[Phase 8]** {代码修正} — 问题: {来源}

## 引用材料索引

列出整个过程中引用的所有材料（去重）：

| 类型 | 路径/链接 | 被哪些阶段引用 |
|------|----------|---------------|
| 代码 | `src/.../XxxService.java` | Phase 2a, Phase 4, Phase 8 |
| 文档 | `system-knowledge/domain-model.md` | Phase 3, Phase 4 |
| 外部 | {飞书链接} | Phase 2b |
```

## 执行流程图（execution-flowchart.md）

使用 Mermaid flowchart 语法，根据**实际执行路径**生成：

- 实际走过的路径用 `:::done` 样式标注
- 跳过的分支用 `:::skipped` 样式标注
- 失败的节点用 `:::failed` 样式标注

```markdown
# 执行流程图

\`\`\`mermaid
flowchart TD
    classDef done fill:#d4edda,stroke:#28a745
    classDef failed fill:#f8d7da,stroke:#dc3545
    classDef skipped fill:#e2e3e5,stroke:#6c757d

    Start([开始]):::done --> P0:::done

    subgraph S1[设计阶段]
        P0[Phase 0: 系统知识] --> P1:::done
        P1[Phase 1: 需求+拆解] --> P2:::done
        P2[Phase 2: 知识采集] --> P3:::done
        P3[Phase 3: 细分设计] --> P4R1:::failed
        P4R1[Phase 4: 设计评审 R1] -->|1C+1H| P5R1:::done
        P5R1[Phase 5: 局部修复 R1] --> P4R2:::done
        P4R2[Phase 4: 设计评审 R2] -->|PASS| S2_START
    end

    subgraph S2[实现阶段]
        S2_START[ ] --> P6:::done
        P6[Phase 6: 编码] --> P7:::done
        P7[Phase 7: 测试] --> S3_START
    end

    subgraph S3[质量保障]
        S3_START[ ] --> P8R1:::done
        P8R1[Phase 8: 代码评审 R1] -->|PASS| S4_START
    end

    subgraph S4[交付阶段]
        S4_START[ ] --> P9:::done
        P9[Phase 9: 交付报告] --> P10:::done
        P10[Phase 10: 日志汇总]
    end

    P10 --> Done([完成]):::done
\`\`\`
```

## 主流程职责

主流程（非 subagent）负责：

1. 每个 Phase 开始时，创建/打开对应日志文件，写入阶段头信息
2. 启动 subagent 时，将日志文件路径传给 subagent（subagent 自行写入）
3. Subagent 返回后，在主流程日志中记录 subagent 的关键结论和产出路径
4. 所有 Phase 结束后，读取所有日志文件，生成 execution-summary.md 和 execution-flowchart.md
