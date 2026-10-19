# -*- coding: utf-8 -*-
"""闻灯 v22 —— 无服饰版：脸部（正/侧）+ 上半身（正/侧/背）

用户要求（2026-09-17）：
    1. 脸部图、上半身图都不要服饰（服饰后面单独叠加）
    2. 上半身要能看到肌肉结构；下半身给白色短裤
    3. 脸部要像 v13 那张已确认的正脸（v21 漂移成"另一个人 + 商务感"，作废）

v21 翻车复盘（本版逐条修正）：
    × 加了 `90 degree side view / single eye visible / face turned to` 等强方位词
      -> 画面被推成超大特写，面部结构被重构  => 本版回到 v13 的 `face closeup, head and shoulders`
    × 负向堆砌种族词（caucasian/european/western/african/indian/...）
      -> 挤占 token 且把脸推向"更柔和的东亚"  => 本版完全不堆种族词，只留 east asian 正向
    × 负向加了 `freckles, mole on cheek`
      -> v13 的雀斑/痣群正是真实感来源，被当成缺陷压掉  => 本版移除
    × 误以为"同 seed + 同 token = 同一个人"
      -> 提示词一变，同一 seed 出来就是另一个人。侧脸真要同一个人只能靠
         img2img 或镜像（镜像方案见 make_face_set.py）

用法： python gen_wendeng_v22.py [TAG] [SEED] [--check]
"""
import urllib.request, urllib.parse, json, ssl, time, uuid, os, sys

BASE = "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016"
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
OUTDIR = r"D:\xiaobai-claude code\comfyUImd\系列-夜市百相簿/02-角色/闻灯/设定图\v22-无服饰"

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
CHECK = "--check" in sys.argv
TAG = ARGS[0] if len(ARGS) > 0 else "v22"
SEED = int(ARGS[1]) if len(ARGS) > 1 else 20260916

CKPT = "leosamsHelloworldXL_helloworldXL70.safetensors"
UPSCALER = "4x-UltraSharp (1).pth"
W, H = 896, 1152
SCALE_BY = 0.5
STEPS_1, CFG_1 = 30, 10.0
STEPS_2, CFG_2, DEN_2 = 20, 10.0, 0.25

# ================== 角色基准块 ==================
# 逐字继承 v13 已确认面部的那组 token，只把「服饰」整段替换为无服饰描述
BGD = "pure white background"
HAIR = "messy wavy black hair"                    # 锚点：黑发微卷
MOLE = "small mole at outer eye corner"           # 锚点：眼尾一颗小痣
BARE = "bare shoulders, bare neck, collarbone visible"   # 无服饰（脸部）
BARE_TORSO = "bare torso, no shirt, bare chest, visible collarbone and chest muscles"

FACE_A = ("face closeup, head and shoulders, 1boy, solo, 24 year old east asian man, "
          "masculine face, strong jaw, " + HAIR + ", " + MOLE + ", " + BARE + ", " + BGD)

FACE_B = ("detailed face, detailed eyes, dark circles under eyes, iris detail, "
          "thick eyebrows, stubble, " + MOLE + ", visible skin pores, "
          "skin texture, peach fuzz, wavy black hair, individual hair strands, "
          + BARE + ", plain " + BGD + ", flat even lighting, sharp focus, photorealistic")

UPPER_A = ("upper body shot, waist up, 1boy, solo, 24 year old east asian man, "
           "masculine face, strong jaw, " + HAIR + ", " + MOLE + ", "
           + BARE_TORSO + ", lean wiry build, white shorts, " + BGD)

UPPER_B = ("1boy, male, lean wiry build, broad shoulders, defined pectorals, toned stomach, "
           "visible muscle definition, detailed skin texture, skin pores, film grain, "
           "white shorts, " + BGD + ", flat even lighting, sharp focus, photorealistic")

# ================== 负向 ==================
N1 = ("1girl, female, feminine face, delicate, fragile, soft features, soft round face, "
      "pretty boy, boyish face, bishounen, makeup, lipstick, rosy lips, eyeshadow, "
      "teenage, child, narrow face, pale skin, blonde hair, long hair, straight hair, "
      "slicked back hair, undercut, side part, neat hair")

# 服装/商务感压制（本版核心：既要压旧衣服，又不能把裸露压掉）
N2 = ("clothing, shirt, t-shirt, collared shirt, sweater, coat, jacket, trench coat, "
      "blazer, business suit, formal wear, tie, uniform, fashion model, fabric folds, "
      "bulky, bodybuilder, muscular hunk, jeans, denim, nsfw, explicit, sexual, genitals")

N3_FACE = ("dark background, grey background, gradient background, vignette, shadow, "
           "busy background, full body, body shot, extra fingers, bad hands, watermark, text, "
           "blurry, lowres, airbrushed, over-smoothed, beauty filter, smooth skin, retouched, "
           "looking away, closed eyes, three quarter view")

N3_UPPER = ("close-up, cropped, hands in pockets, hands hidden, arms crossed, contrapposto, "
            "wide stance, legs apart, walking, leaning, extra fingers, bad hands, watermark, text, "
            "blurry, lowres, busy background, dark background, "
            "airbrushed, over-smoothed, clothing, shirt, coat")

# ================== 五个视角 ==================
VIEWS = [
    # 脸部：构图沿用 v13（不带任何强方位词，那是 v21 漂移的元凶）
    ("脸部正面",
     "face closeup, head and shoulders, front view, looking at viewer, " + FACE_A,
     FACE_B, N3_FACE),

    ("脸部侧面",
     "side profile view, " + FACE_A,
     FACE_B, N3_FACE),

    # 上半身：无服饰 + 白短裤
    ("上半身正面",
     "upper body shot, front view, " + UPPER_A,
     "front view, " + UPPER_B, N3_UPPER),

    ("上半身侧面",
     "upper body shot, side view, " + UPPER_A,
     "side view, " + UPPER_B, N3_UPPER),

    ("上半身背面",
     "upper body shot, back view, " + UPPER_A,
     "back view, " + UPPER_B, N3_UPPER),
]

# ================== token 校验 ==================
sys.path.insert(0, r"D:\xiaobai-claude code\ComfyUI\venv\Lib\site-packages")
from transformers import CLIPTokenizer
tk = CLIPTokenizer.from_pretrained(r"D:\xiaobai-claude code\ComfyUI\comfy\sd1_tokenizer")


def tok(t):
    return len(tk.encode(t, add_special_tokens=False))


bad = []
print("=== token 校验（上限 75）===")
for nm, t in [("N1", N1), ("N2", N2), ("N3脸部", N3_FACE), ("N3上半身", N3_UPPER),
              ("FACE_B", FACE_B), ("UPPER_B", UPPER_B)]:
    n = tok(t)
    print("  %-10s %3d/75 %s" % (nm, n, "OK" if n <= 75 else "★超限★"))
    if n > 75:
        bad.append(nm)
for vn, a, b, n3 in VIEWS:
    for nm, s in [("A", a), ("B", b)]:
        n = tok(s)
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


def build(A, B, N3, vn):
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
        "20": {"class_type": "SaveImage", "inputs": {"filename_prefix": "闻灯%s-%s-草稿" % (TAG, vn),
                                                     "images": ["13", 0]}},
        "21": {"class_type": "SaveImage", "inputs": {"filename_prefix": "闻灯%s-%s-成品" % (TAG, vn),
                                                     "images": ["19", 0]}},
    }


def post(p, pl):
    r = urllib.request.Request(BASE + p, data=json.dumps(pl).encode("utf-8"),
                               headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=60, context=ctx).read().decode())


def get(p):
    return urllib.request.urlopen(BASE + p, timeout=60, context=ctx).read()


print("\n底模: %s | %dx%d | seed=%d（沿用 v13）" % (CKPT, W, H, SEED))
print("★ 本版：脸部/上半身均无服饰；构图回退到 v13 写法\n")

jobs = []
for vn, A, B, N3 in VIEWS:
    pid = post("/prompt", {"prompt": build(A, B, N3, vn), "client_id": str(uuid.uuid4())})["prompt_id"]
    jobs.append((vn, pid))
    print("submitted %-10s -> %s" % (vn, pid))

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
                print("  %s ERROR: %s" % (vn, json.dumps(h[pid]["status"], ensure_ascii=False)[:700]))
                done[vn] = None
            else:
                done[vn] = h[pid].get("outputs", {})
                print("  %s 完成 (%.0fs)" % (vn, (i + 1) * 3))
    if len(done) == len(jobs):
        break

os.makedirs(OUTDIR, exist_ok=True)
print("\n=== 下载 -> %s ===" % OUTDIR)
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
