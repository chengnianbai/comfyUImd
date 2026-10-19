# -*- coding: utf-8 -*-
"""【闻灯】Flux 文生图组 —— 极简结构：FLUX → 正脸基准图 → 身份锁(正脸/右脸/左脸)

★ 用户最终定义的结构（2026-09-20）
      FLUX
       ↓
    闻灯正脸基准图        ← Flux 纯文生图自产，图里不含任何 v23 / SDXL 痕迹
       ↓
    身份锁 / Identity Reference
      ├─ 正脸
      ├─ 右脸
      └─ 左脸

★ 用户原话（这次）
    「我不需要基于 wendeng_v23_face_base.png 生图；现在线上的节点为什么能看到
      wendeng_v23_face_base.png 的图啊」

★ 落地做法（原地改造，不跑装配器；幂等，重跑同值）
    A. 彻底铲除 v23 依赖 —— 删除基线里的 12 个节点：
         · 1120 LoadImage(wendeng_v23_face_base.png)      「v23 身份锚」
         · 1302 LoadImage(wendeng_v23_face_base.png)      「旧 SDXL 正脸锚源」
         · 1121/1122/1123/1124/1125/1126                  「以 v23 图为基图的 d0.3 重绘」
                                                           （第二套冗余基准输出，无下游）
         · 1306 LoadImageOutput(闻灯v23-脸部侧面c-成品)     「右脸的 v23 侧面锚」
         · 1307/1308/1309                                  右脸的 v23 侧脸降采样链
       → 改造后本组内 **LoadImage 数量 = 0**（硬判据，见自检）。
    B. 上游（正脸基准图）保留「Flux 纯文生图」那一段，就是用户要的「FLUX → 基准图」：
         1100 底模(fp8) → 1101 正向 → 1103 FluxGuidance → 1110 空 latent
         1111 KSampler(d1.0) → 1112 VAEDecode
            ├─ 1113 闻灯正脸基准-草稿
            └─ 1114 4x 放大 → 1115 闻灯正脸基准-成品
    C. 下游（身份锁）改为「一个结构锚 + 三条表现层」：
         1303 ← 1112（基准图）→ 1304 → 1305 VAEEncode = 结构锚 latent（三视角共用）
            ├─ 正脸：1310 → 1311 → 1312 → 1313 d0.55 (latent←1305) → 1314 → 1315 → 1316/1317
            ├─ 右脸：1320 → 1321 → 1322 → 1323 d0.55 (latent←1305) → 1324 → 1325 → 1326/1327
            └─ 左脸：1330 → 1331 → 1332 → 1333 d0.55 (latent←1305) → 1334 → 1335 → 1336/1337
         ★ 三视角共用 1301 身份 LOCK + 1305 结构锚，**唯一差别是表现层提示词**
           （front view / turned to his right / turned to his left）。
         ⚠️ 已知不确定性：Flux 在 d0.55 下能否把朝向真正转过去，尚无实测结论。
            若左/右脸出来还是正脸，调 1323/1333 的 denoise（往上加 0.6~0.7）或改用
            G2 组现成的 Kontext 转头工艺产出侧面锚再灌回 1303。
    D. 旧「以 v23 当结构锚 + Flux 重画」的 IMG 支路（1410–1417）**不再生成** ——
       它整条的存在意义就是 v23 骨相，与用户诉求直接冲突。
       需要可回退：把 git/备份里的 `_backup_0920-164302.json` 推回去即可。

★ Flux 参数红线（与 SDXL 完全不通用）
    cfg 必须 1.0；euler + simple；20 步；负向在 cfg=1 下 100% 失效 → 留空。

用法：
    python add_flux_baseline_group.py            # 只生成本地 JSON，不联网（云没开机时用这个）
    python add_flux_baseline_group.py --push     # 备份 → 推送（换新 uuid 绕浏览器缓存）→ 回读校验
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
SNAP = os.path.join(WFDIR, '_server_now.json')     # 改动前的服务器版（121 节点）= 唯一重建基线
LOCALOUT = os.path.join(WFDIR, '夜市百相簿_主工作流.json')

B = os.environ.get(
    'COMFY_BASE',
    'https://gw-efb56d453d484597a1b8ddfc86156262.cn-beijing.aigclinks.com:8016').rstrip('/')
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

PUSH = '--push' in sys.argv

SEED = 20260920
STEPS = 20
CFG = 1.0
D_BASE = 1.0              # 正脸基准图：纯文生图
D_LOCK = 0.55             # 身份锁：结构锚 + Flux 重画质感（三视角同参数）
ANCHOR_DOWN = (512, 640)  # 结构锚 ① 降采样（抹高频细节，只留骨相）
ANCHOR_BACK = (1024, 1280)

# ---------------------------------------------------------------------------- 提示词
# ① 正脸基准图 —— FLUX 正向词。
#   ★ 已知问题（用户 2026-09-20 反馈「太丑 + 磨皮重」）本轮**不动**，待下一轮单独改词，
#     一轮只留一个变量。病灶定位见文档第五节。
FLUX_POS = (
    'photorealistic portrait photograph, front view, straight-on, looking at the viewer, '
    'face closeup, head and shoulders, cropped above the chest, solo, 1boy, '
    'a 24 year old adult East Asian man, clearly adult male face, mature masculine bone structure, '
    'narrow long face, high cheekbones, defined but youthful angular jawline, straight narrow nose bridge, '
    'thin lips, deep-set dark brown eyes, slightly heavy eyelids, tired calm weary gaze, '
    'faint dark circles and soft under-eye shadows, '
    'medium length messy wavy black hair, voluminous tousled waves, individual flyaway strands, '
    'a single small dark mole at the outer corner of his right eye, a few faint natural moles on his cheeks, '
    'thick dark eyebrows with individual hairs, light natural stubble on the upper lip and chin, '
    'bare natural skin, plain unadorned everyday appearance, unretouched realistic complexion, '
    'natural skin texture with visible pores and fine imperfections, matte dry skin, '
    'faded blue shirt with the collar open, dark worn trench coat collar, plain ordinary everyday clothing, '
    'plain seamless white studio backdrop filling the entire frame, evenly lit white backdrop, '
    'soft even studio lighting, subtle facial shadows, sharp focus on the eyes, '
    '35mm film photograph, fine film grain, muted cinematic color grading, high detail'
)
FLUX_NEG = ''   # cfg=1 → 通道关闭，写什么都没用，留空

# ③ 身份锁 · 左脸表现层（新增；照右脸 1320 镜像改向）
FACE_LEFT = (
    '[presentation layer, re-generate the photograph] photorealistic portrait photograph, '
    'three-quarter view, face turned to his left side, left cheek facing the camera, '
    'looking away from the viewer, face closeup, head and shoulders, solo, '
    'natural skin texture with visible pores and fine imperfections, individual eyebrow hairs, '
    'realistic stubble texture, flyaway hair strands, matte dry skin, '
    'soft cinematic studio lighting, subtle side light, shallow depth of field, '
    '35mm film photograph, fine film grain, muted cinematic color grading, sharp focus, high detail'
)

# ---------------------------------------------------------------------------- 要删掉的 v23 依赖
DEL_NODES = [
    1120,                                          # v23 身份锚（半透明缩略图就挂在画布上）
    1302,                                          # 旧 SDXL 正脸锚源
    1121, 1122, 1123, 1124, 1125, 1126,            # 以 v23 图为基图的 d0.3 重绘（冗余第二套输出）
    1306, 1307, 1308, 1309,                        # 右脸的 v23 侧脸锚 + 降采样链
]
DEL_LABEL = {
    1120: 'v23 身份锚 LoadImage', 1302: '旧 SDXL 正脸锚源 LoadImage',
    1121: '块B ① VAEEncode', 1122: '块B ② KSampler d0.3', 1123: '块B ③ VAEDecode',
    1124: '块B 输出 闻灯Flux基准-草稿', 1125: '块B ④ 放大', 1126: '块B 输出 闻灯Flux基准-成品',
    1306: '右脸 v23 侧脸锚 LoadImageOutput', 1307: '右脸锚 ① 降采样',
    1308: '右脸锚 ② 放回', 1309: '右脸锚 ③ VAEEncode',
}

# ---------------------------------------------------------------------------- 载入基线
if not os.path.exists(SNAP):
    print('★ 缺少重建基线：%s' % SNAP)
    sys.exit(1)

wf = json.load(io.open(SNAP, encoding='utf-8'))
print('重建基线：%s  id=%s  节点%d 链接%d 分组%d'
      % (os.path.basename(SNAP), wf.get('id'), len(wf['nodes']), len(wf['links']), len(wf.get('groups', []))))

if any(n['type'] == 'SaveImage' and n.get('widgets_values')
       and '正脸基准' in n['widgets_values'][0] for n in wf['nodes']):
    print('★ 已存在「正脸基准」输出 —— 防重入，退出。')
    sys.exit(0)

byid = {n['id']: n for n in wf['nodes']}
for need in (1100, 1101, 1102, 1103, 1110, 1111, 1112, 1113, 1114, 1115, 1127,
             1300, 1301, 1303, 1304, 1305, 1310, 1311, 1312, 1313, 1314, 1315, 1316, 1317,
             1320, 1321, 1322, 1323, 1324, 1325, 1326, 1327):
    if need not in byid:
        print('★ 基线缺少节点 %d，无法原地改造。' % need)
        sys.exit(1)

tpl = {}
for n in wf['nodes']:
    tpl.setdefault(n['type'], n)

MANUAL = {
    'FluxGuidance': {
        'inputs': [{'name': 'conditioning', 'type': 'CONDITIONING', 'link': None}],
        'outputs': [{'name': 'CONDITIONING', 'type': 'CONDITIONING', 'links': [], 'slot_index': 0}],
        'size': [315, 58]},
    'EmptySD3LatentImage': {
        'inputs': [],
        'outputs': [{'name': 'LATENT', 'type': 'LATENT', 'links': [], 'slot_index': 0}],
        'size': [315, 106]},
    'ConditioningConcat': {
        'inputs': [{'name': 'conditioning_to', 'type': 'CONDITIONING', 'link': None},
                   {'name': 'conditioning_from', 'type': 'CONDITIONING', 'link': None}],
        'outputs': [{'name': 'CONDITIONING', 'type': 'CONDITIONING', 'links': [], 'slot_index': 0}],
        'size': [315, 46]},
}
for t, d in MANUAL.items():
    if t not in tpl:
        tpl[t] = {'type': t, 'flags': {}, 'mode': 0, 'properties': {'Node name for S&R': t},
                  'inputs': copy.deepcopy(d['inputs']), 'outputs': copy.deepcopy(d['outputs'])}


def mk(t, nid, pos, size, wv, in_links=None, out_links=None, title=None, mode=0):
    n = copy.deepcopy(tpl[t])
    n['id'] = nid
    n['pos'] = list(pos)
    n['size'] = list(size)
    n['mode'] = mode
    n.pop('title', None)
    if title:
        n['title'] = title
    n['flags'] = {}
    for s in n.get('inputs') or []:
        s['link'] = (in_links or {}).get(s['name'])
    for i, s in enumerate(n.get('outputs') or []):
        s['links'] = list((out_links or {}).get(s['name'], []))
        s['slot_index'] = i
    if wv is not None:
        n['widgets_values'] = list(wv)
    return n


# ---------------------------------------------------------------- 新增：身份锁 · 左脸段（1330–1337）
# (link_id, from_id, from_slot, to_id, to_slot, type)
LINKS = [
    (2140, 1305, 0, 1323, 3, 'LATENT'),          # 右脸 latent ← 共用结构锚（不再是 v23 侧脸）
    (2141, 1305, 0, 1333, 3, 'LATENT'),          # 左脸 latent ← 共用结构锚
    (2142, 1300, 0, 1333, 0, 'MODEL'),
    (2143, 1300, 1, 1330, 0, 'CLIP'),
    (2144, 1300, 2, 1334, 1, 'VAE'),
    (2145, 1301, 0, 1331, 0, 'CONDITIONING'),    # 共用身份 LOCK
    (2146, 1330, 0, 1331, 1, 'CONDITIONING'),
    (2147, 1331, 0, 1332, 0, 'CONDITIONING'),
    (2148, 1332, 0, 1333, 1, 'CONDITIONING'),
    (2149, 1102, 0, 1333, 2, 'CONDITIONING'),
    (2150, 1333, 0, 1334, 0, 'LATENT'),
    (2151, 1334, 0, 1336, 0, 'IMAGE'),
    (2152, 1334, 0, 1335, 1, 'IMAGE'),
    (2153, 1127, 0, 1335, 0, 'UPSCALE_MODEL'),
    (2154, 1335, 0, 1337, 0, 'IMAGE'),
    (2216, 1112, 0, 1303, 0, 'IMAGE'),           # ★ 身份锁结构锚源 = 正脸基准图（不再是 v23）
]

PORTS = {
    1330: ({'clip': 0}, {'CONDITIONING': 0}),
    1331: ({'conditioning_to': 0, 'conditioning_from': 1}, {'CONDITIONING': 0}),
    1332: ({'conditioning': 0}, {'CONDITIONING': 0}),
    1333: ({'model': 0, 'positive': 1, 'negative': 2, 'latent_image': 3}, {'LATENT': 0}),
    1334: ({'samples': 0, 'vae': 1}, {'IMAGE': 0}),
    1335: ({'upscale_model': 0, 'image': 1}, {'IMAGE': 0}),
    1336: ({'images': 0}, {'images': 0}),
    1337: ({'images': 0}, {'images': 0}),
}


def in_map(nid):
    m = {}
    for l in LINKS:
        if l[3] == nid:
            m[l[4]] = l[0]
    names = {v: k for k, v in PORTS[nid][0].items()}
    return {names[s]: lid for s, lid in m.items() if s in names}


def out_map(nid):
    m = {}
    for l in LINKS:
        if l[1] == nid:
            m.setdefault(l[2], []).append(l[0])
    names = {v: k for k, v in PORTS[nid][1].items()}
    return {names[s]: lids for s, lids in m.items() if s in names}


NEW = [
    mk('CLIPTextEncode', 1330, (8100, 4400), [425, 200], [FACE_LEFT],
       in_map(1330), out_map(1330), '🎨 左脸·表现层（允许 FLUX 重画质感）'),
    mk('ConditioningConcat', 1331, (8560, 4400), [315, 46], None,
       in_map(1331), out_map(1331), '身份段 + 左脸表现段'),
    mk('FluxGuidance', 1332, (8560, 4540), [315, 58], [3.5],
       in_map(1332), out_map(1332)),
    mk('KSampler', 1333, (8900, 4400), [315, 262], [SEED, 'fixed', STEPS, CFG, 'euler', 'simple', D_LOCK],
       in_map(1333), out_map(1333), '左脸 KSampler（d%.2f，结构与正/右脸共用）' % D_LOCK),
    mk('VAEDecode', 1334, (9250, 4400), [210, 46], None, in_map(1334), out_map(1334)),
    mk('ImageUpscaleWithModel', 1335, (9250, 4500), [315, 46], None, in_map(1335), out_map(1335)),
    mk('SaveImage', 1336, (9600, 4300), [400, 500], ['闻灯Flux身份锁-左脸-草稿'],
       in_map(1336), out_map(1336)),
    mk('SaveImage', 1337, (9600, 4750), [400, 500], ['闻灯Flux身份锁-左脸-成品'],
       in_map(1337), out_map(1337)),
]

# ---------------------------------------------------------------- 画布便签（Note 不进 API）
NOTE_TEXT = """【2026-09-20 · 本组结构 = FLUX → 正脸基准图 → 身份锁(正脸/右脸/左脸)】

① FLUX（一体化解）
   1100 底模 fp8 → 1101 正向词 → 1103 FluxGuidance 3.5
   1110 空 latent 1024×1280 → 1111 KSampler d1.0 → 1112 VAEDecode

② 闻灯正脸基准图
   1113 草稿（直出） / 1115 成品（1114 做 4× 放大，不二段重绘）

③ 身份锁 / Identity Reference   （1300 独立底模，三视角共用 1301 身份 LOCK）
   1303 ← 1112（基准图）→ 1304 → 1305 = 结构锚 latent
     ├─ 正脸 1310 → 1311 → 1312 → 1313 d0.55 → 1314 → 1315 → 1316 / 1317
     ├─ 右脸 1320 → 1321 → 1322 → 1323 d0.55 → 1324 → 1325 → 1326 / 1327
     └─ 左脸 1330 → 1331 → 1332 → 1333 d0.55 → 1334 → 1335 → 1336 / 1337

★ 本组已彻底不依赖 v23
   已删除 1120 / 1302（两个 wendeng_v23_face_base.png 的 LoadImage）、
   1121–1126（以 v23 图为基图的第二套冗余输出）、
   1306–1309（右脸的 v23 侧脸锚）。
   硬判据：改造后本组内 LoadImage / LoadImageOutput 数量 = 0。

★ 跑图（按分支名提交，别在浏览器点大「运行」）
   python _scripts\\run_wf.py "夜市百相簿-主工作流.json" "闻灯正脸基准" draft
   python _scripts\\run_wf.py "夜市百相簿-主工作流.json" "闻灯Flux身份锁" final"""

NEW.append({
    'id': 1338,
    'type': 'Note',
    'pos': [7640, 4980],
    'size': [1800, 400],
    'flags': {},
    'order': 40,
    'mode': 0,
    'inputs': [],
    'outputs': [],
    'title': '★ 本组结构 · FLUX → 正脸基准图 → 身份锁(正脸/右脸/左脸)',
    'properties': {'Node name for S&R': 'Note'},
    'widgets_values': [NOTE_TEXT],
    'color': '#432',
    'bgcolor': '#653',
})

# ---------------------------------------------------------------- 改造现有节点
# ① 上游：正脸基准图（Flux 自产）
byid[1101]['widgets_values'] = [FLUX_POS]
byid[1101]['title'] = '① 正脸基准 · 正向词（FLUX）'
byid[1102]['title'] = '① 正脸基准 · 负向词（cfg=1 → 空，写了也无效）'
byid[1111]['title'] = '① 正脸基准 · Flux 纯文生图 d1.0（★一张全新的脸）'
byid[1113]['widgets_values'] = ['闻灯正脸基准-草稿']
byid[1113]['title'] = '② 正脸基准图 · 草稿'
byid[1115]['widgets_values'] = ['闻灯正脸基准-成品']
byid[1115]['title'] = '② 正脸基准图 · 成品（4× 放大，不二段重绘）'

# ③ 身份锁：结构锚（三视角共用）
byid[1301]['title'] = '🔒 身份特征 LOCK（正脸 / 右脸 / 左脸 共用）'
byid[1303]['title'] = '③ 结构锚 ① 降采样 → 512×640（抹掉毛孔/发丝，只留骨相）'
byid[1304]['title'] = '③ 结构锚 ② 放回 1024×1280（细节不回来 = 只留结构）'
byid[1305]['title'] = '③ 结构锚 ③ → latent（身份就锁在这里 · 三视角共用）'
byid[1310]['title'] = '🎨 正脸·表现层'
byid[1311]['title'] = '身份段 + 正脸表现段'
byid[1313]['title'] = '正脸 KSampler（d%.2f）' % D_LOCK
byid[1320]['title'] = '🎨 右脸·表现层'
byid[1321]['title'] = '身份段 + 右脸表现段'
byid[1323]['title'] = '右脸 KSampler（d%.2f）' % D_LOCK
byid[1316]['title'] = '右… 正脸 · 草稿'
byid[1317]['title'] = '正脸 · 成品（4× 放大）'
byid[1326]['title'] = '右脸 · 草稿'
byid[1327]['title'] = '右脸 · 成品（4× 放大）'

# ---------------------------------------------------------------- 删除 v23 依赖节点 + 清理悬空连线
_delset = set(DEL_NODES)
for nid in sorted(_delset):
    if nid not in byid:
        print('  (基线无 %d，跳过删除)' % nid)

wf['nodes'] = [n for n in wf['nodes'] if n['id'] not in _delset]
byid = {n['id']: n for n in wf['nodes']}

_dead = [l[0] for l in wf['links'] if l[1] in _delset or l[3] in _delset]
wf['links'] = [l for l in wf['links'] if l[0] not in _dead]
for n in wf['nodes']:
    for o in (n.get('outputs') or []):
        o['links'] = [x for x in (o.get('links') or []) if x not in _dead]
    for i in (n.get('inputs') or []):
        if i.get('link') in _dead:
            i['link'] = None
print('已删除 %d 个 v23/冗余节点；连带清理 %d 条连线' % (len(_delset), len(_dead)))

# 加新连线 + 补旧节点端口登记
wf['links'].extend([list(l) for l in LINKS])
for (lid, fid, fslot, tid, tslot, _t) in LINKS:
    f = byid.get(fid)
    if f:
        for i, o in enumerate(f.get('outputs') or []):
            if i == fslot:
                o.setdefault('links', [])
                if lid not in o['links']:
                    o['links'].append(lid)
    t = byid.get(tid)
    if t and tslot < len(t.get('inputs') or []):
        t['inputs'][tslot]['link'] = lid
# 1323 的 latent 槽在删掉 1309 后已置 None，这里由 2140 补上；确认一次
assert [i.get('link') for i in byid[1323]['inputs']][3] == 2140, '1323 latent 未接上结构锚'

# ---------------------------------------------------------------- 分组框
for g in wf.get('groups', []):
    if 'Flux' in g.get('title', '') and g.get('bounding', [0, 0, 0, 0])[0] >= 7500:
        g['title'] = '【闻灯】Flux 文生图 · 一体化 fp8（FLUX → 正脸基准图 → 身份锁 正脸/右脸/左脸）'
        g['bounding'] = [7600, 250, 3120, 5220]

# E. 连线登记归一化（消除原版遗留的 outputs[].links 未登记）
_norm = 0
for (lid, fid, fslot, tid, tslot, _t) in wf['links']:
    f, t = byid.get(fid), byid.get(tid)
    if f and fslot < len(f.get('outputs') or []):
        o = f['outputs'][fslot]
        o.setdefault('links', [])
        if lid not in o['links']:
            o['links'].append(lid)
            _norm += 1
    if t and tslot < len(t.get('inputs') or []):
        if t['inputs'][tslot].get('link') != lid:
            t['inputs'][tslot]['link'] = lid
            _norm += 1
print('连线登记归一化补写 %d 处' % _norm)

wf['nodes'].extend(NEW)
wf['last_node_id'] = max([wf.get('last_node_id', 0)] + [n['id'] for n in NEW])
wf['last_link_id'] = max([wf.get('last_link_id', 0)] + [l[0] for l in LINKS])
wf['id'] = str(uuid.uuid4())

print('\n新增 %d 节点 / %d 连线' % (len(NEW), len(LINKS)))
print('现共：节点 %d  链接 %d  分组 %d   新 id = %s'
      % (len(wf['nodes']), len(wf['links']), len(wf['groups']), wf['id']))

# ---------------------------------------------------------------- 本地自检
from wf_api import build_api, deps, find_outputs, WIDGETS   # noqa: E402

bad = 0
byid = {n['id']: n for n in wf['nodes']}

# ① 硬判据：本组内不得再有任何 LoadImage / LoadImageOutput
G3X = 7500
g3 = [n for n in wf['nodes'] if n['pos'][0] >= G3X]
loads = [n for n in g3 if n['type'] in ('LoadImage', 'LoadImageOutput')]
print('\n--- 本地自检 ---')
print('【硬判据】本组内 LoadImage/LoadImageOutput：%s  %s'
      % ([(n['id'], n['widgets_values'][0]) for n in loads] if loads else '0 个',
         '✔' if not loads else '★ 还有 v23 残留！'))
if loads:
    bad += 1

# ② 全工作流里 v23 图还剩几处（应只剩 G1 脸部组的 1004/1027）
v23 = [(n['id'], n['pos'][0], n['widgets_values'][0]) for n in wf['nodes']
       if n['type'] in ('LoadImage', 'LoadImageOutput') and n.get('widgets_values')
       and 'wendeng_v23_face_base' in str(n['widgets_values'][0])]
print('全工作流引用 wendeng_v23_face_base.png 的节点：%s' % (v23 or '无'))

api, titles = build_api(wf)
unsup = sorted({n['type'] for n in wf['nodes'] if n['type'] not in WIDGETS})
print('可转换节点 %d / %d' % (len(api), len(wf['nodes'])))
print('未登记类型（会被静默跳过）：%s' % (unsup if unsup else '无 ✔'))

# ③ 六条身份锁输出 + 两条基准输出，依赖链必须完整且不含 LoadImage
CASES = [('闻灯正脸基准', '草稿'), ('闻灯正脸基准', '成品'),
         ('闻灯Flux身份锁-正脸', '草稿'), ('闻灯Flux身份锁-正脸', '成品'),
         ('闻灯Flux身份锁-右脸', '草稿'), ('闻灯Flux身份锁-右脸', '成品'),
         ('闻灯Flux身份锁-左脸', '草稿'), ('闻灯Flux身份锁-左脸', '成品')]
need = {'CheckpointLoaderSimple', 'KSampler', 'VAEDecode', 'SaveImage'}
print('\n--- 分支自检（8 条）---')
for tok, kind in CASES:
    hits = find_outputs(api, tok, kind)
    if len(hits) != 1:
        print('  ★ %s-%s → 命中 %s 条（应 1 条）' % (tok, kind, len(hits)))
        bad += 1
        continue
    nid, pfx = hits[0]
    keep = deps(api, [nid])
    names = {api[k]['class_type'] for k in keep}
    imgloads = [api[k]['inputs'].get('image') for k in keep if api[k]['class_type'] == 'LoadImage']
    ok = need <= names and not imgloads
    if not ok:
        bad += 1
    print('  %s %-28s 依赖 %2d 节点  含图输入:%s  %s'
          % ('✔' if ok else '★', pfx, len(keep), imgloads or '无', '' if ok else '断链/仍有 LoadImage'))

# ④ 关键连线断言
print('\n--- 关键连线断言 ---')
assertions = [(1303, 0, 1112, 'image   ← 正脸基准图'),
              (1323, 3, 1305, 'latent  ← 共用结构锚'),
              (1333, 3, 1305, 'latent  ← 共用结构锚'),
              (1313, 3, 1305, 'latent  ← 共用结构锚'),
              (1311, 1, 1310, 'from    ← 正脸表现层'),
              (1321, 1, 1320, 'from    ← 右脸表现层'),
              (1331, 1, 1330, 'from    ← 左脸表现层'),
              (1311, 0, 1301, 'to      ← 身份 LOCK'),
              (1321, 0, 1301, 'to      ← 身份 LOCK'),
              (1331, 0, 1301, 'to      ← 身份 LOCK')]
for nid, slot, want, label in assertions:
    src = [l[1] for l in wf['links'] if l[3] == nid and l[4] == slot]
    ok = src == [want]
    if not ok:
        bad += 1
    print('  %s %-6s slot%d %-28s ← %s' % ('✔' if ok else '★', nid, slot, label, src))

# ⑤ 结构完整性：悬空 / 槽位不一致 / 环
declared = set()
for n in wf['nodes']:
    for o in (n.get('outputs') or []):
        for l in (o.get('links') or []):
            declared.add(l)
    for i in (n.get('inputs') or []):
        if i.get('link') is not None:
            declared.add(i['link'])
actual = set(l[0] for l in wf['links'])
mis = []
for l in wf['links']:
    lid, f, fs, t, ts, ty = l
    fo = byid[f].get('outputs') or []
    ti = byid[t].get('inputs') or []
    if fs >= len(fo) or lid not in (fo[fs].get('links') or []):
        mis.append(('from未登记', l))
    if ts >= len(ti) or ti[ts].get('link') != lid:
        mis.append(('to未登记', l))
print('\n--- 结构完整性 ---')
print('  悬空连线（端口引用但 links 里没有）：%s' % (sorted(declared - actual) or '无 ✔'))
print('  孤儿连线（links 里有但无端口引用）：%s' % (sorted(actual - declared) or '无 ✔'))
print('  槽位不一致：%s' % (mis or '无 ✔'))
if mis or (declared - actual):
    bad += 1
# 环检测
adj = {}
for l in wf['links']:
    adj.setdefault(l[1], []).append(l[3])


def has_cycle():
    WHITE, GREY, BLACK = 0, 1, 2
    col = {n['id']: WHITE for n in wf['nodes']}
    for s in list(col):
        if col[s] != WHITE:
            continue
        st = [(s, iter(adj.get(s, [])))]
        col[s] = GREY
        while st:
            node, it = st[-1]
            nxt = next(it, None)
            if nxt is None:
                col[node] = BLACK
                st.pop()
                continue
            if col.get(nxt, WHITE) == GREY:
                return True
            if col.get(nxt, WHITE) == WHITE:
                col[nxt] = GREY
                st.append((nxt, iter(adj.get(nxt, []))))
    return False


_cyc = has_cycle()
print('  环：%s' % ('★ 存在！' if _cyc else '无 ✔'))
if _cyc:
    bad += 1

if bad:
    print('\n★ 自检未通过（%d 处），不写出、不推送。' % bad)
    sys.exit(1)

print('\n✔ 自检全过。')
os.makedirs(WFDIR, exist_ok=True)
io.open(LOCALOUT, 'w', encoding='utf-8').write(json.dumps(wf, ensure_ascii=False, indent=1))
print('本地已写出 → %s' % LOCALOUT)

if not PUSH:
    print('\n（未加 --push，只写本地。云开机后加 --push 即可部署。）')
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
bn = {n['id']: n for n in back['nodes']}
print('  服务器版 id = %s' % back.get('id'))
print('  节点 %d  链接 %d  分组 %d' % (len(back['nodes']), len(back['links']), len(back['groups'])))
badload = [n['id'] for n in back['nodes']
           if n['pos'][0] >= G3X and n['type'] in ('LoadImage', 'LoadImageOutput')]
print('  本组内 LoadImage：%s  %s' % (badload or '0 个', '✔' if not badload else '★ 还有！'))
outs = [n['widgets_values'][0] for n in sorted(back['nodes'], key=lambda x: x['id'])
        if n['type'] == 'SaveImage' and n.get('widgets_values')]
print('  全部输出共 %d 个：' % len(outs))
for o in outs:
    print('     ', o)
print('\n跑图命令（按分支名提交）：')
print('  python run_wf.py "%s" "闻灯正脸基准" draft' % NAME)
print('  python run_wf.py "%s" "闻灯Flux身份锁" draft' % NAME)
