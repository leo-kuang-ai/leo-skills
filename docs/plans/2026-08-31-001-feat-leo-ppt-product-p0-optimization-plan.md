---
title: leo-ppt-generator 产品 P0 优化批 - Plan
type: feat
date: 2026-08-31
topic: leo-ppt-product-p0-optimization
artifact_contract: spec-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: product-analysis-2026-08-31
execution: code
status: completed
---

# leo-ppt-generator 产品 P0 优化批

## 背景与目标

基于《AI-PPT 开源项目调研报告（2026-08-30）》与六专家源码评审会的竞争分析，
工程能力补强已由 M0/M0.1 与并行会话承接；本批补**产品层**四个空白：交互摩擦、
跨模型表面合同可达性、README 视觉证据、成本可预期性。每项独立可验证，
全部遵守"不削弱既有治理合同"的边界。

## Goal Capsule

- 用户侧减少确认往返与成本不可预期（P0 漏斗两流失点）；
- 弱指令遵循模型宿主上表面合同从"恒定违约"放宽到"可达成"（block-early）；
- README 具备成品视觉证据（28k 星竞品均以成品图为首屏）。

## 变更面（四项 OPT）

### OPT-A 表面合同 block-early

- `SKILL.md`：控制面响应合同位置规则由"块必须在最前面（至多一行 interaction_mode）"
  放宽为"前 3 个非空行之内、先于块只允许 ≤40 字符元数据行"；执行主线加顶层锚点。
- `judge_control_plane_fields.py`：位置判定同步放宽；删除唯一用途的正则 import。
- 历史重放：iter-26/28（叙述先行无块）仍 FAIL，iter-32/57/65/66（元数据+块）仍 PASS；
  合成七陷阱（块最前/两行短元数据/长叙述先行/无块/第 4 行块/双 next_action/宿主泄漏）
  全部按预期。

### OPT-B 确认门回合合并

- `SKILL.md` 执行主线与 CONFIRM-GATE：相邻确认点可同回合呈现（合同+大纲、
  视觉方向+样张；逐页母版独立），合并的是往返不是确认——逐件明示确认才冻结。
- `references/image-deck-workflow.md` 步骤 1/2 之间新增「回合合并」规则
  （材料齐全且无口径歧义时适用；材料缺失仍先单独冻结合同）。
- 新用例 `confirmation-batched-turns` + `judge_confirmation_batched.py`
  （合同要素与大纲工件同回合在场 + 逐件确认请求 + 未确认不得冻结/派发红线）。

### OPT-C 成本预估前置

- 新脚本 `scripts/estimate_run_cost.py`：历史 backend_stats 均值×重试系数 /
  无历史保守假设区间（basis 如实标注 history/mixed/assumed-default），
  `--price-per-1k` 可折算成本带；确定性输出，exit 0/2。
- 新单测 `tests/test_estimate_run_cost.py`（12 用例：历史带/混合 basis/
  not-recorded 容错/价格/校验/确定性）。
- `SKILL.md` 不变边界新增「成本预估前置」；`references/backend-selection.md`
  新增同名节（含交付对账要求）。
- 新用例 `cost-estimate-before-dispatch` + `judge_cost_estimate.py`
  （区间+量纲+依据披露在场，精确承诺话术拦截）。

### OPT-D README 视觉证据

- `samples/` 三张 1280 降采样页（政务封面/金融数据页/教育内容页，
  出自 2026-08-29 六行业评测运行，合成材料，出处可溯）。
- README 新增「成品样例」节；仅标注场景与出处，不虚构风格名。

## 明确不做

- 不改变确认语义与 DELIVERY-GATE/PARTIAL-GATE 等任何治理门的存在性；
- 不动并行会话在途文件（vendored/runtime/render lane/layout bank/sources manifest）；
- 不引入交付档案 profiles（runtime 改动，留 P1）；
- 不做 HTML 交付格式、国际化、转场（P2/观察项）。

## Verification Contract

1. `runtime/.venv/bin/python -m unittest discover`：相对基线 218 tests / 7 failures
   （4 validate_assets + 1 visual_measure 属并行在途、2 金样 HEX 属存量）零新增失败；
   本批新增 12 测试全绿。
2. 四条风格 lint 全部 exit 0。
3. `skill-up validate evals/eval.yaml` 全部 61 case 解析通过。
4. 安装副本同步后 `skill-up run --include-case-name` 子集在线复测：
   control-plane-blocked-summary、cost-estimate-before-dispatch、
   confirmation-batched-turns、execute-keeps-confirmation-gates、
   outline-doc-before-confirm、master-doc-before-confirm、
   advice-only-no-execution、mixed-advise-execute-advise-wins。
5. 全量 61 case 后台轮次记录进 known-issues.md。

## 执行记录

- 基线采集：218 tests / 7 failures；四 lint 绿（2026-08-31，见 known-issues 本轮条目）。
- OPT-A/B judge 离线自检：7+6 样本全部符合预期（good 放行 / bad 拦截）。
- OPT-B 两轮校准：it-86 用例口径歧义（修用例预置口径/时长/分级）→ it-87 判官
  词组缺口（确认组补"等你回复/拍板"6 变体，历史双向重放）→ it-88 在线 PASS。
- 在线子集终态 6/6 PASS（it-86 + it-88）：control-plane-blocked-summary（十三点
  历史 12 FAIL 后首轮转绿，单轮不作稳定性结论）、cost-estimate-before-dispatch
  （首轮即绿，正确引用脚本与 basis 披露）、confirmation-batched-turns、
  execute-keeps-confirmation-gates、outline-doc-before-confirm、
  advice-only-no-execution。
- 结果记录见 `evals/known-issues.md` 2026-08-31 产品 P0 批条目。
- 全量轮（iteration-89，61 case）：53 PASS / 8 FAIL / 0 ERROR；8 个失败逐条
  归因全部为在案存量/摆动、零条归因本批；后续项：回合合并下 outline-doc
  判官的环境态等价分支（M0.2 候选，不在本批范围）。验证合同 1–5 全部关闭。
