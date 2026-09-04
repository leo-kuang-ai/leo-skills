# Backend 选择

除内置四类 backend 外，OpenAI 兼容图片渠道（智谱 / 百炼 / 方舟 / 千帆 / 混元 /
魔搭）以 checked-in 目录注册：条目见
[`provider-catalog.md`](provider-catalog.md)，数据源为
`runtime/src/leo_ppt_generator/config/providers.yaml`。渠道能力固定为
generate-only；`backend create --provider <channel>` 时端点 origin 与默认模型由
目录填充（显式 `endpoint_origin` 仍须 origin-only），执行期 base URL =
origin + 渠道固定 `api_path`，不做 `/v1` 猜测。渠道凭据环境变量与 CLI 枚举均从
目录派生；setup 报告在 provider_options 内披露渠道引导块（官网 / 取 key /
环境变量 / 模型清单）。

分别声明 backend 的 `generate`、`edit`、`mask` 和 `reference image`
capability。任务需要的 capability 缺失时，在派发前返回
`blocked/backend_capability_missing`。

setup 的候选必须来自同一个 backend registry。只有宿主明确声明 available，才能
选择 `builtin-imagegen`；宿主声明 unavailable 时，候选中不得出现该 backend；
unknown 必须先确认宿主能力，不能推测为可用。外部 Provider 先按当前任务需要的
capability 过滤，再按凭据状态和用户既有确认排序。需要 mask 时不得推荐不具备 mask
能力的 AtlasCloud。

OpenAI 与 AtlasCloud 是图片 Provider 的选择关系；OCR 不参与图片 Provider 选择。
数据密度是路线与 backend 推荐的输入（与 `image-deck-workflow.md` 3a 步联动）：
数据版式页 ≥6 个数据点或含估算序列的 deck，默认推荐 direct-editable / hybrid——
图片路线的 stylized 图表不承载精确数值标注（`styles/00_索引/图表样式规范.md` §五）；
≤4 个巨数的数据海报页是图片路线最强项。
普通图片式生成不披露 PaddleOCR。只有 editable 阶段明确需要文字 hints 时，setup
才把 PaddleOCR 作为非必需在线增强列出；凭据缺失时使用本地 `builtin-ink`，不得阻断
图片 Provider 确认或普通生成。

优先使用当前宿主可调用的内置图片工具；只有工具不可用、调用错误、输入不可读或
没有有效本地输出时，才按已确认的 run-level fallback contract 使用 CLI/API。
缺少可选参数不是自动 fallback 理由。

确认 backend 时记录：

- backend id、model 与 capability；
- credential reference 类型，不记录 secret value；
- task-local 图片、prompt、mask、reference 的允许发送范围；
- retry/timeout/rate-limit；
- output path、hash 与 provider receipt。

样张确认后保持 backend 和 generation method 不变。域名字符串不能推断 provider
类型；provider 必须来自显式 registry entry。

Backend contract v1 示例：

普通流程不要手写下面的 JSON。用户确认 provider 与 mode 后执行：

```bash
"$LEO_PPT" backend create --provider openai --mode generate --output ./backend.json
"$LEO_PPT" backend validate ./backend.json
```

`create` 从当前静态 registry 生成 capability、execution owner 和允许的 credential
reference，并立刻用同一 loader 自校验。`validate` 的合同通过与
`credential_reference_status` 分层报告；两者都不替代真实 provider smoke。

存放口径：contract 在项目 `<project-root>/contracts/` 下创建与验证（上文
`./backend.json` 仅为示意输出路径）；run 冻结时复制一份到 `<run>/input/
backend-contract.json`，worker 只读取该冻结副本。三个位置是同一 contract 的
创建、冻结、消费三个时点，不是三份独立配置。

生成结果示例：

```json
{
  "schema_version": 1,
  "backend_kind": "openai-compatible",
  "provider": "openai",
  "model": "gpt-image-2",
  "mode": "generate",
  "credential_source": "environment-reference",
  "credential_ref": "env:OPENAI_API_KEY",
  "selection_source": "user-confirmed",
  "capabilities": {
    "generate": true,
    "edit": true,
    "mask": true,
    "max_reference_images": 16,
    "execution_owner": "runtime"
  }
}
```

`credential_ref` 只允许 `env:`、`host:` 或 `keychain:` 引用。原始 key/token、旧
`editppt config` 文件和宿主私有认证文件都不是合法来源。


## backend × 页型路由（批次 3-H）

- `image record` 支持 `--page-type chart|text-heavy|image` 与 `--attempts <N>`：
  每页尝试写入 `<run>/observability/backend_stats.jsonl`（旁路 sidecar，不影响
  canonical state hash；统计失败不阻断 record）。
- `"$LEO_PPT" backend report <run>`：聚合输出 (backend, page_type) 的一次通过率
  表；多轮 run 积累后作为 backend 排序输入——图表/密集文字页优先路由到该页型
  历史通过率高的 backend，而非只按 capability 过滤。
- **prompt 方言**：不同图片后端对长结构化 prompt 的服从度不同——按已选 backend
  生成方言变体（长清单型 backend 保结构化列表；指令敏感型 backend 收短句 +
  负面约束前置），样张阶段必须用"最典型难页"（承接样张合同）。
- **token 计量**：worker 回报 `backend_tokens` → 父 Agent `image record --tokens`
  透传进 backend_stats；`backend report` 的 `tokens_total` 按 (backend, 页型)
  聚合（未回报记 not-recorded），支撑"密集数据页多轮重打"的成本与路线决策
  （如表格页持续高 token 低通过 → 默认改走 direct-editable）。
- 路线成本参考：统计积累显示某页型在某 backend 一次通过率持续低时，派发前提示
  换 backend 或改走 direct-editable（如密集表格页）。

## 成本预估前置（派发前）

逐页派发前必须给出本次 deck 的 token/成本预估区间，与"多一张图成本先告知"同属
成本告知纪律。用确定性脚本生成，不得口头拍一个数：

```bash
python3 scripts/estimate_run_cost.py --pages 12 --chart 2 \
    [--text-heavy N --image N] [--stats <run>] [--price-per-1k X]
```

- **有历史**：`--stats` 指向含 token 记录的 `backend_stats.jsonl`（或 run 目录）时，
  按"均值 tokens/attempt × 均值 attempts/页"估每页型成本，band 上界 ×1.5 重试余量。
- **无历史或 `not-recorded`**：退保守假设区间（chart 9000 / text-heavy 7000 /
  image 5000 / 未分型 6000 tokens 每页，上界 ×2），输出 `basis` 字段如实标注
  `assumed-default`；混合时标 `mixed`。假设区间不得说成测量值。
- **对账**：交付披露时与 `backend report` 的实际 `tokens_total` 对账一句；实际超出
  预估带上限时说明原因（如返工轮次超历史均值）。

## 渲染 lane 路由（gamma M1：与图像 backend 并列的第二产物来源）

确定性渲染 lane（`render page` / `render chart`，合同见
[`render-contract.md`](render-contract.md)）接管正确性合同最重的页型。
路由规则：

- **提议条件**（满足其一，派发前提议）：
  1. 页型命中数据密度路由的"≥6 数据点或含估算序列"档
     （`styles/00_索引/图表样式规范.md` §五）——图表/表格/文字密集页的
     数值逐字保真由确定性渲染承担；
  2. `backend report` 显示某页型在当前图像 backend 一次通过率持续低
     （既有"换 backend 或改走 direct-editable"提示的第三选项）。
- **确认点**：render lane 提议**寄生既有第 5 步 backend 确认点**（与 backend
  选择一并确认，不新增暂停点）；用户拒绝则维持原路由。未确认不得改走
  render——图像 worker 的"不得本地渲染近似替代页"禁令对未经路由确认的
  本地渲染保持有效。
- **readiness 抑制**：`render ready` 非 `render_backend_ready`（missing/
  unknown）时，路由提议被**抑制**并披露原因（`render_backend_missing`
  + 安装指引）；确定性渲染不适用 Provider 三态（无凭据概念），不产生
  credential 类 reason code。图像 lane 全功能不受影响。
- **backend 枚举**：render 页 record 时 `--backend render:html|render:mermaid`
  （echarts P2 占位），`--render-receipt <产物>.render.json` 并入 provenance；
  `backend_tokens` 恒 `not-recorded`，token 聚合单独看待不混入图像成本。
  render 页派发走 `prompts/render-worker.md`（与 slide-worker 平行）。
- **质检**：render 页与图像页同走 `references/visual-qa.md` 2.5 步像素闸门
  （render-worker 单页自查 + 父 Agent 批量复跑）。
