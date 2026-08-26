# Leo Skills

Reusable agent skills for evidence-first technical and editorial writing.

## Included Skill

### `evidence-first-writing`

An agent skill for routing writing requests, preserving source facts, and
producing technically grounded drafts. The package includes its workflow
contract, reference material, factual-invariant checks, and evaluation cases.

See [evidence-first-writing/SKILL.md](evidence-first-writing/SKILL.md) for
trigger conditions and the complete workflow.

## Development

Run the package tests from the repository root:

```sh
python3 -m unittest discover -s evidence-first-writing/tests -p 'test_*.py'
```

Evaluation definitions live in `evidence-first-writing/evals/`. Generated
evaluation workspaces are intentionally ignored by Git.

## License

Released under the [MIT License](LICENSE).
