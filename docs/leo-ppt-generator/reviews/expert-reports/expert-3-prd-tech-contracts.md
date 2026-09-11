# 专家报告 3 · 技术架构（可行性与合同完整性）

- 评审对象：`docs/prd/2026-09-11-leo-ppt-capability-improvement-prd.md`（v1.0）
- 立场：可行性、依赖真实性、合同修订面完整性、与既有红线/机制冲突
- 日期：2026-09-11 · 独立盲评 · 已交叉核对 SKILL.md / execution-contract / render-contract / manifest-schema / backend-selection / build_rendered_ledger.py 等

## 总体结论

**有条件通过。** 14 条需求方向与"三层职责"归位判断成立，绝大多数"基建已备"声明经交叉核实属实（render lane 合同完整、`overlay_text.py`/`compute_impact.py`/44 单元矩阵 fixture/`check_worker_brief` 四块/F1 等价套件均在场）。但 P0 的 R-70 合同修订面存在实质性遗漏——TF 链权威定义与"唯一封闭例外"红灯原文不在修订清单内，"hybrid"命名与既有术语撞车；R-72 双 builder 等价验收与 manifest 可选段先例矛盾；R-73 的 OCR 通道依赖与现状不符。

**通过条件**：①R-70 修订面补全（C-1/C-3/C-12）并消歧命名（C-2）；②R-72 先定义 legacy 对 `charts[]` 行为再谈等价（C-4）；③R-73 先核实 OCR 通道全册可用性与缺失处置（C-5）；④R-80 补 embedding 模型依赖与许可登记（C-10）。

## Findings

- **C-1 [major] R-70 必须修改**：合同修订清单漏掉 TF 链两处权威定义地——`image-deck-workflow.md`「文字保真降级链」节与 `SKILL.md` 不变边界。后者有硬原文："**唯一封闭例外**：经样张确认的 text-fidelity-fallback 模式（TF-2）……**此例外不延伸到任何其他本地合成场景**"——混合页正是"其他本地合成场景"，转正即落在该红灯原文上。→ 修订面增列两文件，显式把"唯一封闭例外"改写为封闭枚举（TF-2 fallback + 组合页常规页型）。
- **C-2 [major] R-70 必须修改**：页型名 `hybrid` 与既有术语冲突——"hybrid"已被占用为交付形态（image 页 + editable 页混装：partial-hybrid、hybrid 混装尺寸统一、backend-selection 默认推荐）。单页内"图像背景 + 渲染文字层"再用 hybrid 一词两义。→ 改用 `composite`/`layered`，或显式消歧并回改四处措辞。
- **C-3 [major] R-70 必须修改**：合成产物 provenance 归属未进修订面——render-contract §2 backend 枚举 + sidecar、sources-manifest 的 `source_class` 枚举、execution-contract 全册尺寸预算（`image_lane_px`/`render_lane_px`）都是**单页单来源模型**；组合页一页两源需要合同裁决。→ 增列三处并给出"双 provenance 子记录"形态。
- **C-4 [major] R-72 必须修改**：验收 3"双 builder 等价"与 manifest 先例矛盾——`tables[]` 的既定合同是"仅 pptx 消费；legacy 忽略"，`charts[]` 大概率沿用；legacy 忽略则 charts 页缺图表，等价断言不可能成立。→ 先定义 legacy 对 `charts[]` 行为（整页拒绝或声明投影等价子集），再写等价验收。
- **C-5 [major] R-73 必须修改**：OCR 通道依赖与现状不符——`build_rendered_ledger.py` 读 run 目录现成 OCR txt，其生产者（PaddleOCR）是"editable 阶段非必需在线增强"，普通图片式生成不披露；即 generate 路线 OCR 非每页保证、质量分两档、缺失页只标 missing。升 record 前置门则每页必有 OCR——通道生产者、builtin-ink 逐字对齐质量、缺失处置（阻断 or not_run 披露）均未写。→ 增加前置核实项与缺失处置路径；误报校准按 OCR 档位分层。
- **C-6 [minor] R-71 质疑待答辩**：U3"同一绑定物化"属实，但其输入是**选定后**绑定 + 冻结设计；R-71 预览发生在 SAMPLE-GATE 同轮，多数页尚无 selected 绑定。→ 答辩预览用候选默认绑定还是逐页先选定；未选定页预览代表性口径。
- **C-7 [minor] R-71 建议**："断言无网络请求"须精化为"无**外部**网络请求"（render lane 字体经 localhost `/leo-fonts/` 供给）；40 页 ≤60s 涉及逐页 playwright + chromium 启动，先跑 spike 再定阈值。
- **C-8 [minor] R-72 建议**：3a 口径统一应含文本回写（"原生图表"显式指向 charts[]）；非目标"render:mermaid/echarts 既有"中 echarts 是"占位枚举（P2 未落地）"，措辞改"既有枚举占位"。
- **C-9 [minor] R-77 质疑待答辩**：TF 触发率派生路径未指明——TF-1 事件散在 run-ledger qa 失败 + `revision_kind: post-confirm`，TF-2 在 slide job `text_fallback: true`；需明确联查工件与判重口径（一页多轮 TF-1 算几次）。
- **C-10 [minor] R-80 必须修改**：embedding 模型依赖未声明——来源（内置/自备）、体积、许可登记（仓库有 upstreams/NOTICE 纪律）、"模型不可用/未下载"降级档未覆盖；模型获取是新增一次性网络动作。→ 补模型选型、获取方式与许可登记。
- **C-11 [minor] R-79 建议**：alt 清单与 R-78 拼图入交付收据须明确"加性字段不进五类指纹集合"，否则 `receipt verify` 语义漂移波及全部交付。
- **C-12 [minor] R-70/R-78 建议**：交付披露"TF-2 fallback 页清单"口径须随组合页转正收窄到真正降级页，否则常规组合页被误判红灯或反向披露缺位。

**红线静默破坏专项检查**：无任何条目*意图*削弱 CLI 真值/凭据边界/不可杜撰/已验证交付物不降级；但三处*实施细节*会静默破坏既有机制：C-1（落在"唯一封闭例外"红灯原文上）、C-4（legacy 忽略 charts[] 使 F1 双跑等价静默失效）、C-5（OCR 缺失页处置未定义，有静默放行或静默全册阻断两向风险）。

## 一句话立场

骨架健康、依赖大体诚实，但 R-70 的修订面漏了它最需要改的两份文件且撞了 hybrid 术语，R-72/R-73 的验收各有一处与既有合同/现实矛盾——补齐这四处后本批可放行。
