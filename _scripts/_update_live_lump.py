# -*- coding: utf-8 -*-
"""线上更新 7：消除正脸内眼角肉瘤 —— 正脸提质感改为 T3（d0.93 + 参考 latent + 正向约束词）

依据（_exp_0924/lump/ 三格目视对照）
    基准 00016（无约束, d1.0）        -> 内眼角有肉瘤
    T2（d1.0 + 正向约束词）           -> 仍然有  ★ 光加词没用
    T3（d0.93 + 参考latent + 同词）   -> 干净、平坦 ✅
    => 根因是 d1.0 + 纯噪声的「完全自由」；降下来结构被锚住，肉瘤就不再被脑补出来。

改动
    · 新增 1220 CLIPTextEncode（原提质感词 + 内眼角约束段）+ 1221 FluxGuidance(3.0)
      —— 单独给正脸用，避免把「双眼对称」这类描述塞给只有一只眼的侧面
    · 1045(正脸 ReferenceLatent).conditioning : 1201 -> 1221
    · 1046(正脸提质感 KSampler).denoise        : 1.0  -> 0.93
    · 1046.latent_image                        : 1052(纯噪声) -> 1029(参考 latent)
    · 1200/1201 保持不动（侧脸 1212 还在用）
    · 布局：1220/1221 放到 (0,9)/(1,9) 空位

用法： COMFY_BASE=... python _update_live_lump.py dry | run | push
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
OUTDIR = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "lump_fix")
WFNAME = "夜市百相簿-主工作流.json"
ENC = urllib.parse.quote(WFNAME, safe='')
MODE = sys.argv[1] if len(sys.argv) > 1 else "dry"
X0, Y0, CW, CH = 7700, 380, 800, 520

CLAUSE = ("\n\nBoth eyes are clean and symmetrical, and both inner eye corners (medial canthus) are flat, "
          "smooth and unobtrusive. There is no raised fleshy lump, no enlarged or swollen caruncle, no nodule, "
          "no bump, no growth, no skin tag, no pterygium and no swelling at the inner corner of either eye. "
          "The inner corner of each eye is only a normal flat fold of skin with no protrusion.")


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


print("=== 1) 拉线上现行版并备份 ===")
wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
byid = {n["id"]: n for n in wf["nodes"]}
EX = list(byid); EXL = [l[0] for l in wf["links"]]
host = urllib.parse.urlparse(BASE).netloc.split(".")[0]
bpath = os.path.join(WFDIR, "_backup_pre_lumpfix_%s_%s.json" % (host, time.strftime("%Y%m%d_%H%M%S")))
io.open(bpath, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("  nodes=%d links=%d  备份 -> %s" % (len(wf["nodes"]), len(wf["links"]), os.path.basename(bpath)))
for i in (1220, 1221):
    if i in byid: print("★ id %s 已存在" % i); sys.exit(1)

changes = []
base_prompt = (byid[1200].get("widgets_values") or [""])[0]

# ---- 新增两个节点（克隆 1200/1201）----
n = json.loads(json.dumps(byid[1200])); n["id"] = 1220
n["title"] = "★ 提质感词 · 正脸版（含内眼角约束）"
n["widgets_values"] = [base_prompt + CLAUSE]
n["pos"] = [X0 + 0 * CW, Y0 + 9 * CH]; n["mode"] = 0; n["order"] = 260
for i in (n.get("inputs") or []): i["link"] = None
for o in (n.get("outputs") or []): o["links"] = []
wf["nodes"].append(n); byid[1220] = n
m = json.loads(json.dumps(byid[1201])); m["id"] = 1221
m["title"] = "提质感 · Guidance 3.0（正脸）"
m["widgets_values"] = [3.0]
m["pos"] = [X0 + 1 * CW, Y0 + 9 * CH]; m["mode"] = 0; m["order"] = 261
for i in (m.get("inputs") or []): i["link"] = None
for o in (m.get("outputs") or []): o["links"] = []
wf["nodes"].append(m); byid[1221] = m
changes.append("新增 1220 CLIPTextEncode（词 %d -> %d 字符）+ 1221 FluxGuidance"
               % (len(base_prompt), len(base_prompt + CLAUSE)))

lid = max(EXL)

def unlink(dst, slot):
    d = byid[dst]
    k = next((i for i, x in enumerate(d.get("inputs") or []) if x.get("name") == slot), None)
    if k is None: return None
    old = d["inputs"][k].get("link")
    d["inputs"][k]["link"] = None
    if old is None: return None
    l = next((x for x in wf["links"] if x[0] == old), None)
    if l:
        s = byid.get(l[1])
        if s:
            for o in (s.get("outputs") or []):
                if o.get("links"): o["links"] = [x for x in o["links"] if x != old]
    wf["links"] = [x for x in wf["links"] if x[0] != old]
    return l[1]

# 连线：1025 -> 1220.clip ; 1220 -> 1221.conditioning ; 1221 -> 1045.conditioning ; 1046.latent_image <- 1029
o = unlink(1045, "conditioning"); changes.append("1045.conditioning  %s -> 1221（正脸专用词）" % o)
o2 = unlink(1046, "latent_image"); changes.append("1046.latent_image  %s -> 1029（参考 latent）" % o2)
for sid, sout, did, din in ((1025, "CLIP", 1220, "clip"),
                            (1220, "CONDITIONING", 1221, "conditioning"),
                            (1221, "CONDITIONING", 1045, "conditioning"),
                            (1029, "LATENT", 1046, "latent_image")):
    sn, dn = byid[sid], byid[did]
    oslot = next(k for k, x in enumerate(sn.get("outputs") or []) if x.get("name") == sout)
    dslot = next(k for k, x in enumerate(dn.get("inputs") or []) if x.get("name") == din)
    lid += 1
    wf["links"].append([lid, sid, oslot, did, dslot, "CONDITIONING" if sout == "CONDITIONING" else ("CLIP" if sout == "CLIP" else "LATENT")])
    dn["inputs"][dslot]["link"] = lid
    sn["outputs"][oslot].setdefault("links", [])
    if sn["outputs"][oslot]["links"] is None: sn["outputs"][oslot]["links"] = []
    sn["outputs"][oslot]["links"].append(lid)
wf["last_link_id"] = lid

# denoise
wv = list(byid[1046].get("widgets_values") or [])
while len(wv) < 7: wv.append(None)
old_d = wv[6]; wv[6] = 0.93
byid[1046]["widgets_values"] = wv
changes.append("1046.denoise  %s -> 0.93" % old_d)

print("\n=== 2) 本次改动 ===")
for c in changes: print("   · %s" % c)
print("   nodes=%d links=%d" % (len(wf["nodes"]), len(wf["links"])))

def src(nid, slot):
    i = next((j for j, x in enumerate(byid[nid]["inputs"]) if x.get("name") == slot), None)
    if i is None: return None
    l = next((x for x in wf["links"] if x[0] == byid[nid]["inputs"][i].get("link")), None)
    return l[1] if l else None

print("\n=== 3) 自检 ===")
print("   1045.conditioning <- %s（应 1221）；1046.latent_image <- %s（应 1029）；1046.denoise = %s"
      % (src(1045, "conditioning"), src(1046, "latent_image"), byid[1046]["widgets_values"][6]))
print("   1220 <- %s ；1221 <- %s" % (src(1220, "clip"), src(1221, "conditioning")))
print("   侧脸仍用 1201：1212.conditioning <- %s" % src(1212, "conditioning"))
g2 = next(g for g in wf["groups"] if g["id"] == 2)
G = [x for x in wf["nodes"] if x["id"] >= 1000]
bx, by, bw, bh = g2["bounding"]
outside = [x["id"] for x in G if not (bx-5 <= x["pos"][0] and x["pos"][0]+(x.get("size") or (300,100))[0] <= bx+bw+5
                                      and by-5 <= x["pos"][1] and x["pos"][1]+(x.get("size") or (300,100))[1] <= by+bh+5)]
print("   组盒外的节点：%s" % (outside or "无 ✔"))
bad = (src(1045, "conditioning") != 1221 or src(1046, "latent_image") != 1029
       or byid[1046]["widgets_values"][6] != 0.93 or src(1212, "conditioning") != 1201 or outside)
if bad: print("★ 自检不过"); sys.exit(1)

out_local = os.path.join(WFDIR, "_pending_lumpfix.json")
io.open(out_local, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
if MODE == "dry":
    print("\n[dry] 未联网写。"); sys.exit(0)

sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                       # noqa
API, _ = build_api(wf)
TARGETS = [nid for nid, a in API.items()
           if a["class_type"] == "SaveImage" and a["inputs"].get("filename_prefix", "").startswith("闻灯-脸部")]
print("\n=== 4) 提交跑三张成品 ===")
print("   目标 = %s" % [API[t]["inputs"]["filename_prefix"] for t in TARGETS])
subg = {k: v for k, v in API.items() if k in deps(API, TARGETS)}
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
            for m2 in st.get("messages", []):
                if m2[0] == "execution_error":
                    print("★ ERROR %s: %s" % (m2[1].get("node_type"), m2[1].get("exception_message", "")[:400]))
            sys.exit(1)
        done = h[pid].get("outputs", {}); print("   完成，约 %d 秒" % ((i + 1) * 3)); break
if done is None: print("★ 超时"); sys.exit(1)
os.makedirs(OUTDIR, exist_ok=True)
for nid, o in done.items():
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        p = os.path.join(OUTDIR, im["filename"]); open(p, "wb").write(raw("/view?" + q, None, None, 300))
        print("   saved %-46s %7.1f KB" % (im["filename"], os.path.getsize(p) / 1024))

if MODE != "push":
    print("\n[run] 验证通过，未写工作流。"); sys.exit(0)

print("\n=== 5) 写回线上 ===")
raw("/api/userdata/workflows%2F" + ENC, io.open(out_local, encoding="utf-8").read().encode("utf-8"),
    "application/json", 300)
back = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
bb = {x["id"]: x for x in back["nodes"]}
def s2(nid, slot):
    i = next(j for j, x in enumerate(bb[nid]["inputs"]) if x.get("name") == slot)
    l = next((x for x in back["links"] if x[0] == bb[nid]["inputs"][i].get("link")), None)
    return l[1] if l else None
ok = (s2(1045, "conditioning") == 1221 and s2(1046, "latent_image") == 1029
      and bb[1046]["widgets_values"][6] == 0.93 and s2(1212, "conditioning") == 1201)
print("   回读：1045<-1221 %s；1046<-1029 %s；1046.d=%.2f %s；侧脸仍用1201 %s；nodes=%d links=%d"
      % (s2(1045, "conditioning") == 1221, s2(1046, "latent_image") == 1029,
         bb[1046]["widgets_values"][6], bb[1046]["widgets_values"][6] == 0.93,
         s2(1212, "conditioning") == 1201, len(back["nodes"]), len(back["links"])))
io.open(os.path.join(WFDIR, "_live_now_%s.json" % host), "w", encoding="utf-8").write(json.dumps(back, ensure_ascii=False, indent=1))
if not ok:
    print("★ 校验不过，自动还原 ...")
    raw("/api/userdata/workflows%2F" + ENC, io.open(bpath, encoding="utf-8").read().encode("utf-8"),
        "application/json", 300)
    print("   已还原。"); sys.exit(1)
print("\n✔ 正脸提质感已改为 d0.93 + 参考 latent + 内眼角约束词（肉瘤消除那版）")
