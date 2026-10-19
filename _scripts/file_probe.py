import socket
import urllib.error
import urllib.request

socket.setdefaulttimeout(30)
UA = {"User-Agent": "Mozilla/5.0"}

REPO = "digiplay/majicMIX_realistic_v7"
FILE = "majicmixRealistic_v7.safetensors"

TARGETS = [
    ("hf-mirror", "https://hf-mirror.com/%s/resolve/main/%s" % (REPO, FILE)),
    ("aifasthub", "https://aifasthub.com/%s/resolve/main/%s" % (REPO, FILE)),
    ("aifasthub /models", "https://aifasthub.com/models/%s/resolve/main/%s" % (REPO, FILE)),
]

print("=== 走环境代理，取前 1KB 试探 ===")
for name, url in TARGETS:
    req = urllib.request.Request(url, headers=dict(UA, Range="bytes=0-1023"))
    try:
        with urllib.request.urlopen(req) as r:
            head = r.read(16)
            cr = r.headers.get("Content-Range", "")
            print("[%3d] %-16s 状态=%s Content-Range=%s 首字节=%s" % (
                r.status, name, r.status, cr, head[:8].hex()))
    except urllib.error.HTTPError as e:
        print("[%3d] %-16s %s" % (e.code, name, e.read(120).decode("utf-8", "replace")[:110]))
    except Exception as e:
        print("[ERR] %-16s %s" % (name, str(e)[:100]))
