"""精确统计 SD 1.5 提示词的 CLIP token 数。

SD 1.5 的 CLIP 上限是 77 个 token（含开头的 BOS 和结尾的 EOS），
所以真正能用来写提示词的只有 75 个。超出部分会被 ComfyUI 直接截断，
而且是静默截断 —— 你根本不知道后半段被扔了。
"""

import os
import sys

TOK_DIR = r"D:\xiaobai-claude code\ComfyUI\comfy\sd1_tokenizer"
sys.path.insert(0, r"D:\xiaobai-claude code\ComfyUI\venv\Lib\site-packages")

from transformers import CLIPTokenizer  # noqa: E402

tk = CLIPTokenizer.from_pretrained(TOK_DIR)
LIMIT = 75


def report(name, text):
    ids = tk.encode(text, add_special_tokens=False)
    n = len(ids)
    flag = "OK " if n <= LIMIT else "超限"
    print("[%s] %-14s %3d / %d token   剩余 %d" % (flag, name, n, LIMIT, LIMIT - n))
    if n > LIMIT:
        kept = tk.decode(ids[:LIMIT])
        dropped = tk.decode(ids[LIMIT:])
        print("        会被保留到：...%s" % kept[-60:])
        print("        会被截断掉：%s" % dropped[:200])
    return n


if __name__ == "__main__":
    import json
    data = json.load(open(sys.argv[1], encoding="utf-8"))
    for k, v in data.items():
        report(k, v)
