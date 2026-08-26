# -*- coding: utf-8 -*-
import json, io, sys, os, re, unicodedata
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ROOT = r"D:\足球分析"
scan = json.load(open(os.path.join(ROOT, "analysis_records", "scan_next24h_20260825_0021.json"), encoding="utf-8"))
bsd = json.load(open(os.path.join(ROOT, "analysis_records", "results_bsd_20260825_2329.json"), encoding="utf-8"))
apifb = json.load(open(os.path.join(ROOT, "analysis_records", "apifb_results_20260825.json"), encoding="utf-8"))

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

apimap = {}
for r in apifb:
    apimap[(r['target'][0], r['target'][1])] = r

bsdmap = {(r['home'], r['away']): r for r in bsd}

out = []
for m in scan:
    h, a = m['home'], m['away']
    r = bsdmap.get((h, a), {})
    score, status, src = r.get('score'), r.get('status'), ('BSD' if r.get('bsd_id') else None)
    # API-Football 覆盖（针对无BSD包场次，用扫描队名映射到 apifb target）
    for tk, tr in apimap.items():
        if max(_fuzzy(h, tk[0]), _fuzzy(a, tk[0])) > 0.85 and max(_fuzzy(h, tk[1]), _fuzzy(a, tk[1])) > 0.85:
            if tr.get('score'):
                score, status, src = tr['score'], tr['status'], (src + '+API-FB' if src else 'API-FB')
                break
    # 特殊修正: Hallescher vs Schalke BSD 2329 误报 2-2, API-FB 确认 2-5(AET)
    if 'hallescher' in _norm(h) and 'schalke' in _norm(a):
        score, status, src = '2-5', 'AET', 'API-FB(BSD误报修正)'
    best = m.get('best_bet') or {}
    out.append({
        'ko_bjt': m['ko_bjt'], 'league': m['league'], 'home': h, 'away': a,
        'direction': m.get('direction'), 'dir_ev': m.get('dir_ev'), 'star': m.get('star'),
        'best_bet': best.get('name'), 'bb_ev': best.get('ev'),
        'vetoed': m.get('vetoed'), 'veto_reason': m.get('veto_reason'),
        'score': score, 'status': status or '未知', 'source': src,
    })

json.dump(out, io.open(os.path.join(ROOT, 'analysis_records', 'results_all_20260825.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('saved results_all_20260825.json | 场次:', len(out))
from collections import Counter
print('状态:', dict(Counter(r['status'] for r in out)))
print('来源:', dict(Counter(r['source'] for r in out)))
print('有比分:', sum(1 for r in out if r['score']))
print('无比分:', [(r['home'], r['away']) for r in out if not r['score']])
