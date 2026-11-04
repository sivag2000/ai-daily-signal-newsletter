import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from digest import Store, select, render, canonical_url, window, verify

NOW = datetime(2026, 11, 2, 1, 30, tzinfo=timezone.utc)


def article(**changes):
    row = dict(category='ai', title='Fixture model release', url='https://openai.com/news/fixture',
               event_id='lab:model:release-1', published_at='2026-11-01T12:00:00+00:00',
               precision='timestamp', publication_excerpt='Published 1 November 2026',
               claim_excerpt='A fixture model was released.', summary='A fixture model was released.',
               why='Useful for evaluating agents.', takeaway='Compare against your baseline.',
               evidence_id='extract-1', score=5)
    row.update(changes)
    return row


class DigestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / 'history.sqlite')
        self.addCleanup(self.store.close)

    def pick(self, rows):
        return select(rows, self.store, *window(NOW, self.store))

    def test_tracking_parameters(self):
        self.assertEqual(canonical_url('https://OPENAI.com/news/a/?utm_source=x#top'), 'https://openai.com/news/a')

    def test_cross_source_event(self):
        got, rejected = self.pick([article(), article(url='https://finextra.com/news/fixture')])
        self.assertEqual(len(got), 1)
        self.assertEqual(rejected[0]['reason'], 'duplicate event or identity')

    def test_accepted_delivery_suppresses(self):
        rows, _ = self.pick([article()])
        self.store.accept('daily-1', rows, 'receipt-1')
        self.assertEqual(self.pick([article()])[0], [])

    def test_failed_delivery_keeps_eligible(self):
        self.pick([article()])
        self.store.cover(NOW)
        self.assertEqual(len(self.pick([])[0]), 1)

    def test_same_title_on_another_site_with_changed_event_is_suppressed(self):
        rows,_ = self.pick([article()])
        self.store.accept('one',rows,'r1')
        repeated=article(url='https://finextra.com/another-url',event_id='different-event-name')
        self.assertFalse(self.pick([repeated])[0])

    def test_paper_identity_across_versions(self):
        row = article(category='paper', paper_id='arxiv:2611.00001v1', preprint=True)
        got, _ = self.pick([row])
        self.store.accept('one', got, 'r1')
        changed = dict(row, paper_id='arxiv:2611.00001v2')
        self.assertEqual(self.pick([changed])[0], [])
        changed.update(update_id='v2', update_summary='Adds a new experiment and revises conclusions.')
        self.assertEqual(len(self.pick([changed])[0]), 1)

    def test_repository_stable_id_and_update(self):
        row = article(category='github', repo_id=123, stars=100, observed_at=NOW.isoformat(),
                      license='MIT', maintenance='Recent commits', documentation='Install guide',
                      usefulness='Local agent evaluation')
        got, _ = self.pick([row])
        self.store.accept('one', got, 'r1')
        self.assertEqual(self.pick([dict(row, stars=900)])[0], [])
        revised = dict(row, update_id='release:v2', update_summary='Adds offline inference.')
        self.assertEqual(len(self.pick([revised])[0]), 1)

    def test_date_only_labels_precision(self):
        got, _ = self.pick([article(published_at='2026-11-01', precision='date')])
        self.assertIn('date only', render(got))

    def test_unknown_date_rejected(self):
        got, rejected = self.pick([article(published_at='unknown')])
        self.assertFalse(got)
        self.assertTrue(rejected)

    def test_future_rejected(self):
        self.assertFalse(self.pick([article(published_at='2026-11-03T12:00:00Z')])[0])

    def test_quotas(self):
        rows = [article(url=f'https://openai.com/news/{n}', event_id=f'event-{n}') for n in range(8)]
        self.assertEqual(len(self.pick(rows)[0]), 3)

    def test_late_window_checkpoint(self):
        self.store.cover(datetime(2026, 10, 30, 1, 30, tzinfo=timezone.utc))
        start, end = window(NOW, self.store)
        self.assertEqual(start.isoformat(), '2026-10-29T23:30:00+00:00')
        self.assertEqual(end, NOW)

    def test_missing_canonical_evidence(self):
        self.assertFalse(verify(article(), {})[0])

    def test_evidence_matches_url_and_excerpts(self):
        row = article()
        extracts = {'extract-1': dict(url=row['url'], content=row['publication_excerpt']+' '+row['claim_excerpt'])}
        self.assertTrue(verify(row, extracts)[0])
        extracts['extract-1']['url'] = 'https://example.com/other'
        self.assertFalse(verify(row, extracts)[0])

    def test_payload_is_bound_to_receipt(self):
        rows, _ = self.pick([article()])
        self.store.accept('one', rows, 'r1')
        with self.assertRaises(ValueError):
            self.store.accept('one', [dict(rows[0], summary='Changed')], 'r1')

    def test_no_empty_receipt(self):
        with self.assertRaises(ValueError):
            self.store.accept('one', [], '')

    def test_empty_brief_does_not_claim_no_news(self):
        self.assertIn('Coverage insufficient', render([]))


if __name__ == '__main__':
    unittest.main()
