from datetime import datetime,timezone,timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from paper_feed import collect_paper
from digest import verify

XML=b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
<id>http://arxiv.org/abs/2611.00001v1</id><published>2026-11-03T00:00:00Z</published>
<title>Fixture agent evaluation</title><summary>A fixture abstract with experimental results.</summary>
</entry></feed>'''


class PaperFeedTests(unittest.TestCase):
    def collect(self,raw,end):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,limit):return raw
        with tempfile.TemporaryDirectory() as folder,patch('paper_feed.urlopen',return_value=Response()):
            return collect_paper(Path(folder),end-timedelta(hours=24),end)

    def test_original_metadata_qualifies_and_matches_excerpt(self):
        bundle=self.collect(XML,datetime(2026,11,3,12,tzinfo=timezone.utc))
        self.assertEqual(len(bundle['items']),1)
        self.assertTrue(verify(bundle['items'][0],bundle['extracts'])[0])
        self.assertTrue(bundle['items'][0]['preprint'])

    def test_old_paper_does_not_become_current_by_observation(self):
        bundle=self.collect(XML,datetime(2026,11,5,12,tzinfo=timezone.utc))
        self.assertFalse(bundle['items'])

    def test_oversized_feed_is_rejected(self):
        with self.assertRaises(ValueError):
            self.collect(b'x'*1_000_001,datetime(2026,11,3,12,tzinfo=timezone.utc))
