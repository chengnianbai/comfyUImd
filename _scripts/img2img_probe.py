# -*- coding: utf-8 -*-
"""图生图通道探针 —— 验证「已确认的脸 → 服务器基图」这条链能不能走通。

背景（为什么必须做这件事）：
    约束文件 H09/H10 要求「全身图必须用已确认的脸做身份参考、不得重新设计脸」。
    本项目已两次实测：纯文生图下，同一个 seed + 同一组 token，只要提示词改一个字，
    出来就是另一个人（v21 事故、v22 复现）。
    该机未装 IPAdapter / Impact-Pack / ApplyControlNet → 唯一可用的一致手段是 img2img。

本脚本验证三件事：
    1. POST /upload/image 能不能把本地图传到服务器 input 目录
    2. LoadImage 能不能读到它
    3. 最简 img2img 链路（LoadImage → VAEEncode → KSampler → VAEDecode）能不能出图

用法： python img2img_probe.py
"""
import urllib.request, urllib.parse, json, ssl, time, uuid, os, sys, mimetypes

BASE = "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016"
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE

SRC = r"D:\xiaobai-claude code\comfyUImd\系列-夜市百相簿/02-角色/闻灯/设定图\脸部素材集\闻灯-正脸-已确认_成品-白底.png"
OUTDIR = r"D:\xiaobai-claude code\comfyUImd\系列-夜市百相簿/02-角色/闻灯/设定图\_img2img探针"
NAME = "wendeng_face_ref.png"


def raw(path, data=None, ctype=None, timeout=120):
    h = {}
    if ctype:
        h["Content-Type"] = ctype
    r = urllib.request.Request(BASE + path, data=data, headers=h)
    return urllib.request.urlopen(r, timeout=timeout, context=ctx).read()


def get_json(path, timeout=60):
    return json.loads(raw(path, timeout=timeout).decode("utf-8", "replace"))


# ---------- 1. 上传 ----------
print("=== 1. 上传基图 ===")
print("  源文件: %s" % SRC)
print("  大小: %.1f KB" % (os.path.getsize(SRC) / 1024))

boundary = "----wb" + uuid.uuid4().hex
body = b""
for k, v in (("overwrite", "true"), ("type", "input"), ("subfolder", "")):
    body += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n" % (boundary, k, v)).encode()
body += ("--%s\r\nContent-Disposition: form-data; name=\"image\"; filename=\"%s\"\r\n"
         "Content-Type: image/png\r\n\r\n" % (boundary, NAME)).encode()
body += open(SRC, "rb").read()
body += ("\r\n--%s--\r\n" % boundary).encode()

try:
    resp = raw("/upload/image", body, "multipart/form-data; boundary=%s" % boundary)
    print("  上传返回:", resp.decode("utf-8", "replace")[:300])
    uploaded = True
except Exception as e:
    print("  ★ 上传失败:", e)
    uploaded = False

# ---------- 2. 确认服务器能看到 ----------
print("\n=== 2. 服务器 input 目录 ===")
try:
    d = get_json("/internal/files/input")
    names = [x["name"] if isinstance(x, dict) else x for x in d]
    print("  文件数: %d" % len(names))
    print("  含基图:", any(NAME in str(n) for n in names))
    for n in names[:12]:
        print("    -", n)
except Exception as e:
    print("  列目录失败:", e)

print("\n  节点可用性:")
nodes = get_json("/object_info", timeout=90)
for n in ("LoadImage", "VAEEncode", "SetLatentNoiseMask", "KSampler", "VAEDecode"):
    print("    %-20s %s" % (n, "OK" if n in nodes else "MISSING"))

if not uploaded:
    print("\n★ 上传没成功，中止")
    sys.exit(1)

# ---------- 3. 最简 img2img ----------
print("\n=== 3. 最简 img2img（denoise 0.45，仅验证链路）===")
CLIP = ["2", 0]
POS = ("face closeup, head and shoulders, front view, looking at viewer, "
       "1boy, solo, 24 year old east asian man, masculine face, strong jaw, "
       "messy wavy black hair, small mole at outer eye corner, pure white background")
NEG = "1girl, feminine face, makeup, blurry, lowres, watermark, text"

wf = {
    "1": {"class_type": "CheckpointLoaderSimple",
          "inputs": {"ckpt_name": "leosamsHelloworldXL_helloworldXL70.safetensors"}},
    "2": {"class_type": "CLIPSetLastLayer",
          "inputs": {"clip": ["1", 1], "stop_at_clip_layer": -1}},
    "3": {"class_type": "CLIPTextEncode", "inputs": {"text": POS, "clip": CLIP}},
    "4": {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": CLIP}},
    "5": {"class_type": "LoadImage", "inputs": {"image": NAME, "upload": "image"}},
    "6": {"class_type": "VAEEncode", "inputs": {"pixels": ["5", 0], "vae": ["1", 2]}},
    "7": {"class_type": "KSampler",
          "inputs": {"seed": 20260917, "steps": 25, "cfg": 8.0, "sampler_name": "dpmpp_2m",
                     "scheduler": "karras", "denoise": 0.45, "model": ["1", 0],
                     "positive": ["3", 0], "negative": ["4", 0], "latent_image": ["6", 0]}},
    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["1", 2]}},
    "9": {"class_type": "SaveImage",
          "inputs": {"filename_prefix": "IMG2IMG探针", "images": ["8", 0]}},
}
try:
    r = urllib.request.Request(BASE + "/prompt",
                               data=json.dumps({"prompt": wf, "client_id": str(uuid.uuid4())}).encode(),
                               headers={"Content-Type": "application/json"})
    sub = json.loads(urllib.request.urlopen(r, timeout=60, context=ctx).read().decode())
    print("  提交:", json.dumps(sub)[:400])
    if "error" in sub or "node_errors" in sub and sub["node_errors"]:
        print("  ★ 提交被拒：", json.dumps(sub.get("node_errors", sub), ensure_ascii=False)[:800])
        sys.exit(1)
    pid = sub["prompt_id"]
except Exception as e:
    print("  ★ 提交失败:", e)
    sys.exit(1)

outs = None
for i in range(120):
    time.sleep(2)
    h = get_json("/history/" + pid)
    if pid in h:
        st = h[pid].get("status", {}).get("status_str")
        if st == "error":
            print("  ★ 执行出错:", json.dumps(h[pid]["status"], ensure_ascii=False)[:800])
            sys.exit(1)
        outs = h[pid].get("outputs", {})
        print("  完成 (%.0fs)" % ((i + 1) * 2))
        break
if not outs:
    print("  ★ 超时")
    sys.exit(1)

os.makedirs(OUTDIR, exist_ok=True)
for nid, o in outs.items():
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"],
                                    "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        dst = os.path.join(OUTDIR, im["filename"])
        open(dst, "wb").write(raw("/view?" + q))
        print("  saved %s (%.0f KB)" % (im["filename"], os.path.getsize(dst) / 1024))

print("\n★★ 结论：img2img 链路可用 —— H09/H10 有落地手段了。")
