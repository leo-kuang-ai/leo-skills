# 仓库约定 Repository Guidelines

## 语言与治理

- **默认语言**：文档、注释、README 使用简体中文；技术术语、文件路径、标识符保持英文。
- **许可证**：MIT，详见 `LICENSE`。
- **变更记录纪律**：所有源文件变更必须同步更新根目录 `CHANGELOG.md`（Keep a Changelog 格式）；面向用户的变更在条目后追加 `(user-visible)`。
- 各技能包在 `SKILL.md` 或包级 `README.md` 中自行声明触发条件、工作流、约束与本包命令。Claude Code 专属开发指引（技能架构、门禁、评测命令）见 `CLAUDE.md`，与本文件保持一致。

## 项目结构与模块组织

本仓库是若干个独立技能包的集合。每个技能放在自己的顶层目录，使用小写 kebab-case 名称，如 `evidence-first-writing/`、`leo-ppt-generator/`。除非共享契约已在文档中显式声明，否则不要在兄弟技能之间建立运行时依赖。

当前顶层目录与产物：

- `evidence-first-writing/` — 证据优先写作技能。
- `leo-ppt-generator/` — 图片式 / 可编辑 / 升级 PPTX 生成技能。
- `creator-buddy/` — vendored 创作工具箱插件（公众号 / 小红书 / 视频，上游来源与同步见 `creator-buddy/UPSTREAM.md`）。
- `docs/` — 仓库级文档。
- `*-workspace/` — 评测运行的生成产物（设计上被 git-ignore）。
- `graphify-out/` — 图结构生成产物。

`creator-buddy/` 是 vendored 所有权边界：根目录总控 `SKILL.md` + `gzh-Skills/`、`xhs-Skills/`、`video-Skills/` 三组共 32 个子技能；内部跨组引用（共享文风档案、视觉系统、脚本复用等）在该边界内豁免"兄弟技能不建立运行时依赖"与 kebab-case 命名约束；`SKILL.md` 中的相对路径命令一律从 `creator-buddy/` 目录执行。除已在 `UPSTREAM.md` 登记的本土化改写（README 系列、文风档案模板化）外不修改上游文件，本地适配通过新增文件（`.claude-plugin/plugin.json`、`LICENSE`、`UPSTREAM.md`）完成；上游同步整目录覆盖并保留本地改写，见 `creator-buddy/UPSTREAM.md`。该包暂不接入 skill-up 评测门禁（上游为 skillhub `evals/evals.json` 格式）。

一个典型技能包应包含：

- `SKILL.md`：入口、触发条件、工作流、约束。
- `scripts/`：技能使用的可执行辅助脚本。
- `references/`：按需加载的支持说明或领域材料。
- `assets/` 或 `templates/`：复制到生成产物的可复用文件。
- `tests/` 或 `evals/`：包级行为检查与 fixture（`evals/eval.yaml` 为 skill-up 评测入口）。

不要将生成产物、缓存、凭据、本地配置或临时评测工作区提交进仓库。

## 构建 / 测试 / 评测命令

仓库没有统一的构建或测试运行器；请从对应技能目录运行包级命令。

### 技能单元测试（Python，evidence-first-writing）

```sh
python3 -m unittest discover -s evidence-first-writing/tests -p 'test_*.py'
python3 -m unittest evidence-first-writing.tests.test_factual_invariants
```

### 评测套件（skill-up CLI）

两技能均以 `evals/eval.yaml` 为入口，引擎默认 `claude_code`：

```sh
cd evidence-first-writing && skill-up run evals/eval.yaml
cd leo-ppt-generator && skill-up run evals/eval.yaml
cd <skill> && skill-up report evals/eval.yaml
cd <skill> && skill-up list-cases evals/eval.yaml
```

评测生成的工作区被 git-ignore，可自由重跑。

### 证据事实不变量检查器（evidence-first-writing，独立运行）

跨宿主使用需设置 `EVIDENCE_FIRST_WRITING_SKILL_DIR` 指向 `evidence-first-writing/`；未设置时自动降级。

```sh
python3 evidence-first-writing/scripts/check_factual_invariants.py before.md after.md
```

### 仓库级检查

```sh
find . -mindepth 2 -maxdepth 2 -name SKILL.md
rg -n "TODO|FIXME" --glob '!AGENTS.md'
git diff --check
```

`spec-first update` 重生成宿主镜像（`.agents/`、`.claude/`、`.codex/`、`.kiro/`）后，须重跑 `python3 scripts/mark-mirror-skills-internal.py`，保持镜像技能对 `npx skills add` 通用安装器默认隐藏（`metadata.internal: true`）。

### 风格库 lint（leo-ppt-generator）

```sh
python3 leo-ppt-generator/scripts/lint_style_briefs.py        # brief 结构 lint（ERROR 非 0 退出）
python3 leo-ppt-generator/scripts/lint_layout_grid.py         # 版式网格/双约束 lint（在技能目录内运行）
```

新增风格 brief / 版式文件必须两条 lint 全过（warning 白名单仅限存量，见
`leo-ppt-generator/scripts/style-lint-baseline.txt` 收敛纪律）。

提交前，请从对应技能目录运行包级格式化、测试与评测，并确认通过。

## 编码风格与命名

- YAML 和 JSON 使用两个空格缩进；实现语言遵循其 formatter 标准。
- 优先使用 ASCII 文件名与 UTF-8 内容；目录用 `lowercase-kebab-case`，shell 变量用 `snake_case`，fixture 名要有描述性。
- 指示直接、祈使式。脚本应清晰失败、避免机器特定的绝对路径，并通过文档化环境变量暴露所需配置。
- 新代码注释使用英文，仅解释非常规意图。

## 测试准则

测试属于其校验的技能。应覆盖触发行为、主成功工作流、无效输入与重要的安全边界。用例按可观察行为命名，例如 `rejects-missing-source`。不要仅把安装或静态校验当作技能可工作的证明；行为评测需记录确切命令与结果。安全门禁类断言应使用"否定感知"的匹配（如 judge 脚本对 `未读取文件` / `不会：- …` 等表述做否定过滤），避免对健康响应误判。

## 提交与合并请求

- 提交信息：短祈使句，可选包作用域，如 `evidence-first-writing: add post-publish eval case`。
- 每次提交限定一个技能或一个仓库级关注点。
- 提交前确认该技能评测通过，并记录验证命令与结果。
- 合并请求应指出受影响包、解释行为变更、列出验证命令与结果、链接相关问题；仅当输出展示方式变化时才附截图或样例产物。

## 安全与 Agent 专属说明

- 绝不提交密钥、token、个人数据或本地配置。
- 把每个顶层技能当作一个所有权边界：只检查与修改被请求的包，保留无关工作，并在做出任何不可避免的跨包影响前报告。

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
