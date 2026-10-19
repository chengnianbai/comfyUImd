# -*- coding: utf-8 -*-
"""诊断「2 类风格」：翻服务器运行历史，取用户最近几次实际提交的提示词与产物"""
import os, io, json, ssl, urllib.request, urllib.parse, time

BASE = os.environ["COMFY_BASE"].rstrip("/")
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
HERE = os.path.dirname(os.path.abspath(__file__))


def raw(p, timeout=120):
    return urllib.request.urlopen(BASE + p, timeout=timeout, context=ctx).read()


h = json.loads(raw("/history", 180).decode("utf-8", "replace"))
print("history 条数 =", len(h))

rows = []
for pid, rec in h.items():
    imgs = []
    for nid, o in (rec.get("outputs") or {}).items():
        for im in o.get("images", []):
            imgs.append(im["filename"])
    p = rec.get("prompt")
    ts = None
    graph = None
    if isinstance(p, list) and len(p) > 2:
        graph = p[2]
        if len(p) > 3 and isinstance(p[3], dict):
            ts = p[3].get("create_time")
    status = ((rec.get("status") or {}).get("status_str"))
    rows.append((ts or 0, pid, status, imgs, graph))

rows.sort()
print("\n%-14s %-38s %-8s %s" % ("时间", "prompt_id", "状态", "产物"))
for ts, pid, status, imgs, g in rows[-12:]:
    t = time.strftime("%H:%M:%S", time.localtime(ts / 1000)) if ts else "?"
    print("%-14s %-38s %-8s %s" % (t, pid, status, ", ".join(imgs) if imgs else "-"))

# 最近一次带产物的运行
last = None
for r in reversed(rows):
    if r[3] and r[4]:
        last = r; break
if last:
    ts, pid, status, imgs, g = last
    print("\n================ 最近一次实际运行的提交内容 ================")
    print("prompt_id =", pid, " 时间 =", time.strftime("%H:%M:%S", time.localtime(ts / 1000)))
    print("产物 =", imgs)
    print("\n提交里出现的节点数 =", len(g))
    for nid in ("1031", "1043", "1030"):
        if nid in g:
            t = g[nid]["inputs"].get("text", "")
            print("\n--- 节点 %s  text 长度 %d ---" % (nid, len(t)))
            print("  开头: %r" % t[:110])
            print("  结尾: %r" % t[-160:])
    for nid in ("1034", "1046", "1044", "1052", "1040", "1042", "1036", "1048"):
        if nid in g:
            print("  %-5s %-24s %s" % (nid, g[nid]["class_type"],
                                        json.dumps(g[nid]["inputs"], ensure_ascii=False)[:260]))
    # 存下来
    io.open(os.path.join(HERE, "_wf", "_last_run_graph.json"), "w", encoding="utf-8").write(
        json.dumps({k: v for k, v in g.items()}, ensure_ascii=False))
    io.open(os.path.join(HERE, "_wf", "_last_run_1031.txt"), "w", encoding="utf-8").write(
        g.get("1031", {}).get("inputs", {}).get("text", ""))
    io.open(os.path.join(HERE, "_wf", "_last_run_meta.json"), "w", encoding="utf-8").write(
        json.dumps({"prompt_id": pid, "time": ts, "images": imgs}, ensure_ascii=False))
    print("\n已存 _wf/_last_run_graph.json / _last_run_1031.txt / _last_run_meta.json")

# 各次运行里 1031 长度序列（看用户改了几次）
print("\n================ 历次运行 1031 文本长度 ================")
for ts, pid, status, imgs, g in rows:
    if not g:
        continue
    t = (g.get("1031", {}).get("inputs", {}) or {}).get("text", "")
    f = (g.get("1043", {}).get("inputs", {}) or {}).get("text", "")
    print("  %s  L1031=%-6d L1043=%-6d  %s" % (
        time.strftime("%m-%d %H:%M", time.localtime(ts / 1000)) if ts else "?", len(t), len(f),
        (imgs[0] if imgs else "-")))
