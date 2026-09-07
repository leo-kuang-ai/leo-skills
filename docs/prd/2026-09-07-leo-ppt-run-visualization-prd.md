# PRD：Leo PPT 生成任务可视化控制台（Run Console）

- 版本：v1.0（PRD 基线，进入 5 轮审查）
- 日期：2026-09-07
- 作者：需求总负责人（本会话）＋ 产品调研（本地能力盘点 / 业界实践两路并行调研）
- 状态：待审（R1-R5）

---

## 1. 背景与问题

`leo-ppt config ui` 已是渠道管理控制台。但用户在 agent 驱动 PPT 生成期间（大纲→逐页母版→图片→渲染→交付，全程数分钟到数十分钟）**完全失明**：进展在 agent 会话的文本流里，预览散落在 `<run>/image-deck/origin_image/*.png`，过程与链路数据（events.ndjson / run.log / backend_stats）只有工程师能读。用户反复问"现在到哪了/哪页失败了/成什么样了"。

本地盘点证实数据链完整：`run.json`（阶段/状态/页进度）、`image-deck/slide_jobs.json`（每页状态机）、`events.ndjson`（append-only 里程碑事件）、`logs/run.log`、`reports/timing.json`、`observability/backend_stats.jsonl`（渠道×页×尝试×token）、页 PNG（record 即落盘）、`final/deck.pptx + validation-summary.json`。无守护进程，页面级刷新靠文件替换——轮询即可。

## 2. 产品目标与非目标

**目标**：把"生成 PPT"变成**看得见的过程**——进展、预览、过程、链路、流程五类信息在同一个本地控制台可视，用户在生成期间与结束后都能一眼获得答案：到哪一步了、每页什么状态、长什么样、谁在什么时候做了什么、最终交付在哪。

**非目标（v1 明确不做）**：
- **不做控制面**：不从页面驱动/重试/取消/清理 run——顶层 agent 拥有运行编排权（SKILL.md 架构红线），控制台是纯观察面；
- 不做账号/多用户/远程访问（仅 127.0.0.1）；
- 不做 PPT 编辑器（预览只读）；
- 不做历史 run 的跨机器聚合（只读本机 LEO_PPT_HOME）。

**隐私口径**：读侧仅本机文件 → 本机浏览器渲染，无遥测、无任何外发；页面路径默认显示 `~` 缩写或相对形式，复制按钮复制完整绝对路径（可用性不受损，截图外发场景降泄漏）。

## 3. 用户与场景

- A1 生成中用户：发起生成后切到控制台盯着看，等待期想知道"还剩几页、卡没卡、哪页失败了"；
- A2 验收用户：生成完成后回来核对"最终长什么样、六门质量闸过没过、交付文件在哪"；
- A3 排障用户（开发者）：失败后要看"哪一步、哪个渠道、第几次尝试、什么事件序列"。

场景故事（S1 生成中）：用户在第 3 分钟打开页面 → 看到流程条停在"逐页生成"、页网格 12 格中 7 绿 1 红 4 灰 → 点红格 → 时间线自动定位到该页失败事件（渠道 zhipu 第 2 次尝试超时）→ 点已完成页看大图预览 → 安心继续等。
场景故事（S2 验收）：完成后进入任务详情 → 交付卡显示 deck.pptx 与六门状态 → 网格全绿 → 逐页翻预览 → 从交付卡复制文件路径。

## 4. 功能需求（FR）

**入口与信息架构**
- FR1 单控制台双 Tab：「渠道管理」（现有）＋「生成任务」（新增）；新增 CLI 入口 `leo-ppt ui` 为规范入口，`config ui` 保持兼容（同一服务）。
- FR2 任务列表：扫描 `${LEO_PPT_HOME}/projects/*/runs/*/`，按更新时间倒序列出：run 短码（run_id 前 4 位，悬停显示全码；run_id 全局唯一作定位键）、项目名、路线（generate/direct-editable/upgrade-*）、状态徽标（created/in_progress/completed/failed/cancelled）、当前阶段、页进度（completed/total，含 failed 计数）、更新时间；进行中 run 徽标呼吸态；空态给"如何发起一次生成"的指引文案；详情视图以 URL 定位（`#run=<run_id>`，刷新/分享可直达），提供返回列表导航，浏览器标题随视图更新。

**详情视图（点击任务进入）**
- FR3 流程（Flow）：按路线渲染步骤条（generate：准备→逐页生成→交付；editable/upgrade 各自的 checked-in 步骤序列），已完成步骤打勾+耗时、当前步骤高亮转圈+已耗时、未到步骤置灰；失败态整条标红并停在失败步骤；cancelled 停在当前步骤、整条置灰、当前步骤显示已耗时。**不显示百分比**（业界共识：总时长不可预知，百分比虚假），用"阶段+已耗时+页进度"表达进展。run.json/events 最新 mtime 超过 5 分钟未更新且未到终态时，显示中性提示"数据 N 分钟未更新，进程可能已退出"（读侧陈旧检测，不做存活断言）。
- FR4 进展（Progress）——页网格：每页一格（Airflow Grid 模式）。状态×数据源映射（技术方案 R2 源码核验后）：`recorded/pending` 直接来自 slide_jobs/page_jobs（image 路线仅此二态落盘）；**editable 路线 `active` 直接读 page_jobs**；image 路线 `failed/timeout` 从 `timing.json` pages 与 `logs/run.log` 失败行推断（该路线无页级事件），推断不出回落二态。格子显示页码，hover tooltip 显示状态与该页最近摘要（渠道/尝试次数以可得数据为准）；未完成页渲染**骨架占位**（统一灰色占位块+页码，数据侧无母版布局信息，不做版式级骨架），完成后替换为缩略图（渐进填充）。
- FR5 预览（Preview）：页格点击按状态分流——recorded 页开 lightbox 大图（`origin_image/slide_NN.png`，左右键翻页，对话语义与焦点管理见 FR13）；failed/pending 页跳转时间线并定位过滤该页事件。editable/upgrade 路线的逐页大图预览 v1 不承诺（worker 产物为 pptx/contact-sheet，散落 worker 目录）——该类页展示状态与验证结果卡片；交付卡显示 `final/deck.pptx`（存在时）与质量闸清单：成功读 `validation-summary.json` 六门；失败摘要优先 `failure-report.json`（存在时），否则回落 run.json 失败阶段＋失败事件摘要（generate 路线页级失败无 failure-report，R2 核验）；路径显示缩写、复制全量（隐私口径）。
- FR6 过程（Timeline）：`events.ndjson` 渲染为结构化事件时间线（时间+动作图标+对象+结果+耗时），最新在上；**失败/重试事件自动展开并红色高亮**，其余默认折叠为一行摘要；从 failed/pending 页格进入时定位过滤该页事件（深链模式）。
- FR7 链路（Trace）：聚合 `observability/backend_stats.jsonl` 为小表：渠道×页型×尝试次数×tokens 合计；附 run 总耗时（timing.json summary）。
- FR8 实时性：进行中 run 详情页 3s 轮询、列表页 15s；页面不可见时（document.hidden）暂停轮询，恢复可见（visibilitychange）时立即拉取一次；检测到 run 迁移到终态时更新 `document.title`（"✔ 生成完成 · <项目>" / "✗ 生成失败 · <项目>"）；手动刷新按钮常在。数据变化时页网格/流程条平滑更新，不整页闪烁。

**信任与安全**
- FR9 只读红线：任务页不提供任何写操作；预览端点**只接受 run_id + 页码**（如 `/api/runs/{id}/pages/{n}.png`），服务端自行拼出 `origin_image/slide_NN.png`——客户端永不传路径；文件访问前 `Path.resolve()` 并断言仍在 `${LEO_PPT_HOME}/projects/<该 run>/` 之下（同时覆盖目录穿越与符号链接逃逸）；Content-Type 与扩展白名单一一对应；沿用 Host 校验/no-store；新增读接口保持 localhost 开放（无 CORS 头即被同源策略阻断），可选加固项：读接口校验 HttpOnly cookie token。
- FR10 诚实降级（显式行为）：① events 逐行解析、坏行跳过并计数（时间线显示"N 行无法解析"）；② 事件超 1000 行默认渲染尾部窗口＋"加载更早"；③ recorded 页图缺失显示占位与"预览文件缺失"文案（仍可跳时间线）；④ LEO_PPT_HOME 未设置或目录不存在显示指引空态（区别于"0 个 run"）；数据缺失一律"暂无数据"占位不报错。
- FR11 渲染与注入安全：新视图沿用 textContent-only 渲染（禁止 innerHTML/insertAdjacentHTML/事件属性字符串拼接）；服务端首屏初始状态注入必须把序列化 JSON 中 `<` 转义为 `\u003c`（`</` 同理）再拼入 `<script>`（堵 `</script><script>` 逃逸——项目目录名等磁盘字符串可含任意字符）。

**可访问性**
- FR12 状态双重编码与键盘可达：页格状态 = 颜色 + 图标/缩写字符（✔/✗/⏳/超）双重表达；页格实现为 button，aria-label 含"第 N 页·状态·最近事件摘要"；tooltip 响应 :focus-visible 并以 aria-describedby 关联；run 短码全码"hover 或 focus 可见"。
- FR13 lightbox 对话语义：`role="dialog" aria-modal="true"`，打开焦点移入、Tab 循环圈定、Esc 与关闭按钮等价、关闭后焦点归还触发格；`<img>` 带 alt（"第 N 页预览·状态"）；翻页到边界播报"已是第一页/最后一页"。
- FR14 轮询与时间线的读屏礼仪：页计数/耗时更新不进 aria-live；仅"阶段跃迁、页失败、终态"三类变化写入 `aria-live="polite"` 离屏区；run 终态后停 3s 轮询（保留手动刷新）；时间线折叠头用 button+aria-expanded，失败事件自动展开不改变焦点；从页格进入过滤态时焦点移至首条并播报"已过滤为第 N 页事件，共 M 条"。

## 5. 产品指标（验收口径）

- 列表/详情首屏数据就绪 <300ms（本地文件读）；
- 500 行事件时间线滚动与页格过滤操作中无超过 100ms 的长帧（DevTools Performance 录制判定）；
- 进行中 run 的页状态变化在 ≤2 个轮询周期（6s）内反映到界面；
- 刷新后停留在同一 run 详情视图（URL `#run=` 定位）且无白屏/报错。

## 6. 原型（信息架构示意）

```text
┌ Leo PPT 控制台 ────────────── [渠道管理] [生成任务●] ─ [固定/自动] ┐
│ ▶ 任务列表（默认）                    ┌ 任务详情（点击进入）──────┐ │
│ ┌────────────────────────────┐      │ ▶▶▶ 准备✔ 逐页生成⏳8m 交付·│ │
│ │ #a3f2 store-digital… Q3    │      │ [✔][✔][✗zhipu×2][⏳][▫][▫] │ │
│ │ generate·逐页生成 7/12(1失败)│      │ ── 事件时间线（最新在上）── │ │
│ │ 2 分钟前更新 ●进行中          │      │ 14:32 ✗ 页3 图像生成失败…  │ │
│ ├────────────────────────────┤      │ 14:29 ✔ 页2 已record zhipu │ │
│ │ #b7c1 ai-native-delivery    │      │ ── 链路：zhipu 12次 1失败  │ │
│ │ upgrade-full ✔ 完成 12/12   │      │ ── 交付：deck.pptx 六门✔  │ │
│ └────────────────────────────┘      └───────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

## 7. 依赖与风险

- 依赖：现有控制台服务与鉴权基建；`LEO_PPT_HOME` 文件契约（盘点报告）。
- 风险：① run 数据由 agent 进程写入，读取方需容忍半写状态（原子写已由 runtime 保证，读取仍需容错）；② 本机无历史 run，验收依赖合成 fixture；③ events/run.log 无 CLI 读取器，读取逻辑为本控制台新增（属读侧适配，不触碰写侧）。

## 8. 审查记录（5 轮）

- R1（产品负责人·产品完整性）：6 项发现已修正——骨架占位降为统一灰块（数据侧无布局信息）；editable 大图预览收缩承诺（v1 仅 image-deck）；run 短码与唯一键定义；补返回导航与标题更新；交付卡覆盖 failure-report 失败态；tooltip 字段改为"以事件/backend_stats 可得为准"。
- R2（产品/UX 评审员，独立评审含源码核验）：8 项发现全部采纳——页状态×数据源映射（slide_jobs 仅二态，active/failed 由事件推断，timeout 条件显示）；页格点击按状态分流（recorded→lightbox / failed、pending→时间线定位，消除 FR5/FR6 手势冲突）；陈旧检测（mtime>5min 中性提示，堵"agent 死亡仍呼吸"误导）；visibilitychange 立即拉取+终态更新标题；失败摘要回落链（failure-report→run.json 阶段+事件）；详情 URL 可寻址（#run=）；指标 2 改为可测长帧口径；cancelled 流程条口径。
- R3（架构师·可行性对齐）：逐 FR 核对数据源全部可落地；两条实现层备注——流程条步骤耗时以 events.ndjson 的 stage_advanced 时间差为主、timing.json 兜底；列表页进度取 run.json `domains.progress` 主域（按路线 terminal_delivery）。无产品级缺口。
- R4（安全/a11y 评审员，独立评审含现有基建核验）：8 项发现全部采纳——预览端点改 run_id+页码形状（客户端永不传路径，resolve 断言覆盖 symlink）；新增 FR11 渲染与注入安全（textContent-only + 首屏注入 `<`→`\u003c` 转义，堵 R4 发现的现有 `</script>` 逃逸面）；新增 FR12-14（状态双重编码/格为 button+aria-label、lightbox 对话语义与焦点管理、aria-live 三类变化礼仪+终态停轮询+折叠键盘语义）；FR10 扩四条显式降级行为（坏行计数/千行窗口/缺图占位/环境缺失指引）；§2 补隐私口径（数据不出本机、路径缩写复制全量）；读接口保持 localhost 开放（Host 校验+无 CORS 头）为结论、token 校验列为可选加固。
- R5（负责人终审）：一致性快扫通过——FR1-FR14 连续无断档；4 条指标均客观可判且与 FR 对应（指标 4↔FR2 URL 定位、指标 3↔FR8）；原型示意与 FR5 点击分流/FR12 双重编码一致；FR8 终态停轮询与 FR3 陈旧检测（仅非终态）互洽。**PRD 定稿 v1.5，移交架构师。**
