# -*- coding: utf-8 -*-
import sys, os, io, json, re, unicodedata
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'prediction_v2'); sys.path.insert(0, '.')
import bsd_extra

ROOT = r'D:\足球分析'

def norm(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '', s.lower())

def ko_utc(m):
    s = m.get('ko_utc')
    if not s: return None
    try: return datetime.strptime(s, '%Y-%m-%dT%H:%M:%S%z')
    except Exception: return None

def ev_team(e, side):
    v = e.get('home_team' if side == 'h' else 'away_team')
    if isinstance(v, dict): return v.get('name') or ''
    if isinstance(v, str): return v
    return ''

def ev_ko(e):
    s = e.get('kickoff') or e.get('ko_utc') or e.get('starts_at') or ''
    if isinstance(s, str):
        for fmt in ('%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d %H:%M:%S'):
            try: return datetime.strptime(s, fmt)
            except Exception: pass
    return None

def ev_score(e):
    hs = e.get('home_score'); as_ = e.get('away_score')
    if hs is None or as_ is None:
        s = e.get('scores') or {}
        hs = hs if hs is not None else s.get('home')
        as_ = as_ if as_ is not None else s.get('away')
    if hs is None or as_ is None:
        ss = e.get('score')
        if ss and '-' in str(ss):
            p = str(ss).split('-')
            if len(p) == 2: hs, as_ = p[0], p[1]
    return hs, as_

# 用本地缓存(若存在), 否则重拉
rawf = os.path.join(ROOT, 'analysis_records', 'events_20260826_raw.json')
if os.path.exists(rawf):
    events = json.load(io.open(rawf, encoding='utf-8'))
    print('loaded cached events:', len(events))
else:
    events = []
    for d in ('2026-08-25', '2026-08-26'):
        ev = bsd_extra.fetch_events(d, tries=2)
        if ev is None: print('BSD FAILED', d); continue
        events.extend(ev)
        print('BSD fetched', d, len(ev))
    io.open(rawf, 'w', encoding='utf-8').write(json.dumps(events, ensure_ascii=False))
    print('BSD total:', len(events))

# 去重(按 home|away|league|score|status)
seen = set(); ev2 = []
for e in events:
    k = (norm(ev_team(e, 'h')), norm(ev_team(e, 'a')), norm(str(e.get('league_name') or e.get('league') or '')),
         norm(str(ev_score(e))), norm(str(e.get('status'))))
    if k in seen: continue
    seen.add(k); ev2.append(e)
print('after dedup:', len(ev2))
events = ev2

scan = json.load(io.open(os.path.join(ROOT, 'analysis_records', 'scan_next24h_20260825_1644.json'), encoding='utf-8'))
scan = scan if isinstance(scan, list) else scan.get('matches', [])

def find(h, a, ko):
    nh, na = norm(h), norm(a)
    out = []
    for e in events:
        eh, ea = norm(ev_team(e, 'h')), norm(ev_team(e, 'a'))
        if not eh or not ea: continue
        sc = 0
        if nh == eh and na == ea: sc = 100
        else:
            if nh and (nh in eh or eh in nh): sc += 30
            if na and (na in ea or ea in na): sc += 30
            if nh[:6] == eh[:6]: sc += 8
            if na[:6] == ea[:6]: sc += 8
        if sc < 60: continue
        ek = ev_ko(e)
        tdiff = 0.0
        if ko and ek:
            d1 = ko.replace(tzinfo=None) if ko.tzinfo else ko
            d2 = ek.replace(tzinfo=None) if ek.tzinfo else ek
            tdiff = abs((d2 - d1).total_seconds()) / 3600.0
        if tdiff > 6: continue
        hs, as_ = ev_score(e)
        lg = e.get('league_name') or e.get('league') or ''
        if isinstance(lg, dict): lg = lg.get('name') or ''
        out.append((sc, tdiff, ev_team(e, 'h'), ev_team(e, 'a'), lg, hs, as_, e.get('status')))
    out.sort(key=lambda x: (-x[0], x[1]))
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
        if c0[0] >= 100 and c0[5] is not None:
            row['score'] = '%d-%d' % (int(c0[5]), int(c0[6])); row['source'] = 'BSD'; row['status'] = c0[7]
    res.append(row)

matched = sum(1 for r in res if r['score'])
print('matched:', matched, '/', len(res))
print('== by league (matched) ==')
from collections import Counter
print(dict(Counter(r['league'] for r in res if r['score'])))
print()
print('== missing ==')
for r in res:
    if r['score']: continue
    print('  ', r['ko_bjt'], r['league'], r['home'], 'vs', r['away'])
print()
print('== matched with live status (需等完赛重拉) ==')
for r in res:
    if r['score'] and r['status'] and r['status'] not in ('FT', 'AET', 'PEN', 'finished'):
        print('  ', r['ko_bjt'], r['league'], r['home'], 'vs', r['away'], r['score'], r['status'])

of = os.path.join(ROOT, 'analysis_records', 'results_scan_20260826_v2.json')
io.open(of, 'w', encoding='utf-8').write(json.dumps(res, ensure_ascii=False, indent=1))
print('saved ->', of)
