# -*- coding: utf-8 -*-
"""1:1 局部放大对比图 —— 专门用来**判断皮肤/头发质感**

为什么需要它：
    make_sheet.py 把整张竖图缩到 780~900px 高，脸只占其中约 400px，
    毛孔、细发丝、胡茬这些「质感」在缩放里被抹平了 → 肉眼看不出差别，会误判。
    本脚本改成**按比例裁出脸部区域再拼**，让几版图的「脸占画面比例」一致，
    质感差异才可比。

用法：
    python zoom_sheet.py <输出.png> <裁切输出边长px> <x0,y0,x1,y1> "标题|副标题|路径" ...

例（脸部区域）：
    python zoom_sheet.py out.png 560 0.28,0.16,0.72,0.60 \
        "v23|SDXL|D:\\...\\a.png" "flux-v2|FLUX|D:\\...\\b.png"

区域用**图片宽高的比例**(0~1)给，所以不同分辨率的图也能对齐同一部位。
⚠️ 副标题里不能再出现竖线 `|`（会被当成字段分隔）。
"""
import os, sys

sys.path.insert(0, r"D:\xiaobai-claude code\ComfyUI\venv\Lib\site-packages")
from PIL import Image, ImageDraw, ImageFont

if len(sys.argv) < 5:
    print(__doc__); sys.exit(1)

OUT = sys.argv[1]
DST = int(sys.argv[2])
x0, y0, x1, y1 = [float(v) for v in sys.argv[3].split(",")]
ITEMS = sys.argv[4:]

PAD, TOP, BOT = 14, 84, 96
crops = []
for it in ITEMS:
    parts = it.split("|")
    if len(parts) != 3:
        print("跳过（应为 标题|副标题|路径）:", it); continue
    t1, t2, p = parts
    if not os.path.exists(p):
        print("跳过（文件不存在）:", p); continue
    im = Image.open(p).convert("RGB")
    W, H = im.size
    box = (int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H))
    c = im.crop(box).resize((DST, DST), Image.LANCZOS)
    crops.append((c, t1, t2, "%dx%d" % (W, H)))

if not crops:
    print("没有可用图片"); sys.exit(1)

Wc = DST * len(crops) + PAD * (len(crops) + 1)
Hc = TOP + DST + BOT
canvas = Image.new("RGB", (Wc, Hc), (246, 246, 248))
d = ImageDraw.Draw(canvas)
try:
    f1 = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 26)
    f2 = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 19)
except Exception:
    f1 = f2 = ImageFont.load_default()

x = PAD
for c, t1, t2, src in crops:
    canvas.paste(c, (x, TOP))
    d.text((x + 2, 14), t1, font=f1, fill=(20, 20, 24))
    d.text((x + 2, TOP + DST + 12), "%s  源 %s" % (t2, src), font=f2, fill=(118, 118, 130))
    x += DST + PAD

canvas.save(OUT, "PNG", optimize=True)
print("OK %s  %s  %.1f KB  （裁切区域 %s）" % (OUT, canvas.size, os.path.getsize(OUT) / 1024, sys.argv[3]))
