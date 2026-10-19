import os, sys, json, io
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
P = r"D:\xiaobai-claude code\comfyUImd\系列-夜市百相簿\02-角色\角色生成.json"
print("文件", os.path.basename(P), os.path.getsize(P), "字节")
wf = json.loads(io.open(P, encoding="utf-8").read())
by = {n["id"]: n for n in wf["nodes"]}
L = {l[0]: l for l in wf["links"]}
print("nodes=%d links=%d groups=%d" % (len(wf["nodes"]), len(wf["links"]), len(wf.get("groups", []))))
for g in wf.get("groups", []):
    print("  组 id=%s %r" % (g["id"], g["title"]))
print("\n=== 节点总览 ===")
for n in sorted(wf["nodes"], key=lambda z: z["id"]):
    if n["type"] == "Note":
        continue
    wv = json.dumps(n.get("widgets_values") or [], ensure_ascii=False)
    print("  #%-5s %-24s mode=%s  %s" % (n["id"], n["type"], n.get("mode"), wv[:150]))


def src(nid, slot):
    n = by.get(nid)
    if not n: return "-"
    k = next((i for i, x in enumerate(n.get("inputs") or []) if x.get("name") == slot), None)
    if k is None: return "(无)"
    l = L.get(n["inputs"][k].get("link"))
    return "#%s.%s" % (l[1], by[l[1]]["type"]) if l else "(空)"


print("\n=== 采样器 ===")
for n in sorted(wf["nodes"], key=lambda z: z["id"]):
    if n["type"] in ("KSampler", "KSamplerAdvanced"):
        print("  #%-5s %s" % (n["id"], json.dumps(n.get("widgets_values") or [], ensure_ascii=False)))
        for s in ("model", "positive", "negative", "latent_image"):
            print("        %-12s <- %s" % (s, src(n["id"], s)))
print("\n=== 提示词全文 ===")
for n in sorted(wf["nodes"], key=lambda z: z["id"]):
    if n["type"] == "CLIPTextEncode":
        t = str((n.get("widgets_values") or [""])[0])
        print("\n#%s  (%d 字符)  <- clip %s" % (n["id"], len(t), src(n["id"], "clip")))
        print(t)
print("\n=== Note ===")
for n in sorted(wf["nodes"], key=lambda z: z["id"]):
    if n["type"] == "Note":
        print("\n#%s: %s" % (n["id"], str((n.get("widgets_values") or [""])[0])[:800]))
