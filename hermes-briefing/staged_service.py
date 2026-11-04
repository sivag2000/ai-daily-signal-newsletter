"""Reviewable service wiring. No command entry point or automatic live activation."""
import json
import re
from datetime import datetime
from pathlib import Path
from digest import Store
from review_pipeline import run_review
from delivery_bridge import send_once
from sequential_brief import atomic_json, exclusive_lock


def run_daily(folder, now, run_id, collector, reviewer, editor, transport):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', run_id):
        raise ValueError('Invalid occurrence')
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (run_id + '.json')
    history = folder / 'history.sqlite'
    with exclusive_lock(folder / 'service.lock'):
        if path.exists():
            state = json.loads(path.read_text(encoding='utf-8'))
            if state['status'] == 'accepted':
                return state
            if state['status'] != 'ready':
                raise RuntimeError('Research interrupted; park and inspect before rerun')
        else:
            atomic_json(path, dict(status='researching'))
            result = run_review(history, now, collector, reviewer, editor, run_id=run_id)
            state = dict(status='ready', result=result)
            atomic_json(path, state)
        result = state['result']
        receipt = send_once(folder / 'delivery', run_id, result['payload'], transport)
        store = Store(history)
        try:
            store.accept(run_id, result['items'], receipt)
            if result['coverage_complete']:
                store.cover(datetime.fromisoformat(result['end']))
        finally:
            store.close()
        state.update(status='accepted', receipt=receipt)
        atomic_json(path, state)
        return state
