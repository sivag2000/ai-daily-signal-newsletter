from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import end_to_end_preview as preview


class PreviewBoundaryTests(unittest.TestCase):
    def run_fixture(self,attempt_send=False):
        class FakeAdapter:
            def __init__(self,home,evidence,history):evidence.mkdir(parents=True)
            def collect(self,prompt):
                if attempt_send:
                    from brief_delivery import deliver
                    deliver('forbidden')
                return dict(items=[],extracts={},gaps=['Fixture preview'],coverage_complete=False)
            def review(self,rows,stage):return []
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);home=root/'profile'
            (home/'scripts').mkdir(parents=True);(home/'cron').mkdir()
            for name in ('brief_service.py','brief_delivery.py','brief_prompts.py','sequential_brief.py'):
                (home/'scripts'/name).write_text('Fixture')
            (home/'config.yaml').write_text('fixture: true')
            (home/'cron/jobs.json').write_text('[]')
            with patch.object(preview,'HOME',home),patch.object(preview,'ROOT',root/'preview'), \
                 patch.object(preview,'ProgressAdapter',FakeAdapter),redirect_stdout(io.StringIO()):
                preview.main()
                return json.loads((preview.ROOT/'summary.json').read_text())

    def test_preview_does_not_acknowledge_delivery_or_advance_coverage(self):
        result=self.run_fixture()
        self.assertEqual(result['delivery'],'preview')
        self.assertEqual(result['safety']['delivery_guard_calls'],0)
        self.assertTrue(result['safety']['accepted_history_unchanged'])
        self.assertIsNone(result['safety']['coverage_checkpoint'])
        self.assertFalse(result['safety']['active_file_changes'])

    def test_accidental_parent_delivery_call_is_blocked(self):
        with self.assertRaisesRegex(AssertionError,'may not send'):
            self.run_fixture(attempt_send=True)
