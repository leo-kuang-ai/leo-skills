# file-github 开源项目全面融合方案：evidence-first-writing × leo-ppt-generator

- 日期：2026-08-30
- 状态：实施中（第一阶段 P0/P1 落地）
- 输入：六位产品专家对 `/Users/kuang/knowledge/file-github` 19 个项目的全量源码评审会决议；上游许可已由用户线下确认授权，本方案按"学思想、重写表达 + 直接 vendor（MIT/Apache 源）"双轨执行，来源登记保留。

## 1. 背景与授权

评审会结论（摘要）：

- evidence-first-writing 的真正增量在四个正交维度：中文确定性检测（human-writing）、改写侧护栏与实证权重（avoid-ai-writing）、误报保护（humanizer）、编辑行为边界（renwei-writing）；英文模式层与现有 55 类 catalog 重合度 70–85%，不做整包镜像。
- leo-ppt-generator 的增量：geekai v4.3.0 PPT 模块的分镜 prompt 四项规则与重试/限流工程模式（路线同构、低成本吸收）、marketingskills 的 11 页销售 deck 内容框架（内容层空白）、human-writing/avoid-ai-writing 的标题文案去模板味子集。
- 用户已线下确认全部上游授权，许可证不再构成集成阻断；融合时仍保留来源标注与快照日期，作为镜像漂移治理锚点。

## 2. 目标与非目标

**目标（第一阶段，本次实施）：**

1. evidence-first-writing 新增中文确定性检查器 `scripts/check_prose.py` 并接入 audit/humanize 诊断链路（线索而非门禁）。
2. 检测层知识融合：改写侧护栏（Never-inject）、误报保护、实证权重注记、公众号体裁指纹与防误判阈值进入 humanizer 与中文协议 references。
3. 知识层融合：文案框架扩展（标题公式/测试法/编辑七轮）、STORM 多视角研究方法论与字幕降级链、coauthor 知识卡片共创节奏、外部工具登记（wenyan-mcp/Wechatsync/XiaohongshuSkills）。
4. leo-ppt-generator 分镜四规则（全局风格锚定/视觉转译/恰好 N 页/双模式文字量）进入 slide-worker 与 deck-master；标题/要点去模板味检查挂载 TITLE-READTHROUGH。
5. `image_gen.py` 增加 429 指数退避与全局 QPS 限流，附单元测试。
6. 新增营销叙事参考 `references/marketing-deck-narrative.md`（11 页销售 deck 框架等）。
7. 全部变更配套：单元测试、eval case 注册、CHANGELOG 条目、验证记录。

**非目标（第二阶段路线图，见 §7）：** 社交卡片输出形态、Playwright 测量式质检、断点续跑/每页即落库、STORM pip 桥、自建公众号导出管线。

## 3. 总体架构：四层融合模型

```
┌─ L4 内容层（leo-ppt） ──────────────────────────────┐
│ 分镜 prompt 规则（geekai）× 营销叙事框架（marketingskills）│
│ → slide-worker.md / deck-master.md / marketing-deck-narrative.md │
├─ L3 工具层（efw） ─────────────────────────────────┤
│ 外部工具登记：wenyan-mcp（排版+草稿箱）/ Wechatsync（多平台分发）│
│ / XiaohongshuSkills（发布与数据回流）→ tool-selection.md    │
├─ L2 脚本层（efw） ─────────────────────────────────┤
│ check_prose.py（中文确定性诊断）∥ check_factual_invariants.py │
│ 双检查器并行：文体线索 × 事实不变量                        │
├─ L1 知识层（efw） ─────────────────────────────────┤
│ 检测知识：Never-inject 护栏 / 误报保护 / 实证权重 / 体裁指纹  │
│ 方法知识：文案框架扩展 / STORM 研究 / 卡片共创 / 字幕降级     │
└────────────────────────────────────────────────────┘
```

设计原则：

- **线索而非门禁**：确定性脚本输出只作为 audit/humanize 的诊断线索，破折号、冒号等风格规则服从"作者样本与渠道优先"的既有原则；事实与授权门禁不因新检查器放宽。
- **增量而非镜像**：references 增补均注明上游来源与快照日期，不做逐条镜像追踪（上游高频发版）。
- **跨技能复用**：标题/要点去模板味规则以同一知识源（human-writing + avoid-ai-writing 子集）分别落两个技能，各自跟随宿主文件的组织方式。

## 4. 实施范围与文件映射

| # | 层 | 来源项目 | 目标文件 | 动作 |
|---|---|---|---|---|
| 1 | L2 | human-writing | `evidence-first-writing/scripts/check_prose.py` | vendor+适配 |
| 2 | L2 | — | `evidence-first-writing/tests/test_check_prose.py` | 新增单测 |
| 3 | L2 | — | `evidence-first-writing/SKILL.md` | 接线说明 |
| 4 | L2 | — | `evidence-first-writing/evals/cases/check-prose-diagnostic.yaml` + `evals/eval.yaml` | 新 case+注册 |
| 5 | L1 | avoid-ai-writing | `evidence-first-writing/references/humanizer-pattern-catalog.md` | 增补护栏/误报/权重 |
| 6 | L1 | humanizer | `evidence-first-writing/references/humanizer-patterns.md` | 增补判断纪律 |
| 7 | L1 | wechat-article-skills | `evidence-first-writing/references/chinese-editorial-protocol.md` | 增补体裁指纹+阈值 |
| 8 | L1 | marketingskills | `evidence-first-writing/references/copywriting.md` + `references/copy-frameworks-ext.md` | 指针+新文件 |
| 9 | L1 | storm + Video_note_generator | `evidence-first-writing/references/source-analysis.md` | 增补研究方法论 |
| 10 | L1 | vibe-writing-workflow | `evidence-first-writing/references/article-workflows.md` | coauthor 卡片节奏 |
| 11 | L3 | wenyan-mcp 等 | `evidence-first-writing/references/tool-selection.md` | 工具登记 |
| 12 | L4 | geekai | `leo-ppt-generator/prompts/slide-worker.md` | 分镜四规则 |
| 13 | L4 | geekai + human-writing + avoid-ai-writing | `leo-ppt-generator/references/deck-master.md` | 分镜呼应+标题去模板味 |
| 14 | L2' | geekai | `leo-ppt-generator/runtime/.../image_gen.py` + `tests/` | 退避+限流+单测 |
| 15 | L4 | marketingskills | `leo-ppt-generator/references/marketing-deck-narrative.md` | 新文件 |
| 16 | 治理 | — | 根 `CHANGELOG.md` | 双技能条目（中央统一写入） |

## 5. 专家分工与文件所有权

并行开发期间文件所有权互斥，避免冲突；CHANGELOG 与跨文件指针接线由中央（主控）在集成阶段统一完成。

| 专家团 | 独占文件集 |
|---|---|
| W1 检测工程 | efw: `scripts/check_prose.py`、`tests/test_check_prose.py`、`SKILL.md`、`evals/cases/check-prose-diagnostic.yaml`、`evals/eval.yaml` |
| W2 检测知识 | efw: `references/humanizer-pattern-catalog.md`、`references/humanizer-patterns.md`、`references/chinese-editorial-protocol.md` |
| W3 知识融合 | efw: `references/copywriting.md`、`references/copy-frameworks-ext.md`、`references/source-analysis.md`、`references/article-workflows.md`、`references/tool-selection.md` |
| P1 PPT 工程 | ppt: `prompts/slide-worker.md`、`references/deck-master.md`、runtime `image_gen.py`、新增 runtime 单测 |
| P2 营销叙事 | ppt: `references/marketing-deck-narrative.md`（仅新文件） |

## 6. 测试–验证–测评三级策略

1. **单元测试**：
   - efw：`python3 -m unittest discover -s evidence-first-writing/tests -p 'test_*.py'`（含新 `test_check_prose.py`，覆盖每族检测器：硬停词/黑话/翻案正则/冒号/排比/名词化/句长 CV/连词密度/比喻场聚集，含误报豁免用例）。
   - ppt：runtime 退避/限流逻辑单测（注入 fake provider 与 fake clock，验证仅 429 退避 2/4/8s、其他错误立即失败、QPS 上限生效）。
2. **仓库级检查**：`python3 leo-ppt-generator/scripts/lint_style_briefs.py`、`lint_layout_grid.py`、`git diff --check`、TODO 扫描。
3. **测评**：新 eval case 注册进 `evals/eval.yaml` 后 `skill-up list-cases evals/eval.yaml` 校验注册完整性；按需以 `skill-up run` 抽跑新 case（引擎 claude_code）；judge 断言遵循"否定感知"纪律（对健康输出不误判）。

## 7. 第二阶段路线图（本次不实施）

| 项 | 来源 | 规格 |
|---|---|---|
| 社交卡片输出形态 | guizang-social-card-skill | platform-specs 三画板（3:4/1:1/21:9）+ 4-band 密度量化 + 组图工作流；渲染管线 Playwright 截图 |
| 测量式质检 | guizang R1–R9 | editable 路线 DOM 测量校验：溢出 px 阶梯/密度/最小字号/标题间距 |
| 断点续跑 | geekai | run 状态记录 per-page 完成态，恢复只补缺页（RecoverStaleTasks 语义） |
| STORM pip 桥 | storm | deep 档可选执行器，环境变量开关，隔离 venv |
| 公众号导出自建管线 | markdown-nice 经验 | markdown-it+juice 自建（当前以 wenyan-mcp 登记替代） |
| 渠道容忍矩阵落地 | avoid-ai-writing | 6 渠道 × 规则 strict/relaxed 表进 humanizer 判断链 |

## 8. 风险与治理

- **镜像漂移**：上游（avoid-ai-writing v3.28+ 等）高频发版，references 一律注明快照日期，不承诺逐条同步。
- **脚本定位**：`check_prose.py` 退出码非零仅代表检出失败级文体线索，不构成交付阻断；SKILL.md 明示其诊断定位，防止被当作硬门禁滥用。
- **测试回归**：所有新测试纳入技能级 unittest 入口；PPT runtime 变更不得破坏既有 fail-fast 语义。
- **变更纪律**：CHANGELOG 由中央统一追加，条目注明来源项目与授权状态。
