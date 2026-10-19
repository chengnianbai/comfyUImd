# -*- coding: utf-8 -*-
"""Back up, patch, deploy and read back the Wendeng profile workflow."""
import json
import os
import ssl
import time
import urllib.parse
import urllib.request
import uuid

from patch_wendeng_profiles import PROFILE_IMAGE_NAME, patch_workflow, validate_workflow


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORKFLOW_NAME = "夜市百相簿-主工作流.json"
LOCAL_WORKFLOW = os.path.join(HERE, "_wf", "夜市百相簿_主工作流.json")
SOURCE_IMAGE = os.path.join(
    ROOT,
    "系列-夜市百相簿",
    "02-角色",
    "闻灯",
    "设定图",
    "闻灯正脸确定",
    "闻灯-脸部正面-成品_00009_.png",
)
BASE = os.environ.get(
    "COMFY_BASE",
    "https://gw-efb56d453d484597a1b8ddfc86156262.cn-beijing.aigclinks.com:8016",
).rstrip("/")
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE


def workflow_path(name):
    return "/api/userdata/workflows%2F" + urllib.parse.quote(name) + "?overwrite=true"


def build_multipart(image_bytes, filename, boundary=None):
    boundary = boundary or ("----codex" + uuid.uuid4().hex)
    chunks = []
    for key, value in (("overwrite", "true"), ("type", "input"), ("subfolder", "")):
        chunks.append(
            ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
             % (boundary, key, value)).encode("utf-8")
        )
    chunks.append(
        ("--%s\r\nContent-Disposition: form-data; name=\"image\"; filename=\"%s\"\r\n"
         "Content-Type: image/png\r\n\r\n" % (boundary, filename)).encode("utf-8")
    )
    chunks.append(image_bytes)
    chunks.append(("\r\n--%s--\r\n" % boundary).encode("utf-8"))
    return b"".join(chunks), "multipart/form-data; boundary=%s" % boundary


def validate_remote_workflow(workflow):
    validate_workflow(workflow)
    nodes = {node["id"]: node for node in workflow["nodes"]}
    if nodes[1046]["widgets_values"][-1] != 1.0:
        raise ValueError("normalized front denoise must be 1.0")
    if nodes[1044]["widgets_values"][0] != 3:
        raise ValueError("normalized front guidance must be 3.0")
    if nodes[1034]["widgets_values"][-1] != 1:
        raise ValueError("Kontext profile denoise must be 1.0")
    if nodes[1032]["widgets_values"][0] != 3:
        raise ValueError("Kontext profile guidance must be 3.0")
    if nodes[1051]["type"] != "ImageFlip" or nodes[1051]["widgets_values"][0] != "y-axis: horizontally":
        raise ValueError("opposite profile must use a horizontal ImageFlip")
    if any(nodes[node_id].get("mode") != 2 for node_id in range(1037, 1042)):
        raise ValueError("the ambiguous second Kontext profile branch must stay disabled")
    return True


def request(path, data=None, content_type=None, timeout=300, method=None):
    headers = {}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    return urllib.request.urlopen(req, timeout=timeout, context=SSL_CONTEXT).read()


def main():
    if not os.path.isfile(SOURCE_IMAGE):
        raise SystemExit("missing source image: %s" % SOURCE_IMAGE)

    print("1/5 Check remote instance")
    stats = json.loads(request("/system_stats", timeout=60).decode("utf-8", "replace"))
    print("    ComfyUI %s" % stats.get("system", {}).get("comfyui_version", "unknown"))

    get_path = workflow_path(WORKFLOW_NAME).split("?", 1)[0]
    print("2/5 Fetch and back up current workflow")
    remote_bytes = request(get_path, timeout=120)
    remote = json.loads(remote_bytes.decode("utf-8", "replace"))
    backup = os.path.join(HERE, "_wf", "_backup_wendeng_profiles_%s.json" % time.strftime("%m%d-%H%M%S"))
    with open(backup, "wb") as handle:
        handle.write(remote_bytes)
    print("    backup: %s" % backup)

    patched = patch_workflow(remote)
    patched["id"] = str(uuid.uuid4())
    validate_remote_workflow(patched)

    print("3/5 Upload confirmed face (%0.2f MB)" % (os.path.getsize(SOURCE_IMAGE) / 1048576))
    with open(SOURCE_IMAGE, "rb") as handle:
        body, content_type = build_multipart(handle.read(), PROFILE_IMAGE_NAME)
    upload_result = request("/upload/image", body, content_type, timeout=600)
    print("    upload: %s" % upload_result.decode("utf-8", "replace")[:200])
    inputs = json.loads(request("/internal/files/input", timeout=120).decode("utf-8", "replace"))
    names = [(item.get("name") if isinstance(item, dict) else str(item)).split(" [", 1)[0]
             for item in inputs]
    if PROFILE_IMAGE_NAME not in names:
        raise RuntimeError("uploaded image is not visible in remote input directory")

    print("4/5 Push patched master workflow")
    payload = json.dumps(patched, ensure_ascii=False).encode("utf-8")
    push_result = request(workflow_path(WORKFLOW_NAME), payload, "application/json", timeout=600, method="POST")
    print("    push: %s" % push_result.decode("utf-8", "replace")[:200])

    print("5/5 Read back and verify")
    deployed = json.loads(request(get_path, timeout=120).decode("utf-8", "replace"))
    validate_remote_workflow(deployed)
    with open(LOCAL_WORKFLOW, "w", encoding="utf-8") as handle:
        json.dump(deployed, handle, ensure_ascii=False, indent=1)
    print("    workflow id: %s" % deployed.get("id"))
    print("    nodes=%d links=%d" % (len(deployed["nodes"]), len(deployed["links"])))
    print("OK: deployed confirmed-face Kontext profile workflow")


if __name__ == "__main__":
    main()
