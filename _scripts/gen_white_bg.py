"""生成「闻灯 · 白底人物」工作流（半身 / 全身各一份）。

和之前的夜巷版差别：
  1. 背景全部换成纯白，去掉所有环境词 → 画面只剩人物
  2. CFG 6.5 → 6.0（CFG 偏高是 SD 1.5 五官崩坏的主因之一）
  3. 正向加 detailed face / clear facial features，负向加 bad face / deformed face /
     asymmetric eyes 等专门压脸崩的词
  4. 背景词从 44 token 降到 35 token，冲突更少，脸的权重更高
"""

import json
import os

OUT_DIR = r"D:\xiaobai-claude code\ComfyUI\user\default\workflows"

POS_A_BUST = ("character reference, 1boy, solo, 24 year old man, east asian, slim lean build, "
              "short black slightly wavy hair, tired eyes, small mole at outer eye corner, "
              "(faded blue old shirt:1.3), dark old trench coat open, "
              "(holding an old leather ledger:1.2), sharp gaze, upper body, looking at viewer")

POS_A_FULL = ("character reference, 1boy, solo, 24 year old man, east asian, slim lean build, "
              "short black slightly wavy hair, tired eyes, small mole at outer eye corner, "
              "(faded blue old shirt:1.3), dark old trench coat open, "
              "(holding an old leather ledger:1.2), sharp gaze, full body, standing")

POS_B = ("pure white background, plain white backdrop, studio lighting, soft even light, "
         "detailed face, clear facial features, sharp focus, film grain, 35mm lens, photorealistic")

NEG = ("1girl, female, woman, wuxia, idol makeup, exaggerated muscles, child, young boy, "
       "bad face, deformed face, asymmetric eyes, extra limbs, bad hands, extra fingers, "
       "watermark, text, signature, blurry, lowres, busy background, scenery, cluttered, "
       "smooth skin, plastic skin, airbrushed")


def build(pos_a, w, h, uw, uh, prefix, title, note):
    return {
        "last_node_id": 16,
        "last_link_id": 22,
        "nodes": [
            {"id": 16, "type": "Note", "pos": [60, 20], "size": [1580, 230],
             "flags": {}, "order": 0, "mode": 0, "inputs": [], "outputs": [],
             "title": "说明 · " + title, "properties": {"Node name for S&R": "Note"},
             "widgets_values": [note], "color": "#223", "bgcolor": "#335"},

            {"id": 1, "type": "CheckpointLoaderSimple", "pos": [60, 300], "size": [430, 120],
             "flags": {}, "order": 1, "mode": 0, "inputs": [],
             "outputs": [{"name": "MODEL", "type": "MODEL", "links": [4, 16]},
                         {"name": "CLIP", "type": "CLIP", "links": [1, 2, 3]},
                         {"name": "VAE", "type": "VAE", "links": [11, 20]}],
             "properties": {"Node name for S&R": "CheckpointLoaderSimple"},
             "widgets_values": ["majicmixRealistic_v7.safetensors"]},

            {"id": 2, "type": "CLIPTextEncode", "pos": [570, 300], "size": [520, 280],
             "flags": {}, "order": 3, "mode": 0,
             "inputs": [{"name": "clip", "type": "CLIP", "link": 1}],
             "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "links": [5]}],
             "title": "正向 A · 人物（锚点都在这一段）",
             "properties": {"Node name for S&R": "CLIPTextEncode"},
             "widgets_values": [pos_a]},

            {"id": 3, "type": "CLIPTextEncode", "pos": [570, 620], "size": [520, 230],
             "flags": {}, "order": 4, "mode": 0,
             "inputs": [{"name": "clip", "type": "CLIP", "link": 2}],
             "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "links": [6]}],
             "title": "正向 B · 纯白背景与光（35 token）",
             "properties": {"Node name for S&R": "CLIPTextEncode"},
             "widgets_values": [POS_B]},

            {"id": 4, "type": "ConditioningCombine", "pos": [1140, 300], "size": [340, 90],
             "flags": {}, "order": 5, "mode": 0,
             "inputs": [{"name": "conditioning_1", "type": "CONDITIONING", "link": 5},
                        {"name": "conditioning_2", "type": "CONDITIONING", "link": 6}],
             "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "links": [7, 17]}],
             "title": "合并 A + B",
             "properties": {"Node name for S&R": "ConditioningCombine"},
             "widgets_values": []},

            {"id": 5, "type": "CLIPTextEncode", "pos": [570, 890], "size": [520, 240],
             "flags": {}, "order": 6, "mode": 0,
             "inputs": [{"name": "clip", "type": "CLIP", "link": 3}],
             "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "links": [8, 18]}],
             "title": "负向（含专门压「脸崩」的词）",
             "properties": {"Node name for S&R": "CLIPTextEncode"},
             "widgets_values": [NEG]},

            {"id": 6, "type": "EmptyLatentImage", "pos": [60, 470], "size": [430, 130],
             "flags": {}, "order": 2, "mode": 0, "inputs": [],
             "outputs": [{"name": "LATENT", "type": "LATENT", "links": [9]}],
             "title": "画布 %d×%d" % (w, h),
             "properties": {"Node name for S&R": "EmptyLatentImage"},
             "widgets_values": [w, h, 1]},

            {"id": 7, "type": "KSampler", "pos": [1520, 300], "size": [360, 300],
             "flags": {}, "order": 7, "mode": 0,
             "inputs": [{"name": "model", "type": "MODEL", "link": 4},
                        {"name": "positive", "type": "CONDITIONING", "link": 7},
                        {"name": "negative", "type": "CONDITIONING", "link": 8},
                        {"name": "latent_image", "type": "LATENT", "link": 9}],
             "outputs": [{"name": "LATENT", "type": "LATENT", "links": [10, 14]}],
             "title": "KSampler（第一段 · 草稿）",
             "properties": {"Node name for S&R": "KSampler"},
             "widgets_values": [20260916, "randomize", 20, 6.0, "dpmpp_2m", "karras", 1.0]},

            {"id": 8, "type": "VAEDecode", "pos": [1520, 650], "size": [340, 80],
             "flags": {}, "order": 8, "mode": 0,
             "inputs": [{"name": "samples", "type": "LATENT", "link": 10},
                        {"name": "vae", "type": "VAE", "link": 11}],
             "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [12, 13]}],
             "title": "VAEDecode（草稿）",
             "properties": {"Node name for S&R": "VAEDecode"}, "widgets_values": []},

            {"id": 9, "type": "PreviewImage", "pos": [1520, 770], "size": [340, 330],
             "flags": {}, "order": 9, "mode": 0,
             "inputs": [{"name": "images", "type": "IMAGE", "link": 12}],
             "outputs": [], "title": "预览 · 草稿",
             "properties": {"Node name for S&R": "PreviewImage"}, "widgets_values": []},

            {"id": 10, "type": "SaveImage", "pos": [1930, 770], "size": [430, 330],
             "flags": {}, "order": 10, "mode": 0,
             "inputs": [{"name": "images", "type": "IMAGE", "link": 13}],
             "outputs": [], "title": "存图 · 草稿",
             "properties": {"Node name for S&R": "SaveImage"},
             "widgets_values": [prefix + "草稿"]},

            {"id": 11, "type": "LatentUpscale", "pos": [60, 660], "size": [430, 150],
             "flags": {}, "order": 11, "mode": 0,
             "inputs": [{"name": "samples", "type": "LATENT", "link": 14}],
             "outputs": [{"name": "LATENT", "type": "LATENT", "links": [15]}],
             "title": "放大（草稿 → %d×%d）" % (uw, uh),
             "properties": {"Node name for S&R": "LatentUpscale"},
             "widgets_values": ["bislerp", uw, uh, "disabled"]},

            {"id": 12, "type": "KSampler", "pos": [1520, 1150], "size": [360, 300],
             "flags": {}, "order": 12, "mode": 0,
             "inputs": [{"name": "model", "type": "MODEL", "link": 16},
                        {"name": "positive", "type": "CONDITIONING", "link": 17},
                        {"name": "negative", "type": "CONDITIONING", "link": 18},
                        {"name": "latent_image", "type": "LATENT", "link": 15}],
             "outputs": [{"name": "LATENT", "type": "LATENT", "links": [19]}],
             "title": "KSampler（第二段 · 补细节，denoise 别动）",
             "properties": {"Node name for S&R": "KSampler"},
             "widgets_values": [20260916, "fixed", 20, 6.0, "dpmpp_2m", "karras", 0.45]},

            {"id": 13, "type": "VAEDecode", "pos": [1520, 1500], "size": [340, 80],
             "flags": {}, "order": 13, "mode": 0,
             "inputs": [{"name": "samples", "type": "LATENT", "link": 19},
                        {"name": "vae", "type": "VAE", "link": 20}],
             "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [21, 22]}],
             "title": "VAEDecode（成品）",
             "properties": {"Node name for S&R": "VAEDecode"}, "widgets_values": []},

            {"id": 14, "type": "PreviewImage", "pos": [1520, 1620], "size": [430, 620],
             "flags": {}, "order": 14, "mode": 0,
             "inputs": [{"name": "images", "type": "IMAGE", "link": 21}],
             "outputs": [], "title": "★ 预览 · 成品（跑完先看这里）",
             "properties": {"Node name for S&R": "PreviewImage"}, "widgets_values": []},

            {"id": 15, "type": "SaveImage", "pos": [1990, 1620], "size": [430, 620],
             "flags": {}, "order": 15, "mode": 0,
             "inputs": [{"name": "images", "type": "IMAGE", "link": 22}],
             "outputs": [], "title": "存图 · 成品",
             "properties": {"Node name for S&R": "SaveImage"},
             "widgets_values": [prefix + "成品"]}
        ],
        "links": [
            [1, 1, 1, 2, 0, "CLIP"], [2, 1, 1, 3, 0, "CLIP"], [3, 1, 1, 5, 0, "CLIP"],
            [4, 1, 0, 7, 0, "MODEL"], [5, 2, 0, 4, 0, "CONDITIONING"], [6, 3, 0, 4, 1, "CONDITIONING"],
            [7, 4, 0, 7, 1, "CONDITIONING"], [8, 5, 0, 7, 2, "CONDITIONING"], [9, 6, 0, 7, 3, "LATENT"],
            [10, 7, 0, 8, 0, "LATENT"], [11, 1, 2, 8, 1, "VAE"], [12, 8, 0, 9, 0, "IMAGE"],
            [13, 8, 0, 10, 0, "IMAGE"], [14, 7, 0, 11, 0, "LATENT"], [15, 11, 0, 12, 3, "LATENT"],
            [16, 1, 0, 12, 0, "MODEL"], [17, 4, 0, 12, 1, "CONDITIONING"], [18, 5, 0, 12, 2, "CONDITIONING"],
            [19, 12, 0, 13, 0, "LATENT"], [20, 1, 2, 13, 1, "VAE"], [21, 13, 0, 14, 0, "IMAGE"],
            [22, 13, 0, 15, 0, "IMAGE"]
        ],
        "groups": [], "config": {}, "extra": {}, "version": 0.4
    }


NOTE_BUST = (
    "闻灯 · 白底半身　【底模 majicmixRealistic_v7（SD 1.5）】\n\n"
    "【为什么这张脸不容易崩 —— 四道保险】\n"
    "  1. 半身构图：脸占了画面的很大一块，像素够，五官才立得住。全身构图时脸只有 60-80 像素，必崩。\n"
    "  2. CFG 从 6.5 降到 6.0：CFG 偏高是 SD 1.5 五官扭曲、眼睛不对称的头号原因。\n"
    "  3. 背景换成纯白：原来那 44 token 的环境词（夜市/巷子/火光）全删了，\n"
    "     模型不用再分心去画场景，注意力都在人身上。\n"
    "  4. 负向里加了 bad face / deformed face / asymmetric eyes 三个压脸崩的词。\n\n"
    "【尺寸】512×640 半身 → 高清修复到 768×960。本机纯 CPU 约 18 分钟。\n"
    "【预览】跑完先看「★ 预览 · 成品」那个节点，图会直接显示在界面上。\n\n"
    "想把背景再压白一点：把正向 B 段里的 (pure white background:1.3) 改成 1.4。\n"
    "想要全身：把画布改成 512×768、「放大」改成 768×1152，\n"
    "并把正向 A 段末尾的 upper body 换成 full body, standing（有另一个现成文件）。")

NOTE_FULL = (
    "闻灯 · 白底全身　【底模 majicmixRealistic_v7（SD 1.5）】\n\n"
    "和半身版的唯一区别：构图改成全身竖构图，画布 512×768 → 高清修复到 768×1152。\n\n"
    "⚠ 必须先知道的事实：全身构图时，脸在画面里大约只占 60-80 像素，\n"
    "   所以「眼尾小痣」这种细节在这一张里基本看不到，脸也比半身版糊。\n"
    "   这是构图决定的，不是提示词写得不好 —— 半身/特写才看得清脸。\n\n"
    "【已做的抗崩脸处理】CFG 降到 6.0、背景换纯白（删掉全部环境词）、\n"
    "  负向加 bad face / deformed face / asymmetric eyes。\n\n"
    "【尺寸】512×768 → 768×1152，本机纯 CPU 约 22 分钟。\n"
    "【预览】跑完先看「★ 预览 · 成品」那个节点。\n\n"
    "建议用法：全身这张用来看服装和整体体态，脸要清楚就用半身那张。")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    files = [
        ("闻灯-白底半身.json", build(POS_A_BUST, 512, 640, 768, 960, "闻灯-白底半身", "闻灯 · 白底半身", NOTE_BUST)),
        ("闻灯-白底全身.json", build(POS_A_FULL, 512, 768, 768, 1152, "闻灯-白底全身", "闻灯 · 白底全身", NOTE_FULL)),
    ]
    for name, data in files:
        p = os.path.join(OUT_DIR, name)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("已写入 %s  (%.1f KB, %d 节点)" % (p, os.path.getsize(p) / 1024, len(data["nodes"])))


if __name__ == "__main__":
    main()
