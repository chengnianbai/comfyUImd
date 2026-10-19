# -*- coding: utf-8 -*-
"""从 v20 生成 v21：给每个侧向单独加强制方位的负向（N2 段还有余量，把方位词塞进 N2）"""
p = r'D:\xiaobai-claude code\comfyUImd\_scripts\gen_wendeng_v20.py'
t = open(p, encoding='utf-8').read()

REPS = [
    ('"""闻灯 脸部左右侧脸 —— 与已确认的 v13 正脸保持同一个人',
     '"""闻灯 脸部左右侧脸 v21 —— 与已确认的 v13 正脸保持同一个人'),
    ('用法： python gen_wendeng_v20.py [TAG] [SEED] [--check]',
     'v20 -> v21：SDXL 对方位词不敏感，两张侧脸都朝了同一侧。\n'
     '  本版给每个视角单独加强制方位负向（复用 N2 段的剩余 token 余量）。\n'
     '用法： python gen_wendeng_v21.py [TAG] [SEED] [--check]'),
    # 视角定义：带各自的负向追加
    ('''VIEWS = [
    ("脸部左向", "profile view, facing right, three quarter turned, " + FACE_A_BODY),
    ("脸部右向", "profile view, facing left, three quarter turned, " + FACE_A_BODY),
]''',
     '''VIEWS = [
    # 朝左：脸转向画面左侧（看到角色右脸）
    ("脸部朝左",
     "side profile view, 90 degree side view, face turned to the left, looking left, "
     "single eye visible, pure profile, " + FACE_A_BODY,
     "facing right, looking right, three quarter view, front view, both eyes visible"),
    # 朝右：脸转向画面右侧（看到角色左脸）
    ("脸部朝右",
     "side profile view, 90 degree side view, face turned to the right, looking right, "
     "single eye visible, pure profile, " + FACE_A_BODY,
     "facing left, looking left, three quarter view, front view, both eyes visible"),
]'''),
    # 校验循环适配三元组
    ('''for vn, a in VIEWS:
    n = tok(a)
    print("  %-8s A %3d/75 %s" % (vn, n, "OK" if n <= 75 else "★超限★"))
    if n > 75:
        bad.append(vn + "A")''',
     '''for vn, a, nx in VIEWS:
    for nm, s in [("A", a), ("N2+", N2 + ", " + nx)]:
        n = tok(s)
        print("  %-8s %-4s %3d/75 %s" % (vn, nm, n, "OK" if n <= 75 else "★超限★"))
        if n > 75:
            bad.append(vn + nm)'''),
    # 提交时用各自的负向
    ('''for vn, A in VIEWS:
    pid = post("/prompt", {"prompt": build(vn, A, FACE_B, N3_FACE), "client_id": str(uuid.uuid4())})["prompt_id"]''',
     '''for vn, A, NX in VIEWS:
    pid = post("/prompt", {"prompt": build(vn, A, FACE_B, N3_FACE, N2 + ", " + NX),
                           "client_id": str(uuid.uuid4())})["prompt_id"]'''),
    # build 支持覆盖 N2
    ('def build(prefix, A, B, N3):', 'def build(prefix, A, B, N3, N2_OVERRIDE=None):'),
    ('"7": {"class_type": "CLIPTextEncode", "inputs": {"text": N2, "clip": CLIP}},',
     '"7": {"class_type": "CLIPTextEncode", "inputs": {"text": N2_OVERRIDE or N2, "clip": CLIP}},'),
    ('TAG = ARGS[0] if len(ARGS) > 0 else "v20"', 'TAG = ARGS[0] if len(ARGS) > 0 else "v21"'),
]

for a, b in REPS:
    assert a in t, '未匹配: ' + a[:60]
    t = t.replace(a, b, 1)

open(r'D:\xiaobai-claude code\comfyUImd\_scripts\gen_wendeng_v21.py', 'w', encoding='utf-8').write(t)
print('v21 已生成')
