from pathlib import Path
from datetime import datetime, timezone
import hashlib
import html
import json
import struct

ROOT = Path(__file__).resolve().parent

# Preserve the original browser bytes; use an extension matching their actual format.
for path in (ROOT / 'screenshots').glob('*.png'):
    if path.read_bytes().startswith(b'\xff\xd8'):
        path.rename(path.with_suffix('.jpg'))

images = [
 ('01-overview', '概览：个人 Pro 与按需用量状态', ''),
 ('02-settings', '设置：数据共享与公开个人资料', '/settings'),
 ('03-privacy-options', '隐私选项：Privacy Mode 与 Share Data', '/settings'),
 ('04-cloud-agents', '云代理：环境、自托管机器和远程控制', '/cloud-agents'),
 ('05-cloud-preferences', '云代理偏好：模型、仓库、PR 和通知', '/cloud-agents'),
 ('06-pr-options', '自动创建 PR 的三个选项', '/cloud-agents'),
 ('07-artifact-options', 'GitHub 产物发布选项', '/cloud-agents'),
 ('08-cloud-security', '云代理安全：网络访问、通知和 Secrets', '/cloud-agents'),
 ('09-network-options', '网络访问策略的三个选项', '/cloud-agents'),
 ('10-members', '成员页面：Teams 升级与团队能力介绍', '/members'),
 ('11-integrations', '第三方集成连接状态', '/integrations'),
 ('12-github-management', 'GitHub 管理菜单', '/integrations'),
 ('13-plugins', '插件：空列表及推荐插件', '/plugins'),
 ('14-api-ssh-keys', 'API 与 SSH 密钥：均未创建', '/api'),
 ('15-shared-canvases', '共享画布：空列表', '/shared-canvases'),
 ('16-spending', '花费控制：按需额外付费已禁用', '/spending'),
 ('17-usage', '用量：当前 7 天筛选范围', '/usage'),
 ('18-billing', '账单：Pro 订阅、续费与支付管理入口', '/billing'),
 ('19-settings-sessions', '活跃会话与账户操作入口', '/settings'),
]

sections = [
 dict(title='1. 检查范围与主要结论', paragraphs=[
  '本报告对应用户要求的 Cursor Dashboard 检查，基于 Chrome 中当前登录账号 Bohan Xu 的实际页面。采集日期按 America/Los_Angeles 为 2026 年 9 月 7 日；对应 UTC 为 9 月 8 日。逐图时间记录在 evidence/capture-manifest.json。',
  '当前工作区显示个人 Pro，价格为 $20/月。Members 页面显示 Upgrade to Teams，没有呈现团队成员名单或角色配置。本次只能核验个人工作区的现状和页面展示的团队升级能力。',
  '关键状态：Share Data 已启用；Cloud Agents 网络策略为 Allow All Network Access；自托管机器和远程控制均关闭；按需额外付费关闭。Slack 通知开关打开，但 Slack 本身尚未连接。',
  '本次仅进行页面导航、滚动、展开菜单和截图。未改变功能开关，未创建团队、密钥或连接，未撤销会话，也未执行升级、支付或取消订阅。'
 ], shots=[1]),
 dict(title='2. 隐私、个人资料与会话权限', paragraphs=[
  'Share Data 标有 Active。页面说明代码库、提示词、编辑和其他使用数据会被 Cursor 存储并用于训练，以改进产品。Privacy Mode 是另一个可选项，当前未选中；其说明为不用于训练，但 Cloud Agent、Team Rules 等功能可能仍会存储代码。因此不能把 Privacy Mode 等同于所有数据均不落地。',
  'Public profile 处于关闭状态。页面说明，开启后任何持有链接的人都能查看 cursor.com 个人资料页。',
  'Active Sessions 显示 Showing 1–5 of 29，共 29 个会话，第一页展示 5 个 Desktop App 会话。每个会话有 Revoke 按钮，页面提示撤销最多需要 10 分钟。未逐页核验全部设备，也未对这些会话是否异常作判断。',
  '另有 Log Out 和 Delete Account 入口。页面文字记录还显示：主题为 System，浅色主题 Cursor Light、深色主题 Cursor Dark，PR Review Provider 为 GitHub。这些项目见设置页面的文字证据，截图重点覆盖隐私和会话。'
 ], rows=[['项目','当前状态','含义'],['Share Data','启用','页面说明相关数据用于存储与训练'],['Privacy Mode','未选中','可选择不训练；部分功能仍可能存储代码'],['Public profile','关闭','未启用持链接公开访问个人资料'],['Active Sessions','29 个','支持逐个撤销，最多 10 分钟生效']], shots=[2,3,19]),
 dict(title='3. Cloud Agents 功能与执行权限', paragraphs=[
  '当前有 1 个 Personal 范围的环境，关联 catbobyman/MultiAgent-Werewolf。页面在 Sep 01–Sep 07 筛选范围内显示 5 次运行、成功率 100%。这些是当前筛选范围的统计，不代表全部历史运行。',
  '自托管机器和远程控制开关均关闭。远程控制的页面说明为：开启后，所有本地 Agent 可通过手机和网页控制。这里只核验开关状态，没有进入机器详情或启动执行。'
 ], rows=[['项目','当前状态','说明'],['Enable Self-hosted Machines','关闭','云代理在自托管机器上的运行入口未开启'],['Enable Remote Control','关闭','未开启网页/手机对本地 Agent 的控制'],['Default Model','Claude Sonnet 4.5','未指定模型时使用'],['Default Repository','未选择','显示 Select Repository'],['Base Branch','未填写','页面说明为空时使用仓库默认分支'],['Branch Prefix','输入框显示 cursor/ 占位提示','不将占位提示当作已保存值'],['Repository routing','0 Rules','没有仓库路由规则'],['My Secrets','0 Secrets','当前列表计数为零']], shots=[4,5]),
 dict(title='4. PR、产物发布、通知与网络策略', paragraphs=[
  'Create PRs 当前为 For Single Model Runs，表示单模型运行完成后自动创建 PR；菜单另有 Always 和 Never。该设置涉及自动创建 PR，不代表自动合并权限。',
  'Allow Posting Artifacts to GitHub 当前为 Link Only，另有 Post Artifact。页面说明云代理可通过难以猜测的公开 URL 把图片嵌入 PR 描述。Link Only 是当前发布方式，不能由此推断全部产物链接的访问鉴权机制。',
  'Slack Notifications 开关为开启，但 Slack Integration 仍显示 Connect Slack，因此“通知开关开启”和“集成已配置并可实际收到通知”是两件事。',
  'Network Access Settings 当前为 Allow All Network Access。菜单可选 Defaults + My Allowlist、My Allowlist Only 和 Allow All Network Access。本次没有切换策略，因此未展开其他策略对应的域名列表；无法据此列出默认允许哪些目的地址。'
 ], rows=[['设置','当前选择','可选项/边界'],['Create PRs','For Single Model Runs','Always / For Single Model Runs / Never'],['GitHub 产物发布','Link Only','Post Artifact / Link Only'],['Slack Notifications','开启','Slack 尚未连接'],['Network Access','Allow All Network Access','Defaults + My Allowlist / My Allowlist Only / Allow All Network Access']], shots=[6,7,8,9]),
 dict(title='5. 团队设置与管理员权限边界', paragraphs=[
  'Members 页面只显示 Upgrade to Teams、Create team 和 Contact sales。没有展示成员邀请记录、具体角色、管理员名单或权限矩阵。因此不能从当前页面断言某个成员拥有管理员权限，也不能判断某项组织策略已经开启或关闭。',
  'Teams 介绍列出 Team Management（邀请成员、角色与访问管理）、Usage Analytics（团队用量分析）、Admin Controls（集中账单和隐私模式控制）、Rules & Commands（团队共享规则和命令）。',
  'Enterprise 介绍另列出 pooled usage（共享用量池）、SCIM seat management（SCIM 席位管理）和 granular admin controls（更细粒度的管理员控制）。以上属于页面展示的套餐能力，不是当前账号已生效的配置。',
  '若后续进入真实 Teams 工作区，需要另行核验：成员角色及管理员范围、加入/邀请控制、组织级隐私策略、插件强制配置、团队费用上限，以及身份管理配置。当前报告对这些项目统一记为“未核验”，不记为“关闭”。'
 ], shots=[10]),
 dict(title='6. 第三方集成与代码仓库授权', paragraphs=[
  'GitHub 已连接，账号为 catbobyman。控制台文字列出可访问仓库所在的组织 LBP97541135、catbobyman。该文字不等于对这些组织下全部仓库均有访问权。',
  'Manage 菜单提供 Manage in GitHub、Reconnect 和 Disconnect。本次只展开菜单，没有跳转 GitHub 修改安装权限。当前 Cursor 面板没有列出完整仓库范围、OAuth/GitHub App scopes 或具体读写权限。',
  'Slack、Microsoft Teams、Linear 和 Sentry 均显示 Connect。Jira 的 Connect 在加载完成后仍不可用；页面没有说明具体原因，不推断为套餐限制或永久不支持。'
 ], rows=[['集成','当前状态','页面用途'],['GitHub','已连接','代码仓库访问'],['Slack','未连接','从 Slack 使用 Cloud Agents'],['Microsoft Teams','未连接','从 Teams 使用 Cloud Agents'],['Linear','未连接','把 issue 委派给 Cloud Agents'],['Jira','Connect 不可用','页面介绍为 issue 委派'],['Sentry','未连接','在 Automations 中使用 issue 事件']], shots=[11,12]),
 dict(title='7. 插件、API/SSH 密钥与共享访问', paragraphs=[
  'Plugins 显示 No Plugins。All、Required、Optional 是列表筛选项，不是三个已开启或关闭的权限开关。Suggested 中的 Google Drive、Google Calendar、Gmail、Granola 是推荐项，不能视为已安装或已授权。',
  'API & SSH Keys 显示 No API Keys Yet 和 No SSH Keys Yet。User API Keys 的页面说明涵盖 Cursor 账号的程序化访问、无界面 Agent CLI 和 Cloud Agent API；本次未创建密钥，因此也没有验证创建时是否提供细粒度 scopes。SSH 密钥说明用于 Origin Codebase 的 SSH 认证访问。',
  'Shared Canvases 显示 No Canvases，当前没有列出的共享画布。本次未创建共享对象，因此未验证创建后的分享对象、链接可见范围和撤销机制。'
 ], shots=[13,14,15]),
 dict(title='8. 费用控制、用量与账单', paragraphs=[
  'Spending 中 On-Demand Spending 为 Disabled，页面文字明确说明按需花费已禁用；Monthly Limit 也为 Disabled，Save 不可用。Cursor Models、Other Models 和 Grok Bot 周用量均显示约 1%，仅代表截图时状态。',
  'Usage 当前采用 7d 筛选，截图显示 Sep 02–Sep 08、Total tokens 10.6M、Included 10.6M、On-demand 0。表格日期以 UTC 展示。这是当前时间范围统计，不与账单整周期数据混用。页面提供按模型分组和 Export CSV。',
  'Billing & Invoices 显示 Pro $20/月，订阅将于 2026 年 10 月 1 日自动续费；提供 Adjust plan、Manage in Stripe 等入口。页面文字记录还显示 9 月 1 日至 9 月 8 日按需费用为 US$0.00，以及 9 月 1 日一笔 paid、20.00 USD 的发票。未打开 Stripe、发票链接或执行支付操作。',
  '按需用量关闭不等于订阅自动续费关闭；两者在面板中是不同控制。截图 16 展示禁用状态，Monthly Limit 的完整文字记录见同名 evidence 文件。'
 ], shots=[16,17,18]),
 dict(title='9. 证据说明与未核验事项', paragraphs=[
  '本报告是当前账号在采集时刻的界面快照。截图采用浏览器原始 JPEG 画面，长页面按关键区域分别采集；没有声称每张均为完整长截图。没有对图片进行内容重绘。浏览器截图曾出现超时和旧画面，相关图片已逐张目视核对并重拍。',
  '每张截图有同名页面文字记录，文字记录可能覆盖截图视口以外的内容。正文已区分截图直接展示的状态、文字记录中的补充信息，以及尚未核验的项目。',
  '未核验事项包括：实际 Teams/Enterprise 权限配置、GitHub 精确仓库及读写授权、其他网络策略的域名清单、插件安装后的权限、API 密钥细粒度 scopes，以及共享画布发布后的访问策略。',
  '本地文件保留账号页面可见信息。账单文字证据中的 Stripe 发票直达地址已替换为省略提示，报告不包含该地址。状态没有因本次报告制作而被修改。'
 ], shots=[]),
]

# A private invoice link is unnecessary evidence for configuration review.
billing_evidence = ROOT / 'evidence/18-billing.txt'
if billing_evidence.exists():
    import re
    txt = billing_evidence.read_text(encoding='utf-8')
    txt = re.sub(r'https://invoice\.stripe\.com/[^\s]+', '[invoice-link-omitted]', txt)
    billing_evidence.write_text(txt, encoding='utf-8')

def esc(v): return html.escape(str(v))
def jpeg_size(data):
    pos = 2
    while pos < len(data):
        if data[pos] != 255:
            pos += 1
            continue
        marker = data[pos + 1]
        pos += 2
        if marker in (0xD8, 0xD9): continue
        size = int.from_bytes(data[pos:pos + 2], 'big')
        if marker in (0xC0, 0xC1, 0xC2):
            return int.from_bytes(data[pos+5:pos+7], 'big'), int.from_bytes(data[pos+3:pos+5], 'big')
        pos += size
    return None, None

manifest = []
for stem, title, suffix in images:
    path = ROOT / 'screenshots' / (stem + '.jpg')
    data = path.read_bytes()
    width, height = jpeg_size(data)
    assert width and height and len(data) > 1000, path
    assert (ROOT / 'evidence' / (stem + '.txt')).exists(), stem
    manifest.append(dict(id=stem, title=title, url='https://cursor.com/dashboard'+suffix,
                         image='screenshots/'+path.name, evidence='evidence/'+stem+'.txt',
                         savedAtUtc=datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                         width=width, height=height, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                         imageVerified=True))
(ROOT / 'evidence/capture-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

md = ['# Cursor Dashboard 界面与权限检查报告', '', '采集日期：2026-09-07（America/Los_Angeles）｜个人 Pro｜19 张截图｜只读检查', '']
body = ['<header><p class="eyebrow">CURSOR · DASHBOARD REVIEW</p><h1>界面与权限检查报告</h1><p>2026-09-07 · America/Los_Angeles · 个人 Pro · 19 张实拍截图</p><div class="badges"><span>Share Data：开启</span><span>网络：全部允许</span><span>按需付费：关闭</span><span>团队权限：未核验</span></div></header>']
body.append('<nav>' + ''.join(f'<a href="#section-{i}">{esc(s["title"])}</a>' for i,s in enumerate(sections,1)) + '<a href="#gallery">截图索引</a></nav>')
for i, section in enumerate(sections, 1):
    md.extend(['## '+section['title'], ''])
    body.append(f'<section id="section-{i}"><h2>{esc(section["title"])}</h2>')
    for p in section['paragraphs']:
        md.extend([p, ''])
        body.append('<p>'+esc(p)+'</p>')
    if section.get('rows'):
        rows = section['rows']
        md.extend(['| '+' | '.join(rows[0])+' |', '| '+' | '.join(['---']*len(rows[0]))+' |'])
        md.extend('| '+' | '.join(r)+' |' for r in rows[1:])
        md.append('')
        body.append('<div class="table-wrap"><table><thead><tr>'+''.join('<th>'+esc(c)+'</th>' for c in rows[0])+'</tr></thead><tbody>')
        body.extend('<tr>'+''.join('<td>'+esc(c)+'</td>' for c in r)+'</tr>' for r in rows[1:])
        body.append('</tbody></table></div>')
    for number in section['shots']:
        m = manifest[number-1]
        caption = f'图 {number:02d} · {m["title"]}'
        md.extend([f'![{caption}]({m["image"]})', '', f'{caption}｜[原页面]({m["url"]})｜[页面文字记录]({m["evidence"]})', ''])
        body.append(f'<figure id="figure-{number}"><a href="{m["image"]}" target="_blank"><img src="{m["image"]}" alt="{esc(caption)}" loading="lazy"></a><figcaption>{esc(caption)} · <a href="{m["url"]}" target="_blank">原页面</a> · <a href="{m["evidence"]}">文字记录</a> · {m["width"]}×{m["height"]}</figcaption></figure>')
    body.append('</section>')

md.extend(['## 截图索引', '', '| 编号 | 截图 | 页面 |', '| --- | --- | --- |'])
body.append('<section id="gallery"><h2>截图索引</h2><div class="gallery">')
for i,m in enumerate(manifest,1):
    md.append(f'| {i:02d} | [{m["title"]}]({m["image"]}) | [原页面]({m["url"]}) |')
    body.append(f'<a class="tile" href="#figure-{i}"><img src="{m["image"]}" loading="lazy" alt="{esc(m["title"])}"><span>{i:02d} · {esc(m["title"])}</span></a>')
body.append('</div></section><footer>原始截图与页面文字记录均在本文件夹中。点击截图查看原图。报告仅反映采集时状态。</footer>')
css = '''*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f3f5f8;color:#263347;font-family:Segoe UI,Microsoft YaHei,sans-serif;line-height:1.8}main{max-width:1180px;margin:auto;padding:32px 24px}header{background:#142237;color:white;padding:46px;border-radius:20px}h1{font-size:36px;margin:8px 0}.eyebrow{font-size:12px;letter-spacing:3px;color:#a2c8ff}.badges{display:flex;gap:10px;flex-wrap:wrap}.badges span{background:#2b405e;border-radius:8px;padding:5px 12px;font-size:13px}nav{display:flex;gap:8px;flex-wrap:wrap;margin:22px 0}nav a{background:white;padding:7px 12px;border-radius:7px;font-size:13px}a{color:#2563a7;text-decoration:none}a:hover{text-decoration:underline}section{background:white;border:1px solid #e0e6ed;border-radius:14px;padding:30px;margin:22px 0}h2{font-size:24px;margin:0 0 18px}p{margin:12px 0}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #e5eaf0;padding:12px}th{background:#eff4fa}.table-wrap{overflow:auto;margin:24px 0}figure{margin:28px 0 10px}figure img{width:100%;height:auto;border-radius:8px;border:1px solid #d6deea}figcaption{font-size:13px;color:#65758b;margin-top:6px}.gallery{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.tile{display:block;font-size:12px}.tile img{width:100%;aspect-ratio:2.1;object-fit:cover;border-radius:6px}.tile span{display:block}footer{font-size:13px;color:#64748b;padding:20px 0}@media(max-width:760px){main{padding:12px}header,section{padding:20px}h1{font-size:28px}.gallery{grid-template-columns:repeat(2,1fr)}}@media print{body{background:white}main{max-width:none;padding:0}nav{display:none}section{border:0;padding:10px 0;break-inside:auto}figure{break-inside:avoid}header{background:#eee;color:#111}a{color:inherit}.gallery{display:none}}'''
(ROOT / 'report.md').write_text('\n'.join(md)+'\n', encoding='utf-8')
(ROOT / 'report.html').write_text('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cursor Dashboard 界面与权限报告</title><style>'+css+'</style></head><body><main>'+''.join(body)+'</main></body></html>', encoding='utf-8')
(ROOT / 'README.md').write_text('''# Cursor Dashboard 检查资料

- [阅读图文报告（HTML）](report.html)：带目录、截图索引和原图链接，可直接在浏览器打开。
- [阅读/编辑报告（Markdown）](report.md)：正文与 HTML 相同。
- `screenshots/`：19 张原始 JPEG 截图，已核对页面内容。
- `evidence/`：逐图页面文字记录和 `capture-manifest.json`（来源 URL、保存时间、尺寸、SHA-256）。
- `build_report.py`：重新生成报告和索引的本地脚本，仅使用 Python 标准库。

截图覆盖控制台全部 11 个导航页面，以及隐私、网络、PR、产物和 GitHub 管理菜单。长页面按关键区域截图，文字记录用于补充视口外的信息。

当前账号为个人 Pro；真实 Teams/Enterprise 权限配置未核验。整个制作过程没有修改 Cursor 设置。
''', encoding='utf-8')

assert len(list((ROOT/'screenshots').glob('*.jpg'))) == 19
assert len(manifest) == 19
for m in manifest:
    assert m['image'] in (ROOT/'report.html').read_text(encoding='utf-8')
print(json.dumps({'screenshots':len(manifest),'report_html_bytes':(ROOT/'report.html').stat().st_size,'report_md_bytes':(ROOT/'report.md').stat().st_size,'verified_images':True}, ensure_ascii=False))
