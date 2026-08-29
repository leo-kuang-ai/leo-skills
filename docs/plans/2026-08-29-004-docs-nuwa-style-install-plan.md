---
title: 安装方式对齐 nuwa-skill 三式结构 - Plan
type: docs
date: 2026-08-29
status: completed
artifact_contract: spec-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: spec-plan-bootstrap
execution: code
---

## Goal Capsule

- **目标**：把本仓库（`leo-kuang-ai/leo-skills`）根 README 与三个技能包 README 的安装节，重构为完全模仿 `alchaincyf/nuwa-skill` 的三式结构：方式一通用一行命令（`npx skills add`）、方式二手动 clone 宿主路径表、方式三粘贴 SKILL.md 作为参考资料。
- **推荐路径**：文档重构为主 + 实机验证前置。外部研究（vercel-labs/skills README）表明仓库现有 `.claude-plugin/marketplace.json` 已让通用安装器原生发现三个顶层技能，预期无需仓库结构改造；方式二保留 Claude Code 官方插件市场链路与 leo-ppt-generator 包级安装器作为宿主/包特化通道。
- **决策焦点**：KTD1 插件市场链路保留并降位；KTD2 完整宿主表只落根 README、包级精简；KTD3 验证前置而非盲目宣称兼容。
- **验证焦点**：`npx skills add … --list` 实机确认发现的技能恰好为三个（creator-buddy 32 个嵌套子技能被总控遮蔽）；四份 README 三式骨架一致。
- **最大风险/边界**：安装器实际发现行为与文档研究不符（子技能漏出或技能未被清单发现）——U1 是后续所有文档宣称「已实测」的前置门。不修改技能行为、不动 creator-buddy 上游文件。
- **停止条件**：U1 验证发现清单发现规则不适用于本仓库形态时，停止文档宣称并转入条件分支（见 Scope Boundaries）。

---

## Product Contract

### Summary

为 leo-skills 仓库建立与 nuwa-skill 同款的安装体验：一行命令跨 78+ 宿主装齐三个技能，手动 clone 有逐宿主路径表，不支持自动加载的宿主可粘贴 SKILL.md 兜底；现有 Claude Code 插件市场与包级安装器通道保留为特化路径。

### Problem Frame

当前安装文档以 Claude Code 插件链为中心：根 README 的「快速安装」是 Claude 专属一行命令 + agents 目录 clone 软链；方式二只详述 `~/.claude/skills/`，Codex 仅以脚注带过，Cursor/OpenClaw 等宿主无路径条目。用户在本次会话中考察了 nuwa-skill 的安装方式（通用安装器一行命令 + 宿主路径表 + 参考资料兜底 + 装好后用法），要求完全模仿该结构优化本仓库。creator-buddy 的 README（与 nuwa-skill 同上游生态）已有「方式三：作为参考资料使用」，证明该结构在本仓库语境成立，缺口集中在方式一与方式二。

### Requirements

**安装文档结构**

- R1. 根 README `安装与使用` 节重构为三式结构：方式一为通用一行命令 `npx skills add leo-kuang-ai/leo-skills`（含按名单装 `--skill <名称>` 变体、「帮我安装这个 skill：<仓库 URL>」对话式入口）；方式二为各宿主手动安装路径表；方式三为「作为参考资料使用」（粘贴 SKILL.md 内容进对话）。
- R2. 方式二宿主表至少覆盖：Claude Code（官方插件市场链路 + clone/软链两种，含更新与卸载说明）、Codex（`~/.codex/skills/`）、Cursor（`~/.cursor/skills/`）、通用 agents 目录（`~/.agents/skills/`）、其他 runtime（clone 到对应 `skills/` 目录）；现有「已实测」标注仅保留在已验证通道上。
- R3. 三个包级 README（`evidence-first-writing` / `leo-ppt-generator` / `creator-buddy`）的安装节改为与根 README 一致的三式骨架（方式一含本包 `--skill` 单装命令），并各自保留包特色通道：leo-ppt-generator 的 `install.sh`/`install.ps1` 包级安装器表格、evidence-first-writing 的 Codex/OpenAI 代理说明、creator-buddy 的子技能执行目录说明。

**验证与记录纪律**

- R4. 文档中的安装命令先实机验证再宣称：用 `--list` 确认通用安装器发现的技能恰好为三个顶层技能；未通过验证前，方式一不得标注「已实测」。
- R5. 变更同步 `CHANGELOG.md` Unreleased 段（`(user-visible)` 标注）并引用本计划路径。

### Scope Boundaries

不做（本次确认排除）：

- 拆分每技能独立仓库（nuwa-skill 的每人一仓库模式）。
- 修改 `SKILL.md` 技能行为、触发条件或评测用例。
- 修改 creator-buddy 上游文件；仅触及其 README 本土化改写面（见 KTD2）。
- 变更 `install.sh` / `install.ps1` 功能；仅调整其文档定位。
- CI、发布自动化、`.zcode` 等宿主专项适配文档。

#### Deferred to Follow-Up Work

- 若 U1 验证发现子技能漏出或清单发现失效：仓库侧适配（如引入 skills CLI 清单或规整目录）另立条件工作，不在本计划内预写方案。
- ZCode 等未列入宿主表的 runtime 专项说明，待实际用户需求出现再补。

---

## Planning Contract

### Key Technical Decisions

- KTD1. **Claude Code 插件市场链路保留并降位**（session-settled: user-approved — 范围综合门呈现「保留并列 vs 降级合并」分叉后用户确认按推荐继续）：从「方式一（推荐）」降为方式二宿主表中 Claude Code 行的官方推荐通道，保留更新/卸载闭环说明。理由：该链路已实测且为 Claude Code 官方机制；「完全模仿」的对象是三式骨架与通用一行命令优先级，不是删除自有能力——nuwa-skill 自身也在方式二表中为 Hermes 保留专属安装脚本，先例一致。
- KTD2. **完整宿主表只落根 README，包级 README 精简**：包级保留三式骨架 + 本包 `--skill` 单装行 + 包特色通道 + 指向根 README 的链接，不四处复制整表。理由：monorepo 中整表多处复制必然漂移；creator-buddy 是 vendored 边界，改写面保持最小（其现有安装节已接近目标结构，方式三已同款）。
- KTD3. **实机验证前置（U1 先于文档宣称）**：研究依据是 vercel-labs/skills README 的「Plugin Manifest Discovery」与「浅层 SKILL.md 遮蔽深层」两条规则，属文档级证据而非本仓库实测；故 U1 作为前置门，验证产出决定方式一能否标「已实测」。
- KTD4. **「快速安装（复制即装）」独立块取消**：其内容并入方式一（npx 一行命令本身即复制即装；Claude Code 插件链一行命令移入方式二 Claude Code 行）。根 README 现有「方式三：项目级」降为方式二表后注（项目级 submodule/提交技能目录），方式三让位给「作为参考资料使用」，对齐 nuwa-skill 与 creator-buddy 现状。
- KTD5. **架构姿态：reuse**。`.claude-plugin/marketplace.json` 同时服务 Claude Code 插件市场与 skills CLI 通用安装器，不新增清单或包装脚本；「贡献约定」节补一句说明该双通道语义，新增技能时两通道自动生效。

### Evidence & Limitations

- vercel-labs/skills README（github.com/vercel-labs/skills，2026-08-29 抓取）：manifest 发现规则与浅层遮蔽规则支撑 KTD3 的「预期原生兼容」判断；`--skill`/`--list`/`-g`/`-a` 参数与 78+ 宿主路径表支撑 R1/R2 的命令形态。局限：未实机验证本仓库形态，由 U1 补齐。
- nuwa-skill README（github.com/alchaincyf/nuwa-skill，2026-08-29 抓取）：三式安装节结构、「帮我安装这个 skill」对话式入口、独立子仓库单独安装模式为「完全模仿」的目标蓝本；其「每人独立仓库」模式经 KTD 决策排除（本仓库为 monorepo，用 `--skill` 达成单装语义）。
- 工作区状态：仓库存在大量未提交修改（AGENTS.md、CHANGELOG.md、两技能包文件），四份 README 本身干净；实施时 CHANGELOG 条目叠加在现有 Unreleased 段之上，勿重排既有条目。
- 静态核实：三个 SKILL.md frontmatter 均含 `name` + `description`（skills CLI 发现前置条件已满足）。

---

## Implementation Units

### U1. 实机验证通用安装器发现行为（前置门）

- **Goal**：确认 `npx skills add` 对本仓库发现的技能恰好为 `evidence-first-writing`、`leo-ppt-generator`、`creator-buddy` 三个，为后续文档宣称提供实测依据。
- **Requirements**：R4
- **Dependencies**：无
- **Files**：无源文件修改；验证记录写入 U6 的 CHANGELOG 条目（与方式一「已实测」标注呼应）。
- **Approach**：优先用 `--list` 只读预览（可用远端 `leo-kuang-ai/leo-skills` 或本地仓库路径）；若工具无 `--list` 或行为异常，在临时目录以项目级 scope 试装后清理，不触碰用户全局技能目录。
- **Execution note**：这是「先冒烟后宣称」的验证性单元——文档中的通道宣称以本单元产出为准。
- **Test scenarios**：
  - 预期路径：预览/试装结果列出且仅列出三个顶层技能名（36 个 SKILL.md 折叠为 3）。
  - 异常路径 A：creator-buddy 子技能漏出（列出 gzh/xhs/video 组内技能）→ 触发 Deferred 条件分支，方式一降级为「理论兼容、待适配」措辞。
  - 异常路径 B：三个技能未被清单发现 → 同上条件分支，并检查 marketplace.json `source` 相对路径解析。
- **Verification**：得到一份可引用的发现清单输出（三个技能名）；异常时明确记录偏离形态。

### U2. 根 README 安装节重构为三式结构

- **Goal**：`README.md` 的 `安装与使用` 节呈现 nuwa 三式骨架，成为全仓库安装文档的规范母本。
- **Requirements**：R1、R2、R5
- **Dependencies**：U1
- **Files**：`README.md`
- **Approach**：按 KTD4 取消「快速安装」独立块；方式一 npx 一行命令 + `--skill` 单装 + 对话式入口；方式二宿主表（Claude Code 行保留插件市场链路与 clone/软链、Codex、Cursor、agents、其他；项目级作表后注）；方式三改为「作为参考资料使用」；「验证」与「使用示例」节保留并按 U1 结果补「已实测」标注；「贡献约定」补 KTD5 双通道说明。
- **Patterns to follow**：nuwa-skill README 安装节结构；creator-buddy README 既有「方式三：作为参考资料使用」措辞。
- **Test scenarios**：
  - 三式标题齐全且顺序为一/二/三（`rg -n "^### 方式[一二三]" README.md`）。
  - 方式一命令在干净环境可复制执行（以 U1 验证为准）。
  - 宿主表每行含宿主名、安装路径与命令三要素。
- **Verification**：根 README 三式骨架完整；旧「快速安装」块与旧「方式三：项目级」无残留。

### U3. evidence-first-writing README 安装节对齐

- **Goal**：包级安装节与根 README 三式骨架一致，保留本包特色通道。
- **Requirements**：R3
- **Dependencies**：U2
- **Files**：`evidence-first-writing/README.md`
- **Approach**：取消「快速安装（复制即装）」独立块，内容并入方式一；方式一改为 npx 一行 + `--skill evidence-first-writing`；宿主表精简为指向根 README 的链接；保留 Codex/OpenAI 代理（`agents/openai.yaml`）与 `$evidence-first-writing` 触发说明；验证节保留。
- **Test scenarios**：
  - 三式标题齐全；`--skill evidence-first-writing` 单装命令出现且语法正确。
  - Codex/OpenAI 代理说明与触发语未被误删。
- **Verification**：与根 README 骨架逐节对照一致；特色通道完整。
- **Test expectation: none -- 文档重构单元，无代码行为变化，结构自查即覆盖。**

### U4. leo-ppt-generator README 安装节对齐

- **Goal**：包级安装节与根 README 三式骨架一致，包级安装器降位为方式二内的包特色通道。
- **Requirements**：R3
- **Dependencies**：U2
- **Files**：`leo-ppt-generator/README.md`
- **Approach**：取消「快速安装（复制即装）」独立块，内容并入方式一；方式一改为 npx 一行 + `--skill leo-ppt-generator`；现有「方式二：包级安装器」表格并入新方式二，明确定位为「提供升级/卸载/稳定命令等 npx 未覆盖能力」的进阶通道；升级、卸载、故障排查节原样保留。
- **Test scenarios**：
  - 三式标题齐全；install.sh 宿主表（Codex/agents/claude/Windows）完整保留。
  - 卸载四步与钥匙串说明未被误删。
- **Verification**：与根 README 骨架逐节对照一致；包级安装器能力描述不丢失。
- **Test expectation: none -- 文档重构单元，无代码行为变化，结构自查即覆盖。**

### U5. creator-buddy README 安装节微调（vendored 边界内最小改写）

- **Goal**：安装节对齐三式骨架，改写面保持最小。
- **Requirements**：R3
- **Dependencies**：U2
- **Files**：`creator-buddy/README.md`
- **Approach**：取消「快速安装（复制即装）」独立块，内容并入方式一；方式一改为 npx 一行 + `--skill creator-buddy`；方式二精简并保留子技能执行目录说明；方式三已是同款措辞，仅核对一致性。改动限于 README 本土化改写面，不触上游文件；如后续上游同步覆盖此文件，按 UPSTREAM.md 流程重登记。
- **Test scenarios**：
  - 三式标题齐全；「从 `creator-buddy/` 目录执行」的相对路径约定说明保留。
- **Verification**：与根 README 骨架对照一致；`git status` 确认 creator-buddy 内除 README 外无文件改动。
- **Test expectation: none -- 文档重构单元，无代码行为变化，结构自查即覆盖。**

### U6. CHANGELOG 同步

- **Goal**：按仓库纪律记录本次安装文档重构。
- **Requirements**：R5
- **Dependencies**：U1、U2、U3、U4、U5
- **Files**：`CHANGELOG.md`
- **Approach**：在 Unreleased 段追加一条综合条目（`(user-visible)`），涵盖三式结构、U1 验证结论（含异常分支时的措辞调整）、引用本计划路径；不重排既有条目。
- **Test scenarios**：
  - 条目含 `(user-visible)` 标注与本计划仓库相对路径。
- **Verification**：CHANGELOG 与实际改动一一对应。
- **Test expectation: none -- 变更记录单元，无代码行为变化。**

---

## Verification Contract

| 检查项 | 命令/方式 | 适用单元 | 通过标准 |
|---|---|---|---|
| 通用安装器发现 | `npx skills add leo-kuang-ai/leo-skills --list`（或本地路径等价形式；无 `--list` 时按 U1 降级路径试装） | U1、U2 | 列出且仅列出三个顶层技能 |
| 三式骨架一致 | `rg -n "^#{3,4} 方式[一二三]" README.md evidence-first-writing/README.md leo-ppt-generator/README.md creator-buddy/README.md` | U2–U5 | 每份 README 三个标题齐全（包级标题层级允许保持各自现状） |
| 旧结构残留 | `rg -n "快速安装（复制即装）" README.md */README.md` | U2–U5 | 四份 README 均无独立快速安装块（内容并入各自方式一） |
| 仓库级检查 | `git diff --check`；`rg -n "TODO\|FIXME" --glob '!AGENTS.md'` | 全部 | 干净 |
| creator-buddy 边界 | `git status --short creator-buddy/` | U5 | 仅 README.md 改动 |

本计划无代码行为变更，不触发包级单测与 skill-up 评测门禁；行为性验证仅 U1 的安装器发现检查。若 U1 走异常分支，方式一相关宣称按 U1 记录降级，其余单元不受阻。

---

## Definition of Done

- 全局：四份 README 呈一致三式骨架；U1 验证结论（正常或异常分支）已记录并反映在方式一措辞与 CHANGELOG；CHANGELOG 含 `(user-visible)` 条目并引用本计划；`git diff --check` 干净；creator-buddy 内无 README 外改动。
- 逐单元：U1 产出可引用的发现清单；U2 根 README 无旧结构残留且贡献约定含双通道说明；U3/U4/U5 与根骨架一致且特色通道完整；U6 条目与改动一一对应。
- 清理：实施过程中产生的临时试装目录、实验性草稿段落全部移除，不留在最终 diff 中。
