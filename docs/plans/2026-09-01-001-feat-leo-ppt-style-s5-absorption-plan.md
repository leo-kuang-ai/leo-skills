# leo-ppt-generator Style S5 吸收批集成方案（v2 修正版）

> 日期：2026-09-01
> 来源：3 专家 agent 对 `/Users/kuang/knowledge/ppt-github` 全量 122 项 + 特殊条目的逐项目审查（无抽查）；v1 方案经事实核验后修正为 v2（修正对照见附录 A）。
> 前提更新：GordenPPTSkill（稻壳）与 dashi-ppt-skill（AGPL）已获项目负责人线下授权（2026-09），许可红线按本方案批次 2 修订。
> 目标：三类全量集成后，skill style 库对 ppt-github 生态达到语义 100% 覆盖 + 实体资产登记 + 治理完备。

---

## 0. 口径与计数总表（E1/E2/G2 修正后）

两套计数口径，登记时**两处都必须改**（G2）：

| 口径 | 现值 | 目标值 | 说明 |
|---|---|---|---|
| lint 口径（`lint_style_index.py` 的 `BRIEF_DIRS` = 01/02/03/05 + 顶层） | 273 | **279** | lint 实际校验值：顶层 11 + 01 + 02 + 03 + 05 |
| 全口径（`_INDEX.md` 注记段，含 15/16 来源目录） | JSON 305 / 独立可选 288 | **311 / 294** | 独立可选 294 ≤ 300 硬顶 ✓ |

分区计数 delta（E1 修正：01 只增 5 套，非 6）：

| 分区 | 现值 | 目标 | 子节同步（标题括号计数） |
|---|---|---|---|
| `01_通用母版/` | 150 | **155** | 商务专业 12→13、科技数字 15→16、设计流派 25→27、柔和治愈 9→10 |
| `02_行业内容域/` | 69 | **70** | 医疗健康 18→19 |
| `10_品牌身份/` | 34 | **36** | 批次 3 补招行/重庆大学（不进 lint 风格口径、不进配对表） |

其余同步：`_INDEX.md` 头行"273 份"表述、总览表行数、`视觉风格配对.md` 主表 **+6 行**、`风格路由.md` 相关维度表 **+6 条目**（G1，见 1.2）。

---

## 1. 批次 1：6 套真缺口 brief（R-29 四步入位）

### 1.1 六套清单（源路径与锚点以实际文件为准）

统一动作流：复制 `00_索引/style-extension-template.md` → 填写（结构真值门 = `lint_style_briefs.py`，模板引用的 `schemas/style-brief-v1.schema.json` 不存在于仓库，以 lint 输出为准，G3）→ 过四条 lint → 登记（`_INDEX.md` + `视觉风格配对.md` + `风格路由.md`）。头部按 S 批先例写"可参考来源"。

| # | 新风格 | 权威源（保真 HEX 提取处） | 落点 | 核心锚点 | 区分性声明要点 | 插画配对 |
|---|---|---|---|---|---|---|
| 1 | 玩味手绘极简风 | huashu-design `references/design-styles.md` L251（Collins 式·大胆·还原 75%） | `01_通用母版/设计流派/` | 荧光黄大面积（Cavendish 黄系，源文件取实值）+ 黑 + 奶油白；Cooper 式圆润衬线大题 | vs 荧光黄商务风（融资 sans 向 vs 品牌玩味衬线）、vs 温暖手工风（纸感手工 vs 品牌怪诞编辑） | collage/core |
| 2 | 人文圆角卡片风 | 同上 L341（Khan 式·安静·还原 80%） | `01_通用母版/柔和治愈/` | 森林绿系（#14BF96/#0A5C4B 待源核）+ 米白暖底 + 大圆角卡 + Source Serif | vs 中小学课堂风（蓝橙活泼 vs 绿系人文衬线）、vs 奶油温柔风（粉系 vs 绿系 + 卡片组件化） | flat/supportive |
| 3 | 不羁玩梗流行风 | 同上 L258（Reddit 式·大胆·还原 80%） | `01_通用母版/设计流派/` | Reddit 橙红 #FF4500 + 撞色；David Carson 破格混排、90s web 复粗边硬影、fun→facts 节奏反转 | vs 波普艺术风（网点拼贴 vs 破格混排）、vs 新粗野主义风（秩序粗边框 vs 无网格旋转重叠） | collage/supportive |
| 4 | 地图战略风 | open-kimi `skills/open-kimi-ppt/reference/design_system/01_strategy/06/en/map-strategy.md`（theme.md L313 链接，P1 修正） | `01_通用母版/商务专业/` | 暖白纸底 + 深藏青 + 克制钴蓝 + 朱砂坐标；地图/航线/等高线/经纬网格/图例编号 DNA | 全库唯一以地图叙事为母版的视觉风格（07 轴"地图"仅是图像内部骨架）；vs 咨询精密网格风、vs 工程蓝图风 | diagram/supportive |
| 5 | 浅粉棕医院运营风 | yixueAIganhuo-PPT `references/style_selector/assets/`（019 实体资产；manifest 仅登记，P3 修正） | `02_行业内容域/医疗健康/` | 浅粉 + 浅棕双联 + 白；经营指标环、科室对比柱状、粉棕斜切几何与建筑摄影 | 医疗域 18 套全为科研/临床/品牌向，本套补运营管理场景；vs 暖陶土医学风、vs 医院品牌风（蓝青系） | dashboard/core |
| 6 | 粉紫云层诊断风 | open-kimi `skills/open-kimi-ppt/reference/design_system/05_academic/01/en/pink-purple-diagnosis.md`（theme.md L401 链接，P1 修正） | `01_通用母版/科技数字/` | 白底工程正文 + 粗深蓝标题 + 单强调下划线锚；粉紫渐变仅封面/收尾（#F7CDD8→#DCC8F2、#3A1D6E→#5C40A8 待源核） | vs 樱粉雾蓝风（全幅渐变氛围 vs 白底正文渐变仅首尾）；**若 `family_duplicate` 告警则降级为樱粉雾蓝风 `variant_of` 变体，不硬立顶层** | glass/supportive |

落点分布核对：01 共 5 套（#1/#3 设计流派、#2 柔和治愈、#4 商务专业、#6 科技数字），02 共 1 套（#5）——与 0 节计数 delta 一致。

### 1.2 登记动作清单（每套完成后逐项勾选）

- [ ] `lint_style_briefs.py`：`briefs=` +1、无 ERROR/未登记 WARNING（四角色 HEX + 身份字族；新文件不进基线白名单）、`family_duplicate` 不触发
- [ ] `lint_style_index.py`：`_INDEX.md` 头行 273→279、总览表 01/02 行数、**子节标题计数**（见 0 节）
- [ ] `lint_style_governance.py`：`视觉风格配对.md` +1 配对行（有渲染锚）
- [ ] `lint_layout_grid.py`：无版式网格偏离
- [ ] **`风格路由.md`（G1）**：快速路由表 / 相关维度表补本风格条目（6 套均需；#5 走行业身份维度、#4 走视觉风格-商务维度、其余按气质维度）
- [ ] `_INDEX.md` 注记段全口径 305→311、288→294 同步（G2）
- [ ] 人工门五条自述（模板第九节）+ 区分性声明（第七节）

---

## 2. 批次 2：授权解锁的实体模板资产登记

### 2.1 GordenPPTSkill（E2 修正：不可整收，101MB → 精选 ≤4 套 + 全量映射表）

实测：`templates/` 22 项 = 21 套 + INDEX.md，共 **101MB**；单套 3.8–14MB。officecli 先例仅 **72K**（4 个小 PPTX）。**禁止整目录复制**。

动作：

1. **精选实体 ≤4 套**复制入 `samples/reference-golden/gorden/`（对齐 officecli 先例量级，总体积目标 < 15MB；超限则从套内抽代表性页拆分）：
   - `red-patriot-general`（10M，党政红族金样板）
   - `thesis-formula`（答辩族，取最小一套 thesis）
   - `report-massive-charts`（汇报图表族）
   - `mckinsey-style`（咨询族）
2. **全 21 套 README-only 映射表**：`samples/reference-golden/gorden/README.md` 逐套登记七字段（模板名 / 页数规模 / 主色 / 场景 / 源路径 / 与 skill 侧等价 brief 映射 / 是否已收实体）。映射沿用审查结论：red-patriot×2、red-teaching×2 → 党政红风格；thesis×3 → 科研答辩/学术论文答辩/课题申请；report-massive×3 → 成果汇报/晋升述职/数据仪表盘；mckinsey-style → 麦肯锡咨询风；quarterly-illust → 合成波/复古视窗；其余按审查表。
3. 授权说明：README 头部注明"2026-09 获项目负责人线下授权收录，仅限本仓库参考使用"。

### 2.2 dashi-ppt-skill（P4 修正：candidates 修订为主，golden 目录名不副实）

dashi 为 React 主题组件 + 1000 页版式母矿，**无 PPTX 实体**，不落 `samples/reference-golden/`（该目录先例只放实体样板）。动作：

1. `references/style-candidates.md` dashi 行修订：勘察定级 C（只借鉴思想）→ **B（授权登记）**；净新说明补"theme01–12 色板 HEX 已获授权可直引"；新增授权说明（2026-09 线下）。
2. 可选：色板索引（themeNN → HEX → 场景 → 等价 brief）以附录形式并入 candidates 文件或独立 `references/style-sources/dashi-themes.md`，不新建 golden 目录。

### 2.3 红线修订（style-candidates.md）

"许可红线"段改为：*GordenPPTSkill（稻壳来源）与 dashi-ppt-skill（AGPL）已于 2026-09 获项目负责人线下授权：Gorden 按金样板先例精选收录 + 全量映射登记（见 `samples/reference-golden/gorden/README.md`）；dashi 升级为授权登记可直引色板。其余红线不变（无授权源仍只做思想级）。*

---

## 3. 批次 3：4 项治理补强

| # | 动作 | 文件 | 修正说明 |
|---|---|---|---|
| 1 | 麦肯锡咨询风来源补注 | `01_通用母版/商务专业/麦肯锡咨询风.md` | 已有"可参考来源"节（核实 ✓），追加一行：`mckinsey-pptx · mckinsey_pptx/theme.py（深海军蓝 #0F2A4A 系同族色板变体，不另立风格）`，aliases 补 "mckinsey-pptx navy" |
| 2 | 品牌轴 +2 | `10_品牌身份/招商银行.md`、`重庆大学.md` | 格式照现有品牌条目；VI 近似色从 cn-academic-spark `skills/CN_Spark_paper2ppt/templates/layouts/<家族>/design_spec.md` 提取；节头免责口径（公开资料近似值）沿用；`_INDEX.md` 品牌身份节 +2 行、计数 34→36；不进配对表 |
| 3 | 手绘技术解释风来源标注 | 顶层 `手绘技术解释风.md` | **P2 修正：该文件头部无"可参考来源"节（核实 ✓），需在"适用场景"后新增来源节**：`GitHub: ian-handdrawn-ppt · assets/theme-tokens.json（theme-tokens 同源，内容已先行吸收）` |
| 4 | deckjs 登记行 | `references/style-candidates.md` 候选表 | 七字段：gitee-mirrors/deckjs｜3 个框架主题（neon/swiss/web-2.0）｜勘察 D 弱｜净新 0（swiss 与瑞士网格风重合、neon/web-2.0 为框架级样式）｜不收｜触发：无｜去重：无 |

---

## 4. 门禁与验证（每批完成后全跑）

```sh
python3 leo-ppt-generator/scripts/lint_style_briefs.py      # briefs= +6，无 ERROR
python3 leo-ppt-generator/scripts/lint_style_index.py       # 273→279 同步
python3 leo-ppt-generator/scripts/lint_style_governance.py  # 配对行同步
cd leo-ppt-generator && python3 scripts/lint_layout_grid.py
cd leo-ppt-generator && skill-up run evals/eval.yaml        # 回归评测
```

注意：`lint_layout_grid.py` 与 eval 必须在技能目录内运行（AGENTS.md 约定）；governance 若同样要求 cwd，以脚本报错为准调整。

---

## 5. 提交切分与 CHANGELOG

| 提交 | 内容 | CHANGELOG |
|---|---|---|
| 1 | `leo-ppt-generator: S5 批吸收 6 套缺口风格 brief（huashu/open-kimi/yixue）` | 风格新增条目，标 `(user-visible)` |
| 2 | `leo-ppt-generator: Gorden/dashi 授权后金样板登记与许可红线修订` | 实体资产条目 |
| 3 | `leo-ppt-generator: 品牌轴补招行/重大与来源标注补强` | 治理条目 |

每次提交前跑第 4 节全部门禁并记录结果（AGENTS.md 提交纪律）。

---

## 6. 可选增强（不阻塞、不触发义务）

- #1/#4/#5 三套走 `generate_style_gallery.py --render-golden` 补 3 页金样板缩略图（双跑 sha256 一致），产物进 `samples/style-gallery/<风格名>/`。定性依据：6 套走扩展模板（金样板属可选门）且不从 candidates 表入库，不触发"同批补金样板"义务；Gorden/dashi 为样板登记非风格入库，同样不触发。
- #6 若保真 HEX 核对后与樱粉雾蓝风色板指纹过近，直接走 `variant_of` 降级路径（1.1 表内预案）。

---

## 附录 A：v1 → v2 修正对照（9 处，审计可溯）

| 编号 | 类型 | v1 问题 | v2 修正 |
|---|---|---|---|
| E1 | 实质错误 | 01_通用母版计 150→156 | 150→**155**（01 只收 5 套）；补子节标题计数同步动作 |
| E2 | 实质错误 | Gorden 21 套整目录复制 | 实测 101MB 不可整收 → **精选 ≤4 套（<15MB）+ 全 21 套 README 映射表**；officecli 先例实测 72K |
| G1 | 完整性缺口 | 未更新 `风格路由.md` | 批次 1 登记 checklist 显式加入路由表 +6 条目 |
| G2 | 完整性缺口 | 两个计数口径混写 | 0 节分列表格：lint 口径 273→279 与全口径 305→311/288→294 两处都改 |
| G3 | 完整性缺口 | 依赖不存在的 `schemas/style-brief-v1.schema.json` | 结构真值门改为 `lint_style_briefs.py` 输出 |
| P1 | 执行偏差 | open-kimi 源写"theme.md 补充节" | 权威源改为 design_system 独立规格文件（L313/L401 链接已核实） |
| P2 | 执行偏差 | 手绘技术解释风"来源节补注" | 该文件无来源节，改为**新增**来源节 |
| P3 | 执行偏差 | yixue 019 写"manifest 019" | tokens 从 `style_selector/assets/` 实体提取 |
| P4 | 执行偏差 | dashi 落 `reference-golden/dashi/` | golden 先例只放实体；改为 candidates 表修订为主 + 可选独立色板索引文件 |
