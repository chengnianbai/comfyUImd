# -*- coding: utf-8 -*-
"""把基图眼部切成带编号的小格（每格标出所属像素范围），用户只需报格子编号"""
import os, sys
from PIL import Image, ImageDraw
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
ROOT = r"D:\xiaobai-claude code\comfyUImd"
OUT = os.path.join(ROOT, "系列-夜市相簿/02-角色/闻灯/设定图/_exp_0924/base_repair") if False else \
      os.path.join(ROOT, "系列-夜市相簿") if False else \
      os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "base_repair")
SC = r"C:\Users\ADMINI~1\AppData\Local\Temp\commandcode\D--xiaobai-claude-code-comfyUImd\df01e59d-0f96-4c37-9495-d9508dda8d9a\scratchpad"
im = Image.open(os.path.join(OUT, "base_original.png")).convert("RGB")
W, H = im.size
print("基图 %dx%d" % (W, H))

XS = [(100, 280), (250, 430), (400, 580), (550, 730), (700, 896)]
YS = [(280, 470), (430, 620)]
COL = "ABCDE"
TILE_W, TILE_H = 300, 340
cols = len(XS); rows = len(YS)
pad_top, pad_left = 26, 26
cv = Image.new("RGB", (pad_left + cols*TILE_W, pad_top + rows*(TILE_H+26)), (255,255,255))
dr = ImageDraw.Draw(cv)
for ci, (x0, x1) in enumerate(XS):
    dr.text((pad_left + ci*TILE_W + 4, 6), "col %s  x=%d..%d" % (COL[ci], x0, x1), fill=(0,0,0))
for ri, (y0, y1) in enumerate(YS):
    base_y = pad_top + ri*(TILE_H+26)
    dr.text((2, base_y + 4), "r%d\ny=%d..%d" % (ri+1, y0, y1), fill=(0,0,0))
    for ci, (x0, x1) in enumerate(XS):
        c = im.crop((x0, y0, x1, y1))
        c = c.resize((TILE_W, TILE_H), Image.LANCZOS)
        px = pad_left + ci*TILE_W
        cv.paste(c, (px, base_y))
        tag = "%s%d" % (COL[ci], ri+1)
        dr.rectangle([px, base_y, px+TILE_W-1, base_y+TILE_H-1], outline=(0,0,0))
        dr.rectangle([px+3, base_y+3, px+76, base_y+26], fill=(255,255,255))
        dr.text((px+7, base_y+7), tag, fill=(200,0,0))
o = os.path.join(OUT, "_指认-眼部格子编号.png"); cv.save(o); print("saved", o, cv.size)
cv.resize((1200, int(1200*cv.size[1]/cv.size[0])), Image.LANCZOS).save(os.path.join(SC, "tiles.png"), optimize=True)
print("\n格子：")
for ri, (y0, y1) in enumerate(YS):
    print("  r%d (y %d..%d): %s" % (ri+1, y0, y1, "  ".join("%s%d (x %d..%d)" % (COL[ci], ri+1, XS[ci][0], XS[ci][1]) for ci in range(cols))))
