# -*- coding: utf-8 -*-
"""把基线「立绘（脸部特写）」块**就地改造成「全身正面」块**。

依据 `角色生成约束-V1.0.md`：
  §4.1 全身（本题先做正面；侧/背待正面验证通过后再加，遵守「一轮只留一个变量」）
  §5   标准站姿（Neutral Standing Pose / Arms Naturally at Sides）
  §6   7～8 头身自然比例
  §7   全身完整入镜（Full Body Shot / Head to Toe / Centered Composition）
  §8.1 男性：上半身裸露 + 纯白短裤（Bare Upper Body / Plain White Shorts）
  §10 / H09   **必须使用已确认的脸部图作为身份参考**
  §12 纯白背景    §13 柔和棚光    §17 禁止词

★ 身份怎么锁 —— 本模块唯一"新"的技术点
    plain img2img 从「脸部特写」出发，**无论 denoise 调多高都不会自己拉远成全身**：
    构图由**基图**决定，不由提示词决定（把脸缩进更高的画布只是把脸拉长，头部仍占满整幅）。
    所以走三步：
      ① 第一段纯文生图出**全身构图** 832×1216 → 草稿（此时脸是随机的）；
      ② 用 `LoadImageOutput` 直读**脸部组已产出的成品**，缩到头部大小，
         贴到草稿头顶 → `ImageCompositeMasked`（`FeatherMask` 羽化边缘，白底对白底无缝）；
      ③ 再走原来那条「4x 放大 → 缩回 0.5 → 二段 denoise 0.25」融合 + 补细节 → 成品。
    这恰好就是 §10 的原话：**「全身图不是重新生成一个角色，而是把已经确认的脸放到完整身体上。」**

★ 幂等
    认出 SaveImage 前缀已经是「闻灯-全身正面」就直接返回，重跑不会二次插入。

★ 唯一需要标定的旋钮
    贴脸尺寸 `FACE_W × FACE_H` 与落点 `FACE_X / FACE_Y`（默认按 832×1216、7.5 头身算）。
    第一张草稿出来后如果头偏大/偏小，只动这 4 个数即可。
"""

FACE_OUT = "闻灯-脸部正面-成品_00001_.png"      # 脸部组 SaveImage 的产物，从 output/ 直读
MARK_PREFIX = "闻灯-全身正面"                   # 幂等标记 = 新 SaveImage 前缀

# —— 贴脸标定（832×1216 画布 / 约 7.5 头身 / 头部高≈162px）——
FACE_W, FACE_H = 200, 257
FACE_X, FACE_Y = (832 - FACE_W) // 2, 6

NEW_IDS = {"load": 30, "scale": 31, "solid": 32, "feather": 33, "comp": 34}

POS_A_FULL = ("full body shot, head to toe, full length, standing straight, arms naturally at sides, "
              "centered composition, 1boy, solo, 24 year old east asian man, masculine face, strong jaw, "
              "messy wavy black hair, small mole at outer eye corner, bare upper body, plain white shorts, "
              "pure white background")

POS_B_FULL = ("natural human anatomy, realistic human proportions, 7 to 8 head proportion, "
              "correct shoulder width, correct hip width, symmetrical body, visible skin pores, "
              "skin texture, peach fuzz, messy wavy hair, pure white background, soft even lighting, "
              "sharp focus, photorealistic")

# N2：★ 必须删掉 bare chest / shirtless / nude —— 全身要的正是"上半身裸露"
NEG_2_FULL = ("t-shirt, sweater, business suit, blazer, tie, dress shirt, formal wear, ironed shirt, "
              "wool coat, brown coat, beige coat, blue coat, light coat, new clothes, fashion model, "
              "jeans, denim, white sneakers, new shoes, police uniform, wuxia, hanfu")

# N3：★ 必须删掉 full body / bare shoulders / shirtless（现在是目标而非禁忌），
#     并按附录 B.2 删掉 smooth skin（负向里不放皮肤词，会把皮肤压成蜡像）；
#     再按 §17 补全身专属禁止词。
NEG_3_FULL = ("dark background, grey background, gradient background, vignette, shadow, busy background, "
              "freckles, mole on cheek, mole on forehead, extra fingers, bad hands, watermark, text, "
              "blurry, lowres, airbrushed, over-smoothed, beauty filter, retouched, "
              "dynamic pose, sitting, walking, running, hands on hips, arms crossed, hands in pockets, "
              "twisted torso, exaggerated anatomy, long limbs, short legs, oversized head, "
              "distorted hands, deformed feet, cropped feet, cropped head, fisheye, "
              "wide angle distortion, complex background, props, accessories")

NOTE_FULL = """【闻灯 · 全身立绘 · SDXL 保身份（正面）】

★ 本块 = 原「立绘」块原址改造（约束 §4.1 / §5 / §6 / §7 / §8.1 / §10 / §12 / §13 / §17）

★ 为什么是「先出全身、再把脸贴回去」，而不是直接拿脸当 img2img 基图：
    plain img2img 的**构图由基图决定**。把一张脸部特写缩进 832×1216 的画布，
    头部照样占满整幅 → 无论 denoise 调到多高都拉不遠。
    所以：① 纯文生图先拿到**构图正确的全身**（脸随机）；
          ② 把**已确认的脸**（本工作流「脸部」块产出的成品）缩到头部、贴到头顶；
          ③ 二段 denoise 0.25 融合 + 补细节。
    这正是 §10 的原话：「全身图不是重新生成一个角色，而是把已经确认的脸放到完整身体上」。

★ 依赖（硬性）：必须先跑「脸部」块并**人工确认**那张脸。
    本块用 LoadImageOutput 直读 output/ 下的 __FACE__
    文件不存在时本组无法提交（这是故意的 —— 对应 §3.1「脸部未确认禁止进入全身」）。

★ 唯一需要标定的旋钮：贴脸尺寸与落点
    ImageScale = __FW__×__FH__；ImageCompositeMasked x=__FX__ y=__FY__
    第一张草稿出来后若头偏大/偏小，只动这几个数。

★ 跑法（不要在浏览器点大「运行」）
    python _scripts\\run_wf.py "夜市百相簿-主工作流.json" "闻灯-全身正面" draft    # 先只跑草稿
    python _scripts\\run_wf.py "夜市百相簿-主工作流.json" "闻灯-全身正面" final    # 确认构图后再跑成品
"""


def _by_id(nodes, nid):
    for n in nodes:
        if n["id"] == nid:
            return n
    return None


def _inp(node, name):
    for s in node.get("inputs", []):
        if s["name"] == name:
            return s
    return None


def _out(node, idx):
    outs = node.get("outputs", [])
    return outs[idx] if idx < len(outs) else None


def _mknode(nid, ntype, pos, size, widgets, inputs, outputs, order, title):
    n = {"id": nid, "type": ntype, "pos": list(pos), "size": list(size), "flags": {},
         "order": order, "mode": 0,
         "inputs": [{"name": a, "type": b, "link": None} for a, b in inputs],
         "outputs": [{"name": a, "type": b, "slot_index": i, "links": []}
                     for i, (a, b) in enumerate(outputs)],
         "properties": {"Node name for S&R": ntype}}
    if widgets is not None:
        n["widgets_values"] = widgets
    if title:
        n["title"] = title
    return n


def _add_link(nodes, links, lid, fid, fslot, tid, tslot, typ):
    links.append([lid, fid, fslot, tid, tslot, typ])
    s = _by_id(nodes, fid)
    if s is not None:
        o = _out(s, fslot)
        if o is not None:
            o.setdefault("links", []).append(lid)
    d = _by_id(nodes, tid)
    if d is not None:
        for i, s_ in enumerate(d.get("inputs", [])):
            if s_["name"] == tslot:
                s_["link"] = lid
                break


def convert(nodes, links):
    """就地改造，返回 (nodes, links, changed)。幂等。"""
    if any(n["type"] == "SaveImage"
           and str((n.get("widgets_values") or [""])[0]).startswith(MARK_PREFIX)
           for n in nodes):
        return nodes, links, False

    # ── ① 提示词与参数 ─────────────────────────────────────────────
    text = {
        2: (POS_A_FULL, "正向 A · 构图 + 人物 + 服装（全身正面）"),
        3: (POS_B_FULL, "正向 B · 人体比例 + 白底 + 光位 + 质感"),
        18: (NEG_2_FULL, "负向 N2 服饰/正装（已剔除 bare chest/shirtless）"),
        19: (NEG_3_FULL, "负向 N3 背景/构图/姿态（全身版 · 已并入 §17）"),
    }
    for nid, (txt, title) in text.items():
        n = _by_id(nodes, nid)
        if n is None or n["type"] != "CLIPTextEncode":
            raise RuntimeError("基线里找不到 CLIPTextEncode id=%s，结构与预期不符" % nid)
        n["widgets_values"] = [txt]
        n["title"] = title

    n = _by_id(nodes, 6)
    if n is None or n["type"] != "EmptyLatentImage":
        raise RuntimeError("基线里找不到 EmptyLatentImage id=6")
    n["widgets_values"] = [832, 1216, 1]
    n["title"] = "画布 832×1216（全身竖构图 · 约 7.5 头身）"

    for nid, pfx in ((10, MARK_PREFIX + "-草稿"), (15, MARK_PREFIX + "-成品")):
        n = _by_id(nodes, nid)
        if n is None or n["type"] != "SaveImage":
            raise RuntimeError("基线里找不到 SaveImage id=%s" % nid)
        n["widgets_values"] = [pfx] + list(n["widgets_values"][1:])

    n = _by_id(nodes, 12)
    if n is not None and n["type"] == "KSampler":
        n["title"] = "KSampler 第2段 · 20步 CFG10 denoise0.25（融合贴脸 + 补细节）"

    n = _by_id(nodes, 16)
    if n is not None and n["type"] == "Note":
        n["widgets_values"] = [(NOTE_FULL
                                .replace("__FACE__", FACE_OUT)
                                .replace("__FW__", str(FACE_W)).replace("__FH__", str(FACE_H))
                                .replace("__FX__", str(FACE_X)).replace("__FY__", str(FACE_Y)))]

    # ── ② 插入「贴脸」链：草稿VAEDecode(8) → 合成(34) → 放大入口(23:1) ──
    ID_DEC, ID_UP, P = 8, 23, NEW_IDS
    target = None
    for l in links:
        if l[1] == ID_DEC and l[2] == 0 and l[3] == ID_UP and l[4] == 1:
            target = l
            break
    if target is None:
        raise RuntimeError("找不到 草稿VAEDecode(8):0 → ImageUpscaleWithModel(23):1 的连线")

    up = _by_id(nodes, ID_UP)
    _inp(up, "image")["link"] = None
    target[3], target[4] = P["comp"], 0          # 原连线终点改到合成的 destination

    node = _mknode(P["load"], "LoadImageOutput", (300, 2100), (400, 400), [FACE_OUT], [],
                   [("IMAGE", "IMAGE"), ("MASK", "MASK")], 90,
                   "★ 已确认的脸 · 脸部组成品（output/ 直读）")
    nodes.append(node)
    nodes.append(_mknode(P["scale"], "ImageScale", (750, 2100), (330, 100),
                         ["lanczos", FACE_W, FACE_H, "center"],
                         [("image", "IMAGE")], [("IMAGE", "IMAGE")], 91,
                         "★ 脸缩到头部大小 %d×%d（唯一标定旋钮）" % (FACE_W, FACE_H)))
    nodes.append(_mknode(P["solid"], "SolidMask", (750, 2230), (330, 80),
                         [1.0, FACE_W, FACE_H], [], [("MASK", "MASK")], 92,
                         "贴图区域掩膜 %d×%d" % (FACE_W, FACE_H)))
    nodes.append(_mknode(P["feather"], "FeatherMask", (750, 2340), (330, 80),
                         [16, 16, 16, 28], [("mask", "MASK")], [("MASK", "MASK")], 93,
                         "羽化边缘（白底对白底，融掉接缝）"))
    nodes.append(_mknode(P["comp"], "ImageCompositeMasked", (1130, 2100), (400, 130),
                         [FACE_X, FACE_Y, True],
                         [("destination", "IMAGE"), ("source", "IMAGE"), ("mask", "MASK")],
                         [("IMAGE", "IMAGE")], 94,
                         "★ 把脸贴到全身草稿的头顶 x=%d y=%d" % (FACE_X, FACE_Y)))

    nxt = max([l[0] for l in links] + [0]) + 1
    _add_link(nodes, links, nxt, P["load"], 0, P["scale"], "image", "IMAGE")
    _add_link(nodes, links, nxt + 1, P["scale"], 0, P["comp"], "source", "IMAGE")
    _add_link(nodes, links, nxt + 2, P["solid"], 0, P["feather"], "mask", "MASK")
    _add_link(nodes, links, nxt + 3, P["feather"], 0, P["comp"], "mask", "MASK")
    _add_link(nodes, links, nxt + 4, P["comp"], 0, ID_UP, "image", "IMAGE")

    # ★ 回填被改道的那条线到新节点上：原 link 现在终点是合成的 destination。
    #   （上面只改了 links 里的终点，节点输入口的 link 字段还得补 —— 少了这步，
    #     自检会报「节点 34 输入 destination 未连接」。）
    _inp(_by_id(nodes, P["comp"]), "destination")["link"] = target[0]
    return nodes, links, True
