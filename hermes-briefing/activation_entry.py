"""Scheduled briefing entry point for an explicitly configured Hermes profile.

Deployment requires approval. Existing durable Hermes send-only delivery is used;
the entry point never starts another Telegram polling process.
"""
import json
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from digest import Store
from delivery_bridge import import_history, legacy_transport
from feed_first import FeedFirstAdapter as HermesAdapter
from staged_service import run_daily


def execute(home, folder, now=None):
    home,folder = Path(home).resolve(),Path(folder).resolve()
    folder.mkdir(parents=True,exist_ok=True)
    now=now or datetime.now(timezone.utc)
    key=now.astimezone(timezone(timedelta(hours=5,minutes=30))).date().isoformat()
    history=folder/'history.sqlite'
    store=Store(history)
    try:
        import_history(home,store)
    finally:
        store.close()
    holder={}
    def collect(prompt):
        holder['adapter']=HermesAdapter(home,folder/'evidence'/key,history)
        return holder['adapter'].collect(prompt)
    return run_daily(folder,now,key,collect,lambda rows:holder['adapter'].review(rows,2),
                     lambda rows:holder['adapter'].review(rows,3),legacy_transport(home,'v3-'+key))


if __name__ == '__main__':
    profile=Path(os.environ.get('HERMES_HOME',Path(__file__).resolve().parents[2]))
    if profile.name!='briefing' or profile.parent.name!='profiles':
        raise SystemExit('Expected explicitly configured briefing profile')
    state=execute(profile,profile/'cron/briefing-v3')
    print(json.dumps(dict(status=state['status'],items=len(state['result']['items']))))
