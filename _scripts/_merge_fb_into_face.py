# -*- coding: utf-8 -*-
"""把「全身立绘」支路真正并入脸部组：共用底模/ClipSkip/放大模型，删掉重复加载器，合并为一个组

依据
    脸部组 (组2) 的 1002 CheckpointLoaderSimple = leosamsHelloworldXL_helloworldXL70（与组1 的 1 同文件）
                         1003 CLIPSetLastLayer(-1)        （与组1 的 17 同参数）
                         1018 UpscaleModelLoader          （与组1 的 22 同文件 4x-UltraSharp）
    ⇒ 组1 的 1 / 17 / 22 是重复件，可全部改为引用组2 的对应节点后删除。
★ VAE 不能共用：组2 的 1026 载的是 Flux 的 ae.safetensors，全身那条是 SDXL，
  必须继续用 SDXL 底模自带的 VAE（1002.VAE）。

改动
    · 所有 origin=1 的连线改指 1002（槽位顺序同为 MODEL/CLIP/VAE，可直接对应）
    · 所有 origin=17 的连线改指 1003 ；所有 origin=22 的连线改指 1018
    · 删除节点 1 / 17 / 22
    · 删除组1 条目；组2 包围盒扩为「全部节点」的并集；组名改为
      【闻灯】脸部 + 全身 · SDXL 出终稿 + Kontext 底稿
    · 修正 Note 16 里那句错话（"把脸缩到头部贴到头顶" → 写明「头部必须采用已确认脸的像素」）

用法： python _merge_fb_into_face.py dry | run | push
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
OUT = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "merged2")
ENC = urllib.parse.quote("夜市百相簿-主工作流.json", safe='')
MODE = sys.argv[1] if len(sys.argv) > 1 else "dry"
REMAP = {1: 1002, 17: 1003, 22: 1018}          # 旧 origin -> 新的共享节点
DELETE = [1, 17, 22]
NEW_G2_TITLE = "【闻灯】脸部 + 全身 · SDXL 出终稿 + Kontext 底稿"


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
byid = {n["id"]: n for n in wf["nodes"]}
host = urllib.parse.urlparse(BASE).netloc.split(".")[0]
bp = os.path.join(WFDIR, "_backup_pre_fbmerge_%s_%s.json" % (host, time.strftime("%Y%m%d_%H%M%S")))
io.open(bp, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("备份 -> %s" % os.path.basename(bp))
print("现状 nodes=%d links=%d groups=%d" % (len(wf["nodes"]), len(wf["links"]), len(wf.get("groups", []))))

# 逐条核对：三个旧节点确实与共享节点同文件/同参数
for old, new in REMAP.items():
    o, n = byid[old], byid[new]
    print("  #%-5s %-24s %s" % (old, o["type"], o.get("widgets_values")))
    print("  #%-5s %-24s %s   ← 合并到它" % (new, n["type"], n.get("widgets_values")))

# ---- 改 origin ----
moved = {}
for l in wf["links"]:
    if l[1] in REMAP:
        newid = REMAP[l[1]]
        # 槽位含义一致（CheckpointLoaderSimple 的 MODEL/CLIP/VAE 与旧节点同序）
        n_out = byid[newid].get("outputs") or []
        if l[2] >= len(n_out):
            print("★ #%s 槽位 %d 超出（%d 个输出）" % (newid, l[2], len(n_out))); sys.exit(1)
        # 从旧节点输出表摘掉
        so = byid[l[1]].get("outputs") or []
        if l[2] < len(so) and so[l[2]].get("links"):
            so[l[2]]["links"] = [x for x in so[l[2]]["links"] if x != l[0]]
        # 挂到新节点
        n_out[l[2]].setdefault("links", [])
        if n_out[l[2]]["links"] is None: n_out[l[2]]["links"] = []
        n_out[l[2]]["links"].append(l[0])
        l[1] = newid
        moved[(old, newid)] = moved.get((old, newid), 0) + 1
print("\n改指统计: %s" % {("%s->%s" % k): v for k, v in moved.items()})

# ---- 删节点 ----
wf["nodes"] = [n for n in wf["nodes"] if n["id"] not in DELETE]
# 清掉任何残留指向被删节点的连线
# ★ 预期会清掉几条「喂给已删节点」的连线（如 1002 -> 17 的 CLIP），这是正常的；
#   真正要断言的是：没有任何连线的**起点**是被删节点（那才是悬空）
bad_origin = [l for l in wf["links"] if l[1] in DELETE]
dead_target = [l for l in wf["links"] if l[3] in DELETE]
wf["links"] = [l for l in wf["links"] if l[1] not in DELETE and l[3] not in DELETE]
print("清理「喂给已删节点」的连线：%s" % (dead_target or "无"))
print("起点是被删节点的悬空链：%s" % (bad_origin or "无 ✔"))
assert not bad_origin

# ---- 合并分组 ----
grp = wf.get("groups", [])
g1 = next((g for g in grp if g["id"] == 1), None)
g2 = next((g for g in grp if g["id"] == 2), None)
print("\n组1 原包围盒 %s ；组2 原包围盒 %s" % ([round(v) for v in g1["bounding"]], [round(v) for v in g2["bounding"]]))
wf["groups"] = [g for g in grp if g["id"] != 1]
alln = wf["nodes"]
bx0 = min(n["pos"][0] for n in alln); by0 = min(n["pos"][1] for n in alln)
bx1 = max(n["pos"][0] + (n.get("size") or (300, 100))[0] for n in alln)
by1 = max(n["pos"][1] + (n.get("size") or (300, 100))[1] for n in alln)
g2["bounding"] = [bx0-40, by0-40, (bx1-bx0)+120, (by1-by0)+120]
g2["title"] = NEW_G2_TITLE
print("合并后 1 个组：%r  包围盒 %s" % (g2["title"], [round(v) for v in g2["bounding"]]))

# ---- 修正 Note 16 的错话 ----
n16 = byid.get(16)
if n16:
    t = (n16.get("widgets_values") or [""])[0]
    t2 = t.replace(
        "② 把**已确认的脸**（本工作流「脸部」块产出的成品）缩到头部、贴到头顶；",
        "② 把**已确认的脸**（本工作流「脸部」块产出的成品）的**头部**按生成头的实际位置/头宽对齐贴入；\n"
        "   ★ 目的不是「生成一张脸再盖住」，而是**全身图的头部必须直接采用已确认脸的像素**，\n"
        "   不得由文生图另生成一张脸（H09/H10）。掩膜必须用**头部剪影 alpha**，不能用矩形。")
    t2 = t2.replace("★ 本块 = 原「立绘」块原址改造",
                    "★ 本块（全身支路）已于 2026-10-08 并入「脸部 + 全身」组，共用 1002 底模 / 1003 ClipSkip / 1018 放大模型")
    if t2 != t:
        n16["widgets_values"] = [t2]
        print("已修正 Note 16 文案")
    else:
        print("Note 16 文案未匹配到待改句（跳过）")

out_local = os.path.join(WFDIR, "_pending_fbmerge.json")
io.open(out_local, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("\nnodes=%d links=%d groups=%d" % (len(wf["nodes"]), len(wf["links"]), len(wf["groups"])))
if MODE == "dry":
    print("\n[dry] 未联网写。"); sys.exit(0)

# ---- 跑一次验证（脸部三张 + 全身六张里挑三张成品）----
sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                       # noqa
API, _ = build_api(wf)
TARGETS = [nid for nid, a in API.items() if a["class_type"] == "SaveImage"
           and str(a["inputs"].get("filename_prefix", "")).endswith("成品")
           and ("闻灯-脸部" in str(a["inputs"].get("filename_prefix")) or "闻灯-全身" in str(a["inputs"].get("filename_prefix")))]
print("\n=== 目标输出 %d 个 ===" % len(TARGETS))
for t in sorted(TARGETS, key=lambda x: int(x)): print("   #%-5s %s" % (t, API[t]["inputs"]["filename_prefix"]))
subg = {k: v for k, v in API.items() if k in deps(API, TARGETS)}
print("   裁剪后 %d 节点；采样器 %d 个" % (len(subg), sum(1 for v in subg.values() if v["class_type"] == "KSampler")))
res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 180).decode())
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:1800]); sys.exit(1)
pid = res["prompt_id"]; print("prompt_id=%s" % pid)
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
back = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
bb = {n["id"]: n for n in back["nodes"]}
print("\n回读：nodes=%d links=%d groups=%d（%s）" % (
    len(back["nodes"]), len(back["links"]), len(back["groups"]), [g["title"] for g in back["groups"]]))
print("  已删 1/17/22：%s" % (not any(i in bb for i in DELETE)))
print("  全身支路是否已引用 1002：%s" % any(l[1] == 1002 and l[3] in (7, 8, 303, 304, 313, 333, 334, 343) for l in back["links"]))
print("\n✔ 全身支路已并入脸部组（共用引擎）")
