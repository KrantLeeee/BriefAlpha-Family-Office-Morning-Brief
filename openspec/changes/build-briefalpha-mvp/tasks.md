## 1. 仓库与基础设施初始化

- [x] 1.1 初始化 monorepo（pnpm workspace 或简单目录约定）：`apps/api/`、`apps/web/`、`packages/prompts/`、`packages/config/`、`data/`、`tests/`
- [x] 1.2 后端 Python 3.11 + uv/poetry，安装 FastAPI、APScheduler、SQLAlchemy 2.x、aiosqlite、redis-py、httpx、pdfplumber、pytesseract、sentence-transformers、anthropic、openai、import-linter、pytest、vcrpy
- [x] 1.3 前端 Next.js 14 + TS + Tailwind + react-pdf + Zustand + Playwright；设置 ESLint、Prettier
- [x] 1.4 添加 `.gitignore`：`data/`、`data/.secrets/`、`research_pdfs/`、`*.enc`、`.env*`
- [x] 1.5 SQLite schema 与 alembic 迁移：`evidence`、`research_chunks`、`evidence_fts`（FTS5 虚拟表）、`portfolio`、`watchlist`、`universes`、`alias_map_metadata`、`audit_log`、`research_jobs`、`source_health_history`、`consent_log`
- [x] 1.6 Redis 部署文档（本地 Docker 或 brew）；命名空间约定写入 README
- [x] 1.7 import-linter 规则：禁止除 `apps/api/llm/wrapper.py` 外任何模块直接 import provider SDK
- [x] 1.8 secrets 启动检查：`data/.secrets/alias_key`（生成脚本）、`llm_api_keys.json`、`admin_token`，权限 0600 校验

## 2. portfolio-context

- [x] 2.1 实现 `portfolio.repo`：portfolio / watchlist 读取
- [x] 2.2 配置文件 `config/ticker_sector_overrides.yml`（≥ 30 行覆盖 demo 持仓 / watchlist / 核心港美股）
- [x] 2.3 sector / industry 映射器：yfinance 字段 + 手工 override 合并
- [x] 2.4 `portfolio.bucket.build_buckets()`：基于 sector + factor 生成 exposure_bucket，输出 weight_band
- [x] 2.5 `portfolio.universe.build_universe()`：补足 decoy / 行业代表 / 宽基 ETF；启用 coarse_bucket_mode 条件（ticker<15）；decoy ≤ holdings × 4 校验
- [x] 2.6 k-anonymity 校验：bucket ticker 数 < 3 合并到 other_equity；冷启动校验失败禁止 ticker 级查询
- [x] 2.7 `PrivacySafeUniverse` pydantic 类型（仅 ticker + asset_class 字段）
- [x] 2.8 单元测试：覆盖 PRD §6.1 universe 验收（30 ticker / 10 ticker / bucket 不满足稀释）

## 3. data-anonymization

- [x] 3.1 `anonymization.alias`：每个 brief 随机生成 ticker → `E_xxxx` 映射；外部 ticker 同规则；返回 `AliasContext`
- [x] 3.2 `sensitive_entity_dictionary` 构造器：每日 06:50 HKT 刷新（yfinance 名称字段 + `company_alias_zh.yml`）；港股变体（`.HK` / 去前导零 / HKEX 前缀）
- [x] 3.3 配置文件 `config/company_alias_zh.yml`（≥ 30-50 个核心标的中文别名）
- [x] 3.4 `anonymization.replace.replace_in_text(text, ctx)`：覆盖 ticker 字面值 + 公司全名 / 简称 / 中文名 + 多种交易所格式
- [x] 3.5 `AliasedEvidence` pydantic 模型（白名单字段：evidence_id / title_aliased / excerpt_aliased / quote_span_aliased / source_tier / asset_class / published_at）；多余字段在 model_validator 阶段剥除
- [x] 3.6 replacement segment list 同步生成（`field / orig_start / orig_end / alias_start / alias_end / original_text / alias`，多次出现 / 多别名归一各为独立 segment）；`aliased_to_original(span, segments)` 反向函数：基于 segment 区间映射，跨 segment / 落 alias 内部 / 无记录 MUST 返回失败；cumulative offset 仅作优化，MUST 与 segment-based 算法逐字符对账
- [x] 3.7 alias_map 加密读写：AES-GCM；存储 `data/alias_maps/{brief_id}.enc`；密钥来自 `data/.secrets/alias_key`
- [x] 3.8 安全反映射函数 `reverse_alias(text, ctx, cited_evidence_ids)`：仅对在 cited evidence 上下文中出现的 alias 反映射；其他 alias 标记 `unsafe_generated_alias`，由 renderer 占位（`[redacted]`）或删除整段；MUST NOT 全文 string-replace
- [x] 3.9 单元测试：公司名漏出、`Tencent` / `腾讯` 替换为同 alias、跨交易所格式归一、白名单字段过滤、LLM 自创 ticker 被输出扫描替换后 reverse 不还原、无 quote_span 锚定的 alias 不还原

## 4. data-ingestion

- [x] 4.1 `ingestion.base`：adapter 抽象（输入 PrivacySafeUniverse、输出标准化 raw_items）；`config/data_sources.yml` 启用开关与备源顺序
- [x] 4.2 market adapter：yfinance 主源；stooq / Finnhub / Alpha Vantage 备源（按 key 启用）；港股 `.HK` 保持
- [x] 4.3 news adapter：GDELT 主源；Google News RSS fallback；按市场宽关键词 + universe ticker 构造查询
- [x] 4.4 official adapter：SEC EDGAR RSS + HKEX RSS；按 universe 内 ticker 拉 filings
- [x] 4.4a official symbol mapping：维护 `data/symbol_maps/sec_company_tickers.json`（SEC `company_tickers.json` 镜像，每周刷新）+ `hkex_stock_codes.json`（HKEX 公开列表，每周刷新）；ticker → CIK / HKEX 代码解析；缺失映射跳过该 ticker 的 EDGAR / HKEX 拉取并写 admin diagnostics warning，不阻塞其他 ticker
- [x] 4.4b SEC User-Agent：`config/data_sources.yml.sec.user_agent` 必填（含联系邮箱）；启动期校验未配置 → 进程启动失败；EDGAR 限速 ≤ 10 req/s
- [x] 4.5 exponential backoff 重试 ≤ 3 次；429 / 5xx 触发降级；调用计数写入 redis
- [x] 4.6 原始 response 压缩存储 7 天；按 source_url + fetched_at 可恢复
- [x] 4.7 时区与 ticker 标准化：UTC 存储 / `Asia/Hong_Kong` 展示；盘前盘后标记；港股 symbol 格式
- [x] 4.8 单元 + integration 测试（vcrpy 录制）：覆盖 §6.1 ingestion 验收（三类源、单源失败、universe 稀释、bucket 不满足）

## 5. brief-pipeline 九阶段

- [x] 5.1 `pipeline.normalize`：字段映射 / 时区 / detected_tickers 抽取
- [x] 5.2 `pipeline.entity_linking`：NER + ticker 字典匹配
- [x] 5.3 `pipeline.dedupe`：content_hash + 本地 embedding 相似度（≥0.90 自动 / 0.80–0.90 candidate）；主源选择（tier > 原始域 > published_at）；写入 `supplementary_sources`
- [x] 5.4 `pipeline.base_scoring`：source_reliability × recency_weight × novelty_weight
- [x] 5.5 `pipeline.portfolio_mapping`：本地映射 evidence → exposure_bucket（不调 LLM）
- [x] 5.6 `pipeline.conflict_resolve`：高可信数字差异 / 方向冲突 / 官方与新闻不一致；标记 conflict=true / requires_review=true（**必须在 final_scoring 之前执行**）
- [x] 5.7 `pipeline.final_scoring`（BPS）：base × portfolio_linkage × event_materiality × market_confirmation；market_confirmation 读取 conflict 标记降权；输出完整 score_breakdown
- [x] 5.8 `pipeline.evidence_selection`：输出 `selected_evidence_for_llm`（top_k=20 按 final_impact_score 降序）+ `evidence_pool_full`（全集，同一 evidence 仅以 `selected_for_llm: bool` 区分，不双写）
- [x] 5.9 `pipeline.anonymization`：批量调用 `data-anonymization` 生成 AliasedEvidence
- [x] 5.10 `pipeline.no_direct_portfolio_link_fallback`：bucket 全部不满足 k=3 或冷启动校验失败时 portfolio_linkage 统一 = 0.3，judgements 标 `no_direct_portfolio_link=true`，**不进入** conservative brief
- [x] 5.11 单元测试：覆盖 §6.1 pipeline 验收（top_k 截断、score_breakdown、dedupe tier 优先、conflict 在 final_scoring 前、bucket 失败走 no_direct_portfolio_link 而非保守 brief）

## 6. evidence-search

- [x] 6.1 SQLite FTS5 虚拟表 schema；evidence 入池时同步索引；删除 chunk 同步移除
- [x] 6.2 `search.search(scope, brief_id, query, judgement_id?, evidence_id?)`：scope 过滤 → BM25 检索
- [x] 6.3 无结果 → `insufficient_evidence`，不调用 LLM
- [x] 6.4 字段范围约束：仅含 title / excerpt / detected_tickers / chunk_type / source_tier
- [x] 6.5 单元测试：scope=judgement / evidence / global 边界、删除同步

## 7. llm-orchestration wrapper

- [x] 7.1 `LlmRequest` / `LlmResponse` pydantic 模型（白名单字段）
- [x] 7.2 `llm.wrapper.call_text_llm()` / `call_vision_llm()` / `call_embedding()`：唯一 LLM 入口
- [x] 7.3 输入端敏感扫描：alias_map 真实 ticker 字面值、`数字+%`、关键词、JSON schema 白名单
- [x] 7.4 输出端反向敏感扫描：sensitive_entity_dictionary 匹配 → 重试 1 次 → 用 alias / 占位替换
- [x] 7.5 重试策略：主 brief MAX_RETRY=3 / QA=1；vision 限额 → caption_unavailable
- [x] 7.6 第三方 embedding 默认禁用开关；启用时强制先做 ticker_aliasing
- [x] 7.7 vision 调用：剥除 user_id / session_id / account_id / portfolio_id；独立 API key
- [x] 7.8 audit pre/post hook 集成（与第 11 节 audit 模块对接）
- [x] 7.9 conservative_fallback：触发保守 brief 文案
- [x] 7.10 单元测试：覆盖 §6.4 安全验收（NVDA / 18% / sector_bucket / weight_band 阻断）

## 8. accuracy_validator

- [x] 8.1 `validator.citations`：cited_evidence_ids 存在性 + ai_judgement_summary 引用 ≥ 2 条
- [x] 8.2 `validator.quote_span`：调用 anonymization 模块的 segment-based 转换函数，禁止自实现近似算法；转换失败 → 视为不可定位 → 触发重试
- [x] 8.3 `validator.numbers`：数字 / 百分比 / bp / 金额 / 倍数在 quote_span ±120 字符内一致 + 单位一致
- [x] 8.4 `validator.polarity`：beat / miss / raise / cut / 上调 / 下调 / 超预期 / 不及预期方向词字典
- [x] 8.5 `validator.time_window`：PRD §2.6 表 → `TimeWindowRule` enum；用 zoneinfo（Asia/Hong_Kong / America/New_York）；NYSE 交易日历库
- [x] 8.6 `validator.sensitive_output`：复用反向敏感扫描
- [x] 8.7 拒绝 / 重试 / 降级路径与 wrapper 联动
- [x] 8.8 单元测试：覆盖 §6.1 validator 验收（quote_span 不可定位 / 数字 / 时间窗 / 连续 3 次失败）

## 9. prompt 模板（packages/prompts）

- [x] 9.1 `prompts/stage_a.json`：morning_base_case + ai_judgement_summary 模板（含 forbidden 列表）
- [x] 9.2 `prompts/stage_b.json`：1-5 条 judgement，含 reasoning_chain 四层
- [x] 9.3 `prompts/stage_c.json`：playbook_events
- [x] 9.4 `prompts/qa_local.json` / `prompts/qa_global.json`
- [x] 9.5 每个模板携带 `template_version` 字段（写入 audit log）
- [x] 9.6 prompt builder 严格组装（不允许字符串拼接 evidence 字段）

## 10. brief 三阶段生成调度

- [x] 10.1 `pipeline.run_brief(brief_date)`：组装 stage_a → stage_b → stage_c；输入约束硬限
- [x] 10.2 字数与引用数量后处理（base_case ≤ 50 字 / summary ≤ 200 字 / judgement ≤ 60 字 / evidence_summary ≤ 120 字符）
- [x] 10.3 conservative brief 触发器（**仅以下三条**）：`evidence_pool_full` 为空 / Text LLM 全 provider 失败 / accuracy_validator 同一 brief 连续失败 3 次。**k=3 全部不满足 / 冷启动校验失败 MUST 走 5.10 `no_direct_portfolio_link_fallback`，不进入 conservative brief**
- [x] 10.4 brief 写入 redis `brief:{date}`（TTL 至次日 freeze）
- [x] 10.5 单元 + integration 测试：覆盖 §6.1 三阶段 + 保守 brief 验收 + bucket 失败必须走 no_direct_portfolio_link 的回归测试

## 11. audit-and-observability

- [x] 11.1 `audit_log` 写入：request_hash / scope / cited_evidence_ids / response_hash / accuracy_validation_passed / call_type / provider / model / template_version / latency_ms / failure_state / audit_mode
- [x] 11.2 demo 模式不存原始 prompt；compliance 模式预留加密 redacted prompt 字段（接口预留，不在 MVP 启用）
- [x] 11.3 `audit_mode` 切换接口（admin only）+ 二次确认 + reason 记录；旧记录保留模式标识
- [x] 11.4 source_health 5 分钟聚合任务；redis `source_health:latest`
- [x] 11.5 conservative_brief 月触发率统计 + diagnostics 告警（>10% 或连续 3 个交易日）
- [x] 11.6 admin diagnostics 视图：source_health 历史、ticker 改名告警、第三方调用边界违规、audit_mode 切换历史
- [x] 11.7 PDF 元数据与原文件保留期清理任务（默认 7 天）
- [x] 11.8 单元测试：覆盖 §6.4 安全验收 audit 字段、模式切换不可追认

## 12. scheduling-and-runtime

- [x] 12.1 APScheduler jobstore=SQLite；进程重启可恢复
- [x] 12.2 cron：07:00 滚动采集、07:55 freeze + run_brief、16:00 alias_map 清理、每日 PDF/audit 清理、每日 06:50 sensitive_entity_dictionary 刷新、每 5 分钟 source_health 聚合、每周 official symbol map 刷新（SEC + HKEX）
- [x] 12.3 后台 worker：`research:queue` 与 `reanalyze:queue`；re-analyze 与主 pipeline 互斥
- [x] 12.4 配置开关读写：`llm_provider`、`data_sources.*.enabled`、`degradation_threshold`、`exposure_bucket_rules`、`k_anonymity_threshold`、`coarse_bucket_mode`、`auto_expand_universe`、`research_upload_limit`、`audit_mode`、`brief_timezone`、`brief_delivery_time`
- [x] 12.5 失败隔离：单源 / 单 PDF 失败不影响主 brief；alias_map 清理失败 admin alert

## 13. morning-brief-api（FastAPI 路由）

- [x] 13.1 `GET /api/brief/today`：缓存优先 / stale 降级 / 90s 超时上一日
- [x] 13.2 `GET /api/judgement/{id}/drawer`：reasoning_chain + evidences + suggested_questions；同会话缓存
- [x] 13.3 `POST /api/qa`：(a) 用户问题端 alias 替换 → (b) evidence-search 在 evidence_pool_full 中检索 → (c) 检索结果**必经 anonymization 转 AliasedEvidence**（FTS 行禁止直接拼 prompt，wrapper 输入端会拦截）→ (d) wrapper → validator → 安全反映射；scope=judgement/evidence (P0) / global (P1)；alias_map 过期 → `brief_expired`；连续 3 次失败 → 友好失败文案
- [x] 13.4 `GET /api/source-health`
- [x] 13.5 `GET /api/portfolio`（仅授权用户）
- [x] 13.6 一致错误结构 `{error: {code, message, retry_after?}}`
- [x] 13.7 单元 + integration 测试：覆盖 §6.1 / §6.2 API 验收

## 14. research-upload

- [x] 14.1 `POST /api/research/upload`：multipart；mime + size 校验；活跃数量 ≤ 5 校验
- [x] 14.2 加密落盘 `research_pdfs/{user_id}/{file_id}.pdf`；权限隔离（403 跨用户）
- [x] 14.3 consent 持久化（`consent_log`）：user_id / timestamp / policy_version / file_id / consent_state
- [x] 14.4 解析 worker：extraction（pdfplumber 文本 + 表格 + bbox）→ OCR fallback（pytesseract）→ vision captioning（仅 consent）→ chunking（200-500 字符 + heading + chunk_type）→ ticker_detection（NER + dict）→ FTS dedupe（embedding > 0.9 丢弃）→ merge to pool（source_tier=research, reliability=0.5）
- [x] 14.5 partial_failure 收集：每 stage 失败记录 stage / 原因 / 页码；parse_report 展示 partial 明细
- [x] 14.6 caption 入池前必经 anonymization
- [x] 14.7 `GET /api/research/{file_id}` 状态查询；`GET /api/research/{file_id}/parse_report`
- [x] 14.8 `POST /api/research/{file_id}/reanalyze`：仅重跑 pipeline stage_4 起；与主 pipeline 互斥
- [x] 14.9 `DELETE /api/research/{file_id}` / chunk 级删除：立即从 evidence_pool + FTS 移除；不自动重跑
- [x] 14.10 `auto_expand_universe` 默认 false：external ticker 入池但 warning，不扩展 ingestion
- [x] 14.11 单元 + integration 测试：覆盖 §6.2 PDF 验收（OCR / vision 超时 / 5 份限制 / external ticker / partial_failure / re-analyze 排队 / consent）

## 15. frontend-morning-brief

- [x] 15.1 Next.js App Router 主页：SSR 注入 `/api/brief/today`；首屏左右布局（portfolio_map 左 / base_case+summary 右）；移动端上下堆叠
- [x] 15.2 `BaseCaseHeadline` 组件：Fraunces serif 30px + 3px orange_600 竖线，按 `fFOSV` 复刻
- [x] 15.3 `AiJudgementSummary` 组件：Inter 14px / ink_700 / line-height 约 1.55；`[n]` 引用点击 → 打开 drawer 并高亮
- [x] 15.4 `PortfolioTreemap`：色块间距 4px / 圆角 2px；symbol+weight%（行 1）/ ▲▼+涨跌%（行 2）；`<TrendIcon>` 同时输出符号 + 颜色 + aria-label；CASH 自动补足
- [x] 15.5 `JudgementList`：rank 升序；rank=1 orange_50 背景 + 橙色左竖线；level=elevated→orange_600；整行点击触发 drawer；默认 top 3 + `[查看全部]`
- [x] 15.6 `SourceHealthTable`：mono 4 行；ok=ink_500 / degraded=warning / failed=danger；research 行 `{N} uploads active` 或 `no uploads`
- [x] 15.7 顶部 chip + base_case 脚注 + footer 三处 degraded 同步
- [x] 15.8 `EvidenceDrawer`：右侧 fixed Sheet 200ms；desktop 560-640px / mobile 全屏；不加遮罩；ESC / 外部点击 / 返回关闭；焦点回退；切换 judgement 平滑替换；< 300ms 打开
- [x] 15.9 `ReasoningChain`、`EvidenceCard`（Fraunces serif 16px 摘录，不强制 italic）、`SupplementarySourcesList`
- [x] 15.10 `ResearchPdfViewer`（react-pdf）：page+bbox 高亮；原 PDF 已删除提示
- [x] 15.11 `LocalQaInput`：行内最小入口 + drawer 增强体验；空 / >500 字符 禁用；20s 超时；3 轮上下文；回答渲染后引用 evidence 高亮 2 秒
- [x] 15.12 `ResearchUploadDrawer`：consent 文案 + Change processing preference 链接；状态轮询；parse_report 视图
- [x] 15.13 Zustand store：portfolio_snapshot / drawer state / qa context；不写 localStorage
- [x] 15.14 stale brief 渲染逻辑：portfolio_snapshot 缺失时 chip + footer 同步
- [x] 15.15 可访问性：focus ring 2px orange_600 + 2px offset；对比度 token 编译期校验；日期含日期前缀
- [x] 15.16 Playwright e2e：覆盖 §6.1 / §6.2 / §6.5 关键路径
- [x] 15.17 视觉复刻验收：导出 Pencil frames `fFOSV` / `uOtTm` / `I4Qnp` / `Nh2S4`，用 Playwright 截图对照检查布局密度、字号层级、颜色、边框、间距、focus ring，确认实现未偏离设计稿

## 16. 埋点

- [x] 16.1 前端事件采集 SDK（本地，不出网）；事件 schema 与 PRD §5.3 一一对应
- [x] 16.2 后端写入 `audit_log` 与本地埋点表；admin diagnostics 可查询
- [x] 16.3 单元测试：drawer_close 携带 duration_ms / close_method、qa_response_render 携带 cited_count + validation_passed

## 17. golden set 与质量回归

- [x] 17.1 设计 ≥ 50 条 golden cases，覆盖 PRD §5.1.3 所列 9 个场景类别（earnings / 政策日 / 平静日 / 突发 / macro / HKEX/SEC / research PDF / conflict / 单源 vs 多源）
- [x] 17.2 golden runner：每次 prompt / scoring / validator 修改 CI 自动执行
- [x] 17.3 输出指标报告：citation 可定位率、数字一致率、极性一致率、时间窗一致率、输出敏感扫描通过率、`unsafe_generated_alias` 计数、conservative_brief 触发率、`no_direct_portfolio_link` 触发率
- [x] 17.4 conservative_brief 触发率门禁：> 10% 阻断合并
- [x] 17.5 端到端 walkthrough（评审版）：示例 portfolio + universe → 采集 → pipeline → brief → QA → 安全验证报告

## 18. 部署与运维

- [x] 18.1 本地启动脚本：`make dev`（后端 uvicorn + scheduler + 前端 next dev + redis）
- [x] 18.2 secrets 生成脚本：`scripts/init_secrets.sh` 创建 alias_key / admin_token
- [x] 18.3 SQLite 备份脚本（每日）+ audit_log 加密备份
- [x] 18.4 systemd / launchd unit 模板（按部署目标）
- [x] 18.5 README：架构总览 / 启动步骤 / 安全边界声明（demo 模式）/ 配置项说明 / 升级 audit_mode 流程
- [x] 18.6 admin 操作手册：universe 维护、company_alias_zh 维护、audit_mode 切换、conservative_brief 排查路径

## 19. 验收闭环

- [x] 19.1 跑通 PRD §6.1 全部 P0 验收用例（自动化 + 人工 walkthrough）
- [x] 19.2 跑通 PRD §6.2 全部 P1 验收用例
- [x] 19.3 PRD §6.3 性能目标实测达标（TTI / 90s / 60s / 30s / drawer 300ms / QA p95）
- [x] 19.4 PRD §6.4 安全验收（NVDA / 18% / weight_band / vision 不带身份 / 第三方 embedding 默认禁用 / 跨用户 PDF 403）
- [x] 19.5 PRD §6.5 可访问性 + §6.6 异常场景验收
- [x] 19.6 准备评审材料：技术设计 walkthrough + 安全审计样例 + golden 报告
- [x] Frontend visual parity: export screenshots from '/Users/krantlee/Documents/Study/Vibe Coding Experiments/Family-Office-Morning-Brief 2 [BriefAlpha]/docs/Designs/BriefAlpha.pen' frames and compare with Playwright screenshots at 1440px desktop. Major layout, typography, spacing, color, and density must match before marking frontend complete.

