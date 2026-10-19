# -*- coding: utf-8 -*-
"""验证「SDXL 产物 → Flux 提质感」到底是不是提升（只提交，不写工作流）

要证的问题
----------
用户方案：1004 唯一基图 → SDXL 出正脸+侧脸 → 把这两张当参考交给 Flux(Kontext) 提质感。
机理上可行（我已验证：参考图与目标视角像素对齐时，Kontext 只重绘表面、姿势几乎不动）。
但风险是：Kontext 会**用自己那套质感覆盖 SDXL 的质感**，而用户明确认可 SDXL 那种肤质。
所以必须实测：Kontext 这一遍之后，到底是变好还是变差。

做法（两个分支，各自单变量）
----------
  E1：SDXL 正脸成品 00011 → Kontext d1.0（纯噪声起点，对齐参考 + 重拍词）
  E2：SDXL 左脸成品 00001 → 同上
参照：SDXL 原件（改前）与 Kontext 90°底稿。

用法： python _exp_flux_enhance.py run
产物： _exp_0924/flux_enhance/
"""
import os, sys, io, ssl, json, time, uuid, urllib.request, urllib.parse
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
if not BASE:
    print("★ 先设 COMFY_BASE"); sys.exit(4)
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
ROOT = r"D:\xiaobai-claude code\comfyUImd"
FIN = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图/_exp_0924/final")
OUTDIR = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "flux_enhance")

UNET = "FLUX1\\flux1-schnell.safetensors"       # 内容是 Kontext fp8
T5 = "t5\\t5xxl_fp8_e4m3fn_scaled.safetensors"
CLIP_L = "clip_l.safetensors"
VAE = "FLUX1\\ae.safetensors"
SEED = 20260920

PROMPT = (
    "Re-photograph this exact portrait as a natural high-end photographic portrait of the same person.\n\n"
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
    "or beauty-filter skin. Do not add freckles, dark spots or scattered dark speckles."
)

SOURCES = [("正脸", "闻灯-脸部正面-成品_00011_.png"),
           ("左脸", "闻灯-脸部左侧-成品_00001_.png")]


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


def build():
    A = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": UNET, "weight_dtype": "default"}},
        "2": {"class_type": "DualCLIPLoader", "inputs": {"clip_name1": T5, "clip_name2": CLIP_L,
                                                        "type": "flux", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
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
        A[str(b + 3)] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["5", 0],
                                                                    "latent": [str(b + 2), 0]}}
        A[str(b + 4)] = {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "positive": [str(b + 3), 0], "negative": ["6", 0],
            "latent_image": ["7", 0], "seed": SEED, "steps": 20, "cfg": 1.0,
            "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}}
        A[str(b + 5)] = {"class_type": "VAEDecode", "inputs": {"samples": [str(b + 4), 0], "vae": ["3", 0]}}
        A[str(b + 6)] = {"class_type": "SaveImage", "inputs": {"images": [str(b + 5), 0],
                                                              "filename_prefix": "闻灯-脸部%s-Flux提质感" % tag}}
        roots.append(str(b + 6))
    return A, roots


A, roots = build()
print("=== 提交 %d 个分支 ===" % len(SOURCES))
for tag, fn in SOURCES:
    print("   %s：%s  → Kontext d1.0（对齐参考 + 重拍词）" % (tag, fn))
res = json.loads(raw("/prompt", json.dumps({"prompt": A, "client_id": str(uuid.uuid4())}).encode(),
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
if done is None:
    print("★ 超时"); sys.exit(1)
os.makedirs(OUTDIR, exist_ok=True)
print("\n=== 下载 ===")
for nid, o in done.items():
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        p = os.path.join(OUTDIR, im["filename"])
        open(p, "wb").write(raw("/view?" + q, None, None, 300))
        print("   saved %-56s %7.1f KB" % (im["filename"], os.path.getsize(p) / 1024))
print("   -> %s" % OUTDIR)
