# -*- coding: utf-8 -*-
"""重排组1（全身立绘）节点布局：按「共用 / 正面 / 侧面 / 背面 / 已停用」分带，每带 5 列网格

之前的 2 列 430×310 网格太密，节点（最大 760×460）互相压住 → 现在用 800×560 的格子。
用法： python _relayout_g1.py dry | push
"""
import os, sys, io, ssl, json, time, urllib.request, urllib.parse
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
ENC = urllib.parse.quote("夜市百相簿-主工作流.json", safe='')
MODE = sys.argv[1] if len(sys.argv) > 1 else "dry"

X0, Y0 = 3540, 2500          # 左移到组2 左侧的空白区（组2 从 x7660 起 → 5*800+ 刚好不越界）
CW, CH = 800, 560            # 格子（最大节点 760x460 装得下）
BAND_GAP = 120
COLS = 5

BANDS = [
    ("A 共用（底模 / ClipSkip / 正向B / 负向 / 放大模型）",
     [1, 17, 3, 5, 18, 19, 20, 21, 22]),
    ("B 正面支路", [2, 4, 6, 7, 8, 9, 10, 30, 31, 32, 33, 34, 23, 24, 14, 15]),
    ("E 已停用（第二段重绘，按 B.7 撤掉）", [12, 25, 13]),
    ("C 侧面支路", [300, 301, 302, 303, 304, 305, 306, 307, 308, 309, 310, 311, 312, 313, 314, 315, 316]),
    ("D 背面支路", [330, 331, 332, 333, 334, 335, 341, 342, 343, 344, 345, 346]),
    ("F 说明（每个 Note 独占一行，避免压住节点）", [16]),
]
NOTES = {16}
G1ALL = sorted({i for _, lst in BANDS for i in lst})
assert len(G1ALL) == 58, len(G1ALL)


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
byid = {n["id"]: n for n in wf["nodes"]}
# 格子尺寸按实际最大节点算，避免超出格里导致互相压住
g1nodes0 = [n for n in wf["nodes"] if n["id"] < 1000 and n["id"] not in NOTES]
CW = int(max((n.get("size") or (300, 100))[0] for n in g1nodes0)) + 60
CH = int(max((n.get("size") or (300, 100))[1] for n in g1nodes0)) + 60
print("按实际最大节点设定格子 = %dx%d" % (CW, CH))
host = urllib.parse.urlparse(BASE).netloc.split(".")[0]
bp = os.path.join(WFDIR, "_backup_pre_g1layout_%s_%s.json" % (host, time.strftime("%Y%m%d_%H%M%S")))
io.open(bp, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("备份 -> %s" % os.path.basename(bp))

missing = [i for i in G1ALL if i not in byid]
if missing:
    print("★ 缺节点 %s" % missing); sys.exit(1)

row = 0
for title, ids in BANDS:
    print("  %-46s %d 个节点" % (title, len(ids)))
    if any(i in NOTES for i in ids):
        # Note 尺寸很大，每个独占若干行，避免压住别的节点
        for nid in sorted(ids):
            byid[nid]["pos"] = [X0, Y0 + row*CH]
            h = (byid[nid].get("size") or (300, 100))[1]
            row += max(2, int(h / CH) + 1)
        continue
    for k, nid in enumerate(sorted(ids)):
        c, r = k % COLS, k // COLS
        byid[nid]["pos"] = [X0 + c*CW, Y0 + (row + r)*CH]
    row += (len(ids) + COLS - 1) // COLS + 1     # 带宽 + 1 行留白

# 组1 包围盒
g1 = next(g for g in wf["groups"] if g["id"] == 1)
gnodes = [n for n in wf["nodes"] if n["id"] < 1000]
bx0 = min(n["pos"][0] for n in gnodes); by0 = min(n["pos"][1] for n in gnodes)
bx1 = max(n["pos"][0] + (n.get("size") or (300, 100))[0] for n in gnodes)
by1 = max(n["pos"][1] + (n.get("size") or (300, 100))[1] for n in gnodes)
old = list(g1["bounding"])
g1["bounding"] = [bx0-40, by0-40, (bx1-bx0)+120, (by1-by0)+120]
print("\n组1 包围盒 %s -> %s" % ([round(v) for v in old], [round(v) for v in g1["bounding"]]))

# 重叠自检
rects = [(n["id"], n["pos"][0], n["pos"][1], (n.get("size") or (300,100))[0], (n.get("size") or (300,100))[1])
         for n in gnodes if n["id"] not in NOTES]      # Note 已各自占行，不参与重叠判定
ov = [(a[0], b[0]) for i, a in enumerate(rects) for b in rects[i+1:]
      if max(a[1],b[1]) < min(a[1]+a[3], b[1]+b[3]) and max(a[2],b[2]) < min(a[2]+a[4], b[2]+b[4])]
print("组内重叠对：%s" % (ov or "无 ✔"))
g2 = next(g for g in wf["groups"] if g["id"] == 2)
ax, ay, aw, ah = g1["bounding"]; cx, cy, cw, ch = g2["bounding"]
ovx = max(0, min(ax+aw, cx+cw) - max(ax, cx)); ovy = max(0, min(ay+ah, cy+ch) - max(ay, cy))
print("与组2 重叠：x %.0f y %.0f %s" % (ovx, ovy, "✔ 不重叠" if ovx*ovy == 0 else "★ 重叠"))
if ov or ovx*ovy:
    print("★ 自检不过"); sys.exit(1)

if MODE == "dry":
    print("\n[dry] 未联网写。"); sys.exit(0)
body = json.dumps(wf, ensure_ascii=False).encode("utf-8")
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
back = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
bb = {n["id"]: n for n in back["nodes"]}
good = all(bb[i]["pos"] == byid[i]["pos"] for i in G1ALL)
print("回读：全部位置正确 %s ；nodes=%d" % ("✔" if good else "✘", len(back["nodes"])))
print("\n✔ 组1 布局已重排")
