# -*- coding: utf-8 -*-
"""A 路原型 + 决定性度量：固定其它、只换种子，测「脸部区域差异」

目的：不靠嘴说，量出两条路的身份稳定性
  路·Flux = 现在的 ReferenceLatent 分支（空潜空间 + reference，denoise 1.0）
  路·A    = SDXL img2img：已确认脸按 7.5 头身摆进 768x1344 画布（下留空），denoise 0.60
  度量    = 同一条路、两个种子，脸部区域的平均绝对差（归一化 %）
            差小 ⇒ 身份由像素锁住 ；差大 ⇒ 身份由种子决定

只试验，不写回线上。
"""
import os, sys, io, ssl, json, time, uuid, urllib.request, urllib.parse
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
import numpy as np
from PIL import Image
BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
if not BASE:
    print("★ 先设 COMFY_BASE"); sys.exit(4)
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
ROOT = r"D:\xiaobai-claude code\comfyUImd"
OUT = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "stability")
ENC = urllib.parse.quote("夜市百相簿-主工作流.json", safe='')
os.makedirs(OUT, exist_ok=True)
H = 1344
SEEDS = (111111, 222222)


def raw(p, data=None, ctype=None, timeout=900):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                       # noqa
wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
byid = {n["id"]: n for n in wf["nodes"]}
print("线上 nodes=%d links=%d" % (len(wf["nodes"]), len(wf["links"])))
lid = max(l[0] for l in wf["links"])


def wire(sid, sout, did, din, stype):
    global lid
    sn, dn = byid[sid], byid[did]
    oslot = next((k for k, o in enumerate(sn.get("outputs") or []) if o.get("name") == sout), None)
    dslot = next((k for k, x in enumerate(dn.get("inputs") or []) if x.get("name") == din), None)
    if oslot is None or dslot is None:
        print("★ 连线失败 #%s.%s -> #%s.%s" % (sid, sout, did, din)); sys.exit(1)
    lid += 1
    wf["links"].append([lid, sid, oslot, did, dslot, stype])
    dn["inputs"][dslot]["link"] = lid
    sn["outputs"][oslot].setdefault("links", [])
    if sn["outputs"][oslot]["links"] is None: sn["outputs"][oslot]["links"] = []
    sn["outputs"][oslot]["links"].append(lid)


def clone(nid, tpl, pos, title, widgets=None, newtype=None, tpl_by=None):
    src = (tpl_by or byid)[tpl]
    n = json.loads(json.dumps(src)); n["id"] = nid
    if newtype: n["type"] = newtype
    n["title"] = title; n["mode"] = 0; n["order"] = 950 + nid
    for i in (n.get("inputs") or []): i["link"] = None
    for o in (n.get("outputs") or []): o["links"] = []
    if widgets is not None: n["widgets_values"] = widgets
    n["pos"] = pos
    wf["nodes"].append(n); byid[nid] = n
    return n


clone(1400, 1004, [22800, 400], "A1 载入已确认脸（输入像素 = 身份来源）", ["wendeng_face_base.png", "image"])
clone(1401, 1005, [22800, 700], "A2 缩放（头 → 179px = 7.5 头身）", ["lanczos", 224, 288, "disabled"])
clone(1402, 1400, [22800, 1000], "A3 向下留空（outpaint，灰底+羽化）", [272, 54, 272, H-288-54, 40],
      newtype="ImagePadForOutpaint")
clone(1403, 25, [22800, 1300], "A4 VAEEncode")
clone(1404, 1015, [23200, 1600], "★ A5 SDXL img2img denoise 0.60（身份靠像素传）",
      [SEEDS[0], "fixed", 30, 10, "dpmpp_2m", "karras", 0.60])
clone(1405, 1016, [23200, 2100], "A6 VAEDecode")
clone(1406, 1021, [23600, 1600], "A7 存图（试验）", ["ZZ-试验A-全身-成品"], newtype="SaveImage")
wire(1400, "IMAGE", 1401, "image", "IMAGE")
wire(1401, "IMAGE", 1402, "image", "IMAGE")
wire(1402, "IMAGE", 1403, "pixels", "IMAGE")
wire(1002, "VAE", 1403, "vae", "VAE")
wire(1002, "MODEL", 1404, "model", "MODEL")
wire(4, "CONDITIONING", 1404, "positive", "CONDITIONING")
wire(21, "CONDITIONING", 1404, "negative", "CONDITIONING")
wire(1403, "LATENT", 1404, "latent_image", "LATENT")
wire(1404, "LATENT", 1405, "samples", "LATENT")
wire(1002, "VAE", 1405, "vae", "VAE")
wire(1405, "IMAGE", 1406, "images", "IMAGE")
print("已建 A 试验分支 #1400..#1406")

API, _ = build_api(wf)
got = {}
for label, ks, target in (("A", "1404", "1406"), ("Flux", "1316", "15")):
    for s in SEEDS:
        need = deps(API, [ks]) | deps(API, [target])
        sub = {k: json.loads(json.dumps(v)) for k, v in API.items() if k in need}
        sub[ks]["inputs"]["seed"] = s
        try:
            res = json.loads(raw("/prompt", json.dumps({"prompt": sub, "client_id": str(uuid.uuid4())}).encode(),
                                 "application/json", 180).decode())
        except urllib.error.HTTPError as e:
            print("★ HTTP %s: %s" % (e.code, e.read().decode('utf-8', 'replace')[:900])); sys.exit(1)
        if res.get("node_errors"):
            print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:900]); sys.exit(1)
        pid = res["prompt_id"]; print("\n[%s] seed=%d pid=%s" % (label, s, pid))
        done = None
        for i in range(900):
            time.sleep(4)
            try:
                h = json.loads(raw("/history/" + pid, None, None, 60).decode('utf-8', 'replace'))
            except Exception:
                continue
            if pid in h:
                st = h[pid].get("status", {})
                if st.get("status_str") == "error":
                    for m in st.get("messages", []):
                        if m[0] == "execution_error":
                            print("★ ERROR %s: %s" % (m[1].get("node_type"), m[1].get("exception_message", "")[:300]))
                    sys.exit(1)
                done = h[pid].get("outputs", {}); print("   完成 %d 秒" % ((i+1)*4)); break
        if done is None: print("★ 超时"); sys.exit(1)
        for nid, o in done.items():
            for im2 in o.get("images", []):
                q = urllib.parse.urlencode({"filename": im2["filename"], "subfolder": im2.get("subfolder", ""),
                                            "type": im2.get("type", "output")})
                p = os.path.join(OUT, "%s_seed%d_%s" % (label, s, im2["filename"]))
                open(p, "wb").write(raw("/view?" + q, None, None, 300))
                got[(label, s)] = p; print("   saved %s" % os.path.basename(p))


def face_region(path):
    im = Image.open(path).convert("RGB"); Wd, Hd = im.size
    c = im.crop((int(Wd*0.30), int(Hd*0.01), int(Wd*0.70), int(Hd*0.22))).resize((256, 256), Image.LANCZOS)
    return np.asarray(c).astype(np.int16)


print("\n=== 稳定性度量（同一条路、只换种子 → 脸部区域平均绝对差）===")
for label in ("Flux", "A"):
    if (label, SEEDS[0]) in got and (label, SEEDS[1]) in got:
        d = np.abs(face_region(got[(label, SEEDS[0])]) - face_region(got[(label, SEEDS[1])])).mean()
        print("  %-5s ：%6.2f/255 = %5.2f%%   %s" % (label, d, 100*d/255,
              "差异小 → 身份被锁住" if d < 18 else "差异大 → 身份由种子决定"))
print("\n[试验] 未写回线上。图在 %s" % OUT)
