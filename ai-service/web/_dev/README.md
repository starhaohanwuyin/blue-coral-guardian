# 网页版调试探针（_dev）

这些是**开发/回归用**的小页面，不参与正常运行，也不会被用户看到（`/` 只会加载 `index.html`）。
用法：服务起来后直接开对应 URL，例如 `http://127.0.0.1:8000/_dev/_overlap_probe_all.html`。

| 探针 | 用途 |
|---|---|
| `_overlap_probe.html` / `_overlap_probe_all.html` | **布局重叠扫描**：量元素包围盒，报"图压文/文压文" |
| `_img_probe.html` / `_imgcheck.html` | 图片加载与**裂图扫描**（逐页） |
| `_rect_probe.html` / `_style_probe.html` | 单元素几何与计算样式（定位/配色排查） |
| `_i18n_scope_probe.html` / `_i18n_steps.html` / `_i18n_dbg.html` | **页面作用域词条**验证（曾出现首页显示科普页品牌名） |
| `_runtime_ver.html` | 运行时能力自检（storage 前缀、route、getCurrentPages 等） |
| `_api_resolve_probe.html` / `_apicall_probe.html` | 服务地址探测与 API 返回形状 |
| `_recognize_probe.html` | **端到端**走小程序 `api.recognize`（是否降级成演示数据） |
| `_errcheck.html` | 单页 JS 错误与渲染字数 |
| `_shape2.html` | 跨域部署（静态站 + 独立服务）下地址解析 |
| `_drive_probe.html` | 驱动页面到指定状态后截图（README 演示图就是这么拍的） |
| `_shot_driver.html` | 全屏 iframe 截图驱动（含自动跑一次真实识别） |
| `_header_probe.html` | 顶栏 DOM 与尺寸（换行/串页排查） |

当前共 18 个探针。

> 注意：临时用的一次性探针（例如带假 Token/测试端口的那种）用完即删，不要提交进仓库。
