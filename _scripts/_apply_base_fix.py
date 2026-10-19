# -*- coding: utf-8 -*-
"""执行基图修补并跑图：目标点 (463,420)（用户坐标 + 格子图判读相互印证）

做法
    1. 生成三个修补版本（C1 鼻梁方向克隆 / C2 下方颊部克隆 / C3 平滑填充），都存本地
    2. 默认采用 C1（保真实毛孔纹理），上传为新文件 wendeng_face_base_fixed.png（不覆盖原图）
    3. 1004.image 指向新文件（先备份），回读校验
    4. 跑三张成品 + 出「修补前/后」内眼角对照，供验收
回退：把 1004.image 改回 wendeng_face_base.png（备份见打印）
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
BR = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "base_repair")
RD = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "base_fixed_run")
SC = r"C:\Users\ADMINI~1\AppData\Local\Temp\commandcode\D--xiaobai-claude-code-comfyUImd\df01e59d-0f96-4c37-9495-d9508dda8d9a\scratchpad"
WFDIR = os.path.join(ROOT, "_scripts", "_wf")
ENC = urllib.parse.quote("夜市百相簿-主工作流.json", safe='')
NEW_NAME = "wendeng_face_base_fixed.png"
TX, TY = 463, 420
PW, PH = 42, 36


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


os.makedirs(BR, exist_ok=True)
im = Image.open(os.path.join(BR, "base_original.png")).convert("RGB")
W, H = im.size
print("基图 %dx%d ；目标点 (%d,%d) ；补丁 %dx%d" % (W, H, TX, TY, PW, PH))


def feather(w, h, soft=0.5):
    yy, xx = np.mgrid[0:h, 0:w]
    cy, cx = (h-1)/2.0, (w-1)/2.0
    r = np.sqrt(((xx-cx)/(w/2.0))**2 + ((yy-cy)/(h/2.0))**2)
    return Image.fromarray((np.clip((1.0-r)/soft, 0, 1)*255).astype(np.uint8))


def clone(sx, sy):
    bt = (TX-PW//2, TY-PH//2); bs = (sx-PW//2, sy-PH//2)
    if min(bs[0], bs[1]) < 0 or bs[0]+PW > W or bs[1]+PH > H: return None
    out = im.copy()
    out.paste(im.crop((bs[0], bs[1], bs[0]+PW, bs[1]+PH)), bt, feather(PW, PH))
    return out


def smooth():
    out = im.copy()
    box = (TX-PW//2, TY-PH//2, TX-PW//2+PW, TY-PH//2+PH)
    reg = im.crop(box)
    mix = Image.blend(reg.filter(ImageFilter.GaussianBlur(8)), reg.filter(ImageFilter.MedianFilter(7)), 0.6)
    out.paste(mix, (box[0], box[1]), feather(PW, PH, 0.6))
    return out


CAND = {"C1_鼻梁侧克隆": clone(TX+62, TY), "C2_下方颊部克隆": clone(TX, TY+62), "C3_平滑填充": smooth()}
for k, v in CAND.items():
    if v is None:
        print("  %s 越界" % k); CAND.pop(k, None); continue
    v.save(os.path.join(BR, "_候选_%s.png" % k.split("_")[0]))
    print("  已生成 %s" % k)

USE = "C1_鼻梁侧克隆" if "C1_鼻梁侧克隆" in CAND else list(CAND)[0]
fixed = CAND[USE]
fixed.save(os.path.join(BR, NEW_NAME))
print("采用 %s -> %s" % (USE, os.path.join(BR, NEW_NAME)))

# 修补前/后内眼角对照
tiles = []
for tag, img in (("原图", im), ("修复后 (%s)" % USE, fixed)):
    c = img.crop((max(0, TX-130), max(0, TY-110), min(W, TX+130), min(H, TY+120)))
    tiles.append((tag, c.resize((c.size[0]*3, c.size[1]*3), Image.LANCZOS)))
hh = tiles[0][1].size[1]
cv = Image.new("RGB", (tiles[0][1].size[0]*2+10, hh+26), (255,255,255)); d = ImageDraw.Draw(cv)
for i, (t, c) in enumerate(tiles):
    cv.paste(c, (i*(c.size[0]+10), 26)); d.text((i*(c.size[0]+10)+4, 6), t, fill=(0,0,0))
o = os.path.join(BR, "_对照-修补前vs后-内眼角.png"); cv.save(o)
cv.resize((980, int(980*cv.size[1]/cv.size[0])), Image.LANCZOS).save(os.path.join(SC, "fix_cmp.png"), optimize=True)
print("saved", o)

# ---------- 上传为新文件 ----------
print("\n=== 上传 %s ===" % NEW_NAME)
png = open(os.path.join(BR, NEW_NAME), "rb").read()
B = "----wb" + uuid.uuid4().hex
body = io.BytesIO()
def part(s): body.write(s.encode("utf-8"))
part("--%s\r\n" % B); part('Content-Disposition: form-data; name="image"; filename="%s"\r\n' % NEW_NAME)
part("Content-Type: image/png\r\n\r\n"); body.write(png)
part("\r\n--%s\r\n" % B); part('Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n')
part("--%s\r\n" % B); part('Content-Disposition: form-data; name="subfolder"\r\n\r\n\r\n')
part("--%s--\r\n" % B)
try:
    payload = body.getvalue()
    ok_up = False
    for attempt in range(4):
        try:
            r = urllib.request.Request(BASE + "/upload/image", data=payload, headers={
                "Content-Type": "multipart/form-data; boundary=%s" % B,
                "Content-Length": str(len(payload)),
                "Connection": "close",
            })
            resp = urllib.request.urlopen(r, timeout=300, context=ctx).read().decode('utf-8', 'replace')
            print("  上传返回:", resp[:140]); ok_up = True; break
        except Exception as e:
            print("  第 %d 次上传失败：%s %s" % (attempt+1, type(e).__name__, str(e)[:90]))
            time.sleep(4)
    if not ok_up:
        print("  ★ 上传最终失败（%d 字节）" % len(payload)); sys.exit(1)
except Exception as e:
    print("  ★ 上传失败", type(e).__name__, str(e)[:150]); sys.exit(1)

# ---------- 改 1004 ----------
wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
byid = {n["id"]: n for n in wf["nodes"]}
host = urllib.parse.urlparse(BASE).netloc.split(".")[0]
bp = os.path.join(WFDIR, "_backup_pre_baserepair_%s_%s.json" % (host, time.strftime("%Y%m%d_%H%M%S")))
io.open(bp, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
old = (byid[1004].get("widgets_values") or [None])[0]
byid[1004]["widgets_values"] = [NEW_NAME, "image"]
raw("/api/userdata/workflows%2F" + ENC, json.dumps(wf, ensure_ascii=False).encode("utf-8"), "application/json", 300)
back = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
bb = {n["id"]: n for n in back["nodes"]}
print("  1004.image %r -> %r ；回读=%r %s" % (old, NEW_NAME, (bb[1004].get("widgets_values") or [None])[0],
      "✔" if (bb[1004].get("widgets_values") or [None])[0] == NEW_NAME else "✘"))
print("  回退：把 1004.image 改回 %r（备份 %s）" % (old, os.path.basename(bp)))

# ---------- 跑 ----------
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
os.makedirs(RD, exist_ok=True)
front = None
for nid, o in done.items():
    for im2 in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im2["filename"], "subfolder": im2.get("subfolder", ""),
                                    "type": im2.get("type", "output")})
        p2 = os.path.join(RD, im2["filename"]); open(p2, "wb").write(raw("/view?" + q, None, None, 300))
        print("   saved %-46s %7.1f KB" % (im2["filename"], os.path.getsize(p2) / 1024))
        if "正面" in im2["filename"]: front = p2
if front:
    imf = Image.open(front).convert("RGB"); w, h = imf.size
    c = imf.crop((int(w*0.20), int(h*0.26), int(w*0.62), int(h*0.50)))
    c.resize((c.size[0]*3, c.size[1]*3), Image.LANCZOS).save(os.path.join(RD, "_正脸内眼角放大-x3.png"))
    print("  saved _正脸内眼角放大-x3.png")
print("\n产物 -> %s" % RD)
