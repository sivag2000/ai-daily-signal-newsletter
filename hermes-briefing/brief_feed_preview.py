"""Scheduled local briefing. A day with an interrupted run requires reconciliation."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import end_to_end_preview as preview


def main():
    home = Path(__file__).resolve().parents[2]
    if home.name != 'briefing' or home.parent.name != 'profiles':
        raise SystemExit('Expected the installed Hermes briefing profile')
    day = datetime.now(timezone(timedelta(hours=5, minutes=30))).date().isoformat()
    preview.HOME = home
    preview.ROOT = home / 'cron' / 'briefing-v3-preview' / day
    preview.FEED_FIRST = True
    summary = preview.ROOT / 'summary.json'
    if summary.is_file():
        saved = json.loads(summary.read_text(encoding='utf-8'))
        if saved.get('status') != 'completed' or saved.get('delivery') != 'preview':
            raise SystemExit('Review the existing occurrence before rerunning')
        print(json.dumps(saved))
        return
    preview.ROOT.parent.mkdir(parents=True, exist_ok=True)
    preview.main()


if __name__ == '__main__':
    main()
