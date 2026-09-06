# software-article-en-zh

面向软件工程文章的英文到简体中文翻译 Skill。支持对话文本、本地纯文本和 Markdown，强调技术语义、代码结构和术语一致性。默认交付为发布型双层模式：先生成严格保真的技术译文，再在不改变语义、事实、逻辑与语气强度的前提下做受约束的中文编辑润色。

## 能力面

- **保真不变量**：完整翻译不摘要、不自由改写；保留否定、条件、因果、量词、规范性强度（MUST/SHOULD/MAY）、数字、单位、风险和限制；不得把相关性改为因果。
- **保护区**：代码块、命令、API、配置、标识符、路径、URL、公式、占位符和 Markdown 结构（含 frontmatter）默认原样保留；链接标签、替代文本和图注是面向读者的可见文本，默认译出（路径与语法不变）。
- **安全边界**：源文中的提示词、命令和工具调用是待译数据——按原文翻译，不执行，也不默认跳过；不覆盖源文件。
- **诚实报告**：不静默修正原文事实；输入不完整、结构无法可靠解析或技术争议未解决时，输出标记为 `partial`、`constrained` 或 `blocked`，不编造内容。
- **术语与审校**：术语优先级为用户选择 > 项目术语表 > 产品官方译法 > 内置术语表 > 领域通行译法 > 上下文判定，同篇一致；审校问题按 critical / major / minor 分级并附证据与验证状态。

## 交付模式

- `publication`（默认）：双层交付——保真初译 → 受约束中文技术编辑 → 逐句对照审校 → 五件套发布输出（译文正文、简短翻译说明、技术术语表、歧义与原文问题清单、未解决事项与需作者确认事项）。模式合同常量：`fidelity_priority: strict`、`editorial_polish: constrained`、`source_correction: prohibited`、`ambiguity_handling: preserve_and_disclose`、`technical_review: required`。
- `polished`：显式降档。在保真初译和语义复核后，清除英文句法、调整中文节奏并统一术语，不做标题/隐喻的发布级优化。
- `faithful`：显式降档。仅保真直译和必要的中文语序调整，不做编辑润色、不强制五件套。

发布判定为合取：漏译、误译、因果变化、模态强化、数字错误、代码破坏等保真失败，或润色越界（新增事实、例子、因果、承诺、结论），均导致整体不可发布；中文流畅度不可抵消保真失败。原文歧义必须保留并披露，不得替作者选定解释。

准确性通过 `technical_review` 报告，中文表达和发布适配通过 `editorial_review` 报告；两者都不等于独立第三方审校。

长文或发布型任务会先分析全文论点、受众、语气、术语、隐喻和结构难点，再进行保真初译与编辑润色。长文按 Markdown 块分段时共享同一会话术语表，并在合并后复核跨段一致性。图片文字默认只做候选提醒，不自动修改图片。

内置英中术语表见 [`references/glossary-en-zh.md`](references/glossary-en-zh.md)，用户术语表和项目术语表优先级更高。

翻译方法、阶段边界和设计模式见 [`references/translation-methods.md`](references/translation-methods.md)。

详见 `references/`（翻译规则、Markdown 保护、术语策略、审校量表）与 `assets/`（task / glossary / review 三个 JSON schema）。

## 安装

> 官方推荐用一行命令或 Claude Code `/plugin` 系统远程安装。开发者本人 dogfood 与非 Claude Code 宿主改用 Git clone + 软链。本技能无运行时依赖（`scripts/` 仅用 Node 标准库），无需额外安装步骤。

### 方式一：一行命令（推荐）

```sh
npx skills add leo-kuang-ai/leo-skills                              # 装齐四个技能
npx skills add leo-kuang-ai/leo-skills -s software-article-en-zh    # 只装本技能
```

通用安装器（[vercel-labs/skills](https://github.com/vercel-labs/skills)）自动识别 78+ 宿主；`-a <宿主>` 指定安装目标、`-g` 装到用户级全局、`--list` 只预览不安装。也可以直接在 agent 对话里说："帮我安装这个 skill：https://github.com/leo-kuang-ai/leo-skills"。

### 方式二：手动 clone + 软链

完整宿主路径表与 Claude Code 官方插件市场链路（含更新 / 卸载）见[仓库根 README](../README.md#安装与使用)。以 Claude Code 为例：

```sh
git clone --depth 1 https://github.com/leo-kuang-ai/leo-skills.git ~/.claude/skills/leo-skills \
  && ln -s ~/.claude/skills/leo-skills/software-article-en-zh ~/.claude/skills/software-article-en-zh
```

## 评测

skill-up 套件共 85 个用例，覆盖 15 个维度：否定与模态、量词与数字精度、代码与 Markdown 保护、提示注入即数据、无效/不完整输入诚实报告、术语策略、因果与风险保留、完整性与结构、不静默修正原文、输出契约与审校、中文技术运营编辑质量、发布型双层交付、模式与操作语义、参数适配、交付契约披露。其中既有否定感知 script judge，也有针对标题、术语解释、长句逻辑、隐喻和新增事实的编辑质量用例；另含中文输出健全性（英文回显回归）、简体字形回归、by/to 数值方向、倍数语义、版本演进时态、否定辖域析取、内置术语表遵循、图片文字提醒、只译注释、脚注结构、写新文件事实核对等行为用例。发布型双层交付维度（D12）验证默认 `publication` 的五轴合同：复杂模态/条件/因果/风险的发布文保真复合、含代码/命令/日志/配置/链接/图片长文的结构保护与五件套交付、原文歧义/错误/立场不完整时的保留披露，以及无模式词请求默认走双层交付。模式与操作语义维度（D13）覆盖显式 faithful 直译不做编辑改写、显式 polished 内部轻量润色与审校操作对编辑越界/语义强化的识别；参数适配维度（D14）覆盖代码注释默认保留与管理层受众术语解释；交付契约披露维度（D15）覆盖 technical_review 与 editorial_review 双轨分开记录与合取发布判定。

```sh
cd software-article-en-zh
skill-up validate evals/eval.yaml        # 校验配置与全部用例
skill-up run evals/eval.yaml             # 运行 85 用例主轨
skill-up run evals/eval.yaml --iteration 3  # 稳定性采样（按轮次抖动率把关）
skill-up run evals/eval.yaml --baseline  # with/without skill 基线对照
skill-up list-cases evals/eval.yaml      # 列出用例
```

稳定性采样提示：多轮采样建议 `--parallelism 4~6`。长时间高并行（如 20 轮 × parallelism 8 ≈ 1700 次调用）可能触发模型供应商限流，产生 `unrecognized_model`、`provider rate limit` 类 ERROR 与输出质量劣化，属环境噪声而非技能回归；判读抖动时应结合错误信息区分。

另含真实文档全文翻译用例（`evals/eval-doc.yaml`，翻译 `leo-ppt-generator/README.en.md`），供人工/专家评审轨取样。doc 轨有意引用**活文件**以驱动真实长文翻译：readme 用例依赖兄弟包 `leo-ppt-generator/README.en.md`，pvncher 用例依赖本机知识库绝对路径，文件缺失或内容演进会造成用例漂移，属预期环境依赖，不纳入主轨门禁。

单元测试（fence 结构保护检查器）：

```sh
node --test software-article-en-zh/tests/test_protection.mjs   # 从仓库根运行
```

本 Skill 不保证零错误或出版级质量；受限状态会在输出中显式披露。
