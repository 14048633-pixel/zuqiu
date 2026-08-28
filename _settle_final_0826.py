# -*- coding: utf-8 -*-
import sys, io, os, json, csv, re, shutil
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ROOT = r'D:\足球分析'

# 权威终局比分 (BSD v2 status=finished, 常规比分, 无加时)
FINAL_SCORES = {
 ('Fagiano Okayama','Belugarosso Iwami'):'3-0', ('Mito Hollyhock','Kyoto Sangyo University'):'0-2',
 ('JEF United Chiba','Azul Claro Numazu'):'1-1', ('Shonan Bellmare','ReinMeer Aomori FC'):'1-0',
 ('Albirex Niigata','Kagoshima United'):'0-4', ('V-Varen Nagasaki','Ehime FC'):'3-2',
 ('Kyoto Sanga FC','FC Maruyasu Okazaki'):'1-0', ('Shimizu S-Pulse','FC Osaka'):'2-1',
 ('Kashiwa Reysol','Senshu University'):'2-1', ('FC Tokyo','AC Nagano Parceiro'):'6-0',
 ('Urawa Red Diamonds','Yamanashi Gakuin University Orions'):'3-0', ('Kashima Antlers','Atletico Suzuka Club'):'3-0',
 ('Gamba Osaka','Reilac Shiga FC'):'2-0', ('Yokohama F. Marinos','Fukushima United FC'):'1-0',
 ('Kawasaki Frontale','Tochigi SC'):'3-1', ('Vissel Kobe','Veroskronos Tsuno'):'2-1',
 ('FC Imabari','Blaublitz Akita'):'4-1', ('Montedio Yamagata','Fujieda MYFC'):'3-5',
 ('Vegalta Sendai','Tochigi City FC'):'1-2', ('Iwaki FC','Oita Trinita'):'2-0',
 ('RB Omiya Ardija','Vanraure Hachinohe'):'2-0', ('Sagan Tosu','Kataller Toyama'):'4-0',
 ('Jubilo Iwata','Tegevajaro Miyazaki'):'0-1', ('Hokkaido Consadole Sapporo','Ventforet Kofu'):'1-3',
 ('Tokyo Verdy','Thespa Gunma'):'4-1', ('Nagoya Grampus','Gainare Tottori'):'1-3',
 ('Tokushima Vortis','FC Tokushima'):'3-0', ('Yokohama FC','Criacao Shinjuku'):'3-1',
 ('Cerezo Osaka','FC Gifu'):'3-1', ('Sanfrecce Hiroshima','Okinawa SV'):'4-1',
 ('Machida Zelvia','Iwate Grulla Morioka'):'3-0',
 ('Gangwon FC','Gwangju FC'):'2-2', ('FC Anyang','Incheon United'):'2-1',
 ('Daejeon Hana Citizen','Ulsan HD'):'2-1',
}

scan = json.load(io.open(os.path.join(ROOT,'analysis_records','scan_next24h_20260825_1644.json'), encoding='utf-8'))
res  = json.load(io.open(os.path.join(ROOT,'analysis_records','results_scan_20260826_final2.json'), encoding='utf-8'))
res_by = {(r.get('home'), r.get('away')): r for r in res}

# 合并: 先用 final2, 再覆盖权威终局
for (h,a),sc in FINAL_SCORES.items():
    if (h,a) in res_by:
        res_by[(h,a)]['score'] = sc
        res_by[(h,a)]['status'] = 'finished'
        res_by[(h,a)]['source'] = 'BSD-v2-finished'

FINAL = ('post','finished','FT','AET','PEN')
def settle(leg, h, a):
    name = leg.get('name') or ''
    total = h + a
    if name.startswith('大') or name.startswith('小'):
        line = float(re.sub(r'[^0-9.]','', name.replace('大','').replace('小','')))
        r = ('win' if total > line else ('push' if total == line else 'lose')) if name.startswith('大') else ('win' if total < line else ('push' if total == line else 'lose'))
    elif name.startswith('1X2'):
        if '主胜' in name: r = 'win' if h > a else ('push' if h==a else 'lose')
        elif '客胜' in name: r = 'win' if h < a else ('push' if h==a else 'lose')
        else: r = 'win' if h==a else 'lose'
    else: return None
    odds = float(leg.get('odds') or 0)
    ret = {'win': odds, 'push': 1.0, 'lose': 0.0}[r]
    return r, round(ret-1,4), total

# 保存最终结果 final3
out = []
for m in scan:
    key = (m.get('home'), m.get('away'))
    rr = res_by.get(key)
    score_s = rr.get('score') if rr else None
    status = rr.get('status') if rr else None
    row = {'ko_bjt': m.get('ko_bjt'), 'league': m.get('league'), 'home': m.get('home'), 'away': m.get('away'),
           'best': (m.get('best_bet') or {}).get('name'), 'best_ev': (m.get('best_bet') or {}).get('ev'),
           'direction': m.get('direction'), 'dir_ev': m.get('dir_ev'), 'star': m.get('star'),
           'vetoed': bool(m.get('vetoed')), 'score': score_s, 'status': status,
           'source': rr.get('source') if rr else None}
    out.append(row)
io.open(os.path.join(ROOT,'analysis_records','results_scan_20260826_final3.json'), 'w', encoding='utf-8').write(
    json.dumps(out, ensure_ascii=False, indent=1))
print('saved final3:', len(out))

# ---- 入账(新增 5 条) ----
LEDGER = os.path.join(ROOT, 'analysis_records', 'bet_ledger.csv')
COLS = ["date","league","match","home","away","bet_name","prob","odds","ev","star","ev_tier",
        "stake_factor","result","ret","pnl","status","src","veto","risk_tags","divergence_pp",
        "placed_odds","bookmaker","verified","kickoff","data_src","snap_age_h","upset_level",
        "data_note","scan_ts","coach_atk_mod","coach_def_mod","coach_sample_size",
        "home_score","away_score","score","is_draw"]
shutil.copyfile(LEDGER, LEDGER.replace('.csv','_backup_20260826_before_final_settle.csv'))
rows = list(csv.DictReader(io.open(LEDGER, encoding='utf-8-sig', newline='')))
existing = {(r.get('home'), r.get('away'), r.get('bet_name')) for r in rows}
added = 0
newrows = []
for m in scan:
    key = (m.get('home'), m.get('away'))
    rr = res_by.get(key)
    if not rr or not rr.get('score') or rr.get('status') not in FINAL:
        continue
    try: h,a = map(int, rr['score'].split('-'))
    except Exception: continue
    leg = m.get('best_bet'); is_best = bool(leg)
    if not leg:
        d = m.get('direction'); dv = m.get('dir_ev') or 0
        if not d or dv <= 0: continue
        leg = next((b for b in (m.get('bets') or []) if b.get('name') == d), None)
        if not leg: continue
    if (m.get('home'), m.get('away'), leg.get('name')) in existing:
        continue
    r, ret, pnl = settle(leg, h, a)
    if r is None: continue
    nr = {'date':'08-26','league':m.get('league',''),'match':'%s vs %s'%(m.get('home'),m.get('away')),
          'home':m.get('home'),'away':m.get('away'),'bet_name':leg.get('name',''),
          'prob':round(float(leg.get('prob') or 0),4),'odds':leg.get('odds',''),
          'ev':round(float(leg.get('ev') or 0),4),'star':leg.get('star',''),'ev_tier':leg.get('ev_tier',''),
          'stake_factor':leg.get('stake_factor',''),'result':r,'ret':ret,'pnl':pnl,
          'status':'已结算' if is_best else '方向参考',
          'src':'20260826_68场_BEST' if is_best else '20260826_68场_方向参考',
          'veto':1 if m.get('vetoed') else 0,'risk_tags':';'.join(m.get('risk_tags') or []),
          'divergence_pp':'','placed_odds':'','bookmaker':'','verified':'','kickoff':m.get('ko_utc') or '',
          'data_src':'','snap_age_h':'','upset_level':'','data_note':'','scan_ts':'20260825_1644',
          'coach_atk_mod':'','coach_def_mod':'','coach_sample_size':'',
          'home_score':h,'away_score':a,'score':'%d-%d'%(h,a),'is_draw':1 if h==a else 0}
    rows.append(nr); newrows.append(nr); existing.add((m.get('home'),m.get('away'),leg.get('name'))); added += 1
with io.open(LEDGER,'w',encoding='utf-8-sig',newline='') as f:
    w = csv.DictWriter(f, fieldnames=COLS, extrasaction='ignore')
    w.writeheader(); w.writerows(rows)
print('新增入账:', added, '| 台账累计:', len(rows))
for nr in newrows:
    mark={'win':'WIN','lose':'LOSE','push':'PUSH'}[nr['result']]
    print('  %-6s %-22s vs %-22s | %-8s %+.1f%% | %s %s | PnL %+.2f' % (
        nr['league'], nr['home'][:20], nr['away'][:20], nr['bet_name'], float(nr['ev'])*100, nr['score'], mark, float(nr['pnl'])))
