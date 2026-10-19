# -*- coding: utf-8 -*-
"""工作流 UI-JSON → API 格式转换 + 依赖裁剪（run_wf.py 与 verify_master.py 共用）

★ 为什么要抽出来
    合并成主工作流后，工作流里出现了原来没有的节点类型。而 run_wf.py 的转换表是
    白名单式的 —— **遇到不认识的类型会静默跳过该节点**，结果是提交上去缺节点、
    或者干脆跑不起来，而且报错指向很含糊。
    实测缺过：EmptyLatentImage / CLIPSetLastLayer / ConditioningCombine（基线要用）、
    UNETLoader / DualCLIPLoader / VAELoader / FluxKontextImageScale / ReferenceLatent（Kontext 要用）。

★ widgets_values 的顺序约定
    ComfyUI 前端保存的 widgets_values 按节点的 widget 顺序排列，
    其中有些是**纯前端 widget**（不在后端 inputs 里），例如 KSampler 的
    control_after_generate。所以 KSampler 的 7 个值要收缩成 6 个。
"""

WIDGETS = {
    # ── 原本就有 ──
    "CheckpointLoaderSimple": ["ckpt_name"],
    "LoadImage": ["image", "upload"],
    "ImageScale": ["upscale_method", "width", "height", "crop"],
    "VAEEncode": [],
    "UpscaleModelLoader": ["model_name"],
    "CLIPTextEncode": ["text"],
    "FluxGuidance": ["guidance"],
    "KSampler": ["seed", "steps", "cfg", "sampler_name", "scheduler", "denoise"],
    "VAEDecode": [],
    "SaveImage": ["filename_prefix"],
    "ImageUpscaleWithModel": [],
    "ImageScaleBy": ["upscale_method", "scale_by"],
    # ── 2026-09-18 合并主工作流时补全 ──
    "EmptyLatentImage": ["width", "height", "batch_size"],
    # Flux / SD3 用的 16 通道空 latent（4 通道的 EmptyLatentImage 喂给 Flux 会报维度错）
    "EmptySD3LatentImage": ["width", "height", "batch_size"],
    "CLIPSetLastLayer": ["stop_at_clip_layer"],
    "ConditioningCombine": [],
    "ConditioningConcat": [],          # 2026-09-20 身份锁：身份段 + 表现段 拼接
    "ConditioningZeroOut": [],
    "PreviewImage": [],
    "VAELoader": ["vae_name"],
    "UNETLoader": ["unet_name", "weight_dtype"],
    "DualCLIPLoader": ["clip_name1", "clip_name2", "type"],
    "FluxKontextImageScale": [],
    "ReferenceLatent": [],
    # ── 2026-09-24 侧脸质感修复：给侧脸支路单独挂细节 LoRA ──
    "LoraLoaderModelOnly": ["lora_name", "strength_model"],
    "LatentUpscale": ["upscale_method", "width", "height", "crop"],
    "ImageBlur": ["blur_radius", "sigma"],
    "ImageInvert": [],
    "ImageFlip": ["flip_method"],
    "ImageCompositeMasked": ["x", "y", "resize_source"],
    # ── 2026-10-08 全身脸部精修（资产C）：从全身母版裁出脸部区域 ──
    "ImageCrop": ["width", "height", "x", "y"],
    # A 路：把已确认脸摆进全身画布（向下留空）→ SDXL img2img，身份靠输入像素传递
    "ImagePadForOutpaint": ["left", "top", "right", "bottom", "feathering"],
    "SetLatentNoiseMask": [],
    # ── 2026-09-18 全身改造（livdan_to_fullbody.py）插入的新类型 ──
    # ⚠️ 忘了登记就会被 to_api 静默跳过 → 提交时缺节点，报错指向很含糊。
    "LoadImageOutput": ["image"],
    "SolidMask": ["value", "width", "height"],
    "FeatherMask": ["left", "top", "right", "bottom"],
    "MaskFromColor": ["color", "threshold"],
    "ImageQuantize": ["colors", "dither"],
    "Note": None,
}

# 纯前端 widget：不在后端 inputs 里，但占 widgets_values 的位置
FRONT_ONLY = {"KSampler": {1}}          # index 1 = control_after_generate


def to_api(n, links):
    """UI 节点 → API 节点 dict；返回 None 表示该类型不支持（会被跳过）"""
    # ★ 2026-09-24：API 格式里没有 mode 字段，所以「前端禁用(mode=2)」的节点
    #   以前会被照样塞进提交内容并真的执行（踩过：三个中间存图节点禁用了却还在落盘）。
    #   这里显式跳过，让「禁用」在 API 路径上也有意义。
    if n.get("mode") == 2:
        return None
    names = WIDGETS.get(n["type"], None)
    if names is None:
        return None
    wv = list(n.get("widgets_values") or [])
    drop = FRONT_ONLY.get(n["type"], set())
    if drop:
        wv = [v for i, v in enumerate(wv) if i not in drop]

    ins = {}
    for k, v in zip(names, wv):
        ins[k] = v

    # 真实连线覆盖 widget 默认值
    for slot in n.get("inputs", []):
        lid = slot.get("link")
        if lid is None:
            continue
        l = links.get(lid)
        if not l:
            continue
        ins[slot["name"]] = [str(l[1]), l[2]]

    return {"class_type": n["type"], "inputs": ins,
            "_meta": {"title": n.get("title") or n["type"]}}


def build_api(wf):
    """整份 UI 工作流 → (API dict, titles dict)"""
    links = {l[0]: l for l in wf["links"]}
    api, titles = {}, {}
    for n in wf["nodes"]:
        a = to_api(n, links)
        if a:
            api[str(n["id"])] = a
            titles[str(n["id"])] = n.get("title") or n["type"]
    return api, titles


def deps(api, roots):
    """从输出节点回溯出全部依赖节点 id"""
    seen, stack = set(), list(roots)
    while stack:
        nid = stack.pop()
        if nid in seen or nid not in api:
            continue
        seen.add(nid)
        for v in api[nid]["inputs"].values():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str):
                stack.append(v[0])
    return seen


def find_outputs(api, tokens, suffix=None):
    """按 filename_prefix 关键词找 SaveImage 节点 id"""
    hits = []
    for nid, a in api.items():
        if a["class_type"] != "SaveImage":
            continue
        pfx = str(a["inputs"].get("filename_prefix", ""))
        if all(t in pfx for t in (tokens if isinstance(tokens, (list, tuple)) else [tokens])):
            if suffix is None or pfx.endswith(suffix):
                hits.append((nid, pfx))
    return hits
