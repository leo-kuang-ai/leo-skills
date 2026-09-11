# 上游源码审计

## 范围冻结

审计时间：2026-08-26。根目录：`/Users/kuang/leo-ppt-verify/参考`。目录无 CodeGraph。

所有 9 个仓库均为干净工作树。全部 1,016 个 tracked 非 `.git` 文件已逐文件读取字节并计算 SHA-256；总计 43,944,583 bytes。二进制文件只做路径、类型、大小和哈希账本，不从图片内容推导写作规则。`writing-agent` 的 306 个 vendor 实例是三份同步投影中的 Markdown 渲染器与代码主题；一方/文档实例 325 个，按内容哈希去重后 204 份。

| 仓库 | Commit | 文件 | 文本/二进制 | 许可证 | 主要能力 |
|---|---|---:|---:|---|---|
| Aboudjem-humanizer-skill | `7ef05e2f8b884f1025e557af06aded51d1971e99` | 80 | 74/6 | MIT | 55 模式、误报保护、透明统计 CLI |
| Hello-SimpleAI-chatgpt-comparison-detection | `1f8c15c28f87e09a5abfd86ee6e15005dc7d2119` | 15 | 15/0 | 根目录无许可证 | HC3 语料、分类器、OOD 检测研究 |
| alchaincyf-nuwa-skill | `fe0374687037c4cc51a65c1e0c145afe2981dc69` | 159 | 130/29 | MIT | 多源风格/思维提炼、诚实边界、独立评分设计 |
| blader-humanizer | `e2e92e7b4b8229253ed5c8e81dc65463fdeddda5` | 9 | 9/0 | MIT | Wikipedia 模式、事实保护、样本优先 |
| brandonwise-humanizer | `4b9b9bee384aea139f599133d2de1e1ceaee71a3` | 47 | 47/0 | MIT | 程序化模式、统计、目录扫描、前后比较 |
| dongbeixiaohuo-writing-agent | `7d2bc3ed2f7a779098895a09bd0e369868c9868f` | 631 | 585/46 | MIT | 全流程编辑状态机、证据/哈希门禁、复盘 |
| hardikpandya-stop-slop | `8da1f030185bdfe8471220585162991eaeb970e9` | 7 | 7/0 | MIT | 英文套路清理、直接表达、false agency |
| leonxlnx-taste-skill | `ccbc15639c97057cbfcf32ecebc38ef716e4bb37` | 64 | 47/17 | MIT | 前端视觉反模板，不是文字审美工具 |
| op7418-Humanizer-zh | `91f3d394db8419c20d67ebe22a96cf8fee0a404b` | 4 | 4/0 | MIT | 中文本地化规则与 stop-slop 吸收 |

## 五类能力结论

### 痕迹检测

适合机械化：代码/引语遮蔽、词和结构定位、Unicode/引用标记泄漏、描述性节奏指标、前后 diff、短样本降级。不能机械化：作者身份、中文风格真实性、论证质量和文章价值。HC3 证明检测依赖语料、语言、模型和领域；其 OOD 脚本本身说明跨域是独立问题。当前快照无许可证，不能复制代码或词表。

### 套路清理

可靠动作是先诊断、删除低信息内容、恢复行为主体和具体对象、去掉对话残留，再局部改写。绝对禁词、全删副词、全禁被动和统一破折号禁令会误伤体裁与作者，应服从上下文和声音证据。自动替换只能覆盖语义风险低的窄规则。

### 声音校准

强机制是作者锚点、跨样本证据账本、量化指纹、风格内核、适用边界、陌生主题和隔离盲测。Nuwa 的“跨域复现/生成力/排他性”适合提炼判断方式；Writing Agent 的 `legacy_unverified/verified` 状态适合治理。人物扮演、样本外履历和静态关键词计数不进入用户声音模型。

### 审美判断

参考目录没有一个经过验证的文字审美引擎。`taste-skill` 是前端设计 Skill。可迁移的是 brief inference、anti-default、audit-first、contextual rules、可解释选择和 preflight，而不是视觉规则。文字品味必须由选择、密度、具体性、张力、推进、记忆点和克制重新定义。

### 全流程写作

Writing Agent 提供最完整的节点和机器门禁：选题、brief、立场、调研/证据、结构、读者价值、具象化、标题、开头、草稿、分层审稿、平台测试、Humanizer、最终事实、交付、diff 学习和发布数据。应吸收错误所有权、产物状态、事实回归和跨样本学习；不照搬公众号特定的“打谁的脸”、固定候选数、19 阶段停机和强制传播情绪模型。

## 验证证据

- Aboudjem CLI：26/26 tests passed。
- blader：package validator passed。
- writing-agent：177 tests 中 171 passed、2 skipped、6 因未安装 `tsx/typescript` 失败；Python syntax、workflow contract、runtime sync 通过。
- Brandonwise：缺本地 `vitest`，未运行；只确认源码测试合同，不能声称 green。
- 其他仓库没有对应的本地自动化行为测试；静态脚本和示例不等于效果证明。
- `ast-grep-outline` Skill 与本机 CLI 版本不匹配，`outline` 子命令不可用；使用全文件哈希、`rg` 结构扫描、逐文件直读和测试交叉替代。

## 对当前 Skill 的约束

1. 顶层价值链优先于工具分类，Humanizer 不得拥有全文质量。
2. 事实核查必须在改写前后出现，最终状态绑定当前标题和正文。
3. 中文统计只作描述性线索，不套英文阈值。
4. 声音档案具有证据状态，未验证档案必须降级。
5. 代理读者测试、热点评分和检测分数不能冒充 field outcome。
6. 只有真实、可比、跨文章重复的发布结果才能升级为稳定规则。

---

# 第二轮上游审计（file-github 语料，2026-08-31）

## 范围冻结

语料根为本地 file-github 语料镜像（路径未入库；沿用第一轮惯例记本地绝对路径于工作区清单），快照 2026-08-31，152 个 git 仓库（commit 清单当时冻结于 git-ignore 工作区语料 manifest，该工作区已于 2026-09-11 清理）。方法：漏斗式全景——12 批并行浅筛全量出卡（A 可吸收度≥2 共 54 / B 29 / C 69，卡片见 screening/batch-01..12）→ 6 轨道定向深读 20 个 A 级项目（deepread/T1-T6）→ 44 条候选合并裁决（05-phase3-candidates.md）→ 用户裁决三批全做、合同口径 3+6（06-adjudication.md）。与 2026-08-26 审计重叠的两个项目（writing-agent、humanizer 同 commit）已按增量重评。

## 五簇能力结论

1. **研究环执行纪律**（gpt-researcher/deep-research/deep-searcher/open_deep_research/AcademicForge/node-DeepResearch，MIT/Apache）：吸收终止与预算（双向终止/禁空转轮/depth 分档/85-15 分割）、策展五维保守准入与降级保留、压缩保真（清理而非总结）、引用三态核验与编号按 family 分治——落 source-analysis.md 三节与 workflow-contract.md 呈现契约。多 agent 拓扑与网络核验脚本不吸收（零网络原则）。
2. **中文去 AI 味语义级核对**（shuorenhua/sepia/qu-ai-wei/academic-humanizer/human-writing，均 MIT）：七要素双向核对、动词强度匹配、hedging 不得升格（Never-inject 第 8 条）、venue-first 语域采样、【需作者确认】区块†、CCL 实证锚点、两域 tells——落 chinese-editorial-protocol.md 与 humanizer 两个文件；120 案例阴阳对转 eval 负例集（chinese-humanize-preserve-negative，13 组）。74/18/8 英文配比仅作参照。
3. **状态块与违约对策**（claude-blog/Deep-Research-skills/last30days-skill/writing-agent，均 MIT）：判官双分支结构化解析（canonical YAML 四值枚举+promoted 三条件+零静默；自然语言同义词分支）+ `branch=canonical|synonym;contract_fields=n` 标注；postpublish 状态外置脚本（仅显式 --ledger、append-only、--invariant-hash）；factual_regression 哈希绑定。**判定线实验结论：结构锚不能唤起 flash 级模型的状态块自发性（16 轮 0 canonical），落盘修复以脚本裁决为主**；route 首锚有效（signal-bearing 4/10→10/10）。
4. **审查与收敛协议**（AI-Scientist 非标→只思想/academic-paper-skills MIT）：收敛早停三条（每轮只精修上轮/无新发现须原样保留/轮数是上限）+ 输出完备性契约（逐维度结论、最少 1 条问题或"未发现+检查范围"出口、pass|blocked|not_checked 枚举）+ 返工 ≤3 轮带病放行 + 拒答式评审。**数值过线门禁被实测证伪**（LLM 自评+机械阈值可博弈：弱维度被高分买过线、伪造引用过校验），任何"分数≥X 放行"机制禁入。
5. **声音认知层与文案质检**（blogger-distiller/xiaoma-durex-copywriter/marketing-os，均 MIT）：soul.md 新增「核心信念与判断方式」「观点张力」章节与行级证据格式（≥2 篇独立样本出处）、覆盖边界披露†复用 voice_basis 字段族；文案 grounding 溯源（ungrounded 披露）†、双层语义借势质检（暗示不豁免证据、强合规禁双关）、战术失效双列、评分有界停止（启发式非实测声明）。策略层声音蒸馏与蒸馏他人模式不吸收（授权红线）。

## 明示不吸收（附理由，防下轮重复评估）

数值过线门禁（证伪如上）；策略层运营打法与"蒸馏他人博主"（授权与概念污染）；Nonce 溯源（单 agent 无攻击面）；多 agent 拓扑/网络核验/外部 embedding（零网络）；"中位 6 字"等统计目标（基数不可复核）；19 阶段停机/固定候选数/empathy 主体（维持 2026-08-26 结论）；74/18/8 编辑配比（英文语料，仅参照注记）。卡片池下轮候选见 `04-phase1-summary.md`（ALwrity claim 三分类、FAROS 六态枚举、渠道容忍矩阵、STORM pip 桥等）。

## 验证证据

- 单测 157 项全绿（判官 20+23 对抗/回归用例、状态外置脚本 26、检查器增量 9 等）。
- 判官加固 A/B 回放：全部历史 fixture 零翻转（重建修改前判官对照实测）。
- it-94 观察性全量：36 case 32 PASS；存量 33=29 PASS（87.9%，it-83..92 带内），4 失败逐案归因（实验基线项 ×1、在案间歇类 ×2、判官 `≠` 否定缺口误拒 ×1 已修+聚焦复跑 PASS）。
- 判定线实验与三组频率对比、三条新 case 首跑基线：记 evals/known-issues.md「R2 上游吸收」节。
- 引擎事实：`expect.must_contain_any` 解析不执行——script case 断言迁移 rule_based（deep-editorial-pipeline、audit-does-not-rewrite，历史重放通过）。

## 对当前 Skill 的约束（第二轮新增）

1. post-publish 状态块自发性：停止一切 SKILL.md 文本尝试（内容追加式与结构位置式均已证伪），落盘路径以脚本裁决为准。
2. 数值门禁禁令永久化：评分只可作软停止线索，任何放行判定不得依赖自评分数过线。
3. 判官收紧必须附历史重放（含重建前判官的 A/B 对照）与对抗 fixture 回归锁；否定感知窗口须覆盖数学否定形态。
4. 新 eval 断言一律 rule_based 形态，直至上游修复 must_contain_any。
5. 本轮全部增补已带来源+许可证+快照 2026-08-31 标注；无证/非标许可项目（AI-Scientist）仅思想重写，零文本复制。
