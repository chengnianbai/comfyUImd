# -*- coding: utf-8 -*-
"""v19 token 预算测算：脸部锁定块 + 全身复用块"""
import sys
sys.path.insert(0, r"D:\xiaobai-claude code\ComfyUI\venv\Lib\site-packages")
from transformers import CLIPTokenizer
tk = CLIPTokenizer.from_pretrained(r"D:\xiaobai-claude code\ComfyUI\comfy\sd1_tokenizer")
def t(s): return len(tk.encode(s, add_special_tokens=False))

BGD = "pure white background"
HAIR = "messy wavy black hair"                 # v13 已确认脸用的发型词
MOLE = "small mole at outer eye corner"
COAT = "dark worn trench coat"

# ===== 脸部（v13 原样锁定，用户已确认）=====
FACE_A = ("front view, looking at viewer, face closeup, head and shoulders, 1boy, solo, "
          "24 year old east asian man, masculine face, strong jaw, " + HAIR + ", " + MOLE + ", "
          "faded blue shirt collar, dark coat collar, " + BGD)
FACE_A_SIDE = ("side profile view, face closeup, head and shoulders, 1boy, solo, "
               "24 year old east asian man, masculine face, strong jaw, " + HAIR + ", " + MOLE + ", "
               "faded blue shirt collar, dark coat collar, " + BGD)
FACE_B = ("detailed face, detailed eyes, dark circles under eyes, iris detail, individual eyelashes, "
          "thick eyebrows, stubble, " + MOLE + ", visible skin pores, skin texture, skin imperfections, "
          "peach fuzz, messy wavy hair, individual hair strands, faded shirt collar, dark coat, "
          + BGD + ", flat even lighting, sharp focus, photorealistic")

# ===== 全身（复用脸部同一角色块）=====
STAND_A = "standing straight, arms down at sides, hands visible"
STAND_B = "arms down at sides, hands visible"

BODY_A_FULL = ("full body shot, head to toe, front view, " + STAND_A + ", 1boy, solo, "
               "24 year old east asian man, masculine face, strong jaw, " + HAIR + ", " + MOLE + ", "
               "faded blue shirt, " + COAT + ", open coat, " + BGD)
BODY_A_NOMOLE = ("full body shot, head to toe, front view, " + STAND_A + ", 1boy, solo, "
                 "24 year old east asian man, masculine face, strong jaw, " + HAIR + ", "
                 "faded blue shirt, " + COAT + ", open coat, " + BGD)
BODY_A_LEAN = ("full body shot, head to toe, front view, " + STAND_A + ", 1boy, solo, "
               "24 year old east asian man, masculine face, " + HAIR + ", "
               "faded blue shirt, " + COAT + ", open coat, " + BGD)

BODY_B_FULL = ("1boy, wavy tousled hair, tired eyes, thick eyebrows, stubble, weathered skin, "
               "detailed skin texture, skin pores, film grain, worn wrinkled clothes, dark trousers, "
               "old worn shoes, " + STAND_B + ", " + BGD + ", even lighting, sharp focus, photorealistic")
BODY_B_LEAN = ("1boy, wavy tousled hair, tired eyes, thick eyebrows, stubble, "
               "detailed skin texture, film grain, dark trousers, old worn shoes, "
               + STAND_B + ", " + BGD + ", sharp focus, photorealistic")

N3_FULL = ("hands in pockets, hands behind back, hands hidden, holding object, prop, "
           "contrapposto, wide stance, legs apart, pockets, "
           "extra fingers, bad hands, watermark, text, blurry, lowres, busy background, "
           "grey background, dark background, gradient background, vignette, shadow, "
           "airbrushed, over-smoothed")
N3_FACE = ("dark background, grey background, gradient background, vignette, shadow, "
           "busy background, full body, bare shoulders, shirtless, freckles, mole on cheek, mole on forehead, "
           "extra fingers, bad hands, watermark, text, blurry, lowres, airbrushed, "
           "over-smoothed, beauty filter, smooth skin, retouched")

items = [("FACE_A 正面", FACE_A), ("FACE_A 侧面", FACE_A_SIDE), ("FACE_B", FACE_B),
         ("BODY_A 带痣", BODY_A_FULL), ("BODY_A 无痣", BODY_A_NOMOLE), ("BODY_A 精简", BODY_A_LEAN),
         ("BODY_B 全", BODY_B_FULL), ("BODY_B 精简", BODY_B_LEAN),
         ("N3全身", N3_FULL), ("N3脸部", N3_FACE)]
for nm, s in items:
    n = t(s)
    print("%-14s %3d/75 %s" % (nm, n, "OK" if n <= 75 else "★超 %d" % (n - 75)))
