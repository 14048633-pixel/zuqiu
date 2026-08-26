# -*- coding: utf-8 -*-
import json, io, sys, re, unicodedata, time, collections
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import requests
BASE = 'https://sports.bzzoiro.com'
env = {}
for l in io.open('D:/足球分析/.env', encoding='utf-8-sig'):
    if '=' in l and not l.strip().startswith('#'):
        k, v = l.split('=', 1); v = v.split('#')[0].strip().strip('"').strip("'")
        env[k.strip()] = v
H = {'User-Agent': 'Mozilla/5.0', 'Authorization': 'Token ' + env['BZZOIRO_API_KEY']}
LEAGUE_IDS = {'土超':11,'意甲':4,'巴甲':9,'巴乙':34,'西甲':3,'西乙':38,'波甲':25,'中超':52,
 '瑞超':26,'丹超':84,'英超':1,'德国杯':43,'比甲':14,'葡超':2,'芬超':55,'荷甲':10,'J1':49,
 '英冠':12,'英乙':87,'美职':18,'法甲':6,'法乙':89,'德甲':5,'阿甲':85,'墨超':19,'挪超':54,
 'K联赛':50,'俄超':None,'希腊超':24,'智利甲':None,'意乙':None,'瑞甲':None,'解放者杯':32,'南美杯':33}
def deaccent(s):
    s = unicodedata.normalize('NFKD', s or '')
    return ''.join(c for c in s if not unicodedata.combining(c))
def tokens(s):
    return set(re.findall(r'[a-z]{3,}', deaccent(s).lower()))
def bsd_events(lid, d1, d2):
    out, off = [], 0
    while True:
        u = (BASE + '/api/v2/events/?league_id=%d&status=finished&date_from=%s&date_to=%s&limit=100&offset=%d' % (lid, d1, d2, off))
        d = requests.get(u, headers=H, timeout=40).json()
        rows = d.get('results') or []
        out.extend(rows)
        if not d.get('next') or not rows: break
        off += len(rows)
    return out
# 收集预测场次
recs = []
def add(lg, h, a, ct):
    recs.append({'league': lg, 'home': h, 'away': a, 'ct': ct})
for f in ('scan24h_analysis_20260822_0139.json','scan24h_analysis_20260822_0141.json','scan24h_analysis_20260822_2046.json','scan24h_analysis_20260822_2136.json','scan24h_analysis_20260823_1824.json'):
    try:
        d = json.load(io.open(r'analysis_records/'+f, encoding='utf-8'))
    except Exception as e:
        print(f, 'ERR', e); continue
    for m in d.get('matches', []):
        if m.get('direction') or m.get('best_bet') or (m.get('result') or {}).get('direction'):
            add(m['league'], m['home'], m['away'], m.get('ct') or m.get('kickoff') or '')
# scan_upcoming 昨晚 (仅未来/已结算窗口)
d = json.load(io.open(r'analysis_records/20260823_scan_upcoming.json', encoding='utf-8'))
for m in d['matches']:
    add(m['league'], m['home'], m['away'], m.get('ct') or '')
print('预测场次合计:', len(recs))
# 去重
seen = set(); uniq = []
for r in recs:
    k = (r['league'], r['home'], r['away'])
    if k in seen: continue
    seen.add(k); uniq.append(r)
print('去重后:', len(uniq))
# BSD 拉比分
lids = {LEAGUE_IDS[r['league']] for r in uniq if LEAGUE_IDS.get(r['league'])}
ev_idx = {}
for lid in sorted(x for x in lids if x):
    try: ev_idx[lid] = bsd_events(lid, '2026-08-15', '2026-08-26')
    except Exception as e: print('ERR lid', lid, repr(e)[:60])
    time.sleep(0.2)
def find_score(r):
    lid = LEAGUE_IDS.get(r['league'])
    if not lid: return None
    hk, ak = tokens(r['home']), tokens(r['away'])
    for ev in ev_idx.get(lid, []):
        h = ev.get('home_team') or ''; a = ev.get('away_team') or ''
        th, ta = tokens(h), tokens(a)
        if th and ta and (th <= hk or hk <= th) and (ta <= ak or ak <= ta):
            hs, as_ = ev.get('home_score'), ev.get('away_score')
            if hs is not None and as_ is not None:
                return (int(hs), int(as_))
    return None
miss = []
for r in uniq:
    sc = find_score(r)
    if sc is None:
        miss.append(r)
print('缺结果:', len(miss))
by = collections.Counter(r['league'] for r in miss)
print('按联赛:', dict(by.most_common(30)))
io.open('_miss_list.json','w',encoding='utf-8').write(json.dumps(miss, ensure_ascii=False, indent=1))
print('saved _miss_list.json')
