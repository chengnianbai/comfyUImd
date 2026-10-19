# -*- coding: utf-8 -*-
"""关机前收尾检查（全部只读）：
  1) 服务器上还有没有排队/执行中的任务（关了会中断）
  2) output/ 里有没有还没拉回本地的产物
  3) 本地是否留有服务器版工作流快照
"""
import json, os, ssl, urllib.request

BASE = os.environ.get(
    "COMFY_BASE",
    "https://gw-efb56d453d484597a1b8ddfc86156262.cn-beijing.aigclinks.com:8016",
)
_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE


def jget(p, timeout=60):
    r = urllib.request.urlopen(urllib.request.Request(BASE + p), timeout=timeout, context=_ctx)
    return json.loads(r.read().decode("utf-8", "replace"))


print("=" * 72)
print("关机前收尾检查")
print("=" * 72)

# 1) 队列
try:
    q = jget("/queue")
    run = len(q.get("queue_running", []))
    pend = len(q.get("queue_pending", []))
    print("\n[1] 队列：执行中 %d / 排队 %d  -> %s"
          % (run, pend, "空闲，可关" if run + pend == 0 else "★ 有任务在跑，关了会中断！"))
except Exception as e:
    print("\n[1] 队列查询失败：%s" % type(e).__name__)

# 2) output 清单
try:
    files = jget("/internal/files/output", 120)
    if isinstance(files, dict):
        files = files.get("files") or files.get("data") or []
    names = [f if isinstance(f, str) else (f.get("name") or f.get("path") or str(f)) for f in files]
    print("\n[2] 服务器 output/ 共 %d 项，最近 12 项：" % len(names))
    for n in names[-12:]:
        print("    %s" % n)
except Exception as e:
    print("\n[2] output 清单失败：%s" % type(e).__name__)

# 3) 本地工作流快照
print("\n[3] 本地工作流快照：")
for d in ("_scripts/_wf", "工作流"):
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", d)
    p = os.path.normpath(p)
    if os.path.isdir(p):
        fs = sorted(os.listdir(p))
        print("    %s/  (%d 项) 最新: %s" % (d, len(fs), fs[-3:] if fs else "-"))
    else:
        print("    %s/ 不存在" % d)
