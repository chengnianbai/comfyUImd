# -*- coding: utf-8 -*-
"""C 方案（换干净锚图）新旧对照四联 + 像素差"""
import os
from PIL import Image, ImageChops, ImageDraw

ROOT = r"D:\xiaobai-claude code\comfyUImd\系列-夜市百相簿\02-角色\闻灯\设定图"
OLD = os.path.join(ROOT, "_diag_2style")
NEW = os.path.join(ROOT, "_exp_0923", "c1_clean_anchor")

PAIRS = [
    ("旧正脸 00027（锚00009·脏）", os.path.join(OLD, "闻灯Kontext统一正脸-成品_00027_.png"),
     "新正脸 00028（锚00010·干净）", os.path.join(NEW, "闻灯Kontext统一正脸-成品_00028_.png")),
    ("旧左脸 00043", os.path.join(OLD, "闻灯主图-左侧脸-成品_00043_.png"),
     "新左脸 00044", os.path.join(NEW, "闻灯主图-左侧脸-成品_00044_.png")),
]

CW, CH = 400, 538
GAP, LBL, PAD = 20, 26, 18
W = CW * 2 + GAP + PAD * 2
H = (CH + LBL) * 2 + GAP + PAD * 2
sheet = Image.new("RGB", (W, H), (255, 255, 255))
dr = ImageDraw.Draw(sheet)

for r, (lt, lp, rt, rp) in enumerate(PAIRS):
    for c, (txt, p) in enumerate([(lt, lp), (rt, rp)]):
        x = PAD + c * (CW + GAP)
        y = PAD + r * (CH + LBL + GAP)
        dr.text((x + 2, y + 6), txt, fill=(30, 30, 30))
        if os.path.exists(p):
            im = Image.open(p).convert("RGB").resize((CW, CH))
            sheet.paste(im, (x, y + LBL))
        else:
            dr.rectangle([x, y + LBL, x + CW, y + LBL + CH], outline=(220, 90, 90))
            dr.text((x + 10, y + LBL + 10), "MISSING", fill=(220, 90, 90))
    a = PAIRS[r][1]; b = PAIRS[r][3]
    if os.path.exists(a) and os.path.exists(b):
        A = Image.open(a).convert("RGB"); B = Image.open(b).convert("RGB")
        if A.size == B.size:
            d = ImageChops.difference(A, B)
            px = list(d.getdata()); n = len(px)
            mean = sum(sum(p) for p in px) / (n * 3)
            big = sum(1 for p in px if max(p) > 40) / n * 100
            print("第%d行  平均差=%.2f  明显不同像素=%.1f%%" % (r + 1, mean, big))

out = os.path.join(NEW, "_sheet_old_vs_new.png")
sheet.save(out)
print("saved", out, sheet.size)
