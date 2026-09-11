# 风格画廊（生成物）

> 由 `python3 scripts/generate_style_gallery.py` 从 `template-library/catalog/current.json` 指向的 canonical catalog 确定性生成；
> 手工编辑会被 `--check` 判漂移。执行期身份索引见
> [`template-library/catalog/current.json`](../template-library/catalog/current.json) 与其 generation 下的 `registry.json`。

## 内置风格（10 套，直接可选）

| 风格 | 适用场景（摘自 brief） |
| --- | --- |
| **医疗洁净风** | 浅底蓝绿 + 大字号少装饰的洁净排印；层级/时间线/KPI 的临床信息秩序 |
| **咨询金字塔风** | 浅暖底 + 分组线 + 严格脚注层级的咨询语法；结论先行标题行（action title） |
| **品牌创意风** | 真实素材满版 + 可控纸感/贴纸设计语言；大图 + 引语 + 叙事卡的品牌叙事节奏 |
| **学术克制风** | 黑白或近单色 + 规范中西文排印的学术版面；图表/公式/引用的编号纪律 |
| **政务庄重风** | 庄重对称版式 + 规范中文排印；红金克制配色（红为主、金仅点缀） |
| **教育明快风** | 清晰明度节奏 + 图文共讲的认知负荷控制；教学顺序（目标→讲解→练习）结构化 |
| **清爽专业风** | 毕业答辩 / 工作总结 / 技术分享 / 项目复盘 |
| **科技暗色风** | 暗底受控强调色 + 等宽字体点缀的系统图示；系统拓扑/回路/时间线结构优先 |
| **管理清晰风** | 中性冷灰底 + 石板蓝主色的克制层级；决策摘要置顶 + KPI 横栏 + 风险对照的固定节奏 |
| **金融藏青风** | 藏青主色 + 细网格线的可核验排印；数字右对齐 + 制表数字字体的表格纪律 |

## 内置风格金样板（R-26 / R-65）

> 每风格三页（封面 / 内容 / 图表），M1 渲染 lane 固定示例数据确定性生成：
> `python3 scripts/generate_style_gallery.py --render-golden` 重建，
> `--check` 以 sha256 对比金样板防漂移（编译回归判据）。
> 页面与图表共同消费 canonical theme；哈希一致仅证明可重复，不代表设计质量通过。

### 医疗洁净风

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![医疗洁净风 封面金样板](style-gallery/医疗洁净风/thumb-cover.png) | ![医疗洁净风 内容金样板](style-gallery/医疗洁净风/thumb-content.png) | ![医疗洁净风 图表金样板](style-gallery/医疗洁净风/thumb-chart.png) |

### 咨询金字塔风

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![咨询金字塔风 封面金样板](style-gallery/咨询金字塔风/thumb-cover.png) | ![咨询金字塔风 内容金样板](style-gallery/咨询金字塔风/thumb-content.png) | ![咨询金字塔风 图表金样板](style-gallery/咨询金字塔风/thumb-chart.png) |

### 品牌创意风

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![品牌创意风 封面金样板](style-gallery/品牌创意风/thumb-cover.png) | ![品牌创意风 内容金样板](style-gallery/品牌创意风/thumb-content.png) | ![品牌创意风 图表金样板](style-gallery/品牌创意风/thumb-chart.png) |

### 学术克制风

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![学术克制风 封面金样板](style-gallery/学术克制风/thumb-cover.png) | ![学术克制风 内容金样板](style-gallery/学术克制风/thumb-content.png) | ![学术克制风 图表金样板](style-gallery/学术克制风/thumb-chart.png) |

### 政务庄重风

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![政务庄重风 封面金样板](style-gallery/政务庄重风/thumb-cover.png) | ![政务庄重风 内容金样板](style-gallery/政务庄重风/thumb-content.png) | ![政务庄重风 图表金样板](style-gallery/政务庄重风/thumb-chart.png) |

### 教育明快风

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![教育明快风 封面金样板](style-gallery/教育明快风/thumb-cover.png) | ![教育明快风 内容金样板](style-gallery/教育明快风/thumb-content.png) | ![教育明快风 图表金样板](style-gallery/教育明快风/thumb-chart.png) |

### 清爽专业风

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![清爽专业风 封面金样板](style-gallery/清爽专业风/thumb-cover.png) | ![清爽专业风 内容金样板](style-gallery/清爽专业风/thumb-content.png) | ![清爽专业风 图表金样板](style-gallery/清爽专业风/thumb-chart.png) |

### 科技暗色风

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![科技暗色风 封面金样板](style-gallery/科技暗色风/thumb-cover.png) | ![科技暗色风 内容金样板](style-gallery/科技暗色风/thumb-content.png) | ![科技暗色风 图表金样板](style-gallery/科技暗色风/thumb-chart.png) |

### 管理清晰风

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![管理清晰风 封面金样板](style-gallery/管理清晰风/thumb-cover.png) | ![管理清晰风 内容金样板](style-gallery/管理清晰风/thumb-content.png) | ![管理清晰风 图表金样板](style-gallery/管理清晰风/thumb-chart.png) |

### 金融藏青风

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![金融藏青风 封面金样板](style-gallery/金融藏青风/thumb-cover.png) | ![金融藏青风 内容金样板](style-gallery/金融藏青风/thumb-content.png) | ![金融藏青风 图表金样板](style-gallery/金融藏青风/thumb-chart.png) |

## 新家族代表金样板（S5 进货 · R-65）

> S5 进货的 8 个新风格家族各选 1 个代表
> （色板最完整 / 最具家族气质），与内置风格同一渲染 lane 与
> `--check` 回归；暗底家族经可见性守护回退纸色底，
> 色板锚点仍逐字进图表 SVG。
> 这些历史家族尚无 canonical theme 绑定，兼容预览不能作为完整换肤或审美验收证据。

### 终端配色 · Dracula紫风

> 知名终端配色方案直迁，暗底霓虹前景的开发者视觉方言

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![Dracula紫风 封面金样板](style-gallery/Dracula紫风/thumb-cover.png) | ![Dracula紫风 内容金样板](style-gallery/Dracula紫风/thumb-content.png) | ![Dracula紫风 图表金样板](style-gallery/Dracula紫风/thumb-chart.png) |

### 设计流派 · 杂志衬线风

> 杂志、播报、撞色等设计史流派的编辑排版语汇

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![杂志衬线风 封面金样板](style-gallery/杂志衬线风/thumb-cover.png) | ![杂志衬线风 内容金样板](style-gallery/杂志衬线风/thumb-content.png) | ![杂志衬线风 图表金样板](style-gallery/杂志衬线风/thumb-chart.png) |

### 东方意蕴 · 故宫墨红风

> 墨红、水墨、宋韵等新中式东方诗意的十种色温

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![故宫墨红风 封面金样板](style-gallery/故宫墨红风/thumb-cover.png) | ![故宫墨红风 内容金样板](style-gallery/故宫墨红风/thumb-content.png) | ![故宫墨红风 图表金样板](style-gallery/故宫墨红风/thumb-chart.png) |

### 柔和治愈 · 奶油温柔风

> 奶油白、豆沙粉、抹茶绿的低饱和温柔色系

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![奶油温柔风 封面金样板](style-gallery/奶油温柔风/thumb-cover.png) | ![奶油温柔风 内容金样板](style-gallery/奶油温柔风/thumb-content.png) | ![奶油温柔风 图表金样板](style-gallery/奶油温柔风/thumb-chart.png) |

### 夜空氛围 · 星火夜空风

> 星河、极光、烟火的深底高对比夜空舞台

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![星火夜空风 封面金样板](style-gallery/星火夜空风/thumb-cover.png) | ![星火夜空风 内容金样板](style-gallery/星火夜空风/thumb-content.png) | ![星火夜空风 图表金样板](style-gallery/星火夜空风/thumb-chart.png) |

### 质感专业 · 黑金期刊风

> 黑金、勃艮第、象牙的期刊级质感与单金锚克制

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![黑金期刊风 封面金样板](style-gallery/黑金期刊风/thumb-cover.png) | ![黑金期刊风 内容金样板](style-gallery/黑金期刊风/thumb-content.png) | ![黑金期刊风 图表金样板](style-gallery/黑金期刊风/thumb-chart.png) |

### 中式载体 · 中式书卷风

> 书卷、宣纸、竹简的古典载体与朱红钤印

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![中式书卷风 封面金样板](style-gallery/中式书卷风/thumb-cover.png) | ![中式书卷风 内容金样板](style-gallery/中式书卷风/thumb-content.png) | ![中式书卷风 图表金样板](style-gallery/中式书卷风/thumb-chart.png) |

### 印象派油画 · 星月夜风

> 梵高、莫奈的笔触、光影与强色彩张力

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![星月夜风 封面金样板](style-gallery/星月夜风/thumb-cover.png) | ![星月夜风 内容金样板](style-gallery/星月夜风/thumb-content.png) | ![星月夜风 图表金样板](style-gallery/星月夜风/thumb-chart.png) |

## 结构轴目录（6 个分组，catalog 口径）

| 轴 | 份数 |
| --- | --- |
| argument（axis） | 19 |
| chart（axis） | 18 |
| infographic（axis） | 11 |
| page-semantics（axis） | 25 |
| rendering（axis） | 43 |
| structure（axis） | 8 |

上述结构轴与 active 内置风格共 134 项；draft 风格和治理参考资产不计入直接可选区。
全库实体数量以 catalog generation 的 `registry.json` 为准，不以画廊条目数代替可执行资格。
选定后由 `style render` 确定性注入，流程见 [`references/style-library.md`](../references/style-library.md)。
