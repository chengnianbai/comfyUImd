# -*- coding: utf-8 -*-
"""闻灯 · Flux 版「脸部三视角」工作流 —— 构建 UI 格式 JSON 并推送到远程 ComfyUI

为什么要有这个版本（对照 flux-v1 的失败）：
    flux-v1 的 T 线是**纯文生图**，所以出来的必然是另一个人（本项目已三次证实：
    同 seed + 同 token ≠ 同一个人）。本版**三条视角全部走 img2img**，
    以「v23 脸部正面成品」（用户认可、身份已锁定）为唯一身份基图。

★ 最关键的一条（约束文件完全没覆盖）：
    FLUX 在 cfg=1.0 下**没有负向通道，negative 提示词 100% 失效**。
    v23（SDXL/CFG10）里那三段反磨皮负向（airbrushed / over-smoothed / beauty filter /
    retouched / doll / 3d render）在 Flux 下等于零。
    → 本版把所有这些约束**改写成正向自然语言**（"no beauty retouching" 这类
      否定式正向短语，Flux 的 T5 编码器能理解），并补回 v23 有、flux-v1 丢掉的
      纹理词（individual hair strands / skin texture / peach fuzz）。
"""
import urllib.request, urllib.parse, json, ssl, uuid, os, sys

sys.path.insert(0, r"D:\xiaobai-claude code\ComfyUI\venv\Lib\site-packages")
from PIL import Image

BASE = "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016"
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE

ROOT = r"D:\xiaobai-claude code\comfyUImd"
WF_DIR = os.path.join(ROOT, "_scripts", "_wf")
SRC_BASE_IMG = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "v23-脸部三视角", "闻灯v23-脸部正面-成品_00001_.png")
UPLOAD_NAME = "wendeng_v23_face_base.png"

CKPT = "FLUX1\\flux1-dev-fp8.safetensors"
UPSCALER = "4x-UltraSharp (1).pth"
W, H = 1024, 1280
STEPS_1, GUIDANCE = 28, 3.5
STEPS_2, DEN_2 = 18, 0.25
SEED = 20260917

# ============ 共用文本块（自然语言，Flux 用；T5 上限 512 token，不受 75 限制）============
CHAR = ("a 24-year-old East Asian man with a masculine face, a strong angular jaw, thick dark "
        "eyebrows, deep-set dark eyes with faint shadows underneath, light stubble, and a single "
        "small beauty mark at the outer corner of one eye")

HAIR = ("His hair is messy wavy black hair, unkempt and slightly damp, with dry individual strands "
        "lifting away and separating, and a few loose strands falling across the forehead. "
        "It is completely unstyled and there is no hair product, no gel, no salon styling.")

SKIN = ("This is a raw unretouched documentary photograph. Real human skin with clearly visible "
        "pores and fine peach fuzz, subtle unevenness in skin tone, faint freckles and a scattering "
        "of small moles across the cheeks, natural creases under the eyes. "
        "No beauty retouching, no airbrushing, no skin smoothing, not a glamour shot, not a "
        "dermatology advertisement.")

LIGHT = ("Studio lighting that is soft and even overall but keeps a gentle directional key from "
         "one side, so the face still has modeling and depth instead of completely flat light.")

BGD = "Plain pure white seamless background, no props, no other people, no scenery, no furniture."

QUAL = "Sharp focus, shot on an 85mm lens at f/4, photorealistic, high detail."

WEAR = "He wears a faded blue collared shirt with a dark worn coat collar."

VIEW_FRONT = ("He faces the camera directly, head level, shoulders square, face centered and "
              "looking straight into the lens, calm neutral expression.")

VIEW_LEFT = ("A true full 90-degree LEFT profile: his head is turned all the way so the camera sees "
             "only the LEFT side of his face. Only his left eye, left eyebrow, left ear and the left "
             "line of his nose and jaw are visible; the entire right side of his face is hidden. "
             "Preserve his exact identity: the same face, eyes, eyebrows, nose, jaw and hair as the "
             "reference image.")

VIEW_RIGHT = ("A true full 90-degree RIGHT profile: his head is turned all the way so the camera "
              "sees only the RIGHT side of his face. Only his right eye, right eyebrow, right ear "
              "and the right line of his nose and jaw are visible; the entire left side of his face "
              "is hidden. Preserve his exact identity: the same face, eyes, eyebrows, nose, jaw and "
              "hair as the reference image.")


def compose(view):
    return ("Photorealistic studio headshot of %s. %s %s %s %s %s %s %s"
            % (CHAR, view, WEAR, HAIR, SKIN, LIGHT, BGD, QUAL))


# 视角定义：显示名 / 提示词 / 第一段 denoise / 前后缀
VIEWS = [
    ("脸部正面", compose(VIEW_FRONT), 0.30),
    ("脸部左侧面", compose(VIEW_LEFT), 0.60),
    ("脸部右侧面", compose(VIEW_RIGHT), 0.60),
]

NOTE = """【闻灯 · Flux 脸部三视角】  FLUX.1-dev-fp8  |  1024x1280  |  seed 固定 20260917

★★ 本工作流与「夜市百相簿.json」（SDXL 版）的关系
    那份是 SDXL/HelloWorld XL 管线（CFG 10、dpmpp_2m karras、896x1152、ClipSkip 1）。
    本份是 **Flux 管线**，两者参数**完全不通用**，别互相照搬。

★★ 为什么 flux-v1 那次出的脸完全不是同一个人（本次修正的第一件事）
    flux-v1 的正面/侧面三张是**纯文生图**（EmptyLatentImage 起步、denoise 1.0）。
    本项目已三次证实：**同 seed + 同 token ≠ 同一个人**，纯文生图必然换脸。
    → 本版三条视角**全部走 img2img**：LoadImage(已确认脸) → VAEEncode → KSampler。
      基图 = 「v23 脸部正面成品」（用户认可、身份已锁定）。

★★★ 本次补上的最大漏项：FLUX 下负向提示词是**完全失效**的
    Flux 走 distilled guidance，cfg 必须 = 1.0，此时**没有 negative 分支**，
    节点里那个空的「负向」接上去也不起作用（留空只是为了满足 KSampler 的接口）。
    v23 在 SDXL 下的反磨皮，一半力量来自负向三段：
        airbrushed / over-smoothed / beauty filter / retouched / doll / 3d render / cgi
    这些在 Flux 里**一个字都不生效**。
    → 本版把它们全部**改写成正向自然语言**，例如：
        "No beauty retouching, no airbrushing, no skin smoothing, not a glamour shot"
        "It is completely unstyled and there is no hair product, no gel, no salon styling"
      Flux 的 T5 编码器能理解这种否定式正向短语，这是它在 cfg=1 下唯一可用的排除手段。

★ 纹理词补齐（v23 有、flux-v1 漏掉的）
    v23 脸部 B 段(60 token)：detailed face, detailed eyes, iris detail, thick eyebrows,
        stubble, visible skin pores, skin texture, peach fuzz, individual hair strands
    flux-v1 只剩：visible pores / fine facial hair
    → 漏掉的是 **individual hair strands（头发质感）** 和 **skin texture**，正是本次重点补回。
      本版正向含：individual strands lifting away and separating / visible pores /
      fine peach fuzz / faint freckles / small moles（★ 雀斑与痣群是 v13 的真实感来源，
      绝对不要写进负向）。

★ 光照：去掉了 flux-v1 里的 "no harsh shadows"
    约束 §13 要求「均匀柔和光」，但本项目实测平光会把皮肤漂成塑料感（约束文件附录 B.2）。
    flux-v1 更把 "no harsh shadows" 白纸黑字写进了正向 → 加重磨皮。
    本版改为「整体柔和，但保留一点方向性主光」，在不违反 §13「不产生强烈彩色光 /
    不产生戏剧化灯光 / 减少复杂阴影」的前提下保住皮肤立体感。

【参数】
    底模      FLUX1\\flux1-dev-fp8.safetensors（一体化 fp8，16.06GiB，无需另配 VAE/文本编码器）
    采样      euler + simple，第一段 28 步，第二段 18 步
    cfg       **必须 1.0**（套 SDXL 的 10 会直接炸图）
    guidance  FluxGuidance 3.5（这个是 Flux 真正吃的那条「提示词听话程度」旋钮）
    CLIP skip **不需要 CLIPSetLastLayer**（SDXL 那套 -1 不要照搬）
    放大      4x-UltraSharp → ImageScaleBy 0.5 → VAEEncode → 第二段 denoise 0.25
              （LatentUpscale 只放量不加细节，已在 v19 被弃用）

【三条视角的 denoise】
    脸部正面  0.30  —— 几乎只重绘质感，身份最稳
    左侧面    0.60  —— 需要真转头，denoise 必须够大
    右侧面    0.60
    ⚠️ SDXL 实测转不出 90 度侧面（denoise 拉到 0.86 也只到 3/4 侧）；
       Flux 对方位词的理解明显更强，本版就是来验证这一点的。
       若侧面仍转不到位，把对应 KSampler 的 denoise 往上调，或改用「迭代转头」
       （先转到 3/4 侧，再拿这张当基图继续转）。

【★ 流程铁律：先脸后身（约束 §14 / H04）】
    只有本工作流的三张脸部图**人工确认通过**后，才允许做全身图。
    脸部未确认 → 禁止进入全身生成。
    全身图必须继续用这里的成品脸做身份参考（H09/H10）。

【纯白背景】
    提示词只能给到浅灰/接近白，仍然建议跑一次后处理：
    python _scripts/post_whitebg.py <图片或目录> --spread 14 --tol 26
"""


# ==================== HTTP ====================
def raw(p, data=None, ctype=None, timeout=180, method=None):
    h = {}
    if ctype:
        h["Content-Type"] = ctype
    r = urllib.request.Request(BASE + p, data=data, headers=h, method=method)
    return urllib.request.urlopen(r, timeout=timeout, context=ctx).read()


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


# ==================== 1) 准备并上传身份基图 ====================
print("=== 1) 身份基图 ===")
os.makedirs(os.path.join(ROOT, "_scripts", "_wf"), exist_ok=True)
LOCAL_BASE = os.path.join(ROOT, "_scripts", "_wf", "flux_face_base_v23_%dx%d.png" % (W, H))
im = Image.open(SRC_BASE_IMG).convert("RGB")
print("  源: %s  %dx%d" % (os.path.basename(SRC_BASE_IMG), im.size[0], im.size[1]))
im.resize((W, H), Image.LANCZOS).save(LOCAL_BASE, "PNG", optimize=True)
print("  ->", upload(LOCAL_BASE, UPLOAD_NAME)[:200])


# ==================== 2) 构建 UI 格式工作流 ====================
print("\n=== 2) 构建工作流 ===")

node_list = []
link_list = []


def N(nid, ntype, pos, size, widgets, inputs, outputs, order, title=None, mode=0):
    n = {"id": nid, "type": ntype, "pos": list(pos), "size": list(size), "flags": {},
         "order": order, "mode": mode, "inputs": inputs, "outputs": outputs,
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


# ---- 共用节点 ----
N(6, "Note", (61, 20), (1700, 700), [NOTE], [], [], 0,
  "★ 说明 · 闻灯 Flux 脸部三视角（img2img 保身份 + 负向失效的正向补偿）")

N(1, "CheckpointLoaderSimple", (61, 760), (470, 100), [CKPT], [],
  [O("MODEL", "MODEL", 0), O("CLIP", "CLIP", 1), O("VAE", "VAE", 2)], 1,
  "FLUX.1-dev-fp8（一体化，无需另配 VAE/clip）")

N(2, "LoadImage", (61, 920), (400, 400), [UPLOAD_NAME, "image"], [],
  [O("IMAGE", "IMAGE", 0), O("MASK", "MASK", 1)], 2,
  "★ 身份基图 = v23 脸部正面成品（已确认身份）")

N(3, "ImageScale", (500, 920), (330, 100), ["lanczos", W, H, "center"],
  [I("image", "IMAGE")], [O("IMAGE", "IMAGE", 0)], 3, "统一到 1024x1280")

N(4, "VAEEncode", (870, 920), (280, 60), [],
  [I("pixels", "IMAGE"), I("vae", "VAE")], [O("LATENT", "LATENT", 0)], 4,
  "身份 latent（img2img 起点）")

N(5, "UpscaleModelLoader", (61, 1380), (430, 80), [UPSCALER], [],
  [O("UPSCALE_MODEL", "UPSCALE_MODEL", 0)], 5, "放大模型 4x-UltraSharp")

N(7, "CLIPTextEncode", (1190, 920), (420, 130), [""],
  [I("clip", "CLIP")], [O("CONDITIONING", "CONDITIONING", 0)], 6,
  "★ 负向（Flux cfg=1.0 下无效，留空仅为满足接口）")

BASE_NODES = [1, 2, 3, 4, 5, 6, 7]

# ---- 三条视角分支 ----
branch_ids = []
for i, (vname, prompt, den) in enumerate(VIEWS):
    b = 10 + i * 11
    y = 1560 + i * 780
    ids = [b + k for k in range(11)]
    branch_ids.append(ids)

    N(b + 0, "CLIPTextEncode", (61, y), (700, 460), [prompt],
      [I("clip", "CLIP")], [O("CONDITIONING", "CONDITIONING", 0)], 10 + i * 11,
      "正向 · %s（自然语言，无 75 token 限制）" % vname)
    N(b + 1, "FluxGuidance", (800, y), (300, 60), [GUIDANCE],
      [I("conditioning", "CONDITIONING")], [O("CONDITIONING", "CONDITIONING", 0)], 11 + i * 11,
      "Guidance %.1f" % GUIDANCE)
    N(b + 2, "KSampler", (800, y + 120), (330, 262),
      [SEED, "fixed", STEPS_1, 1.0, "euler", "simple", den],
      [I("model", "MODEL"), I("positive", "CONDITIONING"), I("negative", "CONDITIONING"),
       I("latent_image", "LATENT")],
      [O("LATENT", "LATENT", 0)], 12 + i * 11,
      "① %s img2img  denoise %.2f" % (vname, den))
    N(b + 3, "VAEDecode", (1190, y + 120), (250, 60), [],
      [I("samples", "LATENT"), I("vae", "VAE")], [O("IMAGE", "IMAGE", 0)], 13 + i * 11)
    N(b + 4, "SaveImage", (1190, y + 220), (420, 500), ["闻灯FluxV2-%s-草稿" % vname],
      [I("images", "IMAGE")], [], 14 + i * 11, "草稿 · %s" % vname)
    N(b + 5, "ImageUpscaleWithModel", (1500, y + 120), (400, 80), [],
      [I("upscale_model", "UPSCALE_MODEL"), I("image", "IMAGE")],
      [O("IMAGE", "IMAGE", 0)], 15 + i * 11)
    N(b + 6, "ImageScaleBy", (1500, y + 250), (300, 80), ["lanczos", 0.5],
      [I("image", "IMAGE")], [O("IMAGE", "IMAGE", 0)], 16 + i * 11, "缩回 2048x2560")
    N(b + 7, "VAEEncode", (1500, y + 370), (280, 60), [],
      [I("pixels", "IMAGE"), I("vae", "VAE")], [O("LATENT", "LATENT", 0)], 17 + i * 11)
    N(b + 8, "KSampler", (1850, y + 120), (330, 262),
      [SEED, "fixed", STEPS_2, 1.0, "euler", "simple", DEN_2],
      [I("model", "MODEL"), I("positive", "CONDITIONING"), I("negative", "CONDITIONING"),
       I("latent_image", "LATENT")],
      [O("LATENT", "LATENT", 0)], 18 + i * 11,
      "② %s 放大重绘  denoise %.2f" % (vname, DEN_2))
    N(b + 9, "VAEDecode", (2240, y + 120), (250, 60), [],
      [I("samples", "LATENT"), I("vae", "VAE")], [O("IMAGE", "IMAGE", 0)], 19 + i * 11)
    N(b + 10, "SaveImage", (2240, y + 220), (420, 500), ["闻灯FluxV2-%s-成品" % vname],
      [I("images", "IMAGE")], [], 20 + i * 11, "成品 · %s" % vname)

byid = {n["id"]: n for n in node_list}

# ---- 连线 ----
CLIP = "CLIP"; COND = "CONDITIONING"; LAT = "LATENT"; IMG = "IMAGE"; VAE = "VAE"; UPM = "UPSCALE_MODEL"
lk_clip_neg = L(1, 1, 7, 0, CLIP)
lk_base_scale = L(2, 0, 3, 0, IMG)
lk_base_enc = L(3, 0, 4, 0, IMG)
lk_base_vae = L(1, 2, 4, 1, VAE)

for i, (vname, prompt, den) in enumerate(VIEWS):
    b = 10 + i * 11
    L(1, 1, b + 0, 0, CLIP)          # CLIP -> 正向编码
    L(b + 0, 0, b + 1, 0, COND)      # 正向 -> FluxGuidance
    L(1, 0, b + 2, 0, "MODEL")       # model -> KSampler1
    L(b + 1, 0, b + 2, 1, COND)      # guidance -> positive
    L(7, 0, b + 2, 2, COND)          # 空负向占位
    L(4, 0, b + 2, 3, LAT)           # 身份 latent
    L(b + 2, 0, b + 3, 0, LAT)       # KSampler1 -> VAEDecode1
    L(1, 2, b + 3, 1, VAE)
    L(b + 3, 0, b + 4, 0, IMG)       # -> SaveImage 草稿
    L(b + 3, 0, b + 5, 1, IMG)       # -> 放大
    L(5, 0, b + 5, 0, UPM)
    L(b + 5, 0, b + 6, 0, IMG)       # 放大 -> 缩小
    L(b + 6, 0, b + 7, 0, IMG)       # -> VAEEncode2
    L(1, 2, b + 7, 1, VAE)
    L(1, 0, b + 8, 0, "MODEL")       # KSampler2
    L(b + 1, 0, b + 8, 1, COND)
    L(7, 0, b + 8, 2, COND)
    L(b + 7, 0, b + 8, 3, LAT)
    L(b + 8, 0, b + 9, 0, LAT)
    L(1, 2, b + 9, 1, VAE)
    L(b + 9, 0, b + 10, 0, IMG)

# ---- 回填 link 引用 ----
for n in node_list:
    for i in n.get("inputs", []):
        i["link"] = None
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
    errs.append("节点 id 有重复")
for lid, fid, fslot, tid, tslot, typ in link_list:
    if fid not in ids:
        errs.append("链接 %d 起点节点 %s 不存在" % (lid, fid))
    if tid not in ids:
        errs.append("链接 %d 终点节点 %s 不存在" % (lid, tid))
for n in node_list:
    for slot in n.get("inputs", []):
        if slot["link"] is None:
            errs.append("节点 %d(%s) 输入 %s 未连接" % (n["id"], n["type"], slot["name"]))
    if n["type"] == "KSampler" and len(n.get("widgets_values", [])) != 7:
        errs.append("KSampler 节点 %d widgets 数量异常" % n["id"])
for b in branch_ids:
    for k in b:
        if k not in ids:
            errs.append("分支节点 %d 缺失" % k)

wf = {
    "id": str(uuid.uuid4()),
    "revision": 0,
    "last_node_id": max(ids),
    "last_link_id": len(link_list),
    "nodes": sorted(node_list, key=lambda n: n.get("order", 0)),
    "links": link_list,
    "groups": [],
    "config": {},
    "extra": {},
    "version": 0.4,
}

print("  节点数 %d  链接数 %d" % (len(node_list), len(link_list)))
if errs:
    print("  ★ 自检失败：")
    for e in errs:
        print("     -", e)
    sys.exit(1)
print("  自检通过")

local_out = os.path.join(WF_DIR, "闻灯-Flux脸部三视角.json")
json.dump(wf, open(local_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("  已写出 %s  (%.1f KB)" % (local_out, os.path.getsize(local_out) / 1024))

# ==================== 3) 推送到远程 ComfyUI ====================
print("\n=== 3) 推送 ===")
NAME = "闻灯-Flux脸部三视角.json"
body = json.dumps(wf, ensure_ascii=False).encode("utf-8")
ok = False
for path in ("/api/userdata/workflows%%2F%s?overwrite=true" % urllib.parse.quote(NAME),
             "/api/userdata/workflows%%2F%s?overwrite=true" % NAME):
    try:
        r = raw(path, body, "application/json", 120, "POST")
        print("  写入成功 ->", r.decode()[:200])
        ok = True
        break
    except Exception as e:
        print("  写入失败(%s): %s" % (path[:60], type(e).__name__))
if not ok:
    print("  ★ 推送失败")
    sys.exit(1)

print("\n  当前工作流列表：")
lst = json.loads(raw("/api/userdata?dir=workflows", None, None, 60).decode("utf-8", "replace"))
print("   ", lst)

print("\n节点清单：")
for n in wf["nodes"]:
    print("  %-3s %-24s %s" % (n["id"], n["type"], (n.get("title") or "")))
print("\nOK")
