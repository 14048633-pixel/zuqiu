# -*- coding: utf-8 -*-
import sys, io, csv, re
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
    if r.get('src','').startswith('20260826_68场') and r.get('date')=='2026-08-25':
        r['date']='08-26'; n+=1
with io.open(LEDGER,'w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=COLS,extrasaction='ignore')
    w.writeheader(); w.writerows(rows)
print('统一日期:',n)
# 校验 14 条
d=[r for r in rows if r.get('date')=='08-26']
print('08-26 条数:',len(d))
w=sum(1 for r in d if r.get('result')=='win'); l=sum(1 for r in d if r.get('result') in ('lose','loss')); p=sum(1 for r in d if r.get('result')=='push')
pnl=sum(float(r.get('pnl') or 0) for r in d)
print('胜 %d / 负 %d / 走 %d | PnL %+.2f | ROI %+.1f%%' % (w,l,p,pnl,pnl/len(d)*100 if d else 0))
print('--- 明细:')
for r in sorted(d, key=lambda x:x.get('match','')):
    print('  %-5s %-22s vs %-22s | %-8s %-9s | %-6s %-5s | ret %-6s pnl %+.2f | %s' % (
        r['league'], (r['home'] or '')[:20], (r['away'] or '')[:20], r['bet_name'], r['ev'],
        r['result'].upper(), r['score'], r['ret'], float(r['pnl'] or 0), r['src'].split('_')[-1]))
