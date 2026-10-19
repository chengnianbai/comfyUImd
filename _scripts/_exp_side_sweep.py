# -*- coding: utf-8 -*-
"""侧脸质感对齐扫描：SDXL 段 denoise × Flux 提质感段 denoise（只提交，不写工作流）

要回答的问题
------------
用户问「侧脸质感为什么和正脸不一样」。已查证：**质感词两条支路是同一个节点(1008)，一字不差**，
所以差异不在提示词。真正的三个不对称是：
  ① 正脸成品走过 Flux 提质感(1047)，侧脸走过的是 SDXL 直出(1108)
  ② 起点细节量差 1.6 倍（正脸起点 lapVar 234.82 / 侧脸起点 150.27）
  ③ denoise 不同（正脸 0.30 / 侧脸 0.45）

本扫描针对 ①③：
     SDXL 段 denoise s ∈ {0.30, 0.60}  ×  Flux 提质感段 denoise f ∈ {1.0, 0.60}
     f=1.0 时 Flux 起点用纯噪声（与线上一致）；f<1.0 时起点改用参考图自身 latent
     （否则 denoise<1.0 + 纯噪声没有意义）。

已知对照点（不重复跑）
    s0.45 + f1.0  -> 变脸那版（左脸 lapVar 566.38）
    s0.45 + 无Flux -> 当前线上左脸成品（SDXL 直出）

用法： python _exp_side_sweep.py run
产物： _exp_0924/side_sweep/
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
OUTDIR = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "side_sweep")
WFNAME = "夜市百相簿-主工作流.json"
sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                        # noqa

COMBOS = [(0.30, 1.0), (0.30, 0.60), (0.60, 1.0), (0.60, 0.60)]
SEED_SDXL, SEED_FLUX = 20260912, 20260920


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


print("=== 1) 拉线上现行版并构 API ===")
wf = json.loads(raw("/api/userdata/workflows%2F" + urllib.parse.quote(WFNAME, safe=''), None, None, 120)
                .decode('utf-8', 'replace'))
API, TITLES = build_api(wf)
for k in ("1002", "1101", "1103", "1014", "1024", "1030", "1052", "1201"):
    assert k in API, "缺节点 %s" % k
print("  共享件：SDXL 底模 1002 / 侧脸参考 latent 1101 / 侧脸词 1103 / 负向 1014")
print("          Kontext 底模 1024 / 负向 1030 / 纯噪声 1052 / 提质感词+guidance 1201")

A = dict(API)
roots = []
for i, (s, f) in enumerate(COMBOS):
    b = 2000 + i * 10
    tag = "s%02d_f%02d" % (round(s * 100), round(f * 100))
    # SDXL 段
    A[str(b)] = {"class_type": "KSampler", "inputs": {
        "model": ["1002", 0], "positive": ["1103", 0], "negative": ["1014", 0],
        "latent_image": ["1101", 0], "seed": SEED_SDXL, "steps": 30, "cfg": 10.0,
        "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": s},
        "_meta": {"title": "%s · SDXL 侧脸 d%.2f" % (tag, s)}}
    A[str(b + 1)] = {"class_type": "VAEDecode", "inputs": {"samples": [str(b), 0], "vae": ["1002", 2]}}
    # 无 Flux 存档（看提质感前的样子）
    A[str(b + 2)] = {"class_type": "SaveImage", "inputs": {"images": [str(b + 1), 0],
                                                           "filename_prefix": "侧脸-%s-无Flux" % tag}}
    # Flux 提质感段
    A[str(b + 3)] = {"class_type": "FluxKontextImageScale", "inputs": {"image": [str(b + 1), 0]}}
    A[str(b + 4)] = {"class_type": "VAEEncode", "inputs": {"pixels": [str(b + 3), 0], "vae": ["1026", 0]}}
    A[str(b + 5)] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["1201", 0],
                                                                "latent": [str(b + 4), 0]}}
    A[str(b + 6)] = {"class_type": "KSampler", "inputs": {
        "model": ["1024", 0], "positive": [str(b + 5), 0], "negative": ["1030", 0],
        "latent_image": (["1052", 0] if f >= 1.0 else [str(b + 4), 0]),
        "seed": SEED_FLUX, "steps": 20, "cfg": 1.0,
        "sampler_name": "euler", "scheduler": "simple", "denoise": f},
        "_meta": {"title": "%s · Flux 提质感 d%.2f（起点=%s）" % (tag, f, "纯噪声" if f >= 1.0 else "参考latent")}}
    A[str(b + 7)] = {"class_type": "VAEDecode", "inputs": {"samples": [str(b + 6), 0], "vae": ["1026", 0]}}
    A[str(b + 8)] = {"class_type": "SaveImage", "inputs": {"images": [str(b + 7), 0],
                                                           "filename_prefix": "侧脸-%s" % tag}}
    A[str(b + 9)] = {"class_type": "ImageFlip", "inputs": {"image": [str(b + 7), 0],
                                                          "flip_method": "y-axis: horizontally"}}
    A[str(b + 10)] = {"class_type": "SaveImage", "inputs": {"images": [str(b + 9), 0],
                                                            "filename_prefix": "右脸-%s" % tag}}
    roots += [str(b + 2), str(b + 8), str(b + 10)]
    print("   组合 %d: SDXL d%.2f  +  Flux 提质感 d%.2f（起点 %s）"
          % (i + 1, s, f, "纯噪声" if f >= 1.0 else "参考latent"))

subg = {k: v for k, v in A.items() if k in deps(A, roots)}
print("\n=== 2) 提交 ===")
print("   裁剪后 %d 节点；采样器 %d 个：%s" % (len(subg),
      sum(1 for v in subg.values() if v["class_type"] == "KSampler"),
      sorted([k for k, v in subg.items() if v["class_type"] == "KSampler"], key=int)))
res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 180).decode())
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:2500]); sys.exit(1)
pid = res["prompt_id"]; print("   prompt_id=%s" % pid)
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

os.makedirs(OUTDIR, exist_ok=True)
files = []
for nid, o in done.items():
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        p = os.path.join(OUTDIR, im["filename"])
        open(p, "wb").write(raw("/view?" + q, None, None, 300))
        files.append(p)

def stats(p):
    im = Image.open(p).convert("RGB"); w, h = im.size
    a = np.asarray(im.resize((880, 1184), Image.LANCZOS)).astype(np.float32)
    R,G,B = a[:,:,0].astype(np.int16), a[:,:,1].astype(np.int16), a[:,:,2].astype(np.int16)
    mx = np.maximum(np.maximum(R,G),B); mn = np.minimum(np.minimum(R,G),B)
    sat = (mx-mn)/np.maximum(mx,1)
    m = (R>95)&(R>G)&(G>B)&((R-B)>12)&((R-B)<90)&(sat>0.12)&(sat<0.65)
    mm = m[1:-1,1:-1]&m[:-2,1:-1]&m[2:,1:-1]&m[1:-1,:-2]&m[1:-1,2:]
    g = 0.299*a[:,:,0]+0.587*a[:,:,1]+0.114*a[:,:,2]
    k = np.array([[0,1,0],[1,-4,1],[0,1,0]],float)
    hh = a[:int(1184*0.62), int(880*0.10):int(880*0.92)]
    gg = 0.299*hh[:,:,0]+0.587*hh[:,:,1]+0.114*hh[:,:,2]
    RR,GG,BB = hh[:,:,0].astype(np.int16),hh[:,:,1].astype(np.int16),hh[:,:,2].astype(np.int16)
    mxx = np.maximum(np.maximum(RR,GG),BB); mnn = np.minimum(np.minimum(RR,GG),BB)
    ss = (mxx-mnn)/np.maximum(mxx,1)
    sk = (RR>95)&(RR>GG)&(GG>BB)&((RR-BB)>12)&((RR-BB)<90)&(ss>0.12)&(ss<0.65)
    dk = gg < 70
    ys,xs = np.nonzero(sk); ys2,xs2 = np.nonzero(dk)
    off = (xs2.mean()-xs.mean())/max(xs.max()-xs.min(),1) if sk.sum()>200 and dk.sum()>200 else float('nan')
    return "%dx%d lapVar=%7.2f locStd=%.3f 偏移=%+6.3f" % (
        w, h, float(((sliding_window_view(g,(3,3))*k).sum(axis=(-1,-2)))[mm].var()),
        float(sliding_window_view(g,(3,3)).reshape(g.shape[0]-2,g.shape[1]-2,-1).std(axis=-1)[mm].mean()), off)

print("\n=== 3) 测量（归一到 880x1184）===")
print("  参照：v23认可正脸 lapVar 234.81 | Kontext正脸 198.79 | Kontext90° 150.27 | 变脸那版 566.38")
for p in sorted(files):
    print("  %-46s %s" % (os.path.basename(p)[:46], stats(p)))
print("\n产物 -> %s" % OUTDIR)
