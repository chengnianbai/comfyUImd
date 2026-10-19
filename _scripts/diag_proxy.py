import os
import socket

print("=== 代理相关环境变量 ===")
keys = [k for k in os.environ if "proxy" in k.lower()]
if not keys:
    print("(无)")
for k in sorted(keys):
    print("  %s = %s" % (k, os.environ[k]))
print()
print("=== 其他可能相关的环境变量 ===")
for k in ("HF_ENDPOINT", "HF_HOME", "GIT_SSL_NO_VERIFY", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"):
    if k in os.environ:
        print("  %s = %s" % (k, os.environ[k]))
print()

print("=== 常见本地代理端口探测 ===")
ports = [7890, 7891, 7897, 10809, 10808, 1080, 8080, 8888, 33210, 4780, 2080]
for p in ports:
    s = socket.socket()
    s.settimeout(0.6)
    r = s.connect_ex(("127.0.0.1", p))
    s.close()
    if r == 0:
        print("  [开放] 127.0.0.1:%d" % p)
print()

print("=== pip / git 配置里的代理 ===")
for path in (
    os.path.expanduser("~/.pip/pip.conf"),
    os.path.expanduser("~/pip/pip.ini"),
    os.path.join(os.environ.get("APPDATA", ""), "pip", "pip.ini"),
):
    if os.path.isfile(path):
        print("  --- %s ---" % path)
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            print("  " + f.read().strip().replace("\n", "\n  "))
