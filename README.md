# Leo Skills

可复用的智能体技能集合，面向证据优先的技术写作与编辑工作流。

## 包含技能

### `evidence-first-writing`

用于路由写作请求、保留源事实，并产出有技术依据的文稿。技能包包含
工作流契约、参考资料、事实不变量检查和评测用例。

详见 [evidence-first-writing/SKILL.md](evidence-first-writing/SKILL.md)，了解
触发条件和完整工作流。

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

## License

本项目基于 [MIT License](LICENSE) 发布。
