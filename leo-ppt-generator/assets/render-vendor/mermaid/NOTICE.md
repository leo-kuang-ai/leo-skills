# render-vendor/mermaid

D2 图表确定性渲染的浏览器端运行时，vendored 本地单文件（不走 CDN，
离线确定）。

- 文件：`mermaid.min.js`
- 上游：mermaid-js/mermaid，npm `mermaid@11.17.2` 官方 tarball
  （`dist/mermaid.min.js`，sha256
  `581ed7d74bd9048d0e3a91363927d72ef22942d7722546b27f7cc29e35390eb8`）
- 许可：MIT（mermaid 本体；bundle 内嵌依赖各自的 MIT/BSD 许可，见
  上游仓库 LICENSE 文件）
- 版本 pin：包根 `vendor-lock.json` `files` 条目锁 sha256；升级 = 换文件
  + 更新 lock + 重跑 `render chart` 确定性断言（同 SVG 两次 sha256 相等）。
