# Repository Guidelines

## Project Structure & Module Organization

This repository is a collection of independent skill packages. Place each skill in its own top-level directory, using a lowercase kebab-case name such as `document-review/` or `release-notes/`. Do not create runtime dependencies between sibling skills unless the shared contract is documented explicitly.

A typical package should contain:

- `SKILL.md`: entry point, trigger conditions, workflow, and constraints.
- `scripts/`: executable helpers used by the skill.
- `references/`: supporting instructions or domain material loaded on demand.
- `assets/` or `templates/`: reusable files copied into generated outputs.
- `tests/` or `evals/`: package-local behavior checks and fixtures.

Keep generated output, caches, credentials, and temporary evaluation workspaces out of the repository.

## Build, Test, and Development Commands

There is currently no repository-wide build or test runner. Each skill must document its own commands in `SKILL.md` or a package-local `README.md`. Useful repository-level checks include:

```sh
find . -mindepth 2 -maxdepth 2 -name SKILL.md
rg -n "TODO|FIXME" --glob '!AGENTS.md'
git diff --check
```

Run package-specific formatting, tests, and evaluations from that package's directory before submitting changes.

## Coding Style & Naming Conventions

Use two spaces for YAML and JSON, and follow the formatter standard for any implementation language. Prefer ASCII filenames and UTF-8 content. Use `lowercase-kebab-case` for skill directories, `snake_case` for shell variables, and descriptive fixture names. Keep instructions direct and imperative. Scripts should fail clearly, avoid machine-specific absolute paths, and expose required configuration through documented environment variables.

## Testing Guidelines

Tests belong to the skill they validate. Cover trigger behavior, the primary successful workflow, invalid input, and important safety boundaries. Name cases after observable behavior, for example `rejects-missing-source`. Never treat installation or static validation alone as proof that a skill works; record the exact command and result for behavioral evaluations.

## Commit & Pull Request Guidelines

No commit history currently establishes a convention. Use short, imperative subjects with an optional package scope, for example `document-review: add PDF fixture`. Keep commits limited to one skill or one repository-level concern. Pull requests should identify affected packages, explain behavior changes, list verification commands and results, and link relevant issues. Include screenshots or sample artifacts only when output presentation changes.

## Security & Agent-Specific Instructions

Never commit secrets, tokens, personal data, or local configuration. Treat each top-level skill as an ownership boundary: inspect and modify only the requested package, preserve unrelated work, and report any unavoidable cross-package impact before making it.
