# 评测验证摘要

更新日期：2026-09-04

## 结论

31 个用例的配置与本地确定性检查有效。固定 Codex 模型 `gpt-5.6-terra` 下 iteration-32 曾达成 20 例全量 `20 PASS / 0 FAIL / 0 ERROR`；2026-08-27 套件扩至 31 例（补齐编辑质量层 + 授权写入正向路径 + 多轮状态机）。GLM flash 代理上：完整回归（iteration-38，29 例）为 `24/4/1`，非设计性失败均经聚焦修复复验；judge 红队（16 对抗探针）暴露的 3 处漏判已修复并以「历史响应重放」确认无回归；四例易碎用例 A/A 量化掉率后确立「实质在场、词汇未命中即记档」纪律（见 known-issues.md）。唯一按设计保持严格的是 `post-publish-no-causal-unprompted`（八轮稳定 FAIL；SKILL 侧行内枚举与 fenced 示例两次文本强化均无法让 flash 级模型自发输出状态块，定性为模型稳健性问题）。同日晚间完成两轮 31 例全量 A/A（iteration-51/54）：`28/1/2` 与 `27/3/1`，3 个 ERROR 均为引擎 180 s 超时且聚焦复验 PASS（iteration-53/55），其余 FAIL 全部按上述纪律定性收敛（audit 证据标签同义修判官后复验 PASS；chinese-22 单轮抖动复验 PASS），与稳态预期一致；判官同义词与输出合同收敛、默认超时放宽至 240 s 后，parallelism 2 全量首次达到 `30 PASS / 1 FAIL / 0 ERROR`（iteration-64，24m49s，较 p=1 缩短 45%）。随后落地创作者化能力层（v2 方案 10 项：选题四问、读者模型、内容资产、论点压缩句判据、叙事骨架、首屏合同、分发包、观察清单）；回归期判官词汇轮换频次上升（更丰富的合同带来更多样的报告形状），iteration-69 全量 `27 PASS / 4 FAIL / 0 ERROR`，4 个 FAIL 全部经分诊收敛：1 个已知模型极限（unprompted，第 10 轮稳定 FAIL）+ 3 个词汇级轮换（`routes-ambiguous`「做完」、`chinese-protocol`「不需要去模板」首掷扩词后复验 PASS；`chinese-22` 编辑判断轮换按纪律记档），有效行为稳定性 30/31。受支持模型上的 31 例全量绿灯仍待复验。未固定模型的历史运行仍保留为 provider 漂移与 Judge 设计的失败证据。

## 有效 focused 证据

| 能力 | 最新结果 | 证据 |
|---|---:|---|
| 裸主题只问一个分叉问题 | PASS | iteration-7 |
| 技术 How-to 路由 | PASS | iteration-7 |
| Deep 证据与事实回归主链 | PASS | iteration-9 |
| 声音档案可跳过且不冒充个人声音 | PASS | iteration-5 / iteration-9 语义证据 |
| audit 只读边界 | PASS（脚本正反自测 + 在线复验） | `check-audit-readonly.sh`（2026-08-27 扩「证据」标签同义词；iteration-56） |
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
| 裸主题两轮分叉状态机 | PASS | iteration-43 首跑 / iteration-54 全量（超时放宽 420 s 后） |
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
- iteration-64，GLM flash，parallelism 2 首次全量（defaults 超时已放宽至 240 s、技能输出合同收紧后）：`30 PASS / 1 FAIL / 0 ERROR`，套件历史最佳全量结果——零引擎超时，唯一 FAIL 为 `post-publish-no-causal-unprompted`（第 8 轮稳定）。墙钟 24m49s，较 parallelism 1 的 ~45m30s 缩短 45%；代价是 bare-topic 两轮 resume 路径在并发下拉长至 398 s，其用例超时同步上调至 480 s。parallelism 2 固化为默认前的证据边界：单轮全量 + 无外部并发；出现争用噪声时优先回退 parallelism 1 而非继续加超时。
- 稳态预期：受支持模型外，GLM flash 上 31 例预期 `30 PASS / 1 FAIL`（唯一稳定 FAIL 为 `post-publish-no-causal-unprompted`）；flash 级模型的措辞重掷意味着单轮 full 可能出现新的词汇级 FAIL，处理纪律见 known-issues.md（实质在场、词汇未命中即记档，不追词）。
- iteration-42~43（E 阶段）：新增授权写入与多轮分叉两用例（先跑 1 FAIL 1 PASS，措辞收敛后全 PASS）；judge 红队暴露 causal「先断言后补丁」、post-publish「已被验证有效」、independent-review「status: PASS」三处漏判，修复后 6/6 历史 PASS 重放接受。
- iteration-45~48（A/A 掉率）：rejects-causal 2/3、chinese-protocol 2/3、docs-truth 1/3、dev-edit 2/3。其中 rejects-causal 的两败为收紧门禁引入的假阴性（情态词与动词间插入宾语），iteration-48 放宽为 0-8 字间隔后 5/5 历史重放接受、对抗样本仍拒绝；docs-truth 移除了会「引用-再否定」误杀的命令级负向断言。修复后聚焦复验全 PASS（iteration-49/50/52）。
- iteration-51 / iteration-54，GLM flash，31 例两轮全量 A/A：`28 PASS / 1 FAIL / 2 ERROR` 与 `27 PASS / 3 FAIL / 1 ERROR`（iteration-51 前 10 分钟与外部会话的 skill-up 运行共享代理配额，iteration-54 无并发干扰）。3 个 ERROR（nonarticle-lifecycle、bare-topic 第二轮 resume、source-grounded）均为引擎超时，聚焦复验 PASS（iteration-53/55）；FAIL 定性：`audit-does-not-rewrite` 两轮均为证据标签同义漂移（响应逐字引用原句但标签用「证据」，判官按 iteration-33 先例扩同义词，历史重放 + iteration-56 在线复验 PASS）；`chinese-22-rules-hit-and-preserve` 单轮漏报反代入 finding，聚焦复验 PASS 不可复现；`post-publish-no-causal-unprompted` 跨轮稳定 FAIL（词汇重掷：缺少 observation → 缺少稳定规则决策）。`bare-topic-fork-two-turns` 干净环境实测 299 s/300 s 余量为零，超时放宽至 420 s 后全量 PASS。
- iteration-57~63，GLM flash，技能输出合同收紧后的安全网与修复验证：iteration-57 五例安全网 `3 PASS / 2 FAIL`——`chinese-protocol-context-judgment` 为停止判定新同义「不需要改」（case any-list 扩词后 it-61 复验 PASS；七类逐类表态使检测报告结构显著稳定）；`post-publish-no-causal-unprompted` 在 SKILL.md 行内枚举合同下仍 FAIL，状态块升级为 fenced YAML 示例后再 2/2 FAIL（it-62/63，响应四字段全缺席），累计七轮稳定 FAIL。`bare-topic-fork-two-turns` 超时分布五样本 [221/271/298/299/309] s，420 s 上限维持（对最大值 36% 余量）。收紧判定必须附带历史响应重放已固化为流程（见 known-issues.md）。
- iteration-65~69，GLM flash，v2 创作者化能力层（3 个新 references + 6 文件改动）的回归链：安全网 8 例 `6 PASS / 2 FAIL`（unprompted 已知；chinese-22 报告风格偏移）；全量 it-66 `26/4/1`——dev-edit 第 5 掷（删掉任意）、chinese-22 决策日志式同义词扩词、nonarticle 240s 超时（第 4 次，聚焦复验 PASS）；dev-edit 第 6 掷（空转，借入 chinese-22 既有合法词）历史重放通过后聚焦 PASS；修复后全量 it-69 `27/4/0`——routes-ambiguous（做完，首掷）与 chinese-protocol（不需要去模板，第 7 掷）扩词后聚焦 PASS，chinese-22 本轮为编辑判断轮换（对抽象词选择「保留+披露缺口」而非删除，实质可辩护、此前 it-68 聚焦 PASS），按纪律记档不追词。- iteration-71~72，GLM flash，全修复态最终全量与收口：it-71 `29 PASS / 2 FAIL / 0 ERROR`——unprompted 第 11 轮稳定 FAIL；`taste-findings-not-visual` 本会话首掷（引用弯引号 + 倾倒/净信息量，扩词后）在 it-72 聚焦复验中再掷新词（并列），两轮实质均在场（canonical finding 格式 + 逐字引用），按纪律记档为词汇轮换类，不追词。v2 落地后的最终画像：31 例有效行为稳定性 30/31（唯一残留 unprompted 已知模型极限）；flash 上单轮全量原始绿灯受词汇轮换概率制约（27-30 PASS 区间），全部 FAIL 经分诊收敛，证据链完整；受支持模型复验仍是最终门槛。
- iteration-99~101，2026-09-04，本机 claude_code 登录态（模型未固定，report `model_name` 为空）上的 description 触发面 + 路由枚举同步锁落地回归：it-99 全量 37 例 `13 PASS / 22 FAIL / 2 ERROR`（ERROR 为 CLI `Prompt is too long` 与 480s 超时）。FAIL 形态与既有 provider 漂移画像一致（judge 词表未命中 / 输出含禁词 / 词汇轮换），不构成改动回归证据；受支持模型复验仍是最终门槛。it-100/101 做 SKILL.md 新旧 A/B（同环境 focused 3 例：routes-technical-howto、personal-context-authorized-write、deep-independent-review-status）：新版 `1 PASS / 2 FAIL`，旧版（stash 改动）`0 PASS / 3 FAIL`——两例共同 FAIL 为同一 judge 词表未命中（新旧一致，非本次改动引入），deep-independent-review-status 仅新版 PASS；本轮顺带适配 skill-up 0.10.0 的 `file_contains` schema（`contains` 列表 → 必填 `content` 字段，断言语义不变），A/B 两轮该断言均通过（真实写集 AGENTS.md 含 `unittest` 成立）。同步锁单测见 `tests/test_route_enum_sync.py`（先红 23 断言、修复后全绿；全套 202 例 PASS）。

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
skill-up validate: 31 cases loaded
python unittest: 6/6 PASS
shell judges: bash -n PASS
git diff --check: PASS when repository metadata is available
```

## Claim ceiling

当前证据证明固定用例上的本地合同和 focused Agent 行为，不证明真实发布效果、作者声音忠实度、AI 作者身份识别能力或跨 provider 的稳定增量价值。后续若要做 promotion，应固定受支持模型和 provider，再执行 A/A 与 full regression。
