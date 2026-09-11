# 模板系统重构基线（U1 冻结）

> 唯一方案：[2026-09-08-001-feat-leo-ppt-template-quality-plan.md](../plans/2026-09-08-001-feat-leo-ppt-template-quality-plan.md)（v4）。
> 本文是 U1 的冻结记录与摘要；账本真值是
> `leo-ppt-generator/template-library/governance/migration/`，以文件 hash 为准，不以 commit 为准。

## 冻结时点

- HEAD：`a5a60e4bca82eeb239f24f926cb669260c78f83b`（分支 `leo-2026-09-04-update-style-model`）
- 工作区状态：dirty（44 项并行修改，属 005 内容评测等其他任务，重构不覆盖）
- 冻结产物：
  - `template-library/governance/migration/asset-ledger.json` —— 891 项全量账本
  - `template-library/governance/migration/consumers.json` —— 32 个消费点闭包
  - `evals/fixtures/template-quality/recommendation-{tasks,labels,baseline}.json` —— 24 题推荐基线
  - `tests/fixtures/render-theme-baseline/` —— 七模板 21 页改前渲染基线

## 全量资产账本摘要

597 项 references/styles 源资产（排除 generated/）+ 86 项派生文件 + 208 项补充资产（模板/字体/presets/画廊/schema/规则）。

| 来源集合 | 数量 | 目标（template-library/） | 处置 | owner |
| --- | --- | --- | --- | --- |
| references/styles 顶层 11 brief | 11 | canonical/styles/ | convert（纯 JSON 真值） | U3 |
| references/styles 顶层 11 .layouts.json | 11 | 并入 brief.bindings.layout_routes | merge | U3 |
| 01/02/03 及来源目录完整 brief | 300 | canonical/styles/（lifecycle=draft 待审） | convert | U3 |
| 12_版式库 36 sidecar + 36 MD | 72 | canonical/layouts/（几何真值唯一化） | convert/merge | U5 |
| 06/07/08/09/11/13 轴文档 | 124 | canonical/axes/（manifest 化） | convert | U3 |
| 10_品牌身份 | 36 | canonical/brands/ | convert | U3 |
| 14_参考池 | 15 | reference/pools/ | migrate-as-is | U10 |
| 00_索引 + unknown 占位模板 | 13 | governance/authoring/ | convert | U10 |
| 行业 _content_rules | 5 | governance/rules/domains/ | convert | U3 |
| 非公式文档（散文/信息不足） | 7 | reference/candidates/ | to-reference | U3 |
| styles/generated/ 派生物 | 86 | catalog/ 重建 | rebuild-delete | U10 |
| assets/render-templates 7+1 | 8 | canonical/templates/ | convert（主题切换） | U5 |
| assets/render-fonts 4 | 4 | canonical/fonts/noto-sans-sc/ | migrate-as-is | U5 |
| style-presets 2 | 2 | canonical/presets/ | convert | U3 |
| samples 画廊/reference-golden | 180 | reference/historical-gallery、reference/sources | migrate-as-is | U10 |
| chart-palette-pool、render-lint-rules | 2 | canonical/components、governance/rules | convert/migrate | U5 |
| 模板域 runtime schema | 3 | governance/schemas/ | convert（v2 取代） | U9 |

当前分类器角色口径（597 源资产）：style 311 / axis 151 / reference 62 / layout 47 / pool 15 / rule 10 / unknown 1。
与旧 generated/counts.md（pool 7 / reference 70）的差异来自旧计数为陈旧派生物；以本账本冻结的当前树为准。

## ID 分配规则

- `<scope>:<kind>:<immutable-slug>`；顶层 11 风格使用显式英文 slug（如 `builtin:style:clean-professional`）。
- 其余 slug = stem 规范化（ASCII kebab-case；非 ASCII 保留原文；冲突加 -N 序号）。
- §8.1 九方向种子 slug（management-clear、finance-navy、consulting-pyramid、tech-dark、gov-red、health-clean、edu-bright、brand-creative、academic-austere）保留给 U3 新增种子，机械分配不占用。
- 首次分配后 ID 登记即稳定；名称/别名/分类/位置变化不改 ID（KTD4）。

## 消费者闭包（32 个消费点）

`consumers.json` 记录每个消费旧路径/旧 API 的文件。切换 owner：
- U9：`styles.py`/`templates.py`/`layout_bank.py` 的身份与解析入口（asset_resolver 接管）
- U4：`compose_style`/`compose_layout`/品牌/轴投影（组合器唯一化）
- U10：脚本层路径扫描（capability_manifest/lint/intake/pack/gallery）与 SKILL/references 文档

## 24 题推荐基线（F6）

- 8 方向（金融/咨询/科技/政务/医疗/教育/品牌/学术）× 3 条件；覆盖管理层/专业受众对照（8 对不相交首选集合）、密度对照（con-b）、环境变化（fin-b/tech-b/gov-b/br-b）。
- 标签为维护者冻结（label_source: maintainer-authored-2026-09-08），不由推荐结果反推；preferred ⊆ acceptable，无全题通用风格。
- 旧推荐器（style_hard_rules.evaluate + current_family_members）两轮独立运行输出一致；3 题（br-mgmt/br-env/ac-den）零触发，按未命中如实记录；环境信号当前推荐器不消费。
- 完成线（U7 验收时）：Top-3 24/24、Top-1 ≥20/24、硬错为零、共同候选基线不退步。

## 七模板 21 页改前渲染基线

- 7 模板 × minimal/typical/near-capacity，Playwright 1.62.0 / Chromium 151.0.7922.34，2560×1440。
- `tests/fixtures/render-theme-baseline/manifest.json`：输入/输出 sha256、命令、源码与字体 hash、freeze 时 dirty 状态。
- 用途：解释重构差异。**不沿用旧方案 diff ≤0.001 作为新设计等价门。**
- 实测容量事实（改前 HTML 模板自身约束，供 U5 版式合同参考）：
  - body-basic：32px 要点，6 条单行以内（8 条或长句触发溢出哨兵）
  - spec-table：当前 HTML 约 6 行 × 6 列上限（8 行触发溢出；P25 sidecar 的 count_max=8 为 editable 原生表格口径）
  - pull-quote：引语字号 min(9.2vw,15vh)≈108px，两行以内（约 16–24 字）

## 校验命令

```sh
runtime/.venv/bin/python scripts/freeze_template_rebuild_baseline.py --check   # 账本漂移检测
runtime/.venv/bin/python scripts/freeze_render_theme_baseline.py --check       # 渲染基线漂移检测
runtime/.venv/bin/python -m unittest tests.test_template_recommendation_fixture tests.test_render_theme_baseline
```
