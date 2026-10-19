# -*- coding: utf-8 -*-
"""修基图肉瘤（完整链，可回退）：自动量眼位 → 镜像修补 → 上传为新文件 → 把 1004 指向新文件 → 跑图验证

安全设计
    · 原基图只读备份在 _exp_0924/base_repair/base_original.png
    · 修补结果上传为 **新文件名** wendeng_face_base_fixed.png，**不覆盖原图**
    · 1004 只改一个字段指向新文件；不顺就改回 wendeng_face_base.png 即可（一条命令）

用法：
    python _repair_base_lump.py            # 只做修补 + 本地出图（不上传、不改线上）
    python _repair_base_lump.py upload      # 修补 + 上传新文件 + 改 1004 + 跑图验证
"""
import os, sys, io, ssl, json, time, uuid, urllib.request, urllib.parse
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
if not BASE:
    print("★ 先设 COMFY_BASE"); sys.exit(4)
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
ROOT = r"D:\xiaobai-claude code\comfyUImd"
OUT = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "base_repair")
SC = r"C:\Users\ADMINI~1\AppData\Local\Temp\commandcode\D--xiaobai-claude-code-comfyUImd\df01e59d-0f96-4c37-9495-d9508dda8d9a\scratchpad"
WFDIR = os.path.join(ROOT, "_scripts", "_wf")
WFNAME = "夜市百相簿-主工作流.json"
ENC = urllib.parse.quote(WFNAME, safe='')
DO_UPLOAD = "upload" in sys.argv
NEW_NAME = "wendeng_face_base_fixed.png"
os.makedirs(OUT, exist_ok=True)


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


# ---------- 1) 取原基图 ----------
q = urllib.parse.urlencode({"filename": "wendeng_face_base.png", "subfolder": "", "type": "input"})
p_orig = os.path.join(OUT, "base_original.png")
if not os.path.exists(p_orig):
    open(p_orig, "wb").write(raw("/view?" + q, None, None, 300))
im = Image.open(p_orig).convert("RGB")
W, H = im.size
g = np.asarray(im.convert("L")).astype(np.float32)
print("基图 %dx%d" % (W, H))

# ---------- 2) 自动量眼位：眼带内「暗块密度」找两个峰 ----------
band = 255.0 - g[int(H*0.28):int(H*0.50), :]          # 越暗值越大
prof = band.mean(axis=0)
k = np.ones(9)/9.0
prof_s = np.convolve(prof, k, mode="same")
peaks = []
for x in range(30, W-30):
    if prof_s[x] == prof_s[max(0, x-25):x+26].max() and prof_s[x] > prof_s.mean():
        peaks.append((prof_s[x], x))
peaks.sort(reverse=True)
eyes = []
for v, x in peaks:
    if all(abs(x - e) > 70 for e in eyes):
        eyes.append(x)
    if len(eyes) == 2: break
eyes.sort()
print("眼位估计（暗度峰）: %s" % eyes)
if len(eyes) == 2:
    xc = (eyes[0] + eyes[1]) / 2.0
    print("  两眼间距 %d px，中点 xc = %.0f（图像中心 %d）" % (eyes[1]-eyes[0], xc, W//2))
else:
    xc = W/2.0
    print("  峰不足，退回图像中心")

# 在每个眼的 x 邻域内找最暗的一行 = 眼睛的 y
def eye_y(xc0):
    sub = 255.0 - g[int(H*0.25):int(H*0.55), max(0, xc0-45):xc0+45]
    return int(H*0.25) + int(np.argmax(sub.mean(axis=1)))
ey = [eye_y(e) for e in eyes] if len(eyes) == 2 else [int(H*0.40)]*2
print("眼位 y: %s" % ey)

# 内眼角 ≈ 眼中心朝鼻侧偏移约 0.55 个眼半宽
if len(eyes) == 2:
    half = (eyes[1]-eyes[0])/2.0
    inner_off = int(half * 0.55)
    TGT = (eyes[0] + inner_off, ey[0])        # 画面左眼（人物右眼）的内眼角
    SRC = (eyes[1] - inner_off, ey[1])        # 画面右眼的内眼角
else:
    TGT = (463, ey[0]); SRC = (2*xc - 463, ey[1])
print("目标（画面左眼内眼角）= %s ；镜像源（画面右眼内眼角）= %s" % (TGT, SRC))

# ---------- 3) 镜像修补 ----------
PW, PH = 46, 38
def make(pw, ph):
    tx, ty = TGT; sx, sy = SRC
    bt = (tx-pw//2, ty-ph//2, tx-pw//2+pw, ty-ph//2+ph)
    bs = (sx-pw//2, sy-ph//2, sx-pw//2+pw, sy-ph//2+ph)
    if min(bt[0], bt[1], bs[0], bs[1]) < 0 or bt[2] > W or bt[3] > H or bs[2] > W or bs[3] > H:
        return None
    src = im.crop(bs).transpose(Image.FLIP_LEFT_RIGHT)
    out = im.copy()
    yy, xx = np.mgrid[0:ph, 0:pw]
    cy, cx = (ph-1)/2.0, (pw-1)/2.0
    r = np.sqrt(((xx-cx)/(pw/2.0))**2 + ((yy-cy)/(ph/2.0))**2)
    a = np.clip((1.0 - r)/0.5, 0, 1)
    out.paste(src, (bt[0], bt[1]), Image.fromarray((a*255).astype(np.uint8)))
    return out

fixed = make(PW, PH)
if fixed is None:
    print("★ 目标/源块越界，缩小补丁重试"); fixed = make(30, 26)
fixed.save(os.path.join(OUT, NEW_NAME))
print("修补结果已存 -> %s" % os.path.join(OUT, NEW_NAME))

# 前后对照
tx, ty = TGT
tiles = []
for tag, img in (("原图", im), ("修复后", fixed)):
    c = img.crop((max(0, tx-100), max(0, ty-80), min(W, tx+100), min(H, ty+90)))
    tiles.append((tag, c.resize((c.size[0]*4, c.size[1]*4), Image.LANCZOS)))
hh = tiles[0][1].size[1]
cv = Image.new("RGB", (tiles[0][1].size[0]*2+10, hh+26), (255, 255, 255)); d = ImageDraw.Draw(cv)
for i, (t, c) in enumerate(tiles):
    cv.paste(c, (i*(c.size[0]+10), 26)); d.text((i*(c.size[0]+10)+4, 6), t, fill=(0, 0, 0))
o = os.path.join(OUT, "_对照-修补前vs后.png"); cv.save(o)
cv.resize((900, int(900*cv.size[1]/cv.size[0])), Image.LANCZOS).save(os.path.join(SC, "repair_cmp.png"), optimize=True)
print("saved", o, cv.size)

if not DO_UPLOAD:
    print("\n（未上传。确认修补位置对了，再加 upload 参数）")
    sys.exit(0)

# ---------- 4) 上传为新文件 ----------
print("\n=== 上传 %s ===" % NEW_NAME)
png = open(os.path.join(OUT, NEW_NAME), "rb").read()
B = "----wb" + uuid.uuid4().hex
body = io.BytesIO()
def part(s): body.write(s.encode("utf-8"))
part("--%s\r\n" % B); part('Content-Disposition: form-data; name="image"; filename="%s"\r\n' % NEW_NAME)
part("Content-Type: image/png\r\n\r\n"); body.write(png)
part("\r\n--%s\r\n" % B); part('Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n')
part("--%s\r\n" % B); part('Content-Disposition: form-data; name="subfolder"\r\n\r\n\r\n')
part("--%s--\r\n" % B)
try:
    up = raw("/upload/image", body.getvalue(), "multipart/form-data; boundary=%s" % B, 300)
    print("  上传返回:", up.decode('utf-8', 'replace')[:160])
except Exception as e:
    print("  ★ 上传失败", type(e).__name__, str(e)[:150]); sys.exit(1)

# ---------- 5) 改 1004 指向新文件 ----------
print("\n=== 改 1004.image 指向新文件 ===")
wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
byid = {n["id"]: n for n in wf["nodes"]}
host = urllib.parse.urlparse(BASE).netloc.split(".")[0]
bp = os.path.join(WFDIR, "_backup_pre_baserepair_%s_%s.json" % (host, time.strftime("%Y%m%d_%H%M%S")))
io.open(bp, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
old = (byid[1004].get("widgets_values") or [None])[0]
byid[1004]["widgets_values"] = [NEW_NAME, "image"]
print("  1004.image  %r -> %r   备份 %s" % (old, NEW_NAME, os.path.basename(bp)))
raw("/api/userdata/workflows%2F" + ENC, json.dumps(wf, ensure_ascii=False).encode("utf-8"), "application/json", 300)
back = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
bb = {n["id"]: n for n in back["nodes"]}
ok = (bb[1004].get("widgets_values") or [None])[0] == NEW_NAME
print("  回读 1004.image = %r  %s" % ((bb[1004].get("widgets_values") or [None])[0], "✔" if ok else "✘"))
if not ok: sys.exit(1)

# ---------- 6) 跑图验证 ----------
sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                       # noqa
API, _ = build_api(back)
TARGETS = [nid for nid, a in API.items()
           if a["class_type"] == "SaveImage" and str(a["inputs"].get("filename_prefix", "")).startswith("闻灯-脸部")]
subg = {k: v for k, v in API.items() if k in deps(API, TARGETS)}
res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 180).decode())
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:1500]); sys.exit(1)
pid = res["prompt_id"]; print("\n=== 跑图 prompt_id=%s ===" % pid)
done = None
for i in range(400):
    time.sleep(3)
    h = json.loads(raw("/history/" + pid, None, None, 60).decode('utf-8', 'replace'))
    if pid in h:
        st = h[pid].get("status", {})
        if st.get("status_str") == "error":
            for m in st.get("messages", []):
                if m[0] == "execution_error":
                    print("★ ERROR %s: %s" % (m[1].get("node_type"), m[1].get("exception_message", "")[:300]))
            sys.exit(1)
        done = h[pid].get("outputs", {}); print("完成，约 %d 秒" % ((i + 1) * 3)); break
if done is None: print("★ 超时"); sys.exit(1)
RD = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "base_repair_run")
os.makedirs(RD, exist_ok=True)
for nid, o in done.items():
    for im2 in o.get("images", []):
        qq = urllib.parse.urlencode({"filename": im2["filename"], "subfolder": im2.get("subfolder", ""),
                                     "type": im2.get("type", "output")})
        p2 = os.path.join(RD, im2["filename"]); open(p2, "wb").write(raw("/view?" + qq, None, None, 300))
        print("   saved %-46s %7.1f KB" % (im2["filename"], os.path.getsize(p2) / 1024))
print("\n✔ 完成。回退：把 1004.image 改回 'wendeng_face_base.png'（备份 %s）" % os.path.basename(bp))
