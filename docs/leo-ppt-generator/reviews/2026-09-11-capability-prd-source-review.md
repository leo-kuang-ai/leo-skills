# 能力提升 PRD 源码核验与四域评审会（会议纪要 · 第三轮）

- 日期：2026-09-11
- 评审对象：[PRD v1.2→v1.3](2026-09-11-capability-prd-methodology-review.md) 之后的实现现状与 [PRD v1.4](../../prd/2026-09-11-leo-ppt-capability-improvement-prd.md)
- 形式（两阶段，均强制源码解读、禁止抽查）：
  - **阶段一 · 四路源码考古**（SRC-1~4）：状态机调度 / 渲染投影 / 脚本账本 / 测试评测四子系统全文通读（cli.py 3719 行全读、render/ 全目录、约 200 文件），回答 PRD 全部未决先决；
  - **阶段二 · 四域评审**（review-r1~r4）：每域专家独立复核 v1.4 声明（断言验证表）＋需求级判断＋新 findings。
- 报告：`expert-reports/src-1-runtime-state-machine.md`、`src-2-render-lane-projection.md`、`src-3-scripts-ledgers.md`、`src-4-tests-evals-infra.md`、`review-r1~r4`（四份）
- 产出：PRD v1.4（基线吸收）→ **v1.4.1**（评审修正，本纪要裁定全部落位）

## 1. 总体结论

四域评审结论：R1/R2/R3 有条件通过、R4 通过。**v1.4 的源码级声明无一错报**（R2 验证 15 项全部吻合、R3 验证 13 项全部吻合），源码考古质量获确认；评审抓到的是 v1.4 的**三个低估**与**一批表述失准**，全部以 v1.4.1 修订关闭。

## 2. 关键裁定

### 裁定 1 · R-73 先决改写（R3-1，高危，采纳）

v1.4 的"转换脚本"先决在 generate 路线**空转**：其输入 `text_hints.json` 只存在于 editable run 结构（page_dirs 从 editable jobs 派生且要求 source.png 在场），generate 页图无 hints 可转。→ 先决改单项"**generate 页图 OCR 探测一条龙**"（复用 `paddle_text_hints.submit_and_fetch`＋`text_blocks_to_lines`，约 100–150 行）；工程量 M+→M+~L；补无 token 环境门语义（not_run 披露＋离线校准替代）。

### 裁定 2 · R-71 补第六项缺口（R2-1，高危，采纳）

批量渲染性能路径缺失：render_page 每页独立起字体服务＋启停 chromium，实测 1.26–1.30s/页（html-deck-e2e sidecar），40 页顺序≈51s，叠加 40×42 候选资格检查后 ≤60s 阈值无余量。→ 缺口清单扩为六项（编排级浏览器/字体服务复用＋失败重试＋部分成功语义＝新组件工作非纯接线）；**40 页性能 spike 前置为开工门**；缺省绑定改"推荐序首个"与 top2 修复共用 `_soft_rank`（R2-2 同步采纳——qualified_pool 序也是 asset_id 序，只修 top2 不同步修 R-71 消费口径会让骨架系统性偏向字典序版式）。

### 裁定 3 · 维护债修正与升级（R1 系列，采纳）

- **债5 升级**：run-ledger 双写入方（agent＋runtime 观察哨）schema 不兼容——runtime 行 page 为 int、缺 schema_version，`--resume-suggestion` 对混合行抛 TypeError 崩溃（EXP1 实证）。修复二选一：adapter 写 str(number) 或 `_page_sort_key` 容错；
- **债2 触发链修正**：KeyError 真实链路＝"vendor 直写覆盖已 recorded 页状态后复位重放"与"editable reset --confirm-lost 后重放"（破坏幂等重试合同，严重度升中）；
- **§1.5-4 措辞修正**："每页独立 FileLock"→"每域单锁＋全局 revision CAS；CLI 零重试支持，重试由外部 Agent 承担"；
- 新增：sweep 轮次预算按 apply 调用计数（空轮烧预算）；blocked 页三口径不一致（editable status 计 pending → next 会建议派发 blocked 页）。

### 裁定 4 · R-81 关闭维持（R1，采纳＋补残留物）

四个断言中三个源码确证、一个（锁粒度）表述修正但结论不变——关闭**不草率**。残留物清单扩为四项：①派发指引（含 vendor_revision_conflict 整命令重跑语义）②sweep 语义越界登记（跨域复位 editable＋无 in-flight 保护）③sweep 预算计数修正④调度纪律告警接入 R-77 观察指标（agent_id 自报可伪造，维持观察不 enforce 的决定确认正确）。

### 裁定 5 · R-70 成本再校准（R2-3/R4-3，采纳）

- R-70a 补 overlay 主题化小改三项（离线字体/主题色对比度/换行——否则盲评在字体不一致上无谓失分）；
- 验收 2 补：**判官通道 spike 前置**（codex exec 图片输入能力仓库内零先例）；verdict schema 从四态扩评分制列入成本；正例判读走协议/L1 判官（R4-4，并入 R-84 同款口径）；
- 回放集最小构造判 M：u19 硬编码可改造母版与白名单、html lane 零成本页图＋image lane 一次付费冻结、runs_fixture 骨架；新建项收敛为 TF 事件标注＋母版→PAGES 转换。

### 裁定 6 · R-77 口径与插入点精化（R3-2/R3-5/R1-5/R4-2，采纳）

TF-2 口径三注记（页级去重/无 --sources 的 run 分母回退 slide_jobs/自报信任级）；补登推荐路线 a′（backend_stats 式加性 sidecar，插入点 argparse＋`_append_backend_stats`，canonical entry 勿动——手补被 state_hash 封死）；收编补调度纪律告警计数；runs_fixture 措辞修正（render 页型参数已有，缺 TF-2 标记与空 run 断言）。

### 裁定 7 · 漂移清单扩至八项（R2-4/R4-1，采纳）

新增：layout_selection docstring 自称"推荐摘要"与实现脱节；content-quality README 登记 adjudication-u04/u10/u16 三文件实为单文件三节。

## 3. 部分采纳与驳回

- **R4"盲评图片通道或可用独立多模态判官直连 4.5V 绕开双 CLI"**：作为备选路线采纳进先决 3 判官 spike（两 CLI＋4.5V 直连各验一次），不预选——家族多样性要求可落在另一判官或人工辅证（protocol 先例支持）。
- **R1"blocked 三口径统一"**：采纳，但归属 R-73 写侧契约（与页态事件结构化同期），不独立立项。
- 驳回：无。

## 4. 行动项

| # | 行动 | 时点 |
| --- | --- | --- |
| 1 | 修复 run-ledger 混行崩溃（债5，一行修复＋回归）与 sweep 预算计数 | 随 R-77 波 1 或独立维护 commit（建议立即） |
| 2 | R-71 的 40 页性能 spike（开工门） | R-71 开票前 |
| 3 | R-70 判官通道 spike（双 CLI＋4.5V） | R-70a 开票前 |
| 4 | R-77 效力反算＋TF 口径收敛（含 a′ 插入点） | R-70 否决门前 |

## 5. 三轮评审累计状态

三轮共 12 位专家/4 路源码考古、~150 findings，PRD 从 v1.0 演进至 v1.4.1：第一轮修验收牙齿、第二轮修门的可满足性与结构保证、第三轮以源码为锚修工程量与先决真伪。当前所有 P0/P1 条目的"基建已备/缺口/工程量"均有 `文件:行号` 级证据支撑；活跃 13 条、波 1 五条可开工（R-77 最小子集无阻塞）。
