# -*- coding: utf-8 -*-
"""只读核对：线上 1031（左侧脸正向提示词）是否已补全、有无截断"""
import os, sys, json, ssl, io, urllib.request, urllib.parse

BASE = os.environ.get("COMFY_BASE", "https://gw-efb56d453d484597a1b8ddfc86156262.cn-beijing.aigclinks.com:8016")
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
HERE = os.path.dirname(os.path.abspath(__file__))

target = int(sys.argv[1]) if len(sys.argv) > 1 else 1031
u = BASE + "/api/userdata/workflows%2F" + urllib.parse.quote("夜市百相簿-主工作流.json")
try:
    r = urllib.request.urlopen(u, timeout=90, context=ctx)
except Exception as e:
    print("!! 拉取失败（实例可能已关机）:", type(e).__name__, e)
    sys.exit(2)

raw = r.read()
d = json.loads(raw.decode("utf-8", "replace"))
if isinstance(d, dict) and "workflow" in d and "nodes" not in d:
    d = d["workflow"]

io.open(os.path.join(HERE, "_wf", "_live_ck.json"), "w", encoding="utf-8").write(
    json.dumps(d, ensure_ascii=False))

ns = {n["id"]: n for n in d.get("nodes", [])}
print("HTTP %s | bytes %d | 节点 %d" % (r.status, len(raw), len(ns)))

for nid in (1027, 1031, 1032, 1033, 1034, 1035, 1036, 1043, 1051, 1042):
    n = ns.get(nid)
    if not n:
        print("  %-5s 不存在" % nid); continue
    wv = n.get("widgets_values") or []
    txt = wv[0] if isinstance(wv, (list, tuple)) and wv else wv
    if n["type"] == "CLIPTextEncode":
        t = txt if isinstance(txt, str) else str(txt)
        print("  %-5s %-16s len=%-6d mode=%s" % (nid, n["type"], len(t), n.get("mode")))
    else:
        print("  %-5s %-16s wv=%s mode=%s" % (nid, n["type"], json.dumps(wv, ensure_ascii=False)[:110], n.get("mode")))

n = ns.get(target)
if n:
    t = n["widgets_values"][0]
    print("\n================ %d 正向提示词全文（%d 字符） ================" % (target, len(t)))
    print(t)
    print("================ 末尾 300 字符 ================")
    print(repr(t[-300:]))
    print("\n[截断自检]")
    for k in ("FINAL PRIORITY", "ONLY THE VIEWING ANGLE CHANGES", "in its correct anatomical position",
              "PHOTOGRAPHIC CONSISTENCY", "same photographic character", "MOLE"):
        print("   %-42s %s" % (k, "OK" if k in t else "MISSING"))
