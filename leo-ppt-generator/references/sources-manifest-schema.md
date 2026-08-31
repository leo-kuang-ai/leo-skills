# Sources Manifest Schema（视觉来源清单，v1）

> 加载阶段：`execute` + Route=generate、进入 `image prepare` 冻结输入前读取；
> upgrade 路线在交付前聚合时读取。不得在入口 / Route 判断 / advise 阶段读取。

sources_manifest.json 是逐页视觉来源的**机器投影**：人确认的内容真值仍在母版
视觉行（见 `deck-master.md`）；本文件只把"这页每张图从哪来、什么等级、怎么处理"
落成可哈希、可 diff、可被交付门（`check_sources_manifest.py --strict`）复核的工件。
generate 路线写入 `<project-root>/content/sources-manifest.json`，由
`image prepare --sources <path>` 校验后冻结为 `<run>/input/sources-manifest.json`，
其自指纹并入 `prepare_fingerprint`。

## 顶层结构（v1）

```json
{
  "schema_version": 1,
  "manifest_kind": "visual-sources",
  "route": "generate",
  "run_ref": "runs/<run-id>",
  "generated_from": "content/deck-master-v3.md",
  "pages": [
    {
      "page_id": "slide_02",
      "visuals": [
        {
          "visual_id": "v1",
          "figure_id": "F3",
          "kind": "figure",
          "source_class": "user-material",
          "tier": "引用",
          "handling_mode": "preserve",
          "review_status": "vision-reviewed",
          "source_ref": "sources/paper/fig3.png",
          "source_sha256": "…",
          "backend": "user"
        },
        {
          "visual_id": "v2",
          "kind": "background",
          "source_class": "ai-generated",
          "tier": "示意",
          "handling_mode": null,
          "review_status": null,
          "source_ref": null,
          "source_sha256": null,
          "backend": "builtin-imagegen"
        }
      ]
    }
  ],
  "contents_sha256": "…"
}
```

`pages[]` 的 `page_id` 必须与 slide_jobs.json 页集合一致（每页至少一条 visual，
或显式 `visuals: []` 表示纯文字页）。

## 字段规则

- **`schema_version`**：固定 `1`。版本演进只增字段不删字段（追加 optional 字段不算
  breaking）。
- **`source_class`（封闭枚举）**：
  - `user-material`：用户素材原图；
  - `derived-crop`：用户素材裁剪派生（含 `user-approved-rasterization` 聚合）；
  - `ai-generated`：AI 生成；
  - `illustrative`：示意图 / 修辞图；
  - `native-rebuild`：对象级原生重建（仅 upgrade）；
  - `deterministic-render`：渲染 lane 产物（CI-1 前瞻预留）；
  - `deterministic-overlay`：TF-2 确定性贴字层（底图仍须来自确认 backend，
    见 image-deck-workflow.md 文字保真降级链）。
- **`tier` ∈ {`引用`, `估算`, `示意`}**：三级标注的**逐图投影**，不新增第四级。
  `unknown` 不入 manifest——入 manifest 前必须先走 A3 求证闭环（校验失败 →
  标 unknown 禁止入页 → 补真实素材或降级示意并确认 → 重验）。
- **`handling_mode` / `review_status`**：复用 `academic-figure-evidence.md` 的封闭
  枚举（6 种处理模式 / 5 级审查状态）；非图类 visual（背景/装饰）可为 `null`。
- **`backend`**：与 image record / imagegen-jobs 的 backend 词表同一来源；按 CI-1
  预留 `render:html` / `render:mermaid` / `render:echarts` 前缀，γ 扩展枚举时无需
  改本 schema。用户自带素材记 `user`。
- **`source_ref`**：本地文件用相对 `sources/` 或 run 冻结输入的 POSIX 路径；URL 用
  完整 https URL（A3 校验可达性）；`null` 仅允许
  `source_class ∈ {ai-generated, native-rebuild, deterministic-overlay}` 且
  `tier ∈ {示意, 估算}`。
- **`source_sha256`**：`source_ref` 指向本地文件时的 sha256（URL 可为 `null`）。

## contents_sha256（自指纹，canonical 键序）

```text
contents_sha256 = sha256( canonical_json( 去掉 contents_sha256 字段后的整个对象 ) )
canonical_json  = json.dumps(obj, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":"))
```

任何字段变更必然翻转指纹；键序 canonical 保证 diff 即语义 diff。γ 的五指纹收据
直接消费本字段（建议收据槽位名 `sources_manifest_sha256`），对本文件只读。

## 敏感纪律

manifest 全文（canonical 化后）按 `evidence.py` 同款正则扫描
（`api_key / access_token / password / authorization / bearer / secret`，大小写不敏感），
命中即 `sources_manifest_invalid`，禁止冻结与交付。

## 迁移注记（CI-3）

- `image prepare` **不带** `--sources` 时，`prepare_fingerprint` 保持旧算法
  `sha256(canonical_json(slides))` 逐字节不变——旧 run 恢复天然兼容；
  带 `--sources` 时为 `sha256(canonical_json({"slides": …, "sources_manifest": …}))`，
  jobs 状态中 `sources` 字段记 `{"path": "input/sources-manifest.json",
  "contents_sha256": …}`，无 sources 输入的旧 jobs 该键缺省（视为 `null`）。
- upgrade 路线的 deck 级 manifest 由页级 `manifest.json` 的 `asset_provenance` 与
  `imagegen-jobs.json` 聚合生成（`check_sources_manifest.py --compile <run>`），
  映射：`user-provided → user-material`；`asset-sheet-separated → derived-crop`；
  `imagegen → ai-generated`；`user-approved-rasterization → derived-crop`。

## 校验

交付前必须运行（在技能目录内执行）：

```sh
python3 scripts/check_sources_manifest.py <run 或 manifest 路径> --strict
```

退出码 0/1/2（CI-4）：0 通过；1 FAIL 阻断（schema/枚举/自指纹/敏感/strict 下引用级
不可回溯或 AI 图冒充引用）；2 WARN 可交付但须披露（低审查状态图、
`request-higher-resolution` 未闭环、URL 缓存过期）。FAIL 与 strict 下的 WARN 均阻止
交付（DELIVERY-GATE 维度，同 `check_deck_geometry.py`，不新增人在回路门）。

reason codes：`sources_manifest_missing` / `sources_manifest_invalid` /
`source_unverifiable`（见 `reason-codes.md`）。
