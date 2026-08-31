# leo-ppt-generator 能力融合工程主方案（Master Plan）

- **编号**：2026-08-30-001
- **性质**：技术方案 + 开发/测试/验证/测评全生命周期执行包
- **上游输入**：[ppt-github 6 专家集成评审会路线图](../ppt-github-6专家集成评审会-2026-08-30.md)（90 项目源码评审收敛的六大支柱）
- **协作形态**：总架构师 + 4 个设计专家团（并行）+ 测评与验证总署（收拢）+ 总架构师裁决汇编
- **文档索引**：
  - [团队α-内容与合同层](fusion-team-designs/团队α-内容与合同层.md)（支柱 A 证据治理 + C 文字保真）
  - [团队β-风格版式资产层](fusion-team-designs/团队β-风格版式资产层.md)（支柱 B）
  - [团队γ-渲染与质量闭环](fusion-team-designs/团队γ-渲染与质量闭环.md)（支柱 D 渲染 lane + E 质量闭环）
  - [团队δ-内核与IR层](fusion-team-designs/团队δ-内核与IR层.md)（支柱 F）
  - [测评与验证总署-总纲](fusion-team-designs/测评与验证总署-总纲.md)（统一测试/验证/测评，424 行）

---

## 一、决策日志

| # | 日期 | 决策 | 依据 |
|---|---|---|---|
| DL-1 | 2026-08-30 | 六大支柱按四层分工：内容合同层（α）/ 风格版式资产层（β）/ 渲染与质量闭环层（γ）/ 内核与 IR 层（δ） | 会议路线图支柱间耦合度分析 |
| DL-2 | 2026-08-30 | 固定 6 条集成合同 CI-1..CI-6 作为跨团队接口基线（见 §三） | 防四团队并行设计产生接口漂移 |
| DL-3 | 2026-08-30 | **许可口径变更：用户声明已线下确认全部来源项目授权，许可兼容性不再作为集成阻断项**；来源登记（upstreams.yaml）与 vendored 文件内上游 NOTICE 保留为工程卫生 | 用户明确指令；见裁决 R-10 |
| DL-4 | 2026-08-30 | 里程碑 M0（快赢）→ M1（结构）→ M2（纵深）→ M3（收口验收），每期命令级准出判据 | 测评总署总纲 §8 |

## 二、总体融合架构

**目标架构一句话**：在不动 leo-ppt-generator 既有治理骨架（Gate 0 / advise-execute / 五字段控制面 / CONFIRM-GATE 五点 / DELIVERY-GATE / CLI 真值 / 比例合同）的前提下，沿四个正交层注入六大支柱能力，全部新能力以"封闭例外 + 寄生既有确认点 + 可指纹审计"模式接入，零新增确认门、零治理红线削弱。

**分层与支柱映射**：

```
┌─ α 内容与合同层 ──── 支柱A 证据治理(图维度) + 支柱C 文字保真 ── deck-master/母版/slide-worker/sources_manifest
├─ β 风格版式资产层 ── 支柱B 风格×版式双层库 ────────── layouts.json sidecar/调度师/容量/主题提取/学术视觉/反演
├─ γ 渲染与质量闭环层 ─ 支柱D 确定性渲染lane + 支柱E 质量闭环 ── render CLI/visual_qa/指纹收据/三层容错/感知lint
└─ δ 内核与IR层 ────── 支柱F 对象级内核与IR ─────────── object_builder(python-pptx)/theme/inspect/diff/patch_merger
        ↑ 消费：δ 产 PPTX ← γ 产页图 ← β 产版式/主题 ← α 产内容合同；γ 的指纹收据横向覆盖全部四层产物
```

## 三、集成合同（CI-1..CI-6，全团队共同遵守）

| # | 合同 | 内容 |
|---|---|---|
| CI-1 | 渲染产物统一 image record | render lane 产物与图像模型产物同构：backend 枚举 `render:html` / `render:mermaid` / `render:echarts`，`--render-receipt` 携带 provenance（template_id + template_sha256 + data_sha256 + renderer + out_sha256）。γ 实读证实 cli.py `image record --backend` 为自由字符串（L1176）、backend_stats 旁路已就绪，零状态机改动接入 |
| CI-2 | 指纹收据权威 | E1 五类 sha256 指纹（页产物/本地资产/QA 报告/渲染预览/模板样式源）；`linked_assets{sources_manifest@sha256, beta_sidecars@sha256}` + 顶层 `builder_id` 上下文；TF-2 fallback 页底图+终图双记 |
| CI-3 | schema 版本化演进 | deck-master/manifest/brief 一切字段演进 vN + 迁移注记，旧 run 可恢复；δ 的 builder 经 `LEO_EDITABLE_BUILDER` + run 冻结字段分派，迁移期双跑 |
| CI-4 | 校验退出码 | 新脚本统一 0=过 / 1=FAIL 阻断 / 2=WARN 可交付须披露；**既有脚本退出码不动**（双轨并存，判读用"脚本名+退出码+判据 id"三元组） |
| CI-5 | 确认寄生原则 | 零新增确认门：render lane 寄生 backend 确认点、B7 寄生样张点、TF-2 寄生样张重确认、调度师 undecided 寄生母版确认 |
| CI-6 | Node 边界 | Node 仅限渲染叶子（resvg Node 绑定走子进程 stdin/stdout JSON 隔离）；PPTX 组装路径永远纯 Python（δ 核实 svg2pptx.py 本就是纯 Python，仅 html2svg 依赖 Node） |

## 四、四团队设计要点（详细见各分报告）

### α 内容与合同层（9 动作，10 新增 + 12 修改文件，7 eval case）
- **A1/A4 图维度证据治理**：《学术图表证据规则》reference（6 处理模式 + 5 级审查状态 + 原图裸上纪律）；母版视觉行机读图行（图[F3] 模式/状态/焦点/承载/服务/避免误读）；数字登记表升 v2 九列（verified?/as-of）。`check_master_contract.py` 升 v2 校验，无图行母版向后兼容。
- **A2 sources_manifest.json**：source_class 封闭枚举 + tier（三级标注投影）+ contents_sha256 自指纹；generate 由母版派生、`image prepare --sources` 冻结入 prepare_fingerprint（无参数走旧算法，旧 run 兼容）；upgrade 由页级 asset_provenance 聚合（`--compile`）；`check_sources_manifest.py` 三态，`--strict` 引用级不可回溯即阻断。
- **C1 文字保真四件套**：deck style lock / page role lock / Required text only 白名单（vendor patch 渲染独立 prompt 块）/ Avoid+六问自检。
- **C2 TF 降级链**：TF-1 压文本预算（回母版减法，至少一轮）→ TF-2 留白版式 + `overlay_text.py` 确定性贴字（定义为 generation method 变更，走样张重确认，例外封闭唯一）。
- **C3/C4/C5**：论断式大纲（TAKEAWAY-READTHROUGH 与既有 TITLE-READTHROUGH 并列）；合同三字段 math_load/figure_orientation/section_priority；RST 8 关系分页启发式（advisory，与禅档位双判据）。

### β 风格版式资产层（7 动作）
- **B1 双层 sidecar**：36 份版式层 `.layouts.json` 为唯一真值（五字段封顶 + 治理字段），11 份风格层为薄路由视图（引用版式 id + capacity_factor，不复制真值）——规避 11×36 爆炸；`reuse_friendly=false={P1,P9,P23,P24,P34,P36}`；lint 三项新检查；runtime 只加只读 `style layouts` 查询，**compose_style/compose_layout 零改动**守住 render 字节确定红线。
- **B2 模板调度师**：四步链（角色对齐→结构匹配→节奏感→置信度）+ 确定性打分器 `suggest_layout.py`（0.45/0.40/0.15 权重，<0.5 输出 undecided 交人工，禁止编造版式 id），无状态只读。
- **B3 vw 容量模型**：`vw_of()`（CJK=1.0/ASCII=0.5/空格=0.35）进 `check_deck_geometry.py --capacity` 互斥模式；容量数值从版心Canon token 公式化生成 + 人工审定，单一真值落 sidecar；硬超阻断、软超 WARN 建议"降档/换版式，绝不缩字号/省略号"。
- **B4 主题提取器**：`extract_pptx_theme.py` 纯 stdlib 移植（rels 链→theme1.xml→clrMap→12 slot→字体双槽+Office→Web 16 条映射→亮度/色距角色色）；HEX 只走 `--color` deck 锚点覆盖通道（与"风格不带 HEX"原则兼容）；仅 Trust Gate+preflight 后运行。
- **B5 主题元数据**：brief schema v1.1 只增可选 theme 块，colors 段不写 HEX 只声明角色槽位；"无 theme 的 brief render 输出逐字节不变"快照先行证明。
- **B6 学术视觉包**：NeurIPS Look 六要素并入图表样式规范新章；06_论证模式加"学术五拍"（load_mode 自动发现，零 runtime 改动）；科研答辩风双档（minimal/dense-defense）。
- **B7 样张升级+反演**：默认仍恰好 1 张正文页；结构页"成本先告知+点头才出"；反演三组判读（应延续/需确认/偶然不锁死）随样张同轮呈现，零新增等待。

### γ 渲染与质量闭环层（D1-D5 + E1-E6）
- **D1 Playwright 渲染 lane**：`"$LEO_PPT" render page --template <id> --data slide.json --out … --size 2560x1440`；playwright-python + 本地 HTTP 字体服务（禁 file://）+ viewport 1280×720×deviceScaleFactor 2；HTML 模板 deterministic 合同（禁动画、`data-leo-ready` 显式信号、`data-leo-block` 结构锚点）；全部输出 `leo-ppt-machine/v1` versioned JSON。
- **D2/D3/D5**：`render chart --dialect mermaid` 从 11_图表语法抽 mermaid-example 块零改写执行（同浏览器实例 themeVariables 注入）；resvg 双路径（Python 绑定优先，Node 子进程隔离兜底，fontDirs 离线中文字体 + fitTo.width=2560）；Pillow 双档 variants。
- **确定性分层承诺**：SVG/resvg 链路逐字节（sha256 断言）；HTML/playwright 链路像素 diff ≤ 容差——evals 增"防过度承诺"case。
- **E1 指纹收据（P0 最优先）**：`delivery receipt create/verify`，五类 sha256 + linked_assets + 波及页推断（页产物漂移→该页；资产/模板漂移→全册；QA 报告漂移→仅重跑 QA），对接既有"再检波及面"协议，挂 delivery_readiness quality_gates。
- **E2 像素 QA 前置闸门**：`visual_qa.py` MIT 移植 leo 化，插 visual-qa 流程 2.5 步，FAIL 页不进 LLM 审；与 check_deck_geometry 职责合同化分界（OOXML 结构层 vs 像素内容层）。
- **E3/E4/E5/E6**：美学三指标自研（恒不阻断）；三层容错（阶段分层重试≤3→清扫≤2 轮→已渲染跳过，`image sweep` 复用 reset_failed_pages）；渲染器感知 lint（规则-渲染器映射 + 跳过集）；prompts/registry.yaml 进化记账（prompt 变更无条目 → 治理 lint FAIL）。
- **渲染证据双角色**：render lane 兼任"独立渲染"验证分册的验证者（evidence visual 的 independent_render receipt），验证 PPTX 装配结果，非自证。

### δ 内核与 IR 层（F1-F7）
- **F1 核心决策**：不改 vendored builder，新增自有 `editable/object_builder.py`（manifest IR → python-pptx 编译器），`LEO_EDITABLE_BUILDER=pptx|legacy` + run 冻结字段分派，vendor 文件 0 diff；**事实修正**：legacy builder 实为"4 类默认形状 + 任意 preset 字符串透传（无枚举校验）"，zip 时间戳本就非确定（canonical 重打包连 legacy 一起治）；python-pptx>=1.0.2 已在依赖树。
- **确定性**：`deterministic_zip.py` canonical 重打包（条目序固定、date_time=1980-01-01），同 manifest 同 builder → 同 sha256；builder_id 写入 app.xml 供指纹与感知 lint 分派。
- **等价性合同**：不做字节 diff，做"结构投影"对比（对象 kind/EMU/prst/custGeom 归一化/runs 全属性/notes hash/media 多重集），投影函数一份两用（迁移等价断言 + F3 对象级 diff）。
- **F2/F3/F4/F5/F6**：theme1.xml 字体双槽 + notes 字节冻结经 zip_surgery 回写；`editable inspect/diff`（选择器 `/slide[N]/shape[@name=X]`，三轴 diff 退出码 0/1/2）；patch_merger（merge_mode=patch，母本字节保留仅补丁页替换，失败页原位重插走 PARTIAL-GATE）；manifest v1→v2（oid/evidence/reading_order/editability）；6 项复杂度计分决策树 + authorized_omissions（引用级禁 omitted）。
- **F7**：svg2pptx 纯 Python 核实，矢量可编辑子路线仅远期评估不排期。

## 五、总架构师裁决记录（R-1..R-10）

| # | 议题 | 裁决 |
|---|---|---|
| R-1 | α-C2 贴字与"禁止 manually composited text overlays"红线冲突 | **批准 α 方案**：TF-2 定义为 generation method 变更（底图出自确认 backend、贴字逐字出自白名单、必须样张重确认、交付逐页披露、例外封闭唯一）；SKILL.md 红灯表相应行**显式改写**为引用 TF-2 条款，不得静默削弱；回滚=TF-2 整链禁用退回 TF-1 |
| R-2 | γ render lane 与 image-deck-workflow.md L104"禁本地渲染"禁令冲突 | **批准 γ 方案**：禁令改写为"未经路由确认不得本地渲染"，render lane 升格为确认的 backend（寄生第 5 步确认点）；独立 `prompts/render-worker.md` 协议 + 反冒充 evals case；**L104 改写由 γ 主笔**，α 的 TF 链引用之，一次编辑 pass（γ 先 α 后） |
| R-3 | 指纹收据槽位命名（α/δ 各自请求） | 定案：`linked_assets{sources_manifest@<sha256>, beta_sidecars@<sha256>}` + 顶层 `builder_id` 上下文字段；TF-2 页底图+终图双记（总署 X-4/X-5 行为测试锁定） |
| R-4 | render backend 枚举终表 | `render:html` / `render:mermaid` / `render:echarts`（预留 `render:diagram`）；E2 per-page 判定结构化输出（页号+判据 id+FAIL/WARN）供 TF 链与收据消费 |
| R-5 | β 调度师是否进 run 状态机 | **不进**：suggest_layout.py 保持无状态只读，确认前可任意重跑；重试语义由 γ E4 容错层包装 |
| R-6 | check_master_contract 退出码 0/1→0/1/2 扩展 | 批准，条件：旧 FAIL 用例不回退 + 扩展当轮全量 evals 全绿（总署 C-2 准出条件） |
| R-7 | 退出码双轨（CI-4 vs 既有脚本 0/1/2/3） | **既有脚本一律不动**（回归红线优先）；新脚本 0/1/2；跨脚本判读一律"脚本名+退出码+判据 id"三元组，写入 execution-contract 与 reason code 表 |
| R-8 | β 容量口径 vs γ 密度口径 | 分层并存：B3 生成前容量（vw/字符，版心Canon 公式）+ E3 生成后像素密度（40-60% 带），**均以版心Canon token 为唯一锚**；对表联审进 M1 交叉用例 X-3 |
| R-9 | 对象 diff 术语 ↔ source_class 映射 | crop/redraw/native-rebuild ↔ α source_class 映射表由 α/δ 联审，作为 F3-T4 验收一部分（M2） |
| R-10 | **许可口径（用户线下授权）** | 许可兼容不再阻断：AGPL/无 LICENSE 来源可按授权直接改编搬运。保留：(a) upstreams.yaml 来源登记（borrowed_ideas/upstream 通道）继续做；(b) vendored 文件内上游 NOTICE/版权头不剥离。各团队按保守口径（原创措辞）完成的设计**依然有效**——直接改编是可选升级，仅在质量明确受益处使用（如 banana 调度师措辞、yixueAIganhuo schema 文案），避免无差别引入外部文本扩大维护面；`04_来源_guizang` 待办从"补标注或重写"降级为"补来源登记" |

## 六、统一里程碑计划

### M0 — P0 快赢（文档/提示词/小脚本为主）
**任务集**：α C1-T1、C3-T1/T2、C4-T1/T2、A1-T1/T2、A4-T1/T2、T-L1（许可登记）；β B6-T1..T4、B7-T1..T4；γ E1-T1/T2、E4-T1、E6-T1；总署 B-1..B-4 基线采集。
**准出（命令级见总纲 §8）**：全量 unittest 绿 + 既有 49 case + M0 批 10 = 59 case 非 model_gating 全 PASS + E1 收据最小演示（create→篡改→verify stale+波及页）+ 确认点数量不变 + reason code 只增 + upstreams.yaml borrowed_ideas 通道出现 + CHANGELOG 记 M0。

### M1 — P1 结构工程（四线并行）
**任务集**：γ D1-T1..T6、D2-T1/T2、D3-T1/T2、E2-T1/T2、E4-T2/T3、E5-T1、T-1/T-2；β B1→B3→B2→B4（严格依赖序）；α A2-T1..T4、A3、C1-T2、C2、C5；δ F1-T1..T8（关键路径 T1→T3→T7→T4）。
**准出**：装有 chromium 环境 tests/render/ 零 skip（首次强制）+ 74 case 全 PASS + `style render` 字节红线与基线一致 + resvg 双跑 sha256 相等 + δ 等价性双跑（legacy 与 pptx 各全量，report 归档；env 透传先以单 case 验证）+ core-tests.yaml 新 suite implemented + backend report 首现 render:* 行 + X-3/X-4/X-5/X-6 交叉用例落地。

### M2 — P2 纵深
**任务集**：δ F2/F3/F4/F5/F6；γ D4、D5、E3、E2-T3、E1-T3；β B5-T1..T5。
**准出**：79~80 case 全 PASS + 双跑进入阶段 B（默认 pptx，双 builder 全量对照，分歧阻塞翻转 ≥1 发布周期）+ patch_merger 字节保真断言（27/30 页 part sha256 前后全等）+ X-1/X-2/X-7 落地 + D-6 确定性断言全绿。

### M3 — 收口验收（总体验收仪式，9 步）
① `install.sh --host claude --upgrade`（安装副本同步，known-issues 实证引擎读安装副本）→ ② 全量 evals 80 case 非 model_gating 全 PASS + model_gating 人工复核记录 → ③ 全量 unittest 有浏览器环境零 skip → ④ 双跑对照报告并排归档分歧 0 → ⑤ 指纹收据篡改-恢复演示 → ⑥ 双 lint + geometry self-test → ⑦ backend report 与基线对比表（render lane 页型达支柱 D 判定式）→ ⑧ DoD D-1..D-10 逐项勾验 → ⑨ known-issues/CHANGELOG/`rg TODO`/`git diff --check` 收口干净。

## 七、测试·验证·测评总纲（摘要，全文见总署文档）

- **完成定义 DoD（D-1..D-10）**：80 case 非 model_gating 全 PASS；unittest 全绿且 render 零 skip（有浏览器环境）；双 lint + baseline 只缩不涨；core-tests.yaml 新 suite implemented；双跑对照完成；确定性承诺兑现（SVG sha256 相等 / HTML 像素 diff ≤0.1% / editable 跨 TZ sha256 相等）；指纹收据闭环可演示；治理红线不破（确认门数量不变 + reason code 只增 + 五字段冒烟）；许可登记齐备；CHANGELOG 收口。
- **验证闸门链 G0→G13**：新增 11 个插入点（G1c 版式复用 / G1d 容量预检 / G1e 调度 undecided / G2 素材校验 / G5 像素闸门 2.5 步 / G7 TF 链 / G8b 清扫 / G9b 对象 diff / G9c patch 冒烟 / G11 strict-sources / G12 收据门），全部寄生既有确认序列。
- **evals 扩展**：31 个新 case（α×7 + β×12 + γ×8 + δ×4）按 M0/M1/M2 三批合入（10/15/6），每批当轮全量回归，非 model_gating FAIL 阻断合入；judge 全部自包含（不得 import judge_common，沙盒实证单文件执行）。
- **交叉用例 X-1..X-7**（四家各自都漏的联动测试，总署补齐）：三处文字真值一致 / linked_assets 漂移即 stale / TF-1 消费容量表而非缩字号 / TF-2 双指纹 / builder_id 跨 builder 不误判 / 清扫耗尽×缺页拒绝×PARTIAL×收据一致性 / theme 令牌三消费点同源。
- **红队 8 类**：反冒充、TF-2 滥用、收据绕过（含光板收据）、过度承诺、授权省略滥用、调度师编造 id、信任门绕过提取、skip/not-run 冒充 pass。
- **基线与度量**：M0 前采集 B-1..B-4（49 case 基线 / backend_stats / 已知失败模式 / legacy 确定性现状——防误判回归）；融合后按支柱判定（如图表页"数值不一致"类 QA 失败率→0，以 render:mermaid first_pass_rate=1.0 度量）。

## 八、风险登记簿（合并 Top 风险）

| 风险 | 等级 | 缓解 | 回滚 |
|---|---|---|---|
| δ 迁移行为回归污染交付 | 高 | 三阶段双跑（默认 legacy→每夜对照→翻转）+ 等价投影 CI 全绿硬门禁 + validator 零改动 | `LEO_EDITABLE_BUILDER=legacy` 单点切换 |
| α C2 贴字/γ render lane 治理冲突迁移不彻底 | 高 | R-1/R-2 封闭例外条款 + 反冒充/滥用红队 case + 红灯表显式改写 | 恢复原禁令原文即回现状 |
| render 字节确定红线破坏（β B5/sidecar 入组装路径） | 高 | B5-T2 快照先行证明逐字节不变；sidecar 只经查询命令暴露，compose 零改动入验收 | 删可选键即回 v1.0 |
| 评测规模化时长与归因（49→80 case，model_gating 摆动） | 高 | 分批合入每批全量回归 + judge 双向离线自检 + 摆动即标 model_gating 记归因 | — |
| 退出码双轨误读 | 中高 | 三元组判读护栏进 execution-contract + 红队 R-8 守 not-run≠pass | 冻结合同文本补 judge |
| render lane 被离线环境架空（chromium ~150MB） | 中高 | skip≠pass 强制披露 + 每里程碑一台零 skip 环境 + 无环境则整体标 not-run 推迟 | 路由开关一处分支 |
| 浏览器字体确定性 | 中 | fontDirs/@font-face 显式字体 + loadSystemFonts:false + 缺字 WARN + E1 指纹自动暴露漂移 | — |
| vendor patch 扩面（α C1-T2） | 中 | patches/ 登记 + core-tests 回归 + "白名单静默丢失"可检出判据 | 撤 patch 并入 constraints[] |

## 九、P0 立即执行清单（M0 第一周排序）

1. **γ-E1-T1/T2 指纹收据**（治理收益/成本比最高，1 脚本 + 1 子命令）
2. **α-C1-T1 slide-worker 四件套** + **α-C3 论断式大纲** + **α-C4 合同三字段**（纯提示词/文档，直击内容质量）
3. **α-A1-T1/T2 图表证据规则** + **α-A4 母版增强**（补图维度证据治理）
4. **β-B7 样张升级+反演** + **β-B6 学术视觉包**（寄生既有确认点，零新增门）
5. **γ-E4-T1 容错协议文本** + **γ-E6-T1 提示词记账**
6. **总署 B-1..B-4 基线采集**（先于任何代码合入）
7. **T-L1 许可登记**（R-10 新口径：borrowed_ideas 通道 + 04_来源_guizang 补登记 + NOTICE 核查）

每项完成后按总纲 §8 M0 准出判据统一验收（全量 unittest + 59 case evals + 治理冒烟）。

---

*本主方案为绑定合同；四团队分报告与总署总纲为其不可分割的组成部分，冲突时以本文档裁决记录（§五）与集成合同（§三）为准，其次依"治理红线 > 总架构师裁决 > 团队设计 > 总署补充"效力序。*
