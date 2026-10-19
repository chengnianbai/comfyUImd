# -*- coding: utf-8 -*-
"""部署前独立复核 + 服务器现版对账（只读，不改任何东西）。"""
import io
import json
import os
import shutil
import ssl
import urllib.request

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_wf')
BASE = os.environ.get(
    'COMFY_BASE',
    'https://gw-efb56d453d484597a1b8ddfc86156262.cn-beijing.aigclinks.com:8016').rstrip('/')
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

NEWP = os.path.join(W, '夜市百相簿_主工作流.json')
PRIOR = os.path.join(W, '_server_live.json')          # 16:43 拉的 = 我上次推上去的 130 节点版
PRIOR_KEEP = os.path.join(W, '_prior_push_130.json')

print('=' * 72)
print('一、本地新成品独立复核')
print('=' * 72)
d = json.load(io.open(NEWP, encoding='utf-8'))
ns = {n['id']: n for n in d['nodes']}
print('成品：%d 节点 / %d 链接 / %d 分组  id=%s' % (len(d['nodes']), len(d['links']), len(d['groups']), d.get('id')))

# 1. 被删节点确实不存在
gone = [1120, 1302, 1121, 1122, 1123, 1124, 1125, 1126, 1306, 1307, 1308, 1309,
        1410, 1411, 1412, 1413, 1414, 1415, 1416, 1417, 1418]
left = [i for i in gone if i in ns]
print('\n[1] 应删除的 v23/IMG 节点残留：%s' % (left or '无 ✔'))

# 2. 悬空/孤儿/槽位/环
declared, actual = set(), set(l[0] for l in d['links'])
for n in d['nodes']:
    for o in (n.get('outputs') or []):
        for l in (o.get('links') or []):
            declared.add(l)
    for i in (n.get('inputs') or []):
        if i.get('link') is not None:
            declared.add(i['link'])
mis = []
for l in d['links']:
    lid, f, fs, t, ts, ty = l
    fo = ns[f].get('outputs') or []
    ti = ns[t].get('inputs') or []
    if fs >= len(fo) or lid not in (fo[fs].get('links') or []):
        mis.append(l)
    if ts >= len(ti) or ti[ts].get('link') != lid:
        mis.append(l)
print('[2] 悬空:%s 孤儿:%s 槽位不一致:%d' % (sorted(declared - actual) or '无',
                                      sorted(actual - declared) or '无', len(mis)))
adj = {}
for l in d['links']:
    adj.setdefault(l[1], []).append(l[3])
col = {n['id']: 0 for n in d['nodes']}
cyc = []
for s in list(col):
    if col[s]:
        continue
    st = [(s, iter(adj.get(s, [])))]
    col[s] = 1
    while st:
        nd, it = st[-1]
        nx = next(it, None)
        if nx is None:
            col[nd] = 2
            st.pop()
            continue
        if col.get(nx, 0) == 1:
            cyc.append((nd, nx))
        elif col.get(nx, 0) == 0:
            col[nx] = 1
            st.append((nx, iter(adj.get(nx, []))))
print('    环:%s' % (cyc or '无 ✔'))

# 3. G3 组内所有节点（给用户看的新结构）
print('\n[3] G3 组内节点（按类型统计）：')
g3 = [n for n in d['nodes'] if n['pos'][0] >= 7500]
from collections import Counter
print('    %d 个节点：%s' % (len(g3), dict(Counter(n['type'] for n in g3))))
print('    LoadImage/LoadImageOutput：%s' % [n['id'] for n in g3 if n['type'] in ('LoadImage', 'LoadImageOutput')] or '0 个 ✔')

# 4. 输出清单
print('\n[4] 全部 SaveImage（含 mode）：')
for n in sorted([x for x in d['nodes'] if x['type'] == 'SaveImage'], key=lambda x: x['id']):
    print('    %-6s mode=%-3s %s' % (n['id'], n.get('mode'), n['widgets_values'][0]))

# 5. 身份锁三视角的关键参数
print('\n[5] 身份锁三视角采样器：')
for nid, lab in ((1313, '正脸'), (1323, '右脸'), (1333, '左脸')):
    n = ns[nid]
    print('    %-6s %-4s latent←%-6s wv=%s  | %s'
          % (nid, lab, [i.get('link') for i in n['inputs']][3], n['widgets_values'], n.get('title')))
print('\n[6] 三视角表现层提示词首句：')
for nid, lab in ((1310, '正脸'), (1320, '右脸'), (1330, '左脸')):
    t = ns[nid]['widgets_values'][0]
    print('    %-4s %s' % (lab, t[:150]))

print()
print('=' * 72)
print('二、服务器现版对账（确认无人手改，重建覆盖才安全）')
print('=' * 72)
u = BASE + '/api/userdata/workflows%2F' + urllib.parse.quote('夜市百相簿-主工作流.json')
live = json.loads(urllib.request.urlopen(u, timeout=90, context=ctx).read().decode('utf-8'))
io.open(os.path.join(W, '_server_live_new.json'), 'w', encoding='utf-8').write(
    json.dumps(live, ensure_ascii=False))
print('服务器现版：%d 节点 / %d 链接 / %d 分组  id=%s'
      % (len(live['nodes']), len(live['links']), len(live['groups']), live.get('id')))

if os.path.exists(PRIOR):
    shutil.copy2(PRIOR, PRIOR_KEEP)
    p = json.load(io.open(PRIOR_KEEP, encoding='utf-8'))
    print('对账基准（我上次推上去的）：%d 节点 / %d 链接  id=%s'
          % (len(p['nodes']), len(p['links']), p.get('id')))
    a = {n['id']: json.dumps(n, sort_keys=True, ensure_ascii=False) for n in live['nodes']}
    b = {n['id']: json.dumps(n, sort_keys=True, ensure_ascii=False) for n in p['nodes']}
    print('  只在服务器:', sorted(set(a) - set(b)))
    print('  只在基准  :', sorted(set(b) - set(a)))
    diff = [i for i in sorted(set(a) & set(b)) if a[i] != b[i]]
    print('  内容不同的节点:', diff or '无 ✔')
    print('  links 一致:', json.dumps(live['links'], sort_keys=True) == json.dumps(p['links'], sort_keys=True))
    same = (not (set(a) ^ set(b))) and not diff
    print('\n  → %s' % ('服务器 == 我上次推的版本，无人手改，重建覆盖安全 ✔' if same
                        else '★ 有差异！先查清再推。'))
