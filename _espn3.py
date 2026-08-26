# -*- coding: utf-8 -*-
import sys, io, json, requests, unicodedata, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
BASE = 'https://site.api.espn.com/apis/site/v2/sports/soccer'

def norm(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '', s.lower())

def pull(lg, dt):
    u = '%s/%s/scoreboard?dates=%s' % (BASE, lg, dt)
    try:
        r = requests.get(u, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        if r.status_code != 200: return None, r.status_code
        d = r.json(); out = []
        for ev in d.get('events') or []:
            try:
                comp = ev['competitions'][0]
                teams = {t['homeAway']: t['team']['displayName'] for t in comp['competitors']}
                scores = {t['homeAway']: t.get('score') for t in comp['competitors']}
                st = ev.get('status', {}).get('type', {}).get('state')
                out.append((teams.get('home'), teams.get('away'), scores.get('home'), scores.get('away'), st))
            except Exception: pass
        return out, 200
    except Exception as e:
        return None, repr(e)[:80]

# 英联杯全部对阵 (找 Sheffield Wednesday)
for dt in ('20260825', '20260826'):
    evs, st = pull('eng.league_cup', dt)
    print('=== eng.league_cup', dt, st, 'n=', len(evs) if evs else 0)
    if evs:
        for h, a, hs, as_, s in evs:
            if 'sheffield' in norm(h) or 'wolverhampton' in norm(h) or 'wolves' in norm(h) or 'sheffield' in norm(a) or 'wolverhampton' in norm(a) or 'wolves' in norm(a):
                print('  **', h, 'vs', a, hs, as_, s)
            print('   ', h, 'vs', a, hs, as_, s)

# 巴乙全部 (找 CRB / Juventude)
for dt in ('20260825', '20260826'):
    evs, st = pull('bra.2', dt)
    print('=== bra.2', dt, st, 'n=', len(evs) if evs else 0)
    if evs:
        for h, a, hs, as_, s in evs:
            if 'crb' in norm(h) or 'juventude' in norm(h) or 'crb' in norm(a) or 'juventude' in norm(a):
                print('  **', h, 'vs', a, hs, as_, s)

# 哥甲 (找 Cúcuta / Alianza)
for dt in ('20260825', '20260826'):
    evs, st = pull('col.1', dt)
    print('=== col.1', dt, st, 'n=', len(evs) if evs else 0)
    if evs:
        for h, a, hs, as_, s in evs:
            if 'cucuta' in norm(h) or 'alianza' in norm(h) or 'cucuta' in norm(a) or 'alianza' in norm(a):
                print('  **', h, 'vs', a, hs, as_, s)
            print('   ', h, 'vs', a, hs, as_, s)

# 巴西杯 code 变体
for code in ('bra.cup', 'br.cup', 'bra.copa_brasil', 'br.1', 'bra.1'):
    evs, st = pull(code, '20260825')
    print('=== 巴西杯', code, st, 'n=', len(evs) if evs else 0)
    if evs:
        for h, a, hs, as_, s in evs:
            if 'cruzeiro' in norm(h) or 'mineiro' in norm(h) or 'cruzeiro' in norm(a) or 'mineiro' in norm(a):
                print('  **', h, 'vs', a, hs, as_, s)
