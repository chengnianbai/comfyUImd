# -*- coding: utf-8 -*-
"""把服务器上的《夜市百相簿》工作流升级为 v19 管线（UI 格式 JSON）

改动：
  1) 底模 majicmixRealistic_v7 -> leosamsHelloworldXL_helloworldXL70.safetensors (SDXL)
  2) 新增 CLIPSetLastLayer，stop_at_clip_layer=-1（SDXL 必须 Clip Skip 1；SD1.5 是 2）
  3) EmptyLatentImage 512x768 -> 896x1152（HelloWorld 官方推荐竖构图）
  4) 第一段 KSampler：steps 20->30, cfg 6.5->10, seed 锁 20260916 fixed
  5) 删掉 LatentUpscale（只放大量不加细节）-> UpscaleModelLoader + ImageUpscaleWithModel
     + ImageScaleBy(0.5) + VAEEncode
  6) 第二段 KSampler：cfg 10, denoise 0.45->0.25
  7) 负向由 1 段拆成 3 段（N1/N2/N3）+ 两级 ConditioningCombine（每段各自受 75 token 上限）
  8) 提示词升级为 v19 现行版本（脸部正面为当前阶段）
"""
import json, os, copy

SRC = r"D:\xiaobai-claude code\comfyUImd\_scripts\_wf\server_夜市百相簿_原始.json"
DST = r"D:\xiaobai-claude code\comfyUImd\_scripts\_wf\夜市百相簿_v19.json"

# ---------------- 现行提示词（与 gen_wendeng_v19.py 完全一致） ----------------
BGD = "pure white background"
HAIR = "messy wavy black hair"
MOLE = "small mole at outer eye corner"
SHIRT = "faded blue shirt"
COAT = "dark worn trench coat"
CHAR = "1boy, solo, 24 year old east asian man, masculine face, strong jaw, " + HAIR

FACE_A_BODY = ("face closeup, head and shoulders, " + CHAR + ", " + MOLE + ", "
               + SHIRT + " collar, dark coat collar, " + BGD)
FACE_A = "front view, looking at viewer, " + FACE_A_BODY
FACE_B = ("detailed face, detailed eyes, dark circles under eyes, iris detail, individual eyelashes, "
          "thick eyebrows, stubble, " + MOLE + ", visible skin pores, skin texture, skin imperfections, "
          "peach fuzz, messy wavy hair, individual hair strands, faded shirt collar, dark coat, "
          + BGD + ", flat even lighting, sharp focus, photorealistic")

BODY_A_TPL = ("full body shot, head to toe, %s, standing straight, arms down at sides, hands visible, "
              + CHAR + ", " + MOLE + ", " + SHIRT + ", " + COAT + ", open coat, " + BGD)
BODY_B_TPL = ("1boy, wavy tousled hair, tired eyes, thick eyebrows, stubble, weathered skin, "
              "detailed skin texture, skin pores, film grain, worn wrinkled clothes, dark trousers, "
              "old worn shoes, arms down at sides, hands visible, " + BGD
              + ", even lighting, sharp focus, photorealistic")

N1 = ("1girl, female, feminine face, delicate, fragile, soft features, soft round face, "
      "pretty boy, boyish face, bishounen, makeup, lipstick, rosy lips, eyeshadow, "
      "teenage, child, narrow face, pale skin, blonde hair, straight hair, "
      "slicked back hair, undercut, side part, neat hair")
N2 = ("t-shirt, sweater, business suit, blazer, tie, dress shirt, formal wear, "
      "ironed shirt, wool coat, brown coat, beige coat, blue coat, light coat, "
      "new clothes, fashion model, jeans, denim, bare chest, shirtless, nude, "
      "white sneakers, new shoes, police uniform, wuxia, hanfu")
N3_FACE = ("dark background, grey background, gradient background, vignette, shadow, "
           "busy background, full body, bare shoulders, shirtless, freckles, mole on cheek, mole on forehead, "
           "extra fingers, bad hands, watermark, text, blurry, lowres, airbrushed, "
           "over-smoothed, beauty filter, smooth skin, retouched")
N3_FULL = ("hands in pockets, hands behind back, hands hidden, holding object, prop, "
           "contrapposto, wide stance, legs apart, pockets, "
           "extra fingers, bad hands, watermark, text, blurry, lowres, busy background, "
           "grey background, dark background, gradient background, vignette, shadow, "
           "airbrushed, over-smoothed")

NOTE = """角色：闻灯 · 24 岁男性 · 半妖借形人 / 旧市夜巡所临时书记
底模：leosamsHelloworldXL_helloworldXL70（SDXL）  |  896×1152  |  Clip Skip 1（CLIPSetLastLayer = -1）
采样：dpmpp_2m + karras，第一段 30 步 CFG 10 denoise 1.0 → ESRGAN 放大 → 第二段 20 步 CFG 10 denoise 0.25
seed 固定 20260916（两个 KSampler 都是 fixed，别开随机）

【★ 出图流程铁律——先脸后身】
  ① 先只出「脸部正面」，确认这个人没问题；
  ② 再用同一组角色 token + 同一 seed 出「左侧脸 / 右侧脸」；
  ③ 脸全部确认后，才出全身图。
  理由：v18 就是因为脸和身用了两套描述词，出成"脸是成年男、身是少年"的两个人。
  角色 token 块（脸/身必须逐字复用）：
      1boy, solo, 24 year old east asian man, masculine face, strong jaw, messy wavy black hair

【当前阶段：脸部正面】A段=节点2，B段=节点3，负向=节点5+18+19（三段合并）
  换视角只改 A 段最前面的取景词：front view, looking at viewer / side profile view, facing left / facing right

【下一步：全身图】脸部确认后再切，A段换成：
  """ + (BODY_A_TPL % "front view") + """
  B段换成：
  """ + BODY_B_TPL + """
  负向第三段（节点19）换成 N3_FULL：
  """ + N3_FULL + """

【锚点（不可改，详见 comfyUImd/.workbuddy/memory/角色视觉锚点-锁定.md）】
  黑发微卷 / 眼尾一颗小痣 / 洗得发白的蓝色旧衬衫 / 深色旧风衣 / 旧鞋 / 眼带睡眠不足
  禁止：现代警察制服、古装侠客、偶像妆、夸张肌肉、少年化脸孔
  道具（账簿、朱砂粉盒）不进角色设定图，之后单独生成

【纯白背景】提示词只能给到浅灰，最终靠脚本后处理：
  _scripts/post_whitebg.py <图片路径> --t 12
"""

with open(SRC, encoding="utf-8") as f:
    wf = json.load(f)

nodes = {n["id"]: n for n in wf["nodes"]}

# ---------- 1) Note ----------
nodes[16]["widgets_values"] = [NOTE]
nodes[16]["size"] = [1720, 720]

# ---------- 2) 底模 ----------
nodes[1]["widgets_values"] = ["leosamsHelloworldXL_helloworldXL70.safetensors"]
# loader 的 CLIP 输出改接 ClipSkip 节点
nodes[1]["outputs"][1]["links"] = []          # 由链接表统一重建
nodes[1]["outputs"][0]["links"] = []
nodes[1]["outputs"][2]["links"] = []

# ---------- 3) 提示词 ----------
nodes[2]["widgets_values"] = [FACE_A]
nodes[3]["widgets_values"] = [FACE_B]
nodes[5]["widgets_values"] = [N1]

# ---------- 4) 分辨率 / 采样参数 ----------
nodes[6]["widgets_values"] = [896, 1152, 1]
nodes[7]["widgets_values"] = [20260916, "fixed", 30, 10.0, "dpmpp_2m", "karras", 1.0]
nodes[12]["widgets_values"] = [20260916, "fixed", 20, 10.0, "dpmpp_2m", "karras", 0.25]

# ---------- 5) 删除 LatentUpscale ----------
wf["nodes"] = [n for n in wf["nodes"] if n["id"] != 11]

# ---------- 6) 新节点 ----------
def node(nid, ntype, pos, size, widgets, inputs, outputs, order, title=None):
    n = {"id": nid, "type": ntype, "pos": pos, "size": size, "flags": {}, "order": order,
         "mode": 0, "inputs": inputs, "outputs": outputs,
         "properties": {"Node name for S&R": ntype}}
    if title:
        n["title"] = title
    if widgets is not None:
        n["widgets_values"] = widgets
    return n


def inp(name, typ, link=None):
    return {"name": name, "type": typ, "link": link}


def out(name, typ, idx, links=None):
    return {"name": name, "type": typ, "slot_index": idx, "links": links or []}


wf["nodes"].extend([
    node(17, "CLIPSetLastLayer", [61, 200], [300, 60], [-1],
         [inp("clip", "CLIP")], [out("CLIP", "CLIP", 0)], 1, "Clip Skip = 1（SDXL 必须）"),
    node(18, "CLIPTextEncode", [571, 1400], [560, 130], [N2],
         [inp("clip", "CLIP")], [out("CONDITIONING", "CONDITIONING", 0)], 3, "负向 N2 服饰/正装"),
    node(19, "CLIPTextEncode", [571, 1580], [560, 170], [N3_FACE],
         [inp("clip", "CLIP")], [out("CONDITIONING", "CONDITIONING", 0)], 4, "负向 N3 背景/构图（脸部版）"),
    node(20, "ConditioningCombine", [1191, 1420], [330, 90], [],
         [inp("conditioning_1", "CONDITIONING"), inp("conditioning_2", "CONDITIONING")],
         [out("CONDITIONING", "CONDITIONING", 0)], 6, "负向 N1+N2"),
    node(21, "ConditioningCombine", [1191, 1560], [330, 90], [],
         [inp("conditioning_1", "CONDITIONING"), inp("conditioning_2", "CONDITIONING")],
         [out("CONDITIONING", "CONDITIONING", 0)], 7, "负向 (N1+N2)+N3"),
    node(22, "UpscaleModelLoader", [61, 950], [430, 80], ["4x-UltraSharp (1).pth"],
         [], [out("UPSCALE_MODEL", "UPSCALE_MODEL", 0)], 9, "放大模型 4x-UltraSharp"),
    node(23, "ImageUpscaleWithModel", [571, 950], [420, 80], [],
         [inp("upscale_model", "UPSCALE_MODEL"), inp("image", "IMAGE")],
         [out("IMAGE", "IMAGE", 0)], 10),
    node(24, "ImageScaleBy", [1051, 950], [330, 80], ["lanczos", 0.5],
         [inp("image", "IMAGE")], [out("IMAGE", "IMAGE", 0)], 11, "缩回 1792×2304"),
    node(25, "VAEEncode", [1421, 950], [300, 60], [],
         [inp("pixels", "IMAGE"), inp("vae", "VAE")], [out("LATENT", "LATENT", 0)], 12),
])

# ---------- 7) 重建链接 ----------
L = []   # [id, from_node, from_slot, to_node, to_slot, type]


def link(fid, fslot, tid, tslot, typ):
    lid = len(L) + 1
    L.append([lid, fid, fslot, tid, tslot, typ])
    return lid


lk_clipskip = link(1, 1, 17, 0, "CLIP")
lk_clipA = link(17, 0, 2, 0, "CLIP")
lk_clipB = link(17, 0, 3, 0, "CLIP")
lk_clipN1 = link(17, 0, 5, 0, "CLIP")
lk_clipN2 = link(17, 0, 18, 0, "CLIP")
lk_clipN3 = link(17, 0, 19, 0, "CLIP")
lk_pA = link(2, 0, 4, 0, "CONDITIONING")
lk_pB = link(3, 0, 4, 1, "CONDITIONING")
lk_n12 = link(5, 0, 20, 0, "CONDITIONING")
lk_n22 = link(18, 0, 20, 1, "CONDITIONING")
lk_n123 = link(20, 0, 21, 0, "CONDITIONING")
lk_n3 = link(19, 0, 21, 1, "CONDITIONING")
lk_model1 = link(1, 0, 7, 0, "MODEL")
lk_pos1 = link(4, 0, 7, 1, "CONDITIONING")
lk_neg1 = link(21, 0, 7, 2, "CONDITIONING")
lk_lat1 = link(6, 0, 7, 3, "LATENT")
lk_dec1 = link(7, 0, 8, 0, "LATENT")
lk_vae1 = link(1, 2, 8, 1, "VAE")
lk_prev1 = link(8, 0, 9, 0, "IMAGE")
lk_save1 = link(8, 0, 10, 0, "IMAGE")
lk_up_img = link(8, 0, 23, 1, "IMAGE")
lk_up_model = link(22, 0, 23, 0, "UPSCALE_MODEL")
lk_up_out = link(23, 0, 24, 0, "IMAGE")
lk_scale = link(24, 0, 25, 0, "IMAGE")
lk_vae2 = link(1, 2, 25, 1, "VAE")
lk_lat2 = link(25, 0, 12, 3, "LATENT")
lk_model2 = link(1, 0, 12, 0, "MODEL")
lk_pos2 = link(4, 0, 12, 1, "CONDITIONING")
lk_neg2 = link(21, 0, 12, 2, "CONDITIONING")
lk_dec2 = link(12, 0, 13, 0, "LATENT")
lk_vae3 = link(1, 2, 13, 1, "VAE")
lk_prev2 = link(13, 0, 14, 0, "IMAGE")
lk_save2 = link(13, 0, 15, 0, "IMAGE")

wf["links"] = L

# 回填每个节点的 inputs/outputs link 引用
byid = {n["id"]: n for n in wf["nodes"]}
for n in wf["nodes"]:
    for i in n.get("inputs", []):
        i["link"] = None
    for o in n.get("outputs", []):
        o["links"] = []
for lid, fid, fslot, tid, tslot, typ in L:
    src = byid.get(fid)
    if src and fslot < len(src.get("outputs", [])):
        src["outputs"][fslot].setdefault("links", []).append(lid)
    dst = byid.get(tid)
    if dst and tslot < len(dst.get("inputs", [])):
        dst["inputs"][tslot]["link"] = lid

wf["last_node_id"] = max(byid)
wf["last_link_id"] = len(L)
wf["groups"] = []
# 节点按 order 排序，保证前端执行顺序合理
wf["nodes"].sort(key=lambda n: n.get("order", 0))

# ---------- 8) 自检 ----------
errs = []
ids = {n["id"] for n in wf["nodes"]}
for lid, fid, fslot, tid, tslot, typ in L:
    if fid not in ids or tid not in ids:
        errs.append("链接 %d 指向不存在的节点" % lid)
for n in wf["nodes"]:
    for i in n.get("inputs", []):
        if i.get("link") is not None and i["link"] not in [x[0] for x in L]:
            errs.append("节点%d 输入 %s 链接 %s 不存在" % (n["id"], i["name"], i["link"]))
    if n.get("type") == "KSampler" and len(n.get("widgets_values", [])) != 7:
        errs.append("KSampler 节点%d widgets 数量异常" % n["id"])
print("节点数:", len(wf["nodes"]), "链接数:", len(L))
print("自检:", "全部通过" if not errs else errs)
assert not errs, errs

os.makedirs(os.path.dirname(DST), exist_ok=True)
with open(DST, "w", encoding="utf-8") as f:
    json.dump(wf, f, ensure_ascii=False, indent=1)
print("已写出:", DST, os.path.getsize(DST), "B")
print("id 保持:", wf["id"])
print()
print("节点清单:")
for n in wf["nodes"]:
    print("  %-3s %-24s %s" % (n["id"], n["type"], (n.get("title") or "")))
