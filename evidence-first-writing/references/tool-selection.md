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
- 选题热点素材源：可考察 `ourongxing/newsnow`（MIT，2026-08-31 快照核验）：66 源实时聚合（微博/知乎/baidu/v2ex 等），公共 JSON API `GET /api/s?id=<sourceId>` 返回 `{status,id,updatedTime,items}`，按源注册表的 interval 控频。仓库本体是 UI 应用，本技能只消费其 API 作选题素材，机制不迁移；MCP 接入需另行部署外部 npm 包 `newsnow-mcp-server`（BASE_URL 指向自部署实例），该仓库内无 MCP 实现。
- 中英混排与标点的排版诊断：双轨。轻量与文章内场景优先用内置 `scripts/check_layout.py`（零依赖，CJK 标点邻接+密度配额+段落节奏，规则口径部分引自 autocorrect，快照 2026-08-31）；整仓/多文件类型（28+ 种）CI 场景可考察 `huacnlee/autocorrect`（MIT，Rust 工具，2026-08-31 快照核验）：确定性规则自动纠正 CJK 与英文间空格、全半角标点与拼写，lint 输出 diff/JSON 并支持 ignore 文件与 CI 集成。两者输出均只作诊断线索，不作门禁；渲染侧约束（CSS 安全区/禁区核对表与字号行高速查）见 [layout-contract.md](layout-contract.md)；公众号导出容量经验值（来源 md-wechat，MIT，快照 2026-08-31）：视频 ≤7.5MB、正文 ≤10M。
- AI 检测工具：只把输出当定位线索，不能当作者身份裁判。
- `Hello-SimpleAI/chatgpt-comparison-detection`：适合了解 bilingual corpus、分类器和 OOD 风险；当前快照根目录没有许可证，禁止复制其代码或词表，且 2023 语料不能代表当前模型分布。

常见中文组合：`Humanizer-zh -> shuorenhua -> 声音档案校准 -> 事实回归`。英文可用 `blader/humanizer` 或 `stop-slop`，需要量化线索时再考虑带统计输出的实现。组合不是必需项；当前 Skill 自身已有可独立执行的合同。

## 发布与分发执行器

- **wenyan-mcp**（文颜排版 MCP，Apache-2.0，npm 包 `@wenyan-md/mcp`）：把 Markdown 排版为公众号/知乎/头条样式并发布到平台草稿箱。提供 `publish_article`/`list_themes`/`register_theme`/`remove_theme` 四个工具；大文档优先用 `file`/`content_url` 参数传入，不内联全文。前置条件：公众号 APPID/SECRET 与 IP 白名单，或使用远程 server 模式。定位：发布执行器，正式群发由用户完成。
- **Wechatsync**（GPL-3.0，仅作外部调用，不集成其源码）：一次排版分发到 29+ 平台；形态为官方 CLI `@wechatsync/cli` 配合 Chrome 扩展，依赖浏览器登录态，默认写入草稿。命令面（2026-08-31 快照核验）：`wechatsync sync article.md -p juejin,zhihu --dry-run` 多平台同步、`wechatsync platforms --auth` 查登录态、`wechatsync extract -o article.md` 网页转 Markdown；安全模型草稿优先，CLI 与扩展仅 localhost token 通信，数据不离开设备。风险：走各平台 web 内部 API，存在验证码与风控不确定性。GPL 许可证决定本技能只调用、不复制其实现。
- **XiaohongshuSkills**（MIT）：小红书 CDP 自动发布与 content-data 数据回流（曝光、点击率等表），回流数据按 observation 喂 post-publish 复盘，禁止段落级归因。前置：用户自行安装、测试号先行纪律；已知多账号场景存在串号缺陷。定位：可选执行器，技能只消费其导出数据。
- **xiaohongshu-mcp**（Go 实现的小红书 MCP server，Apache-2.0，2026-08-31 快照 commit `332d196854a9` 核验）：13 个 MCP 工具覆盖登录态管理、图文/视频发布（`schedule_at` 定时、`visibility` 可见性、商品绑定）、评论读写与平台级 `search_feeds`/`list_feeds` 读取（keyword + 综合/最新/最多点赞等排序）。标准 MCP 协议宿主无关，区别于 XiaohongshuSkills 的自装 CDP CLI 形态（后者仅回流自身 content-data）。其 `humanize/` 目录是浏览器操作拟人化（鼠标/延迟模拟），与文本去 AI 味无关。定位：平台级读取 + 发布执行器，同受测试号先行与平台风控纪律约束。
- **md2wechat-skill**（公众号 Markdown 排版发布 CLI，40+ 主题，BUSL 1.1 改——Source Available，Additional Use Grant 仅限个人非商业创作发布，2026-08-31 快照核验）：Markdown 检查 → 排版 → 封面配图 → 预览校验 → 推送草稿箱全链路，提供 JSON discovery 供 Agent 稳定调用。**许可证为 BUSL 修改版：本技能只登记名称与能力面，不复制其任何代码、模板、主题或文本。**

以上执行器都只负责排版、分发与数据动作；事实核对、授权与渠道语域门禁仍由本技能合同约束，安装前按下方清单核验当前维护状态。

## 安装或执行前

1. 打开当前项目主页和 Skill 源码，不只看名称或榜单。
2. 核对最近维护时间、许可证、安装命令、网络请求、写文件范围和隐私边界。
3. 先用固定小样本运行 detect 或 dry-run；冻结事实不变量。
4. 比较命中、误报、事实漂移和声音变化，再决定是否用于正文。
5. 外部工具失败时回到本 Skill 内置流程，不降低事实保护门禁。
