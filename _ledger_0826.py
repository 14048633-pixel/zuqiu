# -*- coding: utf-8 -*-
import sys, io, os, json, csv, shutil, re
from datetime import datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = r'D:\足球分析'
LEDGER = os.path.join(ROOT, 'analysis_records', 'bet_ledger.csv')
COLS = ["date","league","match","home","away","bet_name","prob","odds","ev","star","ev_tier",
        "stake_factor","result","ret","pnl","status","src","veto","risk_tags","divergence_pp",
        "placed_odds","bookmaker","verified","kickoff","data_src","snap_age_h","upset_level",
        "data_note","scan_ts","coach_atk_mod","coach_def_mod","coach_sample_size",
        "home_score","away_score","score","is_draw"]

scan = json.load(io.open(os.path.join(ROOT,'analysis_records','scan_next24h_20260825_1644.json'), encoding='utf-8'))
res  = json.load(io.open(os.path.join(ROOT,'analysis_records','results_scan_20260826_final2.json'), encoding='utf-8'))
res_by = {}
for r in res:
    res_by[(r.get('home'), r.get('away'))] = r

FINAL = ('post','finished','FT','AET','PEN')

def norm(t):
    t = ''.join(c for c in (t or '') if c.isalnum() or c.isspace()).lower()
    return ' '.join(sorted(x for x in re.split(r'\s+', t) if x and x not in ('fc','cf')))

def result_ou(leg, h, a):
    total = h + a
    name = leg.get('name') or ''
    try: line = float(re.sub(r'[^0-9.]','',name.replace('大','').replace('小','')))
    except Exception: return None, None
    if name.startswith('大'):
        return ('win' if total > line else ('push' if total == line else 'lose')), total
    if name.startswith('小'):
        return ('win' if total < line else ('push' if total == line else 'lose')), total
    return None, total

def result_1x2(leg, h, a):
    name = leg.get('name') or ''
    if '主胜' in name: return 'win' if h > a else ('push' if h == a else 'lose')
    if '客胜' in name: return 'win' if h < a else ('push' if h == a else 'lose')
    if '平局' in name: return 'win' if h == a else 'lose'
    return None

def settle(leg, h, a):
    name = leg.get('name') or ''
    r = None; total = h + a
    if name.startswith('大') or name.startswith('小'):
        r, total = result_ou(leg, h, a)
    elif name.startswith('1X2'):
        r = result_1x2(leg, h, a)
    if r is None:
        return None, None, None
    odds = float(leg.get('odds') or 0)
    ret = {'win': odds, 'push': 1.0, 'lose': 0.0}.get(r)
    pnl = round(ret - 1.0, 4)
    return r, ret, pnl

# 备份
bak = LEDGER.replace('.csv', '_backup_20260826_before_settle.csv')
shutil.copyfile(LEDGER, bak)
rows = []
with io.open(LEDGER, encoding='utf-8-sig', newline='') as f:
    rows = list(csv.DictReader(f))

def team_key(t):
    return norm(t)

added = 0; skipped_live = 0; skipped_nodata = 0
report = []
for m in scan:
    key = (m.get('home'), m.get('away'))
    rr = res_by.get(key)
    if not rr:
        continue
    score_s = rr.get('score'); status = rr.get('status')
    if not score_s:
        skipped_nodata += 1
        continue
    try:
        h, a = map(int, score_s.split('-'))
    except Exception:
        skipped_nodata += 1; continue
    if status not in FINAL:
        skipped_live += 1
        continue

    # 选腿: best_bet > 正EV方向
    leg = m.get('best_bet')
    is_best = bool(leg)
    if not leg:
        d = m.get('direction'); dv = m.get('dir_ev') or 0
        if not d or dv <= 0:
            continue
        leg = next((b for b in (m.get('bets') or []) if b.get('name') == d), None)
        if not leg:
            continue
    r, ret, pnl = settle(leg, h, a)
    if r is None:
        continue
    nr = {
        'date': '08-26',
        'league': m.get('league',''),
        'match': '%s vs %s' % (m.get('home'), m.get('away')),
        'home': m.get('home'), 'away': m.get('away'),
        'bet_name': leg.get('name',''),
        'prob': round(float(leg.get('prob') or 0),4),
        'odds': leg.get('odds',''),
        'ev': round(float(leg.get('ev') or 0),4),
        'star': leg.get('star',''),
        'ev_tier': leg.get('ev_tier',''),
        'stake_factor': leg.get('stake_factor',''),
        'result': r, 'ret': ret, 'pnl': pnl,
        'status': '已结算' if is_best else '方向参考',
        'src': '20260826_68场_BEST' if is_best else '20260826_68场_方向参考',
        'veto': 1 if m.get('vetoed') else 0,
        'risk_tags': ';'.join(m.get('risk_tags') or []),
        'divergence_pp': '', 'placed_odds': '', 'bookmaker': '', 'verified': '',
        'kickoff': m.get('ko_utc') or '',
        'data_src': '', 'snap_age_h': '', 'upset_level': '', 'data_note': '',
        'scan_ts': '20260825_1644',
        'coach_atk_mod': '', 'coach_def_mod': '', 'coach_sample_size': '',
        'home_score': h, 'away_score': a, 'score': '%d-%d' % (h,a),
        'is_draw': 1 if h == a else 0,
    }
    rows.append(nr); added += 1
    report.append(nr)

with io.open(LEDGER, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=COLS, extrasaction='ignore')
    w.writeheader()
    w.writerows(rows)

print('入账 %d 条 | 跳过(LIVE) %d | 跳过(无数据) %d | 台账累计 %d' % (added, skipped_live, skipped_nodata, len(rows)))
print('备份 ->', bak)
print()
print('== 入账明细 ==')
for nr in report:
    mark = {'win':'WIN','lose':'LOSE','push':'PUSH'}.get(nr['result'])
    print('  %-8s %-6s %-22s vs %-22s | %-8s %+.1f%% | %s %s | %s %+.2f' % (
        nr['league'], nr['bet_name'], (nr['home'] or '')[:20], (nr['away'] or '')[:20],
        nr['status'], float(nr['ev'])*100, nr['score'], mark, 'PnL', float(nr['pnl'])))
