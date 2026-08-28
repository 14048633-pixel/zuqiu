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
n=0
for r in rows:
    if r.get('src','').startswith('20260826_68场') and r.get('date')=='2026-08-26':
        r['date']='08-26'; n+=1
with io.open(LEDGER,'w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=COLS,extrasaction='ignore')
    w.writeheader(); w.writerows(rows)
print('再统一:',n)
d=[r for r in rows if r.get('date')=='08-26']
print('08-26 总条数:',len(d))
w=sum(1 for r in d if r.get('result')=='win'); l=sum(1 for r in d if r.get('result') in ('lose','loss'))
pnl=sum(float(r.get('pnl') or 0) for r in d)
print('胜 %d / 负 %d | PnL %+.2f | ROI %+.1f%%' % (w,l,pnl,pnl/len(d)*100 if d else 0))
b=[r for r in d if r.get('src','').endswith('BEST')]
bp=sum(float(r['pnl']) for r in b)
print('BEST 4: 胜 %d / 负 %d | PnL %+.2f | ROI %+.1f%%' % (sum(1 for r in b if r['result']=='win'), sum(1 for r in b if r['result'] in ('lose','loss')), bp, bp/len(b)*100 if b else 0))
