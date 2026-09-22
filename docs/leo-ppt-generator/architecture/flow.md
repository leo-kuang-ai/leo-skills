# leo-ppt-generator 执行流程图

- 日期:2026-09-18 · 配套正文见[执行流程](../execution-workflow.md),权威源为
  `leo-ppt-generator/SKILL.md`、`references/*.md` 与运行时 CLI。
  相对 2026-08-29 版本的增补:表达冻结链(内容包 → PipelineRequest → `generate --request`)、
  模板库 v2 的 current 指针与 registry 发现、worker 逐页三层容错、🔶 SAMPLE-GATE 与
  🔴 PARTIAL-GATE / DELIVERY-GATE 两处交付边界、交付门扩展(尺寸预算与 preflight 聚合)。
- 用法:下方 Mermaid 可在 GitHub / 支持 mermaid 的查看器直接渲染;生成节点编号按当前主线顺序
  ①–⑫(aligned 到 image-deck-workflow 的十二步主干,3a/3b/3c 与交付门为新增标注),可编辑节点
  以 E 前缀表示。

```mermaid
flowchart TD
    %% ========== 入口三道闸 ==========
    START(["用户请求"]) --> G0{"Gate 0<br/>Office 信任"}
    G0 -- "PPT/PPTX 未确认可信" --> BLOCK0[/"固定五字段块<br/>blocked/untrusted_office_input<br/>不读取·不扫描·不净化"/] --> END0(["本轮终止"])
    G0 -- "可信/PDF/图片/文本" --> MODE{"交互模式"}
    MODE -- "advise(咨询/比较/状态)" --> ADV[/"Route 表作答;风格查询只读<br/>current 指针与 registry.json"/] --> ENDA(["结束"])
    MODE -- "execute(制作/转换/升级)" --> GATE2["前置低成本核对:<br/>宿主 worker 能力·Provider 三态·费用区间"]

    %% ========== 路由 ==========
    GATE2 --> ROUTE{"input-routing<br/>四选一 Route"}
    ROUTE -- "新建演示文稿<br/>(文章/报告/大纲)" --> GEN
    ROUTE -- "图片/PDF/可信Office<br/>→对象级可编辑" --> EDI
    ROUTE -- "image-deck 全量升级" --> UPF["upgrade inspect<br/>冻结原交付物<br/>页面/hash/尺寸/notes"]
    ROUTE -- "image-deck 指定页升级" --> UPS["upgrade inspect<br/>冻结选中页集合"]
    UPF --> IMP["upgrade import-baseline<br/>source_binding 关联源 run<br/>输入漂移即 conflict"]
    UPS --> IMP
    IMP --> EDI

    %% ========== generate 主流程 ==========
    subgraph GEN["generate · 十二步主线"]
        direction TB
        S1["①内容合同<br/>one_thing + 哇点 + 反方与边界<br/>四级标注 + 学术三字段"]
        S1 --> S2["②大纲 outline-vN<br/>论断句 + 证据跟随<br/>结构页显式成页"]
        S2 --> S3["③逐页母版 deck-master-vN<br/>四段 + 禅档位 + page_id<br/>>40 页按节分批确认"]
        S3 --> S3A["3a 数据密度路由"] --> S3B["3b 素材校验<br/>validate_assets"] --> S3C["3c 事实核查<br/>高保障档"]
        S3C --> S4["④风格:registry 有界发现<br/>→摘要核对→指纹守卫"]
        S4 --> S5["⑤版式调度 page_intent<br/>+容量预检+强视觉复用上限"]
        S5 --> S6["⑥backend 三态<br/>+全册尺寸预算 size-budget"]
        S6 --> S7["⑦正文难页样张 ×1"]
        S7 --> SG{"🔶 SAMPLE-GATE<br/>呈现认可或显式豁免"}
        SG -- "不满足" --> S7
        SG -- "认可/豁免记录" --> S8["⑧🔒表达冻结:content pack<br/>→PipelineRequest<br/>→generate --request→输入代"]
        S8 --> S9["⑨slides/术语/sources<br/>→image prepare 只读已提交代"]
        S9 --> S10["⑩真实 worker 派发<br/>阶段重试≤3·清扫≤2 轮·rendered 跳过"]
        S10 --> S11{"⑪逐页 QA<br/>五层非补偿门"}
        S11 -- "任一必要项失败" --> FIX["先修母版→重建受影响页<br/>TF-1→TF-2 降级链"] --> S10
        S11 -- "全部 recorded" --> S12["⑫assemble 组装<br/>缺页不组装·hash 变化新建 revision"]
        S12 --> S13["交付门:geometry / size-budget /<br/>sources --strict / preflight / receipt"]
        S13 --> ACC{"delivery_readiness"}
        ACC -- accepted --> DONE(["交付闭环"])
        ACC -- "其他状态" --> PEND[/"不得声称交付完成<br/>给唯一下一步"/] --> END2(["等待验收"])
    end

    %% ========== editable / upgrade ==========
    subgraph EDI["direct-editable(含 upgrade 落地)"]
        direction TB
        E1["editable prepare<br/>冻结 builder 与 page jobs"]
        E1 --> E2["读 manifest-schema<br/>+page-decision-tree"]
        E2 --> E3["循环 editable next --json<br/>逐页取任务"]
        E3 --> E4["page worker 只写本页目录<br/>build-page-worker-prompt"]
        E4 --> E5{"页面 recorded?"}
        E5 -- 否 --> E3
        E5 -- 是 --> E6{"全部目标页?"}
        E6 -- 否 --> E3
        E6 -- 是 --> E7["editable finalize<br/>manifest 校验·双 builder 等价"]
        E7 --> E8["逐页检查:字体替代/CJK字号/<br/>溢出/遮挡/required text"]
        E8 --> E9["delivery assemble<br/>hybrid 混装尺寸统一 1e-6"]
        E9 --> DONE
    end

    %% ========== 样式 ==========
    classDef gate fill:#fdecec,stroke:#c0392b,color:#7b241c
    classDef confirm fill:#fff7e0,stroke:#b7950b,color:#7d6608
    classDef state fill:#eaf2fd,stroke:#2471a3,color:#154360
    classDef done fill:#eafaf1,stroke:#1e8449,color:#145a32
    class G0,BLOCK0 gate
    class MODE,ROUTE,SG,S11,ACC confirm
    class S8,S9,S10,S12,S13 state
    class DONE,END0,ENDA,END2 done
```

## 读图要点

1. **红色系 = 硬门禁**(Gate 0 与模式判定),命中即终止或降级,无绕行路径。
2. **黄色菱形 = 需人裁决的点**:🔶 SAMPLE-GATE 是默认委托执行下唯一默认等待点(逐页派发前的最后一道);
   PARTIAL-GATE 在 upgrade-selected 失败集上单独确认;delivery_readiness 非 `accepted` 一律不是交付闭环。
3. **蓝色节点 = CLI 状态边界**(prepare / record / assemble / 输入代冻结):跨过这条线的每一步都要
   versioned JSON 佐证,聊天声明无效;表达冻结后改版必须建新 run。
4. **QA 打回的箭头指回 worker 派发但先经过「修母版」**:内容问题在母版层修,视觉问题才改 prompt/backend;
   文字失败先走 TF-1(母版减法、同 backend 重生成),再走需样张重确认的 TF-2(留白贴字)。
5. **upgrade-full / upgrade-selected 在进入 editable 子图前多两步「冻结 + 关联」**:`upgrade inspect`
   冻结原交付物,`upgrade import-baseline` 以 source_binding 关联源 generate run;失败不得破坏原成品,
   selected 默认不交付 partial。
6. **run 记录在 backend 合同签署时创建**(约 ⑥ 处):此前的合同、大纲与风格确认属会话内工作,不落 run;
   ⑧ 的输入代一旦提交即不可变,`image prepare` 只核对页身份、页序并登记补充输入,内容或设计改版必须建新 run。
