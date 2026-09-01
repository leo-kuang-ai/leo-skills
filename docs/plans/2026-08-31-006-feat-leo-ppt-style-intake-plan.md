---
title: leo-ppt-generator 风格资产进货批 - Plan
type: feat
date: 2026-08-31
topic: leo-ppt-style-intake
artifact_contract: spec-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: style-survey-2026-08-31(七路全量勘察 283 项)
execution: code
status: in_progress
---

# leo-ppt-generator 风格资产进货批

## 背景与依据

七路勘察 agent 对 `/Users/kuang/knowledge/ppt-github`(131 项,含 gitee-mirrors)与
`/Users/kuang/knowledge/file-github`(152 目录)做了**零抽查全量判定**(每项实测
资产文件,非 README 推断)。结论:约 40 个项目含可集成风格/版式/品牌/叙事资产,
原始候选 315-395 条;跨组同源对去重(frontend-slides bold 包=beautiful-html-templates
副本、OfficeDex=PPTist 同源、reveal.js 被 oh-my-ppt 包含、open-kimi-ppt-skill 与
open-ppt-skill 同构、ppt-agent-skill/ppt-agent-skills 两项目同族、guizang 姊妹
技能同源)与家族重叠映射后,**净新增主风格按克制口径收敛为 60-100**(家族 13→20-25),
另增叙事风格层 12、品牌 14、版式/机制资产若干。leo 现库基数:121 主风格+16 变体。

## 源头配额表(按净价值排序,全部走统一治理门)

| # | 源项目 | 原始规模 | 分级 | 吸收配额 | 途径 |
| --- | --- | --- | --- | --- | --- |
| 1 | oh-my-ppt | 75 风格包(SKILL+style.json+aliases+负面+preview 四件套) | A | 净增 45-55 | 脚本迁移+精选 |
| 2 | html-ppt-skill | 36 CSS token 主题+47 版式目录 | A | 净增 12-18(与 #1 终端系去重) | 脚本迁移 |
| 3 | OfficeCLI morph-ppt | 51 md 风格+21 成品 PPTX | B | 净增 10-15+金样板 21 | LLM 抽取 |
| 4 | LandPPT | 25 带标签完整 HTML 模板 | A | 净增 12-15(中式载体/印象派两新家族) | 脚本+抽取 |
| 5 | open-kimi-ppt-skill(=open-ppt-skill 同构) | 30 套双段式 design.md | B | 净增 12-18 | LLM 抽取 |
| 6 | codex-slides | 45 内置+22 社区生图卡(带许可台账) | A | 净增 8-12+生图卡入 08 轴 | 脚本迁移 |
| 7 | presentation-ai | 39 主题七语义槽 token | A | 净增 6-10(与 #1/#2 去重)+smartLayout 机制 | 脚本迁移 |
| 8 | yixueAIganhuo-PPT | 19 医学风格 JSON | A | 净增 12-14(医疗域加密)+continuity 机制 | 脚本迁移 |
| 9 | slides_maker | 18 预设(guard+image_prompt) | A | 净增 10-11(孟菲斯/蓝晒/粗野等) | AST 迁移 |
| 10 | xiaobei(file-github) | 15 品牌 token 化设计系统 | A | 品牌轴净增 14(10_品牌身份,不占主风格配额) | 脚本迁移 |
| 11 | ppt-master | 19 视觉+12 叙事+7 版式(三层正交) | A | 视觉净增 5-8+**叙事层 12 整层新立** | 脚本+抽取 |
| 12 | academic-ppt-master | 20 风格+15 调色板+三层配对矩阵 | B | 净增 6-10 | LLM 抽取 |
| 13 | huashu-design | 20 PPT 库(三派) | B | 净增 6-10+审美禁区负面语料 | LLM 抽取 |
| 14 | frontend-slides-editable | 46 预设+34 模板(=beautiful 副本) | B | 净增 10-15(取 beautiful 上游双 JSON) | 脚本+抽取 |
| 15 | slides-grab | 90 套(30 西式+60 韩式) | A | 净增 15-25(韩式咨询精密网格新审美) | 脚本迁移 |
| 16 | gpt-image2-ppt-skills | 265 套(32 完整+233 单页池) | B | 完整套净增 15-20;233 池家族化归并 5-8 变体池 | 脚本+抽取 |
| 17 | Awesome-PPT-Design-Skills | 7 套编辑系(日式双变体) | A | 净增 4-5 | 改写迁移 |
| 18 | xhs-visual-director(file-github) | 24 版面气质 | B | 净增 8-12(改画幅) | LLM 抽取 |
| 19 | presentation-skill | 311 原子+13 家族语法+2000 语料 | A | 机制层:原子组合路由(不占条目配额) | 脚本迁移 |
| 20 | 其余 B/C 级(ppt-agent-skill 26/dashi 12 主题/nano-banana/MultiAgentPPT 9/AI-PPT-Slides 4/Mck/OfficeMCP/scholar-ppt-cn/awesome-gpt-image-2 余量/awesome-ppt-skills 31 提示词/ppt-mcp 17 色板/echarts 35 图表色板/revealjs 16) | — | B/C | 择优合计净增 10-20;echarts+ppt-mcp+revealjs 入 token 池与 chart_series 弹药 | 抽取 |

**配额执行纪律**:各源吸收到配额上限即停,按各勘察报告的净新方向清单选取;
全部过四条治理 lint+`family_duplicate` 防回潮+13 家族归属(variant_of 优先于新条目);
总数硬顶:**进货完成后主风格 ≤ 220**(121+配额合计约 200-210+缓冲)。

## 版权红线(硬门)

- **GordenPPTSkill(稻壳儿来源,明示非商业)**:只允许提炼风格语言文字描述,
  禁止搬运 PPTX/图片/字体素材——本批不将其纳入吸收源,仅记录;
- codex-slides 社区卡自带 CC BY/MIT 台账,随条目登记;其余源按用户已确认的
  线下授权口径执行,NOTICE 法定最小集照旧。

## 批次划分(每批独立可验证,全部走既有门禁)

- **S1 机制同构快赢**:源 1/9/17(oh-my-ppt 精选+slides_maker+Awesome)→
  净增约 60-70;随批:aliases 全量补齐(121 既有参考风格别名债一并清偿)。
- **S2 A 级整库**:源 2/4/6/7/10(html-ppt-skill/LandPPT/codex-slides/
  presentation-ai/xiaobei 品牌)→ 净增约 50-60;随批:smartLayout 槽位进
  schema、生图卡入 08 轴。
- **S3 B 级抽取**:源 3/5/8/12/13(OfficeCLI/open-kimi/yixue/academic/huashu)
  → 净增约 45-55;随批:continuity/asset_embedding schema 升格通用机制。
- **S4 结构层**:源 11/14/15/16+20 择优(ppt-master 叙事 12 整层+beautiful/
  slides-grab/gpt-image2/杂项)→ 主风格净增约 40-50+叙事层 12;随批:
  原子组合路由机制评估、echarts/ppt-mcp token 池。
- **S5 收尾治理**:全量 family audit 复测+索引/README/画廊计数迁移+金样板
  补齐(新增主风格各 3 页)+本计划收口。

## 通用迁移合同(每批每源遵守)

1. 目标形态:leo brief 格式(JSON 块:style_name/best_for/canvas/color_palette
   +可选 aliases/negative_prompt/paired_illustration/token_sidecar/variants),
   新增家族同步 style_hard_rules FAMILIES 与 _INDEX 分类;
2. 去重纪律:入库前对色板指纹跑 family_duplicate 预检,同板并入 variant_of;
   跨源同名/同族合并以"有实际令牌者为主";
3. 元数据:aliases 含来源原名;best_for/use_cases 从源 metadata 翻译;
   negative_prompt 从源 avoid/forbidden/负面清单提炼;
4. 验证:每批交付跑五 lint+全量单测零新增失败+audit_style_families 复测
   (簇数不恶化)+CHANGELOG 登记(来源项目+快照日期口径按现行治理);
5. 禁用 git stash(并行纪律)。

## Verification Contract

1. 五条治理 lint+结构 lint 全绿;`skill-up validate evals/eval.yaml` 通过;
2. 全量单测零新增失败(基线 954);
3. `audit_style_families.py` 复测:同族簇数与 family_duplicate 违规为零;
   主风格总数 ≤220;
4. 抽样 3 个新家族经 `style render` 真实渲染成功(渲染 lane 冒烟);
5. known-issues 记录各批吸收数与去重数;CHANGELOG 逐批同步。

## 执行记录

- 2026-08-31 立项:七路勘察(283 项零抽查)汇总去重后制定;S1 批派发。
- 2026-09-01 owner 决策(会话"B"):**主风格硬顶 220→300,候补清单全量进货**
  (净新增空间 94;原始 650 条经四重去重后按价值密度录取至顶)。动机:接受
  大库的推荐稀释风险,以硬规则跨家族配额+variant_of 归并+audit 簇监控对冲;
  若同族簇显著恶化(>20)或推荐质量信号下降,回退门槛在案。执行批次
  C1(gpt-image2 265)/C2(slides-grab 90+OfficeCLI 51)/C3(beautiful 34+
  academic 20+huashu 20)/C4(杂项约 130)四线并行,配额 C1 25-35/C2 25-30/
  C3 20-25/C4 10-15。
