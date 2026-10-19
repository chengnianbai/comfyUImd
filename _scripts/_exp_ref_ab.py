# -*- coding: utf-8 -*-
"""A/B：同一套 Flux 提质感链路，只换参考图 —— 证明「为什么之前那张质感出来了、现在不行」

假设
----
用户的实验版 闻灯-脸部左脸-Flux提质感_00001_.png（lapVar 271.21，他认可）
    参考图 = 闻灯-脸部左侧-成品_00001_.png  ← 锚=00009 时代的左脸
线上那版（lapVar 566.38，变脸）
    参考图 = 锚=SDXL正脸 时代的左脸

本脚本：同一套链路（LoadImageOutput -> FluxKontextImageScale -> VAEEncode -> ReferenceLatent
        -> KSampler d1.0 纯噪声 seed 20260920 -> VAEDecode），只把参考图换成两张不同的，
        一次提交、并排比。

用法： python _exp_ref_ab.py
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
OUTDIR = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "ref_ab")


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


# 先看看服务器 output 里都有哪些「左脸成品」候选
print("=== 0) output 目录里的左脸成品 ===")
try:
    files = json.loads(raw("/internal/files/output", 120).decode('utf-8', 'replace'))
    cand = [f for f in files if "左侧脸-成品" in f]
    for f in cand:
        print("   ", f)
except Exception as e:
    print("   ERR", type(e).__name__)

SOURCES = [("A_旧锚00009", "闻灯-脸部左侧-成品_00001_.png"),     # 实验那版读的
           ("B_新锚SDXL", "闻灯-脸部左侧-成品_00002_.png")]      # 线上那版读的
PROMPT = ("Re-photograph this exact portrait as a natural high-end photographic portrait of the same person.\n\n"
          "Keep exactly the same head direction, viewing angle, facial identity, facial proportions, eyes, "
          "eyebrows, nose, lips, jaw, cheekbones, hair, mole placement, clothing, crop, framing, lighting "
          "direction and background.\n\n"
          "Do not turn, rotate or move the head. Do not change the viewing angle. Do not redesign, beautify, "
          "age, symmetrize or replace his face.\n\n"
          "Regenerate ONLY the photographic surface and the skin material: natural visible pores, fine skin "
          "micro-texture, natural skin grain, subtle skin tone variation, individual eyebrow hairs, realistic "
          "short stubble with visible skin between the hairs, a few fine flyaway hair strands.\n\n"
          "The realism must come from a real photographic skin surface with genuine micro-detail, not from "
          "sharpening. Keep restrained film grain and natural color, and keep the same photographic rendering, "
          "lighting and color grading as the input image.\n\n"
          "Do not smooth the skin excessively. Do not create airbrushed, plastic, porcelain, waxy, polished "
          "or beauty-filter skin. Do not add freckles, dark spots or scattered dark speckles.")

A = {
    "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "FLUX1\\flux1-schnell.safetensors", "weight_dtype": "default"}},
    "2": {"class_type": "DualCLIPLoader", "inputs": {"clip_name1": "t5\\t5xxl_fp8_e4m3fn_scaled.safetensors",
                                                    "clip_name2": "clip_l.safetensors", "type": "flux", "device": "default"}},
    "3": {"class_type": "VAELoader", "inputs": {"vae_name": "FLUX1\\ae.safetensors"}},
    "4": {"class_type": "CLIPTextEncode", "inputs": {"text": PROMPT, "clip": ["2", 0]}},
    "5": {"class_type": "FluxGuidance", "inputs": {"conditioning": ["4", 0], "guidance": 3.0}},
    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["2", 0]}},
    "7": {"class_type": "EmptySD3LatentImage", "inputs": {"width": 880, "height": 1184, "batch_size": 1}},
}
roots = []
for i, (tag, fn) in enumerate(SOURCES):
    b = 100 + i * 10
    A[str(b)] = {"class_type": "LoadImageOutput", "inputs": {"image": fn + " [output]"}}
    A[str(b + 1)] = {"class_type": "FluxKontextImageScale", "inputs": {"image": [str(b), 0]}}
    A[str(b + 2)] = {"class_type": "VAEEncode", "inputs": {"pixels": [str(b + 1), 0], "vae": ["3", 0]}}
    A[str(b + 3)] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["5", 0], "latent": [str(b + 2), 0]}}
    A[str(b + 4)] = {"class_type": "KSampler", "inputs": {
        "model": ["1", 0], "positive": [str(b + 3), 0], "negative": ["6", 0], "latent_image": ["7", 0],
        "seed": 20260920, "steps": 20, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}}
    A[str(b + 5)] = {"class_type": "VAEDecode", "inputs": {"samples": [str(b + 4), 0], "vae": ["3", 0]}}
    A[str(b + 6)] = {"class_type": "SaveImage", "inputs": {"images": [str(b + 5), 0],
                                                          "filename_prefix": "参考AB-%s" % tag}}
    roots.append(str(b + 6))
    # 顺便把参考图也存一份，确认读到的就是那张
    A[str(b + 7)] = {"class_type": "SaveImage", "inputs": {"images": [str(b), 0],
                                                          "filename_prefix": "参考AB-%s-参考原图" % tag}}
    roots.append(str(b + 7))

print("\n=== 1) 提交（只换参考图，其余逐字段相同）===")
res = json.loads(raw("/prompt", json.dumps({"prompt": A, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 180).decode())
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:2000]); sys.exit(1)
pid = res["prompt_id"]; print("   prompt_id=%s" % pid)
done = None
for i in range(300):
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
for nid, o in done.items():
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        p = os.path.join(OUTDIR, im["filename"])
        open(p, "wb").write(raw("/view?" + q, None, None, 300))

def stats(p, tag):
    im = Image.open(p).convert("RGB")
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
    sk = (RR>95)&(RR>GG)&(GG>BB)&((RR-BB)>12)&((RR-BB)<90)&(ss>0.12)&(ss<0.65); dk = gg<70
    ys,xs = np.nonzero(sk); ys2,xs2 = np.nonzero(dk)
    off = (xs2.mean()-xs.mean())/max(xs.max()-xs.min(),1) if sk.sum()>200 and dk.sum()>200 else float('nan')
    print("  %-40s lapVar=%7.2f locStd=%.3f 偏移=%+6.3f" % (tag,
          float(((sliding_window_view(g,(3,3))*k).sum(axis=(-1,-2)))[mm].var()),
          float(sliding_window_view(g,(3,3)).reshape(g.shape[0]-2,g.shape[1]-2,-1).std(axis=-1)[mm].mean()), off))

print("\n=== 2) 测量（归一到 880x1184）===")
print("  参照：实验版(旧锚参考) = 271.21 ｜ 线上版(新锚参考) = 566.38")
for f in sorted(os.listdir(OUTDIR)):
    if f.startswith("参考AB-"):
        stats(os.path.join(OUTDIR, f), f[:44])
print("\n产物 -> %s" % OUTDIR)
