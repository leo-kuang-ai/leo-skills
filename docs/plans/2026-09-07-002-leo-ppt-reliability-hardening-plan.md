# Leo PPT Generator 可靠性加固技术方案（渠道执行面与操作摩擦收敛）

> 依据：`docs/plans/2026-09-06-001-leo-ppt-reliability-baseline-evaluation-plan.md` 基线测评（30 轮）+ 重测轮 1 + 迭代 2 的全部证据。缺陷编号沿用基线测评的 defect-ledger.csv（原存 git-ignore 工作区，已于 2026-09-11 清理）。

## 1. 背景与证据基线

基线测评结论：**架构方向成立**（确定性分层、诚实门、可审计账本均经实测验证），剩余风险集中在**操作摩擦与一致性**：

| 证据 | 问题 | 本方案工作流 |
| --- | --- | --- |
| D-DEF-01/02/03（P1/P2，已修）+ 基线 4 渠道全阻塞延迟暴露 | 渠道能力无进场验证：`backend create` 不探活、参数兼容硬编码在 vendored 层 | WS1 渠道健康体系 |
| D-OBS-04（hybrid 尺寸门）+ D-OBS-05（渲染整数 dsf）+ 渠道档 1792×1008 | 尺寸体系四层各自为政（基准/渠道/渲染 dsf/editable inch） | WS2 尺寸预算合同 |
| D-CHART-01（P2，模板级已修）但根因仍在：`--capacity` 文本 vw 推算管不住 CSS 真实溢出 | 容量预检与渲染脱节，缺陷要到视觉 QA 才暴露 | WS3 渲染溢出哨兵 |
| 方案自评"人工确认成本过高且缺陷下降有限"；样张六字段+授权引用+supersedes 全档一刀切 | 确认仪式未按交付风险分级 | WS4 交付档位分级 |
| D-OBS-01（唯一挂起项）：0 图像页 deck 被迫借图像 Provider 合同的壳 | run create 能力要求与页产物来源脱钩 | WS5 render-lane deck 合同 |
| 协议"主 Agent 不串行替代 worker"仅 next_action 提示，无机器证据 | 派发纪律弱强制 | WS6 派发纪律强制 |
| 本轮 98 个行为用例只做入口验证未全量跑（成本） | 静态/单测/现场/行为四层覆盖不均 | WS7 评测分层 CI |
| openai 401 / openai-compatible 余额不足（代码已就绪，服务端拒绝证明链路通） | 凭据治理缺巡检入口 | WS1（health L3）+ WS8 |

## 2. 目标与非目标

**目标**：把"渠道进场可信、尺寸全链一致、溢出即时拦截、确认按风险付费、派发有机器证据、验证分层可持续"六件事落成合同与实现。

**非目标**：不改四条 Route 的总体叙事；不扩 Provider 数量；不动已验证的诚实性红线语义（strict 门/缺页阻断/收据指纹）；不追求行为用例全量常跑。

## 3. 设计原则

1. **增量合同**：一切 schema 变更 additive（v1 → v1.1），旧 run/旧合同不迁移即兼容。
2. **证据驱动减门**：删确认点必须有 backend_stats/缺陷账本数据支撑（WS4）。
3. **确定性优先**：能用确定性检查拦截的（WS3），不留给概率性视觉 QA。
4. **目录驱动优于代码推断**：渠道能力进 registry 数据（WS1），vendored 层查表而非硬编码。

## 4. 工作流设计

### WS1 渠道健康体系（P0/P1）

**现状**：`doctor` 只有凭据在场性；渠道参数兼容靠 vendored 家族推断（patches/0009）；注册面与执行面一致性曾长期漂移。

**设计**：新增 `leo-ppt provider health [--level 1|2|3] [--probe]`，三态分级：

| 级 | 内容 | 成本 | 判定 |
| --- | --- | --- | --- |
| L1 静态 | 凭据在场 + registry 校验 + config profile 一致 | 零 | doctor 现有能力收口 |
| L2 参数面 | 每渠道默认模型经 vendored dry-run（模型名校验/quality 门控/尺寸档接受） | 零 | 本轮 SWEEP 方法产品化 |
| L3 探活 | 一张最小图真实生成（2560×1440 或渠道最大 16:9 档），回写延迟/尺寸/字节数 | 一张图费用，须显式 `--probe` | 探针产物进 `observability/channel-health.jsonl` |

- `backend create --probe`（默认关）：创建即 L3，探活失败仍可创建但回执带 `probe_failed` 证据（不阻断——渠道可能临时故障）。
- **渠道能力矩阵**进 `providers.yaml`：每渠道声明 `size_menu`（合法尺寸档/像素上限/比例约束）与 `param_compat`（拒收参数表，如 zhipu×quality、doubao×output_format）。vendored 门控从"GPT_IMAGE_MODEL_PREFIX 家族推断"升级为"合同模型 + 目录查表"，矩阵缺失时回退现有家族规则。
- `backend report` 聚合 backend_stats 的渠道×页型一次通过率/P50/P95 延迟，供 WS4 减门决策。

**实现要点**：`provider health` 走 CLI 新子命令（复用 `upstream_bridge.run_upstream` 的 dry-run 路径与 build_execution_context）；L3 复用 R31 驱动器的探针 prompt 模板。

**验收**：矩阵驱动门控后，`tests/test_vendored_image_gen_params.py` 增加查表用例；故意把 zhipu 矩阵标错 → dry-run 报 `channel_size_invalid`（带菜单提示）而非发请求收 400。

### WS2 尺寸预算合同（P1）

**现状**：四个尺寸层各自默认——图像 2560×1440 基准/渠道档、渲染 1280×720×整数 dsf、image 页组装 10×5.625in、editable manifest 13.333×7.5in；D-OBS-04/05 两个坑由此产生。

**设计**：`run create` 时从 advise 阶段推荐尺寸预设写入**全册尺寸预算**（deck_size_budget），随内容合同冻结：

```yaml
deck_size_budget:
  canvas_ratio: "16:9"
  image_lane_px: 2560x1440        # 目标；渠道只能给更小档时取矩阵内最大合法档
  image_lane_px_actual: null      # 渠道选档后回写实际档（进披露）
  render_lane_px: 2560x1440       # 渲染 dsf 从预算推导（整数档），非整数时取上限档
  editable_slide_in: [10.0, 5.625]  # 混装锚；editable manifest 生成时按此改写
```

- 预算字段在 `run create` 写入默认值（标准 16:9 预设，用户可覆盖），随样张确认冻结进 slides.json 头与 run 输入；渠道选档读预算、实际档写入 `image_lane_px_actual`（与目标不一致时进交付披露）。图像渠道选档、render `--size`、editable manifest `slide/content_box` 换算、hybrid 组装校验**全部从预算推导**。
- `check_deck_geometry` 终检对照预算（而非散落的各层默认）。

**验收**：R33 场景（zhipu 渠道档 + 渲染基准混装）在预算合同下无需人工干预选档；故意声明 1792×1008 给渲染页 → 冻结期即报 `render_size_not_in_ladder`（而非渲染期才 `render_size_mismatch`）。

### WS3 渲染溢出哨兵（P0）

**现状**：`--capacity` 是文本 vw 推算，与 CSS 真实布局无闭环；D-CHART-01 类缺陷要到视觉 QA 才发现。

**设计**：模板合同新增第七条——**所有 `data-leo-block` 渲染后必须完整落在 `.leo-slide` 内容盒内**：

- `render page` 截图前执行确定性 JS 断言：逐 block 比较 `scrollWidth/scrollHeight` 与容器盒（容差 0px，`overflow:hidden` 之下的真实溢出可测）。
- 越界 → 新 reason code `render_overflow`（带页 id、block id、越界方向与像素数），**不产出 PNG**。
- `.render.json` sidecar 增加 `overflow_check: "pass"` 字段，进 provenance。

**实现要点**：断言注入在现有 ready 信号等待之后、截图之前（复用 `data-leo-ready` 门）；**先观察模式跑全量模板回归**（7 个存量模板含大量长文本用例），只记 `overflow_observed` 不拦截，数据干净后再转阻断模式（配置项 `overflow_sentinel: observe|enforce`）。对阻断模式误报门槛按"1px 容差 + 仅内容性 block"收紧。

**验收**：观察模式下 7 模板全量回归零误报后，转阻断模式；用修复前的 body-basic（git 历史版）+ 3 要点+图表基线数据 → 哨兵必须拦截（复现 D-CHART-01）；修复后模板 → 通过。新增 `tests/render/test_overflow_sentinel.py`。

### WS4 交付档位分级（P1）

**现状**：确认节点全档一刀切（样张收据六字段、授权引用、supersedes、可选双评审）。

**设计**：三档显式声明（内容合同字段 + 交付档案 profile）：

| 档 | 必过门 | 样张 | 确认粒度 |
| --- | --- | --- | --- |
| minimal（≤8 页/内部） | 结构+geometry+收据 | 1 张，user-delegated 默认 | 合并确认点（合同+大纲同轮） |
| standard | + strict-sources + rendered-ledger 对账 | 1 张 | 现行流程 |
| assured（融资/合规/答辩） | + 双评审官 + 逐页 QA 留痕 | 1 张 + 可选结构页 | 现行流程 + 评审记录 |

- **档位推断规则**（优先级从高到低）：
  1. 用户显式 `--delivery-tier` 参数 → 直接采用
  2. 主题词命中 `['医疗','政务','融资','答辩','合规','IPO']` → assured
  3. 页数 ≤8 且 `audience='internal'` → minimal
  4. 默认 → standard
- **减门纪律**：任何档位的门禁集合变更必须引用 backend_stats/缺陷账本数据（例如"minimal 档 N 轮 0 P0 后，样张授权引用简化为引用 id"）。
- 现有确认点全部保留在 standard/assured——本工作流只给 minimal 做减法，不加新门。

**验收**：`evals/` 新增 3 个档位路由用例；30 轮测评的 mgmt-short 场景在 minimal 档下确认交互次数下降 ≥50%（判官按控制面块计数）。

### WS5 render-lane deck 合同（P2，合同面改动最大故后置）

**现状**（D-OBS-01）：0 图像页的 deck 仍需 generate 能力的图像 Provider 合同（run create 硬性要求 + 样张 binding 校验合同 provider）。

**设计**：backend contract v1.1 增加渠道类型 `render-lane`：

- `backend create --provider render-lane`：capabilities `{generate: false, render: true, execution_owner: runtime}`，无凭据引用。
- `run create` 的能力判定改为**按 slides.json 声明的逐页 backend 聚合**（伪码）：
  ```python
  def aggregate_required_capabilities(slides_json):
      backends = {page['backend'] for page in slides_json['pages']}
      # backend 格式："render:html" | "image:openai:dall-e-3"
      
      if any(b.startswith('image:') for b in backends):
          return {'generate': True, 'render': True}  # 需图像合同
      elif all(b.startswith('render:') for b in backends):
          return {'generate': False, 'render': True}  # render-lane 合同即可
      else:
          raise ValueError(f"Unknown backend types: {backends}")
  ```
  全册页产物来源均为 `render:*` 时，render-lane 合同即满足；任一图像页存在时仍要求图像合同。
- 样张 binding 校验：render-lane deck 的 `binding.backend` 接受 `render:html`。
- 旧合同/旧 run 零迁移（v1 合同在 v1.1 判定下语义不变）。

**验收**：R05 场景（纯渲染页 deck）以 render-lane 合同走通全链（含收据）；图像 Provider 全阻塞时不再出现"借壳合同"；`tests/test_channel_catalog.py` 增加 render-lane 合同用例。

### WS6 派发纪律强制（P1）

**现状**：`multi_agent_required` 只有 next_action 提示；主 Agent 串行干完全册无机器痕迹。

**设计**：观察期→阻断期两步：

- 第一步（本批）：`image record` 检测同 run 内**同 agent-id 连续 record ≥3 页** → run-ledger 写 `dispatch_discipline_warning` 事件（不阻断），`run next` 输出附警告计数。
- 第二步（一个发布周期后视数据）：配置项 `dispatch_discipline: warn|enforce`，enforce 时第 3 页起拒绝同 agent 连续 record（`single_agent_serial_dispatch`），例外通道走 `single_unit_current_agent_allowed` 既有语义。

**验收**：本测评驱动器（串行派发）触发警告事件；R31 的真实混合 deck（每页独立 operation-id）零警告。

### WS7 评测分层 CI（P2）

**现状**：静态（lint×4/结构/索引）与单测（pytest 1330+）每批可跑；现场（fixture 矩阵）与行为（skill-up 98 例）无分层节奏。

**设计**：五层节奏 + 各层门禁：

| 层 | 内容 | 节奏 | 门禁 |
| --- | --- | --- | --- |
| L0 静态 | lint_style_briefs / lint_layout_grid / lint_render_templates / lint_skill_structure / capability_manifest --check / sync_upstreams --check | 每次变更 | 全绿 |
| L1 单测 | pytest tests/ | 每次变更 | 全绿 |
| L2 现场抽样 | 基线驱动器矩阵抽样：1 短 deck 全链 + 1 故障注入 + 溢出哨兵回归 | 每次合入 | 收据 fresh + 注入按设计拦截 |
| L3 行为抽样 | skill-up 随机 20% 用例（seed 固定可复现） | 每周/每发布 | 通过率不低于上次全量基线 −2pp |
| L4 全量基线 | 30 轮矩阵 + 故障注入 + 验收轮 | 每里程碑 | 对照 `reliability-baseline.md` 指标无回退 |

- L2 工件：把基线测评工作区的 tools（drive_deck / image_lane_deck / editable_worker / accept_round；原存 git-ignore 工作区，已于 2026-09-11 清理，需要时从评测脚本重建）提炼进 `leo-ppt-generator/bench/` 或 `scripts/baseline/`（保留 fixture 哈希冻结纪律），CI 可执行入口一个脚本。
- L3 抽样 seed 进 `eval.yaml` 头注释，保证可复现与可比较。

### WS8 凭据治理（用户侧配合项）

- openai：keychain 引用不变，轮换新 key 后跑 `provider health --level 3` 复验即可（本轮已证明代码路径端到端畅通）。
- openai-compatible：充值后同上。
- 六条无凭据渠道（qianxing/dashscope/qianfan/hunyuan/modelscope/atlascloud）：vendored 层已验证开放（本轮 SWEEP），配 key 后直接 health L3 即可纳入可用池。

## 5. 实施批次

| 批次 | 内容 | 依据 | 预估 |
| --- | --- | --- | --- |
| A（P0） | WS1 L1/L2（health 命令 + 矩阵数据骨架） + WS3 溢出哨兵观察模式（7 模板回归） | 矩阵先建骨架（现有 4 渠道菜单数据），哨兵观察不阻断 | 2–3 天 |
| B（P1） | WS1 L3 探活（矩阵补充） + WS2 尺寸预算 + WS6 第一步 | 合同 additive，现场验证复用 R31/R33 场景 | 2–3 天 |
| C（P1） | WS3 哨兵转阻断模式 + WS4 档位分级 + evals 用例 | 依赖批次 A 观察数据，只加 minimal 减法，需行为用例护航 | 2 天 |
| D（P2） | WS5 render-lane 合同 + WS7 CI 分层提炼 | 合同面改动最大后置；依赖 WS2 预算字段；CI 依赖 L2 工件稳定 | 3–4 天 |

每批完成即跑对应层验证并更新 CHANGELOG 与对应合同文档（见第 8 节）；批次 C/D 对批次 A/B 有依赖。

## 6. 风险与兼容

| 风险 | 缓解 |
| --- | --- |
| 溢出哨兵误报（字体度量差异/长文本合法换行） | 批次 A 观察模式跑全量模板回归（只记 `overflow_observed` 不拦截），数据干净后批次 C 再转阻断 |
| 渠道能力矩阵维护漂移（新模型/改参数） | 矩阵进 providers.yaml 与渠道目录同源治理；L3 探活回写实测菜单修正矩阵 |
| 尺寸预算与存量 run 冻结指纹冲突 | 预算字段缺省 = 现行为（各层默认），仅新 run 生效；指纹算法版本化 |
| minimal 档减门放过真实缺陷 | 减门只开放到"确认交互合并"，五层质量门与诚实红线不动；30 轮基线场景作为最小回归 |
| WS6 enforce 误伤单页合法 claim | 例外走既有 `single_unit_current_agent_allowed`；enforce 前有完整观察期数据 |
| vendored patch 累积（已 0001–0010） | WS1 矩阵化后家族推断逻辑收敛为查表，patch 面积不再增长；长期推动上游合入 |

## 7. 验收总标准

1. **渠道**：任一渠道三小时内可完成"配 key → health L3 → 进可用池"，且参数不兼容在 L2 即报（不再依赖服务端 400）。
2. **尺寸**：R33 场景（渠道档+渲染基准混装）零人工干预交付；D-OBS-04/05 两个坑在新 run 上不可复现。
3. **溢出**：D-CHART-01 基线数据被哨兵在渲染期拦截（阻断模式）；7 模板全量回归零误报。
4. **档位**：minimal 档确认交互次数较 standard 下降 ≥50%，质量门不减。
5. **合同**：render-lane deck 无借壳合同；旧 run/旧合同零迁移兼容。
6. **CI**：L0–L2 每次合入可执行；L3 抽样 seed 可复现；批次 A–D 各完成后跑 L4 全量，对照 `docs/plans/2026-09-06-001-leo-ppt-reliability-baseline-evaluation-plan.md` 的 30 轮结果（端到端成功率 100%、P0/P1=0）指标无回退；批次 D 完成后的 L4 结果作为新基线，更新 `reliability-baseline.md`。

每条标准对应 `tests/acceptance/ws{1-7}_*.py` 自动化验收脚本。

## 8. 与既有合同文档的关系

- `references/backend-selection.md`：+渠道健康三级、能力矩阵、`--probe`。
- `references/render-contract.md`：+第七条溢出哨兵、尺寸预算推导、`render_size_not_in_ladder`。
- `references/execution-contract.md`：+尺寸预算节、派发纪律节（warn/enforce）、render-lane 合同判定。
- `references/deck-master.md` / `image-deck-workflow.md`：+交付档位字段与档位路由表。
- `evals/`：+档位路由 3 例、哨兵回归 1 例、render-lane 合同 1 例。
