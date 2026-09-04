# spec-first 中文实战手册（v1.0）

> 公众号「spec-first」关注钩子资产。用途：关注后回复【手册】领取；手册每章末尾带公众号二维码（转发自带涨粉）。
> 导出：本文档 → 飞书文档/PDF 后投放。数字口径：npm v1.15.1 Runtime Capability Catalog 与官网 Reference（2026-08-28 核对）。

---

## 导语：这本手册解决什么问题

你在 Claude Code / Codex 里让 AI 写代码，它说"完成了"，测试也绿了——但你不敢合并。

不是不信任模型，是说不清它按什么顺序做的、哪些要求被悄悄忽略、什么算"做完"。

spec-first 是一个开源的工程化 AI Coding harness（MIT，面向 Claude Code 与 Codex）：把需求、计划、执行、评审、验证证据连接成一条**留在仓库里的闭环**。宿主负责写代码，它负责保留意图、约束执行范围、让"完成"这个字受证据约束。

本手册 30 分钟读完，带你跑通第一条完整工作流。

**获取帮助：** GitHub 仓库提 Issue（见附录）；公众号后台留言。

---

## 第一章 认识 spec-first：三个数字一条链

**三个数字：** 17 个 workflow · 35 个 source skills · 26 个 agents（skill-local 研究员/守卫角色，随工作流按需调用）。

**一条信任链：** Intent → Spec → Plan → Tasks → Code → Review → Knowledge。

**五条规则（全体系的宪法）：**

1. **Evidence over confidence** — 完成声明必须有可追溯证据，不靠自信
2. **Gate the exits not the thinking** — 管住出口（提交/合并/发布），不管住思考
3. **Source first** — 真相源是仓库里的 checked-in 文档，不是会话记忆
4. **Bounded autonomy** — 模型在明确边界内自主
5. **Reversible learning** — 经验沉淀可修正、可废弃

**运行模型（分工铁律）：** 确定性事实归脚本（读源码、跑测试、查状态）；语义判断归 LLM（方案取舍、实现、评审）；副作用授权归人。

---

## 第二章 安装：三条命令

```bash
# 1. 安装 CLI
npm install -g spec-first

# 2. 环境体检（确认 CLI、宿主与项目环境）
spec-first doctor

# 3. 在你的仓库初始化（生成项目指导与宿主 runtime）
cd your-repo && spec-first init
```

初始化后重启宿主，运行 `spec-runtime-setup` 完成工作流所需的本地 runtime 就绪。

**前置要求：** Node.js ≥ 20、npm、Git、至少一个受支持宿主（Claude Code / Codex 主要支持；Kiro、Qoder 为 opt-in preview；Cursor、OpenCode 为 generated preview）。

---

## 第三章 首条工作流：从一句话到可复核交付

推荐第一次走最小闭环：**spec-brainstorm → spec-plan → spec-work**。

**第 1 步 · spec-brainstorm（收敛 WHAT）**
把一句粗想法对话式收敛成 requirements-only 计划：需求（R）、功能点（F）、验收标准（AE）。此阶段禁止讨论实现方式——想清楚之前不开写。

**第 2 步 · spec-plan（补 HOW）**
在同一份计划文档上补实现单元（U1…Un）、依赖与验证门禁，升级为 implementation-ready。大活可用 spec-write-tasks 派生任务包（源计划一变，任务包作废——单一真相源）。

**第 3 步 · spec-work（按证据执行）**
按当前源码实现，本地验证不可跳过，留下 diff + 测试 + 验证证据。完成声明受证据约束：验证缺失/失败/含糊，就不算完成。

**进阶链路（大活/团队）：** spec-prd（存量系统 PRD）→ spec-doc-review（文档评审）→ spec-code-review（结构化代码评审）→ spec-debug（因果链诊断）→ spec-compound（经验沉淀到 docs/solutions/）。

---

## 第四章 全景：8 个阶段怎么分工

| # | 阶段 | Workflow | 产物 | 回答的问题 |
|---|---|---|---|---|
| 1 | Idea/PRD | spec-brainstorm | 方向与边界文档 | 到底要什么 |
| 2 | Requirements | requirements-only plan | R/F/AE 可追踪 | 验收标准是什么 |
| 3 | Plan | spec-plan | 实现单元+门禁 | 怎么算做好 |
| 4 | Task Pack | spec-write-tasks | 依赖与 stop_if | 怎么交接 |
| 5 | Work | spec-work | diff + tests | 按当前源码做 |
| 6 | Review | spec-code-review | 结构化 findings | 风险在哪 |
| 7 | Evidence | verification gates | 日志/截图/记录 | 凭什么说完成 |
| 8 | Knowledge | spec-compound | docs/solutions/ | 经验怎么复用 |

**17 个 workflow 完整清单**（口径：npm v1.15.1 Runtime Capability Catalog，2026-08-28）：

| 段 | Workflow | 干什么 |
|---|---|---|
| 想清楚 | spec-ideate | 产品级构思，把模糊方向变成可评估的想法 |
| 想清楚 | spec-prd | 存量系统的 PRD 需求工程 |
| 想清楚 | spec-brainstorm | 对话收敛成 requirements-only 计划（R/F/AE） |
| 规划好 | spec-plan | 补 HOW：实现单元、依赖、验证门禁 |
| 规划好 | spec-write-tasks | 把定稿计划编译成可选任务包（计划变则作废） |
| 做出来 | spec-work | 按当前源码执行，留 diff + 测试 + 验证证据 |
| 做出来 | spec-code-review | 结构化代码评审（findings 分级） |
| 做出来 | spec-doc-review | 文档评审 |
| 做出来 | spec-debug | 因果链诊断，不从表象改代码 |
| 做出来 | spec-app-consistency-audit | App 一致性审计 |
| 做出来 | spec-dogfood | diff 范围内的自治浏览器 QA |
| 做出来 | spec-polish | 起 dev server，迭代浏览器可见的打磨 |
| 做出来 | spec-optimize | 指标驱动的迭代优化循环 |
| 沉淀 | spec-compound | 经验沉淀到 docs/solutions/（带失效条件） |
| 沉淀 | spec-compound-refresh | 刷新过期的 solution 文档 |
| 基建 | spec-runtime-setup | 安装、配置、验证工作流 runtime 就绪 |
| 基建 | spec-write-skill | 设计/编写项目自有的 Agent Skills |

另有 14 个 standalone skills（spec-explain、spec-handoff、spec-lfg、spec-pov、spec-strategy、spec-sweep 等）随装随用，不占 workflow 主链；4 个 agent-facing internal skills（spec-commit、spec-test-browser 等）由子代理直接调用。26 个 agents 是 skill-local 的研究员/守卫角色（如 spec-security-sentinel、spec-repo-research-analyst），随工作流按需加载，不需要单独安装。

---

## 第五章 案例解剖：官网页脚计数器的交付链

spec-first 官网页脚的访问量计数器不是装饰——它自己就是用 spec-first 交付的，全部产物固定回源 commit `b6261910`：

- **需求**：公开计数、优雅降级、基础防刷、不采集 IP/UA——四条在代码里各有落点
- **计划**：6 个实现单元、测试场景与部署前提
- **实现**：计数服务、前端组件、Nginx 与 PM2 部署链路
- **验证**：10 项 node:test + 6 项 Playwright 全部通过
- **诚实边界**：2 个未验证边界（独立 task pack、不同部署环境会话策略）显式保留，不包装成完成

页面上的 Decision Receipt 回答三问：**凭什么完成 / 哪里还可能错 / 证据在哪里**。

这就是"留成工程记录"的含义：结论可以被质询，未验证不会被伪装。

---

## 第六章 边界与常见问题

**它不承诺 AI 永远正确。** 它让每个判断有上下文、每次交付有验证、每个残余风险有明确位置。

**三种情况不需要它：**
1. 一次性 prompt，用完就扔
2. 仓库禁止写入（它的一切产物都以仓库为家）
3. 期待中心化流程引擎/任务管理平台（它不是，执行永远在本地）

**常见问题：**
- **和 Spec Kit / OpenSpec 什么关系？** 同属 spec-driven 大方向，三者在"规格先行"上共识，重心不同（下表，均为 2026-08 官方页面口径）：

| 维度 | spec-first | GitHub Spec Kit | OpenSpec |
|---|---|---|---|
| 维护方 | sunrain520（MIT 开源） | GitHub 官方（MIT） | Fission-AI（MIT） |
| 一句话定位 | 工程化 AI Coding harness：意图、计划、执行、评审、证据留在仓库 | 规格驱动开发（SDD）工具包：先定义要构建什么，再构建 | 轻量 SDD 框架：fluid not rigid，面向存量代码库 |
| 命令入口 | `spec-*`（17 个 workflow） | `/speckit.*`（constitution→specify→plan→tasks→implement→converge） | `/opsx:*`（explore→propose→apply→archive） |
| 制品结构 | 计划文档（R/F/AE + 实现单元 + 门禁）→ 可选任务包 → 验证证据 → solutions 沉淀 | spec / plan / tasks 文档 + constitution（项目原则） | `openspec/changes/<名称>/`（proposal/specs/design/tasks）→ archive |
| 特色机制 | 证据门禁（"完成"受证据约束）、多宿主同一 canonical source 投射、经验可沉淀可废弃 | extensions / presets / bundles 扩展体系，GitHub 生态集成 | Stores 跨仓库共享 spec（beta）、Requirement+Scenario 纯 Markdown |
| 安装 | `npm install -g spec-first`（Node ≥ 20） | `uv`/`pipx` + Python ≥ 3.11 | `npm i @fission-ai/openspec`（Node ≥ 20.19） |
| 支持宿主 | Claude Code / Codex 主要；Kiro、Qoder、Cursor、OpenCode preview | 30+ AI coding agent | 30+ AI assistant |

选型建议很朴素：三者不互斥。要 GitHub 官方生态和扩展体系，看 Spec Kit；要最轻的 spec 层和跨仓共享，看 OpenSpec；要"完成声明受证据约束"的完整工程闭环（需求→证据→沉淀），试 spec-first。

- **个人项目值得用吗？** 官网定位即"面向个人开发者与 AI 重度用户"。最小闭环三步就够，仪式感与规模匹配。
- **换了宿主要重学吗？** 不用。同一套 canonical source 向各宿主投射相同工作流。

---

## 附录：资源索引

- **GitHub**：github.com/sunrain520/spec-first（点 Star 是对作者最直接的支持）
- **官网**：spec-first.cn（Docs / Versions / Reference）
- **npm**：npmjs.com/package/spec-first
- **公众号**：spec-first（本手册更新在此发布）
- **微信交流群**：公众号后台回复【群】

**已发文章索引（公众号内可搜标题）：**
1. 《到底什么是 Harness？——不是让大脑更聪明，而是给它配齐装备、真能把活干成》
2. 《Spec-First：每次交付，怎样真正反哺下一次交付？》
3. 《Spec-First：一条真实需求，怎样从 Work Object 走到 Archived？》
4. 《Spec-First：不替换飞书、GitLab 和 CI，企业怎样低成本接入 AI？》

*版本 v1.0 · 2026-08-28 · 关注公众号 spec-first，回复【手册】获取最新版*
