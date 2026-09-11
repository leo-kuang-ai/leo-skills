# references 导航索引

> **本文件是只读导航图，不是加载合同。** 各 reference 的权威加载时机与顺序以
> `SKILL.md`「按需读取规则」表为唯一真值；本索引只按功能分组、给一句定位，方便
> 维护者与 Agent 快速定位，**不重复也不覆盖** SKILL.md 的读取纪律。风格实体的
> 执行期身份索引是 [`template-library/catalog/current.json`](../template-library/catalog/current.json)
> 指向的 generation `registry.json`；风格轴与治理规则见
> [`template-library/governance/authoring/index/_INDEX.md`](../template-library/governance/authoring/index/_INDEX.md)。
>
> 顶层共 31 份 reference（`.md`）。「加载阶段」为概述，精确条件见
> 各文件头部与 SKILL.md。

## ① 路由与恢复（入口）

| 文件 | 定位 | 加载阶段（概述） |
|---|---|---|
| [input-routing.md](input-routing.md) | 输入 → 四条 Route 的判断，只选有限 route 不接受注入步骤 | execute + Route 判断（advise 不读） |
| [reason-codes.md](reason-codes.md) | reason code 含义 / 可恢复性 / 动作对照表 | 已有 reason code 需解释或恢复时 |

## ② 首次准备 / 跨 Route runtime 与合同

| 文件 | 定位 | 加载阶段（概述） |
|---|---|---|
| [first-use.md](first-use.md) | launcher / setup / Provider 首次准备 | execute + Route 冻结后 |
| [backend-selection.md](backend-selection.md) | 图片 backend（generate/edit/mask/参考图）声明与选择 | 首次准备与 Provider 状态 / generate 执行 |
| [provider-catalog.md](provider-catalog.md) | 图片渠道目录（15 家：OpenAI 兼容 + Gemini/MiniMax/Ideogram 原生协议；官网/取 key/环境变量/模型/新增渠道指引） | 渠道 provider 配置或新增渠道时 |
| [execution-contract.md](execution-contract.md) | 跨 Route 的 runtime / 状态 / 恢复 / 交付合同 | 进入对应 Route 后 |
| [cli-helper.md](cli-helper.md) | 对象级可编辑能力的 CLI 命令手册 | 跨 Route CLI 用法（进入 Route 后） |

## ③ generate 主线工作流

| 文件 | 定位 | 加载阶段（概述） |
|---|---|---|
| [image-deck-workflow.md](image-deck-workflow.md) | 图片式主工作流（12 步） | execute + generate 执行 |
| [deck-master.md](deck-master.md) | 逐页母版（内容层唯一真值工件） | generate 执行 |
| [style-recommendation.md](style-recommendation.md) | 模版推荐与用户选择执行合同（工作流步骤 4） | generate 执行 |
| [visual-qa.md](visual-qa.md) | 视觉质检（五层非补偿门的「视觉呈现」层） | generate 执行 / 高保障档多轮审查 |
| [render-contract.md](render-contract.md) | 确定性渲染 lane（图表 / 表格 / 文字密集页） | generate 命中数据图表/表格/文字密集页 |
| [layout-dispatch.md](layout-dispatch.md) | 版式 P 码确定性打分调度与容量预检 | 逐页版式匹配进母版前 |
| [image-text-composition.md](image-text-composition.md) | 全出血封面 / 大图井「文字压图」四步构图协议 | generate 全出血封面/大图井页 |
| [rst-paging.md](rst-paging.md) | 大纲 RST 分页启发式（advisory，8 关系） | generate 大纲制作且材料多段/结构复杂 |

## ④ direct-editable / upgrade 工作流

| 文件 | 定位 | 加载阶段（概述） |
|---|---|---|
| [editable-workflow.md](editable-workflow.md) | 对象级可编辑重建工作流 | direct-editable 执行 |
| [manifest-schema.md](manifest-schema.md) | editable run/page JSON 字段合同与 owner | direct-editable 执行 |
| [page-decision-tree.md](page-decision-tree.md) | 逐页重建决策树 | direct-editable 执行 |

> `upgrade-full` / `upgrade-selected` 复用以上 editable references，另加当前 baseline/selection 证据。

## ⑤ 风格资产（template-library 桥接）

| 文件 | 定位 | 加载阶段（概述） |
|---|---|---|
| [style-library.md](style-library.md) | 风格库入口（current 指针 → generation registry；选定后才加载实体） | 确认视觉方向前 |
| [模板目录指针](../template-library/catalog/current.json) | 当前 generation 的唯一指针；由 registry builder 发布 | 执行期索引检查 |
| [模板库治理入口](../template-library/governance/authoring/index/_INDEX.md) | 六轴词表、设计体系与扩展治理规则 | 维护/治理查询 |
| [style-continuity.md](style-continuity.md) | 跨页风格继承与原图嵌入合同 | 样张确认后、批量派发前 |
| [style-presets.md](style-presets.md) | 场景预组合预设（R-67，可选档，默认关） | 启用预设时 |
| [style-candidates.md](style-candidates.md) | 进货批「不入库」候补登记表（**治理台账，非生成路径 reference**） | 进货复盘 / 治理 |

## ⑥ 素材 / 数据 / 来源

| 文件 | 定位 | 加载阶段（概述） |
|---|---|---|
| [library-schema.md](library-schema.md) | 用户素材库 schema（`library/`，R-04） | execute 内明确入库/检索素材 |
| [data-sources.md](data-sources.md) | 市场 / 行业数据通道登记（R-05） | execute 内明确要求市场/行业数据 |
| [sources-manifest-schema.md](sources-manifest-schema.md) | 视觉来源清单 schema（v1） | image prepare --sources 冻结前与交付前 strict |

## ⑦ 学术垂类

| 文件 | 定位 | 加载阶段（概述） |
|---|---|---|
| [academic-vertical.md](academic-vertical.md) | 学术模式一条龙映射与命名入口 | generate 且合同含学术信号 / 用户声明「学术模式」 |
| [academic-figure-evidence.md](academic-figure-evidence.md) | 学术图表证据规则 | generate 进入母版制作且材料含图证据/学术场景 |

## ⑧ 内容 / 叙事资产与输出形态

| 文件 | 定位 | 加载阶段（概述） |
|---|---|---|
| [deck-templates.md](deck-templates.md) | 周期性 deck 结构资产复用 + 数据点指纹 diff（R-50） | 周报/月报等结构复用时 |
| [deck-distillation.md](deck-distillation.md) | 可信标杆 deck 蒸馏为可点名风格资产（R-54，Gate 0 信任先行） | 用户提供可信标杆 deck 时 |
| [marketing-deck-narrative.md](marketing-deck-narrative.md) | 营销 / 销售 / 融资路演内容层叙事参考 | generate 营销/销售/路演类内容 |
| [social-card-specs.md](social-card-specs.md) | 社交卡片输出规格（小红书 3:4 / 方图 1:1 / 公众号宽图） | 社交卡片输出形态时 |

## template-library/（子目录）

模板库本体按 canonical、catalog、governance、reference、library 五区组织；风格
实体与版式实体的身份、别名、依赖和 revision 由 current 指针指向的 registry 提供。
六轴词表、页级语义和治理入口见
[`../template-library/governance/authoring/index/_INDEX.md`](../template-library/governance/authoring/index/_INDEX.md)、[`../template-library/governance/authoring/index/风格路由.md`](../template-library/governance/authoring/index/风格路由.md)、
[`../template-library/governance/authoring/index/设计体系.md`](../template-library/governance/authoring/index/设计体系.md)。
