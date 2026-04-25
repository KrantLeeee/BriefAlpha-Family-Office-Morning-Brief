## ADDED Requirements

### Requirement: 持仓与 watchlist 管理

系统 SHALL 在本地维护 portfolio（含 ticker / weight / asset_class / is_watchlist 等字段），并提供后端只读接口供 brief-pipeline 与前端 portfolio_map 使用。持仓数据 MUST NOT 通过 LLM 调用、第三方 API 调用或埋点事件离开本地。

#### Scenario: 持仓本地隔离

- **WHEN** 任一 LLM / 第三方 API / 埋点请求被发出
- **THEN** request body 与 query string 中 MUST NOT 出现真实 weight 数字、account_id、client_name 或单客户完整 ticker 列表

#### Scenario: 前端展示真实权重

- **WHEN** 授权用户访问 `/api/portfolio`
- **THEN** 返回真实 weight 百分比与 ticker，仅供前端 portfolio_map 渲染，不写入任何 LLM prompt

### Requirement: exposure_bucket 与 weight_band

系统 SHALL 在本地按 sector + factor 规则将持仓映射到 exposure_bucket，并将每个 bucket 的总权重落入 weight_band（low / medium / high / dominant）。bucket 与 weight_band MUST NOT 进入 Text LLM prompt（含 evidence 字段、portfolio_context、score_breakdown）。

#### Scenario: bucket 仅本地使用

- **WHEN** brief-pipeline 计算 portfolio_linkage
- **THEN** portfolio_linkage 数值进入 score_breakdown 用于本地排序与 drawer 展示，但 Text LLM request body 不携带 exposure_bucket / weight_band / portfolio_linkage 字段

### Requirement: k-anonymity 强制

exposure_bucket 成立的最小 ticker 数 k_anonymity_threshold 默认为 3。bucket 内 ticker 数 < 3 时 MUST 合并到 `other_equity` 或相邻 bucket。

#### Scenario: 小 bucket 合并

- **WHEN** `hk_internet` bucket 仅含 2 个 ticker
- **THEN** 系统将其合并到 `other_equity`，且 LLM 输入中不出现 `hk_internet` 作为独立项

### Requirement: coarse_bucket_mode 与冷启动

客户持仓 ticker < 15 时系统 MUST 自动启用 coarse_bucket_mode：仅生成 ≤ 4 个超大类 bucket（如 us_equity / hk_equity / macro_etf / cash_or_other），每个粗 bucket 至少 5 个可查询 ticker；decoy 数 ≤ 客户持仓 ticker 数 × 4，超过则降级为宽基 / sector ETF 查询。冷启动校验失败时 MUST NOT 发起 ticker 级第三方 API 查询。

#### Scenario: 触发 coarse mode

- **WHEN** 新客户导入 10 个 ticker
- **THEN** 系统生成最多 4 个粗 bucket，每个粗 bucket 至少含 max(k,5) 个可查询 ticker，且 universe 至少 20 个 decoy / 行业代表 ticker

#### Scenario: 冷启动失败禁查

- **WHEN** 冷启动校验未通过
- **THEN** 系统拒绝向第三方数据源发任意 ticker 级查询，仅允许使用宽基 / sector ETF 与市场宽关键词

### Requirement: privacy-safe universe 构造

universe 构造 SHALL 来源于 `config/ticker_sector_overrides.yml` + yfinance sector / industry + 行业代表 / 宽基 ETF 池 + decoy tickers；MUST NOT 包含 account / portfolio_id / weight / 客户标签或持仓排序信息；构造结果 SHALL 持久化以供 data-ingestion 与 audit 复用。

#### Scenario: universe 字段白名单

- **WHEN** universe 被序列化用于 data-ingestion 调用
- **THEN** 序列化结果只含 ticker 与 asset_class，不含权重、客户标签或持仓顺序

### Requirement: 行业分类合规边界

MVP MUST NOT 直接声称使用 GICS；sector / industry 数据 SHALL 来源于 yfinance 字段 + 手工 override 表（≥ 30 行覆盖 demo 持仓 / watchlist / 核心港美股）。

#### Scenario: GICS 边界

- **WHEN** 文档或 UI 声明 sector 来源
- **THEN** 文案明确标注 "yfinance + manual overrides"，不写"GICS classification"
