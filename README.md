# 蓝珊 · 珊瑚认养与科普小程序（blue_coral）

广东海洋大学「珊瑚评测」项目 —— 微信小程序端。与官网共用同一套账号体系与后端 API。

## 项目概况

| 项 | 说明 |
| --- | --- |
| 类型 | 微信小程序原生工程（WXML / WXSS / JS，无 npm 构建链） |
| 页面 | 22 个（5 个 Tab 页 + 17 个子页） |
| 基础库 | 3.17.2 |
| 代码量 | 约 8800 行 / 103 个文件 |
| 当前模式 | **`USE_MOCK: true`（本地演示模式，无需后端即可跑通全部功能）** |

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
3. 点「编译」即可预览 —— 因为 `USE_MOCK: true`，**不需要启动任何后端**。

> `project.private.config.json` 不入库，导入后由工具自动生成，属正常现象。

## 接入真实后端

只改 `utils/config.js` 两处，页面代码零改动：

```js
BASE_URL: 'https://你的官网API域名',  // 须 HTTPS + 已备案，并加入小程序后台 request 合法域名
USE_MOCK: false
```

接口路径集中在 `utils/api.js` 顶部的 `URL` 常量表，按后端实际路径对齐即可。

## 团队协作

见 [docs/团队协作指南.md](docs/团队协作指南.md)。
