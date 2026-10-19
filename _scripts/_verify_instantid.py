# -*- coding: utf-8 -*-
"""核实 InstantID 三个模型是否真的落地（用 Manager 清单里的 installed 标记 + 目录端点）"""
import ssl, json, sys, os, urllib.request, urllib.error
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE


def req(p, t=200):
    return urllib.request.urlopen(urllib.request.Request(BASE + p), timeout=t, context=ctx).read()


d = json.loads(req("/externalmodel/getlist?mode=cache").decode('utf-8', 'replace'))
ms = d.get("models") or []
WANT = {"ip-adapter.bin": "instantid", "diffusion_pytorch_model.safetensors": "controlnet/instantid",
        "antelopev2.zip": "insightface/models"}
print("=== Manager installed 标记（现在 vs 之前）===")
for m in ms:
    sp, fn = m.get("save_path"), m.get("filename")
    if (sp, fn) in (("instantid", "ip-adapter.bin"), ("instantid/SDXL", "ip-adapter.bin"),
                    ("controlnet/instantid", "diffusion_pytorch_model.safetensors"),
                    ("controlnet/SDXL/instantid", "diffusion_pytorch_model.safetensors"),
                    ("insightface/models", "antelopev2.zip")):
        print("  %-28s %-42s installed=%s" % (sp, fn, m.get("installed")))

print("\n=== 直接看目录（多种端点）===")
for ep in ("/models", "/models/instantid", "/internal/files/instantid",
           "/api/manager/model_list", "/customnode/getlist?mode=cache"):
    try:
        r = req(ep, 60).decode('utf-8', 'replace')
        mark = [k for k in ("instantid", "antelope", "ip-adapter") if k in r.lower()]
        print("  %-34s %8d 字节 ；命中 %s" % (ep, len(r), mark or "无"))
    except urllib.error.HTTPError as e:
        print("  %-34s HTTP %s" % (ep, e.code))
    except Exception as e:
        print("  %-34s ERR %s" % (ep, type(e).__name__))

print("\n=== 节点包与加载器 ===")
oi = json.loads(req("/object_info", 240).decode('utf-8', 'replace'))
for k in ("InstantIDModelLoader", "InstantIDFaceAnalysis", "ApplyInstantID", "IPAdapterModelLoader",
          "IPAdapterUnifiedLoader", "CLIPVisionLoader", "StyleModelLoader"):
    if k in oi:
        req_in = oi[k].get("input", {}).get("required", {})
        lst = None
        for f in ("instantid_file", "ipadapter_file", "clip_name", "model_name", "style_model_name"):
            if f in req_in and isinstance(req_in[f][0], list):
                lst = req_in[f][0]
        print("  %-24s 在 ；模型列表 %s" % (k, (len(lst), lst[:8]) if lst is not None else "—"))
    else:
        print("  %-24s 不在" % k)
print("\n=== 队列 ===")
print(" ", req("/api/manager/queue/status", 40).decode('utf-8', 'replace')[:200])
