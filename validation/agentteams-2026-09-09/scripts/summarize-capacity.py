"""Summarize observed samples without extrapolating maximum supported projects."""
import collections,json,re,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def mib(s):
    n,u=re.match(r'([0-9.]+)\s*([A-Za-z]+)',s.strip()).groups()
    return float(n)*{'B':1/2**20,'KiB':1/1024,'MiB':1,'GiB':1024,'TiB':1024**2,'kB':1000/2**20,'MB':1000**2/2**20,'GB':1000**3/2**20}[u]
phases=[]
for p in sorted((ROOT/'evidence').glob('capacity-*.json')):
    d=json.loads(p.read_text(encoding='utf-8'))
    if 'samples' not in d:continue
    rows=collections.defaultdict(list)
    totals=[]
    for sample in d['samples']:
        total=0
        for c in sample['containers']:
            row={'cpu':float(c['CPUPerc'].strip('%')),'mem_mib':mib(c['MemUsage'].split('/')[0]),'pids':int(c['PIDs'])}
            rows[c['Name']].append(row);total+=row['mem_mib']
        totals.append(total)
    phases.append({'file':p.name,'samples':len(d['samples']),'start':d['started_at'],'end':d.get('finished_at'),
        'aggregate_mem_max_mib':round(max(totals,default=0),2),
        'containers':[{'name':name,'samples':len(vals),'cpu_mean_pct':round(statistics.mean(v['cpu'] for v in vals),2),
            'cpu_max_pct':max(v['cpu'] for v in vals),'mem_min_mib':round(min(v['mem_mib'] for v in vals),2),
            'mem_max_mib':round(max(v['mem_mib'] for v in vals),2),'pids_max':max(v['pids'] for v in vals)} for name,vals in sorted(rows.items())]})
out={'phases':phases,'limitations':['5s sleeps plus Docker sampling overhead; peaks between samples may be missed',
    'CPU percent is Docker per-core scale, not a 0..100 host utilization fraction',
    'Aggregate container memory is summed container accounting, not measured unique physical memory or host headroom',
    'Startup phases include documented fixture retries; they are not clean deploy benchmarks',
    'No maximum load, OOM, fairness, or atomic global scheduler measurement']}
(ROOT/'evidence/capacity-summary.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
lines=['# 单机资源与恢复实测','',
    '2026-09-09。本机 Docker Engine 28.0.4 / WSL2，16 个可见 CPU、15.27 GiB 可见内存，cgroup v1。仅测本轮隔离容器；宿主还运行其他项目，未停止它们。以下是低负载验证样本，不能据此承诺最大项目或 Worker 数。','',
    '## 采样过程','',
    '[原始汇总](../evidence/capacity-summary.json)、[采样器](../scripts/sample-capacity.py)、[汇总脚本](../scripts/summarize-capacity.py)。每次采集 docker stats 后等待 5 秒，实际间隔含约 2–3 秒命令耗时，可能错过间隔内峰值。CPU 的 100% 约为一核，不是整个 16 核宿主的 100%。内存是 Docker 容器记账值；求和不代表唯一物理内存或整机剩余量。','']
for phase in phases:
    lines+=['### '+phase['file'],'',f"{phase['samples']} 组；{phase['start']} 至 {phase['end']}。采样内最大容器内存合计 {phase['aggregate_mem_max_mib']:.1f} MiB。",'',
        '| 容器 | 样本 | CPU 均值 / 样本最大 | 内存范围 MiB | 最大 PID 数 |','|---|---:|---:|---:|---:|']
    for r in phase['containers']:
        lines.append(f"| {r['name']} | {r['samples']} | {r['cpu_mean_pct']:.2f}% / {r['cpu_max_pct']:.2f}% | {r['mem_min_mib']:.1f}–{r['mem_max_mib']:.1f} | {r['pids_max']} |")
    lines+=['']
lines+=['## 响应与恢复','',
    '- 两实例基础设施重启至 API 可用约 12.813 / 13.328 秒；该轮未启用 runtime，不能当作完整实例恢复成本。',
    '- [双实例六个模型请求](twin-model-live.md)：观察延迟 3.312–5.578 秒；含 HTTP 与轮询，不是首 token 延迟。四个 Team 请求并发期间 24 个有效 healthz 样本全 200；Manager 并发阶段采样误用路径的限制已单独保留。',
    '- [实际 runtime 恢复](runtime-recovery-live.md)：Worker 14.578 秒、Manager 31.937 秒后回复停机期间保存的 marker；346 个 healthz 样本全 200，b 实例未重启。Worker 55 条 backlog 的完整恢复失败，不能只用最后响应时间认定消息恢复完成。',
    '- Team 从首次尝试到就绪的 160.688 秒包含 Human CR 夹具错误和修正；不是干净启动性能。',
    '', '## 磁盘和模型用量','',
    '[资源清单](../evidence/resource-inventory.json)记录采样时刻、镜像 ID、各容器可写层、挂载、du 和原生 token_usage.json。镜像逻辑大小包含共享层，不相加冒充物理磁盘占用；Controller du 包含服务数据，没有把整个 Docker 虚拟磁盘分摊为项目成本。',
    '', '原生 token 计数是相应 runtime 累积自报值，包含该环境已有验证调用；不是供应商账单，也不等同当次 marker 的增量。缺失字段或读取失败标为不可用，不记作零费用。请求 deepseek-chat 的直接 provider 冒烟返回模型 deepseek-v4-flash；未据此假定每次 runtime 调用的供应商映射或计价。',
    '', '## 容量结论与限制','',
    '观察范围内两套 Manager／Leader／Worker 可以共同运行并完成少量真实请求，控制面持续响应。但 CPU／内存请求未下发为实际容器限额，原生资源单元也没有 RepoMesh 的全局配额事务。增加 OOM 或长时间压力无法修复这项已确认缺口，本轮没有做破坏性极限测试。',
    '', '仍需实现并验证全局资源预留、业务预算和实际限制后，再在明确业务负载、模型配额、仓库规模下测试吞吐、尾延迟、公平性、重验证成本和采集开销。本报告不宣布任何固定项目容量。']
inventory=ROOT/'evidence/resource-inventory.json'
if inventory.exists():
    inv=json.loads(inventory.read_text(encoding='utf-8'))
    table=['### 最后一次原生计数快照','',f"采集时间：{inv['at_utc']}。",'',
        '| runtime | call_count | prompt tokens | completion tokens | 可写层 MiB |','|---|---:|---:|---:|---:|']
    for c in inv['containers']:
        if c['name'].endswith('-controller'):continue
        vals=[v for day in c.get('native_token_usage',{}).values() for v in day.values()]
        counts=[str(sum(v.get(k,0) for v in vals)) if vals else '不可用' for k in ('call_count','prompt_tokens','completion_tokens')]
        table.append('| '+c['name']+' | '+' | '.join(counts)+f" | {c.get('size_rw_bytes',0)/2**20:.2f} |")
    table+=['','这些是累计值，不能用 call_count 与六请求数直接相减推定重复执行。Manager 准备、其他验证请求及工具循环都可能贡献调用，需按具体 trace 归属。','']
    lines[lines.index('## 容量结论与限制'):lines.index('## 容量结论与限制')]=table
(ROOT/'reports/capacity-live.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({'phases':len(phases),'samples':sum(p['samples'] for p in phases)}))
