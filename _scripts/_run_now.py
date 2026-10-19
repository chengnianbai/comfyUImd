# -*- coding: utf-8 -*-
"""在线上实例跑一次三视图，并量化肤色差 + 裁出正脸右眼内眼角供检查"""
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
OUT = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "run_now")
sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                        # noqa


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


wf = json.loads(raw("/api/userdata/workflows%2F" + urllib.parse.quote("夜市百相簿-主工作流.json", safe=''),
                    None, None, 120).decode('utf-8', 'replace'))
API, TITLES = build_api(wf)
TARGETS = [nid for nid, a in API.items()
           if a["class_type"] == "SaveImage" and "脸部" in str(a["inputs"].get("filename_prefix", ""))]
print("=== 目标输出 ===")
for t in sorted(TARGETS, key=lambda x: int(x)):
    print("   #%-5s %s  [%s]" % (t, API[t]["inputs"]["filename_prefix"], TITLES.get(t, "")))
subg = {k: v for k, v in API.items() if k in deps(API, TARGETS)}
print("   裁剪后 %d 节点；采样器 %s" % (len(subg),
      sorted([k for k, v in subg.items() if v["class_type"] == "KSampler"], key=int)))
res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 180).decode())
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:2000]); sys.exit(1)
pid = res["prompt_id"]; print("\n提交 prompt_id=%s" % pid)
done = None
for i in range(500):
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
if done is None:
    print("★ 超时"); sys.exit(1)

os.makedirs(OUT, exist_ok=True)
files = {}
for nid, o in done.items():
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        p = os.path.join(OUT, im["filename"])
        open(p, "wb").write(raw("/view?" + q, None, None, 300))
        files[nid] = p
        print("   saved %-50s %7.1f KB" % (im["filename"], os.path.getsize(p) / 1024))

def skinc(p):
    a = np.asarray(Image.open(p).convert("RGB")).astype(np.float32)
    R,G,B = a[:,:,0].astype(np.int16), a[:,:,1].astype(np.int16), a[:,:,2].astype(np.int16)
    mx = np.maximum(np.maximum(R,G),B); mn = np.minimum(np.minimum(R,G),B)
    sat = (mx-mn)/np.maximum(mx,1)
    m = (R>95)&(R>G)&(G>B)&((R-B)>12)&((R-B)<90)&(sat>0.12)&(sat<0.65)&(mx>90)
    return a, m

print("\n=== 肤色对比（皮肤掩膜内的均值，sRGB 0-255）===")
print("  %-26s %8s %8s %8s   %s" % ("图", "R", "G", "B", "R/G 比(黄度)  B/R 比"))
res_col = {}
for nid, p in sorted(files.items(), key=lambda x: int(x[0])):
    a, m = skinc(p)
    r, g, b = a[:,:,0][m].mean(), a[:,:,1][m].mean(), a[:,:,2][m].mean()
    res_col[nid] = (r, g, b)
    print("  #%-5s %-20s %8.1f %8.1f %8.1f   R/G=%.3f   B/R=%.3f"
          % (nid, os.path.basename(p)[:20], r, g, b, r/g, b/r))
ks = sorted(res_col)
if len(ks) >= 2:
    f = res_col[ks[0]]
    print("\n  以 #%s 为基准，其它支路的皮肤均值差：" % ks[0])
    for k in ks[1:]:
        v = res_col[k]
        print("    #%-5s  ΔR %+6.1f  ΔG %+6.1f  ΔB %+6.1f   （亮度差 %.1f%%）"
              % (k, v[0]-f[0], v[1]-f[1], v[2]-f[2],
                 100.0*((v[0]+v[1]+v[2])/3 - (f[0]+f[1]+f[2])/3)/((f[0]+f[1]+f[2])/3)))

# 三视图拼版 + 正脸眼部放大
items = [("#%s" % k, files[k]) for k in ks]
CW, CH = 430, 553
cv = Image.new("RGB", (len(items)*CW, CH+30), (255,255,255)); dr = ImageDraw.Draw(cv)
for i,(lab,p) in enumerate(items):
    cv.paste(Image.open(p).convert("RGB").resize((CW,CH), Image.LANCZOS), (i*CW,30))
    dr.text((i*CW+6,10), lab + " " + os.path.basename(p)[:22], fill=(0,0,0))
cv.save(os.path.join(OUT, "_三视图-本次.png"))

front = files[ks[0]]
im = Image.open(front).convert("RGB"); W, H = im.size
# 正脸眼部一带放大（画面中上部）
eye = im.crop((int(W*0.20), int(H*0.14), int(W*0.80), int(H*0.40))).resize((900, int(900*(H*0.26)/(W*0.60))), Image.LANCZOS)
eye.save(os.path.join(OUT, "_正脸眼部放大.png"))
print("\nsaved -> %s" % OUT)
print("   _三视图-本次.png / _正脸眼部放大.png")
