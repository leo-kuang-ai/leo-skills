# 版式调度合同（layout dispatch）

> 逐页版式匹配从「Agent 自由裁量」升级为「确定性打分 + 人工裁决 undecided」。
> 本文档是调度规则合同：四步链、打分口径、undecided 呈现格式、禁编造纪律、
> 与容量预检（B3）的衔接。打分器为无状态只读脚本
> `scripts/suggest_layout.py`；版式真值为
> `references/styles/12_版式库/*.layouts.json`（layout-bank-v1 sidecar，
> `"$LEO_PPT" style layouts` 可查，输出含 sha256 指纹）。

## 四步链

```
角色对齐 → 结构匹配 → 节奏感 → 置信度裁决
```

1. **角色对齐**：`deck_spec.slides[].page_role`（13_页面语义 25 角色）映射
   到版式 `page_type` 六值枚举（cover / agenda / section / content / data /
   closing），角色不符的候选直接出局（不参与打分）。未识别角色按中性
   0.5 评分（不硬排除）。数据点 ≥3 的页对非 data 版式减半。
2. **结构匹配**：页面侧 `{要点条数, 每要点预估字数, 数据点数, 图源数}`
   （母版内容行已有）对 sidecar `content_capacity`：
   - **区间包含度**：条数落在 `count_min/count_max` 区间内 = 1.0；不足
     按比例折减；超出但 ≤1.2 倍上限 = 0.5；硬超 = 容量分乘 0。
   - **字数覆盖度**：每要点预估字数（vw 视觉宽度）对最宽文本 slot 的
     `max_chars`（× 风格 `capacity_factor.text`）；装得下 = 1.0；
     ≤1.2 倍 = 0.5；硬超 = 容量分乘 0。
3. **节奏感**：`reuse_friendly=false` 且已用 → **硬排除**（与
   `scripts/check_layout_reuse.py` 同口径）；已用版式 -0.4；与上一页同
   版式再 -0.4；同 `page_type` 连续 ≥3 页应提示换型（人工判断项）。
   风格路由视图（`references/styles/<风格名>.layouts.json`）的
   `preferred` 命中 +0.1、`discouraged` 命中 -0.2——**风格层参与但不越权**
   （软权重，不构成硬排除）。
4. **置信度裁决**：top1 综合分 < 0.5 → 该页 `decision: "undecided"`。
   undecided 是合法结果不是失败。

## 打分公式（固定、可解释）

```
score = 0.45 × role_fit + 0.40 × capacity_fit + 0.15 × rhythm + 风格路由调整
```

- 各分量 ∈ [0, 1]，总分封顶 1.0；超容量候选 `capacity_fit = 0`。
- 输出逐候选带 `reasons`（如 `角色对齐:对比·多维`、`容量 120/183 chars`、
  `已用版式 -0.4`），人可复核。

## 用法

```text
python3 scripts/suggest_layout.py <pages.json> [--style <风格名>]
cat pages.json | python3 scripts/suggest_layout.py
python3 scripts/suggest_layout.py --json-schema   # 输入 schema 自校验
```

输入 `pages[]` 每页：`page`（页号）、`page_role`（必填）、`points`（要点
条数）、`est_chars`（每要点预估 vw 字数）、`data_points`、`image_sources`、
`already_used`（本 deck 已用版式 P 码列表）、`previous_layout`。输出键排序、
确定性、无时间戳；同输入两次运行逐字节一致。

退出码（CI-4）：0 = 正常产出（auto 与 undecided 均合法，undecided 不打 1）；
2 = 输入 schema 错误或脚本防御断言触发。

## 禁编造版式 id（纪律）

候选 id 只能来自 sidecar 枚举集（`P1`–`P36`，`"$LEO_PPT" style layouts`
或 `style render --list-templates` 可枚举）。用户要求不存在的版式（如
「时间瀑布版式」）时：引用真实枚举 id 给近似候选，或输出 undecided 交人工；
**绝不编造**非枚举 id。打分器对输出 id 做枚举集防御断言（触发即脚本 bug，
exit 2）；评测对 agent 回复中的非枚举版式名做否定感知拦截。

## undecided 的母版呈现格式（寄生既有母版确认，不新增确认门）

母版文档中 undecided 页的视觉行按固定格式呈现：

```text
第 <页号> 页版式待定：候选 <P码A> 或 <P码B>，理由 <打分器 reasons 摘一行>。
```

- 待定行就在既有母版确认交互里被人工裁决（CI-5：确认点数量不变）；
- 每个待定页给恰好 2 个候选（打分器输出 top 2）；
- 用户不裁决不得静默任选落版式。

母版视觉行节同时声明：版式选择可由 `suggest_layout.py` 预打分（见
`deck-master.md` 视觉行）。

## 与容量预检（B3）的衔接

调度环产出候选后、落版式前，对要点文本跑生成前容量预检：

```text
python3 scripts/check_deck_geometry.py --capacity <deck_spec/master JSON>
```

- 三态：`ok`（exit 0）/ `over` 软超 ≤1.2×（exit 0 + WARN 行）/ `overflow`
  硬超 >1.2×（exit 1 阻断定稿）。
- **硬超处置：先降档（论点页 ≤3 → ≤2）或换版式，再回到匹配环重跑
  `suggest_layout.py`**；绝不缩字号（同级字号一致铁律 + 版心Canon 字阶
  刻度离散表）、绝不省略号截断（max_chars 是软参考不是截断线）。
- 软超不占退出码（2 语义保留给用法错误），以输出行区分三态。
- 与交付后 visual_qa 像素断言的职责分界：本预检是**生成前文本级**，
  visual_qa 是**交付后像素级**；一个防患一个兜底，不重复。

## page_type 映射表（36 版式治理字段汇总）

| page_type | 版式 |
|---|---|
| cover | P1 |
| agenda | P32 |
| section | P3, P10, P12, P23 |
| content | P4, P5, P8, P11, P13, P14, P15, P16, P17, P19, P22, P26, P27, P28, P29, P30, P31, P33, P34 |
| data | P2, P6, P7, P18, P20, P21, P24, P25, P35 |
| closing | P9, P36 |

`reuse_friendly=false`（强视觉锚点，一 deck 受 `max_per_deck` 限制）：
P1、P9、P23、P24、P34（上限 1）与 P36（上限 2）。定稿前跑
`python3 scripts/check_layout_reuse.py <deck_spec.json>` 机器复核。
