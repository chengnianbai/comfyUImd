# -*- coding: utf-8 -*-
"""向远程 ComfyUI 提交闻灯白底设定图（增强版关键词，3段正向 + 2段负向）。"""
import urllib.request, json, ssl, time, uuid, os, sys

BASE = "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016"
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
OUTDIR = r"D:\xiaobai-claude code\comfyUImd\系列-夜市百相簿/02-角色/闻灯/设定图"

# ---------- 提示词：每段均 <=75 token ----------
A = ("1boy, solo, 24 year old man, east asian, narrow face, sharp jawline, tired eyes, "
     "dark circles under eyes, heavy eyelids, thick dark eyebrows, small black mole at outer eye corner, "
     "black hair, slightly wavy black hair, messy damp hair, medium short hair, hair over ears, pale skin")
B = ("slim lean build, thin wiry body, faded light blue cotton shirt, wrinkled worn shirt, rolled sleeves, "
     "dark charcoal grey worn trench coat, open long coat, frayed collar, damp wet fabric, "
     "old worn leather shoes, small damp ledger book, cinnabar red powder on sleeve, "
     "standing, full body shot, head to toe, full length")
C = ("white background, plain light grey seamless backdrop, side lighting, hard directional light, "
     "strong rim light, crisp shadow, detailed skin texture, skin pores, fine skin details, peach fuzz, "
     "film grain, 35mm lens, sharp focus, photorealistic, cinematic still")
N1 = ("1girl, female, woman, feminine face, makeup, lipstick, eyeshadow, pretty boy, boyish face, "
      "teenage, child, muscular, bodybuilder, macho, bulky, white hair, grey hair, blonde hair, long hair")
N2 = ("close-up, portrait, headshot, bust shot, cropped, police uniform, modern uniform, tactical gear, "
      "ancient costume, wuxia, hanfu, swordsman, extra fingers, bad hands, watermark, text, blurry, "
      "lowres, busy background, airbrushed, over-smoothed, beauty filter")

SEED = 20260916
CLIP = ["1", 1]

graph = {
    "1":  {"class_type": "CheckpointLoaderSimple",
           "inputs": {"ckpt_name": "majicmixRealistic_v7 (1).safetensors"}},
    "2":  {"class_type": "CLIPTextEncode", "inputs": {"text": A, "clip": CLIP}},
    "3":  {"class_type": "CLIPTextEncode", "inputs": {"text": C, "clip": CLIP}},
    "4":  {"class_type": "ConditioningCombine", "inputs": {"conditioning_1": ["2", 0], "conditioning_2": ["3", 0]}},
    "16": {"class_type": "CLIPTextEncode", "inputs": {"text": B, "clip": CLIP}},
    "17": {"class_type": "ConditioningCombine", "inputs": {"conditioning_1": ["4", 0], "conditioning_2": ["16", 0]}},
    "5":  {"class_type": "CLIPTextEncode", "inputs": {"text": N1, "clip": CLIP}},
    "18": {"class_type": "CLIPTextEncode", "inputs": {"text": N2, "clip": CLIP}},
    "19": {"class_type": "ConditioningCombine", "inputs": {"conditioning_1": ["5", 0], "conditioning_2": ["18", 0]}},
    "6":  {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 768, "batch_size": 1}},
    "7":  {"class_type": "KSampler",
           "inputs": {"seed": SEED, "steps": 20, "cfg": 6.5, "sampler_name": "dpmpp_2m",
                      "scheduler": "karras", "denoise": 1.0, "model": ["1", 0],
                      "positive": ["17", 0], "negative": ["19", 0], "latent_image": ["6", 0]}},
    "8":  {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["1", 2]}},
    "9":  {"class_type": "PreviewImage", "inputs": {"images": ["8", 0]}},
    "10": {"class_type": "SaveImage",
           "inputs": {"filename_prefix": "夜市百相簿-闻灯白底草稿", "images": ["8", 0]}},
    "11": {"class_type": "LatentUpscale",
           "inputs": {"upscale_method": "bislerp", "width": 768, "height": 1152,
                      "crop": "disabled", "samples": ["7", 0]}},
    "12": {"class_type": "KSampler",
           "inputs": {"seed": SEED, "steps": 20, "cfg": 6.5, "sampler_name": "dpmpp_2m",
                      "scheduler": "karras", "denoise": 0.45, "model": ["1", 0],
                      "positive": ["17", 0], "negative": ["19", 0], "latent_image": ["11", 0]}},
    "13": {"class_type": "VAEDecode", "inputs": {"samples": ["12", 0], "vae": ["1", 2]}},
    "14": {"class_type": "PreviewImage", "inputs": {"images": ["13", 0]}},
    "15": {"class_type": "SaveImage",
           "inputs": {"filename_prefix": "夜市百相簿-闻灯白底成品", "images": ["13", 0]}},
}


def post(path, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=60, context=ctx).read().decode())


def get(path):
    return urllib.request.urlopen(BASE + path, timeout=30, context=ctx).read()


client_id = str(uuid.uuid4())
res = post("/prompt", {"prompt": graph, "client_id": client_id})
pid = res["prompt_id"]
print("submitted prompt_id:", pid)
print("queue number:", res.get("number"))

# ---------- 等完成 ----------
for i in range(150):
    time.sleep(2)
    h = json.loads(get("/history/" + pid).decode("utf-8", "replace"))
    if pid in h:
        rec = h[pid]
        st = rec.get("status", {})
        print("done after %ds, status=%s" % ((i + 1) * 2, st.get("status_str")))
        if st.get("status_str") == "error":
            print(json.dumps(st, ensure_ascii=False)[:2000])
            sys.exit(1)
        break
else:
    print("TIMEOUT")
    sys.exit(1)

# ---------- 下载产物 ----------
os.makedirs(OUTDIR, exist_ok=True)
imgs = rec.get("outputs", {})
saved = []
for nid, o in imgs.items():
    for im in o.get("images", []):
        q = "filename=%s&subfolder=%s&type=%s" % (im["filename"], im.get("subfolder", ""), im.get("type", "output"))
        raw = get("/view?" + q)
        fp = os.path.join(OUTDIR, im["filename"])
        open(fp, "wb").write(raw)
        saved.append((fp, len(raw)))
        print("saved:", fp, len(raw), "bytes")

json.dump({"prompt_id": pid, "client_id": client_id, "graph": graph, "saved": [s[0] for s in saved]},
          open(os.path.join(OUTDIR, "_last_submit.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("OK", len(saved), "files")
