# -*- coding: utf-8 -*-
"""闻灯多视角角色设定图 v11
针对 v10 的三个问题：
  1) 背景仍是深蓝灰 -> 换 high key lighting（高调照明，专指背景纯白的打光），
     并去掉可疑的 soft even lighting；负向加 dark/blue/grey background
  2) 姿势仍是手插兜 -> 正向加 hands at sides / feet together，负向补 hands in pockets 等复数形式
  3) 脸部彻底女性化 -> 极端反柔弱：masculine 词提前 + B 段复述做双倍权重；脸部图加服装防裸肩
"""
import urllib.request, urllib.parse, json, ssl, time, uuid, os, sys

BASE = "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016"
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
OUTDIR = r"D:\xiaobai-claude code\comfyUImd\系列-夜市百相簿/02-角色/闻灯/设定图\多视角"
TAG = sys.argv[1] if len(sys.argv) > 1 else "v11"
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 20260916
CKPT = "majicmixRealistic_v7 (1).safetensors"
UPSCALER = "4x-UltraSharp (1).pth"

# ---------------- 锚点 ----------------
FACE_FULL = "1boy, east asian, masculine face, strong jaw, short black hair"
FACE_HEAD = ("1boy, mature man, east asian, rugged masculine face, strong jaw, stubble, "
             "mole at outer eye corner, short black hair, slightly wavy")
CLOTHES = "blue button up shirt, dark worn trench coat"
# high key = 高调照明，摄影上就是「整体明亮、背景纯白」的打光
BGD = "white background, pure white backdrop, high key lighting, bright, no shadow, sharp focus"
DETAIL_FULL = "detailed skin texture, skin pores, stubble, detailed hair, sinewy build, broad shoulders"
DETAIL_FACE = ("masculine man, strong jaw, blue button up shirt, dark coat, "
               "detailed eyes, iris detail, eyelashes, thick eyebrows, skin pores, skin texture, "
               "peach fuzz, stubble, hair strands")
POSE = "standing still, hands at sides, feet together"

# ---------------- 负向 ----------------
N1 = ("1girl, female, woman, girl, feminine face, effeminate, delicate, fragile, frail, "
      "soft features, soft round face, pretty boy, boyish face, bishounen, "
      "makeup, lipstick, rosy lips, eyeshadow, teenage, child, bulky, bodybuilder, "
      "white t-shirt, blonde hair, long hair, curly hair")
N2 = ("white shirt, t-shirt, v-neck, sweater, knitwear, suit, blazer, vest, waistcoat, tie, "
      "wool coat, brown coat, beige coat, new coat, fashion model, lookbook, jeans, denim, "
      "bare chest, shirtless, nude, police uniform, wuxia, hanfu")
N3_FULL = ("close-up, headshot, cropped, hand in pocket, hands in pockets, contrapposto, "
           "wide stance, legs apart, fashion pose, extra fingers, bad hands, watermark, text, "
           "blurry, lowres, busy background, grey background, dark background, blue background, "
           "gradient background, vignette, airbrushed, over-smoothed")
N3_FACE = ("dark background, grey background, blue background, gradient background, vignette, shadow, "
           "busy background, full body, bare shoulders, shirtless, extra fingers, bad hands, "
           "watermark, text, blurry, lowres, airbrushed, over-smoothed, beauty filter")

# ---------------- 五个视角 ----------------
VIEWS = [
    ("全身正面",
     "full body shot, head to toe, front view, " + POSE + ", " + FACE_FULL + ", " + CLOTHES,
     "1boy, front view, standing straight, hands at sides, feet together, short wavy hair, "
     "sinewy build, broad shoulders, blue shirt, dark long coat, " + DETAIL_FULL + ", " + BGD,
     N3_FULL),

    ("全身侧面",
     "full body shot, head to toe, side view, profile, " + POSE + ", facing left, " + FACE_FULL + ", " + CLOTHES,
     "1boy, side view, profile, standing straight, arms hanging at sides, short wavy hair, "
     "sinewy build, blue shirt, dark long coat, " + DETAIL_FULL + ", " + BGD,
     N3_FULL),

    ("全身背面",
     "full body shot, head to toe, back view, from behind, " + POSE + ", " + FACE_FULL + ", " + CLOTHES,
     "1boy, back view, from behind, standing straight, arms hanging at sides, short wavy hair, "
     "sinewy build, broad shoulders, blue shirt, dark long coat, " + DETAIL_FULL + ", " + BGD,
     N3_FULL),

    ("脸部正面",
     "face closeup, chest up, front view, looking at viewer, " + FACE_HEAD,
     DETAIL_FACE + ", " + BGD,
     N3_FACE),

    ("脸部侧面",
     "face closeup, chest up, side profile view, " + FACE_HEAD,
     DETAIL_FACE + ", " + BGD,
     N3_FACE),
]

# ---------------- token 校验 ----------------
sys.path.insert(0, r"D:\xiaobai-claude code\ComfyUI\venv\Lib\site-packages")
from transformers import CLIPTokenizer
tk = CLIPTokenizer.from_pretrained(r"D:\xiaobai-claude code\ComfyUI\comfy\sd1_tokenizer")


def tok(t):
    return len(tk.encode(t, add_special_tokens=False))


bad = False
print("=== token 校验（上限 75）===")
for nm, t in [("N1", N1), ("N2", N2), ("N3全身", N3_FULL), ("N3脸部", N3_FACE)]:
    n = tok(t)
    print("  %-8s %3d/75 %s" % (nm, n, "OK" if n <= 75 else "★超限★"))
    if n > 75:
        bad = True
for vn, a, b, _ in VIEWS:
    for nm, t in [("A", a), ("B", b)]:
        n = tok(t)
        print("  %-8s %-4s %3d/75 %s" % (vn, nm, n, "OK" if n <= 75 else "★超限★"))
        if n > 75:
            bad = True
if bad:
    print("有段落超限，未提交"); sys.exit(1)

# ---------------- 构图 ----------------
CLIP = ["1", 1]


def build(prefix, A, B, N3):
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": A, "clip": CLIP}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": B, "clip": CLIP}},
        "4": {"class_type": "ConditioningCombine", "inputs": {"conditioning_1": ["2", 0], "conditioning_2": ["3", 0]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": N1, "clip": CLIP}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": N2, "clip": CLIP}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": N3, "clip": CLIP}},
        "8": {"class_type": "ConditioningCombine", "inputs": {"conditioning_1": ["5", 0], "conditioning_2": ["6", 0]}},
        "9": {"class_type": "ConditioningCombine", "inputs": {"conditioning_1": ["8", 0], "conditioning_2": ["7", 0]}},
        "10": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 768, "batch_size": 1}},
        "11": {"class_type": "KSampler", "inputs": {"seed": SEED, "steps": 20, "cfg": 6.5,
                                                    "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0,
                                                    "model": ["1", 0], "positive": ["4", 0],
                                                    "negative": ["9", 0], "latent_image": ["10", 0]}},
        "12": {"class_type": "LatentUpscale", "inputs": {"upscale_method": "bislerp", "width": 768, "height": 1152,
                                                         "crop": "disabled", "samples": ["11", 0]}},
        "13": {"class_type": "KSampler", "inputs": {"seed": SEED, "steps": 20, "cfg": 6.5,
                                                    "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 0.45,
                                                    "model": ["1", 0], "positive": ["4", 0],
                                                    "negative": ["9", 0], "latent_image": ["12", 0]}},
        "14": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["1", 2]}},
        "15": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["1", 2]}},
        "16": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": UPSCALER}},
        "17": {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["16", 0], "image": ["14", 0]}},
        "18": {"class_type": "ImageScaleBy", "inputs": {"upscale_method": "lanczos", "scale_by": 0.5,
                                                        "image": ["17", 0]}},
        "19": {"class_type": "SaveImage", "inputs": {"filename_prefix": "夜市百相簿-闻灯%s-%s-草稿" % (TAG, prefix),
                                                     "images": ["15", 0]}},
        "20": {"class_type": "SaveImage", "inputs": {"filename_prefix": "夜市百相簿-闻灯%s-%s-成品" % (TAG, prefix),
                                                     "images": ["14", 0]}},
        "21": {"class_type": "SaveImage", "inputs": {"filename_prefix": "夜市百相簿-闻灯%s-%s-放大" % (TAG, prefix),
                                                     "images": ["18", 0]}},
    }


def post(p, pl):
    r = urllib.request.Request(BASE + p, data=json.dumps(pl).encode("utf-8"),
                               headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=60, context=ctx).read().decode())


def get(p):
    return urllib.request.urlopen(BASE + p, timeout=60, context=ctx).read()


jobs = []
for vn, A, B, N3 in VIEWS:
    pid = post("/prompt", {"prompt": build(vn, A, B, N3), "client_id": str(uuid.uuid4())})["prompt_id"]
    jobs.append((vn, pid))
    print("submitted %-8s -> %s" % (vn, pid))

print("\n等待生成...")
done = {}
for i in range(300):
    time.sleep(3)
    for vn, pid in jobs:
        if vn in done:
            continue
        h = json.loads(get("/history/" + pid).decode("utf-8", "replace"))
        if pid in h:
            st = h[pid].get("status", {}).get("status_str")
            if st == "error":
                print("  %s ERROR: %s" % (vn, json.dumps(h[pid]["status"], ensure_ascii=False)[:600]))
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
            if not im["filename"].startswith("夜市百相簿"):
                continue
            q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                        "type": im.get("type", "output")})
            dst = os.path.join(OUTDIR, im["filename"])
            open(dst, "wb").write(get("/view?" + q))
            print("  saved %-52s %8.1f KB" % (im["filename"], os.path.getsize(dst) / 1024))
print("\nOK")
