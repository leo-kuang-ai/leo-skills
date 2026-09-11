# 版式调度合同（layout dispatch）

> **整册分配（dashi 集成 K5/U5）**：canonical layout 携带受 schema 约束的
> `structure` 声明（阅读顺序/分组关系/图表编码，不含主题、文案、评分或第二
> 套几何）；结构指纹经版本化规范化——资产重命名不变，顺序/分组/编码改变即
> 变，缺声明记 `unknown` 不获得多样性加分。母版内容包驱动的整册分配由
> runtime `layout_selection.allocate_deck` 完成：内部保留**完整合格候选池**
> （硬资格：角色/容量/媒体/backend/必需覆盖），确定性有界搜索满足禁复用与
> `max_per_deck`（仅对 `reuse_friendly=false` 生效，普通版式可复用），预算
> 耗尽与无候选分别报告；Top-2 仅是面向人的推荐摘要。准入集合由
> `scripts/capability_manifest.py --template-library` 的 `structure_admission`
> 从 canonical 声明派生；缺少结构声明记 unknown。数量随 catalog 更新，
> 以当次派生输出为准，不另存手写名单，HTML 绑定数量不等于自动准入数量。

> 逐页版式匹配从「Agent 自由裁量」升级为「确定性打分 + 人工裁决 undecided」。
> 本文档是调度规则合同：四步链、打分口径、undecided 呈现格式、禁编造纪律、
> 与容量预检（B3）的衔接。打分器为无状态只读脚本
> `scripts/suggest_layout.py`；版式真值为
> `template-library/canonical/layouts/*/layout.json`（layout-profile-v1，
> `"$LEO_PPT" style layouts` 可查，输出含 sha256 指纹）；风格路由来自同一
> style brief 的 `bindings.layout_routes`。

## 四步链

轻量推荐已知执行路线时传 `--backend render:html` / `--backend image`，
或在输入顶层声明 `backend`。未声明对应 `renderer_support` 的版式在评分前
排除，无合格候选返回 `undecided`，不自动换成通用模板。输出携带实际绑定。
未传 backend 保留跨路线探索，明确标记 `capability_check: not_requested`，
不能视作渲染可实现性预检。正式生成仍须经过 content_projection 的内容资格校验。

```
角色对齐 → 结构匹配 → 节奏感 → 置信度裁决
```

1. **角色对齐**：`deck_spec.slides[].page_role`（13_页面语义 25 角色）映射
   到版式 `page_role` 七值枚举（cover / agenda / section / content / data /
   quote / evidence / closing），角色不符的候选直接出局（不参与打分）。未识别角色按中性
   0.5 评分（不硬排除）。数据点 ≥3 的页对非 data 版式减半。
2. **结构匹配**：页面侧 `{要点条数, 每要点预估字数, 数据点数, 图源数}`
   （母版内容行已有）对 canonical profile 的 `slots`：
   - **区间包含度**：条数落在 `count_min/count_max` 区间内 = 1.0；不足
     按比例折减；超出但 ≤1.2 倍上限 = 0.5；硬超 = 候选直接排除（dashi U1）。
   容量预检的人工/agent 选页通道：`leo-ppt style layouts --capacity "槽名<=N"`
   只读过滤（计数槽按 `count_max`、文本槽按 `max_chars`），档位速查见
   `template-library/governance/rules/layouts/00_容量档位参考.md`。
   - **字数覆盖度**：每要点预估字数（vw 视觉宽度）对最宽文本 slot 的
     `max_chars`（× 风格 `capacity_factor.text`）；装得下 = 1.0；
     ≤1.2 倍 = 0.5；硬超 = 候选直接排除（返回 undecided 与原因）。
3. **节奏感**：`reuse_friendly=false` 且已用 → **硬排除**（与
   `scripts/check_layout_reuse.py` 同口径）；已用版式 -0.4；与上一页同
   版式再 -0.4；同 `page_type` 连续 ≥3 页应提示换型（人工判断项）。
   风格 brief 的 `bindings.layout_routes` 中的
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

候选 id 只能来自 resolver 枚举集（当前含 P1–P36 与 HTML lane 的命名别名，
`"$LEO_PPT" style layouts` 或 `style render --list-templates` 可枚举）。用户要求不存在的版式（如
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
- 共创时用户不裁决不得静默任选；委托执行可按既有授权在母版审查节点裁决并记录依据，
  但推荐本身仍为 undecided，必须完成独立容量与实际样张检查才能定稿。

母版视觉行节同时声明：版式选择可由 `suggest_layout.py` 预打分（见
`deck-master.md` 视觉行）。

## 与容量预检（B3）的衔接

### 实际作用域与强制出口

先读取选定风格的 summary 并核对同一 home/selection_fingerprint。仅当实际 source 为随包风格，
且真实同名路由存在时，才用该路由的 preferred/discouraged/capacity_factor。user 同名覆盖没有专属绑定时，
**调度与容量预检两次都去掉 style 名称**，使用通用 layout-bank；报告“仅通用布局，风格适配待样张”，
不使用同名 builtin 的配对渲染、预览或容量因子，也不建立新的用户 sidecar 搜索体系。

`suggest_layout.py` 的 `decision=auto` 只表示综合候选分达到阈值，不代表容量已通过。
两次检查必须保持同一页的文本与要点粒度；一个长要点不能改成大量单字要点。固定文本槽版式还检查 points 总量，避免无限复用最宽槽；定稿应显式映射 slots。
硬超候选在推荐层即被排除（无合格候选返回 undecided 与具体原因）；独立容量预检仍须执行——显式指定同样不能绕过几何闸。
独立检查的 overflow 无条件阻断该页定稿，不能因 auto、用户催促或之前样张通过而忽略。
未知 P 码、空版式库或缺少容量字段时报告缺口，不伪造风格专属支持。

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

### 样张继承

source_digest 只判断目录同步；style_content_digest 判断实际读取内容；layout_binding_digest
由实际使用的路由/版式和容量因子组成，无绑定为未记录。三者不等于样张接受状态。
仅 source/taxonomy 改动且视觉投影、实际绑定与生成方法不变时，核验后保留既有样张；
视觉、绑定、backend、尺寸或生成方法变化时，回既有视觉方向/样张门重确认。
旧 run 缺历史 digest 不视为相等，可回读其冻结材料核验；材料缺失则报告，不自动重写成品。
依据放在现有母版 engineering 与 qa_note，禁止把索引/选择元数据放进 deck_spec.style 或最终图片 prompt。

## page_type 映射表（36 版式治理字段汇总）

| page_role | 版式 |
|---|---|
| cover | P1 |
| agenda | P32 |
| section | P3, P10, P12, P23 |
| content | P4, P5, P8, P11, P13, P14, P15, P16, P17, P19, P22, P26, P27, P28, P29, P30, P31, P33, P34 |
| data | P2, P6, P7, P18, P20, P21, P24, P25, P35 |
| closing | P9, P36 |

`reuse_friendly=false`（canonical profile 中的强视觉锚点，一 deck 受 `max_per_deck` 限制）：
P1、P9、P23、P24、P34（上限 1）与 P36（上限 2）。定稿前跑
`python3 scripts/check_layout_reuse.py <deck_spec.json>` 机器复核。
