"""Staged briefing policy. No network, model invocation or delivery side effects."""
import hashlib
import html
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

LIMITS = {'ai': 3, 'fintech': 2, 'paper': 2, 'github': 2}
LABELS = {'ai': 'AI developments', 'fintech': 'Fintech and banking',
          'paper': 'AI research', 'github': 'AI open source'}


def stamp(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Timezone required')
    return dt.astimezone(timezone.utc)


def canonical_url(url):
    parts = urlsplit(url)
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username:
        raise ValueError('Invalid source URL')
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith('utm_')
             and k.lower() not in ('fbclid', 'gclid')]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip('/'),
                      urlencode(sorted(query)), ''))


def identity(item):
    if item['category'] == 'paper':
        pid = item['paper_id'].lower().strip()
        return 'paper:' + re.sub(r'v\d+$', '', pid) if pid.startswith('arxiv:') else 'paper:' + pid
    if item['category'] == 'github':
        if type(item['repo_id']) is not int or item['repo_id'] <= 0:
            raise ValueError('Stable numeric GitHub repository ID required')
        return 'github:' + str(item['repo_id'])
    return 'url:' + canonical_url(item['url'])


def window(now, store):
    end = stamp(now.isoformat())
    previous = store.checkpoint()
    start = stamp(previous) - timedelta(hours=2) if previous else end - timedelta(hours=24)
    if start >= end:
        raise ValueError('Coverage checkpoint is ahead of clock')
    return start, end


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS coverage (id INTEGER PRIMARY KEY CHECK(id=1), end TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS sent (identity TEXT, event TEXT, revision TEXT, '
                        'run TEXT, receipt TEXT, PRIMARY KEY(identity, revision))')
        self.db.execute('CREATE TABLE IF NOT EXISTS receipts (run TEXT PRIMARY KEY, digest TEXT, receipt TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS pending (identity TEXT, revision TEXT, body TEXT, PRIMARY KEY(identity,revision))')
        self.db.execute('CREATE TABLE IF NOT EXISTS stories (identity TEXT, revision TEXT, body TEXT, PRIMARY KEY(identity,revision))')
        self.db.commit()

    def close(self):
        self.db.close()

    def checkpoint(self):
        row = self.db.execute('SELECT end FROM coverage WHERE id=1').fetchone()
        return row[0] if row else None

    def cover(self, end):
        value = stamp(end.isoformat()).isoformat()
        old = self.checkpoint()
        if old and stamp(value) < stamp(old):
            raise ValueError('Coverage cannot go backwards')
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO coverage VALUES (1,?)', (value,))

    def seen(self, key, event, revision):
        return self.db.execute('SELECT 1 FROM sent WHERE (identity=? OR event=?) AND revision=?',
                               (key, event, revision)).fetchone() is not None

    def pending(self):
        return [json.loads(row[0]) for row in self.db.execute('SELECT body FROM pending')]

    def story_context(self):
        return [json.loads(row[0]) for row in self.db.execute('SELECT body FROM stories ORDER BY rowid DESC LIMIT 100')]

    def queue(self, item):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO pending VALUES (?,?,?)',
                            (identity(item), item.get('update_id', ''), json.dumps(item)))

    def accept(self, run, items, receipt):
        if not isinstance(receipt, str) or not receipt.strip():
            raise ValueError('Accepted delivery receipt required')
        digest = hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest()
        prior = self.db.execute('SELECT digest,receipt FROM receipts WHERE run=?', (run,)).fetchone()
        if prior:
            if prior != (digest, receipt):
                raise ValueError('Occurrence receipt/payload mismatch')
            return
        with self.db:
            self.db.execute('INSERT INTO receipts VALUES (?,?,?)', (run, digest, receipt))
            for item in items:
                self.db.execute('INSERT OR IGNORE INTO stories VALUES (?,?,?)',
                                (identity(item), item.get('update_id', ''), json.dumps(item)))
                self.db.execute('INSERT OR IGNORE INTO sent VALUES (?,?,?,?,?)',
                                (identity(item), item['event_id'], item.get('update_id', ''), run, receipt))
                self.db.execute('DELETE FROM pending WHERE (identity=? OR json_extract(body,\'$.event_id\')=?) AND revision=?',
                                (identity(item), item['event_id'], item.get('update_id', '')))


def verify(item, extracts):
    """Excerpts must match trusted collector records, never model-supplied audit claims.

    Date interpretation and event clustering still require independent review.
    """
    record = extracts.get(item.get('evidence_id'), {})
    normalize = lambda s: ' '.join(html.unescape(str(s)).split())
    try:
        if canonical_url(record['url']) != canonical_url(item['url']):
            return False, 'evidence URL mismatch'
        body = normalize(record['content'])
        if record.get('error'):
            return False, 'extraction failed'
        if item.get('category')=='github' and item.get('precision')=='observation':
            if (record.get('kind')!='github_api_observation' or record.get('repo_id')!=item.get('repo_id')
                or record.get('observed_at')!=item.get('observed_at') or record.get('stars')!=item.get('stars')):
                return False,'repository observation receipt mismatch'
        for key in ('publication_excerpt', 'claim_excerpt'):
            field_record=extracts.get(item.get('claim_evidence_id'),{}) if key=='claim_excerpt' and item.get('claim_evidence_id') else record
            if canonical_url(field_record['url'])!=canonical_url(item['url']):
                return False,'claim source URL mismatch'
            if field_record.get('error') or not item.get(key) or normalize(item[key]) not in normalize(field_record['content']):
                return False, 'unsupported ' + key
    except (KeyError, ValueError, TypeError):
        return False, 'canonical extraction missing'
    return True, ''


def select(items, store, start, end, *, persist=True, include_pending=True):
    kept, rejected, seen = [], [], set()
    pending = store.pending() if include_pending else []
    pending_keys = {(identity(row), row.get('update_id', '')) for row in pending}
    counts = dict.fromkeys(LIMITS, 0)
    def score(row):
        value = row.get('score', 0)
        return value if type(value) in (int, float) else 0
    for raw in sorted(pending + list(items), key=score, reverse=True):
        item = dict(raw)
        try:
            category = item['category']
            if category not in LIMITS:
                raise ValueError('unknown category')
            for field in ('title', 'event_id', 'summary', 'why', 'takeaway', 'publication_excerpt', 'claim_excerpt'):
                if not isinstance(item.get(field), str) or not item[field].strip():
                    raise ValueError('missing ' + field)
            key = identity(item)
            queued = (key, item.get('update_id', '')) in pending_keys
            canonical_url(item['url'])
            if category == 'github' and item.get('precision') == 'observation':
                if stamp(item['published_at']) != stamp(item['observed_at']):
                    raise ValueError('Repository discovery must use actual observation time')
            elif item.get('precision') == 'date':
                day = datetime.strptime(item['published_at'], '%Y-%m-%d').date()
                # Calendar overlap; no timestamp is fabricated for the article.
                if (day < start.date() and not queued) or day > end.date():
                    raise ValueError('outside coverage dates')
            elif item.get('precision') == 'timestamp':
                published = stamp(item['published_at'])
                if published >= end or (published < start and not queued):
                    raise ValueError('outside coverage window')
            else:
                raise ValueError('publication precision missing')
            if category == 'paper' and type(item.get('preprint')) is not bool:
                raise ValueError('paper review status required')
            if category == 'github':
                for field in ('license', 'maintenance', 'documentation', 'usefulness'):
                    if not item.get(field):
                        raise ValueError('repository review missing ' + field)
                if type(item.get('stars')) is not int or item['stars'] < 0:
                    raise ValueError('invalid stars')
                if stamp(item['observed_at']) > datetime.now(timezone.utc):
                    raise ValueError('future star observation')
                # Star growth must be calculated from two observations.
                item.pop('daily_growth', None)
                before = item.get('previous_observation')
                if before:
                    elapsed = stamp(item['observed_at']) - stamp(before['at'])
                    if elapsed.total_seconds() <= 0 or type(before['stars']) is not int or before['stars'] < 0:
                        raise ValueError('invalid star observation pair')
                    item['star_change'] = item['stars'] - before['stars']
                    item['star_interval_hours'] = round(elapsed.total_seconds() / 3600, 1)
            revision = item.get('update_id', '')
            if revision and not item.get('update_summary', '').strip():
                raise ValueError('update requires explanation of material change')
            event = item['event_id']
            title_key = ' '.join(re.findall(r'[a-z0-9]+', item['title'].lower()))
            same_title = any(' '.join(re.findall(r'[a-z0-9]+', old.get('title','').lower())) == title_key
                             and old.get('update_id','') == revision for old in store.story_context())
            identities = {(key, revision), ('event:' + event, revision)}
            if same_title or seen.intersection(identities) or store.seen(key, event, revision):
                raise ValueError('duplicate event or identity')
            if persist:
                store.queue(item)
            if counts[category] >= LIMITS[category]:
                raise ValueError('category limit')
            seen.update(identities)
            counts[category] += 1
            kept.append(item)
        except (ValueError, KeyError, TypeError) as exc:
            rejected.append({'url': item.get('url'), 'reason': str(exc)})
    return kept, rejected


def render(items):
    if not items:
        return 'Coverage insufficient: no new verified items selected. This does not establish that there was no news.'
    lines = ['AI and Fintech Briefing']
    for category in LIMITS:
        rows = [item for item in items if item['category'] == category]
        if not rows:
            continue
        lines += ['', LABELS[category]]
        for item in rows:
            update = 'Update — ' if item.get('update_id') else ''
            precision = ' (date only; time unavailable)' if item['precision'] == 'date' else ''
            source_date = 'Observed ' if item.get('precision') == 'observation' else ''
            lines += [f"{update}{item['title']}", item['summary'],
                      f"Why it matters: {item['why']}", f"Takeaway: {item['takeaway']}",
                      f"Source: {item['url']} | {source_date}{item['published_at']}{precision}"]
            if update:
                lines += ['What changed: ' + item['update_summary']]
            if item.get('evidence_tier')=='publisher_feed_summary':
                lines += ['Evidence: publisher feed summary; article body not verified.']
            elif item.get('evidence_tier')=='publisher_feed_date_and_article_extract':
                lines += ['Evidence: publication timestamp from publisher feed; article extract checked.']
            if category == 'paper':
                lines += ['Research status: ' + ('Preprint' if item['preprint'] else 'Peer reviewed')]
            if category == 'github':
                lines += [f"Stars: {item['stars']} (observed {item['observed_at']})",
                          f"License: {item['license']}; maintenance: {item['maintenance']}"]
                if 'star_change' in item:
                    lines += [f"Star change: {item['star_change']:+} over {item['star_interval_hours']} hours"]
    lines += ['', 'Coverage is selective. Missing sections have no selected items.']
    return '\n'.join(lines)
