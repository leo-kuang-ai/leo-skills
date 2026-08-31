# 外部工具选型

仅在用户要求选择、安装或调用外部工具时读取。先按写作链路中的失败环节选工具，再核对当前仓库、许可证、维护状态、语言支持和输入输出；关注度与模式数量会漂移，不能仅凭榜单排序。

## 按问题选择

| 类型 | 解决什么 | 当前判断 |
|---|---|---|
| 痕迹检测 | 先定位模式、统计与泄漏，不急着改 | `Aboudjem/humanizer-skill`、`blader/humanizer`、`brandonwise/humanizer` 和 `Humanizer-zh` 源码已核验；HC3 是研究代码，不是通用编辑裁判 |
| 套路清理 | 删除连接词、套话、空泛结构和英文 slop | `stop-slop`、已核验 Humanizer 可作参考；`shuorenhua`、`ai-flavor-remover` 源码不在本次目录，只能列候选，不能声称已验证 |
| 声音校准 | 学作者的判断方式、素材选择、节奏与边界 | 当前 Skill 的 `voice/train-voice/evaluate-voice`、Nuwa 的证据提炼方法和 Writing Agent style-modeler 已核验 |
| 编辑品味 | 判断选择、密度、张力、推进、记忆点和克制 | 使用 `editorial-taste.md`；本次 `taste-skill` 实际是前端视觉 Skill，不用于审文章 |
| 全流程写作 | 从问题、证据、结构、成稿到发布与学习 | 使用 `editorial-pipeline.md`；Writing Agent 作为节点与门禁参考，不照搬固定 19 阶段 |
| 发布分发 | 排版、多平台分发与数据回流 | 见下方「发布与分发执行器」；只执行动作，不接管事实与授权门禁 |

- 单篇中文稿的通用检测与基础改写：优先考察 `op7418/Humanizer-zh`。
- 中文互联网黑话、小红书/知乎/公众号语域：在通用检测后考察 `shuorenhua`。
- 英文默认模型腔和 Wikipedia 风格模式：考察 `blader/humanizer`。
- 需要较大模式库、命名 voice 与分数线索：考察 `Aboudjem/humanizer-skill`。
- 英文长文统计指标、词汇重复和黑名单：考察 `brandonwise/humanizer`。
- 只清理英文 filler、公式转场和空洞形容词：考察 `stop-slop`。
- 长期学习用户本人或获授权作者的表达：使用本 Skill 的 `voice/train-voice/evaluate-voice`。Nuwa 可参考其多源证据与诚实边界，但不使用在世人物扮演作为写作捷径。
- 标题、开头、关键转折和结尾的文字审美：使用本 Skill 的编辑品味门。`leonxlnx/taste-skill` 当前源码面向前端设计，不属于文字审美执行器。
- 长期账号的选题到发布全流程：可考察 `writing-agent` 类系统，不用于临时改一段文字。
- AI 检测工具：只把输出当定位线索，不能当作者身份裁判。
- `Hello-SimpleAI/chatgpt-comparison-detection`：适合了解 bilingual corpus、分类器和 OOD 风险；当前快照根目录没有许可证，禁止复制其代码或词表，且 2023 语料不能代表当前模型分布。

常见中文组合：`Humanizer-zh -> shuorenhua -> 声音档案校准 -> 事实回归`。英文可用 `blader/humanizer` 或 `stop-slop`，需要量化线索时再考虑带统计输出的实现。组合不是必需项；当前 Skill 自身已有可独立执行的合同。

## 发布与分发执行器

- **wenyan-mcp**（文颜排版 MCP，Apache-2.0，npm 包 `@wenyan-md/mcp`）：把 Markdown 排版为公众号/知乎/头条样式并发布到平台草稿箱。提供 `publish_article`/`list_themes`/`register_theme`/`remove_theme` 四个工具；大文档优先用 `file`/`content_url` 参数传入，不内联全文。前置条件：公众号 APPID/SECRET 与 IP 白名单，或使用远程 server 模式。定位：发布执行器，正式群发由用户完成。
- **Wechatsync**（GPL-3.0，仅作外部调用，不集成其源码）：一次排版分发到 29+ 平台；形态为 CLI `@wechatsync/cli` 配合 Chrome 扩展，依赖浏览器登录态，默认写入草稿。风险：走各平台 web 内部 API，存在验证码与风控不确定性。GPL 许可证决定本技能只调用、不复制其实现。
- **XiaohongshuSkills**（MIT）：小红书 CDP 自动发布与 content-data 数据回流（曝光、点击率等表），回流数据按 observation 喂 post-publish 复盘，禁止段落级归因。前置：用户自行安装、测试号先行纪律；已知多账号场景存在串号缺陷。定位：可选执行器，技能只消费其导出数据。

三个执行器都只负责排版、分发与数据动作；事实核对、授权与渠道语域门禁仍由本技能合同约束，安装前按下方清单核验当前维护状态。

## 安装或执行前

1. 打开当前项目主页和 Skill 源码，不只看名称或榜单。
2. 核对最近维护时间、许可证、安装命令、网络请求、写文件范围和隐私边界。
3. 先用固定小样本运行 detect 或 dry-run；冻结事实不变量。
4. 比较命中、误报、事实漂移和声音变化，再决定是否用于正文。
5. 外部工具失败时回到本 Skill 内置流程，不降低事实保护门禁。
