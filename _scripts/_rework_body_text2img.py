# -*- coding: utf-8 -*-
"""角色图工作流：改成「纯文生图全身」——撤掉身份基图与贴脸链路，身份改由提示词承担

用户新思路（2026-10-08）
    「先生成全身图，不要身份基图，完全重新生成，但是需要根据里面的提示词来生成脸，
      只是提示词需要增加全身的提示词」

改动（目标文件 = 夜市百相簿-角色图.json，id f1003783…）
  ① 删除整条「身份基图 + 贴脸」链路（10 个节点）：
       正面 30 LoadImageOutput / 31 ImageScale / 32 SolidMask / 33 FeatherMask / 34 ImageCompositeMasked
       侧面 306/307/308/309/310 （同结构）
     并把放大与成品的输入改为直接接草稿：
       23(正面放大).image <- 8(正面草稿) ；311(侧面放大).image <- 304(侧面草稿)
  ② 撤掉第二段重绘（按附录 B.7）：
       316(侧面成品) <- 312(净2x) ；346(背面成品) <- 342(净2x) ；314/344 置禁用
  ③ 新增「第三段正向词 · 五官/身份」（SDXL 每段 ≤75 token，用 ConditioningCombine 分段编码）
       340 CLIPTextEncode(五官) <- 1003.CLIP
       360 正面 combine(4, 340) → 7.positive ；361 侧面 combine(301, 340) → 303.positive
  ④ 重写三视角 A 段：把「全身取景」词前置，并保留角色身份核心词

用法： python _rework_body_text2img.py dry | run | push
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
OUT = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "body_t2i")
WFNAME = "夜市百相簿-角色图.json"
ENC = urllib.parse.quote(WFNAME, safe='')
MODE = sys.argv[1] if len(sys.argv) > 1 else "dry"

DELETE = [30, 31, 32, 33, 34, 306, 307, 308, 309, 310]
DISABLE = [314, 344]
NEW = [340, 360, 361]

A_FRONT = ("full body shot head to toe, entire body visible, feet fully visible, wide full-length framing, "
           "standing straight, arms naturally at sides, centered composition, 1boy, solo, "
           "24 year old east asian man, masculine face, strong jaw, bare upper body, plain white shorts, "
           "pure white background")
A_SIDE = ("full body shot head to toe, entire body visible, feet fully visible, wide full-length framing, "
          "side view, side profile, standing straight, arms naturally at sides, centered composition, "
          "1boy, solo, 24 year old east asian man, masculine face, strong jaw, bare upper body, "
          "plain white shorts, pure white background")
A_BACK = ("full body shot head to toe, entire body visible, feet fully visible, wide full-length framing, "
          "back view, seen from behind, standing straight, arms naturally at sides, centered composition, "
          "1boy, solo, 24 year old east asian man, messy wavy black hair, bare upper body, back muscles, "
          "plain white shorts, pure white background")
C_FACE = ("detailed face, detailed eyes, clear iris detail, natural thick eyebrows, clean shaven face, "
          "youthful natural skin, realistic skin texture, subtle visible pores, youthful masculine face, "
          "defined youthful jawline, messy wavy black hair with individual hair strands, "
          "small dark mole at outer corner of eye, pure white background")


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
byid = {n["id"]: n for n in wf["nodes"]}
print("目标文件 %s  id=%s  nodes=%d links=%d groups=%d" % (WFNAME, wf.get("id"), len(wf["nodes"]), len(wf["links"]), len(wf.get("groups", []))))
host = urllib.parse.urlparse(BASE).netloc.split(".")[0]
bp = os.path.join(WFDIR, "_backup_pre_bodyt2i_%s_%s.json" % (host, time.strftime("%Y%m%d_%H%M%S")))
io.open(bp, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("备份 -> %s" % os.path.basename(bp))
missing = [i for i in DELETE + DISABLE if i not in byid]
if missing: print("★ 缺节点 %s" % missing); sys.exit(1)
if 340 in byid: print("★ 340 已存在"); sys.exit(1)

lid = max(l[0] for l in wf["links"])


def unlink(dst, slot):
    d = byid[dst]
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


changes = []
# ① 删除贴脸链路
gone = [l for l in wf["links"] if l[1] in DELETE or l[3] in DELETE]
wf["links"] = [l for l in wf["links"] if l[1] not in DELETE and l[3] not in DELETE]
gid = {l[0] for l in gone}
for n in wf["nodes"]:
    for o in (n.get("outputs") or []):
        if o.get("links"): o["links"] = [x for x in o["links"] if x not in gid]
wf["nodes"] = [n for n in wf["nodes"] if n["id"] not in DELETE]
changes.append("删除贴脸链路 %s（含 %d 条连线）" % (DELETE, len(gone)))
# 放大直接接草稿
o1 = unlink(23, "image"); wire(8, "IMAGE", 23, "image", "IMAGE")
changes.append("23(正面放大).image %s -> 8(正面草稿)" % o1)
o2 = unlink(311, "image"); wire(304, "IMAGE", 311, "image", "IMAGE")
changes.append("311(侧面放大).image %s -> 304(侧面草稿)" % o2)

# ② 撤第二段重绘
for did, sid in ((316, 312), (346, 342)):
    o = unlink(did, "images"); wire(sid, "IMAGE", did, "images", "IMAGE")
    changes.append("#%s(成品).images %s -> %s(净2x)" % (did, o, sid))
for i in DISABLE: byid[i]["mode"] = 2
changes.append("第二段重绘 314/344 置禁用（B.7）")

# ③ 第三段正向词 + 两个 combine
n = json.loads(json.dumps(byid[2])); n["id"] = 340
n["title"] = "★ 正向 C · 五官/身份（第三段，突破 75 token）"
n["widgets_values"] = [C_FACE]; n["mode"] = 0; n["order"] = 500
for i in (n.get("inputs") or []): i["link"] = None
for o in (n.get("outputs") or []): o["links"] = []
n["pos"] = [3600, 12000]; wf["nodes"].append(n); byid[340] = n
for nid, src, pos in ((360, 4, [4200, 12000]), (361, 301, [4800, 12000])):
    m = json.loads(json.dumps(byid[4])); m["id"] = nid
    m["title"] = "合并 (A+B) + C（%s）" % ("正面" if nid == 360 else "侧面")
    m["widgets_values"] = []; m["mode"] = 0; m["order"] = 500 + nid
    for i in (m.get("inputs") or []): i["link"] = None
    for o in (m.get("outputs") or []): o["links"] = []
    m["pos"] = pos; wf["nodes"].append(m); byid[nid] = m
wire(1003, "CLIP", 340, "clip", "CLIP")
wire(4, "CONDITIONING", 360, "conditioning_1", "CONDITIONING")
wire(340, "CONDITIONING", 360, "conditioning_2", "CONDITIONING")
wire(301, "CONDITIONING", 361, "conditioning_1", "CONDITIONING")
wire(340, "CONDITIONING", 361, "conditioning_2", "CONDITIONING")
o3 = unlink(7, "positive"); wire(360, "CONDITIONING", 7, "positive", "CONDITIONING")
o4 = unlink(303, "positive"); wire(361, "CONDITIONING", 303, "positive", "CONDITIONING")
changes.append("新增 340(五官词)+360/361(合并 A+B+C)；7.positive %s->360 ；303.positive %s->361" % (o3, o4))

# ④ 重写 A 段
for nid, txt in ((2, A_FRONT), (300, A_SIDE), (330, A_BACK)):
    byid[nid]["widgets_values"] = [txt]
changes.append("重写 A 段（三视角）")

# 组1 包围盒重算
g1 = next(g for g in wf["groups"] if g["id"] == 1)
gn = [x for x in wf["nodes"] if x["id"] < 1000]
bx0 = min(x["pos"][0] for x in gn); by0 = min(x["pos"][1] for x in gn)
bx1 = max(x["pos"][0]+(x.get("size") or (300,100))[0] for x in gn)
by1 = max(x["pos"][1]+(x.get("size") or (300,100))[1] for x in gn)
g1["bounding"] = [bx0-40, by0-40, (bx1-bx0)+120, (by1-by0)+120]
g1["title"] = "【闻灯】全身三视角 · SDXL 纯文生图（身份由提示词承担）"
print("\n=== 本次改动 ===")
for c in changes: print("   · %s" % c)
print("nodes=%d links=%d" % (len(wf["nodes"]), len(wf["links"])))
# 自检：贴脸链路彻底没了
left = [x["id"] for x in wf["nodes"] if x["type"] in ("SolidMask", "FeatherMask", "ImageCompositeMasked")]
print("残留贴脸类节点：%s" % (left or "无 ✔"))
assert not left
assert byid[7]["inputs"][next(i for i,x in enumerate(byid[7]["inputs"]) if x["name"]=="positive")]["link"] is not None

out_local = os.path.join(WFDIR, "_pending_bodyt2i.json")
io.open(out_local, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
if MODE == "dry":
    print("\n[dry] 未联网写。"); sys.exit(0)

sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                       # noqa
API, _ = build_api(wf)
TARGETS = [nid for nid, a in API.items() if a["class_type"] == "SaveImage"
           and str(a["inputs"].get("filename_prefix", "")).startswith("闻灯-全身")
           and str(a["inputs"].get("filename_prefix", "")).endswith("成品")]
print("\n=== 目标输出 %s ===" % [API[t]["inputs"]["filename_prefix"] for t in TARGETS])
subg = {k: v for k, v in API.items() if k in deps(API, TARGETS)}
print("   裁剪后 %d 节点；采样器 %s" % (len(subg),
      sorted([k for k, v in subg.items() if v["class_type"] == "KSampler"], key=int)))
res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 180).decode())
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:1800]); sys.exit(1)
pid = res["prompt_id"]; print("prompt_id=%s" % pid)
done = None
for i in range(500):
    time.sleep(4)
    h = json.loads(raw("/history/" + pid, None, None, 60).decode('utf-8', 'replace'))
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
