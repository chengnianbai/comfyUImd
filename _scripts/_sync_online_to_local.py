# -*- coding: utf-8 -*-
"""把 ComfyUI 服务器上最新的工作流 JSON 回写到本地文件（字节一致），供提交 GitHub"""
import os, sys, ssl, json, io, urllib.request, urllib.parse
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
if not BASE:
    print("★ 先设 COMFY_BASE"); sys.exit(4)
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
ROOT = r"D:\xiaobai-claude code\comfyUImd"

PAIRS = [("角色生成.json", os.path.join(ROOT, "系列-夜市百相簿", "02-角色", "角色生成.json")),
         ("闻灯.json", os.path.join(ROOT, "系列-夜市百相簿", "02-角色", "闻灯", "工作流", "闻灯.json"))]

for online_name, local in PAIRS:
    url = BASE + "/api/userdata/workflows%2F" + urllib.parse.quote(online_name, safe='')
    raw = urllib.request.urlopen(urllib.request.Request(url), timeout=180, context=ctx).read()
    wf = json.loads(raw.decode('utf-8', 'replace'))
    # 本地旧档信息
    old = {}
    if os.path.exists(local):
        try:
            ow = json.loads(io.open(local, encoding="utf-8").read())
            old = {"nodes": len(ow.get("nodes", [])), "links": len(ow.get("links", [])),
                   "size": os.path.getsize(local)}
        except Exception:
            old = {"nodes": "读不出"}
    print("\n%s" % online_name)
    print("  线上：nodes=%d links=%d  id=%s  %d 字节"
          % (len(wf["nodes"]), len(wf["links"]), str(wf.get("id"))[:12], len(raw)))
    print("  本地：%s" % old)
    os.makedirs(os.path.dirname(local), exist_ok=True)
    io.open(local, "wb").write(raw)
    # 回读校验
    back = json.loads(io.open(local, encoding="utf-8").read())
    same = (len(back["nodes"]) == len(wf["nodes"]) and len(back["links"]) == len(wf["links"]))
    print("  ✔ 已写入本地，回读 nodes=%d links=%d → %s"
          % (len(back["nodes"]), len(back["links"]), "一致" if same else "★ 不一致"))
    # 抽查关键字段
    if online_name == "角色生成.json":
        by = {n["id"]: n for n in back["nodes"]}
        print("     节点类型：%s" % sorted({n["type"] for n in back["nodes"]}))
        if 6 in by: print("     KSampler cfg = %s" % (by[6].get("widgets_values") or [None])[3:4])
        if 5 in by: print("     画布 = %s" % (by[5].get("widgets_values") or [])[:2])
