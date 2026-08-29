# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project
adheres to a loose semantic-versioning convention.

## [Unreleased]

### Added

- **镜像技能对通用安装器默认隐藏** (user-visible) — 四棵 spec-first 宿主镜像树
  （`.agents/`、`.claude/`、`.kiro/` 各 35，`.codex/` 无）共 105 个 SKILL.md 注入
  `metadata.internal: true`：裸 `npx skills add leo-kuang-ai/leo-skills` 的发现
  清单回归只含三个产品技能（本地路径实测：默认清单恰好三条目，`INSTALL_INTERNAL_SKILLS=1`
  下 38 条目可显式装镜像，裸命令试装 "Installed 3 skills"；远端复验待推送后）。
  新增幂等脚本 `scripts/mark-mirror-skills-internal.py` 应对 `spec-first update`
  重生成覆盖（AGENTS.md 已记重放约定）；四份 README 方式一主命令回归裸命令形态
  （`-s` 降为单装变体）。镜像入库决策（f27e789）不变，clone-即得治理保留。
  计划:docs/plans/2026-08-29-005-feat-hide-mirror-skills-internal-plan.md。
- **仓库安装文档对齐 nuwa-skill 三式结构** (user-visible) — 根 README 与三个技能包
  README 的安装节统一为「方式一通用一行命令（`npx skills add leo-kuang-ai/leo-skills
  -s …`，vercel-labs/skills 安装器，78+ 宿主）/ 方式二手动 clone 宿主路径表（保留
  Claude Code 插件市场链路与 leo-ppt-generator 包级安装器为特化通道）/ 方式三粘贴
  SKILL.md 作参考资料」；「快速安装（复制即装）」独立块并入方式一，原「项目级」
  安装降为方式二表注。实测结论：`-s` 圈定三技能安装成功，creator-buddy 32 个子技能
  被总控遮蔽不漏出；仓库内置 `.agents/skills/` spec-first 宿主镜像会被安装器一并
  列出，故主命令用 `-s` 精确圈定，镜像排除的仓库侧适配另立后续工作。贡献约定补记
  marketplace.json 双通道语义（Claude Code 插件市场 + 通用安装器）。
  计划:docs/plans/2026-08-29-004-docs-nuwa-style-install-plan.md。
- `docs/leo-ppt-generator-master-panel-20-rounds-review.md` — 世界级大师评审团 20 轮审查纪要:
  以 10 位设计师(Duarte/Reynolds/Vignelli/Tufte/Scher/Rams/Sagmeister/Vinh/Gallo/Bierut)的
  公开方法论为判据的角色化评审(并行 10 agent 直读源文件,~80 条发现 + 19 条签名洞察,
  主持人两幕 20 轮交锋决议)。关键产出:①基线验证——上轮三项 P0(data-journalism 悬空、
  P23/P24 缺失、麦肯锡近重复)全部未修复,且麦肯锡分叉已双通道上线、`设计体系.md` 新增
  不实「全部落地完成」宣称;②四个计划盲区新维度——确定性注入链是玻璃地板(Vinh 实测
  `_field` 对标准冒号形态返回空、P9 空骨架静默注入、CSS 方言对生图模型零信息)、数据
  诚实缺视觉层(估算值实心渲染、Tech Spec 装饰竖线 lie factor、KPI Tower 钳制)、叙事层
  无程序(one_thing/三幕/时长和/哇点零合同)、例外无代价表(粗字重/多色/零要点/仪式页被
  一刀切);③全部决议映射到既有两条实施线不另起炉灶——A 并入 W 计划既有单元、B 建议
  新开 W4(注入链修复六项+网格物化,最高工程优先级)、C 并入多行业线(brand 契约/
  verified_at)、D 建议新开 W5(叙事合同+禅档位+AI 图像三级标注),并给出验收口径增量。
- `docs/plans/2026-08-29-001-feat-leo-ppt-style-system-optimization-plan.md` — 风格系统优化
  实施计划（implementation-ready）：将风格评审十档优化点组织为三波 10 个实施单元
  （W1 引用完整性+图表规范 / W2 护栏成文+版式补缺+token 三层化+schema/lint / W3
  动效断言密度+趋势风格+评测）。经 spec-doc-review 三 persona（coherence/
  feasibility/adversarial）审查，20 条 findings 全部合成修复，关键吸收：unittest
  discover 实测 0 测试（存量 7 测试从未被执行）→ KTD9 可发现性前置修复；全库
  palette 为散文实况（0/136 纯 HEX）→ token/护栏/lint 全链按"提取内嵌 HEX 锚点"
  口径重设计 + 12 份内置 brief 定型迁移；护栏前移改 `--guardrail` 旗标保住缺省
  逐字节确定性；与多行业技术方案三处撞车（visual-qa 断言判据行、user-colors 覆盖
  通道、P23–P29 版式编号，后者本计划单方面让号改 P30–P36）逐字核实后在本计划侧
  裁决并登记 Deferred；评测基线先行 + 补 2 个轻量 advise 用例消除空覆盖声明。
- `docs/leo-ppt-generator-multi-industry-optimization-tech-plan.md` — 多行业优化技术
  方案 v2（承接专家评审 30 条清单，经 5 镜头多 agent 深度审查 29 条发现全部闭环：
  内联元数据改登记表单源、医疗红线补《广告法》16 条禁词与五档双力度、政务分级
  细分国家秘密三级并机密绝密拒做、成稿违规改页级修复仅 hard-forbidden 保留 deck
  级、校验下沉 image prepare 前置强制、品牌注入改 load_brand 不触碰 load_style、
  diagram render 零新依赖自绘优先、eval 与单测职责分离防假绿、终验收全量回归
  时点）：总体架构决策（content_rules 独立文件、数字
  内联+登记表双记录、双层校验时机、brand 并入 style render、diagram render 走
  strict asset、评测沿用 9+9 流程），三批次实施设计——批次 1 内容正确性（五行业
  content_rules 契约、数字元数据合同、data_classification/PHI 分级门与 3 新
  reason code）、批次 2 生成确定性（style render --brand 与 brand_assets 契约块、
  防漂移三件、check_master_contract 校验器与标题连读/术语表注入）、批次 3 版式
  资产（P23–P29 与瀑布桥图等 10 类）与 diagram render/backend×页型路由；含风险
  缓解表与逐批验收口径。

- `docs/leo-ppt-generator-style-review.md` — 风格系统评审（十位顶尖设计师视角）：
  以 10 个设计角色（中文排印 / 编辑网格 / 色彩品牌 / 数据可视化 / 叙事 / 动效 /
  无障碍 / 认知负荷 / AI 原生产品 / 设计系统工程）走查 styles/ 风格库全量并对照
  2025–2026 业界趋势。核心结论：六轴正交骨架领先业界，但存在四类系统性短板——
  图表样式规范缺失（14 个文件悬空引用不存在的 `data-journalism`，坐标轴/图例/
  数据标签零规定）、排印参数不落地（字体族几乎全是模糊描述、行高无数值）、
  无障碍只有半条规则（仅 4.5:1，无体系）、"风格不带 HEX" token 化宣称与 138 份
  写死 HEX 的实现脱节。另核验既成缺陷：麦肯锡风格顶层与母版近重复且措辞已分叉、
  P23/P24 版式被引用但文件不存在、目录/团队/引用/数据大屏版式无骨架、deck 级
  动效空白。给出 P0/P1/P2 十档优化矩阵，并标注与多行业专家评审的四处交叉验证点
  （断言式标题、可访问性程序化、品牌 token 链路、版式缺口）。
- `docs/leo-ppt-generator-multi-industry-expert-review.md` — 多行业专家评审：10 位
  PPT 专家画像（咨询/金融/发布会/VI/学术/教学/政务/医疗/工程/AI 架构）五组并行
  分析 58 条发现，归类八大主题：行业内容规范轴缺失（content_rules）、数字元数据
  合同（口径/期间/单位/证据等级）、敏感数据分级与行业合规门、品牌 VI 注入链路与
  防漂移、内容骨架确定性（content render/标题连读/术语表）、版式行业深化（隔页/
  参数表/文献/教学三件套/桥图）、技术图确定性渲染、行业正确性评测与 backend 路由；
  给出三波优先级路线（内容正确性 → 生成确定性 → 工程与评测深化）。

- **docs: spec-first 公众号 W1 二轮推进（手册定稿 + 站外首答）** — 《spec-first 中文实战手册》v0.9 → **v1.0 定稿**（docs/spec-first-gzh-manual-v1.0.md）：两处待补全部补齐——17 workflow 全清单表（权威源 = npm v1.15.1 Runtime Capability Catalog）与 spec-first vs Spec Kit vs OpenSpec 三框架对比表（2026-08 官方页面口径）；三数字 17/35/26 经本地 catalog 与官网 Reference 双重验证成立（26 为 skill-local agents 参考页计数，顶层 source agents 已并入 skill-local 架构）；同工序导出 A4 六页 PDF（章节间嵌公众号码 + 文末大码，Chrome headless 打印，中文渲染经视觉验证通过）。知乎首答草稿落盘（docs/zhihu-answer-01-sdd-practice.md，SDD 实践题，约 820 字 + 双版本钩子段 + 发布待办）。「手册」关键词回复手动文案与链接投放建议追加至运营方案执行记录（后台自动写入不可行的定论不变）。(user-visible)
- **docs: spec-first 公众号 W1 内容资产（自主推进）** — W1 长文《Spec-First 全景：17 个 workflow 怎么串成一条链》全文初稿（约 1600 字，标题 A/B 与发布待办）写入运营方案附录 A；钩子资产《spec-first 中文实战手册》v0.9 落盘（两处待补标记当日已由二轮推进补齐并升级 v1.0，见上条）；知乎题库确认 3 个高流量目标问题（SDD 实践体验 / OpenSpec 与 SDD 未来 / 多 AI 协同交付）。(user-visible)
- **docs: 统一三插件安装规范** — 全仓 README 安装节统一为同一标准：首选 `/plugin marketplace add leo-kuang-ai/leo-skills` + `/plugin install <插件名>`，备选 git clone + 软链，包级安装器（leo-ppt-generator `install.sh`）作为包特有方式保留；移除安装说明中硬编码的陈旧版本号（0.1.0 → `<版本>`）；leo-ppt-generator README 补 marketplace 首选方式；creator-buddy 备选方式对齐软链规范；xhs-hotnotes 文档移除 skillhub 渠道追踪参数；方式二定位措辞统一为「开发者 / 非 Claude Code 宿主」；新增「快速安装（复制即装）」段——每宿主一段可直接粘贴的命令（Claude Code 走 `claude plugin` CLI 官方 marketplace 通道，agents 目录走 clone + 软链），并把 creator-buddy 插件清单迁移至规范位置 `.claude-plugin/plugin.json`（三插件与 marketplace 均经 `claude plugin validate` 校验通过）。(user-visible)
- **creator-buddy: 集成为 vendored 创作工具箱插件（上游 creator-buddy @ edf46c5）** — 以单一顶层目录整体迁入总控 Skill + 32 个子技能（公众号 / 小红书 / 视频三组，与上游字节一致，仅排除 .git）；本地新增 .claude-plugin/plugin.json / LICENSE / UPSTREAM.md，注册 marketplace 条目并先只暴露总控入口（skills: ["./"]）；AGENTS.md 声明 vendored 所有权边界（内部跨组引用与命名豁免、暂不接 skill-up 评测）；README 补安装与使用说明。随后本土化：README 系列（根 / gzh / xhs）移除原作者个人信息与上游安装指引、安装方式改指本仓库，`gzh-Skills/references/my-voice.md` 原作者文风档案转为待填模板，插件 author 元数据改为 leo-kuang-ai；`LICENSE` 版权行按 MIT 再分发要求保留。(user-visible)
- **docs/plans: spec-first 公众号运营方案（战略锚点 + 执行计划）** — 基于产品与生态证据拍板五项运营决策（官方声音缺位诊断、只写一手实践打法、重度 AI Coding 开发者主读者、前 8 周双周长文节奏、docs/plans 落盘位）；含内容三轨、首月排期、三件套草案（带字数校验）、90 天路线图与红线；后经 owner 授权只读后台补充实测基线（834 用户/34 原创/未认证/英文简介），并据此将执行从冷启动基建修正为优化现有三件套；owner 全权授权后已执行菜单改名发布（spec→看内容），简介与自动回复交付了字数校验过的粘贴版文案，并产出基于真实分享率数据的首月 8 篇文章规划。(user-visible)
- **docs/prototypes: v5 设置页完整设计（六组配置）** — 配置分四层：个人偏好（账户/
  通知，门禁到达即时或汇总、失败通知不可关）、算力成本（默认模型带推荐、Provider 健康
  度、单任务 token/时长预算与 failed 续跑闭环、月度提醒阈值）、管线与门禁（门禁策略
  三档标准/精简/严格、默认证据模式与深度、三条硬规则锁定项展示）、系统治理（skill
  版本 × evals 门禁状态、runtime 锁定、产物保留与来源自动入库）；明确不放假配置
  （深色/语言）。(user-visible)
- **docs/prototypes: v5 产品逻辑打磨版原型** — 逐页深化：项目台改为注意力优先排序
  （待决策>失败>运行中）+ 筛选标签 + 每卡"需要你做什么"行动行；向导加深度后果标签
  （时长+适用）与严格接地分支（来源上传步骤）、决定性问题"为什么要问"说明；写作工位
  右栏随阶段自适应三面板、来源↔正文双向高亮联动、门禁选项带代价标注、"手动修改保护"
  所有权可视化；PPT 工位 Route 卡标注"需要准备什么"、逐页样张批准/拒绝（被拒页只重做
  自己）、下载菜单（PPTX/PDF/图片包含保真说明）；设置页模型推荐理由与 Provider 健康
  度。(user-visible)
- **docs/plans: Leo Studio 计划审查修复（12 项 findings 全量处置）** — P1 密钥传递
  边界与提示注入边界入 KTD7/U8（BYOK 密钥不进 workdir 子进程环境）；门禁检测收敛
  为阶段-门禁映射表主机制 + delivered 前必经门禁校验（gate_missed 防静默绕过，
  KTD6/U5 含新测试场景）；U6 补 R1.4 证据模式档位承接；U1 环境契约补 LEO_SECRET；
  KTD8 预览沙箱化；U4 补 worker_abnormal 崩溃映射；范围边界显式点名 R6.4/R4.2 导出/
  R2.2 第三通道延后；U7 注明 V0.5 仅 generate 可执行。(user-visible)
- **docs/plans: Leo Studio 方案一致性整合** — Goal Capsule/KTD2/U1/Output Structure/
  U6/U7/验证合同 8 处同步近期决策（PostgreSQL、KTD9 前端栈、DESIGN.md §11 UX 交互
  合同）：U1 增 tokens CI 校验，U6/U7 增门禁分级"稍后处理"与 failed 断点续跑场景，
  e2e 覆盖空状态/向导/裸主题禁用语义。(user-visible)
- **docs/plans: KTD9 前端技术栈细化（用户确认采用成熟框架）** — Next.js 14+ App
  Router + shadcn/ui/Radix/Tailwind + TanStack Query + Zustand + TipTap，并记录两项
  明确不采用（admin 模板、CSS-in-JS 运行时）与原型→组件映射清单。(user-visible)
- **docs/prototypes: DESIGN.md UX 交互合同与 v4 完整状态原型** — DESIGN.md 新增第 11
  节（首次成功路径/五态矩阵/门禁疲劳渐进披露/failed-blocked UX 合同）；
  `leo-studio-v4.html` 落地：onboarding 三步向导（含裸主题决定性问题与禁用语义）、
  新用户空状态与示例项目入口、failed(budget_exceeded) 断点续跑状态、门禁分级与
  "稍后处理"、Gate 0 阻断交互。(user-visible)
- **docs/plans: Leo Studio 数据库选型改为 PostgreSQL（用户决定）** — KTD5 简化基座
  由 SQLite（WAL）改为 PostgreSQL 16：JSONB 原生、V1 多用户零平移；本地 docker
  compose 与 CI service 承载；Redis 仍不引入。U1 补 DATABASE_URL 与 compose，U3 补
  Alembic/PG 方言与 testcontainers 测试约束。(user-visible)
- **docs/plans: Leo Studio 计划增富为 implementation-ready（技术方案）** —
  Product Contract 字节级保留，新增 Planning Contract（10 条 KTD：独立新仓库
  leo-studio、三进程架构、headless claude CLI runtime 复用 render-control-summary.py、
  V0.5 SQLite+进程内队列+轮询简化基座、AES-GCM 密钥加密与 Gate 0 文件系统级隔离）、
  High-Level Technical Design（组件拓扑/任务状态机/门禁往返时序 mermaid 与仓库
  Output Structure）、Implementation Units U1–U10（含测试场景与验证标准）、
  Verification Contract（skill evals 双门禁 + 导出保真 gate）、Definition of Done、
  风险与系统影响面。(user-visible)
- **leo-ppt-generator 质量回路优化（七项，依据
  `docs/leo-ppt-generator-quality-loop-optimization.md`）** — 由方法论 deck 的
  20 轮多 agent 审查、5 评审官测评与 18 页验收审查反哺 (user-visible)
  - 新增 `references/deck-master.md`：逐页内容母版成为 generate 路线的内容真值
    工件（每页四段：结论句标题/要点/视觉行含落位声明/备注）；审查与修复前移到
    母版层，内容层失败先改母版再重建受影响页。
  - `references/image-deck-workflow.md`：步骤 1 数字与断言三级标注（引用/估算/
    示意；示意不得用图表版式）；步骤 3 逐页稿升级为母版四段结构；步骤 12 组装
    复验增加固定件逐页一致与页内引用存在性核对。
  - `references/visual-qa.md`：打回重做后再检须覆盖「目标判据 + 波及面」双结论；
    对抗清单新增断言-来源等级找茬问句；判据表新增固定件一致与交叉引用两行；
    新增第六节多轮审查协议（镜头池轮换、连续两轮无 P1/P2 收敛、台账与驳回依据，
    高要求可选档）。
  - `references/execution-contract.md`：交付章节新增双独立评审官可选档（分歧
    ≥2 复议；补充证据，不替代三证）。
  - `prompts/slide-worker.md`：自查清单新增要点-容器落位声明（无落位要点或空
    容器即失败）；重做场景 qa_note 须写目标判据与波及面双结论。
  - `SKILL.md`：generate 执行行挂载 `deck-master.md` 按需读取。
  - `evals`：新增 9 个质量回路用例（母版先行/母版修复/波及复查/断言三级/审查
    协议收敛/台账驳回依据/固定件一致/交叉引用/双评审官）与 9 个 judge 脚本，
    共享 `judge_common.py` 否定感知工具；judge 拒绝类断言改直接短语匹配（否定
    过滤自指矛盾，离线双向自检 9/9 通过），known-issues.md 同步记录。评测侧
    发现并修复三项工程问题：skill-up judge 沙盒单文件执行（judge 必须自包含）、
    claude_code 引擎从安装副本加载（仓库改动需 install.sh 同步后进评测）、judge
    长短语断言对模型措辞随机性脆弱（收敛为语义组模式）。六轮收敛后新 9 用例
    全绿；回归抽样 advice-only 与 confirmation-gates 恢复 PASS（后者经 SKILL.md
    两处锚定：材料缺失分支先出控制面块并重申确认序列、确认序列不因用户跳过
    授权豁免）；control-plane-blocked-summary 维持已归档 model_gating 口径。
    修复期间另修旧判官 judge_confirmation_gates.py 的动词表缺口（"发给我"类
    材料请求动作未被识别）。

- **docs/plans: Leo Studio web 工作台 requirements-only 统一计划**（2026-08-28 完善）—
  新增业界同类调研摘要（Gamma / NotebookLM / Elicit / WPS AI 等中文市场评测）并据此
  优化需求：输入多通道（R1.3/R2.2）、证据模式显式化（R1.4 严格接地 vs 开放调研）、
  导出保真验收标准（R2.6）、来源库引用格式导出（R4.2）、品牌模板（R4.4，V2）、
  发布与分享衔接 post-publish 红线（R8，V2）、credits 计费待决问题（Q6）；Non-goals
  明确不做导出水印与 .docx 导出。(user-visible)
- **docs/prototypes: Leo Studio 设计系统与原型三件套** — `DESIGN.md`（Stitch DESIGN.md
  格式，Apple 壳 + Linear 工位双谱系，含动效令牌与 Do/Don't）；静态原型
  `leo-studio-prototype.html`（暗色）与 `leo-studio-apple.html`（Apple 风，含登录/
  注册/设置/模型配置）；动态交互原型 `leo-studio-interactive.html`（任务引擎模拟：
  阶段推进、门禁暂停留痕、Gate 0 blocked、⌘K 命令面板、BYOK Provider 管理）。(user-visible)

- **evidence-first-writing 创作者化能力层（v2 方案，10 项）** — 把 skill 从「单篇生产
  质控机」扩展为「内容经营闭环」，全部与因果/事实/授权红线兼容，势能承诺一律使用
  概率语言，不承诺阅读量数字。(user-visible)
  - 新增 `references/topic-momentum.md`：选题四问合同（时机张力 / 既有叙事定位 /
    势能类型 / 情绪定位，情绪必须附真实性证据）+ momentum card + 情绪真实性门禁
    （情绪命名 ≠ 情绪制造；情绪曲线须「命名 → 复杂化 → 给出口」三段完整，只唤起
    不给出口的焦虑文按操纵处理）。
  - 新增 `references/reader-profile.md`：与作者侧 voice-profiles 对称的读者侧持久
    档案；`misunderstands` 与 `active_emotions` 强制证据链（「反代入四问」的正向
    建设），provisional/verified 分级，无档案时声明 `reader_model: inferred`。
  - 新增 `references/content-assets.md`：选题池、配方候选区（hypothesis → promoted
    分级沉淀，升格条件与 Node 14 `stable_rule_update` 完全一致——因果红线从「禁止
    沉淀」显式化为「分级沉淀」）、系列规划、测试-放大循环；持久化沿用
    personal-context 授权机制。
  - `references/chinese-editorial-protocol.md`：第 13/21 条新增**论点压缩句判据**
    （删句测试：脱离上下文仍成立且删除后 thesis 受损 → 保留并打磨，不按模板感
    删除），修复装饰金句规则误伤传播资产的问题；`references/editorial-taste.md`
    记忆点维度同步交叉引用（论点压缩句是记忆点的传播形态）。
  - `references/article-workflows.md`：新增「骨架选择」节——论证骨架之外提供
    悬念前置 / 双线交织 / 问题-恶化-转折三种叙事骨架，硬规则为每节「知道 / 不知道
    / 想知道」+ 关键信息释放计划（可以延迟陈述，不得误导）。
  - `references/editorial-pipeline.md`：N2 接入四问合同；N7 接入情绪真实性门禁；
    N9 首屏合同（折叠线渠道前三行完成具体开场 + 身份锚定 + 未兑现承诺，兑现位置
    超全文 2/3 记 finding）；N13 分发包（3-5 张金句卡片必须是论点压缩句并注明兑现
    位置、转发语声明三选一传播自利理由、评论预埋默认关闭）；Node 14 观察清单
    （completion_breakpoints / quoted_sentences / comment_keywords 只作
    reader-profile 与 topic-momentum 的证据输入，禁止段落级归因）+ 配方沉淀分级。
  - `SKILL.md`：三个新 reference 的按需读取路由 + post-publish 观察清单条款。
- **leo-ppt-generator 全生命周期体验落地（docs/plans/2026-08-27-001）** —
  按生命周期方案完成 U1–U9：受管 runtime 与 Skill 备份的保留策略核心
  （`runtime_manager.py prune-runtimes|prune-backups`，四闸 containment：
  白名单触发 / lstat 校验 / 整批熔断 / rollback 恢复点下限，14 项安装器
  单测含符号链接 fixture 与恢复点边界）；`--uninstall [--purge-data]`
  程序面/数据面分层拆除（钥匙串零触碰断言、父目录 skills 护栏防误删源码树）；
  `--host codex|agents|claude` 统一宿主选择并兼容既有 `--agents`，
  冲突组合显式报错；装后 onboarding 报告全面中文化且 PS1 补齐对等能力；
  bootstrap 失败在 stdout JSON 契约外新增 stderr 中文伴随行；
  CLI `provider prefer/remove`、`credential remove` 输出一行影响提示
  （仅 stderr，不改变 JSON 协议形状）；README 宿主矩阵/故障排查/卸载四步、
  first-use 离场三件套与配置变更三问、UPDATES.md 变更速览。(user-visible)

- `docs/plans/2026-08-27-001-feat-leo-ppt-lifecycle-ux-plan.md` — 上项工作的
  implementation-ready unified plan（R1–R17 / U1–U9 / 高风险信任链与验证合同）。

- `docs/leo-ppt-generator-quality-loop-optimization.md` — 质量回路优化方案：由
  方法论 deck 的 20 轮多 agent 审查（约 200 条发现）、5 评审官 × 8 维测评与 18 页
  逐页验收审查反哺而成，先明确与现状的边界（大纲确认/unknown/revision/对抗式审查
  等已有能力不重复），再给出六个实测验证的增量：P0 逐页内容母版工件（审查前移，
  修复成本 1 vs N）与修复波及复查；P1 断言-来源三级标注（引用/估算/示意）、多轮
  审查协议（镜头池轮换+NONE 收敛判据+台账）、构建一致性核对（固定件与交叉引用）；
  P2 双评审官可选协议与要点-容器落位声明，每项含证据、落点文件与 eval 验收用例。

- `docs/leo-ppt-generator-lifecycle-ux-plan.md` — 全生命周期用户体验优化方案：
  以首次安装/首次配置/日常使用/非首次更新/配置变更五场景（附卸载缺失场景）
  盘点安装器与 CLI 真实交互面后给出 L1–L16b 分档方案；量化实证本机累积
  23 份 Skill 备份（46MB）与 24 个受管 runtime（4.3GB）零回收，确定
  备份保留策略（L9，含 containment 与 rollback 恢复点下限纪律）为第一优先项，
  并提出宿主别名、onboarding 中文化、人话短语库单一来源等跨场景主题。

- `docs/leo-ppt-generator-ux-review.md` — 用户体验多智能体评审：三个独立审查
  视角（黄金路径旅程、失败与阻断旅程含 6 份真实评测回复实证、行业心智模型
  对照）交叉印证，产出三大结构性问题（确认序列六轮才见首图、worker 缺失无
  解释死局、机器词表全程裸奔）与三档建议（Q 合同零改动快赢 8 项 / P 需拍板
  合同语义微调 5 项 / E 评测配套 3 项），全部设计在四条硬约束之内。

- **leo-ppt-generator** — 落地优化评审 A1–A3 与 C1/C2（依据
  `docs/leo-ppt-generator-optimization-review.md`）：SKILL.md 明确手写降级披露行
  （`gate0_render` / `worker_render: handwritten`）必须置于五字段块之后，消除与
  判官位置合同的互斥；upstream-capabilities.yaml 头部声明 proof/proof_case 属
  上游开发仓 worktree、包内不可复跑（C2 标注路线）；九项文档一致性修复——
  manifest-schema/page-decision-tree 三处悬空章节名改指现行 reference、
  风格计数按盘面实证修正（35+12、02 轴 46、05 轴 3+映射、配对表 84 组并补
  124 口径）、execution-contract 注明 `--backend-contract` 等全局旗标须位于上游名
  之前、first-use 的 `config provider select` 改为实际存在的 `prefer` 并把
  "两问上限"划界为准备阶段、cli-helper 补顶层 `upgrade inspect|import-baseline|
  propose|finalize` 命令段、patches/README 的 0001 归属改为开发仓 proof 并
  移除包内不存在的重放测试引用、worker 返回合同按 vendor record 必填参数对齐；
  README 记录 description 安全冗余偏离官方 ~100 token 建议的理由（C1）。
  判官离线回归与 `git diff --check` 通过。(user-visible)

- `docs/leo-ppt-generator-optimization-review.md` — 最终版优化建议文档：三源证据
  （14 轮 skill-up 实测、全包内容一致性审查、全网调研）支撑的 14 节点逐节点
  分析、对抗性审查与分档建议（立即采纳 A1–A3 / 建议采纳 B1–B3 / 待确认
  C1–C2 / 暂缓 D1–D2 / 否决 E1–E2）；确认判官-合同互斥（handwritten 披露行
  vs 位置合同）与 upstream-capabilities.yaml 12 处死引用为最高优先修复项。

- **leo-ppt-generator/SKILL.md** — 消除"禁工具"与"固定块必须脚本渲染"的合同
  歧义：advise 模式的工具禁令显式豁免 `render-control-summary.py --fixed
  gate0|worker-unavailable`（不读文件、无副作用，输出固定块不构成执行动作，
  用户"不要执行任何操作"不得据此改回手写）；worker-unavailable 固定块补上与
  Gate 0 对齐的手写降级披露 `worker_render: handwritten`。(user-visible)
- **leo-ppt-generator/evals** — 新增 3 个 execute 层行为用例补齐编排层覆盖空白
  （此前 9 用例全部为 advise/状态汇报型）：`mixed-advise-execute-advise-wins`
  （混合请求以咨询为准、首行 `interaction_mode: advise`）、
  `execute-keeps-confirmation-gates`（执行授权不能豁免内容与样张确认门）、
  `single-page-requires-cli-allowance`（单页仍需 CLI 返回
  `single_unit_current_agent_allowed`）。三个判官延续 v2 惯例：判官为唯一断言
  源、否定感知匹配、引号回述剥离；离线回归 6/6（含修复一个"没有开始生成"
  拒绝句被误判的假阳性）。扩容首轮（iter-13）：mixed-advise 与 single-page
  PASS；execute-keeps-confirmation-gates FAIL 为真实合同失守——模型拒绝杜撰
  源数据但在授权压力下放弃样张确认门，与 control-plane 的模型纪律缺口分属
  两类信号。 (user-visible)
- **leo-ppt-generator/evals/cases/control-plane-blocked-summary.yaml** — 携带
  `tags: [model_gating]` 语义分层标记（已验证 skill-up 容忍该键）：带标记用例
  的 FAIL 反映被评模型指令遵循边界，未标记用例的 FAIL 才构成技能合同回归。
- **leo-ppt-generator/tests/boundary/test_editable_patch_regressions.py** —
  patch 0004/0006 的包内聚焦回归落地：confirmed 公式清单缺席即质量合同违规
  （含非 list 清单与未确认候选两个守卫断言）；legacy `.ppt` 规范化把请求 dpi
  透传给 `render_pdf_pages`（LibreOffice 转换器经 mock，不依赖真实 Office 栈）。
  runtime venv 下 5/5 通过；`tests/upstream/core-tests.yaml` 同步把两项从
  pending 出账为已实现用例，editable 侧 pending 清零。

- `evidence-first-writing/scripts/check_factual_invariants.py` — track curly Chinese
  quotes `“…”` as a `curly_quotes` invariant category (the most common quote style in
  user manuscripts was previously invisible to the checker), and stop URL values at
  the first non-ASCII character so trailing full-width punctuation and adjacent CJK
  text are no longer absorbed into the URL (re-typography no longer flags spurious
  URL changes). (user-visible)
- `evidence-first-writing/tests/test_factual_invariants.py` — boundary regression
  tests: curly-quote swap is flagged, URL survives surrounding-punctuation edits
  unchanged, and URL changes inside CJK prose are still flagged.
- `evidence-first-writing/evals/scripts/check-dev-edit-first.sh` — new judge asserting
  development-edit findings (thesis/structure/warrant) precede sentence-polish terms
  in the output, plus presence of the paragraph-swap test and the evidence-to-claim
  link.
- `evidence-first-writing/evals/cases/personal-context-authorized-write.yaml` —
  first positive-path permission case: with explicit write authorization the Skill
  must read existing AGENTS.md, write the minimal repo-relevant projection, create
  no other files, and NOT extend the authorization to unauthorized persistence
  (self-writing a cross-project memory). Asserted at the filesystem level
  (`expect.files_exist` / `files_not_exist` / `file_contains`) plus output gates
  catching scope-creep claims observed in a real run (`另存了一份` / `已写入记忆`).
  (user-visible)
- `evidence-first-writing/evals/cases/bare-topic-fork-two-turns.yaml` — first
  multi-turn case: bare topic → fork question (turn 1 must NOT emit a route card
  or draft) → user answers 「形成判断」 → turn 2 proceeds on the argument workflow
  without re-showing a type questionnaire. Uses the harness's per-turn
  `turn_response_not_contains` assertions, discovered and verified via
  `skill-up debug judge`. (user-visible)
- Nine new `evidence-first-writing` eval cases closing the gap between the 24 planned
  and the 20 implemented cases (deterministic subsets only; residues documented):
  `full-article-evidence-chain`, `chinese-protocol-context-judgment`,
  `chinese-22-rules-hit-and-preserve`, `voice-channel-conflict`,
  `train-voice-provisional`, `docs-truth-param-check`, `dev-edit-before-polish`,
  `taste-findings-not-visual`, and the field-name-unleaked variant
  `post-publish-no-causal-unprompted`. (user-visible)
- `evidence-first-writing/evals/eval-plan.md` — concrete per-group run commands
  (`--include-case-name`, repeatable globs) for routing-smoke / evidence-regression /
  docs-regression, and a plan-case → implemented-case mapping table listing exactly
  which planned capabilities remain unautomated (blind editorial judges, real CLI
  fixtures, blind-eval isolation, finding counts).
- 新增 `leo-ppt-generator/evals/known-issues.md`：记录四轮 control-plane 用例
  F·F·P·F 稳定性账目、GLM 代理环境事实（model_name 为空、unrecognized_model 告警）、
  判官口径变更史与真机复验待办，避免后续轮次误读为回归；同日 S1–S5 五轮全量复测后
  账目扩至十点序列（v2 口径下五连 F，其余 8 用例 5×0 翻红，全套 411–533s），确认
  control-plane 失败形态本身稳定（叙述先行、五字段块缺失、无泄漏），定性为被评
  模型的指令遵循能力边界而非技能合同缺陷。
- 新增 `leo-ppt-generator/tests/boundary/test_vendor_state.py` 与
  `tests/upstream/core-tests.yaml`：`upstreams.yaml` / `patches/README.md`
  引用的回归证明工件现已真实存在并可执行
  （`python3 -m unittest discover -s tests/boundary`）。补丁 0002 的并发锁由
  多线程串行化实测覆盖（缺 `filelock` 时诚实跳过）；codex 套件与补丁
  0004/0006 的聚焦测试如实登记为 pending，不再被暗示为已验证。E27 的
  `proof_case` 同步改为类限定用例 ID。(user-visible)
- Add `leo-ppt-generator` as the second top-level skill package, migrated from
  the standalone `leo-ppt-generator` project. It turns requirements, visual
  mockups, images, or PDFs into editable PowerPoint decks (image-based,
  editable, hybrid, and upgrade routes). During migration the over-the-air
  self-update logic was removed — the `check`/`update` subcommands, download
  helpers, and remote constants that fetched version info and installer scripts
  from `leo-kuang-ai/leo-ppt-generator` are gone, and the runtime health check is
  now a local-only comparison. `install.sh` / `install.ps1` were adapted to
  local-only mode (default source is the script's own directory, `--ref`/`-Ref`
  remote fetch dropped) and moved inside `leo-ppt-generator/` rather than the
  project root. (user-visible)
- Add `.claude-plugin/marketplace.json`: enables `/plugin marketplace add leo-kuang-ai/leo-skills` and
  `/plugin install evidence-first-writing` for remote Claude Code installation.
- Add `evidence-first-writing/README.md`: install (Claude Code personal/project
  and Codex), usage, cross-host adaptation, references map, and test/eval
  commands.
- **README.md** — add an installation-and-usage section with the remote
  `git clone … && ln -s …` commands to `~/.claude/skills/`, project-level and
  Codex install paths, an update step, and a `/skills` verification step; keep
  the English mirror consistent.
- Introduce `evidence-first-writing/evals/` evaluation suite for the Skill:
  - `evals/eval.yaml` orchestration config (default engine `claude_code`).
  - 20 cases under `evals/cases/`, including new ones: `depth-quick-revise`,
    `post-publish-no-causal`, `copywriting-route`, `rejects-causal-overclaim`,
    `personal-context-no-write`.
  - Judge scripts under `evals/scripts/`: `check-single-routing-question.sh`,
    `check-causal-boundary.sh`, `check-audit-readonly.sh`, `check-voice-skip.sh`.
- Add negation-tolerant script judges referenced by migrated eval cases:
  - `evidence-first-writing/evals/scripts/check-formal-report-route.sh` —
    formal-report routing gate with synonym alternatives (`owner||责任人`,
    `期限||上线窗口||决策节点||周期`, `三个方案||三方案||方案 A`) and route-pollution
    negatives.
  - `evidence-first-writing/evals/scripts/check-tool-evidence-routing.sh` —
    tool-select evidence-status gate covering taste-skill / HC3 / shuorenhua /
    ai-flavor-remover with unfalsifiable-claim negatives.
- Add the spec-first host runtime mirrors to version control
  (`.agents/skills/`, `.claude/{commands,hooks,settings.json,skills,spec-first}`,
  `.codex/hooks+hooks.json+spec-first`, `.kiro/{skills,steering,spec-first}`;
  scratch/local subsets stay git-ignored), so fresh clones carry the full
  using-spec-first entry governance without re-running init.
- Add docs/image.png reference to the root README: a Humanizer tool-chain
  selection cheat sheet ("想做什么 → 对应方法" mapping plus open-source tool
  comparison) embedded under the evidence-first-writing section. (user-visible)

### Changed

- **插件版本发布** — `evidence-first-writing` 与 `leo-ppt-generator` 的
  `plugin.json` 版本 0.1.0 → 0.2.0：写作技能发布创作者化能力层（选题四问、
  读者模型、内容资产、论点压缩句、分发包），PPT 技能发布全生命周期管理
  （U1–U9）；description 同步补充能力关键词，`/plugin update` 现在有明确的
  版本锚点。(user-visible)
- `evidence-first-writing/evals/scripts/check-audit-readonly.sh` — accept `引用` /
  `原文` as synonyms of `原句` for the quoted-evidence gate; a compliant audit that
  labels quotes as 「引用：」 no longer false-fails (iteration-33's only FAIL was
  exactly this brittleness). `evals/cases/audit-does-not-rewrite.yaml` drops the
  duplicated `expect` block so the judge is the single assertion source.
- `evidence-first-writing/evals/scripts/check-formal-report-route.sh` — extend the
  time-constraint synonyms (`时限` / `时间表` / `时间约束` / `交付时间` / `排期` /
  `时间节点`) after a compliant response using 「时限」 false-failed in the
  iteration-34 pre-run.
- `evidence-first-writing/evals/scripts/check-causal-boundary.sh` /
  `check-post-publish-boundary.sh` — catch paraphrased over-claims (`证明了因果`,
  `该公式有效`) in addition to the literal banned phrasings; verified locally that
  negation-safe refusals (`不能证明因果关系`, `不写入稳定档案`) still pass.
- `evidence-first-writing` judge sensitivity red-team (16 adversarial probes against
  all 10 script judges; 13 caught, 3 misses fixed, then 6/6 historical PASS
  responses replay-accepted): `check-causal-boundary.sh` gate 2 tightened from
  bare negation words to refusal-verb-bound forms (an "assert causation, then
  append caveats" response no longer passes); `check-post-publish-boundary.sh`
  bans `已被验证` / `已被证明` / `已验证` / `确定有效` over-claim variants;
  `check-independent-review-status.sh` catches the `status: PASS` case variant.
  Follow-up A/A then exposed that the tightened causal regex false-rejected
  compliant Chinese that inserts an object between modal and verb
  (`无法将这一下降归因于`) — relaxed to a 0-8 char gap with `归因` / `确认` /
  `因果结论` verbs, re-verified by replaying 5/5 historical responses (accept)
  plus the adversarial probe (reject). `docs-truth-param-check` drops the
  `qstat --verbose` command-level negatives that false-fired on
  quote-then-reject explanations, and gains the observed compliant phrasings
  (`未采用` / `输出中没有` / `删除`); `evals/known-issues.md` now pins the
  replay-on-tightening discipline and the quantified A/A flake rates
  (dev-edit 1/3, chinese-protocol 1/3, docs-truth 2/3 pre-fix).
- `evidence-first-writing/evals/cases/humanize-preserves-facts.yaml` — fold the
  stricter 7-token invariant list (date, company, verbatim quote sentence) into the
  rule_based judge and drop the duplicated `expect` block (same single-source
  treatment as the migrated routing cases).
- `evidence-first-writing/evals/cases/*.yaml` — evidence-regression group cases
  uniformly get `timeout_seconds: 300` (per eval-plan guidance that this group needs
  longer timeouts than the 180s default).
- `evidence-first-writing/references/humanizer-pattern-catalog.md` /
  `humanizer-patterns.md` — stop hard-coding the pattern count in titles/trigger
  phrasing ("当前 55 类" instead of "55 模式"), aligning with source-analysis's
  rule that the pattern count is a drifting snapshot, never a fixed fact or gate.
- `evidence-first-writing/evals/eval.yaml` — register the nine new cases
  (suite grows 20 → 29).
- `evidence-first-writing` judge/prompt de-brittling after the iteration-34 full
  run (all six FAILs were compliant behavior + paraphrase drift, verified against
  the actual responses): `check-post-publish-boundary.sh` ties the open-rate
  status marker to the open-rate mention via regex (accepts `open-rate status` /
  flipped Chinese word order) instead of fixed phrases;
  `check-dev-edit-first.sh` anchors the structure-test gate on contract
  vocabulary (`推进` from the taste dimensions) plus observed compliant
  phrasings (`零贡献` / `文章不变` / `删掉任何`); `chinese-22-rules-hit-and-preserve`
  adds `预设反驳` / `扣帽子` / `可能以为`; `taste-findings-not-visual` adds
  `争夺` / `罗列` / `清单` / `塞入`; and `humanize-preserves-facts` now asks for
  the full rewritten paragraph verbatim so a correct stop-condition response
  still reprints the frozen invariants.
- `evidence-first-writing/evals/cases/chinese-protocol-context-judgment.yaml` —
  fixture fix: the draft's closing line 「这不是流程的胜利，是人的胜利」 was itself a
  second reversal-aphorism, making the "no real problem → stop" verdict genuinely
  ambiguous (two runs correctly flagged it as a cluster finding). The ending is
  replaced with a concrete forward-looking sentence so the stop-condition contract
  is unambiguous; verdict synonyms extended (`不需要硬改` / `模板感低` / `整体干净`).
- `evidence-first-writing/evals/cases/docs-truth-param-check.yaml` — accept
  `不在真实 --help` / `usage 行` / `已剔除` / `无法运行` for the param-reconciliation
  gate (iteration-38 compliant phrasing).
- `evidence-first-writing/evals/known-issues.md` — add the paraphrase-drift
  handling discipline (substance present + vocabulary missed → record, stop
  chasing words; missing substance → real defect) with the dev-edit and
  chinese-protocol cases as first applications.
- `evidence-first-writing/evals/known-issues.md` — record the iteration-33 GLM-flash
  PASS of `post-publish-no-causal` as provider evidence narrowing the DeepSeek-era
  stable FAIL, update the environment description (deepseek proxy → bigmodel GLM
  proxy), and open a new tracked item: the field-name-unleaked variant
  `post-publish-no-causal-unprompted` FAILs under GLM flash with substantively
  correct reasoning but no canonical contract vocabulary (`hypothesis` /
  `stable_rule_update` / `persistence`) — assertions deliberately kept strict.
  Real-Claude 3/3 remains the closure standard for both items.
- `evidence-first-writing/evals/verification-summary.md` — record the 29-case
  suite expansion, the GLM-flash provider arc (iteration-33 `19/20` with one
  assertion brittleness, iteration-34 `23/29`, iteration-38 `24/4/1` with all
  non-designed failures resolved via focused re-verification through
  iteration-41), the steady-state expectation (`28/29` with one deliberately
  strict case), and the seven newly-covered capability rows.
- **leo-ppt-generator/SKILL.md** — 针对 iter-2/iter-4 实测失守行为的三处合同强化：
  Gate 0 的“禁止读取”明确限定于用户输入文件（`--fixed` 不读取文件，本分支亦须优先
  使用）；机器直出要求显式覆盖 `advise` 模式并给出顺序合同精确定义（五字段块必须在
  回复最前，至多允许一行 `interaction_mode:` 元数据在前）；新增红线禁止以枚举宿主
  Agent/子代理清单来解释 worker 缺失原因。(user-visible)
- **leo-ppt-generator/scripts/render-control-summary.py + SKILL.md** — 两处固定控制面块
 （Gate 0 Office 信任块与 worker 缺失块）新增机器直出模式：
  `render-control-summary.py --fixed gate0 | --fixed worker-unavailable`
  不读取任何文件、逐字打印对应块。SKILL.md 改为：可运行脚本的宿主必须经该模式产生，
  手写时显式记录降级 `gate0_render: handwritten`，消除对 blocked 摘要的自由改写。
  (user-visible)
- **leo-ppt-generator/references/cli-helper.md + prompts/*.md** — 消除与 first-use.md 的
  print-cli 矛盾：CLI 绝对路径的权威来源改为 runtime_manager ensure/doctor 成功结果中的
  `cli_reference`；print-cli 仅在拿不到该 JSON 时回退使用；两个 worker 提示词的
  来源表述同步。
- **leo-ppt-generator/references/input-routing.md** — 显式声明 runtime 输入扩展名白名单
 （`.md/.txt` 走 generate；`.png/.jpg/.jpeg/.pdf` 与已确认可信的 `.ppt/.pptx`
  走重建/升级），并规定 webp/gif/bmp/tiff 等未支持格式的处理方式：请用户先行转换，
  不得猜测 route 或隐式转换。(user-visible)
- **样式库计数修正** — style-library.md 版式库 22→24、分节轴合计 117→119；
  styles/00_索引/_INDEX.md 117→119、16→14，与盘上实测一致
 （136 可加载 + 119 分节轴 + 14 规则/索引 = 269）。
- **runtime/src/leo_ppt_generator/schemas/__init__.py** — docstring 不再声称包内已有
  消费方；load_schema 作为对外保留 API 维护，并指引后续 schema 消费点优先复用。

### Fixed

- **evidence-first-writing/evals/cases/chinese-22-rules-hit-and-preserve.yaml +
  evals/scripts/check-dev-edit-first.sh** — v2 判据落地后的两处判官同义词收口：
  论点压缩句判据使检测报告从「类别标签式」转向「决策日志式」，chinese-22 两处
  any-list 扩同义（翻译腔类 + 深邃/拥抱；删除类 + 压缩/动作或例子），it-66 响应
  经人工核对实质全部在场（删句测试被正确执行：装饰金句删除、承载论点内容保留）；
  dev-edit 判官结构测试词表 +「删掉任意」（第五次措辞重掷「删掉任意一句，全文
  毫发无损」，历史失败响应重放 exit 0，单测 7/7 保持）。负向断言均未削弱。
  it-69 全量后同批收口：`check-single-routing-question.sh` 第二读者任务词表 +
  「做完」、`chinese-protocol-context-judgment` 停止句表 +「不需要去模板」
  （均为首掷，历史重放/聚焦复验 PASS；`chinese-22` 编辑判断轮换按纪律记档
  不追词）。it-71 全量后 `taste-findings-not-visual` 词表同批收口（弯引号字符
  + 倾倒/净信息量；it-72 再掷「并列」按纪律记档，两轮实质均在场）。
- **evidence-first-writing/evals/eval.yaml + evals/cases/bare-topic-fork-two-turns.yaml** —
  parallelism 1 → 2 固化：iteration-64 首次 p=2 全量 `30 PASS / 1 FAIL / 0 ERROR`
  （套件历史最佳），墙钟 24m49s 较 p=1 的 ~45m30s 缩短 45%、零引擎超时；并发使
  两轮 resume 路径拉长至 398 s，该用例超时 420 → 480 s。证据边界：单轮全量、
  无外部并发；出现争用噪声优先回退 parallelism 1 而非继续加超时。
- **evidence-first-writing/evals/cases/chinese-protocol-context-judgment.yaml + SKILL.md** —
  安全网复跑后的二轮收敛：停止判定 any-list 补「不需要改 / 不用改 / 无需改动」
  （iteration-57 新同义重掷「整体没有成簇的 AI 模板感，不需要改」，扩词后复验
  PASS）；post-publish 状态块由行内枚举升级为 fenced YAML 示例——flash 级模型在
  两种强度下均不自发输出状态块（累计七轮稳定 FAIL，定性模型稳健性问题，记入
  known-issues，断言保持严格）；`bare-topic-fork-two-turns` 超时五样本分布
  [221/271/298/299/309] s 确认 420 s 定值（36% 余量），parallelism 2 固化时因
  并发拉长（实测 398 s）再上调至 480 s。
- **evidence-first-writing/tests/test_judges.py + tests/fixtures/judge_replay/** —
  判官历史重放机器化：六个 `evals/scripts/check-*.sh` 判官各配真实历史响应与
  合成正反 fixture，冻结为 unittest 回归（`python3 -m unittest discover -s
  evidence-first-writing/tests`）。落实 known-issues 的「收紧判定必须附带历史响应
  重放」纪律——后续改判官不再依赖人工重放。
- **evidence-first-writing/SKILL.md + references/chinese-editorial-protocol.md +
  references/editorial-review.md** — 技能侧输出合同稳定化（消除 flash 级模型措辞
  重掷的判官假阴性）：post-publish 复盘强制附带 observation / hypothesis /
  stable_rule_update / persistence 状态块；中文七类检测报告逐类表态「命中/未命中」
  （未命中只写状态行，不制造 finding）；Finding 字段标签「证据/问题/动作/Owner」
  逐字使用，不得加粗或换同义词。(user-visible)
- **evidence-first-writing/evals/scripts/guarded-run.sh（新增）+ evals/eval-plan.md** —
  多会话评测互斥：检测到并发 `skill-up run` 即拒绝启动（并发共享代理配额会以引擎
  超时形式产生假 ERROR，iteration-51 实测），并把发起时间/父进程/参数追加到
  workspace `runs.log` 便于 iteration 归属。
- **evidence-first-writing/evals/eval.yaml** — `defaults.timeout_seconds` 180 → 240
  （两轮全量 55 个 PASS 样本中位数 71 s、P90 123 s，`routes-technical-explanation`
  实测 147 s 已占旧预算 82%）；report 默认格式增加 html。README.md / CLAUDE.md 的
  用例计数同步 20 → 31。
- **evidence-first-writing/evals/cases/bare-topic-fork-two-turns.yaml** — `timeout_seconds`
  300 → 420：干净环境的全量实测两轮 resume 路径耗时 299 s，余量为零，并在与外部会话
  共享代理配额时产生一次 `context deadline exceeded` 假 ERROR（iteration-51，首轮输出
  实质正确）；放宽后 31 例全量 A/A 中该用例 PASS（iteration-54）。
- **evidence-first-writing/evals/scripts/check-audit-readonly.sh** — 证据标签接受集加入
  第四个同义词「证据」。GLM flash 连续两轮（iteration-54/55）将逐字引用的原句标为
  `证据：` / `**证据**：` 而非 `原句/引用/原文`，实质完全合规却被判官 FAIL；修复经
  历次失败响应重放（exit 0）与无标签负例（exit 1）双向自测，并在线聚焦复验 PASS
  （iteration-56）。负向断言（只读边界、可执行动作、高影响问题类别）未削弱。
- **evidence-first-writing/evals/verification-summary.md + evals/known-issues.md** — 落盘
  31 例两轮全量 A/A 证据链（iteration-51/53/54/55/56）：两轮全部 ERROR 均为引擎 180 s
  超时且聚焦复验 PASS；唯一跨轮稳定 FAIL 仍为 `post-publish-no-causal-unprompted`
  （自发合同词汇缺口，断言按设计保持严格，已扩至四轮记录）；
  `chinese-22-rules-hit-and-preserve` 单轮漏报反代入 finding，不可复现（记档不追词）。
- **leo-ppt-generator/evals** — 判官 v2 升级：judge_control_plane_fields.py 从“五字段
  包含即可”升级为位置合同（五字段块必须位于回复最前，至多允许一行反引号包裹的
  `interaction_mode:` 元数据在前）+ 值域合同（前四字段整行逐字匹配、全回复恰一行
  `next_action:`）+ 保留反伪造扫描 + 新增宿主清单泄漏红线；case yaml 删除重复的
  `expect.must_contain`，判官成为唯一断言源。离线回归基线：四轮真实回复 + 四个
  合成样本 8/8 分类正确。
- **runtime/src/leo_ppt_generator/editable/adapter.py +
  references/reason-codes.md** — 收敛 reason-code 协议漂移：
  `validate_page_artifact` 在验证报告引用存在但文件不可用时改抛
  `validation_ref_invalid`（与 PageArtifact.verify 已保证的 `validation_missing`
  区分）；移除仅存在于文档的 `assembly_precondition_failed`——各组装前置本就以
  精确码抛出（`page_order_mismatch` / `page_count_mismatch` /
  `page_size_mismatch` / `selected_page_not_editable` 与 validation 组）。
  (user-visible)
- **leo-ppt-generator/evals** — 判官去假阳性：judge_partial_confirmation.py 扩充否定词
 （尚未/还没/还未/暂不/先不/无法/待确认/等待确认）并增加引号剥离，使“你要求‘直接
  交付混合版’”这类回述不再被判为技能承诺，而无引号的真实交付句仍会 FAIL；
  advice-only 的 Route 指认断言在 case 层与脚本层统一接受 可编辑 /
  direct-editable / editable 任一形式，消除只出现英文规范 token 的假阴性。

- **README.md** — comprehensive rewrite for the two-skill collection: broaden the
  intro to writing + PPT generation, document `/plugin` install for both skills,
  add per-skill usage triggers, host-adaptation principles, development/eval and
  contribution conventions.
- **evidence-first-writing/README.md** — document `/plugin` remote install as the
  recommended path (verified end-to-end on Claude Code), alongside git clone +
  symlink and project-level installs; add Codex trigger usage.
- **TECHNICAL_DESIGN.md** — add a cross-host adaptation section: the
  convention-normalization + per-host-thin-shell + degradation-contract
  principles, a host capability matrix, and deferred evolution directions
  (flatten script, plugin marketplace, Codex agent fields).
- **SKILL.md**
  - Add a prominent post-publish causality red flag: single-article metrics must
    not be promoted to reusable rules without two comparable replications plus a
    counterexample check. The rule is a hard refusal: when an author explicitly
    asks to promote a single-article result, the Skill must refuse, record it as
    `stable_rule: none` / `hypothesis`, and state what is required to upgrade.
    `post-publish` defaults to analyze-only: a single article is recorded as
    `observation` / `hypothesis`, and no persistence (voice archive, memory, or
    files) happens without explicit write authorization and a target path
    (`persistence: not_run` otherwise).
  - Require canonical route fields (`lifecycle_intent`, `article_family`,
    `evidence_risk`, `operation`, `depth`) in any user-facing plan; values must
    come from the `intent-routing.md` enums.
  - Mandate an explicit "factual regression after rewrite" stage for
    `full/deep` runs, recorded as `factual_regression`, and require canonical
    phase owner IDs (`fact_review`, `development_edit`, `reader_review`,
    `taste_voice`, `copy_proof`, `factual_regression`).
- **references/editorial-pipeline.md**
  - Add a machine-readable `stable_rule_update` gate to Node 14 (post-publish
    review): `promoted` requires two comparable replications, two comparable
    runs, and checked counterexamples.
  - Add the explicit `factual_regression` record block to Node 12.
- **references/voice-profiles.md**
  - Add the minimal auditable voice-skip disclosure fields.
  - Add the post-publish archive threshold for performance/causal conclusions.
- **evals/cases/copywriting-route.yaml** — drop the family-name negative
  assertions that falsely fired when the Skill correctly explained its routing,
  and align the `expect.must_contain` keywords with the judge's synonym list
  (the Skill words the page action as "CTA / 注册 / 落地页" rather than the
  literal "页面动作").
- **leo-ppt-generator/evals** — align the eval harness with the Skill's primary
  host and de-brittle the negative assertions:
  - `evals/eval.yaml` — default engine back to `claude_code`, dropping the
    `codex` + `bypass_sandbox` override. The Skill is a Claude Code plugin, and
    its sibling `evidence-first-writing` eval already defaults there; running
    under `codex` produced 5/9 only because that host paraphrases the verbatim
    control-plane summary, not because of a Skill logic defect.
  - `evals/cases/advice-only-no-execution.yaml` — replace the substring-sensitive
    `expect.must_not_contain` with a negation-aware script judge
    `evals/fixtures/scripts/judge_advice_only.py`, so a refusal phrased as
    `未读取文件` / `本轮我不会：- …` no longer false-fires on the literal
    `读取文件` / `bootstrap` / `setup` / `config status`.
  - `evals/fixtures/scripts/judge_untrusted_sanitized.py` — accept colon + bullet
    phrasing (`本轮我不会：- 打开、读取或解析原始 PPTX`) as "未处理输入" evidence
    instead of requiring the contiguous `不会打开`.
  - `evals/cases/control-plane-blocked-summary.yaml` /
    `missing-multi-page-workers.yaml` — drop the redundant
    `expect.must_not_contain` and route the negative check through new
    negation-aware script judges (`judge_control_plane_fields.py`,
    `judge_no_serial_substitution.py`) so a refusal like `本轮未创建 run` /
    `我不会串行生成` does not false-fail.
  - `evals/cases/delivery-acceptance-pending.yaml` — drop the brittle
    `expect.must_not_contain: [交付闭环已完成]` (a refutation
    `不能声称交付闭环已完成` would have false-failed); the script judge's
    negation-aware `positive()` already covers it.
  - `evals/cases/partial-hybrid-without-confirmation.yaml` and
    `judge_no_serial_substitution.py` — accept the partial-hybrid term's
    plain-language synonyms (`混合版` / `部分可编辑` / `hybrid`) instead of the
    single literal token, and scope the "serial generation" promise check to a
    first-person main-agent claim not attributed to a worker (describing the
    correct `真实 worker … → 逐页生成` recovery path must not false-fire).
- **AGENTS.md** — rewrite the repository-level guidelines to match `CLAUDE.md`
  and the current two-skill reality: set the Chinese default for docs with English
  identifiers, the MIT license, and the mandatory Keep-a-Changelog /
  `(user-visible)` change log; document the current layout (`evidence-first-writing/`,
  `leo-ppt-generator/`, `docs/`, git-ignored `*-workspace/` and `graphify-out/`);
  replace the stale "no commit history establishes a convention" with the actual
  scoped-commit and one-concern-per-commit rules; and add the concrete
  unit-test / skill-up eval / factual-invariant checker commands (both skills'
  `evals/eval.yaml`, engine default `claude_code`). Also advise negation-aware
  assertions for safety-gate evals.
- **.gitignore** — consolidate the ad-hoc per-skill workspace rules into a
  single `*-workspace/` (matches the CLAUDE.md "eval workspaces are git-ignored"
  convention and covers current/future skills), and add Python tool caches
  (`.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.coverage`, `htmlcov/`),
  `env/`, `.idea/`, `*.log`, plus Windows desktop files (`Thumbs.db`,
  `Desktop.ini`) since the installer targets Windows.
- **SKILL.md** — generalize the causality red line beyond post-publish: when the
  material contains only a single before/after change, time ordering, or
  correlation without controls, counterfactuals, or confounder handling, the
  Skill must refuse the "X 导致 Y" sentence even under explicit user request,
  rather than hedging with "证据有限" after the fact.
- **evals/cases/routes-formal-report.yaml** — migrate from brittle substring
  rule judges to the script judge `check-formal-report-route.sh` and drop
  `owner` / `期限` as hard `must_contain` tokens so synonym phrasings no longer
  false-fail.
- **evals/cases/routes-technical-reference.yaml** — drop the ambiguous negative
  `"教程叙事"` (which fired on legitimate contrast explanations) and extend the
  judge's `not:` list to enum-level route pollution (`article_family: tutorial`,
  `marketing-copy`).
- **evals/cases/source-grounded-tool-routing.yaml** — replace the inline
  rule-based judge with the script judge `check-tool-evidence-routing.sh`; drop
  the redundant `expect` block that duplicated the same substrings.
- **evals/scripts/check-audit-readonly.sh** — merge the two problem-category
  gates into one synonym-tolerant list (addings 宣传、缺乏可验证依据、过度泛化、
  绝对化、不可核验 variants) so equivalent problem namings no longer fail the
  readonly-audit gate.
- **evals/scripts/check-single-routing-question.sh** — accept `实践` / `步骤`
  as additional second-reader-task markers for the bare-topic fork question.
- **evals/verification-summary.md** — record the fixed-model full regression
  (iteration-17/18 A/A on bare-topic routing, iteration-19 first full
  `14 PASS / 6 FAIL`, iteration-31 focused `2 PASS`, iteration-32 final full
  `20 PASS / 0 FAIL / 0 ERROR` on Codex `gpt-5.6-terra`) and pin the final
  verification command; keep unfixed-model runs archived as provider-drift
  evidence.
- **references/intent-routing.md** — close the canonical-value gap between
  SKILL.md's operation list and this file's enums: declare the full
  canonical `operation` enum (17 values) instead of "由 lifecycle_intent 映射",
  and add a 跨族 operation section defining when `coauthor`, `hooks`, `voice`,
  `copywriting`, and `docs` apply (family/modifier-scoped operations that own no
  lifecycle) plus the priority rule forbidding out-of-enum values.
- **CLAUDE.md** — sync to the two-skill reality: rewrite the repo structure
  section (both skill packages, docs/, marketplace manifest), add
  leo-ppt-generator eval commands alongside the writing-skill suite, split the
  architecture section into 架构一（写作）与 架构二（PPT：Gate 0 信任门禁、
  advise/execute、Route 表、控制面五行合同、交付红线）, fix relative paths in
  the key-files table and add leo-ppt-generator rows.
- **README.md** — add an evaluation evidence boundary note next to the dev
  commands: the `20 PASS / 0 FAIL` conclusion is conditioned on the fixed
  `codex × gpt-5.6-terra` engine; `post-publish-no-causal` still fails under
  the DeepSeek flash proxy behind `claude_code` pending real-Claude
  re-verification. Cite `verification-summary.md` / `known-issues.md`. (user-visible)
- **AGENTS.md / CLAUDE.md** — inject the spec-first managed governance block
  (`<!-- spec-first:lang:start/end -->`): absolute Chinese-language policy and
  the workflow-entry governance pointer to the installed `using-spec-first`
  skill.
