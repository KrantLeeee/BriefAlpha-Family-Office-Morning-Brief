## ADDED Requirements

### Requirement: LLM audit log 字段

audit-and-observability SHALL 为每次 LLM 调用写入：`request_hash, scope, cited_evidence_ids, response_hash, accuracy_validation_passed, call_type∈{text,vision,embedding}, provider, model, template_version, latency_ms, failure_state, audit_mode`。MUST NOT 默认保存原始 prompt 明文。

#### Scenario: 字段完整性

- **WHEN** 任一 LLM 调用结束
- **THEN** audit log 行包含上述全部字段；failure_state 在成功时为 `null`

#### Scenario: demo 模式无明文

- **WHEN** audit_mode=demo
- **THEN** 日志不含完整 prompt 与 alias_map snapshot

### Requirement: audit_mode 切换约束

`audit_mode` SHALL 由 admin 后台配置，从 `demo` 切到 `compliance` 前 MUST 二次确认；切换 MUST 仅影响切换后的新 brief / QA / PDF 处理；旧记录 MUST 保留切换前 audit_mode 标识，不能补作合规留痕。从 `compliance` 切回 `demo` MUST 二次确认并记录 reason；历史 compliance log 仍按原保留期保存。

#### Scenario: 旧记录不可追认

- **WHEN** 从 demo 切到 compliance
- **THEN** 切换前已生成的 audit log 仍标识 `audit_mode=demo`，UI / 导出报告显示该模式

#### Scenario: 双向切换记录

- **WHEN** 从 compliance 切回 demo
- **THEN** 系统弹出二次确认，记录 reason 与切换者 user_id

### Requirement: source_health 聚合

ingestion 调用 SHALL 实时写入 redis 计数；后台 SHALL 每 5 分钟聚合为 source_health 快照（4 类源 ok / degraded / failed + research 上传活跃数）；快照供 `/api/source-health` 与前端 chip 使用。

#### Scenario: 聚合周期

- **WHEN** 5 分钟聚合任务运行
- **THEN** redis 中存在最新 source_health JSON 快照

### Requirement: conservative_brief 监控

系统 SHALL 持续记录 `conservative_brief_triggered` 事件（含 brief_id / trigger_reason / failed_stage / source_health_snapshot）；月触发率 > 10% 或连续 3 个交易日触发 MUST 在 admin diagnostics 中提示进入数据源 / validator / prompt 排查。

#### Scenario: 月触发率告警

- **WHEN** 当月 conservative_brief_triggered 占比 > 10%
- **THEN** admin diagnostics 显示告警条目

### Requirement: 埋点事件

前端 SHALL 上报以下事件至本地埋点存储（不离开本地）：brief_view、judgement_row_click、drawer_open、drawer_close、evidence_article_click、qa_submit、qa_response_render、accuracy_validation_failed、source_degraded、sensitive_scan_blocked、conservative_brief_triggered、research_pdf_upload、research_pdf_third_party_consent、research_pdf_parse_complete、research_pdf_chunk_delete、research_reanalyze_click。每事件携带 PRD §5.3 表中的字段。

#### Scenario: drawer_close 携带时长

- **WHEN** 用户关闭 drawer
- **THEN** 事件 payload 含 brief_id、judgement_id、duration_ms、close_method

### Requirement: PDF 元数据与原文件留存

上传 PDF 元数据（filename / upload_time / user_id / file_id）SHALL 单独记录；原 PDF 加密本地存储默认保留 7 天，客户合规要求可延长。审计库独立加密存储，demo 默认保留 90 天。

#### Scenario: 原 PDF 7 天清理

- **WHEN** 上传 7 天后
- **THEN** 后台清理任务删除原 PDF 文件，但保留元数据与解析后的 chunks

### Requirement: alias_map 不入审计

audit log MUST NOT 直接持久化 alias_map 内容；reverse trace 时 SHALL 使用独立加密存储（已存在的 16:00 HKT 过期 alias_map）。

#### Scenario: 审计内不含 alias_map

- **WHEN** 检查任一 audit log 行
- **THEN** 不含 alias → ticker 反向映射明文

### Requirement: admin diagnostics

系统 SHALL 提供 admin diagnostics 视图（仅 admin 可访问）：source_health 历史、conservative_brief 触发统计、ticker_alias 缺失警告、第三方调用边界违规告警、audit_mode 切换历史。

#### Scenario: ticker 改名告警可见

- **WHEN** 每日 yfinance refresh diff 检测到 ticker 改名
- **THEN** admin diagnostics 显示需更新 `company_alias_zh.yml` 的条目
