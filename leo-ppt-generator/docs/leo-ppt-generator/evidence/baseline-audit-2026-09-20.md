# U6/U12 历史基线与双边重基线审计

审计时间：2026-09-20。范围：当前 `quality_replay.py`、导出 owner、恢复历史源码与方案 U6/U12。初始审计结论为 **partial / blocked**；本文包含随后落地的受控协议与验证结果，但不是 U6-A、U12 或 publication receipt。未调用 Provider，未把恢复历史追认为修改前捕获。

## 当前证据

历史工作区 `.migration-work/2026-09-15-u12-historical/source-manifest.json` 明确记录：

- `source_revision=710846e20a900e02bd5349629015d6e3bd441510`。
- `capture_mode=reconstructed-historical`，`source_files` 共 4290 项。
- 顶层只有 `source_revision / capture_mode / source_files / source_archive_sha256 / scope`；它本身没有捕获时的执行环境、输入选择合同或完整配对基线。
- 工作区源码目录之外只找到 `old-html/page.png`，没有旧 image 导出。
- 旧 HTML 的 receipt 记录 `renderer=playwright-chromium@1.62.0`、2560×1440、`overflow_check=pass`、`out_sha256=3d07ae03bf703d4be2d6535862d91aac9d10a8911174a0e8336a1accb94ab733`；其材料由历史测试 `MASTER` 提取，因此属于测试材料的真实 HTML 渲染，不是 recorded-task 留出集。
- 恢复版本没有 `image_deck/expression_adapter.py`。当前与恢复版本执行成员分别为 19 / 15 个；renderer 比较成员的差异为 `image_deck/expression_adapter.py`、`render/page.py`、`render/provenance.py`、`render/receipt.py`。

这些信息由项目 Python 环境直接读取当前文件得出；没有把上轮测试汇总用作本轮验证。

## 已证实的机制缺口

| 行 | 证据与影响 | 需要落地的最小修改 | 不能放松的边界 |
| --- | --- | --- | --- |
| B1 | `quality_replay.verify_legacy_baseline` 的 image 分支要求 `selection.binding`，并以该 binding 调用 `verify_provider_export`。后者调用新 `verify_binding_reference`。真实旧源码不存在新 expression adapter，旧 `ImageDeckAdapter.record` 只生成 PageArtifact；历史 `BackendExecutionContext.receipt` 只有配置/contract 字段，没有 HTTP request_id/响应/原图链。因此旧 image 原样导出无法满足新双层 binding 合同。 | 为历史来源提供独立且判别式的封存协议。旧 material、page、theme、selection、prompt/request、Provider contract、原始 HTTP 请求/响应/原图与最终 PNG 分别按字节绑定。传输部分复用 `verify_provider_export(binding=None)`，历史来源部分单独重核，生产 binding verifier 保持不变。 | 不给旧产物补造 expression/materialization digest；历史配置 receipt 不等于调用 receipt；缺原始响应不能由任意本地图补齐；`local-protocol-test` 不得作为真实旧 Provider 基线。 |
| B2 | `paired_environment_compatibility` 只能接受当前 renderer 成员与基线完全相同，否则报 `paired_renderer_source_rebaseline_required`。CLI 只有 `--freeze-baseline` 与 `--replay-plan`，未提供真正双边重基线 owner 或 receipt。 | 新增不可覆盖的 paired-rebaseline manifest/工具，明确引用原 baseline，保存旧决策源码与共同物化源码的两层快照。旧侧保持旧 selection/input/theme/资产，使用共同 renderer 重新导出；新侧走现有 routes.generate。只有双方实际导出与同环境检查通过，才可被 U6 作为新可比基线消费。 | 不允许手写 transition/status flag 免检；不把新 renderer 字节写入旧 source_snapshot 后声称原旧链未变化；不覆盖原 baseline；无任一侧导出仍 blocked。 |
| B3 | `qualification.is_execution_source`（105–108）仅纳入 `render/`、`providers/` 与几个显式文件。真实 HTTP owner 来自 `image_deck/expression_adapter.py:82–83` 导入的 `_vendor/codex_ppt/image_providers/`。`environment_fingerprint:141–144` 的 vendor_files 来自 `render.assets.vendor_dir:49–50`，只扫描 `assets/render-vendor`。现场 vendor_files 只有 Mermaid 两项，不含 HTTP owner；packages（115）也不含 openai/httpx。 | 统一执行来源合同补齐实际 Provider 传输 owner 及关键客户端版本；之后重新采集受影响 evidence。paired comparator 也必须使用同一规则，不能只更新一个列表。 | 不把 Provider contract digest 视为传输实现摘要；不以相同 endpoint/model 掩盖 SDK/adapter 漂移。 |
| B4 | 现有 baseline image 分支未明确排除 `evidence_source=local-protocol-test`；`verify_provider_export` 本身为协议测试允许该值。 | 历史基线准入显式强制 `provider-http`，并把 request/response/artifact/Provider contract 与历史 page selection 做完整 join。 | 协议测试可证明 verifier 行为，但不得升级真实 Provider 通道。 |
| B5 | 历史单页 selection 尚未形成正式封存描述，恢复 source manifest 也没有运行环境。当前 baseline HTML 仅对 template hash、data hash、renderer 非空和产物匹配做检查；不能由字符串推导同主题或原执行环境。 | 重放前采集完整环境、主题与旧 asset snapshot；正式 rebaseline 每对固定 material、theme family、实际 theme bytes、lane、Provider contract 与共同 browser/font/renderer 指纹。 | 不事后把当前环境填成 2026-09-15 的捕获环境；旧环境缺失时只允许在当前环境真实重跑两侧，保留 reconstructed-historical 来源标签。 |

Provider 源码漏 pin 的实测摘要：旧 `openai_compatible.py` 为 `aa4a8e5ebed78676c85f6377fe273b6d9b66810a9ed5391c8b6f5f6dc43eaa9d`，当前为 `42ba2aa798e542c7c67a4b9e1a120a9c808a9d38e4b27e75ba30babe98e08610`；两者均被当前 `is_execution_source` 判为 false。此结果证明当前 env 不覆盖该 owner，不证明任何 Provider 调用曾成功。

## 可落实的协议与执行顺序

1. 保持已有 v1 封存的可验证性；新增明确版本的历史协议，分别保存 `source_snapshot`（旧决策来源）与 `renderer_snapshot`（真正执行物化的共同来源）。所有引用使用现有 `{path, sha256}` 安全读取，禁止 symlink/越界/重复 canonical identity。
2. `legacy-image-export` 验证只承认真实 HTTP 附件：冻结 prompt/request、Provider contract、request_id/http_status、原始 response bytes、Provider 原图与实际归一化操作；图片字节必须从 response 可重建。历史选页与请求一一对应，不引入新 production binding。
3. paired-rebaseline plan 在执行前冻结：原 baseline reference、case/deck/page identity、材料、旧 selection/data/theme/asset snapshot、新 PipelineRequest、共同环境与来源摘要。新旧任一必需输入缺失时返回具体 gap，不能签发 passed receipt。
4. HTML 旧侧用现有 `render_page(binding=None)` 消费冻结输入，但必须由历史协议约束其 template/theme/asset 来源；它仅用于历史回放，不是生产绕过资格的新路由。新侧仍用 `routes.generate(PipelineRequest)`。相同公共 renderer 的两个执行回执分别保存，结束再重核环境与所有冻结输入。
5. image 只有在已有真实证据可完整核验，或另有该批调用授权时执行。旧 prompt 保持冻结，不能以新 recipe 重新构思旧侧。没有旧 prompt/Provider HTTP 证据时，准备器列出缺口；不能用新 prompt 的请求伪装旧链。
6. U6 消费真实 paired receipt 后仍执行现有 R-85 分母、至少三册 10–14 页、双 lane、四维 review 与 U6-B 用户差页门。重基线仅恢复可比较性，不自动满足这些验收项。

## 必要验证与当前状态

实现测试至少覆盖：旧 image 不依赖新 binding；缺原始响应/错 request/错 contract/错 page/协议测试来源拒绝；历史图或来源漂移 stale；共同 renderer/Provider/browser/font 任一变化 blocked；只重跑一侧拒绝；旧 baseline 不可覆盖；伪造 passed transition 不可准入；同源真实 HTML 两侧重放的产物/receipt 可复核。测试应与真实环境和 Provider 状态分开报告。

当前可以独立完成的是协议、准备器、HTML 双侧执行和拒绝分支。真实 image、recorded-task R-85 数据与配对视觉仍缺必需证据。U12 原定的“早于 U1”时间顺序已不可追认；恢复历史及重放只能明确记录为 reconstructed-historical，不支持该历史时序已满足的声明。

本次没有生成新基线、执行正式 migration 或声明 U6/U12 complete。审计文档路径在写入前为 absent，无既有 dirty owner 被覆盖。

## 本轮已落地的受控工具（2026-09-20）

- `runtime/src/leo_ppt_generator/schemas/legacy-image-export-v1.schema.json`：历史 image 传输封存合同；不包含新双层 binding 字段。
- `runtime/src/leo_ppt_generator/schemas/paired-rebaseline-v1.schema.json`：旧/新输入、材料、主题族、lane、输出和当前环境的封存计划合同。
- `runtime/src/leo_ppt_generator/quality_replay.py`：`validate_legacy_image_export`、`validate_paired_rebaseline_plan`、`execute_paired_html_rebaseline`；`paired_environment_compatibility` 已把 `_vendor/codex_ppt/image_providers/` 视为物化执行源码。
- `scripts/run_quality_scorecard.py`：`--prepare-paired-rebaseline <descriptor>` 封存不可覆盖计划；`--paired-rebaseline-plan <plan> --execute-paired-rebaseline` 实际执行双方 HTML；不带执行参数仅重核。新侧通过 `execute_replay_request → routes.generate`，并重核 committed input、双层 binding、machine scorecard 和真实导出；旧侧固定历史 snapshot/template/input/theme。image case 明确 blocked，工具不会调用 Provider。
- `verify_paired_rebaseline` 重新计算双方结果，拒绝单侧缺失、手改通过状态、产物漂移、来源或环境变化。验证后的 paired receipt 可直接作为 U6 计划的 `baseline` 引用，原基线引用、原 source_snapshot 和 `capture_mode` 保留；共同物化源码单独存入 `execution_source_snapshot`。U6 同时检查 candidate 导出摘要与两层 binding 未偏离该 pair，不签发任何视觉评分。
- 通过收据写入 `qa/paired-rebaseline.json`；blocked 尝试使用单独的摘要命名，所有已有证据只允许字节相同的幂等读取。publication 自包含校验拒绝借用任务根外的新侧执行库。
- `tests/test_quality_replay.py` 新增 Provider source/SDK drift、合成历史 HTTP 归档协议正反例、local protocol image 拒绝、真实浏览器双方 HTML、丢失一侧/产物漂移/改材料/路径越界/子集冒充/幂等封存/CLI 消费与自包含范围回归。合成 HTTP 归档测试不代表真实 Provider 调用。

验证：`PYTHONPATH=runtime/src runtime/.venv/bin/python -m unittest tests.test_quality_replay tests.test_quality_scorecard tests.test_visual_qa tests.test_visual_measure_rules` 为 **75 tests / 52.635s / exit 0**，执行句柄 79390 已取得最终汇总。源码、CLI、测试的 compileall 为 exit 0；两份正式 schema 的 `Draft202012Validator.check_schema` 与空对象负例 exit 0；范围内 diff check exit 0。仓库完整有序验证仍由主线收口，以上不代表全量完成。没有真实 image HTTP 调用。临时测试目录实际生成并重核过双方 HTML 的 `paired-runtime-only` 收据，但它只证明机制，不是历史真实任务、R-85、视觉或用户收益证据。

准备描述须为 `paired-rebaseline-plan` 的 `schema_version / kind / baseline / cases` 四字段；工具补充当前 `environment`、各新侧 `new_fingerprint` 和 plan digest。每个旧 selection 必须包含 `template_id / input / theme / binding`，其中 binding 是历史字节引用，工具不转换它；`old_snapshot` 引用的 manifest 包含 `root / files / source_roots`，files 是 snapshot 根内全部文件的摘要清单。`source_roots` 明确给出 `builtin` 和可选 `user` 对应的历史库根（任务根内相对路径）；每个 canonical 文件必须在该历史根的相同相对路径下具有相同摘要，并存在于原 baseline.source_snapshot，不能只凭字节摘要曾在历史文件集合中出现。新请求须提供明确绝对 library_root；所有写入路径仍限制在任务根内。新侧任何资格门失败都会阻塞该 pair。

## 独立 review 的 P1 修复

- `_verify_historical_html_binding` 对新双摘要调用生产 `verify_dual_binding_digests` 与 `verify_binding_reference`，将 binding 与原导出 receipt 锚定；对历史 schema=2 单摘要只使用历史 `710846e` 的独立算法，原 receipt 必须携带同一摘要。缺 binding、theme 或原 receipt 摘要明确 `blocked`；修改主题后重签 binding 仍无法替换原 receipt。历史兼容只用于此回放桥，生产 verifier 继续拒绝单摘要和新旧混用。
- `_rebaseline_snapshot` 在历史路径校验后，再核每个 binding asset pin 的 `asset_id / origin_scope / revision / files` 与 resolver 实际 fingerprint；manifest 内身份必须与 catalog 和 pin 相同。要求所选 template/layout 均有 pin，拒绝非法 pin 类型、未知 scope、空 pin 集合、历史字节拼接和 catalog 身份偷换。
- 输出保护包括原基线全部 material/selection/artifact/receipt、selection 的 input/binding、snapshot descriptor、snapshot 根和所有历史 source_roots；不能将其中任意文件变成输出目录、覆盖其祖先或把新输出放进历史 snapshot。
- 新增测试以明确的合同机制数据测试历史单摘要；真实浏览器集成测试继续实际生成双侧 HTML 并核验收据。两者都不升级为真实旧 image、recorded-task、R-85、视觉质量或用户收益证据。

修复中的第一轮历史 helper 验证实际发现 `effective=None` 的 `AttributeError` 和缺原 receipt 摘要错误分类（5 tests，exit 1）；随后已修正。第一轮完整 `tests.test_quality_replay` 为 40 tests / 49.403s / exit 1，唯一失败是新增 catalog 攻击测试取错 registry 路径；已改为解析 snapshot 的 current generation 后读取真实 registry。最终复跑结果另行记录，不把这两次失败隐藏为通过。

P1 修复的最终局部验证：`PYTHONPATH=runtime/src runtime/.venv/bin/python -m unittest tests.test_quality_replay tests.test_quality_scorecard tests.test_visual_qa tests.test_visual_measure_rules` 为 **86 tests / 59.796s / exit 0**，执行句柄 `54913` 已取得 `OK` 与最终退出码。`quality_replay.py`、CLI、测试文件的 `compileall -q` 为 exit 0；两份正式 schema 的 `Draft202012Validator.check_schema` 与空对象负例为 exit 0；范围内 `git diff --check` 为 exit 0。Pillow 弃用警告是本次输出的已有兼容性提示，不影响该测试结果。没有运行 full suite、真实 image Provider 或正式 R-85；全局资格与最终验收仍由主线完成。

## image 双侧执行器补齐

此前“仅执行 HTML”是前一子轮的实现边界。当前通用 owner 已改为 `execute_paired_rebaseline`，CLI 与只读 verifier 均切换到此 owner，没有保留旧 HTML-only alias。

- 旧 image 只接受原 baseline 的 `legacy-image-export` manifest；新增可选 `theme_source`（image 重基线必需）必须在该历史 source_snapshot 内，selection.theme 与其实际 JSON 相等。原 prompt/request、material、Provider contract、HTTP response/原图/PNG 全部重核。缺档仍 blocked，工具不推断或补造旧主题。
- `--execute-paired-rebaseline` 配合 `--provider-contract-sha256` 显式约束本次 Provider 范围；摘要必须精确覆盖计划，拒绝缺项、多余项、重复项或只读时携带调用范围。该参数不是用户授权凭据。全部计划 case 预检通过后才允许执行，new request 额外页面/lane 会在调用前拒绝。
- 旧侧复用 `export_provider_image(binding=None)`；只接受现有 owner 可原样传输的 `model/prompt/n=1/size=auto` 合同。`historical-prompt:<archive digest>` 仅为传输 envelope 身份，不宣称旧链存在新 recipe/binding。实际执行 context 的 contract SHA/provider/model/mode 在调用前再核对。
- 新侧保留 `execute_replay_request → routes.generate → committed input/binding/scorecard` 链；image 导出另外强制 `verify_provider_export` 和真实 `provider-http`。双侧使用相同材料、主题、Provider contract 和当前共同物化 fingerprint。
- 旧侧首先不可覆盖地保存 execution-input；有 receipt 的重试只核验，不读取凭据、不重复调用；receipt 已完成但外层 execution 记录缺失时可恢复。只有 inflight 没有 receipt 的未知结果拒绝重发。输入、源码、环境、原始响应或产物变化均 fail closed。
- 修复历史桥原来的 contract 摘要口径：现在与实际 owner 一致，使用 contract 文件字节 SHA-256；U6 Provider 配对也使用相同口径，不能将对象 canonical digest 与实际文件 hash 混用。

已验证本地 HTTP 真实传输冻结旧 prompt、重试不重发、中断结果不重发、只读不创建输出、缺历史主题、未计划 lane、contract/theme 漂移与 CLI 范围拒绝。新侧实际调用生产 route，在缺 image 资格时记录真实 qualification refusal。合成缓存收据仅验证恢复与产物漂移拒绝，没有登记为业务证据；本地 HTTP 始终标为 local-protocol-test 并被重基线拒绝。

扩展回归：`PYTHONPATH=runtime/src runtime/.venv/bin/python -m unittest tests.test_quality_replay tests.test_quality_scorecard tests.test_visual_qa tests.test_visual_measure_rules tests.test_image_expression_adapter` 为 **111 tests / 93.100s / exit 0**，句柄 `37529` 最终 `OK`。随后仅补充 context 执行前漂移检查及对应负例，最终 focused 结果另列。没有外网/付费 Provider 调用，没有真实双侧 image、完整 R-85 或用户收益结果；U6/U12 不能据此 complete。主线负责后续完整有序验证与 CHANGELOG。

源码冻结后的最终 focused：`PYTHONPATH=runtime/src runtime/.venv/bin/python -m unittest tests.test_quality_replay.PairedImageRebaselineTests tests.test_quality_replay.HistoricalBridgeTests` 为 **15 tests / 38.046s / exit 0**，句柄 `67342` 最终 `OK`。最终 compileall 与两份 schema 检查均 exit 0。冻结 SHA-256：`quality_replay.py=af23ae1ac5b266192c5a0d1a190d43e68ea4804e970b45b8d88049589dc4f61d`；`run_quality_scorecard.py=03af83252969aa706585b18d5a77bedc5a63570d038775b1febac33c5b9f24d9`；`test_quality_replay.py=d848dc3f321a4361dad9a365b99d65d31ff1fe421d024b2c92f9d9bfebe07b90`。
