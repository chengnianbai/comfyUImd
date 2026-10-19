# -*- coding: utf-8 -*-
"""拼对比图：正脸 + 三次左脸（不同词版本）"""
import os, sys
from PIL import Image, ImageDraw

D = r"D:\xiaobai-claude code\comfyUImd\系列-夜市百相簿\02-角色\闻灯\设定图\_diag_2style"
items = [
    ("闻灯Kontext统一正脸-成品_00026_.png", "FRONT 1043 (8714)"),
    ("闻灯主图-左侧脸-成品_00040_.png", "LEFT 截断版 (4663)"),
    ("闻灯主图-左侧脸-成品_00041_.png", "LEFT 你补全版 (6271)"),
    ("闻灯主图-左侧脸-成品_00042_.png", "LEFT 再改版 (5961)"),
]
W = 400
imgs = []
for fn, lab in items:
    p = os.path.join(D, fn)
    im = Image.open(p).convert("RGB")
    h = int(im.height * W / im.width)
    imgs.append((im.resize((W, h), Image.LANCZOS), lab, im.size))

H = max(i[0].height for i in imgs)
sheet = Image.new("RGB", (W * len(imgs), H + 34), (255, 255, 255))
dr = ImageDraw.Draw(sheet)
for k, (im, lab, orig) in enumerate(imgs):
    sheet.paste(im, (k * W, 34))
    dr.text((k * W + 6, 6), "%s  %dx%d" % (lab, orig[0], orig[1]), fill=(0, 0, 0))
    dr.line([(k * W, 0), (k * W, H + 34)], fill=(200, 200, 200))
out = os.path.join(D, "_sheet_4up.png")
sheet.save(out)
print("saved", out, sheet.size)
