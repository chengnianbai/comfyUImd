# -*- coding: utf-8 -*-
"""v2：按视角各用「自己的」已确认脸作 Identity Reference；参考图裁成纯头部（去衬衫）

用户决定（2026-10-08）
  · 去掉参考图里的衬衫（母版下半身是蓝色衬衫，被参考潜空间一起传了过去 → 违反 §8.1）
  · 先按 Flux 走（ReferenceLatent），IP-Adapter 不装
  · 侧脸图必须与「已确认的左侧脸成品」同一张脸 ⇒ 每视角用各自的已确认脸当参考
  · 正面歪头、身材比例不对 ⇒ 提示词补「头端正/水平双眼」与「7~8 头身、正确肩髋比」
  · 依据附录 B.7，撤掉侧面/背面残留的第二段重绘（314/344）

链路（每视角一套，全部 denoise 1.0 从空潜空间整张重画）
  已确认脸(该视角) → FluxKontextImageScale → VAEEncode(Flux VAE) → 参考 LATENT
  视角指令词 → FluxGuidance(3.0) → ReferenceLatent(参考 LATENT) → KSampler.positive
  EmptySD3LatentImage(768x1344, 三视角共用) → KSampler.latent_image
  flux-schnell / 20步 / cfg1.0 / euler-simple / denoise 1.0 → VAEDecode → 既有放大链路 → 既有成品前缀

用法： python _refgen_fullbody_v2.py dry | run | push
"""
import os, sys, io, ssl, json, time, uuid, urllib.request, urllib.parse
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
import numpy as np
from PIL import Image
BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
if not BASE:
    print("★ 先设 COMFY_BASE"); sys.exit(4)
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
ROOT = r"D:\xiaobai-claude code\comfyUImd"
WFDIR = os.path.join(ROOT, "_scripts", "_wf")
OUT = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "refgen2")
WFNAME = "夜市百相簿-主工作流.json"
ENC = urllib.parse.quote(WFNAME, safe='')
MODE = sys.argv[1] if len(sys.argv) > 1 else "dry"
DELETE = [30, 31, 32, 33, 34, 306, 307, 308, 309, 310]
DISABLE = [314, 344]
W, H = 768, 1344
SEED = 20261008
os.makedirs(OUT, exist_ok=True)
HEAD_CROP = (0.00, 0.62, 0.14, 0.90)      # y0,y1,x0,x1 比例：只留头部，切掉衬衫与肩线


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


# ---------- 0. 找线上每个视角最新的「已确认脸成品」，裁头部，上传 ----------
hist = json.loads(raw("/history").decode('utf-8', 'replace'))
best = {}
for pid, rec in hist.items():
    for nid, o in (rec.get("outputs") or {}).items():
        for im in o.get("images", []):
            fn = im.get("filename", "")
            for key, pref in (("front", "闻灯-脸部正面-成品"), ("left", "闻灯-脸部左侧-成品"),
                              ("right", "闻灯-脸部右侧-成品")):
                if fn.startswith(pref):
                    n = int(''.join(ch for ch in fn[len(pref):] if ch.isdigit()) or 0)
                    if key not in best or n > best[key][0]: best[key] = (n, fn)
print("=== 线上最新的已确认脸 ===")
for k in ("front", "left", "right"):
    print("  %-6s %s" % (k, best.get(k, ("-", "缺"))[1]))
if not all(k in best for k in ("front", "left", "right")):
    print("★ 有视角缺成品"); sys.exit(1)
IDFILE = {}
for k, (n, fn) in best.items():
    q = urllib.parse.urlencode({"filename": fn, "subfolder": "", "type": "output"})
    p = os.path.join(OUT, "_src_" + fn); open(p, "wb").write(raw("/view?" + q))
    im = Image.open(p).convert("RGB"); Wd, Hd = im.size
    y0, y1, x0, x1 = HEAD_CROP
    c = im.crop((int(Wd*x0), int(Hd*y0), int(Wd*x1), int(Hd*y1)))
    a = np.asarray(c).astype(np.int16)
    blue = ((a[:, :, 2] - a[:, :, 0]) > 18).mean()
    # ★ 关键：# 把头部按「全身 7.5 头身」的比例摆进一张 768x1344 的空白参考画布。
    #   ReferenceLatent 会连「画面布局」一起传过去；若参考是脸部特写，模型就会照抄"大脸"布局 → 头大身小。
    hh = int(H / 7.5)                      # 目标头高
    top = int(H * 0.04)                    # 头顶留白
    nw = int(c.size[0] * hh / c.size[1])
    canvas = Image.new("RGB", (W, H), (255, 255, 255))
    canvas.paste(c.resize((nw, hh), Image.LANCZOS), ((W - nw)//2, top))
    outn = "wendeng_id_%s.png" % k
    canvas.save(os.path.join(OUT, outn))
    IDFILE[k] = outn
    print("  %-6s %s %dx%d → 头裁 %dx%d → 摆进 %dx%d 参考画布（头 %dx%d @ y=%d, 占图高 %.1f%%；蓝像素 %.2f%%）"
          % (k, fn, Wd, Hd, c.size[0], c.size[1], W, H, nw, hh, top, 100*hh/H, 100*blue))
    body = io.open(os.path.join(OUT, outn), "rb").read()
    B = "----cmdc" + uuid.uuid4().hex
    part = (("--%s\r\nContent-Disposition: form-data; name=\"image\"; filename=\"%s\"\r\n"
             "Content-Type: image/png\r\n\r\n" % (B, outn)).encode() + body +
            ("\r\n--%s\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n--%s--\r\n"
             % (B, B)).encode())
    r = raw("/upload/image", part, "multipart/form-data; boundary=" + B, 300)
    print("         上传 %s → %s" % (outn, r.decode('utf-8', 'replace')[:80]))

# ---------- 提示词（★ 2026-10-08 用户提供的优化稿，逐字采用）----------
COMMON_HEAD = ("Full-length character reference photograph of a young man wearing a plain white crew-neck t-shirt "
               "and plain white shorts, bare feet: simple clean white t-shirt, no logo, no print, no pattern, "
               "no pocket; nothing worn over the t-shirt, no jacket, no coat, no collar, no tie, no scarf; "
               "plain white shorts. ")
# ★ 2026-10-08 用户关键词里的 "Refined high-fashion **European** male model" 是强人群先验：
#   全身尺度下参考图里那个头只占约 5% 画面面积（为防头大身小按 7.5 头身缩小摆放），
#   身份信号本就弱 → "欧洲男模"直接压过去，脸变欧洲人、头发变后梳直发。
#   改法：① 最前面加人群/发型硬锚点顶住参考；② 体型段去掉人群词，只留体型语义。
COMMON_ANCHOR = ("A young East Asian man with East Asian facial features, the same East Asian person as the "
                 "reference: same ethnicity, same face, same messy wavy black hair, same hairline, same black hair "
                 "colour. He must never look Caucasian, never look European, never change ethnicity. ")
COMMON_IDENT = ("Preserve the exact identity of the reference: same facial structure and face shape, same facial "
                "proportions, same eyes and eyebrows, same nose shape, same lips, same chin and jawline, same "
                "hairline and haircut, same messy wavy black hair, same apparent age, same small mole at the outer "
                "corner of the eye, same stable identity marks. ")
COMMON_PROP = ("Refined slender athletic male body proportions like a professional fashion model, with an elegant, "
               "naturally athletic physique: approximately 8-head body proportion, a relatively small head compared "
               "with the body, long legs and a long visual leg line, moderately broad and well-shaped shoulders, a "
               "defined but not bulky upper torso, a naturally narrow waist, subtle V-shaped torso, balanced chest "
               "and shoulder development, lean but healthy body mass, long and refined limbs, straight elegant legs, "
               "natural hip width, proportional arms and hands. The physique should look like a professional fashion "
               "model rather than a bodybuilder or fitness model: neither muscular nor bulky, neither skinny nor "
               "underweight, with restrained muscle definition and a clean, sophisticated silhouette. Realistic adult "
               "male anatomy and natural body volume, with no exaggerated muscularity, no extreme thinness, "
               "no oversized head, no shortened legs, no distorted proportions. ")
COMMON_BODY = ("Full body visible from head to feet, head to toe, the entire standing figure inside the frame with "
               "clear space above the head and below the feet, standing straight, arms relaxed naturally at the "
               "sides, weight evenly on both feet, feet fully visible, centered composition. ")
COMMON_TAIL = ("Pure white seamless background, soft even studio lighting, unified lighting and material across the "
               "whole figure, realistic skin texture with subtle visible pores, natural photographic grain, ")
FRONT = (COMMON_HEAD + COMMON_ANCHOR +
         "Regenerate this person as a natural high-end photographic full-length reference photo of "
         "the same exact person. " + COMMON_IDENT +
         "Facing the camera directly, front view, looking straight at the viewer. "
         "The head is held perfectly upright and level: the eye line is horizontal, the head is not tilted and not "
         "turned, the chin is level, the neck is vertical, both shoulders are level and at the same height. "
         + COMMON_PROP + COMMON_BODY + COMMON_TAIL + "sharp focus on the face.")
SIDE = (COMMON_HEAD + COMMON_ANCHOR +
        "Regenerate this person as a natural high-end photographic full-length reference photo of "
        "the same exact person, seen from a true anatomical 90-degree LEFT profile, head turned to the left, pure "
        "profile view showing the nose line, lips, chin and jaw line, one eye visible. " + COMMON_IDENT +
        "The head is held perfectly upright and level: the eye line is horizontal, the head is not tilted, the chin "
        "is level, the neck is vertical, the torso remains upright, and the shoulders are level. "
        + COMMON_PROP + COMMON_BODY + COMMON_TAIL + "sharp focus on the visible profile.")
BACK = (COMMON_HEAD + COMMON_ANCHOR +
        "Regenerate this person as a natural high-end photographic full-length reference photo of "
        "the same exact person, seen from directly behind, back view, the face is not visible; the back of the "
        "head, the hair, the neck, the white t-shirt over the shoulders and back are visible. Keep exactly the same "
        "messy wavy black hair and the same head shape as the reference. The head is held perfectly upright and "
        "level, the neck is vertical, the torso remains upright, and both shoulders are level and symmetrical. "
        + COMMON_PROP + COMMON_BODY + COMMON_TAIL + "sharp focus on the hair, neck, shoulders and back.")
# 侧面/背面的体重分配措辞按用户稿
SIDE = SIDE.replace("weight evenly on both feet,", "weight evenly distributed on both feet,")
BACK = BACK.replace("weight evenly on both feet,", "weight evenly distributed on both feet,")
VIEWS = [(1310, "正面 front", "front", FRONT),
         (1330, "侧面 left profile", "left", SIDE),
         (1350, "背面 back", "front", BACK)]

# ---------- 改工作流 ----------
print("\n" + "="*100)
print("=== 全身关键词（Flux 正向词，按视角三段）===")
for base, label, key, instr in VIEWS:
    io.open(os.path.join(OUT, "全身关键词_%s.txt" % label.replace(" ", "_")), "w", encoding="utf-8").write(instr)
    print("\n【%s】共用参考=%s  (%d 字符)" % (label, IDFILE[key], len(instr)))
    print(instr)
print("\n" + "="*100)

wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
byid = {n["id"]: n for n in wf["nodes"]}
host = urllib.parse.urlparse(BASE).netloc.split(".")[0]
bp = os.path.join(WFDIR, "_backup_pre_refgen2_%s_%s.json" % (host, time.strftime("%Y%m%d_%H%M%S")))
io.open(bp, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("\n线上 nodes=%d links=%d ；备份 %s" % (len(wf["nodes"]), len(wf["links"]), os.path.basename(bp)))
TPL = {"ktscale": 1028, "vaeenc": 1029, "empty": 1052, "text": 1031, "guide": 1032,
       "reflat": 1033, "ksampler": 1034, "dec": 1035, "loadimg": 1004}
for k, i in TPL.items():
    if i not in byid: print("★ 模板 #%s 不存在" % i); sys.exit(1)
lid = max(l[0] for l in wf["links"])


def unlink(dst, slot):
    d = byid.get(dst)
    if not d: return None
    k = next((i for i, x in enumerate(d.get("inputs") or []) if x.get("name") == slot), None)
    if k is None: return None
    old = d["inputs"][k].get("link"); d["inputs"][k]["link"] = None
    if old is None: return None
    l = next((x for x in wf["links"] if x[0] == old), None)
    if l:
        s = byid.get(l[1])
        if s:
            for o in (s.get("outputs") or []):
                if o.get("links"): o["links"] = [x for x in o["links"] if x != old]
    wf["links"] = [x for x in wf["links"] if x[0] != old]
    return l[1] if l else None


def wire(sid, sout, did, din, stype):
    global lid
    sn, dn = byid[sid], byid[did]
    oslot = next((k for k, o in enumerate(sn.get("outputs") or []) if o.get("name") == sout), None)
    dslot = next((k for k, x in enumerate(dn.get("inputs") or []) if x.get("name") == din), None)
    if oslot is None or dslot is None:
        print("★ 连线失败 #%s.%s -> #%s.%s" % (sid, sout, did, din)); sys.exit(1)
    lid += 1
    wf["links"].append([lid, sid, oslot, did, dslot, stype])
    dn["inputs"][dslot]["link"] = lid
    sn["outputs"][oslot].setdefault("links", [])
    if sn["outputs"][oslot]["links"] is None: sn["outputs"][oslot]["links"] = []
    sn["outputs"][oslot]["links"].append(lid)


def clone(key, nid, pos, title, widgets=None):
    n = json.loads(json.dumps(byid[TPL[key]])); n["id"] = nid
    n["title"] = title; n["mode"] = 0; n["order"] = 850 + nid
    for i in (n.get("inputs") or []): i["link"] = None
    for o in (n.get("outputs") or []): o["links"] = []
    if widgets is not None: n["widgets_values"] = widgets
    n["pos"] = pos
    wf["nodes"].append(n); byid[nid] = n
    return n


gone = [l for l in wf["links"] if l[1] in DELETE or l[3] in DELETE]
wf["links"] = [l for l in wf["links"] if l[1] not in DELETE and l[3] not in DELETE]
gid = {l[0] for l in gone}
for n in wf["nodes"]:
    for o in (n.get("outputs") or []):
        if o.get("links"): o["links"] = [x for x in o["links"] if x not in gid]
wf["nodes"] = [n for n in wf["nodes"] if n["id"] not in DELETE]
print("删除贴脸链路 %d 条连线" % len(gone))

BX, BY = 19600, 300
clone("empty", 1302, [BX, BY], "空潜空间 %dx%d（三视角共用）" % (W, H), [W, H, 1])
DEC = {}
for base, label, key, instr in VIEWS:
    x = BX + 500 + (base // 100 - 13) * 820
    clone("loadimg", base + 0, [x, BY], "★ 已确认脸 · %s（参考输入，已去衬衫）" % label, [IDFILE[key], "image"])
    clone("ktscale", base + 1, [x + 250, BY], "参考归一化")
    clone("vaeenc", base + 2, [x + 500, BY], "参考 → LATENT")
    clone("text", base + 3, [x, BY + 300], "指令词 · %s（%d 字符）" % (label, len(instr)), [instr])
    clone("guide", base + 4, [x, BY + 900], "FluxGuidance 3.0")
    clone("reflat", base + 5, [x, BY + 1050], "ReferenceLatent")
    clone("ksampler", base + 6, [x, BY + 1230], "KSampler · flux-schnell · denoise 1.0",
          [SEED, "fixed", 20, 1.0, "euler", "simple", 1.0])
    clone("dec", base + 7, [x, BY + 1590], "VAEDecode")
    wire(base + 0, "IMAGE", base + 1, "image", "IMAGE")
    wire(base + 1, "IMAGE", base + 2, "pixels", "IMAGE")
    wire(1026, "VAE", base + 2, "vae", "VAE")
    wire(1025, "CLIP", base + 3, "clip", "CLIP")
    wire(base + 3, "CONDITIONING", base + 4, "conditioning", "CONDITIONING")
    wire(base + 4, "CONDITIONING", base + 5, "conditioning", "CONDITIONING")
    wire(base + 2, "LATENT", base + 5, "latent", "LATENT")
    wire(1024, "MODEL", base + 6, "model", "MODEL")
    wire(base + 5, "CONDITIONING", base + 6, "positive", "CONDITIONING")
    wire(1030, "CONDITIONING", base + 6, "negative", "CONDITIONING")
    wire(1302, "LATENT", base + 6, "latent_image", "LATENT")
    wire(base + 6, "LATENT", base + 7, "samples", "LATENT")
    wire(1026, "VAE", base + 7, "vae", "VAE")
    DEC[base] = base + 7
    print("  分支 %-16s 参考=%s  节点 #%d..#%d" % (label, IDFILE[key], base, base + 7))

# ---- 5. SDXL 收尾（★ 在 768x1344 原生分辨率上做，再进 4x 放大）----
# 用户 2026-10-08：把 SDXL 收尾接上 —— 已确认脸的毛孔来自 SDXL，纯 Flux 出的是蜡感，
# 故在 Flux 出完身份后加一道 SDXL img2img，把皮肤质感换成已确认脸那一套。
# 原链路把二次采样放在 4x 放大之后（1536x2688），对 SDXL 是灾难分辨率 → 必须前置。
PASS = [(1310, 25, 12, 13, 23, None, None),
        (1330, 313, 314, 315, 311, 316, 312),
        (1350, 343, 344, 345, 341, 346, 342)]
for base, enc, ks, dec, up, fin, scb in PASS:
    src = DEC[base]
    o1 = unlink(enc, "pixels"); wire(src, "IMAGE", enc, "pixels", "IMAGE")
    byid[enc]["mode"] = 0; byid[ks]["mode"] = 0; byid[dec]["mode"] = 0
    wv = list(byid[ks]["widgets_values"]); wv[6] = 0.30; byid[ks]["widgets_values"] = wv
    o2 = unlink(up, "image"); wire(dec, "IMAGE", up, "image", "IMAGE")
    print("  #%-4s 收尾: 编码 #%s.pixels %s->#%s | #%s denoise 0.25->0.40 | #%s.image %s->#%s"
          % (ks, enc, o1, src, ks, up, o2, dec))
    if fin:
        o3 = unlink(fin, "images"); wire(scb, "IMAGE", fin, "images", "IMAGE")
        print("        #%s(成品).images %s -> #%s（放大后的净 2x）" % (fin, o3, scb))

left = [n["id"] for n in wf["nodes"] if n["type"] in ("SolidMask", "FeatherMask", "ImageCompositeMasked", "LoadImageOutput")]
assert not left, left

# ---- 6. SDXL 收尾用的提示词（≤75 token/段；用户 2026-10-08：保留白 T 恤）----
A_FRONT = ("full body shot head to toe, entire body visible, feet fully visible, standing straight, arms at sides, "
           "centered, 1boy, solo, 24 year old east asian man, masculine face, messy wavy black hair, "
           "small mole at outer eye corner, plain white crew-neck t-shirt, plain white shorts, pure white background")
A_SIDE = ("full body shot head to toe, entire body visible, feet fully visible, side view, side profile, standing "
          "straight, arms at sides, centered, 1boy, solo, 24 year old east asian man, masculine face, "
          "plain white crew-neck t-shirt, plain white shorts, pure white background")
A_BACK = ("full body shot head to toe, entire body visible, feet fully visible, back view, seen from behind, "
          "standing straight, arms at sides, centered, 1boy, solo, 24 year old east asian man, messy wavy black "
          "hair, plain white crew-neck t-shirt, plain white shorts, pure white background")
B_OLD = str((byid[3].get("widgets_values") or [""])[0])
EXTRA_B = ", small head relative to the body, head about one eighth of the figure height, no big head, long legs"
N_NEW = ("jacket, coat, sweater, hoodie, hood, suit, blazer, tie, collar, scarf, patterned shirt, printed shirt, "
         "logo, text on shirt, denim jacket, bare chest, shirtless, topless, nude, naked, dark background, "
         "grey background, gradient background, vignette, shadow, busy background, blurry, lowres, bad anatomy, "
         "extra limbs, deformed, big head, oversized head, short legs, cropped")
for nid, txt in ((2, A_FRONT), (300, A_SIDE), (330, A_BACK)):
    byid[nid]["widgets_values"] = [txt]
if EXTRA_B not in B_OLD:
    byid[3]["widgets_values"] = [B_OLD + EXTRA_B]
byid[18]["widgets_values"] = [N_NEW]
print("\nSDXL 收尾词已更新：#2 正面 / #300 侧面 / #330 背面 重写；#3 补头身比；#18 负向改为"
      "（禁外套，但不再禁 t-shirt；同时禁 shirtless）")
print("   #18 负向 = %s" % N_NEW)
print("残留贴脸类节点：无 ✔   nodes=%d links=%d" % (len(wf["nodes"]), len(wf["links"])))
out_local = os.path.join(WFDIR, "_pending_refgen2.json")
io.open(out_local, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
if MODE == "dry":
    print("\n[dry] 未联网跑。"); sys.exit(0)

sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                       # noqa
API, _ = build_api(wf)
TARGETS = [nid for nid, x in API.items() if x["class_type"] == "SaveImage"
           and str(x["inputs"].get("filename_prefix", "")).startswith("闻灯-全身")
           and str(x["inputs"].get("filename_prefix", "")).endswith("成品")]
print("\n=== 目标 %s ===" % [API[t]["inputs"]["filename_prefix"] for t in TARGETS])
subg = {k: v for k, v in API.items() if k in deps(API, TARGETS)}
print("   裁剪后 %d 节点；KSampler %s" % (len(subg),
      sorted([k for k, v in subg.items() if v["class_type"] == "KSampler"], key=int)))
res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 180).decode())
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:1800]); sys.exit(1)
pid = res["prompt_id"]; print("prompt_id=%s" % pid)
done = None
for i in range(700):
    time.sleep(4)
    try:
        h = json.loads(raw("/history/" + pid, None, None, 60).decode('utf-8', 'replace'))
    except Exception:
        continue
    if pid in h:
        st = h[pid].get("status", {})
        if st.get("status_str") == "error":
            for m in st.get("messages", []):
                if m[0] == "execution_error":
                    print("★ ERROR %s: %s" % (m[1].get("node_type"), m[1].get("exception_message", "")[:400]))
            sys.exit(1)
        done = h[pid].get("outputs", {}); print("完成，约 %d 秒" % ((i+1)*4)); break
if done is None: print("★ 超时"); sys.exit(1)
for nid, o in done.items():
    for im in o.get("images", []):
        q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        p = os.path.join(OUT, im["filename"]); open(p, "wb").write(raw("/view?" + q, None, None, 300))
        print("   saved %-44s %7.1f KB" % (im["filename"], os.path.getsize(p)/1024))
print("\n[run] 未写工作流（等你看过再说）。staged: %s" % os.path.basename(out_local))
