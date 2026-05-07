# Testing Phase Guide

Phase 7 的测试用例编写指南。

## 执行原则

1. **需求驱动** — 每个 FR 子项至少一个测试用例
2. **有效断言** — 每个测试必须有验证业务行为的断言
3. **真实数据** — 测试数据贴近真实业务场景
4. **独立运行** — 测试之间无顺序依赖

## 测试分类

| 类型 | 范围 | 示例 |
|------|------|------|
| 单元测试 | 单个方法/函数 | 工具方法、业务规则计算、状态转换 |
| 集成测试 | 多组件协作 | API 端到端、数据库操作、缓存交互 |
| 边界测试 | 极端/异常场景 | 空值、超限、并发、重复提交 |

## 测试命名规范

```
test_{FR编号}_{场景描述}

示例:
test_FR_ORDER_001_create_order_success
test_FR_ORDER_001_create_order_with_empty_items_rejected
test_FR_ORDER_002_create_order_duplicate_returns_existing
test_FR_PAY_001_pay_order_insufficient_balance
```

## 编写流程

### Step 1: 生成测试矩阵

基于 requirement-breakdown.md，生成测试矩阵：

```markdown
| FR 编号 | 功能描述 | 测试场景 | 测试类型 | 预期结果 |
|---------|----------|----------|----------|----------|
| FR-A-001 | 创建订单 | 正常创建 | 集成 | 返回 201，数据库有记录 |
| FR-A-001 | 创建订单 | 空商品列表 | 边界 | 返回 400，不创建记录 |
| FR-A-002 | 重复创建 | 相同 bizId | 集成 | 返回已有订单，不重复创建 |
```

### Step 2: 编写测试代码

按矩阵逐项编写。每个测试遵循 AAA 模式：

```
Arrange — 准备测试数据和环境
Act     — 执行被测操作
Assert  — 验证结果
```

### Step 3: 运行并记录

1. 运行全部测试
2. 记录通过/失败结果
3. 失败的测试：先判断是代码 bug 还是测试写错
   - 代码 bug → 修复代码 → 重跑
   - 测试错误 → 修复测试 → 重跑

## 断言质量标准

### 好的断言

```java
// 验证业务行为
assertThat(order.getStatus()).isEqualTo(OrderStatus.CREATED);
assertThat(order.getTotalAmount()).isEqualByComparingTo(new BigDecimal("99.90"));
assertThat(orderRepository.findByBizId(bizId)).isPresent();
```

### 差的断言

```java
// 只验证非空 — 什么都没验证
assertNotNull(result);
assertTrue(true);
assertThat(result).isNotEmpty(); // 没验证具体内容
```

## 日志记录

在 `log/phase7-testing.md` 中记录完整的测试矩阵和执行结果：

```markdown
## 测试矩阵

| FR 编号 | 测试用例 | 类型 | 结果 | 备注 |
|---------|----------|------|------|------|
| FR-A-001 | test_FR_A_001_create_success | 集成 | ✅ PASS | |
| FR-A-001 | test_FR_A_001_empty_items | 边界 | ✅ PASS | |
| FR-A-002 | test_FR_A_002_duplicate | 集成 | ❌ FAIL → ✅ PASS | 修复了幂等逻辑 |

## 统计
- 测试总数: N
- 通过: N
- 失败后修复: N
- 覆盖率: xx%
```
