# 版式：P25 · Spec Table · 规格参数表

**分类:** canonical/layouts

**用途:** 多行多列参数/规格/BOM 表——密集结构化文本的唯一合法容器。

**适用内容类型:** ≥3 行 × ≥2 列的参数表（行列表头 schema 必填）。**行数 > 8 → 强制 direct-editable 原生表格**（图片模型密集文本错误率高，见 page-decision-tree）。<3 行 → P19 四卡。

**骨架:** 表头行（角色区分底色）+ 斑马纹数据行 + 单位列右对齐；最小字号 24px（2560 画布）；列宽按内容类型分配（参数名 30% / 值 45% / 备注 25%）。

**关键类:** `.spec-table` `.spec-head`

**动效 recipe:** 无（表格页禁动效，保扫读）。

> 超限行数走 editable 是质量门判据，不是建议。

## 机读比对合同（密集表格页必跑）

行数 ≥12 的 P25 页：agent 从母版数字登记表派生**期望值清单**
（`value/unit/page/container` JSON），`image record` 后取该页 OCR 回读文本
（PaddleOCR hints 或人工导出），运行
`python3 scripts/check_table_values.py expected.json ocr_dir/`——任一期望值
未命中即打回该页；单位缺失列 P3 级处置。
