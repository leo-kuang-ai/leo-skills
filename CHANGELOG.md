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
- Add negation-tolerant script judges referenced by migrated eval cases:
  - `evidence-first-writing/evals/scripts/check-formal-report-route.sh` —
    formal-report routing gate with synonym alternatives (`owner||责任人`,
    `期限||上线窗口||决策节点||周期`, `三个方案||三方案||方案 A`) and route-pollution
    negatives.
  - `evidence-first-writing/evals/scripts/check-tool-evidence-routing.sh` —
    tool-select evidence-status gate covering taste-skill / HC3 / shuorenhua /
    ai-flavor-remover with unfalsifiable-claim negatives.
- Add the spec-first host runtime mirrors to version control
  (`.agents/skills/`, `.claude/{commands,hooks,settings.json,skills,spec-first}`,
  `.codex/hooks+hooks.json+spec-first`, `.kiro/{skills,steering,spec-first}`;
  scratch/local subsets stay git-ignored), so fresh clones carry the full
  using-spec-first entry governance without re-running init.
- Add docs/image.png reference to the root README: a Humanizer tool-chain
  selection cheat sheet ("想做什么 → 对应方法" mapping plus open-source tool
  comparison) embedded under the evidence-first-writing section. (user-visible)

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
- **AGENTS.md** — rewrite the repository-level guidelines to match `CLAUDE.md`
  and the current two-skill reality: set the Chinese default for docs with English
  identifiers, the MIT license, and the mandatory Keep-a-Changelog /
  `(user-visible)` change log; document the current layout (`evidence-first-writing/`,
  `leo-ppt-generator/`, `docs/`, git-ignored `*-workspace/` and `graphify-out/`);
  replace the stale "no commit history establishes a convention" with the actual
  scoped-commit and one-concern-per-commit rules; and add the concrete
  unit-test / skill-up eval / factual-invariant checker commands (both skills'
  `evals/eval.yaml`, engine default `claude_code`). Also advise negation-aware
  assertions for safety-gate evals.
- **.gitignore** — consolidate the ad-hoc per-skill workspace rules into a
  single `*-workspace/` (matches the CLAUDE.md "eval workspaces are git-ignored"
  convention and covers current/future skills), and add Python tool caches
  (`.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.coverage`, `htmlcov/`),
  `env/`, `.idea/`, `*.log`, plus Windows desktop files (`Thumbs.db`,
  `Desktop.ini`) since the installer targets Windows.
- **SKILL.md** — generalize the causality red line beyond post-publish: when the
  material contains only a single before/after change, time ordering, or
  correlation without controls, counterfactuals, or confounder handling, the
  Skill must refuse the "X 导致 Y" sentence even under explicit user request,
  rather than hedging with "证据有限" after the fact.
- **evals/cases/routes-formal-report.yaml** — migrate from brittle substring
  rule judges to the script judge `check-formal-report-route.sh` and drop
  `owner` / `期限` as hard `must_contain` tokens so synonym phrasings no longer
  false-fail.
- **evals/cases/routes-technical-reference.yaml** — drop the ambiguous negative
  `"教程叙事"` (which fired on legitimate contrast explanations) and extend the
  judge's `not:` list to enum-level route pollution (`article_family: tutorial`,
  `marketing-copy`).
- **evals/cases/source-grounded-tool-routing.yaml** — replace the inline
  rule-based judge with the script judge `check-tool-evidence-routing.sh`; drop
  the redundant `expect` block that duplicated the same substrings.
- **evals/scripts/check-audit-readonly.sh** — merge the two problem-category
  gates into one synonym-tolerant list (addings 宣传、缺乏可验证依据、过度泛化、
  绝对化、不可核验 variants) so equivalent problem namings no longer fail the
  readonly-audit gate.
- **evals/scripts/check-single-routing-question.sh** — accept `实践` / `步骤`
  as additional second-reader-task markers for the bare-topic fork question.
- **evals/verification-summary.md** — record the fixed-model full regression
  (iteration-17/18 A/A on bare-topic routing, iteration-19 first full
  `14 PASS / 6 FAIL`, iteration-31 focused `2 PASS`, iteration-32 final full
  `20 PASS / 0 FAIL / 0 ERROR` on Codex `gpt-5.6-terra`) and pin the final
  verification command; keep unfixed-model runs archived as provider-drift
  evidence.
- **references/intent-routing.md** — close the canonical-value gap between
  SKILL.md's operation list and this file's enums: declare the full
  canonical `operation` enum (17 values) instead of "由 lifecycle_intent 映射",
  and add a 跨族 operation section defining when `coauthor`, `hooks`, `voice`,
  `copywriting`, and `docs` apply (family/modifier-scoped operations that own no
  lifecycle) plus the priority rule forbidding out-of-enum values.
- **CLAUDE.md** — sync to the two-skill reality: rewrite the repo structure
  section (both skill packages, docs/, marketplace manifest), add
  leo-ppt-generator eval commands alongside the writing-skill suite, split the
  architecture section into 架构一（写作）与 架构二（PPT：Gate 0 信任门禁、
  advise/execute、Route 表、控制面五行合同、交付红线）, fix relative paths in
  the key-files table and add leo-ppt-generator rows.
- **README.md** — add an evaluation evidence boundary note next to the dev
  commands: the `20 PASS / 0 FAIL` conclusion is conditioned on the fixed
  `codex × gpt-5.6-terra` engine; `post-publish-no-causal` still fails under
  the DeepSeek flash proxy behind `claude_code` pending real-Claude
  re-verification. Cite `verification-summary.md` / `known-issues.md`. (user-visible)
- **AGENTS.md / CLAUDE.md** — inject the spec-first managed governance block
  (`<!-- spec-first:lang:start/end -->`): absolute Chinese-language policy and
  the workflow-entry governance pointer to the installed `using-spec-first`
  skill.
