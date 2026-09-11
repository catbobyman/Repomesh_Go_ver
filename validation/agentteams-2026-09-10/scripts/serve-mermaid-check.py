"""Serve only this run's isolated renderer files and save its browser result."""
import argparse,http.server,json,shutil,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--port',type=int,default=48444)
parser.add_argument('--case-file',default='mermaid-library-cases.json')
parser.add_argument('--served-name',default='cases.json')
parser.add_argument('--result-file',default='mermaid-browser-result.json')
args=parser.parse_args()
assert all(Path(v).name==v for v in (args.case_file,args.served_name,args.result_file))
public=ROOT/'runtime/mermaid-check'
shutil.copyfile(ROOT/'scripts/mermaid-browser.html',public/'index.html')
shutil.copyfile(ROOT/'evidence'/args.case_file,public/args.served_name)
class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map={**http.server.SimpleHTTPRequestHandler.extensions_map,'.mjs':'text/javascript'}
    def __init__(self,*a,**kw):super().__init__(*a,directory=str(public),**kw)
    def do_POST(self):
        if self.path=='/shutdown':
            self.send_response(200);self.end_headers()
            threading.Thread(target=self.server.shutdown,daemon=True).start();return
        if self.path!='/result':self.send_error(404);return
        result=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        target=ROOT/'evidence'/args.result_file
        if target.exists():self.send_error(409,'Existing evidence preserved');return
        target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        self.send_response(201);self.end_headers();self.wfile.write(b'saved')
    def log_message(self,*args):pass
print('Renderer fixture: http://127.0.0.1:'+str(args.port),flush=True)
http.server.ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
