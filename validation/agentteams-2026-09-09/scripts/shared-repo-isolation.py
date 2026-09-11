"""Read-only shared Git origin, independent same-name clones in actual Worker containers."""
import datetime as dt,json,secrets,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUN=secrets.token_hex(5)
BASE=(ROOT/'runtime'/('git-isolation-'+RUN)).resolve()
assert BASE.is_relative_to((ROOT/'runtime').resolve())
BASE.mkdir()
records=[]
helper='rv-git-fixture-'+RUN

def run(*args,cwd=None,data=None,timeout=45):
    p=subprocess.run(args,cwd=cwd,input=data,text=True,encoding='utf-8',errors='replace',capture_output=True,timeout=timeout)
    if p.returncode:raise RuntimeError(f'{args[0]} command failed {p.returncode}: {p.stderr[:300]}')
    return p.stdout.strip()

def record(kind,**kw):
    records.append({'kind':kind,**kw})
    (ROOT/'evidence/shared-repo-isolation.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    src=BASE/'seed'
    src.mkdir()
    run('git','init','-b','main',str(src))
    (src/'README.txt').write_text('Shared immutable validation source\n',encoding='utf-8')
    run('git','add','README.txt',cwd=src)
    run('git','-c','user.name=Validation Fixture','-c','user.email=fixture@invalid','commit','-m','Seed fixture',cwd=src)
    initial=run('git','rev-parse','HEAD',cwd=src)
    run('git','clone','--bare',str(src),str(BASE/'source.git'))
    run('git','--git-dir',str(BASE/'source.git'),'update-server-info')
    record('origin',initial_commit=initial,source=str(BASE/'source.git'),writable_origin=False,
        boundary='Local fixed-content HTTP Git fixture shared by both networks; not GitHub authorization or model tool execution')
    cid=run('docker','create','--name',helper,'--label','repomesh.validation=agentteams-2026-09-09',
        '--network','rv-a-net','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
        '--mount',f'type=bind,source={BASE},target=/fixture,readonly','--entrypoint','/opt/venv/qwenpaw/bin/python',
        'repomesh-validation/qwenpaw-worker:eeaab643','-m','http.server','8080','--bind','0.0.0.0','--directory','/fixture')
    try:
        run('docker','network','connect','rv-b-net',cid)
        run('docker','start',cid)
        remote=f'http://{helper}:8080/source.git'
        clone='/tmp/repomesh-same-origin-'+RUN
        for i in 'ab':
            name=f'rv-{i}-worker-live-twin-worker'
            run('docker','exec',name,'git','clone',remote,clone)
            sha=run('docker','exec',name,'git','-C',clone,'rev-parse','HEAD')
            record('clone',instance=i,container=name,remote=remote,path=clone,commit=sha,equal_origin=sha==initial)
            assert sha==initial
        a='rv-a-worker-live-twin-worker';b='rv-b-worker-live-twin-worker'
        code='from pathlib import Path;p=Path('+repr(clone)+');(p/"README.txt").write_text("instance a changed\\n");(p/"only-a.txt").write_text("'+RUN+'")'
        run('docker','exec',a,'/opt/venv/qwenpaw/bin/python','-c',code)
        run('docker','exec',a,'git','-C',clone,'add','README.txt','only-a.txt')
        run('docker','exec',a,'git','-C',clone,'-c','user.name=Validation Fixture','-c','user.email=fixture@invalid','commit','-m','Isolated a change')
        a_sha=run('docker','exec',a,'git','-C',clone,'rev-parse','HEAD')
        b_sha=run('docker','exec',b,'git','-C',clone,'rev-parse','HEAD')
        b_files=json.loads(run('docker','exec',b,'/opt/venv/qwenpaw/bin/python','-c',
            'import json;from pathlib import Path;p=Path('+repr(clone)+');print(json.dumps({"readme":(p/"README.txt").read_text(),"only_a_exists":(p/"only-a.txt").exists()}))'))
        origin=run('git','--git-dir',str(BASE/'source.git'),'rev-parse','HEAD')
        record('isolation',a_commit=a_sha,b_commit=b_sha,origin_commit=origin,b_files=b_files,
            same_original_remote=remote,a_changed=a_sha!=initial,b_unchanged=b_sha==initial,origin_unchanged=origin==initial)
        assert a_sha!=initial and b_sha==initial and origin==initial and not b_files['only_a_exists']
    finally:
        obj=json.loads(run('docker','inspect',cid))[0]
        assert obj['Name']=='/'+helper and obj['Config']['Labels'].get('repomesh.validation')=='agentteams-2026-09-09'
        run('docker','stop','--time','5',cid)
        run('docker','rm',cid)
        record('helper_cleanup',removed_id=cid,source_and_clones_preserved=True)
    print(json.dumps({'shared_origin':True,'independent_clones':True,'helper_removed':True}))

if __name__=='__main__':main()
