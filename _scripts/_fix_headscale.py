# -*- coding: utf-8 -*-
"""标定贴脸尺寸（头身比 → 7~8 头身）

做法（不猜，用实测反推）
    1. 在刚跑出来的「正面成品」里量出：头顶 y、脖子(下巴下沿) y、脚底 y
       → 当前头身比 = 身形高 / 头高
    2. 目标 7.5 头身 → 需要的贴图高度 = 现贴图高度 × (当前头身比 / 7.5)
       （贴图尺寸与头高成正比，这是同一张脸缩放的线性关系）
    3. 把 307(ImageScale) 与 308(SolidMask) 两处改成新尺寸（必须一致），提交跑一版验证

用法： COMFY_BASE=... python _fix_headscale.py run | push
"""
import os, sys, io, ssl, json, time, uuid, urllib.request, urllib.parse
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
import numpy as np
from PIL import Image, ImageDraw

BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
if not BASE:
    print("★ 先设 COMFY_BASE"); sys.exit(4)
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
ROOT = r"D:\xiaobai-claude code\comfyUImd"
FB = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "fullbody")
WFDIR = os.path.join(ROOT, "_scripts", "_wf")
SC = r"C:\Users\ADMINI~1\AppData\Local\Temp\commandcode\D--xiaobai-claude-code-comfyUImd\df01e59d-0f96-4c37-9495-d9508dda8d9a\scratchpad"
ENC = urllib.parse.quote("夜市百相簿-主工作流.json", safe='')
MODE = sys.argv[1] if len(sys.argv) > 1 else "run"
CUR_W, CUR_H = 200, 257          # 当前贴图尺寸（线上 307/308）
TARGET = 7.5                     # 目标头身比


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


def measure(p, pw=None, ph=None):
    """返回 (头身比, ...)。★ 用「头宽」反推头高：成年人的头高 ≈ 1.35 × 头宽。
       头宽只在**贴图块内部的上半部**量，避免把肩膀/手臂算进来。
       pw/ph = 这次要量的那张图所用的贴图尺寸（默认当前的 200x257）。"""
    pw = pw or CUR_W; ph = ph or CUR_H
    im = Image.open(p).convert("RGB")
    W, H = im.size
    a = np.asarray(im).astype(np.int16)
    white = (a[:,:,0] > 235) & (a[:,:,1] > 235) & (a[:,:,2] > 235)
    body = ~white
    rows = body.sum(axis=1)
    nz = np.nonzero(rows > W*0.01)[0]
    if len(nz) == 0: return None
    top, bot = int(nz[0]), int(nz[-1])
    fig_h = bot - top
    # 贴图块在成品中的位置：草稿里贴 (316,6) 尺寸 200x257，成品是草稿的 2 倍
    bx0, by0 = int(316 * W / 832), int(6 * H / 1216)
    bw, bh = int(pw * W / 832), int(ph * H / 1216)
    sub = body[by0:by0+int(bh*0.62), max(0, bx0-60):min(W, bx0+bw+60)]
    if sub.size == 0: return None
    w_head = int(sub.sum(axis=1).max())
    if w_head < 10: return None
    head_h = 1.35 * w_head
    return fig_h / head_h, top, bot, w_head, H, fig_h


print("=== 1) 量当前头身比 ===")
cur = os.path.join(FB, "闻灯-全身正面-成品_00001_.png")
if not os.path.exists(cur):
    print("★ 缺 %s" % cur); sys.exit(1)
r = measure(cur)
if not r:
    print("★ 量不出来"); sys.exit(1)
heads, top, bot, w_head, H, fig_h = r
print("  头顶 y=%d  脚底 y=%d  图高 %d  身形高 %d px" % (top, bot, H, fig_h))
print("  头宽 %d px → 推算头高 ≈ %.0f px  → 当前头身比 ≈ %.2f 头身" % (w_head, 1.35*w_head, heads))

new_h = int(round(CUR_H * heads / TARGET))
new_h = max(120, min(new_h, 320))
new_w = int(round(new_h * CUR_W / CUR_H))
print("\n=== 2) 按比例反推 ===")
print("  目标 %.1f 头身 → 贴图高度 %.0f × (%.2f / %.1f) = %d px ；宽 %d px"
      % (TARGET, CUR_H, heads, TARGET, new_h, new_w))
print("  （%dx%d → %dx%d）" % (CUR_W, CUR_H, new_w, new_h))

# ---- 改线上 API 里的两个节点并提交 ----
wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
byid = {n["id"]: n for n in wf["nodes"]}
print("\n  线上 31(正面)=%s / 32(正面)=%s" % (byid[31]["widgets_values"], byid[32]["widgets_values"]))
print("  线上 307(侧面)=%s / 308(侧面)=%s" % (byid[307]["widgets_values"], byid[308]["widgets_values"]))
# ★ 正面用的是 31/32，侧面用的是 307/308 —— 两套必须一起改，否则只有一个视角会变
byid[31]["widgets_values"] = ["lanczos", new_w, new_h, "center"]
byid[32]["widgets_values"] = [1, new_w, new_h]
byid[307]["widgets_values"] = ["lanczos", new_w, new_h, "center"]
byid[308]["widgets_values"] = [1, new_w, new_h]

sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                       # noqa
API, _ = build_api(wf)
TARGETS = [nid for nid, a in API.items()
           if a["class_type"] == "SaveImage" and a["inputs"].get("filename_prefix") in (
               "闻灯-全身正面-成品", "闻灯-全身侧面-成品", "闻灯-全身背面-成品")]
print("\n=== 3) 提交三张成品 ===")
for t in sorted(TARGETS, key=lambda x: int(x)): print("   #%s %s" % (t, API[t]["inputs"]["filename_prefix"]))
subg = {k: v for k, v in API.items() if k in deps(API, TARGETS)}
res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 180).decode())
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:1500]); sys.exit(1)
pid = res["prompt_id"]; print("   prompt_id=%s" % pid)
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
        done = h[pid].get("outputs", {}); print("   完成，约 %d 秒" % ((i + 1) * 4)); break
if done is None: print("★ 超时"); sys.exit(1)
OUT2 = os.path.join(FB, "headscale_%dx%d" % (new_w, new_h))
os.makedirs(OUT2, exist_ok=True)
newfiles = {}
for nid, o in done.items():
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        p = os.path.join(OUT2, im["filename"]); open(p, "wb").write(raw("/view?" + q, None, None, 300))
        newfiles[im["filename"]] = p
        print("   saved %-42s %7.1f KB" % (im["filename"], os.path.getsize(p) / 1024))

print("\n=== 4) 复量 ===")
for fn, p in sorted(newfiles.items()):
    if "正面" in fn:
        r2 = measure(p, new_w, new_h)
        if r2: print("  %s  → 头身比 ≈ %.2f（目标 %.1f）" % (fn, r2[0], TARGET))

# 对照图
def strip(items, out, cw=360, ch=463):
    cv = Image.new("RGB", (len(items)*cw, ch+28), (255,255,255)); dr = ImageDraw.Draw(cv)
    for i,(t,p) in enumerate(items):
        cv.paste(Image.open(p).convert("RGB").resize((cw,ch), Image.LANCZOS), (i*cw, 28))
        dr.text((i*cw+5, 8), t, fill=(0,0,0))
    cv.save(out); print("saved", out, cv.size)
    return cv
old = [(t, os.path.join(FB, fn)) for t, fn in (("原 200x257 正面", "闻灯-全身正面-成品_00001_.png"),
                                               ("原 200x257 侧面", "闻灯-全身侧面-成品_00001_.png"),
                                               ("原 200x257 背面", "闻灯-全身背面-成品_00001_.png"))]
new = [(("新 %dx%d " % (new_w, new_h)) + t.split()[-1], p) for t, p in
       [(k, v) for k, v in sorted(newfiles.items())]]
cv1 = strip(old, os.path.join(OUT2, "_对照-旧.png"))
cv2 = strip(new, os.path.join(OUT2, "_对照-新.png"))
cv1.resize((1080, int(1080*cv1.size[1]/cv1.size[0])), Image.LANCZOS).save(os.path.join(SC, "hs_old.png"), optimize=True)
cv2.resize((1080, int(1080*cv2.size[1]/cv2.size[0])), Image.LANCZOS).save(os.path.join(SC, "hs_new.png"), optimize=True)

if MODE != "push":
    print("\n[run] 未写工作流（只跑了验证）。"); sys.exit(0)

print("\n=== 5) 写回线上（307/308 新尺寸）===")
body = json.dumps(wf, ensure_ascii=False).encode("utf-8")
okp = False
for i in range(5):
    try:
        r = urllib.request.Request(BASE + "/api/userdata/workflows%2F" + ENC, data=body,
                                   headers={"Content-Type": "application/json",
                                            "Content-Length": str(len(body)), "Connection": "close"})
        urllib.request.urlopen(r, timeout=300, context=ctx).read(); okp = True; break
    except Exception as e:
        print("   第 %d 次失败 %s %s" % (i+1, type(e).__name__, str(e)[:80])); time.sleep(6)
if not okp: print("★ 写回失败"); sys.exit(1)
back = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
bb = {n["id"]: n for n in back["nodes"]}
print("   回读：31=%s 32=%s ；307=%s 308=%s" % (bb[31]["widgets_values"], bb[32]["widgets_values"],
                                          bb[307]["widgets_values"], bb[308]["widgets_values"]))
print("\n✔ 贴脸尺寸已标定为 %dx%d" % (new_w, new_h))
