# -*- coding: utf-8 -*-
"""闻灯多视角角色设定图 v9
- 5 个视角独立生成：全身正/侧/背 + 脸部正/侧
- 纯白背景（正向强调 + 负向压灰底/投影）
- 脸部与头发细节加强
- 新增放大链路：VAEDecode -> ImageUpscaleWithModel(4x-UltraSharp) -> ImageScaleBy(0.5x)
  = 768x1152 -> 3072x4608 -> 1536x2304
"""
import urllib.request, urllib.parse, json, ssl, time, uuid, os, sys

BASE = "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016"
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
OUTDIR = r"D:\xiaobai-claude code\comfyUImd\系列-夜市百相簿/02-角色/闻灯/设定图\多视角"
TAG = sys.argv[1] if len(sys.argv) > 1 else "v9"
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 20260916
CKPT = "majicmixRealistic_v7 (1).safetensors"
UPSCALER = "4x-UltraSharp (1).pth"

# ---------------- 共用锚点 ----------------
BODY_FULL = ("1boy, solo, 24 year old man, east asian, masculine face, strong jaw, stubble, "
             "tired eyes, mole at outer eye corner, short black hair, slightly wavy, "
             "wiry sinewy build, broad shoulders")
BODY_FACE = ("1boy, solo, 24 year old man, east asian, masculine face, strong jaw, stubble, "
             "tired eyes, mole at outer eye corner, short black hair, slightly wavy")

CLOTHES = "blue button up shirt, dark worn trench coat, dark trousers, old shoes"
WHITE = "pure white background, solid white backdrop, isolated on white"
LIGHT = "even soft studio lighting, 35mm lens, sharp focus, photorealistic"

DETAIL_FULL = ("detailed skin texture, skin pores, stubble, weathered skin, "
               "detailed hair, individual hair strands, hair texture, film grain")
DETAIL_FACE = ("detailed face, detailed eyes, iris detail, individual eyelashes, thick eyebrows, "
               "visible skin pores, skin texture, peach fuzz, stubble, "
               "detailed hair, individual hair strands, hair texture")

# ---------------- 负向 ----------------
N1 = ("1girl, female, woman, feminine face, androgynous, effeminate, delicate, fragile, frail, "
      "soft features, pretty boy, boyish face, bishounen, makeup, lipstick, eyeshadow, "
      "teenage, child, bulky, bodybuilder, white hair, grey hair, blonde hair, long hair, curly hair, "
      "white t-shirt")
N2 = ("white shirt, t-shirt, v-neck, sweater, knitwear, suit, blazer, tie, wool coat, brown coat, "
      "beige coat, new coat, modern fashion, fashion model, lookbook, jeans, denim, bare chest, "
      "shirtless, nude, topless, paint splatter, ripped clothes")
# 全身版：压掉特写；加纯白背景要求（压灰底/渐变/投影）
N3_FULL = ("close-up, portrait, headshot, bust shot, cropped, police uniform, wuxia, hanfu, "
           "extra fingers, bad hands, watermark, text, blurry, lowres, busy background, "
           "grey background, gradient background, floor, cast shadow, "
           "airbrushed, over-smoothed, beauty filter")
# 脸部版：不能压特写（否则不画脸），改压全身构图
N3_FACE = ("police uniform, wuxia, hanfu, extra fingers, bad hands, watermark, text, "
           "blurry, lowres, busy background, grey background, gradient background, floor, "
           "body shot, full body, cropped face, airbrushed, over-smoothed, beauty filter")

# ---------------- 五个视角 ----------------
# (文件名后缀, A段, B段, N3)
VIEWS = [
    ("全身正面",
     "full body shot, head to toe, front view, standing straight, arms at sides, symmetrical pose, " + BODY_FULL,
     CLOTHES + ", " + DETAIL_FULL + ", " + WHITE + ", " + LIGHT,
     N3_FULL),

    ("全身侧面",
     "full body shot, head to toe, side view, profile, standing straight, arms at sides, facing left, " + BODY_FULL,
     CLOTHES + ", " + DETAIL_FULL + ", " + WHITE + ", " + LIGHT,
     N3_FULL),

    ("全身背面",
     "full body shot, head to toe, back view, from behind, standing straight, arms at sides, " + BODY_FULL,
     CLOTHES + ", " + DETAIL_FULL + ", " + WHITE + ", " + LIGHT,
     N3_FULL),

    ("脸部正面",
     "face closeup, head and shoulders, front view, looking at viewer, " + BODY_FACE,
     DETAIL_FACE + ", blue collar, " + WHITE + ", " + LIGHT,
     N3_FACE),

    ("脸部侧面",
     "face closeup, head and shoulders, side profile view, " + BODY_FACE,
     DETAIL_FACE + ", blue collar, " + WHITE + ", " + LIGHT,
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

        # ---- 新增放大链路 ----
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


# ---------------- 全部提交 ----------------
jobs = []
for vn, A, B, N3 in VIEWS:
    prefix = "夜市百相簿-闻灯%s-%s" % (TAG, vn)
    g = build(vn, A, B, N3)
    pid = post("/prompt", {"prompt": g, "client_id": str(uuid.uuid4())})["prompt_id"]
    jobs.append((vn, pid))
    print("submitted %-8s -> %s" % (vn, pid))

print("\n等待生成（远程 48G，每张约 10-20 秒）...")
done = {}
for i in range(300):
    time.sleep(3)
    allok = True
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
        else:
            allok = False
    if len(done) == len(jobs):
        break

# ---------------- 下载 ----------------
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
