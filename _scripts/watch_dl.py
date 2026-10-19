# -*- coding: utf-8 -*-
"""
Kontext 四件套下载监控（只读，零成本）。

背景：ComfyUI-Manager V3.41 的 /api/manager/queue/status 只给
      「总任务数 / 已完成 / 进行中」，**没有百分比**。
      所以这里用「Loader 候选列表有没有出现目标文件名」作为落地判据 —— 这是权威信号，
      因为 Loader 的 combo 列表就是 ComfyUI 实际能加载到的文件。

用法：
    python watch_dl.py            # 前台循环，每 90 秒一条，最多 70 分钟
    python watch_dl.py --once     # 只打一条

日志追加到 _scripts/_dl_watch.log（UTF-8）。
"""
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get(
    "COMFY_BASE",
    "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016",
)
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_dl_watch.log")

# 目标文件（全部到位才算完成）
WANT = {
    "diffusion_models": "flux1-schnell.safetensors",   # ★ 实为 Kontext（借白名单槽位）
    "vae":              "ae.safetensors",
}
DONE_POOL = {
    "text_encoders": ["clip_l.safetensors", "t5xxl_fp8_e4m3fn_scaled.safetensors"],
}

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE


def _get(path, timeout=45):
    try:
        r = urllib.request.urlopen(BASE + path, timeout=timeout, context=_ctx)
        return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:200]
    except Exception as e:
        return None, "%s %s" % (type(e).__name__, e)


def _combo(node, key):
    s, b = _get("/object_info/" + node, 60)
    if s != 200:
        return []
    try:
        return json.loads(b)[node]["input"]["required"][key][0]
    except Exception:
        return []


def snapshot():
    """返回 (一行文本, 是否全部到位)"""
    if _get("/system_stats", 25)[0] != 200:
        return "实例掉线（网关返回非 200）", False

    q = _get("/api/manager/queue/status", 30)[1][:120]

    unet = _combo("UNETLoader", "unet_name")
    vae = _combo("VAELoader", "vae_name")
    clip = _combo("DualCLIPLoader", "clip_name1")

    # 归一化：吃掉子目录分隔符差异（FLUX1\xxx 与 xxx）
    def has(lst, name):
        return any(str(x).replace("/", "\\").endswith(str(name).replace("/", "\\")) for x in lst)

    ok_unet = has(unet, WANT["diffusion_models"])
    ok_vae = has(vae, WANT["vae"])
    ok_clip = all(has(clip, n) for n in DONE_POOL["text_encoders"])

    marks = []
    marks.append("[文本编码器] %s  %s" % ("OK" if ok_clip else "缺", clip))
    marks.append("[VAE ae]     %s  %s" % ("OK" if ok_vae else "缺", vae))
    marks.append("[Kontext]    %s  %s" % ("OK" if ok_unet else "缺", unet))

    line = "%s | 队列 %s | %s" % (time.strftime("%H:%M:%S"), q, "  ".join(marks))
    return line, (ok_unet and ok_vae and ok_clip)


def main():
    once = "--once" in sys.argv
    deadline = time.time() + 70 * 60
    last = None
    while True:
        line, done = snapshot()
        if line != last:            # 只在有变化时记录，避免刷屏
            last = line
            print(line, flush=True)
            try:
                with open(LOG, "a", encoding="utf-8") as f:
                    f.write(line + ("    ★★ 全部到位\n" if done else "\n"))
            except Exception:
                pass
        if once or done:
            if done:
                print(">>> 四件套全部到位，可以跑『转头』组了。", flush=True)
            break
        if time.time() > deadline:
            print(">>> 监控超时（70 分钟），退出。", flush=True)
            break
        time.sleep(90)


if __name__ == "__main__":
    main()
