# -*- coding: utf-8 -*-
"""回退：左脸的 Flux 提质感段导致变脸 —— 撤销它，保留正脸的提质感

现象
    接入后 左脸成品 lapVar = 566.38（v23 认可正脸是 234.81，即 2.4 倍），用户目视「变脸了」。
    我实验里同一套参数只有 271.21 —— 差别来自参考图：实验用的是「锚=00009」那版左脸，
    线上现在喂的是「锚=SDXL正脸」那版左脸。d1.0 + 纯噪声下身份完全靠参考图，参考一换就重画。

改动（只动左脸，正脸保持不动）
    · 1109(左脸成品).images : 1214 -> 1105     回到 SDXL 直出
    · 1110(右脸翻转).image  : 1214 -> 1108     右脸跟着回 SDXL 直出
    · 1210/1211/1212/1213/1214 置为禁用（节点与参数保留，方便以后调强度再试）
    · 1200/1201（共享提质感词）保持启用 —— 正脸的 1045 还在用它们
    · 1021(正脸成品) 不动，仍是 1047（Flux 提质感后的正脸）

用法： python _revert_flux_left.py dry | run | push
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
OUTDIR = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "revert_flux_left")
WFNAME = "夜市百相簿-主工作流.json"
ENC = urllib.parse.quote(WFNAME, safe='')
MODE = sys.argv[1] if len(sys.argv) > 1 else "dry"
DISABLE = [1210, 1211, 1212, 1213, 1214]
REWIRE = [(1109, "images", 1108, "IMAGE"),      # 左脸成品 <- SDXL 直出（1108 = 放大后 1792x2304，原始接线就是它）
          (1110, "image",  1108, "IMAGE")]      # 右脸翻转 <- SDXL 直出


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


print("=== 1) 拉线上现行版并备份 ===")
wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
byid = {n["id"]: n for n in wf["nodes"]}
ts = time.strftime("%Y%m%d_%H%M%S")
bpath = os.path.join(WFDIR, "_backup_pre_revertflux_%s.json" % ts)
io.open(bpath, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("  nodes=%d links=%d  备份 -> %s" % (len(wf["nodes"]), len(wf["links"]), os.path.basename(bpath)))

changes = []
lid = max(l[0] for l in wf["links"])

def src_of(nid, slot):
    k = next(i for i, x in enumerate(byid[nid]["inputs"]) if x.get("name") == slot)
    l = next((x for x in wf["links"] if x[0] == byid[nid]["inputs"][k].get("link")), None)
    return (l[1], l[0]) if l else (None, None)

for did, dslot, sid, stype in REWIRE:
    o0, lid0 = src_of(did, dslot)
    if lid0:
        s = byid.get(o0)
        if s:
            for o in (s.get("outputs") or []):
                if o.get("links"): o["links"] = [x for x in o["links"] if x != lid0]
        wf["links"] = [x for x in wf["links"] if x[0] != lid0]
    sn = byid[sid]
    oslot = next(k for k, o in enumerate(sn.get("outputs") or []) if o.get("name") == "IMAGE")
    lid += 1
    wf["links"].append([lid, sid, oslot, did, next(i for i, x in enumerate(byid[did]["inputs"]) if x.get("name") == dslot), stype])
    byid[did]["inputs"][next(i for i, x in enumerate(byid[did]["inputs"]) if x.get("name") == dslot)]["link"] = lid
    sn["outputs"][oslot].setdefault("links", [])
    if sn["outputs"][oslot]["links"] is None: sn["outputs"][oslot]["links"] = []
    sn["outputs"][oslot]["links"].append(lid)
    changes.append("#%s.%s 来源 %s -> %s" % (did, dslot, o0, sid))
wf["last_link_id"] = lid

for i in DISABLE:
    byid[i]["mode"] = 2
changes.append("禁用左脸提质感段节点 %s（保留参数，便于以后调强度重试）" % DISABLE)
p1021 = src_of(1021, "images")[0]; p1045 = src_of(1045, "conditioning")[0]
changes.append("保持不动：1021(正脸成品) <- %s（Flux 提质感）；1045 <- %s（共享提质感词）" % (p1021, p1045))

print("\n=== 2) 本次改动 ===")
for c in changes: print("   · %s" % c)
print("   nodes=%d links=%d" % (len(wf["nodes"]), len(wf["links"])))

print("\n=== 3) 自检 ===")
g2 = next(g for g in wf["groups"] if g["id"] == 2)
G = [n for n in wf["nodes"] if n["id"] >= 1000 and n["pos"][0] >= g2["bounding"][0] - 60]
print("   左脸成品来源 = %s（应为 1105）" % byid[1109]["inputs"][next(i for i,x in enumerate(byid[1109]['inputs']) if x.get('name')=='images')].get("link"))
print("   1210-1214 mode = %s" % [byid[i].get("mode") for i in DISABLE])
bad = [i for i in DISABLE if byid[i].get("mode") != 2]
if bad: print("★ 禁用失败 %s" % bad); sys.exit(1)

out_local = os.path.join(WFDIR, "_pending_revertflux.json")
io.open(out_local, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
if MODE == "dry":
    print("\n[dry] 未联网写。"); sys.exit(0)

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
print("   1213 是否还在图内：%s（应为 False）" % ("1213" in subg))
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
def s2(nid, slot):
    k = next(i for i, x in enumerate(bb[nid]["inputs"]) if x.get("name") == slot)
    l = next((x for x in back["links"] if x[0] == bb[nid]["inputs"][k].get("link")), None)
    return l[1] if l else None
ok = (s2(1109, "images") == 1108 and s2(1110, "image") == 1108
      and all(bb[i].get("mode") == 2 for i in DISABLE) and s2(1021, "images") == 1047)
print("   回读：1109<-1108 %s；1110<-1108 %s；左脸提质感段全禁用 %s；1021<-1047 保持 %s"
      % (s2(1109, "images") == 1108, s2(1110, "image") == 1108,
         all(bb[i].get("mode") == 2 for i in DISABLE), s2(1021, "images") == 1047))
io.open(os.path.join(WFDIR, "_live_now.json"), "w", encoding="utf-8").write(json.dumps(back, ensure_ascii=False, indent=1))
if not ok:
    print("★ 校验不过，自动还原 ...")
    raw("/api/userdata/workflows%2F" + ENC, io.open(bpath, encoding="utf-8").read().encode("utf-8"),
        "application/json", 300)
    print("   已还原。"); sys.exit(1)
print("\n✔ 左脸已回到 SDXL 直出；正脸的 Flux 提质感保留")
