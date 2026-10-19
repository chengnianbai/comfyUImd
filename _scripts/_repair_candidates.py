# -*- coding: utf-8 -*-
"""位置确认 + 3 个候选修补（不依赖眼位检测；全部围绕用户给的坐标 463,420）

用户坐标 (987, 502) 是在 3× 放大网格图（2016x1038，裁剪起点 x=134,y=253）上量的，
换算回原图 = (134 + 987/3, 253 + 502/3) ≈ (463, 420)。

三个候选（都不依赖镜像轴，避免几何出错）
    C1 就近克隆：从「朝鼻子方向 60px」的干净鼻梁皮肤取块
    C2 就近克隆：从「正下方 60px」的颊部皮肤取块
    C3 平滑填充：把该小块用周围皮肤的渐变填平（不搬任何特征，最保守）

输出：位置确认图 + 每个候选的 4 倍局部对照，供挑选。不动线上任何东西。
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
SC = r"C:\Users\ADMINI~1\AppData\Local\Temp\commandcode\D--xiaobai-claude-code-comfyUImd\df01e59d-0f96-4c37-9495-d9508dda8d9a\scratchpad"
im = Image.open(os.path.join(OUT, "base_original.png")).convert("RGB")
W, H = im.size
TX, TY = 463, 420
PW, PH = 40, 34
print("基图 %dx%d ；目标点 (%d,%d) ；补丁 %dx%d" % (W, H, TX, TY, PW, PH))


def feather(w, h, soft=0.5):
    yy, xx = np.mgrid[0:h, 0:w]
    cy, cx = (h-1)/2.0, (w-1)/2.0
    r = np.sqrt(((xx-cx)/(w/2.0))**2 + ((yy-cy)/(h/2.0))**2)
    return Image.fromarray((np.clip((1.0-r)/soft, 0, 1)*255).astype(np.uint8))


def paste_from(sx, sy):
    bt = (TX-PW//2, TY-PH//2)
    bs = (sx-PW//2, sy-PH//2)
    if min(bs[0], bs[1]) < 0 or bs[0]+PW > W or bs[1]+PH > H: return None
    out = im.copy()
    out.paste(im.crop((bs[0], bs[1], bs[0]+PW, bs[1]+PH)), bt, feather(PW, PH))
    return out


def smooth_fill():
    out = im.copy()
    box = (TX-PW//2, TY-PH//2, TX-PW//2+PW, TY-PH//2+PH)
    reg = im.crop(box)
    # 取该块的强模糊（去掉鼓起及其高光/阴影），再略显一点原块结构
    blur = reg.filter(ImageFilter.GaussianBlur(9))
    med = reg.filter(ImageFilter.MedianFilter(9))
    mix = Image.blend(blur, med, 0.5)
    out.paste(mix, (box[0], box[1]), feather(PW, PH, 0.55))
    return out


CANDS = [("C1 鼻梁方向克隆", lambda: paste_from(TX+60, TY)),
         ("C2 下方颊部克隆", lambda: paste_from(TX, TY+60)),
         ("C3 平滑填充(最保守)", smooth_fill)]
made = []
for tag, fn in CANDS:
    r = fn()
    if r is None:
        print("  %s 越界，跳过" % tag); continue
    p = os.path.join(OUT, "_候选_%s.png" % tag.split()[0])
    r.save(p); made.append((tag, r, p))
    print("  生成 %s -> %s" % (tag, os.path.basename(p)))

# 位置确认图
ann = im.copy(); dr = ImageDraw.Draw(ann)
dr.ellipse([TX-24, TY-24, TX+24, TY+24], outline=(255, 0, 0), width=3)
dr.line([(TX-70, TY), (TX+70, TY)], fill=(255, 200, 0), width=1)
dr.line([(TX, TY-70), (TX, TY+70)], fill=(255, 200, 0), width=1)
big = ann.crop((max(0, TX-190), max(0, TY-150), min(W, TX+190), min(H, TY+170)))
big = big.resize((big.size[0]*3, big.size[1]*3), Image.LANCZOS)
o = os.path.join(OUT, "_位置确认-红圈处是否肉瘤.png"); big.save(o); print("saved", o, big.size)
big.resize((820, int(820*big.size[1]/big.size[0])), Image.LANCZOS).save(os.path.join(SC, "pos.png"), optimize=True)

# 候选对照（同一局部 4 倍）
tiles = [("原图", im)] + [(t, r) for t, r, _ in made]
crops = []
for t, img in tiles:
    c = img.crop((max(0, TX-110), max(0, TY-95), min(W, TX+110), min(H, TY+105)))
    crops.append((t, c.resize((c.size[0]*4, c.size[1]*4), Image.LANCZOS)))
cw = crops[0][1].size[0]; ch = crops[0][1].size[1]
cols = min(4, len(crops)); rows = (len(crops)+cols-1)//cols
cv = Image.new("RGB", (cols*(cw+8), rows*(ch+26)), (255,255,255)); d2 = ImageDraw.Draw(cv)
for i, (t, c) in enumerate(crops):
    r, cc = divmod(i, cols)
    cv.paste(c, (cc*(cw+8), r*(ch+26)+26)); d2.text((cc*(cw+8)+4, r*(ch+26)+6), t, fill=(0,0,0))
o2 = os.path.join(OUT, "_对照-原图与3个候选.png"); cv.save(o2); print("saved", o2, cv.size)
cv.resize((1200, int(1200*cv.size[1]/cv.size[0])), Image.LANCZOS).save(os.path.join(SC, "cands.png"), optimize=True)
print("\n产物 -> %s" % OUT)
