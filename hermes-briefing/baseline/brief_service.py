"""Cron entry point: sequential work -> actual session audit -> durable Telegram send.

A platform acceptance is not a human-read receipt. No automatic inference retries.
"""
import argparse
import hashlib
import html
import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from brief_delivery import deliver, validate_accepted_record
from sequential_brief import IST, atomic_json, exclusive_lock, pipeline


def normalized(text):
    return ' '.join(html.unescape(str(text)).split())


def tool_object(text):
    start = text.find('{')
    if start < 0:
        raise ValueError('Tool response has no JSON object')
    value, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(value, dict):
        raise ValueError('Tool response is not an object')
    return value


def audit_sessions(home, manifest):
    """Audit recorded operations/excerpts, not web completeness or factual omniscience."""
    result = {'status': 'rejected', 'issues': [], 'counts': {}, 'proves_no_news': False,
              'limits': ['Publication semantics and source truth still need editorial verification.',
                         'Post-run budget measurement cannot undo an excessive model tool call.']}
    stages = manifest.get('stages', [])
    db = Path(home) / 'state.db'
    if len(stages) != 3 or not db.is_file():
        result['issues'].append('Missing completed sessions or evidence database')
        return result
    try:
        conn = sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True, timeout=10)
        conn.row_factory = sqlite3.Row
        articles = {a['id']: a for a in stages[0]['evidence']['articles']}
        for stage in stages:
            number = stage['stage']
            label = 'S' + str(number)
            sid = stage.get('session_id')
            rows = conn.execute('SELECT role,content,tool_calls,tool_name,tool_call_id FROM messages WHERE session_id=? ORDER BY id', (sid,)).fetchall() if sid else []
            if not rows:
                result['issues'].append(label + ' canonical session missing')
                continue
            counts = {'search': 0, 'extract_urls': 0, 'failed_returns': 0}
            extracts, discovered, call_ids, returned = {}, set(), set(), set()
            if number != 1:
                discovered.update(a['url'] for a in articles.values())
            for row in rows:
                if row['role'] == 'assistant' and row['tool_calls']:
                    for call in json.loads(row['tool_calls']):
                        function = call.get('function', {})
                        name = function.get('name')
                        cid = call.get('id') or call.get('call_id')
                        if not cid or cid in call_ids:
                            result['issues'].append(label + ' duplicate/missing tool call identifier')
                            continue
                        call_ids.add(cid)
                        args = function.get('arguments', {})
                        args = json.loads(args) if isinstance(args, str) else args
                        if name == 'web_search':
                            counts['search'] += 1
                            if args.get('limit') != 10:
                                result['issues'].append(label + ' search limit differs from approved 10')
                        elif name == 'web_extract':
                            urls = args.get('urls', [])
                            if not isinstance(urls, list):
                                raise ValueError('Invalid extraction request')
                            counts['extract_urls'] += len(urls)
                            if any(url not in discovered for url in urls):
                                result['issues'].append(label + ' extraction URL has no earlier discovery/upstream evidence')
                        else:
                            result['issues'].append(label + ' unexpected tool type')
                elif row['role'] == 'tool':
                    returned.add(row['tool_call_id'])
                    payload = tool_object(row['content'] or '')
                    if row['tool_name'] == 'web_search':
                        if not payload.get('success', False):
                            counts['failed_returns'] += 1
                        for item in payload.get('data', {}).get('web', []):
                            if isinstance(item.get('url'), str):
                                discovered.add(item['url'])
                    elif row['tool_name'] == 'web_extract':
                        for item in payload.get('results', []):
                            body = item.get('content')
                            if item.get('error') or not body:
                                counts['failed_returns'] += 1
                                continue
                            extracts[item['url']] = normalized(body)
                            discovered.update(re.findall(r'https?://[^\s<>\)\"\']+', body))
            if call_ids != returned:
                result['issues'].append(label + ' tool calls and terminal tool returns do not reconcile')
            result['counts'][label] = counts
            if number == 1:
                if counts['search'] > 12:
                    result['issues'].append('S1 search cap exceeded')
                reported = stage['evidence']['reported_tool_counts']
                if any(reported.get(key) != counts[key] for key in ('search', 'extract_urls')):
                    result['issues'].append('S1 reported tool counts do not match canonical operations')
                ids = list(articles)
            else:
                if counts['search']:
                    result['issues'].append(label + ' unauthorized search instead of review-only extraction')
                ids = stage['evidence']['approved_ids' if number == 2 else 'published_ids']
            if counts['extract_urls'] > 8:
                result['issues'].append(label + ' extraction URL cap exceeded')
            for aid in ids:
                article = articles[aid]
                source = extracts.get(article['url'], '')
                if not source:
                    result['issues'].append(label + ' article has no successful canonical extraction: ' + aid)
                    continue
                for key in ('publication_excerpt', 'claim_excerpt'):
                    excerpt = normalized(article.get(key, ''))
                    if not excerpt or excerpt not in source:
                        result['issues'].append(label + ' unsupported ' + key + ': ' + aid)
        conn.close()
        result['status'] = 'verified' if not result['issues'] else 'rejected'
    except (sqlite3.Error, ValueError, TypeError, KeyError) as exc:
        result['issues'].append('Canonical audit unavailable: ' + type(exc).__name__)
    return result


def service(home, *, repair_trial=None, attempt=1, runner=None, transport=None, auditor=None):
    home = Path(home).resolve()
    day = datetime.now(IST).date().isoformat()
    key = day + (f'-repair-{repair_trial}-attempt{attempt}' if repair_trial else '')
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', key):
        raise ValueError('Invalid service occurrence')
    folder = home / 'cron/service'
    folder.mkdir(parents=True, exist_ok=True)
    state_path = folder / (key + '.json')
    manifest_path = home / 'cron/sequential' / (key + '.json')
    with exclusive_lock(folder / 'service.lock'):
        previous = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else None
        if previous and previous.get('delivery_state') == 'accepted':
            try:
                saved = json.loads((home / 'cron/delivery' / key / 'state.json').read_text(encoding='utf-8'))
                valid = validate_accepted_record(home, key, previous['owner_payload'], saved)
            except (OSError, ValueError, KeyError, TypeError):
                valid = False
            if not valid:
                raise RuntimeError('Saved service acceptance invalid; reconcile without resend')
            return previous
        if previous and previous.get('status') in {'running', 'delivery_uncertain'}:
            raise RuntimeError('Service occurrence interrupted/uncertain; reconcile, do not replay')
        state = {'key': key, 'started_at': datetime.now(IST).isoformat(), 'status': 'running',
                 'delivery_state': 'not_attempted', 'kind': 'repair_trial' if repair_trial else 'daily'}
        atomic_json(state_path, state)
        try:
            pipeline(home, runner=runner, repair_trial=repair_trial, attempt=attempt)
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            if manifest.get('status') != 'completed' or not manifest.get('owner_message'):
                raise RuntimeError('Pipeline did not produce a valid current-contract owner output')
            artifact = Path(manifest['final_artifact'])
            if hashlib.sha256(artifact.read_bytes()).hexdigest() != manifest['final_sha256']:
                raise RuntimeError('Final artifact hash mismatch')
            audit = (auditor or audit_sessions)(home, manifest)
            audit_dir = home / 'cron/audits'
            audit_dir.mkdir(parents=True, exist_ok=True)
            atomic_json(audit_dir / (key + '.json'), audit)
            state.update(execution='completed', quality=manifest['quality'], published_count=manifest['published_count'],
                         audit_status=audit['status'], manifest=str(manifest_path))
            if audit['status'] == 'verified':
                message = manifest['owner_message']
                if manifest['quality'] == 'RESEARCH_INSUFFICIENT':
                    message += '\nNo publishable items were established within the fixed 24-hour window. This does not mean there was no news. The research-quality acceptance gate remains unmet.'
                else:
                    message += '\n\nEvidence note: recorded tool operations and quoted excerpts were checked; coverage is not exhaustive.'
            else:
                message = 'AI-news research evidence could not be verified. No unverified brief is being published.\nReason: ' + '; '.join(audit['issues'][:3]) + '\nEvidence is preserved; no automatic rerun.'
        except Exception as exc:
            state.update(execution='failed', quality='UNVERIFIED', error_type=type(exc).__name__)
            message = ('AI-news pipeline stopped before a verified final brief.\n'
                       'Reason: stage/runtime/evidence validation failed.\n'
                       'Downstream processing stopped. Evidence is preserved for review; no automatic rerun.')
        if repair_trial:
            message = '[SUPERVISED REPAIR TEST — not a scheduled acceptance pass]\n\n' + message
        state.update(owner_payload=message, status='ready_to_deliver')
        atomic_json(state_path, state)
        try:
            receipt = deliver(home, key, message, transport=transport)
            state.update(status='finished', delivery_state=receipt['state'], finished_at=datetime.now(IST).isoformat(),
                         message_ids=[x['message_id'] for x in receipt['parts']],
                         mirror_verified=all(x.get('mirror_verified') for x in receipt['parts']))
            atomic_json(state_path, state)
        except Exception as exc:
            state.update(status='delivery_uncertain', delivery_state='uncertain', delivery_error_type=type(exc).__name__)
            atomic_json(state_path, state)
            raise
        return state


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repair-trial')
    parser.add_argument('--attempt', type=int, choices=(1, 2), default=1)
    args = parser.parse_args()
    home = Path(os.environ.get('HERMES_HOME') or Path(__file__).resolve().parents[1])
    try:
        result = service(home, repair_trial=args.repair_trial, attempt=args.attempt)
        print(json.dumps({k: result.get(k) for k in ('key','status','execution','quality','published_count','audit_status','delivery_state','message_ids','mirror_verified')}))
        # Delivery failure is separately raised; insufficient quality is not a false execution success.
        if result.get('execution') != 'completed':
            print('[CRON_FAILURE] execution failed; owner status notice delivered')
            sys.exit(1)
    except Exception as exc:
        print('[CRON_FAILURE] Service stopped: ' + type(exc).__name__ + '; inspect durable service/delivery records before retry')
        sys.exit(1)
