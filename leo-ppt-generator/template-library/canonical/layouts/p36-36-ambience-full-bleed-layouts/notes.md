# 版式：P36 · Ambience Full Bleed · 氛围全图

**分类:** canonical/layouts（图片主导版式）

**用途:** 章节情绪页 / 里程碑仪式页 / 发布会呼吸页 / 品牌氛围转场。

**适用内容类型:** **恰好 1 张全幅真实图片 + 最多一句叠加断言**(≤12 字)+ kicker(≤4 词)。零要点页:不承载列表、数据、段落——本版式是「零要点页合法地位」的规范形态(见通用设计规范密度档位)。图片必须是真实图源(实拍/官方素材;AI 生成须按三级标注声明,生成-写实禁入);与数据结合的 hero 用 P22 Image Hero,图文论证用 P30 Swiss Image Split。

**骨架:** 图片全幅出血(cover,主体避开文案区;焦点测试:九宫格中心不与文字重叠)/ 文案块贴版心左下(或右下,同 deck 统一):kicker(meta 1.2vw,accent)+ 断言一句(display 9.6vw,限高 `min(9.6vw,16vh)`,CJK 正字距)/ 文字下垫底部局部渐变遮罩(高 ≤28vh,**取图内深色、峰值 alpha ≤0.30**,遵守通用设计规范 §四.4 遮罩纪律;对比不足时优先挪文案位或加实底信息条),保证正文对比 ≥4.5:1/ 主内容最低处仍守 93vh 安全区。

**关键类:** `.fullbleed` `.ambience-copy` `.ambience-veil` `.ambience-kicker`

**动效 recipe:** `ambience-breathe` — 图片 scale 1.04→1 缓慢落定(800ms),文案块在遮罩稳定后 fade-rise(240ms);一 deck ≤2 页使用本版式(仪式页配额,见通用设计规范)

> 版式是「页级可粘贴结构」，约束内容类型匹配（见 `template-library/governance/rules/layouts/00_选版式P0原则.md`）。氛围页的价值在停顿:一句话必须值得全场安静三秒,否则删掉本页。数值呈现遵守 `template-library/governance/authoring/index/图表样式规范.md`。
