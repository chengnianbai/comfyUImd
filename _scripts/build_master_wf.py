# -*- coding: utf-8 -*-
"""夜市百相簿 · 主工作流装配器

★ 要解决的问题（用户 2026-09-18 提出）
    之前每加一种能力（Flux 质感 / Kontext 转头）我都在旁边**新建一个工作流文件**，
    结果散成 4 个：闻灯-Flux脸部三视角 / -迭代转头 / -质感修复对照 / -Kontext转头。
    用户明确要求：**「夜市百相簿」是主工作流，所有调整都在它里面做**，
    因为这是在生成《夜市百相簿》这部小说里的角色资产。

★ 本脚本的做法
    1. 取基线 = 服务器现行的 `夜市百相簿-主工作流.json`（--fetch），离线时用本地备份
       —— **原有 24 个节点与 id 一律保留不动**（用户已确认过的白底立绘管线）；
    2. 把各能力做成「区块」并入，每块一个 ComfyUI Group，块间**零连线、完全自包含**；
    3. 新增节点的 id 从 1000 起，与原有 1~25 绝不冲突；
    4. 全局自检（id 唯一 / 链接端点存在 / 输入全连接 / SaveImage 前缀唯一）。

★ 区块划分（按角色分组：闻灯一整片，其余角色预留）
    【闻灯】立绘 · SDXL 白底立绘       ← 基线原样（24 节点与 id 一律不动）
    【闻灯】脸部 · SDXL img2img 保身份 ← 新增（= v23 的做法）
    【闻灯】转头 · Flux Kontext 90°    ← 并入 _wf\\闻灯-Kontext转头.json
    （已删）【闻灯】质感 · Flux A~E 对照 ← 2026-09-18 用户裁决删除，源块仍归档在 _wf\\

★★ 只有 Kontext 这一块用 Flux。
    因为「把头转成 90° 侧脸」是 SDXL 给不了的能力（四档 denoise + guidance 已实测否证）。
    其余全部 SDXL —— Flux 从来不是闻灯的主力模型，v23 那张已确认的脸就是 SDXL 出的。

★ 用法
    python push_kontext_wf.py --local          # 先出 Kontext 块的 JSON
    python build_master_wf.py                  # 装配（用本地基线）
    python build_master_wf.py --fetch          # 装配（从服务器拉现行基线，需在线）
    python build_master_wf.py --push           # 装配并推送（需在线，保留原工作流 id）
    python build_master_wf.py --selftest       # 防重入自检

⚠️ 合并后工作流里有 7 个 SaveImage（立绘 2 + 脸部 2 + 转头 3）。
   **在浏览器点「运行」会把所有分支全跑一遍**（几十分钟）→ 跑图一律用 run_wf.py 按分支提交，
   浏览器只用来看结构（或 Ctrl+Enter 只跑选中的输出节点）。
"""
import json, os, sys, copy, ssl, uuid, urllib.request, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from livdan_to_fullbody import convert as convert_livdan   # noqa: E402

ROOT = r"D:\xiaobai-claude code\comfyUImd"
WF_DIR = os.path.join(ROOT, "_scripts", "_wf")
PIC = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图")

BASE_URL = os.environ.get("COMFY_BASE", "https://gw-496303efdc4841bfa3e30e994493225f.cn-beijing.aigclinks.com:8016")
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE

# ★★ 唯一工作流文件名（2026-09-18 用户定）：
#    「夜市百相簿」是主工作流，所有调整都并进这一个文件，**不再另起「查看版」等第二个名字**。
#    浏览器缓存问题改由「推送时换新 uuid」解决（见 ⑥ 推送），文件名保持固定不变。
MASTER_NAME = "夜市百相簿-主工作流.json"
LOCAL_BASE = os.path.join(WF_DIR, "夜市百相簿_v19.json")
FETCH = "--fetch" in sys.argv
PUSH = "--push" in sys.argv

# 区块文件（由各自的 --local 构建脚本产出）
BLK_FLUX = os.path.join(WF_DIR, "闻灯-Flux-质感修复对照.json")
BLK_KONTEXT = os.path.join(WF_DIR, "闻灯-Kontext转头.json")

V23_FACE = os.path.join(PIC, "v23-脸部三视角", "闻灯v23-脸部正面-成品_00001_.png")
# ★ 上传走这张缩略版（1024x1280 / 1.7MB），不要传 1792x2304 原图（5.4MB）。
#   2026-09-18 实测：本网关上行约 40 KB/s，5.4MB 要 2 分钟以上、会被 timeout 判成"卡死"，
#   而工作流实际只需要 1024x1280（脸部 img2img 目标 896x1152、Kontext 会自己缩放）。
SMALL_FACE = os.path.join(WF_DIR, "flux_face_base_v23_1024x1280.png")
UPLOAD_FACE = "wendeng_v23_face_base.png"

CKPT_SDXL = "leosamsHelloworldXL_helloworldXL70.safetensors"
UP_ULTRA = "4x-UltraSharp (1).pth"
SDXL_W, SDXL_H = 896, 1152
SDXL_SEED = 20260917


def raw(p, data=None, ctype=None, timeout=120, method=None):
    h = {}
    if ctype:
        h["Content-Type"] = ctype
    return urllib.request.urlopen(
        urllib.request.Request(BASE_URL + p, data=data, headers=h, method=method),
        timeout=timeout, context=ctx).read()


def upload_base():
    """★ 把身份基图传进实例的 input/（脸部块 + Kontext 块**共同依赖它**）

    为什么必须显式做这件事：
        LoadImage 的 widget 值只是一个**文件名**，工作流 JSON 里并不自带图片数据。
        以前这个文件是 push_flux_face_wf.py 顺手传上去的，于是后面几个脚本就"搭便车"了。
        实例一旦重建（输入目录是空的），三个块会一起报 `invalid image file` —— 
        而那时实例已经开机在烧豆了。所以在这里补成**显式、幂等**的一步。
    """
    src = SMALL_FACE if os.path.exists(SMALL_FACE) else V23_FACE
    if not os.path.exists(src):
        print("  ★ 找不到基图 %s" % src)
        return False
    print("  上传源 %s  (%.2f MB)" % (os.path.basename(src), os.path.getsize(src) / 1048576))
    data = open(src, "rb").read()
    bd = "----wb" + uuid.uuid4().hex
    body = b""
    for k, v in (("overwrite", "true"), ("type", "input"), ("subfolder", "")):
        body += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                 % (bd, k, v)).encode()
    body += ("--%s\r\nContent-Disposition: form-data; name=\"image\"; filename=\"%s\"\r\n"
             "Content-Type: image/png\r\n\r\n" % (bd, UPLOAD_FACE)).encode()
    body += data + ("\r\n--%s--\r\n" % bd).encode()
    r = urllib.request.urlopen(
        urllib.request.Request(BASE_URL + "/upload/image", data=body,
                               headers={"Content-Type": "multipart/form-data; boundary=%s" % bd}),
        timeout=180, context=ctx).read().decode("utf-8", "replace")
    print("  ✔ 基图已上传：%s  (%.1f MB)  -> %s"
          % (UPLOAD_FACE, len(data) / 1048576, r[:120]))
    # 回读确认真的落地了（上传接口偶发成功但文件缺失）
    # ⚠️ /internal/files/input 返回的是**字符串数组**，元素形如 "名字.png [input]"，
    #    不是 dict。2026-09-18 曾因为按纯文件名比对而把成功误判成失败。
    try:
        d = json.loads(raw("/internal/files/input", None, None, 60).decode("utf-8", "replace"))
        names = []
        for x in d:
            n = x.get("name") if isinstance(x, dict) else str(x)
            names.append(n.split(" [")[0].strip())
        if UPLOAD_FACE not in names:
            print("  ★ 回读确认失败：input/ 里没有 %s（现有 %s）" % (UPLOAD_FACE, names))
            return False
        print("  ✔ 回读确认：input/ 里已存在")
    except Exception as e:
        print("  ⚠️ 回读确认跳过（%s），上传接口已返回成功" % type(e).__name__)
    return True


def bbox(nodes):
    if not nodes:
        return 0, 0, 0, 0
    x1 = min(n["pos"][0] for n in nodes)
    y1 = min(n["pos"][1] for n in nodes)
    x2 = max(n["pos"][0] + n.get("size", [200, 100])[0] for n in nodes)
    y2 = max(n["pos"][1] + n.get("size", [200, 100])[1] for n in nodes)
    return int(x1), int(y1), int(x2), int(y2)


def size_of(nodes):
    x1, y1, x2, y2 = bbox(nodes)
    return x2 - x1, y2 - y1


# ══════════════════════════ 装配器 ══════════════════════════
class Asm:
    def __init__(self):
        self.nodes, self.links, self.groups = [], [], []
        self._nid, self._lid, self._ord = 1000, 1000, 1000

    def nid(self):
        self._nid += 1; return self._nid

    def lid(self):
        self._lid += 1; return self._lid

    def ord(self):
        self._ord += 1; return self._ord

    def add(self, src_nodes, src_links, dx, dy, title, color="#3f789e", keep_ids=False):
        """把一个区块并进来：平移 + 重编号 + 回填 + 加 Group。返回新节点列表。"""
        x0, y0, _, _ = bbox(src_nodes)
        idmap = {}
        new = []
        for n in src_nodes:
            old = n["id"]
            newid = old if keep_ids else self.nid()
            idmap[old] = newid
            n2 = copy.deepcopy(n)
            n2["id"] = newid
            n2["pos"] = [int(n["pos"][0] - x0 + dx), int(n["pos"][1] - y0 + dy)]
            n2["order"] = n.get("order", 0) if keep_ids else self.ord()
            n2.setdefault("flags", {})
            n2.setdefault("properties", {"Node name for S&R": n["type"]})
            for s in n2.get("inputs", []):
                s["link"] = None
            for o in n2.get("outputs", []):
                o["links"] = []
            new.append(n2)

        linkmap = {}
        nlinks = []
        for l in src_links:
            lid, fid, fslot, tid, tslot, typ = l
            nl = lid if keep_ids else self.lid()
            linkmap[lid] = nl
            nlinks.append([nl, idmap[fid], fslot, idmap[tid], tslot, typ])

        for n_src, n_dst in zip(src_nodes, new):
            for s_src, s_dst in zip(n_src.get("inputs", []), n_dst.get("inputs", [])):
                if s_src.get("link") is not None:
                    s_dst["link"] = linkmap[s_src["link"]]
            for o_src, o_dst in zip(n_src.get("outputs", []), n_dst.get("outputs", [])):
                o_dst["links"] = [linkmap[x] for x in (o_src.get("links") or [])]

        self.nodes += new
        self.links += nlinks
        x1, y1, x2, y2 = bbox(new)
        self.groups.append({"title": title, "bounding": [x1 - 30, y1 - 70, (x2 - x1) + 60, (y2 - y1) + 110],
                            "color": color, "font_size": 30, "flags": {}})
        return new


# ══════════════════════════ ① 取基线 ══════════════════════════
print("=" * 72)
print("① 取基线：夜市百相簿主工作流")
print("=" * 72)

base_wf = None
if FETCH:
    try:
        u = "/api/userdata/workflows%2F" + urllib.parse.quote(MASTER_NAME)
        base_wf = json.loads(raw(u, None, None, 60).decode("utf-8", "replace"))
        print("  已从服务器拉取现行版：%d 节点 / %d 链接" % (len(base_wf["nodes"]), len(base_wf["links"])))
    except Exception as e:
        print("  ★ 拉取失败（%s）→ 回退到本地备份" % type(e).__name__)

if base_wf is None:
    if not os.path.exists(LOCAL_BASE):
        print("  ★ 本地基线也不在：%s" % LOCAL_BASE); sys.exit(1)
    base_wf = json.load(open(LOCAL_BASE, encoding="utf-8"))
    print("  用本地备份作基线：%d 节点 / %d 链接" % (len(base_wf["nodes"]), len(base_wf["links"])))
    print("  ⚠️ 如果你在浏览器里改过主工作流，请用 --fetch 重新装配，否则你的改动会被覆盖。")

# ═══════════════════ ① -b 防重入：拉回来的可能已经是合并过的主工作流 ═══════════════════
# 背景：开机后如果 oneshot.py all 跑了两遍，第二遍 --fetch 拉回的就是 **已经合并的 128 节点版**，
#       若拿它当基线再合一次 → 24 个原节点被当成"基线"复制，加上新 104 个 = 232 节点，
#       而且 SaveImage 前缀必然重复（自检会报"前缀重复"），但那时实例已经开着在烧豆了。
# 所以：检测到「已合并」就**按分组包围盒把立绘块还原成基线**，让你重跑是幂等的。


def _save_prefixes(wf):
    return [str(n["widgets_values"][0]) for n in wf["nodes"]
            if n["type"] == "SaveImage" and n.get("widgets_values")]


def is_merged(wf):
    """是不是「已合并的主工作流」？
    ⚠️ 2026-09-18：基线里那两个 SaveImage 前缀已被改造为 `闻灯-全身正面-*`（原 `夜市百相簿-白底*`），
       所以白名单里必须同时保留 `闻灯` 与 `夜市百相簿` 两个前缀，
       否则纯基线会被误判成"已合并" → 走进还原分支 → 找不到「立绘」分组 → 静默退回旧基线。"""
    pfx = _save_prefixes(wf)
    return len(wf["nodes"]) > 40 or any(
        not p.startswith(("夜市百相簿", "闻灯")) for p in pfx)


def strip_to_baseline(wf):
    """从已合并的主工作流里，按「立绘」分组的包围盒取回原来那 24 个节点"""
    gb = None
    for g in wf.get("groups", []):
        if "立绘" in (g.get("title") or ""):
            gb = g.get("bounding")
            break
    if not gb:
        return None, "找不到「立绘」分组，无法定位基线"
    x0, y0, w, h = gb
    keep = {n["id"] for n in wf["nodes"]
            if n["pos"][0] >= x0 and n["pos"][0] <= x0 + w
            and n["pos"][1] >= y0 and n["pos"][1] <= y0 + h}
    if not keep:
        return None, "「立绘」分组包围盒内没有节点"

    nodes = [n for n in wf["nodes"] if n["id"] in keep]
    links = [l for l in wf["links"] if l[1] in keep and l[3] in keep]
    remap = {l[0]: i + 1 for i, l in enumerate(links)}
    for l in links:
        l[0] = remap[l[0]]
    for n in nodes:                              # 同步节点端口上记的 link id
        for s in n.get("inputs", []):
            if s.get("link") is not None:
                s["link"] = remap.get(s["link"])
        for o in n.get("outputs", []):
            o["links"] = [remap[x] for x in (o.get("links") or []) if x in remap]

    out = {k: v for k, v in wf.items() if k not in ("nodes", "links", "groups")}
    out.update({"nodes": nodes, "links": links, "groups": []})
    return out, "%d 节点 / %d 链接" % (len(nodes), len(links))


if "--selftest" in sys.argv:
    # 防重入自检：把**已经合并的主工作流**当成「--fetch 拉回来的基线」，
    # 验证能原样还原成本地纯基线。这一步通过，重跑 oneshot 才是幂等的。
    _mf = os.path.join(WF_DIR, "夜市百相簿_主工作流.json")
    if not os.path.exists(_mf):
        print("★ 先跑一次 python build_master_wf.py 生成 %s" % _mf)
        sys.exit(1)
    _m = json.load(open(_mf, encoding="utf-8"))
    _b = json.load(open(LOCAL_BASE, encoding="utf-8"))
    # ★ 2026-09-18：基线现在会被改造成「全身正面」（24→29 节点），
    #   所以自检的基准也必须先过一遍同样的改造，否则会误报"id 集合不一致""前缀不一致"。
    try:
        _b["nodes"], _b["links"], _bc = convert_livdan(_b["nodes"], _b["links"])
    except Exception as _x:
        print("  ★ 基准改造失败：%s: %s" % (type(_x).__name__, _x)); sys.exit(1)
    print("  基准 = 本地 v19 过一遍全身改造 → %d 节点（changed=%s）" % (len(_b["nodes"]), _bc))
    print("=" * 72)
    print("防重入自检：拿「已合并的主工作流」当拉回来的基线")
    print("=" * 72)
    print("  输入            %3d 节点 / %2d 个 SaveImage" % (len(_m["nodes"]), len(_save_prefixes(_m))))
    print("  is_merged()  →  %s   （必须 True，否则守卫不会触发）" % is_merged(_m))
    _s, _info = strip_to_baseline(_m)
    if _s is None:
        print("  ★ 还原失败：%s" % _info); sys.exit(1)
    print("  还原结果        %s" % _info)
    _e = []
    if {n["id"] for n in _s["nodes"]} != {n["id"] for n in _b["nodes"]}:
        _e.append("还原出的节点 id 集合 ≠ 「本地 v19 + 全身改造」的节点 id 集合")
    if _save_prefixes(_s) != _save_prefixes(_b):
        _e.append("还原出的 SaveImage 前缀 ≠ 基准：%s" % _save_prefixes(_s))
    if is_merged(_s):
        _e.append("还原后 is_merged() 仍为 True")
    _lids = [l[0] for l in _s["links"]]
    if len(set(_lids)) != len(_lids):
        _e.append("还原后链接 id 有重复")
    for _n in _s["nodes"]:
        for _sl in _n.get("inputs", []):
            if _sl.get("link") is not None and _sl["link"] not in set(_lids):
                _e.append("节点 %s 输入 %s 指向不存在的 link %s"
                          % (_n["id"], _sl["name"], _sl["link"]))
    if _e:
        print("\n  ★ 自检失败 %d 项：" % len(_e))
        for _x in _e[:12]:
            print("     -", _x)
        sys.exit(1)
    print("  ✔ 还原成 %d 节点 / %d 链接，与本地基线 v19 完全一致 → 重跑是幂等的。"
          % (len(_s["nodes"]), len(_s["links"])))
    sys.exit(0)


# ══════════════ ★★ 安全护栏：禁止「无声吞掉其他分组」（2026-09-20 加） ══════════════
# 为什么必须加：
#   strip_to_baseline() 只按【立绘】分组包围盒取回那 29 个基线节点，**其余全部丢弃**，
#   而本脚本的 blocks 只重建 3 块（全身 / 脸部 / 转头）。
#   「【闻灯】Flux 文生图 · 一体化 fp8」组（含身份锁 正脸/右脸）是 add_flux_group.py /
#   add_identity_lock.py / add_flux_baseline_group.py **原地追加**进去的，本脚本不认识它。
#   于是 `--fetch --push` 会把这一整组（实测 53 个节点、6 条输出）**静默删掉**。
#   而 oneshot.py 的 p2 / all / quick / setup 都会走到这里 —— 那是在**按开机时长计费**的
#   实例上丢资产，等于白烧豆。所以：一旦检测到「将被丢弃的节点里有本脚本不认识的分组」，
#   直接中止，除非显式给 --allow-drop-extra。
ALLOW_DROP_EXTRA = "--allow-drop-extra" in sys.argv
EXTRA_GROUP_KEYS = ("文生图", "身份锁")
EXTRA_DROP = []
if is_merged(base_wf):
    _gb = None
    for _g in base_wf.get("groups", []):
        if "立绘" in (_g.get("title") or ""):
            _gb = _g.get("bounding")
            break
    if _gb:
        _x0, _y0, _w, _h = _gb
        _keep = {n["id"] for n in base_wf["nodes"]
                 if _x0 <= n["pos"][0] <= _x0 + _w and _y0 <= n["pos"][1] <= _y0 + _h}
        _dropped = [n for n in base_wf["nodes"] if n["id"] not in _keep]
        for _g in base_wf.get("groups", []):
            if not any(k in (_g.get("title") or "") for k in EXTRA_GROUP_KEYS):
                continue
            _gx, _gy, _gw, _gh = _g["bounding"]
            _in = [n for n in _dropped
                   if _gx <= n["pos"][0] <= _gx + _gw and _gy <= n["pos"][1] <= _gy + _gh]
            if _in:
                EXTRA_DROP.append((_g.get("title"), _in))

if EXTRA_DROP:
    _tot = sum(len(v) for _, v in EXTRA_DROP)
    print("\n" + "★" * 74)
    print("★★ 中止：这次装配会**删掉本脚本不认识的分组**（共 %d 个节点）" % _tot)
    for _t, _v in EXTRA_DROP:
        print("     - %s\n         → 丢弃 %d 个节点" % ((_t or "")[:56], len(_v)))
    print("   这些节点是 add_flux_group.py / add_identity_lock.py / add_flux_baseline_group.py")
    print("   **原地追加**进去的；本脚本只重建「全身 / 脸部 / 转头」3 块，不认识它们。")
    print("   → 要部署这类改动，请直接用对应的 --push 脚本（原地追加，零删除）：")
    print("        python add_flux_baseline_group.py --push   # 正脸基准改用 Flux 自产")
    print("   → 确实要连同它们一起丢掉，才加 --allow-drop-extra。")
    print("★" * 74)
    if not ALLOW_DROP_EXTRA:
        sys.exit(1)
    print("（已给 --allow-drop-extra，继续丢弃）\n")


if is_merged(base_wf):
    print("\n  ⚠️ 拉回来的已经是**合并过的主工作流**（%d 节点）→ 自动还原立绘块作基线，"
          "重跑幂等。" % len(base_wf["nodes"]))
    stripped, info = strip_to_baseline(base_wf)
    if stripped is None:
        print("  ★ 还原失败：%s" % info)
        print("     改用本地纯基线 %s" % os.path.basename(LOCAL_BASE))
        stripped = json.load(open(LOCAL_BASE, encoding="utf-8"))
        stripped["id"] = base_wf.get("id") or stripped.get("id")
    base_wf = stripped
    print("     还原结果：%s" % info)
    if is_merged(base_wf):
        print("  ★ 还原后仍不像纯基线 → 中止，避免装配出重复节点。")
        sys.exit(1)

BASE_ID = base_wf.get("id") or "8f3eed13-567f-45aa-9c4c-cd8acc0c49f1"
print("  保留原工作流 id = %s（原地更新，不动你的浏览器标签页身份）" % BASE_ID)


# ══════════════════════════ ① -c 脸部块 5 段提示词：**冻结成常量** ══════════════════════════
# 2026-09-18 之前是 pick_title(base_wf, "正向 A") —— 从基线"继承"提示词。
# 但用户已决定把基线（原「立绘」块）改造成**全身**，继承就意味着脸部块也会一起变成全身 → 破功。
# 所以脸部块改为**自带一份写死的副本**（内容 = 改造前那套"脸部特写"提示词，一字未改），
# 从此它与基线彻底解耦：基线怎么改，脸部块都不动。

def pick_title(nodes, *keys):
    """按标题关键词找节点（现在只用于**诊断打印**，不再用于给脸部块取提示词）"""
    for n in nodes:
        t = n.get("title") or ""
        if all(k in t for k in keys) and n["type"] == "CLIPTextEncode":
            return (n.get("widgets_values") or [""])[0]
    return None


print("\n  基线当前提示词（仅诊断；脸部块已独立，不再继承基线）：")
for nm in ("正向 A", "正向 B", "负向 N1", "负向 N2", "负向 N3"):
    v = pick_title(base_wf["nodes"], nm)
    print("    %-8s %s" % (nm, ("%d 字符" % len(v)) if v else "★ 未找到"))

# ★★ 脸部块（= v23 那条线）的提示词，冻结副本。**不要依赖基线。**
POS_A = ("front view, looking at viewer, face closeup, head and shoulders, 1boy, solo, "
         "24 year old east asian man, masculine face, strong jaw, messy wavy black hair, "
         "small mole at outer eye corner, faded blue shirt collar, dark coat collar, "
         "pure white background")
POS_B = ("detailed face, detailed eyes, dark circles under eyes, iris detail, individual eyelashes, "
         "thick eyebrows, stubble, small mole at outer eye corner, visible skin pores, skin texture, "
         "skin imperfections, peach fuzz, messy wavy hair, individual hair strands, faded shirt collar, "
         "dark coat, pure white background, flat even lighting, sharp focus, photorealistic")
NEG_1 = ("1girl, female, feminine face, delicate, fragile, soft features, soft round face, pretty boy, "
         "boyish face, bishounen, makeup, lipstick, rosy lips, eyeshadow, teenage, child, narrow face, "
         "pale skin, blonde hair, straight hair, slicked back hair, undercut, side part, neat hair")
NEG_2 = ("t-shirt, sweater, business suit, blazer, tie, dress shirt, formal wear, ironed shirt, "
         "wool coat, brown coat, beige coat, blue coat, light coat, new clothes, fashion model, "
         "jeans, denim, bare chest, shirtless, nude, white sneakers, new shoes, police uniform, "
         "wuxia, hanfu")
NEG_3 = ("dark background, grey background, gradient background, vignette, shadow, busy background, "
         "full body, bare shoulders, shirtless, freckles, mole on cheek, mole on forehead, "
         "extra fingers, bad hands, watermark, text, blurry, lowres, airbrushed, over-smoothed, "
         "beauty filter, smooth skin, retouched")
for nm, v in (("正向A", POS_A), ("正向B", POS_B), ("负向N1", NEG_1), ("负向N2", NEG_2), ("负向N3", NEG_3)):
    print("    冻结 %-6s %d 字符" % (nm, len(v)))

# ══════════════════════════ ① -d 把基线「立绘（脸部）」就地改造成「全身正面」 ══════════════════════════
# 依据 角色生成约束-V1.0.md §4.1/§5/§6/§7/§8.1/§10/§12/§13/§17 —— 详见 livdan_to_fullbody.py 抬头注释。
print("\n" + "=" * 72)
print("① -d 基线改造：立绘（脸部特写） → 全身正面")
print("=" * 72)
try:
    _before = len(base_wf["nodes"])
    base_wf["nodes"], base_wf["links"], _changed = convert_livdan(base_wf["nodes"], base_wf["links"])
    if _changed:
        print("  ✔ 已改造：%d → %d 节点（新增 4x放大前的「贴脸」链 5 个节点）" % (_before, len(base_wf["nodes"])))
        print("     画布 896×1152 → 832×1216；提示词换成全身；负向删掉 full body/shirtless/bare chest")
    else:
        print("  ✔ 已是全身版（幂等跳过）：%d 节点" % len(base_wf["nodes"]))
except Exception as e:
    print("  ★ 基线改造失败：%s: %s" % (type(e).__name__, e))
    sys.exit(4)



# ══════════════════════════ ② 构建新增区块：闻灯·脸部 ══════════════════════════
def build_face_block():
    """闻灯 · 脸部（SDXL img2img 保身份）= v23 的做法
    ★ 采纳附录 B.7：**撤掉第二段重绘**，成品 = 第一段 → 4x 放大 → 缩回 0.5 → 直接存。
      原链路那步 denoise 0.25 的重绘已实证「不补细节、只抹细节」。"""
    ns, ls = [], []
    CLIP_T, COND, LAT, IMG, VAE_T, UPM = "CLIP", "CONDITIONING", "LATENT", "IMAGE", "VAE", "UPSCALE_MODEL"

    def N(nid, ntype, pos, size, widgets, inputs, outputs, order, title=None):
        n = {"id": nid, "type": ntype, "pos": list(pos), "size": list(size), "flags": {},
             "order": order, "mode": 0, "inputs": inputs, "outputs": outputs,
             "properties": {"Node name for S&R": ntype}}
        if title:
            n["title"] = title
        if widgets is not None:
            n["widgets_values"] = widgets
        ns.append(n)

    def I(name, t):
        return {"name": name, "type": t, "link": None}

    def O(name, t, idx):
        return {"name": name, "type": t, "slot_index": idx, "links": []}

    def L(fid, fslot, tid, tslot, t):
        lid = len(ls) + 1
        ls.append([lid, fid, fslot, tid, tslot, t])

    NOTE = """【闻灯 · 脸部（SDXL img2img 保身份）】

★ 这是当前**最可信的一条管线** —— v23 那张脸就是这么出来的。
  身份不来自底模，来自**基图**：把已确认的 v23 正面脸当输入，img2img 低 denoise 重绘。
  （实证：同 seed + 同 token 的纯文生图会换人；带上基图立刻回到同一张脸）

★ 已采纳附录 B.7 的结论：**撤掉第二段重绘**
  原链路「4x 放大 → 缩回 0.5 → KSampler② denoise 0.25」实测是**不补细节、只抹细节**
  （成品 2048×2560 比它自己的草稿 1024×1280 更糊，雀斑/毛孔/飞散发丝全被抹掉）。
  所以本块成品 = 第一段 → 4x 放大 → 缩回 0.5 → **直接存，不再经过任何采样**。

★ 跑法（按分支提交，不要在浏览器点「运行」）
    python _scripts\\run_wf.py "夜市百相簿-主工作流.json" "闻灯-脸部正面" final

★ 参数
    底模 leosamsHelloworldXL（SDXL）· 896×1152 · CFG 10 · dpmpp_2m + karras · 30 步 · CLIP skip 1
    第一段 denoise 0.30（保身份）· seed 固定 20260917
    基图 = 闻灯v23-脸部正面-成品（已在服务器 input/ 里，名 %s）
""" % UPLOAD_FACE

    N(1, "Note", (61, 20), (1900, 520), [NOTE], [], [], 0, "★ 说明 · 闻灯脸部（img2img 保身份）")

    y = 600
    N(2, "CheckpointLoaderSimple", (61, y), (470, 100), [CKPT_SDXL], [],
      [O("MODEL", "MODEL", 0), O("CLIP", "CLIP", 1), O("VAE", "VAE", 2)], 1, "底模 · HelloWorld XL（SDXL）")
    N(3, "CLIPSetLastLayer", (61, y + 140), (380, 60), [-1],
      [I("clip", "CLIP")], [O("CLIP", "CLIP", 0)], 2, "Clip Skip = 1（SDXL 必须）")
    N(4, "LoadImage", (61, y + 240), (400, 400), [UPLOAD_FACE, "image"], [],
      [O("IMAGE", "IMAGE", 0), O("MASK", "MASK", 1)], 3, "★ 身份基图 = v23 正面（已确认）")
    N(5, "ImageScale", (500, y + 240), (330, 100), ["lanczos", SDXL_W, SDXL_H, "center"],
      [I("image", "IMAGE")], [O("IMAGE", "IMAGE", 0)], 4, "统一到 896×1152")
    N(6, "VAEEncode", (870, y + 240), (280, 60), [],
      [I("pixels", "IMAGE"), I("vae", "VAE")], [O("LATENT", "LATENT", 0)], 5, "身份 latent")

    N(7, "CLIPTextEncode", (61, y + 700), (760, 300), [POS_A],
      [I("clip", "CLIP")], [O("CONDITIONING", "CONDITIONING", 0)], 6, "正向 A · 人物 + 构图")
    N(8, "CLIPTextEncode", (61, y + 1040), (760, 300), [POS_B],
      [I("clip", "CLIP")], [O("CONDITIONING", "CONDITIONING", 0)], 7, "正向 B · 白底 + 光位 + 皮肤质感")
    N(9, "ConditioningCombine", (870, y + 700), (300, 60), [],
      [I("conditioning_1", "CONDITIONING"), I("conditioning_2", "CONDITIONING")],
      [O("CONDITIONING", "CONDITIONING", 0)], 8, "合并 A + B（突破 75 token 的关键）")

    N(10, "CLIPTextEncode", (1200, y + 700), (700, 220), [NEG_1],
      [I("clip", "CLIP")], [O("CONDITIONING", "CONDITIONING", 0)], 9, "负向 N1 · 反柔弱 / 反女性")
    N(11, "CLIPTextEncode", (1200, y + 960), (700, 220), [NEG_2],
      [I("clip", "CLIP")], [O("CONDITIONING", "CONDITIONING", 0)], 10, "负向 N2 · 服饰 / 正装")
    N(12, "CLIPTextEncode", (1200, y + 1220), (700, 220), [NEG_3],
      [I("clip", "CLIP")], [O("CONDITIONING", "CONDITIONING", 0)], 11, "负向 N3 · 背景 / 构图")
    N(13, "ConditioningCombine", (1950, y + 700), (300, 60), [],
      [I("conditioning_1", "CONDITIONING"), I("conditioning_2", "CONDITIONING")],
      [O("CONDITIONING", "CONDITIONING", 0)], 12, "负向 N1+N2")
    N(14, "ConditioningCombine", (1950, y + 800), (300, 60), [],
      [I("conditioning_1", "CONDITIONING"), I("conditioning_2", "CONDITIONING")],
      [O("CONDITIONING", "CONDITIONING", 0)], 13, "负向 (N1+N2)+N3")

    N(15, "KSampler", (2300, y + 240), (330, 262),
      [SDXL_SEED, "fixed", 30, 10.0, "dpmpp_2m", "karras", 0.30],
      [I("model", "MODEL"), I("positive", "CONDITIONING"), I("negative", "CONDITIONING"),
       I("latent_image", "LATENT")], [O("LATENT", "LATENT", 0)], 14,
      "① 第一段 · 30步 CFG10 denoise 0.30（保身份）")
    N(16, "VAEDecode", (2680, y + 240), (250, 60), [],
      [I("samples", "LATENT"), I("vae", "VAE")], [O("IMAGE", "IMAGE", 0)], 15)
    N(17, "SaveImage", (2680, y + 340), (460, 460), ["闻灯-脸部正面-草稿"],
      [I("images", "IMAGE")], [], 16, "草稿 · 闻灯脸部正面")
    N(18, "UpscaleModelLoader", (3200, y + 240), (520, 80), [UP_ULTRA], [],
      [O("UPSCALE_MODEL", "UPSCALE_MODEL", 0)], 17, "放大模型 4x-UltraSharp")
    N(19, "ImageUpscaleWithModel", (3200, y + 380), (440, 80), [],
      [I("upscale_model", "UPSCALE_MODEL"), I("image", "IMAGE")],
      [O("IMAGE", "IMAGE", 0)], 18)
    N(20, "ImageScaleBy", (3200, y + 500), (330, 80), ["lanczos", 0.5],
      [I("image", "IMAGE")], [O("IMAGE", "IMAGE", 0)], 19, "缩回 1792×2304")
    N(21, "SaveImage", (3700, y + 240), (500, 460), ["闻灯-脸部正面-成品"],
      [I("images", "IMAGE")], [], 20, "★ 成品 · 无第二段重绘（B.7）")
    N(22, "Note", (3700, y + 760), (620, 220),
      ["★ 本块没有第二段 KSampler。\n成品 = 第一段 → 4x 放大 → 缩回 0.5，"
       "不经过任何二次采样。\n这是附录 B.7 的结论：低 denoise 重绘不补细节、只抹细节。"],
      [], [], 21, "备注 · 为什么撤掉重绘")

    L(2, 1, 3, 0, CLIP_T)
    L(2, 2, 6, 1, VAE_T)
    L(4, 0, 5, 0, IMG)
    L(5, 0, 6, 0, IMG)
    L(3, 0, 7, 0, CLIP_T)
    L(3, 0, 8, 0, CLIP_T)
    L(7, 0, 9, 0, COND)
    L(8, 0, 9, 1, COND)
    L(3, 0, 10, 0, CLIP_T)
    L(3, 0, 11, 0, CLIP_T)
    L(3, 0, 12, 0, CLIP_T)
    L(10, 0, 13, 0, COND)
    L(11, 0, 13, 1, COND)
    L(13, 0, 14, 0, COND)
    L(12, 0, 14, 1, COND)
    L(2, 0, 15, 0, "MODEL")
    L(9, 0, 15, 1, COND)
    L(14, 0, 15, 2, COND)
    L(6, 0, 15, 3, LAT)
    L(15, 0, 16, 0, LAT)
    L(2, 2, 16, 1, VAE_T)
    L(16, 0, 17, 0, IMG)
    L(16, 0, 19, 1, IMG)
    L(18, 0, 19, 0, UPM)
    L(19, 0, 20, 0, IMG)
    L(20, 0, 21, 0, IMG)

    byid = {n["id"]: n for n in ns}
    for n in ns:
        for s in n.get("inputs", []):
            s["link"] = None
        for o in n.get("outputs", []):
            o["links"] = []
    for lid, fid, fslot, tid, tslot, t in ls:
        s = byid.get(fid)
        if s and fslot < len(s["outputs"]):
            s["outputs"][fslot]["links"].append(lid)
        d = byid.get(tid)
        if d and tslot < len(d["inputs"]):
            d["inputs"][tslot]["link"] = lid
    return ns, ls


# ══════════════════════════ ③ 载入现成区块 ══════════════════════════
def load_block(path, name):
    if not os.path.exists(path):
        print("  ★ 缺少区块文件：%s\n     → 先跑对应的 --local 构建脚本" % path)
        return None
    w = json.load(open(path, encoding="utf-8"))
    print("  载入 %-22s %3d 节点 / %3d 链接" % (name, len(w["nodes"]), len(w["links"])))
    return w["nodes"], w["links"]


print("\n" + "=" * 72)
print("② 准备各区块")
print("=" * 72)

face_n, face_l = build_face_block()
print("  新构建 闻灯·脸部           %3d 节点 / %3d 链接" % (len(face_n), len(face_l)))

# ★★ 2026-09-18 用户裁决：**删掉「Flux 质感对照 A~E」组**（原 56 节点，占全流程 44%）。
#
#   为什么删 —— 闻灯的主力模型本来就是 SDXL，不是 Flux：
#     · 手上唯一被确认的资产 v23 正脸，是 **SDXL**（leosamsHelloworldXL）出的；
#     · Flux 被引进来，只是为了解决**一件** SDXL 做不到的事：把头转成 90° 侧脸（靠 Kontext）；
#     · 于是「用 Flux img2img 去追 SDXL 的质感」= 把已经达标的东西重做一遍，没有收益。
#
#   零成本证据（本地已有，未开机）：
#     · v23 那步「第二段 denoise 0.25 重绘」在 SDXL 上**无害** —— 用 LANCZOS 2x 做"撤掉重绘"的
#       代理去比，成品反而发丝更利落 → SDXL 侧不需要动。
#     · Flux 即使撤掉重绘（flux-v2 草稿），皮肤仍比 v23 滑；发丝能打平，但皮肤追不上。
#       → 说明 Flux 的抛光来自**底模本身**，不是调参能救的。
#
#   源块 _wf\闻灯-Flux-质感修复对照.json **保留归档**，将来真要用可一行恢复。
kontext = load_block(BLK_KONTEXT, "闻灯·Kontext转头")

# ⚠️ 第一块的标题**必须保留「立绘」二字** —— `strip_to_baseline()` 靠它定位基线包围盒。
blocks = [("全身", base_wf["nodes"], base_wf["links"], True, "【闻灯】全身立绘 · SDXL 保身份（正面 · 原立绘块改造）", "#8A8A8A"),
          ("脸部", face_n, face_l, False, "【闻灯】脸部 · SDXL img2img 保身份（v23 做法）", "#3f789e"),
          ("转头", kontext[0] if kontext else [], kontext[1] if kontext else [], False, "【闻灯】转头 · Flux Kontext 90°（左/右/左45）", "#C2410C")]

# ══════════════════════════ ④ 网格布局并装配 ══════════════════════════
print("\n" + "=" * 72)
print("③ 装配（网格布局，块间零连线）")
print("=" * 72)

GAP, PAD, COLS = 500, 300, 2
sizes = {k: size_of(n) for k, n, l, _, _, _ in blocks}
colw = [0] * COLS
rowh = []
for i, (k, _, _, _, _, _) in enumerate(blocks):
    c, r = i % COLS, i // COLS
    w, h = sizes[k]
    colw[c] = max(colw[c], w)
    while r >= len(rowh):
        rowh.append(0)
    rowh[r] = max(rowh[r], h)
colx, x = [], PAD
for w in colw:
    colx.append(x); x += w + GAP
rowy, y = [], PAD
for h in rowh:
    rowy.append(y); y += h + GAP

asm = Asm()
for i, (k, ns, ls_, keep, title, color) in enumerate(blocks):
    if not ns:
        print("  跳过空区块 %s" % k); continue
    c, r = i % COLS, i // COLS
    w, h = sizes[k]
    new = asm.add(ns, ls_, colx[c], rowy[r], title, color, keep_ids=keep)
    print("  %-4s → 画布 (%5d,%5d)  尺寸 %4dx%-5d  %3d 节点%s"
          % (k, colx[c], rowy[r], w, h, len(new), "  [保留原 id]" if keep else ""))

master = {
    "id": BASE_ID,
    "revision": base_wf.get("revision", 0),
    "last_node_id": asm._nid,
    "last_link_id": asm._lid,
    "nodes": sorted(asm.nodes, key=lambda n: n.get("order", 0)),
    "links": asm.links,
    "groups": asm.groups,
    "config": base_wf.get("config", {}),
    "extra": base_wf.get("extra", {}),
    "version": base_wf.get("version", 0.4),
}

# ══════════════════════════ ⑤ 自检 ══════════════════════════
print("\n" + "=" * 72)
print("④ 自检")
print("=" * 72)
errs = []
ids = [n["id"] for n in master["nodes"]]
if len(set(ids)) != len(ids):
    dup = [i for i in set(ids) if ids.count(i) > 1]
    errs.append("节点 id 重复: %s" % dup[:10])
lids = [l[0] for l in master["links"]]
if len(set(lids)) != len(lids):
    errs.append("链接 id 重复")
idset = set(ids)
for lid, fid, fslot, tid, tslot, typ in master["links"]:
    if fid not in idset:
        errs.append("链接 %d 起点节点 %s 不存在" % (lid, fid))
    if tid not in idset:
        errs.append("链接 %d 终点节点 %s 不存在" % (lid, tid))
for n in master["nodes"]:
    if n["type"] == "Note":
        continue
    for s in n.get("inputs", []):
        # ComfyUI 前端会把 widget 端口也列进 inputs（带 "widget" 键，link 恒为 None）——
        # 那是 widgets_values 提供的，本来就不该有线，不算错误。
        if "widget" in s:
            continue
        if s["link"] is None:
            errs.append("节点 %d(%s) 输入 %s 未连接" % (n["id"], n["type"], s["name"]))
    if n["type"] == "KSampler" and len(n.get("widgets_values", [])) != 7:
        errs.append("KSampler %d widgets 数量=%d（应为 7）" % (n["id"], len(n.get("widgets_values", []))))

save_prefixes = [str(n["widgets_values"][0]) for n in master["nodes"]
                 if n["type"] == "SaveImage" and n.get("widgets_values")]
if len(set(save_prefixes)) != len(save_prefixes):
    errs.append("SaveImage 前缀重复（run_wf 会命中多条）")
for p in save_prefixes:
    if not any(p.startswith(x) for x in ("闻灯", "FluxV5", "夜市百相簿")):
        errs.append("SaveImage 前缀 %r 无法被 run_wf 关键词识别" % p)

print("  节点 %d（原 %d + 新 %d）  链接 %d  Group %d"
      % (len(master["nodes"]), len(base_wf["nodes"]),
         len(master["nodes"]) - len(base_wf["nodes"]), len(master["links"]), len(master["groups"])))
print("  SaveImage %d 个：" % len(save_prefixes))
for p in save_prefixes:
    print("     ", p)
print("  Group：")
for g in master["groups"]:
    print("     %-58s x=%d" % (g["title"], g["bounding"][0]))

if errs:
    print("\n  ★ 自检失败 %d 项：" % len(errs))
    for e in errs[:25]:
        print("     -", e)
    sys.exit(1)
print("\n  ✔ 自检全部通过")

out = os.path.join(WF_DIR, "夜市百相簿_主工作流.json")
json.dump(master, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("  已写出 %s  (%.1f KB)" % (out, os.path.getsize(out) / 1024))

# ══════════════════════════ ⑥ 推送 ══════════════════════════
print("\n" + "=" * 72)
print("⑤ 上传身份基图" if PUSH else "⑤ 上传身份基图（未启用）")
print("=" * 72)
print("  脸部块 / Kontext 块两个块共同依赖这一张图，缺它两个块全废。")
if not PUSH:
    print("  加 --push 才会执行。")
    _upload_ok = False
else:
    try:
        _upload_ok = upload_base()
    except Exception as e:
        print("  ★ 上传失败（%s）。" % type(e).__name__)
        _upload_ok = False

print("\n" + "=" * 72)
print("⑥ 推送" if PUSH else "⑥ 推送（未启用）")
print("=" * 72)
if not PUSH:
    print("  加 --push 才会推到服务器（同名覆盖，id 每次换新）。")
    print("  开机后一条命令：python build_master_wf.py --fetch --push")
    sys.exit(0)

if not _upload_ok:
    print("  ★ 基图没上传成功 → 不推工作流。")
    print("     理由：推上去也跑不了（三个块都会报 invalid image file），而实例在烧豆。")
    print("     本地 JSON 已就绪，开机后重跑 python build_master_wf.py --fetch --push")
    sys.exit(3)

# ★★ 每次推送换一个全新 uuid（文件名不变）：
#    ComfyUI 前端打开 /#<id> 时**优先加载 localStorage 里同 id 的旧副本**，不读服务器文件。
#    所以「服务器文件已更新」≠「用户看到的」——只要 id 没变，浏览器就一直给你看它自己那份缓存。
#    历史上靠"换文件名"绕开，代价是服务器上多出一份重复工作流（用户已否掉）。
#    正确做法：文件名固定，**id 每次换新**，浏览器本地没有这个 key，必然拉服务器最新内容。
PUSH_ID = str(uuid.uuid4())
master["id"] = PUSH_ID
body = json.dumps(master, ensure_ascii=False).encode("utf-8")
u = "/api/userdata/workflows%2F" + urllib.parse.quote(MASTER_NAME)
try:
    r = raw(u + "?overwrite=true", body, "application/json", 180, "POST")
    print("  写入成功 ->", r.decode()[:200])
except Exception as e:
    print("  ★ 推送失败（%s）。本地 JSON 已就绪，开机后重跑即可。" % type(e).__name__)
    sys.exit(2)

print("\n  服务器工作流列表：")
try:
    print("   ", raw("/api/userdata?dir=workflows", None, None, 60).decode("utf-8", "replace")[:600])
except Exception as e:
    print("    查询失败", type(e).__name__)

# ══════════════════════════ ⑦ 打开提示 ══════════════════════════
print("""
★ 推送后请在浏览器里打开（id 是新的，旧标签页不会自动看到）：
    %s/#%s
  或：刷新页面 → 左侧 Workflows 侧栏 → 点开「%s」
★ 只此一份，不再有「查看版」。打开后 Ctrl+A 全选 + 按 `.`（Fit view）才能看全三块。
★ 跑图命令（别在浏览器点大「运行」，那会把全部 7 条分支一起跑）：
    python _scripts\\run_wf.py "%s" "闻灯-脸部正面" final     # 第一步：出脸
    python _scripts\\run_wf.py "%s" "闻灯-全身正面" draft     # 第二步：脸部确认后才跑全身草稿
    python _scripts\\run_wf.py "%s" "闻灯Kontext" final       # 转头
""" % (BASE_URL, PUSH_ID, MASTER_NAME, MASTER_NAME, MASTER_NAME, MASTER_NAME))

