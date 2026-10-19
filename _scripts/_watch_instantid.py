# -*- coding: utf-8 -*-
"""等 InstantID 三个文件下完 + 核实落地 + 检查节点包状态"""
import ssl, json, sys, os, time, urllib.request
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE


def req(p, t=90):
    return urllib.request.urlopen(urllib.request.Request(BASE + p), timeout=t, context=ctx).read()


EXPECT = {"instantid/ip-adapter.bin": 1.69e9,
          "controlnet/instantid/diffusion_pytorch_model.safetensors": 2.50e9,
          "insightface/models/antelopev2.zip": 360.7e6}
print("=== 轮询落地（最多 ~10 分钟）===")
for i in range(60):
    time.sleep(10)
    try:
        st = json.loads(req("/api/manager/queue/status", 30).decode('utf-8', 'replace'))
    except Exception:
        st = {}
    found = {}
    for d in ("instantid", "controlnet/instantid", "insightface/models"):
        try:
            r = req("/models/" + d, 30).decode('utf-8', 'replace')
            for name, sz in EXPECT.items():
                if name.split('/')[-1] in r:
                    found[name] = True
        except Exception:
            pass
    print("  [%3ds] queue=%s  已落地 %d/3 %s"
          % ((i+1)*10, json.dumps(st, ensure_ascii=False)[:90], len(found), list(found)))
    if len(found) >= 3 and not st.get("is_processing"):
        print("  ✔ 三个文件都已到位"); break
    if i > 3 and not st.get("is_processing") and st.get("in_progress_count", 0) == 0 and len(found) < 3:
        print("  ★ 队列已空但文件不全 —— 可能有条目被拒或被跳过"); break

print("\n=== 最终核对 ===")
for d in ("instantid", "controlnet/instantid", "insightface/models", "insightface/models/antelopev2"):
    try:
        print("  [%s] %s" % (d, req("/models/" + d, 40).decode('utf-8', 'replace')[:300].replace("\n", " ")))
    except Exception as e:
        print("  [%s] ERR %s" % (d, type(e).__name__))
print("\n=== 节点包是否已出现（重启前应为无）===")
try:
    oi = json.loads(req("/object_info", 200).decode('utf-8', 'replace'))
    print("  InstantIDModelLoader: %s" % ("在" if "InstantIDModelLoader" in oi else "不在"))
    print("  IPAdapterModelLoader: %s" % ("在" if "IPAdapterModelLoader" in oi else "不在"))
except Exception as e:
    print("  ERR %s" % type(e).__name__)
