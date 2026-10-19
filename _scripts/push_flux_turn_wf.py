# -*- coding: utf-8 -*-
"""闻灯 · Flux「迭代转头」工作流 —— 构建 UI 格式 JSON 并推送到远程 ComfyUI

为什么要有这一版（对照「闻灯-Flux脸部三视角.json」的失败）：
    上一版三条视角的 denoise 是 0.30 / 0.60 / 0.60，实测结果：
      正面  ✅ 脸回到 v23 那个人，头发蓬松、皮肤有纹理 —— 方向对了
      左侧  ❌ 仍是大正面
      右侧  ❌ 仍是大正面
    → **从正面基图一步 img2img 到 90°，SDXL 和 Flux 都做不到**（B.4 裁决被否证）。
      道理：denoise 不够，正面 latent 的结构把构图死死锚住；denoise 一高，
      又会被 Flux 自带的"抛光先验"接管、身份走掉。

本版做法：**迭代转头**——不追求一步到位，先把头转 45°（3/4 侧），
    确认这张 3/4 的身份没走掉之后，再拿它当新基图继续转向 90°。
    每一步只需要模型"小改一点"，低 denoise 就够用，身份也守得住。

★★ 本版是**第一步：denoise 阶梯**，目的不是出终稿，而是**花最小代价确定
   "3/4 侧需要多大 denoise"**。所以：
      左 45° 跑三档  0.55 / 0.70 / 0.85
      右 45° 只跑一档 0.70
   先只跑「草稿」分支（28 步第一段，单张约 30 秒），不跑放大重绘，
   四张草稿合计约 2–3 分钟即可看出哪档转得动、哪档开始换人。
   选定之后再走「成品」分支（4x-UltraSharp + 二次重绘 denoise 0.25）。

★★ denoise 与质感是**对抗关系**（本项目已实测）：
   Flux 的 denoise 越高，"美容抛光"先验越占上风 → 皮肤越塑料。
   所以不要"能转就行"，要在**转得动的前提下取最小的那一档**。
"""

import urllib.request, urllib.parse, json, ssl, uuid, os, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, r"D:\xiaobai-claude code\ComfyUI\venv\Lib\site-packages")

from PIL import Image
from wd_blocks import (VIEW_34_L, VIEW_34_R, compose)

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

# ============ 3/4 侧 denoise 阶梯 + 两个兜底探针 ============
# (标签, 提示词, denoise, guidance)
#   前三档 + 右侧对照：测「denoise 要多大才转得动」
#   d095        ：denoise 拉到 0.95（快到纯文生图了），看是否还转不动
#   d085-g080   ：denoise 0.85 但 guidance 提到 8.0，测「是不是模型没听提示词」
TURNS = [
    ("四分之三左侧-d055", compose(VIEW_34_L, True), 0.55, 3.5),
    ("四分之三左侧-d070", compose(VIEW_34_L, True), 0.70, 3.5),
    ("四分之三左侧-d085", compose(VIEW_34_L, True), 0.85, 3.5),
    ("四分之三右侧-d070", compose(VIEW_34_R, True), 0.70, 3.5),
    ("四分之三左侧-d095", compose(VIEW_34_L, True), 0.95, 3.5),
    ("四分之三左侧-d085-g080", compose(VIEW_34_L, True), 0.85, 8.0),
]

NOTE = """【闻灯 · Flux 迭代转头 —— 第一步：3/4 侧 denoise 阶梯】

★★ 先说结论：为什么不能一步转到 90°
    「闻灯-Flux脸部三视角.json」用 denoise 0.60 从正面基图直接转左侧面/右侧面，
    结果是**两张仍然是大正面**。这不是参数没调好，而是这条路本身不通：
      · denoise 低 → 正面 latent 结构把构图锚死，头根本不动
      · denoise 高 → 结构松了，但 Flux 自带的"美容抛光"先验接管，身份和质感一起丢
    SDXL 也一样（denoise 0.86 只到 3/4 侧）→ 约束文件裁决 B.4 已被否证，见 B.6。

★ 本版改用「迭代转头」：分步小角度转
    正面 →(转 45°)→ 3/4 侧 →(继续转 45°)→ 90° 侧脸
    每一步只让模型改一点点，denoise 就能压得低，身份守得住。

★★ 本次要回答的问题只有一个：**45° 到底需要多大 denoise。**
    所以左侧跑三档：0.55 / 0.70 / 0.85，右侧先跑一档 0.70 做对照。

★ 跑法（只跑草稿，最省时间）
    单张草稿 = 28 步第一段，约 30 秒；四张约 2–3 分钟。
    选定档位后再走「成品」分支（4x 放大 + 二次重绘 0.25）。
    命令：python _scripts\\run_wf.py "闻灯-Flux脸部三视角-迭代转头.json" "四分之三左侧-d070" draft

★ 看图时的判断标准（按重要性排序）
    ① 头有没有真的转过去；② 转过去之后还是不是同一个人（看眉骨、鼻梁、单个痣）；
    ③ 皮肤有没有开始变塑料（denoise 越高越明显）。
    ★ 取「转得动的最小 denoise」，不是取转得最狠的那档。

【参数】
    底模      FLUX1\\flux1-dev-fp8.safetensors（一体化 fp8，无需另配 VAE/文本编码器）
    采样      euler + simple，第一段 28 步 / 第二段 18 步
    cfg       **必须 1.0**（套 SDXL 的 10 会直接炸图）
    guidance  FluxGuidance 3.5
    分辨率    1024x1280
    seed      固定 20260917（四个分支同 seed，唯一变量是 denoise）
    基图      wendeng_v23_face_base.png = v23 脸部正面成品（身份已锁定）

⚠️ FLUX 在 cfg=1.0 下**没有负向通道**，节点里那条负向接上去也不生效（留空仅为满足接口）。
   「不要磨皮」只能在正向里写成 "no beauty retouching / no airbrushing" 这类否定式短语。
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


# ==================== 1) 上传身份基图 ====================
print("=== 1) 身份基图 ===")
os.makedirs(WF_DIR, exist_ok=True)
LOCAL_BASE = os.path.join(WF_DIR, "flux_face_base_v23_%dx%d.png" % (W, H))
im = Image.open(SRC_BASE_IMG).convert("RGB")
print("  源: %s  %dx%d" % (os.path.basename(SRC_BASE_IMG), im.size[0], im.size[1]))
im.resize((W, H), Image.LANCZOS).save(LOCAL_BASE, "PNG", optimize=True)
print("  ->", upload(LOCAL_BASE, UPLOAD_NAME)[:200])

# ==================== 2) 构建工作流 ====================
print("\n=== 2) 构建工作流 ===")
node_list, link_list = [], []


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


N(6, "Note", (61, 20), (1700, 760), [NOTE], [], [], 0,
  "★ 说明 · Flux 迭代转头：为什么不一步转到 90°、本次要回答什么")

N(1, "CheckpointLoaderSimple", (61, 820), (470, 100), [CKPT], [],
  [O("MODEL", "MODEL", 0), O("CLIP", "CLIP", 1), O("VAE", "VAE", 2)], 1,
  "FLUX.1-dev-fp8（一体化，无需另配 VAE/clip）")

N(2, "LoadImage", (61, 980), (400, 400), [UPLOAD_NAME, "image"], [],
  [O("IMAGE", "IMAGE", 0), O("MASK", "MASK", 1)], 2,
  "★ 身份基图 = v23 脸部正面成品（已确认身份）")

N(3, "ImageScale", (500, 980), (330, 100), ["lanczos", W, H, "center"],
  [I("image", "IMAGE")], [O("IMAGE", "IMAGE", 0)], 3, "统一到 1024x1280")

N(4, "VAEEncode", (870, 980), (280, 60), [],
  [I("pixels", "IMAGE"), I("vae", "VAE")], [O("LATENT", "LATENT", 0)], 4,
  "身份 latent（img2img 起点）")

N(5, "UpscaleModelLoader", (61, 1440), (430, 80), [UPSCALER], [],
  [O("UPSCALE_MODEL", "UPSCALE_MODEL", 0)], 5, "放大模型 4x-UltraSharp")

N(7, "CLIPTextEncode", (1190, 980), (420, 130), [""],
  [I("clip", "CLIP")], [O("CONDITIONING", "CONDITIONING", 0)], 6,
  "★ 负向（Flux cfg=1.0 下无效，留空仅为满足接口）")

BASE_NODES = [1, 2, 3, 4, 5, 6, 7]
branch_ids = []

for i, (label, prompt, den, gd) in enumerate(TURNS):
    b = 10 + i * 11
    y = 1620 + i * 780
    ids = [b + k for k in range(11)]
    branch_ids.append(ids)
    tag = label.replace("-d", " denoise ").replace("四分之三", "3/4")

    N(b + 0, "CLIPTextEncode", (61, y), (700, 480), [prompt],
      [I("clip", "CLIP")], [O("CONDITIONING", "CONDITIONING", 0)], 10 + i * 11,
      "正向 · %s（自然语言，无 75 token 限制）" % tag)
    N(b + 1, "FluxGuidance", (800, y), (300, 60), [gd],
      [I("conditioning", "CONDITIONING")], [O("CONDITIONING", "CONDITIONING", 0)], 11 + i * 11,
      "Guidance %.1f" % gd)
    N(b + 2, "KSampler", (800, y + 130), (330, 262),
      [SEED, "fixed", STEPS_1, 1.0, "euler", "simple", den],
      [I("model", "MODEL"), I("positive", "CONDITIONING"), I("negative", "CONDITIONING"),
       I("latent_image", "LATENT")],
      [O("LATENT", "LATENT", 0)], 12 + i * 11,
      "① %s img2img  denoise %.2f" % (tag, den))
    N(b + 3, "VAEDecode", (1190, y + 130), (250, 60), [],
      [I("samples", "LATENT"), I("vae", "VAE")], [O("IMAGE", "IMAGE", 0)], 13 + i * 11)
    N(b + 4, "SaveImage", (1190, y + 230), (420, 500), ["闻灯FluxV3-%s-草稿" % label],
      [I("images", "IMAGE")], [], 14 + i * 11, "草稿 · %s（先跑这个）" % tag)
    N(b + 5, "ImageUpscaleWithModel", (1500, y + 130), (400, 80), [],
      [I("upscale_model", "UPSCALE_MODEL"), I("image", "IMAGE")],
      [O("IMAGE", "IMAGE", 0)], 15 + i * 11)
    N(b + 6, "ImageScaleBy", (1500, y + 260), (300, 80), ["lanczos", 0.5],
      [I("image", "IMAGE")], [O("IMAGE", "IMAGE", 0)], 16 + i * 11, "缩回 2048x2560")
    N(b + 7, "VAEEncode", (1500, y + 380), (280, 60), [],
      [I("pixels", "IMAGE"), I("vae", "VAE")], [O("LATENT", "LATENT", 0)], 17 + i * 11)
    N(b + 8, "KSampler", (1850, y + 130), (330, 262),
      [SEED, "fixed", STEPS_2, 1.0, "euler", "simple", DEN_2],
      [I("model", "MODEL"), I("positive", "CONDITIONING"), I("negative", "CONDITIONING"),
       I("latent_image", "LATENT")],
      [O("LATENT", "LATENT", 0)], 18 + i * 11,
      "② %s 放大重绘  denoise %.2f" % (tag, DEN_2))
    N(b + 9, "VAEDecode", (2240, y + 130), (250, 60), [],
      [I("samples", "LATENT"), I("vae", "VAE")], [O("IMAGE", "IMAGE", 0)], 19 + i * 11)
    N(b + 10, "SaveImage", (2240, y + 230), (420, 500), ["闻灯FluxV3-%s-成品" % label],
      [I("images", "IMAGE")], [], 20 + i * 11, "成品 · %s" % tag)

byid = {n["id"]: n for n in node_list}

CLIP = "CLIP"; COND = "CONDITIONING"; LAT = "LATENT"; IMG = "IMAGE"; VAE = "VAE"; UPM = "UPSCALE_MODEL"
L(1, 1, 7, 0, CLIP)
L(2, 0, 3, 0, IMG)
L(3, 0, 4, 0, IMG)
L(1, 2, 4, 1, VAE)

for i, (label, prompt, den, gd) in enumerate(TURNS):
    b = 10 + i * 11
    L(1, 1, b + 0, 0, CLIP)
    L(b + 0, 0, b + 1, 0, COND)
    L(1, 0, b + 2, 0, "MODEL")
    L(b + 1, 0, b + 2, 1, COND)
    L(7, 0, b + 2, 2, COND)
    L(4, 0, b + 2, 3, LAT)
    L(b + 2, 0, b + 3, 0, LAT)
    L(1, 2, b + 3, 1, VAE)
    L(b + 3, 0, b + 4, 0, IMG)
    L(b + 3, 0, b + 5, 1, IMG)
    L(5, 0, b + 5, 0, UPM)
    L(b + 5, 0, b + 6, 0, IMG)
    L(b + 6, 0, b + 7, 0, IMG)
    L(1, 2, b + 7, 1, VAE)
    L(1, 0, b + 8, 0, "MODEL")
    L(b + 1, 0, b + 8, 1, COND)
    L(7, 0, b + 8, 2, COND)
    L(b + 7, 0, b + 8, 3, LAT)
    L(b + 8, 0, b + 9, 0, LAT)
    L(1, 2, b + 9, 1, VAE)
    L(b + 9, 0, b + 10, 0, IMG)

# ---- 回填 ----
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
    "id": str(uuid.uuid4()), "revision": 0,
    "last_node_id": max(ids), "last_link_id": len(link_list),
    "nodes": sorted(node_list, key=lambda n: n.get("order", 0)),
    "links": link_list, "groups": [], "config": {}, "extra": {}, "version": 0.4,
}

print("  节点数 %d  链接数 %d" % (len(node_list), len(link_list)))
if errs:
    print("  ★ 自检失败：")
    for e in errs:
        print("     -", e)
    sys.exit(1)
print("  自检通过")

local_out = os.path.join(WF_DIR, "闻灯-Flux脸部三视角-迭代转头.json")
json.dump(wf, open(local_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("  已写出 %s  (%.1f KB)" % (local_out, os.path.getsize(local_out) / 1024))

# ==================== 3) 推送 ====================
print("\n=== 3) 推送 ===")
NAME = "闻灯-Flux脸部三视角-迭代转头.json"
body = json.dumps(wf, ensure_ascii=False).encode("utf-8")
ok = False
for path in ("/api/userdata/workflows%%2F%s?overwrite=true" % urllib.parse.quote(NAME),
             "/api/userdata/workflows%%2F%s?overwrite=true" % NAME):
    try:
        r = raw(path, body, "application/json", 120, "POST")
        print("  写入成功 ->", r.decode()[:200]); ok = True; break
    except Exception as e:
        print("  写入失败(%s): %s" % (path[:60], type(e).__name__))
if not ok:
    print("  ★ 推送失败"); sys.exit(1)

print("\n  服务器工作流列表：")
print("   ", json.loads(raw("/api/userdata?dir=workflows", None, None, 60).decode("utf-8", "replace")))

print("\n分支清单（SaveImage 前缀 = 跑图时用的关键词）：")
for i, (label, prompt, den, gd) in enumerate(TURNS):
    b = 10 + i * 11
    print("  节点 %-3s denoise %.2f  guidance %.1f  →  闻灯FluxV3-%s-[草稿|成品]" % (b + 2, den, gd, label))
print("\nOK")
