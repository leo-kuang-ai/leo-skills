# 评审报告 R2 · 渲染投影域（源码复核）

- 对象：PRD v1.4 渲染 lane/投影域声明（R-70/R-71/R-77 top2）· 方法：源码全文通读＋42 个 layout.json 程序化扫描＋实测数据取证
- 通读：render/ 全目录 13 文件、content_projection.py、layout_selection.py、content_pack.py、templates.py、verify_html_deck_e2e.py、overlay_text.py、frame-shot/body-basic/compare 模板与版式
- 日期：2026-09-11

## 断言验证（摘要）

**15 项声明全部核实，无一错报**：render 仅单页命令✓；投影链零生产消费者（rg 验证 allocate_deck/qualified_pool 在 scripts/evals 零引用，仅 tests 消费）✓；previews/ 与五类指纹零冲突✓；自动几何补齐/溢出哨兵 enforce✓；42 版式仅 frame-shot 含 media 槽（内容图框非背景层，含图版式 render:html 均 null）✓；合成器不存在（render 截图不透明底＋无层合成代码＋overlay_text 是直绘非叠层）✓；双 provenance 单份覆盖式✓；--backend render:html 强制✓；frame-shot 双 lane 范式✓；top2＝asset_id 序前二（_soft_rank 只服务整册搜索）✓；15 模板计数✓。

## 需求级判断（摘要）

1. **R-71 五项缺口漏一硬项——批量渲染性能路径**：render_page 每页"新起 HTTP 字体服务→chromium launch→单页→close/shutdown"，无复用/并发/重试；实测 html-deck-e2e sidecar render_ms 1264–1295ms/页（含启动），40 页顺序≈51s，叠加 40 页×42 候选 precompile_binding 资格检查后 ≤60s 无余量。浏览器/字体服务跨页复用（或并发）是约百行量级新组件。→ 补第六项缺口；spike 前置开工门。
2. **R-70a 基本成立但漏三个 S 级小改**：overlay 字体走系统候选不接离线字体（跨机器不一致）；单行超宽即拒无换行；颜色默认 #111111 不消费 effective_theme/对比度硬门——不补则盲评在字体不一致上无谓失分。
3. **top2 修复**：PRD 方向正确且两项互补；**更小修复**＝allocate_deck 内对 qualified 用 _soft_rank 排序取前二（10–25 行）；实施陷阱：no_candidates 早退先于 profiles 构建、_selection_result 签名不携带 profiles、top2 应排除整册上下文惩罚项。**R-71 缺省绑定同病**——qualified_pool 序也是 asset_id 序，须与 top2 修复共用排序函数。
4. 正面核验：合成页经 record 落 origin_image 即进指纹链（天然兼容）；预览 1280x720（scale=1）合法可作提速备选。

## Findings

R2-1 [高] 批量渲染性能路径缺失（≤60s 无余量）；R2-2 [中] R-71 缺省绑定与 top2 同病；R2-3 [中] R-70a 漏 overlay 主题化三小改；R2-4 [低] layout_selection docstring 自称"推荐摘要"与实现脱节（漂移清单第六例）；R2-5 [低] top2 修复实施陷阱登记。

## 结论

**有条件通过**——源码级声明无一错报；条件：R-71 补第六项缺口＋spike 前置（波 1 排序 2 最大进度风险）；R-71 缺省绑定口径与 R-70a 主题化小改显式入范围。
