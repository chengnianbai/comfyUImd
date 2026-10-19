# -*- coding: utf-8 -*-
"""扒出线上工作流 1942ebf9-… 的提示词与采样链路（并和本地 角色生成.json 对照）"""
import os, sys, ssl, json, io, urllib.request, urllib.parse
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
WANT = "1942ebf9-d94a-4790-bc94-ff98ed497520"


def get(p, t=200):
    return urllib.request.urlopen(urllib.request.Request(BASE + p), timeout=t, context=ctx).read().decode('utf-8', 'replace')


print("=== 用户区工作流 ===")
lst = json.loads(get("/api/userdata?dir=workflows"))
print("  %s" % lst)
target = None
for fn in lst:
    try:
        wf = json.loads(get("/api/userdata/workflows%2F" + urllib.parse.quote(fn, safe='')))
    except Exception as e:
        print("  %-40s 读不到 %s" % (fn, type(e).__name__)); continue
    mark = ""
    if wf.get("id") == WANT:
        mark = "  ★★ 目标"; target = (fn, wf)
    print("  %-40s id=%s nodes=%d%s" % (fn, str(wf.get("id"))[:20], len(wf["nodes"]), mark))
if not target:
    print("\n★ 没找到 %s ；改用文件列表里第一个含'角色'的" % WANT)
    for fn in lst:
        if "角色" in fn:
            target = (fn, json.loads(get("/api/userdata/workflows%2F" + urllib.parse.quote(fn, safe='')))); break
if not target:
    sys.exit(1)
FN, wf = target
print("\n\n########## %s ##########" % FN)
by = {n["id"]: n for n in wf["nodes"]}
L = {l[0]: l for l in wf["links"]}
print("nodes=%d links=%d groups=%s" % (len(wf["nodes"]), len(wf["links"]), [g["title"] for g in wf.get("groups", [])]))


def src(nid, slot):
    n = by.get(nid)
    if not n: return "-"
    k = next((i for i, x in enumerate(n.get("inputs") or []) if x.get("name") == slot), None)
    if k is None: return "(无)"
    l = L.get(n["inputs"][k].get("link"))
    return "#%s.%s" % (l[1], by[l[1]]["type"]) if l else "(空)"


print("\n=== 加载器 / 采样器 / 分辨率 ===")
for n in sorted(wf["nodes"], key=lambda z: z["id"]):
    if n["type"] in ("CheckpointLoaderSimple", "UNETLoader", "VAELoader", "LoraLoader", "DualCLIPLoader",
                     "KSampler", "KSamplerAdvanced", "EmptyLatentImage", "EmptySD3LatentImage",
                     "ImageScale", "UpscaleModelLoader", "LoadImage", "ReferenceLatent", "FluxGuidance",
                     "Denoise", "SamplerCustom"):
        print("  #%-5s %-22s mode=%-2s %s" % (n["id"], n["type"], n.get("mode"),
              json.dumps(n.get("widgets_values") or [], ensure_ascii=False)[:120]))
        if n["type"] in ("KSampler", "KSamplerAdvanced"):
            for s in ("model", "positive", "negative", "latent_image"):
                print("        %-12s <- %s" % (s, src(n["id"], s)))

print("\n=== 全部提示词 ===")
for n in sorted(wf["nodes"], key=lambda z: z["id"]):
    if n["type"] in ("CLIPTextEncode", "CLIPTextEncodeSDXL", "PromptExpansion"):
        t = str((n.get("widgets_values") or [""])[0])
        print("\n#%s mode=%s  (%d 字符)  clip <- %s" % (n["id"], n.get("mode"), len(t), src(n["id"], "clip")))
        print(t)
print("\n=== Note ===")
for n in sorted(wf["nodes"], key=lambda z: z["id"]):
    if n["type"] == "Note":
        print("\n#%s: %s" % (n["id"], str((n.get("widgets_values") or [""])[0])[:1000]))
