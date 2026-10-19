# -*- coding: utf-8 -*-
"""比对 _server_now.json（推送基线）与 _server_live.json（刚拉的服务器现版）是否逐节点一致"""
import os, json, io

HERE = os.path.dirname(os.path.abspath(__file__))
W = os.path.join(HERE, "_wf")


def load(p):
    d = json.load(io.open(p, encoding="utf-8"))
    if isinstance(d, dict) and "workflow" in d and "nodes" not in d:
        d = d["workflow"]
    return d


a = load(os.path.join(W, "_server_now.json"))    # 推送基线
b = load(os.path.join(W, "_server_live.json"))   # 服务器现版

print("基线 _server_now : %d 节点 / %d 链接 / %d 组"
      % (len(a["nodes"]), len(a.get("links", [])), len(a.get("groups", []))))
print("现版 _server_live: %d 节点 / %d 链接 / %d 组"
      % (len(b["nodes"]), len(b.get("links", [])), len(b.get("groups", []))))

ia = {n["id"]: n for n in a["nodes"]}
ib = {n["id"]: n for n in b["nodes"]}
only_a = sorted(set(ia) - set(ib))
only_b = sorted(set(ib) - set(ia))
print("\n只在基线:", only_a)
print("只在现版:", only_b)

diff = []
for i in sorted(set(ia) & set(ib)):
    if json.dumps(ia[i], sort_keys=True, ensure_ascii=False) != json.dumps(ib[i], sort_keys=True, ensure_ascii=False):
        diff.append(i)
print("内容不同的节点:", len(diff), diff[:30])

def lk(d):
    return sorted(tuple(l[:6]) for l in d.get("links", []))
la, lb = lk(a), lk(b)
print("链接集合一致:", la == lb)
if la != lb:
    print("  只在基线:", [x for x in la if x not in lb][:20])
    print("  只在现版:", [x for x in lb if x not in la][:20])

print("\n判定:", "✔ 完全一致，可安全以基线推送" if (not only_a and not only_b and not diff and la == lb) else "★ 有差异，必须先刷新基线")
