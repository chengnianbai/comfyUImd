# -*- coding: utf-8 -*-
"""定位肉瘤到底出在哪一级：输入基图 / SDXL 那一遍 / Kontext 那一遍

背景
    d0.93 那版用户反馈「肉瘤还是没有」，说明我对位置的判断或视觉结论有误。
    这里不再依赖视觉，改成把三级产物按同一比例裁同一区域并排，由用户判定。

三级
    输入基图   = 1004 LoadImage(wendeng_face_base.png)   —— 用户认可的稿
    SDXL 那一遍 = 1020 ImageScaleBy（正脸 SDXL 输出，未走 Kontext）
    Kontext 那遍 = 1047 VAEDecode（现在的正脸成品来源）

用法： COMFY_BASE=... python _exp_lump_locate.py
"""
import os, sys, io, ssl, json, time, uuid, urllib.request, urllib.parse
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
from PIL import Image, ImageDraw

BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
if not BASE:
    print("★ 先设 COMFY_BASE"); sys.exit(4)
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
ROOT = r"D:\xiaobai-claude code\comfyUImd"
OUT = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "lump_locate")
SC = r"C:\Users\ADMINI~1\AppData\Local\Temp\commandcode\D--xiaobai-claude-code-comfyUImd\df01e59d-0f96-4c37-9495-d9508dda8d9a\scratchpad"
sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                        # noqa


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


wf = json.loads(raw("/api/userdata/workflows%2F" + urllib.parse.quote("夜市百相簿-主工作流.json", safe=''),
                    None, None, 120).decode('utf-8', 'replace'))
API, _ = build_api(wf)
A = json.loads(json.dumps(API))
for k in ("1004", "1020", "1047"):
    assert k in A, "缺 %s" % k

# 统一到 880x1184 再存，便于同一比例裁切
SRC = [("L1-输入基图(wendeng_face_base)", "1004"), ("L2-SDXL那一遍(1020)", "1020"), ("L3-Kontext那一遍(1047)", "1047")]
roots = []
for i, (tag, sid) in enumerate(SRC):
    b = 5000 + i * 10
    A[str(b)] = {"class_type": "ImageScale", "inputs": {"image": [sid, 0], "upscale_method": "lanczos",
                                                        "width": 880, "height": 1184, "crop": "disabled"}}
    A[str(b + 1)] = {"class_type": "SaveImage", "inputs": {"images": [str(b), 0], "filename_prefix": "肉瘤定位-%s" % tag}}
    roots.append(str(b + 1))
subg = {k: v for k, v in A.items() if k in deps(A, roots)}
print("提交三级定位图；裁剪后 %d 节点" % len(subg))
res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 180).decode())
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:2000]); sys.exit(1)
pid = res["prompt_id"]; print("prompt_id=%s" % pid)
done = None
for i in range(400):
    time.sleep(3)
    h = json.loads(raw("/history/" + pid, None, None, 60).decode('utf-8', 'replace'))
    if pid in h:
        st = h[pid].get("status", {})
        if st.get("status_str") == "error":
            for m in st.get("messages", []):
                if m[0] == "execution_error":
                    print("★ ERROR %s: %s" % (m[1].get("node_type"), m[1].get("exception_message", "")[:400]))
            sys.exit(1)
        done = h[pid].get("outputs", {}); print("完成，约 %d 秒" % ((i + 1) * 3)); break
if done is None: print("★ 超时"); sys.exit(1)
os.makedirs(OUT, exist_ok=True)
files = []
for nid, o in done.items():
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        p = os.path.join(OUT, im["filename"]); open(p, "wb").write(raw("/view?" + q, None, None, 300))
        files.append(p); print("  saved %-52s %7.1f KB" % (im["filename"], os.path.getsize(p) / 1024))

def sheet(files, x0, y0, x1, y1, name):
    tiles = []
    for p in sorted(files):
        im = Image.open(p).convert("RGB"); w, h = im.size
        c = im.crop((int(w*x0), int(h*y0), int(w*x1), int(h*y1)))
        W = 620
        tiles.append((os.path.basename(p)[:30], c.resize((W, int(W*c.size[1]/c.size[0])), Image.LANCZOS)))
    hh = tiles[0][1].size[1]
    cv = Image.new("RGB", (W, (hh+24)*len(tiles)), (255,255,255)); dr = ImageDraw.Draw(cv)
    for i,(t,c) in enumerate(tiles):
        cv.paste(c, (0, i*(hh+24)+24)); dr.text((6, i*(hh+24)+6), t, fill=(0,0,0))
    o = os.path.join(OUT, name); cv.save(o); print("saved", o, cv.size)
    return o

sheet(files, 0.18, 0.24, 0.84, 0.52, "_对照-双眼整体.png")
sheet(files, 0.24, 0.27, 0.50, 0.45, "_对照-画面左眼.png")
sheet(files, 0.50, 0.27, 0.76, 0.45, "_对照-画面右眼.png")
print("\n产物 -> %s" % OUT)
