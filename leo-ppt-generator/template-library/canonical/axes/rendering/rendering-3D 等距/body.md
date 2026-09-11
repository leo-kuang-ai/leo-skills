# 图片渲染：3D 等距（3d-isometric）

**分类:** canonical/axes/rendering · 现代商业

**配对视觉风格:** blueprint / soft-rounded

**定位:** Isometric 3D forms with controlled depth — boxes, layers, devices, stacks rendered in 30°/30°/30° projection. The dominant choice for tech architecture, product structure, and system composition visuals in modern decks.

## 1. 风格段落（paste-ready，可直接用于图片生成）

> 3D isometric illustration with clean geometric forms rendered in true 30°/30°/30° projection. All edges are crisp and uniform — no perspective distortion, no vanishing points. Surfaces use flat solid fills with subtle tonal shifts (a single darker shade for shadowed faces, ~15% darker than the light-facing face) to convey volume without painterly rendering. Edges may have thin uniform outlines or use direct color contrast. Composition emphasizes stackable, modular forms — boxes, blocks, layers, cards floating in arrangement. Soft 8% drop shadows beneath floating elements anchor them in space. Overall feel is technical, structured, contemporary — common in SaaS product diagrams, cloud architecture visuals, system component breakdowns. Rendering guardrails: no text, no lettering, no numbers, no logos, no watermarks inside the image — any typography is applied later by the page layout, never by the image model. Compose for a 16:9 widescreen canvas (2560×1440): wide horizontal frame, not a poster column.

## 2. 线条 · 纹理 · 深度

| 维度 | 处理 |
|---|---|
| 线条质量 | Thin uniform edges, or no edges relying on color contrast |
| 纹理 | None on surfaces — flat fills |
| 深度 | True isometric projection (30°/30°/30°), tonal shading on shadowed faces, optional 8% drop shadow under floating elements |
| 材质 | Flat with tonal shading — not glossy, not photorealistic |
| 情绪 | Technical, modular, contemporary |

> 色值来自 deck 的 `colors` 锚点，本渲染只描述画法，不写死 HEX。

## 3. 场景变体：地图（isometric-map）

> 来源：JimLiu/baoyu-skills(MIT,快照 6b7a2e4 2026-07-03) · baoyu-infographic/references/layouts/isometric-map.md（思想级改写）。

用于园区/办公室布局、城市与生态地图、用户旅程地图、系统架构「流程景观」等
空间或系统映射页：30° 等轴鸟瞰下，地点画为建筑/地标微场景，路径以等轴线连接，
标签悬浮于物体上方（文字仍由页面布局后期叠加，图内禁字 guardrail 不变）；
整图配 legend 与比例尺占位。该变体不另立渲染条目，作为本轴的场景扩展描述。