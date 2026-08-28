# Upstream 来源与同步

本目录是 vendored 拷贝，不是独立开发分支；对它的功能迭代应先在上游完成，再同步回来。

- 上游仓库：https://github.com/SpaceZephyr/creator-buddy
- 集成版本：`edf46c567ff54b72ee2157d06f3a02dbd67aaa9c`（2026-08-28，整目录拷贝，排除 `.git`）
- 集成方式：保持上游内部结构原样（根目录总控 `SKILL.md` + `gzh-Skills/`、`xhs-Skills/`、`video-Skills/` 三组共 32 个子技能），不重命名、不拆分、不改上游文件。

## 本地新增文件（上游没有，同步时保留）

- `.claude-plugin/plugin.json` — Claude Code 插件注册；`skills: ["./"]` 只暴露根目录总控 Skill，32 个子技能经总控路由（按需读取其 SKILL.md 并运行脚本），避免全部载入撑大技能面。
- `LICENSE` — 上游 README 声明 MIT 但未附许可证文件，此处补齐（版权行按 MIT 再分发要求保留，不可移除）。
- `UPSTREAM.md` — 本文件。

## 本地改写的上游文件（owner 授权的本土化，同步时排除或重放改写）

- `README.md`（根）— 移除原作者徽章、联系方式与上游安装指引；安装方式改指本仓库（leo-skills marketplace）；致谢小节移除原作者自引条目，其余第三方方法论致谢保留。
- `gzh-Skills/README.md` — 移除含原作者仓库链接的致谢小节。
- `xhs-Skills/README.md` — 安装小节改指本仓库。
- `gzh-Skills/references/my-voice.md` — 原作者个人文风档案（含笔名、成稿样本、主题分布）转为待填模板，规则骨架保留、个人样本全部移除。如需参考原档案，从本地源仓库找回。
- `gzh-Skills/xhs-hotnotes/README.md`、`README.en.md`、`SKILL.md` — 移除 redfox.hk 链接上的 skillhub 渠道追踪参数（`?source=skillhub`），链接本身不变。

## 同步方式

上游更新后，从本地源整目录覆盖（保护三个本地新增文件）：

```sh
rsync -a --delete --exclude='.git' \
  --exclude='/.claude-plugin' --exclude='/LICENSE' --exclude='/UPSTREAM.md' \
  --exclude='/README.md' \
  --exclude='/gzh-Skills/README.md' \
  --exclude='/xhs-Skills/README.md' \
  --exclude='/gzh-Skills/references/my-voice.md' \
  /path/to/creator-buddy/ ./creator-buddy/
```

覆盖后 `diff -rq --exclude=.git` 校验、更新本文件的集成版本 hash，并按仓库纪律补 `CHANGELOG.md`。若未来想要保留合并历史的同步通道，可改用 `git subtree`（`git subtree add --prefix=creator-buddy <repo> main --squash`），届时需先处理本仓库工作区的未提交改动。

## 运行约定

- 总控 `SKILL.md` 与子技能中的相对路径命令（`python3 gzh-Skills/...`、`node gzh-Skills/...`）一律从本目录（`creator-buddy/`）执行。
- `gzh-Skills/global-content-search` 无第三方 npm 依赖，无需 `npm install`。
- 平台凭据（`GUAIKEI_API_TOKEN`、`LABNANA_API_KEY`、`DOUYIN_COMMAND` 等）走本地环境变量，绝不入库；目录内 `.gitignore`（继承自上游）已覆盖 `.env`、`reports/` 等产物。

## 已知差异（记录，不修改上游文件）

- 目录名为 `gzh-Skills/` 等驼峰式，不符合本仓库 lowercase-kebab-case 顶层约定 —— 在 vendored 边界内豁免（见根 `AGENTS.md`）。
- 内部存在跨组引用（如 `space-gzh-cover` 引用 `xhs-Skills/space-xhs-image` 的视觉系统、`gzh-Skills/references/my-voice.md` 共享文风档案、`fetch_xhs_hot_articles.py` 在两组各有一份）—— 一并豁免于"兄弟技能不建立运行时依赖"约束。
- 上游评测为 skillhub `evals/evals.json` 格式，未接入本仓库 skill-up `evals/eval.yaml` 门禁。
- `video-Skills/space-video-edit/references/` 下有中文文件名，同样按 vendored 边界豁免。
