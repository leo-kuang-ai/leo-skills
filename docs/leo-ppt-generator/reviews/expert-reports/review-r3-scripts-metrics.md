# 评审报告 R3 · 脚本指标域（源码复核）

- 对象：PRD v1.4 R-73/R-77/R-74/R-82 声明 · 方法：源码全文通读（含 argparse 全部分支）
- 通读：build_rendered_ledger.py、record_run_step.py、estimate_run_cost.py、compute_impact.py、overlay_text.py、export_speaker_notes.py、check_deck_prose.py、build_delivery_preflight.py、_vendor/editable_ppt 的 deck_text_hints.py/paddle_text_hints.py、cli.py 账本段、observability.py
- 日期：2026-09-11

## 断言验证（摘要）

13 项全部确认且多处比 PRD 更严重：OCR 消费端实际三个读者（build_rendered_ledger/check_plan_compliance/check_table_values，转换落约定三处受益）；text_hints.json 生产链完全挂 editable 命令树；**text_fallback 手工补写被 canonical state_hash 封死**（比"无写入方"更强——只能代码级实现）；北极星原料散落四处无统一定义；**偏离率修正**——选择侧 layout-selection.json 是可选冻结、推荐侧生产工件零留痕（suggest_layout 不落盘＋allocate_deck 无消费者），"per-run 可算"应读作"R-77 前置落地后才可算"；lane 占比 render 页可从 slide_jobs.provenance 交叉对账。

## 需求级判断（摘要）

1. **R-73 先决被低估（关键质疑成立）**：转换脚本的输入在 generate 路线不存在——deck_text_hints 的 page_dirs 从 editable jobs 派生且要求 source.png，把 generate 页图塞进 editable run 会被 run 状态校验挡住（伪造 jobs 不可行）；选项一单独交付对 R-73 适用域**零贡献**。真实先决＝generate 页图→PaddleOCR-VL→OCR_DIRS txt 一条龙（submit_and_fetch 接受任意图片路径、text_blocks_to_lines 可独立调用，新脚本约 100–150 行＋token/成本披露）；两方案不是二选一，选项二是必选项、选项一是其末端子集。工程量 M+~L。
2. **指标矩阵**：公式全部可行但三条"可算"各有条件——TF-2 仅带 --sources 的 run 有 manifest（分母回退 slide_jobs、页级去重、自报信任级）；偏离率依赖 R-77 绑定持久化前置；lane 占比唯一污染源是图像页 backend "fixture" 缺省。
3. R-74 接入点：per_type_stats 扩 backend 维度只改一处；R-82：--prose-check 的 advisory 出口范式现成，但**预算时长无来源**（argparse 无时长参数、母版无秒数字段）。

## Findings

R3-1 [高] R-73 先决改写为一条龙；R3-2 [中] TF-2 口径三条件未披露；R3-3 [中] 无 token 环境门语义未定义（builtin-ink 必然无文字）；R3-4 [低] R-82 预算时长来源未定义；R3-5 [低] 补登走加性 sidecar 勿动 canonical entry；R3-6 [低] 偏离率"可算"表述歧义。

## 结论

**有条件通过**——四条核心断言全部源码证实；R3-1 落地前 R-73 开票基线不成立；其余注记级随条目文本吸收。
