# -*- coding: utf-8 -*-
"""验证解法：把左脸提质感段的输入从「放大后 1108」改成「放大前 1105」

依据（_exp_0924/ref_ab/ 已证）
    这套提质感链路会把输入的微细节放大约 2.3~3.3 倍：
      输入 119.79 -> 输出 271.21（用户认可）
      输入 172.82 -> 输出 566.38（过火/像变脸）
    线上左脸：1105(SDXL直出 896x1152, 约 105~114) --4x放大->缩回0.5--> 1108(172.82)
    现在提质感接的是 1108（被 4x-UltraSharp 锐化过）。改成接 1105，输入就落回 100~115 量级。

预测：改用 1105 后，输出应落在 240~300（≈ 用户认可那版）。

本脚本：直接改线上 API 里 1210.image 的来源，并放开左脸提质感段，一次提交两个对照
    V1 输入=1105（放大前，预测 ~271）
    V2 输入=1108（放大后，现状，应复现 566.38）
用法： python _exp_ref_pre_upscale.py
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
OUTDIR = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "ref_pre_upscale")
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
A = dict(API)
for k in ("1210", "1211", "1212", "1213", "1214"):
    assert k in A, "缺 %s" % k
# 复制一份左脸提质感段，接到 1105（放大前），与线上现用的 1108（放大后）并排
# ★ 克隆后必须把段内连线一并改到新节点上，否则 1311 还指着旧的 1210（踩过）
BB = dict(A)
for k in ("1210", "1211", "1212", "1213", "1214"):
    BB[str(int(k) + 100)] = json.loads(json.dumps(A[k]))
BB["1310"]["inputs"]["image"] = ["1105", 0]          # 参考图 <- 放大前的 SDXL 直出
BB["1311"]["inputs"]["pixels"] = ["1310", 0]         # VAEEncode <- 新 Scale
BB["1312"]["inputs"]["latent"] = ["1311", 0]         # ReferenceLatent <- 新 latent
BB["1313"]["inputs"]["positive"] = ["1312", 0]       # KSampler <- 新 ReferenceLatent
BB["1314"]["inputs"]["samples"] = ["1313", 0]        # VAEDecode <- 新 KSampler
BB["950"] = {"class_type": "SaveImage", "inputs": {"images": ["1314", 0], "filename_prefix": "V1_输入1105放大前"}}
BB["960"] = {"class_type": "SaveImage", "inputs": {"images": ["1214", 0], "filename_prefix": "V2_输入1108放大后"}}
subg = {k: v for k, v in BB.items() if k in deps(BB, ["950", "960"])}
print("   自检：1311.pixels=%s  1313.positive=%s  1314.samples=%s"
      % (subg["1311"]["inputs"]["pixels"], subg["1313"]["inputs"]["positive"], subg["1314"]["inputs"]["samples"]))
print("=== 提交两个对照 ===")
print("   V1: 1210.image <- 1105（放大前）")
print("   V2: 1210.image <- 1108（放大后，线上现状）")
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
    print("  %-30s lapVar=%7.2f locStd=%.3f" % (tag,
          float(((sliding_window_view(g,(3,3))*k).sum(axis=(-1,-2)))[mm].var()),
          float(sliding_window_view(g,(3,3)).reshape(g.shape[0]-2,g.shape[1]-2,-1).std(axis=-1)[mm].mean())))

print("\n=== 测量（归一到 880x1184）===")
print("  目标：v23 认可正脸 234.81 ｜ 你认可那版侧脸 271.21 ｜ 过火那版 566.38")
for f in sorted(os.listdir(OUTDIR)):
    stats(os.path.join(OUTDIR, f), f[:30])
print("\n产物 -> %s" % OUTDIR)
