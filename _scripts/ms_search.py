import json
import socket
import urllib.parse
import urllib.request

socket.setdefaulttimeout(25)
UA = {"User-Agent": "Mozilla/5.0"}


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


CANDIDATE_APIS = [
    ("旧版搜索", "https://modelscope.cn/api/v1/models?PageSize=20&PageNumber=1&Name={kw}"),
    ("新版搜索", "https://www.modelscope.cn/api/v1/dolphin/models?PageSize=20&PageNumber=1&Name={kw}"),
    ("通用搜索", "https://modelscope.cn/api/v1/models?PageSize=20&PageNumber=1&SortBy=Default&Name={kw}"),
]

for keyword in ("majicmix", "majicMIX realistic"):
    print("=" * 60)
    print("关键词:", keyword)
    kw = urllib.parse.quote(keyword)
    for label, tpl in CANDIDATE_APIS:
        url = tpl.format(kw=kw)
        try:
            d = fetch(url)
        except Exception as e:
            print("  [ERR] %-8s %s" % (label, str(e)[:100]))
            continue
        models = None
        if isinstance(d, dict):
            data = d.get("Data") or d.get("data") or {}
            if isinstance(data, dict):
                models = data.get("Models") or data.get("models")
            elif isinstance(data, list):
                models = data
        if not models:
            print("  [空 ] %-8s keys=%s" % (label, list(d)[:6] if isinstance(d, dict) else type(d)))
            continue
        print("  [OK ] %-8s 共 %d 条" % (label, len(models)))
        for m in models:
            if isinstance(m, dict):
                print("      - %s/%s  (%s)" % (
                    m.get("Path") or m.get("Namespace") or "?",
                    m.get("Name") or "?",
                    m.get("ChineseName") or "",
                ))
        break
