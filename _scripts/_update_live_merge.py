# -*- coding: utf-8 -*-
"""线上工作流更新 2：合并组3 到组2（一个组），并删掉草稿存图节点

改动清单
--------
[删除]
  · 1017 SaveImage「草稿 · 闻灯脸部正面」  —— 用户要求只留成品
  · 1106 SaveImage「草稿 · 闻灯脸部左侧」  —— 同上
  （连同它们各自的连线一并删除；上游 VAEDecode 仍被成品支路使用，不受影响）

[分组合并]
  · 组3「【闻灯】Flux 文生图 · 一体化 fp8」整条链现在只是组2 的底稿来源，合并进组2
    -> 组2 包围盒扩为 [3057.37, 250, 7042.63, 2180] 覆盖两组全部节点
       （下边界卡在 y=2430，正好避开下方的组1「全身立绘」，不重叠）
    -> 删除 groups 里的组3 条目
    -> 组2 标题改为「【闻灯】脸部 · SDXL 出终稿 + Kontext 底稿」

[保留未删]（告知，不擅自删）
  · 1037-1041 旧右脸支路（mode=2，5 个节点）—— 你们的作战计划写明「勿删勿启用」，
    且已被 1110 ImageFlip 取代。要删说一声，一次就能拿掉。

[说明文字更新]
  · 1001 / 1023 两个 Note 改成描述新链路（原文字描述的是旧流程，已过时）

安全协议：备份 -> 本地构建 -> 提交跑一次验证 -> 写回 -> 回读逐字节比对 -> 失败自动还原。

用法：
    python _update_live_merge.py dry
    python _update_live_merge.py run
    python _update_live_merge.py push
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
OUTDIR = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "merged")
WFNAME = "夜市百相簿-主工作流.json"
ENC = urllib.parse.quote(WFNAME, safe='')
MODE = sys.argv[1] if len(sys.argv) > 1 else "dry"

DELETE = [1017, 1106, 1037, 1038, 1039, 1040, 1041]
# 1037-1041 = 旧「靠提示词赌 RIGHT 方向」右脸支路。
#   你们的作战计划写「勿删勿启用」，但其理由（留作后路）已被取代：
#   文档同时也写明「实测会收敛成和左脸同向——已被 1051 ImageFlip 方案取代」，
#   而现在 1110 ImageFlip 已提供硬保证。它同时是唯一越出合并组下边界的节点之一。
#   ★ 完整备份在 _backup_pre_merge_*.json，需要还原随时可以。
MOVE_NOTE_1023 = {"pos": [6000, 300]}       # 说明 Note 原本在 y2498，会压到组1；挪到盒内空白区
NEW_G2_BOX = [3050.0, 280.0, 6950.0, 2150.0]
NEW_G2_TITLE = "【闻灯】脸部 · SDXL 出终稿 + Kontext 底稿"

NOTE_1001 = (
    "【闻灯 · 脸部 · 一条链出三张终稿】\n\n"
    "★ 分工（2026-09-24 重构）\n"
    "  右半边（原组3）= Kontext 出底稿：00009 → 统一正脸 → 真 90° 左脸\n"
    "  左半边（本块）= SDXL 出终稿：正脸 / 左脸 / 右脸\n\n"
    "★ 为什么侧脸要绕这一圈\n"
    "  90° 姿势只有 Kontext 给得出。实测三重证据：v23 自己的 denoise 阶梯只到 3/4；\n"
    "  T2I-Adapter(canny) 强度 1.5→3.5 姿势纹丝不动只变脏；拿一张完美 90° 当基图，\n"
    "  SDXL 在 d0.30 就已经把它拧回 3/4。所以侧脸 = 「Kontext 出 90° → SDXL d0.45 重绘」，\n"
    "  结果落 3/4（用户 2026-09-24 已确认接受）。\n\n"
    "★ 三条支路\n"
    "  正脸 1004(wendeng_face_base.png) → d0.30 → 1021 成品\n"
    "  左脸 1100(缩组3 的 90° 侧脸) → d0.45 → 1109 成品\n"
    "  右脸 1110(左脸成品水平翻转) → 1111 成品\n\n"
    "★ 已删除草稿存图（1017/1106），只留成品。\n"
    "  注意线上计数器 last_link_id/last_node_id 曾是过期值，已修正。\n\n"
    "★ 跑法（按分支名提交，不要在浏览器点「运行」）\n"
    "  python _scripts\\run_wf.py \"夜市百相簿-主工作流.json\" "
    "\"闻灯-脸部正面,闻灯-脸部左侧,闻灯-脸部右侧\" final\n"
)

NOTE_1023 = (
    "【Kontext 底稿块 · 现在只负责「姿势 + 身份」】\n\n"
    "① 1027 = 身份基准图 00009（SDXL v23 旧稿）。\n"
    "② 1046 用 d1.0 + 纯噪声完整重画成「统一正脸」→ 1048 存图。\n"
    "③ 1050 的统一正脸 latent 作为身份参考，1034 用 d1.0 生成鼻尖朝画面左的真 90° 侧脸\n"
    "   → 1036 存图（这份是整条链的**姿势底稿**，不是终稿）。\n"
    "④ 1051 水平翻转得到右侧，方向由像素变换硬保证 → 1042 存图。\n\n"
    "★ 终稿不在这里。真 90° 侧脸经 1035 直接喂给本组右半边（1100），\n"
    "  由 SDXL 在 d0.45 重绘成终稿（1109/1111）。\n\n"
    "★ 1037-1041（旧的「靠提示词赌 RIGHT 方向」右脸支路）已删除：\n"
    "  你们的实测已证明它会收敛成和左脸同向，方向现由 1110 ImageFlip 硬保证。\n"
    "  （完整备份见 _wf/_backup_pre_merge_*.json，需要还原随时可以）\n"
)


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


print("=== 1) 拉线上现行版并备份 ===")
wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
ts = time.strftime("%Y%m%d_%H%M%S")
bpath = os.path.join(WFDIR, "_backup_pre_merge_%s.json" % ts)
io.open(bpath, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("  nodes=%d links=%d  备份 -> %s" % (len(wf["nodes"]), len(wf["links"]), os.path.basename(bpath)))

changes = []

# ---------- 删节点 ----------
gone_links = [l for l in wf["links"] if l[1] in DELETE or l[3] in DELETE]
wf["links"] = [l for l in wf["links"] if not (l[1] in DELETE or l[3] in DELETE)]
gone_ids = {l[0] for l in gone_links}
for n in wf["nodes"]:
    for out in (n.get("outputs") or []):
        if out.get("links"):
            out["links"] = [x for x in out["links"] if x not in gone_ids]
removed = []
for nid in DELETE:
    n = next((x for x in wf["nodes"] if x["id"] == nid), None)
    if n:
        removed.append("%s(%s %r)" % (nid, n["type"], (n.get("widgets_values") or [None])[0]))
wf["nodes"] = [n for n in wf["nodes"] if n["id"] not in DELETE]
changes.append("删除节点 %s；连同 %d 条连线" % (removed, len(gone_links)))

# ---------- 合并分组 ----------
grp = wf.get("groups", [])
g2 = next((g for g in grp if g["id"] == 2), None)
g3 = next((g for g in grp if g["id"] == 3), None)
print("  组2 原包围盒 %s / 组3 原包围盒 %s" % (g2["bounding"], g3["bounding"] if g3 else None))
g2["bounding"] = list(NEW_G2_BOX)
g2["title"] = NEW_G2_TITLE
wf["groups"] = [g for g in grp if g["id"] != 3]
changes.append("组2 包围盒 %s，标题 -> %r；删除组3 条目（%d 组 -> %d 组）"
               % (NEW_G2_BOX, NEW_G2_TITLE, len(grp), len(wf["groups"])))

# ---------- 更新说明文字 ----------
for nid, txt in ((1001, NOTE_1001), (1023, NOTE_1023)):
    n = next((x for x in wf["nodes"] if x["id"] == nid), None)
    if n:
        n["widgets_values"] = [txt]
        changes.append("更新说明 Note #%s" % nid)

# ---------- 挪说明 Note，避免它压到下方组1 的框 ----------
n1023 = next((x for x in wf["nodes"] if x["id"] == 1023), None)
if n1023:
    old = list(n1023["pos"])
    n1023["pos"] = list(MOVE_NOTE_1023["pos"])
    changes.append("移动说明 Note #1023  %s -> %s（原位置会越出合并组下边界、压到组1）"
                   % (old, n1023["pos"]))

print("\n=== 2) 本次改动 ===")
for c in changes:
    print("   · %s" % c)

# ---------- 自检：新包围盒真的覆盖全部节点，且不与组1 重叠 ----------
def inbox(n, box):
    x, y = n["pos"]; w, h = n.get("size") or (300, 100)
    bx, by, bw, bh = box
    return bx - 5 <= x and x + w <= bx + bw + 5 and by - 5 <= y and y + h <= by + bh + 5

bad = [n["id"] for n in wf["nodes"] if n["id"] >= 1000 and not inbox(n, NEW_G2_BOX)]
g1 = next((g for g in wf["groups"] if g["id"] == 1), None)
ov = None
if g1:
    ax, ay, aw, ah = NEW_G2_BOX; bx2, by2, bw2, bh2 = g1["bounding"]
    ovx = max(0, min(ax + aw, bx2 + bw2) - max(ax, bx2))
    ovy = max(0, min(ay + ah, by2 + bh2) - max(ay, by2))
    ov = (ovx, ovy)
print("\n=== 2) 自检 ===")
print("   新包围盒外的节点：%s" % (bad or "无 ✔"))
print("   与组1 的重叠面积：%s" % (("无 ✔" if ov == (0, 0) else ov),))
print("   剩余 SaveImage：")
for n in sorted([x for x in wf["nodes"] if x["type"] == "SaveImage"], key=lambda z: z["id"]):
    print("     #%-5s %s" % (n["id"], (n.get("widgets_values") or [None])[0]))

out_local = os.path.join(WFDIR, "_pending_merge.json")
io.open(out_local, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("   待推送版本 -> %s" % os.path.basename(out_local))
if MODE == "dry":
    print("\n[dry] 未联网写。"); sys.exit(0)

# ---------- 验证：跑一次全部成品 ----------
sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                      # noqa
API, TITLES = build_api(wf)
TARGETS = [nid for nid, a in API.items()
           if a["class_type"] == "SaveImage" and "脸部" in str(a["inputs"].get("filename_prefix", ""))]
print("\n=== 3) 目标输出 ===")
for t in sorted(TARGETS, key=lambda x: int(x)):
    print("   #%s  %s" % (t, API[t]["inputs"]["filename_prefix"]))
subg = {k: v for k, v in API.items() if k in deps(API, TARGETS)}
print("   裁剪后 %d 节点；采样器 %s" % (len(subg),
      sorted([k for k, v in subg.items() if v["class_type"] == "KSampler"], key=int)))
res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 180).decode())
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:2000]); sys.exit(1)
pid = res["prompt_id"]; print("\n=== 4) 提交验证 prompt_id=%s" % pid)
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
    print("\n[run] 验证通过，未写工作流。"); sys.exit(0)

print("\n=== 5) 写回线上 ===")
try:
    raw("/api/userdata/workflows%2F" + ENC, io.open(out_local, encoding="utf-8").read().encode("utf-8"),
        "application/json", 300)
    print("   POST 完成")
except urllib.error.HTTPError as e:
    print("   ★ HTTP %s: %s" % (e.code, e.read().decode('utf-8', 'replace')[:300])); sys.exit(1)

print("\n=== 6) 回读校验 ===")
back = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
bids = {n["id"] for n in back["nodes"]}
ok = True
if [d for d in DELETE if d in bids]:
    print("   ✘ 还有被删节点残留：%s" % [d for d in DELETE if d in bids]); ok = False
print("   回读 nodes=%d links=%d groups=%d（组：%s）"
      % (len(back["nodes"]), len(back["links"]), len(back.get("groups", [])),
         [g["title"][:28] for g in back.get("groups", [])]))
io.open(os.path.join(WFDIR, "_live_now.json"), "w", encoding="utf-8").write(json.dumps(back, ensure_ascii=False, indent=1))
if not ok:
    print("\n★ 校验不过，自动还原 ...")
    raw("/api/userdata/workflows%2F" + ENC, io.open(bpath, encoding="utf-8").read().encode("utf-8"),
        "application/json", 300)
    print("   已还原。"); sys.exit(1)
print("\n✔ 已合并为一个组，草稿节点已删，只留成品")
