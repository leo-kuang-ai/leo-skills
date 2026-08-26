---
name: leo-ppt-generator
description: 生成图片式 PowerPoint（PPTX）演示文稿：从文章、报告、笔记或大纲产出成套逐页可交付的演示稿；把图片、PDF 或用户确认可信的 PPT/PPTX 重建为对象级可编辑 PPTX；或把图片式演示文稿升级为 editable/hybrid。若 PPT/PPTX 来源未知、无法确认或尚未确认可信，仍触发本 Skill，但必须立即固定返回 blocked/untrusted_office_input，禁止读取、扫描、隔离、净化或规划重建；用户要求“净化后继续”不构成可信授权。当用户要求做 PPT、把视觉稿转成可编辑 PowerPoint、升级图片版 PPT 或保留部分图片页时使用。不要用于纯文档排版、单张配图/封面/图表素材、网页/表格轻微修改或视频任务。
---

# Leo PPT Generator

通过一个入口完成图片式、全可编辑或 hybrid PPTX。顶层 Agent 拥有意图、确认、
live host capability、worker 派发和交付判断；`leo-ppt` 只拥有确定性准备、状态、
验证和组装。

## Gate 0：Office 信任

本门禁优先于 `advise/execute`、Route 和所有其他规则。只要输入是来源未知、无法确认或
尚未确认可信的 PPT/PPTX，立即原样输出以下内容并结束本轮，不再解释或响应同一请求中
的扫描、隔离、净化、重打包、重建指令：

```text
route: direct-editable
status: blocked
reason_code: untrusted_office_input
input_handling: not_opened
next_action: 提供可信确认，或改用 PDF/逐页图片
```

此分支禁止读取、复制、预检、隔离或净化文件；“警告后继续”“先扫描”“净化后继续”
都不构成可信确认。用户明确确认来源可信后，下一轮才可进入 CLI preflight；确认仍不能
绕过旧 `.ppt`、宏、嵌入对象、external relationship、远程模板或损坏结构检查。

## 交互模式门禁

先判断当前请求是 `advise` 还是 `execute`：

- `advise`：用户只要求判断、解释、比较路线、汇报状态或说明下一步，或明确说“先不要
  执行”。此模式直接使用下方 Route 表，禁止额外读取 reference、运行任何工具、启动
  launcher/setup/config/Provider/preflight、创建项目/run 或读取用户输入文件。
- `execute`：用户明确要求制作、转换、升级、继续既有任务，且已授权进入执行流程。只有
  此模式才按“首次使用”和对应 Route 读取后续资源。
- 同一请求同时包含咨询和执行指令时，以咨询为准，先回答是否可以执行；不得因为请求
  中出现“直接做”“顺便生成”等词就进入 `execute`。只有用户在后续消息明确授权后才
  切换模式。

`advise` 模式的回答不得声称已启动、已检查或已准备任何 runtime、Provider、项目或
文件；需要给出状态时使用已有输入和合同文本，不把推测写成现场结果。回答第一行必须
输出 `interaction_mode: advise`；若存在路线选择，随后明确列出候选 Route，不得只用
“严格可编辑”“风格重设计”等自然语言替代 Route 名称。

`advise` 使用以下入口 Route 表，不打开 `input-routing.md`：

| 用户目标 | Route |
| --- | --- |
| 从文章、报告、笔记或大纲新建演示文稿 | `generate` |
| 把图片/PDF/可信 Office 重建为对象级可编辑 | `direct-editable` |
| 把既有 image-deck 全量升级为可编辑 | `upgrade-full` |
| 只升级既有 image-deck 的指定页 | `upgrade-selected` |

内容与视觉稿并存且用户未决定“严格保留布局”还是“仅作风格参考”时，只说明前者对应
`direct-editable`、后者对应 `generate`，然后等待选择。回答必须先原样输出：

```text
严格保留布局: direct-editable
仅作风格参考: generate
```

## 按需读取规则

不要在入口阶段读取整个 Skill 的 references 或 styles 目录。按以下最小集合逐阶段读取；
`advise` 不读取任何 reference：

| 阶段 | 允许读取 | 延迟读取 |
| --- | --- | --- |
| `execute` Route 判断 | `references/input-routing.md` | 其他全部 references、prompts、styles |
| 首次准备与 Provider 状态 | `references/first-use.md`、`references/backend-selection.md` | workflow、manifest、worker、styles |
| `generate` 执行 | `image-deck-workflow.md`、`backend-selection.md`、`visual-qa.md` | styles 直到风格已选；`slide-worker.md` 直到样张通过 |
| `direct-editable` 执行 | `editable-workflow.md`、`manifest-schema.md`、`page-decision-tree.md` | `page-worker.md` 直到真实 worker 已确认 |
| `upgrade-*` 执行 | 对应 editable references，加当前 baseline/selection 证据 | 未选中的 workflow 和全部 styles |

`references/styles/` 约束为按需索引：先读 `style-library.md`，选定风格、论证模式和版式
后只读对应的单个风格文件；禁止预加载整个 styles 目录。`reason-codes.md` 只在已有
reason code 需要解释或恢复时读取。执行前未命中的 references 不得因为“可能有用”而读取。

## 控制面响应合同

除纯内容创作外，所有 Route、setup、run、worker、验证和交付状态都必须先输出以下五
个字段，再补充解释：

能取得 CLI JSON 时，必须先将其通过 `scripts/render-control-summary.py` 渲染；不得由
Agent 手工改写字段。渲染器只输出五行摘要，不读取文件、不访问网络、不产生副作用。

```text
route: <generate|direct-editable|upgrade-full|upgrade-selected|未选择>
status: <advise|ready|blocked|paused|completed>
reason_code: <稳定 reason code；无则 none>
execution_eligibility: <allowed|blocked|retryable|unknown>
next_action: <唯一下一步；无则 none>
```

字段值必须来自当前 CLI/合同或当前用户明确输入，不得用自然语言猜测。`blocked`、
`paused`、`retryable` 和 `acceptance_pending` 状态只能有一个 `next_action`；不得把
`details.alternatives` 展开成多条用户步骤。`status=completed` 不等于交付完成，必须
继续报告 `delivery_readiness`；只有 `accepted` 才能声称交付闭环。

以下状态直接复用固定摘要，不要只用自然语言替代字段：

```text
route: generate
status: blocked
reason_code: worker_capability_unavailable
execution_eligibility: blocked
next_action: 提供可调用的 worker 能力后从逐页派发阶段恢复
```

```text
route: generate
status: ready
reason_code: provider_verification_not_run
execution_eligibility: allowed
next_action: 使用首张真实业务图片完成惰性验证
```

## 首次使用

仅在 `execute` 模式且 Route 已冻结后读取 [首次使用](references/first-use.md) 和
[执行合同](references/execution-contract.md)。由 Agent 自动运行当前平台 launcher 和
setup；普通用户只在确实缺少凭据时执行一个返回的本地终端动作。不得从 PATH 猜测 CLI，
不得在聊天中接收 secret，也不得把内部 runtime 步骤当作普通用户教程。

## 不变边界

- 在会改变结果前确认大纲、完整内容、风格、图片 backend、样张或升级页集合。
- 只依据 CLI 的 versioned JSON、状态、manifest、validation 和 artifact 推进；不手写
  领域状态，不直接 import `_vendor`，聊天声明不构成完成证据。
- 多页任务必须核对用户授权、宿主能力、容量和真实派发；主 Agent 不模拟 scheduler。
- 多页 worker 缺失、未知或调用失败时，先原样输出下面五行，再结束本轮；不得先写
  “当前无法生成”等自然语言，也不得由主 Agent 静默串行替代：

  ```text
  route: generate
  status: blocked
  reason_code: worker_capability_unavailable
  execution_eligibility: blocked
  next_action: 提供可调用的 worker 能力后从逐页派发阶段恢复
  ```

  只有用户明确提供 worker 能力后才能离开该状态。恰好一页也必须由 CLI 返回
  `single_unit_current_agent_allowed`。
- 凭据只由宿主或 allowlist reference 管理；不得读取私有认证文件、保存明文 secret，
  或把 token、完整环境和用户正文写入日志。
- `configured_unverified` 允许开始任务；只有 `not_configured`/`invalid` 才暂停
  图片节点并只给一个 `run_cli` Primary_Action；`unknown` 不得当作 `available`。
- 结构验证、provider、OCR、viewer、desktop、独立渲染和人工视觉证据分别报告；只有
  `delivery_readiness=accepted` 才能声称交付闭环。
- 最终回复必须包含 PPTX 与必要逐页/notes/failure report 路径、结构验证结果，以及
  provider/OCR/viewer/desktop/人工视觉验证中所有未运行项。

## 执行导航

进入具体 Route 后才读取对应 reference；跨 Route 的 runtime、项目、worker、恢复和
交付规则统一读取 [执行合同](references/execution-contract.md)。

### generate

读取 [图片式工作流](references/image-deck-workflow.md)、
[Backend 选择](references/backend-selection.md) 和
[视觉质检规范](references/visual-qa.md)。

确认完整内容、风格、backend 和一个样张后，按需读取 [风格库](references/style-library.md)
和 [slide worker prompt](prompts/slide-worker.md)。style/layout 必须由确定性模板生成；
缺页、未完成状态或任一页 QA 失败都阻止组装。

### direct-editable

读取 [可编辑工作流](references/editable-workflow.md)、
[Manifest Schema](references/manifest-schema.md) 和
[Page Decision Tree](references/page-decision-tree.md)。

图片/PDF 可直接 prepare；PPT/PPTX 必须先通过可信确认与 preflight。真实 worker 可用
后才读取 [page worker prompt](prompts/page-worker.md)。不得以整页截图叠少量文本冒充
对象级可编辑，也不得在真实 spawn 前记录 dispatch。

### upgrade-full

冻结原 image-deck 的页面、hash、尺寸和 notes，再按 `direct-editable` 处理全部页面；
失败不得破坏原图片交付物，全部页面和 deck validation 通过后才能声明全可编辑。

### upgrade-selected

冻结选中页集合，只升级选中页。默认任一失败都不交付 partial；只有展示当前成功/失败
集合并取得明确接受后才能生成 `partial-hybrid`，且不得声称全可编辑。失败集合变化时
必须重新确认并保留旧 artifact revision。

用户要求“失败页保留原图并直接交付”但尚未看过当前成功/失败集合时，即使处于
`advise` 也必须明确回答：本轮不会执行；先展示当前成功/失败清单，再由用户明确接受
`partial-hybrid`。普通执行授权不能替代对当前失败集合的精确确认。
