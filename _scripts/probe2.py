import os
import socket
import urllib.request

socket.setdefaulttimeout(20)

TEST_URLS = [
    ("https://www.baidu.com/", "baidu"),
    ("https://mirrors.ustc.edu.cn/", "USTC 镜像"),
    ("https://mirrors.aliyun.com/", "阿里云镜像"),
    ("https://gh-proxy.com/", "gh-proxy"),
    ("https://hf-mirror.com/", "hf-mirror"),
    ("https://civitai.com/", "civitai"),
    ("https://modelscope.cn/", "魔搭 modelscope"),
    ("https://www.modelscope.cn/api/v1/models?PageSize=1", "魔搭 API"),
]


def probe(url, label, use_proxy):
    if use_proxy:
        opener = urllib.request.build_opener()
    else:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with opener.open(req) as r:
            n = len(r.read(4096))
            print("  [OK ] %-26s %s" % (label, "读到数据"))
            return True
    except Exception as e:
        print("  [ERR] %-26s %s: %s" % (label, type(e).__name__, str(e)[:90]))
        return False


print("=== 走沙箱代理 ===")
for u, l in TEST_URLS:
    probe(u, l, True)

print()
print("=== 不走代理（直连） ===")
for u, l in TEST_URLS:
    probe(u, l, False)
