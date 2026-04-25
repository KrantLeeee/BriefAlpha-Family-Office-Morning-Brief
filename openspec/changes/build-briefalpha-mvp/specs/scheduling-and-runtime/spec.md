## ADDED Requirements

### Requirement: brief 生成 cron

scheduler SHALL 在 07:00 HKT 触发滚动采集，07:55 HKT freeze evidence_pool 并启动 brief-pipeline；08:30 HKT 前 MUST 完成首个可读 brief；总耗时 ≤ 90 秒。

#### Scenario: 准时交付

- **WHEN** 07:55 触发 freeze
- **THEN** 08:30 HKT 用户访问主页时 brief 已写入 redis

#### Scenario: 90 秒预算

- **WHEN** pipeline 与 LLM 总耗时 > 90 秒
- **THEN** 触发 stale 降级路径（提供上一日 brief）

### Requirement: PDF 解析队列

PDF 上传 SHALL 进入后台解析队列，单文件目标 ≤ 60 秒（10MB 内）；超过显示 queued / processing；re-analyze 与主 pipeline 互斥，re-analyze 排队等待主 pipeline 完成。

#### Scenario: re-analyze 排队

- **WHEN** 主 pipeline 正在运行时触发 re-analyze
- **THEN** re-analyze 在主 pipeline 完成后立即开始，前端显示 queued

### Requirement: alias_map 清理任务

scheduler SHALL 在每日 16:00 HKT 触发清理任务删除当日 alias_map ciphertext；MUST NOT 提前删除。

#### Scenario: 16:00 清理

- **WHEN** 时钟到 16:00 HKT
- **THEN** 当日 alias_map 文件被删除，QA 调用此后返回 `brief_expired`

### Requirement: 原文件 / 审计库定期清理

scheduler SHALL 每日清理超过保留期的原始 API response（7 天）、PDF 原文件（默认 7 天）、demo 模式 audit log（90 天）；compliance 模式按客户合规期保留。

#### Scenario: 7 天 PDF 清理

- **WHEN** 文件 ctime 超过 7 天
- **THEN** 后台清理任务删除原 PDF，但 metadata 与 chunks 保留

### Requirement: redis 键约定

系统 SHALL 在 redis 中使用以下命名空间：`brief:{date}`（当日 brief 缓存，TTL 至次日 freeze）、`source_health:latest`、`qa:context:{brief_id}:{scope}`（保留 3 轮）、`research:queue`、`reanalyze:queue`。MUST NOT 在 redis 中存储 alias_map 明文。

#### Scenario: 命名空间隔离

- **WHEN** 检查 redis keys
- **THEN** 上述前缀清晰分布；无 alias_map 键

### Requirement: 配置开关

系统 SHALL 提供以下配置开关：`llm_provider∈{anthropic,openai}`、`data_sources` 单源启用 / 禁用、`degradation_threshold`（默认 30%）、`exposure_bucket_rules`（仅本地）、`k_anonymity_threshold`（默认 3）、`coarse_bucket_mode`（持仓 ticker < 15 自动开启，admin 可强制）、`auto_expand_universe`（默认 false）、`research_upload_limit`（默认 5）、`audit_mode∈{demo,compliance}`（仅 admin）、`brief_timezone`、`brief_delivery_time`。

#### Scenario: provider 切换

- **WHEN** 配置 `llm_provider=openai`
- **THEN** wrapper 使用 OpenAI provider，audit log 中 provider 字段相应更新

### Requirement: 多租户与时区边界

MVP 默认单租户 HKT；多租户生产扩展 MUST 按 tenant_id 隔离 portfolio / PDF / alias_map / audit log / universe；非 HKT 客户必须配置 `brief_timezone` 与 `brief_delivery_time`。

#### Scenario: 单租户演示

- **WHEN** MVP 启动
- **THEN** 所有数据归属默认 tenant_id，无跨租户访问路径

### Requirement: 失败隔离

scheduler SHALL 隔离不同任务失败：单源失败 MUST NOT 阻塞其他源；PDF 解析失败 MUST NOT 影响 brief 生成；alias_map 清理失败 MUST 不影响交易日 brief 生成且写入 admin alert。

#### Scenario: PDF 解析失败隔离

- **WHEN** 一份 PDF 解析失败
- **THEN** 其他 PDF 与主 brief 流程不受影响
