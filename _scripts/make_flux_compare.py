# -*- coding: utf-8 -*-
"""把「v23 基图 / Flux 纯文生图 / Flux 基图基准」三张横排成一张对比图。

用法：python make_flux_compare.py
（拼图要 PIL —— 托管 python 没装的话用系统 python：
  C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python313\\python.exe）
"""
import os

from PIL import Image, ImageDraw, ImageFont

R = r'D:\xiaobai-claude code\comfyUImd'
D = os.path.join(R, r'系列-夜市百相簿/02-角色/闻灯/设定图\Flux文生图-2026-09-20')

ITEMS = [
    (os.path.join(R, r'_scripts\_wf\flux_face_base_v23_1024x1280.png'), 'v23 基图（SDXL）'),
    (os.path.join(D, '闻灯Flux文生图-草稿_00001_.png'), 'Flux 纯文生图 d1.0'),
    (os.path.join(D, '闻灯Flux基准-草稿_00001_.png'), 'Flux 基图基准 d0.30'),
]

H = 900
PAD = 12
TOP = 56

imgs = []
for p, label in ITEMS:
    im = Image.open(p).convert('RGB')
    im = im.resize((int(im.width * H / im.height), H), Image.LANCZOS)
    imgs.append(im)

W = sum(i.width for i in imgs) + PAD * (len(imgs) + 1)
canvas = Image.new('RGB', (W, H + TOP + PAD * 2), (243, 243, 243))
d = ImageDraw.Draw(canvas)

font = None
for fp in ('C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/msyhbd.ttc', 'C:/Windows/Fonts/simhei.ttf'):
    if os.path.exists(fp):
        try:
            font = ImageFont.truetype(fp, 30)
            break
        except Exception:
            pass
if font is None:
    font = ImageFont.load_default()

x = PAD
for im, (p, label) in zip(imgs, ITEMS):
    canvas.paste(im, (x, PAD + TOP))
    d.text((x + 6, PAD + 12), label, fill=(25, 25, 25), font=font)
    x += im.width + PAD

out = os.path.join(D, '_对比_基图-vs-纯文生图-vs-基图基准.png')
canvas.save(out)
print('saved', out, canvas.size)
