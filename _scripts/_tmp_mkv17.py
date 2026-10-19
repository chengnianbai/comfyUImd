# -*- coding: utf-8 -*-
"""由 v16 生成 v17 —— 专攻「手插兜」

为什么这么顽固：SDXL 对「长风衣 + 正面站立」的先验就是双手插兜，
正向写 arms at sides / hands at sides、负向写 hands in pockets 都压不住。

v17 对策：不再跟先验硬碰，改成**给手一个明确的持物动作** ——
双手在身前拿账簿。这同时落地锚点 #12「手里经常拿受潮小账簿」。
token 不够，所以把鞋子描述从 A 段挪到 B 段，B 段再删掉重复的发型词。
"""
SRC = r'D:\xiaobai-claude code\comfyUImd\_scripts\gen_wendeng_v16.py'
DST = r'D:\xiaobai-claude code\comfyUImd\_scripts\gen_wendeng_v17.py'
t = open(SRC, encoding='utf-8').read()

OLD_A = '''BODY_A = ("1boy, solo, 24 year old east asian man, masculine, " + HAIR + ", "
          "faded blue collared shirt, " + COAT + ", old worn shoes, "
          "holding old ledger, open coat")'''
NEW_A = '''BODY_A = ("1boy, 24 year old east asian man, " + HAIR + ", "
          "faded blue collared shirt, " + COAT + ", open coat, "
          "holding ledger, hands in front")'''

OLD_B = '''BODY_B = ("1boy, male, short tousled hair, tired eyes, thick eyebrows, stubble, "
          "weathered skin, detailed skin texture, skin pores, film grain, "
          "worn wrinkled clothes, open coat, dark trousers, " + BGD + ", even lighting, "
          "sharp focus, photorealistic")'''
NEW_B = '''BODY_B = ("1boy, male, tired eyes, thick eyebrows, stubble, weathered skin, "
          "detailed skin texture, skin pores, film grain, worn wrinkled clothes, "
          "open coat, dark trousers, old worn shoes, " + BGD + ", even lighting, "
          "sharp focus, photorealistic")'''

REPS = [
    (OLD_A, NEW_A),
    (OLD_B, NEW_B),
    ('contrapposto, wide stance, legs apart, walking, leaning, pockets, "',
     'contrapposto, wide stance, legs apart, pockets, hand in pocket, "'),
    ('else "v16"', 'else "v17"'),
    ('gen_wendeng_v16.py [TAG]', 'gen_wendeng_v17.py [TAG]'),
    ('设定图 v16 —— 对照', '设定图 v17 —— 对照'),
]
for a, b in REPS:
    if a not in t:
        raise SystemExit('未匹配: ' + a[:80])
    t = t.replace(a, b)

open(DST, 'w', encoding='utf-8').write(t)
print('v17 written ->', DST)
