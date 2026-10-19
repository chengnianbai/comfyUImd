# -*- coding: utf-8 -*-
"""全身图 ① 修取景：画布改高 + 强制取景词前置 + 负向补裁切词（SDXL 每段 ≤75 token）

依据（实测）：草稿 832×1216 里主体上边距仅 45px、**下边距 0（脚被裁）**
  → 违反 §7 / H14「全身完整入镜、双脚完整入镜、不得裁切」

改动
  · 6 / 302 / 332  EmptyLatentImage：832×1216 -> 768×1344
  · 2 / 300 / 330  正向 A：取景词前置并加强（entire body visible / feet fully visible / wide full-length）
  · 19             负向 N3：补 cropped legs / cropped feet / close-up / portrait crop
本步只跑【草稿】三条，用来量新画布下的头位与头宽（供 ② 贴脸标定用）。

用法： python _fix_fb_step1.py run | push
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
WFDIR = os.path.join(ROOT, "_scripts", "_wf")
OUT = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "fullbody2")
ENC = urllib.parse.quote("夜市百相簿-主工作流.json", safe='')
MODE = sys.argv[1] if len(sys.argv) > 1 else "run"
W, H = 768, 1344

A_FRONT = ("full body shot head to toe, entire body visible, feet fully visible, wide full-length framing, "
           "standing straight, arms naturally at sides, centered, 1boy, solo, 24 year old east asian man, "
           "masculine face, strong jaw, messy wavy black hair, small mole at outer eye corner, "
           "bare upper body, plain white shorts, pure white background")
A_SIDE = ("full body shot head to toe, entire body visible, feet fully visible, wide full-length framing, "
          "side view, side profile, standing straight, arms naturally at sides, centered, 1boy, solo, "
          "24 year old east asian man, masculine face, strong jaw, messy wavy black hair, "
          "bare upper body, plain white shorts, pure white background")
A_BACK = ("full body shot head to toe, entire body visible, feet fully visible, wide full-length framing, "
          "back view, seen from behind, standing straight, arms naturally at sides, centered, 1boy, solo, "
          "24 year old east asian man, messy wavy black hair, bare upper body, back muscles, "
          "plain white shorts, pure white background")
N_ADD = ("cropped legs, cropped feet, cropped ankles, close-up, portrait crop, zoomed in, "
         "half body, knees up")


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
byid = {n["id"]: n for n in wf["nodes"]}
host = urllib.parse.urlparse(BASE).netloc.split(".")[0]
bp = os.path.join(WFDIR, "_backup_pre_fbframe_%s_%s.json" % (host, time.strftime("%Y%m%d_%H%M%S")))
io.open(bp, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("备份 -> %s" % os.path.basename(bp))

for nid in (6, 302, 332):
    old = list(byid[nid]["widgets_values"])
    byid[nid]["widgets_values"] = [W, H, 1]
    print("  #%-4s 画布 %s -> %s" % (nid, old, byid[nid]["widgets_values"]))
for nid, txt in ((2, A_FRONT), (300, A_SIDE), (330, A_BACK)):
    byid[nid]["widgets_values"] = [txt]
    print("  #%-4s 正向A 重写（%d 字符）" % (nid, len(txt)))
old19 = (byid[19].get("widgets_values") or [""])[0]
byid[19]["widgets_values"] = [old19 + ", " + N_ADD]
print("  #19  负向 N3 补 %d 字符" % len(N_ADD))

out_local = os.path.join(WFDIR, "_pending_fbframe.json")
io.open(out_local, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))

sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                       # noqa
API, _ = build_api(wf)
TARGETS = [nid for nid, a in API.items()
           if a["class_type"] == "SaveImage" and str(a["inputs"].get("filename_prefix", "")).endswith("草稿")
           and str(a["inputs"].get("filename_prefix", "")).startswith("闻灯-全身")]
print("\n目标（只跑草稿）：%s" % [API[t]["inputs"]["filename_prefix"] for t in TARGETS])
subg = {k: v for k, v in API.items() if k in deps(API, TARGETS)}
res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 180).decode())
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:1500]); sys.exit(1)
pid = res["prompt_id"]; print("prompt_id=%s" % pid)
done = None
for i in range(400):
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
files = {}
for nid, o in done.items():
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        p = os.path.join(OUT, im["filename"]); open(p, "wb").write(raw("/view?" + q, None, None, 300))
        files[im["filename"]] = p; print("   saved %-44s %7.1f KB" % (im["filename"], os.path.getsize(p)/1024))


def head_geo(p):
    """用「肤色|深色(头发)」的逐行像素数找头部：返回 (头bbox, 身形bbox)"""
    im = Image.open(p).convert("RGB")
    Wp, Hp = im.size
    a = np.asarray(im).astype(np.int16)
    R, G, B = a[:,:,0], a[:,:,1], a[:,:,2]
    mx = np.maximum(np.maximum(R,G),B); mn = np.minimum(np.minimum(R,G),B)
    sat = (mx-mn)/np.maximum(mx,1)
    skin = (R>95)&(R>G)&(G>B)&((R-B)>12)&((R-B)<95)&(sat>0.15)&(sat<0.68)
    dark = (0.299*R+0.587*G+0.114*B) < 78
    hm = skin | dark
    cnt = hm.sum(axis=1)
    thr = Wp*0.02
    rows = np.nonzero(cnt > thr)[0]
    if len(rows) == 0: return None
    top = int(rows[0]); bot = int(rows[-1])
    # 头：从 top 往下，宽度第一次大幅收窄处（脖子）
    seg = cnt[top:top+int((bot-top)*0.45)]
    if len(seg) < 5: return None
    neck = top + int(np.argmin(seg))
    xs = np.nonzero(hm[top:neck].sum(axis=0) > 0)[0]
    head = (int(xs[0]), top, int(xs[-1]), neck)
    return head, (top, bot), Hp


print("\n=== 新画布下的头位/头宽（供 ② 贴脸标定）===")
for fn, p in sorted(files.items()):
    g = head_geo(p)
    if not g: print("  %-30s 量不出" % fn); continue
    head, fig, Hp = g
    hw = head[2]-head[0]; hh = head[3]-head[1]
    print("  %-30s 头 bbox=(x%d..%d, y%d..%d) 宽%d 高%d ；身形 y%d..%d（高%d）；下边距 %d"
          % (fn, head[0], head[2], head[1], head[3], hw, hh, fig[0], fig[1], fig[1]-fig[0], Hp-1-fig[1]))
    print("       → 头身比 ≈ %.2f ；头中心 x ≈ %d ；头顶 y ≈ %d"
          % ((fig[1]-fig[0])/max(hh,1), (head[0]+head[2])//2, head[1]))

if MODE != "push":
    print("\n[run] 未写工作流（只跑了草稿做标定）。"); sys.exit(0)
body = json.dumps(wf, ensure_ascii=False).encode("utf-8")
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
print("\n✔ ① 取景改动已写回线上")
