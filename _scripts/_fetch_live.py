# -*- coding: utf-8 -*-
"""拉取服务器现版主工作流，核对是否处于「改动前」状态（幂等性前提）"""
import os, sys, json, ssl, io, urllib.request, urllib.parse

BASE = os.environ.get("COMFY_BASE", "https://gw-efb56d453d484597a1b8ddfc86156262.cn-beijing.aigclinks.com:8016")
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
HERE = os.path.dirname(os.path.abspath(__file__))

u = BASE + "/api/userdata/workflows%2F" + urllib.parse.quote("夜市百相簿-主工作流.json")
r = urllib.request.urlopen(u, timeout=90, context=ctx)
raw = r.read()
print("HTTP", r.status, "bytes", len(raw))
d = json.loads(raw.decode("utf-8", "replace"))
if isinstance(d, dict) and "workflow" in d and "nodes" not in d:
    d = d["workflow"]

ns = d.get("nodes", [])
ids = sorted(n["id"] for n in ns)
print("服务端: 节点 %d / 链接 %d / 分组 %d / SaveImage %d"
      % (len(ns), len(d.get("links", [])), len(d.get("groups", [])),
         sum(1 for n in ns if n["type"] == "SaveImage")))
print("last_node_id =", d.get("last_node_id"), " last_link_id =", d.get("last_link_id"))
print("1400-1420 已占用:", [i for i in ids if 1400 <= i <= 1420])
print()
print("分组:")
for g in d.get("groups", []):
    print("   ", g.get("title"), g.get("bounding"))
print()
print("SaveImage:")
for n in sorted([x for x in ns if x["type"] == "SaveImage"], key=lambda x: x["id"]):
    print("   %-6s %-42s mode=%s" % (n["id"], n["widgets_values"][0], n.get("mode")))
print()
print("关键节点取图源（1121 / 1303 ← ?）:")
for tgt in (1121, 1303):
    src = [l for l in d.get("links", []) if l[3] == tgt]
    print("   %-6s <- %s" % (tgt, src))
print("1302 mode =", [n.get("mode") for n in ns if n["id"] == 1302])

io.open(os.path.join(HERE, "_wf", "_server_live.json"), "w", encoding="utf-8").write(
    json.dumps(d, ensure_ascii=False))
print("\nsaved _wf/_server_live.json")
