"""Public GitHub metadata snapshots. No repository code is downloaded or run."""
from datetime import datetime, timezone
import json
import base64
import re
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

from digest import stamp


def repository(url):
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.hostname != 'github.com' or parts.username or parts.query:
        raise ValueError('Expected public GitHub repository URL')
    bits = parts.path.strip('/').split('/')
    if len(bits) != 2 or any(not re.fullmatch(r'[A-Za-z0-9_.-]+', bit) or bit in ('.', '..') for bit in bits):
        raise ValueError('Expected owner/repository URL')
    return '/'.join(bits)


def fetch_public(url):
    slug = repository(url)
    request = Request('https://api.github.com/repos/' + slug,
                      headers={'Accept':'application/vnd.github+json', 'User-Agent':'HermesBriefingReview/1'})
    with urlopen(request, timeout=20) as response:
        # A redirect may rename a repository but must remain on the original API host.
        if urlsplit(response.url).hostname != 'api.github.com':
            raise ValueError('Unexpected GitHub API redirect')
        body = response.read(1_000_001)
        if len(body) > 1_000_000:
            raise ValueError('Oversized GitHub response')
        data = json.loads(body)
    return data, datetime.now(timezone.utc).isoformat()


def snapshot(store, data, observed_at):
    rid, stars = data.get('id'), data.get('stargazers_count')
    if type(rid) is not int or rid <= 0 or type(stars) is not int or stars < 0:
        raise ValueError('Invalid GitHub metadata')
    repository(data['html_url'])
    at = stamp(observed_at).isoformat()
    store.db.execute('CREATE TABLE IF NOT EXISTS github_snapshots '
                     '(repo_id INTEGER, at TEXT, stars INTEGER, metadata TEXT, PRIMARY KEY(repo_id,at))')
    existing = store.db.execute('SELECT stars,metadata FROM github_snapshots WHERE repo_id=? AND at=?', (rid,at)).fetchone()
    raw = json.dumps(data, sort_keys=True)
    if existing and existing != (stars,raw):
        raise ValueError('Conflicting snapshot for same observation')
    prior = store.db.execute('SELECT at,stars FROM github_snapshots WHERE repo_id=? AND at<? '
                             'ORDER BY at DESC LIMIT 1',(rid,at)).fetchone()
    with store.db:
        store.db.execute('INSERT OR IGNORE INTO github_snapshots VALUES (?,?,?,?)',(rid,at,stars,raw))
    result = dict(repo_id=rid,stars=stars,observed_at=at,
                  license=(data.get('license') or {}).get('spdx_id') or 'Not declared',
                  maintenance='Last pushed: ' + str(data.get('pushed_at', 'unknown')))
    if prior:
        result['previous_observation'] = dict(at=prior[0],stars=prior[1])
    return result


def fetch_readme(url,folder):
    slug=repository(url)
    endpoint='https://api.github.com/repos/'+slug+'/readme'
    request=Request(endpoint,headers={'Accept':'application/vnd.github+json','User-Agent':'HermesBriefingReview/1'})
    with urlopen(request,timeout=20) as response:
        if urlsplit(response.url).hostname!='api.github.com':raise ValueError('Unexpected README redirect')
        raw=response.read(1_000_001)
        if len(raw)>1_000_000:raise ValueError('README response too large')
    data=json.loads(raw)
    if data.get('encoding')!='base64':raise ValueError('Unexpected README encoding')
    text=base64.b64decode(data['content']).decode('utf-8')
    (folder/'github-readme-original.json').write_bytes(raw)
    return dict(url=url,content=text,kind='github_original_readme',source_api=endpoint)
