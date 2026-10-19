# -*- coding: utf-8 -*-
"""【闻灯】Flux 正脸基准 · 新脸候选批量生成

用户 2026-09-20：「不需要用 v23 正脸做基准图，我需要生成新的脸」
  → 走「正脸基准 T2I」支路（纯 Flux 文生图，无任何 v23 结构锚），
     一次提交多个不同 seed，拿回多张**全新的脸**供挑选。

用法：
    FACES=6 COMFY_BASE=https://gw-xxx:8016 python gen_face_candidates.py

只跑 T2I 支路的**草稿**（1024x1280，不做 4x 放大）—— 选脸阶段够用，最省时间。
"""
import copy
import json
import os
import ssl
import sys
import time
import urllib.parse
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from wf_api import build_api, deps          # noqa: E402

BASE = os.environ.get(
    "COMFY_BASE",
    "https://gw-efb56d453d484597a1b8ddfc86156262.cn-beijing.aigclinks.com:8016").rstrip("/")
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE

ROOT = r"D:\xiaobai-claude code\comfyUImd"
WFNAME = "夜市百相簿-主工作流.json"
TOKEN = os.environ.get("TOKEN", "闻灯正脸基准")
KIND = os.environ.get("KIND", "draft")
SUFFIX = "草稿" if KIND == "draft" else "成品"
OUTDIR = os.path.join(ROOT, "系列-夜市百相簿", "02-角色", "闻灯", "设定图",
                      "正脸基准-2026-09-20", "候选")
N = int(os.environ.get("FACES", "6"))
SEED0 = int(os.environ.get("SEED0", "20260920"))


def raw(p, data=None, ctype=None, timeout=180):
    h = {}
    if ctype:
        h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


print("=== 1) 拉工作流 ===")
u = "/api/userdata/workflows%2F" + urllib.parse.quote(WFNAME)
wf = json.loads(raw(u, None, None, 60).decode("utf-8", "replace"))
print("  %s 节点 %d 链接 %d" % (WFNAME, len(wf["nodes"]), len(wf["links"])))

API, TITLES = build_api(wf)
print("\n=== 2) 定位 T2I 支路 ===")
targets = [nid for nid, a in API.items()
           if a["class_type"] == "SaveImage"
           and TOKEN in str(a["inputs"].get("filename_prefix", ""))
           and str(a["inputs"]["filename_prefix"]).endswith(SUFFIX)]
for t in targets:
    print("  ✔ 节点 %s prefix=%s" % (t, API[t]["inputs"]["filename_prefix"]))
if len(targets) != 1:
    print("  ★ 目标 SaveImage 数量异常：%s" % targets); sys.exit(1)

sub = {k: v for k, v in API.items() if k in deps(API, targets)}
print("\n=== 3) 裁剪后 %d 节点（无 LoadImage = 确实没用 v23 当基准）===" % len(sub))
imgs = [v["inputs"].get("image") for v in sub.values() if v["class_type"] == "LoadImage"]
print("  LoadImage（应为空）:", imgs)
assert not imgs, "★ T2I 支路不该有 LoadImage"
for k in sorted(sub, key=int):
    print("     %-4s %-24s %s" % (k, sub[k]["class_type"], TITLES.get(k, "")))

pos = [v["inputs"]["text"] for v in sub.values() if v["class_type"] == "CLIPTextEncode"]
print("\n  正向提示词 %d 字符" % len(pos[0]) if pos else "  无正向词")
if pos:
    print("  " + pos[0][:400].replace("\n", " ") + (" …" if len(pos[0]) > 400 else ""))

# ------------------------------------------------------------ 提交 N 个 seed
print("\n=== 4) 提交 %d 个 seed（并行排队）===" % N)
jobs = []
for i in range(N):
    seed = SEED0 + i * 7919
    s2 = copy.deepcopy(sub)
    for k, v in s2.items():
        if v["class_type"] == "KSampler":
            v["inputs"]["seed"] = seed
        if v["class_type"] == "SaveImage":
            v["inputs"]["filename_prefix"] = "闻灯新脸候选-%02d-seed%d" % (i + 1, seed)
    res = json.loads(raw("/prompt", json.dumps({"prompt": s2, "client_id": str(uuid.uuid4())}).encode(),
                         "application/json", 120).decode())
    if res.get("node_errors"):
        print("  ★ seed %d node_errors:" % seed)
        print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:1500])
        sys.exit(1)
    jobs.append((i + 1, seed, res["prompt_id"]))
    print("  候选 %02d  seed=%-10d prompt_id=%s" % (i + 1, seed, res["prompt_id"]))

# ------------------------------------------------------------ 等待
print("\n=== 5) 等待（共 %d 张）===" % N)
os.makedirs(OUTDIR, exist_ok=True)
t0 = time.time()
done_set = {}
while len(done_set) < len(jobs) and time.time() - t0 < 1500:
    time.sleep(6)
    for idx, seed, pid in jobs:
        if pid in done_set:
            continue
        try:
            h = json.loads(raw("/history/" + pid, None, None, 60).decode("utf-8", "replace"))
        except Exception:
            continue
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("status_str") == "error":
                for m in st.get("messages", []):
                    if m[0] == "execution_error":
                        print("  ★ 候选 %02d ERROR %s: %s" % (idx, m[1].get("node_type"),
                                                              m[1].get("exception_message", "")[:300]))
            done_set[pid] = h[pid].get("outputs", {})
            print("  ✔ 候选 %02d 完成（累计 %d/%d，用时 %.0f 秒）"
                  % (idx, len(done_set), len(jobs), time.time() - t0))

# ------------------------------------------------------------ 下载
print("\n=== 6) 下载 -> %s ===" % OUTDIR)
n_ok = 0
for idx, seed, pid in jobs:
    for nid, o in (done_set.get(pid) or {}).items():
        for im in o.get("images", []):
            q = urllib.parse.urlencode({"filename": im["filename"],
                                        "subfolder": im.get("subfolder", ""),
                                        "type": im.get("type", "output")})
            data = raw("/view?" + q, None, None, 300)
            dst = os.path.join(OUTDIR, im["filename"])
            open(dst, "wb").write(data)
            n_ok += 1
            print("  saved %-58s %8.1f KB" % (im["filename"], len(data) / 1024))
print("\n拿到 %d 张新脸候选。用时 %.1f 分。" % (n_ok, (time.time() - t0) / 60 + 0.9))
