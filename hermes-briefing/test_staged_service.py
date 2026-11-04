from pathlib import Path
import unittest
from unittest.mock import patch
from test_pipeline import PipelineTests
from staged_service import run_daily
from digest import identity, Store


class ServiceTests(unittest.TestCase):
    setUp = PipelineTests.setUp
    def daily(self, transport, collector=None):
        approve = lambda rows:[identity(row) for row in rows]
        return run_daily(Path(self.tmp.name)/'service', NOW, 'day', collector or (lambda p:self.bundle),
                         approve, approve, transport)

    def test_full_service_replay(self):
        calls=[]
        def send(payload):
            calls.append(payload)
            return 'fake-receipt'
        self.daily(send)
        self.daily(send, collector=lambda p:self.fail('Unexpected research replay'))
        self.assertEqual(len(calls),1)

    def test_accepted_send_history_crash_recovers_without_resend(self):
        calls=[]
        def send(payload):
            calls.append(payload)
            return 'fake-receipt'
        with patch.object(Store,'accept',side_effect=RuntimeError('Crash before history commit')):
            with self.assertRaises(RuntimeError):
                self.daily(send)
        self.daily(send,collector=lambda p:self.fail('Unexpected research replay'))
        self.assertEqual(len(calls),1)

    def test_full_service_nested_call_cannot_research_or_send(self):
        def send(payload):
            with self.assertRaises(OSError):
                self.daily(lambda p:'wrong')
            return 'fake-receipt'
        self.daily(send)


from test_digest import NOW
