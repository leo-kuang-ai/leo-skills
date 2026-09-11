# 评审报告 R1 · 状态机域（源码复核）

- 对象：PRD v1.4 状态机/调度/收据域声明 · 方法：源码全文通读＋两项可重跑实验（EXP1/EXP2）
- 通读：cli.py（3719 行）、image_deck/adapter.py、application/run_index.py、lifecycle.py、sample_decisions.py、render/receipt.py、observability.py、editable/adapter.py、record_run_step.py、build_delivery_preflight.py、estimate_run_cost.py、overlay_text.py
- 日期：2026-09-11

## 断言验证（摘要）

15 项断言验证：A1 无 image dispatch 命令✓；A2 record 不做 QA✓（限定：仅 image 域，editable record 有结构校验门）；A3 页间无顺序依赖——**结论成立、机制描述修正**（每域单锁 `.slide_jobs.json.lock`＋全局 revision，非"每页独立 FileLock"）；A4 终态保护✓；A5 WS6 观察哨✓；A6 CAS 冲突✓（补充：CLI 零重试封装，重试全外包外部 agent）；B1 TF-2 manifest 口径——**口径数据现成✓、"指标现成"不成立**（全仓无计数代码，且 pages-vs-visuals 计数二义）；B2 backend 缺省 fixture✓（render-receipt 路径已被机器强制）；B3~B5 page_type/tokens/无 lane 区分✓；**B6"run-ledger 纯 agent 礼仪"不成立**——runtime 是第二写入方且行 schema 不兼容致消费者崩溃；C1~C6 六项维护债全部属实（债2 触发链失准、债5 定性低估，见下）。

## 需求级判断（摘要）

1. **R-81 关闭不草率**（三断言确证＋一表述修正），但"无需仓库工程投入"过强——补三项残留物：sweep 语义越界（`image sweep` 经 `Lifecycle.reset_failed_pages` 跨域复位 editable 失败页＋无 in-flight 门＋计划读取不加锁）；CAS 冲突重跑语义入 Worker 指引；dispatch_discipline_warning 接入 R-77 观察指标（agent_id 自报可伪造，维持观察不 enforce 正确）。
2. **R-77 补登插入点**：路线 (a) canonical 写入需同步改幂等 fingerprint（schema 演进面大）；**推荐 (a′)** backend_stats 式加性 sidecar——argparse store_true＋`_append_backend_stats`（cli.py），canonical hash 零影响。TF-2 公式须钉死页级 vs visual 级并披露自报信任级。

## 实验

- **EXP1**：向 run-ledger 注入 runtime 式行（page 为 int、无 schema_version）→ `record_run_step.py --resume-suggestion` 在 `_page_sort_key` 抛 `TypeError`（崩溃实证）。
- **EXP2**：record 成功→vendor 直写 blocked→`reset_failed_pages`→重放同 operation → `adapter.py:221 slide["artifact"]` 抛裸 `KeyError`（exit 1 traceback，破坏幂等重试合同）。

## Findings

R1-1 [中] run-ledger 双写入方 schema 不兼容致崩溃（修复一行二选一）；R1-2 [中] sweep 语义越界＋无并行保护；R1-3 [低] sweep 轮次预算按 apply 计数（空轮烧预算）；R1-4 [中低] blocked 页三口径不一致（editable status 计 pending→next 建议派发 blocked 页）；R1-5 [低] 调度纪律告警未入 R-77 收编清单；R1-6 [勘误] 锁粒度与"重试"表述修正；R1-7 [低] TF-2 口径二义＋自报信任。

## 结论

**有条件通过**——R-81 关闭方向成立（需补残留物登记）；B6 须修正；补登插入点已精化；六项维护债属实（两项需改写/升级），新增七项 findings。
