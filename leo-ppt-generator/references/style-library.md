# 风格库

在视觉方向确认前只接收有界候选摘要，用户选定后才读完整 brief 并经确定性组合器生成视觉投影；不得仅凭名称推断，不得把原始 catalog 或 source/taxonomy 元数据复制进 deck_spec.style。

## 资产与检索入口

当前数量只以 [生成计数](styles/generated/counts.md) 为准；[名称/别名入口](styles/generated/by-name-alias.md) 和 [家族入口](styles/generated/by-family-001.md) 来自同一 source_digest。
原始 brief、版式 sidecar、规则、轴与参考池独立分类，coverage 是摘要字段覆盖，verification 按 schema/layout/visual 分范围报告，不能互相替代。
固定顶层内置、来源子目录和用户目录是存储位置；多 family 关系是分类数据，不用颜色相似度自动合并身份。具体查询与选择守卫见 [模板推荐合同](style-recommendation.md)。

- [设计体系](styles/00_索引/设计体系.md)：多轴组合原则。
- [视觉风格配对](styles/00_索引/视觉风格配对.md)：随包风格的既有配对；不能因 user 同名就继承。
- [通用设计规范](styles/00_索引/通用设计规范.md)：上位护栏。
- [版式调度](layout-dispatch.md)：角色、容量、节奏与独立预检；无用户专属配置时仅声明通用布局。
- [扩展模板](styles/00_索引/style-extension-template.md)：新增/修订 brief 的治理流程。

## 元数据与兼容

source 和 taxonomy 是可选的 L0 字段。旧 brief 缺字段继续合法；已声明字段必须过 schema 和实际 lint。许可 unknown 不表示有问题，也不表示已核验；本期不启用许可排除。
taxonomy.families 是多归属，visual_family 若有必须属于该数组；不得猜测主身份。
scope=builtin 包含旧 source=builtin/reference 两种随包位置；scope=user 来自当前 home。角色 reference 与旧 source=reference 不是同一概念。

## 查询与降级

execute 先运行只读索引检查，再通过 `style list --summary --filter <名称或别名>` 与 `style load <解析后的名称> --summary` 核对真实来源。
两个步骤使用同一 home；原始 file_sha256 与 loader 的 style_content_digest 口径不同，不作直接相等断言。
摘要只能比较与消歧，不能作为渲染正文；选定后通过同 home 的完整 load 和带 expected-selection 的 render 组合。
索引缺失或损坏时，summary 查询直接读源且不依赖 generated；advise 不执行工具，按 SKILL.md 的固定降级说明结束本次目录查询。
不得自动修改用户安装目录，也不将用户摘要回写随包索引。

## 模板确定性注入（`style render`）

选定视觉风格、论证模式、版式与信息图类型后，**必须**用 `style render` 得到
确定性注入内容，写进 `deck_spec.style` / `slides[].layout`；不得自由文本手写：

```text
"$LEO_PPT" style render <视觉风格> --mode <论证模式> \
    [--layout <版式> --image-type <信息图类型>]
```

`render` 合并：视觉风格 brief + 配对图片渲染的 paste-ready 段落 + 论证骨架 +
版式骨架 + 信息图骨架；同输入逐字节确定。`style render --list-templates` 枚举
各轴可用名。注入链路：`deck_spec` → `prepare_slide_prompts.py` 的 Global Style /
Layout 块 → 每页图片生成 prompt。

**图片生成路线的构图注入**：骨架文本是 CSS 方言（`.cell-6`、`min(11.6vw,19vh)`）,
扩散模型读不懂类名与 vw。为图片路线注入 `deck_spec.slides[].layout` 时,用
`--materialize` 旗标——`compose_layout` 会附加 `composition_hint` 字段:CSS 类名被
剥离、vw/vh 译为「约 N% 画宽/画高」,输出为生图模型可执行的构图区块描述。缺省
(不带旗标)输出与不带该字段时逐字节一致;可编辑路线继续消费原始 CSS 骨架。
解析失败(空骨架/歧义名/规则文档误引)时 `render` 返回 `template_store_error`
族的稳定 reason code,不静默注入空版式。

**注入通道对照（哪些 brief 字段真正进生图 prompt）**：`compose_style` 输出键
白名单为 `name / visual_direction / color_palette / typography / layout_patterns`
（+条件键 token_sidecar / brand / guardrail / layout_lock / image_rendering /
mode / style_anchor）；08 轴以 `paste_ready` 段落与「线条·纹理·深度」表整段注入。
`rendering_constraints` / `negative_prompt` / `visual_elements` / `canvas` **不在
机器注入键内**——它们是 agent 桥接词表，组页时按
[deck-master.md](deck-master.md) 母版要素 3「风格约束摘抄」摘入页级视觉行，否则
不进生图链路；00_索引 治理文档（通用设计规范/设计体系）约束 agent 行为、无注入路径。

## 品牌 VI 注入（style render --brand）

- `"$LEO_PPT" style render <风格> --brand <名称>`：解析顺序＝
  `${LEO_PPT_HOME}/brands/<名称>.md`（用户企业 VI 优先）→
  `10_品牌身份/<名称>.md`（内置预设，`--list-templates` 可查）。
- 合并优先序（合同）：用户品牌 HEX > 用户 colors > 风格默认；浅底正文对比度
  ≥4.5:1 硬校验，不达标报 `brand_contrast_insufficient` 并给最近合规建议色。
- `--brand` 隐含开启风格锚附录（`--anchor` 可单独开启）：HEX/字族/渲染锚
  逐字节注入每页 prompt，防多页漂移；默认路径输出字节不变。
- **brand_assets 契约块（全部可选 + 程序化降级）**：仅 `logo_primary` 缺失时
  向用户索取；`logo_monochrome`/`safe_area`/`min_size` 缺省自动处理（生成
  去色反白变体、按画布比例推导），`font_license_note` 缺省 not-recorded。
  logo 作为 required asset 逐页注入，组装复验核对位置/尺寸/变体逐页一致。
- **用户 VI 保存**：复用 save_style 通道，保存到 `${LEO_PPT_HOME}/brands/`
  （HEX/logo 引用/字体/语气），生成时优先读取。
- 内置品牌预设 `verified_at` 多为"未核验"近似值：交付前必须向客户索取官方
  VI token 或按手册核验，未核验不得声称"符合品牌规范"。

## 暗场与无障碍预设

- `style_variants` 支持 `dark-deck` 预设（发布会全深色）：全页统一盖 variant、
  深色 palette 推导（中性色反转/强调色提亮）、深底对比度复检（正文 ≥4.5:1）。
- 图表轴注入色盲安全序列（明度 L* 间距 + 双线索铁律）；关键信息不得只靠颜色。

## 变体第二维度：明度 × 饱和度六分组

`variant_of` 家族归并的主维度是"同板场景变体"（R-66）；在此之外声明第二
描述维度（源 OfficeCLI morph-ppt styles/INDEX.md 六分组法，快照
2026-08-31）：风格/变体可标注一个明度×饱和度档位，供暗场切换与配对检索
预筛：

| 档 | 判据 | 典型场景 |
|---|---|---|
| `bw` | 黑白灰零饱和，强调色至多一档 | 学术、咨询极简、印刷风 |
| `dark` | 深底为主 | 发布会、高端商务、科技 |
| `light` | 浅底为主 | 通用汇报、教学课件 |
| `mixed` | 明度跨档块面对切 | 品牌发布、建筑、创意 |
| `vivid` | 高饱和多色 | 活动庆典、儿童教育、营销 |
| `warm` | 暖色温主导 | 生活方式、文创、有机品牌 |

纪律：本维度只作标注与预筛，不新建条目、不占风格配额、不改 `variant_of`
主维度语义；档位写进 brief 散文 `visual_direction`（无专用 schema 键），
`dark-deck` 预设与色盲安全序列照旧优先。

在此之外还可标注**质感档**（clean/grid/organic/pixel/paper/glass/glow 七档，
来源 baoyu-skills dimensions 扩写）：同样只作标注与预筛，档位写进 brief 散文
`canvas.background`（与明度档写 `visual_direction` 分工），七档判据、非穷举
纪律与忌配表见 [`styles/00_索引/设计体系.md`](styles/00_索引/设计体系.md) §3a/§3b。

## 照图做（参考图 → 风格 brief）

用户提供风格参考图时（指定优先序高于推荐，见
[`style-recommendation.md`](style-recommendation.md)）：

- 只提取可复用视觉系统：配色、字重气质、纹理、留白密度；不提取业务正文、人脸、
  可识别标识、水印。
- 提取结果写成 style brief 写入 `deck_spec.style`，来源标注"参考图提取"。
- 验证复用既有样张里程碑：样张产出时与参考图**并排呈现**供"像不像"比对，用户
  确认后锁定；满意可按下节沉淀为自定义风格。
- 两张参考图＝样张双生直入口（默认与第二参考各出一张同内容样张二选一）。

## 保存自定义风格

用户要求保存当前风格时，先检查真实最终页面，至少覆盖封面、普通内容、复杂机制或
数据页、结尾页。只提取可复用视觉系统，不保存业务正文、个人信息、客户数据或必须
依赖的私有图片。自定义风格保存到 `${LEO_PPT_HOME}/styles/<style-name>.md`，不得
修改 Skill 安装目录。重名时先确认覆盖、合并或改名；后续生成优先读取同名用户
风格，再读取内置风格。

勘察确认未入库的源矿按使用信号补充，登记见 [`style-candidates.md`](style-candidates.md)。

## 渐进治理债（登记在案，不阻塞）

- **negative_prompt 渐进补齐**：约 126 份早期批参考 brief 的 negative_prompt 不足
  3 条（lint 仅对顶层 11 套内置强制）。补齐节奏：该风格被点名命中或触发渲染修订时
  顺手补至 3-5 条针对性负面词，不专项批量重写（避免无真实风险的模板化填充）。
  辅助工具：`scripts/draft_negative_prompts.py` 从 brief 自身 avoid/constraints
  确定性派生草案，并可叠加语料池取词（`--pool` 裸旗标用内置池
  `styles/00_索引/负面语料参考池.md`，家族组按 brief 所在目录名匹配，通用组
  全适用；dry-run 默认，--apply 需人工确认）。
- **别名冲突消歧**：约 40 组口语别名跨风格重复（如"国风"/"terminal"/"catppuccin"），
  消歧规则见 [`styles/00_索引/风格路由.md`](styles/00_索引/风格路由.md) 使用规则第 6 条；
  新增风格登记 aliases 时不得与既有别名撞车（lint family_duplicate 之外的人工检查项）。
