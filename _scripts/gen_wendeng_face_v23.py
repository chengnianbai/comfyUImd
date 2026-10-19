# -*- coding: utf-8 -*-
"""闻灯 v23 —— 按《角色生成约束 V1.0》生成脸部三视角（正 / 左 / 右）

为什么要用 img2img 而不是文生图：
    约束 H02/§2.1 要求「三张图必须属于同一个角色、同一张脸」，H09/H10 要求全身图
    必须用已确认的脸做身份参考。但本项目已两次实测：纯文生图下，
    同一个 seed + 同一组 token，只要提示词改一个字，出来就是另一个人（v21 / v22）。
    该机未装 IPAdapter / Impact-Pack / ApplyControlNet → 唯一可用的一致手段是 img2img。
    探针已证实：以「已确认正脸」为基图做 img2img，人物身份保留得非常好。

本版做的事：
    以 `闻灯-正脸-已确认_成品.png`（v13 那张被用户认可的脸，RAW 版，浅灰棚底）
    为唯一身份基图，用不同 denoise 派生视角。**只改视角词，不改角色词。**

用法：
    python gen_wendeng_face_v23.py --check          # 只做 token 校验
    python gen_wendeng_face_v23.py                  # 全跑（正面 + 侧面 denoise 扫描）
"""
import urllib.request, urllib.parse, json, ssl, time, uuid, os, sys

BASE = "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016"
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE

ROOT = r"D:\xiaobai-claude code\comfyUImd\系列-夜市百相簿/02-角色/闻灯/设定图"
BASE_IMG = r"D:\xiaobai-claude code\comfyUImd\系列-夜市百相簿/02-角色/闻灯/设定图\脸部素材集\闻灯-正脸-已确认_成品.png"
OUTDIR = os.path.join(ROOT, "v23-脸部三视角")
UPLOAD_NAME = "wendeng_face_base.png"

CKPT = "leosamsHelloworldXL_helloworldXL70.safetensors"
UPSCALER = "4x-UltraSharp (1).pth"
W, H = 896, 1152
SCALE_BY = 0.5
STEPS_1, CFG_1 = 30, 10.0
STEPS_2, CFG_2, DEN_2 = 20, 10.0, 0.25
SEED = 20260917

CHECK = "--check" in sys.argv

# ==================== 身份锚点块（逐字继承 v13 已确认脸，勿改）====================
# 来源：memory\角色视觉锚点-锁定.md 锚点 #1/#3/#4/#5
CHAR = ("1boy, solo, 24 year old east asian man, masculine face, strong jaw, "
        "messy wavy black hair, small mole at outer eye corner")
COLLAR = "faded blue shirt collar, dark coat collar"      # 锚点 #8/#9（脸部图只露领口）
BGD = "pure white background"                              # 约束 §12（跑完仍需 post_whitebg 校正）

# ==================== 约束 §16 脸部关键词 + §13 影棚光 ====================
# 注意：正向必须有纹理词，否则 §13「均匀柔和光」会把皮肤磨成塑料（附录 B.2 裁决）
FACE_DETAIL = ("detailed face, detailed eyes, iris detail, thick eyebrows, stubble, "
               "small mole at outer eye corner, visible skin pores, skin texture, "
               "peach fuzz, individual hair strands")
LIGHT = "soft studio lighting, even lighting, neutral lighting, natural skin tone, consistent exposure"

# ==================== 负向（三段两级合并）====================
# ⚠️ 不放脸部词（会导致模型干脆不画脸）；不放 freckles（v13 的雀斑群是真实感来源）；
#    不堆种族词（v21 漂移元凶）；不放 smooth skin / plastic skin（会把皮肤压成蜡像）
N1 = ("1girl, female, feminine face, delicate, fragile, soft features, soft round face, "
      "pretty boy, boyish face, bishounen, makeup, lipstick, rosy lips, eyeshadow, "
      "teenage, child, narrow face, pale skin, blonde hair, long hair, straight hair, "
      "slicked back hair, undercut, side part, neat hair")
N2 = ("dark background, grey background, gradient background, vignette, harsh shadow, "
      "busy background, scenery, room, street, furniture, prop, holding object, "
      "full body, multiple views, extra people, extra fingers, bad hands, watermark, text, "
      "signature, logo, blurry, lowres, jpeg artifacts")
N3_FACE = ("airbrushed, over-smoothed, beauty filter, retouched, doll, 3d render, cgi, "
           "painting, illustration, anime, censored, cropped head, fisheye, wide angle, "
           "dramatic lighting, colored lighting, complex shadow")

# ==================== 视角表 ====================
# 正面：几乎不动基图，只把它清干净并居中 → 低 denoise
# 侧面：需要转头，denoise 必须够大；用扫描找出「能转头但脸还在」的临界点
VIEWS = [
    ("脸部正面",  "front view, looking at viewer, face centered", 0.30),
    ("脸部侧面a", "side profile view, face centered", 0.62),
    ("脸部侧面b", "side profile view, face centered", 0.75),
    ("脸部侧面c", "side profile view, face centered", 0.86),
]

# ==================== token 校验 ====================
sys.path.insert(0, r"D:\xiaobai-claude code\ComfyUI\venv\Lib\site-packages")
from transformers import CLIPTokenizer
tk = CLIPTokenizer.from_pretrained(r"D:\xiaobai-claude code\ComfyUI\comfy\sd1_tokenizer")


def tok(t):
    return len(tk.encode(t, add_special_tokens=False))


A_of = lambda v: "%s, face closeup, head and shoulders, %s, %s, %s" % (v, CHAR, COLLAR, BGD)
B_of = lambda: "%s, %s, sharp focus, photorealistic" % (FACE_DETAIL, LIGHT)

bad = []
print("=== token 校验（上限 75）===")
for nm, t in [("N1", N1), ("N2", N2), ("N3", N3_FACE), ("FACE_B", B_of())]:
    n = tok(t)
    print("  %-10s %3d/75 %s" % (nm, n, "OK" if n <= 75 else "★超限★"))
    if n > 75:
        bad.append(nm)
for vn, v, den in VIEWS:
    n = tok(A_of(v))
    print("  %-10s A   %3d/75 %s   (denoise %.2f)" % (vn, n, "OK" if n <= 75 else "★超限★", den))
    if n > 75:
        bad.append(vn + "A")
if bad:
    print("\n★ 有段落超限，未提交：", bad)
    sys.exit(1)
print("\n全部在 75 以内")
if CHECK:
    sys.exit(0)


# ==================== HTTP ====================
def get(p, timeout=60):
    return urllib.request.urlopen(BASE + p, timeout=timeout, context=ctx).read()


def post_json(p, obj, timeout=60):
    r = urllib.request.Request(BASE + p, data=json.dumps(obj).encode("utf-8"),
                               headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=timeout, context=ctx).read().decode())


# ==================== 上传身份基图 ====================
# ⚠️ 坑：直接传 5.8MB 的 1792x2304 原图会 `TimeoutError: The write operation timed out`
#    （探针时 4.8MB 勉强过，5.8MB 就超了）。→ 本地先缩到出图尺寸 896x1152 再传，
#    体积降到 ~1.5MB，顺带省掉一次服务器端缩放。
print("\n=== 上传身份基图 ===")
sys.path.insert(0, r"D:\xiaobai-claude code\ComfyUI\venv\Lib\site-packages")
from PIL import Image

TMPDIR = os.path.join(ROOT, "_tmp")
os.makedirs(TMPDIR, exist_ok=True)
LOCAL_BASE = os.path.join(TMPDIR, "face_base_%dx%d.png" % (W, H))
im = Image.open(BASE_IMG).convert("RGB")
print("  源: %s  %dx%d  %.1f KB" % (os.path.basename(BASE_IMG), im.size[0], im.size[1],
                                   os.path.getsize(BASE_IMG) / 1024))
im = im.resize((W, H), Image.LANCZOS)
im.save(LOCAL_BASE, "PNG", optimize=True)
print("  压到: %s  %dx%d  %.1f KB" % (os.path.basename(LOCAL_BASE), W, H,
                                     os.path.getsize(LOCAL_BASE) / 1024))


def upload(local, name, tries=3):
    bd = "----wb" + uuid.uuid4().hex
    body = b""
    for k, v in (("overwrite", "true"), ("type", "input"), ("subfolder", "")):
        body += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n" % (bd, k, v)).encode()
    body += ("--%s\r\nContent-Disposition: form-data; name=\"image\"; filename=\"%s\"\r\n"
             "Content-Type: image/png\r\n\r\n" % (bd, name)).encode()
    body += open(local, "rb").read()
    body += ("\r\n--%s--\r\n" % bd).encode()
    last = None
    for t in range(tries):
        try:
            r = urllib.request.Request(BASE + "/upload/image", data=body,
                                       headers={"Content-Type": "multipart/form-data; boundary=%s" % bd})
            return urllib.request.urlopen(r, timeout=300, context=ctx).read().decode()
        except Exception as e:
            last = e
            print("    第 %d 次失败: %s" % (t + 1, e))
            time.sleep(3)
    raise last


print("  ->", upload(LOCAL_BASE, UPLOAD_NAME)[:200])

CLIP = ["2", 0]


def build(A, B, den):
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "2": {"class_type": "CLIPSetLastLayer", "inputs": {"clip": ["1", 1], "stop_at_clip_layer": -1}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": A, "clip": CLIP}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": B, "clip": CLIP}},
        "5": {"class_type": "ConditioningCombine", "inputs": {"conditioning_1": ["3", 0], "conditioning_2": ["4", 0]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": N1, "clip": CLIP}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": N2, "clip": CLIP}},
        "8": {"class_type": "CLIPTextEncode", "inputs": {"text": N3_FACE, "clip": CLIP}},
        "9": {"class_type": "ConditioningCombine", "inputs": {"conditioning_1": ["6", 0], "conditioning_2": ["7", 0]}},
        "10": {"class_type": "ConditioningCombine", "inputs": {"conditioning_1": ["9", 0], "conditioning_2": ["8", 0]}},
        # ★ 身份基图：缩到出图尺寸后编码成 latent，作为 img2img 起点
        "11": {"class_type": "LoadImage", "inputs": {"image": UPLOAD_NAME, "upload": "image"}},
        "12": {"class_type": "ImageScale",
               "inputs": {"image": ["11", 0], "upscale_method": "lanczos",
                          "width": W, "height": H, "crop": "center"}},
        "13": {"class_type": "VAEEncode", "inputs": {"pixels": ["12", 0], "vae": ["1", 2]}},
        "14": {"class_type": "KSampler", "inputs": {"seed": SEED, "steps": STEPS_1, "cfg": CFG_1,
                                                    "sampler_name": "dpmpp_2m", "scheduler": "karras",
                                                    "denoise": den, "model": ["1", 0], "positive": ["5", 0],
                                                    "negative": ["10", 0], "latent_image": ["13", 0]}},
        "15": {"class_type": "VAEDecode", "inputs": {"samples": ["14", 0], "vae": ["1", 2]}},
        "16": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": UPSCALER}},
        "17": {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["16", 0], "image": ["15", 0]}},
        "18": {"class_type": "ImageScaleBy",
               "inputs": {"upscale_method": "lanczos", "scale_by": SCALE_BY, "image": ["17", 0]}},
        "19": {"class_type": "VAEEncode", "inputs": {"pixels": ["18", 0], "vae": ["1", 2]}},
        "20": {"class_type": "KSampler", "inputs": {"seed": SEED, "steps": STEPS_2, "cfg": CFG_2,
                                                    "sampler_name": "dpmpp_2m", "scheduler": "karras",
                                                    "denoise": DEN_2, "model": ["1", 0], "positive": ["5", 0],
                                                    "negative": ["10", 0], "latent_image": ["19", 0]}},
        "21": {"class_type": "VAEDecode", "inputs": {"samples": ["20", 0], "vae": ["1", 2]}},
        "22": {"class_type": "SaveImage",
               "inputs": {"filename_prefix": "闻灯v23-%s-草稿" % "PLACEHOLDER", "images": ["15", 0]}},
        "23": {"class_type": "SaveImage",
               "inputs": {"filename_prefix": "闻灯v23-%s-成品" % "PLACEHOLDER", "images": ["21", 0]}},
    }


print("\n底模=%s  %dx%d  seed=%d" % (CKPT, W, H, SEED))
print("★ 身份基图：闻灯-正脸-已确认（v13）  仅改视角词 + denoise\n")

jobs = []
for vn, v, den in VIEWS:
    wf = build(A_of(v), B_of(), den)
    wf["22"]["inputs"]["filename_prefix"] = "闻灯v23-%s-草稿" % vn
    wf["23"]["inputs"]["filename_prefix"] = "闻灯v23-%s-成品" % vn
    sub = post_json("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
    if sub.get("node_errors"):
        print("  ★ %s 被拒: %s" % (vn, json.dumps(sub["node_errors"], ensure_ascii=False)[:500]))
        continue
    jobs.append((vn, sub["prompt_id"]))
    print("submitted %-10s denoise=%.2f -> %s" % (vn, den, sub["prompt_id"]))

print("\n等待生成...")
done = {}
for i in range(400):
    time.sleep(3)
    for vn, pid in jobs:
        if vn in done:
            continue
        h = json.loads(get("/history/" + pid).decode("utf-8", "replace"))
        if pid in h:
            if h[pid].get("status", {}).get("status_str") == "error":
                print("  %s ERROR: %s" % (vn, json.dumps(h[pid]["status"], ensure_ascii=False)[:600]))
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
            q = urllib.parse.urlencode({"filename": im["filename"],
                                        "subfolder": im.get("subfolder", ""),
                                        "type": im.get("type", "output")})
            dst = os.path.join(OUTDIR, im["filename"])
            open(dst, "wb").write(get("/view?" + q, 180))
            print("  saved %-46s %8.1f KB" % (im["filename"], os.path.getsize(dst) / 1024))
print("\nOK")
