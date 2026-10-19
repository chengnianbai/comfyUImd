# -*- coding: utf-8 -*-
"""回读服务器实际存储版本（自己拉，不吃缓存文件），验证 v23 已从本组彻底移除。"""
import io
import json
import os
import ssl
import urllib.parse
import urllib.request

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_wf')
BASE = os.environ.get(
    'COMFY_BASE',
    'https://gw-efb56d453d484597a1b8ddfc86156262.cn-beijing.aigclinks.com:8016').rstrip('/')
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

u = BASE + '/api/userdata/workflows%2F' + urllib.parse.quote('夜市百相簿-主工作流.json')
d = json.loads(urllib.request.urlopen(u, timeout=90, context=ctx).read().decode('utf-8'))
io.open(os.path.join(W, '_server_live.json'), 'w', encoding='utf-8').write(
    json.dumps(d, ensure_ascii=False))
ns = {n['id']: n for n in d['nodes']}

print('服务器实际存储：%d 节点 / %d 链接 / %d 分组   id=%s'
      % (len(d['nodes']), len(d['links']), len(d['groups']), d.get('id')))
print()

print('=== ① 本组（x>=7500）内还有没有 LoadImage ===')
g3 = [n for n in d['nodes'] if n['pos'][0] >= 7500]
bad = [n for n in g3 if n['type'] in ('LoadImage', 'LoadImageOutput')]
print('   %s' % ([(n['id'], n['widgets_values'][0]) for n in bad]
                 if bad else '0 个 ✔ —— 本组画布上已无任何外部图片节点'))
print()

print('=== ② 全工作流仍引用 wendeng_v23_face_base.png 的节点 ===')
hit = [n for n in sorted(d['nodes'], key=lambda x: x['id'])
       if n['type'] in ('LoadImage', 'LoadImageOutput') and n.get('widgets_values')
       and 'wendeng_v23' in str(n['widgets_values'][0])]
for n in hit:
    print('   id=%-6s x=%-6.0f mode=%-3s %-30s | %s'
          % (n['id'], n['pos'][0], n.get('mode'), n['widgets_values'][0], n.get('title')))
print('   （以上若只剩 x≈3080 的两条，就是「脸部 SDXL 组」G1 的旧链路，不属于本次范围）')
print()

print('=== ③ 应删除的节点是否真的没了 ===')
gone = [1120, 1302, 1121, 1122, 1123, 1124, 1125, 1126, 1306, 1307, 1308, 1309,
        1410, 1411, 1412, 1413, 1414, 1415, 1416, 1417, 1418]
print('   残留：%s' % ([i for i in gone if i in ns] or '无 ✔'))
print()

print('=== ④ 新结构：身份锁三视角（latent 来源必须都是 1305 共用结构锚）===')
for nid, lab in ((1313, '正脸'), (1323, '右脸'), (1333, '左脸')):
    if nid not in ns:
        print('   ★ %s %s 不存在！' % (nid, lab))
        continue
    n = ns[nid]
    ins = {i['name']: i.get('link') for i in n['inputs']}
    print('   %-6s %-4s latent←L%-6s positive←L%-6s model←L%-6s  wv=%s'
          % (nid, lab, ins['latent_image'], ins['positive'], ins['model'], n['widgets_values']))
print()

print('=== ⑤ 本组输出（8 条）===')
for n in sorted([x for x in d['nodes'] if x['type'] == 'SaveImage' and x['pos'][0] >= 7500],
                key=lambda x: x['id']):
    print('   %-6s mode=%-3s %s' % (n['id'], n.get('mode'), n['widgets_values'][0]))
