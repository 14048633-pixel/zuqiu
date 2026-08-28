# -*- coding: utf-8 -*-
import sys, io, os, json, csv, re, shutil, unicodedata
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ROOT = r'D:\足球分析'
LEDGER = os.path.join(ROOT,'analysis_records','bet_ledger.csv')
COLS = ["date","league","match","home","away","bet_name","prob","odds","ev","star","ev_tier",
        "stake_factor","result","ret","pnl","status","src","veto","risk_tags","divergence_pp",
        "placed_odds","bookmaker","verified","kickoff","data_src","snap_age_h","upset_level",
        "data_note","scan_ts","coach_atk_mod","coach_def_mod","coach_sample_size",
        "home_score","away_score","score","is_draw"]
def team_key(t):
    t=unicodedata.normalize('NFKD',str(t)); t=''.join(c for c in t if not unicodedata.combining(c))
    toks=sorted(x for x in re.split(r'[^a-z0-9]+',t.lower()) if x and x not in ('fc','cf'))
    return '|'.join(toks)

shutil.copyfile(LEDGER, LEDGER.replace('.csv','_backup_20260826_before_ousameopp.csv'))
rows=list(csv.DictReader(io.open(LEDGER,encoding='utf-8-sig',newline='')))
have={(r.get('league'),team_key(r.get('home','')),team_key(r.get('away','')),r.get('bet_name')) for r in rows}

j=json.load(io.open(os.path.join(ROOT,'analysis_records','ou_same_opp_settled_20260819.json'),encoding='utf-8'))
added=0; dup=0; newrows=[]
for x in j['rows']:
    model=x.get('model'); total=x.get('total')
    if model not in ('大','小'): continue
    bet=model+'2.50'
    k=(x.get('league'),team_key(x.get('home','')),team_key(x.get('away','')),bet)
    if k in have: dup+=1; continue
    hit=bool(x.get('hit'))
    odds=float(x.get('odds') or 0)
    ret=odds if hit else 0.0
    pnl=round(ret-1,4)
    score=str(x.get('score') or '')
    try:
        h,a=map(int,score.split('-'))
    except Exception:
        h=a=''
    nr={'date':(x.get('ct') or '')[:10],'league':x.get('league',''),
        'match':'%s vs %s'%(x.get('home'),x.get('away')),
        'home':x.get('home'),'away':x.get('away'),'bet_name':bet,
        'prob':'','odds':str(odds),'ev':'','star':'','ev_tier':'','stake_factor':'',
        'result':'win' if hit else 'lose','ret':str(ret),'pnl':str(pnl),
        'status':'方向参考','src':'20260819_ou_same_opp_方向参考',
        'veto':'0','risk_tags':'','divergence_pp':'','placed_odds':'','bookmaker':'','verified':'',
        'kickoff':x.get('ct',''),'data_src':'','snap_age_h':'','upset_level':'','data_note':'','scan_ts':'',
        'coach_atk_mod':'','coach_def_mod':'','coach_sample_size':'',
        'home_score':h,'away_score':a,'score':score,'is_draw':(1 if (isinstance(h,int) and h==a) else 0)}
    rows.append(nr); newrows.append(nr); have.add(k); added+=1
with io.open(LEDGER,'w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=COLS,extrasaction='ignore')
    w.writeheader(); w.writerows(rows)
print('新增 %d 条 | 跳过(已在账本) %d | 账本累计 %d' % (added,dup,len(rows)))
print('备份:', LEDGER.replace('.csv','_backup_20260826_before_ousameopp.csv'))
from collections import Counter
print('按日期:',dict(Counter(r['date'] for r in newrows)))
w=sum(1 for r in newrows if r['result']=='win'); l=sum(1 for r in newrows if r['result']=='lose')
pnl=sum(float(r['pnl']) for r in newrows)
print('新增: 胜 %d / 负 %d | PnL %+.2f | ROI %+.1f%%' % (w,l,pnl,pnl/len(newrows)*100 if newrows else 0))
