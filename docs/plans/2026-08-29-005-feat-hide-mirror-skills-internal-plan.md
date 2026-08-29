---
title: 镜像技能打 internal 标记以净化安装器默认发现 - Plan
type: feat
date: 2026-08-29
status: completed
artifact_contract: spec-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: spec-plan-bootstrap
execution: code
---

## Goal Capsule

- **目标**：裸 `npx skills add leo-kuang-ai/leo-skills`（不带 `-s`）的默认发现清单只含三个产品技能；镜像 spec-first 治理技能从默认发现隐藏、但保持显式可装与宿主本地加载不变。
- **推荐路径**：采用官方排除机制——给四棵镜像树（`.agents/`、`.claude/`、`.kiro/`；`.codex/` 无 SKILL.md）共 105 个镜像 SKILL.md 的 frontmatter 批量添加 `metadata.internal: true`；**不取消镜像入库**（f27e789 的「clone 即得治理」决策保留）；配幂等重放脚本应对 `spec-first update` 重生成覆盖。
- **决策焦点**：KTD1 官方 internal 机制替代入库取舍；KTD2 重生成持久化；KTD3 标记范围边界。
- **验证焦点**：标记前后 `--list` 对比（隐藏生效）、`INSTALL_INTERNAL_SKILLS=1` 可见性（语义正确）、宿主技能加载无回归、脚本幂等。
- **最大风险/边界**：`metadata.internal` 为文档级证据（官方 README），本仓库形态未实测——U1 单技能先行验证是前置门；宿主对附加 frontmatter 字段的兼容性需实测。若机制失效，条件分支转入 untrack 方案（见 Scope Boundaries）。
- **停止条件**：U1 实测 internal 标记不改变发现清单、或宿主加载因标记失效时，停止批量标记并回到条件分支。

---

## Product Contract

### Summary

用 vercel-labs/skills 官方的 `metadata.internal` 排除机制，把仓库内 105 个 spec-first 宿主镜像技能从通用安装器默认发现中隐藏，使方式一回归裸命令形态；镜像入库决策不动，clone-即得治理能力完整保留。

### Problem Frame

上一计划（`docs/plans/2026-08-29-004-docs-nuwa-style-install-plan.md`）的 U1 实测发现：仓库已提交的 `.agents/skills/` 等镜像树是 skills CLI 的标准容器目录，裸 `npx skills add` 会把约 36 个镜像技能与三个产品技能一并列出，方式一被迫采用 `-s` 圈定的过渡形态。该计划将「仓库侧适配」记为 Deferred 项，用户现在选择立项。后续研究（vercel-labs/skills README，2026-08-29 抓取）证实存在官方排除机制 `metadata.internal: true`：internal 技能默认从发现隐藏，`INSTALL_INTERNAL_SKILLS=1` 时仍可见可装——核心分叉（是否取消 f27e789 的镜像入库）因此自然消解。

### Requirements

**发现净化与能力保留**

- R1. 裸命令 `npx skills add leo-kuang-ai/leo-skills --list`（远端形态与本地仓库路径形态）的发现清单只含 `evidence-first-writing`、`leo-ppt-generator`、`creator-buddy`。
- R2. 镜像技能在 `INSTALL_INTERNAL_SKILLS=1` 环境下仍出现在发现清单（保持显式可装）；宿主从镜像目录本地加载技能的行为不受 `metadata.internal` 字段影响。

**持久化与文档闭环**

- R3. 标记操作幂等可重放：重放脚本入库（覆盖 `spec-first update` 重生成镜像后的标记丢失场景），仓库约定文档记录重放时机。
- R4. 四份 README 的方式一回归裸命令为主形态（`-s` 降为可选提示），镜像技能说明改为「默认隐藏、`INSTALL_INTERNAL_SKILLS=1` 显式安装」语义。
- R5. 变更同步 `CHANGELOG.md`（`(user-visible)` 标注）并引用本计划路径。

### Scope Boundaries

不做（本次确认排除）：

- 不取消镜像入库、不删除或移动任何镜像文件（f27e789 决策保留）。
- 不修改三个产品技能、creator-buddy 及其子技能的任何文件（后者不在容器目录内，本就不被发现）。
- 不修改 spec-first CLI 与 vercel-labs/skills 上游本体；不向上游提需求。
- 不引入新的宿主适配或安装通道。

#### Deferred to Follow-Up Work

- 条件分支（仅当 U1 验证 internal 机制失效时启用）：untrack 镜像树并补 `.gitignore`——反转 f27e789，新 clone 需 `spec-first init` 重建治理；属独立决策，不在本计划内预写细节。
- 向 spec-first 上游（sunrain520/spec-first）提议投影生成的 SKILL.md 默认携带 `metadata.internal: true`，从根上消除重放需求。
- 把「`--list` 只列三技能」纳入 AGENTS.md 仓库级检查清单。

---

## Planning Contract

### Key Technical Decisions

- KTD1. **采用官方 `metadata.internal: true` 排除机制，不动镜像入库**（session-settled: user-approved — 范围综合门呈现「官方机制优先，否则才动入库」分叉后确认）：标记使镜像技能默认隐藏且 `INSTALL_INTERNAL_SKILLS=1` 显式可装，f27e789 的 clone-即得治理与 dogfood 工作流零损失；拒绝的备选是 untrack 镜像（破坏 clone-即得能力）与维持 `-s` 文档过渡（不解决问题只绕开）。
- KTD2. **重生成持久化 = 仓库侧幂等脚本 + 约定条目**：`spec-first update` 会重生成镜像并抹掉标记（CLI 帮助证实），故重放脚本入库为根脚本、AGENTS.md 记录「update 后重跑」约定；不依赖手动重打。架构姿态 **extend**——扩展 f27e789 建立的镜像入库工作流，不新建边界；脚本是薄维护工具，只负责 frontmatter 字段注入与幂等，不拥有镜像内容。
- KTD3. **标记范围 = 四棵镜像树全部 SKILL.md**（`.agents/` 35 + `.claude/` 35 + `.kiro/` 35，`.codex/` 0）：镜像树经勘察只含 spec 系技能，整树标记安全且对未来新增镜像自动覆盖；产品技能位于仓库顶层不在树内，天然豁免。不逐棵挑选、不依赖「哪些容器目录实际被扫描」的精确判定——整树标记使该问题无关紧要。

### Evidence & Limitations

- vercel-labs/skills README（2026-08-29 二次抓取，no_cache）：`metadata.internal` 隐藏语义、`INSTALL_INTERNAL_SKILLS=1` 显式通道、frontmatter 形态——支撑 KTD1。局限：文档级证据，本仓库形态未实测，U1 前置验证。
- f27e789 提交信息与文件统计：镜像入库是「clone 即得 using-spec-first 入口治理」的有意决策（约 1.4k 文件）——支撑「不动入库」的取舍方向。
- 本地勘察（2026-08-29）：四棵树 SKILL.md 计数与内容归属（仅 spec 系）、镜像 frontmatter 现无 metadata 块、`spec-first update` 刷新运行时资产——支撑 KTD2/KTD3。
- 工作区状态：存在大量未提交改动（含 004 计划的 README/CHANGELOG 改动尚未提交）；本计划实施将叠加其上，实施时不得混入或重排他人 hunks。
- 未确证点：宿主（Claude Code / ZCode / Codex）对附加 `metadata` frontmatter 字段的兼容性——预期忽略未知字段（低风险），U1 实测确认。

---

## Implementation Units

### U1. 单技能先行验证 internal 标记（前置门）

- **Goal**：在批量标记前实测 `metadata.internal` 在本仓库形态下的三项语义：默认隐藏、环境变量可见、宿主加载无害。
- **Requirements**：R1、R2
- **Dependencies**：无
- **Files**：临时修改单个镜像技能（如 `.agents/skills/spec-work/SKILL.md`）的 frontmatter 用于验证，验证后还原；无持久源文件变更。
- **Approach**：给单个镜像 SKILL.md 加 `metadata.internal: true` → 本地路径 `--list` 确认该技能从清单消失 → `INSTALL_INTERNAL_SKILLS=1` 下 `--list` 确认重新出现 → 在宿主会话确认该技能仍可正常调用（frontmatter 附加字段无害）→ 还原临时改动。
- **Execution note**：先冒烟后批量——三项语义任一不符即触发停止条件，转入 Deferred 条件分支，不进入 U2。
- **Test scenarios**：
  - 预期路径 A：标记后 `--list` 清单中该技能名消失、三个产品技能仍在。
  - 预期路径 B：`INSTALL_INTERNAL_SKILLS=1` 下该技能名回到清单。
  - 预期路径 C：宿主技能调用（本会话或 Claude Code `/skills`）不受影响。
  - 异常路径：标记后清单不变（机制对本仓库形态失效）或宿主加载报错 → 停止批量、记录偏离、走条件分支。
- **Verification**：三项语义各有可引用的实测输出；异常时有明确记录。

### U2. 幂等标记脚本与全量标记

- **Goal**：重放脚本入库并对四棵镜像树全部 SKILL.md 完成标记。
- **Requirements**：R3、R1
- **Dependencies**：U1
- **Files**：`scripts/mark-mirror-skills-internal.py`（新增）、`.agents/**`、`.claude/**`、`.kiro/**` 下的 SKILL.md（批量修改）、`AGENTS.md`（补约定条目）
- **Approach**：脚本遍历四棵镜像树（含 `.codex/` 以备未来出现 SKILL.md），对每个 SKILL.md frontmatter 注入 `metadata.internal: true`：已有 metadata 块则合并键、无则新建块；已标记则跳过（幂等）；非镜像树文件不触碰。AGENTS.md 在仓库约定处补一条：`spec-first update` 重生成镜像后须重跑该脚本；AGENTS.md 为预存脏文件，采用最小插入策略、不触碰既有 hunks。
- **Patterns to follow**：仓库脚本风格（清晰失败、无机器特定路径、python3 标准库，参照 `evidence-first-writing/scripts/` 既有脚本）。
- **Test scenarios**：
  - 首跑：105 个 SKILL.md 全部获得标记，其他文件零改动（`git status` 核对）。
  - 幂等：连续重跑两次，第二次 `git diff` 为空。
  - 边界：含既有 `metadata` 块的 frontmatter 合并不破坏原键；frontmatter 缺失或畸形的文件清晰失败并列名。
  - 范围豁免：产品技能与 creator-buddy 文件不被触碰。
- **Verification**：全量标记完成且可重放；`git status` 改动集与声明范围一致。

### U3. 终态验证：默认发现净化与裸命令回归

- **Goal**：确认仓库终态满足 R1/R2 的完整语义，为 README 回改提供实测依据。
- **Requirements**：R1、R2
- **Dependencies**：U2
- **Files**：无源文件修改；验证记录进入 U5 的 CHANGELOG 条目。
- **Approach**：本地仓库路径 `--list` 只列三技能；`INSTALL_INTERNAL_SKILLS=1` 下镜像技能可见；裸命令（无 `-s`）试装于临时目录确认交互清单干净、可正常安装三技能，装后清理。
- **Execution note**：远端 GitHub 形态的验证依赖推送后进行——实施时若未推送，以本地路径形态为准并在 CHANGELOG 注明「远端复验待推送后」，不宣称远端已实测。
- **Test scenarios**：
  - 预期路径：`--list` 恰好三技能；`INSTALL_INTERNAL_SKILLS=1` 清单含镜像技能。
  - 预期路径：临时目录裸命令试装成功装出三技能（或交互选择界面只呈现三技能）。
  - 异常路径：仍有镜像技能漏出（如 `.claude/` 非容器路径文件被发现）→ 补充标记该路径后复验。
- **Verification**：两种环境变量的清单输出与试装结果均可引用；「已实测」标注以此为据。

### U4. README 方式一回归裸命令形态

- **Goal**：四份 README 的方式一以裸命令为主形态，镜像技能说明切换为「默认隐藏」语义。
- **Requirements**：R4
- **Dependencies**：U3
- **Files**：`README.md`、`evidence-first-writing/README.md`、`leo-ppt-generator/README.md`、`creator-buddy/README.md`
- **Approach**：主命令改为裸 `npx skills add leo-kuang-ai/leo-skills`（保留单装 `-s` 变体行）；删除「不带 `-s` 会被一并列出、勾选跳过」的过渡 bullet，替换为「镜像治理技能默认隐藏，`INSTALL_INTERNAL_SKILLS=1` 可显式安装」；「已实测」标注仅保留在 U3 验证覆盖的命令上；三式骨架与 004 计划的验证检查保持兼容。
- **Patterns to follow**：004 计划建立的包级精简模式（根 README 全量、包级引用）。
- **Test scenarios**：
  - 三式骨架检查（`rg "^#{3,4} 方式[一二三]"`）四份 README 仍然全过。
  - 根 README 无 `-s 圈定` 主命令残留；镜像说明含 `INSTALL_INTERNAL_SKILLS=1`。
- **Verification**：与 004 的骨架/残留检查逐项复验通过。
- **Test expectation: none -- 文档重构单元，结构自查即覆盖。**

### U5. CHANGELOG 同步

- **Goal**：按仓库纪律记录本次适配。
- **Requirements**：R5
- **Dependencies**：U1、U2、U3、U4
- **Files**：`CHANGELOG.md`
- **Approach**：Unreleased 段追加一条综合条目（`(user-visible)`）：internal 标记机制、标记范围、重放脚本与约定、U1/U3 验证结论（远端复验条件如实注明）、引用本计划路径；不重排既有条目。
- **Test scenarios**：
  - 条目含 `(user-visible)` 与本计划仓库相对路径。
- **Verification**：条目与实际改动一一对应。
- **Test expectation: none -- 变更记录单元。**

---

## Verification Contract

| 检查项 | 命令/方式 | 适用单元 | 通过标准 |
|---|---|---|---|
| 默认发现净化 | `npx skills add <仓库路径> --list`（远端形态待推送后复验） | U1、U2、U3 | 清单恰好三个产品技能 |
| 显式可见性 | `INSTALL_INTERNAL_SKILLS=1 npx skills add <仓库路径> --list` | U1、U3 | 镜像技能回到清单 |
| 裸命令试装 | 临时目录裸命令安装后清理 | U3 | 只呈现并装出三技能 |
| 脚本幂等 | 连续重跑标记脚本后 `git diff` | U2 | 第二次运行为空 diff |
| 标记范围 | `git status --short` 对照四棵镜像树与豁免面 | U2 | 仅镜像树 SKILL.md 与脚本/约定文件改动 |
| 三式骨架兼容 | `rg -n "^#{3,4} 方式[一二三]" README.md */README.md` | U4 | 四份 README 各三标题 |
| 仓库级检查 | `git diff --check`；`rg -n "TODO\|FIXME" --glob '!AGENTS.md'` | 全部 | 干净 |

本计划为仓库配置/文档变更，不触发包级单测与 skill-up 评测门禁；行为性验证集中在 U1/U3 的安装器实测。若 U1 走异常分支，U2–U4 停止，仅记录验证结论与条件分支建议。

---

## Definition of Done

- 全局：裸命令默认发现只含三技能（本地实测；远端复验或如实注明待推送）；`INSTALL_INTERNAL_SKILLS=1` 显式通道可用；宿主加载无回归；重放脚本幂等且 AGENTS.md 有重放约定；四份 README 方式一为裸命令主形态；CHANGELOG 含 `(user-visible)` 条目并引用本计划；`git diff --check` 干净。
- 逐单元：U1 三项语义实测记录在案；U2 全量标记 + 幂等 + 范围核对；U3 两种清单输出可引用；U4 骨架检查复验通过；U5 条目与改动对应。
- 清理：U1 的临时单技能改动已还原；试装临时目录已删除；无实验性残留进入最终 diff。
