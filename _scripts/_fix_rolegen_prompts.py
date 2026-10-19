# -*- coding: utf-8 -*-
"""角色生成.json：修正「提示词被 CLIP 截断」——拆段 + ConditioningCombine，并调 cfg / 尺寸

根因：SDXL 的 CLIP 只吃 77 token（≈300~350 字符），而正向 1368 字符、负向 1263 字符
      ⇒ 只有最前面约 300 字符生效；五官词（约在第 700 字符）与 monolid/flat 等负向全部被丢弃
改法：
  正向拆 A(构图/服装) + B(五官) + C(发型/体型) → ConditioningCombine 合并
  负向拆 两段（最要紧的 monolid/扁平 等挪到第一段开头）→ 合并
  cfg 6.0 -> 7.0 ； EmptyLatentImage 768x1536 -> 768x1344
"""
import os, sys, ssl, json, io, time, uuid, urllib.request, urllib.parse
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
ROOT = r"D:\xiaobai-claude code\comfyUImd"
WFDIR = os.path.join(ROOT, "_scripts", "_wf")
OUT = os.path.join(ROOT, "系列-夜市百相簿/02-角色/角色生成-出图")
ENC = urllib.parse.quote("角色生成.json", safe='')
os.makedirs(OUT, exist_ok=True)

A_POS = ("One man, (24-year-old East Asian man:1.25), single subject, full-length front view head to bare feet, feet "
         "inside frame, neutral standing pose, legs parallel, arms down, hands visible. Plain white tank top tucked "
         "into white mid-thigh shorts, bare feet, plain white studio.")
B_POS = ("(East Asian face, subtle Eurasian eye structure:1.2), (almond brown eyes:1.15), (clearly visible double "
         "eyelid creases on both upper lids:1.3), (deep-set eye sockets, shadow under a defined brow ridge:1.25), "
         "(high straight nasal bridge, defined nose root:1.2), (defined cheeks, jaw:1.1), no makeup.")
C_POS = ("(Dense dark layered wavy-curly hair:1.2), full volume over crown and temples, curls past the ears to the "
         "nape, separated S-locks across the forehead, no visible part line, no exposed scalp. Broad shoulders, "
         "solid build, natural skin, faintly furrowed brows.")
N1 = ("monolid, single eyelid, indistinct double eyelid, epicanthic fold over the crease, shallow-set eyes, flat "
      "brow ridge, low nasal bridge, flat nose, flat face, flat features, cropped head, cropped legs, cropped feet, "
      "partial body, close-up, portrait crop, shoes, socks, shirtless, bare torso")
N2 = ("untucked shirt, shirt hem outside waistband, fabric over waistband, logo, brand mark, emblem, badge, label, "
      "lettering, text, numbers, printed graphic, watermark, makeup, eyeliner, eyeshadow, mascara, false "
      "eyelashes, lipstick, blush, foundation, glamor portrait, airbrushed skin, retouched face")
N3 = ("sitting, kneeling, walking, dynamic pose, crossed legs, hands on hips, arms crossed, leaning, side view, "
      "three-quarter view, back view, multiple people, duplicate subject, collage, short straight hair, flat hair, "
      "visible scalp part, sparse hair, skinny build, bodybuilding, props, jewelry, deformed hands, extra fingers, "
      "fisheye")
for tag, t in (("A_构图", A_POS), ("B_五官", B_POS), ("C_发型体型", C_POS),
               ("N1_负向1", N1), ("N2_负向2", N2), ("N3_负向3", N3)):
    print("  %-10s %4d 字符  ≈ %3d token %s" % (tag, len(t), len(t)/4.0, "✅" if len(t)/4.0 <= 75 else "⚠️ 超 77"))


def get(p, data=None, t=200, ctype="application/json"):
    r = urllib.request.Request(BASE + p, data=data)
    if data is not None:
        r.add_header("Content-Type", ctype)
    return urllib.request.urlopen(r, timeout=t, context=ctx).read()


wf = json.loads(get("/api/userdata/workflows%2F" + ENC).decode('utf-8', 'replace'))
by = {n["id"]: n for n in wf["nodes"]}
L = {l[0]: l for l in wf["links"]}
print("\n原工作流 nodes=%d links=%d ；节点：%s" % (len(wf["nodes"]), len(wf["links"]),
      [(n["id"], n["type"]) for n in sorted(wf["nodes"], key=lambda z: z["id"])]))
bp = os.path.join(WFDIR, "_backup_pre_rolegen_%s.json" % time.strftime("%Y%m%d_%H%M%S"))
io.open(bp, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("备份 -> %s" % os.path.basename(bp))
lid = max([l[0] for l in wf["links"]] or [0])


def mk(nid, ntype, ins, outs, widgets, pos, title):
    n = {"id": nid, "type": ntype, "title": title, "mode": 0, "order": 10 + nid,
         "pos": pos, "size": [240, 100], "flags": {}, "properties": {"Node name for S&R": ntype},
         "inputs": [{"name": k, "type": t, "link": None} for k, t in ins],
         "outputs": [{"name": k, "type": t, "links": []} for k, t in outs],
         "widgets_values": widgets}
    wf["nodes"].append(n); by[nid] = n
    return n


def unlink(dst, slot):
    d = by[dst]
    k = next((i for i, x in enumerate(d.get("inputs") or []) if x.get("name") == slot), None)
    if k is None: return None
    old = d["inputs"][k].get("link"); d["inputs"][k]["link"] = None
    return old


def wire(sid, sout, did, din, stype):
    global lid
    sn, dn = by[sid], by[did]
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


# 1) 改写既有 A 段 / 负向第一段
by[2]["widgets_values"] = [A_POS]; by[2]["title"] = "★ 正向 A · 构图/服装"
by[3]["widgets_values"] = [N1];   by[3]["title"] = "★ 负向 1 · 五官扁平/裁切/服装"
# 2) 新增 B / C / 负向2 / 三个 combine
mk(10, "CLIPTextEncode", [("clip", "CLIP")], [("CONDITIONING", "CONDITIONING")], [B_POS], [-2600, 400], "★ 正向 B · 五官（关键段）")
mk(11, "CLIPTextEncode", [("clip", "CLIP")], [("CONDITIONING", "CONDITIONING")], [C_POS], [-2600, 800], "★ 正向 C · 发型/体型")
mk(13, "CLIPTextEncode", [("clip", "CLIP")], [("CONDITIONING", "CONDITIONING")], [N2], [-2600, 1200], "★ 负向 2 · 服装/logo/妆")
mk(16, "CLIPTextEncode", [("clip", "CLIP")], [("CONDITIONING", "CONDITIONING")], [N3], [-2600, 1500], "★ 负向 3 · 姿态/视图/其他")
mk(12, "ConditioningCombine", [("conditioning_1", "CONDITIONING"), ("conditioning_2", "CONDITIONING")],
   [("CONDITIONING", "CONDITIONING")], [], [-2200, 400], "合并 A+B")
mk(14, "ConditioningCombine", [("conditioning_1", "CONDITIONING"), ("conditioning_2", "CONDITIONING")],
   [("CONDITIONING", "CONDITIONING")], [], [-1900, 400], "★ 合并 (A+B)+C → 正向")
mk(15, "ConditioningCombine", [("conditioning_1", "CONDITIONING"), ("conditioning_2", "CONDITIONING")],
   [("CONDITIONING", "CONDITIONING")], [], [-1900, 900], "合并 负向1+2")
mk(17, "ConditioningCombine", [("conditioning_1", "CONDITIONING"), ("conditioning_2", "CONDITIONING")],
   [("CONDITIONING", "CONDITIONING")], [], [-1600, 900], "★ 合并 (1+2)+3 → 负向")
for nid in (10, 11, 13, 16):
    wire(1, "CLIP", nid, "clip", "CLIP")
wire(2, "CONDITIONING", 12, "conditioning_1", "CONDITIONING")
wire(10, "CONDITIONING", 12, "conditioning_2", "CONDITIONING")
wire(12, "CONDITIONING", 14, "conditioning_1", "CONDITIONING")
wire(11, "CONDITIONING", 14, "conditioning_2", "CONDITIONING")
wire(3, "CONDITIONING", 15, "conditioning_1", "CONDITIONING")
wire(13, "CONDITIONING", 15, "conditioning_2", "CONDITIONING")
wire(15, "CONDITIONING", 17, "conditioning_1", "CONDITIONING")
wire(16, "CONDITIONING", 17, "conditioning_2", "CONDITIONING")
unlink(6, "positive"); unlink(6, "negative")
wire(14, "CONDITIONING", 6, "positive", "CONDITIONING")
wire(17, "CONDITIONING", 6, "negative", "CONDITIONING")
# 3) cfg 6.0 -> 7.0 ； 尺寸 768x1536 -> 768x1344
wv = list(by[6]["widgets_values"]); old_cfg = wv[3]; wv[3] = 7.0; by[6]["widgets_values"] = wv
lv = list(by[5]["widgets_values"]); old_wh = (lv[0], lv[1]); lv[0], lv[1] = 768, 1344; by[5]["widgets_values"] = lv
print("  KSampler cfg %s -> %s" % (old_cfg, by[6]["widgets_values"][3]))
print("  画布 %sx%s -> %sx%s" % (old_wh[0], old_wh[1], by[5]["widgets_values"][0], by[5]["widgets_values"][1]))
print("  nodes=%d links=%d" % (len(wf["nodes"]), len(wf["links"])))
out_local = os.path.join(WFDIR, "_pending_rolegen.json")
io.open(out_local, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))

# 4) 跑（固定种子）
sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                       # noqa
sys.path.insert(0, os.path.join(ROOT, "_scripts"))
import wf_api
wf_api.WIDGETS.update({"CLIPTextEncode": ["text"], "ConditioningCombine": [], "EmptyLatentImage": ["width", "height", "batch_size"]})
API, _ = build_api(wf)
saves = [k for k, v in API.items() if v["class_type"] == "SaveImage"]
print("\n存图节点 %s" % [(k, API[k]["inputs"].get("filename_prefix")) for k in saves])
subg = {k: v for k, v in API.items() if k in deps(API, saves)}
print("提交 %d 节点" % len(subg))
try:
    res = json.loads(get("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(), 180).decode())
except urllib.error.HTTPError as e:
    print("★ HTTP %s: %s" % (e.code, e.read().decode('utf-8', 'replace')[:1200])); sys.exit(1)
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:1500]); sys.exit(1)
pid = res["prompt_id"]; print("pid=%s" % pid)
done = None
for i in range(600):
    time.sleep(4)
    try:
        h = json.loads(get("/history/" + pid, None, 60).decode('utf-8', 'replace'))
    except Exception:
        continue
    if pid in h:
        st = h[pid].get("status", {})
        if st.get("status_str") == "error":
            for m in st.get("messages", []):
                if m[0] == "execution_error":
                    print("★ ERROR %s: %s" % (m[1].get("node_type"), m[1].get("exception_message", "")[:300]))
            sys.exit(1)
        done = h[pid].get("outputs", {}); print("完成 %d 秒" % ((i+1)*4)); break
if done:
    for nid, o in done.items():
        for im in o.get("images", []):
            q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                        "type": im.get("type", "output")})
            p = os.path.join(OUT, im["filename"]); open(p, "wb").write(get("/view?" + q, None, 300))
            print("   saved %s" % im["filename"])
body = io.open(out_local, encoding="utf-8").read().encode("utf-8")
ok = False
for i in range(5):
    try:
        get("/api/userdata/workflows%2F" + ENC, body, 300); ok = True; break
    except Exception as e:
        print("  写回第 %d 次失败 %s" % (i+1, type(e).__name__)); time.sleep(6)
print("✔ 已写回线上" if ok else "★ 写回失败")
