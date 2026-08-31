# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 提供本仓库开发指引。

## 语言与治理

- **默认语言**：文档、注释、README 使用简体中文。技术术语、文件路径、标识符保持英文。
- **许可证**：MIT，详见 `LICENSE`。
- **变更记录纪律**：所有源文件变更必须同步更新 `CHANGELOG.md`（Keep a Changelog 格式）。面向用户的变更在条目后追加 `(user-visible)`。

## 仓库结构

本仓库是**两个独立技能包**的集合（见 `AGENTS.md`），通过 `.claude-plugin/marketplace.json` 作为 Claude Code 插件市场分发：

- `evidence-first-writing/` — 证据优先写作技能（`SKILL.md`、`references/`、`scripts/`、`tests/`、`evals/`、`agents/`）。
- `leo-ppt-generator/` — PPT 生成技能（`SKILL.md`、`references/`、`prompts/`、`scripts/`、`patches/`、`runtime/`、`evals/`、`agents/`）。
- `docs/` — 仓库级文档与配图。
- 各技能 `*-workspace/` — 评测运行的生成产物（设计上被 git-ignore）；`graphify-out/` 同为生成产物。
- `AGENTS.md` — 仓库级约定：每个顶层目录是独立技能包；文件命名、提交风格、测试期望均在其中。

## 构建 / 测试 / 评测命令

### 技能单元测试（Python）
```sh
python3 -m unittest discover -s evidence-first-writing/tests -p 'test_*.py'
```
运行单个测试文件：
```sh
python3 -m unittest evidence-first-writing.tests.test_factual_invariants
```

### 评测套件（skill-up CLI）
两技能均以各自 `evals/eval.yaml` 为评测入口（引擎 `claude_code`）：evidence-first-writing 31 个用例、leo-ppt-generator 9 个用例。
```sh
cd evidence-first-writing && skill-up run evals/eval.yaml
cd leo-ppt-generator && skill-up run evals/eval.yaml
cd <技能目录> && skill-up report evals/eval.yaml
cd <技能目录> && skill-up validate evals/eval.yaml
```
评测生成的工作区被 git-ignore，可自由重跑。

### 事实不变量检查器（独立运行）
跨宿主使用时需设置 `EVIDENCE_FIRST_WRITING_SKILL_DIR` 指向 `evidence-first-writing/`；未设置时自动降级。
```sh
python3 evidence-first-writing/scripts/check_factual_invariants.py before.md after.md
```

### 仓库级检查
```sh
rg -n "TODO|FIXME" --glob '!AGENTS.md'
git diff --check
python3 leo-ppt-generator/scripts/lint_style_briefs.py
```
新增风格 brief / 版式文件必须 lint 通过（warning 白名单仅限存量）。

## 架构一：证据优先写作技能

技能将写作拆解为**可分离的编辑阶段**（而非一条提示词直出终稿），工作流受门禁控制：

1. **四轴意图路由**（始终最先执行）：`lifecycle_intent × article_family × evidence_risk × collaboration_modifier` — 定义见 `evidence-first-writing/references/intent-routing.md`。
2. **门禁顺序**：意图路由 → 源证据审计 → 起草 → 事实不变量校验 → 编辑审查 → 个人声音 → 去模板化 → 发布就绪。
3. **事实不变量**由 `evidence-first-writing/scripts/check_factual_invariants.py` 提取（URL、Markdown 链接目标、证据 ID、数字、行内代码、中文引号），在每次改写/去 AI 模板化之后进行校验。
4. **硬性安全边界**：单篇文章的发布指标**绝不**可直接提升为可复用规则——即使作者明确要求。提升条件：≥2 次可比复现 + 反例检查。技能必须拒绝并记录 `stable_rule: none` / `hypothesis`；单组前后对比不得写成因果结论。

## 架构二：leo-ppt-generator 技能

以确定性 CLI runtime 为状态唯一来源的 PPTX 生成流水线：

1. **Gate 0 Office 信任**优先于一切规则：来源未知/未确认可信的 PPT/PPTX 一律原样返回 `blocked/untrusted_office_input`，禁止读取、扫描或净化。
2. **advise/execute 交互模式门禁**：咨询类请求直接查 Route 表回答，禁止启动 runtime 或读取输入文件。
3. **四条 Route**：`generate`（图片式）/ `direct-editable`(对象级可编辑) / `upgrade-full` / `upgrade-selected`。
4. **控制面五行合同**：route/status/reason_code/execution_eligibility/next_action 必须先于自然语言输出，字段值只能来自 CLI JSON 或用户明确输入。
5. **交付红线**：`status=completed` 不等于交付完成；只有 `delivery_readiness=accepted` 才能声称交付闭环。

## 关键引用文件

| 文件 | 用途 |
|---|---|
| `evidence-first-writing/SKILL.md` | 入口：触发条件、四轴路由、门禁顺序、审计字段 |
| `evidence-first-writing/TECHNICAL_DESIGN.md` | 跨宿主适配、降级契约、能力矩阵 |
| `evidence-first-writing/references/intent-routing.md` | 四轴路由与 operation 枚举定义 |
| `evidence-first-writing/references/article-workflows.md` | 各文章类型的生产流水线 |
| `evidence-first-writing/references/editorial-pipeline.md` | 顶层流水线节点、门禁、发布后复盘纪律 |
| `evidence-first-writing/references/workflow-contract.md` | 阶段间接口契约 |
| `evidence-first-writing/evals/known-issues.md` | 已知问题与待复验清单 |
| `leo-ppt-generator/SKILL.md` | 入口：Gate 0 信任门禁、advise/execute、Route 表、控制面合同 |
| `leo-ppt-generator/references/execution-contract.md` | 跨 Route 的 runtime、恢复与交付规则 |
| `leo-ppt-generator/evals/eval.yaml` | 9 用例行为评测入口 |

两个技能包各自的 `agents/openai.yaml` 均为其 Codex/OpenAI 宿主适配器。

## 多宿主支持

两技能核心流程均仅依赖 Markdown（宿主无关）。Shell/Python 脚本钩子绑定宿主：
- 各技能 `SKILL.md` + frontmatter 覆盖 Claude Code（个人级 / 项目级安装）。
- 各技能 `agents/openai.yaml` 覆盖 Codex / OpenAI。
- `references/portable-prompt.md` 覆盖零安装可移植用法。
- 宿主无法运行脚本时显式降级并记录（如 `factual_invariant_check: not_run`），绝不猜测路径。

## 贡献规范

- 提交信息：短祈使句，可选包作用域（如 `evidence-first-writing: add post-publish eval case`）。
- 每次提交限定一个技能或一个仓库级关注点。
- 提交前确认评测通过。

<!-- spec-first:lang:start -->
## 语言与治理策略
**语言设置：** `Chinese / 中文`
语言规则为绝对硬执行要求：除非用户在当前请求中明确要求其他语言、翻译、双语输出或保留原文，所有面向用户的新生成自然语言内容必须使用简体中文。
适用范围覆盖回答、状态更新、澄清问题、总结、评审、生成文档、需求、计划、任务、变更说明、commit message 和 PR 文案。
代码标识符、命令、路径、配置键、环境变量、API 名称、协议名、日志、工具输出和引用材料可以保留原文；围绕它们新增的解释、结论和说明仍按本语言设置输出。
skill、agent、模板、历史上下文或示例文本的原文语言不得覆盖本设置；新增代码注释也按本设置，只说明非显然意图。
### Workflow 入口治理
<!-- spec-first:workflow-entry:using-spec-first -->
- 在执行实质性工作前，加载当前宿主已安装的 `using-spec-first` skill；完整入口路由与边界由该 skill 提供。
<!-- spec-first:lang:end -->
