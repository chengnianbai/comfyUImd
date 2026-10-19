import os, sys, glob
from PIL import Image, ImageDraw
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
O = r"D:\xiaobai-claude code\comfyUImd\系列-夜市百相簿\02-角色\角色生成-出图"
SC = r"C:\Users\ADMINI~1\AppData\Local\Temp\commandcode\D--xiaobai-claude-code-comfyUImd\df01e59d-0f96-4c37-9495-d9508dda8d9a\scratchpad"


def g(n):
    f = glob.glob(os.path.join(O, "*_%05d_.png" % n))
    return f[0] if f else None


cells = []
for n, tag in ((1, "改前（提示词被截断，五官词全丢）"), (2, "改后（A+B+C 分段 + 负向 3 段 + cfg7）")):
    p = g(n)
    if not p:
        print("缺 0000%d" % n); continue
    im = Image.open(p).convert("RGB"); W, H = im.size
    print("  %s %dx%d" % (tag, W, H))
    c = im.crop((int(W*0.30), int(H*0.005), int(W*0.70), int(H*0.115)))     # 头部区域
    cells.append((tag, c.resize((int(c.size[0]*760/c.size[1]), 760), Image.LANCZOS)))
Wt = sum(x[1].size[0] for x in cells) + 14*(len(cells)+1)
cv = Image.new("RGB", (Wt, 790), (248, 248, 248)); dr = ImageDraw.Draw(cv)
x = 14
for t, im2 in cells:
    cv.paste(im2, (x, 26)); dr.text((x+2, 8), t, fill=(0, 0, 0)); x += im2.size[0]+14
o = os.path.join(O, "_对照-改前vs改后-头部.png"); cv.save(o); print("saved", o, cv.size)
w = min(1150, cv.size[0]); cv.resize((w, int(w*cv.size[1]/cv.size[0])), Image.LANCZOS).save(os.path.join(SC, "rg_cmp.png"), optimize=True)

cells = []
for n, tag in ((1, "改前"), (2, "改后")):
    p = g(n)
    if not p: continue
    im = Image.open(p).convert("RGB"); W, H = im.size
    cells.append((tag + "  %dx%d" % (W, H), im.resize((int(W*900/H), 900), Image.LANCZOS)))
Wt = sum(x[1].size[0] for x in cells) + 14*(len(cells)+1)
cv2 = Image.new("RGB", (Wt, 930), (248, 248, 248)); dr = ImageDraw.Draw(cv2)
x = 14
for t, im2 in cells:
    cv2.paste(im2, (x, 26)); dr.text((x+2, 8), t, fill=(0, 0, 0)); x += im2.size[0]+14
o2 = os.path.join(O, "_对照-改前vs改后-全身.png"); cv2.save(o2); print("saved", o2)
w = min(1100, cv2.size[0]); cv2.resize((w, int(w*cv2.size[1]/cv2.size[0])), Image.LANCZOS).save(os.path.join(SC, "rg_full.png"), optimize=True)
