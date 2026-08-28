# Leo Studio DESIGN.md

> 设计系统快照（Google Stitch DESIGN.md 格式）。供人类与 AI 编码代理共同消费：任何新生成的界面都应能仅凭本文件还原视觉与交互一致性。
> 谱系：壳层（导航 / 仪表盘 / 设置）= Apple 官网风；工位层（写作 / PPT / 任务运行）= Linear 式专业工具密度与动效。

## 1. Visual Theme & Atmosphere

- **双面性格**：对外呈现 Apple 式的克制、留白与大型排版；进入工位后切换为 Linear 式的高信息密度、键盘优先、状态即时可见。
- **关键词**：可信（trust）、可审计（auditability）、果断（decisiveness）。界面不装饰事实——颜色只表达语义（状态 / 证据类别 / 风险），不做纯装饰。
- **密度**：壳层疏松（版心 1024px，区块 56-88px 呼吸）；工位层紧凑（12px 网格，面板内 8-10px 间距）。

## 2. Color Palette & Roles

```css
:root{
  /* 表面（壳层） */
  --bg:#ffffff; --bg2:#f5f5f7;            /* 交替分区底色 */
  --surface:#ffffff; --hairline:#e8e8ed;  /* 卡片、1px 分隔 */
  /* 文本 */
  --text:#1d1d1f; --text-2:#6e6e73; --text-3:#86868b;
  /* 行动色（唯一主行动色，禁用第二强调色） */
  --accent:#0071e3; --accent-hover:#0077ed; --link:#0066cc;
  /* 语义状态 */
  --ok:#34c759; --warn:#ff9500; --danger:#ff3b30;
  /* 证据四分类（写作工位专属，冻结不可挪用） */
  --ev-fact:#0071e3;      /* 已核实事实 */
  --ev-sourced:#ac8e3e;   /* 有来源解释 */
  --ev-judgment:#8944ab;  /* 作者判断 */
  --ev-personal:#00a06d;  /* 亲身经历 */
}
```

- 深色模式：一期不做，tokens 预留语义命名以便平移。
- 证据四色只允许出现在账本与正文标注，禁止用于按钮或装饰。

## 3. Typography Rules

```css
font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","SF Pro Text",
           "PingFang SC","Inter",sans-serif;
```

| 层级 | 规格 | 用途 |
|---|---|---|
| display | 56px/700，-0.02em | Hero 大标题 |
| h1 | 32px/700，-0.01em | 工位标题、区块标题 |
| h2 | 26px/650 | 卡片标题 |
| body | 15-17px/400，行高 1.6-1.85 | 正文、编辑器 |
| meta | 12-13px/500 | 标签、状态、脚注 |
| mono | SF Mono / ui-monospace 11.5-12.5px | 控制面五字段、reason code、密钥掩码 |

数字（token 数、计数）一律 `font-variant-numeric: tabular-nums`。

## 4. Component Stylings

- **胶囊按钮**：`border-radius:980px; padding:12px 26px`。主行动 `--accent` 白字；次行动 `--bg2` 灰底；破坏性 `--danger`。工位内小号 `7px 16px / 13px`。禁用态降透明度而非换灰。
- **输入框**：圆角 12px，1px `#d2d2d7` 边；聚焦 `--accent` 边 + 3px `rgba(0,113,227,.15)` 光环。错误态换 `--danger` 光环 + 下方 12px 提示。
- **卡片 / 瓦片**：圆角 18px，白底，1px hairline；hover 上浮 2px + 阴影 `0 12px 32px rgba(0,0,0,.09)`（200ms）。
- **面板（工位）**：白底 18px 圆角卡片化分区，标题 12px 大写灰色字距 0.05em。
- **iOS 开关**：44×26，选中 `--ok`；分段控制（segmented）用于二三级互斥选择。
- **门禁卡片（核心组件）**：1px `rgba(0,113,227,.35)` 边 + 4% 蓝底；标题带 ⛳；选项按钮组右对齐。出现在流程上下文内（不弹窗打断），决策后折叠为一条留痕记录。
- **阻断卡（blocked）**：`--danger` 30% 边 + 3% 底，mono 字体原样展示 reason_code；"确认来源可信"按钮必须由 owner 显式点击，无任何绕过入口。
- **控制面状态条**：灰底圆角条内白色小胶囊，五字段（route/status/stage/worker/reason_code）恒定顺序，status 着语义色。
- **Toast**：底部居中浮出，3s 自动消退，承载"决策已留痕"等确认。

## 5. Layout Principles

- 壳层：1024px 版心，区块白 / `--bg2` 交替；瓦片网格 `repeat(2,1fr)` 间隙 16px。
- 工位三栏：`210px | 1fr | 260px`（流水线 | 主区 | 账本/详情）；两栏变体砍右栏。
- 设置页：`230px | 1fr`（分类导航 | 分组行）。分组行 52px 最小高，1px hairline 分隔。
- 间距令牌：4 的倍数（4/8/12/16/24/32/56）。

## 6. Depth & Elevation

| 层级 | 阴影 | 载体 |
|---|---|---|
| 0 | 无 | 页面底、面板 |
| 1 | `0 1px 2px rgba(0,0,0,.04)` | 控制面条内胶囊 |
| 2 | `0 6px 18px rgba(0,0,0,.08)` | 卡片 hover、下拉 |
| 3 | `0 8px 40px rgba(0,0,0,.08)` | 模态、命令面板 |
| 毛玻璃 | `backdrop-filter:saturate(180%) blur(20px)` + 82% 白 | 唯一消费者：吸顶导航 |

阴影只升不叠：同一交互链路上深度单调递增。

## 7. Motion & Interaction（动态交互规范）

- **时长令牌**：micro 120ms / standard 200ms / scene 320ms。曲线统一 `cubic-bezier(.25,.1,.25,1)`（近似苹果 spring-out）。
- **页面切换**：320ms，新视图 12px 上移 + 淡入；旧视图即时卸载（不等待）。
- **列表入场**：子项 40ms 阶梯（stagger）淡入上移；瓦片网格 ≤8 项时启用。
- **任务运行态**：进度环/点 1.2s 呼吸脉冲；阶段推进时流水线节点 200ms 完成态切换；计数变化用 300ms 数字滚动。
- **门禁到达**：门禁卡片 200ms 展开 + 页面顶部 hairline 闪一次 `--accent`；等待中导航栏项目显示 6px warn 圆点。
- **键盘**：`⌘K` 命令面板（全局导航与动作）；`Esc` 关闭浮层；工位内 `⌘⏎` 提交当前门禁首选项。所有按钮可 Tab 聚焦，焦点环 3px accent 光环。
- **反模式**：禁止视差、禁止无限循环动画（运行脉冲除外）、禁止 >320ms 的过渡、禁止自动播放音视频。

## 8. Do's and Don'ts

- ✅ 每个颜色都携带语义；每个动效都指向状态变化。
- ✅ blocked / 门禁文案原样透传 skill 的 canonical 字段值（route、reason_code）。
- ✅ 破坏性操作（删除账户、删 provider）二次确认 + 结果 toast。
- ❌ 不用红色做强调、不用四证据色做装饰、不出现第二主行动色。
- ❌ 不提供任何"跳过门禁 / 忽略红线强制写入"的 UI。
- ❌ 不用弹窗打断管线进行中的阅读（门禁用内联卡片）。

## 9. Responsive Behavior

- ≥1024：完整三栏工位。
- 768-1023：流水线折叠为顶部横向步骤条，账本移到主区下方。
- <768：单列；控制面五字段换行保留完整；触控目标 ≥44px。移动端为只读回溯视图（一期不优化编辑）。

## 10. Agent Prompt Guide

为 Leo Studio 生成新界面时：先判断壳层还是工位层 → 套用对应密度与组件 → 颜色仅从 tokens 取值并核对语义 → 动效不超过第 7 节时长令牌 → 涉及门禁 / blocked / 证据分类的界面必须复用第 4 节对应组件，不得发明新形态。
