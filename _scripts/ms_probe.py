import json
import socket
import urllib.error
import urllib.request

socket.setdefaulttimeout(20)
UA = {"User-Agent": "Mozilla/5.0"}


def code(url):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read(200)
    except urllib.error.HTTPError as e:
        return e.code, e.read(150)
    except Exception as e:
        return -1, str(e)[:80].encode()


print("=== 1. 确认魔搭 API 对查询字符串的处理 ===")
for label, u in [
    ("detail 无参数", "https://modelscope.cn/api/v1/models/Qwen/Qwen2.5-7B-Instruct"),
    ("detail 带参数", "https://modelscope.cn/api/v1/models/Qwen/Qwen2.5-7B-Instruct?Revision=master"),
    ("files 带参数", "https://modelscope.cn/api/v1/models/Qwen/Qwen2.5-7B-Instruct/repo/files?Revision=master&Recursive=true"),
]:
    c, b = code(u)
    print("  [%3s] %-16s %s" % (c, label, b[:100].decode("utf-8", "replace").replace("\n", " ")))

print()
print("=== 2. 试下载一个已知文件，确认魔搭下载通道 ===")
c, b = code("https://modelscope.cn/api/v1/models/Qwen/Qwen2.5-7B-Instruct/repo?Revision=master&FilePath=README.md")
print("  [%3s] 下载 README.md -> %s" % (c, b[:100].decode("utf-8", "replace").replace("\n", " ")))

print()
print("=== 3. 穷举 majicMIX 在魔搭的可能仓库名 ===")
namespaces = ["AI-ModelScope", "majicMIX", "Merjic", "merjic", "majicmix",
              "stable-diffusion-models", "modelscope", "iic", "damo"]
names = ["majicMIX_realistic_v7", "majicmixRealistic_v7", "majicMIX-realistic-v7",
         "majicmixrealistic_v7", "majicMIX_realistic", "majicmixRealistic",
         "majicMIX_realistic_v6", "MajicMIX_realistic_v7", "majicmix_realistic_v7"]
hits = []
for ns in namespaces:
    for nm in names:
        u = "https://modelscope.cn/api/v1/models/%s/%s" % (ns, nm)
        c, b = code(u)
        if c == 200:
            try:
                d = json.loads(b.decode("utf-8", "replace"))
                print("  [命中] %s/%s  %s" % (ns, nm, (d.get("Data") or {}).get("ChineseName", "")))
            except Exception:
                print("  [命中] %s/%s" % (ns, nm))
            hits.append("%s/%s" % (ns, nm))
print("  命中数：%d" % len(hits))
