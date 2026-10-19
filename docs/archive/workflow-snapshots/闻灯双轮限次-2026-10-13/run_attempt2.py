"""Save and execute the second and final authorized front validation."""
import hashlib
import json
from pathlib import Path
import ssl
import subprocess
import time
import urllib.parse
import urllib.request
import uuid

ROOT=Path(__file__).resolve().parents[4]
E=Path(__file__).resolve().parent
OUT=ROOT/'系列-夜市百相簿/02-角色/闻灯/设定图/全身验证-2026-10-13'
MAIN=ROOT/'系列-夜市百相簿/02-角色/闻灯/工作流/闻灯.json'
BASE='https://gw-da074043649a46aa8485bca1ba422cbe.cn-beijing.aigclinks.com:8016'
CTX=ssl._create_unverified_context()
NAME='attempt2_tank_framing'

def record(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def request(path,data=None):
    req=urllib.request.Request(BASE+path,data=data,headers={'Content-Type':'application/json'} if data is not None else {})
    return urllib.request.urlopen(req,context=CTX,timeout=45).read()

assert (E/'attempt2_validation.json').exists()
before=(E/'attempt2_remote_before.json').read_bytes()
candidate=(E/'attempt2_candidate.json').read_bytes()
workflow_path='/userdata/'+urllib.parse.quote('workflows/闻灯.json',safe='')
assert MAIN.read_bytes()==before and request(workflow_path)==before,'Workflow changed since review; stop'
queue=json.loads(request('/queue'));record(E/'attempt2_queue_before.json',queue)
assert not queue['queue_running'] and not queue['queue_pending'],'Queue is busy; stop'

http=subprocess.run(['curl.exe','--http1.1','-k','--silent','--show-error','--fail','--max-time','55',
    '-H','Content-Type: application/json','-X','POST','--data-binary','@'+str(E/'attempt2_candidate.json'),
    BASE+'/api'+workflow_path+'?overwrite=true'],capture_output=True,text=True)
record(E/'attempt2_save_http.json',{'returncode':http.returncode,'stdout':http.stdout,'stderr':http.stderr})
readback=request(workflow_path)
assert readback==candidate,'Remote workflow did not read back byte-identically; do not run'
assert MAIN.read_bytes()==before,'Local workflow changed during save; stop'
(E/'attempt2_remote_after.json').write_bytes(readback)
MAIN.write_bytes(readback)
sha=hashlib.sha256(readback).hexdigest()
record(E/'attempt2_save_validation.json',{'readback_byte_equal':True,'sha256':sha,
    'workflow':'闻灯.json','status':'角色主工作入口，待验收','attempt':2,'final_attempt':True})
print(json.dumps({'stage':'saved','attempt':2,'sha256':sha,'readback_byte_equal':True},ensure_ascii=False),flush=True)

OUT.mkdir(parents=True,exist_ok=True)
marker=OUT/(NAME+'_submission_started.json');job_path=OUT/(NAME+'_job.json')
assert not marker.exists() and not job_path.exists(),'Attempt 2 already started; never duplicate'
api=json.loads((E/'attempt2_front_api.json').read_text(encoding='utf-8'))
api['15']['inputs']['filename_prefix']='codex_wendeng_20261013/'+NAME
record(OUT/(NAME+'_api.json'),api)
payload={'prompt':api,'client_id':str(uuid.uuid4())}
record(OUT/(NAME+'_request.json'),payload)
record(marker,{'attempt':2,'client_id':payload['client_id'],'started_at':time.time(),
 'automatic_retry':False,'final_authorized_attempt':True})
submitted=json.loads(request('/prompt',json.dumps(payload,ensure_ascii=False).encode('utf-8')))
record(job_path,submitted)
assert not submitted.get('node_errors'),submitted
pid=submitted['prompt_id']
print(json.dumps({'stage':'submitted_once','attempt':2,'prompt_id':pid,'dependencies':len(api)},ensure_ascii=False),flush=True)
deadline=time.monotonic()+1500;last=time.monotonic()
while time.monotonic()<deadline:
    history=json.loads(request('/history/'+pid))
    if pid in history:
        item=history[pid];record(OUT/(NAME+'_history.json'),item)
        assert item.get('status',{}).get('status_str')=='success',item.get('status')
        images=item.get('outputs',{}).get('15',{}).get('images',[])
        assert len(images)==1,images
        raw=request('/view?'+urllib.parse.urlencode(images[0]))
        target=OUT/(NAME+'.png');target.write_bytes(raw)
        queue=json.loads(request('/queue'));record(E/'attempt2_queue_after.json',queue)
        record(OUT/(NAME+'_validation.json'),{'attempt':2,'final_authorized_attempt':True,
          'prompt_id':pid,'history':'success','image_count':1,'bytes':len(raw),
          'sha256':hashlib.sha256(raw).hexdigest(),'workflow_sha256':sha,
          'queue_empty':not queue['queue_running'] and not queue['queue_pending'],
          'after_this_attempt':'stop; wait for user decision'})
        print(json.dumps({'stage':'finished','attempt':2,'prompt_id':pid,'target':str(target),
          'bytes':len(raw),'queue_empty':not queue['queue_running'] and not queue['queue_pending']},ensure_ascii=False),flush=True)
        break
    if time.monotonic()-last>40:
        print(json.dumps({'stage':'waiting','attempt':2,'prompt_id':pid},ensure_ascii=False),flush=True)
        last=time.monotonic()
    time.sleep(5)
else:
    raise TimeoutError('Inspect attempt 2 prompt_id; do not retry or submit another job')
