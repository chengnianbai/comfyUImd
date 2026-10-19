# -*- coding: utf-8 -*-
"""对照实验：把「两个基图」合并成一个（基图 = SDXL 生成的正脸）—— 只改提交内容，不写工作流

现状（两个基图，质量差 2.2 倍）
    1027 LoadImage = wendeng_face_confirmed_00009.png   lapVar 106.92   ← Kontext 链的身份锚（旧架构遗留）
    1004 LoadImage = wendeng_face_base.png              lapVar 234.82   ← SDXL 链的基图（v23 认可稿）

本实验做的事（单变量）
    把 1028(FluxKontextImageScale) 的输入从 **1027** 改成 **1021（SDXL 正脸成品）**，
    1027 随之被依赖裁剪自动丢掉 —— 于是全链只剩**一个基图 = 1004**，
    其余一切都从「SDXL 生成的正脸」派生。

★ 必须对照的原因（你们 09-22 实测原话）
    「锚=干净正脸 → 干净但只转 ~3/4；锚 = 00009 → 真 90° 但脏」
    锚图同时在交换「干净」和「能否真转到 90°」，所以不能盲改，必须两版并排看。

用法：
    python _exp_anchor_front.py dry
    python _exp_anchor_front.py run
产物：_exp_0924/anchor_front/   （同时把当前线上版的三张也拉下来并排）
"""
import os, sys, io, ssl, json, time, uuid, urllib.request, urllib.parse
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
if not BASE:
    print("★ 先设 COMFY_BASE"); sys.exit(4)
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
ROOT = r"D:\xiaobai-claude code\comfyUImd"
OUTDIR = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "anchor_front")
WFNAME = "夜市百相簿-主工作流.json"
ENC = urllib.parse.quote(WFNAME, safe='')
MODE = sys.argv[1] if len(sys.argv) > 1 else "dry"
sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                        # noqa

def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()

print("=== 1) 拉线上现行版（只读）===")
wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
API, TITLES = build_api(wf)
print("  1027(身份锚).image = %r" % API["1027"]["inputs"]["image"])
print("  1004(SDXL基图).image = %r" % API["1004"]["inputs"]["image"])
print("  1028.Scale 现在取 = %s" % API["1028"]["inputs"]["image"])
print("  1021 = %s  %r" % (API["1021"]["class_type"], API["1021"]["inputs"]["filename_prefix"]))

# ---- 单变量：1028 的输入 1027 -> 1021 ----
A = json.loads(json.dumps(API))
A["1028"]["inputs"]["image"] = ["1021", 0]
print("\n=== 2) 改动（仅一处）===")
print("   1028.image  ['1027',0] -> ['1021',0]（SDXL 正脸成品）；1027 因无引用被裁剪自动丢弃")

# 输出改前缀，避免和线上版混在一起
MARK = "锚用SDXL正脸"
TARGETS = []
for nid, a in A.items():
    if a["class_type"] != "SaveImage":
        continue
    pfx = str(a["inputs"].get("filename_prefix", ""))
    if pfx.startswith("闻灯-脸部") and "成品" in pfx:
        a["inputs"]["filename_prefix"] = pfx + "-" + MARK
        TARGETS.append(nid)
print("\n=== 3) 目标输出 ===")
for t in sorted(TARGETS, key=lambda x: int(x)):
    print("   #%s  %s" % (t, A[t]["inputs"]["filename_prefix"]))

subg = {k: v for k, v in A.items() if k in deps(A, TARGETS)}
print("   裁剪后 %d 节点；采样器 %s" % (len(subg),
      sorted([k for k, v in subg.items() if v["class_type"] == "KSampler"], key=int)))
print("   确认 1027 已不在图内：%s ；1028 来源 = %s"
      % ("1027" not in subg, subg["1028"]["inputs"]["image"]))
if MODE == "dry":
    print("\n[dry] 未提交。"); sys.exit(0)

print("\n=== 4) 提交 ===")
res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 180).decode())
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:2000]); sys.exit(1)
pid = res["prompt_id"]; print("   prompt_id=%s" % pid)
done = None
for i in range(400):
    time.sleep(3)
    h = json.loads(raw("/history/" + pid, None, None, 60).decode('utf-8', 'replace'))
    if pid in h:
        st = h[pid].get("status", {})
        if st.get("status_str") == "error":
            for m in st.get("messages", []):
                if m[0] == "execution_error":
                    print("★ ERROR %s: %s" % (m[1].get("node_type"), m[1].get("exception_message", "")[:400]))
            sys.exit(1)
        done = h[pid].get("outputs", {}); print("   完成，约 %d 秒" % ((i + 1) * 3)); break
if done is None:
    print("★ 超时"); sys.exit(1)

os.makedirs(OUTDIR, exist_ok=True)
print("\n=== 5) 下载两版（新：锚=SDXL正脸 / 旧：锚=00009）===")
for nid, o in done.items():
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        p = os.path.join(OUTDIR, im["filename"])
        open(p, "wb").write(raw("/view?" + q, None, None, 300))
        print("   [新] %-56s %7.1f KB" % (im["filename"], os.path.getsize(p) / 1024))
# 旧版（线上已产出的三张）
CUR = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图/_exp_0924/final")
for fn in ("闻灯-脸部正面-成品_00011_.png", "闻灯-脸部左侧-成品_00001_.png", "闻灯-脸部右侧-成品_00001_.png"):
    src = os.path.join(CUR, fn)
    if os.path.exists(src):
        open(os.path.join(OUTDIR, "旧_" + fn), "wb").write(open(src, "rb").read())
        print("   [旧] %-56s 已复制" % fn)
print("\n产物 -> %s" % OUTDIR)
