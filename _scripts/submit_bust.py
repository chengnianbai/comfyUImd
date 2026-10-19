"""把「闻灯·白底半身」提交进 ComfyUI 队列，让用户在自己的浏览器里实时看到。

和 UI 工作流 闻灯-白底半身.json 完全一致的参数，节点 id 也保持一致，
这样用户在界面里打开工作流时，能看到节点依次亮起、预览图直接出现在节点上。
"""

import json
import os
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8188"
OUT_DIR = r"D:\xiaobai-claude code\ComfyUI\output"
SEED = 20260916

POS_A = ("character reference, 1boy, solo, 24 year old man, east asian, slim lean build, "
         "short black slightly wavy hair, tired eyes, small mole at outer eye corner, "
         "(faded blue old shirt:1.3), dark old trench coat open, "
         "(holding an old leather ledger:1.2), sharp gaze, upper body, looking at viewer")

POS_B = ("pure white background, plain white backdrop, studio lighting, soft even light, "
         "detailed face, clear facial features, sharp focus, film grain, 35mm lens, photorealistic")

NEG = ("1girl, female, woman, wuxia, idol makeup, exaggerated muscles, child, young boy, "
       "bad face, deformed face, asymmetric eyes, extra limbs, bad hands, extra fingers, "
       "watermark, text, signature, blurry, lowres, busy background, scenery, cluttered, "
       "smooth skin, plastic skin, airbrushed")

urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))

PROMPT = {
    "1": {"class_type": "CheckpointLoaderSimple",
          "inputs": {"ckpt_name": "majicmixRealistic_v7.safetensors"}},
    "2": {"class_type": "CLIPTextEncode", "inputs": {"text": POS_A, "clip": ["1", 1]}},
    "3": {"class_type": "CLIPTextEncode", "inputs": {"text": POS_B, "clip": ["1", 1]}},
    "4": {"class_type": "ConditioningCombine",
          "inputs": {"conditioning_1": ["2", 0], "conditioning_2": ["3", 0]}},
    "5": {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["1", 1]}},
    "6": {"class_type": "EmptyLatentImage",
          "inputs": {"width": 512, "height": 640, "batch_size": 1}},
    "7": {"class_type": "KSampler",
          "inputs": {"seed": SEED, "steps": 20, "cfg": 6.0,
                     "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0,
                     "model": ["1", 0], "positive": ["4", 0],
                     "negative": ["5", 0], "latent_image": ["6", 0]}},
    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["1", 2]}},
    "9": {"class_type": "PreviewImage", "inputs": {"images": ["8", 0]}},
    "10": {"class_type": "SaveImage",
           "inputs": {"filename_prefix": "闻灯-白底半身草稿", "images": ["8", 0]}},
    "11": {"class_type": "LatentUpscale",
           "inputs": {"samples": ["7", 0], "upscale_method": "bislerp",
                      "width": 768, "height": 960, "crop": "disabled"}},
    "12": {"class_type": "KSampler",
           "inputs": {"seed": SEED, "steps": 20, "cfg": 6.0,
                      "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 0.45,
                      "model": ["1", 0], "positive": ["4", 0],
                      "negative": ["5", 0], "latent_image": ["11", 0]}},
    "13": {"class_type": "VAEDecode", "inputs": {"samples": ["12", 0], "vae": ["1", 2]}},
    "14": {"class_type": "PreviewImage", "inputs": {"images": ["13", 0]}},
    "15": {"class_type": "SaveImage",
           "inputs": {"filename_prefix": "闻灯-白底半身成品", "images": ["13", 0]}},
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
    print(">> 提交「闻灯·白底半身」 ...", flush=True)
    try:
        res = api("/prompt", {"prompt": PROMPT})
    except urllib.error.HTTPError as e:
        print("   提交失败 HTTP %s: %s" % (e.code, e.read(1200).decode("utf-8", "replace")))
        return 1
    pid = res.get("prompt_id")
    if not pid:
        print("   异常返回:", res)
        return 1
    print("   prompt_id = %s" % pid, flush=True)
    print("   已进入队列，打开 http://127.0.0.1:8188 即可看到实时进度", flush=True)

    t0 = time.time()
    last = 0
    while True:
        time.sleep(20)
        try:
            h = api("/history/%s" % pid)
        except Exception:
            continue
        el = (time.time() - t0) / 60
        if pid in h:
            entry = h[pid]
            st = entry.get("status", {})
            print(">> 结束，耗时 %.1f 分钟  status=%s" % (el, st.get("status_str")), flush=True)
            if st.get("status_str") == "error":
                print(json.dumps(st, ensure_ascii=False)[:2500])
                return 1
            for node in entry.get("outputs", {}).values():
                for im in node.get("images", []):
                    if im.get("type") != "output":
                        continue
                    p = os.path.join(OUT_DIR, im.get("subfolder", ""), im.get("filename"))
                    print("   产出：%s  (%.0f KB)" % (p, os.path.getsize(p) / 1024))
            return 0
        if el // 3 != last // 3:
            last = el
            print("   进行中 ... %.1f 分钟" % el, flush=True)
        if el > 45:
            print("   超时")
            return 1


if __name__ == "__main__":
    sys.exit(main())
