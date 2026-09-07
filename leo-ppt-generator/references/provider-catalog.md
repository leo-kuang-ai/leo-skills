# Provider 渠道目录（OpenAI 兼容图片渠道）

> 数据源：`runtime/src/leo_ppt_generator/config/providers.yaml`（checked-in，本文件是
> 其用户视角的引导说明；两者不一致以 yaml 为准，新增渠道两处同步）。

## 快速配置（任选一个渠道）

**本地控制台（推荐）**：`leo-ppt config ui` 打开浏览器控制台（仅监听 127.0.0.1，链接
携带一次性 token）——上半区治理已配置渠道（凭据/验证徽标、启用开关、优先级排序、
设为当前/修改/删除；自动模式下可直接编辑各渠道**权重**——权重小的优先被自动选用，
值域 1-1000，也可用 ↑↓ 一键重排），下半区发现可添加渠道（目录卡片直达取 key 页面，推荐渠道排首），
配置向导内完成模型/端点与凭据：网页一次性录入（掩码输入，直写系统钥匙串，页面与
接口零回显）、终端安全录入（页面触发、终端 getpass，无 TTY 自动隐藏）、环境变量引用
或保留现有凭据；CLI 命令等价路径在向导内始终可复制。提示：更新技能/runtime 后需让
受管 runtime 重新 ensure（安装态 CLI 起服才包含最新页面资产；页面报
`config_ui_asset_missing` 即旧运行时未刷新）。

**交互式向导**：`leo-ppt config` → 添加备用服务 / 修改当前服务，菜单会列出
全部渠道，条目布局为「`渠道名 渠道（取 key 页面 URL）- 使用渠道名官方图片服务`」，
选中后按引导输入 API Key；端点与模型直接回车即用目录默认值，凭据写入 OS
keychain（`leo-ppt-generator/<渠道 id>` 槽位）。

**命令行**：

```sh
# 1) 导出对应渠道的 API Key 环境变量（见下表）
export ZHIPU_API_KEY=sk-...        # 以 zhipu 为例

# 2) 建立后端合同（渠道端点与默认模型来自目录，无需 --base-url）
leo-ppt backend create --provider zhipu --mode generate --output ./backend.json
leo-ppt backend validate ./backend.json

# 3) setup 报告会披露渠道引导信息（官网/取 key/环境变量/模型清单）
leo-ppt setup --route generate --host-imagegen unavailable --json
```

可选：把模型偏好持久化进配置（省略时用渠道默认模型与默认端点）：

```sh
leo-ppt provider configure --provider zhipu --model cogview-3-flash
```

## 渠道一览

| 渠道 id | 平台 | 官网 / 控制台 | 取 API Key | 环境变量 | 默认模型 |
| --- | --- | --- | --- | --- | --- |
| `qianxing`（推荐） | 乾行AI画廊（new-api 中转） | <https://fast.qianxing.us.ci/> | [令牌页](https://fast.qianxing.us.ci/token) | `QIANXING_API_KEY` | `gpt-image-1` |
| `zhipu` | 智谱 AI 开放平台 | <https://open.bigmodel.cn/> | [API Keys 页](https://open.bigmodel.cn/usercenter/apikeys) | `ZHIPU_API_KEY` | `cogview-4` |
| `dashscope` | 阿里云百炼 | <https://bailian.console.aliyun.com/> | [API-KEY 页](https://bailian.console.aliyun.com/?apiKey=1) | `DASHSCOPE_API_KEY` | `qwen-image` |
| `ark` | 火山方舟（即梦 Seedream） | <https://www.volcengine.com/product/ark> | [方舟 API Key](https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey) | `ARK_API_KEY` | `doubao-seedream-4-0-250828` |
| `qianfan` | 百度千帆（文心一格） | <https://cloud.baidu.com/product/qianfan> | [IAM API Key](https://console.bce.baidu.com/iam/#/iam/apikey/list) | `QIANFAN_API_KEY` | `ernie-vig-v2` |
| `hunyuan` | 腾讯混元（TokenHub） | <https://cloud.tencent.com/product/hunyuan> | [TokenHub apikey](https://console.cloud.tencent.com/tokenhub) | `HUNYUAN_API_KEY` | `hy-image-v3.0` |
| `modelscope` | 魔搭 ModelScope | <https://modelscope.cn/> | [SDK Token](https://modelscope.cn/my/keys) | `MODELSCOPE_API_TOKEN` | `Qwen/Qwen-Image` |

乾行AI是目录中唯一 `featured` 渠道：向导菜单排第一位并标注（推荐），首配引导直接指向它——只需输入 API Key 与模型，端点自动用默认。

所有渠道走同一条 OpenAI 兼容执行面：`endpoint_origin + api_path` 派生 base URL
（不会误拼 `/v1`），凭据从上表环境变量（或 keychain）解析后注入受控执行环境；
只返回临时 URL 的渠道由 url 回退补丁（`patches/0008`）自动下载转存。

## 模型与注意事项

- **qianxing**：new-api 系中转；登录后在「令牌」页建 key，可用图片模型以站内「模型价格」页为准（gpt-image 系列及站内上架的聚合模型）。
- **zhipu**：`glm-image` / `cogview-4-250304` / `cogview-4` / `cogview-3-flash`。
  仅文生图；响应只含 30 天临时 URL。cogview 尺寸 512–2048 且 16 的倍数；
  glm-image 需 1024–2048 且 32 的倍数、仅 `hd`。个人测试建议 `cogview-3-flash`
  （有免费额度）。
- **dashscope**：`qwen-image` / `qwen-image-edit`，中文文字渲染强。wanx（通义万相）
  与可灵 kling 走百炼原生**异步任务**接口，不在本同步通道内（见下"暂缓项"）。
- **ark**：`doubao-seedream-4-0-250828` / `doubao-seededit-3-0-i2i`（图生图）。
  `response_format` 支持 `url`（默认）/`b64_json`；中文提示词与人像质感强。
- **qianfan**：`ernie-vig-v2`；可用模型以千帆控制台模型列表为准。
- **hunyuan**：`hy-image-v3.0`（TokenHub 同步通道，API Key 鉴权，绕开 TC3 签名）。
  旧控制台 TC3 签名与异步接口不在本通道内。
- **modelscope**：模型名用仓库全路径（如 `Qwen/Qwen-Image`），凭据为 SDK Token；
  有每日免费额度，适合测试。

## 能力边界与暂缓项

- v1 渠道能力固定为 **generate-only**（同步文生图）；`edit` / `mask` /
  `reference` 路线仍走 builtin-imagegen / openai / atlascloud。
- 暂缓（需原生异步任务适配器，不在本目录承诺内）：wanx（通义万相）t2i 异步、
  可灵 kling、腾讯混元旧控制台异步、百度文心一格企业版异步接口。渠道内如后续
  上线同步兼容端点，加目录条目即可接入。
- 尺寸：生成管线默认尺寸（1024x1024 / 1536x1024 / 1024x1536）在全部渠道合法；
  其他自定义尺寸以各渠道文档为准，越界会得到清晰的 provider 报错。

## 新增渠道（维护者）

1. `providers.yaml` 加一条（id / portal / key_page / credential_environment /
   endpoint_origin / api_path / default_model / models / notes），加载器 fail-closed
   校验（id 冲突、origin-only 端点、默认模型必须在 models 内等）。
2. 同步本文件"渠道一览 / 模型与注意事项"。
3. 同步 `runtime/src/leo_ppt_generator/schemas/` 下 4 个 schema 的 provider enum
   （`tests/test_channel_catalog.py` 有一致性看护）。
4. 不改任何 Python 代码；`tests/test_channel_catalog.py` 的解耦测试保证通用模块
   不出现渠道名硬编码。
