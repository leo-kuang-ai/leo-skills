# 上游补丁目录

固定上游当前应用八个可由 `git apply --check` 复核的受控补丁：

- `0001-codex-state-directory-barrier.patch`：状态文件替换后同步父目录；包内暂无
  可执行聚焦回归，proof 在上游开发仓。
- `0002-editable-state-atomic-lock.patch`：editable 状态写入原子化并增加并发锁，聚焦
  回归为 `tests/boundary/test_vendor_state.py`。
- `0003-codex-assembly-fidelity.patch`：图片组装默认无损并以 `contain` 保持比例，同时
  保留显式 `crop/stretch`，聚焦回归为
  `test_image_deck_assembly_preserves_source_ratio_by_default`（开发仓）。
- `0004-editable-expected-formula-inventory.patch`：拒绝已确认公式在 worker 输出中静默
  遗漏，聚焦回归为 `test_confirmed_source_formula_inventory_cannot_be_omitted`。
- `0005-codex-chroma-key-dependency-hint.patch`：保证 Pillow 缺失时返回适用于当前
  受管 runtime 的可执行恢复提示，不再引用旧 codex-ppt bootstrap 路径；聚焦回归为
  `test_chroma_key_dependency_hint_is_available`（开发仓）。
- `0006-editable-ppt-dpi-parameter.patch`：`.ppt` 经 Office 转 PDF 后使用
  `normalize_inputs(..., dpi=...)` 的函数参数，聚焦回归为
  `test_legacy_ppt_normalization_forwards_requested_dpi`。
- `0007-codex-required-text-and-style-lock.patch`：`_build_prompt` 渲染 leo C1 合同的
  两个独立 prompt 块——deck 级 `style_lock` 经 `_format_block("Deck Style Lock")`
  逐字复用，每页 `required_text[]` 渲染为 `## Required Text Only` 白名单块（逐字，
  禁块外内容性文字）；聚焦回归为
  `tests/boundary/test_prompt_block_regression.py`（包内可执行），静默丢失检出为
  `scripts/check_sources_manifest.py --check-job-prompts`。
- `0008-codex-openai-compatible-url-fallback.patch`：通用 provider 适配器的
  `generate` / `edit` / `generate_batch` 统一经 `_image_payload` 取图——优先
  `b64_json`，缺失时按响应 `url` 下载转 base64，两者皆缺时清晰报错；解锁只回
  临时 URL 的 OpenAI 兼容渠道（目录渠道见
  `runtime/src/leo_ppt_generator/config/providers.yaml`）；聚焦回归为
  `tests/test_channel_catalog.py::test_image_payload_prefers_b64_and_downloads_url`。

- `0009-codex-channel-model-execution.patch`：生成/编辑/batch 三处 payload 的
  `quality` 仅对 gpt-image 家族发送（渠道模型如 cogview-4 拒收该参数，
  zhipu 400 code 1214 基线证据）；`_validate_model` 放宽为非空模型名——渠道
  合同模型（doubao-seedream-* 等）与 gpt-image 家族同等合法，gpt-image 专属
  选项校验仍由 `_validate_model_specific_options` 条件承担；`_validate_size`
  对非 gpt-image-2 模型接受 `WIDTHxHEIGHT` 渠道尺寸档（服务端终裁）。聚焦
  回归为 `tests/test_channel_catalog.py` 渠道模型执行面用例与
  `tests/test_vendored_image_gen_params.py`。
- `0010-codex-assembly-progress-stderr.patch`：组装进度输出（✓ 已添加第 N 页/
  压缩日志）统一改走 stderr——`image assemble` 首装时不再污染
  `leo-ppt-machine/v1` envelope 的 stdout 单 JSON 约定。聚焦回归为
  `tests/test_assemble_envelope_purity.py`。

Office 输入信任边界属于当前项目 adapter/route 增强，单独记录为
`assembly-and-office-boundaries.md`，不伪装成 upstream patch。每个补丁在本文件内
登记；对 pinned 上游 worktree 的枚举重放检查在开发仓执行，本包内
暂无对应自动化。相应行为 proof 由上述聚焦测试约束。

禁止直接修改 vendor 副本后不生成补丁文件。
