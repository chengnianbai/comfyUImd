# -*- coding: utf-8 -*-
"""夜市百相簿 · 开机一次性编排（oneshot）—— 开机只跑这一条命令，跑完就关机

════════════════════ 两条铁律（都是花钱买来的） ════════════════════
【一】豆按【开机时长】烧，跟你有没有在跑图**毫无关系**。
      所以开机窗口只做三件事：① 一次提交所有要跑的图 ② 补上该补的模型 ③ 拉回产物后立刻关机。
      一切决策与自检都在**开机之前**于本地（零成本）做完。

【二】**「夜市百相簿」是主工作流**（用户 2026-09-18 定）。
      这是一个小说项目的角色资产生产线，所有管线都并入同一个工作流、按角色分区，
      不再散成「闻灯-Flux脸部三视角 / -迭代转头 / -质感修复对照 / -Kontext转头」一堆文件。
      装配由 build_master_wf.py 负责，**原有 24 个节点与 id 一律保留不动**。

════════════════════════════ 用法 ════════════════════════════
    python oneshot.py wait      等实例上线（15s 一次，默认最多 25 分钟）
    python oneshot.py setup  ★ 配置模式：更新工作流 + 下 Kontext，**不出图**（图你自己在浏览器点）
    python oneshot.py all       全流程 p1 → p2 → p3（含并行下载）→ p4 → report（含自动出图）
    python oneshot.py quick     快路径：只出图、不下载（约 2~4 分钟就能关机）
    python oneshot.py p1        盘点：GPU / 节点 / 模型落地 / Kontext 四件套 / 磁盘余量
    python oneshot.py p2        装配主工作流 → 传基图 → 本地验证 → 推送到服务器
    python oneshot.py p3        跑图：闻灯脸部正面（SDXL img2img 0.30 / 无重绘）→ 自动拼 1:1 图
    python oneshot.py p4        校验 Kontext 完整性 → 跑转头三条（左90/右90/左45）
    python oneshot.py baseline  ★ 部署 Flux 组（原地重建推送：删掉 v23 依赖节点）→ 跑正脸基准 草稿 + 成品
    python oneshot.py pushbase  只做上面那一步推送，不出图
    python oneshot.py p5        只跑正脸基准图的草稿，最快看一眼
    python oneshot.py faces     只跑身份锁三视角（正脸/右脸/左脸）的草稿
    python oneshot.py report    本地产物清单 + 服务器现状 + 收尾检查单

★★ 警告：p2 / all / quick / setup 都会跑 build_master_wf.py（装配器），
   而装配器只重建「全身 / 脸部 / 转头」3 块，**不认识 Flux 文生图组**（含身份锁），
   会把那 53 个节点整组删掉。要用装配器前先看清提示。
   「正脸基准改用 Flux 自产」这类改动**只能用 baseline / pushbase**（原地追加，零删除）。

════════════════════════ 产物去哪 ════════════════════════════
    系列-夜市百相簿/02-角色/闻灯/设定图\\主工作流\\     ← 所有分支的成品都落这里
    系列-夜市百相簿/02-角色/闻灯/设定图\\_1比1_*.png   ← 自动拼的 1:1 质感对比图（判断质感**只能**看这个）
"""
import os, sys, ssl, json, time, glob, subprocess, urllib.request

BASE = os.environ.get("COMFY_BASE", "https://gw-efb56d453d484597a1b8ddfc86156262.cn-beijing.aigclinks.com:8016")
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE

ROOT = r"D:\xiaobai-claude code\comfyUImd"
SCRIPTS = os.path.join(ROOT, "_scripts")
PY = r"C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe"
PIC = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图")

MASTER = "夜市百相簿-主工作流.json"
OUTDIR = os.path.join(PIC, "主工作流")
DL_LOG = os.path.join(SCRIPTS, "_kontext_download.log")

V23_FRONT = os.path.join(PIC, "v23-脸部三视角", "闻灯v23-脸部正面-成品_00001_.png")
FLUXV2_FRONT = os.path.join(PIC, "flux-v2-脸部", "闻灯FluxV2-脸部正面-成品_00001_.png")

T0 = time.time()
# ★ 2026-09-20：把 BASE 注入子进程环境 —— 各脚本里写死的网关 hash 有**两个不同的值**
#   （add_flux_baseline_group.py 是 gw-efb56d…，run_wf.py 是 gw-496303…）。
#   不注入的话，「推送」和「跑图」可能打到**两个不同的地址**，其中一个必然是死的，
#   而现象是「推送成功但跑出来还是旧图」这种最难查的错。
#   现在唯一的真相 = oneshot.py 顶部的 BASE（或外部设的 COMFY_BASE 环境变量）。
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", COMFY_BASE=BASE)


def el():
    return "%4.1f 分" % ((time.time() - T0) / 60)


def head(t):
    print("\n" + "=" * 74)
    print("== [%s] %s" % (el(), t))
    print("=" * 74)


def raw(p, timeout=30):
    return urllib.request.urlopen(BASE + p, timeout=timeout, context=ctx).read()


def jget(p, timeout=120):
    return json.loads(raw(p, timeout).decode("utf-8", "replace"))


def online():
    """只有 200 且是合法 JSON 才算在线（实例掉线时网关返 400 + HTML 页）"""
    try:
        r = urllib.request.urlopen(BASE + "/system_stats", timeout=15, context=ctx)
        return r.status == 200 and "system" in r.read().decode("utf-8", "replace")
    except Exception:
        return False


def sh(args, timeout=None, quiet=False):
    if not quiet:
        print("  $ %s" % " ".join(os.path.basename(a) if i else a for i, a in enumerate(args)))
    p = subprocess.run(args, cwd=SCRIPTS, capture_output=True, env=ENV, timeout=timeout)
    out = (p.stdout or b"").decode("utf-8", "replace") + (p.stderr or b"").decode("utf-8", "replace")
    for line in out.splitlines():
        print("    " + line)
    return p.returncode


# ─────────────────────── 阶段 0：等实例 ───────────────────────
# 可用环境变量 ONESHOT_WAIT_MIN 覆盖等待分钟数（默认见下），便于演练/排查。
WAIT_MIN = int(os.environ.get("ONESHOT_WAIT_MIN", "20"))


def cmd_wait(limit_min=None):
    limit_min = WAIT_MIN if limit_min is None else limit_min
    head("阶段 0 · 等待实例上线（最多 %d 分钟）" % limit_min)
    if online():
        print("  实例已在线。")
        return 0
    print("  实例未就绪。**请现在去云平台开机**（不开机不会烧豆，但会白等）。")
    print("  想先不跑，直接按 Ctrl+C 中断。")
    t0, n = time.time(), 0
    while (time.time() - t0) < limit_min * 60:
        time.sleep(15); n += 1
        if online():
            print("  ✔ 第 %d 次探测（%ds）→ 已上线，用时 %.1f 分钟" % (n, n * 15, (time.time() - t0) / 60))
            return 0
        print("    …已等 %3ds   （实例还没起来，继续等）" % int(time.time() - t0))
    print("  ★ 超时未上线。开机后重跑即可。")
    return 1


# ─────────────────────── 阶段 1：盘点 ───────────────────────
def cmd_p1():
    head("阶段 1 · 盘点")
    st = jget("/system_stats", 60)
    dev = (st.get("devices") or [{}])[0]
    print("  GPU  %s   显存空闲 %.1f GB" % (dev.get("name"), (dev.get("vram_free") or 0) / 1e9))
    print("  ComfyUI %s" % st.get("system", {}).get("comfyui_version"))
    print("\n  ── 服务器上现有的工作流 ──")
    try:
        for name in jget("/api/userdata?dir=workflows", 60):
            print("     %s" % name)
    except Exception as e:
        print("     查询失败 %s" % type(e).__name__)
    print("\n  ── Kontext 四件套落地情况（缺的话 p4 前会下载）──")
    return sh([PY, "kontext_setup.py", "check"], timeout=300)


# ─────────────────────── 阶段 2：装配并推送主工作流 ───────────────────────
def cmd_p2():
    head("阶段 2 · 装配主工作流 → 本地验证 → 推送")
    print("  说明：先本地重建各区块（用最新提示词），再装配进「%s」并推送。" % MASTER)
    print("        --fetch 会先拉服务器现行版作基线，你在浏览器里的改动不会被覆盖。\n")

    rc1 = sh([PY, "push_flux_texture_wf.py", "--local"], timeout=300)
    rc2 = sh([PY, "push_kontext_wf.py", "--local"], timeout=300)
    if rc1 != 0 or rc2 != 0:
        print("  ★ 区块构建失败（rc=%d/%d），停止装配。" % (rc1, rc2))
        return 1

    print()
    rc = sh([PY, "build_master_wf.py", "--fetch", "--push"], timeout=600)
    if rc != 0:
        print("  ★ 装配/推送失败（rc=%d）。" % rc)
        print("     若提示拉取失败 → 实例没开或工作流名不对，先确认 p1 的列表。")
        return rc

    print()
    return sh([PY, "verify_master.py"], timeout=180)


# ─────────────────────── 阶段 3：跑图（含并行下载） ───────────────────────
def cmd_p3(with_download=True):
    head("阶段 3 · 出图：闻灯脸部正面（SDXL img2img，无重绘）")
    print("  一次提交跑完成品（不在浏览器点「运行」——那会把全部 7 条分支一起跑）\n")

    dl = None
    if with_download:
        print("  ── 同时后台启动 Kontext 下载（网络任务，与出图并行，不额外占开机时间）──")
        dl = subprocess.Popen([PY, "kontext_setup.py", "download"], cwd=SCRIPTS,
                              stdout=open(DL_LOG, "w", encoding="utf-8"),
                              stderr=subprocess.STDOUT, env=ENV)
        print("     日志 → %s\n" % DL_LOG)

    rc = sh([PY, "run_wf.py", MASTER, "闻灯-脸部正面", "final", OUTDIR], timeout=2400)
    if rc != 0:
        print("  ★ 出图失败（rc=%d）。" % rc)
    else:
        print("\n  ── 自动拼 1:1 对比图（整图缩放会把质感差异抹平，判断质感只认这个）──")
        sheet_face()
        sheet_hair()

    if dl is not None:
        print("\n  ── 等 Kontext 下载结束 ──")
        dl.wait()
        try:
            lines = open(DL_LOG, encoding="utf-8", errors="replace").read().strip().splitlines()
            print("     下载日志尾部：")
            for l in lines[-14:]:
                print("       " + l)
        except Exception as e:
            print("     读日志失败 %s" % type(e).__name__)
    return rc


def _find(label):
    for pat in ("%s*_00001_.png" % label, "%s*.png" % label):
        c = sorted(glob.glob(os.path.join(OUTDIR, pat)))
        if c:
            return c[0]
    return None


def sheet_face():
    box = "0.30,0.18,0.70,0.58"
    items = [("v23 基准（SDXL）", "身份已确认 基准", V23_FRONT),
             ("flux-v2 旧版（FLUX）", "你评价：质感不够", FLUXV2_FRONT)]
    for lab, tag in [("闻灯-脸部正面-成品", "★ 脸部块（SDXL img2img 0.30 / 无重绘）")]:
        f = _find(lab)
        if f:
            items.append((tag, "主工作流", f))
    if len(items) <= 2:
        print("     没有可拼的新产物，跳过")
        return 1
    args = [PY, "zoom_sheet.py", os.path.join(PIC, "_1比1_脸部_主工作流.png"), "560", box]
    args += ["%s|%s|%s" % (a, b, c) for a, b, c in items]
    return sh(args, quiet=True)


def sheet_hair():
    box = "0.22,0.02,0.78,0.36"
    items = [("v23 基准（SDXL）", "干爽飞散 基准", V23_FRONT),
             ("flux-v2 旧版（FLUX）", "油亮定型", FLUXV2_FRONT)]
    for lab, tag in [("闻灯-脸部正面-成品", "★ 脸部块（无重绘）")]:
        f = _find(lab)
        if f:
            items.append((tag, "主工作流", f))
    if len(items) <= 2:
        return 1
    args = [PY, "zoom_sheet.py", os.path.join(PIC, "_1比1_头发_主工作流.png"), "560", box]
    args += ["%s|%s|%s" % (a, b, c) for a, b, c in items]
    return sh(args, quiet=True)


# ─────────────────────── 阶段 4：Kontext 转头 ───────────────────────
def cmd_p4():
    head("阶段 4 · 校验 Kontext 完整性 → 跑主图左右侧脸")
    rc = sh([PY, "kontext_setup.py", "verify"], timeout=300)
    if rc != 0:
        print("  ★ 校验不通过 → 不跑转头。先按上面的提示补文件（kontext_setup.py download）。")
        return rc

    print()
    rc = sh([PY, "run_wf.py", MASTER, "闻灯主图-左侧脸,闻灯主图-右侧脸", "final", OUTDIR], timeout=2400)
    if rc != 0:
        print("  ★ 转头出图失败（rc=%d）。" % rc)
        return rc

    print("\n  ── 拼转头对比图 ──")
    confirmed = os.path.join(PIC, "闻灯正脸确定", "闻灯-脸部正面-成品_00009_.png")
    items = [("00009 正面（唯一基准）", "身份已确认", confirmed)]
    for lab, tag in [("闻灯主图-左侧脸", "左 90°"), ("闻灯主图-右侧脸", "右 90°")]:
        f = _find(lab)
        if f:
            items.append((tag, "主工作流", f))
    if len(items) > 1:
        args = [PY, "make_sheet.py", os.path.join(PIC, "_对比_Kontext转头.png"), "820"]
        args += ["%s|%s|%s" % (a, b, c) for a, b, c in items]
        sh(args, quiet=True)
    return 0


# ─────────────────────── 阶段 5：Flux 正脸基准（2026-09-20 新增） ───────────────────────
# ★ 为什么单独一条路，不能混进 p2：
#   p2 走的是 build_master_wf.py（装配器），装配器只重建 3 块，**不认识 Flux 文生图组**，
#   一跑就把那 53 个节点整组删掉。「正脸基准改用 Flux 自产」是**原地追加**改动
#   （读服务器现版快照 → 只加 1410–1418 这 9 个节点 → 推回），必须用 add_flux_baseline_group.py。
BASE_OUT = os.path.join(PIC, "正脸基准-2026-09-20")


def cmd_push_baseline():
    """原地追加推送：正脸基准改由 Flux 自产（+9 节点 / 断 2 连线 / 改接 2 处下游基准）。"""
    head("推送 · Flux 正脸基准（原地追加，零删除）")
    if not online():
        print("  实例不在线，先等开机：")
        if cmd_wait() != 0:
            return 1
    return sh([PY, "add_flux_baseline_group.py", "--push"], timeout=900)


def cmd_p5(kind="draft"):
    """跑 Flux 正脸基准图（纯 Flux 文生图，本组内无任何 LoadImage）。

    关键词「闻灯正脸基准」只命中 1113/1115 这一条支路 → 一次提交拿 1 张。
    （09-20 起 Flux 组已简化为 FLUX → 正脸基准图 → 身份锁 正脸/右脸/左脸，IMG 支路已删）
    """
    lab = "草稿" if kind == "draft" else "成品"
    head("阶段 5 · 出图：Flux 正脸基准图（%s）" % lab)
    print("  一次提交拿 1 张（不在浏览器点「运行」——那会把全部 15 条分支一起跑）\n")
    return sh([PY, "run_wf.py", MASTER, "闻灯正脸基准", kind, BASE_OUT], timeout=2400)


def cmd_faces(kind="draft"):
    """跑身份锁三视角：正脸 / 右脸 / 左脸，一次提交拿 3 张。"""
    lab = "草稿" if kind == "draft" else "成品"
    head("阶段 5b · 出图：身份锁 正脸/右脸/左脸（%s）" % lab)
    print("  一次提交拿 3 张（三视角共用结构锚 1305，只差表现层提示词）\n")
    return sh([PY, "run_wf.py", MASTER, "闻灯Flux身份锁", kind, BASE_OUT], timeout=2400)


def cmd_baseline():
    """★ 一条命令做完：「正脸基准改用 Flux 自产」的推送 + 出图。

    推送与出图分开返回码：推送失败就**不跑图**（跑了也是旧工作流，白烧豆）。
    """
    head("部署 · Flux 正脸基准（推送 → 出图）")
    rc = cmd_push_baseline()
    if rc != 0:
        print("\n★ 推送失败 —— 不跑图（否则跑的还是服务器上的旧工作流，白烧豆）。")
        return rc

    print("\n  ── 先出草稿（最快，用来判断身份有没有守住、质感对不对）──")
    r2 = cmd_p5("draft")
    if r2 != 0:
        print("\n★ 草稿出图失败（rc=%d）→ 跳过成品。" % r2)
        cmd_report()
        return r2

    # 草稿与成品是两条并行支路，一次提交能同时拿；但成品要跑 4x 放大 + 18 个节点，慢。
    print("\n  ── 再出成品（含 4x 放大）──")
    r3 = cmd_p5("final")

    print("\n[本轮产物]")
    for f in sorted(glob.glob(os.path.join(BASE_OUT, "*.png"))):
        print("   %-46s %7.1f KB" % (os.path.basename(f), os.path.getsize(f) / 1024))

    cmd_report()
    print("\n★ 用时 %s。看完图立刻去云平台关机。" % el())
    return r3


# ─────────────────────── 报告 ───────────────────────
def cmd_report():
    head("报告")
    print("\n[本地产物]")
    for d in ("主工作流", "v23-脸部三视角", "flux-v2-脸部"):
        p = os.path.join(PIC, d)
        n = len(glob.glob(os.path.join(p, "*.png"))) if os.path.isdir(p) else 0
        print("  %-18s %3d 张   %s" % (d, n, p))
    print("\n[本轮拼好的对比图]")
    for f in ("_1比1_脸部_主工作流.png", "_1比1_头发_主工作流.png", "_对比_Kontext转头.png"):
        p = os.path.join(PIC, f)
        print("  %-28s %s" % (f, "OK %.1f KB" % (os.path.getsize(p) / 1024)
                              if os.path.exists(p) else "（尚未生成）"))
    if online():
        try:
            q = jget("/queue", 30)
            print("\n[队列] running=%d  pending=%d"
                  % (len(q.get("queue_running", [])), len(q.get("queue_pending", []))))
        except Exception:
            pass
        print("\n[服务器工作流]")
        try:
            for name in jget("/api/userdata?dir=workflows", 60):
                print("   %s" % name)
        except Exception:
            pass
    else:
        print("\n  （实例不在线，跳过服务器检查）")
    print("""
── 收尾清单 ────────────────────────────────
  □ 产物已拉到本地（看上面「本地产物」的数字）
  □ 只认 1:1 对比图判断质感（整图缩放会把毛孔和发丝抹平）
  □ 浏览器里看主工作流：先刷新页面 → 从列表重开「夜市百相簿」
  → 确认完毕，**立刻去云平台关机**
""")


# ─────────────────────── 总编排 ───────────────────────
def cmd_all():
    head("开机一次性编排 · 开始")
    print("  策略：一次开机只做「装配推送 + 一次提交出图 + 补模型 + 拉产物」，不做任何试验。")
    if not online():
        print("  实例不在线，先等开机：")
        if cmd_wait() != 0:
            return 1
    cmd_p1()
    r2 = cmd_p2()
    if r2 != 0:
        print("\n★ 主工作流装配/推送没成功 —— 停在这里，避免后面的图跑到旧工作流上。")
        return r2
    cmd_p3(with_download=True)
    cmd_p4()
    cmd_report()
    print("\n★ 全程用时 %s。现在可以关机了。" % el())
    return 0


def cmd_quick():
    """快路径：只出图，不下载。

    适合「只想先看质感修得对不对」的一次开机 —— 约 6~8 分钟就能关机，
    把 17GB 的 Kontext 下载留到你有连续 25 分钟空闲时再单独开一趟。
    """
    head("快路径 · 只出图不下载（预计 6~8 分钟）")
    if not online():
        if cmd_wait(limit_min=min(WAIT_MIN, 10)) != 0:
            return 1
    cmd_p1()
    r2 = cmd_p2()
    if r2 != 0:
        print("\n★ 主工作流装配/推送没成功 —— 停下。")
        return r2
    cmd_p3(with_download=False)
    cmd_report()


def cmd_setup():
    """★ 配置模式：只做「更新工作流 + 补模型」，**不出图**。

    这是给「我自己在浏览器里点运行」这个用法准备的：
      ① 把本地精简版主工作流推到服务器（覆盖旧的 128 节点版）
      ② 下 Kontext 四件套（先查磁盘余量，不够就报数字并停下）
    跑完你刷新浏览器，工作流就是最新的，你自己选中节点按 Ctrl+Enter 出图。
    """
    head("配置模式 · 更新工作流 + 补模型（不出图）")
    print("  这一趟不跑任何图 —— 图由你在浏览器里自己点。\n")
    if not online():
        print("  实例不在线，先等开机：")
        if cmd_wait() != 0:
            return 1

    cmd_p1()

    print("\n" + "─" * 74)
    print("① 更新主工作流（本地精简版 → 服务器，覆盖旧版）")
    print("─" * 74)
    rc = cmd_p2()
    if rc != 0:
        print("\n★ 工作流没更新成功 —— 停在这里，避免你以为看到的是新版。")
        return rc
    print("\n  ✔ 工作流已更新。现在去浏览器：刷新页面 → 重开「夜市百相簿」")

    print("\n" + "─" * 74)
    print("② 下 Kontext 四件套（约 15 GB，走 ModelScope）")
    print("─" * 74)
    rc2 = sh([PY, "kontext_setup.py", "download"], timeout=5400)
    if rc2 != 0:
        print("\n  ★ 下载没跑完（rc=%d）。上面若有磁盘/网络的提示，按提示处理。" % rc2)
    else:
        print("\n  ✔ 下载完成，做一次完整性校验：")
        sh([PY, "kontext_setup.py", "verify"], timeout=300)

    cmd_report()
    print("\n★ 配置完成，用时 %s。图请你在浏览器里自己点。" % el())
    print("   （别点大「运行」按钮 —— 那会把 7 条分支一起跑）")
    return 0
    print("\n★ 全程用时 %s。质感结果已到手，现在可以关机了。" % el())
    return 0


MODES = {"wait": cmd_wait, "all": cmd_all, "quick": cmd_quick, "setup": cmd_setup,
         "p1": cmd_p1, "p2": cmd_p2, "p3": lambda: cmd_p3(with_download=False), "p4": cmd_p4,
         "p5": lambda: cmd_p5("draft"), "faces": lambda: cmd_faces("draft"),
         "pushbase": cmd_push_baseline, "baseline": cmd_baseline,
         "report": cmd_report}

if __name__ == "__main__":
    mode = (sys.argv[1] if len(sys.argv) > 1 else "all").lower()
    if mode not in MODES:
        print(__doc__); sys.exit(1)
    sys.exit(MODES[mode]() or 0)
