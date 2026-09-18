# 图片渲染：发光扫描渲染（luminous-scan-render）

**分类:** canonical/axes/rendering · 现代商业

**配对视觉风格:** —（本批新增渲染,无固定 01 配对;可直接点名,默认使用场景见 `template-library/governance/authoring/index/视觉风格配对.md` 末节）

**定位:** 医学扫描美学——单一主体呈现为发光半透明组织,交织光纤/节点/通路浮于白灰渐变,「从内部点亮」的 hero

## 1. 风格段落（paste-ready，可直接用于图片生成）

> An advanced medical-scan aesthetic: a single subject rendered as luminous, semi-transparent structure — interwoven lit fibers, nodes, and glowing pathways — floating on a clean white-to-grey gradient. Minimalist, high-focus, and text-free, letting the glowing form carry the slide. Clean, technological, and futuristic — a striking hero visual for anatomy, systems, or anything you want to show 'lit from within'. Rendering guardrails: no text, no lettering, no numbers, no logos, no watermarks inside the image — any typography is applied later by the page layout, never by the image model. Compose for a 16:9 widescreen canvas (2560×1440): wide horizontal frame, not a poster column.

## 2. 线条 · 纹理 · 深度

| 维度 | 处理 |
|---|---|
| 线条质量 | Lit fiber pathways and node points; no outlines, glow defines edges |
| 纹理 | Semi-transparent volumetric tissue, faint scan banding |
| 深度 | Floating luminous volume on receding white-grey gradient |
| 材质 | Glowing translucent structure, scan-grade light |
| 情绪 | Clean, technological, futuristic, high-focus |

> 渲染画法不写死 HEX;源卡参考色板 `#2BE38A / #F2F5F3 / #0D1B12 / #7CF2B8（首色为 accent）` 与信息密度 `low` 仅作 deck `colors` 锚点缺省时的默认建议。适用场景（源自卡 tags）：解剖/系统 hero 图 / 医疗科技 / 架构总览 / 未来感主视觉。

## 3. 来源与许可

- 源卡: `nb-luminous-scan-render` · author: Dera | Performance marketing Creative · YouMind Awesome Nano Banana Pro Prompts
- 案例页: https://x.com/Ifekaego1/status/2068607373200039956
- 许可: CC BY 4.0 — https://github.com/YouMind-OpenLab/awesome-nano-banana-pro-prompts/blob/main/LICENSE（经 codex-slides `src/lib/community.ts` 快照 2026-08-31 映射;S2b 吸收）
