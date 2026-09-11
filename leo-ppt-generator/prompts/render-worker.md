# Render Worker Prompt（render lane 页派发协议，与 slide-worker 平行）

Use this template when the parent routes a page to the deterministic render lane
(after the render-lane routing proposal is accepted at the existing backend
confirmation point — see `references/backend-selection.md` 渲染 lane 节). This
prompt is the parallel of `slide-worker.md` for `render:html` / `render:mermaid`
pages; the image-worker forbidden list ("local rendering scripts / SVG / HTML
screenshots") does **not** apply here, because this page was **explicitly routed**
to the deterministic render backend. The routing decision is recorded by the
parent; the worker never routes itself.

```text
Render slide <N> for this leo-ppt deck via the deterministic render lane.

Deck dir: <absolute deck dir>
Run dir: <absolute run dir>
Page number: <N>
Backend (report verbatim): render:html | render:mermaid
Render template id: <template id from template-library/canonical/templates/, e.g. body-basic>
Slide data JSON: <absolute path; produced by the parent from the confirmed deck
master; required_text whitelist values must already be final and approved>
Theme variables source: <deck colors anchor JSON path, or "none — mermaid
defaults + WARN">
Chart dialect file (render:mermaid only): <absolute 11_图表语法 file path or
.mmd code file; numbers must come from the approved data, never the syntax-demo
examples>
Output candidate path (worker-owned): <absolute candidate .png path>
Render receipt (produced by the render command): <candidate>.render.json
Absolute leo-ppt CLI: <absolute leo-ppt CLI path supplied by parent>
visual_qa script: <skill root>/scripts/visual_qa.py

Execution steps (deterministic; no image model involved):
1. `"<CLI>" render ready --json` — if status is not render_backend_ready, STOP
   and return `blocker=render_backend_missing` (or render_backend_unknown) with
   the install guide verbatim. Never attempt rendering with a missing backend.
2. render:html page:
   `"<CLI>" render page --template <template id> --data <slide data JSON> --out <candidate> --size 2560x1440`
   render:mermaid chart:
   `"<CLI>" render chart --dialect mermaid --source <dialect file> --out <chart.svg> --theme-file <theme JSON> --png <candidate> --scale-width 2560`
   (chart pages embedded in an HTML template go through render page with the
   chart SVG in the slide data's chart_svg slot — see render-contract.md.)
3. Pixel gate (single page, machine): run
   `<python> scripts/visual_qa.py <candidate> --report <run>/reports/visual-qa-page_<NN>.json`
   Exit 1 (FAIL) → fix the slide data / template parameters / chart code and
   retry the render, up to 3 attempts per page (stage-tiered: a failed QA does
   not re-run a successful chart render if the chart SVG is unchanged). Do NOT
   hand a FAIL page to LLM review. Exit 2 (WARN) → allowed, but you MUST carry
   every WARN into qa_note.
4. Read the produced PNG header and assert 2560x1440 exactly (read the file
   header, not the CLI arguments). Mismatch → `blocker=render_size_mismatch`.

Forbidden:
- modifying template files outside template-library/canonical/templates/ (report a blocker
  naming the contract violation instead)
- presenting the render output as an image-model product: backend_used must be
  reported verbatim as render:html / render:mermaid — never an image provider
  name, never "image model", never builtin-imagegen
- editing slide job files, origin_image/, or assembling the PPTX (parent-owned)
- inventing or "improving" chart numbers: values/units/labels/order come from
  the approved data verbatim; the syntax-demo numbers in 11_图表语法 files are
  placeholders and must be replaced with approved data before rendering
- editing the .render.json sidecar by hand; it is produced by the render
  command and consumed by `image record --render-receipt` byte-for-byte

When returning, hand back page_type (chart | text-heavy | image), attempts, and
the render receipt path so the parent can record
`image record --backend render:html --render-receipt <path> --page-type ... --attempts ...`.
backend_tokens is always `not-recorded` for render backends — deterministic
rendering has no token cost; the parent's cost report must aggregate render
pages separately, never mixed into image-model token totals.

Return only:
backend_used=render:html | render:mermaid   (verbatim; never an image provider)
output_pixels=<actual WIDTHxHEIGHT read from the produced PNG header>
render_receipt=<absolute path to <candidate>.render.json>
qa_note=<one sentence; on retry also state target-check verdict AND spillover-check verdict; carry every visual_qa WARN>
attempts=<number of render attempts for this page>
worker_duration_seconds=<measured total worker seconds>
backend_duration_seconds=<measured render command seconds>
backend_tokens=not-recorded
```

---

协议要点：backend 如实回报（`render:*` 枚举）、token 恒 `not-recorded`、
单页像素闸门前置于回报、模板不可改、sidecar 不可手改。反冒充约束
（render 产物不得冒充图像模型产物）由 backend 字符串如实回报 +
evals case `gamma-m1-render-worker-no-fake-image-backend` 双向守门。
