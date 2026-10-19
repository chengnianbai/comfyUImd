"""Save the existing entry with readback, then submit exactly one front job."""
import hashlib
import json
from pathlib import Path
import ssl
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid

HERE=Path(__file__).resolve().parent
CFG=json.loads((HERE/'task_config.json').read_text(encoding='utf-8'))
ROOT=Path(CFG['root'])
OUTPUT=Path(CFG['output'])
BASE=CFG['base']
NAME=CFG['name']
CTX=ssl._create_unverified_context()
sys.path.insert(0,str(ROOT/'_scripts'))
from diff_wf import compare_state,advance_state

def record(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def request(path,data=None):
    req=urllib.request.Request(BASE+path,data=data,headers={'Content-Type':'application/json'} if data is not None else {})
    return urllib.request.urlopen(req,context=CTX,timeout=40).read()

assert (HERE/'validation.json').exists(),'Preparation has not passed'
validation=json.loads((HERE/'validation.json').read_text(encoding='utf-8'))
assert validation['api_changes']==['1313','1333','1353']
original=(HERE/'local_before.json').read_bytes()
candidate=(HERE/'candidate.json').read_bytes()
main=ROOT/'系列-夜市百相簿/02-角色/闻灯/工作流/闻灯.json'
path='/userdata/'+urllib.parse.quote('workflows/闻灯.json',safe='')
assert main.read_bytes()==original,'Local entry changed; do not overwrite'
assert request(path)==original,'Remote entry changed; do not overwrite'
queue=json.loads(request('/queue'))
record(HERE/'queue_before.json',queue)
assert not queue['queue_running'] and not queue['queue_pending'],'Existing queue is busy'

save_url=BASE+'/api'+path+'?overwrite=true'
completed=subprocess.run(['curl.exe','--http1.1','-k','--silent','--show-error','--fail',
    '--max-time','55','-H','Content-Type: application/json','-X','POST',
    '--data-binary','@'+str(HERE/'candidate.json'),save_url],capture_output=True,text=True)
record(HERE/'save_http.json',{'returncode':completed.returncode,'stdout':completed.stdout,'stderr':completed.stderr})
# Even if a response timed out, the readback determines whether saving succeeded.
readback=request(path)
assert readback==candidate,'Remote save readback differs; do not run'
(HERE/'remote_after.json').write_bytes(readback)
assert main.read_bytes()==original,'Local entry changed during remote save'
main.write_bytes(readback)
sha=hashlib.sha256(candidate).hexdigest()
report=compare_state(CFG['state'],HERE/'candidate.json')
assert report['new_sha256']==sha
advance_state(CFG['state'],HERE/'candidate.json',report,sha,HERE/'increments')
record(HERE/'save_validation.json',{'local_remote_equal':True,'sha256':sha,
 'name':'闻灯.json','status':'主工作入口，待用户验收','base':BASE,'comparison_baseline_advanced':True})
print(json.dumps({'stage':'saved','sha256':sha,'local_remote_equal':True},ensure_ascii=False),flush=True)

OUTPUT.mkdir(parents=True,exist_ok=True)
job_path=OUTPUT/(NAME+'_job.json')
marker=OUTPUT/(NAME+'_submission_started.json')
assert not marker.exists() and not job_path.exists(),'Submission already started; inspect existing job, never resubmit'
api=json.loads((HERE/'front_browser_api.json').read_text(encoding='utf-8'))
api['15']['inputs']['filename_prefix']='codex_wendeng_20261013/'+NAME
record(OUTPUT/(NAME+'_api.json'),api)
payload={'prompt':api,'client_id':str(uuid.uuid4())}
record(OUTPUT/(NAME+'_request.json'),payload)
record(marker,{'client_id':payload['client_id'],'submitted_at':time.time(),'no_automatic_retry':True})
response=json.loads(request('/prompt',json.dumps(payload,ensure_ascii=False).encode('utf-8')))
record(job_path,response)
assert not response.get('node_errors'),response
prompt_id=response['prompt_id']
print(json.dumps({'stage':'submitted_once','prompt_id':prompt_id,'dependencies':len(api)},ensure_ascii=False),flush=True)
deadline=time.monotonic()+1500
last_report=time.monotonic()
while time.monotonic()<deadline:
    history=json.loads(request('/history/'+prompt_id))
    if prompt_id in history:
        item=history[prompt_id]
        record(OUTPUT/(NAME+'_history.json'),item)
        assert item.get('status',{}).get('status_str')=='success',item.get('status')
        images=item.get('outputs',{}).get('15',{}).get('images',[])
        assert len(images)==1,images
        info=images[0]
        raw=request('/view?'+urllib.parse.urlencode(info))
        target=OUTPUT/(NAME+'.png')
        target.write_bytes(raw)
        after=json.loads(request('/queue'))
        record(HERE/'queue_after.json',after)
        record(OUTPUT/(NAME+'_validation.json'),{'prompt_id':prompt_id,'history_status':'success',
          'submitted_jobs':1,'output_images':1,'output_bytes':len(raw),'image_sha256':hashlib.sha256(raw).hexdigest(),
          'workflow_sha256':sha,'queue_running_count':len(after['queue_running']),
          'queue_pending_count':len(after['queue_pending']),'user_acceptance':'待用户判断'})
        print(json.dumps({'stage':'finished','prompt_id':prompt_id,'target':str(target),'bytes':len(raw),
         'queue_empty':not after['queue_running'] and not after['queue_pending']},ensure_ascii=False),flush=True)
        break
    if time.monotonic()-last_report>40:
        print(json.dumps({'stage':'waiting','prompt_id':prompt_id},ensure_ascii=False),flush=True)
        last_report=time.monotonic()
    time.sleep(5)
else:
    raise TimeoutError('Inspect saved prompt_id; do not submit another job')
