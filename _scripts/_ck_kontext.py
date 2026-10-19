# -*- coding: utf-8 -*-
"""只读：查 Manager 下载队列状态 + 下载日志权威判据（Installation was successful / ENOSPC）。

不发任何会改变服务器状态的请求，不启动实例。
"""
import json, os, re, ssl, sys, urllib.request

BASE = os.environ.get(
    "COMFY_BASE",
    "https://gw-efb56d453d484597a1b8ddfc86156262.cn-beijing.aigclinks.com:8016",
)
_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE


def raw(p, timeout=180):
    return urllib.request.urlopen(urllib.request.Request(BASE + p), timeout=timeout, context=_ctx).read()


def jget(p, timeout=120):
    return json.loads(raw(p, timeout=timeout).decode("utf-8", "replace"))


print("=" * 72)
print("Kontext 下载状态（只读）")
print("=" * 72)

for ep in ("/api/manager/queue/status", "/api/manager/queue", "/manager/queue/status"):
    try:
        st = jget(ep, 60)
        print("\n[队列 %s]" % ep)
        print(json.dumps(st, ensure_ascii=False)[:900])
        break
    except Exception as e:
        print("  %s -> %s" % (ep, type(e).__name__))

try:
    E = json.loads(raw("/internal/logs/raw", 180).decode("utf-8", "replace"))["entries"]
except Exception as e:
    print("\n日志读取失败: %s" % type(e).__name__)
    sys.exit(1)

clean = lambda s: re.sub(r"\x1b\[[0-9;]*m", "", s).rstrip()
KEYS = ("Install model", "Download error", "No space", "Errno", "successful",
        "Queued works", "kontext", "Kontext", "schnell", "ae.safetensors")
hits = [e for e in E if any(k in clean(e["m"]) for k in KEYS)]
print("\n[日志最后 5 分钟内的相关条目]")
for e in hits[-25:]:
    print("   [%s] %s" % (e["t"][11:19], clean(e["m"])[:220]))

print("\n[日志总行数] %d，最早 %s，最新 %s"
      % (len(E), E[0]["t"][11:19] if E else "-", E[-1]["t"][11:19] if E else "-"))
