# -*- coding: utf-8 -*-
"""闻灯多视角角色设定图 v18 —— 对照《角色视觉锚点-锁定.md》逐条回锚点

v13、v14 偏差 -> v15 修正：
  1) 发型：v13 写 "messy wavy black hair" 漏了 short -> 出中长蓬乱卷发
     锚点原文是「黑发微卷」-> 改 "short black hair, slightly wavy"
  2) 眼尾痣：v13 把 MOLE 复述两段（双倍权重）-> 出满脸痣
     锚点原文是「眼尾固定有**一颗**小痣」-> 只在脸部 A 段写一次，负向压 freckles
  3) 风衣：v13 的 "dark worn trench coat" 里 dark 太弱 -> SDXL 把 faded blue 的蓝色
     挪去画风衣，出成浅蓝大风衣、衬衫反成白 T
     锚点原文「深色旧风衣」-> dark 具体化为 charcoal（深炭灰，仍属"深色"范畴）
  4) 鞋：v13 精简时误删 -> 锚点「便于湿地行走的旧鞋」-> 补 "old worn shoes"
v15 追加修正：
  5) 衬衫：v14 的 "faded blue shirt" 出成圆领 T 恤 -> 锚点是「蓝色旧**衬衫**」
     改 "faded blue collared shirt"（明确有领）
  6) 姿势：v14 仍手插兜 -> STAND 补 "hands at sides"；负向保留 hands in pockets
  7) 皮肤：v14 的负向 many moles 把毛孔一起压掉 -> 改定点压 mole on cheek/forehead
v18 修正（用户指令：道具不属于角色设定图）：
  1) 去掉 holding ledger / hands in front —— 账簿、朱砂粉盒等道具后续单独生成，
     不进入角色 5 视角设定图（锚点 #12 相应降级为"道具，另片生成"）
  2) 手插兜在 v16/v17 都没压住 -> 改「空手自然垂在身侧 + 禁止把手藏起来」双管
  3) 补回 v17 漏掉的体型锚点 #3（lean wiry build, broad shoulders）
  4) 负向补 holding object / tucking hand，防止模型自己"造"道具
用法： python gen_wendeng_v18.py [TAG] [SEED] [--check]
"""
import urllib.request, urllib.parse, json, ssl, time, uuid, os, sys

BASE = "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016"
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
OUTDIR = r"D:\xiaobai-claude code\comfyUImd\系列-夜市百相簿/02-角色/闻灯/设定图\多视角"
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
CHECK = "--check" in sys.argv
TAG = ARGS[0] if len(ARGS) > 0 else "v18"
SEED = int(ARGS[1]) if len(ARGS) > 1 else 20260916

CKPT = "leosamsHelloworldXL_helloworldXL70.safetensors"
UPSCALER = "4x-UltraSharp (1).pth"
W, H = 896, 1152
SCALE_BY = 0.5
STEPS_1, CFG_1 = 30, 10.0
STEPS_2, CFG_2, DEN_2 = 20, 10.0, 0.25

# ---------------- 锚点（严格对应《角色视觉锚点-锁定.md》）----------------
BGD = "pure white background"
STAND = ("standing straight, arms hanging down at sides, empty hands, hands visible, "
         "feet together, no pockets")
# B 段用的精简姿势串（A+B 都写姿势 = 双倍权重；B 段篇幅有限，只留核心的"手在身侧可见"）
STAND_B = "standing straight, arms down at sides, hands visible"
HAIR = "short black hair, slightly wavy"           # 锚点 #4 黑发微卷
COAT = "dark charcoal worn trench coat"            # 锚点 #9 深色旧风衣
MOLE = "small mole at outer eye corner"            # 锚点 #5 眼尾一颗小痣

BODY_A = ("1boy, 24 year old east asian man, masculine face, strong jaw, " + HAIR + ", "
          "faded blue collared shirt, " + COAT + ", open coat")
BODY_B = ("1boy, lean wiry build, broad shoulders, tired eyes, thick eyebrows, stubble, "
          "detailed skin texture, film grain, open coat, dark trousers, old worn shoes, "
          + BGD + ", sharp focus, photorealistic")

FACE_HEAD_A = ("face closeup, head and shoulders, 1boy, solo, 24 year old east asian man, "
               "masculine face, strong jaw, " + HAIR + ", " + MOLE + ", "
               "faded blue shirt collar, dark coat collar")
FACE_B = ("detailed face, detailed eyes, dark circles under eyes, iris detail, individual eyelashes, "
          "thick eyebrows, stubble, visible skin pores, skin texture, skin imperfections, "
          "peach fuzz, short tousled hair, individual hair strands, faded shirt collar, dark coat, "
          + BGD + ", flat even lighting, sharp focus, photorealistic")

# ---------------- 负向 ----------------
N1 = ("1girl, female, feminine face, delicate, fragile, soft features, soft round face, "
      "pretty boy, boyish face, bishounen, makeup, lipstick, rosy lips, eyeshadow, "
      "teenage, child, narrow face, pale skin, blonde hair, long hair, straight hair, "
      "slicked back hair, undercut, side part, neat hair, medium length hair")
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

# ---------------- 五个视角 ----------------
VIEWS = [
    ("全身正面",
     "full body shot, head to toe, front view, " + STAND + ", " + BODY_A + ", " + BGD,
     "front view, " + STAND_B + ", " + BODY_B, N3_FULL),
    ("全身侧面",
     "full body shot, head to toe, side view, " + STAND + ", " + BODY_A + ", " + BGD,
     "side view, " + STAND_B + ", " + BODY_B, N3_FULL),
    ("全身背面",
     "full body shot, head to toe, back view, " + STAND + ", " + BODY_A + ", " + BGD,
     "back view, " + STAND_B + ", " + BODY_B, N3_FULL),
    ("脸部正面",
     "front view, looking at viewer, " + FACE_HEAD_A + ", " + BGD,
     FACE_B, N3_FACE),
    ("脸部侧面",
     "side profile view, " + FACE_HEAD_A + ", " + BGD,
     FACE_B, N3_FACE),
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
