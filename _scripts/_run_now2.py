# -*- coding: utf-8 -*-
"""确认线上状态 → 跑一次三视图 → 把内眼角放大出来供检查

会先核对：
  · 1004.image 现在指向哪个文件
  · input 目录里有哪些 wendeng_* 图
  · 服务器上的 wendeng_face_base.png 与我上次备份的 base_original.png 是否还是同一张（md5）
    —— 若不同，说明基图已被换过（那正好），跑出来的结果就该是干净的
"""
import os, sys, io, ssl, json, hashlib, time, uuid, urllib.request, urllib.parse
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
from PIL import Image, ImageDraw

BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
if not BASE:
    print("★ 先设 COMFY_BASE"); sys.exit(4)
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
ROOT = r"D:\xiaobai-claude code\comfyUImd"
BR = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "base_repair")
RD = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "run_now2")
SC = r"C:\Users\ADMINI~1\AppData\Local\Temp\commandcode\D--xiaobai-claude-code-comfyUImd\df01e59d-0f96-4c37-9495-d9508dda8d9a\scratchpad"
WFNAME = "夜市百相簿-主工作流.json"
ENC = urllib.parse.quote(WFNAME, safe='')
sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                        # noqa


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


def md5(b): return hashlib.md5(b).hexdigest()[:12]

print("=== 1) 线上状态 ===")
wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
byid = {n["id"]: n for n in wf["nodes"]}
print("  1004.image = %r" % (byid[1004].get("widgets_values") or [None])[0])
print("  nodes=%d links=%d groups=%d" % (len(wf["nodes"]), len(wf["links"]), len(wf.get("groups", []))))
try:
    d = json.loads(raw("/object_info/LoadImage", 180).decode('utf-8', 'replace'))
    opts = d["LoadImage"]["input"]["required"]["image"][0]
    print("  input 目录里的图：%s" % [x for x in opts if "wendeng" in str(x)])
except Exception as e:
    print("  列 input 失败", type(e).__name__)

print("\n=== 2) 基图是否被换过（与本机备份比 md5）===")
local = os.path.join(BR, "base_original.png")
if os.path.exists(local):
    lm = md5(open(local, "rb").read())
    try:
        q = urllib.parse.urlencode({"filename": "wendeng_face_base.png", "subfolder": "", "type": "input"})
        b = raw("/view?" + q, None, None, 300)
        sm = md5(b)
        print("  本机备份 md5=%s   线上现状 md5=%s   %s"
              % (lm, sm, "★ 已不同（基图被换过）" if lm != sm else "相同（未换）"))
        p = os.path.join(BR, "base_from_server_now.png"); open(p, "wb").write(b)
    except Exception as e:
        print("  取线上基图失败", type(e).__name__)

print("\n=== 3) 跑一次三视图 ===")
API, _ = build_api(wf)
TARGETS = [nid for nid, a in API.items()
           if a["class_type"] == "SaveImage" and str(a["inputs"].get("filename_prefix", "")).startswith("闻灯-脸部")]
print("  目标：%s" % [API[t]["inputs"]["filename_prefix"] for t in TARGETS])
subg = {k: v for k, v in API.items() if k in deps(API, TARGETS)}
res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 180).decode())
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:1500]); sys.exit(1)
pid = res["prompt_id"]; print("  prompt_id=%s" % pid)
done = None
for i in range(400):
    time.sleep(3)
    h = json.loads(raw("/history/" + pid, None, None, 60).decode('utf-8', 'replace'))
    if pid in h:
        st = h[pid].get("status", {})
        if st.get("status_str") == "error":
            for m in st.get("messages", []):
                if m[0] == "execution_error":
                    print("★ ERROR %s: %s" % (m[1].get("node_type"), m[1].get("exception_message", "")[:300]))
            sys.exit(1)
        done = h[pid].get("outputs", {}); print("  完成，约 %d 秒" % ((i + 1) * 3)); break
if done is None: print("★ 超时"); sys.exit(1)
os.makedirs(RD, exist_ok=True)
front = None
for nid, o in done.items():
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        p = os.path.join(RD, im["filename"]); open(p, "wb").write(raw("/view?" + q, None, None, 300))
        print("   saved %-46s %7.1f KB" % (im["filename"], os.path.getsize(p) / 1024))
        if "正面" in im["filename"]: front = p

if front:
    im = Image.open(front).convert("RGB"); w, h = im.size
    c = im.crop((int(w*0.16), int(h*0.24), int(w*0.86), int(h*0.54)))
    Z = 3
    big = c.resize((c.size[0]*Z, c.size[1]*Z), Image.LANCZOS)
    o = os.path.join(RD, "_正脸眼部放大-x3.png"); big.save(o)
    big.resize((900, int(900*big.size[1]/big.size[0])), Image.LANCZOS).save(os.path.join(SC, "now_eye.png"), optimize=True)
    print("\nsaved", o, big.size)
print("产物 -> %s" % RD)
