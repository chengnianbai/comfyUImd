# -*- coding: utf-8 -*-
"""只更新三条 Flux 指令词（去掉人群先验 "European"，加人群/发型硬锚点），然后跑 + 写回

线上已是 v3 结构（128 节点，贴脸链路已删、1024x1792、资产C 分支已建），
所以这里只做「改词 → 跑 → 写回」，不重建图。

背景：用户关键词里 "Refined high-fashion European male model proportions" 这个人群先验，
在全身尺度（参考图里头只占约 5% 面积）下直接压过参考 → 脸变欧洲人、头发变后梳直发。
"""
import os, sys, io, ssl, json, time, uuid, urllib.request, urllib.parse
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
BASE = os.environ.get("COMFY_BASE", "").rstrip("/")
if not BASE:
    print("★ 先设 COMFY_BASE"); sys.exit(4)
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
ROOT = r"D:\xiaobai-claude code\comfyUImd"
WFDIR = os.path.join(ROOT, "_scripts", "_wf")
OUT = os.path.join(ROOT, "系列-夜市百相簿/02-角色/闻灯/设定图", "_exp_0924", "refgen4")
ENC = urllib.parse.quote("夜市百相簿-主工作流.json", safe='')
os.makedirs(OUT, exist_ok=True)

HEAD = ("Full-length character reference photograph of a young man wearing a plain white crew-neck t-shirt and plain "
        "white shorts, bare feet: simple clean white t-shirt, no logo, no print, no pattern, no pocket; nothing worn "
        "over the t-shirt, no jacket, no coat, no collar, no tie, no scarf; plain white shorts. ")
ANCHOR = ("A young East Asian man with East Asian facial features, the same East Asian person as the reference: same "
          "ethnicity, same face, same messy wavy black hair, same hairline, same black hair colour. He must never "
          "look Caucasian, never look European, never change ethnicity. ")
IDENT = ("Preserve the exact identity of the reference: same facial structure and face shape, same facial proportions, "
         "same eyes and eyebrows, same nose shape, same lips, same chin and jawline, same hairline and haircut, same "
         "messy wavy black hair, same apparent age, same small mole at the outer corner of the eye, same stable "
         "identity marks. ")
PROP = ("Refined slender athletic male body proportions like a professional fashion model, with an elegant, naturally "
        "athletic physique: approximately 8-head body proportion, a relatively small head compared with the body, "
        "long legs and a long visual leg line, moderately broad and well-shaped shoulders, a defined but not bulky "
        "upper torso, a naturally narrow waist, subtle V-shaped torso, balanced chest and shoulder development, lean "
        "but healthy body mass, long and refined limbs, straight elegant legs, natural hip width, proportional arms "
        "and hands. The physique should look like a professional fashion model rather than a bodybuilder or fitness "
        "model: neither muscular nor bulky, neither skinny nor underweight, with restrained muscle definition and a "
        "clean, sophisticated silhouette. Realistic adult male anatomy and natural body volume, with no exaggerated "
        "muscularity, no extreme thinness, no oversized head, no shortened legs, no distorted proportions. ")
BODY = ("Full body visible from head to feet, head to toe, the entire standing figure inside the frame with clear "
        "space above the head and below the feet, standing straight, arms relaxed naturally at the sides, weight "
        "evenly distributed on both feet, feet fully visible, centered composition. ")
TAIL = ("Pure white seamless background, soft even studio lighting, unified lighting and material across the whole "
        "figure, realistic skin texture with subtle visible pores, natural photographic grain, ")
P = {
 1313: HEAD + ANCHOR + "Regenerate this person as a natural high-end photographic full-length reference photo of the "
       "same exact person. " + IDENT + "Facing the camera directly, front view, looking straight at the viewer. "
       "The head is held perfectly upright and level: the eye line is horizontal, the head is not tilted and not "
       "turned, the chin is level, the neck is vertical, both shoulders are level and at the same height. "
       + PROP + BODY + TAIL + "sharp focus on the face.",
 1333: HEAD + ANCHOR + "Regenerate this person as a natural high-end photographic full-length reference photo of the "
       "same exact person, seen from a true anatomical 90-degree LEFT profile, head turned to the left, pure profile "
       "view showing the nose line, lips, chin and jaw line, one eye visible. " + IDENT +
       "The head is held perfectly upright and level: the eye line is horizontal, the head is not tilted, the chin "
       "is level, the neck is vertical, the torso remains upright, and the shoulders are level. "
       + PROP + BODY + TAIL + "sharp focus on the visible profile.",
 1353: HEAD + ANCHOR + "Regenerate this person as a natural high-end photographic full-length reference photo of the "
       "same exact person, seen from directly behind, back view, the face is not visible; the back of the head, the "
       "hair, the neck, the white t-shirt over the shoulders and back are visible. Keep exactly the same messy wavy "
       "black hair and the same head shape as the reference. The head is held perfectly upright and level, the neck "
       "is vertical, the torso remains upright, and both shoulders are level and symmetrical. "
       + PROP + BODY + TAIL + "sharp focus on the hair, neck, shoulders and back.",
}


def raw(p, data=None, ctype=None, timeout=600):
    h = {}
    if ctype: h["Content-Type"] = ctype
    return urllib.request.urlopen(urllib.request.Request(BASE + p, data=data, headers=h),
                                  timeout=timeout, context=ctx).read()


wf = json.loads(raw("/api/userdata/workflows%2F" + ENC, None, None, 120).decode('utf-8', 'replace'))
byid = {n["id"]: n for n in wf["nodes"]}
host = urllib.parse.urlparse(BASE).netloc.split(".")[0]
bp = os.path.join(WFDIR, "_backup_pre_fbprompt_%s_%s.json" % (host, time.strftime("%Y%m%d_%H%M%S")))
io.open(bp, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))
print("线上 nodes=%d ；备份 %s" % (len(wf["nodes"]), os.path.basename(bp)))
for nid, txt in P.items():
    old = str((byid[nid].get("widgets_values") or [""])[0])
    print("  #%s %d字符 -> %d字符 ；含 European=%s ；含 East Asian 锚点=%s"
          % (nid, len(old), len(txt), "European" in txt, "East Asian" in txt))
    byid[nid]["widgets_values"] = [txt]
    io.open(os.path.join(OUT, "关键词_%s.txt" % nid), "w", encoding="utf-8").write(txt)
out_local = os.path.join(WFDIR, "_pending_fbprompt.json")
io.open(out_local, "w", encoding="utf-8").write(json.dumps(wf, ensure_ascii=False, indent=1))

sys.path.insert(0, os.path.join(ROOT, "_scripts"))
from wf_api import build_api, deps                       # noqa
API, _ = build_api(wf)
TARGETS = [nid for nid, x in API.items() if x["class_type"] == "SaveImage"
           and (str(x["inputs"].get("filename_prefix", "")).startswith("闻灯-全身")
                and str(x["inputs"].get("filename_prefix", "")).endswith("成品")
                or str(x["inputs"].get("filename_prefix", "")) == "闻灯-全身正面-脸部精修-成品")]
print("\n目标 %s" % [API[t]["inputs"]["filename_prefix"] for t in TARGETS])
subg = {k: v for k, v in API.items() if k in deps(API, TARGETS)}
res = json.loads(raw("/prompt", json.dumps({"prompt": subg, "client_id": str(uuid.uuid4())}).encode(),
                     "application/json", 180).decode())
if res.get("node_errors"):
    print("★ node_errors:"); print(json.dumps(res["node_errors"], ensure_ascii=False, indent=1)[:1500]); sys.exit(1)
pid = res["prompt_id"]; print("prompt_id=%s" % pid)
done = None
for i in range(900):
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
        print("   saved %-46s %7.1f KB" % (im["filename"], os.path.getsize(p)/1024))
body = io.open(out_local, encoding="utf-8").read().encode("utf-8")
ok = False
for i in range(5):
    try:
        r = urllib.request.Request(BASE + "/api/userdata/workflows%2F" + ENC, data=body,
                                   headers={"Content-Type": "application/json",
                                            "Content-Length": str(len(body)), "Connection": "close"})
        urllib.request.urlopen(r, timeout=300, context=ctx).read(); ok = True; break
    except Exception as e:
        print("  第 %d 次写入失败 %s" % (i+1, type(e).__name__)); time.sleep(6)
print("✔ 已写回（三视角关键词已去人群先验）" if ok else "★ 写回失败")
