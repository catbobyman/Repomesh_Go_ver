"""Single S3 request with immutable snapshot credentials, no mc/STS refresh."""
import sys,json,datetime,hashlib,hmac,urllib.request,urllib.error,urllib.parse,xml.etree.ElementTree as ET
C=json.load(sys.stdin);method=C['method'];payload=json.dumps(C.get('value',{})).encode() if method=='PUT' else b''
host='127.0.0.1:9000';uri='/'+urllib.parse.quote(C['bucket']+'/'+C['key'],safe='/~');now=datetime.datetime.now(datetime.timezone.utc);stamp=now.strftime('%Y%m%dT%H%M%SZ');day=stamp[:8]
ph=hashlib.sha256(payload).hexdigest();headers={'host':host,'x-amz-content-sha256':ph,'x-amz-date':stamp}
if C.get('session_token'):headers['x-amz-security-token']=C['session_token']
signed=';'.join(sorted(headers));canonical=method+'\n'+uri+'\n\n'+''.join(k+':'+headers[k]+'\n' for k in sorted(headers))+'\n'+signed+'\n'+ph
scope=day+'/us-east-1/s3/aws4_request';tosign='AWS4-HMAC-SHA256\n'+stamp+'\n'+scope+'\n'+hashlib.sha256(canonical.encode()).hexdigest()
def mac(k,m):return hmac.new(k,m.encode(),hashlib.sha256).digest()
key=mac(mac(mac(mac(('AWS4'+C['secret_key']).encode(),day),'us-east-1'),'s3'),'aws4_request');sig=hmac.new(key,tosign.encode(),hashlib.sha256).hexdigest()
headers['Authorization']='AWS4-HMAC-SHA256 Credential='+C['access_key']+'/'+scope+', SignedHeaders='+signed+', Signature='+sig
request=urllib.request.Request('http://'+host+uri,data=payload if method=='PUT' else None,headers=headers,method=method)
try:r=urllib.request.urlopen(request,timeout=20)
except urllib.error.HTTPError as e:r=e
b=r.read();result={'http_status':r.code,'method':method,'key':C['key']}
if r.code>=400:
 try:result['error_code']=ET.fromstring(b).findtext('Code')
 except Exception:result['error_code']='unparsed'
elif method=='GET':result.update(value=json.loads(b),sha256=hashlib.sha256(b).hexdigest())
print(json.dumps(result))
