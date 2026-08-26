# 上游源码审计

## 范围冻结

审计时间：2026-08-26。根目录：`/Users/kuang/leo-ppt-verify/参考`。目录无 CodeGraph。

所有 9 个仓库均为干净工作树。全部 1,016 个 tracked 非 `.git` 文件已逐文件读取字节并计算 SHA-256；总计 43,944,583 bytes。二进制文件只做路径、类型、大小和哈希账本，不从图片内容推导写作规则。`writing-agent` 的 306 个 vendor 实例是三份同步投影中的 Markdown 渲染器与代码主题；一方/文档实例 325 个，按内容哈希去重后 204 份。

| 仓库 | Commit | 文件 | 文本/二进制 | 许可证 | 主要能力 |
|---|---|---:|---:|---|---|
| Aboudjem-humanizer-skill | `7ef05e2f8b884f1025e557af06aded51d1971e99` | 80 | 74/6 | MIT | 55 模式、误报保护、透明统计 CLI |
| Hello-SimpleAI-chatgpt-comparison-detection | `1f8c15c28f87e09a5abfd86ee6e15005dc7d2119` | 15 | 15/0 | 根目录无许可证 | HC3 语料、分类器、OOD 检测研究 |
| alchaincyf-nuwa-skill | `fe0374687037c4cc51a65c1e0c145afe2981dc69` | 159 | 130/29 | MIT | 多源风格/思维提炼、诚实边界、独立评分设计 |
| blader-humanizer | `e2e92e7b4b8229253ed5c8e81dc65463fdeddda5` | 9 | 9/0 | MIT | Wikipedia 模式、事实保护、样本优先 |
| brandonwise-humanizer | `4b9b9bee384aea139f599133d2de1e1ceaee71a3` | 47 | 47/0 | MIT | 程序化模式、统计、目录扫描、前后比较 |
| dongbeixiaohuo-writing-agent | `7d2bc3ed2f7a779098895a09bd0e369868c9868f` | 631 | 585/46 | MIT | 全流程编辑状态机、证据/哈希门禁、复盘 |
| hardikpandya-stop-slop | `8da1f030185bdfe8471220585162991eaeb970e9` | 7 | 7/0 | MIT | 英文套路清理、直接表达、false agency |
| leonxlnx-taste-skill | `ccbc15639c97057cbfcf32ecebc38ef716e4bb37` | 64 | 47/17 | MIT | 前端视觉反模板，不是文字审美工具 |
| op7418-Humanizer-zh | `91f3d394db8419c20d67ebe22a96cf8fee0a404b` | 4 | 4/0 | MIT | 中文本地化规则与 stop-slop 吸收 |

## 五类能力结论

### 痕迹检测

适合机械化：代码/引语遮蔽、词和结构定位、Unicode/引用标记泄漏、描述性节奏指标、前后 diff、短样本降级。不能机械化：作者身份、中文风格真实性、论证质量和文章价值。HC3 证明检测依赖语料、语言、模型和领域；其 OOD 脚本本身说明跨域是独立问题。当前快照无许可证，不能复制代码或词表。

### 套路清理

可靠动作是先诊断、删除低信息内容、恢复行为主体和具体对象、去掉对话残留，再局部改写。绝对禁词、全删副词、全禁被动和统一破折号禁令会误伤体裁与作者，应服从上下文和声音证据。自动替换只能覆盖语义风险低的窄规则。

### 声音校准

强机制是作者锚点、跨样本证据账本、量化指纹、风格内核、适用边界、陌生主题和隔离盲测。Nuwa 的“跨域复现/生成力/排他性”适合提炼判断方式；Writing Agent 的 `legacy_unverified/verified` 状态适合治理。人物扮演、样本外履历和静态关键词计数不进入用户声音模型。

### 审美判断

参考目录没有一个经过验证的文字审美引擎。`taste-skill` 是前端设计 Skill。可迁移的是 brief inference、anti-default、audit-first、contextual rules、可解释选择和 preflight，而不是视觉规则。文字品味必须由选择、密度、具体性、张力、推进、记忆点和克制重新定义。

### 全流程写作

Writing Agent 提供最完整的节点和机器门禁：选题、brief、立场、调研/证据、结构、读者价值、具象化、标题、开头、草稿、分层审稿、平台测试、Humanizer、最终事实、交付、diff 学习和发布数据。应吸收错误所有权、产物状态、事实回归和跨样本学习；不照搬公众号特定的“打谁的脸”、固定候选数、19 阶段停机和强制传播情绪模型。

## 验证证据

- Aboudjem CLI：26/26 tests passed。
- blader：package validator passed。
- writing-agent：177 tests 中 171 passed、2 skipped、6 因未安装 `tsx/typescript` 失败；Python syntax、workflow contract、runtime sync 通过。
- Brandonwise：缺本地 `vitest`，未运行；只确认源码测试合同，不能声称 green。
- 其他仓库没有对应的本地自动化行为测试；静态脚本和示例不等于效果证明。
- `ast-grep-outline` Skill 与本机 CLI 版本不匹配，`outline` 子命令不可用；使用全文件哈希、`rg` 结构扫描、逐文件直读和测试交叉替代。

## 对当前 Skill 的约束

1. 顶层价值链优先于工具分类，Humanizer 不得拥有全文质量。
2. 事实核查必须在改写前后出现，最终状态绑定当前标题和正文。
3. 中文统计只作描述性线索，不套英文阈值。
4. 声音档案具有证据状态，未验证档案必须降级。
5. 代理读者测试、热点评分和检测分数不能冒充 field outcome。
6. 只有真实、可比、跨文章重复的发布结果才能升级为稳定规则。
