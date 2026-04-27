## Why

家族办公室合伙人每日晨会前要从微信截图、彭博推送、研报 PDF、雪球观点等分散信息源手动梳理市场动态。BriefAlpha MVP 需要在 90 秒内、08:30 HKT 前自动产出一份**可引用、可追溯、对客户持仓最小披露**的结构化晨报，并支持上传研报作为补充证据，让合伙人在 5 分钟内完成阅读与一次深度追问。

PRD 已经明确了功能边界、安全约束（最小必要披露 / k-anonymity / ticker aliasing / 字段白名单）、性能目标和验收标准；本次 change 把 PRD 翻译成可工程实施的 capability 划分、技术架构与建设顺序，作为 BriefAlpha 代码库从 0 → 1 的总体设计。

## What Changes

新增端到端 MVP 系统，覆盖 PRD 中所有 P0 与 P1 功能：

- **数据采集**：按 privacy-safe universe 拉取 yfinance / GDELT / Google News RSS / SEC EDGAR / HKEX 三类公开源；07:55 HKT freeze evidence_pool。
- **晨报生成 pipeline**：normalize → entity_linking → dedupe → portfolio_mapping → BPS scoring → conflict_resolve → evidence_selection → anonymization 九阶段。
- **LLM 安全编排层**：统一 audit wrapper；prompt 字段白名单；ticker aliasing + sensitive_entity_dictionary；输出反向敏感扫描；accuracy_validator（引用、quote_span、数字、极性、时间窗、敏感扫描）。
- **三阶段 LLM 生成**：stage_a base_case + summary、stage_b 1-5 条 judgement、stage_c playbook_events。
- **PDF 上传与解析**：pdfplumber 文本+表格抽取、pytesseract OCR fallback、vision LLM caption（用户授权）、本地 embedding chunking、merge 入 evidence_pool；支持 re-analyze、删除、partial_failure。
- **Local + Global Evidence QA**：scope=judgement / evidence (P0) 以当前 drawer / 单条 evidence 的全量可引用 evidence 作为上下文，不以 FTS 作为门槛；scope=global (P1) 基于 SQLite FTS5 / BM25 检索全部 evidence_pool；alias 反映射；validator 复用主管线。
- **前端首屏**：morning_base_case + ai_judgement_summary（右）、portfolio_map treemap（左）、judgement_list、source_health，并按 `docs/Designs/BriefAlpha.pen` 中文主屏高度复刻视觉密度与排版。
- **Evidence Drawer**：reasoning_chain + evidence_list + 内置 PDF viewer（page+bbox 高亮）+ local_qa。
- **安全审计基础设施**：audit log（request_hash / cited_evidence_ids / failure_state / audit_mode 标识）、alias_map 加密存储至 16:00 HKT、第三方调用边界控制、source_health 聚合、conservative brief 降级。
- **运维与质量基础设施**：cron 调度、redis 缓存、SQLite 持久层、golden set 回归脚手架、埋点事件。

P2 完整功能（完整 playbook UI、完整 watchlist_item、完整 macro_pulse、audit_transparency 完整页）作为后续 change；本次 MVP 为了满足 5 分钟阅读路径，仅实现与设计稿一致的 playbook preview、watchlist preview 与 macro_pulse collapsed entry，并在 pipeline 输出 playbook_events 数据结构以保留接口。

## Capabilities

### New Capabilities

- `data-ingestion`: 按 privacy-safe universe 从 market / news / official 三类公开数据源采集 raw_items，记录 source_health。
- `brief-pipeline`: 9 阶段处理 pipeline，把 raw_items + research_chunks 加工为可引用的 evidence_pool 与待生成 brief 的 selection。
- `portfolio-context`: 本地持仓 / watchlist / exposure_bucket / weight_band 管理、k-anonymity 校验、coarse_bucket_mode、cold_start 校验；privacy-safe universe 构造。
- `llm-orchestration`: 统一 LLM/embedding/vision 调用 wrapper，含 prompt 白名单组装、敏感扫描、reply 反向扫描、accuracy_validator、重试与降级、audit log。
- `data-anonymization`: ticker_aliasing、sensitive_entity_dictionary、alias_map 加密生命周期、字段白名单、敏感扫描规则集。
- `morning-brief-api`: `/api/brief/today`、`/api/judgement/{id}/drawer`、`/api/qa`、`/api/source-health` 等读取与追问端点；缓存与降级语义。
- `research-upload`: `/api/research/*` 上传、解析（extraction / OCR / captioning / chunking / dedupe / merge）、parse_report、re-analyze、删除、第三方处理 consent。
- `evidence-search`: 当日 evidence_pool + research_chunks 的 SQLite FTS5 / BM25 本地检索，scope 过滤、增量索引。
- `frontend-morning-brief`: 主页首屏（base_case + summary + portfolio_map + judgement_list + source_health + playbook/watchlist/macro preview）、Evidence Drawer、Local QA 输入、内置 PDF viewer、上传面板；视觉 source of truth 为 `docs/Designs/BriefAlpha.pen` 的中文 frames。
- `audit-and-observability`: audit log 写入 / 查询、demo↔compliance 模式切换、source_health 聚合、conservative_brief 触发监控、埋点事件采集。
- `scheduling-and-runtime`: cron（07:00 滚动 / 07:55 freeze / 08:30 交付）、queue（PDF 解析 / re-analyze）、redis 缓存键约定、定时清理任务。

### Modified Capabilities

无（首次建设，没有已存在的 spec）。

## Impact

- **新代码库**：后端 Python（FastAPI + APScheduler + SQLAlchemy + SQLite + Redis + pdfplumber + pytesseract + sentence-transformers）；前端 Next.js / React + TypeScript + TailwindCSS + react-pdf。
- **第三方服务依赖**：Anthropic / OpenAI（Text + Vision LLM，via 统一 wrapper），yfinance、GDELT、Google News RSS、SEC EDGAR RSS、HKEX RSS（无 key 公开源）；可选 stooq / Finnhub / Alpha Vantage 备源。
- **数据存储**：SQLite（evidence、research_chunks、FTS5 索引、audit log、portfolio、universe、alias_map metadata）；本地加密文件系统（PDF 原文件、alias_map ciphertext、原始 API response 7 天审计副本）；Redis（当日 brief、source_health、QA 上下文、解析队列）。
- **运维**：单机 demo 部署；cron / scheduler 守护进程；备份策略覆盖 SQLite 与 audit log；密钥（LLM key、alias_map encryption key）由本地 secrets 文件管理。
- **合规边界**：MVP 仅承诺 evidence-grounded + consistency-checked + 最小必要披露；不承诺完整金融合规系统；audit_mode=`demo` 默认，切换到 `compliance` 需独立部署评审。
- **后续 change**：P2 完整模块（完整 playbook UI / 完整 watchlist_item / 完整 macro_pulse / audit_transparency 完整页）、多租户隔离、生产级 security master 接入、合规审计模式落地、生产部署与监控告警。
