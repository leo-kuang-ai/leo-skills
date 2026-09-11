# 评审报告 R4 · 测试评测域（源码复核）

- 对象：PRD v1.4 §1.5 第 5/6/7 条、R-70 验收 2/4、R-77 验收 1、R-84 · 方法：源码与 fixture 全文通读
- 通读：judge_content_common.py（655 行）、judge_common.py、judge_dual_judge_rubric.py、judge_style_index.py、runs_fixture.py（256 行）、verify_industry_visual_matrix.py、verify_html_deck_e2e.py、verify_image_deck_e2e.py、visual_qa.py、eval.yaml、judge-side/ 全目录、protocol.json、build_cases.py、freeze_render_theme_baseline.py、tests/render/ 清单
- 日期：2026-09-11

## 断言验证（摘要）

9 项全部确认：盲评"图片通道与视觉判据需新建"✓（call_model 双通道均纯文本 stdin；render_package_text 二进制必乱码；A1–A5 全文本维度）；defect-controls 物理不存在✓（且 protocol status 仍 development/0.3.0-dev——属 M0 设计产物非遗失）；四套 fixture 均非母版级✓（两 e2e 硬编码 PAGES、industry 硬编码内容、render-theme 为模板×档）；R-84 低成本✓（17–18 行模板＋11 行 judge＋注册行；图表直接判据 3 个口径成立）；冻结纪律可绕开✓（冻结域仅 20 单元，新家族 case 不入协议域）；runs_fixture 支持✓（**部分修正**：render 页型参数 render_pages 已存在，真实缺口仅 TF-2 标记与空 run 断言层）；timeout 事实✓。

## 需求级判断（摘要）

1. **盲评图片通道工程量＝中等改造**（非全新管线也非 18 行）：可复用——verdict/重试/落盘/仲裁（模态无关）、匿名化是 copyfile（图片可搬）；需新建——call_model 视觉通道（claude -p 需 stream-json image block＝重构消息结构；**codex exec 图片能力仓库零先例**＝双家族齐改主要不确定点）、双模态 render_package_text、视觉维度规格＋**评分制 schema（现为四态 pass/fail/not_applicable）**。备选：独立多模态判官直连 GLM-4.5V（anthropic 兼容端点带 image block），家族多样性落在另一判官或人工辅证（protocol 先例支持）。建议判官通道 spike 前置。
2. **回放集最小构造判 M**（PRD 记 L 偏保守）：母版与 required_text 从 u19 硬编码改造；html lane 页图零成本＋image lane 一次付费冻结（"最低 6 张"先例）；run 层 runs_fixture 骨架；**新建仅两项**——TF 事件标注（依赖 R-77 先决）＋母版→PAGES 转换。缺陷植入构造器可平移 verify_industry_visual_matrix 的 run_calibration；冻结纪律可平移 freeze_render_theme_baseline 的 manifest hash＋--check。
3. R-84 成本口径应分开：负例适配现成否定感知 judge；正例是语义判定，需 L1 双判官或人工协议。

## Findings

R4-1 [中] README 登记 adjudication 三文件实为单文件三节（漂移清单补录）；R4-2 [中] runs_fixture 措辞修正（render 页型已有）；R4-3 [中] 判官选型风险未登记＋评分制 schema 扩展；R4-4 [低] R-84 正负例成本口径分开；R4-5 [低] defect-controls 构造范式线索补附录；R4-6 [info] 图表用例计数口径成立。

## 结论

**通过**——核心声明全部源码证实、无虚报；四项条目级修订建议随 v1.4.1 吸收。
