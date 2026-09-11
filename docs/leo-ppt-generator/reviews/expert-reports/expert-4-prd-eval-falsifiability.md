# 专家报告 4 · 质量与评测（可证伪性与评测接线）

- 评审对象：`docs/prd/2026-09-11-leo-ppt-capability-improvement-prd.md`（v1.0）
- 立场：验收标准可证伪性、样本量与基线方法学、评测接线（单测/evals/真实 run/人工判读）
- 日期：2026-09-11 · 独立盲评 · 已抽查 leo-ppt-generator/evals、tests、scripts 现状

## 总体结论

**有条件通过。** PRD 自我定位（"验收标准是完成判据不是已实现声明"）正确，R-75 闭环复检、R-81 先决如实标注、R-73 未达标停 WARN 等设计扎实。但抽查后确认：**P0 头号条目 R-70 的两大核心判据一个分子不可计算（TF-1 无结构化记录）、一个无判读协议（盲评）**；多条验收依赖尚不存在的 ground truth 或超出 evals harness 已自证的能力边界。

**通过条件**：
- C1（D-1/D-2，阻断 R-70）：TF 触发数据源审计与基线建立方案列为 R-70 显式先决；消除与 R-77"无新埋点"的表述冲突；
- C2（D-3）：补盲评判读协议（可复用仓库 adjudication 先例）；
- C3（D-4/D-5）：修正 R-73 样本量论证与 R-74 ground truth 表述；
- C4（D-6/D-11）：每条验收标注测试入口类型（单测机判 / evals 政策 proxy / 真实 run 留痕 / 人工判读协议），proxy 不得宣称行为级证据。

## Findings

- **D-1 [blocker] R-70/R-77 必须修改**：TF 触发率分子不可计算——`record_run_step.py` step 枚举仅 `prompt/backend/qa/record/receipt`，TF-1 不是 step；reason-codes 仅登记 TF-2 的 `text_fallback_engaged` 与 `text_budget_exhausted`，TF-1 触发淹没在 qa attempt 计数里与普通 QA 失败不可区分。且 R-77 验收"无新埋点"与"TF 触发率成为指标"直接矛盾。→ 先做 TF 事件结构化审计：新增 TF-1 reason code/结构化字段（并修正 R-77 表述为"无新增采集通道，允许补登结构化字段"），或诚实收窄为"TF-2 触发率（可计算）+ TF-1 以 qa 重试分布近似（口径披露）"。
- **D-2 [blocker] R-70 必须修改**："较基线下降 ≥90%"无基线路径与统计效力——①历史 run 存量是否有、页数/事件数够否未盘点；②"既有 evals 回放建基线"不可行（evals 是政策 proxy，不产生 TF 数据；E2E 重放需 Provider 环境）；③优先级倒挂（P0 依赖 P1）。→ 基线盘点列为先决；规定最小样本量（基线事件 ≥20~30）与对比口径（同 backend 版本/同任务集/95% CI），明确判定用 CI 下界还是点估计。
- **D-3 [major] R-70 必须修改**：盲评无判读协议（谁评/评什么/怎么盲/一致率/分歧裁决）。仓库有先例可复用：`evals/fixtures/content-quality-20industries/judge-side/adjudication-conflicts.md`（判读框架+失败形态清单+否定感知）与 `verify_industry_visual_matrix.py` 确立的"双评审 80% 一致率不可得时如实登记缺口、不伪造"纪律。单评审通过即转正违反本仓库自己的先例。→ 验收 3 展开为判读协议小节（≥2 人独立、维度操作化、失败形态例举、≥80% 一致或裁决留档），显式引用先例。
- **D-4 [major] R-73 必须修改**：样本量无声明力——10 红例 0 漏报的 95% CI 上限约 26%，20 干净页 0 误报 CI 上限约 14%；且同一校准集既调阈值又报验收指标（train/test 未分离）；OCR 输入是外部产物须冻结构 fixture 才可复现。→ 干净页 ≥60（CI 上限≈5%）或如实报实测与 CI；红例 ≥30 或披露置信上限；校准/验收分集或 k 折；明确页图来源与 OCR fixture 冻结方式。
- **D-5 [major] R-74 必须修改**：44 单元 fixture 实际不含 lane 标注（INDUSTRY_SEED 是行业→皮肤种子，ROLE_LAYOUT 是页角色→模板映射）——"人工既定选择"的 ground truth 不存在，属"把将来要建的当已具备"；且"不设硬阈"使验收 2 无 FAIL 条件。→ (a) 新建 lane 标注集为独立交付物，或 (b) 用历史真实 run 的实际 lane 决策回放对账；一致率设最小判读规则。
- **D-6 [major] R-71 必须修改（轻量）**：验收 4 行为级断言超出 evals harness 已自证能力（既有 case 自述单轮 E2E 超出测量能力，行为证据由合同文本与真实 run 承担）；"断言无网络请求"需指定断言层。→ 验收逐条标注入口（1/2/3 进单测；4 声明为政策 proxy + 真实 run 留痕补强）。
- **D-7 [minor] R-72 建议+质疑**：桌面人工验证无留痕协议（谁验/OS/Office 版本/留什么）；"等价"未定判据——仓库现成口径：`tests/boundary/test_object_builder_equivalence.py`（object_projection 投影相等 + validate_pptx passed，排除字节 diff）。→ 沿用 F1 投影口径并确认 chart 对象纳入投影 kind 覆盖（请实现方答辩）。
- **D-8 [minor] R-70 建议**：红例"手改文字层 → 拒绝"未指定注入点与拒绝者（image record 还是 receipt verify，先例 `gamma-m1-receipt-tamper-detects-stale.yaml`）；"合成产物必须纳入指纹链"应作为设计约束写入范围。
- **D-9 [minor] R-77/R-74 建议**：测试入口未分配——R-77 应全进单测（`tests/runs_fixture.py` 已有合成 run 工厂，空/中断 run 可直接造）；"只读"需落地为可断言形式（数据源清单常量 + 运行前后 hash 不变）。R-74 一致率需声明是一次性留痕还是可重跑测试。
- **D-10 [minor] R-79 建议**："色觉模拟下仅靠颜色断言"未定义判读器——`visual_qa.py` 现有机判仅空白/溢出类，"仅颜色"现状是 LLM 目视。→ 模拟变换进单测（确定性断言），语义判读走 evals 双判官+否定感知，PRD 承认 LLM 判读属性。
- **D-11 [minor] 全局 建议**：全局纪律未区分四类测试入口的证明力差异；本批大量核心价值落在 proxy/留痕/人工三类，不标注会让落地者用最便宜的 proxy 充数。→ 纪律追加"每条验收标注测试入口类型；proxy 不得宣称行为级证据；人工判读附协议；真实 run 登记 run id 与日期"。
- **D-12 [minor] R-83 质疑待答辩**：验收"清除先验后回退"依赖未规划的清除入口；"归因一句"的最小要素未定义（泛泛一句也算？）。→ 范围补清除机制；归因断言给最小要素并做否定感知。

## 一句话立场

治理嗅觉很好（分阶段诚实、先决未决不装懂），但 R-70 这个 P0 主条目的两条核心判据目前一条不可计算、一条不可裁决，外加 R-73/R-74 的样本量与 ground truth 缺口——补上四个条件之前，验收标准配不上它自己写下的"完成判据"四个字。
