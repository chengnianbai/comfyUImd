import json
import socket
import urllib.error
import urllib.request

socket.setdefaulttimeout(25)


def get(url, label, show_body=False):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req) as r:
            data = r.read()
            print("[OK ] %-42s %8d bytes" % (label, len(data)))
            if show_body:
                print(data[:600].decode("utf-8", "replace"))
            return data
    except Exception as e:
        print("[ERR] %-42s %s: %s" % (label, type(e).__name__, str(e)[:120]))
        return None


print("=== 连通性探测 ===")
get("https://hf-mirror.com/", "hf-mirror.com 首页")
get("https://huggingface.co/", "huggingface.co 首页")
get("https://civitai.com/api/v1/models?limit=1", "civitai.com API")
get("https://civitai.com/", "civitai.com 首页")

print()
print("=== 在 HuggingFace 找 majicMIX ===")
for src in ("https://hf-mirror.com", "https://huggingface.co"):
    raw = get(src + "/api/models?search=majicmix&limit=100", src + " 搜索 majicmix")
    if not raw:
        continue
    try:
        items = json.loads(raw)
    except Exception as e:
        print("  解析失败:", e)
        continue
    print("  共 %d 个仓库：" % len(items))
    for it in items:
        print("   - %-52s downloads=%-8s gated=%s" % (
            it.get("modelId") or it.get("id"),
            it.get("downloads", 0),
            it.get("gated", False),
        ))
    break
