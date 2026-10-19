# -*- coding: utf-8 -*-
import copy
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from patch_wendeng_profiles import (  # noqa: E402
    FRONT_NORMALIZATION_IDS,
    FRONT_NORMALIZATION_PREFIX,
    PROFILE_IMAGE_NAME,
    patch_workflow,
    validate_workflow,
)
from wf_api import build_api, deps  # noqa: E402


WORKFLOW = os.path.join(HERE, "_wf", "夜市百相簿_主工作流.json")


class PatchWendengProfilesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WORKFLOW, encoding="utf-8") as handle:
            cls.source = json.load(handle)

    def test_patch_uses_confirmed_face_and_enables_only_two_kontext_profiles(self):
        patched = patch_workflow(copy.deepcopy(self.source))
        nodes = {node["id"]: node for node in patched["nodes"]}

        self.assertEqual(nodes[1027]["widgets_values"][0], PROFILE_IMAGE_NAME)
        self.assertEqual(nodes[1036]["widgets_values"][0], "闻灯主图-左侧脸-成品")
        self.assertEqual(nodes[1042]["widgets_values"][0], "闻灯主图-右侧脸-成品")
        self.assertEqual(nodes[1051]["type"], "ImageFlip")
        self.assertEqual(nodes[1051]["widgets_values"][0], "y-axis: horizontally")
        for node_id in list(range(1024, 1037)) + [1042, 1043, 1044, 1045, 1046, 1047, 1048, 1049, 1050, 1051, 1052]:
            self.assertEqual(nodes[node_id]["mode"], 0, node_id)
        for node_id in range(1037, 1042):
            self.assertEqual(nodes[node_id]["mode"], 2, node_id)
        for node_id in list(range(1100, 1116)) + [1127] + list(range(1300, 1339)):
            self.assertNotIn(node_id, nodes)

        profile_groups = [group for group in patched["groups"] if "00009" in group.get("title", "")]
        self.assertEqual(len(profile_groups), 1)
        self.assertIn("Kontext", profile_groups[0]["title"])
        self.assertEqual(
            profile_groups[0]["title"],
            "【闻灯】Flux 文生图 · 一体化 fp8（00009 → Kontext 左/右侧脸）",
        )
        self.assertGreaterEqual(nodes[1024]["pos"][0], profile_groups[0]["bounding"][0])

    def test_profile_branches_depend_on_reference_latent_and_confirmed_image(self):
        patched = patch_workflow(copy.deepcopy(self.source))
        api, _ = build_api(patched)

        for output_id, reference_id in (("1036", "1033"), ("1042", "1051")):
            branch = deps(api, [output_id])
            self.assertIn("1027", branch)
            self.assertIn("1028", branch)
            self.assertIn("1029", branch)
            self.assertIn(reference_id, branch)
            self.assertIn("1024", branch)
            self.assertEqual(api["1027"]["inputs"]["image"], PROFILE_IMAGE_NAME)

    def test_front_normalization_branch_is_flux_kontext_and_sides_use_its_output(self):
        patched = patch_workflow(copy.deepcopy(self.source))
        nodes = {node["id"]: node for node in patched["nodes"]}
        api, _ = build_api(patched)

        expected_types = {
            1043: "CLIPTextEncode",
            1044: "FluxGuidance",
            1045: "ReferenceLatent",
            1046: "KSampler",
            1047: "VAEDecode",
            1048: "SaveImage",
            1049: "FluxKontextImageScale",
            1050: "VAEEncode",
            1051: "ImageFlip",
            1052: "EmptySD3LatentImage",
        }
        for node_id, node_type in expected_types.items():
            self.assertEqual(nodes[node_id]["type"], node_type)
            self.assertEqual(nodes[node_id]["mode"], 0)

        self.assertEqual(nodes[1048]["widgets_values"][0], FRONT_NORMALIZATION_PREFIX)
        self.assertEqual(nodes[1046]["widgets_values"][-1], 1.0)
        self.assertEqual(nodes[1034]["widgets_values"], nodes[1046]["widgets_values"])
        self.assertIn("front-facing", nodes[1043]["widgets_values"][0])
        self.assertEqual(api["1043"]["inputs"]["clip"][0], "1025")
        for node_id in ("1030", "1031", "1037", "1043"):
            self.assertIn("clip", api[node_id]["inputs"], node_id)

        front = deps(api, [str(1048)])
        self.assertTrue(FRONT_NORMALIZATION_IDS <= front)
        self.assertIn("1027", front)
        self.assertEqual(api["1046"]["inputs"]["latent_image"][0], "1052")

        for output_id in ("1036", "1042"):
            branch = deps(api, [output_id])
            self.assertIn("1047", branch)
            self.assertIn("1049", branch)
            self.assertIn("1050", branch)
            self.assertIn("1052", branch)

        self.assertEqual(api["1033"]["inputs"]["latent"][0], "1050")
        self.assertEqual(api["1034"]["inputs"]["latent_image"][0], "1052")
        self.assertEqual(api["1051"]["inputs"]["image"][0], "1035")
        self.assertEqual(api["1042"]["inputs"]["images"][0], "1051")

    def test_patch_is_idempotent_and_valid(self):
        once = patch_workflow(copy.deepcopy(self.source))
        twice = patch_workflow(copy.deepcopy(once))
        self.assertEqual(once, twice)
        validate_workflow(twice)


if __name__ == "__main__":
    unittest.main(verbosity=2)
