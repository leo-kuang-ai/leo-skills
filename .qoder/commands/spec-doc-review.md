---
name: spec-doc-review
description: Run the Spec-First document review workflow
---

Command support root: `.qoder/skills/spec-doc-review`. Treat it as the loaded skill directory whenever this inlined workflow refers to `SKILL_DIR` or the directory containing `SKILL.md`.


# Document Review

Review requirements or plan documents through multi-persona analysis. Task packs are reviewed as derived, report-only execution inputs against their current source plan. Dispatches generic subagents seeded with skill-local reviewer prompt assets, applies `safe_auto` fixes only when the run-local mutation policy is `markdown-write`, and preserves the same structural/semantic review as report-only findings when mutation is unavailable or forbidden.

## Workflow Contract Summary

- **Inputs:** requirements, unified or legacy plans, task packs, or readable spec artifacts, with optional roster/output/mutation flags.
- **Outputs:** report-only findings by default, coverage, recommendations, and optional JSON. Markdown fixes require explicit apply authority.
- **Hard exits:** unreadable documents, conflicting flags, task-pack/source-plan drift, ambiguous format/source ownership, or missing mutation authority block writes.
- **Dispatch boundary:** `worker_dispatch_authorization`, `capability_probe`, `worker_dispatch_capability`, `worker_capability_unproven`, `provider_untrusted`, `dispatch_authorization_missing`, and `subagent_capability_missing` are recorded before dispatch; direct invocation does not authorize workers, and inline fallback never claims independent persona coverage.

```yaml
worker_context_isolation: isolated | inherited | unknown
worker_model_override: supported | unsupported | unknown
worker_bounded_parallelism: supported | unsupported | unknown
worker_dispatch_outcome: <record the live result>
```
- **Mutation boundary:** `mode:headless` / `mode:non-interactive` only change delivery; `requested_mutation: default-report-only` remains the default. Without `mutation:apply-fixes`, ordinary writable Markdown resolves to `report-only`; commit and landing remain unauthorized.
- **Authority:** the document and source refs supply facts; personas/LLMs judge semantic adequacy. Producers own derived-artifact repair; review inherits no commit or landing authority.
- **Consumers:** document owners, `spec-brainstorm`, `spec-plan`, `spec-write-tasks`, `spec-work`, and human reviewers.

## Interactive mode rules

Read `.qoder/skills/spec-doc-review/references/modes.md` before parsing delivery, mutation, and output flags or firing any interactive question. It owns the eager question-tool preload, non-interactive alias, and delivery-only semantics.

## Phase 0: Detect Mode

Read `.qoder/skills/spec-doc-review/references/modes.md` before resolving flags. Then read `.qoder/skills/spec-doc-review/references/document-intake.md` before reading or classifying the document.

## Phase 1: Get and Analyze Document

Read `.qoder/skills/spec-doc-review/references/document-intake.md` for path, missing-document, classification, and mutation-policy gates.

## Phase 2: Announce and Dispatch Personas

Read `.qoder/skills/spec-doc-review/references/persona-selection.md` to select and budget the roster, including the required `cost-shape:` line.

### Dispatch

Read `.qoder/skills/spec-doc-review/references/dispatch.md` before dispatch or inline review. It owns authorization, provider/capability facts, context slices, backpressure, model defaults, and failure semantics.

## Phases 3-5: Synthesis, Presentation, and Next Action

Before rendering any finding, read `.qoder/skills/spec-doc-review/references/rendering-floor.md`. Its consequence-first wording, recommendation visibility, opaque-token budget, and trace-on-request rules apply to the structured envelope, batch report, walkthrough, bulk preview, and persisted Open Questions entry. Surface-specific layouts may differ, but none may weaken that shared decision floor.

After all dispatched agents return, read `.qoder/skills/spec-doc-review/references/synthesis-and-presentation.md` for the synthesis pipeline (validate, anchor-based gate, dedup, cross-persona promotion, contradiction resolution, auto-promotion, three-tier routing with FYI subsection), mutation-policy enforcement, structured envelope output, and the routing-question handoff.

Only when `delivery_mode: interactive` **and** `mutation_policy: markdown-write`, read `.qoder/skills/spec-doc-review/references/walkthrough.md` for the four-option routing question and per-finding walk-through. For the bulk-action preview used by best-judgment routing, Append-to-Open-Questions, and walk-through's "Auto-resolve with best judgment on the rest", read `.qoder/skills/spec-doc-review/references/bulk-preview.md`. Do not load either before agent dispatch completes, and never load them for `report-only`.

---

## Included References

### Task Pack Review Lens

Read [Task Pack Review Lens](.qoder/skills/spec-doc-review/references/task-pack-review-lens.md) only when Phase 1 classifies the input as `task-pack`.

### Subagent Template

@./.qoder/skills/spec-doc-review/references/subagent-template.md

### Findings Schema

@./.qoder/skills/spec-doc-review/references/findings-schema.json

Selected reviewer prompt assets live under `.qoder/skills/spec-doc-review/references/personas/`. Read only the prompt files selected for the current review.

Read `.qoder/skills/spec-doc-review/references/dispatch.md` before dispatch or inline review.
