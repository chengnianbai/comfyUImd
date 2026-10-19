# -*- coding: utf-8 -*-
"""导出【闻灯】脸部组（SDXL img2img 保身份）的全部节点参数与连线。
   用法：python show_face_block.py [工作流json路径]
"""
import json, os, sys

root = os.path.dirname(os.path.abspath(__file__))
wf_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, "_wf", "夜市百相簿_主工作流.json")
d = json.load(open(wf_path, encoding="utf-8"))

groups = d.get("groups", [])
g = None
for x in groups:
    if "脸部" in x.get("title", ""):
        g = x
        break
if g is None:
    print("找不到脸部组，现有分组：")
    for x in groups:
        print("   ", x.get("title"))
    sys.exit(1)

x0, y0, w, h = g["bounding"]
print("=" * 78)
print("分组：%s" % g["title"])
print("位置 x=%d y=%d 尺寸 %dx%d" % (x0, y0, w, h))
print("=" * 78)


def inbox(n):
    px, py = n["pos"]
    return x0 - 60 <= px <= x0 + w + 60 and y0 - 100 <= py <= y0 + h + 100


ns = [n for n in d["nodes"] if inbox(n)]
ids = {n["id"] for n in ns}
print("组内节点 %d 个\n" % len(ns))

# ---- 依赖图：谁给谁供数据 ----
links = [l for l in d["links"] if l[3] in ids]
src_names = {n["id"]: "%s#%s" % (n["type"], n["id"]) for n in d["nodes"]}
src_types = {n["id"]: n["type"] for n in d["nodes"]}
link_map = {l[0]: (l[1], src_types.get(l[1], "?")) for l in d["links"]}

print("── 连线（含从组外来的输入） ──")
for l in sorted(links, key=lambda a: (a[3], a[4])):
    outer = "" if l[1] in ids else "   ← 组外"
    print("   %-22s .%-14s → #%-3s .%s%s" % (
        src_names.get(l[1], "?#%s" % l[1]), l[2], l[3], l[4], outer))

print()
print("── 节点明细（按 id） ──")
KEY_TYPES = {
    "CLIPTextEncode", "KSampler", "KSamplerAdvanced", "EmptyLatentImage", "LoadImage",
    "ImageScale", "ImageScaleBy", "VAEEncode", "VAEDecode", "UNETLoader",
    "CheckpointLoaderSimple", "CLIPSetLastLayer", "UpscaleModelLoader",
    "ImageUpscaleWithModel", "ConditioningCombine", "SaveImage", "PreviewImage",
    "LatentUpscale", "LoraLoader", "Note", "LoadImageOutput", "ImageCompositeMasked",
    "SolidMask", "FeatherMask",
}
for n in sorted(ns, key=lambda a: a["id"]):
    t = n["type"]
    if t == "Note":
        continue
    wv = n.get("widgets_values")
    mode = n.get("mode", 0)
    flag = " [BYPASS]" if mode == 4 else (" [静音]" if mode == 2 else "")
    print()
    print("#%-4s %-24s%s" % (n["id"], t, flag))
    if n.get("title"):
        print("      标题: %s" % n["title"])
    if t in ("CLIPTextEncode",) and wv:
        txt = wv[0]
        print("      提示词全文（%d 字符）：" % len(txt))
        for line in str(txt).split("\n"):
            print("         %s" % line)
    elif wv is not None:
        s = json.dumps(wv, ensure_ascii=False)
        print("      参数: %s" % s)
    ins = n.get("inputs") or []
    if ins:
        conn = []
        for i in ins:
            lk = i.get("link")
            if lk is None:
                continue
            src = link_map.get(lk)
            if src:
                conn.append("%s ← #%s(%s)" % (i.get("name"), src[0], src[1]))
            else:
                conn.append("%s ← link%s" % (i.get("name"), lk))
        if conn:
            print("      输入: %s" % ", ".join(conn))
