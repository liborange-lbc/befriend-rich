# Coding Phase Guide

Phase 6 的编码实现指南。

## 执行原则

1. **设计驱动** — 严格按 design-doc.md 实现，不自行添加设计中未提及的功能
2. **功能子项排序** — 按 requirement-breakdown.md 的编号顺序实现，优先 P0
3. **增量实现** — 每完成一个功能子项即可编译/运行验证，不攒到最后
4. **规范遵循** — 参照 system-knowledge/coding-conventions.md 中的项目规范

## 编码流程

### Step 1: 准备

1. 重读 design-doc.md 最终版本
2. 重读 code-reading-report.md，确认现有代码结构
3. 与用户确认编码范围（哪些模块、哪些文件）
4. 确认分支策略（新建分支还是在当前分支）

### Step 2: 按功能子项实现

对每个 FR-XXX 子项：

1. **定位** — 确认代码应该放在哪个包/模块/文件
2. **实现** — 编写代码
3. **编译验证** — 确保无编译错误
4. **标记** — 在日志中记录该子项实现完成

### Step 3: 整体验证

所有子项实现完成后：
1. 全量编译通过
2. 无明显的 IDE 警告（unused imports、unchecked casts 等）
3. 与设计文档交叉检查，确认无遗漏

## 代码组织约束

- 新增代码遵循现有项目的包结构
- 新增类/文件的命名遵循现有项目约定
- 分层规则：Controller → Service → Repository，不跨层调用
- 公共工具类放入对应的 util/common 包，不随意散落

## 与设计的对应关系

| 设计文档章节 | 对应代码 |
|-------------|---------|
| §3.1 接口设计 | Controller + Request/Response DTO |
| §3.2 数据模型变更 | Entity/DO + Mapper/Repository + SQL Migration |
| §3.3 缓存设计 | Cache 相关 Service 或 AOP |
| §3.4 消息设计 | Producer/Consumer + Message DTO |
| §2.3 核心流程 | Service 层业务逻辑 |

## 日志记录

每个功能子项实现后，在 `log/phase6-coding.md` 中记录：

```markdown
### FR-XXX: {功能描述}

**实现文件**:
- `src/.../XxxController.java` — 新增接口 POST /api/v1/xxx
- `src/.../XxxService.java:45-78` — 核心业务逻辑

**设计对应**: design-doc.md §3.1.2

**备注**: {如有遗漏/歧义/偏差，记录在此}
```
