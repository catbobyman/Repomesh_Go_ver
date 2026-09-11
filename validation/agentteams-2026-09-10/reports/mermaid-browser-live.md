# 共享 Mermaid 渲染器的真实浏览器验证

2026-09-10。固定AgentTeams `517caff9280242a00a4d4c06365352b9e41659c6`，Mermaid `11.17.2`，Playwright CLI启动的隔离Chromium。**18个输入中14个可解析并产生预期节点／边数量，4个合法字符组成的任务ID触发解析失败。** 官方Go字符串测试通过不能证明任意Task ID都可被Mermaid解析。

## 方法与来源

在隔离构建副本中新建[调用辅助程序](../scripts/mermaid-renderer-main.go)，直接调用未修改的`internal/workflow.RenderMermaid`，输出各输入Snapshot及实际生成文本。[指纹](../evidence/mermaid-renderer-provenance.json)确认所用库文件与新upstream完全相同；辅助程序在Controller镜像构建完成后加入测试副本，不属于产品实现或上游变更。

使用本轮独立`runtime/mermaid-check`安装指定Mermaid版本，安装关闭npm生命周期脚本，依赖锁保存在[package lock](../evidence/mermaid-package-lock.json)。[本地验证页](../scripts/mermaid-browser.html)通过真实`mermaid.parse`及`mermaid.render`执行，插入返回SVG，再检查DOM节点和边数量；没有模拟parser或浏览器。使用strict安全模式。只服务该目录的[本地HTTP程序](../scripts/serve-mermaid-check.py)绑定127.0.0.1:48444，不托管private或其他项目文件。

## 结果

| 输入 | 结果 |
|---|---|
| 两节点一条边、completed与ready样式 | 解析和渲染成功；2节点、1边，[截图](../output/playwright/mermaid-baseline.png) |
| 空图 | 成功；0节点、0边 |
| `a.b`与`a_b`归一化碰撞 | 成功；仍为2节点、1边 |
| 双引号、换行、末尾反斜杠、类似边的文字、括号、控制字符、中文、混合引号换行共8个标题 | 均成功；每例1节点、0边，没有观测到额外结构 |
| Task ID `direction`、`1`、`-` | 均成功；每例1节点 |
| Task ID `end`、`subgraph`、`classDef`、`graph` | **全部失败**；Mermaid把原样输出的ID解释为关键字，[end错误截图](../output/playwright/mermaid-reserved-end.png) |

例如实际共享函数输出包含`end["ordinary title: pending"]`，Mermaid11.17.2在第二行报告`got 'end'`。字符清理只限制`[A-Za-z0-9_-]`并处理碰撞，没有规避Mermaid关键字。这与源码“任何任务ID均有效”的说明不一致。未修改上游以抹去失败。

[原始输入和生成结果](../evidence/mermaid-library-cases.json)、[完整浏览器结果](../evidence/mermaid-browser-result.json)包括每个失败的异常及成功SVG；结果页显示14通过／4失败。唯一浏览器console资源错误是本地favicon.ico的404，与Mermaid解析失败分别记录。

## 验证边界

以上是实际共享Go函数到真实Mermaid浏览器的证据；不是RepoMesh页面实现验收，也不是所有Mermaid版本、主题、安全配置或任意文本输入的穷尽证明。成功的八种标题样本只能证明这些具体样本，没有证明所有用户输入都安全。

## 实际 Controller HTTP 字节对照

随后在全新c实例运行[真实接口回归](controller-api-live.md)，独立Project包含Task ID `end`。workflow JSON与单Task检查均200，`format=mermaid`同样200，返回411字节。原始文件为[API Mermaid正文](../evidence/controller-delta-live-d33b63db78-reserved-end.mmd)，SHA-256为`026597812b4c8205cf7070ac2c2ef812621344a8c4da1d60b97ca488b090f0cc`。

不改正文，将这些确切字节作为第二轮浏览器的唯一输入。结果仍是第二行`got 'end'`解析失败，0通过／1失败；[输入及来源哈希](../evidence/mermaid-api-cases.json)、[浏览器原始结果](../evidence/mermaid-api-browser-result.json)、[错误截图](../output/playwright/mermaid-api-end.png)。这补齐实际Controller→返回文本→真实Mermaid解析的失败链路，不再只是函数级推断。

最小实现修复需要避免把可用的任务ID直接放入Mermaid关键字位置，并保持节点／边映射一致。此轮仅验证和记录，没有修改上游渲染器、业务Task ID或任务状态。
