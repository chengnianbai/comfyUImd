# -*- coding: utf-8 -*-
"""把「取景」改动同步进 角色图 工作流（画布加高 + 负向补裁切词）

A 段里的取景词上一轮已随 _rework_body_text2img.py 写入，这里只补两件：
  · 6 / 302 / 332  EmptyLatentImage：832×1216 -> 768×1344
  · 19            负向 N3：补 cropped legs / cropped feet / close-up / portrait crop
只动这两个变量，便于判断取景变化。

用法： python _sync_frame_to_rolemap.py run | push
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
OUT = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "body_t2i_frame")
WFNAME = "夜市百相簿-角色图.json"
ENC = urllib.parse.quote(WFNAME, safe='')
MODE = sys.argv[1] if len(sys.argv) > 1 else "run"
W, H = 768, 1344
N_ADD = ("cropped legs, cropped feet, cropped ankles, close-up, portrait crop, zoomed in, half body, knees up")


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
byid = {n["id"]: n for n in wf["nodes"]}
assert len(wf["nodes"]) == 113, "节点数不是 113（%d），先确认线上状态" % len(wf["nodes"])
host = urllib.parse.urlparse(BASE).netloc.split(".")[0]
bp = os.path.join(WFDIR, "_backup_pre_rlframe_%s_%s.json" % (host, time.strftime("%Y%m%d_%H%M%S")))
io.open(bp, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("备份 -> %s" % os.path.basename(bp))
for nid in (6, 302, 332):
    old = list(byid[nid]["widgets_values"])
    byid[nid]["widgets_values"] = [W, H, 1]
    print("  #%-4s 画布 %s -> %s" % (nid, old, byid[nid]["widgets_values"]))
old19 = (byid[19].get("widgets_values") or [""])[0]
if "cropped legs" in old19:
    print("  #19  负向已含裁切词（跳过）")
else:
    byid[19]["widgets_values"] = [old19 + ", " + N_ADD]
    print("  #19  负向 N3 补 %d 字符（现 %d）" % (len(N_ADD), len(old19) + len(N_ADD) + 2))
out_local = os.path.join(WFDIR, "_pending_rlframe.json")
io.open(out_local, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))

sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                       # noqa
API, _ = build_api(wf)
TARGETS = [nid for nid, a in API.items() if a["class_type"] == "SaveImage"
           and str(a["inputs"].get("filename_prefix", "")).startswith("闻灯-全身")
           and str(a["inputs"].get("filename_prefix", "")).endswith("成品")]
print("\n目标 %s" % [API[t]["inputs"]["filename_prefix"] for t in TARGETS])
subg = {k: v for k, v in API.items() if k in deps(API, TARGETS)}
res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 180).decode())
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:1500]); sys.exit(1)
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
back = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
bb = {n["id"]: n for n in back["nodes"]}
print("\n回读：nodes=%d  #6=%s  #302=%s  #332=%s  负向含裁切词=%s"
      % (len(back["nodes"]), bb[6]["widgets_values"], bb[302]["widgets_values"], bb[332]["widgets_values"],
         "cropped legs" in (bb[19].get("widgets_values") or [""])[0]))
print("\n✔ 取景已同步进 %s" % WFNAME)
