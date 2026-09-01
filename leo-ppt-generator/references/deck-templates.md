# deck 模板（R-50：结构资产复用 + 数据点指纹 diff）

> 周报/月报等周期性 deck 的结构复用通道：把**已确认 deck** 的母版骨架存为
> 模板，下期新材料到来时以模板预填草案，母版定稿后用数据点指纹做
> 沿用/新增/缺失 diff。执行脚本 `scripts/deck_template.py`（确定性、纯
> stdlib、exit 0/2）。

## 与交付档案（profiles）的差异

| | 交付档案 `${LEO_PPT_HOME}/profiles/<名>.md` | deck 模板 `${LEO_PPT_HOME}/deck-templates/<名>/` |
| --- | --- | --- |
| 存什么 | 内容合同**偏好字段**（audience/scenario/page_count_policy/duration/data_classification_default/density/preferred_style） | **结构资产**：页序 + 每页版式 P 码 + argument_role 序列 + 页数合同 + 风格合同引用 + 数字登记表**列结构** |
| 何时用 | generate 步骤 1 内容合同预填 | 已确认 deck 的下期复用（instantiate 草案 + diff-data 复核） |
| 业务数据 | 绝不存 | **模板本体绝不存**（登记表数据行、页面标题/要点均剥离）；实例登记（instances.jsonl）只存**数据点指纹**（归一化数值键+首见显示串），非登记表数据行 |
| 确认语义 | 不豁免数据分级与答辩档位确认 | **不豁免任何门**（见下节红线） |

两者同构于 `styles/`、`brands/` 的用户档案通道，互不替代：档案管"这份
合同怎么填"，模板管"这份 deck 的骨架长什么样"。

## 确认语义红线（不可交易）

**diff 式确认只减少呈现项，不减少确认门。**

- 下期 instantiate 后的确认序列照常走：合同→大纲→母版→样张→数据分级，
  每期照常逐件确认；模板不豁免任何门。
- diff 报告（沿用/新增/缺失）只是**呈现层的差异摘要**——沿用项不等于
  免确认，缺失项进材料确认清单后须逐项与用户确认保留或放弃。
- 与 BR-002 一致：减少的是往返次数（骨架不用重搭），不是确认点。
- 此红线写死在 `deck_template.py` 每条命令的输出里（`confirm_semantics`
  字段），不可通过参数关闭。

## 命令

```sh
# 在技能目录内执行；<home> 为 LEO_PPT_HOME 根目录（或已设环境变量）

# 1. 把已确认 deck 存为模板（唯一合法来源：<project-root>/content/ 的
#    confirmed 母版基线，含 post-confirm 修订链；无 confirmed 基线 exit 2）
python3 scripts/deck_template.py save <project-root> --name N --home <home>

# 2. 以模板产出新项目 content/ 草案，并登记本期材料的数据点指纹
python3 scripts/deck_template.py instantiate N --data <新材料.md> \
    --out <新项目根目录> --home <home> [--json]

# 3. 母版定稿后对照实例指纹 diff（沿用/新增/缺失）
python3 scripts/deck_template.py diff-data N <新材料母版.md> \
    --home <home> [--json]
```

退出码统一：0 成功；2 用法错误 / 模板不存在 / 无 confirmed 基线 /
文件不可读或不可解析。

## 模板目录结构

```text
${LEO_PPT_HOME}/deck-templates/N/
├── template.json    # 结构资产（无业务数据）：pages[{page_id,
│                    #   argument_role, layout}], page_contract, style_ref,
│                    #   ledger_columns, confirm_semantics
└── instances.jsonl  # 实例登记（追加写）：每行一个实例的数据点指纹
```

- `template.json` 不含时间戳与绝对路径，同输入同字节（save 确定性）。
- 重复 `save` 覆盖 template.json 并保留 instances.jsonl；页序合同变化时
  打 WARN（指纹按数值键比对，不受页序影响）。
- 重复 `instantiate` 同一材料幂等：不追加重复实例记录，草案字节不变。
- 删除模板目录即清除全部结构资产与指纹登记（随 LEO_PPT_HOME 数据目录
  管理，不入技能同步面）。

## 数据点指纹与三分类 diff

- **指纹**：数据点 = 归一化数值键（同构 `check_content_facts.py` 的
  数字抽取：千分位/万·亿/%/‰/百分之 归一为 `num:<值>` / `pct:<值>`，
  "1.24 亿"与"12400 万"同键）；附首见显示串与可选页位。母版侧优先从
  `## 数字登记表` 数值列取（登记表是数字元数据单源），无登记表时按
  assertion 文本抽取；材料侧按全文数值抽取（同 material_number_keys）。
- **三分类**（基线 = 最近一次实例登记的指纹，即本期新材料）：
  - **沿用**：基线与母版都有的数据点（材料数据进入了母版）；
  - **新增**：仅母版有（会话口述/推断数据——核对是否该标"用户确认"
    或降级示意）；
  - **缺失**：仅基线有（材料数据点未进入母版）——逐项进材料确认清单，
    由用户确认保留或放弃，不得静默丢弃。
- 上期实例指纹在 instantiate 草案中列为"沿用候选"（数据连续性：上月
  口径 vs 本月靠机器 diff 而非人记忆）。

## 边界

- 模板不触发任何自动生成：instantiate 产出的是 `confirmation: pending`
  草案（骨架预填 + 指纹清单），内容仍由 generate 路线完整制作与确认。
- 不存平台凭据、不代发（分发边界见
  [`execution-contract.md`](execution-contract.md) 交付节）。
- 样式不锁定：`style_ref` 只是上期风格合同引用，本期可改，改后走完整
  风格确认流程。
