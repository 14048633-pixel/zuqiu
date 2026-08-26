# -*- coding: utf-8 -*-
import sys, os, io, json, re, unicodedata, requests
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

# ---------- 1) BSD 重拉(天皇杯应FT) ----------
rawf = os.path.join(ROOT, 'analysis_records', 'events_20260826_raw.json')
if os.path.exists(rawf):
    os.remove(rawf)
events = []
for d in ('2026-08-25', '2026-08-26'):
    ev = bsd_extra.fetch_events(d, tries=2)
    if ev is None: print('BSD FAILED', d); continue
    events.extend(ev)
io.open(rawf, 'w', encoding='utf-8').write(json.dumps(events, ensure_ascii=False))
print('BSD refetch total:', len(events))

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

seen = set(); ev2 = []
for e in events:
    k = (norm(ev_team(e, 'h')), norm(ev_team(e, 'a')), norm(str(ev_score(e))), norm(str(e.get('status'))))
    if k in seen: continue
    seen.add(k); ev2.append(e)
events = ev2

def bsd_find(h, a, ko):
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
        if sc < 100: continue
        ek = ev_ko(e)
        tdiff = 0.0
        if ko and ek:
            d1 = ko.replace(tzinfo=None) if ko.tzinfo else ko
            d2 = ek.replace(tzinfo=None) if ek.tzinfo else ek
            tdiff = abs((d2 - d1).total_seconds()) / 3600.0
        if tdiff > 6: continue
        hs, as_ = ev_score(e)
        out.append((sc, hs, as_, e.get('status')))
    out.sort(key=lambda x: -x[0])
    return out[0] if out else None

# ---------- 2) scan + ESPN 已有 ----------
scan = json.load(io.open(os.path.join(ROOT, 'analysis_records', 'scan_next24h_20260825_1644.json'), encoding='utf-8'))
scan = scan if isinstance(scan, list) else scan.get('matches', [])
espn_res = json.load(io.open(os.path.join(ROOT, 'analysis_records', 'results_scan_20260826_espn.json'), encoding='utf-8'))
espn_by_key = {}
for r in espn_res:
    if r.get('score'):
        espn_by_key[(norm(r['home']), norm(r['away']))] = r

# 欧冠/沙超 补充 (ESPN 已确认 post)
extra = {('sabahfkhapoe lbee rsheva',): None}  # 占位, 用下述列表
EXTRA = [
    ('Sabah FK', 'Hapoel Be\u2019er Sheva', '5-2', 'ESPN-UCLQ'),
    ('Bod\u00f8/Glimt', 'NEC Nijmegen', '3-0', 'ESPN-UCLQ'),
    ('LASK', 'Celtic', '5-1', 'ESPN-UCLQ'),
    ('Al-Ettifaq', 'Al-Nassr', '2-3', 'ESPN-KSA'),
    ('Al-Shabab', 'Al-Riyadh', '3-3', 'ESPN-KSA'),
]

# ---------- 3) 合并 ----------
out = []
for m in scan:
    ko = ko_utc(m)
    h, a = m.get('home'), m.get('away')
    row = {'ko_bjt': m.get('ko_bjt'), 'league': m.get('league'), 'home': h, 'away': a,
           'best': (m.get('best_bet') or {}).get('name'), 'best_ev': (m.get('best_bet') or {}).get('ev'),
           'star': (m.get('best_bet') or {}).get('star'), 'vetoed': bool(m.get('vetoed')),
           'direction': m.get('direction'), 'score': None, 'status': None, 'source': None}
    # 1) BSD
    b = bsd_find(h, a, ko)
    if b and b[1] is not None:
        row['score'] = '%d-%d' % (int(b[1]), int(b[2])); row['status'] = b[3]; row['source'] = 'BSD'
    # 2) ESPN 已匹配
    if not row['score']:
        e = espn_by_key.get((norm(h), norm(a)))
        if e:
            row['score'] = e['score']; row['status'] = e.get('status'); row['source'] = 'ESPN'
    # 3) 硬编码补充
    if not row['score']:
        for eh, ea, sc, src in EXTRA:
            if norm(eh) == norm(h) and norm(ea) == norm(a):
                row['score'] = sc; row['status'] = 'post'; row['source'] = src
    out.append(row)

matched = sum(1 for r in out if r['score'])
final_ok = sum(1 for r in out if r['score'] and r['status'] in ('FT', 'AET', 'PEN', 'post', 'finished'))
print('matched:', matched, '/', len(out), '| final:', final_ok)
print()
print('== still missing ==')
for r in out:
    if r['score']: continue
    print('  ', r['ko_bjt'], r['league'], r['home'], 'vs', r['away'])
print()
print('== live (非终局) ==')
for r in out:
    if r['score'] and r['status'] and r['status'] not in ('FT', 'AET', 'PEN', 'post', 'finished'):
        print('  ', r['ko_bjt'], r['league'], r['home'], 'vs', r['away'], r['score'], r['status'])
print()
print('== BEST 4 ==')
for r in out:
    if r['best']:
        print('  ', r['ko_bjt'], r['league'], r['home'], 'vs', r['away'], '| best:', r['best'], 'EV%', round((r['best_ev'] or 0)*100, 1), '| 比分:', r['score'], r['status'])

of = os.path.join(ROOT, 'analysis_records', 'results_scan_20260826_final.json')
io.open(of, 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=1))
print('saved ->', of)
