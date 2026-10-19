# -*- coding: utf-8 -*-
"""解决正脸内眼角肉瘤：两个变体各跑一张，供用户目视挑选

已查明
    · 肉瘤是 Kontext 提质感那一步造出来的（纯 SDXL 正脸 00011 内眼角干净，d1.0 之后才出现）
    · 那一路 cfg=1.0 → **负向词完全失效**，只能在正向词里加约束

两个变体（只差这一处「自由度」）
    T2：正向词加「内眼角干净无隆起」+ 保持 d1.0（不动已认可的质感）
    T3：同一段正向词 + 改为 d0.93 且起点用参考 latent（降低自由度）

用法： COMFY_BASE=... python _exp_lump.py
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
OUT = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "lump")
SC = r"C:\Users\ADMINI~1\AppData\Local\Temp\commandcode\D--xiaobai-claude-code-comfyUImd\df01e59d-0f96-4c37-9495-d9508dda8d9a\scratchpad"
sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                        # noqa

CLAUSE = ("\n\nBoth eyes are clean and symmetrical, and both inner eye corners (medial canthus) are flat, "
          "smooth and unobtrusive. There is no raised fleshy lump, no enlarged or swollen caruncle, no nodule, "
          "no bump, no growth, no skin tag, no pterygium and no swelling at the inner corner of either eye. "
          "The inner corner of each eye is only a normal flat fold of skin with no protrusion.")


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


wf = json.loads(raw("/api/userdata/workflows%2F" + urllib.parse.quote("夜市百相簿-主工作流.json", safe=''),
                    None, None, 120).decode('utf-8', 'replace'))
API, _ = build_api(wf)
base_prompt = API["1200"]["inputs"]["text"]
print("原提质感词 %d 字符；加约束后 %d 字符" % (len(base_prompt), len(base_prompt + CLAUSE)))

A = json.loads(json.dumps(API))
VAR = [("T2_d10", 1.0, "1052"), ("T3_d093", 0.93, "1029")]
roots = []
for i, (tag, den, lat) in enumerate(VAR):
    b = 4000 + i * 10
    A[str(b)] = {"class_type": "CLIPTextEncode", "inputs": {"text": base_prompt + CLAUSE, "clip": ["1025", 0]}}
    A[str(b + 1)] = {"class_type": "FluxGuidance", "inputs": {"conditioning": [str(b), 0], "guidance": 3.0}}
    A[str(b + 2)] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": [str(b + 1), 0], "latent": ["1029", 0]}}
    A[str(b + 3)] = {"class_type": "KSampler", "inputs": {
        "model": ["1024", 0], "positive": [str(b + 2), 0], "negative": ["1030", 0],
        "latent_image": [lat, 0], "seed": 20260920, "steps": 20, "cfg": 1.0,
        "sampler_name": "euler", "scheduler": "simple", "denoise": den}}
    A[str(b + 4)] = {"class_type": "VAEDecode", "inputs": {"samples": [str(b + 3), 0], "vae": ["1026", 0]}}
    A[str(b + 5)] = {"class_type": "SaveImage", "inputs": {"images": [str(b + 4), 0],
                                                          "filename_prefix": "肉瘤测试-%s" % tag}}
    roots.append(str(b + 5))
    print("   %s : denoise=%.2f 起点=%s" % (tag, den, "纯噪声1052" if lat == "1052" else "参考latent1029"))
subg = {k: v for k, v in A.items() if k in deps(A, roots)}
print("裁剪后 %d 节点" % len(subg))
res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 180).decode())
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:2000]); sys.exit(1)
pid = res["prompt_id"]; print("\n提交 prompt_id=%s" % pid)
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
if done is None: print("★ 超时"); sys.exit(1)
os.makedirs(OUT, exist_ok=True)
got = {}
for nid, o in done.items():
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        p = os.path.join(OUT, im["filename"]); open(p, "wb").write(raw("/view?" + q, None, None, 300))
        got[nid] = p; print("   saved %-40s %7.1f KB" % (im["filename"], os.path.getsize(p) / 1024))

# 眼部紧凑裁切对照（含改前 00016 作基准）
prev = os.path.join(OUT, "_基准_改前00016.png")
try:
    q = urllib.parse.urlencode({"filename": "闻灯-脸部正面-成品_00016_.png", "subfolder": "", "type": "output"})
    open(prev, "wb").write(raw("/view?" + q, None, None, 300))
except Exception as e:
    print("  取基准失败", type(e).__name__); prev = None

items = []
if prev and os.path.exists(prev): items.append(("基准 00016 (无约束, d1.0)", prev))
for nid in sorted(got): items.append((os.path.basename(got[nid])[:24], got[nid]))
W = 560
tiles = []
for tag, p in items:
    im = Image.open(p).convert("RGB"); w, h = im.size
    c = im.crop((int(w*0.24), int(h*0.155), int(w*0.62), int(h*0.345)))
    tiles.append((tag, c.resize((W, int(W*c.size[1]/c.size[0])), Image.LANCZOS)))
hh = tiles[0][1].size[1]
cv = Image.new("RGB", (W, (hh+26)*len(tiles)), (255,255,255)); dr = ImageDraw.Draw(cv)
for i,(t,c) in enumerate(tiles):
    cv.paste(c, (0, i*(hh+26)+26)); dr.text((6, i*(hh+26)+6), t, fill=(0,0,0))
out = os.path.join(OUT, "_对照-内眼角.png"); cv.save(out)
cv.save(os.path.join(SC, "lump_cmp.png"))
print("\nsaved", out)
print("产物 -> %s" % OUT)
