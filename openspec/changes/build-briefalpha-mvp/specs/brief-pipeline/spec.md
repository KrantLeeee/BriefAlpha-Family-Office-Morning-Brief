## ADDED Requirements

### Requirement: 九阶段处理 pipeline

系统 SHALL 按以下顺序执行 brief 生成流水线：normalize → entity_linking → dedupe → base_scoring → portfolio_mapping → conflict_resolve → final_scoring (BPS) → evidence_selection → anonymization。conflict_resolve MUST 在 final_scoring 之前完成（使 final_scoring 的 market_confirmation 因子可基于 conflict 标记降权，且避免冲突来源被 LLM 合成为单一确定结论）；anonymization MUST 是离开内部数据模型进入 LLM 输入前的最后一步。

#### Scenario: 端到端流水线

- **WHEN** 50 条 raw_items 进入 pipeline
- **THEN** 输出 `evidence_pool_full` 保留全部去重后 evidence；`selected_evidence_for_llm` ≤ 20 条按 final_impact_score 降序，且每条携带完整的 score_breakdown（含 portfolio_linkage、market_confirmation 等六项因子）

#### Scenario: 冲突在 final_scoring 之前

- **WHEN** dedupe 完成且 conflict_resolve 标记某条 evidence 为 conflict=true
- **THEN** 后续 final_scoring 的 market_confirmation 因子据此降低，evidence 仍可能进入 selected_evidence_for_llm 但展示为「需人工复核」

### Requirement: BPS 评分

final_impact_score MUST 通过 BPS 公式计算：`base_score × portfolio_linkage × event_materiality × market_confirmation`，其中 base_score = source_reliability × recency_weight × novelty_weight，所有因子使用 PRD §2.2 定义的取值表。

#### Scenario: 完整 score_breakdown

- **WHEN** 一条 evidence 进入 evidence_pool 顶部
- **THEN** 该 evidence 的 score_breakdown 包含且仅包含 `source_reliability / recency_weight / novelty_weight / portfolio_linkage / event_materiality / market_confirmation` 六项数值字段

#### Scenario: novelty 与 market_confirmation 不抵消

- **WHEN** 同一事件被多个独立来源印证
- **THEN** novelty_weight 仍为 1.0（事件是新的），market_confirmation 取 1.0，不出现"被印证反而扣分"的情形

### Requirement: dedupe 与 supplementary_sources

dedupe 阶段 SHALL 按 content_hash 与本地 embedding 相似度合并同事件；相似度 ≥ 0.90 自动合并，0.80–0.90 进入 candidate cluster 由实体 + 时间窗 + source_tier 再判定；被合并来源 MUST 写入主 evidence 的 supplementary_sources 字段。

#### Scenario: 主源选择

- **WHEN** 两条 content_hash 相同的 evidence 来自不同 source_tier（official 与 news）
- **THEN** 主源选择 source_tier 更高（official），news 来源进入 supplementary_sources，不被丢弃

#### Scenario: 同 tier 优先原始发布源

- **WHEN** 两条相似 evidence 同属 news tier，分别来自原始发布源与转载源
- **THEN** 主源按 url 主域名判定为原始发布源；若仍相同，则保留 published_at 更早者

### Requirement: 结构化冲突检测

冲突检测 SHALL 作为独立 stage 在 dedupe 之后、final_scoring 之前执行；触发条件包括：高可信来源关键数字差异超阈值、同事件方向相反（beat/miss、raise/cut）、官方公告与新闻解读不一致。命中冲突的 evidence MUST 标记 `conflict=true / requires_review=true`，保留双方 quote_span；该标记 SHALL 被 final_scoring 的 market_confirmation 因子读取以降权，且 LLM MUST NOT 被授权裁决冲突。

#### Scenario: 数字冲突

- **WHEN** Reuters 与 Bloomberg 对同一公司 EPS 报道差异 > 阈值
- **THEN** 两条 evidence 均标记 conflict=true、requires_review=true，进入 brief 时显示"需人工复核"

#### Scenario: 方向冲突

- **WHEN** 一条来源写 `raises guidance`，另一条写 `cuts guidance`
- **THEN** 两条均标记 conflict=true，LLM 不输出谁对谁错的裁决性结论

### Requirement: evidence_pool_full 与 selected_evidence_for_llm

evidence_selection 阶段 SHALL 输出两个集合：(a) `selected_evidence_for_llm`：按 final_impact_score 降序的 top_k 条，默认 top_k=20，作为 stage_a / stage_b LLM 的输入；(b) `evidence_pool_full`：当日所有去重 + 评分后的 evidence（含 selected 与未选中部分），用于 evidence-search、QA、drawer 扩展查询、admin 追溯。两集合 MUST 共享同一份 evidence 实体（同一 `evidence_id` 不双写），仅以 `selected_for_llm: bool` 字段区分。

#### Scenario: top_k 截断与全集保留

- **WHEN** pipeline 完成 stage_8
- **THEN** `selected_evidence_for_llm` ≤ 20 条进入 LLM stage_b；`evidence_pool_full` 完整保留全部去重后 evidence 供 QA / drawer / 检索使用

#### Scenario: drawer 扩展查询命中未选 evidence

- **WHEN** 用户在 drawer 中通过 local_qa 追问命中一条未进入 selected 的 evidence
- **THEN** evidence-search 在 evidence_pool_full 中找到并返回，QA 流程仍按 anonymization → wrapper 路径走

### Requirement: 三阶段 LLM 生成

LLM 生成 SHALL 分三阶段：stage_a（morning_base_case ≤ 50 字 + ai_judgement_summary ≤ 200 字 含 ≥2 引用）、stage_b（1-5 条 judgement，每条含 reasoning_chain 四层）、stage_c（playbook_events）。MUST NOT 出现"建议买入/卖出"等动作动词。

#### Scenario: 字数约束

- **WHEN** stage_a 输出 ai_judgement_summary > 200 字
- **THEN** 系统截断到最近句号并触发一次重试，仍超长则进入保守文案

#### Scenario: judgement 不强行凑满

- **WHEN** 当天有效 judgement 仅 1 条
- **THEN** brief 输出 1 条，不强行凑足 3 条

### Requirement: accuracy_validator 校验

每次 LLM 输出后系统 SHALL 执行 PRD §2.6 的 11 项校验：cited_evidence_ids 存在、quote_span 可定位、observed 关键数字可在 quote_span 内找到、ai_judgement_summary 引用 ≥ 2 条、定性结论有 quote_span 锚定、数字一致性、极性一致性、时间窗一致性、输出敏感扫描。任一失败 MUST 触发一次重试，再失败则降级保守 brief 或删除问题段落。

#### Scenario: 引用不可定位

- **WHEN** LLM 返回的 quote_span 在 evidence 原文中找不到匹配
- **THEN** validator 拒绝该输出，触发一次重试

#### Scenario: 数字不一致

- **WHEN** LLM 输出"上调 50bp"，但引用的 quote_span ±120 字符内只能找到"30bp"
- **THEN** validator 拒绝该输出，触发一次重试

#### Scenario: 时间窗不一致

- **WHEN** LLM 写"昨晚"，但引用的 evidence.published_at 在 brief 当日 10:00 HKT
- **THEN** validator 按时间窗规则判定为不合格，要求重写为绝对日期或删除相对时间词

#### Scenario: 连续失败降级

- **WHEN** 同一 brief 的 accuracy_validator 连续 3 次失败
- **THEN** 系统输出保守 brief（不抛错），并触发 conservative_brief_triggered 埋点

### Requirement: 双坐标 quote_span

quote_span 校验 MUST 使用双坐标：LLM 侧返回 `quote_span_aliased`；本地通过 data-anonymization 模块的 replacement segment list 转换为 `quote_span_original` 后再在原文定位。转换正确性约束（segment list 结构、跨 segment 失败处理、cumulative offset 仅作优化）由 `data-anonymization` 的 "replacement segment list 与 quote_span 双坐标转换" requirement 定义；validator MUST 直接调用该模块导出的转换函数，MUST NOT 自行实现近似算法。

#### Scenario: aliased → original 还原

- **WHEN** LLM 返回 `quote_span_aliased: {start: 50, end: 120}` 引用 alias `E_a3f9`
- **THEN** 本地通过 segment list 转换为对应原文偏移 `quote_span_original`，并能在 evidence 原文中定位

#### Scenario: 转换函数失败

- **WHEN** anonymization 转换函数返回失败（如 quote_span_aliased 落在 alias 内部）
- **THEN** validator 视为 quote_span 不可定位，触发一次重试；连续失败仍计入 §"accuracy_validator 校验"的 3 次降级阈值

### Requirement: 保守 brief

仅在以下任一情况系统 MUST 输出保守 brief：(a) `evidence_pool_full` 为空；(b) Text LLM 所有 provider 调用全部失败（含 fallback 后仍失败）；(c) accuracy_validator 在同一 brief 内连续失败 3 次。保守 brief：固定文案 morning_base_case + summary、不输出 judgements、portfolio_map 与 macro_pulse 仍展示。

bucket / k-anonymity 失败 MUST NOT 触发保守 brief；该路径走"无 portfolio linkage 降级"。

#### Scenario: evidence_pool 为空

- **WHEN** freeze 时 `evidence_pool_full` 长度为 0
- **THEN** brief 输出固定中英文保守文案，judgements 数组为空，portfolio_map 仍渲染

#### Scenario: bucket 失败不触发保守 brief

- **WHEN** 所有 bucket 即使合并到 other_equity 仍不满足 k=3
- **THEN** 系统 MUST NOT 进入保守 brief，而是按"无 portfolio linkage 降级"路径正常生成市场 / 宏观 brief

### Requirement: 无 portfolio linkage 降级

当所有 bucket 即使合并到 other_equity 仍不满足 k=3、或 portfolio-context 冷启动校验未通过时，pipeline MUST 仍正常生成市场 / 宏观相关 brief，但：(a) portfolio_linkage 因子统一取值 0.3（"通用市场"），不向 LLM 暴露任何持仓相关信号；(b) 受影响的 judgement 标注 `no_direct_portfolio_link=true`；(c) 前端在 ai_judgement_summary 顶部展示提示文案 `Portfolio linkage unavailable today; market-level analysis only.`；(d) source_health.research / market / news / official 不因此变 degraded。

#### Scenario: 全部 bucket 不满足 k=3

- **WHEN** 所有 bucket 合并后仍不满足 k=3
- **THEN** brief 正常生成市场 / 宏观判断；judgements 数组中相关条目带 `no_direct_portfolio_link=true`；不进入保守 brief；前端显示对应提示文案

#### Scenario: 冷启动校验未通过

- **WHEN** portfolio-context 冷启动校验失败（universe 无法满足稀释约束）
- **THEN** pipeline 跳过 portfolio_mapping 的细粒度映射，所有 evidence 的 portfolio_linkage = 0.3，brief 仍照常生成市场 / 宏观判断

### Requirement: 时间窗规则集

时间表达校验 MUST 按 PRD §2.6 表使用 IANA 时区数据（Asia/Hong_Kong、America/New_York），不得手写 DST 偏移；"最新 / 刚刚"窗口 ≤ 4 小时。

#### Scenario: 美股盘后窗口

- **WHEN** evidence 来源时间为美东 17:30
- **THEN** 系统按 NYSE 交易日历判定为"美股盘后"，转换为 HKT 后展示
