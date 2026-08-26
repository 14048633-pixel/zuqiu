# -*- coding: utf-8 -*-
import json, io, sys, requests, re, unicodedata, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ROOT = r"D:\足球分析"
env = {}
for l in io.open(os.path.join(ROOT, '.env'), encoding='utf-8-sig'):
    if '=' in l and not l.strip().startswith('#'):
        k, v = l.split('=', 1)
        v = v.split('#')[0].strip().strip('"').strip("'")
        env[k.strip()] = v
H = {'x-apisports-key': env['FOOTBALL_API_KEY']}
BASE = 'https://v3.football.api-sports.io/fixtures'

def _norm(s):
    s = unicodedata.normalize('NFKD', str(s or ''))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()

def _fuzzy(a, b):
    na, nb = _norm(a), _norm(b)
    if not na or not nb: return 0.0
    if na == nb: return 1.0
    wa, wb = set(na.split()), set(nb.split())
    if wa and wb and (wa <= wb or wb <= wa): return 0.9
    from difflib import SequenceMatcher
    return SequenceMatcher(None, na, nb).ratio()

targets = [
    ('FSV Mainz 05', 'Werder Bremen'),
    ('Brondby IF', 'Silkeborg IF'),
    ('Celta Vigo', 'Andorra CF'),
    ('Celta Fortuna', 'Andorra CF'),
    ('IFK Varnamo', 'Landskrona BoIS'),
    ('Ostersunds FK', 'Ljungskile SK'),
    ('IFK Norrkoping', 'Falkenbergs FF'),
    ('FC Baltika Kaliningrad', 'Rubin Kazan'),
    ('Kocaelispor', 'Amed SK'),
    ('Malaga', 'Deportivo La Coruna'),
    ('Everton de Vina del Mar', 'Universidad de Concepcion'),
    ('Jeju United FC', 'Pohang Steelers'),
    ('Sangju Sangmu FC', 'Jeonbuk Hyundai Motors'),
]

all_fx = []
for date in ['2026-08-24', '2026-08-25']:
    r = requests.get(BASE, headers=H, params={'date': date}, timeout=30)
    d = r.json()
    all_fx.extend(d.get('response') or [])
    print('date', date, '->', len(d.get('response') or []))
print('total:', len(all_fx))

results = []
for h, a in targets:
    best = None; bs = 0.0
    for f in all_fx:
        sh = _fuzzy(h, (f.get('teams') or {}).get('home', {}).get('name', ''))
        sa = _fuzzy(a, (f.get('teams') or {}).get('away', {}).get('name', ''))
        s = (sh + sa) / 2
        if s > bs:
            bs = s; best = f
    status = (best.get('fixture') or {}).get('status', {}).get('short') if best else None
    goals = best.get('goals', {}) if best else {}
    score = ('%s-%s' % (goals.get('home'), goals.get('away'))) if best else None
    hn = (best.get('teams') or {}).get('home', {}).get('name') if best else ''
    an = (best.get('teams') or {}).get('away', {}).get('name') if best else ''
    ko = (best.get('fixture') or {}).get('date') if best else None
    print('%-26s vs %-28s | score %.2f | %s vs %s | %s | %s | %s' % (h, a, bs, hn, an, status, score, ko))
    results.append({'target': (h, a), 'match': round(bs,2), 'api_home': hn, 'api_away': an, 'status': status, 'score': score, 'ko_utc': ko, 'fixture_id': (best.get('fixture') or {}).get('id') if best else None})

json.dump(results, io.open(os.path.join(ROOT, 'analysis_records', 'apifb_results_20260825.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('saved')
