# PPT 执行流程优化与验证记录

日期：2026-09-06。范围：`leo-ppt-generator` 的交互、内容变更、样张恢复与推荐流程。

本轮在已完成的风格索引实施基础上追加修复，不改写旧验收记录或将历史测试算成本轮结果。
目标是减少无必要等待、避免内容与页面失配、使样张决策可恢复，同时保留费用、事实和人工验收边界。

## 1. 多角色取舍

| 角色 | 建议 | 实施取舍 |
| --- | --- | --- |
| 产品与用户体验 | 减少重复确认、提前暴露能力与费用范围 | 默认委托执行，共创按里程碑；重要事实、范围、额外费用和真实人工验收仍单独核对 |
| 执行可靠性 | 决策有依据，输入漂移不能复用旧样张 | 沿现有 image CLI 加收据，prepare 与组装消费；不另建工作流引擎 |
| 内容与演示质量 | 修复内容传播，按页面角色验证 | 完整页块差异先纳入复核，优先生产已有计划中的高差异页，不普遍增加图片 |

审阅与实施分开：产品角色提出并部分修改交互入口；内容角色修复影响分析；可靠性角色实现样张收据及 CLI。主 Agent 完成版本提交、引用/评测同步、交叉核验及回归。期间子任务出现过限流，已完成的文件保留并由后续执行接续，没有把失败 turn 视为完成证据。

## 2. 已落地变化

| 问题 | 最终行为 | 主要实现 |
| --- | --- | --- |
| 明确委托仍重复询问 | 按任务与已有授权推进；明确暂停和未消解的暂停/启动冲突保持咨询 | `SKILL.md`、输入与图片式工作流 |
| 页数默认意外增加 | 未说正文时默认成品总数，封面与收尾从总数内分配 | 图片式工作流、页数行为用例 |
| 正文反转仍零影响 | 页块、合同、页序、增删页、数字/术语和引用闭包共同确定范围 | `scripts/compute_impact.py` |
| 协作写入先检查后覆盖 | 在共享文件锁内比较调用者的旧 hash，原子发布候选并更新基线 | `scripts/check_content_baseline.py --commit` |
| 样张批准无法恢复 | 记录具体图、内容、视觉、布局、backend、尺寸、方法及决策来源 | `application/sample_decisions.py` |
| 只有说明、没有执行检查 | prepare 冻结前后及 assemble/finalize 前实际核验已有样张收据 | `runtime/src/leo_ppt_generator/cli.py` |
| 单家族锁定与多样性互斥 | 合格集合优先，允许单家族或单候选，不为配额引入错配 | `references/style-recommendation.md` |
| 固定三点和点数路由不适配 | 三点降为建议；低点数精确图表也走原生路线 | 图片式工作流与入口摘要 |
| 一张样张被视为验证整套 | 明示角色覆盖，优先验证已计划中的高差异页 | 风格推荐与图片式工作流 |
| 状态回复技术信息过多 | 普通回复结果先行，诊断保留机器合同，用户指定 JSON 时不追加叙述 | `SKILL.md` |

## 3. 运行合同

内容写回使用 `--record` 建立初始基线，编辑独立候选后执行：

```text
python scripts/check_content_baseline.py --commit <目标> --candidate <候选> --expected-sha256 <编辑前hash>
```

`--verify` 仅供诊断。并发协作写入使用同一锁，旧版本只能一个胜出；冲突不自动采纳最新版本覆盖。外部编辑器不遵守此锁，因此不宣称消除任意外部编辑竞争。目标发布后基线更新失败会留下漂移，后续停止而不是假报成功。

样张审查后使用 `image sample-record`，新流程的 `image prepare` 传 `--sample-binding`；恢复使用 `image sample-verify`。已有收据在不带参数时仍会核验，历史从未启用的任务返回 `legacy/not_run`。启用记录 `sample-decision-required.json` 防止误删收据后退回 legacy。重新决策需传 `--supersedes <旧收据文件hash>`，历史字节原样保存；返回指纹绑定同一验证快照，并发替换报告冲突。

完整命令、六字段 binding 和授权引用规则见[执行合同](../../leo-ppt-generator/references/execution-contract.md)。`user-delegated` 不等于人工确认，收据也不是发言人认证或最终人工视觉验收。

## 4. 验证账本

- 系统 Python 初跑：1264 项，3 failures、33 errors；原始日志保留。根因包括缺少 `jsonschema`、`markdown_it`、Playwright/栅格依赖和测试包导入路径，没有据此修改业务源码。
- 使用已有测试虚拟环境、包级目录与正确 `PYTHONPATH` 重跑：1296 项通过，0 failures/errors/skipped。之后的样张历史保真、损坏恢复与判据调整另跑最终定向集。
- 样张收据最新定向检查：15 项通过，包括实际图/内容/backend/尺寸/方法/视觉漂移，freeze 前后竞争，组装前漂移，损坏恢复，历史字节和非 16:9 拒绝；独立交叉审查追加了已启用后丢收据禁止 legacy、并发重决策禁止混合快照两项回归。
- 内容影响分析：22 项通过；内容基线提交：13 项通过，含两个实际并发进程只有一个旧版本提交成功。
- 四项 lint 通过；brief 318，错误与未登记 warning 均为 0；版式保留 3 项已登记存量豁免；索引一致性错误 0；治理错误与 warning 0。
- 系统 `skill-creator` 结构验证通过；skill-up 配置验证通过，共 98 个已登记用例。
- 真实 Agent 首轮规则矩阵：七项判断均正确，但追加叙述使严格 JSON 失败；修复指定格式优先级后复测通过。
- 第二轮四项真实 Agent：2/4 通过；明确暂停被误执行、委托被扩大为未来所有事项免确认，两项按真实答复修复，原始失败保留。
- 最终定向集 89 项全部通过（样张15、基线13、影响22、Judge25、交付收据14）；9份流程文档链接检查通过，`git diff --check` 通过。
- 八项真实 Agent 回归结果为 7 PASS、0 FAIL、1 ERROR：页数用例按 15 页推进后继续进入风格与容量预检，在 300 秒超时。保留该轮原始结果，不将超时计为通过；页数用例补充止于回复大纲的交付边界，判据保持不变，单独复测另列。
- 页数单独复测：1 PASS、0 FAIL、0 ERROR；明确成品 15 页包含封面、正文和收尾，并止于大纲。八个目标行为均已有通过证据，但没有单轮 8/8 通过结果，不将不同轮次合并为稳定性统计。

包级命令（从技能目录运行；原使用任务隔离工作区的 Python，该工作区已随 2026-09-11 清理移除，`<python>` 为任一 Python 3.12 隔离环境）：

```sh
env -u LEO_PPT_BUNDLE \
  LEO_PPT_RUNTIME_PYTHON="<python>" \
  PYTHONPATH="$PWD/runtime/src:$PWD" \
  <python> -m unittest discover -s tests -t . -p 'test_*.py'
```

真实 Agent 最终回归命令（从技能目录运行）：

```sh
skill-up run evals/eval.yaml \
  --include-case-name workflow-policy-matrix \
  --include-case-name mixed-advise-execute-advise-wins \
  --include-case-name execute-keeps-confirmation-gates \
  --include-case-name page-count-ambiguous-asks \
  --include-case-name advice-only-no-execution \
  --include-case-name missing-multi-page-workers \
  --include-case-name partial-hybrid-without-confirmation \
  --include-case-name delivery-acceptance-pending \
  --parallelism 1 \
  --output-dir <workspace>/evals-final
```

页数用例明确交付边界后单独复测：

```sh
skill-up run evals/eval.yaml \
  --include-case-name page-count-ambiguous-asks \
  --parallelism 1 \
  --output-dir <workspace>/evals-page-count-final
```

真实 Agent 使用现有 `claude_code` 引擎及其已配置模型；日志显示 `glm-5.3[1m]` 的模型识别 warning，不将它称为 GPT-6 实测。评测用例验证交互决策与执行边界，不等于真实图片质量实验。

## 5. 证据与边界

本地生成证据原存 git-ignored 工作区（已于 2026-09-11 清理）：`package-tests.log` 保留初始环境失败，`package-tests-final.log` 为通过结果，`focused-final.log` 为最后定向集；`evals-focused/`、`evals-regression/`、`evals-final/`、`evals-page-count-final/` 分别保留原始行为轮次与页数单独复测。最终以各轮 `result.json` 判断，不合并不同轮次凑通过率。

当前仍保守绑定整套 slides；内容改版使决策失效，已 prepare 的 run 内容仍不可变，应建立新 run。完整 brief 的非视觉文字变化也可能扩大失效，优先绑定实际视觉投影。运行账本的其他手动接线未被本次全部自动化。

没有进行全库真实图片 Provider 对照、实际投屏/人工审美实验或生产用户耗时统计；不声称已证明整体更快、更省钱或审美更好。语义 ranker、MMR、稳定 style ID 与物理目录迁移仍未纳入。本次未提交、推送、发布或主动刷新安装 runtime。

页数复测的答复仍出现从有限经营数字推导“价值驱动”“打法可复制”等未经充分支持的结论；本次页数 Judge 不验证因果与商业结论。这是尚未关闭的内容质量缺口，后续应增加基于原始证据的论断核验，不能将本轮行为通过外推为叙事事实质量达标。

面向用户的详细说明见[执行流程](execution-workflow.md)。
