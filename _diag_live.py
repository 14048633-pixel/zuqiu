import json
from datetime import datetime, timezone
d = json.load(open('_replay_live_feature_out.json', encoding='utf-8'))
def pdt(s):
    try:
        x = datetime.fromisoformat(str(s).replace('Z', '+00:00'))
        if x.tzinfo is None: x = x.replace(tzinfo=timezone.utc)
        return x
    except Exception: return None
h_early, h_live = [], []
for x in d:
    e, l = x.get('early') or {}, x.get('live') or {}
    ct = pdt(x.get('kickoff'))
    es, ls = pdt(e.get('snap')), pdt(l.get('snap'))
    if es and ct: h_early.append(round((ct - es).total_seconds() / 3600, 1))
    if ls and ct: h_live.append(round((ct - ls).total_seconds() / 3600, 1))
if h_early: print('早盘快照距开赛h: avg', round(sum(h_early)/len(h_early),1), 'min', min(h_early), 'max', max(h_early))
if h_live: print('临场快照距开赛h: avg', round(sum(h_live)/len(h_live),1), 'min', min(h_live), 'max', max(h_live))
from collections import Counter
e_nobest, l_nobest = [], []
for x in d:
    e, l = x.get('early') or {}, x.get('live') or {}
    if not e.get('best'): e_nobest.append((e.get('veto_reason'), (e.get('risk_tags') or [])[:2]))
    if not l.get('best'): l_nobest.append((l.get('veto_reason'), (l.get('risk_tags') or [])[:2]))
print()
print('early无best n:', len(e_nobest), Counter(str(x[0]) for x in e_nobest))
print('live无best n:', len(l_nobest), Counter(str(x[0]) for x in l_nobest))
print('early无best 样例(前8):')
for t in e_nobest[:8]: print('  ', t)
print('live无best 样例(前8):')
for t in l_nobest[:8]: print('  ', t)
