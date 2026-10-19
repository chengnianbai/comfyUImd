# -*- coding: utf-8 -*-
"""线上更新 4：只保留一个基图 —— Kontext 链的身份参考改用「SDXL 正脸成品」

改动
----
· 1028(FluxKontextImageScale).image : ['1027',0] -> ['1021',0]
    即 Kontext 链不再读 00009，改读 **SDXL 正脸成品**（1021）——
    于是「SDXL 出的正脸」就是全链唯一的身份来源，Kontint 那条 90° 侧脸也从它派生。
· 删除 1027 LoadImage(wendeng_face_confirmed_00009.png)；它的连线一并删
    => 全工作流的**外部输入只剩一个**：1004 读的 `wendeng_face_base.png`
· 更新说明 Note（1001 / 1023）

★ 对照实测（_exp_0924/anchor_front/，两版都已出图）
   锚=00009（旧）   左脸 lapVar 144.03  头发-脸偏移 +0.182
   锚=SDXL正脸（新） 左脸 lapVar 199.30  头发-脸偏移 +0.226
   正脸两版逐字节相同（正脸支路不依赖 1027）
★ 但你们 09-22 实测过「锚=干净正脸 → 干净但只转 ~3/4」，所以两版图都留着了，
  以你的眼为准；不满意一条命令就能还原（备份在 _wf/_backup_pre_onebase_*.json）。

用法： python _update_live_onebase.py dry | run | push
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
OUTDIR = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "onebase")
WFNAME = "夜市百相簿-主工作流.json"
ENC = urllib.parse.quote(WFNAME, safe='')
MODE = sys.argv[1] if len(sys.argv) > 1 else "dry"
DELETE = [1027]

NOTE_1023_TAIL = (
    "★ 全链唯一的基图 = 1004 读的 `wendeng_face_base.png`（v23 认可的那张 SDXL 正脸）。\n"
    "  1028 现在直接取 **SDXL 正脸成品 1021** 当身份参考（原来取 00009，那张 lapVar 只有\n"
    "  106.92、是文档里定性为「病根」的旧稿，已删除该 LoadImage）。\n"
    "  => 外部只需要上传一个文件，其余全部由 SDXL 衍生。\n"
)


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


print("=== 1) 拉线上现行版并备份 ===")
wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
ts = time.strftime("%Y%m%d_%H%M%S")
bpath = os.path.join(WFDIR, "_backup_pre_onebase_%s.json" % ts)
io.open(bpath, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("  nodes=%d links=%d  备份 -> %s" % (len(wf["nodes"]), len(wf["links"]), os.path.basename(bpath)))

byid = {n["id"]: n for n in wf["nodes"]}
n1028 = byid[1028]
old = [l for l in wf["links"] if l[3] == 1028 and l[4] == 0]
print("  1028.image 当前来源 = %s" % (old[0][1:3] if old else None))

changes = []
# ---- 1) 删掉 1027（含其连线）----
gone = [l for l in wf["links"] if l[1] in DELETE or l[3] in DELETE]
wf["links"] = [l for l in wf["links"] if not (l[1] in DELETE or l[3] in DELETE)]
gid = {l[0] for l in gone}
for n in wf["nodes"]:
    for o in (n.get("outputs") or []):
        if o.get("links"):
            o["links"] = [x for x in o["links"] if x not in gid]
wf["nodes"] = [n for n in wf["nodes"] if n["id"] not in DELETE]
changes.append("删除 1027 LoadImage(wendeng_face_confirmed_00009.png) 及 %d 条连线" % len(gone))

# ---- 2) 1028 改接 1021 ----
EX = [l[0] for l in wf["links"]]
lid = max(EX)
src = byid[1020]
oslot = next(k for k, o in enumerate(src["outputs"]) if o.get("name") == "IMAGE")
# 先把 1028.image 原来的连线从源头摘掉
for l in old:
    s = byid.get(l[1])
    if s:
        for o in (s.get("outputs") or []):
            if o.get("links"):
                o["links"] = [x for x in o["links"] if x != l[0]]
wf["links"] = [l for l in wf["links"] if l[0] not in {l0[0] for l0 in old}]
lid += 1
wf["links"].append([lid, 1020, oslot, 1028, 0, "IMAGE"])
n1028["inputs"][0]["link"] = lid
src["outputs"][oslot].setdefault("links", [])
if src["outputs"][oslot]["links"] is None:
    src["outputs"][oslot]["links"] = []
src["outputs"][oslot]["links"].append(lid)
changes.append("1028.image  ['1027',0] -> ['1020',0]（1020 = SDXL 正脸成品的像素）")

# ---- 3) 说明文字 ----
n1023 = byid[1023]
txt = (n1023.get("widgets_values") or [""])[0]
if "全链唯一的基图" not in txt:
    n1023["widgets_values"] = [txt + "\n" + NOTE_1023_TAIL]
    changes.append("更新说明 Note #1023")

wf["last_link_id"] = max(l[0] for l in wf["links"])
print("\n=== 2) 本次改动 ===")
for c in changes:
    print("   · %s" % c)
print("   nodes=%d links=%d" % (len(wf["nodes"]), len(wf["links"])))

# ---- 自检：没有任何连线还指向已删节点；1028 只有一个来源 ----
bad = [l for l in wf["links"] if (l[1] in DELETE) or (l[3] in DELETE)]
srcs = [l for l in wf["links"] if l[3] == 1028 and l[4] == 0]
print("   指向已删节点的连线：%s" % (bad or "无 ✔"))
print("   1028.image 的来源：%s %s" % (srcs, "✔ 唯一" if len(srcs) == 1 else "★ 异常"))
if bad or len(srcs) != 1:
    print("★ 自检不过"); sys.exit(1)

out_local = os.path.join(WFDIR, "_pending_onebase.json")
io.open(out_local, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
if MODE == "dry":
    print("\n[dry] 未联网写。"); sys.exit(0)

# ---- 跑一次验证 ----
sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                       # noqa
API, TITLES = build_api(wf)
TARGETS = [nid for nid, a in API.items()
           if a["class_type"] == "SaveImage" and "脸部" in str(a["inputs"].get("filename_prefix", ""))]
subg = {k: v for k, v in API.items() if k in deps(API, TARGETS)}
print("\n=== 3) 目标输出 %s ===" % [API[t]["inputs"]["filename_prefix"] for t in TARGETS])
print("   裁剪后 %d 节点；1028 来源 = %s；1027 在图内？%s"
      % (len(subg), subg["1028"]["inputs"]["image"], "1027" in subg))
res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 180).decode())
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:2000]); sys.exit(1)
pid = res["prompt_id"]; print("   prompt_id=%s" % pid)
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
        print("   saved %-52s %7.1f KB" % (im["filename"], os.path.getsize(p) / 1024))

if MODE != "push":
    print("\n[run] 验证通过，未写工作流。"); sys.exit(0)

print("\n=== 4) 写回线上 ===")
raw("/api/userdata/workflows%2F" + ENC, io.open(out_local, encoding="utf-8").read().encode("utf-8"),
    "application/json", 300)
back = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
bb = {n["id"]: n for n in back["nodes"]}
ok = (1027 not in bb) and any(l[3] == 1028 and l[4] == 0 and l[1] == 1020 for l in back["links"])
print("   回读：1027 已删除 %s；1028 来源=1020 %s；nodes=%d links=%d"
      % (1027 not in bb, ok, len(back["nodes"]), len(back["links"])))
io.open(os.path.join(WFDIR, "_live_now.json"), "w", encoding="utf-8").write(json.dumps(back, ensure_ascii=False, indent=1))
if not ok:
    print("★ 校验不过，自动还原 ...")
    raw("/api/userdata/workflows%2F" + ENC, io.open(bpath, encoding="utf-8").read().encode("utf-8"),
        "application/json", 300)
    print("   已还原。"); sys.exit(1)
print("\n✔ 已只剩一个基图（wendeng_face_base.png），Kontext 链改读 SDXL 正脸成品")
