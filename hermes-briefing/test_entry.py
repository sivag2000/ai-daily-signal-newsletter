import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import activation_entry
from test_digest import NOW,article
from digest import identity


class EntryTests(unittest.TestCase):
    def test_assembled_entry_uses_fake_adapter_and_sender_once(self):
        row=article()
        class Adapter:
            instances=0
            def __init__(self,*args):
                Adapter.instances+=1
            def collect(self,prompt):
                return dict(items=[row],extracts={'extract-1':dict(url=row['url'],
                    content=row['publication_excerpt']+' '+row['claim_excerpt'])},gaps=[],coverage_complete=True)
            def review(self,rows,stage):
                return [identity(x) for x in rows]
        sends=[]
        def fake_transport(home,key):
            def send(payload):
                sends.append(payload)
                return 'fake-receipt'
            return send
        with tempfile.TemporaryDirectory() as temp, patch.object(activation_entry,'HermesAdapter',Adapter), \
             patch.object(activation_entry,'legacy_transport',fake_transport):
            root=Path(temp)
            first=activation_entry.execute(root/'profile',root/'state',NOW)
            second=activation_entry.execute(root/'profile',root/'state',NOW)
            self.assertEqual(first['status'],'accepted')
            self.assertEqual(second['status'],'accepted')
            self.assertEqual(Adapter.instances,1)
            self.assertEqual(len(sends),1)
