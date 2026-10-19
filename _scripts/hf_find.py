import json
import socket
import urllib.request

socket.setdefaulttimeout(30)
UA = {"User-Agent": "Mozilla/5.0"}
GH = "https://gh-proxy.com/https://huggingface.co"


def hf(path):
    req = urllib.request.Request(GH + path, headers=UA)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


for kw in ("majicmix", "majicMIX realistic"):
    print("=" * 70)
    print("HF 搜索:", kw)
    try:
        items = hf("/api/models?search=%s&limit=100" % urllib.parse.quote(kw) if False else
                   "/api/models?search=" + kw.replace(" ", "%20") + "&limit=100")
    except Exception as e:
        print("  ERR", str(e)[:120])
        continue
    for it in items:
        print("  %-46s dl=%-8s likes=%-5s gated=%s" % (
            it.get("id"), it.get("downloads", 0), it.get("likes", 0), it.get("gated", False)))


print()
print("=" * 70)
print("候选仓库的文件清单")
CANDIDATES = ["merjic4044/majicMIX", "digiplay/majicMIX_realistic_v7",
              "digiplay/majicMIX_realistic_v6", "Yntec/majicMIXrealistic"]
for repo in CANDIDATES:
    try:
        info = hf("/api/models/" + repo)
    except Exception as e:
        print("  [ERR] %-42s %s" % (repo, str(e)[:80]))
        continue
    sibs = info.get("siblings") or []
    names = [s.get("rfilename") for s in sibs]
    print("  [OK ] %-42s 文件 %d 个" % (repo, len(names)))
    for n in names:
        if n.lower().endswith((".safetensors", ".ckpt", ".pt", ".bin")):
            print("         - %s" % n)
