# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"D:\xiaobai-claude code\ComfyUI\venv\Lib\site-packages")
from transformers import CLIPTokenizer
tk = CLIPTokenizer.from_pretrained(r"D:\xiaobai-claude code\ComfyUI\comfy\sd1_tokenizer")
def t(s): return len(tk.encode(s, add_special_tokens=False))

BGD = "pure white background"

BB1 = ("1boy, male, lean wiry build, broad shoulders, tired eyes, thick eyebrows, "
       "stubble, weathered skin, detailed skin texture, skin pores, film grain, "
       "worn wrinkled clothes, open coat, dark trousers, old worn shoes, "
       + BGD + ", even lighting, sharp focus, photorealistic")
BB3 = ("1boy, lean wiry build, broad shoulders, tired eyes, thick eyebrows, stubble, "
       "detailed skin texture, film grain, open coat, dark trousers, old worn shoes, "
       + BGD + ", sharp focus, photorealistic")
BB4 = ("1boy, lean wiry build, broad shoulders, tired eyes, stubble, film grain, "
       "worn clothes, open coat, dark trousers, old worn shoes, " + BGD + ", "
       "sharp focus, photorealistic")

POSE_B  = "standing straight, arms down at sides, hands visible"
POSE_B2 = "arms down at sides, hands visible"

for nm, pose in [("长", POSE_B), ("短", POSE_B2)]:
    for bn, bb in [("BB1", BB1), ("BB3", BB3), ("BB4", BB4)]:
        for view in ["front view", "side view", "back view"]:
            s = view + ", " + pose + ", " + bb
            n = t(s)
            print("%s %-4s %-11s %3d/75 %s" % (nm, bn, view, n, "OK" if n <= 75 else "超 %d" % (n-75)))
    print()
