import socket
import urllib.error
import urllib.request

socket.setdefaulttimeout(12)
UA = {"User-Agent": "Mozilla/5.0"}

HOSTS = [
    "https://modelscope.cn/",
    "https://www.modelscope.cn/",
    "https://gh-proxy.com/",
    "https://ghfast.top/",
    "https://ghproxy.net/",
    "https://gh.llkk.cc/",
    "https://hub.gitmirror.com/",
    "https://kkgithub.com/",
    "https://gitee.com/",
    "https://aliendao.cn/",
    "https://www.aliendao.cn/",
    "https://aifasthub.com/",
    "https://www.liblib.art/",
    "https://tusiart.com/",
    "https://hf-mirror.com/",
    "https://civitai.com/",
    "https://mirror.ghproxy.com/",
    "https://gitclone.com/",
    "https://www.gitclone.com/",
    "https://atomgit.com/",
]

ok, bad = [], []
for u in HOSTS:
    req = urllib.request.Request(u, headers=UA)
    try:
        with urllib.request.urlopen(req) as r:
            print("[%3d] %s" % (r.status, u))
            ok.append(u)
    except urllib.error.HTTPError as e:
        print("[%3d] %s" % (e.code, u))
        ok.append(u + "  (HTTP响应正常，可达)")
    except Exception as e:
        print("[ERR] %-34s %s" % (u, str(e)[:60]))
        bad.append(u)

print()
print("可达：")
for u in ok:
    print("  " + u)
