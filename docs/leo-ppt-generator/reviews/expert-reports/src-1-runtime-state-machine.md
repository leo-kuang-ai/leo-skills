# 源码考古 SRC-1 · 运行时状态机与调度

- 对象：PRD v1.3 涉及的状态机/调度/收据子系统 · 方法：全文通读+调用链追底（禁止抽查）
- 已完整读取：lifecycle.py(407行)、image_deck/adapter.py(384)、upstream_bridge.py(348)、backend_execution.py(186)、storage.py(191)、runs_console.py(661)、upgrade/baseline.py(237)、hybrid/assembler.py(244)、cli.py(3719 全部)、application/run_index.py(846)、editable/adapter.py(639)、render/receipt.py(492)、render/provenance.py(122)、application/sample_decisions.py(191)、application/routes.py(167)、observability.py(300)、_vendor/codex_ppt/{record_slide_dispatch,record_slide_result,record_slide_blocker}.py
- 日期：2026-09-11

## Q1 · 调度并行性（R-81 先决）

**调度者是外部 Agent，不是 CLI**。image 子命令集仅 `prepare/sample-record/sample-verify/record/sweep/finalize/assemble`——**不存在 `image dispatch` 命令**（cli.py:1443-1526）；`image.dispatch` 只是 route stage 名（application/routes.py:53）。CLI 只发建议：`_worker_dispatch_action`（cli.py:1138-1151）返回 `request_worker_dispatch`，多页 `multi_agent_required`、单页 `single_unit_current_agent_allowed`，`runtime_fallback: False`；`run next --worker-available` 多页无 worker 时 blocked（cli.py:1211-1212）。

**"某页 record→QA"与"其余页派发"无任何 runtime 互斥**：
1. `image record` 一次一页，只做复制产物+hash（image_deck/adapter.py:233-244）、登记 operation（245-252）、写事件（cli.py:2882-2889）——**record 不做任何 QA**（只校验源文件存在 adapter.py:188-190）；页级视觉 QA 是 worker 侧 `--qa-note` 职责；deck 级 visual_render 初始 not_run（observability.py:274）。
2. 页间无顺序约束：每页 record 经 `FileLock + revision CAS` 独立提交（adapter.py:214-228）；并发 record 后进锁者 `vendor_revision_conflict`（227-228）需重试——**高并行度会放大的唯一冲突点**。
3. **源码级结论：QA 与派发可并行，runtime 层无代码障碍**；整册时延由外部 Agent 派发并行度决定。

**run lease**：获取 `_lease_for_operation`（cli.py:918-946）→ `RunIndex.issue_lease`（run_index.py:554-591）uuid 一次性 lease；校验 `validate_lease`（593-604：lease_invalid/lease_revoked/generation_conflict/run_not_mutable）；拒绝迟到 lease 的机制＝generation：cancel 时 generation+1 并 revoke 全部 active lease（733-737）。**无 TTL、无续期、无崩溃回收**——worker 崩溃后 lease 永远 active，只能 `run cancel --wait-workers`（grace 默认 300s，cli.py:2579）超时转 timeout。

**`run retry --from-failed-pages`**（cli.py:2505-2532 → lifecycle.py:236-266）：reconcile → 幂等指纹 operation → 仅 created 态执行 `reset_failed_pages`（failed/blocked/timeout 清为 pending，只保留 page_id/slide_id/number/source/source_sha256/notes 五字段，revision+1）；**recorded 页绝不被重置**；retry 不 bump generation。

## Q2 · TF 链结构化现状

**`text_fallback: true` 在 runtime 生产代码零写入点**。全树 grep 仅命中：references/image-deck-workflow.md:272（文档声明）、tests/boundary/test_overlay_text.py:283,288（测试自造 dict）、evals judge。生产写路径 `ImageDeckAdapter.record` 的 slide.update 只写 status/artifact/sha256/backend/agent_id（adapter.py:236-244）；render provenance schema 也无此字段（provenance.py:30-38）。

**TF-1 无任何结构化记录**（无 reason code/step/字段）；唯一代码痕迹是 `--rework` 旗标 help："TF-1 重生成后的合法重录；无旗标一律拒绝覆盖"（cli.py:1492-1494），实现为已 recorded 页终态保护（adapter.py:193-200 无 --rework → page_already_recorded）。

**attempts**：`image record --attempts`（默认 1，cli.py:1490）→ `_append_backend_stats`（cli.py:3625-3650）追加 backend_stats.jsonl（sidecar 设计：deliberately outside slide_jobs.json so canonical state hash unaffected）。**attempts 完全自报**；qa 失败的 blocked 由 vendor 工具写 slide_jobs（record_slide_blocker.py:33-40），**不产生 backend_stats 行也不写 events**。

## Q3 · worker 派发本质

**dispatch 是纯状态登记，不是 spawn**（editable/adapter.py:282-345：FileLock 内校验、prompt durable_copy 冻结 sha256、status→active，全程无 subprocess）。真正的子进程只在 upstream 桥调 backend API（upstream_bridge.py:169）。**"真实 spawn 前不得记录 dispatch"无硬保证**，只有间接证据链 + WS6 观察哨：同 agent 累计 record ≥3 页 → run-ledger 追加 `dispatch_discipline_warning`（adapter.py:259-289，观察不阻断）。`single_unit_current_agent_allowed` 返回条件统一为单页+无外部 worker（cli.py:1143-1145, 1213-1214；editable/adapter.py:248-262）。

## Q4 · 收据实现

五类指纹（render/receipt.py:45-51, 175-229）：`page_artifacts`（origin_image/**、editable/pages/**、final/*.pptx）；`local_assets`（input/** 非样式命名）；`qa_reports`（validation-summary/failure-report/reports/*.json，排除 timing.json 与收据自身）；`render_previews`（**只覆盖 reports/render-preview/** 与 final/render-preview/**——新目录如 previews/ 不冲突**）；`template_style_sources`（样式命名 input 文件+模板目录，库回退 `library/` 前缀锚定）。排除 logs/observability/run.json。content_binding 摘要（245-281）：内容包 content_digest/page_ids + layout-selection 三键 + resolved-design 双 digest。verify：schema 校验→collect(allow_missing=True 离线可验)→对称差→content_binding→影响面推断（344-391）→ fresh|stale|missing|invalid；集成 `_delivery_receipt_gate`（cli.py:1013-1035：无收据 not_run 不崩、stale/invalid blocked）。

render receipt 消费链（provenance.py）：kind/schema/backend 枚举（29：render:html|render:mermaid|render:echarts）→ `out_sha256` 与 run 内已落盘 artifact 逐字节比对防张冠李戴（64-77）→ 同锁并入 slide.provenance + revision+1（112-114）。**record 的 --backend 缺省 "fixture"（cli.py:1485），渲染页须显式 --backend render:html 否则 render_receipt_invalid（provenance.py:97-101）**。

## Q5 · 样张收据

binding 六字段严格集合校验（sample_decisions.py:47-49）；16:9 断言 `width*9==height*16`（53-56）；backend 须等于冻结合同 provider，render-lane deck 额外允许 render:html/mermaid（61-76）；样张图 PIL verify（77-85）。decision 三元组：authorization_quote 必须是 authorization_ref 文件内容子串（109-110）。supersedes（136-152）：内容相同 replayed；不同须 --supersedes＝旧收据 sha256，旧件归档 `reports/sample-decisions/<sha>.json`。**REQUIRED_PATH = reports/sample-decision-required.json 在 record 时无条件写入（137）——只要记录过一次样张 legacy 通道永久关闭**（163-166），防降级绕门。verify stale 检测重算 _binding 比对（179-187）。

## PRD 声明核对表（摘要）

| PRD 声明 | 裁定 | 证据 |
| --- | --- | --- |
| R-81 先决"调度核实，已并行则关闭" | **确认：runtime 层已并行友好** | cli.py:1138-1151；adapter.py:214-228 |
| R-81 "已 rendered 页不重派" | **确认机制已在**（page_already_recorded + reset 只动失败态） | adapter.py:193-200；lifecycle.py:248-250 |
| R-77 "TF-2＝text_fallback:true 计数" | **修正：字段无写入方，文档-代码漂移** | 全树 grep；adapter.py:236-244 |
| R-77 "无新采集通道，允许补登结构化字段" | **确认可行**（backend_stats 即加性 sidecar 先例） | cli.py:3629-3631 |
| §7 页级失败事件结构化 | **部分成立仍属未来时**：runtime 事件走 events.ndjson，但页级 blocked 由 vendor 写 slide_jobs 不写 events；控制台仍靠 run.log 行推断 | runs_console.py:36-37,441-471 |
| R-79 alt 加性字段 | 确认现状 schema v1 无 alt（未来项兼容） | receipt.py:292-308 |
| R-71 previews/ 不进指纹 | **确认兼容**（previews/ 不在五类任何采集路径） | receipt.py:180-218 |
| R-70a source_class 封闭枚举扩展 | 确认地基已在（7 类枚举含 deterministic-overlay/render） | adapter.py:28-38,72-73 |

## 意外发现（影响需求）

1. lease 无 TTL/续期/崩溃回收（worker 崩溃→cancel --wait-workers 300s 超时兜底）；
2. `retry --from-failed-pages` 后旧 operation 重放读已清除的 `slide["artifact"]` 键会抛**裸 KeyError** 而非稳定 ContractError（adapter.py:220-224 × lifecycle 清除）——维护缺陷；
3. dispatch 纪律观察哨已在生产代码（PRD 未提），是 R-81 核实的现成机器证据通道；
4. attempts 自报、qa 失败不进 backend_stats——R-77"重试分布"缺失败侧数据源；
5. 并发 record 的 revision CAS 冲突是并行度放大点；
6. backend_stats 双消费者（backend report 与控制台）各自聚合，无共享模块——PRD §7"数字单一来源"指向正确。
