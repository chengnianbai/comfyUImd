"""在 hf-mirror 上搜 SD1.5 的细节/皮肤质感类 LoRA。"""
import json
import urllib.request
import urllib.parse

urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

QUERIES = [
    "detail tweaker",
    "detail lora sd15",
    "more details lora",
    "skin texture lora",
    "realistic skin lora",
    "add detail lora",
    "film grain lora",
    "portrait realism lora stable diffusion 1.5",
]


def api(path):
    url = "https://hf-mirror.com/api/" + path
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


seen = {}
for q in QUERIES:
    try:
        data = api("models?" + urllib.parse.urlencode({
            "search": q, "limit": 20, "full": "false", "sort": "downloads", "direction": "-1"
        }))
    except Exception as e:
        print("!! %-42s ERR %s %s" % (q, type(e).__name__, e))
        continue
    print("\n### 搜索词: %s   (%d 条)" % (q, len(data)))
    for m in data:
        mid = m.get("modelId") or m.get("id")
        dl = m.get("downloads", 0)
        tags = ",".join(m.get("tags", [])[:6])
        print("   %-58s dl=%-8s %s" % (mid, dl, tags))
        seen.setdefault(mid, 0)
        seen[mid] += dl

print("\n\n===== 汇总（按下载量）=====")
for mid, dl in sorted(seen.items(), key=lambda x: -x[1])[:25]:
    print("%-60s %s" % (mid, dl))
