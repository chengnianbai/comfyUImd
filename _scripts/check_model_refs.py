# -*- coding: utf-8 -*-
"""开机前把工作流里的**每一个模型引用**，拿去和服务器上真实存在的文件名逐一对账。

★ 为什么需要它（2026-09-18 踩的坑）
    ComfyUI 的 Loader 只接受「下拉列表里有的值」，而列表来自服务器实际扫到的文件。
    引用名写错（少写子目录 `FLUX1\\` / `t5\\`、文件名拼错、文件压根没下）→
    节点照样能装配、能推送、能通过本地自检，**只有提交时才会抛 value not in list**。
    而那时候实例已经开机在烧豆了。

    本脚本用 `/object_info/<NodeName>` 的 combo 列表做判据 —— 那是权威信号
    （就是前端下拉框里给用户选的东西）。

★ 用法
    python check_model_refs.py                       # 校验 _wf\\夜市百相簿_主工作流.json
    python check_model_refs.py 路径\\到\\工作流.json    # 校验指定文件
    退出码 0 = 全对；1 = 有引用对不上（别开机，或先修）。

★ 判据说明
    · 分隔符归一：`FLUX1/flux.safetensors` 与 `FLUX1\\flux.safetensors` 视为同一项。
    · 找不到时，会列出**同名的其它路径**（帮你看出是漏了子目录还是文件没下）。
"""
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get(
    "COMFY_BASE",
    "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016",
)
DEFAULT_WF = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "_wf", "夜市百相簿_主工作流.json")

# 节点类型 → [(object_info 里的节点名, 输入端口名, widgets 下标)]
REFS = {
    "CheckpointLoaderSimple": [("CheckpointLoaderSimple", "ckpt_name", 0)],
    "CheckpointLoader":       [("CheckpointLoader", "ckpt_name", 0)],
    "UNETLoader":             [("UNETLoader", "unet_name", 0)],
    "VAELoader":              [("VAELoader", "vae_name", 0)],
    "CLIPLoader":             [("CLIPLoader", "clip_name", 0)],
    "DualCLIPLoader":         [("DualCLIPLoader", "clip_name1", 0),
                               ("DualCLIPLoader", "clip_name2", 1)],
    "UpscaleModelLoader":     [("UpscaleModelLoader", "model_name", 0)],
    "LoraLoader":             [("LoraLoader", "lora_name", 0)],
    "ControlNetLoader":       [("ControlNetLoader", "control_net_name", 0)],
    "DiffControlNetLoader":   [("DiffControlNetLoader", "control_net_name", 0)],
}

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE


def api(path, timeout=60):
    u = BASE + path
    try:
        return urllib.request.urlopen(u, timeout=timeout, context=_ctx).read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code == 400:
            raise SystemExit("★ 网关返回 400 + “服务连接失败” → 实例掉线（不是文件问题）。")
        raise
    except Exception as e:
        raise SystemExit("★ 连不上实例（%s: %s）→ 先确认开机 / 换对网关 hash。" % (type(e).__name__, e))


_COMBO_CACHE = {}


def combo(node_name, key):
    """取某 Loader 的候选文件列表（就是前端下拉框里的内容）

    ⚠️ 同一台服务器上**两种 combo 编码并存**（2026-09-18 实测），必须都认：
       旧式：  "unet_name": [["a.safetensors", "b.safetensors"], {"advanced": ...}]
       新式：  "model_name": ["COMBO", {"multiselect": False, "options": ["a.pth"]}]
    只认旧式的话，新式会解析出字符串 "COMBO" → 把**明明存在**的文件误报成"对不上"。
    """
    ck = (node_name, key)
    if ck in _COMBO_CACHE:
        return _COMBO_CACHE[ck]
    d = json.loads(api("/object_info/" + urllib.parse.quote(node_name)))
    lst = None
    try:
        spec = d[node_name]["input"]["required"][key]
        if isinstance(spec, list) and spec:
            if isinstance(spec[0], list):
                lst = spec[0]                                  # 旧式
            elif spec[0] == "COMBO" and len(spec) > 1 and isinstance(spec[1], dict):
                lst = spec[1].get("options")                    # 新式
    except Exception:
        # ⚠️ 节点不存在时返回的是 {} + 200（不是 404），会走到本分支
        lst = None
    _COMBO_CACHE[ck] = lst
    return lst


def norm(s):
    return str(s).replace("/", "\\").strip().lower()


def main():
    wf_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_WF
    if not os.path.exists(wf_path):
        raise SystemExit("★ 找不到工作流：%s" % wf_path)
    wf = json.load(open(wf_path, encoding="utf-8"))
    print("=" * 74)
    print("模型引用对账：%s" % os.path.basename(wf_path))
    print("服务器：%s" % BASE)
    print("=" * 74)

    bad, ok = [], 0
    for n in wf["nodes"]:
        for node_name, key, idx in REFS.get(n["type"], []):
            wv = n.get("widgets_values") or []
            if idx >= len(wv):
                continue
            val = wv[idx]
            if not isinstance(val, str) or not val.strip():
                continue
            lst = combo(node_name, key)
            if lst is None:
                bad.append((n["id"], n["type"], key, val, "节点 %s 在本实例不存在" % node_name))
                continue
            if any(norm(x) == norm(val) for x in lst):
                ok += 1
                print("  ✔ %-24s %s" % (key, val))
                continue
            # 对不上：找同名的其它路径，帮判断是「漏子目录」还是「没下载」
            base = os.path.basename(val.replace("/", "\\"))
            near = [x for x in lst if os.path.basename(str(x).replace("/", "\\")) == base]
            hint = ("同名文件在：%s（→ 引用名漏了子目录）" % near) if near \
                else ("该目录下只有 %s" % (lst or "（空）"))
            bad.append((n["id"], n["type"], key, val, hint))
            print("  ★ %-24s %s  ← 对不上！%s" % (key, val, hint))

    print("-" * 74)
    if bad:
        print("★ %d 处对不上（另有 %d 处正常）：" % (len(bad), ok))
        for nid, t, k, v, why in bad:
            print("   节点 %-5s %-22s %s\n        %s" % (nid, t, v, why))
        print("\n→ 先修引用再开机，否则提交时才报 value not in list（那时豆已经在烧）。")
        sys.exit(1)
    print("✔ 全部 %d 处模型引用都能在服务器上找到对应文件。" % ok)


if __name__ == "__main__":
    main()
