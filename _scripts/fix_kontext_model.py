# -*- coding: utf-8 -*-
"""重下 Kontext UNet（残件）并用**最小链路**立刻验货。

为什么会有这个脚本（2026-09-20 实证）
------------------------------------
转头组截图里那句「请下载模型」有两层含义，必须先分辨：
  ① 引用名写错（不带子目录）→ 报 `value not in list`，一眼可见；
  ② 引用名对、文件也在下拉框里，但**内容残缺** → 只在真正 Load 时才炸：
     `Error while deserializing header: incomplete metadata, file not fully covered`
本脚本针对第 ② 种。

根因（服务器日志实证）：2026-09-18 17:18:05 那次下载
`Download error: <kontext url> / [Errno 28] No space left on device`
—— Kontext 与 ae 都是**磁盘写满时留下的碎片**，Manager 却把队列标成 done。

★ Manager 下载器源码（glob/manager_downloader.py）：
      data = response.read()            # 整包先读进内存
      with open(save_path, 'wb') as f:  # 'wb' → 先截断再写
          f.write(data)
  三条硬结论：**① 无 Range 续传**（残件只能整包重下）；
              **② `Installation was successful.` 是唯一可靠的成功信号**；
              **③ 写盘那一刻必须一次性有 11.9GB 空闲。**

落盘位置为什么叫 flux1-schnell.safetensors
------------------------------------------
白名单（model-list.json）里 FLUX.1 的 diffusion_models/FLUX1 槽位只有
flux1-schnell* 这一族名字。Kontext 不在表里 → 借槽位落盘，
工作流里的引用名也跟着写成 `FLUX1\\flux1-schnell.safetensors`（内容是 Kontext）。
**别去"修正"这个文件名**，改名 = 白名单过不去。

用法
----
  python fix_kontext_model.py            # 只探测：引用名 / 候选 / 最小链路验货
  python fix_kontext_model.py --download # 提交下载 → 等完（约 30-40 分钟）→ 再验货
"""
import json, os, ssl, sys, time, uuid, urllib.error, urllib.parse, urllib.request

BASE = os.environ.get(
    "COMFY_BASE",
    "https://gw-efb56d453d484597a1b8ddfc86156262.cn-beijing.aigclinks.com:8016",
)
MS_URL = ("https://www.modelscope.cn/models/Comfy-Org/flux1-kontext-dev_ComfyUI"
          "/resolve/master/split_files/diffusion_models/flux1-dev-kontext_fp8_scaled.safetensors")
MIN_GB = 11.0
# ↓ 三个字段原样抄白名单那条（base=FLUX.1 / diffusion_models/FLUX1 / flux1-schnell.safetensors）
PAYLOAD = {
    "base": "FLUX.1",
    "save_path": "diffusion_models/FLUX1",
    "filename": "flux1-schnell.safetensors",
    "size": "23.8GB",
    "url": MS_URL,
    "name": "FLUX.1 Schnell model",
    "reference": MS_URL,
}

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


def combo(node, key):
    """从服务器下拉框取真实值 —— 手写反斜杠会被层层转义弄错（踩过）。"""
    d = jget("/object_info/" + urllib.parse.quote(node), 180)
    try:
        c = d[node]["input"]["required"][key][0]
    except Exception:
        c = d[node]["input"]["optional"][key][0]
    if isinstance(c, dict):
        c = c.get("options", [])
    return c


CORRUPT_MARKS = ("header too small", "header too large", "fully covered",
                 "deserializ", "incomplete metadata")


def probe_unet(unet, vae):
    """最小链路：UNETLoader → 1 步采样 → VAEDecode(ae) → SaveImage。

    唯一目的是**逼 UNETLoader 真去读那个文件**。
    判定规则：报 header / not fully covered = 文件是残的；
             跑通 = 文件完好。
    """
    wf = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": "default"}},
        "2": {"class_type": "DualCLIPLoader", "inputs": {"clip_name1": combo("DualCLIPLoader", "clip_name1")[1],
                                                          "clip_name2": combo("DualCLIPLoader", "clip_name2")[0],
                                                          "type": "flux"}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "probe", "clip": ["2", 0]}},
        "4": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["3", 0]}},
        "5": {"class_type": "EmptySD3LatentImage", "inputs": {"width": 64, "height": 64, "batch_size": 1}},
        "6": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "positive": ["3", 0], "negative": ["4", 0], "latent_image": ["5", 0],
            "seed": 1, "steps": 1, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple",
            "denoise": 1.0}},
        "7": {"class_type": "VAELoader", "inputs": {"vae_name": vae}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["7", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "_unet_probe"}},
    }
    try:
        res = json.loads(post("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())}, 180).decode())
    except urllib.error.HTTPError as e:
        return False, "提交被拒 HTTP %s: %s" % (e.code, e.read().decode("utf-8", "replace")[:300])
    ne = res.get("node_errors") or {}
    if ne:
        return False, "node_errors: %s" % json.dumps(ne, ensure_ascii=False)[:400]
    pid = res["prompt_id"]
    t0 = time.time()
    for _ in range(90):
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
            if any(k in msg for k in CORRUPT_MARKS):
                return False, "文件残缺 ✘  " + msg
            return True, "UNET 读取成功（%.0f 秒，报错与文件无关）" % (time.time() - t0)
        return True, "UNET 读取成功，最小链路跑通（%.0f 秒）" % (time.time() - t0)
    return False, "超时（90×2s）"


def wait_queue(max_min=70):
    print("\n[下载队列]  每 30 秒报一次进度；Kontext 11.9GB 按 ~5.9MB/s 约 34 分钟")
    last, t0 = None, time.time()
    for i in range(max_min * 2):
        try:
            st = jget("/api/manager/queue/status", 60)
        except Exception as e:
            print("   查询失败 %s" % type(e).__name__); time.sleep(30); continue
        line = json.dumps(st, ensure_ascii=False)
        if line != last:
            print("   [%5.0fs] %s" % (time.time() - t0, line))
            last = line
        if not st.get("is_processing") and st.get("in_progress_count", 0) == 0:
            return True
        time.sleep(30)
    return False


def tail_log(keys=("Install model", "Download error", "No space", "Errno", "successful", "Queued works"),
             n=14):
    """★ 唯一可靠的成功判据在日志里：`Installation was successful.`"""
    try:
        E = json.loads(raw("/internal/logs/raw", timeout=180).decode("utf-8", "replace"))["entries"]
    except Exception as e:
        print("   日志读取失败：%s" % type(e).__name__); return
    import re
    clean = lambda s: re.sub(r"\x1b\[[0-9;]*m", "", s).rstrip()
    hits = [e for e in E if any(k in clean(e["m"]) for k in keys)]
    print("\n[下载日志（权威判据）]")
    for e in hits[-n:]:
        print("   [%s] %s" % (e["t"][11:19], clean(e["m"])[:200]))


def main():
    dl = "--download" in sys.argv
    print("=" * 72)
    print("Kontext UNet 体检 / 重下")
    print("=" * 72)
    unets = combo("UNETLoader", "unet_name")
    print("UNETLoader 候选 = %s" % unets)
    unet = [x for x in unets if "schnell" in x][0]     # 借槽位名，内容是 Kontext
    vaes = combo("VAELoader", "vae_name")
    vae = [x for x in vaes if "ae.safetensors" in x][0]
    print("目标 UNET = %r   |  VAE = %r  (期望 ≥ %.1f GB)" % (unet, vae, MIN_GB))

    print("\n[1/4] 现状验货（最小链路强制 Load）")
    ok, why = probe_unet(unet, vae)
    print("   %s %s" % ("✔" if ok else "✘", why))

    if not dl:
        if ok:
            print("\nUNET 本来就好的，无需重下。")
            return 0
        print("\n★ UNET 不可用。加 --download 重下（url 已换 ModelScope）。")
        return 3

    print("\n[2/4] 提交下载")
    print("   %s" % MS_URL)
    try:
        print("   install_model -> %s"
              % post("/api/manager/queue/install_model", PAYLOAD, 120).decode("utf-8", "replace")[:200])
    except urllib.error.HTTPError as e:
        print("   ★ HTTP %s: %s" % (e.code, e.read().decode("utf-8", "replace")[:300]))
        return 1
    for ep in ("/api/manager/queue/start", "/manager/queue/start"):
        try:
            post(ep, {}, 60); print("   队列已启动（%s）" % ep); break
        except Exception:
            pass

    print("\n[3/4] 等待下载")
    if not wait_queue(70):
        print("   ★ 队列没跑完（或超时）—— 别急着验货"); tail_log(); return 1
    tail_log()

    print("\n[4/4] 重新验货（最小链路）")
    ok, why = probe_unet(unet, vae)
    print("   %s %s" % ("✔" if ok else "✘", why))
    if ok:
        print("\n✅ Kontext 可用，转头组可以跑了：")
        print('   python run_wf.py "夜市百相簿-主工作流.json" "闻灯Kontext" final')
    else:
        print("\n❌ 还是不行 —— 把[下载日志]那段一起发我。")
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
