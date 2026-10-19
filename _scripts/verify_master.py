# -*- coding: utf-8 -*-
"""本地验证主工作流：每条分支能否被 run_wf.py 正确提交（**不联网、零成本**）

为什么需要它：
    合并后的主工作流有 19 个 SaveImage、130 个节点、3 种底模（SDXL / Flux fp8 / Kontext）。
    如果某个分支依赖了 wf_api.WIDGETS 里没登记的类型，run_wf.py 会**静默跳过那个节点** —— 提交上去
    要么缺输入、要么报一堆看不懂的错，而那时实例已经开机在烧豆了。
    所以必须在本地先把每条分支的依赖链完整走一遍。

用法：
    python verify_master.py
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from wf_api import build_api, deps, WIDGETS

WF = os.path.join(HERE, "_wf", "夜市百相簿_主工作流.json")

if not os.path.exists(WF):
    print("★ 找不到 %s\n   先跑 python build_master_wf.py" % WF); sys.exit(1)

wf = json.load(open(WF, encoding="utf-8"))
api, titles = build_api(wf)
byid = {str(n["id"]): n for n in wf["nodes"]}
links = {l[0]: l for l in wf["links"]}

print("=" * 78)
print("主工作流本地验证：%s" % os.path.basename(WF))
print("=" * 78)
print("  UI 节点 %d  可转 API 节点 %d  链接 %d  Group %d"
      % (len(wf["nodes"]), len(api), len(wf["links"]), len(wf.get("groups", []))))

unsup = sorted({n["type"] for n in wf["nodes"]
                if n["type"] not in WIDGETS or WIDGETS[n["type"]] is None})
print("  未登记类型: %s" % (unsup if unsup else "无"))


def ui_deps(roots):
    """按 UI 连线回溯（不关心类型是否受支持）"""
    seen, stack = set(), list(roots)
    while stack:
        k = stack.pop()
        if k in seen or k not in byid:
            continue
        seen.add(k)
        for s in byid[k].get("inputs", []):
            lid = s.get("link")
            if lid is None:
                continue
            l = links.get(lid)
            if l:
                stack.append(str(l[1]))
    return seen


out_nodes = [n for n in wf["nodes"] if n["type"] == "SaveImage"]
print("  输出节点 %d 个\n" % len(out_nodes))

bad = 0
MODE = {}
for n in wf["nodes"]:
    if n["type"] in ("UNETLoader",):
        MODE.setdefault("kontext", []).append(n["widgets_values"][0])
    if n["type"] == "CheckpointLoaderSimple":
        MODE.setdefault("sdxl", []).append(n["widgets_values"][0])

print("%-42s %-6s %-6s %-6s %s" % ("分支（SaveImage 前缀）", "API", "UI", "缺类", "底模 / 备注"))
print("-" * 78)
for n in sorted(out_nodes, key=lambda x: str(x["widgets_values"][0])):
    nid = str(n["id"])
    pfx = str(n["widgets_values"][0])
    ui_keep = ui_deps([nid])
    api_keep = deps(api, [nid])
    missing = sorted(byid[k]["type"] for k in ui_keep
                     if k not in api_keep and byid[k]["type"] not in ("Note",))
    miss_types = sorted({t for t in missing if t not in WIDGETS or WIDGETS[t] is None})
    note = ""
    for k in ui_keep:
        t = byid[k]["type"]
        if t == "CheckpointLoaderSimple":
            note = "ckpt " + str(byid[k]["widgets_values"][0])[:38]
        elif t == "UNETLoader":
            note = "UNet " + str(byid[k]["widgets_values"][0])[:38]
        elif t == "LoadImage":
            note += " | base=" + str(byid[k]["widgets_values"][0])
    flag = "★" if miss_types else "OK"
    if miss_types:
        bad += 1
    print("%-42s %-6d %-6d %-6s %s %s" % (pfx, len(api_keep), len(ui_keep),
                                          len(miss_types), flag, note))

print("-" * 78)
print("\n分支检查：%d 个输出，%d 个有问题" % (len(out_nodes), bad))

# 额外检查：模型引用是否落在已知的 4 个底模里
print("\n[模型引用清点]")
from collections import Counter
ck = Counter()
for n in wf["nodes"]:
    if n["type"] == "CheckpointLoaderSimple" and n.get("widgets_values"):
        ck["ckpt: " + str(n["widgets_values"][0])] += 1
    if n["type"] in ("UNETLoader", "DualCLIPLoader", "VAELoader") and n.get("widgets_values"):
        ck["%s: %s" % (n["type"], n["widgets_values"][0])] += 1
    if n["type"] == "UpscaleModelLoader" and n.get("widgets_values"):
        ck["upscale: " + str(n["widgets_values"][0])] += 1
for k, v in sorted(ck.items()):
    print("   %-62s x%d" % (k, v))

# 跑图命令预览 —— ★ 必须**精确模拟** run_wf.py 的匹配逻辑，不能只看 startswith
# run_wf.py 的判定是：  关键词 in filename_prefix   AND   filename_prefix.endswith("成品")
# 少模拟「后缀」这一步，就会漏掉「Kontext 块前缀没带 -成品」那类 bug：
# 分支本身完全正常，但跑图时一个都选不中，直接退出（而那时实例已经开机在烧豆了）。
print("\n[开机后的跑图命令 —— 精确模拟 run_wf.py 的选中结果]")
prefixes = [str(n["widgets_values"][0]) for n in out_nodes]


def select(tokens, kind="final"):
    suffix = "草稿" if kind == "draft" else "成品"
    return [p for p in prefixes if any(t in p for t in tokens) and p.endswith(suffix)]


CMDS = [
    ("p3 出图", ["闻灯-脸部正面"], "final", "1 张：闻灯脸部正面（SDXL img2img 保身份）"),
    # 2026-09-21：先用 00009 统一 Kontext 正脸质感，再由同一张图生成左右侧脸。
    ("Kontext三视角", ["闻灯Kontext统一正脸", "闻灯主图-左侧脸", "闻灯主图-右侧脸"], "final",
     "3 张：统一质感正脸 + Kontext 左/右 90 度侧脸"),
]
cmd_bad = 0
for name, tokens, kind, expect in CMDS:
    hit = select(tokens, kind)
    print("   %-8s run_wf.py \"夜市百相簿-主工作流.json\" \"%s\" %s" % (name, ",".join(tokens), kind))
    print("            期望 %s" % expect)
    if not hit:
        cmd_bad += 1
        print("            ★★ 一个都没选中 —— 这条命令会直接失败！")
    else:
        for p in hit:
            print("            ✔ %s" % p)

# 全身立绘块（不列入自动跑：按 §3.1 必须先确认脸部才能跑全身，列出来仅供核对）
body_hits = select(["闻灯-全身正面"], "draft") + select(["闻灯-全身正面"], "final")
if body_hits:
    print("   （全身立绘块 %d 个输出不列入自动跑：脸部确认后手动跑）" % len(body_hits))

if cmd_bad:
    print("\n★★ 有跑图命令选不中目标 —— 别开机，先修 SaveImage 前缀与 oneshot.py 的关键词。")
    sys.exit(1)

if bad:
    print("\n★ 有分支存在问题 —— 别开机，先修 wf_api.py 的 WIDGETS 表。")
    sys.exit(1)
print("\n✔ 全部 %d 条分支依赖完整，%d 条跑图命令均能选中目标，可以开机。"
      % (len(out_nodes), len(CMDS)))
