# leo-ppt-generator 多行业优化技术方案

- 日期：2026-08-29（v2，经 5 镜头深度审查修订：工程可实施性 / 契约一致性 / 行业合规正确性 / 交互经济学 / 验收可判定性，29 条发现全部闭环）
- 输入：`docs/leo-ppt-generator-multi-industry-expert-review.md`（10 专家 × 58 条发现 → 30 条可执行清单）
- 性质：技术方案（HOW）；每批次开工前经 spec-plan 细化为统一计划；评测纪律沿用已验证流程（install.sh 同步安装副本 → skill-up 运行 → judge 离线双向自检）

## 总体架构决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 内容规范载体 | 行业目录独立 `_content_rules.md` | 视觉与内容规范正交；风格文件保持纯视觉职责 |
| 数字元数据载体 | **登记表单源 + 内联短标**：要点内联只保留既有三级短标（引用/估算/示意），完整元数据唯一落在"数字登记表" | v1 内联五字段与"每条 ≤2 行"硬约束冲突（审查 P0）；登记表单源后双记录退化为"短标↔登记表"一行对账 |
| 元数据执行者 | agent 从材料提取**预填**登记表并自核对；用户确认面只呈现 unknown/缺字段例外清单，不审全表 | 用户不填表；确认负担最小化 |
| 校验时机与归属 | 合同纪律（冻结前）+ **`image prepare` 前置强制校验**（runtime 调用校验器，模型不可绕过） | 实测模型零工具调用前科（known-issues 13 轮账目），靠模型自觉运行脚本的门必然落空 |
| 品牌注入 | templates.py 新增 `load_brand`（解析品牌轴字段式 md），`compose_style` 返回前合并；**不触碰 `load_style`**（品牌文件无 json 块，走不了 `_is_style_md`） | 审查发现品牌预设全部为 prose 字段式，v1"复用注入链"在加载端断裂 |
| 技术图通道 | 新 `diagram render`；渲染优先 **Pillow/numpy 自绘**（零新依赖），系统 graphviz 为可选增强；均不可用则阻断 | venv 三平台 lock 再生成本高；中档依赖已有 Pillow |
| 与模版推荐计划的关系 | 2026-08-28-001（模版推荐）**先行落地**，本方案批次 2 依赖其沉淀询问/风格保存通道；`风格路由.md` 两案改动合并落地，沉淀询问合同单一源归 001 | 避免同文件同交互点的所有权争用 |
| 评测 | 每批带行业正确性 eval（自包含 judge + 双向离线自检）；runtime 行为断言一律下沉 `tests/` 单测，eval 只承担文本可判定部分 | judge 仅读回复文本，runtime 产物断言在 eval 上必然假绿 |

---

## 批次 1：内容正确性（A 行业规范轴 / B 数字元数据 / C 敏感与合规门）

纯文档合同 + 最小校验半 + 评测；零 runtime 接口改动。

### A1 行业内容规范轴（清单 1–5）

**新增文件**（每行业一份，行业目录根）：

```text
references/styles/02_行业内容域/<行业目录>/_content_rules.md   （金融审计/政务公共/医疗健康/学术类/咨询类 五个首发）
```

**文件结构契约**（六节固定，缺节即不合规）：

```markdown
# <行业> 内容规范（content_rules）
## 术语表            # canonical 术语与禁用异写；术语首现=全称（缩写）
## 禁用与必用表述     # 禁词分组标注力度：blocked（禁用）/ rewrite（必须改写）/ annotate（必须标注）
## 数字标注规范      # 本行业登记表元数据的必填字段
## 图表与图形惯例    # 行业高频图形与标注惯例
## 场景力度表        # 同一表述在不同场景（营销 vs 学术）的不同力度
## 合规红线          # 命中即 blocked 的表述/图元（含 reason code 映射）
```

**注入链**：`风格路由.md` 第 5 维（行业身份）追加规则——路由命中行业域时 content_rules 与风格 brief 同级强制读取，写入 `deck_spec.content_rules`（文件路径 + **红线与禁词摘要**，不整份注入合同面；worker 侧按页实际命中术语/红线裁剪注入）。`image-deck-workflow.md` 步骤 1 增加"行业域命中时挂接内容规范"。

**五个首发行业红线表（v2 修订版）**：

| 行业 | 关键红线 |
|---|---|
| 医疗 | **五档用语**：①特殊药品（麻醉/精神/毒/放射）禁广告→blocked；②处方药面向大众场景→blocked（限指定专业媒体）；③已获批上市（宣传以说明书与广告审查批准文号为限）；④超适应症→禁宣传；⑤临床研究中→禁结论化。**禁词分组（依《广告法》16 条）**：功效保证类（治愈率/有效率/无效退款/保治愈）、绝对化类（最新技术/最高科学/最先进）、背书类（患者/专家证言与代言）、比较类（与其他药品器械机构比较）。**场景力度**：营销/推广场景禁词→blocked；学术/临床交流场景引用已发表文献的疗效陈述→须带证据元数据（rewrite/annotate 级），不误禁 |
| 政务 | 表述：机关与会议全称首现、领导职务排序规则、禁口语化表述。**数据分级细分**：`restricted` 下分工作秘密（internal+脱敏留痕可做）与国家秘密（秘密/机密/绝密——机密/绝密**直接拒做**并提示移交保密渠道，秘密级原则上拒做、确需时提示走定密审批流程）。图元：红头/公章/文号/密级标识 hard-forbidden |
| 金融 | 披露：前瞻性陈述必带免责、过往业绩必标、静默期信息禁入。**私募/资管子场景**：不得向不特定对象宣传私募产品→面向公开 deck 即 blocked；禁"保本保收益/预期收益率/稳赚"；**合格投资者提示为必用表述**；估值/预测数字必须标"估算" |
| 学术 | 引用带来源行（作者/机构/年份）；统计量带 n/误差/显著性；未发表数据拆两式：**个人通信**（经作者许可）与**待刊**（标 in press 且确认 embargo 已解除，ICMJE/COPE 口径） |
| 咨询 | 行动标题纪律（标题=断言）；建议必须带依据页回指；禁无来源的"行业普遍认为" |

**验收**：eval 用例 `industry-content-rules-enforced`（医疗营销材料含"根治/无效退款"→blocked 并给档位；**学术材料含带 n/CI 的疗效陈述→不 blocked，要求证据元数据**——两分支用 require_any 语义组断言）、`gov-ranking-compliance`（排序错误→指出错误并按职务级别给序，字段级断言）、`finance-private-placement`（私募材料面向公开场景→blocked 并提示合格投资者表述）。

### A2 逐页论证角色（清单 5）

- `deck-master.md` 页首元信息增加 `argument_role` 字段；`prompts/slide-worker.md` 注入块增加对应行；`06_论证模式/`（金字塔、故事弧先行）补"角色→拍子指令"对照表。

### B 数字元数据合同（清单 6–11）

**公共契约**（`deck-master.md` 与 workflow 步骤 1 同步登记）：

- **内联短标不变**：母版要点内只保留既有三级短标（引用/估算/示意），不加元数据括注——行数纪律不破坏。
- **登记表单源**：母版末尾 `## 数字登记表`，每数字一行 `| 数值 | 页 | 来源 | 口径 | 期间 | 单位 | 证据等级 |`；行业必填字段由 content_rules 声明（医疗加 p/CI/n/phase，政务加发布机关+年份）。
- **执行者**：agent 从用户材料提取预填、自核对完备性；母版确认面只呈现**例外清单**（缺字段/unknown 数字），用户就例外求证或放行。
- 对比断言必须带基准期间，无基准按编造阻断；统计图缺 n/误差/显著性则降级示意版式；单位制合同声明（同物理量全 deck 一致）。
- **批次 1 即带最小对账半**：`scripts/check_number_ledger.py`（登记表行内元数据完备性核对——纯表格解析，不做 prose 语义匹配）；正文数字⊆登记表的语义对账随批次 2 校验器（母版机读语法落地后）。

**visual-qa 判据表新增两行**（数字三件套随数可追溯 / 统计标注门槛）。

**验收**：`number-metadata-contract`（无基准"增长 30%"→求证基准或 unknown）、`stat-chart-gating`（无 n 疗效对比图→降级示意版式）；`check_number_ledger.py` 单元测试（fixture：合规表/缺字段表/越权行）。

### C 敏感数据与合规门（清单 12–14）

**输入侧分级门**（合同八要素扩九要素 `data_classification: public|internal|restricted`）：

- **分级语义**（v2 细分）：`internal`=工作秘密与内部数据（脱敏留痕可做）；`restricted`=国家秘密体系——**机密/绝密直接拒做**（提示移交保密渠道）、秘密级原则拒做（确需走定密审批）。默认 `public` 仅当材料全部来自公开来源。
- **零新增轮次设计**：分级声明与 restricted 涉密清单并入**步骤 1 合同冻结同轮**一次呈现；PHI 脱敏确认并入**母版确认轮**（视觉行已列素材）——敏感场景不增加确认轮次。
- PHI 子门：required asset 过可识别性清单（人脸清晰影像/病历号/身份证样式文本/可定位地址），命中提示脱敏，脱敏后随母版轮确认。
- `SKILL.md` 不变边界确认序列显式纳入"数据分级确认"，并继承"不因跳过授权豁免"条款。

**reason-codes 扩展**：

| reason code | 触发 | next_action |
|---|---|---|
| `sensitive_data_unclassified` | 检出未公开样貌数据但合同未定级 | 补分级声明后继续 |
| `state_secret_rejected` | 机密/绝密（及原则拒做的秘密级未走审批） | 移交保密渠道，本任务终止 |
| `phi_unmasked_blocked` | required asset 含可识别 PHI | 脱敏或替换素材后重跑 |
| `industry_rule_violation` | 成稿命中行业红线（**逐条定位到页**） | 按既有"母版→受影响页重建"流程页级修复 |

**成稿侧合规镜头**（visual-qa 对抗清单"表述合规"块 + 进多轮协议镜头池）：违禁词分组命中按 content_rules 力度分级处置——blocked 级词与**伪造公文图元（红头/公章/文号/密级）**保留 deck 级阻断（不可逆风险），rewrite/annotate 级逐条定位到页、走页级修复，**不做整副 blocked**。

**验收**：`data-classification-gate`（未声明分级→阻断求声明，同轮呈现清单）、`state-secret-rejected`（材料自述机密→直接拒做）、`phi-asset-blocked`（素材含病历号→提示脱敏并入母版轮）。

### 批次 1 交付物清单

新增：5 × `_content_rules.md`、`scripts/check_number_ledger.py`；修改：workflow（步骤 1 分级挂接/登记表纪律）、deck-master（argument_role/登记表/单位制）、visual-qa（判据 2 行+表述合规块+镜头池）、reason-codes（4 码）、风格路由（第 5 维）、06_论证模式（金字塔/故事弧）、slide-worker（argument_role 行）、SKILL.md（分级入确认序列+不豁免条款+行业规范最短钩子）；评测：≥7 新用例（judge 语义组断言 + 双向离线自检）+ 3 回归抽样。

---

## 批次 2：生成确定性（D 品牌与防漂移 / E 内容骨架）

runtime Python 改动 + 单元测试；**依赖模版推荐计划（2026-08-28-001）先行落地**。

### D 品牌 VI 链路（清单 15–17、19、20）

**D1 `style render --brand <name>`**：

- 新增 `load_brand`（templates.py）：解析 `${LEO_PPT_HOME}/brands/<name>.md`（用户 VI 优先）→ `references/styles/10_品牌身份/<name>.md`；字段式 md（主色/强调色/字体/语气）用 `_field` 风格解析，不要求 json 块、不触碰 `load_style`。
- 合并：品牌 HEX/字体栈/语气并入 `deck_spec.style`，**覆盖顺序：用户品牌 > 风格默认**（v1 的"user-colors"中间层删除——该通道不存在，待有真实需求再立合同）。
- 校验收窄为**可计算两项**：单一强调色不破坏 + 正文/背景对比度 ≥4.5:1（fail-fast）；v1 的"60-30-10 配比"（缺用量权重不可程序化）移入风格库文档作为设计指导，不作硬校验。对比度不达标时**同时输出最近合规建议色**（自动微调明度/饱和度），不只报错。

**D2 `deck_spec.brand_assets` 契约块（全部可选字段 + 程序化降级）**：

```yaml
brand_assets:            # 仅 logo_primary 缺失时向用户索取，其余缺省自动处理
  logo_primary: <path>   # 逐页 required asset 注入
  logo_monochrome: <path|auto>   # 缺省=程序化生成去色/反白变体
  safe_area: <rule|auto>         # 缺省=按画布比例推导
  min_size: <rule|auto>
  font_license_note: <text|"">   # 缺省为空，交付时如实标注 not-recorded
```

- 语义：与 required asset 同通道注入；组装复验核对 logo 位置/尺寸/变体逐页一致（进固定件一致性判据）。

**D3 防漂移三件**：

- `style render` 产物追加"风格锚附录"（HEX token/字族/纹理关键词逐字节注入每页 prompt）。
- visual-qa 新增"全 deck 末轮跨页一致性轮检"：每页 vs 样张 + 相邻页成对比较，超阈值打回。
- 再锚定（**限定维度**）：worker 双参考=原样张 + 最近 accepted **同角色**页，同角色页**仅继承结构与密度维度（排除 palette/纹理）**——样张仍是风格唯一锚定源，不构成双源。

**D4 暗场与色盲**：`style_variants` 增 `dark-deck` 预设（palette 推导 + 深底对比度复检）；图表轴注入色盲安全序列（L* 间距+双线索）。

**D5 用户 VI 保存**：复用 001 落地后的 save_style 通道增 brand 保存（`${LEO_PPT_HOME}/brands/`）；沉淀询问合同以 001 为单一源，本方案只扩展对象不含新询问。

**测试**：`tests/` 新增 load_brand 解析/合并优先级/对比度校验与建议色/brand_assets 降级四组单测；eval 只留文本可判定部分：`brand-priority-qa`（问用户 VI 与内置预设优先序→答用户 VI 优先并说明路径）。

### E 内容骨架确定性（清单 21–24）

**E1 母版机读语法先行 + 校验器**：

- `deck-master.md` 合同升级：要点显式编号（`1.` `2.`），视觉行容器显式命名并带编号引用（`要点 1→卡 A`）——**落死机读语法后校验器只做结构核对，不做语义匹配**。
- `scripts/check_master_contract.py` 校验：①四段完备；②落位闭合（编号引用对得上：无点无家、无空容器）；③登记表行完备（调 check_number_ledger）；④argument_role 在场；⑤交叉引用页码存在。
- **归属**：`image prepare` 前置强制调用（runtime 集成），模型不可绕过；失败项回母版修复。eval 侧用文本断言（`master-contract-gate`：展示无落位母版问能否过→回复必须指出无落位条目并先修母版）。

**E2 标题连读稿**：校验器自动提取全部结论句标题拼连读稿；不成线打回母版；visual-qa 文字区加"标题读作断言"判据。

**E3 术语表**：母版确认后生成全 deck 术语表；`image prepare` 注入时**按该页实际命中的术语裁剪**（不全表复制，防 prompt 撑爆）；assemble 跨页术语一致性检查。

**E4 备注子字段（与既有定义对齐）**：备注段固定槽位 `口播｜预期疑问｜互动指令｜工程细则/失败路径`（"用时"删除——页首元信息"预计用时"是唯一源；既有"工程细则与失败路径"入第四槽，不无处安放）。

**测试**：校验器单测四 fixture（合规/缺段/无落位/引用悬空）。

---

## 批次 3：版式资产与工程深化（F / G / H）

### F 版式与图型扩充（清单 25–26，markdown 资产）

| 新资产 | 落点 | 要点 |
|---|---|---|
| P23 章节隔页 / P24 数字冲击页 / P25 规格表 / P26 文献页 / P27–P29 教学三件套 | `12_版式库/` + `13_页面语义/` + **Schema 登记** | P25 超 8 行强制 direct-editable 原生表格（入 page-decision-tree）；教学类合同必填"先备知识清单+难度阶梯" |
| 瀑布/桥图、2×2 矩阵版式、统计标注契约、节奏序列模板、路演 storyline、Q&A/backup | `11_图表语法/`、`06_论证模式/`、`13_页面语义/` | 金融审计 layout_patterns 改引真实语法名；Q&A 扩写为预判问题+一句话答+跳转证据页，附录页不占正式页码 |
| **Schema 核对脚本化** | `tests/` 新增登记核对测试 | 逐 id 比对新版式/语义与 `版式内容Schema.md`（及 manifest-schema）登记一致并输出 diff——不做人工目检 |

### G 技术图确定性通道（清单 27、30）

- `leo-ppt diagram render`：输入 `diagram.json`（节点/边/分组/方向，禁自由文本布局）；输出 strict input asset PNG。
- 渲染分级：**Pillow/numpy 自绘**（中档依赖已有，零新增、不触发三平台 lock 再生）→ 系统 `dot` 可用则作为布局增强 → 均不可用阻断（不退回模型徒手画）。若未来引入 venv 新依赖，须同步重生成 `runtime/constraints/py312-{darwin-arm64,darwin-x86_64,win32-amd64}.txt` 并接受 identity 变更触发重装。
- 覆盖：流程图/系统图先行；P&ID、接线图列后续（依赖符号规范文件）。
- 密集表格机读比对：P25 页生成期望值清单（值-单位-容器），`image record` 后 OCR hints 回读逐格比对。

### H 评测与 backend（清单 28–30）

- 行业正确性评测集：`evals/cases/industry-*.yaml`（禁词分组/口径完备/图表门槛/表格逐格——**文本可判定断言**；OR 分支一律 require_any 语义组；排序类断言字段级）；沿用 good/bad 双向离线自检 + 历史轮次重放。
- backend×页型路由：`image record` 记录页型标签与一次通过率，run 级聚合推荐表，backend-selection 读取参与排序。
- prompt 按 backend 方言变体；样张必须用最典型难页；record 增 token/重试计数输出路线成本建议。

---

## 风险与缓解（v2 增补审查发现）

| 风险 | 缓解 |
|---|---|
| 母版 prose 无法机读校验 | 批次 2 先落机读语法（要点/容器编号引用），校验器只做结构核对；批次 1 登记表核对也只解析表格 |
| 校验靠模型自觉运行必落空 | 全部校验下沉 `image prepare` 前置强制（runtime 集成），eval 断言 CLI 输出与 advise 文本 |
| 品牌 HEX 覆盖破坏风格体系 | 可计算两项硬校验（单一强调色+对比度）；不达标输出建议色 |
| runtime 改动不进评测 | 每批评测前 install.sh 同步 + diff 验证 |
| 依赖引入触发 lock 再生 | diagram render 首选零新依赖自绘；新依赖路线明示 lock 三平台再生与 identity 代价 |
| 行业规范过度阻断 | 禁词三档力度（blocked/rewrite/annotate）+ 场景力度表（营销 vs 学术）；blocked 仅不可逆风险（特殊药品/伪造公文/国家秘密） |
| 成稿 deck 级 blocked 摧毁生成成本 | 仅 hard-forbidden 保留 deck 级；其余逐条定位页级修复（复用既有母版→受影响页流程） |
| eval 假绿（runtime 断言落在文本 judge 上） | runtime 行为全部下沉 tests/ 单测；eval 只留文本可判定断言 |

## 总验收口径（v2）

- **批次 1**：≥7 新 eval 全绿（judge 双向自检过）+ 3 回归抽样；`check_number_ledger.py` 单测绿；行业挂接以 5 个带自包含 judge 的 case 判定（断言 advise 回复/deck_spec 摘要引用对应 `_content_rules.md` 路径与红线条目），**替代 v1 的无判据"端到端 advise 验证"**。
- **批次 2**：tests/ 新增单测全绿（load_brand 四组/校验器四 fixture）；≥2 新 eval；安装副本同步后新用例绿。
- **批次 3**：行业评测集 ≥5 用例；diagram render 单测 + 一页真实流程图端到端；版式 Schema 登记核对测试绿。
- **终验收（全批次完成后）**：安装副本同步后**全量套件（既有 21 + 新增）至少一轮全绿**（`model_gating` 标记用例按 known-issues 口径除外）；模型敏感用例多轮采样解读。
