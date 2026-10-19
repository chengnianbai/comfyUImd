# -*- coding: utf-8 -*-
"""关机前急救：从线上拉主工作流全量存档（含节点参数 + 提示词全文），不改任何东西。
输出：
  _wf/_server_now_<ts>.json        线上工作流原样快照
  _wf/_live_params_<ts>.md         节点参数总表（不含提示词正文，只给长度/摘要）
  _wf/_prompts_<ts>/<id>.txt       各提示词节点全文备份
"""
import os, io, ssl, json, time, urllib.request, urllib.parse

BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
assert BASE, "需要 COMFY_BASE"
HERE = os.path.dirname(os.path.abspath(__file__))
WF = "夜市百相簿-主工作流.json"
TS = time.strftime("%Y%m%d_%H%M%S")

ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
url = BASE + "/api/userdata/workflows%2F" + urllib.parse.quote(WF)
raw = urllib.request.urlopen(url, timeout=120, context=ctx).read()
d = json.loads(raw.decode("utf-8", "replace"))
if isinstance(d, dict) and "workflow" in d and "nodes" not in d:
    d = d["workflow"]

snap = os.path.join(HERE, "_wf", "_server_now_%s.json" % TS)
io.open(snap, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False))
print("快照 ->", os.path.basename(snap), len(raw), "bytes")

ns = {n["id"]: n for n in d.get("nodes", [])}
links = d.get("links", [])

def ins_of(nid):
    """返回该节点输入连线 [上游节点id, 上游槽位名]"""
    out = []
    for l in links:
        # l = [id, origin_id, origin_slot, target_id, target_slot, type]
        if len(l) >= 6 and l[3] == nid:
            src = ns.get(l[1])
            st = src["type"] if src else "?"
            ss = ""
            try:
                ss = src["outputs"][l[2]].get("name") if src and src.get("outputs") else ""
            except Exception:
                pass
            out.append((l[1], st, ss))
    return out

L = []
def w(s=""):
    L.append(s)

w("# 闻灯 Kontext 三视角组 · 线上节点参数总表")
w()
w("- 实拉时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"))
w("- 来源：服务器 `%s`（只读拉取，未做任何写入）" % WF)
w("- 规模：节点 %d / 链接 %d / 分组 %d" % (len(ns), len(links), len(d.get("groups", []))))
w("- `last_node_id` = %s，`last_link_id` = %s" % (d.get("last_node_id"), d.get("last_link_id")))
w()
w("## 分组")
for g in d.get("groups", []):
    w("- %s" % g.get("title"))
w()
w("## 节点明细（按 id）")
w()
w("| id | 类型 | 关键参数 | 输入来自 | mode |")
w("|---|---|---|---|---|")
for nid in sorted(ns):
    n = ns[nid]
    t = n["type"]
    wv = n.get("widgets_values")
    show = ""
    if isinstance(wv, list):
        if t in ("CLIPTextEncode", "CLIPTextEncodeFlux", "TextEncodeQwenImageEditPlus", "CLIPTextEncodeSDXL"):
            txts = [x for x in wv if isinstance(x, str)]
            show = "文本 %s 字符 | %r…" % (len(txts[0]) if txts else 0, (txts[0][:40] if txts else ""))
        else:
            parts = []
            for x in wv:
                if isinstance(x, str) and len(x) > 60:
                    parts.append("%s…(%d字符)" % (x[:40], len(x)))
                else:
                    parts.append(json.dumps(x, ensure_ascii=False))
            show = ", ".join(parts)
    elif isinstance(wv, dict):
        show = json.dumps(wv, ensure_ascii=False)[:120]
    ins = "; ".join("%s(%s)" % (a, c) for a, c, _ in ins_of(nid)) or "-"
    md = n.get("mode")
    md = "" if md in (0, None) else str(md)
    w("| %s | %s | %s | %s | %s |" % (nid, t, show.replace("|", "\\|"), ins, md))
w()
w("## SaveImage 分支")
for n in sorted([x for x in ns.values() if x["type"] == "SaveImage"], key=lambda x: x["id"]):
    w("- `%s`  **%s**  mode=%s" % (n["id"], n["widgets_values"][0], n.get("mode")))
w()
w("## 提示词节点全文备份")
w()
pdir = os.path.join(HERE, "_wf", "_prompts_%s" % TS)
os.makedirs(pdir, exist_ok=True)
for nid in sorted(ns):
    n = ns[nid]
    if n["type"].startswith("CLIPTextEncode"):
        wv = n.get("widgets_values") or []
        txts = [x for x in wv if isinstance(x, str)]
        if txts:
            fn = os.path.join(pdir, "%s.txt" % nid)
            io.open(fn, "w", encoding="utf-8").write(txts[0])
            w("- `%s`：%d 字符 → `_wf/_prompts_%s/%s.txt`" % (nid, len(txts[0]), TS, nid))
            w("  末尾 40 字符：`%s`" % txts[0][-40:].replace("\n", "\\n"))

out = os.path.join(HERE, "_wf", "_live_params_%s.md" % TS)
io.open(out, "w", encoding="utf-8").write("\n".join(L))
print("参数表 ->", os.path.basename(out))
print("提示词 ->", "_wf/_prompts_%s/" % TS)
print()
print("\n".join(L[:14]))
