# -*- coding: utf-8 -*-
"""线上更新 5：把「Flux 提质感」正式接进链路（用户已确认该效果"变好了"）

依据（_exp_0924/flux_enhance/，用户目视确认变好）
    SDXL 正脸 158.65 -> Flux 提质感 420.85 ；SDXL 左脸 119.79 -> 271.21（统一到 880x1184）
    且左脸朝向一丝没动（头发-脸偏移 +0.182 -> +0.182）——对齐参考机理成立。
    对照：同一套对齐重绘用在 Kontext 90° 底稿上只动 2.2% 像素。

改动
----
[正脸 —— 复用现成的 Flux 段，只换提示词 + 让成品存它]
  · 新增 1200 CLIPTextEncode（提质感词，clip<-1025） + 1201 FluxGuidance(3.0)
  · 1045.conditioning : 1044 -> 1201        （正脸的 Flux 段改用实测通过的那套词）
  · 1021(正脸成品).images : 1020 -> 1047    （成品 = Flux 提质感后的图）
  · 1043/1044 置为禁用（原正脸词，文本保留、不再参与执行）
  · 1048 前缀改为「闻灯-脸部-Kontext统一正脸底稿」（它现在与 1021 同源，标成底稿避免混淆）

[左脸 —— 新增一段 Flux 提质感]
  1210 FluxKontextImageScale(image<-1108) -> 1211 VAEEncode -> 1212 ReferenceLatent(cond<-1201)
       -> 1213 KSampler(model<-1024, neg<-1030, latent<-1052 纯噪声, seed 20260920,
                        20步/cfg1.0/euler/simple/**denoise 1.0**)
       -> 1214 VAEDecode
  · 1109(左脸成品).images : 1105 -> 1214
  · 1110(右脸翻转).image  : 1108 -> 1214    （右脸跟着提质感）

[布局] 新节点排在左脸带右侧；1109/1110/1111 顺移；组包围盒随之外扩（仍不碰组1）

用法： python _update_live_fluxstage.py dry | run | push
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
OUTDIR = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "fluxstage")
WFNAME = "夜市百相簿-主工作流.json"
ENC = urllib.parse.quote(WFNAME, safe='')
MODE = sys.argv[1] if len(sys.argv) > 1 else "dry"

X0, Y0, CW, CH = 7700, 380, 800, 520
NEWPOS = {1200: (12, 10), 1201: (13, 10),
          1210: (12, 8), 1211: (13, 8), 1212: (14, 8), 1213: (15, 8), 1214: (16, 8),
          1109: (17, 8), 1110: (17, 9), 1111: (18, 9)}

TEX_PROMPT = (
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

TEMPLATE = {1200: 1043, 1201: 1044, 1210: 1028, 1211: 1029, 1212: 1033, 1213: 1046, 1214: 1047}
TITLE = {1200: "★ 提质感词（实测通过那套）", 1201: "提质感 · Guidance 3.0",
         1210: "左脸 · 提质感 · Kontext 尺寸", 1211: "左脸 · 提质感 · latent",
         1212: "左脸 · 提质感 · 参考进 conditioning",
         1213: "左脸 · Flux 提质感 KSampler（d1.0 纯噪声）", 1214: "左脸 · 提质感 VAEDecode"}
WIRES = [(1025, "CLIP", 1200, "clip"),
         (1200, "CONDITIONING", 1201, "conditioning"),
         (1201, "CONDITIONING", 1212, "conditioning"),
         (1108, "IMAGE", 1210, "image"),
         (1210, "IMAGE", 1211, "pixels"),
         (1026, "VAE", 1211, "vae"),
         (1211, "LATENT", 1212, "latent"),
         (1024, "MODEL", 1213, "model"),
         (1212, "CONDITIONING", 1213, "positive"),
         (1030, "CONDITIONING", 1213, "negative"),
         (1052, "LATENT", 1213, "latent_image"),
         (1213, "LATENT", 1214, "samples"),
         (1026, "VAE", 1214, "vae")]
TYPE = {"IMAGE": "IMAGE", "LATENT": "LATENT", "CONDITIONING": "CONDITIONING",
        "MODEL": "MODEL", "VAE": "VAE", "CLIP": "CLIP"}


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


print("=== 1) 拉线上现行版并备份 ===")
wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
byid = {n["id"]: n for n in wf["nodes"]}
EX_IDS = list(byid); EX_LINKS = [l[0] for l in wf["links"]]
ts = time.strftime("%Y%m%d_%H%M%S")
bpath = os.path.join(WFDIR, "_backup_pre_fluxstage_%s.json" % ts)
io.open(bpath, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("  nodes=%d links=%d  备份 -> %s" % (len(wf["nodes"]), len(wf["links"]), os.path.basename(bpath)))
if set(TEMPLATE) & set(EX_IDS):
    print("★ id 冲突 %s" % sorted(set(TEMPLATE) & set(EX_IDS))); sys.exit(1)

changes = []

# ---- 新增节点（克隆同类型，保证结构合规）----
for nid, src in TEMPLATE.items():
    n = json.loads(json.dumps(byid[src]))
    n["id"] = nid; n["title"] = TITLE[nid]; n["mode"] = 0; n["flags"] = {}
    n["pos"] = [X0 + NEWPOS[nid][0] * CW, Y0 + NEWPOS[nid][1] * CH]
    n["order"] = 200 + nid
    for i in (n.get("inputs") or []): i["link"] = None
    for o in (n.get("outputs") or []): o["links"] = []
    if nid == 1200:   n["widgets_values"] = [TEX_PROMPT]
    elif nid == 1201: n["widgets_values"] = [3.0]
    elif nid == 1213: n["widgets_values"] = [20260920, "fixed", 20, 1.0, "euler", "simple", 1.0]
    else:             n["widgets_values"] = []
    wf["nodes"].append(n); byid[nid] = n
changes.append("新增节点 %s（共享提质感词/guidance + 左脸提质感链）" % sorted(TEMPLATE))

# ---- 连线 ----
lid = max(EX_LINKS)

def unlink(dst_id, dst_slot_name):
    """把某输入的现有连线摘掉（两端都清）"""
    d = byid[dst_id]
    k = next((i for i, x in enumerate(d.get("inputs") or []) if x.get("name") == dst_slot_name), None)
    if k is None: return
    old = d["inputs"][k].get("link")
    d["inputs"][k]["link"] = None
    if old is None: return
    l = next((x for x in wf["links"] if x[0] == old), None)
    if l:
        s = byid.get(l[1])
        if s:
            for o in (s.get("outputs") or []):
                if o.get("links"): o["links"] = [x for x in o["links"] if x != old]
    wf["links"] = [x for x in wf["links"] if x[0] != old]

# 正脸：1045.conditioning 从 1044 改到 1201
unlink(1045, "conditioning")
# 正脸成品：1021.images 从 1020 改到 1047
unlink(1021, "images")
# 左脸成品：1109.images 从 1105 改到 1214
unlink(1109, "images")
# 右脸翻转：1110.image 从 1108 改到 1214
unlink(1110, "image")

ALLW = WIRES + [(1201, "CONDITIONING", 1045, "conditioning"),
                (1047, "IMAGE", 1021, "images"),
                (1214, "IMAGE", 1109, "images"),
                (1214, "IMAGE", 1110, "image")]
for sid, sout, did, din in ALLW:
    sn, dn = byid[sid], byid[did]
    oslot = next((k for k, o in enumerate(sn.get("outputs") or []) if o.get("name") == sout), None)
    dslot = next((k for k, i in enumerate(dn.get("inputs") or []) if i.get("name") == din), None)
    if oslot is None or dslot is None:
        print("★ 连线失败 #%s.%s -> #%s.%s (out=%s in=%s)" % (sid, sout, did, din, oslot, dslot)); sys.exit(1)
    lid += 1
    wf["links"].append([lid, sid, oslot, did, dslot, TYPE[sout]])
    dn["inputs"][dslot]["link"] = lid
    sn["outputs"][oslot].setdefault("links", [])
    if sn["outputs"][oslot]["links"] is None: sn["outputs"][oslot]["links"] = []
    sn["outputs"][oslot]["links"].append(lid)
changes.append("改接 4 处 + 新增连线，共 %d 条新连线" % len(ALLW))
wf["last_link_id"] = lid

# ---- 1043/1044 禁用；1048 改前缀 ----
for i in (1043, 1044): byid[i]["mode"] = 2
changes.append("1043/1044 置为禁用（原正脸词，文本保留）")
p1048 = (byid[1048].get("widgets_values") or [None])[0]
byid[1048]["widgets_values"] = ["闻灯-脸部-Kontext统一正脸底稿"]
changes.append("1048 前缀 %r -> '闻灯-脸部-Kontext统一正脸底稿'" % p1048)

# ---- 布局：新节点位置 / 1109-1111 顺移 / 组盒外扩 ----
for nid, (c, r) in NEWPOS.items():
    byid[nid]["pos"] = [X0 + c * CW, Y0 + r * CH]
changes.append("布局：新节点入排，1109/1110/1111 顺移")

# 组盒重算（只按组内节点）
G = [n for n in wf["nodes"] if n["id"] >= 1000]
xs0 = min(n["pos"][0] for n in G); ys0 = min(n["pos"][1] for n in G)
xs1 = max(n["pos"][0] + (n.get("size") or (300, 100))[0] for n in G)
ys1 = max(n["pos"][1] + (n.get("size") or (300, 100))[1] for n in G)
g2 = next(g for g in wf["groups"] if g["id"] == 2)
oldbox = list(g2["bounding"])
g2["bounding"] = [xs0 - 40, ys0 - 40, (xs1 - xs0) + 120, (ys1 - ys0) + 120]
changes.append("组2 包围盒 %s -> %s" % ([round(v) for v in oldbox], [round(v) for v in g2["bounding"]]))

print("\n=== 2) 本次改动 ===")
for c in changes: print("   · %s" % c)
print("   nodes=%d links=%d" % (len(wf["nodes"]), len(wf["links"])))

# ---- 自检 ----
rects = [(n["id"], n["pos"][0], n["pos"][1], (n.get("size") or (300, 100))[0], (n.get("size") or (300, 100))[1]) for n in G]
ov = [(a[0], b[0]) for i, a in enumerate(rects) for b in rects[i+1:]
      if max(a[1], b[1]) < min(a[1]+a[3], b[1]+b[3]) and max(a[2], b[2]) < min(a[2]+a[4], b[2]+b[4])]
g1 = next(g for g in wf["groups"] if g["id"] == 1)
ax, ay, aw, ah = g2["bounding"]; bx, by, bw, bh = g1["bounding"]
ox = max(0, min(ax+aw, bx+bw) - max(ax, bx)); oy = max(0, min(ay+ah, by+bh) - max(ay, by))
print("\n=== 3) 自检 ===")
print("   组内重叠对：%s" % (ov or "无 ✔"))
print("   与组1 重叠：x %.0f y %.0f %s" % (ox, oy, "✔ 不重叠" if ox*oy == 0 else "★ 重叠"))
if ov or ox*oy: print("★ 自检不过"); sys.exit(1)

out_local = os.path.join(WFDIR, "_pending_fluxstage.json")
io.open(out_local, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
if MODE == "dry":
    print("\n[dry] 未联网写。"); sys.exit(0)

# ---- 跑 ----
sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                       # noqa
API, TITLES = build_api(wf)
TARGETS = [nid for nid, a in API.items()
           if a["class_type"] == "SaveImage" and "脸部" in str(a["inputs"].get("filename_prefix", ""))
           and "底稿" not in str(a["inputs"].get("filename_prefix", ""))
           and "统一正脸" not in str(a["inputs"].get("filename_prefix", ""))
           and "主图" not in str(a["inputs"].get("filename_prefix", ""))]
print("\n=== 4) 目标输出 ===")
for t in sorted(TARGETS, key=lambda x: int(x)):
    print("   #%s  %s" % (t, API[t]["inputs"]["filename_prefix"]))
subg = {k: v for k, v in API.items() if k in deps(API, TARGETS)}
print("   裁剪后 %d 节点；采样器 %s" % (len(subg),
      sorted([k for k, v in subg.items() if v["class_type"] == "KSampler"], key=int)))
res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 180).decode())
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:2000]); sys.exit(1)
pid = res["prompt_id"]; print("\n=== 5) 提交 prompt_id=%s" % pid)
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
        p = os.path.join(OUTDIR, im["filename"])
        open(p, "wb").write(raw("/view?" + q, None, None, 300))
        print("   saved %-52s %7.1f KB" % (im["filename"], os.path.getsize(p) / 1024))

if MODE != "push":
    print("\n[run] 验证通过，未写工作流。"); sys.exit(0)

print("\n=== 6) 写回线上 ===")
raw("/api/userdata/workflows%2F" + ENC, io.open(out_local, encoding="utf-8").read().encode("utf-8"),
    "application/json", 300)
back = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
bb = {n["id"]: n for n in back["nodes"]}
def src(nid, slot):
    k = next(i for i, x in enumerate(bb[nid]["inputs"]) if x.get("name") == slot)
    l = next((x for x in back["links"] if x[0] == bb[nid]["inputs"][k].get("link")), None)
    return l[1] if l else None
ok = (all(i in bb for i in TEMPLATE) and src(1021, "images") == 1047 and src(1109, "images") == 1214
      and src(1213, "positive") == 1212 and bb[1043].get("mode") == 2)
print("   回读：新节点齐 %s；1021<-1047 %s；1109<-1214 %s；1213.pos<-1212 %s；1043禁用 %s；nodes=%d links=%d"
      % (all(i in bb for i in TEMPLATE), src(1021, "images") == 1047, src(1109, "images") == 1214,
         src(1213, "positive") == 1212, bb[1043].get("mode") == 2, len(back["nodes"]), len(back["links"])))
io.open(os.path.join(WFDIR, "_live_now.json"), "w", encoding="utf-8").write(json.dumps(back, ensure_ascii=False, indent=1))
if not ok:
    print("★ 校验不过，自动还原 ...")
    raw("/api/userdata/workflows%2F" + ENC, io.open(bpath, encoding="utf-8").read().encode("utf-8"),
        "application/json", 300)
    print("   已还原。"); sys.exit(1)
print("\n✔ Flux 提质感阶段已接入：三张脸成品都会经过它")
