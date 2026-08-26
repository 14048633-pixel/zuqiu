# -*- coding: utf-8 -*-
import sys, os, io, json, re, unicodedata, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
BASE = 'https://site.api.espn.com/apis/site/v2/sports/soccer'

def norm(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '', s.lower())

# 1) 全足球 scoreboard
u = BASE + '/scoreboard?dates=20260825-20260826'
try:
    r = requests.get(u, headers={'User-Agent': 'Mozilla/5.0'}, timeout=40)
    print('global scoreboard:', r.status_code)
    d = r.json()
    evs = d.get('events') or []
    print('global events:', len(evs))
    for ev in evs[:10]:
        comp = ev['competitions'][0]
        le = (ev.get('league') or {}).get('slug') or ''
        teams = {t['homeAway']: t['team']['displayName'] for t in comp['competitors']}
        scores = {t['homeAway']: t.get('score') for t in comp['competitors']}
        st = ev.get('status', {}).get('type', {}).get('state')
        print('  ', le, '|', teams.get('home'), 'vs', teams.get('away'), '|', scores.get('home'), scores.get('away'), '|', st, '|', ev.get('date', '')[:16])
except Exception as e:
    print('global ERR', repr(e)[:150])

# 2) 额外 codes
extra = {'ksa.1': 'Saudi', 'bra.copa_brasil': 'BrazilCup', 'intl.friendly': 'Friendly',
         'uefa.cl_qual': 'UCLQual', 'uefa.champions_qual': 'UCLQ2', 'eng.3': 'L1'}
all_ev = []
for lg, tag in extra.items():
    for dt in ('20260825', '20260826'):
        try:
            r = requests.get('%s/%s/scoreboard?dates=%s' % (BASE, lg, dt), headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
            if r.status_code != 200:
                print(tag, lg, dt, 'HTTP', r.status_code); continue
            d = r.json(); evs = d.get('events') or []
            print(tag, lg, dt, 'n=', len(evs))
            for ev in evs:
                try:
                    comp = ev['competitions'][0]
                    teams = {t['homeAway']: t['team']['displayName'] for t in comp['competitors']}
                    scores = {t['homeAway']: t.get('score') for t in comp['competitors']}
                    st = ev.get('status', {}).get('type', {}).get('state')
                    all_ev.append({'h': teams.get('home'), 'a': teams.get('away'), 'hs': scores.get('home'),
                                   'as': scores.get('away'), 'st': st, 'lg': lg})
                except Exception:
                    pass
        except Exception as e:
            print(tag, lg, dt, 'ERR', repr(e)[:100])
print('extra total:', len(all_ev))
for e in all_ev:
    print('  ', e['lg'], '|', e['h'], 'vs', e['a'], '|', e['hs'], e['as'], '|', e['st'])
