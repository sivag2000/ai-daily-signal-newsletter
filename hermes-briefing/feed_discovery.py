"""Bounded RSS/Atom discovery; fetched text is never executable instruction."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import hashlib
import html
import ipaddress
import json
from pathlib import Path
import re
from urllib.parse import urlsplit,urljoin
from urllib.request import Request,build_opener,HTTPRedirectHandler
import xml.etree.ElementTree as ET
from digest import canonical_url,stamp

FEEDS=[
 dict(name='OpenAI',category='ai',url='https://openai.com/news/rss.xml'),
 dict(name='TechCrunch AI',category='ai',url='https://techcrunch.com/category/artificial-intelligence/feed/'),
 dict(name='The Verge AI',category='ai',url='https://www.theverge.com/rss/ai-artificial-intelligence/index.xml'),
 dict(name='Finextra',category='fintech',url='https://www.finextra.com/rss/headlines.aspx'),
 dict(name='Banking Dive',category='fintech',url='https://www.bankingdive.com/feeds/news/'),
 dict(name='Federal Reserve Banking',category='fintech',url='https://www.federalreserve.gov/feeds/press_bcreg.xml')]


def public_url(url):
    p=urlsplit(url)
    if p.scheme not in ('https','http') or not p.hostname or p.username or p.password:
        return False
    host=p.hostname.lower()
    if host=='localhost' or host.endswith(('.local','.localhost','.internal')):return False
    try:return ipaddress.ip_address(host).is_global
    except ValueError:return '.' in host and not re.fullmatch(r'(?:0x[0-9a-f]+|[0-9]+)(?:\.(?:0x[0-9a-f]+|[0-9]+))*',host)


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if not public_url(newurl):raise ValueError('Non-public redirect blocked')
        return super().redirect_request(req,fp,code,msg,headers,newurl)


class PlainText(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.parts=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.skip+=1
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.skip=max(0,self.skip-1)
    def handle_data(self,text):
        if not self.skip:self.parts.append(text)


def plain(text):
    parser=PlainText();parser.feed(text)
    return ' '.join(' '.join(parser.parts).split())[:8000]


def injection_flags(text):
    text=html.unescape(html.unescape(text)).lower()
    patterns={
      'instruction_override':r'\b(?:ignore|disregard)\b.{0,50}\b(?:previous|prior|all)\b.{0,25}\binstructions\b',
      'role_override':r'\byou are now\b|<\s*(?:system|developer)\s*>|\[system\]',
      'secret_exfiltration':r'\b(?:send|upload|exfiltrate|reveal)\b.{0,100}\b(?:secrets|api keys|credentials|tokens)\b'}
    return [name for name,pattern in patterns.items() if re.search(pattern,text,re.S)]


def published(raw):
    if not raw:return None
    try:dt=parsedate_to_datetime(raw)
    except (ValueError,TypeError):
        try:dt=datetime.fromisoformat(raw.replace('Z','+00:00'))
        except ValueError:return None
    if dt.tzinfo is None:return None
    return dt.astimezone(timezone.utc).isoformat()


def parse_feed(raw,source):
    if len(raw)>4_000_000:raise ValueError('Oversized feed')
    xml=raw.decode('utf-8-sig')
    if '\x00' in xml or re.search(r'<!\s*(?:DOCTYPE|ENTITY)\b',xml,re.I):raise ValueError('DTD/entities prohibited')
    root=ET.fromstring(xml)
    local=lambda tag:tag.rsplit('}',1)[-1]
    rows=[]
    for entry in root.iter():
        if local(entry.tag) not in ('item','entry'):continue
        fields={}
        for child in entry:
            fields.setdefault(local(child.tag),child)
        text=lambda key:''.join(fields[key].itertext()).strip() if key in fields else ''
        link=text('link')
        if 'link' in fields and fields['link'].get('href'):link=fields['link'].get('href')
        if not link and public_url(text('id')):link=text('id')
        if not link:continue
        link=urljoin(source['url'],link)
        if not public_url(link):continue
        title=plain(text('title'))
        if not title:continue
        date=text('pubDate') or text('published') or text('date')
        description=text('description') or text('summary') or text('content') or text('encoded')
        flags=injection_flags(text('title')+' '+description)
        normalized_title=' '.join(re.findall(r'[a-z0-9]+',title.lower()))
        rows.append(dict(category=source['category'],title=title,url=canonical_url(link),
                         event_id='feed:'+hashlib.sha256(normalized_title.encode()).hexdigest()[:20],
                         publisher=source['name'],feed_url=source['url'],published_at=published(date),
                         raw_publication=date,description=plain(description),injection_flags=flags,
                         evidence_tier='publisher_feed_summary'))
    return rows


def shortlist(rows,start,end,store=None,limit=12):
    counts=dict(outside_window=0,undated=0,duplicates=0,already_delivered=0,quarantined=0)
    selected=[];urls=set();titles=set();events=set()
    old_titles={' '.join(re.findall(r'[a-z0-9]+',r.get('title','').lower())) for r in store.story_context()} if store else set()
    def rank(row):
        text=(row['title']+' '+row['description']).lower()
        words=('agent','retrieval','rag','bank','fraud','payment','risk','compliance','model','llm','artificial intelligence')
        return sum(2 for word in words if word in text)
    for row in sorted(rows,key=rank,reverse=True):
        if row['injection_flags']:counts['quarantined']+=1;continue
        if not row['published_at']:counts['undated']+=1;continue
        if not start<=stamp(row['published_at'])<end:counts['outside_window']+=1;continue
        title=' '.join(re.findall(r'[a-z0-9]+',row['title'].lower()))
        if store and (store.seen('url:'+row['url'],row['event_id'],'') or title in old_titles):
            counts['already_delivered']+=1;continue
        if row['url'] in urls or title in titles or row['event_id'] in events:
            counts['duplicates']+=1;continue
        urls.add(row['url']);titles.add(title);events.add(row['event_id']);selected.append(row)
    # Reserve capacity for both news sections before filling remaining slots.
    chosen=[]
    for category in ('ai','fintech'):chosen.extend([row for row in selected if row['category']==category][:limit//2])
    chosen.extend(row for row in selected if row not in chosen)
    return chosen[:limit],counts


def discover(folder,start,end,store=None):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    def fetch(source):
        name=re.sub(r'[^a-z0-9]+','-',source['name'].lower())
        try:
            request=Request(source['url'],headers={'User-Agent':'HermesBriefingReview/1'})
            with build_opener(SafeRedirect()).open(request,timeout=20) as response:
                raw=response.read(4_000_001)
            (folder/(name+'.xml')).write_bytes(raw)
            rows=parse_feed(raw,source)
            return rows,dict(source=source['name'],url=source['url'],parsed=len(rows),sha256=hashlib.sha256(raw).hexdigest(),status='parsed')
        except Exception as exc:return [],dict(source=source['name'],url=source['url'],status='failed',error=type(exc).__name__)
    with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(fetch,FEEDS))
    rows=[row for batch,_ in results for row in batch]
    selected,counts=shortlist(rows,start,end,store=store)
    report=dict(window_start=start.isoformat(),window_end=end.isoformat(),grace_minutes=0,
                sources=[state for _,state in results],parsed_total=len(rows),shortlisted=len(selected),counts=counts,
                quarantined=[dict(title=row['title'],url=row['url'],flags=row['injection_flags']) for row in rows if row['injection_flags']])
    (folder/'discovery.json').write_text(json.dumps(dict(report=report,candidates=selected),indent=2),encoding='utf-8')
    return selected,report
