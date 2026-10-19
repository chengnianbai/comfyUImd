# -*- coding: utf-8 -*-
"""生产形态：**把两段合成一张图** —— 侧脸第一段出图后，立刻用「它自己」当像素对齐参考再重绘一次
—— **只改提交内容，绝不写服务器工作流**

与 _exp_side_stage2.py 的区别
    那个版本靠 LoadImageOutput 读上一轮落盘的 00045 当参考（要先跑两次、还硬编码文件名）。
    这个版本把第二段**接在图内**：1034 → 1035(VAEDecode) → 对齐参考 → 第二段 KSampler，
    一次提交自动完成，没有中间文件依赖，也没有环（1034 的输入不依赖这条新链）。

为什么有效（2026-09-24 实测，lapVar/locStd，皮肤掩膜内）
    第一段侧脸 00045          150.27 / 3.066
    对齐参考+原词（A）        191.11 / 3.349     ← 只改「参考是否像素对齐」这一个变量
    对齐参考+重拍词（B）      222.25 / 3.536
    正脸 00029（目标）        198.79 / 3.402
    对照：上一轮 LoRA w=+0.7  132.48 / 2.852     ← 反效果，已弃
    A 相对基线 +27%、B +48%；A 的姿势几乎没动（与基线平均差 3.53 / 仅 2.2% 像素明显不同）。

本版本同时出 A/B 两支，第一段只跑一次（实测一次提交 94 秒全自动）
    A：第二段复用线上左脸词（1031/1032），**提示词一字不改** —— 最保守
    B：第二段换成「重拍+明确要毛孔」的词 —— 更猛，实测已超过正脸

★ 结论：推荐 A
    A 的 lapVar 191.11 / locStd 3.349 与正脸 198.79 / 3.402 基本持平，就是"追平"；
    1:1 目视也与正脸同档，而 B 目视偏"脆"（过锐）。B 留作"想要更狠"时的备选。
    姿势未漂：A 与第一段基线平均差仅 3.53、只有 2.2% 像素明显不同；
    对比上一轮失败的 LoRA w=+0.7（平均差 16.39 / 26.4%）—— 本方案既有效又外科手术式。

用法：
    python _exp_side_stage2_inline.py dry
    python _exp_side_stage2_inline.py run [--only A|B]
    python _exp_side_stage2_inline.py run --only A        # 只出推荐的那一支，省一半时间
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
ONLY = None
for i, a in enumerate(sys.argv):
    if a == "--only":
        ONLY = sys.argv[i + 1].upper()

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
OUTDIR = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "stage2_inline")
PFX = {"A": ("闻灯主图-左侧脸-A对齐-成品", "闻灯主图-右侧脸-A对齐-成品"),
       "B": ("闻灯主图-左侧脸-B对齐重拍-成品", "闻灯主图-右侧脸-B对齐重拍-成品")}


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
assert API["1034"]["inputs"]["model"] == ["1024", 0]
assert API["1035"]["class_type"] == "VAEDecode"

A = json.loads(json.dumps(API))
KS = {"model": ["1024", 0], "negative": ["1030", 0], "latent_image": ["1052", 0],
      "seed": SEED, "steps": 20, "cfg": 1.0, "sampler_name": "euler",
      "scheduler": "simple", "denoise": 1.0}
roots, changes = [], []

# 共享：把第一段的像素拿出来，做成「像素对齐参考 latent」
A["9201"] = {"class_type": "FluxKontextImageScale", "inputs": {"image": ["1035", 0]},
             "_meta": {"title": "★ 对齐参考 · Kontext 尺寸（取第一段侧脸像素）"}}
A["9202"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["9201", 0], "vae": ["1026", 0]},
             "_meta": {"title": "★ 对齐参考 · latent"}}
changes.append("新增 9201 FluxKontextImageScale(image←1035) -> 9202 VAEEncode")

for v in ("A", "B"):
    if ONLY and v != ONLY:
        continue
    cl, cr = PFX[v]
    if v == "A":
        cond = ("1032", 0)                       # 复用线上左脸词（1031→1032），一字不改
        n = {"rl": "9210", "ks": "9211", "vd": "9212", "fl": "9213", "sl": "9214", "sr": "9215"}
        A[n["rl"]] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": [cond[0], cond[1]], "latent": ["9202", 0]},
                      "_meta": {"title": "A · 对齐参考进 conditioning（复用线上左脸词）"}}
        changes.append("A：910 复用 1031/1032 原词（提示词零改动），只把参考换成 9202")
    else:
        n = {"re": "9220", "fg": "9221", "rl": "9222", "ks": "9223", "vd": "9224", "fl": "9225", "sl": "9226", "sr": "9227"}
        A[n["re"]] = {"class_type": "CLIPTextEncode", "inputs": {"text": STAGE2_PROMPT, "clip": ["1025", 0]},
                      "_meta": {"title": "B · 对齐重拍词（明确要毛孔）"}}
        A[n["fg"]] = {"class_type": "FluxGuidance", "inputs": {"conditioning": [n["re"], 0], "guidance": 3.0},
                      "_meta": {"title": "B · Guidance 3.0"}}
        A[n["rl"]] = {"class_type": "ReferenceLatent", "inputs": {"conditioning": [n["fg"], 0], "latent": ["9202", 0]},
                      "_meta": {"title": "B · 对齐参考进 conditioning"}}
        changes.append("B：新增 9220 重拍词 + 9221 Guidance(3.0) + 9222 ReferenceLatent")

    A[n["ks"]] = {"class_type": "KSampler", "inputs": dict(KS, positive=[n["rl"], 0]),
                  "_meta": {"title": "%s · 第二段 d1.0（对齐参考）" % v}}
    A[n["vd"]] = {"class_type": "VAEDecode", "inputs": {"samples": [n["ks"], 0], "vae": ["1026", 0]}, "_meta": {}}
    A[n["fl"]] = {"class_type": "ImageFlip", "inputs": {"image": [n["vd"], 0], "flip_method": "y-axis: horizontally"}, "_meta": {}}
    A[n["sl"]] = {"class_type": "SaveImage", "inputs": {"images": [n["vd"], 0], "filename_prefix": cl}, "_meta": {}}
    A[n["sr"]] = {"class_type": "SaveImage", "inputs": {"images": [n["fl"], 0], "filename_prefix": cr}, "_meta": {}}
    roots += [n["sl"], n["sr"]]
    changes.append("%s：第二段 KSampler %s + VAEDecode %s -> 左脸 %s / 右脸(翻转) %s" % (v, n["ks"], n["vd"], cl, cr))

keep = deps(A, roots)
subg = {k: v for k, v in A.items() if k in keep}
print("\n=== 2) 本次相对线上的改动（只新增，不改线上节点）===")
for c in changes:
    print("   ·", c)
print("   线上节点（未改，仅被复用）：%s" % sorted((k for k in subg if int(k) < 1100), key=int))
print("   裁剪后 %d 节点；采样器：%s"
      % (len(subg), sorted([k for k, v in subg.items() if v["class_type"] == "KSampler"], key=int)))
io.open(os.path.join(HERE, "_wf", "_last_submit_stage2_inline.json"), "w", encoding="utf-8").write(
    json.dumps(subg, ensure_ascii=False))
if MODE == "dry":
    print("\n[dry] 未提交。"); sys.exit(0)

print("\n=== 3) 提交 ===")
res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 120).decode())
if res.get("node_errors"):
    print("  ★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:2500]); sys.exit(1)
pid = res["prompt_id"]; print("  prompt_id =", pid)
done = None
for i in range(300):
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
print("\n=== 4) 下载并测量（皮肤掩膜内）===")
print("  %-48s %9s %8s" % ("文件", "lapVar", "locStd"))
rows = []
for nid, o in done.items():
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        p = os.path.join(OUTDIR, im["filename"])
        open(p, "wb").write(raw("/view?" + q, None, None, 300))
        st = skin_stats(p)
        print("  %-48s %s" % (im["filename"][:48], ("%9.2f %8.3f" % st) if st else "      n/a"))
        rows.append({"node": nid, "file": im["filename"], "stats": st})

print("\n=== 5) 参照（从服务器拉）===")
for fn, out in (("闻灯主图-左侧脸-成品_00045_.png", "ref_baseline_left_00045.png"),
                ("闻灯Kontext统一正脸-成品_00029_.png", "ref_target_front_00029.png")):
    try:
        q = urllib.parse.urlencode({"filename": fn, "subfolder": "", "type": "output"})
        p = os.path.join(OUTDIR, out)
        open(p, "wb").write(raw("/view?" + q, None, None, 300))
        print("  %-48s %s" % (out, ("%9.2f %8.3f" % skin_stats(p))))
        rows.append({"node": "ref", "file": out, "stats": skin_stats(p)})
    except Exception as e:
        print("  %s -> %s" % (fn, type(e).__name__))

io.open(os.path.join(OUTDIR, "_run_meta.json"), "w", encoding="utf-8").write(
    json.dumps({"seed": SEED, "only": ONLY, "rows": rows}, ensure_ascii=False, indent=1))
print("\n产物 -> %s" % OUTDIR)
