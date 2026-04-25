# BriefAlpha PRD

## 1. 背景 & 目标

家族办公室合伙人每日晨会前需要从微信截图、彭博推送、研报 PDF、雪球观点等分散信息源手动梳理市场动态。BriefAlpha 接入多源公开数据与用户上传的研报，经本地信息处理 pipeline 生成一份结构化晨报。范围限定港股与美股。

- 目标用户：家族办公室合伙人、私行投资顾问
- 可量化目标：
  - 晨报生成总耗时 ≤ 90 秒，每日 08:30 HKT 前交付
  - 单次阅读完成时间 ≤ 5 分钟
  - 每条 judgement 引用 ≥ 2 条 evidence，引用原文片段可定位
  - 第三方 Text LLM / embedding / vision 调用 request body 不含客户持仓结构、具体 weight 数字、account_id、client_name、amount
  - Text LLM 与第三方 embedding 调用不得包含真实 ticker / 公司名；MVP 默认使用本地 embedding
  - 用户上传研报从完成解析到可被引用 ≤ 60 秒（10MB 以内 PDF）

### 1.1 Demo 边界与设计依据

BriefAlpha MVP 是可闭环 demo，不承诺完整金融合规系统。安全设计遵循三条轻量原则：

1. **最小必要披露**：参考 NIST Privacy Framework / data minimization 思路，第三方 Text LLM 只接收完成表达任务所需的 aliased evidence、quote_span、source_tier、asset_class；持仓关联、bucket、weight、sector 全部在本地完成。
2. **假名化不等于匿名化**：`E_xxxx` 只能降低直接泄露风险，不能单独抵御重识别。因此 PRD 不把 alias 当作充分匿名化手段，必须配合字段白名单、输出扫描和本地反映射。
3. **demo 可解释，生产留接口**：参考 OWASP LLM Top 10 对 sensitive information disclosure / overreliance 的风险分类，MVP 只做字段白名单、引用校验、敏感扫描、基础审计；生产部署再开启合规审计模式、客户 security master、正式法务授权与长期留痕。

---

## 2. 名词解释

| 名词 | 定义 |
|------|------|
| morning_base_case | 一句话概括今日晨会讨论主题，中文 ≤ 50 字 |
| ai_judgement_summary | AI 详细研判摘要，中文 ≤ 200 字，必须引用 ≥ 2 个 evidence_ids |
| judgement | AI 生成的 1-5 条核心观点之一，按 review 优先级排序；MVP 默认目标为 3 条，但不强行凑满 |
| judgement_level | 枚举：elevated / watch / holding |
| evidence | 单条原始信息单元，含 source、published_at、fetched_at、url、excerpt、content_hash、detected_tickers、source_tier、quote_span |
| research_chunk | 用户上传 PDF 解析后的单个信息块，是 evidence 的一个子类，含 page_number、bbox、chunk_type（text / table / figure_caption） |
| quote_span | evidence 在原文中的起止位置；PDF 源为 `{page, bbox}`，其他源为字符偏移 |
| reasoning_chain | judgement 的四层推理：observed → portfolio_exposure → inference → conclusion |
| evidence_drawer | 从 judgement 触发的侧边抽屉 |
| source_tier | 数据源可信度：official / market / news / research |
| source_reliability | official=1.0 / market=0.9 / news=0.7 / research=0.5 |
| impact_score | evidence 综合评分，公式见 brief_generation_pipeline |
| universe | 本地预配置可采集标的池（持仓 + watchlist + 行业代表 + 宽基代表 + decoy tickers），不得让任一单客户持仓可由 API query 反推 |
| exposure_bucket | 本地脱敏持仓归类；MVP 仅在后端用于 portfolio_mapping / scoring，不进入 Text LLM prompt |
| weight_band | bucket 权重区间：low (0-15%) / medium (15-30%) / high (30-50%) / dominant (>50%) |
| ticker_alias | LLM 输入中 ticker 的无语义匿名代号，格式 `E_a3f9` / `E_7b21`；不得在名称或伴随字段中携带行业、地区、是否外部标的等语义 |
| alias_map | 本地 ticker ↔ alias 双向映射表，按 brief_id 加密保存至当日 16:00 HKT，仅用于 QA 与反映射 |
| k_anonymity_threshold | exposure_bucket 成立的最小 ticker 数，默认 k=3 |
| portfolio_impact_map | evidence 与 exposure_bucket 的本地映射 |
| accuracy_validator | 本地服务，校验引用存在、quote_span 可定位、数字一致、方向/极性一致、时间窗一致，并执行输出反向敏感扫描 |
| parse_report | PDF 上传后的解析结果报告，展示成功率、识别 ticker、chunk 类型分布等 |
| multimodal_caption | 对 PDF 中图表使用 vision LLM 生成的文本描述；vision 调用不传 user_id/session_id/account 信息 |
| playbook_event | 今日需关注的时间节点事件 |
| portfolio_map | 持仓 treemap 可视化 |
| source_health | 四类数据源状态：ok / degraded / failed |

---

## 3. 用户场景

### 3.1 用户角色

| 角色 | 核心目标 |
|------|---------|
| 家族办公室合伙人 | 5 分钟内把握今日市场与持仓要点；默认看到压缩版 base_case、AI 研判和少量 judgement |
| 私行投资顾问 | 基于晨报为客户准备素材，需引用原文；默认展示 citation 与合规免责声明 |
| 投资分析师 | 追溯 judgement 原始数据链路，上传有处理权限的研报补充 AI 视角；默认展开 score_breakdown、evidence 与冲突标记 |

### 3.2 用户流程

**主流程：晨报生成与阅读**

```
cron 触发（每日 07:00 HKT 开始滚动采集）
→ ingestion 多源采集（market / news / official，按 privacy-safe universe 批量查询）
→ 07:55 HKT freeze 当日 evidence_pool
→ 加载已上传 research_chunk（若存在）
→ normalize → entity_linking → dedupe → portfolio_mapping → final_scoring
→ ticker_aliasing + 最小资产类别脱敏
→ llm_generation（stage_a base_case + summary / stage_b judgements / stage_c playbook）
→ accuracy_validator 校验
→ 本地反映射 alias → ticker
→ 缓存至 redis
→ 用户 08:30 打开主页渲染完成
```

**PDF 上传流程**

```
用户点击 "Upload research"
→ 选择 PDF 文件（≤ 10MB）
→ 前端校验格式与大小
→ POST /api/research/upload
→ 后端存储原 PDF（加密本地存储，保留 7 天）
→ parse_pipeline（extraction → OCR fallback → chunk → caption → local_embedding）
→ 返回 parse_report（成功率、chunk 数、识别 ticker 等）
→ 用户查看 parse_report，确认或删除个别 chunk
→ 用户点击 "Re-analyze with uploads"
→ 重跑 LLM generation（不重新采集行情/新闻）
→ 新 brief 覆盖当前缓存
```

**深度验证与追问流程**

```
用户点击 judgement 行
→ drawer 展示 reasoning_chain + evidence 列表
→ 用户点 read_full_article 跳原文（PDF evidence 跳转到对应页码）
→ 用户输入 local_qa 追问
→ LLM 回答 + 引用校验 + alias 反映射
→ 渲染带 citation 的回答
```

---

## 4. 功能需求

### 4.1 功能列表

| 优先级 | 模块 | 功能 |
|-------|------|------|
| P0 | 后端 | data_ingestion（多源采集，≥ 3 类真实公开数据源） |
| P0 | 后端 | brief_generation_pipeline（信息处理 + 脱敏 + 生成 + 引用校验） |
| P0 | 前端 | morning_base_case_and_ai_summary（AI 研判输出） |
| P0 | 后端+前端 | local_evidence_qa（针对 judgement / evidence 的原文追问） |
| P1 | 后端+前端 | research_pdf_upload（用户上传研报 + 解析 + 信任展示） |
| P1 | 后端+前端 | global_evidence_qa（基于全部 evidence_pool 的全局追问） |
| P1 | 前端 | judgement_list（三行判断列表） |
| P1 | 前端 | evidence_drawer（推理链 + 证据卡片 + 增强 local_qa 体验） |
| P1 | 前端 | portfolio_map（持仓可视化） |
| P1 | 前端 | source_health（数据源状态） |
| P2 | 前端 | playbook（完整时间线；MVP 首屏仅展示 2 条 preview） |
| P2 | 前端 | watchlist_item（完整观察列表；MVP 仅在 portfolio_map 下方展示 watchlist preview） |
| P2 | 前端 | macro_pulse（完整宏观面板；MVP 仅展示折叠入口） |
| P2 | 状态 | audit_transparency（LLM 调用哈希与数据源透明度说明） |

### 4.2 功能明细

---

## Feature: data_ingestion（P0）

### 1. 描述

从三类真实公开数据源按本地预配置 universe 采集信息。不按客户组合动态生成查询，避免通过 API 流量反推客户持仓。研报数据通过 `research_pdf_upload` feature 进入 evidence_pool，不在此 feature 自动采集。

### 2. 功能详细说明

#### 2.1 数据源清单与选择理由

| source_tier | 主源（MVP） | 备源 | 覆盖内容 | 频率 | 选择理由 |
|------------|------------|------|---------|------|---------|
| market | yfinance | stooq / Finnhub / Alpha Vantage | universe 行情、指数（S&P 500 / NASDAQ / HSI / VIX）、DXY / GOLD / WTI / 10Y Treasury | 15 min | yfinance 无 key、覆盖美股港股、适合 demo；stooq 为无 key 降级，Finnhub / Alpha Vantage 仅在配置 key 后增强稳定性 |
| news | GDELT + Google News RSS | NewsAPI（仅 dev） | 英文财经新闻、公司事件 | 15 min | GDELT 全球事件库无调用限制；Google News RSS 免费且实时；NewsAPI Developer 计划仅限开发测试且 24 小时延迟，不用于生产 |
| official | SEC EDGAR RSS + HKEX announcements RSS | FOMC / Federal Reserve RSS / 经济日历公开源 | 美股 8-K / 10-Q、港交所披露、政策声明 | 1 hour | source_tier 最高，conflict_resolution 首选；官方源用于校验新闻与政策类判断 |

研报（research tier）通过独立 feature `research_pdf_upload` 由用户上传。

#### 2.2 采集查询策略（安全关键）

**原则**：任何第三方数据源调用不得直接暴露客户组合结构。行情/新闻/公告 API 可以看到 privacy-safe universe，但该 universe 必须满足最小稀释约束，不能近似等同单客户持仓。

| 调用对象 | 查询方式 | 可传 ticker | 可传 weight |
|---------|---------|-----------|-----------|
| yfinance / stooq | 按 privacy-safe universe 批量拉行情 | 是（privacy-safe universe） | 否 |
| GDELT / Google News RSS | 按市场宽关键词 + privacy-safe universe ticker | 是（privacy-safe universe） | 否 |
| SEC EDGAR / HKEX | 按 privacy-safe universe 内 ticker 拉 filings | 是（privacy-safe universe） | 否 |
| LLM provider | 传 alias + asset_class；不传 sector / region / bucket / weight_band | 否 | 否 |

privacy-safe universe 定义与约束：
- universe = 客户持仓 + watchlist + 行业代表 + 宽基指数/ETF + 每个 bucket 的 decoy tickers
- decoy/行业代表数量必须 ≥ 客户持仓 ticker 数 × 2，且每个 exposure_bucket 至少包含 `max(k_anonymity_threshold, 5)` 个可查询 ticker
- 单客户 demo 也必须使用同一 privacy-safe universe，不得直接以客户持仓列表作为 query
- universe query 不包含 account、portfolio_id、weight、客户标签或持仓排序
- 若某 bucket 无法满足稀释约束，该 bucket 不向第三方行情/新闻 API 发 ticker 级查询，仅使用宽基/sector ETF 与市场宽关键词
- 若客户持仓 ticker < 15，触发 `coarse_bucket_mode`：只允许 3-4 个超大类 bucket（如 `us_equity` / `hk_equity` / `macro_etf` / `cash_or_other`），避免 5×3 细分网格导致 decoy 过多且稀释 portfolio_linkage

#### 2.3 功能交互说明

1. **系统初始化**
   - 07:00 HKT 开始滚动采集美股盘后、港股盘前、官方公告与政策源
   - 07:55 HKT freeze 当日 evidence_pool 并触发 brief_generation_pipeline
   - 每类源独立线程，任一源失败不阻塞其他
   - 每次调用记录至 redis，聚合为 source_health

2. **详细逻辑**
   - 与已有功能的交互关系：产出的 raw_items 进入 brief_generation_pipeline
   - 新增逻辑：港股 symbol 统一 `.HK` 格式；时区统一 UTC 存储、HKT 展示；盘前盘后分别标记；USD/HKD 汇率每日一次

#### 2.4 功能数据说明

1. **数据流向**：
   - 外部 API / RSS → normalize → evidence store
   - redis 仅缓存当日 brief、source_health 与短期运行状态
   - SQLite / 等价本地持久层保存 evidence、FTS/BM25 chunks、audit logs、alias_map_encrypted metadata
   - 原始响应压缩后保留 7 天供审计与 quote_span 复核

### 3. 原型图

- 后端服务，无 UI 原型

### 4. 边界情况

- 单源失败：标记 degraded，其他源正常
- 所有源失败：进入保守 brief
- API 限流：exponential_backoff 重试 ≤ 3 次
- universe 配置变更：下次 cron 生效，不热更新

---

## Feature: brief_generation_pipeline（P0）

### 1. 描述

将 raw_items（含行情 + 新闻 + 官方公告 + 上传研报 chunk）经多阶段处理、本地持仓关联和最小必要字段脱敏后生成 MorningBrief。

### 2. 功能详细说明

#### 2.1 处理 pipeline 九步

```
stage_1  normalize              统一字段与时区
stage_2  entity_linking         NER + ticker 字典匹配
stage_3  dedupe                 content_hash + local_embedding 相似度分组
                                同事件保留主来源 + supplementary_sources
stage_4  base_scoring           base_score = source_reliability × recency × novelty
stage_5  portfolio_mapping      本地映射 evidence → exposure_bucket（永不调 LLM）
stage_6  final_scoring          final_impact_score = BPS 多因子综合评分
stage_7  conflict_resolve       结构化冲突检测，不让 LLM 裁决
stage_8  evidence_selection     按 impact_score 降序取 top_k（默认 20）
stage_9  anonymization          ticker_aliasing + 最小资产类别脱敏
```

**为什么 portfolio_mapping 在 scoring 之前结束**：BPS 的 `portfolio_linkage` 需要先完成本地 portfolio_mapping 才能计算。base_score 做粗筛，final_score 做精排。

#### 2.2 impact_score / BPS 评分骨架

V2 采用 Brief Priority Score（BPS）作为 `final_impact_score` 的可解释评分骨架。BPS 是晨报编辑排序分，不是收益预测或交易信号。

```
base_score = source_reliability × recency_weight × novelty_weight
final_impact_score = base_score × portfolio_linkage × event_materiality × market_confirmation

source_reliability:  official=1.0 / market=0.9 / news=0.7 / research=0.5
recency_weight:      1.0 (<4h) / 0.8 (4-12h) / 0.5 (12-24h) / 0.2 (>24h)
novelty_weight:      1.0（新事件，无论是否已有 supplementary_sources 印证） / 0.3（重复但未合并的低质量相似项）
portfolio_linkage:   1.0（本地命中持仓 bucket） / 0.6（watchlist 或本地同粗类） / 0.3（通用市场）
event_materiality:   1.0（盈利/指引/监管/政策/显著价格异动） / 0.6（一般公司新闻） / 0.3（纯观点）
market_confirmation: 1.0（行情/官方/多源 supplementary_sources 互相印证） / 0.6（单一高可信来源） / 0.3（低确认度）
```

`novelty_weight` 只表达“是否是新的独立事件”，不表达是否被多源印证；多源印证只由 `market_confirmation` 加分，避免“被印证反而扣分”的内部抵消。

每条入选 evidence 必须输出 `score_breakdown`，用于本地排序解释与 drawer/debug 视图；`score_breakdown` 不进入 Text LLM prompt，避免泄露 portfolio_linkage。

#### 2.3 Dedupe / supplementary_sources 规则

同 content_hash 或相似度 ≥ 0.90 的 evidence 合并为同一事件；相似度 0.80-0.90 的 evidence 进入 candidate cluster，由事件实体、时间窗、source_tier 再判定是否合并。合并后按以下优先级选择主来源：
1. source_tier 更高（official > market > news > research）
2. 相同 tier 下，原始发布源优先于转载源（通过 url 主域名判断）
3. 以上相同，published_at 更早者保留

被合并来源不丢弃，写入 `supplementary_sources`，用于 market_confirmation、多源印证和 evidence_drawer 展示，避免 dedupe 与 confirmation 互相抵消。

#### 2.3.1 结构化冲突检测

- 冲突检测在 final_scoring 前完成，避免重复或冲突来源被 LLM 合成为单一确定结论。
- 触发条件：
  - 两个高可信来源对同一实体报告的关键数字差异超过阈值
  - 同一事件出现相反方向描述，如 beat / miss、raises / cuts、上调 / 下调
  - 官方公告与新闻解读存在明显不一致
- 冲突处理：
  - evidence 标记 `conflict=true` 与 `requires_review=true`
  - 保留双方来源与 quote_span
  - 若 final_impact_score 足够高，仍可进入 judgement，但必须展示为「需人工复核」
  - 禁止 LLM 裁决冲突来源谁对谁错

#### 2.4 最小必要字段脱敏机制（安全核心）

**原则**：Text LLM request body 不得包含真实 ticker 字符串、真实公司名、具体 weight 数字、客户相关字段。

##### 2.4.1 ticker_aliasing

- 本地维护 alias_map，命名规则为无语义随机 ID：`E_{4-6位随机hex}`，如 `NVDA → E_a3f9`、`0700.HK → E_7b21`
- Text LLM prompt 只允许随 evidence 传 `asset_class`（equity / bond / commodity / fx / cash / unknown）和 `source_tier`；不得传 `region`、`sector`、`industry`、`exposure_bucket`、`portfolio_linkage`、`weight_band` 或 `is_external`
- 行业、地区、bucket、因子等细粒度信息只在本地 `portfolio_mapping`、BPS scoring、前端授权展示和 validator 中使用，不进入 Text LLM request body
- 替换目标：evidence.title / excerpt / detected_tickers / research_chunk / caption / user_question 内文本
- 输入端 ticker_aliasing 必须复用 §2.5.2 的 `sensitive_entity_dictionary`，不仅替换 ticker 字面值，也替换公司英文全名、简称、中文名、交易所格式变体和手工别名，避免 `Tencent` / `英伟达` 这类公司名漏进 Text LLM
- alias_map 按 `brief_id` 加密存储至当日 16:00 HKT，用于 QA 反映射；过期后自动删除
- alias_map 仅后端可解密，不返回前端、不写入审计日志、不进入 LLM request body
- 反映射后的真实 ticker / 公司名可以返回授权前端用于展示，但 alias_map 表本身不下发
- universe 外 ticker 也使用同一 `E_xxxx` 命名规则；`is_external=true` 仅存在本地 diagnostics / parse_report，不传给 Text LLM

##### 2.4.2 weight_band 区间化

- 持仓 weight 不以具体百分比入 Text LLM；MVP 默认也不向 Text LLM 传 `weight_band`，避免 `alias + sector + dominant` 反推到 ticker 级
- `weight_band` 仅用于本地 BPS、前端授权展示、审计解释和人工 debug；如未来产品强依赖 weight_band 进入 LLM，必须重新做隐私评审并在 PRD 中显式接受可反推风险
- 前端展示使用真实权重（本地数据）

##### 2.4.3 k-anonymity（k=3）

- exposure_bucket 成立的最小 ticker 数 k=3
- bucket 下 ticker 数 < 3 时，合并到 `other_equity` 或相邻 bucket
- 避免小型家办场景下通过 bucket 反推具体标的（如 `hk_internet` 仅含 2 只时可直接猜出）
- 若客户持仓 ticker < 15，强制启用 `coarse_bucket_mode`；每个粗 bucket 至少 5 个可查询 ticker，且 decoy 不得超过客户持仓 ticker 数 × 4，超过则降级为宽基/sector ETF 查询，避免 decoy 噪声污染 portfolio_linkage

##### 2.4.4 敏感扫描（发送前硬校验）

LLM request body 发送前执行：
1. 正则扫描是否含 `alias_map` 中任意真实 ticker 或本轮 detected_tickers 字面值
2. 正则扫描是否含 `数字 + %` 组合（具体百分比）
3. 扫描是否含敏感词（account_id / client_name / amount 关键词）
4. JSON schema 白名单校验：不得出现 `sector`、`industry`、`region`、`exposure_bucket`、`weight_band`、`portfolio_linkage`、`is_external`
5. 命中任一规则 → 阻断调用 → 记录 alert → 输出保守 brief

#### 2.5 LLM 生成三阶段

- **stage_a**：morning_base_case + ai_judgement_summary
- **stage_b**：1-5 条 judgement（含 reasoning_chain 四层，默认目标 3 条）
- **stage_c**：playbook_events

**输入约束**：禁止推测未在 evidence 中出现的事实；禁止"建议买入/卖出"等动作动词；所有字段有硬字数上限。

#### 2.5.1 LLM 安全编排骨架

- 应用代码不允许直接调用 LLM provider，所有 Text / Vision LLM 调用必须经过统一 audit wrapper。
- prompt 构建采用白名单字段：
  - `aliased_evidence`
  - `quote_span_aliased`
  - `asset_class`
  - `task_instruction`
  - `output_constraints`
- prompt 不允许包含：
  - 真实 ticker
  - 真实公司英文名、简称、中文名
  - 具体 weight
  - sector / industry / region / exposure_bucket / weight_band / portfolio_linkage / is_external
  - account_id / client_name / amount
  - 原始 prompt 调试信息
- 任一 LLM 调用失败都必须写入 audit failure record。
- Text LLM 输出后必须做反向敏感扫描；若出现 alias_map 中任意真实 ticker、公司英文名、常见简称或中文名，系统重试一次，仍失败则将该实体替换回 alias 或输出保守 brief。

#### 2.5.2 输出敏感黑名单维护

输出反向扫描的黑名单由本地 `sensitive_entity_dictionary` 生成，不依赖人工临时补漏：

- **自动来源**：privacy-safe universe 内 ticker 通过 yfinance 拉取 `symbol`、`longName`、`shortName`、`quoteType`、`exchange`；港股同步生成 `.HK`、去前导零、HKEX 前缀等格式变体
- **手工来源**：维护 `config/company_alias_zh.yml`，覆盖中文名、常见简称、创始人指代和市场俗称；MVP 至少覆盖持仓、watchlist 和 demo universe 的 30-50 个核心标的
- **变体规则**：大小写归一、去标点、`$NVDA` / `NVDA.O` / `NASDAQ:NVDA` / `HKEX:0700` / `700.HK` 等交易所格式、中文全称/简称
- **更新频率**：每日采集前刷新 yfinance 字段；手工表进入代码审查；ticker 上市/退市/改名由每日 refresh diff 生成 admin warning
- **成本/运维**：MVP 接受免费源名称不完整的风险，通过手工中文别名表补齐；生产环境推荐接入 OpenFIGI、客户自有 security master 或合规授权的证券主数据

命中黑名单时，Text LLM 输出重试一次；仍命中则由本地 renderer 使用 alias 或安全占位替换，不把未授权真实实体直接展示给用户。

#### 2.6 accuracy_validator 校验规则

每次 LLM 输出后执行：

1. cited_evidence_ids 必须均在 evidence_pool 内
2. 每条 citation 必须附带 quote_span（字符偏移或 PDF `{page, bbox}`）
3. quote_span 指定文本必须能在 evidence 原文中定位匹配
4. reasoning_chain.observed 的关键数字必须能在引用 evidence 的 quote_span 内找到
5. ai_judgement_summary 必须引用 ≥ 2 条 evidence
6. 定性结论（如 "hawkish commentary"）必须有 quote_span 锚定到可佐证原文片段
7. 数字一致性：LLM 输出中的数字、百分比、bp、金额、倍数必须能在引用 quote_span ±120 字符内找到，且单位一致
8. 极性/方向一致性：beat/miss、raise/cut、上调/下调、超预期/不及预期等方向词必须与 quote_span 中方向词一致
9. 时间窗一致性：LLM 输出涉及"昨晚/今日/本周/季度"等时间表达时，必须与 evidence.published_at 和原文时间窗一致
10. 输出敏感扫描：输出不得包含未通过本地反映射生成的真实 ticker / 公司名
11. 任一校验失败 → 重试一次 → 再失败 → 降级保守 brief 或删除问题段落

quote_span 校验使用双坐标：LLM 侧返回 `quote_span_aliased`，本地通过 alias offset map 转换为 `quote_span_original` 后再在原文定位。

准确性不等同于完整事实核验。MVP 定义为：引用真实存在、数字/方向/时间窗与引用片段一致、冲突不被 LLM 裁决；后续通过 golden set 做回归。

**时间表达 → 时间窗规则（统一以 `brief_timezone=Asia/Hong_Kong` 计算，源时间先转 UTC 再转 HKT）**

| 表达 | 判断窗口 | 说明 |
|------|---------|------|
| 昨晚 / 隔夜 | 前一自然日 18:00 HKT 至 brief 当日 08:30 HKT | 覆盖美股常规交易、盘后公告与亚洲盘前新闻 |
| 今日 / 今早 | brief 当日 00:00 HKT 至当前生成时间 | 08:30 生成时默认截至 freeze_time；重新分析时截至 reanalyze_time |
| 美股盘后 | 美东时间上一交易日 16:00 至 20:00，先按 NYSE 交易日历判定，再转换为 HKT | 夏令时/冬令时由 IANA `America/New_York` 处理，不手写偏移 |
| 美股盘前 | 美东时间当日 04:00 至 09:30，转换为 HKT | 用于判断“盘前”新闻，非 HKT 早晨概念 |
| 本周 | brief 当地时区的 ISO week（周一 00:00 至当前生成时间） | 不使用滚动 7 天，避免周报/晨报语义混淆 |
| 过去 7 天 | 当前生成时间向前滚动 168 小时 | 仅当 LLM 明确写“过去 7 天”时使用 |
| 本季度 / 季度 | 自然财季或公告原文明确 fiscal quarter | 若 evidence 原文写 fiscal Q1/FY，则以原文 fiscal period 为准，不用 published_at 推断 |
| 最新 / 刚刚 | published_at 距当前生成时间 ≤ 4 小时 | 超过 4 小时不得写“刚刚” |

若 LLM 使用的时间表达无法被上表归类，validator 将其视为不合格并要求重写为绝对日期或删除相对时间词。

#### 2.6.1 本地检索骨架

- local_evidence_qa 使用本地全文检索，MVP 优先 SQLite FTS5 / BM25 或等价轻量检索。
- 检索对象是当日 evidence chunks，而不是全互联网。
- local scope 必须先过滤 evidence 集合，再检索：
  - `scope=judgement`：仅检索该 judgement 的 evidence_ids
  - `scope=evidence`：仅检索单条 evidence
  - `scope=global`：P1 才检索全部 evidence_pool
- 检索无结果时不调用 LLM，直接返回 insufficient evidence。

#### 2.7 保守 brief

- morning_base_case: `Data coverage limited today; review overnight moves manually before meeting.`
- ai_judgement_summary: `Automated analysis unavailable due to insufficient evidence. Portfolio and macro data remain accessible below.`
- 不输出 judgements
- portfolio_map 与 macro_pulse 正常展示

#### 2.8 阅读时长预算（5 分钟）

| 模块 | 字数预算 | 阅读时间 |
|-----|---------|---------|
| morning_base_case | ≤ 50 字 | 10 秒 |
| ai_judgement_summary | ≤ 200 字 | 40 秒 |
| judgement.conclusion | 默认展示 top 3，每条 ≤ 60 字；N>3 时后两条折叠 | 45 秒 |
| evidence_summary | 默认展示 top 3，每条 ≤ 120 字符；折叠项不计入首轮阅读 | 45 秒 |
| portfolio_map 扫视 | — | 30 秒 |
| playbook 扫视 | — | 30 秒 |
| 一次 evidence_drawer 快速验证 | ≤ 1 条 judgement | 45 秒 |
| 一次 local_qa 追问 | ≤ 1 个问题 | 45 秒 |
| 总计 | — | ≤ 5 分钟 |

阅读预算按 N=3 估算。若当天有效 judgement 少于 3 条，不强行补足；若爆发日超过 3 条，首屏只展开 top 3，并显示"今日有 5 条值得关注，已展开 top 3"，其余通过 `[查看全部]` 展开，不计入默认 5 分钟阅读路径。

### 3. 原型图

- 后端服务

### 4. 边界情况

- evidence_pool 为空：输出保守 brief
- LLM API 全超时：输出保守 brief，顶部 chip `llm_unavailable`
- accuracy_validator 连续失败 3 次：fallback 保守 brief 并 alert
- 所有 bucket 不满足 k=3：归入 `other_equity`，judgement 标注 `no_direct_portfolio_link`
- ticker_aliasing 遇到 universe 外 ticker：生成同样无语义的 `E_xxxx` alias，并在 parse_report / source diagnostics 中 warning；`is_external=true` 不进入 Text LLM

---

## Feature: morning_base_case_and_ai_summary（P0）

### 1. 描述

首屏右侧展示一句话核心判断 + 200 字详细研判摘要。命题要求的 AI 研判必交输出。

### 2. 功能详细说明

#### 2.1 功能交互说明

1. **系统初始化**：从 `/api/brief/today` 获取 `base_case_headline`、`ai_judgement_summary`、`cited_evidence_ids`、`degradation_note`

2. **详细逻辑**
   - 与已有功能的交互关系：与 portfolio_map 左右并列占首屏
   - 与交互界面的关系：
     - base_case_headline：Fraunces serif 30px，左侧 3px orange_600 竖线；保持首屏视觉焦点但避免压过组合图与 judgement list
     - ai_judgement_summary：Inter 14px，位于下方，ink_700，line-height 约 1.55
     - 引用以 `[1][2]` 形式内嵌，点击跳转对应 evidence_drawer 并高亮
   - 新增逻辑：
     - degradation_note 条件显示，warning 色
     - 中文 > 200 字自动重试

#### 2.2 功能数据说明

1. **数据流向**：pipeline stage_a 生成 → 反映射 alias 回 ticker → 前端渲染

### 3. 原型图

- 原型链接：`/designs/v2/main-page.png`（首屏右侧）

### 4. 边界情况

- 引用 < 2 条：重试一次仍失败则保守文案
- 超过 200 字：截断到最近句号并重试
- 无 degradation_note：不渲染

---

## Feature: research_pdf_upload（P1）

### 1. 描述

用户上传研报 PDF，系统自动解析文本、表格、图表，展示解析结果供用户验收，并将提取的 chunk 作为 evidence 参与 LLM 判断。支持多文件管理与重新分析。

### 2. 功能详细说明

#### 2.1 上传交互

1. **入口**
   - 主页 header 右侧 "Upload research" 按钮
   - 点击弹出上传面板（drawer 或 modal）
   - 首次使用显示第三方图表识别偏好设置；之后每次上传仍展示当前状态摘要与 `Change processing preference` 链接

2. **上传限制**
   - 格式：仅接受 PDF
   - 单文件 ≤ 10MB
   - 累计不超过 5 份活跃研报（超限提示用户先删除旧的）
   - 前端先做 mime 校验再上传

3. **第三方图表识别确认**
   - 默认关闭 `Allow third-party figure captioning`
   - 用户勾选后才允许把 PDF 页面截图发送给 vision LLM；偏好可作为后续上传默认值，但每个文件上传时都保存一次 consent snapshot
   - 确认记录包含 user_id、timestamp、policy_version、file_id、consent_state，可撤回；撤回后不影响已生成 caption 的审计记录，但后续 re-analyze 不再调用 vision LLM
   - 文案：`I confirm this PDF can be processed by third-party AI services for chart captioning and does not contain client holdings, account identifiers, or restricted internal material.`
   - 未勾选时，上传仍可继续；解析结果显示 `Figure captions skipped: third-party processing not allowed`，图表 chunk 标为 `caption_unavailable_by_policy`
   - MVP 文案为产品/合规草案；生产上线前必须经客户法务或内部合规审阅，不把 UI 勾选视为替代合同授权

4. **上传后状态流**

```
uploaded          上传完成，等待解析
→ extracting      文本 + 表格提取中
→ ocr_processing  扫描版 PDF 触发 OCR（可选）
→ captioning      图表 multimodal caption 中
→ chunking        分 chunk 与 local_embedding
→ ready           可用于 brief
→ failed          任一环节失败
```

#### 2.2 解析 pipeline

```
stage_a  extraction
  - pdfplumber 提取文本 + 坐标（bbox）
  - pdfplumber.extract_tables() 提取表格
  - 按 font size 推断 heading 层级用于 chunking 依据

stage_b  ocr_fallback
  - 检测纯图像页面（文本提取结果为空）
  - 调用 pytesseract 做 OCR
  - OCR 失败的页记录，不阻塞其他页

stage_c  figure_captioning
  - 检测页面中的图表（通过 pdfplumber 识别图像对象）
  - 截取图表区域 PNG
  - 调用 multimodal LLM（Claude vision / GPT-4o vision）生成 caption
  - caption 描述要求：图表类型、坐标轴含义、关键数据点或趋势
  - caption 产出后进入 ticker_aliasing 后再加入 evidence_pool

stage_d  chunking
  - 按 heading 层级切分 chunk，保留原文位置（page + bbox）
  - 每个 chunk 长度 200-500 字符，跨段合并时保持语义完整
  - chunk_type 标记：text / table / figure_caption
  - 每个 chunk 独立生成本地 embedding（MVP 默认 bge-small / sentence-transformers 等本地模型）
  - 若后续启用第三方 embedding API，必须先执行 ticker_aliasing，并在第三方调用边界表中显式开启

stage_e  ticker_detection
  - NER + 字典匹配识别 chunk 内的 ticker
  - universe 外的 ticker 标记为 `external_ticker`，不影响后续但在 parse_report 中 warning

stage_f  dedupe_against_pool
  - 与已有 evidence_pool 做 local_embedding 相似度去重
  - 相似度 > 0.9 的 chunk 丢弃并记录

stage_g  merge_to_pool
  - chunk 作为 research_chunk 类型 evidence 加入 evidence_pool
  - source_tier = research，weight = 0.5
```

任一 stage 支持 `partial_failure`：成功 chunk 继续入池，失败 chunk 记录 stage、原因、页码/区域与可重试状态，parse_report 不因单个 chunk 失败而整体 failed。

#### 2.3 parse_report 展示（信任可视化）

解析完成后展示结果面板：

```
┌─────────────────────────────────────────────┐
│ FILENAME: goldman_china_outlook_2026.pdf    │
│ STATUS: ready                               │
│                                             │
│ ──────── Parsing summary ────────           │
│ Pages processed:        28 / 28             │
│ Pages via OCR:          3                   │
│ Text chunks:            47                  │
│ Tables extracted:       6                   │
│ Figures captioned:      12                  │
│ Figures caption failed: 1 (page 14)         │
│                                             │
│ ──────── Tickers detected ────────          │
│ In universe:   NVDA, 0700.HK, 9988.HK       │
│ External:      BABA, JD.US (not in watchlist)│
│   ⚠ External tickers will still be included │
│     but won't match portfolio context        │
│                                             │
│ ──────── Low-confidence chunks ────────     │
│ Page 17, fig 3: "caption may be inaccurate" │
│   [ View chunk ] [ Delete chunk ]           │
│                                             │
│ ──────── Actions ────────                   │
│ [ Re-analyze with uploads ]                 │
│ [ Delete this upload ]                      │
└─────────────────────────────────────────────┘
```

各项说明：
- **Pages processed**：成功解析页数 / 总页数
- **Pages via OCR**：走 OCR 路径的页数（扫描版）
- **Text / Tables / Figures**：各类 chunk 数量
  - **Tickers detected**：命中 universe 的 ticker（可用于持仓关联）+ universe 外 ticker（warning）；进入 Text LLM 前都会 alias
- **Low-confidence chunks**：caption LLM 标记为不确定的 chunk，用户可查看并选择删除

#### 2.4 重新分析

- 用户点击 `Re-analyze with uploads` 按钮触发
- 后端仅重跑 `brief_generation_pipeline` 的 stage_4 至 stage_9 + LLM generation
- 不重新采集 market / news / official
- 新 brief 覆盖当前 redis 缓存
- 用户会看到 judgement 变化（可能新增 research 相关的 Judgement）
- 一次重分析耗时目标 ≤ 30 秒

#### 2.5 多文件管理

- 上传列表视图展示所有活跃 PDF（MVP 默认最多 5 份，可通过 `research_upload_limit` 配置；该限制源于 demo 成本、解析队列和存储控制，不代表生产上限）
- 每份展示：文件名、上传时间、解析状态、chunk 数
- 操作：View parse_report / Delete
- 删除立即从 evidence_pool 移除对应 chunk，但不自动重跑 brief（避免意外触发）

#### 2.6 功能数据说明

1. **存储**
   - 原 PDF 文件：加密本地存储（`research_pdfs/{user_id}/{file_id}.pdf`），MVP 默认保留 7 天，可按客户合规要求延长
   - chunk 与 local_embedding：独立表 `research_chunks`，与主 evidence_pool 联合查询
   - alias 关系：复用主 alias_map

2. **数据流向**
   - 用户上传 → 本地存储 → parse_pipeline → research_chunks 表
   - 重分析 → 读 research_chunks → 参与 pipeline stage_4 及以后

#### 2.7 安全处理

- **PDF 内容归类**：研报内容默认按用户确认的公开/可处理材料处理；用户需确认上传内容不含客户持仓、内部账户信息或禁止外传内容。
- **版权责任**：用户对上传研报的使用权限负责；系统不对外分享原文，不在公开链接展示研报正文，仅对授权用户提供 secure viewer。
- **vision LLM 调用**：PDF 页面截图可传给 vision API 的前提是用户确认其可被第三方处理；请求不得携带 user_id、session_id、account_id、portfolio_id，使用独立 API key，不复用带客户身份的会话。
- **caption 后处理**：vision 返回的 caption 文本在进入 evidence_pool 前，必须经过主 pipeline 的 ticker_aliasing（因为之后主 LLM 调用会读到 caption）
- **universe 扩展**：PDF 中出现的 universe 外 ticker，可选择扩展 alias_map 并重新评估（配置项 `auto_expand_universe`，默认 false）
- **文件隔离**：用户 A 的上传仅对用户 A 可见，后端按 user_id 做权限隔离

### 3. 原型图

- 原型链接：`/designs/v2/upload-flow.png`（上传入口 + parse_report + 重分析按钮）

### 4. 边界情况

- PDF 加密或损坏：stage_a 失败，状态置 `failed`，展示"无法打开此 PDF"
- OCR 完全失败（扫描质量差）：标记所有文本 chunk 为空，提示用户"此 PDF 为扫描版且 OCR 未能识别，建议上传可选文字版本"
- vision API 超时：caption 缺失的图表标记 `caption_unavailable`，不阻塞其他 chunk
- 上传超过 5 份：提示"请先删除旧上传"
- chunk 与已有 evidence 完全重复：stage_f 丢弃并在 parse_report 中显示 `{N} duplicate chunks skipped`
- 重分析触发时主 pipeline 正在运行：排队等待当前 pipeline 完成后再触发，前端显示 queued 状态
- PDF 含有 universe 外 ticker 且 `auto_expand_universe=false`：chunk 仍入池，并在 parse_report warning；进入 Text LLM 前统一替换为无语义 `E_xxxx` alias，`is_external=true` 仅本地可见，原 ticker 仅在授权前端和本地 validator 中可见

---

## Feature: local_evidence_qa（P0） / global_evidence_qa（P1）

### 1. 描述

基于当日 evidence 追问，回答必须包含引用且原文片段可定位。P0 必须支持针对单条 judgement / evidence 的 local scope；P1 扩展支持基于全部 evidence_pool 的 global scope。

### 2. 功能详细说明

#### 2.1 功能交互说明

1. **系统初始化**：P0 local_qa 可从 judgement / evidence 行的最小追问面板打开；P1 evidence_drawer 提供增强体验；global_qa 位于 deep_read 区域（P1）

2. **详细逻辑**
   - 与已有功能的交互关系：scope=judgement 用指定 judgement 的 evidence_ids（P0）；scope=evidence 用单条 evidence（P0）；scope=global 用全量 evidence_pool（P1）
   - 新增逻辑：
     - placeholder 使用今日内容动态示例
     - 下方 3 个建议 chip 基于今日 evidence 动态生成
     - 超时 20 秒
     - 回答渲染后被引用的 evidence 高亮 2 秒
     - 同 scope 下保留 3 轮上下文

#### 2.2 功能数据说明

1. **数据流向**
   - 用户输入 → 后端读取 `brief_id` 对应 alias_map，对问题中的 ticker 做 alias 替换
   - `POST /api/qa`，body: `{brief_id, question_aliased, scope, judgement_id?, evidence_id?}`
   - 后端加载 evidence 子集（已 aliased）→ LLM 生成 → accuracy_validator → 基于 alias_map 反映射 → 返回

### 3. 原型图

- 原型链接：`/designs/v2/main-page.png`、`/designs/v2/drawer.png`

### 4. 边界情况

- 问题为空：发送按钮禁用
- > 500 字符：禁用发送
- 与持仓无关：LLM 返回 `out_of_scope`
- alias_map 已过期：返回 `brief_expired`，提示用户重新生成当日 brief
- 引用不存在或 quote_span 无法定位：accuracy_validator 拒绝，重试一次
- 连续 3 次校验失败：显示 `Unable to answer based on current sources, please rephrase`

---

## Feature: judgement_list（P1）

### 1. 描述

三行列表呈现 AI 核心判断。

### 2. 功能详细说明

#### 2.1 功能交互说明

1. **系统初始化**：从 `/api/brief/today` 获取 judgements 按 rank 升序

2. **详细逻辑**
   - 整行点击热区触发 evidence_drawer
   - conclusion（sans medium 14px）+ evidence_summary（mono 12px）
   - rank=1：orange_50 背景 + 橙色左竖线
   - level 标签 elevated 使用 orange_600，其他 ink_500

#### 2.2 功能数据说明

1. **数据流向**：随 MorningBrief 缓存

### 3. 原型图

- 原型链接：`/designs/v2/main-page.png`（中部）

### 4. 边界情况

- judgements 为空：不渲染
- evidence_summary > 120 字符：pipeline 已截断

---

## Feature: evidence_drawer（P1）

### 1. 描述

侧边抽屉展示 reasoning_chain + evidence 列表 + local_qa。PDF 类 evidence 支持跳转到具体页码。

### 2. 功能详细说明

#### 2.1 功能交互说明

1. **系统初始化**：首次打开调用 `/api/judgement/{id}/drawer`，同会话缓存

2. **详细逻辑**
   - 由 judgement 行或 base_case 的 `[1][2]` 触发
   - 右侧滑入 200ms，desktop 560-640px，mobile 全屏
   - 主页不加遮罩
   - 关闭：× / ESC / 点击外部 / 返回按钮
   - 结构：judgement_anchor → reasoning_chain → evidence_list → local_qa
   - evidence 摘录使用 Fraunces serif 16px；不强制 italic，以当前设计稿的克制新闻摘录气质为准
   - `Read full article ↗`：非 PDF 跳转新标签页；PDF 跳转内置 PDF viewer 并定位到对应 page + bbox 高亮

#### 2.2 功能数据说明

1. **数据流向**：`/api/judgement/{id}/drawer` 返回 `{judgement, reasoning, evidences, suggested_questions}`，alias 已反映射

### 3. 原型图

- 原型链接：`/designs/v2/drawer.png`

### 4. 边界情况

- drawer api 超时 10s：retry 按钮
- evidence 为空：`No cited sources`
- 切换 judgement：平滑替换
- PDF evidence 跳转：若原 PDF 已被用户删除，提示 `Original document unavailable`

---

## Feature: portfolio_map（P1）

### 1. 描述

Treemap 展示持仓隔夜变化。

### 2. 功能详细说明

#### 2.1 功能交互说明

1. **系统初始化**：从 `portfolio` 拆分持仓与 watchlist

2. **详细逻辑**
   - 与 morning_base_case 并列占首屏
   - 色块间距 4px，圆角 2px
   - 第一行 symbol + weight%，第二行 ▲▼ + 涨跌%
   - 涨跌必须同时使用符号与颜色

#### 2.2 功能数据说明

1. **数据流向**：持仓仅本地后端 + 前端；不经 LLM

### 3. 原型图

- 原型链接：`/designs/v2/main-page.png`（首屏左侧）

### 4. 边界情况

- 行情缺失：色块显示 `—`
- 权重 ≠ 100%：CASH 自动补足

---

## Feature: source_health（P1）

### 1. 描述

展示四类数据源健康状态（含 research 上传活跃状态）。

### 2. 功能详细说明

#### 2.1 功能交互说明

1. **系统初始化**：从 `source_health` 按固定顺序渲染

2. **详细逻辑**
   - 降级时顶部 chip、base_case 脚注、footer 三处同步
   - 4 行表格，mono 字体
   - ok 使用 ink_500；degraded 使用 warning；failed 使用 danger
   - research 行显示 `{N} uploads active`（无上传时显示 `no uploads`）

#### 2.2 功能数据说明

1. **数据流向**：ingestion 记录 → 每 5 分钟聚合 → redis 快照

### 3. 原型图

- 原型链接：`/designs/v2/main-page.png`（底部右列）

### 4. 边界情况

- 全 failed：顶部 chip `All sources degraded`，保守 brief
- research 为空：显示 `no uploads`，不计入 degraded

---

## Feature: playbook（P2）

### 1. 描述

时间轴展示今日 2-4 个事件节点。

### 2. 关键说明

- 相对时间每 60 秒刷新
- 下一未发生事件相对时间使用 orange_600
- 数据来自 pipeline stage_c

### 4. 边界情况

- 为空：不渲染
- 全部已发生：`next event` 不显示

---

## Feature: watchlist_item（P2）

### 1. 描述

portfolio_map 下方独立行展示 watchlist 标的。

### 2. 关键说明

- 从 portfolio 筛选 `is_watchlist=true`
- 格式：`WATCHLIST  {symbol} · no holding · quoted for market context`

### 4. 边界情况

- 为空：不渲染
- > 5 项：前 5 + `+{n} more`

---

## Feature: macro_pulse（P2）

### 1. 描述

折叠展示 8 个宏观指标。

### 2. 关键说明

- 默认折叠，展开 200ms ease
- 展开后极简表格

### 4. 边界情况

- 指标缺失：value 显示 `—`

---

## 5. 非功能需求

### 5.1 运营需求

- **权限控制**：
  - admin 可查看审计日志
  - 普通用户仅可查看 audited 说明
  - 上传的 PDF 按 user_id 隔离
- **配置开关**：
  - llm_provider：anthropic / openai
  - data_sources：单源启用/禁用
  - degradation_threshold：默认 30%
  - exposure_bucket_rules：sector + factor 映射可配置，但仅本地使用，不进入 Text LLM
  - k_anonymity_threshold：默认 3，可调
  - coarse_bucket_mode：当持仓 ticker < 15 时自动开启，也可由 admin 强制开启
  - auto_expand_universe：上传 PDF 是否自动扩展 universe，默认 false
  - research_upload_limit：单用户活跃上传数，默认 5
  - audit_mode：`demo` / `compliance`，仅 admin 可切换
- **数据导出**：MVP 不实现
- **新客户冷启动**：
  - 导入持仓 → 本地映射行业/地区/因子 → 生成 exposure_bucket → 补充 decoy tickers → 校验 privacy-safe universe
  - MVP 行业数据源：yfinance `sector` / `industry` 字段 + `config/ticker_sector_overrides.yml` 手工覆盖表（至少 30 行，覆盖 demo 持仓、watchlist、核心港美股）
  - 不直接声称使用 GICS：GICS 属 MSCI/S&P 商业分类，MVP 不默认具备授权；生产环境推荐接入 OpenFIGI、客户自有 sector 分类或合规授权的证券主数据
  - 若持仓 ticker < 15，启用 `coarse_bucket_mode`，只生成 3-4 个超大类 bucket；若仍无法满足 k-anonymity，则禁用 ticker 级第三方查询
  - 行业代表优先选宽基 ETF、sector ETF、行业市值代表，不使用客户持仓顺序
  - 冷启动校验失败时，不允许发起 ticker 级第三方 API 查询
- **多租户 / 时区边界**：
  - MVP 默认单租户 HKT 演示
  - 多租户生产扩展必须 tenant_id 隔离 portfolio、PDF、alias_map、audit log 与 universe
  - 非 HKT 客户需配置 `brief_timezone` 与 `brief_delivery_time`，不得复用 HKT cron 假设
- **成本控制**：
  - Text LLM 调用：每次 brief 生成最多 3 次重试；QA 每问题最多 1 次重试
  - Vision LLM 调用：按 PDF 页/图表限额，超限进入 caption_unavailable
  - Embedding：MVP 使用本地模型，第三方 embedding 默认禁用
  - 用户上传研报受 `research_upload_limit`、单文件大小与每日解析次数限制

### 5.1.1 Prompt 模板骨架（评审版）

Text LLM prompt 必须使用结构化 JSON，示意：

```json
{
  "task_instruction": "generate_morning_brief",
  "language": "zh",
  "aliased_evidence": [
    {
      "evidence_id": "ev_001",
      "title_aliased": "E_a3f9 guidance update...",
      "excerpt_aliased": "...",
      "quote_span_aliased": {"start": 120, "end": 188},
      "source_tier": "official",
      "asset_class": "equity",
      "published_at": "2026-04-24T06:20:00+08:00"
    }
  ],
  "output_constraints": {
    "forbidden": [
      "real ticker",
      "company name",
      "exact weight",
      "weight_band",
      "sector",
      "region",
      "exposure_bucket",
      "portfolio_linkage",
      "buy/sell/recommend"
    ]
  },
  "output_schema": {
    "morning_base_case": "string <= 50 zh chars",
    "ai_judgement_summary": "string <= 200 zh chars with citations",
    "judgements": "1-5 items, each with cited_evidence_ids and quote_span_aliased"
  }
}
```

Prompt 中不得出现 `portfolio_context` 对象，也不得包含 `score_breakdown.portfolio_linkage`、真实 ticker、真实公司名、具体 weight、`weight_band`、`sector`、`region`、`exposure_bucket`、客户身份、原始 prompt debug 信息。与持仓相关的排序和取舍已经在本地 BPS / evidence_selection 完成；Text LLM 只负责基于已筛选 evidence 做表达、归纳和引用，不再获得任何可反推出持仓结构的正向 portfolio signal。

### 5.1.2 端到端 walkthrough（评审样例）

PRD 评审必须准备一日样例，用于验证抽象规则：

1. 输入：示例 portfolio + watchlist + privacy-safe universe
2. 采集：raw_items 数量、来源分布、degraded 状态
3. 处理：dedupe 后事件数、conflict 事件、top evidence 与 score_breakdown
4. 输出：morning_base_case、ai_judgement_summary、1-5 条 judgement
5. 追问：针对一条 evidence 的 local_qa，展示 quote_span 与 validator 结果
6. 安全：展示 Text LLM request 中无真实 ticker/公司名/weight

### 5.1.3 质量评估与 golden set

- 建立至少 50 条人工标注 golden cases，覆盖 earnings 周、政策日、市场平静日、突发大跌/大涨日、macro、HKEX/SEC official、research PDF、conflict、单源高可信与多源印证。
- 每次修改 prompt / scoring / validator 后跑回归：
  - citation 可定位率
  - 数字一致率
  - 极性一致率
  - 时间窗一致率
  - 输出敏感扫描通过率
  - conservative brief 触发率
- 生产环境按周/月监控 `conservative_brief_triggered`，不只依赖 golden set；若月触发率 > 10% 或连续 3 个交易日触发，进入数据源/validator/prompt 排查。
- MVP 不宣称完整事实核验，只宣称 evidence-grounded + consistency-checked。

### 5.2 安全与审计

#### 5.2.1 第三方调用边界表

| 调用对象 | 可传 ticker | 可传 weight | 可传图片 | 用途 |
|---------|-----------|-----------|---------|------|
| yfinance / stooq | 是（仅 privacy-safe universe） | 否 | 否 | 行情采集 |
| GDELT / Google News RSS / SEC EDGAR / HKEX | 是（仅 privacy-safe universe） | 否 | 否 | 新闻公告采集 |
| Local embedding（MVP 默认） | 是（本地处理） | 否 | 否 | chunk 相似度 / FTS 增强 |
| Third-party embedding（默认禁用） | 否（必须先 alias） | 否 | 否 | 仅作为可选增强 |
| Vision LLM（图表 caption） | 是（仅用户确认可处理的研报公开内容） | 否 | 是（PDF 页截图） | 图表理解 |
| Text LLM（主 pipeline / QA） | 否（使用 alias） | 否（不传具体 weight 或 weight_band） | 否 | 研判与 QA 生成 |
| 前端（授权用户浏览器） | 是 | 是（具体百分比） | 是 | 展示 |

**关键原则**：研报内容是作者的观点材料，客户持仓是私有信息。两者不可混淆。vision LLM 只能处理用户确认可被第三方处理的 PDF 页面，且请求不携带用户标识；Text LLM 和第三方 embedding 看不到任何真实 ticker，包括 universe 外 ticker；所有 ticker 均经 alias。

#### 5.2.2 审计日志

- 每次 LLM 调用记录：request_hash、scope、cited_evidence_ids、response_hash、accuracy_validation_passed、调用类型（text / vision / embedding）、provider、model、template_version、latency_ms、failure_state
- MVP 默认不保存原始 prompt 明文，降低敏感信息泄露面
- alias_map 独立加密存储至当日 16:00 HKT，仅用于 QA 与反映射，过期自动删除
- 若进入真实金融合规部署，必须开启合规审计模式：加密保存 redacted prompt、redacted response、alias_map snapshot 与模型配置，保留期按客户监管要求配置；demo 模式明确不承担监管留痕义务
- **模式切换边界**：
  - `audit_mode` 由 admin 在后台配置，生产客户切换到 `compliance` 前需客户书面确认或合同附件确认
  - 从 `demo` 切到 `compliance` 只影响切换后的新 brief / QA / PDF 处理；切换前 audit log 因缺少 redacted prompt、alias_map snapshot 等信息，不能补作合规留痕
  - 从 `compliance` 切回 `demo` 需二次确认并记录 reason；历史 compliance audit log 仍按原保留期保存
  - UI 与导出报告必须标识每条记录生成时的 `audit_mode`
- 审计库独立加密存储，demo 默认保留 90 天
- 上传 PDF 的元数据（文件名、上传时间、user_id）单独记录，原 PDF 保留 7 天

#### 5.2.3 前端缓存与脱敏

- 持仓数据不写入 localStorage / IndexedDB，仅内存保存
- stale brief 缓存仅保留 judgements / ai_summary / evidence，不含 portfolio 结构
- 用户登出 → 内存与 session 缓存清除
- 上传的 PDF 不在前端缓存，每次查看通过后端 secure url 流式传输

### 5.3 埋点需求

| 事件名 | 触发时机 | 字段 |
|-------|---------|------|
| brief_view | 主页加载完成 | brief_id, user_id, load_time_ms |
| judgement_row_click | 点击 judgement 行 | brief_id, judgement_id, judgement_rank |
| drawer_open | drawer 打开 | brief_id, judgement_id, trigger_source |
| drawer_close | drawer 关闭 | brief_id, judgement_id, duration_ms, close_method |
| evidence_article_click | 点击 read_full_article | brief_id, evidence_id, source_tier |
| qa_submit | 提交追问 | brief_id, scope, judgement_id, question_length |
| qa_response_render | 回答渲染完成 | brief_id, scope, response_time_ms, cited_count, validation_passed |
| accuracy_validation_failed | 准确性校验失败 | brief_id, scope, failure_reason |
| source_degraded | 数据源降级 | source_category, failure_rate |
| sensitive_scan_blocked | 敏感扫描阻断 | rule_matched, scope |
| conservative_brief_triggered | 触发保守 brief | brief_id, trigger_reason, failed_stage, source_health_snapshot |
| research_pdf_upload | PDF 上传完成 | file_id, file_size_kb, page_count |
| research_pdf_third_party_consent | 用户确认/撤回第三方图表识别 | file_id, consent_state, policy_version |
| research_pdf_parse_complete | 解析完成 | file_id, duration_ms, chunks_count, ocr_pages, captioning_failures |
| research_pdf_chunk_delete | 用户删除 chunk | file_id, chunk_id |
| research_reanalyze_click | 点击重新分析 | file_id_list, active_chunks_count |

---

## 6. 验收标准

### 6.1 P0 功能验收

**data_ingestion**

- Given 系统配置 3 类数据源，When cron 触发，Then ≥ 3 类源成功返回数据（不允许 mock）
- Given yfinance 采集港股 `0700.HK`，When 返回，Then symbol 保持 `.HK` 后缀
- Given GDELT 500 错误，When 发生，Then fallback Google News RSS 且 source_health 标记 news=degraded
- Given 采集调用发出，When 检查 query，Then 不得存在按单一客户组合动态构造的查询串
- Given 单客户持仓 10 个 ticker，When 构造 privacy-safe universe，Then 自动启用 `coarse_bucket_mode`，universe 至少包含 20 个 decoy/行业代表 ticker，且每个粗 bucket ≥ max(k,5)
- Given 某 bucket 无法满足稀释约束，When 发起第三方数据采集，Then 不发该 bucket ticker 级 query，仅使用 sector ETF / 市场宽关键词

**brief_generation_pipeline**

- Given raw_items 50 条，When pipeline 完成 stage_8，Then evidence_pool ≤ 20 条按 final_impact_score 降序
- Given evidence 入选 MorningBrief，When 查看 score_breakdown，Then 必须包含 source_reliability、recency_weight、novelty_weight、portfolio_linkage、event_materiality、market_confirmation
- Given 两条新闻 content_hash 相同但 source_tier 不同，When stage_3 执行，Then 保留 source_tier 高的（不按时间保留转载）
- Given 两个高可信来源对关键数字冲突，When conflict_resolve 执行，Then evidence 标记 conflict=true / requires_review=true，且 LLM 不得输出裁决性结论
- Given LLM request 组装完成，When 敏感扫描执行，Then body 不得包含 alias_map 中任意真实 ticker、本轮 detected_tickers 或具体 weight%
- Given evidence.title 含 `Tencent` / `腾讯控股` 等公司名但不含 ticker，When ticker_aliasing 执行，Then 这些名称必须基于 `sensitive_entity_dictionary` 替换为同一 `E_xxxx` alias，Text LLM request 不得保留原公司名
- Given Text LLM 输出自主生成真实 ticker 或公司名，When 输出敏感扫描执行，Then 触发重试或替换为 alias，不直接展示
- Given Text LLM request 组装完成，When 检查白名单字段，Then evidence 只允许携带 `asset_class`，不得携带 `sector`、`region`、`exposure_bucket`、`weight_band`、`portfolio_linkage` 或 `is_external`
- Given LLM 输出引用不存在的 evidence 或 quote_span 无法定位，When 校验，Then 拒绝并重试一次
- Given LLM 输出数字、单位或方向词与 quote_span 不一致，When accuracy_validator 执行，Then 拒绝并重试一次
- Given LLM 输出"本周/今日/昨晚"等时间表达与 evidence 时间窗不一致，When accuracy_validator 执行，Then 拒绝并重试一次
- Given accuracy_validator 连续 3 次失败，When 触发，Then 输出保守 brief 不报错
- Given ai_judgement_summary > 200 字，When 生成，Then 自动重试更短版本
- Given exposure_bucket 某类 ticker 数 < 3，When k_anonymity 校验（k=3），Then 合并到 other_equity
- Given 客户持仓 ticker < 15，When 冷启动生成 bucket，Then 启用 `coarse_bucket_mode`，且 Text LLM prompt 仍不包含 bucket 名称
- Given 当天有效 judgement 只有 1 条，When brief 生成，Then 只输出 1 条，不强行凑满 3 条

**morning_base_case_and_ai_summary**

- Given brief 成功生成，When 渲染，Then base_case 使用 Fraunces serif 30px + 3px 橙色竖线
- Given summary 含 `[1]`，When 用户点击，Then 对应 drawer 打开并高亮 evidence ①
- Given summary 引用 < 2 条，When 生成完成，Then 重试一次仍失败则保守文案

**local_evidence_qa**

- Given 用户针对某条 judgement 提交追问，When LLM 返回，Then 回答含 ≥ 1 个 cited_evidence_ids 与对应 quote_span
- Given 用户针对单条 evidence 提交追问，When LLM 返回，Then cited_evidence_ids 只能包含该 evidence
- Given QA 使用的 alias_map 已过期，When 用户提交追问，Then 返回 `brief_expired` 并提示重新生成 brief
- Given LLM 引用超出 local scope 或 quote_span 无法定位，When 校验，Then 丢弃回答

### 6.2 P1 功能验收

**research_pdf_upload**

- Given 用户上传 ≤10MB PDF，When 解析完成，Then 整流程目标 ≤ 60 秒；若超过则显示 queued / processing 状态
- Given PDF 含扫描页，When stage_b OCR 执行，Then parse_report 显示实际 OCR 页数
- Given PDF 含图表，When stage_c 执行，Then parse_report 显示 caption 成功数、失败数和失败页码
- Given PDF 中识别出 BABA（universe 外），When 展示 parse_report，Then External tickers 区域显示 BABA 并标注 warning
- Given 用户点击 `Re-analyze with uploads`，When 触发，Then 仅重跑 pipeline stage_4 起不重采集，完成 ≤ 30 秒
- Given 用户已有 5 份活跃上传，When 尝试新上传，Then 提示"请先删除旧上传"
- Given vision API 超时，When caption 失败，Then 该图表 chunk 标记 caption_unavailable，不阻塞其他 chunk
- Given chunking / ticker_detection / local_embedding 任一 stage 部分失败，When parse_report 展示，Then 成功 chunk 仍可入池，失败 chunk 显示 partial_failure 明细
- Given 用户未确认 PDF 可被第三方处理，When 需要 vision LLM，Then 跳过 vision caption，仅保留文本/表格 chunk
- Given 用户首次上传 PDF，When 上传面板打开，Then 展示第三方图表识别确认文案；未勾选时上传可继续但 parse_report 显示 `caption_unavailable_by_policy`

**global_evidence_qa**

- Given 用户提交全局追问，When LLM 返回，Then 回答含 ≥ 1 个 cited_evidence_ids 与对应 quote_span
- Given LLM 引用超出 scope 或 quote_span 无法定位，When 校验，Then 丢弃回答

**evidence_drawer**

- Given 点击 judgement 行，When drawer 打开，Then 主页不遮罩，用户可继续滚动
- Given drawer 打开后按 ESC，When 触发，Then 关闭且焦点返回
- Given 点击 PDF evidence 的 Read full article，When 触发，Then PDF viewer 打开并定位到对应 page + bbox

**portfolio_map**

- Given 持仓 9 项（含 watchlist），When 渲染，Then 持仓按 weight 占面积，watchlist 独立一行
- Given 涨跌数据存在，When 渲染，Then 必须同时含符号与颜色

### 6.3 性能验收

- 主页首屏 TTI ≤ 2 秒
- evidence_drawer 打开 ≤ 300ms
- 晨报生成总耗时 ≤ 90 秒
- qa 接口响应 p95 ≤ 15 秒（evidence_pool ≤ 200 chunks、单用户本地 demo、并发 1）
- PDF 上传到 ready ≤ 60 秒（10MB 内）
- 重分析 ≤ 30 秒
- conservative brief 触发率在 ≥50 条 golden set 回归中 ≤ 10%，且生产环境按周/月监控 `conservative_brief_triggered`；超出需检查数据源或 validator 过严

### 6.4 安全验收

- Given raw_portfolio 含 `{NVDA, 18%, $5M}`，When 任一 Text LLM 调用执行，Then request body 不含 `NVDA`、`Nvidia`、独立的 `18`、`5000000`、`sector_bucket` 或 `weight_band`，仅可出现无语义 alias `E_a3f9` 与 `asset_class: equity`
- Given LLM 调用完成，When audit log 写入，Then 含 request_hash 与 cited_evidence_ids；demo 模式不含完整 prompt 与 alias_map，合规审计模式仅保存加密 redacted 版本
- Given audit_mode 从 demo 切换到 compliance，When 查看历史日志，Then 切换前记录标识为 demo 且不得用于合规留痕
- Given 敏感扫描匹配 client_name 关键词，When request body 命中，Then 阻断并告警
- Given 前端 localStorage 检查，When 执行，Then 不含 portfolio 结构字段
- Given bucket 含 2 个 ticker（< k=3），When k_anonymity 校验，Then LLM 输入无该 bucket 独立项
- Given vision LLM 调用研报页面截图，When 执行，Then request 不含 user_id、session_id、account_id、portfolio_id，调用类型审计记录为 `vision`，caption 返回后经 ticker_aliasing 才入 evidence_pool
- Given 第三方 embedding 开关未显式开启，When PDF chunk 或新闻 chunk 需要向量化，Then 使用本地 embedding，不发第三方 API
- Given 第三方 embedding 被显式开启，When request body 组装，Then chunk 文本必须先完成 ticker_aliasing，且不得包含真实公司名
- Given 用户 B 尝试访问用户 A 上传的 PDF，When 请求，Then 后端拒绝并返回 403
- Given yfinance 名称字段刷新发现 ticker 更名或缺少中文别名，When 每日 refresh diff 生成，Then admin diagnostics 显示需要维护 `company_alias_zh.yml`

### 6.5 可访问性验收

- 所有涨跌同时含 ▲▼ 与颜色
- 文本与背景对比度 ≥ 4.5:1
- 交互元素 focus ring（2px orange_600 outline + 2px offset）
- 日期时间含日期（`Apr 21, 16:00 → Apr 22, 08:30 HKT`）

### 6.6 异常场景验收

- 数据源全失败：主页 `Data sources unavailable`，不渲染 judgements
- 单源降级：顶部 chip `{N} source degraded` + base_case 脚注
- LLM 全 provider 失败：保守 brief
- redis 缓存失效：重跑 pipeline；90 秒内未完成则上一日 brief（不含 portfolio）标 `stale`
- PDF 解析失败：展示失败原因，不影响其他已上传 PDF
- OCR 无结果：parse_report 明确提示"此 PDF 为扫描版且 OCR 未识别，建议上传文字版"
