# Leo Skills

可复用的智能体技能集合，面向证据优先的技术写作与编辑工作流。

## 包含技能

### `evidence-first-writing`

用于路由写作请求、保留源事实，并产出有技术依据的文稿。技能包包含
工作流契约、参考资料、事实不变量检查和评测用例。

详见 [evidence-first-writing/SKILL.md](evidence-first-writing/SKILL.md)，了解
触发条件和完整工作流；[evidence-first-writing/README.md](evidence-first-writing/README.md)
介绍完整的安装步骤与使用方法。

### `leo-ppt-generator`

把需求、视觉稿、图片或 PDF 转成可编辑 PowerPoint：支持图片版 PPT、
可编辑版 PPT、hybrid 与升级路线。技能包包含运行时（`runtime/`）、
参考风格库（`references/styles/`）、补丁与评测用例，并提供
[install.sh](leo-ppt-generator/install.sh)（macOS/Linux）与
[install.ps1](leo-ppt-generator/install.ps1)（Windows）本地安装脚本。

详见 [leo-ppt-generator/SKILL.md](leo-ppt-generator/SKILL.md)，了解
触发条件、路由与门禁顺序。

## 安装与使用

### 方式一（推荐）：Claude Code `/plugin`

仓库已配置插件市场，一条命令远程安装：

```text
/plugin marketplace add leo-kuang-ai/leo-skills
/plugin install evidence-first-writing
```

更新：`/plugin update evidence-first-writing`；卸载：`/plugin uninstall evidence-first-writing`。

### 方式二：Git clone + 软链到 `~/.claude/skills/`

```sh
git clone https://github.com/leo-kuang-ai/leo-skills.git ~/.claude/skills/leo-skills
ln -s ~/.claude/skills/leo-skills/evidence-first-writing ~/.claude/skills/evidence-first-writing
```

- **项目级**：放在 `<project>/.claude/skills/evidence-first-writing/` 并提交仓库（或用 git submodule）。
- **Codex / OpenAI**：用 `agents/openai.yaml` 声明的 `default_prompt` 触发：`$evidence-first-writing 识别我的写作意图…`。
- **验证**：会话中输入 `/skills` 应出现 `evidence-first-writing`，或用触发语直接发起写作请求。
- **更新**：`git -C ~/.claude/skills/leo-skills pull`。
- **宿主适配**：核心流程是 markdown，与宿主无关；只脚本钩子绑定宿主（`$EVIDENCE_FIRST_WRITING_SKILL_DIR`），
  不可用时降级为 `factual_invariant_check: not_run`。详见
  [evidence-first-writing/README.md 宿主适配](evidence-first-writing/README.md)。

## 开发

在仓库根目录运行测试：

```sh
python3 -m unittest discover -s evidence-first-writing/tests -p 'test_*.py'
```

评测定义位于 `evidence-first-writing/evals/`。生成的评测工作区会被 Git
有意忽略。

## License

本项目基于 [MIT License](LICENSE) 发布。
