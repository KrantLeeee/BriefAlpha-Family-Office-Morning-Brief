## Context

BriefAlpha 是从 0 → 1 的家族办公室晨报 demo。PRD 已规定：
- **业务**：3 类公开数据源 + 用户上传研报，08:30 HKT 前交付一份 ≤ 5 分钟可读完的结构化晨报；judgement 引用 ≥ 2 evidence 且原文可定位。
- **安全**：第三方 LLM / embedding / vision 调用 request body 不含真实 ticker / 公司名 / weight / 客户身份；所有 evidence 字段经字段白名单 + ticker_aliasing；alias_map 当日 16:00 HKT 过期；k-anonymity（k=3，coarse_bucket_mode 触发条件 ticker<15）。
- **性能**：晨报 ≤ 90s、TTI ≤ 2s、drawer ≤ 300ms、QA p95 ≤ 15s、PDF parse ≤ 60s、re-analyze ≤ 30s。
- **demo 边界**：不承诺完整金融合规系统；不直接声称 GICS；audit_mode=`demo` 默认。

主要相关方：合伙人（5 分钟读者）、投资分析师（深度追溯 + 上传研报）、admin（diagnostics / audit_mode 切换）。MVP 单租户单机部署。

## Goals / Non-Goals

**Goals:**
- 一套可工程实施的模块划分，支撑 PRD 全部 P0+P1 验收用例。
- 安全设计深嵌入架构：所有 LLM 调用必经统一 wrapper；evidence 字段白名单在数据流入口（anonymization）和入口前（wrapper）双层守门；alias_map 加密生命周期与 audit log 解耦。
- 数据流单向、可回放：raw → normalized evidence → scored → selected → aliased → LLM → validated → reverse-mapped → cached → frontend。每一步可观测、可重放。
- 部署足够简单：单机 Python 后端 + Next.js 前端 + SQLite + Redis；不引入 Kubernetes / 消息队列等复杂依赖。

**Non-Goals:**
- P2 完整模块（完整 playbook UI / 完整 watchlist_item / 完整 macro_pulse / 完整 audit_transparency 页）由后续 change 实现；本次 MVP 仅实现与设计稿一致的 playbook preview、watchlist preview 与 macro_pulse collapsed entry，并产出对应数据结构。
- 多租户隔离、生产级 security master、合规 audit_mode 落地。
- 真实交易决策 / 投顾建议 / 收益预测：BPS 仅是排序分。

## Decisions

### 1. 技术栈选型

**后端：Python 3.11 + FastAPI + APScheduler + SQLAlchemy 2.x + SQLite (FTS5) + Redis + httpx + pdfplumber + pytesseract + sentence-transformers (bge-small)**

理由：
- Python 拥有最完整的 PDF / OCR / NER 工具链；pdfplumber 是 PRD 明确要求的库。
- FastAPI 原生 async 适合高并发 LLM / IO 调用，pydantic v2 用于字段白名单校验天然适配。
- APScheduler 单进程内即可承载 cron + 后台队列，比 Celery + Broker 简单一个数量级；MVP 单机足够。
- SQLite + FTS5 完整支持当日 evidence 全文检索，零运维；多租户阶段再迁 Postgres。
- Redis 仅用作 brief 缓存与轻量队列；不做主存储。

**替代方案考虑**：
- Node.js 后端（pdf-lib / tesseract.js）：PDF 解析与本地 NER 生态弱于 Python，放弃。
- Postgres：MVP 单机过重；FTS5 已足够。
- Celery + RabbitMQ：增量复杂度高，APScheduler 已能满足 PDF 队列与 cron。

**前端：Next.js 14 (App Router) + TypeScript + TailwindCSS + react-pdf + Zustand**

理由：
- App Router + RSC 让首屏在服务端拼装好缓存数据，TTI ≤ 2s 容易达成。
- react-pdf 直接支持 page + bbox 高亮（drawer 跳转 PDF 的核心需求）。
- Zustand 内存状态足够，不写 localStorage 天然契合"持仓不入持久化缓存"的安全约束。

### 2. 模块/进程划分

```
briefalpha/
├── apps/
│   ├── api/                  # FastAPI 主进程（路由 + LLM wrapper + scheduler）
│   │   ├── routers/          # /brief /qa /research /portfolio /source-health /admin
│   │   ├── pipeline/         # brief-pipeline 9 阶段
│   │   ├── ingestion/        # data-ingestion adapters（market/news/official）
│   │   ├── llm/              # llm-orchestration wrapper + prompt builders
│   │   ├── anonymization/    # data-anonymization 模块
│   │   ├── search/           # evidence-search FTS 封装
│   │   ├── research/         # research-upload pipeline
│   │   ├── portfolio/        # portfolio-context（universe 构造、k-anonymity）
│   │   ├── audit/            # audit-and-observability 写入 + diagnostics
│   │   └── scheduler/        # APScheduler jobs
│   └── web/                  # Next.js 前端
├── packages/
│   ├── prompts/              # JSON 模板 + template_version
│   └── config/               # company_alias_zh.yml / ticker_sector_overrides.yml / data_sources.yml
├── data/                     # SQLite + 加密文件（gitignored）
└── tests/
    ├── unit/
    ├── integration/
    └── golden/               # ≥ 50 条 golden cases
```

理由：
- 单仓库；后端/前端进程分离但共享 prompt 模板与 schema 类型生成（pydantic → ts via openapi-codegen）。
- 模块边界严格对应 capability：每个模块的 public API 即对应 spec 的 requirement，便于追溯。

### 3. 数据流与单向流水线

```
[ingestion adapters] → raw_items
                           ↓
                       [pipeline]
  normalize → entity_linking → dedupe (FTS+embedding)
    → base_scoring → portfolio_mapping (本地)
    → conflict_resolve (mark only)        ← 必须在 final_scoring 前
    → final_scoring (BPS, 读取 conflict 标记降权 market_confirmation)
    → evidence_selection → anonymization
                           ↓                          ↓
                evidence_pool_full         selected_evidence_for_llm
                (全集，含 selected 与未选中)   (≤ top_k=20，作为 LLM 输入)
                           |                          ↓
                  +-----research_chunks       [llm wrapper]
                  |       (PDF 上传)               ↓
                  ↓                           prompt_builder (AliasedEvidence only)
              evidence-search FTS5          → input sensitive scan
                  ↑                          → provider call
                  |                          → output sensitive scan
                  |  (QA: retrieved evidence  → accuracy_validator
                  |   必经 anonymization 才入 prompt)
                  └──────[QA path]──────→    → safe reverse alias
                                                 (仅 cited 上下文内 alias 才还原)
                                              → audit log
                                                   ↓
                                              redis brief:{date}
                                                   ↓
                                              [api routers]
                                                   ↓
                                              [next.js frontend]
```

关键命名约定（避免之前的语义重叠）：

- `evidence_pool_full`：当日所有去重 + 评分后的 evidence 全集，用于 evidence-search、QA、drawer 扩展查询、audit 追溯。同一份 evidence 实体不双写，仅以 `selected_for_llm: bool` 区分。
- `selected_evidence_for_llm`：top_k=20 条进入 stage_a / stage_b LLM 的子集。
- `aliased_evidence`：上述子集（或 QA 检索子集）经 anonymization 后的对外形态，对应 pydantic 类型 `AliasedEvidence`。

关键不变量：
- LLM 边界唯一入口：`apps/api/llm/wrapper.py`；router / pipeline / qa 都不直接 import provider SDK。CI lint 用 import-linter 强制。
- anonymization 是从内部数据模型到 LLM payload 的"穿越层"，对每一个跨越者做白名单 + 敏感扫描双重校验。
- QA 路径同样适用：evidence-search 返回的是 `evidence_pool_full` 中的 raw evidence，QA handler MUST 再调一次 anonymization 生成 `AliasedEvidence` 才能拼 prompt；FTS 行直接进 LLM 是禁止路径，wrapper 输入端白名单会拦截。
- conflict_resolve 必须在 final_scoring **之前**完成，使 conflict 标记可作为 BPS 的 market_confirmation 降权信号。

### 4. 安全架构（PRD 安全核心的工程落地）

#### 4.1 字段白名单：双层守门

- **anonymization 阶段（数据侧）**：对 evidence 应用 pydantic schema `AliasedEvidence`，字段固定为 `evidence_id / title_aliased / excerpt_aliased / quote_span_aliased / source_tier / asset_class / published_at`；多余字段在 `model_validator` 阶段就被剥除。
- **wrapper 阶段（请求侧）**：所有 LLM request body 必须通过 `LlmRequest` schema 校验；额外做 JSON schema 白名单 + 正则扫描（真实 ticker / 公司名 / 数字+% / 关键词）。

为什么双层：anonymization 出错（如新增字段忘了过滤）由 wrapper 兜底；wrapper 出错由 anonymization 提前剥除。两层独立维护，互为防线。

#### 4.2 sensitive_entity_dictionary

- 每日 06:50 HKT 在 ingestion 启动前刷新：拉取 universe 内 ticker 的 yfinance `symbol/longName/shortName/quoteType/exchange`；与 `company_alias_zh.yml` 合并后生成 dict。
- ticker → alias 映射在每个 brief 生成时随机化（按 brief_id），避免跨日 alias 复用反推；公司名 / 简称 / 中文名共享同一 alias。
- diff 用于 admin diagnostics（ticker 改名、缺中文别名告警）。

#### 4.3 alias_map 加密与生命周期

- 存储路径：`data/alias_maps/{brief_id}.enc`；对称加密（AES-GCM），密钥来自 `data/.secrets/alias_key`（gitignored，启动时校验存在）。
- 内存中由 `AliasContext` 上下文对象承载，request 级生命周期；audit log 与 redis MUST NOT 持久化明文。
- scheduler 在 16:00 HKT 删除当日 ciphertext；QA 在过期后返回 `brief_expired`。

#### 4.4 LLM wrapper 实现要点

```python
async def call_text_llm(payload: LlmRequest, *, scope, audit_ctx):
    LlmRequest.model_validate(payload)         # schema whitelist
    sensitive_scan_input(payload, audit_ctx)   # regex + dict scan
    audit_pre = audit.write_pre(payload, scope, audit_ctx)
    try:
        for attempt in range(MAX_RETRY):
            resp = await provider.invoke(payload, audit_ctx)
            sensitive_scan_output(resp, audit_ctx)
            ok = await accuracy_validator.run(resp, audit_ctx)
            if ok: break
        else:
            return conservative_fallback(scope)
    finally:
        audit.write_post(audit_pre, resp_meta=...)
    return reverse_alias(resp, audit_ctx)
```

- 配置项：MAX_RETRY 主 brief=3 / QA=1。
- `audit_ctx` 携带 `audit_mode`（demo / compliance），但 demo 模式只写 hash + meta。

#### 4.5 universe 构造与 k-anonymity

模块 `portfolio.universe.build_universe(portfolio)`：
1. 加载 portfolio + watchlist
2. 按 `config/ticker_sector_overrides.yml` + yfinance sector 映射到 bucket
3. 若 |portfolio.tickers| < 15 → 启用 coarse_bucket_mode，bucket 数 ≤ 4
4. 每个 bucket 补足 decoy（来自宽基/sector ETF 池），直到 >= max(k, 5)
5. 校验：decoy ≤ holdings × 4；否则该 bucket 仅保留宽基 ETF
6. 输出 `PrivacySafeUniverse(tickers, asset_classes_only)`，写入 SQLite `universes` 表

ingestion adapters 只接受 `PrivacySafeUniverse` 类型，不接受裸 portfolio。

### 5. accuracy_validator 与安全反映射实现策略

- **双坐标 quote_span**：anonymization 在做 ticker / 公司名替换时同步生成 **replacement segment list**（每条 segment 含 `field, orig_start, orig_end, alias_start, alias_end, original_text, alias`，同一 alias 多次出现 / 中英文 / 简称归一各为独立 segment）。validator 调用 `aliased_to_original(span, segments)` 做区间映射；跨 segment、落在 alias 内部、无记录 MUST 返回失败而非近似偏移。简单 cumulative offset 仅可作为命中后的加速，且需在单测中与 segment-based 算法逐字符对账（约束已上升到 spec，见 `data-anonymization` "replacement segment list"）。alias_offset_map 仅服务 quote_span 这种"已知锚定到原文位置"的反查，**不能**单独驱动正文 string-replace 反映射。
- **安全反映射（safe reverse alias）**：renderer 仅对"出现于 validated cited evidence 上下文"的 alias 做反映射；其他 alias（LLM 自主生成、输出端反向敏感扫描产生、引用了非 cited 范围 evidence 的）一律标记 `unsafe_generated_alias`，保持占位（`[redacted]`）或删除整段，绝不直接还原。
- **数字 / 极性 / 时间窗一致性**：用规则 + 字典实现；时间窗规则映射成 `TimeWindowRule` enum，统一以 `Asia/Hong_Kong` 计算，DST 由 zoneinfo (IANA) 处理。
- **golden set 回归**：`tests/golden/` 内 ≥ 50 条 case，每次 prompt / scoring / validator 修改 CI 自动跑，输出 citation 可定位率 / 数字一致率 / 时间窗一致率 / sensitive_scan_blocked / `unsafe_generated_alias_count` / conservative_brief_triggered 六项指标。

### 6. PDF 上传 pipeline

- 上传走 multipart 直传后端 → 加密落盘 `research_pdfs/{user_id}/{file_id}.pdf` → 入 redis `research:queue`。
- worker（APScheduler 后台 job）按 file_id 顺序处理；每 stage 失败写入 `research_jobs.failures`；前端轮询 `/api/research/{file_id}` 获取状态。
- caption 调用 vision LLM 必经同一 wrapper（`call_vision_llm`），request body 不含 user_id / session_id；caption 返回后通过 anonymization 入池。
- chunk 入池策略：source_tier=research / source_reliability=0.5；FTS 索引同步写入。

### 7. 前端架构

- **Design source of truth**：前端视觉 MUST 以 `docs/Designs/BriefAlpha.pen` 为准，中文 frames 是 canonical implementation reference：`fFOSV`（Screen / Desktop Main v5 中文版）、`uOtTm`（Judgement Drawer 中文版）、`I4Qnp`（Upload Research Flow）、`Nh2S4`（Interaction States）。英文 frames 仅作双语参考。实现时不得重新设计成通用 SaaS dashboard。
- **Visual tokens**：背景 `#FAFAF7`、主文本 `#0F0F0E`、次级文本 `#5C5C58`、分隔线 `#E8E7E1`、强调橙 `#C2410C`、warning wash `#FDF4EE`；圆角以 2-4px 为主；Fraunces 用于 headline / quote，Inter 用于 prose，JetBrains Mono 用于 metadata。
- **Canonical typography**：base_case headline 使用 Fraunces 30px + 3px orange vertical rule；AI summary 使用 Inter 14px / line-height 约 1.55；evidence quote 使用 Fraunces 16px，不强制 italic。
- **App Router 路由**：`/`（主页 SSR + RSC，从 `/api/brief/today` SSR 注入数据）；`/research/upload`（drawer 内嵌组件，但路由可独立挂载）；`/admin/diagnostics`（仅 admin）。
- **State**：Zustand store 内存保存 portfolio_snapshot + 当前 drawer 状态；不写 localStorage。
- **Drawer**：右侧 fixed `Sheet` 组件，desktop 560-640px、mobile 全屏；不使用全屏遮罩。点击外部 / ESC 关闭统一交给 `useDrawerController`。
- **PDF Viewer**：react-pdf + 自定义 highlight overlay（按 quote_span_original 的 page+bbox 渲染）。
- **可访问性**：所有涨跌色配 `<TrendIcon direction="up|down">`（同时输出 ▲/▼ + aria-label）；Tailwind 主题 token 在编译期检查对比度 ≥ 4.5:1。

### 8. 缓存与降级

- `redis:brief:{date}` TTL 至次日 freeze；写入由 pipeline 负责，读取由 router 负责。
- `redis:source_health:latest` 由 audit 模块每 5 分钟聚合写入。
- `redis:qa:context:{brief_id}:{scope}` 保留最近 3 轮，TTL 跟随 brief。
- 90s 超时降级：router 在等不到当日 brief 时返回上一日 brief（不含 portfolio_snapshot）+ `stale=true`；前端按 stale 渲染 chip。

降级层级（从轻到重，必须区分清楚）：

1. **single source degraded**：单类源 fallback 备源或标记 degraded，brief 仍正常生成；前端顶部 chip + base_case 脚注 + footer 三处同步。
2. **no_direct_portfolio_link 降级**：所有 bucket 即使合并到 other_equity 仍不满足 k=3，或冷启动校验未通过 → portfolio_linkage 因子统一取 0.3，brief 正常生成市场 / 宏观判断，judgements 标 `no_direct_portfolio_link=true`，前端顶部提示 `Portfolio linkage unavailable today; market-level analysis only.`
3. **conservative brief**：仅在 `evidence_pool_full` 为空 / Text LLM 全 provider 失败 / accuracy_validator 同一 brief 连续失败 3 次时触发；固定文案，judgements=[]，portfolio_map 与 macro_pulse 仍展示。

bucket / k-anonymity 失败 **MUST NOT** 触发 conservative brief；这两条降级路径完全独立。

### 9. 配置与密钥

- `config/data_sources.yml`：每源启用开关 + base_url + 备源顺序；MUST 含 SEC EDGAR 用 `user_agent` 字段（合规 User-Agent 含联系邮箱）。
- `config/company_alias_zh.yml`：≥ 30-50 行核心标的中文别名表。
- `config/ticker_sector_overrides.yml`：≥ 30 行 sector / industry 手工覆盖。
- `data/symbol_maps/`：`sec_company_tickers.json`（SEC `company_tickers.json` 镜像，每周刷新）+ `hkex_stock_codes.json`（HKEX 公开列表，每周刷新）；用于 ticker → CIK / HKEX 代码映射，缺失映射写 admin diagnostics 而非整体 degraded。
- `data/.secrets/`：alias_key、llm_api_keys.json、本地 admin token。gitignored；启动时强校验存在与权限 `0600`；同时校验 `data_sources.yml.sec.user_agent` 已配置。

### 10. 测试策略

- **unit**：anonymization 字段过滤、敏感扫描正则、validator 各项规则、universe 构造 / k-anonymity、BPS 计算、time-window 规则、prompt builder 白名单。
- **integration**：用 vcrpy 录制公开 API 响应；pipeline 端到端跑出 brief；wrapper 用 mock provider（注意：不 mock validator 与 anonymization）。
- **golden**：50 条人工标注 brief，覆盖 earnings / 政策 / 平静日 / 突发涨跌 / 宏观 / HKEX/SEC / research PDF / conflict / 单源高可信 / 多源印证。CI 跑回归输出 6 项 metrics 报告。
- **frontend**：Playwright 跑首屏 TTI / drawer 时延 / 键盘可达性；同时导出关键页面截图，与 Pencil frames `fFOSV` / `uOtTm` / `I4Qnp` / `Nh2S4` 做人工视觉回归，确认布局密度、字号、颜色、边框和交互状态未偏离设计稿。

## Risks / Trade-offs

- **[公司名漏出风险]** sensitive_entity_dictionary 依赖 yfinance 名称字段质量；冷门标的 longName 缺失会导致公司名漏到 LLM。
  → Mitigation：`company_alias_zh.yml` 强制覆盖 demo universe；admin diagnostics 显示缺别名告警；输出端反向扫描双重兜底；CI 把"alias 字典缺失"列为部署门禁。

- **[alias 反推]** 即使 alias 无语义，单 brief 内 alias + asset_class + 时间 + quote 仍可能被相关人员推断回原 ticker。
  → Mitigation：alias 按 brief_id 随机化；prompt 不含 sector/region/bucket/weight_band；alias_map 当日 16:00 HKT 销毁；PRD §1.1 已显式承认"假名化不等于匿名化"，由 k-anonymity + 字段白名单 + 输出扫描共同约束风险。

- **[小客户 universe 稀释不足]** 持仓 < 15 时即使开启 coarse_bucket_mode，decoy 噪声仍可能污染 portfolio_linkage。
  → Mitigation：decoy ≤ holdings × 4 上限；超过则降级为宽基/sector ETF 查询；冷启动校验失败禁止 ticker 级 API 查询。

- **[validator 过严导致保守 brief 频发]** PRD 要求月触发率 ≤ 10%。
  → Mitigation：golden set 回归 + 触发率周/月监控；validator 失败原因分类记录用于调参；保守 brief 触发埋点用于排查。

- **[第三方 API 不稳定]** GDELT / Google News RSS 偶发限流或慢。
  → Mitigation：每源独立 worker；exponential backoff；降级到备源；source_health degraded 顶部 chip + footer 三处同步显示。

- **[PDF 解析覆盖率]** 复杂排版 / 扫描质量差导致 OCR 失败。
  → Mitigation：partial_failure 设计已允许成功 chunk 继续入池；parse_report 透明展示缺失，让用户自决是否替换上传文件版本。

- **[单机部署风险]** SQLite 写并发受限；APScheduler 单进程崩溃丢任务。
  → Mitigation：MVP 单用户 demo 写并发可控；APScheduler 配 jobstore=SQLite，进程重启可恢复未完成任务；生产化时再迁移到独立 worker / Postgres。

- **[demo↔compliance 切换治理]** 旧 demo 日志缺 redacted prompt / alias_map snapshot 不能补做合规留痕。
  → Mitigation：UI 与导出报告强制标识 audit_mode；切换需二次确认 + reason 记录；admin diagnostics 显示模式切换历史，避免误判。

## Migration Plan

无历史系统，无需迁移。部署顺序：
1. 在干净环境初始化 SQLite schema、redis、密钥；先验证 ingestion 三类源能拉到数据。
2. 跑 golden set 离线验证 pipeline + LLM wrapper（mock provider）。
3. 接入真实 LLM provider，用 demo portfolio 跑端到端；admin diagnostics 看通。
4. 部署 cron + 16:00 alias_map 清理任务；首日盯盘观察 source_health 与 conservative_brief 触发率。

回滚策略：每次 LLM prompt / scoring / validator 改动随 `template_version` 自增；audit log 携带版本，可回滚到上一版本配置；数据库迁移走 alembic，所有 schema 变更可回退。

## Open Questions

- LLM provider 默认值（anthropic vs openai）？两者均接，但 demo 中默认哪个？建议默认 `anthropic`（Claude 4.x 在中文 + 引用合规上经验更好），openai 作为 fallback。
- 本地 embedding 模型选 `bge-small-zh-v1.5` 还是 `paraphrase-multilingual-MiniLM`？建议 `bge-small-zh-v1.5`（中文新闻覆盖好）。
- admin 鉴权方式：MVP 用本地 token 还是简易账户？建议本地 admin token（写在 `data/.secrets/`），生产再接 SSO。
- 部署目标环境：本地 Mac / 内网 Linux？影响 systemd vs launchd 服务安装脚本，由用户决定。
