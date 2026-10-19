# -*- coding: utf-8 -*-
"""装身份模块（第一步：探通道 + 排队节点包 + 核实模型源）

目标（按锁脸强度）：InstantID（最强，且不需要 CLIP-ViT，模型件更少）
            备选：IP-Adapter FaceID Plus v2 + CLIP-ViT-H
"""
import ssl, json, sys, os, time, urllib.request, urllib.error, urllib.parse
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0"}


def req(p, data=None, t=120, ctype=None):
    r = urllib.request.Request(BASE + p, data=data)
    if data is not None:
        r.add_header("Content-Type", ctype or "application/json")
    return urllib.request.urlopen(r, timeout=t, context=ctx).read()


print("=== A) Manager 端点探测 ===")
for p, data in (("/api/manager/queue/status", None),
                ("/api/manager/version", None),
                ("/manager/version", None),
                ("/api/manager/queue/install_model", None),
                ("/customnode/install/git_url", None)):
    try:
        r = req(p, data, 30)
        print("  %-40s OK %s" % (p, r.decode('utf-8', 'replace')[:110]))
    except urllib.error.HTTPError as e:
        print("  %-40s HTTP %s %s" % (p, e.code, e.read().decode('utf-8', 'replace')[:110]))
    except Exception as e:
        print("  %-40s ERR %s" % (p, type(e).__name__))

print("\n=== B) 已安装的自定义节点里有没有 IPAdapter / InstantID ===")
for ep in ("/api/manager/queue/status", "/customnode/getlist?mode=cache", "/api/customnode/list"):
    try:
        r = req(ep, None, 60).decode('utf-8', 'replace')
        hit = [k for k in ("InstantID", "IPAdapter", "ipadapter", "instantid") if k.lower() in r.lower()]
        print("  %-36s %d 字节 ；命中关键词 %s" % (ep, len(r), hit or "无"))
    except Exception as e:
        print("  %-36s ERR %s" % (ep, type(e).__name__))

print("\n=== C) ModelScope 上是否有对应模型源（国内可达）===")
CAND = [("InstantID", "AI-ModelScope/InstantID", "ip-adapter.bin", "instantid/ip-adapter.bin"),
        ("InstantID-ControlNet", "AI-ModelScope/InstantID", "ControlNetModel/diffusion_pytorch_model.safetensors",
         "controlnet/instantid/diffusion_pytorch_model.safetensors"),
        ("antelopev2", "AI-ModelScope/antelopev2", None, "insightface/models/antelopev2"),
        ("buffalo_l", "AI-ModelScope/buffalo_l", None, "insightface/models/buffalo_l"),
        ("InsightFace", "deepinsight/insightface", None, "(参考)"),
        ("IP-Adapter-FaceID", "AI-ModelScope/IP-Adapter-FaceID", "ip-adapter-faceid-plusv2_sdxl.bin",
         "ipadapter/ip-adapter-faceid-plusv2_sdxl.bin"),
        ("CLIP-ViT-H-14", "AI-ModelScope/CLIP-ViT-H-14-laion2B-s32B-b79K", "open_clip_model.safetensors",
         "clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors")]
for tag, repo, want, dest in CAND:
    api = "https://www.modelscope.cn/api/v1/models/%s/repo/files?Revision=master&Root=" % repo
    try:
        d = json.loads(urllib.request.urlopen(urllib.request.Request(api, headers=UA), timeout=60)
                       .read().decode('utf-8', 'replace'))
        files = d.get("Data", {}).get("Files", [])
        big = [(f.get("Name"), f.get("Size", 0)) for f in files if f.get("Size", 0) > 3_000_000]
        print("  %-22s %-46s 仓库存在，>3MB 文件 %d 个" % (tag, repo, len(big)))
        for n, s in big[:6]:
            print("        %-56s %8.1f MB" % (n, s/1e6))
    except Exception as e:
        print("  %-22s %-46s 不可用（%s）" % (tag, repo, type(e).__name__))
print("\n(只探测，未下载、未安装。下一步按你确认的目标排队下载。)")
