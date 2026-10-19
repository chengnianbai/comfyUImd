# -*- coding: utf-8 -*-
"""线上工作流更新 3：重排【闻灯】脸部 · SDXL 出终稿 + Kontext 底稿 组的节点布局

布局原则
--------
· 按「数据流从左到右」排成网格：Kontext 底稿在上两条带，SDXL 终稿在下两条带。
· 网格单元 800×520（最大节点 CLIPTextEncode 760×420、SaveImage 500×460 都装得下），
  所以**任意两个节点都不会重叠**（脚本会实测校验）。
· 起点 x=7700：组1（立绘）占 x5034-7484 / y2431-4831，任何覆盖全链的矩形都会压到它，
  所以脸部组整体排在组1 右侧，**组1 一个字节都不动**，两组框互不重叠。

布局图（col,row）
-----------------
Kontext 统一正脸    1024(0,0) 1025(0,1) 1026(0,2) | 1027(1,0) 1052(1,1)
                    1028(2,0) 1029(2,1) 1030(2,2) | 1043(3,0) 1044(3,1)
                    1045(4,0) 1046(4,1) | 1047(5,0) 1049(5,1) 1050(6,1) | 1048(6,0)
Kontext 90°底稿     1031(2,3) 1032(3,3) 1033(4,3) 1034(5,3) 1035(6,3)
                    1036(7,3) 1051(7,4) 1042(8,4)
SDXL 正脸           1002(0,6) 1003(0,7) | 1004(1,6) 1005(1,7) 1006(1,8)
                    1007(2,6) 1008(2,7) 1009(2,8) | 1010(3,6) 1011(3,7) 1012(3,8)
                    1013(4,6) 1014(4,7) | 1015(5,6) 1016(6,6) 1018(6,7)
                    1019(7,6) 1020(7,7) 1021(8,6)
SDXL 左/右脸        1100(6,8) 1101(7,8) 1102(6,9) 1103(7,9) 1104(8,8) 1105(9,8)
                    1107(10,8) 1108(11,8) 1109(12,8) 1110(12,9) 1111(13,9)
说明 Note           1001(0,10) 1022(4,10) 1023(7,10)

用法：
    python _update_live_layout.py dry
    python _update_live_layout.py run     # 提交并把三张成品拉回本地
    python _update_live_layout.py push    # 写回线上（备份 + 回读校验，失败自动还原）
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
OUTDIR = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "final")
WFNAME = "夜市百相簿-主工作流.json"
ENC = urllib.parse.quote(WFNAME, safe='')
MODE = sys.argv[1] if len(sys.argv) > 1 else "dry"

X0, Y0, CW, CH = 7700, 380, 800, 520
SLOT = {
    # Kontext 统一正脸
    1024: (0, 0), 1025: (0, 1), 1026: (0, 2),
    1027: (1, 0), 1052: (1, 1),
    1028: (2, 0), 1029: (2, 1), 1030: (2, 2),
    1043: (3, 0), 1044: (3, 1),
    1045: (4, 0), 1046: (4, 1),
    1047: (5, 0), 1049: (5, 1), 1050: (6, 1),
    1048: (6, 0),
    # Kontext 90° 底稿
    1031: (2, 3), 1032: (3, 3), 1033: (4, 3), 1034: (5, 3), 1035: (6, 3),
    1036: (7, 3), 1051: (7, 4), 1042: (8, 4),
    # SDXL 正脸
    1002: (0, 6), 1003: (0, 7),
    1004: (1, 6), 1005: (1, 7), 1006: (1, 8),
    1007: (2, 6), 1008: (2, 7), 1009: (2, 8),
    1010: (3, 6), 1011: (3, 7), 1012: (3, 8),
    1013: (4, 6), 1014: (4, 7),
    1015: (5, 6), 1016: (6, 6), 1018: (6, 7),
    1019: (7, 6), 1020: (7, 7), 1021: (8, 6),
    # SDXL 左 / 右脸
    1100: (6, 8), 1101: (7, 8), 1102: (6, 9), 1103: (7, 9),
    1104: (8, 8), 1105: (9, 8),
    1107: (10, 8), 1108: (11, 8), 1109: (12, 8), 1110: (12, 9), 1111: (13, 9),
    # 说明
    1001: (0, 10), 1022: (4, 10), 1023: (7, 10),
}


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


print("=== 1) 拉线上现行版并备份 ===")
wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
ts = time.strftime("%Y%m%d_%H%M%S")
bpath = os.path.join(WFDIR, "_backup_pre_layout_%s.json" % ts)
io.open(bpath, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("  nodes=%d links=%d  备份 -> %s" % (len(wf["nodes"]), len(wf["links"]), os.path.basename(bpath)))

byid = {n["id"]: n for n in wf["nodes"]}
G = [n for n in wf["nodes"] if n["id"] >= 1000]
missing = [n["id"] for n in G if n["id"] not in SLOT]
extra = [i for i in SLOT if i not in byid]
if missing or extra:
    print("★ 槽位表与线上节点不一致：没排到的=%s  表里多余的=%s" % (missing, extra)); sys.exit(1)
print("  本组 %d 个节点全部有槽位" % len(G))

print("\n=== 2) 重排 ===")
for n in G:
    c, r = SLOT[n["id"]]
    n["pos"] = [X0 + c * CW, Y0 + r * CH]

# order 按拓扑深度重排（只影响前端显示的顺序标记，不影响执行）
L = {l[0]: l for l in wf["links"]}
gids = {n["id"] for n in G}
indeg = {i: 0 for i in gids}
adj = {i: [] for i in gids}
for l in wf["links"]:
    if l[1] in gids and l[3] in gids:
        adj[l[1]].append(l[3]); indeg[l[3]] += 1
import collections
q = collections.deque(sorted([i for i in gids if indeg[i] == 0]))
depth = {i: 0 for i in gids}
seen = set()
while q:
    u = q.popleft()
    if u in seen: continue
    seen.add(u)
    for v in adj[u]:
        depth[v] = max(depth[v], depth[u] + 1)
        indeg[v] -= 1
        if indeg[v] == 0: q.append(v)
for n in G:
    n["order"] = depth.get(n["id"], 0)
print("  拓扑深度 %d 层；order 已按层重排" % (max(depth.values()) + 1))

# 重算包围盒
xs0 = min(n["pos"][0] for n in G); ys0 = min(n["pos"][1] for n in G)
xs1 = max(n["pos"][0] + (n.get("size") or (300, 100))[0] for n in G)
ys1 = max(n["pos"][1] + (n.get("size") or (300, 100))[1] for n in G)
g2 = next(g for g in wf["groups"] if g["id"] == 2)
oldbox = list(g2["bounding"])
g2["bounding"] = [xs0 - 40, ys0 - 40, (xs1 - xs0) + 120, (ys1 - ys0) + 120]
print("  节点范围 x %.0f-%.0f  y %.0f-%.0f" % (xs0, xs1, ys0, ys1))
print("  组2 包围盒 %s -> %s" % ([round(v) for v in oldbox], [round(v) for v in g2["bounding"]]))

print("\n=== 3) 自检 ===")
# 组内两两矩形重叠
rects = [(n["id"], n["pos"][0], n["pos"][1],
          (n.get("size") or (300, 100))[0], (n.get("size") or (300, 100))[1]) for n in G]
ov = []
for i in range(len(rects)):
    for j in range(i + 1, len(rects)):
        a, b = rects[i], rects[j]
        if max(a[1], b[1]) < min(a[1] + a[3], b[1] + b[3]) and max(a[2], b[2]) < min(a[2] + a[4], b[2] + b[4]):
            ov.append((a[0], b[0]))
print("   组内节点重叠对：%s" % (ov or "无 ✔"))
g1 = next(g for g in wf["groups"] if g["id"] == 1)
ax, ay, aw, ah = g2["bounding"]; bx, by, bw, bh = g1["bounding"]
ox = max(0, min(ax + aw, bx + bw) - max(ax, bx)); oy = max(0, min(ay + ah, by + bh) - max(ay, by))
print("   与组1 的重叠：x %.0f  y %.0f  %s" % (ox, oy, "✔ 不重叠" if ox * oy == 0 else "★ 重叠"))
if ov or (ox * oy != 0):
    print("★ 自检不过，不写。"); sys.exit(1)

out_local = os.path.join(WFDIR, "_pending_layout.json")
io.open(out_local, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("   待推送版本 -> %s" % os.path.basename(out_local))
if MODE == "dry":
    print("\n[dry] 未联网写。"); sys.exit(0)

# ---------- 跑 ----------
sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                       # noqa
API, TITLES = build_api(wf)
TARGETS = [nid for nid, a in API.items()
           if a["class_type"] == "SaveImage" and "脸部" in str(a["inputs"].get("filename_prefix", ""))
           and "草稿" not in str(a["inputs"].get("filename_prefix", ""))]
print("\n=== 4) 目标输出 ===")
for t in sorted(TARGETS, key=lambda x: int(x)):
    print("   #%s  %s" % (t, API[t]["inputs"]["filename_prefix"]))
subg = {k: v for k, v in API.items() if k in deps(API, TARGETS)}
print("   裁剪后 %d 节点；采样器 %s" % (len(subg),
      sorted([k for k, v in subg.items() if v["class_type"] == "KSampler"], key=int)))
res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 180).decode())
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:2000]); sys.exit(1)
pid = res["prompt_id"]; print("\n=== 5) 提交 prompt_id=%s" % pid)
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
print("\n=== 6) 下载三张成品 ===")
for nid, o in done.items():
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        p = os.path.join(OUTDIR, im["filename"])
        open(p, "wb").write(raw("/view?" + q, None, None, 300))
        print("   saved %-50s %7.1f KB" % (im["filename"], os.path.getsize(p) / 1024))
print("   -> %s" % OUTDIR)

if MODE != "push":
    print("\n[run] 跑完，未写工作流。"); sys.exit(0)

print("\n=== 7) 写回线上 ===")
try:
    raw("/api/userdata/workflows%2F" + ENC, io.open(out_local, encoding="utf-8").read().encode("utf-8"),
        "application/json", 300)
    print("   POST 完成")
except urllib.error.HTTPError as e:
    print("   ★ HTTP %s: %s" % (e.code, e.read().decode('utf-8', 'replace')[:300])); sys.exit(1)
back = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
bb = {n["id"]: n for n in back["nodes"]}
okb = all(bb[i]["pos"] == [X0 + SLOT[i][0] * CW, Y0 + SLOT[i][1] * CH] for i in SLOT if i in bb)
bg2 = next(g for g in back["groups"] if g["id"] == 2)
print("   回读：位置全部正确 %s；组2 包围盒 %s" % ("✔" if okb else "✘", [round(v) for v in bg2["bounding"]]))
io.open(os.path.join(WFDIR, "_live_now.json"), "w", encoding="utf-8").write(json.dumps(back, ensure_ascii=False, indent=1))
if not okb:
    print("★ 校验不过，自动还原 ...")
    raw("/api/userdata/workflows%2F" + ENC, io.open(bpath, encoding="utf-8").read().encode("utf-8"),
        "application/json", 300)
    print("   已还原。"); sys.exit(1)
print("\n✔ 布局已整理并写回线上")
