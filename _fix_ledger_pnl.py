# -*- coding: utf-8 -*-
import sys, io, csv, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
LEDGER = r'D:\足球分析\analysis_records\bet_ledger.csv'
COLS = ["date","league","match","home","away","bet_name","prob","odds","ev","star","ev_tier",
        "stake_factor","result","ret","pnl","status","src","veto","risk_tags","divergence_pp",
        "placed_odds","bookmaker","verified","kickoff","data_src","snap_age_h","upset_level",
        "data_note","scan_ts","coach_atk_mod","coach_def_mod","coach_sample_size",
        "home_score","away_score","score","is_draw"]
rows = list(csv.DictReader(io.open(LEDGER, encoding='utf-8-sig', newline='')))
fixed = 0
for r in rows:
    if r.get('date') != '08-26':
        continue
    odds = r.get('odds') or ''
    res = r.get('result')
    if res == 'win':
        ret = odds
    elif res == 'push':
        ret = '1.0'
    elif res in ('lose', 'loss'):
        ret = '0.0'
    else:
        continue
    try:
        ret_f = float(ret); pnl_f = round(ret_f - 1.0, 4)
    except Exception:
        continue
    if r.get('pnl') == '' or float(r.get('pnl')) != float(r.get('home_score', 0) or 0) + float(r.get('away_score', 0) or 0):
        r['ret'] = str(ret_f); r['pnl'] = str(pnl_f); fixed += 1
    else:
        r['ret'] = str(ret_f); r['pnl'] = str(pnl_f); fixed += 1
with io.open(LEDGER, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=COLS, extrasaction='ignore')
    w.writeheader(); w.writerows(rows)
print('fixed 08-26 rows:', fixed)
for r in rows:
    if r.get('date')=='08-26':
        print(' ', r.get('league'), r.get('home')[:18], 'vs', r.get('away')[:18], '|', r.get('bet_name'), '|', r.get('result'), '| odds', r.get('odds')[:6], '| ret', r.get('ret'), '| pnl', r.get('pnl'))
