# -*- coding: utf-8 -*-
"""全身三视角：在组1（立绘块）里补上「侧面」「背面」，并按附录 B.7 撤掉第二段重绘

约束依据（角色生成约束-V1.0.md）
    §4.1/H06  全身要 正面+侧面+背面
    §5/H07    自然直立标准站姿（Neutral Standing / Arms Naturally at Sides）
    §6/H08    正常成年人比例，约 7~8 头身
    §7/H14    全身完整入镜（头顶到脚不得裁切）、居中、平视镜头、少透视变形
    §8.1      男性：上半身裸露 + 纯白短裤（无图案/无品牌/无配饰/无鞋袜）
    §10/H09   必须用已确认的脸做身份参考（本块做法：把脸贴到头顶）
    §12/H13   纯白背景    §13 影棚均匀柔光
    §17       禁止词表（动态姿势/畸形/裁切/广角畸变…）

设计（沿用正面块已定的做法，不另起一套）
    正面 = 复用现有节点（不动），只把第二段重绘撤掉（B.7：放大后直接存）
    侧面 = 与正面同构，但「贴的是左脸侧面成品」而不是正面脸
    背面 = 与正面同构，但**不贴脸**（背面看不到脸），且不做第二段重绘（没有接缝要融合）

★ 第二段重绘：现有正面块有 `KSampler② denoise 0.25`，而附录 B.7 裁决「第二段重绘=磨皮主犯，
  能撤就撤」。本脚本按 B.7 把三视角的第二段重绘都撤掉（放大→缩回0.5→直接存）。
  ⚠️ 若贴脸处出现可见接缝，需要单独加一次很低 denoise 的融合，见报告。

用法： python _build_fullbody.py dry | run | push
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
OUT = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "fullbody")
ENC = urllib.parse.quote("夜市百相簿-主工作流.json", safe='')
MODE = sys.argv[1] if len(sys.argv) > 1 else "dry"
FACE_FRONT = "闻灯-脸部正面-成品_00018_.png"
FACE_LEFT = "闻灯-脸部左侧-成品_00010_.png"
HEAD_W, HEAD_H = 200, 257          # 与现有正面块同一标定值（贴脸尺寸，待标定）


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
byid = {n["id"]: n for n in wf["nodes"]}
ALLIDS = {n["id"] for n in wf["nodes"]}
EXL = [l[0] for l in wf["links"]]
ts = time.strftime("%Y%m%d_%H%M%S")
host = urllib.parse.urlparse(BASE).netloc.split(".")[0]
bpath = os.path.join(WFDIR, "_backup_pre_fullbody_%s_%s.json" % (host, ts))
io.open(bpath, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("备份 -> %s" % os.path.basename(bpath))
print("现状 nodes=%d links=%d" % (len(wf["nodes"]), len(wf["links"])))

# 组1 现有节点
G1 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 30, 31, 32, 33, 34]
for i in G1:
    if i not in byid: print("★ 缺组1 节点 %s" % i); sys.exit(1)

T = {300: 2, 301: 4, 302: 6, 303: 7, 304: 8, 305: 10, 306: 30, 307: 31, 308: 32, 309: 33, 310: 34,
     311: 23, 312: 24, 313: 25, 314: 12, 315: 13, 316: 15,
     330: 2, 331: 4, 332: 6, 333: 7, 334: 8, 335: 10,
     341: 23, 342: 24, 343: 25, 344: 12, 345: 13, 346: 15}
TITLE = {
    300: "正向 A · 构图+人物+服装（全身侧面）", 301: "合并 A+B（侧面）", 302: "画布 832×1216（侧面）",
    303: "① 侧面 KSampler · 30步 CFG10 denoise1.0", 304: "VAEDecode（侧面草稿）",
    305: "存图 · 侧面草稿", 306: "★ 已确认的【左脸侧面】成品（output/ 直读）",
    307: "★ 脸缩到头部大小 200×257", 308: "贴图区域掩膜 200×257", 309: "羽化边缘",
    310: "★ 把侧面脸贴到全身草稿的头顶 x=316 y=6", 311: "4x 放大", 312: "缩回 0.5（净 2x）",
    313: "VAEEncode", 314: "② 融合（denoise 0.25）", 315: "VAEDecode（侧面成品）", 316: "★ 存图 · 侧面成品",
    330: "正向 A · 构图+人物+服装（全身背面）", 331: "合并 A+B（背面）", 332: "画布 832×1216（背面）",
    333: "① 背面 KSampler · 30步 CFG10 denoise1.0", 334: "VAEDecode（背面草稿）", 335: "存图 · 背面草稿",
    341: "4x 放大（背面）", 342: "缩回 0.5（背面）", 343: "VAEEncode（背面）",
    344: "② 融合（背面 · denoise 0.25）", 345: "VAEDecode（背面成品）", 346: "★ 存图 · 背面成品",
}
POSA = {
    300: ("side view, full body shot, head to toe, full length, standing straight, arms naturally at sides, "
          "side profile, centered composition, 1boy, solo, 24 year old east asian man, masculine face, strong jaw, "
          "messy wavy black hair, small mole at outer eye corner, bare upper body, plain white shorts, pure white background"),
    330: ("back view, seen from behind, full body shot, head to toe, full length, standing straight, arms naturally at sides, "
          "centered composition, 1boy, solo, 24 year old east asian man, messy wavy black hair, bare upper body, "
          "back muscles, plain white shorts, pure white background"),
}
POS = {310: (316, 6, True)}
NEW = sorted(T)

# ---- 第二段重绘：按 B.7 撤掉 ----
# 正面：15(成品存图)/14(预览) 从 13(第二段VAEDecode) 改接 24(净2x)，并把 12/25/13 置禁用
# 侧面/背面：新块直接不建第二段，成品存图接 312/342（净2x）
byid[15]["widgets_values"] = ["闻灯-全身正面-成品"]
changes = ["正面：15/14 的输入由第二段(13) 改接净2x(24)，12/25/13 置禁用（B.7）"]

lid = max(EXL)


def mk(nid):
    tpl = json.loads(json.dumps(byid[T[nid]]))
    tpl["id"] = nid; tpl["title"] = TITLE[nid]; tpl["mode"] = 0; tpl["flags"] = {}
    for i in (tpl.get("inputs") or []): i["link"] = None
    for o in (tpl.get("outputs") or []): o["links"] = []
    if nid in POSA: tpl["widgets_values"] = [POSA[nid]]
    return tpl


for nid in NEW:
    if nid in ALLIDS: print("★ id %s 冲突" % nid); sys.exit(1)
    n = mk(nid)
    # 位置：侧面排右侧一列，背面再右一列
    col = 0 if nid < 330 else 1
    n["pos"] = [5064 + (530 if nid >= 300 and nid < 400 else 0) * 0, 0]   # 占位，稍后统一排
    wf["nodes"].append(n); byid[nid] = n

# 统一布局：侧面一区、背面一区，各用 2 列网格
COLS = {300: 5064, 330: 6400}
for nid in NEW:
    base = 300 if nid < 330 else 330
    off = nid - base
    px = COLS[base] + (off % 2) * 430
    py = 2560 + (off // 2) * 310
    byid[nid]["pos"] = [px, py]
changes.append("新增节点 %d 个：侧面 %s / 背面 %s" % (len(NEW), [i for i in NEW if i < 330], [i for i in NEW if i >= 330]))

# ---- 连线 ----
def wire(sid, sout, did, din, stype):
    global lid
    sn, dn = byid[sid], byid[did]
    oslot = next((k for k, o in enumerate(sn.get("outputs") or []) if o.get("name") == sout), None)
    dslot = next((k for k, x in enumerate(dn.get("inputs") or []) if x.get("name") == din), None)
    if oslot is None or dslot is None:
        print("★ 连线失败 #%s.%s -> #%s.%s (out=%s in=%s)" % (sid, sout, did, din, oslot, dslot)); sys.exit(1)
    lid += 1
    wf["links"].append([lid, sid, oslot, did, dslot, stype])
    dn["inputs"][dslot]["link"] = lid
    sn["outputs"][oslot].setdefault("links", [])
    if sn["outputs"][oslot]["links"] is None: sn["outputs"][oslot]["links"] = []
    sn["outputs"][oslot]["links"].append(lid)


def unlink(dst, slot):
    d = byid[dst]
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
    return l[1]

# 正面撤第二段
for did, sl in ((15, "images"), (14, "images")):
    o = unlink(did, sl)
    wire(24, "IMAGE", did, sl, "IMAGE")
    changes.append("  #%s.%s : %s -> 24" % (did, sl, o))
for i in (12, 25, 13): byid[i]["mode"] = 2
# ★ 组1 整体启用（只留上面三个按 B.7 撤掉的第二段重绘节点禁用）
#   否则共享节点（1 底模 / 17 clipskip / 3 正向B / 21 负向 / 22 放大模型…）会被"禁用即跳过"排除，
#   新支路引用它们就会报 KeyError: '1'
for i in G1:
    if i not in (12, 25, 13):
        byid[i]["mode"] = 0
changes.append("启用组1 节点（除 12/25/13 外）")

W = [
    # 侧面
    (17, "CLIP", 300, "clip", "CLIP"),
    (17, "CLIP", 330, "clip", "CLIP"),
    (300, "CONDITIONING", 301, "conditioning_1", "CONDITIONING"),
    (3, "CONDITIONING", 301, "conditioning_2", "CONDITIONING"),
    (302, "LATENT", 303, "latent_image", "LATENT"),
    (1, "MODEL", 303, "model", "MODEL"),
    (301, "CONDITIONING", 303, "positive", "CONDITIONING"),
    (21, "CONDITIONING", 303, "negative", "CONDITIONING"),
    (303, "LATENT", 304, "samples", "LATENT"),
    (1, "VAE", 304, "vae", "VAE"),
    (304, "IMAGE", 305, "images", "IMAGE"),
    (306, "IMAGE", 307, "image", "IMAGE"),
    (308, "MASK", 309, "mask", "MASK"),
    (304, "IMAGE", 310, "destination", "IMAGE"),
    (307, "IMAGE", 310, "source", "IMAGE"),
    (309, "MASK", 310, "mask", "MASK"),
    (22, "UPSCALE_MODEL", 311, "upscale_model", "UPSCALE_MODEL"),
    (310, "IMAGE", 311, "image", "IMAGE"),
    (311, "IMAGE", 312, "image", "IMAGE"),
    (312, "IMAGE", 313, "pixels", "IMAGE"),
    (1, "VAE", 313, "vae", "VAE"),
    (313, "LATENT", 314, "latent_image", "LATENT"),
    (1, "MODEL", 314, "model", "MODEL"),
    (301, "CONDITIONING", 314, "positive", "CONDITIONING"),
    (21, "CONDITIONING", 314, "negative", "CONDITIONING"),
    (314, "LATENT", 315, "samples", "LATENT"),
    (1, "VAE", 315, "vae", "VAE"),
    (315, "IMAGE", 316, "images", "IMAGE"),
    # 背面（不贴脸）
    (330, "CONDITIONING", 331, "conditioning_1", "CONDITIONING"),
    (3, "CONDITIONING", 331, "conditioning_2", "CONDITIONING"),
    (332, "LATENT", 333, "latent_image", "LATENT"),
    (1, "MODEL", 333, "model", "MODEL"),
    (331, "CONDITIONING", 333, "positive", "CONDITIONING"),
    (21, "CONDITIONING", 333, "negative", "CONDITIONING"),
    (333, "LATENT", 334, "samples", "LATENT"),
    (1, "VAE", 334, "vae", "VAE"),
    (334, "IMAGE", 335, "images", "IMAGE"),
    (22, "UPSCALE_MODEL", 341, "upscale_model", "UPSCALE_MODEL"),
    (334, "IMAGE", 341, "image", "IMAGE"),
    (341, "IMAGE", 342, "image", "IMAGE"),
    (342, "IMAGE", 343, "pixels", "IMAGE"),
    (1, "VAE", 343, "vae", "VAE"),
    (343, "LATENT", 344, "latent_image", "LATENT"),
    (1, "MODEL", 344, "model", "MODEL"),
    (331, "CONDITIONING", 344, "positive", "CONDITIONING"),
    (21, "CONDITIONING", 344, "negative", "CONDITIONING"),
    (344, "LATENT", 345, "samples", "LATENT"),
    (1, "VAE", 345, "vae", "VAE"),
    (345, "IMAGE", 346, "images", "IMAGE"),
]
for sid, sout, did, din, st in W:
    wire(sid, sout, did, din, st)
changes.append("新增连线 %d 条" % len(W))
wf["last_link_id"] = lid
wf["last_node_id"] = max(ALLIDS | set(NEW))

# 关键 widget
byid[306]["widgets_values"] = [FACE_LEFT + " [output]", False, "refresh", "image"]
byid[305]["widgets_values"] = ["闻灯-全身侧面-草稿"]
byid[316]["widgets_values"] = ["闻灯-全身侧面-成品"]
byid[335]["widgets_values"] = ["闻灯-全身背面-草稿"]
byid[346]["widgets_values"] = ["闻灯-全身背面-成品"]
byid[307]["widgets_values"] = ["lanczos", HEAD_W, HEAD_H, "center"]
byid[308]["widgets_values"] = [1, HEAD_W, HEAD_H]
byid[310]["widgets_values"] = [POS[310][0], POS[310][1], False]
# ★ 修正现有正面块的同类 bug：resize_source=true 会把 200x257 的脸放大到整幅画布再贴
if (byid[34].get("widgets_values") or [None, None, None])[2] is not False:
    byid[34]["widgets_values"] = [316, 6, False]
    changes.append("修正 #34 ImageCompositeMasked resize_source true -> false（原会把脸放大到整幅）")
byid[312]["widgets_values"] = ["lanczos", 0.5]
byid[342]["widgets_values"] = ["lanczos", 0.5]
byid[30]["widgets_values"] = [FACE_FRONT + " [output]", False, "refresh", "image"]
# 三视角同 seed / 同参数
for kid in (303, 333):
    byid[kid]["widgets_values"] = [20260916, "fixed", 30, 10, "dpmpp_2m", "karras", 1]

# 组1 标题与包围盒（按组1 全部节点重算，含新增）
g1 = next(g for g in wf["groups"] if g["id"] == 1)
g1["title"] = "【闻灯】全身立绘 · SDXL 保身份（正/侧/背 三视角）"
g1nodes = [n for n in wf["nodes"] if n["id"] < 1000]
bx0 = min(n["pos"][0] for n in g1nodes); by0 = min(n["pos"][1] for n in g1nodes)
bx1 = max(n["pos"][0] + (n.get("size") or (300, 100))[0] for n in g1nodes)
by1 = max(n["pos"][1] + (n.get("size") or (300, 100))[1] for n in g1nodes)
old_box = list(g1["bounding"])
g1["bounding"] = [bx0 - 40, by0 - 40, (bx1 - bx0) + 120, (by1 - by0) + 120]
changes.append("组1 包围盒 %s -> %s" % ([round(v) for v in old_box], [round(v) for v in g1["bounding"]]))
# 与组2 的框是否重叠（组2 在 x7660 起，y340-6380）
g2 = next(g for g in wf["groups"] if g["id"] == 2)
ax, ay, aw, ah = g1["bounding"]; cx, cy, cw, ch = g2["bounding"]
ovx = max(0, min(ax+aw, cx+cw) - max(ax, cx)); ovy = max(0, min(ay+ah, cy+ch) - max(ay, cy))
changes.append("与组2 的重叠：x %.0f y %.0f %s" % (ovx, ovy, "✔ 不重叠" if ovx*ovy == 0 else "★ 重叠"))
print("\n=== 本次改动 ===")
for c in changes: print("   · %s" % c)
print("   nodes=%d links=%d" % (len(wf["nodes"]), len(wf["links"])))

out_local = os.path.join(WFDIR, "_pending_fullbody.json")
io.open(out_local, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("待推送版本 -> %s" % os.path.basename(out_local))
if MODE == "dry":
    print("\n[dry] 未联网写。"); sys.exit(0)

# ---- 跑：先只跑草稿三条 ----
sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                       # noqa
API, TITLES = build_api(wf)
TARGETS = [nid for nid, a in API.items()
           if a["class_type"] == "SaveImage" and str(a["inputs"].get("filename_prefix", "")).startswith("闻灯-全身")]
print("\n=== 目标输出（含草稿与成品）===")
for t in sorted(TARGETS, key=lambda x: int(x)):
    print("   #%-5s %s" % (t, API[t]["inputs"]["filename_prefix"]))
subg = {k: v for k, v in API.items() if k in deps(API, TARGETS)}
print("   裁剪后 %d 节点；采样器 %s" % (len(subg),
      sorted([k for k, v in subg.items() if v["class_type"] == "KSampler"], key=int)))
try:
    res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                         "application/json", 180).decode())
except urllib.error.HTTPError as e:
    print("★ 提交被拒 HTTP %s" % e.code)
    print(e.read().decode('utf-8', 'replace')[:3000])
    sys.exit(1)
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:2000]); sys.exit(1)
pid = res["prompt_id"]; print("\n提交 prompt_id=%s" % pid)
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
        done = h[pid].get("outputs", {}); print("完成，约 %d 秒" % ((i + 1) * 4)); break
if done is None: print("★ 超时"); sys.exit(1)
os.makedirs(OUT, exist_ok=True)
for nid, o in done.items():
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        p = os.path.join(OUT, im["filename"]); open(p, "wb").write(raw("/view?" + q, None, None, 300))
        print("   saved %-46s %7.1f KB" % (im["filename"], os.path.getsize(p) / 1024))
print("\n产物 -> %s" % OUT)

if MODE != "push":
    print("\n[run] 未写工作流。"); sys.exit(0)
print("\n=== 写回线上 ===")
raw("/api/userdata/workflows%2F" + ENC, io.open(out_local, encoding="utf-8").read().encode("utf-8"), "application/json", 300)
back = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
bb = {n["id"]: n for n in back["nodes"]}
missing = [i for i in NEW if i not in bb]
print("   回读：新节点缺 %s；15 来源=%s；nodes=%d links=%d" % (
    missing or "无 ✔",
    next((l[1] for l in back["links"] if l[3] == 15 and l[4] == 0), None),
    len(back["nodes"]), len(back["links"])))
