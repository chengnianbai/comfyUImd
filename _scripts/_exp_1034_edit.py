# -*- coding: utf-8 -*-
"""
1034 结构改造实验：让 Kontext 真正基于正脸成品做角度编辑（而非纯噪声重画）。
用法（COMFY_BASE 必须已设置）:
    python _exp_1034_edit.py d0.6      # latent_image: 1052->1050, denoise=0.6
    python _exp_1034_edit.py d0.75     # 同上, denoise=0.75
    python _exp_1034_edit.py restore   # 恢复: latent_image<-1052, denoise=1.0
铁律：拉线上->备份->只改目标字段->推回->回读全量 diff（仅允许 1034/1050/1052 与该条链接变化）。
不碰 1031/1043 提示词，不碰 1033 锚线，不碰其他任何节点。
"""
import json, sys, time, copy

sys.path.insert(0, r"D:\xiaobai-claude code\comfyUImd\_scripts")
from deploy_wendeng_profiles import request, workflow_path, WORKFLOW_NAME

TARGET = 1034          # 左脸 KSampler
NOISE = 1052           # EmptySD3LatentImage（现状来源）
FRONT_LATENT = 1050    # 正脸成品 -> 1049 缩放 -> 1050 VAEEncode（新来源）


def main():
    if len(sys.argv) != 2:
        print(__doc__); sys.exit(2)
    cmd = sys.argv[1].lower()

    get = workflow_path(WORKFLOW_NAME).split("?", 1)[0]
    before = json.loads(request(get, timeout=120).decode("utf-8", "replace"))
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = r"D:\xiaobai-claude code\comfyUImd\_scripts\_wf\_backup_pre_1034edit_%s.json" % ts
    json.dump(before, open(bak, "w", encoding="utf-8"), ensure_ascii=False)
    print("backup:", bak)

    nb = {n["id"]: n for n in before["nodes"]}
    p43, p31 = nb[1043]["widgets_values"][0], nb[1031]["widgets_values"][0]
    p1033_src = next(l for l in before["links"] if l[0] == next(
        i["link"] for i in nb[1033]["inputs"] if i["name"] == "latent"))[1]

    wf = copy.deepcopy(before)
    n = {x["id"]: x for x in wf["nodes"]}

    if cmd == "restore":
        new_src, new_dn = NOISE, 1.0
    else:
        if not cmd.startswith("d"):
            print(__doc__); sys.exit(2)
        new_src, new_dn = FRONT_LATENT, float(cmd[1:])

    # --- 改 latent_image 连线 ---
    inp = next(i for i in n[TARGET]["inputs"] if i["name"] == "latent_image")
    lid = inp["link"]
    assert lid is not None, "1034.latent_image 无连线"
    entry = next(l for l in wf["links"] if l[0] == lid)
    old_src = entry[1]
    print("latent_image 链接 %d: %d -> %d" % (lid, old_src, new_src))
    if old_src != new_src:
        entry[1] = new_src
        entry[2] = 0
        for out in n[old_src].get("outputs", []):
            if out.get("links") and lid in out["links"]:
                out["links"].remove(lid)
        out_new = n[new_src]["outputs"][0]
        out_new.setdefault("links", [])
        if lid not in out_new["links"]:
            out_new["links"].append(lid)

    # --- 改 denoise（widgets 最后一项）---
    w = n[TARGET]["widgets_values"]
    old_dn = w[-1]
    w[-1] = new_dn
    print("denoise: %s -> %s" % (old_dn, new_dn))

    request(workflow_path(WORKFLOW_NAME), json.dumps(wf, ensure_ascii=False).encode("utf-8"),
            "application/json", timeout=600, method="POST")

    # --- 回读 + 全量 diff ---
    after = json.loads(request(get, timeout=120).decode("utf-8", "replace"))
    na = {x["id"]: x for x in after["nodes"]}

    a = next(i for i in na[TARGET]["inputs"] if i["name"] == "latent_image")
    src_after = next(l for l in after["links"] if l[0] == a["link"])[1]
    assert src_after == new_src, "连线未生效: %s" % src_after
    assert na[TARGET]["widgets_values"][-1] == new_dn, "denoise 未生效"

    # 只允许这些节点/链接有差异
    changed_nodes = sorted(x["id"] for x in after["nodes"]
                           if json.dumps(x, sort_keys=True) != json.dumps(
                               next(y for y in before["nodes"] if y["id"] == x["id"]), sort_keys=True))
    bmap = {l[0]: l for l in before["links"]}
    changed_links = sorted(l[0] for l in after["links"] if bmap.get(l[0]) != l)
    allowed_nodes = {TARGET}
    if old_src != new_src:
        allowed_nodes |= {old_src, new_src}
    print("diff 节点:", changed_nodes, " diff 链接:", changed_links)
    assert set(changed_nodes) <= allowed_nodes, "意外节点变化: %s" % changed_nodes
    assert changed_links == ([lid] if old_src != new_src else []), "意外链接变化: %s" % changed_links

    # 提示词与锚线必须原样
    assert na[1043]["widgets_values"][0] == p43, "1043 提示词被改动!"
    assert na[1031]["widgets_values"][0] == p31, "1031 提示词被改动!"
    p1033_after = next(l for l in after["links"] if l[0] == next(
        i["link"] for i in na[1033]["inputs"] if i["name"] == "latent"))[1]
    assert p1033_after == p1033_src, "1033 锚线被改动! %s -> %s" % (p1033_src, p1033_after)

    print("READBACK OK: 仅 1034.%s/denoise=%s 生效，提示词与锚线逐字节保留" % (
        "latent_image" if old_src != new_src else "denoise", new_dn))


if __name__ == "__main__":
    main()
