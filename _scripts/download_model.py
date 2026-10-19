"""下载 majicMIX realistic v7 到 ComfyUI 的 checkpoints 目录。

特点：
- 多源自动降级（hf-mirror → huggingface → gh-proxy）
- 断点续传：中断后重跑会从已下载的字节位置继续
- 实时打印速度与剩余时间
- 下完自动校验 safetensors 头部，确认真的是 SD 1.5 权重
"""

import json
import os
import socket
import struct
import sys
import time
import urllib.error
import urllib.request

REPO = "digiplay/majicMIX_realistic_v7"
FILE = "majicmixRealistic_v7.safetensors"
DEST_DIR = r"D:\xiaobai-claude code\ComfyUI\models\checkpoints"
DEST = os.path.join(DEST_DIR, FILE)

SOURCES = [
    ("hf-mirror", "https://hf-mirror.com"),
    ("aifasthub", "https://aifasthub.com"),
    ("gh-proxy", "https://gh-proxy.com/https://huggingface.co"),
]

socket.setdefaulttimeout(60)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
CHUNK = 1024 * 256


def human(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return "%.1f %s" % (n, u)
        n /= 1024.0
    return "%.1f TB" % n


def probe(base):
    """返回 (是否可用, 总大小)。用 Range 取 1 字节。"""
    url = "%s/%s/resolve/main/%s" % (base, REPO, FILE)
    req = urllib.request.Request(url, headers=dict(UA, Range="bytes=0-0"))
    try:
        with urllib.request.urlopen(req) as r:
            cr = r.headers.get("Content-Range", "")
            total = int(cr.split("/")[-1]) if "/" in cr else int(r.headers.get("Content-Length", 0))
            return True, total, url
    except Exception as e:
        print("     探测失败: %s" % str(e)[:110])
        return False, 0, url


def download(url, total):
    os.makedirs(DEST_DIR, exist_ok=True)
    done = os.path.getsize(DEST) if os.path.exists(DEST) else 0
    if done and total and done >= total:
        print("   已有完整文件，跳过下载")
        return True

    t0 = time.time()
    base0 = done
    last = t0
    fails = 0
    while True:
        if total and done >= total:
            break
        req = urllib.request.Request(url, headers=dict(UA))
        if done:
            req.add_header("Range", "bytes=%d-" % done)
        try:
            with urllib.request.urlopen(req) as r:
                if total and r.status == 200 and done:
                    print("   服务器不支持续传，从头开始")
                    done = 0
                    base0 = 0
                    t0 = time.time()
                with open(DEST, "ab" if done else "wb") as f:
                    while True:
                        chunk = r.read(CHUNK)
                        if not chunk:
                            break
                        f.write(chunk)
                        done += len(chunk)
                        now = time.time()
                        if now - last >= 5:
                            last = now
                            spd = (done - base0) / max(now - t0, 1)
                            pct = (done / total * 100) if total else 0
                            eta = ((total - done) / spd) if (spd and total) else 0
                            print("   %6.2f%%  %s / %s   %s/s   剩余 %d 分 %02d 秒" % (
                                pct, human(done), human(total) if total else "?",
                                human(spd), int(eta // 60), int(eta % 60)))
                            sys.stdout.flush()
            if total and done >= total:
                break
            fails += 1
            if fails > 40:
                print("   重试次数过多，放弃")
                return False
            print("   连接中断，3 秒后从 %s 继续（第 %d 次）" % (human(done), fails))
            time.sleep(3)
        except urllib.error.HTTPError as e:
            if e.code == 416 and total and done >= total:
                break
            print("   HTTP %s，3 秒后重试" % e.code)
            fails += 1
            time.sleep(3)
            if fails > 40:
                return False
        except Exception as e:
            fails += 1
            print("   出错(%s)，3 秒后从 %s 继续" % (str(e)[:70], human(done)))
            time.sleep(3)
            if fails > 40:
                return False

    spd = (done - base0) / max(time.time() - t0, 1)
    print("   完成：%s，平均 %s/s" % (human(done), human(spd)))
    return True


def verify():
    """校验 safetensors 头部，确认是 SD 1.5 checkpoint。"""
    size = os.path.getsize(DEST)
    with open(DEST, "rb") as f:
        raw = f.read(8)
        if len(raw) < 8:
            print("   校验失败：文件过小")
            return False
        n = struct.unpack("<Q", raw)[0]
        if n <= 0 or n > 100 * 1024 * 1024:
            print("   校验失败：不是 safetensors（头部长度异常 %d）" % n)
            return False
        header = json.loads(f.read(n).decode("utf-8"))
    keys = list(header.keys())
    tag = {
        "unet": any(k.startswith("model.diffusion_model") for k in keys),
        "clip": any(k.startswith("cond_stage_model") for k in keys),
        "vae": any(k.startswith("first_stage_model") for k in keys),
    }
    print("   文件大小：%s（%d 字节）" % (human(size), size))
    print("   张量数量：%d" % (len(keys) - 1))
    print("   组件：U-Net=%s  CLIP=%s  VAE=%s" % (tag["unet"], tag["clip"], tag["vae"]))
    return all(tag.values())


def main():
    print("目标位置：%s" % DEST)
    print()
    for name, base in SOURCES:
        print(">> 尝试源：%s" % name)
        ok, total, url = probe(base)
        if not ok:
            continue
        print("   可用，文件总大小 %s" % human(total))
        if download(url, total):
            print()
            print(">> 校验文件")
            if verify():
                print()
                print("全部完成，模型已就绪。")
                return 0
            print("   校验未通过，文件可能损坏")
            return 1
    print()
    print("所有源都不可用。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
