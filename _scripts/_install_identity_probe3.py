# -*- coding: utf-8 -*-
"""第三步：正确解析 Manager 外部模型清单，列出身份相关的真实条目（含 save_path / filename / url）"""
import ssl, json, sys, os, urllib.request
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
s = urllib.request.urlopen(urllib.request.Request(BASE + "/externalmodel/getlist?mode=cache"),
                           timeout=180, context=ctx).read().decode('utf-8', 'replace')
d = json.loads(s)
print("顶层键：%s" % list(d.keys())[:10])
models = d.get("models") or []
print("条目总数 %d" % len(models))
print("\n样例条目字段：%s" % (list(models[0].keys()) if models and isinstance(models[0], dict) else type(models[0])))

KW = ("instantid", "ip-adapter", "ipadapter", "insightface", "antelope", "buffalo", "faceid", "clip-vit-h", "clip_vision")
hits = []
for m in models:
    if not isinstance(m, dict):
        continue
    blob = json.dumps(m, ensure_ascii=False).lower()
    if any(k in blob for k in KW):
        hits.append(m)
print("\n=== 身份相关条目 %d 个 ===" % len(hits))
for m in hits:
    print("\n  filename      = %s" % m.get("filename"))
    print("  save_path     = %s" % m.get("save_path"))
    print("  name/title     = %s" % (m.get("name") or m.get("title")))
    print("  base          = %s" % m.get("base"))
    u = m.get("url") or m.get("reference") or ""
    print("  url           = %s" % (u if len(u) < 130 else u[:127] + "..."))
    if m.get("size"): print("  size          = %s" % m.get("size"))
    print("  ---")
