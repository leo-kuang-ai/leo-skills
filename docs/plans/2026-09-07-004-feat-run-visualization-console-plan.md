---
title: Run Visualization Console - Plan
type: feat
date: 2026-09-07
artifact_contract: spec-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: legacy-prd
execution: code
status: active
origin: docs/prd/2026-09-07-leo-ppt-run-visualization-prd.md
---

## Goal Capsule

- **目标**：在现有本地控制台新增「生成任务」Tab：任务列表 + 详情（流程条/页网格/事件时间线/链路聚合/交付卡/页图 lightbox），纯只读、轮询驱动，兑现 PRD FR1-FR14。
- **推荐方案**：新增读侧模块 `runtime/src/leo_ppt_generator/runs_console.py`（扫描/解析/聚合，纯读容错）+ web.py 挂 3 个新 GET 端点（列表/详情/页图沙箱）+ 前端单文件扩展 Tab 与详情视图。
- **决策焦点**：页图沙箱（run_id+页码形状、resolve 断言）；首屏注入 `<` 转义（修现有逃逸面）；events 推断页状态（active/failed）的规则确定性。
- **验证焦点**：`tests/test_runs_console.py`（解析/容错/沙箱拒绝）+ `tests/test_config_web.py` 扩展（新端点/转义/静态断言）+ 合成 run fixture 浏览器验收。
- **最大风险**：合成 fixture 与真实 run 结构漂移——以 run_index.py/routes.py/adapter.py 写侧代码为契约源构造 fixture，并在技术方案 R 轮核对字段。
- **停止条件**：任何实现需要写 run 文件或绕过沙箱断言才能工作，停止重审。

---

## Planning Contract

### 数据契约（读侧，以写侧代码为准）

- run 发现：`glob(${LEO_PPT_HOME}/projects/*/runs/*/run.json)`；run_id 取自 run.json（uuid hex，全局唯一定位键）；updated_at 取 run.json mtime。
- 列表项：`run_id, project(目录名), route, status(created|in_progress|completed|failed|cancelled), stage, progress{total_units,completed,failed,active,pending}(取 domains 主域：generate→image，其余→editable；主域无 progress 键时——如刚创建未 reconcile——进度字段全 null), updated_at, stale_minutes(mtime 距今, 仅非终态计算)`。
- 路线步骤（前端静态映射，源自 `application/routes.py ROUTES`）：generate=[准备,逐页生成,交付]（image.prepare/dispatch/finalize）、direct-editable 同构中文、upgrade-full=[检查,准备,逐页生成,交付]、upgrade-selected=[检查,准备(选定),逐页生成,组装]。
- 页状态（R2 架构核验后的真实契约）：
  - **image 路线**（`image-deck/slide_jobs.json`，顶层键 `schema_version/revision/prepare_fingerprint/run_status/operations/sources/slides`；每 slide entry `{number, slide_id="slide_{n:02d}", status, notes, artifact?, sha256?, backend?, agent_id?}`）：**仅 recorded/pending 二态**（entry.status；sweep 亦按此二态处理）。image 路线无页级 dispatch 事件——**failed/timeout 从 `reports/timing.json` 的 `pages[]`（unit_id+status+reason_code）与 `logs/run.log`（status=failed/blocked 行）推断**，映射到对应页码显示红/橙；推断不出则保持二态。
  - **editable 路线**（`editable/page_jobs.json`，顶层键含 `pages`；entry `{page_id="page_{n:03d}", number, status, source, page_dir, ...}`）：`active` 由 dispatch **直接落盘**（page_jobs.status），无需推断；`editable.reset` 事件与 timing 同样提供失败线索。
  - 解析失败/缺文件 → 页列表按 run.page_order 或 1..total_units 生成 `unknown`（灰）。
- 详情附加：`events`（events.ndjson 尾部 max 200 行 + 坏行计数 bad_lines + 总数 total_lines；超 1000 行由前端"加载更早"调 `?events_before=<seq>` 分页；事件 kind 全集以 cli.py/run_index.py 写侧为准——注意 image 路线只有 prepared/recorded/assembled 三个域事件）、`delivery{deck_path(缩写显示/全量复制), gates[](validation-summary `quality_gates` 六门；失败优先 failure-report{failures,recovery_action}；再回落 run.json 失败阶段+事件摘要；upgrade-selected 补读 final/*.delivery.json)}`、`backend_stats`（按 provider 聚合 attempts/tokens；tokens 缺省可为字符串 "not-recorded"→按 int 容错计 0 并标注未记录；editable/upgrade 路线该表恒空→显示"仅图片路线记录渠道统计"）、`duration_seconds`（timing.json summary.total_duration_seconds；缺省 null）、`steps` 耗时（**timing.json stages[] 为主**（每 CLI 命令 started_at/completed_at/duration），`run.stage_advanced` 事件差值补显式 run advance 跃迁——派生 stage 不发事件，事件差值会缺 prepare 段）。

### API 契约（web.py 新增，全部 GET、Host 校验、no-store、读侧开放不加 token）

- `GET /api/runs` → `{runs:[...列表项...], home_missing: bool}`
- `GET /api/runs/{run_id}` → 详情对象（含 `events_window` 元数据）；`{run_id}` 不存在 → 404 `run_not_found`；支持 `?events_before=<seq>&events_limit<=500`。
- `GET /api/runs/{run_id}/pages/{n}.png` → 图片字节；**真实路径从 slide_jobs entry 的 `artifact` 字段解析**（后缀不定：png/jpg/jpeg/webp），再套 `Path.resolve()` + `is_relative_to(<该 run 目录 resolve>)` + 后缀白名单断言；任何不满足或 entry 无 artifact → 404 `preview_not_found`；Content-Type 按实际后缀映射；Cache-Control `no-store`（与全局一致）。
- 首屏注入扩展：`__LEO_INITIAL__` 增加 `runs`（列表），**runs 注入独立 try/except**（坏 run.json 不拖垮渠道 Tab 首屏直出）；**序列化时 `<`→`\u003c`、`>`→`\u003e`（修现有逃逸面，PRD FR11，注入点 web.py `_serve_index`）**。

### 模块边界

- `runs_console.py`（新，约 260 行）：`RunScanner(home)`（发现+列表）、`run_detail(run_id)`（聚合）、`page_image(run_id, n)`（沙箱路径解析）；纯标准库；不 import config 域；**home 由 web.py 解析（复用 config.runtime_config.default_home）后注入 RunScanner**，读侧不复制平台逻辑。架构姿态 `new`（读侧新边界：与 ConfigService 写域隔离，避免 config 包继续膨胀）；不 import run_index（写侧）。
- 前端：`config-ui.html` 扩展（预计 +500 行，总量 ~1300）：**单文件为零构建自包含的显式决策**（v1 阈值 ~1500 行，超出再议拆分并新增资产端点）；Tab 路由（`#tab=runs`/`#run=<id>`，hashchange）、列表/详情/时间线/网格/lightbox 组件、轮询管理器（3s/15s、visibilitychange、终态停）、aria-live 离屏区。

### 测试与 fixture

- `tests/test_runs_console.py`：RunScanner 解析/容错（坏 json/缺字段/半写 events/空 home）；页状态推断规则表；沙箱拒绝（`../`、绝对路径、symlink 指向 home 外、白名单外扩展、不存在 run）。
- `tests/test_config_web.py` 扩展：3 端点 happy/404/转义断言（注入含 `</script>` 的项目名后 served HTML 无裸 `</script>` 注入点）；静态断言（tab 锚点、lightbox、aria-live、双重编码标记）。
- fixture 工厂 `tests/runs_fixture.py`：`make_run(home, project, route, pages, statuses, events, with_png)`——按写侧契约生成 run.json/jobs/events/timing/validation-summary/页 PNG（Pillow 纯色小图，无文字依赖）；验收与单测共用。

### 实施单元

- U1 `runs_console.py` + `tests/runs_fixture.py` + `test_runs_console.py`
- U2 web.py 端点与注入转义 + `test_config_web.py` 扩展
- U3 前端任务 Tab（列表/详情/时间线/网格/lightbox/轮询/a11y）+ 静态断言
- U4 CLI `leo-ppt ui` 入口（同一 serve，新增顶层子命令；`config ui` 保持）+ 文档（SKILL/README/provider-catalog 提及 + CHANGELOG）

### 审查记录（5 轮）

- R1（架构师·自审）：3 条备注——slide_jobs 写侧结构待核验（交 R2）、events 大文件每轮全读的性能口径（5000 行 jsonl 本地 3s 一次可接受）、前端单文件行数边界（后经 R2 建议设 ~1500 行显式阈值）。
- R2（架构评审员，独立评审含写侧源码逐文件核验）：8 项发现全部采纳——**image 路线无页级 dispatch 事件**（failed/timeout 改从 timing.json/run.log 推断）；页图真实路径改从 entry.artifact 解析（后缀不定）；jobs 键名修正为 slides/pages 且 editable active 直接落盘；progress 键名 total_units 与主域回落条件；steps 耗时改 timing.json 为主；backend_stats tokens 字符串容错与 editable 空表口径；home 解析归 web.py 注入；runs 首屏注入独立容错。正面确认：ROUTES 步骤映射、run.json status 取值、事件行结构、六门/失败报告/timing 字段、读侧开放先例、`new` 模块边界与依赖方向。
- R3（安全专项·负责人）：沙箱链路终确认——客户端输入面收敛为 run_id（uuid hex 白名单）+ 页码（int），路径由服务端 artifact 字段构造，resolve+is_relative_to+后缀白名单三层；symlink 逃逸被 resolve 断言覆盖（含 artifact 字段被注入 `../` 的写侧污染场景）；注入转义点在 `_serve_index` 单点、对渠道与 runs 注入统一生效；无新增写面。通过。
- R4（测试负责人·自审）：fixture 工厂以 R2 核验的字段级契约为源（slides/pages 键名、timing pages[].unit_id、events kind 全集、六门 quality_gates）；测试矩阵补三条关键负路径——artifact 含 `../` 的沙箱拒绝、坏 run.json 不拖垮列表与首屏、`?events_before` 分页边界；性能口径（首屏 <300ms）以合成 60 页 run 验证。通过。
- R5（负责人终审）：数据契约与写侧源码逐项对齐（R2 事实基础）、PRD FR4 已同步修正、API/模块/测试三节自洽、无未决分叉。**技术方案定稿，进入实施 U1→U4。**
