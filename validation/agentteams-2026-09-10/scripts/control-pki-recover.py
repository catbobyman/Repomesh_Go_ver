"""Authorized c-only certificate re-sign and exact supervised Controller process reload."""
import datetime,json,os,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
def call(*args,stdin=None,timeout=45):
 p=subprocess.run(list(args),input=stdin,capture_output=True,text=True,encoding='utf-8',timeout=timeout)
 if p.returncode:raise RuntimeError('Command failed; raw output suppressed: '+args[0])
 return p.stdout
ins=json.loads(call('docker','inspect','rv-c-controller'))[0]
assert ins['Config']['Labels']['repomesh.validation.run']=='agentteams-2026-09-10' and ins['Config']['Labels']['repomesh.validation.instance']=='c'
assert ins['Image']==json.loads(call('docker','image','inspect','repomesh-validation/embedded:517caff9'))[0]['Id']
source=ROOT/'scripts/control-pki-reissue.go';binary=ROOT/'runtime/control-pki-reissue'
p=subprocess.run(['go','build','-o',str(binary),str(source)],env={**os.environ,'GOOS':'linux','GOARCH':'amd64','CGO_ENABLED':'0'},capture_output=True,text=True,timeout=90);assert p.returncode==0
call('docker','cp',str(binary),'rv-c-controller:/tmp/control-pki-reissue')
plan=json.loads(call('docker','exec','rv-c-controller','/tmp/control-pki-reissue'))
(ROOT/'evidence/control-pki-reissue-plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
RELOAD=r'''
import os,pathlib,json,signal,time,sys
c=json.load(sys.stdin)
assert c['action'] in ['inspect','reload']
def processes():
 out={}
 for p in pathlib.Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   rest=(p/'stat').read_text().split(') ',1)[1].split();exe=os.readlink(p/'exe')
   out[int(p.name)]={'pid':int(p.name),'ppid':int(rest[1]),'start_ticks':rest[19],'exe':exe}
  except (FileNotFoundError,PermissionError,ProcessLookupError):pass
 return out
before=processes();matches=[x for x in before.values() if x['exe']=='/usr/local/bin/agentteams-controller']
assert len(matches)==1;old=matches[0];assert old['ppid']==1
assert b'supervisord' in pathlib.Path('/proc/1/cmdline').read_bytes()
children=[x for x in before.values() if x['ppid']==old['pid'] and pathlib.Path(x['exe']).name=='kube-apiserver']
assert len(children)==1
if c['action']=='inspect':print(json.dumps({'controller':old,'kube_child':children[0],'supervisor':before[1]}));sys.exit(0)
assert old==c['expected']['controller'] and children[0]==c['expected']['kube_child']
os.kill(old['pid'],signal.SIGTERM)
orphan_signalled=False
for _ in range(40):
 time.sleep(1);current=processes();current_old=current.get(old['pid']);child=current.get(children[0]['pid'])
 if current_old is None and child==children[0] and not orphan_signalled:
  # Only this exact captured child of the old Controller may be signalled.
  os.kill(child['pid'],signal.SIGTERM);orphan_signalled=True
 new=[x for x in current.values() if x['exe']=='/usr/local/bin/agentteams-controller' and x['pid']!=old['pid'] and x['ppid']==1]
 new_kube=[x for x in current.values() if new and x['ppid']==new[0]['pid'] and pathlib.Path(x['exe']).name=='kube-apiserver']
 if len(new)==1 and len(new_kube)==1 and old['pid'] not in current and children[0]['pid'] not in current:
  print(json.dumps({'before_controller':old,'before_kube':children[0],'after_controller':new[0],'after_kube':new_kube[0],'old_processes_absent':True,'old_kube_precise_sigterm_needed':orphan_signalled,'supervisor_pid_unchanged':before[1]==current.get(1),'signals':'Only exact old c Controller SIGTERM; precise captured old Kube child only if still present'}));sys.exit(0)
raise RuntimeError('Bounded supervised process reload did not converge; no broad kill or service restart attempted')
'''
expected=json.loads(call('docker','exec','-i','rv-c-controller','python3','-c',RELOAD,stdin=json.dumps({'action':'inspect'})))
(ROOT/'evidence/control-pki-process-before.json').write_text(json.dumps(expected,indent=2),encoding='utf-8')
applied=json.loads(call('docker','exec','rv-c-controller','/tmp/control-pki-reissue','--apply'))
(ROOT/'evidence/control-pki-reissue-applied.json').write_text(json.dumps(applied,indent=2),encoding='utf-8')
result=json.loads(call('docker','exec','-i','rv-c-controller','python3','-c',RELOAD,stdin=json.dumps({'action':'reload','expected':expected}),timeout=50))
result['at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();result['container_id_unchanged']=json.loads(call('docker','inspect','rv-c-controller'))[0]['Id']==ins['Id']
(ROOT/'evidence/control-pki-process-reload.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({'certificate_result':applied,'process_reload':result},indent=2))
