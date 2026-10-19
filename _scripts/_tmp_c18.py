# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"D:\xiaobai-claude code\ComfyUI\venv\Lib\site-packages")
from transformers import CLIPTokenizer
tk = CLIPTokenizer.from_pretrained(r"D:\xiaobai-claude code\ComfyUI\comfy\sd1_tokenizer")
def t(s): return len(tk.encode(s, add_special_tokens=False))

BGD = "pure white background"

BODY_B_V1 = ("1boy, male, lean wiry build, broad shoulders, tired eyes, thick eyebrows, "
             "stubble, weathered skin, detailed skin texture, skin pores, film grain, "
             "worn wrinkled clothes, open coat, dark trousers, old worn shoes, "
             + BGD + ", even lighting, sharp focus, photorealistic")

BODY_B_V2 = ("1boy, lean wiry build, broad shoulders, tired eyes, thick eyebrows, stubble, "
             "film grain, open coat, dark trousers, old worn shoes, " + BGD + ", "
             "sharp focus, photorealistic")

BODY_B_V3 = ("1boy, lean wiry build, broad shoulders, tired eyes, thick eyebrows, stubble, "
             "detailed skin texture, film grain, open coat, dark trousers, old worn shoes, "
             + BGD + ", sharp focus, photorealistic")

BODY_B_V4 = ("1boy, lean wiry build, broad shoulders, tired eyes, stubble, film grain, "
             "worn clothes, open coat, dark trousers, old worn shoes, " + BGD + ", "
             "sharp focus, photorealistic")

N3_V1 = ("close-up, cropped, hands in pockets, hands behind back, hands hidden, "
         "hand tucked in pocket, hands on hips, arms crossed, holding object, holding book, "
         "holding paper, prop, contrapposto, wide stance, legs apart, pockets, hand in pocket, "
         "extra fingers, bad hands, watermark, text, blurry, lowres, busy background, "
         "grey background, dark background, gradient background, vignette, shadow, "
         "airbrushed, over-smoothed")

N3_V2 = ("hands in pockets, hands behind back, hands hidden, hands tucked, hands on hips, "
         "arms crossed, holding object, prop, contrapposto, wide stance, legs apart, pockets, "
         "extra fingers, bad hands, watermark, text, blurry, lowres, busy background, "
         "grey background, dark background, gradient background, vignette, shadow, "
         "airbrushed, over-smoothed")

N3_V3 = ("hands in pockets, hands behind back, hands hidden, holding object, prop, "
         "contrapposto, wide stance, legs apart, pockets, "
         "extra fingers, bad hands, watermark, text, blurry, lowres, busy background, "
         "grey background, dark background, gradient background, vignette, shadow, "
         "airbrushed, over-smoothed")

for nm, s in [("BODY_B_V1", BODY_B_V1), ("BODY_B_V2", BODY_B_V2), ("BODY_B_V3", BODY_B_V3),
              ("BODY_B_V4", BODY_B_V4), ("N3_V1", N3_V1), ("N3_V2", N3_V2), ("N3_V3", N3_V3)]:
    n = t(s)
    print("%-10s %3d/75 %s" % (nm, n, "OK" if n <= 75 else "超 %d" % (n - 75)))
