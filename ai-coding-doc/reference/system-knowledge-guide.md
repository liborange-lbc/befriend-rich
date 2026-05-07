# System Knowledge Generation Guide

Phase 0 的系统知识生成规范。使用六步下钻法从代码中提取全局系统知识。

## 目标

生成 7 个系统知识文件，覆盖系统的全部技术维度。这些文件跨需求共享，是所有系分设计的全局上下文。

## 生成策略

### 全量生成（首次）

首次运行时，`system-knowledge/` 目录不存在或为空。启动 subagent 执行完整的六步下钻：

```
Step 1 模块入口 → architecture-overview.md + api-constraints.md
Step 2 领域模型 → domain-model.md
Step 3 核心业务 → coding-conventions.md
Step 4 数据访问 → data-dictionary.md
Step 5 边界交互 → middleware-inventory.md
Step 6 配置基础设施 → infra-config.md
```

### 增量更新（后续）

目录已存在时：
1. 检查 7 个文件是否都存在
2. 缺失的文件 → 针对性生成
3. 全部存在 → 抽样校验（选 2-3 个文件，与当前代码对比）
   - 发现过时内容 → 局部更新
   - 内容仍准确 → 跳过，记录"已验证"

## 各文件的生成规范

### 1. architecture-overview.md

```markdown
# 系统架构总览

## 架构风格
{monolith | microservice | modular-monolith}

## 服务/模块清单
| 服务名 | 职责 | 端口 | 依赖服务 |
|--------|------|------|----------|

## 分层结构
{Controller → Service → DAO 或其他分层}

## 部署拓扑
{单机 / 集群 / K8s / 描述}

## 模块依赖图
{ASCII 或 Mermaid 图}
```

**数据来源**: 项目根目录结构、pom.xml/build.gradle 模块定义、application.yml 端口配置

### 2. middleware-inventory.md

```markdown
# 中间件明细

## Redis
- 用途: {缓存 / 分布式锁 / 限流 / 会话}
- Key 设计: {前缀规范、TTL 策略}
- 使用模式: {@Cacheable / RedisTemplate / Redisson}

## 消息队列 (RocketMQ / Kafka)
- Topic 清单: {topic → 生产者 → 消费者}
- 消费模式: {集群 / 广播}
- 幂等机制: {去重方式}

## Elasticsearch
- 索引清单: {索引名 → 用途}
- 同步方式: {双写 / binlog / 定时任务}

## 其他
{按实际情况补充}
```

**数据来源**: Step 5 边界交互扫描结果、配置文件中的中间件地址

### 3. api-constraints.md

```markdown
# API 约束

## URL 命名规范
{RESTful / 自定义 / 举例}

## 版本策略
{URL 路径版本 /v1/ | Header 版本 | 无版本}

## 鉴权方式
{JWT / OAuth2 / Session / 自定义注解}

## 统一响应格式
{Response 包装类结构}

## 错误码体系
{错误码前缀、分段规则、示例}

## 限流规则
{全局 / 接口级 / 用户级}

## 分页约定
{PageRequest/PageResponse 结构}
```

**数据来源**: Step 1 模块入口扫描、现有 Controller 代码、全局异常处理器

### 4. domain-model.md

```markdown
# 领域模型

## 核心实体

### {EntityName}
- 表名: t_xxx
- 聚合根: 是/否
- 关键字段: {列出业务含义重要的字段}
- 状态流转: {状态机图，如有}

## 实体关系图
{Mermaid ER 图}

## 枚举定义
| 枚举类 | 值 | 含义 |
|--------|-----|------|

## 值对象
{跨实体共享的值对象定义}
```

**数据来源**: Step 2 领域模型扫描、Entity/DO 类、枚举类

### 5. coding-conventions.md

```markdown
# 编码规范

## 分层调用规则
{Controller → Service → DAO，不允许跨层调用等}

## 异常处理
{自定义异常体系、全局异常处理方式}

## 日志规范
{日志框架、级别使用、TraceId 传递}

## 命名约定
{类名/方法名/变量名/包名规范}

## 事务管理
{@Transactional 使用规范、传播级别}

## 其他约定
{从代码中观察到的一致性模式}
```

**数据来源**: Step 3 核心业务流程扫描、全局配置类、异常处理类

### 6. data-dictionary.md

```markdown
# 数据字典

## 核心表结构

### t_xxx
| 字段 | 类型 | 默认值 | 说明 | 索引 |
|------|------|--------|------|------|

**数据量级**: {预估}
**分表策略**: {如有}

## 索引清单
| 表名 | 索引名 | 字段 | 类型 |
|------|--------|------|------|

## 数据库命名规范
{表前缀、字段命名、时间字段约定}
```

**数据来源**: Step 4 数据访问扫描、Mapper XML、migration 脚本

### 7. infra-config.md

```markdown
# 基础设施配置

## 环境清单
| 环境 | 用途 | 配置文件 |
|------|------|----------|

## 配置中心
{Nacos / Apollo / Spring Cloud Config / 本地}

## Feature Flags
{使用方式、现有 flag 清单}

## CI/CD
{构建工具、流水线、部署方式}

## 监控告警
{Prometheus / Grafana / 自定义}
```

**数据来源**: Step 6 配置与基础设施扫描、application*.yml、Dockerfile、CI 配置

## Subagent 指令模板

启动系统知识生成 subagent 时，使用以下 prompt 结构：

```
你是系统知识提取 Agent。按六步下钻法阅读项目代码，生成系统知识文件。

目标文件: {要生成的文件名}
对应下钻步骤: {Step N}
输出路径: ./ai-coding-doc/system-knowledge/{filename}
日志路径: ./ai-coding-doc/requirements/{date}-{name}/log/phase0-knowledge-bootstrap.md

要求:
1. 按六步下钻法的对应步骤系统阅读代码
2. 遵循上方文件模板格式
3. 所有内容必须来源于代码，不得编造
4. 在日志文件中记录读了哪些文件、发现了什么
```

## 校验检查清单

生成完成后自检：

- [ ] 7 个文件全部存在
- [ ] 每个文件都有实质内容（不是空模板）
- [ ] 架构图/ER 图使用 Mermaid 语法，可渲染
- [ ] 数据来源可追溯（日志中有记录）
- [ ] 与当前代码一致（非过期信息）
