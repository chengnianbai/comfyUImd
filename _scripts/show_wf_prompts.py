"""列出指定工作流文件里的提示词与关键参数。"""

import json
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

WF_DIR = os.path.join(r"D:\xiaobai-claude code\ComfyUI", "user", "default", "workflows")

NAMES = sys.argv[1:] or ["夜市百相簿-主工作流.json"]

for name in NAMES:
    p = os.path.join(WF_DIR, name)
    if not os.path.exists(p):
        print("MISSING:", name)
        continue
    d = json.load(open(p, encoding="utf-8"))
    print("=" * 72)
    print("FILE:", name, " nodes =", len(d.get("nodes", [])))
    for n in d["nodes"]:
        t = n.get("type")
        wv = n.get("widgets_values") or []
        if t == "CLIPTextEncode":
            print("  [%s]" % n.get("title"))
            print("      %s" % (wv[0] if wv else ""))
        elif t == "CheckpointLoaderSimple":
            print("  [%s] ckpt=%s" % (n.get("title"), wv[0] if wv else "?"))
        elif t == "EmptyLatentImage":
            print("  [%s] W=%s H=%s batch=%s" % (n.get("title"), wv[0], wv[1], wv[2] if len(wv) > 2 else "?"))
        elif t == "LatentUpscale":
            print("  [%s] %s" % (n.get("title"), wv))
        elif t == "KSampler":
            print("  [%s] seed=%s ctrl=%s steps=%s cfg=%s sampler=%s sched=%s denoise=%s"
                  % (n.get("title"), wv[0], wv[1], wv[2], wv[3], wv[4], wv[5], wv[6] if len(wv) > 6 else "?"))
    print()
