# Residual review findings — leo-2026-09-04-update-style-model

- **Source review run**: `spec-code-review` run `lfg-dashi-1788979338`（artifact: `/tmp/spec-first/spec-code-review/lfg-dashi-1788979338/`，7 名独立 reviewer，34 项 findings，13 项按资格规则应用、下列 21→13 项转 residual 跟踪——应用/残余账目见 run artifact `merged.json`）。
- **Plan**: `docs/plans/2026-09-10-001-feat-dashi-integration-plan.md`（dashi 集成 U1–U7）。
- **Tracker**: 未授权外部 tracker（`tracker_deferral_authorization: missing`），本文件为 durable no-PR sink。
- **Recorded**: 2026-09-10（LFG step 7）。

## 残余 findings（未应用，待后续裁决）

| P1 | leo-ppt-generator/references/layout-dispatch.md:7 | Deck allocation lane has no agent entry point |
| P2 | leo-ppt-generator/runtime/src/leo_ppt_generator/application/run_index.py:842 | Three parallel readers of frozen binding inputs, divergent corruption semantics |
| P2 | leo-ppt-generator/runtime/src/leo_ppt_generator/cli.py:2636 | content pack compiles unconfirmed masters |
| P2 | leo-ppt-generator/runtime/src/leo_ppt_generator/cli.py:559 | Two spellings for same fingerprint-conflict codes |
| P2 | leo-ppt-generator/runtime/src/leo_ppt_generator/cli.py:592 | cli.py grows past 3.7k lines with embedded content-freeze subsystem |
| P2 | leo-ppt-generator/runtime/src/leo_ppt_generator/cli.py:619 | Prepare freezes inputs before validating; poisons run |
| P2 | leo-ppt-generator/runtime/src/leo_ppt_generator/cli.py:662 | Selection-only freeze skips checks, projection gate skips |
| P2 | leo-ppt-generator/runtime/src/leo_ppt_generator/cli.py:665 | layout-selection frozen without per-page integrity checks |
| P2 | leo-ppt-generator/runtime/src/leo_ppt_generator/content_pack.py:378 | Pack fabricates 'user-confirmed' attestation by default |
| P2 | leo-ppt-generator/runtime/src/leo_ppt_generator/content_projection.py:395 | Number coverage passes via substring: 5% in 15% |
| P2 | leo-ppt-generator/runtime/src/leo_ppt_generator/render/receipt.py:224 | Receipt binds hand-edited pack without digest verification |
| P2 | leo-ppt-generator/runtime/src/leo_ppt_generator/render/receipt.py:446 | content_binding drift entry breaks changed-list shape |
| P3 | leo-ppt-generator/scripts/check_master_contract.py:126 | Dual page splitters coexist in check_master_contract, boundaries differ |

## 实施后真实运行补充观察

- **Prepare freezes inputs before validating; poisons run（上表 cli.py:619 项）在真实运行中复现**：`/tmp/dashi-realrun/runs/gen-2` 中，一份缺 `kind` 字段的 layout-selection 被 CAS 冻结后才被合同校验拒绝，修正后的同 run 重试以 `layout-selection_fingerprint_conflict` 永久卡死该 run（fail-closed 但不可恢复，只能新建 run）。证据留档于该 run 目录与计划文档 Evidence 补录。
- 真实运行还暴露并已修复一项收据缺陷（库回退模板指纹键崩溃，见 CHANGELOG「真实运行收据库回退修复」），不在本残余清单内。
