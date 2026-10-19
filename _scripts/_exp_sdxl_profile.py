# -*- coding: utf-8 -*-
"""组2 改组实验：SDXL 出「正脸 + 左脸 + 右脸」，姿势由 Canny 适配器强制，身份来自 v23 正脸 latent
—— **只改提交内容，绝不写服务器工作流**

为什么这么搭
------------
· 身份：沿用 v23 的做法 —— 基图 = wendeng_v23_face_base.png（已确认正脸）编码成 latent，
        作为 KSampler 的**起点**。v23 注释实证「以已确认正脸做 img2img，身份保留得非常好」。
· 姿势：v23 只能靠 denoise 硬推，结果 d0.86 也只到 3/4（已复核实物）。
        本版把「转头」交给 ControlNet —— 控制源 = 你们已有的 Kontext 90° 侧脸
        （闻灯主图-左侧脸-成品_00045_.png，本来就是真 90°），经 Canny 提轮廓。
        侧脸剪影（额头→鼻→唇→下巴）本身就是极强的姿势约束。
· 关键：**低 denoise 保人 + ControlNet 转头** 同时成立 —— 这正是 09-17 缺的那半块拼图
        （当时 ControlNet 有节点但模型目录空）。

本版扫 3 档 denoise，只为找「真转到 90° 且还是同一个人」的临界点
    L55 / L70 / L85 = denoise 0.55 / 0.70 / 0.85，canny 强度固定 1.0
    正面 = denoise 0.30 无控制（v23 原样，当身份对照）
    右脸 = 左脸水平翻转（沿用线上 1051 那套「方向硬保证」）

用法：
    python _exp_sdxl_profile.py dry
    python _exp_sdxl_profile.py run
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
MODE = sys.argv[1] if len(sys.argv) > 1 else "dry"
OUTDIR = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "sdxl_profile")

CKPT = "leosamsHelloworldXL_helloworldXL70.safetensors"
CN_CANNY = "SDXL\\t2i-adapter-canny-sdxl-1.0.safetensors"
UPSCALER = "4x-UltraSharp (1).pth"
W, H = 896, 1152
SEED = 20260912
STEPS, CFG = 30, 10.0
BASE_IMG = "wendeng_v23_face_base.png"
CTRL_IMG = "闻灯主图-左侧脸-成品_00045_.png [output]"

# 逐字继承线上组2的正/负向（只改视角词）
POS_A_FRONT = ("front view, looking at viewer, face closeup, head and shoulders, 1boy, solo, "
               "24 year old young adult east asian man, youthful masculine face, youthful facial proportions, "
               "defined but youthful jawline, masculine facial structure, messy wavy black hair, "
               "small dark mole at outer corner of eye, visible eye-corner mole, tired but young eyes, "
               "slightly heavy eyelids, faint under-eye shadows, faded blue shirt collar, dark worn coat collar, "
               "pure white background")
POS_A_SIDE = POS_A_FRONT.replace("front view, looking at viewer",
                                 "side profile view, face centered, true 90 degree side profile, single eye visible")
POS_B = ("detailed face, detailed eyes, clear iris detail, individual eyelashes, natural thick eyebrows, "
         "clean shaven face, youthful natural skin, realistic skin texture, fine skin texture, subtle visible pores, "
         "natural skin imperfections, realistic complexion, natural facial texture, "
         "small dark mole at outer corner of eye, visible mole, clearly defined mole, "
         "messy wavy hair with individual hair strands, faded blue shirt collar, dark worn coat, "
         "pure white background, soft even studio lighting, subtle facial shadows, sharp focus, "
         "realistic skin rendering, photorealistic")
N1 = ("old man, middle aged man, mature man, aged face, elderly, aged appearance, aging skin, deep wrinkles, "
      "forehead wrinkles, deep nasolabial folds, deep eye bags, heavy dark circles, sunken cheeks, gaunt face, "
      "feminine face, feminine features, woman, female, girl, female facial features, delicate feminine features, "
      "overly soft facial features, soft jawline, narrow delicate chin, round feminine face, large feminine eyes, "
      "makeup, lipstick, pretty girl, bishounen, bishoujo, androgynous, gender ambiguous, effeminate")
N2 = ("t-shirt, sweater, business suit, blazer, tie, dress shirt, formal wear, ironed shirt, wool coat, "
      "brown coat, beige coat, blue coat, light coat, new clothes, fashion model, jeans, denim, "
      "bare chest, shirtless, nude, white sneakers, police uniform, wuxia, hanfu")
N3 = ("dark background, grey background, gradient background, vignette, shadow, busy background, full body, "
      "bare shoulders, shirtless, freckles, mole on cheek, mole on forehead, extra fingers, bad hands, "
      "watermark, text, blurry, lowres, airbrushed, over-smoothed, beauty filter, smooth skin, retouched")

VARIANTS = [("正面", 0.30, None), ("侧面d55", 0.55, 1.0), ("侧面d70", 0.70, 1.0), ("侧面d85", 0.85, 1.0)]
# 允许命令行覆盖：  --v "标签:denoise:强度,标签:denoise:强度,..."   强度给 - 表示不用控制
for i, a in enumerate(sys.argv):
    if a == "--v":
        VARIANTS = []
        for spec in sys.argv[i + 1].split(","):
            nm, den, st = spec.split(":")
            VARIANTS.append((nm, float(den), None if st == "-" else float(st)))
for v in VARIANTS:
    print("  variant: %s  denoise=%.2f  control=%s" % v)

# 基图来源：face = v23 已确认正脸（input/）；profile = Kontext 90°侧脸（output/）
BASEMODE = "face"
for i, a in enumerate(sys.argv):
    if a == "--base":
        BASEMODE = sys.argv[i + 1]
    if a == "--img":
        BASE_IMG = sys.argv[i + 1]
print("  基图来源: %s  文件: %s" % (BASEMODE, BASE_IMG))


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


def build():
    A = {}
    A["1"] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}, "_meta": {"title": "SDXL 底模"}}
    A["2"] = {"class_type": "CLIPSetLastLayer", "inputs": {"clip": ["1", 1], "stop_at_clip_layer": -1}, "_meta": {}}
    if BASEMODE == "profile":
        A["3"] = {"class_type": "LoadImageOutput", "inputs": {"image": "闻灯主图-左侧脸-成品_00045_.png [output]"},
                  "_meta": {"title": "★ 基图 = Kontext 90°侧脸（已做对姿势）"}}
    else:
        A["3"] = {"class_type": "LoadImage", "inputs": {"image": BASE_IMG, "upload": "image"},
                  "_meta": {"title": "身份基图 v23 正脸"}}
    A["4"] = {"class_type": "ImageScale", "inputs": {"image": ["3", 0], "upscale_method": "lanczos",
                                                     "width": W, "height": H, "crop": "center"}, "_meta": {}}
    A["5"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["4", 0], "vae": ["1", 2]}, "_meta": {"title": "身份 latent（采样起点）"}}
    # 控制源：Kontext 90° 侧脸 -> 尺寸 -> Canny
    A["6"] = {"class_type": "LoadImageOutput", "inputs": {"image": CTRL_IMG}, "_meta": {"title": "★ 控制源 = Kontext 90° 侧脸"}}
    A["7"] = {"class_type": "ImageScale", "inputs": {"image": ["6", 0], "upscale_method": "lanczos",
                                                     "width": W, "height": H, "crop": "center"}, "_meta": {}}
    A["8"] = {"class_type": "Canny", "inputs": {"image": ["7", 0], "low_threshold": 0.4, "high_threshold": 0.8},
              "_meta": {"title": "Canny 轮廓"}}
    A["9"] = {"class_type": "ControlNetLoader", "inputs": {"control_net_name": CN_CANNY}, "_meta": {"title": "t2i-adapter-canny SDXL"}}
    # 负向三合一
    A["11"] = {"class_type": "CLIPTextEncode", "inputs": {"text": N1, "clip": ["2", 0]}, "_meta": {"title": "负向 N1"}}
    A["12"] = {"class_type": "CLIPTextEncode", "inputs": {"text": N2, "clip": ["2", 0]}, "_meta": {"title": "负向 N2"}}
    A["13"] = {"class_type": "CLIPTextEncode", "inputs": {"text": N3, "clip": ["2", 0]}, "_meta": {"title": "负向 N3"}}
    A["14"] = {"class_type": "ConditioningCombine", "inputs": {"conditioning_1": ["11", 0], "conditioning_2": ["12", 0]}, "_meta": {}}
    A["15"] = {"class_type": "ConditioningCombine", "inputs": {"conditioning_1": ["14", 0], "conditioning_2": ["13", 0]}, "_meta": {"title": "负向合一"}}
    # 正向 B（质感段）
    A["16"] = {"class_type": "CLIPTextEncode", "inputs": {"text": POS_B, "clip": ["2", 0]}, "_meta": {"title": "正向 B 质感"}}
    # 正向 A 两份：正面 / 侧面
    A["17"] = {"class_type": "CLIPTextEncode", "inputs": {"text": POS_A_FRONT, "clip": ["2", 0]}, "_meta": {"title": "正向 A 正面"}}
    A["18"] = {"class_type": "CLIPTextEncode", "inputs": {"text": POS_A_SIDE, "clip": ["2", 0]}, "_meta": {"title": "正向 A 侧面"}}
    A["19"] = {"class_type": "ConditioningCombine", "inputs": {"conditioning_1": ["17", 0], "conditioning_2": ["16", 0]}, "_meta": {"title": "正向 正面 合一"}}
    A["20"] = {"class_type": "ConditioningCombine", "inputs": {"conditioning_1": ["18", 0], "conditioning_2": ["16", 0]}, "_meta": {"title": "正向 侧面 合一"}}
    A["21"] = {"class_type": "UpscaleModelLoader", "inputs": {"model_name": UPSCALER}, "_meta": {}}
    # 顺带把 Canny 图也存出来，便于判断控制源质量
    A["22"] = {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "闻灯SDXL-控制源Canny"}, "_meta": {"title": "存控制源"}}

    roots = ["22"]
    for i, (nm, den, cns) in enumerate(VARIANTS):
        b = 100 + i * 20
        pos = "20" if (cns is not None or BASEMODE == "profile") else "19"
        if cns is not None:
            A[str(b + 6)] = {"class_type": "ControlNetApplyAdvanced",
                             "inputs": {"positive": [pos, 0], "negative": ["15", 0], "control_net": ["9", 0],
                                        "image": ["8", 0], "strength": cns,
                                        "start_percent": 0.0, "end_percent": 1.0},
                             "_meta": {"title": "%s · ControlNet(canny) 强度 %.2f" % (nm, cns)}}
            pos_ref = [str(b + 6), 0]
        else:
            pos_ref = [pos, 0]
        A[str(b)] = {"class_type": "KSampler",
                     "inputs": {"seed": SEED, "steps": STEPS, "cfg": CFG, "sampler_name": "dpmpp_2m",
                                "scheduler": "karras", "denoise": den,
                                "model": ["1", 0], "positive": pos_ref, "negative": ["15", 0],
                                "latent_image": ["5", 0]},
                     "_meta": {"title": "%s · KSampler d%.2f%s" % (nm, den, " +Canny" if cns else "")}}
        A[str(b + 1)] = {"class_type": "VAEDecode", "inputs": {"samples": [str(b), 0], "vae": ["1", 2]}, "_meta": {}}
        A[str(b + 2)] = {"class_type": "SaveImage", "inputs": {"images": [str(b + 1), 0],
                                                              "filename_prefix": "闻灯SDXL-脸部%s-草稿" % nm}, "_meta": {}}
        A[str(b + 3)] = {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["21", 0],
                                                                          "image": [str(b + 1), 0]}, "_meta": {}}
        A[str(b + 4)] = {"class_type": "ImageScaleBy", "inputs": {"upscale_method": "lanczos", "scale_by": 0.5,
                                                                 "image": [str(b + 3), 0]}, "_meta": {}}
        A[str(b + 5)] = {"class_type": "SaveImage", "inputs": {"images": [str(b + 4), 0],
                                                              "filename_prefix": "闻灯SDXL-脸部%s-成品" % nm}, "_meta": {}}
        roots += [str(b + 2), str(b + 5)]
    # 右脸：每个侧脸档的「成品」水平翻转（沿用线上 1051 的「方向硬保证」）
    for i, (nm, den, cns) in enumerate(VARIANTS):
        if cns is None:
            continue
        b = 100 + i * 20
        A[str(900 + i)] = {"class_type": "ImageFlip",
                           "inputs": {"image": [str(b + 4), 0], "flip_method": "y-axis: horizontally"},
                           "_meta": {"title": "右脸 = %s 成品水平翻转" % nm}}
        A[str(910 + i)] = {"class_type": "SaveImage",
                           "inputs": {"images": [str(900 + i), 0],
                                      "filename_prefix": "闻灯SDXL-脸部右脸(%s)-成品" % nm},
                           "_meta": {}}
        roots.append(str(910 + i))
    return A, roots


A, roots = build()
nodes = sorted(roots, key=lambda x: int(x))
print("=== 提交图：%d 节点（%d 个 SaveImage）===" % (len(A), len(roots)))
for k in nodes:
    print("   #%-4s %s" % (k, A[k]["inputs"].get("filename_prefix", "")))

import json as _j
io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_wf", "_last_submit_sdxl_profile.json"),
        "w", encoding="utf-8").write(_j.dumps(A, ensure_ascii=False))
if MODE == "dry":
    print("\n[dry] 未提交。"); sys.exit(0)

print("\n=== 提交 ===")
res = json.loads(raw("/prompt", json.dumps({"prompt": A, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 180).decode())
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:2500]); sys.exit(1)
pid = res["prompt_id"]; print("  prompt_id =", pid)
done = None
for i in range(300):
    time.sleep(3)
    h = json.loads(raw("/history/" + pid, None, None, 60).decode('utf-8', 'replace'))
    if pid in h:
        st = h[pid].get("status", {})
        if st.get("status_str") == "error":
            for m in st.get("messages", []):
                if m[0] == "execution_error":
                    print("★ ERROR %s: %s" % (m[1].get("node_type"), m[1].get("exception_message", "")[:400]))
            sys.exit(1)
        done = h[pid].get("outputs", {}); print("  完成，约 %d 秒" % ((i + 1) * 3)); break
if done is None:
    print("★ 超时"); sys.exit(1)

os.makedirs(OUTDIR, exist_ok=True)
print("\n=== 下载 -> %s ===" % OUTDIR)
n = 0
for nid, o in done.items():
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        p = os.path.join(OUTDIR, im["filename"])
        open(p, "wb").write(raw("/view?" + q, None, None, 300))
        print("  saved %-52s %7.1f KB" % (im["filename"], os.path.getsize(p) / 1024)); n += 1
print("\n共 %d 张 -> %s" % (n, OUTDIR))
