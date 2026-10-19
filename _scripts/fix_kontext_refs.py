# -*- coding: utf-8 -*-
"""定点修复【闻灯 转头】组三个模型引用 —— 只改 widgets_values，其它一律不动。

为什么会坏
----------
模型文件是好的，坏的是**工作流里写的文件名**。
用户若从"旧标签页"保存工作流，浏览器会把内存里的旧内容整份写回服务器，
于是装配器 17:33 推上去的正确引用被覆盖回旧名 → 提交时 `value not in list`，
前端就弹「请下载模型，或打开节点进行替换」。

正确值从服务器 /object_info 实测得到（不是猜的）：
  UNETLoader  unet_name  = 'FLUX1\\flux1-schnell.safetensors'   ← Kontext 借的白名单槽位名
  DualCLIP    clip_name1 = 't5\\t5xxl_fp8_e4m3fn_scaled.safetensors'
  DualCLIP    clip_name2 = 'clip_l.safetensors'
  VAELoader   vae_name   = 'FLUX1\\ae.safetensors'

用法
----
  python fix_kontext_refs.py            # 只读：打印差异，不写
  python fix_kontext_refs.py --push     # 备份 → 回写服务器 → 回读校验
"""
import io, json, os, ssl, sys, time, urllib.error, urllib.parse, urllib.request

BASE = os.environ.get(
    "COMFY_BASE",
    "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016",
)
HERE = os.path.dirname(os.path.abspath(__file__))
WF = "夜市百相簿-主工作流.json"
PATH = "/api/userdata/workflows%2F" + urllib.parse.quote(WF)

# 只改这三处：node_id -> (widgets_values 的第几个, 正确值, 说明)
FIX = {
    1024: (0, "FLUX1\\flux1-schnell.safetensors", "UNETLoader / unet_name"),
    1025: (0, "t5\\t5xxl_fp8_e4m3fn_scaled.safetensors", "DualCLIPLoader / clip_name1"),
    1026: (0, "FLUX1\\ae.safetensors", "VAELoader / vae_name"),
}

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE


def raw(path, body=None, ctype=None, timeout=180, method=None):
    req = urllib.request.Request(BASE + path, data=body, method=method)
    if ctype:
        req.add_header("Content-Type", ctype)
    with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
        return r.read()


def fetch():
    return json.loads(raw(PATH, timeout=120).decode("utf-8"))


def main():
    push = "--push" in sys.argv
    wf = fetch()
    print("服务器 id = %s | 节点 %d | 链接 %d | 分组 %d"
          % (wf.get("id"), len(wf["nodes"]), len(wf["links"]), len(wf.get("groups", []))))

    byid = {n["id"]: n for n in wf["nodes"]}
    changed = []
    for nid, (idx, want, label) in FIX.items():
        n = byid.get(nid)
        if n is None:
            print("  !! 找不到节点 #%s（结构变了？先别推，回读确认）" % nid)
            return 2
        wv = list(n.get("widgets_values") or [])
        cur = wv[idx] if idx < len(wv) else None
        mark = "OK  " if cur == want else "改 →"
        print("  %s #%-5s %-28s %r  ->  %r" % (mark, nid, label, cur, want))
        if cur != want:
            wv[idx] = want
            n["widgets_values"] = wv
            changed.append((nid, label, cur, want))

    if not changed:
        print("\n三个引用本来就是对的，服务器没问题。")
        return 0

    if not push:
        print("\n（只读模式，未写服务器。加 --push 才写入）")
        return 0

    # ① 先落盘备份，再写
    bk = os.path.join(HERE, "_wf", "_server_before_refpatch_%s.json"
                      % time.strftime("%m%d_%H%M%S"))
    io.open(bk, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
    print("\n备份 -> %s" % os.path.basename(bk))

    body = json.dumps(wf, ensure_ascii=False).encode("utf-8")
    raw(PATH + "?overwrite=true", body, "application/json", 300, "POST")
    print("已写入服务器，回读校验…")

    back = fetch()
    bid = {n["id"]: n for n in back["nodes"]}
    ok = True
    for nid, (idx, want, label) in FIX.items():
        got = (bid[nid].get("widgets_values") or [None] * (idx + 1))[idx]
        good = got == want
        ok = ok and good
        print("  %s #%-5s %r" % ("√" if good else "×", nid, got))
    print("节点 %d / 链接 %d / 分组 %d"
          % (len(back["nodes"]), len(back["links"]), len(back.get("groups", []))))
    print("\n%s" % ("✅ 三处引用已修正并回读通过" if ok else "❌ 回读不一致，检查日志"))
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
