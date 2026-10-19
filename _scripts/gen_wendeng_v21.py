# -*- coding: utf-8 -*-
"""闻灯 脸部左右侧脸 v21 —— 与已确认的 v13 正脸保持同一个人

已确认基准（资产里只保留了这两张）：
    闻灯v13-脸部正面-草稿_00001_ / 闻灯v13-脸部正面-成品_00001_
本脚本只做一件事：把取景词换成左右两个侧向，其余角色 token 逐字复用、seed 相同。
防种族漂移：正向保留 east asian，负向补 caucasian / european / other ethnicity。

v20 -> v21：SDXL 对方位词不敏感，两张侧脸都朝了同一侧。
  本版给每个视角单独加强制方位负向（复用 N2 段的剩余 token 余量）。
用法： python gen_wendeng_v21.py [TAG] [SEED] [--check]
"""
import urllib.request, urllib.parse, json, ssl, time, uuid, os, sys

BASE = "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016"
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
OUTDIR = r"D:\xiaobai-claude code\comfyUImd\系列-夜市百相簿/02-角色/闻灯/设定图\脸部"

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
CHECK = "--check" in sys.argv
TAG = ARGS[0] if len(ARGS) > 0 else "v21"
SEED = int(ARGS[1]) if len(ARGS) > 1 else 20260916

CKPT = "leosamsHelloworldXL_helloworldXL70.safetensors"
UPSCALER = "4x-UltraSharp (1).pth"
W, H = 896, 1152
SCALE_BY = 0.5
STEPS_1, CFG_1 = 30, 10.0
STEPS_2, CFG_2, DEN_2 = 20, 10.0, 0.25

# ============ 角色基准块（与 v13 正脸逐字一致）============
BGD = "pure white background"
HAIR = "messy wavy black hair"
MOLE = "small mole at outer eye corner"
SHIRT = "faded blue shirt"
CHAR = "1boy, solo, 24 year old east asian man, masculine face, strong jaw, " + HAIR
FACE_A_BODY = ("face closeup, head and shoulders, " + CHAR + ", " + MOLE + ", "
               + SHIRT + " collar, dark coat collar, " + BGD)
FACE_B = ("detailed face, detailed eyes, dark circles under eyes, iris detail, individual eyelashes, "
          "thick eyebrows, stubble, " + MOLE + ", visible skin pores, skin texture, skin imperfections, "
          "peach fuzz, messy wavy hair, individual hair strands, faded shirt collar, dark coat, "
          + BGD + ", flat even lighting, sharp focus, photorealistic")

N1 = ("1girl, female, feminine face, delicate, fragile, soft features, soft round face, "
      "pretty boy, boyish face, bishounen, makeup, lipstick, rosy lips, eyeshadow, "
      "teenage, child, narrow face, pale skin, blonde hair, straight hair, "
      "slicked back hair, undercut, side part, neat hair")
N2 = ("caucasian, european face, western features, african, indian, middle eastern, "
      "latino, mixed race, full beard, thick beard, curly beard, "
      "t-shirt, sweater, business suit, blazer, tie, dress shirt, "
      "turtleneck, jean jacket")
N3_FACE = ("dark background, grey background, gradient background, vignette, shadow, "
           "busy background, full body, bare shoulders, shirtless, freckles, mole on cheek, mole on forehead, "
           "extra fingers, bad hands, watermark, text, blurry, lowres, airbrushed, "
           "over-smoothed, beauty filter, smooth skin, retouched, looking away, closed eyes")

# ============ 两个侧向 ============
VIEWS = [
    # 朝左：脸转向画面左侧（看到角色右脸）
    ("脸部朝左",
     "side profile view, 90 degree side view, face turned to the left, looking left, "
     "single eye visible, " + FACE_A_BODY,
     "facing right, looking right, three quarter view, front view, both eyes visible"),
    # 朝右：脸转向画面右侧（看到角色左脸）
    ("脸部朝右",
     "side profile view, 90 degree side view, face turned to the right, looking right, "
     "single eye visible, " + FACE_A_BODY,
     "facing left, looking left, three quarter view, front view, both eyes visible"),
]

# ============ token 校验 ============
sys.path.insert(0, r"D:\xiaobai-claude code\ComfyUI\venv\Lib\site-packages")
from transformers import CLIPTokenizer
tk = CLIPTokenizer.from_pretrained(r"D:\xiaobai-claude code\ComfyUI\comfy\sd1_tokenizer")


def tok(t):
    return len(tk.encode(t, add_special_tokens=False))


bad = []
print("=== token 校验（上限 75）===")
for nm, t in [("N1", N1), ("N2", N2), ("N3脸部", N3_FACE), ("B段", FACE_B)]:
    n = tok(t)
    print("  %-8s %3d/75 %s" % (nm, n, "OK" if n <= 75 else "★超限★"))
    if n > 75:
        bad.append(nm)
for vn, a, nx in VIEWS:
    for nm, s in [("A", a), ("N2+", N2 + ", " + nx)]:
        n = tok(s)
        print("  %-8s %-4s %3d/75 %s" % (vn, nm, n, "OK" if n <= 75 else "★超限★"))
        if n > 75:
            bad.append(vn + nm)
if bad:
    print("\n★ 有段落超限，未提交：", bad)
    sys.exit(1)
print("\n全部在 75 以内")
if CHECK:
    sys.exit(0)

CLIP = ["2", 0]


def build(prefix, A, B, N3, N2_OVERRIDE=None):
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "2": {"class_type": "CLIPSetLastLayer", "inputs": {"clip": ["1", 1], "stop_at_clip_layer": -1}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": A, "clip": CLIP}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": B, "clip": CLIP}},
        "5": {"class_type": "ConditioningCombine", "inputs": {"conditioning_1": ["3", 0], "conditioning_2": ["4", 0]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": N1, "clip": CLIP}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": N2_OVERRIDE or N2, "clip": CLIP}},
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


print("\n底模: %s | %dx%d | seed=%d（与 v13 正脸相同）\n" % (CKPT, W, H, SEED))

jobs = []
for vn, A, NX in VIEWS:
    pid = post("/prompt", {"prompt": build(vn, A, FACE_B, N3_FACE, N2 + ", " + NX),
                           "client_id": str(uuid.uuid4())})["prompt_id"]
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
            print("  saved %-40s %8.1f KB" % (im["filename"], os.path.getsize(dst) / 1024))
print("\nOK")
