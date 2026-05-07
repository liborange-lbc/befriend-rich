# Design Document Template

Phase 3 的系分文档模板和格式规范。

## 文档骨架

先生成骨架让用户确认，再填充内容。

```markdown
# [Feature Name] 系统设计

## 1. 背景与目标
### 1.1 业务背景
### 1.2 设计目标
### 1.3 术语表

## 2. 整体方案
### 2.1 架构图
### 2.2 模块划分
### 2.3 核心流程（时序图）

## 3. 详细设计
### 3.1 接口设计
### 3.2 数据模型变更
### 3.3 缓存设计（如需要）
### 3.4 消息设计（如需要）

## 4. 非功能设计
### 4.1 性能方案
### 4.2 高可用方案
### 4.3 安全方案

## 5. 兼容性与发布
### 5.1 向前/向后兼容
### 5.2 数据迁移方案
### 5.3 灰度/回滚方案
### 5.4 发布顺序

## 6. 风险与应对

## 7. 排期估算

## 8. 附录
### 8.1 代码阅读报告
### 8.2 参考文档
```

## 接口设计格式

每个新增/修改的 API 按此格式编写：

```markdown
#### [接口名称]

- **Path**: POST /api/v1/xxx
- **Auth**: @RequiresPermission("xxx:write")
- **Idempotent**: 基于 bizId 去重 / Token 机制 / 无需
- **Request**:
  ```java
  public class XxxRequest {
      @NotNull private Long bizId;
  }
  ```
- **Response**:
  ```java
  public class XxxResponse {
      private Long id;
  }
  ```
- **Error Codes**: BIZ_001 场景A, BIZ_002 场景B
- **Rate Limit**: N QPS per user
- **Notes**: [边界场景说明]
```

## 数据模型变更格式

```markdown
#### 表名: t_xxx

**变更类型**: 新建 / 加字段 / 加索引

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| id | bigint | auto_increment | 主键 |
| biz_id | varchar(64) | - | 业务ID |

**索引变更**:
- ADD UNIQUE INDEX `uk_biz_id` (`biz_id`)

**数据迁移**: [是否需要？预估耗时？是否锁表？]
**容量预估**: [日增量、总量、是否需要分表]
```

## 时序图格式

使用 Mermaid sequenceDiagram 语法，或 ASCII 时序图。每条核心流程一张图。
