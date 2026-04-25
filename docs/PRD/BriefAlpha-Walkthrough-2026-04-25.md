# BriefAlpha 一日样例 — 2026-04-25 早晨

> 这份文档是 PRD 的配套评审材料，目的是用一个**具体的一天**把 PRD 里所有抽象规则跑一遍，证明它们能落地、能闭环。
>
> 阅读建议：从头读到尾大概 10-15 分钟。每一节先讲故事，再展示数据。术语第一次出现会用括号简短解释。

---

## 0. 这一天发生了什么（剧情背景）

假设今天是 **2026-04-25 周六早上 8:30 HKT**，合伙人即将开晨会。

过去 24 小时，市场上发生了几件值得关注的事：

1. **NVDA 盘后下调 Q1 数据中心营收指引** — 美股盘后跌 6%，多家媒体跟进，但路透和彭博给出的"下调幅度"数字不一致。
2. **腾讯（0700.HK）港交所公告扩大回购计划** — 单日授权额度上调 50%。
3. **美联储理事再次鹰派发言** — 暗示再加息一次。
4. **高盛中国互联网研报**（用户昨晚上传 PDF）— 上调中国互联网行业评级到 Overweight。
5. 其他常规市场新闻、行情若干。

这就是 BriefAlpha 今天要消化、过滤、生成晨报、并支持追问的全部输入。

---

## 1. 输入：客户持仓 + watchlist + privacy-safe universe

### 1.1 客户的真实持仓（仅本地后端可见，永不出后端）


| Ticker  | 名称     | 权重  | 类别    |
| ------- | ------ | --- | ----- |
| NVDA    | 英伟达    | 18% | 美股科技  |
| 0700.HK | 腾讯     | 15% | 港股互联网 |
| AAPL    | 苹果     | 12% | 美股科技  |
| MSFT    | 微软     | 10% | 美股科技  |
| TLT     | 长债 ETF | 10% | 利率    |
| 9988.HK | 阿里巴巴   | 8%  | 港股互联网 |
| GLD     | 黄金 ETF | 8%  | 商品    |
| TSLA    | 特斯拉    | 5%  | 美股    |
| 3690.HK | 美团     | 5%  | 港股互联网 |
| CASH    | 现金     | 9%  | 现金    |


**关键事实**：持仓 ticker 数 = **10 < 15** → 系统**自动启用 `coarse_bucket_mode`**（粗分类模式）。

> **为什么？** PRD §2.4.3 规定，持仓少于 15 时，5×3 的细分（5 sector × 3 region）会让每个分类只有 1-2 个 ticker，外人一眼能猜出。所以系统强制只用 3-4 个超大类。

### 1.2 用户 watchlist（在看但不持有）

`AMD` / `GOOGL` / `1810.HK`（小米）

### 1.3 系统自动生成的 privacy-safe universe（这才是发给第三方 API 的清单）

PRD 要求：

- `decoy（陪跑标的）数量 ≥ 持仓 × 2` → 至少 20 个 decoy
- 每个粗 bucket 至少 5 个 ticker
- decoy 不超过持仓 × 4，避免噪声污染评分

系统生成的 universe（共 **34 个 ticker**）：


| 粗 bucket          | 持仓                        | watchlist  | decoy（陪跑）                                                     |
| ----------------- | ------------------------- | ---------- | ------------------------------------------------------------- |
| **us_equity**     | NVDA, AAPL, MSFT, TSLA    | AMD, GOOGL | AMZN, META, AVGO, ORCL, NFLX, JPM, V, COST                    |
| **hk_equity**     | 0700.HK, 9988.HK, 3690.HK | 1810.HK    | 1299.HK, 0939.HK, 9618.HK, 1024.HK, 9999.HK, 0388.HK, 0005.HK |
| **macro_etf**     | TLT, GLD                  | —          | SPY, QQQ, EEM, IEF, GDX, DIA                                  |
| **cash_or_other** | CASH                      | —          | —                                                             |


**核验**：

- 持仓 10 个 + watchlist 3 个 + decoy 21 个 = 34 ✅
- decoy/持仓 = 21/10 = 2.1x ✅（PRD 要求 ≥ 2x）
- decoy/持仓 = 2.1x < 4x ✅（PRD 要求 ≤ 4x）

> **重点**：发给雅虎财经、GDELT、SEC 这些外部 API 的，是这 34 个 ticker 的批量请求。**外人就算抓到完整 query log，也只能知道"客户关心 us_equity / hk_equity / macro_etf 这三个大方向"，无法精确反推 NVDA 占 18%、腾讯占 15% 这种持仓细节。**

---

## 2. 采集：从外部世界抓回来什么

时间窗：**2026-04-24 07:00 HKT 开始滚动采集，2026-04-25 07:55 HKT freeze**。

### 2.1 各数据源采集结果


| source_tier  | 数据源                             | raw_items                                                                     | 状态    |
| ------------ | ------------------------------- | ----------------------------------------------------------------------------- | ----- |
| **market**   | yfinance                        | 34 个 ticker × 隔夜行情 + 8 个指数（S&P / NASDAQ / HSI / VIX / DXY / GOLD / WTI / 10Y） | ok    |
| **news**     | GDELT                           | 80 条                                                                          | ok    |
| **news**     | Google News RSS                 | 45 条                                                                          | ok    |
| **official** | SEC EDGAR RSS                   | 5 条 8-K（含 NVDA）                                                               | ok    |
| **official** | HKEX announcements              | 3 条（含腾讯回购）                                                                    | ok    |
| **official** | Federal Reserve RSS             | 2 条（含理事讲话稿）                                                                   | ok    |
| **research** | 用户上传 PDF（高盛 China Outlook 28 页） | 47 个 chunk                                                                    | ready |


### 2.2 system source_health 快照

```
market    ok  (34/34 tickers fetched, latency 1.8s)
news      ok  (125 items, GDELT 80 + Google 45)
official  ok  (10 items, SEC 5 + HKEX 3 + Fed 2)
research  1 upload active
```

### 2.3 raw_items 总数

130 条新闻 + 10 条 official + 47 个 research_chunk + 42 行情快照 ≈ **229 个 raw items**

> **注意**：行情数据通常不直接进 evidence_pool，而是作为"市场印证"信号支撑新闻类 evidence 的 `market_confirmation` 评分。所以真正进入信息处理 pipeline 的"待评估事件" ≈ 187 条。

---

## 3. 处理：从 187 条原始信息到 20 条 evidence

### 3.1 Pipeline 九步执行结果


| 阶段                         | 输入数 | 输出数                   | 关键动作                                         |
| -------------------------- | --- | --------------------- | -------------------------------------------- |
| stage_1 normalize          | 187 | 187                   | 字段统一、时区转 UTC                                 |
| stage_2 entity_linking     | 187 | 187                   | 识别每条提到的 ticker（命中 universe 内多少、universe 外多少） |
| stage_3 dedupe             | 187 | **62 个独立事件**          | 把"同一件事的不同来源"聚合，被合并的来源进 supplementary_sources |
| stage_4 base_scoring       | 62  | 62                    | 算 `source_reliability × recency × novelty`   |
| stage_5 portfolio_mapping  | 62  | 62                    | 本地映射 evidence → 粗 bucket（**永不调 LLM**）        |
| stage_6 final_scoring      | 62  | 62                    | 算 BPS 综合分                                    |
| stage_7 conflict_resolve   | 62  | 62（**1 条标 conflict**） | NVDA 下调幅度路透 vs 彭博                            |
| stage_8 evidence_selection | 62  | **20 条**              | 按 final_impact_score 取 top 20                |
| stage_9 anonymization      | 20  | 20                    | ticker 替换为 `E_xxxx`，公司名也替换                   |


### 3.2 Top 5 evidence 与 score_breakdown（这是给 drawer/debug 看的，不进 LLM）


| rank | evidence_id | 标题摘要                    | 来源                            | source_tier | 关键指标                                                                 |
| ---- | ----------- | ----------------------- | ----------------------------- | ----------- | -------------------------------------------------------------------- |
| 1    | ev_001      | NVDA Q1 数据中心指引下调        | SEC 8-K + 路透 + 彭博 + CNBC      | official    | linkage=1.0 / materiality=1.0 / confirmation=1.0 / **conflict=true** |
| 2    | ev_002      | 腾讯扩大回购授权额度 50%          | HKEX 公告 + 财新                  | official    | linkage=1.0 / materiality=1.0 / confirmation=1.0                     |
| 3    | ev_003      | 美联储 Williams 鹰派发言       | Fed RSS + Reuters + Bloomberg | official    | linkage=0.6 / materiality=1.0 / confirmation=1.0                     |
| 4    | ev_004      | 高盛上调中国互联网评级至 Overweight | 用户上传 PDF（page 4）              | research    | linkage=1.0 / materiality=0.6 / confirmation=0.3                     |
| 5    | ev_005      | 美股科技板块盘后跌幅扩大            | yfinance + Bloomberg          | market      | linkage=1.0 / materiality=0.6 / confirmation=1.0                     |


ev_001 的完整 `score_breakdown` 示例：

```
source_reliability:  1.0   (SEC 8-K 主源)
recency_weight:      1.0   (距 freeze 仅 2.5 小时)
novelty_weight:      1.0   (新事件)
portfolio_linkage:   1.0   (命中 us_equity 粗 bucket，且为持仓核心)
event_materiality:   1.0   (盈利指引)
market_confirmation: 1.0   (盘后行情 + 3 家高质媒体印证)
─────────────────────────
final_impact_score:  1.0   (满分)
conflict:            true  (路透 -8% vs 彭博 -10%)
requires_review:     true
```

### 3.3 冲突事件细节（ev_001）

```
事件：NVDA Q1 数据中心营收指引下调

来源 A（路透）:  "Nvidia cut Q1 data center revenue guidance by 8%"
                 quote_span: chars 234-281
来源 B（彭博）:  "Nvidia lowered data center guidance roughly 10% versus consensus"
                 quote_span: chars 156-218

→ 数字差异 (8% vs 10%) 触发 structured_conflict_detection
→ evidence 标记 conflict=true / requires_review=true
→ LLM 不被允许"挑一个数字写进 brief"
→ 进入 brief 时必须展示「需人工复核」标记
```

---

## 4. LLM 收到的真实 prompt（安全核心展示）

这是 stage_9 之后，**实际发给 Anthropic / OpenAI Text LLM 的 request body**：

```json
{
  "task_instruction": "generate_morning_brief",
  "language": "zh",
  "aliased_evidence": [
    {
      "evidence_id": "ev_001",
      "title_aliased": "E_a3f9 cuts Q1 data center revenue guidance",
      "excerpt_aliased": "E_a3f9 announced today that Q1 data center revenue is expected to come in approximately 8-10% below previous guidance, citing softer enterprise demand and inventory normalization at major hyperscalers...",
      "quote_span_aliased": {"start": 0, "end": 220},
      "source_tier": "official",
      "asset_class": "equity",
      "published_at": "2026-04-24T20:15:00-04:00",
      "conflict": true
    },
    {
      "evidence_id": "ev_002",
      "title_aliased": "E_7b21 expands share repurchase authorization by 50%",
      "excerpt_aliased": "E_7b21 board approved an expansion of its share repurchase program, raising the authorized amount by 50% to support shareholder returns amid valuation discounts...",
      "quote_span_aliased": {"start": 0, "end": 198},
      "source_tier": "official",
      "asset_class": "equity",
      "published_at": "2026-04-25T07:30:00+08:00"
    },
    {
      "evidence_id": "ev_003",
      "title_aliased": "Fed Governor Williams signals one more rate hike likely",
      "excerpt_aliased": "Federal Reserve Governor Williams said in remarks that persistent core services inflation may warrant one additional rate increase before year-end, calling current policy 'mildly restrictive'...",
      "quote_span_aliased": {"start": 0, "end": 245},
      "source_tier": "official",
      "asset_class": "unknown",
      "published_at": "2026-04-24T14:00:00-04:00"
    }
    // ... ev_004 至 ev_020 类似结构
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
    ],
    "must_cite_at_least": 2,
    "max_judgements": 5
  },
  "output_schema": {
    "morning_base_case": "string <= 50 zh chars",
    "ai_judgement_summary": "string <= 200 zh chars with [n] citations",
    "judgements": "1-5 items, each with cited_evidence_ids and quote_span_aliased"
  }
}
```

### 4.1 这份 prompt 里**没有**什么（安全验证清单）

逐项核对 PRD §2.4 / §5.1.1 的禁止字段：


| 禁止项                                | 是否出现  | 验证                                                    |
| ---------------------------------- | ----- | ----------------------------------------------------- |
| 真实 ticker（NVDA / 0700.HK / TLT）    | ❌ 未出现 | 全替换为 `E_xxxx`                                         |
| 公司名（Nvidia / Tencent / 英伟达 / 腾讯）   | ❌ 未出现 | 输入端 ticker_aliasing 复用 sensitive_entity_dictionary 替换 |
| 具体 weight（18% / 15%）               | ❌ 未出现 | weight_band 也不传                                       |
| sector / industry / region         | ❌ 未出现 | 只有 `asset_class: equity`                              |
| exposure_bucket（us_equity 等）       | ❌ 未出现 | bucket 只在本地用                                          |
| portfolio_linkage（1.0 / 0.6 / 0.3） | ❌ 未出现 | score_breakdown 不进 prompt                             |
| is_external                        | ❌ 未出现 | 只在本地 diagnostics                                      |
| account_id / client_name / amount  | ❌ 未出现 | —                                                     |


> **关键洞察**：LLM 只知道有一只代号 `E_a3f9` 的股票（`asset_class: equity`）盈利指引下调了。它不知道这只股票在客户组合里占多少、属于什么行业、是不是核心持仓。**它的工作只是用人话把这条 evidence 表达出来，不参与排序和持仓判断**——排序和判断已经在本地 BPS 完成了。

### 4.2 sensitive_entity_dictionary 的工作示例

输入端 aliasing 之前，原文是这样：

```
"Nvidia (NVDA) cuts Q1 data center revenue guidance, sending shares down 6% in after-hours trading. CEO Jensen Huang noted softer enterprise demand."
```

经过 sensitive_entity_dictionary 替换后：

```
"E_a3f9 cuts Q1 data center revenue guidance, sending shares down 6% in after-hours trading. CEO [REDACTED_PERSON] noted softer enterprise demand."
```

替换的字面值：`Nvidia` / `NVDA` / `Jensen Huang`（创始人指代也在字典里）。

---

## 5. LLM 输出 + accuracy_validator 校验

### 5.1 LLM 第一次返回（aliased 形式）

```json
{
  "morning_base_case": "美股科技龙头盘后指引承压，港股回购信号活跃，美联储再现鹰派表述。",
  "ai_judgement_summary": "盘后 E_a3f9 下调 Q1 数据中心营收指引约 8-10%[1]，叠加 Fed 官员暗示年内或再加息一次[3]，美股成长板块短线承压。港股侧 E_7b21 扩大回购授权 50%[2]，对估值形成支撑。整体看，今日重点在科技指引修正与流动性预期再校准的相互影响。",
  "judgements": [
    {
      "rank": 1,
      "level": "elevated",
      "conclusion": "E_a3f9 数据中心指引下调，需关注 hyperscaler 资本开支趋缓信号（注：来源数字不一致，待复核）",
      "evidence_summary": "SEC 8-K 与多家媒体共同披露指引下调，但下调幅度路透报 8%、彭博报 10%，存在结构化冲突",
      "cited_evidence_ids": ["ev_001", "ev_005"],
      "reasoning_chain": {
        "observed": "E_a3f9 公告 Q1 数据中心营收指引较前次下调 8-10%[1]，盘后股价跌约 6%[5]",
        "portfolio_exposure": "evidence 已映射至本地 portfolio bucket（细节不展示给 LLM）",
        "inference": "若 hyperscaler 资本开支节奏放缓，AI 算力链估值或同步调整",
        "conclusion": "建议 review 同主题相关持仓的 thesis（不构成交易建议）"
      }
    },
    {
      "rank": 2,
      "level": "watch",
      "conclusion": "E_7b21 扩大回购授权 50%，释放管理层信心信号",
      "evidence_summary": "HKEX 公告今晨披露，回购授权额度由原方案上调 50%",
      "cited_evidence_ids": ["ev_002"],
      "reasoning_chain": {
        "observed": "E_7b21 董事会批准回购授权额度上调 50%[2]",
        "portfolio_exposure": "evidence 已映射至本地 portfolio bucket",
        "inference": "管理层在估值折让背景下加大回购，与近年港股龙头资本回报趋势一致",
        "conclusion": "对估值底部形成边际支撑"
      }
    },
    {
      "rank": 3,
      "level": "watch",
      "conclusion": "Fed Williams 鹰派发言，年内或再加息一次",
      "evidence_summary": "Fed 官方讲话稿与三家媒体一致，措辞为 'mildly restrictive' 与 'one additional hike'",
      "cited_evidence_ids": ["ev_003"],
      "reasoning_chain": {
        "observed": "Fed Williams 称当前政策'温和限制性'，年内或再加息一次[3]",
        "portfolio_exposure": "evidence 已映射至本地 portfolio bucket",
        "inference": "若加息预期重启，长端利率与成长股估值同步承压",
        "conclusion": "关注利率敏感资产与成长板块的同向风险"
      }
    }
  ]
}
```

### 5.2 accuracy_validator 校验过程

逐条跑 PRD §2.6 的 11 条规则：


| 规则                  | 检查内容                                                                          | 结果                                    |
| ------------------- | ----------------------------------------------------------------------------- | ------------------------------------- |
| 1. citation 存在      | ev_001 / ev_002 / ev_003 / ev_005 均在 evidence_pool 内                          | ✅                                     |
| 2. quote_span 附带    | 每条 citation 都有 quote_span_aliased                                             | ✅                                     |
| 3. quote_span 可定位   | 通过 alias offset map 反向定位到 evidence 原文                                         | ✅                                     |
| 4. 关键数字可找到          | "8-10%" 可在 ev_001 quote_span ±120 字符内找到（路透 8% + 彭博 10%）                       | ✅                                     |
| 5. summary 引用 ≥ 2 条 | 引用了 ev_001 / ev_002 / ev_003 共 3 条                                            | ✅                                     |
| 6. 定性结论锚定           | "鹰派" 锚定到 Williams 讲话原文 "mildly restrictive"                                   | ✅                                     |
| 7. 数字一致性            | "下调约 8-10%" — 与 quote_span 的两个数字（8%、10%）一致；"50%" 与 ev_002 一致；"6%" 与 ev_005 一致 | ✅                                     |
| 8. 极性/方向一致          | "下调"、"扩大"、"鹰派" 与原文方向词一致                                                       | ✅                                     |
| 9. 时间窗一致            | "盘后" → 美东 16:00-20:00 转 HKT，ev_001 published_at 04-24 20:15 EDT 命中            | ✅                                     |
| 10. 输出反向扫描          | 输出未出现 NVDA / Nvidia / 英伟达 / Tencent / 腾讯 / Williams 公司名                       | ✅（"Williams" 是 Fed 官员姓名，公开身份，不在公司黑名单） |
| 11. 总体通过            | —                                                                             | ✅                                     |


`accuracy_validation_passed = true` → 进入 alias 反映射。

### 5.3 alias 反映射后（最终展示给用户的版本）

```
morning_base_case: 美股科技龙头盘后指引承压，港股回购信号活跃，美联储再现鹰派表述。

ai_judgement_summary:
盘后英伟达（NVDA）下调 Q1 数据中心营收指引约 8-10%[1]，叠加 Fed 官员
暗示年内或再加息一次[3]，美股成长板块短线承压。港股侧腾讯（0700.HK）
扩大回购授权 50%[2]，对估值形成支撑。整体看，今日重点在科技指引修正
与流动性预期再校准的相互影响。

judgement #1 (elevated):
英伟达数据中心指引下调，需关注 hyperscaler 资本开支趋缓信号
⚠ 需人工复核（来源数字不一致）

judgement #2 (watch):
腾讯扩大回购授权 50%，释放管理层信心信号

judgement #3 (watch):
Fed Williams 鹰派发言，年内或再加息一次
```

---

## 6. 用户追问示例（local_evidence_qa）

### 6.1 用户操作

合伙人点击 judgement #1 → drawer 滑出 → 在底部 local_qa 输入框问：

> "为什么数据中心营收指引下调？给我原文表述。"

### 6.2 后端处理流

```
step_1: 用户问题中的 ticker 替换 → 问题中无 ticker，原样保留
step_2: 加载 ev_001 (judgement #1 引用的 evidence) 的 aliased 版本
step_3: 调用 LLM with scope=judgement, judgement_id=jd_001
step_4: LLM 返回 + accuracy_validator 校验
step_5: alias 反映射
step_6: 返回前端
```

### 6.3 LLM 收到的 prompt（仅包含 ev_001）

```json
{
  "task_instruction": "answer_user_question_grounded_in_evidence",
  "scope": "judgement",
  "user_question": "为什么数据中心营收指引下调？给我原文表述。",
  "aliased_evidence": [
    {
      "evidence_id": "ev_001",
      "title_aliased": "E_a3f9 cuts Q1 data center revenue guidance",
      "excerpt_aliased": "E_a3f9 announced today that Q1 data center revenue is expected to come in approximately 8-10% below previous guidance, citing softer enterprise demand and inventory normalization at major hyperscalers...",
      "source_tier": "official",
      "asset_class": "equity"
    }
  ],
  "output_constraints": {
    "must_cite_evidence_id": "ev_001",
    "max_chars": 200
  }
}
```

### 6.4 LLM 返回 + 反映射后的回答

> 根据公告原文，主要原因有两点[1]：
>
> 1. **企业端需求趋缓**（"softer enterprise demand"）
> 2. **大型云厂商库存正常化**（"inventory normalization at major hyperscalers"）
>
> 公告同时给出指引下调幅度区间为 8-10%。注意：路透与彭博对具体百分比的报道不一致（8% vs 10%），原始 SEC 文件以"approximately 8-10%"区间表述，**未给出单一精确数字**。
>
> [1] NVDA SEC 8-K, 2026-04-24 20:15 EDT — [查看原文 quote_span]

校验过程：

- ✅ 引用 ev_001（在 scope 内）
- ✅ 引用的"softer enterprise demand"等原文字符串可在 ev_001 quote_span 内定位
- ✅ "8-10%" 数字与原文一致
- ✅ 输出未出现 NVDA / Nvidia / 英伟达 字符串（反映射前）

---

## 7. 阅读时长复核（5 分钟预算）

按 PRD §2.8 预算：


| 模块                          | 阅读时间           |
| --------------------------- | -------------- |
| morning_base_case（35 字）     | 8 秒            |
| ai_judgement_summary（145 字） | 30 秒           |
| 3 × judgement.conclusion    | 45 秒           |
| 3 × evidence_summary        | 45 秒           |
| portfolio_map 扫视            | 30 秒           |
| playbook 扫视                 | 30 秒           |
| 一次 drawer 验证（用户在 ev_001）    | 45 秒           |
| 一次 local_qa 追问（如上）          | 45 秒           |
| **总计**                      | **≈ 4 分 18 秒** |


✅ 在 5 分钟预算内完成"5 分钟进入状态"目标。

---

## 8. 这一日案例验证了 PRD 哪些规则


| PRD 规则                                 | 本样例验证方式                                                      |
| -------------------------------------- | ------------------------------------------------------------ |
| §2.2 privacy-safe universe（decoy ≥ 2x） | universe 34 个，decoy 21/持仓 10 = 2.1x ✅                        |
| §2.4.3 coarse_bucket_mode（持仓 < 15）     | 持仓 10 → 自动启用 4 个粗 bucket ✅                                   |
| §2.3 dedupe + supplementary_sources    | 187 raw → 62 独立事件，被合并源未丢弃 ✅                                  |
| §2.3.1 结构化冲突检测                         | ev_001 路透 vs 彭博数字差异触发 conflict=true，LLM 未裁决 ✅                |
| §2.2 BPS 评分（novelty 不惩罚多源）             | ev_001 novelty=1.0 + confirmation=1.0 同时满分 ✅                 |
| §2.4.1 ticker_aliasing                 | NVDA → E_a3f9，Nvidia / 英伟达也被替换 ✅                             |
| §2.4.4 敏感扫描                            | request body 不含真实 ticker / 公司名 / weight / sector / bucket ✅  |
| §2.5.1 LLM 安全编排                        | 白名单 5 字段，禁止字段全部不出现 ✅                                         |
| §2.5.2 sensitive_entity_dictionary     | 输入端 + 输出端 + 创始人指代统一字典 ✅                                      |
| §2.6 accuracy_validator 11 条           | 全部通过（含数字一致 / 极性 / 时间窗） ✅                                     |
| §2.6 时间窗规则                             | "盘后" 命中美东 16:00-20:00 转 HKT 窗口 ✅                             |
| §2.8 5 分钟阅读预算                          | 实际 4 分 18 秒 ✅                                                |
| §3.2 主流程 cron                          | 07:00 滚动 + 07:55 freeze + 08:30 渲染 ✅                         |
| local_evidence_qa（P0）                  | scope=judgement 追问，引用 + quote_span 校验通过 ✅                    |
| §5.2.2 audit_mode = demo               | request_hash + cited_evidence_ids 写入 audit log，不存原始 prompt ✅ |


---

## 9. 如果换一种剧情会怎么样（延伸）

为了让评审更立体，列几个不展开但需要回答的"如果"：

### 9.1 如果今天什么都没发生（平淡日）

- raw_items 大幅减少 → top_k 不足 20
- BPS 评分 portfolio_linkage 普遍 0.3（通用市场）
- 只生成 1 条 judgement，不强行凑 3 条
- morning_base_case：「今日市场无重大事件，常规观察持仓波动即可。」

### 9.2 如果所有数据源都失败（极端日）

- source_health 三个全 failed
- evidence_pool 为空
- 触发**保守 brief**：
  - morning_base_case: "Data coverage limited today; review overnight moves manually before meeting."
  - 不输出 judgement
  - portfolio_map 仍正常展示（行情数据本地缓存）
- 埋点 `conservative_brief_triggered` 触发，月度监控自动统计

### 9.3 如果 LLM 偷偷写了 "Nvidia"

- 输出反向扫描命中 sensitive_entity_dictionary
- 自动重试一次
- 仍命中 → renderer 替换为 alias 或安全占位
- 用户看到的展示仍然是反映射后的"英伟达"，但来源是**本地反映射**而非 LLM 自主生成
- 这条 LLM 调用的 audit log 标记 `output_sanitization_triggered=true`

### 9.4 如果用户上传的 PDF 含 universe 外 ticker（例如 BABA）

- ticker_detection 标 `external_ticker`
- parse_report 显示 "External: BABA (not in watchlist) ⚠"
- 进入 Text LLM 前 BABA 也替换为无语义 `E_xxxx`
- `is_external=true` 仅本地可见，不进 prompt

---

---

## 附录：本样例使用的假设数据

- 时间：2026-04-25 周六，brief 生成于 07:55 HKT，用户阅读于 08:30 HKT
- 客户：单租户家办，audit_mode = demo
- LLM provider：Anthropic Claude（text）+ 无需 vision（用户未上传新 PDF）
- 本地 embedding：bge-small（默认）
- accuracy_validator 全部通过，无重试，无 fallback
- 保守 brief 未触发

> 注：本样例数据为评审用虚构案例，所有引用文字、quote_span 偏移、新闻来源细节均为示意，不代表真实公告内容或市场事件。

