# -*- coding: utf-8 -*-
"""决定性实验：参考图固定、只换种子 → 若脸随种子大变，证明 ReferenceLatent 没有承担身份

只跑「正面」那一条 Flux 分支（#1316），不碰其它节点、不写回。
用两个不同种子各出一张，再和已确认正脸母版并排。
"""
import os, sys, io, ssl, json, time, uuid, urllib.request, urllib.parse
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
ROOT = r"D:\xiaobai-claude code\comfyUImd"
OUT = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "seedtest")
ENC = urllib.parse.quote("夜市百相簿-主工作流.json", safe='')
os.makedirs(OUT, exist_ok=True)
FRONT_KS = "1316"          # 正面 Flux 采样器
SAVE_FRONT = "15"          # 闻灯-全身正面-成品


def raw(p, data=None, ctype=None, timeout=900):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                       # noqa
wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
API, _ = build_api(wf)
print("正面分支节点：#%s(采样) → 依赖 %d 个节点" % (FRONT_KS, len(deps(API, [FRONT_KS]))))
print("参考图节点 #1310 的值 =", API["1310"]["inputs"].get("image"))

for seed in (111111, 222222):
    need = deps(API, [FRONT_KS]) | deps(API, [SAVE_FRONT])
    sub = {k: json.loads(json.dumps(v)) for k, v in API.items() if k in need}
    sub[FRONT_KS]["inputs"]["seed"] = seed
    print("   提交 %d 节点，含存图=%s" % (len(sub), [k for k in sub if sub[k]["class_type"] == "SaveImage"]))
    try:
        res = json.loads(raw("/prompt", json.dumps({"prompt": sub, "client_id": str(uuid.uuid4())}).encode(),
                             "application/json", 180).decode())
    except urllib.error.HTTPError as e:
        print("★ HTTP %s 正文： %s" % (e.code, e.read().decode('utf-8', 'replace')[:1200])); sys.exit(1)
    if res.get("node_errors"):
        print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:900]); sys.exit(1)
    pid = res["prompt_id"]; print("\nseed=%d  prompt_id=%s" % (seed, pid))
    done = None
    for i in range(600):
        time.sleep(4)
        try:
            h = json.loads(raw("/history/" + pid, None, None, 60).decode('utf-8', 'replace'))
        except Exception:
            continue
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("status_str") == "error":
                for m in st.get("messages", []):
                    if m[0] == "execution_error":
                        print("★ ERROR %s: %s" % (m[1].get("node_type"), m[1].get("exception_message", "")[:300]))
                sys.exit(1)
            done = h[pid].get("outputs", {}); print("  完成，约 %d 秒" % ((i+1)*4)); break
    if done is None: print("★ 超时"); sys.exit(1)
    for nid, o in done.items():
        for im in o.get("images", []):
            q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                        "type": im.get("type", "output")})
            p = os.path.join(OUT, "seed%d_%s" % (seed, im["filename"]))
            open(p, "wb").write(raw("/view?" + q, None, None, 300))
            print("   saved %s" % os.path.basename(p))
print("\n[实验] 未写回工作流。")
