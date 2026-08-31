# Leo PPT Generator (English README)

Leo PPT Generator is an agent skill that produces image-style PowerPoint (PPTX)
decks, rebuilds images / PDFs / trusted Office files into object-level editable
PPTX, and upgrades existing image decks into fully or partially editable
versions — with delivery-grade discipline: every deck is verifiable, auditable,
and upgradeable. ([中文 README](README.md))

> Positioning: tools that "generate a pretty deck in one sentence" are
> abundant. This skill serves the moment when *the deck has to ship tomorrow*:
  sourced numbers, honest partial delivery, tamper-evident receipts, and human
  confirmation gates that cannot be skipped.

## Routes

- `generate` — build an image-style deck from an article, report, notes, or an
  outline.
- `direct-editable` — rebuild images / PDFs / user-confirmed-trusted PPTX into
  object-level editable slides.
- `upgrade-full` — upgrade an existing image deck to fully editable.
- `upgrade-selected` — upgrade only selected pages; the rest stay as images.

## Sample output & style gallery

Real pages from an evaluation run (synthetic materials, provenance recorded)
are embedded in the [Chinese README](README.md#成品样例); the
[style gallery](samples/style-gallery.md) lists all 11 built-in styles with
their intended scenarios (deterministically generated from the style library).

## Installation

```sh
npx skills add leo-kuang-ai/leo-skills -s leo-ppt-generator   # universal installer (78+ hosts)
```

Or via Claude Code plugin marketplace:

```sh
claude plugin marketplace add leo-kuang-ai/leo-skills && claude plugin install leo-ppt-generator@leo-skills
```

Manual / package installer (macOS & Windows), upgrade and uninstall loops, and
a paste-into-chat install guide for hosts without a CLI are documented in the
[Chinese README](README.md#安装). First run self-bootstraps the managed
runtime; never paste API keys into the chat.

## Security boundaries

- Office files of unknown or unconfirmed origin are rejected with
  `blocked/untrusted_office_input` — never opened, scanned, or "sanitized on
  request".
- Trusted PPTX still passes CLI preflight: macros, embedded objects, external
  relationships, remote templates, and corrupt structures fail closed.
- Credentials only via host injection, allow-listed environment references, or
  protected system storage.

## Delivery & verification

Every run lives in its own project directory with traceable state. Structural
validation is not visual equivalence: provider, OCR, Office viewer, desktop
PowerPoint, and human visual acceptance are reported separately. Delivery
claims require a sha256 fingerprint receipt (`delivery receipt verify`) —
`status: completed` is not delivery; only `delivery_readiness: accepted` closes
the loop. Speaker scripts export via `scripts/export_speaker_notes.py` (missing
notes are listed honestly, never invented), and pre-dispatch cost bands via
`scripts/estimate_run_cost.py`.

## Delivery-grade contract highlights

- Three-tier fact labeling: cited / estimated / illustrative — anything else is
  `unknown` and must be resolved, never printed.
- Number ledger and per-page master as the content source of truth; content
  fixes go through the master, never directly onto rendered images.
- Confirmation sequence (contract → outline → page master → visual direction →
  sample) cannot be waived by "don't ask me" — adjacent gates may be batched
  into one turn, but each artifact is still confirmed explicitly.
- Delivery profiles (`${LEO_PPT_HOME}/profiles/`) prefill the contract for
  returning users — preferences only, never business data, and never waiving
  the data-classification check.
- Academic vertical: say "学术模式" for thesis/defense flows (math load, figure
  orientation, section priority, minimal vs dense-defense tiering, figure
  evidence rules).

## Benchmark

`bench/` contains **leo-ppt-bench**, a portable 8-case benchmark of
delivery-grade disciplines (no fabricated numbers, no invented asset URLs, no
host-internals enumeration, non-skippable confirmations, unknown-Office
protection, honest partial delivery, no false completion, no fabricated
speaker notes) that can score *any* PPT skill via skill-up. See
[bench/README.md](bench/README.md).

## Compatibility

Installers target macOS arm64/x86_64 and Windows x64. Actual image providers,
OCR, desktop Office, and worker capabilities depend on the host environment.

## License

MIT — see [LICENSE](LICENSE). This English README summarizes the Chinese
README, which remains the detailed reference.
