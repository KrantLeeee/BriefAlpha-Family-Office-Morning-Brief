## ADDED Requirements

### Requirement: ticker_aliasing 命名规则

系统 SHALL 为每个进入 LLM 输入的 ticker 生成无语义随机 alias，格式 `E_{4-6位随机hex}`（如 `NVDA → E_a3f9`、`0700.HK → E_7b21`）。alias 命名 MUST NOT 携带行业、地区、是否外部标的等任何语义信息。

#### Scenario: 命名无语义

- **WHEN** 任一 ticker 被分配 alias
- **THEN** alias 字符串与 ticker 行业、地区、是否 universe 外无任何映射关系，重启进程后会重新随机生成

#### Scenario: universe 外 ticker 同样匿名

- **WHEN** PDF 中识别出 universe 外 ticker（如 `BABA`）
- **THEN** 同样生成 `E_xxxx` alias 进入 LLM 输入；`is_external=true` 仅在本地 diagnostics / parse_report 中可见

### Requirement: alias_map 加密生命周期

系统 SHALL 按 brief_id 将 alias_map 加密存储至当日 16:00 HKT，过期自动删除。alias_map MUST 仅供后端解密，MUST NOT 返回前端、写入审计日志、进入 LLM request body。

#### Scenario: 过期自动清理

- **WHEN** 当日 16:00 HKT 触发清理任务
- **THEN** 当日所有 brief 的 alias_map ciphertext 被永久删除，QA 此后返回 `brief_expired`

#### Scenario: 加密存储

- **WHEN** alias_map 写入磁盘
- **THEN** 文件内容以对称加密保存，密钥来自本地 secrets，未加密形态仅存在内存

### Requirement: sensitive_entity_dictionary

系统 SHALL 维护 sensitive_entity_dictionary，自动来源 = privacy-safe universe 内 ticker 通过 yfinance 拉取的 symbol / longName / shortName / quoteType / exchange + 港股 `.HK` / 去前导零 / HKEX 前缀变体；手工来源 = `config/company_alias_zh.yml`（≥ 30-50 个核心标的，覆盖中文名 / 简称 / 创始人指代 / 市场俗称）。MUST 每日采集前刷新 yfinance 字段。

#### Scenario: 输入端替换覆盖公司名

- **WHEN** evidence.title 含 `Tencent` 或 `腾讯控股` 但不含 ticker
- **THEN** ticker_aliasing 基于 sensitive_entity_dictionary 将公司名替换为同一 alias，Text LLM request 不保留原公司名

#### Scenario: ticker 改名 / 退市 admin 警告

- **WHEN** 每日 yfinance 名称字段刷新发现 ticker 改名或缺少中文别名
- **THEN** 系统生成 admin diagnostics 告警，提示需要更新 `company_alias_zh.yml`

### Requirement: 字段白名单（输入侧）

数据脱敏层 SHALL 在交付 LLM 前剥除 evidence 上的 sector / industry / region / exposure_bucket / weight_band / portfolio_linkage / is_external 字段，仅保留 evidence_id / title_aliased / excerpt_aliased / quote_span_aliased / source_tier / asset_class / published_at。

#### Scenario: 字段白名单生效

- **WHEN** evidence 进入 anonymization 阶段
- **THEN** 输出对象只包含上述白名单字段；多余字段被丢弃且 MUST NOT 出现在 wrapper 接收的 payload 中

### Requirement: weight_band 不入 LLM

weight_band MUST NOT 出现在 Text LLM prompt 任何字段；仅用于本地 BPS scoring、前端授权展示、审计解释与人工 debug。

#### Scenario: weight_band 抑制

- **WHEN** 任意 LLM request 组装完成
- **THEN** request body 不含 `weight_band` 键或对应 string 字面值

### Requirement: 安全反映射

系统 SHALL 在 LLM 输出经过 accuracy_validator 后、返回前端前对 alias 做"安全反映射"。反映射 MUST 是上下文敏感的：仅当某 alias 出现位置可被某条 validated cited evidence 的 quote_span 锚定（即 alias 是 cited evidence 中已存在的 alias）时，才反映射为真实 ticker / 公司名。反映射结果可下发授权前端展示，但 alias_map 表本身 MUST NOT 下发。

凡是不属于 validated cited evidence 上下文的 alias（包括但不限于：LLM 自主生成但无 quote_span 锚定的 alias、输出端反向敏感扫描"用 alias 替换 LLM 自创真实 ticker"产生的 alias、引用了非 cited 范围 evidence 的 alias）MUST 标记为 `unsafe_generated_alias`。renderer 对 `unsafe_generated_alias` MUST 保持占位（如 `[redacted]`）或删除整段，MUST NOT 直接还原为真实 ticker / 公司名。

公司名替换可能造成长度变化、多别名（中英文 / 简称 / 交易所变体）归一同 alias 等不可逆变换；reverse_alias 实现 MUST 配合 cited-evidence 上下文逻辑，MUST NOT 全文 string-replace。alias_offset_map 仅用于 quote_span 双坐标转换，MUST NOT 单独驱动正文反映射。

#### Scenario: drawer 展示真实 ticker

- **WHEN** drawer api 返回 evidence
- **THEN** evidence.title / excerpt 显示真实 ticker / 公司名，但响应 payload 不含 alias_map 表

#### Scenario: 输出扫描替换出 alias

- **WHEN** LLM 自主生成的真实 ticker 被输出端反向敏感扫描替换为 `E_xxxx`
- **THEN** 该 alias 标记 `unsafe_generated_alias`，renderer MUST NOT 还原，保持占位或删除该段落

#### Scenario: 无 quote_span 锚定的 alias

- **WHEN** LLM 段落出现 alias 但无 quote_span 锚定到对应 cited evidence
- **THEN** validator 已将该段落判为不合格触发重试；若重试后仍无锚定，renderer 不反映射该 alias，保持 alias 形态或删除该段落

#### Scenario: 引用非 cited 范围

- **WHEN** LLM 输出文本中出现的 alias 仅在 evidence_pool_full 中存在但不在该次回答的 cited_evidence_ids 中
- **THEN** 该 alias 不被反映射，触发一次重试或保持 alias 形态返回

### Requirement: ticker 与公司名变体规则

替换规则 SHALL 覆盖：大小写归一、去标点、`$NVDA` / `NVDA.O` / `NASDAQ:NVDA` / `HKEX:0700` / `700.HK` 等交易所格式、中文全称 / 简称、市场俗称。

#### Scenario: 多种交易所格式

- **WHEN** evidence 含 `NASDAQ:NVDA` 与 `$NVDA`
- **THEN** 两种写法均被替换为同一 alias `E_a3f9`

### Requirement: replacement segment list 与 quote_span 双坐标转换

ticker / 公司名替换 MUST 在执行替换的同时为每个被替换片段生成 replacement segment list；每条 segment SHALL 包含至少：`field`（如 `title` / `excerpt` / `caption`）、`orig_start`、`orig_end`、`alias_start`、`alias_end`、`original_text`、`alias`。同一 evidence 内多次出现同一 alias、中英文 / 简称归一为同 alias 的不同 original_text 都 MUST 各生成独立 segment。

`quote_span_aliased → quote_span_original` 的转换 MUST 基于 segment list 做区间映射（按 alias_start / alias_end 二分查找命中的 segment，再换算回原文偏移），MUST NOT 依赖任何"仅累加替换前后长度差"的简单 cumulative offset 算法作为唯一依据；cumulative offset 仅可作为命中后的优化加速，且 MUST 在测试中与 segment-based 算法逐字符对账。

转换函数 SHALL 在以下任一情况返回明确失败（由 wrapper / validator 视为 quote_span 不可定位、触发重试或保守 brief），MUST NOT 静默返回近似偏移：(a) `quote_span_aliased` 跨越多个 segment 且其中含 alias 内部偏移；(b) segment 之外的偏移落在替换边界内（即 quote_span_aliased 起止落在 alias 字符串中部）；(c) 对应 evidence_id 在 segment list 中无任何记录。

#### Scenario: 同一 alias 多次出现

- **WHEN** evidence.excerpt 含 `Tencent ... Tencent ... 腾讯` 三处，全部归一为 alias `E_7b21`
- **THEN** segment list 含 3 条独立 segment（各自 orig_start/orig_end/alias_start/alias_end），quote_span_aliased 落在第 2 处时能反向定位到对应原文位置而非第 1 或第 3 处

#### Scenario: 中英文长度不同

- **WHEN** `Nvidia`（6 字符）与 `英伟达`（3 字符）替换为同一 alias `E_a3f9`（5 字符）
- **THEN** segment list 分别记录 `original_text=Nvidia`（长度 6）与 `original_text=英伟达`（长度 3），quote_span_original 长度根据命中的 segment 还原为 6 或 3，不被 cumulative offset 错算

#### Scenario: quote_span 落在 alias 内部

- **WHEN** LLM 返回的 quote_span_aliased 起止落在 alias 字符串中部（如 `E_a3f9` 的偏移 2-4）
- **THEN** 转换函数 MUST 返回失败，validator 触发一次重试，不接受近似偏移

#### Scenario: 与 cumulative offset 对账

- **WHEN** 单元测试用同一 evidence 跑 segment-based 与 cumulative offset 两种算法
- **THEN** 两者在所有合法 quote_span 上输出一致；不一致的边界 case MUST 以 segment-based 为准
