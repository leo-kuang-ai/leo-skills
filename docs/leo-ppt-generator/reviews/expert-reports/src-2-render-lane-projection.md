# 源码考古 SRC-2 · 渲染 lane 与 dashi 投影

- 对象：render lane / 模板 / 内容投影子系统 · 方法：全文通读+调用链追底（含 lint 实跑验证）
- 已完整读取：templates.py(1302)、content_projection.py、content_pack.py、layout_selection.py、layout_bank.py、template_inputs.py、style_validation.py、recommendation.py、render/{page,chart,fonts,assets,layout,theme,readiness,provenance,raster}.py、scripts/runtime_manager.py(1121)、lint_template_contract.py、lint_render_templates.py（实跑）、verify_html_deck_e2e.py、template-library/canonical/templates/ 全模板清单
- 日期：2026-09-11

## Q1 · render page/chart 实现完整度（实装完整）

**入口更正**：runtime_manager.py 不含 render 子命令（:1006-1032 仅 ensure/bootstrap/doctor 等）；真实入口 runtime CLI（cli.py:1541-1573 定义、2664-2732 执行）。

`render page` 执行路径（render/page.py:158-387）：模板定位（slug 或 builtin:template:<slug>，lane 必须 render:html，assets.py:60-93）→ 数据合同校验（template_inputs.py:77-110；chart_svg 过 SVG 消毒）→ **几何自动补齐**（--theme-file 无 geometry 且模板声明 layout_profiles 时自动 compile_geometry，page.py:193-204）→ playwright+chromium（缺→render_backend_missing；LEO_PPT_RENDER_CHROMIUM 可覆盖）→ 字体：本地 HTTP 仅 127.0.0.1（fonts.py:113），AssetResolver 离线解析缺失即 render_font_missing，document.fonts.load/check 任一失败整体拒绝（page.py:264-293）→ viewport 1280×720×dsf（scale 仅 1/2）→ init script 注入 __LEO_SLIDE_DATA__/__LEO_THEME_VARIABLES__（245-250）→ `?leo_render=1` networkidle（255-257）→ ready 主门 `html[data-leo-ready='1']`（45, 295-304；超时降级 fonts.ready+800ms 记 WARN）→ **溢出哨兵**：全部 data-leo-block/-item/-region 断言画幅内不溢出（54-80, 313-331；LEO_PPT_RENDER_OVERFLOW=warn 降级）→ PNG 头断言（114-121, 345-354：不符删产物抛 render_size_mismatch）→ sidecar `.render.json`（358-378：backend/template_id/template_sha256/data_sha256/renderer/out_sha256/width/height/ready_signal/overflow_check 等）。

`render chart --dialect mermaid`（render/chart.py:343-404，M1 仅 mermaid）：vendored mermaid.min.js（3.5MB 实存）同一 playwright 内渲染；**全部网络请求 abort**（236）；主题 8 键锚映射+治理区 chart-theme-mapping.json，映射不出即阻断不回落（175-183）；SVG 消毒（334-336）；--png 走 resvg。sidecar 额外带 chart_options/mermaid_source_sha256。

`image record --render-receipt` 消费（render/provenance.py）：kind/schema/backend 枚举校验（29,41-61）→ out_sha256 与 run 内 artifact 逐字节比对（64-77）→ 同锁并入 provenance+revision（80-114）。**注意：record --backend 缺省 "fixture"（cli.py:1485），须显式 --backend render:html**。

`render ready` 三态探测含 chromium 真实启动（readiness.py:214-257）。lint 实跑：lint_render_templates 15/15 OK；lint_template_contract 在无 jsonschema 解释器下报 schema validator unavailable（环境问题非违规）。

## Q2 · R-71 预览可行性

**选定后物化已实装且严格**：`materialize_html`（content_projection.py:459-524）slot_map→模板 data dict；不合格绑定拒绝；媒体缺即拒绝不留空图（505-510）。

**默认绑定现状**：`allocate_deck` 的 selection 即确定性默认绑定（有界搜索 20,000 预算，layout_selection.py:126-262），**但输出只带 layout_id+binding_digest，不携带绑定对象**（272-277）。**top2 语义与命名不符**：是合格池按 asset_id 序前二（278-280），非 _soft_rank 推荐前二（软排序只用于 search 内部 196-215）——拿它当推荐绑定需重跑 precompile_binding。未选定页可渲染性：**库层完全可行**（qualified_pool 产出完整 slot_map 绑定，任选一条即可 materialize）。

**批渲染入口距离**：verify_html_deck_e2e.py:86-199 已是全链路原型（compose_design 冻结→逐页 compile_geometry+theme→render_page→PPTX→收据），但 SLIDE_DATA 是手写 fixture 未接内容包。缺口五项：①编排 CLI 命令（render 只有单页 page）；②allocate_deck 绑定对象持久化；③`<run>/previews/` 目录约定（全代码无引用；receipt render_previews 类只盖 reports/final 的 render-preview，新目录不冲突）；④增量重渲集成；⑤U3 契约版本字段（PROJECTION_COMPILER="2" 在 content_projection.py:24，render sidecar 无此字段）。**复用面大**：模板解析/字体/尺寸断言/溢出哨兵/几何自动补齐全部白拿。

## Q3 · R-70b 组合页可行性

**机制可承载，零现成资产**：
- 输入字段类型支持 data-uri/image/media（content_projection.py:66；template_inputs.py:46-47）；frame-shot 是现成媒体模板（image_src type data-uri required）+ 双 lane 声明范式（renderer_support 同时含 render:html 与 image 构图文本）。
- layout 侧 slots.content_type:"media" 合同已在；fixed-regions layout_type 可表达"全幅背景 region+文字 regions"（render/layout.py:17）。
- **但 42 个 layout.json 只有 frame-shot 一个带媒体槽且是内容区单图框非背景层**；p22-image-hero/p36-ambience-full-bleed 是 image-lane-only。
- 合成管线缺口：现只有 TF-2 Pillow 贴字（overlay_text.py）；"render 文字层×图像背景层"合成器与**双 provenance 子记录 schema 不存在**（现 sidecar 单份）。
- design_digest 覆盖组合页无障碍（pages 全键原样入摘要，templates.py:1027-1034, 1114-1133）。主题换肤齐备（--leo-c-*/--leo-f-*/--leo-g-* 变量、对比度硬门 theme.py:161-194）。**溢出哨兵已是渲染期硬门**——组合页文字层天然获得"越界即拒产"。

## Q4 · content pack / stamp-page-ids / CAS 冻结

- U2 实装：compile_content_pack（content_pack.py:394-516）产出 schema v1；content_digest 自身排除规范化哈希（105-107）；page_id 三态（全有=稳定身份/全无=派生 slide_NN 仅定位/部分有=母版损坏 309-351）；数字登记表九列契约；结构标记（对照侧/表列/表行/单行结构数据 JSON）重复声明拒绝。
- U4 实装：propose_page_id_stamping 幂等一次性写入（542-583）；CLI content stamp-page-ids（cli.py:1536-1539, 2623-2634）。
- U4 CAS 冻结实装：image prepare --content-pack/--design/--layout-selection（cli.py:1454-1465）→ _freeze_content_binding（592-672）：纯 CAS（已存在 sha 不一致即冲突 544-558）+ digest 重验 + 页序三重核对（content_pack_page_mismatch 等）。

## Q5 · upgrade import-baseline

冻结（upgrade/baseline.py:152-237）：幂等；逐页产物+delivery PPTX durable_copy+sha 复核；linked_inputs（content_pack→input/page-content-pack.json、resolved_design→input/resolved-design.json）复制校验后随 manifest 发布；source_binding 七键结构（203-211）；失败整目录清理。恢复（54-98）：全链 sha 复核。**缺口**：linked_inputs 只校验无消费者（无再投影代码）；verify_design_freshness（templates.py:1206-1235，U8）只有 tests 消费未接 CLI。

## PRD 声明核对表（摘要）

| PRD 声明 | 裁定 | 证据 |
| --- | --- | --- |
| R-70 依赖"render lane 基建已备" | **确认** | render 全链实装；15 模板 lint OK |
| R-71"母版→全册预览编排 CLI" | **修正：CLI 不存在**，组件在库层+e2e 脚本 | cli.py:1547 仅单页；verify_html_deck_e2e.py |
| R-71"未选定页用候选默认绑定" | 库层可行、未接线（且 top2 语义有坑） | layout_selection.py:272-280 |
| R-71"U3 版本钉扎" | 未证实（sidecar 无 U3 字段） | page.py:358-378 |
| R-70b"组合页模板与合成管线" | **修正：机制可承载、资产与合成器为零** | 42 layouts 仅 frame-shot 有媒体槽 |
| R-70"手改文字层被指纹拒绝" | 部分确认（record 闸+overlay 双指纹+五类指纹链在） | cli.py:1492-1503；receipt.py |
| K4 source_binding 冻结恢复 | 冻结+校验确认；再投影消费未接线 | baseline.py:203-211 |

## 意外发现

1. **top2 语义与命名不符**（asset_id 序前二）——R-71/R-77 偏离率指标若用它会错；
2. **dashi 投影链最后一公里普遍未接线**：precompile_binding/allocate_deck/qualified_pool/materialize/projection_view/verify_design_freshness 全是"库函数+tests"，无 CLI/生产消费者——R-71 工程量在编排接线非新机制；
3. render page 自带几何自动补齐，预览编排成本再降；
4. record 消费 receipt 须显式 --backend render:html（缺省 fixture 会 invalid）；
5. ROLE_PAGE_TYPES 存在第 7 种 page_type "evidence"（content_projection.py:57），超出六值枚举——page_type_regime 扩枚举有先例；
6. frame-shot 模板 manifest notes 陈旧（称硬编码色，实际已 var(--leo-c-*)）；
7. lint_template_contract 需 jsonschema 环境（CI 注意）。
