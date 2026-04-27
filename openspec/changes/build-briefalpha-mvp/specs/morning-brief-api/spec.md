## ADDED Requirements

### Requirement: GET /api/brief/today

后端 SHALL 暴露 `GET /api/brief/today` 返回当日 MorningBrief 视图模型，含 `brief_id / generated_at / morning_base_case / ai_judgement_summary（含 [n] 引用占位）/ judgements / cited_evidence_ids / source_health_snapshot / degradation_note? / playbook_events / portfolio_snapshot / brief_timezone / audit_mode`。响应中 ticker / 公司名 MUST 已完成反映射，alias_map MUST NOT 下发。

#### Scenario: 正常 brief

- **WHEN** 用户在 08:30 HKT 后请求该端点
- **THEN** 返回 200 + 完整字段，ai_judgement_summary 内嵌 `[1][2]` 引用，且 cited_evidence_ids 与 evidence_pool 对应

#### Scenario: 保守 brief

- **WHEN** pipeline 触发保守 brief
- **THEN** 返回 200，judgements 为空数组，degradation_note 含原因，portfolio_snapshot 仍提供

### Requirement: GET /api/judgement/{id}/drawer

后端 SHALL 暴露 `GET /api/judgement/{id}/drawer` 返回 `{judgement, reasoning_chain, evidences[], suggested_questions[]}`，alias 已反映射。同会话同 judgement MUST 可缓存。

#### Scenario: drawer 数据完整

- **WHEN** 用户首次点击某 judgement
- **THEN** 响应含 reasoning_chain 四层 + evidences（含 quote_span_original / source_tier / supplementary_sources）+ 3 个 suggested_questions

#### Scenario: drawer 超时

- **WHEN** 后端处理 > 10 秒
- **THEN** 返回 504 / 等价错误，前端展示 retry 按钮

### Requirement: POST /api/qa

后端 SHALL 暴露 `POST /api/qa`，body=`{brief_id, question, scope: judgement|evidence|global, judgement_id?, evidence_id?}`。后端在转发给 LLM 前 MUST 完成两步 anonymization，且两步均不可跳过：

(a) **问题端**：用对应 brief_id 的 alias_map 替换用户问题中的真实 ticker / 公司名（基于 sensitive_entity_dictionary 命中规则）；

(b) **证据上下文端**：`scope=judgement` 从 cached brief 解析该 judgement drawer 展示的全部 evidence_ids（含 supplementary_sources）；`scope=evidence` 直接使用单条 evidence；`scope=global` 才由 evidence-search 从 `evidence_pool_full` 检索得到 raw evidence 子集。所有 raw evidence MUST 经 data-anonymization 模块批量转换为 `AliasedEvidence`（白名单字段、aliased title / excerpt / quote_span）后才能拼入 LLM prompt。MUST NOT 直接把 FTS 索引行（含原始 title / excerpt / detected_tickers）或 raw evidence 拼入 prompt；wrapper 输入端字段白名单校验对未 aliased 的 payload MUST 阻断。

响应含 `answer, cited_evidence_ids, quote_spans_original, validation_passed`，并经 data-anonymization 的"安全反映射"（仅 cited evidence 上下文内的 alias 才还原；其他 alias 视为 `unsafe_generated_alias` 保持占位）。

#### Scenario: scope=judgement

- **WHEN** scope=judgement、judgement_id 提供
- **THEN** QA 使用该 judgement drawer 展示的全量 evidence_ids 作为上下文，回答 cited_evidence_ids ⊆ 该 judgement 的 evidence_ids；不得因用户问题未命中 FTS 关键词而短路

#### Scenario: scope=evidence 单条

- **WHEN** scope=evidence、evidence_id 提供
- **THEN** QA 使用该 evidence_id 作为唯一上下文，cited_evidence_ids 只能含该 evidence_id

#### Scenario: scope=global（P1）

- **WHEN** scope=global
- **THEN** 检索覆盖全部 `evidence_pool_full`，回答仍含 ≥ 1 cited_evidence_ids 与 quote_span_original

#### Scenario: evidence context 必经 anonymization

- **WHEN** QA handler 解析出 raw evidence 上下文（来自 drawer / 单条 evidence / global search）
- **THEN** QA handler 先调用 anonymization 批量生成 AliasedEvidence 才组装 prompt；wrapper 输入端字段白名单校验拒绝任何含原文 ticker / 公司名的 payload

#### Scenario: alias_map 已过期

- **WHEN** brief_id 对应 alias_map 已被 16:00 HKT 清理
- **THEN** 返回 410 + `brief_expired`，前端提示重新生成

#### Scenario: 校验连续失败

- **WHEN** validator 连续 3 次失败
- **THEN** 返回 200 + `Unable to answer based on current sources, please rephrase`

### Requirement: GET /api/source-health

后端 SHALL 暴露 `GET /api/source-health` 返回 4 类源（market / news / official / research）的状态（ok / degraded / failed）、最近失败时间与 research 上传活跃数。

#### Scenario: research 无上传

- **WHEN** 当前用户 active research_uploads = 0
- **THEN** research 行返回 `no_uploads`，不计入 degraded

### Requirement: GET /api/portfolio

后端 SHALL 暴露 `GET /api/portfolio`（仅授权用户）返回真实持仓 / watchlist / weight；该端点响应 MUST NOT 被复用作 LLM 输入。

#### Scenario: 仅授权用户

- **WHEN** 未授权请求
- **THEN** 返回 401 / 403，且不返回任何持仓字段

### Requirement: 缓存与 stale 语义

`/api/brief/today` 响应 SHALL 优先来自 redis 当日缓存；缓存失效时 SHALL 按需重跑 pipeline；90 秒内未完成 MUST 返回上一日 brief（不含 portfolio）并标记 `stale=true`。

#### Scenario: 缓存命中

- **WHEN** redis 当日 brief 存在
- **THEN** 端点直接返回缓存版本，不触发 LLM 调用

#### Scenario: stale 降级

- **WHEN** redis 失效且 90 秒内 pipeline 未完成
- **THEN** 返回上一日 brief、置 `stale=true`、不返回 portfolio_snapshot

### Requirement: 错误响应规范

所有读取端点 MUST 使用一致错误结构：`{error: {code, message, retry_after?}}`；degradation_note 与 source_health 用于显示文案，不复用 error 字段。

#### Scenario: 一致错误结构

- **WHEN** 端点返回 4xx / 5xx
- **THEN** body 含 `error.code` 字符串与 `error.message` 文案
