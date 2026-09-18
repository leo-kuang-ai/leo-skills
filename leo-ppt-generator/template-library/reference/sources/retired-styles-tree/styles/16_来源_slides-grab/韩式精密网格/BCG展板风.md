# BCG展板风

**分类:** 16_来源_slides-grab · 韩式精密网格
**来源原题:** BCG 익스히빗 덱(ppt-bcg-exhibit-deck,design-diversity)

**适用场景:**
- 咨询展板
- 数据论证
- 董事会材料
- 洞察报告

**可参考来源:**
- GitHub: epoko77-ai/design-diversity(via slides-grab design-diversity-data.js,MIT,快照 2026-05-24)· DD41 BCG 익스히빗 덱

**GPT-Image-2 风格 Brief:**
```json
{
  "type": "16:9 full-slide PowerPoint image",
  "style_name": "BCG展板风",
  "aliases": [
    "BCG 익스히빗 덱",
    "BCG exhibit",
    "展板编号"
  ],
  "best_for": "Exhibit 编号 + answer-first 的咨询展板语法;适合咨询报告/数据论证/董事会材料",
  "visual_direction": "BCG exhibit deck, every slide numbered Exhibit N.N in mono green at top-left, answer-first conclusion header, source footnote line at bottom, charts are the slide",
  "canvas": {
    "aspect_ratio": "16:9",
    "background": "#FFFFFF、#F2F4F3(变体锚)",
    "composition": "左上 Exhibit 编号标签 + 首句结论页眉 + 底部来源行,图表即页面",
    "density": "medium, 密而不挤"
  },
  "color_palette": {
    "primary": "#FFFFFF(白底)",
    "secondary": "#F2F4F3(浅灰面)",
    "accent": "#177B57(BCG 绿唯一强调)",
    "neutral": "#1A1A1A(墨字)"
  },
  "typography": {
    "title": "IBM Plex Sans 700(Inter 兜底)28pt",
    "body": "IBM Plex Sans 400 16pt 级",
    "labels": "IBM Plex Mono 500 11pt Exhibit 标签,tracking 0.06em"
  },
  "layout_patterns": [
    "左上 Exhibit 3.2 式等宽编号标签(绿)",
    "页首 answer-first 结论句,单结论",
    "底部 Source 脚注行",
    "图表/表即页面主体"
  ],
  "layout_usage_rule": "左上 Exhibit 3.2 式等宽编号标签(绿)",
  "visual_elements": {
    "allowed": "左上 Exhibit 编号标签 + 首句结论页眉 + 底部来源行,图表即页面",
    "avoid": "不要把 BCG 绿用作大面积底色——只用于强调文本/关键数据系/Exhibit 标签; 不要渐变/阴影/圆角/表情符号/剪贴画"
  },
  "rendering_constraints": [
    "不要把 BCG 绿用作大面积底色——只用于强调文本/关键数据系/Exhibit 标签",
    "不要渐变/阴影/圆角/表情符号/剪贴画",
    "不要一页两个 takeaway",
    "色板锚点以 brief HEX 为准,不漂移;文案准确,不虚构标识"
  ],
  "negative_prompt": [
    "不要把 BCG 绿用作大面积底色——只用于强调文本/关键数据系/Exhibit 标签",
    "不要渐变/阴影/圆角/表情符号/剪贴画",
    "不要一页两个 takeaway"
  ],
  "paired_illustration": {
    "family": "diagram",
    "density": "core"
  },
  "reference": "GitHub: epoko77-ai/design-diversity(via slides-grab design-diversity-data.js,MIT,快照 2026-05-24)· DD41 BCG 익스히빗 덱"
}
```
