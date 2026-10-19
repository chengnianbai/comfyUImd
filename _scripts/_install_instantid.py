# -*- coding: utf-8 -*-
"""装 InstantID：① 自定义节点包 ② 三个模型文件 ③ 启动队列

清单里的真实条目（由 /externalmodel/getlist 取出，含 HF url 与大小）：
  instantid/ip-adapter.bin                       1.69GB
  controlnet/instantid/diffusion_pytorch_model.safetensors  2.50GB
  insightface/models/antelopev2.zip              360.7MB
"""
import ssl, json, sys, os, time, urllib.request, urllib.error
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE


def req(p, data=None, t=180, ctype="application/json"):
    r = urllib.request.Request(BASE + p, data=data)
    if data is not None:
        r.add_header("Content-Type", ctype)
    return urllib.request.urlopen(r, timeout=t, context=ctx).read()


# ---------- 1) 自定义节点包 ----------
print("=== 1) 装自定义节点包 ComfyUI_InstantID ===")
NODE_TRIES = [("/api/manager/queue/install", {"id": "ComfyUI_InstantID", "version": "latest", "mode": "cache"}),
              ("/api/manager/queue/install", {"id": "https://github.com/cubiq/ComfyUI_InstantID", "version": "latest", "mode": "cache"}),
              ("/customnode/install/git_url", "https://github.com/cubiq/ComfyUI_InstantID"),
              ("/customnode/install", "https://github.com/cubiq/ComfyUI_InstantID")]
done_node = False
for ep, payload in NODE_TRIES:
    body = payload if isinstance(payload, str) else json.dumps(payload)
    ct = "text/plain" if isinstance(payload, str) else "application/json"
    try:
        r = req(ep, body.encode(), 120, ct)
        print("  %-38s OK  %s" % (ep, r.decode('utf-8', 'replace')[:150])); done_node = True; break
    except urllib.error.HTTPError as e:
        print("  %-38s HTTP %s  %s" % (ep, e.code, e.read().decode('utf-8', 'replace')[:130]))
    except Exception as e:
        print("  %-38s ERR %s" % (ep, type(e).__name__))
if not done_node:
    print("  ★ 节点包三种端点都没通 —— 需要你在 ComfyUI 界面里用 Manager 手动装 ComfyUI_InstantID")

# ---------- 2) 模型 ----------
JOBS = [
    {"base": "SDXL", "save_path": "instantid", "filename": "ip-adapter.bin", "size": "1.69GB",
     "url": "https://huggingface.co/InstantX/InstantID/resolve/main/ip-adapter.bin",
     "name": "InstantID ip-adapter.bin", "reference": "https://huggingface.co/InstantX/InstantID"},
    {"base": "SDXL", "save_path": "controlnet/instantid", "filename": "diffusion_pytorch_model.safetensors",
     "size": "2.50GB",
     "url": "https://huggingface.co/InstantX/InstantID/resolve/main/ControlNetModel/diffusion_pytorch_model.safetensors",
     "name": "InstantID ControlNet", "reference": "https://huggingface.co/InstantX/InstantID"},
    {"base": "SDXL", "save_path": "insightface/models", "filename": "antelopev2.zip", "size": "360.7MB",
     "url": "https://huggingface.co/MonsterMMORPG/tools/resolve/main/antelopev2.zip",
     "name": "antelopev2", "reference": "https://huggingface.co/MonsterMMORPG/tools"},
]
print("\n=== 2) 提交 3 个模型下载 ===")
okn = 0
for j in JOBS:
    try:
        r = req("/api/manager/queue/install_model", json.dumps(j).encode(), 120)
        print("  %-46s -> %s" % (j["filename"], r.decode('utf-8', 'replace')[:80])); okn += 1
    except urllib.error.HTTPError as e:
        print("  %-46s HTTP %s  %s" % (j["filename"], e.code, e.read().decode('utf-8', 'replace')[:160]))
    except Exception as e:
        print("  %-46s ERR %s" % (j["filename"], type(e).__name__))

# ---------- 3) 启动队列 ----------
print("\n=== 3) 启动队列 ===")
for ep in ("/api/manager/queue/start", "/manager/queue/start"):
    try:
        r = req(ep, b"{}", 60); print("  %-30s OK %s" % (ep, r.decode('utf-8', 'replace')[:90])); break
    except Exception as e:
        print("  %-30s ERR %s" % (ep, type(e).__name__))

print("\n=== 4) 队列状态（头 60 秒）===")
for i in range(10):
    time.sleep(6)
    try:
        st = req("/api/manager/queue/status", None, 30).decode('utf-8', 'replace')
        print("  [%3ds] %s" % ((i+1)*6, st[:180]))
    except Exception as e:
        print("  [%3ds] ERR %s" % ((i+1)*6, type(e).__name__))
print("\n(提交完成。若队列在跑，文件会陆续落地；ComfyUI 需重启后 InstantID 节点才出现。)")
