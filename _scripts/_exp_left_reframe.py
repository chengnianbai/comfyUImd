# -*- coding: utf-8 -*-
"""左脸词「重拍框架」实验跑图器 —— **只改提交内容，绝不写服务器工作流**

为什么不用 run_wf.py 直接跑：
    线上工作流文件里的 1031 还是**被截断的旧词**（用户在浏览器里改的那版没存进文件），
    所以必须由本地覆盖 1031 的 text 再提交；同时这样也**完全不碰**用户的工作流文件。

用法：
    set COMFY_BASE=https://gw-xxxx.cn-beijing.aigclinks.com:8016
    python _exp_left_reframe.py dry                 # 只构建+校验，不提交（零成本）
    python _exp_left_reframe.py run [输出目录]        # 提交并下载

单变量开关：
    --anchor-front   把 1033(左脸身份锚) 从 1029(00009原图) 换成 1050(正脸成品 latent)
    --seed 20260921  改 1034 的 seed
    --guidance 4.0   改 1032 的 guidance
"""
import os, sys, ssl, json, time, uuid, io, urllib.request, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wf_api import build_api, deps, WIDGETS

BASE = os.environ["COMFY_BASE"].rstrip("/")
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"D:\xiaobai-claude code\comfyUImd"
WFNAME = "夜市百相簿-主工作流.json"
PROMPT_FILE = os.path.join(HERE, "_wf", "left_prompt_reframe_v1.txt")

MODE = sys.argv[1] if len(sys.argv) > 1 else "dry"
OUTDIR = (sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--")
          else os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0922", "e6_reframe_v1"))
ANCHOR_FRONT = "--anchor-front" in sys.argv
SEED = None
GUID = None
for i, a in enumerate(sys.argv):
    if a == "--seed":
        SEED = int(sys.argv[i + 1])
    if a == "--guidance":
        GUID = float(sys.argv[i + 1])

TOKENS = ["闻灯主图-左侧脸", "闻灯主图-右侧脸"]


def raw(p, data=None, ctype=None, timeout=180):
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
_unsup = sorted({n["type"] for n in wf["nodes"] if n["type"] not in WIDGETS})
if _unsup:
    print("  ⚠️ 未登记节点类型：%s" % _unsup)

# ---- 本地覆盖 ----
new_text = io.open(PROMPT_FILE, encoding="utf-8").read().rstrip("\n")
old_text = API["1031"]["inputs"]["text"]
changes = []
changes.append("1031.text  %d -> %d 字符" % (len(old_text), len(new_text)))
API["1031"]["inputs"]["text"] = new_text
if ANCHOR_FRONT:
    API["1033"]["inputs"]["latent"] = ["1050", 0]
    changes.append("1033.latent  1029(00009原图) -> 1050(正脸成品 latent)")
if SEED is not None:
    API["1034"]["inputs"]["seed"] = SEED
    changes.append("1034.seed -> %d" % SEED)
if GUID is not None:
    API["1032"]["inputs"]["guidance"] = GUID
    changes.append("1032.guidance -> %s" % GUID)

print("\n=== 2) 本次相对线上的改动（仅这些）===")
for c in changes:
    print("   ·", c)

# ---- 裁剪到目标分支 ----
targets = []
for nid, a in API.items():
    if a["class_type"] != "SaveImage":
        continue
    pfx = str(a["inputs"].get("filename_prefix", ""))
    if any(t in pfx for t in TOKENS) and pfx.endswith("成品"):
        targets.append(nid)
print("\n=== 3) 目标分支 ===")
for nid in targets:
    print("   ✔ %s  %s" % (nid, API[nid]["inputs"]["filename_prefix"]))
keep = deps(API, targets)
sub = {k: v for k, v in API.items() if k in keep}
print("   裁剪后 %d 节点" % len(sub))
for k in ("1027", "1031", "1032", "1033", "1034", "1051", "1052"):
    if k in sub:
        a = sub[k]
        ins = {kk: vv for kk, vv in a["inputs"].items() if kk != "text"}
        print("   %-5s %-20s %s" % (k, a["class_type"], json.dumps(ins, ensure_ascii=False)))
        if "text" in a["inputs"]:
            print("         text(%d) 开头=%r" % (len(a["inputs"]["text"]), a["inputs"]["text"][:60]))

io.open(os.path.join(HERE, "_wf", "_last_submit.json"), "w", encoding="utf-8").write(
    json.dumps(sub, ensure_ascii=False))
print("\n   提交内容已存 _scripts/_wf/_last_submit.json")

if MODE == "dry":
    print("\n[dry] 未提交。加 run 才真正跑图。")
    sys.exit(0)

print("\n=== 4) 提交 ===")
res = json.loads(raw("/prompt", json.dumps({"prompt": sub, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 120).decode())
if res.get("node_errors"):
    print("  ★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:3000])
    sys.exit(1)
pid = res["prompt_id"]
print("  prompt_id =", pid)

print("\n=== 5) 等待 ===")
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
        print("  完成，用时约 %d 秒" % ((i + 1) * 5)); break
if done is None:
    print("  ★ 超时"); sys.exit(1)

os.makedirs(OUTDIR, exist_ok=True)
print("\n=== 6) 下载 -> %s ===" % OUTDIR)
for nid, o in done.items():
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        data = raw("/view?" + q, None, None, 300)
        open(os.path.join(OUTDIR, im["filename"]), "wb").write(data)
        print("  saved %-46s %8.1f KB" % (im["filename"], len(data) / 1024))
print("\nOK")
