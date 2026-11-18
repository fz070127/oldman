# 银铃守护 · Web 管理端（frontend）

独居老人跌倒行为智能检测预警系统 —— 管理员 / 社区管理员 / 网格员使用的 Web 管理端。

## 技术栈

Vue 3.4 (script setup + TS) · Vite 5 · Element Plus 2 · Pinia · Vue Router 4 · Axios · ECharts 5 · dayjs
· vite-plugin-mock · unplugin-auto-import · unplugin-vue-components · ESLint + Prettier · SCSS

## 快速开始

```bash
# Node >= 18
npm install
npm run dev        # http://localhost:5173
npm run build      # 类型检查 + 生产构建
npm run lint       # ESLint 检查（0 warning）
npm run format     # Prettier 格式化
```

## 环境变量

| 变量 | 说明 | development | production |
|---|---|---|---|
| `VITE_APP_TITLE` | 页面标题后缀 | 银铃守护 | 银铃守护 |
| `VITE_API_BASE` | 接口前缀（契约基础路径） | `/api/v1` | `/api/v1` |
| `VITE_USE_MOCK` | 是否启用前端 mock | `true` | `false` |

- dev 下 `/api` 由 vite proxy 转发到 `http://localhost:8000`（`VITE_USE_MOCK=false` 时生效）。
- Mock 账号：`admin / 123456`、`guardian01 / 123456`、`family01 / 123456`。

## 目录结构

```
src/
├── api/          接口函数；request.ts 为唯一 HTTP 出口（解包 / 刷新 token / 错误提示）
├── types/        TS 类型（common.ts 通用响应 / 分页；与接口契约一一对应）
├── router/       路由表 index.ts + 守卫 guard.ts
├── stores/       Pinia：user（登录态）/ app（UI 状态）/ tabs（多标签）
├── layouts/      DefaultLayout + Sidebar / Navbar / TabsBar
├── components/   通用组件（PageContainer 等）
├── views/        页面
├── hooks/        组合式函数
├── directives/   全局指令
├── utils/        工具（storage 等）
├── styles/       variables.scss / element-override.scss / index.scss
├── mock/         vite-plugin-mock 接口（_ 开头为工具文件）
└── i18n/         Element Plus 语言包 / dayjs 语言
```

## 约定

- 接口字段以《接口契约 v1.0》为唯一事实来源，JSON 字段一律 camelCase。
- `request<T>()` 返回的是契约中的 `data` 本身；业务错误已在拦截器统一 `ElMessage.error`，页面无需重复提示。
- localStorage key 统一带 `yl_` 前缀：`yl_token`、`yl_refresh_token`、`yl_user_info`、`yl_sidebar_collapsed`。

## 调试技巧

跳过登录直接进入布局：

```js
// 浏览器控制台
localStorage.setItem('yl_token', 'fake-token')
location.href = '/'
```
