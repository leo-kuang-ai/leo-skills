# 源码考古 SRC-4 · 测试与评测基建

- 对象：tests/ + evals/ + verify 脚本 · 方法：全文通读关键文件 + 目录全量清单
- 已完整读取：tests/runs_fixture.py、tests/boundary/test_object_builder_equivalence.py、scripts/verify_industry_visual_matrix.py、verify_html_deck_e2e.py、verify_image_deck_e2e.py、visual_qa.py、evals/eval.yaml、evals/fixtures/scripts/ 判官体系（99 个 judge_*.py 清单+judge_common.py 全文+judge_content_common.py 全文+judge_dual_judge_rubric.py+judge_style_index.py）、content-quality-20industries/judge-side/、template-quality/skill-up-registration.json、tests/render/ 与 evals/cases/ 目录清单
- 日期：2026-09-11

## Q1 · 盲评 fixture 化现成度（R-70 验收 3）

现有判官机制六层：①style_index judge（轨迹白名单，唯一在 evals/judges/）；②通用否定感知判官群 **99 个在 evals/fixtures/scripts/**（judge_common.py:13-17 22 词否定表 + positive/forbid_positive）；③双评审官档（judge_dual_judge_rubric.py:49-53）；④**VLM 双判官引擎**（judge_content_common.py：A1–A5 五维度含 steps+failure_forms 失败形态清单 30-186；匿名化包 ANON_FILE_MAP 265-329；双模型家族 claude -p --model glm-5.3 + codex exec 349-378；维度级仲裁 550-558；"无证据 pass 无效"判 error 451-455）；⑤判读协议先例（judge-side/adjudication-conflicts.md 物理隔离+失败形态清单+共同评分规则）；⑥校准纪律（industry matrix 合格+注入缺陷逐类 100% 检出；skill-up 判官回放三源+咬合验证 11/11）。

**离组合页盲评的差距**：现成——双判官调用引擎（含费用登记/重试/原始尝试留存）、匿名化、失败形态 schema、judge-side 隔离约定、L2 校准阈值先例（protocol.json:86）、人工一票否决登记格式（semantic-review.json）。**需新建**——(a) **图片输入通道**（judge_content_common.py:332-342 只读文本拼 prompt，call_model 纯文本 stdin，无 VLM 图入）；(b) 视觉维度判据（A5 仅合同层，无融合度/整体性维度）；(c) 图片匿名化先例无；(d) 校准缺陷类型是渲染闸缺陷非组合质量缺陷。**judge-side/defect-controls/ 在 README 登记但物理不存在**。

## Q2 · runs_fixture（R-77 单测地基）

`make_run()`（:34-55）合成 9 类工件对齐生产写侧契约：run.json（progress 全字段，可写坏 JSON）、slide_jobs/page_jobs、timing.json（键名对齐防合成契约漂移）、events.ndjson（可注入坏行）、backend_stats.jsonl（render lane tokens=0）、run.log、final/deck.pptx+validation-summary（六门）、页 PNG（Pillow 纯色）+ `render_pages` 参数走 render/ 路径混排 lane。**空 run**（参数化 total=0）/ **中断 run**（默认 in_progress+failed/timeout/active 参数）直接支持；**带 TF-2 标记的 run 不支持**（无 text_fallback 参数，需扩展一个注入参数）。消费者：test_runs_console.py、test_config_web.py（HTTP API 集成）。

## Q3 · R-84 落点（evals schema）

case schema 18 行模板（id/title/description/input.prompt/constraints/judge.script_path/collect_artifacts）；引擎 claude_code，defaults timeout 300s/max_turns 4/parallelism 1，注册 119 case。判官三类：文本否定感知（112 例 judge 10s）、轨迹白名单（6 例 600s/12turns）、边界门+离线双判官（20 例 3600s/48turns，内联 judge 查停止点，YAML 明示"harness 通过≠内容达标"）。**图表直接判据用例仅 3 个**（stat-chart-gating / alpha-m0-figure-evidence-row / gamma-m1-mermaid-values-verbatim）；内容质量体系内仅 A5.2 一条子判据涉图表。**R-84 接入成本低**：每例＝1 yaml+1 judge_*.py（复制否定感知模式）+eval.yaml 注册行；受 content-quality 冻结纪律约束时需新协议版本。

## Q4 · 回放集/基线设施

verify_image_deck_e2e **走真实付费 Provider**（ark backend create+6 次 generate 硬断言）；verify_html_deck_e2e 零 Provider。四套 fixture 化基线已存在：html-deck-e2e（冻结设计+6 页+收据）、image-deck-e2e（真实付费 6 页+prompts+收据）、render-theme-baseline（7 模板×3 档=21 页含 sha256+复现命令+git 状态）、deck-style-matrix/industry-visual（9×4×2 与 44×3×2 页+semantic-review）。**限制：均为模板/设计级，"固定母版"回放集不存在**（R-70 指标宣称所需形态无现成物）。

## Q5 · 测试入口类型现实

单测 ≈146 文件（顶层 110+boundary 20+render 14+installer 2）；evals proxy 119 case+bench 8；run 留痕 6 个 verify 脚本；人工协议 ≥4 处（semantic-review caveat、adjudication-conflicts、protocol L2 ≥75%、review_gap"不伪造"纪律）。harness 实际限制：6 例 300s 超时 ERROR 未复测；glm-5.3 触发 [claude-code:unrecognized_model] 告警；付费生成需显式授权；content-quality 判官费用上限（judge_calls ≤260/500 元）。

## PRD 验收可满足性核对表

| 验收项 | 状态 |
| --- | --- |
| R-70 盲评双层评审 | **半现成**：文本双判官引擎/匿名化/失败形态/校准全有；图片输入通道+视觉维度判据需新建 |
| R-70 单测（白名单/指纹/旧 run） | 现成组件齐（REQUIRED_TEXT 断言先例、指纹链测试模式、runs_fixture） |
| R-70 回放集 TF 降幅 | **受限于回放集不存在**（固定母版形态需新建）+TF 结构化登记前置 |
| R-71 成册预览单测 | 需新建（tests/render 现仅单页） |
| R-71 SAMPLE-GATE evals | 现成先例（sample-gate case+judge 已注册） |
| R-73 校准集 | 模式现成规模需扩（industry 校准仅 12+10）；阈值登记纪律可套用 |
| R-77 单测 | **现成**（runs_fixture 即所指工厂；只读断言先例在） |
| R-84 用例集 | 低成本接入 |

## 意外发现

1. judge 脚本主体在 evals/fixtures/scripts/（99 个），evals/judges/ 仅 1 个——目录命名误导；
2. judge-side/defect-controls/ README 登记但物理不存在——盲评 defect-controls 不能假设已存在；
3. 双判官双家族依赖外部 CLI（claude -p/codex exec），glm-5.3 有引擎识别告警——VLM 判官选型继承此风险；
4. 判官校准已有"回放三源+咬合验证"方法论（不扩词纪律），可作盲评判官校准模板；
5. 诚实登记文化是硬约定（review_gap/caveat/honest_notes）——人工否决留痕有可抄格式；
6. runs_fixture 曾因合成契约漂移掩盖读侧缺陷——扩展 TF-2 标记须保持"对齐生产 writer"纪律；
7. evals 超时是活跃问题（6 例未复测），R-84 生成型 case 需显式大 timeout。
