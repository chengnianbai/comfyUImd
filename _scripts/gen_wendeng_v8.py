# -*- coding: utf-8 -*-
"""闻灯白底全身设定图 v7：双重权重压白T恤 + 账簿复述 + 旧衣质感。"""
import urllib.request, urllib.parse, json, ssl, time, uuid, os, sys

BASE = "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016"
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
OUTDIR = r"D:\xiaobai-claude code\comfyUImd\系列-夜市百相簿/02-角色/闻灯/设定图"
TAG = sys.argv[1] if len(sys.argv) > 1 else "v8"
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 20260916

A = ("full body shot, head to toe, 1boy, solo, 24 year old man, east asian, masculine face, "
     "strong jaw, stubble, tired eyes, mole at outer eye corner, short black hair, slightly wavy, "
     "wiry sinewy build, broad shoulders, blue button up shirt, dark worn trench coat, "
     "dark trousers, old shoes, holding old ledger")
# 「old ledger」在 A、B 各出现一次 = 合并后双倍权重；同理 blue shirt
B = ("1boy, male, deep set eyes, thick eyebrows, weathered skin, detailed skin texture, skin pores, "
     "peach fuzz, film grain, blue shirt, short hair, old ledger, worn faded fabric, open coat, "
     "white background, grey backdrop, side lighting, hard directional light, strong rim light, "
     "35mm lens, sharp focus, photorealistic")
N1 = ("1girl, female, woman, feminine face, androgynous, effeminate, delicate, fragile, frail, "
      "soft features, pretty boy, boyish face, bishounen, makeup, lipstick, eyeshadow, "
      "teenage, child, bulky, bodybuilder, white hair, grey hair, blonde hair, long hair, curly hair, "
      "white t-shirt")
N2 = ("white shirt, t-shirt, v-neck, sweater, knitwear, suit, blazer, tie, wool coat, brown coat, "
      "beige coat, new coat, modern fashion, fashion model, lookbook, jeans, denim, bare chest, "
      "shirtless, nude, topless, paint splatter, ripped clothes")
N3 = ("close-up, portrait, headshot, bust shot, cropped, police uniform, wuxia, hanfu, extra fingers, "
      "bad hands, watermark, text, blurry, lowres, busy background, airbrushed, over-smoothed, beauty filter")

sys.path.insert(0, r"D:\xiaobai-claude code\ComfyUI\venv\Lib\site-packages")
from transformers import CLIPTokenizer
tk = CLIPTokenizer.from_pretrained(r"D:\xiaobai-claude code\ComfyUI\comfy\sd1_tokenizer")
bad = False
for nm, t in [("A", A), ("B", B), ("N1", N1), ("N2", N2), ("N3", N3)]:
    n = len(tk.encode(t, add_special_tokens=False))
    print("token %s: %d/75 %s" % (nm, n, "OK" if n <= 75 else "★超限★"))
    if n > 75:
        bad = True
if bad:
    print("超限，未提交"); sys.exit(1)

C = ["1", 1]
graph = {
    "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "majicmixRealistic_v7 (1).safetensors"}},
    "2": {"class_type": "CLIPTextEncode", "inputs": {"text": A, "clip": C}},
    "3": {"class_type": "CLIPTextEncode", "inputs": {"text": B, "clip": C}},
    "4": {"class_type": "ConditioningCombine", "inputs": {"conditioning_1": ["2", 0], "conditioning_2": ["3", 0]}},
    "5": {"class_type": "CLIPTextEncode", "inputs": {"text": N1, "clip": C}},
    "18": {"class_type": "CLIPTextEncode", "inputs": {"text": N2, "clip": C}},
    "20": {"class_type": "CLIPTextEncode", "inputs": {"text": N3, "clip": C}},
    "19": {"class_type": "ConditioningCombine", "inputs": {"conditioning_1": ["5", 0], "conditioning_2": ["18", 0]}},
    "21": {"class_type": "ConditioningCombine", "inputs": {"conditioning_1": ["19", 0], "conditioning_2": ["20", 0]}},
    "6": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 768, "batch_size": 1}},
    "7": {"class_type": "KSampler", "inputs": {"seed": SEED, "steps": 20, "cfg": 6.5, "sampler_name": "dpmpp_2m",
                                               "scheduler": "karras", "denoise": 1.0, "model": ["1", 0],
                                               "positive": ["4", 0], "negative": ["21", 0], "latent_image": ["6", 0]}},
    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["1", 2]}},
    "9": {"class_type": "PreviewImage", "inputs": {"images": ["8", 0]}},
    "10": {"class_type": "SaveImage", "inputs": {"filename_prefix": "夜市百相簿-闻灯%s-草稿" % TAG, "images": ["8", 0]}},
    "11": {"class_type": "LatentUpscale", "inputs": {"upscale_method": "bislerp", "width": 768, "height": 1152,
                                                     "crop": "disabled", "samples": ["7", 0]}},
    "12": {"class_type": "KSampler", "inputs": {"seed": SEED, "steps": 20, "cfg": 6.5, "sampler_name": "dpmpp_2m",
                                                "scheduler": "karras", "denoise": 0.45, "model": ["1", 0],
                                                "positive": ["4", 0], "negative": ["21", 0], "latent_image": ["11", 0]}},
    "13": {"class_type": "VAEDecode", "inputs": {"samples": ["12", 0], "vae": ["1", 2]}},
    "14": {"class_type": "PreviewImage", "inputs": {"images": ["13", 0]}},
    "15": {"class_type": "SaveImage", "inputs": {"filename_prefix": "夜市百相簿-闻灯%s-成品" % TAG, "images": ["13", 0]}},
}


def post(p, pl):
    r = urllib.request.Request(BASE + p, data=json.dumps(pl).encode("utf-8"),
                               headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=60, context=ctx).read().decode())


def get(p):
    return urllib.request.urlopen(BASE + p, timeout=30, context=ctx).read()


pid = post("/prompt", {"prompt": graph, "client_id": str(uuid.uuid4())})["prompt_id"]
print("submitted:", pid)
for i in range(150):
    time.sleep(2)
    h = json.loads(get("/history/" + pid).decode("utf-8", "replace"))
    if pid in h:
        rec = h[pid]
        st = rec.get("status", {}).get("status_str")
        print("done after %ds status=%s" % ((i + 1) * 2, st))
        if st == "error":
            print(json.dumps(rec["status"], ensure_ascii=False)[:1500]); sys.exit(1)
        break
else:
    print("TIMEOUT"); sys.exit(1)

os.makedirs(OUTDIR, exist_ok=True)
for nid, o in rec.get("outputs", {}).items():
    for im in o.get("images", []):
        if not im["filename"].startswith("夜市百相簿"):
            continue
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        open(os.path.join(OUTDIR, im["filename"]), "wb").write(get("/view?" + q))
        print("saved:", im["filename"])
print("OK")
