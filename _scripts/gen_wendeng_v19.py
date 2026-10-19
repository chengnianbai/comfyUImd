# -*- coding: utf-8 -*-
"""闻灯角色设定图 v19 —— 两阶段出图（先脸后身）

工作流规则（用户 2026-09-17 定）：
    ① 先出「脸部正面 + 脸部侧面」，确认这个人没问题；
    ② 再把同一组角色 token + 同一 seed 复用进全身图，出「全身正/侧/背」。
这样才不会出现"脸是成年男人、全身是少年"的脱节。

角色基准（= v13 脸部已确认版本，见《角色视觉锚点-锁定.md》）
    24 year old east asian man / masculine face, strong jaw / messy wavy black hair
    / small mole at outer eye corner / faded blue shirt / dark worn trench coat

用法： python gen_wendeng_v19.py [TAG] [SEED] [--face|--body|--all] [--check]
     默认 --all；--check 只做 token 校验不提交
"""
import urllib.request, urllib.parse, json, ssl, time, uuid, os, sys

BASE = "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016"
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
OUTDIR = r"D:\xiaobai-claude code\comfyUImd\系列-夜市百相簿/02-角色/闻灯/设定图\多视角"

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
CHECK = "--check" in sys.argv
STAGE = "face" if "--face" in sys.argv else ("body" if "--body" in sys.argv else "all")
TAG = ARGS[0] if len(ARGS) > 0 else "v19"
SEED = int(ARGS[1]) if len(ARGS) > 1 else 20260916

CKPT = "leosamsHelloworldXL_helloworldXL70.safetensors"
UPSCALER = "4x-UltraSharp (1).pth"
W, H = 896, 1152
SCALE_BY = 0.5
STEPS_1, CFG_1 = 30, 10.0
STEPS_2, CFG_2, DEN_2 = 20, 10.0, 0.25

# ============ 角色基准块（脸部与全身共用同一组 token，保证是同一个人）============
BGD = "pure white background"
HAIR = "messy wavy black hair"              # 锚点 #4 黑发微卷（v13 脸部已确认的写法）
MOLE = "small mole at outer eye corner"     # 锚点 #5 眼尾一颗小痣
COAT = "dark worn trench coat"              # 锚点 #9 深色旧风衣（不锁色相）
SHIRT = "faded blue shirt"                  # 锚点 #8 洗得发白的蓝色旧衬衫
CHAR = "1boy, solo, 24 year old east asian man, masculine face, strong jaw, " + HAIR

# ============ 阶段一：脸部（v13 已确认，此处原样锁定）============
FACE_A = "face closeup, head and shoulders, " + CHAR + ", " + MOLE + ", " + SHIRT + " collar, dark coat collar, " + BGD
FACE_B = ("detailed face, detailed eyes, dark circles under eyes, iris detail, individual eyelashes, "
          "thick eyebrows, stubble, " + MOLE + ", visible skin pores, skin texture, skin imperfections, "
          "peach fuzz, messy wavy hair, individual hair strands, faded shirt collar, dark coat, "
          + BGD + ", flat even lighting, sharp focus, photorealistic")

# ============ 阶段二：全身（复用同一 CHAR 块 + 同 seed）============
STAND_A = "standing straight, arms down at sides, hands visible"
STAND_B = "arms down at sides, hands visible"
BODY_A = ("full body shot, head to toe, %s, " + STAND_A + ", " + CHAR + ", " + MOLE + ", "
          + SHIRT + ", " + COAT + ", open coat, " + BGD)
BODY_B = ("1boy, wavy tousled hair, tired eyes, thick eyebrows, stubble, weathered skin, "
          "detailed skin texture, skin pores, film grain, worn wrinkled clothes, dark trousers, "
          "old worn shoes, " + STAND_B + ", " + BGD + ", even lighting, sharp focus, photorealistic")

# ============ 负向 ============
N1 = ("1girl, female, feminine face, delicate, fragile, soft features, soft round face, "
      "pretty boy, boyish face, bishounen, makeup, lipstick, rosy lips, eyeshadow, "
      "teenage, child, narrow face, pale skin, blonde hair, straight hair, "
      "slicked back hair, undercut, side part, neat hair")
N2 = ("t-shirt, sweater, business suit, blazer, tie, dress shirt, formal wear, "
      "ironed shirt, wool coat, brown coat, beige coat, blue coat, light coat, "
      "new clothes, fashion model, jeans, denim, bare chest, shirtless, nude, "
      "white sneakers, new shoes, police uniform, wuxia, hanfu")
N3_FULL = ("hands in pockets, hands behind back, hands hidden, holding object, prop, "
           "contrapposto, wide stance, legs apart, pockets, "
           "extra fingers, bad hands, watermark, text, blurry, lowres, busy background, "
           "grey background, dark background, gradient background, vignette, shadow, "
           "airbrushed, over-smoothed")
N3_FACE = ("dark background, grey background, gradient background, vignette, shadow, "
           "busy background, full body, bare shoulders, shirtless, freckles, mole on cheek, mole on forehead, "
           "extra fingers, bad hands, watermark, text, blurry, lowres, airbrushed, "
           "over-smoothed, beauty filter, smooth skin, retouched")

# ============ 视角 ============
VIEWS = [
    ("脸部正面", "front view, looking at viewer, " + FACE_A, FACE_B, N3_FACE, "face"),
    ("脸部侧面", "side profile view, " + FACE_A, FACE_B, N3_FACE, "face"),
    ("全身正面", BODY_A % "front view", "front view, " + STAND_B + ", " + BODY_B, N3_FULL, "body"),
    ("全身侧面", BODY_A % "side view",  "side view, " + STAND_B + ", " + BODY_B, N3_FULL, "body"),
    ("全身背面", BODY_A % "back view",  "back view, " + STAND_B + ", " + BODY_B, N3_FULL, "body"),
]

# ============ token 校验 ============
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
for vn, a, b, _, st in VIEWS:
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

CLIP = ["2", 0]


def build(prefix, A, B, N3):
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
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


todo = [v for v in VIEWS if STAGE == "all" or v[4] == STAGE]
print("\n阶段: %s | 底模: %s\n分辨率: %dx%d -> 成品 %dx%d | seed=%d\n"
      % (STAGE, CKPT, W, H, int(W * 4 * SCALE_BY), int(H * 4 * SCALE_BY), SEED))

jobs = []
for vn, A, B, N3, _ in todo:
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
