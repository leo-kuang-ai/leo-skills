# 学术模式（academic vertical）——命名入口与一条龙映射

> **加载阶段**：execute + Route=`generate` 且合同信号含学术场景（论文/答辩/
> 组会/文献汇报/学术海报）时读取；用户直接说「学术模式」即等价于声明该场景。
> 本文档是**既有合同的整合入口**，不新增任何确认门——各环节判据仍归其原文：
> 合同字段见 `image-deck-workflow.md` 步骤 1、图证据见 `academic-figure-evidence.md`、
> 论证骨架见 `styles/06_论证模式/学术五拍.md`、风格见 `styles/科研答辩风.md`。

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
   学术五拍骨架（`styles/06_论证模式/学术五拍.md`）。
3. **母版**：每图绑定图证据行——六种处理模式封闭枚举（preserve/
   overview+detail/split/cross-slide/not-use/request-higher-resolution）+
   figure_id/focus；数字走 Numbers-not-adjectives 与三级标注；公式页用
   LaTeX 公式渲染（fragments 记录 provenance）。
4. **风格默认推荐**：dense-defense 推荐「科研答辩风」dense 档（左 TOC 侧栏、
   2–4 编号面板、重绘表格）；minimal 推荐清爽专业/电子墨水杂志风。推荐必须
   带归因一句，用户点名/参考图优先序不变。
5. **样张**：锚定**最典型难页**——答辩档默认取最高密度证据页（图/公式/表格页），
   组会档默认取核心方法页；比例合同与成本先告知纪律不变。
6. **交付**：来源清单 strict 校验含每图 provenance；公式/图证据页在交付披露
   中单列；交付收据门不变。

## 边界

- 学术模式不改变 Route（仍是 `generate`）、不豁免确认序列与数据分级；
- Beamer/LaTeX 输出**不在**学术模式范围内（交付物仍为 PPTX）；
- 组会与答辩的分档只影响密度与版式推荐，不改变任何质量门。
