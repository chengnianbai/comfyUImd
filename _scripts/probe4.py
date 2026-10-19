import json
import socket
import urllib.error
import urllib.request

socket.setdefaulttimeout(30)
UA = {"User-Agent": "Mozilla/5.0"}
REPO = "digiplay/majicMIX_realistic_v7"


def try_get(url, label, headers=None, method="GET"):
    req = urllib.request.Request(url, headers=dict(UA, **(headers or {})), method=method)
    try:
        with urllib.request.urlopen(req) as r:
            body = r.read(400)
            print("[%3d] %-40s %s" % (r.status, label, body[:120].decode("utf-8", "replace").replace("\n", " ")))
            return body
    except urllib.error.HTTPError as e:
        print("[%3d] %-40s %s" % (e.code, label, e.read(120).decode("utf-8", "replace").replace("\n", " ")[:110]))
    except Exception as e:
        print("[ERR] %-40s %s" % (label, str(e)[:90]))
    return None


print("=== A. gh-proxy 能否取 HF 上的普通文件（非 LFS）===")
try_get("https://gh-proxy.com/https://huggingface.co/%s/resolve/main/README.md" % REPO, "README.md (非LFS)")

print()
print("=== B. gh-proxy 能否取 LFS 大文件 ===")
try_get("https://gh-proxy.com/https://huggingface.co/%s/resolve/main/majicmixRealistic_v7.safetensors" % REPO, "safetensors 不带 Range")

print()
print("=== C. 通过 API 查文件真实大小 ===")
b = try_get("https://gh-proxy.com/https://huggingface.co/api/models/%s?blobs=true" % REPO, "API blobs=true")
if b:
    try:
        d = json.loads(b if isinstance(b, str) else b.decode("utf-8", "replace"))
        for s in d.get("siblings", []):
            if s.get("rfilename", "").endswith(".safetensors") and "/" not in s["rfilename"]:
                print("      %s  = %s bytes (%.2f GB)" % (
                    s["rfilename"], s.get("size"), (s.get("size") or 0) / 1024 / 1024 / 1024))
    except Exception as e:
        print("      解析失败:", e)

print()
print("=== D. 魔搭 API 变体 ===")
try_get("https://modelscope.cn/api/v1/models?PageSize=5", "列表(不带Name)")
try_get("https://modelscope.cn/api/v1/models?PageSize=5&Name=majicmix&SortBy=Downloads", "列表(带Name)")
req = urllib.request.Request(
    "https://modelscope.cn/api/v1/dolphin/models",
    data=json.dumps({"PageSize": 10, "PageNumber": 1, "Name": "majicmix", "SortBy": "Default"}).encode(),
    headers=dict(UA, **{"Content-Type": "application/json"}), method="POST")
try:
    with urllib.request.urlopen(req) as r:
        print("[%3d] POST dolphin/models  %s" % (r.status, r.read(300).decode("utf-8", "replace")[:250]))
except Exception as e:
    print("[ERR] POST dolphin/models  %s" % str(e)[:110])
