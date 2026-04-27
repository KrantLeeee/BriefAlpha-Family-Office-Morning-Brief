## ADDED Requirements

### Requirement: 首屏布局

主页 SHALL 在首屏左右并列展示 portfolio_map（左）与 morning_base_case + ai_judgement_summary（右）；下方依次为 judgement_list、source_health；首屏 TTI ≤ 2 秒。

#### Scenario: 首屏 TTI

- **WHEN** 用户在 08:30 HKT 后访问主页
- **THEN** 首屏可交互时间 ≤ 2 秒（使用预生成缓存）

#### Scenario: 移动端折叠

- **WHEN** 视口宽度 < 768px
- **THEN** portfolio_map 与 base_case 上下堆叠，仍保持可读

### Requirement: morning_base_case 视觉规范

base_case_headline SHALL 按设计稿使用 Fraunces serif 30px、左侧 3px orange_600 竖线作为视觉焦点；ai_judgement_summary SHALL 使用 Inter 14px、ink_700、line-height 约 1.55。引用以 `[1][2]` 形式内嵌，点击跳转对应 evidence_drawer 并高亮。

#### Scenario: 引用点击

- **WHEN** 用户点击 `[1]`
- **THEN** drawer 打开并高亮 evidence ①

#### Scenario: degradation_note

- **WHEN** brief 含 degradation_note
- **THEN** 在 base_case 下方以 warning 色展示文案；无该字段时不渲染

### Requirement: portfolio_map treemap

portfolio_map SHALL 渲染 treemap：色块间距 4px、圆角 2px；第一行 symbol + weight%，第二行 ▲▼ + 涨跌%。涨跌方向 MUST 同时使用符号与颜色（不依赖单一颜色）。

#### Scenario: 涨跌符号 + 颜色

- **WHEN** 行情上涨
- **THEN** 同时渲染 ▲ 与上涨色，下跌则 ▼ 与下跌色

#### Scenario: 行情缺失

- **WHEN** 某 ticker 涨跌缺失
- **THEN** 第二行显示 `—`，色块仍保留

#### Scenario: CASH 补足

- **WHEN** 持仓 weight 合计 ≠ 100%
- **THEN** 自动补足 CASH 块，使总和 = 100%

### Requirement: judgement_list 行为

judgement_list SHALL 按 rank 升序渲染；整行点击触发 evidence_drawer；rank=1 行使用 orange_50 背景 + 橙色左竖线；level 标签 elevated 使用 orange_600，其他 ink_500。

#### Scenario: 整行热区

- **WHEN** 用户点击 conclusion 或 evidence_summary 任意位置
- **THEN** drawer 打开，进入对应 judgement

#### Scenario: 默认 top 3

- **WHEN** 当天 judgement > 3
- **THEN** 默认展开 top 3，展示"今日有 N 条值得关注，已展开 top 3"，其余通过 `[查看全部]` 展开

### Requirement: source_health 渲染

source_health SHALL 渲染 4 行 mono 表格（market / news / official / research）；ok 使用 ink_500，degraded 使用 warning，failed 使用 danger；degraded 时顶部 chip + base_case 脚注 + footer 三处同步显示。

#### Scenario: research 无上传

- **WHEN** active research_uploads = 0
- **THEN** research 行显示 `no uploads`，不计入 degraded

#### Scenario: 全 failed

- **WHEN** 三类源全部 failed
- **THEN** 顶部 chip 显示 `All sources degraded`，judgements 不渲染

### Requirement: Evidence Drawer

drawer SHALL 由 judgement 行或 base_case 的 `[n]` 触发；右侧滑入 200ms；desktop 宽度 560–640px、mobile 全屏；主页不加遮罩；可通过 ×、ESC、点击外部、返回按钮关闭。结构：judgement_anchor → reasoning_chain → evidence_list → local_qa；evidence 摘录使用 Fraunces serif 16px，按设计稿不强制 italic。drawer 打开 ≤ 300ms。

#### Scenario: 关闭与焦点

- **WHEN** 用户按 ESC
- **THEN** drawer 关闭且焦点返回触发元素

#### Scenario: 切换 judgement

- **WHEN** 在 drawer 内切换到另一 judgement
- **THEN** 内容平滑替换，不重新动画整个 drawer

### Requirement: 设计稿复刻约束

前端实现 SHALL 以 `docs/Designs/BriefAlpha.pen` 的中文 frames 为视觉 source of truth：`fFOSV`（主页）、`uOtTm`（drawer）、`I4Qnp`（上传流程）、`Nh2S4`（交互状态）。英文 frames 仅作双语参考。开发不得重新设计成通用 SaaS dashboard，必须保留设计稿的紧凑金融工作台密度、细分隔线、低圆角、Fraunces/Inter/JetBrains Mono 字体分工与橙色强调系统。

#### Scenario: 视觉回归

- **WHEN** 前端关键页面实现完成
- **THEN** 使用 Playwright 截图与 Pencil 导出的 `fFOSV` / `uOtTm` / `I4Qnp` / `Nh2S4` 做视觉回归检查，主要布局、字号层级、颜色、边框、间距和 focus ring 不得明显偏离设计稿

### Requirement: PDF Viewer 跳转

`Read full article ↗`：非 PDF SHALL 跳转新标签页；PDF SHALL 跳转内置 react-pdf viewer 并定位到对应 page + bbox 高亮。原 PDF 已删除时 MUST 提示 `Original document unavailable`。

#### Scenario: PDF page+bbox 高亮

- **WHEN** evidence.source_type=research 且对应 PDF 存在
- **THEN** viewer 打开第 N 页并以高亮框框出 quote_span 对应 bbox

### Requirement: Local QA 输入

每条 judgement / evidence 行 SHALL 提供最小追问入口；drawer 内提供增强 local_qa。judgement drawer 追问的默认上下文 SHALL 是当前 drawer 展示的全部 evidence，而非用户问题关键词检索结果；输入空 / > 500 字符 MUST 禁用发送；超时 20 秒。同 scope 下 SHALL 保留 3 轮上下文。回答渲染后被引用的 evidence 高亮 2 秒。

#### Scenario: 输入限制

- **WHEN** 输入 > 500 字符
- **THEN** 发送按钮禁用并提示

### Requirement: 上传面板

主页 header SHALL 提供 `Upload research` 按钮；点击弹出 drawer / modal；首次使用展示 third-party figure captioning consent；之后每次上传仍展示当前状态摘要与 `Change processing preference` 链接。

#### Scenario: 上传 consent 文案

- **WHEN** 上传面板首次打开
- **THEN** 展示 PRD §2.1 (3) 文案，consent 默认未勾选

### Requirement: 前端缓存与脱敏

持仓数据 MUST NOT 写入 localStorage / IndexedDB，仅内存保存；stale brief 缓存 SHALL 仅保留 judgements / ai_summary / evidence，不含 portfolio 结构；用户登出时 MUST 清除内存与 session 缓存；上传 PDF MUST NOT 在前端缓存，每次查看通过后端 secure URL 流式传输。

#### Scenario: localStorage 检查

- **WHEN** 检查浏览器存储
- **THEN** 不出现 portfolio 结构字段（ticker + weight 组合）

### Requirement: 可访问性

所有涨跌色 MUST 配 ▲▼ 符号；文本与背景对比度 ≥ 4.5:1；交互元素 focus ring = 2px orange_600 outline + 2px offset；日期时间 MUST 含日期（如 `Apr 21, 16:00 → Apr 22, 08:30 HKT`）。

#### Scenario: 对比度

- **WHEN** 设计 token 编译
- **THEN** 主要文本 / 背景对比度 ≥ 4.5:1

#### Scenario: focus ring

- **WHEN** 键盘 Tab 至按钮
- **THEN** 显示 2px orange_600 outline + 2px offset
