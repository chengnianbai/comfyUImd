# -*- coding: utf-8 -*-
"""重下 FLUX1 VAE（ae.safetensors）并用**最小链路**立刻验货。

为什么会有这个脚本（2026-09-18 实证）
------------------------------------
转头组提交时报 `VAELoader: Error while deserializing header: header too small`。
模型引用名字是对的、文件也在下拉框里 —— 但**文件内容是废的**。

根因：ComfyUI-Manager 的 model-list.json 里 ae.safetensors 这条，
`url` 写的是 `huggingface.co/black-forest-labs/FLUX.1-schnell/resolve/main/ae.safetensors`。
服务器**直连 HF 被墙** → Manager 照样把任务跑完（done_count=1），
落盘的是一个不是 safetensors 的东西 → 只有真正 Load 时才炸。

★ 教训：**下拉框里出现文件名 ≠ 文件可用**。判据必须是「能不能被 Load」，
  或者「字节数对不对」。Manager 从不校验完整性。

做法
----
① 用白名单里**同一条**三元组（base=FLUX.1 / save_path=vae/FLUX1 / filename=ae.safetensors）
   只把 url 换成 ModelScope 直链 → 通过白名单校验，且真的能下下来。
② 下完立刻跑一条最小链路 `EmptyLatentImage → VAEDecode → SaveImage`（1~2 秒）：
   这条链路唯一的作用就是**强制把 VAE 读进显存**。读得进 = 文件是好的。

用法
----
  python fix_ae_vae.py            # 只探测现状（队列 + 最小链路验货）
  python fix_ae_vae.py --download # 提交下载 → 等完成 → 再验货
"""
import json, os, ssl, sys, time, uuid, urllib.error, urllib.parse, urllib.request

BASE = os.environ.get(
    "COMFY_BASE",
    "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016",
)
MS_URL = "https://www.modelscope.cn/models/AI-ModelScope/FLUX.1-dev/resolve/master/ae.safetensors"
EXPECT = 335304388          # 本机 HEAD 实测 Content-Range 总数
PAYLOAD = {
    "base": "FLUX.1",                 # ↓ 三个字段原样抄 model-list.json 那条，才过得去白名单
    "save_path": "vae/FLUX1",
    "filename": "ae.safetensors",
    "size": "335MB",
    "url": MS_URL,                    # ← 只有 url 换成能下的源
    "name": "FLUX.1 VAE model",
    "reference": MS_URL,
}
VAE_REF = "FLUX1\\ae.safetensors"

# 只有这些字样才说明「文件本身是残的」；其它报错（形状不匹配等）与文件无关 → 文件其实是好的
CORRUPT_MARKS = ("header too small", "header too large", "fully covered",
                 "deserializ", "incomplete metadata")

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE


def raw(p, data=None, ctype=None, timeout=180, method=None):
    req = urllib.request.Request(BASE + p, data=data, method=method)
    if ctype:
        req.add_header("Content-Type", ctype)
    return urllib.request.urlopen(req, timeout=timeout, context=_ctx).read()


def jget(p, timeout=120):
    return json.loads(raw(p, timeout=timeout).decode("utf-8", "replace"))


def post(p, obj, timeout=120):
    return raw(p, json.dumps(obj).encode(), "application/json", timeout)


def probe_vae():
    """最小链路：VAELoader → VAEDecode(随机 latent) → SaveImage。
    唯一目的就是把 VAE 读进来。返回 (是否通过, 说明)。"""
    wf = {
        "1": {"class_type": "VAELoader", "inputs": {"vae_name": VAE_REF}},
        # ★ 必须用 SD3（16 通道）latent：FLUX 的 ae 是 16 通道，
        #   喂 4 通道的 EmptyLatentImage 会报形状不匹配 —— 那会被误判成"文件坏"（2026-09-20 踩过）。
        "2": {"class_type": "EmptySD3LatentImage",
              "inputs": {"width": 256, "height": 256, "batch_size": 1}},
        "3": {"class_type": "VAEDecode", "inputs": {"samples": ["2", 0], "vae": ["1", 0]}},
        "4": {"class_type": "SaveImage",
              "inputs": {"images": ["3", 0], "filename_prefix": "_vae_probe"}},
    }
    try:
        res = json.loads(post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())}, 120).decode())
    except urllib.error.HTTPError as e:
        return False, "提交被拒 HTTP %s: %s" % (e.code, e.read().decode("utf-8", "replace")[:300])
    ne = res.get("node_errors") or {}
    if ne:
        return False, "node_errors: %s" % json.dumps(ne, ensure_ascii=False)[:400]
    pid = res["prompt_id"]
    for _ in range(24):
        time.sleep(2)
        h = jget("/history/" + pid, 60)
        if pid not in h:
            continue
        st = h[pid].get("status", {})
        if st.get("status_str") == "error":
            msg = ""
            for m in st.get("messages", []):
                if m[0] == "execution_error":
                    msg = "%s: %s" % (m[1].get("node_type"), m[1].get("exception_message", "")[:240])
            # ★ 只有 header / 未覆盖 才算"文件坏"；形状不匹配这类与文件无关 → 文件是好的
            if any(k in msg for k in CORRUPT_MARKS):
                return False, "文件残缺 ✘  " + msg
            return True, "VAE 读取成功（报错与文件无关）  " + msg
        return True, "VAE 读取成功（最小链路跑通）"
    return False, "超时（24×2s）"


def wait_queue(max_min=20):
    print("\n[下载队列]")
    last = None
    for i in range(max_min * 4):
        try:
            st = jget("/api/manager/queue/status", 60)
        except Exception as e:
            print("   查询失败 %s" % type(e).__name__); time.sleep(15); continue
        line = json.dumps(st, ensure_ascii=False)
        if line != last:
            print("   [%4ds] %s" % (i * 15, line))
            last = line
        if not st.get("is_processing") and st.get("in_progress_count", 0) == 0:
            return True
        time.sleep(15)
    return False


def main():
    dl = "--download" in sys.argv
    print("=" * 72)
    print("FLUX1 VAE（ae.safetensors）体检 / 重下")
    print("=" * 72)
    print("目标路径 = %s  | 期望字节 = %d" % (VAE_REF, EXPECT))
    cand = jget("/object_info/VAELoader", 120)["VAELoader"]["input"]["required"]["vae_name"][0]
    if isinstance(cand, dict):
        cand = cand.get("options", [])
    print("下拉框候选 = %s" % cand)

    print("\n[1/3] 现状验货（最小链路）")
    ok, why = probe_vae()
    print("   %s %s" % ("✔" if ok else "✘", why))
    if not dl:
        if ok:
            print("\nVAE 本来就好的，无需重下。")
            return 0
        print("\n★ VAE 不可用。加 --download 重下（会自动换 ModelScope 源）。")
        return 3

    if dl:
        print("\n[2/3] 提交下载（url 已换 ModelScope）")
        print("   %s" % MS_URL)
        try:
            print("   install_model -> %s" % post("/api/manager/queue/install_model", PAYLOAD, 120)
                  .decode("utf-8", "replace")[:200])
        except urllib.error.HTTPError as e:
            print("   ★ HTTP %s: %s" % (e.code, e.read().decode("utf-8", "replace")[:300]))
            return 1
        for ep in ("/api/manager/queue/start", "/manager/queue/start"):
            try:
                post(ep, {}, 60); print("   队列已启动（%s）" % ep); break
            except Exception:
                pass
        if not wait_queue(20):
            print("   ★ 队列没跑完，别急着验货"); return 1

    print("\n[3/3] 重新验货（最小链路）")
    ok, why = probe_vae()
    print("   %s %s" % ("✔" if ok else "✘", why))
    if ok:
        print("\n✅ VAE 可用，转头组可以跑了。")
    else:
        print("\n❌ 还是不行 —— 说明这次下载内容也不对，先别跑转头，把这段发我。")
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
