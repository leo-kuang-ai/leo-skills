# leo-ppt-generator 执行流程图

- 日期:2026-08-29 · 配套正文见本文件同目录会话梳理,权威源为
  `leo-ppt-generator/SKILL.md` 与 `references/*.md`(含 2026-08-29 叙事合同/密度路由新环节)。
- 用法:下方 Mermaid 可在 GitHub / 支持 mermaid 的查看器直接渲染;节点编号对应
  image-deck-workflow 的步骤号(G=generate,E=editable)。

```mermaid
flowchart TD
    %% ========== 入口三道闸 ==========
    START([用户请求]) --> G0{Gate 0<br/>Office 信任}
    G0 -- "PPT/PPTX 未确认可信" --> BLOCK0[/"固定五字段块<br/>blocked/untrusted_office_input<br/>不读取·不扫描·不净化"/] --> END0([本轮终止])
    G0 -- "可信/PDF/图片/文本" --> MODE{交互模式}
    MODE -- "advise(咨询/比较/状态)" --> ADV[/"五字段块先行<br/>Route 表作答,禁碰工具与文件"/] --> ENDA([结束])
    MODE -- "execute(制作/转换/升级)" --> GATE2[控制面合同:<br/>五字段块最先输出]

    %% ========== 路由 ==========
    GATE2 --> ROUTE{input-routing<br/>四选一 Route}
    ROUTE -- "新建演示文稿<br/>(文章/报告/大纲)" --> GEN
    ROUTE -- "图片/PDF/可信Office<br/>→对象级可编辑" --> EDI
    ROUTE -- "image-deck 全量升级" --> UPF["冻结原交付物<br/>页面/hash/尺寸/notes"]
    ROUTE -- "image-deck 指定页升级" --> UPS["冻结选中页集合<br/>默认不许 partial"]
    UPF --> EDI
    UPS --> EDI

    %% ========== generate 主流程 ==========
    subgraph GEN["generate · 五阶段十二步"]
        direction TB
        S1[①冻结内容合同<br/>one_thing + 哇点登记<br/>三级标注:引用/估算/示意<br/>图像来源三级]
        S1 --> S2[②大纲] --> C1{用户确认}
        C1 -- 否 --> S2
        S2 -- 是 --> S3[③逐页母版·四段<br/>条件化标题/禅档位要点/<br/>视觉行落位+图像来源/<br/>speaker_script·engineering]
        S3 --> SUB[减法审计] --> C2{用户确认}
        C2 -- 否 --> S3
        C2 -- 是 --> S3A[3a 数据密度路由<br/>≥6点→可编辑路线<br/>4-5点→形状语法强制<br/>≤4巨数→数字海报]
        S3A --> S4[④视觉方向 2-3 个] --> C3{用户确认}
        S4 -- 否 --> S4
        C3 -- 是 --> S5[⑤固定图片 backend]
        S5 --> S6[⑥样张 ×1] --> C4{样张确认<br/>不可跳过}
        C4 -- 否 --> S4
        C4 -- 是 --> S7[⑦image prepare<br/>冻结输入→canonical state]
        S7 --> S8[⑧逐页派发 slide worker<br/>样张继承·禁本地渲染冒充]
        S8 --> S9[⑨image record<br/>失败留在同一 state]
        S9 --> S10{⑩对抗式 QA 闭环}
        S10 -- "任一失败" --> FIX[先修母版→重建受影响页<br/>再检=目标判据+波及面] --> S8
        S10 -- 全部通过 --> S11[⑪全部 recorded<br/>→ assemble<br/>缺页不得组装]
        S11 --> S12[⑫重开 PPTX 复验<br/>页数/notes/固定件/交叉引用<br/>+叙事三查:首尾回扣one_thing·<br/>中段三关键点·Σ用时≤合同+15%]
        S12 -- "hash 变化→新 revision 重验" --> S11
        S12 --> S13[⑬交付验证分别执行分别报告<br/>provider/OCR/viewer/桌面/投屏/人工<br/>未运行=not-run]
        S13 --> ACC{delivery_readiness}
        ACC -- accepted --> DONE([交付闭环])
        ACC -- acceptance_pending --> PEND[/"不得声称交付完成<br/>给唯一下一步"/] --> END2([等待验收])
    end

    %% ========== editable / upgrade ==========
    subgraph EDI["direct-editable(含 upgrade 落地)"]
        direction TB
        E1[G·prepare<br/>editable prepare run]
        E1 --> E2[读 manifest-schema<br/>+ page-decision-tree]
        E2 --> E3[循环 editable next --json<br/>逐页取任务]
        E3 --> E4[page worker 只写本页目录<br/>build-page-worker-prompt]
        E4 --> E5{页面 recorded?}
        E5 -- 否 --> E3
        E5 -- 是 --> E6{全部目标页?}
        E6 -- 否 --> E3
        E6 -- 是 --> E7[editable finalize<br/>manifest 校验]
        E7 --> E8[逐页检查:字体替代/CJK字号/<br/>溢出/遮挡/required text]
        E8 --> E9[交付验证:结构+真实证据<br/>禁止截图叠字冒充对象级]
        E9 --> DONE
    end

    %% ========== 样式 ==========
    classDef gate fill:#fdecec,stroke:#c0392b,color:#7b241c
    classDef confirm fill:#fff7e0,stroke:#b7950b,color:#7d6608
    classDef state fill:#eaf2fd,stroke:#2471a3,color:#154360
    classDef done fill:#eafaf1,stroke:#1e8449,color:#145a32
    class G0,BLOCK0 gate
    class C1,C2,C3,C4,S10,ACC,MODE,ROUTE,EDGE confirm
    class S7,S9,S11 state
    class DONE,END0,ENDA,END2 done
```

## 读图要点

1. **红色系 = 硬门禁**(Gate 0 与模式判定),命中即终止或降级,无绕行路径。
2. **黄色菱形 = 用户确认点**:大纲、母版、视觉方向、样张四处,execute 授权不可豁免;样张确认是生成前最后一道。
3. **蓝色节点 = CLI 状态边界**(prepare / record / assemble):跨过这条线的每一步都要 CLI versioned JSON 佐证,聊天声明无效。
4. **QA 打回的箭头指回 worker 派发但先经过「修母版」**:内容问题在母版层修(一行),视觉问题才改 prompt/backend。
5. **upgrade-full / upgrade-selected 在进入 editable 子图前多一步「冻结」**:原交付物 hash 化,失败不得破坏;selected 默认不交付 partial。
6. `delivery_readiness=accepted` 之前一切状态(含 run completed)都**不是**交付声明。
