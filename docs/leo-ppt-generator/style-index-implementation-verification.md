# 风格模板治理与精准索引实施验收

日期：2026-09-06。对应[统一方案](../plans/2026-09-05-002-feat-leo-ppt-engineering-optimization-plan.md)。

当前结论：**本期 U0、U1、U5、U2、U3、U6、U4 的实施与约定验收均完成。** 包级测试 1270 项通过；末次 Judge/轨迹定向测试 26 项通过。最终 `evals-scope-final` 原始 Judge 30/32，两项措辞误报修复后对同一轮全部回答统一重评 32/32，咨询轨迹 27/27，联合通过 32/32。未跨轮拼接通过结果。完整资产差异、原始状态、重评判官哈希、轨迹和最终技能源码哈希见[机器可读验收证据](evidence/style-index-verification.json)。

完成仅指本期约定开发范围，未提交、推送或发布；语义排序、全库视觉还原及业务效果不在此结论内。

## 交付与单元对照

| 单元 | 实际交付 | 验证入口 |
| --- | --- | --- |
| U0 | 冻结 revision、597 份资产原始账本、32 条查询和最终逐页 prompt 基线 | `tests/fixtures/style-index/`、工作区 `baseline/asset-ledger.json` |
| U1 | 共享解析与角色分类、成员/变体引用检查、旧可调用集合兼容 | `test_style_asset_inventory.py`、`test_style_scope_resolution.py` |
| U5 | v1 加性 schema 校验，只回填 11 个内置 source/taxonomy | `test_style_metadata_backfill.py`、`test_style_pack.py`、`final-asset-audit.json` |
| U2 | 名称/别名/家族分页、counts/catalog/manifest、只读完整性检查及中断恢复 | `test_style_index.py`、`test_style_index_links.py`、生成器 `--check` |
| U3 | 有界摘要、同 home 用户覆盖、实际选择守卫、双路径降级与 Skill 接入 | `test_style_index_workflow.py`、`test_style_index_distribution.py`、六类 Agent 用例 |
| U6 | 同作用域版式输入、独立容量门、样张继承和治理字段不入 prompt | `test_style_selection_layout.py`、`test_style_index_baseline.py`、容量与样张 Agent 用例 |
| U4 | 包级回归、真实 Agent 轨迹与 Judge、固定查询配对、文档及分发说明 | 下述执行记录与最终结果 |

测试路径均相对 `leo-ppt-generator/tests/`。工作区指仓库根目录 `leo-ppt-style-index-workspace/`，已忽略的原始日志与轨迹保留在本机，未打入技能包。

## 资产完整性

原始资产 597 份，无增删：584 份完全不变、11 份仅增加 source/taxonomy、2 份导航文档更新。去掉新增元数据后，11 份 brief JSON 与冻结账本完全一致。

| 口径 | 数量 |
| --- | ---: |
| style | 311 |
| independent_styles | 294 |
| pool | 7 |
| layout | 47 |
| axis | 151 |
| rule | 10 |
| reference | 70 |
| unknown | 1 |
| coverage=full | 318 |
| coverage=name-only | 279 |

unknown 是既有扩展模板中的占位 JSON，不能执行。full 仅表示摘要所需结构覆盖，不表示视觉通过。随包 catalog 全部为 builtin，不包含用户资料。

完整路径、before/after SHA-256 与差异字段见工作区 `final-asset-audit.json`。索引摘要：

```text
source_digest=d1e58907a6a6952d3e9eb717e9f1d3803b183f60f8bd527b3382b6308a0eb519
snapshot_digest=d819ccd83a40a84aa02040285366677ea68d53163385cefb06332b4fb86903b0
```

根 `_INDEX.md` 最终保持 authored 导航，生成成员和 counts 全部位于 `generated/`。根导航不进入 source_digest，但由 navigation_sha256 校验完整性，避免自引用同时防止导航篡改漏检。

## 本地验证

实际环境：macOS arm64、任务隔离 Python 3.12。没有用系统 Python 缺依赖的失败推断产品回归。

- 包级测试：**1270 tests，0 failures，0 errors，0 skipped**，见工作区 `package-scope-final.json` 与同名 `.log`。后续窄范围入口调整由对应真实 Agent 回归覆盖，判官末次修改另复跑定向单测。
- brief lint：318 briefs、0 errors、0 warnings。
- layout lint：0 errors，3 个已有白名单豁免，未新增豁免。
- index/governance lint：均 0 errors；governance 0 warnings。
- 本次技能 Markdown 链接：106 份，0 errors。
- `git diff --check`：通过。
- 独立 `generate_style_gallery.py --check`：`OK: gallery and golden samples up to date`。该命令不调用真实图片 Provider。
- 完整 bundle 复制、目录链接、缺 generated 时独立摘要均有实际 fixture；摘要查询不写安装目录。
- Windows x64 / macOS Intel：新增依赖 wheel 可获得性通过；未在对应操作系统运行测试。

从 `leo-ppt-generator/` 执行的包级命令：

```sh
env -u LEO_PPT_BUNDLE \
  LEO_PPT_RUNTIME_PYTHON="$PWD/../leo-ppt-style-index-workspace/.venv/bin/python" \
  PYTHONPATH="$PWD/runtime/src:$PWD" \
  ../leo-ppt-style-index-workspace/.venv/bin/python \
  ../leo-ppt-style-index-workspace/run_tests.py package-scope-final
```

四条 lint 分别运行 `scripts/lint_style_briefs.py`、`scripts/lint_layout_grid.py`、`scripts/lint_style_index.py`、`scripts/lint_style_governance.py`；使用同一任务 Python，`PYTHONPATH=runtime/src:.`。

## 行为与配对评测

宿主：skill-up 0.10.0 / Claude Code 2.1.247；配置未覆盖模型，真实登录模型轨迹为 `glm-5.3`，启动日志为 `glm-5.3[1m]`。这不是当前助手模型的回归。

正式配置 `skill-up validate evals/eval.yaml` 和 `list-cases` 均成功，共 97 个用例；本期选择完整风格相关子集 32 项，不声称全 97 项 Agent 测试通过。

历史结果保留，不覆盖：新六类曾 6/6 通过；首轮 32 项为 22/32，修复子集先 6/10、再 4/4；后续 release 轮为 27/32。release-fixes 为 4/5，剩余长尾经入口修复后 1/1。acceptance 轮为 27/32，五项文本 Judge 误报修复后对同一轨迹重评 32/32；但统一咨询轨迹检查发现 27 项咨询中 10 项使用了 Bash/CodeGraph，故该轮仍不满足完整验收，不能仅引用重评分数放行。

历史 `evals-final-boundary/iteration-1/result.json`：27 PASS / 5 FAIL / 0 ERROR。`scripts/check_style_eval_traces.py` 当时对 27 项咨询统一核验，10 项越界；两者联合为 **19 PASS / 13 FAIL**。其后修复为按能力、路径和副作用判断等价只读工具，并保留原始失败，不将历史未通过状态删除。

最终采用 `evals-scope-final/iteration-1/result.json`，32 项并发度为 3，原始 30 PASS / 2 FAIL / 0 ERROR。原始失败为：双生样张的“同一个正文内容页”未被旧字面匹配识别；样张反演的疑问标题被当作执行承诺。补充肯定/否定、疑问标题/后续实际放行的反例后，对全部 32 项同一轮原始回答重评，32/32；引擎退出断言原样保留，未用 Judge 通过覆盖引擎错误。

`regrade-all.json` 保留每项 original_status、最终 Judge SHA-256、重评退出码及原始轨迹哈希。统一咨询轨迹检查为 27/27；顺序组合逐条验证只读命令，catalog、越界路径、目录穿越和写入反例均拒绝。末次变更只涉及判官及等价只读命令表述，由 26 项定向单测和同轨迹复核覆盖；未重生成模型回答。

复核命令（技能目录）：

```sh
python3 scripts/check_style_eval_traces.py \
  ../leo-ppt-style-index-workspace/evals-scope-final/iteration-1/result.json
```

该命令当前 exit 0；明细在工作区 `evals-scope-final/iteration-1/trace-check.json` 与持久证据中。其余历史轮次的失败不覆盖、不删除。

固定查询确定性对照：24 条有名称集合期望的查询，新摘要 24/24、旧 list/filter 15/24；开发集 19/19 对 12/19，留出集 5/5 对 3/5。剩余 8 条是场景/操作合同，不按名称命中评分。旧实现来自 `6a8578ba16624550c2150ed72245fa9bc3c9fa8c`，使用相同源资产和 Python。

真实 Agent 配对另外执行同一 24 条查询的旧 list/filter 与新摘要读取，共 48 次。它限定为执行期查找阶段：相同宿主、命令包装与用户 fixture，Agent 调用实际查找并返回候选集合；不等于完整旧新 Skill 的自由规划对照，也不代表 advise Markdown 的成本。48 次全部确认只调用一次对应查找命令，旧新错误按同一冻结期望评分，不使用新索引作答案。

| 查询集 | 旧名称正确 | 新名称正确 | 旧/新严格 JSON 合同通过 | 旧/新平均输入 token | 旧/新平均耗时 ms |
| --- | ---: | ---: | --- | --- | --- |
| development，19 条 | 12/19 | 19/19 | 10/19、18/19 | 50642.3、51341.3 | 15063.4、14700.9 |
| holdout，5 条 | 3/5 | 5/5 | 3/5、5/5 | 50620.6、51406.6 | 12898.8、16389.2 |

新名称集合总计 24/24，严格输出合同 23/24：一条回复多输出结束括号，未隐去格式失败。旧名称 15/24，严格合同 13/24。格式要求是配对实验的输出控制，不是 PPT runtime JSON 返回；本期检索硬门按名称和实际工具证据判断。

首次配对 Judge 缺 shebang 导致首批基础设施误报，修复后对全部保留轨迹统一重评，原始 `evals-paired-lookup/iteration-1/result.json` 未覆盖；完整逐项正确性、成本和轨迹 SHA-256 位于 `evals-paired-lookup/regraded/result.json`。此单次固定实验没有统计显著性结论，输入 token 包含宿主上下文，不折算账单，不宣称成本下降。

## 审查修复

本次为主 Agent 行内审查，未运行独立跨模型代码审查，`independent_review=not_run`。已直接核对共享资产解析、schema 增量、索引生成/发布/校验、CLI 摘要、用户覆盖与选择指纹、compose 投影、容量检查、lint/画廊/分发接线，以及本轮改动的 Judge 和正反测试。复用、质量、效率检查未发现需要额外抽象的修改；保留独立容量门和旧 v1 兼容投影，不为精简代码合并职责。

| 问题 | 修复与证据 |
| --- | --- |
| 选择变化错误码被通用异常覆盖 | 专用异常保持 `style_selection_changed` / `style_selection_invalid`，真实 CLI 回归 |
| pool 混入普通候选、非法角色可 guarded compose | 普通 browse 只列 style；精确查询披露角色；guarded compose 校验同一份已加载正文 |
| 根导航篡改和发布中断恢复缺口 | navigation_sha256、staging rename 失败恢复旧快照测试 |
| 画廊误扫 generated、stderr 错误未识别 | 排除派生目录；解析 stderr JSON；缺 backend 后不继续页面渲染 |
| Judge 不识别宿主规范化轨迹或误判否定句 | 支持真实格式，工具结果与调用文本分开，正反测试覆盖 |
| 护栏已经真实调用但最终文本未重复旗标被误报 | 依据调用轨迹识别 `style render --guardrail`，最终仍检查护栏摘要与数值锚点 |
| 固定文本槽版式大量短要点绕过容量 | 无数量槽时增加全部文本槽总预算检查；长字符串与大量单字均须 overflow |
| 咨询检索越界、样张实证和 sidecar 门禁遗漏 | 入口明确宿主 Grep/Read、样张真实证据优先、入库必须 sidecar 和双 lint；真实 Agent 复测 |
| 路径子串检查漏放 catalog、混合读取和目录穿越 | shlex 解析限定简单只读命令，逐输入核对 Markdown；目录列表不等于读取事实 |
| 同句否定掩盖后续放行、TF-2 标签冒充重确认 | 分句正反测试；实际要求样张重确认；区分未来成本授权与推定同意、否定引用与真实越权 |
| 论证模式/版式误用风格名称索引 | 入口按角色分流，未命中不扩读 catalog；六项定向轨迹 6/6 |
| 低置信度推荐冒充已冻结布局 | 前置候选输出合同，保留两个候选、推荐理由与 undecided；修复后定向回归及轨迹 1/1 |

容量用例原文本 `points=[10000 个“长”字]` 有歧义，现明确为单元素数组 `["长" * 10000]`；原来误解成一万个单字仍揭示真实漏洞，已同时纳入确定性回归，未通过改用例掩盖。

## 能力与交付边界

本期提高名称/别名可达性、角色和作用域判定、索引维护一致性；没有实现 semantic ranker、MMR、stable ID、目录迁移、全库元数据富化或许可 enforcing。新摘要返回更丰富的信息，不能声称延迟或 token 必然下降。

未调用真实图片 Provider 验证全库视觉还原，未证明审美提升或客户业务效果。最终逐页 prompt 与确定性画廊检查只能支撑对应范围。

主执行过程未运行发布、提交或推送。已安装 `.agents/skills/leo-ppt-generator` 与 `.claude/skills/leo-ppt-generator` 本来就是本仓库的目录链接，源码修改会即时可见；部分真实 Agent 执行用例调用了 bootstrap/setup，不能声称评测完全没有触及宿主 runtime。其结果不作为独立发布验收。

## 历史问题账本

以下是 `evals-final-boundary` 的历史失败集合，不代表最终版本剩余项；后续修复及最终验收统一以上方结论、当前结果路径和机器证据为准。

| 尚未通过的用例 | 最终证据 |
| --- | --- |
| style-index-lookup、style-index-long-tail | 名称回答正确，但存在 Bash / CodeGraph / 占位调用 |
| user-picks-style、mismatch-warning-once | 咨询中使用白名单外工具 |
| beta-m6-academic-five-modes、beta-m1-layout-dispatch-no-fabricated-ids | 咨询中使用 CodeGraph/Bash |
| style-alias-colloquial-hit、style-candidates-honest-gap、style-hardrule-defense-mismatch、style-new-family-renderable | 旧回答 Judge 通过，真实工具轨迹仍越界 |
| beta-m7-style-inversion-three-groups | 三组判读和实证说明存在，但未明确同一样张确认轮，并出现“暂定”与“锁定”措辞混用 |
| beta-m1-layout-dispatch-undecided-asks-human | 单选两栏，未保留候选/undecided；还将 6 格各约 30 字误说成可压入约 80 字总预算，需要修复实际容量解释 |
| beta-m1-capacity-precheck-downgrades-not-shrinks | 原始 Judge 将“缩小字号……照样会拦”的拒绝解释误判为许可；作为已定位的判定缺口保留，不冒充真实建议缩字 |

本轮已明确按文件范围与副作用约束等价只读访问，并同步入口、Judge 和正反回归。Skill 文本仍不是宿主权限隔离机制；无法证明为有界只读的工具轨迹保留为失败，CodeGraph 不能替代索引事实。最终完成状态依据当前完整回归的回答判定和轨迹检查共同通过。
上述联合门现已通过。必要证明对账：资产集合、索引完整性、最终逐页 prompt、实际检索、作用域/角色、独立容量、治理/分发、11 个试点元数据均有对应测试或逐项证据；没有遗漏的本期必需证明。主 Agent 行内审查是独立审查不可用时的降级覆盖，不冒充跨模型审查。

## 结构化收尾

本地收尾记录位于 `.spec-first/workflows/spec-work/leo-skills/style-index-reviewed-20260906/`：

- `verification-run-summary.json`：包级测试、末次判官/轨迹回归、资产/索引/链接、四 lint/画廊及最终 Agent 证据。
- `honest-closeout.json`：`overall=verified`、`all-claims-consistent`。
- `run.json`：`spec-work-run-artifact/v2`，`workflow_integrated=true`，`trigger-substantive-work`。

以上为本地命令结果的转录及源码绑定，不宣称 provider-confirmed 的独立监督证明。原始 Agent 轨迹保留在本机忽略工作区；可分享的哈希、逐例结论与资产账本在仓库级机器证据中。
