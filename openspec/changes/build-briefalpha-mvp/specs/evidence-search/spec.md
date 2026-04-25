## ADDED Requirements

### Requirement: 本地全文检索

evidence_search SHALL 使用本地 SQLite FTS5 / BM25 或等价轻量检索；检索对象 MUST 为当日 evidence_pool（含 research_chunks），MUST NOT 检索全互联网。

#### Scenario: FTS 索引建立

- **WHEN** evidence 进入 evidence_pool
- **THEN** 同步写入 FTS5 虚拟表，可被关键字检索命中

### Requirement: scope 过滤

检索接口 SHALL 支持 scope=judgement / scope=evidence / scope=global。检索 MUST 先按 scope 过滤 evidence 子集，再执行全文检索；scope=global 仅在 P1 启用。

#### Scenario: judgement scope 限定

- **WHEN** scope=judgement 且 judgement_id=J1
- **THEN** 检索仅在 J1 的 evidence_ids 集合中进行

#### Scenario: 单 evidence scope

- **WHEN** scope=evidence 且 evidence_id=E1
- **THEN** 检索仅命中 E1 内文本

### Requirement: 无结果短路

若检索无结果 evidence_search MUST 直接返回 `insufficient_evidence`，wrapper SHALL NOT 调用 LLM。

#### Scenario: 无关问题

- **WHEN** 用户问与持仓 / 当日新闻无关的问题
- **THEN** 检索返回 0 命中，QA 接口直接返回 `out_of_scope` / `insufficient_evidence`

### Requirement: 增量索引与清理

evidence_pool 写入与删除 SHALL 与 FTS5 索引保持一致；当日 brief 过期或 evidence 被删除时 MUST 同步从索引中移除。

#### Scenario: 删除 chunk 同步索引

- **WHEN** 用户删除 PDF chunk
- **THEN** FTS 索引中对应行同步删除，后续检索不再命中

### Requirement: 检索字段范围

FTS 索引字段 SHALL 包含 evidence.title / excerpt / detected_tickers / chunk_type / source_tier，MUST NOT 包含 portfolio_linkage / weight_band / exposure_bucket。

#### Scenario: 字段约束

- **WHEN** 构建 FTS 索引
- **THEN** schema 中没有持仓相关字段
