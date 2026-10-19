# -*- coding: utf-8 -*-
"""Patch the master workflow to generate Wendeng's profiles from the confirmed face."""
import argparse
import copy
import json
import os

from wf_api import build_api, deps


HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_WORKFLOW = os.path.join(HERE, "_wf", "夜市百相簿_主工作流.json")
PROFILE_IMAGE_NAME = "wendeng_face_confirmed_00009.png"
LEFT_PREFIX = "闻灯主图-左侧脸-成品"
RIGHT_PREFIX = "闻灯主图-右侧脸-成品"
FRONT_NORMALIZATION_PREFIX = "闻灯Kontext统一正脸-成品"
FRONT_NORMALIZATION_IDS = {
    "1024", "1025", "1026", "1027", "1028", "1029", "1030",
    "1043", "1044", "1045", "1046", "1047", "1048", "1052",
}

KEEP_IDENTITY = (
    "Use the uploaded reference image as the identity reference for the same person. "
    "Preserve the same recognizable person and facial identity, including: facial proportions, "
    "overall face shape, eye shape and spacing, eyebrows, nose, lips, cheekbones, jawline, "
    "chin, hairline, moles and overall age appearance. Preserve the same natural youthful "
    "complexion and skin tone, but reconstruct the skin naturally rather than copying individual "
    "skin defects or artifacts from the reference. Preserve the same general black wavy "
    "hairstyle and blue shirt. Change only the head direction and camera angle. Do not "
    "redesign, age, beautify, masculinize, feminize or replace the person's face. "
)

LEFT_EDIT = (
    "Turn the same person into a true 90-degree LEFT profile. "
    "Preserve the exact same facial identity, age appearance, facial proportions, nose "
    "structure, lips, chin, jawline, cheekbone structure, hairline and mole placement. "
    "The skin should remain clean, healthy and youthful. Keep a smooth intact skin surface "
    "with only very subtle natural photographic texture. "
    "Keep the complexion clear and even. The face and neck must have a consistent natural "
    "skin tone. "
    "Do not introduce acne, acne scars, pitted skin, enlarged pores, wrinkles, freckles, "
    "age spots, melasma, hyperpigmentation, brown patches, yellow patches, dirty-looking "
    "skin or large areas of uneven pigmentation. "
    "The eyebrows remain soft and naturally sparse, with visible skin between individual "
    "hairs. "
    "Keep only very subtle moustache and chin stubble. Facial hair is short, sparse and low "
    "contrast, never a solid dark patch. "
    "The black wavy hair remains soft, airy and naturally separated into loose locks. Use "
    "soft hair transitions and only a few fine flyaway hairs. Hair must look dry and "
    "natural, never wet, oily, glossy, stiff or gelled. "
    "Keep the same clean youthful photographic appearance, natural skin color, soft "
    "lighting and restrained contrast."
)

RIGHT_EDIT = (
    KEEP_IDENTITY
    + "Create the opposite-facing profile from the left-profile version: his nose points toward the RIGHT edge "
      "of the image and the back of his head is on the LEFT. Show a true 90-degree profile with exactly one "
      "visible eye and one visible ear. His face must look to image-right, never image-left."
)

FRONT_NORMALIZATION_EDIT = (
    "Regenerate the image as a natural high-end photographic portrait while preserving the "
    "exact identity of the reference person. "
    "The person is clearly a 24-year-old young adult East Asian man in his early twenties. "
    "Keep the visual identity of a natural contemporary East Asian man. His overall "
    "appearance should remain naturally Asian and grounded in the reference image, without "
    "introducing strongly Western facial characteristics. "
    "Preserve a youthful adult appearance and youthful facial proportions. He should look "
    "like a healthy 24-year-old Asian man, not a teenager and not a mature man in his "
    "thirties. "
    "Preserve the exact facial identity and recognizable facial structure of the reference. "
    "His skin should look like real young adult male skin, not beauty-retouched skin. Keep "
    "realistic fine skin texture, subtle visible pores, fine natural facial microtexture, "
    "soft peach fuzz, subtle natural skin variation and realistic skin reflectance. The skin "
    "surface should remain healthy and intact without exaggerated pores or roughness. "
    "Do not smooth the skin excessively. Do not create airbrushed skin, plastic skin or "
    "beauty-filter skin. "
    "Keep the complexion clean and healthy without acne, acne scars, pitted scars, wrinkles, "
    "age spots, melasma, hyperpigmentation, brown patches or dirty-looking discoloration. "
    "Keep the eyebrows naturally dense but realistic, with visible individual eyebrow hairs, "
    "fine hair texture, natural hair direction and slightly irregular natural density. "
    "Keep very short natural facial stubble. The moustache and chin stubble should consist "
    "of fine individual hairs with visible separation and visible skin between the hairs. "
    "Keep the facial hair subtle and low contrast, never a solid dark patch. "
    "Keep the black wavy hair soft, airy and naturally voluminous. Preserve naturally "
    "separated waves, soft hair groupings and a limited number of fine flyaway hairs. Hair "
    "should have realistic soft hair texture and natural variation, not look wet, oily, "
    "glossy, stiff, gelled or glued together. "
    "A single small dark mole is clearly visible at the outer corner of his LEFT eye. The "
    "mole is small, round and naturally embedded in the skin. It is a distinctive identity "
    "marker and must remain visible. Do not remove, blur, cover or relocate the mole. "
    "Keep natural photographic color, soft realistic lighting, restrained contrast and "
    "realistic photographic detail. Avoid beauty retouching and excessive sharpening. "
    "Keep the overall appearance naturally East Asian and faithful to the reference. Do not "
    "introduce strongly Western, European, Mediterranean or Middle Eastern facial "
    "characteristics."
)

PROFILE_POSITIONS = {
    1024: [7630, 400], 1025: [7630, 520], 1026: [7630, 680], 1027: [7630, 800],
    1028: [8070, 800], 1029: [8440, 800], 1030: [8760, 800],
    1031: [7630, 1330], 1032: [8370, 1330], 1033: [8370, 1440],
    1034: [8710, 1390], 1035: [9070, 1390], 1036: [9330, 1330],
    1037: [7630, 1970], 1038: [8370, 1970], 1039: [8370, 2080],
    1040: [8710, 2030], 1041: [9070, 2030], 1042: [9330, 1970],
}

FRONT_NORMALIZATION_POSITIONS = {
    1043: [7630, 1050], 1044: [8370, 1050], 1045: [8370, 1160],
    1046: [8710, 1110], 1047: [9070, 1110], 1048: [9410, 1050],
    1049: [9070, 1260], 1050: [9410, 1260],
    1051: [9070, 1980], 1052: [8370, 920],
}

RETIRED_NODES = set(range(1100, 1116)) | {1127} | set(range(1300, 1339))


def _nodes(workflow):
    return {node["id"]: node for node in workflow["nodes"]}


def _disconnect(workflow, target_node_id, target_slot_name):
    """Remove a single input link and keep UI output-link metadata consistent."""
    nodes = _nodes(workflow)
    target = nodes[target_node_id]
    removed = set()
    for slot in target.get("inputs") or []:
        if slot.get("name") == target_slot_name and slot.get("link") is not None:
            removed.add(slot["link"])
            slot["link"] = None
    if not removed:
        return
    workflow["links"] = [link for link in workflow["links"] if link[0] not in removed]
    for node in workflow["nodes"]:
        for output in node.get("outputs") or []:
            output["links"] = [lid for lid in (output.get("links") or []) if lid not in removed]


def _connect(workflow, link_id, source_node_id, target_node_id, target_slot_name, link_type):
    nodes = _nodes(workflow)
    target = nodes[target_node_id]
    source = nodes[source_node_id]
    source_slot = 0
    for output_index, output in enumerate(source.get("outputs") or []):
        if output.get("type") == link_type:
            source_slot = output_index
            break
    for slot in target.get("inputs") or []:
        if slot.get("name") == target_slot_name:
            slot["link"] = link_id
            break
    else:
        raise ValueError("node %d has no input named %s" % (target_node_id, target_slot_name))
    for output_index, output in enumerate(source.get("outputs") or []):
        if output_index == source_slot:
            output.setdefault("links", []).append(link_id)
            break
    workflow["links"].append([link_id, source_node_id, source_slot, target_node_id,
                               next(i for i, s in enumerate(target.get("inputs") or [])
                                    if s.get("name") == target_slot_name), link_type])


def _clone_node(nodes, source_id, target_id):
    node = copy.deepcopy(nodes[source_id])
    node["id"] = target_id
    node["mode"] = 0
    node["inputs"] = [dict(slot, link=None) for slot in (node.get("inputs") or [])]
    node["outputs"] = [dict(output, links=[]) for output in (node.get("outputs") or [])]
    return node


def _new_empty_flux_latent(node_id):
    return {
        "id": node_id, "type": "EmptySD3LatentImage", "pos": [8370, 920],
        "size": [315, 106], "flags": {}, "order": 0, "mode": 0,
        "inputs": [],
        "outputs": [{"name": "LATENT", "type": "LATENT", "links": [], "slot_index": 0}],
        "properties": {"cnr_id": "comfy-core", "ver": "0.30.1",
                       "Node name for S&R": "EmptySD3LatentImage"},
        "widgets_values": [880, 1184, 1],
        "title": "统一三视角 · 纯噪声 latent 880×1184",
    }


def _new_image_flip(node_id):
    return {
        "id": node_id, "type": "ImageFlip", "pos": [9070, 1980],
        "size": [315, 82], "flags": {}, "order": 0, "mode": 0,
        "inputs": [{"name": "image", "type": "IMAGE", "link": None}],
        "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0}],
        "properties": {"cnr_id": "comfy-core", "ver": "0.30.1",
                       "Node name for S&R": "ImageFlip"},
        "widgets_values": ["y-axis: horizontally"],
        "title": "右侧脸 · 水平翻转左侧脸（方向硬保证）",
    }


def _ensure_front_normalization_branch(workflow):
    # A pre-normalization backup may already use ids 1043-1048 for the old
    # left-45 branch. Remove every link touching those ids before repurposing
    # them, otherwise stale left-45 edges survive the patch.
    front_ids = set(FRONT_NORMALIZATION_POSITIONS)
    stale_links = {
        int(link[0]) for link in workflow["links"]
        if int(link[1]) in front_ids or int(link[3]) in front_ids
    }
    workflow["links"] = [link for link in workflow["links"] if int(link[0]) not in stale_links]
    for node in workflow["nodes"]:
        for output in node.get("outputs") or []:
            output["links"] = [lid for lid in (output.get("links") or []) if lid not in stale_links]
        for slot in node.get("inputs") or []:
            if slot.get("link") in stale_links:
                slot["link"] = None

    nodes = _nodes(workflow)
    required = set(FRONT_NORMALIZATION_POSITIONS)
    # Reuse old 1043-1048 nodes when patching a pre-normalization backup;
    # only ids that do not exist yet are cloned from compatible Kontext nodes.
    templates = {
        1043: 1031, 1044: 1032, 1045: 1033, 1046: 1034,
        1047: 1035, 1048: 1036, 1049: 1028, 1050: 1029,
    }
    for node_id in sorted(required - set(nodes)):
        if node_id == 1051:
            workflow["nodes"].append(_new_image_flip(node_id))
        elif node_id == 1052:
            workflow["nodes"].append(_new_empty_flux_latent(node_id))
        else:
            workflow["nodes"].append(_clone_node(nodes, templates[node_id], node_id))
    workflow["last_node_id"] = max(int(workflow.get("last_node_id", 0)), 1052)
    nodes = _nodes(workflow)
    for node_id, position in FRONT_NORMALIZATION_POSITIONS.items():
        nodes[node_id]["pos"] = list(position)
        nodes[node_id]["mode"] = 0

    nodes[1043]["title"] = "统一正脸 · Kontext 编辑指令（只重画质感）"
    nodes[1043]["widgets_values"] = [FRONT_NORMALIZATION_EDIT]
    nodes[1044]["title"] = "统一正脸 · Guidance 3.0"
    nodes[1044]["widgets_values"] = [3.0]
    nodes[1045]["title"] = "统一正脸 · 参考图进 conditioning"
    nodes[1046]["title"] = "统一正脸 · Kontext 完整重绘（d1.0）"
    nodes[1046]["widgets_values"] = [20260920, "fixed", 20, 1.0, "euler", "simple", 1.0]
    nodes[1047]["title"] = "统一正脸 · VAEDecode"
    nodes[1048]["title"] = "统一正脸 · 成品"
    nodes[1048]["widgets_values"] = [FRONT_NORMALIZATION_PREFIX]
    nodes[1049]["title"] = "统一正脸 · Kontext 尺寸"
    nodes[1050]["title"] = "统一正脸 · 成品 latent（供左右侧脸共用）"
    nodes[1051]["title"] = "右侧脸 · 水平翻转左侧脸（方向硬保证）"
    nodes[1051]["widgets_values"] = ["y-axis: horizontally"]
    nodes[1052]["title"] = "统一三视角 · 纯噪声 latent 880×1184"
    nodes[1052]["widgets_values"] = [880, 1184, 1]

    # Rebuild only the new branch links; this is idempotent across repeated patching.
    for target_id, slot_name in ((1044, "conditioning"), (1045, "conditioning"),
                                 (1045, "latent"), (1046, "model"),
                                 (1046, "positive"), (1046, "negative"),
                                 (1046, "latent_image"), (1047, "samples"),
                                 (1047, "vae"), (1048, "images"),
                                 (1049, "image"), (1050, "pixels"),
                                 (1050, "vae"), (1051, "image"),
                                 (1042, "images")):
        _disconnect(workflow, target_id, slot_name)
    next_link = 2301
    for source_id, target_id, slot_name, link_type in (
        (1025, 1043, "clip", "CLIP"),
        (1043, 1044, "conditioning", "CONDITIONING"),
        (1044, 1045, "conditioning", "CONDITIONING"),
        (1029, 1045, "latent", "LATENT"),
        (1024, 1046, "model", "MODEL"),
        (1045, 1046, "positive", "CONDITIONING"),
        (1030, 1046, "negative", "CONDITIONING"),
        (1052, 1046, "latent_image", "LATENT"),
        (1046, 1047, "samples", "LATENT"),
        (1026, 1047, "vae", "VAE"),
        (1047, 1048, "images", "IMAGE"),
        (1047, 1049, "image", "IMAGE"),
        (1049, 1050, "pixels", "IMAGE"),
        (1026, 1050, "vae", "VAE"),
        (1035, 1051, "image", "IMAGE"),
        (1051, 1042, "images", "IMAGE"),
    ):
        _connect(workflow, next_link, source_id, target_id, slot_name, link_type)
        next_link += 1

    # Both profile branches must use the normalized FLUX/Kontext image, not SDXL 00009.
    for target_id, slot_name in ((1033, "latent"), (1034, "latent_image")):
        _disconnect(workflow, target_id, slot_name)
    for target_id, slot_name, link_type in (
        (1033, "latent", "LATENT"),
    ):
        _connect(workflow, next_link, 1050, target_id, slot_name, link_type)
        next_link += 1
    _connect(workflow, next_link, 1052, 1034, "latent_image", "LATENT")
    next_link += 1
    workflow["last_link_id"] = max(int(workflow.get("last_link_id", 0)), next_link - 1)


def patch_workflow(workflow):
    patched = copy.deepcopy(workflow)
    nodes = _nodes(patched)
    required = set(range(1024, 1043))
    missing = sorted(required - set(nodes))
    if missing:
        raise ValueError("workflow is missing required nodes: %s" % missing)

    # The existing Kontext block is the correct identity-editing mechanism.
    for node_id in range(1024, 1043):
        nodes[node_id]["mode"] = 0
        nodes[node_id]["pos"] = list(PROFILE_POSITIONS[node_id])

    _ensure_front_normalization_branch(patched)
    nodes = _nodes(patched)

    nodes[1027]["widgets_values"] = [PROFILE_IMAGE_NAME, "image"]
    nodes[1027]["title"] = "★ 唯一身份基准 = 闻灯正脸成品 00009"
    nodes[1031]["widgets_values"] = [LEFT_EDIT]
    nodes[1031]["title"] = "主图编辑指令 · 鼻尖朝画面左（仅生成一侧）"
    nodes[1034]["widgets_values"] = [20260920, "fixed", 20, 1.0, "euler", "simple", 1.0]
    nodes[1034]["title"] = "★ 鼻尖朝画面左：Kontext 完整重绘（d1.0）"
    nodes[1036]["widgets_values"] = [LEFT_PREFIX]
    nodes[1036]["title"] = "主图 · 左侧脸 90° · 成品"
    nodes[1037]["widgets_values"] = [RIGHT_EDIT]
    nodes[1037]["title"] = "主图编辑指令 · 右侧脸 90°（仅转头，不换人）"
    nodes[1042]["widgets_values"] = [RIGHT_PREFIX]
    nodes[1042]["title"] = "主图 · 右侧脸成品（由左侧脸水平翻转）"
    for node_id in range(1037, 1042):
        nodes[node_id]["mode"] = 2
    if 1023 in nodes and nodes[1023].get("type") == "Note":
        nodes[1023]["title"] = "★ 说明 · Kontext 统一正脸后再生成左右侧脸"
        nodes[1023]["widgets_values"] = [
            "【闻灯 · Kontext 三视角统一质感】\n\n"
            "① 1027 = SDXL 确认图 00009，只作为身份参考。\n"
            "② 1043-1048 以 denoise 1.0 + 纯噪声 latent 完整重画 FLUX/Kontext 正脸质感。\n"
            "③ 1050 的统一正脸 latent 作为身份参考，1034 以 denoise 1.0 生成鼻尖朝画面左的侧脸。\n"
            "④ 1051 水平翻转这张侧脸得到反方向，方向由像素变换硬保证，不再赌 LEFT/RIGHT 提示词。\n\n"
            "最终视频参考图必须使用：闻灯Kontext统一正脸-成品 + 闻灯主图-左侧脸-成品 + 闻灯主图-右侧脸-成品。\n"
            "跑图：python _scripts\\run_wf.py \"夜市百相簿-主工作流.json\" \"闻灯Kontext统一正脸,闻灯主图-左侧脸,闻灯主图-右侧脸\" final"
        ]

    # Remove the plain FLUX img2img block and the unused left-45 branch, including all port references.
    dead_links = {
        link[0] for link in patched["links"]
        if link[1] in RETIRED_NODES or link[3] in RETIRED_NODES
    }
    patched["nodes"] = [node for node in patched["nodes"] if node["id"] not in RETIRED_NODES]
    patched["links"] = [link for link in patched["links"] if link[0] not in dead_links]
    for node in patched["nodes"]:
        for output in node.get("outputs") or []:
            output["links"] = [link for link in (output.get("links") or []) if link not in dead_links]
        for node_input in node.get("inputs") or []:
            if node_input.get("link") in dead_links:
                node_input["link"] = None

    profile_group = None
    groups = []
    for group in patched.get("groups", []):
        title = group.get("title", "")
        if "旧版 FLUX img2img" in title or ("Flux 文生图 · 一体化 fp8" in title and "Kontext" not in title):
            continue
        if "Flux Kontext" in title or "主图左右侧脸" in title or ("00009" in title and "Kontext" in title):
            profile_group = group
        groups.append(group)
    if profile_group is None:
        raise ValueError("workflow is missing the Kontext group")
    profile_group["title"] = "【闻灯】Flux 文生图 · 一体化 fp8（00009 → Kontext 左/右侧脸）"
    profile_group["bounding"] = [7600, 250, 2500, 3300]
    profile_group["color"] = "#2F6F58"
    patched["groups"] = groups

    validate_workflow(patched)
    return patched


def validate_workflow(workflow):
    nodes = _nodes(workflow)
    if nodes[1027].get("widgets_values", [None])[0] != PROFILE_IMAGE_NAME:
        raise ValueError("node 1027 does not use the confirmed face")
    if nodes[1036].get("widgets_values", [None])[0] != LEFT_PREFIX:
        raise ValueError("left profile output prefix is incorrect")
    if nodes[1042].get("widgets_values", [None])[0] != RIGHT_PREFIX:
        raise ValueError("right profile output prefix is incorrect")
    for node_id in FRONT_NORMALIZATION_POSITIONS:
        if node_id not in nodes or nodes[node_id].get("mode") != 0:
            raise ValueError("front normalization node %d is missing or disabled" % node_id)
    if nodes[1048].get("widgets_values", [None])[0] != FRONT_NORMALIZATION_PREFIX:
        raise ValueError("front normalization output prefix is incorrect")

    for node_id in list(range(1024, 1037)) + [1042]:
        if nodes[node_id].get("mode") != 0:
            raise ValueError("required Kontext node %d is disabled" % node_id)
    retired = sorted(RETIRED_NODES & set(nodes))
    if retired:
        raise ValueError("retired FLUX/left-45 nodes remain: %s" % retired)

    api, _ = build_api(workflow)
    for node_id in ("1030", "1031", "1037", "1043"):
        if api.get(node_id, {}).get("inputs", {}).get("clip") != ["1025", 0]:
            raise ValueError("CLIPTextEncode node %s is missing the shared DualCLIP connection" % node_id)
    expected = {
        "1048": FRONT_NORMALIZATION_IDS,
        "1036": {"1024", "1025", "1026", "1027", "1028", "1029", "1030", "1043", "1044", "1045", "1046", "1047", "1049", "1050", "1033", "1034", "1035"},
        "1042": {"1024", "1025", "1026", "1027", "1028", "1029", "1030", "1035", "1043", "1044", "1045", "1046", "1047", "1049", "1050", "1051", "1052"},
    }
    for output_id, required in expected.items():
        branch = deps(api, [output_id])
        missing = sorted(required - branch)
        if missing:
            raise ValueError("output %s has an incomplete dependency chain: %s" % (output_id, missing))
        if api["1027"]["inputs"].get("image") != PROFILE_IMAGE_NAME:
            raise ValueError("API conversion lost the confirmed image reference")
    if api["1033"]["inputs"]["latent"][0] != "1050":
        raise ValueError("left profile ReferenceLatent does not use normalized front latent")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?", default=DEFAULT_WORKFLOW)
    parser.add_argument("--output")
    args = parser.parse_args()
    output = args.output or args.input

    with open(args.input, encoding="utf-8") as handle:
        workflow = json.load(handle)
    patched = patch_workflow(workflow)
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(patched, handle, ensure_ascii=False, indent=1)
    print("OK: patched and validated %s" % output)


if __name__ == "__main__":
    main()
