# -*- coding: utf-8 -*-
"""v3：走 A（提高分辨率）+ 用户的三资产架构

用户方案（2026-10-08）
  阶段一  Flux 高分辨率直接生成全身母版（1024x1792），ReferenceLatent 锁身份 + Prompt 锁男模身材
  阶段二  不把全身图直接当"高清脸母版"；从全身图里**定位脸 → 裁出 → 高分辨率脸部精修**
          ★ 不是抠脸贴回，而是**以全身图里那张脸为基础重新精修** → 独立产出 C 资产
  三资产 A. Face Master（已确认脸，最高身份质量）
         B. Full Body Master（1024x1792 起，身体+服装+整体）
         C. Face Detail Master（从 B 的脸精修出来，证明近看仍是这个人）

本次改动
  ① 删除旧 SDXL 文生图全身支路（6/7/8/9/10/302/303/304/305/332/333/334/335）
  ② 撤掉"在全身图上做的 SDXL 收尾"（25/12/13/313/314/315/343/344/345 置禁用且不可达）
     —— 它在 768x1344 的小脸上重绘，既是脸变了的元凶，又把 1024x1792 的收益丢掉
  ③ Flux 阶段分辨率 768x1344 → 1024x1792；参考画布同步改为 1024x1792（头 238px = 7.5 头身）
  ④ 新增资产 C 分支：从全身母版裁脸 → 放大 → 1024x1024 → SDXL img2img 精修 → 独立存图
     （脸在该图里约 612px 宽，是原全身图 100px 的 6 倍，SDXL 终于有像素可用）

用法： python _refgen_v3.py dry | run
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
OUT = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "refgen3")
WFNAME = "夜市百相簿-主工作流.json"
ENC = urllib.parse.quote(WFNAME, safe='')
MODE = sys.argv[1] if len(sys.argv) > 1 else "dry"
OLD_T2I = [6, 7, 8, 9, 10, 302, 303, 304, 305, 332, 333, 334, 335]
OLD_PASS = [25, 12, 13, 313, 314, 315, 343, 344, 345]
W, H = 1024, 1792
HEAD_FRAC = 1/7.5
FACE_SRC = {"front": 1317}
os.makedirs(OUT, exist_ok=True)


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


# ---------- 0. 重做 1024x1792 的参考画布（头按 7.5 头身摆）并上传 ----------
hist = json.loads(raw("/history").decode('utf-8', 'replace'))
best = {}
for pid, rec in hist.items():
    for nid, o in (rec.get("outputs") or {}).items():
        for im in o.get("images", []):
            fn = im.get("filename", "")
            for key, pref in (("front", "闻灯-脸部正面-成品"), ("left", "闻灯-脸部左侧-成品"),
                              ("right", "闻灯-脸部右侧-成品")):
                if fn.startswith(pref):
                    n = int(''.join(ch for ch in fn[len(pref):] if ch.isdigit()) or 0)
                    if key not in best or n > best[key][0]: best[key] = (n, fn)
print("=== 参考来源（已确认脸）===")
for k in ("front", "left", "right"):
    if k not in best: print("★ 缺 %s" % k); sys.exit(1)
    print("  %-6s %s" % (k, best[k][1]))
IDFILE = {}
hh = int(H * HEAD_FRAC); top = int(H * 0.04)
for k, (n, fn) in best.items():
    q = urllib.parse.urlencode({"filename": fn, "subfolder": "", "type": "output"})
    p = os.path.join(OUT, "_src_" + fn); open(p, "wb").write(raw("/view?" + q))
    im = Image.open(p).convert("RGB"); Wd, Hd = im.size
    c = im.crop((int(Wd*0.14), 0, int(Wd*0.90), int(Hd*0.62)))     # 纯头部，切掉肩线
    nw = int(c.size[0] * hh / c.size[1])
    cv = Image.new("RGB", (W, H), (255, 255, 255))
    cv.paste(c.resize((nw, hh), Image.LANCZOS), ((W - nw)//2, top))
    outn = "wendeng_id_%s.png" % k
    cv.save(os.path.join(OUT, outn)); IDFILE[k] = outn
    a = np.asarray(cv).astype(np.int16)
    blue = ((a[:, :, 2] - a[:, :, 0]) > 18).mean()
    print("  %-6s → 参考画布 %dx%d（头 %dx%d @ y=%d，占图高 %.1f%%；蓝像素 %.2f%%）"
          % (k, W, H, nw, hh, top, 100*hh/H, 100*blue))
    body = io.open(os.path.join(OUT, outn), "rb").read()
    B = "----cmdc" + uuid.uuid4().hex
    part = (("--%s\r\nContent-Disposition: form-data; name=\"image\"; filename=\"%s\"\r\n"
             "Content-Type: image/png\r\n\r\n" % (B, outn)).encode() + body +
            ("\r\n--%s\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n--%s--\r\n"
             % (B, B)).encode())
    okup = False
    for t in range(5):
        try:
            raw("/upload/image", part, "multipart/form-data; boundary=" + B, 300)
            okup = True; break
        except Exception as e:
            print("         上传第 %d 次失败 %s，重试" % (t+1, type(e).__name__)); time.sleep(5)
    if not okup:
        print("★ %s 上传失败" % outn); sys.exit(1)
print("  已上传 3 张参考画布（%dx%d）" % (W, H))

# ---------- 1. 改工作流 ----------
wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
byid = {n["id"]: n for n in wf["nodes"]}
host = urllib.parse.urlparse(BASE).netloc.split(".")[0]
bp = os.path.join(WFDIR, "_backup_pre_refgen3_%s_%s.json" % (host, time.strftime("%Y%m%d_%H%M%S")))
io.open(bp, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("\n线上 nodes=%d links=%d ；备份 %s" % (len(wf["nodes"]), len(wf["links"]), os.path.basename(bp)))
lid = max(l[0] for l in wf["links"])


def unlink(dst, slot):
    d = byid.get(dst)
    if not d: return None
    k = next((i for i, x in enumerate(d.get("inputs") or []) if x.get("name") == slot), None)
    if k is None: return None
    old = d["inputs"][k].get("link"); d["inputs"][k]["link"] = None
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


def clone(nid, tpl, pos, title, widgets=None, newtype=None):
    n = json.loads(json.dumps(byid[tpl])); n["id"] = nid
    if newtype: n["type"] = newtype
    n["title"] = title; n["mode"] = 0; n["order"] = 900 + nid
    for i in (n.get("inputs") or []): i["link"] = None
    for o in (n.get("outputs") or []): o["links"] = []
    if widgets is not None: n["widgets_values"] = widgets
    n["pos"] = pos
    wf["nodes"].append(n); byid[nid] = n
    return n


# ① 删旧 SDXL 文生图支路
have = [i for i in OLD_T2I if i in byid]
gone = [l for l in wf["links"] if l[1] in have or l[3] in have]
wf["links"] = [l for l in wf["links"] if l[1] not in have and l[3] not in have]
gid = {l[0] for l in gone}
for n in wf["nodes"]:
    for o in (n.get("outputs") or []):
        if o.get("links"): o["links"] = [x for x in o["links"] if x not in gid]
wf["nodes"] = [n for n in wf["nodes"] if n["id"] not in have]
print("① 删除旧 SDXL 文生图支路：%s（%d 条连线）" % (have, len(gone)))

# ② 撤掉全身图上的 SDXL 收尾，全身直接接 Flux 输出
for i in OLD_PASS:
    if i in byid: byid[i]["mode"] = 2
for up, dec in ((23, 1317), (311, 1337), (341, 1357)):
    o = unlink(up, "image"); wire(dec, "IMAGE", up, "image", "IMAGE")
    print("② #%s(放大).image %s -> #%s（Flux 原始输出，不再经过小脸重绘）" % (up, o, dec))
print("   全身 SDXL 收尾 %s 已禁用且不可达" % [i for i in OLD_PASS if i in byid])

# ③ 分辨率 1024x1792
wv = list(byid[1302]["widgets_values"]); wv[0], wv[1] = W, H
byid[1302]["widgets_values"] = wv
print("③ #1302 空潜空间 -> %s" % byid[1302]["widgets_values"])

# ④ 资产 C：从全身母版裁脸 → 放大 → 1024x1024 → SDXL 精修
#    摆放依据：全身 7.5 头身 ⇒ 头高 = H/7.5 = %d，头顶 y ≈ %.0f；裁头+颈+肩，左右居中
CY0, CH = int(H*0.017), int(H*0.235)
CW = int(W*0.47); CX0 = (W - CW)//2
clone(1360, 1005, [21400, 400], "★ C1 裁脸（从全身母版）", [CW, CH, CX0, CY0], newtype="ImageCrop")
clone(1361, 24, [21400, 700], "C2 放大 4x（lanczos）", ["lanczos", 4.0])
clone(1362, 1005, [21400, 1000], "C3 归一到 1024x1024", ["lanczos", 1024, 1024, "center"])
clone(1363, 25, [21400, 1300], "C4 VAEEncode（SDXL）")
clone(1364, 1008, [21800, 400], "C5 正向（脸部细节词）")
clone(1365, 1012, [21800, 1000], "C6 负向")
clone(1366, 1015, [21800, 1400], "★ C7 SDXL img2img 精修 1024x1024 denoise 0.45",
      [20260912, "fixed", 30, 7.5, "dpmpp_2m", "karras", 0.45])
clone(1367, 1016, [21800, 1900], "C8 VAEDecode")
clone(1368, 1021, [22200, 1400], "★ 资产C · 脸部精修", ["闻灯-全身正面-脸部精修-成品"], newtype="SaveImage")
wire(1317, "IMAGE", 1360, "image", "IMAGE")
wire(1360, "IMAGE", 1361, "image", "IMAGE")
wire(1361, "IMAGE", 1362, "image", "IMAGE")
wire(1362, "IMAGE", 1363, "pixels", "IMAGE")
wire(1002, "VAE", 1363, "vae", "VAE")
wire(1003, "CLIP", 1364, "clip", "CLIP")
wire(1003, "CLIP", 1365, "clip", "CLIP")
wire(1364, "CONDITIONING", 1366, "positive", "CONDITIONING")
wire(1365, "CONDITIONING", 1366, "negative", "CONDITIONING")
wire(1002, "MODEL", 1366, "model", "MODEL")
wire(1363, "LATENT", 1366, "latent_image", "LATENT")
wire(1366, "LATENT", 1367, "samples", "LATENT")
wire(1002, "VAE", 1367, "vae", "VAE")
wire(1367, "IMAGE", 1368, "images", "IMAGE")
print("④ 资产C 分支：裁 %dx%d @ (%d,%d) → 4x → 1024x1024 → SDXL img2img d0.45 → %s"
      % (CW, CH, CX0, CY0, "闻灯-全身正面-脸部精修-成品"))
print("   注：#1364/#1365 沿用脸部组正向/负向；#1317 是 Flux 正面输出的那一张")

print("\nnodes=%d links=%d" % (len(wf["nodes"]), len(wf["links"])))
out_local = os.path.join(WFDIR, "_pending_refgen3.json")
io.open(out_local, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
if MODE == "dry":
    print("\n[dry] 未联网跑。"); sys.exit(0)

# ---------- 跑：3 全身成品 + 1 脸部精修 ----------
sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                       # noqa
API, _ = build_api(wf)
TARGETS = [nid for nid, x in API.items() if x["class_type"] == "SaveImage"
           and (str(x["inputs"].get("filename_prefix", "")).startswith("闻灯-全身")
                and str(x["inputs"].get("filename_prefix", "")).endswith("成品")
                or str(x["inputs"].get("filename_prefix", "")) == "闻灯-全身正面-脸部精修-成品")]
print("\n=== 目标 %s ===" % [API[t]["inputs"]["filename_prefix"] for t in TARGETS])
subg = {k: v for k, v in API.items() if k in deps(API, TARGETS)}
print("   裁剪后 %d 节点；KSampler %s" % (len(subg),
      sorted([k for k, v in subg.items() if v["class_type"] == "KSampler"], key=int)))
res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 180).decode())
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:2000]); sys.exit(1)
pid = res["prompt_id"]; print("prompt_id=%s" % pid)
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
        done = h[pid].get("outputs", {}); print("完成，约 %d 秒" % ((i+1)*4)); break
if done is None: print("★ 超时"); sys.exit(1)
for nid, o in done.items():
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        p = os.path.join(OUT, im["filename"]); open(p, "wb").write(raw("/view?" + q, None, None, 300))
        print("   saved %-46s %7.1f KB" % (im["filename"], os.path.getsize(p)/1024))

# ---------- 写回 ----------
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
print("✔ 已写回" if ok else "★ 写回失败")
