# 用户素材库 Schema（library/，R-04）

> 加载阶段：`execute` 内用户明确入库/检索素材时读取；不得在入口 / Route 判断 / advise 阶段读取。
> 来源：专家5 E5-01（Beav 目录式素材库 + catalog 登记，借鉴机制不取码）。

库根约定 `${LEO_PPT_HOME}/library/`：`assets/<sha12>-<原名>` 为素材本体（sha256 前
12 位 + 安全化原文件名，内容寻址）；`catalog.json` 为登记清单（canonical 键序写盘，
entries 按 sha256 排序）。条目字段：`sha256`（64 hex，重复 add 幂等键）、`asset_path`
（相对库根 POSIX 路径）、`original_name`（原文件名）、`source`（来源 URL 或路径，
用户自报；敏感扫描命中拒入库）、`added_at`（ISO8601 UTC）、`tags`（排序去重，可含
空格）、`note`。

**数据边界（PRD R-04 原文）**：入库属用户主动动作，存储素材本体并以 sha256 + 来源
元数据 + 标签登记；库仅存本地、随 LEO_PPT_HOME 数据目录管理（不入技能同步面）、
提供整库导出（`export-manifest`）与清理入口（`remove` / `remove --all`）；母版视觉行
引用库内素材时自动携带出处，sources-manifest 从库登记派生。与交付档案的边界：
**档案只存偏好字段，素材库存用户主动入库的素材本体**。

与 sources-manifest 的派生关系：`library_catalog.py export-manifest` 把每条登记映射为
`source_class=user-material / tier=引用 / backend=user` 的 visual 条目（schema 见
`sources-manifest-schema.md`）；page_id 占位、source_ref 为库内绝对路径等差异在命令
stderr 打 WARN，接入真实 run 前按 slide_jobs.json 页集合改写。库外编造链接仍被
`check_sources_manifest.py --strict` 拒绝（素材库不放松 strict 门）。

用法（技能目录内执行，exit 0 成功含幂等 WARN / 2 输入错误）：
`library_catalog.py --root <library/> add <file> [--tags a,b] [--source URL] [--note …]`、
`list [--tag]`、`remove <sha12>|--all`、`export-manifest`；数据通道登记见
`data-sources.md`。
