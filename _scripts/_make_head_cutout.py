# -*- coding: utf-8 -*-
"""② 的第一步：从已确认脸部图里抠出「头部」，输出带 alpha 的 PNG（供贴入全身图）

做法（用头发+肤色两个掩膜求并，比单一阈值稳）
    头发 = 灰度 < 80 的暗区（黑发）
    脸部 = R>G>B 且 R-B>15 的肤色区
    头部 bbox = 两者并集的 bbox（上=发顶，下=下巴）
    alpha = 一个贴合头部的圆角椭圆 + 羽化；边缘留一点内缩避免带进背景
输出：_头部抠图-<尺寸>.png（RGB + alpha），另存一张带棋盘底的可视化预览供人工检查。
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
ROOT = r"D:\xiaobai-claude code\comfyUImd"
BR = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "base_repair")
OUT = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "head_cutout")
os.makedirs(OUT, exist_ok=True)
SRC = os.path.join(BR, "_face_asset.png")
im = Image.open(SRC).convert("RGB")
W, H = im.size
a = np.asarray(im).astype(np.int16)
R, G, B = a[:,:,0], a[:,:,1], a[:,:,2]
gray = 0.299*R + 0.587*G + 0.114*B
hair = gray < 80
skin = (R > 90) & (R > G) & (G > B) & ((R - B) > 15)
m = hair | skin
print("脸部原图 %dx%d ；头发像素 %d ；肤色像素 %d" % (W, H, hair.sum(), skin.sum()))
ys, xs = np.nonzero(m)
if len(ys) == 0:
    print("★ 掩膜为空，退出"); sys.exit(1)
y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
print("合并掩膜 bbox = x%d..%d  y%d..%d  （宽%d 高%d）" % (x0, x1, y0, y1, x1-x0, y1-y0))

# 头部：上取发顶，下巴取"肤色区"的下沿（比头发下沿低）
sy = np.nonzero(skin.sum(axis=1) > W*0.01)[0]
chin = int(sy.max()) if len(sy) else y1
top = y0
# 左右：取头发+肤色在"眼睛以上到下巴"区间内的边界
band = m[top:chin+1]
bx = np.nonzero(band.sum(axis=0) > 0)[0]
hx0, hx1 = int(bx.min()), int(bx.max())
print("头部估计：y %d..%d（高 %d）  x %d..%d（宽 %d）" % (top, chin, chin-top, hx0, hx1, hx1-hx0))

# 内缩一点，避免带进背景；再外扩一点把下颌/耳侧包住
pad_x = int((hx1-hx0)*0.06); pad_y = int((chin-top)*0.05)
cx0, cy0 = max(0, hx0 - pad_x), max(0, top - pad_y)
cx1, cy1 = min(W, hx1 + pad_x), min(H, chin + int((chin-top)*0.10))
crop = im.crop((cx0, cy0, cx1, cy1))
cw, ch = crop.size
print("裁切框 %dx%d（原图坐标 x%d..%d y%d..%d）" % (cw, ch, cx0, cx1, cy0, cy1))

# alpha：圆角矩形 + 羽化（贴合头部轮廓的近似）
M = Image.new("L", (cw, ch), 0)
d = ImageDraw.Draw(M)
r = int(min(cw, ch) * 0.32)          # 圆角半径大一点，接近头部椭圆
d.rounded_rectangle([0, 0, cw-1, ch-1], radius=r, fill=255)
M = M.filter(ImageFilter.GaussianBlur(max(3, int(min(cw,ch)*0.045))))
cut = crop.convert("RGBA"); cut.putalpha(M)
# 放大到便于贴入的尺寸（头高约 224px → 目标贴入后头高≈全身高的 1/7.5，见下）
for scale in (1.0, 2.0):
    w2, h2 = int(cw*scale), int(ch*scale)
    p = os.path.join(OUT, "_头部抠图-%dx%d.png" % (w2, h2))
    cut.resize((w2, h2), Image.LANCZOS).save(p)
    print("  saved %s" % os.path.basename(p))

# 可视化预览（棋盘底）
ck = Image.new("RGB", (cw, ch), (255,255,255))
dd = ImageDraw.Draw(ck)
for yy in range(0, ch, 16):
    for xx in range(0, cw, 16):
        if ((xx//16) + (yy//16)) % 2 == 0:
            dd.rectangle([xx, yy, xx+15, yy+15], fill=(205,205,205))
ck = ck.convert("RGBA"); ck.alpha_composite(cut)
cv = Image.new("RGB", (cw*2+10, max(ch, 300)+26), (255,255,255))
cv.paste(im.crop((cx0,cy0,cx1,cy1)), (0, 26))
cv.paste(ck.convert("RGB"), (cw+10, 26))
dr = ImageDraw.Draw(cv)
dr.text((4, 7), "原裁切（含背景）", fill=(0,0,0))
dr.text((cw+14, 7), "抠图结果（alpha，棋盘=透明）", fill=(0,0,0))
o = os.path.join(OUT, "_预览-头部抠图.png"); cv.save(o)
cv.resize((1000, int(1000*cv.size[1]/cv.size[0])), Image.LANCZOS).save(
    r"C:\Users\ADMINI~1\AppData\Local\Temp\commandcode\D--xiaobai-claude-code-comfyUImd\df01e59d-0f96-4c37-9495-d9508dda8d9a\scratchpad\headcut.png", optimize=True)
print("saved 预览 -> %s" % o)
