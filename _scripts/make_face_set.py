# -*- coding: utf-8 -*-
"""整理闻灯脸部素材集：正脸基准 + 左右侧脸（侧脸用镜像保证是同一个人）

背景：SDXL 对方位词不敏感，连续两版（v20/v21）生成的侧脸都朝同一侧，
      靠提示词拿不到"另一侧"。镜像是最可靠的做法——数学上保证是同一个人。
代价（如实说明）：痣的那一侧会跟着翻转，发缝方向也会翻。
"""
import os, shutil, glob
from PIL import Image

BASE = r"D:\xiaobai-claude code\comfyUImd\系列-夜市百相簿/02-角色/闻灯/设定图"
SRC_FACE = os.path.join(BASE, "多视角")
SRC_SIDE = os.path.join(BASE, "脸部")
DST = os.path.join(BASE, "脸部素材集")
os.makedirs(DST, exist_ok=True)

# 1) 已确认的正脸基准（资产里保留的那两张）
plan_copy = [
    (os.path.join(SRC_FACE, "闻灯v13-脸部正面-成品_00001_.png"), "闻灯-正脸-已确认_成品.png"),
    (os.path.join(SRC_FACE, "闻灯v13-脸部正面-草稿_00001_.png"), "闻灯-正脸-已确认_草稿.png"),
    # 2) 生成的近正侧脸（朝画面右）
    (os.path.join(SRC_SIDE, "闻灯v20-脸部右向-成品_00001_.png"), "闻灯-侧脸-朝右_成品.png"),
    (os.path.join(SRC_SIDE, "闻灯v20-脸部右向-草稿_00001_.png"), "闻灯-侧脸-朝右_草稿.png"),
]
for s, d in plan_copy:
    if not os.path.isfile(s):
        print("缺文件:", s); continue
    shutil.copy2(s, os.path.join(DST, d))
    print("复制 ->", d)

# 3) 镜像出另一侧
for s, d in [("闻灯-侧脸-朝右_成品.png", "闻灯-侧脸-朝左_镜像_成品.png"),
             ("闻灯-侧脸-朝右_草稿.png", "闻灯-侧脸-朝左_镜像_草稿.png")]:
    p = os.path.join(DST, s)
    if not os.path.isfile(p):
        print("缺文件:", s); continue
    Image.open(p).transpose(Image.FLIP_LEFT_RIGHT).save(os.path.join(DST, d))
    print("镜像 ->", d)

print()
for f in sorted(os.listdir(DST)):
    fp = os.path.join(DST, f)
    im = Image.open(fp)
    print("  %-34s %-12s %8.1f KB" % (f, "%dx%d" % im.size, os.path.getsize(fp) / 1024))
