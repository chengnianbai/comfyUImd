# -*- coding: utf-8 -*-
"""闻灯 · Flux「质感修复」对照批次 flux-v5 —— 构建并推送 UI 格式工作流

════════════════════════ 一、诊断（已由免费实验坐实） ════════════════════════
用户对 flux-v2（Flux img2img 0.30 / 正面）的评价：
    「生成的还可以，就是皮肤和头发质感不够真实」

★ 免费实验一：1:1 裁切对比（zoom_sheet.py，不烧豆）
    · v23(SDXL) = 毛孔 / 细绒毛 / 痣群 / 一根根眉毛 / 干爽飞散发丝
    · flux-v2   = 皮肤发蜡有油光 / 眉毛糊 / 头发油亮定型
    · 且 flux-v2 是 2048x2560、v23 只有 1792x2304 —— 分辨率更高的反而更糊
      ⇒ 质感是**真丢了**，不是分辨率不够。

★ 免费实验二（决定性）：flux-v2 的**草稿**（第二段重绘之前那张）本地就有，
  把它和**成品**并排 1:1 对比 ——
    · 草稿（1024x1280）：雀斑、毛孔、细小飞散发丝都在
    · 成品（2048x2560）：皮肤更光更蜡、雀斑被抹掉、脸颊泛油光、发绺更亮更成团
    · **像素多 3 倍的那张反而更糊**
  ⇒ 第二段「成品重绘」不是在补细节，是在**抹细节**。H1 成立。

════════════════════════ 二、三个旋钮 ════════════════════════
  H1 ★ 第二段 denoise 0.25 的「重绘」= 磨皮主犯   → **本批直接撤掉重绘**（纯放大存图）
  H2    第一段 denoise 0.30 偏高                  → C 压到 0.25，更贴 v23 基图
  H3    提示词「slightly damp」是油光来源、缺 dry/matte/flyaway → B 换成新词
  H4    光照太平（掠射侧光才是显纹理的物理机制）  → E 分支纳入**对照**：
        平光下毛孔的光学对比度极低，纹理天然显不出来；掠射光能让每个毛孔/细绒毛产生微小阴影。
        ⚠️ 与约束 §13「均匀柔和光」冲突 → 只作对照，由用户看图裁决，不擅自改规范。
  H5    放大模型 4x-UltraSharp 偏锐化/塑化        → D 换 4x_NMKD-Superscale（更自然的照片向）

════════════════════════ 三、五个分支（一轮只变一个变量） ════════════════════════
  A 旧词 · 第一段 0.30 · UltraSharp · 不重绘  ← 与现有 flux-v2 成品对比 = H1 的代价
  B 新词 · 第一段 0.30 · UltraSharp · 不重绘  ← A→B 只变 H3（提示词）
  C 新词 · 第一段 0.25 · UltraSharp · 不重绘  ← B→C 只变 H2（第一段 denoise）
  D 新词 · 第一段 0.30 · NMKD · 不重绘        ← B→D 只变 H5（放大模型）
  E 新词 · 第一段 0.30 · UltraSharp · 掠射光  ← B→E 只变 H4（光照）★ 最可能一举解决「质感不够」

★ 全部「不重绘」：第一段 → 4x 放大 → 缩回 0.5（净 2x）→ 直接存。
  没有第二段 KSampler，成品不再经过任何采样。

成本 ≈ 每条 28 步 @1024x1280 + 4x 放大，约 45–60 s；五条一次提交 ≈ 4–5 分钟。

════════════════════════ 四、与其它工作流的关系（并存，互不覆盖） ════════════════════════
  夜市百相簿.json                      SDXL/HelloWorldXL 管线（CFG10 / dpmpp_2m karras / 896x1152）—— v23 出自它
  闻灯-Flux脸部三视角.json              Flux img2img 三视角（0.30 / 0.60 / 0.60）—— flux-v2 出自它
  闻灯-Flux脸部三视角-迭代转头.json      4 档 denoise 转头阶梯（已证 img2img 转不到 90°）
  本文件                               Flux 正面质感修复对照批（A/B/C/D）

【参数】底模 FLUX1\\flux1-dev-fp8.safetensors（一体化 fp8，无需另配 VAE / 文本编码器）
        采样 euler + simple；第一段 28 步；cfg 必须 1.0；FluxGuidance 3.5；seed 固定 20260917
        ⚠️ cfg=1.0 → 负向通道关闭，negative 100% 失效 →「不要油光/不要磨皮」全写在正向里

【怎么跑】
  python run_wf.py "闻灯-Flux-质感修复对照.json" "FluxV5-A,FluxV5-B,FluxV5-C,FluxV5-D" final "…\\系列-夜市百相簿/02-角色/闻灯/设定图\\flux-v5-质感"
  跑完**必须用 zoom_sheet.py 做 1:1 裁切**再判断质感（整图缩放会把差异抹平！）：
  python zoom_sheet.py out.png 560 "0.30,0.18,0.70,0.58" "标签|副标|图1.png" ...
"""
import urllib.request, urllib.parse, json, ssl, uuid, os, sys

sys.path.insert(0, r"D:\xiaobai-claude code\ComfyUI\venv\Lib\site-packages")
from PIL import Image

# --local：只在本机构建 + 自检 + 写盘，跳过上传与推送（实例没开机时先用这个验证结构）
LOCAL_ONLY = "--local" in sys.argv

BASE = os.environ.get("COMFY_BASE", "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016")
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE

ROOT = r"D:\xiaobai-claude code\comfyUImd"
WF_DIR = os.path.join(ROOT, "_scripts", "_wf")
SRC_BASE_IMG = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "v23-脸部三视角", "闻灯v23-脸部正面-成品_00001_.png")
UPLOAD_NAME = "wendeng_v23_face_base.png"

CKPT = "FLUX1\\flux1-dev-fp8.safetensors"
UP_ULTRA = "4x-UltraSharp (1).pth"
UP_NMKD = "4x_NMKD-Superscale-SP_178000_G.pth"
W, H = 1024, 1280
STEPS_1, GUIDANCE, SEED = 28, 3.5, 20260917

# ============ 文本块 ============
CHAR = ("a 24-year-old East Asian man with a masculine face, a strong angular jaw, thick dark "
        "eyebrows, deep-set dark eyes with faint shadows underneath, light stubble, and a single "
        "small beauty mark at the outer corner of one eye")

VIEW_FRONT = ("He faces the camera directly, head level, shoulders square, face centered and "
              "looking straight into the lens, calm neutral expression.")

WEAR = "He wears a faded blue collared shirt with a dark worn coat collar."

# ---- 两种光照（E 分支专用变量）----
# 均匀光：符合约束 §13，但平光下毛孔的物理对比度极低，纹理天然显不出来。
LIGHT_EVEN = ("Studio lighting that is soft and even overall but keeps a gentle directional key from "
              "one side, so the face still has modeling and depth instead of completely flat light.")

# ★ 掠射光（raking light）：光源贴近面部切线方向打过来，毛孔/细绒毛/皮肤起伏会产生
#   微小阴影和高光 —— 这是让「皮肤质感」在照片上真正显形的物理机制，不是提示词魔法。
#   ⚠️ 与用户约束 §13「均匀柔和光」冲突 → 仅作对照分支，由用户看图裁决。
LIGHT_RAKE = ("Raking side lighting: a single hard key light from the left side, almost parallel to "
              "the skin surface and grazing across it at a low angle, so every pore, every fine hair "
              "and every small bump in the skin catches the light and casts a tiny shadow. Deep "
              "defined shadows on the far side of the face, strong rim light along the cheekbone and "
              "jaw, high micro-contrast on the skin texture. Not flat, not even, not frontal lighting.")

BGD = "Plain pure white seamless background, no props, no other people, no scenery, no furniture."

# ---- 旧词（= 现有 flux-v2 那一套，A 分支用）----
HAIR_OLD = ("His hair is messy wavy black hair, unkempt and slightly damp, with dry individual strands "
            "lifting away and separating, and a few loose strands falling across the forehead. "
            "It is completely unstyled and there is no hair product, no gel, no salon styling.")

SKIN_OLD = ("This is a raw unretouched documentary photograph. Real human skin with clearly visible "
            "pores and fine peach fuzz, subtle unevenness in skin tone, faint freckles and a scattering "
            "of small moles across the cheeks, natural creases under the eyes. "
            "No beauty retouching, no airbrushing, no skin smoothing, not a glamour shot, not a "
            "dermatology advertisement.")

QUAL_OLD = "Sharp focus, shot on an 85mm lens at f/4, photorealistic, high detail."

# ---- 新词（B/C/D 用）：去掉 damp，改干爽哑光 + 飞散发丝 + 胶片颗粒 ----
HAIR_NEW = ("His hair is messy wavy black hair that is completely dry and matte, never wet, never "
            "glossy, with no sheen and no light reflecting off it. It is genuinely unkempt: hundreds "
            "of separate individual strands are visible, several thin flyaway hairs lift off the "
            "silhouette and stand out against the white background as bright threads catching the "
            "light, the ends are dry and slightly frizzy with a few split tips, and a few loose "
            "strands fall across his forehead. It is completely unstyled and there is no hair "
            "product, no gel, no pomade, no oil, no salon styling.")

SKIN_NEW = ("This is a raw unretouched documentary photograph of a real human being. Real skin with "
            "clearly visible pores across the cheeks and nose, fine peach fuzz and tiny vellus hairs "
            "catching the light along the jaw, faint freckles, a scattering of small moles, uneven "
            "skin tone with slight redness around the nose and only a hint of shine on the forehead "
            "and nose tip, natural creases under the eyes and fine dry lines. The skin surface is "
            "matte and slightly weathered, never waxy, never oily, never airbrushed. "
            "Every eyebrow hair and every eyelash is rendered as a separate strand. "
            "Shot on 35mm film stock, fine natural film grain, real optical detail. "
            "No beauty retouching, no skin smoothing, no wax, no plastic, no digital noise reduction, "
            "not a glamour shot, not a dermatology advertisement.")

QUAL_NEW = ("Sharp focus with real micro-detail, shot on an 85mm lens at f/4, photorealistic, "
            "natural sensor noise, no noise reduction, no digital sharpening halo.")

KEEP_ID = ("Keep exactly the same person, the same face, the same identity and the same framing as "
           "the input photograph — only the rendering becomes more photographic.")


def compose(hair, skin, qual, light=None):
    return ("Photorealistic studio headshot of %s. %s %s %s %s %s %s %s %s"
            % (CHAR, VIEW_FRONT, WEAR, hair, skin, light or LIGHT_EVEN, BGD, qual, KEEP_ID))


P_OLD = compose(HAIR_OLD, SKIN_OLD, QUAL_OLD)
P_NEW = compose(HAIR_NEW, SKIN_NEW, QUAL_NEW)
P_RAKE = compose(HAIR_NEW, SKIN_NEW, QUAL_NEW, LIGHT_RAKE)

# ============ 五个分支：(标签, 提示词, 第一段 denoise, 放大模型) ============
BRANCHES = [
    ("FluxV5-A-旧词-d030-Ultra", P_OLD, 0.30, UP_ULTRA),
    ("FluxV5-B-新词-d030-Ultra", P_NEW, 0.30, UP_ULTRA),
    ("FluxV5-C-新词-d025-Ultra", P_NEW, 0.25, UP_ULTRA),
    ("FluxV5-D-新词-d030-NMKD", P_NEW, 0.30, UP_NMKD),
    ("FluxV5-E-掠射光-d030-Ultra", P_RAKE, 0.30, UP_ULTRA),
]

NOTE = """【闻灯 · Flux 质感修复对照批 flux-v5】  FLUX.1-dev-fp8  |  1024x1280  |  seed 20260917
基图 = v23 脸部正面成品（SDXL / 身份已确认，1792x2304 压到 1024x1280）

★ 起因：用户评价 flux-v2（Flux img2img 0.30）「还可以，就是皮肤和头发质感不够真实」。

★ 免费实验一 · 1:1 裁切（zoom_sheet.py）
  v23(SDXL) = 毛孔 / 细绒毛 / 痣群 / 一根根眉毛 / 干爽飞散发丝
  flux-v2   = 皮肤发蜡有油光 / 眉毛糊 / 头发油亮定型
  且 flux-v2 是 2048x2560、v23 只有 1792x2304 —— 分辨率更高反而更糊
  ⇒ 质感是真丢了，不是分辨率不够。

★ 免费实验二 · 重绘前后对比（决定性）
  flux-v2 的草稿（1024x1280，第二段重绘之前）本地就有，与成品并排：
    · 草稿：雀斑、毛孔、细小飞散发丝都在
    · 成品：皮肤更光更蜡、雀斑被抹掉、脸颊泛油光、发绺更亮更成团
    · 【像素多 3 倍的那张反而更糊】
  ⇒ 第二段「成品重绘」不是补细节，是在抹细节。⇒ 本批**全部撤掉第二段重绘**。

★ 四个旋钮（一轮只变一个变量）
  H1 第二段 denoise 0.25 重绘 = 磨皮主犯 → 已确认，本批直接撤掉
  H2 第一段 0.30 偏高                         → C 压到 0.25
  H3 提示词 slightly damp 是油光来源、缺 dry/matte/flyaway → B 换新词
  H5 放大模型 4x-UltraSharp 偏锐化塑化        → D 换 4x_NMKD-Superscale（照片向）
  H4 光照太平（掠射侧光才是显纹理的物理机制） → 未纳入：约束 §13 要求均匀柔和光，需先经用户同意

★ 四分支对照关系
  A 旧词 + d0.30 + UltraSharp + 不重绘   ← 与现有 flux-v2 成品对比 = H1 的代价（免费基线已有）
  B 新词 + d0.30 + UltraSharp + 不重绘   ← A→B 只变 H3
  C 新词 + d0.25 + UltraSharp + 不重绘   ← B→C 只变 H2
  D 新词 + d0.30 + NMKD      + 不重绘   ← B→D 只变 H5
  每条分支：第一段 → 4x 放大 → 缩回 0.5（净 2x）→ 直接存，**没有第二段 KSampler**。

★ 与其它工作流并存、互不覆盖
  夜市百相簿.json                    SDXL/HelloWorldXL（CFG10 / dpmpp_2m karras / 896x1152）—— v23 出自它
  闻灯-Flux脸部三视角.json            Flux 三视角（0.30 / 0.60 / 0.60）—— flux-v2 出自它
  闻灯-Flux脸部三视角-迭代转头.json    4 档 denoise 转头阶梯（已证 img2img 转不到 90°）
  本文件                             Flux 正面质感修复对照批（A/B/C/D）

★ 看结果的方式（很重要）
  不要用整图看！必须 zoom_sheet.py 做 1:1 裁切：
    python zoom_sheet.py out.png 560 "0.30,0.18,0.70,0.58" "标签|副标|图.png" ...
  ⚠️ cfg=1.0 → 负向通道关闭，negative 100% 失效，「不要油光/不要磨皮」只能写在正向里。
"""


# ==================== HTTP ====================
def raw(p, data=None, ctype=None, timeout=180):
    h = {}
    if ctype:
        h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


def upload(local, name, tries=4):
    data = open(local, "rb").read()
    print("  上传 %s (%.1f KB)" % (os.path.basename(local), len(data) / 1024))
    last = None
    for t in range(tries):
        bd = "----wb" + uuid.uuid4().hex
        body = b""
        for k, v in (("overwrite", "true"), ("type", "input"), ("subfolder", "")):
            body += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                     % (bd, k, v)).encode()
        body += ("--%s\r\nContent-Disposition: form-data; name=\"image\"; filename=\"%s\"\r\n"
                 "Content-Type: image/png\r\n\r\n" % (bd, name)).encode()
        body += data
        body += ("\r\n--%s--\r\n" % bd).encode()
        try:
            r = urllib.request.Request(BASE + "/upload/image", data=body,
                                       headers={"Content-Type": "multipart/form-data; boundary=%s" % bd})
            return urllib.request.urlopen(r, timeout=300, context=ctx).read().decode()
        except Exception as e:
            last = e
            print("    第 %d 次失败: %s" % (t + 1, type(e).__name__))
    raise last


print("=== 1) 身份基图 ===")
if not LOCAL_ONLY:
    # 先探一次：实例掉线时 /upload/image 会重试 4 次 × 300s ≈ 卡 20 分钟，必须提前拦住
    try:
        r = urllib.request.urlopen(BASE + "/system_stats", timeout=15, context=ctx)
        if r.status != 200 or "system" not in r.read().decode("utf-8", "replace"):
            raise RuntimeError("system_stats 异常")
    except Exception as e:
        print("  ★ 实例不在线（%s）。请先开机，然后跑： python oneshot.py all"
              % type(e).__name__)
        sys.exit(2)

os.makedirs(WF_DIR, exist_ok=True)
LOCAL_BASE = os.path.join(WF_DIR, "flux_face_base_v23_%dx%d.png" % (W, H))
im = Image.open(SRC_BASE_IMG).convert("RGB")
print("  源 %s %dx%d" % (os.path.basename(SRC_BASE_IMG), im.size[0], im.size[1]))
im.resize((W, H), Image.LANCZOS).save(LOCAL_BASE, "PNG", optimize=True)
if LOCAL_ONLY:
    print("  [--local] 跳过上传；本地已备好 %s" % LOCAL_BASE)
else:
    try:
        print("  ->", upload(LOCAL_BASE, UPLOAD_NAME)[:160])
    except Exception as e:
        print("  ★ 上传失败（%s）—— 实例可能还没就绪。开机后重跑本脚本。" % type(e).__name__)
        sys.exit(2)

# ==================== 构建 ====================
print("\n=== 2) 构建工作流 ===")
node_list, link_list = [], []


def N(nid, ntype, pos, size, widgets, inputs, outputs, order, title=None):
    n = {"id": nid, "type": ntype, "pos": list(pos), "size": list(size), "flags": {},
         "order": order, "mode": 0, "inputs": inputs, "outputs": outputs,
         "properties": {"Node name for S&R": ntype}}
    if title:
        n["title"] = title
    if widgets is not None:
        n["widgets_values"] = widgets
    node_list.append(n)
    return n


def I(name, typ):
    return {"name": name, "type": typ, "link": None}


def O(name, typ, idx):
    return {"name": name, "type": typ, "slot_index": idx, "links": []}


def L(fid, fslot, tid, tslot, typ):
    lid = len(link_list) + 1
    link_list.append([lid, fid, fslot, tid, tslot, typ])
    return lid


CLIP, COND, LAT, IMG, VAE, UPM = "CLIP", "CONDITIONING", "LATENT", "IMAGE", "VAE", "UPSCALE_MODEL"

# ---- 共用 ----
N(6, "Note", (61, 20), (2000, 1080), [NOTE], [], [], 0, "★ 说明 · Flux 质感修复对照批 flux-v5")
N(1, "CheckpointLoaderSimple", (61, 1140), (470, 100), [CKPT], [],
  [O("MODEL", "MODEL", 0), O("CLIP", "CLIP", 1), O("VAE", "VAE", 2)], 1,
  "FLUX.1-dev-fp8（一体化）")
N(2, "LoadImage", (61, 1300), (400, 400), [UPLOAD_NAME, "image"], [],
  [O("IMAGE", "IMAGE", 0), O("MASK", "MASK", 1)], 2, "★ 身份基图 = v23 脸部正面成品")
N(3, "ImageScale", (500, 1300), (330, 100), ["lanczos", W, H, "center"],
  [I("image", "IMAGE")], [O("IMAGE", "IMAGE", 0)], 3, "统一到 1024x1280")
N(4, "VAEEncode", (870, 1300), (280, 60), [],
  [I("pixels", "IMAGE"), I("vae", "VAE")], [O("LATENT", "LATENT", 0)], 4, "身份 latent")
N(7, "CLIPTextEncode", (1190, 1300), (460, 130), [""],
  [I("clip", "CLIP")], [O("CONDITIONING", "CONDITIONING", 0)], 5,
  "★ 负向（cfg=1.0 下无效，留空仅为满足接口）")

L(1, 1, 7, 0, CLIP)
L(2, 0, 3, 0, IMG)
L(3, 0, 4, 0, IMG)
L(1, 2, 4, 1, VAE)

# ---- 四条分支：stride 10，b = 10 + i*10 ----
for i, (label, prompt, den1, upmodel) in enumerate(BRANCHES):
    b = 10 + i * 10
    y = 1700 + i * 700

    N(b + 0, "CLIPTextEncode", (61, y), (760, 460), [prompt],
      [I("clip", "CLIP")], [O("CONDITIONING", "CONDITIONING", 0)], 10 + i * 10,
      "正向 · %s" % label)
    N(b + 1, "FluxGuidance", (860, y), (300, 60), [GUIDANCE],
      [I("conditioning", "CONDITIONING")], [O("CONDITIONING", "CONDITIONING", 0)], 11 + i * 10,
      "Guidance %.1f" % GUIDANCE)
    N(b + 2, "KSampler", (860, y + 120), (330, 262),
      [SEED, "fixed", STEPS_1, 1.0, "euler", "simple", den1],
      [I("model", "MODEL"), I("positive", "CONDITIONING"), I("negative", "CONDITIONING"),
       I("latent_image", "LATENT")],
      [O("LATENT", "LATENT", 0)], 12 + i * 10,
      "① %s  第一段 denoise %.2f" % (label, den1))
    N(b + 3, "VAEDecode", (1230, y + 120), (250, 60), [],
      [I("samples", "LATENT"), I("vae", "VAE")], [O("IMAGE", "IMAGE", 0)], 13 + i * 10)
    N(b + 4, "SaveImage", (1230, y + 220), (460, 460), ["%s-草稿" % label],
      [I("images", "IMAGE")], [], 14 + i * 10, "草稿 · %s" % label)
    N(b + 5, "UpscaleModelLoader", (1750, y + 100), (520, 80), [upmodel], [],
      [O("UPSCALE_MODEL", "UPSCALE_MODEL", 0)], 15 + i * 10,
      "放大模型：%s" % upmodel.split(".")[0])
    N(b + 6, "ImageUpscaleWithModel", (1750, y + 240), (440, 80), [],
      [I("upscale_model", "UPSCALE_MODEL"), I("image", "IMAGE")],
      [O("IMAGE", "IMAGE", 0)], 16 + i * 10)
    N(b + 7, "ImageScaleBy", (1750, y + 360), (330, 80), ["lanczos", 0.5],
      [I("image", "IMAGE")], [O("IMAGE", "IMAGE", 0)], 17 + i * 10, "缩回 2048x2560")
    N(b + 8, "SaveImage", (2260, y + 100), (500, 460), ["%s-成品" % label],
      [I("images", "IMAGE")], [], 18 + i * 10, "★ 成品 · %s（无第二段采样）" % label)
    N(b + 9, "Note", (2260, y + 600), (620, 180),
      ["★ 本分支没有第二段 KSampler。\n成品 = 第一段 → 4x 放大 → 缩回 0.5（净 2x），"
       "不经过任何二次采样。\n对照现有 flux-v2 成品，即可看出「重绘」那步的代价。"],
      [], [], 19 + i * 10, "备注 · %s" % label)

byid = {n["id"]: n for n in node_list}
for i, (label, prompt, den1, upmodel) in enumerate(BRANCHES):
    b = 10 + i * 10
    L(1, 1, b + 0, 0, CLIP)
    L(b + 0, 0, b + 1, 0, COND)
    L(1, 0, b + 2, 0, "MODEL")
    L(b + 1, 0, b + 2, 1, COND)
    L(7, 0, b + 2, 2, COND)
    L(4, 0, b + 2, 3, LAT)
    L(b + 2, 0, b + 3, 0, LAT)
    L(1, 2, b + 3, 1, VAE)
    L(b + 3, 0, b + 4, 0, IMG)
    L(b + 3, 0, b + 6, 1, IMG)
    L(b + 5, 0, b + 6, 0, UPM)
    L(b + 6, 0, b + 7, 0, IMG)
    L(b + 7, 0, b + 8, 0, IMG)

# ---- 回填 ----
for n in node_list:
    for s in n.get("inputs", []):
        s["link"] = None
    for o in n.get("outputs", []):
        o["links"] = []
for lid, fid, fslot, tid, tslot, typ in link_list:
    src = byid.get(fid)
    if src and fslot < len(src.get("outputs", [])):
        src["outputs"][fslot]["links"].append(lid)
    dst = byid.get(tid)
    if dst and tslot < len(dst.get("inputs", [])):
        dst["inputs"][tslot]["link"] = lid

# ---- 自检 ----
errs = []
ids = set(byid)
if len(ids) != len(node_list):
    errs.append("节点 id 重复")
for lid, fid, fslot, tid, tslot, typ in link_list:
    if fid not in ids:
        errs.append("链接 %d 起点 %s 不存在" % (lid, fid))
    if tid not in ids:
        errs.append("链接 %d 终点 %s 不存在" % (lid, tid))
for n in node_list:
    if n["type"] == "Note":
        continue
    for s in n.get("inputs", []):
        if s["link"] is None:
            errs.append("节点 %d(%s) 输入 %s 未连接" % (n["id"], n["type"], s["name"]))
    if n["type"] == "KSampler" and len(n.get("widgets_values", [])) != 7:
        errs.append("KSampler %d widgets 异常" % n["id"])
    if n["type"] == "ImageUpscaleWithModel" and n.get("outputs") and len(n["inputs"]) != 2:
        errs.append("ImageUpscaleWithModel %d 输入数异常" % n["id"])
# 每条分支必须有唯一「成品」SaveImage，且前缀能被 run_wf 命中
for label, _, _, _ in BRANCHES:
    hits = [n for n in node_list if n["type"] == "SaveImage"
            and str(n["widgets_values"][0]) == "%s-成品" % label]
    if len(hits) != 1:
        errs.append("分支 %s 的成品 SaveImage 数量 = %d（应为 1）" % (label, len(hits)))
    if not label.startswith("FluxV5-"):
        errs.append("分支标签 %s 未以 FluxV5- 开头，run_wf 关键词会歧义" % label)

wf = {"id": str(uuid.uuid4()), "revision": 0,
      "last_node_id": max(ids), "last_link_id": len(link_list),
      "nodes": sorted(node_list, key=lambda n: n.get("order", 0)),
      "links": link_list, "groups": [], "config": {}, "extra": {}, "version": 0.4}

print("  节点 %d  链接 %d" % (len(node_list), len(link_list)))
if errs:
    print("  ★ 自检失败：")
    for e in errs:
        print("     -", e)
    sys.exit(1)
print("  自检通过")
for label, prompt, den1, upmodel in BRANCHES:
    print("     %-28s d%.2f  %s  提示词 %d 字符" % (label, den1, upmodel, len(prompt)))

local_out = os.path.join(WF_DIR, "闻灯-Flux-质感修复对照.json")
json.dump(wf, open(local_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("  已写出 %s (%.1f KB)" % (local_out, os.path.getsize(local_out) / 1024))

# ==================== 推送 ====================
print("\n=== 3) 推送 ===")
NAME = "闻灯-Flux-质感修复对照.json"
if LOCAL_ONLY:
    print("  [--local] 跳过推送。开机后**只跑这一条**（它会把下面几步全部串起来）：")
    print("     python oneshot.py all")
    print("  或单独跑：")
    print("     python push_flux_texture_wf.py")
    print('     python run_wf.py "%s" "%s" final "…\\系列-夜市百相簿/02-角色/闻灯/设定图\\flux-v5-质感"'
          % (NAME, ",".join(l for l, _, _, _ in BRANCHES)))
    print("  跑完必须用 zoom_sheet.py 做 1:1 裁切再看质感（oneshot 会自动拼）。")
    print("\nOK（仅本地构建）")
    sys.exit(0)

body = json.dumps(wf, ensure_ascii=False).encode("utf-8")
ok = False
for path in ("/api/userdata/workflows%%2F%s?overwrite=true" % urllib.parse.quote(NAME),
             "/api/userdata/workflows%%2F%s?overwrite=true" % NAME):
    try:
        r = raw(path, body, "application/json", 120)
        print("  写入成功 ->", r.decode()[:180]); ok = True; break
    except Exception as e:
        print("  写入失败: %s %s" % (type(e).__name__, str(e)[:140]))
if not ok:
    print("  ★ 推送失败（实例可能未开机）。本地 JSON 已就绪，开机后重跑本脚本即可。")
    sys.exit(2)

print("\n  工作流列表:", raw("/api/userdata?dir=workflows", None, None, 60).decode("utf-8", "replace")[:400])
print("\nOK")
