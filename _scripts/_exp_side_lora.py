# -*- coding: utf-8 -*-
"""方案 2：给侧脸支路单独挂「add-details」细节 LoRA —— **只改提交内容，绝不写服务器工作流**

★★★ 实测结论（2026-09-24）：本方案【失败】，别再指望这个 LoRA ★★★
    固定 seed 20260920，唯一变量 = LoRA 权重。皮肤掩膜内度量：
        基线 00045       lapVar 150.27  locStd 3.066
        w=+0.35          lapVar 143.59  locStd 3.010
        w=+0.50          lapVar 143.81  locStd 2.983
        w=+0.70          lapVar 132.48  locStd 2.852   ← 最差
        w=-0.40          lapVar 163.88  locStd 3.044
        w=-0.70          lapVar 151.89  locStd 2.931
        w=-1.00          lapVar 125.89  locStd 2.803   ← 目视已出伪影
        正脸对照          lapVar 198.79  locStd 3.402   ← 与 00029 逐位一致，未被污染
    · locStd（较稳的微对比度指标）在【正负两个方向】都随 |w| 单调下降
      ⇒ 任何方向施加这个 LoRA 都在削弱质感，而不是增强。
    · w=-0.4 的 lapVar 单独上翘是【非单调噪声】：它的 locStd 反而低于基线，
      1:1 目视也只与 +0.5 同档 —— 多出来的是 1 像素"脆"噪声，不是真皮肤纹理。
    · w=-1.0 目视：颊部成片黑点、胡茬扭曲、整体脏污 —— 大负权重会直接毁图。

★ 纠正 README 的说法（不能直接采信到本链路）
    README 自称 "enhancing realism and details, achieving natural skin"，并说
    "The scale can be negative"。本链路实测与之矛盾：该 LoRA 的 "realism" 方向是
    【影棚级匀净肤质】而非毛孔颗粒；正权重让它更干净，负权重不是简单反演而是崩坏。
    很可能是与 1031 提示词里 `Prioritize realistic skin material ... over visible pore
    detail` / `Avoid excessive pore visibility` 【同向叠加】，一起把皮肤推向"干净"。
    ⇒ 只读模型 README 来推断效果不可靠，必须在本链路上实测。

背景（2026-09-24 实拉线上 00029/00045/00046 实测）
--------------------------------------------------
皮肤微细节能量（lapVar，皮肤掩膜内）：正脸 198.8 / 左脸 150.3 / 右脸 150.3
    → 侧脸比正脸少 ~32%；1:1 高通滤波下侧脸接近一片平灰（正脸能看到根根胡须与毛孔）。
根因：侧脸支路要同时做两件事 —— ① 把正面重投影成 90° 侧面（几何重构）
      ② 渲染皮肤质感。而它的身份参考是「正脸产物」，在几何上对不上 90° 目标，
      Kontext 的 ReferenceLatent 是软条件 → 只能传身份/大结构，传不了毛孔级高频，
      模型于是退回自己对「90° 侧面」的先验 = 光滑蜡质。
      关键反证：侧脸的参考图（正脸产物 lapVar 198.8）比侧脸自己的输出（150.3）更细，
      参考比结果好、结果还是掉了 ⇒ 是「重投影」这个任务本身在压制高频。

本脚本做什么
------------
新增 1 个 LoraLoaderModelOnly（LoRA = FLUX.1-dev-LoRA-add-details，Dote 版），
**只接在 1034（左脸 KSampler）的 model 上**：
    1024(UNETLoader/Kontext fp8) ──┬──> 1046(正脸 KSampler)   直连，不动
                                   └──> 9001(LoRA, w=s) ──> 1034(左脸 KSampler)
右脸是 1051 的水平翻转，自动继承。
LoRA 是**与视角无关**的条件，正好绕开「参考图对不上」这个死结。

单变量保证
----------
该 LoRA 官方 README 明写「There is no essential trigger words」→ **提示词一个字不改**。
本轮唯一变量 = LoRA 权重。正脸 1046 不在改动范围内，作为对照（应逐像素不变）。

★ 结构注意：侧脸支路的身份锚 1050 ← 1049 ← 1047 ← 1046，所以**正脸 KSampler 是
  侧脸的硬依赖，每次都必须跑**，省不掉。

落盘位置说明（为什么文件名不像它）
----------------------------------
服务器 Manager 白名单没有 Flux 细节 LoRA 槽位（只有 HyperSD/LCM/LTX/Qwen），
`install_model` 会拿 (save_path, base, filename) 三元组精确匹配白名单，不匹配直接 400。
所以只能借 `loras/HyperSD/FLUX.1` 的槽位落盘，文件名是
`Hyper-FLUX.1-dev-8steps-lora.safetensors`，**内容其实是 add-details**。
（与当初 Kontext 借 flux1-schnell.safetensors 同一个做法，**勿去"修正"文件名**）
已在服务器上验过货：日志 `Installation was successful.`，最小链路 15 秒跑通。

用法：
    python _exp_side_lora.py dry                       # 零成本：只构建 + 校验提交内容
    python _exp_side_lora.py run                       # 默认权重扫描 0.35 / 0.5 / 0.7
    python _exp_side_lora.py run --strength 0.5        # 只跑一个权重
    python _exp_side_lora.py run --baseline <旧左脸.png>  # 顺带算与旧图的 lapVar 对照
"""
import os, sys, ssl, json, time, uuid, io, urllib.request, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wf_api import build_api, deps

BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
if not BASE:
    print("★ 先设环境变量 COMFY_BASE，例如：")
    print('   set COMFY_BASE=https://gw-24913d21c3684a67bd1f95e3e619eaf0.cn-beijing.aigclinks.com:8016')
    sys.exit(4)
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"D:\xiaobai-claude code\comfyUImd"
WFNAME = "夜市百相簿-主工作流.json"

MODE = sys.argv[1] if len(sys.argv) > 1 else "dry"

# ---- 借槽位落盘的 LoRA（内容是 FLUX.1-dev-LoRA-add-details）----
LORA_NAME = "HyperSD\\FLUX.1\\Hyper-FLUX.1-dev-8steps-lora.safetensors"
LORA_NODE = "9001"          # 新增节点 id，与现有 1..1052 不冲突

STRENGTHS = [0.35, 0.5, 0.7]
BASELINE = None
for i, a in enumerate(sys.argv):
    if a == "--strength":
        STRENGTHS = [float(x) for x in sys.argv[i + 1].split(",")]
    if a == "--baseline":
        BASELINE = sys.argv[i + 1]

OUTDIR = (sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--")
          else os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "side_lora"))

TOKENS = ["闻灯Kontext统一正脸", "闻灯主图-左侧脸", "闻灯主图-右侧脸"]


def raw(p, data=None, ctype=None, timeout=300):
    h = {}
    if ctype:
        h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


# ==================== 皮肤微细节度量（与 09-24 诊断同一套指标）====================
def skin_stats(path):
    """返回 (lapVar, locStd) —— 皮肤掩膜内的拉普拉斯方差 / 3x3 局部标准差"""
    try:
        import numpy as np
        from PIL import Image
        from numpy.lib.stride_tricks import sliding_window_view
    except Exception:
        return None
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    R, G, B = a[:, :, 0].astype(np.int16), a[:, :, 1].astype(np.int16), a[:, :, 2].astype(np.int16)
    mx = np.maximum(np.maximum(R, G), B); mn = np.minimum(np.minimum(R, G), B)
    sat = (mx - mn) / np.maximum(mx, 1)
    m = (R > 95) & (R > G) & (G > B) & ((R - B) > 12) & ((R - B) < 90) & (sat > 0.12) & (sat < 0.65)
    mm = m[1:-1, 1:-1] & m[:-2, 1:-1] & m[2:, 1:-1] & m[1:-1, :-2] & m[1:-1, 2:]
    if mm.sum() < 1000:
        return None
    g = 0.299 * a[:, :, 0] + 0.587 * a[:, :, 1] + 0.114 * a[:, :, 2]
    k = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], float)
    lap = (sliding_window_view(g, (3, 3)) * k).sum(axis=(-1, -2))
    loc = sliding_window_view(g, (3, 3)).reshape(g.shape[0] - 2, g.shape[1] - 2, -1).std(axis=-1)
    return float(lap[mm].var()), float(loc[mm].mean())


# ==================== 1) 拉线上工作流（只读）====================
print("=== 1) 拉线上工作流（只读）===")
u = "/api/userdata/workflows%2F" + urllib.parse.quote(WFNAME)
wf = json.loads(raw(u, None, None, 60).decode("utf-8", "replace"))
print("  %s  节点 %d  链接 %d   id=%s" % (WFNAME, len(wf["nodes"]), len(wf["links"]), wf.get("id")))

API, TITLES = build_api(wf)

print("  线上 1024 = %r" % API["1024"]["inputs"]["unet_name"])
print("  线上 1027 = %r" % API["1027"]["inputs"]["image"])
print("  线上 1046(正脸).model = %s" % API["1046"]["inputs"]["model"])
print("  线上 1034(左脸).model = %s" % API["1034"]["inputs"]["model"])


def build(strength):
    """返回 (裁剪后的提交内容, 目标 SaveImage id 列表, 改动清单)"""
    A = json.loads(json.dumps(API))          # 深拷
    changes = []

    # 新增 LoRA 节点
    A[LORA_NODE] = {"class_type": "LoraLoaderModelOnly",
                    "inputs": {"model": ["1024", 0], "lora_name": LORA_NAME,
                               "strength_model": strength},
                    "_meta": {"title": "侧脸专用 · add-details LoRA w=%.2f（借槽位名）" % strength}}
    changes.append("新增 %s LoraLoaderModelOnly  lora=%s  w=%.2f" % (LORA_NODE, LORA_NAME, strength))

    # 只把左脸 KSampler 的 model 从 1024 改接到新节点
    assert A["1034"]["inputs"]["model"] == ["1024", 0], "1034.model 不是预期的 1024"
    A["1034"]["inputs"]["model"] = [LORA_NODE, 0]
    changes.append("1034.model  ['1024',0] -> ['%s',0]   （仅左脸支路）" % LORA_NODE)

    # 正脸必须保持直连（对照）
    assert A["1046"]["inputs"]["model"] == ["1024", 0], "1046.model 被动过，正脸对照失效"

    # 找目标输出节点
    roots = []
    for nid, a in A.items():
        if a["class_type"] != "SaveImage":
            continue
        pfx = str(a["inputs"].get("filename_prefix", ""))
        if any(t in pfx for t in TOKENS) and pfx.endswith("成品"):
            roots.append(nid)
    # 输出文件名带权重，便于事后归因（只改提交内容，线上前缀不变）
    tag = ("n%d" % round(abs(strength) * 100)) if strength < 0 else ("%d" % round(strength * 100))
    for nid in roots:
        pfx = str(A[nid]["inputs"]["filename_prefix"])
        if "正脸" not in pfx:
            A[nid]["inputs"]["filename_prefix"] = pfx + "-L" + tag
            changes.append("%s.filename_prefix %r -> %r" % (nid, pfx, A[nid]["inputs"]["filename_prefix"]))

    keep = deps(A, roots)
    return {k: v for k, v in A.items() if k in keep}, sorted(roots), changes


# ==================== 2) dry：构建并校验 ====================
for s in STRENGTHS:
    subg, roots, changes = build(s)
    print("\n=== 2) w=%.2f  本次相对线上的改动（仅这些）===" % s)
    for c in changes:
        print("   ·", c)
    print("   目标输出: %s" % ", ".join("%s[%s]" % (r, TITLES.get(r, "")) for r in roots))
    print("   裁剪后 %d 节点；含 LoRA 节点: %s" % (len(subg), LORA_NODE in subg))
    if LORA_NODE in subg:
        print("   %s = %s" % (LORA_NODE, json.dumps(subg[LORA_NODE]["inputs"], ensure_ascii=False)))
    tag = ("%g" % s).replace(".", "")
    io.open(os.path.join(HERE, "_wf", "_last_submit_loraL%s.json" % tag), "w",
            encoding="utf-8").write(json.dumps(subg, ensure_ascii=False))

if MODE == "dry":
    print("\n[dry] 未提交。确认无误后跑：python _exp_side_lora.py run")
    sys.exit(0)

# ==================== 3) run：逐权重提交 ====================
os.makedirs(OUTDIR, exist_ok=True)
print("\n=== 3) 提交（%d 个权重，每个约 90 秒）===" % len(STRENGTHS))
rows = []
for s in STRENGTHS:
    subg, roots, _ = build(s)
    tag = ("%g" % s).replace(".", "")
    print("\n---- w=%.2f ----" % s)
    res = json.loads(raw("/prompt", json.dumps({"prompt": subg,
                                                "client_id": str(uuid.uuid4())}).encode(),
                         "application/json", 120).decode())
    if res.get("node_errors"):
        print("  ★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:2500])
        continue
    pid = res["prompt_id"]; print("  prompt_id =", pid)
    done = None
    for i in range(180):
        time.sleep(5)
        h = json.loads(raw("/history/" + pid, None, None, 60).decode("utf-8", "replace"))
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("status_str") == "error":
                for m in st.get("messages", []):
                    if m[0] == "execution_error":
                        print("  ★ ERROR %s: %s" % (m[1].get("node_type"),
                                                    m[1].get("exception_message", "")[:400]))
                break
            done = h[pid].get("outputs", {}); print("  完成，约 %d 秒" % ((i + 1) * 5)); break
    if done is None:
        print("  ★ 超时"); continue
    for nid, o in done.items():
        for im in o.get("images", []):
            q = urllib.parse.urlencode({"filename": im["filename"],
                                        "subfolder": im.get("subfolder", ""),
                                        "type": im.get("type", "output")})
            p = os.path.join(OUTDIR, im["filename"])
            open(p, "wb").write(raw("/view?" + q, None, None, 300))
            st = skin_stats(p)
            print("  saved %-52s %7.1f KB   %s" % (im["filename"], os.path.getsize(p) / 1024,
                  ("lapVar=%7.2f locStd=%.3f" % st) if st else ""))
            rows.append({"w": s, "node": nid, "file": im["filename"], "stats": st})

# ==================== 4) 与旧图对照 ====================
if BASELINE and os.path.exists(BASELINE):
    st = skin_stats(BASELINE)
    print("\n=== 4) 基线对照 ===")
    print("  %-52s %s" % (os.path.basename(BASELINE),
          ("lapVar=%7.2f locStd=%.3f" % st) if st else "（无皮肤掩膜）"))
io.open(os.path.join(OUTDIR, "_run_meta.json"), "w", encoding="utf-8").write(
    json.dumps({"lora": LORA_NAME, "node": LORA_NODE, "strengths": STRENGTHS,
                "baseline": BASELINE, "rows": rows}, ensure_ascii=False, indent=1))
print("\n产物 -> %s" % OUTDIR)
print("★ 看什么：左脸的毛孔/胡茬是否回来；同时确认正脸那张与 00029 逐像素一致（对照没被污染）。")
