# 团队δ 设计文档：对象级内核与 IR 层（支柱 F1–F7 可执行技术方案）

- 日期：2026-08-30
- 范围：`leo-ppt-generator` 技能包的对象级生成内核、notes/theme 合同、upgrade 对象级 spec 与补丁合并、manifest IR v2、复杂度计分与授权省略、SVG→OOXML 远期子路线
- 上游依据：`docs/ppt-github-6专家集成评审会-2026-08-30.md` 支柱 F 与裁决 1；专家6 报告（格式内核）、专家4 报告（质量闭环）
- 总架构师合同对齐：CI-2（确定性）、CI-3（schema 版本化与新旧 builder 可切换）、CI-4（新校验退出码 0/1/2）、CI-6（内核层绝不引入 Node）；治理红线见第 8/9 节
- 本文只读引用的源码路径均为真实打开阅读过的文件；本任务未修改除本文档外的任何文件

---

## 1. 设计目标与范围

### 1.1 目标一句话

把对象级生成内核从"1002 行手写 OOXML"迁移到 **manifest IR → python-pptx 对象 API 的编译器**，一次性补齐形状库/原生表格/原生图表/母版继承/notes 接线，同时保持 manifest 唯一 IR 地位、validate_pptx 兜底回归、双 builder 可切换与产物确定性。

### 1.2 动作映射与分期（对齐会议路线图）

| 动作 | 内容 | 分期 | 本文详设章节 |
|---|---|---|---|
| F1 | 内核迁移 python-pptx 对象 API（全 MSO 形状、原生表格/图表、母版/版式继承、notes 母版接线；shape id/rel/content-type 归库；xmlchemy 逃生舱承接 custom polygon） | P1 | §3.1 |
| F2 | notes 全链路 + theme1.xml 字体双槽最小合同（headFontFace/bodyFontFace → `a:latin` 双槽） | P1 | §3.2 |
| F3 | upgrade 对象级 spec：prepare 即 dump 结构化 JSON（与 manifest 同构）、finalize 后源 vs 产物对象级 diff（位置/文本/notes 三轴）、选择器 `/slide[N]/shape[@name=X]` | P2 | §3.3 |
| F4 | 字节保真 OOXML 补丁原则 + 单页合并降级（母本字节保留、仅补丁页替换；失败原位重插） | P2 | §3.4 |
| F5 | manifest IR v2：坐标无关 + 稳定对象 ID + 证据链接 + 阅读顺序 + 可编辑性元数据（版本化迁移） | P2（后置） | §3.5 |
| F6 | 复杂度计分决策树（6 项条件计分触发器）+ `authorized_omissions` 登记字段 + 自纠固定优先级序与轮次上限 | P1（计分）/P2（omissions 与 diff 联动） | §3.6 |
| F7 | SVG→OOXML 矢量可编辑子路线（远期备选，仅依赖评估与接口占位） | 远期 | §3.7 |

### 1.3 明确不做（沿会议裁决）

1. 不引入 Node 进 PPTX 组装路径（PptxGenJS/unioffice 一票否决；unioffice 另有商业 EULA+混淆源码双重否决）。
2. 不采用多内核并用；LibreOffice PDF→PPTX 不作重建主路径。
3. 不改 manifest 的 IR 理念（box_px 缺失即违规、asset_provenance 枚举、notes 冻结全部保留）；F5 是加厚不是重构。
4. 不在迁移期静默修改 vendored 上游合同（见 §8 vendor 纪律）。

---

## 2. 现状盘点：build_pptx_from_manifest.py 结构解剖

对象：`runtime/src/leo_ppt_generator/_vendor/editable_ppt/editppt/runtime/build_pptx_from_manifest.py`（实测 1002 行，`import pptx` 0 处、`zipfile` 3 处、`subprocess` 1 处用于 SVG 预览）。该文件是 vendored 上游 `image-to-editable-ppt-skill`（MIT，pinned commit `fb86976`，`upstreams.yaml` L41-77）的一部分，capability 登记 E21/E23/E26 的 integration 落点。

### 2.1 模块分段（行级证据）

| 分段 | 行区间 | 职责 |
|---|---|---|
| 常量与单位 | L15-38 | `EMU_PER_INCH=914400`；对齐/锚定枚举表 `TEXT_ALIGNMENTS`/`TEXT_VERTICAL_ALIGNMENTS` |
| 像素→画布几何 | L41-48, L87-180 | `emu()`、`source_size_px`、`slide_size`、`fit_content_box()`（**比例合同**：页图与画布同比例 letterbox 进 `content_box` 而非拉伸全画布）、`px_to_inches()`、`normalize_position_item()`（`polygon_px`→外接盒+英寸多边形；`points_px`→盒 + `flip_h/flip_v` 方向语义；`source_corner_radius_px`→英寸 radius） |
| 文本宽度模型 | L183-289 | `iter_text_lines`、`text_width_units()`（CJK=1.0/ASCII=0.55/空格=0.32 的启发式宽度）、`fitted_font_size()`（safety=0.9 折减；`font_size_source∈{measured,hints}` 时 safety=1.0 信任测量值）、`fit_text_item()` + run 级等比缩放 `scale_run_font_sizes()` |
| manifest 归一化 | L292-300 | `normalize_manifest()`：px 字段解析为英寸（**被 validate_pptx.py L11 直接 import，是跨文件合同**） |
| XML 生成（页内对象） | L314-501 | `shape_fill/shape_line_xml`（stroke 宽 `px*12700`、`prstDash`）、`slide_background_xml`、`text_box_xml()`（手写 `p:sp`：`lIns/tIns/rIns/bIns=0`、`wrap`、`anchor`、`spAutoFit`、run 级 `sz/b/i/baseline` + `a:latin/a:ea/a:cs` 三槽同字体、`endParaRPr`）、`image_xml()`（`alt`→cNvPr name）、`shape_xml()`、`custom_polygon_geometry_xml()`（custGeom 21600×21600 归一化坐标 + `moveTo/lnTo/close`）、`round_rect_adjustment()`（adj 0–50000 clamp）、`preset_geometry_xml()`（roundRect 写 `<a:gd name="adj">`，**其他 preset 空avLst 透传**） |
| XML 生成（包结构） | L504-647 | `slide_xml()`（z_index 分层：shapes 默认 100 / images 200 / text 300，`next_id` 从 2 递增；`p:bg` 背景色）、`rels_xml()`（rId1=layout，图片 `rId{i+1}` 硬编码、notes 追加）、`notes_slide_xml()`（手写 notes body placeholder `ph type="body" idx="1"`）、`notes_rels_xml`/`notes_master_xml`/`notes_master_rels_xml`（**极简骨架**：spTree 空、无 theme 声明细节）、`content_types_xml()`（Default+Override 手工拼）、`presentation_xml()`（sldId id 从 256 起、`sldSz type=wide|custom`）、`presentation_rels_xml()` |
| 包写入 | L650-728 | `write_common_parts()`（手写 `_rels/.rels`、`docProps/core.xml`（title="Image to editable PPT"）、`docProps/app.xml`（Application="Codex"）、slideMaster1/slideLayout1(blank)/theme1.xml（fontScheme 三槽 PingFang SC 硬编码））、`write_pptx()`（单页）、`write_deck()`（多页 + notes：**`notes_xml` 字节存在则原样字节写回**——E26 notes 冻结的实现点，L721-728） |
| deck manifest 读取 | L731-767 | `page_entries_from_deck_manifest()`、`output_path_from_deck_manifest()` |
| PIL 预览 | L770-973 | `render_preview()`（page.pptx 的独立像素近似渲染，含 SVG 经 ImageMagick 转换）、`choose_preview_font()`（macOS 字体路径硬编码）、`draw_dashed_line()` |
| CLI | L975-998 | `manifest` / `--deck-manifest --out --preview` |

调用方（迁移必须保持的接口面）：

- `validate_pptx.py` L11：`from build_pptx_from_manifest import TEXT_ALIGNMENTS, TEXT_VERTICAL_ALIGNMENTS, normalize_manifest`。
- `editable/adapter.py` L17-18、L512-518、L557-564：`_vendor_builder.write_pptx(manifest, output_path, manifest_path)`、`_vendor_builder.write_deck(deck, entries, destination, notes)`。
- vendor `finalize_deck_run.py` L51：以子进程直接调用 `build_pptx_from_manifest.py --deck-manifest ... --out ...`（vendor 命令面内部固定 legacy builder，见 §3.1.6）。
- `hybrid/assembler.py` L227 经 `EditableAdapter.assemble_page_artifacts` 间接使用。
- `tests/boundary/test_editable_patch_regressions.py` 以文件路径方式加载 vendor 模块（测试加载模式需在新布局下复刻）。

### 2.2 支持的对象/属性清单（迁移等价基线）

- **text_boxes**：`box_px`（必需）、`font_size`（+ fit 链：`fit_text/text_fit_safety/min_font_size/max_font_size/line_height/font_size_source`）、`font`（默认 PingFang SC）、`color`、`align∈{l,ctr,r}`、`valign∈{t,ctr,b}`、`wrap`（默认 `none`）、`autofit=shape→spAutoFit`、`rotation`、`text`/`runs[]`/`paragraphs[]`（run：`text/font_size/font/color/bold/italic/baseline`）、`z_index`。
- **images**：`box_px`、`path`（png/jpg/jpeg/gif/svg，`content_type_for` 白名单）、`alt`、`z_index`。
- **shapes**：`type∈{rect,roundRect,ellipse,line}` 四类默认 + **任意 `preset` 字符串透传**（无枚举校验）、`fill`（none/六位 hex）、`stroke`/`stroke_width`/`dash`、`box_px` 或（line）`points_px`（带 flip 语义）、`polygon_px`（custGeom）、`source_corner_radius_px`/`radius`、`flip_h/flip_v`、`z_index`。
- **slide/deck**：`slide.width/height`（英寸，默认 13.333×7.5）、`background`（纯色）、`notes`（`text` + `text_sha256` + `notes_xml` 字节冻结）。
- **完全缺失**：原生表格（graphicFrame）、原生图表、母版/版式继承（只有 1 个空 slideMaster + blank layout）、占位符语义、主题色消费、组合形状、连接符库、SmartArt、媒体。

### 2.3 风险点（迁移动机与等价性保护点）

1. **preset 任意字符串直写 `prstGeom`（L434、L491-493）**：manifest 写 `"preset": "rounded-rectangle"` 之类非法 token 会产出打不开的文件且无任何拦截——迁移后由 `MSO_AUTO_SHAPE_TYPE` 枚举校验兜住，非法值在 build 期清晰失败。
2. **id/relationship/content-type 三线手工对齐**（`next_id` L506-523、`rId{i+1}` L512/540-546、`content_types_xml` L595-620）：每新增一种对象都要重学一遍 OOXML 接线（专家6 反面教训 4 的实体现场）；这正是 python-pptx 存在的理由。
3. **手写 notesMaster/theme 是"最小能打开"骨架**（L580-592、L661：fmtScheme 仅一项 fill/ln/effect）：兼容性靠 PowerPoint 容错；python-pptx `templates/notesMaster.xml` + `default.pptx` 是久经测试的完整骨架。
4. **zipfile.writestr 时间戳非确定**（L674、L706）：同 manifest 两次构建字节不同——CI-2 当前就不满足，legacy 路径也需补确定性包装（§3.1.5）。
5. **media 命名与 validator 的顺序耦合**：validator 按 `ppt/media/image{index}{ext}` 反查（validate_pptx.py L724-746），依赖 builder 的全局 `media_index` 递增（L673、L705）；python-pptx 按 image sha 去重复用 part，重复引用同一文件时 media 数 < manifest 数 → `media_manifest_mismatch` 误报（§3.1.7 处理）。
6. **`fit_content_box` 双实现漂移面**：builder L101-114 与 `prepare_deck_run.py` L44-59 同逻辑两处维护。
7. **产物元数据身份混乱**：core.xml title "Image to editable PPT"、app.xml Application "Codex"（L653-654）；对 γ/E5 的渲染器感知 lint 不友好（无法判定产物来源）。

---

## 3. 详细技术设计

### 3.1 F1：对象级生成内核迁移 python-pptx 对象 API

#### 3.1.1 总体架构：新增自有 builder，vendored builder 降级为 legacy

**决策：不修改 vendored 文件，新写自有编译器，feature flag 分派。** 理由：

- `build_pptx_from_manifest.py` 是 vendored 上游文件，"整体重写"不可能以可审查的 patch 形式登记（约千行替换），违反 `upstreams.yaml` patch 纪律；vendor 纪律的正确姿势是"本地适配通过新增文件完成"（同 `creator-buddy` 先例与既有 `.claude-plugin/plugin.json` 先例）。
- CI-3 要求迁移期新旧可切换 + 旧路径回归保留：新文件共存是最自然的双跑形态。

分层（自上而下，全部落在 leo 自有包内，runtime 内部实现迁移合法——"主 Agent 不 import _vendor"红线不受影响）：

```
manifest.json (IR, 不变)
    │
    ├─ normalize/fit 几何层（共享，保持字节等价）
    │    editable/geometry.py        ← 从 vendor builder 抽取的纯函数复刻：
    │                                    normalize_manifest / px_to_inches /
    │                                    fit_content_box / fitted_font_size /
    │                                    TEXT_ALIGNMENTS / TEXT_VERTICAL_ALIGNMENTS
    │                                    （vendor 原实现原样保留，自有层为受测复刻）
    ├─ legacy builder（vendored，冻结不动）
    │    _vendor/.../build_pptx_from_manifest.py::write_pptx / write_deck
    └─ object builder（新，本设计核心）
         editable/object_builder.py::write_pptx / write_deck / compile_page
              │  manifest → python-pptx 对象 API 编译
              ├─ shapes: autoshape/connector/freeform（MSO 枚举）
              ├─ text: textframe runs；ea/cs 槽经 oxml 逃生舱
              ├─ images: add_picture（rel/content-type/media 归库）
              ├─ notes: notes_slide 懒创建（notesMaster 接线归库）
              ├─ tables/charts: graphicFrame（F1 增量对象面）
              └─ deterministic_zip.py::save_canonical(prs, path)  ← CI-2
```

#### 3.1.2 目标接口（与 legacy 完全同签名，调用方零改动分派）

```python
# editable/object_builder.py
TEXT_ALIGNMENTS = {...}            # 与 vendor 逐字相同
TEXT_VERTICAL_ALIGNMENTS = {...}

def normalize_manifest(manifest: dict) -> dict: ...   # 语义与 vendor 等价（共享几何层）
def write_pptx(manifest: dict, out_path, manifest_path) -> Path: ...
def write_deck(deck: dict, page_entries: list, out_path, notes_entries: list) -> Path: ...
def compile_page(slide: "pptx.slide.Slide", manifest: dict, manifest_path: Path,
                 *, page_index: int = 1, notes: dict | None = None) -> None:
    """页编译核心：page.pptx 与 final deck 共用，保证两级产物同构。"""
```

分派点（唯一改动面，两处）：

```python
# editable/adapter.py
def _builder():  # 新增模块级函数
    from ..config import builder_selection      # 读 LEO_EDITABLE_BUILDER + run 冻结字段
    if builder_selection.current() == "pptx":
        from . import object_builder
        return object_builder
    return _vendor_builder

# build_page_from_manifest / assemble_page_artifacts 内
# _vendor_builder.write_pptx(...) → _builder().write_pptx(...)
```

#### 3.1.3 manifest → python-pptx 映射表（等价性合同的"翻译规格"）

| manifest 对象/属性 | python-pptx API | 等价性注意点 |
|---|---|---|
| `slide.width/height` | `prs.slide_width = Inches(w)` | EMU `int(round(w*914400))` 与 `emu()` 一致 |
| `slide.background` | `slide.background.fill.solid(); .fore_color.rgb = RGBColor.from_string(hex)` | validator 不检查 bg；等价测试按 `p:bg/p:bgPr` 投影对比 |
| `text_boxes[]` | `shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))` | `bodyPr` 四 inset 显式置 0（库默认 91440/45720 等）；`wrap="none"` → `tf.word_wrap = False` 后还需 oxml 置 `bodyPr@wrap="none"`（库 False 只删属性，OOXML 默认 square≠none，**必须逃生舱补写**）；`anchor` → `tf.vertical_anchor = MSO_VERTICAL_ANCHOR.{TOP,MIDDLE,BOTTOM}`；`autofit="shape"` → `tf.auto_size = MSO_AUTO_SIZE.SHAPE_TO_FIT_TEXT`，否则 `None`（等价于 noAutofit 缺省，与 legacy `<a:noAutofit/>` 字节不同但语义同；等价测试按"autofit 语义"投影） |
| run `text` | `p.text`/`r.text` | 逐字；`endParaRPr` 由库生成，等价测试不比 |
| run `font_size` | `run.font.size = Pt(v)` | centipoint 取整一致 |
| run `font` | `run.font.name = f`（写 `a:latin`）+ 逃生舱同写 `a:ea`/`a:cs`（legacy 三槽同字体） | 唯一必须 oxml 的文本属性 |
| run `color` | `run.font.color.rgb = RGBColor.from_string(...)` | |
| run `bold/italic` | `run.font.bold/italic` | |
| run `baseline` | 逃生舱 `rPr.set("baseline", str(int(v)))` | |
| `align` | `paragraph.alignment = PP_ALIGN.{LEFT,CENTER,RIGHT}` | |
| `rotation` | `shape.rotation = float(v)` | 度↔60000 分度换算归库 |
| `images[]` | `shapes.add_picture(path, Inches(l), Inches(t), Inches(w), Inches(h))`；`pic._element._nvXxPr.cNvPr.set("name", alt)` | rel/content-type/media part 归库；part 命名按加入顺序 `image1..N`（与 validator 反查约定兼容，重复引用例外见 §3.1.7） |
| `shapes[] type=rect` | `add_shape(MSO_SHAPE.RECTANGLE, ...)` | |
| `type=roundRect` | `add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, ...)` + `shape.adjustments[0] = adj/100000`（`round_rect_adjustment()` 的 0–50000 clamp 复用于归一化前） | Adjustment 归一化基 100000 与 vendor L478-488 同 |
| `type=ellipse` | `add_shape(MSO_SHAPE.OVAL, ...)` | |
| `type=line`（`points_px`） | `add_connector(MSO_CONNECTOR.STRAIGHT, left, top, w, h)` + 逃生舱 `spPr/xfrm@flipH|flipV`（`normalize_position_item` 已算 flip 语义，L173-176） | connector 无 flip 高层属性，必须 oxml |
| `preset`（任意） | 查 `MSO_AUTO_SHAPE_TYPE` 枚举（`MSO_SHAPE` 全 preset 集）；命中 → `add_shape(enum)`；未命中 → **build 期 ValueError**（清晰失败，替代现状静默写非法 XML） | `dash` → `line.dash_style = MSO_LINE.{SQUARE_DOT,DASH,...}`（按 `prstDash` token 映射，未知 token 清晰失败） |
| `polygon_px` | 优先 `shapes.build_freeform(start_x, start_y, scale).add_line_segments(vertices, close=True).convert_to_shape()`；FreeformBuilder 不覆盖的用例（多轮廓 subtract 语义）经 xmlchemy 直接构造 `a:custGeom` | legacy 的 21600 归一化坐标与 FreeformBuilder 的本地坐标是**同一渲染语义的两种编码**（顶点在外接盒内相对位置不变）；等价测试按顶点相对位置投影对比，不比字节（python-pptx `freeform.py` L26-117 证实） |
| `fill="none"` | `shape.fill.background()`（noFill）；`fill="#hex"` → `solid()+rgb` | |
| `stroke="none"` | `shape.line.fill.background()`；否则 `line.color.rgb` + `line.width = Emu(int(px*12700))` | `Emu()` 直写避免 Pt 换算误差 |
| `z_index` 分层 | 编译顺序 = `sorted([(z, kind_order, seq)])`（复刻 `slide_xml` L504-523 的稳定排序键） | spTree 文档顺序即 z 序，排序键必须逐字复刻 |
| notes（text） | `slide.notes_slide.notes_text_frame.text = ...`（`parts/slide.py` L108-155：notesMaster 懒创建、clone_master_placeholders、双 rel 接线全归库） | E26：validator 只校验段落文本 sha256（validate_pptx.py L493-500），高层 API 即满足 |
| notes（`notes_xml` 冻结字节） | save 后经 `zip_surgery.replace_part(z, f"ppt/notesSlides/notesSlide{N}.xml", bytes)` 原样字节回写（见 §3.4.2 的共用原语） | 字节冻结语义与 legacy `write_deck` L721-728 一致；validator 文本 hash 不变即通过 |
| **新增对象面（F1 增量，manifest 可选段）** | `tables[]` → `shapes.add_table(rows, cols, ...)`（`pptx.table`，含列宽/行高/单元格文本/合并）；`charts[]` → `shapes.add_chart(XL_CHART_TYPE.*, x, y, cx, cy, ChartData)`（`pptx.chart`，数值/系列/轴标签逐字） | P1 只做"表格先行"（文本密集页高频）；图表接线与 D 支柱（mermaid/echarts 确定性渲染）路线分野：**图表数据若可逐字确认才允许原生 chart，否则走 D 支柱位图/公式资产**——与 editable-workflow.md 质量门"图表必须保留真实数值，无法确认时标记失败"一致 |

#### 3.1.4 custom polygon 逃生舱（oxml/xmlchemy）

三层递进，逐层降级到更低层 API：

1. **高层**：`build_freeform`（折线闭合路径，覆盖现状 `polygon_px` 100% 用例）。
2. **中层**：`shape._element` 直接操作（lxml element）——ea/cs 字体槽、connector flip、baseline、`bodyPr@wrap` 均走此层；全部封装为 `object_builder._oxml.py` 内的具名函数（如 `set_ea_cs(run, typeface)`），禁止散落裸 XML 字符串拼接。
3. **底层**：`pptx.oxml.parse_xml`/自定义 `xmlchemy` 元素类（`OxmlElement` 注册即用）——仅当需要引入库 schema 未定义的元素（如 F7 的 `asvg:svgBlip` 扩展）。

逃生舱纪律：每个 oxml 触点必须带注释说明"为什么高层 API 不够"，并在等价性测试有对应投影断言。

#### 3.1.5 确定性策略（CI-2）

现状两条路径（vendor zipfile / python-pptx save）都写入当前时间戳的 zip 目录项，**均非字节确定**。方案：统一 canonical 重打包。

```python
# editable/deterministic_zip.py
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)          # zip 最小合法时间
ENTRY_ORDER = ["[Content_Types].xml", "_rels/.rels"]  # 其余按 partname 字典序

def save_canonical(prs: Presentation, out_path: Path) -> None:
    buf = io.BytesIO(); prs.save(buf)                  # python-pptx 序列化
    repack_zipstream(buf, out_path)                    # 固定条目序/date_time/
                                                        # compress_type=ZIP_DEFLATED/
                                                        # external_attr=0o600<<16
def repack_zipstream(src: io.BytesIO, out_path: Path) -> None: ...   # 同样适用于 legacy 产物
```

- 产物身份：builder 在 `docProps/app.xml` 写 `Application=leo-ppt-generator/<builder-id>`（对象级路径）——服务 γ 指纹与 E5 渲染器感知 lint 的来源判定；legacy 产物保持 "Codex" 不动（vendor 字节纪律）。
- core.xml：不触碰 `core_properties`（显式设置才会写动态字段；default.pptx 模板的静态 revision/日期是冻结字节）。
- 浮点：全部经 `int(round(...))` 进 EMU/centipoint，无浮点进 XML。
- 依赖锁定：`python-pptx>=1.0.2` 已在 `runtime/pyproject.toml`（L17），升级 python-pptx 视为重大变更——lxml 序列化细节（属性顺序/自闭合习惯）可能变化，必须重跑 golden 确定性回归（§5）。
- 验收口径：同 manifest 同 builder 连续两次构建 sha256 相等；`TZ`/系统时间变化不影响（回归测试显式注入两个不同 TZ）。

#### 3.1.6 feature flag 与迁移策略（CI-3）

- **选择器**：`LEO_EDITABLE_BUILDER=pptx|legacy`（环境变量，默认值由发布阶段决定，见 §9 双跑对照期）；`editable/adapter.py` 与 `upstream_bridge` 在 run 创建时把生效值冻结进 `deck_manifest.json` 的 `"builder": {"id": "...", "selection": "pptx"}`——finalize/重建按冻结字段分派，保证**同一 run 永远同一 builder**（旧 run 可恢复性：无字段的旧 run 视为 legacy）。
- **vendor 命令面**：`leo-ppt upstream editable-ppt -- run finalize` 内部子进程固定调 vendored builder（`finalize_deck_run.py` L51），迁移期保持 legacy-only 并在 SKILL.md/execution-contract 注明"vendor run finalize 子命令为 legacy 路径"；顶层 `leo-ppt editable finalize`（stable workflow，走 adapter）为可切换路径。这保证 vendor CLI 合同零改动。
- **manifest 不变**：F1 是实现切换不是 IR 变更，`schema_version: 1` 不动（CI-3 的 schema 版本化在 F5 才启用）。
- **判定翻转门槛**：§5 全部等价性测试 + 全量 evals 双跑通过两个发布周期后，默认翻转为 `pptx`；legacy 保留至 P2 结束再评估退役。

#### 3.1.7 已知语义差异与处理决策（诚实清单）

| 差异 | 处理 |
|---|---|
| python-pptx 按 sha 去重 media part：同文件两次引用 → 1 part 2 rel，validator `media_manifest_mismatch`（L723）误报 | 等价测试覆盖该用例；若真实 fixture 触发，打 `patches/0007-editable-media-hash-multiset.patch`（validator 改为 hash 多重集匹配：manifest image 文件 hash 集合 == media part hash 集合），按 §8 登记 |
| default.pptx 带 11 个版式+完整 master/theme（legacy 仅 1 blank layout） | 采用 `prs.slide_layouts[6]`（Blank）挂页；多余 layout 是模板字节，validator 不受影响；theme 覆写见 F2 |
| `bodyPr@wrap` 库默认 square vs legacy 显式 "none" | 逃生舱显式写 `wrap="none"`（默认路径）保持语义等价 |
| spAutoFit 字节形态 | 语义投影对比（autofit 有/无），不比字节 |
| `sldId` id 起点（legacy 256 起；库自动分配 256 起） | 等价（库实现同为 256 递增） |

#### 3.1.8 CI 对齐

- CI-2：§3.1.5。
- CI-3：§3.1.6。
- CI-6：python-pptx 纯 Python，无 Node。
- 比例合同：`fit_content_box`/`px_to_inches` 语义逐字复刻进共享几何层，等价测试含 letterbox（源非 16:9）用例。
- notes hash 冻结（E26）：字节回写原语 + validator 回归（§5）。
- 已确认公式清单（E31）：validator 逻辑不动，manifest `formula_inventory/expected_formula_inventory` 照旧经 images 资产路径进 builder（公式仍是 latex-rendered-formula image 资产，F1 不改公式策略）。

### 3.2 F2：notes 全链路 + 主题最小合同

#### 3.2.1 theme1.xml 字体双槽

- **合同来源**：deck 级新增可选段（α/β 提供）：

```json
"theme": {
  "head_font_face": "Source Han Sans SC",
  "body_font_face": "PingFang SC"
}
```

- **落点**：`object_builder` 在 Presentation 起步后经 oxml 覆写 slideMaster 的 theme part（python-pptx 主题编辑无高层 API，走 `prs.slide_masters[0].element` 关联的 theme part element）：

```
a:theme/a:themeElements/a:fontScheme
  a:majorFont/a:latin|a:ea|a:cs @typeface = head_font_face
  a:minorFont/a:latin|a:ea|a:cs @typeface = body_font_face
```

配方参照 PptxGenJS `gen-xml.ts makeXmlTheme()`（headFontFace/bodyFontFace 双槽语义，MIT）与 python-pptx `templates/theme.xml`（完整 fontScheme 骨架），XML 按 OOXML 规范自写。
- **run 级联动**：`text_boxes[].font` 变为可选——缺省时继承主题槽位；新增可选 `text_boxes[].role ∈ {title, body}`（缺省 body），`title→majorFont`、`body→minorFont`。显式 `font` 仍逐 run 写 `a:latin/ea/cs`（向后兼容：无 theme 段、无 role 的旧 manifest 行为不变）。
- **字体替代记录主题层化**：editable-workflow.md 质量门"字体缺失时记录明确替代字体"从逐 run 改写升级为：theme 段即替代记录的落点（`theme.substitutions[]` 可选登记：`{requested, substituted, reason}`），升级换字体不再逐页改 run；页面级替代仍走既有 visual 字段。γ 的桌面验收门不变（未执行不得声称通过）。
- legacy builder 不实现 theme 段（vendor 冻结）；theme 段存在且 builder=legacy 时 record 阶段发 warning（不 fail），提示切 builder。

#### 3.2.2 notes 全链路

- notes 写入：见 §3.1.3（懒创建 + notesMaster 接线归库，替换手写 `notes_master_xml` 骨架）。
- notes 冻结字节：`notes_xml` 字节经 `zip_surgery.replace_part` 回写（legacy 行为等价）。
- notes 提取（E03/E26 上游）：`_input_normalization.collect_notes_from_pptx` 不动。

### 3.3 F3：upgrade 路线对象级 spec（dump / 选择器 / diff）

#### 3.3.1 对象级 dump（prepare 阶段）

新命令 `leo-ppt editable inspect <pptx|run> [--selector S] --out objects.json`（自有命令面，不动 vendor CLI）。实现 `editable/object_dump.py`：

- 遍历 `Presentation` 每页 spTree，产出**与 manifest 同构**的 JSON：

```json
{
  "schema_version": 1,
  "source_type": "pptx-dump",
  "slide": {"width_in": 13.333, "height_in": 7.5},
  "slides": [{
    "slide_index": 1,
    "text_boxes": [{"oid": "s1-t03", "name": "TextBox 5", "left": ..., "top": ...,
                     "width_in": ..., "height_in": ..., "runs": [...], "font_size_pt": ...}],
    "shapes":   [{"oid": "s1-x07", "kind": "roundRect", "adj": 12500, ...}],
    "images":   [{"oid": "s1-i02", "media_sha256": "...", ...}],
    "tables":   [{"rows": [...], "cells": ...}],
    "charts":   [{"chart_type": "...", "series": [...]}],
    "notes":    {"text": "...", "text_sha256": "..."},
    "reading_order": ["s1-t03", "s1-t01", ...],
    "unsupported": [{"element": "graphicFrame/smartArt", "reason": "..."}]
  }]
}
```

- 坐标口径：英寸（内部 EMU）；提供 `--source-px {width,height}` 时同步产出 `box_px` 反算列（供与重建 manifest 对照）。
- `unsupported[]`：OfficeCLI `PptxBatchEmitter.cs` 的 UnsupportedWarning 思想（slide 照常 dump，无法词汇化的元素记警告不抛错，L70/L136-150 证实）；dump 永不因不认识对象而失败。
- 接线：upgrade 路线 prepare（可信 Office 输入，经 Gate 0 信任门禁之后）自动 dump 至 `<run>/input-objects.json`，作为对象级 ground truth；与既有 text_hints.json（文本级）互补。

#### 3.3.2 选择器语义

`editable/object_selector.py`，OfficeCLI `PowerPointHandler.Selector.cs` 思想移植（Apache-2.0，不引 C#）：

- 语法：`/slide[N]/<tag>[@attr=value][@text~=fragment]`；`>` 与 `/` 均为分隔符；`tag ∈ {shape, textbox, picture, table, chart, group, notes, placeholder}`；属性谓词支持 `@name=`、`@type=`、`@text~=`（包含匹配）；顶层逗号多选（SplitTopLevelCommas 思想）；不支持的组合子（后代空格）**显式报错**而非静默空匹配（Selector.cs FindUnsupportedCombinator 的诚实失败思想，L24-48）。
- 用途：diff 报告的对象指代、F5 稳定 ID 的人类可读别名、upgrade-selected 的对象级指令定位。

#### 3.3.3 对象级 diff（finalize 后验收）

新命令 `leo-ppt editable diff --source input-objects.json --produced final.pptx --axes position,text,notes [--omissions omissions.json] --report diff.json`，实现 `editable/object_diff.py`：

- **三轴**：
  - 位置：对象配对（oid/稳定 ID 或文本指纹）后比 `left/top/width/height`（英寸），容差 `±0.02in` + 中心点偏移 + IoU≥0.95 三判据任一失败即 FAIL；
  - 文本：配对对象 run 文本归一化（去首尾空白）逐字比对；`required_text` 全集必须出现；
  - notes：逐页文本 sha256 全等（E26 同算法 `sha256_text`）。
- **豁免**：`--omissions` 读 F6 `authorized_omissions`，登记对象的三轴差异降级为 WARN 并附登记引用。
- **退出码（CI-4）**：`0` = 三轴全过且无豁免降级；`1` = 存在未豁免差异（FAIL，阻断 record/finalize）；`2` = 仅存在已登记豁免的差异（可交付，报告落盘 + PARTIAL-GATE 联动）。
- **与迁移等价测试复用**：diff 的"结构投影"（对象列表规范化）即 §5 等价性断言的底层——同一份投影函数 `object_projection.py` 两用（新旧 builder 对比 / 源产物对比），先在等价测试中校准。

### 3.4 F4：字节保真 OOXML 补丁原则 + 单页合并降级

#### 3.4.1 原则（genoffice generate.ts 思想，Apache-2.0）

头注明确（L1-18 证实）："no wholesale parse→serialize（丢未建模属性：effects/custom geometry/extensions），代之以原始字节片的手术式就地补丁；未触碰字节保持原样"。落地为两条铁律：

1. **母本字节保留**：upgrade-selected 只替换被补丁页的 part 字节，母本（`upgrade/baseline.py` 冻结的 `image-baseline/image-delivery.pptx` 或可信原 PPTX）其余 part 字节逐字节保留；
2. **只在副本上动刀**：输出经既有 `atomic_materialize`（storage.py）落盘，母本只读——治理红线"失败不得破坏原图片交付物"由构造保证。

#### 3.4.2 实现：`upgrade/zip_surgery.py` + `upgrade/patch_merger.py`

```python
# zip_surgery.py —— 字节级 OOXML 手术原语（唯一写入口，白名单操作）
ALLOWED_PART_OPS = {"replace", "add", "drop"}
def replace_part(zin, zout, partname: str, blob: bytes) -> None: ...
def add_part(zin, zout, partname, blob, content_type_override=None) -> None: ...  # 自动补 [Content_Types].xml Override
def add_relationship(zin, zout, rels_partname, rel_type, target) -> str: ...      # 返回新 rId，id 取 max+1
def preserve_bytes(zin, zout, partname) -> None: ...                              # 显式拷贝（默认行为，供审计）
```

- 全部操作先在内存缓冲组装，完成后对产物跑两道冒烟：`Presentation(out).slides` 页数可读 + `validate_pptx` 结构校验；任何异常 → 丢弃缓冲、回退全重建路径并记录 `merge_fallback_reason`。
- 条目顺序/时间戳沿用 canonical 规则（确定性不被补丁破坏）。

```python
# patch_merger.py —— upgrade-selected 的 merge_mode=patch
def merge_selected_pages(baseline_pptx: Path, page_manifests: dict[int, dict],
                         notes_entries: list, out: Path) -> dict:
    """对选中页：object_builder.compile_page 到独立单页 Presentation，
    取其 ppt/slides/slideN.xml + .rels + 新增 media parts，
    经 zip_surgery 替换进母本副本；未选中页与全部母版/版式/主题/docProps 字节不动。
    失败页：保留母本原页字节原位重插（partial 状态），不废整 deck。"""
```

- 页级失败降级（`landGeneratedPages` 思想）：某补丁页构建失败 → 该页保留母本原 part 字节，结果 manifest 记 `pages[N].mode = "baseline-preserved"`，走既有 PARTIAL-GATE 显式确认；绝不让单页失败废掉整 deck。
- 旧 media 孤儿处理：被替换页引用的旧 media part **保留不删**（字节保真优先；未引用 media 为合法包状态，PowerPoint 容忍）；体积治理（D5/γ）另行评估 GC 可选项。
- 与既有 `hybrid/assembler.py` 关系：assembler 增加 `merge_mode ∈ {"rebuild"（默认，现状）, "patch"}`；patch 仅在"母本存在 + 页数一致 + 母本可解析"时可用，否则自动 rebuild。

### 3.5 F5：manifest IR v2（P2 后置）

参照 presentation-skill `deck_ir.schema.json`（MIT："intentionally excludes slide coordinates"，required 含 stable ids/evidence/reading order）。

- **版本化（CI-3）**：`schema_version: 1 → 2`；`references/manifest-schema.md` 增 v2 章节 + 迁移注记；读取侧（validate/builder/finalize）按 `schema_version` 分派归一化：v1 自动补默认值升级（`oid` 默认 = `{section}[{i}]` 派生、无 evidence/reading_order 字段时跳过相关校验），**旧 run 可恢复**（v1 manifest 永远可构建）。
- **v2 新增字段**（全部可选，v1 超集）：

| 字段 | 层级 | 语义 |
|---|---|---|
| `oid` | text_boxes/shapes/images/tables[] 每项 | 稳定对象 ID：page 内唯一；来源优先级 = 源 dump 的 name→内容指纹→数组序派生；upgrade-selected 用它做对象指代（配合 §3.3.2 选择器别名） |
| `evidence` | 每对象/每数字 | 证据链接：`{tier: 引用|估算|示意, ref: 数字登记表条目/figure_id/用户输入文件}`——与α支柱 A/S2 联动 |
| `reading_order` | 页级 | oid 有序列表；服务无障碍/审阅/文本 diff 的语义顺序 |
| `editability` | 每对象 | `native-text | asset-image | formula | chart | table | preserved-bitmap`——质量门与 omissions 分派依据 |
| `theme` | deck 级 | §3.2.1 字体双槽段 |
| `authorized_omissions` | 页级 | §3.6 |

- **坐标归后端执行层**：v1 的 `box_px`（source.png 像素系）本就是"执行层拥有坐标"的雏形（px→英寸映射全在 builder）；v2 不改坐标字段，只把"坐标不可进内容合同"的纪律写显式（prompt/大纲层禁坐标——与α的内容合同对齐）。

### 3.6 F6：复杂度计分决策树 + authorized_omissions

#### 3.6.1 6 项条件计分触发器（替换 page-decision-tree.md §1.2/§1.4 的模糊判断）

新脚本 `scripts/score_page_complexity.py <page_dir>`，读 `source.png` + `text_hints.json` + `visual_inventory`，输出：

```
score = Σ w_i · s_i   (s_i ∈ 0..3)
  C1 对象密度        text_hints 行数 + visual_inventory 项数（>40 项 → 3）
  C2 图层交叠        hint 框两两 IoU>0.3 的对数（>15 → 3）
  C3 纹理/渐变面积   高频区（Laplacian 方差分位）+ 渐变色带占比（PIL 可算）
  C4 手绘元素计数    visual_inventory 中 hand-drawn/sticker 类词频
  C5 图表数据可恢复性 chart-like 区域中可 OCR 数值/标签的覆盖率（text_hints 交叉）
  C6 文字-背景粘连   前景文本框落在 C3 高纹理区内的比例
阈值：score ≥ T_bitmap（默认 11/18）→ "复杂视觉保留位图区"决策触发，
      记录 6 项分值进 manifest `background_strategy.complexity_score`（可审计、可 lint）。
```

- 阈值与权重经 evals fixtures 校准后冻结进脚本常量（渲染端阈值外置纪律——"默认设计偏好不硬编码进提示词"反面教训）。
- 输出仅是**决策输入**：触发保留位图仍须逐条满足 §1.2 复用条件；不满足即按现状三步决策树继续。

#### 3.6.2 authorized_omissions（与三级标注联动）

manifest 页级新字段（v1 即可启用，不依赖 v2）：

```json
"authorized_omissions": [
  {"oid": "s2-t11", "kind": "omitted", "reason": "装饰性水印文字，非内容",
   "evidence_tier": "示意", "source_ref": "visual_inventory[7]"},
  {"kind": "merged", "oids": ["s2-t03","s2-t04"], "reason": "双行合并为单行标语"},
  {"kind": "reordered", "oids": [...], "reason": "阅读顺序按 RTL 语言重排"}
]
```

- validator/diff 语义：登记过的 omitted/merged/reordered 对象在三轴 diff 中降级 WARN（退出码 2，可交付）；**未登记的遗漏 = FAIL**（对象级 diff 豁免表的唯一入口）。
- 三级标注联动：`evidence_tier=引用` 的对象**不允许** omitted（引用级内容被省略必须 FAIL——与"已确认公式清单不可静默遗漏"（E31）同族的守卫）；估算/示意级必须附 `reason+source_ref`。
- 自纠固定优先级序 + 轮次上限（写入 page-decision-tree.md"Final self-check"节）：失败自纠顺序固定为 **位置 → 文本 → notes → 视觉资产**；每页自纠 ≤2 轮，超限 reset 重派而非继续修补（与 γ 的 E4 三层容错咬合：此处是页面内纠错序，E4 是派发层重试）。

### 3.7 F7：SVG→OOXML 矢量可编辑子路线（远期备选，只评估不排期）

- **源码事实**（ppt-agent-skill，MIT）：`scripts/svg2pptx.py`（994 行）为**纯 Python**（lxml + python-pptx，`from pptx import Presentation`），将 SVG 元素（rect/text+tspan/circle/ellipse/line/path→custGeom/image data-URI/渐变/transform）解析为**原生 OOXML 形状**——不是简单图片嵌入；`scripts/html2svg.py`（628 行）依赖 Puppeteer + dom-to-svg（Node），以子进程运行 Python 内嵌的 JS 脚本。
- **CI-6 评估结论**：`svg2pptx` 纯 Python，若引入无 Node 问题；`html2svg` 的 Node 仅出现在"HTML→SVG 渲染叶子"，与裁决 1"Node 只许出现在渲染叶子节点且以子进程隔离，永不进 PPTX 组装路径"相容——但须作为**可选依赖**（不可用时整条子路线禁用并明示，不得静默降级）。SVG→PPTX 组装段（svg2pptx）永远纯 Python。
- **接入面（远期）**：direct-editable 路线新增 `vector_lane`：确定性渲染产物（D 支柱 SVG）→ svg2pptx → 原生形状页；`make-slide references/pptx-spec.md`（MIT）的生成端约束（裸 div 文本静默丢弃/禁 `<br>`/禁手工 bullet/web-safe 字体/渐变先栅格化）并入 direct-editable 参考清单，约束前置到生成端。
- **P2 末评估项**：仅交付评估报告（转换保真矩阵 + 字体陷阱清单），不排实现任务。

---

## 4. 开发任务分解表

规模：S ≤1 天，M 2–5 天，L 1–2 周。分期对齐会议 P1/P2。

| ID | 任务 | 依赖 | 涉及文件（新建 ● / 修改 ▲） | 规模 | 验收标准 |
|---|---|---|---|---|---|
| F1-T1 | 共享几何层抽取复刻（normalize/fit/常量） | — | ● `runtime/src/leo_ppt_generator/editable/geometry.py` | M | 对 golden manifests，`geometry.normalize_manifest` 输出与 vendor 逐字段相等（unittest 字典断言）；vendor 文件 0 diff |
| F1-T2 | 确定性 zip 重打包器 | — | ● `editable/deterministic_zip.py` | S | 同输入两次 repack sha256 相等；跨 TZ 不变；legacy 产物经 repack 后 validate_pptx 通过 |
| F1-T3 | object_builder 核心（text/image/shape/line/polygon/preset 枚举/背景/notes/z 序） | F1-T1 | ● `editable/object_builder.py`、● `editable/_oxml.py` | L | 对 §5 全部等价 fixture：结构投影 100% 相等；preset 非法值 build 期 ValueError |
| F1-T4 | builder 选择器 + run 冻结 | F1-T3 | ▲ `editable/adapter.py`、▲ `config/`（builder_selection）、▲ SKILL.md/execution-contract 注记 | M | `LEO_EDITABLE_BUILDER=legacy` 走 vendor 路径产物 hash 与改造前一致；run 冻结字段生效：环境变量改值不影响已创建 run 的 finalize 重建 |
| F1-T5 | 原生表格对象面（manifest `tables[]`） | F1-T3 | ▲ `editable/object_builder.py`、▲ `references/manifest-schema.md`（可选段） | M | tables fixture：单元格文本/合并/列宽经 dump 投影相等；validator required_text 覆盖表格文本 |
| F1-T6 | 原生图表对象面（manifest `charts[]`，仅"数据可逐字确认"场景） | F1-T5、与 D 支柱路由对齐 | ▲ `editable/object_builder.py`、▲ `references/manifest-schema.md` | L | chart 数值/系列/轴标签逐字保真断言；无数据授权 chart-like 禁令维持（validator 既有 + evals 既有 case 不回归） |
| F1-T7 | 等价性测试套件落地 | F1-T3, T2 | ● `tests/boundary/test_object_builder_equivalence.py`、● `tests/fixtures/object-equivalence/`（manifests） | L | CI 全绿；含 letterbox/重复 media 引用/dash/flip/baseline/measured-font 用例 |
| F1-T8 | 回归与 capability 登记 | F1-T7 | ▲ `tests/upstream/core-tests.yaml`、▲ `upstream-capabilities.yaml`（E21/E23 integration 更新 + 新增 F 系条目）、▲ `upstreams.yaml`（integration_adaptations 注记）、▲ `CHANGELOG.md` | S | core-tests.yaml 新 suite 可执行；capability 条目 proof 指向新测试 |
| F2-T1 | theme 字体双槽 + role 继承 | F1-T3 | ▲ `editable/object_builder.py`、▲ `references/manifest-schema.md`（theme 段）、▲ `references/editable-workflow.md`（替代记录主题层化） | M | theme 段产物 theme1.xml 双槽 typeface 断言；无 theme 段旧行为回归通过；builder=legacy 时 warning 不 fail |
| F2-T2 | notes 字节冻结经 zip_surgery 回写 | F4-T1（原语） | ▲ `editable/object_builder.py` | S | notes_xml 字节回写后：字节全等 + validator notes hash 通过（E26 回归） |
| F3-T1 | 对象投影函数（dump/diff/等价测试共用） | F1-T3 | ● `editable/object_projection.py` | M | 对 legacy/pptx 双产物输出规范化投影；被 F1-T7 采用为断言底层 |
| F3-T2 | 对象级 dump CLI（inspect） | F3-T1 | ● `editable/object_dump.py`、▲ `cli.py`（`editable inspect` 子命令） | M | 对离线 fixture PPTX dump：对象计数/坐标/notes hash 稳定；unsupported 元素记警告不失败 |
| F3-T3 | 选择器实现 | F3-T2 | ● `editable/object_selector.py` | M | OfficeCLI 语义子集用例集：`/slide[2]/shape[@name=Foo]`、`>`/`/` 等价、逗号多选、非法组合子显式报错 |
| F3-T4 | 对象级 diff + upgrade 接线 | F3-T1/T3、F6-T2 | ● `editable/object_diff.py`、▲ `cli.py`、▲ upgrade prepare 流程（dump input-objects.json） | L | 三轴 fixture 全覆盖；退出码 0/1/2 与 CI-4 一致；omissions 豁免生效 |
| F4-T1 | zip_surgery 字节手术原语 | F1-T2 | ● `upgrade/zip_surgery.py` | M | 单测：replace/add/add_relationship 后包可开、[Content_Types] 一致性、未触碰 part 字节全等 |
| F4-T2 | patch_merger（upgrade-selected merge_mode=patch） | F4-T1、F1-T3 | ● `upgrade/patch_merger.py`、▲ `hybrid/assembler.py`（merge_mode 参数） | L | 未选中页 part hash 与母本全等；补丁页内容正确；母本文件只读（写前/写后 hash 断言）；结构不支持时自动 rebuild |
| F4-T3 | 页失败原位重插 + PARTIAL-GATE 联动 | F4-T2 | ▲ `upgrade/patch_merger.py`、▲ references（PARTIAL 条款） | M | 注入一页失败 → 该页保留母本字节、其余补丁页保留、交付 manifest 记 baseline-preserved、无确认不放行 |
| F5-T1 | manifest schema v2 + 迁移注记 | F3-T4（oid 语义定型） | ▲ `references/manifest-schema.md`、▲ `editable/geometry.py`（v1→v2 归一化） | M | v1 manifest 自动升级可构建；v2 新字段 validator 语义（evidence_tier 引用级禁 omitted）生效；旧 run（v1）finalize 恢复测试通过 |
| F5-T2 | 稳定 oid 生成与 upgrade-selected 指代 | F5-T1 | ▲ `editable/object_dump.py`（dump 产 oid）、▲ upgrade 流程 | M | 同源两次 dump oid 稳定；selected 指令经 oid 命中率 ≥ name 匹配 |
| F6-T1 | 复杂度计分脚本 + 决策树改写 | — | ● `scripts/score_page_complexity.py`、▲ `references/page-decision-tree.md`（§1.2/1.4 改 6 项触发器 + 自纠序/轮次上限） | M | fixtures 计分稳定（同输入同分）；阈值外置常量；文档含 6 项定义与分值表 |
| F6-T2 | authorized_omissions 字段 + 校验联动 | F3-T4 | ▲ `references/manifest-schema.md`、▲ `editable/object_diff.py`、▲ vendor validator 补丁 `patches/0008-editable-authorized-omissions.patch` | M | 未登记遗漏 FAIL（exit 1）；登记后 WARN（exit 2）；引用级 omitted 恒 FAIL；E31 公式守卫不回归 |
| F7-T1 | 远期评估报告（不实现） | — | ● `docs/`（评估笔记，P2 末） | M | 转换保真矩阵 + 字体陷阱清单 + CI-6 隔离方案评审通过 |

关键路径：F1-T1→T3→T7→T4（P1 内核翻转门槛）；F4-T1 同时服务 F2-T2 与 F4-T2，宜提前。

---

## 5. 测试计划（含迁移等价性测试）

### 5.1 等价性测试总策略：语义投影对比，不做字节 diff

新旧 builder 的合法差异（default 模板多余版式、endParaRPr、属性顺序）使字节对比不可行也不必要；等价合同定义为"同一 manifest 在两个 builder 下产物的**结构投影**相等"。投影由 `object_projection.py`（F3-T1）产出：

```
投影(pptx) = {
  slides: [ {
    objects: [ {kind, name, off_emu, ext_emu, rot, flip_h, flip_v,
                geometry: {prst | custgeom_vertices_normalized},
                fill, line: {color, width_emu, dash},
                text: [ {runs: [{text, size_centipoint, font_latin/ea/cs,
                                  color, bold, italic, baseline}],
                         align, anchor}] } ... 按 (z 序) 排序 ],
    background, notes_text_sha256 } ... ],
  media_hash_multiset, slide_size_emu }
```

### 5.2 用例矩阵（`tests/boundary/test_object_builder_equivalence.py`）

1. **基线等价**：4 类默认形状 + 文本（runs/paragraphs/全属性）+ 图片 + 背景的 manifest，双 builder 投影相等（off/ext EMU ±0 容差；custGeom 顶点归一化坐标 ±1/21600）。
2. **比例合同**：非 16:9 源（letterbox `content_box`）、`size_mode=source` 画布——px→英寸映射逐值相等（共享几何层 + 双端产物互证）。
3. **z_index 稳定排序**：同 z 值跨类混合，spTree 顺序一致。
4. **文本 fit**：`font_size_source=measured`（safety=1）与默认 safety=0.9 两条链字号输出一致（fit 在共享层，投影中 size 相等）。
5. **line 方向语义**：`points_px` 反向端点 → flipH/flipV 投影相等。
6. **roundRect adj**：`source_corner_radius_px`（px 路径）与 `radius`（英寸路径）→ adj 归一化值相等，clamp 50000 生效。
7. **dash/自由 preset**：`prstDash` token 全集映射；preset 合法值（diamond/chevron 等）投影相等；**非法 preset 双端行为**：legacy 产出（不合规 XML，测试断言其包含非法 prst 字符串以记录现状）vs 新 builder ValueError。
8. **重复 media 引用**：同文件两次引用——若触发 validator 误报即启动 patch 0007（§3.1.7），测试先行登记预期行为。
9. **notes 双路径**：纯 text；`notes_xml` 冻结字节（F2-T2 后字节全等断言）+ E26 hash 回归。
10. **确定性（CI-2）**：双 builder 各连跑 2 次 sha256 相等；`TZ=UTC`/`TZ=Asia/Tokyo` 交叉构建 hash 相等。
11. **validator 兜底通过性**：全部等价 fixture 的 pptx-builder 产物经 `validate_pptx.py`（page 级 + deck 级）`passed=true`——validator 零改动通过即最强等价证据。
12. **page.pptx 与 final deck 同构**：同 manifest 单页产物与 deck 内该页投影相等（`compile_page` 共用的直接验证）。

### 5.3 回归登记（tests/upstream/core-tests.yaml 新 suite）

```yaml
editable-object-builder:
  status: implemented
  runner: "python3 -m unittest discover -s tests/boundary -p 'test_object_builder*.py'"
  cases:
    - id: "test_object_builder_equivalence.py::ProjectionEquivalenceTest::test_baseline_objects_project_identically"
      contract: F1 迁移等价（manifest → 双 builder 结构投影相等）
      requires: python-pptx>=1.0.2（runtime venv 内置）
    - id: "test_object_builder_equivalence.py::DeterminismTest::test_same_manifest_same_sha256_across_tz"
      contract: CI-2 确定性（canonical zip 重打包）
    - id: "test_object_builder_equivalence.py::NotesFreezeTest::test_notes_xml_bytes_preserved_and_hash_verified"
      contract: E26 notes 冻结在 object builder 下不削弱
```

同时 `upstream-capabilities.yaml`：E21/E23 的 `integration` 更新为 adapter 分派层；新增条目（F1 对象面、F2 theme 双槽、F3 dump/diff、F4 patch 合并、F6 omissions）`proof` 指向新测试——沿用"capability 回归清单"纪律。

### 5.4 F3/F4 专项测试

- diff 三轴：构造位置漂移（±0.01/±0.05in）、文本一字之差、notes 缺页三 fixture，断言 exit 1 与报告字段；omissions 豁免后 exit 2。
- patch 合并：母本 30 页、补丁 3 页——27 页 part sha256 前后全等（字节保真断言）；注入补丁页失败 → baseline-preserved + PARTIAL-GATE 阻断；`[Content_Types]` 与 rels 一致性由 validate_pptx + Presentation 开包双冒烟。

---

## 6. 验证方案（validate_pptx 兜底 + 对象级 diff 验收）

1. **既有链路不动**：page 级 `validate_pptx.py`（record 门，L43-58 subprocess 调用）与 deck 级 `validate_deck` 是迁移的兜底回归——新产物必须零 validator 改动通过（仅 §3.1.7 列明的 media 多重集语义例外需 patch 登记）。
2. **对象级 diff 验收（upgrade 路线新增门）**：finalize 后跑 `editable diff`（exit 0/1/2）；record 阶段在 γ 的指纹收据（E1）就绪后把 diff 报告纳入收据五指纹之"QA 报告"类。
3. **迁移期双跑对照**（§9）：全量 evals（skill-up `evals/eval.yaml`）在两种 builder 默认值下各跑一轮，`skill-up report` 归档对照。
4. **可交付性证据链**：page validation.json `passed=true` + deck validation.json + （upgrade）object diff 报告 + （patch 合并）part hash 对账表，全部落盘为 versioned JSON（CLI 真值纪律）。

---

## 7. 测评扩展（evals case 草案 + judge 断言）

四个新 case（追加进 `evals/eval.yaml cases.files`，judge script 放 `evals/fixtures/scripts/`，断言遵循"否定感知"匹配纪律——FAIL_WORDS 对"未/不得/不会"表述做否定过滤）：

1. **`builder-flag-fallback.yaml`**（CI-3）——prompt 触发 direct-editable 且注入"新 builder 构建失败"信号（fixture: `LEO_EDITABLE_BUILDER=pptx` + 损坏 manifest）；judge 断言：run 回退 legacy 或报清晰失败，**不得产出半成品 page.pptx 声称通过**；旧 run（无 builder 字段）finalize 恢复成功。
2. **`object-diff-gate.yaml`**（CI-4/F3）——upgrade fixture：finalize 产物一处未登记文本漂移；judge 断言：`editable diff` exit=1 被阻断或如实上报，不得以 exit 0 放行；报告含三轴明细。
3. **`authorized-omissions-discipline.yaml`**（F6）——两变体：a) 未登记省略某文本对象 → FAIL；b) 已登记（估算级+reason）→ exit 2 WARN 可交付且 PARTIAL-GATE 提示；judge 断言引用级 omitted 恒被拒。
4. **`patch-merge-preserves-bytes.yaml`**（F4）——upgrade-selected 3/10 页；judge script 直接 sha256 对账产物 zip 内未选中页 part 与母本（脚本级判定，非 LLM 目测），断言相等且单页失败时原图片交付物完好（治理红线）。

每个 case 的 `input.prompt` 使用技能四路线术语；`judge.type: script`；超时/轮次沿 defaults。

---

## 8. 许可合规与 vendor 纪律

### 8.1 外部来源使用清单

| 来源 | 许可证 | 使用方式 | 义务 |
|---|---|---|---|
| python-pptx（`/Users/kuang/knowledge/ppt-github/python-pptx`） | MIT（Steve Canny） | 直接依赖（已在 `runtime/pyproject.toml` L17），无代码复制 | 依赖声明即可；升级视为重大变更（§3.1.5） |
| PptxGenJS `gen-xml.ts makeXmlTheme` | MIT | **配方思想**（headFontFace/bodyFontFace 双槽→fontScheme）；XML 按 OOXML 规范自写 | 思想来源注记（无代码搬运） |
| OfficeCLI `PptxBatchEmitter.cs`/`PowerPointHandler.Selector.cs` | Apache-2.0 | **思想移植**：dump/UnsupportedWarning/选择器语义/诚实失败；不引 C# 二进制、不复制代码 | 思想来源注记 |
| genoffice `generate.ts`/`landGeneratedPages` | Apache-2.0 | **思想移植**：字节保真补丁原则、失败页原位保留；无代码搬运 | 思想来源注记 |
| ppt-agent-skill `svg2pptx.py`/`html2svg.py` | MIT（sunbigfly） | F7 远期若引入：`svg2pptx.py` 为代码级移植 | 保留文件头版权与署名 + NOTICE/UPSTREAM 登记（F7-T1 评估时落实） |
| make-slide `references/pptx-spec.md` | MIT | 生成端约束清单并入 references（改编引用） | 来源标注 |
| presentation-skill `deck_ir.schema.json` | MIT | F5 schema 参照（字段语义，非逐字拷贝） | 来源标注 |
| xiaobei-skill（复杂度计分/authorized_omissions） | 无 LICENSE 记录 | 仅思想改写 | 代码/文本零搬运（会议纪律：无 LICENSE 从严） |

登记落点：`upstreams.yaml` 保持两 vendored 上游不变 + 新增 `thought_sources:` 段（或独立 NOTICE 增补）登记上述思想来源与许可证；CHANGELOG 每变更同步（user-visible 标注）。

### 8.2 vendored 合同保护（不静默重写）

- `build_pptx_from_manifest.py` / `validate_pptx.py` / `finalize_deck_run.py` 等 vendored 文件：**F1-T4 的分派在 leo 自有 adapter 层完成，vendor 文件 0 diff**。
- 例外两处须走正式 patch（先测试证明必要性再打）：
  - `patches/0007-editable-media-hash-multiset.patch`：validator media 反查改 hash 多重集（§3.1.7 重复引用场景）；
  - `patches/0008-editable-authorized-omissions.patch`：validator 承认登记省略（F6-T2）。
  - 二者均在 `upstreams.yaml image-to-editable-ppt.patches` 登记、`tests/upstream/core-tests.yaml` 挂聚焦回归（沿 0004/0006 先例）。
- `upstreams.yaml` `integration_adaptations` 增补一行：`builder selection flag（vendored zip writer 保留为 legacy；leo object_builder 为 pptx 路径）`；E21/E23/E26 capability 条目 `integration` 与 `disposition: enhanced` 更新——retained_contracts（"object-level PPTX build and structural validation"）语义不变，实现层切换显式可见。

---

## 9. 风险与回滚

### 风险登记（Top 3 加粗）

| # | 风险 | 概率×影响 | 缓解 | 回滚 |
|---|---|---|---|---|
| **R1** | **迁移行为回归**：新 builder 在长尾 manifest（手写 worker 产出的边角属性组合）上与 legacy 渲染不一致，污染交付 | 中×高 | ①双跑对照期（下述）；②validator 零改动通过作为硬门禁；③等价投影 CI 全绿才翻转默认；④evals 双跑归档 | 单点回滚：`LEO_EDITABLE_BUILDER=legacy`（无状态迁移，run 冻结字段保证已建 run 重建一致）；vendor 路径全程保留至 P2 末 |
| **R2** | **确定性破坏**：python-pptx/lxml 升级改变 XML 序列化（属性序/命名空间前缀/自闭合），CI-2 指纹漂移 | 低×高 | canonical repack 只消 zip 层差异；XML 层差异靠依赖 pin + golden hash 回归（依赖升级=重大变更流程）；builder id 进 app.xml 便于 γ 指纹分版本 | 回退依赖版本；必要时切 legacy（其 XML 生成纯字符串拼接，序列化面极小） |
| **R3** | **字节补丁产出损坏包**：zip_surgery 漏改 `[Content_Types]`/rels / id 冲突导致 PowerPoint 打不开 | 中×高 | 白名单原语 + 内存组装 + 双冒烟（Presentation 开页数 + validate_pptx）失败即弃；patch 仅限"页数一致替换"，不尝试结构重排 | merge_mode 自动回退 rebuild（assembler 既有路径）；母本只读、产物 atomic，原始交付物不受影响 |
| R4 | notes 冻结被库路径削弱（E26 红线） | 低×高 | 字节回写原语 + E26 hash 回归测试进 core-tests | F2-T2 独立可回退 |
| R5 | 原生表格/图表引入"看起来合理"的数据风险（质量门既有禁令） | 中×中 | F1-T6 限定"数据可逐字确认"场景 + 既有 validator/evals chart 门禁不放松 | tables/charts 为 manifest 可选段，不启用即零暴露 |
| R6 | patch 合并的孤儿 media 体积膨胀 | 低×中 | 保留策略优先保真；体积治理交 γ（D5）评估可选 GC | — |

**双跑对照期（R1 主缓解，三个发布阶段）**：

1. **阶段 A（合入期）**：默认 `legacy`；`pptx` 可选。门槛：等价套件全绿 + 全量 evals 在强制 `pptx` 下通过。
2. **阶段 B（对照期，≥1 个发布周期）**：默认 `pptx`；CI 每夜双跑（两种 builder 各跑全量 evals + golden hash 对照）；任何分歧进 known-issues 并阻塞默认翻转。
3. **阶段 C（收口）**：legacy 保留为显式逃生路径（文档声明），P2 末按分歧记录决定退役或长期保留。

---

## 10. 对其他团队的接口需求 / 暴露

### 10.1 给α（内容与合同层）——需求

1. manifest 可选段契约确认：`theme`（head/body 字体双槽）、`tables[]`/`charts[]`（列/行/数据逐字字段）、`authorized_omissions`、v2 的 `oid/evidence/reading_order/editability`——α 的合同文档需同步声明这些字段为**可选且校验语义由 δ 层实现**。
2. 内容合同禁坐标条款：v2 起 prompt/大纲/母版层禁放任意坐标（坐标归执行层），请α在内容文档门（outline/master doc gates）校验中加对应拒绝规则。
3. `evidence.tier` 与三级标注的权威枚举对齐（引用|估算|示意）：omissions 联动规则（引用级禁 omitted）依赖该枚举不漂移。

### 10.2 给β（风格版式资产层）——需求

1. style brief 头部主题元数据（B5：size/colors/fonts/fontSizes/space 五段令牌）落定后，向 δ 提供其中 **fonts（head/body 双槽）与 colors（accent1–6 + bg/tx 映射）** 的机器可读侧（JSON sidecar 即可），δ 的 object_builder 将其编译进 theme1.xml——实现"brief → theme1.xml 单一上游"。
2. 画布比例/尺寸令牌（16:9 基准）与 `slide.width/height` 英寸口径统一（slidev `canvasWidth+aspectRatio` 同构），避免双源换算。
3. 版式骨架若需占位符语义（placeholder 继承），请给出占位符类型清单（title/body/...），δ 在 F1 后续迭代接线 `slide_layouts` 占位符。

### 10.3 给γ（渲染与质量闭环）——需求与承诺

1. **确定性承诺（CI-2）**：δ 保证同 manifest + 同 builder 版本 → 同 sha256（canonical zip：条目序 `[Content_Types].xml`→`_rels/.rels`→字典序、date_time=1980-01-01、DEFLATED）；γ 指纹收据可直接对 page.pptx/final.pptx 取 sha256。**请求**：γ 的收据把 `builder_id`（app.xml Application）纳入指纹上下文，跨版本不误判。
2. 对象级 diff 报告（三轴 + exit 0/1/2）请纳入 γ 的 QA 报告指纹类；E1 收据的"模板/样式源"类请包含 β 的主题 sidecar。
3. `LEO_EDITABLE_BUILDER` 失败回退事件请纳入 γ 的 E4 容错协议信号集（builder 回退=该页阶段级重试的一种）。
4. δ 保留 `render_preview()`（PIL 像素近似）作为对象级路径的页面预览源；γ 的确定性渲染 lane（D 支柱）产物若进 PPTX，请走 `images[]`（provenance: user-approved-rasterization / imagegen）或远期 F7 vector_lane，两条通道 δ 均已预留。

### 10.4 δ 暴露给全团队的接口（稳定面）

| 接口 | 形态 | 稳定性 |
|---|---|---|
| `write_pptx / write_deck / compile_page / normalize_manifest` | Python API（同 legacy 签名） | 冻结（调用方零改动） |
| `LEO_EDITABLE_BUILDER` + deck_manifest `builder` 冻结字段 | env + run 字段 | 迁移期合同，阶段 C 前不改语义 |
| `leo-ppt editable inspect <pptx> [--selector S] --out json` | CLI，versioned JSON | v1 |
| `leo-ppt editable diff --source --produced --axes --omissions` | CLI，exit 0/1/2（CI-4） | v1 |
| `scripts/score_page_complexity.py <page_dir>` | CLI，JSON（6 项分值 + 触发判定） | 阈值常量冻结后 v1 |
| `upgrade zip_surgery / patch_merger`（merge_mode=patch） | Python API + delivery manifest `pages[N].mode` 字段 | v1 |
| manifest 可选段：`theme/tables[]/charts[]/authorized_omissions`；v2：`oid/evidence/reading_order/editability` | schema（references/manifest-schema.md 为真值） | v1 可选段向后兼容；v2 版本化 |

---

## 附：本设计读取过的关键文件（证据索引）

- leo 现状：`build_pptx_from_manifest.py`（1002 行全读）、`validate_pptx.py`、`finalize_deck_run.py`、`prepare_deck_run.py`、`record_page_result.py`、`deck_run_state.py`、`editable/adapter.py`、`hybrid/assembler.py`、`upgrade/baseline.py`、`runtime/pyproject.toml`、`references/manifest-schema.md`、`references/page-decision-tree.md`、`references/editable-workflow.md`、`upstreams.yaml`、`upstream-capabilities.yaml`、`tests/upstream/core-tests.yaml`、`tests/boundary/test_editable_patch_regressions.py`（加载模式）、`evals/eval.yaml` + case 样例、`_input_normalization.py`（notes 提取段）
- 参考：python-pptx `util.py`/`shapes/autoshape.py`/`shapes/freeform.py`/`parts/slide.py`/`templates/theme.xml`/`shapes/shapetree.py`（add API 清单）；OfficeCLI `PowerPointHandler.Selector.cs`/`PptxBatchEmitter.cs`（头注与结构）；genoffice `generate.ts`（字节保真头注）；ppt-agent-skill `svg2pptx.py`/`html2svg.py`（依赖与实现形态）；make-slide `references/pptx-spec.md`
