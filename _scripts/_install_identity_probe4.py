# -*- coding: utf-8 -*-
"""列出 Manager 清单里「身份/人脸」相关的全部条目（紧凑）"""
import ssl, json, sys, os, urllib.request
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
d = json.loads(urllib.request.urlopen(urllib.request.Request(BASE + "/externalmodel/getlist?mode=cache"),
                                     timeout=180, context=ctx).read().decode('utf-8', 'replace'))
ms = d.get("models") or []


def hb(m, keys):
    b = json.dumps(m, ensure_ascii=False).lower()
    return any(k in b for k in keys)


GROUPS = [("★ InstantID", ("instantid",)),
          ("★ FaceID", ("faceid",)),
          ("★ insightface / antelope", ("insightface", "antelope", "buffalo")),
          ("★ Flux Redux", ("redux",)),
          ("SDXL IP-Adapter", ("sdxl",)),
          ("其他 ip-adapter", ("ip-adapter", "ipadapter"))]
for title, keys in GROUPS:
    sel = [m for m in ms if hb(m, keys)]
    if title == "SDXL IP-Adapter":
        sel = [m for m in sel if hb(m, ("ip-adapter", "ipadapter"))]
    print("\n=== %s   （%d 条）===" % (title, len(sel)))
    seen = set()
    for m in sel:
        k = (m.get("save_path"), m.get("filename"))
        if k in seen: continue
        seen.add(k)
        print("  %-14s %-52s %-14s %-8s %s" % (m.get("save_path"), m.get("filename"),
                                               m.get("base"), m.get("size"),
                                               "已装" if m.get("installed") else ""))
        u = m.get("url", "")
        if "huggingface" in u:
            print("       url(HF) %s" % u[:118])
        else:
            print("       url      %s" % u[:118])
