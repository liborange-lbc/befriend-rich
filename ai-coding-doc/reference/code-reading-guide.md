# Code Reading Guide

Phase 2a 的代码阅读方法。按顺序执行，用 subagent 并行读取独立模块。

## 六步下钻法

```
Step 1: 模块入口 ──────────────────────────────────────────
  目标：Controller / API Gateway routes
  读取：URL patterns, request/response DTOs, auth annotations
  工具：Grep "@RestController" / "@RequestMapping" in affected modules

Step 2: 领域模型 ──────────────────────────────────────────
  目标：Entity / DO classes in model/entity/domain packages
  读取：table mappings, field types, relationships, enums
  工具：Grep "@Table" / "@Entity" / "extends BaseDO"

Step 3: 核心业务流程 ──────────────────────────────────────
  目标：Service layer implementations
  读取：@Transactional scope, lock strategies, validation rules,
        external service calls, event publishing
  工具：Read *ServiceImpl.java for affected services

Step 4: 数据访问 ──────────────────────────────────────────
  目标：Mapper/Repository interfaces + XML SQL
  读取：complex queries, index usage hints, batch operations
  工具：Read *Mapper.java + *Mapper.xml side by side

Step 5: 边界交互 ──────────────────────────────────────────
  目标：RPC/HTTP clients, MQ producers/consumers, Cache patterns
  读取：failure modes, retry policies, idempotency mechanisms,
        Redis key design, TTL
  工具：Grep "@FeignClient" / "@RocketMQMessageListener" / "@Cacheable"

Step 6: 配置与基础设施 ────────────────────────────────────
  目标：application.yml, migration scripts
  读取：environment-specific configs, feature flags
  工具：Read application*.yml, Glob "db/migration/**"
```

## Spring Boot 项目目录约定

```
src/main/java/com/{company}/{project}/
├── controller/          ← Step 1: API 入口
│   └── XxxController.java
├── service/             ← Step 3: 业务逻辑
│   ├── XxxService.java          (interface)
│   └── impl/XxxServiceImpl.java (implementation)
├── model/               ← Step 2: 领域模型
│   ├── entity/XxxDO.java        (数据库映射)
│   ├── dto/XxxDTO.java          (传输对象)
│   ├── vo/XxxVO.java            (视图对象)
│   └── enums/XxxEnum.java
├── mapper/              ← Step 4: 数据访问
│   └── XxxMapper.java
├── client/              ← Step 5: 外部调用
│   └── XxxClient.java
├── config/              ← Step 6: 配置
│   └── XxxConfig.java
├── mq/                  ← Step 5: 消息
│   ├── producer/
│   └── consumer/
└── common/
    ├── constants/
    ├── exception/
    └── util/

src/main/resources/
├── mapper/              ← MyBatis XML SQL
├── application.yml
└── application-{env}.yml
```

## 关键注解速查

| 注解 | 设计含义 |
|------|----------|
| `@Transactional` | 事务边界——检查 scope 和 propagation |
| `@Async` | 异步执行——检查线程池配置 |
| `@Retryable` | 有重试——必须检查幂等 |
| `@Cacheable/@CacheEvict` | 有缓存——检查 key 设计和失效策略 |
| `@FeignClient` | RPC 调用——检查超时和 fallback |
| `@RocketMQMessageListener` | MQ 消费——检查幂等和顺序性 |
| `@Scheduled` | 定时任务——检查并发和分布式锁 |
| `@DistributedLock` | 分布式锁——检查粒度和超时 |
| `@RequiresPermission` | 鉴权——检查权限粒度 |

## MyBatis XML 审查要点

- `<select>`：WHERE 字段是否有索引？
- `<insert>`：批量还是单条？
- `<update>`：是否有乐观锁（version 字段）？
- `<foreach>`：集合是否可能很大（慢查询风险）？
- `${...}` vs `#{...}`：前者有 SQL 注入风险

## 代码阅读产出模板

```markdown
## 代码阅读报告

### 模块依赖图
[ASCII 或 drawio 图]

### 核心调用链
[每条关键流程：入口 → Service → DAO → 外部]

### 现有约束
- 事务边界: [哪里开始/结束]
- 锁策略: [乐观/悲观/分布式]
- 缓存策略: [key 设计, TTL, 失效方式]
- 幂等机制: [去重方式]

### 数据模型现状
- 涉及表: [表名 + 关键字段]
- 索引: [现有索引]
- 数据量级: [预估行数]

### 风险标记
- [脆弱的、未文档化的、不一致的发现]
```
