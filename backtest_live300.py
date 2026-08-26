# -*- coding: utf-8 -*-
"""
实盘账本 300 场回测（无泄漏口径）
================================
预测输入: 仅读账本赛前固化字段 (bet_name/prob/odds/ev/star/risk_tags/snap_age_h)
结算: 仅用 result (win/lose/push/half/VOID) 等额注净值
禁止: 不重跑模型、不用比分反推、不修改任何预测字段
"""
import csv, collections, io, sys, datetime

sys.stdout.reconfigure(encoding='utf-8')

LEDGER = r'D:\足球分析\analysis_records\bet_ledger.csv'
OUT = r'D:\足球分析\analysis_records\backtest_live300_report.csv'

def g(r, k):
    return (r.get(k) or '').strip()

def grp(name):
    n = name
    if n.startswith(('大', '小')):
        return '大小球'
    if n.startswith(('1X2', '胜平负')):
        return '1X2'
    if n.startswith(('让球主', '让球客')) or ('让' in n and ('(+' in n or '(-' in n)):
        return '让球'
    return '其他'

def net(r):
    o = float(g(r, 'odds'))
    res = g(r, 'result')
    if res == 'win':
        return o - 1.0
    if res == 'half':
        return (o - 1.0) / 2.0
    if res in ('push', 'VOID'):
        return 0.0
    if res == 'lose':
        return -1.0
    return None

def stats(rows):
    n = len(rows)
    wins = sum(1 for r in rows if g(r, 'result') == 'win')
    half = sum(1 for r in rows if g(r, 'result') == 'half')
    push = sum(1 for r in rows if g(r, 'result') in ('push', 'VOID'))
    lose = sum(1 for r in rows if g(r, 'result') == 'lose')
    dec = wins + half + lose
    hit = (wins + half * 0.5) / dec if dec else float('nan')
    nets = [net(r) for r in rows]
    nets = [x for x in nets if x is not None]
    pnl = sum(nets)
    roi = pnl / len(nets) if nets else float('nan')
    return {'N': n, 'win': wins, 'half': half, 'push': push, 'lose': lose,
            '判定': dec, '命中率': hit, 'PnL': pnl, 'ROI': roi}

def fmt(s):
    return '%5d  win=%3d half=%2d push=%2d lose=%3d | 命中=%5.1f%%  PnL=%+7.2f  ROI=%+6.1f%%' % (
        s['N'], s['win'], s['half'], s['push'], s['lose'],
        s['命中率'] * 100 if s['命中率'] == s['命中率'] else float('nan'),
        s['PnL'], s['ROI'] * 100 if s['ROI'] == s['ROI'] else float('nan'))

def main():
    rows = list(csv.DictReader(io.open(LEDGER, 'r', encoding='utf-8-sig')))
    valid = [r for r in rows if net(r) is not None]
    matches = collections.OrderedDict()
    for r in valid:
        matches.setdefault((g(r, 'match'), g(r, 'kickoff')), []).append(r)
    print('=' * 78)
    print('实盘账本回测（无泄漏口径：赛前固化预测 + result 结算）')
    print('=' * 78)
    print('样本: %d 腿 / %d 场  (账本总 %d 腿, 可结算 %d, 剔除未提取 %d)'
          % (len(valid), len(matches), len(rows), len(valid), len(rows) - len(valid)))
    kk = [x for x in (g(r, 'kickoff') for r in valid) if x]
    if kk:
        print('赛程范围: %s ~ %s' % (min(kk)[:16], max(kk)[:16]))

    print()
    print('【1. 总体】')
    print(fmt(stats(valid)))
    # 仅 star 非空
    star_rows = [r for r in valid if g(r, 'star')]
    print('仅 star非空(正式口径):')
    print('  ' + fmt(stats(star_rows)))

    print()
    print('【2. 按方向组】')
    by_grp = collections.defaultdict(list)
    for r in valid:
        by_grp[grp(g(r, 'bet_name'))].append(r)
    for k in ['1X2', '让球', '大小球', '其他']:
        if by_grp[k]:
            print('%-4s ' % k + fmt(stats(by_grp[k])))

    print()
    print('【3. 按星级(star)】')
    by_star = collections.defaultdict(list)
    for r in valid:
        s = g(r, 'star')
        by_star[s if s else '无star'].append(r)
    for k in sorted([x for x in by_star if x != '无star'], key=lambda x: int(x)):
        print('★%s    ' % k + fmt(stats(by_star[k])))
    if by_star.get('无star'):
        print('无star ' + fmt(stats(by_star['无star'])))

    print()
    print('【4. 按EV档】')
    def evtier(r):
        try:
            e = float(g(r, 'ev'))
        except Exception:
            return '无ev'
        if e >= 0.20:
            return 'EV>=20%'
        if e >= 0.08:
            return 'EV 8-20%'
        if e >= 0.05:
            return 'EV 5-8%'
        if e >= 0:
            return 'EV 0-5%'
        return 'EV<0'
    by_ev = collections.defaultdict(list)
    for r in valid:
        by_ev[evtier(r)].append(r)
    for k in ['EV>=20%', 'EV 8-20%', 'EV 5-8%', 'EV 0-5%', 'EV<0', '无ev']:
        if by_ev[k]:
            print('%-9s ' % k + fmt(stats(by_ev[k])))

    print()
    print('【5. 按联赛】')
    by_lg = collections.defaultdict(list)
    for r in valid:
        by_lg[g(r, 'league')].append(r)
    for k, v in sorted(by_lg.items(), key=lambda kv: -len(kv[1])):
        print('%-6s ' % k + fmt(stats(v)))

    print()
    print('【6. 按来源】')
    by_src = collections.defaultdict(list)
    for r in valid:
        by_src[g(r, 'src')].append(r)
    for k, v in sorted(by_src.items(), key=lambda kv: -len(kv[1])):
        print('%-12s ' % k + fmt(stats(v)))

    print()
    print('【7. 筛选策略模拟(等额注)】')
    def filt(name, pred):
        sub = [r for r in valid if pred(r)]
        print('%-28s ' % name + fmt(stats(sub)))
    filt('全量(star不限)', lambda r: True)
    filt('star>=1', lambda r: g(r, 'star').isdigit() and int(g(r, 'star')) >= 1)
    filt('star>=2', lambda r: g(r, 'star').isdigit() and int(g(r, 'star')) >= 2)
    filt('star>=3', lambda r: g(r, 'star').isdigit() and int(g(r, 'star')) >= 3)
    filt('EV>=8%', lambda r: g(r, 'ev') and float(g(r, 'ev')) >= 0.08)
    filt('EV>=20%', lambda r: g(r, 'ev') and float(g(r, 'ev')) >= 0.20)
    filt('star>=1 且 EV>=8%', lambda r: g(r, 'star').isdigit() and int(g(r, 'star')) >= 1 and g(r, 'ev') and float(g(r, 'ev')) >= 0.08)
    filt('star>=2 且 EV>=8%', lambda r: g(r, 'star').isdigit() and int(g(r, 'star')) >= 2 and g(r, 'ev') and float(g(r, 'ev')) >= 0.08)

    print()
    print('【8. 模型概率 vs 市场隐含 vs 实际命中(按方向组)】')
    for k in ['1X2', '让球', '大小球']:
        sub = by_grp[k]
        if not sub:
            continue
        s = stats(sub)
        imp = [1.0 / float(g(r, 'odds')) for r in sub]
        prob = [float(g(r, 'prob')) for r in sub]
        print('%-4s 模型均prob=%5.1f%%  市场隐含均=%5.1f%%  实际命中=%5.1f%%  (判定局=%d)'
              % (k, sum(prob) / len(prob) * 100, sum(imp) / len(imp) * 100,
                 s['命中率'] * 100, s['判定']))

    print()
    print('【9. 方向细分(命中/ROI)】')
    def subname(n):
        if n.startswith('1X2主胜'): return '1X2主胜'
        if n.startswith('1X2平局'): return '1X2平局'
        if n.startswith('1X2客胜'): return '1X2客胜'
        if n.startswith('让球主'): return '让球主(+号/主受让或让球)'
        if n.startswith('让球客'): return '让球客(+号/客受让或让球)'
        if n.startswith('大'): return '大球'
        if n.startswith('小'): return '小球'
        return '其他'
    by_name = collections.defaultdict(list)
    for r in valid:
        by_name[subname(g(r, 'bet_name'))].append(r)
    for k in ['1X2主胜', '1X2平局', '1X2客胜', '让球主(+号/主受让或让球)', '让球客(+号/客受让或让球)', '大球', '小球', '其他']:
        if by_name[k]:
            print('%-22s ' % k + fmt(stats(by_name[k])))

    print()
    print('【10. 按快照年龄(snap_age_h)】')
    def age_tier(r):
        try:
            a = float(g(r, 'snap_age_h'))
        except Exception:
            return '无snap'
        if a < 0:
            return '赛后补录(<0h)'
        if a <= 2:
            return '临场(<=2h)'
        if a <= 6:
            return '近盘(2-6h)'
        if a <= 24:
            return '中盘(6-24h)'
        return '过期(>24h)'
    by_age = collections.defaultdict(list)
    for r in valid:
        by_age[age_tier(r)].append(r)
    for k in ['临场(<=2h)', '近盘(2-6h)', '中盘(6-24h)', '过期(>24h)', '赛后补录(<0h)', '无snap']:
        if by_age[k]:
            print('%-14s ' % k + fmt(stats(by_age[k])))

    print()
    print('【11. 星级 × EV 交叉(仅star非空)】')
    for sk in ['1', '2', '3']:
        sub = [r for r in valid if g(r, 'star') == sk]
        if not sub:
            continue
        hi = [r for r in sub if g(r, 'ev') and float(g(r, 'ev')) >= 0.20]
        lo = [r for r in sub if not (g(r, 'ev') and float(g(r, 'ev')) >= 0.20)]
        if hi:
            print('★%s 且 EV>=20%%: ' % sk + fmt(stats(hi)))
        if lo:
            print('★%s 且 EV<20%%:  ' % sk + fmt(stats(lo)))

    # 导出明细CSV
    with io.open(OUT, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['league', 'match', 'kickoff', 'bet_name', 'grp', 'odds', 'ev', 'star',
                    'result', 'net', 'src', 'snap_age_h'])
        for r in valid:
            w.writerow([g(r, 'league'), g(r, 'match'), g(r, 'kickoff'), g(r, 'bet_name'),
                        grp(g(r, 'bet_name')), g(r, 'odds'), g(r, 'ev'), g(r, 'star'),
                        g(r, 'result'), round(net(r), 4), g(r, 'src'), g(r, 'snap_age_h')])
    print()
    print('明细已导出: %s' % OUT)

if __name__ == '__main__':
    main()
