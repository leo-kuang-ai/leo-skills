# 风格扩展模板（style-brief-v2）

本模板用于新增或修订可被推荐、组合和渲染的风格资产。活动真值是
[`canonical/styles/`](../../../canonical/styles/) 下每个目录的 `brief.json`；
[`catalog/current.json`](../../../catalog/current.json) 只保存由 canonical 重建的索引。
退役树只用于迁移和 provenance，不能作为新增资产目录或执行期查询入口。

## 先选扩展范围

- **内置风格**：维护者在仓库中新增 `canonical/styles/<slug>/brief.json`，`asset_id`
  必须是 `builtin:style:<slug>`。
- **用户风格**：通过 `leo-ppt style save <name> --content-file <file> --home <dir>`
  写入 `${LEO_PPT_HOME}/template-library/canonical/styles/<slug>/brief.json`，来源为
  `user:style:<slug>`，默认 `lifecycle=draft`，不会改写内置 catalog。
- **参考资料**：没有完整 brief 或未完成内容审阅的材料放在 reference/evidence
  区，不能伪装成 builtin 或直接进入推荐资格。

## 填写 brief.json

结构契约是 [`style-brief-v2.schema.json`](../../schemas/style-brief-v2.schema.json)。
占位符必须全部替换，未知字段不要加入 brief；缺少事实时写入
`adaptation_gaps`，不要用猜测值填满字段。

```json
{
  "schema_version": 2,
  "entity": "style-brief",
  "asset_id": "builtin:style:<slug>",
  "name": "<中文名称>",
  "aliases": ["<口语别名>"],
  "variant_of": null,
  "lifecycle": "draft",
  "source": {
    "origin": "authored",
    "upstream": "<来源或本库自创>",
    "license_note": "<许可与再分发边界>"
  },
  "taxonomy": {
    "families": ["<视觉家族>"],
    "industries": ["<行业，可为空>"],
    "scenarios": ["<适用场景>"]
  },
  "recommendation_features": {
    "audience_conservatism": "balanced",
    "formality": 0.7,
    "density": "balanced",
    "environments": ["desktop-review"],
    "counter_indications": ["<明确不适用条件>"]
  },
  "visual_language": {
    "direction": "<至少 8 个字符的可执行视觉方向>",
    "features": ["<可观察特征 1>", "<可观察特征 2>"],
    "composition_discipline": ["<位置、比例、层级和留白规则>"],
    "continuity": {
      "cover": "<封面角色>",
      "content": "<正文角色>",
      "data": "<数据角色>",
      "closing": "<结尾角色>"
    }
  },
  "constraints": {
    "negative": ["<针对本风格真实风险>"],
    "hard_rule_ids": ["<governance rule id，可为空>"]
  },
  "bindings": {
    "theme_default": "builtin:theme:<slug>",
    "modes_supported": ["light"],
    "layout_routes": [
      {
        "page_type": "content",
        "preferred": ["builtin:layout:<slug>"],
        "discouraged": []
      }
    ],
    "capacity_factor": {"text": 1.0}
  },
  "adaptation_gaps": ["<尚未验证的能力，可为空>"],
  "content_review": {
    "reviewed": false,
    "disposition": "draft",
    "reviewer_note": "<审阅证据或待办>"
  }
}
```

## 资产规则

1. `asset_id`、目录 slug 和实体类型必须一致，不能使用 `references/styles` 的旧路径、
   generated 快照或另一个实体的 ID。
2. `name` 是展示名，`aliases` 只收录已确认的口语命中；别名命中多个实体时，推荐器必须
   返回候选并要求上下文消歧，不能静默取第一项。
3. `taxonomy` 描述适用语境，`visual_language` 描述可观察的形状、排印、材质和构图。
   品牌色、字体文件和几何由 theme、brand、font、layout 实体拥有；不要把治理统计或
   验证状态塞进逐页 prompt。
4. `bindings.layout_routes` 只能引用 registry 中存在的 `builtin:layout:*`；版式容量以
   对应 `layout.json` 为准，风格的 `capacity_factor` 只能作为折减视图。
5. `lifecycle=active` 需要完整特征、默认主题、适用性和内容审阅证据；没有视觉证据时
   保持 `draft`，不能把 schema 通过写成视觉通过。
6. 来源、许可、变体归属和 `adaptation_gaps` 必须可追溯。共享色板或语义相同的变体优先
   使用 `variant_of`，不要复制成新的顶层风格。

## 验证与发布

在技能目录执行：

```sh
python3 -m json.tool template-library/canonical/styles/<slug>/brief.json
python3 scripts/lint_layout_grid.py
runtime/.venv/bin/python scripts/capability_manifest.py --template-library --library-check
```

维护者确认 brief、主题和绑定均已落盘后，才运行：

```sh
runtime/.venv/bin/python scripts/capability_manifest.py \
  --template-library --library-publish
runtime/.venv/bin/python scripts/capability_manifest.py \
  --template-library --library-check
```

发布由 `catalog/generations/<generation>/registry.json` 加 `catalog/current.json` 构成，
不得手工编辑 registry 或 current。若检查返回 `registry_stale`，先重新发布或恢复 canonical
输入；执行期必须 fail closed，不能返回部分 ready 列表。

## 内容与视觉门

- 用 `leo-ppt style list --summary --filter <名称或别名>` 检查可查询摘要，用
  `leo-ppt style load <名称> --summary` 检查实际解析到的 `source/path/asset_id/revision`。
- 组合前完成 layout capacity 预检；有数据才使用数据版式，不因风格装饰编造数值。
- 视觉验证需留下 evidence 包并标明运行环境、主题、页面角色和结果；没有 evidence 时只
  报告 schema/索引状态，不宣称整稿可交付。
