"""Save with readback, then submit exactly one front validation job."""
import hashlib
import json
import os
from pathlib import Path
import ssl
import time
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parent
OUTPUT = ROOT / '系列-夜市百相簿/02-角色/闻灯/设定图/全身验证-2026-10-13'
OUTPUT.mkdir(parents=True, exist_ok=True)
BASE = os.environ['COMFY_BASE'].rstrip('/')
CTX = ssl._create_unverified_context()

def request(path, data=None):
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={'Content-Type': 'application/json'} if data else {})
    return urllib.request.urlopen(req, context=CTX, timeout=40).read()

def record(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

workflow_path = '/userdata/' + urllib.parse.quote('workflows/闻灯.json', safe='')
original = (EVIDENCE / 'remote_before.json').read_bytes()
body = (EVIDENCE / 'candidate.json').read_bytes()
current = request(workflow_path)
assert current in (original, body), 'Remote workflow changed; recheck before saving'
local_path = ROOT / '系列-夜市百相簿/02-角色/闻灯/工作流/闻灯.json'
assert local_path.read_bytes() == original, 'Local workflow changed; recheck before saving'
(EVIDENCE / 'local_before.json').write_bytes(original)
if current != body:
    request(workflow_path + '?overwrite=true', body)
readback = request(workflow_path)
assert readback == body, 'Saved workflow readback differs'
(EVIDENCE / 'remote_after.json').write_bytes(readback)
local_path.write_bytes(readback)
record(EVIDENCE / 'save_validation.json', {
    'workflow_name': '闻灯.json', 'readback_byte_equal': True, 'local_byte_equal': True,
    'sha256': hashlib.sha256(readback).hexdigest(), 'status': '主工作文件 / 待用户验收',
    'base': BASE,
})
print('Saved existing 闻灯.json; remote and local readback identical', flush=True)

api = json.loads((EVIDENCE / 'front_browser_api.json').read_text(encoding='utf-8'))
name = 'front_183_prompt'
job_path = OUTPUT / (name + '_job.json')
assert not job_path.exists(), 'Job already submitted; inspect saved prompt_id instead of resubmitting'
api['15']['inputs']['filename_prefix'] = 'codex_wendeng_20261013/' + name
record(OUTPUT / (name + '_api.json'), api)
payload = {'prompt': api, 'client_id': str(uuid.uuid4())}
record(OUTPUT / (name + '_request.json'), payload)
response = json.loads(request('/prompt', json.dumps(payload, ensure_ascii=False).encode('utf-8')))
record(job_path, response)
assert not response.get('node_errors'), response
prompt_id = response['prompt_id']
print('Submitted', prompt_id, flush=True)
deadline = time.monotonic() + 1500
while time.monotonic() < deadline:
    history = json.loads(request('/history/' + prompt_id))
    if prompt_id in history:
        item = history[prompt_id]
        record(OUTPUT / (name + '_history.json'), item)
        assert item.get('status', {}).get('status_str') == 'success', item.get('status')
        info = item['outputs']['15']['images'][0]
        raw = request('/view?' + urllib.parse.urlencode(info))
        target = OUTPUT / (name + '.png')
        target.write_bytes(raw)
        print('Downloaded', target, len(raw), flush=True)
        record(EVIDENCE / 'queue_after.json', json.loads(request('/queue')))
        break
    time.sleep(5)
else:
    raise TimeoutError('Inspect recorded prompt_id before any new submission')
