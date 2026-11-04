from datetime import datetime,timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from hermes_adapter import HermesAdapter
from digest import verify


class CollectorWiringTests(unittest.TestCase):
    def test_claim_in_omitted_middle_binds_after_full_readme_fetch(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'cron').mkdir();(root/'cron/jobs.json').write_text('[]')
            adapter=HermesAdapter(root,root/'evidence',root/'history.sqlite',category='github')
            url='https://github.com/example/repo'
            row=dict(category='github',url=url,claim_excerpt='Exact claim from omitted middle.',precision='observation')
            truncated=dict(url=url,content='Truncated navigation only')
            full=dict(url=url,content='Introduction. Exact claim from omitted middle. Documentation.')
            data=dict(id=7,stargazers_count=100,full_name='example/repo',html_url=url,description='Toolkit')
            related=dict(url=url+'/issues/7',content='Original issue evidence')
            unrelated=dict(url='https://github.com/other/repo/issues/7',content='Other project')
            with patch.object(adapter,'invoke',return_value=(dict(items=[row],gaps=[],coverage_complete=True),{'page':truncated,'issue':related,'other':unrelated})), \
                 patch('hermes_adapter.fetch_public',return_value=(data,'2026-11-03T00:00:00+00:00')), \
                 patch('hermes_adapter.fetch_readme',return_value=full):
                result=adapter.collect('Frozen source context')
            self.assertEqual(result['items'][0]['claim_evidence_id'],'readme:7')
            self.assertTrue(verify(result['items'][0],result['extracts'])[0])
            self.assertIn('issue',result['items'][0]['support_evidence_ids'])
            self.assertNotIn('other',result['items'][0]['support_evidence_ids'])

    def test_full_collector_uses_ranked_paper_path_with_frozen_bounds(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/'cron').mkdir(); (root/'cron/jobs.json').write_text('[]')
            adapter=HermesAdapter(root,root/'evidence',root/'history.sqlite')
            bundle=dict(items=[],gaps=[],coverage_complete=True)
            papers=dict(items=[],extracts={},gaps=['paper sample empty'],coverage_complete=False)
            with patch.object(adapter,'invoke',return_value=(bundle,{})),patch('hermes_adapter.collect_paper',return_value=papers) as collect:
                result=adapter.collect('Coverage start: 2026-11-02T00:00:00+00:00; end: 2026-11-03T00:00:00+00:00.\n')
            self.assertEqual(collect.call_args.args[1],datetime(2026,11,2,tzinfo=timezone.utc))
            self.assertIn('paper sample empty',result['gaps'])

    def test_repository_collector_binds_receipt_and_full_readme(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/'cron').mkdir(); (root/'cron/jobs.json').write_text('[]')
            adapter=HermesAdapter(root,root/'evidence',root/'history.sqlite',category='github')
            url='https://github.com/example/repo'
            row=dict(category='github',url=url,claim_excerpt='Local retrieval for agents.',precision='observation')
            record=dict(url=url,content='Local retrieval for agents.')
            data=dict(id=7,stargazers_count=100,full_name='example/repo',html_url=url,description='Local retrieval',license=dict(spdx_id='MIT'),pushed_at='2026-11-02T00:00:00Z')
            with patch.object(adapter,'invoke',return_value=(dict(items=[row],gaps=[],coverage_complete=True),{'page':record})), \
                 patch('hermes_adapter.fetch_public',return_value=(data,'2026-11-03T00:00:00+00:00')), \
                 patch('hermes_adapter.fetch_readme',return_value=record):
                result=adapter.collect('Frozen source context')
            self.assertTrue(verify(result['items'][0],result['extracts'])[0])
            self.assertEqual(result['items'][0]['support_evidence_ids'],['readme:7'])
            self.assertNotIn('changelog',result['items'][0]['documentation'])
