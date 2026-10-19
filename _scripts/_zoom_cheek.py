# -*- coding: utf-8 -*-
"""1:1 局部质感比对：锚图00009 vs 正脸产出 vs 侧脸产出（同一物理尺度）"""
import os
from PIL import Image, ImageDraw

BASE = r"D:\xiaobai-claude code\comfyUImd\系列-夜市百相簿\02-角色\闻灯\设定图"
# (路径, 标签, 归一化裁剪框 x0,y0,x1,y1, 源图相对 880x1184 的像素倍率)
items = [
    (os.path.join(BASE, "闻灯正脸确定/闻灯-脸部正面-成品_00009_.png"),
     "ANCHOR 00009  锚图/身份源", (0.26, 0.40, 0.54, 0.62), 2.036),
    (os.path.join(BASE, "_diag_2style/闻灯Kontext统一正脸-成品_00026_.png"),
     "FRONT 00026  正脸产出", (0.50, 0.40, 0.78, 0.62), 1.0),
    (os.path.join(BASE, "_diag_2style/闻灯主图-左侧脸-成品_00042_.png"),
     "LEFT 00042  侧脸产出", (0.40, 0.34, 0.68, 0.56), 1.0),
]
P = 330   # 1:1 显示尺寸（源像素）
panels = []
for p, lab, fr, scale in items:
    im = Image.open(p).convert("RGB")
    box = (int(fr[0] * im.width), int(fr[1] * im.height),
           int(fr[2] * im.width), int(fr[3] * im.height))
    c = im.crop(box)
    if scale > 1.5:                      # 锚图是 2 倍图 → 缩回来，保证与其他两张同物理尺度
        c = c.resize((c.width // 2, c.height // 2), Image.LANCZOS)
    c = c.resize((P, P), Image.LANCZOS)
    panels.append((c, lab, box, im.size))

sheet = Image.new("RGB", (P * 3, P + 46), (255, 255, 255))
dr = ImageDraw.Draw(sheet)
for k, (c, lab, box, size) in enumerate(panels):
    sheet.paste(c, (k * P, 46))
    dr.text((k * P + 6, 8), lab, fill=(0, 0, 0))
    dr.text((k * P + 6, 26), "src %dx%d  crop %s" % (size[0], size[1], box), fill=(90, 90, 90))
    dr.line([(k * P, 0), (k * P, P + 46)], fill=(190, 190, 190))
out = os.path.join(BASE, "_diag_2style", "_zoom_cheek.png")
sheet.save(out)
print("saved", out, sheet.size)
