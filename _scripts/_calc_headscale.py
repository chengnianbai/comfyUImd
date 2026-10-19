# -*- coding: utf-8 -*-
"""确定性地标定贴脸尺寸：在**脸部原图**里量出头高 → 反推贴图尺寸使成品达到 7.5 头身

推导
    贴图把「脸部原图（880×1184）」缩放到 (pw, ph) 贴进 832×1216 的草稿，成品再 ×2。
    ⇒ 头高(成品) = 2 × 头高(原图) × ph / 1184
    ⇒ 头身比    = 身形高(成品) / 头高(成品)
    解出： ph = 身形高 × 1184 / (目标头身比 × 2 × 头高(原图))
"""
import os, sys, io, ssl, json, urllib.request, urllib.parse
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
import numpy as np
from PIL import Image
BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
ROOT = r"D:\xiaobai-claude code\comfyUImd"
BR = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "base_repair")
FACE = "闻灯-脸部正面-成品_00018_.png"
TARGET = 7.5

def get(fn, out, typ="output"):
    q = urllib.parse.urlencode({"filename": fn, "subfolder": "", "type": typ})
    open(out, "wb").write(urllib.request.urlopen(BASE + "/view?" + q, timeout=300, context=ctx).read())

p = os.path.join(BR, "_face_asset.png")
get(FACE, p)
im = Image.open(p).convert("RGB")
W, H = im.size
a = np.asarray(im).astype(np.int16)
bg = a[3, 3].astype(np.int16)                      # 以左上角像素为背景基准（背景是浅灰，不是纯白）
body = np.abs(a - bg).sum(axis=2) > 70
rows = body.sum(axis=1)
nz = np.nonzero(rows > W*0.01)[0]
top, bot = int(nz[0]), int(nz[-1])
print("脸部原图 %dx%d ；非白区域 y=%d..%d" % (W, H, top, bot))
# 在头部区域找"最窄行"= 脖子（下巴下沿）；头宽 = 该行以上的最大宽度
hi = top + int((bot-top)*0.55)
seg = rows[top:hi]
neck = top + int(np.argmin(seg))
head_h_asset = neck - top
head_w_asset = int(rows[top:neck].max())
print("  头高（顶→脖）≈ %d px ；头宽 ≈ %d px ；比例 %.2f（成年人约 1.3~1.4）"
      % (head_h_asset, head_w_asset, head_h_asset/max(head_w_asset,1)))

FIG = 2432.0          # 成品身形高（实测：图像 1664x2432，非白区域几乎占满）
ph = FIG * H / (TARGET * 2.0 * head_h_asset)
ph = int(round(min(max(ph, 120), 400)))
pw = int(round(ph * 880 / 1184))
print("\n目标 %.1f 头身 → ph = %.0f×1184/(%.1f×2×%d) = %d px ；pw = %d px"
      % (TARGET, FIG, TARGET, head_h_asset, ph, pw))
print("（当前是 200x257）")
