import socket
import sys
import urllib.request

socket.setdefaulttimeout(30)
UA = {"User-Agent": "Mozilla/5.0"}

MIRRORS = {
    "gh-proxy": "https://gh-proxy.com/https://huggingface.co",
    "ghfast": "https://ghfast.top/https://huggingface.co",
}
REPO = "digiplay/majicMIX_realistic_v7"
FILE = "majicmixRealistic_v7.safetensors"

for name, base in MIRRORS.items():
    url = "%s/%s/resolve/main/%s" % (base, REPO, FILE)
    req = urllib.request.Request(url, headers=UA, method="GET")
    req.add_header("Range", "bytes=0-1023")
    try:
        with urllib.request.urlopen(req) as r:
            head = r.read(64)
            cr = r.headers.get("Content-Range") or ""
            total = cr.split("/")[-1] if "/" in cr else r.headers.get("Content-Length")
            print("[OK ] %-9s status=%s  总大小=%s  首字节=%s" % (
                name, r.status, total, head[:8].hex()))
    except Exception as e:
        print("[ERR] %-9s %s" % (name, str(e)[:110]))
