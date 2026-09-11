# Canonical HTML 渲染模板

这里是 render:html 的唯一模板真源。每个模板必须是一个独立目录：

```text
canonical/templates/<template-slug>/
├── page.html       # 1280×720 确定性 HTML 渲染入口
└── template.json   # template-v1 manifest，输入字段与依赖合同
```

运行时通过 `render page --template <template-slug>` 加载
`<template-slug>/page.html`。完整 asset id（例如
`builtin:template:body-basic`）也可作为模板 id 传入，运行时会归一化到同一个
canonical 目录；不会读取 `assets/render-templates/` 或其他旧目录。

模板入口先经 `AssetResolver` 校验 catalog 中的 manifest，再读取同目录的
`page.html`；HTML 路径必须留在可信库根内。`LEO_PPT_BUNDLE` 可以指定含
`template-library/library.json` 与有效 catalog 的完整 bundle；仅放置裸 HTML
不构成模板注册，也不能遮蔽已有模板。HTTP 只接受登记的 `<slug>.html` 入口，
不通过 `<slug>/page.html` 绕行。catalog 校验不替代下述模板代码审阅与视觉验收。

## 新增模板流程

1. **先确定页面职责**：明确 page role、内容容量、输入数据形状，以及复用的 layout profile。模板负责 HTML/CSS/数据投影；几何和容量真值放在 `canonical/layouts/<layout-slug>/layout.json`。
2. **建立配对目录**：创建 `canonical/templates/<template-slug>/page.html` 和 `template.json`。`asset_id` 必须是 `builtin:template:<template-slug>`，`lane` 必须是 `render:html`。
3. **实现 page.html**：遵守下方渲染合同；所有静态内容锚点使用 `data-leo-block`，动态重复项使用 `data-leo-block-item`。输入只从 `window.__LEO_SLIDE_DATA__` 和 `window.__LEO_THEME_VARIABLES__` 读取。
4. **填写 template.json**：
   - `input_fields` 描述真实输入字段、类型和 required；
   - `slot_bindings` 描述输入/结构槽到 DOM selector 的绑定；结构槽使用 `binding_kind: "structural"`；
   - `theme_roles` 列出模板实际消费的主题角色；
   - `layout_profiles` 至少绑定一个 `builtin:layout:*`，并在对应 `layout.json.renderer_support.render:html` 反向指向本模板；`dependencies` 同步列出该 layout。
5. **校验合同**：先运行模板目录级合同检查，再运行 HTML、layout、registry 检查：

   ```sh
   cd leo-ppt-generator
   runtime/.venv/bin/python scripts/lint_template_contract.py
   runtime/.venv/bin/python scripts/lint_render_templates.py
   runtime/.venv/bin/python scripts/lint_layout_grid.py
   runtime/.venv/bin/python scripts/capability_manifest.py --template-library --library-check
   ```

6. **补充测试与样张**：在 `tests/render/test_template_variants.py` 增加最小 payload；至少覆盖正常输入、容量边界和真实浏览器渲染。若新增枚举、主题角色或 layout 类型，同时补对应治理 schema/词表和测试。
7. **发布前验证**：执行 `bash scripts/ci_gate.sh`。catalog 是可重建产物；模板变更后用 `runtime/.venv/bin/python scripts/capability_manifest.py --template-library --library-publish` 更新 generation，再用 `--library-check` 复核。
8. **同步变更记录**：更新根目录 `CHANGELOG.md`，说明新增模板及其可观察影响。

## 模板渲染合同

1. deterministic 模式：识别 `?leo_render=1`，禁用 animation/transition。
2. ready 信号：字体与数据就绪后设置 `html[data-leo-ready="1"]`。
3. 数据注入：不得 `fetch` 外部数据；图表 SVG 必须来自注入数据并经过渲染侧清洗。
4. 字体：只使用 `/leo-fonts/` 本地 HTTP 供给，禁止 `file://` 和远程 CDN。
5. 画幅：根容器 `1280px × 720px`、`overflow:hidden`；渲染输出由 PNG 头校验。
6. 结构锚点：DOM selector 必须能命中真实 `data-leo-block` / `data-leo-block-item` 锚点。

当前 canonical 模板共 7 个：`cover-basic`、`body-basic`、`compare`、`timeline`、`spec-table`、`pull-quote`、`frame-shot`。
