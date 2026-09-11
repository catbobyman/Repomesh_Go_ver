# 验证期间的时钟回退

CFG-05第三轮在原墙钟`2026-09-10T10:39:00Z`写入失效Provider后，下次采样变为约`03:39:05Z`。Kubernetes TLS报`certificate is not yet valid`，也阻断测试finally恢复。证书错误不是Provider清空接口的失败证据。

主任务随后查询Windows、clock工具和两个HTTPS响应Date：[安全原始观察](../evidence/clock-discontinuity.json)。主机UTC03:39:45、LA本地09-09 20:39:45、Pacific时区相互一致；GitHub和Microsoft的响应Date也分别为03:39:59和03:40:00 UTC。Windows时间服务停止，w32tm查询返回0x80070426。没有证据指明是谁或什么程序改变了早先时钟，也不能据日志旧时间强行把主机调回10时。

旧证据保留原始时间戳，本轮目录继续按已建立的09-10 UTC批次命名。早先测试期间的单调计时及原始输入输出仍保留；跨此跳变的起止墙钟不能相减当作耗时。后续报告按实际阶段和证据文件组织，不重新排序来掩盖跳变。

上游`internal/apiserver/embedded.go`在生成本地CA及server证书时直接使用`time.Now()`为NotBefore。时间退到证书生成之前后，真实TLS校验拒绝连接。移走整个PKI会同时重新生成SA签名密钥，因此没有采用清空PKI的办法。

## 已执行的有限恢复

03:44:04 UTC，在本任务c容器内使用[标准库Go辅助程序](../scripts/control-pki-reissue.go)读取原有密钥，仅重签`ca.crt`与`apiserver.crt`，将NotBefore从10:25:45改为03:43:04，即操作时刻前一分钟。旧证书保存在同c实例的0700备份目录。subject、issuer、SPKI、扩展、serial和NotAfter均相同，其余五个PKI文件哈希不变，密钥没有导出，新证书链验证成功，见[签发结果](../evidence/control-pki-reissue-applied.json)。

supervisord没有配置管理socket，不能使用supervisorctl重启。恢复脚本核对`/proc`的精确可执行路径、PID、父PID和启动tick，仅对旧Controller PID50发SIGTERM，由现有Supervisor自动重启；新Controller为7667，其Kube子进程为7682。原Kube进程418自然退出，没有额外发送信号。容器ID和Supervisor PID不变，见[进程记录](../evidence/control-pki-process-reload.json)。没有重启Docker或其他项目服务。

随后保持TLS校验开启，真实Kubernetes CR读回成功，见[恢复后快照](../evidence/control-manager-projection-state-20260910T034411Z.json)。Provider测试的首次恢复CLI参数有误；finally中真实REST于03:44:20清空失效绑定并保留chat，正确CLI随后只能证明重复清空。最终配置及运行进程读回以[Manager实测](manager-config-live.md)为准，不把基础证书恢复冒充全部模型路径通过。

此次修复没有调整系统时间、关闭TLS校验、导出密钥、改上游源码或清空数据库／卷。它恢复了自有测试实例，不能证明导致时钟变化的根因已消除。
