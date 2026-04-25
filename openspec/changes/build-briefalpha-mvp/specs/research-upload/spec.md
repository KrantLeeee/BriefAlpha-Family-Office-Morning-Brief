## ADDED Requirements

### Requirement: PDF 上传端点

后端 SHALL 暴露 `POST /api/research/upload`（multipart）接受单文件 ≤ 10MB 的 PDF；前端先做 mime 与大小校验。MUST 仅接受 application/pdf，且单用户活跃文件 ≤ `research_upload_limit`（默认 5）。

#### Scenario: 超出活跃数量限制

- **WHEN** 用户已有 5 份活跃上传，尝试再上传
- **THEN** 返回 409 + `please_delete_existing_first`，前端提示

#### Scenario: 非 PDF 拒绝

- **WHEN** 上传 .docx / .png
- **THEN** 后端返回 415 / Unsupported Media Type

### Requirement: 上传后状态机

每个 file_id SHALL 经历 `uploaded → extracting → ocr_processing → captioning → chunking → ready` 或在任一阶段 `failed`；状态可通过 `GET /api/research/{file_id}` 查询。

#### Scenario: 状态可查询

- **WHEN** 客户端轮询状态
- **THEN** 返回当前 stage 与上一次错误（若有）

### Requirement: 第三方 figure captioning consent

上传面板 SHALL 默认关闭 `Allow third-party figure captioning`；用户勾选后才允许调用 vision LLM。系统 MUST 为每次上传单独保存 consent snapshot（含 user_id、timestamp、policy_version、file_id、consent_state）。consent 可撤回；撤回 MUST NOT 影响已生成 caption 的审计记录，但后续 re-analyze 不再调用 vision LLM。

#### Scenario: 未 consent 跳过 vision

- **WHEN** 用户未勾选 consent 即上传
- **THEN** 解析跳过 captioning 阶段，对应图表 chunk 标记 `caption_unavailable_by_policy`，parse_report 显示对应文案

#### Scenario: 撤回 consent

- **WHEN** 用户撤回 consent
- **THEN** 已生成的 caption 仍保留，但下次 re-analyze 不再发起 vision 调用

### Requirement: 解析 pipeline

后端解析 SHALL 按以下顺序执行：(a) pdfplumber 文本 + 表格 + 坐标抽取；(b) 检测纯图像页 → pytesseract OCR fallback；(c) vision LLM 图表 captioning（仅在 consent 下）；(d) chunking（200-500 字符，按 heading 切分，保留 page+bbox，chunk_type∈{text,table,figure_caption}，每 chunk 独立本地 embedding）；(e) NER + 字典 ticker_detection；(f) 与 evidence_pool 本地 embedding 相似度 > 0.9 dedupe；(g) merge to pool（source_tier=research、source_reliability=0.5）。任一 stage 支持 partial_failure：成功 chunk 继续入池，失败 chunk 记录 stage / 原因 / 页码 / 可重试状态。

#### Scenario: 扫描版 OCR

- **WHEN** PDF 含 3 页纯图像
- **THEN** parse_report 显示 `Pages via OCR: 3`，OCR 失败的页记录、不阻塞其他页

#### Scenario: vision API 超时

- **WHEN** 单图表 vision 调用超时
- **THEN** 该 chunk 标记 caption_unavailable，其他 chunk 继续解析

#### Scenario: 部分失败仍入池

- **WHEN** chunking / ticker_detection / embedding 任一阶段对部分 chunk 失败
- **THEN** 成功 chunk 进入 evidence_pool，失败 chunk 写入 parse_report 的 partial_failure 明细

#### Scenario: 重复 chunk 丢弃

- **WHEN** 与已有 evidence 相似度 > 0.9
- **THEN** chunk 丢弃且 parse_report 显示 `{N} duplicate chunks skipped`

### Requirement: parse_report 信任可视化

每个 file 解析完成后系统 SHALL 提供 parse_report：含 pages_processed、pages_via_ocr、text_chunks、tables_extracted、figures_captioned、figures_caption_failed_pages、tickers_in_universe、tickers_external（warning）、low_confidence_chunks（含 page+ chunk_id）、actions（re-analyze / delete）。

#### Scenario: external ticker 警告

- **WHEN** PDF 中识别 `BABA`（universe 外）
- **THEN** parse_report 的 `External` 区域列出 BABA 并标 warning，进入 LLM 前仍被 alias

### Requirement: re-analyze

用户点击 `Re-analyze with uploads` SHALL 仅重跑 brief-pipeline 的 stage_4 至 stage_9 + LLM generation；MUST NOT 重新采集 market / news / official；新 brief 覆盖当前 redis 缓存；目标耗时 ≤ 30 秒。

#### Scenario: re-analyze 排队

- **WHEN** 主 pipeline 正在运行时触发 re-analyze
- **THEN** 排队等待当前 pipeline 完成后再触发，前端显示 queued 状态

### Requirement: 删除 chunk / 文件

用户 SHALL 能删除单个 chunk 或整份上传；删除立即从 evidence_pool 移除对应 chunk，但 MUST NOT 自动重跑 brief。

#### Scenario: 立即从 pool 移除

- **WHEN** 用户删除单 chunk
- **THEN** evidence_pool 中对应 chunk 立即不可被新 brief / QA 引用

### Requirement: 文件隔离与权限

PDF 原文件 SHALL 加密本地存储于 `research_pdfs/{user_id}/{file_id}.pdf`，默认保留 7 天；用户 A 上传 MUST 仅对用户 A 可见；后端按 user_id 做权限隔离。

#### Scenario: 跨用户访问拒绝

- **WHEN** 用户 B 请求用户 A 的 file_id
- **THEN** 后端返回 403

### Requirement: caption 入池前 aliasing

vision 返回的 caption 文本 MUST 在进入 evidence_pool 之前完成 ticker_aliasing，避免后续主 LLM 调用读到真实 ticker / 公司名。

#### Scenario: caption 含真实 ticker

- **WHEN** caption 文本含 `NVDA`
- **THEN** 写入 research_chunks 表的 caption 仍保留原文（仅本地可见），但 LLM 输入端 caption 字段已被 alias 替换

### Requirement: universe 自动扩展开关

`auto_expand_universe` SHALL 默认关闭；关闭时 PDF 中 universe 外 ticker 仍入池但 parse_report warning，且第三方行情 / 新闻 API MUST NOT 因此扩展查询。

#### Scenario: 默认不扩展

- **WHEN** 配置默认未开启
- **THEN** 新出现的 universe 外 ticker 不触发后续 ingestion 查询变更
