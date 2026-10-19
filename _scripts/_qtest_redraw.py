# -*- coding: utf-8 -*-
"""零成本验证：v23(SDXL) 那步「第二段 denoise 0.25 重绘」到底在帮忙还是在抹细节。

做法：拿本地留存的 v23 草稿（重绘前，896x1152），
      ① 原样
      ② 用 LANCZOS 放大 2x（= 撤掉重绘的产物代理）
      ③ 与 v23 成品（4x 放大 + 重绘，1792x2304）在同一显示尺寸下比。

判据：②是"笨办法"（朴素重采样），③是"聪明办法"（4x 模型 + 重绘）。
      如果 ② 的纹理 ≤ ③，那重绘才有价值；如果 ② 反而 ≥ ③，重绘就是在抹细节。
"""
import os
import sys

sys.path.insert(0, r"D:\xiaobai-claude code\ComfyUI\venv\Lib\site-packages")
from PIL import Image, ImageDraw, ImageFont

R = r"D:\xiaobai-claude code\comfyUImd\系列-夜市百相簿/02-角色/闻灯/设定图"
OUT_DIR = R

# (标题, 副标题, 路径, 是否先放大2倍)
CASES = {
    "v23": (
        os.path.join(R, "v23-脸部三视角", "闻灯v23-脸部正面-草稿_00001_.png"),
        os.path.join(R, "v23-脸部三视角", "闻灯v23-脸部正面-成品_00001_.png"),
    ),
    "v13": (
        os.path.join(R, "脸部素材集", "闻灯-正脸-已确认_草稿.png"),
        os.path.join(R, "脸部素材集", "闻灯-正脸-已确认_成品.png"),
    ),
}

# 取景：脸部（左,上,右,下 的分数）
FACE = (0.30, 0.18, 0.70, 0.58)
HAIR = (0.22, 0.02, 0.78, 0.36)

TH = 620          # 每格显示高度
PAD = 12
TOP = 78
BOT = 96


def font(sz, bold=False):
    for name in (r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
                 r"C:\Windows\Fonts\simhei.ttf"):
        try:
            return ImageFont.truetype(name, sz)
        except Exception:
            continue
    return ImageFont.load_default()


def crop_scaled(path, box, up2=False):
    im = Image.open(path).convert("RGB")
    if up2:
        im = im.resize((im.width * 2, im.height * 2), Image.LANCZOS)
    w, h = im.size
    l, t, r, b = box
    c = im.crop((int(w * l), int(h * t), int(w * r), int(h * b)))
    # 统一显示尺寸（等比）
    nh = TH
    nw = max(1, int(c.width * TH / c.height))
    return c.resize((nw, nh), Image.LANCZOS)


def build(tag, box, key):
    draft, final = CASES[key]
    items = []
    items.append((crop_scaled(draft, box, False), "草稿（重绘前）", "%dx%d · SDXL 第一段" % Image.open(draft).size))
    items.append((crop_scaled(draft, box, True), "草稿 → LANCZOS 2x", "「撤掉重绘」的产物代理（朴素重采样）"))
    items.append((crop_scaled(final, box, False), "成品（4x放大+重绘 d0.25）", "%dx%d · 现有资产" % Image.open(final).size))

    W = sum(i[0].width for i in items) + PAD * (len(items) + 1)
    H = TOP + TH + BOT
    cv = Image.new("RGB", (W, H), (246, 246, 248))
    d = ImageDraw.Draw(cv)
    f1, f2 = font(26, True), font(19)
    x = PAD
    for im, t1, t2 in items:
        cv.paste(im, (x, TOP))
        col = (18, 18, 22)
        if "重绘前" in t1:
            col = (150, 150, 158)
        elif "撤掉" in t1:
            col = (12, 118, 92)
        elif "成品" in t1:
            col = (170, 52, 52)
        d.text((x + 2, 40), t1, font=f1, fill=col)
        d.text((x + 2, TOP + TH + 10), t2, font=f2, fill=(122, 122, 134))
        x += im.width + PAD
    out = os.path.join(OUT_DIR, "_1比1_%s_重绘到底干嘛_%s.png" % (key, tag))
    cv.save(out, "PNG", optimize=True)
    print("OK  %s  %s  %.1f KB" % (out, cv.size, os.path.getsize(out) / 1024))
    return out


if __name__ == "__main__":
    build("脸部", FACE, "v23")
    build("头发", HAIR, "v23")
    build("脸部", FACE, "v13")
