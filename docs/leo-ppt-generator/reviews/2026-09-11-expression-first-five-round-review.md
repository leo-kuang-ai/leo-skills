# 表达优先模板重构方案五轮全量评审

日期：2026-09-11  
目标方案：`docs/plans/2026-09-11-004-feat-leo-ppt-expression-first-plan.md`  
代码基线：`710846e20a900e02bd5349629015d6e3bd441510`（dirty worktree；本次仅更新方案与评审文档）

## 覆盖边界

本轮先建立完整分母，再逐文件/逐 JSON 解析，不以目录抽查推断结论：排除 `__pycache__`、`.venv`，保留源码、测试、模板库、references、evals 和 docs 活动文件；runtime 293 个文件、scripts 85 个文件、tests 263 个文件、template-library 1,936 个文件、references 67 个文件、evals 1,458 个文件、docs 131 个文件；Python 589 个、JSON 1,762 个，解析错误均为 0。此前未声明排除规则的 109/82/237 与 482/1,755 仅作历史记录，不作为当前分母。

## 五轮结论

1. **文档合同与准入**：发现 `artifact_readiness: review-required` 不属于 `spec-unified-plan/v1` 合法值；已改为 `implementation-ready`，并更新 `source_revision`。这只表示计划可作为实施输入，不表示代码完成。
2. **runtime、resolver、binding**：发现新 `axis-guide` 与现有 `axis` 的身份和消费者迁移未锁定；已固定 124 个稳定 slug 映射并重写完整 `asset_id`（`builtin:axis:<slug>` → `builtin:axis-guide:<slug>`），要求 `templates.py`、`layout_bank.py`、gallery 和测试在 U9 同批切换，U11 后拒绝旧 kind。catalog 损坏、composition 身份、隐式 point fallback 的 fail-closed 合同同时保留。
3. **迁移、catalog、原子发布**：发现 closure 扫描活动 `docs/plans` 会命中自身的迁移词；已增加 `plan-control` 与 `declared_plan_hits`，普通活动文件仍必须分类，只有 `unclassified_hits=0` 且 `active_legacy_hits=0` 才通过。preview/apply/verify/cleanup、staging、allowlist、摘要绑定和同代冲突均为硬门。
4. **表达质量与视觉验收**：发现旧 `test_page_expression.py` 不能证明 focus、reading order 和隐式 point fallback 已覆盖；已把这些断言写入 U1 与 Verification Contract。U6 必须在 U11 迁移产物之上完成用户差页的新链回放（内容包、绑定、HTML/image 导出和四维评分），U11 单独提供迁移前后内容/资产完整性对照；缺少差页身份时只能报告通用能力。
5. **跨方案一致性与实施准入**：未发现新的依赖环或范围冲突；清理重复 U8/Verification 条目，明确结构、表达、运行时、视觉和用户收益证据互不抵扣。

## 独立性与限制

runtime reviewer 返回了完整覆盖报告。migration 与 quality 两路独立 worker 因 429 未返回，因此本记录是多领域角色化五轮评审，独立性标记为 `partial/degraded`，不冒称三路独立专家结论。当前未执行代码迁移、真实双 lane 导出、外部模型调用或人工视觉验收；这些仍是 `spec-work` 阶段的必需证据。

## 处置

方案已吸收上述文档层 P1，保持 `implementation-ready`。进入实施后必须按 U1–U11 和 Verification Contract 逐门执行；任何门失败都不能宣称专项完成，也不能用 lint、单测或通用 fixture 替代真实导出与用户差页回放。

## 本轮独立复审补充（2026-09-12）

本轮重新读取目标方案、当前 HEAD `710846e20a900e02bd5349629015d6e3bd441510` 与 dirty worktree。上述分母为本轮快照；方案文档自身的新增行只影响 docs 计数，不改变 runtime/scripts/tests/template-library 的源码事实。

源码反例已确认：`content_projection.py` 仍在未声明 slot 时把 point 回填到 title/label；`verify_effective_binding()` 仍保留 v1 读取；`AssetResolver` 在缺少 catalog 时仍执行 canonical rebuild；`page_intent.py` 把 causal 压平为 system；`layout_proposals.py` 当前实现的是 R75 容量减法菜单，不是 U5/KTD9 的 bounded task-local patch。上述行为均与本方案的 fail-closed、无兼容桥和表达关系硬资格要求存在直接差距，必须在实施前逐项关闭。

项目虚拟环境 `leo-ppt-generator/runtime/.venv` 的可用性和 focused lint/test 结果沿用上一轮记录；本次未重新运行实现测试。表达专项命令在上一轮为 0 tests，因为 `tests/test_page_expression.py` 尚不存在；上一轮全量 unittest 的 2,046 项、4 failures、2 errors 仅是历史 baseline，不能代表当前 HEAD 的新运行结果。

独立性仍为 `partial/degraded`：本轮独立 worker 派发连续因 429 未返回，以上结论来自主 Agent 的源码证据与角色化钢人复核，不宣称独立专家全部通过。真实 HTML/image 导出、人工视觉评分和用户差页回放仍未完成，因此 `implementation-ready` 只表示计划合同完整，不表示代码或视觉交付完成。
