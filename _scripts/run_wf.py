# -*- coding: utf-8 -*-
"""通用跑图器：从远程 ComfyUI 拉回指定工作流 → 转 API 格式 → 裁剪到目标分支 → 提交 → 取图

为什么不直接写死节点 id：
    工作流一改节点编号就漂，之前 run_flux_face_wf.py 把 SaveImage 的 id 写死了
    （front=14/20 …），一加分支就全废。这里改成**按 SaveImage 的 filename_prefix 找**。

用法：
    python run_wf.py <工作流文件名> <前缀关键词> [draft|final] [输出目录]

例：
    python run_wf.py "闻灯-Flux脸部三视角-迭代转头.json" "四分之三左侧-d070" draft
    python run_wf.py "闻灯-Flux脸部三视角-迭代转头.json" "四分之三左侧-d070" final

    draft → 命中 filename_prefix 以「草稿」结尾的 SaveImage（只跑 28 步第一段，最快）
    final → 命中以「成品」结尾的（带 4x 放大 + 二次重绘，慢）
"""
import urllib.request, urllib.parse, json, ssl, time, uuid, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wf_api import build_api, deps, WIDGETS          # 转换表统一在 wf_api.py 维护

BASE = os.environ.get("COMFY_BASE", "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016")
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
ROOT = r"D:\xiaobai-claude code\comfyUImd"

if len(sys.argv) < 3:
    print(__doc__); sys.exit(1)
WFNAME = sys.argv[1]
# 支持逗号分隔多个关键词 → 一次提交跑多条分支（比反复提交省去排队开销）
TOKENS = [t.strip() for t in sys.argv[2].split(",") if t.strip()]
KIND = (sys.argv[3] if len(sys.argv) > 3 else "final").lower()
OUTDIR = (sys.argv[4] if len(sys.argv) > 4
          else os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "flux-v3-转头"))
SUFFIX = "草稿" if KIND == "draft" else "成品"


def raw(p, data=None, ctype=None, timeout=180):
    h = {}
    if ctype:
        h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


print("=== 1) 拉回工作流 ===")
u = "/api/userdata/workflows%2F" + urllib.parse.quote(WFNAME)
try:
    wf = json.loads(raw(u, None, None, 60).decode("utf-8", "replace"))
except Exception as e:
    print("  ★ 读取失败（%s）—— 实例可能没开机，或工作流名不对。" % type(e).__name__)
    print("     · 实例状态：python oneshot.py wait")
    print("     · 工作流列表：见 oneshot.py p1 的输出")
    sys.exit(2)
print("  %s  节点 %d  链接 %d" % (WFNAME, len(wf["nodes"]), len(wf["links"])))

API, TITLES = build_api(wf)
print("  可转换节点 %d / %d" % (len(API), len(wf["nodes"])))
_unsup = sorted({n["type"] for n in wf["nodes"] if n["type"] not in WIDGETS})
if _unsup:
    print("  ⚠️ 未支持的节点类型（会被静默跳过，导致缺节点跑不起来）：%s" % _unsup)
    print("     → 去 _scripts/wf_api.py 的 WIDGETS 里补上它的 widget 名列。")

# ---------- 2) 按前缀找目标 SaveImage ----------
print("\n=== 2) 定位目标 SaveImage ===")
print("  关键词 %s   类型 %s" % (TOKENS, SUFFIX))
targets = []
for nid, a in API.items():
    if a["class_type"] != "SaveImage":
        continue
    pfx = str(a["inputs"].get("filename_prefix", ""))
    if any(t in pfx for t in TOKENS) and pfx.endswith(SUFFIX):
        targets.append(nid)
        print("   ✔ 节点 %s  prefix=%s" % (nid, pfx))
if not targets:
    print("  ★ 没找到匹配的 SaveImage。当前全部 SaveImage：")
    for nid, a in API.items():
        if a["class_type"] == "SaveImage":
            print("     %-4s %s" % (nid, a["inputs"].get("filename_prefix")))
    sys.exit(1)


# ---------- 3) 依赖裁剪 ----------
keep = deps(API, targets)
sub = {k: v for k, v in API.items() if k in keep}
print("\n=== 3) 裁剪后 %d 个节点 ===" % len(sub))
for k in sorted(sub, key=int):
    print("   %-4s %-22s %s" % (k, sub[k]["class_type"], TITLES.get(k, "")))
missing_img = [v["inputs"].get("image") for v in sub.values()
               if v["class_type"] == "LoadImage"]
if missing_img:
    print("   基图 =", missing_img)

# ---------- 4) 提交 ----------
print("\n=== 4) 提交 ===")
res = json.loads(raw("/prompt", json.dumps({"prompt": sub, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 120).decode())
if res.get("node_errors"):
    print("  ★ node_errors:")
    print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:3000])
    sys.exit(1)
pid = res["prompt_id"]
print("  prompt_id =", pid, " node_errors 为空 → 节点与参数在服务器上全部合法")

# ---------- 5) 等待 ----------
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
                    print("  ★ ERROR 节点=%s: %s" % (m[1].get("node_type"),
                                                     m[1].get("exception_message", "")[:500]))
                    if m[1].get("traceback"):
                        print("  " + " | ".join(str(x) for x in m[1]["traceback"])[:600])
            sys.exit(1)
        done = h[pid].get("outputs", {})
        print("  完成，用时约 %d 秒" % ((i + 1) * 5))
        break
if done is None:
    print("  ★ 超时"); sys.exit(1)

# ---------- 6) 下载 ----------
os.makedirs(OUTDIR, exist_ok=True)
print("\n=== 6) 下载 -> %s ===" % OUTDIR)
for nid, o in done.items():
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"],
                                    "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        dst = os.path.join(OUTDIR, im["filename"])
        data = raw("/view?" + q, None, None, 300)
        open(dst, "wb").write(data)
        print("  saved %-52s %8.1f KB" % (im["filename"], len(data) / 1024))
print("\nOK")
