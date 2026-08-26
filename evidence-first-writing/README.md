# evidence-first-writing

证据优先写作 Skill：先识别写作意图、文章类型、证据风险和协作方式，再编排调研、论证、起草、编辑、个人声音、技术验证、营销文案和去 AI 模板感的多阶段工作流。作者始终拥有事实、判断与取舍的最终控制权。

## 前置条件

- **Claude Code**（推荐）：本地运行 `claude` CLI。
- **Codex / OpenAI 格式**：额外提供 `agents/openai.yaml` 代理定义。
- 无需安装额外包；`scripts/` 里的 Python 脚本只需标准库。

## 安装

> 官方推荐用 Claude Code 的 `/plugin` 系统远程安装（已实测通过）。Git clone + 软链是备选。

### 方式一：Claude Code `/plugin`（推荐，已实测）

仓库已配置 Claude Code 插件市场（`.claude-plugin/marketplace.json`），在 Claude Code 会话中：

```text
/plugin marketplace add sunrain520/leo-skills
/plugin install evidence-first-writing
```

- `marketplace add` 从 GitHub clone 到 `~/.claude/plugins/marketplaces/leo-skills/`；
- `plugin install` 把 skill 装到 `~/.claude/plugins/cache/leo-skills/evidence-first-writing/0.1.0/`，并注册为用户级 Personal Skill（Claude Code 启动时自动扫描）；
- 更新：推送新版本后执行 `/plugin update evidence-first-writing`（或先 `/plugin marketplace update` 再 update）；
- 卸载：`/plugin uninstall evidence-first-writing`。

### 方式二：Git clone + 软链（备选）

从 GitHub 拉取本仓库并软链该 skill 到 `~/.claude/skills/`：

```sh
git clone https://github.com/sunrain520/leo-skills.git ~/.claude/skills/leo-skills
ln -s ~/.claude/skills/leo-skills/evidence-first-writing ~/.claude/skills/evidence-first-writing
```

`git clone` 装下整个技能集合；软链让 Claude Code 能识别本 skill，且拉取后 `git pull` 即更新。
只装单独一份、不保留仓库的临时做法：

```sh
git clone --depth 1 https://github.com/sunrain520/leo-skills.git /tmp/leo-skills
cp -R /tmp/leo-skills/evidence-first-writing ~/.claude/skills/
rm -rf /tmp/leo-skills
```

### 方式三：项目级（跟随仓库，团队共享）

在项目根目录建立（例如 `git submodule add https://github.com/sunrain520/leo-skills.git .claude/skills/leo-skills`
再软链），或直接提交：

```text
<your-project>/.claude/skills/evidence-first-writing/
    ├── SKILL.md
    ├── references/   # 按需加载的流程与契约
    ├── scripts/      # 事实不变量检查脚本
    ├── tests/        # 包级单元测试
    └── evals/        # skill-up 评测定义
```

### Codex / OpenAI 代理

`agents/openai.yaml` 声明了该能力，供 Codex/OpenAI 格式的 Agent 按 `interface` 字段加载为「证据优先写作」工具。
Codex 不依赖插件系统，在 Codex 会话中直接用代理触发语：

```text
$evidence-first-writing 识别我的写作意图和文章类型，进入合适 workflow 完成文章。
```

## 验证安装

在 Claude Code 会话中：

- 输入 `/skills`，应看到 `evidence-first-writing`；或
- 直接用触发语发起一次写作请求，若被路由到本 Skill 即安装成功。

跑包级测试确认脚本可用：

```sh
cd evidence-first-writing
python3 -m unittest discover -s tests -p 'test_*.py'
```

## 使用

触发一段自然语言写作请求即可。SKILL 会先在内部冻结**四轴路由**：

| 轴 | 取值 |
|---|---|
| `lifecycle_intent` | 新写 / 调研 / 定主张结构 / 起草 / 修订 / 审查 / 去模板 / 声音建模 / 发布复盘 |
| `article_family` | 观点评论 / 研究解释 / 教程 / How-to / 技术 Reference / 技术 Explanation / 案例复盘 / 个人叙事 / Newsletter / 正式报告 / 产品营销文案 / `not_applicable` |
| `evidence_risk` | 事实密度、影响范围、时效性、发布不可逆性 |
| `collaboration_modifier` | 直接执行 / 逐节共创 / 声音档案 / 渠道适配 / 是否落盘 |

据此推断 `operation` 与 `depth`：

- `depth`：`quick`（低风险局部任务）/ `standard`（默认文章）/ `deep`（高影响、强事实、精品稿）。
- `operation`：`full`、`research`、`shape`、`draft`、`revise`、`audit`、`humanize`、`coauthor`、`hooks`、`voice`、`train-voice`、`evaluate-voice`、`copywriting`、`docs`、`tool-select`、`personal-context`、`post-publish`。

常见入口：

```text
# 从 0 到 1 写一篇观点文
使用 evidence-first-writing 帮我写一篇关于远程办公的评论，面向技术团队。

# 只审查不改写
用 evidence-first-writing 审查这篇文章的事实、结构和读者路径，只报告不修改。

# 复盘已发布数据
用 evidence-first-writing 复盘这篇公众号文章的阅读数据，看标题公式是否有效。
```

路由和门禁说明随 `response` 给出，正文交付时附简短编辑说明（所用 operation、实际运行阶段、影响结果的假设、未解决/有争议的主张、相关检查）。

## 宿主适配

本 Skill 与宿主/model 无关——核心是 `SKILL.md` 与 `references/` 里的 markdown 指令，任何能读文件并遵循指令的
模型都可执行。每个宿主只加一层薄适配器，唯一真正绑定宿主的是脚本钩子。

| 宿主 | 接入载体 | 触发方式 | 宿主能力 |
|---|---|---|---|
| Claude Code | `SKILL.md`（个人/项目级安装） | 自然语言请求、`/skills` | 按需加载 `references/`；通过 `$EVIDENCE_FIRST_WRITING_SKILL_DIR` 运行脚本 |
| Codex / OpenAI | `agents/openai.yaml` | `$evidence-first-writing`（`default_prompt`） | 同一 `references/` 作为指令被模型读取 |
| 其它 / 零安装 | `references/portable-prompt.md` | 复制提示词粘贴 | 无文件系统依赖，能力最弱 |

**降级契约（宿主差异不破坏交付）：**

- 流程逻辑是 markdown 指令，随宿主执行；只有 `scripts/check_factual_invariants.py` 依赖文件系统 + python +
  `$EVIDENCE_FIRST_WRITING_SKILL_DIR`。
- 宿主无法确定已加载 Skill 路径时，`SKILL.md` 要求记录 `factual_invariant_check: not_run` 并说明原因，再人工核对
  语义；**不得在用户项目里猜测 `scripts/` 路径**。
- `post-publish` 持久写入需用户授权 + 目标路径；否则 `persistence: not_run`，只登记为观察/假设。
- 声音档案、`soul.md`、渠道档案按宿主可用性读取；读不到时按「无档案」降级，只用临时语域，不声称学会个人声音。

### Codex 使用示例

`agents/openai.yaml` 声明了代理；用其 `default_prompt` 触发（`$evidence-first-writing` 为该代理占位符）：

```text
$evidence-first-writing 识别我的写作意图和文章类型，进入合适 workflow 完成文章。
```

Codex 宿主同样读取 `references/` 各流程契约；脚本/环境变量不可用时走上述降级。

## 关键文件

| 路径 | 用途 |
|---|---|
| `SKILL.md` | 入口：触发条件、四轴路由、operation/depth、门禁顺序、审计信息 |
| `agents/openai.yaml` | Codex / OpenAI 代理声明 |
| `references/intent-routing.md` | 四轴 route 定义 |
| `references/article-workflows.md` | 各文章类型的生产主轴 |
| `references/editorial-pipeline.md` | 顶层流水线节点、门禁与发布后复盘纪律 |
| `references/voice-profiles.md` | 个人声音档案的建立、验证与使用 |
| `references/copywriting.md` / `technical-docs.md` | 营销文案 / Diataxis 技术文档 |
| `references/humanizer-patterns.md` | Humanizer 模式与多轮收敛 |
| `references/tool-selection.md` | 可选写作/Humanizer 工具选择 |
| `references/personal-context.md` / `portable-prompt.md` | 个人说明书 / 可移植提示词 |
| `scripts/check_factual_invariants.py` | 改写前后的事实不变量校验（需设置 `EVIDENCE_FIRST_WRITING_SKILL_DIR`） |
| `tests/test_factual_invariants.py` | 包级单元测试 |
| `evals/eval.yaml` + `evals/cases/` | `skill-up` 评测配置与用例 |
| `evals/known-issues.md` | 已知问题与待复验清单 |

## 测试与评测

```sh
# 单元测试
python3 -m unittest discover -s tests -p 'test_*.py'

# 行为评测（需 skill-up CLI 与可用引擎）
skill-up validate evals/eval.yaml
skill-up run evals/eval.yaml --engine claude_code
```

评测工作区（`evidence-first-writing-workspace/`）在 `.gitignore` 中，不提交。

## 约束

- 全程区分已核实事实、有来源解释、作者判断、个人经历，不把一类升级成另一类，不编造来源/引语/数据。
- `audit` 冻结为只读；持久写入（声音档案、记忆、项目文件）必须获得授权与目标路径。
- `post-publish` 默认只分析；单篇表现只能登记为观察与假设，不得在复现与反例检查前升级为稳定规则。
