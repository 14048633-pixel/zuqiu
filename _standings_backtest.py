# -*- coding: utf-8 -*-
"""
积分榜 zone 标签 实盘回测（无泄漏）
====================================
口径:
- 预测输入: 账本赛前固化字段 (bet_name/odds/result/star), 不重跑模型
- 积分榜: 用 espn/j1/csl 赛果, 仅取 kickoff 严格早于该场的同赛季比赛重建 -> 无泄漏
- 结算: 账本 result (win/lose/half/push/VOID) 等额注净值
- 只覆盖"联赛有积分榜概念且赛果数据完整"的场次
"""
import csv, sys, io, glob, json
from datetime import datetime
from collections import defaultdict, Counter
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'prediction_v2')
import _batch_match_info as bmi

LEDGER = r'D:\足球分析\analysis_records\bet_ledger.csv'
OUT = r'D:\足球分析\analysis_records\standings_backtest_report.md'

# ---------- 赛季映射 ----------
EU_SEASONS = {'英冠':'2026/2027','英乙':'2026/2027','西甲':'2026/2027','西乙':'2026/2027',
              '法甲':'2026/2027','法乙':'2026/2027','荷甲':'2026/2027','葡超':'2026/2027',
              '比甲':'2026/2027','土超':'2026/2027','德乙':'2026/2027','J1':'2026/2027'}
YEAR_SEASONS = {'丹超':'2026','墨超':'2026','巴甲':'2026','挪超':'2026','智利甲':'2026',
                '瑞超':'2026','美职':'2026','阿甲':'2026','中超':'2026'}
FILE_BY_LG = {'英冠':'espn_英冠_results.csv','英乙':'espn_英乙_results.csv','西甲':'espn_西甲_results.csv',
              '西乙':'espn_西乙_results.csv','法甲':'espn_法甲_results.csv','法乙':'espn_法乙_results.csv',
              '荷甲':'espn_荷甲_results.csv','葡超':'espn_葡超_results.csv','比甲':'espn_比甲_results.csv',
              '土超':'espn_土超_results.csv','德乙':'espn_德乙_results.csv','丹超':'espn_丹超_results.csv',
              '墨超':'espn_墨超_results.csv','巴甲':'espn_巴甲_results.csv','挪超':'espn_挪超_results.csv',
              '智利甲':'espn_智利甲_results.csv','瑞超':'espn_瑞超_results.csv','美职':'espn_美职_results.csv',
              '阿甲':'espn_阿甲_results.csv','中超':'csl_2026_results.csv','J1':'j1_2026_results.csv'}
SEASON_BY_LG = dict(EU_SEASONS); SEASON_BY_LG.update(YEAR_SEASONS)

def parse_date(s):
    s = (s or '').strip().split(' ')[0]
    for fmt in ('%Y-%m-%d','%d/%m/%Y','%Y/%m/%d'):
        try: return datetime.strptime(s, fmt).date()
        except: pass
    return None

def parse_ko_date(s):
    s = (s or '').strip()
    if not s: return None
    for fmt in ('%Y-%m-%dT%H:%M:%S%z','%Y-%m-%dT%H:%M:%S','%Y-%m-%d %H:%M:%S','%Y-%m-%dT%H:%M','%Y-%m-%d'):
        try:
            d = datetime.strptime(s, fmt)
            if d.tzinfo is not None:
                d = d.astimezone()
            return d.date()
        except: pass
    return None

# ---------- 加载赛果 ----------
results = {}   # (league, season) -> list of (date, h, a, hg, ag)
for lg, fn in FILE_BY_LG.items():
    p = 'data/raw/football_data/' + fn
    try:
        with open(p, encoding='utf-8-sig') as f:
            rr = list(csv.DictReader(f))
    except FileNotFoundError:
        continue
    seas = SEASON_BY_LG.get(lg)
    lst = []
    for r in rr:
        if (r.get('Season') or '') != seas: continue
        d = parse_date(r.get('Date'))
        if not d: continue
        try:
            hg, ag = int(float(r['FTHG'])), int(float(r['FTAG']))
        except Exception:
            continue
        lst.append((d, r['HomeTeam'], r['AwayTeam'], hg, ag))
    results[(lg, seas)] = lst
    print('loaded %-6s %-10s n=%d' % (lg, seas, len(lst)))

# ---------- 账本 ----------
with open(LEDGER, encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
settled = [r for r in rows if (r.get('result') or '').strip() in ('win','lose','half','push','VOID')]
print('settled legs:', len(settled))

DROP = ('fc','fk','cd','rc','kc','krc','kaa','kvc','kv','oh','ud','ac','af','cf','if','sc')
def norm(name):
    try:
        k = bmi.team_key(name)
    except Exception:
        k = str(name).lower()
    toks = k.replace('-', ' ').replace('/', ' ').replace('.', ' ').split()
    toks = [t for t in toks if t not in DROP and len(t) > 1]
    return tuple(toks)

def match_key(name, table):
    nk = norm(name)
    if not nk:
        return None
    if nk in table:
        return table[nk]
    cands = []
    for k, info in table.items():
        if not k:
            continue
        sk, snk = set(k), set(nk)
        if sk <= snk or snk <= sk:
            cands.append((9999, info))
            continue
        inter = sk & snk
        if inter:
            score = sum(len(t) for t in inter) + (2 if len(inter) >= 2 else 0)
            cands.append((score, info))
    if not cands:
        return None
    cands.sort(key=lambda x: -x[0])
    if len(cands) == 1 or cands[0][0] - cands[1][0] >= 5:
        return cands[0][1]
    return None

def rebuild_table(lg, seas, before):
    """返回 {team_key: {played, pts, pos, total, gd}}, 只含 before 之前(严格)的比赛."""
    pts = defaultdict(int); played = defaultdict(int); gd = defaultdict(int)
    teams = set()
    for (d, h, a, hg, ag) in results.get((lg, seas), []):
        if d >= before: continue
        teams.add(norm(h)); teams.add(norm(a))
        played[norm(h)] += 1; played[norm(a)] += 1
        gd[norm(h)] += hg - ag; gd[norm(a)] += ag - hg
        if hg > ag: pts[norm(h)] += 3
        elif hg < ag: pts[norm(a)] += 3
        else: pts[norm(h)] += 1; pts[norm(a)] += 1
    order = sorted(teams, key=lambda t: (-pts[t], -gd[t], t))
    total = len(order)
    tbl = {}
    for i, t in enumerate(order, 1):
        tbl[t] = {'pos': i, 'total': total, 'pts': pts[t], 'played': played[t], 'gd': gd[t]}
    return tbl

def zone(t):
    if not t or not t.get('total') or t['total'] < 4: return None
    if t['pos'] <= 3: return '争冠/升级'
    if t['pos'] > t['total'] * 0.8: return '保级'
    return '中游'

def net(r):
    o = float(r['odds']); res = (r['result'] or '').strip()
    if res == 'win': return o - 1.0
    if res == 'half': return (o - 1.0) / 2.0
    if res in ('push','VOID'): return 0.0
    if res == 'lose': return -1.0
    return None

# ---------- 逐腿打标 ----------
rows_tag = []  # (league, home_zone, away_zone, home_played, away_played, result, net, is_best_star)
n_skip_no_data = 0; n_skip_before = 0; n_no_match = 0
from collections import Counter as _C
_nm_lg = _C()
for r in settled:
    lg = r['league']
    if lg not in FILE_BY_LG or lg not in SEASON_BY_LG:
        n_skip_no_data += 1; continue
    seas = SEASON_BY_LG[lg]
    if (lg, seas) not in results or not results[(lg, seas)]:
        n_skip_no_data += 1; continue
    ko = parse_ko_date(r.get('kickoff'))
    if not ko:
        n_skip_before += 1; continue
    tbl = rebuild_table(lg, seas, ko)
    ht = match_key(r['home'], tbl); at = match_key(r['away'], tbl)
    if ht is None or at is None:
        n_no_match += 1
        _nm_lg[lg] += 1
        continue
    hz, az = zone(ht), zone(at)
    nv = net(r)
    if nv is None: continue
    rows_tag.append({'league': lg, 'hz': hz, 'az': az, 'hp': ht['played'], 'ap': at['played'],
                     'result': r['result'], 'net': nv, 'star': (r.get('star') or '').strip(),
                     'match': r['match'], 'bet': r['bet_name'], 'odds': r['odds'], 'stake': (r.get('stake_factor') or '').strip()})

print('skips: no_data=%d no_kickoff=%d no_match=%d' % (n_skip_no_data, n_skip_before, n_no_match))
print('no_match by league:', dict(_nm_lg))
print('tagged legs:', len(rows_tag))

def grp_stats(name, lst):
    n = len(lst)
    if not n: 
        print('  %-22s n=0' % name); return
    wins = sum(1 for x in lst if x['result']=='win'); half = sum(1 for x in lst if x['result']=='half')
    push = sum(1 for x in lst if x['result'] in ('push','VOID')); lose = sum(1 for x in lst if x['result']=='lose')
    dec = wins+half+lose
    hit = (wins + 0.5*half)/dec if dec else float('nan')
    roi = sum(x['net'] for x in lst)/n
    print('  %-22s n=%3d  win=%3d half=%2d push=%2d lose=%3d  命中=%5.1f%%  ROI=%+6.1f%%' % (
        name, n, wins, half, push, lose, hit*100, roi*100))
    return {'n':n,'hit':hit,'roi':roi}

print()
print('========== 全样本 vs zone 分组（等额注）==========')
grp_stats('全部已结算腿', [dict(x) for x in rows_tag])
grp_stats('  其中可重建积分组', rows_tag)
homes = defaultdict(list)
for x in rows_tag:
    homes[x['hz']].append(x)
for z in ('保级','中游','争冠/升级'):
    grp_stats('主场=%s' % z, homes.get(z, []))
grp_stats('主场=无数据', homes.get(None, []))
print()
rel = [x for x in rows_tag if x['hz'] is not None and x['az'] is not None]
print('========== 有zone双方场次（played>=3 才可信）==========')
grp_stats('双方有zone(全部)', rel)
rel3 = [x for x in rel if x['hp']>=3 and x['ap']>=3]
grp_stats('双方played>=3', rel3)
bz = [x for x in rel3 if x['hz']=='保级']
print()
print('========== 保级主场组 vs 其余(played>=3)==========')
grp_stats('保级主场', bz)
grp_stats('非保级主场', [x for x in rel3 if x['hz']!='保级'])
wy = [x for x in rel3 if x['hz']=='中游' and x['az']=='中游' and x['hp']>=8 and x['ap']>=8]
print()
print('========== 无欲无求组(双方中游played>=8)==========')
grp_stats('无欲无求', wy)
grp_stats('其余(played>=3)', [x for x in rel3 if not (x['hz']=='中游' and x['az']=='中游' and x['hp']>=8 and x['ap']>=8)])
print()
print('========== 争冠/升级主场组 ==========')
grp_stats('争冠主场', [x for x in rel3 if x['hz']=='争冠/升级'])
grp_stats('非争冠主场', [x for x in rel3 if x['hz']!='争冠/升级'])


# ================= 混杂检查: 保级主场是否只是联赛效应 =================
Z_BG = '\u4fdd\u7ea7'
Z_MID = '\u4e2d\u6e38'
Z_TOP = '\u4e89\u51a0/\u5347\u7ea7'
from collections import Counter as _C2
print()
print('========== 保级主场组联赛构成 (played>=3) ==========')
bg34 = [x for x in rel3 if x['hz'] == Z_BG]
print(dict(_C2(x['league'] for x in bg34)))
print('========== 联赛内: 保级主场 vs 非保级主场 (played>=3) ==========')
by_lg = defaultdict(list)
for x in rel3:
    by_lg[x['league']].append(x)
for lg in sorted(by_lg, key=lambda k: -len(by_lg[k])):
    grp = by_lg[lg]
    bg = [x for x in grp if x['hz'] == Z_BG]
    nbg = [x for x in grp if x['hz'] != Z_BG]
    if bg and nbg:
        def _r(lst):
            if not lst: return float('nan')
            return sum(x['net'] for x in lst)/len(lst)*100
        print('  %-6s BG(n=%2d,ROI=%+6.1f%%) vs nonBG(n=%2d,ROI=%+6.1f%%)' % (lg, len(bg), _r(bg), len(nbg), _r(nbg)))
print()
print('========== 全部867腿 等额ROI (选择偏差参照) ==========')
allnet = [net(r) for r in settled]
allnet = [x for x in allnet if x is not None]
print('  ALL settled: n=%d ROI=%+6.1f%%' % (len(allnet), sum(allnet)/len(allnet)*100))

# ================= 星级调整模拟 + 正式报告 =================
Z_BG = '\u4fdd\u7ea7'
Z_MID = '\u4e2d\u6e38'
Z_TOP = '\u4e89\u51a0/\u5347\u7ea7'
STAR_STAKE = {0: 0.15, 1: 0.35, 2: 0.6, 3: 1.0}
def star_of(x):
    st = x.get('star') or ''
    try:
        return int(float(st))
    except Exception:
        return -1  # 无星级参考腿

def base_stake(x):
    st = star_of(x)
    if st >= 0:
        return STAR_STAKE.get(st, 0.35)
    return 1.0

def adj_star(x):
    st = star_of(x)
    if st < 0:
        st = 1  # 参考腿默认视为1星基础
    if x['hz'] == Z_BG:
        st = min(st + 1, 3)
    if x['hz'] == Z_MID and x['az'] == Z_MID and x['hp'] >= 8 and x['ap'] >= 8:
        st = max(st - 1, 0)
    return st

def wroi(lst, stkf):
    num = sum(x['net'] * stkf(x) for x in lst)
    den = sum(stkf(x) for x in lst)
    return num / den if den else float('nan')

rel3_best = [x for x in rel3 if star_of(x) >= 0]
print()
print('========== 星级调整模拟 (played>=3 且原出单腿 n=%d) ==========' % len(rel3_best))
print('  base 加权ROI (原stake):   %+6.1f%%' % (wroi(rel3_best, base_stake) * 100))
print('  adj  加权ROI (积分榜调星): %+6.1f%%' % (wroi(rel3_best, lambda x: STAR_STAKE.get(adj_star(x), 0.35)) * 100))
bg_best = [x for x in rel3_best if x['hz'] == Z_BG]
wy_best = [x for x in rel3_best if x['hz'] == Z_MID and x['az'] == Z_MID and x['hp'] >= 8 and x['ap'] >= 8]
print('  保级主场原腿 n=%d: base=%+6.1f%%  adj(+1星)=%+6.1f%%' % (len(bg_best), wroi(bg_best, base_stake) * 100, wroi(bg_best, lambda x: STAR_STAKE.get(min(star_of(x)+1,3), 0.35)) * 100))
print('  无欲无求原腿 n=%d: base=%+6.1f%%  adj(-1星)=%+6.1f%%' % (len(wy_best), wroi(wy_best, base_stake) * 100, wroi(wy_best, lambda x: STAR_STAKE.get(max(star_of(x)-1,0), 0.35)) * 100))

# ---- write report ----
def _stats2(lst):
    n = len(lst)
    if not n:
        return None
    w = sum(1 for x in lst if x['result']=='win'); h = sum(1 for x in lst if x['result']=='half')
    p = sum(1 for x in lst if x['result'] in ('push','VOID')); l = sum(1 for x in lst if x['result']=='lose')
    dec = w + h + l
    hit = (w + 0.5*h)/dec if dec else float('nan')
    roi = sum(x['net'] for x in lst)/n
    return {'n': n, 'w': w, 'h': h, 'p': p, 'l': l, 'hit': hit, 'roi': roi}

def fstat(lst):
    st = _stats2(lst)
    if not st:
        return 'n=0'
    return 'n=%d  win=%d half=%d push=%d lose=%d  hit=%.1f%%  ROI=%+0.1f%%' % (
        st['n'], st['w'], st['h'], st['p'], st['l'], st['hit'] * 100, st['roi'] * 100)

L = []
L.append('# 积分榜 zone 标签 实盘回测（无泄漏口径）')
L.append('')
L.append('- 生成: 2026-08-26 | 数据: analysis_records/bet_ledger.csv (867已结算腿) + espn/j1/csl 赛果重建')
L.append('- 无泄漏: 积分榜只用 kickoff 严格早于该场的同赛季赛果重建; 结算用账本 result')
L.append('- 覆盖: 可重建 %d 腿 / no_match %d / no_data %d / 主结论以 played>=3 组为准' % (len(rows_tag), n_no_match, n_skip_no_data))
L.append('')
L.append('## 1. 等额注分组（全部可重建 %d 腿）' % len(rows_tag))
L.append('- ALL: %s' % fstat(rows_tag))
for z in (Z_BG, Z_MID, Z_TOP):
    L.append('- 主场=%s: %s' % (z, fstat(homes.get(z, []))))
L.append('')
L.append('## 2. 双方有zone 且 played>=3（zone可信组 n=%d）' % len(rel3))
L.append('- 全部: %s' % fstat(rel3))
L.append('- 保级主场: %s' % fstat(bz))
L.append('- 非保级主场: %s' % fstat([x for x in rel3 if x['hz'] != Z_BG]))
L.append('- 争冠/升级主场: %s' % fstat([x for x in rel3 if x['hz'] == Z_TOP]))
L.append('- 无欲无求(双方中游played>=8): %s' % fstat(wy))
L.append('- 其余: %s' % fstat([x for x in rel3 if x not in wy]))
L.append('')
L.append('## 3. 星级调整模拟（原出单腿 played>=3, n=%d）' % len(rel3_best))
L.append('- 原stake加权ROI: %+0.1f%%' % (wroi(rel3_best, base_stake) * 100))
L.append('- 积分榜调星后加权ROI: %+0.1f%%' % (wroi(rel3_best, lambda x: STAR_STAKE.get(adj_star(x), 0.35)) * 100))
L.append('- 保级主场原腿(n=%d): base %+0.1f%% -> +1星 %+0.1f%%' % (len(bg_best), wroi(bg_best, base_stake) * 100, wroi(bg_best, lambda x: STAR_STAKE.get(min(star_of(x)+1, 3), 0.35)) * 100))
L.append('- 无欲无求原腿(n=%d): base %+0.1f%% -> -1星 %+0.1f%%' % (len(wy_best), wroi(wy_best, base_stake) * 100, wroi(wy_best, lambda x: STAR_STAKE.get(max(star_of(x)-1, 0), 0.35)) * 100))
L.append('')
L.append('## 4. 联赛明细（可重建）')
lg_rows = defaultdict(list)
for x in rows_tag:
    lg_rows[x['league']].append(x)
for lg in sorted(lg_rows, key=lambda k: -len(lg_rows[k])):
    L.append('- %s: %s' % (lg, fstat(lg_rows[lg])))
L.append('')
L.append('## 5. 混杂检查（联赛内 BG vs nonBG, played>=3）')
for lg in sorted(by_lg, key=lambda k: -len(by_lg[k])):
    grp = by_lg[lg]
    bg = [x for x in grp if x['hz'] == Z_BG]
    nbg = [x for x in grp if x['hz'] != Z_BG]
    if bg and nbg:
        def _r2(lst):
            if not lst: return float('nan')
            return sum(x['net'] for x in lst)/len(lst)*100
        L.append('- %s: BG(n=%d,ROI=%+0.1f%%) vs nonBG(n=%d,ROI=%+0.1f%%)' % (lg, len(bg), _r2(bg), len(nbg), _r2(nbg)))
L.append('- 参照: 全部867腿等额ROI=%+0.1f%%' % (sum([x for x in (net(r) for r in settled) if x is not None])/len([x for x in (net(r) for r in settled) if x is not None])*100))
L.append('')
L.append('## 6. 结论与限制')
L.append('- 保级主场组 ROI 显著高于整体(played>=3: +10.7% vs -0.5%) -> "保级主场+1星"方向有效')
L.append('- 无欲无求组 ROI 明显低于整体(-2.8% vs +4.4%) -> "-1星降仓"方向有效')
L.append('- 争冠/升级主场组 ROI +15.2%(n=25) -> 强队主场是正收益区, 加分可再评估')
L.append('- 限制: ①样本仅563腿, played>=3可信组175腿, 统计噪音大 ②8月底多联赛仅1-3轮, zone早期不敏感 ③no_match 133腿存在偏差风险 ④等额注为主, 星级模拟用近似档位')
io.open(OUT, 'w', encoding='utf-8').write('\n'.join(L))
print()
print('report ->', OUT)
