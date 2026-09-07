# Leo Skills

可复用的智能体技能集合，兼容 Claude Code 与 Codex / OpenAI 双宿主，覆盖证据优先写作、内容编辑、PPT 演示生成，以及公众号 / 小红书 / 视频创作工具箱。

## 包含技能

### `evidence-first-writing`

先识别写作意图、文章类型、证据风险和协作方式，再编排调研、论证、起草、编辑、个人声音、技术验证、营销文案与去 AI 模板感的多阶段工作流，并提供选题势能、读者模型、内容资产等创作者化能力层。作者保留事实、判断与取舍的最终控制权。

- 入口：[evidence-first-writing/SKILL.md](evidence-first-writing/SKILL.md)
- 安装与用法：[evidence-first-writing/README.md](evidence-first-writing/README.md)
- 评测：33 个用例（`evals/cases/`）
- 脚本工具链：事实不变量校验（`check_factual_invariants.py`）、中文模板味确定性检查（`check_prose.py`）、可选 STORM 多视角研究执行器（`storm_research.py`）

### `leo-ppt-generator`

从文章、报告、笔记或大纲生成图片式演示文稿，把图片、PDF 或可信 Office 输入重建为对象级可编辑 PPTX，或将既有图片式演示升级为 editable/hybrid 版本。技能包内含确定性 Python 运行时（`runtime/`）、137 个可加载风格 brief 的参考风格库（`references/styles/`）、受控补丁与评测用例，并提供本地安装脚本。

- 入口：[leo-ppt-generator/SKILL.md](leo-ppt-generator/SKILL.md)
- 本地安装：[install.sh](leo-ppt-generator/install.sh)（macOS/Linux）、[install.ps1](leo-ppt-generator/install.ps1)（Windows）
- 评测：59 个用例（`evals/cases/`）
- 质量闭环：`delivery receipt create|verify` 交付指纹收据、母版内容合同校验、图像版本历史（`--keep-versions` / `set-active`）与提示词进化记账（`prompts/registry.yaml`）

### `creator-buddy`

公众号 / 小红书 / 视频全栈创作工具箱（vendored 集成）。根目录总控 Skill 负责路由：先做平台情报（全域内容搜索、爆款检测、赛道分析、博主与文章拆解），再把选题做成成品（定位、长短文写作、标题、封面、配图、排版、视频脚本、剪辑、B-roll、字幕、配音配乐），共 32 个子技能分三组，保持上游内部结构原样。

- 入口：[creator-buddy/SKILL.md](creator-buddy/SKILL.md)；相对路径命令从 `creator-buddy/` 目录执行
- 上游同步方式：[creator-buddy/UPSTREAM.md](creator-buddy/UPSTREAM.md)
- 平台凭据（`GUAIKEI_API_TOKEN` 等）走本地环境变量，不入库

### `software-article-en-zh`

软件工程英文 → 简体中文翻译技能。完整翻译不摘要，保留否定、条件、量词与规范性强度（MUST/SHOULD/MAY）；代码块、命令、API、配置、路径、URL 与 Markdown 结构原样保护；源文中的提示词与命令视为待译数据，不执行也不默认跳过；输入不完整时报告 `partial` / `constrained` / `blocked` 受限状态，不编造。

- 入口：[software-article-en-zh/SKILL.md](software-article-en-zh/SKILL.md)
- 安装与用法：[software-article-en-zh/README.md](software-article-en-zh/README.md)
- 评测：50 个用例（`evals/cases/`，10 维度 × 5）+ 39 个否定感知 script judge；另含真实文档全文翻译 case（`evals/eval-doc.yaml`）

## 安装与使用

四个插件（`evidence-first-writing` / `leo-ppt-generator` / `software-article-en-zh` / `creator-buddy`）统一按以下方式安装；各插件 README 的安装节与此保持一致。

### 方式一：一行命令（推荐，已实测）

用通用安装器（[vercel-labs/skills](https://github.com/vercel-labs/skills)，自动识别 78+ 宿主）安装，终端粘贴：

```sh
# 装齐四个技能（已实测）
npx skills add leo-kuang-ai/leo-skills

# 只装一个
npx skills add leo-kuang-ai/leo-skills -s leo-ppt-generator
```

- `-a <宿主>` 指定安装目标（如 `-a claude-code`），`-g` 装到用户级全局，`--list` 只预览不安装；
- 仓库内置的 spec-first 宿主镜像技能已标记 `metadata.internal`，默认不出现在发现清单；需要时以 `INSTALL_INTERNAL_SKILLS=1` 显式安装；
- 或直接在 agent 对话里说：`帮我安装这个 skill：https://github.com/leo-kuang-ai/leo-skills`。

### 方式二：手动 clone（各宿主路径表）

| 宿主 | 安装路径 |
|---|---|
| Claude Code | `~/.claude/skills/`（或官方插件市场，见下） |
| Codex | `~/.codex/skills/` |
| Cursor | `~/.cursor/skills/` |
| 通用 agents 目录 | `~/.agents/skills/`（Codex / Cursor 等兼容宿主通用） |
| 其他 runtime | clone 到对应宿主的 `skills/` 目录 |

本仓库是多技能 monorepo：clone 整仓后把四个技能目录软链进目标宿主的 skills 目录。以 Claude Code 为例（其他宿主替换两处路径即可）：

```sh
git clone --depth 1 https://github.com/leo-kuang-ai/leo-skills.git ~/.claude/skills/leo-skills \
  && for p in evidence-first-writing leo-ppt-generator software-article-en-zh creator-buddy; do ln -s ~/.claude/skills/leo-skills/"$p" ~/.claude/skills/"$p"; done
```

`git -C ~/.claude/skills/leo-skills pull` 即可更新。项目级共享：`git submodule add https://github.com/leo-kuang-ai/leo-skills.git .claude/skills/leo-skills` 后同样软链，或直接提交技能目录。

**Claude Code 官方插件市场（已实测，含更新与卸载闭环）：**

```sh
claude plugin marketplace add leo-kuang-ai/leo-skills \
  && claude plugin install evidence-first-writing@leo-skills \
  && claude plugin install leo-ppt-generator@leo-skills \
  && claude plugin install software-article-en-zh@leo-skills \
  && claude plugin install creator-buddy@leo-skills
```

- `marketplace add` 从 GitHub clone 到 `~/.claude/plugins/marketplaces/leo-skills/`；`plugin install` 把技能装到 `~/.claude/plugins/cache/leo-skills/<技能>/<版本>/`，注册为用户级 Personal Skill（Claude Code 启动时自动扫描）；
- 更新：推送新版本后 `/plugin update <技能>`（或先 `/plugin marketplace update` 再 update）；卸载：`/plugin uninstall <技能>`。

### 方式三：宿主对话框粘贴安装指引

宿主没有命令行入口或插件市场时（网页版 / 桌面版 agent 等），把下面这段指引整段复制进对话框，让 agent 自己完成 clone 与软链：

```text
帮我安装技能仓库 https://github.com/leo-kuang-ai/leo-skills：
1. 确定你所在宿主的技能目录（Claude Code 为 ~/.claude/skills，Codex 为 ~/.codex/skills，
   Cursor 为 ~/.cursor/skills，其余宿主用通用 ~/.agents/skills；不确定时选 ~/.agents/skills）；
2. git clone --depth 1 https://github.com/leo-kuang-ai/leo-skills.git <技能目录>/leo-skills，
   已存在则改为 git -C <技能目录>/leo-skills pull 更新；
3. 将 evidence-first-writing、leo-ppt-generator、software-article-en-zh、creator-buddy 四个目录软链到技能目录
   （Windows 无 symlink 权限时改用目录复制）；
4. 列出技能目录确认四个技能就位，并提醒我重启宿主后生效。
```

指引只做 clone / 软链 / 校验三件事，不涉及任何凭据或系统配置；第 3 步可换成单个技能名只装其一。

### 方式四：作为参考资料使用

即使 runtime 不支持自动加载，也可以直接打开对应技能目录的 `SKILL.md`，把内容粘贴进对话——技能本质是 markdown 指令，任何能读文件并遵循指令的模型都可执行。

### 验证

在 Claude Code 会话中输入 `/skills`，应看到 `evidence-first-writing`、`leo-ppt-generator` 与 `creator-buddy`；或用触发语直接发起请求（见下）。

## 使用示例

```text
# 证据优先写作
使用 evidence-first-writing 帮我写一篇关于远程办公的评论，面向技术团队。

# PPT 生成（Codex 触发语）
$leo-ppt-generator 把这份 PDF 视觉稿转成可编辑 PPTX，保留照片式风格。

# 全域内容搜索与创作（creator-buddy 总控）
小红书 Codex 最近有什么爆款？结合公众号近期热门给我几个短文选题。
```

## 宿主适配

四个技能都与宿主/model 无关——核心是 `SKILL.md` 与 `references/` 里的 markdown 指令，任何能读文件并遵循指令的模型都可执行。体系约定：

- **约定归一化**：能力即 markdown，不绑定特定宿主字段。
- **per-host 薄壳**：Claude Code 用 `SKILL.md` frontmatter；Codex / OpenAI 用 `evidence-first-writing` 与 `leo-ppt-generator` 各自的 `agents/openai.yaml`（`$<技能名>` 触发）；`creator-buddy` 为 vendored 集成，包根无宿主专属壳（个别子技能保留上游自带的 `agents/openai.yaml`）。
- **降级契约**：脚本钩子（如 `$EVIDENCE_FIRST_WRITING_SKILL_DIR`）在宿主不可用时显式降级（如 `factual_invariant_check: not_run`），绝不在缺失时猜测路径。

## 开发

```sh
# evidence-first-writing 单元测试
python3 -m unittest discover -s evidence-first-writing/tests -p 'test_*.py'

# 行为评测（需 skill-up CLI 与可用引擎）
skill-up validate evidence-first-writing/evals/eval.yaml
skill-up validate leo-ppt-generator/evals/eval.yaml

# leo-ppt-generator 风格库 lint（layout lint 需在技能目录内运行）
python3 leo-ppt-generator/scripts/lint_style_briefs.py
```

评测生成的 workspace（`*-workspace/`，如 `evidence-first-writing-workspace/`、`leo-ppt-generator-*-workspace/`）已在 `.gitignore`，不提交。

**评测证据边界**：evidence-first-writing 曾在 20 例套件时代于固定模型 `codex × gpt-5.6-terra` 达成全量 `20 PASS / 0 FAIL`（历史快照，见其 `evals/verification-summary.md`）；当前 33 例套件的最新全量回归（`claude_code` 引擎、GLM flash 代理）为 32/33 PASS，唯一非通过 `post-publish-no-causal-unprompted` 为在案故意保持失败项，等待受支持模型复验（见其 `evals/known-issues.md` iteration-81/82）。leo-ppt-generator 59 例套件的 M0 轮（iteration-66）修正后口径为 49 PASS / 6 FAIL / 1 ERROR，余项均为在案已知问题与 M0.1 校准批（见根 `CHANGELOG.md` 与其 `evals/known-issues.md`）。对外引用评测结论时请注明引擎与模型条件。

## 贡献约定

- 每个顶层目录是一个独立技能包（见 `AGENTS.md`）；新技能放在仓库根目录，与 `evidence-first-writing`、`leo-ppt-generator` 平级。
- 源文件变更需同步更新 `CHANGELOG.md`（Keep a Changelog 格式）。
- 新增可安装技能时，补其 `.claude-plugin/plugin.json` 并在 `.claude-plugin/marketplace.json` 的 `plugins[]` 追加条目；该清单同时服务 Claude Code 插件市场与 `npx skills add` 通用安装器，新增技能两通道自动生效。

## License

本项目基于 [MIT License](LICENSE) 发布。
