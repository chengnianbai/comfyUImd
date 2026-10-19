# -*- coding: utf-8 -*-
"""闻灯 · Flux Kontext 环境准备（A 方案）

三个子命令，对应作战计划的第 0/1/2 步：

    python kontext_setup.py check      # 盘点：节点是否齐、模型是否已落地（10 秒）
    python kontext_setup.py download   # 下载 4 个模型文件（10-20 分钟，唯一的长耗时项）
    python kontext_setup.py smoke      # 校验大小 + 冒烟测试出 1 张（约 1 分钟）

★ 为什么要单独一个脚本：
  2026-09-17 那天在开机状态下硬撞了三轮 img2img，全部白跑。根因是机器缺
  「姿势控制 / 身份锁定」能力。本脚本把"补能力"这一步固化成一条命令，
  避免下次开机又现场摸索 —— 豆是按开机时长烧的。

★ 下载必须走 ModelScope。服务器直连 huggingface.co 被墙，Manager 会「跑完但没文件」。
★ Manager 下载**不校验完整性** → 下完一定跑 smoke。
"""
import urllib.request, urllib.parse, json, ssl, os, sys, time

BASE = os.environ.get("COMFY_BASE", "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016")
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE

ROOT = r"D:\xiaobai-claude code\comfyUImd"
WF_DIR = os.path.join(ROOT, "_scripts", "_wf")
SRC_BASE_IMG = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "v23-脸部三视角", "闻灯v23-脸部正面-成品_00001_.png")
UPLOAD_NAME = "wendeng_v23_face_base.png"
OUTDIR = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "kontext-转头")

# ---- 要下的 4 个文件：(本地文件名, 目标目录, ModelScope 模型 id, 仓库内路径, 期望大小GB下限) ----
FILES = [
    ("flux1-dev-kontext_fp8_scaled.safetensors", "diffusion_models",
     "Comfy-Org/flux1-kontext-dev_ComfyUI",
     "split_files/diffusion_models/flux1-dev-kontext_fp8_scaled.safetensors", 10.5),
    ("t5xxl_fp8_e4m3fn_scaled.safetensors", "text_encoders",
     "comfyanonymous/flux_text_encoders",
     "t5xxl_fp8_e4m3fn_scaled.safetensors", 4.0),
    ("clip_l.safetensors", "text_encoders",
     "comfyanonymous/flux_text_encoders",
     "clip_l.safetensors", 0.15),
    ("ae.safetensors", "vae",
     "Comfy-Org/flux1-dev",
     "split_files/vae/ae.safetensors", 0.25),
]

# ---- Kontext 需要的节点 ----
NEED_NODES = ["UNETLoader", "DualCLIPLoader", "VAELoader", "LoadImage", "VAEEncode",
              "CLIPTextEncode", "FluxGuidance", "ReferenceLatent", "KSampler",
              "VAEDecode", "SaveImage", "EmptySD3LatentImage", "ConditioningZeroOut",
              "FluxKontextImageScale"]

# ---- 编辑指令：★ 写成「指令」而不是画面描述，一轮只改一件事 ----
PROMPT_L90 = ("Turn his head to a full 90-degree LEFT profile, so the camera sees only the left side "
              "of his face. Keep the same person, the same messy wavy black hair, the same eyebrows, "
              "nose and jawline, the same unretouched skin texture with visible pores and the same "
              "small mole, the same lighting, the same white background and the same faded blue shirt. "
              "Do not restyle, do not smooth the skin, do not change his identity.")
PROMPT_R90 = PROMPT_L90.replace("LEFT profile", "RIGHT profile") \
                       .replace("only the left side", "only the right side")


def raw(p, data=None, ctype=None, timeout=120):
    h = {}
    if ctype:
        h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


def jget(p, timeout=180):
    return json.loads(raw(p, None, None, timeout).decode("utf-8", "replace"))


def post(p, obj, timeout=120):
    return raw(p, json.dumps(obj).encode(), "application/json", timeout)


def upload(local, name):
    import uuid
    data = open(local, "rb").read()
    bd = "----wb" + uuid.uuid4().hex
    body = b""
    for k, v in (("overwrite", "true"), ("type", "input"), ("subfolder", "")):
        body += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                 % (bd, k, v)).encode()
    body += ("--%s\r\nContent-Disposition: form-data; name=\"image\"; filename=\"%s\"\r\n"
             "Content-Type: image/png\r\n\r\n" % (bd, name)).encode()
    body += data + ("\r\n--%s--\r\n" % bd).encode()
    return urllib.request.urlopen(
        urllib.request.Request(BASE + "/upload/image", data=body,
                               headers={"Content-Type": "multipart/form-data; boundary=%s" % bd}),
        timeout=300, context=ctx).read().decode()


def ls_dir(folder):
    """返回 {文件名: 字节数}；目录不存在时返回 {}"""
    for ep in ("/internal/files/%s" % folder, "/models/%s" % folder):
        try:
            d = jget(ep, 60)
        except Exception:
            continue
        out = {}
        items = d if isinstance(d, list) else d.get("files", [])
        for f in items:
            if isinstance(f, dict):
                out[f.get("name")] = f.get("size", 0)
            else:
                out[str(f)] = 0
        return out
    return {}


# ---- 预计要占用的总空间（用体积下限之和，实际会略大 10~20%）----
NEED_GB = sum(f[4] for f in FILES)


def probe_disk():
    """尽力探测数据盘余量。

    ★ 老实说：ComfyUI 官方 API **不暴露磁盘余量**，这里只能三路试探 + 打印找到的东西。
      探不到就必须让用户去云控制台看一眼 —— 宁可多花 10 秒，也别下到一半撑爆盘
      （撑爆的后果不是"下载失败"，而是实例卡死在 I/O 上，你还得开着机去救）。
    """
    found = []

    def walk(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, path + "." + str(k))
        elif isinstance(o, (list, tuple)):
            for i, v in enumerate(o[:8]):
                walk(v, path + "[%d]" % i)
        else:
            kl = path.lower()
            if any(w in kl for w in ("disk", "free_space", "available", "fs_")):
                found.append((path, o))
            elif "free" in kl and isinstance(o, (int, float)) and o > 1e8:
                found.append((path, o))

    for ep in ("/system_stats", "/system_stats/", "/manager/queue/status"):
        try:
            walk(jget(ep, 60))
        except Exception:
            pass
    return found


def report_disk():
    print("\n[磁盘余量]")
    found = probe_disk()
    if found:
        for p, v in found[:8]:
            try:
                print("   %-46s %8.1f GB" % (p, float(v) / 1e9))
            except Exception:
                print("   %-46s %s" % (p, v))
    else:
        print("   ★ 服务器 API 不暴露磁盘余量，探不到。")
    print("   本轮要占约 %.1f GB（4 个文件的下限之和，实际会大 10~20%%）。" % NEED_GB)
    print("   ⚠️ 若数据盘余量 < %.0f GB，**先去控制台扩容或删模型**，否则下到一半会撑爆。"
          % (NEED_GB * 1.3))
    print("      可删的闲置模型：SD1.5（2.1GB）、majicmix（2.1GB）—— 闻灯已不用这两个。")


# ==================== check ====================
def cmd_check():
    print("=" * 70)
    print("盘点：这台机器现在到底有什么")
    print("=" * 70)
    alln = jget("/object_info", 240)
    print("\n[节点] 共 %d 个" % len(alln))
    missing = []
    for n in NEED_NODES:
        ok = n in alln
        if not ok:
            missing.append(n)
        print("   %-24s %s" % (n, "✔ 有" if ok else "✘ 缺"))
    if missing:
        print("\n   ★ 缺 %d 个节点：%s" % (len(missing), missing))
        print("     → Kontext 原生链路需要这些节点。缺的话要先更新 ComfyUI 本体")
        print("       （Manager → 重启），再回来跑本脚本。")
    else:
        print("\n   ✔ Kontext 所需节点齐全")

    print("\n[模型落地情况]")
    for fn, folder, mid, path, min_gb in FILES:
        m = ls_dir(folder)
        size = m.get(fn, 0)
        got = size / 1e9 if size else 0
        mark = "✔" if got >= min_gb else ("△ 偏小" if size else "✘ 缺")
        print("   %-44s %-18s %s  %.2f GB" % (fn, folder, mark, got))

    for extra in ("ipadapter", "controlnet", "clip_vision", "loras"):
        m = ls_dir(extra)
        print("   [参考] %-16s %d 项" % (extra, len(m)))

    report_disk()
    return alln


# ==================== download ====================
def cmd_download():
    print("=" * 70)
    print("下载 4 个模型文件（走 ModelScope）")
    print("=" * 70)
    todo = []
    for fn, folder, mid, path, min_gb in FILES:
        size = ls_dir(folder).get(fn, 0)
        if size / 1e9 >= min_gb:
            print("   已有，跳过：%s (%.2f GB)" % (fn, size / 1e9))
        else:
            todo.append((fn, folder, mid, path, min_gb))
    if not todo:
        print("\n全部已就绪，无事可做。")
        return

    # ★ 按体积**从小到大**下：万一磁盘中途撑爆，先到手的都是完整可用的小文件
    #   （clip_l / ae / t5xxl），只剩最大的 Kontext UNet 待补 —— 而不是全都下了半截。
    todo.sort(key=lambda x: x[4])
    print("\n待下载 %d 个（已按体积升序，小的先完成）：" % len(todo))
    for fn, folder, mid, path, min_gb in todo:
        print("   %-44s -> %-18s ≥%.2f GB" % (fn, folder, min_gb))
    print("   合计约 %.1f GB。下载期间**不要关机**，下完立刻跑 verify。" % sum(x[4] for x in todo))
    report_disk()

    # ---- 尝试 Manager 的模型下载接口（端点名各版本不同，逐个试）----
    for fn, folder, mid, path, min_gb in todo:
        url = "https://www.modelscope.cn/models/%s/resolve/master/%s" % (mid, path)
        print("\n---- %s ----" % fn)
        print("   URL: %s" % url)
        payload = {"url": url, "save_path": folder, "filename": fn,
                   "modelname": fn, "model": url}
        ok = False
        for ep in ("/api/manager/queue/install_model", "/manager/queue/install_model"):
            try:
                r = post(ep, payload, 120).decode("utf-8", "replace")
                print("   [%s] -> %s" % (ep, r[:200]))
                ok = True
                break
            except Exception as e:
                print("   [%s] 失败: %s" % (ep, type(e).__name__))
        if not ok:
            print("   ★ 自动下载接口不可用 → 改用通道 B（在服务器终端手动跑）：")
            print('     modelscope download --model %s "%s" --local_dir /models/%s/'
                  % (mid, path, folder))

    for ep in ("/manager/queue/start", "/api/manager/queue/start"):
        try:
            post(ep, {}, 60)
            print("\n已触发 Manager 队列：" % ())
            break
        except Exception:
            pass

    print("\n轮询进度（每 15 秒一次，最多 40 次）：")
    for i in range(40):
        time.sleep(15)
        try:
            st = jget("/manager/queue/status", 60)
        except Exception as e:
            print("   第 %d 次：查询失败 %s" % (i + 1, type(e).__name__)); continue
        print("   [%4ds] %s" % ((i + 1) * 15, json.dumps(st, ensure_ascii=False)))
        if not st.get("is_processing") and st.get("in_progress_count", 0) == 0:
            break

    print("\n★ Manager 下载不校验完整性，务必接着跑：python kontext_setup.py smoke")


# ==================== smoke ====================
def cmd_smoke():
    print("=" * 70)
    print("校验大小 + 冒烟测试")
    print("=" * 70)
    alln = jget("/object_info", 240)
    miss = [n for n in NEED_NODES if n not in alln]
    if miss:
        print("★ 节点缺失，冒烟测试无法进行：%s" % miss); sys.exit(1)

    bad = []
    for fn, folder, mid, path, min_gb in FILES:
        size = ls_dir(folder).get(fn, 0)
        got = size / 1e9
        mark = "✔" if got >= min_gb else "✘"
        if got < min_gb:
            bad.append(fn)
        print("   %-44s %s %.2f GB (期望≥%.2f)" % (fn, mark, got, min_gb))
    if bad:
        print("\n★ 以下文件不完整（Manager 下载常见截断）：%s" % bad)
        print("  → 用通道 B 的 modelscope 命令重下，不要硬跑。"); sys.exit(1)

    # 上传身份基图
    os.makedirs(WF_DIR, exist_ok=True)
    dst = os.path.join(WF_DIR, "kontext_base_v23.png")
    import shutil
    shutil.copy(SRC_BASE_IMG, dst)
    print("\n上传身份基图 ->", upload(dst, UPLOAD_NAME)[:140])

    def build(prompt, prefix):
        return {
            "1": {"class_type": "UNETLoader", "inputs": {
                "unet_name": FILES[0][0], "weight_dtype": "default"}},
            "2": {"class_type": "DualCLIPLoader", "inputs": {
                "clip_name1": FILES[1][0], "clip_name2": FILES[2][0], "type": "flux"}},
            "3": {"class_type": "VAELoader", "inputs": {"vae_name": FILES[3][0]}},
            "4": {"class_type": "LoadImage", "inputs": {"image": UPLOAD_NAME, "upload": "image"}},
            "5": {"class_type": "FluxKontextImageScale", "inputs": {"image": ["4", 0]}},
            "6": {"class_type": "VAEEncode", "inputs": {"pixels": ["5", 0], "vae": ["3", 0]}},
            "7": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
            "8": {"class_type": "FluxGuidance", "inputs": {"conditioning": ["7", 0], "guidance": 3.0}},
            "9": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["8", 0], "latent": ["6", 0]}},
            "10": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["2", 0]}},
            # ★ denoise 1.0：从纯噪声开始，参考图走 ReferenceLatent 进 conditioning（不是 img2img）
            "11": {"class_type": "KSampler", "inputs": {
                "model": ["1", 0], "positive": ["9", 0], "negative": ["10", 0],
                "latent_image": ["6", 0], "seed": 20260917, "steps": 20, "cfg": 1.0,
                "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
            "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["3", 0]}},
            "13": {"class_type": "SaveImage", "inputs": {"images": ["12", 0], "filename_prefix": prefix}},
        }

    print("\n提交冒烟测试（左侧 90°）...")
    res = json.loads(post("/prompt", {"prompt": build(PROMPT_L90, "闻灯Kontext-冒烟-左90"),
                                      "client_id": "smoke"}, 120).decode())
    if res.get("node_errors"):
        print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:3000])
        sys.exit(1)
    pid = res["prompt_id"]
    print("  prompt_id =", pid)

    t0, done = time.time(), None
    for _ in range(90):
        time.sleep(5)
        h = jget("/history/" + pid, 60)
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("status_str") == "error":
                for m in st.get("messages", []):
                    if m[0] == "execution_error":
                        print("★ ERROR 节点=%s: %s" % (m[1].get("node_type"),
                                                       m[1].get("exception_message", "")[:400]))
                sys.exit(1)
            done = h[pid].get("outputs", {}); break
    if done is None:
        print("★ 超时"); sys.exit(1)
    print("  完成，用时 %.0f 秒" % (time.time() - t0))

    os.makedirs(OUTDIR, exist_ok=True)
    for nid, o in done.items():
        for im in o.get("images", []):
            q = urllib.parse.urlencode({"filename": im["filename"],
                                        "subfolder": im.get("subfolder", ""),
                                        "type": im.get("type", "output")})
            p = os.path.join(OUTDIR, im["filename"])
            open(p, "wb").write(raw("/view?" + q, None, None, 300))
            print("  已保存 %s" % p)
    print("\n★ 看那张图：① 头真的转过 90° 了吗？ ② 还是同一个人吗？")
    print("  两者缺一 → 暂停后续生成，按 docs/workflow.md 核对输入与连线；当前决定和进度见 docs/decisions.md、docs/roadmap.md。")


# ==================== verify ====================
def cmd_verify():
    """只校验：节点是否齐 + 四个文件大小是否达标。不跑图。"""
    print("=" * 70)
    print("校验 Kontext 环境（节点 + 四个文件大小）")
    print("=" * 70)
    alln = jget("/object_info", 240)
    miss = [n for n in NEED_NODES if n not in alln]
    print("\n[节点]")
    for n in NEED_NODES:
        print("   %-24s %s" % (n, "✔" if n in alln else "✘"))
    bad = []
    print("\n[模型文件]")
    for fn, folder, mid, path, min_gb in FILES:
        size = ls_dir(folder).get(fn, 0)
        got = size / 1e9
        ok = got >= min_gb
        if not ok:
            bad.append(fn)
        print("   %-44s %-18s %s %.2f GB (期望≥%.2f)" % (fn, folder, "✔" if ok else "✘", got, min_gb))
    if miss or bad:
        print("\n★ 不通过：")
        if miss:
            print("   缺节点 %s → Kontext 原生链路跑不起来" % miss)
        if bad:
            print("   文件不完整 %s → Manager 下载常见截断，用通道 B 的 modelscope 命令重下，别硬跑" % bad)
        sys.exit(1)
    print("\n✔ Kontext 环境就绪，可以跑转头分支。")
    return 0


if __name__ == "__main__":
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "check").lower()
    FUNC = {"check": cmd_check, "download": cmd_download,
            "verify": cmd_verify, "smoke": cmd_smoke}
    if cmd not in FUNC:
        print(__doc__); print("可用子命令：%s" % sorted(FUNC)); sys.exit(1)

    # 实例离线时先拦一道：否则每个请求都要等到超时，白等好几轮
    try:
        r = urllib.request.urlopen(BASE + "/system_stats", timeout=15, context=ctx)
        online = r.status == 200 and "system" in r.read().decode("utf-8", "replace")
    except Exception:
        online = False
    if not online:
        print("★ 实例未开机（网关无正常响应）—— 先开机再跑 kontext_setup.py %s" % cmd)
        sys.exit(4)

    try:
        sys.exit(FUNC[cmd]() or 0)
    except Exception as e:
        print("★ 执行失败：%s: %s" % (type(e).__name__, e))
        print("  如果反复出现，把上面这段发我。")
        sys.exit(1)
