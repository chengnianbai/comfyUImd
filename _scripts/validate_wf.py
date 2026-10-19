# -*- coding: utf-8 -*-
"""静态校验 ComfyUI 工作流：节点连线完整性 + 提取提示词供 token 复核。
不提交任何任务，纯静态检查。"""
import json, os, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

WF = r'D:\xiaobai-claude code\ComfyUI\user\default\workflows\夜市百相簿.json'
OUT = r'C:\Users\Administrator\WorkBuddy\2026-09-15-16-33-24\_scripts\prompts_from_wf.json'

j = json.load(open(WF, encoding='utf-8'))
nodes = {n['id']: n for n in j['nodes']}
print('节点数 =', len(j['nodes']), ' 连线数 =', len(j['links']))

# --- 1. 连线完整性 ---
errs = []
out_slots = {}   # (node_id, slot_index) -> 已连出的 link id 列表
for n in j['nodes']:
    for i, o in enumerate(n.get('outputs', [])):
        out_slots[(n['id'], i)] = list(o.get('links') or [])

for l in j['links']:
    lid, src, sslot, dst, dslot, typ = l[0], l[1], l[2], l[3], l[4], l[5]
    if src not in nodes:
        errs.append('link %s: 源节点 %s 不存在' % (lid, src)); continue
    if dst not in nodes:
        errs.append('link %s: 目标节点 %s 不存在' % (lid, dst)); continue
    sn, dn = nodes[src], nodes[dst]
    if sslot >= len(sn.get('outputs', [])):
        errs.append('link %s: 源 %s 输出槽 %s 越界' % (lid, src, sslot))
    if dslot >= len(dn.get('inputs', [])):
        errs.append('link %s: 目标 %s 输入槽 %s 越界' % (lid, dst, dslot))
    # 反向引用检查
    if lid not in out_slots.get((src, sslot), []):
        errs.append('link %s: 节点 %s 输出槽 %s 里没有反向记录' % (lid, src, sslot))

# --- 2. 每个必填输入是否都有线 ---
must = {
    'KSampler': ['model', 'positive', 'negative', 'latent_image'],
    'VAEDecode': ['samples', 'vae'],
    'LatentUpscale': ['samples'],
    'ConditioningCombine': ['conditioning_1', 'conditioning_2'],
    'CLIPTextEncode': ['clip'],
    'PreviewImage': ['images'],
    'SaveImage': ['images'],
}
for n in j['nodes']:
    t = n.get('type')
    if t in must:
        for name in must[t]:
            inp = next((x for x in n.get('inputs', []) if x['name'] == name), None)
            if inp is None:
                errs.append('%s(id=%s) 缺少输入定义 %s' % (t, n['id'], name))
            elif not inp.get('link'):
                errs.append('%s(id=%s) 的输入 %s 没有连线' % (t, n['id'], name))

print('连线检查：', '全部通过 ✔' if not errs else '发现 %d 个问题' % len(errs))
for e in errs:
    print('   ✗', e)

# --- 3. 关键参数摘要 ---
print('\n--- 关键参数 ---')
for n in j['nodes']:
    t = n.get('type'); w = n.get('widgets_values') or []
    if t == 'KSampler':
        print('  KSampler(id=%s) seed=%s after=%s steps=%s cfg=%s denoise=%s' % (n['id'], w[0], w[1], w[2], w[3], w[6]))
    elif t == 'EmptyLatentImage':
        print('  EmptyLatentImage:', w[:2])
    elif t == 'LatentUpscale':
        print('  LatentUpscale:', w)
    elif t == 'CheckpointLoaderSimple':
        print('  Checkpoint:', w[0])
    elif t == 'SaveImage':
        print('  SaveImage prefix:', w[0])

# --- 4. 导出提示词 ---
prompts = {}
for n in j['nodes']:
    if n.get('type') == 'CLIPTextEncode':
        prompts['node%s_%s' % (n['id'], n.get('title'))] = n['widgets_values'][0]
json.dump(prompts, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('\n已导出提示词 ->', OUT)
for k, v in prompts.items():
    print('  [%s] %d 字符' % (k, len(v)))
