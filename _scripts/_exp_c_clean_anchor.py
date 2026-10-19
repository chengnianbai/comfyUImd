# -*- coding: utf-8 -*-
"""C 方案：把身份锚图换成「干净正脸」——**只改提交内容，绝不写服务器工作流**

思路：现在两条支路都从 00009（v13 旧稿：雀斑+胡茬+炸卷毛）出发，Kontext 忠实复刻它，
      所以正脸和侧脸一起脏。换成干净正脸当锚 → 整组质感跟着干净，
      代价是转头落 3/4（14:15 已实测过，用户已确认 3/4 可用）。

单变量：只改 1027(LoadImage).image，其余一个字节不动。
用法：
    python _exp_c_clean_anchor.py dry
    python _exp_c_clean_anchor.py run
可选：
    --src <图片路径>   换别的干净正脸（默认 00010）
    --name <服务器名>  上传后的文件名
"""
import os, sys, ssl, json, time, uuid, io, urllib.request, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wf_api import build_api, deps

BASE = os.environ["COMFY_BASE"].rstrip("/")
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"D:\xiaobai-claude code\comfyUImd"
WFNAME = "夜市百相簿-主工作流.json"

MODE = sys.argv[1] if len(sys.argv) > 1 else "dry"
OUTDIR = (sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--")
          else os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0923", "c1_clean_anchor"))

DEFAULT_SRC = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图/主工作流/闻灯Kontext统一正脸-成品_00010_.png")
ANCHOR_SRC = DEFAULT_SRC
ANCHOR_NAME = "wendeng_clean_front_00010.png"
for i, a in enumerate(sys.argv):
    if a == "--src":
        ANCHOR_SRC = sys.argv[i + 1]
    if a == "--name":
        ANCHOR_NAME = sys.argv[i + 1]

TOKENS = ["闻灯主图-左侧脸", "闻灯主图-右侧脸", "闻灯Kontext统一正脸"]


def raw(p, data=None, ctype=None, timeout=300):
    h = {}
    if ctype:
        h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


print("=== 1) 拉线上工作流（只读）===")
u = "/api/userdata/workflows%2F" + urllib.parse.quote(WFNAME)
wf = json.loads(raw(u, None, None, 60).decode("utf-8", "replace"))
print("  %s  节点 %d  链接 %d" % (WFNAME, len(wf["nodes"]), len(wf["links"])))

API, TITLES = build_api(wf)
_unsup = sorted({n["type"] for n in wf["nodes"] if n["type"] not in WIDGETS}) if False else []
print("  线上 1027.image = %r" % API["1027"]["inputs"].get("image"))
print("  线上 1031 词长度 = %d 字符（本次不动）" % len(API["1031"]["inputs"]["text"]))
print("  线上 1034 参数 = %s" % json.dumps({k: v for k, v in API["1034"]["inputs"].items()
                                             if k not in ("model", "positive", "negative", "latent")},
                                            ensure_ascii=False))

print("\n=== 2) 上传干净正脸 -> %s ===" % ANCHOR_NAME)
png = open(ANCHOR_SRC, "rb").read()
print("  源文件 %s  %.1f KB" % (os.path.basename(ANCHOR_SRC), len(png) / 1024))
B = "----wb" + uuid.uuid4().hex
body = io.BytesIO()


def part(s):
    body.write(s.encode("utf-8"))


part("--%s\r\n" % B)
part('Content-Disposition: form-data; name="image"; filename="%s"\r\n' % ANCHOR_NAME)
part("Content-Type: image/png\r\n\r\n")
body.write(png)
part("\r\n--%s\r\n" % B)
part('Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n')
part("--%s\r\n" % B)
part('Content-Disposition: form-data; name="subfolder"\r\n\r\n\r\n')
part("--%s--\r\n" % B)

up = json.loads(raw("/upload/image", body.getvalue(),
                    "multipart/form-data; boundary=%s" % B, 300).decode())
print("  上传返回:", json.dumps(up, ensure_ascii=False))
upname = up.get("name", ANCHOR_NAME)
sub = up.get("subfolder") or ""
served = (sub + "/" + upname) if sub else upname

changes = ["1027.image  %r -> %r" % (API["1027"]["inputs"].get("image"), served)]
API["1027"]["inputs"]["image"] = served

print("\n=== 3) 本次相对线上的改动（仅这些）===")
for c in changes:
    print("   ·", c)

print("\n=== 4) 目标分支 ===")
targets = []
for nid, a in API.items():
    if a["class_type"] != "SaveImage":
        continue
    pfx = str(a["inputs"].get("filename_prefix", ""))
    if any(t in pfx for t in TOKENS) and (pfx.endswith("成品")):
        targets.append(nid)
for nid in targets:
    print("   ✔ %s  %s" % (nid, API[nid]["inputs"]["filename_prefix"]))
keep = deps(API, targets)
subg = {k: v for k, v in API.items() if k in keep}
print("   裁剪后 %d 节点" % len(subg))

io.open(os.path.join(HERE, "_wf", "_last_submit_c1.json"), "w", encoding="utf-8").write(
    json.dumps(subg, ensure_ascii=False))

if MODE == "dry":
    print("\n[dry] 未提交。")
    sys.exit(0)

print("\n=== 5) 提交 ===")
res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 120).decode())
if res.get("node_errors"):
    print("  ★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:3000])
    sys.exit(1)
pid = res["prompt_id"]
print("  prompt_id =", pid)

print("\n=== 6) 等待 ===")
done = None
for i in range(180):
    time.sleep(5)
    h = json.loads(raw("/history/" + pid, None, None, 60).decode("utf-8", "replace"))
    if pid in h:
        st = h[pid].get("status", {})
        if st.get("status_str") == "error":
            for m in st.get("messages", []):
                if m[0] == "execution_error":
                    print("  ★ ERROR %s: %s" % (m[1].get("node_type"), m[1].get("exception_message", "")[:400]))
            sys.exit(1)
        done = h[pid].get("outputs", {})
        print("  完成，约 %d 秒" % ((i + 1) * 5)); break
if done is None:
    print("  ★ 超时"); sys.exit(1)

os.makedirs(OUTDIR, exist_ok=True)
print("\n=== 7) 下载 -> %s ===" % OUTDIR)
for nid, o in done.items():
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        data = raw("/view?" + q, None, None, 300)
        open(os.path.join(OUTDIR, im["filename"]), "wb").write(data)
        print("  saved %-46s %8.1f KB" % (im["filename"], len(data) / 1024))
print("\nOK")
