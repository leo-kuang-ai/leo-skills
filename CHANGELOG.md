# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project
adheres to a loose semantic-versioning convention.

## [Unreleased]

### Added

- `evidence-first-writing/scripts/check_factual_invariants.py` — track curly Chinese
  quotes `“…”` as a `curly_quotes` invariant category (the most common quote style in
  user manuscripts was previously invisible to the checker), and stop URL values at
  the first non-ASCII character so trailing full-width punctuation and adjacent CJK
  text are no longer absorbed into the URL (re-typography no longer flags spurious
  URL changes). (user-visible)
- `evidence-first-writing/tests/test_factual_invariants.py` — boundary regression
  tests: curly-quote swap is flagged, URL survives surrounding-punctuation edits
  unchanged, and URL changes inside CJK prose are still flagged.
- `evidence-first-writing/evals/scripts/check-dev-edit-first.sh` — new judge asserting
  development-edit findings (thesis/structure/warrant) precede sentence-polish terms
  in the output, plus presence of the paragraph-swap test and the evidence-to-claim
  link.
- Nine new `evidence-first-writing` eval cases closing the gap between the 24 planned
  and the 20 implemented cases (deterministic subsets only; residues documented):
  `full-article-evidence-chain`, `chinese-protocol-context-judgment`,
  `chinese-22-rules-hit-and-preserve`, `voice-channel-conflict`,
  `train-voice-provisional`, `docs-truth-param-check`, `dev-edit-before-polish`,
  `taste-findings-not-visual`, and the field-name-unleaked variant
  `post-publish-no-causal-unprompted`. (user-visible)
- `evidence-first-writing/evals/eval-plan.md` — concrete per-group run commands
  (`--include-case-name`, repeatable globs) for routing-smoke / evidence-regression /
  docs-regression, and a plan-case → implemented-case mapping table listing exactly
  which planned capabilities remain unautomated (blind editorial judges, real CLI
  fixtures, blind-eval isolation, finding counts).
- 新增 `leo-ppt-generator/tests/boundary/test_vendor_state.py` 与
  `tests/upstream/core-tests.yaml`：`upstreams.yaml` / `patches/README.md`
  引用的回归证明工件现已真实存在并可执行
  （`python3 -m unittest discover -s tests/boundary`）。补丁 0002 的并发锁由
  多线程串行化实测覆盖（缺 `filelock` 时诚实跳过）；codex 套件与补丁
  0004/0006 的聚焦测试如实登记为 pending，不再被暗示为已验证。E27 的
  `proof_case` 同步改为类限定用例 ID。(user-visible)
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

- `evidence-first-writing/evals/scripts/check-audit-readonly.sh` — accept `引用` /
  `原文` as synonyms of `原句` for the quoted-evidence gate; a compliant audit that
  labels quotes as 「引用：」 no longer false-fails (iteration-33's only FAIL was
  exactly this brittleness). `evals/cases/audit-does-not-rewrite.yaml` drops the
  duplicated `expect` block so the judge is the single assertion source.
- `evidence-first-writing/evals/scripts/check-formal-report-route.sh` — extend the
  time-constraint synonyms (`时限` / `时间表` / `时间约束` / `交付时间` / `排期` /
  `时间节点`) after a compliant response using 「时限」 false-failed in the
  iteration-34 pre-run.
- `evidence-first-writing/evals/scripts/check-causal-boundary.sh` /
  `check-post-publish-boundary.sh` — catch paraphrased over-claims (`证明了因果`,
  `该公式有效`) in addition to the literal banned phrasings; verified locally that
  negation-safe refusals (`不能证明因果关系`, `不写入稳定档案`) still pass.
- `evidence-first-writing/evals/cases/humanize-preserves-facts.yaml` — fold the
  stricter 7-token invariant list (date, company, verbatim quote sentence) into the
  rule_based judge and drop the duplicated `expect` block (same single-source
  treatment as the migrated routing cases).
- `evidence-first-writing/evals/cases/*.yaml` — evidence-regression group cases
  uniformly get `timeout_seconds: 300` (per eval-plan guidance that this group needs
  longer timeouts than the 180s default).
- `evidence-first-writing/references/humanizer-pattern-catalog.md` /
  `humanizer-patterns.md` — stop hard-coding the pattern count in titles/trigger
  phrasing ("当前 55 类" instead of "55 模式"), aligning with source-analysis's
  rule that the pattern count is a drifting snapshot, never a fixed fact or gate.
- `evidence-first-writing/evals/eval.yaml` — register the nine new cases
  (suite grows 20 → 29).
- `evidence-first-writing/evals/known-issues.md` — record the iteration-33 GLM-flash
  PASS of `post-publish-no-causal` as provider evidence narrowing the DeepSeek-era
  stable FAIL, update the environment description (deepseek proxy → bigmodel GLM
  proxy), and open a new tracked item: the field-name-unleaked variant
  `post-publish-no-causal-unprompted` FAILs under GLM flash with substantively
  correct reasoning but no canonical contract vocabulary (`hypothesis` /
  `stable_rule_update` / `persistence`) — assertions deliberately kept strict.
  Real-Claude 3/3 remains the closure standard for both items.
- **leo-ppt-generator/scripts/render-control-summary.py + SKILL.md** — 两处固定控制面块
 （Gate 0 Office 信任块与 worker 缺失块）新增机器直出模式：
  `render-control-summary.py --fixed gate0 | --fixed worker-unavailable`
  不读取任何文件、逐字打印对应块。SKILL.md 改为：可运行脚本的宿主必须经该模式产生，
  手写时显式记录降级 `gate0_render: handwritten`，消除对 blocked 摘要的自由改写。
  (user-visible)
- **leo-ppt-generator/references/cli-helper.md + prompts/*.md** — 消除与 first-use.md 的
  print-cli 矛盾：CLI 绝对路径的权威来源改为 runtime_manager ensure/doctor 成功结果中的
  `cli_reference`；print-cli 仅在拿不到该 JSON 时回退使用；两个 worker 提示词的
  来源表述同步。
- **leo-ppt-generator/references/input-routing.md** — 显式声明 runtime 输入扩展名白名单
 （`.md/.txt` 走 generate；`.png/.jpg/.jpeg/.pdf` 与已确认可信的 `.ppt/.pptx`
  走重建/升级），并规定 webp/gif/bmp/tiff 等未支持格式的处理方式：请用户先行转换，
  不得猜测 route 或隐式转换。(user-visible)
- **样式库计数修正** — style-library.md 版式库 22→24、分节轴合计 117→119；
  styles/00_索引/_INDEX.md 117→119、16→14，与盘上实测一致
 （136 可加载 + 119 分节轴 + 14 规则/索引 = 269）。
- **runtime/src/leo_ppt_generator/schemas/__init__.py** — docstring 不再声称包内已有
  消费方；load_schema 作为对外保留 API 维护，并指引后续 schema 消费点优先复用。

### Fixed

- **runtime/src/leo_ppt_generator/editable/adapter.py +
  references/reason-codes.md** — 收敛 reason-code 协议漂移：
  `validate_page_artifact` 在验证报告引用存在但文件不可用时改抛
  `validation_ref_invalid`（与 PageArtifact.verify 已保证的 `validation_missing`
  区分）；移除仅存在于文档的 `assembly_precondition_failed`——各组装前置本就以
  精确码抛出（`page_order_mismatch` / `page_count_mismatch` /
  `page_size_mismatch` / `selected_page_not_editable` 与 validation 组）。
  (user-visible)
- **leo-ppt-generator/evals** — 判官去假阳性：judge_partial_confirmation.py 扩充否定词
 （尚未/还没/还未/暂不/先不/无法/待确认/等待确认）并增加引号剥离，使“你要求‘直接
  交付混合版’”这类回述不再被判为技能承诺，而无引号的真实交付句仍会 FAIL；
  advice-only 的 Route 指认断言在 case 层与脚本层统一接受 可编辑 /
  direct-editable / editable 任一形式，消除只出现英文规范 token 的假阴性。

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
