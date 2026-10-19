# -*- coding: utf-8 -*-
"""在「夜市百相簿-主工作流.json」里**原地追加**一个 Flux 文生图组（一体化 flux1-dev-fp8）。

★ 为什么是"原地追加"而不是跑装配器
    build_master_wf.py 会用常量把各分组**重建**一遍 —— 用户已在浏览器里改过脸部组的
    4 处提示词（7 项），一跑装配器就被冲掉。所以这里改成"读服务器现版 → 只加新节点 → 推回"，
    旧节点一个字节都不碰。

★ 为什么做两条支路（用户说"文生图"，又要"以基图为基准"）
    纯文生图**拿不到同一张脸**（2026-09-17 实证：Flux 纯文生图的脸完全不是闻灯，
    换成 img2img + 同一张基图才回到 v23 那张脸）。所以：
      支路 A = 真·文生图（EmptySD3LatentImage，不读图）
      支路 B = 以 wendeng_v23_face_base.png 为基准（VAEEncode + denoise 0.30）
    一次提交出两张，直接对比哪条能保身份。

★ Flux 参数红线（与 SDXL 完全不通用）
    cfg 必须 1.0；euler + simple；20 步；负向在 cfg=1 下 100% 失效（所以留空，
    "不要 XX" 一律改写进正向）；放大后**不做第二段重绘**（B.7 实证：Flux 的二段重绘只抹细节）。

用法：
    python add_flux_group.py            # 只生成本地 JSON，不联网
    python add_flux_group.py --push     # 备份 → 推送（换新 id 绕过浏览器缓存）→ 回读校验
"""
import copy
import io
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
WFDIR = os.path.join(HERE, '_wf')
NAME = '夜市百相簿-主工作流.json'
SNAP = os.path.join(WFDIR, '_server_now.json')
LOCALOUT = os.path.join(WFDIR, '夜市百相簿_主工作流.json')

B = os.environ.get(
    'COMFY_BASE',
    'https://gw-efb56d453d484597a1b8ddfc86156262.cn-beijing.aigclinks.com:8016').rstrip('/')
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

PUSH = '--push' in sys.argv

GROUP_TITLE = '【闻灯】Flux 文生图 · 一体化 fp8（+ v23 基图 基准对照）'
CKPT = 'FLUX1\\flux1-dev-fp8.safetensors'
UPSCALE = '4x-UltraSharp (1).pth'
BASE_IMG = 'wendeng_v23_face_base.png'

SEED = 20260920
W, H = 1024, 1280
STEPS = 20
CFG = 1.0
GUIDANCE = 3.5
D_T2I = 1.0        # 纯文生图
D_IMG = 0.30       # 以基图为基准（identity 来自基图，不是底模）

# Flux 用 T5，吃长句、不吃 tag 堆叠；"不要 XX" 一律写成正向的 dry/matte/flyaway
FLUX_POS = (
    'photorealistic portrait photograph, front view, looking at viewer, face closeup, '
    'head and shoulders, solo, 1boy, a 24 year old young adult East Asian man, '
    'youthful masculine face, defined but youthful jawline, '
    'messy wavy black hair with individual flyaway strands, '
    'small dark mole at the outer corner of his right eye, '
    'tired but young eyes, slightly heavy eyelids, faint under-eye shadows, clean shaven face, '
    'natural skin texture with visible pores and subtle skin imperfections, matte dry skin, '
    'faded blue shirt collar, dark worn coat collar, pure white background, '
    'soft even studio lighting, subtle facial shadows, sharp focus, '
    '35mm film photograph, fine film grain'
)
FLUX_NEG = ''      # cfg=1 → 负向通道关闭，写什么都没用，留空

# ---------------------------------------------------------------- 载入服务器现版
wf = json.load(io.open(SNAP, encoding='utf-8'))
print('现版：%s  id=%s  节点%d 链接%d 分组%d'
      % (NAME, wf.get('id'), len(wf['nodes']), len(wf['links']), len(wf.get('groups', []))))

for g in wf.get('groups', []):
    if 'Flux 文生图' in g.get('title', ''):
        print('★ 已存在同名分组（%s）—— 防重入，退出。' % g['title'])
        sys.exit(0)

tpl = {}
for n in wf['nodes']:
    tpl.setdefault(n['type'], n)

NEED = ['CheckpointLoaderSimple', 'CLIPTextEncode', 'KSampler', 'VAEDecode', 'SaveImage',
        'ImageUpscaleWithModel', 'UpscaleModelLoader', 'LoadImage', 'VAEEncode']
missing = [t for t in NEED if t not in tpl]
if missing:
    print('⚠️ 现有工作流里没有这些类型的模板（脚本会用手工结构）：', missing)


def mk(t, nid, pos, size, wv, in_links=None, out_links=None, title=None):
    """克隆同类型现有节点做模板，只改 id / 位置 / widget / 连线。"""
    if t in tpl:
        n = copy.deepcopy(tpl[t])
    else:                                   # 兜底：手工结构（FluxGuidance / EmptySD3LatentImage）
        n = {'type': t, 'flags': {}, 'mode': 0,
             'properties': {'Node name for S&R': t}, 'inputs': [], 'outputs': []}
    n['id'] = nid
    n['pos'] = list(pos)
    n['size'] = list(size)
    n['mode'] = 0
    n.pop('title', None)
    if title:
        n['title'] = title
    n['flags'] = {}
    for s in n.get('inputs', []) or []:
        s['link'] = (in_links or {}).get(s['name'])
    for i, s in enumerate(n.get('outputs', []) or []):
        s['links'] = list((out_links or {}).get(s['name'], []))
        s['slot_index'] = i
    if wv is not None:
        n['widgets_values'] = list(wv)
    return n


# 手工结构（模板里没有的类型）
MANUAL = {
    'FluxGuidance': {
        'inputs': [{'name': 'conditioning', 'type': 'CONDITIONING', 'link': None}],
        'outputs': [{'name': 'CONDITIONING', 'type': 'CONDITIONING', 'links': [], 'slot_index': 0}],
        'size': [315, 58],
    },
    'EmptySD3LatentImage': {
        'inputs': [],
        'outputs': [{'name': 'LATENT', 'type': 'LATENT', 'links': [], 'slot_index': 0}],
        'size': [315, 106],
    },
}
for t, d in MANUAL.items():
    if t not in tpl:
        n = {'type': t, 'flags': {}, 'mode': 0, 'properties': {'Node name for S&R': t},
             'inputs': copy.deepcopy(d['inputs']), 'outputs': copy.deepcopy(d['outputs'])}
        tpl[t] = n

# ---------------------------------------------------------------- 节点与连线
# (link_id, from_id, from_slot, to_id, to_slot, type)
LINKS = [
    (2001, 1100, 0, 1111, 0, 'MODEL'),
    (2002, 1100, 0, 1122, 0, 'MODEL'),
    (2003, 1100, 1, 1101, 0, 'CLIP'),
    (2004, 1100, 1, 1102, 0, 'CLIP'),
    (2005, 1100, 2, 1112, 1, 'VAE'),
    (2006, 1100, 2, 1123, 1, 'VAE'),
    (2007, 1100, 2, 1121, 1, 'VAE'),
    (2008, 1101, 0, 1103, 0, 'CONDITIONING'),
    (2009, 1103, 0, 1111, 1, 'CONDITIONING'),
    (2010, 1103, 0, 1122, 1, 'CONDITIONING'),
    (2011, 1102, 0, 1111, 2, 'CONDITIONING'),
    (2012, 1102, 0, 1122, 2, 'CONDITIONING'),
    (2013, 1110, 0, 1111, 3, 'LATENT'),
    (2014, 1120, 0, 1121, 0, 'IMAGE'),
    (2015, 1121, 0, 1122, 3, 'LATENT'),
    (2016, 1111, 0, 1112, 0, 'LATENT'),
    (2017, 1122, 0, 1123, 0, 'LATENT'),
    (2018, 1112, 0, 1113, 0, 'IMAGE'),
    (2019, 1112, 0, 1114, 1, 'IMAGE'),
    (2020, 1114, 0, 1115, 0, 'IMAGE'),
    (2021, 1123, 0, 1124, 0, 'IMAGE'),
    (2022, 1123, 0, 1125, 1, 'IMAGE'),
    (2023, 1125, 0, 1126, 0, 'IMAGE'),
    (2024, 1127, 0, 1114, 0, 'UPSCALE_MODEL'),
    (2025, 1127, 0, 1125, 0, 'UPSCALE_MODEL'),
]


def links_to(nid, name):
    return [l[0] for l in LINKS if l[3] == nid and true_slot(nid, name) == l[4]]


NODE_PORTS = {
    # id: {input_name: slot, output_name: slot}
    1100: ({}, {'MODEL': 0, 'CLIP': 1, 'VAE': 2}),
    1101: ({'clip': 0}, {'CONDITIONING': 0}),
    1102: ({'clip': 0}, {'CONDITIONING': 0}),
    1103: ({'conditioning': 0}, {'CONDITIONING': 0}),
    1110: ({}, {'LATENT': 0}),
    1111: ({'model': 0, 'positive': 1, 'negative': 2, 'latent_image': 3}, {'LATENT': 0}),
    1112: ({'samples': 0, 'vae': 1}, {'IMAGE': 0}),
    1113: ({'images': 0}, {'images': 0}),
    1114: ({'upscale_model': 0, 'image': 1}, {'IMAGE': 0}),
    1115: ({'images': 0}, {'images': 0}),
    1120: ({}, {'IMAGE': 0, 'MASK': 1}),
    1121: ({'pixels': 0, 'vae': 1}, {'LATENT': 0}),
    1122: ({'model': 0, 'positive': 1, 'negative': 2, 'latent_image': 3}, {'LATENT': 0}),
    1123: ({'samples': 0, 'vae': 1}, {'IMAGE': 0}),
    1124: ({'images': 0}, {'images': 0}),
    1125: ({'upscale_model': 0, 'image': 1}, {'IMAGE': 0}),
    1126: ({'images': 0}, {'images': 0}),
    1127: ({}, {'UPSCALE_MODEL': 0}),
}


def true_slot(nid, name):
    return NODE_PORTS[nid][0].get(name)


def in_map(nid):
    m = {}
    for l in LINKS:
        if l[3] == nid:
            m[l[4]] = l[0]
    # 转成 {端口名: link}
    names = {v: k for k, v in NODE_PORTS[nid][0].items()}
    return {names[slot]: lid for slot, lid in m.items() if slot in names}


def out_map(nid):
    m = {}
    for l in LINKS:
        if l[1] == nid:
            m.setdefault(l[2], []).append(l[0])
    names = {v: k for k, v in NODE_PORTS[nid][1].items()}
    return {names[slot]: lids for slot, lids in m.items() if slot in names}


NEW = [
    mk('CheckpointLoaderSimple', 1100, (7640, 320), [315, 98], [CKPT],
       in_map(1100), out_map(1100), 'Flux 一体化 fp8（UNET+CLIP+VAE 都在里面）'),
    mk('UpscaleModelLoader', 1127, (7640, 470), [315, 58], [UPSCALE],
       in_map(1127), out_map(1127), '4x 放大（放大后不做二段重绘）'),
    mk('LoadImage', 1120, (7640, 590), [315, 314], [BASE_IMG, 'image'],
       in_map(1120), out_map(1120), '基准图 = wendeng_v23_face_base.png'),
    mk('CLIPTextEncode', 1101, (8000, 320), [430, 320], [FLUX_POS],
       in_map(1101), out_map(1101), 'Flux 正向（长句，否定词一律写成正面短语）'),
    mk('CLIPTextEncode', 1102, (8000, 700), [430, 120], [FLUX_NEG],
       in_map(1102), out_map(1102), '负向（cfg=1 → 通道关闭，留空）'),
    mk('FluxGuidance', 1103, (8470, 320), [315, 58], [GUIDANCE],
       in_map(1103), out_map(1103), 'FluxGuidance'),
    mk('EmptySD3LatentImage', 1110, (8470, 430), [315, 106], [W, H, 1],
       in_map(1110), out_map(1110), '空 latent（16 通道）'),
    mk('VAEEncode', 1121, (8470, 600), [210, 46], None,
       in_map(1121), out_map(1121), '把基图编码成 latent（这就是"以基图为基准"）'),
    mk('KSampler', 1111, (8830, 300), [315, 262], [SEED, 'fixed', STEPS, CFG, 'euler', 'simple', D_T2I],
       in_map(1111), out_map(1111), 'A 纯文生图'),
    mk('KSampler', 1122, (8830, 620), [315, 262], [SEED, 'fixed', STEPS, CFG, 'euler', 'simple', D_IMG],
       in_map(1122), out_map(1122), 'B 以基图为基准'),
    mk('VAEDecode', 1112, (9190, 300), [210, 46], None, in_map(1112), out_map(1112)),
    mk('VAEDecode', 1123, (9190, 600), [210, 46], None, in_map(1123), out_map(1123)),
    mk('ImageUpscaleWithModel', 1114, (9440, 300), [315, 46], None, in_map(1114), out_map(1114)),
    mk('ImageUpscaleWithModel', 1125, (9440, 600), [315, 46], None, in_map(1125), out_map(1125)),
    mk('SaveImage', 1113, (9800, 260), [400, 500], ['闻灯Flux文生图-草稿'],
       in_map(1113), out_map(1113)),
    mk('SaveImage', 1115, (9800, 790), [400, 500], ['闻灯Flux文生图-成品'],
       in_map(1115), out_map(1115)),
    mk('SaveImage', 1124, (10250, 260), [400, 500], ['闻灯Flux基准-草稿'],
       in_map(1124), out_map(1124)),
    mk('SaveImage', 1126, (10250, 790), [400, 500], ['闻灯Flux基准-成品'],
       in_map(1126), out_map(1126)),
]

# 组框（照抄现有组的字段集合）
gt = copy.deepcopy(wf['groups'][0])
gt['title'] = GROUP_TITLE
gt['bounding'] = [7600, 250, 3120, 1060]

wf['nodes'].extend(NEW)
wf['links'].extend([list(l) for l in LINKS])
wf['groups'] = list(wf.get('groups', [])) + [gt]
wf['last_node_id'] = max([wf.get('last_node_id', 0)] + [n['id'] for n in NEW])
wf['last_link_id'] = max([wf.get('last_link_id', 0)] + [l[0] for l in LINKS])
wf['id'] = str(uuid.uuid4())

print('\n追加 %d 个节点 / %d 条连线 / 1 个分组' % (len(NEW), len(LINKS)))
print('现共：节点 %d  链接 %d  分组 %d   新 id = %s'
      % (len(wf['nodes']), len(wf['links']), len(wf['groups']), wf['id']))

# ---------------------------------------------------------------- 本地自检
from wf_api import build_api, deps, find_outputs, WIDGETS   # noqa: E402

api, titles = build_api(wf)
unsup = sorted({n['type'] for n in wf['nodes'] if n['type'] not in WIDGETS})
print('\n--- 本地自检 ---')
print('可转换节点 %d / %d' % (len(api), len(wf['nodes'])))
if unsup:
    print('⚠️ 未登记类型（会被静默跳过）：%s' % unsup)
else:
    print('节点类型登记 ✔ 全部可转换')

for tok, kind in [('闻灯Flux文生图', '草稿'), ('闻灯Flux文生图', '成品'),
                  ('闻灯Flux基准', '草稿'), ('闻灯Flux基准', '成品')]:
    hits = find_outputs(api, tok, kind)
    print('  %-16s %-4s → %s' % (tok, kind, [h[1] for h in hits]))

bad = 0
for tok, kind in [('闻灯Flux', '草稿'), ('闻灯Flux', '成品')]:
    for nid, pfx in find_outputs(api, tok, kind):
        keep = deps(api, [nid])
        names = {api[k]['class_type'] for k in keep}
        need = {'CheckpointLoaderSimple', 'KSampler', 'VAEDecode', 'SaveImage'}
        if not need <= names:
            print('  ★ 断链：%s 缺 %s' % (pfx, need - names))
            bad += 1
        else:
            print('  ✔ %-22s 依赖链 %d 个节点完整' % (pfx, len(keep)))
        if 'VAEEncode' in names:
            print('        基图 =', [api[k]['inputs'].get('image') for k in keep
                                      if api[k]['class_type'] == 'LoadImage'])
if bad:
    print('\n★ 自检未通过，不推送。')
    sys.exit(1)

os.makedirs(WFDIR, exist_ok=True)
io.open(LOCALOUT, 'w', encoding='utf-8').write(json.dumps(wf, ensure_ascii=False, indent=1))
print('\n本地已写出 → %s' % LOCALOUT)

if not PUSH:
    print('\n（未加 --push，只写本地。）')
    sys.exit(0)

# ---------------------------------------------------------------- 推送
u = '/api/userdata/workflows%2F' + urllib.parse.quote(NAME)


def req(method, data=None, ctype=None, timeout=300, url=None):
    h = {}
    if ctype:
        h['Content-Type'] = ctype
    return urllib.request.urlopen(urllib.request.Request(url or (B + u), data=data, headers=h,
                                                         method=method),
                                  timeout=timeout, context=ctx).read()


print('\n--- 备份服务器现版 ---')
bak = os.path.join(WFDIR, '_backup_%s.json' % time.strftime('%m%d-%H%M%S'))
io.open(bak, 'wb').write(req('GET'))
print('  →', bak)

print('--- 推送（overwrite=true）---')
try:
    r = req('POST', json.dumps(wf, ensure_ascii=False).encode('utf-8'),
            'application/json', 600, url=B + u + '?overwrite=true')
    print('  POST ->', r[:120])
except urllib.error.HTTPError as e:
    print('  ★ 推送失败 HTTP %s: %s' % (e.code, e.read().decode('utf-8', 'replace')[:300]))
    sys.exit(1)

print('--- 回读校验 ---')
back = json.loads(req('GET'))
G = [g['title'] for g in back.get('groups', [])]
print('  服务器版 id = %s' % back.get('id'))
print('  节点 %d  链接 %d  分组 %d' % (len(back['nodes']), len(back['links']), len(back['groups'])))
print('  分组：')
for t in G:
    print('    -', t)
outs = [n['widgets_values'][0] for n in back['nodes']
        if n['type'] == 'SaveImage' and n.get('widgets_values')]
print('  输出共 %d 个：%s' % (len(outs), outs))
new = [o for o in outs if o.startswith('闻灯Flux')]
print('  新增 Flux 输出 %d 个 ✔' % len(new) if len(new) == 4 else '  ★ 新增输出数量不对！')
print('\n跑图命令：')
print('  python run_wf.py "%s" "闻灯Flux" draft   (草稿 ×2)' % NAME)
print('  python run_wf.py "%s" "闻灯Flux" final   (成品 ×2)' % NAME)
