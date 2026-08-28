# -*- coding: utf-8 -*-
import sys, io, csv
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
LEDGER = r'D:\足球分析\analysis_records\bet_ledger.csv'
COLS = ["date","league","match","home","away","bet_name","prob","odds","ev","star","ev_tier",
        "stake_factor","result","ret","pnl","status","src","veto","risk_tags","divergence_pp",
        "placed_odds","bookmaker","verified","kickoff","data_src","snap_age_h","upset_level",
        "data_note","scan_ts","coach_atk_mod","coach_def_mod","coach_sample_size",
        "home_score","away_score","score","is_draw"]
rows = list(csv.DictReader(io.open(LEDGER, encoding='utf-8-sig', newline='')))
for r in rows:
    if r.get('date')=='08-26' and r.get('ret') not in ('', '0.0'):
        try:
            r['ret'] = str(round(float(r['ret']), 4))
            r['pnl'] = str(round(float(r['pnl']), 4))
        except Exception: pass
with io.open(LEDGER,'w',encoding='utf-8-sig',newline='') as f:
    w = csv.DictWriter(f, fieldnames=COLS, extrasaction='ignore')
    w.writeheader(); w.writerows(rows)
print('OK')
