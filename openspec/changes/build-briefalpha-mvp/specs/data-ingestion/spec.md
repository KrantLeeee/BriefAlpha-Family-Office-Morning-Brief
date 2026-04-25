## ADDED Requirements

### Requirement: 多源公开数据采集

系统 SHALL 同时从 market（yfinance + 备源）、news（GDELT + Google News RSS）、official（SEC EDGAR RSS + HKEX announcements RSS）三类公开源采集 raw_items；任一类源失败 MUST NOT 阻塞其他类。

#### Scenario: 三类源全部可用

- **WHEN** 07:00 HKT cron 触发滚动采集，三类源均返回 200
- **THEN** evidence_pool 内同时存在 market / news / official 来源条目，且 source_health 记录三类均为 `ok`

#### Scenario: 单类源失败

- **WHEN** GDELT 返回 5xx 或超时
- **THEN** 系统 fallback 至 Google News RSS，并把 source_health.news 标记为 `degraded`，其他类别正常采集

#### Scenario: 全部源失败

- **WHEN** 三类源在 freeze 时间前全部连续失败
- **THEN** 系统不抛出异常，标记三类 source_health=`failed`，由 brief-pipeline 进入保守 brief 路径

### Requirement: privacy-safe universe 查询约束

系统 MUST NOT 用单客户持仓列表直接构造第三方 API 查询；所有 ticker 级查询 SHALL 仅基于 privacy-safe universe。privacy-safe universe = 客户持仓 + watchlist + 行业代表 + 宽基代表 + decoy tickers，且每个 exposure_bucket 至少包含 max(k_anonymity_threshold, 5) 个可查询 ticker。

#### Scenario: universe 满足稀释约束

- **WHEN** 客户持仓 30 个 ticker、5 个 bucket 均满足 k≥3
- **THEN** universe 包含至少 60 个 decoy / 行业代表 ticker，且第三方 API 查询字符串中不出现客户持仓单独成组的 query

#### Scenario: 持仓过少触发 coarse_bucket_mode

- **WHEN** 客户持仓 ticker 数 < 15
- **THEN** 系统自动启用 coarse_bucket_mode，universe 至少含 20 个 decoy / 行业代表 ticker，且 bucket 数 ≤ 4 个粗分类，每个粗 bucket ≥ max(k,5) 个可查询 ticker

#### Scenario: bucket 无法满足稀释约束

- **WHEN** 某 bucket 即使加入 decoy 仍不满足 k=3
- **THEN** 系统不向第三方行情 / 新闻 API 发该 bucket 任一 ticker 级查询，仅使用宽基 / sector ETF 与市场宽关键词

### Requirement: ticker 与时区标准化

采集层 SHALL 在写入 evidence_pool 前完成 ticker 与时间标准化：港股 symbol 保留 `.HK` 后缀；所有时间字段以 UTC 存储，输出时按 `brief_timezone` 转换；盘前盘后状态独立标记。

#### Scenario: 港股 symbol 标准化

- **WHEN** yfinance 返回 `0700.HK` 行情
- **THEN** 写入 evidence 的 detected_tickers 字段保持 `0700.HK` 格式，不被截断为 `0700`

#### Scenario: 时区一致性

- **WHEN** SEC EDGAR 返回美东时间 16:30 的 8-K
- **THEN** evidence.published_at 以 UTC 存储，前端按 Asia/Hong_Kong 渲染为对应 HKT 时间，且标记为 `us_after_hours`

### Requirement: 限流与重试

采集层 SHALL 对每个第三方调用使用 exponential backoff 重试 ≤ 3 次；每次调用 MUST 写入 redis 计数用于 source_health 聚合。

#### Scenario: 命中限流

- **WHEN** Alpha Vantage 返回 429
- **THEN** 系统按 1s / 2s / 4s 退避重试 3 次仍失败后切换备源或标记 degraded，且 redis 中累计 failure_count + 1

### Requirement: 原始 response 审计副本

采集层 MUST 将每次外部调用的原始 response 压缩存储 7 天，用于 audit 与 quote_span 复核；副本 MUST NOT 进入前端可见路径。

#### Scenario: 审计回查

- **WHEN** admin 在 7 天内追溯某条 evidence 的来源
- **THEN** 系统能从压缩副本中按 evidence.source_url + fetched_at 恢复原始字段

### Requirement: official 源 symbol 映射与可用性

official adapter SHALL 内置 ticker ↔ external_id 映射：(a) SEC EDGAR 需要 `ticker → CIK`，映射表来源于 SEC `company_tickers.json`，每周刷新；(b) HKEX announcements 需要 `ticker → 港交所股票代码 / company short name`，映射表由 HKEX 公开列表生成（去前导零、`.HK` 归一），每周刷新。SEC EDGAR 调用 MUST 携带合规 User-Agent（含联系邮箱），并按 SEC 规定限速（≤ 10 req/s）；缺少 User-Agent 配置时启动期校验 MUST 失败。

#### Scenario: 缺失映射

- **WHEN** privacy-safe universe 中某 ticker 在 SEC company_tickers.json 中查不到 CIK
- **THEN** 该 ticker 跳过 EDGAR 拉取，写入 admin diagnostics warning，不阻塞其他 ticker；source_health.official 不因此整体 degraded

#### Scenario: SEC User-Agent 强制

- **WHEN** 任意 SEC EDGAR 请求发出
- **THEN** request header 含合规 User-Agent 字符串（格式 `BriefAlpha/<version> (<contact-email>)`）；未配置时进程启动期 MUST 失败并提示

#### Scenario: 映射表周刷新

- **WHEN** scheduler 触发每周刷新任务
- **THEN** SEC company_tickers.json 与 HKEX 列表被重新拉取并写入本地映射表；diff 写入 admin diagnostics 用于追踪上市 / 退市 / 改名
