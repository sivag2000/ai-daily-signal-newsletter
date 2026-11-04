import tempfile
from pathlib import Path
import unittest
from delivery_bridge import send_once


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

    def test_replay_returns_receipt_without_send(self):
        calls = []
        def send(payload):
            calls.append(payload)
            return 'receipt'
        self.assertEqual(send_once(self.folder,'day','payload',send), 'receipt')
        self.assertEqual(send_once(self.folder,'day','payload',send), 'receipt')
        self.assertEqual(calls, ['payload'])

    def test_changed_payload_cannot_reuse_occurrence(self):
        send_once(self.folder,'day','payload',lambda p:'receipt')
        with self.assertRaises(ValueError):
            send_once(self.folder,'day','changed',lambda p:'receipt')

    def test_interrupted_send_cannot_replay(self):
        def fail(payload):
            raise RuntimeError('ambiguous')
        with self.assertRaises(RuntimeError):
            send_once(self.folder,'day','payload',fail)
        with self.assertRaisesRegex(RuntimeError, 'reconcile'):
            send_once(self.folder,'day','payload',lambda p:'receipt')

    def test_nested_invocation_cannot_send_twice(self):
        def send(payload):
            with self.assertRaises(OSError):
                send_once(self.folder,'day','payload',lambda p:'wrong')
            return 'receipt'
        send_once(self.folder,'day','payload',send)


if __name__ == '__main__':
    unittest.main()
