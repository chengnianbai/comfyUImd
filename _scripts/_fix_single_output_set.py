# -*- coding: utf-8 -*-
"""只保留一组成品：关闭 3 个中间产物的存图节点

现象（用户在实例 gw-6f9531df… 上跑任务 7f30654e 后反馈「生成了 2 组成品」）
    一次跑实际落盘 6 个文件：
      1021 闻灯-脸部正面-成品       ← 终稿 ✅
      1109 闻灯-脸部左侧-成品       ← 终稿 ✅
      1111 闻灯-脸部右侧-成品       ← 终稿 ✅
      1036 闻灯主图-左侧脸-成品      ← Kontext 90° 姿势底的稿，中间产物 ⚠️（名字却带「成品」）
      1042 闻灯主图-右侧脸-成品      ← 同上 ⚠️
      1048 闻灯-脸部-Kontext统一正脸底稿 ← 与 1021 同源(都 <- 1047)，**逐像素重复** ⚠️

改动
    · 1036 / 1042 / 1048 三个 SaveImage 置为禁用（mode=2），并把前缀改成「底稿」以免再被误认成成品
    · 其余一律不动
    => 一次跑只落 3 个文件：正脸/左脸/右脸 成品

用法（可对任意实例执行，靠 COMFY_BASE 切换）：
    set COMFY_BASE=https://gw-xxxx.cn-beijing.aigclinks.com:8016
    python _fix_single_output_set.py dry | run | push
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
WFDIR = os.path.join(ROOT, "_scripts", "_wf")
OUTDIR = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "one_set")
WFNAME = "夜市百相簿-主工作流.json"
ENC = urllib.parse.quote(WFNAME, safe='')
MODE = sys.argv[1] if len(sys.argv) > 1 else "dry"

DISABLE = {}                       # 保留变量名避免误用；本脚本改用「删除」
DELETE = [1036, 1042, 1048]        # 三个中间产物的存图节点，直接删除
KEEP = {1021: "闻灯-脸部正面-成品", 1109: "闻灯-脸部左侧-成品", 1111: "闻灯-脸部右侧-成品"}


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


print("=== 1) 目标实例 %s ===" % BASE)
wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
byid = {n["id"]: n for n in wf["nodes"]}
host = urllib.parse.urlparse(BASE).netloc.split(".")[0]
bpath = os.path.join(WFDIR, "_backup_pre_oneset_%s_%s.json" % (host, time.strftime("%Y%m%d_%H%M%S")))
io.open(bpath, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("  id=%s nodes=%d links=%d  备份 -> %s" % (wf.get("id"), len(wf["nodes"]), len(wf["links"]), os.path.basename(bpath)))

changes = []
gone = [l for l in wf["links"] if l[1] in DELETE or l[3] in DELETE]
wf["links"] = [l for l in wf["links"] if not (l[1] in DELETE or l[3] in DELETE)]
gid = {l[0] for l in gone}
for n in wf["nodes"]:
    for o in (n.get("outputs") or []):
        if o.get("links"):
            o["links"] = [x for x in o["links"] if x not in gid]
for nid in DELETE:
    n = next((x for x in wf["nodes"] if x["id"] == nid), None)
    if n:
        changes.append("删除 #%-5s SaveImage  %r（中间产物）" % (nid, (n.get("widgets_values") or [None])[0]))
wf["nodes"] = [n for n in wf["nodes"] if n["id"] not in DELETE]
changes.append("连同 %d 条连线" % len(gone))

print("\n=== 2) 改动 ===")
for c in changes: print("   · %s" % c)
print("\n=== 3) 改动后的 SaveImage 一览 ===")
for n in sorted([x for x in wf["nodes"] if x["type"] == "SaveImage"], key=lambda z: z["id"]):
    mark = "★启用" if n.get("mode") == 0 else "  禁用"
    print("   #%-5s %s %r" % (n["id"], mark, (n.get("widgets_values") or [None])[0]))

active = {n["id"]: (n.get("widgets_values") or [None])[0]
          for n in wf["nodes"] if n["type"] == "SaveImage" and n.get("mode") == 0}
print("\n=== 4) 自检：启用中的存图节点 ===")
for k, v in sorted(active.items()):
    print("   #%s %r" % (k, v))
extra = [k for k in active if k not in KEEP]
if extra:
    print("   ★ 还有非终稿的启用存图节点：%s" % extra); sys.exit(1)
print("   ✔ 只剩三张终稿")

out_local = os.path.join(WFDIR, "_pending_oneset.json")
io.open(out_local, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
if MODE == "dry":
    print("\n[dry] 未联网写。"); sys.exit(0)

sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                       # noqa
API, TITLES = build_api(wf)
TARGETS = [nid for nid, a in API.items() if a["class_type"] == "SaveImage" and "脸部" in str(a["inputs"].get("filename_prefix", ""))]
print("\n=== 5) 提交一次，确认只落 3 个文件 ===")
print("   目标输出 = %s" % [API[t]["inputs"]["filename_prefix"] for t in TARGETS])
subg = {k: v for k, v in API.items() if k in deps(API, TARGETS)}
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
if done is None: print("★ 超时"); sys.exit(1)
os.makedirs(OUTDIR, exist_ok=True)
n_files = 0
for nid, o in sorted(done.items(), key=lambda x: int(x[0])):
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        p = os.path.join(OUTDIR, im["filename"])
        open(p, "wb").write(raw("/view?" + q, None, None, 300))
        n_files += 1
        print("   [node %-5s] %s" % (nid, im["filename"]))
print("   => 本次落盘 %d 个文件 %s" % (n_files, "✔" if n_files == 3 else "★ 不是 3"))

if MODE != "push":
    print("\n[run] 未写工作流。"); sys.exit(0)

print("\n=== 6) 写回线上 ===")
raw("/api/userdata/workflows%2F" + ENC, io.open(out_local, encoding="utf-8").read().encode("utf-8"),
    "application/json", 300)
back = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
bb = {n["id"]: n for n in back["nodes"]}
act = sorted(n["id"] for n in back["nodes"] if n["type"] == "SaveImage" and n.get("mode") == 0)
print("   回读：启用中的存图节点 = %s %s；nodes=%d links=%d"
      % (act, "✔" if act == sorted(KEEP) else "★ 不对", len(back["nodes"]), len(back["links"])))
io.open(os.path.join(WFDIR, "_live_now_%s.json" % host), "w", encoding="utf-8").write(json.dumps(back, ensure_ascii=False, indent=1))
if act != sorted(KEEP):
    print("★ 校验不过，自动还原 ...")
    raw("/api/userdata/workflows%2F" + ENC, io.open(bpath, encoding="utf-8").read().encode("utf-8"),
        "application/json", 300)
    print("   已还原。"); sys.exit(1)
print("\n✔ 该实例现在只落三张终稿（正脸 / 左脸 / 右脸）")
