# -*- coding: utf-8 -*-
"""通用拼图：把若干张图横向拼成对比条，带标题与副标题

用法：
    python make_sheet.py <输出png> <高度> "标题1|副标题1|图片路径1" "标题2|副标题2|图片路径2" ...

例：
    python make_sheet.py out.png 760 "v23 基准|SDXL|D:\\a.png" "d070|Flux|D:\\b.png"
"""
import os, sys

sys.path.insert(0, r"D:\xiaobai-claude code\ComfyUI\venv\Lib\site-packages")
from PIL import Image, ImageDraw, ImageFont


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def main():
    out = sys.argv[1]
    th = int(sys.argv[2])
    items = []
    for spec in sys.argv[3:]:
        parts = spec.split("|")
        if len(parts) != 3:
            print("跳过（应为 标题|副标题|路径）:", spec); continue
        t1, t2, p = parts
        if not os.path.exists(p):
            print("★ 文件不存在:", p); continue
        items.append((t1.strip(), t2.strip(), p.strip()))
    if not items:
        print("没有可用图片"); sys.exit(1)

    PAD, TOP, BOT = 14, 84, 96
    f1 = font(r"C:\Windows\Fonts\msyhbd.ttc", 30)
    f2 = font(r"C:\Windows\Fonts\msyh.ttc", 22)
    ims = []
    for t1, t2, p in items:
        im = Image.open(p).convert("RGB")
        w = max(1, int(im.width * th / im.height))
        ims.append((im.resize((w, th), Image.LANCZOS), t1, t2))

    W = sum(i[0].width for i in ims) + PAD * (len(ims) + 1)
    H = TOP + th + BOT
    c = Image.new("RGB", (W, H), (246, 246, 248))
    d = ImageDraw.Draw(c)
    x = PAD
    for im, t1, t2 in ims:
        c.paste(im, (x, TOP))
        low = t1.lower()
        col = (15, 110, 86) if ("ok" in low or "基准" in t1) else (
            (163, 45, 45) if ("ng" in low or "v1" in low) else (30, 30, 34))
        d.text((x + 4, 16), t1, font=f1, fill=col)
        d.text((x + 4, TOP + th + 12), t2, font=f2, fill=(118, 118, 130))
        x += im.width + PAD
    os.makedirs(os.path.dirname(out), exist_ok=True)
    c.save(out, "PNG", optimize=True)
    print("OK %s  %dx%d  %.1f KB" % (out, c.size[0], c.size[1], os.path.getsize(out) / 1024))


main()
