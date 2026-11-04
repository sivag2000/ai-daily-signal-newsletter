"""Staged bridge to the existing durable sender; no delivery on import.

Call only from an explicitly activated service. State is written before invoking any
sender, so interruption never automatically resends. Reconciliation uses receipts.
"""
import hashlib
import json
import re
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).with_name('baseline')))
from sequential_brief import exclusive_lock, atomic_json


def send_once(folder, run_id, payload, transport):
    if not run_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in run_id):
        raise ValueError('Invalid occurrence identifier')
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (run_id + '.json')
    digest = hashlib.sha256(payload.encode()).hexdigest()
    with exclusive_lock(folder / 'delivery.lock'):
        if path.exists():
            state = json.loads(path.read_text(encoding='utf-8'))
            if state['digest'] != digest:
                raise ValueError('Payload differs for existing occurrence')
            if state['state'] == 'accepted':
                return state['receipt']
            raise RuntimeError('Delivery uncertain/interrupted; reconcile saved receipt before resend')
        atomic_json(path, dict(state='sending', digest=digest))
        try:
            receipt = transport(payload)
            if not isinstance(receipt, str) or not receipt.strip():
                raise ValueError('Accepted receipt missing')
        except BaseException:
            atomic_json(path, dict(state='uncertain', digest=digest))
            raise
        atomic_json(path, dict(state='accepted', digest=digest, receipt=receipt))
        return receipt


def legacy_transport(home, occurrence):
    """Returns callable; its eventual invocation sends through the existing Hermes CLI."""
    from brief_delivery import deliver, validate_accepted_record
    def send(payload):
        receipt = deliver(Path(home), occurrence, payload)
        if not validate_accepted_record(Path(home), occurrence, payload, receipt):
            raise RuntimeError('Canonical sender receipt does not validate')
        return json.dumps(receipt, sort_keys=True)
    return send


def import_history(home, store):
    """Seed only accepted, receipt-validated, hash-bound published legacy entries.

    Old entries lack semantic event IDs; URL suppression is exact, semantic cross-source
    history remains an explicit migration limitation.
    """
    from brief_delivery import validate_accepted_record
    home = Path(home)
    imported = 0
    for path in sorted((home / 'cron/service').glob('*.json')):
        state = json.loads(path.read_text(encoding='utf-8'))
        if state.get('delivery_state') != 'accepted' or state.get('published_count', 0) == 0:
            continue
        key = state['key']
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', key) or key in ('.', '..'):
            raise ValueError('Invalid historical occurrence key')
        receipt_path = home / 'cron/delivery' / key / 'state.json'
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        if not validate_accepted_record(home, key, state['owner_payload'], receipt):
            raise ValueError('Historical delivery receipt invalid')
        # Resolve locally by key; never follow an arbitrary stored manifest path.
        manifest = json.loads((home / 'cron/sequential' / (key + '.json')).read_text(encoding='utf-8'))
        final_path = Path(manifest['final_artifact']).resolve()
        if not final_path.is_relative_to((home / 'cron/output').resolve()):
            raise ValueError('Historical artifact escaped output directory')
        if hashlib.sha256(final_path.read_bytes()).hexdigest() != manifest['final_sha256']:
            raise ValueError('Historical final artifact mismatch')
        approved = set(manifest['stages'][2]['evidence']['published_ids'])
        if len(approved) != state['published_count'] or manifest.get('published_count') != state['published_count']:
            raise ValueError('Historical publication count mismatch')
        rows = [dict(row, category='ai', event_id='legacy:' + row['url'])
                for row in manifest['stages'][0]['evidence']['articles'] if row['id'] in approved]
        if len(rows) != len(approved):
            raise ValueError('Historical published identifiers missing from evidence')
        store.accept('legacy-' + key, rows, json.dumps(receipt, sort_keys=True))
        imported += len(rows)
    return imported
