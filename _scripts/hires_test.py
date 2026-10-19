"""皮肤质感验证：同一个提示词 / 同一个种子，同时存出「512 草稿」和「高清修复后」两张图。

目的是把变量单独拎出来 —— 两张图除了分辨率完全一样，
所以画质差异只能归因于「高清修复（分辨率）」这一个因素。
"""

import json
import os
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8188"
OUT_DIR = r"D:\xiaobai-claude code\ComfyUI\output"
SEED = 20260916

POSITIVE = ("masterpiece, best quality, ultra detailed, RAW photo, photorealistic, "
            "1girl, asian, chinese, black straight hair, dark brown eyes, single eyelid, "
            "delicate features, (realistic skin texture:1.3), (skin pores:1.2), fine skin details, "
            "subtle freckles, natural skin imperfections, peach fuzz, detailed eyes, "
            "detailed eyelashes, natural makeup, side lighting, directional light, rim light, "
            "upper body portrait, looking at viewer, 85mm lens, f/2.8, film grain, Fujifilm, "
            "sharp focus on face, bokeh background")

NEGATIVE = ("lowres, bad anatomy, bad hands, worst quality, low quality, watermark, "
            "signature, caucasian, western face, blonde hair, blue eyes, "
            "smooth skin, plastic skin, airbrushed, over-smoothed, blurry, soft focus, "
            "glow, oversaturated, cartoon, 3d, cgi, painting, illustration, doll, retouched")

urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))

PROMPT = {
    "1": {"class_type": "CheckpointLoaderSimple",
          "inputs": {"ckpt_name": "majicmixRealistic_v7.safetensors"}},
    "4": {"class_type": "EmptyLatentImage",
          "inputs": {"width": 512, "height": 640, "batch_size": 1}},
    "2": {"class_type": "CLIPTextEncode",
          "inputs": {"text": POSITIVE, "clip": ["1", 1]}},
    "3": {"class_type": "CLIPTextEncode",
          "inputs": {"text": NEGATIVE, "clip": ["1", 1]}},
    # ---- 第一段：512 草稿 ----
    "5": {"class_type": "KSampler",
          "inputs": {"seed": SEED, "steps": 20, "cfg": 6.5,
                     "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0,
                     "model": ["1", 0], "positive": ["2", 0],
                     "negative": ["3", 0], "latent_image": ["4", 0]}},
    "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
    "7": {"class_type": "SaveImage",
          "inputs": {"filename_prefix": "SkinDraft512", "images": ["6", 0]}},
    # ---- 放大 ----
    "8": {"class_type": "LatentUpscale",
          "inputs": {"samples": ["5", 0], "upscale_method": "bislerp",
                     "width": 768, "height": 960, "crop": "disabled"}},
    # ---- 第二段：低幅度二次重绘补细节 ----
    "9": {"class_type": "KSampler",
          "inputs": {"seed": SEED, "steps": 20, "cfg": 6.5,
                     "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 0.45,
                     "model": ["1", 0], "positive": ["2", 0],
                     "negative": ["3", 0], "latent_image": ["8", 0]}},
    "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["1", 2]}},
    "11": {"class_type": "SaveImage",
           "inputs": {"filename_prefix": "SkinFinal768", "images": ["10", 0]}},
}


def api(path, payload=None):
    url = BASE + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"},
        method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    print(">> 提交任务 ...", flush=True)
    try:
        res = api("/prompt", {"prompt": PROMPT})
    except urllib.error.HTTPError as e:
        print("   提交失败 HTTP %s: %s" % (e.code, e.read(800).decode("utf-8", "replace")))
        return 1
    pid = res.get("prompt_id")
    print("   prompt_id = %s" % pid, flush=True)
    if not pid:
        return 1

    t0 = time.time()
    last = 0
    while True:
        time.sleep(15)
        try:
            h = api("/history/%s" % pid)
        except Exception:
            continue
        el = (time.time() - t0) / 60
        if pid in h:
            entry = h[pid]
            st = entry.get("status", {})
            print(">> 结束，耗时 %.1f 分钟   status=%s" % (el, st.get("status_str")), flush=True)
            if st.get("status_str") == "error":
                print(json.dumps(st, ensure_ascii=False)[:2000])
                return 1
            for node in entry.get("outputs", {}).values():
                for im in node.get("images", []):
                    p = os.path.join(OUT_DIR, im.get("subfolder", ""), im.get("filename"))
                    print("   产出：%s  (%.0f KB)" % (p, os.path.getsize(p) / 1024))
            return 0
        if el // 2 != last // 2:
            last = el
            print("   出图中 ... %.1f 分钟" % el, flush=True)
        if el > 40:
            print("   超时")
            return 1


if __name__ == "__main__":
    sys.exit(main())
