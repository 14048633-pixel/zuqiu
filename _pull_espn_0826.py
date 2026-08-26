# -*- coding: utf-8 -*-
import sys, os, io, json, re, unicodedata, requests
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = r'D:\足球分析'
BASE = 'https://site.api.espn.com/apis/site/v2/sports/soccer'

def norm(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '', s.lower())

LEAGUES = ['eng.1', 'eng.2', 'eng.3', 'eng.4', 'eng.league_cup', 'esp.1', 'uefa.champions',
           'sau.1', 'bra.2', 'bra.cup', 'conmebol.libertadores', 'col.1', 'intl.friendly']
DATES = ['20260825', '20260826']

all_events = []
for lg in LEAGUES:
    for dt in DATES:
        u = '%s/%s/scoreboard?dates=%s' % (BASE, lg, dt)
        try:
            r = requests.get(u, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
            if r.status_code != 200:
                print('%-18s %s HTTP %s' % (lg, dt, r.status_code)); continue
            d = r.json()
            evs = d.get('events') or []
            if not evs:
                print('%-18s %s n=0' % (lg, dt)); continue
            print('%-18s %s n=%d' % (lg, dt, len(evs)))
            for ev in evs:
                try:
                    comp = ev['competitions'][0]
                    teams = {}
                    scores = {}
                    for t in comp['competitors']:
                        teams[t['homeAway']] = t['team']['displayName']
                        scores[t['homeAway']] = t.get('score')
                    st = ev.get('status', {}).get('type', {}).get('state', '')  # pre/in/post
                    ko = ev.get('date', '')
                    all_events.append({'lg': lg, 'h': teams.get('home'), 'a': teams.get('away'),
                                       'hs': scores.get('home'), 'as': scores.get('away'), 'st': st, 'ko': ko})
                except Exception:
                    pass
        except Exception as e:
            print('%-18s %s ERR %s' % (lg, dt, repr(e)[:100]))
print('total espn events:', len(all_events))

# 去重
seen = set(); ev2 = []
for e in all_events:
    k = (norm(e['h']), norm(e['a']), e['lg'], e['ko'])
    if k in seen: continue
    seen.add(k); ev2.append(e)
all_events = ev2
print('after dedup:', len(all_events))

scan = json.load(io.open(os.path.join(ROOT, 'analysis_records', 'scan_next24h_20260825_1644.json'), encoding='utf-8'))
scan = scan if isinstance(scan, list) else scan.get('matches', [])

def ko_utc(m):
    s = m.get('ko_utc')
    if not s: return None
    try: return datetime.strptime(s, '%Y-%m-%dT%H:%M:%S%z')
    except Exception: return None

def find(h, a, ko):
    nh, na = norm(h), norm(a)
    out = []
    for e in all_events:
        eh, ea = norm(e['h']), norm(e['a'])
        if not eh or not ea: continue
        sc = 0
        if nh == eh and na == ea: sc = 100
        else:
            if nh and (nh in eh or eh in nh): sc += 30
            if na and (na in ea or ea in na): sc += 30
            if nh[:6] == eh[:6]: sc += 8
            if na[:6] == ea[:6]: sc += 8
        if sc < 60: continue
        out.append((sc, e))
    out.sort(key=lambda x: -x[0])
    return out

res = []
for m in scan:
    ko = ko_utc(m)
    cands = find(m.get('home'), m.get('away'), ko)
    row = {'ko_bjt': m.get('ko_bjt'), 'league': m.get('league'), 'home': m.get('home'), 'away': m.get('away'),
           'best': (m.get('best_bet') or {}).get('name'), 'best_ev': (m.get('best_bet') or {}).get('ev'),
           'vetoed': bool(m.get('vetoed')), 'score': None, 'status': None, 'source': None}
    if cands:
        c0 = cands[0]
        if c0[0] >= 100 and c0[1]['hs'] is not None:
            row['score'] = '%d-%d' % (int(c0[1]['hs']), int(c0[1]['as'])); row['source'] = 'ESPN'
            row['status'] = c0[1]['st']
            row['match_lg'] = c0[1]['lg']
    res.append(row)

matched = sum(1 for r in res if r['score'])
print('matched:', matched, '/', len(res))
print('== matched by league ==')
from collections import Counter
print(dict(Counter(r['league'] for r in res if r['score'])))
print('== missing ==')
for r in res:
    if r['score']: continue
    print('  ', r['ko_bjt'], r['league'], r['home'], 'vs', r['away'])
print('== matched detail ==')
for r in res:
    if r['score']:
        print('  ', r['ko_bjt'], r['league'], r['home'], 'vs', r['away'], r['score'], r['status'], r.get('match_lg'), r['source'])

of = os.path.join(ROOT, 'analysis_records', 'results_scan_20260826_espn.json')
io.open(of, 'w', encoding='utf-8').write(json.dumps(res, ensure_ascii=False, indent=1))
print('saved ->', of)
