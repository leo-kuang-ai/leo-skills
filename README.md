# Leo Skills

可复用的智能体技能集合，面向证据优先的技术写作与编辑工作流。

## 包含技能

### `evidence-first-writing`

用于路由写作请求、保留源事实，并产出有技术依据的文稿。技能包包含
工作流契约、参考资料、事实不变量检查和评测用例。

详见 [evidence-first-writing/SKILL.md](evidence-first-writing/SKILL.md)，了解
触发条件和完整工作流；[evidence-first-writing/README.md](evidence-first-writing/README.md)
介绍完整的安装步骤与使用方法。

## 安装与使用

从 GitHub 拉取并软链 `evidence-first-writing` 到本机 Claude Code 技能目录（`~/.claude/skills/`）：

```sh
git clone https://github.com/sunrain520/leo-skills.git ~/.claude/skills/leo-skills
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

## English

Reusable agent skills for evidence-first technical and editorial writing.

The included `evidence-first-writing` skill routes writing requests, preserves
source facts, and produces technically grounded drafts. See
[evidence-first-writing/SKILL.md](evidence-first-writing/SKILL.md) for the
complete workflow.

To install as a personal Claude Code skill from GitHub:

```sh
git clone https://github.com/sunrain520/leo-skills.git ~/.claude/skills/leo-skills
ln -s ~/.claude/skills/leo-skills/evidence-first-writing ~/.claude/skills/evidence-first-writing
```

## License

本项目基于 [MIT License](LICENSE) 发布。
