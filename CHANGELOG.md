# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project
adheres to a loose semantic-versioning convention.

## [Unreleased]

### Added

- Add `leo-ppt-generator` as the second top-level skill package, migrated from
  the standalone `leo-ppt-generator` project. It turns requirements, visual
  mockups, images, or PDFs into editable PowerPoint decks (image-based,
  editable, hybrid, and upgrade routes). During migration the over-the-air
  self-update logic was removed — the `check`/`update` subcommands, download
  helpers, and remote constants that fetched version info and installer scripts
  from `leo-kuang-ai/leo-ppt-generator` are gone, and the runtime health check is
  now a local-only comparison. `install.sh` / `install.ps1` were adapted to
  local-only mode (default source is the script's own directory, `--ref`/`-Ref`
  remote fetch dropped) and moved inside `leo-ppt-generator/` rather than the
  project root. (user-visible)。作者: leokuang
- Add `.claude-plugin/marketplace.json`: enables `/plugin marketplace add leo-kuang-ai/leo-skills` and
  `/plugin install evidence-first-writing` for remote Claude Code installation.
- Add `evidence-first-writing/README.md`: install (Claude Code personal/project
  and Codex), usage, cross-host adaptation, references map, and test/eval
  commands.
- **README.md** — add an installation-and-usage section with the remote
  `git clone … && ln -s …` commands to `~/.claude/skills/`, project-level and
  Codex install paths, an update step, and a `/skills` verification step; keep
  the English mirror consistent.
- Introduce `evidence-first-writing/evals/` evaluation suite for the Skill:
  - `evals/eval.yaml` orchestration config (default engine `claude_code`).
  - 20 cases under `evals/cases/`, including new ones: `depth-quick-revise`,
    `post-publish-no-causal`, `copywriting-route`, `rejects-causal-overclaim`,
    `personal-context-no-write`.
  - Judge scripts under `evals/scripts/`: `check-single-routing-question.sh`,
    `check-causal-boundary.sh`, `check-audit-readonly.sh`, `check-voice-skip.sh`.

### Changed

- **README.md** — comprehensive rewrite for the two-skill collection: broaden the
  intro to writing + PPT generation, document `/plugin` install for both skills,
  add per-skill usage triggers, host-adaptation principles, development/eval and
  contribution conventions.
- **evidence-first-writing/README.md** — document `/plugin` remote install as the
  recommended path (verified end-to-end on Claude Code), alongside git clone +
  symlink and project-level installs; add Codex trigger usage.
- **TECHNICAL_DESIGN.md** — add a cross-host adaptation section: the
  convention-normalization + per-host-thin-shell + degradation-contract
  principles, a host capability matrix, and deferred evolution directions
  (flatten script, plugin marketplace, Codex agent fields).
- **SKILL.md**
  - Add a prominent post-publish causality red flag: single-article metrics must
    not be promoted to reusable rules without two comparable replications plus a
    counterexample check. The rule is a hard refusal: when an author explicitly
    asks to promote a single-article result, the Skill must refuse, record it as
    `stable_rule: none` / `hypothesis`, and state what is required to upgrade.
    `post-publish` defaults to analyze-only: a single article is recorded as
    `observation` / `hypothesis`, and no persistence (voice archive, memory, or
    files) happens without explicit write authorization and a target path
    (`persistence: not_run` otherwise).
  - Require canonical route fields (`lifecycle_intent`, `article_family`,
    `evidence_risk`, `operation`, `depth`) in any user-facing plan; values must
    come from the `intent-routing.md` enums.
  - Mandate an explicit "factual regression after rewrite" stage for
    `full/deep` runs, recorded as `factual_regression`, and require canonical
    phase owner IDs (`fact_review`, `development_edit`, `reader_review`,
    `taste_voice`, `copy_proof`, `factual_regression`).
- **references/editorial-pipeline.md**
  - Add a machine-readable `stable_rule_update` gate to Node 14 (post-publish
    review): `promoted` requires two comparable replications, two comparable
    runs, and checked counterexamples.
  - Add the explicit `factual_regression` record block to Node 12.
- **references/voice-profiles.md**
  - Add the minimal auditable voice-skip disclosure fields.
  - Add the post-publish archive threshold for performance/causal conclusions.
- **evals/cases/copywriting-route.yaml** — drop the family-name negative
  assertions that falsely fired when the Skill correctly explained its routing,
  and align the `expect.must_contain` keywords with the judge's synonym list
  (the Skill words the page action as "CTA / 注册 / 落地页" rather than the
  literal "页面动作").
- **leo-ppt-generator/evals** — align the eval harness with the Skill's primary
  host and de-brittle the negative assertions:
  - `evals/eval.yaml` — default engine back to `claude_code`, dropping the
    `codex` + `bypass_sandbox` override. The Skill is a Claude Code plugin, and
    its sibling `evidence-first-writing` eval already defaults there; running
    under `codex` produced 5/9 only because that host paraphrases the verbatim
    control-plane summary, not because of a Skill logic defect.
  - `evals/cases/advice-only-no-execution.yaml` — replace the substring-sensitive
    `expect.must_not_contain` with a negation-aware script judge
    `evals/fixtures/scripts/judge_advice_only.py`, so a refusal phrased as
    `未读取文件` / `本轮我不会：- …` no longer false-fires on the literal
    `读取文件` / `bootstrap` / `setup` / `config status`.
  - `evals/fixtures/scripts/judge_untrusted_sanitized.py` — accept colon + bullet
    phrasing (`本轮我不会：- 打开、读取或解析原始 PPTX`) as "未处理输入" evidence
    instead of requiring the contiguous `不会打开`.
  - `evals/cases/control-plane-blocked-summary.yaml` /
    `missing-multi-page-workers.yaml` — drop the redundant
    `expect.must_not_contain` and route the negative check through new
    negation-aware script judges (`judge_control_plane_fields.py`,
    `judge_no_serial_substitution.py`) so a refusal like `本轮未创建 run` /
    `我不会串行生成` does not false-fail.
  - `evals/cases/delivery-acceptance-pending.yaml` — drop the brittle
    `expect.must_not_contain: [交付闭环已完成]` (a refutation
    `不能声称交付闭环已完成` would have false-failed); the script judge's
    negation-aware `positive()` already covers it.
  - `evals/cases/partial-hybrid-without-confirmation.yaml` and
    `judge_no_serial_substitution.py` — accept the partial-hybrid term's
    plain-language synonyms (`混合版` / `部分可编辑` / `hybrid`) instead of the
    single literal token, and scope the "serial generation" promise check to a
    first-person main-agent claim not attributed to a worker (describing the
    correct `真实 worker … → 逐页生成` recovery path must not false-fire).
