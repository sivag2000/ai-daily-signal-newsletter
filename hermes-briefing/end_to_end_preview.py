"""Full live staged-collector preview. No sender, schedule edits or activation."""
from datetime import datetime,timezone
import hashlib
import argparse
import json
import os
from pathlib import Path
import traceback
from unittest.mock import patch
from digest import Store
from delivery_bridge import import_history
from hermes_adapter import HermesAdapter,session_extracts,parse_result
from feed_first import FeedFirstAdapter
from review_pipeline import run_review

ROOT=Path('end-to-end-preview-2026-11-03')
HOME = None
status={'research':'pending','review':'pending','editor':'pending','render':'pending','audit':'pending','activation':'not authorised'}
RESEARCH_REPLAY=None
FEED_FIRST=False


def update():
    (ROOT/'status.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
    lines=['# End-to-End Live Preview Dashboard','', 'Master Agent // Live Preview','',
           '```mermaid','flowchart LR',' A[Live collector] --> B[Evidence and duplicates]',
           ' B --> C[Reviewer]',' C --> D[Editor]',' D --> E[Local draft and audit]',
           ' E --> F[Owner review]','```','',
           '| Step | Status |','|---|---|']
    for step,state in status.items():
        label='~~'+step+'~~' if state=='passed' else step
        lines.append('| '+label+' | '+state+' |')
    lines += ['', 'Delivery is disconnected. No Telegram send or activation is part of this run.',
              '', '[Local regression tests](../TEST-RESULTS.md)']
    if (ROOT/'PREVIEW.md').exists():lines+=['','[Live preview](PREVIEW.md)']
    if (ROOT/'RESULTS.md').exists():lines+=['','[Full results](RESULTS.md)']
    (ROOT/'DASHBOARD.md').write_text('\n'.join(lines),encoding='utf-8')


class ProgressAdapter(HermesAdapter):
    def invoke(self,prompt,stage):
        if stage==1 and RESEARCH_REPLAY:
            raw=(RESEARCH_REPLAY/'evidence/stage-1.jsonl').read_text(encoding='utf-8')
            parsed=parse_result(raw,metadata=True)
            registry=json.loads(Path(__file__).with_name('sources.json').read_text(encoding='utf-8'))
            seeds=[url for urls in registry.values() for url in urls if '{' not in url]+['https://github.com/trending']
            extracts=session_extracts(self.home,parsed['session_id'],seed_urls=seeds)
            (self.evidence_dir/'stage-1.jsonl').write_text(raw,encoding='utf-8')
            text=parsed['text'].strip()
            if text.startswith('```'):text='\n'.join(text.splitlines()[1:-1])
            return json.loads(text),extracts
        return super().invoke(prompt,stage)
    def collect(self,prompt):
        status['research']='running';update()
        result=super().collect(prompt)
        status['research']='passed';update()
        return result


    def review(self,rows,stage):
        name='review' if stage==2 else 'editor'
        status[name]='running';update()
        result=super().review(rows,stage)
        status[name]='passed';update()
        return result


class FeedProgressAdapter(ProgressAdapter,FeedFirstAdapter):
    pass


def fingerprint():
    paths=[HOME/'scripts'/name for name in ('brief_service.py','brief_delivery.py','brief_prompts.py','sequential_brief.py')]
    paths+=[HOME/'config.yaml',HOME/'cron/jobs.json']
    return {str(path.relative_to(HOME)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def main():
    if ROOT.exists():raise SystemExit('Evidence directory already exists; preserve it before another trial')
    ROOT.mkdir()
    update()
    before=fingerprint()
    (ROOT/'active-before.json').write_text(json.dumps(before,indent=2),encoding='utf-8')
    history=ROOT/'history.sqlite'
    store=Store(history)
    try:
        imported=import_history(HOME,store)
        sent_before=store.db.execute('SELECT COUNT(*) FROM sent').fetchone()[0]
    finally:store.close()
    sends=[]
    def forbidden(*args,**kwargs):
        sends.append('blocked send attempt')
        raise AssertionError('Live preview may not send anything to Telegram')
    try:
        adapter_type=FeedProgressAdapter if FEED_FIRST else ProgressAdapter
        adapter=adapter_type(HOME,ROOT/'evidence',history)
        # These guards protect against accidental delivery wiring in the parent process.
        # Child research sessions expose web tools only, checked against canonical records.
        with patch('brief_delivery.deliver',forbidden),patch('brief_delivery.cli_transport',forbidden),patch('delivery_bridge.legacy_transport',forbidden):
            now=datetime.fromisoformat(json.loads((RESEARCH_REPLAY/'result.json').read_text())['end']) if RESEARCH_REPLAY else datetime.now(timezone.utc)
            result=run_review(history,now,adapter.collect,
                              lambda rows:adapter.review(rows,2),lambda rows:adapter.review(rows,3),sender=None)
        status['render']='passed';update()
        (ROOT/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        (ROOT/'PREVIEW.md').write_text('# END-TO-END LIVE PREVIEW — NOT SENT\n\n'+result['payload'],encoding='utf-8')
        registry=json.loads(Path(__file__).with_name('sources.json').read_text(encoding='utf-8'))
        seeds=[url for urls in registry.values() for url in urls if '{' not in url]+['https://github.com/trending']+getattr(adapter,'seed_urls',[])
        audits=[]
        for stream in sorted((ROOT/'evidence').glob('stage-*.jsonl')):
            stage=int(stream.stem.rsplit('-',1)[-1])
            parsed=parse_result(stream.read_text(encoding='utf-8'),metadata=True)
            session_extracts(HOME,parsed['session_id'],search_cap=12 if stage==1 else 0,
                             extract_cap=12 if stage==1 else 0,seed_urls=seeds if stage==1 else ())
            audits.append(dict(stage=stage,passed=True))
        status['audit']='passed'
        store=Store(history)
        try:
            sent_after=store.db.execute('SELECT COUNT(*) FROM sent').fetchone()[0]
            checkpoint=store.checkpoint()
        finally:store.close()
        after=fingerprint()
        safety=dict(no_sender_passed=True,delivery_guard_calls=len(sends),accepted_history_unchanged=sent_before==sent_after,
                    coverage_checkpoint=checkpoint,active_file_changes=[name for name in before if before[name]!=after[name]])
        if sends or sent_before!=sent_after or checkpoint is not None:
            raise AssertionError('Preview delivery/history boundary violated')
        summary=dict(status='completed',imported_history=imported,selected=len(result['items']),
                     categories=[row['category'] for row in result['items']],delivery=result['delivery'],
                     coverage_complete=result['coverage_complete'],audits=audits,safety=safety)
        summary['research_reused_from']=str(RESEARCH_REPLAY) if RESEARCH_REPLAY else None
        (ROOT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
        print(json.dumps(summary),flush=True)
    except Exception as exc:
        status['audit']='blocked: '+type(exc).__name__
        (ROOT/'error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        print(json.dumps(dict(status='failed',error_type=type(exc).__name__)),flush=True)
        raise
    finally:update()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--home', type=Path, default=os.environ.get('HERMES_HOME'))
    parser.add_argument('--output',default=str(ROOT))
    parser.add_argument('--reuse-research')
    parser.add_argument('--feed-first',action='store_true')
    args=parser.parse_args()
    if not args.home:
        parser.error('supply --home or set HERMES_HOME')
    HOME = Path(args.home).resolve()
    ROOT=Path(args.output)
    RESEARCH_REPLAY=Path(args.reuse_research) if args.reuse_research else None
    FEED_FIRST=args.feed_first
    main()
