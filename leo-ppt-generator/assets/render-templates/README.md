# render-templates：HTML 页渲染模板（D 柱 render lane）

`render page --template <id>` 从本目录加载 `<id>.html`（可选同目录
`<id>.css`）。模板是确定性渲染的输入合同——**模板不为截图设计则时序漏气**
（frontend-slides 教训），因此以下六条为 lint 强制（见
`scripts/lint_render_templates.py`，缺 ready 信号 = ERROR）：

## 模板合同（六条）

1. **deterministic 模式**：渲染器以 `?leo_render=1` 访问；模板须在该查询
   参数下禁用全部 animation/transition（建议模板自带
   `html[data-leo-render] * { animation: none !important; transition: none !important; }`
   兜底），且不注册 IntersectionObserver/scroll 等时序触发逻辑。
2. **显式 ready 信号**：字体与数据就绪后执行
   `document.documentElement.dataset.leoReady = "1"`。渲染器以
   `wait_for_selector("html[data-leo-ready='1']")` 为主门；模板缺该信号时
   渲染器回退 `document.fonts.ready + 800ms` 并记 WARN
   （`ready_signal_missing_fallback_wait`）——回退可渲染，但模板 lint FAIL。
3. **数据注入**：渲染器注入 `window.__LEO_SLIDE_DATA__`（slide JSON 原文）
   与 `window.__LEO_THEME_VARIABLES__`；模板只从该全局读数据，**不得
   fetch 外部资源**。`chart_svg` 槽内嵌 `render chart` 产出的 SVG 字符串
   （图表资产形态，见 references/render-contract.md）。
4. **字体**：`@font-face` 的 `src: url(/leo-fonts/<family>.<ext>)`——渲染器
   起本地 HTTP 服务从 `assets/render-fonts/`（及风格包字体目录）供给。
   **禁止 `file://` 直引**（headless 下字体静默失败）与远程 CDN 字体。
5. **画幅**：根容器 `width:1280px; height:720px`（逻辑像素）+
   `overflow:hidden`（禁止滚动条）；`device_scale_factor=2` 输出 2560×1440
   位图；渲染后读 PNG 头断言实际像素，不符 → `render_size_mismatch`。
6. **结构锚点**：内容容器带 `data-leo-block="<block-id>"`，供 E2 策划卡
   对账与 E5 渲染器感知 lint 使用。

## 现有模板

- `cover-basic.html` 封面：kicker / title / subtitle / footer 双栏。
- `body-basic.html` 正文：title / bullets 清单 / 可选 `chart_svg` 槽 / 页码。

## 版式映射（β 团队接口）

12_版式库 39 骨架 → 模板族的扩展由风格版式资产层（团队β）生产；新模板
必须满足上述六条并通过 lint：

```sh
python3 scripts/lint_render_templates.py   # ERROR 非 0 退出
```

跳过集/规则-渲染器映射见 `assets/render-lint-rules.json`；映射改动走
`scripts/style-lint-baseline.txt` 式白名单登记纪律。
