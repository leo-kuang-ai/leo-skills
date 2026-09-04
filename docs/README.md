# docs/ 目录导航

本目录存放 leo-skills 仓库的技能包文档、评测报告、评审记录和规划文档。

## 目录结构

### 技能包文档

#### `leo-ppt-generator/`
PPT 生成技能相关文档

- **architecture/** - 架构设计与流程图
  - `flow.md` - 执行流程图（Gate 0-5 + 四路由）
  - `style-library-target-architecture.md` - 风格库目标架构
  
- **evals/** - 评测报告（按日期排序）
  - `2026-08-29-docgates.md` - 文档门禁评测
  - `2026-08-29-pagecount.md` - 页数合同评测
  - `2026-08-29-6industries.md` - 6 行业评测 R1
  - `2026-08-30-6industries.md` - 6 行业评测 R2
  - `2026-08-30-industry.md` - 行业单轮评测
  - `2026-08-31-stability-10r-m01.md` - 10 轮稳定性评测
  - `2026-08-31-cross-eval-6judges.md` - 6 判官交叉评测
  - `2026-09-01-style-route-50industries.md` - 50 行业风格路由评测
  
- **reviews/** - 评审文档
  - `lifecycle-ux-plan.md` - 生命周期 UX 规划
  - `master-panel-20-rounds.md` - 20 轮判官主评审
  - `multi-industry-expert-review.md` - 多行业专家评审
  - `optimization-review.md` - 优化评审
  - `quality-loop-optimization.md` - 质量闭环优化
  - `style-review.md` - 风格评审
  - `ux-review.md` - UX 评审
  - `2026-08-30-6-experts-integration.md` - 6 专家集成评审会
  - **expert-reports/** - 专家独立报告
    - `expert-1-skill-prompt-engineering.md` - 专家1：Skill 提示词工程
    - `expert-2-e2e-product-architecture.md` - 专家2：端到端产品架构
    - `expert-3-academic-content-planning.md` - 专家3：学术风格内容策划
    - `expert-4-agent-orchestration-quality.md` - 专家4：Agent 编排质量闭环
    - `expert-5-rendering-image-pipeline.md` - 专家5：渲染图像管线基建
    - `expert-6-slide-framework-core.md` - 专家6：幻灯片框架格式内核
    
- **tech-plans/** - 技术规划
  - `multi-industry-optimization-tech-plan.md` - 多行业优化技术规划

#### `evidence-first-writing/`
证据优先写作技能相关文档（待补充）

### 静态资源

#### `assets/`
- **images/** - 图片资源
  - `darwin-leo-ppt-generator-card.png` - Leo PPT Generator 卡片
  - `image.png` - 通用图片
  
- **guides/** - 指南手册
  - `spec-first-gzh-manual-v1.0.md` - Spec-First 公众号手册 v1.0（Markdown）
  - `spec-first-gzh-manual-v1.0.pdf` - Spec-First 公众号手册 v1.0（PDF）

### 外部内容

#### `external-content/`
发布到外部平台的内容
- `zhihu-answer-01-sdd-practice.md` - 知乎回答：SDD 实践

### 工作目录

#### `plans/`
带日期的规划文档（格式：`YYYY-MM-DD-{编号}-{主题}-plan.md`）
- 包含 fusion-team-designs/ 子目录

#### `tasks/`
带日期的任务文档（格式：`YYYY-MM-DD-{编号}-{主题}-tasks.md`）

#### `brainstorms/`
头脑风暴记录

#### `ideation/`
创意构思记录

#### `prototypes/`
原型设计文档

#### `file-github-expert-reports/`
另一组专家报告（文件整合方向）

## 文档命名约定

### 评测报告
格式：`YYYY-MM-DD-{主题}.md`
- 按执行日期排序
- 主题简洁描述评测内容

### 评审文档
格式：`{主题}-review.md` 或带日期的 `YYYY-MM-DD-{主题}.md`
- 不带日期表示持续更新
- 带日期表示单次会议记录

### 规划/任务文档
格式：`YYYY-MM-DD-{编号}-{主题}-{plan|tasks}.md`
- 编号用于同日多文档排序
- 主题使用 kebab-case

## 维护指引

### 新增文档时
1. 根据技能包归类到对应目录
2. 评测报告统一放入 `evals/` 并加日期前缀
3. 评审文档放入 `reviews/`，会议记录加日期
4. 长期技术规划放入 `tech-plans/`

### 归档原则
- 技能包相关文档优先按技能包分类
- 时效性文档（评测、会议）带明确日期
- 持续更新文档（架构、指南）不带日期
- 外部发布内容统一归入 `external-content/`

### 跨技能包文档
如文档涉及多个技能包：
- 主题明确偏向某一技能包：归入该技能包目录
- 仓库级规划/对比：考虑放入 `plans/` 或创建 `cross-skill/` 目录
- 通用指南/方法论：放入 `assets/guides/`

## 历史记录

- 2026-09-04：完成 docs/ 目录重组，建立按技能包+文档类型的两级分类体系
