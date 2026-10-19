# -*- coding: utf-8 -*-
"""
远程 ComfyUI：确保 FLUX.1 [dev] fp8 一体化 checkpoint 就位，并验证真的能用。

流程（幂等，可反复运行；关机/断网后重启机器直接重跑即可）：
  1. 探测服务器在线
  2. 目标文件已存在且 >= 17GB  -> 跳过下载，直接验证
  3. 否则提交 ModelScope 下载任务；若队列里已有任务在跑则不重复提交
  4. 轮询：实时打印文件大小，突破 10.74GB 会打标记
     （10,737,418,235 字节 = C 盘时代的 ENOSPC 截断点；越过它说明模型目录已指向大盘）
  5. 队列结束后校验大小 -> 等 RAM 释放（Manager 是整文件读进内存再落盘）
     -> 跑 Flux 冒烟测试 -> 取回 PNG

对网络抖动（504 / 连接重置）容错：连续失败达到 --offline-limit 次即判定
「服务器离线」并退出（退出码 2），避免像上次那样直接抛栈崩掉。

用法:
  python flux_remote_get.py                  # 全流程
  python flux_remote_get.py --status         # 只体检，不提交任何任务
  python flux_remote_get.py --verify-only    # 只做验证（假定文件已就位）
  python flux_remote_get.py --queue-status   # 看下载队列 + 最近下载日志
"""
import argparse
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

DEFAULT_BASE = "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016"
DEFAULT_OUT = r"D:\xiaobai-claude code\comfyUImd\系列-夜市百相簿/02-角色/闻灯/设定图\_flux_smoketest.png"
CKPT_SUB = "FLUX1"
CKPT_FILE = "flux1-dev-fp8.safetensors"
CKPT_NAME = CKPT_SUB + "\\" + CKPT_FILE          # API 里要用列表原文（Windows 反斜杠）
CKPT_API_URL = ("https://modelscope.cn/models/Comfy-Org/flux1-dev"
                "/resolve/master/flux1-dev-fp8.safetensors")
CKPT_BYTES_MIN = 17_000_000_000                  # 认定"完整"的下限
TRUNCATION_MARK = 10_737_418_235                 # C 盘 ENOSPC 截断点
OFFLINE_EXIT = 2


def ssl_ctx():
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    return c


def ts():
    return time.strftime("%H:%M:%S")


class Offline(Exception):
    """连续多次网络失败 -> 服务器不可达"""


class Client:
    def __init__(self, base, offline_limit=6):
        self.base = base.rstrip("/")
        self.c = ssl_ctx()
        self.offline_limit = offline_limit
        self.fails = 0

    def _raw(self, path, method="GET", payload=None, timeout=30):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.base + path, method=method, data=data,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=self.c) as r:
                return r.read()
        except Exception as e:
            self.fails += 1
            print(ts(), "[warn] %s %s -> %s (%d/%d)" %
                  (method, path, type(e).__name__, self.fails, self.offline_limit), flush=True)
            if self.fails >= self.offline_limit:
                raise Offline("连续 %d 次失败，服务器离线" % self.fails)
            raise

    def json(self, path, method="GET", payload=None, timeout=30):
        raw = self._raw(path, method, payload, timeout)
        self.fails = 0
        return json.loads(raw.decode("utf-8", "ignore")) if raw else {}

    def text(self, path, timeout=30):
        raw = self._raw(path, "GET", None, timeout)
        self.fails = 0
        return raw.decode("utf-8", "ignore")


def model_size(cli, name="flux1-dev-fp8"):
    """目标 checkpoint 当前字节数（不存在 -> 0）"""
    try:
        for x in cli.json("/experiment/models/checkpoints", timeout=25):
            if name in x.get("name", ""):
                return x.get("size", 0)
    except Offline:
        raise
    except Exception:
        pass
    return 0


def queue_status(cli):
    return cli.json("/manager/queue/status", timeout=20)


def recent_download_log(cli, n=15):
    """最近和下载相关的服务器日志行"""
    try:
        j = json.loads(cli.text("/internal/logs/raw", timeout=30))
        ents = j.get("entries", [])
    except Exception:
        return []
    keys = ("Install model", "Download error", "successful", "Errno",
            "incomplete", "modelscope", "hf-mirror", "huggingface")
    out = [e for e in ents if any(k in e.get("m", "") for k in keys)]
    return [(e.get("t", "")[11:19], e.get("m", "").strip()[:220]) for e in out[-n:]]


def health(cli):
    s = cli.json("/system_stats", timeout=25)
    sysd = s.get("system", {})
    dev = (s.get("devices") or [{}])[0]
    ram_used = (sysd.get("ram_total", 0) - sysd.get("ram_free", 0)) / 2**30
    print("  版本      :", sysd.get("comfyui_version"))
    print("  显存      : %.1fGB 可用 / %.1fGB 总" %
          (dev.get("vram_free", 0) / 2**30, dev.get("vram_total", 0) / 2**30))
    print("  内存      : %.1fGB 已用 / %.1fGB 总" %
          (ram_used, sysd.get("ram_total", 0) / 2**30))
    try:
        fp = cli.json("/internal/folder_paths", timeout=20)
        print("  checkpoints 根:", fp.get("checkpoints"))
    except Exception:
        pass


def submit_download(cli):
    payload = {
        "name": "Comfy Org/FLUX.1 [dev] Checkpoint model (fp8) via ModelScope",
        "type": "checkpoint",
        "base": "FLUX.1",
        "save_path": "checkpoints/" + CKPT_SUB,
        "filename": CKPT_FILE,
        "url": CKPT_API_URL,
        "size": "17.25GB",
    }
    cli.json("/manager/queue/install_model", method="POST", payload=payload, timeout=40)
    print(ts(), "已提交下载任务:", CKPT_FILE)
    cli.json("/manager/queue/start", method="POST", payload={}, timeout=30)
    print(ts(), "队列已启动")


def wait_queue(cli, max_min=90):
    t0 = time.time()
    marked = False
    while time.time() - t0 < max_min * 60:
        st = queue_status(cli)
        sz = model_size(cli)
        if sz > TRUNCATION_MARK and not marked:
            marked = True
            print(ts(), "*** 已突破 10.74GB 截断点 -> 模型目录指向大盘，成功 ***", flush=True)
        print(ts(), "size=%.2fGB  %s" % (sz / 2**30, st), flush=True)
        if st.get("done_count", 0) >= 1 and st.get("in_progress_count", 0) == 0 \
                and not st.get("is_processing"):
            print(ts(), "队列结束，最终 size=%.2fGB" % (sz / 2**30))
            return True
        time.sleep(30)
    print(ts(), "等待超时")
    return False


def wait_ram_release(cli, max_min=10):
    t0 = time.time()
    while time.time() - t0 < max_min * 60:
        try:
            free = cli.json("/system_stats", timeout=20)["system"]["ram_free"] / 2**30
        except Exception:
            time.sleep(15)
            continue
        print(ts(), "ram_free=%.2fGB" % free, flush=True)
        if free > 55:
            return True
        time.sleep(20)
    print(ts(), "内存释放等待超时（仍继续尝试加载）")
    return False


def smoke_test(cli, ckpt, out_path, wait_min=35):
    """用目标 checkpoint 跑一张 1024² 的图 —— 权重是否完整可用的唯一硬证据。

    注意：任务会进入 ComfyUI 的同一个执行队列，如果用户此时正在跑 SDXL，
    本任务会排在后面。因此等待时间可调（--smoke-wait-min），期间会报告排队情况。
    """
    prompt = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "2": {"class_type": "CLIPTextEncode",
              "inputs": {"text": "a cozy night market street in Chengdu, warm lantern light, cinematic",
                         "clip": ["1", 1]}},
        "3": {"class_type": "EmptyLatentImage",
              "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
        "4": {"class_type": "KSampler",
              "inputs": {"seed": 42, "steps": 20, "cfg": 1.0, "sampler_name": "euler",
                         "scheduler": "simple", "denoise": 1.0,
                         "model": ["1", 0], "positive": ["2", 0], "negative": ["2", 0],
                         "latent_image": ["3", 0]}},
        "5": {"class_type": "VAEDecode", "inputs": {"samples": ["4", 0], "vae": ["1", 2]}},
        "6": {"class_type": "SaveImage",
              "inputs": {"filename_prefix": "flux_smoketest", "images": ["5", 0]}},
    }
    res = cli.json("/prompt", method="POST",
                   payload={"prompt": prompt, "client_id": str(uuid.uuid4())}, timeout=120)
    pid = res.get("prompt_id")
    errs = res.get("node_errors") or {}
    print(ts(), "已提交冒烟测试", pid, "node_errors =", errs if errs else "无")

    img = None
    deadline = time.time() + wait_min * 60
    tick = 0
    while time.time() < deadline:
        tick += 1
        try:
            h = cli.json("/history/" + pid, timeout=30)
        except Offline:
            raise
        except Exception:
            time.sleep(5)
            continue
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("status_str") == "error":
                for m in st.get("messages", []):
                    if m[0] == "execution_error":
                        d = m[1]
                        print("!! 执行错误 node=%s type=%s" % (d.get("node_type"), d.get("exception_type")))
                        print("  ", (d.get("exception_message") or "").strip()[:400])
                return False
            for out in h[pid]["outputs"].values():
                if "images" in out:
                    img = out["images"][0]
            if img:
                break
        elif tick % 20 == 0:
            try:
                q = cli.json("/queue", timeout=20)
                print(ts(), "等待出图... 排队 %d 个 / 运行中 %d 个"
                      % (len(q.get("queue_pending") or []), len(q.get("queue_running") or [])),
                      flush=True)
            except Exception:
                pass
        time.sleep(3)

    if not img:
        print(ts(), "没有产出图片")
        return False

    q = urllib.parse.urlencode({"filename": img["filename"],
                                "subfolder": img.get("subfolder", ""),
                                "type": img.get("type", "output")})
    with urllib.request.urlopen(cli.base + "/view?" + q, timeout=180, context=cli.c) as r:
        data = r.read()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(data)
    print(ts(), "OK 已保存", out_path, len(data), "bytes")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--ckpt", default=CKPT_NAME)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--status", action="store_true", help="只体检，不提交任务")
    ap.add_argument("--queue-status", action="store_true", help="队列 + 最近下载日志")
    ap.add_argument("--verify-only", action="store_true", help="假定文件已就位，只做验证")
    ap.add_argument("--smoke-wait-min", type=int, default=35,
                    help="冒烟测试最长等待分钟数（用户同时在跑 SDXL 时排队会久）")
    ap.add_argument("--offline-limit", type=int, default=6)
    a = ap.parse_args()

    cli = Client(a.base, offline_limit=a.offline_limit)
    try:
        print("=== 体检", a.base, "===")
        health(cli)
        sz = model_size(cli)
        print("  目标文件  : %s = %.2fGB (%d bytes)" % (CKPT_FILE, sz / 2**30, sz))
        st = queue_status(cli)
        print("  下载队列  :", st)

        if a.queue_status:
            print("--- 最近下载日志 ---")
            for t, m in recent_download_log(cli, 25):
                print(t, m)
            return 0

        if a.status:
            return 0 if sz >= CKPT_BYTES_MIN else 1

        # --- 阶段 1：确保文件就位 ---
        if sz < CKPT_BYTES_MIN and not a.verify_only:
            if st.get("in_progress_count", 0) == 0 and not st.get("is_processing"):
                print(ts(), "文件不完整 -> 提交下载")
                submit_download(cli)
            else:
                print(ts(), "文件不完整，但队列里已有任务在跑 -> 继续等")
            if not wait_queue(cli):
                return 1

        sz = model_size(cli)
        print(ts(), "文件最终大小 = %.2fGB" % (sz / 2**30))
        if sz < CKPT_BYTES_MIN:
            print("!! 文件仍不完整（期望 ~17.25GB），跳过冒烟测试")
            for t, m in recent_download_log(cli, 10):
                print("   ", t, m)
            return 1

        # --- 阶段 2：验证 ---
        wait_ram_release(cli)
        print(ts(), "提交验证任务（会进入 ComfyUI 同一执行队列，若你正在出 SDXL 会排在后面，"
                    "最长等 %d 分钟）" % a.smoke_wait_min)
        ok = smoke_test(cli, a.ckpt, a.out, wait_min=a.smoke_wait_min)
        print("RESULT:", "PASS" if ok else "FAIL")
        return 0 if ok else 1

    except Offline as e:
        print(ts(), "OFFLINE:", e)
        print("服务器当前不可达（可能已关机）。开机后重新运行本脚本即可自动接上，无需重下已完成的部分。")
        return OFFLINE_EXIT


if __name__ == "__main__":
    sys.exit(main())
