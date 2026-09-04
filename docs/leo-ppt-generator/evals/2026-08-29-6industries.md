# leo-ppt-generator 六行业全流程测评报告(2026-08-29)

- 主题:「AI Agent 落地一年:从试点到规模化」,一题六景(金融/医疗/制造/教育/政务/零售)
- 执行:主持人 + 6 个场景 agent(两波×3 并行),全流程真实执行——母版 → `style render
  --materialize` 确定性注入 → 样张对抗式自审 → `image prepare` → 逐页真实 gpt-image-2
  生成(2560×1440)→ `image record` → `image assemble` → PPTX 机检 → 主持人独立读图抽检
- 产物:`leo-ppt-workspace/eval-6ind-0829/deliveries/` 六份 PPTX(各 6 页 + 6 notes);
  方案与逐景裁决见同目录 `EVAL-PLAN.md`、`verdicts/`
- 预算实耗:37 张真实生成(含冒烟),单页 26-90 秒;6 agent 合计约 2.5 小时 wall time

## 一、总分:76/84(90.5%)

| 场景 | 风格/模式 | D1 流程 | D2 内容 | D3 注入 | D4 生成 | D5 视觉 | D6 组装 | D7 诚实 | 总分 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| finance | 麦肯锡咨询/金字塔 | 2 | 2 | 2 | 1 | 2 | 2 | 2 | 13 |
| medical | 极简/金字塔 | 1 | 2 | 2 | 2 | 2 | 2 | 2 | 13 |
| manufacturing | 工程蓝图/教学分解 | 1 | 2 | 2 | 2 | 2 | 2 | 2 | 13 |
| education | 包豪斯/教学分解 | 2 | 2 | 2 | 2 | 2 | 1 | 2 | 12 |
| government | 政府工作报告/金字塔 | 2 | 2 | 2 | 2 | 2 | 1 | 2 | 13 |
| retail | 波普艺术/视觉展示 | 1 | 2 | 2 | 2 | 1 | 2 | 2 | 12 |

D3(确定性注入)与 D7(诚实度)**六景满分**;失分集中在 D1/D6 的流程摩擦与 D5 的单字
渲染偏差——没有任何场景失分于内容纪律或风格系统。

## 二、内容纪律实测(本轮最重要的验证结论)

每个材料包都埋了两个受控陷阱,六景全部正确处置:

- **unknown 埋点 6/6 拒上版**:无出处数字(NPS 82/满意度 96%/OEE+12pp/兴趣+40%/
  办结率 99.2%/复购+23%)在母版三级标注表被判 unknown,未出现在任何页面文案、
  生图 prompt 与口播稿中,部分场景在母版留痕求证路径——**内容事实门在真实流程中成立**。
- **估算埋点 6/6 双重标注**:估算数字(1200 万/2.5 FTE/860 万/3.5 小时/14 人/45 万元)
  全部以「估算」括注 + 视觉第二线索(描边/角标)上版,符合置信度形状语法。
- **数字保真**:抽检页面全部数字与材料包逐字一致(41%→68%、86.4%/17%/4.1%、
  2→22 条、6 班 340 人、91.7%、26→9 小时、9.6%、3,400 路等);全部 36 页无编造基准值。
- **R15 图表诚实性实证**:medical P21(规格版式)在真实数据只有 3 项时,prompt 明确
  「no decorative vertical bars, use hairline grid」,成品**零装饰竖线、数值直接标注**——
  「编形状=编数据」的红线在生图链路可执行。
- **六种风格身份全部成立**:麦肯锡近白+navy 强调、极简大留白、深蓝图标注线稿、
  包豪斯三原色几何、政务红底白字横幅+金 hairline、波普半调网点撞色——六轴路由的
  视觉区分度在成品上肉眼可辨,无「换皮同脸」。

## 三、缺陷发现(按严重度)

**H1 · image edit 模式整体不可用(6/6 场景命中)**
vendored `image_gen.py` 的 `_edit` 调用 `_decode_write_and_downscale()` 缺
keyword-only 参数 `expected_size`,TypeError 崩溃且重试必现;backend contract 却声明
`edit: true`(合同与实际能力不符)。全部场景按预案降级 generate 模式,风格继承退化为
prompt 文字化描述(成品一致性经对抗审查成立,但参考图继承通道断了)。修复需走
patches 流程(0007)。

**H2 · prepare 契约摩擦四连(6/6 命中,平均每场景损耗 2 次 run 重建)**
① `image prepare --slides` 只接受**顶层 JSON 数组**,传入 deck-spec dict 报误导性
`input_too_large`→兜底 `contract_error`(文档与骨架均为 dict 口径);② 先 prepare 后
`run create` 会让 canonical state 落错位置,assemble 报 `contract_error`(需 run create
先行,或幂等 prepare 修复);③ `slides_fingerprint_conflict` 死锁无恢复命令,只能重建
run(PNG 产物可保留);④ notes 必须放每页 `notes` 字段(`speaker_focus` 不映射),
漏了要到 assemble 才发现 notesSlides=0。

**M1 · assemble --output 限制在 `<run>/final/` 内**:`deliveries/` 路径报
`output_outside_run`,需进程外复制。
**M2 · reason code 兜底化**:`contract_error` 掩盖子因(missing_page_artifact /
output_outside_run / 指纹冲突),三个 agent 都靠读源码定位,可诊断性差。
**M3 · image_rendering no-text 守卫与整页路线冲突(F2,复现确认)**:守卫会经
Global Style 块流入整页 prompt;本轮按评测缓解(删除该字段)全部绕开,需按路线作用域修复。
**M4 · 直调 venv CLI 报 `style_not_found`**:风格库定位依赖 `LEO_PPT_BUNDLE`,只有
launcher 会设置;错误信息不提示该因,首次使用者易困。

**L1 · 单字渲染偏差 1/36 页**:retail P9 出处行缺「约」字,重试 1 次未修复,估算标记
仍在——生图模型文字保真的物理上限,现有「重试≤1+诚实登记」处置正确。
**L2 · finance PPTX `sldSz type="screen4x3"`** 与实际 16:9 尺寸不符(组装器属性遗漏)。
**L3 · `speech.md` 连播稿**文档声明 assemble 生成,实际产物未见;叙事三查的 Σ用时
门禁无 CLI 自动校验(母版内人工核算)。
**L4 · run create 完整形参(--input/--backend-contract)报 `route_contract_error`**,
基本形可用;兜底码无子码。

## 四、结论与建议

1. **内容与风格层已达产级**:三级标注/unknown 门/密度路由/哇点/one_thing/六轴风格
   路由全部在真实生图链路验证通过,这是本技能区别于「模板套壳」的核心资产。
2. **工程摩擦是当前主要失分源**:H2 四连坑 + M1/M2 集中在 prepare/assemble 的合同
   与诊断面;建议下一批工程单元:prepare 接受 dict 或改文档口径、run create 时序
   校验前移、指纹冲突提供恢复命令、reason code 透出子码、assemble 输出面放宽或文档明示。
3. **edit 通道修复(H1)**:单个 patch 即可恢复参考图继承,收益最大。
4. 产物样张可直接用作风格路由文档的例证库(六景封面 + medical P21 反 chartjunk 实证)。

## 五、验证口径声明

- 本报告的 D5 视觉结论 = agent 逐页对抗式自审 + 主持人独立抽检(6 封面 + P21/P9 共
  8 张)双重确认;OCR 机检、PowerPoint 桌面打开、投屏与人工审美验收未执行(not-run)。
- 六份 PPTX 交付于 `leo-ppt-workspace/eval-6ind-0829/deliveries/`(git-ignored 工作区),
  结构机检 6×(slides=6, notes=6, media=6)全部通过。
