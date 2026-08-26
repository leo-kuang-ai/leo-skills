# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 提供本仓库开发指引。

## 语言与治理

- **默认语言**：文档、注释、README 使用简体中文。技术术语、文件路径、标识符保持英文。
- **许可证**：MIT，详见 `LICENSE`。
- **变更记录纪律**：所有源文件变更必须同步更新 `CHANGELOG.md`（Keep a Changelog 格式）。面向用户的变更在条目后追加 `(user-visible)`。

## 仓库结构

- `evidence-first-writing/` — 唯一技能包，结构遵循 `AGENTS.md`（`SKILL.md`、`references/`、`scripts/`、`tests/`、`evals/`、`agents/`）。
- `evidence-first-writing-workspace/` — 评测运行的生成产物（设计上被 git-ignore）。
- `graphify-out/` — 图结构生成产物。
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
评测配置位于 `evidence-first-writing/evals/eval.yaml`（20 个用例，引擎 `claude_code`）。
```sh
cd evidence-first-writing && skill-up run evals/eval.yaml
cd evidence-first-writing && skill-up report evals/eval.yaml
cd evidence-first-writing && skill-up list-cases evals/eval.yaml
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
```

## 架构：证据优先写作技能

技能将写作拆解为**可分离的编辑阶段**（而非一条提示词直出终稿），工作流受门禁控制：

1. **四轴意图路由**（始终最先执行）：`lifecycle_intent × article_family × evidence_risk × collaboration_modifier` — 定义见 `references/intent-routing.md`。
2. **门禁顺序**：意图路由 → 源证据审计 → 起草 → 事实不变量校验 → 编辑审查 → 个人声音 → 去模板化 → 发布就绪。
3. **事实不变量**由 `scripts/check_factual_invariants.py` 提取（URL、Markdown 链接目标、证据 ID、数字、行内代码、中文引号），在每次改写/去 AI 模板化之后进行校验。
4. **硬性安全边界**：单篇文章的发布指标**绝不**可直接提升为可复用规则——即使作者明确要求。提升条件：≥2 次可比复现 + 反例检查。技能必须拒绝并记录 `stable_rule: none` / `hypothesis`。

## 关键引用文件

| 文件 | 用途 |
|---|---|
| `evidence-first-writing/SKILL.md` | 入口：触发条件、四轴路由、门禁顺序、审计字段 |
| `evidence-first-writing/TECHNICAL_DESIGN.md` | 跨宿主适配、降级契约、能力矩阵 |
| `references/intent-routing.md` | 四轴路由定义 |
| `references/article-workflows.md` | 各文章类型的生产流水线 |
| `references/editorial-pipeline.md` | 顶层流水线节点、门禁、发布后复盘纪律 |
| `references/voice-profiles.md` | 个人声音档案的建立、验证与使用 |
| `references/humanizer-patterns.md` / `humanizer-pattern-catalog.md` | Humanizer 模式与多轮收敛 |
| `references/workflow-contract.md` | 阶段间接口契约 |
| `agents/openai.yaml` | Codex/OpenAI 宿主适配器 |
| `evals/known-issues.md` | 已知问题与待复验清单 |

## 多宿主支持

核心流程仅依赖 Markdown（宿主无关）。Shell 脚本钩子绑定宿主：
- `SKILL.md` 覆盖 Claude Code（个人级 / 项目级安装）。
- `agents/openai.yaml` 覆盖 Codex / OpenAI。
- `references/portable-prompt.md` 覆盖零安装可移植用法。
- 宿主无法运行不变量检查器时，自动降级为 `factual_invariant_check: not_run`。

## 贡献规范

- 提交信息：短祈使句，可选包作用域（如 `evidence-first-writing: add post-publish eval case`）。
- 每次提交限定一个技能或一个仓库级关注点。
- 提交前确认评测通过。
