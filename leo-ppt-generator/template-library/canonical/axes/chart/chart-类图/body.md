# 图表语法：类图（ClassDiagram）

**分类:** 11_图表语法

**定位:** 系统结构与数据模型 — 系统结构/数据模型,类+属性+关系。用于架构、技术方案。

## 说明

**Mermaid 类型**：`ClassDiagram`。文本描述即可渲染（mermaid 语法），是「可执行的图解」——与 07 信息图类型的「静态骨架」互补。

## 示例语法

```mermaid-example
classDiagram
    class Product {
      +String name
      +int price
    }
```

> **示例数字仅为语法演示，必须替换为 approved 真实数据**（见 `template-library/governance/authoring/index/图表样式规范.md`）。

> 图表的坐标轴/图例/配色处理沿用 `rendering 轴` 与 `template-library/governance/authoring/index/图表样式规范.md`；颜色来自 deck colors 锚点，本文件只定结构与语法。