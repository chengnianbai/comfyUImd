"""Offline regressions for incremental workflow inspection; no ComfyUI requests."""
import copy
import json
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import diff_wf as tool


def workflow():
    return {"version": 0.4, "nodes": [
        {"id": 1, "type": "Source", "widgets_values": [5],
         "outputs": [{"name": "image", "type": "IMAGE", "links": [10]}]},
        {"id": 2, "type": "Source", "widgets_values": [5],
         "outputs": [{"name": "image", "type": "IMAGE", "links": []}]},
        {"id": 3, "type": "SaveImage", "inputs": [
            {"name": "images", "type": "IMAGE", "link": 10}]}],
        "links": [[10, 1, 0, 3, 0, "IMAGE"]]}


class IncrementalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.old = self.write("old.json", workflow())
        self.new = self.write("new.json", workflow())
        self.state = self.root / "state.json"

    def write(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_parameter_delta_has_exact_values_and_neighbors(self):
        w = workflow(); w["nodes"][0]["widgets_values"][0] = 8
        self.write("new.json", w)
        r = tool.compare_files(self.old, self.new)
        self.assertEqual(len(r["changes"]), 1)
        self.assertEqual(r["changes"][0]["path"], "/nodes/1/widgets_values/0")
        self.assertEqual((r["changes"][0]["old"], r["changes"][0]["new"]), (5, 8))
        self.assertIn('3', r["context"]["new"])

    def test_same_link_id_rewire_is_detected(self):
        w = workflow(); w["links"][0][1] = 2
        w["nodes"][0]["outputs"][0]["links"] = []
        w["nodes"][1]["outputs"][0]["links"] = [10]
        self.write("new.json", w)
        r = tool.compare_files(self.old, self.new)
        self.assertTrue(any(c["path"].startswith("/links/10") for c in r["changes"]))
        self.assertIn("structure", r["review_reasons"])

    def test_reordered_nodes_do_not_create_false_delta(self):
        w = workflow(); w["nodes"].reverse()
        self.write("new.json", w)
        self.assertEqual(tool.compare_files(self.old, self.new)["changes"], [])

    def test_dangling_link_and_duplicate_id_rejected(self):
        for kind in ("dangling", "duplicate", "backlink", "bad_slot"):
            with self.subTest(kind=kind):
                w = workflow()
                if kind == "dangling": w["links"][0][1] = 99
                if kind == "duplicate": w["nodes"][1]["id"] = 1
                if kind == "backlink": w["nodes"][2]["inputs"][0]["link"] = 999
                if kind == "bad_slot": w["links"][0][2] = -1
                self.write("new.json", w)
                with self.assertRaises(ValueError): tool.compare_files(self.old, self.new)

    def test_unsupported_format_does_not_claim_equal(self):
        self.write("new.json", {"1": {"class_type": "SaveImage", "inputs": {}}})
        with self.assertRaises(ValueError): tool.compare_files(self.new, self.new)

    def test_equal_hash_skips_parse_only_with_validated_state(self):
        tool.init_state(self.old, self.state)
        with patch.object(tool, "read_workflow", side_effect=AssertionError("parsed")):
            r = tool.compare_state(self.state, self.new)
        self.assertTrue(r["parse_skipped"])

    def test_tampered_baseline_fails_even_if_current_matches_it(self):
        state = tool.init_state(self.old, self.state)
        w = workflow(); w["nodes"][0]["widgets_values"] = [999]
        Path(state['baseline_path']).write_text(json.dumps(w), encoding='utf-8')
        self.write("new.json", w)
        with self.assertRaises(ValueError): tool.compare_state(self.state, self.new)

    def test_advance_requires_exact_reviewed_hash_and_archives_delta(self):
        tool.init_state(self.old, self.state)
        w = workflow(); w["nodes"][0]["widgets_values"] = [8]
        self.write("new.json", w)
        report = tool.compare_state(self.state, self.new)
        before = self.state.read_bytes()
        with self.assertRaises(ValueError):
            tool.advance_state(self.state, self.new, report, "stale", self.root / "snap")
        self.assertEqual(self.state.read_bytes(), before)
        tool.advance_state(self.state, self.new, report, report["new_sha256"], self.root / "snap")
        self.assertTrue(tool.compare_state(self.state, self.new)["parse_skipped"])
        self.assertTrue(list((self.root / "snap").glob("*.delta.json")))
        self.assertEqual(json.loads(self.old.read_text()), workflow())

    def test_long_values_remain_in_record_but_not_console(self):
        w = workflow(); w["nodes"][0]["widgets_values"] = ["x" * 20000]
        self.write("new.json", w)
        r = tool.compare_files(self.old, self.new)
        self.assertEqual(len(r["changes"][0]["new"]), 20000)
        self.assertLess(len(tool.render_report(r)), 5000)

    def test_metadata_changes_are_not_silently_ignored(self):
        w = workflow(); w["extra"] = {"unknown_dependency": "new"}
        self.write("new.json", w)
        r = tool.compare_files(self.old, self.new)
        self.assertTrue(any(c["path"].startswith("/metadata/extra") for c in r["changes"]))
        self.assertTrue(r["review_reasons"])

    def test_baseline_survives_source_edits_and_advance(self):
        s = tool.init_state(self.old, self.state)
        self.assertNotEqual(Path(s['baseline_path']), self.old)
        w = workflow(); w['nodes'][0]['widgets_values'] = [8]
        self.write('old.json', w)
        r = tool.compare_state(self.state, self.old)
        tool.advance_state(self.state, self.old, r, r['new_sha256'], self.root / 'archive')
        w['nodes'][0]['widgets_values'] = [9]; self.write('old.json', w)
        self.assertEqual(tool.compare_state(self.state, self.old)['changes'][0]['old'], 8)

    def test_input_metadata_and_null_field_additions_are_reported(self):
        w = workflow(); w['nodes'][2]['inputs'][0]['name'] = 'renamed'
        w['nodes'][0]['extra_field'] = None
        self.write('new.json', w)
        paths = [c['path'] for c in tool.compare_files(self.old, self.new)['changes']]
        self.assertIn('/nodes/3/inputs/0/name', paths)
        self.assertIn('/nodes/1/extra_field', paths)

    def test_missing_reverse_link_is_rejected(self):
        w = workflow(); w['nodes'][2]['inputs'][0]['link'] = None
        self.write('new.json', w)
        with self.assertRaises(ValueError): tool.compare_files(self.old, self.new)

    def test_many_changes_have_bounded_console_and_full_local_report(self):
        w = workflow(); w['nodes'][0]['widgets_values'] = ['X' * 5000] * 100
        self.write('new.json', w)
        report = self.root / 'report.json'; usage = self.root / 'usage.jsonl'
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = tool.main([str(self.old), str(self.new), '--report', str(report),
                                '--usage-log', str(usage), '--max-chars', '1200'])
        self.assertEqual(result, 0)
        self.assertLessEqual(len(output.getvalue()), 1200)
        self.assertEqual(len(json.loads(report.read_text())['changes']), 100)
        metrics = json.loads(usage.read_text())
        self.assertIsNone(metrics['input_tokens'])
        self.assertEqual(metrics['console_chars'], len(output.getvalue()))
        self.assertGreater(metrics['local_read_bytes'], 0)

    def test_existing_state_is_not_overwritten_by_init(self):
        tool.init_state(self.old, self.state); before = self.state.read_bytes()
        with self.assertRaises(ValueError): tool.init_state(self.new, self.state)
        self.assertEqual(before, self.state.read_bytes())

    def test_expanded_review_cannot_advance_without_ack(self):
        tool.init_state(self.old, self.state)
        w = workflow(); w['nodes'][0]['type'] = 'Other'
        self.write('new.json', w); r = tool.compare_state(self.state, self.new)
        with self.assertRaises(ValueError):
            tool.advance_state(self.state, self.new, r, r['new_sha256'], self.root / 'archive')

    def test_report_cannot_overwrite_workflow(self):
        before = self.old.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()):
            rc = tool.main([str(self.old), str(self.new), '--report', str(self.old)])
        self.assertNotEqual(rc, 0)
        self.assertEqual(before, self.old.read_bytes())

    def test_validation_failure_is_measured_without_advancing(self):
        w = workflow(); w['nodes'][0]['outputs'][0]['links'].append(999)
        self.write('new.json', w); usage = self.root/'usage.jsonl'
        with contextlib.redirect_stderr(io.StringIO()):
            rc = tool.main(['--init-state', str(self.new), '--state', str(self.state), '--usage-log', str(usage)])
        self.assertEqual(rc, 1)
        self.assertFalse(self.state.exists())
        self.assertEqual(json.loads(usage.read_text())['status'], 'error')

    def test_failed_validation_does_not_advance_existing_state(self):
        tool.init_state(self.old, self.state); before = self.state.read_bytes()
        w = workflow(); w['nodes'][0]['widgets_values'] = [8]; self.write('new.json', w)
        report = tool.compare_state(self.state, self.new)
        w['links'][0][1] = 99; self.write('new.json', w)
        with self.assertRaises(ValueError):
            tool.advance_state(self.state, self.new, report, report['new_sha256'], self.root/'archive')
        self.assertEqual(before, self.state.read_bytes())


if __name__ == "__main__":
    unittest.main()
