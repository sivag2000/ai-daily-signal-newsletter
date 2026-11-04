"""Bounded official arXiv Atom fallback; publication metadata retained with raw XML."""
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
import xml.etree.ElementTree as ET
import re
from urllib.parse import urlencode
from digest import stamp

QUERY='(cat:cs.AI OR cat:cs.CL OR cat:cs.LG) AND (all:agent OR all:retrieval OR all:evaluation OR all:fraud OR all:banking)'
URL='https://export.arxiv.org/api/query?'+urlencode(dict(search_query=QUERY,start=0,max_results=20,sortBy='submittedDate',sortOrder='descending'))
TERMS={'retrieval':5,'rag':5,'agent':4,'agentic':4,'evaluation':3,'fraud':5,'banking':5,'financial':4,'tool use':4}


def relevance(title,abstract):
    text=(title+' '+abstract).lower()
    if any(word in text for word in ('diabet','physiolog','clinical','healthcare','patient','robot','locomotion')):
        return 0,[]
    tags=[term for term in TERMS if re.search(r'\b'+re.escape(term)+r'\b',text)]
    score=sum(TERMS[term] for term in tags)
    if any(word in text for word in ('robot','manipulation','locomotion')):score-=8
    return score,tags


def collect_paper(folder,start,end):
    folder=Path(folder)
    with urlopen(Request(URL,headers={'User-Agent':'HermesBriefingReview/1'}),timeout=25) as response:
        raw=response.read(1_000_001)
        if len(raw)>1_000_000:raise ValueError('Oversized paper feed')
    (folder/'arxiv-original.xml').write_bytes(raw)
    namespace={'a':'http://www.w3.org/2005/Atom'}
    tree=ET.fromstring(raw)
    ranked=[]
    for entry in tree.findall('a:entry',namespace):
        read=lambda key:' '.join((entry.findtext('a:'+key,default='',namespaces=namespace)).split())
        url,published,title,abstract=(read(k) for k in ('id','published','title','summary'))
        if not url.startswith(('http://arxiv.org/abs/','https://arxiv.org/abs/')) or not abstract:
            continue
        if not start <= stamp(published)<end:continue
        score,tags=relevance(title,abstract)
        if score<3:continue
        paper_id='arxiv:'+url.rsplit('/',1)[-1]
        key='official-atom:'+paper_id
        sentences=re.split(r'(?<=[.!?])\s+',abstract)
        excerpt=sentences[0]
        for sentence in sentences[1:]:
            if len(excerpt)+len(sentence)+1>650:break
            excerpt+=' '+sentence
        if len(excerpt)>900:excerpt=abstract[:650]+'…'
        # Evidence excerpt must remain an actual substring even when displayed summary is shortened.
        quote=excerpt.removesuffix('…')
        item=dict(category='paper',title=title,url=url,event_id=paper_id,published_at=published,
                  precision='timestamp',publication_excerpt=published,claim_excerpt=quote,
                  summary='Abstract-only preprint overview: '+abstract,
                  why='Matches your research interests: '+', '.join(tags)+'. These are author-reported claims, not independently reproduced findings.',
                  takeaway='Use this as an offline benchmark-reading candidate. Full experimental methods and limitations require full-paper review before adoption.',
                  evidence_id=key,score=score,paper_id=paper_id,preprint=True)
        ranked.append((score,item,dict(url=url,content='Published: '+published+'\nTitle: '+title+'\nAbstract: '+abstract,
                     source_api=URL,raw_evidence='arxiv-original.xml')))
    if ranked:
        _,item,evidence=max(ranked,key=lambda row:row[0])
        return dict(items=[item],extracts={item['evidence_id']:evidence},coverage_complete=False,
                    gaps=['paper: relevance-ranked official-feed sample; not comprehensive coverage'])
    return dict(items=[],extracts={},coverage_complete=False,
                gaps=['paper: official feed contained no sufficiently relevant recent preprint in the fixed window'])
