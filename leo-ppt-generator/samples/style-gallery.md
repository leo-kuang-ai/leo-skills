# 风格画廊（生成物）

> 由 `python3 scripts/generate_style_gallery.py` 从 `references/styles/` 文件系统确定性生成；
> 手工编辑会被 `--check` 判漂移。完整索引与选风格路由见
> [`references/styles/00_索引/_INDEX.md`](../references/styles/00_索引/_INDEX.md)。

## 内置风格（11 套，直接可选）

| 风格 | 适用场景（摘自 brief） |
| --- | --- |
| **党政红风格** | 党政机关工作汇报、专题学习与会议材料 / 政策宣讲、党建活动、年度总结与重点工作部署 / 国企、事业单位和公共服务机构的正式汇报 |
| **创意杂志风** | 创意提案 / 品牌展示 / 设计作品集 / 文化活动 |
| **复古扁平插画风** | 文化创意项目展示 / 品牌故事讲述 / 旅游景点介绍 / 复古产品发布 |
| **手绘技术解释风** | 中文技术文章配图 / 技术概念解释 / 课程课件 / 知识卡片 |
| **手绘白板风** | 教学讲解 / 培训课程 / 头脑风暴 / 概念说明 |
| **教学课件风** | 高校课程、专题讲座与课堂教学 / 技术培训、知识科普与专业能力建设 / 概念讲解、体系梳理、案例分析与研究进展介绍 / 需要同时呈现文字、图解、图片和数据的教学型演示 |
| **数据仪表盘风** | 数据分析报告 / 业绩展示 / KPI 汇报 / 实时数据展示 |
| **清爽专业风** | 毕业答辩 / 工作总结 / 工作 review / 技术分享 |
| **温暖手工风** | 儿童教育 / 文化活动 / 手工艺展示 / 温馨主题 |
| **电子墨水杂志风** | 线下分享 / 行业内部讲话 / AI / 科技产品发布 / Demo day / 个人观点型演讲 / 非虚构叙事 / 强节奏主题演讲 / 户外 / 生活方式 / 人文题材 / 文化叙事 |
| **科研答辩风** | 科研项目申报答辩 / 基金申请与重点专项汇报 / 中期检查与结题验收 / 论文开题、预答辩和毕业答辩 |

## 内置风格金样板（R-26 / R-65）

> 每风格三页（封面 / 内容 / 图表），M1 渲染 lane 固定示例数据确定性生成：
> `python3 scripts/generate_style_gallery.py --render-golden` 重建，
> `--check` 以 sha256 对比金样板防漂移（编译回归判据）。

### 党政红风格

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![党政红风格 封面金样板](style-gallery/党政红风格/thumb-cover.png) | ![党政红风格 内容金样板](style-gallery/党政红风格/thumb-content.png) | ![党政红风格 图表金样板](style-gallery/党政红风格/thumb-chart.png) |

### 创意杂志风

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![创意杂志风 封面金样板](style-gallery/创意杂志风/thumb-cover.png) | ![创意杂志风 内容金样板](style-gallery/创意杂志风/thumb-content.png) | ![创意杂志风 图表金样板](style-gallery/创意杂志风/thumb-chart.png) |

### 复古扁平插画风

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![复古扁平插画风 封面金样板](style-gallery/复古扁平插画风/thumb-cover.png) | ![复古扁平插画风 内容金样板](style-gallery/复古扁平插画风/thumb-content.png) | ![复古扁平插画风 图表金样板](style-gallery/复古扁平插画风/thumb-chart.png) |

### 手绘技术解释风

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![手绘技术解释风 封面金样板](style-gallery/手绘技术解释风/thumb-cover.png) | ![手绘技术解释风 内容金样板](style-gallery/手绘技术解释风/thumb-content.png) | ![手绘技术解释风 图表金样板](style-gallery/手绘技术解释风/thumb-chart.png) |

### 手绘白板风

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![手绘白板风 封面金样板](style-gallery/手绘白板风/thumb-cover.png) | ![手绘白板风 内容金样板](style-gallery/手绘白板风/thumb-content.png) | ![手绘白板风 图表金样板](style-gallery/手绘白板风/thumb-chart.png) |

### 教学课件风

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![教学课件风 封面金样板](style-gallery/教学课件风/thumb-cover.png) | ![教学课件风 内容金样板](style-gallery/教学课件风/thumb-content.png) | ![教学课件风 图表金样板](style-gallery/教学课件风/thumb-chart.png) |

### 数据仪表盘风

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![数据仪表盘风 封面金样板](style-gallery/数据仪表盘风/thumb-cover.png) | ![数据仪表盘风 内容金样板](style-gallery/数据仪表盘风/thumb-content.png) | ![数据仪表盘风 图表金样板](style-gallery/数据仪表盘风/thumb-chart.png) |

### 清爽专业风

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![清爽专业风 封面金样板](style-gallery/清爽专业风/thumb-cover.png) | ![清爽专业风 内容金样板](style-gallery/清爽专业风/thumb-content.png) | ![清爽专业风 图表金样板](style-gallery/清爽专业风/thumb-chart.png) |

### 温暖手工风

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![温暖手工风 封面金样板](style-gallery/温暖手工风/thumb-cover.png) | ![温暖手工风 内容金样板](style-gallery/温暖手工风/thumb-content.png) | ![温暖手工风 图表金样板](style-gallery/温暖手工风/thumb-chart.png) |

### 电子墨水杂志风

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![电子墨水杂志风 封面金样板](style-gallery/电子墨水杂志风/thumb-cover.png) | ![电子墨水杂志风 内容金样板](style-gallery/电子墨水杂志风/thumb-content.png) | ![电子墨水杂志风 图表金样板](style-gallery/电子墨水杂志风/thumb-chart.png) |

### 科研答辩风

| 封面 | 内容 | 图表 |
| --- | --- | --- |
| ![科研答辩风 封面金样板](style-gallery/科研答辩风/thumb-cover.png) | ![科研答辩风 内容金样板](style-gallery/科研答辩风/thumb-content.png) | ![科研答辩风 图表金样板](style-gallery/科研答辩风/thumb-chart.png) |

## 新家族代表金样板（S5 进货 · R-65）

> S5 进货的 8 个新风格家族各选 1 个代表
> （色板最完整 / 最具家族气质），与内置风格同一渲染 lane 与
> `--check` 回归；暗底家族经可见性守护回退纸色底，
> 色板锚点仍逐字进图表 SVG。

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

## 参考轴（16 轴，markdown 份数）

| 轴 | 份数 |
| --- | --- |
| 通用母版（01） | 0 |
| 行业内容域（02） | 0 |
| 场景用途结构（03） | 0 |
| 来源_guizang（04） | 1 |
| 来源_awesome-gpt-image-2（05） | 0 |
| 论证模式（06） | 7 |
| 信息图类型（07） | 11 |
| 图片渲染（08） | 43 |
| 结构布局（09） | 8 |
| 品牌身份（10） | 36 |
| 图表语法（11） | 18 |
| 版式库（12） | 39 |
| 页面语义（13） | 25 |
| 参考池_gpt-image2（14） | 15 |
| 来源_officecli（15） | 7 |
| 来源_slides-grab（16） | 0 |

合计 markdown 风格/规范文档 221 份（不含 JSON sidecar 与 00_索引规则文档）。
选定后由 `style render` 确定性注入，流程见 [`references/style-library.md`](../references/style-library.md)。
