# -*- coding: utf-8 -*-
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from deploy_wendeng_profiles import (  # noqa: E402
    build_multipart,
    validate_remote_workflow,
    workflow_path,
)
from patch_wendeng_profiles import patch_workflow  # noqa: E402


WORKFLOW = os.path.join(HERE, "_wf", "夜市百相簿_主工作流.json")


class DeployWendengProfilesTest(unittest.TestCase):
    def test_workflow_path_encodes_chinese_name_and_slash(self):
        path = workflow_path("夜市百相簿-主工作流.json")
        self.assertTrue(path.startswith("/api/userdata/workflows%2F"))
        self.assertIn("%E5%A4%9C", path)
        self.assertTrue(path.endswith("?overwrite=true"))

    def test_multipart_contains_filename_payload_and_upload_flags(self):
        body, content_type = build_multipart(b"PNGDATA", "wendeng_face_confirmed_00009.png", "BOUNDARY")
        self.assertEqual(content_type, "multipart/form-data; boundary=BOUNDARY")
        self.assertIn(b'filename="wendeng_face_confirmed_00009.png"', body)
        self.assertIn(b'name="overwrite"\r\n\r\ntrue', body)
        self.assertIn(b'name="type"\r\n\r\ninput', body)
        self.assertIn(b"PNGDATA", body)
        self.assertTrue(body.endswith(b"--BOUNDARY--\r\n"))

    def test_remote_validation_accepts_patched_workflow(self):
        with open(WORKFLOW, encoding="utf-8") as handle:
            workflow = json.load(handle)
        validate_remote_workflow(patch_workflow(workflow))

    def test_remote_validation_rejects_ambiguous_second_profile_sampler(self):
        with open(WORKFLOW, encoding="utf-8") as handle:
            workflow = patch_workflow(json.load(handle))
        nodes = {node["id"]: node for node in workflow["nodes"]}
        nodes[1040]["mode"] = 0
        with self.assertRaisesRegex(ValueError, "ambiguous second Kontext profile"):
            validate_remote_workflow(workflow)

    def test_remote_validation_rejects_non_horizontal_flip(self):
        with open(WORKFLOW, encoding="utf-8") as handle:
            workflow = patch_workflow(json.load(handle))
        nodes = {node["id"]: node for node in workflow["nodes"]}
        nodes[1051]["widgets_values"] = ["x-axis: vertically"]
        with self.assertRaisesRegex(ValueError, "horizontal ImageFlip"):
            validate_remote_workflow(workflow)


if __name__ == "__main__":
    unittest.main(verbosity=2)
