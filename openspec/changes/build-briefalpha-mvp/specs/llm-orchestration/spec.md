## ADDED Requirements

### Requirement: 统一 audit wrapper

应用代码 MUST NOT 直接调用 LLM provider SDK；所有 Text / Vision / Embedding 调用 SHALL 经过统一 audit wrapper，wrapper 负责字段白名单组装、敏感扫描、调用记录、重试与降级。

#### Scenario: 直接调用被阻止

- **WHEN** 代码尝试 import provider SDK 并直接调用
- **THEN** lint / 单元测试拒绝合并；运行时 wrapper 之外的调用 MUST NOT 写入 audit log，且 audit-and-observability 能识别并告警

### Requirement: prompt 字段白名单

Text LLM prompt body SHALL 仅包含以下字段：`task_instruction`、`language`、`aliased_evidence`（含 evidence_id、title_aliased、excerpt_aliased、quote_span_aliased、source_tier、asset_class、published_at）、`output_constraints`、`output_schema`。MUST NOT 包含 portfolio_context、real ticker、real company name、exact weight、weight_band、sector、industry、region、exposure_bucket、portfolio_linkage、is_external、account_id、client_name、amount、原始 prompt debug 信息。

#### Scenario: 白名单校验

- **WHEN** wrapper 在发送前校验 request body
- **THEN** 出现任一禁用字段时立即阻断调用、写入 sensitive_scan_blocked 埋点，并触发降级路径

### Requirement: 输入端敏感扫描

发送 LLM request 前 wrapper SHALL 执行：(1) 正则匹配 alias_map 中真实 ticker / 本轮 detected_tickers 字面值；(2) 正则匹配 `数字+%` 组合；(3) 关键词扫描 `account_id / client_name / amount`；(4) JSON schema 白名单校验。任一命中 MUST 阻断调用并记录 alert。

#### Scenario: 真实 ticker 漏出

- **WHEN** 组装好的 prompt 仍含 `NVDA`
- **THEN** wrapper 阻断调用、写入 sensitive_scan_blocked、触发保守 brief

#### Scenario: 公司名漏出

- **WHEN** prompt 含 `Tencent` 或 `腾讯控股`
- **THEN** wrapper 通过 sensitive_entity_dictionary 检测命中，阻断调用并告警

### Requirement: 输出端反向敏感扫描

LLM 输出后 wrapper SHALL 对响应文本执行 sensitive_entity_dictionary 反向匹配；命中真实 ticker / 公司全名 / 简称 / 中文名时 MUST 触发一次重试；仍命中则由 renderer 用 alias 或安全占位替换，不直接展示未授权真实实体。

#### Scenario: 输出含真实 ticker

- **WHEN** LLM 自主生成 `NVDA`
- **THEN** 系统重试一次；二次仍命中则用 `E_a3f9` 替换或删除该段落

### Requirement: 失败必审计

wrapper SHALL 对每次 LLM 调用记录 audit failure record（含 request_hash、provider、model、template_version、failure_state、latency_ms），无论成功或失败。

#### Scenario: 调用超时

- **WHEN** Text LLM 调用 30 秒超时
- **THEN** audit log 写入 failure_state=`timeout`，并触发本阶段重试或降级

### Requirement: 重试与降级

主 brief Text LLM 调用 SHALL 最多重试 3 次；QA 调用每问题最多重试 1 次；vision LLM 按 PDF 页 / 图表限额；命中限额 MUST 进入 caption_unavailable。Embedding MUST 默认使用本地模型，第三方 embedding 默认禁用。

#### Scenario: 主 brief 重试上限

- **WHEN** brief 生成的 stage_b 连续失败 3 次
- **THEN** 进入保守 brief，不再发起新调用

#### Scenario: vision 限额

- **WHEN** PDF 单文件 caption 调用超过配置限额
- **THEN** 后续图表 chunk 标记 caption_unavailable，不阻塞文本 chunk

### Requirement: 第三方 embedding 显式开关

第三方 embedding API SHALL 默认禁用；显式开启时 wrapper MUST 在请求前完成 chunk 文本的 ticker_aliasing 与公司名替换。

#### Scenario: 默认本地

- **WHEN** PDF chunk 或新闻 chunk 需要向量化
- **THEN** wrapper 调用本地 embedding 模型（如 bge-small / sentence-transformers），不发出第三方请求

### Requirement: vision LLM 调用约束

Vision LLM 调用 SHALL 仅传入用户已 consent 处理的 PDF 页截图；request MUST NOT 携带 user_id / session_id / account_id / portfolio_id；vision 调用使用独立 API key，不复用带客户身份的会话；返回 caption MUST 经主 pipeline ticker_aliasing 后才能进入 evidence_pool。

#### Scenario: 未 consent 不调用

- **WHEN** 用户未勾选 third-party figure captioning consent
- **THEN** 系统跳过 vision 调用，对应图表 chunk 标记 `caption_unavailable_by_policy`

#### Scenario: 不带身份字段

- **WHEN** vision request 组装完成
- **THEN** request headers / body / query 不含 user_id / session_id / account_id / portfolio_id

### Requirement: accuracy_validator 一致性入口

LLM 输出 SHALL 在返回调用方之前必经 accuracy_validator（具体校验规则属 brief-pipeline）；validator 失败 MUST 由 wrapper 决定重试或降级。

#### Scenario: validator 拒绝

- **WHEN** validator 返回 invalid
- **THEN** wrapper 按调用类型策略重试一次或多次，最终失败时返回降级响应给调用方
