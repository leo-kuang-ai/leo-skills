# 学术模式（academic vertical）——命名入口与一条龙映射

> **加载阶段**：execute + Route=`generate` 且合同信号含学术场景（论文/答辩/
> 组会/文献汇报/学术海报）时读取；用户直接说「学术模式」即等价于声明该场景。
> 本文档是**既有合同的整合入口**，不新增任何确认门——各环节判据仍归其原文：
> 合同字段见 `image-deck-workflow.md` 步骤 1、图证据见 `academic-figure-evidence.md`、
> 论证骨架见 `template-library/canonical/axes/argument/argument-学术五拍/body.md`、
> 风格 brief 见 `template-library/canonical/styles/research-defense/brief.json`。

## 入口判定

任一命中即进入学术模式：材料是论文/预印本/学位论文章节；用户目标是答辩、
组会汇报、文献分享；受众含导师/评委/同行评审。用户说「学术模式」而无学术
材料时，先问材料来源，不得凭空构造论文内容（三级标注 unknown 纪律不变）。

## 一条龙映射（全部为既有合同的指认，无新增门）

1. **合同轮（三字段 + 档位）**：`math_load`（light/medium/heavy）、
   `figure_orientation`（figure-first/balanced/text-first）、`section_priority`
   （分节优先级页数分配 H/M/L→页数）三字段必填；同时问明交付档位——
   **组会简报（minimal）还是答辩证据密集（dense-defense）**，未问明不得默认
   取密集档。交付档案若存有偏好只作预填建议，档位仍须本轮明示。
2. **大纲**：按 `rst-paging.md` 的 8 关系词表标注分页边界（same-unit 绝不拆页），
   论断式要点规则不变；答辩档建议「研究问题→方法→证据→限制→贡献」的
   学术五拍骨架（`template-library/canonical/axes/argument/argument-学术五拍/body.md`）。
3. **母版**：每图绑定图证据行——六种处理模式封闭枚举（preserve/
   overview+detail/split/cross-slide/not-use/request-higher-resolution）+
   figure_id/focus；数字走 Numbers-not-adjectives 与三级标注；公式页用
   LaTeX 公式渲染（fragments 记录 provenance）。母版含参考文献页/段时，
   派发前另跑 `python3 scripts/check_references.py <母版>` 做文献元数据
   离线校验（DOI 格式 / 同文献多处引用一致性 / GB/T 7714 提示，R-13；
   FAIL 项 strict 档并入交付披露，联网 CrossRef 交叉属后续）。
4. **风格默认推荐**：dense-defense 推荐「科研答辩风」dense 档（左 TOC 侧栏、
   2–4 编号面板、重绘表格）；minimal 推荐清爽专业/电子墨水杂志风。推荐必须
   带归因一句，用户点名/参考图优先序不变。
5. **样张**：锚定**最典型难页**——答辩档默认取最高密度证据页（图/公式/表格页），
   组会档默认取核心方法页；比例合同与成本先告知纪律不变。
6. **交付**：来源清单 strict 校验含每图 provenance；公式/图证据页在交付披露
   中单列；交付收据门不变。

## 学术图表规范（figure-first 判据，R-14）

学术场景 `figure_orientation=figure-first` 时，图表制作执行以下公约数判据
（只定判据不动 `styles/` 风格资产，风格分节轴接入由风格线另行处理）：

- **色盲安全调色板封闭枚举**：数据系列着色取 Okabe-Ito 八色或 Paul Tol
  亮色系之一，全 deck 单选不混用；红绿对不作唯一区分通道（附加形状/线型/
  直接标注）。
- **误差表示必填判据**：均值类统计图必须带误差表示（误差棒 / 置信区间带 /
  box plot 四分位），并注明样本量 n 与误差类型（SD/SE/95%CI）；缺任一项
  降级示意版式（对齐数字登记表「统计图缺样本量/误差标注降级示意」）。
- **多面板网格对齐**：多子图共享轴对齐（共享轴只标一次）、子图间距一致、
  面板标签 (a)(b)(c) 左上编号；同一物理量跨面板同单位同量程，除非注明。
- **学科倾向色板（advisory）**：图表容器/底色/标题带倾向参考（源
  paper2anything color_palettes.md，快照 2026-08-31），行序
  primary→secondary→accent；不豁免上条数据系列封闭枚举：
  | 计算机/AI | 生物/医学 | 物理/数学 | 工程 | 社科 | 化学/材料 |
  |---|---|---|---|---|---|
  | #1B3A5C | #2D6A4F | #5A189A | #E76F51 | #6D597A | #0077B6 |
  | #2E86AB | #52B788 | #9D4EDD | #F4A261 | #B56576 | #00B4D8 |
  | #A3D5FF | #B7E4C7 | #E0AAFF | #FFDDD2 | #EAAC8B | #90E0EF |

## 评审视角矩阵（dense-defense 答辩档）

- 机制来源：storm persona 生成器——评审视角从**同类材料的结构先例**归纳
  （先取同类话题文章目录作 examples 再派生编辑 persona，
  `persona_generator.py` L77-97；上游快照 2026-08-31），不凭空生成视角。
- 答辩档在大纲制作前从材料归纳 **3–5 个评审 persona**，每个一行：
  `persona 名 | 关注维度 | 最可能追问 1–2 条`；追问须能指回材料中的证据
  或明示的缺口，指不回的不得列入。
- 归纳顺序：先扫材料自带的评审信号（审稿意见/限制节/对比实验/导师批注），
  不足再按同类答辩常见维度补齐（方法新颖性/基线公平性/样本与误差/
  可复现性/泛化边界/工程代价），补齐项标注来源为「结构先例」而非「引用」。
- 映射到页配额：每 persona 配 1–2 个预设追问页（Q&A 预设页或 backup
  附录页），大纲对应节标注 `persona:<名>` 锚；组会 minimal 档不生成矩阵。
- 矩阵随大纲一并呈现——寄生既有大纲确认门，**不新增确认门、不改确认
  序列**；未采纳的 persona 在确认摘要说明一句后删除。

## 边界

- 学术模式不改变 Route（仍是 `generate`）、不豁免确认序列与数据分级；
- Beamer/LaTeX 输出**不在**学术模式范围内（交付物仍为 PPTX）；
- 组会与答辩的分档只影响密度与版式推荐，不改变任何质量门。
