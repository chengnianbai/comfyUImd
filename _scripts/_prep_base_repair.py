# -*- coding: utf-8 -*-
"""把基图 wendeng_face_base.png 拉下来，做「带像素坐标网格」的眼部放大图，用于定位肉瘤

目的：确认肉瘤的精确像素坐标后，做一次局部修补（从邻近干净皮肤克隆一小块 + 羽化边缘），
      再把修补好的图以同名覆盖上传回去 —— 这样 L1/L2/L3 全都会跟着干净，且不新增任何节点。
"""
import os, sys, ssl, json, urllib.request, urllib.parse
import numpy as np
from PIL import Image, ImageDraw
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
if not BASE:
    print("★ 先设 COMFY_BASE"); sys.exit(4)
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
ROOT = r"D:\xiaobai-claude code\comfyUImd"
OUT = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "base_repair")
SC = r"C:\Users\ADMINI~1\AppData\Local\Temp\commandcode\D--xiaobai-claude-code-comfyUImd\df01e59d-0f96-4c37-9495-d9508dda8d9a\scratchpad"
os.makedirs(OUT, exist_ok=True)

FN = "wendeng_face_base.png"
q = urllib.parse.urlencode({"filename": FN, "subfolder": "", "type": "input"})
b = urllib.request.urlopen(BASE + "/view?" + q, timeout=300, context=ctx).read()
p = os.path.join(OUT, "base_original.png")
open(p, "wb").write(b)
im = Image.open(p).convert("RGB")
W, H = im.size
print("基图 %s  %dx%d  %.1f KB" % (FN, W, H, len(b) / 1024))

# 眼部横带（上中部），放大 3 倍并叠加 25px 网格（坐标是原图像素坐标）
X0, Y0, X1, Y1 = int(W*0.15), int(H*0.22), int(W*0.90), int(H*0.52)
c = im.crop((X0, Y0, X1, Y1))
Z = 3
big = c.resize((c.size[0]*Z, c.size[1]*Z), Image.LANCZOS)
dr = ImageDraw.Draw(big)
for gx in range(0, W, 25):
    if X0 <= gx <= X1:
        px = (gx - X0) * Z
        major = (gx % 100 == 0)
        dr.line([(px, 0), (px, big.size[1])], fill=(255,0,0) if major else (255,180,180), width=2 if major else 1)
        if major: dr.text((px+3, 3), str(gx), fill=(255,0,0))
for gy in range(0, H, 25):
    if Y0 <= gy <= Y1:
        py = (gy - Y0) * Z
        major = (gy % 100 == 0)
        dr.line([(0, py), (big.size[0], py)], fill=(0,80,255) if major else (170,200,255), width=2 if major else 1)
        if major: dr.text((3, py+3), str(gy), fill=(0,80,255))
o = os.path.join(OUT, "_眼部网格-原图坐标.png"); big.save(o)
print("saved", o, big.size)

# 缩一版给视觉试（不超过 ~900 宽）
s = big.resize((900, int(900*big.size[1]/big.size[0])), Image.LANCZOS)
s.save(os.path.join(SC, "base_grid.png"), optimize=True)

# 顺带：镜像不对称热力图（只在上半部），给个"异常点"的线索
g = np.asarray(im.convert("L")).astype(np.float32)
mir = g[:, ::-1]
d = np.abs(g - mir)
band = d[int(H*0.20):int(H*0.55), int(W*0.08):int(W*0.92)]
print("\n镜像不对称（仅供线索）：该横带内 diff 均值 %.1f，最大 %.0f" % (band.mean(), band.max()))
ys, xs = np.unravel_index(np.argmax(band), band.shape)
print("  最大差异点 ≈ 原图坐标 (x=%d, y=%d)" % (xs + int(W*0.08), ys + int(H*0.20)))
# 取前 5 个局部极值（粗略：每 30px 分块取块内最大）
best = []
for by in range(0, band.shape[0]-30, 30):
    for bx in range(0, band.shape[1]-30, 30):
        best.append((band[by:by+30, bx:bx+30].max(), bx + int(W*0.08), by + int(H*0.20)))
best.sort(reverse=True)
print("  前 5 个分块最大差异点：")
for v, x, y in best[:5]:
    print("     diff=%.0f  (x=%d, y=%d)" % (v, x, y))
