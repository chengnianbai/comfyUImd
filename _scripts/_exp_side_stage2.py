# -*- coding: utf-8 -*-
"""方案 2'（两段式）：把「侧脸自己的产物」当成**像素对齐的参考图**再重绘一次
—— **只改提交内容，绝不写服务器工作流**

为什么打这一枪（2026-09-24 的硬证据）
------------------------------------
正脸之所以有质感：**它的参考图与目标视角像素对齐**（同视角重拍）。
    正脸产物 lapVar 198.8 > 它自己那张降采样参考图的 92.4
    ⇒ 模型在"重拍同一视角"时是【生成】纹理的，参考图的纹理水平并不封顶。
侧脸之所以糊：参考图是【正脸】，与 90° 目标几何对不上，ReferenceLatent 是软条件
    → 只传身份/大结构，传不了毛孔级高频 → 模型退回「90°侧面=光滑」的先验。
    反证：侧脸参考(198.8)比侧脸输出(150.3)更细，参考更好结果反而掉了。

本枪的设计：让侧脸的第二段也拿到「像素对齐」的参考图。
    · 第 1 段不重跑 —— 直接用服务器 output 里已有的 00045（几何正确的 90° 侧脸）
    · 第 2 段：LoadImageOutput(00045) → FluxKontextImageScale → VAEEncode
              → ReferenceLatent → KSampler(纯噪声起点, denoise 1.0) → 存图

★ 为什么这一枪能避开已知的两个坑
    1. **不是低 denoise 二次重绘**（你们 09-22 实测的"磨皮主犯"）：起点仍是纯噪声 1052，
       denoise 仍是 1.0，姿势由参考图锁。低 denoise 会向流形均值收敛、把高频当噪声抹掉，
       这条路径完全不经过那个机理。
    2. **不是换模型/换人**：身份仍锁在同一张侧脸上。

两个变体，一次分辨归因
    A：只换参考图对齐，**提示词一字不动**（复用线上 1031/1032）→ 纯"对齐"变量
    B：对齐参考 + 一段"要毛孔"的重拍词（新 CLIPTextEncode）→ A→B 只变提示词
    判读：A 明显高于基线 150 ⇒ 对齐就是主因；A≈150 而 B 高 ⇒ 词在卡着；两个都≈150 ⇒
          我的机理判断错，该换路线（FaceDetailer / 更高分辨率人脸精修）。

用法：
    python _exp_side_stage2.py dry
    python _exp_side_stage2.py run
可调：--src <服务器output文件名>   默认 闻灯主图-左侧脸-成品_00045_.png
"""
import os, sys, io, ssl, json, time, uuid, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wf_api import build_api, deps

BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
if not BASE:
    print("★ 先设 COMFY_BASE"); sys.exit(4)
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"D:\xiaobai-claude code\comfyUImd"
WFNAME = "夜市百相簿-主工作流.json"
MODE = sys.argv[1] if len(sys.argv) > 1 else "dry"

SRC = "闻灯主图-左侧脸-成品_00045_.png"
for i, a in enumerate(sys.argv):
    if a == "--src":
        SRC = sys.argv[i + 1]
SRC_WIDGET = SRC + " [output]"          # LoadImageOutput 的 widget 值格式（与线上既有节点一致）

SEED = 20260920
STAGE2_PROMPT = (
    "Re-photograph this exact profile portrait as a natural high-end photographic portrait "
    "of the same person.\n\n"
    "Keep exactly the same true 90-degree LEFT profile head direction, the same facial identity, "
    "facial proportions, eyes, eyebrows, nose, lips, jaw, cheekbones, hair and mole placement, "
    "the same light blue shirt, the same crop and framing, the same lighting direction and the "
    "same plain background.\n\n"
    "Do not turn, rotate or move the head. Do not change the viewing angle. "
    "Do not redesign, beautify, age, symmetrize or replace his face.\n\n"
    "Regenerate ONLY the photographic surface and the skin material. Render natural visible pores, "
    "fine skin micro-texture, natural skin grain and subtle skin tone variation across the large "
    "visible cheek, jaw and neck. Keep individual eyebrow hairs visible. Keep realistic short "
    "stubble around the upper lip and mouth with visible skin between the individual hairs. "
    "Keep a few fine natural flyaway hair strands.\n\n"
    "The realism must come from a real photographic skin surface with genuine micro-detail, "
    "not from sharpening. Keep restrained film grain and natural color. Keep the same photographic "
    "rendering, lighting and color grading as the input image.\n\n"
    "Do not smooth the skin excessively. Do not create airbrushed, plastic, porcelain, waxy, "
    "polished or beauty-filter skin. Do not add freckles, dark spots or scattered dark speckles."
)

OUTDIR = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "stage2")
PFX_A_L = "闻灯主图-左侧脸-A对齐参考-成品"
PFX_A_R = "闻灯主图-右侧脸-A对齐参考-成品"
PFX_B_L = "闻灯主图-左侧脸-B对齐重拍-成品"
PFX_B_R = "闻灯主图-右侧脸-B对齐重拍-成品"


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype:
        h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


def skin_stats(path):
    try:
        import numpy as np
        from PIL import Image
        from numpy.lib.stride_tricks import sliding_window_view
    except Exception:
        return None
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    R, G, B = a[:, :, 0].astype(np.int16), a[:, :, 1].astype(np.int16), a[:, :, 2].astype(np.int16)
    mx = np.maximum(np.maximum(R, G), B); mn = np.minimum(np.minimum(R, G), B)
    sat = (mx - mn) / np.maximum(mx, 1)
    m = (R > 95) & (R > G) & (G > B) & ((R - B) > 12) & ((R - B) < 90) & (sat > 0.12) & (sat < 0.65)
    mm = m[1:-1, 1:-1] & m[:-2, 1:-1] & m[2:, 1:-1] & m[1:-1, :-2] & m[1:-1, 2:]
    if mm.sum() < 1000:
        return None
    g = 0.299 * a[:, :, 0] + 0.587 * a[:, :, 1] + 0.114 * a[:, :, 2]
    k = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], float)
    lap = (sliding_window_view(g, (3, 3)) * k).sum(axis=(-1, -2))
    loc = sliding_window_view(g, (3, 3)).reshape(g.shape[0] - 2, g.shape[1] - 2, -1).std(axis=-1)
    return float(lap[mm].var()), float(loc[mm].mean())


print("=== 1) 拉线上工作流（只读）===")
wf = json.loads(raw("/api/userdata/workflows%2F" + urllib.parse.quote(WFNAME), None, None, 60)
                .decode("utf-8", "replace"))
API, TITLES = build_api(wf)
print("  节点 %d  id=%s" % (len(wf["nodes"]), wf.get("id")))
# 对照：线上既有的 LoadImageOutput 节点用的什么值格式
for n in wf["nodes"]:
    if n["type"] == "LoadImageOutput":
        print("  线上既有 LoadImageOutput #%s 值 = %r" % (n["id"], (n.get("widgets_values") or [None])[0]))

print("\n=== 2) 参考图源：%s ===" % SRC_WIDGET)

A = json.loads(json.dumps(API))
changes = []
# --- 像素对齐的参考 latent 链 ---
A["9101"] = {"class_type": "LoadImageOutput", "inputs": {"image": SRC_WIDGET},
             "_meta": {"title": "★ 像素对齐参考源 = 第一段侧脸"}}
A["9102"] = {"class_type": "FluxKontextImageScale", "inputs": {"image": ["9101", 0]},
             "_meta": {"title": "对齐参考 · Kontext 尺寸"}}
A["9103"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["9102", 0], "vae": ["1026", 0]},
             "_meta": {"title": "对齐参考 · latent"}}
changes.append("新增 9101 LoadImageOutput(%s) -> 9102 Scale -> 9103 VAEEncode" % SRC_WIDGET)

KS = {"model": ["1024", 0], "negative": ["1030", 0], "latent_image": ["1052", 0],
      "seed": SEED, "steps": 20, "cfg": 1.0, "sampler_name": "euler",
      "scheduler": "simple", "denoise": 1.0}

# --- A：对齐参考 + 原提示词（复用线上 1031/1032）---
A["9110"] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["1032", 0], "latent": ["9103", 0]},
             "_meta": {"title": "A · 对齐参考进 conditioning（复用线上左脸词）"}}
A["9111"] = {"class_type": "KSampler", "inputs": dict(KS, positive=["9110", 0]),
             "_meta": {"title": "A · 对齐参考 d1.0（原词）"}}
A["9112"] = {"class_type": "VAEDecode", "inputs": {"samples": ["9111", 0], "vae": ["1026", 0]}, "_meta": {}}
A["9113"] = {"class_type": "SaveImage", "inputs": {"images": ["9112", 0], "filename_prefix": PFX_A_L}, "_meta": {}}
A["9114"] = {"class_type": "ImageFlip", "inputs": {"image": ["9112", 0], "flip_method": "y-axis: horizontally"}, "_meta": {}}
A["9115"] = {"class_type": "SaveImage", "inputs": {"images": ["9114", 0], "filename_prefix": PFX_A_R}, "_meta": {}}
changes.append("新增 A 支路 9110-9115（对齐参考 + 线上 1031 原词，d1.0）")

# --- B：对齐参考 + 要毛孔的重拍词 ---
A["9120"] = {"class_type": "CLIPTextEncode", "inputs": {"text": STAGE2_PROMPT, "clip": ["1025", 0]},
             "_meta": {"title": "B · 对齐重拍词（要毛孔）"}}
A["9121"] = {"class_type": "FluxGuidance", "inputs": {"conditioning": ["9120", 0], "guidance": 3.0}, "_meta": {}}
A["9122"] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["9121", 0], "latent": ["9103", 0]},
             "_meta": {"title": "B · 对齐参考进 conditioning"}}
A["9123"] = {"class_type": "KSampler", "inputs": dict(KS, positive=["9122", 0]),
             "_meta": {"title": "B · 对齐参考 d1.0（重拍词）"}}
A["9124"] = {"class_type": "VAEDecode", "inputs": {"samples": ["9123", 0], "vae": ["1026", 0]}, "_meta": {}}
A["9125"] = {"class_type": "SaveImage", "inputs": {"images": ["9124", 0], "filename_prefix": PFX_B_L}, "_meta": {}}
A["9126"] = {"class_type": "ImageFlip", "inputs": {"image": ["9124", 0], "flip_method": "y-axis: horizontally"}, "_meta": {}}
A["9127"] = {"class_type": "SaveImage", "inputs": {"images": ["9126", 0], "filename_prefix": PFX_B_R}, "_meta": {}}
changes.append("新增 B 支路 9120-9127（对齐参考 + 重拍词，d1.0）")

roots = ["9113", "9115", "9125", "9127"]
keep = deps(A, roots)
subg = {k: v for k, v in A.items() if k in keep}

print("\n=== 3) 本次相对线上的改动（仅新增，不改任何线上节点）===")
for c in changes:
    print("   ·", c)
print("   共享依赖（未改）：%s" % sorted(k for k in subg if int(k) < 1100))
print("   裁剪后 %d 节点" % len(subg))
print("   ★ 正脸/第一段全部不在图内 → 不重跑，只跑 2 个采样器")
io.open(os.path.join(HERE, "_wf", "_last_submit_stage2.json"), "w", encoding="utf-8").write(
    json.dumps(subg, ensure_ascii=False))

if MODE == "dry":
    print("\n[dry] 未提交。")
    sys.exit(0)

print("\n=== 4) 提交 ===")
res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 120).decode())
if res.get("node_errors"):
    print("  ★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:2500]); sys.exit(1)
pid = res["prompt_id"]; print("  prompt_id =", pid)
done = None
for i in range(180):
    time.sleep(2)
    h = json.loads(raw("/history/" + pid, None, None, 60).decode("utf-8", "replace"))
    if pid in h:
        st = h[pid].get("status", {})
        if st.get("status_str") == "error":
            for m in st.get("messages", []):
                if m[0] == "execution_error":
                    print("  ★ ERROR %s: %s" % (m[1].get("node_type"), m[1].get("exception_message", "")[:400]))
            sys.exit(1)
        done = h[pid].get("outputs", {}); print("  完成，约 %d 秒" % ((i + 1) * 2)); break
if done is None:
    print("  ★ 超时"); sys.exit(1)

os.makedirs(OUTDIR, exist_ok=True)
print("\n=== 5) 下载并测量 ===")
rows = []
print("  %-46s %8s %8s" % ("文件", "lapVar", "locStd"))
for nid, o in done.items():
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        p = os.path.join(OUTDIR, im["filename"])
        open(p, "wb").write(raw("/view?" + q, None, None, 300))
        st = skin_stats(p)
        print("  %-46s %s" % (im["filename"][:46],
              ("%8.2f %8.3f" % st) if st else "     n/a"))
        rows.append({"node": nid, "file": im["filename"], "stats": st})

# 参照图（基线侧脸 / 目标正脸）也拉下来，便于并排
print("\n=== 6) 参照 ===")
refs = [("闻灯主图-左侧脸-成品_00045_.png", "baseline_left_00045.png"),
        ("闻灯Kontext统一正脸-成品_00029_.png", "target_front_00029.png")]
for fn, out in refs:
    try:
        q = urllib.parse.urlencode({"filename": fn, "subfolder": "", "type": "output"})
        p = os.path.join(OUTDIR, out)
        open(p, "wb").write(raw("/view?" + q, None, None, 300))
        st = skin_stats(p)
        print("  %-46s %s" % (out, ("%8.2f %8.3f" % st) if st else " n/a"))
        rows.append({"node": "ref", "file": out, "stats": st})
    except Exception as e:
        print("  %s -> %s" % (fn, type(e).__name__))

io.open(os.path.join(OUTDIR, "_run_meta.json"), "w", encoding="utf-8").write(
    json.dumps({"src": SRC, "seed": SEED, "rows": rows}, ensure_ascii=False, indent=1))
print("\n产物 -> %s" % OUTDIR)
print("判读: A 明显高于基线 150.27 -> 对齐是主因; A~150 而 B 高 -> 词在卡着; 都~150 -> 机理判断错, 换路线。")
