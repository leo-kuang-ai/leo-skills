# 渲染 lane 合同（render contract，gamma M1）

确定性渲染 lane 是与图像模型并列的第二类页产物来源：图像模型管视觉创意页
（封面/概念/氛围），确定性渲染接管正确性合同最重的页型（数据图表/表格/
文字密集）。路由判定与确认点见
[`backend-selection.md`](backend-selection.md) 渲染 lane 节；本文件是机器
侧合同的单一定义处。

## 1. CLI 与 envelope

全部输出走 `leo-ppt-machine/v1` versioned JSON envelope（CLI 真值红线）。

```bash
"$LEO_PPT" render ready --json                       # 三态探测（doctor 分面同源）
"$LEO_PPT" render page --template <id> --data <slide.json> \
    --out slide_N.png --size 2560x1440 [--timeout 60] [--theme-file <theme.json>]
"$LEO_PPT" render chart --dialect mermaid \
    --source <11_图表语法/*.md | --code-file <code.mmd> \
    --out chart_N.svg [--png chart_N.png] [--theme-file <theme.json>] [--scale-width 2560]
```

- 成功 reason code：`render_page_completed` / `render_chart_completed`；失败走
  [`reason-codes.md`](reason-codes.md) 渲染 lane 节（`blocked` → exit 2）。
- `--size` 缺省 2560x1440（逻辑画幅 1280×720 × deviceScaleFactor 2）；实现
  读 **PNG 头**断言实际像素（不信 CLI 参数），不符 → `render_size_mismatch`
  且不产出。
- `render chart --source` 抽取 ```` ```mermaid-example ```` fenced 块（多块取
  第一块并 WARN 计数）；无块/空块/语法失败 → `render_data_invalid`。
  **11_图表语法 中的示例数字仅为语法演示，渲染前必须替换为 approved 真实数据。**

## 2. backend 枚举与 provenance sidecar（CI-1）

render 产物仍是 `mode=image` 页图（不新增 mode）。backend 字符串枚举：

| backend | 来源命令 | 说明 |
| --- | --- | --- |
| `render:html` | `render page` | HTML 模板整页渲染 |
| `render:mermaid` | `render chart --dialect mermaid` | 浏览器实例内 mermaid |
| `render:echarts` | `render chart --dialect echarts`（P2，未落地） | 占位枚举 |

每次渲染成功在产物旁写 `<out>.render.json`（schema v1，`kind=
render_provenance`）：`backend / template_id / template_sha256 / data_sha256 /
dialect / renderer / out / out_sha256 / width / height / rendered_at / warnings`。

`image record --render-receipt <path>` 消费 sidecar：校验 `out_sha256` 与被
record 的产物逐字节一致、backend 与 `--backend` 一致后，把 sidecar 并入该页
slide entry 的 `provenance` 字段（与图像模型产物的 backend/hashes 同构；
provenance 留在 slide_jobs entry 层，不动 PageArtifact schema）。sidecar
不可手改——手改后 sha 不匹配即 `render_receipt_invalid`。

`backend_tokens` 对 render backend **恒为 `not-recorded`**（确定性渲染无
token 成本）；`backend report` 的 token 聚合把 render 行单独看待，不混入
图像模型成本。

## 3. 模板合同（七条）

模板目录 `template-library/canonical/templates/`（每模板 `<id>/page.html`；合同与 lint 见
目录 `README.md`、`scripts/lint_template_contract.py` 与 `scripts/lint_render_templates.py`，缺 ready 信号 =
ERROR）：deterministic 模式（`?leo_render=1` 禁动画）、`data-leo-ready`
显式就绪信号（渲染主门；缺失 → `document.fonts.ready + 800ms` 回退并 WARN
`ready_signal_missing_fallback_wait`）、数据只读 `window.__LEO_SLIDE_DATA__`
（渲染器以 add_init_script 在页面脚本执行前注入——注入晚于模板脚本是
"干净空页"竞态，只有像素闸门能抓住）、字体经 `/leo-fonts/` HTTP 供给
（**禁 `file://` 与远程 CDN**）、根容器 1280×720 + `overflow:hidden`、
内容容器带 `data-leo-block` 锚点、**溢出哨兵**（加固方案 WS3）：截图前
对全部 `data-leo-block` 做确定性越界断言——块矩形必须完整落在逻辑画幅
（±1px 容差）内，且自身裁剪（overflow hidden/clip）的块内容不得超出其盒；
越界 → `render_overflow` 拒产（不留 PNG），sidecar 记 `overflow_check`。
`LEO_PPT_RENDER_OVERFLOW=warn` 降级为观察模式（sidecar 记
`overflow_observed` 警告并照常产出，供存量模板回归摸底）；`=off` 完全关闭
哨兵（诊断逃生口，交付披露须注明哨兵未运行）。装饰性出血
（overflow visible 的合法溢出，如 pull-quote 巨引号）不触发哨兵。

字体 HTTP 服务的工程要点（本地 HTTP server 供字体、`networkidle` +
`document.fonts.ready` 等待）改编自 frontend-slides `scripts/export-pdf.sh`
（MIT；upstreams.yaml 登记）；其"四段魔法等待"反面教训即 ready 信号合同的
动机。

R-28 扩面模板（槽位语义对齐 `template-library/canonical/layouts/*/layout.json`
对应 P 码 profile；模板实现仍在 `template-library/canonical/templates/`）：

- `spec-table.html` 规格参数表（P25）：`columns`/`column_align`/`rows`，
  表头角色底色 + 斑马纹行 + 数值列右对齐。
- `timeline.html` 横向时间线（P11）：`steps`（4-7 节点），1px 横轴 + 均布
  直角方块节点 + 上编号下步骤名。
- `compare.html` 双轨对照（P8）：`sides`（恰 2 项），中央 1px 纵线，两侧
  同构 label + 大字标题 + 要点。
- `pull-quote.html` 大引语（P34）：`quote`/`source_name`/`source_meta`，
  垂直居中引文 + 出处块，留白 ≥40%。
- `frame-shot.html` 证据截图框架（R-32，guizang `.frame-shot` 六参数移植）：
  `ratio`（7 档：16x10 缺省/16x9/4x3/3x2/1x1/3x4/21x9）/ `corners`
  （sq/sm=6px/md=14px，**上限 14px**）/ `shadow`（none 缺省/soft/ed 带 1px
  outline 留 hero）/ `bg`（paper/paper-2/grey-1/grid/dot/ink——舞台**永不
  accent 着色**，要强调加 kicker 不染底）/ `inset`（none/sub=20px 缺省/
  bal=48px）/ `fit`（contain 缺省是组件的全部意义，cover 仅显式覆盖）+
  `device` 包装（none 缺省/browser=chrome 条/phone=墨色 bezel，phone 强制
  sq 圆角防双圆角）+ `image_src`（**仅 data: URI**，远程/file 路径拒绝加载）
  + kicker/title/caption/页码；**正交纪律：禁透视/倾斜/旋转/3D tilt**——
  直 subject、等比缩放、安静背景、清晰安全边距；对比图（before/after）
  用相同参数。路由：**页面含证据截图（Demo/看板/代码证据）优先走渲染 lane
  本组件**，图像模型截图页是高废片页型。

## 4. mermaid 运行时与 themeVariables 映射（D2）

mermaid 以本地 pinned 单文件 vendored：
`assets/render-vendor/mermaid/mermaid.min.js`（mermaid@11.17.2，MIT，sha256
锁进 `vendor-lock.json`），浏览器实例内 `mermaid.initialize({startOnLoad:
false})` → `mermaid.render` → SVG，不走 CDN。

deck colors 锚 → mermaid themeVariables 映射（初始 8 键 + xyChart 域补充；
`--theme-file` 输入，锚侧接受常见命名，未命中用 mermaid 默认并 WARN）：

| mermaid 键 | 锚（按序取首个命中） |
| --- | --- |
| `primaryColor` | `primary` / `accent` / `accent_color` |
| `primaryTextColor` | `on_primary` / `text_on_primary` / `primary_text` |
| `primaryBorderColor` | `primary_border` / `border` / `line` |
| `lineColor` | `grid_line` / `line_color` / `axis_line` |
| `secondaryColor` | `secondary` / `secondary_color` |
| `tertiaryColor` | `tertiary` / `tertiary_color` / `surface` |
| `mainBkg` | `background` / `bg` / `canvas` |
| `fontSize` | `font_size` / `base_font_size`（数值自动加 px） |
| `xyChart.plotColorPalette` | `primary` / `accent` / `accent_color` |
| `xyChart.backgroundColor` | `background` / `bg` / `canvas` |
| `xyChart.titleColor` | `on_primary` / `title_color` / `primary_text` |

xyChart 域是补充映射：xychart 系（折线/柱状）不消费全局 `primaryColor/
mainBkg`，主色走 `themeVariables.xyChart.plotColorPalette`。验收口径：
有 theme 时主色 hex 必须可在 SVG 内 grep 到。

图表与页面的组装两形态：**图表资产形态**——SVG 字符串进 `render page`
模板的 `chart_svg` 数据槽（`body-basic` 已支持），整页由 D1 出图，数值/
单位/标签经 mermaid 原生渲染 100% 逐字保真；**纯图形态**——`--png` 直接
出图，作为 strict input asset 给图像 lane 风格化合成（与 diagram_render.py
同通道，此时它是输入而非终稿）。

## 5. SVG → PNG 栅格化（D3，resvg）

- 首选 Python 绑定 `resvg-py`；备选 Node `@resvg/resvg-js` 独立子进程
  `scripts/render/rasterize_svg.mjs`（stdin/stdout 一行 JSON 协议隔离，
  **永不进 PPTX 组装路径**，CI-6）；双路径皆不可用 →
  `rasterizer_unavailable`。
- 确定性参数：`skip_system_fonts=true`（或 Node `loadSystemFonts:false`）+
  显式 `font_files/font_dirs`（`assets/render-fonts/` + 风格包目录，经
  `LEO_PPT_RENDER_FONT_DIRS` 追加）+ `fitTo width` + 显式背景色。
  **禁止 patch resvg 源码**（MPL-2.0 合规：仅二进制依赖使用，NOTICE 登记）。
- 同输入两次栅格化 `out_sha256` 必须相等（进 tests/render 断言）。

## 6. 确定性承诺分层（防过度承诺）

| 链路 | 承诺 | 断言方式 |
| --- | --- | --- |
| SVG → resvg（含 mermaid SVG 本体） | **位级一致**（sha256 逐字节相等） | 单测 + evals |
| HTML → playwright 截图 | **像素 diff ≤ 容差**（跨版本抗锯齿微差不承诺位级） | 同输入两次渲染 ImageChops diff |

宣称渲染确定性时必须按本表分层表述；对 HTML lane 宣称"位级一致"是过度承诺。

## 7. readiness、字体与缓存

- `render ready` 三态：`render_backend_ready / render_backend_missing /
  render_backend_unknown`（组件在场但启动探测不可判）。不套用 Provider
  三态（无凭据概念）。missing 时路由提议被抑制并披露，图像 lane 不受影响。
- chromium 缓存固定 `$LEO_PPT_HOME/render-browsers/`（`PLAYWRIGHT_BROWSERS_PATH`
  注入；用户已有 `PLAYWRIGHT_BROWSERS_PATH` 不覆盖）；`LEO_PPT_RENDER_CHROMIUM`
  显式覆盖 executable。
- 离线字体：`assets/render-fonts/`（Noto Sans SC 子集，OFL-1.1，目录内
  NOTICE/LICENSE 登记）；缺字 WARN 并回退 defaultFontFamily，**不静默换系统
  字体**（跨机器非确定）。doctor 的 render 分面默认跳过真实启动
  （`LEO_PPT_RENDER_DOCTOR_LAUNCH=1` 打开），启动级真值以 `render ready` 为准。

## 8. worker 容错与清扫（E4）

- 三层容错协议（阶段分层重试 ≤3/页、清扫 ≤2 轮、已 rendered 页无条件跳过）
  文本见 `prompts/render-worker.md` / `prompts/slide-worker.md`。
- 机器化清扫：`"$LEO_PPT" image sweep <run> --max-rounds 2 [--dry-run]`——
  dry-run 输出非 rendered 页复位计划（含 attempts 统计与建议动作）；apply
  复用既有 `Lifecycle.reset_failed_pages()`（只复位 failed/blocked/timeout
  页，recorded 页不动），轮次记 `<run>/observability/render-sweep.jsonl`，
  超上限拒绝（`render_sweep_rounds_exhausted`）。

## 9. 渲染器感知 lint（E5）

规则-渲染器映射的机器可读定义：`assets/render-lint-rules.json`（`template.*`
规则由 `scripts/lint_render_templates.py` 消费；`grid.slot_alignment` 等页级
规则按 slide_jobs 的 backend 来源判定，图像模型页自动 skip 并输出
`skipped_rules` 披露——presentation-skill `layout_lint.py` 跳过集思想，
upstreams.yaml 登记）。跳过集改动走 `style-lint-baseline.txt` 式白名单登记。

## 10. 许可与来源

vendored/借源登记：mermaid（MIT，vendor-lock.json pin）、Noto Sans SC 子集
（OFL-1.1）、resvg-py（MPL-2.0，NOTICE 专项）、ppt-agent-skill visual_qa
检查族（MIT，`scripts/visual_qa.py` 头注署名）、frontend-slides（HTTP 字体
机制）、presentation-skill（跳过集思想）、codex-slides（容错常量思想）、
OpenCanvas PROMPTS_REGISTRY（registry 结构）。完整登记见包根
`upstreams.yaml` 与 `NOTICE`。

## 11. 导出目标（handout-PDF / 长图，R-47 首批）

```bash
python3 scripts/export_deck.py <pages_dir> --format handout-pdf [--output <p>] [--json]
python3 scripts/export_deck.py <pages_dir> --format long-image   # 参数同上
```

- 输入为逐页 PNG 目录（如 `image-deck/origin_image`）：目录含 `pages.json`
  索引则按其排序，否则按文件名自然排序（数字段按整数比较；统一
  `前缀+数字+后缀` 命名族缺号判 missing）。carousel 不在本批。
- 确定性合同：同输入双跑产物 sha256 逐字节相等——Pillow PDF 默认写入的
  `CreationDate/ModDate` 墙钟已被显式置空，PNG 无时间戳 chunk；逐页像素
  分辨率保持原样（PDF 页尺寸按 PNG dpi，缺省 72）。
- 三态回执（E5-11）：`--json` 输出 started/completed/failed JSON Lines，
  含产物路径、sha256、页数、失败页清单（missing/corrupt）；exit 0/1/2。
  失败页必须如实列出，不得声称全部导出。
- 导出属交付动作：产物路径与回执并入交付披露，导出前须过
  `delivery receipt verify`（execution-contract.md 交付节）；导出产物指纹
  并入收据五类指纹属后续批，本批不改写收据。

## 12. 风格 token sidecar 与 `--var` 覆盖（R-27）

brief JSON 块可选 `token_sidecar` 键（schema `style-brief-v1.schema.json`，
纯增量）：`palette`（核心键 `primary`/`accent`/`background`/`surface`/
`text`，对齐 H 线 `samples/style-gallery/*/theme.json` 渲染锚，可按
social-card 8 token 先例扩展键名；值一律纯 `#RRGGBB`）+ `typography`
（字符串）+ `density`（字符串）+ `layout`（五字段版式锚源，供 §13
`--layout-lock` 消费）。`palette` 可选 `chart_smart` 槽（源 presentation-ai
smartLayout 七语义槽）：金字塔/饼图/阶梯/循环/时间线等 smart 图解结构的
专用填充色，取 primary 近邻或其变体；与卡面 `surface`、图表数据系列色序
（弹药池 `scripts/chart_palette_pool.py`）三分各司其职。`leo-ppt style render <风格> --var key=value`
（可重复）在本面覆盖：键为点路径（`palette.accent` / `typography.title` /
`density`），键不存在或值非法 → `style_var_override_invalid`（exit 2）。
覆盖 `primary`/`text`（≥4.5:1，正文口径）或 `accent`（≥3:1，大字/非文本
口径）时，对生效 `background`（缺省 `#FFFFFF`）复用 brand_contrast 同一
WCAG 实现与最近合规建议算法做硬校验，不足同样返回
`style_var_override_invalid`（附对比度说明——reason_code 统一折叠，
reason-codes.md 按实现口径登记）；覆盖 `background` 时对三者全量重查。
**不带 `--var` 时输出逐字节不变**（回归断言在 tests/test_style_render_options.py）；
例外：brief 自带 `token_sidecar` 时该键随 brief 输出面透传（brief 文件变更
即输出变更，属 brief 版本化公告范畴，非 --var 破线）；`--color` 仍作用于散文
`color_palette`，两者是分离的面、互不改写。多页样张确认后的跨页继承字段
清单与用户原图「保真 vs 风格化」政策声明归 `references/style-continuity.md`。

## 13. 版式系统锚 `--layout-lock`（R-31）

`leo-ppt style render <风格> --layout-lock` 输出追加确定性版式锁定块
`layout_lock`（list[str]，逐页逐字节相同注入，防网格/页码/边距漂移——
xhs-visual-director 母版锁定前缀的 prompt 侧前置，与静态属性锚
`style_anchor` 分层："颜色字体不漂"归 anchor，"网格页码不漂"归本锚）：

```json
"layout": {
  "grid": "12 列 × 24px 槽",
  "safe_margin": "80px 100px 72px",
  "page_no": "右下 right:44px bottom:30px",
  "corner_radius": "0px（直角）",
  "line_weight": "1px 分隔线"
}
```

- 读取源：`token_sidecar.layout` 键**优先**（生效 token 面，与 palette
  同序），brief JSON 块顶层 `layout` 键降级；五字段（grid / safe_margin /
  page_no / corner_radius / line_weight）全部为非空字符串才注入。
- 失败路径：两处皆无 `layout` 键、或任一字段缺失/空白 →
  `layout_lock_unavailable`（exit 2，报错指明缺字段，**不静默降级**——
  半锁等于放行漂移）。
- 字节红线：**不带旗标输出逐字节不变**（回归断言在
  tests/test_style_render_options.py）；与 `--var`（palette 面）、
  `--anchor`（静态属性面）正交可组合，互不改写。
