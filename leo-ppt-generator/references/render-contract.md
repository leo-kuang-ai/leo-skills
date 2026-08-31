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

## 3. 模板合同（六条）

模板目录 `assets/render-templates/`（每模板 `<id>.html`；合同与 lint 见该
目录 `README.md` 与 `scripts/lint_render_templates.py`，缺 ready 信号 =
ERROR）：deterministic 模式（`?leo_render=1` 禁动画）、`data-leo-ready`
显式就绪信号（渲染主门；缺失 → `document.fonts.ready + 800ms` 回退并 WARN
`ready_signal_missing_fallback_wait`）、数据只读 `window.__LEO_SLIDE_DATA__`
（渲染器以 add_init_script 在页面脚本执行前注入——注入晚于模板脚本是
"干净空页"竞态，只有像素闸门能抓住）、字体经 `/leo-fonts/` HTTP 供给
（**禁 `file://` 与远程 CDN**）、根容器 1280×720 + `overflow:hidden`、
内容容器带 `data-leo-block` 锚点。

字体 HTTP 服务的工程要点（本地 HTTP server 供字体、`networkidle` +
`document.fonts.ready` 等待）改编自 frontend-slides `scripts/export-pdf.sh`
（MIT；upstreams.yaml 登记）；其"四段魔法等待"反面教训即 ready 信号合同的
动机。

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
