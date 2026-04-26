# BriefAlpha 可信数据闭环 & 9 项 UX 修复 — Design

**Date:** 2026-04-26
**Author:** KrantLee + Claude
**Status:** Design ready for implementation planning
**Context:** 项目作为家办面试题提交。用户当前体验中，fixture 数据冒充真实数据导致整体可信度崩塌；与此同时存在 8 项次级 UX 缺口（刷新缺失、链接 404、待复核含义不清、QA 一刀切回错、宏观脉搏不可展开、观察事件无依据、证据轨迹"查看全部"无反应、source health 假数据、watchlist 文案费解）。

## 0. 目标与非目标

### 目标
1. **可信数据闭环**：用户任何时候都能一眼判断现在看到的是 demo 还是 live 数据
2. **真实可用**：`live` 模式下 ingestion → brief → QA 全链路工作
3. **demo 友好**：未配置任何 key 也能跑起来，但所有"假"数据都被显式标记
4. **9 项问题全部修复或显式补充**

### 非目标
- 多用户登录态（单用户假设）
- macro_pulse 指标可配置 UI（留 P1）
- watchlist 编辑/导入（留 P1）
- review status 多人协作流转（resolve 留 P1）

## 1. 架构核心：Mode + 状态机

### 1.1 Mode 简化为二元

```
BRIEFALPHA_MODE = demo | live    # 默认 demo
```

不做 auto 检测——避免"我以为我配好了但仍是 demo"的灰色地带。手动切。

### 1.2 `live` fail-fast 条件

启动时检查（**不**满足任一条则启动失败、打印缺失项）：

- `BRIEFALPHA_MODE=live`
- 至少一个 **market** provider enabled（默认 yfinance，无需 key）
- 至少一个 **news** provider enabled（默认 GDELT 或 Google News RSS，无需 key）
- 至少一个 **official** provider enabled（默认 SEC EDGAR + HKEX，要求 SEC `user_agent` 合法）
- 启用了 keyed provider（Finnhub / Alpha Vantage 等）才校验对应 key 存在
- LLM provider 至少一个可用（key 设置且 reachable）

`demo` 模式跳过以上所有检查，直接启动。

### 1.3 顶层状态契约

```ts
Brief.system: {
  mode:              "demo" | "live"
  status:            "ready" | "generating" | "stale" | "error"
  generated_at:      string | null   // ISO8601 HKT
  last_refreshed_at: string | null   // ISO8601 HKT
  data_quality:      "fixture" | "live" | "partial" | "unavailable"
}
```

`stale: bool` 兼容保留一个 release，前端读 `system.status` 优先。

`data_quality` 是**统一信号**：Banner / QA / Refresh / Source Health 都读这个字段做判断，不再各自推断。

| data_quality | 含义 | 出现条件 |
|---|---|---|
| `fixture`   | 当前 brief 完全来自 fixture | mode=demo |
| `live`      | 当前 brief 完全来自真实管线 | mode=live, 所有源都成功 |
| `partial`   | 真实管线但部分源降级 | mode=live, source health 有 degraded |
| `unavailable` | 数据完全不可用，UI 应显示错误态 | mode=live, status=error |

## 2. 9 项问题修复对照

| # | 问题 | 修复 | 实现层 |
|---|---|---|---|
| 1 | 无刷新按钮 | TopBar `<RefreshButton>` + `POST /api/admin/data/refresh`：live → 触发 ingestion → brief 重生成 → 返回 job_id；demo → 旋转 fixture 时间戳，**且 UI 显式标"Demo refreshed HH:MM · 示例数据，非实时采集"** | api/web |
| 2 | "AMD · GOOGL · 1810.HK · 未持有 · 仅作市场参照" 不知所云 | 段标题改为 **"市场参照（非持仓）"**，加 `(?)` 提示气泡解释定义；与 portfolio 视觉清晰区分 | web |
| 3 | Evidence 链接 404 | EvidenceCard 加 `link_kind` 枚举：`external` / `internal_demo` / `internal_research` / `unavailable`。前端按 kind 路由：`external` 新窗口；`internal_demo` 弹窗"示例 evidence · 来自 fixture"；`internal_research` 路由到 `/research/<id>`（内部 PDF 查看器）；`unavailable` 置灰 + tooltip"原文链接不可用" | api/web |
| 4 | "⚠ 待复核" 含义不明 | `requires_review:bool` 升级为 `review: {reason, note, status} \| null`。reason ∈ `source_conflict / portfolio_uncertain / threshold_breach / data_gap`。chip 可点击弹窗显示理由 + note + **"我已审阅"** 按钮（status: `open` → `reviewed`）。**后端持久化**：`POST /api/review/{judgement_id}`，写入 SQLite `review_overrides` 表（不走 localStorage，遵守项目约定） | api/web |
| 5 | "当前无法生成可信回答" 一刀切 | `failure_reason` 分流：`llm_unconfigured` / `evidence_insufficient` / `out_of_scope` / `empty_question` / `demo_mode_no_match` / `demo_mode_prebaked`。**demo 模式额外搭关键词回答表**（`hi` / `总结今日` / `为什么 NVDA` 等十余条）。预制回答时返回 `failure_reason: "demo_mode_prebaked"` + `validation_passed: true`，UI 显式标 **"示例回答"** badge——不伪装成 LLM | api/web |
| 6 | Macro pulse 不能展开 | `<MacroPulseExpanded>` 折叠/展开切换，8 指标读 `brief.macro_pulse[]`（schema 新增 `{name, value, delta, threshold, status}`）。指标编辑 UI 留 P1 | api/web |
| 7 | 观察事件无来源 | `playbook_events[i].related_evidence_ids: string[]`；事件展开渲染对应 evidence 卡片复用现有 `<EvidenceCard>` | api/web |
| 8 | "查看全部 20 条"无反应 | `<EvidenceTrailDrawer>`：渲染 `deep_read.evidence_trail` 完整列表，时间倒排，`source_tier` 筛选；live 从 SQLite 拉，demo 从 fixture | api/web |
| 9 | "研报 1 个上传" 假数据 | demo 模式：每行加 `(示例)` 后缀；live 模式：source health 真接 ingestion runner 状态 + DB 真实上传计数 | api |

## 3. 数据契约改动汇总

```ts
// types.ts
Brief.system                       : SystemMeta            // NEW
Brief.macro_pulse                  : MacroPulseItem[]      // NEW
Judgement.review                   : ReviewMeta | null     // NEW，替代 requires_review
Judgement.requires_review          : boolean               // 兼容保留一个 release
EvidenceCard.link_kind             : LinkKind              // NEW
EvidenceCard.source_link?          : string                // 改为可选
PlaybookEvent.related_evidence_ids : string[]              // NEW
SourceHealthRow.is_demo            : boolean               // NEW（demo 模式下 true）
```

### 3.1 兼容映射规则
- `requires_review=true` 且 `review` 字段缺失 → 后端 artifact builder 自动派生 `review = {reason: "data_gap", status: "open", note: ""}`
- `review` 存在 → 前端**只读** `review`，忽略 `requires_review`
- 删除 `requires_review` 留下个 release（在最终归档前完成）

### 3.2 后端新增 SQLite 表

```python
class ReviewOverride(Base):
    __tablename__ = "review_overrides"
    id: int                 # PK autoincr
    brief_id: str           # FK 概念
    judgement_id: str
    status: str             # "open" | "reviewed"
    reviewed_at: datetime | None
    note: str               # 空字符串允许
    UNIQUE(brief_id, judgement_id)
```

前端调 `POST /api/review/{judgement_id}` 时 brief_id 从当前 brief 取。简单 upsert。

## 4. 实施顺序（每步独立可上线）

```
Step 1: 数据契约层
  - apps/api Pydantic models 升级
  - apps/web TS types 同步
  - fixtures.py + fixtures.ts 升级到新 schema（同时让 demo 数据自洽）
  - 不改任何业务逻辑，纯结构

Step 2: Mode + Banner + Refresh + README
  - briefalpha_api/config.py: BRIEFALPHA_MODE 解析 + fail-fast 校验
  - brief.py: live cache miss 返回 status:"generating"，不再回退 fixture
  - api.ts: 删除静默 fallback，错误显式抛出
  - 新增 <ModeBanner> 永久横幅
  - 新增 <RefreshButton> + POST /api/admin/data/refresh
  - README 加"切换模式"章节（与代码同步落盘）

Step 3: Evidence link_kind + 行为分发
  - artifact.py: _build_evidence_card 根据 source_link scheme 分类
  - <EvidenceCard>: 按 link_kind 路由到 external / demo modal / research viewer / 置灰
  - 修问题 3

Step 4: QA 降级 + demo 关键词表
  - qa/service.py: failure_reason 枚举化
  - qa/demo_responses.py: 关键词 → 预制回答表
  - <LocalQaInput>: 按 failure_reason 显示对应人话 + "示例回答" badge
  - 修问题 5

Step 5: Review 结构化 + 弹窗 + 持久化
  - DB migration: review_overrides 表
  - POST /api/review/{judgement_id} 端点
  - artifact.py: 兼容映射规则
  - <JudgementDrawer>: review chip 可点击 → <ReviewModal> → "我已审阅"
  - 修问题 4

Step 6: Macro pulse 展开 + Playbook evidence 绑定 + Evidence trail drawer
  - <MacroPulseExpanded>
  - <TodayPlaybook>: 事件展开渲染 related evidence
  - <EvidenceTrailDrawer>: 全量列表 + 筛选
  - 修问题 6/7/8

Step 7: Source health 真假分流
  - audit/source_health_aggregator.py: live 模式真接 ingestion 状态 + 真实研报上传计数
  - demo 模式：每行加 is_demo=true 标
  - <SourceHealth>: 渲染 (示例) 后缀
  - 修问题 9

Step 8: Watchlist 文案 + 提示气泡
  - fixtures: 段标题 → "市场参照（非持仓）"
  - <PortfolioTreemap>: 加 (?) 提示气泡
  - 修问题 2
```

每步做完跑 `pnpm build` + `pnpm test` + 手动开页面验一遍 demo + live 两态，再推下一步。

## 5. 测试策略

### 5.1 单测
- `test_mode_resolution`: BRIEFALPHA_MODE 解析 + fail-fast 各分支
- `test_link_kind_classification`: source_link scheme → link_kind 映射
- `test_qa_failure_reason_branches`: 6 种 failure_reason 分流
- `test_review_status_transition`: open → reviewed 单向
- `test_requires_review_compat_mapping`: 旧字段派生新字段

### 5.2 集成测试
- `test_demo_brief_response_shape`: demo 模式响应字段稳定
- `test_live_cache_miss_returns_generating`: live 模式 cache miss 返回 status:"generating"，**不**回退 fixture
- `test_review_persistence_roundtrip`: POST → GET 一致

### 5.3 E2E（Playwright，已有依赖）
一个 happy path 脚本覆盖：
1. demo 模式启动 → ModeBanner 可见
2. 点 RefreshButton → "Demo refreshed HH:MM" 出现
3. 点"⚠ 待复核" chip → 弹窗 → "我已审阅" → chip 状态变更
4. 点 evidence trail "查看全部" → drawer 打开
5. QA 输入 "hi" → 显示"示例回答"badge

## 6. 文档与交付

- `README.md` 新增"切换模式"章节（Step 2 同步完成）
- `docs/PRD/` 现有文档不动（保留对方面试官评估视角）
- `docs/admin_runbook.md` 加"刷新数据 / 强制重生成 brief"操作说明
- 最终 PR 描述附前后截图：demo 模式（带 banner）+ live 模式（无 banner）

## 7. 风险与回滚

- **风险 1**：live 模式 fail-fast 太严，本地启不起来 → 在 README 提供"最小 live 配置 checklist"，列出可选 vs 必选
- **风险 2**：Step 1 schema 升级破坏现有页面 → 兼容映射规则在后端落地后，前端可逐组件切换；任何一步出错可仅回退该组件
- **风险 3**：demo 关键词表覆盖不全，面试官输入冷门问题仍卡 → fallback 文案明确写"当前为 demo 模式，未配置 LLM provider，仅支持基于示例 brief 的预设问题"

## 8. 验收清单（面试提交前）

- [ ] `BRIEFALPHA_MODE=demo` clone 即跑，所有页面有内容、所有"假"数据带显式标记
- [ ] `BRIEFALPHA_MODE=live` 配齐 key 后端到端工作（ingestion → brief → QA）
- [ ] 9 个原始问题逐一回归通过
- [ ] README 切换模式章节清晰，对方 reviewer 5 分钟内能跑起来
- [ ] 测试套件全绿
- [ ] 截图 + commit 信息能讲清楚"为什么这么改"
