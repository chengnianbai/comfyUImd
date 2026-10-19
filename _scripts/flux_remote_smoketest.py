# -*- coding: utf-8 -*-
"""
远程 ComfyUI：等待 Manager 下载队列结束 -> 用 Flux checkpoint 跑冒烟测试 -> 取回测试图。
用途：验证远程服务器上的 FLUX 模型文件是否完整可用（截断的 safetensors 会在加载时报
      'incomplete metadata, file not fully covered'）。

用法:
  python flux_remote_smoketest.py [--base URL] [--ckpt "FLUX1\\flux1-dev-fp8.safetensors"]
                                  [--wait-only] [--out 输出png路径]
"""
import argparse, json, ssl, sys, time, urllib.request, urllib.parse, uuid, os

DEFAULT_BASE = "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016"
DEFAULT_OUT = r"D:\xiaobai-claude code\comfyUImd\系列-夜市百相簿/02-角色/闻灯/设定图\_flux_smoketest.png"


def ctx():
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    return c


def api(base, path, c, method="GET", payload=None, timeout=60):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(base + path, method=method, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=c) as r:
        raw = r.read()
        return json.loads(raw.decode()) if raw else {}


def ts():
    return time.strftime("%H:%M:%S")


# 上一次失败精确停在这个字节数（C 盘写满）。超过它就说明模型目录已指向大盘。
TRUNCATION_MARK = 10_737_418_235


def ckpt_size(base, c, name="flux1-dev-fp8"):
    """从 /experiment/models/checkpoints 读目标文件当前字节数"""
    try:
        lst = api(base, "/experiment/models/checkpoints", c, timeout=25)
        for x in lst:
            if name in x.get("name", ""):
                return x.get("size", 0)
    except Exception:
        pass
    return 0


def wait_queue(base, c, max_min=90):
    """等 Manager 下载队列跑完，同时报文件大小"""
    t0 = time.time()
    passed_mark = False
    while time.time() - t0 < max_min * 60:
        st = api(base, "/manager/queue/status", c, timeout=20)
        sz = ckpt_size(base, c)
        if sz > TRUNCATION_MARK and not passed_mark:
            passed_mark = True
            print(ts(), "*** 已突破 10.74GB 截断点 -> 联接/大盘生效 ***", flush=True)
        print(ts(), "size=%.2fGB" % (sz / 2**30), st, flush=True)
        if st.get("done_count", 0) >= 1 and st.get("in_progress_count", 0) == 0 \
                and not st.get("is_processing"):
            print(ts(), "queue finished, final size=%.2fGB" % (sz / 2**30), flush=True)
            return True
        time.sleep(30)
    print(ts(), "queue wait timeout", flush=True)
    return False


def wait_ram_release(base, c, max_min=10):
    """等写盘结束、内存释放（Manager 是先把整个文件读进内存再落盘）"""
    t0 = time.time()
    while time.time() - t0 < max_min * 60:
        try:
            s = api(base, "/system_stats", c, timeout=20)["system"]
            free = s["ram_free"] / 2**30
        except Exception:
            time.sleep(15)
            continue
        print(ts(), "ram_free=%.2fGB" % free, flush=True)
        if free > 55:
            return True
        time.sleep(20)
    print(ts(), "ram release timeout (继续尝试加载)", flush=True)
    return False


def smoke_test(base, c, ckpt, out_path):
    prompt = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "2": {"class_type": "CLIPTextEncode",
              "inputs": {"text": "a cozy night market street in Chengdu, warm lantern light, cinematic",
                         "clip": ["1", 1]}},
        "3": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
        "4": {"class_type": "KSampler",
              "inputs": {"seed": 42, "steps": 20, "cfg": 1.0, "sampler_name": "euler",
                         "scheduler": "simple", "denoise": 1.0,
                         "model": ["1", 0], "positive": ["2", 0], "negative": ["2", 0],
                         "latent_image": ["3", 0]}},
        "5": {"class_type": "VAEDecode", "inputs": {"samples": ["4", 0], "vae": ["1", 2]}},
        "6": {"class_type": "SaveImage",
              "inputs": {"filename_prefix": "flux_smoketest", "images": ["5", 0]}},
    }
    res = api(base, "/prompt", c, method="POST",
              payload={"prompt": prompt, "client_id": str(uuid.uuid4())}, timeout=120)
    pid = res.get("prompt_id")
    print(ts(), "submitted", pid, "node_errors=", res.get("node_errors"), flush=True)

    img = None
    for _ in range(120):
        try:
            h = api(base, "/history/" + pid, c, timeout=30)
        except Exception as e:
            print("poll err", e, flush=True)
            time.sleep(5)
            continue
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("status_str") == "error":
                for m in st.get("messages", []):
                    if m[0] == "execution_error":
                        d = m[1]
                        print("ERROR node", d.get("node_type"), d.get("exception_type"))
                        print(d.get("exception_message"))
                return False
            for out in h[pid]["outputs"].values():
                if "images" in out:
                    img = out["images"][0]
            if img:
                break
        time.sleep(3)

    if not img:
        print(ts(), "no image produced", flush=True)
        return False

    q = urllib.parse.urlencode({"filename": img["filename"],
                                "subfolder": img.get("subfolder", ""),
                                "type": img.get("type", "output")})
    with urllib.request.urlopen(base + "/view?" + q, timeout=120, context=c) as r:
        data = r.read()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(data)
    print(ts(), "OK saved", out_path, len(data), "bytes", flush=True)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--ckpt", default="FLUX1\\flux1-dev-fp8.safetensors")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--wait-only", action="store_true")
    a = ap.parse_args()
    c = ctx()
    base = a.base.rstrip("/")
    ok = wait_queue(base, c)
    if a.wait_only or not ok:
        return
    final = ckpt_size(base, c)
    print(ts(), "file size = %.2fGB (期望 ~17.25GB)" % (final / 2**30), flush=True)
    if final < 17_000_000_000:
        print(ts(), "!! 文件仍不完整，跳过冒烟测试", flush=True)
        return
    wait_ram_release(base, c)
    smoke_test(base, c, a.ckpt, a.out)


if __name__ == "__main__":
    main()
