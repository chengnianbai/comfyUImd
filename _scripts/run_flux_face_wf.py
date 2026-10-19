# -*- coding: utf-8 -*-
"""从远程 ComfyUI 拉回「闻灯-Flux脸部三视角」工作流 → 转成 API 格式 → 只跑指定分支

为什么要「从服务器拉回来再转」：
    这样提交的就是**用户在界面里看到的那个工作流**本身，验证的是工作流真实有效，
    而不是另写一套脚本"绕过"工作流（那样界面里的工作流可能其实是坏的）。

用法：
    python run_flux_face_wf.py front        # 只跑脸部正面（默认，用于先验证方向）
    python run_flux_face_wf.py left
    python run_flux_face_wf.py right
    python run_flux_face_wf.py all
"""
import urllib.request, urllib.parse, json, ssl, time, uuid, os, sys

BASE = "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016"
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
ROOT = r"D:\xiaobai-claude code\comfyUImd"
WFNAME = "闻灯-Flux脸部三视角.json"
OUTDIR = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "flux-v2-脸部")


def raw(p, data=None, ctype=None, timeout=180):
    h = {}
    if ctype:
        h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


# ---------- 拉回工作流 ----------
u = "/api/userdata/workflows%2F" + urllib.parse.quote(WFNAME)
wf = json.loads(raw(u, None, None, 60).decode("utf-8", "replace"))
print("工作流: %s  节点 %d  链接 %d" % (WFNAME, len(wf["nodes"]), len(wf["links"])))

byid = {n["id"]: n for n in wf["nodes"]}
links = {l[0]: l for l in wf["links"]}

# UI widgets 顺序 -> API 参数名
WIDGETS = {
    "CheckpointLoaderSimple": ["ckpt_name"],
    "LoadImage": ["image", "upload"],
    "ImageScale": ["upscale_method", "width", "height", "crop"],
    "VAEEncode": [],
    "UpscaleModelLoader": ["model_name"],
    "CLIPTextEncode": ["text"],
    "FluxGuidance": ["guidance"],
    "KSampler": ["seed", "steps", "cfg", "sampler_name", "scheduler", "denoise"],
    "VAEDecode": [],
    "SaveImage": ["filename_prefix"],
    "ImageUpscaleWithModel": [],
    "ImageScaleBy": ["upscale_method", "scale_by"],
}


def to_api(n):
    names = WIDGETS.get(n["type"])
    if names is None:
        return None
    wv = list(n.get("widgets_values") or [])
    if n["type"] == "KSampler" and len(wv) == len(names) + 1:
        wv = [wv[0]] + wv[2:]          # 丢掉 control_after_generate
    ins = {}
    for k, v in zip(names, wv):
        ins[k] = v
    for slot in n.get("inputs", []):
        lid = slot.get("link")
        if lid is None:
            continue
        l = links.get(lid)
        if not l:
            continue
        ins[slot["name"]] = [str(l[1]), l[2]]
    return {"class_type": n["type"], "inputs": ins, "_meta": {"title": n.get("title") or n["type"]}}


API = {}
for n in wf["nodes"]:
    a = to_api(n)
    if a:
        API[str(n["id"])] = a
print("可转换节点 %d / %d" % (len(API), len(wf["nodes"])))

# ---------- 视角 -> SaveImage 节点 ----------
VIEW_TARGETS = {
    "front": ["14", "20"],
    "left": ["25", "31"],
    "right": ["36", "42"],
}
VIEW_LABEL = {"front": "脸部正面", "left": "脸部左侧面", "right": "脸部右侧面"}

arg = (sys.argv[1] if len(sys.argv) > 1 else "front").lower()
if arg == "all":
    targets = sum(VIEW_TARGETS.values(), [])
    sel = ["front", "left", "right"]
else:
    if arg not in VIEW_TARGETS:
        print("用法: front | left | right | all"); sys.exit(1)
    targets = VIEW_TARGETS[arg]
    sel = [arg]


# ---------- 依赖裁剪：只保留能到达目标 SaveImage 的节点 ----------
def deps(root):
    seen, stack = set(), list(root)
    while stack:
        nid = stack.pop()
        if nid in seen or nid not in API:
            continue
        seen.add(nid)
        for v in API[nid]["inputs"].values():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str):
                stack.append(v[0])
    return seen


keep = deps([t for t in targets if t in API])
sub = {k: v for k, v in API.items() if k in keep}
print("裁剪后节点 %d：%s" % (len(sub), ",".join(sorted(sub, key=int))))

# ---------- 提交 ----------
print("\n提交 %s ..." % "+".join(VIEW_LABEL[s] for s in sel))
res = json.loads(raw("/prompt", json.dumps({"prompt": sub, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 120).decode())
if res.get("node_errors"):
    print("★ node_errors:")
    print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:3000])
    sys.exit(1)
pid = res["prompt_id"]
print("  prompt_id =", pid, " node_errors 为空 → 工作流节点与参数在服务器上全部合法")

# ---------- 等待 ----------
print("\n等待生成（Flux 较慢）...")
done = None
for i in range(150):
    time.sleep(4)
    h = json.loads(raw("/history/" + pid, None, None, 60).decode("utf-8", "replace"))
    if pid in h:
        st = h[pid].get("status", {})
        if st.get("status_str") == "error":
            for m in st.get("messages", []):
                if m[0] == "execution_error":
                    print("★ ERROR %s: %s" % (m[1].get("node_type"),
                                              m[1].get("exception_message", "")[:400]))
            sys.exit(1)
        done = h[pid].get("outputs", {})
        print("  完成，用时约 %d 秒" % ((i + 1) * 4))
        break
if done is None:
    print("★ 超时"); sys.exit(1)

# ---------- 下载 ----------
os.makedirs(OUTDIR, exist_ok=True)
print("\n=== 下载 -> %s ===" % OUTDIR)
for nid, o in done.items():
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"],
                                    "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        dst = os.path.join(OUTDIR, im["filename"])
        data = raw("/view?" + q, None, None, 180)
        open(dst, "wb").write(data)
        print("  saved %-50s %8.1f KB" % (im["filename"], len(data) / 1024))
print("\nOK")
