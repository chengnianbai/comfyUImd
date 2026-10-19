# -*- coding: utf-8 -*-
"""把「正脸提质感」对齐到侧脸那档 —— 一次解决三件事（肤色、肉瘤、质感一致性）

已查明
    · 肤色差：正脸走 d1.0+纯噪声（Kontext 自己的色彩），侧脸走 d0.93+参考latent（保留 SDXL 色彩）
    · 内眼角肉瘤：纯 SDXL 正脸(00011) 没有 → 是 Kontext d1.0 那一步脑补出来的
    · 两者同一病根：d1.0 + 纯噪声 = 完全自由，可以改色、也可以凭空长出东西

本测试（单变量）
    1046 KSampler（正脸提质感段）：denoise 1.0 -> 0.93 ；latent_image 1052(纯噪声) -> 1029(参考 latent)
    其余一律不动。预测：肤色与侧脸对齐、肉瘤消失。

用法： COMFY_BASE=... python _exp_front_align.py
"""
import os, sys, io, ssl, json, time, uuid, urllib.request, urllib.parse
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
import numpy as np
from PIL import Image, ImageDraw

BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
if not BASE:
    print("★ 先设 COMFY_BASE"); sys.exit(4)
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
ROOT = r"D:\xiaobai-claude code\comfyUImd"
OUT = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "front_align")
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
print("改动前：1046.denoise=%s  latent_image=%s  positive<-%s"
      % (A["1046"]["inputs"]["denoise"], A["1046"]["inputs"]["latent_image"], A["1046"]["inputs"]["positive"]))
A["1046"]["inputs"]["denoise"] = 0.93
A["1046"]["inputs"]["latent_image"] = ["1029", 0]
print("改动后：1046.denoise=%s  latent_image=%s" % (A["1046"]["inputs"]["denoise"], A["1046"]["inputs"]["latent_image"]))
for nid, pfx in (("1021", "对齐测试-正脸"), ("1109", "对齐测试-左脸"), ("1111", "对齐测试-右脸")):
    A[nid]["inputs"]["filename_prefix"] = pfx
roots = ["1021", "1109", "1111"]
subg = {k: v for k, v in A.items() if k in deps(A, roots)}
print("裁剪后 %d 节点；采样器 %s" % (len(subg),
      sorted([k for k, v in subg.items() if v["class_type"] == "KSampler"], key=int)))
res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 180).decode())
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:2000]); sys.exit(1)
pid = res["prompt_id"]; print("\n提交 prompt_id=%s" % pid)
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
        done = h[pid].get("outputs", {}); print("   完成，约 %d 秒" % ((i + 1) * 3)); break
if done is None: print("★ 超时"); sys.exit(1)
os.makedirs(OUT, exist_ok=True)
got = {}
for nid, o in done.items():
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        p = os.path.join(OUT, im["filename"])
        open(p, "wb").write(raw("/view?" + q, None, None, 300))
        got[nid] = p
        print("   saved %-46s %7.1f KB" % (im["filename"], os.path.getsize(p) / 1024))

def skin(a):
    a = a.astype(np.float32)
    R,G,B = a[:,:,0].astype(np.int16), a[:,:,1].astype(np.int16), a[:,:,2].astype(np.int16)
    mx = np.maximum(np.maximum(R,G),B); mn = np.minimum(np.minimum(R,G),B)
    sat = (mx-mn)/np.maximum(mx,1)
    m = (R>95)&(R>G)&(G>B)&((R-B)>12)&((R-B)<90)&(sat>0.12)&(sat<0.65)&(mx>90)
    return a, m

print("\n=== 肤色（皮肤掩膜均值）===")
print("  %-22s %7s %7s %7s   R/G    B/R" % ("图", "R", "G", "B"))
vals = {}
for nid in ("1021", "1109", "1111"):
    if nid not in got: continue
    a, m = skin(np.asarray(Image.open(got[nid]).convert("RGB")))
    r, g, b = a[:,:,0][m].mean(), a[:,:,1][m].mean(), a[:,:,2][m].mean()
    vals[nid] = (r, g, b)
    print("  #%-5s %-16s %7.1f %7.1f %7.1f  %.3f  %.3f" % (nid, os.path.basename(got[nid])[:16], r, g, b, r/g, b/r))
if "1021" in vals and "1109" in vals:
    f, s = vals["1021"], vals["1109"]
    dR, dG, dB = f[0]-s[0], f[1]-s[1], f[2]-s[2]
    lum = 100.0 * ((f[0]+f[1]+f[2]) - (s[0]+s[1]+s[2])) / (s[0]+s[1]+s[2])
    print("\n  正脸 vs 左脸： dR {:+.1f}  dG {:+.1f}  dB {:+.1f}   亮度差 {:+.1f}%".format(dR, dG, dB, lum))
    print("  对照（改前）： dR -8.6  dG -4.4  dB -2.2   亮度差 -3.5%（正脸更亮更黄）")

# 眼部裁切对照（改前 00016 vs 改后）
imgs = []
try:
    q = urllib.parse.urlencode({"filename": "闻灯-脸部正面-成品_00016_.png", "subfolder": "", "type": "output"})
    p = os.path.join(OUT, "_改前_正脸00016.png"); open(p, "wb").write(raw("/view?" + q, None, None, 300))
    imgs.append(("改前 00016 (d1.0 纯噪声)", Image.open(p).convert("RGB")))
except Exception as e:
    print("  取改前失败", type(e).__name__)
if "1021" in got:
    imgs.append(("改后 (d0.93 参考latent)", Image.open(got["1021"]).convert("RGB")))
CW = 1000
tiles = []
for tag, im in imgs:
    W, H = im.size
    c = im.crop((int(W*0.18), int(H*0.12), int(W*0.82), int(H*0.40)))
    tiles.append((tag, c.resize((CW, int(CW*c.size[1]/c.size[0])), Image.LANCZOS)))
if tiles:
    hh = tiles[0][1].size[1]
    cv = Image.new("RGB", (CW, (hh+30)*len(tiles)), (255,255,255)); dr = ImageDraw.Draw(cv)
    for i,(tag,t) in enumerate(tiles):
        cv.paste(t, (0, i*(hh+30)+30)); dr.text((8, i*(hh+30)+8), tag, fill=(0,0,0))
    out = os.path.join(OUT, "_对照-正脸提质感改前改后-眼部.png"); cv.save(out); print("\nsaved", out)
print("\n产物 -> %s" % OUT)
