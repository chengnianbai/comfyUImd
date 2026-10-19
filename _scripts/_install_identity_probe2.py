# -*- coding: utf-8 -*-
"""第二步：找 Manager 模型清单里的真实条目（InstantID / IP-Adapter / insightface）+ 确认安装端点"""
import ssl, json, sys, os, re, urllib.request, urllib.error
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE


def req(p, data=None, t=180, ctype="application/json"):
    r = urllib.request.Request(BASE + p, data=data)
    if data is not None:
        r.add_header("Content-Type", ctype)
    return urllib.request.urlopen(r, timeout=t, context=ctx).read()


print("=== 1) 找 Manager 的模型清单端点 ===")
CAND = ["/api/manager/model_list", "/api/manager/getmodel?mode=cache", "/api/manager/mode_list",
        "/api/manager/queue/status", "/externalmodel/getlist?mode=cache", "/api/manager/model_list.json"]
got = None
for p in CAND:
    try:
        r = req(p, None, 120)
        s = r.decode('utf-8', 'replace')
        keys = [k for k in ("instantid", "ipadapter", "ip-adapter", "insightface", "antelope")
                if k in s.lower()]
        print("  %-42s %8d 字节 ；命中 %s" % (p, len(s), keys or "无"))
        if keys and got is None:
            got = (p, s)
    except urllib.error.HTTPError as e:
        print("  %-42s HTTP %s" % (p, e.code))
    except Exception as e:
        print("  %-42s ERR %s" % (p, type(e).__name__))

if got:
    p, s = got
    print("\n=== 2) 从 %s 里提取相关条目 ===" % p)
    try:
        d = json.loads(s)
    except Exception:
        d = None
        print("  （非 JSON，改用文本抓取）")
    def show(obj, depth=0):
        pass
    if isinstance(d, dict):
        flat = []
        def walk(o, path=""):
            if isinstance(o, dict):
                for k, v in o.items():
                    walk(v, path + "/" + str(k))
            elif isinstance(o, list):
                for v in o:
                    walk(v, path)
            else:
                flat.append((path, o))
        walk(d)
        seen = set()
        for path, val in flat:
            sv = str(val)
            if any(k in sv.lower() for k in ("instantid", "ipadapter", "ip-adapter", "antelope", "insightface")):
                key = (path.split('/')[1] if len(path.split('/')) > 1 else path)
                if key in seen: continue
                seen.add(key)
                print("   %-34s %s" % (key, sv[:150]))
    else:
        for line in s.splitlines():
            if re.search(r"instantid|ip-?adapter|antelope|insightface", line, re.I):
                print("   %s" % line[:220])

print("\n=== 3) 确认安装端点（用 POST 而不是 GET）===")
for p, payload in (("/api/manager/queue/install_model", b"{}"),):
    try:
        req(p, payload, 60)
        print("  %-42s POST OK" % p)
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', 'replace')[:300]
        print("  %-42s POST HTTP %s  %s" % (p, e.code, body))
    except Exception as e:
        print("  %-42s POST ERR %s" % (p, type(e).__name__))
print("\n(只探测，未安装、未下载)")
