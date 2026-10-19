# -*- coding: utf-8 -*-
"""从 v17 生成 v18：道具全部移出角色设定图（用户要求：账簿等道具后续单独生成）"""
p = r'D:\xiaobai-claude code\comfyUImd\_scripts\gen_wendeng_v17.py'
t = open(p, encoding='utf-8').read()

REPS = [
    # ---- 文档头 ----
    ('"""闻灯多视角角色设定图 v17 —— 对照《角色视觉锚点-锁定.md》逐条回锚点',
     '"""闻灯多视角角色设定图 v18 —— 对照《角色视觉锚点-锁定.md》逐条回锚点'),
    ('用法： python gen_wendeng_v17.py [TAG] [SEED] [--check]',
     'v18 修正（用户指令：道具不属于角色设定图）：\n'
     '  1) 去掉 holding ledger / hands in front —— 账簿、朱砂粉盒等道具后续单独生成，\n'
     '     不进入角色 5 视角设定图（锚点 #12 相应降级为"道具，另片生成"）\n'
     '  2) 手插兜在 v16/v17 都没压住 -> 改「空手自然垂在身侧 + 禁止把手藏起来」双管\n'
     '  3) 补回 v17 漏掉的体型锚点 #3（lean wiry build, broad shoulders）\n'
     '  4) 负向补 holding object / tucking hand，防止模型自己"造"道具\n'
     '用法： python gen_wendeng_v18.py [TAG] [SEED] [--check]'),

    # ---- 姿势：空手垂在身侧 ----
    ('STAND = "standing straight, arms at sides, hands at sides, feet together"',
     'STAND = ("standing straight, arms hanging down at sides, empty hands, hands visible, "\n'
     '         "feet together, no pockets")'),

    # ---- A 段：去道具 + 补男性/体型锚点 ----
    ('BODY_A = ("1boy, 24 year old east asian man, " + HAIR + ", "\n'
     '          "faded blue collared shirt, " + COAT + ", open coat, "\n'
     '          "holding ledger, hands in front")',
     'BODY_A = ("1boy, 24 year old east asian man, masculine face, strong jaw, " + HAIR + ", "\n'
     '          "faded blue collared shirt, " + COAT + ", open coat")'),

    # ---- B 段：补体型锚点 #3 ----
    ('BODY_B = ("1boy, male, tired eyes, thick eyebrows, stubble, weathered skin, "\n'
     '          "detailed skin texture, skin pores, film grain, worn wrinkled clothes, "\n'
     '          "open coat, dark trousers, old worn shoes, " + BGD + ", even lighting, "\n'
     '          "sharp focus, photorealistic")',
     'BODY_B = ("1boy, male, lean wiry build, broad shoulders, tired eyes, thick eyebrows, "\n'
     '          "stubble, weathered skin, detailed skin texture, skin pores, film grain, "\n'
     '          "worn wrinkled clothes, open coat, dark trousers, old worn shoes, "\n'
     '          + BGD + ", even lighting, sharp focus, photorealistic")'),

    # ---- 负向：禁藏手 + 禁自造道具 ----
    ('N3_FULL = ("close-up, cropped, hands in pockets, hands on hips, arms crossed, "\n'
     '           "contrapposto, wide stance, legs apart, pockets, hand in pocket, "',
     'N3_FULL = ("close-up, cropped, hands in pockets, hands behind back, hands hidden, "\n'
     '           "hand tucked in pocket, hands on hips, arms crossed, "\n'
     '           "holding object, holding book, holding paper, prop, "\n'
     '           "contrapposto, wide stance, legs apart, pockets, hand in pocket, "'),
]

for a, b in REPS:
    assert a in t, '未匹配: ' + a[:70]
    t = t.replace(a, b, 1)

t = t.replace('TAG = ARGS[0] if len(ARGS) > 0 else "v17"', 'TAG = ARGS[0] if len(ARGS) > 0 else "v18"')

open(r'D:\xiaobai-claude code\comfyUImd\_scripts\gen_wendeng_v18.py', 'w', encoding='utf-8').write(t)
print('v18 已生成')
