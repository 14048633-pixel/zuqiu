# -*- coding: utf-8 -*-
import sys, os, io, json, re, unicodedata
from datetime import datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'prediction_v2'); sys.path.insert(0, '.')
import bsd_extra

ROOT = r'D:\足球分析'

def norm(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '', s.lower())

def ev_team(e, side):
    v = e.get('home_team' if side == 'h' else 'away_team')
    if isinstance(v, dict): return v.get('name') or ''
    if isinstance(v, str): return v
    return ''

def ev_score(e):
    hs = e.get('home_score'); as_ = e.get('away_score')
    if hs is None or as_ is None:
        s = e.get('scores') or {}
        hs = hs if hs is not None else s.get('home')
        as_ = as_ if as_ is not None else s.get('away')
    return hs, as_

def ev_ko(e):
    s = e.get('starts_at') or e.get('kickoff') or e.get('ko_utc') or ''
    if isinstance(s, str):
        for fmt in ('%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d %H:%M:%S'):
            try: return datetime.strptime(s, fmt)
            except Exception: pass
    return None

def ko_dt(s):
    if not s: return None
    try: return datetime.strptime(s, '%Y-%m-%dT%H:%M:%S%z')
    except Exception: return None

# 强制重拉(不走缓存)
events = []
for d in ('2026-08-25', '2026-08-26'):
    ev = bsd_extra.fetch_events(d, tries=3)
    if ev is None:
        print('BSD FAILED', d); continue
    events.extend(ev)
    print('BSD fetched', d, len(ev))

# 去重
seen = set(); ev2 = []
for e in events:
    k = (norm(ev_team(e,'h')), norm(ev_team(e,'a')), norm(str(e.get('league_name') or e.get('league') or '')), norm(str(ev_score(e))), norm(str(e.get('status'))))
    if k in seen: continue
    seen.add(k); ev2.append(e)
print('after dedup:', len(ev2))
events = ev2

base = json.load(io.open(os.path.join(ROOT, 'analysis_records', 'results_scan_20260826_final.json'), encoding='utf-8'))

def find(h, a, ko):
    nh, na = norm(h), norm(a)
    out = []
    for e in events:
        eh, ea = norm(ev_team(e,'h')), norm(ev_team(e,'a'))
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
        out.append((sc, tdiff, ev_team(e,'h'), ev_team(e,'a'), lg, hs, as_, e.get('status')))
    out.sort(key=lambda x: (-x[0], x[1]))
    return out

upd = 0
for r in base:
    ko = ko_dt(r.get('ko_utc') or '')
    cands = find(r.get('home'), r.get('away'), ko)
    if cands:
        c0 = cands[0]
        if c0[0] >= 100 and c0[5] is not None:
            r['score'] = '%d-%d' % (int(c0[5]), int(c0[6]))
            r['status'] = c0[7]
            r['source'] = 'BSD'
            upd += 1

from collections import Counter
print('updated:', upd)
print(Counter((x.get('status') or 'None') for x in base))
final = sum(1 for x in base if x.get('score') and x.get('status') in ('post','finished','FT','AET','PEN'))
print('final(终局):', final, '/ 68')
print('--- still live:')
for r in base:
    if r.get('score') and r.get('status') not in ('post','finished','FT','AET','PEN'):
        print('  ', r.get('status'), r.get('ko_bjt'), r.get('league'), r.get('home'), 'vs', r.get('away'), '|', r.get('score'))
print('--- no data:')
for r in base:
    if not r.get('score'):
        print('  ', r.get('ko_bjt'), r.get('league'), r.get('home'), 'vs', r.get('away'))

of = os.path.join(ROOT, 'analysis_records', 'results_scan_20260826_final2.json')
io.open(of, 'w', encoding='utf-8').write(json.dumps(base, ensure_ascii=False, indent=1))
print('saved ->', of)
