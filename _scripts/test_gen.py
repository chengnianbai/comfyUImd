"""端到端验证：用 majicMIX realistic v7 实际出一张亚洲人像。

通过 ComfyUI 的 /prompt 接口提交任务（用 API 格式），轮询 /history 等结果，
最后确认 output 目录里生成了图片。
"""

import json
import os
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8188"
OUT_DIR = r"D:\xiaobai-claude code\ComfyUI\output"
PREFIX = "AsianTest"

POSITIVE = ("masterpiece, best quality, photorealistic, 1girl, asian, chinese, "
            "black straight hair, dark brown eyes, single eyelid, delicate features, "
            "fair skin, natural makeup, soft window light, upper body portrait, "
            "looking at viewer, 85mm lens, shallow depth of field")
NEGATIVE = ("lowres, bad anatomy, bad hands, worst quality, low quality, watermark, "
            "signature, caucasian, western face, blonde hair, blue eyes")

# 强制不走代理（访问的是本机服务）
urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))


def api(path, payload=None):
    url = BASE + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


PROMPT = {
    "1": {"class_type": "CheckpointLoaderSimple",
          "inputs": {"ckpt_name": "majicmixRealistic_v7.safetensors"}},
    "4": {"class_type": "EmptyLatentImage",
          "inputs": {"width": 512, "height": 640, "batch_size": 1}},
    "2": {"class_type": "CLIPTextEncode",
          "inputs": {"text": POSITIVE, "clip": ["1", 1]}},
    "3": {"class_type": "CLIPTextEncode",
          "inputs": {"text": NEGATIVE, "clip": ["1", 1]}},
    "5": {"class_type": "KSampler",
          "inputs": {"seed": 20260916, "steps": 20, "cfg": 7.0,
                     "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0,
                     "model": ["1", 0], "positive": ["2", 0],
                     "negative": ["3", 0], "latent_image": ["4", 0]}},
    "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
    "7": {"class_type": "SaveImage",
          "inputs": {"filename_prefix": PREFIX, "images": ["6", 0]}},
}


def main():
    print(">> 提交任务到 ComfyUI ...", flush=True)
    try:
        res = api("/prompt", {"prompt": PROMPT})
    except urllib.error.HTTPError as e:
        print("   提交失败 HTTP %s: %s" % (e.code, e.read(600).decode("utf-8", "replace")))
        return 1
    pid = res.get("prompt_id")
    if not pid:
        print("   没有拿到 prompt_id，返回：%s" % res)
        return 1
    print("   prompt_id = %s" % pid, flush=True)

    t0 = time.time()
    while True:
        time.sleep(10)
        try:
            h = api("/history/%s" % pid)
        except Exception as e:
            print("   查询失败：%s" % str(e)[:80])
            continue
        if pid in h:
            entry = h[pid]
            status = entry.get("status", {})
            print(">> 完成，耗时 %.1f 分钟" % ((time.time() - t0) / 60), flush=True)
            if status.get("status_str") == "error":
                print("   执行出错：")
                print(json.dumps(status, ensure_ascii=False)[:1500])
                return 1
            outs = entry.get("outputs", {})
            files = []
            for node in outs.values():
                for im in node.get("images", []):
                    files.append(os.path.join(OUT_DIR, im.get("subfolder", ""), im.get("filename")))
            for f in files:
                size = os.path.getsize(f) if os.path.exists(f) else -1
                print("   产出图片：%s  (%.1f KB)" % (f, size / 1024))
            return 0 if files else 1
        print("   出图中 ... 已等待 %.1f 分钟" % ((time.time() - t0) / 60), flush=True)
        if time.time() - t0 > 30 * 60:
            print("   超时")
            return 1


if __name__ == "__main__":
    sys.exit(main())
