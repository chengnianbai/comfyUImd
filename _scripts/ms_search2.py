import json
import socket
import urllib.error
import urllib.request

socket.setdefaulttimeout(20)
UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def get(url, label, raw=False):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req) as r:
            body = r.read()
            print("  [OK ] %-44s %6d B" % (label, len(body)))
            if raw:
                return body
            try:
                return json.loads(body.decode("utf-8", "replace"))
            except Exception:
                return body.decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        print("  [%3d] %-44s" % (e.code, label))
    except Exception as e:
        print("  [ERR] %-44s %s" % (label, str(e)[:80]))
    return None


print("=== 1. 详情类 API（验证仓库是否存在）===")
guess = [
    "AI-ModelScope/majicmixRealistic_v7",
    "AI-ModelScope/majicMIX_realistic_v7",
    "AI-ModelScope/majicmixRealistic",
    "majicMIX/majicMIX_realistic",
    "AI-ModelScope/majicMIX-realistic",
    "Merjic/majicMIX_realistic_v7",
]
for g in guess:
    d = get("https://modelscope.cn/api/v1/models/%s" % g, "detail: " + g)
    if isinstance(d, dict):
        data = d.get("Data") or d.get("data") or {}
        print("        -> Name=%s  Downloads=%s" % (data.get("Name"), data.get("Downloads")))


print()
print("=== 2. 文件列表 API ===")
for g in guess[:2]:
    get("https://modelscope.cn/api/v1/models/%s/repo/files?Revision=master" % g, "files: " + g)


print()
print("=== 3. 搜索页 HTML（找线索）===")
html = get("https://modelscope.cn/models?name=majicmix", "搜索页 HTML", raw=True)
if html:
    txt = html.decode("utf-8", "replace")
    import re
    hits = sorted(set(re.findall(r"[A-Za-z0-9_\-]+/majic[A-Za-z0-9_\-]*", txt, re.I)))
    print("      页面中出现的仓库名候选:", hits[:20] if hits else "(无，可能是前端渲染)")
