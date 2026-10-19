# -*- coding: utf-8 -*-
"""冒烟：一体化 flux1-dev-fp8 能否真的被加载（纯文生图最小链路）。

用法：
    COMFY_BASE=https://gw-xxxx.cn-beijing.aigclinks.com:8016 python probe_flux_t2i.py

判据（自动）：
    报错含 'header too small' / 'file not fully covered'  → 文件残缺 ✘
    其他报错（形状/节点不匹配之类）                        → 文件是好的 ✔
"""
import os
import json
import ssl
import sys
import time
import uuid
import urllib.request
import urllib.error

B = os.environ.get(
    'COMFY_BASE',
    'https://gw-efb56d453d484597a1b8ddfc86156262.cn-beijing.aigclinks.com:8016'
).rstrip('/')

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

CKPT = 'FLUX1\\flux1-dev-fp8.safetensors'


def post(path, obj, timeout=240):
    req = urllib.request.Request(
        B + path, data=json.dumps(obj).encode(),
        headers={'Content-Type': 'application/json'})
    return urllib.request.urlopen(req, timeout=timeout, context=ctx).read()


wf = {
    '1': {'class_type': 'CheckpointLoaderSimple',
          'inputs': {'ckpt_name': CKPT}},
    '2': {'class_type': 'CLIPTextEncode',
          'inputs': {'text': 'a photo of a cat', 'clip': ['1', 1]}},
    '3': {'class_type': 'CLIPTextEncode',
          'inputs': {'text': '', 'clip': ['1', 1]}},
    '4': {'class_type': 'EmptySD3LatentImage',
          'inputs': {'width': 256, 'height': 256, 'batch_size': 1}},
    '5': {'class_type': 'KSampler',
          'inputs': {'model': ['1', 0], 'positive': ['2', 0], 'negative': ['3', 0],
                     'latent_image': ['4', 0], 'seed': 1, 'steps': 1, 'cfg': 1.0,
                     'sampler_name': 'euler', 'scheduler': 'simple', 'denoise': 1.0}},
    '6': {'class_type': 'VAEDecode', 'inputs': {'samples': ['5', 0], 'vae': ['1', 2]}},
    '7': {'class_type': 'SaveImage',
          'inputs': {'images': ['6', 0], 'filename_prefix': '_probe_flux_t2i'}},
}

t0 = time.time()
try:
    r = json.loads(post('/prompt', {'prompt': wf, 'client_id': str(uuid.uuid4())}).decode())
except urllib.error.HTTPError as e:
    print('提交被拒 HTTP %s: %s' % (e.code, e.read().decode('utf-8', 'replace')[:400]))
    sys.exit(1)

if r.get('node_errors'):
    print('提交被拒（节点错误）：', json.dumps(r['node_errors'], ensure_ascii=False)[:500])
    sys.exit(1)

pid = r['prompt_id']
print('已提交（模型 17.25GB，加载要等一会儿）…')

for i in range(90):
    time.sleep(2)
    try:
        h = json.loads(urllib.request.urlopen(
            B + '/history/' + pid, timeout=60, context=ctx).read().decode())
    except Exception:
        continue
    if pid not in h:
        continue
    st = h[pid].get('status', {})
    if st.get('status_str') == 'error':
        for m in st.get('messages', []):
            if m[0] == 'execution_error':
                nt = m[1].get('node_type')
                em = m[1].get('exception_message', '')
                print('\nERROR @%s  (%d 秒)' % (nt, time.time() - t0))
                print('   ', em[:400])
                if 'header too small' in em or 'not fully covered' in em or 'deserializ' in em:
                    print('\n=> 文件残缺 ✘（必须重下）')
                else:
                    print('\n=> 报错与文件完整性无关 → 模型文件是好的 ✔')
        break
    print('\n跑通了 ✔  一体化 flux1-dev-fp8 完好可用（%.0f 秒）' % (time.time() - t0))
    outs = h[pid].get('outputs', {})
    for nid, o in outs.items():
        for im in o.get('images', []):
            print('   产物:', im.get('filename'))
    break
