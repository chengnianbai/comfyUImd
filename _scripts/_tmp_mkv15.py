# -*- coding: utf-8 -*-
"""由 v14 生成 v15（只替换差异行，避免整份重写）"""
SRC = r'D:\xiaobai-claude code\comfyUImd\_scripts\gen_wendeng_v14.py'
DST = r'D:\xiaobai-claude code\comfyUImd\_scripts\gen_wendeng_v15.py'
t = open(SRC, encoding='utf-8').read()

REPS = [
    # 切换到新的远程实例
    ('BASE = "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016"',
     'BASE = "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016"'),
    # 锚点 #8「洗得发白的蓝色旧衬衫」：v14 出成圆领 T 恤 -> 必须明确是有领衬衫
    ('"faded blue shirt, " + COAT + ", old worn shoes"',
     '"faded blue collared shirt, " + COAT + ", old worn shoes"'),
    # 姿势：v14 仍手插兜（长风衣+站姿的强先验）-> 正向把「手在身侧」说死
    ('STAND = "standing straight, arms at sides, feet together"',
     'STAND = "standing straight, arms at sides, hands at sides, feet together"'),
    # 脸部负向：v14 的 many moles 连皮肤质感一起压掉了 -> 改成定点压制
    ('freckles, many moles, ',
     'freckles, mole on cheek, mole on forehead, '),
    # 文档头
    ('gen_wendeng_v14.py [TAG]', 'gen_wendeng_v15.py [TAG]'),
    ('v14 —— 对照', 'v15 —— 对照'),
    ('v13 偏差 -> v14 修正', 'v13、v14 偏差 -> v15 修正'),
    ('else "v14"', 'else "v15"'),
    # v15 相对 v14 的改动说明
    ('  4) 鞋：v13 精简时误删 -> 锚点「便于湿地行走的旧鞋」-> 补 "old worn shoes"',
     '  4) 鞋：v13 精简时误删 -> 锚点「便于湿地行走的旧鞋」-> 补 "old worn shoes"\n'
     'v15 追加修正：\n'
     '  5) 衬衫：v14 的 "faded blue shirt" 出成圆领 T 恤 -> 锚点是「蓝色旧**衬衫**」\n'
     '     改 "faded blue collared shirt"（明确有领）\n'
     '  6) 姿势：v14 仍手插兜 -> STAND 补 "hands at sides"；负向保留 hands in pockets\n'
     '  7) 皮肤：v14 的负向 many moles 把毛孔一起压掉 -> 改定点压 mole on cheek/forehead'),
]
for a, b in REPS:
    if a not in t:
        raise SystemExit('未匹配: ' + a[:70])
    t = t.replace(a, b)

open(DST, 'w', encoding='utf-8').write(t)
print('v15 written ->', DST)
