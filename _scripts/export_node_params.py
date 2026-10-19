# -*- coding: utf-8 -*-
"""把「夜市百相簿-主工作流」的节点参数完整导成 Markdown，供人工核对。

数据源：_wf/_server_now.json。默认读取已有快照，可能落后于线上；
只有 --fetch 会先刷新。导出到 docs/generated/，仅供核对，不作为执行指令。

用法：
    python export_node_params.py                 # 用已有快照
    python export_node_params.py --fetch         # 先拉一次服务器现版再导
"""
import io
import json
import os
import ssl
import sys
from datetime import datetime, timedelta, timezone
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
WFDIR = os.path.join(HERE, '_wf')
SNAP = os.path.join(WFDIR, '_server_now.json')
NAME = '夜市百相簿-主工作流.json'
OUTDIR = os.path.join(os.path.dirname(HERE), 'docs', 'generated')
BEIJING = timezone(timedelta(hours=8))

B = os.environ.get('COMFY_BASE', '').rstrip('/')
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

GROUP = None
for _i, _a in enumerate(sys.argv):
    if _a == '--group' and _i + 1 < len(sys.argv):
        GROUP = sys.argv[_i + 1]

if '--fetch' in sys.argv:
    if not B:
        print('★ 需要 COMFY_BASE 环境变量')
        sys.exit(1)
    u = '/api/userdata/workflows%2F' + urllib.parse.quote(NAME)
    raw = urllib.request.urlopen(urllib.request.Request(B + u, method='GET'),
                                timeout=120, context=ctx).read()
    io.open(SNAP, 'wb').write(raw)
    print('已刷新快照 →', SNAP)

wf = json.load(io.open(SNAP, encoding='utf-8'))
exported_at = datetime.now(BEIJING)
nodes = wf['nodes']
byid = {n['id']: n for n in nodes}
L = wf['links']

# link = [id, from_node, from_slot, to_node, to_slot, type]
link_by_id = {l[0]: l for l in L}


def out_slot_name(node, slot):
    outs = node.get('outputs') or []
    return outs[slot]['name'] if 0 <= slot < len(outs) else 'out%d' % slot


def in_src_desc(nid, slot):
    """某个输入端口的上游是谁。"""
    n = byid[nid]
    inp = None
    for s in (n.get('inputs') or []):
        # 输入端口按声明顺序，但槽位号要用真实 index
        pass
    ins = n.get('inputs') or []
    if slot < len(ins):
        inp = ins[slot]
    if not inp or not inp.get('link'):
        # 兜底：按 link 表找
        for l in L:
            if l[3] == nid and l[4] == slot:
                f = byid.get(l[1])
                if f:
                    return '%s(#%s).%s' % (f.get('title') or f['type'], f['id'], out_slot_name(f, l[2]))
        return None
    l = link_by_id.get(inp['link'])
    if not l:
        return None
    f = byid.get(l[1])
    if not f:
        return None
    return '%s(#%s).%s' % (f.get('title') or f['type'], f['id'], out_slot_name(f, l[2]))


def out_dest(nid):
    n = byid[nid]
    res = []
    for i, o in enumerate(n.get('outputs') or []):
        ds = []
        for lid in (o.get('links') or []):
            l = link_by_id.get(lid)
            if not l:
                continue
            t = byid.get(l[3])
            if not t:
                continue
            ds.append('#%s %s' % (t['id'], t.get('title') or t['type']))
        if ds:
            res.append('%s → %s' % (o['name'], ', '.join(ds)))
    return res


def wv(n):
    w = n.get('widgets_values')
    if w is None or w == []:
        return None
    return w


# ---------------------------------------------------------------- 分组归属
def group_of(n):
    for g in wf.get('groups', []):
        x, y, w, h = g['bounding']
        if x <= n['pos'][0] <= x + w and y <= n['pos'][1] <= y + h:
            return g['title']
    return '（不属于任何分组）'


_all_titles = [g['title'] for g in wf.get('groups', [])]
groups_order = [t for t in _all_titles if GROUP in t] if GROUP else _all_titles
buckets = {t: [] for t in _all_titles}
buckets['（不属于任何分组）'] = []
for n in nodes:
    buckets[group_of(n)].append(n)

LINES = []
A = LINES.append

MODE = {0: '正常', 2: '静音(mute)', 4: '旁路(bypass)'}

A('# 夜市百相簿-主工作流 · 节点参数快照')
A('')
A('> 导出时间：%s（北京时间）' % exported_at.strftime('%Y-%m-%d %H:%M:%S'))
A('> 工作流 id：`%s`' % wf.get('id'))
A('> 规模：**节点 %d · 连线 %d · 分组 %d · 输出节点 %d**'
  % (len(nodes), len(L), len(wf.get('groups', [])),
     len([n for n in nodes if n['type'] == 'SaveImage'])))
A('> 数据来源：本地快照 `_scripts/_wf/_server_now.json`；%s。'
  % ('本次已通过 --fetch 从服务器刷新' if '--fetch' in sys.argv else '本次未联网刷新，不代表线上现状'))
A('> 快照文件修改时间：%s（北京时间；不等于服务器保存时间）'
  % datetime.fromtimestamp(os.path.getmtime(SNAP), BEIJING).strftime('%Y-%m-%d %H:%M:%S'))
if GROUP:
    A('> 分组筛选：`%s`（标题包含该文字的分组）' % GROUP)
A('> 本文件只记录快照数据，不作为当前方案或运行指令。有效决定见 [decisions](../decisions.md)，流程见 [workflow](../workflow.md)，进度见 [roadmap](../roadmap.md)。')
A('')
A('---')
A('')

# ---- 输出总览
A('## 〇、所选分组内的输出节点')
A('')
A('| # | 输出名 | 状态 | 所属组 |')
A('|---|---|---|---|')
for n in nodes:
    if n['type'] == 'SaveImage' and group_of(n) in groups_order:
        w = wv(n) or ['?']
        A('| %s | `%s` | %s | %s |' % (n['id'], w[0], MODE.get(n.get('mode', 0), n.get('mode')), group_of(n)))
A('')
A('> 实际执行范围取决于提交的输出及其依赖；运行前按当前流程核对。')
A('')

# ---- 按实际连线拓扑排序
ADJ = {}
for _n in nodes:
    ADJ.setdefault(_n['id'], [])
for _l in L:
    ADJ.setdefault(_l[1], []).append(_l[3])


def topo_order(ns):
    ids = {n['id'] for n in ns}
    deg = {i: 0 for i in ids}
    for _l in L:
        if _l[1] in ids and _l[3] in ids and _l[1] != _l[3]:
            deg[_l[3]] = deg.get(_l[3], 0) + 1
    q = [i for i in ids if deg[i] == 0]
    q.sort(key=lambda i: (byid[i]['pos'][1], byid[i]['pos'][0]))
    out = []
    while q:
        i = q.pop(0)
        out.append(byid[i])
        for j in ADJ.get(i, []):
            if j in deg:
                deg[j] -= 1
                if deg[j] == 0:
                    q.append(j)
                    q.sort(key=lambda k: (byid[k]['pos'][1], byid[k]['pos'][0]))
    seen = {n['id'] for n in out}
    out += [n for n in sorted(ns, key=lambda n: (n['pos'][1], n['pos'][0])) if n['id'] not in seen]
    return out


# ---- 逐组
sec = 0
for t in groups_order:
    sec += 1
    ns = buckets[t]
    ns = topo_order(buckets[t])
    A('---')
    A('')
    A('## %d、%s' % (sec, t))
    A('')
    A('节点 **%d** 个。' % len(ns))
    A('')
    for n in ns:
        title = n.get('title') or n['type']
        A('### #%s %s' % (n['id'], n['type']))
        A('')
        A('- **标题**：%s' % title)
        if n.get('mode', 0) != 0:
            A('- **状态**：`%s`' % MODE.get(n['mode'], n['mode']))
        w = wv(n)
        if w is not None:
            if n['type'] == 'CLIPTextEncode':
                A('- **文本内容**：')
                A('')
                A('  ```')
                for line in str(w[0]).split('\n'):
                    A('  ' + line)
                A('  ```')
                A('')
                if len(w) > 1:
                    A('- 其余 widget：`%s`' % json.dumps(w[1:], ensure_ascii=False))
            else:
                A('- **参数**：`%s`' % json.dumps(w, ensure_ascii=False))
        ins = n.get('inputs') or []
        conn = []
        for i, s in enumerate(ins):
            name = s.get('localized_name') or s.get('name')
            if s.get('link') or any(l[3] == n['id'] and l[4] == i for l in L):
                s2 = in_src_desc(n['id'], i)
                if s2:
                    conn.append('%s ← **%s**' % (name, s2))
        if conn:
            A('- **输入连接**：')
            for c in conn:
                A('    - %s' % c)
        else:
            A('- **输入连接**：无（起点节点）')
        od = out_dest(n['id'])
        if od:
            A('- **输出去向**：')
            for o in od:
                A('    - %s' % o)
        A('')

# ---- 未分组
left = buckets['（不属于任何分组）']
if left:
    A('---')
    A('')
    A('## 附、未归入任何分组的节点（%d）' % len(left))
    A('')
    for n in left:
        A('- `#%s` %s — %s' % (n['id'], n['type'], n.get('title') or ''))

scope = '分组' if GROUP else '主工作流'
OUT = os.path.join(OUTDIR, '夜市百相簿-%s-节点参数快照-%s.md'
                   % (scope, exported_at.strftime('%Y%m%d_%H%M%S_%f')))
os.makedirs(OUTDIR, exist_ok=True)
io.open(OUT, 'w', encoding='utf-8').write('\n'.join(LINES))
print('已导出 →', OUT)
print('行数 %d' % len(LINES))
