"""闻灯角色快速验证：只出 512×768 草稿，确认「男性能否成立」+「服装能否还原」。

跑得快（约 6 分钟），用来在花 22 分钟跑高清修复之前先排雷。
"""

import json
import os
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8188"
OUT_DIR = r"D:\xiaobai-claude code\ComfyUI\output"
SEED = 20260916

POS_A = ("cinematic photo, 1boy, solo, 24 year old man, east asian, slim lean build, "
         "short black slightly wavy hair, tired eyes, dark circles, small mole at outer eye corner, "
         "(faded blue old shirt:1.3), dark old trench coat open, (holding an old leather ledger:1.2), "
         "sharp gaze, full body, standing")

POS_B = ("oriental old city, humid night market alley, blue grey ambient light, "
         "dim desaturated firelight, wet ground reflections, film grain, "
         "35mm lens, cinematic, moody, supernatural realism, street lamp light on face")

NEG = ("1girl, female, woman, modern police uniform, ancient chinese costume, wuxia, idol makeup, "
       "exaggerated muscles, child, young boy, smooth skin, plastic skin, airbrushed, extra limbs, "
       "bad hands, watermark, text, signature, blurry, lowres, oversaturated")

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
          "inputs": {"width": 512, "height": 768, "batch_size": 1}},
    "7": {"class_type": "KSampler",
          "inputs": {"seed": SEED, "steps": 20, "cfg": 6.5,
                     "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0,
                     "model": ["1", 0], "positive": ["4", 0],
                     "negative": ["5", 0], "latent_image": ["6", 0]}},
    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["1", 2]}},
    "9": {"class_type": "SaveImage",
          "inputs": {"filename_prefix": "WendengTest", "images": ["8", 0]}},
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
    print(">> 提交闻灯测试任务 ...", flush=True)
    try:
        res = api("/prompt", {"prompt": PROMPT})
    except urllib.error.HTTPError as e:
        print("   提交失败 HTTP %s: %s" % (e.code, e.read(900).decode("utf-8", "replace")))
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
        if el > 30:
            print("   超时")
            return 1


if __name__ == "__main__":
    sys.exit(main())
