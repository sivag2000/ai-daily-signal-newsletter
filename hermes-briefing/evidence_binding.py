"""Separate repository observation receipts from verbatim source claims."""
import html
from digest import canonical_url


def normalized(value):
    return ' '.join(html.unescape(str(value)).split())


def bind_observation(row, metadata, at, extracts):
    row=dict(row)
    claim=normalized(row.get('claim_excerpt',''))
    matches=[key for key,record in extracts.items()
             if canonical_url(record['url'])==canonical_url(row['url'])
             and claim and claim in normalized(record.get('content',''))]
    row['claim_evidence_id']=matches[-1] if matches else 'missing'
    key=f"github-observation:{metadata['id']}:{at}"
    excerpt='Observed at: '+at
    extracts[key]=dict(url=row['url'],kind='github_api_observation',repo_id=metadata['id'],
                       observed_at=at,stars=metadata['stargazers_count'],
                       license=metadata.get('license'),pushed_at=metadata.get('pushed_at'),
                       content=excerpt+'\n'+str(metadata.get('description') or ''),
                       source_api='https://api.github.com/repos/'+metadata['full_name'])
    row.update(evidence_id=key,publication_excerpt=excerpt,published_at=at,precision='observation')
    return row
