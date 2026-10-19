# -*- coding: utf-8 -*-
"""闻灯 · Kontext「转头」工作流 —— 构建 UI 格式 JSON 并推送到远程 ComfyUI

★ 与前面几版的根本区别
    「闻灯-Flux脸部三视角.json」走 img2img：从原图出发改一点点 → 转不动头。
    「-迭代转头.json」把 denoise 拉到 0.95：转得动，但**人变了**。
    本版走 **Kontext 机制**：参考图的 latent 进 conditioning，采样从**纯噪声**开始
    （denoise 1.0）→ 朝向可以大改，人物特征由 conditioning 锁住。

★ 推送前会先查节点是否齐全，缺哪个直接报出来，不会推一个跑不起来的空壳。

用法：
    python push_kontext_wf.py
"""
import urllib.request, urllib.parse, json, ssl, uuid, os, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, r"D:\xiaobai-claude code\ComfyUI\venv\Lib\site-packages")
from PIL import Image

# --local：只构建 JSON 写盘，跳过在线前置检查/上传/推送（实例没开时用；也给 build_master_wf.py 复用）
LOCAL_ONLY = "--local" in sys.argv

BASE = os.environ.get("COMFY_BASE", "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016")
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
ROOT = r"D:\xiaobai-claude code\comfyUImd"
WF_DIR = os.path.join(ROOT, "_scripts", "_wf")
SRC = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "v23-脸部三视角", "闻灯v23-脸部正面-成品_00001_.png")
UPLOAD_NAME = "wendeng_v23_face_base.png"

# ★★ 2026-09-18：模型引用必须写成**服务器上真实落盘的名字（含子目录）**。
#    这四个文件是用 ComfyUI-Manager 下的，Manager 按 model-list.json 的 `save_path` 自动建子目录：
#      text_encoders\t5\t5xxl_fp8_e4m3fn_scaled.safetensors
#      vae\FLUX1\ae.safetensors
#      diffusion_models\FLUX1\flux1-schnell.safetensors   ← ★ 这里面装的其实是 **Kontext**
#    最后一条是权宜之计：Manager V3.41 只认白名单里的模型名，Kontext 不在名单，
#    于是借 `flux1-schnell` 槽位下载 → 文件以该名落盘（内容确是 11.09GiB 的 Kontext fp8_scaled）。
#    ⚠️ 引用名少写 `FLUX1\` / `t5\` → Loader 抛 value not in list，**只有跑图时才暴露**。
#    实测验证（2026-09-18 17:28）：GET /models/diffusion_models → ["FLUX1\\flux1-schnell.safetensors"]
UNET = "FLUX1\\flux1-schnell.safetensors"
CLIP1 = "t5\\t5xxl_fp8_e4m3fn_scaled.safetensors"
CLIP2 = "clip_l.safetensors"
VAE = "FLUX1\\ae.safetensors"

STEPS, CFG, GUID, DEN, SEED = 20, 1.0, 3.0, 1.0, 20260917

# ★ 编辑指令：写成「指令」而不是画面描述；一轮只改一件事（这次只改朝向）
KEEP = ("Keep the same person, the same messy wavy black hair, the same thick eyebrows, the same "
        "nose and jawline, the same unretouched skin with visible pores and the same small mole, "
        "the same lighting, the same plain white background and the same faded blue shirt.")
NOSTYLE = "Do not restyle, do not smooth or airbrush the skin, do not change his identity."

LEFT_90 = ("Turn his head to a full 90-degree LEFT profile, so the camera sees only the left side of "
           "his face: one eye, the left eyebrow, the left ear, the ridge of the nose and the lips in "
           "profile. His right eye and the right half of his face are hidden. " + KEEP + " " + NOSTYLE)

RIGHT_90 = ("Turn his head to a full 90-degree RIGHT profile, so the camera sees only the right side of "
            "his face: one eye, the right eyebrow, the right ear, the ridge of the nose and the lips in "
            "profile. His left eye and the left half of his face are hidden. " + KEEP + " " + NOSTYLE)

LEFT_45 = ("Change the camera angle so his head is turned about 45 degrees to his left, a three-quarter "
           "view: his left eye is near the middle of the frame, his right eye is pushed toward the far "
           "contour of his cheek, the nose is foreshortened, and the far jaw and cheekbone still show. "
           + KEEP + " " + NOSTYLE)

VIEWS = [("左侧90", LEFT_90), ("右侧90", RIGHT_90), ("左侧45", LEFT_45)]

NEED_NODES = ["UNETLoader", "DualCLIPLoader", "VAELoader", "LoadImage", "VAEEncode",
              "CLIPTextEncode", "FluxGuidance", "ReferenceLatent", "KSampler",
              "VAEDecode", "SaveImage", "FluxKontextImageScale"]

NOTE = """【闻灯 · Flux Kontext 转头】 三次失败之后的第三版，换了机制

★★ 前两版为什么不行（别再回头走老路）
   v1「纯文生图」    → 同 seed + 同 token ≠ 同一个人，脸直接换人
   v2「三视角 img2img」→ denoise 0.55/0.70/0.85 全是大正面，头根本没转
   v3「迭代转头」     → denoise 0.95 转出约 25–30°，**但人变了**（脸变宽、唇变厚、皮肤变光）
   结论：**img2img 给不了「同一张脸 + 转头」**。这不是参数问题，是机制问题。

★★ 本版换机制：Kontext
   参考图的 latent **进 conditioning**（ReferenceLatent），采样从**纯噪声**开始（denoise 1.0）。
   → 朝向可以大改，人物特征由 conditioning 锁住。这才是"改姿势但不改人"的正解。

★ 关键参数（与 SDXL / Flux-dev 都不通用，别照搬）
   cfg        必须 1.0
   guidance   FluxGuidance 3.0（编辑任务偏低更稳）
   denoise    **1.0** —— 注意：这里不是 img2img，别拿前两版的 0.30 / 0.95 套过来
   尺寸       随参考图（FluxKontextImageScale → 16 的倍数），**不要自己写 1024x1280**
   采样       euler + simple，20 步，seed 固定 20260917

★ 提示词写法：写「编辑指令」，不是画面描述
   反例（前两版就是这么写的，所以不生效）：
       "A true full 90-degree LEFT profile of a 24-year-old East Asian man with..."
   正例（本版）：
       "Turn his head to a full 90-degree LEFT profile... Keep the same person..."
   ★ 一轮只改一件事。这次只改朝向，服装/光线/背景一律要求保持。

★ 跑法
   python _scripts\\run_wf.py "闻灯-Kontext转头.json" "左侧90" final
   （三条分支可逗号一次跑完： "左侧90,右侧90,左侧45"）

⚠️ Dev 版官方承认的短板：**有些提示词它可能完全不编辑**。
   不生效时换措辞，例如改说 "Change the camera angle so we see him from his left side."

【先脸后身（约束 §14 / H04）】
   脸部三视角**人工确认通过**之前，禁止做全身图。

【收尾】产物确认落盘后**立刻关机** —— 豆按开机时长烧，与是否在跑图无关。
"""


def raw(p, data=None, ctype=None, timeout=180, method=None):
    h = {}
    if ctype:
        h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h, method=method),
                                  timeout=timeout, context=ctx).read()


# ==================== 0) 前置检查 ====================
print("=== 0) 前置检查 ===")
if LOCAL_ONLY:
    print("   [--local] 跳过（需在线）")
else:
    alln = json.loads(raw("/object_info", None, None, 240).decode("utf-8", "replace"))
    miss = [n for n in NEED_NODES if n not in alln]
    for n in NEED_NODES:
        print("   %-24s %s" % (n, "✔" if n in alln else "✘"))
    if miss:
        print("\n★ 缺节点 %s → 现在推上去也跑不起来，先补节点。不推送。" % miss)
        sys.exit(1)
    print("   节点齐全")

    for folder, fn in (("diffusion_models", UNET), ("text_encoders", CLIP1),
                       ("text_encoders", CLIP2), ("vae", VAE)):
        try:
            d = json.loads(raw("/internal/files/%s" % folder, None, None, 60).decode("utf-8", "replace"))
            names = [x.get("name") if isinstance(x, dict) else x for x in d]
        except Exception:
            names = []
        print("   [%s] %-46s %s" % (folder, fn, "✔ 在" if fn in names else "✘ 不在"))
        if fn not in names:
            print("     ★ 模型没到，先用 _scripts/kontext_setup.py download 下完再来。")

# ==================== 1) 上传身份基图 ====================
print("\n=== 1) 身份基图 ===")
os.makedirs(WF_DIR, exist_ok=True)
local_base = os.path.join(WF_DIR, "kontext_base_v23.png")
Image.open(SRC).convert("RGB").save(local_base, "PNG", optimize=True)
if LOCAL_ONLY:
    print("   [--local] 本地已备好 %s，跳过上传" % local_base)
else:
    data = open(local_base, "rb").read()
    bd = "----wb" + uuid.uuid4().hex
    body = b""
    for k, v in (("overwrite", "true"), ("type", "input"), ("subfolder", "")):
        body += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n" % (bd, k, v)).encode()
    body += ("--%s\r\nContent-Disposition: form-data; name=\"image\"; filename=\"%s\"\r\n"
             "Content-Type: image/png\r\n\r\n" % (bd, UPLOAD_NAME)).encode()
    body += data + ("\r\n--%s--\r\n" % bd).encode()
    r = urllib.request.urlopen(
        urllib.request.Request(BASE + "/upload/image", data=body,
                               headers={"Content-Type": "multipart/form-data; boundary=%s" % bd}),
        timeout=300, context=ctx).read().decode()
    print("  ->", r[:160])

# ==================== 2) 构建工作流 ====================
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


def I(name, typ):
    return {"name": name, "type": typ, "link": None}


def O(name, typ, idx):
    return {"name": name, "type": typ, "slot_index": idx, "links": []}


def L(fid, fslot, tid, tslot, typ):
    lid = len(link_list) + 1
    link_list.append([lid, fid, fslot, tid, tslot, typ])
    return lid


N(6, "Note", (61, 20), (1620, 720), [NOTE], [], [], 0,
  "★ 说明 · 为什么换到 Kontext 机制（img2img 已证明给不了「同一张脸 + 转头」）")

N(1, "UNETLoader", (61, 780), (430, 90), [UNET, "default"], [],
  [O("MODEL", "MODEL", 0)], 1, "Kontext fp8（借 flux1-schnell 槽位落盘 · FLUX1 子目录）")
N(2, "DualCLIPLoader", (61, 900), (430, 130), [CLIP1, CLIP2, "flux"], [],
  [O("CLIP", "CLIP", 0)], 2, "DualCLIP：t5xxl_fp8（t5 子目录） + clip_l")
N(3, "VAELoader", (61, 1060), (430, 80), [VAE], [],
  [O("VAE", "VAE", 0)], 3, "VAE ae（FLUX1 子目录）")
N(4, "LoadImage", (61, 1170), (400, 400), [UPLOAD_NAME, "image"], [],
  [O("IMAGE", "IMAGE", 0), O("MASK", "MASK", 1)], 4, "★ 身份参考图 = v23 正面（已确认）")
N(5, "FluxKontextImageScale", (500, 1170), (330, 80), [],
  [I("image", "IMAGE")], [O("IMAGE", "IMAGE", 0)], 5, "缩到 Kontext 合适尺寸（勿手写宽高）")
N(7, "VAEEncode", (870, 1170), (280, 60), [],
  [I("pixels", "IMAGE"), I("vae", "VAE")], [O("LATENT", "LATENT", 0)], 6,
  "参考 latent（既喂 conditioning 也当采样起点）")
N(8, "CLIPTextEncode", (1190, 1170), (420, 120), [""],
  [I("clip", "CLIP")], [O("CONDITIONING", "CONDITIONING", 0)], 7,
  "★ 负向（cfg=1.0 下无效，留空仅为满足接口）")

for i, (label, prompt) in enumerate(VIEWS):
    b = 10 + i * 10
    y = 1700 + i * 640
    N(b + 0, "CLIPTextEncode", (61, y), (700, 420), [prompt],
      [I("clip", "CLIP")], [O("CONDITIONING", "CONDITIONING", 0)], 10 + i * 10,
      "★ 编辑指令 · %s（写成指令，不是画面描述）" % label)
    N(b + 1, "FluxGuidance", (800, y), (300, 60), [GUID], [I("conditioning", "CONDITIONING")],
      [O("CONDITIONING", "CONDITIONING", 0)], 11 + i * 10, "Guidance %.1f" % GUID)
    N(b + 2, "ReferenceLatent", (800, y + 110), (300, 60), [],
      [I("conditioning", "CONDITIONING"), I("latent", "LATENT")],
      [O("CONDITIONING", "CONDITIONING", 0)], 12 + i * 10, "★ 参考图进 conditioning")
    N(b + 3, "KSampler", (1140, y + 60), (330, 262),
      [SEED, "fixed", STEPS, CFG, "euler", "simple", DEN],
      [I("model", "MODEL"), I("positive", "CONDITIONING"), I("negative", "CONDITIONING"),
       I("latent_image", "LATENT")], [O("LATENT", "LATENT", 0)], 13 + i * 10,
      "★ %s：从纯噪声重画  denoise %.1f" % (label, DEN))
    N(b + 4, "VAEDecode", (1500, y + 60), (250, 60), [],
      [I("samples", "LATENT"), I("vae", "VAE")], [O("IMAGE", "IMAGE", 0)], 14 + i * 10)
    # ★ 前缀必须带「-成品」后缀：run_wf.py 用 endswith("成品") 区分成品/草稿，
    #   少了它 p4 会「找不到匹配的 SaveImage」直接退出（本块无草稿分支，所以只有成品）。
    N(b + 5, "SaveImage", (1500, y + 160), (420, 460), ["闻灯Kontext-%s-成品" % label],
      [I("images", "IMAGE")], [], 15 + i * 10, "成品 · %s" % label)

byid = {n["id"]: n for n in node_list}
CLIP, COND, LAT, IMG, VAE_T = "CLIP", "CONDITIONING", "LATENT", "IMAGE", "VAE"

L(2, 0, 8, 0, CLIP)
L(3, 0, 7, 1, VAE_T)
L(4, 0, 5, 0, IMG)
L(5, 0, 7, 0, IMG)

for i, (label, prompt) in enumerate(VIEWS):
    b = 10 + i * 10
    L(2, 0, b + 0, 0, CLIP)
    L(b + 0, 0, b + 1, 0, COND)
    L(b + 1, 0, b + 2, 0, COND)
    L(7, 0, b + 2, 1, LAT)
    L(1, 0, b + 3, 0, "MODEL")
    L(b + 2, 0, b + 3, 1, COND)
    L(8, 0, b + 3, 2, COND)
    L(7, 0, b + 3, 3, LAT)
    L(b + 3, 0, b + 4, 0, LAT)
    L(3, 0, b + 4, 1, VAE_T)
    L(b + 4, 0, b + 5, 0, IMG)

for n in node_list:
    for i in n.get("inputs", []):
        i["link"] = None
    for o in n.get("outputs", []):
        o["links"] = []
for lid, fid, fslot, tid, tslot, typ in link_list:
    s = byid.get(fid)
    if s and fslot < len(s.get("outputs", [])):
        s["outputs"][fslot]["links"].append(lid)
    d = byid.get(tid)
    if d and tslot < len(d.get("inputs", [])):
        d["inputs"][tslot]["link"] = lid

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
    for slot in n.get("inputs", []):
        if slot["link"] is None:
            errs.append("节点 %d(%s) 输入 %s 未连接" % (n["id"], n["type"], slot["name"]))
    if n["type"] == "KSampler" and len(n.get("widgets_values", [])) != 7:
        errs.append("KSampler 节点 %d widgets 数量异常" % n["id"])

wf = {"id": str(uuid.uuid4()), "revision": 0, "last_node_id": max(ids),
      "last_link_id": len(link_list),
      "nodes": sorted(node_list, key=lambda n: n.get("order", 0)),
      "links": link_list, "groups": [], "config": {}, "extra": {}, "version": 0.4}

print("  节点数 %d  链接数 %d" % (len(node_list), len(link_list)))
if errs:
    print("  ★ 自检失败：")
    for e in errs:
        print("     -", e)
    sys.exit(1)
print("  自检通过")

NAME = "闻灯-Kontext转头.json"
local_out = os.path.join(WF_DIR, NAME)
json.dump(wf, open(local_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("  已写出 %s (%.1f KB)" % (local_out, os.path.getsize(local_out) / 1024))

# ==================== 3) 推送 ====================
print("\n=== 3) 推送 ===")
if LOCAL_ONLY:
    print("   [--local] 跳过推送。")
    print("   注：本块已作为【闻灯 · Kontext 转头】并入主工作流 —— 由 build_master_wf.py 装配，")
    print("       开机后统一跑 build_master_wf.py --fetch --push，不再单独推这个文件。")
    print("\nOK（仅本地构建）")
    sys.exit(0)

body = json.dumps(wf, ensure_ascii=False).encode("utf-8")
for path in ("/api/userdata/workflows%%2F%s?overwrite=true" % urllib.parse.quote(NAME),
             "/api/userdata/workflows%%2F%s?overwrite=true" % NAME):
    try:
        print("  写入成功 ->", raw(path, body, "application/json", 120, "POST").decode()[:200])
        break
    except Exception as e:
        print("  写入失败(%s): %s" % (path[:60], type(e).__name__))
else:
    print("  ★ 推送失败"); sys.exit(1)

print("\n  服务器工作流列表：")
print("   ", raw("/api/userdata?dir=workflows", None, None, 60).decode("utf-8", "replace")[:600])
print("\n跑法：python _scripts\\run_wf.py \"%s\" \"左侧90,右侧90,左侧45\" final" % NAME)
print("\nOK")
