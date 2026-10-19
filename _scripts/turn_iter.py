# -*- coding: utf-8 -*-
"""迭代转头实验：以一张正面脸为起点，连续多步 img2img 把头顶到 90° 侧面

背景（本项目的实测结论）：
    从正面基图**一步** img2img 到 90° 侧面，SDXL 和 Flux 都做不到 ——
    denoise 0.55/0.70/0.85 出来全是大正面。但 **0.95 转出了约 25–30°**。
    → 说明这条路不是不通，而是"一步转不够"，需要**分步累积**。

本脚本就是那条链：
    正面 --(0.95)--> 45° --(0.95)--> 70° --(0.95)--> 90°
每一步都把上一步的产物传回服务器当新基图，并且提示词**逐步加强**朝向描述
（如果三步都用同一句"45°"，模型会把它拉回 45°，永远到不了 90°）。

用法：
    python turn_iter.py left     # 从 v23 正面脸推左侧脸
    python turn_iter.py right
"""
import urllib.request, urllib.parse, json, ssl, uuid, os, sys, time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, r"D:\xiaobai-claude code\ComfyUI\venv\Lib\site-packages")
from PIL import Image
from wd_blocks import CHAR, HAIR, SKIN, LIGHT, BGD, QUAL, WEAR, compose, VIEW_34_L, VIEW_34_R, VIEW_90_L, VIEW_90_R

BASE = "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016"
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
ROOT = r"D:\xiaobai-claude code\comfyUImd"

CKPT = "FLUX1\\flux1-dev-fp8.safetensors"
W, H = 1024, 1280
STEPS, CFG, GUID, DEN, SEED = 28, 1.0, 3.5, 0.95, 20260917

SRC = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "v23-脸部三视角", "闻灯v23-脸部正面-成品_00001_.png")

# ---- 中间态提示词：朝向描述必须一步比一步狠，否则会被拉回前一个角度 ----
V65_L = ("His head is turned far to his left, well past a three-quarter view and almost sideways. "
         "His left eye sits at the very edge of the frame, and his right eye is almost completely "
         "hidden behind the bridge of his nose so that only a sliver of the far eyebrow shows. "
         "The far cheekbone is no longer visible. His left ear is clearly visible and the nose is "
         "seen almost in profile.")
V65_R = ("His head is turned far to his right, well past a three-quarter view and almost sideways. "
         "His right eye sits at the very edge of the frame, and his left eye is almost completely "
         "hidden behind the bridge of his nose so that only a sliver of the far eyebrow shows. "
         "The far cheekbone is no longer visible. His right ear is clearly visible and the nose is "
         "seen almost in profile.")

def comp(view):
    return "Photorealistic studio headshot of %s. %s %s %s %s %s %s %s" % (
        CHAR, view, WEAR, HAIR, SKIN, LIGHT, BGD, QUAL)

DIR = (sys.argv[1] if len(sys.argv) > 1 else "left").lower()
if DIR == "left":
    STAGES = [("s1-45度", comp(VIEW_34_L)), ("s2-70度", comp(V65_L)), ("s3-90度", comp(VIEW_90_L))]
    OUTDIR = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "flux-v3-转头", "迭代-左")
else:
    STAGES = [("s1-45度", comp(VIEW_34_R)), ("s2-70度", comp(V65_R)), ("s3-90度", comp(VIEW_90_R))]
    OUTDIR = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "flux-v3-转头", "迭代-右")
os.makedirs(OUTDIR, exist_ok=True)


def raw(p, data=None, ctype=None, timeout=300):
    h = {}
    if ctype:
        h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


def upload(local, name):
    data = open(local, "rb").read()
    bd = "----wb" + uuid.uuid4().hex
    body = b""
    for k, v in (("overwrite", "true"), ("type", "input"), ("subfolder", "")):
        body += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                 % (bd, k, v)).encode()
    body += ("--%s\r\nContent-Disposition: form-data; name=\"image\"; filename=\"%s\"\r\n"
             "Content-Type: image/png\r\n\r\n" % (bd, name)).encode()
    body += data + ("\r\n--%s--\r\n" % bd).encode()
    return urllib.request.urlopen(
        urllib.request.Request(BASE + "/upload/image", data=body,
                               headers={"Content-Type": "multipart/form-data; boundary=%s" % bd}),
        timeout=300, context=ctx).read().decode()


def build(img_name, prompt, prefix):
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "2": {"class_type": "LoadImage", "inputs": {"image": img_name, "upload": "image"}},
        "3": {"class_type": "ImageScale", "inputs": {"image": ["2", 0], "upscale_method": "lanczos",
                                                     "width": W, "height": H, "crop": "center"}},
        "4": {"class_type": "VAEEncode", "inputs": {"pixels": ["3", 0], "vae": ["1", 2]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "6": {"class_type": "FluxGuidance", "inputs": {"conditioning": ["5", 0], "guidance": GUID}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["1", 1]}},
        "8": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["4", 0],
            "seed": SEED, "steps": STEPS, "cfg": CFG, "sampler_name": "euler",
            "scheduler": "simple", "denoise": DEN}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["1", 2]}},
        "10": {"class_type": "SaveImage", "inputs": {"images": ["9", 0], "filename_prefix": prefix}},
    }


# ---- 起点：v23 正面脸 ----
start_local = os.path.join(SCRIPT_DIR, "_wf", "flux_turn_start_%dx%d.png" % (W, H))
Image.open(SRC).convert("RGB").resize((W, H), Image.LANCZOS).save(start_local, "PNG", optimize=True)
cur_name = "wendeng_turn_in_%s.png" % DIR
print("起点上传 ->", upload(start_local, cur_name)[:120])

t_all = time.time()
for i, (tag, prompt) in enumerate(STAGES):
    prefix = "闻灯FluxV3-迭代转头-%s-%s" % (DIR, tag)
    print("\n===== 第 %d 步  %s  (denoise %.2f) =====" % (i + 1, tag, DEN))
    res = json.loads(raw("/prompt", json.dumps({"prompt": build(cur_name, prompt, prefix),
                                                "client_id": str(uuid.uuid4())}).encode(),
                         "application/json", 120).decode())
    if res.get("node_errors"):
        print("  ★ node_errors:", json.dumps(res["node_errors"], ensure_ascii=False)[:1000]); sys.exit(1)
    pid = res["prompt_id"]
    t0, done = time.time(), None
    for _ in range(150):
        time.sleep(4)
        h = json.loads(raw("/history/" + pid, None, None, 60).decode("utf-8", "replace"))
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("status_str") == "error":
                for m in st.get("messages", []):
                    if m[0] == "execution_error":
                        print("  ★ ERROR %s" % m[1].get("exception_message", "")[:300])
                sys.exit(1)
            done = h[pid].get("outputs", {}); break
    if done is None:
        print("  ★ 超时"); sys.exit(1)
    print("  用时 %.0f 秒" % (time.time() - t0))

    got = None
    for nid, o in done.items():
        for im in o.get("images", []):
            q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                        "type": im.get("type", "output")})
            dst = os.path.join(OUTDIR, im["filename"])
            d = raw("/view?" + q)
            open(dst, "wb").write(d)
            got = dst
            print("  saved %s  %.1f KB" % (im["filename"], len(d) / 1024))
    # 把这一步的产物当成下一步的基图
    cur_name = "wendeng_turn_%s_s%d.png" % (DIR, i + 1)
    print("  下一步基图 <-", upload(got, cur_name)[:120])

print("\n全部完成，总用时 %.0f 秒 -> %s" % (time.time() - t_all, OUTDIR))
