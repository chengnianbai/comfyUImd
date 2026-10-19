# -*- coding: utf-8 -*-
"""线上更新 6：左/右脸启用「提质感段」，denoise 用用户选定的 0.93

依据（_exp_0924/f_mid/，用户目视确认 右脸f93_00001 可用）
    f=0.93 输出 lapVar 157.19、朝向偏移 +0.191（参考图偏移 +0.181，姿势基本没动）
    f=1.0 会冲到 566.38（过火/像变脸）；f<=0.85 不干活。用户选定 0.93。
    ★ f<1.0 时起点必须用参考图自身的 latent，否则「低 denoise + 纯噪声」没有意义。

改动
    · 1213 KSampler.denoise : 1.0 -> 0.93
    · 1213 KSampler.latent_image : 1052(纯噪声) -> 1211(参考 latent)
    · 1210-1214 由禁用改为启用
    · 1109(左脸成品).images <- 1214 ；1110(右脸翻转).image <- 1214
    · 正脸不动（1021 仍 <- 1047，提质感段仍 d1.0 —— 那是你先前单独确认过的那版）

用法： python _update_live_side_tex93.py dry | run | push
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
OUTDIR = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "side_tex93")
WFNAME = "夜市百相簿-主工作流.json"
ENC = urllib.parse.quote(WFNAME, safe='')
MODE = sys.argv[1] if len(sys.argv) > 1 else "dry"
ENABLE = [1210, 1211, 1212, 1213, 1214]


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


print("=== 1) 拉线上现行版并备份 ===")
wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
byid = {n["id"]: n for n in wf["nodes"]}
ts = time.strftime("%Y%m%d_%H%M%S")
bpath = os.path.join(WFDIR, "_backup_pre_side93_%s.json" % ts)
io.open(bpath, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("  nodes=%d links=%d  备份 -> %s" % (len(wf["nodes"]), len(wf["links"]), os.path.basename(bpath)))

changes = []
# ---- 1213 参数 ----
k = byid[1213]
old = list(k.get("widgets_values") or [])
wv = list(old)
while len(wv) < 7: wv.append(None)
wv[6] = 0.93
k["widgets_values"] = wv
changes.append("1213.denoise %s -> 0.93" % old[6])
kslot = next(i for i, x in enumerate(k["inputs"]) if x.get("name") == "latent_image")
k["inputs"][kslot]["link"] = None
oldlink = [l for l in wf["links"] if l[3] == 1213 and l[4] == kslot]
for l in oldlink:
    s = byid.get(l[1])
    if s:
        for o in (s.get("outputs") or []):
            if o.get("links"): o["links"] = [x for x in o["links"] if x != l[0]]
wf["links"] = [l for l in wf["links"] if l[0] not in {x[0] for x in oldlink}]
lid = max(l[0] for l in wf["links"]) + 1
wf["links"].append([lid, 1211, 0, 1213, kslot, "LATENT"])
k["inputs"][kslot]["link"] = lid
byid[1211]["outputs"][0].setdefault("links", [])
if byid[1211]["outputs"][0]["links"] is None: byid[1211]["outputs"][0]["links"] = []
byid[1211]["outputs"][0]["links"].append(lid)
changes.append("1213.latent_image  %s -> 1211（参考 latent；f<1.0 必须这样）" % [l[1] for l in oldlink])

# ---- 启用 + 改接成品 ----
for i in ENABLE: byid[i]["mode"] = 0
changes.append("启用 %s" % ENABLE)
lid = max(l[0] for l in wf["links"])
for did, dslot, sid, stype in ((1109, "images", 1214, "IMAGE"), (1110, "image", 1214, "IMAGE")):
    d = byid[did]
    ki = next(i for i, x in enumerate(d["inputs"]) if x.get("name") == dslot)
    ol = [l for l in wf["links"] if l[0] == d["inputs"][ki].get("link")]
    for l in ol:
        s = byid.get(l[1])
        if s:
            for o in (s.get("outputs") or []):
                if o.get("links"): o["links"] = [x for x in o["links"] if x != l[0]]
    wf["links"] = [l for l in wf["links"] if l[0] not in {x[0] for x in ol}]
    sn = byid[sid]
    oslot = next(i for i, o in enumerate(sn["outputs"]) if o.get("name") == "IMAGE")
    lid += 1
    wf["links"].append([lid, sid, oslot, did, ki, stype])
    d["inputs"][ki]["link"] = lid
    sn["outputs"][oslot].setdefault("links", [])
    if sn["outputs"][oslot]["links"] is None: sn["outputs"][oslot]["links"] = []
    sn["outputs"][oslot]["links"].append(lid)
    changes.append("#%s.%s 来源 %s -> 1214" % (did, dslot, [l[1] for l in ol]))
wf["last_link_id"] = lid

print("\n=== 2) 本次改动 ===")
for c in changes: print("   · %s" % c)
print("   nodes=%d links=%d" % (len(wf["nodes"]), len(wf["links"])))

def src(nid, slot):
    i = next((j for j, x in enumerate(byid[nid]["inputs"]) if x.get("name") == slot), None)
    if i is None: return None
    l = next((x for x in wf["links"] if x[0] == byid[nid]["inputs"][i].get("link")), None)
    return (l[1], l[5]) if l else None

print("\n=== 3) 自检 ===")
print("   1213.denoise = %s ；1213.latent_image <- %s" % (byid[1213]["widgets_values"][6], src(1213, "latent_image")))
print("   1109 <- %s ；1110 <- %s" % (src(1109, "images"), src(1110, "image")))
print("   1210 <- %s" % (src(1210, "image"),))
bad = [i for i in ENABLE if byid[i].get("mode") != 0]
if bad: print("★ 启用失败 %s" % bad); sys.exit(1)

out_local = os.path.join(WFDIR, "_pending_side93.json")
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
        print("   saved %-50s %7.1f KB" % (im["filename"], os.path.getsize(p) / 1024))

if MODE != "push":
    print("\n[run] 验证通过，未写工作流。"); sys.exit(0)

print("\n=== 6) 写回线上 ===")
raw("/api/userdata/workflows%2F" + ENC, io.open(out_local, encoding="utf-8").read().encode("utf-8"),
    "application/json", 300)
back = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
bb = {n["id"]: n for n in back["nodes"]}
def s2(nid, slot):
    i = next(j for j, x in enumerate(bb[nid]["inputs"]) if x.get("name") == slot)
    l = next((x for x in back["links"] if x[0] == bb[nid]["inputs"][i].get("link")), None)
    return l[1] if l else None
ok = (bb[1213]["widgets_values"][6] == 0.93 and s2(1213, "latent_image") == 1211
      and s2(1109, "images") == 1214 and s2(1110, "image") == 1214
      and all(bb[i].get("mode") == 0 for i in ENABLE))
print("   回读：1213.d=0.93 %s；1213<-1211 %s；1109<-1214 %s；1110<-1214 %s；全启用 %s；nodes=%d links=%d"
      % (bb[1213]["widgets_values"][6] == 0.93, s2(1213, "latent_image") == 1211,
         s2(1109, "images") == 1214, s2(1110, "image") == 1214,
         all(bb[i].get("mode") == 0 for i in ENABLE), len(back["nodes"]), len(back["links"])))
io.open(os.path.join(WFDIR, "_live_now.json"), "w", encoding="utf-8").write(json.dumps(back, ensure_ascii=False, indent=1))
if not ok:
    print("★ 校验不过，自动还原 ...")
    raw("/api/userdata/workflows%2F" + ENC, io.open(bpath, encoding="utf-8").read().encode("utf-8"),
        "application/json", 300)
    print("   已还原。"); sys.exit(1)
print("\n✔ 左/右脸已启用提质感段（denoise 0.93，起点=参考 latent）")
