# Slide Worker Prompt

Use this template when dispatching a slide subagent after the sample slide is approved and full-deck generation is authorized.

```text
Generate slide <N> for this codex-ppt deck.

Deck dir: <absolute deck dir>
Run dir: <absolute run dir>
Backend contract: <absolute run dir>/input/backend-contract.json
Required slide image: 2560x1440 px (16:9). This is a hard contract: the slide image must be exactly the deck canvas ratio (default 16:9) — a non-16:9 slide image letterboxes or stretches on the canvas and fails deck geometry QA. Available sizes are whatever the selected backend/contract supports; never assume a model's size menu and never fall back to a non-16:9 size.
Slide job file: <absolute deck dir>/prompts/slide_<NN>.json
Output target owned by parent: <absolute deck dir>/origin_image/slide_<NN>.png
Selected image backend: <built-in image tool OR CLI/API fallback>
Absolute leo-ppt CLI: <absolute leo-ppt CLI path supplied by parent from runtime_manager cli_reference>
Sample generation method copied from the approved sample:
- backend_used: <exact backend label recorded by parent>
- tool_name: <built-in image tool OR absolute leo-ppt CLI path + upstream codex-ppt -- image>
- mode: <generate OR edit>
- required_size: <pixel size copied from the approved sample; MUST be 16:9, e.g. 2560x1440>
- model/config: <model, size, quality, or "built-in default" if not exposed>
- prompt_source: <approved sample prompt source>
- input_context_preparation: <how local images were made visible or attached>
- approved_sample_path: <absolute path to approved origin_image/slide_XX.png>
- handoff_rule: use this same backend/tool/mode; return a blocker if unavailable. If the recorded method's pixel size is not 16:9, do NOT inherit it and do NOT silently downgrade: return `blocker=aspect_ratio_method_mismatch` instead
Input images already prepared by the parent:
- <absolute path> - approved sample slide style reference; match style only, do not copy layout
- <absolute path> - strict input asset; preserve labels/data/arrows/content

Read the JSON job file, then follow its `prompt` field exactly. Use the selected image backend and the recorded sample generation method only.
Deck-wide content contract for the job prompt (applies to every page of this deck):
- Global style anchoring: this page's visual style, palette, and composition language must stay anchored to the approved sample, the locked visual direction, and the deck master. Do not drift page by page; inherit the style language only, never the sample's layout.
- Visual translation: the job prompt describes both the illustration AND the text that must appear on the image (this page's title, key points, or short phrases). On-image text is content, not decoration — render the page fully illustrated with its copy baked in, never as blank space waiting for captions.
- On-image text language must match the deck's confirmed output language exactly (the same language as this page's title and points).
- On-image text volume follows the deck's confirmed mode: detailed mode may carry fuller on-image copy (page points plus one or two explanatory lines); slides mode (the lean default) keeps on-image text minimal — the main title or a few keywords — while page copy lives in the slide's own text containers.
- Page count is a hard contract: the deck ships exactly the page count frozen in the confirmed content contract and deck master, and this job is exactly one of those pages. Do not fold neighboring pages' content into this page and do not drop this page's content points; report `blocker=page_count_mismatch` if the dispatched job set or slide number visibly contradicts the confirmed contract page count.
- Deck style lock: once the sample is approved, the parent freezes a compact deck-level style lock (outer shell constants only: paper/background tone, page-number position and form, title treatment and optical size tier, grid/corner construction marks, people policy, expression tier) into the deck-level `style_lock` field. When the job file carries it, reuse that lock text verbatim in this page's prompt; the outer shell must not drift page by page — only the central semantic figure area changes with the content.
- Page role lock: every page prompt declares exactly one page role (cover | body | closing, aligned with the deck master's page roles). Body-page titles must be optically the same size across all body pages; a short title is never enlarged to fill space. Only the cover role may scale the title up.
- Required text only: the confirmed deck master freezes a per-page `required_text[]` whitelist — every content-bearing visible text item of the page (title, points, labels, captions, fixed furniture copy). Render exactly and only the whitelisted items, verbatim; any content-bearing text, label, or micro-annotation beyond the whitelist counts as invented content and fails QA. Decorative texture marks are not content-bearing text.
- Avoid list + pre-generation consistency pass: the tail of every page prompt carries an Avoid list derived from the locked style brief's forbidden list plus the universal prohibitions (watermark, fake logos, extra page numbers, footer date stamps, English filler, invented micro-labels, placeholder text). Before generating, run the multi-page consistency pass: same page-number position on every page? same outer shell? body titles optically the same size, short titles included? canvas exactly 16:9? layouts semantic rather than randomly varied? whitelist short enough to render cleanly?
- Failure tolerance (E4 three-tier protocol): per-page failures retry by stage, up to 3 attempts; whole-deck sweeps are capped at 2 rounds; already-rendered pages are skipped on retry. Full protocol in `references/execution-contract.md`.
You must produce the final slide candidate by calling the selected image generation backend:
- Built-in mode: use the built-in image generation/editing tool.
- CLI/API fallback generate mode: use `"<absolute leo-ppt CLI path>" upstream --backend-contract <absolute run dir>/input/backend-contract.json codex-ppt -- image generate --size 2560x1440 --prompt-file <job-prompt> --out <candidate-path>`.
- CLI/API fallback edit mode: use `"<absolute leo-ppt CLI path>" upstream --backend-contract <absolute run dir>/input/backend-contract.json codex-ppt -- image edit --size 2560x1440 --prompt-file <job-prompt> --image <absolute-input-path> --out <candidate-path>`; repeat `--image` for every required reference.

Forbidden for final slide image creation:
- local drawing or rendering scripts
- Pillow-generated slides
- SVG, HTML/CSS, or canvas screenshots
- python-pptx/PptxGenJS/native PPT layout screenshots
- manually composited text, card, chart, or image overlays

Sole exception: the parent-authorized text-fidelity-fallback (TF-2) mode after sample re-confirmation — base image still from the confirmed backend; the overlay text layer is produced deterministically by `scripts/overlay_text.py` from the required_text whitelist verbatim. Workers never perform this overlay themselves.

If you cannot use the selected image backend, stop and return `blocker=<reason>` instead of creating a lower-quality replacement.
If you cannot follow the recorded sample generation method, stop and return `blocker=<reason>` instead of switching tools.
If the backend cannot produce the required 16:9 size, stop and return `blocker=aspect_ratio_unsupported` instead of emitting a non-16:9 image.
Do not edit slide job files, origin_image, speech.md, or assemble the PPT.

Before returning, visually check:
- the produced PNG's actual pixel dimensions match the required 16:9 size exactly (read the image file header, not the CLI arguments)
- Chinese text is readable and not garbled
- every required title, number, unit, label, and citation matches the approved slide job exactly
- style matches the approved sample slide and stays anchored to the locked visual direction (no page-by-page drift)
- body-page title is optically the same size as the other body pages — a short title is NOT enlarged to fill space
- every `required_text` whitelist item appears verbatim, and no content-bearing text beyond the whitelist is present
- on-image text appears where the job prompt specifies it, uses the deck's confirmed output language, and respects the confirmed mode's text volume (detailed = fuller copy, slides = minimal)
- required source images are visibly included and not replaced by a similar redraw
- no overlapping or truncated important content
- every content point from the job maps into a distinct on-canvas container (no point without a home, no empty container)
- charts preserve approved values, units, labels, legends, and ordering; do not invent missing data
- no date stamp or timestamp in the footer (page-number form follows the deck style lock; a footer date stamp is invented furniture text and fails QA even if typographically clean)

When returning, also hand back page_type (chart | text-heavy | image), attempts, and backend_tokens so the parent can record them for backend routing stats (they flow into `image record --page-type/--attempts/--tokens`).

Return only:
backend_used=<built-in image tool OR absolute leo-ppt CLI path + upstream codex-ppt -- image>
output_pixels=<actual WIDTHxHEIGHT read from the produced PNG header>
selected_source=/absolute/path/to/$CODEX_HOME/generated_images/.../ig_*.png
qa_note=<one sentence; on retry also state target-check verdict AND spillover-check verdict>
worker_duration_seconds=<measured total worker seconds>
backend_duration_seconds=<measured backend call seconds, or not-recorded>
backend_tokens=<image backend token usage for this page if reported by the backend, or not-recorded>
```
