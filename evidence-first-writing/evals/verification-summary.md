# 评测验证摘要

更新日期：2026-08-27

## 结论

31 个用例的配置与本地确定性检查有效。固定 Codex 模型 `gpt-5.6-terra` 下 iteration-32 曾达成 20 例全量 `20 PASS / 0 FAIL / 0 ERROR`；2026-08-27 套件扩至 31 例（补齐编辑质量层 + 授权写入正向路径 + 多轮状态机）。GLM flash 代理上：完整回归（iteration-38，29 例）为 `24/4/1`，非设计性失败均经聚焦修复复验；judge 红队（16 对抗探针）暴露的 3 处漏判已修复并以「历史响应重放」确认无回归；四例易碎用例 A/A 量化掉率后确立「实质在场、词汇未命中即记档」纪律（见 known-issues.md）。唯一按设计保持严格的是 `post-publish-no-causal-unprompted`。受支持模型上的 31 例全量绿灯仍待复验。未固定模型的历史运行仍保留为 provider 漂移与 Judge 设计的失败证据。

## 有效 focused 证据

| 能力 | 最新结果 | 证据 |
|---|---:|---|
| 裸主题只问一个分叉问题 | PASS | iteration-7 |
| 技术 How-to 路由 | PASS | iteration-7 |
| Deep 证据与事实回归主链 | PASS | iteration-9 |
| 声音档案可跳过且不冒充个人声音 | PASS | iteration-5 / iteration-9 语义证据 |
| audit 只读边界 | PASS（脚本正反自测） | `check-audit-readonly.sh` |
| 独立 reviewer 不可用时降级 | PASS | iteration-10 |
| 工具源码证据路由 | PASS | iteration-8 |
| 正式报告路由 | PASS | iteration-9 |
| 完整 Humanizer canonical IDs | PASS | iteration-9 |
| 非文章 `tool-select × not_applicable` | PASS | iteration-9 |
| copywriting 路由 | PASS | iteration-9 |
| 相关性不升级为因果 | PASS | iteration-6 |
| 未授权持久写入保持只读 | PASS | iteration-5 |
| post-publish 不升级单篇因果规则 | PASS | iteration-15 |
| 中文上下文判断与停止条件 | PASS | iteration-34 |
| 证据型短文保留冲突 | PASS | iteration-34 |
| 渠道档案冲突优先级 | PASS | iteration-34 |
| 少样本声音训练 provisional | PASS | iteration-34 |
| 技术参数回源与 not_run | PASS | iteration-34 |
| 发展编辑先于润色 | PASS | iteration-36（judge 同义词三轮修正后） |
| 授权后最小投射写入（文件级断言） | PASS | iteration-43（两轮措辞收敛后） |
| 裸主题两轮分叉状态机 | PASS | iteration-43（首跑） |
| judge 灵敏度红队 | 16 探针全捕获 + 5/5 历史重放 | 2026-08-27 本地 |

## 完整回归

- iteration-7，Claude Code：`12 PASS / 6 FAIL / 2 ERROR`。后续对 6 个 FAIL 逐例修复并 focused 验证；两个 ERROR 均为 180 秒超时，其中工具路由和正式报告后续 focused PASS。
- iteration-16，Codex：`8 PASS / 9 FAIL / 3 ERROR`。运行中出现未识别模型、未知 MCP server、`request_user_input` 在 Default mode 不可用、线程记录失败及超时；该轮用于记录宿主噪声，不覆盖更精确的 focused 证据。
- iteration-17 / iteration-18，Codex `gpt-5.6-terra` A/A：裸主题路由两轮均 `1 PASS / 0 FAIL / 0 ERROR`。
- iteration-19，固定模型首次 full：`14 PASS / 6 FAIL / 0 ERROR`；逐项定位剩余 Judge 假阴性与一项因果真实失败。
- iteration-31，因果红线修复后 focused：`2 PASS / 0 FAIL / 0 ERROR`。
- iteration-32，固定模型最终 full（20 例）：`20 PASS / 0 FAIL / 0 ERROR`。
- iteration-33，GLM flash 代理（`open.bigmodel.cn` / `glm-5.3-flash`），20 例：`19 PASS / 1 FAIL / 0 ERROR`。唯一 FAIL 为 `audit-does-not-rewrite` 的 `原句/引用` 同义脆弱性（合规输出用「引用：」标签），非技能缺陷；`post-publish-no-causal` 在该 provider 下 PASS，成为跨 provider 证据。
- iteration-34，GLM flash，套件扩至 29 例后的首次 full：`23 PASS / 6 FAIL / 0 ERROR`。6 个 FAIL 全部为「合规行为 + 措辞漂移」组合（`时限`、`open-rate status`、`预设反驳`、`互相争夺`、停止条件不重印原文、`互不推进`），逐例修正 judge/prompt 后 focused 复验。
- iteration-35 / iteration-36，GLM flash，focused：受影响 6 例中 5 例复验 PASS；`post-publish-no-causal-unprompted` 2/2 稳定 FAIL（实质正确、自发合同词汇缺失），按设计保持严格并转 known-issues.md 跟踪。
- iteration-38，GLM flash，judge 修正后首次完整 29 例：`24 PASS / 4 FAIL / 1 ERROR`。`nonarticle-lifecycle` 为 180s 宿主超时（前三轮同 provider 均 PASS，复验 PASS）；`chinese-protocol-context-judgment` 的 fixture 结尾句本身含反转金句导致判定二义，已修正 fixture；`docs-truth-param-check`、`dev-edit-before-polish` 为新措辞漂移（不在真实 --help / 通用真理·罗列），同义词修正后聚焦复验 PASS（iteration-39/40/41）。
- 稳态预期：受支持模型外，GLM flash 上 31 例预期 `30 PASS / 1 FAIL`；flash 级模型的措辞重掷意味着单轮 full 可能出现新的词汇级 FAIL，处理纪律见 known-issues.md（实质在场、词汇未命中即记档，不追词）。
- iteration-42~43（E 阶段）：新增授权写入与多轮分叉两用例（先跑 1 FAIL 1 PASS，措辞收敛后全 PASS）；judge 红队暴露 causal「先断言后补丁」、post-publish「已被验证有效」、independent-review「status: PASS」三处漏判，修复后 6/6 历史 PASS 重放接受。
- iteration-45~48（A/A 掉率）：rejects-causal 2/3、chinese-protocol 2/3、docs-truth 1/3、dev-edit 2/3。其中 rejects-causal 的两败为收紧门禁引入的假阴性（情态词与动词间插入宾语），iteration-48 放宽为 0-8 字间隔后 5/5 历史重放接受、对抗样本仍拒绝；docs-truth 移除了会「引用-再否定」误杀的命令级负向断言。修复后聚焦复验全 PASS（iteration-49~51）。收紧判定必须附带历史响应重放已固化为流程（见 known-issues.md）。

## Provider 诊断

- Claude Code 显式覆盖 `anthropic/claude-sonnet-4-6` 后不再出现未识别模型警告，但当前代理上的 `post-publish` focused case 仍在 180 秒超时。
- Codex 默认登录在完整回归中路由到未识别的 `free-deepseek-v4-flash`，并出现未知 MCP、Default mode 工具不可用与线程记录失败；相同的 `post-publish` case 独立 focused 运行在 iteration-15 中 `1 PASS / 0 FAIL / 0 ERROR`。
- 因此 promotion 前必须固定受支持的 provider/model，并先做至少两轮 A/A；不得把当前代理的随机模型路由当成 Skill 回归。

最终验证命令：

```sh
skill-up run evidence-first-writing/evals/eval.yaml \
  --engine codex \
  --model gpt-5.6-terra \
  --parallelism 2 \
  --format html -v
```

## 静态验证

```text
skill-up validate: 29 cases loaded
python unittest: 6/6 PASS
shell judges: bash -n PASS
git diff --check: PASS when repository metadata is available
```

## Claim ceiling

当前证据证明固定用例上的本地合同和 focused Agent 行为，不证明真实发布效果、作者声音忠实度、AI 作者身份识别能力或跨 provider 的稳定增量价值。后续若要做 promotion，应固定受支持模型和 provider，再执行 A/A 与 full regression。
