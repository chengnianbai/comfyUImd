# -*- coding: utf-8 -*-
"""闻灯多视角角色设定图 v13 —— 修 v12 的三个问题
  1) 头发：v12 漏了「微卷」-> 出成商务背头/undercut。
     新增 HAIR = "messy wavy black hair"，并在 B 段复述做双倍权重；
     负向压 slicked back hair / undercut / side part / neat hair / straight hair
  2) 商务感：v12 的 "blue button up shirt + dark worn trench coat" 被 SDXL
     理解成「衬衫+外套=正装」，蓝色还被挪用去画西装。
     改为 faded blue shirt + old dark grey trench coat（锁死风衣颜色），
     并加 worn / wrinkled / open coat 强化「旧」；负向补 business suit / blazer /
     dress shirt / ironed shirt / crisp shirt / formal wear
  3) 磨皮：加 tired eyes / dark circles / uneven skin tone / skin imperfections，
     负向补 smooth skin / beauty filter / retouched
  4) 纯白背景：SDXL 对 pure white background 只给浅灰 -> 生成后另跑白场校正后处理
用法： python gen_wendeng_v13.py [TAG] [SEED] [--check]
"""
import urllib.request, urllib.parse, json, ssl, time, uuid, os, sys

BASE = "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016"
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
OUTDIR = r"D:\xiaobai-claude code\comfyUImd\系列-夜市百相簿/02-角色/闻灯/设定图\多视角"
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
CHECK = "--check" in sys.argv
TAG = ARGS[0] if len(ARGS) > 0 else "v13"
SEED = int(ARGS[1]) if len(ARGS) > 1 else 20260916

CKPT = "leosamsHelloworldXL_helloworldXL70.safetensors"
UPSCALER = "4x-UltraSharp (1).pth"
W, H = 896, 1152
SCALE_BY = 0.5
STEPS_1, CFG_1 = 30, 10.0
STEPS_2, CFG_2, DEN_2 = 20, 10.0, 0.25

# ---------------- 锚点 ----------------
BGD = "pure white background"
STAND = "standing straight, arms at sides, feet together"
HAIR = "messy wavy black hair"
COAT = "dark worn trench coat"   # 锚点：档案只写「深色旧风衣」，不要锁具体色相（写 dark grey 属擅自加戏）
MOLE = "small mole at outer eye corner"   # 锚点 #5：眼尾固定有一颗小痣（脸部图必保留）

BODY_A = ("1boy, solo, 24 year old east asian man, masculine, " + HAIR + ", "
          "faded blue shirt, " + COAT)
BODY_B = ("1boy, male, wavy tousled hair, tired eyes, thick eyebrows, stubble, "
          "weathered skin, detailed skin texture, skin pores, film grain, "
          "worn wrinkled clothes, open coat, dark trousers, " + BGD + ", even lighting, "
          "sharp focus, photorealistic")

FACE_HEAD_A = ("face closeup, head and shoulders, 1boy, solo, 24 year old east asian man, "
               "masculine face, strong jaw, " + HAIR + ", " + MOLE + ", "
               "faded blue shirt collar, dark coat collar")
FACE_B = ("detailed face, detailed eyes, dark circles under eyes, iris detail, individual eyelashes, "
          "thick eyebrows, stubble, " + MOLE + ", visible skin pores, skin texture, skin imperfections, "
          "peach fuzz, messy wavy hair, individual hair strands, faded shirt collar, dark coat, "
          + BGD + ", flat even lighting, sharp focus, photorealistic")

# ---------------- 负向 ----------------
N1 = ("1girl, female, feminine face, delicate, fragile, soft features, soft round face, "
      "pretty boy, boyish face, bishounen, makeup, lipstick, rosy lips, eyeshadow, "
      "teenage, child, narrow face, pale skin, blonde hair, long hair, straight hair, "
      "slicked back hair, undercut, side part, neat hair")
N2 = ("t-shirt, v-neck, sweater, knitwear, business suit, blazer, waistcoat, tie, "
      "dress shirt, formal wear, crisp shirt, ironed shirt, wool coat, "
      "brown coat, beige coat, new clothes, fashion model, jeans, denim, bare chest, "
      "shirtless, nude, police uniform, wuxia, hanfu")
N3_FULL = ("close-up, cropped, hands in pockets, hands on hips, arms crossed, "
           "contrapposto, wide stance, legs apart, walking, leaning, "
           "extra fingers, bad hands, watermark, text, blurry, lowres, busy background, "
           "grey background, dark background, gradient background, vignette, shadow, "
           "airbrushed, over-smoothed")
N3_FACE = ("dark background, grey background, gray background, gradient background, vignette, "
           "shadow, busy background, full body, bare shoulders, shirtless, extra fingers, "
           "bad hands, watermark, text, blurry, lowres, airbrushed, over-smoothed, "
           "beauty filter, smooth skin, retouched")

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

# ---------------- token 校验 ----------------
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
