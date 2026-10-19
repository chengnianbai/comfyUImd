# -*- coding: utf-8 -*-
"""由 v15 生成 v16

v15 遗留问题 -> v16 对策：
  1) 全身图手插兜（长风衣+站姿的强先验，正向 arms/hands at sides 压不住）
     -> 改用「给手一个动作」：让他**手里拿着账簿**。
        这同时落下了锚点 #12「手里经常拿受潮小账簿」——一举两得。
  2) 全身图里衬衫退化成圆领 T 恤（被风衣遮住只露一小块领口）
     -> 加 "open coat"，让风衣敞开、露出衬衫前襟与领子。
  3) 负向补 "pockets"，进一步压制插兜。
"""
SRC = r'D:\xiaobai-claude code\comfyUImd\_scripts\gen_wendeng_v15.py'
DST = r'D:\xiaobai-claude code\comfyUImd\_scripts\gen_wendeng_v16.py'
t = open(SRC, encoding='utf-8').read()

REPS = [
    # 1) + 2) 手里拿账簿（锚点 #12）+ 风衣敞开露出衬衫
    ('"faded blue collared shirt, " + COAT + ", old worn shoes")',
     '"faded blue collared shirt, " + COAT + ", old worn shoes, "\n'
     '          "holding old ledger, open coat")'),
    # 3) 负向补 pockets
    ('contrapposto, wide stance, legs apart, walking, leaning, "',
     'contrapposto, wide stance, legs apart, walking, leaning, pockets, "'),
    # 版本号
    ('else "v15"', 'else "v16"'),
    ('gen_wendeng_v15.py [TAG]', 'gen_wendeng_v16.py [TAG]'),
    ('设定图 v15 —— 对照', '设定图 v16 —— 对照'),
]
for a, b in REPS:
    if a not in t:
        raise SystemExit('未匹配: ' + a[:70])
    t = t.replace(a, b)

open(DST, 'w', encoding='utf-8').write(t)
print('v16 written ->', DST)
