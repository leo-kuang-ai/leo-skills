# 表达优先重构完成矩阵

当前整体为 **partial**；U1–U13 均保留 required gaps，不符合 goal complete。最新完整有序验证：**2232 tests，0 failures、0 errors，exit 0，source_stable=true**。

逐行文件、符号、实现证据、命令、退出码、日志摘要及历史见 [JSON 账本](expression-first-completion-matrix.json)。历史 receipts 只作历史证据；本页与 JSON 的 current_evidence 指向本轮新增证据。

## U1–U13

| 单元 | 状态 | 文件与符号 | 当前测试与结果 | 剩余 required gaps |
| --- | --- | --- | --- | --- |
| U1 | partial | `runtime/src/leo_ppt_generator/content_pack.py:compile_page_expression`<br>`runtime/src/leo_ppt_generator/page_intent.py:load_page_type_regime`<br>`scripts/lint_page_type_regime.py:scan_active_regime_residue`<br>`references/authoring/page-expression-example.md`<br>`runtime/src/leo_ppt_generator/schemas/page-content-pack-v2.schema.json`<br>`runtime/src/leo_ppt_generator/page_intent.py:_parse_page_type_regime`<br>`tests/test_page_intent_routing.py` | V2: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/schemas.log))<br>V3: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/regime-lint.log))<br>V6: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/expression-consumers.log))<br>V9: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/full-suite.log)) | U12 仅恢复历史字节并导出单页，尚无完整可比配对视觉基线；不追认改动前已冻结 |
| U2 | partial | `runtime/src/leo_ppt_generator/qualification.py:verify_capability_evidence`<br>`runtime/src/leo_ppt_generator/qualification.py:layout_capability_contract`<br>`scripts/capability_manifest.py:build_qualification_manifest`<br>`runtime/src/leo_ppt_generator/content_projection.py:precompile_binding`<br>`runtime/src/leo_ppt_generator/relation_oracle.py:evaluate_output`<br>`runtime/src/leo_ppt_generator/render/page.py:render_page`<br>`scripts/probe_relation_capabilities.py:run_probes`<br>`runtime/src/leo_ppt_generator/template_inputs.py:slot_input_path_errors`<br>`runtime/src/leo_ppt_generator/raster_oracle.py:evaluate_raster_output`<br>`runtime/src/leo_ppt_generator/raster_text.swift`<br>`runtime/src/leo_ppt_generator/capability_probes.py:_run_image_case`<br>`runtime/pyproject.toml`<br>`runtime/src/leo_ppt_generator/qualification.py:verify_provider_qualification`<br>`runtime/src/leo_ppt_generator/quality_replay.py:verify_capability_publication`<br>`runtime/src/leo_ppt_generator/capability_probes.py:run_probes`<br>`runtime/src/leo_ppt_generator/capability_probes.py:image_probe_inputs`<br>`template-library/canonical/executable/recipes/p25-spec-table/recipe.json`<br>`template-library/canonical/layouts/p25-spec-table/layout.json`<br>`runtime/src/leo_ppt_generator/image_deck/recipe.py:validate_recipe_content`<br>`runtime/src/leo_ppt_generator/schemas/image-recipe-v1.schema.json`<br>`template-library/governance/schemas/image-recipe-v1.schema.json`<br>`tests/test_image_expression_adapter.py:TableImageRecipeTests`<br>`template-library/canonical/layouts/manifest.json` | V2: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/schemas.log))<br>V4: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/layout-lint.log))<br>V5: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/template-lint.log))<br>V6: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/expression-consumers.log))<br>V9: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/full-suite.log)) | image probe已接入像素OCR和实际Provider/几何证据导入，但尚无真实正反导出；五关系10份输入已准备，首批6次付费调用范围仍待答复，新增准备输入不扩大授权<br>已配置 qianxing/gpt-image-1 且凭据可用，当前状态 configured_unverified；尚无真实 Provider HTTP 调用及对应导出证据<br>缺视觉裁决与 publication-qualified 能力；user/proposal scope、全部消费者和双 lane 最终集成仍需关闭<br>正式U6-A capability晋升的真实正向链仍未运行；不可用负例/机制回归代替 |
| U3 | partial | `runtime/src/leo_ppt_generator/content_projection.py`<br>`runtime/src/leo_ppt_generator/layout_selection.py`<br>`runtime/src/leo_ppt_generator/content_preview.py`<br>`runtime/src/leo_ppt_generator/layout_selection.py:allocate_deck`<br>`template-library/canonical/executable/recipes/p25-spec-table/recipe.json`<br>`template-library/canonical/layouts/p25-spec-table/layout.json`<br>`runtime/src/leo_ppt_generator/image_deck/recipe.py:validate_recipe_content`<br>`runtime/src/leo_ppt_generator/schemas/image-recipe-v1.schema.json`<br>`template-library/governance/schemas/image-recipe-v1.schema.json`<br>`tests/test_image_expression_adapter.py:TableImageRecipeTests` | V6: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/expression-consumers.log))<br>V9: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/full-suite.log)) | 真实双 lane 与最终 v2 catalog 集成仍待验证 |
| U4 | partial | `runtime/src/leo_ppt_generator/application/expression_pipeline.py`<br>`runtime/src/leo_ppt_generator/application/routes.py`<br>`runtime/src/leo_ppt_generator/application/run_index.py`<br>`runtime/src/leo_ppt_generator/image_deck/expression_adapter.py:verify_provider_export`<br>`runtime/src/leo_ppt_generator/ocr_alignment.py:record_alignment`<br>`runtime/src/leo_ppt_generator/cli.py:dispatch`<br>`tests/test_ocr_alignment.py:CliAlignmentIntegrationTest`<br>`runtime/src/leo_ppt_generator/asset_resolver.py:AssetResolver.library_session`<br>`tests/test_expression_pipeline.py` | V6: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/expression-consumers.log))<br>V9: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/full-suite.log)) | 真实image Provider导出、OCR准入与双lane端到端正向集成仍无证据 |
| U5 | partial | `runtime/src/leo_ppt_generator/task_local_layout_proposals.py`<br>`runtime/src/leo_ppt_generator/capability_probes.py:run_probes`<br>`runtime/src/leo_ppt_generator/layout_selection.py:qualified_pool`<br>`runtime/src/leo_ppt_generator/content_projection.py:precompile_binding`<br>`runtime/src/leo_ppt_generator/application/expression_pipeline.py:run_expression_pipeline`<br>`runtime/src/leo_ppt_generator/render/page.py:render_page`<br>`tests/test_task_local_expression_proposals.py:ProposalPipelineTests`<br>`references/authoring/task-local-proposal.md` | V6: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/expression-consumers.log))<br>V9: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/full-suite.log)) | 真实 image proposal oracle/Provider 导出和视觉资格未验证<br>HTML 仍仅 validation provisional，未证明真实用户任务与视觉收益 |
| U6 | partial | `runtime/src/leo_ppt_generator/quality_metrics.py`<br>`scripts/run_quality_scorecard.py`<br>`scripts/compute_impact.py`<br>`runtime/src/leo_ppt_generator/quality_replay.py:execute_replay_request`<br>`runtime/src/leo_ppt_generator/quality_replay.py:evaluate_quality_replay`<br>`runtime/src/leo_ppt_generator/quality_replay.py:evaluate_user_outcomes`<br>`runtime/src/leo_ppt_generator/quality_metrics.py:deck_quality_for_run`<br>`runtime/src/leo_ppt_generator/schemas/quality-replay-v1.schema.json`<br>`references/quality-replay.md`<br>`runtime/src/leo_ppt_generator/quality_replay.py:capability_publication_files` | V2: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/schemas.log))<br>V8: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/quality.log))<br>V9: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/full-suite.log)) | 尚无正式 U6-A/B、R-85 留出集、完整同环境旧链配对视觉证据或可定位的用户差页回放<br>image输出oracle已实现并做本机像素回归，但真实Provider/image与U6-A/B尚未完成，无法签发双lane/visual_validated<br>用户收益无真实成对观测，保持 not_run；机制数据不代表用户收益 |
| U7 | partial | `runtime/src/leo_ppt_generator/library_migration.py:preview_migration`<br>`runtime/src/leo_ppt_generator/library_migration.py:scan_consumer_closure`<br>`runtime/src/leo_ppt_generator/library_migration.py:validate_plan_contract`<br>`runtime/src/leo_ppt_generator/schemas/migration-plan-v2.schema.json`<br>`scripts/migrate_template_library.py:main`<br>`runtime/src/leo_ppt_generator/library_migration.py:CLOSURE_FILES` | V2: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/schemas.log))<br>V7: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/migration.log))<br>V9: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/full-suite.log)) | 缺预迁移价值收据，U7-B 未运行；当前 U7-A 计划只作当时合同基线，后续证据/文档变化不能沿用为执行快照<br>完整消费者变更必须在执行 mapping/target hashes 中冻结后才能 stage |
| U8 | partial | `runtime/src/leo_ppt_generator/template_catalog.py:LibraryContext`<br>`runtime/src/leo_ppt_generator/template_catalog.py:build_catalog`<br>`runtime/src/leo_ppt_generator/template_catalog.py:read_catalog`<br>`runtime/src/leo_ppt_generator/template_catalog.py:publish_catalog`<br>`runtime/src/leo_ppt_generator/asset_resolver.py:AssetResolver`<br>`runtime/src/leo_ppt_generator/schemas/template-library-v2.schema.json`<br>`runtime/src/leo_ppt_generator/schemas/template-registry-v2.schema.json`<br>`template-library/governance/rules/asset-locations-v2.json`<br>`scripts/capability_manifest.py`<br>`runtime/src/leo_ppt_generator/asset_resolver.py:AssetResolver._require_available`<br>`tests/test_template_catalog_v2.py:test_warmed_resolver_rejects_maintenance_in_every_cached_consumer`<br>`runtime/src/leo_ppt_generator/asset_resolver.py:AssetResolver.library_session`<br>`runtime/src/leo_ppt_generator/asset_resolver.py:_library_read`<br>`runtime/src/leo_ppt_generator/template_catalog.py:scan_records`<br>`tests/test_template_catalog_v2.py`<br>`tests/test_library_bundle.py:IsolatedInstallTest` | V7: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/migration.log))<br>V9: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/full-suite.log)) | 当前 delivery 仍为 v1 library/catalog，旧默认 reader/builder 尚存，v2 尚非唯一活动协议<br>正式 U13 staging 未准入；v2 publication-qualified pairing 与真实 image 证据尚未取得 |
| U9 | partial | `runtime/src/leo_ppt_generator/asset_resolver.py`<br>`scripts/capability_manifest.py:main`<br>`tests/test_library_bundle.py`<br>`tests/expression_test_support.py:real_validation_inputs_v2`<br>`tests/test_effective_binding.py`<br>`tests/test_design_projection.py`<br>`tests/test_design_execution_binding.py`<br>`runtime/src/leo_ppt_generator/library_migration.py:scan_consumer_closure`<br>`samples/style-gallery`<br>`tests/test_content_projection.py`<br>`tests/test_dashi_integration_fixtures.py`<br>`tests/test_library_bundle.py:IsolatedInstallTest`<br>`runtime/src/leo_ppt_generator/page_intent.py:load_page_type_regime`<br>`tests/test_page_intent_routing.py` | V6: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/expression-consumers.log))<br>V7: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/migration.log))<br>V9: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/full-suite.log)) | 当前扫描287处active旧引用；固定十个消费者根及CHANGELOG全部存在，unclassified_hits=0；须完成reader/fallback/alias/路径及fixture/eval切换<br>尚未取得staging/delivery active_legacy_hits=0 |
| U10 | partial | `runtime/src/leo_ppt_generator/execution_pairing.py:derive_execution_pairings`<br>`runtime/src/leo_ppt_generator/schemas/execution-pairing-v1.schema.json`<br>`runtime/src/leo_ppt_generator/layout_selection.py:qualified_pool`<br>`runtime/src/leo_ppt_generator/content_projection.py:precompile_binding`<br>`template-library/canonical/executable/recipes/p25-spec-table/recipe.json`<br>`template-library/canonical/layouts/p25-spec-table/layout.json`<br>`runtime/src/leo_ppt_generator/image_deck/recipe.py:validate_recipe_content`<br>`runtime/src/leo_ppt_generator/schemas/image-recipe-v1.schema.json`<br>`template-library/governance/schemas/image-recipe-v1.schema.json`<br>`tests/test_image_expression_adapter.py:TableImageRecipeTests` | V2: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/schemas.log))<br>V6: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/expression-consumers.log))<br>V7: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/migration.log))<br>V9: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/full-suite.log)) | v2 catalog 与全部活动消费者闭合尚未完成<br>真实 image lane 配对与输出证据仍未验证 |
| U11 | partial | `runtime/src/leo_ppt_generator/library_migration.py:verify_migration`<br>`runtime/src/leo_ppt_generator/library_migration.py:publish_migration`<br>`runtime/src/leo_ppt_generator/library_migration.py:cleanup_migration`<br>`runtime/src/leo_ppt_generator/library_migration.py:verify_final_receipt`<br>`runtime/src/leo_ppt_generator/library_migration.py:_recover_cleanup_rollback`<br>`runtime/src/leo_ppt_generator/library_migration.py:_release_cleanup_maintenance`<br>`scripts/migrate_template_library.py`<br>`tests/test_migration_transaction.py`<br>`tests/test_migration_phases.py`<br>`references/template-library-migration.md`<br>`runtime/src/leo_ppt_generator/library_migration.py:_converged_hashes`<br>`runtime/src/leo_ppt_generator/library_migration.py:verify_consumer_closure`<br>`tests/test_migration_transaction.py:MigrationTransactionTests._hard_interrupt_publication`<br>`runtime/src/leo_ppt_generator/library_migration.py:_publication_identity`<br>`runtime/src/leo_ppt_generator/library_migration.py:_verify_publication_confirmation`<br>`runtime/src/leo_ppt_generator/library_migration.py:_seal_publication_receipt`<br>`runtime/src/leo_ppt_generator/library_migration.py:_check_cleanup_journal`<br>`runtime/src/leo_ppt_generator/library_migration.py:fsync_directory`<br>`runtime/src/leo_ppt_generator/library_migration.py:_library_lock`<br>`runtime/src/leo_ppt_generator/library_migration.py:library_operation`<br>`runtime/src/leo_ppt_generator/library_migration.py:locked_publication`<br>`runtime/src/leo_ppt_generator/styles.py:save_style`<br>`runtime/src/leo_ppt_generator/render/page.py:render_page`<br>`scripts/style_pack.py:cmd_import`<br>`scripts/style_pack.py:cmd_adopt`<br>`scripts/capability_manifest.py`<br>`tests/test_style_pack.py`<br>`runtime/src/leo_ppt_generator/page_intent.py:load_page_type_regime` | V2: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/schemas.log))<br>V7: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/migration.log))<br>V9: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/full-suite.log)) | 仅文件事务、拒绝门及 v2 构建/导出回归通过；尚无真实高层 preview→stage→verify→publish→cleanup 正向闭环<br>已接入操作期共享锁并验证真实竞争；全部活动消费者在完成 U9 切换后的正式 publish 期间仍需端到端复核，当前 Darwin 证据不能外推其他平台<br>正式 publication-ready、cleanup、delivery convergence 受缺 U6-A/image/consumer closure 证据阻塞；进程硬中断的高层恢复场景仍需补验 |
| U12 | partial | `runtime/src/leo_ppt_generator/quality_replay.py:verify_legacy_baseline`<br>`runtime/src/leo_ppt_generator/quality_replay.py:freeze_legacy_baseline`<br>`runtime/src/leo_ppt_generator/capability_probes.py:run_probes`<br>`template-library/evidence/oracles/relation-output-v1.json` | V6: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/expression-consumers.log))<br>V8: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/quality.log))<br>V9: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/full-suite.log)) | 尚无正式完整旧链 baseline manifest、3 册同环境配对视觉、真实 image baseline 与 R-85 留出集<br>单页历史 fixture 导出不代表真实任务、用户差页或视觉收益；不能追认提前冻结 |
| U13 | partial | `runtime/src/leo_ppt_generator/library_migration.py:stage_migration`<br>`runtime/src/leo_ppt_generator/library_migration.py:materialize_shadow_library`<br>`scripts/migrate_template_library.py`<br>`tests/test_migration_phases.py`<br>`runtime/src/leo_ppt_generator/library_migration.py:_unlink_cas` | V2: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/schemas.log))<br>V7: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/migration.log))<br>V9: exit 0 ([日志](expression-verification-2026-09-16-table-recipe-final-v3/full-suite.log)) | U7-B 价值前置缺失，正式 stage 未运行；高层 stage 中断恢复/重试与正向 receipt 尚缺真实验证<br>完整 U9 消费者改动与最终 target hashes 必须收口到同一 plan；不能把临时 converter 或目录复制当正式迁移 |

## 本轮落地与证据

- U2/U3/U10：新增规格表 recipe，比较/趋势共用 layout owner 的容量约束；五关系正反10份输入可准备，资格仍为 unverified。
- U1/U9/U11：regime 通过正式 bundle 定位，每次读取验证当前字节与维护锁；安装态错误已实测复现并修复。
- U8/U9：v2 复制与链接安装都可解析新 recipe；当前 delivery 的 v1 协议与287处活动旧引用尚未正式切换。

- U1：[u1-regime-bundle-red-2026-09-16.log](u1-regime-bundle-red-2026-09-16.log)；[u2-table-recipe-installed-wheel-v2-2026-09-16.json](u2-table-recipe-installed-wheel-v2-2026-09-16.json)；[table-recipe-inline-review-2026-09-16.json](table-recipe-inline-review-2026-09-16.json)
- U2：[u2-table-recipe-live-probes-v2-2026-09-16.json](u2-table-recipe-live-probes-v2-2026-09-16.json)；[u2-current-probes-table-recipe-v2-2026-09-16.json](u2-current-probes-table-recipe-v2-2026-09-16.json)；[u2-image-prepared-inputs-v7-2026-09-16.json](u2-image-prepared-inputs-v7-2026-09-16.json)；[u2-table-recipe-html-byte-comparison-2026-09-16.json](u2-table-recipe-html-byte-comparison-2026-09-16.json)
- U3：[table-recipe-inline-review-2026-09-16.json](table-recipe-inline-review-2026-09-16.json)；[u2-table-recipe-installed-wheel-v2-2026-09-16.json](u2-table-recipe-installed-wheel-v2-2026-09-16.json)
- U8：[u2-table-recipe-wheel-v2-2026-09-16.json](u2-table-recipe-wheel-v2-2026-09-16.json)；[u2-table-recipe-installed-wheel-v2-2026-09-16.json](u2-table-recipe-installed-wheel-v2-2026-09-16.json)
- U9：[consumer-closure-table-recipe-2026-09-16.json](consumer-closure-table-recipe-2026-09-16.json)；[u2-table-recipe-installed-wheel-v2-2026-09-16.json](u2-table-recipe-installed-wheel-v2-2026-09-16.json)
- U10：[u2-image-prepared-inputs-v7-2026-09-16.json](u2-image-prepared-inputs-v7-2026-09-16.json)；[u2-current-probes-table-recipe-v2-2026-09-16.json](u2-current-probes-table-recipe-v2-2026-09-16.json)
- U11：[consumer-closure-table-recipe-2026-09-16.json](consumer-closure-table-recipe-2026-09-16.json)；[table-recipe-inline-review-2026-09-16.json](table-recipe-inline-review-2026-09-16.json)
- U12：[u2-table-recipe-live-probes-v2-2026-09-16.json](u2-table-recipe-live-probes-v2-2026-09-16.json)；[u2-table-recipe-html-byte-comparison-2026-09-16.json](u2-table-recipe-html-byte-comparison-2026-09-16.json)

## 命令与终态

完整 manifest：[verification.json](expression-verification-2026-09-16-table-recipe-final-v3/verification.json)；监督进程 session 84773 已退出0。

V1 / compileall / exit 0

```sh
PYTHONPATH=runtime/src /Users/kuang/knowledge/leo-skills/leo-ppt-generator/runtime/.venv/bin/python -m compileall -q runtime/src scripts tests
```

V2 / schemas / exit 0 / 63 tests

```sh
PYTHONPATH=runtime/src /Users/kuang/knowledge/leo-skills/leo-ppt-generator/runtime/.venv/bin/python -m unittest tests.test_library_contracts tests.test_page_expression_contract tests.test_execution_pairing tests.test_image_expression_adapter tests.test_quality_replay tests.test_migration_phases
```

V3 / regime-lint / exit 0

```sh
PYTHONPATH=runtime/src /Users/kuang/knowledge/leo-skills/leo-ppt-generator/runtime/.venv/bin/python scripts/lint_page_type_regime.py
```

V4 / layout-lint / exit 0

```sh
PYTHONPATH=runtime/src /Users/kuang/knowledge/leo-skills/leo-ppt-generator/runtime/.venv/bin/python scripts/lint_layout_grid.py
```

V5 / template-lint / exit 0

```sh
PYTHONPATH=runtime/src /Users/kuang/knowledge/leo-skills/leo-ppt-generator/runtime/.venv/bin/python scripts/lint_template_contract.py
```

V6 / expression-consumers / exit 0 / 137 tests

```sh
PYTHONPATH=runtime/src /Users/kuang/knowledge/leo-skills/leo-ppt-generator/runtime/.venv/bin/python -m unittest tests.test_content_pack tests.test_content_projection tests.test_content_preview tests.test_binding_v2 tests.test_deck_layout_selection tests.test_expression_pipeline tests.test_deck_projection_view tests.test_task_local_expression_proposals tests.test_qualification_evidence tests.test_relation_oracle tests.test_raster_oracle
```

V7 / migration / exit 0 / 82 tests

```sh
PYTHONPATH=runtime/src /Users/kuang/knowledge/leo-skills/leo-ppt-generator/runtime/.venv/bin/python -m unittest tests.test_migration_phases tests.test_migration_transaction tests.test_template_catalog_v2 tests.test_library_catalog tests.test_library_bundle tests.test_style_aliases_migration
```

V8 / quality / exit 0 / 104 tests

```sh
PYTHONPATH=runtime/src /Users/kuang/knowledge/leo-skills/leo-ppt-generator/runtime/.venv/bin/python -m unittest tests.test_quality_replay tests.test_expression_quality_channels tests.test_quality_scorecard tests.test_quality_metrics tests.test_compute_impact tests.test_visual_measure_rules tests.test_visual_qa
```

V9 / full-suite / exit 0 / 2232 tests

```sh
PYTHONPATH=runtime/src /Users/kuang/knowledge/leo-skills/leo-ppt-generator/runtime/.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

## 实际能力与完成边界

| 层级 | 当前证据/状态 |
| --- | --- |
| mechanism | partial |
| real_runtime | 当前源码五关系HTML正反10张PNG；177文件源码/wheel/installed摘要一致；当前安装后7项regime/recipe测试退出0。上一轮44项安装态事务/catalog测试保留为历史，不外推当前安装态全量 |
| real_provider | not_run；首批6次付费调用范围待答复，本轮实际调用0；五关系10份输入仅为准备 |
| real_task | not_run |
| visual | 10张HTML同用例字节回归无变化；当前探针仍缺visual_review，正式U6-A/B、三册旧链配对及用户差页未运行 |
| user_benefit | not_run |
| publication | not_run；正式stage/publish/cleanup/convergence未闭环，本轮未commit/push/PR |
| independent_review | not_run；仅串行单Agent检查，status=degraded / verdict=Not ready |

- 最新关系探针 CLI exit 1 / blocked；HTML五组均 provisional，image无真实Provider及几何证据。不能将有序测试exit 0写成该探针通过。
- 旧源891/891已找回；这是此前逐字节核对记录，缺legacy source已不再列作阻塞。仍缺正式旧链完整baseline与配对视觉。
- 中间失败/中断保留：final-v1 layout摘要不符；final-v2全量2230项、2 failures；安装态旧wheel 7项中5 errors。最终v3与最新安装态结果已分别覆盖修复，不覆盖历史记录。
- 本轮只追加包内开发与证据、同步根CHANGELOG；未commit/push/PR，未调用goal complete。goal服务当前仍为既有blocked状态。
- 正式workflow helper只接受Git根，包根为target-repo-not-found；根.spec-first超出本次写入范围，formal closeout保持not_run。见[已记录的边界](maintenance-workflow-boundary-2026-09-16.json)。
