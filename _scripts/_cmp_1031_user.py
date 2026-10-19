# -*- coding: utf-8 -*-
"""本地零成本核对：用户 17:16 补全版 vs 17:10 线上快照的 1031（截断版）"""
import os, io, json, difflib

HERE = os.path.dirname(os.path.abspath(__file__))
snap = os.path.join(HERE, "_wf", "_server_now.json")
newf = os.path.join(HERE, "_wf", "user_prompt_1031_20260922_1716.txt")

d = json.load(io.open(snap, encoding="utf-8"))
if "workflow" in d and "nodes" not in d:
    d = d["workflow"]
ns = {n["id"]: n for n in d.get("nodes", [])}
old = ns[1031]["widgets_values"][0]
new = io.open(newf, encoding="utf-8").read().rstrip("\n")

print("旧（17:10 线上快照 1031）: %d 字符" % len(old))
print("新（用户 17:16 补全版）  : %d 字符" % len(new))
print("差值: %+d 字符" % (len(new) - len(old)))

# 公共前缀
i = 0
while i < min(len(old), len(new)) and old[i] == new[i]:
    i += 1
print("\n公共前缀长度 = %d 字符" % i)
print("旧文在分叉处结束于: ...%r" % old[max(0, i - 90):i])
print("新文在分叉处继续于: %r..." % new[i:i + 120])

# 旧文是否为完整前缀
print("\n旧文是新文的【逐字节前缀】吗:", old.rstrip("\n") == new[:len(old.rstrip('\n'))])

sm = difflib.SequenceMatcher(None, old, new, autojunk=False)
print("相似度 = %.4f" % sm.ratio())
print("\n差异块（old→new）:")
for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag == "equal":
        continue
    print("  [%s] old[%d:%d]=%r" % (tag, i1, i2, (old[i1:i2][:70] or "")))
    print("        new[%d:%d]=%r" % (j1, j2, (new[j1:j2][:70] or "")))
