import io, sys, collections
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'prediction_v2')
import scan_upcoming as su
from datetime import datetime, timezone

ts, lavg, index = su.load_team_stats()
events, future_skipped = su.parse_snapshots()
TARGET = {'比甲','荷甲','葡超'}
evs = [e for e in events if e['league'] in TARGET]
print('三联赛待扫描比赛:', len(evs), '| 剔除未来脏快照:', future_skipped)

rows = []
for e in evs:
    r = su.analyze_match(e, ts, lavg, index)
    rows.append((e, r))

# 汇总
print()
print('%-6s %-22s %-22s | λ主/客 | 源[主/客] | 方向 | BEST | EV分布' % ('联赛','主队','客队'))
n_bet=0; n_pos=0; n_indep=0
tier = collections.Counter()
for e, r in rows:
    bb = r['best_bet']
    bb_s = ('%s EV%+.1f%% ★%d' % (bb['name'], bb['ev']*100, bb.get('star',0))) if bb else '-无单-'
    pos = any(b['ev']>0 for b in r['bets'])
    if bb: n_bet+=1
    if pos: n_pos+=1
    src = '%s/%s' % (r['data_src']['home'], r['data_src']['away'])
    if 'cur' in src and 'cur' in src: n_indep+=1
    tier[r['ev_tier']]+=1
    di = r['direction']
    dir_s = di['name'] if di else '-'
    print('%-6s %-22s %-22s | %.2f/%.2f | %s | %s | %s | %s' % (
        e['league'], e['home'][:22], e['away'][:22], r['lambda']['home'], r['lambda']['away'],
        src, dir_s, bb_s, ','.join('%s%.0f%%' % (b['name'][:2], b['ev']*100) for b in r['bets'] if b['ev']>0)[:60]))
print()
print('可出单:', n_bet, '/', len(rows), '| 正EV场次:', n_pos, '/', len(rows), '| EV分级:', dict(tier))
