# -*- coding: utf-8 -*-
"""在「夜市百相簿-主工作流.json」的 Flux 文生图组里**原地追加**「身份锁 · 高质感重生」节点。

★ 用户要的分层（2026-09-20）
    【身份锁定】→ 身份特征 ─┬─ 正脸提示词 → FLUX → 高质感正脸
                            └─ 右脸提示词 → FLUX → 高质感右脸
    · 身份层（锁死）：脸型 / 眼睛 / 鼻子 / 嘴 / 下巴 / 眉眼比例 / 年龄感 / 眼尾小痣 / 男性特征
    · 表现层（放开）：皮肤微纹理 / 毛孔 / 眉毛毛发 / 胡茬 / 发丝 / 光影 / 色调 / 景深 /
                      摄影质感 / 电影感 / 不同角度 / 不同表情
    一句话：「人」锁住，「照片」重新生成。

★ 怎么实现「锁身份但不锁表现」—— 两把不同的锁
    1) **结构锚（管身份）**：基图先 `ImageScale` 缩到 512×640 再放回 1024×1280，
       这一步是低通滤波 —— **高频细节（毛孔/发丝/皮肤微纹理）被彻底抹掉，低频结构
       （脸型/五官位置/比例/痣的位置）完整保留**。再把这张"有骨架没皮肤"的图
       `VAEEncode` 成 latent 喂给 KSampler。
    2) **高 denoise（管表现）**：因为是**模糊输入**，Flux 没有细节可抄 → 必须自己
       重画毛孔、发丝、光影、景深；而大结构被模糊图锚住 → 人还是那个人。
       denoise 0.55 是甜点值：结构稳、质感新。
    → 缩放倍率 = 身份锁强度旋钮；denoise = 表现层自由度旋钮。两个都在这里可调。

★ 为什么右脸不用 Kontext
    Kontext 模型 `diffusion_models\\FLUX1\\flux1-schnell.safetensors` 仍是**残件**
    （8,589,934,588 字节 = 差 4 字节到 8GiB 整，modified 停在 09-18 17:18，今天那次重下没落地）。
    而 img2img **转不出朝向**（已有 4 次实证）。所以右脸路改用**已有的 v23 侧面成品当结构锚**
    （`闻灯v23-脸部侧面c-成品_00001_.png`）—— 角度由基图给，质感由 Flux 重画。
    要"任意角度"才需要 Kontext。

★ 复用而非重复（少 2 个节点、不碰旧节点）
    · 负向 conditioning 复用 `#1102`（Flux 组原有的空负向；cfg=1 时负向通道本就关闭）
    · 放大模型复用 `#1127`（4x-UltraSharp）

用法：
    python add_identity_lock.py             # 只生成本地 JSON，不联网
    python add_identity_lock.py --push      # 备份 → 推送（换新 id 绕缓存）→ 回读校验
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

GROUP_MATCH = 'Flux 文生图'
GROUP_TITLE = '【闻灯】Flux 文生图 · 一体化 fp8（v23 基准对照 + 身份锁 正脸/右脸）'
GROUP_BOX = [7600, 250, 3120, 4150]      # x, y, w, h —— 向下扩展以容纳身份锁节点

CKPT = 'FLUX1\\flux1-dev-fp8.safetensors'
UPSCALE = '4x-UltraSharp (1).pth'
FACE_BASE = 'wendeng_v23_face_base.png'                  # 正脸结构锚源（input/）
SIDE_BASE = '闻灯v23-脸部侧面c-成品_00001_.png'            # 右脸结构锚源（output/）

SEED = 20260920
W, H = 1024, 1280
W_LOW, H_LOW = 512, 640          # 结构锚降采样尺寸 = 身份锁强度旋钮
STEPS = 20
CFG = 1.0
GUIDANCE = 3.5
DENOISE = 0.55                   # 表现层自由度旋钮

# ---------------------------------------------------------------- 提示词
# Flux 用 T5，吃长句、不吃 tag 堆叠；cfg=1 → 否定词一律写成正面短语
LOCK_POS = (
    '[identity lock, keep the exact same person as the reference] '
    '24 year old East Asian man, narrow long face, high cheekbones, '
    'defined youthful jawline, straight narrow nose bridge, thin lips, '
    'slightly heavy-lidded dark eyes, calm tired gaze, '
    'small dark mole at the outer corner of his right eye, '
    'messy wavy black hair, light stubble on chin and upper lip, '
    'masculine youthful bone structure, consistent facial proportions'
)

FRONT_POS = (
    '[presentation layer, re-generate the photograph] '
    'photorealistic portrait photograph, front view, looking at viewer, '
    'face closeup, head and shoulders, solo, ' \
    'natural skin texture with visible pores and fine imperfections, '
    'individual eyebrow hairs, realistic stubble texture, flyaway hair strands, '
    'matte dry skin, soft cinematic studio lighting, subtle rim light, '
    'shallow depth of field, 35mm film photograph, fine film grain, '
    'muted cinematic color grading, sharp focus on the eyes, high detail'
)

RIGHT_POS = (
    '[presentation layer, re-generate the photograph] '
    'photorealistic portrait photograph, three-quarter view, '
    'face turned to his right side, right cheek facing the camera, '
    'looking away from the viewer, face closeup, head and shoulders, solo, '
    'natural skin texture with visible pores and fine imperfections, '
    'individual eyebrow hairs, realistic stubble texture, flyaway hair strands, '
    'matte dry skin, soft cinematic studio lighting, subtle side light, '
    'shallow depth of field, 35mm film photograph, fine film grain, '
    'muted cinematic color grading, sharp focus, high detail'
)

# ---------------------------------------------------------------- 载入服务器现版
wf = json.load(io.open(SNAP, encoding='utf-8'))
print('现版：%s  id=%s  节点%d 链接%d 分组%d'
      % (NAME, wf.get('id'), len(wf['nodes']), len(wf['links']), len(wf.get('groups', []))))

for g in wf.get('groups', []):
    if '身份锁' in g.get('title', ''):
        print('★ 已存在身份锁分组（%s）—— 防重入，退出。' % g['title'])
        sys.exit(0)

existing_ids = {n['id'] for n in wf['nodes']}
NEW_IDS = [1300, 1301, 1302, 1303, 1304, 1305, 1306, 1307, 1308, 1309,
           1310, 1311, 1312, 1313, 1314, 1315, 1316, 1317,
           1320, 1321, 1322, 1323, 1324, 1325, 1326, 1327]
clash = [i for i in NEW_IDS if i in existing_ids]
if clash:
    print('★ 节点 id 冲突：%s —— 退出。' % clash)
    sys.exit(1)

tpl = {}
for n in wf['nodes']:
    tpl.setdefault(n['type'], n)

NEED = ['CheckpointLoaderSimple', 'CLIPTextEncode', 'KSampler', 'VAEDecode', 'SaveImage',
        'ImageUpscaleWithModel', 'LoadImage', 'LoadImageOutput', 'VAEEncode', 'ImageScale',
        'FluxGuidance']
missing = [t for t in NEED if t not in tpl]
if missing:
    print('⚠️ 缺模板（将用手工结构）：', missing)


def mk(t, nid, pos, size, wv, in_links=None, out_links=None, title=None):
    """克隆同类型现有节点做模板，只改 id / 位置 / widget / 连线。"""
    if t in tpl:
        n = copy.deepcopy(tpl[t])
    else:
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


MANUAL = {
    'ConditioningConcat': {
        'inputs': [{'name': 'conditioning_to', 'type': 'CONDITIONING', 'link': None},
                   {'name': 'conditioning_from', 'type': 'CONDITIONING', 'link': None}],
        'outputs': [{'name': 'CONDITIONING', 'type': 'CONDITIONING', 'links': [], 'slot_index': 0}],
        'size': [315, 46],
    },
}
for t, d in MANUAL.items():
    if t not in tpl:
        n = {'type': t, 'flags': {}, 'mode': 0, 'properties': {'Node name for S&R': t},
             'inputs': copy.deepcopy(d['inputs']), 'outputs': copy.deepcopy(d['outputs'])}
        tpl[t] = n

# ---------------------------------------------------------------- 连线
# (link_id, from_id, from_slot, to_id, to_slot, type)
LINKS = [
    # 底模 → 各处
    (2101, 1300, 0, 1313, 0, 'MODEL'),
    (2102, 1300, 0, 1323, 0, 'MODEL'),
    (2103, 1300, 1, 1301, 0, 'CLIP'),
    (2104, 1300, 1, 1310, 0, 'CLIP'),
    (2105, 1300, 1, 1320, 0, 'CLIP'),
    (2106, 1300, 2, 1305, 1, 'VAE'),
    (2107, 1300, 2, 1309, 1, 'VAE'),
    (2108, 1300, 2, 1314, 1, 'VAE'),
    (2109, 1300, 2, 1324, 1, 'VAE'),
    # 正脸结构锚链：基图 → 缩 → 还原 → 编码
    (2110, 1302, 0, 1303, 0, 'IMAGE'),
    (2111, 1303, 0, 1304, 0, 'IMAGE'),
    (2112, 1304, 0, 1305, 0, 'IMAGE'),
    # 右脸结构锚链
    (2113, 1306, 0, 1307, 0, 'IMAGE'),
    (2114, 1307, 0, 1308, 0, 'IMAGE'),
    (2115, 1308, 0, 1309, 0, 'IMAGE'),
    # 身份特征 → 两条支路的 Concat
    (2116, 1301, 0, 1311, 0, 'CONDITIONING'),
    (2117, 1301, 0, 1321, 0, 'CONDITIONING'),
    # 表现层 → Concat.from
    (2118, 1310, 0, 1311, 1, 'CONDITIONING'),
    (2119, 1320, 0, 1321, 1, 'CONDITIONING'),
    # Concat → FluxGuidance
    (2120, 1311, 0, 1312, 0, 'CONDITIONING'),
    (2121, 1321, 0, 1322, 0, 'CONDITIONING'),
    # FluxGuidance → KSampler.positive
    (2122, 1312, 0, 1313, 1, 'CONDITIONING'),
    (2123, 1322, 0, 1323, 1, 'CONDITIONING'),
    # 负向复用 #1102
    (2124, 1102, 0, 1313, 2, 'CONDITIONING'),
    (2125, 1102, 0, 1323, 2, 'CONDITIONING'),
    # 结构锚 latent → KSampler.latent_image
    (2126, 1305, 0, 1313, 3, 'LATENT'),
    (2127, 1309, 0, 1323, 3, 'LATENT'),
    # KSampler → VAEDecode
    (2128, 1313, 0, 1314, 0, 'LATENT'),
    (2129, 1323, 0, 1324, 0, 'LATENT'),
    # VAEDecode → 草稿存档 + 放大
    (2130, 1314, 0, 1316, 0, 'IMAGE'),
    (2131, 1314, 0, 1315, 1, 'IMAGE'),
    (2132, 1324, 0, 1326, 0, 'IMAGE'),
    (2133, 1324, 0, 1325, 1, 'IMAGE'),
    # 放大模型复用 #1127
    (2134, 1127, 0, 1315, 0, 'UPSCALE_MODEL'),
    (2135, 1127, 0, 1325, 0, 'UPSCALE_MODEL'),
    # 放大 → 成品存档
    (2136, 1315, 0, 1317, 0, 'IMAGE'),
    (2137, 1325, 0, 1327, 0, 'IMAGE'),
]

NODE_PORTS = {
    1300: ({}, {'MODEL': 0, 'CLIP': 1, 'VAE': 2}),
    1301: ({'clip': 0}, {'CONDITIONING': 0}),
    1302: ({}, {'IMAGE': 0, 'MASK': 1}),
    1303: ({'image': 0}, {'IMAGE': 0}),
    1304: ({'image': 0}, {'IMAGE': 0}),
    1305: ({'pixels': 0, 'vae': 1}, {'LATENT': 0}),
    1306: ({}, {'IMAGE': 0, 'MASK': 1}),
    1307: ({'image': 0}, {'IMAGE': 0}),
    1308: ({'image': 0}, {'IMAGE': 0}),
    1309: ({'pixels': 0, 'vae': 1}, {'LATENT': 0}),
    1310: ({'clip': 0}, {'CONDITIONING': 0}),
    1311: ({'conditioning_to': 0, 'conditioning_from': 1}, {'CONDITIONING': 0}),
    1312: ({'conditioning': 0}, {'CONDITIONING': 0}),
    1313: ({'model': 0, 'positive': 1, 'negative': 2, 'latent_image': 3}, {'LATENT': 0}),
    1314: ({'samples': 0, 'vae': 1}, {'IMAGE': 0}),
    1315: ({'upscale_model': 0, 'image': 1}, {'IMAGE': 0}),
    1316: ({'images': 0}, {'images': 0}),
    1317: ({'images': 0}, {'images': 0}),
    1320: ({'clip': 0}, {'CONDITIONING': 0}),
    1321: ({'conditioning_to': 0, 'conditioning_from': 1}, {'CONDITIONING': 0}),
    1322: ({'conditioning': 0}, {'CONDITIONING': 0}),
    1323: ({'model': 0, 'positive': 1, 'negative': 2, 'latent_image': 3}, {'LATENT': 0}),
    1324: ({'samples': 0, 'vae': 1}, {'IMAGE': 0}),
    1325: ({'upscale_model': 0, 'image': 1}, {'IMAGE': 0}),
    1326: ({'images': 0}, {'images': 0}),
    1327: ({'images': 0}, {'images': 0}),
}


def in_map(nid):
    m = {}
    for l in LINKS:
        if l[3] == nid:
            m[l[4]] = l[0]
    names = {v: k for k, v in NODE_PORTS[nid][0].items()}
    return {names[slot]: lid for slot, lid in m.items() if slot in names}


def out_map(nid):
    m = {}
    for l in LINKS:
        if l[1] == nid:
            m.setdefault(l[2], []).append(l[0])
    names = {v: k for k, v in NODE_PORTS[nid][1].items()}
    return {names[slot]: lids for slot, lids in m.items() if slot in names}


# ---------------------------------------------------------------- 节点
NEW = [
    # ── 身份层：底模 + 身份特征提示词 ──
    mk('CheckpointLoaderSimple', 1300, (7640, 1400), [315, 98], [CKPT],
       in_map(1300), out_map(1300), '身份锁 · 底模 FLUX 一体化 fp8'),
    mk('CLIPTextEncode', 1301, (7640, 2400), [430, 420], [LOCK_POS],
       in_map(1301), out_map(1301), '🔒 身份特征 LOCK（正脸/右脸共用）'),

    # ── 正脸结构锚 ──
    mk('LoadImage', 1302, (7640, 1560), [315, 314], [FACE_BASE, 'image'],
       in_map(1302), out_map(1302), '正脸锚源 wendeng_v23_face_base.png'),
    mk('ImageScale', 1303, (7990, 1580), [315, 130], ['lanczos', W_LOW, H_LOW, 'disabled'],
       in_map(1303), out_map(1303), '① 降采样 → 512×640（抹掉毛孔/发丝等高频细节）'),
    mk('ImageScale', 1304, (8330, 1580), [315, 130], ['lanczos', W, H, 'disabled'],
       in_map(1304), out_map(1304), '② 放回 1024×1280（细节不会回来 = 只留结构）'),
    mk('VAEEncode', 1305, (8660, 1600), [210, 46], None,
       in_map(1305), out_map(1305), '③ 结构锚 → latent（身份就锁在这里）'),

    # ── 右脸结构锚 ──
    mk('LoadImageOutput', 1306, (7640, 1920), [315, 314], [SIDE_BASE, 'image'],
       in_map(1306), out_map(1306), '右脸锚源 闻灯v23-脸部侧面c-成品（output/）'),
    mk('ImageScale', 1307, (7990, 1940), [315, 130], ['lanczos', W_LOW, H_LOW, 'disabled'],
       in_map(1307), out_map(1307), '① 降采样 → 512×640'),
    mk('ImageScale', 1308, (8330, 1940), [315, 130], ['lanczos', W, H, 'disabled'],
       in_map(1308), out_map(1308), '② 放回 1024×1280'),
    mk('VAEEncode', 1309, (8660, 1960), [210, 46], None,
       in_map(1309), out_map(1309), '③ 结构锚 → latent（右脸身份锁）'),

    # ── 正脸支路 ──
    mk('CLIPTextEncode', 1310, (8100, 2400), [430, 300], [FRONT_POS],
       in_map(1310), out_map(1310), '🎨 正脸·表现层（允许 FLUX 重画质感）'),
    mk('ConditioningConcat', 1311, (8560, 2400), [315, 46], None,
       in_map(1311), out_map(1311), '身份段 + 正脸表现段'),
    mk('FluxGuidance', 1312, (8560, 2540), [315, 58], [GUIDANCE],
       in_map(1312), out_map(1312), 'FluxGuidance'),
    mk('KSampler', 1313, (8900, 2400), [315, 262], [SEED, 'fixed', STEPS, CFG, 'euler', 'simple', DENOISE],
       in_map(1313), out_map(1313), '正脸 KSampler（d%.2f = 表现层自由度旋钮）' % DENOISE),
    mk('VAEDecode', 1314, (9250, 2400), [210, 46], None, in_map(1314), out_map(1314)),
    mk('ImageUpscaleWithModel', 1315, (9250, 2500), [315, 46], None,
       in_map(1315), out_map(1315)),
    mk('SaveImage', 1316, (9600, 2300), [340, 420], ['闻灯Flux身份锁-正脸-草稿'],
       in_map(1316), out_map(1316)),
    mk('SaveImage', 1317, (9600, 2820), [340, 420], ['闻灯Flux身份锁-正脸-成品'],
       in_map(1317), out_map(1317)),

    # ── 右脸支路 ──
    mk('CLIPTextEncode', 1320, (8100, 3500), [430, 300], [RIGHT_POS],
       in_map(1320), out_map(1320), '🎨 右脸·表现层（允许 FLUX 重画质感）'),
    mk('ConditioningConcat', 1321, (8560, 3500), [315, 46], None,
       in_map(1321), out_map(1321), '身份段 + 右脸表现段'),
    mk('FluxGuidance', 1322, (8560, 3640), [315, 58], [GUIDANCE],
       in_map(1322), out_map(1322), 'FluxGuidance'),
    mk('KSampler', 1323, (8900, 3500), [315, 262], [SEED, 'fixed', STEPS, CFG, 'euler', 'simple', DENOISE],
       in_map(1323), out_map(1323), '右脸 KSampler（d%.2f）' % DENOISE),
    mk('VAEDecode', 1324, (9250, 3500), [210, 46], None, in_map(1324), out_map(1324)),
    mk('ImageUpscaleWithModel', 1325, (9250, 3600), [315, 46], None,
       in_map(1325), out_map(1325)),
    mk('SaveImage', 1326, (9600, 3400), [340, 420], ['闻灯Flux身份锁-右脸-草稿'],
       in_map(1326), out_map(1326)),
    mk('SaveImage', 1327, (9600, 3920), [340, 420], ['闻灯Flux身份锁-右脸-成品'],
       in_map(1327), out_map(1327)),
]

# ---------------------------------------------------------------- 组框：扩大原 Flux 组
hit = None
for g in wf.get('groups', []):
    if GROUP_MATCH in g.get('title', ''):
        hit = g
        break
if hit is None:
    print('★ 找不到 Flux 文生图组 —— 退出。')
    sys.exit(1)
old_box = list(hit['bounding'])
hit['bounding'] = list(GROUP_BOX)
hit['title'] = GROUP_TITLE
print('组框：%s → %s' % (old_box, GROUP_BOX))

wf['nodes'].extend(NEW)
wf['links'].extend([list(l) for l in LINKS])
wf['last_node_id'] = max([wf.get('last_node_id', 0)] + NEW_IDS)
wf['last_link_id'] = max([wf.get('last_link_id', 0)] + [l[0] for l in LINKS])
wf['id'] = str(uuid.uuid4())

print('\n追加 %d 个节点 / %d 条连线' % (len(NEW), len(LINKS)))
print('现共：节点 %d  链接 %d  分组 %d   新 id = %s'
      % (len(wf['nodes']), len(wf['links']), len(wf['groups']), wf['id']))

# ---------------------------------------------------------------- 本地自检
from wf_api import build_api, deps, find_outputs, WIDGETS   # noqa: E402

api, titles = build_api(wf)
unsup = sorted({n['type'] for n in wf['nodes'] if n['type'] not in WIDGETS})
print('\n--- 本地自检 ---')
print('可转换节点 %d / %d' % (len(api), len(wf['nodes'])))
print('⚠️ 未登记类型（会被静默跳过）：%s' % unsup if unsup else '节点类型登记 ✔ 全部可转换')

bad = 0
for tok, kind in [('闻灯Flux身份锁-正脸', '草稿'), ('闻灯Flux身份锁-正脸', '成品'),
                  ('闻灯Flux身份锁-右脸', '草稿'), ('闻灯Flux身份锁-右脸', '成品')]:
    hits = find_outputs(api, tok, kind)
    print('  %-22s %-4s → %s' % (tok, kind, [h[1] for h in hits]))
    for nid, pfx in hits:
        keep = deps(api, [nid])
        names = {api[k]['class_type'] for k in keep}
        need = {'CheckpointLoaderSimple', 'KSampler', 'VAEDecode', 'SaveImage',
                'VAEEncode', 'ImageScale', 'CLIPTextEncode'}
        if not need <= names or not ({'LoadImage', 'LoadImageOutput'} & names):
            print('    ★ 断链：缺 %s' % (need - names))
            bad += 1
        else:
            print('    ✔ 依赖链 %d 个节点完整' % len(keep))
        if 'ConditioningConcat' in names:
            print('       身份拼接 ✔（身份段 + 表现段）')
        if 'LoadImageOutput' in names:
            print('       右脸锚 = LoadImageOutput（读 output/）')

# 右脸锚源是否真的存在于 output/
try:
    import urllib.request as _u
    files = json.loads(_u.urlopen(_u.Request(B + '/internal/files/output', method='GET'),
                                  timeout=120, context=ctx).read())
    names = [str(f).split(' ')[0] for f in files]
    print('\n右脸锚源 `%s` → %s' % (SIDE_BASE, '在 output/ ✔' if SIDE_BASE in names else '★ 不在 output/！'))
except Exception as e:
    print('\n（跳过 output 清单校验：%s）' % e)

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


def req(method, data=None, ctype=None, timeout=600, url=None):
    h = {}
    if ctype:
        h['Content-Type'] = ctype
    return urllib.request.urlopen(urllib.request.Request(url or (B + u), data=data, headers=h,
                                                         method=method),
                                  timeout=timeout, context=ctx).read()


print('\n--- 备份服务器现版 ---')
bak = os.path.join(WFDIR, '_backup_identitylock_%s.json' % time.strftime('%m%d-%H%M%S'))
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
print('  服务器版 id = %s' % back.get('id'))
print('  节点 %d  链接 %d  分组 %d' % (len(back['nodes']), len(back['links']), len(back['groups'])))
for g in back.get('groups', []):
    print('    -', g['title'])
outs = [n['widgets_values'][0] for n in back['nodes']
        if n['type'] == 'SaveImage' and n.get('widgets_values')]
print('  输出共 %d 个：' % len(outs))
for o in outs:
    print('    *', o)
newout = [o for o in outs if o.startswith('闻灯Flux身份锁')]
print('  新增身份锁输出 %d 个 %s' % (len(newout), '✔' if len(newout) == 4 else '★ 数量不对！'))
print('\n跑图命令（一次只跑一条支路）：')
print('  python run_wf.py "%s" "闻灯Flux身份锁-正脸" draft' % NAME)
print('  python run_wf.py "%s" "闻灯Flux身份锁-右脸" draft' % NAME)
