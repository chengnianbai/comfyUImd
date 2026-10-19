# -*- coding: utf-8 -*-
"""改为「脸部母版作 Identity Reference → 模型重画完整全身」（彻底删除贴脸链路）

用户的正确路线
    ✅ Face Reference + Character Prompt → Model → New Full Body Character
    ❌ Face → Cutout → Mask → Composite → Full Body

机制（原样克隆脸部组已验证的 Flux 参考潜空间模式）
    1004 脸部母版 ─1300 FluxKontextImageScale─ 1301 VAEEncode(1026 Flux VAE) ─→ 参考 LATENT
    指令词 CLIPTextEncode ─ FluxGuidance(3.0) ─ ReferenceLatent(参考 LATENT) ─→ KSampler.positive
    EmptySD3LatentImage(768x1344) ───────────────────────────────────────────→ KSampler.latent_image
    KSampler(flux-schnell, 20步, cfg 1.0, euler/simple, denoise 1.0)  ← 空潜空间起步 = 整张重画
    → VAEDecode(1026) → 汇入既有放大链路(23/311/341) → 既有「全身正/侧/背-成品」前缀不变

删除（工做流里不应再存在贴脸步骤）
    正面 30 LoadImageOutput / 31 ImageScale / 32 SolidMask / 33 FeatherMask / 34 ImageCompositeMasked
    侧面 306 / 307 / 308 / 309 / 310
    ⇒ 23(正面放大).image 与 311(侧面放大).image 改接新的 Flux 输出

三视角共用：同一张脸部母版参考 + 同一空潜空间 ⇒ §11「三视角同一人物」由机制保障

用法： python _refgen_fullbody.py dry | run | push
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
WFDIR = os.path.join(ROOT, "_scripts", "_wf")
OUT = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "refgen")
WFNAME = "夜市百相簿-主工作流.json"
ENC = urllib.parse.quote(WFNAME, safe='')
MODE = sys.argv[1] if len(sys.argv) > 1 else "dry"
DELETE = [30, 31, 32, 33, 34, 306, 307, 308, 309, 310]
W, H = 768, 1344
SEED = 20261008
BODY = ("Full body visible from head to feet, head to toe, the entire standing figure inside the frame with clear "
        "space above the head and below the feet, standing straight, arms relaxed naturally at the sides, "
        "weight evenly on both feet, feet fully visible, centered composition.")
TAIL = ("Bare upper body, plain white shorts. Pure white seamless background, soft even studio lighting, "
        "unified lighting and material across the whole figure, realistic skin texture with subtle visible pores, "
        "natural photographic grain, sharp focus on the face. Keep the face clearly the same person as the reference.")
IDENT = ("Preserve the exact identity of the reference face: same facial structure and face shape, same facial "
         "proportions, same eyes and eyebrows, same nose shape, same lips, same chin and jawline, same hairline and "
         "haircut, same apparent age, same small mole at the outer corner of the eye, same stable identity marks. "
         "The head, hair, neck, shoulders, torso and legs must be newly drawn as one continuous anatomically correct "
         "body; the head must belong to this body naturally, with a correct neck, trapezius and shoulder structure. ")
FRONT = ("Regenerate this person as a natural high-end photographic full-length studio portrait of the same exact person. "
         + IDENT + "Facing the camera directly, front view, looking at the viewer. " + BODY + " " + TAIL)
SIDE = ("Regenerate this person as a natural high-end photographic full-length studio portrait of the same exact person, "
        "seen from a true anatomical 90-degree LEFT profile, head turned to the left, pure profile view showing the "
        "nose line, lips and jaw line. " + IDENT + BODY + " " + TAIL)
BACK = ("Regenerate this person as a natural high-end photographic full-length studio portrait of the same exact person, "
        "seen from directly behind, back view, the face is not visible; the back of the head, the hair, the neck, the "
        "shoulders, the shoulder blades and the back muscles are visible. Preserve the same hair and the same head "
        "shape as the reference. " + IDENT.replace("Preserve the exact identity of the reference face: ", "")
        + BODY + " " + TAIL)
VIEWS = [(1310, "正面 front", FRONT), (1330, "侧面 side", SIDE), (1350, "背面 back", BACK)]


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
byid = {n["id"]: n for n in wf["nodes"]}
host = urllib.parse.urlparse(BASE).netloc.split(".")[0]
bp = os.path.join(WFDIR, "_backup_pre_refgen_%s_%s.json" % (host, time.strftime("%Y%m%d_%H%M%S")))
io.open(bp, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("线上 nodes=%d links=%d groups=%d" % (len(wf["nodes"]), len(wf["links"]), len(wf.get("groups", []))))
print("备份 -> %s" % os.path.basename(bp))
missing = [i for i in DELETE if i not in byid]
if missing: print("★ 缺节点 %s" % missing); sys.exit(1)
# 克隆源必须存在
TPL = {"ktscale": 1028, "vaeenc": 1029, "empty": 1052, "text": 1031, "guide": 1032,
       "reflat": 1033, "ksampler": 1034, "dec": 1035}
for k, i in TPL.items():
    if i not in byid: print("★ 模板节点 #%s 不存在" % i); sys.exit(1)
lid = max(l[0] for l in wf["links"])


def unlink(dst, slot):
    d = byid.get(dst)
    if not d: return None
    k = next((i for i, x in enumerate(d.get("inputs") or []) if x.get("name") == slot), None)
    if k is None: return None
    old = d["inputs"][k].get("link"); d["inputs"][k]["link"] = None
    if old is None: return None
    l = next((x for x in wf["links"] if x[0] == old), None)
    if l:
        s = byid.get(l[1])
        if s:
            for o in (s.get("outputs") or []):
                if o.get("links"): o["links"] = [x for x in o["links"] if x != old]
    wf["links"] = [x for x in wf["links"] if x[0] != old]
    return l[1] if l else None


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


def clone(key, nid, pos, title, widgets=None):
    n = json.loads(json.dumps(byid[TPL[key]])); n["id"] = nid
    n["title"] = title; n["mode"] = 0; n["order"] = 800 + nid
    for i in (n.get("inputs") or []): i["link"] = None
    for o in (n.get("outputs") or []): o["links"] = []
    if widgets is not None: n["widgets_values"] = widgets
    n["pos"] = pos
    wf["nodes"].append(n); byid[nid] = n
    return n


# ---- 1. 删贴脸链路 ----
gone = [l for l in wf["links"] if l[1] in DELETE or l[3] in DELETE]
wf["links"] = [l for l in wf["links"] if l[1] not in DELETE and l[3] not in DELETE]
gid = {l[0] for l in gone}
for n in wf["nodes"]:
    for o in (n.get("outputs") or []):
        if o.get("links"): o["links"] = [x for x in o["links"] if x not in gid]
wf["nodes"] = [n for n in wf["nodes"] if n["id"] not in DELETE]
print("删除贴脸链路 %s（含 %d 条连线）" % (DELETE, len(gone)))

# ---- 2. 参考潜空间（三视角共用）----
BX, BY = 19600, 400
clone("ktscale", 1300, [BX, BY], "参考图归一化 (FluxKontextImageScale)")
clone("vaeenc", 1301, [BX + 280, BY], "参考 → LATENT (Flux VAE)")
clone("empty", 1302, [BX, BY + 220], "空潜空间 %dx%d（三视角共用 ⇒ 同一个人由机制保障）" % (W, H), [W, H, 1])
wire(1004, "IMAGE", 1300, "image", "IMAGE")
wire(1300, "IMAGE", 1301, "pixels", "IMAGE")
wire(1026, "VAE", 1301, "vae", "VAE")

# ---- 3. 三视角：指令 → FluxGuidance → ReferenceLatent → KSampler → Decode ----
DEC = {1310: 1314, 1330: 1334, 1350: 1354}
for base, label, instr in VIEWS:
    x = BX + 620 + (base // 100 - 13) * 700
    clone("text", base + 0, [x, BY], "★ 指令词 · %s（%d 字符）" % (label, len(instr)), [instr])
    clone("guide", base + 1, [x, BY + 520], "FluxGuidance 3.0")
    clone("reflat", base + 2, [x, BY + 700], "ReferenceLatent（脸部母版）")
    clone("ksampler", base + 3, [x, BY + 880],
          "KSampler · flux-schnell · denoise 1.0（从空潜空间重画）",
          [SEED, "fixed", 20, 1.0, "euler", "simple", 1.0])
    clone("dec", base + 4, [x, BY + 1240], "VAEDecode (Flux VAE)")
    wire(1025, "CLIP", base + 0, "clip", "CLIP")
    wire(base + 0, "CONDITIONING", base + 1, "conditioning", "CONDITIONING")
    wire(base + 1, "CONDITIONING", base + 2, "conditioning", "CONDITIONING")
    wire(1301, "LATENT", base + 2, "latent", "LATENT")
    wire(1024, "MODEL", base + 3, "model", "MODEL")
    wire(base + 2, "CONDITIONING", base + 3, "positive", "CONDITIONING")
    wire(1030, "CONDITIONING", base + 3, "negative", "CONDITIONING")
    wire(1302, "LATENT", base + 3, "latent_image", "LATENT")
    wire(base + 3, "LATENT", base + 4, "samples", "LATENT")
    wire(1026, "VAE", base + 4, "vae", "VAE")
    print("  建分支 %s：#%d 指令 / #%d 引导 / #%d 参考 / #%d 采样 / #%d 解码"
          % (label, base + 0, base + 1, base + 2, base + 3, base + 4))

# ---- 4. 既有放大链路改接 Flux 输出（成品前缀不变）----
for up, dec in ((23, 1314), (311, 1334), (341, 1354)):
    old = unlink(up, "image")
    wire(dec, "IMAGE", up, "image", "IMAGE")
    print("  #%s(放大).image %s -> #%s（Flux 输出）" % (up, old, dec))

left = [n["id"] for n in wf["nodes"] if n["type"] in ("SolidMask", "FeatherMask", "ImageCompositeMasked", "LoadImageOutput")]
print("\n残留贴脸类节点：%s" % (left or "无 ✔"))
assert not left
print("nodes=%d links=%d" % (len(wf["nodes"]), len(wf["links"])))
out_local = os.path.join(WFDIR, "_pending_refgen.json")
io.open(out_local, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
if MODE == "dry":
    print("\n[dry] 未联网。"); sys.exit(0)

# ---- 5. 跑 ----
sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                       # noqa
API, _ = build_api(wf)
TARGETS = [nid for nid, x in API.items() if x["class_type"] == "SaveImage"
           and str(x["inputs"].get("filename_prefix", "")).startswith("闻灯-全身")
           and str(x["inputs"].get("filename_prefix", "")).endswith("成品")]
print("\n=== 目标 %s ===" % [API[t]["inputs"]["filename_prefix"] for t in TARGETS])
subg = {k: v for k, v in API.items() if k in deps(API, TARGETS)}
print("   裁剪后 %d 节点；KSampler %d 个：%s" % (len(subg),
      sum(1 for v in subg.values() if v["class_type"] == "KSampler"),
      sorted([k for k, v in subg.items() if v["class_type"] == "KSampler"], key=int)))
res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 180).decode())
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:1800]); sys.exit(1)
pid = res["prompt_id"]; print("prompt_id=%s" % pid)
done = None
for i in range(600):
    time.sleep(4)
    try:
        h = json.loads(raw("/history/" + pid, None, None, 60).decode('utf-8', 'replace'))
    except Exception as e:
        print("   轮询异常 %s，继续" % type(e).__name__); continue
    if pid in h:
        st = h[pid].get("status", {})
        if st.get("status_str") == "error":
            for m in st.get("messages", []):
                if m[0] == "execution_error":
                    print("★ ERROR %s: %s" % (m[1].get("node_type"), m[1].get("exception_message", "")[:400]))
            sys.exit(1)
        done = h[pid].get("outputs", {}); print("完成，约 %d 秒" % ((i+1)*4)); break
if done is None: print("★ 超时"); sys.exit(1)
os.makedirs(OUT, exist_ok=True)
for nid, o in done.items():
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        p = os.path.join(OUT, im["filename"]); open(p, "wb").write(raw("/view?" + q, None, None, 300))
        print("   saved %-44s %7.1f KB" % (im["filename"], os.path.getsize(p)/1024))
if MODE != "push":
    print("\n[run] 未写工作流。"); sys.exit(0)
body = io.open(out_local, encoding="utf-8").read().encode("utf-8")
ok = False
for i in range(5):
    try:
        r = urllib.request.Request(BASE + "/api/userdata/workflows%2F" + ENC, data=body,
                                   headers={"Content-Type": "application/json",
                                            "Content-Length": str(len(body)), "Connection": "close"})
        urllib.request.urlopen(r, timeout=300, context=ctx).read(); ok = True; break
    except Exception as e:
        print("  第 %d 次写入失败 %s" % (i+1, type(e).__name__)); time.sleep(6)
if not ok: print("★ 写回失败"); sys.exit(1)
print("\n✔ 已写回 %s" % WFNAME)
