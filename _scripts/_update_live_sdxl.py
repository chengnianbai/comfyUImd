# -*- coding: utf-8 -*-
"""线上工作流更新：组2 = SDXL 出终稿三张（正/左/右），组3 = Kontext 提供姿势与身份底稿

改动清单
--------
[字段级]
  1. 1004(LoadImage).image : wendeng_v23_face_base.png -> wendeng_face_base.png
     （后者 lapVar 234.82，与「闻灯-正脸-已确认_成品」降到 896 后逐位一致；前者只有 117.44）
  2. 组2 的 22 个节点 mode 2 -> 0（启用）
  3. 组2 分组标题补一句说明（组3 现为底稿来源）

[新增 12 个节点，只加不改，id 1100-1111]
  1100 ImageScale         image  <- 1035 (组3「主图·左侧脸 90°·成品」的 VAEDecode)   896x1152 center
  1101 VAEEncode          pixels <- 1100, vae <- 1002.VAE
  1102 CLIPTextEncode     侧面词（由组2 正向A 改写 front view -> side profile view）, clip <- 1003
  1103 ConditioningCombine 1102 + 1008(质感词)
  1104 KSampler           model<-1002  pos<-1103  neg<-1014  latent<-1101
                          seed 20260912 / 30步 / CFG10 / dpmpp_2m / karras / **denoise 0.45**
  1105 VAEDecode          samples <- 1104, vae <- 1002.VAE
  1106 SaveImage          闻灯-脸部左侧-草稿
  1107 ImageUpscaleWithModel  upscale_model <- 1018(4x-UltraSharp), image <- 1105
  1108 ImageScaleBy       lanczos 0.5, image <- 1107        （净 2x，与组2 正面同一套放大）
  1109 SaveImage          闻灯-脸部左侧-成品
  1110 ImageFlip          image <- 1108, y-axis: horizontally
  1111 SaveImage          闻灯-脸部右侧-成品

为什么这么接
------------
· 90° 姿势只有 Kontext 给得出；SDXL 任何 denoise 都会把 90° 拧回 3/4（三重实测），
  用户已确认接受 3/4，所以侧脸 = 「Kontext 出 90° -> SDXL d0.45 重绘」= P45 那条链。
· 身份：正脸走 1004 的正确基图（v23 已确认正脸）；侧脸的身份来自 Kontext 那张本身。
· 输出与组3 的 SaveImage 前缀不冲突（组3 是「闻灯主图-」「闻灯Kontext」，组2 是「闻灯-脸部」）。

用法：
    python _update_live_sdxl.py dry     # 本地构建 + 打印改动（不联网写）
    python _update_live_sdxl.py run     # 提交跑一次验证（不写工作流）
    python _update_live_sdxl.py push    # 写回线上（先备份 + 回读逐字节校验，失败自动还原）
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
OUTDIR = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "restructure")
WFNAME = "夜市百相簿-主工作流.json"
ENC = urllib.parse.quote(WFNAME, safe='')
MODE = sys.argv[1] if len(sys.argv) > 1 else "dry"
NEW_BASE_IMG = "wendeng_face_base.png"
G2 = [1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008, 1009, 1010, 1011, 1012, 1013, 1014,
      1015, 1016, 1017, 1018, 1019, 1020, 1021, 1022]


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


print("=== 1) 拉线上现行版并备份 ===")
wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
nodes = {n["id"]: n for n in wf["nodes"]}
EXISTING_IDS = [n["id"] for n in wf["nodes"]]        # ★ 必须在追加新节点之前抓取
EXISTING_LINKS = [l[0] for l in wf["links"]]
print("  id=%s nodes=%d links=%d last_node_id=%s" % (wf.get("id"), len(wf["nodes"]), len(wf["links"]), wf.get("last_node_id")))
ts = time.strftime("%Y%m%d_%H%M%S")
bpath = os.path.join(WFDIR, "_backup_pre_sdxl_restructure_%s.json" % ts)
io.open(bpath, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("  备份 -> %s" % os.path.basename(bpath))

changes = []

# ==================== 改动 1/2：字段级 ====================
old_img = (nodes[1004].get("widgets_values") or [None])[0]
nodes[1004]["widgets_values"][0] = NEW_BASE_IMG
changes.append("1004.image  %r -> %r" % (old_img, NEW_BASE_IMG))
en = [i for i in G2 if nodes[i].get("mode") != 0]
for i in en:
    nodes[i]["mode"] = 0
changes.append("启用组2 %d 个节点：%s" % (len(en), en))

# 侧面词 = 组2 正向A 改写视角
front_txt = nodes[1007]["widgets_values"][0]
SIDE_TXT = front_txt.replace("front view, looking at viewer",
                             "side profile view, face centered, true 90 degree side profile")

# ==================== 改动 3：新增节点（克隆同类型节点，保证结构完全合规）====================
TEMPLATE = {1100: 1005, 1101: 1006, 1102: 1007, 1103: 1009, 1104: 1015, 1105: 1016,
            1106: 1017, 1107: 1019, 1108: 1020, 1109: 1017, 1110: 1051, 1111: 1017}
TITLE = {
    1100: "① 拿组3 的 90° 侧脸当基图（缩到 896×1152）",
    1101: "① 身份/姿势 latent（P45 那条链的起点）",
    1102: "① 正向 A · 侧面视角词",
    1103: "① 正向 侧面（视角词 + 质感词）",
    1104: "② KSampler · SDXL d0.45（P45 档）",
    1105: "② VAEDecode",
    1106: "草稿 · 闻灯脸部左侧",
    1107: "3x 放大（4x-UltraSharp）",
    1108: "缩回 0.5（净 2x）",
    1109: "★ 成品 · 闻灯脸部左侧",
    1110: "右脸 = 左脸成品水平翻转（方向硬保证）",
    1111: "★ 成品 · 闻灯脸部右侧",
}
POS = {1100: (7500, 1200), 1101: (7500, 1320), 1102: (7090, 1450), 1103: (7500, 1560),
       1104: (7870, 1180), 1105: (7870, 1560), 1106: (8250, 1140), 1107: (8250, 1500),
       1108: (8250, 1620), 1109: (8640, 1120), 1110: (8640, 1500), 1111: (8640, 1780)}

new_ids = []
for nid, src in TEMPLATE.items():
    tpl = nodes[src]
    n = json.loads(json.dumps(tpl))
    n["id"] = nid
    n["title"] = TITLE[nid]
    n["pos"] = list(POS[nid])
    n["mode"] = 0
    n["flags"] = {}
    n["order"] = 50 + len(new_ids)
    for inp in (n.get("inputs") or []):
        inp["link"] = None
    for out in (n.get("outputs") or []):
        out["links"] = []
    # widgets
    if nid in (1100,):
        n["widgets_values"] = ["lanczos", 896, 1152, "center"]
    elif nid == 1102:
        n["widgets_values"] = [SIDE_TXT]
    elif nid == 1104:
        n["widgets_values"] = [20260912, "fixed", 30, 10, "dpmpp_2m", "karras", 0.45]
    elif nid == 1106:
        n["widgets_values"] = ["闻灯-脸部左侧-草稿"]
    elif nid == 1108:
        n["widgets_values"] = ["lanczos", 0.5]
    elif nid == 1109:
        n["widgets_values"] = ["闻灯-脸部左侧-成品"]
    elif nid == 1111:
        n["widgets_values"] = ["闻灯-脸部右侧-成品"]
    elif nid == 1110:
        n["widgets_values"] = ["y-axis: horizontally"]
    else:
        n["widgets_values"] = []
    wf["nodes"].append(n)
    nodes[nid] = n
    new_ids.append(nid)
changes.append("新增节点 %s" % new_ids)

# ==================== 连线 ====================
WIRES = [
    (1035, "IMAGE", 1100, "image"),
    (1100, "IMAGE", 1101, "pixels"),
    (1002, "VAE", 1101, "vae"),
    (1003, "CLIP", 1102, "clip"),
    (1102, "CONDITIONING", 1103, "conditioning_1"),
    (1008, "CONDITIONING", 1103, "conditioning_2"),
    (1002, "MODEL", 1104, "model"),
    (1103, "CONDITIONING", 1104, "positive"),
    (1014, "CONDITIONING", 1104, "negative"),
    (1101, "LATENT", 1104, "latent_image"),
    (1104, "LATENT", 1105, "samples"),
    (1002, "VAE", 1105, "vae"),
    (1105, "IMAGE", 1106, "images"),
    (1018, "UPSCALE_MODEL", 1107, "upscale_model"),
    (1105, "IMAGE", 1107, "image"),
    (1107, "IMAGE", 1108, "image"),
    (1108, "IMAGE", 1109, "images"),
    (1108, "IMAGE", 1110, "image"),
    (1110, "IMAGE", 1111, "images"),
]
TYPE = {"IMAGE": "IMAGE", "LATENT": "LATENT", "CONDITIONING": "CONDITIONING",
        "MODEL": "MODEL", "VAE": "VAE", "CLIP": "CLIP", "UPSCALE_MODEL": "UPSCALE_MODEL"}
# ★ 线上文件的 last_link_id / last_node_id 是过期计数器（实测 last_link_id=2318 但已存在 id=2319 的连线），
#   所以取号必须用「实际最大值」，否则会生出重复 id，把原连线挤掉（已踩过）。
_existing_links = EXISTING_LINKS
_existing_nodes = EXISTING_IDS
_dup = sorted({i for i in _existing_links if _existing_links.count(i) > 1})
print("  实际 max(link id)=%s  max(node id)=%s  已有重复 link id=%s"
      % (max(_existing_links), max(_existing_nodes), _dup or "无"))
if set(TEMPLATE) & set(_existing_nodes):
    print("★ 新节点 id 与现有节点冲突：%s" % (sorted(set(TEMPLATE) & set(_existing_nodes)))); sys.exit(1)
lid = max(_existing_links)
print("  新连线将从 id %d 开始" % (lid + 1))

added = []
for sid, sout, did, din in WIRES:
    sn, dn = nodes[sid], nodes[did]
    oslot = next((k for k, o in enumerate(sn.get("outputs") or []) if o.get("name") == sout), None)
    dslot = next((k for k, i in enumerate(dn.get("inputs") or []) if i.get("name") == din), None)
    if oslot is None or dslot is None:
        print("  ★ 连线失败 #%s.%s -> #%s.%s （槽位找不到: out=%s in=%s）" % (sid, sout, did, din, oslot, dslot))
        sys.exit(1)
    lid += 1
    wf["links"].append([lid, sid, oslot, did, dslot, TYPE[sout]])
    if dn["inputs"][dslot].get("links") is not None:
        pass
    dn["inputs"][dslot]["link"] = lid
    sn["outputs"][oslot].setdefault("links", [])
    if sn["outputs"][oslot]["links"] is None:
        sn["outputs"][oslot]["links"] = []
    sn["outputs"][oslot]["links"].append(lid)
    added.append(lid)
wf["last_link_id"] = lid
wf["last_node_id"] = max(_existing_nodes + new_ids)      # 顺手修正过期计数器
changes.append("新增连线 %d 条（link id %d -> %d）" % (len(added), lid - len(added) + 1, lid))
changes.append("修正过期计数器 last_node_id=%s last_link_id=%s" % (wf["last_node_id"], wf["last_link_id"]))

# 分组标题补注
for gr in wf.get("groups", []):
    if gr["id"] == 2:
        gr["title"] = "【闻灯】脸部 · SDXL img2img 出终稿（正/左/右 · 基图来自组3）"
        changes.append("组2 标题 -> %r" % gr["title"])

print("\n=== 2) 本次改动（只加不改，除字段与启用）===")
for c in changes:
    print("   · %s" % c)
print("   改动后 nodes=%d links=%d" % (len(wf["nodes"]), len(wf["links"])))

out_local = os.path.join(WFDIR, "_pending_sdxl_restructure.json")
io.open(out_local, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("   待推送版本已存 -> %s" % os.path.basename(out_local))

if MODE == "dry":
    print("\n[dry] 未联网写。"); sys.exit(0)

# ==================== run：用 UI->API 转换提交，只跑组2 四条输出 ====================
sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                     # noqa
API, TITLES = build_api(wf)
TARGETS = []
for nid, a in API.items():
    if a["class_type"] != "SaveImage":
        continue
    pfx = str(a["inputs"].get("filename_prefix", ""))
    if pfx.startswith("闻灯-脸部"):
        TARGETS.append(nid)
print("\n=== 3) 目标输出（组2）===")
for t in sorted(TARGETS, key=lambda x: int(x)):
    print("   #%s  %s  [%s]" % (t, API[t]["inputs"]["filename_prefix"], TITLES.get(t, "")))
keep = deps(API, TARGETS)
subg = {k: v for k, v in API.items() if k in keep}
print("   裁剪后 %d 节点；含采样器 %s"
      % (len(subg), sorted([k for k, v in subg.items() if v["class_type"] == "KSampler"], key=int)))

res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 180).decode())
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:2500]); sys.exit(1)
pid = res["prompt_id"]; print("\n=== 4) 提交验证 prompt_id = %s" % pid)
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
if done is None:
    print("★ 超时"); sys.exit(1)
os.makedirs(OUTDIR, exist_ok=True)
for nid, o in done.items():
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        p = os.path.join(OUTDIR, im["filename"])
        open(p, "wb").write(raw("/view?" + q, None, None, 300))
        print("   saved %-50s %7.1f KB" % (im["filename"], os.path.getsize(p) / 1024))

if MODE != "push":
    print("\n[run] 验证通过，未写工作流。要写线上请跑 push。"); sys.exit(0)

# ==================== push ====================
print("\n=== 5) 写回线上 ===")
try:
    raw("/api/userdata/workflows%2F" + ENC, io.open(out_local, encoding="utf-8").read().encode("utf-8"),
        "application/json", 300)
    print("   POST 完成")
except urllib.error.HTTPError as e:
    print("   ★ HTTP %s: %s" % (e.code, e.read().decode('utf-8', 'replace')[:300])); sys.exit(1)

print("\n=== 6) 回读校验 ===")
back = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
bn = {n["id"]: n for n in back["nodes"]}
ok = True
if (bn.get(1004, {}).get("widgets_values") or [None])[0] != NEW_BASE_IMG:
    print("   ✘ 1004.image 不对"); ok = False
miss = [i for i in new_ids if i not in bn]
if miss:
    print("   ✘ 缺节点 %s" % miss); ok = False
bad = [i for i in G2 if bn.get(i, {}).get("mode") != 0]
if bad:
    print("   ✘ 组2 未全启用: %s" % bad); ok = False
print("   回读 nodes=%d links=%d" % (len(back["nodes"]), len(back["links"])))
io.open(os.path.join(WFDIR, "_live_now.json"), "w", encoding="utf-8").write(json.dumps(back, ensure_ascii=False, indent=1))
if not ok:
    print("\n★ 校验不过，自动还原备份 ...")
    raw("/api/userdata/workflows%2F" + ENC, io.open(bpath, encoding="utf-8").read().encode("utf-8"),
        "application/json", 300)
    print("   已还原。"); sys.exit(1)
print("\n✔ 线上工作流已更新：组2 出终稿三张（正/左/右），组3 提供姿势与身份底稿")
