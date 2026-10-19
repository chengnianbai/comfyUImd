# -*- coding: utf-8 -*-
"""拉服务器最新几次运行的提示词摘要 + 下载新产物（诊断用）"""
import os, io, ssl, json, time, urllib.request, urllib.parse, sys

BASE = os.environ["COMFY_BASE"].rstrip("/")
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = r"D:\xiaobai-claude code\comfyUImd\系列-夜市百相簿\02-角色\闻灯\设定图\_diag_2style"


def raw(p, timeout=180):
    return urllib.request.urlopen(BASE + p, timeout=timeout, context=ctx).read()


h = json.loads(raw("/history", 240).decode("utf-8", "replace"))
rows = []
for pid, rec in h.items():
    imgs = []
    for nid, o in (rec.get("outputs") or {}).items():
        for im in o.get("images", []):
            imgs.append(im["filename"])
    p = rec.get("prompt")
    ts, g = 0, None
    if isinstance(p, list) and len(p) > 2:
        g = p[2]
        if len(p) > 3 and isinstance(p[3], dict):
            ts = p[3].get("create_time") or 0
    rows.append((ts, pid, imgs, g))
rows.sort()

print("=== 最近 8 次运行 ===")
for ts, pid, imgs, g in rows[-8:]:
    t = time.strftime("%H:%M:%S", time.localtime(ts / 1000)) if ts else "?"
    lt = (g.get("1031", {}).get("inputs", {}) or {}).get("text", "") if g else ""
    print("  %s  L1031=%-6d  %s" % (t, len(lt), ", ".join(imgs) if imgs else "-"))

# 最新一次有产物的运行
last = None
for r in reversed(rows):
    if r[2] and r[3]:
        last = r; break
ts, pid, imgs, g = last
print("\n=== 最近一次运行 %s ===" % time.strftime("%H:%M:%S", time.localtime(ts / 1000)))
lt = g.get("1031", {}).get("inputs", {}).get("text", "")
io.open(os.path.join(HERE, "_wf", "_last_run_1031.txt"), "w", encoding="utf-8").write(lt)
io.open(os.path.join(HERE, "_wf", "_last_run_1043.txt"), "w", encoding="utf-8").write(
    g.get("1043", {}).get("inputs", {}).get("text", ""))
print("  1031 长度=%d  开头=%r" % (len(lt), lt[:90]))
print("  1031 结尾=%r" % lt[-110:])
for k in ("1031", "1034", "1033", "1046", "1044"):
    if k in g:
        ins = {kk: vv for kk, vv in g[k]["inputs"].items() if kk != "text"}
        print("  %-5s %-18s %s" % (k, g[k]["class_type"], json.dumps(ins, ensure_ascii=False)[:200]))

print("\n=== 下载新产物 ===")
os.makedirs(OUT, exist_ok=True)
for fn in imgs:
    dst = os.path.join(OUT, fn)
    if os.path.exists(dst):
        print("  已有 %s" % fn); continue
    q = urllib.parse.urlencode({"filename": fn, "subfolder": "", "type": "output"})
    try:
        d = raw("/view?" + q, 300)
    except Exception as e:
        print("  FAIL %s %s" % (fn, e)); continue
    open(dst, "wb").write(d)
    print("  saved %-46s %8.1f KB" % (fn, len(d) / 1024))
print("->", OUT)
