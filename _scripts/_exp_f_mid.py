# -*- coding: utf-8 -*-
"""提质感段 denoise 中间档扫描：f ∈ {0.75, 0.85, 0.93}（线上现用参考图 1108）

已测两端（同一张参考图 1108，输入 lapVar 172.82）
    f=1.00 -> 输出 566.38（过火/像变脸，起点=纯噪声）
    f=0.60 -> 输出  87.51（磨皮，起点=参考 latent）
中间档没试过，而 f<1.0 时起点是参考图自身 → 结构被锚住，理论上能既补细节又不改脸。

目标区间：你认可那版 271.21 ／ v23 认可正脸 234.81

用法： python _exp_f_mid.py
"""
import os, sys, io, ssl, json, time, uuid, urllib.request, urllib.parse
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
import numpy as np
from PIL import Image
from numpy.lib.stride_tricks import sliding_window_view

BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
if not BASE:
    print("★ 先设 COMFY_BASE"); sys.exit(4)
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
ROOT = r"D:\xiaobai-claude code\comfyUImd"
OUTDIR = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "f_mid")
sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                        # noqa

FS = [0.75, 0.85, 0.93]


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


wf = json.loads(raw("/api/userdata/workflows%2F" + urllib.parse.quote("夜市百相簿-主工作流.json", safe=''),
                    None, None, 120).decode('utf-8', 'replace'))
API, _ = build_api(wf)
A = dict(API)
# 共享：1200/1201 提质感词+guidance、1024 底模、1030 负向、1210/1211 参考链（输入=1108）
A["1210"]["inputs"]["image"] = ["1108", 0]
roots = []
for i, f in enumerate(FS):
    b = 3000 + i * 10
    A[str(b)] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["1201", 0], "latent": ["1211", 0]}}
    A[str(b + 1)] = {"class_type": "KSampler", "inputs": {
        "model": ["1024", 0], "positive": [str(b), 0], "negative": ["1030", 0],
        "latent_image": ["1211", 0],           # ★ f<1.0 -> 起点用参考 latent（结构被锚住）
        "seed": 20260920, "steps": 20, "cfg": 1.0,
        "sampler_name": "euler", "scheduler": "simple", "denoise": f}}
    A[str(b + 2)] = {"class_type": "VAEDecode", "inputs": {"samples": [str(b + 1), 0], "vae": ["1026", 0]}}
    A[str(b + 3)] = {"class_type": "SaveImage", "inputs": {"images": [str(b + 2), 0],
                                                          "filename_prefix": "提质感f%02d" % round(f * 100)}}
    A[str(b + 4)] = {"class_type": "ImageFlip", "inputs": {"image": [str(b + 2), 0],
                                                          "flip_method": "y-axis: horizontally"}}
    A[str(b + 5)] = {"class_type": "SaveImage", "inputs": {"images": [str(b + 4), 0],
                                                          "filename_prefix": "右脸f%02d" % round(f * 100)}}
    roots += [str(b + 3), str(b + 5)]
    print("   分支: 参考=1108（线上同款）  起点=参考latent  denoise=%.2f" % f)
subg = {k: v for k, v in A.items() if k in deps(A, roots)}
print("   裁剪后 %d 节点" % len(subg))
res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 180).decode())
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:2000]); sys.exit(1)
pid = res["prompt_id"]; print("   prompt_id=%s" % pid)
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
os.makedirs(OUTDIR, exist_ok=True)
for nid, o in done.items():
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        open(os.path.join(OUTDIR, im["filename"]), "wb").write(raw("/view?" + q, None, None, 300))

def stats(p, tag):
    a = np.asarray(Image.open(p).convert("RGB").resize((880, 1184), Image.LANCZOS)).astype(np.float32)
    R,G,B = a[:,:,0].astype(np.int16), a[:,:,1].astype(np.int16), a[:,:,2].astype(np.int16)
    mx = np.maximum(np.maximum(R,G),B); mn = np.minimum(np.minimum(R,G),B)
    sat = (mx-mn)/np.maximum(mx,1)
    m = (R>95)&(R>G)&(G>B)&((R-B)>12)&((R-B)<90)&(sat>0.12)&(sat<0.65)
    mm = m[1:-1,1:-1]&m[:-2,1:-1]&m[2:,1:-1]&m[1:-1,:-2]&m[1:-1,2:]
    g = 0.299*a[:,:,0]+0.587*a[:,:,1]+0.114*a[:,:,2]
    k = np.array([[0,1,0],[1,-4,1],[0,1,0]],float)
    hh = a[:int(1184*0.62), int(880*0.10):int(880*0.92)]
    gg = 0.299*hh[:,:,0]+0.587*hh[:,:,1]+0.114*hh[:,:,2]
    RR,GG,BB2 = hh[:,:,0].astype(np.int16),hh[:,:,1].astype(np.int16),hh[:,:,2].astype(np.int16)
    mxx = np.maximum(np.maximum(RR,GG),BB2); mnn = np.minimum(np.minimum(RR,GG),BB2)
    ss = (mxx-mnn)/np.maximum(mxx,1)
    sk = (RR>95)&(RR>GG)&(GG>BB2)&((RR-BB2)>12)&((RR-BB2)<90)&(ss>0.12)&(ss<0.65); dk = gg<70
    ys,xs = np.nonzero(sk); ys2,xs2 = np.nonzero(dk)
    off = (xs2.mean()-xs.mean())/max(xs.max()-xs.min(),1) if sk.sum()>200 and dk.sum()>200 else float('nan')
    print("  %-26s lapVar=%7.2f locStd=%.3f 偏移=%+6.3f" % (tag,
          float(((sliding_window_view(g,(3,3))*k).sum(axis=(-1,-2)))[mm].var()),
          float(sliding_window_view(g,(3,3)).reshape(g.shape[0]-2,g.shape[1]-2,-1).std(axis=-1)[mm].mean()), off))

print("\n=== 测量（归一到 880x1184）===")
print("  目标：你认可的 271.21 ｜ v23 认可正脸 234.81 ｜ 过火 566.38 ｜ 磨皮 87.51")
print("  参照：参考图 1108 本身 = 172.82 ；提质感前(before) 侧脸 = 119.79")
for f in sorted(os.listdir(OUTDIR)):
    stats(os.path.join(OUTDIR, f), f[:26])
print("\n产物 -> %s" % OUTDIR)
