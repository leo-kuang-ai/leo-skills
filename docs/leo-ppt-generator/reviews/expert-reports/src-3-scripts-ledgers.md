# 源码考古 SRC-3 · 确定性脚本与账本

- 对象：scripts/ 确定性脚本 + observability 账本 · 方法：全文通读（含 argparse 全部分支）
- 已完整读取：build_rendered_ledger.py、record_run_step.py、compute_impact.py、estimate_run_cost.py、overlay_text.py、check_deck_geometry.py、build_delivery_preflight.py、reproject_derivatives.py、export_speaker_notes.py（含 --prose-check）、check_sensitive_text.py、observability.py、evidence.py、_vendor/editable_ppt/editppt/runtime/{deck_text_hints,paddle_text_hints,text_hints}.py、config/channel_catalog.py、setup.py、cli.py 相关段
- 日期：2026-09-11

## Q1 · OCR 通道（R-73 先决）

**OCR_DIRS 常量原文**（build_rendered_ledger.py:42-44）：`("reports/ocr", "ocr", "image-deck/ocr")`，文件 pattern 六种（page_{n}/page_{n:02d}/page_{n:03d}/slide_{n:02d}/slide_{n:03d}/S{n}.txt），find_ocr_text 按序取第一个命中（138-147）。

**生产者考证（代码 vs 文档）**：仓库唯一真实 OCR 代码属 editable 路线——vendored `editppt run hints`（deck_text_hints.py:128-151）：有 token 时批量提交 PaddleOCR-VL 云 API（paddle_text_hints.py:31-32，`PaddleOCR-VL-1.6`），无 token/失败回落本地 `builtin-ink`。**但产物是 `pages/page_NNN/text_hints.json` + overlay PNG，不是 `page_<N>.txt`，也不落三个 OCR_DIRS**——形态与目录双错位。builtin-ink 是纯几何检测器（"measures where text is and how large, it cannot read it"，deck_text_hints.py:133-135）。setup 侧 paddleocr 只在 route≠generate 且 ocr_requirement=editable_text_hints 时列为可选（setup.py:131-155）——**generate 路线 setup 完全不涉及 OCR**。

**结论：整个仓库没有任何代码写 page_<N>.txt 到 OCR_DIRS**。唯一"生产者"是文档约定（check_table_values.py:13-14 明言来自"PaddleOCR hints 或人工导出"）——靠 agent 人工转换桥接的断开接线。缺失页 ledger 标 `ocr_status: missing`、key_numbers 降级从 notes 抽取显式标 source=notes、exit 0 不编造（171-185, 198）。

## Q2 · 账本格式与 R-77 指标可得性

**backend_stats.jsonl 行**（cli.py:3640-3645）：`{ts, slide, backend, page_type, attempts, tokens}`——backend 自由字符串**默认 "fixture"**（cli.py:1482）；page_type 枚举仅 chart/text-heavy/image（:1487）；tokens 全靠 --tokens 透传缺省 not-recorded（1495-1497）**无自动采集**。聚合双消费者：backend report（first_pass_rate，cli.py:3653-3679）与控制台（runs_console.py:553-586）各自实现无共享模块。

**run-ledger.jsonl 行**（record_run_step.py:83-94）：`{schema_version, ts, step, page, attempt, status, problems, artifact, artifact_sha256, note}`；RUN_STEPS=("prompt","backend","qa","record","receipt")（:37）；MAX_PAGE_ATTEMPTS=3（:41）。**runtime 也会写枚举外行**：dispatch_discipline_warning（adapter.py:274-287，无 schema_version/status）。**run-ledger 是纯 agent 礼仪**（execution-contract.md:190-193 自认 CLI 自动接线不存在）。--resume-suggestion（133-202）：逐页四阶段推断续点；exit 2 双义（需人工 vs 用法错误）。

**rendered-ledger**（build_rendered_ledger.py:189-200）：每页 page_id/slide_no/artifact_sha256/ocr_status/ocr_text_head(160字)/key_numbers(top5)/chart_count/notes_head；**key_numbers 双形态**（ok=list[str]，missing=list[{value,source}]，167 vs 180-182）。

**sample-decision.json**（sample_decisions.py:125-133）：binding 十键 + decision 三元组 + contents_sha256；16:9 断言；render-lane backend 白名单已含 render:html/mermaid（68-70）；supersede 归档链（149-151）。

**指标可得性矩阵**：

| 指标 | 现状 | 缺口 |
| --- | --- | --- |
| TF 触发率 | per-run 近似今天可算（sources-manifest 数 `source_class=="deterministic-overlay"`，overlay_text.py:240 产标记；reproject_derivatives.py:131 继承）；文档承诺的 slide job text_fallback **无写入方** | text_fallback 落地或删文档声明；跨 run 聚合器 |
| 北极星返工轮次 | 原料在（attempts/rework 旗标/母版 post-confirm 链 find_confirmed_baseline.py:36-60/样张归档件数） | "轮次"无权威定义；通道未归一 |
| 预览拦截轮次 | 补登后可算（样张必过门 verify 在 cli.py:2758；重确认可数 sample-decisions/ 归档件数） | 专用计数行不存在 |
| 建议偏离率 | per-run 可算（layout-selection.json 冻结 selection+top2+page_status，layout_selection.py:270-289） | 基线选 top2 还是 suggest_layout 未定（suggest_layout 无状态不持久化） |
| lane 占比 | per-run 有条件可算（backend_stats.backend 自由串；sample-decision backend 已认 render lane） | backend 靠自报默认 fixture；page_type 无 render 类；estimate_run_cost 聚合忽略 backend |
| 同项目重复 run | 分组结构已备（projects/*/runs/* + registry project_root） | 聚合器缺；"重复"定义未定（content_digest 可作判重键 receipt.py:255） |

## Q3 · R-74/R-76 支撑

**estimate_run_cost**（:10-14, 88-95, 126-133）：`per_page = mean_tokens × max(mean_attempts,1)`，headroom 1.5 有历史/2.0 假设；**无 lane 区分**（per_type_stats 只按 page_type 分桶，backend 不读取）；basis 三态强制披露。**tokens 常缺 → 大多 run 落 assumed-default×2.0 带宽**。

**compute_impact**：页级清单+六类理由迭代到不动点——页块增删/变化/页序（196-205）；数字登记表行键=(数值,页)增删映射（111-126, 229-232），原始行对称差解析不出目标页则全 deck（219-227）；术语词形≥2字正文匹配（163-167）；交叉引用闭包（146-160）；页外变化全 deck 兜底（207-217）。**粒度上限＝页，无 slot/figure 级**。

## Q4 · overlay_text.py（TF-2 现状）

画布恒定 2560×1440（:40）；同比例 LANCZOS 缩放（205）；**非 16:9 拒绝**（200-204）；白名单两种形态（纯数组自动排版 / {required_text, anchors} 锚点三重拒绝 141-149）；落位超画布拒绝不静默截断（208-223）；颜色 #RRGGBB；stdout 末行 JSON 含 base/output 双指纹 + `source_class: deterministic-overlay`（231-242）。边界：锚点间无重叠检查。**slide-job text_fallback 与 manifest 记录是文档合同，代码无写入方**。

## Q5 · R-82 接线点

`--prose-check` 复用 scan_speaker_scripts，**advisory only**（PROSE-WARN 到 stderr 不阻断不改退出码，export_speaker_notes.py:15-17, 98-115）；检查三项（check_deck_prose.py:612-642）：15 短语套话表、单句 >40 字、通知腔"大家"。**无任何时长/语速模型雏形**（无字/分钟常量）——R-82 需全新通道。

## 意外发现

1. image 路线 OCR 是"无生产者的消费端"（三读者等 txt，唯一 OCR 代码产 JSON 于 pages/，agent 人工桥接）——R-73 需确定性转换脚本；
2. runtime 向 run-ledger 写枚举外行（dispatch_discipline_warning）——schema 不再单一；
3. run-ledger CLI 自动接线不存在，指标依赖部分有漏记风险；
4. key_numbers 双形态，下游聚合须兼容；
5. 成本模型实践常退化为假设区间（tokens 缺省 not-recorded）；
6. build_delivery_preflight 的 GATE_ORDER 死常量列 4 门、实际执行 5 门（含 U7 projection 门，258-262）——文档/代码漂移；
7. 样张收据已是 lane 权威锚点（16:9+render backend 白名单+归档链）——lane/拦截指标最便宜挂靠点；
8. --resume-suggestion exit 2 双义码（CI 断言注意）。
