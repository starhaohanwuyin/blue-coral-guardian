# 蓝珊 · 珊瑚认养与科普小程序（blue_coral）

广东海洋大学「珊瑚评测」项目 —— 微信小程序端。与官网共用同一套账号体系与后端 API。

## 项目概况

| 项 | 说明 |
| --- | --- |
| 类型 | 微信小程序原生工程（WXML / WXSS / JS，无 npm 构建链） |
| 页面 | 22 个（5 个 Tab 页 + 17 个子页） |
| 基础库 | 3.17.2 |
| 代码量 | 约 8800 行 / 103 个文件 |
| 当前模式 | **`USE_MOCK: true`（认养/科普等业务数据用 mock）；AI 识别、完整图鉴与团队视频需要评估服务** |

## 目录结构

```
blue_coral/
├── app.js / app.json / app.wxss / sitemap.json   应用入口与全局配置
├── project.config.json                            团队共享的工程配置（要提交）
├── project.private.config.json                    个人配置（已 gitignore，不要提交）
├── custom-tab-bar/                                自定义底部导航（5 个 Tab）
├── utils/
│   ├── config.js     全局配置：BASE_URL / USE_MOCK   ← 接后端只改这里
│   ├── api.js        统一 API 层（30+ 接口，Mock / 真实后端自动切换）
│   ├── request.js    请求封装（Bearer token、401 跳登录、文件上传）
│   ├── mock.js       本地演示数据
│   └── util.js       通用工具（toast / 剪贴板 / 环形进度 / 相册 / 登录检查）
├── pages/            22 个页面，每个页面一套 .js/.json/.wxml/.wxss
└── docs/             团队文档
```

## 本地运行

1. 安装 [微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)（稳定版）。
2. 导入项目：选择本目录，填入自己的 AppID（**没有权限时选「测试号」也能跑**）。
3. 点「编译」即可预览基础页面。**要看到完整 225 种珊瑚图鉴、全部实拍照片和团队视频，需要在电脑上再启动一次本地服务**：双击项目根目录的 `启动演示.bat`，等 8000 端口就绪。

> `project.private.config.json` 不入库，导入后由工具自动生成，属正常现象。

### 小程序端与网页版的资源差异

| 功能 | 小程序端做法 | 注意 |
| --- | --- | --- |
| 团队视频 | 读取本地服务的 `/video/team.mp4`，用原生 `<video>` 播放 | 12MB 原片不塞进 2MB 主包；服务未启动时页面会给出提示 |
| 珊瑚图鉴照片 | 213 张实拍图由服务 `/mp/assets/img/` 静态托管；12 条精选条目用包内实拍图兜底 | 服务未启动时显示 18 种离线演示图鉴，并在页面顶部提示 |
| 证书保存 | 手机保存到相册；开发者工具/PC 微信生成文件后直接预览，右键或长按另存为 | 桌面端不再依赖“相册”接口 |
| 外部文章链接 | 复制链接到微信/浏览器打开 | 小程序无法直接打开任意外部网页 |

## 接入真实后端

只改 `utils/config.js` 两处，页面代码零改动：

```js
BASE_URL: 'https://你的官网API域名',  // 须 HTTPS + 已备案，并加入小程序后台 request 合法域名
USE_MOCK: false
```

接口路径集中在 `utils/api.js` 顶部的 `URL` 常量表，按后端实际路径对齐即可。

### 真机 / 上线必读

AI 识别和团队视频由 `ai-service/scripts/serve_fusion.py` 提供。真机不能访问
`127.0.0.1`，必须部署公网 HTTPS 服务并填写：

```js
const PUBLIC_API_BASE = 'https://coralguard.cn/api'
```

同时在微信公众平台登记 `request`、`uploadFile`、`downloadFile` 合法域名。
完整步骤见 [真机与上线部署.md](docs/真机与上线部署.md)。

临时真机调试可在小程序「我的 → 右上角 ⚙」填写电脑局域网地址或临时隧道地址；
正式体验版不要在代码里保留 `127.0.0.1`。

## 团队协作

见 [docs/团队协作指南.md](docs/团队协作指南.md)。
