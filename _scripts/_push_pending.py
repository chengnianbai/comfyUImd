# -*- coding: utf-8 -*-
"""带重试 + 回读校验地把本地「待推送工作流」写回线上（应对网关偶发 WinError 10054）

用法： python _push_pending.py _pending_fullbody.json
"""
import os, sys, io, ssl, json, time, urllib.request, urllib.parse
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
if not BASE:
    print("★ 先设 COMFY_BASE"); sys.exit(4)
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
ROOT = r"D:\xiaobai-claude code\comfyUImd"
WFDIR = os.path.join(ROOT, "_scripts", "_wf")
FN = sys.argv[1] if len(sys.argv) > 1 else "_pending_fullbody.json"
p = os.path.join(WFDIR, FN)
body = io.open(p, encoding="utf-8").read().encode("utf-8")
print("待推送 %s  %d 字节" % (FN, len(body)))
WNAME = sys.argv[2] if len(sys.argv) > 2 else "夜市百相簿-主工作流.json"
ENC = urllib.parse.quote(WNAME, safe='')
print("目标工作流 %s" % WNAME)


def post(payload):
    r = urllib.request.Request(BASE + "/api/userdata/workflows%2F" + ENC, data=payload,
                               headers={"Content-Type": "application/json",
                                        "Content-Length": str(len(payload)),
                                        "Connection": "close"})
    return urllib.request.urlopen(r, timeout=300, context=ctx).read()


ok = False
for i in range(5):
    try:
        print("  第 %d 次写入..." % (i + 1))
        post(body)
        ok = True; break
    except Exception as e:
        print("    失败 %s %s" % (type(e).__name__, str(e)[:90]))
        time.sleep(6)
if not ok:
    print("★ 5 次写入都失败，线上未改。"); sys.exit(1)

back = json.loads(urllib.request.urlopen(BASE + "/api/userdata/workflows%2F" + ENC, timeout=180, context=ctx)
                  .read().decode('utf-8', 'replace'))
want = json.loads(body.decode('utf-8'))
print("\n=== 回读校验 ===")
print("  线上 nodes=%d links=%d ；待推送 nodes=%d links=%d"
      % (len(back["nodes"]), len(back["links"]), len(want["nodes"]), len(want["links"])))
bb = {n["id"]: n for n in back["nodes"]}
wb = {n["id"]: n for n in want["nodes"]}
miss = [i for i in wb if i not in bb]
print("  待推送里有、线上没有的节点：%s" % (miss or "无 ✔"))
extra = [i for i in bb if i not in wb]
print("  线上有、待推送里没有的节点：%s" % (extra or "无 ✔"))
for g in back.get("groups", []):
    print("  组 id=%s %r  包围盒=%s" % (g["id"], g["title"], [round(v) for v in g["bounding"]]))
act = [(n["id"], (n.get("widgets_values") or [None])[0]) for n in back["nodes"]
       if n["type"] == "SaveImage" and n.get("mode") == 0]
print("  启用中的存图节点 %d 个：" % len(act))
for i, v in act: print("     #%-5s %s" % (i, v))
io.open(os.path.join(WFDIR, "_live_now_gw-6f9531df.json"), "w", encoding="utf-8").write(
    json.dumps(back, ensure_ascii=False, indent=1))
print("\n✔ 已写回")
