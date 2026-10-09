# 内容感知版式选择优化计划

## 产品合同

- **目标用户：** 在本地安装 `leo-ppt-generator`、希望从内容生成可人工审核 PPT 的个人用户。
- **目标：** 让每页版式选择优先反映已冻结的页面表达关系、逐槽文字容量和整册叙事节奏，并在候选接近时诚实返回人工裁决信号。
- **非目标：** 不增加云服务、并发编排、向量检索、额外模型调用或 AI 图片审查；不改变人工对图片内容和审美的最终审核职责。
- **成功标准：** 相同输入可确定性复现；表达合同优先于关键词推断；长短文本、关系图和低分差候选能给出可解释结果；现有显式选择、资格门和双 lane 物化不回归。

## 当前依据

- `leo-ppt-generator/runtime/src/leo_ppt_generator/layout_selection.py` 已拥有硬资格池、`rank_page`、`allocate_deck` 与跨页节奏控制，是唯一应扩展的选择 owner。
- `content_projection.precompile_binding` 已验证关系、焦点、阅读顺序、事实及逐槽文字容量；重做平行校验器会造成第二真值源。
- `page_rank_signals` 当前仅投影角色、总条数和总字符数，使排序无法充分利用已验证的页面表达和槽位使用量。
- 2026-10-08 的当前 catalog 可解析 42 个 layout；`lint_layout_grid.py` 与 `lint_page_type_regime.py` 已通过。模板 contract lint 在项目 venv 下通过。

## 关键技术决策

1. **扩展而非新建排序器：** 在 `layout_selection.py` 中将表达投影和绑定容量摘要传入既有 `rank_page`。`content_projection` 仍是合同和硬失败的唯一 owner。
2. **分层排序：** 硬资格继续先于软排序；软排序依次考虑关系/阅读任务匹配、逐槽容量余量、角色与风格路由、叙事节奏。任何新分数不得绕过硬失败。
3. **置信度用候选分差校准：** 保留现有绝对门槛，同时暴露第一、第二候选分差；分差不足时 `decision=undecided`，不伪装为自动选择。
4. **本地人工审核保留：** 输出“为何推荐/为何不确定”的确定性证据，不导入视觉模型评分或自动审图。

## 实施单元

### U1：冻结表达投影

**文件：** `leo-ppt-generator/runtime/src/leo_ppt_generator/layout_selection.py`、相邻单元测试。

将 `relation.kind`、`reading_task`、`focus`、`reading_order`、`uncertainty` 及现有结构化表达投影为排序输入。缺失或 undecided 的页型优先从 v2 regime 的明确阅读任务或唯一关系映射补齐；有效的显式页型保留，避免 `independent` 等通用任务抹除指标、表格和系统关系的具体类型。仅轻量入口缺少表达时使用现有 `page_intent` 推断。非空 uncertainty 保留人工裁决。候选理由须显示证据来源。

### U2：逐槽容量适配

**文件：** 同上。

从已生成 binding 的 `text_capacity` 摘要建立执行候选级容量余量读数，按完整 execution identity 隔离同 layout 的不同绑定。比较已有字数上限的标题和文字槽，避免用总字符数把不等价页面视为相同。满载但未溢出的候选降权；硬溢出继续由资格门排除。没有字数上限或没有摘要的要点数组保持中性，既有条数资格门继续生效；本期不新造字数容量声明或改动绑定 owner。

### U3：整册选择置信度与节奏

**文件：** 同上。

在候选结果中写入 `score_margin` 和确定性原因。将连续同教学任务或同数据口径的页面识别为可重复结构的上下文，保留章节切换、核心论点页的去重惩罚。显式选择仍为硬约束。

### U4：测试与用户可见说明

**文件：** 对应 `leo-ppt-generator/tests/`、`leo-ppt-generator/references/style-recommendation.md`、`CHANGELOG.md`。

消费者版本校验同步修改 `content_projection.load_run_binding` 和 `tests/test_deck_projection_view.py`，接受当前策略并保留已有冻结 v2 输入，未知版本仍拒绝。这两处在修改前无既有 dirty 改动。

新增真实内容形态测试：对比、流程、关系页、长标题/短要点、低分差候选、同类连续教学页、显式选择和两个 lane。更新用户说明，说明推荐是确定性结构判断，图片和审美仍由人工审核。

## 验证合同

1. 在项目环境执行 `PYTHONPATH=runtime/src runtime/.venv/bin/python -m unittest discover -s tests -p 'test_*layout*py'` 及关联 expression/content/binding 测试。
2. 执行 `PYTHONPATH=runtime/src runtime/.venv/bin/python scripts/lint_template_contract.py`、`runtime/.venv/bin/python scripts/lint_layout_grid.py`、`runtime/.venv/bin/python scripts/lint_page_type_regime.py`。
3. 执行完整 `PYTHONPATH=runtime/src runtime/.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`，保存可信退出码与日志。
4. 验证仅覆盖确定性结构和导出合同；不将测试结果表述为真实 Provider 成功、人工视觉验收或用户收益。

## 风险与边界

- 不修改 generated mirrors、catalog 数据结构、资格语义或表达 schema，降低与既有 expression-first 迁移工作的冲突风险。
- 当前工作树已有未提交改动；实施仅写入本计划明确列出的文件和根 `CHANGELOG.md`，并在提交前重新核对 diff。
- 实施复核将“冻结表达优先”细化为补齐缺失语义并保留显式具体页型；将“逐槽容量”限定为已有 binding 的真实声明。此调整避免第二页型映射或未经声明的要点字数假设，不扩大本地产品范围。
- 风格/预设是否适配整稿仍依赖其已声明的能力和人工样张；本期不会把 `draft` 资产升级为已验证资产。

## 完成定义

U1-U4 已实现；新增用例覆盖上述内容形态并通过；现有完整测试通过；变更记录更新；最终报告明确区分代码机制验证与人工视觉、Provider、用户收益的未验证边界。

## 执行结果

U1–U4 本期开发与约定验证已完成。最终全量 `Ran 2436 tests in 1111.172s / OK / exit 0`；修复后的关联 51 项测试、compileall、template/layout/regime lint 和 `git diff --check` 均 exit 0。

逐项文件、符号、实现证据、命令、结果、源码哈希与限制见 [交付记录](../../leo-ppt-generator/workspace/content-aware-layout-selection/completion.md)，完整脱敏日志见 [full-suite.log](../../leo-ppt-generator/workspace/content-aware-layout-selection/full-suite.log)。本结论仅覆盖内容感知版式选择，不代表历史迁移全部完成或真实图片 Provider、人工视觉、用户收益已验证。未提交、推送或创建 PR。
