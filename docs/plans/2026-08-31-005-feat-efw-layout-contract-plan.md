---
title: evidence-first-writing 排版合同四件套 - Plan
type: feat
date: 2026-08-31
artifact_contract: spec-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: spec-plan-bootstrap
execution: code
status: active
---

# evidence-first-writing 排版合同四件套 - Plan

## Goal Capsule

- **目标**：为 evidence-first-writing 补上排版合同本体（现状四构件全零）：结构规约、CJK 排版确定性 lint、密度判据、渲染器中立兼容断言——让技能产出的 markdown 在任何成熟渲染器（doocs/md、wenyan 等）里都能得到高质量排版，"确保"形态为零依赖脚本退出码 + eval 断言。上游四构件分类对应交付四件套（U1-U4）：结构规约+密度判据→U1/U2、兼容断言→U3（规约条款侧 U1 ③）、另增登记接线→U4。
- **推荐路径**：合同文本（规则出处）→ check_layout.py（首版 6 类规则+四保护区）→ eval 断言 → 接线与登记升级；渲染实现不建（线 2 已由 leo-ppt 承接、线 3 登记成熟产品）。
- **权威层级**：排版赛道漏斗裁决（upstream-absorption-workspace/layout/07-funnel-verdict.md，用户已裁决"线 1 立项"）为最高输入；深读报告（deepread-line1/line2.md）为机制证据。
- **决策焦点**：check_layout 的 FAIL/WARN 分档边界（密度配额哪些进 FAIL 级、哪些留 WARN 级线索——全部均为诊断级，无交付阻断）。
- **验证焦点**：单测（保护区与邻接正反例）+ 新 eval case 首跑基线 + 既有测试零回归。
- **最大风险/边界**：与 check_prose 职责混淆（vendored 契约不可混入）；膨胀红线（新 reference ×1、脚本 ×1、case ≤2、SKILL.md 合同字段 0 改动——接线净增 ≤4 行）。
- **停止条件**：任何规则需要非标准库依赖或需要渲染 DOM 才能判定——该规则降级为登记判据或移交线 2，不硬造。

---

## Product Contract

### Summary

以三个来源（xiaohu-wechat-format 机制吸收、autocorrect/md-wechat/obsidian-wechat-converter MIT 可引用）为基底，为 efw 落地排版合同四件套：规约文本 + 确定性 lint + eval 断言 + 登记/接线。渲染层不建。

### Problem Frame

排版赛道漏斗（30 项浅筛、7 项深读）实证：efw 有文风 lint、事实 lint、工具登记，唯缺排版合同本体——内容 95 分但交付终点是未规约的 markdown，呈现质量依赖运气与手工。语料中线 1 形态的机制全部有行级验证来源：xiaohu 的标点门禁/密度配额/量化判据、autocorrect 的规则口径、md-wechat 的兼容断言、obsidian 的封闭词表保真条款。线 2（渲染测量）已由 leo-ppt 并行落地，线 3（成熟产品）已登记——efw 的空白恰是"保证输入质量"的合同层。

### Requirements

- R1. 排版结构规约：产出 markdown 遵守六条结构纪律（标题层级不跳级且 H1 唯一；callout/提示块全文 ≤4；高亮标记全文 ≤5；加粗每段 ≤2；表格 ≤4 列且必含表头；连续 3 段须有结构变化），规约含"只加标记不改内容"原则——排版动作只添加标记，不得改写正文文字。
- R2. CJK 排版确定性 lint：`check_layout.py` 零依赖（标准库），检测 CJK 标点全角/半角混用（。，；：？！""（）《》——……对半角形态），四类保护区豁免（fenced code 块、行内 code、URL、链接段）；退出码 0/1/2/3 语义与 check_prose 对齐；输出为诊断线索非交付门禁。
- R3. 密度判据双层：可数配额中 callout/高亮/加粗/表格列四类进 lint 的 FAIL 级；连续 3 段同构为 WARN 级线索；标题层级不跳级与表头必含属规约条款、首版 lint 不机械判定；px 阈值（正文 15-17px、行高 ≥1.7、H1 ≤28px、345px 版心推导）作登记判据入规约文本（渲染实现归渲染器，efw 只登记出处与口径）。
- R4. 渲染器中立兼容断言：新增 eval case 验证发布级产出使用标准 markdown 语法（标准链接、无裸 HTML 标签、无私有容器标记泄漏、嵌套列表层级正确）——来源为 md-wechat 429 行行为断言的渲染器中立子集；规约条款侧（含 CSS 安全区/禁区核对表）由 U1 承载。
- R5. AI 参与排版的保真条款：AI 做版式编排时必须使用封闭可校验的 block 词表；降级路径确定性（不静默改写正文）；正文引用按索引不重写原文。
- R6. 治理：全部增补带来源+许可证+快照 2026-08-31 标注；xiaohu（MIT 补证失败）机制吸收零文本复制；autocorrect/mit-wechat/obsidian（MIT 成立）可引用口径；AGPL 零引用；登记升级含 autocorrect 双轨表述。

### Scope Boundaries

**非目标**：自建渲染管线/主题库（线 3 登记）；DOM 测量/截图质检（线 2，leo-ppt 已承接）；check_prose 扩展（vendored 契约不混）；微信接口自动化；px 阈值的渲染侧强制。

**Deferred to Follow-Up Work**：线 2 增量口径移交（guizang 测量规则 R2 页脚碰撞/R3 粗大字阈值/scrollH 口径/raphael 整形参考——以工作区 handoff 文档供 leo 并行会话取用，不入仓；规则编号均为 guizang validate-social-dck 的 R1-R9 口径，非本计划 R-ID）。

---

## Planning Contract

### Key Technical Decisions

- KTD1. **新 reference 而非塞进既有文件**：排版合同是独立关注面（结构规约+判据登记+保真条款），塞进 chinese-editorial-protocol（文风）或 workflow-contract（流程）都会混责；`layout-contract.md` 是本轮唯一新 reference，条件加载同既有模式。(session-settled: user-directed — 漏斗裁决四件套形态)
- KTD2. **check_layout.py 独立脚本，不扩展 check_prose**：check_prose 是 vendored 契约（上游超集关系已审计），排版规则混入破坏其可追溯性；两脚本并行同 check_factual_invariants 模式。
- KTD3. **密度配额 FAIL 级、px 阈值登记级**：可数配额 markdown 层可判定→FAIL；px 是渲染产物属性→登记出处（xiaohu 345px 版心推导）供渲染工具与线 2 消费。
- KTD4. **诊断非门禁**：SKILL.md 接线句表述为"发布级任务的 audit/draft 输出前可选运行，输出为排版诊断线索"——与 check_prose 同定位，不做交付阻断。
- KTD5. **保护区设计沿用 xiaohu 实证形态**：fenced code/行内 code/URL/链接段四类保护区 + 显式 codepoint 匹配（防 IME 全角空格类坑）；autocorrect 规则口径作引用来源（MIT 补 xiaohu 文本不可复制之缺）。

### Evidence & Limitations

- 机制证据：deepread-line1.md（四项行级验证）；许可证：xiaohu README 声明 MIT 无 LICENSE 文件（补证失败→零文本复制）、autocorrect/md-wechat/obsidian-wechat-converter MIT 成立、guizang AGPL（零引用）。
- 限制：px 阈值无法在 markdown 层验证（登记形态）；eval 环境为 GLM flash 代理（措辞漂移总则适用）；新脚本无历史回放义务（判官不涉及）。

---

## Implementation Units

### U1. layout-contract.md 规约文本

- **Goal**：排版合同的真值源文档。
- **Requirements**：R1、R3、R4（规约条款侧，含 CSS 核对表）、R5、R6
- **Files**：`evidence-first-writing/references/layout-contract.md`（新增）
- **Approach**：四节——①结构规约六条（含"只加标记不改内容"原则与六条配额）；②密度 px 阈值登记判据（15-17px/行高≥1.7/H1≤28px/345px 版心→11 字/行推导，注明渲染实现归渲染器）；③渲染器中立兼容条款（标准链接/无裸 HTML/无私有容器泄漏/嵌套列表保层级 + CSS 安全区/禁区核对表：安全=内联/渐变纯色兜底/box-shadow/圆角/字距/flex，禁区=position/`<style>`/动画/百分比；`==高亮==` 属渲染器依赖扩展，规约限制其数量并注明兼容性由登记渲染器核对）；④AI 排版保真条款（封闭 block 词表可校验/确定性降级/索引引用不重写正文）。每节来源+许可证+快照标注。净增 ≤80 行。
- **Test scenarios**：人工 diff 与 check_layout 规则一一对应（每条 FAIL 规则在规约有出处）；标注 rg 检查。
- **Verification**：来源标注齐全；行数预算内。

### U2. check_layout.py 确定性 lint

- **Goal**：排版规约的可机械判定子集。
- **Requirements**：R1（可数部分：四类 FAIL + 结构变化 WARN）、R2、R3（FAIL 层）、R6
- **Dependencies**：U1（规则出处）
- **Files**：`evidence-first-writing/scripts/check_layout.py`（新增）；`evidence-first-writing/tests/test_check_layout.py`（新增）
- **Approach**：6 类规则——①CJK 标点半角混用：判定条件为半角标点（`, : ; ? ! . ( )` 等）**前后紧邻 CJK 字符**时才报（deepread-line1 候选 1.1 口径——避免 3.14/1,000/12:30/英文句读误报），保护区豁免整函数复用 check_prose 的 mask 形态（fenced code/行内 code/URL/链接段，另含 YAML front-matter 与 HTML 标签屏蔽，共 6 类）；②callout 计数（连续 `> ` 行计一块）全文 >4 FAIL；③高亮标记 `==...==`（Obsidian 式语法，xiaohu 口径）全文 >5 FAIL；④加粗按段内 `**…**` 对计、每段 >2 FAIL；⑤表格列按表头分隔行管道数计、>4 FAIL；⑥连续 3 段同构 WARN（正文纯段落三连无结构变化）。退出码 0/1/2/3（1=有 FAIL、2=仅 WARN、3=用法错误），**不设汉字守卫**（无汉字时规则照跑、语义不变），stdout 五字段格式仿 check_prose：`LEVEL | rule | 位置 | 摘录 | 建议动作`（含头行统计与尾行退出码说明）。autocorrect 口径在 docstring 引用。仅标准库。
- **Test scenarios**：①半角逗号句号紧邻中文报 FAIL、在保护区内不报（各一例）、**英文/数字语境反例不报**（3.14、1,000、12:30、e.g.）；②五类配额各正/反例（4 个 callout 块过、5 块 FAIL 等，按计数粒度构造）；③连续 3 段纯文本 WARN、含列表/引用则不报；④退出码四态；⑤多规则同时命中全列；⑥空文件/缺参 exit 3；⑦纯英文与纯表格文档（无汉字）正常跑不误判 exit 3。
- **Verification**：单测全绿；对全部 references/*.md 与 SKILL.md 遍历实测记录基线输出（诊断快照，供 U4 接线后对比）。
- **Execution note**：先写失败断言再实现（红→绿），沿用 check_prose 测试形态。

### U3. 兼容断言 eval case

- **Goal**：渲染器中立输出可被 eval 锁定。
- **Requirements**：R4、R6
- **Dependencies**：U1
- **Files**：`evidence-first-writing/evals/cases/layout-neutral-output.yaml`（新增）；`evidence-first-writing/evals/eval.yaml`
- **Approach**：发布级 draft 场景（带表格+列表+引用+链接的正文），rule_based 断言：any（标准链接语法 `[文字](url)` 或引导语）+ not（裸 HTML 标签 `<div|<span|<section|<table`、私有容器泄漏标记）+ not（半角标点成串误用——与 U2 呼应的轻量形态）。timeout 420。首跑基线记 description 尾部；断言一律 rule_based（must_contain_any 引擎缺陷在案）。
- **Test scenarios**：①首跑 PASS 或按同义词惯例收口记档；②list-cases 注册可见。
- **Verification**：首跑基线记录；注册成功。

### U4. SKILL.md 接线与登记升级

- **Goal**：合同接入工作流、登记补双轨。
- **Requirements**：R2（接线）、R6
- **Dependencies**：U1、U2
- **Files**：`evidence-first-writing/SKILL.md`；`evidence-first-writing/references/tool-selection.md`
- **Approach**：SKILL.md 在 check_prose 接线句之后加一句（≤3 行）：中文发布级任务的 draft/audit 可选运行 `check_layout.py`，输出为排版诊断线索非门禁；读取 layout-contract.md 的条件加载句（并入现有条件加载段）。tool-selection：autocorrect 条目升级双轨（CLI 可选超集引擎 + 规则口径已被 check_layout 吸收引用）；新增 CSS 安全区核对表指针；视频 ≤7.5MB/正文 ≤10M 经验值备注（来源 md-wechat）。
- **Test scenarios**：①全套单测零回归（test_contract_sync 不受影响——接线句不改合同字段）；②list-cases 正常。
- **Verification**：SKILL.md 净增 ≤4 行；来源标注齐。

### U5. 线 2 增量移交附录（工作区文档）

- **Goal**：深读补齐的测量口径供 leo 并行会话取用。
- **Requirements**：R6（治理边界：不入仓、不触碰 leo 领地）
- **Dependencies**：无
- **Files**：`upstream-absorption-workspace/layout/handoff-line2.md`（git-ignore 工作区）
- **Approach**：从 deepread-line2.md 提炼移交清单——R2 页脚碰撞（worst overlap>6px FAIL）、R3 Swiss 粗大字（≥72px 且字重≥600 FAIL）、R6/R7（WARN advisory）、R1 精确口径（scrollH−clientH>4px）；raphael wechatCompat 六步整形管线参考（MIT，移植须补行为断言）；leo 剩余仓内缺口四项清单。附"判定式抽取、AGPL 零复制"纪律声明。
- **Test scenarios**：不适用（工作区移交文档）。
- **Verification**：文档存在且自包含（leo 会话无需回读漏斗全档）。

---

## Verification Contract

| 项 | 命令/标准 | 适用 |
|---|---|---|
| 单元测试 | `python3 -m unittest discover -s evidence-first-writing/tests -p 'test_*.py'`（既有 159 + 新增全绿） | U2 及全部 |
| 用例注册 | `cd evidence-first-writing && skill-up list-cases evals/eval.yaml` | U3 |
| 聚焦评测 | `skill-up run evals/eval.yaml --include-case-name layout-neutral-output --iteration 1` | U3 |
| 全量回归 | 存量 36 case 一次（无新增稳定 FAIL；对照 it-95/96/97 带内） | U4 后 |
| 仓库级检查 | `git diff --check`；来源标注 rg | 全部 |
| 行数预算 | layout-contract ≤80、SKILL.md ≤4、tool-selection ≤12 | 防膨胀 |

- **Largest unproven risk**：新 lint 对既有 21 个 references/SKILL.md 的基线输出未知（U2 遍历实测收口；它们是规约前文档，输出为诊断快照非缺陷清单）。验收口径为"既有测试零回归 + 新增全绿"（基线数以当次实测为准，不锁定绝对值）。
- **Behavioral skill evaluation**：U3 首跑即行为证据。

---

## Definition of Done

**全局**

- 四件套全部落地且 U1-U4 验证过；U5 移交文档在位。
- 既有单测零回归 + 新增单测全绿；全量回归带内无新增稳定 FAIL。
- 来源+许可证+快照标注齐全（xiaohu 零文本复制、AGPL 零引用）。
- CHANGELOG 条目（user-visible）。

**Per-unit**：各 U 的 Test scenarios 全过、行数预算内。
