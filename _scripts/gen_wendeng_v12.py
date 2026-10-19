# -*- coding: utf-8 -*-
"""闻灯多视角角色设定图 v12 —— SDXL (LEOSAM's HelloWorld XL 7.0) 版
与 v11 的关键差异：
  1) 底模换 SDXL：896x1152 原生竖构图（官方推荐），CFG 10、steps 30、DPM++ 2M Karras
  2) CLIP skip 由 2 改 1（SDXL 规范）-> 新增 CLIPSetLastLayer(stop_at_clip_layer=-1)
  3) 放大链路换 ESRGAN：UpscaleModelLoader(4x-UltraSharp) + ImageUpscaleWithModel
     + ImageScaleBy(0.5) -> VAEEncode -> KSampler(denoise .25) 低重绘
     替代只会等比放大的 LatentUpscale（后者不产生任何新细节）
  4) 需求：全身正/侧/背 + 脸部正/侧，共 5 视角，纯白背景，强调脸部与头发细节
用法： python gen_wendeng_v12.py [TAG] [SEED] [--check]
      --check 只做 token 校验与构图打印，不提交
"""
import urllib.request, urllib.parse, json, ssl, time, uuid, os, sys

BASE = "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016"
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
OUTDIR = r"D:\xiaobai-claude code\comfyUImd\系列-夜市百相簿/02-角色/闻灯/设定图\多视角"
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
CHECK = "--check" in sys.argv
TAG = ARGS[0] if len(ARGS) > 0 else "v12"
SEED = int(ARGS[1]) if len(ARGS) > 1 else 20260916

CKPT = "leosamsHelloworldXL_helloworldXL70.safetensors"
UPSCALER = "4x-UltraSharp (1).pth"
W, H = 896, 1152            # HelloWorld XL 官方推荐竖构图
SCALE_BY = 0.5              # 4x 放大后回缩 -> 最终 1792x2304
STEPS_1, CFG_1 = 30, 10.0   # HelloWorld 官方推荐 CFG 10
STEPS_2, CFG_2, DEN_2 = 20, 10.0, 0.25

# ---------------- 人物锚点 ----------------
# A 段：构图 / 姿势 / 身份 / 服装 / 背景（权重最高，必须顶在最前）
# B 段：五官 / 质感 / 服装复述 / 光照
BGD = "pure white background"
STAND = "standing straight, arms at sides, feet together"
BODY_A = ("1boy, solo, 24 year old east asian man, masculine, short black hair, "
          "blue button up shirt, dark worn trench coat")
BODY_B = ("1boy, male, deep set eyes, thick eyebrows, stubble, weathered skin, "
          "detailed skin texture, skin pores, film grain, blue shirt, dark long coat, "
          "dark trousers, old shoes, fully clothed, " + BGD + ", flat even lighting, "
          "sharp focus, photorealistic")
FACE_HEAD_A = ("face closeup, head and shoulders, 1boy, solo, 24 year old east asian man, "
               "masculine face, strong jaw, short black hair, blue shirt collar, dark coat collar")
FACE_B = ("detailed face, detailed eyes, iris detail, individual eyelashes, thick eyebrows, "
          "stubble, visible skin pores, skin texture, peach fuzz, detailed hair, "
          "individual hair strands, blue shirt collar, dark coat collar, " + BGD + ", "
          "flat even lighting, sharp focus, photorealistic")

# ---------------- 负向 ----------------
N1 = ("1girl, female, woman, girl, feminine face, effeminate, delicate, fragile, "
      "soft features, soft round face, pretty boy, boyish face, bishounen, makeup, lipstick, "
      "rosy lips, eyeshadow, teenage, child, bulky, bodybuilder, blonde hair, long hair, "
      "curly hair, slim skinny, narrow face, pale skin")
N2 = ("white t-shirt, t-shirt, v-neck, sweater, knitwear, suit, blazer, vest, waistcoat, tie, "
      "wool coat, brown coat, beige coat, new coat, fashion model, lookbook, jeans, denim, "
      "bare chest, shirtless, nude, topless, police uniform, wuxia, hanfu")
N3_FULL = ("close-up, cropped, hands in pockets, hands on hips, arms crossed, "
           "contrapposto, wide stance, legs apart, walking, leaning, "
           "extra fingers, bad hands, watermark, text, blurry, lowres, busy background, "
           "grey background, dark background, gradient background, vignette, shadow, "
           "airbrushed, over-smoothed")
N3_FACE = ("dark background, grey background, gray background, gradient background, vignette, "
           "shadow, busy background, full body, bare shoulders, shirtless, extra fingers, "
           "bad hands, watermark, text, blurry, lowres, airbrushed, over-smoothed, beauty filter")

# ---------------- 五个视角 ----------------
VIEWS = [
    ("全身正面",
     "full body shot, head to toe, front view, " + STAND + ", " + BODY_A + ", " + BGD,
     "front view, " + STAND + ", " + BODY_B,
     N3_FULL),

    ("全身侧面",
     "full body shot, head to toe, side view, profile, facing left, " + STAND + ", " + BODY_A + ", " + BGD,
     "side view, profile, " + STAND + ", " + BODY_B,
     N3_FULL),

    ("全身背面",
     "full body shot, head to toe, back view, from behind, " + STAND + ", " + BODY_A + ", " + BGD,
     "back view, " + STAND + ", " + BODY_B,
     N3_FULL),

    ("脸部正面",
     "front view, looking at viewer, " + FACE_HEAD_A + ", " + BGD,
     FACE_B,
     N3_FACE),

    ("脸部侧面",
     "side profile view, " + FACE_HEAD_A + ", " + BGD,
     FACE_B,
     N3_FACE),
]

# ---------------- token 校验（SDXL 的 CLIP-L 与 SD1.5 同一 tokenizer，上限同为 75）----------------
sys.path.insert(0, r"D:\xiaobai-claude code\ComfyUI\venv\Lib\site-packages")
from transformers import CLIPTokenizer
tk = CLIPTokenizer.from_pretrained(r"D:\xiaobai-claude code\ComfyUI\comfy\sd1_tokenizer")


def tok(t):
    return len(tk.encode(t, add_special_tokens=False))


bad = []
print("=== token 校验（上限 75）===")
for nm, t in [("N1", N1), ("N2", N2), ("N3全身", N3_FULL), ("N3脸部", N3_FACE)]:
    n = tok(t)
    print("  %-10s %3d/75 %s" % (nm, n, "OK" if n <= 75 else "★超限★"))
    if n > 75:
        bad.append(nm)
for vn, a, b, _ in VIEWS:
    for nm, t in [("A", a), ("B", b)]:
        n = tok(t)
        print("  %-10s %-3s %3d/75 %s" % (vn, nm, n, "OK" if n <= 75 else "★超限★"))
        if n > 75:
            bad.append(vn + nm)
if bad:
    print("\n★ 有段落超限，未提交：", bad)
    sys.exit(1)
print("\n全部在 75 以内")
if CHECK:
    sys.exit(0)

# ---------------- 构图 ----------------
CLIP = ["2", 0]


def build(prefix, A, B, N3):
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        # SDXL 规范：clip skip 1 = 用最后一层（-1）
        "2": {"class_type": "CLIPSetLastLayer", "inputs": {"clip": ["1", 1], "stop_at_clip_layer": -1}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": A, "clip": CLIP}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": B, "clip": CLIP}},
        "5": {"class_type": "ConditioningCombine", "inputs": {"conditioning_1": ["3", 0], "conditioning_2": ["4", 0]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": N1, "clip": CLIP}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": N2, "clip": CLIP}},
        "8": {"class_type": "CLIPTextEncode", "inputs": {"text": N3, "clip": CLIP}},
        "9": {"class_type": "ConditioningCombine", "inputs": {"conditioning_1": ["6", 0], "conditioning_2": ["7", 0]}},
        "10": {"class_type": "ConditioningCombine", "inputs": {"conditioning_1": ["9", 0], "conditioning_2": ["8", 0]}},
        "11": {"class_type": "EmptyLatentImage", "inputs": {"width": W, "height": H, "batch_size": 1}},
        "12": {"class_type": "KSampler", "inputs": {"seed": SEED, "steps": STEPS_1, "cfg": CFG_1,
                                                    "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0,
                                                    "model": ["1", 0], "positive": ["5", 0],
                                                    "negative": ["10", 0], "latent_image": ["11", 0]}},
        "13": {"class_type": "VAEDecode", "inputs": {"samples": ["12", 0], "vae": ["1", 2]}},
        # --- ESRGAN 放大链路（真正增加细节的部分）---
        "14": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": UPSCALER}},
        "15": {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["14", 0], "image": ["13", 0]}},
        "16": {"class_type": "ImageScaleBy", "inputs": {"upscale_method": "lanczos", "scale_by": SCALE_BY,
                                                        "image": ["15", 0]}},
        "17": {"class_type": "VAEEncode", "inputs": {"pixels": ["16", 0], "vae": ["1", 2]}},
        "18": {"class_type": "KSampler", "inputs": {"seed": SEED, "steps": STEPS_2, "cfg": CFG_2,
                                                    "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": DEN_2,
                                                    "model": ["1", 0], "positive": ["5", 0],
                                                    "negative": ["10", 0], "latent_image": ["17", 0]}},
        "19": {"class_type": "VAEDecode", "inputs": {"samples": ["18", 0], "vae": ["1", 2]}},
        "20": {"class_type": "SaveImage", "inputs": {"filename_prefix": "闻灯%s-%s-草稿" % (TAG, prefix),
                                                     "images": ["13", 0]}},
        "21": {"class_type": "SaveImage", "inputs": {"filename_prefix": "闻灯%s-%s-成品" % (TAG, prefix),
                                                     "images": ["19", 0]}},
    }


def post(p, pl):
    r = urllib.request.Request(BASE + p, data=json.dumps(pl).encode("utf-8"),
                               headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=60, context=ctx).read().decode())


def get(p):
    return urllib.request.urlopen(BASE + p, timeout=60, context=ctx).read()


print("\n底模: %s\n分辨率: %dx%d -> 成品 %dx%d\n" % (CKPT, W, H, int(W * 4 * SCALE_BY), int(H * 4 * SCALE_BY)))

jobs = []
for vn, A, B, N3 in VIEWS:
    pid = post("/prompt", {"prompt": build(vn, A, B, N3), "client_id": str(uuid.uuid4())})["prompt_id"]
    jobs.append((vn, pid))
    print("submitted %-8s -> %s" % (vn, pid))

print("\n等待生成...")
done = {}
for i in range(400):
    time.sleep(3)
    for vn, pid in jobs:
        if vn in done:
            continue
        h = json.loads(get("/history/" + pid).decode("utf-8", "replace"))
        if pid in h:
            st = h[pid].get("status", {}).get("status_str")
            if st == "error":
                print("  %s ERROR: %s" % (vn, json.dumps(h[pid]["status"], ensure_ascii=False)[:800]))
                done[vn] = None
            else:
                done[vn] = h[pid].get("outputs", {})
                print("  %s 完成 (%.0fs)" % (vn, (i + 1) * 3))
    if len(done) == len(jobs):
        break

os.makedirs(OUTDIR, exist_ok=True)
print("\n=== 下载 ===")
for vn, outs in done.items():
    if not outs:
        continue
    for nid, o in outs.items():
        for im in o.get("images", []):
            q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                        "type": im.get("type", "output")})
            dst = os.path.join(OUTDIR, im["filename"])
            open(dst, "wb").write(get("/view?" + q))
            print("  saved %-46s %8.1f KB" % (im["filename"], os.path.getsize(dst) / 1024))
print("\nOK")
