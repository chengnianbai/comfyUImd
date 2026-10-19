import socket
import urllib.error
import urllib.request

socket.setdefaulttimeout(20)
UA = {"User-Agent": "Mozilla/5.0"}

TESTS = [
    ("已知仓库详情(不带www)", "https://modelscope.cn/api/v1/models/Qwen/Qwen2.5-7B-Instruct"),
    ("已知仓库详情(带www)", "https://www.modelscope.cn/api/v1/models/Qwen/Qwen2.5-7B-Instruct"),
    ("已知仓库文件列表", "https://modelscope.cn/api/v1/models/Qwen/Qwen2.5-7B-Instruct/repo/files?Revision=master"),
    ("gh-proxy 代理HF搜索", "https://gh-proxy.com/https://huggingface.co/api/models?search=majicmix"),
    ("gh-proxy 直取HF文件", "https://gh-proxy.com/https://huggingface.co/digplay/majicMIX_realistic_v7/resolve/main/README.md"),
    ("USTC 镜像探路", "https://mirrors.ustc.edu.cn/"),
]

for label, url in TESTS:
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req) as r:
            body = r.read(300)
            print("[%3d] %-26s %s" % (r.status, label, body[:160].decode("utf-8", "replace").replace("\n", " ")))
    except urllib.error.HTTPError as e:
        print("[%3d] %-26s %s" % (e.code, label, e.read(200).decode("utf-8", "replace").replace("\n", " ")[:160]))
    except Exception as e:
        print("[ERR] %-26s %s" % (label, str(e)[:90]))
