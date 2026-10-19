# -*- coding: utf-8 -*-
"""Side-profile A/B experiments: single-point edits on the LIVE workflow.

Does NOT use patch_workflow (that would reset everything). Reads the remote
workflow, changes exactly one thing, pushes back, verifies by re-fetching.

Usage:
  python _exp_side_ab.py guidance 2.5      # node 1032 FluxGuidance value
  python _exp_side_ab.py anchor 1029       # 1033.latent <- 1029 (00009 ref)
  python _exp_side_ab.py anchor 1050       # 1033.latent <- 1050 (front output, original)
"""
import json
import sys
import uuid

from deploy_wendeng_profiles import request, workflow_path, WORKFLOW_NAME

GET = workflow_path(WORKFLOW_NAME).split("?", 1)[0]
NODE_GUIDANCE_LEFT = 1032
NODE_REF_LEFT = 1033
NODE_VAEENC_REF = 1029    # 00009 reference latent
NODE_VAEENC_FRONT = 1050  # unified front-face latent


def fetch():
    return json.loads(request(GET, timeout=120).decode("utf-8", "replace"))


def push(d):
    d["id"] = str(uuid.uuid4())
    request(workflow_path(WORKFLOW_NAME), json.dumps(d, ensure_ascii=False).encode("utf-8"),
            "application/json", timeout=600, method="POST")


def out_slot(nodes, nid, type_name):
    for i, o in enumerate(nodes[nid].get("outputs", [])):
        if o.get("type") == type_name or o.get("name") == type_name:
            return i
    raise SystemExit("no %s output on node %d" % (type_name, nid))


def in_index(nodes, nid, name):
    for i, inp in enumerate(nodes[nid].get("inputs", [])):
        if inp.get("name") == name:
            return i
    raise SystemExit("no %s input on node %d" % (name, nid))


def set_guidance(value):
    d = fetch()
    nodes = {n["id"]: n for n in d["nodes"]}
    nodes[NODE_GUIDANCE_LEFT]["widgets_values"] = [value]
    push(d)
    back = fetch()
    n = {x["id"]: x for x in back["nodes"]}[NODE_GUIDANCE_LEFT]
    assert n["widgets_values"] == [value], "guidance readback mismatch: %r" % n["widgets_values"]
    print("OK guidance(%d) = %s  (readback verified)" % (NODE_GUIDANCE_LEFT, value))


def set_anchor(src_nid):
    assert src_nid in (NODE_VAEENC_REF, NODE_VAEENC_FRONT)
    d = fetch()
    nodes = {n["id"]: n for n in d["nodes"]}
    ref = nodes[NODE_REF_LEFT]
    idx = in_index(nodes, NODE_REF_LEFT, "latent")
    old_link_id = ref["inputs"][idx].get("link")
    # remove old link object + stale references on its source node outputs
    if old_link_id is not None:
        old = [l for l in d["links"] if l[0] == old_link_id]
        if old:
            o = old[0]
            src_node = nodes[o[1]]
            sl = src_node["outputs"][o[2]].get("links") or []
            if old_link_id in sl:
                sl.remove(old_link_id)
            d["links"] = [l for l in d["links"] if l[0] != old_link_id]
    # create new link src -> 1033.latent
    new_id = max(l[0] for l in d["links"]) + 1
    slot = out_slot(nodes, src_nid, "LATENT")
    d["links"].append([new_id, src_nid, slot, NODE_REF_LEFT, idx, "LATENT"])
    ref["inputs"][idx]["link"] = new_id
    ol = nodes[src_nid]["outputs"][slot].setdefault("links", [])
    if new_id not in ol:
        ol.append(new_id)
    push(d)
    # verify
    back = fetch()
    bn = {x["id"]: x for x in back["nodes"]}
    links = {l[0]: l for l in back["links"]}
    lk = bn[NODE_REF_LEFT]["inputs"][idx]["link"]
    assert lk is not None and links[lk][1] == src_nid, "anchor readback mismatch"
    print("OK anchor: 1033.latent <- %d (%s)  (readback verified)"
          % (src_nid, "00009 ref" if src_nid == NODE_VAEENC_REF else "front output"))


if __name__ == "__main__":
    cmd, arg = sys.argv[1], sys.argv[2]
    if cmd == "guidance":
        set_guidance(float(arg) if "." in arg else int(arg))
    elif cmd == "anchor":
        set_anchor(int(arg))
    else:
        raise SystemExit("unknown cmd: " + cmd)
