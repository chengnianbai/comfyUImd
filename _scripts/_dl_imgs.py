# -*- coding: utf-8 -*-
"""拉回指定产物到本地诊断目录"""
import os, ssl, sys, json, urllib.request, urllib.parse

BASE = os.environ["COMFY_BASE"].rstrip("/")
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
OUT = r"D:\xiaobai-claude code\comfyUImd\系列-夜市百相簿\02-角色\闻灯\设定图\_diag_2style"
os.makedirs(OUT, exist_ok=True)

names = sys.argv[1:] or [
    "闻灯Kontext统一正脸-成品_00026_.png",
    "闻灯主图-左侧脸-成品_00040_.png",
    "闻灯主图-左侧脸-成品_00041_.png",
    "闻灯主图-左侧脸-成品_00042_.png",
]
for fn in names:
    q = urllib.parse.urlencode({"filename": fn, "subfolder": "", "type": "output"})
    try:
        data = urllib.request.urlopen(BASE + "/view?" + q, timeout=300, context=ctx).read()
    except Exception as e:
        print("  FAIL %-46s %s" % (fn, e)); continue
    open(os.path.join(OUT, fn), "wb").write(data)
    print("  saved %-46s %8.1f KB" % (fn, len(data) / 1024))
print("->", OUT)
