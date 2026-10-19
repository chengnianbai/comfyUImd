# -*- coding: utf-8 -*-
"""1) 修正节点标题/说明文字  2) 校验 widget 顺序  3) 上传到服务器工作流目录"""
import json, os, ssl, urllib.request, urllib.parse

WF = r"D:\xiaobai-claude code\comfyUImd\_scripts\_wf\夜市百相簿_v19.json"
BASE = "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016"
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE

TITLES = {
    1: "底模 · HelloWorld XL 7.0（SDXL）",
    2: "正向 A · 人物 + 构图（当前：脸部正面）",
    3: "正向 B · 白底 + 光位 + 皮肤质感",
    5: "负向 N1 · 反柔弱 / 反女性",
    6: "画布 896×1152（SDXL 竖构图）",
    7: "KSampler 第1段 · 30步 CFG10 denoise1.0",
    8: "VAEDecode（草稿 896×1152）",
    9: "预览 · 草稿",
    10: "存图 · 草稿",
    12: "KSampler 第2段 · 20步 CFG10 denoise0.25",
    13: "VAEDecode（成品）",
    14: "★ 预览 · 成品（跑完先看这里）",
    15: "存图 · 成品",
    16: "说明 · 夜市百相簿（闻灯 · 先脸后身 v19）",
}

with open(WF, encoding="utf-8") as f:
    wf = json.load(f)

for n in wf["nodes"]:
    if n["id"] in TITLES:
        n["title"] = TITLES[n["id"]]

# ---- 校验 widget 顺序（对齐 /object_info）----
def oi(node):
    d = json.loads(urllib.request.urlopen(BASE + "/object_info/" + node, timeout=40, context=ctx).read().decode())
    return list(d[node]["input"].get("required", {}).keys())

checks = {
    "ImageScaleBy": ["upscale_method", "scale_by"],
    "CLIPSetLastLayer": ["stop_at_clip_layer"],
    "UpscaleModelLoader": ["model_name"],
    "EmptyLatentImage": ["width", "height", "batch_size"],
    "KSampler": ["seed", "steps", "cfg", "sampler_name", "scheduler", "denoise"],
}
print("=== widget 顺序核对 ===")
for node, expect in checks.items():
    actual = oi(node)
    wv = [n for n in wf["nodes"] if n["type"] == node]
    n_wv = len(wv[0].get("widgets_values", [])) if wv else -1
    ok = all(e in actual for e in expect)
    print("  %-20s object_info顺序=%s  期望=%s  %s | 本工作流 widgets=%d" %
          (node, actual, expect, "OK" if ok else "★不符", n_wv))

# 4x-UltraSharp 文件名核对
d = json.loads(urllib.request.urlopen(BASE + "/object_info/UpscaleModelLoader", timeout=40, context=ctx).read().decode())
opts = d["UpscaleModelLoader"]["input"]["required"]["model_name"][1]["options"]
print("\n可用放大模型:", opts)
up = [n for n in wf["nodes"] if n["type"] == "UpscaleModelLoader"][0]["widgets_values"][0]
print("工作流里写的:", up, "->", "OK" if up in opts else "★不在列表里")

with open(WF, "w", encoding="utf-8") as f:
    json.dump(wf, f, ensure_ascii=False, indent=1)

# ---- 上传 ----
body = json.dumps(wf, ensure_ascii=False).encode("utf-8")
target = "/api/userdata/workflows%2F" + urllib.parse.quote("夜市百相簿.json") + "?overwrite=true"
req = urllib.request.Request(BASE + target, data=body, method="POST",
                             headers={"Content-Type": "application/json"})
r = urllib.request.urlopen(req, timeout=60, context=ctx)
print("\n上传:", r.status, r.read().decode()[:200])

# ---- 清理探针文件 ----
try:
    req = urllib.request.Request(BASE + "/api/userdata/_probe.json", method="DELETE")
    print("清理探针:", urllib.request.urlopen(req, timeout=30, context=ctx).status)
except Exception as e:
    print("清理探针失败(可忽略):", type(e).__name__)

# ---- 读回验证 ----
back = json.loads(urllib.request.urlopen(
    BASE + "/api/userdata/workflows%2F" + urllib.parse.quote("夜市百相簿.json"),
    timeout=40, context=ctx).read().decode())
print("\n读回验证: 节点 %d 个, 链接 %d 条, id=%s" % (len(back["nodes"]), len(back["links"]), back["id"]))
ks = [n for n in back["nodes"] if n["type"] == "KSampler"]
for k in ks:
    print("  KSampler id=%s %s" % (k["id"], k["widgets_values"]))
ck = [n for n in back["nodes"] if n["type"] == "CheckpointLoaderSimple"][0]
print("  底模:", ck["widgets_values"])
lat = [n for n in back["nodes"] if n["type"] == "EmptyLatentImage"][0]
print("  画布:", lat["widgets_values"])
