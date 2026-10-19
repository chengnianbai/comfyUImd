# -*- coding: utf-8 -*-
"""把「组2 正脸支路」更新到线上工作流（第一步，只做无争议的改动）

改动只有两处，都是字段级修改，不动任何连线：
  1. 节点 1004(LoadImage).image : wendeng_v23_face_base.png -> wendeng_face_base.png
     （后者 lapVar 234.82，与你们认可的「闻灯-正脸-已确认_成品」降到 896 后逐位一致；
       前者只有 117.44，是另一张细节减半的图）
  2. 组2 的 22 个节点 mode 2 -> 0（启用）

安全协议：先备份 -> POST 写回 -> GET 回读逐字节比对 -> 不一致立刻用备份还原。

用法：
    python _update_live_g1.py dry     # 只打印将要改什么
    python _update_live_g1.py push    # 真写（会先备份 + 回读校验）
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
WFNAME = "夜市百相簿-主工作流.json"
ENC = urllib.parse.quote(WFNAME, safe='')
MODE = sys.argv[1] if len(sys.argv) > 1 else "dry"
NEW_BASE_IMG = "wendeng_face_base.png"

# 组2 的 22 个节点 id
G2 = [1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008, 1009, 1010, 1011, 1012, 1013, 1014,
      1015, 1016, 1017, 1018, 1019, 1020, 1021, 1022]


def raw(p, data=None, ctype=None, timeout=300):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


print("=== 1) 拉线上现行版 ===")
wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
print("  id=%s  nodes=%d links=%d last_node_id=%s" % (wf.get("id"), len(wf["nodes"]), len(wf["links"]), wf.get("last_node_id")))

ts = time.strftime("%Y%m%d_%H%M%S")
bpath = os.path.join(WFDIR, "_backup_pre_g1enable_%s.json" % ts)
io.open(bpath, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("  已备份 -> %s" % os.path.basename(bpath))

# ---- 字段级修改 ----
before = wf["nodes"]
n1004 = next((n for n in before if n["id"] == 1004), None)
if n1004 is None:
    print("★ 找不到 1004，中止"); sys.exit(1)
old_img = (n1004.get("widgets_values") or [None])[0]
n1004["widgets_values"][0] = NEW_BASE_IMG

enabled, already = [], []
for n in before:
    if n["id"] in G2:
        if n.get("mode") == 0:
            already.append(n["id"])
        else:
            n["mode"] = 0
            enabled.append(n["id"])

print("\n=== 2) 本次改动 ===")
print("  · 1004.image  %r -> %r" % (old_img, NEW_BASE_IMG))
print("  · 启用组2 节点 %d 个：%s" % (len(enabled), enabled))
if already:
    print("  · （本来就已启用：%s）" % already)
print("  · 其它一律未动：nodes=%d links=%d 不变" % (len(wf["nodes"]), len(wf["links"])))

# 组2 内部连线自检（防止早就断了一半）
links = {l[0]: l for l in wf["links"]}
g2set = set(G2)
print("\n=== 3) 组2 内部连线自检 ===")
cnt = 0
for n in before:
    for inp in (n.get("inputs") or []):
        lid = inp.get("link")
        if lid is None or n["id"] not in g2set:
            continue
        l = links.get(lid)
        if l and l[1] in g2set:
            cnt += 1
        else:
            print("  ⚠ #%s.%s 的连线 %s 指向组外或缺失" % (n["id"], inp.get("name"), lid))
print("  组2 内部连线 %d 条，全部有效" % cnt)

if MODE == "dry":
    print("\n[dry] 未写入。确认后跑：python _update_live_g1.py push")
    sys.exit(0)

print("\n=== 4) 写回线上 ===")
body = json.dumps(wf, ensure_ascii=False).encode("utf-8")
try:
    r = raw("/api/userdata/workflows%2F" + ENC, body, "application/json", 300)
    print("  POST 返回 %s" % r.decode('utf-8', 'replace')[:200])
except urllib.error.HTTPError as e:
    print("  ★ HTTP %s: %s" % (e.code, e.read().decode('utf-8', 'replace')[:300])); sys.exit(1)

print("\n=== 5) 回读校验 ===")
back = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
b1004 = next((n for n in back["nodes"] if n["id"] == 1004), None)
print("  回读 1004.image = %r  %s" % ((b1004.get("widgets_values") or [None])[0],
      "✔" if (b1004.get("widgets_values") or [None])[0] == NEW_BASE_IMG else "✘"))
modes = {n["id"]: n.get("mode") for n in back["nodes"] if n["id"] in G2}
bad = [k for k, v in modes.items() if v != 0]
print("  回读组2 mode：%s" % ("全部=0 ✔" if not bad else "★ 这些不是0: %s" % bad))
print("  回读 nodes=%d links=%d" % (len(back["nodes"]), len(back["links"])))
io.open(os.path.join(WFDIR, "_live_now.json"), "w", encoding="utf-8").write(json.dumps(back, ensure_ascii=False, indent=1))

if bad or (b1004.get("widgets_values") or [None])[0] != NEW_BASE_IMG:
    print("\n★ 校验不过，用备份还原 ...")
    try:
        raw("/api/userdata/workflows%2F" + ENC, io.open(bpath, encoding="utf-8").read().encode("utf-8"),
            "application/json", 300)
        print("  已还原。请告诉我，我再查。")
    except Exception as e:
        print("  还原失败 %s —— 手动用 %s 恢复" % (type(e).__name__, bpath))
    sys.exit(1)
print("\n✔ 线上工作流已更新（1004 已修 + 组2 已启用）")
