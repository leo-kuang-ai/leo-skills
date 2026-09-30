# 表达质量回放

工具在任务根内读写证据，所有引用固定为 `{path, sha256}`，拒绝越界与符号链接。
新增计划必须满足 `runtime/src/leo_ppt_generator/schemas/quality-replay-v1.schema.json`。
JSON 摘要使用 `storage.canonical_json_bytes`；摘要字段自身不参与其摘要。
计划显式声明 `run_prefix`、`representatives` 和 `observations`。U6-A 的
`representatives` 必须为 `null`，执行固定数据集全集；U6-B 指定同时覆盖 HTML/image 的
代表 case ID，并使用独立 `run_prefix`。B 重核 A 的完整收据并继承 R-85 分母与改善结果，
不会把代表页检查写成整册逐页视觉通过。

```sh
PYTHONPATH=runtime/src runtime/.venv/bin/python scripts/run_quality_scorecard.py <任务根> --freeze-baseline <旧链描述.json>
PYTHONPATH=runtime/src runtime/.venv/bin/python scripts/run_quality_scorecard.py <任务根> --replay-plan <计划.json> --execute-replay --library-root <明确库根>
PYTHONPATH=runtime/src runtime/.venv/bin/python scripts/run_quality_scorecard.py <任务根> --replay-plan <计划.json>
```

第一条仅封存已经真实导出的旧链，输出 `qa/legacy-baseline.json`。描述包含源 revision、
源码字节全集、dirty hashes、执行环境、输入、旧 selection、PNG 和对应收据。
环境中的 renderer 源码摘要必须能由冻结文件重算；每张图须与真实模板及输入收据对应。
`capture_mode` 必须明确为修改前捕获或事后从历史字节重建，后者不能声称提前冻结。

环境指纹包含实际 image Provider 实现、`openai`/`httpx` SDK、renderer、adapter、
浏览器和字体。Provider 或渲染源码改变后，旧 receipt 不能继续作为同环境证据。
仅 oracle/OCR 观测器变化可以保留渲染可比性，比较结果仍记录双方 execution digest。

历史 image 可用 `legacy-image-export-v1` 封存桥，固定旧源 revision、源码、材料、
selection、冻结 prompt/request、Provider contract 和原始 HTTP receipt。它验证原图到
归一化 PNG 的字节与像素，不要求历史链本来不存在的新双层 binding，也不授予新生产资格。
缺原始请求/响应、冒用本地协议测试或将新 binding 填进历史记录均拒绝。

renderer 已变化时，可以准备并执行双侧重基线：

```sh
PYTHONPATH=runtime/src runtime/.venv/bin/python scripts/run_quality_scorecard.py <任务根> --prepare-paired-rebaseline <描述.json>
PYTHONPATH=runtime/src runtime/.venv/bin/python scripts/run_quality_scorecard.py <任务根> --paired-rebaseline-plan qa/paired-rebaseline-plan.json --execute-paired-rebaseline
PYTHONPATH=runtime/src runtime/.venv/bin/python scripts/run_quality_scorecard.py <任务根> --paired-rebaseline-plan qa/paired-rebaseline-plan.json
```

HTML 旧 `old_snapshot` 是 `root / files / source_roots` 描述；`source_roots` 明确指定
任务根内的历史 `builtin` 与可选 `user` 库根，逐资产校验相同历史路径及 identity/pin。
image 旧 `old_snapshot` 必须等于原 baseline 的 `legacy-image-export` receipt 引用；该归档
必须另有 `theme_source` 字节引用，并登记在原 `source_snapshot` 中，selection 的 `theme`
与其内容完全一致。没有原历史主题、prompt/request、HTTP 响应或 Provider contract 时保持 blocked。

只有已获该任务 Provider 调用授权时才执行 image；命令必须另外明确每个冻结 contract
**文件字节 SHA-256**（不是 JSON 对象 canonical digest）：

```sh
PYTHONPATH=runtime/src runtime/.venv/bin/python scripts/run_quality_scorecard.py <任务根> \
  --paired-rebaseline-plan qa/paired-rebaseline-plan.json --execute-paired-rebaseline \
  --provider-contract-sha256 <计划所引用contract文件的SHA256>
```

多份 contract 重复提供参数，须精确覆盖计划，不能带重复或多余项。此参数约束执行范围，
不代表工具替用户授予调用权限。仅核验不接受此参数且不调用 Provider。计划不得包含未列为
case 的新侧页面或 lane；双侧 Provider contract 与实际主题必须一致。当前历史传输适配只
支持与既有 export owner 相同的 `model/prompt/n=1/size=auto` 请求，其他历史请求保持 blocked，
不会静默丢字段或改参数。旧侧只使用固定 prompt，传输 envelope 不授予旧链新的 recipe 或 binding。
新侧继续走统一 generate 链。输出保留原始 HTTP 响应、Provider 原图、PNG 与原 receipt。
已有通过收据只核验；receipt 已落盘而外层记录未落盘时可恢复；inflight 但无 receipt 时拒绝重发。
任一侧失败不会自动重复另一次未知调用，输入、环境或产物漂移均拒绝通过。

描述保留原 baseline，并逐 case 指定旧 selection/冻结资产、新 `PipelineRequest`、材料、
lane 和两侧输出目录；准备过程计算执行 fingerprint，计划及源码封存不可覆盖。旧侧只能
用已核验的历史 template/data/theme 再渲染；新侧调用真实 route。验证重新读取双方产物、
来源、环境和 committed binding，不能通过手改 `passed` 放行。该收据只证明配对 runtime，
不会生成视觉评分或用户收益；本地 HTTP 协议测试不能成为真实 Provider 重基线证据。
原基线与 `reconstructed-historical` 身份始终保留；U6 引用重基线收据后仍执行全部 R-85
及视觉门，并核对新侧产物和 binding 未换页。正式自包含晋升包还必须携带执行库。

R-85 数据集的 `kind` 为 `r85-heldout`，固定 `owner`、`origin`、三个 families、十个 tasks
及逐 case 的 deck/page/lane、材料、请求和任务根内 run 路径。每个 case 的 `expected` 为
`solvable|unsolvable|insufficient`。30 格、至少 60 个独立页、6 册、每类至少 4 页均由记录
重算，双 lane 不重复计页，反例分母独立报告。`origin=fixture` 只能验证机制，不能签发发布通过。

真实运行仍调用 `application.routes.generate(PipelineRequest)`，不绕过资格或修改请求内容。
`--execute-replay` 会真实执行请求中的 lane；Provider 须已满足该任务的授权及配置范围。

## image 关系证据

先在技能根目录生成待调用输入；此命令不会访问 Provider：

```sh
PYTHONPATH=runtime/src runtime/.venv/bin/python scripts/probe_relation_capabilities.py \
  --library-root template-library \
  --cases evals/fixtures/expression-first-relation-probes.json \
  --prepare-image-inputs
```

输出包含当前环境及文件摘要、每个具备 recipe 的正反探针输入。没有 recipe 的
layout 保持 blocked；不能借用 HTML 模板或构图说明补足 image 资格。
获得对应调用授权后，使用 `export_provider_image` 保存原始 HTTP 响应、Provider
原图和固定留边的 PNG。URL-only 响应缺少下载传输证据时拒绝准入。

每张实际图片还需要 `raster-geometry-observation`：具名 reviewer、human/model
方法、具体观测说明、完整连线端点与方向、区域矩形及裁切标记。坐标统一为
1280×720 逻辑画布；图片、预期、oracle 和环境摘要必须对应。观测必须来自查看
该图片，不能从模板 DOM、输入 JSON 或正向 expected 复制。它不代替 U6-A 四维评分。

`--image-evidence <json>` 接收如下引用结构，所有路径均相对 library root：

```json
{
  "independent": {
    "positive": {
      "provider_receipt": {"path": "evidence/.../page.png.provider.json", "sha256": "实际文件摘要"},
      "raster_review": {"path": "evidence/.../geometry.json", "sha256": "实际文件摘要"}
    },
    "negative": {
      "provider_receipt": {"path": "evidence/.../page.png.provider.json", "sha256": "实际文件摘要"},
      "raster_review": {"path": "evidence/.../geometry.json", "sha256": "实际文件摘要"}
    }
  }
}
```

verifier 重新运行实际 PNG 的 Apple Vision OCR，并核对 recipe→请求→原图→PNG、
全部必需文字、事实和几何关系。当前本机检测依赖 macOS Vision revision 3 与
`swiftc`；缺依赖、低置信文字或缺观测均不能放行。原始观测及 Provider 附件进入
冻结 evidence closure；localhost 协议测试无法成为真实 Provider 证据。
缺裁决时先保留导出并标 `not_run`，不会替用户生成验收结论。
资格拒答也保存 `<run>/qa/replay-execution.json` 和日志，绑定请求、源码、库与环境。
复核会重新运行同一候选资格算法；修改 failure/status 后重签摘要不能伪造正确拒答。

逐页 review 必须引用当前图和基线图，包含裁决者、方法、理由、四维新旧评分、严重缺陷数与
可接受的完整 candidate identity digest。至少三册各 10–14 页满足四维阈值与两维改善，
旧链已达到 4 的维度不能退化；HTML 和 image 真实收据都缺一不可。

U6-B 还重核 U6-A 计划及证据、正式 cleanup→publish→verify→plan 收据链、代表页的双层 binding，
以及可定位用户差页；等价 fixture 必须附触发、关系、失败和验收四项同构说明。
convergence 必须引用 [五阶段迁移](template-library-migration.md) 产生的 cleanup 收据；
手写的 staging/delivery hash 字典不构成发布证据。
结论识别率、任务成功率和返工收益仍需真实用户观测，工具不会从视觉分数推断这些收益。
`observations` 引用成对的 before/after 观测与对应产物摘要；无观测或 fixture origin 为
`not_run`。工具计算识别率、成功率、返工率和差值，不能把机制测试中的数据当作用户收益。

结果写入 `qa/visual-replay.json`。退出码 `0` 表示该回放门通过，`1` 表示未通过或受阻，
`2` 表示 CLI/输入错误。scorecard 会重新读取计划和证据，不信任历史 `passed` 或手填汇总分数。
各 run 的 `qa/visual-replay.json` 只保存任务根和收据的显式引用；完整证据仍由任务根拥有。

能力晋升时，局部 `visual_review` 必须增加 `u6a` 引用，否则仅为
`provisional / u6a_required`。`u6a` 包含 `root`、`receipt` 和 `files`：
`root` 是库内 `evidence/replays/<name>` 的完整回放根；后两项分别是该根下
正式 A 收据的 `{path, sha256}` 和全部文件的同形引用数组。附件目录不得含链接、
遗漏文件或目录外依赖。应先在固定回放根建立独立库快照和运行记录，再冻结文件清单；
改变路径或字节后必须重验，不能移动后沿用旧摘要。

`verify_capability_publication` 重新运行 A 的全部验证，再核对通过页的 layout、
relation、lane 和原正反探针证据。晋升不改变旧回放中已冻结的 provisional 输入；
相互引用或自证循环被拒绝。`evidence_closure` 将完整附件纳入生产冻结输入。
缺真实 image、留出集、旧链基线或配对评分时，该门仍不能通过。
