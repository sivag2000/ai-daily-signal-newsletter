import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from hermes_adapter import session_extracts


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.db = sqlite3.connect(self.home / 'state.db')
        self.addCleanup(self.db.close)
        self.db.execute('CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, tool_calls TEXT, tool_name TEXT, tool_call_id TEXT)')

    def call(self, cid, name, args):
        calls = json.dumps([dict(id=cid, function=dict(name=name, arguments=json.dumps(args)))])
        self.db.execute('INSERT INTO messages(session_id,role,tool_calls) VALUES (?,?,?)', ('s1','assistant',calls))
        self.db.commit()

    def result(self, cid, name, body):
        self.db.execute('INSERT INTO messages(session_id,role,content,tool_name,tool_call_id) VALUES (?,?,?,?,?)',
                        ('s1','tool',json.dumps(body),name,cid))
        self.db.commit()

    def test_canonical_extraction(self):
        self.call('s', 'web_search', dict(query='AI',limit=10))
        self.result('s','web_search',dict(data=dict(web=[dict(url='https://openai.com/news/a')])))
        self.call('e','web_extract',dict(urls=['https://openai.com/news/a']))
        self.result('e','web_extract',dict(results=[dict(url='https://openai.com/news/a',content='Evidence')]))
        self.assertEqual(len(session_extracts(self.home,'s1')), 1)

    def test_missing_return_rejected(self):
        self.call('s','web_search',dict(query='AI',limit=10))
        with self.assertRaises(ValueError):
            session_extracts(self.home,'s1')

    def test_configured_seed_is_valid_discovery(self):
        self.call('e','web_extract',dict(urls=['https://openai.com/news/']))
        self.result('e','web_extract',dict(results=[dict(url='https://openai.com/news/',content='News index')]))
        self.assertEqual(len(session_extracts(self.home,'s1',seed_urls=['https://openai.com/news/'])),1)

    def test_explicit_link_from_prior_extract_is_valid(self):
        self.call('e','web_extract',dict(urls=['https://openai.com/news/']))
        self.result('e','web_extract',dict(results=[dict(url='https://openai.com/news/',
            content='[Article](https://openai.com/news/article)')]))
        self.call('a','web_extract',dict(urls=['https://openai.com/news/article']))
        self.result('a','web_extract',dict(results=[dict(url='https://openai.com/news/article',content='Article')]))
        self.assertEqual(len(session_extracts(self.home,'s1',seed_urls=['https://openai.com/news/'])),2)

    def test_unexpected_tool_rejected(self):
        self.call('x','terminal',dict(command='ignored'))
        with self.assertRaises(ValueError):
            session_extracts(self.home,'s1')

    def test_undiscovered_url_rejected(self):
        self.call('e','web_extract',dict(urls=['https://example.com']))
        with self.assertRaises(ValueError):
            session_extracts(self.home,'s1')

    def test_review_cannot_search(self):
        self.call('s','web_search',dict(query='AI',limit=10))
        self.result('s','web_search',dict(data=dict(web=[])))
        with self.assertRaises(ValueError):
            session_extracts(self.home,'s1',search_cap=0)


if __name__ == '__main__':
    unittest.main()
