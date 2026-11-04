"""Durable, bounded Telegram delivery via supported Hermes send-only CLI.

No bot polling, credentials, private scheduler APIs or automatic retries.
"""
import hashlib
import json
import os
import re
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from sequential_brief import atomic_json, exclusive_lock, runtime_command

TARGET = os.environ.get('HERMES_BRIEF_TELEGRAM_CHAT_ID', '').strip()


def now():
    return datetime.now(timezone.utc).isoformat()


def split_payload(text):
    chunks, current, units = [], [], 0
    for char in text:
        size = len(char.encode('utf-16-le')) // 2
        if units + size > 2800:
            chunks.append(''.join(current))
            current, units = [], 0
        current.append(char)
        units += size
    if current:
        chunks.append(''.join(current))
    return chunks


def cli_transport(home, text):
    home = Path(home).resolve()
    # Resolve this explicitly, rather than inheriting the research profile's absent Telegram config.
    if home.name != 'briefing' or home.parent.name != 'profiles':
        raise RuntimeError('Unexpected briefing profile path')
    runtime = runtime_command(home)
    default_home = home.parents[1]
    source = Path(runtime[0]).parents[2] / 'hermes-agent'
    env = dict(os.environ, HERMES_HOME=str(default_home), PYTHONPATH=str(source),
               PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run(runtime[:3] + ['-p', 'default', 'send', '--to', 'telegram:' + TARGET,
                             '--json', '--file', '-'], input=text, env=env,
                            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=90)
    if result.returncode:
        raise RuntimeError('Send-only CLI failed; outcome must be reconciled before any resend')
    receipt = json.loads(result.stdout)
    # Read back the exact mirrored message/target without reading unrelated conversations.
    receipt['mirror_verified'] = False
    db = default_home / 'state.db'
    if receipt.get('mirrored') and db.is_file():
        try:
            conn = sqlite3.connect(db.as_uri() + '?mode=ro', uri=True, timeout=5)
            found = conn.execute('SELECT 1 FROM messages m JOIN sessions s ON m.session_id=s.id '
                                 'WHERE s.source=? AND s.chat_id=? AND m.role=? AND m.content=? LIMIT 1',
                                 ('telegram', TARGET, 'assistant', text)).fetchone()
            receipt['mirror_verified'] = bool(found)
            conn.close()
        except sqlite3.Error:
            pass
    return receipt


def validate_accepted_record(home, key, payload, state):
    """Bind every acknowledgement to the exact durable occurrence/payload/target."""
    try:
        if not re.fullmatch(r'-?[1-9][0-9]*', TARGET):
            return False
        if not isinstance(state, dict) or state.get('state') != 'accepted':
            return False
        if state.get('key') != key or state.get('target') != 'telegram:' + TARGET:
            return False
        raw = (Path(home) / 'cron/delivery' / key / 'payload.txt').read_bytes()
        if raw != payload.encode('utf-8') or hashlib.sha256(raw).hexdigest() != state.get('payload_sha256'):
            return False
        parts = state.get('parts')
        if not isinstance(parts, list) or len(parts) != len(split_payload(payload)) or not parts:
            return False
        ids = []
        for index, part in enumerate(parts, 1):
            if not isinstance(part, dict) or part.get('index') != index or part.get('state') != 'accepted':
                return False
            mid = part.get('message_id')
            if not isinstance(mid, str) or not mid.strip():
                return False
            ids.append(mid)
        return len(ids) == len(set(ids))
    except (OSError, TypeError, ValueError):
        return False


def deliver(home, key, payload, transport=None):
    home = Path(home).resolve()
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', key):
        raise ValueError('Invalid delivery occurrence key')
    if not re.fullmatch(r'-?[1-9][0-9]*', TARGET):
        raise ValueError('Set HERMES_BRIEF_TELEGRAM_CHAT_ID to the approved numeric chat ID')
    if not isinstance(payload, str) or not payload.strip():
        raise ValueError('Empty delivery payload')
    folder = home / 'cron/delivery' / key
    folder.mkdir(parents=True, exist_ok=True)
    state_path = folder / 'state.json'
    digest = hashlib.sha256(payload.encode('utf-8')).hexdigest()
    with exclusive_lock(folder / 'delivery.lock'):
        def event(kind, **detail):
            with (folder / 'events.jsonl').open('a', encoding='utf-8', newline='\n') as handle:
                handle.write(json.dumps({'at': now(), 'event': kind, **detail}) + '\n')
                handle.flush()
                os.fsync(handle.fileno())

        if state_path.exists():
            previous = json.loads(state_path.read_text(encoding='utf-8'))
            if previous.get('payload_sha256') != digest:
                raise RuntimeError('Payload differs from preserved occurrence; manual review required')
            if previous.get('state') == 'accepted':
                if not validate_accepted_record(home, key, payload, previous):
                    raise RuntimeError('Saved acceptance evidence invalid; reconcile without resend')
                return previous
            raise RuntimeError('Prior delivery is incomplete/uncertain; reconcile before resend')
        chunks = split_payload(payload)
        state = {'key': key, 'target': 'telegram:' + TARGET, 'payload_sha256': digest,
                 'state': 'prepared', 'created_at': now(), 'parts': []}
        with (folder / 'payload.txt').open('x', encoding='utf-8', newline='\n') as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        for index, chunk in enumerate(chunks, 1):
            state['parts'].append({'index': index, 'state': 'prepared'})
        atomic_json(state_path, state)
        event('prepared', payload_sha256=digest, parts=len(chunks))
        sender = transport or (lambda text: cli_transport(home, text))
        try:
            for index, chunk in enumerate(chunks):
                part = state['parts'][index]
                part['state'] = 'sending'
                state['state'] = 'sending'
                atomic_json(state_path, state)
                event('sending', part=index + 1)
                text = f'[AI News | {key} | {index + 1}/{len(chunks)}]\n\n' + chunk
                result = sender(text)
                if (not result.get('success') or result.get('platform') != 'telegram' or
                        str(result.get('chat_id')) != TARGET or not result.get('message_id')):
                    raise RuntimeError('Invalid or mismatched platform receipt')
                part.update(state='accepted', message_id=str(result['message_id']), accepted_at=now(),
                            mirror_verified=bool(result.get('mirror_verified')))
                atomic_json(state_path, state)
                event('accepted', part=index + 1, message_id=part['message_id'], target=TARGET,
                      mirror_verified=part['mirror_verified'])
            state.update(state='accepted', accepted_at=now())
            atomic_json(state_path, state)
            event('complete')
            return state
        except Exception as exc:
            state.update(state='uncertain', error_type=type(exc).__name__, stopped_at=now())
            atomic_json(state_path, state)
            event('uncertain', error_type=type(exc).__name__)
            raise RuntimeError('Delivery uncertain/failed; evidence preserved; no automatic resend') from exc
