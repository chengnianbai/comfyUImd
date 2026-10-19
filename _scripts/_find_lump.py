# -*- coding: utf-8 -*-
"""无用监督定位基图上的肉瘤：去趋势的镜像不对称 + 候选点标注图

原理
    人脸的左右镜像差异里，「全局」部分来自光照方向/头发/头部姿态（低频），
    「局部」异常（如内眼角的肉瘤）是高频的小块凸起。
    做法： d = |I - mirror(I)| ； d_low = 大半径模糊(d) 当作全局场；
           residual = d / (d_low + eps)  → 局部异常会突出出来。
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
ROOT = r"D:\xiaobai-claude code\comfyUImd"
OUT = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "base_repair")
p = os.path.join(OUT, "base_original.png")
im = Image.open(p).convert("RGB")
W, H = im.size
g = np.asarray(im.convert("L")).astype(np.float32)

d = np.abs(g - g[:, ::-1])
d_img = Image.fromarray(np.clip(d, 0, 255).astype(np.uint8))
# 去掉靠近中轴 / 边缘的不可靠区
d_low = np.asarray(d_img.filter(ImageFilter.GaussianBlur(60))).astype(np.float32)
res = d / (d_low + 8.0)

# 只在眼部横带找（眼在头肩像的中上部）
Y0, Y1 = int(H*0.22), int(H*0.55)
band = res[Y0:Y1, :].copy()
# 抑制中轴附近（镜像差天然小）与极边缘
cx = W/2
for x in range(W):
    if abs(x-cx) < W*0.04 or x < W*0.08 or x > W*0.92:
        band[:, x] = 0

# 每 24px 分块取块内最大，聚一个候选
cands = []
B = 24
for by in range(0, band.shape[0]-B, B):
    for bx in range(0, band.shape[1]-B, B):
        cands.append((float(band[by:by+B, bx:bx+B].max()), bx+B//2, by+B//2+Y0))
cands.sort(reverse=True)
print("去趋势后的候选点（值越大越像局部异常）:")
for v, x, y in cands[:8]:
    print("   score=%.2f  (x=%d, y=%d)" % (v, x, y))

# 在中轴两侧各取最强的一个（左半与右半）
left = [c for c in cands if c[1] < cx][:1]
right = [c for c in cands if c[1] >= cx][:1]
print("\n左半最强: %s" % (left[0] if left else None,))
print("右半最强: %s" % (right[0] if right else None,))

# 标注图：整图 + 放大眼带，标出前 3 个候选
marks = cands[:3]
ann = im.copy(); dr = ImageDraw.Draw(ann)
for i, (v, x, y) in enumerate(marks):
    dr.ellipse([x-26, y-26, x+26, y+26], outline=(255, 0, 0), width=3)
    dr.text((x+28, y-30), "%d:%.1f" % (i+1, v), fill=(255, 0, 0))
o1 = os.path.join(OUT, "_候选点-整图.png"); ann.save(o1); print("\nsaved", o1)

X0, Y0b, X1, Y1b = int(W*0.15), int(H*0.20), int(W*0.92), int(H*0.55)
c = ann.crop((X0, Y0b, X1, Y1b))
Z = 3
big = c.resize((c.size[0]*Z, c.size[1]*Z), Image.LANCZOS)
db = ImageDraw.Draw(big)
for gx in range(0, W, 50):
    if X0 <= gx <= X1:
        px = (gx-X0)*Z
        db.line([(px, 0), (px, big.size[1])], fill=(0,160,0), width=1); db.text((px+2, 2), str(gx), fill=(0,160,0))
for gy in range(0, H, 50):
    if Y0b <= gy <= Y1b:
        py = (gy-Y0b)*Z
        db.line([(0, py), (big.size[0], py)], fill=(0,160,0), width=1); db.text((2, py+2), str(gy), fill=(0,160,0))
o2 = os.path.join(OUT, "_候选点-眼部放大带网格.png"); big.save(o2); print("saved", o2, big.size)
big.resize((900, int(900*big.size[1]/big.size[0])), Image.LANCZOS).save(
    r"C:\Users\ADMINI~1\AppData\Local\Temp\commandcode\D--xiaobai-claude-code-comfyUImd\df01e59d-0f96-4c37-9495-d9508dda8d9a\scratchpad\cand.png", optimize=True)
