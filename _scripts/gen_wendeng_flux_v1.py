# -*- coding: utf-8 -*-
"""闻灯 Flux 版脸部生成 —— FLUX.1-dev-fp8 一体化 checkpoint

与 SDXL 版的关键差异（很重要，参数不通用）：
    * CFG 必须 ≈ 1.0（套 SDXL 的 10 会炸图）
    * sampler = euler, scheduler = simple, steps 20~30
    * **不需要 CLIPSetLastLayer**（不设 clip skip）
    * CFG=1 时负向词无效 —— 负面内容只能靠正向措辞排除
    * 文本编码器是 T5（512 token），**不再受 SD 1.5 的 75 token 硬上限约束**
    * ★ 提示词要用**自然语言句子**描述，而不是 SDXL 那种逗号标签堆叠
      （Flux 对自然语言的空间/方位关系理解明显更强 → 侧脸朝向有戏）

两条路线同时试：
    T 线 = 纯文生图（正面 / 左侧面 / 右侧面）—— 看 Flux 能不能自己把朝向做对
    I 线 = 图生图（以已确认正脸为身份基图，高 denoise 转头）—— 保身份

用法：
    python gen_wendeng_flux_v1.py [--only text|i2i]
"""
import urllib.request, urllib.parse, json, ssl, time, uuid, os, sys

# PIL 在 ComfyUI 的 venv 里（托管 python 没装）→ 必须在任何 PIL 导入之前挂路径
sys.path.insert(0, r"D:\xiaobai-claude code\ComfyUI\venv\Lib\site-packages")
from PIL import Image

BASE = "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016"
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE

ROOT = r"D:\xiaobai-claude code\comfyUImd\系列-夜市百相簿/02-角色/闻灯/设定图"
OUTDIR = os.path.join(ROOT, "flux-v1-脸部")

CKPT = "FLUX1\\flux1-dev-fp8.safetensors"
UPSCALER = "4x-UltraSharp (1).pth"
W, H = 1024, 1280
STEPS = 28
GUIDANCE = 3.5
SCALE_BY = 0.5
STEPS_2, DEN_2 = 18, 0.25
SEED = 20260917

ONLY = None
if "--only" in sys.argv:
    ONLY = sys.argv[sys.argv.index("--only") + 1]

# ==================== 身份描述（自然语言，Flux 用）====================
# 锚点来源 memory\角色视觉锚点-锁定.md：#1 年龄性别 / #4 黑发微卷 / #5 眼尾小痣
#                              #3 偏瘦有韧性 / #6 睡眠不足 / #8/#9 发白蓝衬衫+深色旧风衣
CHAR = ("a 24-year-old East Asian man with a lean wiry build, messy wavy black hair, "
        "thick dark eyebrows, a strong masculine jaw, light stubble, deep-set dark eyes "
        "with faint shadows underneath, and a small beauty mark at the outer corner of his eye")

# 约束 §12 纯白背景 + §13 影棚光；纹理词抵抗磨皮（附录 B.2 裁决）
STYLE = ("Plain pure white seamless background, absolutely no props and no other people. "
         "Soft even studio lighting, neutral white light, no harsh shadows, natural realistic "
         "skin with visible pores and fine facial hair, true-to-life skin tone, sharp focus, "
         "shot on an 85mm lens at f/4, photorealistic, high detail.")

# ==================== T 线：纯文生图 ====================
TEXT_VIEWS = [
    ("脸部正面",
     "Photorealistic studio headshot of %s. He faces the camera directly, head level, "
     "shoulders square, calm neutral expression, looking straight into the lens. He wears a "
     "faded blue collared shirt with a dark worn coat collar. %s" % (CHAR, STYLE)),

    ("脸部左侧面",
     "Photorealistic studio headshot in a true full left profile view of %s. His head is turned "
     "a full 90 degrees so the camera sees only the LEFT side of his face; only his left eye, "
     "left eyebrow, left ear and the left line of his nose and jaw are visible. The right side "
     "of his face is completely hidden. He wears a faded blue collared shirt with a dark worn "
     "coat collar. %s" % (CHAR, STYLE)),

    ("脸部右侧面",
     "Photorealistic studio headshot in a true full right profile view of %s. His head is turned "
     "a full 90 degrees so the camera sees only the RIGHT side of his face; only his right eye, "
     "right eyebrow, right ear and the right line of his nose and jaw are visible. The left side "
     "of his face is completely hidden. He wears a faded blue collared shirt with a dark worn "
     "coat collar. %s" % (CHAR, STYLE)),
]

# ==================== I 线：图生图 ====================
I2I_VIEWS = [
    ("脸部侧面转a", "left profile", 0.80),
    ("脸部侧面转b", "left profile", 0.92),
]

PROFILE_PROMPT = ("Photorealistic studio headshot in a true full left profile view of %s. "
                  "His head is turned 90 degrees so only the LEFT side of his face is visible. "
                  "Preserve his exact identity: the same face, the same eyes, the same eyebrows, "
                  "the same nose, the same jaw, the same hair and the same age as the reference "
                  "image. %s" % (CHAR, STYLE))


# ==================== HTTP ====================
def raw(p, data=None, ctype=None, timeout=180):
    h = {}
    if ctype:
        h["Content-Type"] = ctype
    r = urllib.request.Request(BASE + p, data=data, headers=h)
    return urllib.request.urlopen(r, timeout=timeout, context=ctx).read()


def get_json(p, timeout=60):
    return json.loads(raw(p, timeout=timeout).decode("utf-8", "replace"))


def post_json(p, obj, timeout=90):
    return json.loads(raw(p, json.dumps(obj).encode("utf-8"), "application/json", timeout).decode())


NODES = get_json("/object_info", timeout=120)
HAS_GUIDANCE = "FluxGuidance" in NODES
print("FluxGuidance 节点: %s" % ("有" if HAS_GUIDANCE else "无"))


def build_text(pos):
    wf = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": pos, "clip": ["1", 1]}},
        "3": {"class_type": "EmptyLatentImage", "inputs": {"width": W, "height": H, "batch_size": 1}},
        "5": {"class_type": "VAEDecode", "inputs": {"samples": ["4", 0], "vae": ["1", 2]}},
        "8": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": UPSCALER}},
        "9": {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["8", 0], "image": ["5", 0]}},
        "10": {"class_type": "ImageScaleBy",
               "inputs": {"upscale_method": "lanczos", "scale_by": SCALE_BY, "image": ["9", 0]}},
        "11": {"class_type": "VAEEncode", "inputs": {"pixels": ["10", 0], "vae": ["1", 2]}},
        "12": {"class_type": "KSampler",
               "inputs": {"seed": SEED, "steps": STEPS_2, "cfg": 1.0, "sampler_name": "euler",
                          "scheduler": "simple", "denoise": DEN_2, "model": ["1", 0],
                          "positive": ["2", 0], "negative": ["2", 0], "latent_image": ["11", 0]}},
        "13": {"class_type": "VAEDecode", "inputs": {"samples": ["12", 0], "vae": ["1", 2]}},
    }
    pos_src = ["2", 0]
    if HAS_GUIDANCE:
        wf["2b"] = {"class_type": "FluxGuidance",
                    "inputs": {"conditioning": ["2", 0], "guidance": GUIDANCE}}
        pos_src = ["2b", 0]
    wf["4"] = {"class_type": "KSampler",
               "inputs": {"seed": SEED, "steps": STEPS, "cfg": 1.0, "sampler_name": "euler",
                          "scheduler": "simple", "denoise": 1.0, "model": ["1", 0],
                          "positive": pos_src, "negative": ["2", 0], "latent_image": ["3", 0]}}
    return wf


def build_i2i(pos, den, img_name):
    wf = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": pos, "clip": ["1", 1]}},
        # ★ 身份基图：LoadImage(IMAGE) 必须先过 VAEEncode 变成 LATENT，才能喂给 KSampler
        "16": {"class_type": "LoadImage", "inputs": {"image": img_name, "upload": "image"}},
        "17": {"class_type": "VAEEncode", "inputs": {"pixels": ["16", 0], "vae": ["1", 2]}},
        "5": {"class_type": "VAEDecode", "inputs": {"samples": ["4", 0], "vae": ["1", 2]}},
        "8": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": UPSCALER}},
        "9": {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["8", 0], "image": ["5", 0]}},
        "10": {"class_type": "ImageScaleBy",
               "inputs": {"upscale_method": "lanczos", "scale_by": SCALE_BY, "image": ["9", 0]}},
        "11": {"class_type": "VAEEncode", "inputs": {"pixels": ["10", 0], "vae": ["1", 2]}},
        "12": {"class_type": "KSampler",
               "inputs": {"seed": SEED, "steps": STEPS_2, "cfg": 1.0, "sampler_name": "euler",
                          "scheduler": "simple", "denoise": DEN_2, "model": ["1", 0],
                          "positive": ["2", 0], "negative": ["2", 0], "latent_image": ["11", 0]}},
        "13": {"class_type": "VAEDecode", "inputs": {"samples": ["12", 0], "vae": ["1", 2]}},
    }
    pos_src = ["2", 0]
    if HAS_GUIDANCE:
        wf["2b"] = {"class_type": "FluxGuidance",
                    "inputs": {"conditioning": ["2", 0], "guidance": GUIDANCE}}
        pos_src = ["2b", 0]
    wf["4"] = {"class_type": "KSampler",
               "inputs": {"seed": SEED, "steps": STEPS, "cfg": 1.0, "sampler_name": "euler",
                          "scheduler": "simple", "denoise": den, "model": ["1", 0],
                          "positive": pos_src, "negative": ["2", 0], "latent_image": ["17", 0]}}
    return wf


def submit(wf, tag):
    sub = post_json("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
    if sub.get("node_errors"):
        print("  ★ %s 被拒: %s" % (tag, json.dumps(sub["node_errors"], ensure_ascii=False)[:600]))
        return None
    print("  submitted %-14s -> %s" % (tag, sub["prompt_id"]))
    return sub["prompt_id"]


def upload_image(local, name, tries=5):
    """上传基图。⚠️ 实测这条通道很脆：1.5MB 能过、1.9MB 可能 ConnectionReset / 写超时
    → 必须带重试，并在连续失败时降级成 JPEG（体积砍到 1/5）。"""
    sys.path.insert(0, r"D:\xiaobai-claude code\ComfyUI\venv\Lib\site-packages")
    from PIL import Image
    cands = [(local, "image/png", name)]
    jp = local.rsplit(".", 1)[0] + ".jpg"
    Image.open(local).convert("RGB").save(jp, "JPEG", quality=95, subsampling=0)
    cands.append((jp, "image/jpeg", name.rsplit(".", 1)[0] + ".jpg"))

    last = None
    for path, mime, fname in cands:
        data = open(path, "rb").read()
        print("    尝试 %s (%.1f KB)" % (os.path.basename(path), len(data) / 1024))
        for t in range(tries):
            bd = "----wb" + uuid.uuid4().hex
            body = b""
            for k, v in (("overwrite", "true"), ("type", "input"), ("subfolder", "")):
                body += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n" % (bd, k, v)).encode()
            body += ("--%s\r\nContent-Disposition: form-data; name=\"image\"; filename=\"%s\"\r\n"
                     "Content-Type: %s\r\n\r\n" % (bd, fname, mime)).encode()
            body += data
            body += ("\r\n--%s--\r\n" % bd).encode()
            try:
                r = urllib.request.Request(BASE + "/upload/image", data=body,
                                           headers={"Content-Type": "multipart/form-data; boundary=%s" % bd})
                return fname, urllib.request.urlopen(r, timeout=300, context=ctx).read().decode()
            except Exception as e:
                last = e
                print("      第 %d 次失败: %s" % (t + 1, type(e).__name__))
                time.sleep(4)
    raise last


# ==================== 上传身份基图 ====================
LOCAL_BASE = os.path.join(ROOT, "_tmp", "face_base_%dx%d.png" % (W, H))
UPLOAD_NAME = "flux_face_base.png"
if ONLY != "text":
    from PIL import Image as _I
    SRC = os.path.join(ROOT, "脸部素材集", "闻灯-正脸-已确认_成品.png")
    os.makedirs(os.path.dirname(LOCAL_BASE), exist_ok=True)
    _I.open(SRC).convert("RGB").resize((W, H), _I.LANCZOS).save(LOCAL_BASE, "PNG", optimize=True)
    print("=== 上传身份基图 (%dx%d, %.1f KB) ===" % (W, H, os.path.getsize(LOCAL_BASE) / 1024))
    UPLOAD_NAME, resp = upload_image(LOCAL_BASE, UPLOAD_NAME)
    print("  ->", resp[:200])

print("\n底模=%s  %dx%d  steps=%d  cfg=1.0  guidance=%.1f  seed=%d\n" % (CKPT, W, H, STEPS, GUIDANCE, SEED))

jobs = []
if ONLY in (None, "text"):
    for vn, p in TEXT_VIEWS:
        wf = build_text(p)
        wf["14"] = {"class_type": "SaveImage",
                    "inputs": {"filename_prefix": "闻灯flux-%s-草稿" % vn, "images": ["5", 0]}}
        wf["15"] = {"class_type": "SaveImage",
                    "inputs": {"filename_prefix": "闻灯flux-%s-成品" % vn, "images": ["13", 0]}}
        pid = submit(wf, "T:" + vn)
        if pid:
            jobs.append((vn, pid))

if ONLY in (None, "i2i"):
    for vn, _, den in I2I_VIEWS:
        wf = build_i2i(PROFILE_PROMPT, den, UPLOAD_NAME)
        wf["14"] = {"class_type": "SaveImage",
                    "inputs": {"filename_prefix": "闻灯flux-%s-草稿" % vn, "images": ["5", 0]}}
        wf["15"] = {"class_type": "SaveImage",
                    "inputs": {"filename_prefix": "闻灯flux-%s-成品" % vn, "images": ["13", 0]}}
        pid = submit(wf, "I:%s(%.2f)" % (vn, den))
        if pid:
            jobs.append((vn, pid))

print("\n等待生成...")
done = {}
for i in range(500):
    time.sleep(4)
    for vn, pid in jobs:
        if vn in done:
            continue
        try:
            h = json.loads(raw("/history/" + pid).decode("utf-8", "replace"))
        except Exception as e:
            continue
        if pid in h:
            if h[pid].get("status", {}).get("status_str") == "error":
                for m in h[pid]["status"].get("messages", []):
                    if m[0] == "execution_error":
                        print("  ★ %s ERROR %s: %s" % (vn, m[1].get("node_type"), m[1].get("exception_message", "")[:300]))
                done[vn] = None
            else:
                done[vn] = h[pid].get("outputs", {})
                print("  %s 完成 (%.0fs)" % (vn, (i + 1) * 4))
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
            open(dst, "wb").write(raw("/view?" + q, timeout=180))
            print("  saved %-50s %8.1f KB" % (im["filename"], os.path.getsize(dst) / 1024))
print("\nOK")
