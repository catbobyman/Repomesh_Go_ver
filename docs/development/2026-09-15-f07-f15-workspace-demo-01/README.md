# 2026-09-15：F07—F15 假数据工作区演示

按用户授权，把会话 / Issue / 交付原型收成 React 页面，并让页面只通过 `/api` 读写内存假数据。设计说明见 [F07—F15 演示基线](../../current/f07-f15-workspace-browser-demo.md)。

## 做了什么

- 从 F07—F15 原型抽出元素，映射到已采用浏览器契约；为会话页头、只读 DAG、交付页签补只读扩展。
- `web/src/workspace/`：解析器、client、内存 mock、Vite 中间件、工作区 UI。
- 入口 `/demo/workspace`，不走 GitHub 登录。
- 前端测试覆盖列表、创建幂等、消息澄清、分析、CSRF／幂等键。

## 不是什么

- 不是 B07—B11 产品实现，没有 Go 路由、迁移或真实 Manager／房间／Python 分析。
- 没有改 `docs/current/api-design.md` 的 `/api/v1` 方案。
- SSE、F11 更正、F13 换图写接口、F14 交付动作未做。可进房间与只读原生 DAG 见后续 [房间／DAG 记录](../2026-09-15-f07-f15-workspace-rooms-dag-01/README.md)。

## 如何打开

```bash
npm --prefix web run dev
```

浏览器打开 `http://127.0.0.1:5173/demo/workspace`。顶栏场景可切会话、澄清、列表、创建、概览、DAG、交付。开发者工具 Network 应看到 `/api/projects/...` 与 `/api/issues/...`。
