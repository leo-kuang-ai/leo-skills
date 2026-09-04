# leo-ppt-generator 全生命周期用户体验优化方案

- 日期：2026-08-27
- 定位：以**用户生命周期五场景**（首次安装 → 首次配置 → 日常使用 → 非首次更新 → 配置变更，附卸载/迁移缺失场景）为主轴的完整优化方案。使用中段的深度体验问题（确认序列、worker 死局、机器词表）已在
  `docs/leo-ppt-generator-ux-review.md` 拆解，本文收拢其结论并补齐前后两端；工程链路评审见 `docs/leo-ppt-generator-optimization-review.md`。
- 方法：对安装器（`install.sh`/`install.ps1`）、bootstrap（`scripts/leo-bootstrap.sh`）、`runtime_manager.py`、CLI 现场（`update`/`rollback`/`doctor`/`config` 家族帮助文本与真实输出）逐一盘点，并以本机真实安装残留做量化实证。
- 成本级标注：[D]=纯文档/README；[S]=包内脚本层（shell/python，随包发布可控）；[C]=CLI/runtime vendored 层（须走 patches 流程，高成本）；[E]=评测配套。

## 0. 生命周期地图与成熟度总评

```text
S1 首次安装 ──> S2 首次配置 ──> S3 日常使用(迭代)──> S4 非首次更新(循环)
                     │                │                  │
                     └──── S5 配置变更/凭据轮换 <──────┘
                                      │
                          S6 卸载/迁移（现状：完全缺失）
```

| 场景 | 成熟度 | 一句话评价 |
|---|---|---|
| S1 首次安装 | 高 | 平台检查、互斥锁、staging 原子激活、四 route doctor、装后 onboarding 已是专业水准 |
| S2 首次配置 | 中高 | TTY 向导 + 免费默认不计费路径存在；token 直出与离场指引缺失 |
| S3 日常使用 | 中 | 执行链可靠，体验债集中在确认节奏与失败文案（详见 ux-review） |
| S4 非首次更新 | 中低 | 校验后替换/rollback 机制完备；**备份与 runtime 零回收正在复利积累** |
| S5 配置变更 | 中 | 幂等确认与冻结 run 保护齐备；变更影响面不告知 |
| S6 卸载 | 缺失 | 无 `--uninstall`、无手工卸载文档 |

## 1. S1 首次安装

**已达标（保持）**：架构预检含平台拒绝语义；发现根冲突与陈旧备份挡道采用 fail-fast；安装锁防并发；staging + 原子激活失败自动回滚；每 route doctor 校验后才切换；装后即跑 onboard 检查并输出中文状态报告（配置状态/真实验证/执行资格）；非 TTY 环境守卫明确（"未检测到交互终端；不会等待配置输入或发起可能计费的验证"）；PATH 未含 bin 目录时给出可粘贴 export 行。

**痛点与方案**：

| # | 方案 | 成本 | 说明 |
|---|---|---|---|
| L1 | **宿主选择友好化**：新增 `--host claude\|agents\|codex` 别名参数映射目标目录；usage 与 README 给出各宿主推荐安装命令矩阵。现状默认 `${CODEX_HOME:-~/.codex}/skills`，Claude Code 用户必须自行发现 `--agents` | [S] | 首触第一道门槛是"这个安装器以为我在用别的产品" |
| L2 | **bootstrap 失败的人话伴随行**：`fail_bootstrap` 在协议 JSON 之后向 stderr 追加一行中文摘要（如"缺兼容 Python，将下载私有运行时环境失败；可检查网络后重装"）。stdout JSON 契约不动，Agent 消费不受影响 | [S] | 现状失败时终端人类只看到裸 JSON |
| L3 | **onboarding 报告完成中文化**："执行资格/安装可用性"直出 `blocked`/`usable_unverified` 等 raw token；接状态人话映射表（与 ux-review Q4 同源） | [S] | 安装成功的喜悦瞬间被英文枚举打断 |
| L4 | **装完第一步指引**：尾部固定"下一步"段——在哪个宿主里重启/开新会话、说哪句话能开始（引 README 示例 prompt）、配置命令在哪。"请重新启动 Codex"按实际安装模式动态生成 | [S]+[D] | 现状假设人人知道下文 |

## 2. S2 首次配置

**已达标（保持）**：默认不发起付费 smoke（只有 TTY 内显式同意才 verify）；非 ready 只给单一 primary_action；blocked 时禁倾泻内部名词并留"高级诊断"逃生口；准备阶段最多两问的上限防轰炸。

**方案**：

| # | 方案 | 成本 | 说明 |
|---|---|---|---|
| L5 | **config status 人话标签**：三态与关键字段接 glossary（configured_unverified→"配置完整，首次生成图片时会顺带做真实验证"）。与 ux-review P4 单一来源共享 | [D] | 解除"看起来像出错了"的最大误解源 |
| L6 | **离场回话指引模板**：TTY 向导完成后打印"回到对话发送『已配置完成』即可继续"；与 agent 侧合同呼应（`first-use.md` 已有"完成后复查 config status 并回到原任务"，两侧模板对齐） | [D] | 补全程唯一离场操作的闭环 |
| L7 | **usable_unverified 一句话承诺**：把惰性验证机制的标准解释句写进 README/first-use，agent 侧直接引用（"你的配置已经可用；第一次真实生图会同时完成服务验证，无需额外操作或费用"） | [D] | 现有三态说明偏 contract 语言 |

## 3. S3 日常使用

主轴结论以 `docs/leo-ppt-generator-ux-review.md` 为准（Q1–Q8 快赢、P1–P5 待拍板、E1–E3 评测配套）。生命周期视角仅补充一项：

| # | 方案 | 成本 | 说明 |
|---|---|---|---|
| L8 | **会话内版本感知条款**：execute 开始时的首次状态汇报附带一行本地版本与人话就绪度（来源 doctor readiness_summary 映射），版本较上次交付发生变化时如实提示"刚完成过一次更新，首轮生成将重新验证服务" | [D]（判官不加断言） | 承接 S4 的"更新后首用"心智衔接；措辞进 glossary |

## 4. S4 非首次更新（本轮最重的量化发现）

**已达标（保持）**：skill 升级 = 校验后原子替换 + 自动备份，失败自动回滚；runtime 有 `update --check/--dry-run/--yes/--version` 渐进确认与 `rollback --identity`；verification stale 语义已被 installer 文案正确表达（"此前验证已失效；下次生成图片时会重新验证"）；冻结 run 不被新 secret 影响。

**量化实证（本机）**：

- `.leo-ppt-generator-backups/` 下 **23 份历史 Skill 备份共 46MB**；
- 受管 `runtimes/` 下 **24 个哈希命名的 runtime 共 4.3GB**，长期无任何回收；
- 全代码库 grep `uninstall|卸载` 零命中——没有卸载概念。
- 结论：**更新流程只管"进入新版本"这一半，"离开旧版本"的一半完全缺位**。短期是磁盘税，长期在容量敏感设备上会演变为安装失败的真实诱因；且 doctor 检查项（directory_fsync degraded 类环境告警）也可能因空间压力漂移。

| # | 方案 | 成本 | 说明 |
|---|---|---|---|
| L9 | **备份与旧 runtime 保留策略**：Skill 备份各保留最近 3 份、受管 runtime 除 current 外保留最近 2 份（任何时刻至少保留一个可回滚 identity 作为 rollback 下限）。清理仅由 `--upgrade` / `update` 成功路径触发，其余命令不产生删除动作；成功尾部报告“已清理 N 项，释放 X MB”。删除目标逐项经 lstat 校验为真实目录且非符号链接，任一异常即整批跳过并告警；动作仅限自家命名空间、跳过 current 与活动锁 | [S] | 最高 ROI：纯脚本层，治 4.3GB 级泄漏；验收含伪造符号链接 fixture 的跳过断言 |
| L10 | **备份挡道文案精确化**：发现根扫描命中旧备份时的 fail 文案从"请移入非发现目录"升级为给出确切 `mv` 命令；同时校验自身备份根命名恒为点前缀（隐藏于发现 glob），杜绝自产自拦 | [S] | 把 fail-fast 从"墙"变成"门牌" |
| L11 | **更新内容可发现性**：skill 包随附 `UPDATES.md`（发布时由顶层 CHANGELOG 过滤本包条目生成，或直接注明获取路径）；`update --check` 人话输出附带"变更详情见 …"一行 | [D]+[S] | 更新静默是信任损耗点 |
| L12 | **rollback 发现性**：README 故障排查节 + advanced 诊断回复模板明示 `leo-ppt update --check` / `rollback` 与 identity 取值处；glossary 收录 | [D] | 机制已建好，缺的是让人知道 |

## 5. S5 更新配置与凭据轮换

**已达标（保持）**：凭据只在 TTY 写入且覆盖前二次确认；`config reset --confirm` 仅限用户显式要求；切 Provider/ generation method 强制重做样张（image-deck-workflow 后端继承失效条款）；`backend_contract_changed_during_copy` 等漂移保护完整。

| # | 方案 | 成本 | 说明 |
|---|---|---|---|
| L13 | **配置变更影响面三问清单**（进 first-use 新小节）：这次改动影响哪些 run（已交付不受保护例外、未完成 run 的 backend 继承失效）/ 是否触发重新验证 / 是否产生费用。Agent 改配置前照单告知 | [D] | 用户改配置时最想问的三件事目前靠推断 |
| L14 | **CLI 影响提示语**：`provider prefer/remove`、`credential remove` 输出一行含义提示（"未完成 run 若依赖该 provider 将需要新的样张确认"） | [C]，暂缓 | 正确做法但走 patches 流程成本高；先以 L13 文档替代观察需求 |
| L15 | **凭据自检路径**：credential 操作文案附带 Keychain 条目名约定（如 `leo-ppt-generator/openai-compatible`），让用户能在系统钥匙串里亲眼核对存在性（doctor 已实证此命名） | [D] | 一行成本换"看得见的安心感" |

## 6. S6 卸载与迁移（缺失场景补位）

| # | 方案 | 成本 | 说明 |
|---|---|---|---|
| L16a | **手工卸载文档**（立即）：README 新节，给出四步手工路径——删 launcher symlink、删 skill 目录、`rm -rf` 受管 home（列明将丢失的内容：配置/凭据引用/keychain 条目需另行手动删除及其确认步骤）、检查 PATH 残留 | [D] | 最小诚实方案；明确"钥匙串条目由你决定是否删除"的安全边界 |
| L16b | `--uninstall` 参数（后续）：删 launcher/skill 目录/受管 runtime，**绝不静默触碰 keychain**，涉及凭据的操作全部转交互确认 | [S]，第二批 | 与安装器的锁/原子习惯一致后再做 |

## 7. 跨场景共同主题

1. **人话短语库单一来源**：S1–S5 出现的所有英文枚举收敛到一个 glossary（ux-review P4 的自然延伸），installer/report/agent 回复同源引用，避免三处各自发明译法。
2. **离场操作三件套**：凡要求用户离开对话的动作（终端命令、重启宿主、改系统设置）统一携带"为什么 → 会看到什么 → 做完说什么"。
3. **fail 文案的命令纪律**：一切阻断类文案必须包含一条可直接照做的恢复命令（bootstrap/installer 多数已达标，L10/L12 是补漏）；延续仓库"安全门禁否定感知判官"的评测传统。
4. **更新即沟通**：每个会改变用户环境的环节（install/upgrade/update/config change）都内置"发生什么 + 对我已有东西的影响 + 详情在哪看"三层。

## 8. 汇总清单与实施顺序

| 批次 | 条目 | 理由 |
|---|---|---|
| 第一批 | **L9**（4.3GB 泄漏止血）、L1、L3、L2、L16a | 量化伤害最大 + 首触门槛 + 纯脚本/文档低风险 |
| 第二批 | L4、L5、L6、L7、L10、L11、L12、L13、L15、L8 | 文档为主的状态/指引补全 |
| 第三批（拍板后） | L16b | --uninstall 属删除面功能，值得单独审阅设计 |
| 观望 | L14 | CLI 层提示待 L13 验证是否足够 |

**验证挂钩 [E]**：安装器/onboarding 输出的中文标签枚举用轻量 Python 断言锁定（防 L3 这类映射再次漂移，类同 optimization-review E1 的码保真思路）；L9 的清理逻辑加入保留计数、current 保护与伪造符号链接 fixture 跳过断言的单元测试，并以"连续多次更新后 rollback 仍至少有一个可用恢复点"为边界值用例；标注 [S] 且涉及安装器的条目（L1–L4、L9–L12）须在 install.sh 与 install.ps1 双侧同步实现并各自纳入验收；文档类条目进入仓库级 `git diff --check` 与链接可达抽查即可。

**与前两篇评审的关系**：本篇 L5/L8 直接消费 ux-review Q4/P4 资产；E1（码保真）天然覆盖本篇 L3 的标签面；实施时建议同一批次合并验证并在 known-issues 记账（installer 层行为变化不影响 skill-up 用例，属独立回归面）。
