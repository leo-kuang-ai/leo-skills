---
title: leo-ppt-generator 产品 P1 优化批 - Plan
type: feat
date: 2026-08-31
topic: leo-ppt-product-p1-optimization
artifact_contract: spec-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: product-analysis-2026-08-31
execution: code
status: completed
---

# leo-ppt-generator 产品 P1 优化批

## 背景与目标

P0 批（2026-08-31-001，已合入 b4eb4c9）落地表面合同 block-early、确认门回合
合并、成本预估前置与 README 成品样例。本批推进 P1 四项：回头用户合同免答
（交付档案）、学术垂直命名入口、讲稿导出交付物、风格可发现性。全部沿用
P0 纪律：不削弱任何治理门、避开并行会话在途面、逐项独立可验证。

## 变更面（四项 P1）

### P1-A 交付档案（delivery profiles）

- 存储：`${LEO_PPT_HOME}/profiles/<名称>.md`（与 `styles/`、`brands/` 同构的
  用户档案第三通道；不修改 Skill 安装目录）。
- 字段（封闭集合）：audience / scenario / page_count_policy / duration /
  data_classification_default / density / preferred_style（可选）。**只存偏好，
  绝不存业务数据**（材料数字、客户名、项目名不入档）。
- 合同行为：合同冻结轮若存在点名 profile（或唯一 profile 提及），合同草案
  按档案预填并逐项标注"来自交付档案 <名称>"；用户只确认差异项；**档案不豁免
  任何确认语义——数据分级与答辩档位仍须明示确认**（分级是安全门）。
- 保存：用户要求保存偏好时落盘；`scripts/check_delivery_profile.py` 做结构
  校验 + 业务数据启发式告警（数字+单位、%等模式 WARN）。
- 新用例 `delivery-profile-contract-advisory`（advise 档，测合同知识与不豁免
  语义，不依赖沙箱文件态）。

### P1-B 学术模式命名入口（academic vertical）

- 新 reference `references/academic-vertical.md`：入口信号（论文/答辩/组会/
  文献汇报）、用户一句话入口（"学术模式"）、既有合同的一条龙映射——合同
  三字段（math_load/figure_orientation/section_priority）+ 答辩档位询问
  （minimal vs dense-defense）→ 大纲（RST 可用）→ 母版图证据行/六种处理模式
  → 风格默认推荐（科研答辩风）→ 样张锚最典型难页 → 交付含公式/图 provenance。
  **纯整合既有合同，不新增确认门。**
- SKILL.md 按需读取表 generate 行与 CONFIRM-GATE 学术句补"学术模式"入口
  指认；advise Route 表不变（学术仍是 generate 路线上的垂直档）。
- 新用例 `academic-vertical-entry`（execute 首轮：三字段+档位询问在场）。

### P1-C 讲稿导出（speaker notes export）

- 新脚本 `scripts/export_speaker_notes.py`：从成品 PPTX notes（python-pptx，
  runtime 依赖树内）或逐页母版导出讲稿 markdown（页序、标题、speaker_script、
  时长）；缺 notes 页如实列出，不编造。确定性输出。
- 合同锚点：image-deck-workflow 交付节 + SKILL.md 交付披露一句。
- 新用例 `speaker-notes-export-offered`（advise 档，测知识在场与诚实边界）。

### P1-D 风格画廊（style gallery）

- 新脚本 `scripts/generate_style_gallery.py`：从 `00_索引/_INDEX.md` 确定性
  生成 `samples/style-gallery.md`（11 内置风格一句话定位 + 六轴计数 + 指向
  总索引），README 成品样例节链接。**不放 00_索引 目录**（避免 lint_style_index
  计数漂移）。

## 明确不做

- 不改 runtime/CLI 代码（profiles 走合同+脚本层，与 brands 模式对齐）；
- 不做 HTML/PDF handout 导出（渲染依赖属 M1 渲染 lane 后续）；
- 不生成风格缩略图（需图像 API，成本与确定性不成立，仅做目录级画廊）；
- 不动 M1 已合入的 render lane / layout bank / sources manifest 面。

## Verification Contract

1. 新增单测三个脚本各自全绿；全量单测相对当前基线（M1 后口径）零新增失败。
2. 五条 lint（含 M1 新增 lint_render_templates）全部 exit 0。
3. `skill-up validate evals/eval.yaml`（80+3 case）全部解析通过。
4. 三个新用例在线复测通过；子集含既有相关用例（alpha-m0-contract-academic-
   fields、confirmation-batched-turns、control-plane-blocked-summary）无回归。
5. 结果记入 evals/known-issues.md 本批条目；CHANGELOG 同步。

## 执行记录

- 调研澄清：`~/.claude/skills/leo-ppt-generator` 为指向仓库工作目录的 symlink，
  评测引擎读实时树；P0 批"安装副本顺带同步"的推断据此修正。
- 单测：新增 19 例全绿；全量 391 tests / 2 failures（在案金样存量）。
- 在线：子集 8/8 PASS（it-91 + it-93）；alpha-m0-contract-academic-fields
  判官两轮校准（全局延迟姿态豁免 + 场景限定计入边界意识），it-89/91/92
  重放 PASS、it-93 在线绿。
- 全量 83 case 轮（it-94）：57/26/0。归因：17 例 M1 新用例首次在线校准
  （M1 自留工作面，抽查三例均判官误杀健康回复）、8 例在案摆动轮转、1 例
  本批 confirmation-batched 判官引号族缺口（扩词 + it-86..94 全历史重放 +
  it-95 在线复绿）。P1 有效口径：零行为回归；control-plane 连续三轮绿。
- 验证合同 1–5 全部关闭；结果详录 evals/known-issues.md 本批条目。
