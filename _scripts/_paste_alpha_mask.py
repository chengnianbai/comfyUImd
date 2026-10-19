# -*- coding: utf-8 -*-
"""把「贴脸」的矩形掩膜换成头部剪影 alpha（最小改动：像素/尺寸/落点/采样参数全不变）

原链路（正面）
    30 LoadImageOutput ──31 ImageScale──┐
                                        └─→ 34 ImageCompositeMasked(dest=8, x=316, y=6)
    32 SolidMask(1,200,257) ──33 FeatherMask──┘        ← ★ 矩形，把背景/衣领一起贴上去
侧面 306/307/308/309 → 310 同结构

问题：矩形 mask 会贴上贴图块的背景与衣领，且遮不住生成头像露在矩形外的部分。

改法（每视角 4 节点 → 1 节点）
    · 本地生成「贴入尺寸(200×257) 就带 alpha」的头部抠图 → 上传为 wendeng_head_alpha_200x257.png
    · 新增 LoadImage(该文件)：IMAGE 直接当 source（尺寸已对，故不需 ImageScale）、MASK 直接当 mask
    · 删除 30/31/32/33 与 306/307/308/309
    · 34/310 的 image 与 mask 改接新 LoadImage

alpha 构造：肤色 ∪ 头发（头发只取下巴以上，避开深色衣物），再羽化。
★ 不动脸部母版、不动任何采样参数、不动尺寸与落点。

用法： python _paste_alpha_mask.py make | run | push
"""
import os, sys, io, ssl, json, time, uuid, urllib.request, urllib.parse
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
import numpy as np
from PIL import Image, ImageFilter
BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
if not BASE:
    print("★ 先设 COMFY_BASE"); sys.exit(4)
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
ROOT = r"D:\xiaobai-claude code\comfyUImd"
WFDIR = os.path.join(ROOT, "_scripts", "_wf")
OUT = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "alpha_paste")
EXP = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924")
WFNAME = "夜市百相簿-主工作流.json"
ENC = urllib.parse.quote(WFNAME, safe='')
MODE = sys.argv[1] if len(sys.argv) > 1 else "make"
PW, PH = 200, 257
CUT = os.path.join(OUT, "wendeng_head_alpha_%dx%d.png" % (PW, PH))
DELETE = [30, 31, 32, 33, 306, 307, 308, 309]
NEWIMG = {34: 1230, 310: 1240}        # 目标合成节点 -> 新的 LoadImage 节点 id
SRC_FACE = os.path.join(EXP, "merged2/闻灯-脸部正面-成品_00019_.png")


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


# ============ 1. 造带 alpha 的头部抠图（就是原贴图块的像素，只是背景变透明） ============
if MODE == "make":
    os.makedirs(OUT, exist_ok=True)
    src = Image.open(SRC_FACE).convert("RGB")
    W0, H0 = src.size
    a = np.asarray(src).astype(np.int16)
    R, G, B = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    gray = 0.299*R + 0.587*G + 0.114*B
    hair = (gray < 90) & (np.arange(H0)[:, None] < H0*0.70)      # 只取下巴以上，避开深色衣物
    skin = (R > 90) & (R > G) & (G > B) & ((R - B) > 15) & ((R - B) < 95)
    m = (skin | hair).astype(np.uint8) * 255
    print("源图 %dx%d ；头发 %d px（限 y<%.0f）；肤色 %d px；并集占比 %.1f%%"
          % (W0, H0, hair.sum(), H0*0.70, skin.sum(), 100*(skin|hair).sum()/(W0*H0)))
    small = src.resize((PW, PH), Image.LANCZOS)
    am = Image.fromarray(m, "L").resize((PW, PH), Image.LANCZOS)
    am = am.filter(ImageFilter.GaussianBlur(2.4))
    # 边缘再收一点，避免带上光晕
    am = am.point(lambda v: 0 if v < 60 else (255 if v > 190 else int((v-60)*255/130)))
    cut = small.convert("RGBA"); cut.putalpha(am)
    cut.save(CUT)
    print("saved %s  %dx%d  (alpha 覆盖 %.1f%%)" % (CUT, PW, PH, 100*np.asarray(am).mean()/255))
    # 预览（棋盘底）
    ck = Image.new("RGB", (PW, PH), (255, 255, 255))
    px = ck.load()
    for yy in range(0, PH, 12):
        for xx in range(0, PW, 12):
            if ((xx//12)+(yy//12)) % 2 == 0:
                for j in range(12):
                    for i in range(12):
                        if xx+i < PW and yy+j < PH: px[xx+i, yy+j] = (205, 205, 205)
    pv = ck.convert("RGBA"); pv.alpha_composite(cut)
    S = 2.6
    cv = Image.new("RGB", (int(PW*S)*2+30, int(PH*S)+30), (250, 250, 250))
    from PIL import ImageDraw
    dr = ImageDraw.Draw(cv)
    cv.paste(small.resize((int(PW*S), int(PH*S)), Image.LANCZOS), (10, 26))
    cv.paste(pv.convert("RGB").resize((int(PW*S), int(PH*S)), Image.LANCZOS), (int(PW*S)+20, 26))
    dr.text((12, 7), "原贴图块（含背景/衣领）", fill=(0, 0, 0))
    dr.text((int(PW*S)+22, 7), "新：头部剪影 alpha（棋盘=透明）", fill=(0, 0, 0))
    o = os.path.join(OUT, "_预览-剪影掩膜.png"); cv.save(o); print("saved 预览 %s" % o)
    cv.resize((900, int(900*cv.size[1]/cv.size[0])), Image.LANCZOS).save(
        r"C:\Users\ADMINI~1\AppData\Local\Temp\commandcode\D--xiaobai-claude-code-comfyUImd\df01e59d-0f96-4c37-9495-d9508dda8d9a\scratchpad\cutout.png", optimize=True)
    if MODE == "make":
        sys.exit(0)

# ============ 2. 上传抠图到 input ============
BOUND = "----cmdc" + uuid.uuid4().hex
data = io.open(CUT, "rb").read()
fn = os.path.basename(CUT)
part = (("--%s\r\nContent-Disposition: form-data; name=\"image\"; filename=\"%s\"\r\n"
         "Content-Type: image/png\r\n\r\n" % (BOUND, fn)).encode() + data +
        ("\r\n--%s\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n"
         "--%s--\r\n" % (BOUND, BOUND)).encode())
print("\n上传 %s（%d 字节）" % (fn, len(data)))
try:
    r = raw("/upload/image", part, "multipart/form-data; boundary=" + BOUND, 300)
    print("  上传返回 %s" % r.decode('utf-8', 'replace')[:200])
except Exception as e:
    print("★ 上传失败 %s %s" % (type(e).__name__, str(e)[:200])); sys.exit(1)

# ============ 3. 改工作流 ============
wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
byid = {n["id"]: n for n in wf["nodes"]}
host = urllib.parse.urlparse(BASE).netloc.split(".")[0]
bp = os.path.join(WFDIR, "_backup_pre_alphamask_%s_%s.json" % (host, time.strftime("%Y%m%d_%H%M%S")))
io.open(bp, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("备份 -> %s" % os.path.basename(bp))
missing = [i for i in DELETE if i not in byid]
if missing: print("★ 缺节点 %s" % missing); sys.exit(1)
lid = max(l[0] for l in wf["links"])


def unlink(dst, slot):
    d = byid[dst]
    k = next((i for i, x in enumerate(d.get("inputs") or []) if x.get("name") == slot), None)
    old = d["inputs"][k].get("link") if k is not None else None
    if k is not None: d["inputs"][k]["link"] = None
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


# 新 LoadImage（每个合成节点一个，避免同一输出被多处引用时的歧义）
for dst, nid in NEWIMG.items():
    tpl = byid[30] if 30 in byid else None
    n = json.loads(json.dumps(tpl)); n["id"] = nid
    n["type"] = "LoadImage"; n["title"] = "★ 头部剪影 alpha（%dx%d，自带 alpha 当 mask）" % (PW, PH)
    n["widgets_values"] = [fn, "image"]; n["mode"] = 0; n["order"] = 700 + nid
    for i in (n.get("inputs") or []): i["link"] = None
    for o in (n.get("outputs") or []): o["links"] = []
    n["pos"] = [-2600, 3000 + (nid % 100) * 320]
    wf["nodes"].append(n); byid[nid] = n

gone = [l for l in wf["links"] if l[1] in DELETE or l[3] in DELETE]
wf["links"] = [l for l in wf["links"] if l[1] not in DELETE and l[3] not in DELETE]
gid = {l[0] for l in gone}
for n in wf["nodes"]:
    for o in (n.get("outputs") or []):
        if o.get("links"): o["links"] = [x for x in o["links"] if x not in gid]
wf["nodes"] = [n for n in wf["nodes"] if n["id"] not in DELETE]
print("删除 %s（含 %d 条连线）" % (DELETE, len(gone)))

for dst, nid in NEWIMG.items():
    o1 = unlink(dst, "destination"); o2 = unlink(dst, "source"); o3 = unlink(dst, "mask")
    wire(8 if dst == 34 else 304, "IMAGE", dst, "destination", "IMAGE")
    wire(nid, "IMAGE", dst, "source", "IMAGE")
    wire(nid, "MASK", dst, "mask", "MASK")
    print("  #%s: dest %s->%s(草稿) ; source %s->#%s ; mask %s->#%s 的 alpha"
          % (dst, o1, 8 if dst == 34 else 304, o2, nid, o3, nid))
    print("      合成参数 widgets_values = %s （未改：x/y/resize_source）" % byid[dst].get("widgets_values"))

left = [n["id"] for n in wf["nodes"] if n["type"] in ("SolidMask", "FeatherMask", "LoadImageOutput")]
print("残留矩形掩膜/LoadImageOutput 节点：%s" % (left or "无 ✔"))
assert not left
out_local = os.path.join(WFDIR, "_pending_alphamask.json")
io.open(out_local, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("nodes=%d links=%d" % (len(wf["nodes"]), len(wf["links"])))
if MODE == "dry":
    print("\n[dry] 未联网跑。"); sys.exit(0)

# ============ 4. 跑一组（脸部三张 + 全身三张成品）============
sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                       # noqa
API, _ = build_api(wf)
TARGETS = [nid for nid, x in API.items() if x["class_type"] == "SaveImage"
           and str(x["inputs"].get("filename_prefix", "")).endswith("成品")
           and ("闻灯-全身" in str(x["inputs"]["filename_prefix"]) or "闻灯-脸部" in str(x["inputs"]["filename_prefix"]))]
print("\n=== 目标 %s ===" % [API[t]["inputs"]["filename_prefix"] for t in TARGETS])
subg = {k: v for k, v in API.items() if k in deps(API, TARGETS)}
print("   裁剪后 %d 节点；采样器 %d 个" % (len(subg), sum(1 for v in subg.values() if v["class_type"] == "KSampler")))
res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 180).decode())
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:1800]); sys.exit(1)
pid = res["prompt_id"]; print("prompt_id=%s" % pid)
done = None
for i in range(600):
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
