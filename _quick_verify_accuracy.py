# -*- coding: utf-8 -*-
"""快速验证: BSD finished 比分 -> 结算 9/3 快照 15 腿命中率 + ROI."""
import sys, io, os, json, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r'D:\足球分析\prediction_v2')
import bsd_extra
TOKEN = bsd_extra.TOKEN
BASE = 'https://sports.bzzoiro.com/api/v2'
H = {**bsd_extra.HEADERS, 'Authorization': 'Token %s' % TOKEN}

def get(url, params=None, tries=3):
    for i in range(tries):
        try:
            r = requests.get(BASE + url, params=params, headers=H, timeout=60)
            if r.status_code == 200: return r.json()
        except Exception as e:
            pass
    return None

def norm(s):
    s = str(s).lower().strip()
    for x in ['fc', 'cf', 'sc', 'ac', 'ca', 'ud', 'deportivo', 'athletic', 'club', 'city', 'united', 'sv', 'ksv']:
        pass
    return s

# 拉 9/3-9/4 已完赛
d = get('/events/', {'status': 'finished',
                     'date_from': '2026-09-03T00:00:00Z',
                     'date_to': '2026-09-04T23:59:59Z', 'limit': 800})
evs = d.get('results') if isinstance(d, dict) else None
print('BSD finished events:', len(evs) if evs is not None else 'none')

res = {}
for e in evs or []:
    h = e.get('home_team'); a = e.get('away_team')
    if isinstance(h, dict): h = h.get('name')
    if isinstance(a, dict): a = a.get('name')
    if h is None or a is None: continue
    hs, as_ = e.get('home_score'), e.get('away_score')
    if hs is None or as_ is None: continue
    res[(str(h).lower(), str(a).lower())] = (int(hs), int(as_))

snap = json.load(open(r'D:\足球分析\analysis_records\v2_best_scan_20260903_1943.json', encoding='utf-8'))
print('快照场次:', len(snap))

rows = []
matched = 0
for m in snap:
    key = (str(m['home']).lower(), str(m['away']).lower())
    r_ = res.get(key)
    if r_ is None:
        rows.append((m['league'], m['home'], m['away'], None, None, None, None, None, None, None))
        continue
    matched += 1
    hg, ag = r_; total = hg + ag
    for leg in (m.get('bets') or []):
        nm, star, odds, ev = leg['name'], leg['star'], leg.get('odds'), leg.get('ev')
        if nm == '主胜': hit = 1 if hg > ag else 0
        elif nm == '客胜': hit = 1 if hg < ag else 0
        elif nm == '平局': hit = 1 if hg == ag else 0
        elif nm == '大2.5': hit = 1 if total >= 3 else 0
        else: hit = 1 if total <= 2 else 0
        rows.append((m['league'], m['home'], m['away'], nm, star, odds, ev, hg, ag, hit))

print('匹配到比分的场次: %d/%d' % (matched, len(snap)))
print('\n%-8s %-28s %-6s %2s %6s %5s %-6s %s' % ('联赛', '对阵', '腿', '星', '赔率', 'EV', '比分', '命中'))
tot = hits = roi_n = 0; roi_pnl = 0.0
missed = []
for r in rows:
    if r[3] is None:
        missed.append('%s %s vs %s' % (r[0], r[1], r[2])); continue
    lg, h, a, nm, star, odds, ev, hg, ag, hit = r
    tot += 1; hits += hit
    if odds:
        roi_n += 1; roi_pnl += (odds - 1) if hit else -1
    print('%-8s %-28s %-6s %2d %6s %5s %-6s %s' % (lg, '%s vs %s' % (h, a), nm, star, odds, ev, '%d-%d' % (hg, ag), '对' if hit else '错'))

print('\n=== 结算汇总 ===')
print('总腿 %d  命中 %d  →  命中率 %.1f%%' % (tot, hits, 100.0 * hits / tot if tot else 0))
if roi_n: print('带赔率 %d 腿  模拟ROI %+.1f%%' % (roi_n, 100.0 * roi_pnl / roi_n))
for sl in (1, 2, 3):
    sub = [r for r in rows if r[3] is not None and r[4] == sl]
    if sub:
        hh = sum(1 for x in sub if x[9])
        print('  star=%d: %d腿 命中%.1f%%' % (sl, len(sub), 100.0 * hh / len(sub)))
if missed:
    print('\n未匹配(无腿场或无结果):')
    for x in missed: print('  ', x)
