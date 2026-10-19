# -*- coding: utf-8 -*-
"""远程 ComfyUI 开机探测（只读，不烧额外成本）。

用法（每次开机网关 hash 都会变，必须传新的）：
    COMFY_BASE=https://gw-xxxx.cn-beijing.aigclinks.com:8016 python probe_server.py
"""
import os
import json
import ssl
import urllib.request
import urllib.error
import urllib.parse

B = os.environ.get(
    'COMFY_BASE',
    'https://gw-efb56d453d484597a1b8ddfc86156262.cn-beijing.aigclinks.com:8016'
).rstrip('/')

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def get(path, timeout=60):
    try:
        r = urllib.request.urlopen(B + path, timeout=timeout, context=ctx)
        return r.status, r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')[:300]
    except Exception as e:
        return None, '%s: %s' % (type(e).__name__, str(e)[:120])


def head(t):
    print('\n' + '=' * 62)
    print(t)
    print('=' * 62)


head('BASE = ' + B)

s, b = get('/', 30)
print('GET /             -> %s  %s' % (s, (b[:70].replace('\n', ' ') if isinstance(b, str) else b)))

s, b = get('/system_stats', 60)
print('GET /system_stats -> %s' % s)
if s == 200:
    try:
        for k, v in json.loads(b).items():
            print('    %-14s %s' % (k, json.dumps(v, ensure_ascii=False)[:240]))
    except Exception:
        print('   ', b[:260])

s, b = get('/queue', 60)
print('GET /queue        -> %s  %s' % (s, (b[:180].replace('\n', ' ') if isinstance(b, str) else b)))

s, b = get('/api/userdata?dir=workflows', 60)
print('GET workflows     -> %s' % s)
if s == 200:
    try:
        arr = json.loads(b)
        arr = json.loads(arr) if isinstance(arr, str) else arr
        for x in arr:
            print('     ', x)
    except Exception:
        print('   ', b[:400])

head('模型目录')
DIRS = ['checkpoints', 'checkpoints/FLUX1', 'diffusion_models', 'diffusion_models/FLUX1',
        'vae', 'vae/FLUX1', 'text_encoders', 'text_encoders/t5',
        'upscale_models', 'loras', 'unet']
for d in DIRS:
    got, code = None, None
    for p in ('/experiment/models/' + urllib.parse.quote(d),
              '/models/' + urllib.parse.quote(d)):
        s, b = get(p, 60)
        code = s
        if s == 200:
            got = b
            break
    if got is None:
        print('  %-24s <%s>' % (d, code))
        continue
    try:
        arr = json.loads(got)
        names = [x.get('name') for x in arr] if isinstance(arr, list) else arr
        print('  %-24s %s' % (d, names))
    except Exception:
        print('  %-24s %s' % (d, got[:200]))

print('\n完成。')
