# -*- coding: utf-8 -*-
"""34 场结果入账 bet_ledger.csv: BEST 出单 + 方向参考 + 否决, 复用 settle_leg 计算"""
import json, io, sys, os, csv, shutil
from datetime import datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
from settle_batch import settle_leg, pnl_for_result

scan = json.load(open(os.path.join(ROOT, "analysis_records", "scan_next24h_20260825_0021.json"), encoding="utf-8"))
res = json.load(open(os.path.join(ROOT, "analysis_records", "results_all_20260825.json"), encoding="utf-8"))
scanmap = {(m['home'], m['away']): m for m in scan}
resmap = {(r['home'], r['away']): r for r in res}

ledger = os.path.join(ROOT, "analysis_records", "bet_ledger.csv")
bak = ledger.replace(".csv", ".bak_20260825_2340.csv")
shutil.copy(ledger, bak)
print("backup:", bak)

HEAD = ['date','league','match','home','away','bet_name','prob','odds','ev','star','ev_tier','stake_factor',
        'result','ret','pnl','status','src','veto','risk_tags','divergence_pp','placed_odds','bookmaker',
        'verified','kickoff','data_src','snap_age_h','upset_level','data_note','scan_ts','coach_atk_mod',
        'coach_def_mod','coach_sample_size','home_score','away_score','score','is_draw']

new_rows = []
for r in sorted(res, key=lambda x: x['ko_bjt']):
    m = scanmap.get((r['home'], r['away'])) or {}
    if not r['score']: continue
    hs, as_ = [int(x) for x in r['score'].split('-')]
    ko = m.get('ko_utc', '')
    date = r['ko_bjt'][:5].replace('-', '-')  # "08-25"
    league = r['league']
    home, away = r['home'], r['away']
    match = f"{home} vs {away}"
    tags = '; '.join(m.get('risk_tags') or [])
    vetoed = bool(r['vetoed'])
    bb = m.get('best_bet') or {}

    # 1) BEST 出单腿
    if bb.get('name'):
        name, odds, ev, star, tier = bb['name'], float(bb['odds']), bb['ev'], bb.get('star', 0), bb.get('ev_tier', '')
        resl, ret = settle_leg(name, odds, hs, as_)
        pnl = pnl_for_result(resl, ret)
        stake = 0.5 if star >= 2 else 0.35
        new_rows.append([date, league, match, home, away, name, bb.get('prob'), round(odds,2), round(ev,4), star, tier, stake,
                         resl, ret, round(pnl,4), '已结算', '20260825_34场_BEST', 0, tags, '', '', '', '', ko, 'BSD+API-FB', '', '', 'BEST出单', '2026-08-25T00:21:00+00:00', '', '', '', hs, as_, r['score'], int(hs==as_)])
    # 2) 方向参考腿 (direction != best_bet.name 或非 BEST 场次)
    dl = m.get('direction')
    if dl and not (bb.get('name') == dl):
        odds = float(m.get('dir_odds') or 0)
        ev = m.get('dir_ev') or 0
        resl, ret = settle_leg(dl, odds, hs, as_)
        pnl = pnl_for_result(resl, ret)
        if vetoed:
            status, src = '否决', '20260825_34场_否决'
        else:
            status, src = '方向参考', '20260825_34场_方向参考'
        new_rows.append([date, league, match, home, away, dl, m.get('dir_prob'), round(odds,2), round(ev,4), m.get('star',0), m.get('ev_tier',''), 0.0,
                         resl, ret, round(pnl,4), status, src, 1 if vetoed else 0, tags, '', '', '', '', ko, 'BSD+API-FB', '', '', '方向参考' if not vetoed else '否决场-方向若打', '2026-08-25T00:21:00+00:00', '', '', '', hs, as_, r['score'], int(hs==as_)])

print("新增行:", len(new_rows))
with open(ledger, 'a', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f)
    for row in new_rows:
        w.writerow(row)

# 汇总
from collections import Counter
print()
print("== BEST 出单 8 ==")
for r in new_rows:
    if r[16] == 'BEST出单' or 'BEST' in r[16]:
        print(f"  {r[1]:<6} {r[3][:18]:20} vs {r[4][:18]:20} {r[5]:8} {r[11]:5} ret={r[12]} pnl={r[13]}")
c = Counter(x[11] for x in new_rows if 'BEST' in str(x[16]))
print("BEST 结果分布:", dict(c))
c2 = Counter(x[11] for x in new_rows if '方向参考' == str(x[16]))
print("方向参考结果分布:", dict(c2))
c3 = Counter(x[11] for x in new_rows if str(x[16]) == '否决')
print("否决场方向分布:", dict(c3))
pnl_best = sum(x[13] for x in new_rows if 'BEST' in str(x[16]))
pnl_dir = sum(x[13] for x in new_rows if '方向参考' == str(x[16]))
n_best = sum(1 for x in new_rows if 'BEST' in str(x[16]))
n_dir = sum(1 for x in new_rows if '方向参考' == str(x[16]))
print(f"BEST PnL={pnl_best:+.2f} ROI={pnl_best/n_best*100:+.1f}%")
print(f"方向参考 PnL={pnl_dir:+.2f} ROI={pnl_dir/n_dir*100:+.1f}%")
