# -*- coding: utf-8 -*-
"""新词 vs 旧词 左右侧脸 + 正脸 四联"""
import os
from PIL import Image, ImageDraw

D = r"D:\xiaobai-claude code\comfyUImd\系列-夜市百相簿\02-角色\闻灯\设定图\_diag_2style"
items = [
    ("闻灯Kontext统一正脸-成品_00027_.png", "FRONT 00027"),
    ("闻灯主图-左侧脸-成品_00042_.png", "LEFT 00042 旧词"),
    ("闻灯主图-左侧脸-成品_00043_.png", "LEFT 00043 新词"),
    ("闻灯主图-右侧脸-成品_00044_.png", "RIGHT 00044 新词镜像"),
]
W = 400
panels = []
for fn, lab in items:
    im = Image.open(os.path.join(D, fn)).convert("RGB")
    h = int(im.height * W / im.width)
    panels.append((im.resize((W, h), Image.LANCZOS), lab))
H = max(p[0].height for p in panels)
sheet = Image.new("RGB", (W * len(panels), H + 30), (255, 255, 255))
dr = ImageDraw.Draw(sheet)
for k, (im, lab) in enumerate(panels):
    sheet.paste(im, (k * W, 30))
    dr.text((k * W + 6, 9), lab, fill=(0, 0, 0))
    dr.line([(k * W, 0), (k * W, H + 30)], fill=(200, 200, 200))
out = os.path.join(D, "_sheet_new_vs_old.png")
sheet.save(out)
print("saved", out, sheet.size)
