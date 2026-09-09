# 14_参考池_gpt-image2

> gpt-image2-ppt-skills `styles/xiamulingzi/` 233 套单页参考池的家族化
> 归并目录(C1 批)。每池 = 1 个池代表 brief(可整池选用的独立风格)
> + 1 份同名 `.清单.md`(登记全部成员源 ID/原名/主色板)。本目录
> **不计入 _INDEX.md 的 JSON 风格 brief 口径**(lint_style_index 的
> BRIEF_DIRS 不含 14_),也不进视觉风格配对主表——最小破坏计数
> 结构;选风格时可经 `_INDEX.md` 参考池节或直接点名池名/成员源 ID。

| 池 | 归并键 | 池内套数 | 代表成员 |
|---|---|---|---|
| **朋克深底撞色池** | punk/dark | 22 | `linzi-punk-fg11-0324-e488f418` |
| **朋克白底撞色池** | punk/light | 4 | `linzi-punk-fg11-7001ppt-2d4f3d66` |
| **科技浅底净色池** | tech/light | 2 | `linzi-tech-7-0cf19a16` |
| **科技深底霓虹池** | tech/dark | 8 | `linzi-tech-9-429050a1` |
| **莫兰迪冷调编辑池** | morandi/cool | 11 | `linzi-morandi-ppt-50-0cfbe592` |
| **莫兰迪暖调编辑池** | morandi/warm | 104 | `linzi-morandi-2-21-40ppt-ppt-37-45157cb4` |
| **莫兰迪深色雕塑池** | morandi/dark | 82 | `linzi-morandi-2-21-40ppt-ppt-14-1678fc3d` |

归并规则(确定性,见 `scripts/intake_gpt_image2.py` 的 classify_pool):
底色锚(色板首位)亮度 <0.45 → 深色池;否则按饱和锚的暖/冷多数归池(平局归暖)。
punk/tech 组仅按深浅二分。重跑 `--write` 幂等覆盖本目录全部产物。
