"""把 512 草稿 与 768 高清修复 的同一脸部区域裁出来放一起，做放大对比图。

因为两张图构图完全一致（同种子同提示词，只有分辨率不同），
所以按相同比例裁同一块区域，再统一放大到同样大小，
差异就全部来自分辨率 —— 这是最直观的证据。
"""

import os
from PIL import Image, ImageDraw, ImageFont

OUT = r"D:\xiaobai-claude code\ComfyUI\output"
A = os.path.join(OUT, "SkinDraft512_00001_.png")   # 512x640
B = os.path.join(OUT, "SkinFinal768_00001_.png")   # 768x960
DST = os.path.join(OUT, "对比_皮肤质感_512草稿_vs_768修复.png")

# 归一化裁剪框（以左眼+面颊为中心）
CX, CY, FW, FH = 0.335, 0.415, 0.34, 0.27

PANEL = 320
GAP = 24
PAD = 28
HEADER = 60
FOOTER = 46

FONT = None
for cand in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhl.ttc",
             r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\arial.ttf"):
    if os.path.exists(cand):
        FONT = cand
        break


def font(sz):
    return ImageFont.truetype(FONT, sz) if FONT else ImageFont.load_default()


def crop_frac(path):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    box = (int((CX - FW / 2) * w), int((CY - FH / 2) * h),
           int((CX + FW / 2) * w), int((CY + FH / 2) * h))
    return im.crop(box).resize((PANEL, PANEL), Image.LANCZOS), (w, h)


ca, sa = crop_frac(A)
cb, sb = crop_frac(B)

W = PAD * 2 + PANEL * 2 + GAP
H = HEADER + PANEL + FOOTER
canvas = Image.new("RGB", (W, H), (245, 244, 240))
d = ImageDraw.Draw(canvas)

f_title = font(20)
f_sub = font(15)
f_small = font(13)

d.text((PAD, 18), "同一张图 · 同一块脸 · 放大到同样大小", font=f_title, fill=(40, 40, 40))

xa, xb = PAD, PAD + PANEL + GAP
y = HEADER
canvas.paste(ca, (xa, y))
canvas.paste(cb, (xb, y))
d.rectangle([xa, y, xa + PANEL - 1, y + PANEL - 1], outline=(150, 150, 150), width=1)
d.rectangle([xb, y, xb + PANEL - 1, y + PANEL - 1], outline=(150, 150, 150), width=1)

d.text((xa + 6, y + 6), "512 × 640  草稿", font=f_sub, fill=(120, 40, 40))
d.text((xb + 6, y + 6), "768 × 960  高清修复后", font=f_sub, fill=(20, 90, 60))

fy = y + PANEL + 10
d.text((xa, fy), "源图 %d×%d · 细节糊、边缘发虚" % sa, font=f_small, fill=(90, 90, 90))
d.text((xb, fy), "源图 %d×%d · 雀斑颗颗分明" % sb, font=f_small, fill=(90, 90, 90))

canvas.save(DST)
print("已生成:", DST, canvas.size)
