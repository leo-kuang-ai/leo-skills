# render-fonts 离线字体包

本目录是 render lane 的确定性字体供给源（渲染器本地 HTTP 服务以
`/leo-fonts/` 前缀供给模板 `@font-face`；resvg 栅格化以 `font_dirs`
显式加载，`loadSystemFonts=false`）。**缺字时 WARN 并回退
defaultFontFamily，不静默换系统字体**（系统字体跨机器非确定）。

## 内容与许可

| 文件 | 来源 | 许可 |
| --- | --- | --- |
| `NotoSansSC-Regular.otf` | notofonts/noto-cjk `Sans/SubsetOTF/SC/`（sha256 `faa6c9df…706d5ea9`） | OFL-1.1 |
| `NotoSansSC-Bold.otf` | 同上（sha256 `c6cb5a93…764767c0`） | OFL-1.1 |
| `LICENSE-OFL.txt` | 上游 LICENSE 副本 | — |

OFL-1.1 既定条款：字体不得单独以收费方式再分发、RESERVED 名称
（"Noto"）用于衍生字体时须重命名、衍生字体须以同许可发布并附
免责声明。本仓以原样二进制随包分发并在包根 `NOTICE` 登记。

## 风格包字体（β 团队接口）

deck 专用字体由风格包提供目录路径，经
`LEO_PPT_RENDER_FONT_DIRS`（路径分隔符分隔）或 `render/raster.py`
的 `extra_font_dirs` 进入同一显式加载链；不进本目录混装。
