# -*- coding: utf-8 -*-
"""A 路正式形态：带噪声掩膜的扩图（Masked Outpaint）→ 三视角

实测依据（本轮 _stability_test 的结果）
  Flux(ReferenceLatent)  同参考换种子 → 脸部区域差 10.21%  ⇒ 身份由种子决定
  A(SDXL img2img)        同参考换种子 → 脸部区域差  5.90%  ⇒ 身份由像素锁住
且 A 的问题：denoise 0.60 时空白区不会被填 → 必须用 SetLatentNoiseMask，
让「新增区域」按满噪声生成、「脸部区域」保持不动。

结构（每视角）
  已确认脸 → ImageScale(头=179px) → ImagePadForOutpaint(向下留空, 羽化)
      → VAEEncode → SetLatentNoiseMask(新增区掩膜) → KSampler(SDXL, denoise 1.0)
      → VAEDecode → SaveImage
  ★ 头部的像素尺寸 = 179px 直接钉死 7.5 头身 ⇒ 身体比例不可能错
  ★ 背面不能保头（要翻成后脑），故背面不打掩膜、denoise 0.75

用法： python _outpaint_body.py dry | run
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
OUT = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "outpaint")
ENC = urllib.parse.quote("夜市百相簿-主工作流.json", safe='')
MODE = sys.argv[1] if len(sys.argv) > 1 else "dry"
W, H = 768, 1344
HEAD = int(H/7.5)          # 179
TOP = int(H*0.04)          # 54
# 视角： 基准节点, 输入图,        缩放后宽高,         正向combine, 负向, 是否打掩膜, denoise, 存图前缀
VIEWS = [("front", "wendeng_face_base.png", (224, 288), 4, 21, True, 1.0, "闻灯-全身正面-成图A"),
         ("side", "wendeng_id_left_face.png", (215, 289), 301, 21, True, 1.0, "闻灯-全身侧面-成图A"),
         ("back", "wendeng_face_base.png", (224, 288), 331, 21, False, 0.75, "闻灯-全身背面-成图A")]
os.makedirs(OUT, exist_ok=True)


def raw(p, data=None, ctype=None, timeout=900):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


# ---------- 已确认左侧脸：优先用本地已下载副本（新网关 /history 可能为空），裁纯头后上传 ----------
LOCAL_LEFT = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "refgen2",
                          "_src_闻灯-脸部左侧-成品_00012_.png")
srcpath = None
if os.path.exists(LOCAL_LEFT):
    srcpath = LOCAL_LEFT
    print("左侧脸来源：本地副本 %s" % os.path.basename(LOCAL_LEFT))
else:
    hist = json.loads(raw("/history").decode('utf-8', 'replace'))
    best = None
    for pid, rec in hist.items():
        for nid, o in (rec.get("outputs") or {}).items():
            for img in o.get("images", []):
                fn = img.get("filename", "")
                if fn.startswith("闻灯-脸部左侧-成品"):
                    n = int(''.join(ch for ch in fn[len("闻灯-脸部左侧-成品"):] if ch.isdigit()) or 0)
                    if best is None or n > best[0]: best = (n, fn)
    if best:
        q = urllib.parse.urlencode({"filename": best[1], "subfolder": "", "type": "output"})
        srcpath = os.path.join(OUT, "_src_" + best[1]); open(srcpath, "wb").write(raw("/view?" + q))
        print("左侧脸来源：线上 %s" % best[1])
if not srcpath:
    print("★ 找不到已确认左侧脸"); sys.exit(1)
from PIL import Image
im = Image.open(srcpath).convert("RGB"); Wd, Hd = im.size
c = im.crop((int(Wd*0.10), 0, int(Wd*0.94), int(Hd*0.66)))
o = os.path.join(OUT, "wendeng_id_left_face.png"); c.save(o)
print("  纯头裁切 %dx%d → %s" % (c.size[0], c.size[1], os.path.basename(o)))
body = io.open(o, "rb").read(); B = "----cmdc" + uuid.uuid4().hex
part = (("--%s\r\nContent-Disposition: form-data; name=\"image\"; filename=\"wendeng_id_left_face.png\"\r\n"
         "Content-Type: image/png\r\n\r\n" % B).encode() + body +
        ("\r\n--%s\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n--%s--\r\n" % (B, B)).encode())
for t in range(6):
    try:
        r = raw("/upload/image", part, "multipart/form-data; boundary=" + B, 300)
        print("  已上传 %s" % r.decode('utf-8', 'replace')[:120]); break
    except Exception as e:
        print("  上传失败 %s，重试" % type(e).__name__); time.sleep(5)
else:
    print("★ 上传失败"); sys.exit(1)

wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
byid = {n["id"]: n for n in wf["nodes"]}
lid = max(l[0] for l in wf["links"])


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


def clone(nid, tpl, pos, title, widgets=None, newtype=None):
    n = json.loads(json.dumps(byid[tpl])); n["id"] = nid
    if newtype: n["type"] = newtype
    n["title"] = title; n["mode"] = 0; n["order"] = 990 + nid
    for i in (n.get("inputs") or []): i["link"] = None
    for o in (n.get("outputs") or []): o["links"] = []
    if widgets is not None: n["widgets_values"] = widgets
    n["pos"] = pos
    wf["nodes"].append(n); byid[nid] = n
    return n


def mknode(nid, ntype, ins, outs, widgets, pos, title):
    """线上不存在、且没有同类可克隆的节点，手工构造（名字/类型必须与后端一致）"""
    n = {"id": nid, "type": ntype, "title": title, "mode": 0, "order": 990 + nid,
         "pos": pos, "size": [260, 120], "flags": {}, "properties": {"Node name for S&R": ntype},
         "inputs": [{"name": k, "type": t, "link": None} for k, t in ins],
         "outputs": [{"name": k, "type": t, "links": []} for k, t in outs],
         "widgets_values": widgets}
    wf["nodes"].append(n); byid[nid] = n
    return n


TARGETS = []
for i, (tag, src, (sw, sh), pos, neg, masked, dn, pref) in enumerate(VIEWS):
    b = 1500 + i*100
    x = 24200 + i*900
    clone(b+0, 1004, [x, 400], "%s 1 输入已确认脸" % tag, [src, "image"])
    clone(b+1, 1005, [x, 700], "%s 2 缩放（头=%dpx = 7.5 头身）" % (tag, HEAD), ["lanczos", sw, sh, "disabled"])
    mknode(b+2, "ImagePadForOutpaint", [("image", "IMAGE")],
           [("IMAGE", "IMAGE"), ("MASK", "MASK")],
           [(W-sw)//2, TOP, (W-sw)//2, H-sh-TOP, 40], [x, 1000], "%s 3 向下扩出全身画布" % tag)
    clone(b+3, 25, [x, 1300], "%s 4 VAEEncode" % tag)
    clone(b+4, 1015, [x+380, 1700], "%s 5 SDXL 采样 denoise=%.2f%s" % (tag, dn, "（掩膜）" if masked else ""),
          [20260916, "fixed", 30, 10, "dpmpp_2m", "karras", dn])
    clone(b+5, 1016, [x+380, 2200], "%s 6 VAEDecode" % tag)
    clone(b+6, 1021, [x+760, 1700], "%s 7 存图" % tag, [pref], newtype="SaveImage")
    wire(b+0, "IMAGE", b+1, "image", "IMAGE")
    wire(b+1, "IMAGE", b+2, "image", "IMAGE")
    wire(b+2, "IMAGE", b+3, "pixels", "IMAGE")
    wire(1002, "VAE", b+3, "vae", "VAE")
    lat, lat_src = b+3, "LATENT"
    if masked:
        mknode(b+7, "SetLatentNoiseMask", [("samples", "LATENT"), ("mask", "MASK")],
               [("LATENT", "LATENT")], [], [x+180, 1300], "%s 4b SetLatentNoiseMask" % tag)
        wire(b+2, "MASK", b+7, "mask", "MASK")
        wire(b+3, "LATENT", b+7, "samples", "LATENT")
        lat = b+7
    wire(1002, "MODEL", b+4, "model", "MODEL")
    wire(pos, "CONDITIONING", b+4, "positive", "CONDITIONING")
    wire(neg, "CONDITIONING", b+4, "negative", "CONDITIONING")
    wire(lat, "LATENT", b+4, "latent_image", "LATENT")
    wire(b+4, "LATENT", b+5, "samples", "LATENT")
    wire(1002, "VAE", b+5, "vae", "VAE")
    wire(b+5, "IMAGE", b+6, "images", "IMAGE")
    TARGETS.append(str(b+6))
    print("  建 %-6s 分支 #%d..#%d（存图 %s，掩膜=%s，d=%.2f）" % (tag, b, b+6, pref, masked, dn))

print("nodes=%d links=%d" % (len(wf["nodes"]), len(wf["links"])))
out_local = os.path.join(WFDIR, "_pending_outpaint.json")
io.open(out_local, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
if MODE == "dry":
    print("\n[dry] 未联网。"); sys.exit(0)

sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                       # noqa
API, _ = build_api(wf)
missing = [t for t in TARGETS if t not in API]
if missing:
    print("★ 目标节点缺失（多半是节点类型没登记）：%s" % missing); sys.exit(1)
subg = {k: v for k, v in API.items() if k in deps(API, TARGETS)}
print("提交 %d 节点；KSampler %s" % (len(subg), sorted([k for k, v in subg.items() if v["class_type"] == "KSampler"], key=int)))
try:
    res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                         "application/json", 180).decode())
except urllib.error.HTTPError as e:
    print("★ HTTP %s: %s" % (e.code, e.read().decode('utf-8', 'replace')[:1200])); sys.exit(1)
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:1500]); sys.exit(1)
pid = res["prompt_id"]; print("pid=%s" % pid)
done = None
for i in range(900):
    time.sleep(4)
    try:
        h = json.loads(raw("/history/" + pid, None, None, 60).decode('utf-8', 'replace'))
    except Exception:
        continue
    if pid in h:
        st = h[pid].get("status", {})
        if st.get("status_str") == "error":
            for m in st.get("messages", []):
                if m[0] == "execution_error":
                    print("★ ERROR %s: %s" % (m[1].get("node_type"), m[1].get("exception_message", "")[:400]))
            sys.exit(1)
        done = h[pid].get("outputs", {}); print("完成 %d 秒" % ((i+1)*4)); break
if done is None: print("★ 超时"); sys.exit(1)
for nid, o in done.items():
    for im2 in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im2["filename"], "subfolder": im2.get("subfolder", ""),
                                    "type": im2.get("type", "output")})
        p = os.path.join(OUT, im2["filename"]); open(p, "wb").write(raw("/view?" + q, None, None, 300))
        print("   saved %-42s %7.1f KB" % (im2["filename"], os.path.getsize(p)/1024))
print("\n[run] 未写回；先看效果。staged %s" % os.path.basename(out_local))
